---
agent: tester
assignment: P1b-arith
round: 1
status: complete
files_touched: [tests/unit/test_fcff.py, tests/unit/test_wacc.py, tests/unit/test_capm.py]
verdict: fail
---

# P1b-arith — `analysis/fcff.py`, `wacc.py` and `capm.py` go from 0% to 100%, and six places that should stop do not

> **Read the verdict line before anything else.** The `fail` is **not** a broken
> deliverable. **All seven done-criteria pass, measured.** 110 of 110 assertions matched
> an independently-derived expectation on the first execution, and all three modules are
> at **100% of statements and 100% of branches** from my own three files alone.
>
> The `fail` is a verdict about `analysis/`, which I may not edit.
> `.claude/agents/tester.md` is categorical: *"If a stop path cannot be reached because
> the code defaults instead of raising, that is a `fail`, not an untestable case."*
> There are **six** such places across the three modules. Five were named in the
> assignment's "Known open items" and I report them without asserting them. **The sixth
> is new and is the most serious thing in this entry:**
>
> **`analysis/capm.py:87` returns `beta = NaN` — it does not stop — when the market
> return series is empty and an ERP was supplied.** NaN then propagates through cost of
> equity, WACC, the terminal value guard (`nan <= g` is `False`, so it does not raise)
> and out to the share price. Measured, not read. See Finding 1.

## What I did

Wrote three new files — `tests/unit/test_fcff.py`, `tests/unit/test_wacc.py`,
`tests/unit/test_capm.py` — holding **37 test functions and 110 `assert` statements**,
plus 2 exception-type checks through `pytest.raises(ValueError)`. Every expected value
came from hand arithmetic written into the test, from a closed-form identity, or from a
named constant in `config.py`; **none came from running the code**. Every fixture is a
dataclass built inside the file: no key, no PDF, no network, no `.pkl`. The three
modules go from 0% to 100% of statements and 100% of branches. I touched no
implementation file and no test file belonging to `P1c-flow`.

Six places where a missing or contradictory input produces a number instead of a stop
are **executed** (so the branch is covered) and **deliberately not asserted**, each with
a comment in the test saying why. Asserting any of them would make the defect permanent
and turn its fix red — `docs/5-testing/strategy.md` section 2.

## Done-criteria

Measured on the working tree at `19f1767` + this unit's three new files. `P1c-flow` had
not yet written `tests/unit/test_normalizer.py`, `test_normalizer_rule3_red.py` or
`test_projector.py` when I took the figures below, so each one is earned by this unit's
tests and nothing else.

