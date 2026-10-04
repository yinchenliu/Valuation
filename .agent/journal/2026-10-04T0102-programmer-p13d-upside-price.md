---
agent: programmer
assignment: P13d-upside-price
round: 1
status: complete
files_touched: [models/valuation.py, analysis/dcf.py]
verdict:
---

# P13d-upside-price — stop on no current price instead of reporting 0% upside

> Second run of this unit. The first run (`2026-10-03T2110-programmer-p13d-upside-price.md`)
> stopped at an account usage limit before it changed anything. That entry is left as it is.

## What I did

`run_dcf` (`analysis/dcf.py`) now stops before it discounts anything when `current_price`
is not a finite number greater than zero. The check runs directly after the existing
`diluted_shares` check and uses the same test, `math.isfinite(x) and x > 0`. The
`ValueError` names `current_price` and its value. It says that the price is market data
(the last close from the price series), not a filing figure, and that the upside is not
reported as 0%. The `Args` docstring line for `current_price` says the same thing.
`DCFResult.upside_downside` (`models/valuation.py`) loses `if self.current_price == 0:
return 0.0` and raises a `ValueError` that names `current_price`, with the same test. This
is the guard `P13b` put on `implied_share_price` for `diluted_shares`. Backlog item 65.

## Done-criteria

All measured on the isolated tree
`scratchpad/p13d_programmer/new` (`git archive 19298f3` plus only my two files), against
`scratchpad/p13d_programmer/base` (`git archive 19298f3` unchanged). The script is
`scratchpad/p13d_programmer/c.py`, run as `PYTHONPATH=. .venv/bin/python c.py` in each tree.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | `run_dcf` stops on no price | **pass** | new tree: `ValueError: current_price is 0.0: …`, `… is -5.0`, `… is nan`, `… is inf`, each `names current_price: True`. Base tree: all four `NO STOP`. Each price was also run with a NaN FCFF and no balance sheet, and the error still names `current_price` and not the FCFF or the balance sheet. This shows that the stop comes before discounting and before the bridge. |
| 2 | the property stops on no price | **pass** | `DCFResult(..., current_price=0.0, ...)`: new tree `ValueError: current_price is 0.0, so there is no upside or downside …`. Also -5.0, nan and inf, and the field omitted (it defaults to 0.0), all `names current_price: True`. Base tree returned `0.0`, `-400.0`, `nan`, `-100.0` and `0.0`. |
| 3 | a positive price keeps its upside | **pass** | Hand case through `run_dcf`: WACC 20%, g 0, one year of FCFF 120. PV FCFF 120/1.2 = 100. TV 120/0.2 = 600, PV 600/1.2 = 500. EV = 600. Net debt 150 − 50 = 100. NCI 20 + 30 = 50. Equity 450. Price 450/18 = 25.0. With a current price of 20: (25/20 − 1) × 100 = **25.0%**. Measured: `implied 25.0 upside 25.0` in both trees. Second case, built directly: EV 1000 − 250 − 150 = 600, / 40 = 15.0. With a current price of 20: (15/20 − 1) × 100 = **−25.0%**. Measured: `upside -25.0` in both trees. |
| 4 | the census does not rise | **does not rise, but 65, not 64 as the assignment expected** | The census grep reads **65** on both trees. The sets are identical: `diff census_base.txt census_new.txt` shows only `terminal_growth_rate` moving from line 381 to 397, and `routes_upload.py:115` in a different grep order. **The removed site was never in the census.** The regex `if [^)]+ else 0(\.0)?\b` matches only a one-line conditional. `if self.current_price == 0:` / `return 0.0` is two lines and has no `else`, so the grep never counted it. The only census hit in this property's area is `models/valuation.py:366 current_price: float = 0.0`, a dataclass zero default. That is backlog item 1, which this unit is told not to fix. Removing that default would also need the field reordered, because fields with defaults come before it. I did not change code to reach 64. |
| 9 | the suite fails only where expected | **pass: no test turned red** | Full suite, new tree: `2 failed, 793 passed`. The failures are `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`, the same two as on the base tree. Gate form: `793 passed` on both trees. |
| 10 | the gates do not get worse | **pass** | ruff `Found 5 errors.`, all 5 `BLE001` (same as base). mypy `Found 10 errors in 4 files (checked 20 source files)` (same as base). Census 65 (same as base). |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The `run_dcf` check goes after `diluted_shares` and before `wacc_result.wacc` is read | Step 1: "stops before it discounts anything" | It runs before `discount_cash_flows` and before the balance sheet read, so a bad price is reported even when other inputs are also bad. Criterion 1, second row of each price, shows this. |
| `math.isfinite(x) and x > 0`, in that order | Step 2: "the same test as step 1, as `P13b` did for `diluted_shares`" | `<= 0` lets NaN through. Infinity would give −100% in the property, from a price nobody observed. |
| The message says "market data … not a filing figure" in both places | Rule 5, step 1 | The property can be reached without `run_dcf`, so it carries its own label. |
| `current_price: float = 0.0` left in place | The assignment: "Item 1: the zero-default fields" is not this unit's work | The property now refuses that default when it is read, so the default no longer reaches a displayed figure. |
| No caller edited | Step 3: "Do not edit those callers" | — |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `run_dcf(current_price=…)` | stops and names `current_price` (0, negative, nan, inf) | `analysis/dcf.py:195-207` (the new block); criterion 1 |
| `DCFResult.current_price` in `upside_downside` | stops and names `current_price` (0, negative, nan, inf, field omitted) | `models/valuation.py:381-388`; criterion 2 |
| `DCFResult.current_price` as a field | **defaults to `0.0`** when a caller omits it (`models/valuation.py:366`) | Backlog item 1, out of scope. The default no longer reaches the upside figure: reading it raises. |
| `implied_share_price` in `upside_downside` | stops and names `diluted_shares` (P13b, unchanged) | `models/valuation.py:357-362` |

