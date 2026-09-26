"""`_historical_fcff_by_year` — one row per extracted year, and the contradiction test.

Every expected figure below was computed by hand from the formula stated in
`analysis/fcff.py:54`

    FCFF = CFO + Interest_Expense * (1 - t) - CapEx

before anything was run, and the arithmetic is written out above the assertion.
There is no benchmark in this repository (`docs/5-testing/strategy.md` section
1), so nothing here came from the code's own output.

Two requirements are checked:

1. **A year whose income statement or cash flow statement is missing is not
   dropped.** `cli.py:721-722` drops it with a bare `continue` and a reader
   cannot tell a dropped year from a year that was never extracted. The row is
   carried through with `is_computable=False`, `fcff=None`, and the absent
   statement named.

2. **Criterion 13, in its CORRECTED wording.** The three ratios fed by the cash
   flow statement may never be labelled `derived` in a render where the FCFF
   table reports that no cash flow statement was extracted. The three fed by
   the income statement alone are under no such constraint — and the first test
   fixture below is precisely the case that breaks the criterion as it was
   first written.
"""

from __future__ import annotations

from dataclasses import MISSING, fields

import pytest

from analysis.projector import derive_assumptions
from api.routes_valuation import _historical_fcff_by_year
from models.financial_statements import (
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
)
from models.valuation import (
    ASSUMPTION_ORIGIN_DERIVED,
    ASSUMPTION_ORIGIN_SUBSTITUTED,
    HistoricalFCFFYear,
)

# The split criterion 13 turns on, taken from the corrected table in
# `.agent/assignments/P8a-statements-data.md`.
INCOME_STATEMENT_ONLY = ("revenue_growth_rates", "operating_margin", "tax_rate")
NEEDS_BOTH_STATEMENTS = ("da_pct_revenue", "capex_pct_revenue", "nwc_pct_revenue")


# --------------------------------------------------------------------------
# Fixtures, by hand.
# --------------------------------------------------------------------------


def _one_year_missing_its_cash_flow() -> FinancialStatements:
    """Two extracted years; only 2024 has a cash flow statement.

    2023 — income statement only:
        revenue 500, COGS 300 -> EBIT 200, operating margin 200 / 500 = 0.40
        no interest or non-operating line, so EBT = 200
        tax_expense 0 -> effective tax rate 0 / 200 = 0.00

    2024 — both statements:
        INCOME STATEMENT
            revenue                     1000
            cost of revenue              600
            SG&A                         100
            total operating expenses     700   = 600 + 100
            EBIT                         300   = 1000 - 700
            interest expense              50
            EBT                          250   = 300 - 50
            tax expense                   50
            effective tax rate          0.20   = 50 / 250   (inside [0, 50%],
                                                 so the clamp cannot move it)
        CASH FLOW STATEMENT
            net income                   200
            D&A                          100
            SBC                            0
            change in working capital    -40
            other operating                0
            CFO                          260   = 200 + 100 + 0 - 40 + 0
            capital expenditures         -60   -> magnitude 60

        FCFF = CFO + interest * (1 - t) - CapEx
             = 260 + 50 * (1 - 0.20) - 60
             = 260 + 40 - 60
             = 240.0

    The cash flow statement's net income of 200 agrees with the income
    statement's (EBT 250 - tax 50 = 200), so the fixture is a coherent filing
    and not an arbitrary bag of numbers.
    """
    return FinancialStatements(
        ticker="TEST",
        income_statements=[
            IncomeStatement(year=2023, revenue=500.0, cost_of_revenue=300.0),
            IncomeStatement(
                year=2024,
                revenue=1000.0,
                cost_of_revenue=600.0,
                sga=100.0,
                interest_expense=50.0,
                tax_expense=50.0,
            ),
        ],
        cash_flow_statements=[
            CashFlowStatement(
                year=2024,
                net_income=200.0,
                depreciation_amortization=100.0,
                change_in_working_capital=-40.0,
                capital_expenditures=-60.0,
            )
        ],
    )


