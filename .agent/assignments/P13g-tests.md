---
id: P13g-tests
phase: 13 — silent defects first, wave 2
agent: tester
depends_on: [P13g-pass2-unread]
---

# Lock the stop when route A cannot read Pass 2 after its retry

## Objective

`P13g-pass2-unread` (approved in round 1, not yet committed) closes backlog item 50.
When the Pass 2 reply cannot be parsed on the retry either, `_run_nri_pass` now raises a
`ValueError` that names the ticker, the company, the Pass 1 years and both parse errors,
where it used to return `[]`. No test locks it. No test turned red.

Read first: `.agent/assignments/P13g-pass2-unread.md`, the programmer's entry
`.agent/journal/2026-10-04T0102-programmer-p13g-pass2-unread.md`, the review
`.agent/journal/2026-10-04T0130-code_reviewer-p13g-pass2-unread.md`, and
`.claude/agents/tester.md` from its first section.

**Make no API call.** `.env` holds a live key. Stub `_call_llm`, and make every road to a
network connection raise, as the programmer and the reviewer did. Never print a key value.

## What to do

1. Two unparseable replies: `ValueError`, naming the ticker, the company and both parse
   errors. Assert that exactly two calls were made.
2. A malformed first reply and a parseable second reply with items: the items are
   returned.
3. A parseable reply `{"non_recurring_items": []}`: `[]`, on the first call.
4. Do not lock the review's F1 (an `OverflowError` or `RecursionError` from the retry
   escapes unnamed) or F2 (bad first replies that stop with no retry). They are backlog
   items.

## Files in scope

- `tests/unit/test_claude_extractor.py`

**Nothing else.** Two other testers are writing `tests/unit/test_dcf.py` and
`tests/unit/test_projector_sources.py`. Work in your own scratch area. If the write guard
refuses a path inside the repository, use the session scratchpad outside it. Export
`git archive f6da3e9`, copy in `ingestion/claude_extractor.py` and your test file. Never
`rm -rf` outside your own directory, and do not stash or reset the shared tree.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form on the isolated tree | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite on the isolated tree | exactly the 2 known `*_rule3_red.py` failures | `.venv/bin/python -m pytest -q` |
| 3 | the stop is locked | the step 1 test turns red when the old `return []` is put back | a mutant in a scratch copy |
| 4 | no API call | every network road raises during the new tests | the guard and its control |
| 5 | two counts | accuracy and coverage, as `tester.md` requires | its "Report two counts" section |

## Backlog items this unit is NOT fixing

- The review's F1 and F2 (new backlog items), items 51, 61, 63, 64.
