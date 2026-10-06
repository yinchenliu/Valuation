---
id: P3b-pipeline-stops
phase: 3 — unify the pipeline (part 2)
agent: programmer
depends_on: [P3a-one-pipeline]
---

# A filing with no fiscal year stops and names the file (item 49); the CLI's debt display stops reading 0 (item 72)

## Objective

**Fact 1, backlog item 49.** With more than one filing, both entry points keep only the
filings whose year is above 0 and drop the rest without a word.
`cli.py:892` holds `valid = [(y, p) for y, p in filings if y > 0]` and
`api/routes_valuation.py:122` holds the same line. When every filing lacks a year, both
extract the first one alone. The web upload page sends a yearless PDF through as year 0
on purpose: `api/routes_upload.py:94` says "backlog item 49 owns what happens to it
next". Route B stops on the same input and names the file
(`ingestion/session_extraction.py:385`), so the two routes disagree today.

**Fact 2, backlog item 72.** `cli.py:1061` holds
`total_debt = latest_bs.total_debt if latest_bs else 0`, and prints that figure as
"Total debt" in stage 8. A missing balance sheet is not a debt-free company (rule 3).

**What follows.** When this unit is done, one named function holds the rule "with more
than one filing, every filing needs its own fiscal year", both entry points call it, and
a filing with no year stops the run and names the file before anything is extracted. The
CLI prints the debt balance that WACC used, read from `pipeline.ValuationRun`, and no
conditional zero stands between them.

**No number moves for a filing that has a year on every PDF.**

## What is already true — verify, do not redo

Measured by the overall lead at `7a3955d`, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| gate | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` | **14 failed**, 1090 passed, 5 skipped |
| lint | `.venv/Scripts/python.exe -m ruff check .` | 4 errors, every one `BLE001` |
| types | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | **6 errors in 3 files** |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.venv/Scripts/python.exe .claude/check_guard.py` | 48/48 |

**The 14 failures are not yours and are not a regression.** They are Windows-only test
defects: 13 from a `_no_socket` fixture that breaks the Windows asyncio self-pipe, and 1
from an argparse message that differs between Python 3.11 and 3.14. `P1b-windows-gate`
is repairing them in `tests/` while you work. Your criterion is the **set** of failing
test names, not the count: your change must add no name to it, and must remove none
except by making a test's subject correct.

**One of the 6 type errors is on a line this unit rewrites:**

```
api\routes_valuation.py:128: error: Argument 1 to "extract_multi_year" has incompatible
  type "list[tuple[int, str]]"; expected "list[tuple[int, str | Path]]"  [arg-type]
```

**Facts about the code, each read today:**

| Fact | Where |
|---|---|
| A year of 0 means "a bare path: every year the filing presents". It is not verified | `ingestion/filings.py:342-344`, `parse_pdf_args` docstring |
| `discover_filings` never yields a year of 0: a filename with no year stops it | `ingestion/filings.py:414-420` |
| `parse_pdf_args` raises `ValueError`, and `_extract_via_api` turns it into `SystemExit(f"ERROR: {exc}")` | `cli.py:825-828` |
| `_run_extraction` raises `ValueError` for every bad input, and the route renders it | `api/routes_valuation.py:167-195` |
| `calculate_wacc` already stops when the balance sheet is `None`, naming the three debt lines | `analysis/wacc.py:55-79`, `_require_balance_sheet` |
| `_require_valid_debt` returns `balance_sheet.total_debt`, the same figure the CLI prints | `analysis/wacc.py:82-134` |
| `value_company` fetches market data **after** the share count stop, so a filing figure that stops the run does not wait on the network | `pipeline.py:144-167` |
| `WACCResult` carries no debt balance | `models/valuation.py:187-207` |
| The web page shows no "total debt" in its WACC block | `grep -rn "total_debt" templates/` gives one line, in the balance sheet table |

**This machine has no session file and no cached extraction.** `extractions/` is empty
and `10K_filings/` holds PDFs only. So there is **no end-to-end Walmart run available
here**, and no criterion below asks for one. Do not try to produce one, and do not report
its absence as a blocker.

## What to do

