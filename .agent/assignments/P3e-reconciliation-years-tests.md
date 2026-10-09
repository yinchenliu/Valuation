---
id: P3e-reconciliation-years-tests
phase: 3 — unify the pipeline
agent: tester
depends_on: [P3e-reconciliation-years]
team: B (worktree `Valuation-wt/team-b`, branch `unit/team-b`)
---

# Verifying CLI reconciliation year-set parity with web page (item 128)

## Objective

Verify that `cli.print_normalization` iterates the union of `raw.years` and `adjusted.years`, exactly matching `api/routes_valuation._build_ebit_reconciliation` (backlog item 128). Specifically, verify that when a year exists on the adjusted side only, both entry points report that year with identical missing statement phrasing (`not extracted: raw income statement`), and verify that this test fails if `cli.py` is mutated back to `years = raw.years`.

## What is already true — verify, do not redo

- `cli.py:849` iterates `years = sorted(set(raw.years) | set(adjusted.years))`.
- `api/routes_valuation.py:329` iterates `years = sorted(set(raw.years) | set(adjusted.years))`.
- `tests/unit/test_p3d_invisible_year.py:452` holds `test_both_entry_points_name_an_unreconciled_year_in_the_same_words`, which tests missing income statement lines when cash flow covers the year on both sides.
- In `main` (before item 128), if a year was present only in `adjusted` (for example, adjusted has statements for 2023, 2024, 2025 and raw has statements only for 2023, 2025), `cli.print_normalization` completely omitted year 2024 because `raw.years` did not contain 2024.

## What to do

1. Create `tests/unit/test_p3e_reconciliation_years.py`.
2. Write tests verifying criterion 2:
   - When a year appears in `adjusted` but not in `raw` (for example, `adjusted` has an income statement or cash flow statement for 2024 while `raw` has no statements covering 2024):
     - `cli.print_normalization` prints `  2024: not extracted: raw income statement`.
     - `_build_ebit_reconciliation(raw, adjusted)` returns an `EBITReconciliationYear` with `year == 2024`, `missing_statement == "raw income statement"`, `as_reported_ebit is None`, `adjusted_ebit == <value>`, and `difference is None`.
     - The cell formatted by the web template (`f"not extracted: {record.missing_statement}"`) matches the CLI's printed row for that year.
   - Closed-form identity / expected text written by hand before code runs.
   - Also test cases where a year appears in `raw` only (`not extracted: adjusted income statement`) and when years are present on both sides.
   - Also test empty financial statements on both sides (early return, no output).
3. Test criterion 3 (mutation check):
   - Temporarily mutate `cli.py` to `years = raw.years` (or run a probe simulating it).
   - Show that the test in criterion 2 fails (red) when `years = raw.years`.
   - Restore `cli.py` and show it passes (green). Report both counts.
4. Verify existing parity test passes (criterion 4):
   `.venv/bin/python -m pytest -q -p no:cacheprovider "tests/unit/test_p3d_invisible_year.py::test_both_entry_points_name_an_unreconciled_year_in_the_same_words"`
5. Measure gates and report all counts (accuracy, coverage, gates at seeds 7, 1234, 99, lint, types, rule 3 census).

## Files in scope

- `tests/unit/test_p3e_reconciliation_years.py` (tester, new file)
- `.agent/journal/<timestamp>-tester-p3e-reconciliation-years.md`

**Nothing else.** You may not modify `cli.py`, `api/routes_valuation.py`, or any implementation code (except the temporary mutation test for criterion 3, which must be reverted before completing).

## Out of scope

- `cli.py`, `api/routes_valuation.py`: implementation is done and approved by code reviewer.
- The four record files (`STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md`, `docs/9-reference/refactor-backlog.md`).

## Done-criteria

Run every command from the worktree root with `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python`.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the CLI no longer iterates the raw years alone | no match | `grep -n "years = raw.years" cli.py` |
| 2 | a year on the adjusted side only is named by both entry points, in the same words | the CLI prints `<year>: not extracted: raw income statement` and `_build_ebit_reconciliation` returns a row for that year with `missing_statement == "raw income statement"` | `tests/unit/test_p3e_reconciliation_years.py`, with expected text written by hand |
| 3 | the test in criterion 2 fails on `main`'s `cli.py` | red with `years = raw.years`, green without it | report the mutation and both counts |
| 4 | the existing parity test still passes | `3 passed` | `.venv/bin/python -m pytest -q -p no:cacheprovider "tests/unit/test_p3d_invisible_year.py::test_both_entry_points_name_an_unreconciled_year_in_the_same_words"` |
| 5 | the gate form at three orders | failed set equals `main`'s (1 failure on macOS, item 145), and passed count increases by new tests | `.venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=<n>` for n = 7, 1234, 99 |
| 6 | lint unchanged | `4 errors`, every one `BLE001`, none in new test file | `.venv/bin/python -m ruff check .` |
| 7 | types unchanged | `2 errors in 2 files` | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` |
| 8 | rule 3 census unchanged | `64` | `grep -rnE "if [^)]+ else 0(\.0)?\b\|\bor +0(\.0)?\b\|\.get\([^,]+, *0(\.0)?\)\|: *float *= *0\.0" '--include=*.py' models analysis api ingestion pipeline.py \| wc -l` |
| 9 | unit stayed in scope | only `cli.py`, `tests/unit/test_p3e_reconciliation_years.py`, assignments, and new journal entries | `git diff --name-only main...HEAD` |

## Citations

- `api/routes_valuation.py:311-360`, `_build_ebit_reconciliation`
- `cli.py:821-879`, `print_normalization`
- `templates/_statements.html:455`
- `tests/unit/test_p3d_invisible_year.py:452-490`
