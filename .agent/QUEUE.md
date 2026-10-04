# The work queue

**The bus between the two teams** ([AGENTS.md](../AGENTS.md), "Two teams"). One row per
unit, in build order. The state says whose turn it is. Change only the states your
team owns.

| State | Set by | Means |
|---|---|---|
| `planned` | overall lead | in the plan; no assignment yet |
| `ready` | overall lead | the assignment is written; the build lead may start |
| `building` | build lead | its programmer, reviewer or tester is at work |
| `blocked` | build lead | a question waits in the assignment, under `## Questions for the overall lead` |
| `for acceptance` | build lead | committed, tester passed, `## Handoff` written; the build lead stops |
| `rework` | overall lead | findings in `## Overall lead review`; the build lead starts again |
| `accepted` | overall lead | reviewed, re-measured, recorded in `STATUS.md` |

**One unit is `ready`, `building` or `rework` at a time**, unless the Notes column says
that two units may run in parallel.

| # | Unit | Assignment | State | Backlog items | Notes |
|---|---|---|---|---|---|
| 1 | `P14b-pass2-units` | [P14b-pass2-units.md](assignments/P14b-pass2-units.md) | `accepted` | 77 | the user's decision "fix 77a", 2026-10-04. Session format v4 |
| 2 | `P14b-reasoning` | [P14b-reasoning.md](assignments/P14b-reasoning.md) | `accepted` | 81 | rule 1 option 0: route A sends adaptive thinking at a named effort, streamed, with room to finish; the setting is shown. No format change |
| 2b | `P15a-two-routes` | [P15a-two-routes.md](assignments/P15a-two-routes.md) | `ready` | — | the user's decisions of 2026-10-04 ("1a, 2a"): route A through the Gemini API only, the default provider; Claude only through a Claude Code session (route B); no Foundry, no Anthropic API, no DeepSeek. Start it |
| 2c | `P14b-note-figures` | [P14b-note-figures.md](assignments/P14b-note-figures.md) | `planned` | — | rule 1 option B, with check B1 (the user's decision of 2026-10-04). Assignment written; `ready` when `P15a-two-routes` is accepted |
| 3 | `P14b-row-reasons` | not written | `planned` | — | rule 1 option A: a reason for each printed row, shown on both pages. A format change, and Walmart must be extracted again |
| 4 | `P14c-layout-facts` | not written | `planned` | 10 | rule 1 option C: a layout fact the filing states, page-checked; the D&A decision moves into `analysis/` |
| 5 | Phase 3 | not written | `planned` | 7, 49, 72 | one pipeline for `cli.py` and the web app |
