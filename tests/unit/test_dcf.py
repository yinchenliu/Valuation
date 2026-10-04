"""Unit tests for `analysis/dcf.py`.

Every expected value in this file was derived **before the code ran**, from
either the hand arithmetic written out in the comment above the assertion, or a
closed-form identity that must hold whatever the inputs are. No expected value
here was obtained by running the code and recording what it printed.
See `docs/5-testing/strategy.md` section 1.

Nothing here needs an API key, a PDF, or the network: every input is a
dataclass built in this file, with only the fields the function under test
reads. See `docs/5-testing/strategy.md` section 3.
"""

from __future__ import annotations

import math

import pytest

from analysis.dcf import calculate_terminal_value, discount_cash_flows, run_dcf
from models.financial_statements import (
    BalanceSheet,
    FinancialStatements,
    IncomeStatement,
)
from models.valuation import DCFResult, ProjectedFCFF, WACCResult

# ---------------------------------------------------------------------------
# Fixture builders
#
# These exist so the arithmetic in each test is about `analysis/dcf.py` and not
# about how a `ProjectedFCFF` or a `WACCResult` computes its own property. The
# two tests directly below pin those two properties, so the builders are not
# taken on trust.
# ---------------------------------------------------------------------------


def make_projected_fcff(year: int, fcff: float) -> ProjectedFCFF:
    """A `ProjectedFCFF` whose `.fcff` is exactly `fcff`.

    ProjectedFCFF.fcff = NOPAT + D&A - |CapEx| - dNWC
                       = fcff +  0  -    0     -   0   = fcff
    """
    return ProjectedFCFF(
        year=year,
        revenue=0.0,
        ebit=0.0,
        nopat=fcff,
        depreciation_amortization=0.0,
        capital_expenditures=0.0,
        change_in_working_capital=0.0,
    )


def make_wacc_result(wacc: float) -> WACCResult:
    """A `WACCResult` whose `.wacc` is exactly `wacc`.

    Closed-form identity: WACC = E/V * Ke + D/V * Kd * (1 - t). With
    D/V = 0 and E/V = 1 the debt term vanishes and WACC == Ke == `wacc`.
    """
    return WACCResult(
        cost_of_equity=wacc,
        cost_of_debt=0.0,
        tax_rate=0.0,
        equity_weight=1.0,
        debt_weight=0.0,
    )


# ---------------------------------------------------------------------------
# The two model properties the builders above rely on
# ---------------------------------------------------------------------------


def test_wacc_with_zero_debt_weight_equals_cost_of_equity() -> None:
    """Closed-form identity: the debt term vanishes when D/V is zero.

    WACC = 1.0 * 0.25 + 0.0 * 0.90 * (1 - 0.40) = 0.25 + 0.0 = 0.25,
    whatever the cost of debt and the tax rate are.
    """
    result = WACCResult(
        cost_of_equity=0.25,
        cost_of_debt=0.90,
        tax_rate=0.40,
        equity_weight=1.0,
        debt_weight=0.0,
    )
    assert result.wacc == pytest.approx(0.25)


def test_projected_fcff_is_nopat_plus_da_less_capex_less_delta_nwc() -> None:
    """FCFF = NOPAT + D&A - |CapEx| - dNWC = 80 + 30 - 25 - 5 = 80.0

    CapEx is passed as -25 here (the cash-flow-statement sign convention) and
    the formula takes its absolute value, so the answer is the same 80.0 for
    +25. The second assertion pins that, because a CapEx sign flip is the
    easiest error in this file to make and the hardest to see.
    """
    negative_capex = ProjectedFCFF(
        year=2026,
        revenue=1000.0,
        ebit=100.0,
        nopat=80.0,
        depreciation_amortization=30.0,
        capital_expenditures=-25.0,
        change_in_working_capital=5.0,
    )
    positive_capex = ProjectedFCFF(
        year=2026,
        revenue=1000.0,
        ebit=100.0,
        nopat=80.0,
        depreciation_amortization=30.0,
        capital_expenditures=25.0,
        change_in_working_capital=5.0,
    )
    assert negative_capex.fcff == pytest.approx(80.0)
    assert positive_capex.fcff == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# calculate_terminal_value — Gordon Growth
# ---------------------------------------------------------------------------


