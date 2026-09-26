"""DELIBERATELY RED. Read this docstring before you touch anything in here.

The test below states the behaviour [rule 3](../../docs/2-rules/rules.md)
requires — *a missing input stops the run and names the field* — not the
behaviour `analysis/dcf.py` has today. It **fails** at `bc19431`, and that is
the point: a red test that states a true requirement is doing its job
(`docs/5-testing/strategy.md` section 2).

It is not a regression. It was written red, on purpose, by unit `P1-suite`.

The alternative was to assert `net_debt == 0.0`, which would have made
`analysis/dcf.py:80-81` permanent and turned its fix red. The strategy document
names that as the single most damaging thing a test here could do.

**Do not weaken, skip or `xfail` this to make the suite green.** It goes green
when `analysis/dcf.py` raises. That is backlog item 2
(`docs/9-reference/refactor-backlog.md`), scheduled for phase 4, and it is
outside the write scope of the unit that wrote this file.
"""

from __future__ import annotations

import pytest

from analysis.dcf import run_dcf
from models.financial_statements import FinancialStatements, IncomeStatement
from models.valuation import ProjectedFCFF, WACCResult


def test_run_dcf_stops_when_the_balance_sheet_is_absent() -> None:
    """Enterprise value cannot be bridged to equity value without net debt.

    `analysis/dcf.py:80-81` substitutes `net_debt = 0.0` and `cash = 0.0` when
    the latest year has no balance sheet. On a clean run with no warning
    anywhere, equity value is then overstated by the entire debt balance and
    the implied share price with it. A zero that means "we do not know" and a
    zero that means "zero" are the same bytes.

    The required behaviour is a stop that names the missing input. The
    exception type asserted here is `ValueError`, which is what the rest of
    this codebase raises for an absent input — see
    `ingestion/claude_extractor.py:835`.
    """
    financials = FinancialStatements(
        ticker="TEST",
        company_name="Test Co",
        income_statements=[IncomeStatement(year=2025)],
        balance_sheets=[],  # the missing input
    )
    wacc_result = WACCResult(
        cost_of_equity=0.10,
        cost_of_debt=0.0,
        tax_rate=0.0,
        equity_weight=1.0,
        debt_weight=0.0,
    )
    projected = [
        ProjectedFCFF(
            year=2026,
            revenue=0.0,
            ebit=0.0,
            nopat=100.0,
            depreciation_amortization=0.0,
            capital_expenditures=0.0,
            change_in_working_capital=0.0,
        )
    ]

    with pytest.raises(ValueError) as excinfo:
        run_dcf(
            projected_fcffs=projected,
            wacc_result=wacc_result,
            financials=financials,
            terminal_growth_rate=0.0,
            current_price=20.0,
            diluted_shares=10.0,
        )

    message = str(excinfo.value).lower()
    assert (
        "balance sheet" in message
        or "balance_sheet" in message
        or "net debt" in message
        or "net_debt" in message
    ), f"the message must name the missing input, got: {message!r}"
