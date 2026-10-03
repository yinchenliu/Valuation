---
agent: code_reviewer
assignment: P10b-capm-variance
round: 1
verdict: approved
---

# Review of P10b-capm-variance, round 1

Programmer entry: `.agent/journal/2026-10-02T2127-programmer-p10b-capm-variance.md`
Diff reviewed: `git diff 54c966f -- analysis/capm.py` (+21 / -3, one file).

## The guard checks

Run over `analysis/capm.py`, the one file in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean |
| lookup with a fallback — `.get(k, 0)` | clean |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (`models/ analysis/ api/`, no hit) |

The diff adds no import. `capm.py:16` imports `ingestion.price_fetcher`: that is backlog
item 17, in a line the unit did not touch.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `market_returns`, every value identical | yes: names `market_returns`, the value, the count, "variance is zero" | `capm.py:91-97`; scratch call with `[0.01]*12` |
| `market_returns`, all `0.0` / mixed `0.0` and `-0.0` | yes, same stop | scratch call: `same value (0.0) in all 12 observations` |
| `market_returns` with one NaN, or all NaN | yes, via the unchanged NaN check | `capm.py:104`; scratch call reaches it (see F1 on its wording) |
| `stock_returns` with one NaN | yes, via the NaN check | scratch call; wording see F1 |
| empty series | yes, the minimum-count stop fires before `market_returns[0]` is indexed | scratch call: `hold 0 observations; beta needs at least 3` |
| unequal lengths / fewer than 3 | unchanged | `capm.py:66`, `:74` |

The new check adds no fallback and returns no number. Indexing `[0]` is safe because
`:74` guarantees `size >= 3`; I confirmed the empty case stops by name, not with
`IndexError`.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | n/a: returns are ratios; the unit moves no figure |
| percentages converted at the route boundary, once | n/a |
| falsy not treated as missing | clean. `np.all(x == x[0])` is an identity test; a zero series stops for zero variance, which is correct, not because it is falsy |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | no new import; `:16` is pre-existing item 17 |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | failing test passes | 20 passed | `.venv/bin/python -m pytest -q tests/unit/test_capm.py` → `20 passed` | yes |
| 2 | the gate, by name | 398 passed, 0 failed | Working tree (with P10a's in-flight `models/` and `dcf.py` edits): `398 passed`. Isolated: `git archive 54c966f` to `/tmp/p10b-base`, gate → `1 failed, 397 passed`, failure set = {`test_capm.py::test_beta_stops_when_the_market_series_has_no_variation`}. Same tree plus only this unit's `capm.py` → `398 passed`, failure set = {}. Full suite there: failures = exactly the three `*_rule3_red.py` tests | yes |
| 3 | message is the repository's | names `market_returns`, variance | `market_returns has the same value (0.01) in all 12 observations, so its variance is zero; …` | yes |
| 4 | coverage 100%, statements and branches | 55 stmts 0 miss, 20 branch 0 partial | `COVERAGE_FILE=/tmp/p10b-review.coverage … --cov=analysis.capm --cov-branch` → `analysis/capm.py 55 0 20 0 100%`. The assignment's path form `--cov=analysis/capm.py` → `No data to report`, confirming the programmer's finding | yes |
| 5 | lint and types, no new error | 5 / 10 in 4 | `ruff check .` → `Found 5 errors.`; `ruff check analysis/capm.py` → `All checks passed!`; mypy exact gate command → `Found 10 errors in 4 files`, none in `capm.py` | yes |

Scope: only `analysis/capm.py` and the journal entry are the unit's. `tests/` has no diff
against `54c966f`. The other modified files (`models/financial_statements.py`,
`analysis/dcf.py`) are P10a's.

The identity test is correct against SciPy's own check: `_stats_py.py:10513` raises when
`np.amax(x) == np.amin(x)`, which for non-NaN input is the same predicate. The
programmer's measurement that `np.var([0.01]*12)` is `3.009e-36`, not `0.0`, reproduces,
so the assignment's override of backlog item 45's suggested `np.var == 0` was right.
The change is justified by a reason (the wrong message), not by a target number.

## Findings

### F1 — The NaN branch's message now describes a case that can no longer reach it · `minor`

**Evidence:** scratch call with a NaN in `stock_returns` only → `market_returns has variance 0.0011916666666666668 over 12 observations; a market series with no variation explains nothing and no beta exists for it` (`capm.py:105-112`).
**Rule or document:** none broken: the run stops and names both series. The diagnosis is wrong. Before this unit the trailing clause at least matched the constant-market case on older SciPy; after it, every input that reaches `:104` is a NaN observation, and the message blames market variation that exists. The lines are untouched (assignment step 2 said keep the check), so this does not block.
**What would fix it:** a later unit rewords `:105-112` to name the NaN observation, in whichever series it is, as the cause. The orchestrator should record it.

### F2 — The `MINIMUM_REGRESSION_OBSERVATIONS` comment's measurement does not hold on 1.17.1 · `note`

**Evidence:** `.venv/bin/python` (SciPy 1.17.1): `stats.linregress([0.01, 0.02], [0.03, 0.05])` → `stderr=0.0`, not `nan` as `capm.py:32-35` says ("Measured against scipy 1.18.1").
**Rule or document:** none. The derivation (n − 2 ≥ 1) still holds, and on 1.17.1 the stop matters more: an n = 2 regression would return a finite, false `std_error` of 0.0 rather than NaN. Untouched lines; the programmer raised it too.
**What would fix it:** state both versions' behaviour in the comment when the file is next assigned.

### F3 — A near-constant market series passes both checks and returns a beta of 3.6e14 · `note`

**Evidence:** scratch call, `market_returns = [0.1]*11 + [nextafter(0.1, 1)]` → `(3.6e14, R² 0.0192, std_error 8.1e14)`. SciPy's own check misses it as well, so this behaviour is the same as at `54c966f`. A series of `inf` stops with "variance is zero", which is not literally true (the variance is NaN), but such a series cannot come from a price history.
**Rule or document:** none by itself. The data are present, and `describe_beta_reliability` labels the result NOT RELIABLE (R² < threshold), which is the rule 6 path. Outside this assignment, which asked for identity.
**What would fix it:** nothing in this unit. Recorded so the orchestrator can decide whether a relative-variance floor is wanted.

### F4 — Assignment criterion 4 uses a coverage form that measures nothing · `note`

**Evidence:** `--cov=analysis/capm.py` → `WARNING: Failed to generate report: No data to report.`; `--cov=analysis.capm` → 100%.
**Rule or document:** an assignment defect, not code. The programmer reported it.
**What would fix it:** the orchestrator uses the module form in future assignments and in `docs/8-build/environment.md`, if that file uses the path form.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 17 — `analysis/` imports from `ingestion/` | `analysis/capm.py:16` | no |
| 1 — `r_sq = 0.0`, `std_err = 0.0` on an overridden beta | `analysis/capm.py:229-230` | no |
| 45 — the item this unit closes | `analysis/capm.py:91` | yes, it is the fix |

No recorded user decision covers any line here, and the assignment claims none.

## Verdict

`approved`

The change does exactly what the assignment asked: an identity test before
`stats.linregress` that stops with the repository's message naming `market_returns`, its
value, its count and its zero variance. The NaN check stays. I re-ran every
done-criterion myself. Comparing failure sets by name, on an isolated tree, the unit
removes exactly `test_beta_stops_when_the_market_series_has_no_variation` from the gate
and adds no failure. Coverage stays at 100% statements and branches. Lint and types are
unchanged. No rule is broken. F1 is a minor defect in untouched wording. F2 to F4 are
notes for the orchestrator. None of them blocks.