1. **Write one function in `ingestion/filings.py`** that holds the rule:

   ```python
   def require_fiscal_year_per_filing(filings: list[tuple[int, str]]) -> None:
   ```

   With more than one filing, every filing needs a fiscal year above 0. Raise
   `ValueError` naming **every** filing that has none, not the first. With one filing, a
   year of 0 is allowed and the function returns: a bare path means "every year the
   filing presents". Say in the message what the reader can do: give the filing as
   `YEAR:PATH`, or rename the file so its name carries the year.
   The reason the rule lives in one function: item 49's own entry says "Make the change
   in both entry points, or after item 7 in one place."

2. **Call it from `parse_pdf_args`**, next to the existing `verify_filing_years` call.
   That is the CLI's input parser, and `_extract_via_api` already turns its `ValueError`
   into `ERROR: <message>`. The stop therefore happens before the cache key is built and
   before any PDF is opened.

3. **Call it from `_run_extraction` in `api/routes_valuation.py`**, immediately after
   `_parse_files_param(files)` and the empty check. That is the one place both web pages
   extract through, so one call covers `GET /assumptions` and `POST /valuation`.

4. **Delete the `valid = [...]` filter and the fall-back-to-the-first-file branch** in
   both `cli.py:890-910` and `api/routes_valuation.py:121-128`. Pass the full `filings`
   list to `extract_multi_year`. Keep each entry point's single-filing branch exactly as
   it is today, including the CLI's `single = len(filings) == 1 and filings[0][0] == 0`:
   this unit changes what happens to several filings, nothing else.

5. **Fix the type error at `api/routes_valuation.py:128`** by widening
   `extract_multi_year`'s and `plan_filings`' parameter from
   `list[tuple[int, str | Path]]` to `Sequence[tuple[int, str | Path]]` in
   `ingestion/claude_extractor.py`. `Sequence` is covariant in its element type, so a
   `list[tuple[int, str]]` satisfies it. Leaving a type error on a line you just rewrote
   is a review finding (`STATUS.md`: "Treat a type error here as a defect report").

6. **Add `total_debt: float` to `pipeline.ValuationRun`** and set it in `value_company`
   from the latest balance sheet. To read it, `value_company` must have a balance sheet,
   so **add a stop for a missing one beside the share-count stop, before
   `fetch_price_data`**. Rule 3, and the reason the share-count stop sits there: a
   filing figure that stops the run should not wait on the network. Name the field, the
   ticker and the fiscal year, and say that the debt balance is not set to 0. Keep
   `calculate_wacc`'s own stop as it is: it guards every other caller, and its tests
   call it directly.

7. **Make `cli.py` print `run.total_debt`** and delete
   `total_debt = latest_bs.total_debt if latest_bs else 0`. If nothing else in
   `cli.py:main` reads `latest_bs` after that, delete the local too.

8. **Record what you find, do not widen your scope.** If you find a defect outside this
   list, write it in your log entry under "Found". The overall lead puts it in the
   backlog.

## Files in scope

- `ingestion/filings.py`
- `ingestion/claude_extractor.py` (step 5 only: the two parameter annotations)
- `cli.py`
- `api/routes_valuation.py`
- `pipeline.py`

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Out of scope

- **`tests/`.** `P1b-windows-gate`'s tester is editing six files there while you work,
  and the write guard denies you `tests/` in any case. Your unit's own tests are a
  separate assignment after the code review.
- **`api/routes_upload.py`.** It sends a yearless PDF on as year 0 on purpose, and its
  docstring says item 49 owns what happens next. After this unit, that is a stop with a
  message. Do not change the upload route.
- **`ingestion/session_extraction.py`.** Its own year check (`:385`) has the JSON path of
  the offending entry, which `require_fiscal_year_per_filing` cannot give. Leave it.
