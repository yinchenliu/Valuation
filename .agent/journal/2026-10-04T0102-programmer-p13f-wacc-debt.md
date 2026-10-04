---
agent: programmer
assignment: P13f-wacc-debt
round: 1
status: complete
files_touched: [analysis/wacc.py]
verdict:
---

# P13f-wacc-debt — stop on negative debt, on no balance sheet, and on interest with no debt under an override

## What I did

I changed only `analysis/wacc.py`. I added two guards: `_require_balance_sheet` and
`_require_non_negative_debt`. `cost_of_debt_with_source` now runs four steps in this order:

1. Stop on `balance_sheet=None` (item 38b (b)).
2. Stop on a `total_debt` that is NaN or below 0 (item 69).
3. Run item 22's interest-against-zero-debt stop.
4. Only then return a supplied override (item 38b (a)).

`calculate_wacc` and `cost_of_debt_with_source` now take `BalanceSheet | None`. The
None guard returns a narrowed `BalanceSheet` to `calculate_wacc`. `calculate_wacc` gets
its debt weight from the same `_require_non_negative_debt`, so the weights cannot use a
value the check did not see. This change also removes the mypy error at
`api/routes_valuation.py:634`. I did not edit `api/`.

The isolated trees are under
`/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/5a3eb59a-dd70-43de-8ee8-c16bbd7dd61e/scratchpad/p13f_programmer/`:
- `base/` is `git archive 19298f3`.
- `mine/` is `base/` with only `analysis/wacc.py` copied in.
- `crit.py` is the script for criteria 1 to 4.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | negative debt stops | **pass** | `crit.py` on `mine/`, (300, -50): `ValueError : balance_sheet.total_debt is -50.00 (year 2025; short_term_debt 0.00 + current_portion_lt_debt 0.00 + long_term_debt -50.00), which is below 0. A filing prints debt as a positive figure, ...`. The message gives no cause, and it is the same with and without override 0.05. Base: `OK Ew 1.2 Dw -0.2 Rd -0.4 WACC 0.18` |
| 2 | interest with no debt stops under an override | **pass** | Market cap 300, every debt line 0, interest 30, override 0.05. `mine/` gives `ValueError : the balance sheet reports total debt of 0 while the income statement reports interest expense of 30.00 for 2025. ...` (item 22's stop). Base: `OK Ew 1.0 Dw 0.0 Rd 0.05 WACC 0.1` |
| 3 | no balance sheet stops by name | **pass** | `calculate_wacc(..., balance_sheet=None, ...)` gives `ValueError : balance_sheet is None, so the debt balance ... cannot be read.` with and without override 0.05. Base: `AttributeError : 'NoneType' object has no attribute 'total_debt'` both times. A direct call `cost_of_debt_with_source(IS, None, 0.05)` also gives `ValueError balance_sheet is None ...` |
| 4 | a normal case keeps its result | **pass** | (300, 100), interest 20, tax 75 / EBT 300. Both trees: `Ew 0.75 Dw 0.25 Rd 0.2 WACC 0.11250000000000002`. With override 0.05, both trees: `WACC 0.084375`. Hand check: 0.75 x 0.10 + 0.25 x 0.20 x 0.75 = 0.075 + 0.0375 = 0.1125, and 0.075 + 0.25 x 0.05 x 0.75 = 0.084375 |
| 5 | mypy does not rise | **pass, 9** | `mypy ... --ignore-missing-imports` on `mine/`: `Found 9 errors in 4 files (checked 20 source files)`. `diff` against base: the only removed line is `api/routes_valuation.py:634: error: Argument "balance_sheet" to "calculate_wacc" has incompatible type "BalanceSheet \| None"` |
| 9 | the suite fails only where expected | **pass, no new red** | Full suite on `mine/`: `2 failed, 793 passed`. The failure set is the same as on base: `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`, both red on purpose. Gate form: `793 passed` |
| 10 | the gates do not get worse | **pass** | ruff `Found 5 errors.` (base 5). `ruff check analysis/wacc.py`: `All checks passed!` mypy 9 (base 10). Census grep with `'--include=*.py'`: `65` (base 65) |

The "What is already true" baseline matched on `base/`: 793 / 2+793 / ruff 5 / mypy 10
in 4 / census 65 / the `:634` arg-type error. Nothing disagreed.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The negative-debt check sits in `cost_of_debt_with_source`, not only in `calculate_wacc` | With no override, base computes Rd = 20 / -50 = -0.4 (criterion 1, base row). That is a second silent figure from the same bad value, and `calculate_cost_of_debt` reaches it too | A check only in `calculate_wacc` would leave the negative rate open on a direct call |
| The NaN check comes before the `< 0` comparison in `_require_non_negative_debt` | `nan < 0` is False, so a comparison alone passes NaN (this module's own `_require_finite` docstring) | `test_a_nan_total_debt_stops_and_names_the_balance_sheet_field` stays green. The field named is still `balance_sheet.total_debt` |
| Item 22's remedy clause "or supply a cost of debt explicitly with --cost-of-debt if the zero is correct" is replaced by "whether or not a cost of debt is supplied: supply the debt balance" | After 38b (a), that advice is false: supplying `--cost-of-debt` no longer passes the stop. A message that tells the user to do something that cannot work misleads them | I did not touch the "has debt ... did not extract" inference. That is item 37, which is excluded. I changed only the one clause my change made false |
| The None message gives `income_statement.year` as "the income statement supplied with it" | It states what the function received. It does not guess why the balance sheet is absent (item 37 spirit) | Saying "no balance sheet for year X was extracted" would be an inference about the caller |
| `calculate_cost_of_debt` stays `BalanceSheet` | The assignment names only `calculate_wacc` and `cost_of_debt_with_source`. No caller passes None to it | A wider signature with no caller is scope widening |
| I did not check each debt component for a negative value | The assignment says to stop when `total_debt` is below zero. A component check would be new behaviour | Listed under Findings |

No change was made to reach a target number.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `balance_sheet` (None) | stops and names `balance_sheet` | criterion 3, both override states |
| `balance_sheet.total_debt` NaN | stops and names `balance_sheet.total_debt` | `_require_non_negative_debt`; `test_a_nan_total_debt_...` green |
| `balance_sheet.total_debt` < 0 | stops and names `balance_sheet.total_debt` and its value | criterion 1 |
| `total_debt` == 0 with interest != 0, with or without an override | stops (item 22) | criterion 2; `test_the_contradiction_stops_calculate_wacc_too` green |
| `income_statement.interest_expense` NaN, debt > 0, override supplied | **not read into any figure.** The override is returned and interest is unused on that path | by reading the code: unchanged behaviour, outside this unit |
| `income_statement.interest_expense` NaN, no override | stops at `_require_finite(cost_of_debt, "cost_of_debt")`. It names the derived rate, not the interest field | unchanged from base |
| `market_cap` NaN / <= 0 / sum 0 | stops (unchanged, P13a) | suite green |

No "defaults to" row comes from this unit.

## Measurements

| Gate | base `19298f3` | mine |
|---|---|---|
| full suite | 2 failed, 793 passed | 2 failed, 793 passed (same failure set) |
| gate form | 793 passed | 793 passed |
| ruff | 5 (BLE001) | 5 |
| mypy | 10 in 4 files | **9 in 4 files** (`routes_valuation.py:634` gone) |
| census | 65 | 65 |

Figures this unit moved, with the inputs from `crit.py`:
- (300, -50): `WACC 0.18` / `0.1125` becomes a stop.
- Zero debt, interest 30, override 0.05: `WACC 0.1` becomes a stop.
- `balance_sheet=None`: `AttributeError` becomes a named `ValueError`.
- (300, 100): unchanged.

Tests that turned red: **none**.

## What I did not do

- Item 37 (the inference in the zero-debt message). Excluded.
- Item 22's logic beyond its ordering. Excluded.
- Item 1's sites. Excluded.
- `api/` and `cli.py`: not in scope, not edited.

## Findings for the orchestrator

1. **`cli.py:1043`: `total_debt = latest_bs.total_debt if latest_bs else 0`.**
   - This is a rule 3 conditional zero (a presence test with a zero branch).
   - `cli.py:1035` has the same pattern for `shares`.
   - The census grep does not count either one, because `cli.py` is outside `models analysis api ingestion`.
   - The `calculate_wacc` call two lines later now stops on `latest_bs=None`, so the zero no longer reaches WACC on that path. Whether it reaches a printed line I did not check.
2. **Item 37's repaid-debt case now has no escape path.** Before this unit, a company that repaid all its debt before the balance sheet date could pass item 22's stop with `--cost-of-debt`. Now nothing passes the stop except a non-zero debt balance. 38b (a) asks for this. The orchestrator may want to say so when it closes item 37.
3. **A negative individual debt line can still hide behind a non-negative total.** Example: `short_term_debt` -50 with `long_term_debt` 100 gives `total_debt` 50, which passes. The Pass 1 prompt (`ingestion/claude_extractor.py:305`, "All values must be POSITIVE") makes each line a bad value when it is negative. A per-component check would be a separate assignment.
4. **The route's `except Exception` at `api/routes_valuation.py:703` now receives the named `ValueError`.** Before, it received the `AttributeError`. I did not check what that handler renders.
