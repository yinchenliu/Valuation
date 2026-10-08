---
id: P1f-worktree-guards
phase: 1 — the gates
agent: overall lead (see "Who builds this, and why it cannot be delegated")
depends_on: [P1e-test-order]
---

# Make the write guard and the seal hold when agents run in worktrees (items 142, 141)

## Objective

The user decided on 2026-10-08, option `a`: **build these two fixes before switching to a
multi-worktree team scheme.** Until they land, a worktree run has no write guard at all.

**Fact 1, item 142, measured by executing the hook on 2026-10-08.** `guard_paths.py:218-221`
reads:

```python
rel = repo_relative(candidate, project, cwd)
if rel is None:
    continue                      # outside the repository: scratch space, allowed
```

`project` is `CLAUDE_PROJECT_DIR` or the cwd. **A git worktree lives outside it**, so every
write in one takes the `rel is None` branch. Two payloads, same role, same repo-relative
target:

```
tester writes  <project>/analysis/dcf.py   ->  DENY: "The `tester` agent may write only
                                                `tests/**`, `.agent/journal/**`"
tester writes  <worktree>/analysis/dcf.py  ->  no output at all, exit 0
```

**What follows.** In a worktree a tester may rewrite the code it judges. `AGENTS.md` says
the split is "enforced by permission, not by good intentions". In a worktree it is back to
good intentions, and nothing reports it.

**The `rel is None` branch is correct for its purpose** and must survive: scratch trees under
`C:\tmp` have to stay writable, and every unit in this repository depends on that.

**Fact 2, item 141, measured by reading both hooks on 2026-10-08.** `seal_baseline.py` writes
**one** path, `.agent/.seal-baseline.json`, on `PreToolUse` for `Agent`, `Task` and
`SendMessage`. `seal_check.py:45` reads that same one path on `SubagentStop`.

**What follows.** Dispatch A writes S1. Dispatch B overwrites it with S2. A then stops and is
checked against S2. Anything A wrote to a sealed file between S1 and S2 is already inside S2,
so the check sees no difference and clears A. A **false negative**, and a silent one. The
sealed things are `.agent/journal/INDEX.md`, `STATUS.md` and `.claude/hooks/` itself.

**Fact 3, and it shapes the fix rather than blocking it.** `seal_baseline.py` runs at
**dispatch**, and at dispatch the harness has not yet created the agent, so **there may be no
agent identifier in the payload to key a per-agent file by**. The hook today reads only
`agent_type`, `cwd` and `tool_name`. **Criterion 1 below is to measure what each payload
actually carries, before designing anything.**

**What is true when this unit is done.** A subagent writing outside its role is denied in a
worktree exactly as it is in the main checkout; two subagents in flight cannot clear each
other; and `.claude/check_guard.py` covers both, so the next change to either hook is
measured and not argued.

## Who builds this, and why it cannot be delegated

**Measured on 2026-10-08.** A `programmer` subagent writing `.claude/hooks/guard_paths.py` is
denied:

```
"`.claude/hooks/guard_paths.py` is closed to every subagent:
 a subagent does not edit the permissions that bind it."
```

`.claude/hooks/*.py` is in `ALWAYS_DENIED`, which applies to every role whatever its allow
list says. **That is correct and it must not be relaxed for this unit.** A subagent that
could edit the guard could disarm it.

**So the overall lead writes the code, and the normal loop runs around it:**

1. The overall lead implements, in the main checkout.
2. A **code reviewer** subagent reviews it. It reads everything and writes only
   `.agent/journal/`, so nothing in its role is blocked. **This review is not optional.**
   `.claude/skills/main-agent/SKILL.md` says a change that looks small enough to just make is
   exactly the change that skips review, and this change is to the thing that enforces every
   other change.
3. A **tester** subagent writes tests under `tests/`. It **cannot** write
   `.claude/check_guard.py`, which is the guard's own case table and is also `ALWAYS_DENIED`.
   **The overall lead extends `check_guard.py`; the tester covers the hooks from `tests/`.**

## What is already true — verify, do not redo

Take these yourself before changing anything, on the Windows machine
(`.venv/Scripts/python.exe`), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. **Take them at the
commit you start from and write that commit down**, because a stale baseline table has
already cost this repository one false alarm (`P1e-test-order`, F1).

| Fact | Command |
|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` |
| full suite | `-m pytest -q` |
| lint | `-m ruff check .` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` |
| census | the grep at `docs/2-rules/rules.md:102` |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` |
| **guard** | `.claude/check_guard.py` — **48/48 today. This unit raises that number** |

**The suite shuffles now.** `-q` suppresses the `Using --randomly-seed=` line, measured both
ways. Re-run without `-q` to recover a seed, and name it. **Never `-p no:randomly`.**

## What to do

1. **Measure the payloads before designing.** Print what `PreToolUse` carries for `Agent`,
   for `Task` and for `SendMessage`, and what `SubagentStop` carries. **Name every field.**
   Fact 3 stands or falls on this. If an identifier exists that is common to a dispatch and
   its stop, key the baseline by it and the fix is small. If none does, use step 2's shape.
2. **If there is no shared identifier, key by the in-flight window instead of by the agent.**
   Keep a count: a dispatch increments it, a `SubagentStop` decrements it, and the baseline is
   written **only when the count goes from 0 to 1**. Then a sealed file that moves while any
   subagent is in flight is caught, and no attribution is needed. **The repository's own rule
   already makes that safe**: `main-agent` says the orchestrator must not write
   `.agent/journal/INDEX.md` while a unit is building. **State which shape you chose and the
   measurement that chose it.**
3. **Teach `guard_paths.py` which outside paths are worktrees of this repository.**
   `git worktree list --porcelain` names them. A target under one must be made relative to
   **that worktree's root** and then checked exactly as an in-repository path is.
   **`C:\tmp` and every other outside path must stay allowed.** That is the branch's purpose
   and breaking it breaks every unit's scratch discipline.
4. **Do not shell out on every call without measuring the cost.** This hook runs before every
   `Write`, `Edit` and `Bash` of every subagent. If `git worktree list` is slow, cache it for
   the life of the process and say what you measured.
5. **Extend `.claude/check_guard.py`.** It holds 48 cases today. Add cases for: each role
   writing an allowed path in a worktree, each role writing a denied path in a worktree, an
   `ALWAYS_DENIED` path in a worktree, and a `C:\tmp` path that must stay allowed. **A fix to
   a guard that its own case table does not cover is a fix nobody can check.**
6. **Prove the seal fix by execution, not by argument.** Two dispatches, then two stops, with
   a sealed file changed in between. Show that the first agent is no longer cleared.
7. **Record what you find, do not widen the scope.** Anything else goes in the entry under
   "Found".

## Files in scope

- `.claude/hooks/guard_paths.py`
- `.claude/hooks/seal_baseline.py`
- `.claude/hooks/seal_check.py`
- `.claude/check_guard.py`
- `tests/` — **the tester only**, after the review.

**Nothing else.**

## Out of scope

- **Relaxing `ALWAYS_DENIED`.** `.claude/hooks/*.py` stays closed to every subagent. If the
  fix seems to need a subagent to edit a hook, the fix is wrong.
- **Creating the worktrees, or running a team in one.** That is the next unit. This one makes
  it safe; it does not use it.
- **`docs/8-build/environment.md`** and the worktree workflow documents. After both fixes
  pass, not inside this unit.
- **Backlog items 123 and 125.**
- **The two tests that are red on purpose.** Leave both red.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | The payload fields are measured, not assumed | every field of all four payloads, named | print them |
| 2 | The chosen seal shape, and the measurement that chose it | stated in the entry | criterion 1 |
| 3 | **The item 142 before is reproduced** | at the starting commit, a `tester` writing `<worktree>/analysis/dcf.py` gives no output and exit 0 | execute the hook |
| 4 | That same write is now denied | the same message as the in-project case, naming the role and the path | execute the hook |
| 5 | A role's **allowed** path in a worktree is still allowed | a `tester` writing `<worktree>/tests/x.py` passes | execute the hook |
| 6 | `ALWAYS_DENIED` holds in a worktree | a `programmer` writing `<worktree>/.claude/hooks/guard_paths.py` is denied | execute the hook |
| 7 | **Scratch space is still allowed** | a `tester` writing `C:/tmp/anything/analysis/dcf.py` passes | execute the hook |
| 8 | The hook's cost | the added time per call, measured | time it |
| 9 | The seal no longer clears the first agent | two dispatches, two stops, a sealed file changed between them | execute it |
| 10 | The seal still clears an honest run | one dispatch, one stop, nothing changed | execute it |
| 11 | `check_guard.py` covers both | **more than 48 cases, all passing**, and the new ones named | `.claude/check_guard.py` |
| 12 | The gate | unchanged from criterion 0, by **name** | the gate form, plus three named seeds |
| 13 | Lint | 4 errors, every one `BLE001`. **Run `ruff check .` after the last edit** | `-m ruff check .` |
| 14 | Types | 2 errors in 2 files, or fewer | the mypy command |
| 15 | Census | 64, or fewer | the grep |
| 16 | Route | 200 | `TestClient(...)` |

**Criterion 7 is the one most likely to be broken by a careless fix**, and breaking it would
be invisible until a unit's scratch probe silently stopped working.

## Citations

- `docs/9-reference/refactor-backlog.md`, items 141 and 142, each with the measurement.
- `AGENTS.md` — "This is enforced by permission, not by good intentions", and the 48 cases.
- `.claude/hooks/guard_paths.py:218-221` — the `rel is None` branch.
- `.claude/hooks/seal_baseline.py` — its docstring explains why a dispatch-time snapshot
  exists at all, and that reason must survive the fix.
- `.claude/skills/main-agent/SKILL.md` — why this still goes to a reviewer.
- The user's decision of 2026-10-08, option `a`.

## Known open items

- **Never mutate a file in this repository for a measurement.** Work in a scratch copy and
  print the sha256 before and after. `git stash` is forbidden, and a worktree shares the stash
  stack, which is a second reason.
- **`10K_filings/` and `extractions/` are tracked** as of 2026-10-08, so a worktree carries
  them. Measured: a worktree ran `tests/unit/test_p14g_unit_statement_pages.py` at
  **113 passed**, against the real Walmart PDF, using the main checkout's venv by absolute
  path. A worktree has **no `.venv`**.
- **Windows holds a file lock on a worktree directory after a test run.**
  `git worktree remove` fails the first time and succeeds on a retry. Seen twice on
  2026-10-08. Worth knowing before a unit automates worktree cleanup.