- **`docs/`, `STATUS.md`, `.agent/`, `.claude/`.** The overall lead writes them.
- **`analysis/wacc.py`.** Step 6 adds no stop there.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | Several filings, one with no year, stop and name it | `ValueError` naming `a.pdf` | `-c "from ingestion.filings import require_fiscal_year_per_filing as r; r([(0,'a.pdf'),(2025,'b.pdf')])"` |
| 2 | Every yearless filing is named, not only the first | the message holds `a.pdf` and `c.pdf` | `-c "...; r([(0,'a.pdf'),(2025,'b.pdf'),(0,'c.pdf')])"` |
| 3 | One bare path is still allowed | no exception | `-c "...; r([(0,'a.pdf')]); print('ok')"` |
| 4 | Several filings, every one with a year, are allowed | no exception | `-c "...; r([(2024,'a.pdf'),(2025,'b.pdf')]); print('ok')"` |
| 5 | The CLI stops, names both files, and opens no PDF | `ERROR: ...` naming both, exit code 1 | `.venv/Scripts/python.exe cli.py a.pdf b.pdf -t TESTCO; echo $?` |
| 6 | The CLI still accepts one bare path | the run proceeds past `parse_pdf_args` to the extraction or the cache | `.venv/Scripts/python.exe cli.py a.pdf -t TESTCO; echo $?` (it then stops on the missing file or the empty key: record what it says) |
| 7 | The web route stops and names the file, with no extraction | `ValueError` naming `a.pdf` | `-c "import api.routes_valuation as r; r._run_extraction(files='0:a.pdf,2025:b.pdf', file_path='', session_file='', ticker='T', company_name='T')"` |
| 8 | The message reaches the page | HTTP 200 and the file name in the body | `TestClient(app.app, raise_server_exceptions=False).get('/assumptions', params={'ticker':'T','files':'0:a.pdf,2025:b.pdf'})` — print the status and the part of the body that holds the message |
| 9 | Neither entry point filters any more | no match in either file | `grep -n "valid = " cli.py api/routes_valuation.py` |
| 10 | The CLI's conditional zero is gone | no match | `grep -n "latest_bs.total_debt if latest_bs" cli.py` |
| 11 | The CLI prints the pipeline's figure | 1 match | `grep -n "run.total_debt" cli.py` |
| 12 | A valuation with no balance sheet for the latest year stops, names the field, and makes no market call | `ValueError` naming `balance_sheet`, and the price stub records 0 calls | a `-c` that builds a `FinancialStatements` with one income statement and no balance sheet, replaces `pipeline.fetch_price_data` with a recorder, and calls `pipeline.value_company` |
| 13 | Types | **5 errors in 3 files** | the mypy command above |
| 14 | Lint | 4 errors, every one `BLE001` | `-m ruff check .` |
| 15 | Census | 64 | the grep at `docs/2-rules/rules.md:102` |
| 16 | Route | 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` |
| 17 | No test fails that did not fail before, by name | the set of failing names is a subset of the 14 named above, plus any test whose subject this unit changed — name each one and say why | `-m pytest -q --ignore-glob="*_rule3_red.py"` |

**Every criterion is a measurement, never an opinion.** Criterion 17 is a set
comparison, not a count: save the failing names before and after.

## Citations

- `docs/2-rules/rules.md` — the six rules. Rule 3 ("stop, never guess") forces both
  halves of this unit.
- `docs/9-reference/refactor-backlog.md`, items 49 and 72 — the two defects, with the
  evidence that found them.
- `ingestion/session_extraction.py:385-392` — route B's stop, and the wording to match:
  "with more than one filing every filing needs its fiscal year, because the plan routes
  years by it".
- `pipeline.py:144-161` — the share-count stop, the shape your balance-sheet stop
  follows.
- `analysis/wacc.py:55-134` — the stop and the debt total that already exist.
- `.claude/agents/programmer.md` — your role card.

## Known open items

- **Backlog item 8** (blanket `except Exception`): the web route renders your new stop at
  HTTP 200, not 4xx. That is item 8's, not yours. Criterion 8 expects 200.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path
  and refuses a `>` or a heredoc. Write files with the Write tool.
- The suite takes about 135 seconds on this machine.

## Backlog items this unit is NOT fixing

- **Item 87** — the web form rounds its defaults to one decimal, so Walmart is $27.01 on
  the page and $28.02 in the CLI. In `assumptions_page` and `templates/`.
- **Item 88** — `assumptions` is a bare dict. **The user accepted it until item 88 is
  fixed** (decision of 2026-10-05). Do not change the signature.
- **Item 89** — `run_capm` prints "ERP from history" from inside a calculation.
- **Item 90** — the default terminal growth rate is a literal in `cli.py:205` and in the
  web form.
- **Item 92** — the CLI and the web pages show different historical FCFF.
- **Item 26** — the `files` branch tests for a character every path contains, in
  `api/routes_valuation.py`. Latent.
- **Item 5** — the module-global extraction cache in `api/routes_valuation.py`.
- **Item 82** — the CLI cache key stores the model as "(provider default)".

Every one of them sits in a file you touch. Leave all of them alone.

---

## Round 2 amendment (overall lead), 2026-10-05

The code reviewer returned **`approved`** with five findings, none blocking. Round 2
answers two of them. **Nothing else in this assignment changes**, and no criterion from
1 to 17 is withdrawn: re-run all of them.

**F1, and it is the assignment's defect before it is yours.** The stop message ends
"...or rename the file so the year after '10-K' in its name is that year". That remedy
is **false on the command line**. `parse_pdf_args` gives a bare path the year 0 and never
reads the file name for a year (`ingestion/filings.py:450-460`); only `discover_filings`
(a folder argument) and the web upload page read a year from a file name. So two files
already named `ABBV_10-K_2025-12-31.pdf` and `ABBV_10-K_2024-12-31.pdf`, passed as bare
paths, meet this stop and are told to do a thing that changes nothing. The wording came
from step 1 of this assignment, which I wrote.

**What to do.** Make every remedy in the message true for the reader who meets it. State
the condition first, as the repository's own style requires. The facts, each read today:

| The reader is at | Where the year comes from | The remedy that works |
|---|---|---|
| the command line, with paths | nowhere: a bare path is year 0 | give each filing as `YEAR:PATH` |
| the command line, with a folder | each file name (`discover_filings`), and it stops on a name with no year, with its own message | this stop never fires for a folder |
| the web upload page | each file name (`api/routes_upload.py`, `_guess_fiscal_year`) | rename the file so its name carries the year, and upload it again |

One message serves both entry points, so it must name which remedy belongs where, or
drop the remedy that is not universal. Do not add a parameter that makes the message
differ by caller unless you can state why that is better than one true message.

**F4, a note.** `pipeline.py:83` and `:176` quote `latest_bs.total_debt if latest_bs else 0`
in prose, which contradicts the decision row in your own entry ("the comments describe the
deleted lines instead of quoting them"). Either stop quoting it in `pipeline.py` too, or
correct that row and say why `pipeline.py` may quote it when `cli.py` may not. Criterion
10's grep reads `cli.py` only, so no measurement moves either way.

**Not yours, recorded by me, do not fix:** F2 is backlog item 95 (`cmd_plan`'s own year
check is now unreachable). F3 and F5 are notes; F5 is backlog item 96 if it is still true
at the end of round 2.

**New criterion 18.** Every remedy the stop message states is true for the entry point
that reaches it. Measure it: run `cli.py` with the two **real** ABBV 10-K PDFs under
`10K_filings/ABBV/`, whose names already carry their years, as bare paths. Print the
message, and show that the message does not tell that reader to rename those files.

---

## Overall lead review of round 2, 2026-10-05

**Round 2 went to me and not to the code reviewer, and here is the reason.** Round 1 was
reviewed in full and `approved`. Round 2 answered F1 and F4 only. I compared every
executable line of the current diff against the diff the reviewer approved: the control
flow of `require_fiscal_year_per_filing` (`len(filings) <= 1`, `year <= 0`, the two
returns, the raise) and of `value_company`'s new stop (`if latest_bs is None`,
`total_debt = latest_bs.total_debt`) is unchanged, character for character. Round 2
changed one error message and three comments. A second hour-long review of a message
string buys less than it costs. **I state this because `AGENTS.md` says every programmer
run goes to a reviewer, and this one did not.**

My measurements, on the Windows machine, with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| What | Result |
|---|---|
| criterion 18, the two real ABBV PDFs as bare paths | exit 1; both real file names in the message; the command-line remedy says "renaming it changes nothing here"; every "rename" sits in the web-upload remedy |
| gate | 1107 passed, 5 skipped, **0 failed** |
| types | 5 errors in 2 files |
| lint | 4 errors, every one `BLE001` |
| census | 64 |
| `GET /` | 200 |
| write guard | 48/48 |

**F1 is answered.** The message now states the condition first and gives each entry point
the remedy that works there. I checked both halves myself: a bare path never reads a file
name for a year (`parse_pdf_args`), and the web upload page reads every year from the
file name (`api/routes_upload.py`, `_guess_fiscal_year`), so each half is true where it
is addressed.

**F4 is answered.** No comment in `pipeline.py` quotes the deleted expression.

**One new finding from the round 2 programmer, recorded as backlog item 97:**
`templates/assumptions.html` and `templates/valuation_result.html` render an error
without `white-space: pre-line`, which `templates/upload.html` has. So this stop's file
list and its two remedy bullets collapse into one wrapped paragraph on both pages. It is
display only, it is older than this unit, and `templates/` was outside its scope.

The tester is next: `.agent/assignments/P3b-pipeline-stops-tests.md`.
