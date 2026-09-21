---
id: <PHASE>-<slug>
phase: <n> — <name from docs/8-build/phases.md>
agent: programmer | tester
depends_on: [<unit ids that must be accepted first>]
---

# <One line: what this unit does>

## Objective

<What is true when this unit is done. Two or three sentences. State the fact that
forced the unit before stating what to do about it.>

## What is already true — verify, do not redo

<Every measurement the orchestrator has already taken, with the command that
reproduces it. If one disagrees, the programmer stops and reports the disagreement
rather than editing.>

## What to do

<Numbered steps. Each one names its reason — a document section, a rule, an
accounting convention, or a filing page. Never a target number on its own.>

## Files in scope

- `<exact path>`

**Nothing else.** Work outside this list is a review finding, even if the change is
good.

## Out of scope

- <path, and one line saying who owns it instead>

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | | | the command whose output proves it |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/<file>.md` — <what it gives this unit>
- `10K_filings/<file>.pdf` page <n> — <the figure it holds>
- <accounting convention, named> — <what it requires>

## Known open items

- <anything the orchestrator knows is unresolved, so the programmer does not
  rediscover it and report it as new>

## Backlog items this unit is NOT fixing

<Entries from docs/9-reference/refactor-backlog.md that sit in files this unit
touches but which the unit deliberately leaves alone. Naming them here stops the
reviewer raising them as new findings, and stops the programmer widening its own
scope to fix them.>
