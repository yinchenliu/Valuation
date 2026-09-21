"""Independently-derived tests for `analysis/projector.py`.

Every expected value in this file was computed by hand before
`analysis/projector.py` was run, and the arithmetic is written out above each
assertion. **None of them came from executing the code.**

The two things this file exists to pin:

1. **The delta-NWC sign**, all the way through to FCFF. Derived from the
   definition, not from reading `analysis/projector.py:97`:

   Working capital growing *consumes* cash. The cash flow statement reports
   "changes in operating assets and liabilities" from the cash point of view, so
   a year in which working capital grows shows a **negative**
   `change_in_working_capital` (`docs/4-conventions/units-and-signs.md` section
   3). Projected FCFF is `NOPAT + D&A - CapEx - delta_NWC`
   (`models/valuation.py:80-81`), i.e. it **subtracts** delta-NWC. For a growing
   working capital to *reduce* FCFF — which it must, because the cash left the
   firm — `nwc_pct_revenue` has to be **positive**. So the derivation from the
   CFS figure must carry a negation, and `-cf.change_in_working_capital / revenue`
   is what that negation looks like. Removing it reverses the effect of working
   capital on the valuation while still producing a plausible share price, which
   is why it is checked here at the point it changes FCFF rather than at the
   point it is computed.

2. **A supplied override of `0.0`** reaching the output for all five overridable
   percentage fields. A deliberate zero is a value, not an absence. Backlog item
   6 is the same defect at the route boundary; these tests say whether
   `derive_assumptions` itself honours a zero.

No test in this file asserts a rule-3 fallback. Where the code defaults instead
of stopping, the journal entry names the `file:line` and no assertion is written.
"""

from __future__ import annotations

import pytest

import config
from analysis.projector import derive_assumptions, project_fcffs
from models.financial_statements import (
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
)
from models.valuation import ProjectionAssumptions

# --------------------------------------------------------------------------
# Fixtures, built by hand. No network, no key, no pickle.
# --------------------------------------------------------------------------


def _three_year_financials() -> FinancialStatements:
    """Three years chosen so that every derived assumption is exact on paper.

    year  revenue  COGS  EBIT  margin  tax_exp  tax rate  D&A  D&A%  capex  capex%   dWC   nwc%
    2022      100    80    20    0.20        4      0.20   10  0.10     -5    0.05    -2   +0.02
    2023      200   140    60    0.30       18      0.30   40  0.20    -30    0.15   -12   +0.06
    2024      400   240   160    0.40       16      0.10  120  0.30   -100    0.25   -16   +0.04

    EBIT              = revenue - COGS (no other operating expense is set).
    effective tax rate= tax_expense / EBT, and EBT = EBIT here because no
                        interest or non-operating line is set.
    D&A% / capex%     = the cash-flow figure over the same year's revenue;
                        capex is negative on the statement and enters as a
                        magnitude.
    nwc%              = MINUS the cash-flow figure over revenue: every one of
                        these three years shows working capital growing (a
                        negative CFS line), so every nwc% is positive.

    Hand-derived assumptions, all three years averaged:

        revenue growth : lookback = min(3, 3 - 1) = 2 years, so the CAGR runs
                         from 2022 to 2024: (400 / 100) ** (1/2) - 1
                       = 2 - 1 = 1.00
        operating margin (0.20 + 0.30 + 0.40) / 3 = 0.30
        tax rate         (0.20 + 0.30 + 0.10) / 3 = 0.20
        D&A %            (0.10 + 0.20 + 0.30) / 3 = 0.20
        capex %          (0.05 + 0.15 + 0.25) / 3 = 0.15
        nwc %            (0.02 + 0.06 + 0.04) / 3 = 0.04

    Every one of the six is non-zero, which is what makes the `0.0`-override
    tests below falsifiable.
    """
    return FinancialStatements(
        ticker="TEST",
        income_statements=[
            IncomeStatement(year=2022, revenue=100.0, cost_of_revenue=80.0, tax_expense=4.0),
            IncomeStatement(year=2023, revenue=200.0, cost_of_revenue=140.0, tax_expense=18.0),
            IncomeStatement(year=2024, revenue=400.0, cost_of_revenue=240.0, tax_expense=16.0),
        ],
        cash_flow_statements=[
            CashFlowStatement(
                year=2022,
                depreciation_amortization=10.0,
                capital_expenditures=-5.0,
                change_in_working_capital=-2.0,
            ),
            CashFlowStatement(
                year=2023,
                depreciation_amortization=40.0,
                capital_expenditures=-30.0,
                change_in_working_capital=-12.0,
            ),
            CashFlowStatement(
                year=2024,
                depreciation_amortization=120.0,
                capital_expenditures=-100.0,
                change_in_working_capital=-16.0,
            ),
        ],
    )


