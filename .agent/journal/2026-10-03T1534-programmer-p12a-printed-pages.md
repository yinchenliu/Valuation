---
agent: programmer
assignment: P12a-printed-pages
round: 1
status: complete
files_touched: [ingestion/claude_extractor.py, ingestion/session_extraction.py, docs/2-rules/llm-boundary.md, docs/3-architecture/extraction.md, .agent/journal/2026-10-03T1534-programmer-p12a-printed-pages.md]
---

# P12a-printed-pages — each Pass 1 printed line is looked up on its cited page

Started at `0839ad9`, 2026-10-03, macOS, `.venv/bin/python` 3.11.6. Not committed.

## What I did

Both routes now open the filing's PDF with `pdfplumber` and look for every Pass 1 printed
line on the page it cites. A match needs the line's label and figure on one text line.
In `ingestion/claude_extractor.py`, next to `_validate_extracted_data`, I added five things:

- `printed_line_on_page(label, value, page_text) -> bool`. This is the assignment's rule,
  written as a pure function.
- `_read_cited_pages(pdf_bytes, pages)`. It opens the PDF once and reads each cited page
  once. It returns the page count and each text layer.
- `_printed_line_failure(...)`. It decides one line: found, not found, page beyond the
  PDF, or no text layer.
- `_printed_line_failures(data, pdf_bytes)`. This is **the walk**. It covers every line
  field of every year and of the balance sheet, and returns `list[_CheckFailure]`.
- `printed_line_page_failures(json_str, pdf_bytes) -> list[str]`. This is route B's
  public wrapper, placed beside `parse_pass1`.

**Route A.** In `_run_financials_pass`, after a successful parse, the page failures are
added to `val_errors`. They then go through the existing retry and the existing
`[Pass 1 FAIL]` print. I reworded the opening of the check-retry prompt so that it also
says Python "looked for each line on the page it cites". Every sentence that forbids
changing a value is kept word for word.

**Route B.** `load_session_extraction` now adds the wrapper's messages to that filing's
errors, before the `where` prefix is applied. The PDF bytes come from `plan.pdf_path`. The
exit codes of `check` are unchanged. Its "Clean" sentence now also says every printed line
was found on the page it cites.

**Docs.**
- `llm-boundary.md`, "The checks": a new paragraph on the page check. The "no check could
  tell" sentence is replaced by it, with its two limits.
- `extraction.md`: a new subsection, "The page check", inside "Validation". It holds the
  rule, the outcome table, where each route runs it, the cost and the two limits.
- `extraction.md`, rest of "Validation": the route A retry paragraph now describes the
  page failures, and the sentence pointing at item 59 is gone.
- `extraction.md`, "The loader, and what stops it": a PDF that cannot be opened is added
  as a stop.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | one rule, one walk, both routes call it | **pass** | `grep -rn "def printed_line_on_page" ingestion/` gives one hit, `claude_extractor.py:876`. `grep -rn "def _printed_line_failures" ingestion/` gives one hit, `:1001`. The walk has two call sites: `:1701` in `_run_financials_pass` (route A) and `:2151` in the wrapper `printed_line_page_failures`. Route B calls that wrapper once, at `session_extraction.py:630`. The reader `_read_cited_pages` is called only from the walk (`:1025`) |
