---
id: P13f-tests
phase: 13 — silent defects first, wave 2
agent: tester
depends_on: [P13f-wacc-debt]
---

# Lock the new WACC stops: bad debt lines, no balance sheet, values that are not finite

## Objective

`P13f-wacc-debt` (approved in round 2, not yet committed) closes backlog item 69 and
part (b) of item 38b, and the round 2 review's F2 to F4. No test locks them. No test
turned red. **Use the "Round 2 amendment" in the assignment, not its done-criteria
table**: the table still shows the withdrawn criterion 2 (the review's note F2).

Read first: `.agent/assignments/P13f-wacc-debt.md` with its round 2 amendment, the two
programmer entries (`2026-10-04T0102-programmer-p13f-wacc-debt.md`,
`2026-10-04T0111-programmer-p13f-wacc-debt-r2.md`), the two reviews
(`2026-10-04T0109-code_reviewer-p13f-wacc-debt.md`,
`2026-10-04T0115-code_reviewer-p13f-wacc-debt-r2.md`), and `.claude/agents/tester.md`
from its first section.

## What to do

1. A negative `total_debt` (300, −50) raises `ValueError` naming
   `balance_sheet.total_debt`, with and without an override. The message claims no cause.
2. A negative single debt line under a positive total (short-term −50, long-term 100)
   raises `ValueError` naming that line.
3. `balance_sheet=None` raises `ValueError` naming `balance_sheet`, through
   `calculate_wacc` with and without an override, and through `cost_of_debt_with_source`.
4. An infinite value stops by name: a debt line, `market_cap`, `cost_of_equity`, a
   cost-of-debt override and a tax override.
5. A NaN interest expense with zero debt and no override raises `ValueError` naming
   `income_statement.interest_expense`.
6. For (300, 100), derive the weights and the WACC by hand and assert them.
7. **Do not lock item 38b (a).** An override with zero debt lines and interest still
   returns weights 1.0 / 0.0. The user is deciding its replacement. Do not assert that
   behaviour either way.

## Files in scope

- `tests/unit/test_wacc.py`

**Nothing else.** The P13g tester is writing `tests/unit/test_claude_extractor.py`. The
write guard refuses scratch paths inside the repository, so work in the session
scratchpad: `/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/5a3eb59a-dd70-43de-8ee8-c16bbd7dd61e/scratchpad/p13f_tester/`.
Export `git archive f6da3e9`, copy in `analysis/wacc.py` and your test file. Never
`rm -rf` outside your directory, and do not stash or reset the shared tree. Set
`PYTHONDONTWRITEBYTECODE=1` when you run mutants, or a stale `.pyc` can hide a survivor.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form on the isolated tree | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite on the isolated tree | exactly the 2 known `*_rule3_red.py` failures | `.venv/bin/python -m pytest -q` |
| 3 | each stop is locked | each of steps 1 to 5 has a test that turns red when its check is removed | mutants in a scratch copy |
| 4 | two counts | accuracy and coverage, as `tester.md` requires | its "Report two counts" section |

## Backlog items this unit is NOT fixing

- Item 38b (a), items 22 and 37. Do not lock their current behaviour.
- Five stale line citations in `test_wacc.py` (`:164`, `:367`, `:427`, `:489`, `:581`) may be corrected, since you own the file.
