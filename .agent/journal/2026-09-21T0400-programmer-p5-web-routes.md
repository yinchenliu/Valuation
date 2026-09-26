---
agent: programmer
assignment: P5-web-routes
round: 1
status: complete
files_touched: [api/routes_upload.py, api/routes_valuation.py]
verdict: —
---

# P5-web-routes — the last two template calls; `GET /` serves a page for the first time

> Opened before the first command. Filled as each result landed.

Measured at `d885d8d`, not `0e4649f`. The tree moved between the assignment being
written and my first command (`d885d8d Add backlog item 27, the two routes still
returning 500`). Every baseline below was re-measured on `d885d8d` with a clean working
tree, so no figure is carried forward from another entry.

## What I did

Two call sites, two lines of behaviour. `api/routes_upload.py:42` and the
`assumptions.html` call in `api/routes_valuation.py:114` were still using the
`TemplateResponse(name, context)` form that starlette 1.6.0 removed; both now use
`TemplateResponse(request, name, context)`. **`GET /` returns 200 and serves the upload
form, and `GET /assumptions` returns 200, for the first time in this environment.** I
changed nothing else in either file — the blanket `except Exception`, the module-global
cache, the five falsy-as-missing conversions and the yfinance fallback are all
untouched, and the two `valuation_result.html` calls `P2b-provider` owns are byte
identical.

**Line numbers had moved, as warned.** At `d885d8d` the sites were
`api/routes_upload.py:42` (unchanged) and `api/routes_valuation.py:114` (the assignment
and the `P2b` entry both said `:114`, and that was still right). They are now `:48` and
`:117` because of the comments I added above each.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the front page serves | **pass** | `TestClient(app).get("/")` → **200**, 1648 bytes, six form markers FOUND. Was **500**, 21 bytes, on the same script before the edit |
| 2 | the assumptions page serves | **pass** | **200** twice: empty form (5673 B) and a real extraction (5759 B, success branch, cache written, six defaults derived from the document) |
| 3 | no `TemplateResponse` call uses the old form | **pass** | `grep -n "TemplateResponse(" api/*.py` → 4 calls, all `(request, name, …)`, each read below |
| 4 | the type gate improves, and adds nothing | **pass** | **18 → 14**. `comm -13` (added) is **empty**; `comm -23` (removed) is exactly the 4 errors on my 2 lines |
| 5 | the suite is unchanged | **pass** | `1 failed, 105 passed`, same single failure; gate form `105 passed` |
| 6 | lint unchanged | **pass** | `Found 5 errors.`, all `BLE001`, the same five locations |
| 7 | the census did not rise | **pass** | **116** before, **116** after |

### Criterion 1 — the same script, before and after the two-line edit

`c:/tmp/p5/http_probe.py`, `TestClient(app.app, raise_server_exceptions=False)`. No port,
no key, no network. The `ABSENT`/`FOUND` block is the assignment's "the body holds the
upload form".

```
--- BEFORE (working tree at d885d8d, unmodified) ---
GET /                      -> 500   bytes=21
GET /assumptions (no file) -> 500   bytes=21
cache after both calls     -> {}

=== GET / body: is the upload form there? ===
  <form                                  ABSENT
  enctype="multipart/form-data"          ABSENT
  name="ticker"                          ABSENT
  name="pdf_files"                       ABSENT
  action="/upload"                       ABSENT
  type="submit"                          ABSENT

--- AFTER (the two lines changed, nothing else) ---
GET /                      -> 200   bytes=1648
GET /assumptions (no file) -> 200   bytes=5673
cache after both calls     -> {}

=== GET / body: is the upload form there? ===
  <form                                  FOUND
  enctype="multipart/form-data"          FOUND
  name="ticker"                          FOUND
  name="pdf_files"                       FOUND
  action="/upload"                       FOUND
  type="submit"                          FOUND
```

21 bytes is `Internal Server Error`. The before/after pair is one script run twice
against one tree, so nothing but the two lines differs.

### Criterion 2 — `GET /assumptions` with a document, and the trace out of it

