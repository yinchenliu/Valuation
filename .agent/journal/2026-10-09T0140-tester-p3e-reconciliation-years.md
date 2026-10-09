---
agent: tester
assignment: P3e-reconciliation-years-tests
round: 1
status: complete
files_touched: [tests/unit/test_p3e_reconciliation_years.py]
verdict: pass
---

# P3e-reconciliation-years-tests — Verifying CLI reconciliation year-set parity with web page (item 128)

> **Opened before the first command. Filled as each result landed.**

## What I did

Created `tests/unit/test_p3e_reconciliation_years.py` containing 11 test functions (17 collected cases, 124 dynamic assertions, 75 static AST assert statements, 0 taken from running code output). Verified that `cli.print_normalization` and `api.routes_valuation._build_ebit_reconciliation` iterate the identical sorted union of `raw.years` and `adjusted.years` (backlog item 128). Verified that when a year exists on the adjusted side only, both entry points report that year with identical missing statement phrasing (`not extracted: raw income statement` or `not extracted: raw and adjusted income statement`), and when a year exists on the raw side only, both report `not extracted: adjusted income statement`. Confirmed that mutating `cli.py` back to `years = raw.years` fails 6 test cases (killed). Re-measured all gates at three random seeds (7, 1234, 99), lint, types, and census. Did not modify any implementation code in the repository.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the CLI no longer iterates the raw years alone | pass | `grep -n "years = raw.years" cli.py` exited 1 with no output |
| 2 | a year on the adjusted side only is named by both entry points, in the same words | pass | `tests/unit/test_p3e_reconciliation_years.py` asserts CLI prints `  2024: not extracted: raw income statement` and web returns `EBITReconciliationYear(year=2024, missing_statement="raw income statement", as_reported_ebit=None, adjusted_ebit=220.0, difference=None)`. Hand-derived arithmetic and closed-form identities. 17/17 passed in 0.94s |
| 3 | the test in criterion 2 fails on `main`'s `cli.py` | pass | Tested in scratch tree `/tmp/p3e_scratch` with `years = raw.years`: **6 failed, 11 passed** (killed). Restored: **17 passed, 0 failed** |
| 4 | the existing parity test still passes | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider "tests/unit/test_p3d_invisible_year.py::test_both_entry_points_name_an_unreconciled_year_in_the_same_words"` returned `3 passed in 0.86s` |
| 5 | the gate form at three orders | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=<n>` gave `1 failed, 1602 passed` across seeds 7 (33.89s), 1234 (33.42s), 99 (32.25s). Single failure is known backlog item 145 on macOS (`tests/unit/test_session_extraction_console.py:774`), identical to `main`. Passed count increased by 17 (from 1585 to 1602) |
| 6 | lint unchanged | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m ruff check .` returned exactly 4 errors, every one `BLE001`, 0 errors in new test file |
| 7 | types unchanged | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` returned 2 errors in 2 files (`analysis/projector.py:395`, `api/routes_upload.py:28`, 21 files checked) |
| 8 | rule 3 census unchanged | pass | `grep -rnE "if [^)]+ else 0(\.0)?\b\|\bor +0(\.0)?\b\|\.get\([^,]+, *0(\.0)?\)\|: *float *= *0\.0" '--include=*.py' models analysis api ingestion pipeline.py \| wc -l` returned `64` |
| 9 | unit stayed in scope | pass | Only `cli.py` (programmer diff, 7 lines), `tests/unit/test_p3e_reconciliation_years.py` (new test file), assignments, and journal entries. `git status --porcelain` clean of any unexpected edits |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Use scratch tree under `/tmp/p3e_scratch` for mutation test | `.claude/agents/tester.md` ("You may not modify implementation code") and guard hook `guard_paths.py` | Modifying repository implementation files violates tester constraints; scratch tree provides a rigorous isolated test of the mutation without repo file alteration |
| Use hand-derived round figures (1000 rev, 600 cogs, 180/200/220 sga) | `.claude/agents/tester.md` section "The hardest rule" | EBIT = rev - (cogs + sga) yields exact integer-level arithmetic (200.0, 220.0, 240.0) checkable by hand before execution |
| Test full matrix of statement presence (absent, income, cash_flow) | Assignment step 2 and rule 3 verification | Verifies both income statement absence and non-income statement presence (which puts the year into `FinancialStatements.years` without an income statement) |
| Assert early return preserves section banner in CLI | `cli.py:825-852` | Banner is printed before the year check; early return cleanly stops before looping or printing rows |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `raw.get_income_statement(y)` when `y` in union | Stops delta calculation; names missing statement as `"raw income statement"` (or `"raw and adjusted income statement"` if adjusted also absent) | `cli.py:858-866`, `api/routes_valuation.py:344-353`, `test_adjusted_only_year_with_income_statement_is_named_by_both_entry_points` |
| `adjusted.get_income_statement(y)` when `y` in union | Stops delta calculation; names missing statement as `"adjusted income statement"` (or `"raw and adjusted income statement"` if raw also absent) | `cli.py:858-866`, `api/routes_valuation.py:354-363`, `test_raw_only_year_with_income_statement_is_named_by_both_entry_points` |
| Both income statements when `y` in union | Stops delta calculation; names missing statement as `"raw and adjusted income statement"` in both entry points | `cli.py:859-860`, `api/routes_valuation.py:364-373`, `test_adjusted_only_year_with_non_income_statement_is_named_by_both_entry_points` |
| `raw` or `adjusted` is `None` in `_build_ebit_reconciliation` | Returns empty list `[]` | `api/routes_valuation.py:326-327`, `test_build_ebit_reconciliation_handles_none_inputs` |
| `raw.years` and `adjusted.years` both empty | Early return in CLI (header only, no rows/summary); empty list in web | `cli.py:851-852`, `test_empty_financial_statements_on_both_sides_produce_empty_output` |

