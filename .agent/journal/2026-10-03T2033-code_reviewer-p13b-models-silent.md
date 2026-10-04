---
agent: code_reviewer
assignment: P13b-models-silent
round: 1
verdict: approved
---

# Review of P13b-models-silent, round 1

Programmer entry: `.agent/journal/2026-10-03T2021-programmer-p13b-models-silent.md`

Measured in an isolated tree: `git archive 0021845` into scratch, plus only this unit's four
files (`diff -rq` against a second clean export shows exactly those four `.py` files). The
shared tree was not stashed or modified.

## The guard checks

Run over the four files in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | 9 hits, **none in a diff line**: `models/valuation.py:238,242`, `models/financial_statements.py:67,91,111,118`, `analysis/projector.py:73,170,287`. All are census lines under backlog item 1; `:170` is item 41 |
| lookup with a fallback — `.get(k, 0)` | clean |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | 51 hits, none in a diff line. Item 1. `DCFResult.diluted_shares: float = 0.0` (`models/valuation.py:325`) is item 1 and the assignment excludes it; the programmer names it in its rule 3 table |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (`models/ analysis/ api/`) |

The unit **removed** two census lines and added none. The diff of the census grep output,
`0021845` against the isolated tree: `models/financial_statements.py: return max(self.years) if self.years else 0`
and `models/valuation.py: return self.equity_value / self.diluted_shares if self.diluted_shares else 0.0`. 67 → 65.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `FinancialStatements.years` in `latest_year` | yes. `ValueError` with the ticker: "holds no income statements, so there is no latest year" | DC1 below |
| `diluted_shares` in `run_dcf` | yes, for `0`, `0.0`, `-5.0`, `nan`, `inf`, `-inf`. Message names `diluted_shares` and its value. It sits after the empty-FCFF check and before `discount_cash_flows` (`analysis/dcf.py:185`), so nothing is discounted | DC2 |
| `diluted_shares` = `None` in `run_dcf` | stops with `TypeError: must be real number, not NoneType`, which does not name the field. Not a finding: the parameter is typed `float`, the mypy gate enforces it, and both callers (`api/routes_valuation.py:624-628`, `cli.py:1035-1039`) produce a float or raise earlier | `python -c`, run below |
| `DCFResult.diluted_shares` in `implied_share_price` | yes, for 0, negative, NaN, inf, and the field default `0.0` | DC3 |
| `NonRecurringItem.confidence` | `TypeError` at construction. The one live constructor (`ingestion/claude_extractor.py:1484-1494` at `0021845`) passes `confidence=item["confidence"]`. No `**dict` or other construction path in `ingestion/`, `api/`, `cli.py` | DC5; `grep -rn "NonRecurringItem("` |
| `rates_before_padding`, `len(rev_growth)` in the truncation clause | lengths of lists in hand. No absent case. See F1 for the negative-`projection_years` case | `analysis/projector.py:192-201` |

**Callers of `latest_year`**, re-read: `analysis/dcf.py:208`, `analysis/projector.py:322`,
`api/routes_valuation.py:619`, `cli.py:458`, `cli.py:1032-1033`, `templates/_statements.html:295`.
None catches the error and returns a year. The route's blanket `except Exception` (item 8)
shows the message as the page error. The CLI's `__main__` handler prints `ERROR:`. One
behaviour change the entry does not state, and it is correct: an empty extraction on the
CLI now stops at stage 2 (`print_extracted_financials`, `cli.py:458`). Before, it printed
`FY0` and "No balance sheet extracted." and failed later.

**`upside_downside`** (`models/valuation.py:369-373`) reads `implied_share_price`. With zero
shares and a non-zero price it now raises (measured below). Before, it returned −100%. That
is better, not worse. The `current_price == 0 → 0.0` branch is unchanged by this diff. The
programmer reported it, and the orchestrator is adding it to the backlog.

