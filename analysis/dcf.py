"""DCF (Discounted Cash Flow) valuation engine.

Enterprise Value = Sum of PV(FCFFs) + PV(Terminal Value)
Terminal Value = FCFF_n * (1 + g) / (WACC - g)   [Gordon Growth Model]
Equity Value = Enterprise Value - Net Debt - Noncontrolling Interest
Implied Share Price = Equity Value / Diluted Shares Outstanding
"""

from __future__ import annotations

import math

from models.financial_statements import BalanceSheet, FinancialStatements
from models.valuation import DCFResult, ProjectedFCFF, WACCResult


def _require_finite(value: float, field: str) -> None:
    """Stop when a cash flow entering the DCF is NaN, naming where it came from.

    Rule 3: a missing input stops the run and names the field. NaN is the shape
    a missing input takes once it has been through a float calculation, and
    **no comparison can detect it** — `nan <= x`, `nan > x` and `nan == nan`
    are all False, so a guard written as a comparison passes a NaN straight
    through. `math.isnan` is the only reliable test. This is the same helper,
    and the same reasoning, as `analysis/wacc.py:_require_finite`; the message
    differs because the field it names is a cash flow, not a discount rate.

    `ProjectedFCFF.fcff` is a *property* over four stored fields, so a NaN in
    any one of nopat, D&A, CapEx or the change in working capital arrives here
    as a NaN cash flow. Summing it makes the whole present value NaN, and from
    there every figure downstream — enterprise value, equity value and the
    implied share price — is NaN, on a run that raises nothing at all.
    """
    if math.isnan(value):
        raise ValueError(
            f"{field} is NaN, so it cannot be discounted. A NaN here means an "
            "input was absent or degenerate further up the chain, in the "
            "projection or in the figures it was built from. Supply the "
            "missing input; it is not substituted with a default."
        )


def total_noncontrolling_interest(balance_sheet: BalanceSheet) -> float:
    """Total noncontrolling interest = nonredeemable + redeemable, both as printed.

    Pass 1's net income and cash flows are **consolidated**: they include the
    share of the group that belongs to minority holders, so the enterprise
    value built from them values the whole group. The parent's equity value is
    what is left after net debt **and** the noncontrolling interests' book value
    (backlog item 48).

    The filing prints the two parts on separate lines — the nonredeemable
    amount inside equity, the redeemable amount outside it — and their sum on
    none (Walmart FY2026, PDF page 22: 6,270 and 293). So the model reads each
    line and this function, not the model, adds them (rule 1). It is the only
    place the sum is taken.

    Each part stops when it is None ("not extracted") or NaN, naming its key
    and the year, and neither falls back to zero (rule 3): a zero here and "not
    extracted" are the same bytes, and the second overstates the share price by
    the whole minority stake. A filing that prints no such line is extracted
    as an explicit 0, which passes.
    """
    parts = (
        ("noncontrolling_interest_nonredeemable",
         balance_sheet.noncontrolling_interest_nonredeemable),
        ("noncontrolling_interest_redeemable",
         balance_sheet.noncontrolling_interest_redeemable),
    )
    total = 0.0
    for key, value in parts:
        if value is None:
            raise ValueError(
                f"{key} was not extracted for the FY{balance_sheet.year} balance "
                "sheet, so the equity bridge cannot subtract the noncontrolling "
                "interests. Re-extract with the current Pass 1 schema, or write "
                "the figure printed on the balance sheet (0 if the filing prints "
                "no such line). It is not substituted with zero."
            )
        if math.isnan(value):
            # A comparison cannot detect NaN (see `_require_finite`); subtracted
            # unchecked it would make equity value and the share price NaN.
            raise ValueError(
                f"{key} on the FY{balance_sheet.year} balance sheet is NaN, so "
                "the equity bridge cannot subtract it. Supply the figure printed "
                "on the balance sheet; it is not substituted with a default."
            )
        total += value
    return total


