---
agent: code_reviewer
assignment: P1b-arith
round: 1
verdict: approved
---

# Review of P1b-arith, round 1

Entry under review: `.agent/journal/2026-09-20T2145-tester-p1b-arith.md` (written by the
`tester` agent, read in place of a programmer entry).

Scope confirmed. `git status --short` shows this unit's additions as exactly
`tests/unit/test_fcff.py`, `tests/unit/test_wacc.py`, `tests/unit/test_capm.py`. No
tracked file is modified (`git diff --stat` → empty), so no implementation file, no
`tests/unit/__init__.py`, no `test_dcf*.py` and none of the nine scripts were touched.
`P1c-flow`'s three files are present and I did not read, run or judge them except to
exclude them.

The unit's `verdict: fail` is a verdict about `analysis/`, which it was forbidden to
edit. I judged the deliverable.

## The guard checks

Run over the three files in scope only.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean |
| lookup with a fallback — `.get(k, 0)` | clean |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output |

All eight greps returned nothing. No hit to answer.

## Are the expected values independent of the code? — re-derived, not accepted

I derived each of these from the formula in `docs/3-architecture/valuation-math.md` and
the property definitions in `models/`, without running `analysis/`.

| Assertion | My re-derivation | Agree? |
|---|---|---|
| `test_beta_on_an_imperfect_fit_solved_by_hand` — β `1.6`, R² `16/17`, SE `√(4/75)` | x̄ = 0, ȳ = 0.004. `Sxy = 0.00068+0.00014+0+0.00006+0.00072 = 0.0016`; `Sxx = 0.001`; `Syy = 0.001156+0.000196+0.000036+0.000036+0.001296 = 0.00272`. β = 0.0016/0.001 = **1.6**. R² = 2.56e-6/(0.001·0.00272) = 2.56/2.72 = **16/17**. SSE = 0.00272 − 2.56·0.001 = 0.00016; s² = 0.00016/3; SE = √(s²/Sxx) = √(0.0533̄) = **√(4/75)** | yes — all three, exactly |
| `test_historical_fcff_worked_example` — FCFF `210` | opex 600+50+0+50+0 = 700 → EBIT 300; EBT 300−100 = 200; t = 40/200 = 0.20; CFO 160+50+30−40 = 200; 200 + 100·0.80 − 70 = **210** | yes, all 9 figures |
| `test_wacc_worked_example` — WACC `0.075` | D = 100+50+250 = 400 (`total_debt`, `financial_statements.py:187`); V = 1000; Rd = 20/400 = 0.05; EBT = 320−20 = 300, t = 75/300 = 0.25; 0.6·0.10 + 0.4·0.05·0.75 = **0.075** | yes, all 6 |
| `test_the_two_fcff_methods_agree_when_the_definitions_line_up` — both `185` | historical: CFO 225+50+0−20 = 255, +0 − 70 = **185**. projected: EBIT 1000·0.30 = 300, NOPAT 225, +50 −70 −20 = **185**. Two independent routes | yes |
| `test_stock_based_compensation_is_the_gap_…` — gap `30` | CFO 225+50+30−20 = 285; 285 − 70 = 215; 215 − 185 = **30** | yes |
| `test_compounding_across_a_half_year_of_periods` — `0.20` | 1.5·0.8·1.5·0.8 = 1.44; 1.44^(2/4) = 1.2; **0.20**. Arithmetic annualisation of the same series gives 0.30, so it is falsifiable | yes |
| `test_run_capm_end_to_end_…` — Ke `0.37` | market return 0.20; ERP 0.20 − 0.03 = 0.17; 0.03 + 2·0.17 = **0.37**. At the config default Rf the same run gives 0.36 | yes, all 6 |
| `test_wacc_at_a_zero_tax_rate_…` — `0.095`, and `test_the_tax_shield_…` — `0.090`, gap `0.005` | 0.75·0.10 + 0.25·0.08 = 0.095; with t = 0.25, 0.075 + 0.25·0.08·0.75 = 0.090; gap = (D/V)·Rd·t = **0.005** | yes |
| `test_projected_fcff_*` — `240`, `260`, `200` | 2000·0.20 = 400, ·0.75 = 300, +80 −120 −20 = **240**; at ΔNWC 0, **260**; NOPAT at t = 0 is EBIT = 500·0.40 = **200** | yes |
| `test_wacc_with_no_debt_…` — `0.10` with `Kd = 0.90` | identity: 1.0·0.10 + 0.0·0.90·0.60 = **0.10**. Market cap is 1000, so the weights are computed, not the `wacc.py:77-84` fallback | yes |

