---
agent: programmer
assignment: P3b-pipeline-stops
round: 1
status: complete
files_touched: [ingestion/filings.py, ingestion/claude_extractor.py, cli.py, api/routes_valuation.py, pipeline.py]
---

# P3b-pipeline-stops — a yearless filing stops and is named; the CLI prints the debt balance WACC used

## What I did

Backlog item 49: one new function, `ingestion/filings.require_fiscal_year_per_filing`,
holds the rule "with more than one filing, every filing needs its own fiscal year". It
raises `ValueError` naming **every** yearless filing, not the first. `parse_pdf_args`
calls it before `verify_filing_years` (so the CLI stops before the cache key is built
and before any PDF is opened), and `_run_extraction` calls it immediately after
`_parse_files_param` (so one call covers `GET /assumptions` and `POST /valuation`). The
`valid = [...]` filter and the fall-back-to-the-first-file branch are deleted from both
entry points; the full `filings` list now reaches `extract_multi_year`. Each entry
point's single-filing branch is untouched, including the CLI's
`single = len(filings) == 1 and filings[0][0] == 0`.

Backlog item 72: `pipeline.ValuationRun` carries `total_debt: float`, set in
`value_company` from the latest fiscal year's balance sheet. To read it `value_company`
must have one, so a missing balance sheet now stops beside the share-count stop, before
`fetch_price_data`; the message names `balance_sheet`, the ticker and the fiscal year,
and says the debt balance is not set to 0. `cli.py` stage 8 prints `run.total_debt`; the
conditional zero and the `latest_bs` local are gone. `calculate_wacc` keeps its own stop.

`plan_filings`' and `extract_multi_year`'s `filings` parameter widened from
`list[tuple[int, str | Path]]` to `Sequence[...]`, which removes the one type error on a
line this unit rewrote (`api/routes_valuation.py:128`).

**No number moves for a filing that has a year on every PDF.** Nothing in the valuation
arithmetic changed: the three valuation gates (suite, census, route) are unmoved and
`run.total_debt` is the same figure `calculate_wacc` already weighted the capital with,
proved by identity below.

## Done-criteria