**A 200 on the empty form proves the line, not the page.** `assumptions_page` renders the
same template on both branches, so the empty-form 200 above only shows the call site is
repaired. To exercise the branch a user actually hits — a real extraction, populated
defaults — I ran the route against a document. `c:/tmp/p5/assumptions_real.py`, nothing
stubbed: the repository's own `_extract_from_files` through the Foundry gateway, its own
`normalize_financials`, its own `derive_assumptions`.

```
cache BEFORE -> {}

  Provider: CLAUDE  |  Model: claude-opus-5  |  Transport: Microsoft Foundry gateway
  (apm-use-claudecode-pd.azure-api.net)  |  Credential: Entra ID token via
  DefaultAzureCredential (`az login`), scope https://cognitiveservices.azure.com/.default
  PDF: probe_filing_2024.pdf (0.0 MB)
  [Pass 1] Extracting financials (all years) + B/S...
  [Pass 1] Tokens - input: 4,506  output: 990
  ... 9 of 9 arithmetic reconciliations at +0 OK ...
  [Pass 2] No non-recurring items identified

GET /assumptions?ticker=PRBE&files=2024:probe_filing_2024.pdf  -> 200
content-type: text/html; charset=utf-8  bytes: 5759

cache AFTER  -> keys=['2024:probe_filing_2024.pdf']
   [2024:probe_filing_2024.pdf] years=[2022, 2023, 2024] ticker=PRBE
      2022: revenue=5291.0  ebit=1588.0  tax_expense=289.0  eff_tax=0.2099
            D&A=529.0  capex=-423.0  d_wc=-106.0
      2023: revenue=6349.0  ebit=1904.0  tax_expense=351.0  eff_tax=0.2101
            D&A=635.0  capex=-508.0  d_wc=-127.0
      2024: revenue=7619.0  ebit=2285.0  tax_expense=426.0  eff_tax=0.2100
            D&A=762.0  capex=-609.0  d_wc=-152.0

=== is this the error branch? ===
   ERROR BLOCK: none -- success branch

=== the derived defaults, as the route rendered them into the form ===
   revenue_growth         value=20.0, 20.0, 20.0, 20.0, 20.0
   operating_margin       value=30.0
   tax_rate               value=21.0
   da_pct                 value=10.0
   capex_pct              value=8.0
   nwc_pct                value=2.0
   terminal_growth_rate   value=2.5
```

**`STATUS.md` trap 2 says a 200 proves nothing on its own**, so here is the input side.
Every one of the six numbers the page rendered reproduces by hand from figures printed
on the document — none of them is a zero default:

| Rendered | Hand arithmetic from the page | Recomputed |
|---|---|---|
| `revenue_growth` 20.0 | CAGR `(7619 / 5291) ** (1/2) - 1` | **20.0 %** |
| `operating_margin` 30.0 | mean of `1588/5291`, `1904/6349`, `2285/7619` | **30.0 %** |
| `tax_rate` 21.0 | mean of `289/1377`, `351/1671`, `426/2029` | **21.0 %** |
| `da_pct` 10.0 | mean of `529/5291`, `635/6349`, `762/7619` | **10.0 %** |
| `capex_pct` 8.0 | mean of `423/5291`, `508/6349`, `609/7619` | **8.0 %** |
| `nwc_pct` 2.0 | mean of `106/5291`, `127/6349`, `152/7619` | **2.0 %** |

Recomputed with `.venv/Scripts/python.exe -c "... numpy.mean ..."`; the six lines printed
`20.0 30.0 21.0 10.0 8.0 2.0`. The document was built so each ratio is exact, which makes
the trace unambiguous rather than approximately right.

**The document is synthetic and every figure in it is invented.** `c:/tmp/p5/make_probe_pdf.py`
writes it with the header `SYNTHETIC PROBE DOCUMENT - NOT A REAL SEC FILING`, and the
figures (5291 / 6349 / 7619 …) are ones no previous unit has used. **This run is evidence
about the route and about nothing else.** There is still no real 10-K on this machine.

