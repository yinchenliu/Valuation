"""CAPM model: calculate beta via OLS regression and cost of equity.

E(Ri) = Rf + beta * (E(Rm) - Rf)

Beta is estimated by regressing stock returns on market returns.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

import config
from ingestion.price_fetcher import PriceData
from models.valuation import (
    BETA_RELIABILITY_NOT_ASSESSED,
    BETA_SOURCE_OVERRIDE,
    BETA_SOURCE_REGRESSION,
    RISK_FREE_SOURCE_SUBSTITUTED,
    RISK_FREE_SOURCE_SUPPLIED,
    CAPMResult,
)

# The smallest number of aligned observations an OLS regression of one series
# on another can produce all three of this module's statistics from. It is
# derived, not chosen: the standard error of the slope is
#
#     SE(beta) = sqrt( SSE / ((n - 2) * Sxx) )
#
# so n - 2 must be at least 1. Measured against scipy 1.18.1: at n = 2
# `stats.linregress` returns a finite slope of exactly 1.0 for a perfect fit
# and `stderr = nan`, which would then be carried into `CAPMResult.std_error`
# and rendered. At n = 0 and n = 1 every returned statistic is nan.
MINIMUM_REGRESSION_OBSERVATIONS = 3


def calculate_beta(price_data: PriceData) -> tuple[float, float, float]:
    """Run OLS regression of stock returns vs. market returns.

    Returns:
        (beta, r_squared, std_error)

    Raises:
        ValueError: when the inputs cannot produce a finite beta, naming which
            input was inadequate. `stats.linregress` raises nothing for an
            empty or a degenerate series — it returns `nan` for every
            statistic — and a `nan` beta cannot be detected downstream by a
            comparison, because `nan <= x` and `nan > x` are both False. This
            function is the source of that value, so it is where the run stops.

    `stats.linregress` also returns two statistics this function discards:
      - the intercept (Jensen's alpha — the part of the stock return the
        market return does not explain);
      - the p-value for the null hypothesis that the slope is zero, i.e. the
        statistical significance of the estimated beta.
    Neither reaches `CAPMResult`. A caller that needs one must widen this
    signature; it cannot recover them from the return value.
    """
    market_returns = np.asarray(price_data.market_returns, dtype=float)
    stock_returns = np.asarray(price_data.stock_returns, dtype=float)

    if market_returns.size != stock_returns.size:
        raise ValueError(
            f"market_returns holds {market_returns.size} observations and "
            f"stock_returns holds {stock_returns.size}: beta regresses one on "
            "the other period by period, so the two series must be aligned and "
            "of equal length"
        )

    if market_returns.size < MINIMUM_REGRESSION_OBSERVATIONS:
        raise ValueError(
            f"market_returns and stock_returns hold {market_returns.size} "
            "observations; beta needs at least "
            f"{MINIMUM_REGRESSION_OBSERVATIONS} because the standard error of "
            "the slope divides by (n - 2). Supply a longer price history; a "
            "beta cannot be estimated from this one"
        )

    slope, _intercept, r_value, _p_value, std_err = stats.linregress(
        market_returns,
        stock_returns,
    )

    if math.isnan(slope) or math.isnan(r_value) or math.isnan(std_err):
        raise ValueError(
            "the regression of stock_returns on market_returns produced no "
            f"finite beta (beta={slope}, r_value={r_value}, "
            f"std_error={std_err}). market_returns has variance "
            f"{float(np.var(market_returns))} over {market_returns.size} "
            "observations; a market series with no variation explains nothing "
            "and no beta exists for it"
        )

    return slope, r_value ** 2, std_err


def describe_beta_reliability(
    r_squared: float,
    std_error: float,
    beta: float,
    observations: int,
) -> str:
    """State, in words, whether a regressed beta is precise enough to present.

    Rule 6, backlog item 35. The R-squared was already computed and already
    printed; what was missing is a threshold it is judged against, and the
    verdict standing *beside the beta* rather than two lines away.

    **This returns a sentence. It changes no number and it stops nothing.**
    A regression with a low R-squared is a real measurement of a weak
    relationship between this stock and the market — the data are present and
    the arithmetic is sound. That is rule 6 (say so), not rule 3 (stop). A
    caller that refused to proceed here would refuse legitimate runs: a
    defensive contractor whose returns track its order book rather than the
    index is the normal case, not a broken one.

    The threshold is `config.MINIMUM_BETA_R_SQUARED`, whose comment derives it
    from the standard error of an OLS slope at the default 60-observation
    window.

    Args:
        r_squared: the regression's R-squared, as returned by `calculate_beta`.
        std_error: the standard error of the slope, from the same call.
        beta: the slope itself, reported back so the reader can see the ratio.
        observations: the number of aligned return periods regressed.
    """
    threshold = config.MINIMUM_BETA_R_SQUARED
    if r_squared >= threshold:
        return (
            f"measured and above the minimum: R-squared {r_squared:.3f} >= "
            f"{threshold:.3f} (config.MINIMUM_BETA_R_SQUARED), over "
            f"{observations} observations"
        )
    return (
        f"NOT RELIABLE — R-squared {r_squared:.3f} is below the "
        f"{threshold:.3f} minimum in config.MINIMUM_BETA_R_SQUARED. The market "
        f"explains only {r_squared:.1%} of this stock's return variation over "
        f"{observations} observations, so beta {beta:.3f} carries a standard "
        f"error of {std_error:.3f}. Treat the cost of equity, the WACC and the "
        f"implied share price below as uncertain by a wide margin, and consider "
        f"supplying a beta with --beta."
    )


def annualized_market_return(price_data: PriceData) -> float:
    """Geometric annualized S&P 500 return from historical periodic returns."""
    returns = np.asarray(price_data.market_returns, dtype=float)
    if returns.size == 0:
        raise ValueError("No market returns available to estimate market return")
    gross = float(np.prod(1.0 + returns))
    if gross <= 0:
        # Compounding wiped out; fall back to arithmetic annualization
        return float(np.mean(returns)) * price_data.periods_per_year
    return gross ** (price_data.periods_per_year / returns.size) - 1.0


def run_capm(
    price_data: PriceData,
    risk_free_rate: float | None = None,
    equity_risk_premium: float | None = None,
    beta_override: float | None = None,
) -> CAPMResult:
    """Calculate cost of equity using CAPM.

    Args:
        price_data: Historical return data from price_fetcher.
        risk_free_rate: Annual risk-free rate (e.g., 0.04 for 4%). Uses default if None.
        equity_risk_premium: Market risk premium (e.g., 0.055 for 5.5%). If None,
            it is computed as the historical annualized S&P 500 return minus the
            risk-free rate.
        beta_override: If provided, skips regression and uses this beta directly.

    Returns:
        CAPMResult with beta, cost of equity, and regression diagnostics.
    """
    # Rule 6. The *value* already flowed through to CAPMResult; what did not is
    # the fact that it was substituted. `config.DEFAULT_RISK_FREE_RATE` is not a
    # fallback for a failed fetch — there is no fetch — so on every run without
    # an explicit rate this branch is the one that fires, and the output said
    # nothing about it. This is not rule 3: a risk-free rate is not extracted
    # from a filing, so no measurement is being papered over. It is an
    # assumption that has to be visible as one.
    if risk_free_rate is not None:
        rf = risk_free_rate
        rf_source = RISK_FREE_SOURCE_SUPPLIED
    else:
        rf = config.DEFAULT_RISK_FREE_RATE
        rf_source = RISK_FREE_SOURCE_SUBSTITUTED

    if equity_risk_premium is not None:
        erp = equity_risk_premium
    else:
        market_return = annualized_market_return(price_data)
        erp = market_return - rf
        print(
            f"  ERP from history: S&P 500 annualized return {market_return:.2%} "
            f"- risk-free {rf:.2%} = {erp:.2%}"
        )

    if beta_override is not None:
        beta = beta_override
        # These two zeros are a known defect (backlog item 1): 0.0 here means
        # "no regression was run", not "the regression explained nothing", and
        # the two are the same bytes. They are NOT changed to None, because
        # existing assertions read them as floats. `beta_source` is what now
        # tells a reader which of the two a zero means, and the reliability
        # verdict is NOT_ASSESSED rather than "weak" so that an overridden beta
        # is not accused of failing a threshold it was never measured against.
        r_sq = 0.0
        std_err = 0.0
        beta_src = BETA_SOURCE_OVERRIDE
        reliability = BETA_RELIABILITY_NOT_ASSESSED
    else:
        beta, r_sq, std_err = calculate_beta(price_data)
        beta_src = BETA_SOURCE_REGRESSION
        reliability = describe_beta_reliability(
            r_squared=r_sq,
            std_error=std_err,
            beta=beta,
            observations=len(price_data.stock_returns),
        )

    return CAPMResult(
        beta=beta,
        risk_free_rate=rf,
        equity_risk_premium=erp,
        r_squared=r_sq,
        std_error=std_err,
        risk_free_rate_source=rf_source,
        beta_source=beta_src,
        beta_reliability=reliability,
    )
