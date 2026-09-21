"""Two rule-3 requirements that `analysis/normalizer.py` does not meet today.

**BOTH TESTS IN THIS FILE FAIL ON PURPOSE.** They are not broken and they must
not be weakened, skipped or `xfail`ed. Each states, as executable code, a
requirement from `docs/2-rules/rules.md` rule 3 — *"a missing input stops the run
and names the field. It never falls back to zero, to a default, or to 'the
historical average of nothing'."* Each goes green on the day the defect it names
is fixed, and is **kept, not deleted**, when it does.

The phase-1 gate excludes this file:

    .venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"

1. `test_an_unrecognised_line_item_stops_the_run` — **backlog item 3**,
   `analysis/normalizer.py:50-51`. An unrecognised `line_item` prints one line to
   stdout and then *guesses* `other_operating_expense`. The web app never shows
   stdout, so the only signal that the adjustment landed on the wrong line is a
   line nobody reads.

2. `test_an_unrecognised_direction_stops_the_run` — `analysis/normalizer.py:68`,
   **not yet on the backlog**. The test is `== "add_back"`, so every other
   string — `"Add_Back"`, `"addback"`, a typo — silently takes the `remove`
   branch and moves the adjustment the *opposite* way. The error is 2x the
   amount, because the correct move and the applied move have equal magnitude
   and opposite sign.
"""

from __future__ import annotations

import pytest

from analysis.normalizer import apply_adjustments
from models.financial_statements import IncomeStatement, NonRecurringItem

# Revenue 1000, COGS 400, SG&A 200 -> EBIT = 1000 - 600 = 400, margin 0.40.


def _base_statement() -> IncomeStatement:
    return IncomeStatement(
        year=2024,
        revenue=1000.0,
        cost_of_revenue=400.0,
        sga=200.0,
    )


def test_an_unrecognised_line_item_stops_the_run() -> None:
    """Backlog item 3 — `analysis/normalizer.py:50-51`.

    Requirement, from rule 3: a `line_item` the engine cannot place is an input
    it does not have. It must stop and name the unplaceable label, so the reader
    can see which adjustment could not be applied.

    What happens instead, measured: no exception. The 50 lands on
    `other_operating_expense` (0 - 50 = -50), EBIT rises from 400 to 450, the
    operating margin moves from 0.40 to 0.45, and every projected year moves
    with it. The only signal is a `print` to stdout.

    This test asserts the **correct** behaviour. It does not assert the
    fallback: asserting `other_operating_expense == -50.0` would make the guess
    permanent and turn the eventual fix red.
    """
    item = NonRecurringItem(
        year=2024,
        description="Goodwill impairment on the Widgets reporting unit",
        amount=50.0,
        line_item="Goodwill impairment charge",
        direction="add_back",
        category="impairment",
    )

    with pytest.raises(ValueError) as excinfo:
        apply_adjustments(_base_statement(), [item])

    message = str(excinfo.value)
    assert "Goodwill impairment charge" in message
    assert "line_item" in message


def test_an_unrecognised_direction_stops_the_run() -> None:
    """`analysis/normalizer.py:68` — not yet on the backlog.

    Requirement, from rule 3: `direction` has exactly two legal values,
    `"add_back"` and `"remove"` (`models/financial_statements.py:26`). A third
    value is an input the engine does not have. It must stop and name the field
    and the offending value.

    What happens instead, measured with `direction="addback"` (a plausible typo)
    on a 50 sitting in SG&A:

        correct, as an add_back : SG&A 200 - 50 = 150, EBIT = 450   (+50)
        applied, as a remove    : SG&A 200 + 50 = 250, EBIT = 350   (-50)
        error in EBIT                                   = 100 = 2 x the amount

    A plausible share price comes out of both. Nothing anywhere reports that the
    direction was not understood.
    """
    item = NonRecurringItem(
        year=2024,
        description="Restructuring charge",
        amount=50.0,
        line_item="sga",
        direction="addback",
        category="restructuring",
    )

    with pytest.raises(ValueError) as excinfo:
        apply_adjustments(_base_statement(), [item])

    message = str(excinfo.value)
    assert "direction" in message
    assert "addback" in message
