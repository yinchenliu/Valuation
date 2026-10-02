---
agent: tester
assignment: P9b-route-tests
round: 1
status: complete
files_touched: [tests/unit/_session_route_helpers.py, tests/unit/test_routes_session.py, tests/unit/test_routes_session_rule3_red.py]
verdict: fail
---

# P9b-route-tests: tests for /upload-session, the session_file routes and the recorded label

Base commit `dce8d42`; the code under test was accepted at `be1c077`. Run on macOS with
`.venv/bin/python` (Python 3.11.6), starting 2026-10-02T1713. P9d-pass2-checks was changing
`ingestion/session_extraction.py` (and docs) in the same working tree while I worked.
Every test here uses a well-formed Pass 2, and none of them depends on that change.

**Verdict `fail`, for one reason only: backlog item 52.** Every value asserted in the
green file matches its independently derived expectation. Every stop path the
assignment names is locked, except one. On a cache hit, `POST /valuation` with both
`session_file` and `files` **does not stop**. It values the cached session file and
drops `files` without saying so (`api/routes_valuation.py:544`). The assignment asked
for that case as a red test (item 8), and it is one. Under this contract, a stop path
that the code skips instead of raising is a `fail`. Nothing else in the unit fails.

## What I did

I wrote 24 tests in two files and added one helper module, so that every proof
P9b-session-web's programmer and reviewer ran as a `/tmp/` script now lives in `tests/`.

- `tests/unit/_session_route_helpers.py` is not collected (the leading underscore). It
  holds the hand-written session file: one filing, ticker `TST`, company `Test Co`,
  model ID `model-id-declared-in-the-test-session`, 2023 revenue 1,000 and 2024 revenue
  2,000, plus one well-formed `low`-confidence Pass 2 item. It also holds a PDF of a few
  bytes under `tmp_path`, hashed with `hashlib`, and the boundary stubs.
- `tests/unit/test_routes_session.py`: 23 tests, all green.
- `tests/unit/test_routes_session_rule3_red.py`: 1 test, red on purpose (backlog item 52).

No test reaches the API, the network, `.env` or `10K_filings/`:

- `_call_llm`, the route module's `fetch_price_data` and `yfinance.Ticker` are replaced
  with functions that raise.
- Every credential variable is removed **after** `config` is imported, so that
  `load_dotenv(override=True)` has already run (backlog item 46).
- `routes_upload.UPLOAD_DIR` points at `tmp_path/uploads`.
- The route A stub answers only the exact (system prompt, user prompt, PDF bytes)
  triples that `pass1_prompts` / `pass2_prompts` give for the one-filing plan, and only
  on `anthropic-direct`. Anything else raises.
