---
agent: programmer
assignment: P4c-nan-stops
round: 1
status: complete
files_touched: [analysis/capm.py, analysis/dcf.py, analysis/wacc.py]
verdict:
---

# P4c-nan-stops — a NaN can no longer reach the share price, and an empty projection list names `projected_fcffs`

Measured against `e01dddf`, on branch `build/phase-1-2`. Every row below was
executed; the two probe transcripts are at `c:/tmp/p4c_before.txt` and
`c:/tmp/p4c_after.txt`, produced by the same script `c:/tmp/p4c_chain.py`.

## What I did

Closed backlog item 20 with **three stops in series**, and item 14 with one raise.
`analysis/capm.py:calculate_beta` now rejects a series of unequal length, a series
shorter than three observations, and a regression whose statistics come back NaN —
each raise names the input. `analysis/wacc.py:calculate_wacc` checks its five named
inputs with `math.isnan` before assembling a discount rate, so a NaN arriving from a
path CAPM cannot see (an overridden beta, a NaN market cap, a `CAPMResult` built
elsewhere) also stops. `analysis/dcf.py:calculate_terminal_value` rejects a NaN WACC
or a NaN growth rate **before** the `wacc <= terminal_growth_rate` comparison, which
is the guard the defect defeated. `analysis/dcf.py:run_dcf` raises naming
`projected_fcffs` instead of letting `projected_fcffs[-1]` throw a bare `IndexError`.

**Every guard is `math.isnan`. Not one is a comparison.** `nan <= x`, `nan > x` and
`nan == nan` are all `False` — measured, below — which is the entire reason item 20
existed.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | an empty market series with a supplied premium **stops**, message names the input | **pass** | `PYTHONPATH=… .venv/Scripts/python.exe c:/tmp/p4c_chain.py`, case 1. Before/after transcripts below |
| 2 | a NaN cannot reach `run_dcf` from any path | **pass** | same script, cases 4, 9, 10, 11, 13 — degenerate variance, NaN in the `CAPMResult`, NaN `market_cap`, a NaN `WACCResult` handed straight to `run_dcf`, and a NaN growth rate. All five raise |
| 3 | an empty `projected_fcffs` stops and names the field | **pass** | same script, case 12. `IndexError: list index out of range` → `ValueError: projected_fcffs is empty: …` |
| 4 | **no existing assertion changed meaning** | **pass** | `.venv/Scripts/python.exe -m pytest -q` → `1 failed, 120 passed in 4.17s`. Failure **set** = `{tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent}`, identical to the baseline set, and still failing with `Failed: DID NOT RAISE ValueError` — the same reason as before, so item 2 is still open and its red test still states the requirement |
| 5 | coverage of both files does not fall | **FAIL — reported, not worked around** | 100% → `capm.py` 92% (3 missed), `dcf.py` 93% (2), `wacc.py` 97% (1). All six are new `raise` statements. Lines named below |
| 6 | lint unchanged | **pass** | `.venv/Scripts/python.exe -m ruff check .` → `Found 5 errors`, all `BLE001`, the same five files as `STATUS.md` §1 |
| 7 | types not worse | **pass — identical set, not merely a subset** | `comm -13`/`comm -23` against `git archive e01dddf`, line numbers stripped: **both empty**. 14 before, 14 after |
| 8 | the census did not rise | **pass** | the rule 3 grep → **116**, unchanged |

### Criterion 1 and 2 — before and after, same script, same cases

The script builds a `PriceData`, a `FinancialStatements` and two `ProjectedFCFF`s in
memory and drives `run_capm` → `calculate_wacc` → `run_dcf`. Cases 1-6 are the full
chain; 7-13 enter partway to reach a path the chain cannot.

**Before (`e01dddf`, `c:/tmp/p4c_before.txt`):**

