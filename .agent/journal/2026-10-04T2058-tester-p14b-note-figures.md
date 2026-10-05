---
agent: tester
assignment: P14b-note-figures-tests
round: 1
status: complete
files_touched:
  - tests/unit/_pass1_pdf.py
  - tests/unit/test_page_check.py
  - tests/unit/test_p14b_note_figures.py
verdict: pass
---

# P14b-note-figures-tests — Check B1 test fixtures repair and behavior lock

## What I did

1. **Repaired synthetic test fixtures:**
   - In `tests/unit/_pass1_pdf.py` (`pass1_pages`), ensured synthetic PDFs print the filing's unit statement on cash flow statement pages (`_CASH_FLOW_FIELDS`), matching the real-world 10-K convention where each primary statement table prints its unit header. This resolved 30 fixture failures where cash flow rows on page 52 or 3 failed Check B1 due to missing unit headers.
   - In `tests/unit/test_page_check.py`, updated `test_check_exits_2_on_a_page_with_no_text_layer`: under Check B1, a cited page with no text layer cannot confirm the scale of figures citing it, so `session_extraction check` stops (exit 2) rather than keeping unconfirmed figures as a warning (exit 1).

2. **Locked Check B1 unit behaviors in `tests/unit/test_p14b_note_figures.py` (29 tests, 67 assertions):**
   - Unit statement on row's page confirms scale (0 failures).
   - Unit statement on preceding page (`page - 1`) confirms scale (0 failures).
   - Page 1 does not check non-existent page 0.
   - Missing unit statement on `page` or `page - 1` stops, naming page, kind, expected scale, statement description, and all citing rows.
   - Multiple rows on the same page grouped into exactly one failure per `(page, kind)`.
   - Mismatched unit statement (expected millions, found thousands) fails naming expected and found statements.
   - Distinct kinds (`"money figures"` vs `"share count"`) verified independently (e.g. Okta two scales).
   - Multi-scale limit: page with multiple statements (e.g. `(In millions)` and `(In thousands)`) confirms rows of either scale.
   - Unparenthesised prose (`$1.2 billion` in MD&A) cannot confirm scale and stops.
   - Page beyond PDF page count or page with no text layer stops.
   - Route A retry exhaustion raises `ValueError` listing unconfirmed scale failures.
   - Route B `session_extraction check` exits 2 on scale failures, and `load_session_extraction` raises `ValueError`.
   - Summary line output format verified for both empty and non-empty rows.
   - Rule 3 stops locked for missing keys (`units`, `share_units`, `year`, `label`, `page`) and invalid PDF bytes.
   - Real 10-K filings verified: Walmart, Chipotle, Okta, and L3Harris.
   - Coverage: candidate group raising `ValueError` in `printed_scale` is discarded for that kind.

---

## Done-criteria