- The price stub answers only `("TST", 5, "monthly")`.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the eight groups exist, ≥ 1 test each | **pass** | `.venv/bin/python -m pytest --collect-only -q tests/unit/test_routes_session.py tests/unit/test_routes_session_rule3_red.py` → `24 tests collected`. By group: 1 → 2 tests, 2 → 6 (one parametrised ×2), 3 → 4, 4 → 2, 5 → 2, 6 → 4, 7 → 2, 8 → 1 red + its cache-miss half (1 green) |
| 2 | every expected value has a written source | **pass** | each test's docstring or the comment above each assertion names the source. See "Expected values" below |
| 3 | the gate | **pass** | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` → `1 failed, 376 passed`. Before: `1 failed, 353 passed`. The failure set is unchanged: `{test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}` (item 45, held by the user). +23 = the 23 green tests. The one red test sits in `test_routes_session_rule3_red.py`, and its docstring gives the reason |
| 4 | `api/` coverage, measured with `COVERAGE_FILE` under `/tmp/` | **pass (measured)** | `COVERAGE_FILE=/tmp/p9b_rt/.coverage.after .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py" --cov=api --cov-report=term-missing`: `routes_upload.py 48 stmts 0 miss 100%`, `routes_valuation.py 197 stmts 8 miss 96%` (missing `129-130, 195, 263, 349, 626-628`), `TOTAL 245 / 8 → 97%`. Before (the same gate with my file excluded): 77%, 88%, total 86%. See Measurements |
| 5 | at least two tests can fail | **pass** | 11 mutations of a copy under `/tmp/p9b_rt/mut/`, and all 11 turn at least one test red. Output pasted below |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Shared builders sit in `_session_route_helpers.py` as **plain functions**. Each test file wraps them in its own three fixtures | ruff `F811`: importing fixture objects by name raised the lint gate from 5 to 37 errors (measured) | a `tests/unit/conftest.py` would put these fixtures into every route test's namespace. Thin local fixtures keep the lint gate at 5 |
| `price_calls` depends on `closed_client` | `closed_client` installs a refusing `fetch_price_data`. Whichever fixture runs second wins | without the dependency, a test that listed `price_calls` first would silently get the refusing stub |
| Route A runs through the real `extract_financials` down to a stubbed `_call_llm`, not a stubbed `extract_financials` | assignment item 5: "Stub `_call_llm`". The label path under test is `_run_extraction` → `resolve_provider` → extractor | stubbing `extract_financials` would skip the extractor's own `resolve_provider`, which is the call a stale environment would break |
| Before the cache-hit POST, group 5 asserts `resolve_provider("claude", None)` **raises** | `.env` is loaded with `override=True` (backlog item 46). The precondition proves the key removal actually took | without it, a passing hit test could mean the key was still present |
| A spy around `load_session_extraction` tells a hit from a miss | "on a cache hit and on a cache miss" (item 4) must be shown, not assumed | asserting only the label would pass on either branch |
| Group 6, "on both routes": locked as (a) `POST /valuation` with nothing named, (b) route A `files=","`, (c) route B `session_file` naming no file, and (d) `GET /assumptions` with nothing named runs no extraction and names no route | backlog item 29 is about `POST /valuation` only. (b) and (c) are each route's way of naming no filing | (d) does **not** assert whether `GET /assumptions` shows an error. It does not today; see the open question under "Findings" |
| The legacy `file_path` arc in `_run_extraction` (`:194→195`) is left uncovered | `docs/5-testing/strategy.md` section 4 names the legacy `file_path` branch as uncovered on purpose (item 26's territory) | covering it would pin a fallback that a later fix may remove |
| No test asserts a share price | the assignment's subject is the route and the label. The page figure asserted is revenue, read straight from the file | a price would need the whole DCF chain worked by hand. `test_routes.py` already does that for route A |

## Rule 3: what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| upload field `session_file` | stops: 422, `loc ["body","session_file"]` | `test_upload_session_with_no_file_field_answers_422_naming_the_field` |
| uploaded filename `.` / `..` | stops: 400, detail starts `session_file:`, nothing written | `test_upload_session_with_no_usable_filename_answers_400_naming_the_field[.]`, `[..]` |
| a crafted `../../escape.json` | not a missing value. Saved as `uploads/session/escape.json`, nothing outside | `test_upload_session_keeps_only_the_final_path_component` |
| `session_file`, `files`, `file_path` all empty, `POST /valuation` | stops, naming all three | `test_valuation_with_no_filing_stops_naming_all_three_fields` (item 29) |
| `files` naming no entry (`","`) | stops, `files: ','…` | `test_assumptions_with_files_naming_no_entry_stops_naming_files` |
| `session_file` naming no file on disk | stops, naming the path | `test_assumptions_with_a_session_file_that_is_not_there_stops_naming_it` |
| one Pass 1 key (`sbc`, year 2024) | stops: 200 page, error names the file, `year 2024` and `'sbc'`. No label, no statements, nothing cached | `test_a_session_file_missing_one_pass1_key_renders_the_loaders_message`, and through the upload form |
| route A credential, cache miss | stops, naming `ANTHROPIC_API_KEY`, with 0 `_call_llm` calls | `test_route_a_on_a_cache_miss_with_no_key_stops_on_the_credential` |
| request ticker / company that differs from the file | stops, naming both. On `POST /valuation` it stops before the price fetch | three tests in group 3 |
| `session_file` + `files`, cache miss | stops, naming both | `test_valuation_with_session_file_and_files_on_a_cache_miss_stops` |
| **`session_file` + `files`, cache hit** | **does not stop: `files` is silently ignored** | **`api/routes_valuation.py:544`** (`cache_key = session_file or files`, consulted before `_run_extraction`'s check at `:177-182`). Locked red in `test_routes_session_rule3_red.py`. Backlog item 52 |
| `GET /assumptions` with nothing named | no extraction, no label. Whether it should *stop* is not settled (see Findings) | `test_assumptions_with_no_filing_runs_no_extraction_and_names_no_route` asserts only the first two |

## Measurements

**Suite (failure SETS):**

| Run | Before (`dce8d42` + P9d's in-flight tree) | After |
|---|---|---|
| gate `--ignore-glob="*_rule3_red.py"` | `1 failed, 353 passed`, `{test_capm…no_variation}` | `1 failed, 376 passed`, `{test_capm…no_variation}` |
| full `pytest -q` | `3 failed, 356 passed`: capm, `test_dcf_rule3_red`, `test_projector_rule3_red` | `4 failed, 379 passed`: the same three plus `test_routes_session_rule3_red::…cache_hit_stops` |

**Lint:** `.venv/bin/python -m ruff check .` → `Found 5 errors.` (the same five BLE001
sites). The three new files are clean.
**Types:** the exact gate command → `Found 10 errors in 4 files (checked 20 source files)`,
unchanged. Tests are outside the type gate.

**Coverage, `api/`** (`COVERAGE_FILE` under `/tmp/p9b_rt/`):

| File | Before (statements) | After (statements) | After (branches) |
|---|---|---|---|
| `api/routes_upload.py` | 37 of 48, 77% (missing 45-56, 116-117) | **48 of 48, 100%** | 4 of 4 |
| `api/routes_valuation.py` | 173 of 197, 88% | **189 of 197, 96%** | 47 of 52 |
| `api/` total | 210 of 245, 86% | **237 of 245, 97%** | 51 of 56 |

The five arcs still missing in `routes_valuation.py`, from `--cov-report=json`, are
`127→129`, `194→195`, `262→263`, `338→349` and `625→626`. **Only `194→195` sits in code
P9b added**: the legacy `file_path` branch of `_run_extraction`, left uncovered on
purpose (see Decisions). The other four predate P9b: the multi-file all-year-0 fallback,
two statement-absent rows, and the yfinance share-count fallback (rule 5, deliberately
unpinned).

**Coverage of what P9b added**:

- **Functions:** 6 of 6 called by a test in this unit: `_save_session_upload`,
  `upload_session_file`, `_run_extraction`, `_shown_identity`, and the changed
  `assumptions_page` and `run_valuation`.
- **Branch arcs** on P9b's lines: 21 of 22.
  - `_save_session_upload`: 2 of 2.
  - `_run_extraction`: 9 of 10. The missing one is `194→195`.
  - `_shown_identity`: 6 of 6.
  - `assumptions_page`'s `if cache_key`: 2 of 2.
  - `run_valuation`'s cache test: 2 of 2.
  - `run_valuation`'s `":" in files`: 2 of 2.

**Criterion 5: mutations of a copy** (`/tmp/p9b_rt/mutate.py`, output in
`/tmp/p9b_rt/mutate.out`). Each line under test is edited in `/tmp/p9b_rt/mut/` and
restored afterwards. The script asserts the restore. The repository is never touched.

```
=== M1 cache hit re-derives the label at render time      (extraction = cached.extraction -> resolve_provider(...))
    test_valuation_on_a_cache_hit_shows_the_session_label
    test_route_a_label_survives_removing_the_key_on_a_cache_hit
    2 failed, 21 passed
=== M2 no filing extracts the empty path (item 29 reopened)
    test_valuation_with_no_filing_stops_naming_all_three_fields
    1 failed, 22 passed
=== M3 upload accepts '.' and '..'                        ('..' red; '.' stays 400 because Path('.').name == '')
    test_upload_session_with_no_usable_filename_answers_400_naming_the_field[..]
    1 failed, 22 passed
=== M4 request ticker differing from the file is ignored
    test_assumptions_with_a_ticker_that_differs_from_the_file_stops_naming_both
    test_valuation_with_a_ticker_that_differs_from_the_file_stops_before_pricing
    2 failed, 21 passed
=== M5 session extraction labelled by resolve_provider    (7 red)
=== M6 session_file with files accepted on a miss         -> test_valuation_with_session_file_and_files_on_a_cache_miss_stops
=== M7 session upload saved outside uploads/session       (4 red)
=== M8 company name differing from the file is ignored    -> ..._company_name_that_differs_..._stops_naming_both
=== M9 files naming no entry is not stopped               -> test_assumptions_with_files_naming_no_entry_stops_naming_files
=== M10 ticker shown is the request's, not the file's     -> test_assumptions_from_a_session_file_shows_the_label_and_the_files_identity
=== M11 assumptions page does not forward session_file    -> the same test
restored
```

**The red test can go green.** `/tmp/p9b_rt/fix52.py` adds, in the copy, a stop before
the cache lookup in `run_valuation` when `session_file and files`. The red file then
reports `1 passed`, the green file `23 passed`, and the copy is restored. So the red test
states a requirement that the code can meet, not one that is impossible.

## Expected values (testers only)

No expected value was read off a rendered page or from a `.pkl`. The sources:
**F** = written by hand into the session file in `_session_route_helpers.py`. **P9a-11** =
`.agent/assignments/P9a-session-route.md:198-201` (provider claude, the declared model, a
transport label saying "Claude Code session" and naming the file, a credential source
saying no API call was made). **P9b-n** = `.agent/assignments/P9b-session-web.md` step n.
**Sig** = the route's declared signature. **Env3** = `docs/8-build/environment.md:95`
(on macOS, Claude is reached "over the public API with `ANTHROPIC_API_KEY`").

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| front page form count; second form's action, method, enctype, file input `session_file`; no `<script` | 2; `/upload-session`, `post`, `multipart/form-data`; absent | P9b-1; Sig `session_file: UploadFile = File(...)` |
| submitting the second form's own field | 303 (not 422) | Sig: `status_code=303`. FastAPI answers 422 on a missing `File(...)` |
| upload: status, location path, query, file on disk | 303, `/assumptions`, `{session_file: [<tmp>/uploads/session/tst_session.json]}`, bytes equal to those sent | Sig; P9b-2 ("under `uploads/session/`"); `UPLOAD_DIR` set by the fixture |
| `.` / `..` filename | 400, detail starts `session_file:`, nothing written | assignment item 2 ("names `session_file`"); rule 3 |
| no file field | 422, `["body","session_file"]` in the locations | Sig |
| `../../escape.json` | saved as `uploads/session/escape.json` only | `_save_session_upload` docstring, `api/routes_upload.py:42-43`: "only the final path component is kept" |
| label rows on both pages (session) | Provider `CLAUDE`, Model `model-id-declared-in-the-test-session`, Transport contains `Claude Code session` and the session file's path, Credential contains `no API call was made` | P9a-11 for the shape; F for the model ID, chosen to be no real or default model so it can only come from the file |
| hidden `ticker`, `company_name`, `session_file`, `files` | `TST`, `Test Co`, the path, `""` | F; P9b-5 ("the ticker shown and forwarded comes from the loaded file"); P9b-7 |
| revenue row | `["1,000", "2,000"]` | F: base revenue 1000 × k, with k = 1 for 2023 and k = 2 for 2024. `"{:,.0f}"` format in `_statements.html:22` |
| ticker / company mismatch | error contains `'OTHER'` and `'TST'` / `'Other Corp'` and `'Test Co'`; nothing cached | assignment item 3 ("the page names both"); F |
| valuation mismatch stops before pricing | error names both tickers, and the price stub refuses | the ticker reaches `fetch_price_data`. A stop placed after it would surface the stub's message instead |
| cache hit / miss: loader calls | hit: 1 in total (the GET's); miss: `[<path>]` | the definition of a cache hit (no new extraction) |
| price calls | `[("TST", 5, "monthly")]` | F (ticker); the form's `beta_lookback_years=5` and `return_frequency=monthly` |
| `public API` absent on session pages | absent | P9a-11: no API was used. Rule 6 |
| excluded item description on the result page | present | F (confidence `low`); `partition_by_confidence` docstring, `analysis/normalizer.py:101-104`: `low` is excluded and listed |
| route A: `_call_llm` calls | `["pass1", "pass2"]`, then no more on the cache hit | `extract_financials` makes two passes (its docstring). The stub keys on the exact prompts |
| route A label, before and after removing the key | Transport contains `public API`, Credential contains `ANTHROPIC_API_KEY` | Env3; P9b-6 (recorded, not re-derived) |
| precondition: key removed | `resolve_provider` raises `ValueError` matching `No Anthropic credential resolved` | the stop message route A's miss must show. It proves the removal took |
| route A miss with no key | error contains `No Anthropic credential resolved` and `ANTHROPIC_API_KEY`; 0 calls; no label | assignment item 5; Env3 names the credential |
| no filing | error contains `session_file`, `files`, `file_path`; 0 loader calls; no label | the three parameters `_run_extraction` declares; backlog item 29 |
| `files=","` | error starts `files:` and contains `','` | P9b programmer's decision table (rule 3, field named) |
| missing session file | error contains the path | the loader's contract: every stop names the file |
| `sbc` removed | error contains the file path, `year 2024`, `'sbc'`, `absent`; no label, no statements, empty cache | assignment item 7; P9a step 10's stop list (file, year, key) |
| red, item 52 | error contains `session_file` and `files`; no price fetched | the two form parameters; rule 3; the cache-miss behaviour of the same form |

**Two counts:**

- **Accuracy, in assertions.** `test_routes_session.py` holds 117 `assert` statements,
  and every one holds (23 of 23 tests pass). `test_routes_session_rule3_red.py` holds 5.
  Its first, a precondition, holds. The second (`message is not None`) fails, which is
  the requirement item 52 states, so the three after it do not run. The helper holds 3
  precondition asserts (the Pass 1 reconciles, and so on), and all hold.
- **Coverage, in functions and then in branches.** 6 of 6 functions P9b added or changed
  are called. 21 of 22 branch arcs on P9b's lines are taken. Module figures are in
  Measurements.

## What I did not do

- **I did not fix backlog item 52.** That is implementation code. It is locked red.
- **I did not cover the legacy `file_path` arc (`api/routes_valuation.py:194→195`)**, on
  purpose (strategy.md section 4).
- **I did not move `tests/unit/test_session_extraction_rule3_red.py`** (see Findings 2).
  That module is P9d's, its change is uncommitted and unreviewed, and moving the tests
  is outside this assignment.
- **I did not assert a share price** on the session route.

## Findings for the orchestrator

1. **Backlog item 52 is now a red test**:
   `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`.
   A fix that stops when `session_file and files` before the cache lookup in
   `run_valuation` turns it green (shown in the `/tmp` copy). **When it goes green, the
   fixing unit must move it into `tests/unit/test_routes_session.py`** (backlog item 24).
2. **Backlog item 24 risk, live right now.** With P9d's uncommitted change to
   `ingestion/session_extraction.py` in the tree, all 3 tests in
   `tests/unit/test_session_extraction_rule3_red.py` **pass**
   (`.venv/bin/python -m pytest -q tests/unit/test_session_extraction_rule3_red.py` →
   `3 passed`). STATUS at `be1c077` counts them among the 5 red. If P9d is accepted, its
   tester must move them out of the `*_rule3_red.py` pattern in the same unit. Otherwise
   the gate stops running the tests that prove P9d's fix.
3. **Open question on group 6 ("stops on both routes").** `GET /assumptions` with no
   filing named renders the form with no error and no extraction (the programmer
   recorded this as the page's landing state). I read "both routes" as route A and
   route B and locked a stop for each. **If the assignment meant both HTTP routes**,
   then `GET /assumptions` with nothing named does not stop
   (`api/routes_valuation.py:395-397`: `if cache_key:` skips everything). That would be
   a new backlog item, not a test to write here. My test asserts only that no extraction
   runs and no route is named, which holds under either reading.
4. **`uploads/session/WMT.json` appeared in the repository at 17:13**, the minute this
   unit started. It is not from these tests: they write only under `tmp_path`, and no
   test names `WMT`. It is git-ignored (`.gitignore:5`). It probably comes from the
   parallel P9d run or from a manual session. The programmer's entry said `uploads/`
   held only `LHX`.
