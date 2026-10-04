---
id: P14b-pass2-units-tests
phase: 14 — the Pass 1 role (the user's decision "fix 77a", 2026-10-04)
agent: tester
depends_on: [P14b-pass2-units]
---

# Repair the fixtures and test suites for session v4 and NonRecurringItem fields, and lock P14b's unit behaviors

## Objective

`P14b-pass2-units` is approved in round 1. Pass 2 items copy figures, cited pages, and unit statement words as printed without model conversions; Python scales each item individually via `pass2_amount_scale`. Both route A and route B confirm figure and unit statements on their cited pages and stop on any discrepancy. Session extraction format is upgraded to `session-extraction-v4` (v3 refused with remedy), and CLI cache format is updated to `p14b-pass2-units-v1`.

87 tests currently fail in the test gate:
- 58 tests: `NonRecurringItem(...)` constructor calls missing required arguments (`page`, `printed_units`, `units_page`).
- 28 tests: Session v3 format fixtures or Pass 2 fixtures missing `page` or `units`.
- 1 test: CLI cache format test expecting `p14a-units-in-millions-v1` instead of `p14b-pass2-units-v1`.

Read first:
- `.agent/assignments/P14b-pass2-units.md`
- Programmer entry: `.agent/journal/2026-10-04T1437-programmer-p14b-pass2-units.md`
- Code reviewer entry: `.agent/journal/2026-10-04T1506-code_reviewer-p14b-pass2-units.md`
- `.claude/agents/tester.md`

## What to do

1. **Repair the existing fixtures and NonRecurringItem calls:**
   - Add `page=1`, `printed_units="(Amounts in millions)"`, `units_page=1` (or appropriate test values) to `NonRecurringItem` instantiations across `tests/unit/`.
   - Update Pass 2 test fixtures and session fixtures to `session-extraction-v4` shape with `page: int` and `units: {"printed": "...", "page": ...}`.
   - Update cache marker assertions for `p14b-pass2-units-v1`.
   - **No existing numerical assertion may change**, unless re-derived by hand in a comment.

2. **Lock `pass2_amount_scale`:**
   - Test inline regex forms: `$0.7 billion` (1000), `$5.2 million` (1), `$300 thousand` (1/1000), plural forms (`billions`, etc.), whitespace variations.
   - Test statement forms: delegation to `printed_scale`.
   - Test stops: amount mismatch between inline text and `amount` (e.g. text `$0.7 billion` with amount `700` or `0.8`), missing scale word (`$0.7`), unreadable scale word.

3. **Lock Pass 2 page checks (`_pass2_item_failures` and `pass2_page_failures`):**
   - Figure check: number on page text line (`_text_line_holds`). Assert failure when amount is not on cited page.
   - Inline unit words check: `units_page == page`, whitespace-normalised substring match. Assert failure when `units_page != page` or text not found on page.
   - Statement unit words check: `units_page in (page, page - 1)`, whole statement / group on page (`unit_statement_on_page`). Assert failure when `units_page` is not `page` or `page - 1`, or statement is not on page.
   - Stop and message: assert exceptions name item, year, text, page.

4. **Lock individual Pass 2 scaling in `convert_filing_to_millions`:**
   - Test items with different scales in the same filing (e.g. statement in millions, footnote item in billions, another item in millions, another under thousands). Derive all converted values by hand.
   - Filing in thousands: item `$5.2 million` -> 5.2 $M; item 5,200 under `(in thousands)` -> 5.2 $M.

5. **Lock session format v4 and CLI cache:**
   - Refusal of `session-extraction-v3` with remedy message naming `v3`, `v4`, `page`, `units`.
   - Refusal of old cache markers in `cli._load_cache`.

Never read `10K_filings/` in tests; write test PDFs as bytes in `tmp_path`. No test may reach the external network or paid API.

## Files in scope

- `tests/`
- `.agent/journal/<YYYY-MM-DDTHHMM>-tester-p14b-pass2-units.md`

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite | exactly 2 failures: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` | `.venv/bin/python -m pytest -q` |
| 3 | no assertion weakened | none removed or loosened in repaired fixtures | `git diff` per file |
| 4 | new tests can fail | mutants in a scratch copy turn tests red | verify with mutants |
| 5 | lint | 4 errors (BLE001 pre-existing), 0 in `tests/` | `.venv/bin/python -m ruff check .` |
| 6 | mypy | 9 errors in 4 files, 0 in `tests/` | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` |
| 7 | two counts | accuracy and coverage reported | tester log entry |
