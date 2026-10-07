from __future__ import annotations

from dataclasses import dataclass, field

# The balance sheet check's tolerance, in PRINTED UNITS: 1 in the unit the filing
# prints its figures in (1 million for a filing in millions, 1 thousand for a filing
# in thousands). A printed total and the sum of the lines mapped under it may differ
# by rounding and by nothing more: the user's decision of 2026-10-02, "if the
# balance sheet check doesn't pass, just fail it and show it". It decides a status,
# never a figure, and every output that shows the status names it.
#
# The figures a BalanceSheet holds are in millions after the conversion
# (`claude_extractor.convert_filing_to_millions`, P14a), so the threshold in
# millions is this times `BalanceSheet.printed_unit_in_millions`: 0.001 for a
# filing in thousands, 1 for a filing in millions.
BALANCE_CHECK_TOLERANCE = 1.0

# Decimal places, in printed units, to which a balance check difference is rounded
# before it is compared with the tolerance. Not a figure and not an assumption about
# the company: it removes the binary floating-point noise the conversion to millions
# leaves (a filing in thousands: each figure divided by 1,000, and 0.001 has no exact
# binary form, so a gap of exactly 1 printed unit reads as 0.99999999999 or
# 1.00000000001 printed units, about 1e-8 either side). No statement prints a figure
# to a millionth of its unit, so rounding there changes no real difference. It
# decides only whether a gap of exactly 1 printed unit reads as 1, as it does on the
# page.
PRINTED_UNIT_DECIMALS = 6


def printed_total_status(difference_in_printed_units: float | None) -> str:
    """'OK', 'FAIL' or 'FAIL: not extracted' for one printed-total difference given
    in the filing's printed units.

    FAIL when the difference exceeds BALANCE_CHECK_TOLERANCE (1 printed unit, after
    rounding to PRINTED_UNIT_DECIMALS): rounding, and nothing more. The user decided
    on 2026-10-02 that a balance sheet that does not pass is failed and shown, never
    repaired. The one threshold for the parser (which checks the figures as printed,
    before the conversion), the CLI and the page (which check them in millions,
    through BalanceSheet.printed_total_check).

    None (the printed total was not extracted) fails too, and says why: every
    balance sheet prints both totals, so a missing one is a reading that did not
    happen, never a pass and never a printed 0 (review F1).
    """
    if difference_in_printed_units is None:
        return "FAIL: not extracted"
    gap = round(abs(difference_in_printed_units), PRINTED_UNIT_DECIMALS)
    return "FAIL" if gap > BALANCE_CHECK_TOLERANCE else "OK"


@dataclass
class NonRecurringItem:
    """A non-recurring / one-time item identified by the LLM from the filing.

    direction:
      "add_back" — an expense that inflated costs; remove it to get a clean base.
      "remove"   — a gain that inflated income; strip it to get a clean base.

    line_item: the IncomeStatement field name this item sits in, e.g. "sga",
      "cost_of_revenue", "rd_expense", "depreciation_amortization",
      "other_operating_expense", or "other_non_operating".

    category:
      restructuring | impairment | litigation | gain_loss_asset_sale |
      acquisition_costs | covid | other
    """
    year: int
    description: str
    amount: float           # as printed until convert_filing_to_millions; in millions after
    line_item: str          # IncomeStatement field name (see above)
    direction: str          # "add_back" | "remove"
    category: str
    # "high" | "medium" | "low". Required, with no default: an absent
    # confidence must not arrive as the strongest reading. Rule 3; backlog
    # item 39.
    confidence: str
    page: int
    printed_units: str
    units_page: int
    source: str = ""           # e.g. "Note 12 — Restructuring charges"

    @property
    def adjusted_impact(self) -> float:
        """Signed impact on operating income after adjustment.
        add_back -> positive (removes expense -> improves EBIT)
        remove   -> negative (removes gain   -> reduces EBIT)
        """
        return self.amount if self.direction == "add_back" else -self.amount