**`P1c-flow` landed its three files while I was writing this entry.** I re-ran every
command afterwards; the re-measured combined figures are in the row for criterion 1 and
in Finding 7, each marked as combined. Nothing in criteria 2-7 moved.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | suite runs with no unexpected failure | **pass** | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` → `56 passed in 3.13s`, **0 failed**. Full form `pytest -q` → `1 failed, 56 passed`; the failure **set** is `{tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent}` — one element, `P1-suite`'s deliberate red, unchanged. Baseline before my files: `1 failed, 19 passed`. **Re-run after `P1c-flow` landed** (combined tree, its files included): same command → `90 passed`, 0 failed; my three files alone → `37 passed` |
| 2 | `analysis/fcff.py` statement coverage = 100% | **pass** | `... --ignore-glob="*_rule3_red.py" --cov=analysis --cov-report=term` → `analysis\fcff.py  19  0  100%` |
| 3 | `analysis/wacc.py` statement coverage = 100% | **pass** | same command → `analysis\wacc.py  25  0  100%` |
| 4 | `analysis/capm.py` ≥ 90%, uncovered lines named | **pass — 100%** | same command → `analysis\capm.py  30  0  100%`. **No uncovered line to name.** See the caveat under Measurements about what 100% does and does not mean here |
| 5 | every assertion's expected value is sourced | **pass** | the "Expected values" table below: 37 rows, one per test function, reconciling to 110 `assert` statements + 2 `pytest.raises` type checks |
| 6 | `tests/` lints with exactly 1 error | **pass** | `.venv/Scripts/python.exe -m ruff check tests --output-format concise` → `tests\test_e2e_all_googl.py:106:16: BLE001` / `Found 1 error.` — the deferred one, unchanged. Repo-wide `ruff check .` → `5 errors`, all `BLE001`, identical to `STATUS.md` section 1 |
| 7 | no key, no PDF, no network | **pass** | `env -u GEMINI_API_KEY -u ANTHROPIC_API_KEY .venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` → `56 passed in 3.17s`. `ls .env` → no such file. Both keys were already `None` in the environment |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Executed all six defaulting branches but asserted **nothing** about the substituted value | `docs/5-testing/strategy.md` §2, assignment "Known open items" 1-5 | The alternatives were both worse. Skipping the branch leaves it at 0% and reads as clean. Asserting the value (`cost_of_debt == 0.04`, `equity_weight == 1.0`, `r_squared == 0.0`) would make the defect permanent. So each such test asserts only figures that are independent of the substitution — weights, pass-throughs — and carries a docstring saying which line it is stepping over and why |
| Did **not** assert `!= 0.04` or `is not None` on the substituted cost of debt either | Backlog item 9's recorded fix changes the signature to return the value with a flag | A `!= 0.0` assertion would keep passing against `(0.04, True)` and so would be a test that cannot fail. That is worse than no test, because it reads as coverage |
| Wrote **no red test** | The assignment permits one only for a defect already on the backlog. The three new rule-3 holes I found (Findings 1-3) are not on it | Reporting them is the prescribed route; the orchestrator records them and a later unit writes the red test with the correct behaviour agreed |
| Wrote **no test** for the `[0.0, 0.50]` tax clamp | The assignment: *"If the correct behaviour is not obvious — as with the tax clamp, where the right bound is a judgement — report it and write no test"* | Measured it instead and reported it (Finding 4). Any assertion would freeze a bound nobody has chosen |
| Solved one regression **by hand** with an imperfect fit (`test_beta_on_an_imperfect_fit_solved_by_hand`) rather than relying only on the self-regression identity | An exact-multiple fixture cannot distinguish a correct slope from a mis-weighted estimator: every reasonable estimator agrees when the fit is perfect | β = Sxy/Sxx = 1.6, R² = 16/17 and SE(β) = √(4/75) are all solved in the docstring from the OLS normal equations. This is the only assertion in the file that would catch a wrong weighting, and it needed the arithmetic done in full first |
| Used an **empty** market series in the ERP-supplied tests | It makes "the S&P 500 history is not consulted" falsifiable: a run that computed the ERP from history would raise the `ValueError` those same tests lock two rows above | Supplying a valid series there would have proved nothing about the short-circuit |
| Asserted `risk_free_rate == config.DEFAULT_RISK_FREE_RATE` by **reference to the constant**, never the literal `0.04` | Rule 6: the assumption carries a name, a default on the record (`config.py:20`), and is visible in the output. The expected side is `config.py`, an independent record, not a run | A literal `0.04` would be a photograph and would also go red on a deliberate change to the default. Referencing the constant states the requirement — *the documented default is the one the run uses* — and survives a change of value |
| Used `0.03` as the risk-free rate in the end-to-end CAPM test | `config.DEFAULT_RISK_FREE_RATE` is `0.04`. A test that passed `0.04` explicitly could not tell "the supplied rate was used" from "the supplied rate was ignored and the default taken" | With `0.03` the two give 0.37 and 0.36. The assertion is falsifiable |
| Pinned the `CAPMResult` cost-of-equity fixture in `test_wacc.py` (1 assertion) | So the WACC arithmetic is about `analysis/wacc.py` and not about how `CAPMResult` computes its own property | Same pattern `tests/unit/test_dcf.py` uses for its two fixture builders. It is counted separately below |
| Put large, "unrealistic" magnitudes in some fixtures — a 90% cost of debt, a +50% periodic return | Round numbers are the only kind anyone can independently check, and an absurd `Kd` is what makes the `D/V = 0` independence *visible* | Realistic-looking inputs would have forced me to paste what the code said, which is the one thing forbidden |

No implementation file was touched. `git status --short` shows my working-tree additions
as exactly `tests/unit/test_fcff.py`, `tests/unit/test_wacc.py`, `tests/unit/test_capm.py`
and this entry.

## Rule 3 — what stops, and what does not

One row per value the three modules read. **Six "defaults to" rows. All six are findings.**

| Value read | If it were missing | Evidence |
|---|---|---|
| `price_data.market_returns` in `annualized_market_return` | **stops and names `market return`** — `"No market returns available to estimate market return"` | `analysis/capm.py:42-43`. **Locked** on type (`ValueError`) and on the message naming the field, by `test_annualized_market_return_stops_when_there_are_no_market_returns` |
| the same, reached through `run_capm` with no ERP supplied | **stops**, and the message survives the composition | **Locked** by `test_run_capm_propagates_the_missing_market_returns_stop` |
| the same, when an **ERP is supplied** and no `beta_override` | **does not stop — returns `beta = NaN`** | `analysis/capm.py:87` → `scipy.stats.linregress` on empty arrays. **Could not be locked.** Measured: `run_capm(empty, risk_free_rate=0.03, equity_risk_premium=0.05).beta` → `nan`, with a `SmallSampleWarning` on stderr and no exception. **Finding 1 — new** |
| `interest_expense` when `total_debt > 0` in `calculate_cost_of_debt` | **defaults to `config.DEFAULT_COST_OF_DEBT`** (4.0%), unlabelled in the output | `analysis/wacc.py:41-43`. Branch executed by `test_weights_are_still_the_reported_ones_when_interest_is_not_reported`; **nothing about the rate is asserted.** Backlog item 9, rule 6 |
| `market_cap` and `total_debt` when both are zero | **defaults to `equity_weight = 1.0, debt_weight = 0.0`** instead of stopping | `analysis/wacc.py:77-84`. Branch executed by `test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`; **only the pass-through cost of equity is asserted.** Assignment known item 2 — **not yet on the backlog** |
| `total_debt` when it is zero but interest expense is **not** | **defaults to `0.0`** with no complaint about the contradiction | `analysis/wacc.py:37-38`. Measured: `calculate_cost_of_debt(IncomeStatement(interest_expense=20.0), BalanceSheet())` → `0.0`. Executed by `test_a_debt_free_company_prices_at_its_cost_of_equity`, which asserts the WACC identity and says nothing about the rate. **Finding 2 — new** |
| every money figure `calculate_fcff_historical` reads | **defaults to `0.0`** — the function has **no stop of any kind** | `analysis/fcff.py` holds zero `raise` statements. Measured: `calculate_fcff_historical(IncomeStatement(year=2025), CashFlowStatement(year=2025)).fcff` → `0.0`, a complete `HistoricalFCFF` from an extraction that returned nothing. The zeros come from `models/financial_statements.py:47-104` and `:217-234` (backlog item 1). **Not locked, and deliberately not asserted.** Finding 3 |
| `income_statement.ebt` behind `effective_tax_rate` | **defaults to `0.0`** when `ebt == 0` — a conditional zero | `models/financial_statements.py:101`. Reached from `fcff.py:43` and `wacc.py:69`. Backlog item 1. Not locked, not asserted |
| an effective tax rate above 50%, or below 0% | **silently clamped** to `[0.0, 0.50]` | `analysis/fcff.py:44`, `analysis/wacc.py:71`. Measured: a filing reporting 60% (tax 60 on EBT 100) is read as `0.5` in both. Rule 6. **Finding 4 — assignment known item 3, not yet on the backlog.** No test, by the assignment's instruction |
| `r_squared` / `std_error` when `beta_override` is supplied | **set to `0.0`** — "no regression was run" is indistinguishable from "the regression explained nothing" | `analysis/capm.py:82-85`. Branch executed by four tests; **only the beta pass-through is asserted.** Assignment known item 5 |
| `balance_sheet` itself, if `None` is passed to `calculate_wacc` | **stops, but does not name the field** — `AttributeError: 'NoneType' object has no attribute 'total_debt'` | `analysis/wacc.py:74`. Measured. This is the live defect `STATUS.md` §1 already records from `api/routes_valuation.py:190`; I confirmed it by running it. Not locked — writing it green would photograph a bare `AttributeError` that names nothing |
| stock and market return series of **different lengths** | **stops, but does not name the field** — `ValueError: Array shapes are incompatible for broadcasting.` | `analysis/capm.py:32`, from scipy. Measured. Not locked, same reason. Finding 5 |

## Measurements

### The test gate, as failure sets

| | Before (this tree, before my files) | After |
|---|---|---|
| collected | 20 | **57** |
| run | `1 failed, 19 passed in 0.23s` | `1 failed, 56 passed in 3.76s` |
| failure set | `{test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent}` | **identical — one element, the same deliberate red** |
| phase-1 gate form | `19 passed` | **`56 passed`, 0 failed** |

Re-run on the combined tree after `P1c-flow` landed: `90 passed`, 0 failed, and my three
files in isolation still `37 passed`. **No test of mine depends on that unit's files, and
none of its tests changed any figure I report.**

The suite time rose from 0.23 s to 3.76 s. All of it is import cost: `tests/unit/test_capm.py`
imports `ingestion.price_fetcher`, which imports `yfinance`, `pandas` and `scipy`. **No
request is made** — the first cold run took 19.9 s and every run after 3.1-4.2 s, which is
import caching, not I/O. That import exists only because `analysis/capm.py:14` imports
`PriceData` from `ingestion/` (backlog item 17); when item 17 lands, this cost goes with it.

### Coverage — measured, from this unit's three files **only**

```
$ .venv/Scripts/python.exe -m pytest -q tests/unit/test_fcff.py tests/unit/test_wacc.py \
      tests/unit/test_capm.py --cov=analysis.fcff --cov=analysis.wacc --cov=analysis.capm \
      --cov-branch --cov-report=term-missing

