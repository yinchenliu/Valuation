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

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| | | hand arithmetic (show it) / closed-form identity / filing page `<n>` |

**Never "what the code returned".** An assertion whose source is not one of the three
named kinds does not count, and the unit does not pass.

**Two counts, with their units:** accuracy (of assertions), coverage (of functions,
then branches).

## What I did not do

<Anything in the assignment left undone, and why. Anything found and deliberately not
fixed, with who should own it.>

## Findings for the orchestrator

<Things nobody owns yet. Be specific enough that an assignment could be written from
this line alone.>
