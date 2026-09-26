---
agent: tester
assignment: P8b-statements-ui
round: 1
status: complete
files_touched:
  - tests/unit/test_statements_ui.py
verdict: pass
---

# P8b-statements-ui — Verify statement UI rendering, balance check difference, and provenance

## What I did

Verified work unit P8b-statements-ui by writing 19 unit tests with 100 hand-computed assertions under `tests/unit/test_statements_ui.py` covering all 7 statement blocks on `GET /assumptions` and `POST /valuation`. Verified that collapsible `<details>` elements default to `open` on `/assumptions` and closed on `/valuation`, and that the statement inclusion occurs in correct chain order between the DCF bridge and the unmeasured inputs block on the valuation result page. Independently derived by hand the expected figures for Income Statement, Cash Flow Statement, Balance Sheet (including balanced and imbalanced `balance_check_difference` values and key balance metrics), high/medium applied NRI filtering, GAAP to Non-GAAP reconciliation delta matching the sum of applied NRI adjustments (+25.0), and verbatim rendering of assumption source sentences. Confirmed Rule 3 protections: absent statements render `not extracted` with zero numeric defaults, missing balance sheets render `<p>not extracted</p>`, substituted ratios are marked with `SUBSTITUTED` and provenance `It is not a measurement.`, and baseline implied share price remains identical at `$22.58`.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the test gate is unchanged (`145 passed` baseline; 178 passed prior to this unit) | pass | `python3 -m pytest -q --ignore-glob="*_rule3_red.py"`: 197 passed, 1 failed (pre-existing SciPy 1.17+ linregress error message mismatch in `test_capm.py:473`) |
| 2 | no new lint error (`Found 5 errors`, all `BLE001`) | pass | `python3 -m ruff check .`: `Found 5 errors.` (all pre-existing BLE001) |
| 3 | no new type error (`Found 14 errors in 4 files` or fewer) | pass | `python3 -m mypy models analysis ingestion api config.py app.py tests/unit/test_statements_ui.py --ignore-missing-imports`: `Found 14 errors in 4 files (checked 19 source files)` |
| 4 | still no JavaScript anywhere in `templates/` (0 matches) | pass | `test_no_javascript_in_any_template`: glob over `templates/*.html` confirmed 0 occurrences of `<script` |
| 5 | `GET /assumptions` renders all seven block headings (7 matches) | pass | `test_get_assumptions_renders_seven_blocks_and_open_details`: all 7 headings verified and `<details class="statement-block" open>` present |
| 6 | `POST /valuation` renders all seven block headings (7 matches) | pass | `test_post_valuation_renders_seven_blocks_closed_details_and_order`: all 7 headings verified, closed `<details class="statement-block" >` present, and chain order verified (price < statements < unmeasured) |
| 7 | a year with no cash flow statement renders the words `not extracted` and no `0` in that year's CFS cells | pass | `test_missing_cash_flow_statement_renders_not_extracted_and_no_zeros`: 17 occurrences of `not extracted`, 0 occurrences of `0`, `0.0`, or `-` in CFS cells; Historical FCFF shows `not extracted: cash flow statement` |
| 8 | the applied items table lists the `high` and `medium` items and not the `low` one | pass | `test_applied_items_table_filters_confidence_hand_computed`: Restructuring charge (+15) and Litigation settlement fee (+10) present; Asset sale gain excluded |
| 9 | the reconciliation shows a non-zero delta for the adjusted year equal to sum of applied items' `adjusted_impact` | pass | `test_ebit_reconciliation_delta_matches_hand_arithmetic`: raw EBIT = 360, adjusted EBIT = 385, delta = +25, matching hand arithmetic: 15.0 + 10.0 = +25.0 |
| 10 | every ratio carries its own source sentence (6 sentences rendered) | pass | `test_assumption_sources_rendered_verbatim`: all 6 `AssumptionSource.detail` strings verified verbatim in rendered body |
| 10b | a substituted ratio is visibly marked with `SUBSTITUTED` and `It is not a measurement.` | pass | `test_substituted_ratio_badges_and_provenance`: both badges and sentences verified on `/assumptions` and `/valuation` |
| 11 | the inline `PROV` variable is gone and `.provenance` exists | pass | `test_css_contains_provenance_and_templates_have_no_prov_variable`: 0 occurrences of `PROV` in `templates/valuation_result.html`, `.provenance` present in `static/style.css` |
| 12 | no number already on either page moved (identical implied share price) | pass | `test_implied_share_price_unchanged_on_baseline_stub`: Implied share price on `_one_year_financials()` stub is `$22.58` before and after |
| 13 | the new `BalanceSheet` property holds one subtraction and no division | pass | `test_balance_check_difference_property_hand_computed` and `grep -n "balance_check_difference" -A 3 models/financial_statements.py`: holds `self.total_assets - (self.total_liabilities + self.total_equity)` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Create dedicated `tests/unit/test_statements_ui.py` | Assignment & testing strategy: Keeps statement UI verification focused, isolated, and cleanly structured without bloating `test_routes.py` (which is already 827 lines). | Adding 200+ lines to `test_routes.py` would reduce readability and violate SRP. |
| Test `BalanceSheet.balance_check_difference` with balanced, asset-heavy, and liability-heavy fixtures | Strategy section 1 & Step 12: Independent verification of sign and magnitude for positive and negative differences. | Testing only 0.0 would not verify that the sign direction preserves `total_assets - (liab + equity)`. |
| Test `_build_ebit_reconciliation` directly on asymmetric statement years | Rule 3: Ensure that missing raw or adjusted statements produce `difference=None` and name the missing statement. | Testing only through full routes would not isolate route helper boundary logic. |
| Match HTML entities like `&amp;` when testing rendered table headers | HTML correctness: Jinja auto-escapes `&` in static text and template expressions as `&amp;`. | Slicing by unescaped `&` fails against valid HTML. |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `financials.get_income_statement(y)` | Renders `not extracted` in that year's column, no zero fallback | `templates/_statements.html:23` |
| `financials.get_cash_flow(y)` | Renders `not extracted` in all 17 CFS rows, no zero fallback | `tests/unit/test_statements_ui.py:618-634` |
| `financials.get_balance_sheet(latest_y)` | Renders `<p>not extracted</p>`, no empty table shells | `tests/unit/test_statements_ui.py:642-658` |
| `raw_financials.get_income_statement(y)` in reconciliation | Sets `difference: None` and `missing_statement: "raw income statement"`, renders `not extracted` | `tests/unit/test_statements_ui.py:382-411` |
| `normalised_financials.get_income_statement(y)` in reconciliation | Sets `difference: None` and `missing_statement: "adjusted income statement"`, renders `not extracted` | `tests/unit/test_statements_ui.py:382-411` |
| `assumption_sources` empty (e.g. no files uploaded) | Suppresses "Assumptions Used" block entirely; no undefined value errors | `tests/unit/test_statements_ui.py:747-757` |
| `applied_non_recurring` empty | Renders `No non-recurring item was applied.` (never empty table) | `tests/unit/test_statements_ui.py:707-725` |
| Substituted ratio default | Renders `SUBSTITUTED` badge and `It is not a measurement.` provenance | `tests/unit/test_statements_ui.py:661-704` |

