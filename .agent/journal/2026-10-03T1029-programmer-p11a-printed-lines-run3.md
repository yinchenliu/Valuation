---
agent: programmer
assignment: P11a-printed-lines
round: 1 (run 3; runs 1 and 2 were stopped, see Prior runs)
status: complete
files_touched: [ingestion/claude_extractor.py, ingestion/session_extraction.py, models/financial_statements.py, cli.py, templates/_statements.html, docs/2-rules/llm-boundary.md, docs/3-architecture/extraction.md, docs/3-architecture/data-contract.md]
verdict:
---

# P11a-printed-lines run 3: Pass 1 returns printed lines, Python does every sum

> Opened 2026-10-03 10:29, before the first command, at `631cf45` plus run 2's
> uncommitted diff. Completed 10:40. Nothing committed: the orchestrator commits.

## Prior runs

- Run 1 (`2026-10-02T2233-programmer-p11a-printed-lines.md`): stopped by the usage limit, no change.
- Run 2 (`2026-10-03T1010-programmer-p11a-printed-lines-run2.md`): a user interrupt
  stopped it at about 10:24. It left all eight files changed and uncommitted, and its
  entry is not edited here. **I took ownership of that whole diff** (`git diff 631cf45`).
  I read every file of it and re-ran every measurement below myself. Nothing here rests
  on run 2's `.out` files.

## What I did

Every Pass 1 money field, in each historical year and in the balance sheet, is now a
list of printed rows `{"label", "value", "page"}`. One typed function,
`claude_extractor.py:figure_from_printed_lines` (`:460`), adds a field's rows. It is the
only place a Pass 1 figure is formed, in both routes. `pass1_problems` (`:492`) runs
first in both routes. An absent key or a malformed line stops and names the field, the
year and the line index. `[]` reads as 0. The prompt no longer asks the model to add,
subtract, net or plug anything. "Adjust catch-alls to close any gap" is deleted.

The checks compare printed rows with Python's sums:
- gross profit, operating income and net income at 0.5%, with gross profit skipped and
  labelled when the filing prints none;
- the two new printed balance sheet totals against the mapped lines, at 1 in the
  filing's units (`BALANCE_CHECK_TOLERANCE`).

A failure is shown and the figures are kept. Route A's retry asks the model to read the
rows again, never to change a value so a check passes. Route B is format
`session-extraction-v2`, and a v1 file is refused by name. `BalanceSheet` carries
`printed_total_assets` and `printed_total_liabilities_and_equity` as `float | None`
memos. The CLI's 2% tolerance is gone. The CLI and the statements page show
printed / mapped / difference / `OK` or `FAIL`. `CACHE_FORMAT` is `p11a-printed-lines-v1`.

**Run 3's own code changes**, on top of run 2's diff:
1. **Route A's shape retry and check retry now send the PDF** (`pdf_bytes=pdf_bytes`).
   Before this they sent only the prompt and the previous JSON, which was unchanged
   since before P11a. Meanwhile the new retry prompt tells the model to "read the
   statement rows again from the filing". A model that cannot see the filing can only
   comply by making rows up, which rule 1 forbids. The JSON-syntax repair retry still
   sends no PDF, because it is syntactic.
2. **`BalanceSheet.printed_total_tolerance()`**, a static method returning
   `BALANCE_CHECK_TOLERANCE`. The template now prints the threshold the check applies
   (`bs.printed_total_tolerance()`) instead of a literal "1", which could drift from the
   check. I proved it by setting the constant to 5,000 in a scratch process: the header
   read "FAIL above 5,000" and the +4,124 row turned `OK` (`/tmp/p11a/r3_tol_probe.py`).
3. **Docs.** I wrote down the retry-with-PDF in `extraction.md` and `llm-boundary.md`.
   In `data-contract.md` I recorded that `[]` on a printed total reads 0 and fails the
   check (proved by execution, see the rule 3 table), and that the page reads the
   tolerance through `printed_total_tolerance()`. I replaced two stale locators in
   `extraction.md`'s known-defects table: "16 mypy errors" is now the measured 1, and
   `:795` is now `_run_nri_pass`.

## Done-criteria

