from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

# ---------------------------------------------------------------------------
# Provenance labels — rule 6
#
# Three numbers reach the share price without being read from a filing or
# derived by formula from one: the risk-free rate, the beta, and the cost of
# debt. Rule 6 requires each to carry "a name, a default, the reason for that
# default", visible to the user. Before this, all three were rendered as bare
# percentages indistinguishable from a measurement.
#
# These are string CONSTANTS, not a dispatch table. Nothing looks a function up
# by one of them; the producing function assigns one and the two output layers
# print it verbatim. Rule 2's ban is on looking up *behaviour*.
#
# Every `*_UNRECORDED` / `*_NOT_ASSESSED` value is the dataclass default, and
# each one says in words that nothing was recorded. A default that claimed
# "measured" would be the very defect these fields exist to close, and a
# default of "" would render as a blank cell that reads as "fine".
# ---------------------------------------------------------------------------

RISK_FREE_SOURCE_UNRECORDED: Final = (
    "not recorded — this result was built without recording where its "
    "risk-free rate came from"
)
RISK_FREE_SOURCE_SUBSTITUTED: Final = (
    "ASSUMPTION — config.DEFAULT_RISK_FREE_RATE. No rate was supplied and this "
    "platform fetches no treasury series, so the configured constant was "
    "substituted. It is not a measurement of any market."
)
RISK_FREE_SOURCE_SUPPLIED: Final = (
    "supplied by the caller (--risk-free-rate / "
    "ProjectionAssumptions.risk_free_rate). Still an assumption, not a "
    "measurement: nothing in this platform reads a treasury rate."
)

BETA_SOURCE_UNRECORDED: Final = (
    "not recorded — this result was built without recording where its beta "
    "came from"
)
BETA_SOURCE_REGRESSION: Final = (
    "measured — OLS regression of this stock's returns on the S&P 500's, over "
    "the price history named beside it"
)
BETA_SOURCE_OVERRIDE: Final = (
    "ASSUMPTION — supplied by the caller (--beta / "
    "ProjectionAssumptions.beta_override). No regression was run."
)

BETA_RELIABILITY_NOT_ASSESSED: Final = (
    "not assessed — no regression was run, so there is no R-squared to judge"
)


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

    # Provenance — rule 6. Defaulted so that every construction predating these
    # fields still builds; each default states that nothing was recorded.
    #
    # KNOWN, NOT FIXED HERE: on the beta-override path `analysis/capm.py` sets
    # `r_squared` and `std_error` to 0.0, which is indistinguishable from a
    # regression that explained nothing (backlog item 1, and the module
    # docstring of tests/unit/test_capm.py). `beta_source` now tells the two
    # apart, and `beta_reliability` is NOT_ASSESSED rather than "weak" on that
    # path, so the zero no longer reads as a diagnostic. Changing the fields to
    # `float | None` would change the meaning of existing assertions.
    risk_free_rate_source: str = RISK_FREE_SOURCE_UNRECORDED
    beta_source: str = BETA_SOURCE_UNRECORDED
    beta_reliability: str = BETA_RELIABILITY_NOT_ASSESSED


COST_OF_DEBT_SOURCE_UNRECORDED: Final = (
    "not recorded — this result was built without recording where its cost of "
    "debt came from"
)


@dataclass
class WACCResult:
    """Output of WACC calculation."""

    cost_of_equity: float
    cost_of_debt: float
    tax_rate: float
    equity_weight: float  # E / V
    debt_weight: float  # D / V

    # Provenance — rule 6, backlog item 9. `analysis/wacc.py` substitutes
    # `config.DEFAULT_COST_OF_DEBT` whenever interest expense is not reported
    # separately; that substitution reaches WACC, every discounted cash flow,
    # and the share price. This field is what says so in the output.
    cost_of_debt_source: str = COST_OF_DEBT_SOURCE_UNRECORDED

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
class ProjectionAssumptions:
    """User-configurable assumptions for financial projections."""

    projection_years: int = 5
    terminal_growth_rate: float = 0.025  # 2.5%

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
    # None means "the caller did not supply one", and NOT "fetch it from the
    # market" as this comment used to claim — nothing in this platform reads a
    # treasury series. None is what makes the substitution reachable: on None,
    # `analysis/capm.py` substitutes `config.DEFAULT_RISK_FREE_RATE` and
    # records RISK_FREE_SOURCE_SUBSTITUTED, which both outputs print. A caller
    # that always passes a number can never produce that label — which is
    # exactly what `api/routes_valuation.py`'s `Form(4.0)` did.
    risk_free_rate: float | None = None
    equity_risk_premium: float | None = None  # None = historical S&P 500 return - risk-free rate
    cost_of_debt_override: float | None = None
    beta_override: float | None = None

    # Price data
    beta_lookback_years: int = 5
    return_frequency: str = "monthly"  # "daily" or "monthly"
