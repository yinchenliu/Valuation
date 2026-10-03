---
agent: programmer
assignment: P10b-capm-variance
round: 1
status: complete
files_touched: [analysis/capm.py]
verdict:
---

# P10b-capm-variance: stop on a constant market series before SciPy does

## What I did

In `analysis/capm.py::calculate_beta`, `capm.py:91` now stops when every value in
`market_returns` is identical. The check runs after the length and minimum-count stops,
which guarantee `market_returns[0]` exists, and before `stats.linregress`. The new
`ValueError` names `market_returns`, gives the repeated value and the observation count,
and says its variance is zero. Before this change, SciPy 1.17.1 raised its own message
("Cannot calculate a linear regression if all x values are identical") ahead of the
repository's, and that message names no input. The NaN check after the call
(`capm.py:104`) is unchanged and still catches a NaN observation. I also corrected the
`Raises:` docstring, which said `linregress` "raises nothing for ... a degenerate
series". That is no longer true for a constant regressor on 1.17.1. I did not edit the
test.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the failing test passes | pass | `.venv/bin/python -m pytest -q tests/unit/test_capm.py` gives **20 passed**. Before the change: `1 failed, 19 passed`, with `AssertionError: assert 'market_returns' in 'Cannot calculate a linear regression if all x values are identical'` |
| 2 | the gate | pass | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` gives **398 passed, 0 failed**. At `a375dae` the result was 397 passed, 1 failed (`test_capm.py:473`). No P10a failure exists in this tree: when I ran it, `git status` showed only `analysis/capm.py` modified |
| 3 | the message is the repository's | pass | Scratch call `calculate_beta` with `market_returns=[0.01]*12` and a non-constant stock series gives `market_returns has the same value (0.01) in all 12 observations, so its variance is zero; a market series with no variation explains nothing and no beta exists for it` |
| 4 | coverage of `capm.py` stays 100% | pass | `COVERAGE_FILE=/tmp/p10b.coverage .venv/bin/python -m pytest -q tests/unit/test_capm.py --cov=analysis.capm --cov-branch --cov-report=term-missing` gives `analysis/capm.py 55 stmts 0 miss 20 branch 0 brpart 100%`. The path form `--cov=analysis/capm.py` reports "No data to report", so the module form is used |
| 5 | lint and types | pass | `ruff check .` gives **5 errors**, the same as the `a375dae` baseline in STATUS. `ruff check analysis/capm.py` gives `All checks passed!`. mypy (exact gate command) gives **10 errors in 4 files**, the same as baseline, none in `capm.py` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Test identity with `np.all(market_returns == market_returns[0])` | Assignment step 1. Measured: `np.var(np.array([0.01]*12))` = `3.009e-36` and `np.var([0.1]*12)` = `1.93e-34`, neither of them `0.0` | A `np.var(...) == 0.0` check would miss exactly the input the test uses at length 12 |
| Place the check after the length and minimum-count stops | Those stops guarantee `size >= 3`, so indexing `[0]` cannot fail | Placed earlier, an empty series would raise `IndexError` instead of the named stop |
| Keep the post-call NaN check unchanged | Assignment step 2. A NaN in `market_returns` compares unequal to everything, so the identity check does not stop it. The scratch run with `[0.01]*11 + [nan]` reached the NaN branch and stopped with its message | It is the only stop for NaN observations |
| Wrap in `bool(...)` | `np.all` returns `np.bool_`. Being explicit keeps mypy and the reader certain of the type | — |
| Edit the docstring's `Raises:` text | The old sentence stated that linregress raises nothing for a degenerate series, which 1.17.1 contradicts | Leaving the comment stale would misstate why the new stop exists |

No change was made to reach a target number. This unit moves no figure: it changes
which exception text appears for an input that already stopped the run.

## Rule 3: what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `price_data.market_returns` with no variation | stops and names `market_returns`, with the variance and the count | `capm.py:91`. Scratch call above. `test_beta_stops_when_the_market_series_has_no_variation` |
| `price_data.market_returns` / `stock_returns` of unequal length | stops and names both (unchanged) | `capm.py:66` |
| fewer than 3 observations | stops and names both (unchanged) | `capm.py:74` |
| a NaN observation | stops via the NaN check (unchanged) | `capm.py:104`. Scratch call with a NaN in `market_returns` |

No "defaults to" row exists. The unit adds no fallback.

## Measurements

- `tests/unit/test_capm.py`: failure set before = {`test_beta_stops_when_the_market_series_has_no_variation`}, after = {} (20 passed).
- Gate (`--ignore-glob="*_rule3_red.py"`): failure set before (STATUS at `a375dae`) = {`test_capm.py:473`}, after = {}. 398 passed.
- SciPy on this machine: `1.17.1` (`.venv/bin/python -c "import scipy; print(scipy.__version__)"`).
- Lint: 5 (all pre-existing `BLE001`). Types: 10 in 4 files. Both unchanged.
- Coverage `analysis/capm.py`: 100% statements, 100% branches (20/20).
- Regression sanity: a non-degenerate 12-period series still returns a finite beta (0.979, R-squared 0.995).

## What I did not do

- I did not touch the test file (out of scope, and the assignment says so).
- I did not re-run the gate after P10a's changes land. Any `run_dcf` failures that appear later belong to P10a.

## Findings for the orchestrator

- The module comment above `MINIMUM_REGRESSION_OBSERVATIONS` (`capm.py:27-35`) says it
  was "Measured against scipy 1.18.1", but this machine runs 1.17.1. The n = 2 and
  n < 2 behaviour it describes was not re-measured here. It is low risk because the
  stop fires before `linregress` in either case, but the version claim cannot be
  reproduced on the macOS machine.
- STATUS section 1 can drop the CAPM failure from the gate line once this unit is
  accepted.
- `--cov=analysis/capm.py` (the path form in the assignment's criterion 4) collects no
  data under pytest-cov here. `--cov=analysis.capm` is the form that works.
