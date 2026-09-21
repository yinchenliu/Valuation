"""Unit tests for `analysis/fcff.py`.

Every expected value in this file was derived **before the code ran**, from the
hand arithmetic written out above the assertion or from a closed-form identity
that must hold whatever the inputs are. No expected value here was obtained by
running the code and recording what it printed.
See `docs/5-testing/strategy.md` section 1.

Nothing here needs an API key, a PDF, or the network: every input is a
dataclass built in this file, with only the fields the function under test
reads. See `docs/5-testing/strategy.md` section 3.

Units: every money figure is **millions**, per
`docs/4-conventions/units-and-signs.md` section 1. Rates are decimals.

The two formulas under test, from `docs/3-architecture/valuation-math.md`
sections 3 and 4:

    historical   FCFF = CFO + interest_expense * (1 - t) - CapEx
    projected    FCFF = EBIT * (1 - t) + D&A - CapEx - dNWC
                      = NOPAT + D&A - CapEx - dNWC
"""

from __future__ import annotations

import pytest

from analysis.fcff import calculate_fcff_historical, calculate_fcff_projected
from models.financial_statements import CashFlowStatement, IncomeStatement

# ---------------------------------------------------------------------------
# Fixtures, built by hand so that every derived figure is checkable on paper.
#
#   IncomeStatement 2025
#     EBIT   = revenue - (cost_of_revenue + sga + rd + D&A + other opex)
#            = 1000 - (600 + 50 + 0 + 50 + 0)
#            = 1000 - 700
#            = 300
#     EBT    = EBIT - interest_expense = 300 - 100 = 200
#     t      = tax_expense / EBT = 40 / 200 = 0.20
#
#   CashFlowStatement 2025
#     CFO    = net_income + D&A + SBC + dWC + other
#            = 160 + 50 + 30 + (-40) + 0
#            = 200
#     CapEx  = |-70| = 70
# ---------------------------------------------------------------------------


def _income_statement_2025(interest_expense: float = 100.0) -> IncomeStatement:
    return IncomeStatement(
        year=2025,
        revenue=1000.0,
        cost_of_revenue=600.0,
        sga=50.0,
        depreciation_amortization=50.0,
        interest_expense=interest_expense,
        tax_expense=40.0,
    )


def _cash_flow_2025(capital_expenditures: float = -70.0) -> CashFlowStatement:
    return CashFlowStatement(
        year=2025,
        net_income=160.0,
        depreciation_amortization=50.0,
        stock_based_compensation=30.0,
        change_in_working_capital=-40.0,
        capital_expenditures=capital_expenditures,
    )


# ---------------------------------------------------------------------------
# calculate_fcff_historical — CFO-based
# ---------------------------------------------------------------------------


def test_historical_fcff_worked_example() -> None:
    """The whole CFO-based formula, by hand, before running anything.

        EBIT             1000 - 700                       = 300
        EBT              300 - 100                        = 200
        t                40 / 200                         = 0.20
        CFO              160 + 50 + 30 - 40               = 200
        interest         |100|                            = 100
        after-tax int.   100 * (1 - 0.20) = 100 * 0.80    =  80
        CapEx            |-70|                            =  70
        FCFF             200 + 80 - 70                    = 210
    """
    result = calculate_fcff_historical(_income_statement_2025(), _cash_flow_2025())

    assert result.year == 2025
    assert result.revenue == pytest.approx(1000.0)
    assert result.ebit == pytest.approx(300.0)
    assert result.cfo == pytest.approx(200.0)
    assert result.tax_rate == pytest.approx(0.20)
    assert result.interest_expense == pytest.approx(100.0)
    assert result.after_tax_interest == pytest.approx(80.0)
    assert result.capital_expenditures == pytest.approx(70.0)
    assert result.fcff == pytest.approx(210.0)