def test_terminal_value_worked_example() -> None:
    """TV = FCFF_n * (1 + g) / (WACC - g)
          = 100 * 1.02 / (0.10 - 0.02)
          = 102 / 0.08
          = 1275.0
    """
    assert calculate_terminal_value(100.0, 0.02, 0.10) == pytest.approx(1275.0)


def test_terminal_value_with_zero_growth_is_a_flat_perpetuity() -> None:
    """Closed-form identity: at g = 0 Gordon Growth collapses to FCFF / WACC.

    TV = 50 * (1 + 0) / (0.10 - 0) = 50 / 0.10 = 500.0
    """
    assert calculate_terminal_value(50.0, 0.0, 0.10) == pytest.approx(500.0)


def test_terminal_value_with_a_narrow_spread() -> None:
    """A one-point spread makes the denominator small and the value large.

    TV = 100 * 1.04 / (0.05 - 0.04) = 104 / 0.01 = 10400.0
    """
    assert calculate_terminal_value(100.0, 0.04, 0.05) == pytest.approx(10400.0)


def test_terminal_value_is_linear_in_the_final_fcff() -> None:
    """The formula scales FCFF_n by a constant, so the sign carries through.

    TV = -100 * 1.02 / 0.08 = -102 / 0.08 = -1275.0
    """
    assert calculate_terminal_value(-100.0, 0.02, 0.10) == pytest.approx(-1275.0)


def test_terminal_value_raises_when_wacc_is_below_growth() -> None:
    """A WACC below g makes the denominator negative and the value meaningless.

    The run must stop, and the message must name both figures so the reader
    knows which two to compare. `analysis/dcf.py:24-27`.
    """
    with pytest.raises(ValueError) as excinfo:
        calculate_terminal_value(100.0, 0.05, 0.03)

    message = str(excinfo.value)
    assert "WACC" in message, "the message must name WACC"
    assert "0.03" in message, "the message must name the WACC that was passed"
    assert "growth" in message.lower(), "the message must name the growth rate"
    assert "0.05" in message, "the message must name the growth rate that was passed"


def test_terminal_value_raises_when_wacc_equals_growth() -> None:
    """The boundary case. At WACC == g the denominator is exactly zero, so
    this must raise rather than divide by zero — `<=`, not `<`.
    """
    with pytest.raises(ValueError) as excinfo:
        calculate_terminal_value(100.0, 0.05, 0.05)

    message = str(excinfo.value)
    assert "WACC" in message
    assert "growth" in message.lower()
    # 0.05 is both figures here, so it must appear twice for both to be named.
    assert message.count("0.05") >= 2, f"both figures must be named: {message!r}"


# ---------------------------------------------------------------------------
# discount_cash_flows
# ---------------------------------------------------------------------------


def test_discount_one_cash_flow() -> None:
    """PV = FCFF_1 / (1 + WACC)^1 = 110 / 1.1 = 100.0"""
    flows = [make_projected_fcff(2026, 110.0)]
    assert discount_cash_flows(flows, 0.10) == pytest.approx(100.0)


def test_discount_two_cash_flows() -> None:
    """PV = 100 / 1.25 + 100 / 1.25^2
          = 100 / 1.25 + 100 / 1.5625
          = 80.0 + 64.0
          = 144.0
    """
    flows = [make_projected_fcff(2026, 100.0), make_projected_fcff(2027, 100.0)]
    assert discount_cash_flows(flows, 0.25) == pytest.approx(144.0)


def test_discount_at_zero_wacc_is_the_plain_sum() -> None:
    """Closed-form identity: (1 + 0)^t = 1 for every t, so discounting at a
    WACC of zero must return the undiscounted sum.

    PV = 10 + 20 + 30 = 60.0
    """
    flows = [
        make_projected_fcff(2026, 10.0),
        make_projected_fcff(2027, 20.0),
        make_projected_fcff(2028, 30.0),
    ]
    assert discount_cash_flows(flows, 0.0) == pytest.approx(60.0)


def test_discounting_starts_at_year_one_not_year_zero() -> None:
    """The first projected year is one period away, so it is discounted once.

    At WACC = 1.0 the first period's factor is 2, so a single FCFF of 100.0
    is worth 100 / 2 = 50.0. A t = 0 convention would give 100.0, and this
    test is here to tell those two apart.
    """
    flows = [make_projected_fcff(2026, 100.0)]
    assert discount_cash_flows(flows, 1.0) == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# run_dcf
# ---------------------------------------------------------------------------


