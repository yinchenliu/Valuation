"""Project future financial statements based on historical data and assumptions.

Derives default assumptions from historical averages, but allows user overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

import numpy as np

import config
from analysis.fcff import calculate_fcff_projected
from models.financial_statements import FinancialStatements, IncomeStatement
from models.valuation import (
    ASSUMPTION_CLAMPED_CLAUSE_TEMPLATE,
    ASSUMPTION_ORIGIN_DERIVED,
    ASSUMPTION_ORIGIN_SUBSTITUTED,
    ASSUMPTION_ORIGIN_SUPPLIED,
    ASSUMPTION_PADDED_CLAUSE_TEMPLATE,
    ASSUMPTION_SOURCE_DERIVED_TEMPLATE,
    ASSUMPTION_SOURCE_SUBSTITUTED_TEMPLATE,
    ASSUMPTION_SOURCE_SUPPLIED,
    ASSUMPTION_TRUNCATED_CLAUSE_TEMPLATE,
    AssumptionSource,
    ProjectedFCFF,
    ProjectionAssumptions,
)

# The band this platform imposes on the effective tax rate, named once so the
# clamp below and the sentence that reports the clamp cannot drift apart. The
# figures are the ones that were already inline at the clamp; naming them
# moves nothing.
_TAX_RATE_FLOOR: Final = 0.0
_TAX_RATE_CEILING: Final = 0.50


@dataclass(frozen=True)
class _Derived:
    """A ratio, and the number of filing-years that fed it.

    `observations == 0` means nothing in the filing reached it, so `value` is
    a substituted default and not a measurement.

    **The count is produced here, where the list is built.** By the time a
    ratio is returned the evidence is gone: `da_pcts` is a local list and no
    caller can see whether it was empty. A label computed in the route could
    only re-derive the condition, which is one fact living in two files
    (backlog item 7), and round 1 of `P8a-statements-data` showed what happens
    when the caller guesses instead — it asserted "derived from the filing's
    history" over three substituted zeros (code reviewer finding F1).
    """

    value: float
    observations: int


def _historical_average(values: list[float]) -> _Derived:
    """Average of non-zero values, with the count of values that fed it.

    The `else 0.0` is backlog item 1 and is deliberately left where it is:
    this unit may not move a figure. What is new is that the caller is now
    TOLD the average had nothing behind it — `observations == 0` — instead of
    receiving a 0.0 indistinguishable from a measured zero.

    Zero values are dropped before the average, as they always were, so the
    count is the length of the non-zero list and not of `values`. A year that
    reported a zero fed nothing.
    """
    non_zero = [v for v in values if v != 0]
    return _Derived(
        value=float(np.mean(non_zero)) if non_zero else 0.0,
        observations=len(non_zero),
    )


def _historical_cagr(first: float, last: float, periods: int) -> _Derived:
    """Compound annual growth rate, with the count of filing-years behind it.

    Two revenue figures feed a CAGR — the first year of the window and the
    last — so a computed CAGR reports **2** observations however wide the
    window is. The years between the endpoints feed nothing and are not
    counted.

    The guard returns 0.0 on a non-positive or degenerate window, exactly as
    before. That 0.0 is a SUBSTITUTION and not a measured flat year, and
    `observations == 0` is what says so.
    """
    if first <= 0 or last <= 0 or periods <= 0:
        return _Derived(value=0.0, observations=0)
    return _Derived(value=(last / first) ** (1 / periods) - 1, observations=2)


def _income_statements_for_years(
    financials: FinancialStatements,
    years: list[int],
) -> list[IncomeStatement]:
    """The income statement of each year in `years`, in the order given.

    Stops and names the field and the year when a year in `years` has none.

    Since `P3d-invisible-year`, `FinancialStatements.years` covers every year
    any of the three statements reaches, so a year in it can have a cash flow
    statement and a balance sheet and no income statement (backlog item 116).
    Three of this module's ratios read `revenue`, `operating_margin` and
    `effective_tax_rate` off the income statement of EVERY year, and a
    projection cannot be built from a year with no revenue.

    The two cheap answers are both wrong and are both refused here:
    `financials.get_income_statement(y).revenue` is `AttributeError:
    'NoneType' object has no attribute 'revenue'`, which names no field and no
    year and which the blanket `except Exception` in both entry points renders
    as a string on the results page; and skipping the year silently drops a
    year the filing covers out of the growth window, which moves the growth
    rate with nothing saying so. Rule 3: stop, and name the field.
    """
    statements: list[IncomeStatement] = []
    for year in years:
        income = financials.get_income_statement(year)
        if income is None:
            raise ValueError(
                f"revenue is not available for fiscal year {year}: "
                f"{financials.ticker!r} has no income statement for it, so "
                f"revenue, operating_margin and effective_tax_rate cannot be "
                f"read for that year and a projection cannot be built from "
                f"it. The extracted years are {years}; the years with an "
                f"income statement are {financials.income_statement_years}. "
                f"No figure is substituted for fiscal year {year} and it is "
                f"not dropped from the window either, because dropping it "
                f"would move the growth rate with nothing saying so. Extract "
                f"the income statement for fiscal year {year}."
            )
        statements.append(income)
    return statements


def _source_supplied() -> AssumptionSource:
    """The caller gave this figure. No filing-year fed it, so 0 observations."""
    return AssumptionSource(
        origin=ASSUMPTION_ORIGIN_SUPPLIED,
        detail=ASSUMPTION_SOURCE_SUPPLIED,
        observations=0,
    )


def _source_for(derived: _Derived) -> AssumptionSource:
    """Label a computed ratio: derived when something fed it, substituted when nothing did.

    The whole point of the three-state scheme is this one branch. A ratio with
    no observation behind it carries the default's own value, and saying so is
    rule 6: an assumption that is not labelled as one is indistinguishable
    from a measurement.
    """
    if derived.observations == 0:
        return AssumptionSource(
            origin=ASSUMPTION_ORIGIN_SUBSTITUTED,
            detail=ASSUMPTION_SOURCE_SUBSTITUTED_TEMPLATE.format(
                default_value=f"{derived.value:.2%}"
            ),
            observations=0,
        )
    return AssumptionSource(
        origin=ASSUMPTION_ORIGIN_DERIVED,
        detail=ASSUMPTION_SOURCE_DERIVED_TEMPLATE.format(
            observations=derived.observations
        ),
        observations=derived.observations,
    )


def derive_assumptions(
    financials: FinancialStatements,
    overrides: ProjectionAssumptions | None = None,
) -> dict:
    """Derive projection assumptions from historical financials.

    Returns a dict with keys: revenue_growth_rates, operating_margin, tax_rate,
    da_pct_revenue, capex_pct_revenue, nwc_pct_revenue, projection_years,
    terminal_growth_rate, **sources**.

    `sources` is a `dict[str, AssumptionSource]` under the same six ratio keys
    — `revenue_growth_rates`, `operating_margin`, `tax_rate`, `da_pct_revenue`,
    `capex_pct_revenue`, `nwc_pct_revenue` — saying for each whether the caller
    supplied it, how many filing-years derived it, or that nothing fed it and a
    default was substituted. Rule 6.

    **It is an added key. No existing key and no existing value moved**, because
    `cli.py:733`, `project_fcffs` and `api/routes_valuation.py` all read this
    dict by name and an added key breaks none of them.
    """
    ov = overrides or ProjectionAssumptions()

    # A projection shorter than one year has no cash flow to discount, and the
    # growth label below would describe years that never run. Stop and name the
    # field before any rate is derived. Rule 3; backlog item 67. A bool is
    # refused too: `True` is an int to Python, but it is not a year count anyone
    # typed.
    if (
        isinstance(ov.projection_years, bool)
        or not isinstance(ov.projection_years, int)
        or ov.projection_years < 1
    ):
        raise ValueError(
            f"projection_years must be an integer of 1 or more; got "
            f"{ov.projection_years!r}. A projection shorter than one year has "
            f"no cash flow to discount."
        )

    # Every year any statement covers, since `P3d-invisible-year`. The three
    # ratios below need the income statement of each one, so they are fetched
    # once, through a call that STOPS and names the field and the year when a
    # covered year has none (backlog item 116). Reading
    # `financials.income_statement_years` here instead would drop such a year
    # out of the growth window in silence, which moves the derived growth rate.
    years = financials.years
    income_statements = _income_statements_for_years(financials, years)

    sources: dict[str, AssumptionSource] = {}

    # --- Revenue growth ---
    revenues = [income.revenue for income in income_statements]
    if ov.revenue_growth_rates:
        # A copy: the padding below appends, and appending to the caller's own
        # list would make a second call read the repeated rates as supplied and
        # drop the REPEATED clause. Rule 6; backlog item 66.
        rev_growth = list(ov.revenue_growth_rates)
        growth_source = _source_supplied()
    else:
        # Use a rolling lookback window to avoid distortion from one-off macro events
        # (e.g. 2020 COVID trough inflating the full-period CAGR).
        lookback = min(config.DEFAULT_REVENUE_GROWTH_LOOKBACK_YEARS, len(revenues) - 1)
        cagr = _historical_cagr(revenues[-1 - lookback], revenues[-1], lookback)
        rev_growth = [cagr.value] * ov.projection_years
        growth_source = _source_for(cagr)

    # Pad or truncate to match projection_years
    rates_before_padding = len(rev_growth)
    while len(rev_growth) < ov.projection_years:
        rev_growth.append(rev_growth[-1] if rev_growth else 0.05)
    rev_growth = rev_growth[: ov.projection_years]

    # A repeated rate is this platform's figure, not the caller's and not the
    # filing's, so the label has to say so or the years after the first read
    # as though someone chose them. Rule 6. (The derived branch above already
    # fills exactly `projection_years`, so in practice only a short supplied
    # list is padded; the clause is worded for either.)
    if len(rev_growth) > rates_before_padding:
        growth_source = replace(
            growth_source,
            detail=growth_source.detail
            + ASSUMPTION_PADDED_CLAUSE_TEMPLATE.format(
                projection_years=len(rev_growth),
                supplied_years=rates_before_padding,
            ),
        )

    # A cut list needs the same candour as a padded one. The reader typed
    # more rates than the projection uses, and the label has to say which
    # ones reached a figure or the dropped ones read as applied. Rule 6;
    # backlog item 42.
    if rates_before_padding > len(rev_growth):
        growth_source = replace(
            growth_source,
            detail=growth_source.detail
            + ASSUMPTION_TRUNCATED_CLAUSE_TEMPLATE.format(
                supplied_years=rates_before_padding,
                projection_years=len(rev_growth),
                dropped_years=rates_before_padding - len(rev_growth),
            ),
        )
    sources["revenue_growth_rates"] = growth_source

    # --- Operating margin ---
    op_margins = [income.operating_margin for income in income_statements]
    if ov.operating_margin is not None:
        operating_margin = ov.operating_margin
        sources["operating_margin"] = _source_supplied()
    else:
        margin_derived = _historical_average(op_margins)
        operating_margin = margin_derived.value
        sources["operating_margin"] = _source_for(margin_derived)

    # --- Tax rate ---
    tax_rates = [income.effective_tax_rate for income in income_statements]
    if ov.tax_rate is not None:
        pre_clamp_tax_rate = ov.tax_rate
        tax_source = _source_supplied()
    else:
        tax_derived = _historical_average(tax_rates)
        pre_clamp_tax_rate = tax_derived.value
        tax_source = _source_for(tax_derived)
    tax_rate = max(_TAX_RATE_FLOOR, min(pre_clamp_tax_rate, _TAX_RATE_CEILING))

    # The clamp is not a fourth origin: it lands on a supplied figure and on a
    # derived one alike. But a clamped figure reported as derived is a
    # measurement the filing did not produce, so when it moves the value the
    # sentence names both the figure that arrived and the band that moved it.
    if tax_rate != pre_clamp_tax_rate:
        tax_source = replace(
            tax_source,
            detail=tax_source.detail
            + ASSUMPTION_CLAMPED_CLAUSE_TEMPLATE.format(
                low=f"{_TAX_RATE_FLOOR:.0%}",
                high=f"{_TAX_RATE_CEILING:.0%}",
                pre_clamp=f"{pre_clamp_tax_rate:.2%}",
                post_clamp=f"{tax_rate:.2%}",
            ),
        )
    sources["tax_rate"] = tax_source

    # --- D&A as % of revenue ---
    da_pcts = []
    for y in years:
        cf = financials.get_cash_flow(y)
        inc = financials.get_income_statement(y)
        if cf and inc and inc.revenue > 0:
            da_pcts.append(cf.depreciation_amortization / inc.revenue)
    if ov.da_pct_revenue is not None:
        da_pct = ov.da_pct_revenue
        sources["da_pct_revenue"] = _source_supplied()
    else:
        da_derived = _historical_average(da_pcts)
        da_pct = da_derived.value
        sources["da_pct_revenue"] = _source_for(da_derived)

    # --- CapEx as % of revenue ---
    capex_pcts = []
    for y in years:
        cf = financials.get_cash_flow(y)
        inc = financials.get_income_statement(y)
        if cf and inc and inc.revenue > 0:
            capex_pcts.append(abs(cf.capital_expenditures) / inc.revenue)
    if ov.capex_pct_revenue is not None:
        capex_pct = ov.capex_pct_revenue
        sources["capex_pct_revenue"] = _source_supplied()
    else:
        capex_derived = _historical_average(capex_pcts)
        capex_pct = capex_derived.value
        sources["capex_pct_revenue"] = _source_for(capex_derived)

    # --- NWC change as % of revenue (from CFS "Changes in assets and liabilities") ---
    # CFS convention: negative = WC increase (cash outflow).
    # We negate so nwc_pct is positive when WC grows (outflow that reduces FCFF).
    nwc_pct = 0.0
    if ov.nwc_pct_revenue is not None:
        nwc_pct = ov.nwc_pct_revenue
        sources["nwc_pct_revenue"] = _source_supplied()
    else:
        nwc_pcts = []
        for y in years:
            cf = financials.get_cash_flow(y)
            inc = financials.get_income_statement(y)
            if cf and inc and inc.revenue > 0:
                nwc_pcts.append(-cf.change_in_working_capital / inc.revenue)
        # Use plain average (not _historical_average) — zero WC change is valid
        nwc_pct = float(np.mean(nwc_pcts)) if nwc_pcts else 0.0
        # So the observation count is the length of the whole list, not of a
        # non-zero subset: here a reported zero IS an observation.
        sources["nwc_pct_revenue"] = _source_for(
            _Derived(value=nwc_pct, observations=len(nwc_pcts))
        )

    return {
        "revenue_growth_rates": rev_growth,
        "operating_margin": operating_margin,
        "tax_rate": tax_rate,
        "da_pct_revenue": da_pct,
        "capex_pct_revenue": capex_pct,
        "nwc_pct_revenue": nwc_pct,
        "projection_years": ov.projection_years,
        "terminal_growth_rate": ov.terminal_growth_rate,
        # Added at round 2 of P8a-statements-data. Six keys, always the same
        # six, whatever produced the ratios.
        "sources": sources,
    }


def project_fcffs(
    financials: FinancialStatements,
    assumptions: dict,
) -> list[ProjectedFCFF]:
    """Generate projected FCFFs for each forecast year.

    Args:
        financials: Historical financial statements.
        assumptions: Dict from derive_assumptions().

    Returns:
        List of ProjectedFCFF for each projection year.
    """
    latest_year = financials.latest_year
    latest_is = financials.get_income_statement(latest_year)

    last_revenue = latest_is.revenue

    projected = []
    for i in range(assumptions["projection_years"]):
        year = latest_year + i + 1
        growth = assumptions["revenue_growth_rates"][i]
        revenue = last_revenue * (1 + growth)

        fcff = calculate_fcff_projected(
            year=year,
            revenue=revenue,
            operating_margin=assumptions["operating_margin"],
            tax_rate=assumptions["tax_rate"],
            da_pct_revenue=assumptions["da_pct_revenue"],
            capex_pct_revenue=assumptions["capex_pct_revenue"],
            nwc_pct_revenue=assumptions["nwc_pct_revenue"],
        )
        projected.append(fcff)

        last_revenue = revenue

    return projected