### The cache — the assignment's instruction was inaccurate, and I did not follow it

The brief and the assignment both say "**`GET /assumptions` reads** the module-global
extraction cache at `api/routes_valuation.py:25`; populate it in your scratch script".
Two things are wrong with that and I am correcting them rather than disputing, because
both are settled by execution:

```
$ grep -n "_extraction_cache" api/routes_valuation.py
31:_extraction_cache: dict[str, FinancialStatements] = {}     <- :31, not :25
102:            _extraction_cache[cache_key] = financials      <- assumptions_page WRITES
148:        if files in _extraction_cache:                     <- run_valuation READS
149:            financials = _extraction_cache.pop(files)
```

`assumptions_page` never reads the cache; there is no cache-hit branch in it. Pre-populating
the cache in my script would have changed nothing about the route's behaviour — the
run above prints `cache BEFORE -> {}` and `cache AFTER -> keys=[…]`, which is the write.
So the only way to reach the populated-defaults branch is a real extraction, and that is
what I did. **I did not change the route to make it testable**, which was the instruction
behind the sentence.

### Criterion 3 — all four call sites, read

```
$ grep -n "TemplateResponse(" api/*.py
api/routes_upload.py:42:    # starlette 1.6.0 removed the deprecated TemplateResponse(name, context) form;
api/routes_upload.py:48:    return templates.TemplateResponse(request, "upload.html")
api/routes_valuation.py:117:    return templates.TemplateResponse(request, "assumptions.html", {
api/routes_valuation.py:243:        # starlette 1.6.0 removed the deprecated TemplateResponse(name, context)
api/routes_valuation.py:248:        return templates.TemplateResponse(request, "valuation_result.html", {
api/routes_valuation.py:261:        return templates.TemplateResponse(request, "valuation_result.html", {
```

Six hits, **four calls**; `:42` and `:243` are comment text, not calls. All four calls
pass `request` first and a `str` second. `:248` and `:261` are `P2b-provider`'s and are
untouched — `git diff` below shows the only hunks are at `:42` and `:114`.

### Criterion 4 — the type gate, set-diffed and not counted

Baseline `c:/tmp/p5/mypy_before.txt` was taken on the clean `d885d8d` tree before the
edit, with the gate from `docs/8-build/environment.md`. Line numbers stripped, sorted,
`comm`'d.

```
before errors: 18   after errors: 14
--- ADDED (comm -13: in after, not in before) ---
--- (end added) ---                                 <- empty
--- REMOVED (comm -23: in before, not in after) ---
api\routes_upload.py:    Argument 1 to "TemplateResponse" ... expected "Request[State]"  [arg-type]
api\routes_upload.py:    Argument 2 to "TemplateResponse" ... expected "str"             [arg-type]
api\routes_valuation.py: Argument 1 to "TemplateResponse" ... expected "Request[State]"  [arg-type]
api\routes_valuation.py: Argument 2 to "TemplateResponse" ... expected "str"             [arg-type]
--- (end removed) ---
```

**Nothing added; the 14 are a strict subset of the 18, and the 4 removed are exactly the
two lines this unit changed.** By file:

| File | Before | After |
|---|---|---|
| `analysis/projector.py` | 4 | 4 |
| `api/routes_upload.py` | 3 | **1** |
| `api/routes_valuation.py` | 6 | **4** |
| `ingestion/claude_extractor.py` | 5 | 5 |
| **total** | **18** | **14** |

### Criteria 5, 6, 7 — the other three gates

```
$ .venv/Scripts/python.exe -m pytest -q
1 failed, 105 passed in 3.24s
FAILED tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent
$ .venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"
105 passed in 2.67s
$ .venv/Scripts/python.exe -m ruff check .
BLE001  api\routes_valuation.py:111  |  api\routes_valuation.py:259  |  cli.py:766
BLE001  ingestion\claude_extractor.py:934  |  tests\test_e2e_all_googl.py:106
Found 5 errors.
$ grep -rnE "<the rules.md census pattern>" --include=*.py models analysis api ingestion | wc -l
116
```

