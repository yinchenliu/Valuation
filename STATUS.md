# Where the build stands

**Measured, never planned.** Every number here carries the commit it was measured at.
A number with no commit beside it is not a measurement. Re-measure on every update;
never carry a figure forward.

**Measured at `ff632df`, 2026-09-21**, on branch `build/phase-1-2`. **Ten work units
accepted, and not one on its own report.** Every programmer run went to a reviewer that
re-ran the measurements rather than reading them; three times a reviewer overturned a
claim, twice against a programmer and once against the orchestrator. The journal is
[.agent/journal/INDEX.md](.agent/journal/INDEX.md).

---

## 1. The gates, today

| Gate | Command | Result at `ff632df` |
|---|---|---|
| Tests | `.venv/Scripts/python.exe -m pytest -q` | **121 tests. 120 pass, 1 red on purpose**, 3.9 s |
| **Tests, the gate form** | `... -m pytest -q --ignore-glob="*_rule3_red.py"` | **120 passed**, 0 failed |
| Lint | `.venv/Scripts/python.exe -m ruff check .` | **5 errors**, every one `BLE001` |
| Types | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | **14 errors in 4 files**, 18 files checked |
| **Routes** | `TestClient(app.app, raise_server_exceptions=False).get('/')` | **200** |

**There is a fourth gate now, and it is stricter than `import app` ever was.**

```
.venv/Scripts/python.exe -c "from starlette.testclient import TestClient; import app; \
  print(TestClient(app.app, raise_server_exceptions=False).get('/').status_code)"
```

→ **200**, as of `622262b`. `import app` passed throughout the outage described in
section 1b, from `bc19431` to `d885d8d`. **It was never the strongest check available
and it should not be used as one.**

### Type errors fell 33 → 14, and not one by annotating anything

| Commit | Errors | What removed them |
|---|---|---|
| `bc19431` | 33 | — |
| `0e4649f` | 22 | `response.content[0].text` — it died on every real extraction |
| `0e4649f` | 18 | two `TemplateResponse` calls — 500 on every page |
| `622262b` | **14** | the other two `TemplateResponse` calls |

Every drop came from fixing a defect the checker had been reporting all along, and each
was a live outage. **Treat a type error here as a defect report until proven
otherwise.** Three times now the checker named one while the prose beside it called the
error a nicety.

**Use the `--ignore-glob` form as the gate.** It excludes every deliberately red test by
pattern, so it keeps working as more are written. An earlier revision of this file named
a single file by path; that form went stale the moment a second red test landed.

**When a red test goes green, move it out of the pattern in the same unit.** At
`38b903c` two tests went green and stayed inside it, so the two tests proving a fix
worked were the two the gate did not run. That was backlog item 24, closed at
`81816be`, and the rule is now in `.claude/agents/tester.md` so it is not rediscovered.

**Set `COVERAGE_FILE` before measuring coverage** if anything else may be running:
two processes in one tree collide on the root `.coverage`, and a `--cov-branch` run
against statement-only data aborts as a pytest `INTERNALERROR`.

**The lint gate is one rule away from clean.** All 5 remaining errors are blanket
`except Exception`: `api/routes_valuation.py:96` and `:220`, `cli.py:758`,
`ingestion/claude_extractor.py:795`, `tests/test_e2e_all_googl.py:106`. They are
backlog item 8 and phase 5 owns them. **They are deliberately left visible.**
Suppressing them would delete the record of a defect instead of fixing it.

## 1b. The web application served no page at all until `622262b`

`starlette` 1.6.0 requires `TemplateResponse(request, name, context)`. This repository
used the removed `(name, context)` form at all four call sites, which passes a `str`
where a `Request` belongs.

```
the removed form  ->  TypeError: cannot use 'tuple' as a dict key
the current form  ->  rendered OK, status 200
```

`api/routes_upload.py`'s call was **unchanged from `bc19431` to `d885d8d`**, so `app.py`
— one of the two entry points this product ships — had never served a page in this
environment until `622262b`.