**No assertion I checked is a photograph of output.** Several are genuinely falsifiable
against a plausible wrong implementation, which is the property that matters: the OLS
row would catch a mis-weighted estimator, the half-year row tells geometric from
arithmetic, the two-methods row goes red if either formula drifts, and every `abs()`
pair would go red on a sign carried through. The entry's process claim ("matched on the
first execution, no expectation revised") is not verifiable by me; the arithmetic is,
and it holds. Counts reconcile: `grep -c "^\s*assert "` → 47 / 31 / 32 = **110**, and
`grep -c "^def test"` → 11 / 12 / 14 = **37**, with 2 `pytest.raises(ValueError)`.

## Does any test lock a defect as an expectation?

**No.** I checked all 110 assertions and both sets of fixture builders against
`docs/5-testing/strategy.md` §2.

- `wacc.py:41-43` (`DEFAULT_COST_OF_DEBT`) — executed by `test_wacc.py:335-346`; the
  four assertions are `cost_of_equity`, `tax_rate` and the two weights. Neither
  `cost_of_debt` nor `wacc` is asserted, so nothing carries the 0.04.
- `wacc.py:77-84` (all-equity weights) — executed by `test_wacc.py:363-370`; the single
  assertion is the CAPM pass-through. The weights and the WACC are untouched.
- `wacc.py:37-38` (`return 0.0` at zero debt) — executed by `test_wacc.py:251-259`,
  which asserts `debt_weight == 0.0` (the **computed** 0/1000, not the fallback) and
  `wacc == 0.10`, an identity that holds for any `Rd` because `D/V = 0`.
- `capm.py:84-85` (zeroed diagnostics under `beta_override`) — executed by four tests;
  `r_squared` and `std_error` are asserted in none of them.
- The `[0.0, 0.50]` tax clamp — every `tax_rate_override` in the suite is 0.0, 0.20,
  0.25 or 0.40, all inside the band, so no assertion sits on a clamped value.
- `models/valuation.py:138` and `:69,73` (zero-share price, zero-revenue margins) — not
  asserted; `diluted_shares` never appears and neither margin property is read.

`test_the_risk_free_rate_defaults_to_the_named_constant` asserts
`config.DEFAULT_RISK_FREE_RATE` reaches `CAPMResult`, and I checked whether that is a
blessed fallback. It is not: both call sites pass `overrides.risk_free_rate`
(`api/routes_valuation.py:169`, `cli.py:689`), which is `None` only when the user
supplied nothing — there is no risk-free-rate fetch anywhere in the repository for the
default to paper over. It is a rule 6 assumption, and asserting that the named default
reaches the output is stating rule 6's visibility requirement, not encoding a rule 3
hole. (`config.py:20`'s comment "fallback if market fetch fails" is stale — no such
fetch exists. `config.py` is out of scope and was not touched; recorded here only so the
next reader does not re-litigate this test.)

## The NaN path — confirmed end to end, and it is real

The entry's Finding 1 is correct and worse than a beta figure. Measured from a scratch
script at `c:/tmp/rev_p1b_nan.py`, outside the repository:

```
beta          : nan          run_capm(empty series, risk_free_rate=0.03, equity_risk_premium=0.05)
cost_of_equity: nan
wacc          : nan
nan <= 0.025  : False
DCFResult type      : DCFResult      <- a complete object, no exception anywhere
pv_fcffs            : nan
terminal_value      : nan
enterprise_value    : nan
net_debt            : 350.0
implied_share_price : nan
upside_downside     : nan
```

