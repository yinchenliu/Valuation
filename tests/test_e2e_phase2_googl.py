"""Phase 2 test: LLM extracts GOOGL financials from a 10-K PDF.

Supports two providers — choose by setting PROVIDER below:
  "claude"  →  requires ANTHROPIC_API_KEY env var
  "gemini"  →  requires GEMINI_API_KEY env var

Usage:
    set GEMINI_API_KEY=AIza...
    python tests/test_e2e_phase2_googl.py
"""
import sys
sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")

from ingestion.claude_extractor import extract_financials
from ingestion.price_fetcher import fetch_price_data
from analysis.capm import run_capm
from analysis.wacc import calculate_wacc
from analysis.projector import derive_assumptions, project_fcffs
from analysis.fcff import calculate_fcff_historical
from analysis.dcf import run_dcf

# ---------------------------------------------------------------------------
# CONFIGURATION — edit these
# ---------------------------------------------------------------------------
TICKER       = "GOOGL"
PDF_PATH     = r"C:\Users\yinchenliu\Downloads\google\Alphabet Inc._10-K_2024-12-31_English.pdf"
PROVIDER     = "gemini"   # "claude" or "gemini"
MODEL        = None       # None = use provider default

# ---------------------------------------------------------------------------
# Phase 2: LLM extraction (PDF only)
# ---------------------------------------------------------------------------
print("=" * 65)
print(f"PHASE 2: {PROVIDER.upper()} extracting financials from 10-K PDF")
print("=" * 65)
financials, adjustments = extract_financials(
    pdf_path=PDF_PATH,
    ticker=TICKER,
    company_name="Alphabet Inc.",
    provider=PROVIDER,
    model=MODEL,
    debug=True,
)

years = financials.years
print(f"  Years extracted: {years}")

# ---------------------------------------------------------------------------
# Balance sheet balance check — all years
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("BS BALANCE CHECK (all years)")
print("=" * 65)
for y in years:
    bs = financials.get_balance_sheet(y)
    assets = bs.total_assets
    le = bs.total_liabilities + bs.total_equity
    diff = abs(assets - le)
    pct = diff / assets * 100 if assets else 0
    flag = "OK" if pct < 2.0 else "WARN"
    print(f"  {y}: Assets={assets:,.0f}  Liab+Eq={le:,.0f}  "
          f"Diff={diff:,.0f} ({pct:.2f}%)  {flag}")

# ---------------------------------------------------------------------------
# Historical FCFF
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("HISTORICAL FCFF (CFO-based, $M)")
print("=" * 65)
print(f"  {'Year':>4}  {'Revenue':>9}  {'CFO':>8}  {'Int*(1-t)':>9}  "
      f"{'CapEx':>7}  {'FCFF':>8}  {'FCFF%':>6}")
print("  " + "-" * 60)

for y in years:
    is_ = financials.get_income_statement(y)
    cf_ = financials.get_cash_flow(y)
    h = calculate_fcff_historical(is_, cf_)
    print(f"  {y:>4}  {h.revenue:>9,.0f}  {h.cfo:>8,.0f}  "
          f"{h.after_tax_interest:>9,.0f}  {h.capital_expenditures:>7,.0f}  "
          f"{h.fcff:>8,.0f}  {h.fcff_margin:>5.1%}")

# ---------------------------------------------------------------------------
# Non-recurring items
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print(f"NON-RECURRING ITEMS (identified by {PROVIDER.upper()})")
print("=" * 65)
if not adjustments:
    print("  None found.")
else:
    total_add_back = sum(a.amount for a in adjustments if a.direction == "add_back")
    total_remove   = sum(a.amount for a in adjustments if a.direction == "remove")
    print(f"  Found {len(adjustments)} items  |  "
          f"Total add-backs: {total_add_back:,.0f}M  |  Total removals: {total_remove:,.0f}M\n")
    for item in adjustments:
        sign = "+" if item.direction == "add_back" else "-"
        print(f"  [{item.year}] {sign}{item.amount:,.0f}M  {item.category.upper()}  "
              f"({item.confidence} confidence)  line_item={item.line_item}")
        print(f"         {item.description}")
        if item.source:
            print(f"         Source: {item.source}")
        print()

# ---------------------------------------------------------------------------
# Full DCF
# ---------------------------------------------------------------------------
print("=" * 65)
print("FULL DCF ON LLM-EXTRACTED DATA")
print("=" * 65)

latest_is = financials.get_income_statement(financials.latest_year)
latest_bs = financials.get_balance_sheet(financials.latest_year)

assumptions = derive_assumptions(financials)
price_data  = fetch_price_data(TICKER, lookback_years=5, frequency="monthly")
capm_result = run_capm(price_data)

import yfinance as yf
info       = yf.Ticker(TICKER).info
shares     = info.get("sharesOutstanding", 0) / 1e6
market_cap = price_data.current_price * shares

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

print(f"  WACC:               {dcf.wacc:.2%}")
print(f"  Terminal growth:    {dcf.terminal_growth_rate:.2%}")
print(f"  PV FCFFs:           ${dcf.pv_fcffs:>12,.0f}M")
print(f"  PV Terminal Value:  ${dcf.pv_terminal_value:>12,.0f}M")
print(f"  Enterprise Value:   ${dcf.enterprise_value:>12,.0f}M")
print(f"  Net Debt:           ${dcf.net_debt:>12,.0f}M")
print(f"  Equity Value:       ${dcf.equity_value:>12,.0f}M")
print(f"  Implied Price:      ${dcf.implied_share_price:>11.2f}")
print(f"  Current Price:      ${dcf.current_price:>11.2f}")
direction = "UPSIDE" if dcf.upside_downside > 0 else "DOWNSIDE"
print(f"  {direction}:          {dcf.upside_downside:>+11.1f}%")