def _financials_with_a_balance_sheet() -> FinancialStatements:
    """Two years of statements. 2025 is the latest, so 2025's balance sheet is
    the one `run_dcf` must read. 2024 carries a deliberately absurd debt
    balance and absurd noncontrolling interests so that reading the wrong year
    cannot pass by accident.

    2025 net debt = total_debt - cash - short-term investments
                  = (0 + 0 + 100) - 30 - 0
                  = 70.0
    2025 NCI      = nonredeemable + redeemable = 0.0 + 0.0 = 0.0

    The two NCI parts are given as an explicit 0.0: this test company prints no
    noncontrolling interest. An explicit zero is a value, not a default — the
    field's own default is None ("not extracted"), on which `run_dcf` stops
    (P10a, backlog item 48).
    """
    return FinancialStatements(
        ticker="TEST",
        company_name="Test Co",
        income_statements=[IncomeStatement(year=2024), IncomeStatement(year=2025)],
        balance_sheets=[
            BalanceSheet(
                year=2024,
                cash_and_equivalents=0.0,
                long_term_debt=9999.0,
                noncontrolling_interest_nonredeemable=9999.0,
                noncontrolling_interest_redeemable=9999.0,
            ),
            BalanceSheet(
                year=2025,
                cash_and_equivalents=30.0,
                short_term_investments=0.0,
                long_term_debt=100.0,
                noncontrolling_interest_nonredeemable=0.0,
                noncontrolling_interest_redeemable=0.0,
            ),
        ],
    )


def test_run_dcf_worked_example() -> None:
    """The whole bridge, by hand, at WACC = 0.25 and g = 0.05.

    FCFF          100.0 in 2026 and 100.0 in 2027
    PV of FCFFs   100 / 1.25 + 100 / 1.5625 = 80.0 + 64.0        = 144.0
    Terminal      100 * 1.05 / (0.25 - 0.05) = 105 / 0.20        = 525.0
    PV terminal   525 / 1.25^2 = 525 / 1.5625                    = 336.0
    Enterprise    144.0 + 336.0                                  = 480.0
    Net debt      100 - 30 - 0  (2025 balance sheet)             =  70.0
    NCI           0 + 0         (2025 balance sheet, explicit)   =   0.0
    Equity        480.0 - 70.0 - 0.0                             = 410.0
    Share price   410.0 / 10.0 shares                            =  41.00
    Upside        (41.00 / 20.00 - 1) * 100                      = 105.0 %
    """
    result = run_dcf(
        projected_fcffs=[
            make_projected_fcff(2026, 100.0),
            make_projected_fcff(2027, 100.0),
        ],
        wacc_result=make_wacc_result(0.25),
        financials=_financials_with_a_balance_sheet(),
        terminal_growth_rate=0.05,
        current_price=20.0,
        diluted_shares=10.0,
    )

    assert result.ticker == "TEST"
    assert result.projection_years == 2
    assert result.wacc == pytest.approx(0.25)
    assert result.terminal_growth_rate == pytest.approx(0.05)

    assert result.pv_fcffs == pytest.approx(144.0)
    assert result.terminal_value == pytest.approx(525.0)
    assert result.pv_terminal_value == pytest.approx(336.0)
    assert result.enterprise_value == pytest.approx(480.0)

    assert result.net_debt == pytest.approx(70.0)
    assert result.cash == pytest.approx(30.0)
    assert result.noncontrolling_interest == pytest.approx(0.0)
    assert result.equity_value == pytest.approx(410.0)

    assert result.diluted_shares == pytest.approx(10.0)
    assert result.implied_share_price == pytest.approx(41.0)
    assert result.current_price == pytest.approx(20.0)
    assert result.upside_downside == pytest.approx(105.0)


@pytest.mark.parametrize("years", [1, 2, 3, 4, 5])
def test_run_dcf_flat_perpetuity_identity(years: int) -> None:
    """Closed-form identity, independent of the number of projected years.

    With a constant FCFF C and g = 0, the explicit period and the terminal
    value must sum to the flat perpetuity C / WACC for *any* n:

        PV(explicit) = sum_{t=1..n} C / (1+w)^t = (C/w) * (1 - (1+w)^-n)
        TV_n         = C * (1 + 0) / (w - 0)    =  C/w
        PV(TV_n)     = (C/w) * (1+w)^-n
        EV           = (C/w)*(1 - (1+w)^-n) + (C/w)*(1+w)^-n = C/w

    With C = 100 and w = 0.10 that is 100 / 0.10 = 1000.0 for n = 1..5.
    A discounting exponent off by one, or a terminal value discounted over
    the wrong number of periods, breaks this for every n but n = 0.
    """
    flows = [make_projected_fcff(2026 + i, 100.0) for i in range(years)]
    result = run_dcf(
        projected_fcffs=flows,
        wacc_result=make_wacc_result(0.10),
        financials=_financials_with_a_balance_sheet(),
        terminal_growth_rate=0.0,
        current_price=1.0,
        diluted_shares=1.0,
    )
    assert result.enterprise_value == pytest.approx(1000.0)