Every command was run with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Several filings, one with no year, stop and name it | **pass** | `-c "from ingestion.filings import require_fiscal_year_per_filing as r; r([(0,'a.pdf'),(2025,'b.pdf')])"` → `ValueError: 1 of 2 filings have no fiscal year:` / `  - a.pdf (given as 'a.pdf')` |
| 2 | Every yearless filing is named, not only the first | **pass** | same with `[(0,'a.pdf'),(2025,'b.pdf'),(0,'c.pdf')]` → `2 of 3 filings have no fiscal year:` then `  - a.pdf …` and `  - c.pdf …` |
| 3 | One bare path is still allowed | **pass** | `r([(0,'a.pdf')])` returns; printed `C3,C4 ok` |
| 4 | Several filings, every one with a year, are allowed | **pass** | `r([(2024,'a.pdf'),(2025,'b.pdf')])` returns; same line |
| 5 | The CLI stops, names both files, opens no PDF | **pass** | `cli.py a.pdf b.pdf -t TESTCO` → `ERROR: 2 of 2 filings have no fiscal year:` naming both, `exit=1`. Strong form, `c:/tmp/p3b_c5_no_pdf_opened.py`, with two **real** ABBV 10-K PDFs as bare paths and `builtins.open`, `cli.extract_financials`, `cli.extract_multi_year` replaced by recorders: `PDFs opened: []`, `extractor calls: []` |
| 6 | The CLI still accepts one bare path | **pass** | `cli.py a.pdf -t TESTCO` → `ERROR: extraction input 'a.pdf' is not a readable file, so its content cannot be fingerprinted…`, exit 1 — past `parse_pdf_args`, inside the cache key. With a real PDF (`cli.py "…AbbVie Inc._10-K_2025-12-31_English.pdf" -t ABBV`) it reaches `>>> [1/10] Extracting financials via GEMINI — 1 PDF(s)` and stops on `GEMINI_API_KEY is not set` |
| 7 | The web route stops and names the file, with no extraction | **pass** | `r._run_extraction(files='0:a.pdf,2025:b.pdf', …)` → `ValueError: 1 of 2 filings have no fiscal year: / - a.pdf …`; with both extractors replaced by recorders, `extractor calls: []` (`c:/tmp/p3b_c7_c8_web.py`) |
| 8 | The message reaches the page | **pass** | `TestClient(app.app, raise_server_exceptions=False).get('/assumptions', params={'ticker':'T','files':'0:a.pdf,2025:b.pdf'})` → `status: 200`, body holds `<div class="alert alert-error">1 of 2 filings have no fiscal year: - a.pdf (given as &#39;a.pdf&#39;)…`, `'a.pdf' in body: True`, `extractor calls: []`. **Also POST**: `client.post('/valuation', data={'ticker':'T','files':'0:a.pdf,2025:b.pdf'})` → 200, `<strong>Error:</strong> 1 of 2 filings have no fiscal year: - a.pdf …`, `extractor calls: []` |
| 9 | Neither entry point filters any more | **pass** | `grep -n "valid = " cli.py api/routes_valuation.py` → no match, `rc=1`. Also `grep -rn "valid = \[" cli.py api/ ingestion/ pipeline.py` → no match |
| 10 | The CLI's conditional zero is gone | **pass** | `grep -n "latest_bs.total_debt if latest_bs" cli.py` → no match, `rc=1`. `grep -n "latest_bs" cli.py` → no match: the local is deleted too |
| 11 | The CLI prints the pipeline's figure | **pass** | `grep -n "run.total_debt" cli.py` → exactly 1: `1058:    print_wacc(wacc_result, run.market_cap, run.total_debt)` |
| 12 | A valuation with no balance sheet for the latest year stops, names the field, makes no market call | **pass** | `c:/tmp/p3b_c12_no_balance_sheet.py`: `ValueError: balance_sheet is None for 'TST' in fiscal year 2024, …The debt balance is not set to 0…`; `'balance_sheet' in message: True`, `'not set to 0' in message: True`, ticker and year in message; `fetch_price_data calls: []` with the recorder installed. Twin in the same script: the identical statements **with** a balance sheet do reach the recorder (`fetch_price_data calls now: [('TST', ('lookback_years', 3), ('frequency', 'daily'))]`), so the stop is the balance sheet's and not something upstream |
| 13 | Types | **pass on the count, dispute on the file count** — **5 errors in 2 files** | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → `Found 5 errors in 2 files (checked 21 source files)`. The criterion says "5 errors in 3 files". Measured on a clean export of `HEAD` (`git archive HEAD \| tar -x -C /c/tmp/p3b-base`), the baseline is `Found 6 errors in 3 files` and `api/routes_valuation.py` holds **exactly one** of them (`:128`, the `arg-type` this unit fixes). Removing the only error in a file removes the file, so 6-in-3 becomes 5-in-2. The remaining 5: `analysis/projector.py` ×4, `api/routes_upload.py:28` ×1 |
| 14 | Lint | **pass** — 4 errors, every one `BLE001` | `-m ruff check . --output-format concise` → `api/routes_valuation.py:451`, `:709`, `cli.py:1139`, `tests/test_e2e_all_googl.py:106`, `Found 4 errors`. On the five files in scope alone: 3 errors, all `BLE001` |
| 15 | Census | **pass** — 64 | the grep at `docs/2-rules/rules.md:102` → `64` |
| 16 | Route | **pass** — 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` → `status: 200` |
| 17 | No test fails that did not fail before, by name | **pass** | before: `14 failed, 1090 passed, 5 skipped` — the 14 names listed under Measurements. After: `1106 passed, 5 skipped` in 112 s, **0 failed**. The empty set is a subset of the 14. The 14 went green because `P1b-windows-gate`'s tester landed its `tests/` repairs in the same working tree while I worked (`git status` shows `tests/conftest.py`, `test_cli_overrides.py`, `test_p14d_finance_leases.py`, `test_pipeline.py`, `test_routes.py` modified by that unit). What this run does prove about **my** change: no test, including the 14 just repaired, fails with my five files in place |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `require_fiscal_year_per_filing` raises naming every yearless filing in one message | Assignment step 1; item 49's cost is a *silent* drop, so the reader must see every file that will not be read | Naming the first only makes a user fix one path, re-run, and meet the same stop again. `verify_filing_years` beside it already collects every problem into one message |
| The stop message names no example year | Rule 3 / rule 1 in spirit: the code does not know the filing's year, and `verify_filing_years` checks any year the user then gives against the filing's content | A worked example such as `2025:a.pdf` reads as a suggested year. A reader could copy it onto a 2023 filing; the content check would catch it, but the message would have guessed |
| Called in `parse_pdf_args` **before** `verify_filing_years` | Assignment steps 1-2; `verify_filing_years` opens each PDF with `pdfplumber` | Ordering it first means a yearless input costs no file read. Proved: two real PDFs, `PDFs opened: []` |
| Called in `_run_extraction`, not in `_extract_from_files` | Assignment step 3. `_run_extraction` is the one place both web pages extract through, and it runs before any PDF is opened | In `_extract_from_files` the stop would be one frame later and would be bypassed if a third caller ever appeared. `_extract_from_files` has exactly one caller today, and it is `_run_extraction` |
| `year <= 0`, not `year == 0` | The rule the assignment states is "a fiscal year **above 0**" | `== 0` would let a negative year through to `plan_filings`, which sorts by it and would route years silently wrong |
| An empty `filings` list returns without raising (`len(filings) <= 1`) | Not this function's question, and both callers already stop: `_run_extraction` raises `files: … names no filing.`, `plan_filings` raises `filings list is empty` | Adding a second stop for the empty case here would duplicate a message and put two owners on one rule |
| `ValuationRun.latest_balance_sheet` narrowed from `BalanceSheet \| None` to `BalanceSheet` | A direct consequence of step 6's stop: after it, the field cannot be `None`. The file's own style says "the type says what the property guarantees" (the `latest_is` comment) | Leaving `\| None` would state in the type a case the constructor can no longer reach, and every reader of the field would write a dead `if` — exactly the shape rule 3 calls a presence test with an empty branch |
| The new stop's message keeps the words "balance_sheet is None" | It names the field the way `analysis/wacc.py:_require_balance_sheet` names it, so one vocabulary covers both stops | A different wording for the same missing input makes a reader think two different things are absent |
| The three explanatory comments describe the deleted lines instead of quoting them | Done-criteria 9, 10 and 11 are greps over `cli.py` and `api/routes_valuation.py`; a comment that reproduces the deleted expression makes the grep that checks the deletion go green on a comment | The history is kept — each comment names the backlog item and what the old line did — without blinding the measurement that checks it |

**No change in this unit was made to reach a target number.** No valuation figure moved;
the only figures produced are from hand-built inputs in `c:/tmp/` scratch scripts.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `filings` entry's fiscal year, with more than one filing (CLI) | **stops** and names every yearless file | `cli.py a.pdf b.pdf -t TESTCO` → `ERROR: 2 of 2 filings have no fiscal year:` + both names, exit 1 |
| `filings` entry's fiscal year, with more than one filing (web, `files`) | **stops** and names every yearless file | `_run_extraction(files='0:a.pdf,2025:b.pdf', …)` → `ValueError … - a.pdf`; rendered on both pages at 200 |
| `filings` entry's fiscal year, with exactly one filing | **allowed, by design**: 0 means "every year this filing presents" | `r([(0,'a.pdf')])` returns; `ingestion/filings.py:342-344`, `parse_pdf_args` docstring. Single-filing semantics are unchanged by this unit |
| latest fiscal year's balance sheet (`pipeline.value_company`) | **stops** and names `balance_sheet`, the ticker and the year, before any market call | `c:/tmp/p3b_c12_no_balance_sheet.py` → `ValueError: balance_sheet is None for 'TST' in fiscal year 2024…`, `fetch_price_data calls: []` |
| `run.total_debt`, printed by CLI stage 8 | **stops** — it cannot be missing: the balance sheet stop runs first, so the field is always the balance sheet's own `total_debt` | `grep -n "latest_bs" cli.py` → no match; `pipeline.py` sets `total_debt = latest_bs.total_debt` after the stop |
| debt lines inside the balance sheet (`short_term_debt`, `current_portion_lt_debt`, `long_term_debt`) | **stops**, in `calculate_wacc`, unchanged by this unit (`_require_valid_debt`, and the zero-debt stop of item 38b) | `c:/tmp/p3b_c11_debt_from_the_filing.py`, second half: a balance sheet with no debt lines beside interest expense 100 stops with the item 38b message |
| `filings`' element type at `extract_multi_year` | n/a — a typing widening only; no runtime behaviour | mypy 6→5; suite unchanged |

No row of this table reads "defaults to".

## Measurements

**Suite, before** (`-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly`, run at the
start of this unit against the unmodified tree):
`14 failed, 1090 passed, 5 skipped in 128.70s` — exactly the assignment's figure. The 14:

```
tests/unit/test_p15a_two_routes.py::test_cli_refuses_dash_p_claude
tests/unit/test_pipeline.py::test_the_share_count_stop_reaches_the_web_result_page
tests/unit/test_pipeline.py::test_cli_and_web_report_the_same_implied_share_price
tests/unit/test_routes.py::test_get_assumptions_shows_the_confirm_zero_debt_checkbox_inside_the_valuation_form
tests/unit/test_routes.py::test_post_valuation_with_the_box_checked_values_the_company_with_no_debt
tests/unit/test_routes.py::test_post_valuation_with_the_box_checked_and_an_override_says_the_rate_reaches_nothing
tests/unit/test_routes.py::test_post_valuation_with_the_box_unchecked_stops_at_item_22[absent]
tests/unit/test_routes.py::test_post_valuation_with_the_box_unchecked_stops_at_item_22[empty]
tests/unit/test_routes.py::test_post_valuation_with_the_box_unchecked_stops_at_item_22[absent-with-override]
tests/unit/test_routes.py::test_post_valuation_with_a_value_no_checkbox_sends_stops_and_names_it[yes]
tests/unit/test_routes.py::test_post_valuation_with_a_value_no_checkbox_sends_stops_and_names_it[ON]
tests/unit/test_routes.py::test_post_valuation_with_a_value_no_checkbox_sends_stops_and_names_it[true]
tests/unit/test_routes.py::test_post_valuation_with_a_value_no_checkbox_sends_stops_and_names_it[1]
tests/unit/test_routes.py::test_post_valuation_with_a_value_no_checkbox_sends_stops_and_names_it[ on]
```

**Suite, after:** `1106 passed, 5 skipped, 2 warnings in 112.01s`. Failing set after = {}.
{} ⊂ the 14. No name was added. The 14 were removed by `P1b-windows-gate`'s tester, not
by me — its edits to six files under `tests/` landed in this working tree during my run.

| Gate | Before (assignment, re-confirmed on a clean `HEAD` export where noted) | After |
|---|---|---|
| suite (gate form) | 14 failed, 1090 passed, 5 skipped | **0 failed, 1106 passed, 5 skipped** |
| types | 6 errors in 3 files (re-measured on `git archive HEAD`) | **5 errors in 2 files** |
| lint | 4 errors, all `BLE001` | **4 errors, all `BLE001`** |
| census (grep at `rules.md:102`) | 64 | **64** |
| route `GET /` | 200 | **200** |
| write guard | 48/48 | **48/48** |

**The one figure this unit produces, and where its inputs came from.** `run.total_debt`,
on Walmart's fiscal 2026 balance sheet rows as printed on **page 22** of its 10-K (the
same rows `tests/unit/test_p14d_finance_leases.py` builds): short-term borrowings 6,596 +
long-term debt due within one year 3,542 + finance lease obligations due within one year
856 = 10,994; long-term debt 34,624 + long-term finance lease obligations 5,905 = 40,529.
Hand sum **51,523**. Market data is a stub in this script, so no market figure is claimed.
`c:/tmp/p3b_c11_debt_from_the_filing.py`:

```
run.total_debt           : 51,523
hand sum of page 22 lines: 51,523
equal                    : True
debt weight from the run : 0.2048440898
debt / (market cap+debt) : 0.2048440898
equal                    : True
...
  Total debt:           $      51,523M