**The inf extension in `implied_share_price`** (orchestrator's question). I accept it. A
finite numerator divided by `inf` gives `0.0`, which is the silent zero item 32 removes.
`run_dcf` was already told to refuse a count that is "not a finite number" (step 2), so the
extension puts the property and the function on one predicate. It is the same function and
the same file, and the docstring gives the reason. It is not a scope breach and it does not
widen any rule.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | no figure crosses a unit boundary in this diff. Walmart's 8,022 (millions, read from the filing) reaches the guard and passes |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing | the new code tests `isfinite(x) and x > 0` and compares lengths. No new `if x` |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | holds. `models/valuation.py` adds only `import math` (standard library) |

## Done-criteria, re-run

Script `scratchpad/rv13b/dc.py`, run with `PYTHONPATH=.` in the isolated tree.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | no statements, no latest year | ValueError | `ValueError: FinancialStatements for 'X' holds no income statements, so there is no latest year. ...` | yes |
| 2 | `run_dcf` stops on no share count | 0, −5, nan (and inf) | `diluted_shares is 0.0: ...`, `is 0`, `is -5.0`, `is nan`, `is inf`, `is -inf`. All are ValueError and all name the field | yes |
| 3 | the property stops | ValueError | `diluted_shares is 0, so there is no implied share price ...`. Also refused: 0.0, −1.0, nan, inf, and the field default | yes |
| 4 | positive count keeps its price | 41.0 and 50.0 | My own case: FCFF 100, 100, WACC 0.20 (all equity), g 0. PV FCFF = 83.333 + 69.444 = 152.778. TV = 100/0.20 = 500. PV TV = 500/1.44 = 347.222. EV = 500.0. Net debt = 120 − 20 = 100. NCI = 10. Equity = 390. With 13 shares, 390/13 = **30.0**, and the code returned `30.0`. Upside at price 50: (30/50 − 1) × 100 = −40.0, and the code returned `-40.0`. Direct `DCFResult` (100 + 400 − 50)/9 = `50.0`, which matches | yes |
| 5 | `confidence` required | TypeError | `TypeError: NonRecurringItem.__init__() missing 1 required positional argument: 'confidence'`. With `confidence="low"` it returns `'low'` | yes |
| 6 | cut list labelled | 5/2/3 | rates `[0.1, 0.2]`. Label ends `5 rate(s) were supplied and the projection runs 2 year(s), so only the first 2 were used and the last 3 were DROPPED. The dropped rates reach no figure in this valuation.` | yes |
| 7 | right length, no clause | none | `[0.1, 0.2]` with n=2 gives the supplied sentence alone. `[0.1]` with n=3 gives the pad clause only. The derived branch gives no clause | yes |
| 8 | Walmart unchanged, stages 2–5 | identical | Both trees exit 0. Stages 2–5: 125 lines each, `diff` empty, both `shasum b7a4be71caa0727ea43166db46fd1b05d257a260`. Stage 6 is also identical. Stage 10 is `$28.02` on both | yes |
| 9 | suite fails only where expected | 28 named | Isolated: `30 failed, 696 passed`. At `0021845`: `2 failed, 724 passed`. **Set difference = 28 tests**: 26 in `test_normalizer.py` and 2 in `test_normalizer_stops.py`. Every one is `TypeError: ... missing 1 required positional argument: 'confidence'`, and the names match the entry's list. 0 tests left the failure set. Shared tree: `31 failed, 695 passed`. The extra test is `test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`, which is P13a's and green in the isolated tree | yes |
| 10 | gates not worse | ruff 5, mypy 10, census 65 | ruff `Found 5 errors` on both trees, and the four files alone give `All checks passed!`. mypy (exact gate command): `Found 10 errors in 4 files` on both trees, and the **error sets are identical**. Census 67 → 65 | yes |

## Findings

### F1 — a non-positive `projection_years` makes the new clause state a projection length that did not run · `minor`

**Evidence:** `derive_assumptions(h, ProjectionAssumptions(projection_years=-1, revenue_growth_rates=[0.1,0.2,0.3,0.4,0.5]))`
gives rates `[0.1, 0.2, 0.3, 0.4]` and a label ending "the projection runs 4 year(s), so
only the first 4 were used". `project_fcffs` then builds **0** years. The clause is fed
`projection_years=len(rev_growth)` (`analysis/projector.py:198`), and `rev_growth[:-1]`
slices from the end.
**Rule or document:** none broken. The sentence is false, but only on a path that always
stops before the label is read. `run_dcf` raises "projected_fcffs is empty". On the web
route the label is read at `api/routes_valuation.py:670`, after `run_dcf` at `:644`. The
CLI never prints the label (see O1). The root cause predates this unit: `projection_years`
is never validated, and the old code labelled the same 4-rate list "supplied".
**What would fix it:** `derive_assumptions` stops when `ov.projection_years < 1` and names
the field. This belongs in the backlog. It does not have to be fixed in this unit.

## Observation for the orchestrator — not a finding against this unit

**O1. The CLI prints no `AssumptionSource` at all.** `cli.py:677-695` (`print_assumptions`)
prints the rates and an `(override)` tag. It never prints
`assumptions["sources"][...].detail`. On the CLI, therefore, neither the new truncation
clause, the pad clause, nor any `SUBSTITUTED` label is visible. Measured:
`cli.py --session-file extractions/WMT.json --projection-years 2 --revenue-growth 0.03,0.04,0.05,0.06,0.07`
prints `Revenue growth (per yr): ['3.0%', '4.0%'] (override)` and no word that three
rates were dropped. The web route does render the clause (`templates/assumptions.html:53`).
This is a rule 6 gap on the CLI. It is older than this unit and wider than item 42: it
covers every label `P8a` added. It is in a file this assignment forbade, and this diff did
not touch it. I found no record of it in `docs/9-reference/refactor-backlog.md`
(`grep -n -i "print_assumptions\|AssumptionSource"`). It should be recorded.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 (zero-default fields, census) | `models/valuation.py:162-163, 314-325, 366`; `models/financial_statements.py` money fields and the four ratio properties; `analysis/projector.py:73, 287` | no |
| 41 (`else 0.05`) | `analysis/projector.py:170` | no. It is the line above the new block, unchanged |
| 8 (blanket `except Exception`) | `api/routes_valuation.py`, `cli.py:1143`: they display the new `ValueError`s | no |
| 44 (yfinance share count) | `api/routes_valuation.py:624-628`, `cli.py:1035-1039`: a missing yfinance count now reaches the new stop rather than `$0.00` | no |
| new, being recorded by the orchestrator | `models/valuation.py:371-372` (`upside_downside` 0.0 on zero price); `analysis/projector.py:158` alias + `:170` append (caller's list mutated) | no. Neither is made worse: truncation slices a copy, and the pad mutation never lengthens a list past `projection_years`, so no truncation clause can appear on a second call |

The assignment's "about 40 assertions" in `models/valuation.py`: `grep -c assert` → 1, a
comment at `:174`. The diff touches no assertion. This agrees with the programmer.

## Verdict

`approved`

All ten done-criteria reproduce by execution in an isolated tree. The 28 new red tests are
exactly the anticipated `confidence` constructors, compared as failure sets. Walmart's
stages 2–6 are byte-identical. The gates hold: ruff 5, the same 10 mypy errors, and the
census falls 67 → 65. The inf refusal in `implied_share_price` is justified and in scope. No
`blocker` or `major` finding stands. F1 is `minor`: a label that is false only on an input
that always stops before display. O1 is a pre-existing CLI gap for the backlog. The tester
repairs the 28 constructors.
