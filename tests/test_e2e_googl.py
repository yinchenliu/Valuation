"""End-to-end Phase 1 test: GOOGL valuation using Capital IQ data.

ARCHITECTURE NOTE
-----------------
Phase 1 — pure math contract:
  ProjectionAssumptions -> capm / wacc / fcff / projector / dcf -> DCFResult

Phase 2 (not yet implemented) — Claude as data extraction layer:
  Raw Excel F/S  -+
                  +-> claude_extractor.py -> FinancialStatements (same contract)
  10-K PDF       -+                       -> NonRecurringItems (GAAP adjustments)

This test uses the legacy Capital IQ adapter (capital_iq_parser.py) purely
to populate the Phase 1 contract for validation. In production, Phase 2 will
replace that adapter with Claude — supporting any company layout and
simultaneously flagging non-recurring items.

FCFF APPROACH
-------------
Historical FCFF (CFO-based):  FCFF = CFO + Interest*(1-t) - CapEx
  Uses the actual reported cash flow statement. More accurate because it
  captures all operating cash movements as reported, including working
  capital changes, SBC, deferred taxes, etc.

Projected FCFF (EBIT-based):  FCFF = EBIT*(1-t) + D&A - CapEx - dNWC
  Built from income statement assumptions where no actual CF statement exists.

Covers:
  1. Parse Capital IQ Excel (Phase 1 legacy adapter)
  2. Balance Sheet validation (assets = liabilities + equity)
  3. Historical FCFF — CFO-based
  4. Derive projection assumptions
  5. CAPM beta regression
  6. WACC calculation
  7. Projected FCFFs (5 years, EBIT-based)
  8. DCF valuation — implied share price vs current price
"""
import sys
sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")

from ingestion.capital_iq_parser import parse_capital_iq   # Phase 1 legacy adapter
from ingestion.price_fetcher import fetch_price_data
from analysis.capm import run_capm
from analysis.wacc import calculate_wacc
from analysis.projector import derive_assumptions, project_fcffs
from analysis.fcff import calculate_fcff_historical
from analysis.dcf import run_dcf

TICKER = "GOOGL"
FILE = r"C:\Users\yinchenliu\Downloads\AlphabetInc.NASDAQGSGOOGL_Report_03-02-2026.xlsx"

# ---------------------------------------------------------------------------
# 1. Parse financials
# ---------------------------------------------------------------------------
print("=" * 65)
print("1. PARSING CAPITAL IQ FINANCIALS")
print("=" * 65)
financials = parse_capital_iq(FILE, TICKER, "Alphabet Inc.")
years = financials.years
print(f"   Years parsed: {years}   Latest: {financials.latest_year}")

latest_is = financials.get_income_statement(financials.latest_year)
latest_bs = financials.get_balance_sheet(financials.latest_year)
latest_cf = financials.get_cash_flow(financials.latest_year)

print(f"\n   Income Statement ({financials.latest_year}, $M):")
print(f"     Revenue:         {latest_is.revenue:>12,.0f}")
print(f"     Cost of Revenue: {latest_is.cost_of_revenue:>12,.0f}")
print(f"     Gross Profit:    {latest_is.gross_profit:>12,.0f}  ({latest_is.gross_margin:.1%})")
print(f"     SG&A:            {latest_is.sga:>12,.0f}")
print(f"     R&D:             {latest_is.rd_expense:>12,.0f}")
print(f"     Other Opex:      {latest_is.other_operating_expense:>12,.0f}")
print(f"     EBIT:            {latest_is.ebit:>12,.0f}  ({latest_is.operating_margin:.1%})")
print(f"     Other Inc/Exp:   {latest_is.other_non_operating:>12,.0f}")
print(f"     EBT:             {latest_is.ebt:>12,.0f}")
print(f"     Tax:             {latest_is.tax_expense:>12,.0f}  ({latest_is.effective_tax_rate:.1%})")
print(f"     Net Income:      {latest_is.net_income:>12,.0f}")

print(f"\n   Balance Sheet ({financials.latest_year}, $M):")
print(f"     Cash:                    {latest_bs.cash_and_equivalents:>10,.0f}")
print(f"     Short-term Investments:  {latest_bs.short_term_investments:>10,.0f}")
print(f"     Accounts Receivable:     {latest_bs.accounts_receivable:>10,.0f}")
print(f"     Other Current Assets:    {latest_bs.other_current_assets:>10,.0f}")
print(f"     PP&E net:                {latest_bs.ppe_net:>10,.0f}")
print(f"     Goodwill:                {latest_bs.goodwill:>10,.0f}")
print(f"     Other Non-curr Assets:   {latest_bs.other_non_current_assets:>10,.0f}")
print(f"     Total Assets (model):    {latest_bs.total_assets:>10,.0f}")
print(f"     ----")
print(f"     Accounts Payable:        {latest_bs.accounts_payable:>10,.0f}")
print(f"     Accrued Liabilities:     {latest_bs.accrued_liabilities:>10,.0f}")
print(f"     Other Current Liab:      {latest_bs.other_current_liabilities:>10,.0f}")
print(f"     Long-term Debt:          {latest_bs.long_term_debt:>10,.0f}")
print(f"     Other Non-curr Liab:     {latest_bs.other_non_current_liabilities:>10,.0f}")
print(f"     Total Debt:              {latest_bs.total_debt:>10,.0f}")
print(f"     Total Equity:            {latest_bs.total_equity:>10,.0f}")
print(f"     Total Liab+Equity(model):{latest_bs.total_liabilities + latest_bs.total_equity:>10,.0f}")
print(f"     Net Debt (incl ST inv):  {latest_bs.net_debt:>10,.0f}")