def test_run_dcf_raises_when_terminal_growth_is_not_below_wacc() -> None:
    """The `WACC <= g` stop must survive the composition, not only be
    reachable by calling `calculate_terminal_value` directly.

    WACC = 0.04, g = 0.06, so the run must stop and name both figures.
    """
    with pytest.raises(ValueError) as excinfo:
        run_dcf(
            projected_fcffs=[make_projected_fcff(2026, 100.0)],
            wacc_result=make_wacc_result(0.04),
            financials=_financials_with_a_balance_sheet(),
            terminal_growth_rate=0.06,
            current_price=20.0,
            diluted_shares=10.0,
        )

    message = str(excinfo.value)
    assert "WACC" in message
    assert "0.04" in message, "the message must name the WACC that was passed"
    assert "growth" in message.lower()
    assert "0.06" in message, "the message must name the growth rate that was passed"


# ---------------------------------------------------------------------------
# The stops. Rule 3 — a missing input stops the run and names the field.
#
# NaN is the shape a missing input takes once it has been through a float
# calculation, and `analysis/dcf.py`'s own `wacc <= terminal_growth_rate` guard
# cannot see it: `nan <= 0.025` is False, so a NaN walked straight past it and
# rendered as a NaN share price. Every expectation below is that requirement,
# not a message recorded from a run.
# ---------------------------------------------------------------------------

NAN = float("nan")


def test_terminal_value_stops_on_a_nan_final_cash_flow() -> None:
    """The terminal value is the whole of the enterprise value beyond the
    projection window, so a NaN base cash flow makes the entire valuation NaN.
    `calculate_terminal_value` is called directly as well as through `run_dcf`,
    so the guard has to be here and not only at the caller.

    The growth rate and WACC are the worked example's 0.02 and 0.10, which
    together give a finite 1275.0 from a base of 100 — so the only broken input
    is the one the message must name.
    """
    with pytest.raises(ValueError, match="final_fcff"):
        calculate_terminal_value(NAN, 0.02, 0.10)


def test_terminal_value_stops_on_a_nan_wacc_before_the_spread_check() -> None:
    """`wacc <= terminal_growth_rate` is False when `wacc` is NaN, so the spread
    check below it passes a NaN through and the division that follows returns
    NaN rather than raising. The NaN guard must therefore come first, and it
    must name both figures so a reader can see which of the two was broken.
    """
    with pytest.raises(ValueError) as excinfo:
        calculate_terminal_value(100.0, 0.02, NAN)

    message = str(excinfo.value)
    assert "WACC" in message
    assert "growth" in message.lower()


def test_terminal_value_stops_on_a_nan_growth_rate() -> None:
    """The same guard from the other side: a NaN growth rate also survives
    `wacc <= terminal_growth_rate` and reaches `(wacc - g)` in the denominator.
    """
    with pytest.raises(ValueError):
        calculate_terminal_value(100.0, NAN, 0.10)


def test_a_comparison_cannot_detect_the_nan_these_guards_catch() -> None:
    """The premise the three tests above rest on, stated as arithmetic rather
    than taken on trust. If `nan <= 0.02` were True the existing spread check
    would already have stopped the run and the NaN guards would be ceremony.
    """
    assert (NAN <= 0.02) is False
    assert (NAN > 0.02) is False
    assert math.isnan(NAN * 1.02 / (NAN - 0.02))


def test_discounting_stops_on_a_nan_year_and_names_that_year() -> None:
    """A single NaN year makes the whole present value NaN, because anything
    added to NaN is NaN. The guard names the *year* so a reader can find the
    offending projection rather than only learning that one of them was bad.

    Years 2026 and 2028 are finite; 2027 is not, and 2027 is what the message
    must say.
    """
    with pytest.raises(ValueError, match="2027"):
        discount_cash_flows(
            [
                make_projected_fcff(2026, 100.0),
                make_projected_fcff(2027, NAN),
                make_projected_fcff(2028, 100.0),
            ],
            0.10,
        )


