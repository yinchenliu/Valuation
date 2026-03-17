"""CAPM model: calculate beta via OLS regression and cost of equity.

E(Ri) = Rf + beta * (E(Rm) - Rf)

Beta is estimated by regressing stock returns on market returns.
"""

from __future__ import annotations

from scipy import stats

from ingestion.price_fetcher import PriceData
from models.valuation import CAPMResult

import config


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
        equity_risk_premium: Market risk premium (e.g., 0.055 for 5.5%). Uses default if None.
        beta_override: If provided, skips regression and uses this beta directly.

    Returns:
        CAPMResult with beta, cost of equity, and regression diagnostics.
    """
    rf = risk_free_rate if risk_free_rate is not None else config.DEFAULT_RISK_FREE_RATE
    erp = equity_risk_premium if equity_risk_premium is not None else config.DEFAULT_EQUITY_RISK_PREMIUM

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