def _one_year_financials(
    revenue: float,
    change_in_working_capital: float,
) -> FinancialStatements:
    """A single 2024 year carrying only revenue and the working-capital change."""
    return FinancialStatements(
        ticker="TEST",
        income_statements=[IncomeStatement(year=2024, revenue=revenue)],
        cash_flow_statements=[
            CashFlowStatement(
                year=2024,
                change_in_working_capital=change_in_working_capital,
            )
        ],
    )


def _nwc_overrides() -> ProjectionAssumptions:
    """Everything supplied except `nwc_pct_revenue`, which stays derived.

    One projection year at 0% growth, so the projected revenue equals the last
    historical revenue and every figure below is a plain percentage of it.
    """
    return ProjectionAssumptions(
        projection_years=1,
        revenue_growth_rates=[0.0],
        operating_margin=0.20,
        tax_rate=0.25,
        da_pct_revenue=0.10,
        capex_pct_revenue=0.05,
    )


# --------------------------------------------------------------------------
# derive_assumptions — the derived path
# --------------------------------------------------------------------------


def test_every_derived_assumption_matches_hand_arithmetic() -> None:
    """All six derived figures, from the table in `_three_year_financials`.

        revenue growth   (400 / 100) ** (1/2) - 1        = 1.00, repeated
        operating margin (0.20 + 0.30 + 0.40) / 3        = 0.30
        tax rate         (0.20 + 0.30 + 0.10) / 3        = 0.20
        D&A %            (0.10 + 0.20 + 0.30) / 3        = 0.20
        capex %          (0.05 + 0.15 + 0.25) / 3        = 0.15
        nwc %            (0.02 + 0.06 + 0.04) / 3        = 0.04
    """
    out = derive_assumptions(_three_year_financials())

    assert out["revenue_growth_rates"] == [pytest.approx(1.0)] * 5
    assert out["operating_margin"] == pytest.approx(0.30)
    assert out["tax_rate"] == pytest.approx(0.20)
    assert out["da_pct_revenue"] == pytest.approx(0.20)
    assert out["capex_pct_revenue"] == pytest.approx(0.15)
    assert out["nwc_pct_revenue"] == pytest.approx(0.04)


def test_capex_enters_as_a_magnitude_whichever_sign_the_filing_used() -> None:
    """`docs/4-conventions/units-and-signs.md` section 3: capex is a magnitude.

    Extraction sign conventions vary between filings, so a capital expenditure
    of -100 and one of +100 on a revenue of 400 must both give a capex
    percentage of 100 / 400 = 0.25. A capex percentage can never be negative:
    spending money on plant is not a source of cash.
    """
    negative = FinancialStatements(
        ticker="TEST",
        income_statements=[IncomeStatement(year=2024, revenue=400.0)],
        cash_flow_statements=[
            CashFlowStatement(year=2024, capital_expenditures=-100.0)
        ],
    )
    positive = FinancialStatements(
        ticker="TEST",
        income_statements=[IncomeStatement(year=2024, revenue=400.0)],
        cash_flow_statements=[
            CashFlowStatement(year=2024, capital_expenditures=100.0)
        ],
    )

    assert derive_assumptions(negative)["capex_pct_revenue"] == pytest.approx(0.25)
    assert derive_assumptions(positive)["capex_pct_revenue"] == pytest.approx(0.25)


