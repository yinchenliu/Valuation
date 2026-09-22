---
agent: programmer
assignment: P4d-cashflow-nan
round: 1
status: complete
files_touched: [analysis/dcf.py, analysis/fcff.py]
verdict:
---

# P4d-cashflow-nan — guard the cash-flow side of the DCF, and close the tax clamp twin

Measured at `eed4fe1` (clean tree) before, and on the working tree after. Probe:
`c:/tmp/p4d_probe.py`, 9 controls + 11 NaN cases + 3 FACT lines. Transcripts:
`c:/tmp/p4d_before.txt`, `c:/tmp/p4d_after.txt`.

Run it with `PYTHONPATH=/c/Users/LiuYinchen/Valuation .venv/Scripts/python.exe
c:/tmp/p4d_probe.py`.

## What I did

Two guards, both `math.isnan`, both following the `_require_finite` pattern
`P4c-nan-stops` established in `analysis/wacc.py`.

**Backlog item 30.** `analysis/dcf.py` now checks every projected cash flow before it
is used. `discount_cash_flows` checks each year's `fcff` **inside the loop, before the
`pv +=`**, and names the year (`the projected FCFF for year 2027`), not just the field.
`calculate_terminal_value` checks its `final_fcff` parameter. Before this, a NaN in one
`ProjectedFCFF` produced `implied_share_price = nan` with a finite WACC and no
exception anywhere — all eleven NaN cases below returned a number-shaped `nan`; all
eleven now raise.

