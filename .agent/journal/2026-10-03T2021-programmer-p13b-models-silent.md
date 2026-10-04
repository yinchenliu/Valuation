---
agent: programmer
assignment: P13b-models-silent
round: 1
status: complete
files_touched: [models/financial_statements.py, models/valuation.py, analysis/dcf.py, analysis/projector.py]
---

# P13b-models-silent — stop on no latest year and no share count; required confidence; truncation label

## What I did

Four absences that read as measurements now either stop or are labelled.
`FinancialStatements.latest_year` raises `ValueError` ("holds no income statements, so
there is no latest year") in place of returning `0` (item 15). `run_dcf` stops before
it discounts anything when `diluted_shares` is not a finite number greater than zero, and
`DCFResult.implied_share_price` raises in place of returning `0.0` (item 32).
`NonRecurringItem.confidence` is a required field with no default (item 39). A new
`ASSUMPTION_TRUNCATED_CLAUSE_TEMPLATE` beside the pad template is appended to the growth
label by `derive_assumptions` when a supplied list is longer than `projection_years`
(item 42). Rule 3 for the first three, rule 6 for the fourth. Nothing outside the four
files in scope was edited.

## Starting facts (assignment table, re-measured before any edit)

All ten agreed. `latest_year` at `models/financial_statements.py:370-371`;
`implied_share_price` at `models/valuation.py:337-338`; `confidence: str = "high"` at
`:35`; `run_dcf` names `diluted_shares` only at `:157, :168, :218`; one constructor at
`ingestion/claude_extractor.py:1484`, **and it passes `confidence=item["confidence"]`**
(read at lines 1484-1494), so step 3 did not need to stop; pad clause only at
`analysis/projector.py:166-186`. Census 67. Baseline full suite at the shared tree before
any edit (no code file modified by anyone yet): `2 failed, 724 passed` — the two
`*_rule3_red.py` tests.

## Done-criteria

Script: `/private/tmp/claude-501/.../scratchpad/dc.py`, run as
`PYTHONPATH=. .venv/bin/python <scratch>/dc.py` from the repo root.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | no statements, no latest year | pass | `FinancialStatements(ticker="X").latest_year` → `ValueError: FinancialStatements for 'X' holds no income statements, so there is no latest year. Extract at least one year of the filing; year 0 is not substituted.` |
| 2 | `run_dcf` stops on no share count | pass | `run_dcf(..., diluted_shares=0.0)` → `ValueError: diluted_shares is 0.0: the DCF needs a finite diluted share count greater than zero, ...`; `-5.0` → `diluted_shares is -5.0: ...`; `nan` → `diluted_shares is nan: ...`; also `inf` → `diluted_shares is inf: ...` |
| 3 | the property stops on no share count | pass | `DCFResult(..., diluted_shares=0, noncontrolling_interest=0.0, ...).implied_share_price` → `ValueError: diluted_shares is 0, so there is no implied share price: ...` |
| 4 | a positive share count keeps its price | pass | (a) `run_dcf` with FCFF 100, 100, WACC 0.25, g 0.05, net debt 100-30=70, NCI 0, 10 shares: EV 144+336=480, equity 480-70=410, price by hand 410/10 = **41.0**; code returned `41.0`. (b) direct `DCFResult(pv_fcffs=100, pv_terminal_value=400, net_debt=50, NCI=0, diluted_shares=9)`: by hand (100+400-50-0)/9 = **50.0**; code returned `50.0` |
| 5 | `confidence` is required | pass | `NonRecurringItem(year=2025, description="d", amount=1.0, line_item="sga", direction="add_back", category="other", source="Note 1")` → `TypeError: NonRecurringItem.__init__() missing 1 required positional argument: 'confidence'`. With `confidence="low"` it builds and reads `'low'` |
| 6 | a cut growth list is labelled | pass | `derive_assumptions(f, ProjectionAssumptions(projection_years=2, revenue_growth_rates=[0.1,0.2,0.3,0.4,0.5]))` → rates `[0.1, 0.2]`, label ends `5 rate(s) were supplied and the projection runs 2 year(s), so only the first 2 were used and the last 3 were DROPPED. The dropped rates reach no figure in this valuation.` |
| 7 | a list of the right length gets no clause | pass | same call with `[0.1, 0.2]` → rates `[0.1, 0.2]`, label is the supplied sentence alone, no clause. (Also `[0.1]` → `[0.1, 0.1]` with the pad clause only, no truncation clause.) |
| 8 | Walmart is unchanged, stages 2 to 5 | pass | old tree = `git archive 0021845` into scratch `old/` with `extractions/WMT.json` copied in (gitignored); no `git stash`. `.venv/bin/python cli.py --session-file extractions/WMT.json` on both, exit 0 both. Stages `[2/10]` to before `[6/10]` extracted with awk, `(Ns elapsed)` stripped: 125 lines each, `diff` empty, both `shasum b7a4be71caa0727ea43166db46fd1b05d257a260`. Stage 6 also identical. Stage 10 on the new tree: equity 224,757M / diluted shares 8,022M (the FY2026 "Dil. Shares" line read from the filing, stage 2 line 59) = 28.017, printed `$28.02` — a price reached from a filing share count through the new guard |
| 9 | the suite fails only where expected | pass (every red test named below) | full suite in the shared tree: `31 failed, 695 passed`; gate form: `29 failed, 695 passed`. Isolated tree (0021845 + only my four files): `30 failed, 696 passed`; set difference against 0021845 = exactly 28 tests, all `TypeError: ... missing 1 required positional argument: 'confidence'`. See Measurements |
| 10 | the gates do not get worse | pass | ruff: `Found 5 errors` (the four files alone: `All checks passed!`); mypy exact gate command: `Found 10 errors in 4 files (checked 20 source files)`; census `65` (was 67; the two removed lines are listed below). Same three figures in the isolated tree and the shared tree |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `implied_share_price` also refuses non-finite counts, not only `<= 0` | `equity / inf` returns `0.0`, the same silent zero item 32 removes; `nan > 0` is False so NaN is refused either way. Same reasoning as `analysis/dcf.py:_require_finite` | The assignment says "not greater than zero" for the property; refusing infinity is a superset and keeps the property and `run_dcf` on one rule |
| `run_dcf` share check placed after the empty-FCFF check and before `discount_cash_flows` | Assignment step 2: "stops before it discounts anything" | Placing it beside the balance-sheet check (after discounting) would compute PVs for a run that cannot finish |
| Message for `latest_year` names the ticker | Rule 3: name the field; the ticker tells the reader which extraction was empty | A message without the ticker is the same on every route |
| Truncation clause is a separate `if` after the pad `if` | Pad and truncation exclude each other (shorter vs longer list); the comment above the clause templates now says so | One combined branch would mix two clauses with different arguments |
| `confidence` kept positional in field order (no `kw_only`) | It follows `category`, which has no default, and `source: str = ""` follows it, so dataclass field order is valid; the one live constructor passes keywords | `kw_only` would also work but changes more than the assignment asks |

No change was made to reach a target number. Walmart's stages 2 to 6 are byte-identical
to `0021845`.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `FinancialStatements.years` in `latest_year` | stops and names "no income statements, so there is no latest year" with the ticker | DC1 |
| `diluted_shares` in `run_dcf` | stops and names `diluted_shares` and its value (0, negative, NaN, inf) | DC2 |
| `DCFResult.diluted_shares` in `implied_share_price` | stops and names `diluted_shares` | DC3. **Note:** the field itself still **defaults to `0.0`** (`diluted_shares: float = 0.0`, backlog item 1, not this unit) — the property now stops on that default instead of printing 0.0 |
| `NonRecurringItem.confidence` | `TypeError` at construction | DC5 |
| `rates_before_padding` / `len(rev_growth)` in the truncation clause | both are lengths of lists in hand; no absent case | `analysis/projector.py` truncation block |
| `DCFResult.current_price` in `upside_downside` (not changed, read by the same result) | **defaults to `0.0` and `upside_downside` returns `0.0`** | pre-existing, outside the assignment; see Findings |

## Measurements

**Suite, as failure sets.**

- `0021845` (scratch `old/`): `2 failed, 724 passed` — `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`.
- `0021845` + my four files only (scratch `mine/`): `30 failed, 696 passed` = the 2 above + **28 caused by this unit**, every one `TypeError: NonRecurringItem.__init__() missing 1 required positional argument: 'confidence'` (item 39, step 5 of the assignment anticipated it). Tests that build a `NonRecurringItem` without `confidence`:
  - `tests/unit/test_normalizer.py` — 26 tests, all through the builder at `tests/unit/test_normalizer.py:84` (no `confidence=`): `test_add_back_lowers_the_expense_field_and_raises_ebit_and_margin`, `test_remove_raises_the_expense_field_and_lowers_ebit_and_margin`, `test_the_ebit_move_equals_the_items_own_declared_adjusted_impact`, `test_a_research_and_development_label_moves_rd_expense_and_nothing_else`, `test_a_cost_of_goods_label_lands_on_cost_of_revenue`, `test_a_selling_general_label_lands_on_sga`, `test_label_matching_ignores_case_and_surrounding_whitespace`, `test_two_add_backs_on_one_field_accumulate`, `test_opposite_directions_on_one_field_net_off`, `test_two_items_on_different_fields_both_apply`, `test_an_item_is_applied_to_its_own_year_only`, `test_normalize_financials_does_not_mutate_its_input`, `test_normalize_financials_leaves_the_other_statements_alone`, `test_sign_cost_of_revenue_add_back_raises_pre_tax_earnings`, `test_sign_cost_of_revenue_remove_lowers_pre_tax_earnings`, `test_sign_sga_add_back_raises_pre_tax_earnings`, `test_sign_sga_remove_lowers_pre_tax_earnings`, `test_sign_rd_expense_add_back_raises_pre_tax_earnings`, `test_sign_rd_expense_remove_lowers_pre_tax_earnings`, `test_sign_depreciation_amortization_add_back_raises_pre_tax_earnings`, `test_sign_depreciation_amortization_remove_lowers_pre_tax_earnings`, `test_sign_other_operating_expense_add_back_raises_pre_tax_earnings`, `test_sign_other_operating_expense_remove_lowers_pre_tax_earnings`, `test_sign_other_non_operating_add_back_raises_pre_tax_earnings`, `test_sign_other_non_operating_remove_lowers_pre_tax_earnings`, `test_sign_a_non_operating_item_leaves_every_operating_line_untouched`.
  - `tests/unit/test_normalizer_stops.py` — 2 tests, direct constructors at `:78` and `:114` with no `confidence=`: `test_an_unrecognised_line_item_stops_the_run`, `test_an_unrecognised_direction_stops_the_run`.
  - Repair for the tester: pass `confidence="high"` (or the value the test means) in those constructors.
- Shared tree (all three P13 units' uncommitted work): `31 failed, 695 passed` = the 30 above + `tests/unit/test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`, `ValueError: market_cap is 0.00 and balance_sheet.total_debt is 0.00 ... They are not set to an all-equity 1.0 / 0.0.` That message is from `analysis/wacc.py` (P13a's file) and the test is green in the isolated tree with my four files, so it is **not** caused by this unit.
- Gate form (`--ignore-glob="*_rule3_red.py"`): shared tree `29 failed, 695 passed`; isolated tree 28 failed.
- No test asserting the old label text turned red: `tests/unit/test_projector.py::test_a_long_growth_list_is_truncated_to_the_projection_horizon` asserts only the rates and stays green.
- No test reaches `implied_share_price` or `run_dcf` with a zero share count, and none reaches `latest_year` on empty statements (the projector red test fails on the revenue `IndexError` before `latest_year` is read, unchanged).

**Census, removed lines** (`diff` of the grep output, 0021845 vs isolated tree):
`models/financial_statements.py: return max(self.years) if self.years else 0` and
`models/valuation.py: return self.equity_value / self.diluted_shares if self.diluted_shares else 0.0`. 67 → 65.

**Callers of `latest_year`** (step 1). None catches the error and turns it into a default:
- `analysis/projector.py:322` (`project_fcffs`) and `analysis/dcf.py:194+` (`run_dcf`): no `try`.
- `api/routes_valuation.py:619`: inside the `try` of `run_valuation`; the blanket `except Exception` (backlog item 8) renders `str(e)` as the page error with `dcf=None`. It reports the message, it does not substitute a year.
- `cli.py:458` and `:1032-1033`: no local handler; the only catch is `__main__`'s `except Exception` at `cli.py:1143`, which prints `ERROR: <message>` and exits 1.
- `templates/_statements.html:295`: **no route can render it with empty statements today.** It is guarded by `{% if financials %}` (line 2), and an empty `FinancialStatements` is truthy, so the guard alone would not stop it. But on `assumptions.html:249` it is included only `if not error and financials`, and `derive_assumptions` on empty statements raises (the bare `IndexError`, `test_projector_rule3_red.py`) before the page is built, so `error` is set. On `valuation_result.html:249` it sits in the `{% elif dcf %}` branch, and `dcf` exists only if `derive_assumptions` and `run_dcf` succeeded — both stop on empty statements. If the template were ever rendered with empty statements, Jinja's attribute lookup does not swallow `ValueError` (only `AttributeError`), so the page would raise, not show a year 0.

## What I did not do

- Did not edit `tests/`, `api/`, `cli.py`, `templates/`, `ingestion/`, `docs/`.
- Did not touch `diluted_shares: float = 0.0` (item 1), the `else 0.05` at `analysis/projector.py:169` (item 41), the projector `IndexError` (red test), or item 31.
- The assignment mentions "about 40 assertions" in `models/valuation.py`. `grep -n assert models/valuation.py` finds none (one comment hit, line ~165); my change touches no assertion there.

## Findings for the orchestrator

1. **`DCFResult.upside_downside` returns `0.0` when `current_price == 0`** (`models/valuation.py`, the property after `current_price: float = 0.0`). A missing market price shows "0.0% upside", which reads as "fairly valued". Same shape as item 32, not in the backlog (`grep -i upside docs/9-reference/refactor-backlog.md` → nothing). Measured: a `DCFResult` with default `current_price` → `upside_downside == 0.0`.
2. **`derive_assumptions` mutates the caller's growth list.** `analysis/projector.py`: `rev_growth = ov.revenue_growth_rates` aliases the list and the pad loop `append`s to it. Measured: `rates=[0.1]`, `projection_years=3` → after the call `rates == [0.1, 0.1, 0.1]`. A second call with the same `ProjectionAssumptions` would then see three "supplied" rates and lose the pad clause, so the label would call the platform's repeats the caller's figures (rule 6). Pre-existing at `0021845`; not in the backlog. Fix is one `list(...)` copy.
3. **Effect on item 44's path.** When the filing gives no share count and yfinance has no `sharesOutstanding`, `api/routes_valuation.py:628` computes `0 / 1e6 = 0.0` and `cli.py:1039` does the same (after `cli.py:1035` set `0` for no income statement). Before this unit that reached a displayed price of `$0.00`; now `run_dcf` stops with `diluted_shares is 0.0: ...`, rendered as the page error on the web route and as `ERROR:` on the CLI.
