---
id: P13e-tests
phase: 13 — silent defects first, wave 2
agent: tester
depends_on: [P13e-growth-input]
---

# Lock that the caller's growth list is not changed, and the stop on a short projection

## Objective

`P13e-growth-input` (approved in round 1, not yet committed) closes backlog items 66 and
67. `derive_assumptions` works on a copy of the supplied growth list, and it stops with a
`ValueError` naming `projection_years` when the value is not an integer of 1 or more
(`True` and `2.0` included, which the review accepted). No test locks either. No test
turned red.

Read first: `.agent/assignments/P13e-growth-input.md`, the programmer's entry
`.agent/journal/2026-10-04T0102-programmer-p13e-growth-input.md`, the review
`.agent/journal/2026-10-04T0130-code_reviewer-p13e-growth-input.md`, and
`.claude/agents/tester.md` from its first section.

## What to do

1. After a call with `[0.1]` and `projection_years=3`, the caller's list is the same
   object and still `[0.1]`.
2. Two calls with the same assumptions give the same growth label, and both hold the
   `REPEATED` clause.
3. `projection_years` of 0, −1, `True` and `2.0` each raise `ValueError` naming
   `projection_years`. Assert the field name and the value, not the reason sentence: the
   review's F1 says that sentence is wrong for non-integer values, and it may change.
4. One valid case, `projection_years=1`, still projects one year.

## Files in scope

- `tests/unit/test_projector_sources.py`

**Nothing else.** The P13d tester is writing `tests/unit/test_dcf.py` now. Work in your
own scratch subdirectory `scratchpad/p13e_tester/`, on a `git archive f6da3e9` export with
`analysis/projector.py` and your test file copied in. Never `rm -rf` outside your
subdirectory, and do not stash or reset the shared tree.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form on the isolated tree | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite on the isolated tree | exactly the 2 known `*_rule3_red.py` failures | `.venv/bin/python -m pytest -q` |
| 3 | each behaviour is locked | each of steps 1 to 3 has a test that turns red when its change is reverted | mutants in a scratch copy |
| 4 | two counts | accuracy and coverage, as `tester.md` requires | its "Report two counts" section |

## Backlog items this unit is NOT fixing

- Item 41: the dead `else 0.05`. Do not assert it.
- The bare `IndexError` locked by `tests/unit/test_projector_rule3_red.py`. Leave that file alone.