Name               Stmts   Miss Branch BrPart  Cover   Missing
analysis\capm.py      30      0      8      0   100%
analysis\fcff.py      19      0      0      0   100%
analysis\wacc.py      25      0      8      0   100%
TOTAL                 74      0     16      0   100%
37 passed in 3.66s
```

Re-confirmed after `P1c-flow` landed, with an isolated data file
(`COVERAGE_FILE=c:/tmp/.coverage_p1b`): identical, `37 passed`. **The isolation is
needed, and it is worth knowing:** two units measuring coverage in the same working tree
share the repository-root `.coverage`, and a `--cov-branch` run against a statement-only
file aborts with
`coverage.exceptions.DataError: Can't combine branch coverage data with statement data`
as a pytest `INTERNALERROR`. The tests themselves pass; only the report dies. Anyone
re-running these figures alongside a parallel unit should set `COVERAGE_FILE` or delete
`.coverage` first.

**The narrow figure above is the one I report**, and it is deliberately the narrow one. The assignment
warned that `analysis/projector.py` imports `calculate_fcff_projected`, so once
`P1c-flow` lands, a whole-suite `--cov=analysis` figure for `fcff.py` will include
statements its tests executed rather than mine. Selecting only my three files removes
that ambiguity: **all 74 statements and all 16 branches above are executed by this unit's
own tests.**

The whole-suite figure, for the orchestrator's `STATUS.md` update, measured at the same
tree with `--ignore-glob="*_rule3_red.py" --cov=analysis --cov=models`:

