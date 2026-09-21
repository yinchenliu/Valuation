# Where the build stands

**Measured, never planned.** Every number here carries the commit it was measured at.
A number with no commit beside it is not a measurement. Re-measure on every update;
never carry a figure forward.

**Measured at `d1854fb`, 2026-09-20**, on branch `build/phase-1-2`. Two work units
have been accepted: `P1-suite` and `P2-hygiene`. Both were reviewed and approved. The
journal is [.agent/journal/INDEX.md](.agent/journal/INDEX.md).

---

## 1. The gates, today

| Gate | Command | Result at `d1854fb` |
|---|---|---|
| Tests | `.venv/Scripts/python.exe -m pytest -q` | **20 tests. 19 pass, 1 red on purpose**, 0.26 s |
| Tests, phase-1 form | `... -m pytest -q --ignore=tests/unit/test_dcf_rule3_red.py` | **19 passed**, 0.12 s |
| Lint | `.venv/Scripts/python.exe -m ruff check .` | **5 errors**, every one `BLE001` |
| Types | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | **33 errors in 4 files**, 18 files checked |

**The lint gate is one rule away from clean.** All 5 remaining errors are blanket
`except Exception`: `api/routes_valuation.py:96` and `:220`, `cli.py:758`,
`ingestion/claude_extractor.py:795`, `tests/test_e2e_all_googl.py:106`. They are
backlog item 8 and phase 5 owns them. **They are deliberately left visible.**
Suppressing them would delete the record of a defect instead of fixing it.

### The test gate runs, and one test is red on purpose

`pytest` no longer makes a paid API call during collection. It needs no key, no PDF
and no network, and it finishes in under a third of a second.

**`tests/unit/test_dcf_rule3_red.py` fails deliberately.** It states the requirement
that `run_dcf` must stop when the balance sheet is absent. The code defaults to zero
net debt instead, so the test is red. It goes green when backlog item 2 lands, and
**it is kept, not deleted.** Until then, the phase-1 gate is the `--ignore` form above,
and the `--ignore` is removed the day item 2 is fixed.

Nothing else fails. A second red test means a real regression.

### `tests/`, measured at `d1854fb`

| | At `bc19431` | At `d1854fb` |
|---|---|---|
| `.py` files | 10 | **13** |
| `assert` statements | **0** | **40** |
| files guarded by `if __name__ == "__main__":` | **0** | **9 of 9 scripts** |
| tests collected | 0 | **20** |
| paid API calls during collection | attempted | **none** |

### Coverage of `analysis/`, measured

```
analysis/dcf.py          24 statements    0 missed   100%
analysis/capm.py         30               30           0%
analysis/fcff.py         19               19           0%
analysis/normalizer.py   28               28           0%
analysis/projector.py    68               68           0%
analysis/wacc.py         25               25           0%
TOTAL                   194              170          12%
```

**This is the honest headline.** One module of six has any test. 170 statements are
touched by nothing, and a function no test calls cannot fail — so a coverage gap reads
as a clean report, and the cleaner it reads the worse it is.

Note also: coverage.py does not count a conditional *expression* as a branch, so 100%
branch coverage on `dcf.py` does **not** include the `if latest_bs else 0.0` fallback
at lines 80-81.

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

**This machine reaches Anthropic through Microsoft Foundry, not the public API.**
`ANTHROPIC_FOUNDRY_BASE_URL` and `CLAUDE_CODE_USE_FOUNDRY` are set in the environment;
`ANTHROPIC_API_KEY` and `GEMINI_API_KEY` are not. The installed `anthropic` 1.7.0
exports `AnthropicFoundry`. `ingestion/claude_extractor.py` does not use it yet, so
**extraction cannot run on this machine today.** See backlog item 13.

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
| 1 | **117** silent zero-default sites (`models/` 60, `ingestion/` 49, `analysis/` 6, `api/` 2) | a wrong share price on a clean run | open |
| 2 | `analysis/dcf.py:80` — missing balance sheet gives **zero net debt** | equity value overstated by the whole debt balance | **open, and now proven by measurement.** A red test states the requirement |
| 3 | `analysis/normalizer.py:46` — unknown line item **guesses** `other_operating_expense` | the adjustment lands on the wrong line | open |
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
4. **One test is red on purpose.** `pytest -q` reports `1 failed, 19 passed` and that
   is the expected state. Do not fix it by weakening the test; fix backlog item 2.
5. **Backlog item 1's census grep excludes `tests/`.** The 117 figure counts
   `models/`, `analysis/`, `api/` and `ingestion/` only. The nine scripts hold 33 more
   hits of the same shape. They are dev scripts, not pipeline code, but `tests/` is not
   clean and the figure should not be read as saying it is.
