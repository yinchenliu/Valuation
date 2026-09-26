---
agent: code_reviewer
assignment: <id>
round: 1
verdict: approved | changes_requested | blocked
---

# Review of <unit id>, round <n>

Programmer entry: `.agent/journal/<entry>.md`

## The guard checks

Run over the assignment's **Files in scope**, not over the whole repository.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean / hit at `file:line` |
| lookup with a fallback — `.get(k, 0)` | |
| bare or-default — `or 0.0` | |
| money field defaulted to zero — `: float = 0.0` | |
| `**kwargs` on a calculation function | |
| `getattr(` on a name from outside the file | |
| dict of functions keyed by data | |
| model client imported outside `ingestion/` | |

**A hit is a question, not automatically a finding.** If the programmer answered it in
its entry, say so.

## Rule 3, by reading

The greps catch the four written forms. This table catches the rest. For every value
the unit reads, ask: if it were missing, what happens?

| Value | Stops and names it? | Evidence |
|---|---|---|

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | |
| percentages converted at the route boundary, once | |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|

**Do not accept a claim you have not executed.**

## Findings

### F1 — <one line> · `blocker` | `major` | `minor` | `note`

**Evidence:** `file:line`, or the command and its output.
**Rule or document:** which one it violates.
**What would fix it:** one sentence.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|

A defect the unit **touched** is the unit's, backlog or not.

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| F1 | fixed / not_fixed / disputed / withdrawn | |

## Verdict

`approved` | `changes_requested` | `blocked`

<One paragraph. If `changes_requested`, name the findings that block.>
