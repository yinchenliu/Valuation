from __future__ import annotations

from dataclasses import dataclass, field


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
    amount: float           # absolute value, same units as F/S (e.g. $M)
    line_item: str          # IncomeStatement field name (see above)
    direction: str          # "add_back" | "remove"
    category: str
    confidence: str = "high"   # "high" | "medium" | "low"
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
        """Available years sorted ascending."""
        year_set = set()
        for stmt in self.income_statements:
            year_set.add(stmt.year)
        return sorted(year_set)

    def get_income_statement(self, year: int) -> IncomeStatement | None:
        return next((s for s in self.income_statements if s.year == year), None)

    def get_balance_sheet(self, year: int) -> BalanceSheet | None:
        return next((s for s in self.balance_sheets if s.year == year), None)

    def get_cash_flow(self, year: int) -> CashFlowStatement | None:
        return next((s for s in self.cash_flow_statements if s.year == year), None)

    @property
    def latest_year(self) -> int:
        return max(self.years) if self.years else 0
