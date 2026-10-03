---
id: P10b-capm-variance
phase: 10 — the user's fixes of 2026-10-02 (items 43, 45, 48)
agent: programmer
depends_on: []
---

# Stop on a constant market series before SciPy does

## Objective

`analysis/capm.py` calls `stats.linregress` and only afterwards checks the result for
NaN, with a message that names `market_returns` and its variance. SciPy 1.17.1, which
the macOS machine runs, raises its own `ValueError` for a constant regressor first:
"Cannot calculate a linear regression if all x values are identical". So the
repository's message never appears, and
`tests/unit/test_capm.py::test_beta_stops_when_the_market_series_has_no_variation` fails
on that machine. It is the one failure in the test gate. Backlog item 45. **The user
asked for the fix on 2026-10-02.**

## What to do

1. In `analysis/capm.py`, before the `linregress` call, stop when every value in
   `market_returns` is identical, with the same message the NaN branch gives today: it
   names `market_returns`, says its variance is zero, and gives the observation count.
   Test identity, not `np.var(...) == 0.0`: a float sum can leave a tiny non-zero
   variance for identical values.
2. Keep the NaN check after the call. It still catches the other degenerate inputs, such
   as a NaN observation.
3. Do not edit the test. It is the specification.

## Files in scope

- `analysis/capm.py`
- your journal entry

`P10a` and `P10c` run in parallel. Neither touches this file.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the failing test passes | 1 passed | `.venv/bin/python -m pytest -q tests/unit/test_capm.py` |
| 2 | the gate | 0 failed from `test_capm.py`; any other failure is `P10a`'s, by name | the test gate |
| 3 | the message is the repository's | it names `market_returns` and `variance` | a scratch call with `[0.01] * 12` |
| 4 | coverage of `capm.py` stays 100% | statements and branches | `--cov=analysis/capm.py --cov-branch`, `COVERAGE_FILE` under `/tmp/` |
| 5 | lint and types | no new error | the two gates |
