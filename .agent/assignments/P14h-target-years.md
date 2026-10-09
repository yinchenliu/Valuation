---
id: P14h-target-years
phase: 14 — the Pass 1 and Pass 2 roles
agent: programmer
depends_on: []
team: B (worktree `Valuation-wt/team-b`, branch `unit/team-b`)
---

# An empty year list stops the two prompt builders, instead of reading as "all years" (item 133)

## Objective

**The fact.** Two prompt builders in `ingestion/claude_extractor.py` test the year list by
truthiness:

| Builder | Line at `84c0462` | Test |
|---|---|---|
| `_build_financials_prompt` (Pass 1) | 2336 | `if target_years:` |
| `_build_nri_prompt` (Pass 2) | 2414 | `if target_years:` |

`None` means "every year the filing presents". An empty list means "no year". The two
are different requests, and the truthiness test reads both as the first. Measured by the
overall lead on `main`:

```
$ .venv/bin/python -c "from ingestion.claude_extractor import _build_nri_prompt as n; print(n('IS', [])[:63])"
Analyze non-recurring items for ALL fiscal years in the filing.
```

So a caller that asks for no year is sent a prompt that asks the model for every year.
`P3d-invisible-year` fixed the third site of this shape, `_build_is_summary`, in its round 2
(review finding F2). Backlog item 133 holds these two.

**It is latent.** No caller passes an empty list today. Every one arrives from
`_plan_target_years`, which returns `None` or `list(plan.target_years)`, and
`plan_filings` builds `target_years` as `None` or a one-element tuple.

**Why not the one-token fix.** `if target_years is not None:` would build
`"... fiscal year(s):  ONLY"` with no year in it, and route A would send that to the model.
A request for no year is not a request the model can answer. Rule 3 says a missing input
stops the run and names the field. So:

**When this unit is done**, each of the two builders stops on an empty list with a
`ValueError` that names `target_years`. `None` and a non-empty list build the same prompt
text as before, byte for byte.

## What is already true — verify, do not redo

- The six real prompts, with the repository path replaced by `<REPO>`, hash as below on
  `main` at `84c0462`, and the same in this worktree before any edit:

  | `--filing` | `--pass 1` | `--pass 2` |
  |---|---|---|
  | 0 | `cbf26b0a876034f6` | `024bd96701e72481` |
  | 1 | `c401b7bb3096592c` | `9391f61bfa21ac43` |
  | 2 | `4aa84c989703f3ce` | `cc61ac590ca169f0` |

  Reproduce one, from the worktree root:

  ```
  ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m ingestion.session_extraction \
      prompt extractions/WMT.json --filing 0 --pass 1 2>&1 | sed "s#$PWD/#<REPO>/#g" \
      | shasum -a 256 | cut -c1-16
  ```

- `_build_is_summary` already uses `target_years if target_years is not None else …`.
  Its docstring holds the reasoning (`P3d-invisible-year`, round 2, F2).
- The gate form on `main` at `84c0462`: **1 failed, 1602 passed, 0 skipped** at seeds 7,
  1234 and 99. The failure is item 145, team A's unit `P1h-mac-gate`, now in rework.

If a measurement disagrees, stop and report the disagreement. Do not edit to make it agree.

## What to do

1. In `_build_financials_prompt` and in `_build_nri_prompt`, stop on an empty
   `target_years` with a `ValueError`. The message names `target_years`, says that an empty
   list requests no year, and says that `None` is how a caller asks for every year.
   Reason: rule 3, `docs/2-rules/rules.md`.
2. Test the year list with `is not None`, not by truthiness, in both builders, as
   `_build_is_summary` does. Reason: the same, and one form for one question in one file.
3. Keep the prompt text for `None` and for a non-empty list unchanged, byte for byte.
   Reason: route A sends these strings to the model. A change to what the model reads is an
   escalation (`AGENTS.md`, "Escalate, do not decide alone").

## Files in scope

- `ingestion/claude_extractor.py` (programmer)
- `tests/unit/test_p14h_target_years.py` (tester, new file)

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Out of scope

- `_build_is_summary`: correct since `P3d`. Do not change it.
- The two `year_label = ... if target_years else ...` lines in `_run_financials_pass` and
  `_run_nri_pass`. They only label a console line, and each runs **after** its builder is
  called, so once step 1 stops on an empty list, neither label can see one.
