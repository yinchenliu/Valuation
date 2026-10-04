"""Backlog item 25: an adjustment for a year with no income statement stops.

`normalize_financials` (`analysis/normalizer.py`) groups the non-recurring items
by year and walks the income statements. Until `P13a-analysis-silent`, an item
whose year matched no statement was never looked at: the adjustment was dropped
and the result was still labelled normalised. Rule 3
(`docs/2-rules/rules.md`): a missing input stops and names itself. The item's
year and the statements' years come from two separate extraction passes, so the
function cannot know which of the two is wrong; it must name both.

Every expected value here was written down **before the code ran**:

* the stop tests assert only what the assignment requires the message to name,
  and every name is an input the test itself supplied;
* the moved figures are hand arithmetic, written out above each assertion.

Nothing here needs an API key, a PDF or the network.
`docs/5-testing/strategy.md` sections 1 and 3.

Fixture, by hand. Two income statements, identical but for the year:

    revenue           1000
    cost_of_revenue    600
    sga                200
    EBIT = 1000 - 600 - 200 = 200

`confidence` is passed explicitly on every item. The applied/withheld split is
`partition_by_confidence`'s business, not this file's, and an explicit value
does not depend on whether the model gives the field a default (backlog item 39).
"""

from __future__ import annotations

import pytest

from analysis.normalizer import normalize_financials
from models.financial_statements import (
    BalanceSheet,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)

STATEMENT_YEARS = (2023, 2024)

# Descriptions carry no digits, so a year found in a message cannot have come
# from a description.
PLANT_CLOSURE = "Severance for the closure of the Ohio plant"
LAWSUIT = "Settlement of the patent lawsuit with a former supplier"
WAREHOUSE = "Write-down of a warehouse held for sale"


def _income_statement(year: int) -> IncomeStatement:
    return IncomeStatement(year=year, revenue=1000.0, cost_of_revenue=600.0, sga=200.0)


def _financials() -> FinancialStatements:
    return FinancialStatements(
        ticker="TEST",
        income_statements=[_income_statement(y) for y in STATEMENT_YEARS],
    )


def _item(
    year: int,
    description: str,
    line_item: str = "sga",
    amount: float = 50.0,
    direction: str = "add_back",
) -> NonRecurringItem:
    return NonRecurringItem(
        year=year,
        description=description,
        amount=amount,
        line_item=line_item,
        direction=direction,
        category="restructuring",
        confidence="high",
    )


# ---------------------------------------------------------------------------
# The stop
# ---------------------------------------------------------------------------


def test_an_item_for_a_year_with_no_income_statement_stops_and_names_itself() -> None:
    """Statements for 2023 and 2024, one item for 2019. The message must name
    the item's year, its `line_item`, its description, and the statement years
    that do exist, so a reader can see both sides of the mismatch.

    `rd_expense` is used rather than `sga` so that the `line_item` check cannot
    be satisfied by a word that happens to appear in the surrounding sentence.
    """
    with pytest.raises(ValueError) as raised:
        normalize_financials(_financials(), [_item(2019, PLANT_CLOSURE, line_item="rd_expense")])

    message = str(raised.value)
    assert "2019" in message
    assert "rd_expense" in message
    assert PLANT_CLOSURE in message
    assert "2023" in message
    assert "2024" in message


def test_two_unmatched_items_are_both_named_in_one_message() -> None:
    """Two items whose years (2019, 2020) match no statement. One raise, and it
    names both, so the user fixes both on one run rather than one per run.
    """
    items = [
        _item(2019, PLANT_CLOSURE, line_item="rd_expense"),
        _item(2020, LAWSUIT, line_item="other_operating_expense"),
    ]

    with pytest.raises(ValueError) as raised:
        normalize_financials(_financials(), items)

    message = str(raised.value)
    for year, line_item, description in (
        ("2019", "rd_expense", PLANT_CLOSURE),
        ("2020", "other_operating_expense", LAWSUIT),
    ):
        assert year in message
        assert line_item in message
        assert description in message
    assert "2023" in message
    assert "2024" in message


def test_one_unmatched_item_stops_the_run_even_beside_a_matched_one() -> None:
    """A 2024 item (which has a statement) and a 2019 item (which does not).
    The run stops rather than applying the 2024 item and returning: a result
    that holds some adjustments and silently lacks others is the defect.

    Only the unmatched item is named as unmatched; the matched item's
    description does not appear.
    """
    items = [
        _item(2024, WAREHOUSE),
        _item(2019, PLANT_CLOSURE, line_item="rd_expense"),
    ]

    with pytest.raises(ValueError) as raised:
        normalize_financials(_financials(), items)

    message = str(raised.value)
    assert PLANT_CLOSURE in message
    assert "2019" in message
    assert WAREHOUSE not in message


def test_a_balance_sheet_year_does_not_count_as_a_statement_year() -> None:
    """The adjustment moves an income statement field, so only an income
    statement year can receive it. A balance sheet for 2019 does not make a
    2019 item applicable.
    """
    financials = FinancialStatements(
        ticker="TEST",
        income_statements=[_income_statement(y) for y in STATEMENT_YEARS],
        balance_sheets=[BalanceSheet(year=2019)],
    )

    with pytest.raises(ValueError) as raised:
        normalize_financials(financials, [_item(2019, PLANT_CLOSURE)])

    assert "2019" in str(raised.value)
    assert PLANT_CLOSURE in str(raised.value)


# ---------------------------------------------------------------------------
# The matched path still applies, under its direction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("direction", "expected_sga", "expected_ebit"),
    [
        # add_back: a one-time expense inside sga is removed from it.
        #   sga  200 - 50 = 150;  EBIT 1000 - 600 - 150 = 250  (= 200 + 50)
        ("add_back", 150.0, 250.0),
        # remove: a one-time gain netted inside sga is stripped out, so the
        # expense line rises by it.
        #   sga  200 + 50 = 250;  EBIT 1000 - 600 - 250 = 150  (= 200 - 50)
        ("remove", 250.0, 150.0),
    ],
)
def test_an_item_for_a_year_with_a_statement_moves_its_field_by_its_amount(
    direction: str, expected_sga: float, expected_ebit: float
) -> None:
    """An item for 2024, a year that has a statement, moves 2024's sga by 50
    in the direction its `direction` names. 2023 is untouched:
    sga 200, EBIT 1000 - 600 - 200 = 200.
    """
    result = normalize_financials(_financials(), [_item(2024, WAREHOUSE, direction=direction)])

    by_year = {s.year: s for s in result.income_statements}
    assert sorted(by_year) == [2023, 2024]

    assert by_year[2024].sga == pytest.approx(expected_sga)
    assert by_year[2024].ebit == pytest.approx(expected_ebit)

    assert by_year[2023].sga == pytest.approx(200.0)
    assert by_year[2023].ebit == pytest.approx(200.0)
