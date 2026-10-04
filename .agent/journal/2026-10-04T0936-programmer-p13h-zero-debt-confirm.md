---
agent: programmer
assignment: P13h-zero-debt-confirm
round: 1
status: complete
files_touched: [analysis/wacc.py, models/valuation.py, cli.py, api/routes_valuation.py, templates/assumptions.html]
---

# P13h-zero-debt-confirm — an explicit "confirm zero debt" choice replaces the cost-of-debt bypass

## What I did

I added `zero_debt_confirmed: bool = False` as a keyword-only parameter to
`cost_of_debt_with_source`, `calculate_cost_of_debt` and `calculate_wacc` in
`analysis/wacc.py`. I rebuilt `cost_of_debt_with_source` on the assignment's table.
`_require_balance_sheet` and `_require_valid_debt` still run first, in the same order.
After them, a confirmation beside a debt balance above 0 stops (new
`_require_no_confirmation_against_debt`). On every total-debt-0 path, with or without
an override, `_require_finite(interest_expense)` runs first. Then item 22's stop fires
unless the user confirmed the zero, so an override no longer gets past it. The
confirmed and override rows return the labels the table asks for. The debt-above-0
paths without a confirmation are byte-identical to before (the supplied-rate label is
now the constant `_SUPPLIED_COST_OF_DEBT`, with the same text). I also added the field
to `ProjectionAssumptions`, `--confirm-zero-debt` to the CLI (`build_overrides` and stage
8), a `confirm_zero_debt` form field to the valuation route (read by
`_checkbox_checked`, which stops on any value other than `""` or `"on"`), and the
checkbox to `templates/assumptions.html`. No test turned red.

