---
agent: tester
assignment: P9c-parse-tests
round: 1
status: complete
files_touched: [tests/unit/test_claude_extractor.py, tests/unit/test_session_extraction.py, tests/unit/test_filings.py, tests/unit/test_session_extraction_rule3_red.py]
verdict: fail
---

# P9c-parse-tests — tests for the parse layer both extraction routes share

Started 2026-10-02T1658 at `d97855b` (code under test accepted at `ad52e1a`), macOS,
`.venv/bin/python`. Scratch work is under `/tmp/p9c/`. `COVERAGE_FILE` was set under
`/tmp/p9c/` for every run. `P9b-session-web` ran in parallel and had uncommitted changes
in `api/`, `templates/` and `docs/3-architecture/entry-points.md` during my gate runs.
The gate's failure set did not move.

**What the verdict means.** All five done-criteria pass. The verdict is `fail` because
the tester contract says a stop path that defaults or loads, rather than raising, is a
`fail`. There are three, and **every one was already known**:
- F1 of the P9a review, twice: a non-list `non_recurring_items`, and a `NaN` amount. Both
  are now red tests, and `P9d` is assigned to fix them.
- backlog item 1: route A's `parse_pass1` reads an absent key as 0.

The tests are complete. No new programmer work is needed beyond `P9d` and item 1.

## What I did

I wrote four test files for the code that route A and route B now share:
`parse_pass1`, `parse_pass2`, `plan_filings` and `merge_filing_extractions`. They also
cover the session loader, route equality, the route label, and filing hashing.

- Every Pass 1 input is a round number. Each expected value is either the input itself
  or one line of arithmetic, written beside it.
- The route-equality test sends the same JSON through `extract_multi_year` and through
  a session file. On the route A side, `_call_llm` is replaced by a stub that answers
  only the exact `(system prompt, user prompt, PDF bytes)` triples built from
  `pass1_prompts` and `pass2_prompts`, and raises on anything else. So the same run also
  proves the two routes send the same prompts.
- `resolve_provider` is stubbed as well, so no test depends on `.env`. Each test file
  has an autouse fixture that makes `_call_llm` raise, so no test can reach the API.
- The PDFs are a few bytes written under `tmp_path`. Nothing reads `10K_filings/`.
- I wrote the two F1 requirements red, in `tests/unit/test_session_extraction_rule3_red.py`.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the seven groups exist, ≥ 1 test each | **pass** | `.venv/bin/python -m pytest --collect-only -q tests/unit/test_claude_extractor.py tests/unit/test_session_extraction.py tests/unit/test_filings.py tests/unit/test_session_extraction_rule3_red.py` → `159 tests collected`. By group: **(1)** `parse_pass1`: 11 cases (`test_pass1_*`). **(2)** `parse_pass2`: 6. **(3)** `plan_filings`: 3. **(4)** merge: 2. **(5)** routes equal: 2, plus 1 negative control. **(6)** loader stops: 107 cases in the gate (see the Rule 3 table), 1 explicit-zero case and 3 red. **(7)** label: 1. Also 6 subcommand cases, and 6 in `test_filings.py` |
| 2 | every expected value has a written source | **pass** | A comment sits beside or above every assertion. The table below lists each source. Nothing came from the code's output |
| 3 | the gate | **pass** | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` → `1 failed, 353 passed`. The failure set is `{tests/unit/test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}`, the same as the baseline (`1 failed, 197 passed`). 353 = 197 + 156 new. Full `pytest -q` → `6 failed, 353 passed`: the CAPM test, the 2 older red tests, and my 3 red tests |
| 4 | coverage of the new and moved code, measured | **pass** (measured) | `COVERAGE_FILE=/tmp/p9c/... .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py" --cov=ingestion --cov-branch --cov-report=term-missing`. See Measurements |
| 5 | at least two tests can fail | **pass** | Six mutations, each made in a copy under `/tmp/p9c/mut_*` by `/tmp/p9c/mutate.sh`. Output pasted below |

### Criterion 5 — the mutations, pasted