```
analysis\capm.py                    30      0   100%
analysis\dcf.py                     24      0   100%
analysis\fcff.py                    19      0   100%
analysis\normalizer.py              28     28     0%   7-100
analysis\projector.py               68     68     0%   6-150
analysis\wacc.py                    25      0   100%
models\financial_statements.py     151     18    88%
models\valuation.py                 95      3    97%
TOTAL                              440    117    73%
```

`analysis/` goes from **1 of 6 modules covered (12% of statements)** to **4 of 6 (98
of 194 statements, 51%)**. `normalizer.py` and `projector.py` — 96 statements — are
`P1c-flow`'s, and are still at 0% as I measured.

**The caveat a reader must not miss, and it is the same one `P1-suite` recorded.**
coverage.py does not count a conditional *expression* as a branch. Three of the four
conditional expressions in these modules are therefore invisible to the branch counter:

- `analysis/fcff.py:43` — `tax_rate_override if ... is not None else ...`. `fcff.py`
  reports **0 branches**, which is why its 100% branch figure must not be read as "every
  path is checked". I exercised both sides explicitly anyway (three override tests and
  two derived-rate tests).
- `analysis/wacc.py:69` — the same shape for the tax rate. Both sides exercised.
- `models/financial_statements.py:101` — `... if self.ebt else 0.0`, the conditional zero.
  Executed via the derived-rate path; its zero branch is **not** exercised and is not asserted.

`100%` here means every statement and every `if` ran. It does not mean every path is
blessed — six of them are executed precisely so that they are covered without being
asserted.

### Lint

`.venv/Scripts/python.exe -m ruff check tests --output-format concise`

| | Before | After |
|---|---|---|
| `BLE001` (deferred, backlog item 8) | 1 | **1 — unchanged** |
| anything else in `tests/` | 0 | **0** |
| **total** | **1** | **1** |

My three files add zero lint errors. Repo-wide `ruff check .` → `5 errors`, all `BLE001`,
the exact set `STATUS.md` §1 records.

### Absent-input behaviour, measured for the findings

Run from a scratch script at `c:/tmp/p1b_probe.py` (outside the repository). **These are
measurements that produced findings. Not one of them became an assertion.**

```
run_capm empty returns, erp supplied, NO beta override : returned np.float64(nan)
fcff_historical on wholly empty statements             : returned 0.0
calculate_wacc with balance_sheet=None                 : AttributeError: 'NoneType' object has no attribute 'total_debt'
cost_of_debt: interest 20 but total_debt 0             : returned 0.0
wacc tax clamp: effective rate 0.60                    : returned 0.5
fcff tax clamp: override 0.60                          : returned 0.5
run_capm with mismatched return lengths                : ValueError: Array shapes are incompatible for broadcasting.
```

## Expected values — testers only

One row per test function, with the number of `assert` statements it holds, so the counts
reconcile: **47 + 31 + 32 = 110**. **None came from running the code.** All 110 matched on
the first execution; no expectation was revised after seeing output.

### `tests/unit/test_fcff.py` — 11 functions, 47 assertions

The shared fixture, derived before anything ran:
`EBIT = 1000 − (600 + 50 + 50) = 300`; `EBT = 300 − 100 = 200`; `t = 40/200 = 0.20`;
`CFO = 160 + 50 + 30 − 40 = 200`; `CapEx = |−70| = 70`.