def _no_cash_flow_at_all() -> FinancialStatements:
    """Two income statements, no cash flow statement. Criterion 11's shape.

    2023: revenue 100, COGS 80 -> EBIT 20, margin 0.20; tax 4 / EBT 20 = 0.20
    2024: revenue 200, COGS 140 -> EBIT 60, margin 0.30; tax 18 / EBT 60 = 0.30
    """
    return FinancialStatements(
        ticker="TEST",
        income_statements=[
            IncomeStatement(year=2023, revenue=100.0, cost_of_revenue=80.0, tax_expense=4.0),
            IncomeStatement(year=2024, revenue=200.0, cost_of_revenue=140.0, tax_expense=18.0),
        ],
    )


def _both_years_complete() -> FinancialStatements:
    """Two years, both statements present in both. Every row computable.

    2023  revenue 100, COGS 80 -> EBIT 20; tax 4 / EBT 20 = 0.20
          CFO = net income 16 + D&A 10 + dWC -2 = 24; capex -5
          FCFF = 24 + 0 * (1 - 0.20) - 5 = 19.0
    2024  revenue 200, COGS 140 -> EBIT 60; tax 18 / EBT 60 = 0.30
          CFO = net income 42 + D&A 40 + dWC -12 = 70; capex -30
          FCFF = 70 + 0 * (1 - 0.30) - 30 = 40.0

    Neither year reports an interest expense, so the after-tax interest add-back
    is 0 in both and FCFF is CFO minus capex. That is deliberate: it keeps this
    fixture's arithmetic trivially checkable, and the interest term is exercised
    by `_one_year_missing_its_cash_flow` above, where it is 40 of the 240.
    """
    return FinancialStatements(
        ticker="TEST",
        income_statements=[
            IncomeStatement(year=2023, revenue=100.0, cost_of_revenue=80.0, tax_expense=4.0),
            IncomeStatement(year=2024, revenue=200.0, cost_of_revenue=140.0, tax_expense=18.0),
        ],
        cash_flow_statements=[
            CashFlowStatement(
                year=2023,
                net_income=16.0,
                depreciation_amortization=10.0,
                change_in_working_capital=-2.0,
                capital_expenditures=-5.0,
            ),
            CashFlowStatement(
                year=2024,
                net_income=42.0,
                depreciation_amortization=40.0,
                change_in_working_capital=-12.0,
                capital_expenditures=-30.0,
            ),
        ],
    )


# --------------------------------------------------------------------------
# 1. The row per year.
# --------------------------------------------------------------------------


def test_a_year_without_a_cash_flow_statement_keeps_its_row_and_names_what_is_absent() -> None:
    """2023 is carried, not dropped, and says which statement was missing.

    `FinancialStatements.years` is built from the income statements
    (`models/financial_statements.py:276-282`), so both 2023 and 2024 are
    extracted years. 2023 has no cash flow statement, so `get_cash_flow(2023)`
    returns `None` and the year cannot produce an FCFF.

    The requirement is that it still appears, marked, with `fcff=None` — never
    a `HistoricalFCFF` full of zeros, because a zero meaning "we do not know"
    and a zero meaning "zero" are the same bytes (rule 3).
    """
    rows = _historical_fcff_by_year(_one_year_missing_its_cash_flow())

    assert [row.year for row in rows] == [2023, 2024]

    absent = rows[0]
    assert absent.year == 2023
    assert absent.is_computable is False
    assert absent.fcff is None
    assert absent.missing_statements == ("cash flow statement",)


def test_the_computable_year_reproduces_the_fcff_formula_by_hand() -> None:
    """2024 of the same fixture, every component derived above the assertion.

        interest add-back  50 * (1 - 0.20)      =  40.0
        CFO                200 + 100 + 0 - 40   = 260.0
        CapEx              |-60|                =  60.0
        FCFF               260 + 40 - 60        = 240.0

    Cross-check from a different direction, so the 240 is not one arithmetic
    path asserted twice: FCFF here is CFO less capex plus the after-tax
    interest, i.e. 260 - 60 = 200 of operating-less-investing cash, plus a 40
    financing add-back. 200 + 40 = 240.

    The tax rate is asserted too, because `calculate_fcff_historical` clamps it
    into [0, 50%] and a clamp firing here would silently change the add-back.
    0.20 is inside the band, so it must arrive unmoved.
    """
    rows = _historical_fcff_by_year(_one_year_missing_its_cash_flow())
    computed = rows[1]

    assert computed.year == 2024
    assert computed.is_computable is True
    assert computed.missing_statements == ()
    assert computed.fcff is not None

    fcff = computed.fcff
    assert fcff.year == 2024
    assert fcff.revenue == pytest.approx(1000.0)
    assert fcff.ebit == pytest.approx(300.0)  # 1000 - (600 + 100)
    assert fcff.tax_rate == pytest.approx(0.20)  # 50 / 250, unclamped
    assert fcff.cfo == pytest.approx(260.0)
    assert fcff.interest_expense == pytest.approx(50.0)
    assert fcff.after_tax_interest == pytest.approx(40.0)
    assert fcff.capital_expenditures == pytest.approx(60.0)  # a magnitude
    assert fcff.fcff == pytest.approx(240.0)