| Route | `bc19431` … `0e4649f` | At `622262b` |
|---|---|---|
| `GET /` | **500**, 21 bytes | **200**, 1648 bytes |
| `GET /assumptions` | **500** | **200**, 5673 bytes |
| `POST /valuation` | **500** | **200**, with the provider/model/transport block |
| `POST /upload` | renders no template | reachable; no HTTP proof in its own unit |

**Why a total outage showed as a blank 500 and not a message.** The failing calls sit
inside a blanket `except Exception` that renders the error onto a page — **through the
same broken call.** So the handler meant to report a failure could not report anything.

That is not a deduction. The reviewer of `P5-web-routes` exercised the error branch of
`assumptions_page` after the fix: it now returns 200 and renders
`<div class="alert alert-error">[Errno 2] No such file…</div>`. Before the fix, that
same branch produced 21 bytes of `Internal Server Error`.

**This is the clearest argument in the repository for backlog item 8.**

### The test gate runs, and one test is red on purpose

`pytest` no longer makes a paid API call during collection. It needs no key, no PDF
and no network.

**One test fails deliberately.** `tests/unit/test_dcf_rule3_red.py` states that
`run_dcf` must stop when the balance sheet is absent. That is backlog item 2, and it is
still open. `ls tests/unit/*_rule3_red.py` returns exactly that one line.

**A failure other than that one is a real regression.**

### `tests/`, measured at `742f447`

| | At `bc19431` | At `742f447` |
|---|---|---|
| `.py` files | 10 | **20** |
| `assert` statements | **0** | **442** |
| scripts guarded by `if __name__ == "__main__":` | **0** | **9 of 9** |
| tests collected | 0 | **121** |
| paid API calls during collection | attempted | **none** |

### Coverage, measured at `ff632df`

```
analysis/capm.py         40 statements    3 missed    92%
analysis/dcf.py          29               2           93%
analysis/fcff.py         19               0          100%
analysis/normalizer.py   36               0          100%
analysis/projector.py    68               0          100%
analysis/wacc.py         34               1           97%
analysis/ TOTAL         226               6           97%

api/routes_upload.py     33               0          100%
api/routes_valuation.py  93               8           91%
api/ TOTAL              126               8           94%
```

**`api/` went from 0 of 126 statements to 118 of 126 at `742f447`, unchanged since.** Before
`P5b-route-tests`, coverage.py reported `Module app was never imported`. The eight
uncovered arcs are each a fallback or a recorded backlog item the tester **refused to
pin**: the cache-hit branch (item 5), the yfinance share-count fallback (rule 5), and
the legacy `file_path` branch (item 26). Pinning one would lock the defect.

**220 of 226 statements in `analysis/`, against 24 at `d1854fb`.** It reached 202 of
202 at `742f447`; `P4c-nan-stops` then added six `raise` statements that no existing
test reaches, because no existing test supplies the broken input they catch.

**That gap is deliberate and was not worked around.** The unit was told in writing not
to add an unreachable guard or restructure code to hold a percentage, and the reviewer
reached all six lines by execution to confirm none is dead. A tester closes them next.

**Two caveats a reader must not skip.**

1. Coverage.py does not count a conditional *expression* as a branch. So 100% branch
   coverage does **not** include `if latest_bs else 0.0` at `analysis/dcf.py:80-81`, or
   any of the other conditional-expression defaults. **Coverage here is not evidence
   that every path is checked.**
2. **`ingestion/` still has no tests at all.** That is where 49 of the 116
   zero-default sites live, and where the extraction boundary sits. `api/` was in the
   same position until `742f447`.

### Type errors, by kind and by file, at `622262b`

| Kind | `bc19431` | Now | | File | `d885d8d` | Now |
|---|---|---|---|---|---|---|
| `union-attr` | 16 | **5** | | `ingestion/claude_extractor.py` | 5 | 5 |
| `arg-type` | 11 | **3** | | `api/routes_valuation.py` | 6 | **4** |
| `assignment` | 4 | 4 | | `analysis/projector.py` | 4 | 4 |
| `typeddict-item`, `operator` | 2 | 2 | | `api/routes_upload.py` | 3 | **1** |
| **total** | **33** | **14** | | **total** | **18** | **14** |

**The 14 are a strict subset of the 33.** Verified by the code reviewers with `comm -13`
against `git archive` exports, line numbers stripped: nothing was added at any step.

