---
agent: programmer
assignment: P3b-pipeline-stops
round: 2
status: complete
files_touched: [ingestion/filings.py, pipeline.py]
---

# P3b-pipeline-stops round 2 — every remedy in the stop message is true for the reader who meets it; two comments stop quoting the conditional zero

Round 1 entry: `.agent/journal/2026-10-05T1548-programmer-p3b-pipeline-stops.md`
Review: `.agent/journal/2026-10-05T1625-code_reviewer-p3b-pipeline-stops.md` (verdict
`approved`, five findings, none blocking).

## What I did

Two changes, both answering a finding by number, and nothing else. **F1**:
`require_fiscal_year_per_filing`'s message told every reader "or rename the file so the
year after '10-K' in its name is that year", which is false on the command line — a bare
path is year 0 and `parse_pdf_args` never reads the file name for a year
(`ingestion/filings.py`, the loop at `:522-530`; only `discover_filings` and the web
upload read a name). The message now states the condition first and names which remedy
belongs to which entry point: on the command line, `YEAR:PATH`, and in so many words that
renaming changes nothing there; on the web upload page, rename and upload again, which is
that page's only way to supply a year. A docstring paragraph records where each entry
point's year comes from, with the file that proves it. I did **not** add a `Remedy`
parameter: see the decision table. **F4**: `pipeline.py:83` and `:176` quoted
`latest_bs.total_debt if latest_bs else 0` in prose; both now describe the deleted line in
words, so the repository-wide grep for the conditional-zero pattern no longer lands on a
`pipeline.py` comment and round 1's decision row ("the comments describe the deleted lines
instead of quoting them") is true of all three comments.

**No behaviour changed.** The stop fires on exactly the same inputs as in round 1, at the
same place, before any PDF is opened; only the words differ. No valuation arithmetic was
touched: no figure in `pipeline.py` moved, only two comments.

## Findings answered, by number

| # | Severity | Answer |
|---|---|---|
| F1 | minor | **Fixed.** `ingestion/filings.py:386-403`, with the facts recorded in the docstring at `:360-375`. Each remedy now names its entry point and is true there; the command-line remedy says outright that renaming the file changes nothing. Criterion 18 measures it with the two real ABBV PDFs. I accept the finding; no dispute |
| F2 | minor | **Not mine to fix, and already recorded.** The amendment says F2 is backlog item 95, and `docs/9-reference/refactor-backlog.md:130` carries it (written by the lead). `ingestion/session_extraction.py` is out of scope. For the record I accept the review's point that round 1 should have reported `cmd_plan`'s now-unreachable check under "Found"; it did not |
| F3 | note | **Left as it is, by the amendment**, which names only F1 and F4 for round 2 and says "nothing else in this assignment changes". The note is accurate: `parse_pdf_args`' folder branch returns at `:517-520` before `require_fiscal_year_per_filing` runs at `:531`, and a folder is covered by `discover_filings`' own stop on a yearless file name. The new docstring paragraph I wrote for F1 now states that fact in the function itself ("a folder never reaches this stop"), which is part of what F3 asked for, but I did not touch the `cli.py` comment F3 quotes |
| F4 | note | **Fixed**, by the first of the two options the amendment offers: `pipeline.py` stops quoting the expression. `grep -rnE "if [^)]+ else 0(\.0)?\b" pipeline.py` → no match, `rc=1`. Round 1's decision row therefore stands as written |
| F5 | note | **Left as it is.** The amendment records it as backlog item 96 if still true; it is still true — `ValuationRun.latest_balance_sheet` is read by no production code. Deleting the field would also need `tests/unit/test_pipeline.py:298`, which is out of scope |

## Done-criteria

