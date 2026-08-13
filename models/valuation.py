from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import config


@dataclass
class CAPMResult:
    """Output of CAPM calculation."""

    beta: float
    risk_free_rate: float
    equity_risk_premium: float

    @property
    def cost_of_equity(self) -> float:
        return self.risk_free_rate + self.beta * self.equity_risk_premium

    # Regression diagnostics
    r_squared: float = 0.0
    std_error: float = 0.0

    # Provenance — where the two market inputs came from, so a reader can tell a
    # live observation from a fallback constant without re-running anything.
    risk_free_source: str = ""
    risk_free_as_of: date | None = None
    risk_free_is_fallback: bool = False
    erp_source: str = ""
    erp_as_of: date | None = None
    erp_is_fallback: bool = False


@dataclass
class WACCResult:
    """Output of WACC calculation."""

    cost_of_equity: float
    cost_of_debt: float
    tax_rate: float
    equity_weight: float  # E / V
    debt_weight: float  # D / V

    @property
    def wacc(self) -> float:
        return (
            self.equity_weight * self.cost_of_equity
            + self.debt_weight * self.cost_of_debt * (1 - self.tax_rate)
        )


@dataclass
class HistoricalFCFF:
    """Single year of historical FCFF derived from the cash flow statement.

    Formula: FCFF = CFO + Interest_Expense * (1 - t) - CapEx

    Rationale: CFO is the reported operating cash flow from the actual filing.
    Under GAAP, interest paid is classified as an operating activity, so CFO
    is AFTER interest. Adding back after-tax interest restores the pre-financing
    (firm-level) cash flow available to all capital providers.

    Note: CFO-based FCFF implicitly treats SBC as non-cash (it is added back in
    CFO). For tech companies with heavy SBC this will be materially higher than
    EBIT-based FCFF. Both are valid — they represent different views of economic cost.
    """

    year: int
    revenue: float
    ebit: float                   # for reference / operating margin calculation
    cfo: float                    # reported Cash from Operations
    interest_expense: float       # positive; 0 if not separately reported
    after_tax_interest: float     # interest_expense * (1 - tax_rate)
    capital_expenditures: float   # positive (gross CapEx from CFS)
    tax_rate: float
    fcff: float                   # = cfo + after_tax_interest - capital_expenditures

    @property
    def operating_margin(self) -> float:
        return self.ebit / self.revenue if self.revenue else 0.0

    @property
    def fcff_margin(self) -> float:
        return self.fcff / self.revenue if self.revenue else 0.0


@dataclass
class ProjectedFCFF:
    """Single year of projected free cash flow (EBIT-based).

    Formula: FCFF = NOPAT + D&A - CapEx - delta_NWC
           = EBIT * (1 - t) + D&A - CapEx - delta_NWC

    Used for forward projections where we model the income statement from
    revenue growth and margin assumptions.
    """

    year: int
    revenue: float
    ebit: float
    nopat: float
    depreciation_amortization: float
    capital_expenditures: float
    change_in_working_capital: float

    @property
    def fcff(self) -> float:
        return (
            self.nopat
            + self.depreciation_amortization
            - abs(self.capital_expenditures)
            - self.change_in_working_capital
        )


@dataclass
class DCFResult:
    """Complete DCF valuation output."""

    # Inputs / assumptions
    ticker: str
    projection_years: int
    terminal_growth_rate: float
    wacc: float

    # Projected cash flows
    projected_fcffs: list[ProjectedFCFF] = field(default_factory=list)

    # Valuation components
    pv_fcffs: float = 0.0  # PV of projected FCFFs
    terminal_value: float = 0.0  # Undiscounted terminal value
    pv_terminal_value: float = 0.0  # PV of terminal value

    @property
    def enterprise_value(self) -> float:
        return self.pv_fcffs + self.pv_terminal_value

    # Bridge to equity
    net_debt: float = 0.0
    cash: float = 0.0
    diluted_shares: float = 0.0

    @property
    def equity_value(self) -> float:
        return self.enterprise_value - self.net_debt

    @property
    def implied_share_price(self) -> float:
        return self.equity_value / self.diluted_shares if self.diluted_shares else 0.0

    # Comparison
    current_price: float = 0.0

    @property
    def upside_downside(self) -> float:
        """Percentage upside (+) or downside (-) vs current price."""
        if self.current_price == 0:
            return 0.0
        return (self.implied_share_price / self.current_price - 1) * 100


@dataclass
class DerivedAssumptions:
    """The resolved projection assumptions produced by derive_assumptions().

    Previously a bare dict, which meant every consumer indexed it with string keys
    and a typo surfaced as a KeyError at projection time. It is a dataclass now,
    but it still supports mapping access so existing callers and templates keep
    working unchanged.
    """

    revenue_growth_rates: list[float]
    operating_margin: float
    tax_rate: float
    da_pct_revenue: float
    capex_pct_revenue: float
    nwc_pct_revenue: float
    projection_years: int
    terminal_growth_rate: float

    # Which fields came from a user/agent override rather than history.
    overridden: list[str] = field(default_factory=list)

    _KEYS = (
        "revenue_growth_rates",
        "operating_margin",
        "tax_rate",
        "da_pct_revenue",
        "capex_pct_revenue",
        "nwc_pct_revenue",
        "projection_years",
        "terminal_growth_rate",
    )

    # --- Mapping interface, for backwards compatibility ---
    def __getitem__(self, key: str):
        if key not in self._KEYS:
            raise KeyError(key)
        return getattr(self, key)

    def __contains__(self, key: object) -> bool:
        return key in self._KEYS

    def keys(self):
        return iter(self._KEYS)

    def items(self):
        return ((k, getattr(self, k)) for k in self._KEYS)

    def values(self):
        return (getattr(self, k) for k in self._KEYS)

    def get(self, key: str, default=None):
        return getattr(self, key) if key in self._KEYS else default

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self._KEYS}


@dataclass
class ProjectionAssumptions:
    """User-configurable assumptions for financial projections."""

    projection_years: int = config.DEFAULT_PROJECTION_YEARS
    terminal_growth_rate: float = config.DEFAULT_TERMINAL_GROWTH_RATE

    # Revenue growth — list per year or single rate applied to all
    revenue_growth_rates: list[float] = field(default_factory=list)

    # Margins (as decimals)
    operating_margin: float | None = None  # None = use historical average
    tax_rate: float | None = None  # None = derive from financials

    # CapEx & Working Capital (as % of revenue)
    capex_pct_revenue: float | None = None  # None = use historical average
    da_pct_revenue: float | None = None  # None = use historical average
    nwc_pct_revenue: float | None = None  # None = use historical average

    # WACC overrides
    risk_free_rate: float | None = None  # None = fetch live (^TNX), else config fallback
    equity_risk_premium: float | None = None  # None = config default; "realised" = trailing S&P
    cost_of_debt_override: float | None = None
    beta_override: float | None = None

    # Price data
    beta_lookback_years: int = config.DEFAULT_BETA_LOOKBACK_YEARS
    return_frequency: str = config.DEFAULT_RETURN_FREQUENCY  # "daily" or "monthly"
