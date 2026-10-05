---
agent: tester
assignment: P14b-note-figures-tests
round: 2
status: complete
files_touched:
  - tests/unit/test_p14b_note_figures.py
verdict: pass
---

# P14b-note-figures-tests — Check B1 test fixtures and Rule 3 locks

## What I did

In Round 2, updated test helper builders in `tests/unit/test_p14b_note_figures.py` (`_historical_year`, `_balance_sheet`, and `_pass1_dict`) to populate all standard line fields (`PASS1_YEAR_LINE_FIELDS` and `PASS1_BALANCE_SHEET_LINE_FIELDS`). Updated all test cases to use `_historical_year` and `_balance_sheet` so strict `[]` indexing succeeds on valid inputs without fallbacks. Updated `test_row_on_page_1_checks_page_1_only` to assert `"no unit statement on page 1"` (addressing review finding F5). Updated `test_route_a_retry_exhaustion_raises_value_error_on_unconfirmed_scale` to assert `"1 row scale failure(s) are still not confirmed"` (addressing review finding F4). Added comprehensive Rule 3 stop tests locking `KeyError` on missing keys: `historical_years`, line fields in historical years, `latest_balance_sheet`, line fields in balance sheets, and `year` in balance sheets. Verified all mutants turn tests red, and verified that both pytest gates (gate form and full suite with the 2 known red tests) pass cleanly.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | gate form | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`: 1066 passed in 15.34s (0 failed). |
| 2 | full suite | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q`: exactly 2 failed (`test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`), 1066 passed in 15.49s. |
| 3 | no assertion weakened | pass | `git diff tests/` shows zero loosened or removed assertions; all numerical expectations preserved; strict `KeyError` locks and exact error messages added. |
| 4 | new tests can fail | pass | Scratch mutation verification test killed 6 distinct mutants across preceding page logic, page 1 formatting, and missing key handling. |
| 5 | lint | pass | `.venv/bin/python -m ruff check .`: 4 pre-existing `BLE001` errors, 0 in `tests/`. |
| 6 | mypy | pass | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports`: 8 errors in 3 files (unchanged); `.venv/bin/python -m mypy tests/unit/test_p14b_note_figures.py --ignore-missing-imports`: 0 errors in test file. |
| 7 | two counts | pass | Accuracy: 85/85 assertions and raises blocks matched (100%). Coverage: `_row_scale_failures` (lines 1573-1685) has 100% statement and branch coverage. |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Add `_historical_year` and `_balance_sheet` test builders | Review finding F1, Rule 3 | Tests must construct fully valid schemas matching `pass1_problems` expectations so that direct `[]` indexing in `_row_scale_failures` succeeds without defaulting. |
| Explicitly test `KeyError` for each missing key | Review finding F1, Rule 3 | Verifies that removing `historical_years`, entry line fields, `latest_balance_sheet`, or balance sheet line fields immediately stops and names the key rather than defaulting via `.get()` or `in`. |
| Update page 1 assertion to `"no unit statement on page 1"` | Review finding F5 | Page 0 does not exist in 1-based PDF indexing; Check B1 formats `elif page == 1:` as `"no unit statement on page 1"`. |
| Update Route A retry message to `"1 row scale failure(s)"` | Review finding F4 | Round 2 distinguished unit statement failures from row scale failures in Route A stop messages. |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `data["historical_years"]` in `_row_scale_failures` | stops and raises `KeyError('historical_years')` | `test_rule_3_missing_historical_years_key_stops_and_names_field` |
| `entry[field]` for line fields in `historical_years` | stops and raises `KeyError('<field>')` | `test_rule_3_missing_line_field_in_historical_year_stops_and_names_field` |
| `data["latest_balance_sheet"]` in `_row_scale_failures` | stops and raises `KeyError('latest_balance_sheet')` | `test_rule_3_missing_latest_balance_sheet_key_stops_and_names_field` |
| `balance[field]` for line fields in `latest_balance_sheet` | stops and raises `KeyError('<field>')` | `test_rule_3_missing_line_field_in_balance_sheet_stops_and_names_field` |
| `balance["year"]` in `latest_balance_sheet` | stops and raises `KeyError('year')` | `test_rule_3_missing_year_in_balance_sheet_stops_and_names_field` |
| `entry["year"]` in `historical_years` | stops and raises `KeyError('year')` | `test_rule_3_missing_year_key_stops_and_names_field` |
| `line["label"]` in row item | stops and raises `KeyError('label')` | `test_rule_3_missing_line_label_key_stops_and_names_field` |
| `line["page"]` in row item | stops and raises `KeyError('page')` | `test_rule_3_missing_line_page_key_stops_and_names_field` |
| `data["units"]` in `_filing_units` | stops and raises `KeyError('units')` | `test_rule_3_missing_units_key_stops_and_names_field` |
| `data["share_units"]` in `_filing_units` | stops and raises `KeyError('share_units')` | `test_rule_3_missing_share_units_key_stops_and_names_field` |
| Invalid PDF bytes | stops and raises `ValueError` | `test_rule_3_invalid_pdf_bytes_raises_value_error` |

## Measurements

- **Pytest Gate:** 0 failed, 1066 passed (`.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`)
- **Pytest Full Suite:** 2 failed (`test_projector_rule3_red.py`, `test_routes_session_rule3_red.py`), 1066 passed (`.venv/bin/python -m pytest -q`)
- **Ruff:** 4 errors (all `BLE001`, pre-existing, 0 in tests)
- **Mypy:** 8 errors in 3 files (`tests/unit/test_p14b_note_figures.py` clean with 0 errors)
- **Guard Check:** 48/48 correct (`.venv/bin/python .claude/check_guard.py`)

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `test_row_scale_confirmed_on_row_page` | `failures == []` | Hand arithmetic: Page 1 text holds `(in millions)`. Row on page 1. Candidate word `'millions'` matches expected `'millions'` -> 0 failures. |
| `test_row_scale_confirmed_on_preceding_page` | `failures == []` | Hand arithmetic: Row on page 2. Preceding page 1 holds `(in millions)`. Candidate words across pages 2 and 1 hold `'millions'` -> 0 failures. |
| `test_row_on_page_1_checks_page_1_only` | 1 failure, `"no unit statement on page 1"` | Closed-form boundary condition: Page 1 has no preceding page (`page > 1` condition). Page 1 has no unit statement -> 1 failure. |
| `test_no_unit_statement_on_page_or_preceding_fails_with_named_details` | 1 failure, exact error message | Hand arithmetic: Row on page 3. Pages 3 and 2 have no parenthesised statement. Produces 1 failure naming page 3, money figures, expected millions, and row. |
| `test_multiple_rows_on_same_page_grouped_into_single_failure` | 1 failure for `(3, 'money figures')` | Closed-form identity: Grouping by `(page, kind)`. 3 citing rows share page 3 and kind `money figures` -> exactly 1 grouped failure. |
| `test_mismatched_unit_statement_fails_naming_expected_and_found` | 1 failure, expected millions, found `(in thousands)` | Hand arithmetic: Expected scale `'millions'`. Page 2 prints `(in thousands)`. Candidate `'thousands' != 'millions'` -> 1 failure naming both. |
| `test_distinct_kinds_verified_independently_on_two_scale_statement` | `failures == []` | Hand arithmetic: Statement prints `(dollars in millions, shares in thousands...)`. Money matches millions, shares matches thousands -> 0 failures. |
| `test_distinct_kinds_one_passes_and_one_fails` | 1 failure for share count | Hand arithmetic: Money matches millions (0 failures); share count expects millions but statement is thousands (1 failure). |
| `test_multi_scale_limit_page_with_multiple_statements_passes_either_scale` | `failures == []` for millions and thousands | Closed-form property: Page prints `(In millions)` and `(In thousands)`. Candidate set holds both scales; row of either scale finds a match -> 0 failures. |
| `test_mda_unparenthesised_prose_cannot_confirm_scale_and_stops` | 1 failure, no unit statement on page 2 or 1 | Closed-form property: MD&A prose `$1.2 billion` has no parentheses. `_PARENTHESISED_GROUP` regex matches only text in parentheses -> 1 failure. |
| `test_page_beyond_pdf_page_count_stops` | 1 failure, page beyond last page | Closed-form boundary condition: PDF has 2 pages; row cites page 5 (`5 > 2`). Scale on non-existent page cannot be confirmed -> 1 failure. |
| `test_page_with_no_text_layer_stops` | 1 failure, page 2 has no text layer | Closed-form boundary condition: Page 2 text is empty list `[]` -> 1 failure naming no text layer. |
| `test_balance_sheet_rows_checked_for_scale` | 1 failure for cash row on page 3 | Hand arithmetic: Cash row in balance sheet cites page 3 without unit statement on page 3 or 2 -> 1 failure under `money figures`. |
| `test_empty_rows_returns_empty_failures_and_prints_summary` | `failures == []`, `"0 checked, 0 pages, 0 pages not confirmed"` | Closed-form boundary condition: 0 rows in extraction -> early exit returns `[]` and prints 0 summary. |
| `test_summary_line_counts` | `"3 checked, 2 pages, 2 pages not confirmed"` | Hand arithmetic: 3 rows across pages 1 and 2 (neither has statement). Checked: 3, pages: 2, unconfirmed: 2. |
| `test_route_a_retry_exhaustion_raises_value_error_on_unconfirmed_scale` | `ValueError`, `"Pass 1: after 2 retries, 1 row scale failure(s)..."` | Hand arithmetic: `MAX_RETRIES = 2`. 1 initial + 2 retries = 3 calls. Exhaustion raises `ValueError` naming unconfirmed scale failure. |
| `test_route_b_cmd_check_exits_2_on_scale_failure` | `ValueError` from loader, exit code 2 from `cmd_check` | Closed-form contract: Route B check command exits 2 and loader raises `ValueError` when Check B1 has failures. |
| `test_unit_statement_page_failures_combines_unit_and_row_scale_failures` | `len(failures) >= 2`, both failures present | Closed-form property: Helper combines Check A (units citation on governed pages) and Check B1 (row scale on cited pages). |
| `test_rule_3_missing_units_key_stops_and_names_field` | `KeyError('units')` | Rule 3 stop: Missing top-level key `units`. |
| `test_rule_3_missing_share_units_key_stops_and_names_field` | `KeyError('share_units')` | Rule 3 stop: Missing top-level key `share_units`. |
| `test_rule_3_missing_year_key_stops_and_names_field` | `KeyError('year')` | Rule 3 stop: Missing `year` in historical year dict. |
| `test_rule_3_missing_historical_years_key_stops_and_names_field` | `KeyError('historical_years')` | Rule 3 stop: Missing top-level key `historical_years`. |
| `test_rule_3_missing_line_field_in_historical_year_stops_and_names_field` | `KeyError('revenue')` | Rule 3 stop: Missing standard line field in historical year dict. |
| `test_rule_3_missing_latest_balance_sheet_key_stops_and_names_field` | `KeyError('latest_balance_sheet')` | Rule 3 stop: Missing top-level key `latest_balance_sheet`. |
| `test_rule_3_missing_line_field_in_balance_sheet_stops_and_names_field` | `KeyError('cash')` | Rule 3 stop: Missing standard line field in `latest_balance_sheet`. |
| `test_rule_3_missing_year_in_balance_sheet_stops_and_names_field` | `KeyError('year')` | Rule 3 stop: Missing `year` in `latest_balance_sheet`. |
| `test_rule_3_missing_line_label_key_stops_and_names_field` | `KeyError('label')` | Rule 3 stop: Missing `label` in row line dict. |
| `test_rule_3_missing_line_page_key_stops_and_names_field` | `KeyError('page')` | Rule 3 stop: Missing `page` in row line dict. |
| `test_rule_3_invalid_pdf_bytes_raises_value_error` | `ValueError` | Rule 3 stop: Invalid PDF bytes passed to extractor. |
| `test_real_walmart_filing_scale_confirmation` | clean case `failures == []`, bad case 1 failure | Filing page citation: `10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf` page 21 prints `(Amounts in millions, except per share data)`. Page 2 prints no statement. |
| `test_real_chipotle_filing_scale_mismatch` | 1 failure, expected millions, found `(in thousands...)` | Filing page citation: `10K_filings/Chipotle/Chipotle Mexican Grill Inc._10-K_2025-12-31_English.pdf` page 29 prints `(in thousands, except per share data)`. |
| `test_real_okta_filing_two_scales` | clean case `failures == []`, wrong shares 1 failure | Filing page citation: `10K_filings/Okta/Okta Inc._10-K_2026-01-31_English.pdf` page 58 prints `(dollars in millions, shares in thousands, except per share data)`. |
| `test_real_lhx_filing_multi_scale_limit` | passes under millions (0 failures) and thousands (0 failures) | Filing page citation: `10K_filings/LHX/L3Harris Technologies Inc._10-K_2026-01-02_English.pdf` page 62 prints both `(In millions)` and `(In thousands)`. |
| `test_candidate_raising_value_error_is_discarded_for_kind` | 1 failure for share count | Hand arithmetic: Page 1 prints `(dollars in millions)`. For share count, `printed_scale` raises `ValueError('states no scale for share count')`. Candidate discarded, candidate list empty, 1 failure emitted. |

### Two counts, with their units:
- **Accuracy count:** 85/85 assertions (72 assert statements + 13 pytest.raises blocks) match expected values derived by hand arithmetic, closed-form properties, or filing page citations (100% accuracy).
- **Coverage count:** 1 function (`_row_scale_failures`), 113 statements (lines 1573-1685), 100% statement and branch coverage.

## What I did not do

- Did not edit implementation code (`ingestion/claude_extractor.py`, `docs/`, `models/`, `analysis/`, `api/`).
- Did not touch `STATUS.md` or `.agent/journal/INDEX.md` (reserved for orchestrator).
- Did not make any real network or paid API calls.

## Findings for the orchestrator

None.
