---
agent: code_reviewer
assignment: P11a-printed-lines
round: 2
verdict: approved
---

# Review of P11a-printed-lines, round 2

Programmer entry: `.agent/journal/2026-10-03T1048-programmer-p11a-printed-lines-r2.md`.
Decisions reviewed against: the "Round 2" section of `.agent/assignments/P11a-printed-lines.md`.
These are the orchestrator's decisions of 2026-10-03, inside the user's option A.
Round 1: `.agent/journal/2026-10-03T1046-code_reviewer-p11a-printed-lines.md`.
Diff: `git diff 631cf45` over the eight files in scope. The orchestrator confirmed these
modified files are its own and not this unit's: `.claude/skills/extract-filing/SKILL.md`,
`.agent/journal/INDEX.md`, `.agent/assignments/P11a-printed-lines.md` and
`docs/9-reference/refactor-backlog.md` (item 59). I did not review them.

## The guard checks

Every line the diff now adds (878 lines, from `git diff -U0 631cf45` per code file,
`/tmp/p11a_rev/added_r2.txt`) is clean against all six patterns. No model client exists
outside `ingestion/`. The whole-file hits are the untouched lines listed in round 1.

## Rule 3, by reading — the rows that changed

| Value | Stops and names it? | Evidence |
|---|---|---|
| `total_assets` / `total_liabilities_and_equity` `[]` | `None`, shown as `FAIL: not extracted`, counted as a failure. No printed 0, no gap | `check r2_empty_total.json` exit 1: `Total Assets (none) 284,668 FAIL: not extracted`. Page: `not extracted` / `—` / `<strong>FAIL: not extracted</strong>`. CLI: `printed not extracted ... FAIL: not extracted`. Same for L+E (`r2_empty_le.json`) |
| `operating_income` `[]` | `None`; the check is skipped and labelled. It feeds no figure | `r2_empty_oi.json` exit 0: `2025 Oper. Income (none) 29,348 SKIP: not printed (the filing prints no operating_income row)` |
| `net_income` `[]` | **stops**, in both routes | Route B exit 2: `filings[0] (Walmart ...pdf), year 2024, 'net_income': is [], ...`. Route A (stubbed): 3 calls, each carrying the PDF, then `Pass1ShapeError`. It never reaches `CashFlowStatement.net_income` (`pass1_problems` runs before any figure, `claude_extractor.py:580`) |
| a `value` too large for a float | stops, naming field, year and line | `r2_huge.json` exit 2: `year 2026, 'capex': line 0: 'value' must be a finite JSON number, got an integer of 1329 bits, too large for a float.` |
| a `value` over 4,300 digits | stops, inside `json`, without naming the line | exit 2, `STOPPED — Exceeds the limit (4300 digits) ...`. A stop, not a number. N2 |

`check_row_from_printed_lines` (`:505`) is one named, typed function with one meaning:
"a check row's printed figure, or None". That satisfies rule 2. `figure_from_printed_lines`
is unchanged, so an empty list on a component field still reads 0, as the assignment says.

## Units and boundaries

Unchanged from round 1. The new `_CheckFailure` message now prints the 0.5%
income statement threshold ("the check allows 0.5%"), which fixes the unprinted status
threshold noted under round 1's F5.

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | no prompt sentence computes | 0 hits | `grep -n -i "sum of\|combine\|minus\|adjust catch"` gives 0 lines. The new prompt text at `:183,188,217-218,320-322` says what `[]` means and asks for no computation | yes |
| 2 | both routes equal | ALL EQUAL | `r3_equal.py` behind my client guard: `ALL EQUAL`; 4 and 8 calls, 2 retries each, each carrying the PDF | yes |
| 3 | capex 26,695 | pass | still holds: `-26695.0` in the cash flow statement (round 2 changed no summing) | yes |
| 4 | balanced sheet OK | pass | `check wmt_v2.json` exit 0, `+0 OK` on both totals | yes |
| 5 | dropped row FAIL, kept | pass | `check r2_drop.json` exit 1, `+4,124 FAIL`. Route A returns the figures after 3 calls | yes |
| 6 | stops named | pass | the round 1 cases still stop as before. The new `net_income []` and `10**400` cases stop and are named | yes |
| 7 | v1 stops | pass | the v1 refusal code is unchanged since round 1, and the 9 v1 tests still fail on it | yes |
| 8 | census | 67 | 67 | yes |
| 9 | red list | the same 40 | By JUnit set, round 2's failing set is **identical** to round 1's (`same 40: True`), and the set of tests run is identical too. By reason: 28 on the old shape, 9 on the v1 refusal, 2 on `check` exiting 2, 1 on the key tuple | yes |
| 10 | lint, types | ruff 5, mypy 10 | ruff `Found 5 errors.` (the same five BLE001; `claude_extractor` moved to `:1582`). mypy `Found 10 errors in 4 files` | yes |

## Findings

No `blocker`, `major` or `minor` finding.

### N1 — The docstring says "five rows" and lists four · `note`

**Evidence:** `ingestion/claude_extractor.py:508`, "For the five rows read only to check
the reading (gross_profit, operating_income, total_assets, total_liabilities_and_equity;
net_income is a figure ...)". Say "four", or the tester will wonder which one is missing.

### N2 — A value of more than 4,300 digits stops without naming the line · `note`

**Evidence:** `check /tmp/p11a_rev/r2_digits.json` exits 2 with
`STOPPED — Exceeds the limit (4300 digits) ...`. It stops inside `json.loads`, before any
line is checked. No figure is produced, so no rule is broken. The programmer recorded
it and declined it, which is reasonable for an input no filing produces.

## Pre-existing, already recorded — not findings against this unit

Unchanged from round 1: items 1, 8, 10, 11 and 44, on the same lines, untouched except
for item 10's line, which was rewritten in round 1 to drop its defaults.

## Earlier findings — re-review

| # | Outcome | Note |
|---|---|---|
| F1 | fixed | an empty printed total is `None`, `FAIL: not extracted`, in `check`, the CLI and the page; no printed 0, no gap. `data-contract.md:165` records it |
| F2 | fixed | per the orchestrator's decisions 2 and 3: an empty `operating_income` is SKIP "not printed"; an empty `net_income` stops in both routes. No path puts an unprinted 0 into the cash flow |
| F3 | fixed | `extraction.md:184` now says each shape or check retry re-sends the whole PDF, up to three times Pass 1's input tokens, and that the JSON repair retry sends none |
| F4 | fixed | `_is_finite_number` returns False on OverflowError (`:426-429`); `_shown` describes the value by its bit length |
| F5 | fixed | the dead `WARN` branch is gone; the remaining `WARN` strings (`:1033,1571,1583`) are unrelated |
| F6 | fixed | `data-contract.md:134-135` now says "an empty list, `[]`, which reads as `0`" |
| F7 | fixed | `_CheckFailure` holds two wordings. Route A's check retry sends `retry_message`. In the stubbed runs (dropped row, empty total, operating income off by 900), the retry text before the JSON contains no number but the year `2026`. Route B's `check` keeps `diff=+4,124`. The model still receives the JSON values, as decision 6 accepts; backlog item 59 holds the real defence |

## Verdict

`approved`

Each round 1 finding is fixed as the orchestrator's round 2 decisions specify, and I
verified each by execution in both routes, the CLI and the page. All ten done-criteria
hold. The 40 red tests are the same set as round 1, and each fails only on the old
fixture shape, so a tester can rewrite them. N1 and N2 are notes and need no further round.