```
== M1 capex sign    (claude_extractor.py: capital_expenditures=-capex  ->  =capex)
FAILED tests/unit/test_claude_extractor.py::test_pass1_capex_is_stored_negative
1 failed, 149 passed
== M2 merge preference    (if y not in all_income or y == fiscal_year:  ->  if y not in all_income:)
FAILED tests/unit/test_claude_extractor.py::test_merge_prefers_the_filing_whose_fiscal_year_is_the_statement_year
1 failed, 149 passed
== M3 route B reorders items    (session_extraction.py: non_recurring=list(reversed(merged_items)))
FAILED tests/unit/test_session_extraction.py::test_one_filing_both_routes_give_equal_statements_and_items
FAILED tests/unit/test_session_extraction.py::test_three_filings_both_routes_give_equal_statements_and_items
2 failed, 148 passed
== M4 only the first 10 year keys checked    (for key in PASS1_YEAR_FIELDS[:10]:)
FAILED ...test_stop_year_key_absent[interest_income] ... [change_in_working_capital]   (9 cases)
FAILED ...test_every_problem_is_listed_in_one_stop
FAILED ...test_check_exit_codes
11 failed, 139 passed
== M5 parser stops subtracting D&A    (other_operating_expense=float(yr.get(...)) without "- D&A")
FAILED ...test_pass1_ebit_equals_the_stated_operating_income[D&A inside other_operating_expense]
FAILED ...test_pass1_ebit_equals_the_stated_operating_income[D&A inside cost_of_revenue]
2 failed, 148 passed
== M6 no confidence stop    (if "confidence" not in item:  ->  if False:)
FAILED tests/unit/test_claude_extractor.py::test_pass2_item_without_confidence_stops_naming_year_and_description
FAILED tests/unit/test_session_extraction.py::test_stop_pass2_item_key_absent[confidence]
2 failed, 148 passed
```

(These were run before I added the 6 `test_stop_pass2_item_other_key_absent` cases.
That is why each total is 150, not 156.)

- **M5 shows that the EBIT identity is a real lock.** The "no D&A reported" case stays
  green, because 0 subtracted changes nothing. Item 10's fix is safe to make as long as
  it keeps EBIT equal to the stated figure.
