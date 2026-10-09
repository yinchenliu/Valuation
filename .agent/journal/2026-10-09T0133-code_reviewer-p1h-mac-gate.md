---
agent: code_reviewer
assignment: P1h-mac-gate
round: 1
verdict: approved
---

# Review of P1h-mac-gate, round 1

Programmer entry: `.agent/journal/2026-10-09T0121-programmer-p1h-mac-gate.md`

## The guard checks

Run over the assignment's **Files in scope**, not over the whole repository.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean (`ingestion/session_extraction.py`) |
| lookup with a fallback — `.get(k, 0)` | clean (`ingestion/session_extraction.py`) |
| bare or-default — `or 0.0` | clean (`ingestion/session_extraction.py`) |
| money field defaulted to zero — `: float = 0.0` | clean (`ingestion/session_extraction.py`) |
| `**kwargs` on a calculation function | clean (`ingestion/session_extraction.py`) |
| `getattr(` on a name from outside the file | clean (`ingestion/session_extraction.py`) |
| dict of functions keyed by data | clean (`ingestion/session_extraction.py`) |
| model client imported outside `ingestion/` | clean (`models/`, `analysis/`, `api/`) |

## Rule 3, by reading

The greps catch the four written forms. This table catches the rest. For every value
the unit reads, ask: if it were missing, what happens?

| Value | Stops and names it? | Evidence |
|---|---|---|
| `stream.errors` | Yes. Stops with `TypeError` and names the read value, expected handler name type, and stream class and repr | `ingestion/session_extraction.py:1223-1234` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean (not applicable; stream wrapper does not handle monetary values) |
| percentages converted at the route boundary, once | clean (not applicable) |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean (`if not isinstance(previous, str):` explicitly checks type) |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean (no changes to `analysis/`) |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | the test that found the defect passes, unchanged | `1 passed in 0.03s` | `1 passed in 0.03s` | yes |
| 2 | that test file did not change | empty output | empty output (`git diff main -- tests/unit/test_session_extraction_console.py`) | yes |
| 3 | the gate form is green at three orders | seeds 7, 1234, 99 all `1586 passed, 0 failed, 0 skipped` | seed 7: `1586 passed in 32.76s`<br>seed 1234: `1586 passed in 33.06s`<br>seed 99: `1586 passed in 32.93s`<br>(all `0 failed, 0 skipped`) | yes |
| 4 | the full suite fails only the two tests that are red on purpose | `2 failed, 1586 passed` (`test_projector_rule3_red.py`, `test_routes_session_rule3_red.py`) | `2 failed, 1586 passed in 33.08s` (same two tests) | yes |
| 5 | lint unchanged | `4 errors` (all BLE001) | `4 errors` (all BLE001, none in touched files) | yes |
| 6 | types unchanged | `2 errors in 2 files` | `Found 2 errors in 2 files` (`projector.py:395`, `routes_upload.py:28`) | yes |
| 7 | rule 3 census unchanged | `64` | `64` | yes |
| 8 | the unit stayed in scope | only `ingestion/session_extraction.py` and programmer journal | `M ingestion/session_extraction.py`, untracked journal | yes |
| 9 | a test that kills the defect on Python 3.11 | tester ownership | reserved for tester subagent | yes |

## Findings

None.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 53 — `_NRI_SCHEMA` private name import | `ingestion/session_extraction.py:31` | no |
| 60 — `plan` message on fiscal year | `ingestion/session_extraction.py:165` | no |
| 95 — unreachable fiscal-year check | `ingestion/session_extraction.py:163` | no |
| 120 — repeated `[MERGE]` summary | `ingestion/session_extraction.py:1016` | no |
| 123, 125 — discarded bool / surrogateescape | `ingestion/session_extraction.py:1210-1239` | no |
| 146 — absolute PDF paths in session | `ingestion/session_extraction.py:151` | no |

## Earlier findings — re-reviews only

Not applicable (round 1).

## Verdict

`approved`

The change is minimal, correct, and strictly within scope. The stop message at `ingestion/session_extraction.py:1233-1234` explicitly interpolates `{type(stream).__name__}` while preserving `{stream!r}`. All guard checks pass, and all gate measurements match expected results.
