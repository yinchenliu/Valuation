---
agent: tester
assignment: P5b-route-tests
round: 1
status: complete
files_touched: [tests/unit/test_routes.py]
verdict: pass
escalation: "a rule-3 stop path in the routes defaults instead of stopping and is NOT recorded in the backlog — api/routes_valuation.py:131 with :154. Not asserted in either direction. See 'Escalations'."
---

# P5b-route-tests — lock every route on status AND body, and prove the lock bites

Measured at `b2ab32f`, working tree, 2026-09-21. Every figure below is from a command
I ran in this session. Nothing is carried from the programmer's or the reviewer's entry.

## What I did

Wrote `tests/unit/test_routes.py`: 14 test functions, 15 collected cases, 104 `assert`
statements, covering all four routes on **status code and body**, both error branches
that exist, and the three HTTP-level stop paths. Every expected value was derived before
the code ran — hand arithmetic over round inputs, or a contract stated somewhere other
than the path under test (a route's own `Form(...)`/`File(...)` declaration, the
redirect target's parser, `docs/8-build/environment.md` section 3). Then I proved the
tests are falsifiable by reverting the `TemplateResponse` calls in a copy of the tree at
`c:/tmp/p5b_rev` and re-running: **11 of 15 cases go red, and the 105 pre-existing tests
all still pass on that same broken copy, as does `import app`.**

**No expected value was adjusted after seeing a run.** The first `pytest` invocation of
the file returned `15 passed`. The only edits after it were three lint/readability fixes
(`import` form, `re.S` → `re.DOTALL`, an `AttributeError` turned into a named assert, a
redundant ternary removed). No assertion's right-hand side was touched at any point.

## Two counts, with their units

| Count | Value | Unit |
|---|---|---|
| **Accuracy** | **122 / 122** | assertion *executions* (104 `assert` statements; loops over `EXPECTED_DEFAULTS` and the parametrised stop test expand to 122). Every one matched an expectation written before the run. |
| **Coverage — functions** | **8 / 8** | functions in `api/`: `_save_upload`, `_guess_fiscal_year`, `upload_page`, `upload_files`, `_parse_files_param`, `_extract_from_files`, `assumptions_page`, `run_valuation`. Plus `app.py`'s module body, which no test had ever imported. |
| **Coverage — statements** | **130 / 138** | statements in `api/` + `app.py`. Was **0 / 126** before this file: `api/` had no test at all, and coverage warned `Module app was never imported`. |
| **Coverage — branches** | **16 / 22** | branch arcs in `api/` + `app.py`; 6 partial. The six are listed below with the reason each is deliberate. |

Commands:

```
COVERAGE_FILE=/c/tmp/.cov_mine .venv/Scripts/python.exe -m pytest -q tests/unit/test_routes.py \
  --cov=api --cov=app --cov-branch --cov-report=term-missing
api\routes_upload.py      33   0   2  0  100%
api\routes_valuation.py   93   8  20  6   88%   40, 69-70, 92, 151, 160->163, 199-201
app.py                    12   0   0  0  100%
TOTAL                    138   8  22  6   91%          15 passed

# the same measurement with my file excluded — the baseline this unit moved:
COVERAGE_FILE=/c/tmp/.cov_base ... --ignore=tests/unit/test_routes.py
api\routes_upload.py      33  33  0%   3-70
api\routes_valuation.py   93  93  0%   3-261
TOTAL                    126 126  0%                   105 passed
```

**The six uncovered arcs, each on purpose:**

| `file:line` | What it is | Why no test touches it |
|---|---|---|
| `routes_valuation.py:40` | `if not entry: continue` in `_parse_files_param` | an empty `files` entry; part of the `files`-is-absent question I am reporting, not pinning |
| `:69-70` | `if not valid:` — multi-file with no year, falls back to the first file | **a fallback.** Asserting it would make it permanent. `strategy.md` section 2 |
| `:92` | the legacy `file_path` branch | superseded by `files`; backlog item 26 names it as the one live route into the `int()` crash. Pinning it would fix its shape in place |
| `:151` | `_extraction_cache.pop(files)` — the cache **hit** | backlog item 5. Every test starts from an empty cache and takes the miss branch on purpose, so item 5's fix cannot turn one red |
| `:160->163` | `revenue_growth` blank | the blank case routes into `derive_assumptions`' historical path, which is item 6 territory |
| `:199-201` | `shares == 0` → `yfinance` `info.get("sharesOutstanding", 0)` | **a fallback and a rule-5 break at once.** A test here would lock a filing figure being taken from a market feed. Reported, not asserted |

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | all four routes locked on status **and** body | **pass** — 4 routes | the route table below |
| 2 | the error branch of each template-rendering route locked at 200 | **pass, with the count corrected: 2, not 3** | only two of the three template-rendering routes *have* an error branch. Both are locked. See "Criterion 2's third route does not exist" |
| 3 | the suite passes | **pass — 120 passed, 0 failed** (105 + 15) | `pytest -q --ignore-glob="*_rule3_red.py"` → `120 passed` |
| 4 | the whole suite unchanged in shape | **pass — 1 failed, 120 passed**, same single test | `pytest -q` → `FAILED tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`, `1 failed, 120 passed`. Before my file: `1 failed, 105 passed`, **the identical failure set** |
| 5 | **the test is falsifiable** | **pass — 2 cases / 10 of 10 assertions red** on the assigned revert; **11 of 15 cases** red when all four call sites are reverted | the two scratch runs below |
| 6 | no test needs a key, a PDF or the network | **pass** | `env -u ANTHROPIC_API_KEY -u ANTHROPIC_FOUNDRY_BASE_URL -u ANTHROPIC_FOUNDRY_RESOURCE -u ANTHROPIC_FOUNDRY_API_KEY -u GEMINI_API_KEY ... pytest -q --ignore-glob="*_rule3_red.py"` → **120 passed**. There is no `.env` in this tree |
| 7 | nothing written into the repository | **pass** | `git status --short` → three untracked paths only: this entry, the assignment, `tests/unit/test_routes.py`. `ls -la uploads/` → empty. `git check-ignore -v uploads` → `.gitignore:5:uploads/` |
| 8 | `tests/` lints with exactly 1 error | **pass — 1** | `ruff check tests --output-format concise` → `tests\test_e2e_all_googl.py:106:16: BLE001`, `Found 1 error.` Whole tree: `Found 5 errors`, all `BLE001` — unchanged |

### Criterion 5 in full — the number that decides whether this unit is worth anything

Scratch copy of the working tree at `c:/tmp/p5b_rev` (everything but `.venv`, `.git`,
`10K_filings`, `uploads`). **Run 1**, the revert the assignment named — `api/routes_upload.py:48`
put back to the removed `TemplateResponse("upload.html", {"request": request})` form:

```
GET / -> 500, 21 bytes, b'Internal Server Error'
FAILED test_get_root_serves_the_upload_form                             assert 500 == 200
FAILED test_the_form_on_the_front_page_is_accepted_by_the_route_it_targets
                             AssertionError: the front page offered no form: 'Internal Server Error'
2 failed, 13 passed
```

A pytest case stops at its first failing assert, so "2 failed" understates it. I
evaluated each of `test_get_root_serves_the_upload_form`'s conditions independently
(`c:/tmp/count_red.py`): **10 of 10 red** — status, the absence of `Internal Server
Error`, the `<form>` itself, its `action`, `method` and `enctype`, all three input names
and the `type="file"`.

**Run 2**, all four call sites reverted (`upload.html`, `assumptions.html` and both
`valuation_result.html` calls):

```
11 failed, 4 passed
```

The 4 that stay green are the only 4 that render no template: the `POST /upload`
redirect and the three 422 stop cases. That is the correct answer, not a gap.

**And the control, on the same fully broken copy:**

```
pytest -q --ignore-glob="*_rule3_red.py" --ignore=tests/unit/test_routes.py   ->  105 passed
python -c "import app"                                                        ->  import app: OK
```

Every route 500, the suite green, and the done-criterion that was used during this build
still reporting success. That is backlog item 27 reproduced, and it is the thing this
file removes.

## The route table — status and body, for each route

| Route | Status asserted | Body asserted | Where the expected value came from |
|---|---|---|---|
| `GET /` | 200 | the `<form>`'s `action="/upload"`, `method="post"`, `enctype="multipart/form-data"`, and inputs named `ticker`, `company_name`, `pdf_files` with `pdf_files` of `type="file"` | the **declared signature** of `POST /upload`, `api/routes_upload.py:51-57`. A form that does not POST multipart to `/upload` with those three names cannot reach that route, whatever the page looks like |
| `GET /` → `POST /upload` | ≠ 422, and 303 | — | the form is read *off the rendered page* and submitted back to the action it names. 422 is FastAPI's answer to an absent declared field, so "the page offers what the route requires" is checkable without knowing either page's text |
| `POST /upload` | 303 | `Location` path is `/assumptions`; `ticker=GOOGL` from `googl`; `files` is `2024:<path>`; the file is on disk with the bytes uploaded | `status_code=303` is declared at `routes_upload.py:76`; `ticker.upper()` and `UPLOAD_DIR/<TICKER>/` are the route's contract; `2024` is `_guess_fiscal_year`'s docstring ("a 4-digit year from the filename") and the `year:path` shape is what the *receiving* parser expects (`_parse_files_param`, `routes_valuation.py:34-43`) |
| `POST /upload` → `GET /assumptions` | 200 | `Valuation Assumptions: TESTCO`; the extractor is handed exactly the file that was saved | outcome, not branch: the drive-letter colon must survive the round trip. Backlog item 26 may change *how* `files` is parsed without changing *which* file is read |
| `GET /assumptions` | 200 | the six derived defaults in the form: `20.0, 20.0, 20.0, 20.0, 20.0` / `20.0` / `25.0` / `10.0` / `5.0` / `2.0`, plus the `files` and `ticker` round-trip, plus no `alert-error` | **hand arithmetic** — see the table below |
| `GET /assumptions`, two filings | 200 | the same six defaults; the two `(year, path)` pairs reach `extract_multi_year` in order | `_extract_from_files`' docstring; the defaults as above |
| `GET /assumptions`, extraction fails | **200** | `alert-error` present, the failure's text visible, page identity intact, and **no number invented** into any of the five numeric fields | the requirement is "a failure is reported to the reader on a rendered page, not as a blank 500" — backlog item 27. Independent of *how* the route catches it |
| `GET /assumptions`, no filing named | 200 | that a form posting to `/valuation` rendered. **Nothing about what the page says** | item 27's "no route answers 500" only. Deliberately silent so the rule-3 finding below can be fixed without turning this red |
| `POST /valuation` | 200 | 31 assertions: the three summary cards, nine CAPM/WACC rows, the eight projection cells, eight bridge rows, eight assumption rows | **hand arithmetic** — the full chain is written out below |
| `POST /valuation` | 200 | provider `CLAUDE`, model `claude-opus-5`, transport names the public Anthropic API and **not** Foundry, credential names `ANTHROPIC_API_KEY` | `docs/8-build/environment.md` section 3: the one provider default, the default Claude model, and the transport table |
| `POST /valuation`, Foundry configured | 200 | transport names the Foundry gateway and its host and **not** `api.anthropic.com`; the placeholder key does not appear anywhere in the page | rule 6 — "the same model over a company gateway and over the public API must be distinguishable by the reader" — and `ProviderResolution`'s "no field holds a key or a token" |
| `POST /valuation`, the run fails | **200** | `alert-error`, the failure's text, page identity intact, and **no `big-number` and no "Implied Share Price" anywhere** — a failed run must not show a price | item 27, and rule 3's spirit: no figure for a run that did not happen |

## Expected values — every one, and where it came from

### `GET /assumptions` — the derived defaults

Inputs built by hand in the test: two years whose every ratio is identical, so every
average *is* that ratio and no long division is needed.

| Assertion | Expected | Hand arithmetic |
|---|---|---|
| `revenue_growth` | `20.0, 20.0, 20.0, 20.0, 20.0` | CAGR over the one available step = (1200/1000)^(1/1) − 1 = **20.0%**; `projection_years` defaults to 5 (`models/valuation.py:155`), so five entries |
| `operating_margin` | `20.0` | mean(200/1000, 240/1200) = mean(20%, 20%) |
| `tax_rate` | `25.0` | mean(50/200, 60/240) = mean(25%, 25%) |
| `da_pct` | `10.0` | mean(100/1000, 120/1200) |
| `capex_pct` | `5.0` | mean(50/1000, 60/1200) |
| `nwc_pct` | `2.0` | mean(20/1000, 24/1200); the CFS sign is negated, `projector.py:86-97` |

### `POST /valuation` — the whole chain

Inputs: one year, revenue 1000, 100 m diluted shares, debt 500, cash 100, price 45.00.
Every assumption is supplied explicitly on the form, so nothing is derived from history.
Formulas from the `analysis/` module docstrings and `docs/3-architecture/valuation-math.md`.

| Assertion | Expected | Hand arithmetic |
|---|---|---|
| projection row | `2025 · 1,100 · 220 · 165 · 110 · 55 · 22 · 198` | revenue 1000×1.10 = 1100; EBIT 1100×20% = 220; NOPAT 220×0.75 = 165; D&A 110; CapEx 55; ΔNWC 22; FCFF 165+110−55−22 = **198** |
| Cost of Equity | `10.00%` | CAPM: Rf + β·ERP = 4% + 1.0×6% |
| Beta / R² / Rf / ERP | `1.000` / `0.000` / `4.00%` / `6.00%` | `beta_override` is given, so the regression is skipped and its diagnostics are zero by construction (`capm.py:82-85`); the other two are the form inputs ÷ 100 |
| Cost of Debt | `6.00%` | the override, ÷ 100 at the route boundary |
| Tax Rate (WACC) | `25.00%` | the override, ÷ 100, below the 50% clamp |
| E/V, D/V | `90.0%`, `10.0%` | E = 45.00 × 100 = 4500; D = 0+0+500 = 500; V = 5000 |
| **WACC** | `9.45%` | 0.9×10% + 0.1×6%×(1−25%) = 9% + 0.45% |
| PV of FCFFs | `181` | 198 / 1.0945 = 180.90 |
| Terminal Value | `2,711` | 198 × 1.02 / (0.0945 − 0.02) = 2710.87 |
| PV of TV | `2,477` | 2710.87 / 1.0945 = 2476.81 |
| Enterprise Value | `2,658` | 180.90 + 2476.81 = 2657.72 |
| Less: Net Debt | `(400)` | 500 − 100 − 0 |
| Equity Value | `2,258` | 2657.72 − 400 = 2257.72 |
| Diluted Shares | `100` | the input |
| Implied Share Price | `$22.58` | 2257.72 / 100 = 22.577 |
| Current Price | `$45.00` | the input |
| Upside / Downside | `-49.8%` | (22.577/45 − 1) × 100 = −49.83% |
| Assumptions Used, 8 rows | `1`, `2.00%`, `10.0%`, `20.0%`, `25.0%`, `10.0%`, `5.0%`, `2.0%` | the form inputs, ÷ 100 at the route boundary and × 100 again for display — a round trip that must return what was sent |

I checked this arithmetic twice: once on paper before writing the test, and once with
`c:/tmp/p5b_arith.py`, a 30-line script that **evaluates the formulas directly and
imports nothing from this repository**. The two agree, and the first pytest run agreed
with both.

### The provider block

| Assertion | Expected | Source |
|---|---|---|
| Provider | `CLAUDE` | `docs/8-build/environment.md` §3: "`config.DEFAULT_EXTRACTION_PROVIDER` is `"claude"`, and it is the only provider default in the repository" |
| Model | `claude-opus-5` | same, "The default Claude model is **`claude-opus-5`**" |
| Transport, no Foundry var | contains `Anthropic`, contains `api.anthropic.com`, does **not** contain `Foundry` | same, the transport table: "neither → the public Anthropic API" |
| Transport, `ANTHROPIC_FOUNDRY_BASE_URL` set | contains `Foundry` and the host, does **not** contain `api.anthropic.com` | same table, and rule 6 |
| the key string | absent from the whole page | `ProviderResolution`'s contract: "No field holds a key or a token" |

## Rule 3 — what stops, and what does not

### Stop paths locked

| Route | Input removed | Result asserted | The field its message names |
|---|---|---|---|
| `POST /upload` | `ticker` | **422**, body names the field | `ticker` |
| `POST /upload` | `pdf_files` | **422**, body names the field | `pdf_files` |
| `POST /valuation` | `ticker` | **422**, body names the field | `ticker` |

These are the only three inputs across the four routes declared without a default
(`Form(...)` / `File(...)`). FastAPI's 422 body carries `{"loc": ["body", "ticker"], …}`,
so the stop names the field — the HTTP-boundary form of rule 3.

### Stop paths I could NOT lock, because the code defaults

| `file:line` | The default | What happens instead of a stop | Recorded? |
|---|---|---|---|
| `api/routes_valuation.py:131` `files: str = Form("")`, with `:154` | `""` → `[(0, "")]` | **the extractor is called with an empty path.** Measured: `POST /valuation` with `ticker` only → HTTP 200, `extract_financials` received `''`, and the word `files` appears nowhere on the page | **NO. This is new** — see Escalations |
| `api/routes_valuation.py:80,82` `files`/`file_path` default `""`, with `:94` | `[]` | a blank assumptions form renders and reports nothing | partially — the *page* is fine on first visit; the pairing with the row above is what makes it a defect |
| `api/routes_valuation.py:135-139` with `:167-175` | `0` → `None` | a user who types a genuine `0%` margin silently gets the historical average | backlog item **6** |
| `api/routes_valuation.py:198-201` | `info.get("sharesOutstanding", 0)` | shares — the denominator of the headline figure — are taken from **yfinance** when the filing says zero | backlog item **1** (the `api/` census) and **rule 5** |
| `api/routes_upload.py:67` | `f"{year or 0}:{path}"` | an unguessable fiscal year becomes `0` | backlog item **1** |
| `analysis/dcf.py:80` | `net_debt = … if latest_bs else 0.0` | reached through `POST /valuation` | backlog item **2**, red test already exists |

**I asserted none of these in either direction.** `strategy.md` section 2: a test that
locks a fallback makes it permanent and turns its fix red.

## Criterion 2's third route does not exist

The criterion says "the error branch of each template-rendering route" and expects 3.
There are three template-rendering routes and **two** error branches:

| Route | Renders | Error branch | Locked? |
|---|---|---|---|
| `GET /` | `upload.html` | **none.** `api/routes_upload.py:39-48` is four lines with no `try`, no parameter but `request`, and nothing that can fail | n/a — there is no branch to lock. I lock it against the 500 that actually happened instead |
| `GET /assumptions` | `assumptions.html` | `api/routes_valuation.py:111-112` | **yes** |
| `POST /valuation` | `valuation_result.html` (twice) | `api/routes_valuation.py:259-271` | **yes** |

So the honest measurement is **2 of 2 that exist**, not 3 of 3. I did not fabricate a
third by making a template fail — that would test jinja, not the route. Flagging rather
than silently substituting, per my instructions.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| assert the *body*, never the status alone | the assignment; all four routes answer 200/303 and the error page answers 200 too | a status-only test is exactly the blindness that let the outage hide |
| `raise_server_exceptions=False` | the outage surfaced to users as HTTP 500 | with the default, a broken route raises into pytest as an error; asserting `500 != 200` reproduces what a browser saw |
| every boundary fails loudly by default in the `client` fixture | `strategy.md` §3 | a test that forgets its fake would otherwise reach the network or a key; now it cannot |
| the provider environment is pinned in the fixture | criterion 6 | `resolve_provider` reads `os.environ`, so an unpinned test would pass on my machine (Foundry configured) and fail on a machine without it, or vice versa |
| `_extraction_cache` rebound to a fresh dict, `raising=False` | backlog item 5 | every `POST /valuation` takes the **miss** branch, so neither the current `pop` nor its removal can change a result. `raising=False` because item 5's fix may delete the global |
| `files` carries a Windows drive letter in every test that uses it | backlog item 26 | the assertion is on the *outcome* — the extractor gets the path the user named — so a change to the parser cannot turn it red while the behaviour stays right |
| the "no filing named" test asserts only "not 500" | the rule-3 finding above | if that finding is fixed and the page starts saying "no filing named", this test must stay green |
| `test_post_valuation_renders_the_completed_valuation` asserts 31 values, not a marker | criterion 1 | a marker proves a template rendered; the bridge proves the *right* page rendered with the right numbers. Both error tests assert markers plus absence, which is the complementary half |

## Which branch each `POST /valuation` test took

All three: the **cache-miss** branch (`api/routes_valuation.py:152-156`). No test issues
a prior `GET /assumptions` with the same `files` value, and the cache is a fresh empty
dict per test, so a miss is guaranteed whatever item 5 does later. The hit branch at
`:151` is the one uncovered line I am reporting rather than exercising.

## Backlog item 24 — the check the tester card asks for on every visit

`tests/unit/` holds exactly one `*_rule3_red.py`: `test_dcf_rule3_red.py`, and it is
**still red** (`1 failed` in the full-suite run), so it is correctly named and correctly
excluded. `test_normalizer_stops.py` is green and is *not* inside the pattern, so the
gate runs it. Nothing to move.

## Escalations

### E1 — a rule-3 stop path defaults, and it is not in the backlog · `major`

`POST /valuation` with `files` absent does not stop and does not name `files`.

```
api/routes_valuation.py:131   files: str = Form("")
api/routes_valuation.py:154   filings = _parse_files_param(files) if ":" in files else [(0, files)]
```

Measured (`c:/tmp/p5b_finding.py`, extractor faked so nothing reaches a model):

```
POST /valuation  data={"ticker": "TESTCO"}     ->  HTTP 200
extract_financials received pdf_path = ''
the word "files" appears nowhere in the rendered page
```

The run proceeds to the extraction boundary with an empty path. In production the user
sees whatever message the file-open produces — a message about a path, never about the
field they failed to supply. **This is not backlog item 26** (that is the `":" in files`
branch shape) and **not item 1** (whose `api/` census is 2 sites, both different, and
whose grep pattern does not match a `""` default). It is unrecorded.

**Why this matters for my verdict.** `.claude/agents/tester.md`'s four-outcomes table
says a stop path that defaults instead of raising is a `fail`. I have recorded `pass`
because every done-criterion of *this* unit passes and this defect is in code the
assignment puts out of scope and the `P5-web-routes` diff never touched — the repository's
own convention is that a pre-existing defect is not a finding against the unit that
found it. **The orchestrator should decide**: either open a backlog item for it, or
re-dispatch this unit with the rule-3 state of `api/` in scope, in which case the verdict
above should be read as `fail`. I did not write the red test for it because a
`*_rule3_red.py` file is outside this unit's Files in scope.

### E2 — criterion 2 expects three error branches; two exist

See the table above. Not a defect in the code or the tests; the criterion's count is
wrong. No action needed beyond not treating "2" as a shortfall.

## What I did not do

- **Did not assert the cache-hit branch, the `valid`-is-empty fallback, the legacy
  `file_path` branch, or the yfinance share-count fallback.** Each is a fallback or a
  recorded item; asserting any would make it permanent. Listed above with reasons.
- **Did not write a red test for E1.** Files in scope is `tests/unit/test_routes.py` and
  a shared `conftest.py`; a `*_rule3_red.py` is neither. Reported instead.
- **Did not add `tests/unit/conftest.py`.** The assignment allows it "only if fixtures
  are shared across files". They are not — one file, so the fixtures live in it.
- **Did not touch any existing test file**, including `test_dcf_rule3_red.py`.
- **Did not run `mypy`.** The type gate's file list (`models analysis ingestion api
  config.py app.py`) does not include `tests/`, so this unit cannot move it.

## Findings for the orchestrator

1. **E1 above** — a new, unrecorded rule-3 site at `api/routes_valuation.py:131` + `:154`.
   Worth a backlog entry; it is the same class as item 6 but on a *path*, not a number,
   and the whole valuation depends on it.
2. **`import app` should be struck from every done-criteria list.** Measured again here,
   on a tree where all four routes 500: `import app: OK` and `105 passed`. `STATUS.md`
   §1 already says this; this run is independent confirmation, and it is now cheap to
   replace — `pytest -q tests/unit/test_routes.py` is 3 seconds and fails on all four.
3. **`api/` had 0% coverage of 126 statements before this file and `app.py` was never
   imported by the suite.** That is now 91% of 138 with branch coverage on. If a future
   unit adds a route, the same shape of test is ~20 lines; there is no infrastructure to
   build.
4. **Scratch left behind, outside the repository**, if anyone wants to re-run the
   falsification: `c:/tmp/p5b_rev` (the reverted tree), `c:/tmp/count_red.py` (the
   assertion-by-assertion count), `c:/tmp/p5b_arith.py` (the independent arithmetic),
   `c:/tmp/p5b_finding.py` (E1's evidence). Nothing under `c:/tmp` is referenced by any
   test; the suite does not need them.