**Count `error:` lines, not output lines.** An earlier revision of this table said
`8/5/4/4 = 21` against its own stated total of 18, because the count swept up mypy's
`note:` lines as well. Notes added 2 to `routes_valuation` and 1 to `routes_upload`.
**A by-file breakdown that does not sum to the total is a broken measurement**, and this
one sat here through two updates.

**One of the 14 is a live defect, not a typing nicety:**

```
api/routes_valuation.py: Argument "balance_sheet" to "calculate_wacc"
  has incompatible type "BalanceSheet | None"; expected "BalanceSheet"
```

`calculate_wacc` raises `AttributeError` on `None.total_debt` deep inside the
valuation, and the blanket `except Exception` renders that as a string on the results
page. Rule 3.

The survivor in `api/routes_upload.py` is `:27`,
`Unsupported operand types for / ("Path" and "None")` — a `str | None` used as a path
segment. Not yet on the backlog.

---

## 2. What exists

| Area | State |
|---|---|
| `models/` | 2 dataclass modules. `company.py` was dead and is deleted |
| `ingestion/claude_extractor.py` | two-pass extraction, Gemini and Claude providers, multi-PDF year routing. The largest file |
| `ingestion/price_fetcher.py` | yfinance prices for CAPM |
| `analysis/` | normalizer, projector, capm, wacc, fcff, dcf. All deterministic |
| `api/` + `templates/` | FastAPI upload → assumptions → result, 3 routes |
| `cli.py` | 760 lines, a full 10-step pipeline runner with its own printing layer |
| `tests/` | 9 scripts, all guarded, plus `tests/unit/` with the first real tests |

Two entry points run the same pipeline: `app.py` (web) and `cli.py` (terminal). They
duplicate the orchestration rather than sharing it. See the backlog, item 7.

---

## 3. The environment

Built 2026-09-20. `docs/8-build/environment.md` owns the detail.

- **Interpreter:** `.venv/Scripts/python.exe`, Python **3.14.4**.
- All 13 runtime dependencies import. pandas **3.0.6**, numpy **2.5.3**, scipy **1.18.1**.
- Dev gates: pytest 9.1.1, ruff 0.16.8, mypy 2.3.1, pytest-cov.
- `ruff.toml` now exists. It sets `target-version` and one justified `B008` per-file
  ignore for `api/`, where `File(...)` in a parameter default is the required FastAPI
  idiom. **It sets no `select` or `ignore` list**, so the gate still means what ruff's
  default rule set means.

**pandas 3.0 is a major version.** `ingestion/price_fetcher.py` branches on the pandas
version to choose `"ME"` over `"M"` for month-end resampling. That branch has not been
exercised against 3.0 on real data. Treat any resampling result as unverified until it
is.

### The extraction path on this machine — measured, 2026-09-21

**This machine reaches Anthropic through a Microsoft Foundry gateway, not the public
API.** `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` are unset and will stay unset; Gemini is
unreachable from this network. Every row below was **executed**, not read:

| Fact | Result |
|---|---|
| `ANTHROPIC_FOUNDRY_BASE_URL` is set; `AnthropicFoundry` reads it with no argument | its `__init__` |
| the gateway accepts an Entra ID bearer token on `https://cognitiveservices.azure.com/.default` | **HTTP 200** |
| `https://ai.azure.com/.default` is rejected, and the 401 names the right audience | **HTTP 401** |
| `claude-opus-5` and `claude-haiku-4-5` are served | **HTTP 200** |
| **native PDF ingestion works through the gateway** | a one-line PDF; the model returned the printed figure |
| the whole path works through the SDK, not only raw HTTP | `AnthropicFoundry(azure_ad_token_provider=…)` |
| `azure-identity` is **not** installed | `ModuleNotFoundError` |

**Extraction runs, as of `0e4649f`.** `P2b-provider` closed backlog item 13: one default
provider named once in `config.py`, Foundry as a transport, and an Entra token from
`azure-identity` 1.25.3. No API key anywhere.

