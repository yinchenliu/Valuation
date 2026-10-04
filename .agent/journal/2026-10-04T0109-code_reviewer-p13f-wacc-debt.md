---
agent: code_reviewer
assignment: P13f-wacc-debt
round: 1
verdict: changes_requested
---

# Review of P13f-wacc-debt, round 1

Programmer entry: `.agent/journal/2026-10-04T0102-programmer-p13f-wacc-debt.md`

Measured on `scratchpad/p13f_reviewer/`: `base/` is `git archive f6da3e9`, and `mine/` is the same export with only `analysis/wacc.py` copied in. The edge-case script is `scratchpad/p13f_reviewer/rev.py`.

## The guard checks

Run over `analysis/wacc.py`.

| Check | Result |
|---|---|
| conditional zero | clean |
| `.get` with a fallback | clean |
| bare or-default | clean |
| `: float = 0.0` | clean |
| `**kwargs` | clean |
| `getattr(` | clean |
| dict of functions | clean |
| model client outside `ingestion/` (`models/ analysis/ api/`) | clean |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `balance_sheet` None | yes, with and without an override, and also on a direct call | `rev.py` C3 |
| `total_debt` NaN | yes | `wacc.py:91` |
| `total_debt` < 0, including -inf | yes | `rev.py` C1 and `-inf debt` |
| `total_debt` +inf | **no**: weights `0.0 / nan`, WACC `nan` | F2 |
| a negative debt line under a non-negative total | **no**: WACC 0.1316 | F3 |
| zero debt with interest, override supplied | stops (item 22) | `rev.py` C2 |
| `market_cap` +inf (orchestrator addition) | **no**: weights `nan / 0.0`, WACC `nan`, on both trees | F2 |

## Units and boundaries

| Check | Result |
|---|---|
| every figure in millions | no conversion is added or removed |
| percentages converted at the route boundary | not touched |
| falsy treated as missing | none added. `override is not None` and `balance_sheet is None` are used |
| `analysis/` imports | `math`, `config` and `models` only |

## Done-criteria, re-run

| # | Programmer claimed | I measured | Agree? |
|---|---|---|---|
| 1 | stops at (300, -50) | `ValueError: balance_sheet.total_debt is -50.00 ... A filing prints debt as a positive figure`. No cause is claimed. Base: `Ew 1.2 Dw -0.2` | yes |
| 2 | item 22 stops under an override | `ValueError: the balance sheet reports total debt of 0 while ... interest expense of 30.00`. Base: `Ew 1.0 Dw 0.0 WACC 0.1` | yes |
| 3 | `None` gives a named `ValueError` | `ValueError: balance_sheet is None ...` on both override states and on a direct `cost_of_debt_with_source`. Base: `AttributeError` | yes |
| 4 | (300, 100) unchanged | both trees: `Ew 0.75 Dw 0.25 Rd 0.2 WACC 0.11513157894736843`. With override 0.05: `0.08503289473684211` on both trees. My fixture differs from the programmer's, so the figures differ from theirs | yes |
| 5 | mypy 9 | `Found 9 errors in 4 files`. The diff against base removes only `api/routes_valuation.py:634 [arg-type]` | yes |
| 9 | no new red | full suite `2 failed, 793 passed` on both trees. The failure sets are identical by `diff` (the two `*_rule3_red.py`). The gate form gives `793 passed` | yes |
| 10 | gates not worse | ruff 5 / 5, mypy 10 → 9, census 65 / 65 | yes |

## Findings

### F1 — Step 2 turns item 22 into a dead end. No entry point accepts a debt balance · `major` (assignment defect, escalated)

**Evidence:**
- The new remedy at `analysis/wacc.py:185` is "supply the debt balance". No input can do that:
  - The CLI flags at `cli.py:142-156` carry no debt flag. `--cost-of-debt` is the only debt input.
  - The form at `api/routes_valuation.py:496-538` and the inputs in `templates/assumptions.html:138-239` carry no debt field. `cost_of_debt_override` is the only debt input.
  - Route B (`api/routes_upload.py:128`) takes a session JSON. A user could hand-edit the balance sheet in it. For backlog item 37's repaid-debt company, though, the filing prints a closing balance of 0, so a non-zero figure would be a balance-sheet number from somewhere other than the filing. That breaks rule 5.
- Item 37's lease case cannot pass either: `BalanceSheet` has no lease field.

**Answer to the orchestrator's question:**
- Yes, the stop now blocks a legitimate valuation with no way past.
- The old path was no real remedy either:
  - The override acted as an implicit "I confirm the zero" switch, and the supplied rate then reached nothing (debt weight 0).
  - For the repaid case the all-equity result was arguably right.
  - For the lease case it was wrong, and nothing said so.
- Rule 3 is met by the stop, so the assignment breaks no rule. The defect is that the stop removes the only remedy and puts nothing in its place.