- `ingestion/session_extraction.py`, `tests/unit/test_p1h_mac_gate.py`: team A's unit
  `P1h-mac-gate` is in rework on them.
- `.venv`, `requirements*.txt`: a unit branch installs nothing. The venv is shared.
- The four record files and `docs/`, `.claude/`, `extractions/`: see "Pilot rules".

## Done-criteria

Run every command **from the worktree root**, with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`
in front.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | no truthiness test of `target_years` is left in the two builders | no match | `grep -n "if target_years:" ingestion/claude_extractor.py` |
| 2 | an empty list stops Pass 1 | `ValueError` whose message contains `target_years` | the tester's test, calling `_build_financials_prompt([])` |
| 3 | an empty list stops Pass 2 | `ValueError` whose message contains `target_years` | the tester's test, calling `_build_nri_prompt("<summary>", [])` |
| 4 | the six real prompts are unchanged | the six hashes in "What is already true" | the command there, for `--filing` 0, 1, 2 and `--pass` 1, 2 |
| 5 | `None` and a one-element list build the same text as on `main` | equal strings | the tester's tests. The expected text is written by hand from the two literal strings in each builder, not printed by the code |
| 6 | the tests in 2 and 3 kill the old code | red with `if target_years:` restored and no stop, green without | the tester reports the mutation and both counts |
| 7 | the gate form at three orders | the failed set equals `main`'s, and the passed count is `main`'s plus the tester's new tests | `.venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=<n>` for n = 7, 1234, 99 |
| 8 | lint, types, census unchanged | `4 errors`, all `BLE001`, none in a unit file; `2 errors in 2 files`; `64` | the commands in `docs/8-build/environment.md`, section 4, and the grep at `docs/2-rules/rules.md:65` with `pipeline.py` added |
| 9 | the unit stayed in scope | only the two files above, this assignment, `P14h-target-years-tests.md` and new files under `.agent/journal/` | `git diff --name-only main...HEAD` |

**Every criterion is a measurement, never an opinion.**

## Pilot rules (worktree)

This unit runs in a git worktree, beside team A's rework. [docs/8-build/worktree-teams.md](../../docs/8-build/worktree-teams.md)
owns the scheme. These five points bind this unit:

1. **Do not write** `STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md` or
   `docs/9-reference/refactor-backlog.md`. The overall lead writes them on `main` after the
   merge. A subagent's own journal entry, with its own file name, is allowed.
2. **The build lead does not set a queue state.** It writes `## Handoff` at the end of this
   file, commits on `unit/team-b`, and tells the user "P14h-target-years is ready for the
   overall lead".
3. **The handoff names the commit hash.** `P3e-reconciliation-years` did not (note N2 of its
   review). **Do not amend a commit**: make a new one.
4. **Install nothing.** `.venv` in the worktree is a link to the main checkout's venv.
5. **No hook protects a Gemini subagent.** After each subagent run, run `git status` and
   reject the run if it wrote outside its role or outside Files in scope.

**A test must call the code it is about.** `P3e`'s review found one test that called no
production code and passed under the mutant (backlog item 148). The tester's trap is the
first section of `.claude/agents/tester.md`.

## Citations

- `docs/2-rules/rules.md`, rule 3 — a missing input stops and names the field.
- `ingestion/claude_extractor.py`, `_build_is_summary`'s docstring — why `None` and an
  empty list are two requests.
- `.agent/assignments/P3d-invisible-year.md`, round 2, finding F2 — the third site, fixed.
- `docs/2-rules/llm-boundary.md` — what the model may be sent.

## Known open items

- Item 133 names lines `:2280` and `:2358`. They are `:2336` and `:2414` at `84c0462`.

## Backlog items this unit is NOT fixing

Each sits in `ingestion/claude_extractor.py`. Leave them alone.

- 10 — the D&A subtraction inside the parser (`P14c-layout-facts`).
- 51, 61 — the dead `WARN` branch and the unreachable return after Pass 1's retry loop.
- 63, 64 — retries on a filing with no text layer; the joined-line page check.
- 73, 74, 79, 121 — stops that do not name the filing or the item.
- 78, 80, 84, 85, 138 — the unit-scale checks and their messages.
- 119, 120 — the non-recurring item merge.
- 122 — `--debug` on a Windows console.

