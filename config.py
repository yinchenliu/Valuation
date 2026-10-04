import os
from pathlib import Path
from typing import Final

from dotenv import dotenv_values

# Project paths
# These name locations; they do not create them. Importing a configuration
# module must not touch the filesystem. The directory UPLOAD_DIR names is
# created by api/routes_upload.py at the moment a file is actually written.
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"

# Load .env from the project root into os.environ.
#
# The order: a name already in the environment WINS over .env. This module reads
# .env ONCE, with dotenv_values, and fills only the names that are absent from
# os.environ. A name that is set, even to the empty string, is not filled. So:
#
#   * `GEMINI_API_KEY=shell-value ...` runs on the shell's key;
#   * `GEMINI_API_KEY= ...` (empty) runs with the key OFF for that one run;
#   * `env -u GEMINI_API_KEY ...` does NOT turn the key off — the name is absent,
#     so it is filled from .env.
#
# This is the behaviour of `load_dotenv(override=False)`, done here by hand so the
# file's values are kept for credential_origin below without a second read.
# Backlog item 46 (docs/9-reference/refactor-backlog.md) holds the probe table.
# Until P13c this was `load_dotenv(..., override=True)`, and nothing in the shell
# could turn a key off.
#
# The credential names whose origin a run labels (rule 6).
CREDENTIAL_NAMES: Final = (
    "GEMINI_API_KEY",
)


def _load_dotenv_without_override() -> dict[str, str]:
    """Read .env once, fill the absent names, and return the file's credential values.

    A missing .env file reads as no names: dotenv_values returns an empty mapping,
    as load_dotenv does. A line with a name and no `=` reads as None, and is neither
    filled nor kept, as load_dotenv does.

    One difference from load_dotenv(override=False): a `${OTHER}` reference inside
    .env is resolved file-first by dotenv_values, environment-first by load_dotenv.
    It matters only when .env uses `${...}` for a name the shell also sets.

    Returns only the CREDENTIAL_NAMES the file holds, so the rest of the file's
    values are not kept in this module.
    """
    file_values = dotenv_values(BASE_DIR / ".env")
    for name, value in file_values.items():
        if value is not None and name not in os.environ:
            os.environ[name] = value
    return {
        name: value
        for name, value in file_values.items()
        if name in CREDENTIAL_NAMES and value is not None
    }


# The value .env holds for each credential name it holds. Compared, never shown.
_DOTENV_CREDENTIAL_VALUES: Final[dict[str, str]] = _load_dotenv_without_override()


def credential_origin(name: str) -> str:
    """Say whether the credential in use is the one in .env. Never returns its value.

    The rule is a comparison each process can check for itself, at call time:

    * the value in os.environ equals the value .env holds: `(.env file)`;
    * it differs, or .env does not hold the name: `(shell or parent process, not .env)`.

    A shell value that equals the file's value reads `(.env file)`. That is harmless:
    the key in use is the key in the file.

    The label says nothing about a value's history (who set it, in which process).
    Two rounds of P13c showed that history does not survive a process boundary.

    Stops, naming the field, when the name is not one this module knows, or is not
    set to a non-blank value: a label for an absent credential would be a false
    label (rule 6).
    """
    if name not in CREDENTIAL_NAMES:
        raise ValueError(
            f"credential_origin: {name!r} is not one of {CREDENTIAL_NAMES}.",
        )
    if name not in os.environ or not os.environ[name].strip():
        raise ValueError(
            f"credential_origin: {name} is not set to a non-blank value, so it has "
            "no origin to label.",
        )
    if (
        name in _DOTENV_CREDENTIAL_VALUES
        and _DOTENV_CREDENTIAL_VALUES[name] == os.environ[name]
    ):
        return f"{name} (.env file)"
    return f"{name} (shell or parent process, not .env)"


# Extraction provider — named ONCE, here.
#
# Which model read the filing is an assumption about every figure downstream of it
# (rule 6), so it is named in one place and shown in the output. No other module
# defines a provider default: ingestion, api/ and cli.py all read this constant.
#
# On the user's decision of 2026-10-04, route A uses Gemini. Gemini's reachability
# from this machine is not yet measured (the overall lead asks the user for one
# paid run). Claude reads a filing only in a Claude Code session (route B).
#
# `Final` with no annotation is deliberate — it makes the inferred type
# Literal["gemini"], which satisfies ingestion.claude_extractor.Provider without
# config.py having to import from ingestion.
DEFAULT_EXTRACTION_PROVIDER: Final = "gemini"

