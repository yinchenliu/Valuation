"""Free Cash Flow to Firm (FCFF) calculation — two approaches.

HISTORICAL (CFO-based) — uses actual reported cash flow statement:
  FCFF = CFO + Interest_Expense * (1 - t) - CapEx

  CFO is taken directly from the filing. GAAP classifies interest paid as
  operating, so CFO is after-interest. We add back after-tax interest to
  convert to a pre-financing, firm-level measure.

PROJECTED (EBIT-based) — built from income statement assumptions:
  FCFF = EBIT * (1 - t) + D&A - CapEx - delta_NWC
       = NOPAT + D&A - CapEx - delta_NWC

  Used for forward projections where we have no actual cash flow statement.
"""

from __future__ import annotations

import math

from models.financial_statements import (
    CashFlowStatement,
    IncomeStatement,
)
from models.valuation import HistoricalFCFF, ProjectedFCFF


def _require_finite(value: float, field: str) -> None:
    """Stop when an FCFF input is NaN, naming the field it arrived in.

    Rule 3: a missing input stops the run and names the field. NaN is the shape
    a missing input takes once it has been through a float calculation, and
    **no comparison can detect it** — `nan <= x`, `nan > x` and `nan == nan`
    are all False. `math.isnan` is the only reliable test. This is the same
    helper, and the same reasoning, as `analysis/wacc.py:_require_finite`; it
    is repeated here rather than imported because the message it raises names
    FCFF, not WACC.
    """
    if math.isnan(value):
        raise ValueError(
            f"{field} is NaN, so FCFF cannot be computed from it. A NaN here "
            "means an input was absent or degenerate further up the chain. "
            "Supply the missing input; it is not substituted with a default."
        )


def calculate_fcff_historical(
    income_statement: IncomeStatement,
    cash_flow: CashFlowStatement,
    tax_rate_override: float | None = None,
) -> HistoricalFCFF:
    """Calculate historical FCFF using the CFO-based method.

    FCFF = CFO + Interest_Expense * (1 - t) - CapEx

    Args:
        income_statement: Period's income statement (for tax rate, interest, EBIT).
        cash_flow: Period's cash flow statement (for CFO and CapEx).
        tax_rate_override: Override effective tax rate (e.g., use statutory rate).

    Returns:
        HistoricalFCFF with full breakdown for audit.
    """
    tax_rate = tax_rate_override if tax_rate_override is not None else income_statement.effective_tax_rate
    # Checked BEFORE the clamp below. `max(0.0, min(nan, 0.50))` is 0.0, not
    # nan: every comparison against nan is False, so both builtins fall
    # through to their first argument and a NaN tax rate would be silently
    # read as a 0% rate. Here that means a full, untaxed interest add-back,
    # which *raises* FCFF and so raises the valuation. After the clamp the
    # evidence is gone, because the NaN has already become a plausible 0.0.
    _require_finite(
        tax_rate, "tax_rate (tax_rate_override or income_statement.effective_tax_rate)"
    )
    tax_rate = max(0.0, min(tax_rate, 0.50))

    cfo = cash_flow.cash_from_operations
    interest_expense = abs(income_statement.interest_expense)
    after_tax_interest = interest_expense * (1 - tax_rate)
    capex = abs(cash_flow.capital_expenditures)

    fcff = cfo + after_tax_interest - capex

    return HistoricalFCFF(
        year=income_statement.year,
        revenue=income_statement.revenue,
        ebit=income_statement.ebit,
        cfo=cfo,
        interest_expense=interest_expense,
        after_tax_interest=after_tax_interest,
        capital_expenditures=capex,
        tax_rate=tax_rate,
        fcff=fcff,
    )


def calculate_fcff_projected(
    year: int,
    revenue: float,
    operating_margin: float,
    tax_rate: float,
    da_pct_revenue: float,
    capex_pct_revenue: float,
    nwc_pct_revenue: float,
) -> ProjectedFCFF:
    """Calculate FCFF from projected assumptions.

    Args:
        year: Projection year.
        revenue: Projected revenue.
        operating_margin: EBIT / Revenue.
        tax_rate: Effective tax rate.
        da_pct_revenue: D&A as % of revenue.
        capex_pct_revenue: CapEx as % of revenue.
        nwc_pct_revenue: Change in NWC as % of revenue (from historical CFS).
    """
    ebit = revenue * operating_margin
    nopat = ebit * (1 - tax_rate)
    da = revenue * da_pct_revenue
    capex = revenue * capex_pct_revenue
    delta_nwc = revenue * nwc_pct_revenue

    return ProjectedFCFF(
        year=year,
        revenue=revenue,
        ebit=ebit,
        nopat=nopat,
        depreciation_amortization=da,
        capital_expenditures=capex,
        change_in_working_capital=delta_nwc,
    )