**The value tracks the page, which is the only evidence that counts here.** Pages
printing `4321`, `6174`, `2718` and `8765` each extracted to the figure printed on them.
Through the route, two documents differing only in that every income and cash-flow line
was doubled produced `$82.18` and `$166.86` per share, with the cost of capital pinned
identical across both runs — exactly `2 × 82.18 + net_debt/shares`.

**Those figures come from invented documents and are meaningless as valuations.** They
are evidence about the pipeline, not about a company.

**There are still no PDFs on this machine.** `10K_filings/` holds one stray `.DS_Store`.
A real valuation needs a filing as well as a working client, and no run so far has used
one.

**PDF input is a beta feature on Microsoft Foundry.** It works today. Treat a future
failure there as a platform change, not as a defect in this repository.

---

## 4. The agent contract

Set up 2026-09-20, ported from the CLO_AUP build and adapted. First exercised the same
day.

- `.claude/agents/` — `programmer`, `code-reviewer`, `tester`.
- `.claude/hooks/` — `guard_paths.py` (write scope), `seal_baseline.py` +
  `seal_check.py` (the seal on this file, the journal index, and the hooks themselves).
- **`.venv/Scripts/python.exe .claude/check_guard.py` → 48/48 cases correct**,
  re-measured at `d1854fb`.
- `docs/INDEX.md` is the map. Agents read it and open only what they need.

**Two units have run through the full loop**, in parallel with disjoint file scopes,
each reviewed by a reviewer that re-ran every measurement rather than accepting the
claim. Both approved. The write guard denied nothing it should have allowed and
allowed nothing it should have denied.

**There is no benchmark, by decision.** The tester derives expected values by hand.
`.claude/agents/tester.md` opens with the trap that creates. Read it before dispatching
one.

---

## 5. Open items

Ranked by cost, **open first**. The full list with evidence is
[docs/9-reference/refactor-backlog.md](docs/9-reference/refactor-backlog.md); this is
the headline. Re-ranked at `622262b`.

### Open

| # | Item | Cost |
|---|---|---|
| 30 | `analysis/dcf.py:46-57` — a NaN in one `ProjectedFCFF` still reaches the share price | **the highest-cost defect now known.** It sums and discounts the cash flows with no check on what it is summing. All three stops added at `ff632df` sit on the discount-rate side; **the cash-flow side has none.** Confirmed before and after, middle year and final year |
| 1 | **116** silent zero-default sites — `models/` 60, `ingestion/` 49, `analysis/` 5, `api/` 2 | **worse than its original description.** It does not produce zeros; it produces a signed, correctly-scaled figure that tracks the filing and reads as a measurement |
| 2 | `analysis/dcf.py:80` — missing balance sheet gives **zero net debt** | equity value overstated by the whole debt balance. A red test already states the requirement |
| 25 | `analysis/normalizer.py:167-170` — an adjustment whose **year** matches no statement is discarded | a valuation labelled "normalised" whose figures are as-reported, with no signal |
| 8 | Blanket `except Exception` at five sites | **it swallowed the web outage for the life of the repository**, because the error page rendered through the same broken call |
| 6 | Five `x / 100 if x else None` conversions | a deliberate `0` from the user is read as "not supplied" |
| 15 | `models/financial_statements.py:295` — `latest_year` returns `0` for an empty extraction | turns "no data" into "year zero" with no error. The silent upstream of item 2 |
| 22 | `analysis/wacc.py:37` — zero debt balance gives a 0% cost of debt | missing data read as a measurement |
| 23 | `analysis/fcff.py` holds **no `raise` at all** | wholly empty statements return a well-formed result with `fcff = 0.0` |
| 9 | Unlabelled cost-of-debt assumption, `analysis/wacc.py` | a 4% guess reaches the share price with nothing saying so |
| 10 | D&A subtraction buried in the parser, `ingestion/claude_extractor.py:479` | an accounting decision taken inside a parser, on two zero-defaulted values |
| 7 | `cli.py` and `api/` duplicate the pipeline | a fix must be made twice or it is made once |
| 5 | `api/routes_valuation.py:31` — module-global extraction cache, `pop`ped on read | shared across users; a page refresh re-runs the paid extraction |
| 11 | **14** type errors, down from 33 | one is a live crash path. Every removal so far was a real defect, never an annotation |
| 23b | `analysis/fcff.py:44` — the NaN tax clamp twin | `max(0.0, min(nan, 0.50))` is **`0.0`**, so an unknown tax rate becomes a 0% rate and a full tax shield, which **raises** the valuation. `analysis/wacc.py` held the same clamp and was fixed at `ff632df` |
| 16 | Nine scripts carry a `sys.path.insert` to a path that does not exist here | none runs as `python tests/<name>.py`. Use `-m tests.<name>` |
| 26 | `api/routes_valuation.py:152` branches on a character every path contains | **latent.** Live only on the legacy no-year branch. My first write-up of this was wrong and was corrected by review |
| 17 | `analysis/capm.py:14` imports from `ingestion/` | a layering break |
| 18 | The lint gate's rule set is unpinned | a ruff upgrade changes what the gate enforces, with no commit to point at |
| 28 | `api/routes_upload.py:27` — `str \| None` used as a path segment | the last type error in that file |
| 29 | `POST /valuation` with no `files` runs an extraction on the empty string | **rule 3, and never counted.** HTTP 200, the extractor receives `''`, and the word `files` appears nowhere on the page |