Trees: `base/` and `new/` are `git archive HEAD` (a993b94) exports under
`/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/49a4d4a7-ff32-4deb-a1ba-ba1f44e044e1/scratchpad/p13h_programmer/`.
Each has the untracked `extractions/WMT.json` copied in. `new/` has the five changed
files copied in, and `cmp` shows each is byte-identical to the repository copy.
`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `ruff --no-cache` and
`mypy --cache-dir=/dev/null` were used on every run. Scripts in that directory:
`measure_wacc.py` (criteria 1-8; CAPM beta 1.0, rf 0.04, ERP 0.06, so Re = 0.10; tax
override 0.25 unless stated), `measure_cli.py` (9), `measure_route.py` (10, route gate).
Outputs: `wacc_base.txt`, `wacc_new.txt`, `wmt_base.txt`, `wmt_new.txt`,
`wmt_confirm.txt`, `mypy_*.txt`, `ruff_*.txt`.

## Baseline at a993b94 (base tree): matches the assignment's table

| Fact | Measured |
|---|---|
| full suite | 2 failed (the two `*_rule3_red.py`), 857 passed |
| gate form | 857 passed |
| ruff | 4, all BLE001 |
| mypy | 9 errors in 4 files |
| census | 65 |
| Walmart | $28.02, WACC 7.68%, label "measured from the filing: interest expense 2,799 / total debt 51,523" |
| the bypass | weights 1.0 / 0.0, label "supplied by the caller (--cost-of-debt / ...)" |

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | interest with zero debt stops, no override | **pass** | `measure_wacc.py` C1, new tree: `ValueError` "... If the company repaid all its debt, so the closing balance really is 0, confirm the zero with --confirm-zero-debt on the CLI, or the "Confirm zero debt" checkbox on the assumptions page; ProjectionAssumptions.zero_debt_confirmed. A supplied cost of debt does not get past this stop ...". The string `--cost-of-debt` is not in the message |
| 2 | the bypass is gone | **pass** | C2 (override 0.05): the same `ValueError`. Base tree: returned 1.0 / 0.0 |
| 3 | a confirmed zero values with no debt | **pass** | C3: weights `1.0 / 0.0`, `wacc == cost_of_equity: True` (0.1), `cost_of_debt 0.0`, label "confirmed zero debt, not measured: the user confirmed total debt of 0 (...) although the income statement reports interest expense of 30.00 for 2025 ... the debt weight D / (E + D) is 0 and the WACC is the cost of equity ..." |
| 4 | confirmed and override: rate kept, said unused | **pass** | C4: `cost_of_debt 0.05`, `1.0 / 0.0`, `wacc == cost_of_equity: True`, label "supplied by the caller ... Not used: the user confirmed total debt of 0 ... With a debt weight of 0, this rate does not reach the WACC." |
| 5 | confirmation against real debt stops | **pass** | C5: `ValueError` "balance_sheet.total_debt is 100.00 (year 2025; short_term_debt 0.00 + current_portion_lt_debt 0.00 + long_term_debt 100.00), but the user confirmed a debt balance of 0 (...). The two inputs contradict each other ..." |
| 6 | debt-free plus override says rate unused | **pass** | C6 (mc 1000, debt 0, interest 0, override 0.90, tax 0.40): wacc `0.1` on both trees, weights 1.0 / 0.0 on both. The new label adds "Not used: the balance sheet for 2025 reports total debt of 0, so the debt weight D / (E + D) is 0 and this rate does not reach the WACC, which is the cost of equity." |
| 7 | normal case unchanged | **pass** | C7 (mc 300, debt 100, interest 5): weights `0.75 / 0.25`, wacc `0.084375` on both trees, the same label. Hand check: 0.75 × 0.10 + 0.25 × 0.05 × 0.75 = 0.075 + 0.009375 = 0.084375 |
| 8 | NaN interest stops by name under an override | **pass** | C8 (debt 0, nan, override 0.05): `ValueError: income_statement.interest_expense is nan ...`. Base tree: returned 1.0 / 0.0 |
| 9 | CLI flag reaches the WACC | **pass** | `cli.py --help` lists `[--confirm-zero-debt]` and its help. `measure_cli.py`: with the flag, `args.confirm_zero_debt = True`, `overrides.zero_debt_confirmed = True`; without it, False / False. End to end: `cli.py --session-file extractions/WMT.json --confirm-zero-debt` exits 1 at stage 8 with "balance_sheet.total_debt is 51,523.00 (year 2026; short_term_debt 10,994.00 + current_portion_lt_debt 0.00 + long_term_debt 40,529.00), but the user confirmed a debt balance of 0 ..." |
| 10 | form field reaches the WACC | **pass** | `measure_route.py`, new tree. `GET /assumptions` (with a filing named): 200, holds `<input type="checkbox" id="confirm_zero_debt" name="confirm_zero_debt" ...>` and "Confirm zero debt". `POST /valuation` on a company with debt 0 and interest 30: `on` gives `calculate_wacc` `zero_debt_confirmed` `[True]` and a success page, $25.75. Field absent gives `[False]` and item 22's stop page. `yes` gives `[]` (not called) and the page "form field confirm_zero_debt is 'yes' ...". Absent with `cost_of_debt_override=5` gives `[False]` and item 22's stop (the bypass is gone in the route too). Hand check of $25.75: FCFF 198, WACC = Re = 10%, PV 180 + PV(TV) 198 × 1.02 / 0.08 / 1.1 = 2,295, EV 2,475, net debt 0 − 100, equity 2,575 / 100 = 25.75 |
| 11 | Walmart does not move | **pass** | Both trees: "Implied Share Price: $ 28.02", "WACC: 7.68%", "source: measured from the filing: interest expense 2,799 / total debt 51,523". `diff` of the two outputs without timing lines: only the two lines that print the session file's path (`base/` against `new/`) |
| 12 | suite fails only where expected | **pass** | Full suite, new tree: `2 failed, 857 passed`. Failure set {`test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`}, equal to base. Gate form: `857 passed`. **No test turned red** (see Measurements) |
| 13 | gates no worse | **pass** | ruff `Found 4 errors.`, the same set as base (`diff` on concise output without line numbers: equal). mypy `Found 9 errors in 4 files`, the same set as base (equal without line numbers). Census `65`. `GET /` → 200. Guard `48/48` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `zero_debt_confirmed` is keyword-only (`*,`) in all three functions | The assignment says "a keyword parameter". Keyword-only means a positional `True` cannot land in it by mistake | A positional parameter after `tax_rate_override` would accept `calculate_wacc(..., 0.05, 0.25, True)`. That call is silent and easy to misread |
| The interest finite check runs on every total-debt-0 path and on the no-override path. It does **not** run on "debt above 0, override given, not confirmed" (`measure_wacc.py` C8c: debt 100, interest nan, override 0.05 still returns 0.75 / 0.25, as on base) | The assignment says the check runs "before every comparison with it, on every row, including when an override is given", and the "above 0 / no / any" row says "unchanged". On that one path nothing compares the interest with anything or reads it: the override replaces it. Both sentences hold only if the check sits before each comparison | A check at the top of the function would also stop C8c. That breaks "unchanged", and it would stop a run on a value the function does not read. **The reviewer should confirm this reading.** If the orchestrator wants the stricter one, it is a one-line move |
| The confirmation-against-debt check uses `total_debt != 0`, not `> 0` | `_require_valid_debt` already refuses a negative line and a non-finite total, so after it `!= 0` and `> 0` select the same cases. `!= 0` refuses any non-zero balance even if that guard ever changes | — |
| Item 22's remedy now says "re-extract the filing or correct the extraction" for an unread balance, not "supply the debt balance" | Review F1 (`2026-10-04T0109-code_reviewer-p13f-wacc-debt.md`) proved that no entry point accepts a debt balance, so the old text named an action nobody can take. That text is part of the remedy, which this unit owns. The rest of the message (item 37's "did not extract" wording) is left as it was | Keeping "supply the debt balance" would keep a remedy that cannot be followed |
| The remedy says "A supplied cost of debt does not get past this stop" without the literal `--cost-of-debt` | Criterion 1: the message "no longer names `--cost-of-debt` as the remedy". Leaving the flag out entirely means a check for the string cannot misread a negative sentence as a remedy | — |
| Confirmed and override, and 0/0 with an override, both return the supplied rate and say "Not used" | Rule 6: the rate is reported, but its weight is 0. The table asks for the supplied rate (criterion 4: cost of debt 0.05) | Returning 0.0 would contradict criterion 4 and hide what the user typed |
| The confirmed 0.0 is labelled "confirmed zero debt, not measured ... No cost of debt is measured; 0.0 is shown because no rate reaches the WACC" | Rule 6: the 0.0 is neither read from the filing nor derived from it. It is shown only because its weight is 0. The label says so, so that it does not read like the debt-free measurement | — |
| The 0/0 rows add "The user also confirmed the zero" when confirmed | The table: "If confirmed, the label also says that the user confirmed the zero". I applied it to both 0/0 rows (with and without an override) for consistency | — |
| `_checkbox_checked(field, value)` is a typed helper. It is not a table, and it does not dispatch | Rule 3: only `""` and `"on"` come from a browser checkbox, and anything else stops and names the field and value. It is called inside the route's `try`, so the stop reaches the error page (item 8, as the assignment notes) | Parsing the value inline as `value == "on"` would read `yes` as unchecked: a silent guess |
| Inline `style="width: auto; margin-right: 0.4rem;"` on the checkbox | `static/style.css:88` sets `.form-group input { width: 100% }`, which would stretch the checkbox across the column. `static/style.css` is not in scope; the template is | A CSS class would need a change to `static/style.css`, which is out of scope |
| No edit to `docs/3-architecture/valuation-math.md` or `docs/3-architecture/entry-points.md` | Both are in scope only on a condition. The WACC section (`valuation-math.md:126-144`) describes neither item 22's stop nor the override: it holds the formula, the book-value note, the clamp and item 9's defect. `entry-points.md` does not list the overrides one by one: it lists `build_overrides` as a function (`:116`) and item 6's parsing difference (`:174`). Neither condition holds | Adding a new section would go beyond "state the confirmation ... if that section describes ..." |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `balance_sheet` | stops, names `balance_sheet` (unchanged, runs first) | `_require_balance_sheet` before everything, `analysis/wacc.py` `cost_of_debt_with_source` |
| debt lines and `total_debt` | stop, naming the line or the total, on NaN, inf or a negative value (unchanged, runs second) | `_require_valid_debt` |
| `zero_debt_confirmed` (function argument) | defaults to `False`, which is "the user confirmed nothing". That default leads to item 22's **stop**, not to a value, so a missing confirmation never values a company | C1, C2 |
| `zero_debt_confirmed` against a total debt above 0 | stops, naming `balance_sheet.total_debt`, its three lines, the year and the confirmation | C5, X4, Walmart with the flag |
| `income_statement.interest_expense` beside total debt 0 | stops, naming `income_statement.interest_expense`, on NaN or inf, before any comparison, with or without an override or confirmation | C8, C8b |
| `income_statement.interest_expense` beside debt above 0, no override | stops, naming it (unchanged) | existing tests `test_a_non_finite_interest_*` stay green |
| `income_statement.interest_expense` beside debt above 0, override given | **not read**, so it does not stop (unchanged from base) | C8c. See Decisions, row 2 |
| `cost_of_debt_override` | `None` means "not supplied" (unchanged) | — |
| form `confirm_zero_debt` | absent → `""` → `False`: that is how a browser sends an unchecked box, and it leads to item 22's stop, not to a value. Any value other than `""` or `"on"` **stops**, naming the field and the value | `measure_route.py`: `yes` gives the named stop page, and `calculate_wacc` is not called |
| CLI `--confirm-zero-debt` | `store_true`: absent is `False`, as above | `measure_cli.py` |
| `ProjectionAssumptions.zero_debt_confirmed` | `False` default: a `bool`, not a money figure, so it does not match the census pattern. Census unchanged at 65 | census grep |

## Measurements

- **Suite, failure sets.** Base: {`test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`}, 857 passed. New: the same set, 857 passed. Gate form: 857 / 857.
- **Why no test turned red.** The assignment expected `test_wacc.py` cases that pin the old bypass or the old remedy text. There are none. The module docstring of `tests/unit/test_wacc.py` (lines 31-35) says: "Backlog item 38b (a) ... No test here asserts that behaviour, either way". `_wacc_on` (`:479`) and the non-finite interest section (`:1147`) each say that no override is passed beside zero debt. `test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt` (`:252`) is the 0/0 + override row (criterion 6). It asserts weights and WACC, which do not move, and not the label. So it stays green.
- **Lint.** 4 → 4, the same set (3 BLE001 in `api/routes_valuation.py` ×2, `cli.py`; 1 in `tests/test_e2e_all_googl.py`).
- **Types.** 9 in 4 files → 9 in 4 files, the same set. The two `api/routes_valuation.py` errors moved line (now `:649`, `:658`) because of the inserted lines. They are not new.
- **Census.** 65 → 65.
- **Figures moved.** No figure on a run that worked before. Walmart: $28.02 / 7.68%, unchanged. Each newly reachable figure was checked by hand: C3 and C4 WACC = Re = 0.10 because D = 0, and the route's $25.75 (arithmetic in criterion 10). The route's $25.75 rests on the stub's revenue 1000 and cash 100, and Walmart's WACC rests on the filing's interest expense 2,799 / total debt 51,523 (`wmt_new.txt:215`).

## What I did not do

- No test edits (`tests/` is the tester's).
- No doc edits. Neither conditional doc section describes the stop or lists the
  overrides (see Decisions).
- Item 37 (item 22's wording other than its remedy) is left as it is. The message still
  says the balance "did not extract", and then offers the confirmation for the case
  where the zero is real. Item 37 owns that inconsistency.
- Items 72, 6, 5 and 7 are untouched, as the assignment directs. Stage 8 in `cli.py`
  changes by one argument line.
- `.claude/output-styles/ste100.md` was already modified in the working tree before this
  run (the git status snapshot at the start). It is not mine. I did not touch it.

## Findings for the orchestrator

1. **Tester:** item 38b (a) now has behaviour to lock. The rows to cover are C1-C8,
   C8b, X1-X4 in `measure_wacc.py`, plus the route's `""`, `"on"` and `"yes"` cases and
   the CLI flag. The note in `tests/unit/test_wacc.py:31-35` ("The user is deciding its
   replacement ... No test here asserts that behaviour") is now stale and should be
   rewritten when those tests land.
2. **Decision to confirm:** with total debt above 0 and an override given, a NaN
   interest expense still passes (C8c), because nothing reads it. I read the
   assignment's "every row" sentence as "before every comparison" (see Decisions). If
   the stricter reading is wanted, move the `_require_finite` call to just after
   `_require_valid_debt`, and C8c will stop.
3. **Item 37, now sharper.** Item 22's stop says the balance "did not extract" as a
   fact, then offers a confirmation for a zero that is real. A rewrite of item 37
   should state the two readings as alternatives.
4. **Backlog item 75 (guard)** did not trigger in this run. The quoted `>` patterns
   were kept out of Bash by putting the scripts in files.
