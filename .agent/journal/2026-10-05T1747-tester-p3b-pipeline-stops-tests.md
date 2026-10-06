---
agent: tester
assignment: P3b-pipeline-stops-tests
round: 2
status: complete
files_touched: [tests/unit/test_p3b_pipeline_stops.py]
verdict: pass
---

# P3b-pipeline-stops-tests — lock item 49's stop and item 72's debt figure

## What I did

Round 1 wrote `tests/unit/test_p3b_pipeline_stops.py` and stopped before it measured
anything. Round 2 audited all 25 round-1 cases, replaced two whose measurement was
vacuous, added four tests, confirmed the Walmart rows against the PDF, ran the four
mutations, and measured all nine criteria. The file is now **28 test functions, 29
cases, 80 assertions, 927 lines**, and every one of criteria 1 to 9 is a command with
an output recorded below. Nothing outside `tests/` changed.

The audit found three real weaknesses, all inside `tests/`, all fixed here:

* **A1. The CLI stop test was vacuous.** `test_cli_main_stops_on_two_bare_paths_and_names_both_files`
  ran the module with `runpy.run_path(cli.__file__, run_name="__main__")`. `runpy`
  executes the file into a **fresh namespace**, so `monkeypatch.setattr(cli,
  "extract_financials", ...)` patched a name that namespace never bound, and the
  assertion `cli_extractor_calls == {"single": [], "multi": []}` was true whatever the
  fresh copy did. Behaviour 5's "neither extractor is called" was therefore not
  measured. Replaced with a direct `cli.main()` call — the same entry
  (`cli.py:1133`) — so the recorders are the names the code under test resolves. The
  empty lists are now a measurement. Mutation 16 confirms it: the test goes red.
* **A2. One test assumed its own premise.** `test_a_bare_path_whose_name_carries_a_year_is_still_yearless`
  claims the file **name** is not read for a year, but builds the `(0, name)` pairs
  itself and hands them straight to `require_fiscal_year_per_filing`. Kept, and added
  `test_parse_pdf_args_does_not_read_a_year_out_of_a_file_name`, which gives
  `parse_pdf_args` two files actually named `ABBV_10-K_2025-12-31.pdf` and
  `ABBV_10-K_2024-12-31.pdf`, so the 0 is the parser's.
* **A3. Mutation 17 left behaviour 12 green.** With the balance sheet present,
  `run.total_debt` and the reverted `latest_bs.total_debt if latest_bs else 0` are the
  same 51,523, so the stage-8 print test cannot tell them apart, and the CLI can no
  longer reach stage 8 without a balance sheet. Added
  `test_valuation_run_requires_total_debt_and_a_balance_sheet_with_no_default`, which
  asserts the `ValuationRun` contract mutation 17 deletes: `total_debt` is a field,
  `latest_balance_sheet`'s annotation admits no `None`, and no field has a default.

I also closed the premise behind `test_require_fiscal_year_allows_an_empty_list`: an
empty-list return is only not a rule-3 fallback if the callers stop themselves, so two
tests now ask them (`cli.parse_args()` → `SystemExit(2)`; `_run_extraction(files=",")`
→ `ValueError` naming `files`).