| 2 | Walmart's real file is clean | **pass** | `.venv/bin/python -m ingestion.session_extraction check extractions/WMT.json` exits 0 and prints `Printed lines looked up on their cited pages: 89 checked, 89 found, 0 not confirmed.` and the new "Clean: … and every printed line was found on the page it cites." A separate scratch count of the file's lines gives 89 lines on pages {21, 22, 23, 27} |
| 3 | an invented row that balances is caught | **pass** | Scratch `c3_invented.json` is a copy of WMT.json with `other_current_assets` set to `[{label: "Other current assets", value: 4124, page: 22}]`. `check` exits 1. The failure reads `balance sheet 2026, 'other_current_assets' line 0: 'Other current assets' = 4,124 was not found on page 22: …`. Both balance rows still read `OK` (284,668 against 284,668, +0) |
| 4 | a wrong page is caught | **pass** | Scratch `c4_wrong_page.json` keeps the real label with page 23. `check` exits 1: `… 'Prepaid expenses and other' = 4,124 was not found on page 23: …` |
| 5 | a page beyond the PDF is caught | **pass** | Scratch `c5_beyond.json` cites page 87. `check` exits 1: `… 'Prepaid expenses and other' = 4,124 cites page 87, but the PDF has 86 pages. …` |
| 6 | the rule, by hand | **pass, 6 of 6** | Scratch `c6_c9.py` calls `printed_line_on_page` on the assignment's six cases. Each returns the expected value: True, False, True, True, True, False |
| 7 | route A's retry names the row, never an amount | **pass** | Scratch `c7_c8.py` stubs `_call_llm` to return the criterion 3 JSON every time, and passes the real Walmart 2026 PDF bytes. The retry names `'Other current assets'`, `other_current_assets` and `page 22`. Outside the JSON, none of `4,124`, `4124`, `284,668` or `284668` appears (all four tested `False`). Both retries carried the PDF bytes |
| 8 | route A keeps the figures after its last retry | **pass** | The same run makes 3 calls. The console shows `[Pass 1 FAIL] Checks still fail after 2 retries. …` followed by the page failure. A `FinancialStatements` is returned, with years [2024, 2025, 2026], balance sheet 2026, `other_current_assets` = 4124.0 and revenue 2026 = 713,163. Page 21 prints `Total revenues 713,163 680,985 648,125` |
| 9 | a PDF `pdfplumber` cannot open stops | **pass** | Stand-in bytes `b"%PDF-1.4 stand-in for tests"` through `printed_line_page_failures` raise `ValueError: the PDF sha256 f323a2c6d3ab7975… (27 bytes) cannot be opened by pdfplumber (PdfminerException: No /Root object! …)`. Its `__cause__` is `pdfplumber.utils.exceptions.PdfminerException`. `git diff -U0 ingestion \| grep "^+.*except"` shows one new handler, `except (PdfminerException, MalformedPDFException)`. Ruff `BLE001` stays at 5 |
| 10 | the gates do not regress | **pass** | ruff: 5 errors, all `BLE001`, the same 5 sites as before. mypy: `Found 10 errors in 4 files`, and the error set (line numbers removed) diffs identical against the stashed baseline. Census: 67 |
| 11 | the red list | **pass** | 24 tests are red, listed below. Each fails on the stand-in PDF. As a control, I replaced the walk with `lambda data, pdf_bytes: []` through a scratch pytest plugin, and the same gate run gave **626 passed**. No test fails on a reworded message |

### Criterion 11: the 24 red tests (gate form, `--ignore-glob="*_rule3_red.py"`)

Before the change: 626 passed. After: **24 failed, 602 passed**. Every one fails because
its session file or route A runner hands `pdfplumber` stand-in bytes (`%PDF-1.4 stand-in
…`, 34, 48 or 49 bytes). `pdfplumber` raises `PdfminerException`, and the page check turns
it into the new `ValueError`. Each test's own failure line is below.

