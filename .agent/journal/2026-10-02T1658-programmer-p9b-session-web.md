---
agent: programmer
assignment: P9b-session-web
round: 1
status: complete
files_touched: [api/routes_upload.py, api/routes_valuation.py, templates/upload.html, templates/assumptions.html, docs/3-architecture/entry-points.md]
---

# P9b-session-web — let the web app value a company from an uploaded session file

Base commit: `d97855b` (P9a accepted at `ad52e1a`). Started 2026-10-02T1658, macOS,
`.venv/bin/python`. Outcome: **`ok`**. Every scratch file is under `/tmp/p9b/`.
`templates/valuation_result.html` was **not** changed: its four label rows already read
`extraction.provider|model|transport_label|credential_source`.

**Every financial figure in every scratch session file is invented** (`/tmp/p9b/build_session.py`
says so in its docstring). The PDF they name — Walmart's FY2026 10-K in `10K_filings/` —
is real and hashed by `session_extraction plan`; the numbers are round figures chosen so
the arithmetic checks reconcile. The implied price $33.98 printed below means nothing.
The share price is not what this unit claims. It claims the label and the route.

## What I did

Added a second form to `templates/upload.html` and `POST /upload-session` to
`api/routes_upload.py`. The route saves the `.json` under `uploads/session/` and returns 303
to `/assumptions?session_file=<path>`. It does not parse the file. In
`api/routes_valuation.py`, `CachedExtraction` gained a fifth required field,
`extraction: ProviderResolution`. A new `_run_extraction(files, file_path, session_file,
ticker, company_name) -> RouteExtraction` is now the one place either handler extracts.
With a session file it calls `load_session_extraction` and carries the loader's label.
Otherwise it records `resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)` right
before route A extracts. `assumptions_page` and `run_valuation` accept `session_file`,
key the cache on the first non-empty of `session_file`/`files`/`file_path`, and take
the ticker and company name from the file through `_shown_identity`. `run_valuation`
renders the recorded label: the render-time `resolve_provider` call and its "KNOWN
LIMITATION" comment are gone. `templates/assumptions.html` forwards `session_file` as a
hidden field and shows the same four label rows. `docs/3-architecture/entry-points.md`
has the new route, the new flow and a re-measured `cli.py` table.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the upload page offers both routes | **pass** | `/tmp/p9b/crit.py` → `200 forms: 2 \| /upload-session in body: True \| /upload in body: True \| <script: 0` |
| 2 | a session file reaches the assumptions page | **pass** | same script: `upload: 303 /assumptions?session_file=%2Ftmp%2Fp9b%2Fuploads%2Fsession%2Fsession_wmt.json`; `assumptions: 200 \| error alert: False`; all seven headings `True` (Adjusted Income Statement, Cash Flow Statement, Balance Sheet, Non-recurring items APPLIED, GAAP to Non-GAAP Reconciliation, Historical Free Cash Flow to Firm, Assumptions Used); label rows `('Provider','CLAUDE'), ('Model','claude-opus-5'), ('Transport','Claude Code session — figures read from the PDF in a Claude Code session and stored in the session file /private/tmp/p9b/uploads/session/session_wmt.json. …'), ('Credential source','none — no API call was made; …')`; hidden `ticker WMT`, `company_name Walmart Inc.`, `files ''`, `session_file /tmp/p9b/uploads/session/session_wmt.json`. **Figures invented** |
| 3 | the result page shows the recorded label | **pass** | `POST /valuation` (cache hit), `fetch_price_data` stubbed: `200 \| error: None`, `Claude Code session in body: True \| public API in body: False`, same four label rows, all seven headings, `price fetched for: ['WMT']`. Cache miss (second POST, same form): `200`, `Claude Code session: True`. `.env`'s key was loaded in this process, so a re-derivation would have printed "Anthropic public API". It is absent |
| 3' | the same, with **no credential at all** | **pass** | `/tmp/p9b/crit_nocred.py` imports `config`, then pops every credential variable (`no credential resolves in this process`), then runs `crit.py`. Every line is identical. Before this unit, `run_valuation` called `resolve_provider` at render time, so a valuation with no credential stopped even on a cached extraction |
| 4 | the label survives a change of environment | **pass** | `/tmp/p9b/crit4.py`: `_call_llm` is stubbed before any request. After `config` loads, the Foundry variables are popped and `ANTHROPIC_API_KEY=dummy-not-a-key` is set. `GET /assumptions?files=2026:<WMT pdf>` → `200`, stub calls `[('anthropic-direct', 1113685), ('anthropic-direct', 1113685)]`, label `Anthropic public API (api.anthropic.com)` / `ANTHROPIC_API_KEY (environment)`. Then the variable is popped, and `resolve_provider` now `STOPS -> No Anthropic credential resolved…`. That is what the old render-time call would have done. `POST /valuation` (cache hit) → `200 \| error: None`, `'Anthropic public API' in body: True`. Control: the same POST again (cache miss, variable unset) → error `No Anthropic credential resolved…`, `new stub calls: 0`. Route A resolves at extraction time |
| 5 | a bad session file shows the loader's message | **pass** | `session_wmt_bad.json` (the `sbc` key removed from 2025) → `200 \| message: /private/tmp/p9b/uploads/session/session_wmt_bad.json: the session file cannot be used. 1 problem(s): - …: filings[0] (Walmart Inc._10-K_2026-01-31_English.pdf), year 2025: key 'sbc' is absent. …` |
| 6 | route A is unchanged | **pass** | gate on P9a's test set (`--ignore` the tester's two new files): `1 failed, 197 passed`. The failure set is `{test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}`, the same as P9a. Full gate with P9c's new files present mid-run: `1 failed, 291 passed`, same failure set. The route tests that stub `_extract_from_files` (`tests/unit/test_statements_ui.py`, `test_route_context_keys.py`, `test_routes.py`) all pass. They pin `ANTHROPIC_API_KEY` in their fixtures, which `_run_extraction` now resolves before it extracts |
| 7 | no new lint or type errors | **pass** | ruff `Found 5 errors.`: the same five BLE001 sites (`api/routes_valuation.py:445`, `:703`, `cli.py:1107`, `ingestion/claude_extractor.py:1051`, `tests/test_e2e_all_googl.py:106`). mypy `Found 10 errors in 4 files (checked 20 source files)`. The error SET is identical to before with line numbers stripped: `diff /tmp/p9b/mypy_before.norm /tmp/p9b/mypy_after.norm` gives no output |
| 8 | one extraction function | **pass** | `grep -n "_run_extraction" api/routes_valuation.py` → `147:def _run_extraction(`, `399:` (`assumptions_page`), `563:` (`run_valuation` cache miss). One definition, two callers. `_extract_from_files` now has one caller, `_run_extraction:202` |
| — | census | 116 | the rules.md:65 grep, `'--include=*.py'` quoted → `116`, unchanged |
| — | web app serves | 200 | `TestClient(app.app).get('/')` → `200` |

