---
id: P9d-pass2-checks
phase: 9 — two extraction routes, one parser
agent: programmer
depends_on: [P9a-session-route, P9c-parse-tests]
---

# Check the shape of Pass 2 in the session loader, as Pass 1 is checked

## Objective

The `P9a` review found that the session loader checks Pass 1 strictly and Pass 2
loosely (finding F1, `.agent/journal/2026-10-02T1654-code_reviewer-p9a-session-route.md`):

- a `pass2` whose `non_recurring_items` is not a list raises `AttributeError` from inside
  `parse_pass2`. The loader does not catch it, so `check` exits 1, which the assignment
  reserves for "arithmetic errors only";
- a Pass 2 item whose `amount` is `NaN` loads. The run then stops only at the DCF, with
  "projected FCFF is NaN", and that message names no item.

Both are rule 3: the stop must name the input. The session file is written by hand in a
chat, so a malformed Pass 2 is a likely input, not a remote one. `P9c-parse-tests` wrote
both requirements as red tests in `tests/unit/test_session_extraction_rule3_red.py`.
This unit makes them pass.

## What to do

1. In `ingestion/session_extraction.py`, before the loader calls `parse_pass2` for a
   filing, check that `non_recurring_items` is a list, and that every item's `amount` is
   a finite number. Collect each problem the way the loader already collects Pass 1
   problems, naming the file, the filing index, the PDF name and, for an item, its year
   and description.
   **Added from the `P9c` tester's entry** (`.agent/journal/2026-10-02T1658-tester-p9c-parse-tests.md`,
   findings 2 and 5):
   - an `amount` given as a string, such as `"12"`, loads today as `12.0`. Reject any
     `amount` that is not a JSON number, as the Pass 1 key check already rejects a
     non-number;
   - an item missing `year`, `description`, `amount`, `line_item`, `direction` or
     `category` stops today, but the message does not say which item. Check that every
     key `_NRI_SCHEMA` names is present on each item, and name the item by its index,
     and by its year and description where those are present.
2. **Do not change `parse_pass2` or `_parse_nri_response`.** They are route A's parser
   too, and route A must not change. The check lives in the loader, like the Pass 1 key
   check.
3. Answer finding F2 from the same review in your entry: the `.get` at
   `session_extraction.py:471` that the guard grep hits. State what it reads and why it
   cannot reach a figure, or change it.

## Files in scope

- `ingestion/session_extraction.py`
- your journal entry under `.agent/journal/`

## Out of scope

- `tests/`: the tester moves the two tests out of the red file when they pass.
- `ingestion/claude_extractor.py`: route A's parser.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the red tests pass | every case in the file passes | `.venv/bin/python -m pytest -q tests/unit/test_session_extraction_rule3_red.py` |
| 2 | nothing else moved | the gate as `P9c` left it | the test gate |
| 3 | `check` exit codes keep their meaning | a non-list `non_recurring_items` exits 2 | `.venv/bin/python -m ingestion.session_extraction check <scratch file>` |
| 4 | the real Walmart file still loads | `check` exit 0 | `.venv/bin/python -m ingestion.session_extraction check extractions/WMT.json` |
| 5 | no new lint or type errors | ruff 5, mypy as `P9b` left it | the two gates |

## Backlog items this unit is NOT fixing

- **Item 1.** Route A's `.get(field, 0)` reads.
- **Item 36.** Variance between readings.
