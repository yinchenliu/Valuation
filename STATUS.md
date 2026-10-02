# Where the build stands

**Measured, never planned.** Every number here carries the commit it was measured at.
A number with no commit beside it is not a measurement. Re-measure on every update;
never carry a figure forward.

**Measured at `6db180c`, 2026-10-02**, on branch `main`, **on the macOS machine**
(`.venv/bin/python`, Python 3.11.6). Every figure before `cde33cb` was measured on the
Windows machine. **Twenty-two work units accepted, and not one on its own report.** Every programmer run went to a reviewer that
re-ran the measurements rather than reading them; **five** times a reviewer or a
programmer overturned a claim — twice against a programmer, **three times against the
orchestrator**. The journal is [.agent/journal/INDEX.md](.agent/journal/INDEX.md).

**The newest of the three orchestrator errors is the instructive one.** `P8a`'s
assignment mandated a two-sentence provenance label, supplied or derived. Review round 1
proved by execution that two sentences cannot state this provenance: a filing with no
cash flow statements produces a D&A ratio derived from nothing, and the two-sentence
scheme called it "derived from the filing's history". **The assignment was the defect,
not the code that followed it.** Round 2 then overturned one of the orchestrator's
done-criteria as well, showing it went red against correct code.

---

## 1. The gates, today

| Gate | Command | Result at `6db180c` (macOS) |
|---|---|---|
| Tests | `.venv/bin/python -m pytest -q` | **383 tests. 379 pass, 4 fail**: 3 red on purpose, and the CAPM test below. **3 more pass inside a red file and the gate skips them** (trap 5); a tester moves them next |
| **Tests, the gate form** | `... -m pytest -q --ignore-glob="*_rule3_red.py"` | **376 passed, 1 failed**: `test_capm.py:473`. SciPy 1.17.1 raises its own message first. Backlog item 45, **held by the user** |
| Lint | `.venv/bin/python -m ruff check .` | **5 errors**, every one `BLE001` |
| Types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | **10 errors in 4 files**, 20 files checked |
| **Routes** | `TestClient(app.app, raise_server_exceptions=False).get('/')` | **200** |
| **Rule 3 census** | the grep at [rules.md:65](docs/2-rules/rules.md) | **116**, unchanged since `7354698`. Under zsh, quote `'--include=*.py'` or the count reads 0 |
| **Write guard** | `.venv/bin/python .claude/check_guard.py` | **48/48** |

**There is a fourth gate now, and it is stricter than `import app` ever was.**

```
.venv/Scripts/python.exe -c "from starlette.testclient import TestClient; import app; \
  print(TestClient(app.app, raise_server_exceptions=False).get('/').status_code)"
```

→ **200**, as of `622262b`. `import app` passed throughout the outage described in
section 1b, from `bc19431` to `d885d8d`. **It was never the strongest check available
and it should not be used as one.**

### Type errors fell 33 → 10, and not one by annotating anything

| Commit | Errors | What removed them |
|---|---|---|
| `bc19431` | 33 | — |
| `0e4649f` | 22 | `response.content[0].text` — it died on every real extraction |
| `0e4649f` | 18 | two `TemplateResponse` calls — 500 on every page |
| `622262b` | 14 | the other two `TemplateResponse` calls |
| `ad52e1a` | **10** | `P9a` moved the merge into its own function; four `assignment` errors were one variable, `stmt`, reused for three statement types |

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

**Use the type gate command exactly as written above.** Until `7354698` the three agent
contracts printed a shorter form, `mypy models analysis ingestion api`, which reports
**18 errors in 6 files** — the four extra being only missing third-party stubs that
`--ignore-missing-imports` exists to suppress. Two agents measuring "the types gate"
both got a defensible number and disagreed. `docs/8-build/environment.md` was **not** at
fault: it is headed "Result at `bc19431`" and states that it owns the commands, not the
counts.

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

**Three test cases fail deliberately.** `ls tests/unit/*_rule3_red.py` returns four files:

- `test_dcf_rule3_red.py`: `run_dcf` must stop when the balance sheet is absent.
  Backlog item 2, still open.