# Balance sheet balance check
assets = latest_bs.total_assets
liab_equity = latest_bs.total_liabilities + latest_bs.total_equity
discrepancy = abs(assets - liab_equity)
discrepancy_pct = discrepancy / assets * 100 if assets else 0
flag = "  WARN: discrepancy > 1%" if discrepancy_pct > 1.0 else "  OK"
print(f"\n   BS Balance Check: |Assets - (Liab+Equity)| = {discrepancy:,.0f}M  ({discrepancy_pct:.2f}%){flag}")

# ---------------------------------------------------------------------------
# 2. Historical FCFF — CFO-based (uses actual cash flow statement)
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("2. HISTORICAL FCFF (CFO-based, $M)")
print("   Formula: FCFF = CFO + Interest*(1-t) - CapEx")
print("=" * 65)
print(f"   {'Year':>4}  {'Revenue':>9}  {'EBIT':>8}  {'Op Mgn':>7}  "
      f"{'CFO':>8}  {'Int*(1-t)':>9}  {'CapEx':>7}  {'FCFF':>8}  {'FCFF%Rev':>8}")
print("   " + "-" * 74)

for yr in years:
    is_ = financials.get_income_statement(yr)
    cf_ = financials.get_cash_flow(yr)

    h = calculate_fcff_historical(income_statement=is_, cash_flow=cf_)

    print(
        f"   {yr:>4}  {h.revenue:>9,.0f}  {h.ebit:>8,.0f}  {h.operating_margin:>6.1%}  "
        f"{h.cfo:>8,.0f}  {h.after_tax_interest:>9,.0f}  {h.capital_expenditures:>7,.0f}  "
        f"{h.fcff:>8,.0f}  {h.fcff_margin:>7.1%}"
    )

# Note on SBC
latest_cf_ = financials.get_cash_flow(financials.latest_year)
print(f"\n   [Note] CFO-based FCFF includes SBC as non-cash add-back "
      f"(${latest_cf_.stock_based_compensation:,.0f}M in {financials.latest_year}).")
print(f"   EBIT-based FCFF treats SBC as real economic cost -> lower FCFF.")
print(f"   Both are valid; CFO-based matches the reported cash generation.")

# ---------------------------------------------------------------------------
# 3. Derive projection assumptions
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("3. PROJECTION ASSUMPTIONS (derived from historical)")
print("=" * 65)
assumptions = derive_assumptions(financials)
print(f"   Revenue growth (3yr CAGR): {assumptions['revenue_growth_rates'][0]:.2%}")
print(f"   Operating margin (avg):    {assumptions['operating_margin']:.2%}")
print(f"   Tax rate (avg):            {assumptions['tax_rate']:.2%}")
print(f"   D&A % revenue (avg):       {assumptions['da_pct_revenue']:.2%}")
print(f"   CapEx % revenue (avg):     {assumptions['capex_pct_revenue']:.2%}")
print(f"   NWC % revenue (avg):       {assumptions['nwc_pct_revenue']:.2%}")
print(f"   Projection years:          {assumptions['projection_years']}")
print(f"   Terminal growth rate:      {assumptions['terminal_growth_rate']:.2%}")

print(f"\n   Historical revenue growth by year:")
for i in range(1, len(years)):
    y0 = years[i - 1]
    y1 = years[i]
    r0 = financials.get_income_statement(y0).revenue
    r1 = financials.get_income_statement(y1).revenue
    print(f"     {y0}->{y1}: {(r1/r0 - 1):+.1%}  ({r0:,.0f} -> {r1:,.0f})")

# ---------------------------------------------------------------------------
# 4. Price data + CAPM
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("4. PRICE DATA & CAPM BETA")
print("=" * 65)
price_data = fetch_price_data(TICKER, lookback_years=5, frequency="monthly")
print(f"   Current price:        ${price_data.current_price:.2f}")
print(f"   Monthly return pairs: {len(price_data.stock_returns)}")