**Backlog item 23b.** `analysis/fcff.py:44` held the twin of the tax clamp that
`P4c-nan-stops` fixed in `wacc.py`. `max(0.0, min(nan, 0.50))` is `0.0`, so a NaN tax
rate was silently read as a 0% rate. The check now sits **before** the clamp, exactly as
`analysis/wacc.py:104` sits before its clamp at `:106`. Measured cost of the defect, on
my control figures: a NaN tax rate gave `tax_rate=0.0 after_tax_interest=10.0
fcff=115.0` where the filing's own rate gives `tax_rate=0.25 after_tax_interest=7.5
fcff=112.5`. The unknown rate **raised** FCFF by 2.5 in one year, through a full
untaxed interest add-back, and read as a measurement.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | NaN in a middle-year `ProjectedFCFF` stops, naming the year | **pass** | probe N1 (index 2 of 5, `nopat=nan`), N4 (`depreciation_amortization=nan`), N7 (direct `discount_cash_flows`), N9 (via `calculate_fcff_projected`). Before: `price=nan`. After: `ValueError: the projected FCFF for year 2027 is NaN, so it cannot be discounted…` |
| 2 | NaN in the final-year `ProjectedFCFF` stops, naming the year | **pass** | probe N2 (`nopat`), N5 (`change_in_working_capital`), N6 (`capital_expenditures`), N8 (direct `calculate_terminal_value`). Before: `pv_fcffs=nan tv=nan pv_tv=nan price=nan`. After: `ValueError: … for year 2029 …`, and N8 `ValueError: final_fcff (the terminal value's base cash flow) is NaN…` |
| 3 | NaN tax rate into `calculate_fcff_historical` stops, not `0.0` | **pass** | probe N10 (`tax_rate_override=nan`) and N11 (`effective_tax_rate` NaN because `tax_expense` is NaN). Before both: `tax_rate=0.0 after_tax_interest=10.0 fcff=115.0`. After both: `ValueError: tax_rate (tax_rate_override or income_statement.effective_tax_rate) is NaN…` |
| 4 | no existing assertion changed meaning | **pass** | `pytest -q` → `1 failed, 120 passed` both before and after. Failure **set** diffed, not counted: `diff` of the sorted `FAILED` lines → **identical**, the one entry being `tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`. Collected node sets diffed → **identical, 121 nodes** |
| 5 | a healthy path is byte-identical | **pass** | `diff <(grep -A1 CONTROL before) <(grep -A1 CONTROL after)` → **no output**. Nine controls, full `repr` precision. Figures below |
| 6 | lint unchanged | **pass** | `ruff check .` → `Found 5 errors`; codes `uniq -c` → `5 BLE001`, both before and after |
| 7 | types not worse | **pass** | line numbers stripped, sorted, `comm -13` **empty** and `comm -23` **empty**; `14 -> 14`. Set-identical, so trivially a strict subset |
| 8 | census did not rise | **pass** | the `rules.md` grep → **116** before, **116** after |

### Criterion 5 — the healthy figures, before and after

Identical to the last digit. These are the full control block, unchanged:

```
C1 run_dcf, 5 healthy years
   pv_fcffs=565.4263887417133 tv=2890.1639344262285 pv_tv=1913.2571765451426
   ev=2478.683565286856 net_debt=200.0 price=22.786835652868557
C2 run_dcf, 1 healthy year
   pv_fcffs=110.49723756906077 tv=2016.39344262295 pv_tv=1856.7158771850368
   ev=1967.2131147540977 net_debt=200.0 price=17.672131147540977
C3 discount_cash_flows healthy        565.4263887417133
C4 calculate_terminal_value healthy   3192.622950819672
C5 fcff_historical, rate from filing  tax_rate=0.25 after_tax_interest=7.5 fcff=112.5
C6 override 0.80 -> clamps to 0.50    tax_rate=0.5  after_tax_interest=5.0  fcff=110.0
C7 override -0.30 -> clamps to 0.0    tax_rate=0.0  after_tax_interest=10.0 fcff=115.0
C8 override 0.21                      tax_rate=0.21 after_tax_interest=7.9  fcff=112.9
C9 calculate_fcff_projected healthy   120.0
```

**C6 and C7 exist because the clamp is what I was editing around.** They prove the
clamp still clamps in both directions and that the new check did not displace it: an
out-of-range but *known* rate is still clamped, only an *unknown* one now stops.

The route gate also still returns 200:
`TestClient(app.app, raise_server_exceptions=False).get('/')` → **200**.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| guard inside `discount_cash_flows`' loop, naming `fcff.year` | assignment step 1; the reviewer's F4 asked for the year | naming only the field tells a reader one of five projections is bad without saying which. The year is already on the object |
| guard `final_fcff` inside `calculate_terminal_value`, not in `run_dcf` | it is a parameter of that function, and that function is **public and called directly** — probe N8 shows `calculate_terminal_value(nan, 0.025, 0.086)` returned `nan` before | a guard on `final_fcff` in `run_dcf` would be **dead code**: `discount_cash_flows` runs first at `dcf.py:133` over the whole list, last element included, so it can never fire. I was told not to write an unreachable guard |
| a local `_require_finite` in each of `dcf.py` and `fcff.py`, rather than importing `wacc.py`'s | assignment step 3 permits an `analysis/` → `analysis/` import but asks me to check it. The WACC message says "so WACC cannot be computed from it", which is false in both new homes | importing a `_`-prefixed private across sibling modules to then not use its message buys nothing. The *approach* is reused — same `math.isnan`, same signature `(value: float, field: str) -> None`, same "names the field, substitutes nothing" contract. The docstrings point at `analysis/wacc.py:_require_finite` so the three are findable as one pattern |
| bind `cash_flow = fcff.fcff` before the guard | `ProjectedFCFF.fcff` is a property over four fields; the guard and the sum must see the same value | re-reading the property would check one value and discount another. Float-identical for a healthy path — criterion 5 confirms no digit moved |
| `analysis/fcff.py` gets one guard, on the tax rate, and nothing else | assignment step 5 | item 23's other half (no `raise` for wholly empty statements) is a different backlog item |

**No change here was made to reach a target number.** Every healthy figure is
byte-identical by construction and by diff; the only figures that moved are the eleven
that were `nan` or a fabricated `0.0` and are now exceptions.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `ProjectedFCFF.fcff`, each projected year, in `discount_cash_flows` | **stops**, names `the projected FCFF for year <year>` | `analysis/dcf.py:97`; probe N1, N3, N4, N7, N9 |
| `ProjectedFCFF.fcff`, the final year | **stops**, names the year | `analysis/dcf.py:97` reached via `run_dcf:133`; probe N2, N5, N6 |
| `final_fcff` in `calculate_terminal_value` | **stops**, names `final_fcff (the terminal value's base cash flow)` | `analysis/dcf.py:66`; probe N8 |
| `tax_rate_override` / `income_statement.effective_tax_rate` in `calculate_fcff_historical` | **stops**, names both sources, **before** the clamp | `analysis/fcff.py:71-73` against the clamp at `:74`; probe N10, N11 |
| `wacc` inside `discount_cash_flows` | **defaults to nothing, but returns `nan` silently on a direct call** | see "What I did not do". Through `run_dcf` the chain still stops, at `calculate_terminal_value` (`dcf.py:67-68`), which `P4c-nan-stops` added |
| `financials.get_balance_sheet(latest_year)` | **defaults to `0.0` net debt and `0.0` cash** | `analysis/dcf.py:143-144` — **backlog item 2, pre-existing, untouched.** Its red test is required to stay red by criterion 4, and it does |

The last two rows are findings against the file, not against this unit's diff. Neither
line is in the diff (`git diff` shows nothing at either).

## Measurements

| Gate | Before (`eed4fe1`) | After |
|---|---|---|
| `pytest -q` | `1 failed, 120 passed` | `1 failed, 120 passed` |
| failure **set** | `{test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent}` | identical, by `diff` |
| collected node set | 121 | identical, by `diff` |
| `ruff check .` | `Found 5 errors`, `5 BLE001` | `Found 5 errors`, `5 BLE001` |
| mypy | 14 errors, 4 files | 14 errors, 4 files; `comm` both directions empty |
| census (`rules.md` grep) | 116 | 116 |
| `GET /` | — | **200** |

### Coverage fell, and here is exactly where

```
                before                      after
analysis/dcf.py    29 stmts  2 missed  93%    35 stmts  3 missed  91%   missing 35, 68, 124
analysis/fcff.py   19        0        100%    24        1         96%   missing 40
analysis/ TOTAL   226        6         97%   237        8         97%
```

**Exactly two statements are newly uncovered by the suite**, and both are the
`raise ValueError(` inside the new `_require_finite`:

- `analysis/dcf.py:35`
- `analysis/fcff.py:40`

`dcf.py:68` and `dcf.py:124` are the pre-existing raises that were at `:33` and `:82`
before my diff shifted them down; they were already uncovered at `eed4fe1`.

**Neither new raise is dead.** Running my probe alone under coverage reaches both:

```
COVERAGE_FILE=/c/tmp/p4d_cov_probe .venv/Scripts/python.exe -m coverage run --source=analysis c:/tmp/p4d_probe.py
analysis\dcf.py    35  3  91%   67, 74, 123     <- :35 covered
analysis\fcff.py   24  0 100%                   <- :40 covered
```

(The three still missing under the probe are the WACC/growth NaN raise, the
`wacc <= g` raise and the empty-`projected_fcffs` raise — all pre-existing, and the
middle one is covered by the suite.)

**I did not write an unreachable guard or restructure anything to hold the
percentage.** A tester needs at least four cases to close the gap honestly, because
statement coverage cannot tell the two `dcf.py` call sites apart once `:35` is green:
one per-year NaN naming the year, one final-year NaN, one direct
`calculate_terminal_value(nan, …)`, and one NaN tax rate into
`calculate_fcff_historical` asserting it **raises rather than returning
`tax_rate=0.0`**. That last assertion is the whole point of item 23b; a test that only
checks `tax_rate <= 0.50` would have passed against the defect.

### A caveat on the control figures

**My control inputs are invented literals, not a filing.** There is no PDF on this
machine (`STATUS.md` §3). C1's `price=22.786835652868557` is evidence about the code
path and is meaningless as a valuation. What it proves is the thing criterion 5 asks:
the arithmetic did not move.

## What I did not do

- **`discount_cash_flows`' `wacc` parameter is still unguarded.** Called directly,
  `discount_cash_flows(healthy_fcffs, nan)` returns `nan`. It is **not** a live hole
  through `run_dcf`: `discount_cash_flows` runs at `dcf.py:133` and
  `calculate_terminal_value` at `:137`, and the latter raises on a NaN WACC, so the run
  still stops — the reviewer of `P4c-nan-stops` confirmed that as its case R. I left it
  because the assignment scoped me to "guard each projected **cash flow**", and
  widening scope is itself a finding. See the findings below.
- **Item 2** (`analysis/dcf.py:143-144`, zero net debt) — untouched, red test still red.
- **Item 23's other half** — `analysis/fcff.py` still has no `raise` for wholly empty
  statements, and `calculate_fcff_projected` still has no guards. Out of scope by
  assignment step 5.
- **`tests/`** — not mine to write.
- **`STATUS.md`, the backlog and the journal index** — not mine to write. Items 30 and
  23b are closed by this diff and both are still listed as open.

## Findings for the orchestrator

1. **`analysis/dcf.py:discount_cash_flows` takes `wacc` and does not check it.** A
   direct call with a NaN WACC returns `nan` silently (probe would show it; I did not
   add the case because I was not going to fix it). Latent only — the `run_dcf` chain
   stops two lines later at `calculate_terminal_value`. One line to close, in the same
   shape as this unit's guards. Worth a backlog item, low cost.

2. **`analysis/fcff.py:calculate_fcff_projected` has no guards at all** — seven float
   parameters, any of which NaN produces a NaN `ProjectedFCFF`. This unit makes that
   safe *at the DCF boundary* (probe N9 stops, naming year 2028), but the stop happens
   one module later than the bad input arrived, so the year it names is the year of the
   bad projection and not the name of the bad assumption. Folding this into item 23
   would close it at the source.

3. **`models/valuation.py:138`** — `DCFResult.implied_share_price` is
   `self.equity_value / self.diluted_shares if self.diluted_shares else 0.0`. Zero
   shares outstanding renders a **share price of 0.0**, not an error. It is one of
   the 116, and it is the last line before the headline figure. Not my file.

4. **`config.DEFAULT_COST_OF_DEBT` is still unlabelled** (item 9) and `analysis/dcf.py`
   still shows no assumption trail in its result object (rule 6, rule 4). Unchanged by
   me; recorded because I read the whole of both files.