- `test_projector_rule3_red.py`: `analysis/projector.py` raises a bare `IndexError` on
  an empty revenue list. Written at `80febe1`, the twin of closed item 14.
- `test_session_extraction_rule3_red.py`, 3 cases: **green since `33afced`** (`P9d`). They
  must move out of the red file, or the gate never runs them. A tester run is next.
- `test_routes_session_rule3_red.py`, 1 case: a cache hit ignores `files` sent with
  `session_file`. Backlog item 52.

**On macOS one more test fails**, `test_capm.py:473`, because of the SciPy version
(item 45, held). **A failure other than those three is a real regression.**

### `tests/`, measured at `3028627`

| | At `bc19431` | At `3028627` |
|---|---|---|
| `.py` files | 10 | **20** |
| `assert` statements | **0** | **483** |
| scripts guarded by `if __name__ == "__main__":` | **0** | **9 of 9** |
| tests collected | 0 | **146** |
| paid API calls during collection | attempted | **none** |

### Coverage, measured at `576d4f0`

```
                          statements  missed  cover
analysis/capm.py                  53       0   100%
analysis/dcf.py                   35       0   100%
analysis/fcff.py                  24       0   100%
analysis/normalizer.py            49       0   100%
analysis/projector.py            114       0   100%
analysis/wacc.py                  39       0   100%
analysis/ TOTAL                  314       0   100%

api/routes_upload.py              33       0   100%
api/routes_valuation.py          158       9    94%
api/ TOTAL                       191       9    95%

models/financial_statements.py   154       1    99%
models/valuation.py              127       2    98%

ingestion/claude_extractor.py    438     133    70%     22% at ad52e1a
ingestion/filings.py              65      19    71%     new at ad52e1a
ingestion/session_extraction.py  510      81    84%     new at ad52e1a
ingestion/price_fetcher.py        37      21    43%
api/routes_upload.py              48       0   100%     at 6db180c
api/routes_valuation.py          197       8    96%     at 6db180c
```

**`ingestion/` is measured for the first time at `ad52e1a`, and tested since `92549f8`.**
`P9c-parse-tests` added 156 tests for the parse layer both routes share. The uncovered
parts are route A's retry loops, `locate`, `text` and the PDF helpers, which need a real
PDF. **`api/` is back to 97%** since `5294a73`, when the `P9b` tester added 23 route
tests for the session path.

**`P8b-statements-ui` verified all statement rendering blocks and brought `analysis/` to 100% coverage.**
`analysis/normalizer.py` and `analysis/projector.py` are now at 100%. `api/routes_valuation.py`
stands at 94% across 158 statements (149 covered). Total coverage across `analysis/`, `api/`,
and `models/` is 98% (786 statements, 12 missed).

**That gap is not `P8a`'s.** Measured by stashing `P8a`'s three files and re-running
against the committed tree at `35be956`: `analysis/normalizer.py 49 6 85%`, identical.
Read the rule this broke: a file that states a measurement names the commit it was
measured at, **and a measurement is re-taken when a unit lands, never carried forward.**
The second half was skipped.

**`P8a-statements-data` added 46 statements to `analysis/projector.py` and 37 to
`api/routes_valuation.py`.** One projector line is uncovered — the tax-clamp clause body
— and the reviewer reached it twice by execution before approving. Of `api/`'s 13, four
are the cache-hit branch (item 5) now spelled over five statements instead of one, and
one is the dead-but-required type narrowing named in the review as F4.

**The gap was never worked around.** Each unit was told in writing not to add an
unreachable guard or restructure code to hold a percentage, and each reviewer reached
the uncovered lines by execution to confirm none was dead.

**`api/` went from 0 of 126 statements at `742f447`**; before `P5b-route-tests`,
coverage.py reported `Module app was never imported`.

**Two caveats a reader must not skip.**

1. Coverage.py does not count a conditional *expression* as a branch. So 100% branch
   coverage does **not** include `if latest_bs else 0.0` at `analysis/dcf.py:80-81`, or
   any of the other conditional-expression defaults. **Coverage here is not evidence
   that every path is checked.**
