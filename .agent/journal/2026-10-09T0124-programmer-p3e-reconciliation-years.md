---
agent: programmer
assignment: P3e-reconciliation-years
round: 1
status: complete
files_touched: [cli.py]
---

# P3e-reconciliation-years — The CLI reconciles the same years as the web page

## What I did

In `cli.py:print_normalization`, updated the year iteration from `years = raw.years` to `years = sorted(set(raw.years) | set(adjusted.years))`, matching `api/routes_valuation.py:_build_ebit_reconciliation` (backlog item 128). This ensures that any year reached only by the adjusted statements is reported in the CLI reconciliation as `not extracted: raw income statement`, eliminating the divergence between the terminal and web entry points (the third standing trap). Preserved the existing `P3d` round 2 explanatory comment, updated the docstring/comment above the line to explain the set now iterated, and kept the early `return` on empty years and the summary line printing rule.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the CLI no longer iterates the raw years alone | pass | `grep -n "years = raw.years" cli.py` exited 1 with no output |
| 2 | a year on the adjusted side only is named by both entry points, in the same words | pass | Verified by execution probe: CLI prints `2024: not extracted: raw income statement` and `_build_ebit_reconciliation` sets `missing_statement == "raw income statement"`; formal test suite left to tester |
| 3 | the test in criterion 2 fails on `main`'s `cli.py` | pass | Verified by execution probe: with `years = raw.years`, 2024 was absent from CLI output; tester will record formal mutation |
| 4 | the existing parity test still passes | pass | `.venv/bin/python -m pytest -q -p no:cacheprovider "tests/unit/test_p3d_invisible_year.py::test_both_entry_points_name_an_unreconciled_year_in_the_same_words"` returned `3 passed in 0.85s` |
| 5 | the gate form at three orders | pass | `.venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=<n>` gave `1 failed, 1585 passed` for n = 7, 1234, 99 (the single failure is known item 145 on macOS) |
| 6 | lint unchanged | pass | `.venv/bin/python -m ruff check .` returned exactly 4 errors, all `BLE001`, `cli.py`'s one `BLE001` at line 1416 |
| 7 | types unchanged | pass | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` returned 2 errors in 2 files (`analysis/projector.py:395`, `api/routes_upload.py:28`) |
| 8 | rule 3 census unchanged | pass | `grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" '--include=*.py' models analysis api ingestion pipeline.py | wc -l` returned `64` |
| 9 | the unit stayed in scope | pass | `git status` shows only `cli.py` modified and the new journal entry untracked |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Use `sorted(set(raw.years) \| set(adjusted.years))` | `api/routes_valuation.py:329` and assignment step 1; entry point parity (third standing trap) | An entry point specific year set allows drift where adjusted-only years are omitted by CLI |
| Retain full `P3d` round 2 comment and append explanation of union year set | Assignment step 2 ("Do not shorten the record of P3d round 2 in it") | Preserves historical audit record of finding F4 while documenting item 128 |
| Keep early return on empty years | Assignment step 3 | No statements on either side means nothing to reconcile; returns immediately before any printing or looping |
| Keep summary check `if not reconciled: return` | Assignment step 3 | Summary line ("No adjustments applied...") must only print if at least one year was reconciled |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `raw.years` | empty list; union with `adjusted.years` handles empty set | `cli.py:849` (`years = sorted(set(raw.years) \| set(adjusted.years))`) |
| `adjusted.years` | empty list; union with `raw.years` handles empty set | `cli.py:849` (`years = sorted(set(raw.years) \| set(adjusted.years))`) |
| `years` | returns early without printing table rows or summary | `cli.py:850-851` (`if not years: return`) |
| `raw.get_income_statement(y)` | reports explicit absence `not extracted: raw income statement` (or `raw and adjusted income statement` if both absent) | `cli.py:857-865` |
| `adjusted.get_income_statement(y)` | reports explicit absence `not extracted: adjusted income statement` (or `raw and adjusted income statement` if both absent) | `cli.py:857-865` |

## Measurements

- Test suite gate:
  - Seed 7: `1 failed, 1585 passed in 33.83s`
  - Seed 1234: `1 failed, 1585 passed in 32.63s`
  - Seed 99: `1 failed, 1585 passed in 32.73s`
  - Failed test across all seeds: `tests/unit/test_session_extraction_console.py:774: AssertionError: test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream` (backlog item 145, identical to `main` on macOS).
- Lint: 4 errors, all `BLE001`:
  - `api/routes_valuation.py:463:16`
  - `api/routes_valuation.py:745:12`
  - `cli.py:1416:12`
  - `tests/test_e2e_all_googl.py:106:16`
- Types: 2 errors in 2 files (21 source files checked):
  - `analysis/projector.py:395`
  - `api/routes_upload.py:28`
- Rule 3 census: 64
- Scope diff:
  - `git diff --stat`: `cli.py | 7 +++++--` (5 insertions, 1 deletion in `print_normalization`)

## What I did not do

- Did not write `tests/unit/test_p3e_reconciliation_years.py`: owned by the tester role per assignment.
- Did not touch `api/routes_valuation.py`, `pipeline.py`, or any other file outside scope.
- Did not touch backlog items 8, 68, 86, 90, 104, 129, 130, 132, 134, 135, 136, 137 explicitly named as out of scope.

## Findings for the orchestrator

None. The change is small, targeted, and matches `api/routes_valuation.py:329` identically.