| Test | n | Expected | Where the expected value came from |
|---|---|---|---|
| `test_historical_fcff_worked_example` | 9 | year 2025, revenue 1000, EBIT 300, CFO 200, t 0.20, interest 100, after-tax interest 80, CapEx 70, **FCFF 210** | hand arithmetic: `FCFF = CFO + I(1−t) − CapEx = 200 + 100×0.80 − 70 = 210`, all intermediate steps written into the docstring |
| `test_historical_fcff_is_the_same_for_either_capex_sign` | 4 | CapEx `70` and FCFF `210` for CapEx reported as −70 **and** as +70 | the `abs()` convention at `analysis/fcff.py:49`, stated in `docs/4-conventions/units-and-signs.md` §3. With the sign carried through, +70 would give `200 + 80 + 70 = 350` |
| `test_historical_fcff_is_the_same_for_either_interest_sign` | 4 | interest `100` and FCFF `210` for interest reported as +100 **and** as −100 | the same `abs()` convention at `fcff.py:47`. The tax rate is supplied so the two cases differ in exactly one thing — without it, flipping the sign also moves EBT to 400 and the rate to 0.10 |
| `test_historical_fcff_with_a_zero_tax_override_adds_back_gross_interest` | 3 | t `0.0`, after-tax interest `100`, FCFF `230` | closed-form identity: at `t = 0` the shield vanishes and the whole interest expense is added back. `200 + 100 − 70 = 230`. The statement's own rate is 0.20, so ignoring the override would give 210 |
| `test_historical_fcff_override_replaces_the_effective_rate` | 3 | t `0.40`, after-tax interest `60`, FCFF `190` | hand arithmetic: `100 × 0.60 = 60`; `200 + 60 − 70 = 190` |
| `test_projected_fcff_worked_example` | 8 | EBIT 400, NOPAT 300, D&A 80, CapEx 120, ΔNWC 20, **FCFF 240**, year, revenue | hand arithmetic: `2000×0.20 = 400`; `400×0.75 = 300`; `300 + 80 − 120 − 20 = 240` |
| `test_projected_nopat_at_a_zero_tax_rate_equals_ebit` | 3 | EBIT `200`, NOPAT `== EBIT`, NOPAT `200` | closed-form identity named in `docs/5-testing/strategy.md` §1: `NOPAT = EBIT(1−t)`, so at `t = 0` it is EBIT |
| `test_projected_fcff_is_the_same_for_either_capex_sign` | 4 | CapEx `+120` / `−120` as supplied, FCFF `240` both ways | the `abs()` at `models/valuation.py:100`. With the sign carried through the −0.06 case would give 480 |
| `test_projected_fcff_subtracts_a_growing_working_capital` | 3 | `260` at ΔNWC 0, `240` at ΔNWC 20, and `240 < 260` | hand arithmetic + the sign convention in `units-and-signs.md` §3. A reversed sign gives 280, which is *higher* than the no-growth case and would still look plausible |
| `test_the_two_fcff_methods_agree_when_the_definitions_line_up` | 3 | historical `185`, projected `185`, and equal | hand arithmetic on **both** sides independently: `CFO 255 + 0 − 70 = 185` and `NOPAT 225 + 50 − 70 − 20 = 185`. The year is constructed so the two definitional gaps (`valuation-math.md` §4) are both closed: CFO = NOPAT + D&A − ΔNWC, and interest = 0 |
| `test_stock_based_compensation_is_the_gap_between_the_two_methods` | 3 | CFO `285`, FCFF `215`, gap `30` | hand arithmetic: adding 30 of SBC to the same aligned year raises CFO to `225+50+30−20 = 285` and FCFF to `285 − 70 = 215`, exactly 30 above the EBIT-based 185. The SBC divergence `valuation-math.md` §4 records, made a number |

### `tests/unit/test_wacc.py` — 12 functions, 31 assertions

Fixture, derived first: `Re = 0.04 + 1.2×0.05 = 0.10`; `EBIT = 1000 − 680 = 320`;
`EBT = 320 − 20 = 300`; `t = 75/300 = 0.25`; `total_debt = 100 + 50 + 250 = 400`.

| Test | n | Expected | Where the expected value came from |
|---|---|---|---|
| `test_the_capm_fixture_supplies_a_ten_percent_cost_of_equity` | 1 | `0.10` | hand arithmetic on the CAPM formula: `Rf + β×ERP = 0.04 + 1.2×0.05`. **This one assertion tests `models/valuation.py`, not `analysis/wacc.py`** — it pins the fixture so the rest of the file is about WACC |
| `test_cost_of_debt_is_interest_over_total_debt` | 1 | `0.05` | hand arithmetic: `20 / (100+50+250) = 20/400`. The 500 of payables and 9999 of other non-current liabilities are decoys: counting payables gives 0.0222, counting everything 0.0018 |
| `test_cost_of_debt_is_the_same_for_either_interest_sign` | 2 | `0.05` for +20 and for −20 | the `abs()` at `wacc.py:40`. Carrying the sign gives −0.05 — a company paid to borrow |
| `test_cost_of_debt_override_replaces_the_derived_rate` | 1 | `0.065` | pass-through of the argument supplied. The same fixtures imply 0.05, so ignoring the override is falsifiable |
| `test_wacc_worked_example` | 6 | Re 0.10, Rd 0.05, t 0.25, E/V 0.60, D/V 0.40, **WACC 0.075** | hand arithmetic: `E=600, D=400, V=1000`; `0.60×0.10 + 0.40×0.05×0.75 = 0.06 + 0.015` |
| `test_the_weights_sum_to_one` | 3 | sum `1.0`, `900/1300`, `400/1300` | closed-form identity `E/V + D/V = V/V = 1`, checked at a lopsided split sharing no figure with the worked example |
| `test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt` | 4 | E/V 1.0, D/V 0.0, WACC `0.10` (twice, once against the named constant) | closed-form identity from `docs/5-testing/strategy.md` §1: the debt term vanishes at `D/V = 0`. `Kd` is set to an absurd **0.90** and `t` to 0.40 so the independence is visible — if the debt term reached the answer, 0.10 could not survive it. Market cap is 1000, so these weights are the **computed** ones, not the `wacc.py:77-84` fallback |
| `test_a_debt_free_company_prices_at_its_cost_of_equity` | 2 | D/V `0.0`, WACC `0.10` | the same identity without the override, so the `wacc.py:36-38` derivation path runs. **`result.cost_of_debt` is deliberately not asserted** — that is the `return 0.0` at line 38 |
| `test_wacc_at_a_zero_tax_rate_is_the_plain_weighted_average` | 4 | t 0.0, E/V 0.75, D/V 0.25, WACC `0.095` | closed-form identity from `strategy.md` §1 plus hand arithmetic: `0.75×0.10 + 0.25×0.08 = 0.075 + 0.02`. At the fixture's own 25% rate the same inputs give 0.090, so this is not rate-independent — it tells the two apart |
| `test_the_tax_shield_only_reduces_the_debt_term` | 2 | WACC `0.090`, difference `0.005` | closed-form identity derived from the formula: the equity term carries no tax factor, so the gap between the untaxed and taxed WACC is exactly `(D/V)×Rd×t = 0.25×0.08×0.25 = 0.005` |
| `test_weights_are_still_the_reported_ones_when_interest_is_not_reported` | 4 | Re 0.10, t 0.25, E/V 0.75, D/V 0.25 | hand arithmetic on figures **independent of the substitution**. `wacc.py:41-43` runs here and substitutes `DEFAULT_COST_OF_DEBT`; **no assertion touches the rate or the resulting WACC.** Backlog item 9 |
| `test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt` | 1 | Re `0.10` | pass-through of the CAPM argument, the one figure independent of the `wacc.py:77-84` defect. **The weights are not asserted.** Known item 2 |

