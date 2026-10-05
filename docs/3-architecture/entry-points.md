# Entry points

Two programs run the same eight steps. Since `P3a-one-pipeline` both call **one
module, `pipeline.py`**, for those steps (backlog item 7); what each entry point still
does on its own is listed in "What `pipeline.py` holds, and how the two still differ"
below.

---

## The web app — `app.py`

```bash
.venv/Scripts/python.exe -m uvicorn app:app --reload
```

FastAPI, five routes, Jinja2 templates, no JavaScript. Line numbers measured at
`P10c-fiscal-year` round 2 (2026-10-02, on top of `1ae0069`), each checked against the
file; the function names are the stable reference.

| Route | Method | Function | Renders |
|---|---|---|---|
| `/` | GET | `upload_page`, `api/routes_upload.py:70` | `upload.html`: two forms, PDFs (route A) and a session file (route B) |
| `/upload` | POST | `upload_files`, `api/routes_upload.py:82` | 303 → `/assumptions?ticker=…&company_name=…&files=…`; **400 and `upload.html` with the message** when a filename's year disagrees with the filing (`P10c`) |
| `/upload-session` | POST | `upload_session_file`, `api/routes_upload.py:129` | 303 → `/assumptions?session_file=…` |
| `/assumptions` | GET | `assumptions_page`, `api/routes_valuation.py:362` | `assumptions.html` |
| `/valuation` | POST | `run_valuation`, `api/routes_valuation.py:497` | `valuation_result.html` |

### The flow

1. **Upload**, by one of two routes.
   - **PDFs (route A).** `_save_upload` writes each PDF to `uploads/<TICKER>/`.
     `_guess_fiscal_year` takes the year from the filename with
     `fiscal_year_from_filename` (`ingestion/filings.py`), the same guesser the CLI
     and route B use. **Every year so found is then verified against the filing**
     with `verify_filing_years`: the cover's "For the fiscal year ended" date and the
     newest column label above the income statement. A mismatch, or a filing whose
     evidence cannot be read, **stops here**: the upload page is rendered again with
     the message, HTTP 400, no redirect, and nothing is extracted. The message names
     the file, the year given, the cover date, the column label, the year the content
     gives, and the web remedy: rename the file so the year after `10-K` in its name is
     the year the filing gives, and upload it again (`YEAR:PATH` is the CLI's remedy,
     and a web user cannot use it). A filing whose evidence could not be read is listed
     under its own heading, "could not be confirmed", not "does not match". The rule is in
     [extraction.md](extraction.md), "Where each filing's fiscal year comes from".
     Otherwise files are passed on as a comma-separated `year:path,year:path`
     **query string**.
   - **A session file (route B).** `_save_session_upload` writes the `.json` to
     `uploads/session/` (the last path component of its name only; a missing name is a
     400 naming `session_file`). It is **not parsed** here. Its saved path is passed on
     as `session_file`. The file's format and stop list are in
     [extraction.md](extraction.md), "Two routes, one parser".