```
=== 1. FULL CHAIN: empty market series, ERP supplied, no beta override
  RETURNED 'beta=nan  cost_of_equity=nan  wacc=nan  implied_share_price=nan'
=== 2. FULL CHAIN: one observation only (too short to regress)
  RETURNED 'beta=nan  cost_of_equity=nan  wacc=nan  implied_share_price=nan'
=== 3. FULL CHAIN: two observations (no residual degrees of freedom)
  RETURNED 'beta=1.0  cost_of_equity=0.1  wacc=0.09525798525798526  implied_share_price=16.86256083162375'
=== 4. FULL CHAIN: degenerate market series, zero variance (3 identical returns)
  RETURNED 'beta=nan  cost_of_equity=nan  wacc=nan  implied_share_price=nan'
=== 5. FULL CHAIN: stock and market series of different lengths
  RAISED  ValueError: Array shapes are incompatible for broadcasting.
=== 6. FULL CHAIN: a healthy 5-point regression (must still work)
  RETURNED 'beta=1.6  cost_of_equity=0.136  wacc=0.12798525798525798  implied_share_price=10.242377145601743'
=== 7. calculate_beta on empty series
  RETURNED (np.float64(nan), np.float64(nan), np.float64(nan))
=== 8. calculate_beta on a zero-variance market series
  RETURNED (np.float64(nan), np.float64(nan), np.float64(nan))
=== 9. calculate_wacc with a NaN beta in the CAPMResult
  RETURNED nan
=== 10. calculate_wacc with a NaN market_cap
  RETURNED nan
=== 11. run_dcf handed a NaN WACC directly
  (wacc is nan; nan <= 0.025 is False; nan > 0.025 is False)
  RETURNED nan
=== 12. run_dcf with an empty projected_fcffs list
  RAISED  IndexError: list index out of range
=== 13. run_dcf with a NaN terminal_growth_rate
  RETURNED nan
```

**After (`c:/tmp/p4c_after.txt`):**

```
=== 1. FULL CHAIN: empty market series, ERP supplied, no beta override
  RAISED  ValueError: market_returns and stock_returns hold 0 observations; beta needs at
          least 3 because the standard error of the slope divides by (n - 2). Supply a
          longer price history; a beta cannot be estimated from this one
=== 2. FULL CHAIN: one observation only
  RAISED  ValueError: … hold 1 observations; …
=== 3. FULL CHAIN: two observations
  RAISED  ValueError: … hold 2 observations; …
=== 4. FULL CHAIN: degenerate market series, zero variance
  RAISED  ValueError: the regression of stock_returns on market_returns produced no finite
          beta (beta=nan, r_value=nan, std_error=nan). market_returns has variance 0.0 over
          3 observations; a market series with no variation explains nothing and no beta
          exists for it
=== 5. FULL CHAIN: stock and market series of different lengths
  RAISED  ValueError: market_returns holds 2 observations and stock_returns holds 3: beta
          regresses one on the other period by period, so the two series must be aligned
          and of equal length
=== 6. FULL CHAIN: a healthy 5-point regression
  RETURNED 'beta=1.6  cost_of_equity=0.136  wacc=0.12798525798525798  implied_share_price=10.242377145601743'
=== 7. calculate_beta on empty series
  RAISED  ValueError: … hold 0 observations; …
=== 8. calculate_beta on a zero-variance market series
  RAISED  ValueError: … produced no finite beta …
=== 9. calculate_wacc with a NaN beta in the CAPMResult
  RAISED  ValueError: capm_result.cost_of_equity is NaN, so WACC cannot be computed from it. …
=== 10. calculate_wacc with a NaN market_cap
  RAISED  ValueError: market_cap is NaN, so WACC cannot be computed from it. …
=== 11. run_dcf handed a NaN WACC directly
  (wacc is nan; nan <= 0.025 is False; nan > 0.025 is False)
  RAISED  ValueError: WACC (nan) and terminal growth rate (0.025) must both be numbers; a
          NaN here would pass the spread check below silently and render as a NaN share
          price. A NaN WACC means an input was absent or degenerate in CAPM or in WACC
=== 12. run_dcf with an empty projected_fcffs list
  RAISED  ValueError: projected_fcffs is empty: a DCF needs at least one projected year,
          because the terminal value is built from the final projected FCFF
=== 13. run_dcf with a NaN terminal_growth_rate
  RAISED  ValueError: WACC (0.1) and terminal growth rate (nan) …
```

**Case 6 is the control and it is the important row.** The one healthy regression
returns `implied_share_price = 10.242377145601743` before and after, to the last
digit. Nothing that used to compute was made to compute differently.