## Callers of `upside_downside` (step 3)

`grep -rn upside_downside api cli.py templates analysis models` finds:

- `cli.py:792,794` (`print_dcf_result`) and `cli.py:1088-1089` (the final summary). They
  read the property on the `run_dcf` result. **No catch** converts the error to a value.
  Only `__main__` at `cli.py:1143` catches `Exception`, and it prints `ERROR: …` and exits 1.
- `templates/valuation_result.html:18,37,39`. Only inside `{% elif dcf %}`, where `dcf` is
  the `run_dcf` result. The route's `except Exception` (`api/routes_valuation.py:703`)
  renders `error: str(e)` with `dcf: None`. That shows the error and does not default the
  figure. Its `"current_price": 0` sits beside `dcf: None` and an error message, so the
  page shows no upside built from it.

**Which callers can now raise where they did not.** Both live paths compute
`market_cap = price * shares` and call `calculate_wacc` before `run_dcf`. I ran
`calculate_wacc` with `market_cap = price × 18`
(`scratchpad/p13d_programmer/w.py`). Price 0 stops (`market_cap is 0.00, which is not greater
than 0`), -5 stops, and nan stops. **Infinity does not stop**. WACC returns
`equity_weight nan, debt_weight 0.0, wacc nan`. So on the web route and the CLI, **an
infinite price now stops in `run_dcf`**, naming `current_price`, where before it went on
with a NaN WACC. A zero, negative or NaN price already stopped earlier, in WACC, and still
does. The one remaining path is a `DCFResult` built directly without a price that then reads
`upside_downside`. No production code builds one: `analysis/dcf.py` is the only
`DCFResult(` in the code. In `tests/unit/test_dcf.py`, the two direct builders (lines 611
and 827, the second with `current_price=0.0`) read only `implied_share_price`, and they
stay green.

## Measurements

| Gate | Base (`19298f3`, isolated) | New (isolated) |
|---|---|---|
| full suite | 2 failed / 793 passed: the two `*_rule3_red.py` | the same set |
| gate form | 793 passed | 793 passed |
| ruff | 5, all BLE001 | 5, all BLE001 |
| mypy (exact command) | 10 errors in 4 files | 10 errors in 4 files |
| census | 65 | 65 (identical set, see criterion 4) |

Every fact in the assignment's "already true" table matched at the start: 793 / 2+793 /
5 BLE001 / 10 in 4 / 65 / `sed -n 369,373p` / `current_price` at dcf.py 156, 167, 233.

`git diff --stat 19298f3 -- models/valuation.py analysis/dcf.py`: 2 files, +36 −4. I
touched no other file.

## What I did not do

- Item 1 (`current_price: float = 0.0` and the other zero defaults): out of scope by name.
- No test written or edited. The tester owns `tests/`. The tester will want tests for
  criteria 1 to 3. No existing test locks the old 0.0 behaviour.

## Findings for the orchestrator

1. **Criterion 4's expected value was wrong. The census cannot see this site.** The rule
   3 grep matches only one-line conditionals. The two-line `if x == 0:` / `return 0.0`
   form, the shape of item 65, is invisible to it. So the census undercounts silent
   zeros, and removing one of them does not move it. Proposal: either add a multi-line
   pattern to the census in `docs/2-rules/rules.md`, or state there that the census counts
   one-line forms only.
2. **`analysis/wacc.py` does not stop on an infinite `market_cap`.** `_require_finite`
   tests `math.isnan` only. `market_cap=inf` gives `equity_weight=nan` and `wacc=nan` with
   no exception. Reproduce with `calculate_wacc(..., market_cap=math.inf, ...)` →
   `nan 0.0 nan`. `run_dcf` now stops on the infinite price one step later, so this
   cannot reach a share price on the two live paths. A direct call to `calculate_wacc`
   still returns NaN. It is in `P13f-wacc-debt`'s file, so I did not touch it.