2. **`ingestion/` has tests of its own since `92549f8`**, but route A's retry loops are
   not run. That is where 49 of the 116
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
| `ingestion/claude_extractor.py` | two-pass extraction, Gemini and Claude providers, multi-PDF year routing. Since `ad52e1a` it also holds the public plan, merge, prompt and parse functions both routes share |
| `ingestion/session_extraction.py` | **route B**, new at `ad52e1a`: a Claude Code session writes the two JSON answers to a session file; this loads and checks it. Subcommands `plan`, `locate`, `text`, `prompt`, `check` |
| `ingestion/filings.py` | filing discovery and hashing, moved from `cli.py` at `ad52e1a` |
| `ingestion/price_fetcher.py` | yfinance prices for CAPM |
| `analysis/` | normalizer, projector, capm, wacc, fcff, dcf. All deterministic |
| `api/` + `templates/` | FastAPI upload → assumptions → result, 3 routes |
| `cli.py` | a full 10-step pipeline runner with its own printing layer. `--session-file` runs route B with no API call |
| `tests/` | 9 scripts, all guarded, plus `tests/unit/` with the first real tests |

Two entry points run the same pipeline: `app.py` (web) and `cli.py` (terminal). They
duplicate the orchestration rather than sharing it. See the backlog, item 7.

---

## 3. The environment

Built 2026-09-20 on Windows. **Development moved to a macOS machine by 2026-09-26.**
`docs/8-build/environment.md` owns the detail for both.

- **macOS, measured 2026-10-02:** `.venv/bin/python`, Python **3.11.6**, scipy **1.17.1**,
  numpy 2.4.6, starlette 1.7.0. The credential is `ANTHROPIC_API_KEY` from `.env`; no
  Foundry variable is set. **`.env` overrides the environment** (backlog item 46).
  `pdftoppm` is absent and Homebrew 4.4.6 cannot install it on macOS 27.0, so a session
  reads PDFs through `session_extraction text`.
- **Windows interpreter:** `.venv/Scripts/python.exe`, Python **3.14.4**.
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

**The macOS machine holds 16 10-K PDFs** for AbbVie, Chipotle, L3Harris, Okta and
Walmart under `10K_filings/`. **The first route B run used one**, at `ad52e1a`: Walmart's
fiscal 2026 10-K, read in a Claude Code session, `check` clean, every arithmetic check at
a difference of 0, balance sheet 284,668 = 284,668 (PDF page 22). The CLI gave an
implied price of $28.84 against $104.26, and every step was re-derived by hand. The gap
is the assumptions, not the code: a 4.25% margin and 4.9% growth, averaged from three
years.

**PDF input is a beta feature on Microsoft Foundry.** It works today. Treat a future
failure there as a platform change, not as a defect in this repository.

---

## 4. The agent contract

Set up 2026-09-20, ported from the CLO_AUP build and adapted. First exercised the same
day.

- `.claude/agents/` — `programmer`, `code-reviewer`, `tester`.
- `.claude/hooks/` — `guard_paths.py` (write scope), `seal_baseline.py` +
  `seal_check.py` (the seal on this file, the journal index, and the hooks themselves).
- **`check_guard.py` → 48/48 cases correct**, at `d1854fb` on Windows and at
  `ad52e1a` on macOS.
