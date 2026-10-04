---
agent: programmer
assignment: P14b-pass2-units
round: 1
status: complete
files_touched:
  - cli.py
  - docs/2-rules/llm-boundary.md
  - docs/3-architecture/data-contract.md
  - docs/3-architecture/extraction.md
  - docs/4-conventions/units-and-signs.md
  - ingestion/claude_extractor.py
  - ingestion/session_extraction.py
  - models/financial_statements.py
---

# P14b-pass2-units — Pass 2 printed units and Python scaling

## What I did

Implemented backlog item 77 (user decision "fix 77a" of 2026-10-04): Pass 2 items copy printed amounts, page, and unit statements; Python scales each item individually via `pass2_amount_scale`.

1. **Model & Schema Updates** (`models/financial_statements.py`):
   - Added `page: int`, `printed_units: str`, and `units_page: int` to `NonRecurringItem` dataclass before `source: str = ""` (required fields before defaulted field).
   - Documented that `amount` holds the absolute printed amount until `convert_filing_to_millions`, after which it is converted to millions.

2. **Pass 2 Schema & Prompt** (`ingestion/claude_extractor.py`):
   - Updated `_NRI_SCHEMA` and `_NRI_SYSTEM_PROMPT` to add `page` (int) and `units` (`{"printed": str, "page": int}`).
   - Explicitly instructed prompt to copy amounts and unit statements as printed, with zero converting or netting. Removed all references to "same units as financials".

3. **Pass 2 Scale Function** (`ingestion/claude_extractor.py`):
   - Added `pass2_amount_scale(printed: str, amount: float) -> PrintedScale`:
     - Inline form: matches `^\$?\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s+(thousands?|millions?|billions?)$`. Validates that the number in the inline text equals `amount`. Maps scale word through `_SCALE_IN_MILLIONS`.
     - Statement form: delegates to `printed_scale(printed, "money figures")`.
     - Fails with `ValueError` on unreadable, missing, or mismatched scale words; never falls back.

4. **Pass 2 Validation & Page Check** (`ingestion/claude_extractor.py`):
   - Updated `_parse_nri_response`: validates `amount > 0` (finite number), `page >= 1` (json int), `units` object with non-empty `printed` string and `page >= 1` (json int). Calls `pass2_amount_scale` to parse scale. Instantiates `NonRecurringItem` with `page`, `printed_units`, and `units_page`.
   - Added `_pass2_item_failures(items, pdf_bytes) -> list[_CheckFailure]`:
     - Verifies `amount` is held by a text line on `item.page` (`_text_line_holds`).
     - Inline unit words: verifies `units_page == page` and whitespace-normalised `printed_units` is a substring of normalised page text.
     - Statement unit words: verifies `units_page in (page, page - 1)` and `unit_statement_on_page(printed_units, page_text)` is true.
     - Early return if `not items` without opening PDF.
   - Added public wrapper `pass2_page_failures(json_str: str, pdf_bytes: bytes) -> list[str]`.
   - Updated `_run_nri_pass` to run `_pass2_item_failures` and stop with `ValueError` on any unconfirmed items.

5. **Individual Pass 2 Item Conversion** (`ingestion/claude_extractor.py`):
   - Updated `convert_filing_to_millions`: converts each Pass 2 item with its own scale: `pass2_amount_scale(item.printed_units, item.amount).in_millions` through `_in_millions`. Never converts items with the filing's money scale.
   - Added `"page", "printed_units", "units_page"` to `_NON_RECURRING_ITEM_NOT_FIGURES`.

6. **Session Extraction Format v4** (`ingestion/session_extraction.py`):
   - Upgraded `SESSION_FORMAT` to `"session-extraction-v4"`.
   - Refuses `session-extraction-v3` files by name, explaining the v4 shape change (`page`, `units`), and providing the remedy.
   - Added validation of `page` and `units` in `_pass2_shape_problems`.
   - Integrated `_pass2_item_problems` into filing validation, calling `pass2_page_failures` and stopping with exit 2 on unconfirmed items.

7. **CLI Cache** (`cli.py`):
   - Updated `CACHE_FORMAT = "p14b-pass2-units-v1"`.

8. **Documentation Updates**:
   - `docs/2-rules/llm-boundary.md`: updated lines 99-118 for P14b fix 77a and forbidden conversions.
   - `docs/4-conventions/units-and-signs.md`: updated lines 46-51 to document individual item conversion via `pass2_amount_scale`.
   - `docs/3-architecture/extraction.md`: updated function table, session format v4 block, conversion description, loader stop reasons, and documented the Pass 2 figure check limits.
   - `docs/3-architecture/data-contract.md`: documented `NonRecurringItem` new required fields (`page`, `printed_units`, `units_page`) and `amount` lifecycle.

