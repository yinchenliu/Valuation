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

import config
from models.financial_statements import BalanceSheet, IncomeStatement
from models.valuation import CAPMResult, WACCResult


def calculate_cost_of_debt(
    income_statement: IncomeStatement,
    balance_sheet: BalanceSheet,
    override: float | None = None,
) -> float:
    """Estimate pre-tax cost of debt from financials.

    Rd = Interest Expense / Total Debt

    Many Capital IQ "As Reported" exports fold interest expense into
    "Other Income/Expense, Net" rather than reporting it as a standalone line.
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
    cost_of_debt = calculate_cost_of_debt(income_statement, balance_sheet, cost_of_debt_override)

    tax_rate = tax_rate_override if tax_rate_override is not None else income_statement.effective_tax_rate
    # Clamp tax rate to reasonable range
    tax_rate = max(0.0, min(tax_rate, 0.50))

    equity_value = market_cap
    debt_value = balance_sheet.total_debt
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
