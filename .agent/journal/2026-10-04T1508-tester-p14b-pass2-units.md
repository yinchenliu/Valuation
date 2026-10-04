---
agent: tester
assignment: P14b-pass2-units-tests
round: 1
status: complete
files_touched:
  - tests/unit/_pass1_pdf.py
  - tests/unit/_session_route_helpers.py
  - tests/unit/test_claude_extractor.py
  - tests/unit/test_models_stops.py
  - tests/unit/test_normalizer.py
  - tests/unit/test_normalizer_stops.py
  - tests/unit/test_normalizer_year_stop.py
  - tests/unit/test_p14a_units.py
  - tests/unit/test_p14b_units.py
  - tests/unit/test_page_check.py
  - tests/unit/test_pass1_printed_lines.py
  - tests/unit/test_route_context_keys.py
  - tests/unit/test_session_extraction.py
  - tests/unit/test_statements_ui.py
verdict: pass
---

# P14b-pass2-units-tests — Repair fixtures and test suites for session v4 and NonRecurringItem fields, and lock P14b unit behaviors

## What I did

Repaired all 87 existing test failures across 13 test files resulting from the `P14b-pass2-units` implementation changes:
1. Updated `NonRecurringItem` constructor calls to include required fields `page`, `printed_units`, and `units_page` (58 tests across `test_models_stops.py`, `test_normalizer.py`, `test_normalizer_stops.py`, `test_normalizer_year_stop.py`, `test_route_context_keys.py`, `test_statements_ui.py`, `test_p14a_units.py`, `test_claude_extractor.py`, `test_session_extraction.py`).
2. Updated test fixtures to format `session-extraction-v4` with required `page` and `units: {"printed": ..., "page": ...}` objects on Pass 2 items, and updated `_pass1_pdf.py` to print cited Pass 2 items and unit statements so page check validations succeed honestly (28 tests across `_session_route_helpers.py`, `test_page_check.py`, `test_pass1_printed_lines.py`, `test_session_extraction.py`).
3. Updated CLI cache marker assertion from `p14a-units-in-millions-v1` to `p14b-pass2-units-v1` in `test_p14a_units.py`.
4. Created dedicated test suite `tests/unit/test_p14b_units.py` locking:
   - `pass2_amount_scale` inline regex matching, plural and whitespace variants, statement delegation, and Rule 3 stops (amount mismatch, missing scale word, unreadable scale word).
   - Pass 2 page checks (`_pass2_item_failures` and `pass2_page_failures`) verifying figure presence, inline unit equality/substring on same page, statement unit on `page` or `page - 1`, and failure message contents.
   - Individual Pass 2 item scaling in `convert_filing_to_millions` with mixed footnote and statement scales in one filing, and filing in thousands with footnote in millions.
   - Rejection of `session-extraction-v3` with remedy message and rejection of old CLI cache markers in `cli._load_cache`.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | gate form | PASS | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` -> 1001 passed, 0 failed in 8.47s |
| 2 | full suite | PASS | `.venv/bin/python -m pytest -q` -> exactly 2 failures: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`, 1001 passed in 8.68s |
| 3 | no assertion weakened | PASS | `git diff tests/` shows only required field additions and v4 format updates; no numerical assertions loosened or removed |
| 4 | new tests can fail | PASS | Scratch mutations turning `test_p14b_units.py` red: scale multiplier mutation (exit code 1), individual scaling mutation (exit code 1), session v3 message mutation (exit code 1) |
| 5 | lint | PASS | `.venv/bin/python -m ruff check .` -> 4 errors (all pre-existing BLE001 in api and cli), 0 in `tests/` |
| 6 | mypy | PASS | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` -> 9 errors in 4 files, 0 in `tests/` |
| 7 | two counts | PASS | Accuracy: 92/92 assertions in `test_p14b_units.py` (100%); Coverage: 81% overall on touched modules, 100% on new P14b functions |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Populate test fixture `NonRecurringItem` calls with valid fields `page=1, printed_units="(Amounts in millions)", units_page=1` | Required fields on `NonRecurringItem` dataclass cannot take defaults (Rule 3) | Passing dummy values or empty strings would trigger validation errors in downstream functions. |
| Extend `_pass1_pdf.py` to extract and print Pass 2 items and unit statements | Route tests check that all cited figures and units exist on cited pages in generated PDFs | Mocking or bypassing page checks in tests would weaken test realism; printing them in generated PDFs keeps tests honest. |
| Use exact hand-derived arithmetic for all `pass2_amount_scale` and `convert_filing_to_millions` assertions | Rule 1 & Tester guidelines ("Never the code's own output") | All expected values derived by hand before running tests. |
| Keep session format v4 validation strictly isolated from v3 | Session format contract upgrade | Session format v3 files cannot be parsed automatically because they lack required citation pages and unit statements. |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| Inline unit text number | stops with `ValueError` naming text number and amount if they differ | `ingestion/claude_extractor.py:796`, `tests/unit/test_p14b_units.py:test_pass2_amount_scale_stops_on_inline_number_mismatch` |
| Inline scale word | stops with `ValueError` ("it holds no scale word") | `ingestion/claude_extractor.py:750`, `tests/unit/test_p14b_units.py:test_pass2_amount_scale_stops_on_missing_or_unreadable_scale` |
| Money scale in statement | stops with `ValueError` if statement specifies shares only or dollars outside clause | `ingestion/claude_extractor.py:727,750`, `tests/unit/test_p14b_units.py:test_pass2_amount_scale_stops_on_missing_or_unreadable_scale` |
| Pass 2 amount on cited page | stops with check failure naming item description, year, amount, and page | `ingestion/claude_extractor.py:1623`, `tests/unit/test_p14b_units.py:test_pass2_page_checks_figure_found_and_not_found` |
| Pass 2 cited page > PDF page count | stops with check failure naming page and total PDF pages | `ingestion/claude_extractor.py:1600`, `tests/unit/test_p14b_units.py:test_pass2_page_checks_figure_page_beyond_pdf_or_no_text` |
| Pass 2 cited page has no text layer | stops with check failure naming page has no text layer | `ingestion/claude_extractor.py:1613`, `tests/unit/test_p14b_units.py:test_pass2_page_checks_figure_page_beyond_pdf_or_no_text` |
| Inline units page != figure page | stops with check failure naming units page and figure page | `ingestion/claude_extractor.py:1660`, `tests/unit/test_p14b_units.py:test_pass2_page_checks_inline_units` |
| Inline units text on cited page | stops with check failure naming units text and page | `ingestion/claude_extractor.py:1671`, `tests/unit/test_p14b_units.py:test_pass2_page_checks_inline_units` |
| Statement units page not in (page, page - 1) | stops with check failure naming units page and allowed pages | `ingestion/claude_extractor.py:1682`, `tests/unit/test_p14b_units.py:test_pass2_page_checks_statement_units` |
| Statement units whole statement on page | stops with check failure stating statement not found as whole printed statement | `ingestion/claude_extractor.py:1693`, `tests/unit/test_p14b_units.py:test_pass2_page_checks_statement_units` |
| Session format v3 file | stops with `ValueError` naming v3, v4, page, units, and extract-filing remedy | `ingestion/session_extraction.py:288`, `tests/unit/test_p14b_units.py:test_session_extraction_v3_refused_with_remedy` |
| CLI cache marker mismatch | stops with `ValueError` naming expected marker `p14b-pass2-units-v1` | `cli.py:358`, `tests/unit/test_p14b_units.py:test_cli_cache_refuses_old_marker` |

## Measurements

- Suite before test repair: 87 failing tests, 866 passing tests (gate run).
- Suite after test repair and new tests: 0 failing tests, 1001 passing tests (gate run).
- Full suite run: exactly 2 pre-existing failures (`test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`), 1001 passing tests.
- Lint (`ruff check .`): 4 pre-existing errors (all `BLE001` in `api/` and `cli.py`), 0 in `tests/`.
- Types (`mypy models analysis ingestion api config.py app.py --ignore-missing-imports`): 9 pre-existing errors in 4 files, 0 in `tests/`.
- Accuracy count: 92 / 92 assertions in `test_p14b_units.py` matched independently derived values (100% accuracy).
- Coverage count:
  - `ingestion/claude_extractor.py`: 77% (737 / 951 statements; 100% of P14b added functions).
  - `ingestion/session_extraction.py`: 84% (436 / 521 statements; 100% of P14b added functions).
  - `models/financial_statements.py`: 89% (178 / 199 statements; 100% of P14b added dataclass fields).
  - Total across 3 touched modules: 81% (1351 / 1671 statements).

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `pass2_amount_scale("$0.7 billion", 0.7)` | `word="billions", in_millions=Fraction(1000, 1)` | Hand derivation: $0.7 billion = $700.0M; scale multiplier 1,000 |
| `pass2_amount_scale("$5.2 million", 5.2)` | `word="millions", in_millions=Fraction(1, 1)` | Hand derivation: $5.2 million = $5.2M; scale multiplier 1 |
| `pass2_amount_scale("$300 thousand", 300.0)` | `word="thousands", in_millions=Fraction(1, 1000)` | Hand derivation: $300 thousand = $0.3M; scale multiplier 1/1,000 |
| `pass2_amount_scale("(Amounts in millions, except per share data)", 2075.0)` | `word="millions", in_millions=Fraction(1, 1)` | Hand derivation: statement specifies millions; multiplier 1 |
| `pass2_amount_scale("(in thousands, except per share data)", 5200.0)` | `word="thousands", in_millions=Fraction(1, 1000)` | Hand derivation: statement specifies thousands; multiplier 1/1,000 |
| Mixed scales PhonePe: $0.7B converted | `700.0` | Hand arithmetic: 0.7 * 1,000 = 700.0 $M |
| Mixed scales Restructuring: 2075.0 in millions converted | `2075.0` | Hand arithmetic: 2075.0 * 1 = 2075.0 $M |
| Mixed scales Legal: $300 thousand converted | `0.3` | Hand arithmetic: 300.0 * 0.001 = 0.3 $M |
| Mixed scales Severance: 5200.0 in thousands converted | `5.2` | Hand arithmetic: 5200.0 * 0.001 = 5.2 $M |
| Filing in thousands, footnote item $5.2 million converted | `5.2` | Hand arithmetic: 5.2 * 1 = 5.2 $M (individual scaling, not filing scale 1/1000) |
| Filing in thousands, statement item 5200.0 in thousands converted | `5.2` | Hand arithmetic: 5200.0 * 0.001 = 5.2 $M |

## What I did not do

- Did not modify any implementation code in `models/`, `ingestion/`, `analysis/`, or `cli.py` (strict tester boundary).
- Did not make external network or paid API calls. All test PDFs were constructed in-memory and written to `tmp_path`.

## Findings for the orchestrator

None. All 87 failing tests repaired, dedicated suite `test_p14b_units.py` added and passing, all done-criteria satisfied with verdict `pass`.