| Test | How the stand-in PDF surfaces |
|---|---|
| `test_pass1_printed_lines.py::test_a_field_of_two_rows_is_their_sum_by_route_b` | `ValueError: the PDF sha256 b5fd… cannot be opened by pdfplumber` from the loader |
| `…::test_the_shape_retry_sends_the_pdf` | `run_route_a` catches that ValueError as the outcome, so `'ValueError' object has no attribute 'get_cash_flow'` |
| `…::test_the_check_retry_sends_the_pdf` | the ValueError on the first parse stops before the retry: `assert 1 == 2` calls |
| `…::test_the_json_repair_retry_does_not_send_the_pdf` | the outcome is the ValueError, not `FinancialStatements` |
| `…::test_the_balance_check_retry_states_no_gap_and_no_total` | no retry is made, so `calls[1]` raises `IndexError` |
| `…::test_the_income_statement_check_retry_states_no_gap_and_no_total` | same, `IndexError` |
| `…::test_after_the_last_retry_a_failed_check_is_kept` | stops after call 1: `assert 1 == 3` |
| `…::test_the_cli_session_route_shows_a_failed_check_and_keeps_the_figures` | `SystemExit: ERROR: the PDF sha256 b5fd… cannot be opened by pdfplumber` (`cli.py:918`) |
| `test_routes_session.py::test_upload_then_follow_the_redirect_reaches_the_assumptions_page_with_the_label` | the page shows the error `the PDF sha256 b5fd… cannot be opened…` where `None` was expected |
| `…::test_assumptions_from_a_session_file_shows_the_label_and_the_files_identity` | same |
| `…::test_assumptions_with_a_ticker_that_differs_from_the_file_stops_naming_both` | it stops on the PDF before the ticker mismatch, so `'OTHER'` is not in the message |
| `…::test_assumptions_with_a_company_name_that_differs_from_the_file_stops_naming_both` | same, `'Other Corp'` |
| `…::test_valuation_with_a_ticker_that_differs_from_the_file_stops_before_pricing` | same, `'OTHER'` |
| `…::test_valuation_on_a_cache_hit_shows_the_session_label` | the PDF error where `None` was expected |
| `…::test_valuation_on_a_cache_miss_shows_the_session_label` | same |
| `…::test_route_a_label_survives_removing_the_key_on_a_cache_hit` | same |
| `test_session_extraction.py::test_one_filing_both_routes_give_equal_statements_and_items` | `ValueError: the PDF sha256 d676… (34 bytes) cannot be opened…` |
| `…::test_three_filings_both_routes_give_equal_statements_and_items` | same, `b19c…` |
| `…::test_a_changed_figure_makes_the_routes_differ` | same |
| `…::test_explicit_zero_is_accepted` | same |
| `…::test_pass2_item_amount_zero_loads` | same |
| `…::test_session_label_names_the_session_route_and_the_declared_model` | same |
| `…::test_check_exit_codes` | `cmd_check` returns 2 (stopped) where 0 was expected |
| `…::test_main_check_and_a_bad_page_range` | `main(['check', …])` returns 2 where 0 was expected |