def test_both_complete_years_are_computable_and_match_hand_arithmetic() -> None:
    """From `_both_years_complete`, where the interest term is zero in both years.

        2023  CFO = 16 + 10 - 2 = 24;  capex 5;  FCFF = 24 + 0 - 5 = 19.0
        2024  CFO = 42 + 40 - 12 = 70; capex 30; FCFF = 70 + 0 - 30 = 40.0
    """
    rows = _historical_fcff_by_year(_both_years_complete())

    assert [row.year for row in rows] == [2023, 2024]
    assert all(row.is_computable for row in rows)
    assert all(row.missing_statements == () for row in rows)
    assert rows[0].fcff is not None
    assert rows[1].fcff is not None
    assert rows[0].fcff.fcff == pytest.approx(19.0)
    assert rows[1].fcff.fcff == pytest.approx(40.0)


def test_no_cash_flow_statement_means_every_row_is_carried_and_none_computable() -> None:
    """Both extracted years appear; neither can produce an FCFF; both say why."""
    rows = _historical_fcff_by_year(_no_cash_flow_at_all())

    assert [row.year for row in rows] == [2023, 2024]
    for row in rows:
        assert row.is_computable is False
        assert row.fcff is None
        assert row.missing_statements == ("cash flow statement",)


def test_an_empty_extraction_produces_no_rows_rather_than_a_zero_row() -> None:
    """No income statement means no extracted year, so there is nothing to report.

    An empty list is the honest answer here and it is not a fallback: a row
    invented for a year that was never extracted would be a fabrication. The
    distinction this asserts is "no rows" and not "a row of zeros".
    """
    assert _historical_fcff_by_year(FinancialStatements(ticker="TEST")) == []


def test_historical_fcff_year_defaults_nothing() -> None:
    """Rule 3 in the record itself: a row that cannot say whether its FCFF was
    computable must not be constructible.

    A default of `is_computable=True` would make a bare `HistoricalFCFFYear(year)`
    claim a computed figure it does not have; a default of `fcff=None` would let
    a row claim computable while carrying nothing.
    """
    for f in fields(HistoricalFCFFYear):
        assert f.default is MISSING, f.name
        assert f.default_factory is MISSING, f.name

    with pytest.raises(TypeError):
        HistoricalFCFFYear(year=2024)  # type: ignore[call-arg]


# --------------------------------------------------------------------------
# 2. Criterion 13, corrected wording: the page cannot contradict itself.
# --------------------------------------------------------------------------


def _assert_no_contradiction(financials: FinancialStatements) -> None:
    """The invariant, stated once and applied to every fixture in this file.

    `historical_fcff` reports, per year, whether the income statement AND the
    cash flow statement were both extracted. `da_pct_revenue`,
    `capex_pct_revenue` and `nwc_pct_revenue` need exactly that same pair
    (`analysis/projector.py:228-231`, `:243-246`, `:265-268`). So:

      * if one of those three is labelled `derived`, at least one year must be
        computable in the FCFF table — otherwise the same render says the cash
        flow statement both did and did not reach the platform;
      * and its `observations` can never exceed the number of computable years,
        because each observation needed a year with both statements. That bound
        is the sharper half: a count of 3 against 1 computable year is a
        contradiction that a mere "at least one" check would not see.

    The three income-statement-only ratios are deliberately NOT constrained
    here. `analysis/projector.py:189` and `:199` build them from income
    statements alone, so they can be rightly derived on a filing where every
    FCFF row is rightly not computable.
    """
    rows = _historical_fcff_by_year(financials)
    computable = sum(1 for row in rows if row.is_computable)
    sources = derive_assumptions(financials)["sources"]

    for ratio in NEEDS_BOTH_STATEMENTS:
        source = sources[ratio]
        if source.origin == ASSUMPTION_ORIGIN_DERIVED:
            assert computable >= 1, ratio
        assert source.observations <= computable, (ratio, computable)


