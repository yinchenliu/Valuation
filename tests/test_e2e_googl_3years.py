"""E2E test: Extract GOOGL financials from 3 separate 10-K PDFs, merge, and run DCF.

Each 10-K is processed independently by the LLM extractor. The results are
merged into a single FinancialStatements object (deduplicating by year,
preferring the filing that "owns" that fiscal year).

Usage:
    set GEMINI_API_KEY=AIza...
    python tests/test_e2e_googl_3years.py
"""
import sys
sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")

from ingestion.claude_extractor import extract_financials
from ingestion.price_fetcher import fetch_price_data
from analysis.capm import run_capm
from analysis.normalizer import normalize_financials
from analysis.wacc import calculate_wacc
from analysis.projector import derive_assumptions, project_fcffs
from analysis.fcff import calculate_fcff_historical
from analysis.dcf import run_dcf
from models.financial_statements import FinancialStatements

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
TICKER = "GOOGL"
COMPANY = "Alphabet Inc."
PROVIDER = "gemini"
MODEL = None  # use provider default

# 10-K PDFs — each covers one fiscal year (with prior-year comparatives)
PDF_DIR = r"C:\Users\yinchenliu\Downloads\google"
PDFS = [
    (2023, rf"{PDF_DIR}\Alphabet Inc._10-K_2023-12-31_English.pdf"),
    (2024, rf"{PDF_DIR}\Alphabet Inc._10-K_2024-12-31_English.pdf"),
    (2025, rf"{PDF_DIR}\Alphabet Inc._10-K_2025-12-31T00_00_00_English.pdf"),
]

# ---------------------------------------------------------------------------
# Step 1: Extract from each PDF
# ---------------------------------------------------------------------------
all_income = {}      # year -> IncomeStatement
all_balance = {}     # year -> BalanceSheet (latest only per filing)
all_cashflow = {}    # year -> CashFlowStatement
all_adjustments = [] # merged non-recurring items

for fiscal_year, pdf_path in PDFS:
    print("\n" + "=" * 65)
    print(f"EXTRACTING: {pdf_path.split(chr(92))[-1]}  (fiscal {fiscal_year})")
    print("=" * 65)

    fin, adj = extract_financials(
        pdf_path=pdf_path,
        ticker=TICKER,
        company_name=COMPANY,
        provider=PROVIDER,
        model=MODEL,
    )

    # Merge: for each year in this extraction, prefer the "primary" filing
    # (the filing whose fiscal_year matches) over comparative data from other filings
    for stmt in fin.income_statements:
        y = stmt.year
        if y not in all_income or y == fiscal_year:
            all_income[y] = stmt
    for stmt in fin.balance_sheets:
        y = stmt.year
        if y not in all_balance or y == fiscal_year:
            all_balance[y] = stmt
    for stmt in fin.cash_flow_statements:
        y = stmt.year
        if y not in all_cashflow or y == fiscal_year:
            all_cashflow[y] = stmt

    # Merge non-recurring items (dedupe by year+amount+direction)
    existing = {(a.year, a.amount, a.direction) for a in all_adjustments}
    for a in adj:
        key = (a.year, a.amount, a.direction)
        if key not in existing:
            all_adjustments.append(a)
            existing.add(key)

# Build merged FinancialStatements (GAAP — pre-adjustment)
gaap_financials = FinancialStatements(
    ticker=TICKER,
    company_name=COMPANY,
    income_statements=sorted(all_income.values(), key=lambda x: x.year),
    balance_sheets=sorted(all_balance.values(), key=lambda x: x.year),
    cash_flow_statements=sorted(all_cashflow.values(), key=lambda x: x.year),
)

years = gaap_financials.years
print("\n" + "=" * 65)
print(f"MERGED FINANCIALS — {len(years)} years: {years}")
print("=" * 65)

# ---------------------------------------------------------------------------
# Step 2: Balance sheet check (latest year only now)
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("BS BALANCE CHECK")
print("=" * 65)
for bs in gaap_financials.balance_sheets:
    y = bs.year
    assets = bs.total_assets
    le = bs.total_liabilities + bs.total_equity
    diff = abs(assets - le)
    pct = diff / assets * 100 if assets else 0
    flag = "OK" if pct < 2.0 else "WARN"
    print(f"  {y}: Assets={assets:,.0f}  Liab+Eq={le:,.0f}  "
          f"Diff={diff:,.0f} ({pct:.2f}%)  {flag}")

# ---------------------------------------------------------------------------
# Step 3: GAAP I/S -> Adjustments -> Non-GAAP I/S
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("INCOME STATEMENT: GAAP -> ADJUSTMENTS -> NON-GAAP")
print("=" * 65)

# Group adjustments by year
adj_by_year: dict[int, list] = {}
for a in all_adjustments:
    adj_by_year.setdefault(a.year, []).append(a)

# Apply normalization to get Non-GAAP financials
adjusted_financials = normalize_financials(gaap_financials, all_adjustments)

