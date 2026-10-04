---
agent: code_reviewer
assignment: P13f-wacc-debt
round: 2
verdict: approved
---

# Review of P13f-wacc-debt, round 2

Programmer entry: `.agent/journal/2026-10-04T0111-programmer-p13f-wacc-debt-r2.md`. Round 1 review: `.agent/journal/2026-10-04T0109-code_reviewer-p13f-wacc-debt.md`. Assignment: the "Round 2 amendment" in `.agent/assignments/P13f-wacc-debt.md`.

Measured on `scratchpad/p13f_reviewer/mine2/`: `git archive f6da3e9` with only `analysis/wacc.py` copied in. The baseline is `scratchpad/p13f_reviewer/base/`, and the script is `scratchpad/p13f_reviewer/rev2.py`. The diff I reviewed is `git diff f6da3e9 -- analysis/wacc.py`.

## The guard checks

Run over `analysis/wacc.py`.

| Check | Result |
|---|---|
| conditional zero / `.get` fallback / bare or-default / `: float = 0.0` | clean |
| `**kwargs` / `getattr(` / dict of functions | clean. `_require_valid_debt:95-99` is a tuple of (name, number) pairs, and every pair gets the same two checks. Rule 2 allows a lookup of numbers. The programmer answered this |
| model client outside `ingestion/` | clean |

## Rule 3, by reading

| Value | Stops and names it? | Evidence (`rev2.py` on `mine2/`) |
|---|---|---|
| `balance_sheet` None | yes, with and without an override, and on a direct call | C3 |
| each debt line NaN / ±inf | yes, names `balance_sheet.<line>` | F2 debt ±inf, F3 nan line |
| each debt line < 0, even under a positive total | yes, names every negative line | F3, three cases |
| `total_debt` inf from two finite lines | yes | `F2 lines sum inf` |
| `market_cap`, `cost_of_equity`, `cost_of_debt`, `tax_rate` inf | yes, each by name | F2. On base: `WACC nan`, `inf`, `inf`, and `0.1` (the clamp hid it) |
| `interest_expense` NaN / inf, no override | yes, before item 22's comparison | F4, three cases |
| zero debt + interest + override | returns the override with a weight of 0 | C2. This was restored on the amendment's order, and the user decides F1. **Not counted against the unit**, as instructed |

## Done-criteria, re-run

| # | Programmer claimed | I measured | Agree? |
|---|---|---|---|
| step 2 withdrawn | override block and item 22 to the end are identical to `f6da3e9` | a Python text comparison of both blocks against `base/`: `override identical: True`, `item22..end identical: True`. `git diff` shows no hunk in either block | yes |
| 1 | (300, -50) stops, no cause | `ValueError: balance_sheet.long_term_debt is below 0. balance_sheet.total_debt is -50.00 ...`, the same with an override. Base: `Ew 1.2 Dw -0.2` | yes |
| 2 (amended) | returns as at `f6da3e9` | both trees: `Ew 1.0 Dw 0.0 Rd 0.05 WACC 0.1`. Without the override, both give the identical item 22 stop | yes |
| 3 | None stops by name | `ValueError: balance_sheet is None ...` in all three call forms. Base: `AttributeError` | yes |
| 4 | (300, 100) unchanged | both trees: `WACC 0.11513157894736843`, and `0.08503289473684211` with an override | yes |
| F2 | 8 inf cases stop by name | all 8 stop by name on `mine2/`. All 8 are silent on base | yes |
| F3 | each line checked | ST -50 / LT 100, CP -10 / LT 100 with an override, and two negative lines all stop. `-0.0` passes, which is correct | yes |
| F4 | NaN interest stops before item 22 | `income_statement.interest_expense is nan` with zero debt and with debt 100. Inf interest also stops. Base printed "interest expense of nan" | yes |
| 5 | mypy 9 | `Found 9 errors in 4 files`. The diff against base removes only `routes_valuation.py:634 [arg-type]` | yes |
| 9 | 0 red | `2 failed, 793 passed`. The failure set is identical to base by `diff` (the two `*_rule3_red.py`). The gate form gives `793 passed` | yes |
| 10 | gates not worse | ruff 5, mypy 9, census 65 | yes |

One fixture difference: with zero debt, NaN interest and an override, my fixture stops at `tax_rate is nan`, because my effective tax rate is formed through interest. The programmer's fixture returns `Rd 0.05`. Both results are consistent with the restored path, which never reads interest.

## Findings

### F1 — The multi-line message is ungrammatical · `note`

**Evidence:** `analysis/wacc.py:123` prints `balance_sheet.short_term_debt, balance_sheet.current_portion_lt_debt is below 0.` (`rev2.py`, `F3 two neg lines`).
**What would fix it:** use "are below 0" when there is more than one name. No rule is involved.

### F2 — The assignment's done-criteria table still states the withdrawn criterion 2 · `note`

**Evidence:** `.agent/assignments/P13f-wacc-debt.md:95` still says "interest with no debt stops under an override", while the amendment says criterion 2 now expects the `f6da3e9` behaviour. The amendment's new F2–F4 criteria were not added as rows either. I measured against the amendment text. The tester should do the same, or the orchestrator should correct the table.

## Earlier findings

| # | Outcome | Note |
|---|---|---|
| F1 (step 2 dead end) | withdrawn | The amendment withdrew step 2, and the code is restored byte for byte. Item 38b (a) is open for the user |
| F2 (inf passes) | fixed | `wacc.py:47` uses `math.isfinite`. 8 cases stop by name |
| F3 (negative line hidden) | fixed | `_require_valid_debt`, `wacc.py:83-129` |
| F4 (NaN interest in item 22's message) | fixed | `wacc.py:192`, placed after the override return, as at base |
| F5 (debt-free + override) | withdrawn | Restored behaviour that is part of the user's F1 decision. Not counted, as instructed |

## Pre-existing — not findings against this unit

| Item | `file:line` | Touched? |
|---|---|---|
| 37: the inference in item 22's message | `wacc.py`, item 22 block | no. Byte-identical to base |
| 38b (a): override before item 22 | `wacc.py:181` | no. Restored by order, awaiting the user |
| `cli.py:1035` / `:1043` conditional zeros | `cli.py` | no. Still not in the backlog. The orchestrator should record them |

## Verdict

`approved`. Every round 1 finding is fixed or withdrawn on the amendment's order. Every criterion re-measured as claimed. The two notes break no rule.