def test_historical_fcff_is_the_same_for_either_capex_sign() -> None:
    """A filing that reports CapEx as -70 and one that reports it as +70 must
    give the same FCFF, because `analysis/fcff.py:49` takes the magnitude.

    Both: FCFF = 200 + 80 - 70 = 210, and the reported CapEx is +70 either way.

    A CapEx sign flip is the easiest error in this area to make and the hardest
    to see: with the sign carried through, +70 would give 200 + 80 + 70 = 350.
    """
    negative = calculate_fcff_historical(
        _income_statement_2025(), _cash_flow_2025(capital_expenditures=-70.0)
    )
    positive = calculate_fcff_historical(
        _income_statement_2025(), _cash_flow_2025(capital_expenditures=70.0)
    )

    assert negative.capital_expenditures == pytest.approx(70.0)
    assert positive.capital_expenditures == pytest.approx(70.0)
    assert negative.fcff == pytest.approx(210.0)
    assert positive.fcff == pytest.approx(210.0)


def test_historical_fcff_is_the_same_for_either_interest_sign() -> None:
    """`analysis/fcff.py:47` takes the magnitude of interest expense too.

    The tax rate is supplied explicitly here so that the two cases differ in
    exactly one thing. Without the override they would not: flipping the sign
    of interest expense also moves EBT (300 + 100 = 400) and therefore the
    effective rate (40 / 400 = 0.10), and the comparison would no longer
    isolate the `abs()`.

        FCFF = 200 + |interest| * (1 - 0.20) - 70
             = 200 + 100 * 0.80 - 70
             = 210      for interest = +100 and for interest = -100
    """
    reported_positive = calculate_fcff_historical(
        _income_statement_2025(interest_expense=100.0),
        _cash_flow_2025(),
        tax_rate_override=0.20,
    )
    reported_negative = calculate_fcff_historical(
        _income_statement_2025(interest_expense=-100.0),
        _cash_flow_2025(),
        tax_rate_override=0.20,
    )

    assert reported_positive.interest_expense == pytest.approx(100.0)
    assert reported_negative.interest_expense == pytest.approx(100.0)
    assert reported_positive.fcff == pytest.approx(210.0)
    assert reported_negative.fcff == pytest.approx(210.0)


def test_historical_fcff_with_a_zero_tax_override_adds_back_gross_interest() -> None:
    """Closed-form identity: at t = 0 the after-tax interest add-back is the
    whole interest expense, because the tax shield vanishes.

        FCFF = CFO + interest * (1 - 0) - CapEx
             = 200 + 100 - 70
             = 230

    The override is what is being exercised here: the income statement's own
    effective rate is 0.20, so a run that ignored the override would give 210.
    """
    result = calculate_fcff_historical(
        _income_statement_2025(), _cash_flow_2025(), tax_rate_override=0.0
    )

    assert result.tax_rate == pytest.approx(0.0)
    assert result.after_tax_interest == pytest.approx(100.0)
    assert result.fcff == pytest.approx(230.0)


def test_historical_fcff_override_replaces_the_effective_rate() -> None:
    """The same inputs at a supplied t = 0.40 rather than the statement's 0.20.

        after-tax interest = 100 * (1 - 0.40) = 60
        FCFF               = 200 + 60 - 70    = 190
    """
    result = calculate_fcff_historical(
        _income_statement_2025(), _cash_flow_2025(), tax_rate_override=0.40
    )

    assert result.tax_rate == pytest.approx(0.40)
    assert result.after_tax_interest == pytest.approx(60.0)
    assert result.fcff == pytest.approx(190.0)


# ---------------------------------------------------------------------------
# calculate_fcff_projected — EBIT-based
# ---------------------------------------------------------------------------