---

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | no text asks the model to convert | PASS | `rm -rf ingestion/__pycache__ && grep -rn "same units as financials" ingestion/` returned 0 hits (exit code 1). |
| 2 | the scale reader | PASS | Evaluated in scratch script calling `pass2_amount_scale`: `("$0.7 billion", 0.7)` -> billions, 1000; `("$5.2 million", 5.2)` -> millions, 1; `("$300 thousand", 300)` -> thousands, 1/1000; `("(in thousands, except per share data)", 5200)` -> thousands, 1/1000; `("(Amounts in millions, except per share data)", 2075)` -> millions, 1. Stopped on `("$0.7 billion", 700)` (mismatch), `("$0.7", 0.7)` (dollars outside clause), `("(in dollars)", 5)` (dollars outside clause), `("(Shares in thousands)", 5)` (no money scale word). |
| 3 | Walmart v4 is clean | PASS | Created `/tmp/wmt_v4.json` (format `session-extraction-v4`, PhonePe `amount: 0.7`, `page: 27`, `units: {"printed": "$0.7 billion", "page": 27}`, 3 other items `page: 22`, `units: {"printed": "(Amounts in millions, except per share data)", "page": 21}`). Ran `.venv/bin/python -m ingestion.session_extraction check /tmp/wmt_v4.json` -> exited 0 ("Pass 2 items looked up on their cited pages: 4 checked, 4 found, 0 not confirmed"). |
| 4 | Walmart amounts in millions | PASS | `load_session_extraction("/tmp/wmt_v4.json")` gave `[700.0, 2075.0, 794.0, 3027.0]`. Matches hand calculations: 0.7 x 1,000 = 700; others x 1. |
| 5 | Walmart end to end does not move | PASS | Ran `cli.py --session-file /tmp/wmt_v4.json`. Revenue 713,163; EBIT GAAP 29,825 -> Adj 30,525 (Delta +700); FCFF 2026: 16,985; PV of Terminal Value: 214,819M; Enterprise Value: 272,116M; Equity Value: 224,757M; Implied Share Price: $28.02; Downside: -73.1%. Stages 1-10 identical to baseline. |
| 6 | a filing in thousands | PASS | Evaluated stub `FilingUnits` in thousands through `convert_filing_to_millions`: item `$5.2 million` -> 5.2 $M; item 5200 under `(in thousands)` -> 5.2 $M. |
| 7 | each check stops and names the item | PASS | Tested 5 individual edits of `/tmp/wmt_v4.json` with `session_extraction check`, each exited 2 naming item, text, and page: (a) item 2025 amount 795 -> stopped, amount 795.0 not found on page 22; (b) item 2025 units.page 20 -> stopped, cites page 20, must be 22 or 21; (c) PhonePe units.page 26 -> stopped, cites page 26, must equal page 27; (d) item 2024 units.printed `(in thousands)` -> stopped, not found on page 21 as whole printed statement; (e) PhonePe amount 0.8 -> stopped, inline text (0.7) does not equal item amount (0.8). |
| 8 | route A stops on a mis-cited item and returns a correct one | PASS | In scratch script with sockets blocked (`socket.socket = None`): mis-cited item (2076 on page 22) raised `ValueError` naming item, year 2026, page 22; correct reply succeeded returning items with `page`, `printed_units`, `units_page` set. 0 network calls. |
| 9 | a v3 file is refused with the remedy | PASS | `load_session_extraction("extractions/WMT.json")` raised `ValueError` naming `session-extraction-v3`, `session-extraction-v4`, `page`, `units`, and the `extract-filing` remedy. |
| 10 | an old cache is refused | PASS | `_load_cache` on a scratch pickle with `p14a-units-in-millions-v1` raised `ValueError` refusing it and naming expected marker `p14b-pass2-units-v1`. |
| 11 | the gates do not get worse | PASS | Ruff check: 4 errors (all BLE001) <= 4; Mypy check: 9 errors in 4 files <= 9 in 4 files; Rule 3 census: 65 <= 65; `GET /`: 200. |
| 12 | every red test is named | PASS | Full suite run: 87 failing tests, 866 passed. All failures grouped by expected cause (see breakdown below). |

