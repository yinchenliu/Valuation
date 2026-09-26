---
id: P4c-nan-stops
phase: 4 — the highest-cost silent defects
agent: programmer
depends_on: [P1b-arith, P4b-normalizer-verify]
---

# Stop before a NaN reaches the share price, and name the field when the projection list is empty

## Objective

**A NaN share price renders on a clean run, and the one correct guard in `analysis/`
cannot catch it.** That is backlog item 20, and it is the highest-cost defect now known
in this repository.

`scipy.stats.linregress` returns `nan` for an empty series and **raises nothing**. The
guard at `analysis/capm.py:42-43` catches an empty series only on the path that derives
the equity risk premium from history; supplying a premium — which both the web form and
the CLI allow — skips it. The NaN then reaches:

```python
analysis/dcf.py:24    if wacc <= terminal_growth_rate: raise ValueError(...)
```

**`nan <= 0.025` is `False`.** Every comparison against NaN is false, so the guard does
not fire and a complete `DCFResult` renders with `implied_share_price = nan`.

The unit also closes backlog item 14: `analysis/dcf.py:73` raises a bare `IndexError`
for an empty projection list, which stops but names nothing.

## What is already true — verify, do not redo

Measured at `e01dddf`. Each row was executed.

| Fact | Evidence |
|---|---|
| `linregress([], [])` → `slope=nan, rvalue=nan, stderr=nan`, raises nothing | orchestrator |
| `float("nan") <= 0.025` is `False`; so is `>` | orchestrator |
| the full chain ends in `implied_share_price = nan`, no exception | reviewer of `P1b-arith`, twelve call sites |
| **both entry points reach it** | `api/routes_valuation.py:167-172`, `cli.py:687-692` |
| `analysis/dcf.py:73` on an empty list → `IndexError: list index out of range` | tester of `P1-suite` |
| `analysis/capm.py` and `analysis/dcf.py` are at **100% of statements and branches** | the coverage gate |

**Both files are fully covered by tests you may not edit.** That is your safety net and
your constraint: if an existing assertion turns red, you changed behaviour someone
derived by hand.

## What to do

1. **Stop at the source, in `analysis/capm.py`.** `calculate_beta` must not return a
   value it cannot compute. Raise `ValueError` when the regression cannot produce a
   finite beta, naming **which input was inadequate** — an empty series, a length
   mismatch between the stock and market series, or a series too short to regress.

   Keep it a `ValueError`; typed exception classes are phase 5.

2. **Do not rely on a comparison to detect NaN.** `math.isnan` is the only reliable
   test. A guard written as `if beta > 0` or `if beta <= x` silently passes NaN, which
   is the whole reason this defect exists.

3. **Add a second stop where WACC is built**, so a NaN arriving from anywhere — not just
   from an empty series — cannot reach the discounting. A degenerate regression with
   zero variance in the market series also produces NaN, and step 1 does not cover that.

   Name the field in the message.

4. **Make `analysis/dcf.py:24`'s guard NaN-safe.** It is the last line of defence before
   a price is rendered, and today it is defeated by a value it was written to catch.
   State plainly in your entry whether you made it reject NaN or relied on steps 1 and
   3; either is defensible, but the reader must know which.

5. **Close item 14.** `analysis/dcf.py:73` reads `projected_fcffs[-1]`. Raise naming
   `projected_fcffs` instead of letting a bare `IndexError` escape. One line.

6. **Prove each stop by execution, not by reading.** Write a scratch script under
   `c:/tmp/` that drives the whole chain — empty market series with a supplied premium,
   through CAPM, WACC and `run_dcf` — and show it now raises with a named field where it
   previously returned a NaN price. Paste the before and after.

## Files in scope

- `analysis/capm.py`
- `analysis/dcf.py`
- `analysis/wacc.py` — **only** if step 3 belongs there rather than in `capm.py`. Say
  which you chose and why.

**Nothing else.**

## Out of scope

- **`tests/`** — your write guard denies it. 121 tests exist and a tester follows you.
- **`models/valuation.py`** — `WACCResult.wacc` and `DCFResult.implied_share_price` are
  properties on the path, and 40 assertions rest on them. If the fix needs one, **stop
  and say so**; that is an escalation.
- **Backlog item 9**, the unlabelled cost-of-debt fallback in `analysis/wacc.py`. You may
  touch that file; you do not fix that defect.
- **Item 2**, `analysis/dcf.py:80`. Its red test must stay red.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | an empty market series with a supplied premium **stops** | raises, message names the input | your scratch script; paste before and after |
| 2 | a NaN cannot reach `run_dcf` from any path | raises | same script, degenerate-variance case |
| 3 | an empty `projected_fcffs` stops and names the field | raises `ValueError` naming `projected_fcffs` | same |
| 4 | **no existing assertion changed meaning** | `1 failed, 120 passed` — the failure is `test_dcf_rule3_red.py` | `.venv/Scripts/python.exe -m pytest -q` |
| 5 | coverage of both files does not fall | 100% of statements | `COVERAGE_FILE=c:/tmp/.cov pytest -q --ignore-glob="*_rule3_red.py" --cov=analysis --cov-report=term` |
| 6 | lint unchanged | 5 errors, all `BLE001` | `.venv/Scripts/python.exe -m ruff check .` |
| 7 | types not worse | ≤ 14 errors, a strict subset | the mypy gate, set-diffed |
| 8 | the census did not rise | ≤ 116 | the grep in `docs/2-rules/rules.md` |

**Criterion 4 is the constraint.** Both files are at 100% coverage from assertions
derived by hand. If one turns red, you changed a number, and that is a blocker unless
you can show the old number was wrong.

**Criterion 5 may be hard to hold**, because a new `raise` is a new statement that no
test reaches. If coverage falls, say by how much and which line; the tester that follows
will close it. Do not write an unreachable guard to keep a percentage.

## Citations

- `docs/9-reference/refactor-backlog.md` items **20** and **14**.
- `docs/2-rules/rules.md` rule 3 — a missing input stops the run and names the field.
- `.agent/journal/2026-09-20T2145-tester-p1b-arith.md` — the unit that found item 20.
- `.agent/journal/2026-09-20T2215-code_reviewer-p1b-arith.md` — the twelve-site chain,
  confirmed end to end.

## Known open items

- `analysis/capm.py:14` imports from `ingestion/` — backlog item 17, a layering break in
  a file you are editing. **Not yours.** Say you saw it.
- `analysis/capm.py:45-47` silently switches from geometric to arithmetic annualisation
  when the compounded return is `<= 0`. Reported by `P1b-arith`, not on the backlog,
  **not in this unit.** Leave it and say you saw it.
- `analysis/capm.py:82-85` sets `r_squared` and `std_error` to `0.0` when a beta is
  supplied, so a reader cannot tell "no regression ran" from "it explained nothing".
  Same treatment: leave it, name it.

## Backlog items this unit is NOT fixing

- **Item 1** — the 116 zero-default sites.
- **Item 2** — `analysis/dcf.py:80`. Its red test stays red; criterion 4 depends on it.
- **Item 8** — the blanket catches. Do not add one, and do not wrap your raises.
- **Item 9** — the unlabelled cost of debt.
- **Item 17** — the layering break.