Every command run from the repository root with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Criteria 1 to 17 were all re-run this round, against the live
post-`P1b` baseline (`0a8ea54`): gate form 1107 passed / 5 skipped / 0 failed, full suite
2 failed (the two red-on-purpose).

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Several filings, one with no year, stop and name it | **pass** | `-c "from ingestion.filings import require_fiscal_year_per_filing as r; r([(0,'a.pdf'),(2025,'b.pdf')])"` → `ValueError: 1 of 2 filings have no fiscal year:` / `  - a.pdf (given as 'a.pdf')` |
| 2 | Every yearless filing is named, not only the first | **pass** | same with `[(0,'a.pdf'),(2025,'b.pdf'),(0,'c.pdf')]` → `2 of 3 filings have no fiscal year:` then `  - a.pdf …` and `  - c.pdf …` |
| 3 | One bare path is still allowed | **pass** | `r([(0,'a.pdf')])` returns; printed `C3 ok` |
| 4 | Several filings, every one with a year, are allowed | **pass** | `r([(2024,'a.pdf'),(2025,'b.pdf')])` returns; printed `C4 ok` |
| 5 | The CLI stops, names both files, and opens no PDF | **pass** | `cli.py a.pdf b.pdf -t TESTCO` → `ERROR: 2 of 2 filings have no fiscal year:` naming both, `exit=1`. Strong form `c:/tmp/p3b_r2_c18.py`, with the two **real** ABBV 10-K PDFs as bare paths and `builtins.open`, `cli.extract_financials`, `cli.extract_multi_year` replaced by recorders: `PDFs opened: []`, `extractor calls: []`, `both real file names in the message: True` |
| 6 | The CLI still accepts one bare path | **pass** | `cli.py a.pdf -t TESTCO` → `ERROR: extraction input 'a.pdf' is not a readable file, so its content cannot be fingerprinted and no cache decision can be made about it`, `exit=1` — past `parse_pdf_args`, stopped inside the cache key as in round 1 |
| 7 | The web route stops and names the file, with no extraction | **pass** | `c:/tmp/p3b_r2_c7_c8.py`: `_run_extraction(files='0:a.pdf,2025:b.pdf', file_path='', session_file='', ticker='T', company_name='T')` → `ValueError: 1 of 2 filings have no fiscal year: / - a.pdf …`; with both extractors replaced by recorders, `extractor calls: []` |
| 8 | The message reaches the page | **pass** | same script: `GET /assumptions?ticker=T&files=0:a.pdf,2025:b.pdf` → `200`, body holds `<div class="alert alert-error">1 of 2 filings have no fiscal year: - a.pdf (given as &#39;a.pdf&#39;)…` with both remedy bullets; `'a.pdf' in body: True`. `POST /valuation` → `200`, `<strong>Error:</strong> 1 of 2 filings…`; `extractor calls: []` |
| 9 | Neither entry point filters any more | **pass** | `grep -n "valid = " cli.py api/routes_valuation.py` → no match, `rc=1` |
| 10 | The CLI's conditional zero is gone | **pass** | `grep -n "latest_bs.total_debt if latest_bs" cli.py` → `rc=1`; `grep -n "latest_bs" cli.py` → `rc=1`, the local is gone too |
| 11 | The CLI prints the pipeline's figure | **pass** | `grep -n "run.total_debt" cli.py` → exactly 1: `1058:    print_wacc(wacc_result, run.market_cap, run.total_debt)` |
| 12 | A valuation with no balance sheet for the latest year stops, names the field, and makes no market call | **pass** | `c:/tmp/p3b_r2_c12_c16.py`: `ValueError: balance_sheet is None for 'TST' in fiscal year 2024, the latest year: … The debt balance is not set to 0: a missing balance sheet is not a debt-free company.`; `'balance_sheet' …: True`, `'TST': True`, `'2024': True`, `'not set to 0': True`; `fetch_price_data calls: []` with the recorder installed. Twin with a balance sheet does reach it: `fetch_price_data calls now: [('TST', ('lookback_years', 3), ('frequency', 'daily'))]`, so the stop is the balance sheet's |
| 13 | Types | **pass on the count; 5 errors in 2 files, not 3** | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → `Found 5 errors in 2 files (checked 21 source files)`: `analysis/projector.py` ×4, `api/routes_upload.py:28` ×1. Unchanged from round 1; the reviewer confirmed the "3 files" in the criterion is the assignment's stale figure, because `api/routes_valuation.py` held exactly one of the baseline 6 |
| 14 | Lint | **pass** — 4 errors, every one `BLE001` | `-m ruff check . --output-format concise` → `api/routes_valuation.py:451`, `:709`, `cli.py:1139`, `tests/test_e2e_all_googl.py:106`; `Found 4 errors.` |
| 15 | Census | **pass** — 64 | the grep at `docs/2-rules/rules.md:102` → `64` |
| 16 | Route | **pass** — 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` → `GET / status: 200` |
| 17 | No test fails that did not fail before, by name | **pass** | gate form `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly` → **1107 passed, 5 skipped, 0 failed** in 123.26s, failing set = {}. Full suite `-m pytest -q -p no:randomly` → **2 failed, 1107 passed, 5 skipped**, the two names being `test_projector_rule3_red::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`. Both sets are exactly the lead's post-`P1b` baseline; no name added, none removed |
| 18 | Every remedy the stop message states is true for the entry point that reaches it | **pass** | `c:/tmp/p3b_r2_c18.py`, the two real ABBV PDFs as bare paths. See the table below |

### Criterion 18 in full

Command: `.venv/Scripts/python.exe c:/tmp/p3b_r2_c18.py`, which runs
`cli.py "10K_filings/ABBV/AbbVie Inc._10-K_2025-12-31_English.pdf" "10K_filings/ABBV/AbbVie Inc._10-K_2024-12-31_English.pdf" -t ABBV`
in process, with `builtins.open` and both extractors recorded. The message, as the reader
sees it (`SystemExit` carries it, so the shell prints it to stderr):

```
ERROR: 2 of 2 filings have no fiscal year:
  - AbbVie Inc._10-K_2025-12-31_English.pdf (given as '…\AbbVie Inc._10-K_2025-12-31_English.pdf')
  - AbbVie Inc._10-K_2024-12-31_English.pdf (given as '…\AbbVie Inc._10-K_2024-12-31_English.pdf')