def test_the_revenue_cagr_uses_only_the_lookback_window() -> None:
    """The CAGR must ignore years older than the lookback window.

    `config.DEFAULT_REVENUE_GROWTH_LOOKBACK_YEARS` is 3 and carries its reason on
    the line above it (`config.py:28-30`): a rolling window keeps a one-off macro
    trough out of the growth forecast. The fixture is built to make the two
    answers unmistakably different.

        revenues : 2020 = 1, 2021 = 100, 2022 = 200, 2023 = 400, 2024 = 800

        3-year window : (800 / 100) ** (1/3) - 1 = 8 ** (1/3) - 1 = 2 - 1 = 1.00
        whole period  : (800 /   1) ** (1/4) - 1 = 800 ** 0.25 - 1 ~= 4.32

    A test asserting only the 3-year answer on a fixture where the two coincide
    would not be able to tell them apart. Here, 1.00 and 4.32 differ by a factor
    of four.
    """
    assert config.DEFAULT_REVENUE_GROWTH_LOOKBACK_YEARS == 3

    financials = FinancialStatements(
        ticker="TEST",
        income_statements=[
            IncomeStatement(year=2020, revenue=1.0),
            IncomeStatement(year=2021, revenue=100.0),
            IncomeStatement(year=2022, revenue=200.0),
            IncomeStatement(year=2023, revenue=400.0),
            IncomeStatement(year=2024, revenue=800.0),
        ],
    )

    out = derive_assumptions(financials, ProjectionAssumptions(projection_years=2))

    assert out["revenue_growth_rates"] == [pytest.approx(1.0), pytest.approx(1.0)]


def test_a_shorter_history_shortens_the_lookback_window() -> None:
    """Two years of revenue give a one-period CAGR, not a three-period one.

    lookback = min(3, 2 - 1) = 1, so the CAGR runs 2023 -> 2024:

        (125 / 100) ** (1/1) - 1 = 1.25 - 1 = 0.25
    """
    financials = FinancialStatements(
        ticker="TEST",
        income_statements=[
            IncomeStatement(year=2023, revenue=100.0),
            IncomeStatement(year=2024, revenue=125.0),
        ],
    )

    out = derive_assumptions(financials, ProjectionAssumptions(projection_years=3))

    assert out["revenue_growth_rates"] == [pytest.approx(0.25)] * 3


# --------------------------------------------------------------------------
# derive_assumptions — the supplied-growth path, padding and truncation
# --------------------------------------------------------------------------


def test_a_short_growth_list_is_padded_with_its_last_rate() -> None:
    """Two supplied rates, four projection years.

    The documented behaviour is to extend the list to the projection horizon by
    repeating the final supplied rate, so [0.10, 0.20] over four years is
    [0.10, 0.20, 0.20, 0.20]. That is the only extension that adds no new
    assumption of its own.
    """
    out = derive_assumptions(
        _three_year_financials(),
        ProjectionAssumptions(projection_years=4, revenue_growth_rates=[0.10, 0.20]),
    )

    assert out["revenue_growth_rates"] == [
        pytest.approx(0.10),
        pytest.approx(0.20),
        pytest.approx(0.20),
        pytest.approx(0.20),
    ]


def test_a_long_growth_list_is_truncated_to_the_projection_horizon() -> None:
    """Five supplied rates, two projection years: only the first two are used."""
    out = derive_assumptions(
        _three_year_financials(),
        ProjectionAssumptions(
            projection_years=2,
            revenue_growth_rates=[0.10, 0.20, 0.30, 0.40, 0.50],
        ),
    )

    assert out["revenue_growth_rates"] == [pytest.approx(0.10), pytest.approx(0.20)]


# --------------------------------------------------------------------------
# derive_assumptions — the override path. A supplied 0.0 is a value.
# --------------------------------------------------------------------------


def test_supplied_overrides_reach_the_output_unchanged() -> None:
    """Every supplied figure passes through untouched.

    The fixture's derived answers are 0.30 / 0.20 / 0.20 / 0.15 / 0.04, so a
    pass-through failure on any of the five would show up as one of those
    numbers rather than as the number supplied. The tax rate of 0.33 is inside
    the [0, 0.50] band, so the clamp at `analysis/projector.py:65` cannot be what
    makes this pass.
    """
    out = derive_assumptions(
        _three_year_financials(),
        ProjectionAssumptions(
            projection_years=3,
            terminal_growth_rate=0.03,
            revenue_growth_rates=[0.08, 0.09, 0.10],
            operating_margin=0.42,
            tax_rate=0.33,
            da_pct_revenue=0.07,
            capex_pct_revenue=0.11,
            nwc_pct_revenue=0.02,
        ),
    )

    assert out["operating_margin"] == pytest.approx(0.42)
    assert out["tax_rate"] == pytest.approx(0.33)
    assert out["da_pct_revenue"] == pytest.approx(0.07)
    assert out["capex_pct_revenue"] == pytest.approx(0.11)
    assert out["nwc_pct_revenue"] == pytest.approx(0.02)
    assert out["projection_years"] == 3
    assert out["terminal_growth_rate"] == pytest.approx(0.03)
    assert out["revenue_growth_rates"] == [
        pytest.approx(0.08),
        pytest.approx(0.09),
        pytest.approx(0.10),
    ]