- **The hooks were off on macOS until `cde33cb`.** `settings.json` named the Windows
  interpreter, so no hook could start, and Claude Code let every tool call through
  without a message. Every hook now starts through `.claude/hooks/run_hook.sh`, which
  finds either interpreter. The seal snapshot appeared at the first dispatch after the
  fix, which is how it was confirmed live.
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
| 48 | The equity bridge does not subtract noncontrolling interest | **new at `ad52e1a`.** About $0.82 of Walmart's $28.84. The fix adds an extracted field, so it needs the user |
| 46 | `.env` overrides the environment | **new.** `env -u` does not remove the key; it caused one possibly billed call during `P9a` |
| 43 | The fiscal year comes from the filename's date | **new.** Wrong for L3Harris's 2025 and 2026 filings |
| 49 | Given several PDFs, the API route drops one with no year, silently | **new.** Route B stops on the same input |
| 44 | The `units` field is extracted and ignored | **new, latent.** Chipotle reports in thousands |
| 47 | The income statement shown has no interest income row | **new, display.** EBT does not add up from the rows shown |
| 45 | The CAPM constant-market stop is reached only on older SciPy | **new. Held by the user** |
| 50 | Route A returns `[]` when Pass 2 cannot be parsed twice | **new, found by `P9c`.** "Nothing was read" looks like "none found" |
| 52 | A cache hit ignores `files` sent with `session_file` | **new, found by the `P9b` review.** Hand-built requests only |
| 51 | The arithmetic check's `WARN` branch is dead | **new, found by `P9c`** |
| 53 | The session loader imports `_NRI_SCHEMA` by its private name | **new, the `P9d` review's F1, minor** |
| 54 | `GET /assumptions` with no filing shows an empty form and no message | **new, found by the `P9b` tester** |
| 36 | **The same filing extracted twice gave share prices 16% apart** — $343.15 against $296.01 | **half closed at `7354698`.** On the user's decision, `low`-confidence items are now withheld and listed. **The variance itself is still unmeasured** — one pair is an observation, not a range, and the single occurrence that prompted it cannot be sized: three cached extractions hold **zero** `low` items between them |
| 39 | `models/financial_statements.py:28` defaults `confidence` to `"high"` | the last place absence becomes the strongest reading. **No live path reaches it**, so the decision is in force today; it is a type-level gap |
| 40 | Five dev scripts produce a price neither entry point would | **created by `7354698`.** They apply `low` items both entry points withhold, and print no excluded block |
| 38 | `analysis/wacc.py` fabricates a 100% equity weighting when market cap and debt are both zero | a supplied `--cost-of-debt` with a missing balance sheet also gets a zero debt weight, so the rate the user typed vanishes. **Verified unblocked**; fixing it costs exactly one test |
| 32 | `models/valuation.py:138` renders a share price of `0.0` on zero diluted shares | same shape as item 2, on the **denominator** of the headline figure |
| 37 | `analysis/wacc.py`'s new stop states an inference as a fact | the stop is right; the message asserts the extraction failed when a real deleveraging produces the same pattern. **Message only** |
| 31 | `discount_cash_flows`' `wacc` is unguarded on a **direct** call | **latent.** The `run_dcf` chain stops two lines later, so no current path reaches it |
| 1 | **116** silent zero-default sites — `models/` 60, `ingestion/` 49, `analysis/` 5, `api/` 2 | **worse than its original description.** It does not produce zeros; it produces a signed, correctly-scaled figure that tracks the filing and reads as a measurement |
| 2 | `analysis/dcf.py:80` — missing balance sheet gives **zero net debt** | equity value overstated by the whole debt balance. A red test already states the requirement |
| 25 | `analysis/normalizer.py:167-170` — an adjustment whose **year** matches no statement is discarded | a valuation labelled "normalised" whose figures are as-reported, with no signal |
| 8 | Blanket `except Exception` at five sites | **it swallowed the web outage for the life of the repository**, because the error page rendered through the same broken call |
| 6 | Five `x / 100 if x else None` conversions | a deliberate `0` from the user is read as "not supplied" |
| 15 | `models/financial_statements.py:295` — `latest_year` returns `0` for an empty extraction | turns "no data" into "year zero" with no error. The silent upstream of item 2 |
| 22 | `analysis/wacc.py:37` — zero debt balance gives a 0% cost of debt | missing data read as a measurement |
| 23 | `analysis/fcff.py` holds **no `raise` at all** | wholly empty statements return a well-formed result with `fcff = 0.0` |
| 10 | D&A subtraction buried in the parser, `ingestion/claude_extractor.py:479` | an accounting decision taken inside a parser, on two zero-defaulted values |
| 7 | `cli.py` and `api/` duplicate the pipeline | a fix must be made twice or it is made once |
| 5 | `api/routes_valuation.py:31` — module-global extraction cache, `pop`ped on read | shared across users; a page refresh re-runs the paid extraction |
| 11 | **10** type errors, down from 33 | one is a live crash path. Every removal so far was a real defect, never an annotation |
| 23 | `analysis/fcff.py` holds no `raise` for empty statements, and `calculate_fcff_projected` has **seven** unguarded float parameters | wholly empty statements return a well-formed result with `fcff = 0.0` |
| 16 | Nine scripts carry a `sys.path.insert` to a path that does not exist here | none runs as `python tests/<name>.py`. Use `-m tests.<name>` |
| 26 | `api/routes_valuation.py:152` branches on a character every path contains | **latent.** Live only on the legacy no-year branch. My first write-up of this was wrong and was corrected by review |
| 17 | `analysis/capm.py:14` imports from `ingestion/` | a layering break |
| 18 | The lint gate's rule set is unpinned | a ruff upgrade changes what the gate enforces, with no commit to point at |
| 28 | `api/routes_upload.py:27` — `str \| None` used as a path segment | the last type error in that file |
| 42 | A supplied growth list longer than the projection is silently truncated | **new at `6e58f13`.** Five rates supplied, two used, and the label says `supplied` without naming the three discarded |
| 41 | `analysis/projector.py:169`'s `0.05` growth rate is unreachable | **new at `6e58f13`.** Proved dead two ways. The **cheapest hit in item 1's census** — deleting it cannot move a number |

