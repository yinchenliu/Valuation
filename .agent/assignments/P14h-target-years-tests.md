---
id: P14h-target-years-tests
phase: 14 — the Pass 1 and Pass 2 roles
agent: tester
depends_on: [P14h-target-years]
team: B (worktree `Valuation-wt/team-b`, branch `unit/team-b`)
---

# Verifying target_years prompt builder stops and prompt invariance (item 133)

## Objective

Verify that `_build_financials_prompt` (Pass 1) and `_build_nri_prompt` (Pass 2) in `ingestion/claude_extractor.py` reject an empty `target_years` list `[]` by raising `ValueError` naming `target_years` (Rule 3, backlog item 133).
Verify that `target_years=None` and non-empty `target_years` lists generate exact expected prompt text derived by hand from the prompt builder templates, and that all six real filing prompt hashes remain identical.
Verify that these tests call the production code directly (preventing backlog item 148) and kill the pre-item-133 code (`if target_years:` without stop).

## What is already true — verify, do not redo

- `_build_financials_prompt` and `_build_nri_prompt` test `target_years is not None` and raise `ValueError` on empty list.
- The six real prompts on `extractions/WMT.json` match the hashes in `P14h-target-years.md`:
  - filing 0 pass 1: `cbf26b0a876034f6`, pass 2: `024bd96701e72481`
  - filing 1 pass 1: `c401b7bb3096592c`, pass 2: `9391f61bfa21ac43`
  - filing 2 pass 1: `4aa84c989703f3ce`, pass 2: `cc61ac590ca169f0`
- Gate form on `main` at `84c0462`: 1 failed, 1602 passed at seeds 7, 1234, 99 (known failure item 145 on macOS).

## What to do

1. Create `tests/unit/test_p14h_target_years.py`.
2. Write tests verifying:
   - Calling `_build_financials_prompt(target_years=[])` raises `ValueError` whose message names `target_years` (Criterion 2).
   - Calling `_build_nri_prompt(is_summary="...", target_years=[])` raises `ValueError` whose message names `target_years` (Criterion 3).
   - Calling each builder with `target_years=None` produces the all-years prompt text, asserted against hand-derived literal text.
   - Calling each builder with non-empty `target_years` (e.g. `[2024]`, `[2023, 2024]`) produces the specific-years prompt text, asserted against hand-derived literal text.
   - Calling each builder with `include_bs=True` and `include_bs=False` (for Pass 1) produces the expected balance sheet instructions.
   - Verify the six real prompt hashes match the baseline table (Criterion 4).
   - Every assertion must be derived by hand or closed-form identity; none from running code output.
   - Every test must call the production code directly (item 148).
3. Test mutation (Criterion 6):
   - In a scratch copy or temporary mutation, test that reverting to `if target_years:` without the stop makes the empty-list tests fail (red).
   - Verify tests pass (green) on the actual codebase.
4. Measure and report:
   - Accuracy and coverage counts.
   - Full gate at seeds 7, 1234, 99.
   - Lint (`ruff check .`), types (`mypy`), and Rule 3 census (64).
   - Scope diff.

## Files in scope

- `tests/unit/test_p14h_target_years.py` (tester, new file)
- `.agent/journal/<timestamp>-tester-p14h-target-years.md`

**Nothing else.** You may not modify `ingestion/claude_extractor.py` or any other implementation code.

## Out of scope

- `ingestion/claude_extractor.py` (implementation is done and approved).
- The four record files (`STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md`, `docs/9-reference/refactor-backlog.md`).

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | no truthiness test of `target_years` is left in the two builders | no match | `grep -n "if target_years:" ingestion/claude_extractor.py` |
| 2 | an empty list stops Pass 1 | `ValueError` naming `target_years` | test calling `_build_financials_prompt([])` |
| 3 | an empty list stops Pass 2 | `ValueError` naming `target_years` | test calling `_build_nri_prompt("<summary>", [])` |
| 4 | the six real prompts are unchanged | all six hashes match baseline | command in assignment |
| 5 | `None` and a one-element list build the same text as on `main` | equal strings | tests with hand-derived expected text |
| 6 | the tests in 2 and 3 kill the old code | red with `if target_years:`, green without | mutation report and counts |
| 7 | the gate form at three orders | failed set equals `main`'s (item 145 on macOS), passed count increases by new tests | seeds 7, 1234, 99 |
| 8 | lint, types, census unchanged | 4 `BLE001` errors, 2 types errors in 2 files, census 64 | gate commands |
| 9 | unit stayed in scope | only `ingestion/claude_extractor.py`, `tests/unit/test_p14h_target_years.py`, assignments, journal entries | `git diff --name-only main...HEAD` |

## Citations

- `ingestion/claude_extractor.py:2328-2358`, `_build_financials_prompt`
- `ingestion/claude_extractor.py:2411-2430`, `_build_nri_prompt`
- `docs/2-rules/rules.md`, rule 3
- `.agent/assignments/P14h-target-years.md`
