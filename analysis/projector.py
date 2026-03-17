"""Project future financial statements based on historical data and assumptions.

Derives default assumptions from historical averages, but allows user overrides.
"""

from __future__ import annotations

import numpy as np

import config
from analysis.fcff import calculate_fcff_projected
from models.financial_statements import FinancialStatements
from models.valuation import ProjectedFCFF, ProjectionAssumptions


def _historical_average(values: list[float]) -> float:
    """Average of non-zero values."""
    non_zero = [v for v in values if v != 0]
    return float(np.mean(non_zero)) if non_zero else 0.0


def _historical_cagr(first: float, last: float, periods: int) -> float:
    """Compound annual growth rate."""
    if first <= 0 or last <= 0 or periods <= 0:
        return 0.0
    return (last / first) ** (1 / periods) - 1


def derive_assumptions(
    financials: FinancialStatements,
    overrides: ProjectionAssumptions | None = None,
) -> dict:
    """Derive projection assumptions from historical financials.

    Returns a dict with keys: revenue_growth_rates, operating_margin, tax_rate,
    da_pct_revenue, capex_pct_revenue, nwc_pct_revenue, projection_years,
    terminal_growth_rate.
    """
    ov = overrides or ProjectionAssumptions()
    years = financials.years

    # --- Revenue growth ---
    revenues = [financials.get_income_statement(y).revenue for y in years]
    if ov.revenue_growth_rates:
        rev_growth = ov.revenue_growth_rates
    else:
        # Use a rolling lookback window to avoid distortion from one-off macro events
        # (e.g. 2020 COVID trough inflating the full-period CAGR).
        lookback = min(config.DEFAULT_REVENUE_GROWTH_LOOKBACK_YEARS, len(revenues) - 1)
        cagr = _historical_cagr(revenues[-1 - lookback], revenues[-1], lookback)
        rev_growth = [cagr] * ov.projection_years

    # Pad or truncate to match projection_years
    while len(rev_growth) < ov.projection_years:
        rev_growth.append(rev_growth[-1] if rev_growth else 0.05)
    rev_growth = rev_growth[: ov.projection_years]

    # --- Operating margin ---
    op_margins = [financials.get_income_statement(y).operating_margin for y in years]
    operating_margin = ov.operating_margin if ov.operating_margin is not None else _historical_average(op_margins)

    # --- Tax rate ---
    tax_rates = [financials.get_income_statement(y).effective_tax_rate for y in years]
    tax_rate = ov.tax_rate if ov.tax_rate is not None else _historical_average(tax_rates)
    tax_rate = max(0.0, min(tax_rate, 0.50))

    # --- D&A as % of revenue ---
    da_pcts = []
    for y in years:
        cf = financials.get_cash_flow(y)
        inc = financials.get_income_statement(y)
        if cf and inc and inc.revenue > 0:
            da_pcts.append(cf.depreciation_amortization / inc.revenue)
    da_pct = ov.da_pct_revenue if ov.da_pct_revenue is not None else _historical_average(da_pcts)

    # --- CapEx as % of revenue ---
    capex_pcts = []
    for y in years:
        cf = financials.get_cash_flow(y)
        inc = financials.get_income_statement(y)
        if cf and inc and inc.revenue > 0:
            capex_pcts.append(abs(cf.capital_expenditures) / inc.revenue)
    capex_pct = ov.capex_pct_revenue if ov.capex_pct_revenue is not None else _historical_average(capex_pcts)

    # --- NWC as % of revenue ---
    nwc_pcts = []
    for y in years:
        bs = financials.get_balance_sheet(y)
        inc = financials.get_income_statement(y)
        if bs and inc and inc.revenue > 0:
            nwc_pcts.append(bs.net_working_capital / inc.revenue)
    nwc_pct = ov.nwc_pct_revenue if ov.nwc_pct_revenue is not None else _historical_average(nwc_pcts)

    return {
        "revenue_growth_rates": rev_growth,
        "operating_margin": operating_margin,
        "tax_rate": tax_rate,
        "da_pct_revenue": da_pct,
        "capex_pct_revenue": capex_pct,
        "nwc_pct_revenue": nwc_pct,
        "projection_years": ov.projection_years,
        "terminal_growth_rate": ov.terminal_growth_rate,
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
    latest_bs = financials.get_balance_sheet(latest_year)

    last_revenue = latest_is.revenue
    last_nwc = latest_bs.net_working_capital if latest_bs else 0.0

    projected = []
    for i in range(assumptions["projection_years"]):
        year = latest_year + i + 1
        growth = assumptions["revenue_growth_rates"][i]
        revenue = last_revenue * (1 + growth)

        nwc_pct = assumptions["nwc_pct_revenue"]
        current_nwc = revenue * nwc_pct

        fcff = calculate_fcff_projected(
            year=year,
            revenue=revenue,
            operating_margin=assumptions["operating_margin"],
            tax_rate=assumptions["tax_rate"],
            da_pct_revenue=assumptions["da_pct_revenue"],
            capex_pct_revenue=assumptions["capex_pct_revenue"],
            nwc_pct_revenue=nwc_pct,
            prior_nwc=last_nwc,
        )
        projected.append(fcff)

        last_revenue = revenue
        last_nwc = current_nwc

    return projected