def test_a_supplied_operating_margin_of_zero_reaches_the_output() -> None:
    """A deliberate 0% operating margin is a value, not an absence.

    The fixture's historical average is 0.30. If the zero were read as "not
    supplied" the answer would be 0.30, so this assertion is falsifiable.
    `docs/4-conventions/units-and-signs.md` section 2: the test is
    `is not None`, never truthiness.
    """
    out = derive_assumptions(
        _three_year_financials(), ProjectionAssumptions(operating_margin=0.0)
    )
    assert out["operating_margin"] == 0.0


def test_a_supplied_tax_rate_of_zero_reaches_the_output() -> None:
    """A deliberate 0% tax rate is a value. The fixture's average is 0.20.

    Zero tax is not a hypothetical: a company with loss carry-forwards can pay
    none. The clamp `max(0.0, min(rate, 0.50))` leaves a supplied 0.0 at 0.0, so
    the clamp is not what this test is about.
    """
    out = derive_assumptions(
        _three_year_financials(), ProjectionAssumptions(tax_rate=0.0)
    )
    assert out["tax_rate"] == 0.0


def test_a_supplied_da_pct_of_zero_reaches_the_output() -> None:
    """A deliberate 0% D&A is a value. The fixture's average is 0.20."""
    out = derive_assumptions(
        _three_year_financials(), ProjectionAssumptions(da_pct_revenue=0.0)
    )
    assert out["da_pct_revenue"] == 0.0


def test_a_supplied_capex_pct_of_zero_reaches_the_output() -> None:
    """A deliberate 0% capex is a value. The fixture's average is 0.15."""
    out = derive_assumptions(
        _three_year_financials(), ProjectionAssumptions(capex_pct_revenue=0.0)
    )
    assert out["capex_pct_revenue"] == 0.0


def test_a_supplied_nwc_pct_of_zero_reaches_the_output() -> None:
    """A deliberate 0% working-capital drag is a value. The average is 0.04."""
    out = derive_assumptions(
        _three_year_financials(), ProjectionAssumptions(nwc_pct_revenue=0.0)
    )
    assert out["nwc_pct_revenue"] == 0.0


# --------------------------------------------------------------------------
# The delta-NWC sign, carried through to FCFF.
# --------------------------------------------------------------------------


def test_a_growing_working_capital_gives_a_positive_nwc_pct() -> None:
    """Derived from the CFS convention, not from reading the code.

    Working capital growing consumes cash, so the cash flow statement shows the
    change as **negative**: here -50 on a revenue of 1000. `nwc_pct_revenue` is
    defined as the share of revenue that working-capital growth *takes out* of
    free cash flow, so it must come out **positive**:

        nwc_pct = -(-50) / 1000 = +0.05
    """
    out = derive_assumptions(
        _one_year_financials(revenue=1000.0, change_in_working_capital=-50.0),
        _nwc_overrides(),
    )
    assert out["nwc_pct_revenue"] == pytest.approx(0.05)
    assert out["nwc_pct_revenue"] > 0


def test_a_released_working_capital_gives_a_negative_nwc_pct() -> None:
    """The other direction. Working capital shrinking *releases* cash.

    The cash flow statement shows the change as **positive**: +50 on a revenue
    of 1000. The drag on free cash flow is then negative — a boost:

        nwc_pct = -(+50) / 1000 = -0.05
    """
    out = derive_assumptions(
        _one_year_financials(revenue=1000.0, change_in_working_capital=50.0),
        _nwc_overrides(),
    )
    assert out["nwc_pct_revenue"] == pytest.approx(-0.05)
    assert out["nwc_pct_revenue"] < 0


