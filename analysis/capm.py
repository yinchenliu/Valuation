"""CAPM model: calculate beta via OLS regression and cost of equity.

E(Ri) = Rf + beta * (E(Rm) - Rf)

Beta is estimated by regressing stock returns on market returns.
"""

from __future__ import annotations

from datetime import date

import numpy as np
from scipy import stats

from analysis.market_data import (
    MarketValue,
    fetch_equity_risk_premium,
    fetch_risk_free_rate,
    realised_equity_risk_premium,
)
from models.market import PriceData
from models.valuation import CAPMResult

# Sentinel for `equity_risk_premium`: opt back in to the backward-looking
# realised-return ERP that used to be the default.
REALISED = "realised"


def calculate_beta(price_data: PriceData) -> tuple[float, float, float]:
    """Run OLS regression of stock returns vs. market returns.

    Returns:
        (beta, r_squared, std_error)
    """
    slope, intercept, r_value, p_value, std_err = stats.linregress(
        price_data.market_returns,
        price_data.stock_returns,
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
    equity_risk_premium: float | str | None = None,
    beta_override: float | None = None,
) -> CAPMResult:
    """Calculate cost of equity using CAPM.

    Args:
        price_data: Historical return data from price_fetcher.
        risk_free_rate: Annual risk-free rate as a decimal (0.04 == 4%). If None,
            the current 10Y Treasury yield is fetched, falling back to
            ``config.DEFAULT_RISK_FREE_RATE``.
        equity_risk_premium: Market risk premium as a decimal (0.055 == 5.5%). If
            None, uses the versioned ``config.DEFAULT_EQUITY_RISK_PREMIUM``. Pass
            ``REALISED`` ("realised") to instead derive it from the trailing
            market return, which is what this function used to do by default.
        beta_override: If provided, skips regression and uses this beta directly.

    Returns:
        CAPMResult with beta, cost of equity, regression diagnostics, and the
        provenance of both market inputs.
    """
    if risk_free_rate is not None:
        rf = MarketValue(
            value=risk_free_rate,
            source="caller-supplied override",
            as_of=date.today(),
        )
    else:
        rf = fetch_risk_free_rate()

    if equity_risk_premium is None:
        erp = fetch_equity_risk_premium()
    elif isinstance(equity_risk_premium, str):
        if equity_risk_premium.lower() != REALISED:
            raise ValueError(
                f"equity_risk_premium must be a number or {REALISED!r}, got {equity_risk_premium!r}"
            )
        erp = realised_equity_risk_premium(annualized_market_return(price_data), rf.value)
    else:
        erp = MarketValue(
            value=equity_risk_premium,
            source="caller-supplied override",
            as_of=date.today(),
        )

    if beta_override is not None:
        beta = beta_override
        r_sq = 0.0
        std_err = 0.0
    else:
        beta, r_sq, std_err = calculate_beta(price_data)

    return CAPMResult(
        beta=beta,
        risk_free_rate=rf.value,
        equity_risk_premium=erp.value,
        r_squared=r_sq,
        std_error=std_err,
        risk_free_source=rf.source,
        risk_free_as_of=rf.as_of,
        risk_free_is_fallback=rf.is_fallback,
        erp_source=erp.source,
        erp_as_of=erp.as_of,
        erp_is_fallback=erp.is_fallback,
    )
