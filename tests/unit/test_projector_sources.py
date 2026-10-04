"""The provenance of the six projection ratios — `analysis/projector.py`'s `sources`.

Every expected value in this file was derived **by hand from the formula, before
`analysis/projector.py` was run**, and the arithmetic is written out above the
assertion that uses it. None of it came from executing the code, from a cached
`.pkl`, or from a number another test already asserts. This repository has no
benchmark (`docs/5-testing/strategy.md` section 1), so hand arithmetic and
closed-form identities are the only two sources available here — there is no
filing page involved, because nothing in this module reads a PDF.

What `P8a-statements-data` claims, and what this file checks independently:

1. A ratio that **no filing-year fed** is labelled SUBSTITUTED, not derived.
   Before the unit, a substituted zero was labelled "derived from the filing's
   history" (code reviewer finding F1).
2. A ratio that **was** fed names **how many** filing-years fed it, and that
   integer never overstates.
3. The clamp and the pad are clauses appended to one of the three origins, not
   a fourth origin.

**Two things this file deliberately does NOT assert.**

- It never asserts that a substituted ratio equals `0.0`. That zero is
  `analysis/projector.py:73`, `:91` and `:307` — backlog item 1 — and an
  assertion pinning it would turn its fix red. Where the substituted sentence
  has to be checked against the value it reports, the check is the *identity*
  "the sentence names the figure that was actually used", which holds whatever
  that figure is.
- It never asserts that a typed `0` reads as "not supplied". That is backlog
  item 6, and `tests/unit/test_projector.py` already pins the opposite — the
  correct behaviour — for all five overridable fields.
"""

from __future__ import annotations

import re
from dataclasses import MISSING, fields

import pytest

import config
from analysis.projector import derive_assumptions, project_fcffs
from models.financial_statements import (
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
)
from models.valuation import (
    ASSUMPTION_ORIGIN_DERIVED,
    ASSUMPTION_ORIGIN_SUBSTITUTED,
    ASSUMPTION_ORIGIN_SUPPLIED,
    ASSUMPTION_PADDED_CLAUSE_TEMPLATE,
    ASSUMPTION_SOURCE_SUPPLIED,
    ASSUMPTION_TRUNCATED_CLAUSE_TEMPLATE,
    AssumptionSource,
    ProjectionAssumptions,
)

# The six ratio keys the contract promises, written out here rather than read
# back off the returned dict, so that a key silently disappearing is a failure
# and not an empty loop.
SIX_RATIOS = (
    "revenue_growth_rates",
    "operating_margin",
    "tax_rate",
    "da_pct_revenue",
    "capex_pct_revenue",
    "nwc_pct_revenue",
)

# The eight keys that existed before this unit, plus the one key it added.
# Criterion 14: "add a key, change no existing key".
NINE_KEYS = {
    *SIX_RATIOS,
    "projection_years",
    "terminal_growth_rate",
    "sources",
}


# --------------------------------------------------------------------------
# Fixtures. Built by hand; no network, no key, no pickle.
# --------------------------------------------------------------------------


def _income_only_two_years() -> FinancialStatements:
    """Two complete income statements and **no cash flow statement at all**.

    This is the shape criterion 11 names, and the shape the code reviewer used
    to prove finding F1.

    year  revenue  COGS  EBIT  margin  interest_income  tax_exp  EBT  tax rate
    2023      100    80    20    0.20                0        4   20      0.20
    2024      200   140    60    0.30                0       18   60      0.30

    EBIT  = revenue - COGS; no other operating line is set.
    EBT   = EBIT, because no interest or non-operating line is set.

    By hand, from `analysis/projector.py:262-313`: `da_pcts`, `capex_pcts` and
    `nwc_pcts` are each built by a loop whose body runs only when
    `financials.get_cash_flow(y)` is truthy. `cash_flow_statements` is empty, so
    `get_cash_flow` returns `None` for both years
    (`models/financial_statements.py:290-291`), the body never runs, and all
    three lists are empty. **Nothing from the filing reaches those three
    ratios.**
    """
    return FinancialStatements(
        ticker="TEST",
        income_statements=[
            IncomeStatement(year=2023, revenue=100.0, cost_of_revenue=80.0, tax_expense=4.0),
            IncomeStatement(year=2024, revenue=200.0, cost_of_revenue=140.0, tax_expense=18.0),
        ],
    )


