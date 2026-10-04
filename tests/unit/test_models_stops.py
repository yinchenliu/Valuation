"""Rule-3 stops in `models/financial_statements.py`: backlog items 15 and 39.

Added by `P13b-tests` to lock what `P13b-models-silent` changed. Every expected
value here was fixed before the code ran:

* the latest year of a set of fiscal years is their maximum, read off the
  inputs the test itself writes (2023, 2025, 2024 -> 2025);
* the two stops are stated by rule 3 (`docs/2-rules/rules.md`): an absent input
  stops and names itself. The words asserted are the ones the assignment
  requires the message to carry, not text copied from a run.

**What this file does not assert.** It never asserts that an empty
`FinancialStatements` has a latest year of `0`, and it never asserts that a
`NonRecurringItem` built without a confidence reads as `"high"`. Those are the
two defaults the unit removed; asserting either would make them permanent.
"""

from __future__ import annotations

from dataclasses import MISSING, fields

import pytest

from models.financial_statements import (
    BalanceSheet,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)

# --------------------------------------------------------------------------
# Backlog item 15: `FinancialStatements.latest_year` with no statements.
# --------------------------------------------------------------------------


def test_latest_year_with_no_statements_stops_and_says_there_is_none() -> None:
    """No income statements means no latest year. Year 0 is not a fiscal year.

    Before `P13b-models-silent`, `latest_year` returned `0`, and every lookup
    keyed on it (`get_balance_sheet(0)`, `get_income_statement(0)`) quietly
    found nothing. Rule 3: the absent input stops and names itself.
    """
    with pytest.raises(ValueError) as excinfo:
        _ = FinancialStatements(ticker="EMPTY").latest_year

    message = str(excinfo.value)
    assert "no latest year" in message      # what is missing
    assert "income statements" in message   # why: the input it is read from
    assert "EMPTY" in message               # which extraction


def test_latest_year_ignores_balance_sheets_when_there_is_no_income_statement() -> None:
    """`years` is read from the income statements alone (`models/financial_statements.py`,
    `FinancialStatements.years`). A balance sheet with no income statement still
    leaves no latest year, so the same stop fires and no year is invented from
    the balance sheet.
    """
    financials = FinancialStatements(
        ticker="BSONLY",
        balance_sheets=[BalanceSheet(year=2025, cash_and_equivalents=10.0, printed_unit_in_millions=1.0)],
    )

    with pytest.raises(ValueError, match="no latest year"):
        _ = financials.latest_year


def test_latest_year_with_two_years_is_the_later_one() -> None:
    """The control for the stop. Statements for 2024 and 2025 -> 2025.

    Written in descending order so that "the last one in the list" and "the
    later year" disagree; only the maximum gives 2025.
    """
    financials = FinancialStatements(
        ticker="TWO",
        income_statements=[IncomeStatement(year=2025), IncomeStatement(year=2024)],
    )

    assert financials.latest_year == 2025


def test_latest_year_is_the_maximum_not_the_last_listed() -> None:
    """Three years listed 2023, 2025, 2024: max(2023, 2025, 2024) = 2025."""
    financials = FinancialStatements(
        ticker="THREE",
        income_statements=[
            IncomeStatement(year=2023),
            IncomeStatement(year=2025),
            IncomeStatement(year=2024),
        ],
    )

    assert financials.latest_year == 2025


# --------------------------------------------------------------------------
# Backlog item 39: `NonRecurringItem.confidence` is required.
# --------------------------------------------------------------------------


def test_a_non_recurring_item_without_confidence_cannot_be_built() -> None:
    """An absent confidence must not arrive as the strongest reading.

    Before `P13b-models-silent` the field defaulted to `"high"`, so an item
    whose confidence was never extracted was applied in full. Leaving it out
    now raises at construction, naming the field.
    """
    with pytest.raises(TypeError, match="confidence"):
        NonRecurringItem(  # type: ignore[call-arg]
            year=2025,
            description="Restructuring charge",
            amount=50.0,
            line_item="sga",
            direction="add_back",
            category="restructuring",
            source="Note 12",
        )


def test_the_confidence_field_carries_no_default_of_any_kind() -> None:
    """Structural form of the same requirement: neither a default nor a factory.

    A `default_factory` returning `"high"` would pass a test that only checks
    the plain default, and would rebuild the defect.
    """
    (confidence,) = [f for f in fields(NonRecurringItem) if f.name == "confidence"]

    assert confidence.default is MISSING
    assert confidence.default_factory is MISSING


@pytest.mark.parametrize("value", ["high", "medium", "low"])
def test_a_supplied_confidence_is_kept_as_given(value: str) -> None:
    """The control: each of the three legal tags builds and reads back unchanged."""
    item = NonRecurringItem(
        year=2025,
        description="Restructuring charge",
        amount=50.0,
        line_item="sga",
        direction="add_back",
        category="restructuring",
        confidence=value,
    )

    assert item.confidence == value