def test_run_dcf_stops_when_there_are_no_projected_cash_flows() -> None:
    """A DCF needs at least one projected year: the terminal value is built from
    the final projected FCFF, and an empty list has no final element. Without
    the stop, `pv_fcffs` would be the empty sum 0.0 and the run would reach
    `projected_fcffs[-1]` and fail with an `IndexError` that names nothing.
    """
    with pytest.raises(ValueError, match="projected_fcffs"):
        run_dcf(
            projected_fcffs=[],
            wacc_result=make_wacc_result(0.10),
            financials=_financials_with_a_balance_sheet(),
            terminal_growth_rate=0.02,
            current_price=20.0,
            diluted_shares=10.0,
        )


# ---------------------------------------------------------------------------
# Backlog item 2: the balance sheet is absent.
#
# Moved here from `tests/unit/test_dcf_rule3_red.py` by `P10-tests`, unchanged in
# what it asserts, once `P10a-nci-bridge` made `run_dcf` stop. That file was
# deleted in the same unit: a green test left inside the `*_rule3_red.py`
# pattern is a test the gate never runs (backlog item 24).
# ---------------------------------------------------------------------------


def test_run_dcf_stops_when_the_balance_sheet_is_absent() -> None:
    """Enterprise value cannot be bridged to equity value without net debt.

    Until `P10a-nci-bridge`, `analysis/dcf.py` substituted `net_debt = 0.0` and
    `cash = 0.0` when the latest year had no balance sheet. On a clean run with
    no warning anywhere, equity value was then overstated by the entire debt
    balance and the implied share price with it. A zero that means "we do not
    know" and a zero that means "zero" are the same bytes.

    The required behaviour is a stop that names the missing input. The
    exception type asserted here is `ValueError`, which is what the rest of
    this codebase raises for an absent input.
    """
    financials = FinancialStatements(
        ticker="TEST",
        company_name="Test Co",
        income_statements=[IncomeStatement(year=2025)],
        balance_sheets=[],  # the missing input
    )
    wacc_result = WACCResult(
        cost_of_equity=0.10,
        cost_of_debt=0.0,
        tax_rate=0.0,
        equity_weight=1.0,
        debt_weight=0.0,
    )
    projected = [
        ProjectedFCFF(
            year=2026,
            revenue=0.0,
            ebit=0.0,
            nopat=100.0,
            depreciation_amortization=0.0,
            capital_expenditures=0.0,
            change_in_working_capital=0.0,
        )
    ]

    with pytest.raises(ValueError) as excinfo:
        run_dcf(
            projected_fcffs=projected,
            wacc_result=wacc_result,
            financials=financials,
            terminal_growth_rate=0.0,
            current_price=20.0,
            diluted_shares=10.0,
        )

    message = str(excinfo.value).lower()
    assert (
        "balance sheet" in message
        or "balance_sheet" in message
        or "net debt" in message
        or "net_debt" in message
    ), f"the message must name the missing input, got: {message!r}"


# ---------------------------------------------------------------------------
# P10a-nci-bridge (backlog item 48): the noncontrolling interests.
#
# Equity Value = Enterprise Value - Net Debt - (NCI nonredeemable + NCI redeemable)
# The two parts are two printed lines; Python sums them in
# `analysis/dcf.py:total_noncontrolling_interest`, which stops on None or NaN.
# ---------------------------------------------------------------------------

NCI_KEYS = ("noncontrolling_interest_nonredeemable", "noncontrolling_interest_redeemable")


def _financials_for_the_bridge(
    nonredeemable: float | None, redeemable: float | None
) -> FinancialStatements:
    """One year, 2025. Net debt = (0 + 0 + 200) - 0 - 0 = 200.0."""
    return FinancialStatements(
        ticker="TEST",
        company_name="Test Co",
        income_statements=[IncomeStatement(year=2025)],
        balance_sheets=[
            BalanceSheet(
                year=2025,
                cash_and_equivalents=0.0,
                short_term_investments=0.0,
                long_term_debt=200.0,
                noncontrolling_interest_nonredeemable=nonredeemable,
                noncontrolling_interest_redeemable=redeemable,
            ),
        ],
    )


