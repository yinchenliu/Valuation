---
id: P13a-analysis-silent
phase: 13 — silent defects first (the user's decision of 2026-10-03)
agent: programmer
depends_on: []
---

# Stop on an adjustment for a year with no statement, and on WACC weights from nothing

## Objective

Two functions in `analysis/` return a well-formed result from absent data, and nothing
downstream can tell.

- **Item 25.** `normalize_financials` (`analysis/normalizer.py:225-245`) groups the
  non-recurring items by year and walks the income statements. An item whose year
  matches no income statement is never looked at. The valuation is then labelled
  normalised while that adjustment is missing. The item's year and the statements' years
  come from two separate model passes, with nothing reconciling them.
- **Item 38.** `calculate_wacc` (`analysis/wacc.py:213-223`) returns `equity_weight=1.0,
  debt_weight=0.0` when `market_cap + balance_sheet.total_debt == 0`. A company with no
  market value and no debt is absent data, not an all-equity company.

Rule 3 (`docs/2-rules/rules.md`): a missing input stops the run and names the field.
Both functions must raise `ValueError` instead, and say what was absent.

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Measured at `0021845` on 2026-10-03.

| Fact | Command | Result |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 724 passed |
| full suite | `.venv/bin/python -m pytest -q` | 2 failed (both `*_rule3_red.py`), 724 passed |
| lint | `.venv/bin/python -m ruff check .` | 5 errors, all `BLE001` |
| types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 10 errors in 4 files |
| census | the grep in `docs/2-rules/rules.md` (quote `'--include=*.py'` under zsh) | 67 |
| item 25 code | `sed -n 236,243p analysis/normalizer.py` | `by_year.get(stmt.year, [])` over `financials.income_statements` |
| item 38 code | `sed -n 213,223p analysis/wacc.py` | `if total_value == 0: return WACCResult(... equity_weight=1.0, debt_weight=0.0 ...)` |
| Walmart is not affected by item 25 | load `extractions/WMT.json` with `load_session_extraction` and compare `{i.year for i in r.non_recurring}` with `r.financials.years` | statement years [2024, 2025, 2026], item years [2024, 2025, 2026], 4 items, 0 outside |

If any of these disagrees with what you measure, stop and report the disagreement.

## What to do

1. **Item 25, `analysis/normalizer.py`.** In `normalize_financials`, before any
   adjustment is applied, collect every item whose `year` is not the year of an income
   statement in `financials`. If there is one or more, raise `ValueError`. The message
   names, for each such item, its year, `line_item` and description, and it names the
   income statement years that exist. Keep the early return for an empty item list.
   Reason: rule 3, and backlog item 25's "Fix".

2. **Item 38, `analysis/wacc.py`.** Replace the `total_value == 0` branch with a
   `ValueError` that names `market_cap` and `balance_sheet.total_debt`, gives both
   values, and says that the capital weights cannot be formed from them.
   **Do not state a cause as a fact.** Do not say that the extraction failed. Backlog
   item 37 records that mistake in the zero-debt stop of this same file.
   Reason: rule 3, and backlog item 38.

   **Round 2 amendment (orchestrator, 2026-10-03, from review F1).** Step 2 as first
   written checked only the sum. A market cap of 0 with debt of 100 still returns
   `equity_weight 0.0, debt_weight 1.0`, and the WACC falls to the after-tax cost of
   debt. A market cap of zero or below can only come from absent inputs, and it is
   reachable: `api/routes_valuation.py:628` and `cli.py:1039` fall back to
   `info.get("sharesOutstanding", 0)`. So `calculate_wacc` also stops when `market_cap`
   is not greater than zero, naming `market_cap` and its value, with no claim about the
   cause. The sum check stays for the case that it still covers.

3. **Do not edit `tests/`.** One test is known to turn red:
   `tests/unit/test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`
   requires the call to return. Its docstring says that it asserts nothing about the
   weights, so this is expected. The tester rewrites it. List every test that turns red,
   by name, with the reason for each.

4. Check `docs/3-architecture/valuation-math.md` for a sentence that states either old
   behaviour. If you find one, report it with its line. Do not edit it.

## Files in scope

- `analysis/normalizer.py`
- `analysis/wacc.py`

**Nothing else.** Work outside this list is a review finding, even if the change is
good. Two other units run in parallel: `P13b-models-silent` owns `models/`,
`analysis/dcf.py` and `analysis/projector.py`, and `P13c-env-override` owns `config.py`
and `ingestion/claude_extractor.py`. Their changes can show in the full test run.

## Out of scope

- `tests/`: the tester's.
- `docs/9-reference/refactor-backlog.md` and `STATUS.md`: the orchestrator closes the
  items after acceptance.
- `api/routes_valuation.py:634`, the `BalanceSheet | None` type error: item 11, phase 5.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | an item for a year with no statement stops | `ValueError` naming 2019, the item's `line_item` and description, and [2023, 2024] | a `python -c` that builds statements for 2023 and 2024 and one item for 2019 |
| 2 | an item for a year with a statement still applies | the field moves by the item's amount, under its direction | the same script with the item year 2024 |
| 3 | `market_cap + total_debt == 0` stops | `ValueError` naming both inputs and both values, with no claim about the cause | a `python -c` call to `calculate_wacc` |
| 4 | a positive total keeps its weights | equity 0.75, debt 0.25 for 300 and 100 | the same call with 300 and 100 |
| 5 | Walmart is unchanged | `normalize_financials` on `WMT.json` gives the same adjusted income statements as at `0021845` | a script run on both trees (`git stash` for the old one), outputs compared |
| 6 | the suite fails only where expected | every red test named, with its reason | the full suite and the gate form |
| 7 | the gates do not get worse | ruff 5, mypy 10, census 67 or fewer | the three commands above |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md`, rule 3: a missing input stops and names the field.
- `docs/9-reference/refactor-backlog.md`, items 25, 37 and 38.
- `docs/5-testing/strategy.md`, section 2: why no test may lock the old behaviour.

## Known open items

- Item 36: low-confidence items are withheld by `partition_by_confidence` before
  `normalize_financials` runs. The new stop applies only to the items that reach it.

## Backlog items this unit is NOT fixing

- Item 1: the zero-default sites in these two files.
- Item 22's other half and item 37: the zero-debt cost-of-debt stop and its message.
- Item 17: `analysis/capm.py` imports from `ingestion/`.
- The second face of item 38: a supplied cost of debt with an absent balance sheet. If
  you can reach it after your change, report how. Do not fix it.