for y in years:
    gaap_is = gaap_financials.get_income_statement(y)
    adj_is = adjusted_financials.get_income_statement(y)
    yr_adj = adj_by_year.get(y, [])

    print(f"\n  --- {y} ---")
    print(f"  {'Line Item':<28} {'GAAP':>10} {'Adj':>10} {'Non-GAAP':>10}")
    print(f"  {'-'*62}")

    for label, field in [
        ("Revenue",                "revenue"),
        ("Cost of Revenue",        "cost_of_revenue"),
        ("Gross Profit",           "gross_profit"),
        ("SG&A",                   "sga"),
        ("R&D",                    "rd_expense"),
        ("D&A",                    "depreciation_amortization"),
        ("Other OpEx",             "other_operating_expense"),
        ("Operating Income",       "ebit"),
        ("Interest Expense",       "interest_expense"),
        ("Interest Income",        "interest_income"),
        ("Other Non-Operating",    "other_non_operating"),
        ("EBT",                    "ebt"),
        ("Tax Expense",            "tax_expense"),
        ("Net Income",             "net_income"),
    ]:
        gaap_val = getattr(gaap_is, field)
        adj_val = getattr(adj_is, field)
        diff = adj_val - gaap_val
        diff_str = f"{diff:>+10,.0f}" if abs(diff) > 0.5 else f"{'—':>10}"
        print(f"  {label:<28} {gaap_val:>10,.0f} {diff_str} {adj_val:>10,.0f}")

    print(f"  {'Operating Margin':<28} {gaap_is.operating_margin:>10.1%} {'':>10} {adj_is.operating_margin:>10.1%}")

    if yr_adj:
        print(f"\n  Adjustments applied:")
        for item in yr_adj:
            sign = "+" if item.direction == "add_back" else "-"
            print(f"    {sign}{item.amount:,.0f}M on {item.line_item} — {item.description}")

# ---------------------------------------------------------------------------
# Step 4: Historical FCFF
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("HISTORICAL FCFF (CFO-based, $M)")
print("=" * 65)
print(f"  {'Year':>4}  {'Revenue':>9}  {'CFO':>8}  {'Int*(1-t)':>9}  "
      f"{'CapEx':>7}  {'FCFF':>8}  {'FCFF%':>6}")
print("  " + "-" * 60)

for y in years:
    is_ = gaap_financials.get_income_statement(y)
    cf_ = gaap_financials.get_cash_flow(y)
    if is_ and cf_:
        h = calculate_fcff_historical(is_, cf_)
        print(f"  {y:>4}  {h.revenue:>9,.0f}  {h.cfo:>8,.0f}  "
              f"{h.after_tax_interest:>9,.0f}  {h.capital_expenditures:>7,.0f}  "
              f"{h.fcff:>8,.0f}  {h.fcff_margin:>5.1%}")

# ---------------------------------------------------------------------------
# Step 4b: Historical NWC from CFS
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("HISTORICAL NWC (from CFS 'Changes in assets & liabilities')")
print("=" * 65)
print(f"  {'Year':>4}  {'Revenue':>9}  {'dNWC (CFS)':>11}  {'dNWC/Rev':>8}")
print("  " + "-" * 40)
for y in years:
    is_ = gaap_financials.get_income_statement(y)
    cf_ = gaap_financials.get_cash_flow(y)
    if is_ and cf_:
        delta_wc = cf_.change_in_working_capital
        pct = -delta_wc / is_.revenue if is_.revenue else 0
        print(f"  {y:>4}  {is_.revenue:>9,.0f}  {delta_wc:>+11,.0f}  {pct:>7.1%}")

# ---------------------------------------------------------------------------
# Step 5: Full DCF (assumptions from Non-GAAP / adjusted financials)
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("FULL DCF VALUATION (assumptions from Non-GAAP financials)")
print("=" * 65)

assumptions = derive_assumptions(adjusted_financials)
price_data = fetch_price_data(TICKER, lookback_years=5, frequency="monthly")
capm_result = run_capm(price_data)

import yfinance as yf
info = yf.Ticker(TICKER).info
shares = info.get("sharesOutstanding", 0) / 1e6
market_cap = price_data.current_price * shares

latest_is = adjusted_financials.get_income_statement(adjusted_financials.latest_year)
latest_bs = adjusted_financials.get_balance_sheet(adjusted_financials.latest_year)

wacc_result = calculate_wacc(
    capm_result=capm_result,
    income_statement=latest_is,
    balance_sheet=latest_bs,
    market_cap=market_cap,
)
projected = project_fcffs(adjusted_financials, assumptions)
dcf = run_dcf(
    projected_fcffs=projected,
    wacc_result=wacc_result,
    financials=adjusted_financials,
    terminal_growth_rate=assumptions["terminal_growth_rate"],
    current_price=price_data.current_price,
    diluted_shares=shares,
)

print(f"\n  Beta:               {capm_result.beta:.3f}")
print(f"  Cost of Equity:     {capm_result.cost_of_equity:.2%}")
print(f"  WACC:               {dcf.wacc:.2%}")
print(f"  Terminal growth:    {dcf.terminal_growth_rate:.2%}")
print(f"\n  Revenue growth assumptions: {[f'{r:.1%}' for r in assumptions['revenue_growth_rates']]}")
print(f"  Operating margin:   {assumptions['operating_margin']:.1%}")
print(f"  Tax rate:           {assumptions['tax_rate']:.1%}")
print(f"\n  PV FCFFs:           ${dcf.pv_fcffs:>12,.0f}M")
print(f"  PV Terminal Value:  ${dcf.pv_terminal_value:>12,.0f}M")
print(f"  Enterprise Value:   ${dcf.enterprise_value:>12,.0f}M")
print(f"  Net Debt:           ${dcf.net_debt:>12,.0f}M")
print(f"  Equity Value:       ${dcf.equity_value:>12,.0f}M")
print(f"  Diluted Shares:     {dcf.diluted_shares:>12,.0f}M")
print(f"  Implied Price:      ${dcf.implied_share_price:>11.2f}")
print(f"  Current Price:      ${dcf.current_price:>11.2f}")
direction = "UPSIDE" if dcf.upside_downside > 0 else "DOWNSIDE"
print(f"  {direction}:          {dcf.upside_downside:>+11.1f}%")
