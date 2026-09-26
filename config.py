from pathlib import Path
from typing import Final

from dotenv import load_dotenv

# Project paths
# These name locations; they do not create them. Importing a configuration
# module must not touch the filesystem. The directory UPLOAD_DIR names is
# created by api/routes_upload.py at the moment a file is actually written.
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"

# Load .env from project root — values are merged into os.environ.
# System env vars still work; .env just provides a convenient local override.
load_dotenv(BASE_DIR / ".env", override=True)

# Extraction provider — named ONCE, here.
#
# Which model read the filing is an assumption about every figure downstream of it
# (rule 6), so it is named in one place and shown in the output. No other module
# defines a provider default: ingestion, api/ and cli.py all read this constant.
#
# "claude" and not "gemini": Gemini is unreachable from the network this platform
# runs on. See docs/8-build/environment.md section 3.
#
# `Final` with no annotation is deliberate — it makes the inferred type
# Literal["claude"], which satisfies ingestion.claude_extractor.Provider without
# config.py having to import from ingestion.
DEFAULT_EXTRACTION_PROVIDER: Final = "claude"

# Entra ID (Azure AD) token scope for the Microsoft Foundry gateway.
#
# This is the *audience* the gateway validates, not a secret and not a URL we call.
# `https://ai.azure.com/.default` is rejected with HTTP 401; the gateway names this
# scope in the body of that 401. See docs/8-build/environment.md section 3.
ENTRA_TOKEN_SCOPE: Final = "https://cognitiveservices.azure.com/.default"

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