- **M4 shows that the loader is the only guard.** With the check removed, an absent key
  loads as 0 through route A's parser (backlog item 1).

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| I assert `IncomeStatement.ebit == 300` and never the parsed `other_operating_expense` or `IncomeStatement.depreciation_amortization` | assignment §1. Backlog item 10 will move the D&A subtraction | Locking either line would make item 10's fix go red. M5 proves the identity still catches the defect it is meant to catch |
| I do not assert the parser's hard-coded `0.0` lines (`acquisitions`, the financing lines, `current_portion_lt_debt`) | strategy §2, "never assert a fallback" | Asserting those zeros would lock defaults |
| I stub `resolve_provider` as well as `_call_llm` in the route A tests | `config.py:15` loads `.env` with `override=True` (backlog 46) | Setting env vars would let the result depend on `.env`, and a Foundry `.env` would import `azure.identity` |
| The `_call_llm` stub answers only the exact prompt triples built from `pass1_prompts`/`pass2_prompts` | P9a criterion 3 asked for proof that the prompt sent equals the prompt printed | One run proves both result equality and prompt equality. A retry call (pdf_bytes `None`) raises, so a hidden retry cannot pass |
| Each stop test checks that **one line** of the message names the file, the filing index, the PDF and the year/key (`assert_one_line_names`) | P9a step 10: "names the file, the filing index and its PDF name, and … the year and the key" | The loader collects problems into a multi-line message. A key and a year named on different lines would not tell the reader which year the key belongs to |
| `YEAR_KEYS` / `BALANCE_SHEET_KEYS` are written by hand from the schema and compared with `PASS1_*_FIELDS` | assignment §6. A test that loops over the code's own tuple shrinks silently when a key is dropped | A dropped key now fails `test_the_required_key_lists_are_the_schema` |
| I added 41 shape-stop rows beyond P9a's 7-row stop list | tester contract: "for every input the unit reads, write a second test: remove the input" | These are the other values the loader reads: identity, plan keys, hash, locator, container types |
| The red file uses two non-list shapes (`{"a": 1}` and a string) and not an `int` | measured: an `int` raises `TypeError`, which the loader already wraps in a `ValueError` | An `int` case would pass today, so it states no unmet requirement |
| `test_filings.py` does **not** assert the year `discover_filings` infers from a filename | backlog item 43 | A test locking the filename inference would go red when the fix reads the year from the filing |
| I did not assert `parse_pdf_args`' `(0, path)` for a bare path | P9a review F3: 0 is a sentinel in a data format | Locking a sentinel that the review suggested replacing with `null` |
| `text` and `locate` are not tested | assignment "Out of scope": they need a real PDF, and `10K_filings/` is not in git | Recorded as a coverage gap |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| session file absent / not JSON / not an object | stops, names the file | `test_stop_session_file_absent`, `_not_json`, `_not_an_object` |
| `format` (absent, wrong, null) | stops, names the file and `format` | `test_stop_wrong_format[*]`, `test_stop_absent_format` |
| `ticker`, `company_name`, `extracted_by` (absent or wrong type) | stops, names file and key | `test_stop_on_a_missing_or_malformed_value[ticker absent … extracted_by not an object]` |
| `extracted_by.model` (absent, null, `""`, blank) | stops, names file and `extracted_by.model` | `test_stop_model_empty[*]`, `test_stop_model_absent`. Collected with the Pass 1 problems, not ahead of them: `test_every_problem_is_listed_in_one_stop` |
| `filings` (absent, empty), a filing not an object | stops | shape rows |
| `fiscal_year`, `pdf_path`, `target_years`, `include_bs` (absent, wrong type, 0 among several, edited by hand, out of plan order) | stops, names file, `filings[i]`, the PDF and the key | shape rows, `test_stop_target_years_edited_by_hand`, `test_stop_filings_out_of_plan_order` |
| the PDF (missing, one byte appended) | stops, names file, `filings[i]`, the PDF | `test_stop_pdf_missing`, `test_stop_pdf_changed` |
| `pdf_sha256`, `size_bytes` (absent, wrong type) | stops | shape rows |
| `pass1` / `pass2` (key absent, null, not an object) | stops, names file, `filings[i]`, the PDF and the pass | `test_stop_pass_is_null[*]`, shape rows |
| `pages_read`, `.pass1`, `.pass2` (absent, not an object, page 0, empty) | stops | shape rows |
| each of the 18 non-`year` year keys | stops, names file, `filings[0]`, the PDF, `year 2023` and the key | `test_stop_year_key_absent[*]` (18 cases) |
| `year` in a year entry (absent, not an int) | stops, names `historical_years[i]` and `'year'` | `test_stop_year_key_year_absent`, shape row |
| a year key as null, `"12"`, `true`, NaN, Infinity | stops, names the year and the key | `test_stop_year_key_not_a_finite_number[*]` |
| a year given twice; pass1 years ≠ planned `target_years` | stops | shape row; `test_stop_pass1_years_differ_from_the_plan` |
| each of the 16 non-`year` balance sheet keys, when `include_bs` | stops, names `balance sheet 2024` and the key | `test_stop_balance_sheet_key_absent[*]` (16 cases) |
| `latest_balance_sheet` (absent, not an object, empty when planned, no year, year 0, non-number figure, present when not planned) | stops | `test_stop_balance_sheet_planned_*`, `_where_the_plan_has_none`, shape rows |
| an explicit `0` for a schema key | **accepted**, value 0.0 | `test_explicit_zero_is_accepted` |
| Pass 2 `non_recurring_items` absent | stops: "not a Pass 2 answer" | `test_pass2_absent_key_stops_saying_it_was_not_a_pass2_answer` |
| Pass 2 item `confidence`, `source` absent | stops, names year and description (route A and via the loader) | `test_pass2_item_without_*`, `test_stop_pass2_item_key_absent[*]` |
| Pass 2 item `year`, `description`, `amount`, `line_item`, `direction`, `category` absent | stops, names file, filing, PDF and key. **Does not name the item's year or description** | `test_stop_pass2_item_other_key_absent[*]`. Finding 2 |
| Pass 2 `non_recurring_items` not a list | **does not stop with `ValueError`.** It escapes as `AttributeError` | **red**: `test_pass2_items_not_a_list_*`. `ingestion/session_extraction.py:497` catches only `ValueError, KeyError, TypeError`. The `AttributeError` is raised at `ingestion/claude_extractor.py:768` |
| Pass 2 item `amount` NaN | **loads** | **red**: `test_pass2_item_amount_nan_*`. `ingestion/session_extraction.py:489-500` has no finite-number check on Pass 2. `claude_extractor.py:787` does `float(item["amount"])` |
| route A `parse_pass1`: any absent Pass 1 key | **defaults to 0** | `ingestion/claude_extractor.py:650-711` (`.get(field, 0)`), and the arithmetic check at `:347-358`. Backlog item 1, out of this unit's scope. I did not assert it (doing so would lock a default). Route B guards it, as M4 shows |
| route A `parse_pass1`: absent `latest_balance_sheet` | gives no balance sheet (an empty list, not zeros) | `test_pass1_without_a_balance_sheet_gives_none`. The `{}` the prompt asks for is the input here |