capm_result = run_capm(price_data)
print(f"   Beta (OLS 5yr):       {capm_result.beta:.3f}")
print(f"   R²:                   {capm_result.r_squared:.3f}")
print(f"   Risk-free rate:       {capm_result.risk_free_rate:.2%}")
print(f"   Equity risk premium:  {capm_result.equity_risk_premium:.2%}")
print(f"   Cost of Equity (Ke):  {capm_result.cost_of_equity:.2%}")

# ---------------------------------------------------------------------------
# 5. WACC
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("5. WACC")
print("=" * 65)

import yfinance as yf
info = yf.Ticker(TICKER).info
shares = info.get("sharesOutstanding", 0) / 1e6  # -> millions
market_cap = price_data.current_price * shares
print(f"   Shares outstanding:   {shares:,.0f}M  (from yfinance)")
print(f"   Market cap:           ${market_cap:,.0f}M")

wacc_result = calculate_wacc(
    capm_result=capm_result,
    income_statement=latest_is,
    balance_sheet=latest_bs,
    market_cap=market_cap,
)
rd_note = "(fallback — interest not reported separately in CIQ)" if latest_is.interest_expense == 0 and latest_bs.total_debt > 0 else ""
print(f"   Cost of Equity (Re):  {wacc_result.cost_of_equity:.2%}")
print(f"   Cost of Debt (Rd):    {wacc_result.cost_of_debt:.2%}  {rd_note}")
print(f"   Tax Rate:             {wacc_result.tax_rate:.2%}")
print(f"   Equity Weight (E/V):  {wacc_result.equity_weight:.1%}")
print(f"   Debt Weight (D/V):    {wacc_result.debt_weight:.1%}")
print(f"   WACC:                 {wacc_result.wacc:.2%}")

# ---------------------------------------------------------------------------
# 6. Projected FCFFs
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("6. PROJECTED FCFFs ($M)")
print("=" * 65)
projected = project_fcffs(financials, assumptions)
print(f"   {'Year':>4}  {'Revenue':>9}  {'EBIT':>8}  {'Op Mgn':>7}  {'NOPAT':>8}  {'D&A':>7}  {'CapEx':>7}  {'dNWC':>7}  {'FCFF':>8}")
print("   " + "-" * 68)
for p in projected:
    print(
        f"   {p.year:>4}  {p.revenue:>9,.0f}  {p.ebit:>8,.0f}  "
        f"{p.ebit/p.revenue:>6.1%}  {p.nopat:>8,.0f}  "
        f"{p.depreciation_amortization:>7,.0f}  {p.capital_expenditures:>7,.0f}  "
        f"{p.change_in_working_capital:>7,.0f}  {p.fcff:>8,.0f}"
    )

# ---------------------------------------------------------------------------
# 7. DCF Valuation
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("7. DCF VALUATION")
print("=" * 65)
dcf_result = run_dcf(
    projected_fcffs=projected,
    wacc_result=wacc_result,
    financials=financials,
    terminal_growth_rate=assumptions["terminal_growth_rate"],
    current_price=price_data.current_price,
    diluted_shares=shares,
)

wacc_pct = dcf_result.wacc
tgr_pct = dcf_result.terminal_growth_rate

print(f"   WACC:                          {wacc_pct:.2%}")
print(f"   Terminal growth rate:          {tgr_pct:.2%}")
print(f"   Spread (WACC - g):             {wacc_pct - tgr_pct:.2%}")
print()
print(f"   PV of projected FCFFs:         ${dcf_result.pv_fcffs:>12,.0f}M")
print(f"   Terminal Value (undiscounted): ${dcf_result.terminal_value:>12,.0f}M")
print(f"   PV of Terminal Value:          ${dcf_result.pv_terminal_value:>12,.0f}M")
print(f"   {'-' * 46}")
print(f"   Enterprise Value:              ${dcf_result.enterprise_value:>12,.0f}M")
print()
print(f"   Equity Bridge ($M):")
print(f"     + Enterprise Value:          ${dcf_result.enterprise_value:>12,.0f}M")
print(f"     - Net Debt (debt-cash-ST inv): ${dcf_result.net_debt:>11,.0f}M")
print(f"   = Equity Value:                ${dcf_result.equity_value:>12,.0f}M")
print()
print(f"   Diluted Shares:                {dcf_result.diluted_shares:>12,.0f}M")
print(f"   Implied Share Price:           ${dcf_result.implied_share_price:>11.2f}")
print(f"   Current Price:                 ${dcf_result.current_price:>11.2f}")
direction = "UPSIDE" if dcf_result.upside_downside > 0 else "DOWNSIDE"
print(f"   {direction}:                      {dcf_result.upside_downside:>+11.1f}%")

tv_pct = dcf_result.pv_terminal_value / dcf_result.enterprise_value * 100
print(f"\n   [Note] TV = {tv_pct:.0f}% of EV  "
      f"({'healthy range' if tv_pct < 75 else 'high — consider shorter projection period or higher WACC'})")
