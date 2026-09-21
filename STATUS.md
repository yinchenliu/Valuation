# Where the build stands

**Measured, never planned.** Every number here carries the commit it was measured at.
A number with no commit beside it is not a measurement. Re-measure on every update;
never carry a figure forward.

**Measured at `bc19431`, 2026-09-20.** Working tree: the agent contract
(`.claude/`, `.agent/`, `docs/`, `AGENTS.md`, this file) is new and uncommitted. No
source file under `models/`, `analysis/`, `ingestion/` or `api/` has been changed.

---

## 1. The gates, today

| Gate | Command | Result at `bc19431` |
|---|---|---|
| Tests | `.venv/Scripts/python.exe -m pytest -q` | **does not run.** 3 collection errors, 0 tests |
| Lint | `.venv/Scripts/python.exe -m ruff check .` | **45 errors** (17 in source, 28 in `tests/` + `cli.py`) |
| Types | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | **33 errors in 4 files**, 19 files checked |

**No gate passes today.** That is the starting position, not a regression. Do not
report a gate as green until it is.

### The test gate does not merely fail — it cannot start

```
ERROR tests/test_e2e_abbv_3years.py   - ValueError: GEMINI_API_KEY is not set.
ERROR tests/test_e2e_googl_3years.py  - ValueError: GEMINI_API_KEY is not set.
ERROR tests/test_e2e_phase2_googl.py  - ValueError: GEMINI_API_KEY is not set.
Interrupted: 3 errors during collection
```

Measured facts about `tests/`, at `bc19431`:

- **0 `assert` statements** across all 10 files.
- **0 files** guard their body behind `if __name__ == "__main__":`. Every file runs its
  whole pipeline — LLM call, network fetch, DCF — at **import** time.
- So `pytest` triggers paid API calls and network requests during **collection**, and
  fails before a single test runs.

These are scripts. They are useful scripts, and they should be kept, but they are not a
test suite and the repository has never had one. See
[docs/5-testing/strategy.md](docs/5-testing/strategy.md).

### Type errors, by kind

| Kind | Count | What it means here |
|---|---|---|
| `union-attr` | 16 | an `X \| None` used without checking for `None` |
| `arg-type` | 11 | includes a real crash path, below |
| `assignment` | 4 | |
| `typeddict-item`, `operator` | 2 | |

By file: `ingestion/claude_extractor.py` 16, `api/routes_valuation.py` 12,
`api/routes_upload.py` 4, `analysis/projector.py` 4.

**One of them is a live defect, not a typing nicety:**

```
api/routes_valuation.py:190: error: Argument "balance_sheet" to "calculate_wacc"
  has incompatible type "BalanceSheet | None"; expected "BalanceSheet"
```

`financials.get_balance_sheet(latest_year)` returns `None` when the year is absent.
`calculate_wacc` then raises `AttributeError` on `None.total_debt`, deep inside the
valuation, and `run_valuation`'s blanket `except Exception` renders that as an error
string on the results page. The user sees a stack-trace message where a named input
error belongs. Rule 3.

---

## 2. What exists

| Area | State |
|---|---|
| `models/` | 3 dataclass modules. `models/company.py` is **dead** — nothing imports `Company` |
| `ingestion/claude_extractor.py` | two-pass extraction, Gemini and Claude providers, multi-PDF year routing. 1,023 lines, the largest file |
| `ingestion/price_fetcher.py` | yfinance prices for CAPM |
| `analysis/` | normalizer, projector, capm, wacc, fcff, dcf. All deterministic |
| `api/` + `templates/` | FastAPI upload → assumptions → result, 3 routes |
| `cli.py` | 760 lines, a full 10-step pipeline runner with its own printing layer |
| `tests/` | 10 scripts, 0 tests (above) |

Two entry points run the same pipeline: `app.py` (web) and `cli.py` (terminal). They
duplicate the orchestration rather than sharing it. See the backlog.