@dataclass
class IncomeStatement:
    """Single-period income statement."""

    year: int

    # Revenue
    revenue: float = 0.0
    cost_of_revenue: float = 0.0

    # Gross profit
    @property
    def gross_profit(self) -> float:
        return self.revenue - self.cost_of_revenue

    @property
    def gross_margin(self) -> float:
        return self.gross_profit / self.revenue if self.revenue else 0.0

    # Operating expenses
    sga: float = 0.0  # Selling, General & Administrative
    rd_expense: float = 0.0  # Research & Development
    depreciation_amortization: float = 0.0
    other_operating_expense: float = 0.0

    @property
    def total_operating_expenses(self) -> float:
        return (
            self.cost_of_revenue
            + self.sga
            + self.rd_expense
            + self.depreciation_amortization
            + self.other_operating_expense
        )

    @property
    def ebit(self) -> float:
        return self.revenue - self.total_operating_expenses

    @property
    def operating_margin(self) -> float:
        return self.ebit / self.revenue if self.revenue else 0.0

    # Below operating line
    interest_expense: float = 0.0
    interest_income: float = 0.0
    other_non_operating: float = 0.0

    @property
    def ebt(self) -> float:
        """Earnings before tax."""
        return self.ebit - self.interest_expense + self.interest_income + self.other_non_operating

    tax_expense: float = 0.0

    @property
    def net_income(self) -> float:
        return self.ebt - self.tax_expense

    @property
    def effective_tax_rate(self) -> float:
        return self.tax_expense / self.ebt if self.ebt else 0.0

    # Share data
    diluted_shares_outstanding: float = 0.0

    @property
    def eps(self) -> float:
        return self.net_income / self.diluted_shares_outstanding if self.diluted_shares_outstanding else 0.0

    # Non-recurring items (populated during GAAP→Non-GAAP adjustment)
    non_recurring_items: dict[str, float] = field(default_factory=dict)


