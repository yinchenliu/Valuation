from pathlib import Path

from dotenv import load_dotenv

# Project paths
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Load .env from project root — values are merged into os.environ.
# System env vars still work; .env just provides a convenient local override.
load_dotenv(BASE_DIR / ".env", override=False)

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

