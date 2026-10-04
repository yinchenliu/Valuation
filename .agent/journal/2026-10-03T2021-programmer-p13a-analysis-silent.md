---
agent: programmer
assignment: P13a-analysis-silent
round: 1
status: complete
files_touched: [analysis/normalizer.py, analysis/wacc.py]
---

# P13a-analysis-silent — stop on an adjustment for a year with no statement, and on WACC weights from nothing

## What I did

Two rule-3 stops, each a `ValueError`, nothing else. **Item 25:** `normalize_financials`
(`analysis/normalizer.py:247-262`) now collects, before any adjustment, every item whose
`year` is not the year of an income statement in `financials`, and raises naming each such
item's year, `line_item` and description and the sorted statement years. The empty-list
early return is kept. **Item 38:** the `total_value == 0` branch of `calculate_wacc`
(`analysis/wacc.py:215-229`) no longer returns `equity_weight=1.0, debt_weight=0.0`; it
raises naming `market_cap` and `balance_sheet.total_debt` with both values (and the balance
sheet year), and says the weights cannot be formed. Neither message states a cause (item 37).

## Done-criteria

Scripts are in my scratchpad (`/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/5a3eb59a-dd70-43de-8ee8-c16bbd7dd61e/scratchpad/`): `crit12.py <year> <direction>`, `crit34.py <market_cap> <debt>`, `wmt.py <session file>`. Each is run with `PYTHONPATH=<repo> .venv/bin/python`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | item for a year with no statement stops | pass | `crit12.py 2019 add_back` (statements 2023, 2024): `ValueError: 1 non-recurring item(s) carry a year with no income statement in the financials: year 2019, line_item 'sga', description 'Restructuring charge, Note 12'. The income statement years are [2023, 2024]. ...` |
| 2 | item for a year with a statement still applies | pass | `crit12.py 2024 add_back`: 2024 sga 200.0 → 150.0, ebit 200 → 250; 2023 untouched (sga 200, ebit 200). `crit12.py 2024 remove`: 2024 sga 250.0, ebit 150. Hand check: add_back on an expense field moves the field by −50 and EBIT by +50; remove the reverse. |
| 3 | `market_cap + total_debt == 0` stops | pass | `crit34.py 0 0` (with and without a cost-of-debt override): `ValueError: market_cap is 0.00 and balance_sheet.total_debt is 0.00 (year 2024), so their sum is 0 and the capital weights E / (E + D) and D / (E + D) cannot be formed from them. They are not set to an all-equity 1.0 / 0.0. Supply a non-zero market_cap or debt balance.` No cause claimed. |
| 4 | positive total keeps its weights | pass | `crit34.py 300 100`: `equity_weight 0.75 debt_weight 0.25` (300/400, 100/400) |
| 5 | Walmart unchanged | pass | `wmt.py extractions/WMT.json` on the `0021845` tree (via `git archive`, see Measurements) and on the edited tree: `cmp` → IDENTICAL. The adjustments are real filing inputs, not zeros: 2026 sga 147,943 → 147,243 (the 700 add_back, Note 3, PDF p.27); other_non_operating −3,027 / −794 / 2,075 → 0 for 2024/2025/2026. |
| 6 | suite fails only where expected | pass (with attribution) | Isolated (`0021845` tree + only my two files): full suite `3 failed, 723 passed` = the 2 `*_rule3_red.py` + `test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`; gate form `1 failed, 723 passed`. Shared tree: 31 failed / 29 in gate form; the extra 28 are P13b's, see Measurements. |
| 7 | gates do not get worse | pass | Isolated: ruff `Found 5 errors.`, mypy `Found 10 errors in 4 files (checked 20 source files)`, census 67. Shared tree: ruff 5, mypy 10 in 4 files, census 65 (P13b's edits). My two files: `ruff check analysis/normalizer.py analysis/wacc.py` → `All checks passed!`; census hits in my two files: 0 before, 0 after. |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The year check runs before `by_year` is built and before any `apply_adjustments` | assignment step 1, "before any adjustment is applied" | Checking inside the loop would only see items whose year matches, which is exactly the defect |
| Collect all unmatched items, then raise once | assignment step 1: "for each such item" | Raising on the first would hide the others and cost the user one run per item |
| Message does not say which year is wrong | the two years come from two passes; the function cannot know which is right (assignment objective; item 37's lesson) | Claiming "the item year is wrong" would state a cause as fact |
| `by_year.get(stmt.year, [])` left as is | a statement year with no items legitimately has no adjustment; the empty list is not a stand-in for a missing value. After the new check, every item is in some statement's bucket, so nothing can be dropped by it | Not a census pattern and not a rule-3 site |
| WACC message includes `balance_sheet.year` | names where the debt figure came from, so the reader can find it | — |
| WACC message says "their sum is 0" rather than "both are 0" | `total_value == 0` also fires for e.g. −100 and +100; the message gives both values so it stays true in that case | — |
| Old-tree reference by `git archive`, not `git stash` (deviation from criterion 5's suggested method) | the working tree is shared with P13b and P13c; `git stash` would have stashed and restored their uncommitted edits mid-run | Same comparison, no side effect on other units |

No change was made to reach a target number.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `non_recurring` (the list) | empty → returns `financials` unchanged (kept per assignment; no items is a legitimate state) | `normalizer.py:244-245` |
| `item.year` vs `financials.income_statements[*].year` | no matching statement → stops, names year, line_item, description and the statement years | criterion 1 |
| `financials.income_statements` empty, items present | stops: every item is unmatched, statement years printed as `[]` | executed: `normalize_financials(FinancialStatements(ticker='T'), [one 2024 item])` → `ValueError: ... The income statement years are [].` |
| `market_cap` + `balance_sheet.total_debt` == 0 | stops, names both and both values | criterion 3 |
| `market_cap` NaN / `total_debt` NaN | stops (pre-existing `_require_finite`) | `wacc.py:209-212` (`_require_finite` at 210 and 212), unchanged |
| `balance_sheet` is `None` with a cost-of-debt override | **AttributeError**, not a named ValueError (pre-existing, not changed) | see Findings, face B |
| `balance_sheet.total_debt == 0` because the debt lines did not extract, with an override, interest ≠ 0, market_cap > 0 | **weights default to 1.0 / 0.0**, override unused (pre-existing; item 38's second face, not fixed per assignment) | see Findings, face A |

## Measurements

### Baseline at `0021845` (before any edit, tree clean in analysis/, models/, config.py, ingestion/)

- full suite: `2 failed, 724 passed` — failure set {test_projector_rule3_red::test_an_extraction_with_no_income_statements_stops_and_names_the_input, test_routes_session_rule3_red::test_valuation_with_session_file_and_files_on_a_cache_hit_stops}
- ruff: `Found 5 errors.`; mypy (exact gate command): `Found 10 errors in 4 files (checked 20 source files)`; census (quoted `'--include=*.py'`): 67; census restricted to my two files: 0
- item 25 / item 38 code at the cited lines: as the assignment states.
- Walmart: statement years [2024, 2025, 2026], item years [2024, 2025, 2026], 4 items, 0 outside; partition: 4 applied, 0 excluded.
- Old-tree reference for criterion 5 captured with `git archive 0021845 | tar -x -C <scratchpad>/old`, NOT `git stash`: a stash in this shared working tree would also stash the parallel units' (P13b, P13c) uncommitted edits. Script `<scratchpad>/wmt.py` loads `extractions/WMT.json` (untracked, so the same absolute path serves both trees), partitions by confidence, normalises, dumps the adjusted income statements as sorted JSON. Old tree vs current-before-edit: `cmp` → IDENTICAL (67 lines).


### After the edit

**Shared tree** (P13b and P13c edits present: `analysis/dcf.py`, `analysis/projector.py`, `config.py`, `ingestion/claude_extractor.py`, `models/financial_statements.py`, `models/valuation.py` modified by them):
- full suite: `31 failed, 695 passed`; gate form: `29 failed, 695 passed`.
- Failure set = baseline 2 `*_rule3_red.py` + `test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt` (mine, expected) + 28 others: 26 in `tests/unit/test_normalizer.py` and 2 in `tests/unit/test_normalizer_stops.py` (`test_an_unrecognised_line_item_stops_the_run`, `test_an_unrecognised_direction_stops_the_run`). **All 28 fail with `TypeError: NonRecurringItem.__init__() missing 1 required positional argument: 'confidence'`** (grouped with `pytest ... | grep '^E ' | sort | uniq -c` → 28 identical lines). That is the test fixtures constructing `NonRecurringItem` without `confidence`, which `models/financial_statements.py` (P13b's file, item 39) now requires. Not caused by this unit.
- ruff 5 (BLE001), mypy 10 in 4 files, census 65 (the drop of 2 is P13b's).

**Isolated** (`git archive 0021845` into `<scratchpad>/iso`, then only `analysis/normalizer.py` and `analysis/wacc.py` copied in; `diff` of `analysis/` confirms only those two files differ apart from the parallel units' `dcf.py`/`projector.py`, which are NOT copied):
- full suite: `3 failed, 723 passed` — failure set = baseline 2 + `test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`.
- gate form: `1 failed, 723 passed`.
- that test's error: `ValueError: market_cap is 0.00 and balance_sheet.total_debt is 0.00 (year 2025), so their sum is 0 and the capital weights ... cannot be formed from them. ...` — it requires the call to return, and its docstring says it asserts nothing about the weights. Expected per assignment step 3.
- ruff `Found 5 errors.`, mypy `Found 10 errors in 4 files (checked 20 source files)`, census 67.

**Red tests caused by this unit: exactly one**, `tests/unit/test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`. No normalizer test turned red from the year check in isolation.

## What I did not do

- Did not edit `tests/`. `tests/unit/test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt` is red by design; the tester rewrites it.
- Did not edit `docs/3-architecture/valuation-math.md` (step 4: **no sentence there states either old behaviour**; searched sections 1 and 6, lines 12-34 and 125-151).
- Did not touch items 1, 17, 22/37, or the second face of item 38 (reported below).
- Did not commit.

## Findings for the orchestrator

1. **Item 38, second face — reachable after this change.** Face A: `calculate_wacc(capm, IncomeStatement(interest_expense=30, ...), BalanceSheet(year=2024, all debt lines 0), market_cap=300, cost_of_debt_override=0.05)` returns `equity_weight 1.0, debt_weight 0.0, cost_of_debt 0.05`. The same inputs without the override stop (item 22's guard), because `cost_of_debt_with_source` returns the override before it looks at the balance sheet, so the interest-vs-zero-debt check never runs. The supplied rate is then multiplied by a zero weight and the firm is discounted at its cost of equity. Face B: `balance_sheet=None` with an override raises `AttributeError: 'NoneType' object has no attribute 'total_debt'`, not a named stop, at `wacc.py:211` (`debt_value = balance_sheet.total_debt`); reachable from `api/routes_valuation.py:621-634` (`get_balance_sheet` returns `None`), which is item 11's type error.
2. **Line citations shifted by this edit (outside my scope):** `api/routes_valuation.py:411` cites `analysis/normalizer.py:245` for `dataclasses.replace`; it is now line 273. `tests/unit/test_wacc.py:404` cites the early return at `analysis/wacc.py:215` that no longer exists (the tester's rewrite covers it). `docs/9-reference/refactor-backlog.md:618` cites `wacc.py:215-223` (closes with the item).
3. **Stale prose in `docs/3-architecture/valuation-math.md`, not about this unit's behaviour:** lines 31-34 record `_resolve_field` guessing as an open defect (closed at `38b903c`, backlog item 3); lines 147-151 say nothing in the output reports the 4.0% substitution (item 9 added `cost_of_debt_source`); lines 159-161 call `calculate_terminal_value` "the one place in `analysis/`" that stops per rule 3, which is no longer true. The owner of that doc should reconcile.
4. **The new stops reach the user as text.** Both API paths catch `Exception` and render `str(e)` (`api/routes_valuation.py:445-446`, `703-707`); `cli.py:1002` and `cli.py:1045` call without a catch. No test checks that either message reaches the result page.