```

The second identity is the one criterion 11 is really about: the figure stage 8 prints is
the balance `calculate_wacc` weighted the capital with, not a second reading of the
balance sheet. `cli.print_wacc(run.wacc_result, run.market_cap, run.total_debt)` prints
`Total debt: $51,523M` beside `Debt weight: 20.5%`.

**No end-to-end Walmart valuation was run.** `extractions/` does not exist on this
machine and `10K_filings/` holds PDFs only, as the assignment states; no criterion asks
for one.

## What I did not do

- **No tests.** `tests/` is out of scope and denied by the write guard. `P1b-windows-gate`
  was writing six files there throughout this run.
- **`api/routes_upload.py` untouched**, as the assignment requires. Its year-0 pass-through
  now meets this unit's stop at `GET /assumptions`, which is what its docstring said would
  happen.
- **`ingestion/session_extraction.py` untouched.** Its own year check keeps the JSON path
  of the offending entry, which `require_fiscal_year_per_filing` cannot give.
- **`analysis/wacc.py` untouched.** Its `_require_balance_sheet` stop stands; it guards
  every other caller and its tests call it directly.
- **Items 5, 8, 26, 82, 87-92 left alone**, though each sits in a file I touched.

## Findings for the orchestrator

1. **`api/routes_valuation._parse_files_param` stops with a bare `int()` message that
   names neither the field nor the file.** Measured:
   `_parse_files_param('a.pdf,b.pdf')` → `ValueError: invalid literal for int() with
   base 10: 'a.pdf'`, and `_parse_files_param('x:a.pdf,2025:b.pdf')` → the same shape.
   That message reaches the page through the blanket `except Exception` (criterion 8's
   path), so a user who omits the `year:` prefix on the web form is told about base 10.
   It stops, so it is not a rule 3 defect; it is the naming half of rule 3. Adjacent to
   item 26, which is about the same `files` branch. Not fixed: outside this unit's eight
   steps.
2. **The assignment's criterion 13 expects "5 errors in 3 files"; the measurement is 5 in
   2.** The error count is right. `api/routes_valuation.py` held exactly one of the
   baseline 6 (verified on `git archive HEAD`), so fixing it removes the file from the
   count. Worth correcting in `STATUS.md` section 1 when this unit is accepted:
   **5 errors in 2 files**, `analysis/projector.py` ×4 and `api/routes_upload.py:28` ×1.
3. **The baseline suite figure in the assignment (14 failed) is already stale**, because
   `P1b-windows-gate` landed during this unit. Whoever reviews P3b will measure
   `0 failed, 1106 passed, 5 skipped` and should not read the difference as mine.
4. **`pipeline.ValuationRun.latest_balance_sheet` is now non-optional and is read by
   nobody** (`grep -rn "latest_balance_sheet" --include=*.py` outside `tests/` and
   `ingestion/` finds only `pipeline.py` itself, plus one assertion in
   `tests/unit/test_pipeline.py`). `total_debt` is what the CLI needed from it. If a
   reviewer would rather the run carried no whole balance sheet, deleting the field is a
   one-line change — but it is not this unit's, and `tests/unit/test_pipeline.py:298`
   asserts on it today.
