---
agent: programmer
assignment: P13f-wacc-debt
round: 2
status: complete
files_touched: [analysis/wacc.py]
verdict:
---

# P13f-wacc-debt round 2: withdraw step 2, refuse inf, check each debt line, check interest is finite

Review: `.agent/journal/2026-10-04T0109-code_reviewer-p13f-wacc-debt.md`. Round 1 entry:
`.agent/journal/2026-10-04T0102-programmer-p13f-wacc-debt.md`. Amendment: "Round 2
amendment" in `.agent/assignments/P13f-wacc-debt.md`.

## What I did

I rebuilt `analysis/wacc.py` from `git show f6da3e9:analysis/wacc.py`, not on top of round 1, so
nothing withdrawn could leak through. On top of that text I made these changes:

- **`_require_finite`** now uses `math.isfinite` instead of `math.isnan` (F2).
- **`_require_balance_sheet`** is kept from round 1 (item 38b (b)).
- **`_require_valid_debt`** replaces `_require_non_negative_debt`. It checks each of the three debt lines and the total for finiteness, then each line for a negative value (item 69 and F3).
- **Interest expense** must be finite before item 22's comparison (F4).
- **Signatures:** `calculate_wacc` and `cost_of_debt_with_source` take `BalanceSheet | None`, and narrow it by reassignment from `_require_balance_sheet`.

The override return and item 22's block (code and message) are the `f6da3e9` text,
byte for byte. The isolated trees are under
`/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/5a3eb59a-dd70-43de-8ee8-c16bbd7dd61e/scratchpad/p13f_programmer/`:
- `base/` is `git archive 19298f3`. `git diff --stat 19298f3 f6da3e9 -- '*.py'` is empty, so it is the same code as `f6da3e9`.
- `mine2/` is `base/` plus only the new `analysis/wacc.py`.
- `crit2.py` is the criteria script.

## Answers to the review, by number

**F1 (step 2 is a dead end): withdrawn, as the amendment orders.**
- The order inside `cost_of_debt_with_source` is now:
  1. the `balance_sheet` None guard
  2. the debt-line guard
  3. `if override is not None: return ...` (the `f6da3e9` text)
  4. item 22's block (the `f6da3e9` text)
- The comparison script prints `override block identical: True` and
  `item 22 to end of function identical: True`, comparing against `wacc_f6.py`.
- Criterion 2 on `mine2/`: `OK Ew 1.0 Dw 0.0 Rd 0.05 WACC 0.1`, the same as base.
- The message again ends with "...or supply a cost of debt explicitly with --cost-of-debt if the zero is correct." (C2b).
- Item 38b (a) stays open for the user's decision.
- The None and debt-line guards still run **before** the override return. They are steps 1 and 3 of the assignment, which are not withdrawn. Criterion 3 requires the None stop under an override. A bad debt balance would reach the weights in `calculate_wacc` whatever the rate.

**F2 (inf passes): fixed.** `_require_finite` tests `not math.isfinite(value)`. The message now prints the value ("is inf, which is not a finite number"). The cases below were all silent on base and all stop on `mine2/`, each naming its field:
- `long_term_debt` +inf, with and without an override (base: `Dw nan WACC nan`)
- `long_term_debt` -inf
- `market_cap` +inf (base: `Ew nan WACC nan`)
- `capm_result.cost_of_equity` inf (base: `WACC inf`)
- `cost_of_debt` override inf (base: `WACC inf`)
- `tax_rate` override inf. Base clamped it to 0.50 and returned `WACC 0.1`.
- two finite lines of 1e308 that sum to inf. This stops as `balance_sheet.total_debt (year 2025) is inf`.

**F3 (a negative line under a non-negative total): fixed.** `_require_valid_debt` checks each line. Every negative line is named, and the total is printed with its three lines.
- `short_term_debt` -50 with `long_term_debt` 100 gives `ValueError : balance_sheet.short_term_debt is below 0. balance_sheet.total_debt is 50.00 (...)`. Base: `WACC 0.12857`.
- `current_portion_lt_debt` -10 with an override is also named. Base: `WACC 0.0856`.
- A NaN line now names the line (`balance_sheet.short_term_debt (a line of balance_sheet.total_debt, year 2025) is nan`). On base the stop named the derived `cost_of_debt`.

**F4 (NaN interest printed as reported): fixed.** `_require_finite(income_statement.interest_expense, "income_statement.interest_expense")` runs right before `interest = abs(...)`, so it runs before item 22's `interest != 0`.
- Zero debt with NaN interest and no override: `ValueError : income_statement.interest_expense is nan, ...`. Base printed "interest expense of nan" inside item 22's message.
- On the override path interest is not read at all (the `f6da3e9` order), so zero debt + NaN interest + override returns `Rd 0.05, Dw 0.0` on both trees. The rate reaches nothing, because the debt weight is 0. I did not add a new stop on the restored path.

**F5 (debt-free + override returns the supplied rate with a weight of 0): acknowledged, no change.**
- It is the same on both trees (`F5 debt-free ovr: OK Ew 1.0 Dw 0.0 Rd 0.05 WACC 0.1`).
- It is part of the override-ordering question that F1 hands to the user.

## Done-criteria