Every command was run at 10:36-10:38 on the final tree, with `PYTHONPATH` set to the repo
for the scratch scripts that import `cli` / `app`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | no prompt sentence asks the model to compute | **pass** | `grep -n -i "sum of\|combine\|minus\|adjust catch" ingestion/claude_extractor.py` returns **0 lines**; it returned 10 at `631cf45` (`:171,172,181,184,246,251,253,255,261,264`). **No hit remains to explain.** I also ran a wider scan of the rendered Pass 1 prompt (`/tmp/p11a/r3_prompt1.txt`) for sum/plus/add/subtract/net/reconcile/equals/derive/calculate/compute/verify/adjust/plug/total/minus/combine. Every hit is one of two kinds. (a) A prohibition: "NEVER add, subtract or net rows", "never derive it", "never add it to any total", "Never list a printed total together with the rows it totals", "read, never derived". (b) The name of a printed row: "total net revenue / net sales", "PP&E net of accumulated depreciation", "Net cash provided by operating activities", "total stockholders equity", "only net interest", "Total assets". Sign rules ("POSITIVE", "Absolute value", "SIGNED") are the existing per-field sign rules, which the assignment keeps |
| 2 | the same JSON gives the same statements by both routes | **pass** | `.venv/bin/python /tmp/p11a/r3_equal.py` gives exit 0 and `ALL EQUAL`. This is run 2's adaptation of P9a's script; its stub now tells a retry prompt from a first-pass prompt by its opening words, because retries carry the PDF since this run. One filing (Walmart PDF, invented figures, failing B/S total 7,887 vs 7,882): statements equal, items equal, prompts equal (2 pairs), 4 calls of which 2 are retries. Three filings (Chipotle 2023-25, a deliberate +90 operating income error in 2022): statements, items and prompts (6 pairs) equal, 8 calls of which 2 are retries. `_call_llm` and `resolve_provider` are stubbed, so no API call is possible |
| 3 | Python's sums: Walmart 2026 capex 26,642 + 53 = 26,695 | **pass** | `/tmp/p11a/r3_crit3.py` gives `capex lines 2026: [('Payments for property and equipment', 26642, 23), ('Payments for business acquisitions, net of cash acquired', 53, 23)]`, `figure_from_printed_lines -> 26695.0` and `CashFlowStatement 2026 capital_expenditures: -26695.0`. The rows were read on PDF page 23 (`session_extraction text --pages 21-23`, saved to `/tmp/p11a/run3_pages21_23.txt`): "(26,642)" and "(53)", taken as absolute values per the capex sign rule. The same script parses the committed v1 `extractions/WMT.json` with the `cd7101d` parser: income statements equal, cash flows equal; only the two new memo totals differ (None in the old parse, 284,668 in the new) |
| 4 | a balance sheet that balances passes | **pass** | `session_extraction check /tmp/p11a/r3_wmt_v2.json` exits 0 with `2026 Total Assets 284,668 284,668 +0 OK` and `Total L + E 284,668 284,668 +0 OK`. The figures come from PDF page 22 and I added them by hand. Assets: 10,727 + 11,172 + 58,851 + 4,124 + 136,083 + 14,750 + 6,123 + 28,735 + 14,103 = 284,668. L+E: the 107,469 current lines (6,596 + 63,061 + 31,187 + 596 + 3,542 + 1,631 + 856), plus 34,624 + 13,941 + 5,905 + 16,549 + 293 (redeemable NCI, mezzanine) + 105,887 = 284,668 |
| 5 | a dropped row fails, is shown, and the figures are kept | **pass** | With "Prepaid expenses and other 4,124" removed (`r3_wmt_drop.json`), `check` exits 1: `Total Assets 284,668 280,544 +4,124 FAIL`, with the message naming the row sum and "the check allows 1". The CLI (`run_cli.py`, `_call_llm` stubbed, price data faked) prints `Total Assets printed 284,668 mapped 280,544 diff +4,124 FAIL` and **continues to `Equity Value: $ 95,469M`**, exit 0. That figure only shows the run continues; the prices are fake. Web (`run_route.py`): status 200, the row in red with `<strong>FAIL</strong>`. Route A (`r3_retry.py`, "dropped row every time"): 3 calls, then `[Pass 1 FAIL] Checks still fail after 2 retries. The figures are kept`, returning `other_current_assets=0` and `total_assets=280,544` |
| 6 | an absent key or bad line stops | **pass** | `/tmp/p11a/r3_crit6.py` runs 10 cases, each through route A (`parse_pass1`) and route B (`load_session_extraction`), and all 20 stop with `ValueError` (`Pass1ShapeError` in A). Examples: `year 2025: key 'sbc' is absent.`, `year 2026, 'capex': line 1: key 'page' is absent.`, `'value' must be a finite JSON number, got '26642'.` / `got nan.` / `got True.`, `'page' must be a positive integer ... got 0.`, `'label' must be ... non-empty`, `'revenue': must be a list of printed lines ... Got int 713163.`, `balance sheet 2026: key 'total_assets' is absent.`, `key 'pass1.latest_balance_sheet' is absent.` `[]` reads 0 (`rd_expense 2026 = 0.0`). Route A after retries (`r3_retry.py`): a malformed line or an absent key stops after 3 calls |
| 7 | a v1 session file stops | **pass** | `check` on `/tmp/p11a/r3_wmt_v1fmt.json` (the v2 file relabelled v1) **and** on a copy of the real `extractions/WMT.json` exits 2 with `format is 'session-extraction-v1', and this reader understands 'session-extraction-v2' only. The Pass 1 shape changed ... Extract the filing again in the new shape`. The CLI cache: `/tmp/p11a/r3_cache.py` writes a pickle under `p6-inputs-keyed-v1`, and `_load_cache` refuses it naming `p11a-printed-lines-v1` |
| 8 | the census falls | **pass: 114 → 67** | the grep at `rules.md:65` with `'--include=*.py'` quoted. At `631cf45` (exported to `/tmp/p11a/base`): 114, of which `claude_extractor.py` 49. Now 67, of which `claude_extractor.py` 2: `:885-886`, the Gemini token counts `getattr(..., 0) or 0`. Those are not figures and were outside this unit. Other files are unchanged (financial_statements 47, valuation 13, projector 3, routes_upload 1, routes_valuation 1) |
| 9 | the red list | **pass: 40 named below** | test gate `--ignore-glob="*_rule3_red.py"`: at `631cf45` **495 passed, 0 failed**; now **455 passed, 40 failed**. By set, from JUnit XML (`/tmp/p11a/r3_base_junit.xml`, `/tmp/p11a/r3_final_junit.xml`): the failing set equals the baseline-passing set minus the now-passing set; no test newly passes; no test exists in one run only. Full list with reasons under Measurements |
| 10 | lint and types | **pass** | ruff `Found 5 errors.`, the same five BLE001 as before, lines moved: `api/routes_valuation.py:445,703`, `cli.py:1143`, `ingestion/claude_extractor.py:1416`, `tests/test_e2e_all_googl.py:106`. mypy gate `Found 10 errors in 4 files (checked 20 source files)`, the same set as `631cf45` (`claude_extractor.py` content TypedDict, now `:808`; projector x4; routes_valuation x4; routes_upload:28) |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Send the PDF with the shape retry and the check retry | The assignment's step 3 says "the retry prompt asks the model to read the rows again". Without the document that request cannot be met, and the only way to "comply" is to make a row up: rule 1 | Leaving it out keeps token cost down but makes the retry a request to fabricate. The JSON repair retry stays without the PDF, because fixing syntax needs no reading |
| `[]` on `total_assets` / `total_liabilities_and_equity` reads 0 (FAIL), not `None` | The assignment: "An empty list says the filing prints no such row. Python reads it as 0." Only `gross_profit` is given a skip | Mapping `[]` to `None` would print "not extracted", but it would add a special case the assignment did not ask for. Both forms fail the check. Recorded in `data-contract.md` |
| Expose the tolerance to the page via `BalanceSheet.printed_total_tolerance()` | Rule 6: the threshold shown must be the one applied; a literal "1" in the template could drift from it | A Jinja global needs a change in `api/` (out of scope). A `ClassVar` would have worked too, but needed a new typing import in a dataclass module |
| Keep run 2's `Pass1ShapeError(ValueError)` carrying `problems` | Route A sends every problem back in one retry, route B lists them all in one `check`, and every existing `except ValueError` still catches it | A plain `ValueError` would force callers to parse its message |
| Keep `BALANCE_CHECK_TOLERANCE = 1.0` in `models/` | The assignment fixes it ("exceeds 1 in the filing's units"). It sets a status, never a figure, and all three outputs print it | n/a |
| Route equality script: tell retries apart by prompt prefix | Retries now carry the PDF, so "has `pdf_bytes`" no longer means "first pass" | Without this, `sent == printed` fails on a test-harness artefact, not on a route difference |