**I did not replace any expected value for being code-derived.** All 80 assertions
trace to the stated contract, to page 22 of the Walmart 10-K, or to hand arithmetic;
the table below gives the source of each.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Every behaviour 1 to 13 has a test | **pass** — 13 of 13, mapped below | `-m pytest -q tests/unit/test_p3b_pipeline_stops.py` → `29 passed in 3.36s` |
| 2 | The gate is green | **pass** — 0 failed | `-m pytest -q --ignore-glob="*_rule3_red.py"` → `1136 passed, 5 skipped` |
| 3 | Full suite shows only the two deliberate failures | **pass** — 2 failed | `-m pytest -q -rf` → `2 failed, 1136 passed, 5 skipped`; the two are `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` |
| 4 | Each of the four mutations turns a named test red | **pass** — 4 of 4, 18 named tests in total | the mutation table below |
| 5 | 100% of `require_fiscal_year_per_filing`'s statements and branches | **pass** | `COVERAGE_FILE=C:/tmp/p3b_coverage coverage run --branch -m pytest -q` then `coverage report --include="ingestion/filings.py" --show-missing` → `209 stmts, 0 miss, 88 branch, 0 BrPart, 100%`, `Missing` column empty. The whole module is at 100/100, so the function's 8 statements and 6 branch arcs are all exercised |
| 6 | Accuracy count, with the source of each | **pass** — **80 of 80 assertions** match an independently derived expectation | the "Expected values" table below |
| 7 | Nothing outside `tests/` changed | **pass** | `git status --porcelain` → the five files of the code unit, three journal/assignment files, `docs/9-reference/refactor-backlog.md`, `.agent/journal/INDEX.md`, and `tests/unit/test_p3b_pipeline_stops.py`. Identical to the status at the start of this session |
| 8 | Lint: 4 errors, every one `BLE001` | **pass** | `-m ruff check .` → `Found 4 errors`, all `BLE001`, at `api/routes_valuation.py:451`, `api/routes_valuation.py:709`, `cli.py:1139`, `tests/test_e2e_all_googl.py:106`. `ruff check tests/unit/test_p3b_pipeline_stops.py` → `All checks passed!` |
| 9 | The two helper modules unchanged | **pass** | `git status --porcelain tests/` → `?? tests/unit/test_p3b_pipeline_stops.py` and nothing else. `tests/unit/_fiscal_year_stub.py` and `tests/unit/_session_route_helpers.py` do not appear |