All commands run with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. Zero paid API calls made.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | gate form | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` passed with 0 failed, 1061 passed in 15.30s (1032 baseline + 29 new tests). |
| 2 | full suite | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q` passed with exactly 2 failed (`test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`), 1061 passed in 15.67s. |
| 3 | no assertion weakened | pass | `git diff tests/unit/_pass1_pdf.py tests/unit/test_page_check.py`: `_pass1_pdf.py` added unit header to cash flow statement pages without changing assertions; `test_page_check.py` tightened exit code assertion from exit 1 to exit 2 per Check B1 / Rule 3 stop semantics. |
| 4 | new tests can fail | pass | Mutation testing script applied 5 distinct mutants against `ingestion/claude_extractor.py`: Mutant 1 (ignore `page - 1`: 2 failed), Mutant 2 (treat shares as money: 2 failed), Mutant 3 (skip page > page_count: 1 failed), Mutant 4 (skip no text layer: 1 failed), Mutant 5 (accept any candidate scale: 4 failed). All 5 mutants caught. |
| 5 | lint | pass | `.venv/bin/python -m ruff check .` reports 4 errors (`BLE001` pre-existing in `api/routes_valuation.py`, `cli.py`, `tests/test_e2e_all_googl.py`), 0 in `tests/`. |
| 6 | mypy | pass | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` reports 8 errors in 3 files (`analysis/projector.py`, `api/routes_upload.py`, `api/routes_valuation.py`), 0 in `tests/`. |
| 7 | two counts | pass | Accuracy: 67/67 assertions matching expected values. Coverage: 1/1 function (`_row_scale_failures`), 73/73 statements (100% statement coverage), all branches covered. |

---

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Insert `units["printed"]` on cash flow statement pages in `_pass1_pdf.py` | `P14b-note-figures-tests.md` step 1 | In real 10-K filings, every financial statement table prints its unit statement. The synthetic generator previously printed `units` only on the single page cited in `units["page"]`, omitting the cash flow statement header. Rather than modifying 30 individual test files, updating the central fixture builder accurately reflects filing reality while keeping all numerical assertions intact. |
| Update `test_page_check.py` to assert exit 2 for page with no text layer | Check B1 specification; `ingestion/claude_extractor.py:1637-1645` | In P12a, a page with no text layer only failed the line check (exit 1). In P14b, Check B1 checks every cited page for scale confirmation. A page with no text layer cannot confirm scale and constitutes a fatal stop (exit 2). Tightening the test asserts the true contract of Check B1. |
| Test candidate group `ValueError` discard in `printed_scale` | Coverage analysis (lines 1662-1663 of `claude_extractor.py`) | When a parenthesised statement states no scale for a kind (e.g. `(dollars in millions)` for share count), `printed_scale` raises `ValueError`. Discarding the group ensures it is not treated as a candidate for that kind. Tested explicitly in `test_candidate_raising_value_error_is_discarded_for_kind`. |

---

## Rule 3 — what stops, and what does not

For every value this unit reads, one row.

| Value read | If it were missing | Evidence |
|---|---|---|
| `units` in Pass 1 data | stops: `_filing_units` raises `KeyError('units')` | `test_rule_3_missing_units_key_stops_and_names_field` |
| `share_units` in Pass 1 data | stops: `_filing_units` raises `KeyError('share_units')` | `test_rule_3_missing_share_units_key_stops_and_names_field` |
| `year` in `historical_years` entry | stops: raises `KeyError('year')` | `test_rule_3_missing_year_key_stops_and_names_field` |
| `label` in printed row dict | stops: raises `KeyError('label')` | `test_rule_3_missing_line_label_key_stops_and_names_field` |
| `page` in printed row dict | stops: raises `KeyError('page')` | `test_rule_3_missing_line_page_key_stops_and_names_field` |
| `pdf_bytes` passed to check | stops: `_read_cited_pages` raises `ValueError` | `test_rule_3_invalid_pdf_bytes_raises_value_error` |
| Cited page beyond PDF page count | stops: reports `page X is beyond the last page of the filing (N pages)` | `test_page_beyond_pdf_page_count_stops` |
| Cited page has no text layer | stops: reports `page X has no text layer` | `test_page_with_no_text_layer_stops` |
| No unit statement on `page` or `page - 1` | stops: reports `no unit statement on page X or X - 1` | `test_no_unit_statement_on_page_or_preceding_fails_with_named_details` |
| Mismatched unit statement | stops: reports `expected <X>, found <Y>` | `test_mismatched_unit_statement_fails_naming_expected_and_found` |
| Unparenthesised MD&A prose | stops: reports `no unit statement on page X or X - 1` | `test_mda_unparenthesised_prose_cannot_confirm_scale_and_stops` |

---

## Measurements

### Quality Gates Comparison

| Gate | Before (`P14b-note-figures`) | After (`P14b-note-figures-tests`) | Status |
|---|---|---|---|
| Ruff (`ruff check .`) | 4 errors (`BLE001`) | 4 errors (`BLE001`) | Clean in `tests/` |
| Mypy (`mypy models analysis ingestion api config.py app.py --ignore-missing-imports`) | 8 errors in 3 files | 8 errors in 3 files | Clean in `tests/` |
| Rule 3 census | 65 | 65 | Unchanged |
| Write guard (`.claude/check_guard.py`) | 48/48 | 48/48 | Unchanged |
| Pytest Gate (`--ignore-glob="*_rule3_red.py"`) | 31 failed, 1001 passed (1032 total) | 0 failed, 1061 passed | 31 repaired + 29 added |
| Pytest Full | 33 failed, 1001 passed (1034 total) | 2 failed, 1061 passed | Exactly the 2 red tests |

---

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `test_row_scale_confirmed_on_row_page` | `failures == []` | Hand arithmetic: filing units '(in millions)' -> money scale 'millions'; page 1 has '(in millions)'; candidate_words = ['millions'] matches expected 'millions' |
| `test_row_scale_confirmed_on_preceding_page` | `failures == []` | Hand arithmetic: row on page 2; page 2 has no statement; page - 1 = 1 has '(in millions)'; pages_to_check = (2, 1); candidate_words = ['millions'] matches expected 'millions' |
| `test_row_on_page_1_checks_page_1_only` | `len(failures) == 1`, message names 'page 1 (money figures): expected millions, no unit statement on page 1 or 0' | Closed-form identity: page 1 has page - 1 = 0, condition `page > 1` excludes 0; page 1 has no statement -> unconfirmed; 1 failure |
| `test_no_unit_statement_on_page_or_preceding_fails_with_named_details` | `failures[0].message == "page 3 (money figures): expected millions, no unit statement on page 3 or 2. Rows citing page 3: 'Total revenues' (revenue, year 2024)."` | Hand arithmetic: row on page 3; page 2 and 3 have no statement; expected 'millions'; message formats page, kind, expected scale, and row |
| `test_multiple_rows_on_same_page_grouped_into_single_failure` | `len(failures) == 1`, message joins 3 rows with '; ' | Closed-form property: check groups by `(page, kind)`; 3 rows share (3, 'money figures') -> exactly 1 failure |
| `test_mismatched_unit_statement_fails_naming_expected_and_found` | `failures[0].message == "page 2 (money figures): expected millions, found (in thousands). Rows citing page 2: 'Total revenues' (revenue, year 2024)."` | Hand arithmetic: filing scale 'millions'; statement on page 2 '(in thousands)' gives candidate 'thousands' != 'millions' |
| `test_distinct_kinds_verified_independently_on_two_scale_statement` | `failures == []` | Closed-form identity: '(dollars in millions, shares in thousands, except per share data)' gives money = millions, shares = thousands; each row matches its kind |
| `test_distinct_kinds_one_passes_and_one_fails` | `len(failures) == 1`, failure for '(share count)' | Hand arithmetic: statement gives shares in thousands; share_units expects millions; money matches (0 failures), share count fails (1 failure) |
| `test_multi_scale_limit_page_with_multiple_statements_passes_either_scale` | `failures == []` for millions, `failures == []` for thousands | Stated limit in docs: page with '(In millions)' and '(In thousands)' holds candidate_words ['millions', 'thousands'], matching either expected scale |
| `test_mda_unparenthesised_prose_cannot_confirm_scale_and_stops` | `len(failures) == 1`, 'no unit statement on page 2 or 1' | Stated limit in docs: '$1.2 billion' in prose lacks parentheses; `_PARENTHESISED_GROUP` finds no group -> 1 failure |
| `test_page_beyond_pdf_page_count_stops` | `len(failures) == 1`, 'page 5 is beyond the last page of the filing (2 pages)' | Closed-form identity: row cites page 5; PDF page count is 2; 5 > 2 -> unconfirmed page beyond filing |
| `test_page_with_no_text_layer_stops` | `len(failures) == 1`, 'page 2 has no text layer' | Closed-form identity: page 2 text is empty; statement_desc is 'page 2 has no text layer' -> 1 failure |
| `test_balance_sheet_rows_checked_for_scale` | `len(failures) == 1`, 'page 3 (money figures)', 'Cash and equivalents' | Hand arithmetic: B/S cash row on page 3 without unit statement on page 3 or 2 -> 1 failure |
| `test_empty_rows_returns_empty_failures_and_prints_summary` | `failures == []`, summary line shows 0 checked, 0 pages, 0 not confirmed | Hand arithmetic: total_rows == 0 -> returns [] immediately, summary line prints 0 checked |
| `test_summary_line_counts` | Summary line prints '3 checked, 2 pages, 2 pages not confirmed.' | Hand arithmetic: 3 rows (revenue on page 1, cfo on page 2, capex on page 2); cited pages {1, 2} = 2; both pages unconfirmed = 2 |
| `test_route_a_retry_exhaustion_raises_value_error_on_unconfirmed_scale` | `len(calls) == 3`, `ValueError` raised naming page 3 scale failure | Hand arithmetic: MAX_RETRIES = 2 -> 1 initial + 2 retries = 3 calls; exhausted retries raise ValueError |
| `test_route_b_cmd_check_exits_2_on_scale_failure` | `exit_code == 2`, `load_session_extraction` raises `ValueError` | Closed-form contract: Route B loader stops on any unit failure (exit 2) |
| `test_unit_statement_page_failures_combines_unit_and_row_scale_failures` | `len(failures) >= 2`, holds Check A and Check B1 failures | Closed-form contract: returns `_unit_statement_failures + _row_scale_failures` |
| `test_candidate_raising_value_error_is_discarded_for_kind` | `len(failures) == 1`, '(share count)' fails | Hand arithmetic: '(dollars in millions)' raises ValueError for 'share count'; candidate discarded; 1 failure |
| `test_real_walmart_filing_scale_confirmation` | `failures == []` on page 21; `len(failures) == 1` on page 2 | Walmart 10-K PDF page 21: reads '(Amounts in millions, except per share data)'; page 1 and 2 print no unit statement |
| `test_real_chipotle_filing_scale_mismatch` | `len(failures) == 1`, 'found (in thousands, except per share data)' | Chipotle 10-K PDF page 29: reads '(in thousands, except per share data)' |
| `test_real_okta_filing_two_scales` | `failures == []` clean; `len(failures) == 1` when share_units expects millions | Okta 10-K PDF page 58: reads '(dollars in millions, shares in thousands, except per share data)' |
| `test_real_lhx_filing_multi_scale_limit` | `failures == []` for millions; `failures == []` for thousands | L3Harris 10-K PDF page 62: reads both '(In millions)' and '(In thousands)' |

### Counts

- **Accuracy:** 67 / 67 assertions matching independently derived expected values (100% accuracy). Unit: assertions.
- **Coverage:** 1 / 1 new function added by unit (`_row_scale_failures`), 73 / 73 statements (100% statement coverage), all branches covered (100% branch coverage). Unit: functions, statements, branches.

---

## What I did not do

- Did not modify implementation code (`ingestion/claude_extractor.py`, `docs/`, etc.): enforced by permission and role separation.
- Did not touch pre-existing red tests (`test_projector_rule3_red.py`, `test_routes_session_rule3_red.py`).
- Did not make any paid API calls or live network requests.

---

## Findings for the orchestrator

1. **Check B1 and Route B exit code on pages with no text layer:** In P12a, `test_check_exits_1_on_a_page_with_no_text_layer` expected exit 1 (warnings only). Under P14b Check B1, a cited page with no text layer cannot confirm the scale of figures citing it, so `session_extraction check` stops with exit 2. The test in `test_page_check.py` was updated accordingly to assert exit 2.
2. **All 31 fixture test failures resolved:** All synthetic fixture failures were traced to missing unit statements on cash flow statement pages (page 52 and 3), now cleanly repaired in `_pass1_pdf.py`.
3. **Full suite green except 2 designated red tests:** 1061 passed, 2 failed.
