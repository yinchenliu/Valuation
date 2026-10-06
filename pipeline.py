"""The valuation sequence, once. `cli.py` and `api/routes_valuation.py` both call it.

Until `P3a-one-pipeline` each entry point called the same eight functions in its own
copy, and chose the share count and the arguments itself, so a fix made in one copy
did not reach the other and a figure verified in the CLI was not verified on the web
page (backlog item 7, `docs/3-architecture/entry-points.md`).

Two functions, not one, because the two callers stop at different places:

- `adjust_financials` — partition the non-recurring items on their confidence, then
  normalise with the applied half. The web assumptions page calls this alone; the CLI
  calls it and prints stages 2 to 5 before it fetches any market data.
- `value_company` — the assumptions, the market data, CAPM, the share count, the market
  capitalisation, WACC, the projection and the DCF.

Neither function prints and neither formats anything for display. That stays with
the callers: the CLI's per-stage audit trail, the routes' templates.

This module sits at the repository root, beside `cli.py` and `app.py`, and not in
`analysis/`: the sequence calls `ingestion.price_fetcher.fetch_price_data`, and
`analysis/` importing from `ingestion/` is backlog item 17.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from analysis.capm import run_capm
from analysis.dcf import run_dcf
from analysis.normalizer import normalize_financials, partition_by_confidence
from analysis.projector import derive_assumptions, project_fcffs
from analysis.wacc import calculate_wacc
from ingestion.price_fetcher import PriceData, fetch_price_data
from models.financial_statements import (
    BalanceSheet,
    FinancialStatements,
    NonRecurringItem,
)
from models.valuation import (
    CAPMResult,
    DCFResult,
    ProjectedFCFF,
    ProjectionAssumptions,
    WACCResult,
)


@dataclass(frozen=True)
class AdjustedFinancials:
    """The statements after the non-recurring items that were applied.

    `applied` are the `high` and `medium` confidence items; they moved the income
    statement. `excluded` are the `low` items; they moved nothing, and each caller
    shows them so a reader can put one back by hand. `adjusted` is a new
    `FinancialStatements`: `normalize_financials` does not mutate its argument, so
    the caller's raw statements are still the pre-adjustment extraction.

    Every field is required, so a result missing one cannot be constructed.
    """

    applied: list[NonRecurringItem]
    excluded: list[NonRecurringItem]
    adjusted: FinancialStatements


@dataclass(frozen=True)
class ValuationRun:
    """Every value either entry point reads after the valuation ran.

    `shares` is the latest fiscal year's diluted share count, in millions, as the
    filing prints it. It is never taken from market data (rule 5): when the filing
    gives none, `value_company` stops instead.

    `latest_balance_sheet` is the balance sheet of the latest fiscal year. It is
    never `None`: `value_company` stops when the extraction holds none, so a run
    that exists was valued on a balance sheet.

    `total_debt` is that balance sheet's debt balance, in millions — the figure
    `calculate_wacc` weighted the capital with, and the one the CLI prints as
    "Total debt" in stage 8. It is carried here rather than re-read by each
    caller because the CLI used to re-derive it from a balance sheet it only
    tested for presence, printing zero when there was none — a missing balance
    sheet shown as a debt-free company (backlog item 72, rule 3).

    Every field is required. None is defaulted.
    """

    assumptions: dict
    price_data: PriceData
    capm_result: CAPMResult
    shares: float
    market_cap: float
    latest_balance_sheet: BalanceSheet
    total_debt: float
    wacc_result: WACCResult
    projected: list[ProjectedFCFF]
    dcf_result: DCFResult


def adjust_financials(
    raw_financials: FinancialStatements,
    non_recurring: list[NonRecurringItem],
) -> AdjustedFinancials:
    """Partition the items on their confidence, then normalise with the applied half.

    The partition happens before normalisation and outside it: rule 1 puts the
    decision in `analysis/`, and `normalize_financials` keeps the signature its tests
    were written against. Only `applied` reaches the arithmetic.
    """
    applied, excluded = partition_by_confidence(non_recurring)
    adjusted = normalize_financials(raw_financials, applied)
    return AdjustedFinancials(applied=applied, excluded=excluded, adjusted=adjusted)


def value_company(
    adjusted: FinancialStatements,
    overrides: ProjectionAssumptions,
    ticker: str,
    lookback_years: int,
    frequency: str,
) -> ValuationRun:
    """Run the valuation on the adjusted statements, with the caller's overrides.

    The arguments passed to each step are the ones both entry points passed before
    `P3a-one-pipeline`; that unit moved the call sites and no number, with one
    exception: a filing with no diluted share count used to be valued on a share
    count from yfinance, and now stops (review F1, rules 3 and 5).

    Raises:
        ValueError: when the latest fiscal year's diluted share count is not a
            finite number above 0, or when that year has no balance sheet.
            Both are raised before any market data is fetched.
    """
    assumptions = derive_assumptions(adjusted, overrides)

    latest_year = adjusted.latest_year
    latest_is = adjusted.get_income_statement(latest_year)
    latest_bs = adjusted.get_balance_sheet(latest_year)
    # `latest_year` is the largest year that HAS an income statement, and it raises
    # when there is none (`models/financial_statements.py`, `latest_year`), so this
    # branch cannot run. It is written as a stop, rather than as the conditional
    # zero share count the CLI used to have here, so that the type says what the
    # property guarantees and a future change to `latest_year` stops here instead
    # of valuing on zero shares.
    if latest_is is None:
        raise ValueError(
            f"No income statement for {adjusted.ticker!r} in fiscal year "
            f"{latest_year}, the latest year. The diluted share count and the cost "
            f"of debt are read from it; nothing is substituted."
        )

    # The share count is the denominator of the headline figure, and the filing is
    # its only source (rule 5). The extraction makes an empty `diluted_shares` list
    # into 0 (`figure_from_printed_lines`), so 0 here means the filing gave no
    # count. Stop and name it (rule 3). Until review F1 of `P3a-one-pipeline` a 0
    # fell back to yfinance's `sharesOutstanding` (rule 5), and that lookup itself
    # fell back to zero when yfinance had no figure. `math.isfinite` is tested
    # first because a comparison alone lets NaN through. Checked before the
    # market data call: a filing figure that stops the run should not wait on
    # the network.
    shares = latest_is.diluted_shares_outstanding
    if not (math.isfinite(shares) and shares > 0):
        raise ValueError(
            f"diluted_shares is {shares!r} for {ticker!r} in fiscal year "
            f"{latest_year}: the implied share price needs the latest year's diluted "
            f"share count as printed in the filing, a finite number above 0. No "
            f"share count is taken from market data (rule 5); supply the count "
            f"printed in the filing."
        )

    # The debt balance is read from the filing's balance sheet and from nothing
    # else, so a missing balance sheet stops the run here (rule 3, backlog item
    # 72). `calculate_wacc` already stops on the same input, but only after the
    # market data has been fetched, and the CLI read the balance sheet a second
    # time for its stage 8 display, testing it for presence and printing zero
    # when there was none — a missing balance sheet shown as a debt-free
    # company. This stop sits beside the share-count stop and for the same
    # reason: a filing figure that stops the run should not wait on the
    # network. `calculate_wacc` keeps its own stop; it guards every other
    # caller.
    if latest_bs is None:
        raise ValueError(
            f"balance_sheet is None for {ticker!r} in fiscal year {latest_year}, "
            f"the latest year: the debt balance "
            f"(BalanceSheet.short_term_debt + "
            f"BalanceSheet.current_portion_lt_debt + "
            f"BalanceSheet.long_term_debt) cannot be read, so the capital "
            f"weights, the cost of debt and the net debt in the equity bridge "
            f"are not computed. The debt balance is not set to 0: a missing "
            f"balance sheet is not a debt-free company. Supply the balance "
            f"sheet for the year being valued."
        )
    total_debt = latest_bs.total_debt

    price_data = fetch_price_data(
        ticker,
        lookback_years=lookback_years,
        frequency=frequency,
    )
    capm_result = run_capm(
        price_data,
        risk_free_rate=overrides.risk_free_rate,
        equity_risk_premium=overrides.equity_risk_premium,
        beta_override=overrides.beta_override,
    )

    market_cap = price_data.current_price * shares

    wacc_result = calculate_wacc(
        capm_result=capm_result,
        income_statement=latest_is,
        balance_sheet=latest_bs,
        market_cap=market_cap,
        cost_of_debt_override=overrides.cost_of_debt_override,
        tax_rate_override=assumptions["tax_rate"],
        zero_debt_confirmed=overrides.zero_debt_confirmed,
    )

    projected = project_fcffs(adjusted, assumptions)

    dcf_result = run_dcf(
        projected_fcffs=projected,
        wacc_result=wacc_result,
        financials=adjusted,
        terminal_growth_rate=assumptions["terminal_growth_rate"],
        current_price=price_data.current_price,
        diluted_shares=shares,
    )

    return ValuationRun(
        assumptions=assumptions,
        price_data=price_data,
        capm_result=capm_result,
        shares=shares,
        market_cap=market_cap,
        latest_balance_sheet=latest_bs,
        total_debt=total_debt,
        wacc_result=wacc_result,
        projected=projected,
        dcf_result=dcf_result,
    )