Every command was prefixed `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and run with
`.venv/Scripts/python.exe` on the Windows machine, Python 3.14.4.

Types, not a criterion, measured so a regression would show:
`-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports`
→ **5 errors in 2 files**, the figure the assignment records for this unit. Unchanged.

## Behaviours 1 to 13, mapped to test names

| # | Behaviour | Test |
|---|---|---|
| 1 | message names **every** yearless filing, 2 of 3 | `test_require_fiscal_year_names_every_yearless_filing_not_only_the_first`; also `test_require_fiscal_year_names_the_only_yearless_filing` |
| 2 | returns for one yearless filing, for several that all have a year, for an empty list | `test_require_fiscal_year_allows_one_filing_with_no_year`, `test_require_fiscal_year_allows_several_filings_that_all_have_a_year`, `test_require_fiscal_year_allows_an_empty_list` |
| 3 | a negative year counts as no year | `test_require_fiscal_year_treats_a_negative_year_as_no_year[-1]`, `[-2025]` |
| 4 | `parse_pdf_args` with two bare paths raises before any PDF is opened | `test_parse_pdf_args_stops_on_two_bare_paths_before_opening_a_pdf`; also `test_parse_pdf_args_does_not_read_a_year_out_of_a_file_name` |
| 5 | `cli.main` exits non-zero with `ERROR:`, names both files, calls neither extractor | `test_cli_main_stops_on_two_bare_paths_and_names_both_files` |
| 6 | `_run_extraction(files='0:a.pdf,2025:b.pdf')` raises, names `a.pdf`, calls neither extractor | `test_run_extraction_stops_on_a_yearless_filing_and_names_it` |
| 7 | `GET /assumptions` and `POST /valuation` render it at HTTP 200 with the file name | `test_the_stop_reaches_the_assumptions_page`, `test_the_stop_reaches_the_valuation_result_page` |
| 8 | three filings with years all reach `extract_multi_year`, both entry points | `test_three_filings_with_years_all_reach_extract_multi_year_in_the_cli`, `..._in_the_web_route`; the filter's own absence: `test_the_cli_never_drops_a_filing_from_the_list_it_was_given`, `test_the_web_route_never_drops_a_filing_from_the_list_it_was_given` |
| 9 | a single bare path still reaches `extract_financials`, both entry points | `test_one_bare_path_still_reaches_extract_financials_in_the_cli`, `..._in_the_web_route` |
| 10 | `value_company` stops on a missing balance sheet, names field/ticker/year, before `fetch_price_data`; the twin reaches it | `test_value_company_stops_on_a_missing_balance_sheet_before_any_market_call`, `test_the_same_statements_with_a_balance_sheet_do_reach_fetch_price_data` |
| 11 | `ValuationRun.total_debt` is the hand sum of the three debt lines | `test_total_debt_is_the_hand_sum_of_walmarts_debt_lines` |
| 12 | stage 8 prints that same figure | `test_cli_stage_8_prints_the_debt_balance_wacc_used` |
| 13 | `debt_weight == total_debt / (market_cap + total_debt)` | `test_the_debt_weight_is_total_debt_over_market_cap_plus_total_debt` |

Four tests are not in the list because they are not in behaviours 1 to 13:
`test_the_stop_gives_each_entry_point_the_remedy_that_works_there` (review finding F1),
`test_a_bare_path_whose_name_carries_a_year_is_still_yearless` (round 2's criterion 18
of the code unit),
`test_valuation_run_requires_total_debt_and_a_balance_sheet_with_no_default` (A3 above),
and the two empty-list caller tests.

## The Walmart figures, checked against the PDF

`10K_filings/WMT/Walmart Inc._10-K_2026-01-31_English.pdf`, **PDF page 22** — the
Consolidated Balance Sheets, which the filing prints as its own page **54**. Read with
`pdfplumber.extract_text`, "As of January 31, (Amounts in millions) 2026 2025", the
2026 column:

| Row as printed | Printed | File header claims | Agree |
|---|---|---|---|
| Short-term borrowings | 6,596 | 6,596 | yes |
| Long-term debt due within one year | 3,542 | 3,542 | yes |
| Finance lease obligations due within one year | 856 | 856 | yes |
| Long-term debt | 34,624 | 34,624 | yes |
| Long-term finance lease obligations | 5,905 | 5,905 | yes |

Hand sums: 6,596 + 3,542 = 10,138; 10,138 + 856 = **10,994**. 34,624 + 5,905 =
**40,529**. 10,994 + 0 + 40,529 = **51,523**. Every figure and every sum in the file
header is confirmed. The three current rows are corroborated a second time on PDF page
20 (short-term borrowings variable rate $6,596 total) and PDF page 28 (Note 5: "Less
amounts due within one year (3,542)", "Long-term debt $34,624").

**One correction to the wording, not to a figure.** The assignment and the file header
both say "page 22". That is the **PDF page index**, not the page number printed on the
page, which is 54. The figures are right; a reader opening the paper filing at its page
22 will not find them. Noted for whoever writes the next citation.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| a filing's fiscal year, several filings, CLI | **stops**, names **every** yearless path (file name and the string as given) | `ingestion/filings.py:531` via `parse_pdf_args`; `test_parse_pdf_args_stops_on_two_bare_paths_before_opening_a_pdf`, `test_cli_main_stops_on_two_bare_paths_and_names_both_files` |
| a filing's fiscal year, several filings, web route | **stops**, names every yearless path | `api/routes_valuation.py:197`; `test_run_extraction_stops_on_a_yearless_filing_and_names_it`, the two page tests |
| `files` naming no filing (web route) | **stops**, names `files` | `api/routes_valuation.py:190`; `test_the_web_route_stops_before_the_fiscal_year_rule_when_files_names_none` |
| no PDF given (CLI) | **stops**, `SystemExit(2)` from argparse | `cli.py:185`; `test_the_cli_stops_before_the_fiscal_year_rule_when_no_pdf_is_given` |
| the latest year's balance sheet | **stops**, names `balance_sheet`, the ticker and the fiscal year, **before** `fetch_price_data` | `pipeline.py:182-193`; `test_value_company_stops_on_a_missing_balance_sheet_before_any_market_call` asserts `price_calls == []` and `ticker_calls == []` |
| the debt balance shown in CLI stage 8 | **cannot be missing**: `ValuationRun.total_debt` is required and `latest_balance_sheet` is non-optional, so stage 8 has no branch to default on | `pipeline.py:94-95`, `cli.py:1058`; `test_valuation_run_requires_total_debt_and_a_balance_sheet_with_no_default` |
| the latest year's diluted share count | **stops**, names `diluted_shares` (P3a, re-exercised here) | `pipeline.py:163-170`; reached by every `value_company` test in this file |

**No stop path in this unit's scope defaults.** There is no "defaults to" row, and no
test in this file asserts a fallback. One assertion is deliberately negative —
`assert f"Total debt:           ${0.0:>12,.0f}M" not in wacc_block` — which locks the
absence of the old conditional zero rather than its presence.

`require_fiscal_year_per_filing([])` returning is **not** a fallback: it is the stated
contract (the function does not own the empty rule), and both callers stop on empty
themselves, which the two new tests now measure rather than assume.

## The four mutations

Applied in a scratch copy at `C:/tmp/p3bmut` (the repository without `.git` and
`.venv`), never in the repository. Each mutation was restored by copying the file back
from the repository and confirmed byte-identical with `filecmp.cmp(..., shallow=False)`
before the next one. Baseline in the scratch copy before any mutation: **2 failed, 1133
passed, 5 skipped** — the two deliberate red tests only.

| # | Mutation | Suite | Named tests that went red |
|---|---|---|---|
| 14 | `valid = [(y, p) for y, p in filings if y > 0]` back in `cli.py` `_extract_via_api`, with its single-file fallback | 3 failed | `test_the_cli_never_drops_a_filing_from_the_list_it_was_given` |
| 15 | the same filter back in `api/routes_valuation.py` `_extract_from_files` | 3 failed | `test_the_web_route_never_drops_a_filing_from_the_list_it_was_given` |
| 16 | `require_fiscal_year_per_filing` returns without raising | 14 failed | `test_require_fiscal_year_names_every_yearless_filing_not_only_the_first`, `test_require_fiscal_year_names_the_only_yearless_filing`, `test_the_stop_gives_each_entry_point_the_remedy_that_works_there`, `test_a_bare_path_whose_name_carries_a_year_is_still_yearless`, `test_parse_pdf_args_does_not_read_a_year_out_of_a_file_name`, `test_require_fiscal_year_treats_a_negative_year_as_no_year[-1]`, `[-2025]`, `test_parse_pdf_args_stops_on_two_bare_paths_before_opening_a_pdf`, `test_cli_main_stops_on_two_bare_paths_and_names_both_files`, `test_run_extraction_stops_on_a_yearless_filing_and_names_it`, `test_the_stop_reaches_the_assumptions_page`, `test_the_stop_reaches_the_valuation_result_page` — **12** |
| 17 | `total_debt = latest_bs.total_debt if latest_bs else 0` back in `cli.py` stage 8; in `pipeline.py` the `latest_bs is None` stop deleted, `total_debt` field deleted, `latest_balance_sheet: BalanceSheet \| None` | 5 failed (4 in this file) | `test_value_company_stops_on_a_missing_balance_sheet_before_any_market_call`, `test_valuation_run_requires_total_debt_and_a_balance_sheet_with_no_default`, `test_total_debt_is_the_hand_sum_of_walmarts_debt_lines`, `test_the_debt_weight_is_total_debt_over_market_cap_plus_total_debt` — **4** |

Each of the three failures in 14 and 15 and the 14 in 16 and the 5 in 17 include the
two deliberate red tests, which fail at baseline too.

**Mutation 17's one green test is recorded, not hidden.**
`test_cli_stage_8_prints_the_debt_balance_wacc_used` stays green under mutation 17,
because with a balance sheet present the two readings give the same 51,523, and because
`value_company`'s stop means stage 8 can no longer be reached without one. That is why
A3's dataclass-contract test was added: it is red under mutation 17, so the field
deletion is reported.

After the last restore, `git status --porcelain` in the repository showed exactly the
five code files, the journal and assignment files, and
`tests/unit/test_p3b_pipeline_stops.py` — the same set as at the start of the session.
`C:/tmp/p3bmut` has been deleted.

## Expected values — testers only

**80 of 80 assertions.** Grouped; every assertion in the file is in exactly one row.

| Assertions | Expected | Where the expected value came from |
|---|---|---|
| `"a.pdf" in message`, `"c.pdf" in message`, `"b.pdf" not in message`, both `ABBV_10-K_*.pdf` names, in 8 stop tests (17 assertions) | the input list's own file names, and only the offenders | **Stated contract**: `require_fiscal_year_per_filing`'s docstring, "naming EVERY filing that has no fiscal year, not only the first". A list of file names is the input, not a computed number |
| `len(command_line) == 1`, `len(web_upload) == 1`, `"YEAR:PATH" in/not in`, `"rename the file" in/not in` (6) | one line per entry point, each carrying only the remedy that works there | **Stated contract**: review finding F1 and the docstring, "Each remedy in the message names the entry point it works on... the remedy is YEAR:PATH... There the remedy is to rename and upload again" |
| `require_fiscal_year_per_filing(...) is None` ×3 (3) | returns for one filing, for several all with a year, for an empty list | **Stated contract**: the docstring's three return cases |
| `"a.pdf" in str(raised.value)` for year −1 and −2025 (1 statement, 2 cases) | a negative year is no year | **Stated contract**: the rule is "a fiscal year above 0"; the code's own predicate is `year <= 0` |
| `pdf_opens == []` ×3 (3) | no PDF opened before the stop | **Stated contract**: `parse_pdf_args`' docstring, "It is called first, before any PDF is opened, so the stop costs no file read". The fixture records both doors `read_fiscal_year_evidence` uses (`pdfplumber.open`, `ingestion/filings.py:238`, and `builtins.open`), so the empty list is a record of opens, not an absence of an error |
| `isinstance(code, str)`, `code != 0`, `code.startswith("ERROR:")` (3) | `SystemExit("ERROR: ...")` | **Stated contract**: `cli.py:828`, `raise SystemExit(f"ERROR: {exc}")`, and `sys.exit`'s documented rule that a string code exits status 1 |
| `cli_extractor_calls == {"single": [], "multi": []}`, `route_extractor_calls == {...}` ×4 (4) | neither extractor is called on a stop | **Stated contract**: the behaviour as the assignment states it (5, 6, 7) |
| `response.status_code == 200` ×2 (2) | the stop renders, it does not 500 | **Stated contract**: assignment behaviour 7, "each render the message at HTTP 200 (backlog item 8 owns the status code)" |
| `"a.pdf" in shown`, `"a.pdf" in body`, `"Implied Share Price" not in body` (3) | the offending file name on the page, no valuation | **Stated contract**: as above. The page recorders raise and name no path, so a page showing `a.pdf` can only have got it from the stop |
| `calls["multi"] == [[(2023, a), (2024, b), (2025, c)]]` and the web route's `[(2023,"a.pdf"),(2024,"b.pdf"),(2025,"c.pdf")]`, with `calls["single"] == []` (4) | the list given is the list extracted, all three | **Stated contract**: assignment behaviour 8, "the filing that used to be dropped now reaches the extractor". The expected value is the test's own input list |
| `calls["single"] == [str(pdf)]` / `["a.pdf"]`, `calls["multi"] == []` (4) | one bare path still goes to `extract_financials`, with the path given | **Stated contract**: assignment behaviour 9; the expected value is the test's own input path |
| `calls["multi"] == [given]`, `calls["single"] == []` ×2 (4) | no entry point drops a filing from the list it was handed | **Stated contract**: the filter is gone; the expected value is the test's own `given` list |
| `raised.value.code == 2`; `"files" in str(raised.value)` + recorders empty (3) | both callers stop on empty themselves | **Stated contract**: `cli.py:185` `p.error(...)` → argparse's documented exit status 2; `api/routes_valuation.py:190` `files: {files!r} names no filing.` |
| `"balance_sheet" in message`, `"WMT" in message`, `"2026" in message`, `price_calls == []`, `ticker_calls == []` (5) | the stop names the field, the ticker and the year, before any market call | **Stated contract**: `pipeline.value_company`'s `Raises:` clause, "Both are raised before any market data is fetched", and the message at `pipeline.py:183-193` |
| `price_calls == [("WMT", 3, "daily")]` ×3, `ticker_calls == []` ×4 (7) | the twin: with a balance sheet the run reaches `fetch_price_data`, with the test's own arguments | **Stated contract**: `value_company`'s signature passes `ticker`, `lookback_years`, `frequency` straight through; the expected tuple is the test's own input |
| `"total_debt" in by_name`, `"latest_balance_sheet" in by_name`, `"None" not in str(type)`, `default is MISSING`, `default_factory is MISSING` (5) | the `ValuationRun` contract | **Stated contract**: `ValuationRun`'s docstring — "It is never `None`", "`total_debt` is that balance sheet's debt balance", "Every field is required. None is defaulted." |
| `WMT_SHORT_TERM_DEBT == 10994.0` (1) | 6,596 + 3,542 + 856 = 10,994 | **Filing page**: 10-K PDF page 22 (printed page 54), three printed rows; **hand arithmetic** for the sum |
| `WMT_LONG_TERM_DEBT == 40529.0` (1) | 34,624 + 5,905 = 40,529 | **Filing page**: same page, two printed rows; **hand arithmetic** for the sum |
| `run.total_debt == approx(51523.0)` (1) | 10,994 + 0 + 40,529 = 51,523 | **Hand arithmetic** over the five filing rows, against `BalanceSheet.total_debt`'s formula `short_term_debt + current_portion_lt_debt + long_term_debt` (`models/financial_statements.py:274`). `current_portion_lt_debt` is 0 because all three current debt rows map to `short_term_debt`, as `tests/unit/test_p14d_finance_leases.py` maps the same page |
| `run.market_cap == approx(48477.0)` (1) | 48,477 shares × $1.00 = 48,477 | **Hand arithmetic**. `market_cap = price_data.current_price * shares` (`pipeline.py:208`); the share count and the stub price are the test's own inputs, chosen so the product is exact |
| `wacc_result.debt_weight == approx(0.51523)`, `equity_weight == approx(0.48477)` (2) | 48,477 + 51,523 = 100,000; 51,523 / 100,000 = 0.51523; 48,477 / 100,000 = 0.48477 | **Hand arithmetic** on inputs chosen to make total capital exactly 100,000 |
| `debt_weight == approx(total_debt / (market_cap + total_debt))` (1) | D / (E + D) | **Closed-form identity**, checked on the run's own figures as well as against the decimal above. This is what makes behaviour 11 read "the figure shown is the figure used" |
| `"Total debt:           $      51,523M" in wacc_block`, `"Market cap:           $      48,477M" in wacc_block`, `"Total debt:           $           0M" not in wacc_block` (3) | the hand sums above, in `print_wacc`'s format | **Hand arithmetic** for both figures; the label and the `${:>12,.0f}M` format are read off `cli.py:764-765`, which is the stated format and holds no number |
| `price_calls == [("WMT", 3, "daily")]`, `ticker_calls == []` inside the stage-8 test — counted in the `price_calls` row above | | |

**Not one expected value in this file was obtained by running the code.** The three
I replaced or added in round 2 (A1, A2, A3) are contract-derived in the same way.

**Two counts, with their units.**

* **Accuracy: 80 of 80 assertions.** Every assertion's expected value is sourced in the
  table above: 10 from hand arithmetic over figures read off 10-K PDF page 22, 1 from
  the closed-form identity `D / (E + D)`, 69 from the stated contract (a docstring, a
  message the docstring specifies, an argparse-documented exit status, or the test's
  own input list). 0 from the code's output.
* **Coverage: 7 of 7 functions and 1 of 1 dataclass that this unit added or changed are
  exercised; 100% of statements and branches in the one new function.**
  - `ingestion/filings.require_fiscal_year_per_filing` (new): 8 of 8 statements,
    6 of 6 branch arcs — `len(filings) <= 1` both ways, `not yearless` both ways, the
    comprehension loop both ways. Measured: `ingestion/filings.py` reports
    `209 stmts, 0 miss, 88 branch, 0 BrPart, 100%`.
  - `ingestion/filings.parse_pdf_args` (changed), `cli._extract_via_api` (changed),
    `cli.main` stage 8 (changed), `api/routes_valuation._run_extraction` (changed),
    `api/routes_valuation._extract_from_files` (changed), `pipeline.value_company`
    (changed): every changed line is covered. `pipeline.py` misses only line 147 (the
    documented-unreachable `latest_is is None` raise, from P3a, not this unit);
    `api/routes_valuation.py` misses only 199, 267, 353 (the legacy `file_path`
    branch and two unrelated lines); `cli.py`'s missing set holds no line this unit
    changed.
  - Module totals, for the record: `ingestion/filings.py` 100%,
    `api/routes_valuation.py` 98%, `pipeline.py` 97%, `cli.py` 78%.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Replaced `runpy.run_path` with `cli.main()` in the CLI stop test | `runpy` builds a fresh namespace, so the monkeypatched extractor names were not the ones under test and the "neither extractor was called" assertion could not fail | Keeping `runpy` and dropping the assertion would have left behaviour 5 half-measured; `cli.main()` is the same entry the `__main__` guard calls (`cli.py:1133`) |
| Added a `parse_pdf_args` test beside the name-carries-a-year one rather than rewriting it | The old test is still a valid statement about the function; it is only its docstring's claim about the parser that it cannot support | Deleting it would lose a case; leaving it alone would leave the claim unproven |
| Added a dataclass-contract test instead of forcing stage 8 to print a zero | Stage 8 is unreachable without a balance sheet now, and a test that reached it would have to assert the fallback — the one thing the role card forbids | Asserting `total_debt` exists and no field defaults locks exactly what mutation 17 deletes, without locking a default |
| Ran the mutations in `C:/tmp/p3bmut`, not in the repository | The write guard allows `tests/` only, and a tester may not edit implementation code | A `git stash` dance would have put mutated code in the working tree |
| Did not move anything into or out of a `*_rule3_red.py` file | No test here states a requirement the code does not meet; all 29 cases are green against the unit's code | — |

## What I did not do

* I did not re-derive the code unit's own 17 done-criteria. The reviewer did that; this
  unit's job was to turn them into tests, which criteria 1 and 4 above measure.
* I did not test the legacy `file_path` branch of `_run_extraction`
  (`api/routes_valuation.py:199`, uncovered by the whole suite). It is outside
  behaviours 1 to 13 and this unit did not change it.
* I did not add a test for `discover_filings`' own yearless-name stop, which the new
  function's docstring cites as the reason a ticker folder never reaches it.
  `tests/unit/test_filings.py` and `tests/unit/test_fiscal_year.py` already own that
  path.
* No end-to-end valuation of a real filing was run: `extractions/` is empty and no
  criterion asks for one.

## Findings for the orchestrator

1. **The "page 22" citation is a PDF page index, not a printed page number.** The
   Walmart Consolidated Balance Sheets are the 22nd page of
   `10K_filings/WMT/Walmart Inc._10-K_2026-01-31_English.pdf` and are printed as page
   **54** of the filing. Every figure in `.agent/assignments/P3b-pipeline-stops-tests.md`
   behaviour 11 is confirmed; only the page wording is ambiguous. The same ambiguity is
   in `tests/unit/test_p14d_finance_leases.py` and now in this file's header, which I
   left as written so the three agree. Worth one convention line in
   `docs/5-testing/strategy.md`: a filing citation gives the printed page, and the PDF
   index beside it.
2. **`runpy.run_path` defeats monkeypatching, and this repository uses it.** The defect
   A1 describes is not specific to this unit: any test that patches a module attribute
   and then re-executes that module under `runpy` is asserting against a namespace its
   patch never reached. Worth a grep across `tests/` and, if any others are found, a
   backlog item. I checked only this file.
3. **`api/routes_valuation.py:199` is reached by no test in the suite.** `filings =
   [(0, file_path)]` — the legacy single-`file_path` branch. It is correct as written
   (one filing with year 0 is the allowed case), but it is the one door into
   `_extract_from_files` that `require_fiscal_year_per_filing` does not guard, and
   nothing would report it if a second filing ever arrived that way. Not this unit's
   change; a candidate backlog item.
4. **Backlog item 24's pattern check, done.** No module in this unit's scope has a
   recently-fixed defect whose green test is stranded in a `*_rule3_red.py` file. The
   two red tests in the suite —
   `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`
   and
   `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`
   — are both still red, so both are still in the right file.
