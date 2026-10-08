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

**Start here, 2026-10-07. `P1e-test-order` (row 6j) is `ready`.** Every unit through
`P14g-unit-statement-pages` is `accepted`, and no subagent is in flight. **Read row 6j's own
note before dispatching it**: it installs `pytest-randomly`, which changes the result of every
gate command in this repository at once, and it carries no "0 failed" criterion on purpose.

**`P14g-unit-statement-pages` (row 6h) was accepted on 2026-10-07.** It closed item 114 and
opened items 138, 139 and 140. **It carries one recorded price, and the price is item 138**:
the window in which a model may cite another table's unit statement goes from one page to two,
and nothing can see it, because check B1 reads its expected scale from `units` itself. **The
hole is older than the unit** — the code reviewer put the same wrong statement on the figures'
own page and `HEAD` accepted it too — so this widened an existing window and did not open one.
Two narrower rules were priced by execution and both failed, and the 2x2 is in item 138 so
nobody re-proposes them.

**Item 138 was offered to the user as the next unit on 2026-10-07 and the user chose `a`:
leave it in queue order.** The two facts behind that choice: the hole is older than `P14g`,
and no filing this repository holds can reach it. So the order is `P1e-test-order`, then
`P14c-layout-facts` (row 7), then the deferred route A work.

**`P3d-invisible-year` (row 6i) was accepted on 2026-10-07**, built by the one team in three
rounds. It closed item 116 and opened items 128 to 137. **It carries one live behaviour
change**: a year reached only by a balance sheet or a cash flow statement now stops the
valuation, where it used to be dropped in silence. No input in this repository has that
shape today.

**`P1e-test-order` (row 6j) has its decision: the user chose option `a` on 2026-10-07,
install `pytest-randomly`.** Its assignment is written and it is now `ready`, because
`P14g-unit-statement-pages` is accepted and no row is `building`. **It could not be `ready`
before that, and the reason was scheduling rather than doubt**: installing the plugin changes
the result of every gate command in this repository at once, so it cannot run beside another
unit.

