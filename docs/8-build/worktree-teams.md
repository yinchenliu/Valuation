# Two teams in two worktrees: how to run the pilot

**Read [../0-start.md](../0-start.md) and [../2-rules/rules.md](../2-rules/rules.md) first.**
This file owns **how two agent teams run in parallel in git worktrees**. Nothing else states
it. It is written for a session that starts fresh and has read none of the work that
produced it.

**The user chose two teams, not three, on 2026-10-08.** Two is not a smaller three. It is
the smallest number that tests anything new, because every defect this scheme exposes needs
exactly two agents in flight and no more. A third team adds contention without adding a case.

---

## 1. What is already set up

Measured on 2026-10-08. **Verify, do not redo.**

| Thing | State |
|---|---|
| `C:/Users/LiuYinchen/Valuation-wt/team-a` | worktree on branch `unit/team-a` |
| `C:/Users/LiuYinchen/Valuation-wt/team-b` | worktree on branch `unit/team-b` |
| Both carry `10K_filings/` | **yes**, 3 company folders each |
| Both carry `extractions/WMT.json` | **yes** |
| Both carry `.venv` | **no, and they never will.** It is git-ignored |

```
git worktree list
```

**A worktree has no `.venv`.** Every command inside one uses the main checkout's interpreter
by absolute path:

```
C:/Users/LiuYinchen/Valuation/.venv/Scripts/python.exe -m pytest -q
```

Run it **from** the worktree directory, so `import models` resolves to that worktree's code.
Measured: a fresh worktree ran `tests/unit/test_p14g_unit_statement_pages.py` at **113
passed**, against the real Walmart PDF, that way.

---

## 2. The four rules a unit branch must obey

**Break any of these and the merge is worse than serialising would have been.**

1. **Disjoint Files in scope.** The two units must not name the same file. This is the
   orchestrator's job to check and nobody else's.
2. **A unit branch never touches the four record files**: `STATUS.md`, `.agent/QUEUE.md`,
   `.agent/journal/INDEX.md`, `docs/9-reference/refactor-backlog.md`. They are append-mostly,
   so every merge would conflict on all four. **The orchestrator writes them on `main` after
   each merge.** Subagents already write one journal file each, with a unique name, and those
   never conflict.
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

                     o1 ──▶ o2 ──▶ o3 ─────────────────────────▶ M1 ──▶ M2
                                    │                           ╱       ╱
      unit/team-a  ─────────────────┴──▶ A4 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╱       ╱
                                    │                          *       ╱
      unit/team-b  ─────────────────┴──▶ B4 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╱
                                                                      *
```

1. **Write both assignments on `main`**, before anything starts. Check the two Files in scope
   lists against each other.
2. **In each worktree, run the full loop**: programmer, then code reviewer, then tester. One
   agent at a time per team, so at most two agents are ever in flight.
3. **Merge team A into `main`.** Run the gate.
4. **Merge team B into `main`.** Run the gate again.
5. **Write the records on `main`**: the acceptance in each assignment, `STATUS.md`,
   `.agent/QUEUE.md`, `.agent/journal/INDEX.md`, the backlog. Then push once.

**`unit/team-b` was branched at o3 and does not contain A4.** So the second merge is a real
merge, not a fast-forward, and that is where a conflict appears. The gate after it is testing
a combination that has never run anywhere.

---

## 4. What protects you, and what does not

### The write guard works, including inside a worktree

`P1f-worktree-guards` closed backlog item 142. Before it, `guard_paths.py` allowed every path
outside `CLAUDE_PROJECT_DIR`, and a worktree is outside it, so **in a worktree the guard was
off**: a `tester` writing `<worktree>/analysis/dcf.py` produced no output and exit 0.

It now finds a worktree by reading that tree's `.git` file, which holds
`gitdir: <project>/.git/worktrees/<name>`. So it needs no git on `PATH` and makes no
subprocess call. `.claude/check_guard.py` covers it with **60 cases**, 12 of them worktree
cases, and it **fails rather than skips** if the worktree cannot be built.

```
.venv/Scripts/python.exe .claude/check_guard.py      # expect 60/60
```

### The seal does not work, and it never has

**Backlog items 143 and 144.** Measured three ways and then a fourth:

- `PreToolUse` filters on **tool names only**, and `Agent`, `Task` and `SendMessage` are not
  tool names, so the original matcher could never fire.
- `SubagentStart` and `SubagentStop` are the correct events and are now configured.
- Both hooks were instrumented to record what they are sent **before any exit**, so that "ran
  and exited early" could be told from "never ran".
- One real background subagent was then dispatched and allowed to finish. **The state file
  was never created.** Neither event fires for a background agent, and every dispatch here is
  a background one.

**So `.agent/journal/INDEX.md`, `STATUS.md` and `.claude/hooks/` are unsealed for every
subagent run.** That was true before the pilot and the pilot does not make it worse. The
remaining route is the mods layer's `agent.spawn` event, which needs a plugin with a hooks
module. Item 144 names a cheaper test to try first: dispatch one **foreground** subagent and
see whether the two events fire there.

**What this means in practice.** The guard that keeps a tester out of `analysis/` works. The
tripwire over three bookkeeping files does not. Check the record files yourself after each
merge.

---

## 5. Cleanup, and one Windows trap

```
git worktree remove --force C:/Users/LiuYinchen/Valuation-wt/team-a
git worktree prune
git branch -D unit/team-a
```

**Windows holds a lock on a worktree directory after a process has read from it.**
`git worktree remove` fails the first time and works on a retry. Seen five times on
2026-10-08. Never let cleanup decide a verdict: run it, and if it fails, run
`git worktree prune` and remove the directory later.

---

## 6. The candidate pair for the pilot

Both are small, both are real defects found by earlier units, and neither touches the other's
files. Swap either if something more urgent appears.

| Team | Backlog item | Files in scope |
|---|---|---|
| A | **133**, the two surviving `if target_years:` sites | `ingestion/claude_extractor.py` |
| B | **128**, the CLI reconciliation iterates `raw.years` where the page iterates the union of both sides | `cli.py`, `api/routes_valuation.py` |

**Why these two.** The pilot tests the machinery, not throughput. A failure must be cheap to
diagnose and cheap to throw away.

---

## 7. The gate figures to expect

Measured at `82ac523`, Windows, with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Gate | Expected |
|---|---|
| gate form | **1584 passed, 2 skipped, 0 failed** |
| full suite | **2 failed**, exactly the two `*_rule3_red.py` tests |
| lint | 4 errors, every one `BLE001` |
| types | 2 errors in 2 files |
| census | 64 |
| route | 200 |
| write guard | **60/60** |

**The suite shuffles.** `pytest-randomly` is installed, and **`-q` suppresses the
`Using --randomly-seed=` line**. Re-run without `-q` to recover a seed when something goes
red, use `--randomly-seed=<n>` for anything that must repeat, and **never `-p no:randomly`**:
it stopped being a no-op the moment the plugin was installed.
[environment.md](environment.md) owns this.