def test_run_dcf_bridge_subtracts_net_debt_and_both_noncontrolling_interests() -> None:
    """The bridge with round numbers, by hand. WACC 10%, g 0, one year.

    PV of FCFF   100 / 1.10                                  =   90.909...
    Terminal     100 * (1 + 0) / (0.10 - 0)                  = 1000.0
    PV terminal  1000 / 1.10                                 =  909.090...
    Enterprise   (100 + 1000) / 1.10 = 1100 / 1.10           = 1000.0
    Net debt     200 - 0 - 0                                 =  200.0
    NCI          nonredeemable 40 + redeemable 10            =   50.0
    Equity       1000 - 200 - 50                             =  750.0
    Share price  750 / 10 shares                             =   75.0
    """
    result = run_dcf(
        projected_fcffs=[make_projected_fcff(2026, 100.0)],
        wacc_result=make_wacc_result(0.10),
        financials=_financials_for_the_bridge(40.0, 10.0),
        terminal_growth_rate=0.0,
        current_price=50.0,
        diluted_shares=10.0,
    )

    assert result.enterprise_value == pytest.approx(1000.0)
    assert result.net_debt == pytest.approx(200.0)
    assert result.noncontrolling_interest == pytest.approx(50.0)
    assert result.equity_value == pytest.approx(750.0)
    assert result.implied_share_price == pytest.approx(75.0)
    # Rule 4: the source line names both printed parts, their figures, the year
    # and the function that summed them (P10a round 2, step 2).
    source = result.noncontrolling_interest_source
    assert "nonredeemable 40" in source
    assert "redeemable 10" in source
    assert "FY2025" in source
    assert "total_noncontrolling_interest" in source


def test_equity_value_is_ev_less_net_debt_less_nci_on_the_result_itself() -> None:
    """The property, independent of `run_dcf`: 1000 - 200 - 50 = 750, / 10 = 75."""
    from models.valuation import DCFResult

    result = DCFResult(
        ticker="TEST",
        projection_years=1,
        terminal_growth_rate=0.0,
        wacc=0.10,
        pv_fcffs=400.0,
        pv_terminal_value=600.0,  # 400 + 600 = 1000 enterprise value
        net_debt=200.0,
        diluted_shares=10.0,
        noncontrolling_interest=50.0,
        noncontrolling_interest_source="by hand",
    )
    assert result.enterprise_value == pytest.approx(1000.0)
    assert result.equity_value == pytest.approx(750.0)
    assert result.implied_share_price == pytest.approx(75.0)


@pytest.mark.parametrize(
    ("nonredeemable", "redeemable", "expected"),
    [
        (40.0, 10.0, 50.0),   # 40 + 10
        (6270.0, 293.0, 6563.0),  # Walmart FY2026 shape: 6,270 + 293 = 6,563
        (0.0, 0.0, 0.0),      # a company that prints neither line: explicit zeros
        (0.0, 25.0, 25.0),    # 0 + 25: only the redeemable line printed
    ],
)
def test_total_noncontrolling_interest_is_the_sum_of_the_two_printed_parts(
    nonredeemable: float, redeemable: float, expected: float
) -> None:
    from analysis.dcf import total_noncontrolling_interest

    sheet = BalanceSheet(
        year=2025,
        noncontrolling_interest_nonredeemable=nonredeemable,
        noncontrolling_interest_redeemable=redeemable,
    )
    assert total_noncontrolling_interest(sheet) == pytest.approx(expected)


@pytest.mark.parametrize("missing_key", NCI_KEYS)
@pytest.mark.parametrize("bad_value", [None, NAN], ids=["None", "NaN"])
def test_total_noncontrolling_interest_stops_naming_the_key_and_the_year(
    missing_key: str, bad_value: float | None
) -> None:
    """Rule 3. One part is None ("not extracted") or NaN; the other is a good 10.0.
    The stop names the bad key and the balance sheet's year, FY2031 — a year
    used nowhere else in this file, so the match cannot come from elsewhere.
    """
    from analysis.dcf import total_noncontrolling_interest

    values: dict[str, float | None] = {key: 10.0 for key in NCI_KEYS}
    values[missing_key] = bad_value
    sheet = BalanceSheet(year=2031, **values)  # type: ignore[arg-type]

    with pytest.raises(ValueError) as excinfo:
        total_noncontrolling_interest(sheet)

    message = str(excinfo.value)
    assert missing_key in message
    assert "2031" in message
    # Only the bad key is named, not the good one.
    (other_key,) = [key for key in NCI_KEYS if key != missing_key]
    assert other_key not in message