**A figure on the page comes from the file.** `/tmp/p9b/trace.py` copies the session file
and changes 2026 revenue from 1,200 to 1,234 (both invented). The Adjusted Income Statement
block then shows `1,234` and no longer shows `1,200`.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `_run_extraction` returns a frozen dataclass `RouteExtraction` (3 required fields), not a tuple | rule 2: named fields. Same reasoning as `CachedExtraction`'s docstring | a 3-tuple whose third member is a label is easy to unpack in the wrong order |
| Route A's label is `resolve_provider(...)` called immediately **before** `_extract_from_files` | step 4. `extract_financials` resolves internally and does not return the resolution, and `ingestion/` is out of scope | it is the same call, in the same environment, microseconds apart. Changing the extractor to return its resolution would be the exact record, but that is `ingestion/` (finding 1) |
| Identity (ticker, company) handled by `_shown_identity`, called by both handlers after the cache branch | step 5: "the ticker shown and forwarded comes from the loaded file". The cache-hit branch runs no extraction, so the identity cannot live only inside `_run_extraction` | a ticker or name in the request that differs from the file **stops**, as `cli.py` does for `-t`/`-n` (`cli.py:884-897`). Ticker compare is case-insensitive, as in the CLI. Silently replacing a supplied ticker would hide which ticker was priced |
| A `session_file` together with `files`/`file_path` stops | rule 3: an input is never silently ignored. `cli.py` refuses PDFs with `--session-file` | letting the session file win silently would discard what the user gave |
| None of the three given → stop, `No filing named: …` | backlog item 29. The assignment asks to close it "if the shared function makes this a stop at no extra cost". It does: it is the `else` branch | `POST /valuation` with no filing now renders that message. It used to extract `''` |
| `files` that parses to no entry (e.g. `","`) → stop `files: ',' names no filing.` | rule 3. Without it `_extract_from_files` hits a bare `IndexError` on `filings[0]` | **behaviour change on degenerate input:** before, `GET /assumptions?files=,` rendered an empty form with no error, because `if filings:` skipped extraction |
| `run_valuation` maps its `files` form field to `files`/`file_path` with the existing `":" in files` test | item 26 is out of scope. Keeping the test keeps route A's cache-miss behaviour identical | moving the test into `_run_extraction` would change `assumptions_page` for a `files` with no colon |
| Upload: only `Path(filename).name` is kept, and `""`, `.` and `..` stop with 400 `session_file: the uploaded file has no usable filename (…)` | backlog item 28 says do not copy `_save_upload`'s unchecked path segment. A missing name must stop, naming the field | probed with `/tmp/p9b/fname.py`. `.`, `/` and `a/..` each give 400. `a/..` gave 500 (`IsADirectoryError`) before I added `.`/`..`. `../../escape.json` is saved as `uploads/session/escape.json`. An empty filename or an absent field never reaches the function: FastAPI answers 422 naming `session_file` |
| The redirect URL is built with `urlencode` | paths contain spaces and `/` | the PDF route's unencoded f-string is not copied. TestClient follows the redirect to the right file |
| The label block on `assumptions.html` sits above "Assumptions Used" and shows whenever `extraction` is set, error or not | step 7: the reader must know the route before choosing. If a later step fails after the extraction ran, the label is still true | it is hidden when no extraction ran (`extraction` is `None`). On a loader stop there is no label, only the message |
| Session filings (sha256, pages) are **not** shown on the page | optional per the amendment ("if you show…"). The four-field label already names the file | keeps the two routes' pages the same shape. A later unit can add it |
| Route B's arithmetic `validation_errors` are not shown | "Known open items": do not show them in this unit | — |

