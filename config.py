import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# Project paths
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Load .env from project root — values are merged into os.environ.
# System env vars still work; .env just provides a convenient local override.
load_dotenv(BASE_DIR / ".env", override=True)

# ---------------------------------------------------------------------------
# Default valuation assumptions
#
# These are the single source of truth. Do not re-declare any of these values as
# literals in dataclass field defaults, form defaults, argparse defaults, or HTML
# templates — those shadow the constant and make it dead. Read from here instead.
# ---------------------------------------------------------------------------
DEFAULT_PROJECTION_YEARS = 5
DEFAULT_TERMINAL_GROWTH_RATE = 0.025  # 2.5%
DEFAULT_EQUITY_RISK_PREMIUM = 0.055  # 5.5%
DEFAULT_RISK_FREE_RATE = 0.04  # 4.0% — fallback when the ^TNX fetch fails
DEFAULT_BETA_LOOKBACK_YEARS = 5
DEFAULT_RETURN_FREQUENCY = "monthly"  # "daily" or "monthly"

# Cost of debt fallback: used when interest expense is not reported separately.
# Set to a conservative investment-grade spread. Override per company as needed.
DEFAULT_COST_OF_DEBT = 0.04  # 4.0% pre-tax

# Revenue growth: number of trailing years to use for CAGR estimation.
# Using 3 years avoids distortion from one-off macro events (e.g. COVID 2020 trough).
DEFAULT_REVENUE_GROWTH_LOOKBACK_YEARS = 3

# S&P 500 ticker for CAPM
SP500_TICKER = "^GSPC"

# yfinance keeps a small sqlite timezone cache. It defaults to a per-user
# location, which fails with "disk I/O error" on machines where the profile
# directory is full or quota'd — and that failure takes down *every* price fetch,
# not just the first. Keeping it beside the project avoids depending on the
# profile being writable. Override with YF_CACHE_DIR if you'd rather it live
# elsewhere.
YF_CACHE_DIR = Path(os.environ.get("YF_CACHE_DIR", BASE_DIR / ".yf_cache"))


def configure_yfinance_cache() -> None:
    """Point yfinance's timezone cache somewhere writable. Safe to call repeatedly."""
    try:
        import yfinance as yf

        YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(YF_CACHE_DIR))
    except Exception:  # noqa: BLE001 — never let cache setup break a valuation
        pass

# ---------------------------------------------------------------------------
# Provenance
#
# Where each default came from, when it was last reviewed, and why it holds that
# value. Surfaced in the UI and in the agent transcript so a reader can tell a
# live market observation from a judgement call that needs revisiting.
# ---------------------------------------------------------------------------
ASSUMPTION_PROVENANCE: dict[str, dict] = {
    "risk_free_rate": {
        "source": "10Y US Treasury yield (^TNX); this constant is the fallback",
        "as_of": date(2026, 8, 11),
        "rationale": (
            "Matched to the 10-year Treasury as the standard maturity for a "
            "perpetuity-based DCF. Fetched live; the constant applies only when "
            "the fetch fails."
        ),
    },
    "equity_risk_premium": {
        "source": "Damodaran implied US ERP (annual review)",
        "as_of": date(2026, 8, 11),
        "rationale": (
            "A forward ERP is an estimate, not an observable, so it is versioned "
            "rather than computed. Replaces the previous realised trailing S&P 500 "
            "return, which is procyclical and can go negative."
        ),
    },
    "terminal_growth_rate": {
        "source": "long-run nominal GDP growth proxy",
        "as_of": date(2026, 8, 11),
        "rationale": (
            "Perpetuity growth cannot exceed long-run nominal GDP growth without "
            "implying the firm eventually becomes the whole economy."
        ),
    },
    "cost_of_debt": {
        "source": "investment-grade corporate spread over the risk-free rate",
        "as_of": date(2026, 8, 11),
        "rationale": (
            "Applies only when the filing carries debt but does not report interest "
            "expense separately, so an effective rate cannot be derived."
        ),
    },
    "revenue_growth_lookback_years": {
        "source": "judgement",
        "as_of": date(2026, 8, 11),
        "rationale": (
            "Three years is short enough to exclude the 2020 COVID trough from the "
            "CAGR base while still spanning more than one operating year."
        ),
    },
    "beta_lookback_years": {
        "source": "market convention",
        "as_of": date(2026, 8, 11),
        "rationale": "Five years of monthly returns is the standard beta estimation window.",
    },
}