def _one_zero_margin_year() -> FinancialStatements:
    """Two complete years; 2023's operating margin and tax rate are exactly zero.

    year  revenue  COGS  EBIT  margin  int_income  EBT  tax_exp  tax rate
    2023      100   100     0    0.00          10   10        0      0.00
    2024      200   140    60    0.30           0   60       12      0.20

    2023's zeros are **measured**, not absent: a firm that broke even at the
    operating line and paid no tax. The interest income of 10 is there so that
    EBT is 10 rather than 0, which keeps the 0.00 tax rate a real division
    (0 / 10) rather than `IncomeStatement.effective_tax_rate`'s own
    `if self.ebt else 0.0` fallback at `models/financial_statements.py:101`.

    Cash flow statements, both years present:

    year  D&A  D&A%   capex  capex%   dWC   nwc%
    2023   10  0.10      -5    0.05    -2   +0.02
    2024   40  0.20     -30    0.15   -12   +0.06

    D&A% and capex% are the cash-flow figure over the same year's revenue, capex
    as a magnitude. nwc% is MINUS the cash-flow figure over revenue
    (`docs/4-conventions/units-and-signs.md` section 3).
    """
    return FinancialStatements(
        ticker="TEST",
        income_statements=[
            IncomeStatement(
                year=2023,
                revenue=100.0,
                cost_of_revenue=100.0,
                interest_income=10.0,
                tax_expense=0.0,
            ),
            IncomeStatement(year=2024, revenue=200.0, cost_of_revenue=140.0, tax_expense=12.0),
        ],
        cash_flow_statements=[
            CashFlowStatement(
                year=2023,
                depreciation_amortization=10.0,
                capital_expenditures=-5.0,
                change_in_working_capital=-2.0,
            ),
            CashFlowStatement(
                year=2024,
                depreciation_amortization=40.0,
                capital_expenditures=-30.0,
                change_in_working_capital=-12.0,
            ),
        ],
    )


