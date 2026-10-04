"""The three rule-3 stops `analysis/normalizer.py` owes its caller.

**These two tests were written red and they are now green.** They lived in
`tests/unit/test_normalizer_rule3_red.py` until this unit moved them here and
deleted that file. That matters, because the phase-1 gate excludes the red
pattern:

    .venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"

so while they sat there, **the only two tests that prove the P4-normalizer fix
works were the only two the gate did not run**, and every gate still reported
clean. That is [backlog item 24](../../docs/9-reference/refactor-backlog.md).
The `_rule3_red` suffix means "states a requirement the code does not meet",
not "tests a stop" — a stop that the code *does* meet belongs in the gate.

What each states, from `docs/2-rules/rules.md` rule 3 — *"a missing input stops
the run and names the field. It never falls back to zero, to a default, or to
'the historical average of nothing'"*:

1. `test_an_unrecognised_line_item_stops_the_run` — **backlog item 3**, closed
   at `38b903c`. An unrecognised `line_item` used to print one line to stdout
   and then *guess* `other_operating_expense`. The web app never shows stdout,
   so the only signal that the adjustment landed on the wrong line was a line
   nobody reads.

2. `test_an_unrecognised_direction_stops_the_run` — **backlog item 21**, closed
   at `38b903c`. The test used to be `== "add_back"`, so every other string —
   `"Add_Back"`, `"addback"`, a typo — silently took the `remove` branch and
   moved the adjustment the *opposite* way. The error is 2x the amount, because
   the correct move and the applied move have equal magnitude and opposite
   sign.

Neither test asserts the old fallback. Asserting `other_operating_expense ==
-50.0`, or an EBIT of 350 on a mis-spelled direction, would have made the defect
permanent and turned its fix red.

**Strengthened by `P4b-normalizer-verify`:** each now also asserts that the
message names the **year** of the offending item. A valuation carries several
years of items, and a message that says only *which* value was wrong does not
say *which item* to go and look at. The year is in both messages today
(`analysis/normalizer.py:89` and `:110`); this pins it there.
"""

from __future__ import annotations

import pytest

from analysis.normalizer import apply_adjustments, partition_by_confidence
from models.financial_statements import IncomeStatement, NonRecurringItem

# Revenue 1000, COGS 400, SG&A 200 -> EBIT = 1000 - 600 = 400, margin 0.40.


def _base_statement() -> IncomeStatement:
    return IncomeStatement(
        year=2021,
        revenue=1000.0,
        cost_of_revenue=400.0,
        sga=200.0,
    )


def test_an_unrecognised_line_item_stops_the_run() -> None:
    """Backlog item 3 — closed at `38b903c`, `analysis/normalizer.py:88-92`.

    Requirement, from rule 3: a `line_item` the engine cannot place is an input
    it does not have. It must stop and name the unplaceable label, so the reader
    can see which adjustment could not be applied, and on which year.

    What it did instead, before the fix: no exception. The 50 landed on
    `other_operating_expense` (0 - 50 = -50), EBIT rose from 400 to 450, the
    operating margin moved from 0.40 to 0.45, and every projected year moved
    with it. The only signal was a `print` to stdout.

    This test asserts the **correct** behaviour. It does not assert the
    fallback.
    """
    item = NonRecurringItem(
        year=2021,
        description="Goodwill impairment on the Widgets reporting unit",
        amount=50.0,
        line_item="Goodwill impairment charge",
        direction="add_back",
        category="impairment",
        # `high` is applied by `partition_by_confidence`, so this item reaches
        # `apply_adjustments` on a live run; a `low` one would be withheld first.
        confidence="high",
        page=1,
        printed_units="(Amounts in millions)",
        units_page=1,
    )

    with pytest.raises(ValueError) as excinfo:
        apply_adjustments(_base_statement(), [item])

    message = str(excinfo.value)
    assert "Goodwill impairment charge" in message  # the offending value
    assert "line_item" in message                   # the field it belongs to
    assert "2021" in message                        # which item, of the several


