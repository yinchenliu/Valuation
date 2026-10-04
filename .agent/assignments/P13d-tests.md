---
id: P13d-tests
phase: 13 — silent defects first, wave 2
agent: tester
depends_on: [P13d-upside-price]
---

# Lock the stop on a current price that is not finite and above zero

## Objective

`P13d-upside-price` (approved in round 1, not yet committed) closes backlog item 65.
`run_dcf` stops before it discounts when `current_price` is not a finite number above
zero, and `DCFResult.upside_downside` raises instead of returning `0.0`. No test locks
either. No test turned red.

Read first: `.agent/assignments/P13d-upside-price.md`, the programmer's entry
`.agent/journal/2026-10-04T0102-programmer-p13d-upside-price.md`, the review
`.agent/journal/2026-10-04T0108-code_reviewer-p13d-upside-price.md`, and
`.claude/agents/tester.md` from its first section.

## What to do

1. `run_dcf` raises `ValueError` naming `current_price` for 0, a negative price, `nan`,
   `inf` and `-inf`. Show that the check runs before discounting, as the P13b tests did
   for `diluted_shares` (a NaN cash flow must not be the error that is reported).
2. `upside_downside` on a `DCFResult` built directly raises `ValueError` naming
   `current_price` for the same values.
3. For one positive case, derive the upside by hand, `(implied / current − 1) × 100`,
   from a bridge you work out, and assert it.

## Files in scope

- `tests/unit/test_dcf.py`

**Nothing else.** Other wave 2 units are under review in the same tree. Work in your own
scratch subdirectory `scratchpad/p13d_tester/`, on a `git archive f6da3e9` export with
`models/valuation.py`, `analysis/dcf.py` and your test file copied in. Never `rm -rf`
outside your subdirectory, and do not stash or reset the shared tree.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form on the isolated tree | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite on the isolated tree | exactly the 2 known `*_rule3_red.py` failures | `.venv/bin/python -m pytest -q` |
| 3 | each stop is locked | each of steps 1 and 2 has a test that turns red when its stop is removed | mutants in a scratch copy |
| 4 | two counts | accuracy and coverage, as `tester.md` requires | its "Report two counts" section |

## Backlog items this unit is NOT fixing

- Item 1: `current_price: float = 0.0` and the other field defaults.
- Item 31: `discount_cash_flows` on a direct call.