def test_projected_fcff_worked_example() -> None:
    """The whole EBIT-based formula, by hand, before running anything.

        EBIT    2000 * 0.20                 = 400
        NOPAT   400 * (1 - 0.25) = 400*0.75 = 300
        D&A     2000 * 0.04                 =  80
        CapEx   2000 * 0.06                 = 120
        dNWC    2000 * 0.01                 =  20
        FCFF    300 + 80 - 120 - 20         = 240
    """
    result = calculate_fcff_projected(
        year=2026,
        revenue=2000.0,
        operating_margin=0.20,
        tax_rate=0.25,
        da_pct_revenue=0.04,
        capex_pct_revenue=0.06,
        nwc_pct_revenue=0.01,
    )

    assert result.year == 2026
    assert result.revenue == pytest.approx(2000.0)
    assert result.ebit == pytest.approx(400.0)
    assert result.nopat == pytest.approx(300.0)
    assert result.depreciation_amortization == pytest.approx(80.0)
    assert result.capital_expenditures == pytest.approx(120.0)
    assert result.change_in_working_capital == pytest.approx(20.0)
    assert result.fcff == pytest.approx(240.0)


def test_projected_nopat_at_a_zero_tax_rate_equals_ebit() -> None:
    """Closed-form identity named in `docs/5-testing/strategy.md` section 1:
    NOPAT = EBIT * (1 - t), so at t = 0 it is EBIT itself.

        EBIT = 500 * 0.40 = 200, and NOPAT = 200 * 1 = 200.
    """
    result = calculate_fcff_projected(
        year=2026,
        revenue=500.0,
        operating_margin=0.40,
        tax_rate=0.0,
        da_pct_revenue=0.0,
        capex_pct_revenue=0.0,
        nwc_pct_revenue=0.0,
    )

    assert result.ebit == pytest.approx(200.0)
    assert result.nopat == pytest.approx(result.ebit)
    assert result.nopat == pytest.approx(200.0)


def test_projected_fcff_is_the_same_for_either_capex_sign() -> None:
    """`ProjectedFCFF.fcff` (`models/valuation.py:100`) takes the magnitude of
    CapEx, so a CapEx percentage supplied as -0.06 must give the same FCFF as
    +0.06 — the same convention `calculate_fcff_historical` applies.

        +0.06 -> CapEx = +120, FCFF = 300 + 80 - |+120| - 20 = 240
        -0.06 -> CapEx = -120, FCFF = 300 + 80 - |-120| - 20 = 240

    With the sign carried through, the -0.06 case would give 480.
    """
    positive = calculate_fcff_projected(
        year=2026,
        revenue=2000.0,
        operating_margin=0.20,
        tax_rate=0.25,
        da_pct_revenue=0.04,
        capex_pct_revenue=0.06,
        nwc_pct_revenue=0.01,
    )
    negative = calculate_fcff_projected(
        year=2026,
        revenue=2000.0,
        operating_margin=0.20,
        tax_rate=0.25,
        da_pct_revenue=0.04,
        capex_pct_revenue=-0.06,
        nwc_pct_revenue=0.01,
    )

    assert positive.capital_expenditures == pytest.approx(120.0)
    assert negative.capital_expenditures == pytest.approx(-120.0)
    assert positive.fcff == pytest.approx(240.0)
    assert negative.fcff == pytest.approx(240.0)


def test_projected_fcff_subtracts_a_growing_working_capital() -> None:
    """dNWC enters with a minus sign, so a positive `nwc_pct_revenue` must
    *reduce* FCFF. This is the half of the two-flip convention that lives in
    `analysis/fcff.py`; the negation that feeds it lives in
    `analysis/projector.py` and is not this file's subject.
    See `docs/4-conventions/units-and-signs.md` section 3.

        at nwc_pct = 0.00: FCFF = 300 + 80 - 120 - 0  = 260
        at nwc_pct = 0.01: FCFF = 300 + 80 - 120 - 20 = 240

    A reversed sign would give 280 for the second case, which is higher than
    the first and would still look like a plausible number.
    """
    no_growth = calculate_fcff_projected(
        year=2026,
        revenue=2000.0,
        operating_margin=0.20,
        tax_rate=0.25,
        da_pct_revenue=0.04,
        capex_pct_revenue=0.06,
        nwc_pct_revenue=0.0,
    )
    growing = calculate_fcff_projected(
        year=2026,
        revenue=2000.0,
        operating_margin=0.20,
        tax_rate=0.25,
        da_pct_revenue=0.04,
        capex_pct_revenue=0.06,
        nwc_pct_revenue=0.01,
    )

    assert no_growth.fcff == pytest.approx(260.0)
    assert growing.fcff == pytest.approx(240.0)
    assert growing.fcff < no_growth.fcff