**No code was changed to reach a target number.** The one figure-related change is in a
scratch script: the price stub's random market series annualised to -1.19%, the
historical ERP came out negative, and the first criterion-3 run stopped. The scratch
form now supplies `equity_risk_premium=5`, which the page labels as user-supplied.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| upload field `session_file` | FastAPI 422, `loc: ["body","session_file"], "Field required"` | `crit.py` "field absent" |
| uploaded filename | empty: 422 naming `session_file`. `.`/`/`/`..`: stops, 400 `session_file: … no usable filename` | `routes_upload.py:45-50`, `/tmp/p9b/fname.py` |
| `session_file` / `files` / `file_path` (all three) | `assumptions_page`: no extraction, empty form, no error (unchanged; it is the page's landing state). `run_valuation`: stops, `No filing named: session_file, files and file_path are all empty.` | `_run_extraction` `else` branch. `crit.py` "no filing at all (item 29)" |
| `files` naming no entry | stops, `files: ',' names no filing.` | `_run_extraction` |
| the session file's content | the loader's stop list (P9a). Its message reaches the page | criterion 5 |
| the route A credential | stops in `resolve_provider` at extraction time (same message as before, now raised one call earlier) | `crit4.py` step 4 |
| `CachedExtraction.extraction` / `RouteExtraction.*` | cannot be constructed without them. No default | dataclass definitions |
| `ticker` / `company_name` from the request in session mode | optional. Absent → the file's values. Present and different → stops, naming both | `crit.py` "ticker mismatch"; `wmt` accepted |
| `raw_financials.ticker` / `.company_name` (session) | the loader stops on an absent or empty `ticker`. `company_name` may be `""`, and then Pass 1's name is used (P9a's documented behaviour) | P9a entry, Rule 3 table |
| `extraction` in `assumptions_page` | `None` until an extraction runs. The template then shows no label. It is a "not run" marker, never a substitute label | `routes_valuation.py:393` |
| `cache_key = session_file or files or file_path` | an `or` over strings that picks the first given. Not a numeric default. Empty means "no filing", handled above | — |

No "defaults to" row for a figure.

## Measurements