No change in this run was made to reach a target number.

## Rule 3: what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| any `historical_years[i]` line field (18 of them) | stops, naming the year and the key | `pass1_problems` → `_line_field_problems` `claude_extractor.py:476-489`; `r3_crit6.py` "absent key sbc, 2025" in both routes |
| any `latest_balance_sheet` line field (21, including the 2 totals and the 2 NCI memos) | stops, naming the balance sheet year and the key | same; `r3_crit6.py` "B/S total_assets absent" |
| a line's `label` / `value` / `page` | stops, naming the field, the year and the line index | `printed_line_problems` `:420`; `r3_crit6.py` (no page, string value, NaN, bool, empty label, page 0) |
| a field given as a bare number (the v1 shape) | stops: "must be a list of printed lines" | `r3_crit6.py` "revenue a bare number" |
| `historical_years` / `latest_balance_sheet` | stops | `pass1_problems` `:492-547`; "latest_balance_sheet absent" case |
| `year` in a year entry or the balance sheet | stops | `pass1_problems` |
| `[]` for a field | **reads as 0**, by the assignment's definition ("the filing prints no such row"). Not a default: it is present | `figure_from_printed_lines` `:460` (`math.fsum` of nothing); `[empty list] rd_expense 2026 = 0.0` |
| `[]` for `gross_profit` | the check is **skipped and says so** (`SKIP: the filing prints no gross profit row`) | `gross_profit_printed=len(...) > 0` `:955`; check output above |
| `[]` for a printed total | reads 0, and the check **FAILs** by the whole mapped sum | scratch run: `Total Assets 0 284,668 -284,668 FAIL` |
| `printed_total_assets` / `..._liabilities_and_equity` on `BalanceSheet` | `None` = "not extracted". The check says `not extracted`, which counts as a failure in the parser's error list. Never a zero default | `models/financial_statements.py:211-212,253`. The parser is the only producer (`grep "BalanceSheet("` → `claude_extractor.py:1014` only) and always sets them |
| session `format` v1 | stops, naming both formats | `session_extraction.py:224` |
| CLI cache under the old marker | stops (refused, not overwritten) | `cli.py:224`, `r3_cache.py` |
| `pass1.get("historical_years")` / `.get("latest_balance_sheet")` in `session_extraction.py:432,449` | no default value: `None` fails the `isinstance` test, and the absence itself is reported by `pass1_problems` above | `r3_crit6.py` "latest_balance_sheet absent" (route B line) |
| **`ticker=ticker or data.get("ticker", "")`** `claude_extractor.py:1043` | **defaults to `""`**. Pre-existing and unchanged; both callers pass the ticker. Not a figure | finding against the file, not introduced here |
| **`acquisitions=0.0` and the other financing/investing fields of `CashFlowStatement`, plus `current_portion_lt_debt=0.0`** `:992-1001,1027` | **set to 0.0 without a read**. Pre-existing and unchanged. Acquisitions are folded into `capex`, and the current portion into `short_term_debt`, by the prompt's definitions; the rest are not extracted at all | backlog item 1, outside the Pass 1 line reading. Listed so the reviewer sees it |

