---
agent: code_reviewer
assignment: P13d-upside-price
round: 1
verdict: approved
---

# Review of P13d-upside-price, round 1

Programmer entry: `.agent/journal/2026-10-04T0102-programmer-p13d-upside-price.md`
(the empty `2026-10-03T2110` entry is an interrupted earlier run, ignored).

Measured on `scratchpad/p13d_reviewer/new` (`git archive f6da3e9` plus only
`models/valuation.py` and `analysis/dcf.py` from the working tree) against
`scratchpad/p13d_reviewer/base` (`git archive f6da3e9` unchanged). Diff: 2 files,
+36 −4; hunks at `analysis/dcf.py:167`, `:195-208`, `models/valuation.py:370-388`.

## Orchestrator decision, recorded

Criterion 4 expected the census to fall to 64. The orchestrator recorded on 2026-10-04
that this expectation was its own error: the census grep matches only one-line
conditionals, so it never counted the two-line `if self.current_price == 0: return 0.0`.
Criterion 4's 65 is not counted against the unit. I confirmed the conditional zero is
gone: `models/valuation.py:370-388` in the new tree has no `return 0.0`, and the
property raises for 0, −3, nan and inf (criterion 2 below).

## The guard checks

Run over `models/valuation.py` and `analysis/dcf.py`.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | hits at `models/valuation.py:238,242` — pre-existing, outside the diff (item 1) |
| lookup with a fallback — `.get(k, 0)` | clean |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | 9 hits in `models/valuation.py` (162-163, 314-316, 323-325, 366), same 10-line set as base; none in a changed line. Line 366 `current_price: float = 0.0` is item 1, out of scope by name; the programmer answered it |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (`models/ analysis/ api/`) |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `run_dcf(current_price)` | yes, 0 / −0.01 / nan / inf / −inf, before discounting and before the bridge | new tree: each price with a NaN FCFF and no balance sheet still raises `current_price is …` |
| `DCFResult.current_price` read by `upside_downside` | yes | `models/valuation.py:381-388`; criterion 2 |
| `None` as a price | stops with `TypeError: must be real number`, not naming the field | not reachable: `PriceData.current_price: float` (`ingestion/price_fetcher.py:23`), set by `float(...)` at `:85`; mypy gate checks callers. Not a finding |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | no figure crosses a unit boundary; the price is per share and is only compared |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing | the old `== 0` test is replaced by `isfinite and > 0`; no new `if x` |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | `analysis/dcf.py` imports `math`, `models.*` only |

## Callers (step 3), re-read

`cli.py:792,794,1088-1089` and `templates/valuation_result.html:18,37,39` read the
property only on a `run_dcf` result, which now stops first. No caller catches and
defaults: `cli.py` `__main__` prints the error and exits; the route's `except Exception`
renders `dcf: None` with the message. Only `analysis/dcf.py:237` builds a `DCFResult`
in production code. Agrees with the programmer.

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | `run_dcf` stops on no price | ValueError naming `current_price` for 0, −5, nan, inf | my script: 0.0, −0.01, nan, inf, −inf each raise, message names `current_price` and says "market data"; base: all `NO STOP` | yes |
| 2 | property stops | ValueError naming `current_price` | `DCFResult(current_price=0.0 / −3 / nan / inf)` each raise naming it; base returned 0.0, −766.7, nan, −100.0 | yes |
| 3 | positive price keeps upside | 25.0% and −25.0% | own hand case: WACC 10%, g 0, FCFF 110 → PV 100, TV 1100 → PV 1000, EV 1100, net debt 200 − 100 = 100, equity 1000, /50 = 20.0. Price 16 → (20/16 − 1)×100 = **25.0**; price 25 → **−20.0**. Measured 24.99999999999998 and −20.000000000000018, both trees | yes |
| 4 | census | 65, identical set | 65 both trees; sorted sets with line numbers stripped are identical (`diff` empty). Expectation of 64 withdrawn by the orchestrator, see above | yes |
| 9 | suite fails only where expected | 2 failed / 793 passed, same two | failure sets compared, not counts: both trees fail exactly `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`; gate form 793 passed both | yes |
| 10 | gates not worse | ruff 5, mypy 10 in 4, census 65 | ruff `Found 5 errors.`, 5 × BLE001 both; mypy `Found 10 errors in 4 files (checked 20 source files)` both, error lists identical; census 65 | yes |

## Findings

### F1 — The rule 3 census cannot see a multi-line conditional zero · `note`

**Evidence:** census reads 65 in base and new while the unit removed
`if self.current_price == 0:` / `return 0.0` (base `models/valuation.py:370-372`).
**Rule or document:** none broken by this unit; the census grep in
`docs/2-rules/rules.md` undercounts. Already raised as the programmer's finding 1 and
acknowledged by the orchestrator.
**What would fix it:** the orchestrator adds a multi-line pattern to the census or
states in `rules.md` that it counts one-line forms only.

### F2 — No test yet locks the two new stops · `note`

**Evidence:** `tests/unit/test_dcf.py:324` asserts only the positive case (105.0); no
test passes a non-positive or non-finite price.
**Rule or document:** none; the tester owns `tests/`.
**What would fix it:** the tester adds tests for criteria 1-3.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 (zero-default fields) | `models/valuation.py:162-163, 314-316, 323-325, 366` | no |
| 1 (conditional zeros) | `models/valuation.py:238, 242` | no |
| 31 (`discount_cash_flows` wacc unguarded on a direct call) | `analysis/dcf.py` | no |

The programmer's finding 2 (`calculate_wacc` returns NaN on an infinite `market_cap`)
is in `analysis/wacc.py`, `P13f`'s file, and is outside this review.

## Verdict

`approved`

The conditional zero is gone, both paths stop on a price that is not a finite number
above zero and name `current_price` with a market-data label, a positive price keeps
its upside on an independent hand case, and the failure sets, ruff, mypy and census are
identical to `f6da3e9`. No file outside scope was written. F1 and F2 are notes and break
no rule.