The chain, with every link:

1. `analysis/capm.py:72` — an ERP is supplied, so the `else` branch that would call
   `annualized_market_return` is skipped and the one existing guard
   (`analysis/capm.py:42-43`) never runs.
2. `analysis/capm.py:87` → `analysis/capm.py:32` — `stats.linregress` on two empty
   arrays returns `nan` for slope, `rvalue` and `stderr`, emits a `SmallSampleWarning`
   on stderr, and raises nothing.
3. `models/valuation.py:16` — `cost_of_equity = rf + nan * erp` → `nan`.
4. `analysis/wacc.py:66`, then `models/valuation.py:34-38` — `WACCResult.wacc` → `nan`.
5. `analysis/dcf.py:24` — `if wacc <= terminal_growth_rate` is `nan <= 0.025`, which is
   `False`, so the one guard in `analysis/` that behaves the way rule 3 requires does
   **not** fire.
6. `analysis/dcf.py:70,74,75` → `models/valuation.py:138` — a complete `DCFResult` with
   `implied_share_price = nan` and `upside_downside = nan`.

Both entry points reach it: `api/routes_valuation.py:167-172` and `cli.py:687-692` both
pass `equity_risk_premium=overrides.equity_risk_premium`, so any user who supplies an
ERP on the form or the CLI and hits a short or empty return series gets a rendered
share price of `nan`. This is the most valuable thing in the unit and it needs an
assignment; the tester was right not to write it as a green test and right not to write
it red without the correct behaviour agreed. **Not a finding against this unit** — it is
a pre-existing defect in a file the assignment placed out of scope, and it was reported
with the correct `file:line`.

I also reproduced every other measured claim in the entry's probe table, all seven,
identically: `fcff` on empty statements → `0.0`; `calculate_cost_of_debt` with interest
20 and no debt → `0.0`; both tax clamps at a 60% effective rate → `0.5`;
`calculate_wacc(balance_sheet=None)` → `AttributeError: 'NoneType' object has no
attribute 'total_debt'`; mismatched return lengths → `ValueError: Array shapes are
incompatible for broadcasting.`

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| every value the three **test** files read | n/a — the files read only literals they define; no `.get`, no `or`, no defaulted field | guard greps clean |
| `market_returns` via `annualized_market_return` | yes | `analysis/capm.py:42-43`; locked on type **and** on the field named in the message, `test_capm.py:208-237` (two tests, direct and through `run_capm`) |
| `market_returns` when an ERP is supplied | **no — returns NaN** | `analysis/capm.py:87`. Reported, not asserted. Chain above |
| `interest_expense`, `market_cap + total_debt`, `total_debt`, the tax clamp, the beta-override diagnostics | **no — five defaults** | `wacc.py:37-38,41-43,71,77-84`, `fcff.py:44`, `capm.py:82-85`. All executed for coverage, none asserted. Docstrings at `test_wacc.py:23-34,240-249,318-333,349-361` and `test_capm.py:29-36,295-312` name the line each test steps over |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | consistent — revenue 1000, debt 400, CapEx 70, market cap 600, all millions; no share count and no price appears, so no boundary is crossed |
| percentages converted at the route boundary, once | n/a — no route touched. Every rate in the fixtures is already a decimal (`0.20`, `0.05`, `0.25`) |
| falsy not treated as missing | clean — the suite deliberately exercises real zeros as values (`tax_rate_override=0.0`, `beta_override=0.0`, twelve zero returns) and adds no `if x` site |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | unchanged by this unit. `test_capm.py:49` imports `ingestion.price_fetcher.PriceData` because `analysis/capm.py:14` does — backlog item 17, named in the assignment as unavoidable and out of scope. A test file is not `analysis/`, so no layering rule is crossed |

## Done-criteria, re-run

Every figure below I executed myself, with `COVERAGE_FILE` under `c:/tmp/` so the
parallel unit could not collide on the root `.coverage`.

