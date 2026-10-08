---
id: P1f-worktree-guards-tests
phase: 1 — the gates
agent: tester
depends_on: [P1f-worktree-guards]
---

# Tests for `P1f-worktree-guards`: the write guard reaches into a worktree, and the seal survives a corrupt count

## Objective

`P1f-worktree-guards` is written and reviewed twice. It changed four files and closed
backlog item 142, and it repaired item 141's logic.

**Item 142, the one that is enforced today.** `guard_paths.py` allowed every path outside
`CLAUDE_PROJECT_DIR`, and a git worktree is outside it, so **in a worktree the write guard
was off**: a `tester` writing `<worktree>/analysis/dcf.py` produced no output and exit 0.
A new `worktree_root_of` finds a worktree by **reading that tree's `.git` file** — a worktree's
`.git` is a file holding `gitdir: <project>/.git/worktrees/<name>` — so it runs no subprocess
and does not need git on `PATH`.

**Item 141, the one whose logic is right and whose wiring is not.** `seal_baseline.py` used
to rewrite its snapshot on every dispatch, so with two agents in flight the second dispatch
cleared the first. It now snapshots when the in-flight count goes 0 → 1 and otherwise
increments; `seal_check.py` decrements, **before** any comparison can exit.

## Read this before you plan, because it changes what is worth testing

**Neither seal hook is invoked by this harness.** Backlog item 143, measured three ways,
reproducing at `HEAD`. An instrument that writes **before any exit** in `seal_baseline.py`
is absent after two real dispatches, and the matcher is dead for `SendMessage` as well as
`Agent`.

**What that means for you.** The seal's *logic* is live code and you test it directly, by
importing the hook and by running it as a subprocess with payloads you construct. **Do not
write a test that depends on the harness delivering a payload**, because it does not. **And
do not write a test that asserts the hooks never run** — that would lock item 143 as correct
behaviour and turn red the day it is fixed. That is the trap the `P14g` tester refused and
the `P1e` tester refused. Refuse it too, and say in your entry that you did.

## The trap this repository puts in front of you, stated first

**There is no benchmark in this repository.** The only thing that makes an expected value
worth anything is that you derived it before the code ran. **Running the code, reading the
output and asserting that is the one failure mode that passes forever.**
`.claude/agents/tester.md` spends its first section on it.

## The second trap, and it is this unit's own history

**A guard check that silently skips its newest cases is the defect, not the report.** Both
already happened inside this unit:

1. `.claude/check_guard.py` ran the guard with `PATH: ""`. Git was unreachable, so the
   worktree cases would have passed as "allow" **for the wrong reason**. It now carries git
   and **fails rather than skips** when the worktree cannot be built.
2. Backlog item 140, recorded two days ago: a mutation survived the whole suite on any
   machine without `10K_filings/`, in silence.

**Your worktree tests need `git worktree add`.** If git is unavailable, **fail loudly. Never
skip.** A skipped test reports green.

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-08, Windows, `.venv/Scripts/python.exe`, with
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`, on the working tree that holds this unit:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --randomly-seed=<n> --ignore-glob="*_rule3_red.py"` | **1382 passed, 2 skipped, 0 failed** at seeds 7, 1234 and 99 |
| full suite | `-m pytest -q` | **2 failed**, the two red on purpose, by name |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 2 errors in 2 files, 21 checked |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| **write guard** | `.claude/check_guard.py` | **60/60**, up from 48/48 |

**If one disagrees when you run it, stop and report the disagreement.**

**`-q` suppresses the `Using --randomly-seed=` line.** Re-run without `-q` to recover a seed
and name it. **Never `-p no:randomly`.**

**Read these three entries before you start.** They hold every probe already built, 21
attacks on the scratch path, and three mutants with their exact counts:

- `.agent/journal/2026-10-08T1430-overall_lead-p1f-worktree-guards.md` — rounds 1 to 3.
- `.agent/journal/2026-10-08T1510-code_reviewer-p1f-worktree-guards.md` — round 1.
- `.agent/journal/2026-10-08T1610-code_reviewer-p1f-worktree-guards-r2.md` — round 2.

## What to do

1. **Lock the worktree decisions, through the hook as a subprocess**, for all three roles: a
   denied path in a worktree is denied, an allowed path is allowed, `ALWAYS_DENIED` holds,
   and the Bash tripwire reaches in. **The deny message in a worktree must be identical to
   the in-project one** — that identity is the point, and a test that only checks "denied"
   would pass on a message that named the wrong path.
2. **Lock that the guard needs no git.** Run it with `PATH=""` and confirm a worktree path is
   still denied. This is the reviewer's F6 and it is what stops the guard failing open in
   silence.
3. **Lock criterion 7 hardest of all: scratch stays writable.** Every unit in this repository
   works in `C:\tmp`, so a regression here breaks everything at once. The round 2 reviewer
   built 21 cases; take the shapes that are cheap in a test and say which you took: a scratch
   directory containing its own clone, a `.git` file naming a different repository, junk in
   a `.git` file, an empty `.git`, a `<wt>_extra` sibling that is not a worktree.
4. **Test `worktree_root_of` directly**, not only through the subprocess. Import the hook by
   path. Cover: a worktree root, a file deep inside one, the project itself, a scratch path,
   and a `.git` file whose `gitdir` points elsewhere.
