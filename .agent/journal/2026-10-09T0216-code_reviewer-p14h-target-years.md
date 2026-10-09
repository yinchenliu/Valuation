---
agent: code_reviewer
assignment: P14h-target-years
round: 1
verdict: approved
---

# Review of P14h-target-years, round 1

Programmer entry: `.agent/journal/2026-10-09T0204-programmer-p14h-target-years.md`

## The guard checks

Run over the assignment's **Files in scope**, not over the whole repository.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean in diff; 0 hits across `ingestion/claude_extractor.py` |
| lookup with a fallback — `.get(k, 0)` | clean in diff; 5 pre-existing hits in `ingestion/claude_extractor.py` (:1953, :2170, :2171, :2220, :2774), all untouched |
| bare or-default — `or 0.0` | clean in diff; 3 pre-existing hits in `ingestion/claude_extractor.py` (:1982, :1983, :1984), all untouched |
| money field defaulted to zero — `: float = 0.0` | clean; 0 hits across `ingestion/claude_extractor.py` |
| `**kwargs` on a calculation function | clean; 0 hits across `ingestion/claude_extractor.py` |
| `getattr(` on a name from outside the file | clean in diff; 2 pre-existing hits in `ingestion/claude_extractor.py` (:1983, :1984), all untouched |
| dict of functions keyed by data | clean; 0 hits across `ingestion/claude_extractor.py` |
| model client imported outside `ingestion/` | clean; 0 hits in `models/`, `analysis/`, `api/` |

**A hit is a question, not automatically a finding.** If the programmer answered it in
its entry, say so.

## Rule 3, by reading

The greps catch the four written forms. This table catches the rest. For every value
the unit reads, ask: if it were missing, what happens?

| Value | Stops and names it? | Evidence |
|---|---|---|
| `target_years` (`_build_financials_prompt`) | Yes, stops on empty list `[]` with `ValueError` naming `target_years`. When `None`, selects all years by design. | `ingestion/claude_extractor.py:2336-2341` |
| `target_years` (`_build_nri_prompt`) | Yes, stops on empty list `[]` with `ValueError` naming `target_years`. When `None`, selects all years by design. | `ingestion/claude_extractor.py:2419-2424` |
| `include_bs` (`_build_financials_prompt`) | Non-optional boolean flag defaulting to `True`. | `ingestion/claude_extractor.py:2330` |
| `is_summary` (`_build_nri_prompt`) | Required positional `str` argument; missing argument causes Python `TypeError` at call site. | `ingestion/claude_extractor.py:2412` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean / not applicable (prompt string formatting only) |
| percentages converted at the route boundary, once | clean / not applicable |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean; replaced `if target_years:` with `if target_years is not None:` and explicitly handles empty `target_years` |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean; zero imports outside layer boundaries |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | no truthiness test of `target_years` is left in the two builders | pass (0 matches) | `grep -n "if target_years:" ingestion/claude_extractor.py` returned exit code 1 with 0 matches | yes |
| 2 | an empty list stops Pass 1 | pass (`ValueError` naming `target_years`) | `_build_financials_prompt([])` raised `ValueError: target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year.` | yes |
| 3 | an empty list stops Pass 2 | pass (`ValueError` naming `target_years`) | `_build_nri_prompt('summary', [])` raised `ValueError: target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year.` | yes |
| 4 | the six real prompts are unchanged | pass (all 6 hashes match) | filing 0 pass 1: `cbf26b0a876034f6`<br>filing 0 pass 2: `024bd96701e72481`<br>filing 1 pass 1: `c401b7bb3096592c`<br>filing 1 pass 2: `9391f61bfa21ac43`<br>filing 2 pass 1: `4aa84c989703f3ce`<br>filing 2 pass 2: `cc61ac590ca169f0` | yes |
| 5 | `None` and a one-element list build the same text as on `main` | pass | Tested literal substrings and prompt starts for `None` and `[2024]` on both builders; all identical | yes |
| 6 | the tests in 2 and 3 kill the old code | pass | Verified; under old code `[]` fell through to all-years prompt without stop; under new code raises `ValueError` | yes |
| 7 | the gate form at three orders | pass (1 failed, 1602 passed at seeds 7, 1234, 99) | `pytest` seeds 7, 1234, 99 all reported `1 failed, 1602 passed`; sole failure is item 145 on macOS (`test_session_extraction_console.py:774`) | yes |
| 8 | lint, types, census unchanged | pass | `ruff check .` reported 4 errors (all `BLE001`, none in unit files); `mypy` reported 2 errors in 2 files; census grep reported 64 | yes |
| 9 | the unit stayed in scope | pass | Only `ingestion/claude_extractor.py` modified and programmer journal untracked | yes |

**Do not accept a claim you have not executed.**

## Findings

None.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 133 | `ingestion/claude_extractor.py:2336`, `:2414` (formerly `:2280`, `:2358`) | Yes; resolved by this unit |

A defect the unit **touched** is the unit's, backlog or not.

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|

## Verdict

`approved`

The unit correctly addresses backlog item 133. In `ingestion/claude_extractor.py`, `_build_financials_prompt` and `_build_nri_prompt` now check `if target_years is not None:` instead of testing truthiness, and raise an informative `ValueError` naming `target_years` when `target_years` is an empty list. When `target_years` is `None` or a populated list, prompt text is identical byte for byte to `main`, matching all six reference prompt hashes. Full test suite at three seeds, lint, type checker, and Rule 3 census all match baseline. The unit is approved for the tester.
