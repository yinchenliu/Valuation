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


def cost_of_debt_with_source(
    income_statement: IncomeStatement,
    balance_sheet: BalanceSheet,
    override: float | None = None,
) -> tuple[float, str]:
    """Pre-tax cost of debt, together with a sentence saying where it came from.

    Rd = Interest Expense / Total Debt

    Rule 6, backlog item 9. Four branches can return a number here and only one
    of them is a measurement from the filing. Until now all four returned a
    bare float, so a 4.00% substituted from `config.DEFAULT_COST_OF_DEBT` was
    printed in the same cell, in the same format, as a 5.72% divided out of the
    filing's own interest expense. This function is the single place that knows
    which branch fired, so it is the place that says so.

    Rule 3, backlog item 22. A fifth path returns nothing at all: a zero debt
    balance standing beside a reported interest expense is a missing balance
    sheet, not a debt-free company, and it raises rather than valuing the firm
    as unlevered. See the comment on that branch.

    `calculate_cost_of_debt` below is the unchanged float-returning form, kept
    so that every existing caller and assertion keeps working. It delegates
    here rather than repeating the branches, so the label cannot drift from the
    number it describes.

    Returns:
        (rate, source) — the rate as a decimal, and a human sentence naming the
        branch, the inputs it used, and whether it is a measurement.

    Raises:
        ValueError: when the balance sheet reports no debt while the income
            statement reports interest expense, naming both figures and the
            fields they came from.
    """
    if override is not None:
        return override, (
            "supplied by the caller (--cost-of-debt / "
            "ProjectionAssumptions.cost_of_debt_override). Not derived from "
            "the filing."
        )

    total_debt = balance_sheet.total_debt
    interest = abs(income_statement.interest_expense)

    if total_debt == 0:
        # Backlog item 22, closed here. A zero debt balance used to return 0.0
        # unconditionally, and that single zero carried two incompatible
        # meanings: "this company carries no debt" and "the balance sheet did
        # not extract". They are the same bytes and nothing downstream could
        # tell them apart.
        #
        # The income statement tells them apart. A company that paid interest
        # had debt to pay it on, so a reported interest expense beside a zero
        # debt balance is not a debt-free company — it is a balance sheet that
        # did not come through. That is a missing input, and rule 3 says the
        # run stops and names the field rather than valuing the company as
        # though it were unlevered.
        #
        # The consequence of NOT stopping is not confined to this rate. With
        # total_debt == 0 the debt weight in `calculate_wacc` is also 0, so the
        # whole debt term drops out of WACC: the firm is discounted at its cost
        # of equity, the discount rate is overstated, and the share price is
        # understated, on a clean run, with nothing in the output saying so.
        if interest != 0:
            raise ValueError(
                f"the balance sheet reports total debt of 0 while the income "
                f"statement reports interest expense of "
                f"{income_statement.interest_expense:,.2f} for "
                f"{income_statement.year}. A company that pays interest has "
                f"debt, so the debt balance "
                f"(BalanceSheet.short_term_debt + "
                f"BalanceSheet.current_portion_lt_debt + "
                f"BalanceSheet.long_term_debt, year "
                f"{balance_sheet.year}) did not extract. The cost of debt is "
                f"not substituted and the WACC is not computed from a zero "
                f"debt weight: supply the debt balance, or supply a cost of "
                f"debt explicitly with --cost-of-debt if the zero is correct."
            )
        # Zero debt AND zero interest: a genuinely debt-free company. 0.0 is a
        # real measurement here, and it is labelled as one.
        return 0.0, (
            "no debt reported: total debt on the balance sheet is 0 and the "
            f"income statement reports no interest expense for "
            f"{income_statement.year}, so this company is debt-free and there "
            "is no rate to measure. The debt term drops out of the WACC, which "
            "is therefore the cost of equity."
        )

    if interest == 0:
        return config.DEFAULT_COST_OF_DEBT, (
            f"ASSUMPTION — config.DEFAULT_COST_OF_DEBT "
            f"({config.DEFAULT_COST_OF_DEBT:.2%}) was SUBSTITUTED, because "
            f"interest expense is not reported separately (0) while the "
            f"balance sheet carries {total_debt:,.0f} of debt, so "
            f"interest / total debt cannot be computed. This is a guess at a "
            f"coupon, it is not this company's, and it reaches the WACC and "
            f"the implied share price."
        )

    return interest / total_debt, (
        f"measured from the filing: interest expense {interest:,.0f} / total "
        f"debt {total_debt:,.0f}"
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

    The rate only. `cost_of_debt_with_source` returns the same number together
    with the label rule 6 requires; this wrapper exists so that callers which
    need no label keep their signature and their meaning unchanged.
    """
    rate, _source = cost_of_debt_with_source(income_statement, balance_sheet, override)
    return rate


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

    cost_of_debt, cost_of_debt_source = cost_of_debt_with_source(
        income_statement, balance_sheet, cost_of_debt_override
    )
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
            cost_of_debt_source=cost_of_debt_source,
        )

    return WACCResult(
        cost_of_equity=cost_of_equity,
        cost_of_debt=cost_of_debt,
        tax_rate=tax_rate,
        equity_weight=equity_value / total_value,
        debt_weight=debt_value / total_value,
        cost_of_debt_source=cost_of_debt_source,
    )