2. **Assumptions.** `_run_extraction`, the one place either handler extracts, takes
   `files`, `file_path` and `session_file`:
   - with a `session_file`, it calls `load_session_extraction`. A bad file stops there,
     and its message, naming the file, the filing, the year and the key, is shown on the
     page. The ticker and company name come from the file; one in the request that
     differs from the file stops (`_shown_identity`), as `-t`/`-n` do in the CLI.
     A `session_file` together with `files`/`file_path` stops;
   - otherwise it runs route A over the API, and records
     `resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)` as it extracts;
   - with none of the three, it stops (backlog item 29 for `POST /valuation`).

   It returns the raw statements, the items and the **`ProviderResolution`, recorded
   when the extraction ran**. The page normalises, caches the result under the first
   non-empty of `session_file`, `files` and `file_path`, derives the defaults, formats
   them as percentage strings for the form, and shows the route ("Extraction — who read
   the filing"). It forwards `files` and `session_file` as hidden fields.
3. **Valuation.** Reads the cache under the same key (or, on a miss, calls the same
   `_run_extraction`), applies the user's overrides, runs steps 4 to 8, and renders the
   **recorded** label. The label used to be re-derived from the environment at render
   time (`P2b-provider` review, finding F3), which named who *would* read a filing now:
   wrong after an environment change, and wrong for every session file.

### Four things about this flow that will surprise you

**The fiscal year comes from the filename, and the filing must agree** (route A). A
filename year the filing contradicts stops at `/upload` (L3Harris's
`…_10-K_2026-01-02_….pdf` names 2026; the filing calls that year 2025). A file named
`annual_report.pdf` gets year `0`, is not verified, and `_extract_from_files` then
filters it out of the multi-file path (backlog item 49). Renaming a file changes which
years are extracted.

**File paths travel in the URL.** The query string carries absolute filesystem paths,
visible to the user and editable by them. `/assumptions?files=...` and
`?session_file=...` accept whatever they are given. A session file is at least checked
by the loader, and each PDF it names is verified by sha256.

**The LLM runs on `/assumptions`, not on `/valuation`.** That is deliberate — the user
must see historical-derived defaults before choosing overrides. It means the expensive
call happens on a **GET**, so a browser prefetch or a refresh re-runs it. On route B the
same GET only re-reads the session file; no API call is made.

**The cache is popped, not read.** `run_valuation` (`api/routes_valuation.py:548`) uses `.pop()`, so
refreshing the results page is a cache miss and re-runs the whole paid extraction.
Backlog item 5.

## The CLI — `cli.py`

```bash
.venv/Scripts/python.exe cli.py --help
```

1,146 lines (measured at `P3a-one-pipeline`): argument parsing, a pickle cache, a
10-step progress display, one print function per pipeline stage, and stage 1 by either
route. Filing discovery moved to `ingestion/filings.py` at `P9a-session-route`; the
valuation steps moved to `pipeline.py` at `P3a-one-pipeline`.

**It is the cheaper way to iterate on `analysis/`**, because `--cache-dir` stores the
extraction result as a pickle and `--no-cache` forces a re-run. You can change a formula
and re-run the valuation without paying for extraction again.

Measured at `P9b-session-web` (`cli.py` unchanged since `P9a-session-route`). The
function names are the stable reference; the line numbers drift.

| Piece | Lines |
|---|---|
| `parse_args` | `:85` |
| `discover_filings` | **moved** to `ingestion/filings.py` by `P9a-session-route` (it was `_discover_filings`), with `parse_pdf_args`, `InputFingerprint` and `fingerprint_filings`. `cli.py` imports them |
| `build_overrides` | `:189` — argparse → `ProjectionAssumptions` |
| `ExtractionKey` / `build_extraction_key` / `describe_key_difference` | `:219-246` — what the pickle cache is keyed on |
| `_cache_path` / `_load_cache` / `_save_cache` | `:295-348` |
| `print_*` — one per stage | `:382-743` |
| `_extract_via_api` / `_extract_from_session_file` | `:762` / `:867` — stage 1, route A / route B |
| `main` | `:934` |

### `--session-file FILE` — the session route

Added by `P9a-session-route`. Reads the extraction from a Claude Code session file
(`ingestion/session_extraction.py`; format and stop list in
[extraction.md](extraction.md), "Two routes, one parser") instead of calling an API.

```bash
.venv/bin/python cli.py --session-file extractions/CMG.json
```

- **No PDF arguments.** The file names its PDFs and each is verified by sha256. Giving
  both, or neither, is an `argparse` error. The positional is `nargs="*"`.
- **The ticker and company come from the file.** `-t` and `-n` are optional; one that
  differs from the file stops the run.
- **`-p`, `-m`, `--cache-dir` and `--no-cache` are refused**, not ignored: they belong to
  the API route. No pickle is read or written; the session file is the stored
  extraction. (`-p`'s argparse default is `None` so that it can be refused; without
  `--session-file` it resolves to `config.DEFAULT_EXTRACTION_PROVIDER` as before.)
- **No credential is needed.** No API call is made on this route.
- **Stage 1 prints `describe_resolution` of the session label**, then each PDF with its
  sha256 prefix, size and the pages read for each pass, then any arithmetic validation
  errors as warnings.
- **Every later place that named the provider names the route.** Stage 3's heading reads
  `identified by a Claude Code session, model <id> as declared` instead of `CLAUDE`, and
  the closing "not measured" block names the session file and says no API call was made.

Stage 1 is two functions, `_extract_via_api` (the old stage 1, moved unchanged) and
`_extract_from_session_file`. Stages 2 to 10 are the same code for both: `main` calls
`pipeline.adjust_financials` before it prints stages 3 to 5, then
`pipeline.value_company` once, and prints stages 6 to 10 from its result.

> **Warning.** The cache is a **pickle**. Loading a pickle executes code inside it. Do
> not load a `.pkl` from anywhere but your own machine, and note that five are committed
> to this repository (backlog item 12).

## What `pipeline.py` holds, and how the two still differ

Until `P3a-one-pipeline` each entry point called the eight valuation functions in its
own copy and chose the share count and the arguments itself, so a fix made in one copy
did not reach the other (backlog item 7). Now `pipeline.py`, at the repository root
beside `cli.py` and `app.py`, holds the sequence once. It is not in `analysis/` because
it calls `ingestion.price_fetcher.fetch_price_data`, and `analysis/` importing from
`ingestion/` is backlog item 17.

| Function | Runs | Returns | Called by |
|---|---|---|---|
| `adjust_financials(raw_financials, non_recurring)` | `partition_by_confidence`, then `normalize_financials` with the applied half | `AdjustedFinancials`: `applied`, `excluded`, `adjusted` | `cli.main` (before stages 3 to 5 print); `assumptions_page`; the cache-miss branch of `run_valuation` |
| `value_company(adjusted, overrides, ticker, lookback_years, frequency)` | `derive_assumptions(adjusted, overrides)`, the share count (it stops when the filing gives none), `fetch_price_data`, `run_capm`, the market cap, `calculate_wacc`, `project_fcffs`, `run_dcf` | `ValuationRun`: `assumptions`, `price_data`, `capm_result`, `shares`, `market_cap`, `latest_balance_sheet`, `wacc_result`, `projected`, `dcf_result` | `cli.main` (before stages 6 to 10 print); `run_valuation` |

Two functions and not one, because the callers stop at different places: the CLI prints
stages 3 to 5 before it fetches market data, and the assumptions page uses the first
function alone. The assumptions page also keeps its own `derive_assumptions` call with
no overrides; it fills the form's defaults and is not part of the valuation. Neither
pipeline function prints or formats; the CLI's audit trail and the routes' templates
stay with the callers.

**The share count comes from the filing, and from nowhere else.** `value_company`
reads the latest fiscal year's `diluted_shares_outstanding`. When it is not a finite
number above 0 (an empty `diluted_shares` list in the extraction becomes 0), the run
stops with a `ValueError` that names `diluted_shares`, the ticker and the fiscal year,
and says that no share count is taken from market data. The stop comes after
`derive_assumptions` and before `fetch_price_data`, so it makes no network call. The CLI
prints it as `ERROR: ...` and exits 1; the web result page shows it in its error block.
**This is the one behaviour change of `P3a-one-pipeline`** (review F1, rules 3 and 5):
until then both entry points asked yfinance for `sharesOutstanding` when the filing gave
0, and that lookup itself fell back to 0. That fallback is deleted, with the CLI's line
"Diluted shares from yfinance: ...".

**What a stop hides in the CLI.** The CLI prints each stage after the pipeline function
that computes it, so a stop inside a pipeline function now comes before some stage
output that used to print ahead of it. A stop inside `adjust_financials` (a
normalisation stop) comes before stages 3 to 5 print: the stage 3 banner shows, then
the error, with no non-recurring items, no normalisation table and no historical FCFF.
A stop inside `value_company` (the share count, the market data, CAPM, WACC, the
projection or the DCF) comes before stages 6 to 10 print: no assumptions, no CAPM
result, no WACC. Each error message is the one the failing function raised before the
move, and the web result page, which never showed the stages, is unchanged.

**One display difference the move made.** `run_capm` prints the line "ERP from
history: ..." when no equity risk premium is supplied (`analysis/capm.py`). The CLI now
calls `value_company` before stage 6, so that line prints after stage 5's table instead
of under stage 7. No figure moved.

**They still differ** in what each does around the pipeline:

- the default provider (`gemini` in the CLI, file-count-dependent in the route — backlog
  item 13),
- override parsing — argparse types against `x / 100 if x else None` (backlog item 6),
- the CLI prints a full audit trail per stage; the web app shows only the result, and
  the assumptions form rounds each default to one decimal place, so a web user who
  accepts every default values on the rounded figures,
- the historical FCFF table: the CLI prints it from the statements as extracted, the
  web pages from the normalised statements (display only; neither reaches the DCF),
- the extraction step (stage 1) stays in each entry point (backlog item 49).

## Templates

`templates/` — `base.html` and the three pages. `static/style.css` holds the styling;
`static/charts.js` is a placeholder and is not wired to anything.

The result page shows the implied share price, the upside, and the assumption table. It
does **not** show which assumptions were substituted rather than measured — that is
[rule 6](../2-rules/rules.md) and backlog items 9 and 13.
