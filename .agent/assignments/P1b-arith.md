---
id: P1b-arith
phase: 1b — close the coverage gap, part 1
agent: tester
depends_on: [P1-suite]
---

# First real tests for `analysis/fcff.py`, `analysis/wacc.py` and `analysis/capm.py`

## Objective

`analysis/dcf.py` is at 100% of statements. The other five modules are at **0%** — 170
statements that no test touches. A function no test calls cannot fail, so the suite
currently reads clean about code it has never executed.

This unit takes three of the five: `fcff.py` (19 statements), `wacc.py` (25) and
`capm.py` (30). They are the three whose arithmetic is checkable by hand or by a
closed-form identity, which is why they come before `normalizer.py` and `projector.py`.

When this unit is done, those three modules have independently-derived tests, every
stop path that exists is locked, and every stop path that **should** exist but does not
is reported with its `file:line`.

## What is already true — verify, do not redo

Measured by the orchestrator at `19f1767`, 2026-09-20.

| Fact | Command |
|---|---|
| `pytest -q` → `1 failed, 19 passed` | the one failure is `tests/unit/test_dcf_rule3_red.py`, red on purpose |
| `analysis/fcff.py`, `wacc.py`, `capm.py` are at 0% | `pytest -q --cov=analysis --cov-report=term` |
| `tests/` lints with exactly 1 error, a deferred `BLE001` | `ruff check tests --output-format concise` |
| no API key is set and no `.env` exists | `ls .env` |

**`1 failed` is the expected state.** It is `P1-suite`'s deliberate red test against
`analysis/dcf.py:80`. A second unexpected failure is a real regression.

## What to do

1. **Write one file per module**: `tests/unit/test_fcff.py`, `tests/unit/test_wacc.py`,
   `tests/unit/test_capm.py`. Build every fixture by hand inside the file. No network,
   no key, no PDF, no `.pkl`.

2. **Use the identities `docs/5-testing/strategy.md` section 1 already names.** They
   are the strongest tests available here because they hold whatever the inputs:

   - `WACCResult` with `debt_weight = 0` equals the cost of equity, whatever `Kd` and
     `t` are. Set an absurd `Kd` so the independence is visible.
   - `WACC` with `tax_rate = 0` equals the plain weighted average.
   - `calculate_beta` on a series regressed **on itself** gives `beta = 1.0` exactly,
     `r_squared = 1.0`, `std_error = 0.0`. This needs no market data and it is the
     cheapest real test of the regression.
   - `annualized_market_return` with one return `r` and `periods_per_year = 1` gives
     exactly `r`. With twelve monthly returns of `0.0` it gives exactly `0.0`.
   - `NOPAT` with `tax_rate = 0` equals `EBIT`.

3. **Pin the two sign conventions.** Both are places where a reversal still produces a
   plausible number.

   - `calculate_fcff_historical` applies `abs()` to interest expense and to CapEx
     (`analysis/fcff.py:47,49`). A filing that reports CapEx as `-1000` and one that
     reports it as `+1000` must give the **same** FCFF. Assert both.
   - `ProjectedFCFF.fcff` applies `abs()` to CapEx. Same test, on the projected side.

4. **Pin the relationship between the two FCFF methods.** The module docstring gives
   both formulas. Construct one year where `CFO = NOPAT + D&A - ΔNWC` exactly, and show
   `calculate_fcff_historical` and `calculate_fcff_projected` agree. That assertion is
   what tells a reader the two methods are the same measure, and it goes red if either
   drifts.

5. **Lock every stop that exists.** `analysis/capm.py:43` raises `ValueError` on empty
   market returns. Assert the type **and** that the message names the missing input.

6. **Report every stop that should exist and does not**, with its `file:line`. Do not
   assert the fallback. See "Known open items" for the five I already know about; find
   any others.

## Files in scope

- `tests/unit/test_fcff.py` (new)
- `tests/unit/test_wacc.py` (new)
- `tests/unit/test_capm.py` (new)
- `tests/unit/test_fcff_rule3_red.py`, `tests/unit/test_wacc_rule3_red.py`,
  `tests/unit/test_capm_rule3_red.py` — **only if** you write a red test, and only for
  a defect already on the backlog.

**Nothing else.** In particular, do **not** edit `tests/unit/__init__.py`,
`tests/unit/test_dcf.py`, `tests/unit/test_dcf_rule3_red.py`, or any of the nine
scripts. Unit `P1c-flow` is running in parallel and owns
`tests/unit/test_normalizer.py` and `tests/unit/test_projector.py`.

## Out of scope

- Every implementation file. You may not edit `analysis/`. If a test cannot pass
  without a code change, **that is your finding** — report it.
