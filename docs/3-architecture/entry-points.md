# Entry points

Two programs run the same eight steps. **They are separate implementations**, which is
[backlog item 7](../9-reference/refactor-backlog.md) and the reason this file exists.

---

## The web app — `app.py`

```bash
.venv/Scripts/python.exe -m uvicorn app:app --reload
```

FastAPI, three routes, Jinja2 templates, no JavaScript framework.

| Route | Method | File | Renders |
|---|---|---|---|
| `/` | GET | `api/routes_upload.py:35` | `upload.html` |
| `/upload` | POST | `api/routes_upload.py:41` | 303 → `/assumptions` |
| `/assumptions` | GET | `api/routes_valuation.py:60` | `assumptions.html` |
| `/valuation` | POST | `api/routes_valuation.py:109` | `valuation_result.html` |

### The flow

1. **Upload.** `_save_upload` writes each PDF to `uploads/<TICKER>/`.
   `_guess_fiscal_year` pulls a 4-digit year from the filename with
   `re.search(r"(20\d{2})")`. Files are passed on as a comma-separated
   `year:path,year:path` **query string**.
2. **Assumptions.** Runs extraction and normalisation, caches the result, derives the
   defaults, formats them as percentage strings for the form.
3. **Valuation.** Reads the cache, applies the user's overrides, runs steps 4 to 8,
   renders.

### Four things about this flow that will surprise you

**The fiscal year comes from the filename.** A file named `annual_report.pdf` gets year
`0`, and `_extract_from_files` then filters it out of the multi-file path. Renaming a
file changes which years are extracted.

**File paths travel in the URL.** The query string carries absolute filesystem paths,
visible to the user and editable by them. `/assumptions?files=...` accepts whatever it
is given.

**The LLM runs on `/assumptions`, not on `/valuation`.** That is deliberate — the user
must see historical-derived defaults before choosing overrides. It means the expensive
call happens on a **GET**, so a browser prefetch or a refresh re-runs it.

**The cache is popped, not read.** `api/routes_valuation.py:134` uses `.pop()`, so
refreshing the results page is a cache miss and re-runs the whole paid extraction.
Backlog item 5.

## The CLI — `cli.py`

```bash
.venv/Scripts/python.exe cli.py --help
```

760 lines: argument parsing, filing discovery, a pickle cache, a 10-step progress
display, and one print function per pipeline stage.

**It is the cheaper way to iterate on `analysis/`**, because `--cache-dir` stores the
extraction result as a pickle and `--no-cache` forces a re-run. You can change a formula
and re-run the valuation without paying for extraction again.

| Piece | Lines |
|---|---|
| `parse_args` | `:69` |
| `_discover_filings` | **moved** to `ingestion/filings.py` as `discover_filings` by `P9a-session-route`, with `parse_pdf_args`, `InputFingerprint` and `fingerprint_filings`. `cli.py` imports them |
| `build_overrides` | `:214` — argparse → `ProjectionAssumptions` |
| `_cache_path` / `_load_cache` / `_save_cache` | `:240-259` |
| `print_*` — one per stage | `:286-591` |
| `main` | `:596` |

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
`_extract_from_session_file`. Stages 2 to 10 are the same code for both.

> **Warning.** The cache is a **pickle**. Loading a pickle executes code inside it. Do
> not load a `.pkl` from anywhere but your own machine, and note that five are committed
> to this repository (backlog item 12).

## Where they duplicate each other

Both build the same call sequence independently:

| Step | `cli.py` | `api/routes_valuation.py` |
|---|---|---|
| normalise | `:667` | `:139` |
| assumptions | `:677` | `:163` |
| price data | `:682` | `:166` |
| CAPM | `:687` | `:167` |
| WACC | `:710` | `:187` |
| project | `:722` | `:197` |
| DCF | — `main()` | `:200` |

**They also differ**, which is worse than duplicating:

- the default provider (`gemini` in the CLI, file-count-dependent in the route — backlog
  item 13),
- override parsing — argparse types against `x / 100 if x else None` (backlog item 6),
- the share-count fallback: the route reaches for yfinance at `:182`, the CLI does not
  in the same way,
- the CLI prints a full audit trail per stage; the web app shows only the result.

**A figure verified in one is not verified in the other.**

### The fix, when it is assigned

Extract one function both call:

```python
def run_pipeline(financials, overrides, ticker) -> PipelineResult: ...
```

The CLI keeps its printing layer. The route keeps its form parsing. Neither keeps a copy
of the sequence. **Do this before fixing backlog items 1, 2 or 3**, or every one of
those fixes must be made twice.

## Templates

`templates/` — `base.html` and the three pages. `static/style.css` holds the styling;
`static/charts.js` is a placeholder and is not wired to anything.

The result page shows the implied share price, the upside, and the assumption table. It
does **not** show which assumptions were substituted rather than measured — that is
[rule 6](../2-rules/rules.md) and backlog items 9 and 13.