def test_the_two_pages_agree_on_every_fixture_in_this_file() -> None:
    """The invariant over three shapes: no cash flow, one, and both.

    The fourth shape — an extraction with no income statements at all — is not
    here because `derive_assumptions` cannot be called on it: it raises a bare
    `IndexError` from `analysis/projector.py:162`, naming nothing. That is a
    rule 3 defect and it is stated as a requirement, red, in
    `tests/unit/test_projector_rule3_red.py`. It is deliberately NOT asserted
    in this file, because an `pytest.raises(IndexError)` here would lock the
    unnamed stop as the expected behaviour and turn its fix red.
    """
    _assert_no_contradiction(_no_cash_flow_at_all())
    _assert_no_contradiction(_one_year_missing_its_cash_flow())
    _assert_no_contradiction(_both_years_complete())


def test_no_cash_flow_statement_makes_the_bottom_three_substituted_and_the_top_three_derived() -> None:
    """Criterion 13's hard case, and the one the original wording got wrong.

    On `_no_cash_flow_at_all` every FCFF row is not computable, so the three
    cash-flow-fed ratios must be `substituted`. The three income-statement-fed
    ratios are nonetheless `derived`, because the income statements really were
    extracted:

        operating margins  0.20 and 0.30 -> 2 observations
        tax rates          0.20 and 0.30 -> 2 observations
        revenue CAGR       (200 / 100) ** (1 / 1) - 1 = 1.00, two endpoints -> 2

    A test written to the original criterion — "every ratio labelled derived has
    a computable historical_fcff row" — goes RED here against correct code.
    """
    financials = _no_cash_flow_at_all()
    rows = _historical_fcff_by_year(financials)
    sources = derive_assumptions(financials)["sources"]

    assert not any(row.is_computable for row in rows)

    for ratio in NEEDS_BOTH_STATEMENTS:
        assert sources[ratio].origin == ASSUMPTION_ORIGIN_SUBSTITUTED, ratio

    for ratio in INCOME_STATEMENT_ONLY:
        assert sources[ratio].origin == ASSUMPTION_ORIGIN_DERIVED, ratio
        assert sources[ratio].observations == 2, ratio


def test_one_computable_year_lets_the_bottom_three_claim_exactly_one_observation() -> None:
    """The middle case: half the cash flow statements are there.

    On `_one_year_missing_its_cash_flow` only 2024 has both statements, so each
    of the three cash-flow-fed ratios is fed by exactly one filing-year:

        D&A%    100 / 1000 = 0.10
        capex%   60 / 1000 = 0.06
        nwc%    -(-40) / 1000 = 0.04

    and the FCFF table reports exactly one computable year. One and one agree.

    The income-statement ratios count differently on the same filing, which is
    what makes this more than a restatement of the row count:

        operating margins  2023: 200 / 500 = 0.40   2024: 300 / 1000 = 0.30
            neither is zero -> 2 observations, mean 0.35
        tax rates          2023:   0 / 200 = 0.00   2024:  50 /  250 = 0.20
            the zero is dropped by `_historical_average` -> 1 observation, 0.20
    """
    financials = _one_year_missing_its_cash_flow()
    rows = _historical_fcff_by_year(financials)
    out = derive_assumptions(financials)
    sources = out["sources"]

    assert sum(1 for row in rows if row.is_computable) == 1

    for ratio in NEEDS_BOTH_STATEMENTS:
        assert sources[ratio].origin == ASSUMPTION_ORIGIN_DERIVED, ratio
        assert sources[ratio].observations == 1, ratio

    assert out["da_pct_revenue"] == pytest.approx(0.10)
    assert out["capex_pct_revenue"] == pytest.approx(0.06)
    assert out["nwc_pct_revenue"] == pytest.approx(0.04)

    assert sources["operating_margin"].observations == 2
    assert out["operating_margin"] == pytest.approx(0.35)  # (0.40 + 0.30) / 2
    assert sources["tax_rate"].observations == 1
    assert out["tax_rate"] == pytest.approx(0.20)
