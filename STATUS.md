# Where the build stands

**Measured, never planned.** Every number here carries the commit it was measured at.
A number with no commit beside it is not a measurement. Re-measure on every update;
never carry a figure forward.

**Measured at `81816be`, 2026-09-21**, on branch `build/phase-1-2`. Six work units have
been accepted: `P1-suite`, `P2-hygiene`, `P1b-arith`, `P1c-flow`, `P4-normalizer` and
`P4b-normalizer-verify`. Every one was reviewed or verified, and none was accepted on
its own report. The journal is [.agent/journal/INDEX.md](.agent/journal/INDEX.md).

---

## 1. The gates, today

| Gate | Command | Result at `81816be` |
|---|---|---|
| Tests | `.venv/Scripts/python.exe -m pytest -q` | **106 tests. 105 pass, 1 red on purpose**, 3.5 s |
| **Tests, the gate form** | `... -m pytest -q --ignore-glob="*_rule3_red.py"` | **105 passed**, 0 failed |
| Lint | `.venv/Scripts/python.exe -m ruff check .` | **5 errors**, every one `BLE001` |
| Types | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | **33 errors in 4 files**, 18 files checked |

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

### The test gate runs, and one test is red on purpose

`pytest` no longer makes a paid API call during collection. It needs no key, no PDF
and no network.

**One test fails deliberately.** `tests/unit/test_dcf_rule3_red.py` states that
`run_dcf` must stop when the balance sheet is absent. That is backlog item 2, and it is
still open. `ls tests/unit/*_rule3_red.py` returns exactly that one line.

**A failure other than that one is a real regression.**

### `tests/`, measured at `81816be`

| | At `bc19431` | At `81816be` |
|---|---|---|
| `.py` files | 10 | **19** |
| `assert` statements | **0** | **334** |
| scripts guarded by `if __name__ == "__main__":` | **0** | **9 of 9** |
| tests collected | 0 | **106** |
| paid API calls during collection | attempted | **none** |

### Coverage, measured at `38b903c`

```
analysis/capm.py         30 statements    0 missed   100%
analysis/dcf.py          24               0          100%
analysis/fcff.py         19               0          100%
analysis/normalizer.py   36               0          100%
analysis/projector.py    68               0          100%
analysis/wacc.py         25               0          100%
analysis/ TOTAL         202               0          100%
```

**202 of 202 statements in `analysis/`, against 24 at `d1854fb`.** The two lines that
were uncovered at `796de9a` were the guess at the old `normalizer.py:50-51`, which
`P4-normalizer` deleted.

**Two caveats a reader must not skip.**

1. Coverage.py does not count a conditional *expression* as a branch. So 100% branch
   coverage does **not** include `if latest_bs else 0.0` at `analysis/dcf.py:80-81`, or
   any of the other conditional-expression defaults. **Coverage here is not evidence
   that every path is checked.**
2. `ingestion/` and `api/` have **no tests at all.** That is where 51 of the 117
   zero-default sites live, and where the extraction boundary sits.

### Type errors, by kind

| Kind | Count |
|---|---|
| `union-attr` | 16 |
| `arg-type` | 11 |
| `assignment` | 4 |
| `typeddict-item`, `operator` | 2 |

By file: `ingestion/claude_extractor.py`, `api/routes_valuation.py`,
`api/routes_upload.py`, `analysis/projector.py`. **The error set is identical to
`bc19431`** — verified by the code reviewer against a worktree at that commit, with
line numbers normalised. The file count fell from 19 to 18 only because
`models/company.py` was deleted.

**One of them is a live defect, not a typing nicety:**

```
api/routes_valuation.py:190: error: Argument "balance_sheet" to "calculate_wacc"
  has incompatible type "BalanceSheet | None"; expected "BalanceSheet"
```

`calculate_wacc` raises `AttributeError` on `None.total_debt` deep inside the
valuation, and `run_valuation`'s blanket `except Exception` renders that as an error
string on the results page. The user sees a stack-trace message where a named input
error belongs. Rule 3.

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