## Measurements

**Gate, before and after, as failure sets.**

| | Command | Result |
|---|---|---|
| before (`d97855b`) | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | `1 failed, 197 passed`. Set: {`test_capm.py::test_beta_stops_when_the_market_series_has_no_variation`} |
| after | same | `1 failed, 353 passed`. **The same set** |
| after, full | `.venv/bin/python -m pytest -q` | `6 failed, 353 passed`. Set: CAPM, `test_dcf_rule3_red`, `test_projector_rule3_red`, and my 3 `test_session_extraction_rule3_red` cases |
| lint | `.venv/bin/python -m ruff check .` | `Found 5 errors.` (unchanged). The four new files: `All checks passed!` |
| types | not run | tests are outside the mypy gate's paths, and I changed no code |

**Coverage of `ingestion/`** (`--cov=ingestion --cov-branch`, gate form):

| File | Before (statements) | After: statements | After: branches |
|---|---|---|---|
| `claude_extractor.py` | 96/438 (22%, import only) | 304/438 | 148 branches, 19 partially covered (66% combined) |
| `filings.py` | 0/65 | 46/65 | 28 branches, 5 partially covered (68% combined) |
| `session_extraction.py` | 0/474 | 401/474 | 220 branches, 8 partially covered (84% combined) |

**Coverage of the code this unit is about**, per function (coverage JSON
`/tmp/p9c/cov.json`, `functions` key):

- **The four shared functions and what they call: 13 of 13 functions at 100% of
  statements and branches.** They are `plan_filings`, `_plan_target_years`,
  `merge_filing_extractions`, `pass1_prompts`, `pass2_prompts`, `parse_pass1`,
  `parse_pass2`, `_parse_financials_response`, `_parse_nri_response`,
  `_pass1_prompt_pair`, `_pass2_prompt_pair`, `_build_financials_prompt` and
  `_build_nri_prompt`.
- `_validate_extracted_data`: 36/38 statements, 8/10 branches.
  - `:375` is not reached: both a stated and a derived figure of 0.
  - `:387` is **dead code**: the `WARN` branch tests `diff_pct > 0.5` right after the
    `FAIL` branch tests `diff_pct > fail_pct`, and `fail_pct` defaults to 0.5 at every
    caller. See the findings.
- `_build_is_summary`: 8/8 statements, 3/4 branches. Not covered: a target year with no
  income statement.
- Route A runners: `_run_financials_pass` 14/41 and `_run_nri_pass` 15/28. Their retry
  paths are not exercised. A retry is a second model call, and the stub refuses those
  on purpose.