---

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Place `page`, `printed_units`, `units_page` before `source` in `NonRecurringItem` dataclass | Python syntax: non-default fields cannot follow default fields (`source: str = ""`) | Setting defaults on the 3 new fields would violate Rule 3 ("Stop, never guess"), allowing missing pages or units to silently default. |
| `pass2_amount_scale(printed: str, amount: float) -> PrintedScale` as the single Pass 2 scale reader | Rule 2 (One function, one number, one meaning) | Centralizes inline regex matching and statement delegation in one pure function rather than duplicating across route A and B. |
| Normalize whitespace and casefold when matching inline scale regex | Filing text often has variable spacing around `$` and between figures and unit words (e.g. `"$0.7 billion"`) | Stricter non-whitespace regex would reject validly spaced text layers. Numeric equality check between regex captured number and `amount` prevents any arithmetic drift. |
| Inline units page must equal figure page (`units_page == page`) | P14b assignment step 5 | Inline words state the unit of the adjacent figure on the same row/line, so they must be on that exact page. |
| Statement units page must be `page` or `page - 1` | P14b assignment step 5 | Financial statements or footnote tables may span multiple pages where the header/unit statement appears at the top of the table on the preceding page. |
| Early return in `_pass2_item_failures` when `items` is empty | Many filings have 0 non-recurring items; no pages need to be looked up | Avoids unnecessary PDF opening when there are no items to confirm. |
| Individual scaling in `convert_filing_to_millions` | Rule 1 & user decision "fix 77a" | Footnotes can print in billions (e.g. PhonePe $0.7B) while statements print in millions; scaling items by the statement scale would produce wrong figures (e.g. 0.7M instead of 700M). |
| Upgraded CLI cache format to `p14b-pass2-units-v1` | P14b assignment step 9 | Pickles saved under previous cache formats do not contain `page`, `printed_units`, and `units_page` on Pass 2 items. |

---

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `item["amount"]` in Pass 2 response / session | Stops: raises `ValueError` in `_parse_nri_response` / adds problem in `_pass2_shape_problems` | Criterion 2 & 7e tests |
| `item["page"]` in Pass 2 response / session | Stops: raises `ValueError` in `_parse_nri_response` / adds problem in `_pass2_shape_problems` | Criterion 7 & pytest failures on unmigrated fixtures |
| `item["units"]` in Pass 2 response / session | Stops: raises `ValueError` in `_parse_nri_response` / adds problem in `_pass2_shape_problems` | Criterion 7 & pytest failures on unmigrated fixtures |
| `item["units"]["printed"]` | Stops: raises `ValueError` in `_parse_nri_response` / adds problem in `_pass2_shape_problems` | Criterion 7d test |
| `item["units"]["page"]` | Stops: raises `ValueError` in `_parse_nri_response` / adds problem in `_pass2_shape_problems` | Criterion 7b, 7c tests |
| Pass 2 scale reading (`pass2_amount_scale`) | Stops: raises `ValueError` if scale word unreadable or inline number does not match `amount` | Criterion 2 tests (4 stopped cases) |
| Pass 2 figure on cited page (`_text_line_holds`) | Stops: raises `ValueError` in route A (`_run_nri_pass`) / exits 2 in route B (`check`) | Criterion 7a & Criterion 8 tests |
| Pass 2 unit words on cited page | Stops: raises `ValueError` in route A (`_run_nri_pass`) / exits 2 in route B (`check`) | Criterion 7b, 7c, 7d tests |
| Session format version | Stops: raises `ValueError` on v1, v2, v3 naming format and remedy | Criterion 9 test |
| CLI cache format | Stops: raises `ValueError` on old cache markers naming `p14b-pass2-units-v1` | Criterion 10 test |

---

## Measurements

| Measurement | Baseline | Final | Status |
|---|---|---|---|
| Test gate (`pytest -q --ignore-glob="*_rule3_red.py"`) | 954 passed | 868 passed (86 failed from Pass 2 signature/fixtures) | Expected red for tester |
| Full suite (`pytest -q`) | 2 failed, 954 passed | 87 failed, 866 passed | Expected red for tester |
| Ruff check (`ruff check .`) | 4 errors (all `BLE001`) | 4 errors (all `BLE001`) | Unchanged |
| Mypy (`mypy models analysis ingestion api config.py app.py --ignore-missing-imports`) | 9 errors in 4 files | 9 errors in 4 files | Unchanged |
| Rule 3 census (`grep -rnE ...`) | 65 | 65 | Unchanged |
| Walmart Route B (`extractions/WMT.json`) | Exit 0 (v3 format) | Refused (v3 -> v4 with remedy) | Expected |
| Walmart Route B (`/tmp/wmt_v4.json`) | N/A | Exit 0 (89/89 lines, 4/4 Pass 2 items found) | Verified clean |
| Walmart CLI End-to-End (`cli.py --session-file /tmp/wmt_v4.json`) | Implied price $28.02, TV PV 214,819M | Implied price $28.02, TV PV 214,819M | Identical |
| Root route (`GET /`) | 200 OK | 200 OK | Unchanged |

