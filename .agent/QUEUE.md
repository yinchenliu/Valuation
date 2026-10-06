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

**The order, on the user's direction of 2026-10-04:** route B is the main route and route A
an option, so defect fixes come first, then route A refinements, then new features.

**Build mode: one team (Claude Code), from 2026-10-05, until the user says to return to two
teams.** The user's words: "antigravity is stopped and won't continue after refresh unless i
tell it to. so you can takeover the build. i will ask you to change to 2 teams once
antigravity token is back". The overall lead also sets the build lead's states and runs
the programmer, code reviewer and tester as Claude subagents, by the loop in `AGENTS.md`.

**One unit is `ready`, `building` or `rework` at a time**, unless the Notes column says
that two units may run in parallel.

**The user confirmed one-team mode on 2026-10-05** ("I want the one team framework where
you are the main agent, and will dispatch subagents to finish the build"). The overall
lead writes every assignment, dispatches the programmer, code reviewer and tester as
Claude subagents, and reports to the user only.

| # | Unit | Assignment | State | Backlog items | Notes |
|---|---|---|---|---|---|
| 0 | `P1b-windows-gate` | [P1b-windows-gate.md](assignments/P1b-windows-gate.md) | `accepted` | 93 | the build moved to the Windows machine, where 14 tests fail for two reasons that no product defect causes: a `_no_socket` fixture that breaks the Windows asyncio self-pipe (13), and an argparse message that differs between Python 3.11 and 3.14 (1). A tester unit, `tests/` only. **Runs in parallel with `P3b-pipeline-stops`: disjoint files** |
| 1 | `P14b-pass2-units` | [P14b-pass2-units.md](assignments/P14b-pass2-units.md) | `accepted` | 77 | the user's decision "fix 77a", 2026-10-04. Session format v4 |
| 2 | `P14b-reasoning` | [P14b-reasoning.md](assignments/P14b-reasoning.md) | `accepted` | 81 | rule 1 option 0: route A sends adaptive thinking at a named effort, streamed, with room to finish; the setting is shown. No format change |
| 3 | `P15a-two-routes` | [P15a-two-routes.md](assignments/P15a-two-routes.md) | `accepted` | — | the user's decisions of 2026-10-04 ("1a, 2a"): route A through the Gemini API only, the default provider; Claude only through a Claude Code session (route B); no Foundry, no Anthropic API, no DeepSeek. Start it |
| 4 | `P14b-note-figures` | [P14b-note-figures.md](assignments/P14b-note-figures.md) | `accepted` | — | rule 1 option B, with check B1 (the user's decision of 2026-10-04). Start it |
| 5 | `P14d-finance-leases` | [P14d-finance-leases.md](assignments/P14d-finance-leases.md) | `accepted` | 83 | the user's decision "83a" (2026-10-04): finance lease obligations are debt, operating lease obligations are not; the schema says so. Start it |
| 6 | `P3a-one-pipeline` | [P3a-one-pipeline.md](assignments/P3a-one-pipeline.md) | `accepted` | 7 | Phase 3, part 1: `pipeline.py` holds the valuation steps once; `cli.py` and the web routes call it; no number moves. One-team mode |
| 6b | `P3b-pipeline-stops` | [P3b-pipeline-stops.md](assignments/P3b-pipeline-stops.md) | `accepted` | 49, 72 | Phase 3, part 2: a filing with no year stops and names the file, in one function both entry points call (49); the `total_debt` display line in `cli.py` reads `pipeline.ValuationRun` instead of a conditional zero (72). The share count fallback is already gone (`P3a`). **Runs in parallel with `P1b-windows-gate`: disjoint files** |
| 6c | `P1c-test-network-copies` | [P1c-test-network-copies.md](assignments/P1c-test-network-copies.md) | `accepted` | 93 | the two copies of the no-network rule that survived `P1b` and still refuse the loopback address. A tester unit, `tests/` only, so it conflicts with nothing |
| 6d | `P3c-one-number` | [P3c-one-number.md](assignments/P3c-one-number.md) | `building` | 87, 92, 6, 97 | the user's decision "1a" of 2026-10-05: a blank ratio field means "derive it", and the derived figure moves from the form's `value` attribute to its `placeholder`. **The programmer finished round 1; the code reviewer is next.** 22 tests are red in the working tree: 2 assert the deleted prefill, 20 read an error box through a regex that forbids an attribute. Its tester unit repairs them |
| 6e | `P1d-skipped-filings` | [P1d-skipped-filings.md](assignments/P1d-skipped-filings.md) | `accepted` | 101, 102 | a `skipif` guard named `10K_filings/Walmart/` and the folder is `10K_filings/WMT/`, so the real-filing check for check B1 skipped on a machine that holds the filing. A tester unit, `tests/` only |
| 7 | `P14c-layout-facts` | not written | `planned` | 10 | defect (item 10), through rule 1 option C: a layout fact the filing states, page-checked; the D&A decision moves into `analysis/` |
| 8 | `P15b-gemini-flash` | [P15b-gemini-flash.md](assignments/P15b-gemini-flash.md) | `planned` | 82 | the user's decision of 2026-10-04: route A's default model becomes `gemini-3.8-flash`; the CLI cache key names the model ID. Assignment written. **Deferred by the user, 2026-10-04:** "focus on fixing the defects first before refine route A" |
| 9 | `P14b-row-reasons` | not written | `planned` | — | feature, after the defects: rule 1 option A: a reason for each printed row, shown on both pages. A format change, and Walmart must be extracted again |