**Recommendation (a decision for the orchestrator and the user, not for me):**
1. Keep the stop.
2. Add an explicit, typed confirmation primitive, for example a `zero_debt_confirmed: bool` argument with a `--confirm-zero-debt` flag and a form checkbox.
   - When set, item 22's case continues with a debt weight of 0.
   - `cost_of_debt_source` then states the confirmation and the interest figure (rule 6).
   - This needs `cli.py` and `api/` in scope, so it is a new unit. The alternative is to decide from `CashFlowStatement.debt_repaid` (`models/financial_statements.py:323`), as item 37 notes.
3. Until then, record the dead end as a known limitation, or hold step 2 back from this unit. Do not restore the override-as-confirmation.

Separately, the message tells the user to do something that no input supports. It should name what can actually be done, which is to re-extract or correct the extraction.

**Rule or document:** backlog items 37 and 38b. This is an assignment question, not a programmer error. The programmer reported it (its finding 2).

### F2 — An infinite debt balance passes the new guard, and an infinite market cap passes the old one · `major`

**Evidence:**
- `rev.py` on `mine/`, (300, +inf): `OK Ew 0.0 Dw nan Rd 0.0 WACC nan`.
- `rev.py`, (+inf, 100): `OK Ew nan Dw 0.0 WACC nan`. This is the same on `base/`, which confirms the P13d programmer's report.
- Cause: `_require_finite` tests only `math.isnan` (`wacc.py:40`). `_require_non_negative_debt` (`wacc.py:91-92`) adds `< 0`, so +inf passes.
- This unit wrote the debt read at `wacc.py:284`, so the debt half is this unit's.
- `analysis/dcf.py:116` later stops on a NaN `wacc`, but it names `wacc`, not the input.

**Rule or document:** rule 3. The stop does not name the field. A degenerate input yields a `WACCResult` that holds NaN.

**What would fix it:** test `not math.isfinite(value)` in `_require_finite`. That one line covers `market_cap`, `total_debt`, `cost_of_equity`, `cost_of_debt` and `tax_rate`. **Orchestrator addition:** fold the market-cap case into round 2 by amending the assignment, because the fix is the same line. Do not open a separate backlog item. It is not in `refactor-backlog.md` today.

### F3 — A negative debt line hides under a non-negative total · `major`

**Evidence:** `rev.py` on `mine/` with `short_term_debt` -50 and `long_term_debt` 100 gives `OK Ew 0.857 Dw 0.143 Rd 0.4 WACC 0.1316`. The programmer reported it (its finding 3).

**Rule or document:** rule 3, as the assignment applies it to item 69. The Pass 1 prompt makes each line positive, so a negative line is the same bad value as a negative total. The assignment scoped step 1 to `total_debt`. The rule beats the scope, so the orchestrator widens it.

**What would fix it:** in `_require_non_negative_debt`, check each of the three lines and name the negative one.

### F4 — A NaN interest expense now reaches item 22's message as if it were a reported figure · `minor`

**Evidence:** `rev.py`, zero debt, NaN interest, override 0.05, on `mine/`: `ValueError: ... reports interest expense of nan ... A company that pays interest has debt`. On base this stopped at the `tax_rate` NaN guard. The stop is correct. The message is not, because `nan != 0` is True at `wacc.py:154`.

**What would fix it:** call `_require_finite(income_statement.interest_expense, "income_statement.interest_expense")` before line 154.

### F5 — Zero debt, zero interest and an override still return the supplied rate with a weight of 0 · `note`

**Evidence:** `rev.py`, `X debt-free ovr`: `Ew 1.0 Dw 0.0 Rd 0.05`, the same on both trees. The moved override return still comes before the debt-free branch. The WACC is right. The page shows a "supplied" rate that reaches nothing. This is item 38's second face, the part that is not item 22.

## Pre-existing — not findings against this unit

| Item | `file:line` | Touched? |
|---|---|---|
| 37: the "did not extract" inference | `wacc.py:174-181` | the text was kept and only the remedy clause changed. Excluded by the assignment |
| `cli.py:1043` `latest_bs.total_debt if latest_bs else 0` (programmer finding 1) | `cli.py:1043` | no. **Not in the backlog** (`grep "latest_bs else" refactor-backlog.md` matches only the closed `dcf.py` lines). The orchestrator should record it |
| route error path | `api/routes_valuation.py:703-708` renders `str(e)` | no. The named `ValueError` now reaches the page, which is better than the old `AttributeError` |

## Verdict

`changes_requested`. F2 and F3 are rule 3 majors in the function this unit wrote, and each is a few lines in `analysis/wacc.py`. F1 is an assignment defect. The orchestrator must decide it, with the user, before step 2 is accepted: either add a confirmation primitive in a new unit or record the dead end as accepted. The code itself, on criteria 1 to 10, is correct and measured as claimed.
