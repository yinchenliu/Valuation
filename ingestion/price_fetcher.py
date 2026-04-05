"""Fetch historical price data using yfinance for CAPM beta calculation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from config import SP500_TICKER


@dataclass
class PriceData:
    """Historical return data for a stock and the market index."""

    ticker: str
    stock_returns: np.ndarray
    market_returns: np.ndarray
    dates: pd.DatetimeIndex
    current_price: float


def fetch_price_data(
    ticker: str,
    lookback_years: int = 5,
    frequency: str = "monthly",
) -> PriceData:
    """Fetch historical prices and compute returns for CAPM regression.

    Args:
        ticker: Stock ticker symbol.
        lookback_years: Number of years of historical data to fetch.
        frequency: "daily" or "monthly" return frequency.

    Returns:
        PriceData with aligned stock and market returns.
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=lookback_years * 365)

    # Fetch adjusted close prices
    stock = yf.download(ticker, start=start_date, end=end_date, progress=False)
    market = yf.download(SP500_TICKER, start=start_date, end=end_date, progress=False)

    if stock.empty or market.empty:
        raise ValueError(f"Could not fetch price data for {ticker} or {SP500_TICKER}")

    # Use Adj Close if available, otherwise Close
    stock_prices = stock["Adj Close"] if "Adj Close" in stock.columns else stock["Close"]
    market_prices = market["Adj Close"] if "Adj Close" in market.columns else market["Close"]

    # Flatten MultiIndex columns if present (yfinance sometimes returns MultiIndex)
    if hasattr(stock_prices, "columns"):
        stock_prices = stock_prices.squeeze()
    if hasattr(market_prices, "columns"):
        market_prices = market_prices.squeeze()

    # Resample to monthly if requested
    # "ME" (month-end) requires pandas >= 2.2; older versions use "M".
    if frequency == "monthly":
        import pandas as _pd
        _month = "ME" if tuple(int(x) for x in _pd.__version__.split(".")[:2]) >= (2, 2) else "M"
        stock_prices = stock_prices.resample(_month).last()
        market_prices = market_prices.resample(_month).last()

    # Calculate returns
    stock_returns = stock_prices.pct_change().dropna()
    market_returns = market_prices.pct_change().dropna()

    # Align on common dates
    combined = pd.DataFrame({
        "stock": stock_returns,
        "market": market_returns,
    }).dropna()

    current_price = float(stock_prices.iloc[-1])

    return PriceData(
        ticker=ticker,
        stock_returns=combined["stock"].values,
        market_returns=combined["market"].values,
        dates=combined.index,
        current_price=current_price,
    )