**Extraction still cannot run**, because `ingestion/claude_extractor.py:352` builds a
plain `anthropic.Anthropic(api_key=…)` and `:830` refuses to start without
`ANTHROPIC_API_KEY`. Backlog item 13 closes that gap.

**There are also no PDFs on this machine.** `10K_filings/` holds one stray `.DS_Store`.
A real valuation needs a filing as well as a working client.

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

Ranked by cost. The full list with evidence is
[docs/9-reference/refactor-backlog.md](docs/9-reference/refactor-backlog.md); this is
the headline.

| # | Item | Cost | State |
|---|---|---|---|
| 19 | `analysis/normalizer.py:68` — one sign rule applied to two kinds of line | earnings moved by **2×** the item, in the wrong direction, on ordinary input | **closed at `38b903c`** |
| 20 | `analysis/capm.py:87` — a **NaN** beta is returned, not raised | a NaN share price renders, because `nan <= g` is `False` and the one working guard does not fire | **open. The highest-cost defect now known.** Confirmed end to end |
| 24 | a red test that goes green stays excluded by the gate | the gate stopped checking the thing the fix was made to guarantee | **closed at `81816be`** |
| 25 | `analysis/normalizer.py:167-170` — an adjustment whose **year** matches no statement is silently discarded | a valuation labelled "normalised" whose figures are GAAP, with no signal | **new.** The item's year and the statements' years come from two separate model passes with nothing reconciling them |
| 8 | Blanket `except Exception` at five sites | **more urgent since `38b903c`** — every stop we add lands in the catch at `api/routes_valuation.py:220` and renders as a bare string | open |
| 1 | **116** silent zero-default sites (`models/` 60, `ingestion/` 49, `analysis/` 5, `api/` 2) | a wrong share price on a clean run | open |
| 2 | `analysis/dcf.py:80` — missing balance sheet gives **zero net debt** | equity value overstated by the whole debt balance | **open, and now proven by measurement.** A red test states the requirement |
| 3 | `analysis/normalizer.py:46` — unknown line item **guesses** `other_operating_expense` | the adjustment lands on the wrong line | **closed at `38b903c`** |
| 4 | No test suite at all | nothing detects any of the above | **closed.** 20 tests, `analysis/dcf.py` at 100% of statements |
| 5 | `api/routes_valuation.py:25` — module-global extraction cache, `pop`ped on use | shared across users; a page refresh re-runs the LLM | open |
| 6 | Five `x / 100 if x else None` conversions | a deliberate `0` from the user is read as "not supplied" | open |
| 7 | `cli.py` and `api/` duplicate the pipeline | a fix must be made twice or it is made once | open |
| 8 | Provider default differs between one-PDF and multi-PDF upload | **extraction cannot run on this machine at all** | open, and now urgent |
| 14 | `analysis/dcf.py:73` — empty `projected_fcffs` raises a bare `IndexError` | a stack trace where a named input error belongs | new |
| 15 | `models/financial_statements.py:295` — `latest_year` returns `0` for an empty extraction | turns "no data" into "year zero" with no error | new |
| 16 | Nine scripts carry a `sys.path.insert` to a path that does not exist on this machine | none of them runs as `python tests/<name>.py` | new |
| 17 | `analysis/capm.py:14` imports from `ingestion/` | a layering break; `analysis/` must not depend on `ingestion/` | new |
| 18 | The lint gate's rule set is unpinned | a ruff upgrade changes what the gate enforces, with no commit to point at | new |
| 21 | `analysis/normalizer.py:68` — an unrecognised `direction` silently takes the `remove` branch | any spelling but `"add_back"` moves the adjustment the wrong way | **closed at `38b903c`** |
| 22 | `analysis/wacc.py:37` — zero debt balance gives a 0% cost of debt | missing data read as a measurement | new |
| 23 | `analysis/fcff.py` holds **no `raise` at all** | wholly empty statements return a well-formed result with `fcff = 0.0` | new |

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
4. **One test is red on purpose.** `pytest -q` reports `1 failed, 105 passed` and that
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