## Measurements

### Gates, `631cf45` (a `git archive` export in `/tmp/p11a/base`, with `10K_filings`, `extractions` and `.env` symlinked) against the final tree

| Gate | `631cf45` | final tree |
|---|---|---|
| tests `--ignore-glob="*_rule3_red.py"` | 495 passed, 0 failed | 455 passed, 40 failed |
| ruff | 5 (BLE001) | 5 (the same BLE001 set) |
| mypy gate | 10 errors in 4 files | 10 errors in 4 files, the same set |
| census | 114 | 67 |
| `GET /` | — | 200 |

### The red list: 40 tests, by name and reason

Every one of them builds Pass 1 in the old one-number-per-field shape, or a
`session-extraction-v1` file, or asserts the old key list. The tester rewrites the
fixtures. **None fails on a figure.** The count is A 19 + B 11 + C 10 = 40;
`/tmp/p11a/r3_final_junit.xml` is the authority.

**A. `tests/unit/test_claude_extractor.py`: 19.** Each builds Pass 1 JSON with a bare
number per field, so `parse_pass1` raises `Pass1ShapeError` ("'revenue': must be a list
of printed lines ..."). With a balance sheet that is 38 problems, without one 18.
- `test_pass1_income_statement_fields_land_on_their_fields`
- `test_pass1_ticker_and_name_come_from_the_caller`
- `test_pass1_ebit_equals_the_stated_operating_income`, all 3 parametrisations: `[D&A inside other_operating_expense-overrides0]`, `[D&A inside cost_of_revenue-overrides1]`, `[no D&A reported-overrides2]`
- `test_pass1_cash_from_operations_equals_the_stated_cfo`
- `test_pass1_capex_is_stored_negative`
- `test_pass1_balance_sheet_fields_land_on_their_fields`
- `test_pass1_an_absent_nci_key_is_none_never_zero`, both parametrisations: `[noncontrolling_interest_nonredeemable]`, `[noncontrolling_interest_redeemable]`. Its premise has also changed: an absent NCI key now **stops** rather than giving `None`
- `test_pass1_a_null_nci_key_is_none_never_zero`, both parametrisations: `[noncontrolling_interest_nonredeemable]`, `[noncontrolling_interest_redeemable]`. A null key now stops ("must be a list")
- `test_pass1_explicit_zero_nci_is_kept_as_zero` (an explicit 0 is now `[]`)
- `test_pass1_without_a_balance_sheet_gives_none`
- `test_pass1_years_are_returned_ascending`
- `test_pass1_arithmetic_check_is_clean_when_everything_reconciles`
- `test_pass1_arithmetic_check_names_year_and_field_on_a_gross_profit_miss`
- `test_pass1_gross_profit_tolerance_is_half_a_percent`, both parametrisations: `[602-False]`, `[604-True]`

**B. `tests/unit/test_routes_session.py`: 11.** Nine write a `session-extraction-v1`
file, which is now refused by name, so the page shows the v1 message instead of the
label or error under test. Two run route A over old-shape stubbed Pass 1 JSON and get
`Pass1ShapeError` (56 problems).
- `test_upload_then_follow_the_redirect_reaches_the_assumptions_page_with_the_label`: v1 refused
- `test_assumptions_from_a_session_file_shows_the_label_and_the_files_identity`: v1 refused
- `test_assumptions_with_a_ticker_that_differs_from_the_file_stops_naming_both`: v1 refused before the ticker comparison
- `test_assumptions_with_a_company_name_that_differs_from_the_file_stops_naming_both`: same
- `test_valuation_with_a_ticker_that_differs_from_the_file_stops_before_pricing`: same
- `test_valuation_on_a_cache_hit_shows_the_session_label`: v1 refused
- `test_valuation_on_a_cache_miss_shows_the_session_label`: v1 refused
- `test_a_session_file_missing_one_pass1_key_renders_the_loaders_message`: v1 refused before the key check ("year 2024" not in the message)
- `test_a_bad_session_file_uploaded_through_the_form_reaches_the_page_named`: v1 refused before the `'sbc'` key check
- `test_route_a_label_survives_removing_the_key_on_a_cache_hit`: old-shape Pass 1 → `Pass1ShapeError`
- `test_route_a_on_a_cache_miss_with_no_key_stops_on_the_credential`: old-shape Pass 1 → `Pass1ShapeError`

**C. `tests/unit/test_session_extraction.py`: 10.** These fixtures use `SESSION_FORMAT`
(now v2) but put old-shape numbers in `pass1`, so the loader reports "must be a list of
printed lines" for every field, except `test_the_required_key_lists_are_the_schema`.
- `test_one_filing_both_routes_give_equal_statements_and_items`: loader stops, 56 problems
- `test_three_filings_both_routes_give_equal_statements_and_items`: loader stops, 110 problems
- `test_a_changed_figure_makes_the_routes_differ`: route A `Pass1ShapeError`
- `test_the_required_key_lists_are_the_schema`: asserts the old literal tuple; the balance sheet tuple now has 2 more keys, `total_assets` and `total_liabilities_and_equity`
- `test_explicit_zero_is_accepted`: an explicit `0` is now `[]`; the loader stops
- `test_pass2_item_amount_zero_loads`: the old-shape `pass1` stops the loader first
- `test_session_label_names_the_session_route_and_the_declared_model`: same
- `test_check_exit_codes`: `cmd_check` returns 2, not 0, on an old-shape `pass1`
- `test_prompt_prints_route_a_prompts`: `prompt --pass 2` needs a valid Pass 1 first, and it is old-shape
- `test_main_check_and_a_bad_page_range`: `main(['check', ...])` returns 2, not 0, same reason

### Size of the new answer against route A's output ceiling

The three-year Walmart Pass 1 in the new shape is 7,906 characters compact and 12,864
indented, about 2-3.2k tokens, against `_call_claude`'s `max_tokens=8096`. That fits for
Walmart. A filing with many more rows, or more years per filing, would come closer. If
it hits the ceiling, the existing stop on `stop_reason == "max_tokens"` fires loudly.
Nothing truncates silently.

### Scratch files (all under `/tmp/p11a/`, prefix `r3_` for this run)

`r3_wmt_v2.json` (`build_wmt.py`, byte-identical to run 2's), `r3_wmt_drop.json`,
`r3_wmt_v1fmt.json`, `r3_real_v1_copy.json`, `r3_equal.py/.out`, `r3_crit3.py/.out`,
`r3_crit6.py/.out`, `r3_retry.py/.out`, `r3_cache.py`, `r3_tol_probe.py`,
`r3_prompt1.txt`, `run3_pages21_23.txt`, `r3_base_junit.xml`, `r3_final_junit.xml`,
`*.check.out`, `*.cli.out`, `*.route.out`.

## What I did not do

- `tests/`: out of scope. 40 fixtures need the new shape (list above).
- `extractions/WMT.json`: still v1 and now refused. The orchestrator re-extracts it.
- `.claude/skills/extract-filing/SKILL.md`: still describes the v1 shape. The orchestrator updates it.
- Backlog items 1 (outside the Pass 1 line reading), 10 (the D&A subtraction stays, now
  on summed figures), 44 and the other listed items: untouched.
- Nothing was committed.

## Findings for the orchestrator

1. **Route A's retries cost more now.** Shape and check retries send the PDF again, at
   up to 2 extra full-document calls per filing when checks fail. That is the price of
   asking for a re-read; earlier retries were cheaper because they could not re-read.
2. **Dead `WARN` branch in the income statement check** (`claude_extractor.py`
   `_validate_extracted_data`, pre-existing): `elif diff_pct > 0.5: status = "WARN"`
   can never fire while `fail_pct` is 0.5. Either the 0.5% threshold is meant to have
   a WARN band below it or the branch should go. The 0.5% figure is also not printed in
   the check table (the 1-unit balance sheet tolerance is). That is a rule 6 gap for a
   status, not a figure.
3. **`_run_nri_pass`'s `except Exception: return []`** (`claude_extractor.py:1416`,
   item 8) turns a Pass 2 parse failure after the retry into "no non-recurring items",
   which reads as a measurement. That is rule 3, and it is worse than the BLE001 lint
   label suggests.
4. **`ticker or data.get("ticker", "")`** (`:1043`) and the `0.0` cash flow
   financing/investing fields (`:992-1001`) remain from item 1. Not figures the model
   read, but zeros that look like measurements in `CashFlowStatement`.
5. The `SKILL.md` for route B must teach the v2 line shape, including "never list a
   printed total together with the rows it totals". Otherwise the first re-extraction
   of Walmart may double-count `Total current assets`.