def calculate_terminal_value(
    final_fcff: float,
    terminal_growth_rate: float,
    wacc: float,
) -> float:
    """Gordon Growth Model terminal value.

    TV = FCFF_n * (1 + g) / (WACC - g)

    The NaN check below is not redundant with the spread check that follows
    it. **A comparison cannot detect NaN**: `nan <= 0.025` is False and so is
    `nan > 0.025`, so the spread check falls through and the whole valuation
    completes with `implied_share_price = nan`. This is the last line of
    defence before a price is rendered, and it has to be `math.isnan`.

    `final_fcff` is checked for the same reason and is checked here rather
    than only in `run_dcf`, because this function is called directly as well:
    `calculate_terminal_value(nan, 0.025, 0.086)` returned `nan` before this
    guard existed. A NaN here is no smaller a failure than a NaN in a
    discounted year: the terminal value is the whole of the enterprise value
    beyond the projection window, and it flows into `pv_terminal_value` and on
    to the share price by exactly the same route.
    """
    _require_finite(final_fcff, "final_fcff (the terminal value's base cash flow)")
    if math.isnan(wacc) or math.isnan(terminal_growth_rate):
        raise ValueError(
            f"WACC ({wacc}) and terminal growth rate ({terminal_growth_rate}) "
            "must both be numbers; a NaN here would pass the spread check "
            "below silently and render as a NaN share price. A NaN WACC means "
            "an input was absent or degenerate in CAPM or in WACC"
        )
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

    Each year's cash flow is checked before it is added, and the guard names
    the **year**, so a reader can find the offending projection rather than
    only learning that one of them was bad. Without it a single NaN year makes
    `pv` NaN and carries through to the share price with no exception raised.
    """
    pv = 0.0
    for i, fcff in enumerate(projected_fcffs, start=1):
        cash_flow = fcff.fcff
        _require_finite(cash_flow, f"the projected FCFF for year {fcff.year}")
        pv += cash_flow / (1 + wacc) ** i
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
        financials: Historical financials (for net debt and the
            noncontrolling interest, both from the latest balance sheet).
        terminal_growth_rate: Long-term growth rate (e.g., 0.025).
        current_price: Current stock price for comparison.
        diluted_shares: Diluted shares outstanding.

    Returns:
        DCFResult with enterprise value, equity value, implied share price.
    """
    if not projected_fcffs:
        raise ValueError(
            "projected_fcffs is empty: a DCF needs at least one projected year, "
            "because the terminal value is built from the final projected FCFF"
        )

    # The share count is the denominator of the headline figure. Zero, a
    # negative count or NaN is no share count, and the result would show a
    # price of 0.0 (a company worth nothing) or NaN. Stop before discounting
    # anything. Rule 3; backlog item 32. `math.isfinite` is tested first
    # because a guard written as a comparison, such as `<= 0`, lets NaN
    # through (see `_require_finite`).
    if not (math.isfinite(diluted_shares) and diluted_shares > 0):
        raise ValueError(
            f"diluted_shares is {diluted_shares!r}: the DCF needs a finite "
            "diluted share count greater than zero, in the units of the "
            "filing, to divide equity value into a share price. It is not "
            "substituted; supply the count printed in the filing."
        )

    wacc = wacc_result.wacc
    n = len(projected_fcffs)

    # PV of projected FCFFs
    pv_fcffs = discount_cash_flows(projected_fcffs, wacc)

    # Terminal value (based on last projected FCFF)
    final_fcff = projected_fcffs[-1].fcff
    tv = calculate_terminal_value(final_fcff, terminal_growth_rate, wacc)
    pv_tv = tv / (1 + wacc) ** n

    # The bridge from enterprise value to equity value, from the latest balance
    # sheet: net debt and the noncontrolling interests. With no balance sheet
    # neither can be read, so the run stops (rule 3; backlog item 2 — this
    # replaced `net_debt = 0.0` and `cash = 0.0` on that branch).
    latest_year = financials.latest_year
    latest_bs = financials.get_balance_sheet(latest_year)
    if latest_bs is None:
        raise ValueError(
            f"The latest year (FY{latest_year}) has no balance sheet, so net debt, "
            "cash and the noncontrolling interests cannot be read and the equity "
            "bridge cannot be built. Extract the balance sheet for that year; "
            "none of them is substituted with zero."
        )
    noncontrolling_interest = total_noncontrolling_interest(latest_bs)
    net_debt = latest_bs.net_debt
    cash = latest_bs.cash_and_equivalents

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
        noncontrolling_interest=noncontrolling_interest,
        noncontrolling_interest_source=(
            f"FY{latest_year} balance sheet, read from the filing: nonredeemable "
            f"{latest_bs.noncontrolling_interest_nonredeemable:,.0f} + redeemable "
            f"{latest_bs.noncontrolling_interest_redeemable:,.0f}, summed by "
            "analysis/dcf.py:total_noncontrolling_interest"
        ),
    )