Identical to the baseline on the same tree in every case. The two `routes_valuation.py`
`BLE001` line numbers moved `111 → 111` and `247 → 259` relative to `STATUS.md`'s older
reading only because of intervening commits; both are the same two `except Exception`
blocks and neither is mine.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Dropped `"request": request` from the `assumptions.html` context, and passed **no** context at all on `upload.html` | starlette 1.6.0 does `context.setdefault("request", request)` itself. I did not take this from the `P2b` entry — I re-read `inspect.getsource(Jinja2Templates.TemplateResponse)` and then **proved it by execution**: a call passing no context returned `resp.context == {'request': <Request>}`, `is` the object I passed, 200, 1648 bytes | Keeping `{"request": request}` still works but tells the next reader the old form applies. `{}` would be noise. `templates/` was left untouched because no template reads it |
| Left `templates/` alone | `grep -rn "request" templates/` → exit 1, no hits; `grep -rn "url_for" templates/` → exit 1. All four pages then rendered 200 with their forms intact, which is the stronger check | The assignment allows a `templates/` edit only if a template reads `request`. None does |
| Added a 4-6 line comment above each call | Rule 4, and the shape `P2b-provider` set at `:243`. The next reader meets the reason for the argument order in the code | Silence is how the defect survived from `bc19431`. `STATUS.md` names it "the miss this unit closes" |
| Did **not** pre-populate the cache, as instructed | `assumptions_page` writes the cache and never reads it — the `grep` above. Pre-populating would have proved nothing | The instruction's intent ("do not change the route to make it testable") is honoured: the route is unmodified apart from its one call site |
| Ran one real extraction rather than stubbing | `STATUS.md` trap 2: the pipeline produces a page out of zeros, so "it rendered" is not evidence. Six rendered numbers now trace to printed figures | A stub would have proved the template renders, which the empty-form 200 already proved |
| Ran `POST /valuation` too | I edited `routes_valuation.py`. A route `P2b` proved at 200 must still be at 200 after my hunk | Reading the diff is not proof. It is 200, success branch — below |
| Did **not** exercise `POST /upload` | It writes a PDF into `<repo>/uploads/` (`config.py:11`, `UPLOAD_DIR = BASE_DIR / "uploads"`), outside my Files in scope | I asserted the form's `action="/upload"` on the rendered `GET /` body instead, and named the route as unreached below |

**No change in this unit was made to reach a target number.** The only figure it produced
is a probe share price from an invented document, declared meaningless below.

## The whole journey, in one process

`c:/tmp/p5/journey.py`. One extraction, three routes, real ASGI requests.

```
1. GET  /            -> 200  bytes=1648
   posts to          -> /upload
2. GET  /assumptions -> 200  bytes=5743
   cache written     -> ['2024:probe_filing_2024.pdf']
3. POST /valuation   -> 200  bytes=6969
   cache popped      -> []
   error block       -> none -- success branch
   Implied Share Price    $77.42
   Provider               CLAUDE
   Transport              Microsoft Foundry gateway (apm-use-claudecode-pd.azure-api.net)
```