- `session_extraction.py`: **24 of 29 functions touched**, 337/409 statements, 179/218
  branches.
  - Untouched: `_open_verified_pdf`, `_page_texts`, `_page_count`, `_matches` and
    `cmd_locate`, all of which need a real PDF text layer. Out of scope.
  - Partial: `cmd_text` (1/11, same reason), `_print_pass1_tables` (8/14), `main`
    (12/14) and `cmd_plan` (20/21).
- `filings.py`: 3 of 3 functions touched, 31/50 statements, 17/28 branches. The
  year-inference body of `discover_filings` is untested on purpose (item 43).

## Expected values — testers only

**Accuracy: 156 of 156 gate test cases pass, and 3 of 3 red cases fail for the reason
stated.** Statically, the four files hold:
- 127 `assert` statements in the gate files;
- 10 `pytest.raises` in the gate files, plus 2 in the red file;
- 27 calls to `assert_one_line_names`, the multi-part message check: 25 in the gate files and 2 in the red file.

Every one of them matches its expected value.

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| I/S fields (`revenue` … `diluted_shares_outstanding`) | 1000, 400, 150, 100, 20, 10, −5, 57, 48 | the JSON input, unchanged. All values distinct, so a swap is caught |
| `gross_profit` | 600 | hand: 1000 − 400 |
| `ebit`, in 3 placements of D&A | 300 | identity: stated operating income, which reconciles. Hand: 1000−400−150−100−50; 1000−430−150−100−20; 1000−400−150−100−50 |
| `cash_from_operations` | 290 | identity: the parser builds a residual so that CFO equals the JSON `cfo` (assignment §1) |
| CFS named lines | 228, 30, 25, −15 | the JSON input |
| `other_operating_activities` | 22 | hand: 290 − 228 − 30 − 25 − (−15) |
| `capital_expenditures` | −70 | `docs/4-conventions/units-and-signs.md` row `capital_expenditures`: "negative (a cash outflow)". JSON 70 |
| 16 balance sheet fields | 100 … 285 | the JSON input. `cash` → `cash_and_equivalents` |
| `balance_check_difference` | 0 | hand: assets 860 = liabilities 575 + equity 285 |
| no B/S when `{}` | `[]` | the prompt's `{}` for "skip the balance sheet" |
| years ascending | [2023, 2024] | `FinancialStatements.years` docstring "sorted ascending" |
| arithmetic check clean | `[]` | hand: 600, 300, 228 all reconcile |
| gross profit miss names year and field | "2024", "Gross Profit" | hand: 10/610 = 1.64% > 0.5% |
| tolerance boundary | 602 passes, 604 fails | hand: 2/602 = 0.33%; 4/604 = 0.66% |
| `parse_pass2` empty | `[]` | the prompt text: return `{"non_recurring_items": []}` when none |
| `parse_pass2` item | the input `NonRecurringItem` | the JSON input |
| the three Pass 2 stops, and `""` accepted | `ValueError`; "not a Pass 2 answer"; "year 2024", "Plant closure"; `source == ""` | assignment §2 and the `_parse_nri_response` docstring |
| `plan_filings` one / three out of order / empty | the four fields of each `FilingPlan`; `ValueError` | `docs/3-architecture/extraction.md` routing table; P9a step 2 |
| merge per year | {2022: 1, 2023: 2, 2024: 7} | the rule in P9a step 3, applied by hand in the test's comment: primary seen first kept, primary seen second overwrites, neither → first seen |
| merge dedupe | [first, opposite, other] | the rule "(year, amount, direction), first seen kept", applied by hand: 4 in, 3 out |
| routes equal, 1 and 3 filings | `fin_B == fin_A`, `items_B == items_A` | identity: same JSON in |
| calls made | 2, 6 | hand: 2 passes × filings, with no retry |
| merged years / B/S / item order / revenues | [2020..2024]; [2024]; A, B, C, D; 1000·k | hand, in the comment above `three_filings` |
| negative control | `!=` | one `sbc` changed 50 → 51 in route B only |
| every stop | `ValueError`, and one line naming the file, `filings[i]`, the PDF, the year/key | P9a step 10's stop list and naming requirement |
| key lists | the 19 and 17 keys | the schema in `claude_extractor.py:167-208`, written out by hand |
| explicit zero | 0.0 | the explicit input 0 |
| label | `claude`, model, `claude-code-session` ×2, the file path, "no API call", "Claude Code session" | P9a step 11 |
| `check` exit codes | 0 / 1 / 2 | P9a step 9. The arithmetic case: 100/1300 = 7.7% |
| `plan` skeleton | the routing table, `TST`, nulls, the sha256 | routing table; hashlib over the same bytes |
| `prompt` | the strings `pass1_prompts`/`pass2_prompts` return | identity: P9a step 5 says they are the one source |
| `_compress` | "1-3, 7", "none", "4", "1, 3-4" | its docstring for the first two; hand for the rest |
| `fingerprint_filings` | `hashlib.sha256(content)`, 18 bytes, order [2023, 2025] | hashlib and len() computed independently; the docstring "stable order" |
| `parse_pdf_args` YEAR:PATH | [(2024, …), (2023, …)] | its docstring |

