---
id: P13b-tests
phase: 13 — silent defects first (the user's decision of 2026-10-03)
agent: tester
depends_on: [P13b-models-silent]
---

# Repair the 28 fixtures that omit `confidence`, and lock the four new behaviours

## Objective

`P13b-models-silent` (approved in round 1, not yet committed) closes backlog items 15,
32, 39 and 42. **28 tests in the gate now fail**, all with
`TypeError: NonRecurringItem.__init__() missing 1 required positional argument:
'confidence'`, because item 39 made that field required. The review confirmed the 28 by
name: 26 in `tests/unit/test_normalizer.py` through the builder at line 84, and 2 in
`tests/unit/test_normalizer_stops.py`, constructors at lines 78 and 114. No test locks
the four new behaviours yet.

Read these first:

- `.agent/assignments/P13b-models-silent.md`
- `.agent/journal/2026-10-03T2021-programmer-p13b-models-silent.md`
- `.agent/journal/2026-10-03T2033-code_reviewer-p13b-models-silent.md`
- `.claude/agents/tester.md`, from its first section. Every expected value comes from the
  formula or the rule, worked by hand before the code runs.

## What to do

1. **Repair the 28.** Pass `confidence=` in each constructor that omits it. Choose the
   value that each test's own subject needs. A test about the normalizer applying an
   item must use a confidence that the entry points apply (`partition_by_confidence`
   withholds `low`). **No assertion about a figure may change.**

2. **Lock item 15.** `FinancialStatements.latest_year` with no statements raises
   `ValueError`. Assert the type and the words that say there is no latest year. With
   statements for two years, it returns the later year.

3. **Lock item 32.** `run_dcf` stops before it discounts, naming `diluted_shares`, for 0,
   a negative count, `nan` and `inf`. `DCFResult.implied_share_price` raises for the
   same values. For one positive case, derive the price by hand from the bridge
   (enterprise value − net debt − noncontrolling interest) ÷ diluted shares, and assert
   it.

4. **Lock item 39.** Building a `NonRecurringItem` without `confidence` raises
   `TypeError`.

5. **Lock item 42.** Five supplied rates with `projection_years=2` give the first two
   rates, and the growth label holds the truncation clause, naming 5 supplied, 2 used
   and 3 dropped. Two rates with `projection_years=2` give no truncation clause. One
   rate with `projection_years=3` keeps the pad clause and has no truncation clause.

6. **Do not lock the open defects that the review found.** With `projection_years`
   below 1, the label describes a projection that never runs (review F1). Do not assert
   that text. It goes to the backlog.

## Files in scope

- `tests/unit/test_normalizer.py`
- `tests/unit/test_normalizer_stops.py`
- `tests/unit/test_dcf.py`
- `tests/unit/test_projector_sources.py`
- `tests/unit/test_models_stops.py`, new, for items 15 and 39

**Nothing else.** `P13a-analysis-silent` and `P13c-env-override` are in round 2 with
their programmers in the same tree. Their files are `analysis/normalizer.py`,
`analysis/wacc.py`, `config.py`, `ingestion/claude_extractor.py` and
`docs/8-build/environment.md`. Do not edit them. Do not edit `tests/unit/test_wacc.py`:
the P13a tester owns it.

## Measure on an isolated tree

The shared tree holds the other two units' changes, which make other tests red. Export
`git archive 0021845` into your scratch directory, copy in this unit's four code files
(`models/financial_statements.py`, `models/valuation.py`, `analysis/dcf.py`,
`analysis/projector.py`) and your test files, and run the gates there. Do not stash or
reset the shared tree.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the 28 pass | 0 of the 28 fail | the full suite on the isolated tree, failure set compared with the 28 names |
| 2 | no figure assertion changed in the repairs | only constructor arguments differ | `git diff` of the two repaired files, read line by line |
| 3 | the gate form on the isolated tree | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 4 | the full suite on the isolated tree | exactly the 2 known `*_rule3_red.py` failures | `.venv/bin/python -m pytest -q` |
| 5 | each new behaviour is locked | each of steps 2 to 5 has a test that fails when the behaviour is reverted | revert each code change in a scratch copy, one at a time, and run the new tests; report which tests turn red |
| 6 | two counts | accuracy and coverage, as `tester.md` requires | its "Report two counts" section |

## Citations

- `docs/5-testing/strategy.md`: where an expected value may come from.
- `docs/2-rules/rules.md`, rules 3 and 6.
- `models/valuation.py`, the pad and truncation clause templates.

## Backlog items this unit is NOT fixing

- Item 1, item 23, item 41, and the bare `IndexError` locked by
  `tests/unit/test_projector_rule3_red.py`. Leave that file as it is.
- `upside_downside` on a zero current price, and `derive_assumptions` padding the
  caller's list in place. They are new backlog items. Do not lock either behaviour.
