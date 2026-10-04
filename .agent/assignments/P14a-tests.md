---
id: P14a-tests
phase: 14 — the Pass 1 role (the user's approval of `share_units`, 2026-10-04)
agent: tester
depends_on: [P14a-units]
---

# Repair the fixtures and test suites for session v3 and printed_unit_in_millions, and lock P14a's unit behaviors

## Objective

`P14a-units` is approved in round 2. It reads `units` and `share_units` statements with cited pages, page-checks them as whole statements on income statement / share pages, converts statements and Pass 2 items to millions once per filing in Python, requires `BalanceSheet.printed_unit_in_millions`, sets balance check threshold to 1 printed unit (0.001 $M for thousands), and moves session files to `session-extraction-v3`.

291 tests fail:
- Group A (163 tests): `BalanceSheet(...)` instantiations missing `printed_unit_in_millions` (including `tests/unit/test_cli_overrides.py:109,173`, `tests/unit/test_wacc.py`, `tests/unit/test_routes.py`).
- Group B (121 tests): fixtures missing `units` and `share_units` v3 format.
- Group E (6 tests): instance method updates (e.g. `bs.printed_total_check(difference)`).
- Group V (1 test): v2 format refusal.

Read first:
- `.agent/assignments/P14a-units.md` (and its Round 2 amendment)
- Programmer round 2 entry: `.agent/journal/2026-10-04T1041-programmer-p14a-units-r2.md`
- Code reviewer round 2 entry: `.agent/journal/2026-10-04T1109-code_reviewer-p14a-units-r2.md`
- `.claude/agents/tester.md`

## What to do

1. **Repair the existing fixtures and BalanceSheet calls:**
   - Add `printed_unit_in_millions=1.0` (or appropriate scale) to `BalanceSheet` instantiations across `tests/unit/`.
   - Update Pass 1 test fixtures to `session-extraction-v3` shape with `units` and `share_units` objects `{"printed": "...", "page": ...}`.
   - Update calls to `printed_total_check` to use instance method `bs.printed_total_check(difference)`.
   - **No existing numerical assertion may change**, unless re-derived by hand in a comment.

2. **Lock `printed_scale` and stops:**
   - Test scale words: thousands (1/1000), millions (1), billions (1000).
   - Test required stops: no scale word (`(in dollars)`), except shares (`except share data`), shares mentioned outside clauses (`_named_outside_its_clauses`: `excluding share data`, `other than shares`, `but not shares`, `shares in actual numbers`), dollars mentioned outside clauses.

3. **Lock `unit_statement_on_page`:**
   - Test whole parenthesised group / whole text line match (whitespace normalised).
   - Test that fragments fail: e.g. `(in thousands)` on a page that prints `(dollars in millions, shares in thousands, except per share data)` returns `False`.

4. **Lock `_unit_statement_pages_allowed`:**
   - Test `units.page` restricted to income statement line pages.
   - Test `share_units.page` restricted to `units.page` union `diluted_shares` pages.
   - Assert stop and message when cited page is outside allowed set.

5. **Lock `convert_filing_to_millions`:**
   - Thousands filing: money lines divided by 1,000; diluted shares divided by 1,000; Pass 2 amounts divided by 1,000; `printed_unit_in_millions=0.001`. Derive all expected figures by hand.
   - Millions filing: unchanged (multiplied by 1 exact); `printed_unit_in_millions=1.0`.
   - Billions filing: multiplied by 1,000; `printed_unit_in_millions=1000.0`.
   - Duplicate conversion stops with `ValueError`.

6. **Lock balance check tolerance and decimals:**
   - Tolerance is 1 printed unit: 0.001 for thousands, 1.0 for millions.
   - Gap within tolerance is `OK`, gap exceeding tolerance is `FAIL`.
   - `printed_unit_decimals()` returns 3 for thousands, 0 for millions.
   - Template formatting: difference cells formatted with decimals (`+0.002`, not `+0`).

7. **Lock session formats & cache:**
   - `session-extraction-v2` refused with remedy message naming `v3`, `units`, `share_units`.
   - Old CLI cache format `p11a-printed-lines-v1` refused by `_load_cache`.

Never read `10K_filings/` in tests; write test PDFs as bytes in `tmp_path`. No test may reach the external network or paid API.

## Files in scope

- `tests/`
- `.agent/journal/<YYYY-MM-DDTHHMM>-tester-p14a-tests.md`

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite | exactly 2 failures: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` | `.venv/bin/python -m pytest -q` |
| 3 | no assertion weakened | none removed or loosened in repaired fixtures | `git diff` per file |
| 4 | new tests can fail | mutants in a scratch copy turn tests red | verify with mutants |
| 5 | lint | 4 errors (BLE001 pre-existing), 0 in `tests/` | `.venv/bin/python -m ruff check .` |
| 6 | mypy | 9 errors in 4 files, 0 in `tests/` | `.venv/bin/python -m mypy ...` |
| 7 | two counts | accuracy and coverage reported | tester log entry |
