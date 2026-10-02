"""DELIBERATELY RED. Two requirements the session loader does not meet yet.

Source: finding F1 of the `P9a-session-route` review,
`.agent/journal/2026-10-02T1654-code_reviewer-p9a-session-route.md`. The loader
checks Pass 1's shape strictly and Pass 2's loosely:

1. A `pass2` whose `non_recurring_items` is not a list escapes the loader as an
   `AttributeError` raised inside route A's parser. `_pass2_problems`
   (`ingestion/session_extraction.py:497`) catches `ValueError`, `KeyError` and
   `TypeError` only. The loader's contract is one `ValueError` naming the file and
   the filing (P9a step 10), and `check` exits 1 on it, the code reserved for
   "arithmetic errors only".
2. A Pass 2 item whose `amount` is `NaN` loads. The run then stops only at the DCF,
   with "projected FCFF is NaN", a message that names no item and no file. Pass 1
   rejects NaN in every key (`_is_number`); Pass 2 does not.

Both are rule 3 (`docs/2-rules/rules.md`): the stop must name the input.

**Do not weaken, skip or `xfail` these.** `P9d-pass2-checks` makes them pass. When
they go green, its tester moves them into `tests/unit/test_session_extraction.py`
in the same unit and deletes this file: the gate excludes `*_rule3_red.py`, so a
green test left here is a test nobody runs (backlog item 24).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ingestion.session_extraction import load_session_extraction
from tests.unit.test_session_extraction import (
    assert_one_line_names,
    one_filing,
    pdf_name,
    write,
)


@pytest.mark.parametrize("not_a_list", [{"a": 1}, "restructuring"])
def test_pass2_items_not_a_list_stops_naming_file_and_filing(
    tmp_path: Path, not_a_list: Any,
) -> None:
    data = one_filing(tmp_path)
    data["filings"][0]["pass2"] = {"non_recurring_items": not_a_list}
    path = write(tmp_path, data)
    # Today: AttributeError: 'str' object has no attribute 'get'.
    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)
    assert_one_line_names(str(excinfo.value), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "non_recurring_items")


def test_pass2_item_amount_nan_stops_naming_filing_year_and_description(
    tmp_path: Path,
) -> None:
    data = one_filing(tmp_path)
    # json.dumps writes float('nan') as NaN, and json.loads reads it back.
    data["filings"][0]["pass2"]["non_recurring_items"][0]["amount"] = float("nan")
    path = write(tmp_path, data)
    # Today: loads, with amount=nan.
    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)
    assert_one_line_names(str(excinfo.value), str(path.resolve()), "filings[0]",
                          pdf_name(2024), "2024", "Plant closure")
