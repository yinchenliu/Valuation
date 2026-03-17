"""DCF (Discounted Cash Flow) valuation engine.

Enterprise Value = Sum of PV(FCFFs) + PV(Terminal Value)
Terminal Value = FCFF_n * (1 + g) / (WACC - g)   [Gordon Growth Model]
Equity Value = Enterprise Value - Net Debt
Implied Share Price = Equity Value / Diluted Shares Outstanding
"""

from __future__ import annotations

from models.financial_statements import FinancialStatements
from models.valuation import DCFResult, ProjectedFCFF, WACCResult


def calculate_terminal_value(
    final_fcff: float,
    terminal_growth_rate: float,
    wacc: float,
) -> float:
    """Gordon Growth Model terminal value.

    TV = FCFF_n * (1 + g) / (WACC - g)
    """
    if wacc <= terminal_growth_rate:
        raise ValueError(
            f"WACC ({wacc:.4f}) must exceed terminal growth rate ({terminal_growth_rate:.4f})"
        )
    return final_fcff * (1 + terminal_growth_rate) / (wacc - terminal_growth_rate)


def discount_cash_flows(
    projected_fcffs: list[ProjectedFCFF],
    wacc: float,
) -> float:
    """Calculate present value of projected FCFFs.

    PV = Sum of FCFF_t / (1 + WACC)^t
    """
    pv = 0.0
    for i, fcff in enumerate(projected_fcffs, start=1):
        pv += fcff.fcff / (1 + wacc) ** i
    return pv


def run_dcf(
    projected_fcffs: list[ProjectedFCFF],
    wacc_result: WACCResult,
    financials: FinancialStatements,
    terminal_growth_rate: float,
    current_price: float,
    diluted_shares: float,
) -> DCFResult:
    """Run full DCF valuation.

    Args:
        projected_fcffs: List of projected FCFFs.
        wacc_result: WACC calculation result.
        financials: Historical financials (for net debt).
        terminal_growth_rate: Long-term growth rate (e.g., 0.025).
        current_price: Current stock price for comparison.
        diluted_shares: Diluted shares outstanding.

    Returns:
        DCFResult with enterprise value, equity value, implied share price.
    """
    wacc = wacc_result.wacc
    n = len(projected_fcffs)

    # PV of projected FCFFs
    pv_fcffs = discount_cash_flows(projected_fcffs, wacc)

    # Terminal value (based on last projected FCFF)
    final_fcff = projected_fcffs[-1].fcff
    tv = calculate_terminal_value(final_fcff, terminal_growth_rate, wacc)
    pv_tv = tv / (1 + wacc) ** n

    # Net debt from latest balance sheet
    latest_year = financials.latest_year
    latest_bs = financials.get_balance_sheet(latest_year)
    net_debt = latest_bs.net_debt if latest_bs else 0.0
    cash = latest_bs.cash_and_equivalents if latest_bs else 0.0

    return DCFResult(
        ticker=financials.ticker,
        projection_years=n,
        terminal_growth_rate=terminal_growth_rate,
        wacc=wacc,
        projected_fcffs=projected_fcffs,
        pv_fcffs=pv_fcffs,
        terminal_value=tv,
        pv_terminal_value=pv_tv,
        net_debt=net_debt,
        cash=cash,
        diluted_shares=diluted_shares,
        current_price=current_price,
    )
