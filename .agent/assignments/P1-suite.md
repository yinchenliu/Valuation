---
id: P1-suite
phase: 1 — make the suite runnable
agent: tester
depends_on: []
---

# Make `pytest` collect without an API key, then write the first real tests for `analysis/dcf.py`

## Objective

`tests/` holds 10 files, 0 `assert` statements, and 0 `if __name__ == "__main__":`
guards. Every file therefore executes its whole pipeline — LLM call, network fetch,
DCF — at **import** time. So `pytest` triggers paid API calls during collection and
fails before a single test runs.

That means nothing in this repository detects any defect in the backlog. Until
collection is clean and real assertions exist, every later fix produces an
unverifiable claim.

When this unit is done, `pytest` collects with 0 errors and no API key, the 10 scripts
still run by hand, and `analysis/dcf.py` has its first independently-derived tests.

## What is already true — verify, do not redo

Measured by the orchestrator at `bc19431`, 2026-09-20. If one of these disagrees when
you run it, **stop and report the disagreement** rather than working around it.

| Fact | Command |
|---|---|
| 3 collection errors, 0 tests | `.venv/Scripts/python.exe -m pytest -q` |
| no `.env` file exists; `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` are both unset in the environment | `ls .env` → no such file |
| 27 ruff errors inside `tests/` | `.venv/Scripts/python.exe -m ruff check tests --output-format concise \| wc -l` |
| `pytest-cov` is installed | it is listed in `requirements-dev.txt` |
| `tests/__init__.py` exists, so `tests` is an importable package | `ls tests/__init__.py` |
| there is no `pyproject.toml`, `pytest.ini`, `setup.cfg` or `tox.ini` | `ls pyproject.toml pytest.ini setup.cfg tox.ini` |

The 3 failing collections are `tests/test_e2e_abbv_3years.py`,
`tests/test_e2e_googl_3years.py` and `tests/test_e2e_phase2_googl.py`. Each raises
`ValueError: GEMINI_API_KEY is not set.` from
`ingestion/claude_extractor.py:835`. **That raise is correct behaviour** — it is the
model the rest of the codebase should follow. The defect is that a script reaches it
at import time, not that it raises.

## What to do

1. **Stop `pytest` from executing the scripts at import.** Choose one of the two
   approaches `docs/5-testing/strategy.md` section 4 names, and **state in your entry
   which you chose and why**:

   - **(a) Guard each script.** Wrap the module body in a function and call it under
     `if __name__ == "__main__":`. No file moves, so no data path changes.
   - **(b) Move the scripts.** Relocate them under `tests/manual/` and add
     `tests/conftest.py` with `collect_ignore_glob`. If you do this, every path the
     scripts read must still resolve — three of them load
     `tests/.cache_*_extraction.pkl`.

   Prefer (a) unless you find a concrete reason it does not work. It cannot break a
   data path.

   **Do not delete a script.** `docs/5-testing/strategy.md` section 4: they are useful
   and they are kept.

2. **Put the new tests in their own directory**, `tests/unit/`, so a reader can tell a
   test from a script by its path alone. Add `tests/unit/__init__.py` if the package
   layout needs it.

3. **Write the first real tests for `analysis/dcf.py`.** The file holds three
   functions: `calculate_terminal_value`, `discount_cash_flows`, `run_dcf`.

   Every expected value comes from **hand arithmetic or a closed-form identity**, never
   from running the code. `docs/5-testing/strategy.md` section 1 lists the three
   acceptable sources and the one forbidden one. Write the arithmetic into the test as
   a comment, so the next reader can check it without running anything.

   Worked examples you may use directly:

   - `calculate_terminal_value(100.0, 0.02, 0.10)` → `100 * 1.02 / 0.08 = 1275.0`
   - `discount_cash_flows` with one `ProjectedFCFF` of `110.0` and `wacc = 0.10` →
     `110 / 1.1 = 100.0`
   - `discount_cash_flows` with `wacc = 0.0` → the plain sum of the FCFFs

4. **Lock the `WACC <= g` raise** at `analysis/dcf.py:24-27`. Assert the **exception
   type** and that the **message names both figures**. `pytest.raises(Exception)` alone
   does not count — see `docs/5-testing/strategy.md` section 2.

   The boundary matters: `wacc == terminal_growth_rate` must raise, not only
   `wacc < terminal_growth_rate`. Test the equal case.