| # | Criterion | Result | Evidence (`crit2.py`) |
|---|---|---|---|
| 1 | negative debt stops, names `balance_sheet.total_debt` and -50, no cause | **pass** | (300, -50): `ValueError : balance_sheet.long_term_debt is below 0. balance_sheet.total_debt is -50.00 (year 2025; ...)`. Same with override 0.05. Base: `Ew 1.2 Dw -0.2` |
| 2 | (amended) override + zero debt lines + interest 30 returns as at `f6da3e9` | **pass** | `mine2/` and base both give `OK Ew 1.0 Dw 0.0 Rd 0.05 WACC 0.1`. Without the override both stop with the identical item 22 message (C2b) |
| 3 | no balance sheet stops by name | **pass** | `ValueError : balance_sheet is None, ...` with and without an override, and on a direct `cost_of_debt_with_source`. Base: `AttributeError` |
| 4 | (300, 100) unchanged | **pass** | Both trees: `Ew 0.75 Dw 0.25 Rd 0.2 WACC 0.11250000000000002`. With override: `0.084375` |
| F2 | an infinite input stops by name | **pass** | See F2 above: 8 cases, each a named `ValueError` on `mine2/`, each silent on base |
| F3 | a negative line under a non-negative total stops by name | **pass** | `short_term_debt` -50 / `long_term_debt` 100 and `current_portion_lt_debt` -10 / 100, both named |
| F4 | NaN interest stops before item 22 | **pass** | `income_statement.interest_expense is nan` on zero debt and on debt 100. It is not printed as a reported figure |
| 5 | mypy does not rise | **pass, 9** | `Found 9 errors in 4 files`. The diff against base removes only `api/routes_valuation.py:634 [arg-type]` |
| 9 | suite fails only where expected | **pass, no red** | Full suite: `2 failed, 793 passed`, the same two `*_rule3_red.py` tests as base. Gate form: `793 passed` |
| 10 | gates not worse | **pass** | ruff `Found 5 errors.` (base 5). `ruff check analysis/wacc.py`: `All checks passed!` mypy 9 (base 10). Census 65 (base 65) |

**Tests that turned red: none.**

`test_a_nan_total_debt_stops_and_names_the_balance_sheet_field` (`match="total_debt"`)
stays green. A NaN line's message names both `balance_sheet.long_term_debt` and "a line of
balance_sheet.total_debt", because the reader needs both: which printed line is bad, and
which total it feeds.

## Decisions, each with its reason

| Decision | Reason | Alternative rejected |
|---|---|---|
| Rebuild from `f6da3e9`, not revert hunks of round 1 | "exactly as at `f6da3e9`" is then provable by comparing the text (True / True above) | Hand-reverting could leave a stray edit |
| None and debt-line guards stay before the override return | Steps 1 and 3 are kept. Criterion 3 asks for the None stop under an override. The weights read the debt balance whatever the rate | Putting them after the override would make criterion 3 fail |
| The interest finite check goes after the override return | F4 asks for it "before item 22's comparison". At `f6da3e9` the override path never reads interest, so putting it there would add a new stop to a path the amendment says to restore | Before the override would change the restored path |
| Every negative line is named, not only the first | One message then lists everything the user must correct | Stopping at the first would hide the second |
| The (name, value) tuple loop in `_require_valid_debt` | It holds numbers, not functions, so rule 2 allows it | — |

No change was made to reach a target number.

## Rule 3 — what stops, and what does not

| Value read | If missing / bad | Evidence |
|---|---|---|
| `balance_sheet` None | stops, names `balance_sheet` | C3 |
| each debt line NaN / ±inf | stops, names `balance_sheet.<line>` | F2, F3 nan line |
| each debt line < 0 | stops, names each negative line and the total | C1, F3 |
| `total_debt` ±inf from finite lines | stops, names `balance_sheet.total_debt` | `F2 lines sum to inf` |
| `interest_expense` NaN / inf, no override | stops, names `income_statement.interest_expense` | F4 |
| `interest_expense` NaN, override supplied | **not read** (the `f6da3e9` path). The rate reaches nothing when debt is 0. When debt > 0 the override is used and interest is not | F4 ovr row, the same on both trees |
| zero debt + interest + override | **returns the override with weight 0** (the `f6da3e9` behaviour, item 38b (a) open per F1) | C2 |
| `market_cap`, `cost_of_equity`, `cost_of_debt`, `tax_rate` NaN / inf | stops by name | F2 |

The two bold rows are behaviour the amendment ordered restored. They are not new defaults.

## Measurements

| Gate | base | `mine2/` |
|---|---|---|
| full suite | 2 failed, 793 passed | 2 failed, 793 passed (same set) |
| gate form | 793 passed | 793 passed |
| ruff | 5 | 5 |
| mypy | 10 in 4 | 9 in 4 |
| census | 65 | 65 |

## What I did not do

- Item 38b (a) is withdrawn and stays open.
- Item 37 is excluded.
- F5 is acknowledged, with no change.
- I did not edit `api/` or `cli.py`.

## Findings for the orchestrator

1. **The round 1 finding about `cli.py:1035` / `:1043` stands.** The reviewer confirms it is not in the backlog. These are conditional zeros, `latest_bs.total_debt if latest_bs else 0` and `shares` likewise, outside the census directories.
2. **When the user decides item 38b (a), F4's override row and F5 fall out of the same decision.** Both are the override returning before the debt-balance consistency checks.
