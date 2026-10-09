---
id: P3e-reconciliation-years
phase: 3 — unify the pipeline
agent: programmer
depends_on: []
team: B (worktree `Valuation-wt/team-b`, branch `unit/team-b`)
---

# The CLI reconciles the same years as the web page (item 128)

## Objective

**The fact.** The two entry points iterate different year sets for the GAAP to non-GAAP
EBIT reconciliation:

| Entry point | Line | Year set |
|---|---|---|
| CLI, `print_normalization` | `cli.py:845` | `years = raw.years` |
| web, `_build_ebit_reconciliation` | `api/routes_valuation.py:329` | `years = sorted(set(raw.years) \| set(adjusted.years))` |

**What follows.** A year that only the adjusted statements reach is on the page, as
`not extracted: raw income statement`, and is absent from the CLI with no line at all.
The code reviewer and the tester of `P3d-invisible-year` found this independently on
2026-10-07 (backlog item 128). Two entry points that drift apart are this repository's
third standing trap.

**It is latent.** `normalize_financials` returns a statement for every raw year today, so
no input reaches the difference. The `P3d` tester said its own parity test passes only
because its fixtures give both sides the same year set.

**When this unit is done**, the CLI iterates the same set as the page, and a test with a
year on the adjusted side only shows both entry points naming that year in the same words.

## What is already true — verify, do not redo

- `cli.py:845` reads `years = raw.years`. `api/routes_valuation.py:329` reads the union.
  Reproduce: `grep -n "years = raw.years" cli.py` and
  `grep -n "set(raw.years) | set(adjusted.years)" api/routes_valuation.py`.
- `print_normalization` already holds the four cases and the web's exact phrases:
  `raw and adjusted income statement`, `raw income statement`,
  `adjusted income statement`. `P3d` round 2 made them match (finding F4).
- `tests/unit/test_p3d_invisible_year.py:452`,
  `test_both_entry_points_name_an_unreconciled_year_in_the_same_words`, is the existing
  parity test.

If a measurement disagrees, stop and report the disagreement. Do not edit to make it agree.

## What to do

1. In `cli.print_normalization`, iterate the sorted union of `raw.years` and
   `adjusted.years`, as `_build_ebit_reconciliation` does. Reason: the two entry points
   must report the same years (the third standing trap, `.claude/skills/main-agent`).
2. Update the comment above that line so it states the set the CLI now iterates and why.
   Do not shorten the record of `P3d` round 2 in it.
3. Keep the early `return` for an empty year set, and keep the summary rule: the summary
   line prints only when at least one year was reconciled.

## Files in scope

- `cli.py` (programmer)
- `tests/unit/test_p3e_reconciliation_years.py` (tester, new file)

**Nothing else.** Work outside this list is a review finding, even if the change is good.
**`api/routes_valuation.py` does not change.** The page is the reference here.

## Out of scope

- `api/routes_valuation.py`, `templates/`: the web side is correct.
- `pipeline.py`: a shared year-set function for both entry points is a larger unit. Do not
  start it here.
- `ingestion/session_extraction.py`: team A's unit `P1h-mac-gate` is in flight on it.
- `.venv`, `requirements*.txt`: a unit branch installs nothing. The venv is shared.
- The four record files and `docs/`, `.claude/`, `extractions/`: see "Pilot rules".

## Done-criteria

Run every command **from the worktree root**, with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`
in front.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the CLI no longer iterates the raw years alone | no match | `grep -n "years = raw.years" cli.py` |
| 2 | a year on the adjusted side only is named by both entry points, in the same words | the CLI prints `<year>: not extracted: raw income statement` and `_build_ebit_reconciliation` returns a row for that year with `missing_statement == "raw income statement"` | the tester's new test, with expected text written by hand before the code runs |
| 3 | the test in criterion 2 fails on `main`'s `cli.py` | red with `years = raw.years` restored, green without it | the tester reports the mutation and both counts |
| 4 | the existing parity test still passes | `1 passed` | `.venv/bin/python -m pytest -q -p no:cacheprovider "tests/unit/test_p3d_invisible_year.py::test_both_entry_points_name_an_unreconciled_year_in_the_same_words"` |
| 5 | the gate form at three orders | the failed set equals `main`'s, and the passed count is `main`'s plus the tester's new tests | `.venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=<n>` for n = 7, 1234, 99 |
| 6 | lint unchanged | `4 errors`, every one `BLE001`, none in a file this unit wrote. `cli.py`'s one `BLE001` stays where it is | `.venv/bin/python -m ruff check .` |
| 7 | types unchanged | `2 errors in 2 files` | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` |
| 8 | rule 3 census unchanged | `64` | the grep at `docs/2-rules/rules.md:65`, with `pipeline.py` added and `'--include=*.py'` quoted |
| 9 | the unit stayed in scope | only the two files above, this assignment, `P3e-reconciliation-years-tests.md` and new files under `.agent/journal/` | `git diff --name-only main...HEAD` |

**Every criterion is a measurement, never an opinion.** On `main` the gate form has one
known failure on macOS, `test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream`
(backlog item 145, team A's unit). It is not this unit's. Criterion 5 compares against it.

## Pilot rules (worktree)

This unit runs in a git worktree, beside team A's unit. [docs/8-build/worktree-teams.md](../../docs/8-build/worktree-teams.md)
owns the scheme. These four points bind this unit:

1. **Do not write** `STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md` or
   `docs/9-reference/refactor-backlog.md`. Every merge would conflict on them. The
   overall lead writes them on `main` after the merge. A subagent's own journal entry,
   with its own file name, is allowed.
2. **The build lead does not set a queue state.** It writes `## Handoff` at the end of
   this file, commits on `unit/team-b`, and tells the user "P3e-reconciliation-years is
   ready for the overall lead".
3. **Install nothing.** `.venv` in the worktree is a link to the main checkout's venv.
4. **No hook protects a Gemini subagent.** After each subagent run, run `git status` and
   reject the run if it wrote outside its role or outside Files in scope.

## Citations

- `api/routes_valuation.py:311-360`, `_build_ebit_reconciliation` — the reference set and
  the three phrases.
- `templates/_statements.html:455` — the page renders `not extracted: {{ row.missing_statement }}`.
- `docs/3-architecture/entry-points.md` — the two entry points and how they still differ.
- `.agent/assignments/P3d-invisible-year.md` — why the phrases match, round 2, finding F4.

## Known open items

- Backlog item 92 (the two entry points show different historical FCFF) is closed by
  `P3c-one-number`. Do not reopen it.

## Backlog items this unit is NOT fixing

Each sits in `cli.py`. Leave them alone.

- 8 — the blanket `except Exception` in `cli.py`.
- 68 — the CLI prints no assumption label.
- 86, 90 — the `CACHE_FORMAT` comment and the terminal growth literal.
- 104 — the historical-FCFF basis sentence in three files.
- 129, 130, 132, 134, 135, 136, 137 — the other `P3d-invisible-year` findings in `cli.py`.
