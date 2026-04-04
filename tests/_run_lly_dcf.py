"""Quick DCF run from cached LLY extraction."""
import sys, pickle
sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")
from pathlib import Path
from ingestion.price_fetcher import fetch_price_data
from analysis.capm import run_capm
from analysis.wacc import calculate_wacc
from analysis.projector import derive_assumptions, project_fcffs
from analysis.normalizer import normalize_financials
from analysis.dcf import run_dcf

cache = Path(r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform\tests\.cache_lly_extraction.pkl")
with open(cache, "rb") as f:
    financials, adjustments = pickle.load(f)

adjusted = normalize_financials(financials, adjustments)
assumptions = derive_assumptions(adjusted)
latest_is = adjusted.get_income_statement(adjusted.latest_year)
latest_bs = adjusted.get_balance_sheet(adjusted.latest_year)

price_data = fetch_price_data("LLY", lookback_years=5, frequency="monthly")
capm_result = run_capm(price_data)

import yfinance as yf
info = yf.Ticker("LLY").info
shares = info.get("sharesOutstanding", 0) / 1e6
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
rev_str = [f"{r:.1%}" for r in assumptions["revenue_growth_rates"]]
print(f"\n  Revenue growth assumptions: {rev_str}")
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