def test_an_unrecognised_direction_stops_the_run() -> None:
    """Backlog item 21 — closed at `38b903c`, `analysis/normalizer.py:108-113`.

    Requirement, from rule 3: `direction` has exactly two legal values,
    `"add_back"` and `"remove"` (`models/financial_statements.py:26`). A third
    value is an input the engine does not have. It must stop and name the field,
    the offending value and the year.

    What it did instead, before the fix, with `direction="addback"` (a plausible
    typo) on a 50 sitting in SG&A:

        correct, as an add_back : SG&A 200 - 50 = 150, EBIT = 450   (+50)
        applied, as a remove    : SG&A 200 + 50 = 250, EBIT = 350   (-50)
        error in EBIT                                   = 100 = 2 x the amount

    A plausible share price came out of both, and nothing anywhere reported that
    the direction had not been understood.
    """
    item = NonRecurringItem(
        year=2021,
        description="Restructuring charge",
        amount=50.0,
        line_item="sga",
        direction="addback",
        category="restructuring",
        # `high`, for the same reason as above: an applied item reaches the stop.
        confidence="high",
        page=1,
        printed_units="(Amounts in millions)",
        units_page=1,
    )

    with pytest.raises(ValueError) as excinfo:
        apply_adjustments(_base_statement(), [item])

    message = str(excinfo.value)
    assert "direction" in message   # the field
    assert "addback" in message     # the offending value
    assert "2021" in message        # which item, of the several


def test_an_unrecognised_confidence_stops_the_run() -> None:
    """`analysis/normalizer.py:137`, added at `7354698` and untested until now.

    Found while verifying `P8a-statements-data`: `partition_by_confidence` was
    at 0 covered statements in its loop body, so the one decision that says
    whether a non-recurring item moves the valuation or is withheld from it had
    no test at all. It is the function `api/routes_valuation.py:219` calls
    before it normalises anything.

    Requirement, from rule 3 and from the function's own docstring: an item this
    engine cannot rank is an input it does not have. It must stop and name the
    offending value, the year and the item — and it must **not** be read as
    `high`, because defaulting an unknown to the strongest reading is the same
    guess as defaulting a missing number to zero, in the direction that silently
    maximises the adjustment.

    This test asserts the stop. It does not assert any partition of the
    unrecognised item into either list, which is what pinning the old default
    would look like.
    """
    item = NonRecurringItem(
        year=2021,
        description="Restructuring charge",
        amount=50.0,
        line_item="sga",
        direction="add_back",
        category="restructuring",
        confidence="probably",
        page=1,
        printed_units="(Amounts in millions)",
        units_page=1,
    )

    with pytest.raises(ValueError) as excinfo:
        partition_by_confidence([item])

    message = str(excinfo.value)
    assert "confidence" in message              # the field
    assert "probably" in message                # the offending value
    assert "2021" in message                    # which item, of the several
    assert "Restructuring charge" in message    # and which one, within the year


def test_case_and_space_around_a_confidence_are_folded_not_rejected() -> None:
    """`"  HIGH "` is `high` shouted, not an unknown label.

    The control for the stop above: a stop that fired on every capitalisation
    would reject valid extractions, and a reader would see the rule-3 message
    for an item the model tagged correctly. One high item and one low item,
    both oddly cased, must partition one each way.
    """
    loud_high = NonRecurringItem(
        year=2021, description="Restructuring", amount=50.0, line_item="sga",
        direction="add_back", category="restructuring", confidence="  HIGH ",
        page=1, printed_units="(Amounts in millions)", units_page=1,
    )
    loud_low = NonRecurringItem(
        year=2021, description="Litigation", amount=10.0, line_item="sga",
        direction="add_back", category="litigation", confidence="Low",
        page=1, printed_units="(Amounts in millions)", units_page=1,
    )

    applied, excluded = partition_by_confidence([loud_high, loud_low])

    assert applied == [loud_high]
    assert excluded == [loud_low]


def test_medium_confidence_is_applied_and_low_is_withheld() -> None:
    """The partition itself, from the docstring's contract at `:99-104`.

    applied  — `high` and `medium`; these move the income statement.
    excluded — `low`; these move nothing.

    Order within each list is the order the items arrived, so a reader can put a
    withheld one back by hand against the source it cited.
    """
    high = NonRecurringItem(
        year=2021, description="A", amount=1.0, line_item="sga",
        direction="add_back", category="restructuring", confidence="high",
        page=1, printed_units="(Amounts in millions)", units_page=1,
    )
    medium = NonRecurringItem(
        year=2021, description="B", amount=2.0, line_item="sga",
        direction="add_back", category="restructuring", confidence="medium",
        page=1, printed_units="(Amounts in millions)", units_page=1,
    )
    low = NonRecurringItem(
        year=2021, description="C", amount=3.0, line_item="sga",
        direction="add_back", category="litigation", confidence="low",
        page=1, printed_units="(Amounts in millions)", units_page=1,
    )

    applied, excluded = partition_by_confidence([high, low, medium])

    assert applied == [high, medium]
    assert excluded == [low]