def test_a_growing_working_capital_reduces_fcff_by_the_amount_it_grew() -> None:
    """The sign, at the only point where it matters.

    Three companies identical but for their working capital, each with revenue
    1000, a 20% operating margin, a 25% tax rate, D&A of 10% of revenue and
    capex of 5% of revenue, projected one year at 0% growth. Projected revenue
    is therefore 1000 in every case, and:

        EBIT  = 1000 * 0.20        = 200
        NOPAT = 200 * (1 - 0.25)   = 150
        D&A   = 1000 * 0.10        = 100
        capex = 1000 * 0.05        =  50

    so FCFF = 150 + 100 - 50 - delta_NWC = 200 - delta_NWC.

        working capital GREW by 50   (CFS -50)  -> nwc_pct +0.05
            delta_NWC = 1000 * +0.05 =  +50  ->  FCFF = 200 - 50 = 150
        working capital UNCHANGED    (CFS   0)  -> nwc_pct  0.00
            delta_NWC =                    0  ->  FCFF = 200 - 0  = 200
        working capital RELEASED 50  (CFS +50)  -> nwc_pct -0.05
            delta_NWC = 1000 * -0.05 =  -50  ->  FCFF = 200 + 50 = 250

    The requirement in one line: **cash tied up in working capital is cash the
    firm does not have, so growing working capital must LOWER free cash flow, by
    exactly the amount it grew.** Drop the negation at
    `analysis/projector.py:97` and the grown case becomes 250 and the released
    case 150 — both plausible share prices, in the wrong direction. Nothing else
    in this suite would notice.

    The unchanged case asserts a *measured* zero — a year whose working capital
    genuinely did not move — not a missing input. No fallback is asserted here.
    """
    grown = _one_year_financials(revenue=1000.0, change_in_working_capital=-50.0)
    flat = _one_year_financials(revenue=1000.0, change_in_working_capital=0.0)
    released = _one_year_financials(revenue=1000.0, change_in_working_capital=50.0)

    fcff_grown = project_fcffs(grown, derive_assumptions(grown, _nwc_overrides()))
    fcff_flat = project_fcffs(flat, derive_assumptions(flat, _nwc_overrides()))
    fcff_released = project_fcffs(
        released, derive_assumptions(released, _nwc_overrides())
    )

    assert fcff_grown[0].fcff == pytest.approx(150.0)
    assert fcff_flat[0].fcff == pytest.approx(200.0)
    assert fcff_released[0].fcff == pytest.approx(250.0)

    # Stated as the direction, so the test reads as the requirement it is.
    assert fcff_grown[0].fcff < fcff_flat[0].fcff
    assert fcff_released[0].fcff > fcff_flat[0].fcff
    assert fcff_flat[0].fcff - fcff_grown[0].fcff == pytest.approx(50.0)
    assert fcff_released[0].fcff - fcff_flat[0].fcff == pytest.approx(50.0)

    # And on the component the sign actually travels through.
    assert fcff_grown[0].change_in_working_capital == pytest.approx(50.0)
    assert fcff_released[0].change_in_working_capital == pytest.approx(-50.0)


# --------------------------------------------------------------------------
# project_fcffs
# --------------------------------------------------------------------------


def test_projected_revenue_compounds_year_on_year() -> None:
    """Revenue must compound, not grow off the base year each time.

    Starting revenue 100, flat growth of 10% over three years:

        2025 : 100   * 1.10 = 110.0
        2026 : 110   * 1.10 = 121.0
        2027 : 121   * 1.10 = 133.1

    A test asserting only the first year cannot see a compounding error: a
    version that applied the growth to the base revenue every year would give
    110, 110, 110 and would still pass year one.
    """
    financials = FinancialStatements(
        ticker="TEST",
        income_statements=[IncomeStatement(year=2024, revenue=100.0)],
    )
    assumptions = {
        "projection_years": 3,
        "revenue_growth_rates": [0.10, 0.10, 0.10],
        "operating_margin": 0.20,
        "tax_rate": 0.25,
        "da_pct_revenue": 0.10,
        "capex_pct_revenue": 0.05,
        "nwc_pct_revenue": 0.04,
    }

    projected = project_fcffs(financials, assumptions)

    assert len(projected) == 3
    assert [p.year for p in projected] == [2025, 2026, 2027]
    assert projected[0].revenue == pytest.approx(110.0)
    assert projected[1].revenue == pytest.approx(121.0)
    assert projected[2].revenue == pytest.approx(133.1)


def test_each_projection_year_uses_its_own_growth_rate() -> None:
    """The rate for year i must be `revenue_growth_rates[i]`.

        2025 : 100 * 1.20 = 120.0
        2026 : 120 * 1.10 = 132.0
        2027 : 132 * 1.00 = 132.0

    The rates are deliberately unequal and deliberately end in a zero: a
    version that reused the first rate would give 120, 144, 172.8, and one that
    treated the 0.0 as "no rate supplied" would not give 132 twice.
    """
    financials = FinancialStatements(
        ticker="TEST",
        income_statements=[IncomeStatement(year=2024, revenue=100.0)],
    )
    assumptions = {
        "projection_years": 3,
        "revenue_growth_rates": [0.20, 0.10, 0.0],
        "operating_margin": 0.20,
        "tax_rate": 0.25,
        "da_pct_revenue": 0.10,
        "capex_pct_revenue": 0.05,
        "nwc_pct_revenue": 0.04,
    }

    projected = project_fcffs(financials, assumptions)

    assert projected[0].revenue == pytest.approx(120.0)
    assert projected[1].revenue == pytest.approx(132.0)
    assert projected[2].revenue == pytest.approx(132.0)


