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
DEFAULT_RISK_FREE_RATE = 0.04  # 4.0% fallback if market fetch fails
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