### Closed

| # | Item | Closed at |
|---|---|---|
| 3 | Unknown NRI line item guessed a field | `38b903c` |
| 4 | No test suite; `pytest` could not collect | `d1854fb`, extended through `81816be` |
| 12 | Dead code and repository hygiene | `d1854fb` — mostly; three `tests/*.pkl` stay tracked on purpose |
| 13 | Provider default differed with the number of PDFs uploaded | `0e4649f` |
| 19 | One sign rule applied to two kinds of income statement line | `38b903c` |
| 21 | An unrecognised `direction` silently reversed the adjustment | `38b903c` |
| 24 | A red test that went green stayed outside the gate | `81816be` |
| 27 | `GET /` and `GET /assumptions` returned 500 | `622262b` |
| 20 | A NaN beta was returned, not raised | `ff632df` |
| 14 | Empty `projected_fcffs` raised a bare `IndexError` | `ff632df` |

**Ten closed, twenty-one open.** Items 19 to 28 did not exist when this build started —
**every one of them was found by running the code**, not by reading it.

---

## 6. Standing traps

Things that have already misled a reader of this repository.

1. **`tests/*.pkl` are committed.** Three of them. They are pickled extraction results,
   and loading a pickle executes the code in it, so they are not inert fixtures. They
   are also stale relative to any extractor change. Three scripts read them, which is
   why they were left. `cache/*.pkl` and both `.DS_Store` files were untracked at
   `d1854fb`; all of them remain on disk.
2. **A valuation that runs proves nothing.** Every dataclass money field defaults to
   `0.0`, so the pipeline produces a share price from an extraction that returned
   nothing at all. "It ran" is not evidence. Name an input that came from a filing.
3. **`cli.py` and the web app can disagree.** They build assumptions by separate code
   paths. A figure verified in one is not verified in the other.
4. **One test is red on purpose.** `pytest -q` reports `1 failed, 120 passed` and that
   is the expected state. Do not fix it by weakening it; fix backlog item 2. The gate
   form that excludes it is `pytest -q --ignore-glob="*_rule3_red.py"`.
5. **A green test inside `*_rule3_red.py` is invisible to the gate.** That happened
   once, at `38b903c`. Move a test out of the pattern the day it goes green.
6. **A tester's `fail` is a verdict about the code, not about its own work.** All four
   units so far returned `fail` or `partial` in their own entries and all four were
   approved by review. Read the verdict line at the top of an entry before reading the
   word alone.
7. **99% coverage of `analysis/` does not mean every path is checked.** Coverage.py
   does not count a conditional expression as a branch, and the conditional-expression
   default is this repository's most common defect. `ingestion/` and `api/` have no
   tests at all.
5. **Backlog item 1's census grep excludes `tests/`.** The 117 figure counts
   `models/`, `analysis/`, `api/` and `ingestion/` only. The nine scripts hold 33 more
   hits of the same shape. They are dev scripts, not pipeline code, but `tests/` is not
   clean and the figure should not be read as saying it is.