def test_project_fcffs_worked_example_every_line_by_hand() -> None:
    """The whole projection for two years, derived before running anything.

    Starting revenue 1000, growth 10% a year, operating margin 20%, tax 25%,
    D&A 10% of revenue, capex 5% of revenue, delta-NWC 4% of revenue.

        2025  revenue    1000 * 1.10            = 1100.0
              EBIT       1100 * 0.20            =  220.0
              NOPAT       220 * (1 - 0.25)      =  165.0
              D&A        1100 * 0.10            =  110.0
              capex      1100 * 0.05            =   55.0
              delta_NWC  1100 * 0.04            =   44.0
              FCFF       165 + 110 - 55 - 44    =  176.0

        2026  revenue    1100 * 1.10            = 1210.0
              EBIT       1210 * 0.20            =  242.0
              NOPAT       242 * 0.75            =  181.5
              D&A        1210 * 0.10            =  121.0
              capex      1210 * 0.05            =   60.5
              delta_NWC  1210 * 0.04            =   48.4
              FCFF   181.5 + 121 - 60.5 - 48.4  =  193.6

    Cross-check, independent of the line-by-line arithmetic: every component is
    proportional to revenue, so FCFF must scale with revenue exactly —
    176.0 * 1.10 = 193.6.

    The projection years are the historical latest year plus one, plus two.
    """
    financials = FinancialStatements(
        ticker="TEST",
        income_statements=[IncomeStatement(year=2024, revenue=1000.0)],
    )
    assumptions = {
        "projection_years": 2,
        "revenue_growth_rates": [0.10, 0.10],
        "operating_margin": 0.20,
        "tax_rate": 0.25,
        "da_pct_revenue": 0.10,
        "capex_pct_revenue": 0.05,
        "nwc_pct_revenue": 0.04,
    }

    first, second = project_fcffs(financials, assumptions)

    assert first.year == 2025
    assert first.revenue == pytest.approx(1100.0)
    assert first.ebit == pytest.approx(220.0)
    assert first.nopat == pytest.approx(165.0)
    assert first.depreciation_amortization == pytest.approx(110.0)
    assert first.capital_expenditures == pytest.approx(55.0)
    assert first.change_in_working_capital == pytest.approx(44.0)
    assert first.fcff == pytest.approx(176.0)

    assert second.year == 2026
    assert second.revenue == pytest.approx(1210.0)
    assert second.ebit == pytest.approx(242.0)
    assert second.nopat == pytest.approx(181.5)
    assert second.depreciation_amortization == pytest.approx(121.0)
    assert second.capital_expenditures == pytest.approx(60.5)
    assert second.change_in_working_capital == pytest.approx(48.4)
    assert second.fcff == pytest.approx(193.6)

    assert second.fcff == pytest.approx(first.fcff * 1.10)


def test_derive_and_project_compose_on_the_three_year_fixture() -> None:
    """The two functions end to end, with the hand-derived assumptions carried in.

    From `_three_year_financials`: growth 1.00, margin 0.30, tax 0.20,
    D&A 0.20, capex 0.15, nwc 0.04, and the latest historical revenue is 400.

        2025  revenue    400 * (1 + 1.00)             = 800.0
              EBIT       800 * 0.30                   = 240.0
              NOPAT      240 * (1 - 0.20)             = 192.0
              D&A        800 * 0.20                   = 160.0
              capex      800 * 0.15                   = 120.0
              delta_NWC  800 * 0.04                   =  32.0
              FCFF       192 + 160 - 120 - 32         = 200.0
    """
    financials = _three_year_financials()
    assumptions = derive_assumptions(
        financials, ProjectionAssumptions(projection_years=1)
    )

    projected = project_fcffs(financials, assumptions)

    assert len(projected) == 1
    assert projected[0].year == 2025
    assert projected[0].revenue == pytest.approx(800.0)
    assert projected[0].nopat == pytest.approx(192.0)
    assert projected[0].fcff == pytest.approx(200.0)