---

## 3. The environment

Built 2026-09-20. `docs/8-build/environment.md` owns the detail.

- **Interpreter:** `.venv/Scripts/python.exe`, Python **3.14.4**, from
  `D:\Software\Python.Python.3.14\python.exe`.
- All 13 runtime dependencies import. pandas **3.0.6**, numpy **2.5.3**, scipy **1.18.1**.
- Dev gates installed from `requirements-dev.txt`: pytest 9.1.1, ruff 0.16.8, mypy 2.3.1.

**The interpreter path in the old `CLAUDE.md` was wrong.** It named
`C:\Users\yinchenliu\Python3\python-3.14.2\python.exe`; that user directory does not
exist on this machine. Every command in the docs now uses `.venv/Scripts/python.exe`.

**pandas 3.0 is a major version.** `ingestion/price_fetcher.py:66` branches on the
pandas version to choose `"ME"` over `"M"` for month-end resampling. That branch has
not been exercised against 3.0 on real data — no run has been made since the
environment was built. Treat any resampling result as unverified until it is.

---

## 4. The agent contract

Set up 2026-09-20, ported from the CLO_AUP build and adapted.

- `.claude/agents/` — `programmer`, `code-reviewer`, `tester`.
- `.claude/hooks/` — `guard_paths.py` (write scope), `seal_baseline.py` +
  `seal_check.py` (the seal on this file, the journal index, and the hooks themselves).
- **`.venv/Scripts/python.exe .claude/check_guard.py` → 48/48 cases correct**, measured
  2026-09-20.
- `docs/INDEX.md` is the map. Agents read it and open only what they need.

**There is no benchmark, by decision.** The tester derives expected values by hand.
`.claude/agents/tester.md` opens with the trap that creates. Read it before dispatching
one.

---

## 5. Open items

Ranked by cost. The full list with evidence is
[docs/9-reference/refactor-backlog.md](docs/9-reference/refactor-backlog.md); this is
the headline.

| # | Item | Cost |
|---|---|---|
| 1 | **119** silent zero-default sites across `models/`, `analysis/`, `api/`, `ingestion/` | a wrong share price on a clean run |
| 2 | `analysis/dcf.py:80` — missing balance sheet gives **zero net debt** | equity value overstated by the whole debt balance |
| 3 | `analysis/normalizer.py:46` — unknown line item **guesses** `other_operating_expense` | the adjustment lands on the wrong line |
| 4 | No test suite at all | nothing detects any of the above |
| 5 | `api/routes_valuation.py:25` — module-global extraction cache, `pop`ped on use | shared across users; a page refresh re-runs the LLM |
| 6 | Five `x / 100 if x else None` conversions | a deliberate `0` from the user is read as "not supplied" |
| 7 | `cli.py` and `api/` duplicate the pipeline | a fix must be made twice or it is made once |
| 8 | Provider default differs between one-PDF and multi-PDF upload | a different model, and a different key, per file count |

**Nothing in this list has been assigned.** No work unit has been dispatched.

---

## 6. Standing traps

Things that have already misled a reader of this repository.

1. **`.gitignore` lists `CLAUDE.md`, but the file is tracked.** The ignore line is
   inert — git does not ignore a tracked file. Editing it therefore *does* dirty the
   tree, which is the opposite of what the line suggests.
2. **`tests/*.pkl` and `cache/*.pkl` are committed.** They are pickled extraction
   results. Loading a pickle executes code in it, so these are not inert fixtures.
   They are also stale relative to any extractor change.
3. **A valuation that runs proves nothing.** Every dataclass money field defaults to
   `0.0`, so the pipeline produces a share price from an extraction that returned
   nothing at all. "It ran" is not evidence. Name an input that came from a filing.
4. **`cli.py` and the web app can disagree.** They build assumptions by separate code
   paths. A figure verified in one is not verified in the other.
