---
id: P13a-tests
phase: 13 — silent defects first (the user's decision of 2026-10-03)
agent: tester
depends_on: [P13a-analysis-silent]
---

# Rewrite the one red WACC test, and lock the two new stops

## Objective

`P13a-analysis-silent` (approved in round 2, not yet committed) closes backlog item 25
and item 38's own case. **One test in the gate now fails**, as the assignment predicted:
`tests/unit/test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`.
It needs `calculate_wacc` to return on a market cap and debt of 0, and that call now
stops. Its docstring says that it asserts nothing about the weights. No test locks the
two new stops yet.

Read these first:

- `.agent/assignments/P13a-analysis-silent.md`, including the round 2 amendment to step 2
- `.agent/journal/2026-10-03T2021-programmer-p13a-analysis-silent.md`
- `.agent/journal/2026-10-03T2031-code_reviewer-p13a-analysis-silent.md`
- `.agent/journal/2026-10-03T2033-programmer-p13a-analysis-silent-r2.md`
- `.agent/journal/2026-10-03T2037-code_reviewer-p13a-analysis-silent-r2.md`
- `.claude/agents/tester.md`, from its first section.

## What to do

1. **Rewrite the red test.** Its subject is that the cost of equity passes through
   unchanged. Keep that subject on an input where the weights can be formed, or turn it
   into a test of the new stop. Do not delete what it guards without saying why in your
   entry. Its citation of `wacc.py:215` (the old early return) is stale. Correct it.

2. **Lock item 25.** `normalize_financials` with income statements for 2023 and 2024 and
   one item for 2019 raises `ValueError`. Assert the type and that the message names
   2019, the item's `line_item`, its description, and the years 2023 and 2024. Two
   unmatched items are both named in one message. An item for 2024 still moves its field
   by its amount, under its direction. Work the moved figure out by hand.

3. **Lock item 38 and the amendment.** `calculate_wacc` raises `ValueError` for these
   pairs of market cap and debt: (0, 0), (−100, 100), (0, 100) and (−5, 100). Assert the
   type and that each message names `market_cap`. The sum case also names
   `balance_sheet.total_debt`. Assert that no message states a cause: it must not say
   that the extraction failed (backlog item 37). For (300, 100), derive the weights by
   hand, 300 ÷ 400 and 100 ÷ 400, and assert them.

4. **Do not lock the open defects.** Do not assert the weights for a negative debt
   balance (backlog item 69). Do not assert the behaviour of item 38's second face
   (backlog item 38b): an override with zero debt lines, or `balance_sheet=None`.

## Files in scope

- `tests/unit/test_wacc.py`
- `tests/unit/test_normalizer_year_stop.py`, new, for item 25

**Nothing else.** The P13b tester is writing tests in the same tree now. Its files are
`tests/unit/test_normalizer.py`, `tests/unit/test_normalizer_stops.py`,
`tests/unit/test_dcf.py`, `tests/unit/test_projector_sources.py` and
`tests/unit/test_models_stops.py`. Do not edit them. `P13c-env-override` is in review and
owns `config.py`, `ingestion/claude_extractor.py` and `docs/8-build/environment.md`.

## Measure on an isolated tree

The shared tree holds the other units' changes. Export `git archive 0021845` into your
scratch directory, copy in this unit's two code files (`analysis/normalizer.py`,
`analysis/wacc.py`) and your two test files, and run the gates there. Do not stash or
reset the shared tree.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the red test is rewritten | it passes, and your entry says what it guards now | the full suite on the isolated tree |
| 2 | the gate form on the isolated tree | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 3 | the full suite on the isolated tree | exactly the 2 known `*_rule3_red.py` failures | `.venv/bin/python -m pytest -q` |
| 4 | each new stop is locked | each of steps 2 and 3 has a test that fails when its code change is reverted | revert each stop in a scratch copy, one at a time, and run the new tests; report which turn red |
| 5 | two counts | accuracy and coverage, as `tester.md` requires | its "Report two counts" section |

## Citations

- `docs/5-testing/strategy.md`: where an expected value may come from.
- `docs/2-rules/rules.md`, rule 3.
- `docs/9-reference/refactor-backlog.md`, items 25, 37, 38, 38b and 69.

## Backlog items this unit is NOT fixing

- Items 37, 38b and 69 in `analysis/wacc.py`. Do not lock their current behaviour.
- Item 1's zero-default sites in both files.