# ---------------------------------------------------------------------------
# The two methods are the same measure
# ---------------------------------------------------------------------------


def test_the_two_fcff_methods_agree_when_the_definitions_line_up() -> None:
    """The CFO-based and EBIT-based formulas are two routes to one measure.
    They coincide exactly when the two definitional gaps named in
    `docs/3-architecture/valuation-math.md` section 4 are closed:

      1. CFO equals NOPAT + D&A - dNWC — i.e. the only operating add-backs are
         D&A and the working-capital movement, and there is no SBC;
      2. interest expense is zero, so the after-tax add-back that converts CFO
         to a pre-financing measure is zero too.

    Both are arranged here on purpose, so the assertion is about the formulas
    and not about a company.

        Income statement 2025
          EBIT  = 1000 - (650 + 50) = 300
          EBT   = 300 - 0           = 300
          t     = 75 / 300          = 0.25
          NI    = 300 - 75          = 225

        Cash flow statement 2025
          CFO   = 225 + 50 + 0 + (-20) = 255      == NOPAT + D&A - dNWC
                                                   == 225 +  50 -   20
          CapEx = |-70|                =  70

        historical FCFF = 255 + 0 * (1 - 0.25) - 70          = 185
        projected  FCFF = 225 + 50 - 70 - 20                 = 185

    The projected side is fed the ratios the same year implies:
    operating_margin 300/1000 = 0.30, D&A 50/1000 = 0.05,
    CapEx 70/1000 = 0.07, dNWC -(-20)/1000 = 0.02.
    """
    income = IncomeStatement(
        year=2025,
        revenue=1000.0,
        cost_of_revenue=650.0,
        depreciation_amortization=50.0,
        interest_expense=0.0,
        tax_expense=75.0,
    )
    cash_flow = CashFlowStatement(
        year=2025,
        net_income=225.0,
        depreciation_amortization=50.0,
        stock_based_compensation=0.0,
        change_in_working_capital=-20.0,
        capital_expenditures=-70.0,
    )

    historical = calculate_fcff_historical(income, cash_flow)
    projected = calculate_fcff_projected(
        year=2025,
        revenue=1000.0,
        operating_margin=0.30,
        tax_rate=0.25,
        da_pct_revenue=0.05,
        capex_pct_revenue=0.07,
        nwc_pct_revenue=0.02,
    )

    assert historical.fcff == pytest.approx(185.0)
    assert projected.fcff == pytest.approx(185.0)
    assert historical.fcff == pytest.approx(projected.fcff)


def test_stock_based_compensation_is_the_gap_between_the_two_methods() -> None:
    """The counterpart to the test above, and the reason the two methods must
    never be compared as a trend (`valuation-math.md` section 4).

    Taking the aligned year and adding 30 of SBC to the cash flow statement —
    changing nothing on the projected side — raises CFO by 30 and therefore
    raises the CFO-based FCFF by exactly 30, to 215, while the EBIT-based
    figure stays at 185. The gap is the SBC, not a change in the business.

        CFO  = 225 + 50 + 30 - 20 = 285
        FCFF = 285 + 0 - 70       = 215
        215 - 185                 = 30
    """
    income = IncomeStatement(
        year=2025,
        revenue=1000.0,
        cost_of_revenue=650.0,
        depreciation_amortization=50.0,
        interest_expense=0.0,
        tax_expense=75.0,
    )
    with_sbc = CashFlowStatement(
        year=2025,
        net_income=225.0,
        depreciation_amortization=50.0,
        stock_based_compensation=30.0,
        change_in_working_capital=-20.0,
        capital_expenditures=-70.0,
    )

    historical = calculate_fcff_historical(income, with_sbc)

    assert historical.cfo == pytest.approx(285.0)
    assert historical.fcff == pytest.approx(215.0)
    assert historical.fcff - 185.0 == pytest.approx(30.0)