**Case 3 changed behaviour, and it was not a NaN before.** At n = 2 scipy 1.18.1
returns a *finite* slope of 1.0 but `stderr = nan`, so the old code produced a share
price of `16.86…` while carrying a NaN into `CAPMResult.std_error`. Measured
directly:

```
$ .venv/Scripts/python.exe -c "from scipy import stats; …"
0 slope nan   rvalue nan   stderr nan
1 slope nan   rvalue nan   stderr nan
2 slope 1.0   rvalue 1.0   stderr nan
3 slope 1.0   rvalue 1.0   stderr 0.0
```

That is why the threshold is **3**, and it is derived rather than chosen:
`SE(beta) = sqrt(SSE / ((n - 2) * Sxx))` needs `n - 2 >= 1`. The constant is named
`MINIMUM_REGRESSION_OBSERVATIONS` with that derivation in the comment above it. It
never reaches a displayed figure — it only decides whether the run stops — so it is a
precondition, not a rule 6 assumption. If a reviewer reads it the other way, the fix
is to surface it, not to remove it.

### Criterion 5 — the coverage drop, in full

```
$ COVERAGE_FILE=c:/tmp/.cov_p4c_after .venv/Scripts/python.exe -m pytest -q \
    --ignore-glob="*_rule3_red.py" --cov=analysis --cov-report=term-missing

Name                     Stmts   Miss  Cover   Missing
analysis\capm.py            40      3    92%   58, 66, 80
analysis\dcf.py             29      2    93%   33, 82
analysis\fcff.py            19      0   100%
analysis\normalizer.py      36      0   100%
analysis\projector.py       68      0   100%
analysis\wacc.py            34      1    97%   41
TOTAL                      226      6    97%
120 passed
```

Baseline at `e01dddf` was `202 statements, 0 missed, 100%` across all six modules.
**All six missed lines are new `raise` statements and nothing else is uncovered:**

| Line | Statement | What reaches it |
|---|---|---|
| `analysis/capm.py:58` | `raise ValueError(` | stock and market series of unequal length |
| `analysis/capm.py:66` | `raise ValueError(` | fewer than 3 observations, including the empty series of item 20 |
| `analysis/capm.py:80` | `raise ValueError(` | a regression that returned NaN — zero variance in the market series |
| `analysis/dcf.py:33` | `raise ValueError(` | a NaN WACC or a NaN terminal growth rate |
| `analysis/dcf.py:82` | `raise ValueError(` | an empty `projected_fcffs` (item 14) |
| `analysis/wacc.py:41` | `raise ValueError(` | any of the five `_require_finite` call sites with a NaN |

Each is reachable, and case-by-case reachability is demonstrated above by execution.
**I did not write a test to close them** — `tests/` is out of my scope and a
programmer that writes its own tests tests the code it remembers writing. I also did
not restructure anything to hold the percentage; the assignment was explicit that an
honest gap beats contorted code.

`analysis/wacc.py` holds five guards behind one helper, so the drop there is 1 line
rather than 5. **That is a design choice, and a reviewer should know it cuts the
visible gap.** I made it because five textually identical `if math.isnan(x): raise`
blocks in one function are harder to read than five named call sites, not to protect
the number — the five call sites are themselves statements and are all covered, so
the helper moves one uncovered line, not five behaviours.

### Criterion 7 — the type set, diffed not counted

```
$ git archive e01dddf | tar -x -C /c/tmp/p4c_base
$ (cd /c/tmp/p4c_base && … -m mypy models analysis ingestion api config.py app.py \
     --ignore-missing-imports) | grep "error:" | sed -E 's/:[0-9]+:/:/' | sort > before.txt
$ (… same command on the working tree …)                                    > after.txt
before=14  after=14
--- ADDED (comm -13) ---   (empty)
--- REMOVED (comm -23) --- (empty)
```

