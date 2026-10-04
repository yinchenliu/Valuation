from __future__ import annotations

import math
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


# ---------------------------------------------------------------------------
# Provenance labels for the six projection ratios — rule 6
#
# `analysis/projector.py` produces six ratios and a reader cannot tell them
# apart once each is rendered as a percentage. THREE things can produce one,
# not two:
#
#   supplied     — the caller typed it into the form, or passed it on the CLI.
#   derived      — at least one filing-year fed the average or the CAGR.
#   substituted  — NO filing-year fed it. `_historical_average([])` returns
#                  0.0 and `_historical_cagr` returns 0.0 on a non-positive or
#                  degenerate revenue window (backlog item 1), so a ratio can
#                  reach the page as a confident 0.0% that nothing measured.
#
# Round 1 of `P8a-statements-data` had only the first two states and said
# "derived from the filing's history" over the third. On a filing with income
# statements and no cash flow statements that is a false claim about three
# ratios at once, made in the same render where `historical_fcff` reports that
# the cash flow statement was never extracted. Code reviewer finding F1.
#
# Two of the three sentences carry a fact about the particular run — how many
# years fed it, or which default replaced it — so they are format templates
# rather than finished strings. The invariant words are still written once,
# here, beside the labels they belong to. Nothing is looked up by one of these
# values and none of them is called: rule 2's ban is on looking up behaviour.
# ---------------------------------------------------------------------------

ASSUMPTION_ORIGIN_SUPPLIED: Final = "supplied"
ASSUMPTION_ORIGIN_DERIVED: Final = "derived"
ASSUMPTION_ORIGIN_SUBSTITUTED: Final = "substituted"

ASSUMPTION_SOURCE_SUPPLIED: Final = (
    "supplied by the caller — the assumptions form, or the matching CLI "
    "option. Still an assumption, not a measurement: nothing in this platform "
    "checks a figure you typed against the filing."
)
ASSUMPTION_SOURCE_DERIVED_TEMPLATE: Final = (
    "derived from the filing: {observations} filing-year(s) of extracted data "
    "fed it. It measures those years; that they continue is the assumption."
)
ASSUMPTION_SOURCE_SUBSTITUTED_TEMPLATE: Final = (
    "ASSUMPTION — SUBSTITUTED. Nothing from the filing fed this figure — no "
    "year contributed an observation — so {default_value} was used in place "
    "of a derivation. It is not a measurement."
)

# Appended to whichever sentence above applies. Each names a step this
# platform took that the filing did not, and each can land on a figure that
# is otherwise supplied or otherwise derived, so none is a fourth origin.
# Padding and truncation exclude each other: a growth list is either shorter
# than the projection or longer than it.
ASSUMPTION_CLAMPED_CLAUSE_TEMPLATE: Final = (
    " It was then CLAMPED into the {low} to {high} band this platform "
    "imposes: {pre_clamp} fell outside it, so {post_clamp} is the figure "
    "every calculation downstream used."
)
ASSUMPTION_PADDED_CLAUSE_TEMPLATE: Final = (
    " The projection runs {projection_years} year(s) and only "
    "{supplied_years} rate(s) reached it, so the last rate was REPEATED to "
    "fill the remainder. The repeat is this platform's, and it is not in the "
    "filing."
)
ASSUMPTION_TRUNCATED_CLAUSE_TEMPLATE: Final = (
    " {supplied_years} rate(s) were supplied and the projection runs "
    "{projection_years} year(s), so only the first {projection_years} were "
    "used and the last {dropped_years} were DROPPED. The dropped rates reach "
    "no figure in this valuation."
)


@dataclass(frozen=True)
class AssumptionSource:
    """Where one projection ratio came from. Rule 6.

    Every field is required and nothing is defaulted. A source that cannot say
    which of the three origins produced its ratio is not a source, and a field
    defaulting to `derived` would be finding F1 rebuilt: the claim a reader
    trusts least should never be the one that arrives for free.

    `observations` is the number of filing-years that fed the figure. It is
    `0` when the ratio was supplied (no filing-year fed it — the caller did)
    and `0` when it was substituted (no filing-year fed it — a default did),
    and `origin` is what tells those two apart.
    """

    origin: str          # exactly one of the three ASSUMPTION_ORIGIN_* constants
    detail: str          # the sentence a reader sees
    observations: int    # filing-years that fed it; 0 when supplied or substituted


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


@dataclass(frozen=True)
class HistoricalFCFFYear:
    """One extracted year's historical FCFF, or the record that it has none.

    A year whose income statement or cash flow statement was not extracted is
    carried here with `is_computable=False` and `fcff=None`, and
    `missing_statements` names what was absent. It is NOT dropped, as
    `cli.py:721-722` drops it with a bare `continue`, because a reader cannot
    tell a dropped year from a year that was never extracted; and it is NOT
    given a `HistoricalFCFF` full of zeros, because a zero that means "we do
    not know" and a zero that means "zero" are the same bytes (rule 3).

    Nothing is defaulted, so a row that cannot say whether its FCFF was
    computable cannot be built at all.

    (Written in `api/routes_valuation.py` at round 1 of `P8a-statements-data`
    because that unit's Files in scope held one file; moved here unchanged at
    round 2, per code reviewer finding F7. A record belongs in `models/`.)
    """

    year: int
    is_computable: bool
    fcff: HistoricalFCFF | None
    missing_statements: tuple[str, ...]


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

    # The noncontrolling interests' book value on the latest balance sheet: the
    # two printed lines (Pass 1 'noncontrolling_interest_nonredeemable' and
    # '_redeemable'), summed by analysis/dcf.py:total_noncontrolling_interest.
    # Subtracted because the
    # projected cash flows are consolidated and value the whole group, of which
    # this share is not the parent's. Keyword-only with NO default: a zero here
    # would be indistinguishable from "not extracted" (rule 3), so every
    # constructor must state it. `run_dcf` stops before building a result when
    # the balance sheet does not carry it.
    noncontrolling_interest: float = field(kw_only=True)
    # Where that figure came from, printed beside it in both outputs (rule 4).
    noncontrolling_interest_source: str = field(kw_only=True)

    @property
    def equity_value(self) -> float:
        """Equity Value = Enterprise Value - Net Debt - Noncontrolling Interest."""
        return self.enterprise_value - self.net_debt - self.noncontrolling_interest

    @property
    def implied_share_price(self) -> float:
        """Equity Value / diluted shares.

        Raises `ValueError` when `diluted_shares` is not a finite number
        greater than zero. A price of 0.0 for a missing share count would read
        as a company worth nothing. Rule 3; backlog item 32. `run_dcf` stops on
        the same input before it discounts anything; this guards a result
        built directly. Infinity is refused too: dividing by it would return
        the same 0.0. NaN is tested by `isfinite` because a guard written as a
        comparison, such as `<= 0`, lets NaN through.
        """
        if not (math.isfinite(self.diluted_shares) and self.diluted_shares > 0):
            raise ValueError(
                f"diluted_shares is {self.diluted_shares!r}, so there is no "
                "implied share price: equity value is divided by the diluted "
                "share count, and that count must be a number greater than zero."
            )
        return self.equity_value / self.diluted_shares

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