def _one_zero_da_year() -> FinancialStatements:
    """Two complete years; 2023 reports D&A of exactly 0 and no change in WC.

    year  revenue  COGS  EBIT  margin  tax_exp  EBT  tax rate  D&A  D&A%  capex  capex%  dWC  nwc%
    2023      100    80    20    0.20        4   20      0.20    0  0.00     -5    0.05    0  0.00
    2024      200   140    60    0.30       18   60      0.30   40  0.20    -30    0.15  -12  0.06

    Exists to separate the **two different counting rules** the module applies,
    on one fixture where every other input is identical:

      * `_historical_average` (`:59-75`) drops zero values, so D&A counts 1 year.
      * the NWC branch (`:296-313`) takes a plain mean, so NWC counts 2 years.
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
                depreciation_amortization=0.0,
                capital_expenditures=-5.0,
                change_in_working_capital=0.0,
            ),
            CashFlowStatement(
                year=2024,
                depreciation_amortization=40.0,
                capital_expenditures=-30.0,
                change_in_working_capital=-12.0,
            ),
        ],
    )


def _one_year_above_the_tax_band() -> FinancialStatements:
    """A single year whose effective tax rate is 80%, outside the [0, 50%] band.

    revenue 100, COGS 90 -> EBIT 10; no interest line, so EBT = 10;
    tax_expense 8 -> effective tax rate = 8 / 10 = 0.80.

    A single filing year also makes the revenue CAGR window degenerate:
    `lookback = min(3, len([100]) - 1) = min(3, 0) = 0`, so
    `_historical_cagr(100, 100, 0)` hits its `periods <= 0` guard at `:90`.
    """
    return FinancialStatements(
        ticker="TEST",
        income_statements=[
            IncomeStatement(year=2024, revenue=100.0, cost_of_revenue=90.0, tax_expense=8.0),
        ],
    )


# --------------------------------------------------------------------------
# Helpers that state invariants, so each test asserts a requirement once.
# --------------------------------------------------------------------------


def _assert_source_is_self_consistent(source: AssumptionSource) -> None:
    """Closed-form identities every `AssumptionSource` must satisfy, whatever the inputs.

    They come from the definition in `models/valuation.py:120-137` and from the
    assignment's three-origin table, not from any run:

      * `origin` is exactly one of the three constants. A fourth would mean the
        clamp or the pad had become an origin, which round 2 forbids.
      * `observations >= 0`. A negative count of filing-years is meaningless.
      * `derived`      <=> `observations > 0`. That biconditional IS the unit:
        "derived" with nothing behind it is finding F1, and "substituted" with
        a year behind it throws away a real measurement.
      * `supplied` and `substituted` both carry `observations == 0`, because in
        neither case did a filing-year feed the figure.
      * `detail` is a non-empty sentence ending in a full stop. A blank label
        renders as a blank cell, which reads as "fine".
    """
    assert source.origin in {
        ASSUMPTION_ORIGIN_SUPPLIED,
        ASSUMPTION_ORIGIN_DERIVED,
        ASSUMPTION_ORIGIN_SUBSTITUTED,
    }
    assert source.observations >= 0
    assert (source.origin == ASSUMPTION_ORIGIN_DERIVED) == (source.observations > 0)
    if source.origin != ASSUMPTION_ORIGIN_DERIVED:
        assert source.observations == 0
    assert source.detail.strip()
    assert source.detail.rstrip().endswith(".")


def _sources(
    financials: FinancialStatements,
    overrides: ProjectionAssumptions | None = None,
) -> dict[str, AssumptionSource]:
    """Derive, check the contract on the whole dict, and hand back the labels."""
    out = derive_assumptions(financials, overrides)
    sources = out["sources"]
    # CONTRACT: exactly six entries, always the same six, never partial.
    assert set(sources) == set(SIX_RATIOS)
    for source in sources.values():
        _assert_source_is_self_consistent(source)
    return sources


# --------------------------------------------------------------------------
# 1. The substituted case — criterion 11.
# --------------------------------------------------------------------------


def test_the_three_cash_flow_ratios_are_substituted_when_no_cash_flow_was_extracted() -> None:
    """No cash flow statement means no observation, and the label must say so.

    Derived by hand from `analysis/projector.py:262-313`. Each of the three
    loops appends only when `financials.get_cash_flow(y)` is truthy;
    `cash_flow_statements` is empty, so that call returns `None` for 2023 and
    for 2024 and **all three lists stay empty**:

        da_pcts    = []   -> `_historical_average([])` -> observations 0
        capex_pcts = []   -> `_historical_average([])` -> observations 0
        nwc_pcts   = []   -> `_Derived(..., observations=len([]) == 0)`

    Zero observations is the definition of substituted, so all three must carry
    the substituted origin and the substituted sentence.

    **No assertion here pins the substituted VALUE.** That value is backlog
    item 1's `else 0.0`, and pinning it would turn its fix red. What is pinned
    instead is the identity that the sentence names whatever figure was in fact
    used, which holds for any default the fix might choose.
    """
    financials = _income_only_two_years()
    out = derive_assumptions(financials)
    sources = _sources(financials)

    for ratio in ("da_pct_revenue", "capex_pct_revenue", "nwc_pct_revenue"):
        source = sources[ratio]
        assert source.origin == ASSUMPTION_ORIGIN_SUBSTITUTED, ratio
        assert source.observations == 0, ratio
        # The two phrases the assignment requires a reader to be able to find.
        assert "SUBSTITUTED" in source.detail, ratio
        assert "It is not a measurement." in source.detail, ratio
        # Identity, not a pinned number: the sentence must name the figure that
        # was actually used in place of a derivation.
        assert f"{out[ratio]:.2%}" in source.detail, ratio
        # And it must not claim the filing fed it.
        assert "derived from the filing" not in source.detail, ratio


def test_a_degenerate_revenue_window_is_substituted_not_a_measured_flat_year() -> None:
    """One filing year gives no growth window, and 0% growth is then a SUBSTITUTION.

    By hand from `analysis/projector.py:182-184`: with one income statement,
    `lookback = min(3, 1 - 1) = 0`, so `_historical_cagr(100, 100, 0)` meets
    `periods <= 0` at `:90` and returns `observations = 0`.

    A 0% growth rate presented as measured is the same defect as a 0% D&A ratio
    presented as measured (round 2, step 6), so the label must read substituted
    even though the two revenue figures themselves were extracted.
    """
    sources = _sources(_one_year_above_the_tax_band())

    growth = sources["revenue_growth_rates"]
    assert growth.origin == ASSUMPTION_ORIGIN_SUBSTITUTED
    assert growth.observations == 0
    assert "SUBSTITUTED" in growth.detail
    assert "It is not a measurement." in growth.detail


def test_the_income_statement_ratios_are_still_derived_with_no_cash_flow_statement() -> None:
    """The income statement alone feeds three of the six, so those three are derived.

    From the same fixture, by hand:

        operating margins  2023: 20 / 100 = 0.20   2024: 60 / 200 = 0.30
        tax rates          2023:  4 /  20 = 0.20   2024: 18 /  60 = 0.30

    Neither is zero, so `_historical_average` drops neither and both count 2.
    The revenue CAGR has two endpoints, 100 and 200, so it counts 2 as well:

        lookback = min(3, 2 - 1) = 1
        (200 / 100) ** (1 / 1) - 1 = 2 - 1 = 1.00

    This is criterion 13 in its corrected form, and it is the case that breaks
    the criterion as first written: these three are rightly `derived` on a
    filing where **every** historical FCFF row is rightly not computable.
    """
    assert config.DEFAULT_REVENUE_GROWTH_LOOKBACK_YEARS == 3

    financials = _income_only_two_years()
    out = derive_assumptions(financials)
    sources = _sources(financials)

    for ratio in ("revenue_growth_rates", "operating_margin", "tax_rate"):
        assert sources[ratio].origin == ASSUMPTION_ORIGIN_DERIVED, ratio
        assert sources[ratio].observations == 2, ratio
        assert "2 filing-year(s)" in sources[ratio].detail, ratio

    # The values themselves, so a label that is right about a figure that is
    # wrong cannot pass. Averages of the two columns above.
    assert out["operating_margin"] == pytest.approx(0.25)  # (0.20 + 0.30) / 2
    assert out["tax_rate"] == pytest.approx(0.25)  # (0.20 + 0.30) / 2
    assert out["revenue_growth_rates"] == [pytest.approx(1.0)] * 5


# --------------------------------------------------------------------------
# 2. The observations count — criteria 12 and the counting rules.
# --------------------------------------------------------------------------


def test_a_year_whose_margin_is_zero_is_not_counted_as_an_observation() -> None:
    """`_historical_average` drops zeros, so the count is of the NON-ZERO values.

    From `_one_zero_margin_year`, by hand:

        operating margins  2023:   0 / 100 = 0.00   2024: 60 / 200 = 0.30
            non-zero list = [0.30]              -> 1 observation, mean 0.30
        tax rates          2023:   0 /  10 = 0.00   2024: 12 /  60 = 0.20
            non-zero list = [0.20]              -> 1 observation, mean 0.20

    **1, not 2.** Two filing-years were extracted and only one fed each average.
    A label saying "2 filing-year(s)" over a mean of one value is the defect
    this unit closed, in a smaller form.

    The three cash-flow ratios on the same fixture are unaffected, because both
    years have a cash flow statement and a positive revenue:

        D&A%    2023: 10 / 100 = 0.10   2024: 40 / 200 = 0.20  -> 2 obs, 0.15
        capex%  2023:  5 / 100 = 0.05   2024: 30 / 200 = 0.15  -> 2 obs, 0.10
        nwc%    2023:  2 / 100 = 0.02   2024: 12 / 200 = 0.06  -> 2 obs, 0.04

    So one call reports 1 for two ratios and 2 for three others, which no
    constant can satisfy.
    """
    financials = _one_zero_margin_year()
    out = derive_assumptions(financials)
    sources = _sources(financials)

    assert sources["operating_margin"].observations == 1
    assert sources["tax_rate"].observations == 1
    assert "1 filing-year(s)" in sources["operating_margin"].detail
    assert "1 filing-year(s)" in sources["tax_rate"].detail

    # The identity the count has to satisfy: the reported figure is the mean of
    # exactly the values that were counted. One observation means the figure IS
    # the single year's own ratio.
    assert out["operating_margin"] == pytest.approx(0.30)
    assert out["tax_rate"] == pytest.approx(0.20)

    assert sources["da_pct_revenue"].observations == 2
    assert sources["capex_pct_revenue"].observations == 2
    assert sources["nwc_pct_revenue"].observations == 2
    assert out["da_pct_revenue"] == pytest.approx(0.15)  # (0.10 + 0.20) / 2
    assert out["capex_pct_revenue"] == pytest.approx(0.10)  # (0.05 + 0.15) / 2
    assert out["nwc_pct_revenue"] == pytest.approx(0.04)  # (0.02 + 0.06) / 2


def test_the_count_never_exceeds_the_number_of_extracted_filing_years() -> None:
    """A closed-form bound, independent of any particular fixture.

    A ratio is an average over filing-years, so it cannot have been fed by more
    years than were extracted. The revenue CAGR is the one ratio that is not an
    average — it reads two endpoints — and two endpoints still cannot exceed the
    number of years present.

    Checked over all three complete fixtures at once, so a count computed from
    `projection_years` (5 by default) rather than from the data would fail on
    every one of them.
    """
    for financials in (
        _income_only_two_years(),
        _one_zero_margin_year(),
        _one_zero_da_year(),
        _one_year_above_the_tax_band(),
    ):
        year_count = len(financials.years)
        for ratio, source in _sources(financials).items():
            assert source.observations <= year_count, (ratio, year_count)


def test_da_drops_a_zero_year_and_nwc_keeps_it_on_the_same_two_years() -> None:
    """The two counting rules, separated on one fixture. Round 2, step 5.

    From `_one_zero_da_year`, both years complete, by hand:

        D&A%   2023:  0 / 100 = 0.00   2024: 40 / 200 = 0.20
            `_historical_average` drops the zero -> [0.20]
            -> 1 observation, mean 0.20
        nwc%   2023: -0 / 100 = 0.00   2024: 12 / 200 = 0.06
            the NWC branch takes a PLAIN mean, keeping the zero -> [0.00, 0.06]
            -> 2 observations, mean (0.00 + 0.06) / 2 = 0.03

    A reported zero working-capital change IS an observation — the filing said
    working capital did not move — whereas a reported zero D&A is dropped before
    the average, so only one year fed it. Whatever one thinks of the second
    rule, the label must report what the code did: 1 and 2, on the same two
    years.

    capex is a control: neither year is zero, so it counts 2.

        capex% 2023: 5 / 100 = 0.05   2024: 30 / 200 = 0.15 -> 2 obs, 0.10
    """
    financials = _one_zero_da_year()
    out = derive_assumptions(financials)
    sources = _sources(financials)

    assert sources["da_pct_revenue"].observations == 1
    assert out["da_pct_revenue"] == pytest.approx(0.20)

    assert sources["nwc_pct_revenue"].observations == 2
    assert out["nwc_pct_revenue"] == pytest.approx(0.03)

    assert sources["capex_pct_revenue"].observations == 2
    assert out["capex_pct_revenue"] == pytest.approx(0.10)


# --------------------------------------------------------------------------
# 3. The supplied origin.
# --------------------------------------------------------------------------


def test_every_supplied_ratio_is_labelled_supplied_with_no_observations() -> None:
    """A figure the caller typed was fed by zero filing-years, by definition.

    All six are overridden here, on a fixture whose derived answers are all
    different (0.25 / 0.25 / 0.15 / 0.10 / 0.04 on `_one_zero_margin_year`), so
    a label that fell through to the derived branch would be visible.

    The supplied tax rate of 0.33 is inside the [0, 50%] band, so no clamp
    clause can be what makes this pass.
    """
    sources = _sources(
        _one_zero_margin_year(),
        ProjectionAssumptions(
            projection_years=3,
            revenue_growth_rates=[0.08, 0.09, 0.10],
            operating_margin=0.42,
            tax_rate=0.33,
            da_pct_revenue=0.07,
            capex_pct_revenue=0.11,
            nwc_pct_revenue=0.02,
        ),
    )

    for ratio in SIX_RATIOS:
        assert sources[ratio].origin == ASSUMPTION_ORIGIN_SUPPLIED, ratio
        assert sources[ratio].observations == 0, ratio
        assert "supplied by the caller" in sources[ratio].detail, ratio
        # Rule 6: supplied is still an assumption, and the sentence has to say
        # so or a reader reads a typed figure as a measurement.
        assert "not a measurement" in sources[ratio].detail, ratio
        assert "SUBSTITUTED" not in sources[ratio].detail, ratio


# --------------------------------------------------------------------------
# 4. The clamp and the pad are clauses, not origins. Round 2, step 7.
# --------------------------------------------------------------------------


def test_a_derived_tax_rate_outside_the_band_stays_derived_and_names_the_clamp() -> None:
    """80% derived, 50% used, and the sentence names both.

    By hand from `_one_year_above_the_tax_band`:

        EBIT = 100 - 90 = 10; EBT = 10; effective tax rate = 8 / 10 = 0.80
        `_historical_average([0.80])` -> 1 observation, 0.80
        clamp: max(0.0, min(0.80, 0.50)) = 0.50

    The origin stays `derived` — one filing-year did feed it — and the clause
    is appended, because the clamp lands on a supplied figure and on a derived
    one alike. A clamped figure reported as plain "derived" would be a
    measurement the filing did not produce, so both figures must appear.
    """
    financials = _one_year_above_the_tax_band()
    out = derive_assumptions(financials)
    sources = _sources(financials)

    assert out["tax_rate"] == pytest.approx(0.50)

    tax = sources["tax_rate"]
    assert tax.origin == ASSUMPTION_ORIGIN_DERIVED
    assert tax.observations == 1
    assert "1 filing-year(s)" in tax.detail
    assert "CLAMPED" in tax.detail
    assert "80.00%" in tax.detail  # the figure that arrived
    assert "50.00%" in tax.detail  # the figure every calculation downstream used
    assert "0%" in tax.detail and "50%" in tax.detail  # the band


def test_a_supplied_tax_rate_outside_the_band_stays_supplied_and_names_the_clamp() -> None:
    """The same clause on a different origin, which is what makes it not an origin.

    Supplied 0.90 -> max(0.0, min(0.90, 0.50)) = 0.50. The label must still say
    the caller supplied it; only the clause is added.
    """
    financials = _one_zero_margin_year()
    out = derive_assumptions(financials, ProjectionAssumptions(tax_rate=0.90))
    sources = _sources(financials, ProjectionAssumptions(tax_rate=0.90))

    assert out["tax_rate"] == pytest.approx(0.50)

    tax = sources["tax_rate"]
    assert tax.origin == ASSUMPTION_ORIGIN_SUPPLIED
    assert tax.observations == 0
    assert "supplied by the caller" in tax.detail
    assert "CLAMPED" in tax.detail
    assert "90.00%" in tax.detail
    assert "50.00%" in tax.detail


def test_a_tax_rate_inside_the_band_carries_no_clamp_clause() -> None:
    """The control for the two above. 0.20 is inside [0, 50%], so nothing is said.

    `_one_zero_margin_year` derives a tax rate of 0.20 (one non-zero year, 2024,
    at 12 / 60). A clause appended unconditionally would report a clamp that did
    not happen, which is the same class of false claim as finding F1.
    """
    sources = _sources(_one_zero_margin_year())

    assert "CLAMPED" not in sources["tax_rate"].detail


def test_a_padded_growth_list_says_the_last_rate_was_repeated() -> None:
    """Two supplied rates over four projection years: the pad is this platform's.

    `tests/unit/test_projector.py` already pins the padded VALUES
    ([0.10, 0.20, 0.20, 0.20]). What is pinned here is that the label says the
    repeat happened, and names both numbers — 4 years reached by 2 rates. A
    reader shown four rates who was told only "supplied by the caller" would
    believe someone chose all four.
    """
    sources = _sources(
        _one_zero_margin_year(),
        ProjectionAssumptions(projection_years=4, revenue_growth_rates=[0.10, 0.20]),
    )

    growth = sources["revenue_growth_rates"]
    assert growth.origin == ASSUMPTION_ORIGIN_SUPPLIED
    assert "REPEATED" in growth.detail
    assert "4 year(s)" in growth.detail
    assert "2 rate(s)" in growth.detail


def test_a_complete_growth_list_carries_no_padded_clause() -> None:
    """The control. Three rates over three years need no repeat."""
    sources = _sources(
        _one_zero_margin_year(),
        ProjectionAssumptions(
            projection_years=3, revenue_growth_rates=[0.10, 0.20, 0.30]
        ),
    )

    assert "REPEATED" not in sources["revenue_growth_rates"].detail


def test_a_derived_growth_rate_carries_no_padded_clause() -> None:
    """The derived branch fills exactly `projection_years`, so it is never padded.

    From `analysis/projector.py:184`, `[cagr.value] * ov.projection_years` is
    already the right length, so `len(rev_growth) > rates_before_padding` is
    False. A clause here would tell a reader the platform repeated a rate it
    never repeated.
    """
    sources = _sources(
        _income_only_two_years(), ProjectionAssumptions(projection_years=7)
    )

    assert sources["revenue_growth_rates"].origin == ASSUMPTION_ORIGIN_DERIVED
    assert "REPEATED" not in sources["revenue_growth_rates"].detail


# --------------------------------------------------------------------------
# 4b. The truncation clause — backlog item 42, added by `P13b-tests`.
#
# Rule 6: the reader typed five numbers and must see that the valuation used
# two. Before `P13b-models-silent` the list was cut with no word in the label.
#
# The counts are fixed by the inputs each test writes: 5 rates typed, a 2-year
# projection, so 2 used and 5 - 2 = 3 dropped. The clause is checked against
# `ASSUMPTION_TRUNCATED_CLAUSE_TEMPLATE` (the wording contract in
# `models/valuation.py`) filled with those hand counts, and separately for the
# words a reader needs, so a template that lost a number would still fail.
#
# The two cases this note used to leave out — `projection_years` below 1, and
# whether `derive_assumptions` changes the caller's list — are now locked in
# section 4c below (backlog items 67 and 66, `P13e-tests`).
# --------------------------------------------------------------------------


def test_a_long_growth_list_uses_the_first_rates_and_says_the_rest_were_dropped() -> None:
    """Five supplied rates over two projection years.

    Rates used: the first two of [0.10, 0.20, 0.30, 0.40, 0.50] -> [0.10, 0.20].
    Label: supplied sentence + the truncation clause for 5 supplied, 2 used,
    5 - 2 = 3 dropped.
    """
    out = derive_assumptions(
        _one_zero_margin_year(),
        ProjectionAssumptions(
            projection_years=2,
            revenue_growth_rates=[0.10, 0.20, 0.30, 0.40, 0.50],
        ),
    )

    assert out["revenue_growth_rates"] == pytest.approx([0.10, 0.20])

    growth = out["sources"]["revenue_growth_rates"]
    _assert_source_is_self_consistent(growth)
    assert growth.origin == ASSUMPTION_ORIGIN_SUPPLIED
    assert growth.observations == 0

    expected_clause = ASSUMPTION_TRUNCATED_CLAUSE_TEMPLATE.format(
        supplied_years=5, projection_years=2, dropped_years=3
    )
    assert growth.detail == ASSUMPTION_SOURCE_SUPPLIED + expected_clause

    # The words a reader needs, independent of the template.
    assert "5 rate(s)" in growth.detail     # how many were typed
    assert "2 year(s)" in growth.detail     # how long the projection runs
    assert "first 2" in growth.detail       # which ones were used
    assert "last 3" in growth.detail        # how many were not
    assert "DROPPED" in growth.detail
    assert "REPEATED" not in growth.detail  # padding and truncation exclude each other


def test_a_growth_list_of_the_right_length_carries_no_truncation_clause() -> None:
    """Two supplied rates over two years: nothing cut, nothing repeated.

    The label is the supplied sentence and nothing appended.
    """
    out = derive_assumptions(
        _one_zero_margin_year(),
        ProjectionAssumptions(projection_years=2, revenue_growth_rates=[0.10, 0.20]),
    )

    assert out["revenue_growth_rates"] == pytest.approx([0.10, 0.20])
    growth = out["sources"]["revenue_growth_rates"]
    assert growth.detail == ASSUMPTION_SOURCE_SUPPLIED
    assert "DROPPED" not in growth.detail


def test_a_short_growth_list_keeps_the_pad_clause_and_has_no_truncation_clause() -> None:
    """One supplied rate over three years: the pad case, not the cut case.

    Rates used: 0.10, then 0.10 repeated twice -> [0.10, 0.10, 0.10].
    Label: supplied sentence + the pad clause for a 3-year projection reached
    by 1 rate, and no truncation clause.
    """
    out = derive_assumptions(
        _one_zero_margin_year(),
        ProjectionAssumptions(projection_years=3, revenue_growth_rates=[0.10]),
    )

    assert out["revenue_growth_rates"] == pytest.approx([0.10, 0.10, 0.10])
    growth = out["sources"]["revenue_growth_rates"]
    expected_pad = ASSUMPTION_PADDED_CLAUSE_TEMPLATE.format(
        projection_years=3, supplied_years=1
    )
    assert growth.detail == ASSUMPTION_SOURCE_SUPPLIED + expected_pad
    assert "REPEATED" in growth.detail
    assert "DROPPED" not in growth.detail


# --------------------------------------------------------------------------
# 4c. The caller's growth list, and a projection shorter than one year —
#     backlog items 66 and 67, added by `P13e-tests`.
#
# Item 66 (rule 6): the pad used to append to the caller's OWN list, so
# `[0.1]` with a 3-year projection became `[0.1, 0.1, 0.1]` in the caller's
# object, and a second call read the repeated rates as supplied and dropped
# the REPEATED clause.
#
# Item 67 (rule 3): `projection_years` was never checked. A value that cannot
# form a projection must stop and name the field.
#
# Every expected value below follows from the inputs the test writes and from
# the wording contract in `models/valuation.py`; none was read off a run. The
# stop tests assert the field name and the offending value, NOT the reason
# sentence: review F1 of `P13e-growth-input` says that sentence is wrong for a
# non-integer, and it may change.
# --------------------------------------------------------------------------


def test_the_callers_growth_list_is_the_same_object_and_unchanged_after_a_padded_call() -> None:
    """One supplied rate over three years: the pad must work on a copy.

    Input list `[0.1]`, 3 projection years. The pad repeats the last rate, so
    the rates USED are `[0.1, 0.1, 0.1]` (1 supplied + 2 repeats = 3). The
    caller's list must still be the object it handed in, holding `[0.1]` —
    one element, not three.
    """
    rates = [0.1]
    assumptions = ProjectionAssumptions(projection_years=3, revenue_growth_rates=rates)

    out = derive_assumptions(_one_zero_margin_year(), assumptions)

    # The caller's object: same identity, same one element.
    assert assumptions.revenue_growth_rates is rates
    assert rates == [0.1]
    assert len(rates) == 1

    # The padded list is a different object, so a later append to it cannot
    # reach the caller either.
    assert out["revenue_growth_rates"] is not rates
    assert out["revenue_growth_rates"] == pytest.approx([0.1, 0.1, 0.1])


def test_two_calls_with_the_same_assumptions_give_the_same_padded_growth_label() -> None:
    """The second call must not read the first call's repeats as supplied.

    Both calls see 1 supplied rate over 3 years, so both labels must be the
    supplied sentence plus the pad clause filled with (3 years, 1 rate). Before
    the fix the second call saw 3 "supplied" rates and carried no clause.
    """
    assumptions = ProjectionAssumptions(projection_years=3, revenue_growth_rates=[0.1])
    expected = ASSUMPTION_SOURCE_SUPPLIED + ASSUMPTION_PADDED_CLAUSE_TEMPLATE.format(
        projection_years=3, supplied_years=1
    )

    first = derive_assumptions(_one_zero_margin_year(), assumptions)
    second = derive_assumptions(_one_zero_margin_year(), assumptions)

    first_label = first["sources"]["revenue_growth_rates"].detail
    second_label = second["sources"]["revenue_growth_rates"].detail

    assert first_label == second_label
    assert first_label == expected
    assert "REPEATED" in first_label
    assert "REPEATED" in second_label
    assert "1 rate(s)" in second_label  # the second call still counts ONE supplied rate
    assert second["revenue_growth_rates"] == pytest.approx([0.1, 0.1, 0.1])


def _names_value(message: str, value: object) -> bool:
    """True when `repr(value)` appears in `message` as a whole token.

    A bare substring test would let `0` match inside `2.0` or `-1` inside
    `-10`; the lookarounds stop that, so the message has to name THIS value.
    A full stop straight after the value (the end of a sentence) is allowed;
    a full stop followed by a digit (a longer number) is not.
    """
    token = re.escape(repr(value))
    return re.search(rf"(?<![\w.\-]){token}(?!\w|\.\d)", message) is not None


@pytest.mark.parametrize(
    "projection_years",
    [0, -1, True, 2.0],
    ids=["zero", "minus_one", "bool_True", "float_2.0"],
)
def test_a_projection_years_that_is_not_an_integer_of_one_or_more_stops_and_names_it(
    projection_years: object,
) -> None:
    """0 and -1 form no projection; `True` and `2.0` are not year counts.

    The review of `P13e-growth-input` accepted refusing `True` (an `int` to
    Python, but not a count anyone typed) and `2.0` (not an integer). Each must
    raise `ValueError`, and the message must name the field and the value the
    caller passed, so a reader can find which input to correct.
    """
    with pytest.raises(ValueError) as caught:
        derive_assumptions(
            _one_zero_margin_year(),
            ProjectionAssumptions(projection_years=projection_years),  # type: ignore[arg-type]
        )

    message = str(caught.value)
    assert "projection_years" in message
    assert _names_value(message, projection_years), message


def test_the_projection_years_stop_comes_before_anything_is_read_from_the_filing() -> None:
    """The check runs before any rate is derived (assignment step 2).

    An extraction with no statements at all would otherwise fail later, on the
    revenue list. With `projection_years=0` the first stop a reader sees must
    be the one that names `projection_years`. This asserts nothing about what
    an empty extraction does with a valid year count — that case is the red
    test in `tests/unit/test_projector_rule3_red.py`.
    """
    with pytest.raises(ValueError) as caught:
        derive_assumptions(
            FinancialStatements(ticker="TEST"),
            ProjectionAssumptions(projection_years=0),
        )

    message = str(caught.value)
    assert "projection_years" in message
    assert _names_value(message, 0), message


def test_a_one_year_projection_still_projects_one_year() -> None:
    """The smallest valid value must still run, and run exactly once.

    Every ratio is supplied, so each figure is hand arithmetic on
    `_one_zero_margin_year`, whose latest year is 2024 with revenue 200:

        growth [0.10], 1 year      -> 1 rate used, no pad, no cut
        year     2024 + 1           = 2025
        revenue  200 * (1 + 0.10)   = 220
        EBIT     220 * 0.30         = 66
        NOPAT    66 * (1 - 0.20)    = 52.8
        D&A      220 * 0.10         = 22
        capex    220 * 0.05         = 11
        dNWC     220 * 0.05         = 11
        FCFF     52.8 + 22 - 11 - 11 = 52.8
    """
    financials = _one_zero_margin_year()
    out = derive_assumptions(
        financials,
        ProjectionAssumptions(
            projection_years=1,
            revenue_growth_rates=[0.10],
            operating_margin=0.30,
            tax_rate=0.20,
            da_pct_revenue=0.10,
            capex_pct_revenue=0.05,
            nwc_pct_revenue=0.05,
        ),
    )

    assert out["projection_years"] == 1
    assert out["revenue_growth_rates"] == pytest.approx([0.10])
    # One rate over one year: neither repeated nor dropped.
    assert out["sources"]["revenue_growth_rates"].detail == ASSUMPTION_SOURCE_SUPPLIED

    projected = project_fcffs(financials, out)

    assert len(projected) == 1
    (year_one,) = projected
    assert year_one.year == 2025
    assert year_one.revenue == pytest.approx(220.0)
    assert year_one.ebit == pytest.approx(66.0)
    assert year_one.nopat == pytest.approx(52.8)
    assert year_one.fcff == pytest.approx(52.8)


# --------------------------------------------------------------------------
# 5. The shape of the contract itself.
# --------------------------------------------------------------------------


def test_sources_is_an_added_key_and_nothing_else_moved() -> None:
    """Criterion 14, checked structurally: nine keys, eight of them pre-existing.

    The eight pre-existing keys are named in `derive_assumptions`' own docstring
    and read by name at `cli.py:733`, by `project_fcffs` and by
    `api/routes_valuation.py`. Their VALUES are pinned by hand in
    `tests/unit/test_projector.py`; what is pinned here is that no key was
    renamed or dropped to make room for `sources`.
    """
    out = derive_assumptions(_one_zero_margin_year())

    assert set(out) == NINE_KEYS


def test_assumption_source_defaults_nothing() -> None:
    """Every field required, per round 2 step 2 and rule 3.

    A field defaulting to `derived` would be finding F1 rebuilt: the claim a
    reader trusts least should never be the one that arrives for free. A source
    that cannot say which of the three origins produced its ratio must not be
    constructible at all.
    """
    for f in fields(AssumptionSource):
        assert f.default is MISSING, f.name
        assert f.default_factory is MISSING, f.name

    with pytest.raises(TypeError):
        AssumptionSource(origin=ASSUMPTION_ORIGIN_DERIVED)  # type: ignore[call-arg]


def test_the_three_origin_constants_are_distinct() -> None:
    """Three origins and no fourth, each distinguishable from the other two.

    If two of them compared equal, `origin == ASSUMPTION_ORIGIN_SUBSTITUTED`
    would be true of a derived ratio and every test above would still pass.
    """
    assert (
        len(
            {
                ASSUMPTION_ORIGIN_SUPPLIED,
                ASSUMPTION_ORIGIN_DERIVED,
                ASSUMPTION_ORIGIN_SUBSTITUTED,
            }
        )
        == 3
    )