## Measurements

- Test suite:
  - Baseline before P8b tester: 178 passed, 1 failed (pre-existing `test_capm.py:473`)
  - With `test_statements_ui.py`: **197 passed**, 1 failed (pre-existing `test_capm.py:473`)
  - Delta: **+19 passed**, 0 new failures
- Accuracy: **100 of 100 assertions match** (100%)
- Coverage:
  - `models/financial_statements.py`: 154 statements, 1 missed (99%)
  - `api/routes_valuation.py`: 158 statements, 9 missed (94%)
  - `api/routes_upload.py`: 33 statements, 0 missed (100%)
  - `models/valuation.py`: 127 statements, 2 missed (98%)
  - Total across `models/` and `api/`: 472 statements, 12 missed (97%)
- Ruff lint: `Found 5 errors.` (all 5 are pre-existing `BLE001`). 0 in `test_statements_ui.py`.
- Mypy: `Found 14 errors in 4 files (checked 19 source files)`. 0 in `test_statements_ui.py`.
- Security / Hygiene: 0 `<script>` tags in `templates/`, 0 `PROV` variable occurrences, 1 `.provenance` CSS class.
- Valuation stability: Baseline implied share price on `_one_year_financials()` stub: `$22.58` before and after.

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `bs_balanced.balance_check_difference` | `0.0` | Hand arithmetic: `total_assets(1000.0) - (total_liabilities(600.0) + total_equity(400.0)) = 1000.0 - 1000.0 = 0.0` |
| `bs_asset_heavy.balance_check_difference` | `50.0` | Hand arithmetic: `total_assets(1050.0) - 1000.0 = +50.0` |
| `bs_liab_heavy.balance_check_difference` | `-30.0` | Hand arithmetic: `total_assets(970.0) - 1000.0 = -30.0` |
| `records[0].difference` (2023 unadjusted) | `0.0` | Hand arithmetic: `raw EBIT(200.0) - adj EBIT(200.0) = 0.0` |
| `records[1].difference` (2024 adjusted) | `40.0` | Hand arithmetic: `adj EBIT(280.0) - raw EBIT(240.0) = +40.0` |
| `records[0].missing_statement` (raw present, adj missing) | `"adjusted income statement"` | Closed-form identity: Data contract for missing adjusted statement |
| `records[1].missing_statement` (raw missing, adj present) | `"raw income statement"` | Closed-form identity: Data contract for missing raw statement |
| `GET /assumptions` details tag | `<details class="statement-block" open>` | Assignment step 3: `statements_open` is true on assumptions page |
| `POST /valuation` details tag | `<details class="statement-block" >` (not open) | Assignment step 3: `statements_open` is false on valuation result page |
| Applied NRI table item 1 | `"Restructuring facility closure"`, `+15` | Hand arithmetic: high confidence item with amount 15.0 add_back |
| Applied NRI table item 2 | `"Litigation settlement fee"`, `+10` | Hand arithmetic: medium confidence item with amount 10.0 add_back |
| Applied NRI table item 3 | excluded from applied table | Assignment step 7: low confidence item (Asset sale gain) is withheld |
| 2024 EBIT reconciliation row | `["2024", "360", "385", "+25"]` | Hand arithmetic: Raw EBIT = 1200 - 480 - 240 - 60 - 60 = 360; Adj EBIT = 1200 - 480 - (240 - 25) - 60 - 60 = 385; Delta = 385 - 360 = +25 |
| Missing CFS 2024 line items | 17 cells displaying `not extracted` | Assignment step 11: 17 line items in CFS; missing year prints `not extracted`, never 0 |
| Missing BS section | `<p>not extracted</p>` | Assignment step 11: Missing balance sheet renders `not extracted` |
| Substituted ratio badges | `SUBSTITUTED`, `It is not a measurement.` | Assignment step 10b: Contract for substituted ratio display |
| Empty applied NRI section | `No non-recurring item was applied.` | Assignment step 7: Required sentence when applied list is empty |
| Unadjusted reconciliation section | `No adjustment reached the income statement.` | Assignment step 8: Required sentence when no adjustments reached EBIT |
| Empty assumption sources table | not rendered | Finding 1: `/assumptions` with no files sets `{}` and suppresses table |
| Imbalanced BS metrics table row | `+50` | Hand arithmetic: `920.0 - 870.0 = +50.0` |
| Baseline implied share price | `$22.58` | Done-criterion 12: Regression check against baseline fixture in `tests/unit/test_routes.py` |

## What I did not do

- Did not edit `tests/unit/test_capm.py:473` or `analysis/capm.py` to suppress the pre-existing SciPy 1.17+ linregress error message mismatch, as both are out of scope.
- Did not edit implementation code in any directory (tester contract).

## Findings for the orchestrator

1. Pre-existing SciPy 1.17+ error message mismatch in `tests/unit/test_capm.py:473`: `assert "market_returns" in message` fails because `scipy.stats.linregress` raises `ValueError("Cannot calculate a linear regression if all x values are identical")`. Recommend updating `test_capm.py` or wrapping the exception in `analysis/capm.py`.
2. Reviewer finding F1 note: CapEx column header in `templates/_statements.html:446` reads `CapEx ($M, negative = outflow)` while `HistoricalFCFF.capital_expenditures` is stored as positive (`analysis/fcff.py:79` takes `abs()`). Consider updating the header to `CapEx ($M)` in a future polish unit.