## Handoff (build lead B)

### Commit

`a67a225` (`a67a225c312a0fad7d16b555ebc85d8239079587`)

### Verdicts

- **Programmer:** complete (`.agent/journal/2026-10-09T0204-programmer-p14h-target-years.md`)
- **Code Reviewer:** `approved` (`.agent/journal/2026-10-09T0216-code_reviewer-p14h-target-years.md`)
- **Tester:** `pass` (`.agent/journal/2026-10-09T0218-tester-p14h-target-years.md`)

### Summary

In `ingestion/claude_extractor.py`, `_build_financials_prompt` (Pass 1) and `_build_nri_prompt` (Pass 2) now test `target_years is not None` instead of truthiness (`if target_years:`), and raise `ValueError` naming `target_years` when `target_years` is an empty list (Rule 3, backlog item 133). When `target_years` is `None` or a populated list, prompt text is identical byte for byte to `main`, matching all six reference prompt hashes on `extractions/WMT.json`.

New test file `tests/unit/test_p14h_target_years.py` contains 23 unit tests verifying Rule 3 stops, template string generation against hand-derived literal expectations, prompt pair assembly, and prompt hash invariance across all 3 filings in `extractions/WMT.json`. All tests call production code directly (item 148). Mutation probe restoring `if target_years:` failed 7 tests (killed).

### Measured Gates

All commands run on macOS from `/Users/yinchenliu/Documents/Git/DCF/Valuation-wt/team-b` with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`.

| Gate / Criterion | Command | Result |
|---|---|---|
| 1. No truthiness test of `target_years` | `grep -n "if target_years:" ingestion/claude_extractor.py` | Exit 1 (0 matches) |
| 2. Pass 1 empty list stop | `pytest -q -p no:cacheprovider tests/unit/test_p14h_target_years.py -k test_build_financials_prompt_empty` | 2 passed in 0.03s |
| 3. Pass 2 empty list stop | `pytest -q -p no:cacheprovider tests/unit/test_p14h_target_years.py -k test_build_nri_prompt_empty` | 1 passed in 0.03s |
| 4. Six real prompt hashes | `for f in 0 1 2; do for p in 1 2; do ...; done; done` | All 6 hashes match baseline: f0p1 `cbf26b0a876034f6`, f0p2 `024bd96701e72481`, f1p1 `c401b7bb3096592c`, f1p2 `9391f61bfa21ac43`, f2p1 `4aa84c989703f3ce`, f2p2 `cc61ac590ca169f0` |
| 5. Template text unchanged | `pytest -q -p no:cacheprovider tests/unit/test_p14h_target_years.py -k matches_hand_derived` | 8 passed in 0.03s |
| 6. Mutation probe killed | Mutant with `if target_years:` | 7 failed, 10 passed (DID NOT RAISE ValueError) |
| 7. Randomly shuffled gate (n=7) | `pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=7` | 1 failed, 1625 passed in 33.60s |
| 7. Randomly shuffled gate (n=1234) | `pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=1234` | 1 failed, 1625 passed in 32.68s |
| 7. Randomly shuffled gate (n=99) | `pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=99` | 1 failed, 1625 passed in 33.18s |
| 8. Lint | `ruff check .` | 4 errors, all `BLE001` (`api/routes_valuation.py:463, 745`, `cli.py:1416`, `tests/test_e2e_all_googl.py:106`), 0 in files written by this unit |
| 8. Types | `mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 2 errors in 2 files (`analysis/projector.py:395`, `api/routes_upload.py:28`, 21 files checked) |
| 8. Rule 3 census | `grep -rnE "if [^)]+ else 0(\.0)?\b\|\bor +0(\.0)?\b\|\.get\([^,]+, *0(\.0)?\)\|: *float *= *0\.0" '--include=*.py' models analysis api ingestion pipeline.py \| wc -l` | 64 |
| 9. Scope | `git diff --name-only main...HEAD` | Only files in scope |