| Gate | Before (`d97855b`) | After |
|---|---|---|
| tests, `--ignore-glob="*_rule3_red.py"` | `1 failed, 197 passed` | P9a's set: `1 failed, 197 passed`. With P9c's new files present: `1 failed, 291 passed`. Failure set `{test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}` both times |
| ruff | `Found 5 errors.` | `Found 5 errors.` (same five sites) |
| mypy (exact gate command) | `Found 10 errors in 4 files (checked 20 source files)` | the same, the same set. `api/routes_valuation.py`'s four moved to `:132`, `:624`, `:633`, `:634` |
| census | 116 | 116 |
| `GET /` | 200 | 200 |

All five "already true" rows agreed at the start: `load_session_extraction` is at
`session_extraction.py:550`, `SessionExtraction` at `:154` with six fields, the label was
re-derived at `routes_valuation.py:522`, `CachedExtraction` had four fields, the hidden
`files` was at `assumptions.html:114`, and the label fields were at
`valuation_result.html:290-293`.

Scratch scripts and outputs: `/tmp/p9b/build_session.py`, `crit.py` → `crit.out`,
`crit_nocred.py` → `crit_nocred.out`, `crit4.py` → `crit4.out`, `fname.py`, `trace.py`.
The scratch uploads went to `/tmp/p9b/uploads/`: `crit.py` patches
`api.routes_upload.UPLOAD_DIR`. The repository's `uploads/` holds only `LHX`, as before.

## Progress log

- Read the assignment, rules, STATUS, P9a's programmer and review entries, both route
  files, the three templates and the loader's interface. The baseline gates agreed with
  P9a.
- Wrote the code. Ran ruff and mypy: unchanged.
- `crit.py`'s first run: criterion 3 rendered an error page (negative historical ERP from
  the stub's random series). Supplied ERP 5 in the scratch form and re-ran: pass.
- `fname.py` found `a/..` → 500. Added `.`/`..` to the rejected names and re-ran: 400.
- `crit4.py` and `crit_nocred.py`: pass. Updated the docs, then re-ran every gate.

## What I did not do

- **`ingestion/`**: untouched. Route A's exact resolution is not returned by
  `extract_financials` (finding 1).
- **Tests**: the tester's. My proofs are the `/tmp/p9b/` scripts above.
- **Backlog items 5, 6, 8, 26, 28**: untouched as instructed. `.pop()` is kept. `":" in files`
  is kept (moved into a two-way assignment, same test). `_save_upload` is not changed,
  and its mypy error at `routes_upload.py:28` remains.
- **Item 29 is closed for `POST /valuation`**, at no extra cost, as the assignment allowed.
- `docs/3-architecture/entry-points.md`: I did not touch the "Where they duplicate each
  other" table (`cli.py :667…`, `api :139…`) or the "Templates" paragraph saying the result
  page shows no substitutions. Both were stale before this unit and are outside the three
  edits asked for (finding 3).

## Findings for the orchestrator

1. **Route A's label is recorded beside the extraction, not by it.** `extract_financials`
   / `extract_multi_year` resolve the provider internally (`claude_extractor.py:1427`) and
   do not return the `ProviderResolution`. `_run_extraction` calls the same
   `resolve_provider` just before. That is exact unless the environment changes between
   the two calls, microseconds apart in one request. Closing it fully means returning the
   resolution from the extractor. That is an `ingestion/` change, and `cli.py`'s
   `_extract_via_api` would want it too.
2. **Route B now runs the whole web flow with no credential.** Before this unit,
   `run_valuation` re-derived the label at render time, and with no credential that
   raised. So no valuation, even of a cached extraction, could render without a key.
   Shown by `crit_nocred.py`.
3. **`entry-points.md`'s "Where they duplicate each other" table is stale**: its `api`
   line numbers predate P8. The "Templates" paragraph says the result page does not
   show substitutions, which P8 changed. A docs pass should re-measure both.
4. **The session file path travels in the URL and is loaded from wherever it points**,
   as `files` paths already do (the "File paths travel in the URL" surprise). The
   loader verifies every PDF by sha256, so a pointed-at file cannot smuggle in a changed
   PDF. It can name any readable `.json` on the machine. The same exposure as route A's
   `files`. It is recorded in the doc, not fixed.
5. **P9a review F1 is now reachable from the web.** A session file whose
   `non_recurring_items` is not a list raises `AttributeError` in the parser. On the web
   the blanket `except Exception` (item 8) shows it as a bare message without the file
   name. `P9d-pass2-checks` (untracked assignment in the tree) appears to own it.