| # | Criterion | Claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | no unexpected failure | 56 passed / 0 failed; failure set unchanged | `pytest -q --ignore-glob="*_rule3_red.py"` → **`90 passed`** on the combined tree, 0 failed. With `P1c-flow`'s three files ignored: **`1 failed, 56 passed`**, failure set `{test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent}` — one element, `P1-suite`'s. Baseline with this unit's three files also ignored: **`1 failed, 19 passed`**, same one-element set. I compared the **sets**, not the counts | yes |
| 2 | `analysis/fcff.py` 100% | 19/19 | `analysis\fcff.py 19 0 0 0 100%` | yes |
| 3 | `analysis/wacc.py` 100% | 25/25 | `analysis\wacc.py 25 0 8 0 100%` | yes |
| 4 | `analysis/capm.py` ≥ 90% | 100%, no line to name | `analysis\capm.py 30 0 8 0 100%` | yes |
| 5 | every assertion sourced | 37 rows → 110 asserts | the table is one row per **test function**, not one per assertion as the criterion words it; every row enumerates the expected values it covers and the counts reconcile (47+31+32 = 110). I re-derived ten rows covering ~45 assertions, above | yes, in substance |
| 6 | `tests/` lints with exactly 1 error | 1 `BLE001` | `ruff check tests --output-format concise` → `tests\test_e2e_all_googl.py:106:16: BLE001` / `Found 1 error.` Repo-wide → `Found 5 errors`, all `BLE001`, the set `STATUS.md` §1 records | yes |
| 7 | no key, no PDF, no network | 56 passed with keys unset | `ls .env` → no such file; both keys `None`. Stronger check: I ran the three files with **all socket connections denied** (a `sitecustomize.py` on `PYTHONPATH` replacing `socket.socket.connect`, `connect_ex` and `create_connection` with a raise) → **`37 passed in 3.38s`**. No request is made | yes, independently |

The narrow coverage figure reproduces exactly, and the narrow measurement was the right
call — `analysis/projector.py` imports `calculate_fcff_projected`, so a whole-suite
figure would now credit `P1c-flow`'s tests to `fcff.py`:

```
$ COVERAGE_FILE=c:/tmp/.coverage_rev_p1b_narrow .venv/Scripts/python.exe -m pytest -q \
    tests/unit/test_fcff.py tests/unit/test_wacc.py tests/unit/test_capm.py \
    --cov=analysis.fcff --cov=analysis.wacc --cov=analysis.capm --cov-branch --cov-report=term-missing
analysis\capm.py      30      0      8      0   100%
analysis\fcff.py      19      0      0      0   100%
analysis\wacc.py      25      0      8      0   100%
TOTAL                 74      0     16      0   100%
37 passed in 3.40s
```

**74 of 74 statements and 16 of 16 branches, from this unit's three files alone.**
Confirmed. The entry's caveat that coverage.py does not count a conditional *expression*
as a branch is correct and matters here: `fcff.py` reports 0 branches while holding the
`tax_rate_override if … else …` at line 43, and both sides are nonetheless exercised by
five tests.

The entry's `STATUS.md` figures also check out: `find tests -name "*.py" | wc -l` → 19
and `grep -rh "^\s*assert " tests | wc -l` → **261** on the combined tree, i.e. 16 files
and 150 assertions for this unit's slice, exactly as stated.

## Findings

### F1 — the Findings section omits known open item 4, while an earlier row claims it reports it · `minor`

**Evidence:** the geometric→arithmetic switch at `analysis/capm.py:45-47` appears once in
the entry, at `2026-09-20T2145-tester-p1b-arith.md:279`, which says "*the entry for this
unit reports it*"; Findings 1-7 (lines 328-422) contain no row for it and the rule-3
table (lines 89-102) contains no row for it either.
**Rule or document:** no rule — the assignment's "Known open items" 4: "*Report it.*" The
orchestrator reads the Findings list when it records open items, and item 4 is not in it.
**What would fix it:** one Findings row naming `analysis/capm.py:45-47`, the behaviour,
and the fact that it is the only fallback in the suite that is asserted.

### F2 — the only asserted fallback in the suite is not listed anywhere a future fixer would look · `note`