The two sets are **identical**, not merely nested. Nothing was added and nothing was
accidentally fixed.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Step 3 went in **`analysis/wacc.py`**, not `capm.py` | `calculate_wacc` is the single point where every input to the discount rate converges: the CAPM cost of equity, a cost of debt that may be overridden, a tax rate from the filing, a market cap from market data, a debt balance from the balance sheet | A guard in `capm.py` cannot see four of those five. Case 10 (a NaN `market_cap`) and case 9 (a `CAPMResult` assembled elsewhere, e.g. from a NaN `beta_override`) both reach WACC without passing through `calculate_beta` at all. The assignment permitted `wacc.py` only if step 3 belongs there; it does |
| **Step 4: `analysis/dcf.py`'s guard now rejects NaN itself.** I did not rely on steps 1 and 3 | It is the last line of defence before a price is rendered, and `run_dcf` is a public function reached by both entry points (`api/routes_valuation.py:217`, `cli.py:735`). Case 11 hands a NaN `WACCResult` straight to it, bypassing CAPM and WACC entirely, and before this change it returned `implied_share_price = nan` | Relying on the upstream stops would leave `calculate_terminal_value` correct only for callers that came through `calculate_wacc`. Three stops in series is the whole point: the assignment's own evidence is that a single guard, written as a comparison, was defeated |
| Threshold of **3** observations, not 2 | Derived from `SE(beta) = sqrt(SSE / ((n - 2) * Sxx))`, and measured: scipy returns `stderr = nan` at n = 2 while the slope is finite | A "beta is finite" check alone lets n = 2 through with a NaN standard error landing in `CAPMResult.std_error`. `calculate_beta`'s contract is three statistics, so all three must be finite for it to return |
| Checked the NaN **and** the input length, rather than only the output | The three messages name *which* input was inadequate — empty, mismatched, or degenerate. An output-only check can say "beta is NaN" and nothing more | Rule 3 requires the field to be named, not just the stop |
| `tax_rate` checked **before** the `[0.0, 0.50]` clamp | Measured: `min(nan, 0.50)` is `nan` but `max(0.0, nan)` is **`0.0`**. Both builtins fall through on a false comparison, so a NaN tax rate was silently read as a 0% rate — a full tax shield on the debt term | Checking after the clamp would never fire, because the clamp has already destroyed the evidence. This is a new finding; see below |
| Kept the existing `wacc <= terminal_growth_rate` message byte-for-byte | Four assertions in `tests/unit/test_dcf.py` read `"WACC"`, `"0.03"`, `"growth"`, `"0.05"` and `message.count("0.05") >= 2` out of it | The new NaN raise is a separate, earlier statement, so the old message is unreachable only on a path that used to be wrong |
| Converted the two series with `np.asarray(..., dtype=float)` | `.size` and the mismatch check need an array, and `PriceData`'s declared `np.ndarray` type is not enforced at run time | Using `len()` on whatever arrived would fail confusingly on a scalar rather than naming the field |