5. **Fix the 27 ruff errors inside `tests/`.** They are 22 `I001` (unsorted imports),
   4 `F541` (f-string with no placeholder), 1 `F401` (unused import) and 1 `BLE001`.

   **Leave the `BLE001` in `tests/test_e2e_all_googl.py` alone.** Blanket
   `except Exception` is backlog item 8 and belongs to phase 5. Say in your entry that
   you left it and why.

6. **No unit test may need a key, a PDF, or the network.**
   `docs/5-testing/strategy.md` section 3. Build the dataclasses by hand in the test,
   with only the fields the function under test reads.

## Files in scope

- `tests/**` — every file under it, including new ones.

**Nothing else.** Your write guard enforces this. A denial outside `tests/` is the
permission answering correctly; report the need in your entry rather than working
around it.

## Out of scope

- `analysis/dcf.py` and every other implementation file. You may not edit them. If a
  test cannot pass without a code change, **that is your finding** — report it.
- `pyproject.toml` or any root-level pytest configuration. It is outside your write
  scope. If you need one, say so in your entry and the orchestrator will assign it.
- `tests/.cache_*_extraction.pkl` — do not untrack, delete or load them. They are
  tracked pickles and loading one executes code in it. Three scripts read them; leave
  that alone.
- `.gitignore`, `models/`, `analysis/`, `ingestion/`, `api/`, `config.py` — unit
  `P2-hygiene` is running in parallel and owns those. Do not read them expecting them
  to be stable.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | `pytest` collects with no API key | **0 errors** | `.venv/Scripts/python.exe -m pytest -q --collect-only 2>&1 \| tail -3` |
| 2 | the suite runs and every test passes | 0 failed | `.venv/Scripts/python.exe -m pytest -q` |
| 3 | at least 6 assertions cover `analysis/dcf.py`, each with its source stated in your entry | ≥ 6 | count them in your entry; `pytest -q` proves they run |
| 4 | the `WACC <= g` raise is locked on type **and** message | 1+ test | `.venv/Scripts/python.exe -m pytest -q -k terminal` |
| 5 | a script still runs as a script and still reaches the extraction call | fails with `ValueError: GEMINI_API_KEY is not set.` | `.venv/Scripts/python.exe tests/test_e2e_googl_3years.py` (adjust the path if you moved it) |
| 6 | `tests/` lints clean except the one deferred `BLE001` | exactly 1 error, `BLE001` | `.venv/Scripts/python.exe -m ruff check tests --output-format concise` |
| 7 | coverage of `analysis/dcf.py` is measured, not estimated | report the number | `.venv/Scripts/python.exe -m pytest -q --cov=analysis --cov-report=term-missing` |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/5-testing/strategy.md` — section 1 (where an expected value may come from),
  section 2 (lock the stop), section 3 (no network, no keys), section 4 (what `tests/`
  holds today), section 5 (two counts), section 6 (where to start).
- `docs/2-rules/rules.md` rule 3 — the absent case is most of your work.
- `docs/8-build/phases.md` phase 1 — the four criteria this unit answers.
- `docs/9-reference/refactor-backlog.md` item 4 — the defect that forced this unit.
- `analysis/dcf.py:24-27` — the raise to lock.
- `ingestion/claude_extractor.py:835` — the raise the scripts hit at import today.

## Known open items

- `analysis/dcf.py:80-81` gives `net_debt = 0.0` and `cash = 0.0` when the balance
  sheet is absent. **This is backlog item 2 and it is the highest-cost silent defect in
  the repository.** It is scheduled for phase 4.

  **Do not write a test that asserts `net_debt == 0.0`.** Such a test makes the defect
  permanent and turns its fix red. `docs/5-testing/strategy.md` section 2 names this as
  the single most damaging thing you could write here.

  You may write a test that asserts the **correct** behaviour — a raise naming the
  missing statement — and leave it failing. A red test that states a true requirement
  is doing its job. If you do, mark it clearly and say so in your entry, so the
  orchestrator does not read it as a regression.

- `models/` money fields all default to `0.0`, so you can construct a
  `FinancialStatements` that is empty and still valid. That is backlog item 1, phase 6.
  Use it to build fixtures, but do not assert on a default it produced.

## Backlog items this unit is NOT fixing

- **Item 2** — `analysis/dcf.py:80` zero net debt. Phase 4. Outside your write scope.
- **Item 8** — blanket `except Exception`, including the one in
  `tests/test_e2e_all_googl.py`. Phase 5.
- **Item 12** — the tracked `tests/*.pkl` files. Deliberately left; three scripts read
  them.
- **Item 1** — the 119 zero-default sites. Phase 6.