### `tests/unit/test_capm.py` — 14 functions, 32 assertions + 2 `pytest.raises` type checks

| Test | n | Expected | Where the expected value came from |
|---|---|---|---|
| `test_beta_of_a_series_regressed_on_itself_is_exactly_one` | 3 | β `1.0`, R² `1.0`, SE `0.0` | closed-form identity named in `strategy.md` §1: regressing a series on itself is the line `y = x`. Perfect fit ⇒ R² = 1 and no residual ⇒ SE = 0. Needs no market data |
| `test_beta_recovers_an_exact_multiple_and_discards_the_intercept` | 3 | β `2.0`, R² `1.0`, SE `0.0` | closed-form identity: `y = 2x + 0.01` is exactly linear with slope 2, whatever the constant. The 0.01 is Jensen's alpha, which `calculate_beta` discards — a function returning the intercept in the slope's place would give 0.01 |
| `test_beta_on_an_imperfect_fit_solved_by_hand` | 3 | β `1.6`, R² `16/17`, SE `√(4/75)` | **hand arithmetic, the OLS normal equations solved in full in the docstring**: `Sxy = 0.0016`, `Sxx = 0.001`, `Syy = 0.00272`; `β = Sxy/Sxx = 1.6`; `R² = Sxy²/(Sxx·Syy) = 256/272 = 16/17`; `SSE = Syy − β²Sxx = 0.00016`, `SE(β) = √(SSE/((n−2)Sxx)) = √(4/75)`. The only assertion here that would catch a mis-weighted estimator |
| `test_one_return_with_one_period_per_year_annualizes_to_itself` | 1 | `0.25` | closed-form identity named in the assignment: `n = 1`, `ppy = 1` ⇒ exponent 1 ⇒ `(1+r) − 1 = r` |
| `test_twelve_monthly_zero_returns_annualize_to_zero` | 1 | `0.0` | closed-form identity named in the assignment: `prod(1+0) = 1`, `1^(12/12) − 1 = 0` |
| `test_a_constant_annual_return_annualizes_to_itself_whatever_the_count` | 1 | `0.25` | closed-form identity derived here: for constant `r`, `prod(1+r) = (1+r)^n`, so the result is `(1+r)^ppy − 1` — a function of `ppy` only, not of `n`. At `ppy = 1` that is `r`, for four periods as for one |
| `test_compounding_across_a_half_year_of_periods` | 1 | `0.20` | hand arithmetic: `1.5×0.8×1.5×0.8 = 1.44`; exponent `2/4 = 0.5`; `1.44^0.5 − 1 = 0.2`. The arithmetic mean of the same series annualizes to 0.30, so this tells the geometric formula from an arithmetic one |
| `test_annualized_market_return_stops_when_there_are_no_market_returns` | 1 + type | `ValueError`, message names **`market return`** | rule 3 (`docs/2-rules/rules.md`): a missing input stops and names the field. The requirement, not the code's format string |
| `test_run_capm_propagates_the_missing_market_returns_stop` | 1 + type | the same stop through `run_capm` | the same requirement: the stop must survive the composition, which is where the pipeline actually enters |
| `test_arithmetic_fallback_when_compounding_wipes_out` | 1 | `−0.8` | hand arithmetic **of the fallback formula, not the documented one**: `prod(1+r) = 0×1.2 = 0 ≤ 0`, so `mean(−1.0, 0.2) × 2 = −0.4 × 2`. Flagged in the test docstring and here: this is `capm.py:45-47`, a second formula chosen at run time. `valuation-math.md` §5 calls it a numerical guard for an impossible input rather than a rule 3 default, which is the only reason it is asserted at all |
| `test_run_capm_end_to_end_with_the_erp_derived_from_history` | 6 | β 2.0, R² 1.0, SE 0.0, Rf 0.03, ERP `0.17`, Ke `0.37` | hand arithmetic across every step: market return `1.44^0.5 − 1 = 0.20`; `ERP = 0.20 − 0.03`; `Ke = 0.03 + 2.0×0.17 = 0.37`. Rf is 0.03 on purpose — with 0.04 (the config default) a run that ignored the supplied rate would pass |
| `test_a_supplied_equity_risk_premium_is_used_as_given` | 4 | β `1.5`, Rf 0.05, ERP 0.06, Ke `0.14` | hand arithmetic: `0.05 + 1.5×0.06 = 0.14`. The market series is **empty**, so a run that computed the ERP from history would raise instead. **R² and SE are not asserted** — `capm.py:84-85` zeroes them, known item 5 |
| `test_cost_of_equity_is_linear_in_beta` | 4 | `0.11`, `0.17`, difference `0.06`, and `0.05` at β = 0 | closed-form identity: `Ke = Rf + β·ERP` is affine in β, so doubling β moves Ke by exactly one ERP, and β = 0 gives Rf itself — an asset with no market exposure earns the risk-free rate |
| `test_the_risk_free_rate_defaults_to_the_named_constant` | 2 | `config.DEFAULT_RISK_FREE_RATE`, and `config.DEFAULT_RISK_FREE_RATE + 0.06` | rule 6 plus `config.py:20`, the recorded default — **referenced as the constant, never as the literal `0.04`**. The requirement is that the documented default is the one the run uses and that it reaches the output. Not a rule 3 fallback: the risk-free rate is never extracted from a filing, so no measurement is being papered over |

