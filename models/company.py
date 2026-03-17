from __future__ import annotations

from dataclasses import dataclass

from models.financial_statements import FinancialStatements


@dataclass
class Company:
    """Represents a company being analyzed."""

    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    current_price: float = 0.0
    diluted_shares_outstanding: float = 0.0
    financials: FinancialStatements | None = None

    @property
    def market_cap(self) -> float:
        return self.current_price * self.diluted_shares_outstanding