**No change here was made to reach a target number.** The only figure this unit moves
is case 3's `16.86…`, which stops instead of rendering, and the reason is measured
scipy behaviour at n = 2 rather than the size of the number.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `price_data.market_returns` in `calculate_beta` | **stops and names `market_returns`** | `analysis/capm.py:58,66,80`. Probe cases 1, 2, 3, 5, 7 |
| `price_data.stock_returns` in `calculate_beta` | **stops and names `stock_returns`** | `analysis/capm.py:58`. Probe case 5 |
| a market series with no variation | **stops and names `market_returns`, with its variance** | `analysis/capm.py:80`. Probe cases 4, 8 |
| `capm_result.cost_of_equity` in `calculate_wacc` | **stops and names `capm_result.cost_of_equity`** | `analysis/wacc.py:41`. Probe case 9 |
| `market_cap` in `calculate_wacc` | **stops and names `market_cap`** | `analysis/wacc.py:41`. Probe case 10 |
| `balance_sheet.total_debt` in `calculate_wacc` | **stops and names `balance_sheet.total_debt`** (when NaN) | `analysis/wacc.py:41`, call site at `:111` |
| `tax_rate` in `calculate_wacc` | **stops and names it** (when NaN) — previously clamped silently to `0.0` | `analysis/wacc.py:41`, call site at `:104` |
| `cost_of_debt` in `calculate_wacc` | **stops and names `cost_of_debt`** (when NaN) | `analysis/wacc.py:41`, call site at `:97` |
| `wacc` in `calculate_terminal_value` | **stops** — `math.isnan`, then the unchanged spread check | `analysis/dcf.py:32-33`, then the unchanged `:39`. Probe case 11 |
| `terminal_growth_rate` in `calculate_terminal_value` | **stops** | `analysis/dcf.py:33`. Probe case 13 |
| `projected_fcffs` in `run_dcf` | **stops and names `projected_fcffs`** | `analysis/dcf.py:82`. Probe case 12. Item 14 closed |
| `balance_sheet.total_debt` when it is **zero** in `calculate_cost_of_debt` | **defaults to `0.0`** | `analysis/wacc.py:64-65`. **Unchanged — backlog item 22, out of scope** |
| `interest_expense` when zero but debt exists | **defaults to `config.DEFAULT_COST_OF_DEBT`**, unlabelled | `analysis/wacc.py:68-70`. **Unchanged — backlog item 9, explicitly out of scope** |
| `market_cap + total_debt` when both are zero | **defaults to `equity_weight = 1.0`** | `analysis/wacc.py:114-121`. Unchanged, not on the backlog |
| `latest_bs` in `run_dcf` | **defaults to `net_debt = 0.0`** | `analysis/dcf.py:101`. **Unchanged — backlog item 2. Its red test must stay red, and does** |
| `r_squared` / `std_error` under `beta_override` | **set to `0.0`** | `analysis/capm.py:137-138`. Unchanged, named below |
| a projected FCFF that is itself NaN | **does not stop — `pv_fcffs` and the price go NaN** | `analysis/dcf.py:46-57`. **New finding, see below.** Not fixed: outside items 20 and 14 |

Five "defaults to" rows survive. Four are recorded backlog items the assignment put
out of scope; the fifth (NaN in a projected FCFF) is new and reported rather than
fixed, because widening my own scope is forbidden.

## Measurements

### The `nan` facts this unit rests on, executed

```
$ .venv/Scripts/python.exe -c "n=float('nan'); …"
min(nan,0.50) = nan
max(0.0, min(nan,0.50)) = 0.0        <- a NaN tax rate was read as 0%
nan <= 0.025 = False   nan > 0.025 = False   nan == nan = False
```

### Gates, before and after

| Gate | `e01dddf` | After |
|---|---|---|
| `pytest -q` | `1 failed, 120 passed` | `1 failed, 120 passed` — **same failure set**, same reason (`DID NOT RAISE`) |
| `pytest -q --ignore-glob="*_rule3_red.py"` | `120 passed` | `120 passed` |
| `ruff check .` | 5, all `BLE001` | 5, all `BLE001`, same five files |
| mypy | 14 errors, 4 files | 14 errors, 4 files — **set-identical** |
| rule 3 census | 116 | 116 |
| coverage, `analysis/` | 202 stmts, 0 missed, 100% | 226 stmts, **6 missed**, 97% |
| `git diff --stat` | — | 3 files, 113 insertions, 2 deletions |

### The one figure this unit reports, and whether it came from data

`implied_share_price = 10.242377145601743`, probe case 6, identical before and after.
**It is not a valuation and must not be read as one.** There are no PDFs on this
machine (`STATUS.md` §3), so every statement in the probe is hand-built. What I can
show is that the figure is not manufactured from zeros — it tracks the balance-sheet
input it is bridged through:

```
long_term_debt=  500.0  net_debt=  400.0  implied_share_price=10.242377145601743
long_term_debt=  600.0  net_debt=  500.0  implied_share_price= 9.564947374012805
long_term_debt=    0.0  net_debt= -100.0  implied_share_price=14.216121050628088
```

The move is not exactly `100 / 100 shares = 1.00` because `total_debt` also shifts the
WACC weights. `STATUS.md` standing trap 2 applies in full: "the valuation ran" is not
evidence of anything, and I am not claiming it is.

## What I did not do

- **Wrote no test.** `tests/` is outside my scope and a hook denies it. The six
  uncovered `raise` lines are enumerated above so the tester that follows can close
  them without rediscovering them.
- **Did not touch `models/valuation.py`.** `WACCResult.wacc` and
  `DCFResult.implied_share_price` are read, never modified; 40 assertions rest on
  them and the assignment called a change there an escalation. None was needed.