def test_total_noncontrolling_interest_stops_when_neither_part_was_set() -> None:
    """A `BalanceSheet` built without either field: both are None (not extracted).
    The stop is a ValueError naming a key, never a total of 0.0."""
    from analysis.dcf import total_noncontrolling_interest

    with pytest.raises(ValueError, match="noncontrolling_interest_"):
        total_noncontrolling_interest(BalanceSheet(year=2025))


@pytest.mark.parametrize("missing_key", NCI_KEYS)
def test_run_dcf_stops_when_a_noncontrolling_interest_was_not_extracted(
    missing_key: str,
) -> None:
    """The stop survives the composition: through `run_dcf`, not only directly."""
    parts: dict[str, float | None] = {key: 10.0 for key in NCI_KEYS}
    parts[missing_key] = None

    with pytest.raises(ValueError) as excinfo:
        run_dcf(
            projected_fcffs=[make_projected_fcff(2026, 100.0)],
            wacc_result=make_wacc_result(0.10),
            financials=_financials_for_the_bridge(
                parts["noncontrolling_interest_nonredeemable"],
                parts["noncontrolling_interest_redeemable"],
            ),
            terminal_growth_rate=0.0,
            current_price=50.0,
            diluted_shares=10.0,
        )
    assert missing_key in str(excinfo.value)
    assert "2025" in str(excinfo.value)


@pytest.mark.parametrize(
    ("nonredeemable", "redeemable"),
    [(None, None), (0.0, 0.0), (7.0, 3.0)],
    ids=["not-extracted", "zeros", "seven-and-three"],
)
def test_neither_nci_part_enters_any_balance_sheet_total(
    nonredeemable: float | None, redeemable: float | None
) -> None:
    """Both parts are memos, already inside another line (P10a step 3).

    By hand, whatever the two NCI parts are:
      total_assets      = cash 100 + PP&E 300                 = 400
      total_liabilities = payables 50 + long-term debt 150    = 200
      total_equity      = 200 (as given)
      balance check     = 400 - (200 + 200)                   =   0
    """
    sheet = BalanceSheet(
        year=2025,
        cash_and_equivalents=100.0,
        ppe_net=300.0,
        accounts_payable=50.0,
        long_term_debt=150.0,
        total_equity=200.0,
        noncontrolling_interest_nonredeemable=nonredeemable,
        noncontrolling_interest_redeemable=redeemable,
    )
    assert sheet.total_assets == pytest.approx(400.0)
    assert sheet.total_liabilities == pytest.approx(200.0)
    assert sheet.total_equity == pytest.approx(200.0)
    assert sheet.balance_check_difference == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Backlog item 32: no share count is no share price. Added by `P13b-tests`.
#
# Before `P13b-models-silent`, `DCFResult.implied_share_price` returned 0.0 when
# `diluted_shares` was zero (a company worth nothing), NaN on a NaN count, 0.0 on
# an infinite one, and a negative price on a negative one; `run_dcf` checked
# nothing. Rule 3: the absent input stops and names itself.
#
# Nothing below asserts a price of 0.0 for a zero share count. That is the
# default the unit removed.
# ---------------------------------------------------------------------------

NO_SHARE_COUNT = [
    pytest.param(0.0, id="zero"),
    pytest.param(0, id="integer-zero"),
    pytest.param(-10.0, id="negative"),
    pytest.param(math.nan, id="nan"),
    pytest.param(math.inf, id="inf"),
    pytest.param(-math.inf, id="minus-inf"),
]


@pytest.mark.parametrize("shares", NO_SHARE_COUNT)
def test_run_dcf_stops_on_no_share_count_and_names_it(shares: float) -> None:
    """Every other input is clean, so only the share count can stop the run.

    With a valid count these inputs give a price (the bridge test above uses
    the same balance sheet), so a run that returned anything here returned a
    price for a valuation that has no share count.
    """
    with pytest.raises(ValueError) as excinfo:
        run_dcf(
            projected_fcffs=[make_projected_fcff(2026, 100.0)],
            wacc_result=make_wacc_result(0.10),
            financials=_financials_for_the_bridge(40.0, 10.0),
            terminal_growth_rate=0.0,
            current_price=50.0,
            diluted_shares=shares,
        )

    message = str(excinfo.value)
    assert "diluted_shares" in message   # the field
    assert repr(shares) in message       # and the value that was refused