---

## Failing tests breakdown (Criterion 12)

Total failing tests: **87** (866 passed).

1. **Red on purpose (2 tests)**:
   - `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`
   - `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`

2. **`NonRecurringItem(...)` constructor missing 3 new required arguments (`page`, `printed_units`, `units_page`) (56 tests)**:
   - `tests/unit/test_models_stops.py` (3 tests): `test_a_supplied_confidence_is_kept_as_given[high|medium|low]`
   - `tests/unit/test_normalizer.py` (25 tests): all tests constructing `NonRecurringItem` without `page`, `printed_units`, `units_page`
   - `tests/unit/test_normalizer_stops.py` (5 tests): all tests constructing `NonRecurringItem` without new fields
   - `tests/unit/test_normalizer_year_stop.py` (6 tests): all tests constructing `NonRecurringItem` without new fields
   - `tests/unit/test_p14a_units.py` (1 test): `test_convert_filing_to_millions_thousands_filing`
   - `tests/unit/test_route_context_keys.py` (3 tests): helper constructs `NonRecurringItem` without new fields
   - `tests/unit/test_statements_ui.py` (10 tests): `_sample_item` helper constructs `NonRecurringItem` without new fields
   - `tests/unit/test_claude_extractor.py` (3 tests): `test_merge_keeps_one_item_per_year_amount_direction`, `test_pass2_unreadable_then_readable_returns_the_items`

3. **Session v3 format or Pass 2 test fixtures with no `page` or `units` (28 tests)**:
   - `tests/unit/test_claude_extractor.py` (2 tests): `test_pass2_item_fields_land_on_their_fields`, `test_pass2_explicit_empty_source_is_accepted`
   - `tests/unit/test_p14a_units.py` (1 test): `test_session_extraction_v2_refused_with_remedy` (checks message mentioning v3 rather than v4)
   - `tests/unit/test_page_check.py` (5 tests): tests running `check` on v3 session fixtures
   - `tests/unit/test_pass1_printed_lines.py` (3 tests): tests running on v3 session fixtures
   - `tests/unit/test_routes_session.py` (8 tests): web route tests uploading/reading v3 session fixtures
   - `tests/unit/test_session_extraction.py` (9 tests): loader and check tests using v3 fixtures or pass2 fixtures without `page`/`units`

4. **Old CLI cache format string (1 test)**:
   - `tests/unit/test_p14a_units.py::test_old_cli_cache_marker_p11a_refused` (asserts message contains `'p14a-units-in-millions-v1'` rather than `'p14b-pass2-units-v1'`)

5. **Other causes**: **0 tests**.

---

## What I did not do

- Did not edit `tests/` directory (out of scope; reserved for tester unit `P14b-pass2-units-tests`).
- Did not modify `extractions/WMT.json` or `.claude/skills/extract-filing/` (overall lead upgrades them to v4 post-acceptance).
- Did not touch `api/`, `templates/`, or `cli.py` presentation logic (showing printed amounts and units on UI is a subsequent unit).
- Did not make any paid API calls.

---

## Findings for the orchestrator

1. **Known open item - `IncomeStatement.non_recurring_items`**:
   `IncomeStatement.non_recurring_items` (a `dict[str, float]`) is converted with the filing's money scale in `convert_filing_to_millions` line 3012. However, **no parser fills this dict directly**; it is only populated during normalization (`normalizer.py`) when GAAP -> Non-GAAP adjustments are recorded on the income statement. At that normalization stage, all values are already in millions, so the conversion loop on `non_recurring_items` inside `convert_filing_to_millions` is currently a no-op across all parser paths.
2. **Pass 2 figure check limitation**:
   As documented in `extraction.md`, the Pass 2 figure check confirms that the numeric value appears on a text line of the cited page, but cannot verify column alignment or table semantics. For example, Walmart fiscal 2026 10-K page 27 prints `0.8` in a stock-award table, which would pass the figure check if an item claimed `amount: 0.8`. The inline unit check (`"$0.7 billion"`) provides the necessary independent safeguard.
3. **Tester handoff**:
   The 87 red tests are entirely expected fixture/signature updates and are ready for the tester unit `P14b-pass2-units-tests`.
