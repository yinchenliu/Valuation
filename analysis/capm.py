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
from models.valuation import CAPMResult

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
    rf = risk_free_rate if risk_free_rate is not None else config.DEFAULT_RISK_FREE_RATE

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
        r_sq = 0.0
        std_err = 0.0
    else:
        beta, r_sq, std_err = calculate_beta(price_data)

    return CAPMResult(
        beta=beta,
        risk_free_rate=rf,
        equity_risk_premium=erp,
        r_squared=r_sq,
        std_error=std_err,
    )