@dataclass
class BalanceSheet:
    """Single-period balance sheet."""

    year: int

    # Current assets
    cash_and_equivalents: float = 0.0
    short_term_investments: float = 0.0
    accounts_receivable: float = 0.0
    inventory: float = 0.0
    other_current_assets: float = 0.0

    @property
    def total_current_assets(self) -> float:
        return (
            self.cash_and_equivalents
            + self.short_term_investments
            + self.accounts_receivable
            + self.inventory
            + self.other_current_assets
        )

    # Non-current assets
    ppe_net: float = 0.0  # Property, Plant & Equipment (net)
    goodwill: float = 0.0
    intangible_assets: float = 0.0
    other_non_current_assets: float = 0.0

    @property
    def total_assets(self) -> float:
        return (
            self.total_current_assets
            + self.ppe_net
            + self.goodwill
            + self.intangible_assets
            + self.other_non_current_assets
        )

    # Current liabilities
    accounts_payable: float = 0.0
    short_term_debt: float = 0.0
    current_portion_lt_debt: float = 0.0
    accrued_liabilities: float = 0.0
    other_current_liabilities: float = 0.0

    @property
    def total_current_liabilities(self) -> float:
        return (
            self.accounts_payable
            + self.short_term_debt
            + self.current_portion_lt_debt
            + self.accrued_liabilities
            + self.other_current_liabilities
        )

    # Non-current liabilities
    long_term_debt: float = 0.0
    other_non_current_liabilities: float = 0.0

    @property
    def total_liabilities(self) -> float:
        return (
            self.total_current_liabilities
            + self.long_term_debt
            + self.other_non_current_liabilities
        )

    # Equity
    total_equity: float = 0.0

    # Memo: the noncontrolling interests, as the two lines the filing prints —
    # the nonredeemable amount inside equity, and the redeemable amount shown
    # outside it (mezzanine). Each is already inside `total_equity` or another
    # line, so neither is part of any total below nor of the balance check.
    # The equity bridge subtracts their sum, computed in Python by
    # `analysis/dcf.py:total_noncontrolling_interest`, because Pass 1's net
    # income and cash flows are consolidated and so value the whole group.
    #
    # None is not a zero default: it means "not extracted", and that function
    # stops on it and names the key (rule 3). A filing that prints no such line
    # is extracted as an explicit 0.
    noncontrolling_interest_nonredeemable: float | None = None
    noncontrolling_interest_redeemable: float | None = None

    # Memo: the two totals the filing PRINTS, each read off its total row, used
    # only to check the reading. They are in no total and no figure: the check
    # compares each with the sum of the mapped lines above (`total_assets`, and
    # `total_liabilities + total_equity`). None is not a zero default: it means
    # "not extracted" (also what an empty list of printed lines gives), and the
    # check then FAILs saying so instead of passing (rule 3).
    printed_total_assets: float | None = None
    printed_total_liabilities_and_equity: float | None = None

    # What ONE PRINTED UNIT of the filing is, in millions: 0.001 for a filing that
    # prints in thousands, 1.0 for millions, 1000.0 for billions. Set by the
    # conversion to millions (`claude_extractor.convert_filing_to_millions`), from
    # the money scale Python reads in the filing's printed unit statement (P14a).
    # The balance check's threshold is BALANCE_CHECK_TOLERANCE of these.
    #
    # Required, with no default: a default would assume millions, and a filing in
    # thousands would then be checked at 1,000 printed units (rule 3). None is
    # stated explicitly by the parser, whose figures are still as printed: it means
    # "not converted to millions", and the check stops on it, naming this field.
    printed_unit_in_millions: float | None = field(kw_only=True)

    # Derived
    @property
    def total_debt(self) -> float:
        return self.short_term_debt + self.current_portion_lt_debt + self.long_term_debt

    @property
    def net_debt(self) -> float:
        """Net debt = total financial debt minus all liquid assets (cash + short-term investments).

        Short-term investments (marketable securities) are included because they are
        liquid, investment-grade assets that can service debt or be returned to shareholders.
        This follows standard investment banking equity bridge convention.
        """
        return self.total_debt - self.cash_and_equivalents - self.short_term_investments

    @property
    def balance_check_difference(self) -> float:
        return self.total_assets - (self.total_liabilities + self.total_equity)

    @property
    def total_liabilities_and_equity(self) -> float:
        """The sum of the mapped liability and equity lines. The NCI memos are not in it."""
        return self.total_liabilities + self.total_equity

    @property
    def printed_total_assets_difference(self) -> float | None:
        """Printed total assets minus the mapped asset lines. None: total not extracted."""
        if self.printed_total_assets is None:
            return None
        return self.printed_total_assets - self.total_assets

    @property
    def printed_total_liabilities_and_equity_difference(self) -> float | None:
        """Printed total L+E minus the mapped L+E lines. None: total not extracted."""
        if self.printed_total_liabilities_and_equity is None:
            return None
        return self.printed_total_liabilities_and_equity - self.total_liabilities_and_equity

    def printed_unit(self) -> float:
        """`printed_unit_in_millions`, or a stop naming it when it is None.

        None means the figures are still as printed, not in millions, so no
        threshold in millions can be stated for them (rule 3).
        """
        if self.printed_unit_in_millions is None:
            raise ValueError(
                f"BalanceSheet {self.year}: 'printed_unit_in_millions' is None, so "
                "these figures were never converted to millions, and the balance "
                "check's threshold (1 printed unit, in millions) is not known. "
                "Convert the filing with claude_extractor.convert_filing_to_millions."
            )
        return self.printed_unit_in_millions

    def printed_total_check(self, difference: float | None) -> str:
        """'OK', 'FAIL' or 'FAIL: not extracted' for one printed-total difference in
        millions, at 1 printed unit: `printed_total_status` of the difference
        expressed in printed units. The CLI and the page call this.

        Raises:
            ValueError: `printed_unit_in_millions` is None (never converted).
        """
        unit = self.printed_unit()
        return printed_total_status(None if difference is None else difference / unit)

    def printed_total_tolerance(self) -> float:
        """The threshold `printed_total_check` applies, in millions:
        BALANCE_CHECK_TOLERANCE printed units. A template reaches it through `bs`,
        so the threshold it prints is the one the check applies.

        Raises:
            ValueError: `printed_unit_in_millions` is None (never converted).
        """
        return BALANCE_CHECK_TOLERANCE * self.printed_unit()

    def printed_unit_decimals(self) -> int:
        """Decimal places of $M that show one printed unit: 0 for a filing in
        millions or billions, 3 for one in thousands. Display only, so a gap of
        0.002 $M is not printed as 0 beside a FAIL.

        Raises:
            ValueError: `printed_unit_in_millions` is None (never converted).
        """
        unit = self.printed_unit()
        if unit >= 1:
            return 0
        return len(f"{unit:f}".rstrip("0").split(".")[1])

    @property
    def net_working_capital(self) -> float:
        """Operating working capital (excludes cash and debt)."""
        current_operating_assets = self.accounts_receivable + self.inventory + self.other_current_assets
        current_operating_liabilities = (
            self.accounts_payable + self.accrued_liabilities + self.other_current_liabilities
        )
        return current_operating_assets - current_operating_liabilities


