"""E2E test: LLY multi-year DCF from three 10-K PDFs.

Caches LLM extraction results to avoid repeat API calls.
Delete the cache file to force re-extraction.

Usage:
    python tests/test_e2e_lly.py
"""
import sys
import pickle
from pathlib import Path

sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")

from ingestion.claude_extractor import extract_multi_year
from ingestion.price_fetcher import fetch_price_data
from analysis.capm import run_capm
from analysis.wacc import calculate_wacc
from analysis.projector import derive_assumptions, project_fcffs
from analysis.normalizer import normalize_financials
from analysis.fcff import calculate_fcff_historical
from analysis.dcf import run_dcf

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
TICKER       = "LLY"
COMPANY      = "Eli Lilly and Company"
PROVIDER     = "gemini"
MODEL        = "gemini-3.1-flash-lite-preview"

FILINGS = [
    (2023, r"C:\Users\yinchenliu\Downloads\LLY\Eli Lilly and Company_10-K_2023-12-31_English_218432882_1.pdf"),
    (2024, r"C:\Users\yinchenliu\Downloads\LLY\Eli Lilly and Company_10-K_2024-12-31_English_237118761_1.pdf"),
    (2025, r"C:\Users\yinchenliu\Downloads\LLY\Eli Lilly and Company_10-K_2025-12-31_English_255397128_1.pdf"),
]

CACHE_FILE = Path(__file__).parent / f".cache_{TICKER.lower()}_extraction.pkl"

# ---------------------------------------------------------------------------
# LLM extraction (multi-PDF) — cached
# ---------------------------------------------------------------------------
if CACHE_FILE.exists():
    print("=" * 65)
    print(f"LOADING CACHED EXTRACTION: {CACHE_FILE.name}")
    print("=" * 65)
    with open(CACHE_FILE, "rb") as f:
        financials, adjustments = pickle.load(f)
else:
    print("=" * 65)
    print(f"PHASE 1: {PROVIDER.upper()} extracting financials from {len(FILINGS)} 10-K PDFs")
    print("=" * 65)
    financials, adjustments = extract_multi_year(
        filings=FILINGS,
        ticker=TICKER,
        company_name=COMPANY,
        provider=PROVIDER,
        model=MODEL,
        debug=True,
    )
    with open(CACHE_FILE, "wb") as f:
        pickle.dump((financials, adjustments), f)
    print(f"  Cached to {CACHE_FILE.name}")

years = financials.years
print(f"  Years extracted: {years}")

# ---------------------------------------------------------------------------
# Balance sheet balance check
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("BS BALANCE CHECK (all years)")
print("=" * 65)
for y in years:
    bs = financials.get_balance_sheet(y)
    if bs is None:
        print(f"  {y}: No B/S (only extracted from latest filing)")
        continue
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
# Normalize financials (apply NRI adjustments)
# ---------------------------------------------------------------------------
print("=" * 65)
print("NORMALIZING FINANCIALS (applying NRI adjustments)")
print("=" * 65)
adjusted = normalize_financials(financials, adjustments)
for y in years:
    raw_is = financials.get_income_statement(y)
    adj_is = adjusted.get_income_statement(y)
    print(f"  {y}: Op. Income  GAAP={raw_is.ebit:>10,.0f}  "
          f"Adj={adj_is.ebit:>10,.0f}  "
          f"Delta={adj_is.ebit - raw_is.ebit:>+10,.0f}")

# ---------------------------------------------------------------------------
# Derive assumptions from adjusted financials
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("PROJECTION ASSUMPTIONS (from adjusted financials)")
print("=" * 65)

latest_is = adjusted.get_income_statement(adjusted.latest_year)
latest_bs = adjusted.get_balance_sheet(adjusted.latest_year)

assumptions = derive_assumptions(adjusted)
print(f"  Revenue growth (CAGR):   {assumptions['revenue_growth_rates'][0]:.2%}")
print(f"  Operating margin:        {assumptions['operating_margin']:.2%}")
print(f"  Tax rate:                {assumptions['tax_rate']:.2%}")
print(f"  D&A % revenue:           {assumptions['da_pct_revenue']:.2%}")
print(f"  CapEx % revenue:         {assumptions['capex_pct_revenue']:.2%}")
print(f"  NWC % revenue:           {assumptions['nwc_pct_revenue']:.2%}")
print(f"  Projection years:        {assumptions['projection_years']}")
print(f"  Terminal growth:          {assumptions['terminal_growth_rate']:.2%}")

# ---------------------------------------------------------------------------
# Full DCF
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("FULL DCF ON ADJUSTED DATA")
print("=" * 65)
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
projected = project_fcffs(adjusted, assumptions)
dcf = run_dcf(
    projected_fcffs=projected,
    wacc_result=wacc_result,
    financials=adjusted,
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