**Outside the gate, one red-on-purpose test changed its reason.**
`tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`
used to fail at line 74 ("a session_file sent with files was valued, files ignored"),
which is the defect it records. It now fails at line 63, in its setup, because the
`/assumptions` call stops on the stand-in PDF. It no longer reaches the assertion it
exists for until its fixture is a real PDF. The other one,
`test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`,
is unchanged. Both were measured before (`git stash`) and after.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The unopenable PDF is named by sha256 prefix and byte size, not by file name | Route A's `_run_financials_pass(pdf_bytes, …)` holds only bytes. Route B's session file records the same `pdf_sha256` beside `pdf_path`, and `check` prints `sha256 23920728ddd7eed2…` the same way | Adding a `pdf_name` parameter to `_run_financials_pass` would change a signature the tests call, and would add a non-PDF reason to criterion 11's red list. A defaulted name would be a silent default (rule 3) |
| Catch `(PdfminerException, MalformedPDFException)` from `pdfplumber.utils.exceptions` | `pdfplumber/pdf.py:51-52` wraps every exception from opening in `PdfminerException`, and `:160-161` (page listing) and `page.py:266-268` (layout for `extract_text`) do the same. `MalformedPDFException` is pdfplumber's only other exception (`page.py:167`, `utils/pdfinternals.py:80`). Stand-in bytes raise `PdfminerException` (measured) | Backlog item 8 forbids a broad `except`. Both classes are pdfplumber's own and both mean "this PDF cannot be read" |
| The walk takes `pdf_bytes` and calls the reader. The rule (`printed_line_on_page`) and the per-line decision (`_printed_line_failure`, which takes the page count and page texts) are pure | The assignment: "Keep [the reader] separate from the rule, so a test can give page texts without a PDF". One walk, called once by each route | A walk that took page texts would need each route to call the reader as well, which makes two call sequences to keep in step |
| The wrapper runs `pass1_problems` again before walking | The walk reads every key with `[]` and relies on `pass1_problems` having passed. In the loader it already has, so the repeat is a no-op there, but the public wrapper must not index a malformed answer | Leaving the guard out would let a direct caller get a `KeyError` instead of a `Pass1ShapeError` that names the field |
| Route A's walk runs after the `try` that parses, so a `ValueError` for an unopenable PDF is outside every `except` and stops the run on the first attempt | The assignment: "stop, with a ValueError naming the PDF". No retry can make an unreadable PDF readable | Putting it inside the `try` is safe today, since the excepts catch only `JSONDecodeError` and `Pass1ShapeError`, but it would be one edit away from being retried |
| The figure regex accepts comma groups only as whole groups of three (`\d{1,3}(?:,\d{3})+(?!\d)\|\d+`), and a `$` takes spaces only after itself | Rule step 1: "digits with optional thousands commas", and "an optional `$` with optional spaces" | `\s*` outside the `$` would swallow the space before a bare number. Removing figures would then join the words on either side, as in `abc 123def` → `abcdef` |
| A removed figure leaves nothing behind (`""`), not a space | Rule step 3: "Remove every figure". The same normalisation is applied to label and page, so the two are always treated alike | A space would also work, because step 3 collapses non-alphanumerics to one space. For text where a figure touches letters (`Item7A`), `""` is the literal reading |
| Substring match, not word match | Rule step 4: "is a substring of the normalised text". A tester derives cases by hand from that sentence | Word boundaries would be stricter, for example label `Debt` against `Long-term debt`. I report it as a finding and did not change the rule |
| A one-line summary is printed per walk (`Printed lines looked up on their cited pages: N checked, F found, K not confirmed.`) | Criterion 2 asks for "89 lines checked, 89 found". `_validate_extracted_data` prints its table the same way | Without it, a clean run shows no evidence that the check ran |

No code was changed to reach a target number.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| a line's `label`, `value`, `page` | `pass1_problems` stops first and names the year, field and line. The walk reads each with `[]` | `printed_line_page_failures` raises `Pass1ShapeError` before walking. In route A the walk runs only after `_parse_financials_response` has passed `pass1_problems` |
| a field's list of lines | same, `pass1_problems` | the walk reads `entry[field]` and `balance[field]` with `[]` |
| `latest_balance_sheet` = `{}` | not walked: `{}` is the answer for "balance sheet not asked for", as in `pass1_problems` and the parser | `if balance:` in `_printed_line_failures` |
| a cited page's text | the page is read for every cited page within the PDF. A page beyond the PDF is a failure that names the page count. `None` or whitespace-only text is a failure saying "cannot be confirmed", **never a pass** | `_printed_line_failure` reads `page_texts[page]` with `[]`. The scratch `notext.py` run gives page 2 (empty) as "cannot be confirmed … not confirmed" and page 3 of 2 as "cites page 3, but the PDF has 2 pages" |
| the PDF itself | stops with `ValueError` naming it by sha256 and size | criterion 9 |
| a normalised label that is empty | not found, so a failed check | `if not wanted: return False` |

No "defaults to" row. The census is unchanged at 67.

## Measurements

### Baseline at 0839ad9 (before any edit)

| Gate | Command | Result |
|---|---|---|
| tests | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py" -p no:cacheprovider` | 626 passed, 0 failed |
| lint | `.venv/bin/python -m ruff check .` | 5 errors, all `BLE001` |
| types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 10 errors in 4 files |
| census | the grep at `docs/2-rules/rules.md:65`, with `'--include=*.py'` quoted | 67 |