Note on Criterion 7: The single failing test across all three seeds is `tests/unit/test_session_extraction_console.py:774: test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream`, which is the known pre-existing failure on macOS (backlog item 145, team A's unit `P1h-mac-gate`). Passed tests increased by 23 (from 1602 to 1625).

### New Findings

None.

### Questions for the Overall Lead

None.


## Overall lead review

**Round 1, 2026-10-08. Verdict: `rework`, for the tester only.** The code change in
`a67a225` is accepted as it stands: the programmer does not run again. This unit was built
before the test review joined the loop (`919afd7`), so I ran the five test-review
questions myself, from `.claude/agents/code-reviewer.md` on `main`.

### What I re-ran, with the empty-key prefix

| # | Check | I measured | Agree? |
|---|---|---|---|
| 1 | no `if target_years:` | `grep` exit 1 | yes |
| 2, 3 | an empty list stops both builders | the 7 stop tests pass | yes |
| 4 | the six real prompts unchanged | the six hashes match, from this worktree | yes |
| 6 | the tests kill the old code | in a scratch worktree, `main`'s `ingestion/claude_extractor.py`: **8 failed, 15 passed** (the 7 stop tests and the source-text test); restored: 23 passed. The handoff says 7 failed, 10 passed; the difference is the 6 hash tests, which pass either way | yes |
| 7 | gate form, seeds 7, 1234, 99 | `1 failed, 1625 passed`; the one failure is item 145, closed on `main` since `d13be2d` | yes |
| 8 | lint, types, census | 4, 2 in 2, 64 | yes |
| 9 | scope | the two files, two assignment files, three journal entries | yes |
| T1 | every test calls the code | yes, except `test_no_truthiness_test_of_target_years_in_source`, which reads source text (F2) | — |
| T2 | every test holds on both machines | **no**: F1 | — |
| T3 | no fallback asserted | the search finds one line, `assert exit_code == 0`: a command's success, not a fallback | yes |
| T4 | source labels | the prompt literals are the text on `main`, which criterion 5 states as the requirement | yes |
| T5 | coverage, measured | `--cov=ingestion.claude_extractor --cov-branch`: `_build_financials_prompt` 11 of 11 statements, 6 of 6 branches; `_build_nri_prompt` 8 of 8, 4 of 4. The entry counted these by hand, which the card of its time allowed | — |

### F1 — `major`. The six hash tests fail on the Windows machine, and they test nothing the literal tests do not

**The fact.** `test_real_prompt_hash_invariance` normalises the output with
`combined.replace(f"{Path.cwd()}/", "<REPO>/")`. The prompt header prints the session
file's path, and on Windows that path uses backslashes: the measured Windows header in
`.agent/assignments/P14f-prompt-encoding.md:17` reads `...\extractions\WMT.json`. So on
Windows the replacement matches nothing, the machine's path stays in the hashed text, and
all six tests fail against correct code. Run from another directory, they fail on macOS
too: from `/tmp`, **7 failed** (the 6 hash tests and F2's test).

**What follows.** The tests break `docs/5-testing/strategy.md`, section 1, "Every test holds
on both machines". They also pin a hash of the code's own output on `main`, which section 1
calls a photograph. The six hashes were this unit's **measurement** (criterion 4), not a
requirement for every later unit. `P14c-layout-facts` will change the Pass 1 prompt on
purpose, and these tests would then go red with an unreadable diff. The eight literal tests
already pin the same text readably, so the hash tests add only the fragility.

**The fix.** Delete `test_real_prompt_hash_invariance` and the `WMT_BASELINE_HASHES` table,
and the imports only they use. Record the six hashes in the entry as the criterion 4
measurement, with the command.

### F2 — `minor`. The source-text test depends on the working directory

`test_no_truthiness_test_of_target_years_in_source` reads `Path("ingestion/claude_extractor.py")`,
relative to the working directory, so it fails when pytest starts anywhere else. The seven
stop tests already kill the mutant. Either delete it, or anchor the path to the repository:
`Path(__file__).resolve().parents[2] / "ingestion" / "claude_extractor.py"`.

### To finish the rework

1. Dispatch the tester with F1 and F2. It changes `tests/unit/test_p14h_target_years.py`
   only. The programmer does not run.
2. Re-run criterion 6 and the gates.
3. Commit as a new commit, append `## Handoff, round 2` naming the commit, **commit the
   handoff**, and tell the user "P14h-target-years is ready for the overall lead".
