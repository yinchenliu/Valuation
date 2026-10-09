# Two teams in two worktrees: how to run the pilot

**Read [../0-start.md](../0-start.md) and [../2-rules/rules.md](../2-rules/rules.md) first.**
This file owns **how two agent teams run in parallel in git worktrees**. Nothing else states
it. It is written for a session that starts fresh and has read none of the work that
produced it.

**The user chose two teams, not three, on 2026-10-08.** Two is not a smaller three. It is
the smallest number that tests anything new, because every defect this scheme exposes needs
exactly two agents in flight and no more. A third team adds contention without adding a case.

**Who builds, from 2026-10-08, on the macOS machine.** The user's words: "i would like to
use the antigravity gemini agent to work on each of git worktree (total of 2 worktree to
start with) and you are the orchestrator, the main agent, the overall lead". So:

| Where | Who | Does |
|---|---|---|
| `Valuation/` on `main` | Claude Code, the **overall lead** | writes assignments and the four record files, merges, gates, accepts |
| `Valuation-wt/team-a` on `unit/team-a` | Antigravity, **build lead A** | builds one unit with its programmer, code reviewer and tester, commits, hands off |
| `Valuation-wt/team-b` on `unit/team-b` | Antigravity, **build lead B** | the same, for its own unit |

---

## 1. What is set up

Measured on the macOS machine. **Verify, do not redo.**

| Thing | State |
|---|---|
| `/Users/yinchenliu/Documents/Git/DCF/Valuation-wt/team-a` | worktree on branch `unit/team-a` |
| `/Users/yinchenliu/Documents/Git/DCF/Valuation-wt/team-b` | worktree on branch `unit/team-b` |
| Both carry `10K_filings/` and `extractions/WMT.json` | yes: both are tracked |
| `.venv` in each worktree | **a symbolic link** to `../../Valuation/.venv`, the main checkout's venv. `.gitignore` names `.venv` without a slash so the link is ignored too |

```
git worktree list
```

**There is one venv, and every team shares it.** Run every command from the worktree root,
so `import models` resolves to that worktree's code. Measured on 2026-10-08: from a
worktree, `.venv/bin/python -c "import models; print(models.__file__)"` prints the
worktree's path, not the main checkout's.

**`extractions/WMT.json` holds repo-relative PDF paths** (`10K_filings/WMT/<name>`), so it
resolves to the worktree's own copy of each filing. Before 2026-10-08 it held absolute
Windows paths. Backlog item 146 holds why, and why the next route B `plan` would write an
absolute path again.

**The Windows machine made two worktrees of the same names on 2026-10-08.** Their branches
were never pushed and nothing was built in them. They are not these.

---

## 2. The four rules a unit branch must obey

**Break any of these and the merge is worse than serialising would have been.**

1. **Disjoint Files in scope.** The two units must not name the same file. This is the
   overall lead's job to check and nobody else's.
2. **A unit branch never touches the four record files**: `STATUS.md`, `.agent/QUEUE.md`,
   `.agent/journal/INDEX.md`, `docs/9-reference/refactor-backlog.md`. They are append-mostly,
   so every merge would conflict on all four. **The overall lead writes them on `main` after
   each merge.** So in this mode a build lead does **not** set a queue state and does not
   append to the journal index, although [../../AGENTS.md](../../AGENTS.md) tells it to in
   one-worktree mode. Subagents still write one journal file each, with a unique name, and
   those never conflict.
3. **A unit branch installs nothing.** The venv is shared across worktrees, so a unit like
   `P1e-test-order`, which installs `pytest-randomly`, can never be parallel under any
   scheme.
4. **Merge one at a time, and run the gate after EACH merge.** Unit A passes alone and unit B
   passes alone; **nothing has run A and B together until the merge**. Gating after each one
   names the culprit. Gating once at the end does not.

---

## 3. The sequence

```
Legend:  ──▶ normal   ┄┄▶ failure path   * the step people forget

 main         o─────────────────────────────────────▶ M1 ─▶ gate ─▶ M2 ─▶ gate ─▶ records *
              │                                       ▲             ▲
 unit/team-a  ├─▶ programmer ─▶ reviewer ─▶ tester ─▶ A             │
              │                                                     │
 unit/team-b  └─▶ programmer ─▶ reviewer ─▶ tester ─▶ B ────────────┘

 a gate that goes red after a merge ┄┄▶ rework on that branch, merge again
```

1. **The overall lead writes both assignments on `main`**, before anything starts, and
   checks the two Files in scope lists against each other. It sets both units `ready`,
   commits, and creates the worktrees from that commit.
2. **In each worktree, the build lead runs the full loop**: programmer, then code reviewer,
   then tester. One agent at a time per team, so at most two agents are ever in flight.
3. **The build lead commits on its branch, writes `## Handoff`, and tells the user.** The
   user tells the overall lead.
4. **The overall lead checks the branch**: `git diff --name-only main...unit/team-a` names
   only the unit's Files in scope, its assignment files and new journal entries. A file
   outside that list is `rework`, whoever wrote it.