### Two counts, with their units

- **Accuracy: 110 of 110 `assert` statements** across the three files match their
  independently-derived expectation, on the first execution, with no expectation revised
  after seeing output. Plus **2 of 2 exception-type checks** (`pytest.raises(ValueError)`).
  Of the 110, **109 execute the module under test**; **1** pins the
  `models/valuation.py` `CAPMResult.cost_of_equity` property the `test_wacc.py` fixtures
  depend on.
- **Coverage**, measured from this unit's three files alone:
  - **functions: 7 of 7.** `fcff.py` 2 of 2 (`calculate_fcff_historical`,
    `calculate_fcff_projected`); `wacc.py` 2 of 2 (`calculate_cost_of_debt`,
    `calculate_wacc`); `capm.py` 3 of 3 (`calculate_beta`,
    `annualized_market_return`, `run_capm`).
  - **statements: 74 of 74** — `fcff.py` 19/19, `wacc.py` 25/25, `capm.py` 30/30. 100%.
  - **branches: 16 of 16** — `wacc.py` 8, `capm.py` 8, `fcff.py` 0. 100%, **and see the
    caveat above**: three conditional *expressions* are not counted as branches by
    coverage.py, and **six covered branches are deliberately not asserted**.
  - **across `analysis/`: 4 of 6 modules** now have tests — 98 of 194 statements, 51%,
    up from 1 of 6 and 12%. `normalizer.py` and `projector.py` (96 statements) belong to
    `P1c-flow` and were at 0% when I measured.

## What I did not do

- **Wrote no red test.** The three new rule-3 holes (Findings 1-3) are not on the backlog,
  and the assignment permits a red test only for a defect already recorded. Reporting is
  the prescribed route.
- **Wrote no test for the tax clamp**, by the assignment's explicit instruction. Measured
  it and reported it (Finding 4).
- **Asserted nothing about six substituted values**: the default cost of debt, the
  all-equity weights, the zero cost of debt at zero total debt, the zeroed regression
  diagnostics, the all-zero `HistoricalFCFF`, and the clamped tax rate. Each branch is
  executed and each test says in its docstring which line it is stepping over.
- **Did not test `analysis/normalizer.py` or `analysis/projector.py`.** `P1c-flow` owns
  them, and I wrote and read nothing under `tests/unit/test_normalizer.py` or
  `tests/unit/test_projector.py`.
- **Did not touch `tests/unit/test_dcf.py`, `test_dcf_rule3_red.py`, `tests/unit/__init__.py`
  or any of the nine scripts.**
- **Did not assert `HistoricalFCFF.operating_margin` or `fcff_margin`.** Both are
  `x / revenue if revenue else 0.0` conditional zeros (`models/valuation.py:69,73`) —
  backlog item 1, and the only interesting case is the one I must not bless.

## Findings for the orchestrator

### 1. `analysis/capm.py:87` returns `beta = NaN` instead of stopping · **new, and the worst of these**

**Evidence, measured:** `run_capm(price_data_with_empty_returns, risk_free_rate=0.03,
equity_risk_premium=0.05).beta` → `np.float64(nan)`. `scipy.stats.linregress` emits a
`SmallSampleWarning` on stderr and returns NaN for every statistic rather than raising.

**Why it matters, and why it is worse than it looks.** The existing guard at
`capm.py:42-43` only fires on the path where the ERP is derived from history. Supplying
an ERP — which the web form and the CLI both allow — bypasses it entirely, and then an
empty or one-element return series produces a NaN beta. NaN then propagates:
`cost_of_equity = Rf + nan×ERP` → NaN → WACC → NaN. It is **not** caught by the one guard
that exists downstream: `analysis/dcf.py:24` tests `if wacc <= terminal_growth_rate`, and
`nan <= 0.025` is `False`, so the DCF runs to completion and the user is shown a NaN
share price with no error anywhere.

**What would fix it:** `calculate_beta` validates its inputs before calling `linregress` —
at minimum a non-empty series of at least 3 points, with a raise naming
`stock_returns` / `market_returns`. One function, two lines, and a green test can then be
written. Needs an assignment.

### 2. `analysis/wacc.py:37-38` returns a 0% cost of debt for a self-contradictory filing · new

