"""Test parsing the Alphabet Capital IQ export end-to-end."""
import sys
sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")

from ingestion.capital_iq_parser import parse_capital_iq

fp = r"C:\Users\yinchenliu\Downloads\AlphabetInc.NASDAQGSGOOGL_Report_03-02-2026.xlsx"
financials = parse_capital_iq(fp, "GOOGL", "Alphabet Inc.")

print(f"Company: {financials.company_name} ({financials.ticker})")
print(f"Years: {financials.years}")
print(f"Latest year: {financials.latest_year}")

print("\n=== Income Statements ===")
for yr in financials.years:
    s = financials.get_income_statement(yr)
    print(f"  {yr}: Revenue={s.revenue:,.0f}  COGS={s.cost_of_revenue:,.0f}  "
          f"SGA={s.sga:,.0f}  R&D={s.rd_expense:,.0f}  "
          f"EBIT={s.ebit:,.0f}  Tax={s.tax_expense:,.0f}  "
          f"NetInc={s.net_income:,.0f}  Shares={s.diluted_shares_outstanding:,.0f}")

print("\n=== Balance Sheets ===")
for yr in financials.years:
    s = financials.get_balance_sheet(yr)
    print(f"  {yr}: Cash={s.cash_and_equivalents:,.0f}  STInv={s.short_term_investments:,.0f}  "
          f"AR={s.accounts_receivable:,.0f}  PPE={s.ppe_net:,.0f}  "
          f"LTDebt={s.long_term_debt:,.0f}  Equity={s.total_equity:,.0f}  "
          f"NWC={s.net_working_capital:,.0f}  NetDebt={s.net_debt:,.0f}")

print("\n=== Cash Flow Statements ===")
for yr in financials.years:
    s = financials.get_cash_flow(yr)
    print(f"  {yr}: NetInc={s.net_income:,.0f}  D&A={s.depreciation_amortization:,.0f}  "
          f"SBC={s.stock_based_compensation:,.0f}  CapEx={s.capital_expenditures:,.0f}  "
          f"CFO={s.cash_from_operations:,.0f}")
