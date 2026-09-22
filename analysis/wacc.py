"""Weighted Average Cost of Capital (WACC).

WACC = (E/V) * Re + (D/V) * Rd * (1 - T)

Where:
    E = Market value of equity (market cap)
    D = Market value of debt (approximated by book value)
    V = E + D
    Re = Cost of equity (from CAPM)
    Rd = Cost of debt (interest expense / total debt)
    T = Effective tax rate
"""

from __future__ import annotations

import math

import config
from models.financial_statements import BalanceSheet, IncomeStatement
from models.valuation import CAPMResult, WACCResult


def _require_finite(value: float, field: str) -> None:
    """Stop when a WACC input is NaN, naming the field it arrived in.

    Rule 3: a missing input stops the run and names the field. NaN is the shape
    a missing input takes once it has been through a float calculation, and
    **no comparison can detect it** — `nan <= x`, `nan > x` and `nan == nan`
    are all False, so a guard written as a comparison passes a NaN straight
    through. That is precisely how a NaN beta used to reach a rendered share
    price past `analysis/dcf.py`'s `wacc <= terminal_growth_rate` guard.
    `math.isnan` is the only reliable test.

    WACC is where every input to the discount rate converges — the CAPM cost of
    equity, a cost of debt that may have been overridden, a tax rate from the
    filing, a market capitalisation from market data, and a debt balance from
    the balance sheet. A guard here therefore catches a NaN arriving from any
    of them, not only from the regression.
    """
    if math.isnan(value):
        raise ValueError(
            f"{field} is NaN, so WACC cannot be computed from it. A NaN here "
            "means an input was absent or degenerate further up the chain. "
            "Supply the missing input; it is not substituted with a default."
        )


def calculate_cost_of_debt(
    income_statement: IncomeStatement,
    balance_sheet: BalanceSheet,
    override: float | None = None,
) -> float:
    """Estimate pre-tax cost of debt from financials.

    Rd = Interest Expense / Total Debt

    When interest_expense = 0 but the company carries debt, we fall back to
    config.DEFAULT_COST_OF_DEBT rather than returning 0%.
    """
    if override is not None:
        return override

    total_debt = balance_sheet.total_debt
    if total_debt == 0:
        return 0.0

    interest = abs(income_statement.interest_expense)
    if interest == 0:
        # Interest not separately reported; use default market rate
        return config.DEFAULT_COST_OF_DEBT

    return interest / total_debt


def calculate_wacc(
    capm_result: CAPMResult,
    income_statement: IncomeStatement,
    balance_sheet: BalanceSheet,
    market_cap: float,
    cost_of_debt_override: float | None = None,
    tax_rate_override: float | None = None,
) -> WACCResult:
    """Calculate WACC.

    Args:
        capm_result: CAPM output with cost of equity.
        income_statement: Latest income statement (for interest expense, tax rate).
        balance_sheet: Latest balance sheet (for debt figures).
        market_cap: Current market capitalization (shares * price).
        cost_of_debt_override: If provided, use instead of deriving from financials.
        tax_rate_override: If provided, use instead of effective tax rate from I/S.
    """
    cost_of_equity = capm_result.cost_of_equity
    _require_finite(cost_of_equity, "capm_result.cost_of_equity")

    cost_of_debt = calculate_cost_of_debt(income_statement, balance_sheet, cost_of_debt_override)
    _require_finite(cost_of_debt, "cost_of_debt")

    tax_rate = tax_rate_override if tax_rate_override is not None else income_statement.effective_tax_rate
    # Checked BEFORE the clamp below. `max(0.0, min(nan, 0.50))` is 0.0, not
    # nan: every comparison against nan is False, so both builtins fall
    # through to their first argument and a NaN tax rate would be silently
    # read as a 0% rate — a full tax shield on the debt term.
    _require_finite(tax_rate, "tax_rate (tax_rate_override or income_statement.effective_tax_rate)")
    # Clamp tax rate to reasonable range
    tax_rate = max(0.0, min(tax_rate, 0.50))

    equity_value = market_cap
    _require_finite(equity_value, "market_cap")
    debt_value = balance_sheet.total_debt
    _require_finite(debt_value, "balance_sheet.total_debt")
    total_value = equity_value + debt_value

    if total_value == 0:
        return WACCResult(
            cost_of_equity=cost_of_equity,
            cost_of_debt=cost_of_debt,
            tax_rate=tax_rate,
            equity_weight=1.0,
            debt_weight=0.0,
        )

    return WACCResult(
        cost_of_equity=cost_of_equity,
        cost_of_debt=cost_of_debt,
        tax_rate=tax_rate,
        equity_weight=equity_value / total_value,
        debt_weight=debt_value / total_value,
    )