### The assignment's fact table, re-measured: all agree

| Fact | Measured |
|---|---|
| WMT.json | one filing, `Walmart Inc._10-K_2026-01-31_English.pdf`, sha256 `23920728ddd7eed2…`; 89 printed lines; years 2026, 2025 and 2024, plus balance sheet 2026; cited pages {21, 22, 23, 27} |
| PDF pages | 86 |
| page 22 | prints `Prepaid expenses and other 4,124 4,011`; no line contains `Other current assets`; page 23 has no `4,124` |
| pdfplumber on stand-in bytes | raises `pdfplumber.utils.exceptions.PdfminerException` ("No /Root object! - Is this really a PDF?"). pdfplumber 0.11.10, pdfminer.six 20260107 |

### After, on the final tree

| Gate | Result |
|---|---|
| tests, gate form | **24 failed, 602 passed**. The set is the 24 above, identical across two runs |
| tests, gate form, with the walk replaced by `lambda data, pdf_bytes: []` (scratch plugin `no_page_check.py` via `PYTHONPATH=<scratch> … -p no_page_check`) | **626 passed** |
| lint | 5, all `BLE001`. My import order raised one `I001`, fixed with `ruff check --fix ingestion/session_extraction.py` |
| types | 10 in 4 files. The error set, line numbers stripped, `diff`s identical against the stashed baseline |
| census | 67 |

**Cost on Walmart** (scratch `cost.py`, 5 runs of `_printed_line_failures` on the real 89
lines): 0.544-0.557 s per walk. `_read_cited_pages` on pages {21, 22, 23, 27} alone takes
0.547 s. Reading the pages is the whole cost. `check extractions/WMT.json` takes 0.64 s
wall clock end to end.

**The first limit, measured.** `printed_line_on_page('Prepaid expenses and other', 4011,
<page 22>)` returns True, and with 4012 it returns False. The prior year's column is
accepted, as the docs now say.

The scratch scripts are under
`/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/abfaba0a-dbfc-4078-8cbf-99abdeae9e3b/scratchpad/`:
`variants.py`, `c6_c9.py`, `c7_c8.py`, `cost.py`, `notext.py` and `no_page_check.py`.

## What I did not do

- Nothing under `tests/`. The 24 red tests, and the reason change in one `_rule3_red`
  test, wait for the tester. `tests/unit/_text_pdf.py:write_text_pdf` builds a real PDF
  that works with this check. `notext.py` used it, read-only, to drive the no-text-layer
  branch.
- `_print_pass1_tables`, `cmd_prompt`, `cli.py`, `api/`, `templates/`, Pass 2,
  `CACHE_FORMAT` and the skill file are untouched, as the assignment says.
- I did not add word-boundary matching. The rule says substring (see the findings).

## Findings for the orchestrator

1. **The rule's substring match is loose for short labels.** A label `Other` with value 0
   is found on any text line that contains `other` and a standalone dash or a 0. A label
   `Debt` is found inside `Long-term debt`. Requiring whole words, for example
   `f" {label} " in f" {text} "` after normalisation, would close this. That is a change
   to the rule, which the orchestrator owns. I did not measure it against the 16 filings.
2. **A filing with no text layer at all would waste route A's two retries.** Every line
   fails "cannot be confirmed", so route A retries twice and then shows them all. All 16
   filings under `10K_filings/` have a text layer, so this is not live today. A later unit
   could stop or skip the retry when every cited page lacks a text layer.
3. **One red-on-purpose test now fails in its setup** (see criterion 11). The tester should
   give `test_routes_session_rule3_red.py` a real PDF too, or it stops guarding its defect.
4. **`_read_cited_pages` builds every page object to get the page count**
   (`len(pdf.pages)`). On Walmart's 86 pages this is inside the 0.55 s. A 300-page filing
   may cost more. That has not been measured.
