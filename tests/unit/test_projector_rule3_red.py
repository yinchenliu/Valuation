"""RED ON PURPOSE. `analysis/projector.py` stops without naming the field.

**This file fails today and that is its job.** It states a requirement rule 3
makes and the code does not meet. The phase-1 gate excludes it by pattern:

    .venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"

**When the defect is fixed and this goes green, move the test into
`tests/unit/test_projector_sources.py` in the same unit.** A green test left
inside the excluded pattern is a test the gate never runs, so the one test that
proves the fix becomes the one test nobody checks. That happened at `38b903c`
and it is backlog item 24.

---

## The requirement

Rule 3 (`docs/2-rules/rules.md:43`): **"A missing input stops the run and names
the field."** Both halves are required. A stop that names nothing leaves the
reader with `IndexError: list index out of range` and no way to tell which
input was absent — and this one is raised from a line that is reading revenue,
so the traceback does not say it either.

## The fact

`analysis/projector.py:161-162`, on a `FinancialStatements` holding no income
statements:

    revenues = []                                   # :154, the comprehension is empty
    lookback = min(3, len(revenues) - 1) = min(3, -1) = -1
    _historical_cagr(revenues[-1 - (-1)], revenues[-1], -1)
                     ^^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^^
                     revenues[0]          both index an empty list

Either index raises `IndexError: list index out of range` before
`_historical_cagr`'s own `periods <= 0` guard at `:89` is ever reached.

## Why this is not merely theoretical, and why it is not already recorded

This is the **exact twin of backlog item 14**, which was closed at `ff632df`:
"Empty `projected_fcffs` raises a bare `IndexError`" in `analysis/dcf.py`. That
fix turned `IndexError: list index out of range` into a `ValueError` naming the
empty input. The same shape in `analysis/projector.py` is **not** in the backlog
at `6e58f13`.

The upstream is recorded, though. Backlog item 1 makes an extraction that
returned nothing produce a `FinancialStatements` with empty lists rather than an
error, and backlog item 15 is the same absence turning into `latest_year == 0`.
`api/routes_valuation.py` catches the `IndexError` in its blanket
`except Exception` (backlog item 8) and renders `str(e)` — so what a user sees
today for an extraction that returned nothing is the words "list index out of
range" on the assumptions page.

## What "fixed" looks like

`derive_assumptions` raises an error whose message names the absent input — the
income statements, or the ticker's extracted years. The exception TYPE is left
to the fix; this test accepts any exception that is not the bare `IndexError`,
and requires the message to name the field. Asserting `IndexError` instead
would lock the defect in.
"""

from __future__ import annotations

import re

import pytest

from analysis.projector import derive_assumptions
from models.financial_statements import FinancialStatements


def test_an_extraction_with_no_income_statements_stops_and_names_the_input() -> None:
    """Rule 3, both halves: it must stop, and the message must name what is absent.

    `FinancialStatements(ticker="TEST")` is what an extraction that returned
    nothing produces today (backlog item 1). `financials.years` is `[]`, so
    there is no filing-year to derive any of the six ratios from.

    The assertion deliberately does NOT name an exception type: any stop is
    acceptable so long as it is not the current bare `IndexError`, and so long
    as a reader can tell from the message which input was missing.
    `pytest.raises(Exception)` alone would pass against the defect.
    """
    empty = FinancialStatements(ticker="TEST")
    assert empty.years == []

    # `Exception` here is not laziness: the exception TYPE belongs to whoever
    # fixes this, and naming one would make a correct fix that chose a
    # different type fail. The two assertions below are what carry the
    # requirement, and neither of them passes against the code as it stands.
    with pytest.raises(Exception) as caught:
        derive_assumptions(empty)

    message = str(caught.value)

    # Half one: it must not be the unnamed builtin it is today.
    assert not isinstance(caught.value, IndexError), (
        "analysis/projector.py:162 raises a bare IndexError from an empty "
        "revenues list. It stops, but it names nothing — rule 3 requires both. "
        "This is the twin of backlog item 14, closed at ff632df in "
        "analysis/dcf.py, and it is not recorded for analysis/projector.py."
    )

    # Half two: the message must name the input a reader has to go and supply.
    assert re.search(
        r"income statement|financial statement|years|extracted", message, re.IGNORECASE
    ), (
        "The message must name the absent input so the reader knows what to "
        f"supply. It said: {message!r}"
    )