5. **Lock the seal's counting**: 0 → 1 snapshots, later dispatches increment, a stop
   decrements, the count cannot go below 0, and **a stop still fires when a sealed file
   changed**. Construct the payloads yourself.
6. **Lock the corrupt shapes.** `in_flight` as `"abc"`, `true`, `null`; a file that is not
   JSON; a JSON list; an empty file. **Both hooks must exit 0 and must not crash**, the
   count must return to 0, and the next stop must still fire. A crashing hook is a guard
   that is off, which is what the round 1 reviewer found.
7. **Lock `window_lost_at`.** An unreadable baseline is replaced by a fresh snapshot that
   **has digests** and records the loss. The first fix for this wrote a state with **no**
   digests, which made the check skip every comparison in silence — a worse defect than the
   one being fixed. Write the test that would have caught that.
8. **Lock `as_count` rejecting `bool`.** `True` is an `int` in Python and would count as 1.
9. **Mutate your own tests and record what each kills.** At least these five, each in its own
   scratch tree, never in the repository:
   - `resolve_repo_relative` reverted to `repo_relative`, which is item 142 returning.
   - `worktree_root_of` returning the probe's parent for any outside path, which denies
     scratch.
   - the `finally`-equivalent removed from the seal: `seal_check.py` not decrementing.
   - `as_count` replaced by `int(...)`, which is the round 1 crash.
   - `window_lost_at` branch deleted and the no-digest state restored.
   **A mutation your suite survives is a hole. Report it; do not hide it.**
10. **Count what you covered, do not estimate it.** Intersect a `--cov-branch` report with the
    added lines from `git diff -U0` over the four files in scope.

## Files in scope

- `tests/` only.

**Nothing else.** `.claude/check_guard.py` is `ALWAYS_DENIED` to you as well, so the guard's
own case table is not yours to extend. Cover the hooks from `tests/`.

## Out of scope

- **The four files the unit changed.** If you believe the implementation is wrong, say so in
  your entry and return `fail`. Do not fix it.
- **Backlog item 143**, that the hooks are never invoked. Named above so you do not test for
  it in either direction.
- **The two tests that are red on purpose.** Leave both red.
- **Criterion 1 of the unit**, struck on 2026-10-08. See the amendment at the top of the
  unit's criteria table.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | Every expected value is hand-sourced | a count of assertions, and how many came from the code's output | **the second must be 0** |
| 2 | The worktree decisions are locked for all three roles | deny, allow, `ALWAYS_DENIED`, Bash | your tests |
| 3 | The deny message in a worktree is identical to the in-project one | asserted, not merely "denied" | your tests |
| 4 | The guard works with `PATH=""` | a worktree path still denied | your tests |
| 5 | **Scratch stays writable** | the shapes you took, named | your tests |
| 6 | `worktree_root_of` covered directly | five cases | your tests |
| 7 | The seal's counting | 0 → 1, increment, decrement, floor at 0, and a stop still fires on a change | your tests |
| 8 | Six corrupt shapes | both hooks exit 0, count returns to 0, next stop still fires | your tests |
| 9 | `window_lost_at`, with digests present | the test that would have caught the no-digest state | your tests |
| 10 | `as_count` rejects `bool` | `True` counts as 0, not 1 | your tests |
| 11 | Five mutations, each killed | for each: the mutation, the command, the failing count and the **names** that went red | your own scratch trees |
| 12 | Coverage of what the unit added | statements covered and missed, as counts | `--cov-branch` intersected with `git diff -U0` |
| 13 | The gate | **1382 plus your new tests, 2 skipped, 0 failed**, at three named seeds | the gate form |
| 14 | The failing set | empty, by name | the gate form |
| 15 | Lint | 4 errors, every one `BLE001`. **Run `ruff check .` after your last write** | `-m ruff check .` |
| 16 | The write guard | 60/60 | `.claude/check_guard.py` |
| 17 | No test skips silently | if git is unavailable, fail | state how you did it |

**Criterion 15 has its own history and the newest entry in it is mine.** The round 2 reviewer
found `ruff check .` at 5, not 4, because I ran lint **before** my last edit. The same defect
is recorded against `P3c-one-number-tests`, and the `P3d` and `P14g` testers each caught one
in their own file by running lint last. **Run lint after your last write.**

## Citations

- `.claude/agents/tester.md` — your role card.
- `docs/2-rules/rules.md` — rule 3.
- `docs/9-reference/refactor-backlog.md`, items 141, 142, 143 and 140.
- `.agent/assignments/P1f-worktree-guards.md` — the unit, and the amendment striking its
  criterion 1.
- `AGENTS.md` — "enforced by permission, not by good intentions", which is what item 142 broke.

## Known open items

- **Never mutate a file in this repository.** Scratch copies under `C:\tmp`; print the sha256
  of all four files in scope before and after. `git stash` is forbidden, and a worktree
  shares the stash stack.
- **Backlog item 75**: the write guard refuses a `>` or a heredoc inside a Bash command.
  **And a second reason to use the Write tool**: on 2026-10-08 I applied a patch through
  `python -c` inside a double-quoted bash string, and bash ate every backticked word as a
  command substitution. Three identifiers vanished from a comment. **Write files with the
  Write and Edit tools, not through a shell.**
- **Windows holds a lock on a worktree directory** after a process reads from it.
  `git worktree remove` fails the first time and works on a retry. Seen four times on
  2026-10-08. Make teardown best-effort and never let it decide a verdict.
- The suite takes about 135 to 150 seconds.
