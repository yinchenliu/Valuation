# Where the build stands

**Measured, never planned.** Every number here carries the commit it was measured at.
A number with no commit beside it is not a measurement. Re-measure on every update;
never carry a figure forward.

**Measured at `2c4f69d` (`P3b-pipeline-stops` and its tests, one-team mode), 2026-10-05, by the overall lead**, on branch `main`, **on the Windows machine**
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`.
The build moved back to the Windows machine at `0a8ea54`; the figures from `cde33cb` to
`ac736e7` were measured on the macOS machine. **Forty-seven work units accepted by `69436d9`, fourteen more since (`P14b-pass2-units`, `P14b-reasoning`, `P15a-two-routes`, `P14b-note-figures`, `P14d-finance-leases`, `P3a-one-pipeline`, `P1b-windows-gate`, `P3b-pipeline-stops` and their tests), and not one on its own report.** Every programmer run went to a reviewer that
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

| Gate | Command | Result at `2c4f69d` (Windows) |
|---|---|---|
| Tests | `.venv/Scripts/python.exe -m pytest -q` | **1138 tests. 1136 pass, 2 fail**, plus 5 skipped: the 2 red on purpose |
| **Tests, the gate form** | `... -m pytest -q --ignore-glob="*_rule3_red.py"` | **1136 passed, 5 skipped, 0 failed**, with or without the empty-key prefix: `tests/conftest.py` empties both API keys for every test |
| Lint | `.venv/Scripts/python.exe -m ruff check .` | **4 errors**, every one `BLE001`. `P13g` removed the one in `_run_nri_pass` |
| Types | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | **5 errors in 2 files**, 21 files checked, 0 in `pipeline.py`. `P3b` removed one by widening `plan_filings` and `extract_multi_year` to `Sequence`. `P3a` removed two in `api/routes_valuation.py`; `P15a` removed one before that |
| **Routes** | `TestClient(app.app, raise_server_exceptions=False).get('/')` | **200** |
| **Rule 3 census** | the grep at [rules.md:65](docs/2-rules/rules.md), with `pipeline.py` added | **64**. `P3b` deleted `cli.py`'s `latest_bs.total_debt if latest_bs else 0`, which the census grep never searched (`cli.py` is outside its four directories), so the figure does not move. `P3a` deleted the yfinance share count fallback's `.get("sharesOutstanding", 0)`; `pipeline.py` holds 0 sites. `P13b` removed two conditional zeros (`latest_year`, `implied_share_price`). `P11a` replaced the Pass 1 parser's `.get(field, 0)` reads (114 at `24a9a90`). Under zsh, quote `'--include=*.py'` or the count reads 0 |
| **Write guard** | `.venv/Scripts/python.exe .claude/check_guard.py` | **48/48** |

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

**Two test cases fail deliberately.** `ls tests/unit/*_rule3_red.py` returns two files.
`test_dcf_rule3_red.py` went green when `P10a` closed item 2, and `P10-tests` moved it
into `test_dcf.py`.

- `test_projector_rule3_red.py`: `analysis/projector.py` raises a bare `IndexError` on
  an empty revenue list. Written at `80febe1`, the twin of closed item 14.
- `test_routes_session_rule3_red.py`, 1 case: a cache hit ignores `files` sent with
  `session_file`. Backlog item 52.

**A failure other than those two is a real regression.** Since `P12a-tests`, the item 52
test fails at its own assertion (`:74`) again, on a real PDF it writes.

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

ingestion/claude_extractor.py    667     106    84%     at 1888ccb
ingestion/filings.py             200       0   100%     at 24a9a90
ingestion/session_extraction.py  477      68    86%     at 1888ccb
ingestion/price_fetcher.py        37      21    43%
api/routes_upload.py              51       0   100%     at 24a9a90
api/routes_valuation.py          197       8    96%
analysis/dcf.py                   48       0   100%     at 24a9a90
analysis/capm.py                  55       0   100%     at 24a9a90
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
   not run. That is where 49 of the 114
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
  numpy 2.4.6, starlette 1.7.0. **Corrected 2026-10-04: the user has no Anthropic API
  key.** `.env` holds `ANTHROPIC_API_KEY` with a 27-character value that does not start with
  `sk-ant-` (checked by length and prefix only), so it is not a usable key, but
  `_resolve_claude` reads it as set. The user holds a Gemini key (in `.env`) and a DeepSeek
  key (not in `.env`). No Foundry variable is set.
  **First real Gemini call from this Mac, 2026-10-04 (at `470a075`, overall lead):** the key
  lists 32 Gemini models with `generateContent`, `gemini-3.1-pro-preview` (the code's
  default) among them. Page 21 of the Walmart 10-K 2026-01-31, sent alone as a PDF with
  the code's settings (temperature 0, JSON reply), came back as `713,163` and
  `(Amounts in millions, except per share data)`, the figures printed there; 5.1 s, 599
  input, 42 output and 458 thinking tokens. A whole-filing route A run is not yet measured.
  **`gemini-3.8-flash`, the same day:** the key reaches it (output limit 65,536). Page 21 gave
  `713,163` and the unit statement, page 22 gave `(2,075)`, `794`, `3,027` and `8,022`, each as
  printed; 2.0 s per page; 277 and 242 thinking tokens. The user chose it as the default
  (`P15b-gemini-flash`, planned).
  **First whole-filing route A run, 2026-10-04, at `3c3fac0` (a clean copy), `-m gemini-3.8-flash`,
  Walmart 10-K 2026-01-31, on the user's approval.** Pass 1's first answer failed net income in
  all three years by exactly twice "Other (gains) and losses" (2 x 3,027, 2 x 794, 2 x 2,075):
  the row's sign was wrong. The check caught it and the one retry fixed it. Then 86 of 86 lines
  found, both unit statements found, every check OK; 3 of 3 Pass 2 items found. Tokens: Pass 1
  47,626 in and 4,171 out, the retry 52,603 and 4,171, Pass 2 45,886 and 441. **Against route B
  (Claude, `extractions/WMT.json`): 90 of 100 statement fields equal.** The 10 that differ: (1)
  finance lease obligations, 856 current and 5,905 long-term, are debt in route B and other
  liabilities in Gemini's answer (backlog item 83); (2) share-based compensation is its own field
  in route B and inside other operating activities in Gemini's answer (no analysis code reads
  either field). Pass 2 differs in judgment: both flag PhonePe 700; route B also flags "Other
  (gains) and losses" in each year, Gemini a $37 million FTC settlement and a $0.3 billion JD.com
  loss. **Result: $28.04 against route B's $28.02, but that agreement is partly chance:** net debt
  34,035 against 40,796, WACC 7.74% against 7.68%, enterprise value 265,512M against 272,116M.
  The two effects of the debt difference almost cancel. First measurement for backlog item 36.
  **The user's reading of it, 2026-10-04:** non-recurring items are a judgment each model
  makes differently, so an exact match of the result means nothing; the run's use is to show
  whether route A has a significant defect. Route A works; route B is the main route. Since `P13c`, a shell value wins over
  `.env` (backlog item 46, closed).
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

**History since `2b0b265` (`P15a-two-routes`).** The Foundry gateway, the Entra token and
the Anthropic API route below are removed on the user's decision of 2026-10-04. Route A
reads a filing through the Gemini API (`gemini-3.1-pro-preview`, the default provider);
Claude reads a filing only in a Claude Code session (route B). The table below is the
record of how the Windows machine reached Claude before that.

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
| 68 | The CLI prints no assumption label | **new, the `P13b` review.** `SUBSTITUTED`, `REPEATED` and `DROPPED` show on the web page only (rule 6) |
| 98 | `runpy.run_path` defeats a patch on the module it re-executes | **new, the `P3b` tester.** One test could not fail. Fixed in `tests/`; the one other `runpy` site is sound |
| 99 | `api/routes_valuation.py:199`, the legacy `file_path` branch, is reached by no test | **new, the `P3b` tester.** Correct as written; nothing would report it if it broke |
| 100 | A filing citation gives one page number, sometimes the PDF index and sometimes the printed page | **new, the `P3b` tester.** Walmart's balance sheet is PDF page 22 and printed page 54 |
| 70 | Walmart stage 10 differs by 1M between runs on one tree | **new, the `P13e` review.** Cause not measured |
| 73 | Some bad first Pass 2 replies stop with no retry and no filing name | **new, the `P13g` review** |
| 71, 74, 75, 76 | census grep blind to two-line zeros; retry `OverflowError`; the guard's false denials; the form's `projection_years` bound | **new, minor**; see the backlog |
| 62 | No failed reading check reaches the web page, for either route | **new at `P12a`.** Route A prints to the server console; route B's failures print in `check` and the CLI. Only the balance `FAIL` shows on the page |
| 64 | The page check lets a label written across two printed rows take either row's figure | **new, `P12a` round 2 review's F6.** Needs a label the filing does not print; stated in the docs |
| 63 | A filing with no text layer uses up route A's two retries | **new, `P12a` review's F5.** Not live: all 16 filings have a text layer |
| 78 | The "already converted" guard sees balance sheets only | **new, the `P14a` review's F5.** No call site converts twice today |
| 79 | Route A's unit stop does not name the PDF | **new, the `P14a` programmer.** The same shape as item 73 |
| 80 | The arithmetic check table and route B's failed-check messages are in printed units, with no label | **new, the `P14a` programmer.** For a filing in thousands, `printed=11,313,853` shows beside statements in $M |
| 82 | The CLI cache key stores the model as "(provider default)" | **new, latent.** A change of default would label old figures with the new model. Assigned to `P15b-gemini-flash` |
| 83 | Finance lease obligations: debt or not? The schema does not say | **new, silent. The user decided "83a" (they are debt); assigned to `P14d-finance-leases`.** Walmart: Claude counted 6,761M of finance leases as debt, Gemini did not; net debt differs by that much |
| 47 | The income statement shown has no interest income row | **new, display.** EBT does not add up from the rows shown |
| 52 | A cache hit ignores `files` sent with `session_file` | **new, found by the `P9b` review.** Hand-built requests only |
| 51 | The arithmetic check's `WARN` branch is dead | **new, found by `P9c`** |
| 53 | The session loader imports `_NRI_SCHEMA` by its private name | **new, the `P9d` review's F1, minor** |
| 54 | `GET /assumptions` with no filing shows an empty form and no message | **new, found by the `P9b` tester** |
| 36 | **The same filing extracted twice gave share prices 16% apart** — $343.15 against $296.01 | **half closed at `7354698`.** On the user's decision, `low`-confidence items are now withheld and listed. **The variance itself is still unmeasured** — one pair is an observation, not a range, and the single occurrence that prompted it cannot be sized: three cached extractions hold **zero** `low` items between them |
| 39 | `models/financial_statements.py:28` defaults `confidence` to `"high"` | the last place absence becomes the strongest reading. **No live path reaches it**, so the decision is in force today; it is a type-level gap |
| 40 | Five dev scripts produce a price neither entry point would | **created by `7354698`.** They apply `low` items both entry points withhold, and print no excluded block |
| 37 | `analysis/wacc.py`'s new stop states an inference as a fact | the stop is right; the message asserts the extraction failed when a real deleveraging produces the same pattern. **Message only** |
| 31 | `discount_cash_flows`' `wacc` is unguarded on a **direct** call | **latent.** The `run_dcf` chain stops two lines later, so no current path reaches it |
| 1 | **114** silent zero-default sites — `models/` 60, `ingestion/` 49, `analysis/` 3, `api/` 2 | **worse than its original description.** It does not produce zeros; it produces a signed, correctly-scaled figure that tracks the filing and reads as a measurement |
| 8 | Blanket `except Exception` at five sites | **it swallowed the web outage for the life of the repository**, because the error page rendered through the same broken call |
| 6 | Five `x / 100 if x else None` conversions | a deliberate `0` from the user is read as "not supplied" |
| 22 | `analysis/wacc.py:37` — zero debt balance gives a 0% cost of debt | missing data read as a measurement |
| 23 | `analysis/fcff.py` holds **no `raise` at all** | wholly empty statements return a well-formed result with `fcff = 0.0` |
| 10 | D&A subtraction buried in the parser, `ingestion/claude_extractor.py:479` | an accounting decision taken inside a parser, on two zero-defaulted values |
| 93, 94, 95, 96, 97 | two more no-network copies that refuse the loopback address; `_parse_files_param`'s bare `int()` message; a now-unreachable third copy of the fiscal-year rule; `ValuationRun.latest_balance_sheet` read by no production code; two templates that render a multi-line error as one paragraph | **new, `P1b` and `P3b`.** Each is small and each is recorded in the backlog with its evidence |
| 5 | `api/routes_valuation.py:31` — module-global extraction cache, `pop`ped on read | shared across users; a page refresh re-runs the paid extraction |
| 11 | **10** type errors, down from 33 | one is a live crash path. Every removal so far was a real defect, never an annotation |
| 23 | `analysis/fcff.py` holds no `raise` for empty statements, and `calculate_fcff_projected` has **seven** unguarded float parameters | wholly empty statements return a well-formed result with `fcff = 0.0` |
| 16 | Nine scripts carry a `sys.path.insert` to a path that does not exist here | none runs as `python tests/<name>.py`. Use `-m tests.<name>` |
| 26 | `api/routes_valuation.py:152` branches on a character every path contains | **latent.** Live only on the legacy no-year branch. My first write-up of this was wrong and was corrected by review |
| 17 | `analysis/capm.py:14` imports from `ingestion/` | a layering break |
| 18 | The lint gate's rule set is unpinned | a ruff upgrade changes what the gate enforces, with no commit to point at |
| 28 | `api/routes_upload.py:27` — `str \| None` used as a path segment | the last type error in that file |
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
| 45 | The CAPM constant-market stop was reached only on older SciPy | `1ae0069` |
| 48 | The equity bridge did not subtract noncontrolling interest | `dd1e225` |
| 2 | A missing balance sheet gave zero net debt | `dd1e225` |
| 43 | The fiscal year came from the filename, unverified | `bf6eb20` |
| 56 | Pass 1 asked the model to compute | `ae27f47` |
| 59 | Nothing checked that a printed line is on the page it cites | `a64818b` |
| 25 | An adjustment whose year matches no statement was discarded | `47b8b09` |
| 38 | A 100% equity weighting was invented when market cap and debt were both zero | `47b8b09`, with a stop on a market cap of 0 or below |
| 15 | `latest_year` returned `0` for an empty extraction | `aa6f80d` |
| 32 | Zero diluted shares rendered a share price of `0.0` | `aa6f80d` |
| 39 | `confidence` defaulted to `"high"` | `aa6f80d` |
| 42 | A supplied growth list longer than the projection was cut with no label | `aa6f80d` |
| 46 | `.env` overrode the environment, so unsetting a key did not stop a paid call | `P13c-env-override`, `5b03600` |
| 65 | `upside_downside` returned 0.0 on a zero price | `2a09d3c` |
| 66 | `derive_assumptions` padded the caller's growth list | `d1b4ad2` |
| 67 | `projection_years` was never checked | `d1b4ad2` |
| 69 | A negative debt balance gave weights above 1 | `5c4fb67` |
| 50 | Route A returned `[]` when Pass 2 could not be read | `bce6fae` |
| 44 | The Pass 1 schema asked for units as a free string, unread | `bf428d3` (`P14a`), locked at `69436d9` (`P14a-tests`) |
| 38b (a) | A supplied cost of debt with zero debt lines gave 100% equity | `bc30be4` (`P13h`), locked at `98b908e` (`P13h-tests`) |
| 77 | Pass 2 asked the model to convert a note's figure into the statements' units | `dde9b25` (`P14b-pass2-units`), locked at `21125ed` |
| 81 | The Pass 2 summary line miscounted the items not confirmed | `49cf0f5` (`P14b-reasoning`), locked at `158f25d` |
| 83 | The Pass 1 schema did not say whether a finance lease obligation is debt | `78d21c4` (`P14d-finance-leases`), locked at `9e49bef` |
| 7 | `cli.py` and `api/` duplicated the valuation sequence | `dc81088` (`P3a-one-pipeline`), locked at `ac736e7` |
| 49 | Several PDFs, one with no year: the filing was dropped silently | `2c4f69d` (`P3b-pipeline-stops`), locked in the same commit |
| 72 | `cli.py`'s conditional zeros, the census does not search that file | `2c4f69d`: the `shares` half at `dc81088`, the `total_debt` half here |

**At `a64818b` these tables hold 24 closed items and 37 open ones** (item 23 appears twice above). They are the headline, not the whole list: items 55, 57, 58, 60 and 61 are open in the backlog and not shown here. Items 19 to 28 did not exist when this build
started — **every one of them was found by running the code**, not by reading it. So were
41 and 42, both found at `6e58f13` by a reviewer exhausting inputs rather than reading
the branch.

**Phase 14 (read printed unit statements, check on page, convert in Python) is in progress.** `P14a` (`bf428d3`) closes item 44: Pass 1 reads `units` and `share_units` with pages, page check verifies whole statements on income statement / share pages, Python converts once to millions per filing in both routes, balance sheet tolerance is 1 printed unit (0.001 $M for thousands) with `printed_unit_in_millions`, session files are `v3`. `P14a-tests` (`69436d9`) repaired 291 fixtures and added 44 new tests locking all unit behaviors. Gates at `69436d9`, measured: gate 954 passed, full 2 failed (the known two), ruff 4, mypy 9 in 4 files, census 65, route 200, guard 48/48.

**`P14a` round 2 review, `P14a-tests` and the three commits from `bf428d3` ran outside Claude Code** (no Claude co-author line), so the write guard did not run. The orchestrator re-checked them at `6830188`: the gates above, re-run; the tester's changes to old tests only add `printed_unit_in_millions=1.0` and the v3 shape, and change no expected value; the unit page check on the real Okta 10-Ks (pages 64, 58, 57) does not find `(in thousands)` and finds the whole statement. `bf428d3` also carries an unrelated change to `.claude/output-styles/ste100.md`.

**The two orchestrator follow-ups of `P14a` are done.** `extractions/WMT.json` (not in git) is now `session-extraction-v3`: `units` and `share_units` both `(Amounts in millions, except per share data)`, page 21; the v2 copy is in the session scratchpad. `session_extraction check` exits 0: 89 of 89 lines found, both unit statements found, total L + E 284,668 = 284,668. `cli.py --session-file extractions/WMT.json` with both keys empty: revenue 713,163 (page 21, FY2026), PV of terminal value 214,819M, implied price $28.02, downside -73.1%, unchanged. The `extract-filing` skill now teaches the v3 unit statements; it said before that two scales must stop.

**From 2026-10-04 two teams build.** Antigravity's main agent (Gemini) is the build lead and runs the programmer, reviewer and tester; the Claude Code session is the overall lead and accepts each unit. `AGENTS.md`, "Two teams"; `.agent/QUEUE.md`.

**`P14b-pass2-units` is accepted at `21125ed`, the first unit the build team ran end to end.** It closes item 77 on the user's "fix 77a": each Pass 2 item copies its figure as printed, its page, and the printed words that state its unit; Python reads the scale, looks both up on their pages, stops on either not found, and converts each item with its own scale. Session format v4. The overall lead re-ran all 12 criteria on its own Walmart v4 copy: `check` exit 0, 4 of 4 items, 89 of 89 lines; the PhonePe item is 0.7 from `$0.7 billion` on page 27 and 700 $M after conversion; stages 1 to 10 identical to the v3 run, $28.02; five edited copies each stop and name the right item; route A, stubbed on the real PDF, stops on a mis-cited amount with 0 network attempts. One minor finding, item 81 (a miscounted summary line), goes to `P14b-reasoning`. `extractions/WMT.json` is now v4; the `extract-filing` skill teaches the v4 item.

**`P14b-reasoning` is accepted at `158f25d`.** Every provider resolution carries a `reasoning_label`, shown by the CLI and on both pages (route B: "as the Claude Code session ran; not set by this code"); item 81 is closed. Its streamed Claude call with adaptive thinking at `config.EXTRACTION_EFFORT` passed every stub check, but the user has no Anthropic key, so no real call measured it, and `P15a-two-routes` deletes it on the user's decision "1a". `P15a-two-routes` is `ready`.

**`P15a-two-routes` is accepted at `525b98f`, after one rework round.** Two extraction routes only: route A through the Gemini API, the default provider (`-p claude` stops and names route B); route B, a Claude Code session file. Foundry, Entra, the Anthropic API path, `anthropic` and `azure-identity` are gone. Round 1 found that 21 tests passed only because `.env` held the user's real Gemini key; `tests/conftest.py` now empties both keys for every test. A stubbed Gemini run on the real Walmart PDF gives statements and items equal to route B's. `P14b-note-figures` is `ready`.

**`P14b-note-figures` is accepted at `ac4af5a`, after one rework round.** Rule 1 option B is in force: the Pass 1 prompt lets a figure come from a note or MD&A, one printed line with its page, copied in the unit printed there. Check B1 (`_row_scale_failures`) reads every Pass 1 row's page and the page before it for a parenthesised unit statement of the filing's scale for that row's kind, and stops both routes when none is found (route A after its retries, `check` exit 2). Walmart: 89 rows checked on 4 pages, 0 not confirmed; stages 1 to 10 identical to `525b98f` but for the new summary line, $28.02. A scan of the 16 filings' statement title pages and the page after each (320 pages) found a money scale on every primary statement page. Round 1 found rule 3 fallbacks in the check (an absent key gave 0 failures) and a criterion 10 table that named filings not in the repository; round 2 fixed both. Its limits are items 84 (a statement on the page need not govern the row's table) and 85 (three texts do not name B1). The `extract-filing` skill teaches option B and B1. `P14d-finance-leases` is `ready`.

**From 2026-10-05 one team builds, on the user's words** ("you can takeover the build. i will ask you to change to 2 teams once antigravity token is back"). The Gemini quota ran out during `P14d-finance-leases`. The overall lead now also runs the programmer, code reviewer and tester as Claude subagents, so the write guard and the seal run again. `.agent/QUEUE.md` holds the mode line.

**`P14d-finance-leases` is accepted at `9e49bef`.** It closes item 83 on the user's "83a": the Pass 1 schema and prompt say that finance lease obligations are debt and operating lease obligations are not; `CACHE_FORMAT` is `p14d-finance-leases-v1`. Its Gemini programmer and reviewer finished; its Gemini tester stopped part way, and that work was committed as found (`78d21c4`, the user's "2a"). A Claude tester finished it: it deleted a test that asserted CAPM values copied from a run, and rebuilt the Walmart debt arithmetic from PDF page 22 inside the test, so the suite no longer needs the untracked `extractions/WMT.json` (clean checkout: 1087 passed, 5 skipped). Walmart route B does not move: ST debt 10,994, LT debt 40,529, net debt 40,796, $28.02. No Gemini run has shown that route A follows the rule. The `extract-filing` skill teaches the rule. Phase 3 is next.

**`P3a-one-pipeline` (Phase 3, part 1) is accepted at `ac736e7`.** It closes item 7. A new root module, `pipeline.py`, holds the valuation sequence once: `adjust_financials` (partition the items, normalise) and `value_company` (assumptions, market data, CAPM, share count, WACC, projection, DCF). `cli.py` and both web routes call it. Walmart does not move: the CLI gives $28.02 with only the "ERP from history" line moved (item 89), and the web pages are byte-identical with the market data held fixed. **One behaviour changed, on the user's rules:** the yfinance share count fallback is deleted, so a filing with no diluted share count now stops and names `diluted_shares` in both entry points, with no market call (rules 3 and 5). The review's rule 2 finding on the `assumptions` dict is accepted until item 88, on the user's decision "Accept until item 88". New items: 87 (the web form rounds its defaults, $27.01 against $28.02), 88, 89, 90, 91. `P3b-pipeline-stops` (items 49 and 72) is next; its assignment is not written.

**`P3b-pipeline-stops` (Phase 3, part 2) is accepted, with its tests, 2026-10-05.** It
closes items 49 and 72. `ingestion/filings.require_fiscal_year_per_filing` holds the rule
"with more than one filing, every filing needs a fiscal year above 0" once;
`parse_pdf_args` and `_run_extraction` both call it, and both
`valid = [(y, p) for y, p in filings if y > 0]` filters are gone. **A yearless filing now
stops both entry points and the message names every offender, before any PDF is opened.**
`pipeline.ValuationRun` carries a required `total_debt`, a missing latest balance sheet
stops the run before any market call, and `cli.py` stage 8 prints `run.total_debt`. The
code reviewer approved round 1 after re-executing all 17 criteria; round 2 answered its
F1 (the stop message's "rename the file" remedy was false on the command line) and F4.

**Its tester had to be run twice, and the second run is why the unit is trustworthy.**
Round 1 wrote 825 lines of passing tests and measured nothing. Round 2 audited them and
found that the CLI stop test ran `cli.py` through `runpy.run_path`, which executes the
file into a fresh namespace: the patch on the `cli` module object was never the name the
fresh copy bound, so the assertion "neither extractor was called" **could not fail**. A
test that cannot fail is worse than no test, because the gate reports it green. Two more
weaknesses were found and fixed the same way.

**Measured by the overall lead at the commit, on the Windows machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:**
gate `1136 passed, 5 skipped, 0 failed`; full suite `2 failed, 1136 passed, 5 skipped`,
the 2 red on purpose; lint 4, every one `BLE001`; types **5 errors in 2 files**; census
64; `GET /` 200; write guard 48/48. **Mutation 16 re-run by the overall lead**, not read:
`require_fiscal_year_per_filing` made to return without raising turns **12** named tests
red, exactly the 12 the tester lists, and the file was restored byte-identical.
80 of 80 assertions are hand-sourced, 0 from the code's output.
New items: 98, 99, 100. Items 87, 89, 90 and 92 are corrected in the backlog with facts
measured on 2026-10-05, and **item 90's correction changes its fix**: the constant
`config.DEFAULT_TERMINAL_GROWTH_RATE` already exists and is read by nothing.

**Phase 13 (silent defects first, the user's decision of 2026-10-03) is complete at `98b908e`.** Wave 1: `P13a` (`47b8b09`) closes items 25 and 38, `P13b` (`aa6f80d`) closes items 15, 32, 39 and 42, each reviewed and tested. `P13c` (`5b03600`) closes item 46 after three review rounds, and `P13c-tests` locks the key order and both labels without reading the real `.env`. Wave 1 is done. **Wave 2 is done at `bce6fae`**: `P13d` item 65, `P13e` items 66 and 67, `P13f` item 69 and 38b part (b), `P13g` item 50, each reviewed and tested. **Wave 3, on the user's option 1 of 2026-10-04:** `P13h` (`bc30be4`) closes item 38b part (a) with `--confirm-zero-debt` and a "Confirm zero debt" checkbox; `P13h-tests` (`98b908e`) locked all 53 cases.

**Phase 12 (every printed line is found on its page) is done at `1888ccb`.** `P12a`
(`a64818b`): both routes look up each Pass 1 line's label and figure on its cited page
with `pdfplumber`, and a line not found is a failed check, shown, figures kept. Walmart:
89 of 89 lines found, about 0.55 s. An invented row that keeps the balance sheet in
balance (`Other current assets` = 4,124, page 22) now fails. Three limits are stated in
`docs/3-architecture/extraction.md`. `P12a-tests` gave the 24 fixtures real PDFs and
locked each outcome with 98 hand-derived cases.

**Phase 11 (printed lines; Python sums) is done.** `P11a` (`ae27f47`): every Pass 1
money field is a list of printed rows, Python sums, the balance-sheet plug is gone, and a
failed balance check shows `FAIL`. Session files are `session-extraction-v2`.
`P11a-tests` rewrote the 40 old-shape fixtures and tested every new behaviour. Walmart,
re-read in the new shape: every printed subtotal and total agrees with Python's sum
(total assets 284,668 = 284,668), and the implied price is unchanged at $28.02.

**Phase 10 (the user's fixes of 2026-10-02) is done at `24a9a90`.** `P10b` closed item
45, `P10a` closed items 48 and 2, `P10c` closed item 43, and `P10-tests` repaired the 36
fixtures they turned red on purpose and tested all three. Walmart's implied price is $28.02 with the new bridge.

**Phase 9 ("two extraction routes, one parser") is done.** Route B works from the
CLI since `ad52e1a` and from the web app since `be1c077`. The parse layer both routes
share is tested since `92549f8`, the web routes since `5294a73`, and the session loader
checks Pass 2 as strictly as Pass 1 since `33afced`, with every stop tested since
`a375dae`. **Phase 9 is done at `a375dae`**; `docs/8-build/phases.md` records the
evidence for each criterion.

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
3. **`cli.py` and the web app can still disagree.** Since `P3a-one-pipeline` both run
   the valuation through `pipeline.py`, and a test shows one price for the same inputs.
   But each still extracts and parses its own inputs, and the web form posts its
   defaults back rounded to one decimal: Walmart is $27.01 on the web page and $28.02 in
   the CLI (backlog item 87).
4. **Two test cases are red on purpose.** On macOS `pytest -q` reports `2 failed, 857
   passed` at `bce6fae`. That is the expected
   state. Do not fix it by weakening it; fix backlog item 2. The gate
   form that excludes it is `pytest -q --ignore-glob="*_rule3_red.py"`.
5. **A green test inside `*_rule3_red.py` is invisible to the gate.** That happened
   once, at `38b903c`. Move a test out of the pattern the day it goes green.
6. **A test can pass because it cannot fail.** `P3b`'s first CLI stop test ran `cli.py`
   through `runpy.run_path(..., run_name="__main__")` and then asserted that
   `cli.extract_financials` was never called. `runpy` executes the file into a **fresh
   namespace**, so `monkeypatch.setattr(cli, "extract_financials", ...)` patched a name
   that namespace never bound, and the assertion was true whatever the code did. The
   gate reported it green. A patch on a module that `cli` imports **from** still holds,
   which is why `tests/unit/test_pipeline.py:465` is sound. Backlog item 98.
7. **A tester's `fail` is a verdict about the code, not about its own work.** All four
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