- `analysis/normalizer.py` and `analysis/projector.py`. `P1c-flow` owns them.
- Any root-level configuration file. Outside your write scope.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the suite runs with no unexpected failure | only `*_rule3_red.py` files fail | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` → 0 failed |
| 2 | `analysis/fcff.py` statement coverage | **100%** | `... -m pytest -q --ignore-glob="*_rule3_red.py" --cov=analysis --cov-report=term` |
| 3 | `analysis/wacc.py` statement coverage | **100%** | same command |
| 4 | `analysis/capm.py` statement coverage | ≥ 90%, and every uncovered line named in your entry | same command |
| 5 | every assertion's expected value is sourced in your entry | 1 row per assertion | the table in your entry |
| 6 | `tests/` still lints with exactly 1 error | 1, the deferred `BLE001` | `.venv/Scripts/python.exe -m ruff check tests --output-format concise` |
| 7 | no test needs a key, a PDF or the network | passes with both keys unset | criterion 1's command, with no `.env` present |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/5-testing/strategy.md` — section 1 (the three acceptable sources and the one
  forbidden one), section 2 (lock the stop, never assert a fallback), section 3 (no
  network, no keys), section 6 (this order).
- `docs/2-rules/rules.md` rule 3 (the absent case) and rule 6 (an assumption is
  labelled).
- `docs/4-conventions/units-and-signs.md` — **read before writing arithmetic.** Every
  money figure is in millions.
- `docs/3-architecture/valuation-math.md` — the formulas.
- `.agent/journal/2026-09-20T2010-tester-p1-suite.md` — the prior unit. Its
  "Expected values" table is the shape yours must take.

## Known open items

These five are already known. **Report each one; do not assert its fallback**, and do
not rediscover them as new.

1. **`analysis/wacc.py:41-43`** — when `total_debt > 0` and `interest_expense == 0`,
   returns `config.DEFAULT_COST_OF_DEBT` (4.0%) with nothing in the output saying so.
   Backlog item 9, rule 6. **Do not assert `== 0.04`.** The recorded fix changes the
   signature to return the value with a flag, so such an assertion would turn that fix
   red.

2. **`analysis/wacc.py:77-84`** — when `market_cap + total_debt == 0`, returns
   `equity_weight = 1.0, debt_weight = 0.0` instead of stopping. A company with no
   market cap and no debt is not a 100%-equity company; it is missing data. Rule 3.
   **Not on the backlog yet** — report it and I will record it.

3. **`analysis/fcff.py:44` and `analysis/wacc.py:71`** — the effective tax rate is
   silently clamped to `[0.0, 0.50]`. A filing reporting a 60% effective rate is read
   as 50%, with nothing saying so. Rule 6. **Not on the backlog yet** — report it.

4. **`analysis/capm.py:45-47`** — when the compounded gross return is `<= 0`, the
   function silently switches from geometric to **arithmetic** annualisation. That is a
   different formula, chosen at run time, with only a code comment saying so. Report
   it. You may test the branch; say in your entry that you are testing a fallback
   rather than the documented formula.

5. **`analysis/capm.py:82-85`** — when `beta_override` is supplied, `r_squared` and
   `std_error` are set to `0.0`. A reader cannot tell "no regression was run" from "the
   regression explained nothing". Rule 3 shape. Report it. **Do not assert
   `r_squared == 0.0` as though it were correct**; if you cover that branch, assert the
   beta passes through and say in your entry why you did not assert the diagnostics.

Also note, and do not report as new: **`analysis/capm.py:14` imports from
`ingestion/`** (backlog item 17). Your test will therefore import
`ingestion.price_fetcher.PriceData` to build a fixture. That is unavoidable today and
it is evidence for item 17, not a defect in your test.

## Backlog items this unit is NOT fixing

- **Item 1** — the 117 zero-default sites. Phase 6.
- **Item 9** — the unlabelled cost of debt. Phase 7. Reported, never asserted.
- **Item 17** — `analysis/capm.py:14` imports from `ingestion/`.
- **Item 2** — `analysis/dcf.py:80`. `P1-suite`'s red test already states it.

## On writing a red test

You may write one **only** for a defect already on the backlog, and only when the
correct behaviour is unambiguous. Put it in a file named `*_rule3_red.py` so the gate's
`--ignore-glob` covers it, give it a docstring saying which backlog item it states, and
**list every red test you wrote in your entry**. A red test that nobody knows about is
a broken gate.

If the correct behaviour is not obvious — as with the tax clamp, where the right bound
is a judgement — **report it and write no test.** That is an escalation, not a gap.