**One lesson from 2026-10-05 holds the one-unit rule in place.** Two units shared this
working tree and the failing count moved between two runs eight minutes apart, so neither
unit's gate figure meant anything. Serialise, or give each unit a worktree.

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
| 6d | `P3c-one-number` | [P3c-one-number.md](assignments/P3c-one-number.md) | `accepted` | 87, 92, 6, 97, 107, 115 | the user's decision "1a" of 2026-10-05: a blank ratio field means "derive it", and the derived figure moves from the form's `value` attribute to its `placeholder`. **The code reviewer approved round 1 on 2026-10-06. The tester assignment is written ([P3c-one-number-tests.md](assignments/P3c-one-number-tests.md)) and waits for the route B extraction to finish**, because `tests/unit/test_p14d_finance_leases.py:519` reads `extractions/WMT.json` and a half-written file would make the tester chase a phantom. 22 tests are red in the working tree: 2 assert the deleted prefill, 20 read an error box through a regex that forbids an attribute. The tester repairs them. New items 103 to 111 |
| 6e | `P1d-skipped-filings` | [P1d-skipped-filings.md](assignments/P1d-skipped-filings.md) | `accepted` | 101, 102 | a `skipif` guard named `10K_filings/Walmart/` and the folder is `10K_filings/WMT/`, so the real-filing check for check B1 skipped on a machine that holds the filing. A tester unit, `tests/` only |
| 6f | `P14e-nri-dedupe` | [P14e-nri-dedupe.md](assignments/P14e-nri-dedupe.md) | `accepted` | 112 | **the defect that moves a number.** `merge_filing_extractions` dedupes non-recurring items on `(year, amount, direction)` with no `else`, so Walmart's two fiscal 2022 divestiture losses of $0.2 billion, Asda on page 66 and Seiyu on page 67, become one. Measured on the real route B file: 14 written, 13 merged, 200 $M of add-back lost in silence. **Ready to start once `P3c-one-number` lands**: its file scope is `ingestion/claude_extractor.py` alone, which is disjoint from `P3c`'s four files |
| 6g | `P14f-prompt-encoding` | [P14f-prompt-encoding.md](assignments/P14f-prompt-encoding.md) | `accepted` | 113 | `session_extraction prompt --pass 2` exits 2 on a Windows console: the two arrows in the Pass 2 direction rules hit the `charmap` codec. Measured 2026-10-06: exit 2 and 19 lines without `PYTHONIOENCODING=utf-8`, exit 0 and 82 lines with it, and **that one subcommand is the only one of six that fails**. The prompt text does not change: those two lines are what route A sends the model. **Assignment written. Not `ready` on purpose**: its file scope (`ingestion/session_extraction.py`) is disjoint from `P14e`'s, but one unit at a time keeps every gate figure meaningful |
| 6h | `P14g-unit-statement-pages` | [P14g-unit-statement-pages.md](assignments/P14g-unit-statement-pages.md) | `accepted` | 114 | check B1 reads the row's page **and the page before**; `_unit_statement_pages_allowed` allows only pages an income statement row cites. Walmart's fiscal 2024 filing prints its income statement title and unit statement at the foot of PDF page 45 and every data row on page 46, so citing page 45 stops the run on a correct reading |
| 6i | `P3d-invisible-year` | [P3d-invisible-year.md](assignments/P3d-invisible-year.md) | `accepted` | 116 | **the overall lead's recommendation for the next unit, 2026-10-07.** `FinancialStatements.years` is built from `self.income_statements` alone, so a year that has a cash flow statement and a balance sheet but no income statement is in no table, carries no reason, and nothing reports it. **A whole year can vanish.** Both entry points hold an `if income_statement is None` branch written to report exactly that, and neither branch can run. **Do not delete the dead branch**: the branch is right and the set it iterates is wrong. Touches `models/financial_statements.py`, `cli.py` and `api/routes_valuation.py`, so every consumer of `years` must be re-checked |
| 6j | `P1e-test-order` | [P1e-test-order.md](assignments/P1e-test-order.md) | `building` | 127, 124 | **The user decided it on 2026-10-07, option `a`: install `pytest-randomly`.** The user's framing: it "may turn tests red the first time it runs, which is the point". **Assignment written. Deliberately not `ready`, and this one has a reason the other deferrals do not**: installing the plugin changes the result of **every** gate command in this repository at once, so a unit measuring its own gate in the same working tree gets a number that means nothing. It starts when no other unit is `building`. **There is no "0 failed" criterion in it.** What it owes instead is the failing set **by name** at each of five named seeds. It also closes item 124, the one live example, without undoing `P14f-prompt-encoding`. Three things it is forbidden to do, each of which would look like success: put `-p no:randomly` anywhere, pin a default seed, or weaken a test to make it pass under shuffling. **Once the plugin is installed, `-p no:randomly` stops being the no-op item 126 deleted and becomes a way to switch the guard off.** The old row text follows | **the user's decision "1a" of 2026-10-07 is done and is not this unit**: `-p no:randomly` asserted nothing and is deleted from every live document (item 126, closed). Journal entries and accepted assignments keep it, because they record what was run. **What is left is item 127**: no test-order guard exists, so a test that passes only because another ran first passes forever. Item 124 is a live example. **Install `pytest-randomly`. It may turn tests red the first time it runs, which is the point**, so schedule it as a unit rather than folding it into a cleanup |
| 6k | `P1f-worktree-guards` | [P1f-worktree-guards.md](assignments/P1f-worktree-guards.md) | `planned` | 142, 141 | **the user's decision of 2026-10-08, option `a`: build the guard fixes before switching to a multi-worktree team scheme.** Item 142: `guard_paths.py` allows every path outside `CLAUDE_PROJECT_DIR`, and a worktree is outside it, so **in a worktree the write guard is off**. Measured by executing the hook: a `tester` writing `<project>/analysis/dcf.py` is denied by name, and the same `tester` writing `<worktree>/analysis/dcf.py` produces no output and exit 0. Item 141: the seal keeps **one** baseline for the whole session, so a second dispatch overwrites the snapshot the first agent will be judged against, and clears it. **This unit cannot be given to a programmer subagent, and that is by design**: `.claude/hooks/*.py` is `ALWAYS_DENIED` with the message "a subagent does not edit the permissions that bind it". **The overall lead implements it; a code reviewer still reviews it; a tester covers it from `tests/`.** The reviewer step is not optional — the change is to the thing that enforces every other change. **Waits for `P1e-test-order` to be accepted**, one unit at a time |
| 7 | `P14c-layout-facts` | not written | `planned` | 10 | defect (item 10), through rule 1 option C: a layout fact the filing states, page-checked; the D&A decision moves into `analysis/` |
| 8 | `P15b-gemini-flash` | [P15b-gemini-flash.md](assignments/P15b-gemini-flash.md) | `planned` | 82 | the user's decision of 2026-10-04: route A's default model becomes `gemini-3.8-flash`; the CLI cache key names the model ID. Assignment written. **Deferred by the user, 2026-10-04:** "focus on fixing the defects first before refine route A" |
| 9 | `P14b-row-reasons` | not written | `planned` | — | feature, after the defects: rule 1 option A: a reason for each printed row, shown on both pages. A format change, and Walmart must be extracted again |