With more than one filing every filing needs its fiscal year, because the plan routes
years by it. What to do depends on where the filings were given:
  - on the command line: give each filing as YEAR:PATH, with the fiscal year that filing
    covers. A path given on its own counts as no year whatever the file is called, so
    renaming it changes nothing here; a file name is read for a year only when a ticker
    folder is the single argument.
  - on the web upload page: rename the file so its name carries the fiscal year after the
    '10-K' marker, and upload it again. That page takes each year from the file name and
    offers no way to type one.
No year is guessed here: the year a filing covers is checked against its content before
anything is extracted (verify_filing_years). Nothing was extracted.
```

(The two bullets are one line each in the message; wrapped here to fit.)

| What the criterion asks | Measured |
|---|---|
| the message is shown to a reader whose files already carry their years | `both real file names in the message: True`; `PDFs opened: []`, `extractor calls: []`, exit 1 |
| the message does **not** tell that reader to rename those files | the command-line remedy contains no instruction to rename — the only occurrence of the stem in it is `so renaming it changes nothing here`. `every 'rename' in the message is inside the web-upload remedy: True` |
| every remedy names its entry point, condition first | `exactly one remedy for the command line: True`, `exactly one remedy for the web upload: True`, `every remedy states its entry point first: True` (every `  - ` line that is not a file name begins `- on …`) |
| the command-line remedy is true | `parse_pdf_args(['2025:<ABBV 2025 pdf>', '2024:<ABBV 2024 pdf>'], 'ABBV')` returns years `[2025, 2024]` — and that call runs `verify_filing_years`, so both years were confirmed against the two real PDFs' content |
| the web-upload remedy is true | `api.routes_upload._guess_fiscal_year('AbbVie Inc._10-K_2025-12-31_English.pdf')` → `2025`, so a name that carries its year never reaches this stop from that page; `_guess_fiscal_year('filing.pdf')` → `None`, the year-0 case that does |
| the folder path is not promised anything | it cannot reach this stop: `parse_pdf_args` returns `discover_filings(...)` at `ingestion/filings.py:517-520`, before the call at `:531`, and `discover_filings` stops on a yearless file name with its own message (`:481-487`). The message mentions a ticker folder only to say where a file name *is* read for a year |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| One message that names which remedy belongs to which entry point, rather than a `Remedy` parameter | The amendment: "it must name which remedy belongs where, or drop the remedy that is not universal. Do not add a parameter that makes the message differ by caller unless you can state why that is better than one true message." I cannot state that, so I did not add one | A parameter would also change the signature the assignment fixes in step 1, and round 2 "changes nothing else". It would additionally put the choice on each caller, and the caller that most needs the stop — the web `files` string — can be reached from a hand-typed URL as well as from the upload page, so a per-caller message would be a guess about who is reading |
| Keeping the rename remedy, conditioned, rather than dropping it | Dropping it would leave the web-upload reader with the one remedy that is false for them: that page has no field for a year, so `YEAR:PATH` is unreachable there (`templates/upload.html`, `api/routes_upload.py` `upload_files` takes `pdf_files` only) | A message with no remedy for one of its two readers is the same defect as F1 with the sides swapped |
| The command-line remedy says outright that renaming changes nothing | F1's cost is a reader who renames two files, re-runs, and meets the same stop. Naming the true remedy alone would leave the rename bullet visible one line below, and a reader on the CLI would still try it | Silence about renaming is cheaper to write and leaves exactly the failure mode F1 reports |
| Still no example year anywhere in the message | Round 1's decision, unchanged: the code does not know the filing's year, and a worked example such as `2025:a.pdf` reads as a suggested year. The web bullet says "the fiscal year after the '10-K' marker", which is the rule `fiscal_year_from_filename` applies, with no year in it | An example file name (`TICKER_10-K_2024-12-31.pdf`, the shape `discover_filings` prints) would be friendlier but names a year the code has not read |
| A docstring paragraph recording where each entry point's year comes from | The finding was that a remedy was false, and nothing in the function said which entry points reach it. The citation lives next to the words it governs so the next change to the message is checkable | A comment at the `raise` would be read later than the docstring, and the facts are about the function as a whole |
| `pipeline.py`'s two comments describe the deleted expression instead of quoting it | F4, first option. Round 1's own decision row already claims the comments describe rather than quote; making it true everywhere is cheaper than carrying an exception, and a repository-wide grep for the rule 3 pattern should not land on prose | Correcting the decision row instead would leave two `pipeline.py` hits that every future guard grep must be re-told to ignore |

**No change in this unit was made to reach a target number.** Round 2 changed one error
message and two comments; no figure is produced by either.

## Rule 3 — what stops, and what does not

Round 2 added no new value read. The table is round 1's, re-measured this round; the first
two rows are the ones whose words changed.

| Value read | If it were missing | Evidence |
|---|---|---|
| `filings` entry's fiscal year, with more than one filing (CLI) | **stops** and names every yearless file, with the remedy that works on the command line | `cli.py a.pdf b.pdf -t TESTCO` → `ERROR: 2 of 2 filings have no fiscal year:` + both names, exit 1; criterion 18 with two real PDFs, `PDFs opened: []` |
| `filings` entry's fiscal year, with more than one filing (web `files`) | **stops** and names every yearless file, with the remedy that works on the upload page | `_run_extraction(files='0:a.pdf,2025:b.pdf', …)` → `ValueError … - a.pdf`; rendered at 200 on both pages; `extractor calls: []` |
| `filings` entry's fiscal year, with exactly one filing | **allowed, by design**: 0 means "every year this filing presents" (`ingestion/filings.py:342-344`) | `r([(0,'a.pdf')])` returns |
| latest fiscal year's balance sheet (`pipeline.value_company`) | **stops**, naming `balance_sheet`, the ticker and the year, before any market call | criterion 12: `fetch_price_data calls: []`, and the twin reaches the recorder |
| `run.total_debt`, printed by CLI stage 8 | cannot be missing: the field is required, set from `latest_bs.total_debt` after the stop | `pipeline.py:95, 194, 238`; `grep -n "latest_bs" cli.py` → no match |
| debt lines inside the balance sheet | **stops**, in `calculate_wacc`, untouched by this unit | `analysis/wacc.py:82-134` |

No row of this table reads "defaults to".

## Measurements

| Gate | Round 1 end (reviewer's figures) | Round 2 end |
|---|---|---|
| suite, gate form (`--ignore-glob="*_rule3_red.py"`) | 1107 passed, 5 skipped, **0 failed** | **1107 passed, 5 skipped, 0 failed** in 123.26s |
| suite, full | 2 failed (both `_rule3_red`, red on purpose), 1107 passed, 5 skipped | **2 failed, 1107 passed, 5 skipped** — the same two names |
| types | 5 errors in 2 files | **5 errors in 2 files** |
| lint | 4 errors, all `BLE001` | **4 errors, all `BLE001`** |
| census (grep at `rules.md:102`) | 64 | **64** |
| route `GET /` | 200 | **200** |
| write guard | 48/48 | **48/48** (`.claude/check_guard.py`) |
| `grep -rnE "if [^)]+ else 0(\.0)?\b" pipeline.py` | 2 hits, both comments (F4) | **no match, `rc=1`** |

Failing-name sets: gate form before = {} , after = {}; full form before = after =
{`test_projector_rule3_red::test_an_extraction_with_no_income_statements_stops_and_names_the_input`,
`test_routes_session_rule3_red::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`}.
No name was added or removed.

**No figure moved this round, and none was produced.** The only valuation figure this unit
ever produced is round 1's `run.total_debt` identity on Walmart's page 22 balance sheet
rows (51,523, equal to the hand sum and to the balance `calculate_wacc` weighted the
capital with); round 2 touched no arithmetic, and the gate counts above are unmoved.

## What I did not do

- **No tests.** `tests/` is out of scope and denied by the write guard.
  `.agent/assignments/P3b-pipeline-stops-tests.md` appeared in the tree during this run;
  I read it only far enough to confirm it does not pin the message's remedy wording (it
  asserts on the count of named files, the file name in the body, and the
  `balance_sheet`/ticker/year words), so round 2's rewording does not invalidate it.
- **F2, F3, F5 not acted on**, per the amendment: F2 is backlog item 95 and lives in an
  out-of-scope file, F3 is a note the amendment did not assign to round 2, F5 is backlog
  item 96 and needs a `tests/` edit.
- **`api/routes_upload.py`, `ingestion/session_extraction.py`, `analysis/wacc.py`,
  `templates/` untouched**, as in round 1.
- **Items 5, 8, 26, 82, 87-92 left alone**, though each sits in a file I touched.
- `ingestion/claude_extractor.py`, `cli.py` and `api/routes_valuation.py` were **not
  edited this round**: round 1's changes to them stand unmodified.

## Findings for the orchestrator

1. **The new multi-line stop message collapses to one paragraph on two of the three
   pages.** `templates/upload.html:11` renders its error inside
   `style="white-space: pre-line"`, but `templates/assumptions.html:10` and
   `templates/valuation_result.html:10` do not, so on `GET /assumptions` and
   `POST /valuation` the file list and the two remedy bullets run together into a single
   wrapped line. Criterion 8 only asks for the file name in the body, and it is there; this
   is readability, and it was already true of round 1's message and of any other multi-line
   `ValueError` these pages render (`verify_filing_years`' mismatch message is the other
   one). Fix: the same `white-space: pre-line` on those two blocks. `templates/` is outside
   this unit's scope.
2. Round 1's finding 1 stands and is not yet in the backlog as far as I can see:
   `api/routes_valuation._parse_files_param` stops with a bare
   `ValueError: invalid literal for int() with base 10: 'a.pdf'`, which names neither the
   field nor the file, and that message reaches the page. Adjacent to item 26.
3. Round 1's findings 2 and 3 were answered by the lead and the reviewer (the criterion 13
   expectation should read **5 errors in 2 files**; the assignment's 14-failed baseline is
   stale). Nothing further from me.
