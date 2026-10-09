---
agent: programmer | tester
assignment: <id>
round: 1
status: complete | partial | blocked | failed
files_touched: [<paths>]
verdict: <testers only: pass | fail | blocked>
---

# <unit id> — <one line>

> **Open this file before your first command. Fill it as each result lands.**
> An agent stopped mid-run with everything in context and nothing on disk has
> done no work.

## What I did

<One paragraph. What changed, and why.>

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | | pass / fail | the command and its output |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|

**A code change made to reach a target number, rather than on a reason, is
forbidden.** If you changed something because it made a figure look right, say so
here and expect the finding.

## Rule 3 — what stops, and what does not

For every value this unit reads, one row. This is the table the reviewer checks first.

| Value read | If it were missing | Evidence |
|---|---|---|
| | stops and names `<field>` / **defaults to `<x>`** | `file:line`, or the command that showed the stop |

**A "defaults to" row is a finding against your own unit.** Write it anyway.

## Measurements

<Suite counts before and after, as failure SETS not counts. Lint. Types. Any figure
this unit moved, with the input that produced it.>

## Expected values — testers only

| Assertion | Expected | Source | How |
|---|---|---|---|
| | | hand arithmetic / closed-form identity / filing page / stated requirement | the arithmetic, the identity, page `<n>`, or the `file:line` that states it |

**Never "what the code returned", and never the code's own literal.** An assertion whose
source is not one of the four kinds in `docs/5-testing/strategy.md`, section 1, does not
count, and the unit does not pass.

**Two counts, with their units:**

| Count | Value | Command |
|---|---|---|
| assertions per source | hand arithmetic `<n>`, identity `<n>`, filing page `<n>`, stated requirement `<n>` | — |
| coverage of the files in scope | `<file>`: statements `<n>` of `<n>`, branches `<n>` of `<n>` | the `--cov=<module> --cov-branch` command, and its output line |

**The five checks** (`.claude/agents/tester.md`):

| # | Check | Result |
|---|---|---|
| 1 | every test calls the code it is about | |
| 2 | every test holds on Python 3.11 and 3.14 | |
| 3 | no fallback asserted: the search output, and the reason for each hit | |
| 4 | every source label is true | |
| 5 | coverage measured over the files in scope | |

**The mutation**, run in a scratch worktree outside the repository:

| Mutation | `file:line` | Result with it | Result without it | Tests that went red |
|---|---|---|---|---|

## What I did not do

<Anything in the assignment left undone, and why. Anything found and deliberately not
fixed, with who should own it.>

## Findings for the orchestrator

<Things nobody owns yet. Be specific enough that an assignment could be written from
this line alone.>
