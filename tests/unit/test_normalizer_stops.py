"""The two rule-3 stops `analysis/normalizer.py` owes its caller.

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

from analysis.normalizer import apply_adjustments
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
    )

    with pytest.raises(ValueError) as excinfo:
        apply_adjustments(_base_statement(), [item])

    message = str(excinfo.value)
    assert "direction" in message   # the field
    assert "addback" in message     # the offending value
    assert "2021" in message        # which item, of the several