# Default valuation assumptions
DEFAULT_PROJECTION_YEARS = 5
DEFAULT_TERMINAL_GROWTH_RATE = 0.025  # 2.5%
DEFAULT_EQUITY_RISK_PREMIUM = 0.055  # 5.5%

# Risk-free rate — AN ASSUMPTION, NOT A MEASUREMENT. Rule 6, backlog item 34.
#
# This comment used to read "fallback if market fetch fails". There is no market
# fetch. `ingestion/price_fetcher.py` fetches share prices and the S&P 500 series
# and nothing else; no treasury rate is read from anywhere, so this constant is
# used on every run in which the caller does not pass --risk-free-rate. It
# reaches the cost of equity, WACC, every discounted cash flow and the share
# price.
#
# 4.0% is the round figure near the 10-year US Treasury yield over the period
# this platform was written in. It is not sourced, not dated, and not refreshed.
# `analysis/capm.py` records on every CAPMResult whether this constant was
# substituted or a rate was supplied, and both outputs print that label beside
# the rate.
#
# Adding a treasury fetch would be a new market data source (rule 5) and is a
# separate decision; labelling closes the rule 6 break on its own.
DEFAULT_RISK_FREE_RATE = 0.04  # 4.0%, assumed — see above
DEFAULT_BETA_LOOKBACK_YEARS = 5
DEFAULT_RETURN_FREQUENCY = "monthly"  # "daily" or "monthly"

# Cost of debt substitute — AN ASSUMPTION. Rule 6, backlog item 9.
#
# Used when the company carries debt but interest expense is not reported
# separately, i.e. when Rd = interest / total_debt cannot be computed. 4.0%
# pre-tax is a round investment-grade coupon; it is not this company's coupon
# and it is not read from the filing.
#
# `analysis/wacc.py` records on every WACCResult which of the four branches
# produced the cost of debt, and both outputs print that label beside the rate,
# so a substitution is no longer indistinguishable from a measurement.
DEFAULT_COST_OF_DEBT = 0.04  # 4.0% pre-tax, assumed — see above

# Minimum R-squared for a regressed beta to be presented without a warning.
# Rule 6, backlog item 35. THIS THRESHOLD CHANGES NO NUMBER — it only decides
# whether the output says the beta is unreliable. A weak regression is a real
# measurement of a weak relationship, not a missing input, so it does not stop
# the run (that would be rule 3, and this is not rule 3).
#
# Why 0.20 and not some other number. For an OLS slope, the standard error of
# beta relative to beta itself is fixed by R-squared and the number of
# observations alone:
#
#     SE(beta) / beta = sqrt( (1 - R^2) / (R^2 * (n - 2)) )
#
# At the default 5-year monthly window, n = 60, so:
#
#     R^2 = 0.30  ->  SE/beta = 0.201  ->  95% interval +/- 39% of the estimate
#     R^2 = 0.20  ->  SE/beta = 0.263  ->  95% interval +/- 52% of the estimate
#     R^2 = 0.10  ->  SE/beta = 0.394  ->  95% interval +/- 77% of the estimate
#
# 0.20 is the point at which the 95% interval on beta is about as wide as the
# estimate itself (+/- 52%). Below it, "beta = 0.49" and "beta = 0.95" are not
# distinguishable by the regression that produced them — and on the L3Harris
# FY2025 run that difference moved the implied price from $343 to well under
# the market price. Above it the interval narrows fast.
#
# The identity above is checkable against any run's own printed output:
# L3Harris FY2025 reported beta 0.493 and std error 0.196, a ratio of 0.3976,
# against 0.3961 predicted from its R-squared of 0.099 at n = 60.
#
# The threshold itself is an assumption and is printed as one.
MINIMUM_BETA_R_SQUARED = 0.20

# Revenue growth: number of trailing years to use for CAGR estimation.
# Using 3 years avoids distortion from one-off macro events (e.g. COVID 2020 trough).
DEFAULT_REVENUE_GROWTH_LOOKBACK_YEARS = 3

# S&P 500 ticker for CAPM
SP500_TICKER = "^GSPC"