The cache round-trips: `/assumptions` writes the key, `/valuation` pops it, so the second
route ran on the first route's extraction and made no second model call. `P2b-provider`'s
labelling block still renders. **`$77.42` is meaningless as a valuation** — the statements
are invented and only the market-data leg (MSFT's) is real. It is evidence that the three
routes connect, and about nothing else.

**No credential leaked onto any rendered page.** `re.search("sk-ant|Bearer |eyJ[A-Za-z0-9_-]{10,}")`
over all four saved bodies → `leak=False` on each.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `request`, now the first argument to both calls | **cannot be missing.** It is a declared route parameter FastAPI injects; without it the route does not start | `upload_page(request: Request)` `api/routes_upload.py:40`; `assumptions_page(request: Request, …)` `api/routes_valuation.py:76` |
| the `assumptions.html` context dict (`ticker`, `company_name`, `files`, `defaults`, `error`) | **unchanged by this unit.** Every key is built above my line and I removed none of them; only `"request"` left, and starlette re-supplies it | `git diff` — the hunk deletes one line and adds the call plus a comment. Proved live: `resp.context == {'request': …}` on an omitted context |

**No "defaults to" row, and no new one added.** No added line matches the census or
rule-2 patterns:

```
$ git diff -U0 HEAD -- api/ templates/ | grep "^+" | grep -E "if [^)]+ else 0(\.0)?\b|\bor +(0|0\.0)\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0|\*\*kwargs|getattr\("
exit=1        (no output)
```

Census **116 → 116**.

## Rules 1, 2, 4, 5, 6

- **Rule 1.** No prompt, schema field or extractor code was touched. The change is two
  response constructors.
- **Rule 2.** No dispatch table, no `**kwargs`, no `getattr` added. `TemplateResponse` is
  a literal call with positional arguments a reviewer can read in git.
- **Rule 4.** Unchanged either way. `assumptions.html` still shows derived defaults with
  no chain back to the lines they came from — I reconstructed that chain by hand above
  precisely because the page does not show it. That gap is not this unit's.
- **Rule 5.** No statement figure moved. `api/routes_valuation.py:197` (the yfinance
  `sharesOutstanding` fallback) is untouched and still a rule-5 break.
- **Rule 6.** `P2b`'s labelling block still renders, shown above. This unit adds no
  assumption.

## Measurements

| Gate | `d885d8d`, clean tree | After the two lines | Verdict |
|---|---|---|---|
| Tests | `1 failed, 105 passed` | **`1 failed, 105 passed`** | identical failure set: `test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` |
| Tests, gate form | `105 passed` | **`105 passed`** | unchanged |
| Lint | 5, all `BLE001` | **5, all `BLE001`** | same five locations |
| Types | 18 errors, 4 files | **14 errors, 4 files** | `comm -13` empty; 4 removed are this unit's two lines |
| Rule-3 census | 116 | **116** | unchanged |
| `GET /` | **500** | **200** | criterion 1 |
| `GET /assumptions` | **500** | **200** | criterion 2 |
| `POST /valuation` | 200 | **200** | no regression |

Diff: **2 files, 2 call sites, 11 insertions / 3 deletions**, of which 9 insertions are
comments. Both files are in Files in scope.

**The gate changed meaning, as the assignment predicted.** `import app` succeeding is no
longer the strongest available check on the web half — it passed through the entire
outage, `bc19431` to `d885d8d`. The strongest check is now:

```
.venv/Scripts/python.exe -c "from starlette.testclient import TestClient; import app; \
  print(TestClient(app.app, raise_server_exceptions=False).get('/').status_code)"
```

→ **200**. That belongs in `STATUS.md` section 1 as a gate, not as a note; the
orchestrator owns that file.

**Why it was a bare 500 and not a message.** The `assumptions.html` call sits below a
blanket `except Exception` (`api/routes_valuation.py:111`) whose handler renders the error
onto a page — through the very call that was broken. So the error page could not render
either, and starlette returned its 21-byte default. `routes_upload.py` has no handler at
all. This is the clearest argument in the repository for **backlog item 8**: the catch did
not merely hide one exception, it hid a total outage of two routes for the whole life of
the repository, and the lint gate had been printing `BLE001` on that exact line the entire
time.

**Cleanup.** `TestClient` opens no listening socket; there is no server to stop. All
scratch is outside the repository: `c:/tmp/p5/{http_probe,assumptions_real,journey,make_probe_pdf}.py`,
`c:/tmp/p5/probe_filing_2024.pdf`, `c:/tmp/p5/body_*.html`,
`c:/tmp/p5/mypy_{before,after}.txt`, `c:/tmp/p5/{before,after}.set`. Nothing was copied
into the repository; `git status` shows `api/routes_upload.py`, `api/routes_valuation.py`
and this entry, and nothing else.

## What I did not do

- **`POST /upload` is not reached, and it is the one route with no HTTP proof.** It writes
  into `<repo>/uploads/`, outside my Files in scope. It renders no template, so it was
  never affected by this defect, but it is the hinge between the two routes I did fix and
  it has never been exercised — and `_guess_fiscal_year` returning `None` feeds the
  `f"{year or 0}:{path}"` at `:61`, a rule-3 bare-or-default on the path a user takes.
  **The tester that follows should lock it**, with `UPLOAD_DIR` redirected.
- **Did not touch the two `valuation_result.html` calls.** Verified untouched by `git diff`,
  and re-proved at 200.
- **Did not touch `tests/`.** `api/` still has no tests, and all three routes I exercised
  are now proved only by a scratch script that will be deleted.
- **Did not repair the cache, the blanket catches, the falsy conversions, the yfinance
  fallback or the remaining 14 type errors.** Backlog items 5, 8, 6, 1/12 and 11, all
  named out of scope.
- **Did not update `STATUS.md`, `docs/9-reference/refactor-backlog.md` or the journal
  index.** Orchestrator's. Backlog item 27 is now closeable and `STATUS.md` section 1b's
  table needs both rows moved to 200.

## Findings for the orchestrator

1. **`STATUS.md`'s by-file type-error breakdown does not sum to its own total.** Section 1
   says "`api/routes_valuation.py` 8, `ingestion/claude_extractor.py` 5,
   `api/routes_upload.py` 4, `analysis/projector.py` 4" = **21**, against a stated total of
   18. Measured at `d885d8d` the split is `routes_valuation` 6, `claude_extractor` 5,
   `projector` 4, `routes_upload` 3 = **18**. Related: section 1b's "The remaining 4 in
   `api/routes_upload.py` are the last broken template call" is wrong in the same place —
   the file held 3 errors, of which **2** were the template call; the other 2 of the 4 were
   in `routes_valuation.py`. The correct total is right, the attribution is not.

2. **The assignment's cache instruction was inaccurate and a less careful agent would have
   changed the route to satisfy it.** It says `GET /assumptions` *reads* the cache at
   `:25`; the route *writes* it at `:102` and the line is `:31`. An agent that pre-populated
   the cache, saw no effect, and concluded the route was still broken could have "fixed"
   `assumptions_page` to add a cache-hit branch — which is backlog item 5's territory.
   Worth correcting wherever it is restated.

3. **`_guess_fiscal_year` → `f"{year or 0}:{path}"` is a live rule-3 site on the user's
   only path into the app** (`api/routes_upload.py:36` and `:61`). A filename with no
   4-digit year yields `None`, becomes year `0`, and `_extract_from_files:66` then filters
   the file out of the multi-file path — so uploading two correctly-named PDFs and one
   badly-named one silently values the company on two years. It is inside the 116 census.
   **Until this unit, that path was unreachable and so untestable.** It is reachable now.

4. **`run_valuation:152` still cannot accept a Windows absolute path** (`P2b` finding 2,
   still open, now more urgent). `POST /upload` passes exactly such a path —
   `C:\...\uploads\TICKER\x.pdf` — so the journey `GET /` → `POST /upload` →
   `GET /assumptions` will hand `_parse_files_param` a string whose first `:` is a drive
   letter and `int("C")` will raise. **I could only prove the journey by bypassing
   `POST /upload` with a bare relative filename.** `P2b` wrote "it may be masked today only
   because `routes_upload.py` is itself broken" — `routes_upload.py` is no longer broken, so
   this is now the next thing a real user will hit. It needs an item and it is the natural
   successor to this unit.

5. **Two routes just became testable that never were.** `api/` has no tests at all. The
   four assertions worth locking, in order: `GET /` is 200 and its body contains
   `action="/upload"`; `GET /assumptions` with no `files` is 200; every
   `templates.TemplateResponse(` call in `api/` passes a `Request` first (a source-level
   test would have caught this defect at `bc19431` and costs three lines); and
   `_guess_fiscal_year(None-yielding-name)` must stop rather than return `0`.