5. **Merge team A into `main`.** Run the gate.
6. **Merge team B into `main`.** Run the gate again.
7. **Write the records on `main`**: the acceptance in each assignment, `STATUS.md`,
   `.agent/QUEUE.md`, `.agent/journal/INDEX.md`, the backlog. Then push once.

**`unit/team-b` was branched before A merged and does not contain A.** So the second merge
is a real merge, not a fast-forward, and that is where a conflict appears. The gate after it
is testing a combination that has never run anywhere.

**For the next round**, the overall lead fast-forwards each branch to the new `main`
(`git -C ../Valuation-wt/team-a merge --ff-only main`) before it sets the next unit `ready`.

---

## 4. What protects you, and what does not

### Nothing in `.claude/` protects an Antigravity agent

The write guard and the seal are Claude Code hooks. **Antigravity does not run them**
([../../AGENTS.md](../../AGENTS.md), "Two teams"). So no permission stops a Gemini tester
from writing `analysis/`, in a worktree or anywhere else. Two checks replace them:

1. **The build lead runs `git status` after every subagent run** and rejects a run that
   wrote outside its role or outside Files in scope.
2. **The overall lead runs the scope check in step 4 of the sequence** before it merges.

### For a Claude Code subagent, the write guard works inside a worktree

`P1f-worktree-guards` closed backlog item 142. Before it, `guard_paths.py` allowed every path
outside `CLAUDE_PROJECT_DIR`, and a worktree is outside it, so **in a worktree the guard was
off**. It now finds a worktree by reading that tree's `.git` file, which holds
`gitdir: <project>/.git/worktrees/<name>`. `.claude/check_guard.py` covers it with
**60 cases**, 12 of them worktree cases.

```
.venv/bin/python .claude/check_guard.py      # expect 60/60
```

### The seal does not work, and it never has

**Backlog items 143 and 144.** `SubagentStart` and `SubagentStop` are now configured, and
neither fires for a background agent, which is every agent Claude Code dispatches here. It
does not matter to this pilot, because no Claude subagent builds in it. **Check the record
files yourself after each merge.**

---

## 5. Starting a build lead

The user opens Antigravity once per worktree, with the worktree folder as the workspace,
and gives it this prompt, with the letter and the unit filled in:

```
You are the build lead for team A in a two-team worktree pilot.
Your workspace is /Users/yinchenliu/Documents/Git/DCF/Valuation-wt/team-a, on branch unit/team-a.
Read docs/0-start.md, docs/2-rules/rules.md, AGENTS.md ("The build lead's procedure")
and docs/8-build/worktree-teams.md. Your unit is P1h-mac-gate:
.agent/assignments/P1h-mac-gate.md. Follow its "Pilot rules (worktree)" where they differ
from AGENTS.md: do not edit .agent/QUEUE.md, .agent/journal/INDEX.md, STATUS.md, docs/,
.claude/ or extractions/, and install nothing. Use .venv/bin/python, never a bare python,
with ANTHROPIC_API_KEY= GEMINI_API_KEY= in front of every command. When the tester passes,
run the gates, commit on unit/team-a, write ## Handoff at the end of the assignment, and
tell me "P1h-mac-gate is ready for the overall lead". Then stop.
```

---

## 6. Cleanup

```
git worktree remove ../Valuation-wt/team-a
git worktree prune
git branch -d unit/team-a
```

`git worktree remove` refuses a worktree with changes that are not committed. That refusal
is the point: read what is there before you pass `--force`. **On Windows**, the directory
stays locked after a process has read from it, and the command works on a retry. That was
seen five times on 2026-10-08.

---

## 7. The current pair

| Team | Unit | Backlog item | Files in scope |
|---|---|---|---|
| A, done | `P1h-mac-gate` | **145**, accepted in round 2 and merged as `d13be2d` | `ingestion/session_extraction.py`, `tests/unit/test_p1h_mac_gate.py` |
| B | `P14h-target-years` | **133**, an empty year list reads as "all years" in two prompt builders | `ingestion/claude_extractor.py`, `tests/unit/test_p14h_target_years.py` |
| B, done | `P3e-reconciliation-years` | **128**, accepted and merged as `f4059c7` | `cli.py`, `tests/unit/test_p3e_reconciliation_years.py` |

**Why these two.** The pilot tests the machinery, not throughput, so a failure must be cheap
to diagnose and cheap to throw away. Item 145 also makes the macOS gate red, so the merge
gates cannot read `0 failed` until it lands. Item 133 (`P14h-target-years`) was team A's
first candidate. It went to team B, because team B finished first and its file is
disjoint from team A's rework.

---

## 8. The gate figures to expect

[../../STATUS.md](../../STATUS.md), section 1, owns the current figures, with the commit
and the machine they were measured on. The commands are in
[environment.md](environment.md), section 4. On macOS, `.venv/bin/python` replaces
`.venv/Scripts/python.exe` in each.

**The suite shuffles.** `pytest-randomly` is installed, and **`-q` suppresses the
`Using --randomly-seed=` line**. Re-run without `-q` to recover a seed when something goes
red, use `--randomly-seed=<n>` for anything that must repeat, and **never `-p no:randomly`**:
it stopped being a no-op the moment the plugin was installed.
[environment.md](environment.md) owns this.