- **Did not fix backlog item 9** (the unlabelled `DEFAULT_COST_OF_DEBT`), **item 2**
  (`analysis/dcf.py:101`, zero net debt — its red test is still red), **item 22**
  (zero debt balance → 0% cost of debt) or **item 1**. All named in the table above.
- **Did not fix the NaN-in-a-projected-FCFF hole** I found. Reported below.

### The three "Known open items" — seen, left, and named

1. **`analysis/capm.py:16` imports `PriceData` from `ingestion/`** — backlog item 17,
   a layering break in a file I edited. I saw it; I did not move `PriceData`, and my
   change does not deepen the dependency (it adds `math` and uses `numpy`, both
   already imported).
2. **`analysis/capm.py:98-100` switches from geometric to arithmetic annualisation**
   when the compounded gross return is `<= 0`, silently and with no record on
   `CAPMResult`. Reported by `P1b-arith`, not on the backlog, not in this unit. I
   left it untouched — note that `tests/unit/test_capm.py:258` **asserts** its output
   (`-0.8`), so a future unit that raises here instead turns that test red, and the
   reviewer of `P1b-arith` flagged exactly that as F2.
3. **`analysis/capm.py:137-138` sets `r_squared` and `std_error` to `0.0`** when a
   beta is supplied, so "no regression ran" is indistinguishable from "it explained
   nothing". Left. Worth saying that this unit makes it slightly sharper: a real
   regression can no longer return `0.0` for `std_error` **by accident** through a
   NaN, so the two `0.0`s that remain are now only the override's.

## Findings for the orchestrator

### 1. A NaN tax rate was silently clamped to 0%, in the code I was editing · new

`analysis/wacc.py`'s clamp is `max(0.0, min(tax_rate, 0.50))`. Measured:
`min(nan, 0.50)` is `nan`, but `max(0.0, nan)` is **`0.0`**, because `nan > 0.0` is
False and `max` keeps its first argument. So a NaN effective tax rate — which
`models/financial_statements.py`'s `tax_expense / ebt` produces from a NaN on either
side — was read as a 0% rate, giving the debt term a full tax shield, on a clean run.
This is the same mechanism as item 20 in a different place. **I fixed it inside this
unit** because the guard had to go somewhere and before-the-clamp is the only place
it can fire; the finding is recorded so the shape is on the record. `analysis/fcff.py`
has the identical clamp at line 44 and **is not fixed** — same defect, different file,
outside my scope.

### 2. A NaN in a single `ProjectedFCFF` still produces a NaN share price · new

`analysis/dcf.py:46-57` sums `fcff.fcff / (1 + wacc) ** i` with no finiteness check,
and `projected_fcffs[-1].fcff` feeds the terminal value. A NaN in one projected year
therefore reaches `implied_share_price` even with a perfectly finite WACC — the three
stops this unit added all sit on the discount-rate side of the calculation. The
upstream is `analysis/projector.py`, whose inputs are the zero-defaulted money fields
of backlog item 1. **Not fixed: it is neither item 20 nor item 14, and widening scope
is forbidden.** It wants an assignment of its own, and it is cheap — one
`math.isnan` in `discount_cash_flows` and one on `final_fcff`.

### 3. Backlog items 20 and 14 are closed, and `STATUS.md` §5 needs re-ranking

Item 20 was `STATUS.md`'s highest-cost open defect. It is closed by three stops in
series, each proved by execution above. Item 14 is closed by
`analysis/dcf.py:82`. `STATUS.md` §5's "Open" table and §1's coverage block
(`analysis/` is no longer 100%) both need the orchestrator's re-measurement; I may
not edit that file.

### 4. The scripts under `tests/` call this path and none of them is collected

`tests/test_e2e_*.py` and `tests/_run_lly_dcf.py` — six files — call
`run_capm` → `calculate_wacc` → `run_dcf` against real tickers. None is collected by
pytest (backlog item 16, the broken `sys.path.insert`), so none exercised the NaN
path and none will exercise the new stops. They are not a regression risk for this
unit; they are the reason nobody noticed item 20 for the life of the repository.