## What I did not do

- **`locate`, `text` and the PDF helpers.** They need a real PDF, and `10K_filings/` is
  not in git (assignment "Out of scope"). That is 5 functions untouched and `cmd_text`
  at 1/11.
- **Route A's retry loops** (`_run_financials_pass` `:948-1000`, `_run_nri_pass`
  `:1039-1053`). Each retry is a second model call. The stub refuses it, by the
  assignment's "raise if called with anything it was not given".
- **The fiscal year `discover_filings` infers** (backlog item 43), and the `(0, path)`
  sentinel (review F3). Neither is asserted, so neither is locked.
- `tests/unit/test_capm.py:473`: held by the user.
- No code was edited. Only the four test files and this entry were written.

## Findings for the orchestrator

1. **The two F1 requirements are red, as assigned**, in
   `tests/unit/test_session_extraction_rule3_red.py`. There are three cases. **When
   `P9d` lands, its tester must move them into `test_session_extraction.py` and delete
   the red file** (backlog item 24).
2. **A Pass 2 item missing `year`, `description`, `amount`, `line_item`, `direction` or
   `category` stops, but the message does not name the item.** Route A's parser reads
   these with `item[key]` (`claude_extractor.py:785-790`), so the `KeyError` names the
   key and nothing else. The loader's wrapper adds the file and the filing. The
   `confidence` and `source` stops name the year and the description; these six do
   not. Fix it in the loader: P9d's Pass 2 shape check could name the item index there.
   I locked only the parts that exist today (file, filing, PDF, key), so adding the item
   to the message will not turn any test red.
3. **Dead `WARN` branch in `_validate_extracted_data`.** At `claude_extractor.py:386-387`,
   `elif diff_pct > 0.5` follows `if diff_pct > fail_pct`, and `fail_pct` is 0.5 at
   every caller, so `WARN` is never printed. Severity is `note`: it changes no figure.
   It belongs with backlog item 12 (dead code).
4. **Route A returns `[]` when Pass 2 parsing fails twice** (`claude_extractor.py:1049-1053`,
   `except Exception … returning empty list`). The `_parse_nri_response` docstring
   says "nothing was read" and "found none" must not collapse into one another. This
   branch collapses them on the API route. It sits inside backlog item 8's
   `except Exception`. Item 8's row should name the rule 3 consequence, not only the
   lint error. Route B has no such path.
5. A Pass 2 `amount` given as the string `"12"` is converted by `float()` and loads
   (route A's parser, `:787`). Measured: `parse_pass2` on `"amount": "12"` gives `12.0` (`/tmp/p9c/amount_str.py`). Pass 1 rejects strings (`_is_number`). That makes it the
   same shape as F1. `P9d`'s finite-number check should reject non-numbers as well as
   NaN.

.agent/journal/2026-10-02T1658-tester-p9c-parse-tests.md