**Evidence:** `tests/unit/test_capm.py:258` asserts `== pytest.approx(-0.8)`, the output
of the arithmetic-annualisation branch at `analysis/capm.py:45-47`.
**Rule or document:** not a rule break. `docs/3-architecture/valuation-math.md:121-124`
states that this fallback "*is a genuine numerical guard, not a rule 3 violation*", and
the assignment explicitly permits testing the branch provided the entry says so — which
the test docstring (`test_capm.py:241-254`) and the entry both do. The point is only
that if the orchestrator ever records a fix that raises here instead of switching
formula, this assertion turns that fix red, and nothing in the red-test inventory or the
entry's "What I did not do" would lead anyone to it.
**What would fix it:** name it alongside F1's Findings row, so the assertion and the
open item are recorded together.

### F3 — two fixture comments state a derivation whose zero terms come from `models/` defaults · `note`

**Evidence:** `tests/unit/test_wacc.py:50-52` documents `EBIT = 1000 - 680 = 320`, but
`_income_statement()` (`test_wacc.py:69-76`) sets only `revenue` and `cost_of_revenue`;
`sga`, `rd_expense`, `depreciation_amortization` and `other_operating_expense` are zero
by the dataclass defaults at `models/financial_statements.py:60-63`.
**Rule or document:** none — this is the same shape as `P1-suite`'s F1, and backlog item
1 covers the defaults themselves. `tests/unit/test_fcff.py:35-36` does it better,
enumerating `1000 - (600 + 50 + 0 + 50 + 0)`. The exposure is forward-compatibility: when
item 1 makes those fields required, these fixtures need editing and the comment gives no
warning.
**What would fix it:** pass the zero terms explicitly, or enumerate them in the comment
as `test_fcff.py` does.

No `blocker` and no `major`. F1 is `minor` because the substance is in the entry — the
`file:line`, the behaviour and the disclosure are all there — and only its placement is
wrong.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 — zero-default sites | `models/financial_statements.py:47-104,217-234`, `:101`, `models/valuation.py:69,73,138` | no. Used to build fixtures, never asserted |
| 2 — zero net debt on an absent balance sheet | `analysis/dcf.py:80` | no. `P1-suite`'s red test states it |
| 9 — unlabelled cost of debt | `analysis/wacc.py:41-43` | no. Branch executed, value never asserted |
| 17 — `analysis/` imports `ingestion/` | `analysis/capm.py:14` | no. The test's `PriceData` import is the consequence, and the assignment says so |
| 8 — blanket `except Exception` | `tests/test_e2e_all_googl.py:106` | no. The one deferred lint error, unchanged |

I saw all five and am not reporting them. The five "Known open items" named in the
assignment are likewise excluded from my findings, except F1, which is about one of them
being missing from the report rather than about the defect itself.

## Verdict

`approved`

The deliverable is correct, in scope and maintainable. Every expected value I re-derived
matches its stated source, including the OLS case — β = 1.6, R² = 16/17 and
SE = √(4/75) all fall out of the normal equations on the fixture's own numbers — and
several assertions are genuinely falsifiable against a plausible wrong implementation,
which is the property an output-photographed suite cannot have. No assertion in the 110,
and nothing in the fixtures, locks a rule 3 fallback; the six defaulting branches are
executed for coverage and each is named in the docstring of the test that steps over it.
All seven done-criteria re-measured and agreed, with criterion 7 checked harder than
claimed (sockets denied, `37 passed`) and coverage re-measured narrowly under an isolated
`COVERAGE_FILE`: 74 of 74 statements and 16 of 16 branches from this unit's three files
alone. The entry's new Finding 1 is confirmed end to end — a complete `DCFResult` with
`implied_share_price = nan` comes out of `run_capm` → `calculate_wacc` → `run_dcf` with
no exception raised, because `analysis/dcf.py:24` compares `nan <= g` and gets `False`;
that needs its own assignment. The three findings are one `minor` and two `note`s, all
about the entry's bookkeeping rather than the tests, and none blocks.
