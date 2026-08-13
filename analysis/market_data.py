"""Market-driven valuation inputs, with provenance.

The risk-free rate and equity risk premium used to be bare literals. This module
fetches what can be fetched, falls back explicitly when it can't, and stamps every
value with where it came from and as of when — so a valuation can be audited
without guessing which numbers were live and which were stale.

Design notes:

- The risk-free rate is genuinely observable, so it is fetched (CBOE 10-Year
  Treasury Yield Index, ``^TNX``).
- The equity risk premium is *not* observable; it is an estimate. It therefore
  comes from a versioned constant carrying an explicit as-of date, not from a
  scrape. The previous behaviour — realised trailing S&P 500 return minus the
  risk-free rate — remains available via ``realised_equity_risk_premium()`` but is
  no longer the default. See ``config.ASSUMPTION_PROVENANCE`` for the rationale.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime

import config

# yfinance ticker for the CBOE 10-Year Treasury Yield Index. Quoted in percent
# (e.g. 4.32 means 4.32%), so it needs dividing by 100.
TREASURY_10Y_TICKER = "^TNX"

# Seconds to reuse a fetched value. An agentic loop may revisit CAPM several times
# within one run; without this, each revisit is another network round trip.
_CACHE_TTL_SECONDS = 900

_cache: dict[str, tuple[float, "MarketValue"]] = {}


@dataclass
class MarketValue:
    """A valuation input together with where it came from."""

    value: float
    source: str
    as_of: date
    is_fallback: bool = False

    def describe(self) -> str:
        suffix = " (fallback)" if self.is_fallback else ""
        return f"{self.value:.2%} — {self.source}, as of {self.as_of.isoformat()}{suffix}"


def _cached(key: str) -> MarketValue | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    stored_at, value = entry
    if time.monotonic() - stored_at > _CACHE_TTL_SECONDS:
        del _cache[key]
        return None
    return value


def _store(key: str, value: MarketValue) -> MarketValue:
    _cache[key] = (time.monotonic(), value)
    return value


def clear_cache() -> None:
    """Drop cached market values. Used by tests and by long-lived processes."""
    _cache.clear()


def fetch_risk_free_rate(force_refresh: bool = False) -> MarketValue:
    """Current 10-year Treasury yield as a decimal (0.0432 == 4.32%).

    Falls back to ``config.DEFAULT_RISK_FREE_RATE`` on any failure — no network,
    a delisted ticker, an empty frame, a nonsensical value. The fallback is always
    labelled as such rather than silently substituted.
    """
    if not force_refresh:
        hit = _cached("risk_free_rate")
        if hit is not None:
            return hit

    fallback = MarketValue(
        value=config.DEFAULT_RISK_FREE_RATE,
        source=f"config.DEFAULT_RISK_FREE_RATE ({config.ASSUMPTION_PROVENANCE['risk_free_rate']['source']})",
        as_of=config.ASSUMPTION_PROVENANCE["risk_free_rate"]["as_of"],
        is_fallback=True,
    )

    try:
        import yfinance as yf

        config.configure_yfinance_cache()

        # yf.download rather than Ticker().history(): the latter always resolves
        # the ticker's timezone through the sqlite cache, so a cache failure takes
        # the whole call down even when the price data itself is reachable.
        frame = yf.download(
            TREASURY_10Y_TICKER, period="1mo", progress=False, auto_adjust=True,
        )
        if frame.empty or "Close" not in frame.columns:
            return _store("risk_free_rate", fallback)

        closes = frame["Close"]
        if hasattr(closes, "columns"):  # yfinance sometimes returns a MultiIndex
            closes = closes.squeeze()
        closes = closes.dropna()
        if closes.empty:
            return _store("risk_free_rate", fallback)

        last_close = float(closes.iloc[-1])
        rate = last_close / 100.0

        # Sanity-bound the result. A 10Y yield outside 0%-25% means the feed
        # returned something other than a yield, and silently discounting a DCF
        # at a garbage rate is worse than using a documented constant.
        if not (0.0 < rate < 0.25):
            return _store("risk_free_rate", fallback)

        observed = closes.index[-1]
        as_of = observed.date() if hasattr(observed, "date") else datetime.today().date()

        return _store(
            "risk_free_rate",
            MarketValue(
                value=rate,
                source=f"{TREASURY_10Y_TICKER} 10Y Treasury yield (yfinance)",
                as_of=as_of,
            ),
        )
    except Exception:  # noqa: BLE001 — any failure means fall back, never abort a valuation
        return _store("risk_free_rate", fallback)


def fetch_equity_risk_premium() -> MarketValue:
    """Forward equity risk premium as a decimal.

    Sourced from a versioned constant rather than computed, because a *forward*
    ERP is an estimate, not an observable. Review the constant (and its as-of
    date) in ``config.py`` periodically.
    """
    meta = config.ASSUMPTION_PROVENANCE["equity_risk_premium"]
    return MarketValue(
        value=config.DEFAULT_EQUITY_RISK_PREMIUM,
        source=meta["source"],
        as_of=meta["as_of"],
    )


def realised_equity_risk_premium(market_return: float, risk_free_rate: float) -> MarketValue:
    """Backward-looking ERP: realised market return minus the risk-free rate.

    This was the default before; it is retained as an explicit opt-in. It is a
    poor forward estimate — after a strong run it overstates the premium and
    suppresses the valuation, and after a drawdown it does the reverse. It can
    even go negative, which drives the cost of equity below the risk-free rate
    and makes the WACC unusable.
    """
    return MarketValue(
        value=market_return - risk_free_rate,
        source=(
            f"realised {config.SP500_TICKER} annualised return "
            f"{market_return:.2%} less risk-free {risk_free_rate:.2%}"
        ),
        as_of=datetime.today().date(),
    )