## Measurements

- **Accuracy: 124 of 124 dynamic assertions match an independently derived expectation** (75 static assert statements in AST), across 11 test functions and 17 collected test cases. 0 derived from running code output.
- **Coverage: 100% of statements and branches in unit scope**.
  - `cli.py:print_normalization` (`:821-884`): 27 of 27 executable statements executed, 0 missed.
  - `api/routes_valuation.py:_build_ebit_reconciliation` (`:312-374`): 16 of 16 executable statements executed, 0 missed.
- Gates:
  - Seed 7: `1 failed, 1602 passed in 33.89s`
  - Seed 1234: `1 failed, 1602 passed in 33.42s`
  - Seed 99: `1 failed, 1602 passed in 32.25s`
  - Single failure across all seeds: `tests/unit/test_session_extraction_console.py:774` (item 145 on macOS, identical to `main`).
- Lint: 4 errors, all `BLE001` (`api/routes_valuation.py:463`, `745`, `cli.py:1416`, `tests/test_e2e_all_googl.py:106`), 0 in `tests/unit/test_p3e_reconciliation_years.py`.
- Types: 2 errors in 2 files (`analysis/projector.py:395`, `api/routes_upload.py:28`), 21 files checked.
- Census: 64.

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `test_adjusted_only_year_with_income_statement...` web record 2024 `adjusted_ebit` | `220.0` | Hand arithmetic: rev 1100 - (cogs 660 + sga 220) = `220.0` |
| `test_adjusted_only_year_with_income_statement...` web record 2024 `missing_statement` | `"raw income statement"` | Closed-form identity: year in adjusted, raw has no statements |
| `test_adjusted_only_year_with_income_statement...` CLI 2024 line | `"  2024: not extracted: raw income statement"` | Closed-form identity: CLI row matches `f"  2024: not extracted: {rec.missing_statement}"` |
| `test_adjusted_only_year_with_income_statement...` web record 2023 `difference` | `20.0` | Hand arithmetic: adj ebit (1000 - 600 - 180 = 220) - raw ebit (1000 - 600 - 200 = 200) = `+20.0` |
| `test_adjusted_only_year_with_income_statement...` CLI 2023 line | `"  2023: EBIT  GAAP=       200  Adj=       220  Delta=       +20"` | Hand arithmetic and format string `r.ebit:>10,.0f`, `a.ebit:>10,.0f`, `delta:>+10,.0f` |
| `test_adjusted_only_year_with_income_statement...` CLI 2025 absence | line starting with `  2025:` not in lines | Closed-form identity: delta is 0 (240 - 240 = 0), row suppressed |
| `test_adjusted_only_year_with_non_income_statement...` 2024 phrase | `"raw and adjusted income statement"` | Closed-form identity: neither side has income statement for 2024 |
| `test_raw_only_year_with_income_statement...` web record 2024 `as_reported_ebit` | `220.0` | Hand arithmetic: rev 1100 - (cogs 660 + sga 220) = `220.0` |
| `test_raw_only_year_with_income_statement...` 2024 phrase | `"adjusted income statement"` | Closed-form identity: raw has income statement, adjusted has none |
| `test_raw_only_year_with_non_income_statement...` 2024 phrase | `"raw and adjusted income statement"` | Closed-form identity: neither side has income statement for 2024 |
| `test_entry_points_parity_across_missing_statement_combinations` (7 cases) | expected phrases and ebit values | Closed-form identity: matrix of presence across statement types |
| `test_summary_line_prints_when_all_reconciled_years_have_zero_delta` | `"  No adjustments applied..."` | Closed-form identity: at least one reconciled year, all have delta == 0 |
| `test_reconciliation_summary_is_silent_when_no_year_was_reconciled` | summary line absent | Closed-form identity: 0 reconciled years -> summary suppressed |
| `test_empty_financial_statements_on_both_sides_produce_empty_output` | header only, no data rows, `[]` for web | Closed-form identity: empty inputs produce empty outputs |
| `test_build_ebit_reconciliation_handles_none_inputs` | `[]` | Closed-form identity: None input returns empty list |
| `test_union_years_are_sorted_chronologically_across_disjoint_year_sets` | `[2021, 2022, 2023, 2024]` | Closed-form identity: sorted union of disjoint sets {2021, 2023} and {2022, 2024} |

## Mutations — killed

| # | Mutation | `file` | Result | Tests that went red |
|---|---|---|---|---|
| **M1** | Revert `years = sorted(set(raw.years) \| set(adjusted.years))` to `years = raw.years` (state before item 128) | `cli.py:850` | **6 failed, 11 passed** | `test_adjusted_only_year_with_income_statement_is_named_by_both_entry_points`, `test_adjusted_only_year_with_non_income_statement_is_named_by_both_entry_points`, `test_entry_points_parity_across_missing_statement_combinations[absent-income-...]`, `test_entry_points_parity_across_missing_statement_combinations[absent-cash_flow-...]`, `test_reconciliation_summary_is_silent_when_no_year_was_reconciled`, `test_union_years_are_sorted_chronologically_across_disjoint_year_sets` |

## What I did not do

- Did not modify implementation code (`cli.py`, `api/routes_valuation.py`).
- Did not touch pre-existing backlog items out of scope (8, 68, 86, 90, 104, 129, 130, 132, 134, 135, 136, 137, 145).

## Findings for the orchestrator

None. Backlog item 128 is verified and cleanly locked with 100% statement and branch coverage in the affected functions.

## Verdict

`pass`
