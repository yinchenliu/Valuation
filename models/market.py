"""Market data contracts.

``PriceData`` lives here rather than in ``ingestion/`` so the analysis layer does
not have to import the ingestion layer to type its own inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PriceData:
    """Historical return data for a stock and the market index.

    ``stock_returns`` and ``market_returns`` are periodic simple returns aligned
    on the same dates; ``periods_per_year`` says how to annualise them.
    """

    ticker: str
    stock_returns: Any  # np.ndarray
    market_returns: Any  # np.ndarray
    dates: Any  # pd.DatetimeIndex
    current_price: float
    periods_per_year: int = 12  # 12 for monthly, 252 for daily returns
