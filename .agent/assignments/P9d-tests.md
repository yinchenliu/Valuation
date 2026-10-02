---
id: P9d-tests
phase: 9 — two extraction routes, one parser
agent: tester
depends_on: [P9d-pass2-checks]
---

# Move P9d's green tests out of the red file, and lock its other stops

## Objective

`P9d-pass2-checks` (accepted at `33afced`) made the three cases in
`tests/unit/test_session_extraction_rule3_red.py` pass. The gate skips every file named
`*_rule3_red.py`, so today those three tests run only in the full suite and the gate
never sees them. That is the defect backlog item 24 records, and
`.claude/agents/tester.md` says to move a test out of the pattern the day it goes green.

`P9d` also added stops that no test locks: an `amount` that is a string or a boolean, an
item missing one of the eight keys, a `year` that is not an integer, and an item that is
not an object. Its programmer and its reviewer proved them with scratch probes only.

Read the assignment `.agent/assignments/P9d-pass2-checks.md`, the programmer entry
`.agent/journal/2026-10-02T1713-programmer-p9d-pass2-checks.md` and the review entry
`.agent/journal/2026-10-02T1720-code_reviewer-p9d-pass2-checks.md` first.

## What to do

1. Move the three cases into `tests/unit/test_session_extraction.py`, unchanged in what
   they assert. Delete `tests/unit/test_session_extraction_rule3_red.py`.
2. Add one test per new stop: an `amount` of `"12"`, of `true`, of `null` and of `inf`;
   an item missing each of the eight keys, as one parametrised test; a `year` of
   `2025.5` and of `true`; an item that is a string, not an object. Each asserts
   `ValueError` and that the message names the file, the filing and the item.
3. Add one test that an `amount` of `0` loads. A stop on a bad value must not turn into
   a stop on zero.
4. Use the helpers `tests/unit/test_session_extraction.py` already has for building a
   session file. Write PDFs as bytes under `tmp_path`. Never read `10K_filings/`.

## Files in scope

- `tests/unit/test_session_extraction.py`
- `tests/unit/test_session_extraction_rule3_red.py`, to delete it
- your journal entry under `.agent/journal/`

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the red file is gone | no such file | `ls tests/unit/test_session_extraction_rule3_red.py` |
| 2 | the gate runs the moved tests | the gate count rises by at least 3 plus the new tests, with 1 failure (the held CAPM test) | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 3 | the full suite | exactly 4 failures: the CAPM test, and the one case in each of `test_dcf_rule3_red.py`, `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` | the failure list from `.venv/bin/python -m pytest -q` |
| 4 | at least one new test can fail | break one new check in a copy under `/tmp/`, show the test go red | paste it in your entry |
| 5 | lint | still 5 errors, none in your file | `.venv/bin/python -m ruff check .` |