### Closed

| # | Item | Closed at |
|---|---|---|
| 3 | Unknown NRI line item guessed a field | `38b903c` |
| 9 | Unlabelled cost-of-debt assumption and projection ratios | `6cf34d3` (debt), `576d4f0` (ratios rendered via `P8b-statements-ui`) |
| 22 | Zero debt balance gave a 0% cost of debt | `6cf34d3` — its weights half is item 38 |
| 33 | The CLI cache was keyed on the ticker alone | `6cf34d3` |
| 34 | The risk-free rate was a constant presented as measured | `6cf34d3` |
| 35 | An unusable beta was reported without qualification | `6cf34d3` |
| 4 | No test suite; `pytest` could not collect | `d1854fb`, extended through `81816be` |
| 12 | Dead code and repository hygiene | `d1854fb` — mostly; three `tests/*.pkl` stay tracked on purpose |
| 13 | Provider default differed with the number of PDFs uploaded | `0e4649f` |
| 19 | One sign rule applied to two kinds of income statement line | `38b903c` |
| 21 | An unrecognised `direction` silently reversed the adjustment | `38b903c` |
| 24 | A red test that went green stayed outside the gate | `81816be` |
| 27 | `GET /` and `GET /assumptions` returned 500 | `622262b` |
| 20 | A NaN beta was returned, not raised | `ff632df` |
| 30 | A NaN cash flow reached the share price | `2ca620a` |
| 23b | The NaN tax clamp twin | `2ca620a` |
| 14 | Empty `projected_fcffs` raised a bare `IndexError` | `ff632df` |
| 29 | `POST /valuation` with no filing ran an extraction on an empty path | `be1c077` |

**Nineteen closed, thirty-three open.** Items 19 to 28 did not exist when this build
started — **every one of them was found by running the code**, not by reading it. So were
41 and 42, both found at `6e58f13` by a reviewer exhausting inputs rather than reading
the branch.

**Phase 9 ("two extraction routes, one parser") is in progress.** Route B works from the
CLI since `ad52e1a` and from the web app since `be1c077`. The parse layer both routes
share is tested since `92549f8`, the web routes since `5294a73`, and the session loader
checks Pass 2 as strictly as Pass 1 since `33afced`. **Remaining:** a tester run moves
`P9d`'s three green tests out of the red file.

**Phase 8 ("Show the chain") is complete at `576d4f0`.** Both `GET /assumptions` and
`POST /valuation` render the adjusted income statement, cash flow statement, balance sheet
with balance check, applied adjustments, reconciliation, historical FCFF, and assumption
provenance sentences. Substituted ratios are marked with `SUBSTITUTED` and provenance.

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
4. **Three test cases are red on purpose.** On macOS `pytest -q` reports `4 failed, 379
   passed`: three red cases and the held CAPM test. That is the expected
   state. Do not fix it by weakening it; fix backlog item 2. The gate
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
