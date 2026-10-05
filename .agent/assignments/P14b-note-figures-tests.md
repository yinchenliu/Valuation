---
id: P14b-note-figures-tests
phase: 14 — the Pass 1 role (rule 1 option B, the user's decision of 2026-10-03; check B1, the user's decision of 2026-10-04)
agent: tester
depends_on: [P14b-note-figures]
---

# Repair test fixtures for Check B1 unit statement pages and lock Pass 1 note figures behaviors

## Objective

`P14b-note-figures` is approved in round 1. Pass 1 allows a printed figure from a note or MD&A (Rule 1 Option B), copied in the unit printed there without conversion. Python checks every Pass 1 printed row via `_row_scale_failures` (Check B1): the row's page or the preceding page must print a parenthesised unit statement of the filing's scale for that row's kind. If not, the run stops across Route A (retries exhausted -> `ValueError`) and Route B (`session_extraction check` -> exit 2).

31 tests currently fail in the test gate:
- Synthetic test fixtures (e.g. `_session_route_helpers.py` / `make_pdf`, `one_filing`, etc.) assign cash flow lines to page 52, but the synthetic PDF generated for the tests lacks a unit statement on page 52 or 51. Check B1 correctly stops on these rows because the scale cannot be confirmed.

Read first:
- `.agent/assignments/P14b-note-figures.md`
- Programmer entry: `.agent/journal/2026-10-04T2011-programmer-p14b-note-figures.md`
- Code reviewer entry: `.agent/journal/2026-10-04T2041-code_reviewer-p14b-note-figures.md`
- `.claude/agents/tester.md`

## What to do

1. **Repair synthetic test fixtures:**
   - Update synthetic PDF generation or test fixtures (e.g. `tests/unit/_session_route_helpers.py` or wherever page 52 rows are generated) so that cash flow statement pages carry a unit statement (e.g. `(in millions)`) on page 51 or 52, or cite pages where the unit statement is present.
   - **No existing numerical assertion may change**, unless re-derived by hand in a comment.

2. **Lock Check B1 unit behaviors in `tests/unit/test_p14b_note_figures.py`:**
   - Unit statement on row's page confirms scale (0 failures).
   - Unit statement on preceding page (`page - 1`) confirms scale (0 failures).
   - No unit statement on `page` or `page - 1` fails naming page, kind, expected scale, and all citing rows.
   - Mismatched unit statement (e.g. expected millions, found thousands) fails naming expected and found statements.
   - Distinct kinds (`"money figures"` vs `"share count"`) verified independently (e.g. Okta two scales).
   - Multi-scale limit: page with multiple statements (e.g. `(In millions)` and `(In thousands)`) confirms rows of either scale.
   - Page beyond PDF page count or page with no text layer stops.
   - Route A retry exhaustion raises `ValueError` listing unconfirmed scale failures.
   - Route B `session_extraction check` exits 2 on scale failures.
   - Summary line output format verified: `Row unit scales looked up on their cited pages: X checked, Y pages, Z pages not confirmed.`

Never make paid API calls or real network calls in tests. All stubs/mocks in memory.

## Files in scope

- `tests/`
- `.agent/journal/<YYYY-MM-DDTHHMM>-tester-p14b-note-figures.md`

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form | 0 failed (1032 passed) | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite | exactly 2 failures: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q` |
| 3 | no assertion weakened | none removed or loosened in repaired fixtures | `git diff` per file |
| 4 | new tests can fail | mutants in a scratch copy turn tests red | verify with mutants |
| 5 | lint | 4 errors (BLE001 pre-existing), 0 in `tests/` | `.venv/bin/python -m ruff check .` |
| 6 | mypy | 8 errors in 3 files, 0 in `tests/` | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` |
| 7 | two counts | accuracy and coverage reported | tester log entry |
