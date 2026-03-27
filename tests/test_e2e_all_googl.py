"""Run full DCF pipeline on all GOOGL 10-K PDFs in the google folder."""
import sys
sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")

from pathlib import Path
from ingestion.claude_extractor import extract_financials
from ingestion.price_fetcher import fetch_price_data
from analysis.capm import run_capm
from analysis.wacc import calculate_wacc
from analysis.projector import derive_assumptions, project_fcffs
from analysis.fcff import calculate_fcff_historical
from analysis.dcf import run_dcf

TICKER = "GOOGL"
PROVIDER = "gemini"
PDF_DIR = Path(r"C:\Users\yinchenliu\Downloads\google")

PDFS = sorted(PDF_DIR.glob("*.pdf"))

for pdf_path in PDFS:
    print("\n" + "#" * 70)
    print(f"# PROCESSING: {pdf_path.name}")
    print("#" * 70)

    try:
        financials, adjustments = extract_financials(
            pdf_path=str(pdf_path),
            ticker=TICKER,
            company_name="Alphabet Inc.",
            provider=PROVIDER,
            debug=False,
        )

        years = financials.years
        print(f"  Years extracted: {years}")

        # BS balance check
        print(f"\n  {'Year':>4}  {'Assets':>12}  {'Liab+Eq':>12}  {'Diff':>10}  {'%':>6}  Status")
        for y in years:
            bs = financials.get_balance_sheet(y)
            assets = bs.total_assets
            le = bs.total_liabilities + bs.total_equity
            diff = abs(assets - le)
            pct = diff / assets * 100 if assets else 0
            flag = "OK" if pct < 2.0 else "WARN"
            print(f"  {y:>4}  {assets:>12,.0f}  {le:>12,.0f}  {diff:>10,.0f}  {pct:>5.1f}%  {flag}")

        # Historical FCFF
        print(f"\n  {'Year':>4}  {'Revenue':>9}  {'CFO':>8}  {'CapEx':>7}  {'FCFF':>8}  {'Margin':>6}")
        for y in years:
            is_ = financials.get_income_statement(y)
            cf_ = financials.get_cash_flow(y)
            h = calculate_fcff_historical(is_, cf_)
            print(f"  {y:>4}  {h.revenue:>9,.0f}  {h.cfo:>8,.0f}  {h.capital_expenditures:>7,.0f}  {h.fcff:>8,.0f}  {h.fcff_margin:>5.1%}")

        # Non-recurring
        if adjustments:
            print(f"\n  Non-recurring items: {len(adjustments)}")
            for item in adjustments:
                sign = "+" if item.direction == "add_back" else "-"
                print(f"    [{item.year}] {sign}{item.amount:,.0f}M {item.category} — {item.description}")

        # DCF
        assumptions = derive_assumptions(financials)
        price_data = fetch_price_data(TICKER, lookback_years=5, frequency="monthly")
        capm_result = run_capm(price_data)

        import yfinance as yf
        info = yf.Ticker(TICKER).info
        shares = info.get("sharesOutstanding", 0) / 1e6
        market_cap = price_data.current_price * shares

        latest_is = financials.get_income_statement(financials.latest_year)
        latest_bs = financials.get_balance_sheet(financials.latest_year)

        wacc_result = calculate_wacc(
            capm_result=capm_result,
            income_statement=latest_is,
            balance_sheet=latest_bs,
            market_cap=market_cap,
        )
        projected = project_fcffs(financials, assumptions)
        dcf = run_dcf(
            projected_fcffs=projected,
            wacc_result=wacc_result,
            financials=financials,
            terminal_growth_rate=assumptions["terminal_growth_rate"],
            current_price=price_data.current_price,
            diluted_shares=shares,
        )

        print(f"\n  === DCF RESULT ===")
        print(f"  WACC:              {dcf.wacc:.2%}")
        print(f"  Enterprise Value:  ${dcf.enterprise_value:>12,.0f}M")
        print(f"  Net Debt:          ${dcf.net_debt:>12,.0f}M")
        print(f"  Equity Value:      ${dcf.equity_value:>12,.0f}M")
        print(f"  Implied Price:     ${dcf.implied_share_price:>11.2f}")
        print(f"  Current Price:     ${dcf.current_price:>11.2f}")
        direction = "UPSIDE" if dcf.upside_downside > 0 else "DOWNSIDE"
        print(f"  {direction}:         {dcf.upside_downside:>+11.1f}%")

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