**Evidence, measured:** `calculate_cost_of_debt(IncomeStatement(interest_expense=20.0),
BalanceSheet())` → `0.0`. A filing that reports interest paid but no debt balance is
internally inconsistent — almost certainly a failed balance-sheet extraction — and the
function answers "0%" without comment. It is benign inside `calculate_wacc`, where the
debt weight is also zero, but `calculate_cost_of_debt` is a public function of the module
and nothing stops a future caller reading that 0.0 as a measurement. Rule 3 shape. Low
cost today, and the fix is the same shape as item 9's.

### 3. `analysis/fcff.py` holds no stop of any kind · new, and it is backlog item 1's sharp end

**Evidence, measured:** `calculate_fcff_historical(IncomeStatement(year=2025),
CashFlowStatement(year=2025))` returns a complete, well-formed `HistoricalFCFF` with
`fcff = 0.0` from an extraction that returned nothing at all. There is no `raise` in the
file. This is the same mechanism as `STATUS.md` standing trap 2, reached one module
earlier than `dcf.py:80`, and it is why "the valuation ran" cannot be evidence of
anything. It is covered by backlog item 1 in aggregate; I am naming it because item 1's
census counts *sites*, and this is the specific composition — every input to a headline
figure defaulting together — that produces a clean run on no data.

### 4. The `[0.0, 0.50]` tax clamp is silent, in two places · assignment known item 3, **not yet on the backlog**

**Evidence, measured:** a filing reporting a 60% effective rate (tax 60 on EBT 100) is
read as `0.5` by both `analysis/fcff.py:44` and `analysis/wacc.py:71`, with nothing in
`HistoricalFCFF` or `WACCResult` recording that a clamp fired. A 60% effective rate is
unusual but real — a bad year with non-deductible items, or a repatriation charge.
Rule 6: the clamp is an assumption and it is invisible. **I wrote no test**, per the
assignment: the right bound is a judgement, not a derivation, and any assertion would
freeze a number nobody has chosen. The minimum fix is a flag on the result saying the
clamp fired and what the raw rate was.

### 5. Two stops exist but name nothing · confirmatory, same shape as `P1-suite`'s finding 2

- `analysis/wacc.py:74` — `calculate_wacc(..., balance_sheet=None, ...)` →
  `AttributeError: 'NoneType' object has no attribute 'total_debt'`. Measured. This is the
  live defect `STATUS.md` §1 already records from the mypy error at
  `api/routes_valuation.py:190`; I have now confirmed it by running it rather than reading it.
- `analysis/capm.py:32` — return series of different lengths →
  `ValueError: Array shapes are incompatible for broadcasting.` from scipy. Measured.

Neither is locked by a test. Writing either green would photograph a third-party message
that names none of this repository's fields; writing either red would add a permanently
failing test for something nobody has scheduled. Both want the same one-line input check
as Finding 1.

### 6. `analysis/capm.py:14`'s import from `ingestion/` now costs the test suite 3 seconds · evidence for backlog item 17

`tests/unit/test_capm.py` must import `ingestion.price_fetcher` to build a `PriceData`,
which imports `yfinance`, `pandas` and `scipy`. The suite went from 0.23 s to 3.76 s, and
the cold run took 19.9 s. No request is made and no key is read — it is pure import cost —
but a unit test of a pure-arithmetic module should not be loading an HTTP client.
`PriceData` is a dataclass of five fields; moving it to `models/` closes item 17 and
takes the import with it. **Reported as evidence for item 17, not as a defect in the test.**

### 7. Figures for `STATUS.md`, which I may not edit

Measured at `19f1767` + **this unit only**, with `P1c-flow`'s files not yet present. The
orchestrator must combine these with `P1c-flow`'s own entry before writing `STATUS.md`;
I do not report that unit's figures.

| Line in `STATUS.md` | Now reads | Should read, this unit alone |
|---|---|---|
| test gate | 20 tests, 19 pass, 1 red | **57 tests, 56 pass, 1 red**, 3.76 s |
| phase-1 gate form | `19 passed` | **`56 passed`** |
| `tests/` — `.py` files | 13 | **16** |
| `tests/` — `assert` statements | 40 | **150** (40 + this unit's 110) |
| coverage of `analysis/` | `dcf.py` 100%, five modules 0%, TOTAL 194/12% | **`capm.py` 100%, `dcf.py` 100%, `fcff.py` 100%, `wacc.py` 100%, `normalizer.py` 0%, `projector.py` 0%. 98 of 194 statements, 51%** |
| §5 open items | — | add Findings 1-4 above; item 9's evidence is now executed-but-unasserted, which is worth saying |

**Combined tree, re-measured after `P1c-flow` landed its three files:** 19 `.py` files
under `tests/`, 261 `assert` statements, and
`pytest -q --ignore-glob="*_rule3_red.py"` → **`90 passed`, 0 failed**. The 19 − 16 = 3
files and the 261 − 150 = 111 assertions are that unit's, and `normalizer.py` /
`projector.py` coverage is its figure to report, not mine.

`docs/5-testing/strategy.md` §4 and §6 are stale in the same way: §6's order now has its
first three entries done, and §4's "the other five modules are at 0%" is no longer true.