@dataclass
class CashFlowStatement:
    """Single-period cash flow statement."""

    year: int

    # Operating activities
    net_income: float = 0.0
    depreciation_amortization: float = 0.0
    stock_based_compensation: float = 0.0
    change_in_working_capital: float = 0.0
    other_operating_activities: float = 0.0

    @property
    def cash_from_operations(self) -> float:
        return (
            self.net_income
            + self.depreciation_amortization
            + self.stock_based_compensation
            + self.change_in_working_capital
            + self.other_operating_activities
        )

    # Investing activities
    capital_expenditures: float = 0.0  # Typically negative
    acquisitions: float = 0.0
    other_investing_activities: float = 0.0

    @property
    def cash_from_investing(self) -> float:
        return self.capital_expenditures + self.acquisitions + self.other_investing_activities

    # Financing activities
    debt_issued: float = 0.0
    debt_repaid: float = 0.0
    shares_issued: float = 0.0
    shares_repurchased: float = 0.0
    dividends_paid: float = 0.0
    other_financing_activities: float = 0.0

    @property
    def cash_from_financing(self) -> float:
        return (
            self.debt_issued
            + self.debt_repaid
            + self.shares_issued
            + self.shares_repurchased
            + self.dividends_paid
            + self.other_financing_activities
        )

    @property
    def net_change_in_cash(self) -> float:
        return self.cash_from_operations + self.cash_from_investing + self.cash_from_financing


@dataclass
class FinancialStatements:
    """Container for multiple years of financial statements."""

    ticker: str
    company_name: str = ""
    income_statements: list[IncomeStatement] = field(default_factory=list)
    balance_sheets: list[BalanceSheet] = field(default_factory=list)
    cash_flow_statements: list[CashFlowStatement] = field(default_factory=list)

    @property
    def years(self) -> list[int]:
        """Every fiscal year ANY of the three statements covers, ascending.

        The set is built from `income_statements`, `balance_sheets` AND
        `cash_flow_statements`.

        Until `P3d-invisible-year` it was built from `income_statements`
        alone, so a year that had a cash flow statement and a balance sheet
        but no income statement was in no table, carried no reason, and
        nothing anywhere reported it — its figures were extracted and then
        dropped without a word. Both entry points held a branch written to
        report exactly that case (`cli.print_historical_fcff` and
        `api/routes_valuation._historical_fcff_by_year`), and neither could
        run, because both iterate this list. Backlog item 116.

        **A year in this list is not a year with an income statement.** A
        caller that needs one for every year reads `income_statement_years`
        (`cli.print_extracted_financials`'s income statement table,
        `claude_extractor._build_is_summary`), or reads this list and stops
        naming the year it cannot serve
        (`analysis/projector.derive_assumptions`). It never reads
        `get_income_statement(y).<field>` off this list: that is `None.<field>`,
        an `AttributeError` naming no field, which is the same silent omission
        with a louder failure.
        """
        year_set: set[int] = set()
        for income in self.income_statements:
            year_set.add(income.year)
        for balance in self.balance_sheets:
            year_set.add(balance.year)
        for cash_flow in self.cash_flow_statements:
            year_set.add(cash_flow.year)
        return sorted(year_set)

    @property
    def income_statement_years(self) -> list[int]:
        """The fiscal years that HAVE an income statement, ascending.

        A subset of `years`, which covers every year any statement reaches.
        `get_income_statement(y)` returns a statement, never `None`, for every
        year in this list and for no other.
        """
        return sorted({income.year for income in self.income_statements})

    def get_income_statement(self, year: int) -> IncomeStatement | None:
        return next((s for s in self.income_statements if s.year == year), None)

    def get_balance_sheet(self, year: int) -> BalanceSheet | None:
        return next((s for s in self.balance_sheets if s.year == year), None)

    def get_cash_flow(self, year: int) -> CashFlowStatement | None:
        return next((s for s in self.cash_flow_statements if s.year == year), None)

    @property
    def latest_year(self) -> int:
        """The most recent fiscal year with an income statement.

        Raises `ValueError` when there are no income statements. There is then
        no latest year, and year 0 is not one: it would read as a fiscal year
        and every lookup keyed on it would quietly find nothing. Rule 3;
        backlog item 15.

        **It reads `income_statement_years`, not `years`.** Since
        `P3d-invisible-year`, `years` covers every year any statement reaches,
        so a filing can hold a balance sheet and no income statement at all:
        `years` would be non-empty while the message below says there are no
        income statements. Reading the narrow set keeps the message true when
        it prints, and keeps `get_income_statement(latest_year)` a statement
        for every caller that follows this property with that call
        (`pipeline.value_company`, `analysis/projector.project_fcffs`,
        `analysis/dcf`). Backlog item 116, fact 4.
        """
        years = self.income_statement_years
        if not years:
            raise ValueError(
                f"FinancialStatements for {self.ticker!r} holds no income "
                "statements, so there is no latest year. Extract at least one "
                "year of the filing; year 0 is not substituted."
            )
        return max(years)