@pytest.mark.parametrize("shares", NO_SHARE_COUNT)
def test_run_dcf_checks_the_share_count_before_it_discounts_anything(
    shares: float,
) -> None:
    """The share check comes first: before discounting and before the balance sheet.

    The other inputs are poisoned so that each later check would raise with a
    different message:

      * the one projected FCFF is NaN, so `discount_cash_flows` would stop
        naming "the projected FCFF for year 2026";
      * there is no balance sheet, so the bridge would stop naming the
        balance sheet.

    Only a share check that runs before both can produce a message naming
    `diluted_shares`.
    """
    financials = FinancialStatements(
        ticker="TEST",
        income_statements=[IncomeStatement(year=2025)],
        balance_sheets=[],
    )

    with pytest.raises(ValueError) as excinfo:
        run_dcf(
            projected_fcffs=[make_projected_fcff(2026, math.nan)],
            wacc_result=make_wacc_result(0.10),
            financials=financials,
            terminal_growth_rate=0.0,
            current_price=50.0,
            diluted_shares=shares,
        )

    message = str(excinfo.value)
    assert "diluted_shares" in message
    assert "projected FCFF" not in message
    assert "balance sheet" not in message


def _result_with_shares(shares: float) -> DCFResult:
    """EV 400 + 600 = 1000, net debt 250, NCI 150 -> equity 1000 - 250 - 150 = 600."""
    return DCFResult(
        ticker="TEST",
        projection_years=1,
        terminal_growth_rate=0.0,
        wacc=0.10,
        pv_fcffs=400.0,
        pv_terminal_value=600.0,
        net_debt=250.0,
        diluted_shares=shares,
        current_price=0.0,
        noncontrolling_interest=150.0,
        noncontrolling_interest_source="by hand",
    )


@pytest.mark.parametrize("shares", NO_SHARE_COUNT)
def test_implied_share_price_on_a_result_built_directly_stops_on_no_share_count(
    shares: float,
) -> None:
    """The property guards a result that never passed through `run_dcf`."""
    result = _result_with_shares(shares)

    with pytest.raises(ValueError, match="diluted_shares"):
        _ = result.implied_share_price


def test_implied_share_price_on_a_result_built_directly_is_equity_over_shares() -> None:
    """The control for the stop, by hand from the bridge.

    Enterprise  400 + 600            = 1000.0
    Equity      1000 - 250 - 150     =  600.0
    Price       600 / 40 shares      =   15.0
    """
    result = _result_with_shares(40.0)

    assert result.equity_value == pytest.approx(600.0)
    assert result.implied_share_price == pytest.approx(15.0)


def test_run_dcf_positive_share_count_gives_the_bridge_price_by_hand() -> None:
    """One positive case through `run_dcf`, every step by hand. WACC 20%, g 0, one year.

    PV of FCFF   120 / 1.20                                  =  100.0
    Terminal     120 * (1 + 0) / (0.20 - 0)                  =  600.0
    PV terminal  600 / 1.20                                  =  500.0
    Enterprise   100 + 500                                   =  600.0
    Net debt     long-term debt 150 - cash 50 - STI 0        =  100.0
    NCI          nonredeemable 20 + redeemable 30            =   50.0
    Equity       600 - 100 - 50                              =  450.0
    Price        450 / 18 shares                             =   25.0
    """
    financials = FinancialStatements(
        ticker="TEST",
        income_statements=[IncomeStatement(year=2025)],
        balance_sheets=[
            BalanceSheet(
                year=2025,
                cash_and_equivalents=50.0,
                short_term_investments=0.0,
                long_term_debt=150.0,
                noncontrolling_interest_nonredeemable=20.0,
                noncontrolling_interest_redeemable=30.0,
            ),
        ],
    )

    result = run_dcf(
        projected_fcffs=[make_projected_fcff(2026, 120.0)],
        wacc_result=make_wacc_result(0.20),
        financials=financials,
        terminal_growth_rate=0.0,
        current_price=50.0,
        diluted_shares=18.0,
    )

    assert result.enterprise_value == pytest.approx(600.0)
    assert result.net_debt == pytest.approx(100.0)
    assert result.noncontrolling_interest == pytest.approx(50.0)
    assert result.equity_value == pytest.approx(450.0)
    assert result.diluted_shares == pytest.approx(18.0)
    assert result.implied_share_price == pytest.approx(25.0)
