---
agent: overall lead (implementer — see the assignment, "Who builds this")
assignment: P1f-worktree-guards
round: 1
status: complete
files_touched: [.claude/hooks/guard_paths.py, .claude/hooks/seal_baseline.py, .claude/hooks/seal_check.py, .claude/check_guard.py]
---

# P1f-worktree-guards — the write guard reaches into a worktree, and the seal stops clearing the first of two agents

> **I implemented this unit myself and that is not a shortcut.** `.claude/hooks/*.py` is
> `ALWAYS_DENIED` to every role, measured: a `programmer` writing `guard_paths.py` is refused
> with "a subagent does not edit the permissions that bind it". No subagent can build this.
> **Everything below is therefore an unreviewed claim until the code reviewer re-runs it**,
> which is exactly why the review step is mandatory in the assignment.

## What I did

Two fixes, four files.

**Item 142.** `guard_paths.py` computed `project = CLAUDE_PROJECT_DIR or cwd` and allowed
every path not under it. A worktree is not under it, so in a worktree the guard was off. Two
new functions close that: `worktree_roots(project)` asks
`git worktree list --porcelain` and returns every tree but the project itself, and
`resolve_repo_relative(target, project, cwd)` tries the project first and only then the
worktrees. `main()` calls the second instead of `repo_relative`. **The `rel is None` branch
survives**: a target under no worktree is still outside the repository and still allowed,
which every unit's scratch discipline depends on.

**Item 141.** `seal_baseline.py` rewrote one file on every dispatch, so a second dispatch
overwrote the snapshot the first agent would be judged against and cleared it. It now takes
the snapshot when the in-flight count goes **0 → 1** and otherwise only increments.
`seal_check.py` decrements, **before** any comparison can exit, so a firing cannot strand the
count.

**`check_guard.py`** gained 12 worktree cases, a real temporary worktree to run them in, and
a `PATH` that contains git.

## Done-criteria

| # | Criterion | Result |
|---|---|---|
| 0 | starting commit | `0729d19` |
| 1 | the payload fields, measured | **partly, and honestly: not yet from the harness.** My probe payloads recorded `['cwd','session_id','tool_name']`, which is what *I* sent. **The real keys land in `.agent/.seal-baseline.json` at the first real dispatch**, which is the review that follows this entry. See "What is not finished" |
| 2 | the seal shape chosen, and why | counting, not keying. Chosen because criterion 1 could not be answered before implementing, and counting needs **no** identifier. Reasons in the code |
| 3 | the item 142 "before" reproduced | **yes**, at `0729d19`: `tester` → `<worktree>/analysis/dcf.py` gave no output and exit 0 |
| 4 | that write is now denied | **yes**, and the message is byte-identical to the in-project one: "The `tester` agent may write only `tests/**`, `.agent/journal/**`. `analysis/dcf.py` is outside that." |
| 5 | an allowed path in a worktree still passes | **yes**: `tester` → `<wt>/tests/x.py` allow; `tester` → `<wt>/.agent/journal/x.md` allow |
| 6 | `ALWAYS_DENIED` holds in a worktree | **yes**: `<wt>/.claude/hooks/guard_paths.py` deny, `<wt>/STATUS.md` deny, `<wt>/.agent/journal/INDEX.md` deny |
| 7 | **scratch is still allowed** | **yes**: `tester` → `C:/tmp/scratch/analysis/dcf.py` allow; `programmer` → `C:/tmp/anything/tests/x.py` allow |
| 8 | the hook's cost | median **788 ms** in-project against **863 ms** outside, 7 runs each. **Within interpreter-startup noise** — min 755/425, max 1187/1144. Both dominated by Python process start, and git is only asked when the target is outside the project |
| 9 | the seal no longer clears the first agent | **yes.** See the sequence below |
| 10 | the seal still clears an honest run | **yes**: one dispatch, one stop, nothing changed → cleared |
| 11 | `check_guard.py` covers both | **60/60**, up from 48/48 |
| 12 | the gate | **1382 passed, 2 skipped, 0 failed** at seeds 7, 1234 and 99. Full suite **2 failed**, exactly the two red on purpose, by name. Unchanged from `0729d19` |
| 13 | lint, after my last edit | **4 errors, every one `BLE001`**, none in a file I touched |
| 14 | types | **2 errors in 2 files**, 21 checked |
| 15 | census | **64** |
| 16 | route | **200** |

## The item 142 table, measured

```
                                       at 0729d19   after
tester  <wt>/analysis/dcf.py             ALLOW      DENY    <- the defect
tester  <wt>/models/valuation.py         ALLOW      DENY
tester  <wt>/tests/x.py                  ALLOW      ALLOW
tester  <wt>/.agent/journal/x.md         ALLOW      ALLOW
prog    <wt>/.claude/hooks/guard...py    ALLOW      DENY
prog    <wt>/STATUS.md                   ALLOW      DENY
prog    Bash rm -rf <wt>/tests/unit      ALLOW      DENY
tester  C:/tmp/scratch/analysis/dcf.py   ALLOW      ALLOW   <- must not break
prog    C:/tmp/anything/tests/x.py       ALLOW      ALLOW   <- must not break
tester  <project>/analysis/dcf.py        DENY       DENY    <- control
prog    <project>/models/x.py            ALLOW      ALLOW   <- control
```

## The item 141 sequence, measured

`C:\tmp\p1f_seal_probe.py`, run against a scratch copy at `C:\tmp\p1f_seal`. The repository's
three hooks carry identical sha256 before and after.

```
=== two in flight, agent A changes a sealed file ===
  dispatch A        in_flight=1
  A writes INDEX.md
  dispatch B        in_flight=2
  A stops           in_flight=1  -> FIRED      (silently cleared before this unit)
  B stops           in_flight=0  -> FIRED
=== one in flight, nothing changed ===
  dispatch, stop    in_flight=0  -> cleared
=== one in flight, the agent changes a sealed file ===
  dispatch, write, stop          -> FIRED      (control: single-agent case unaffected)
=== the count returns to 0 even when the seal FIRES ===
  after a firing    in_flight=0
=== a new session_id refreshes a stranded count ===
  two dispatches    in_flight=2  (nothing stopped: stranded)
  new session       in_flight=1  (refreshed)
```

## Decisions, each with its reason

| Decision | Reason | Why this and not the alternative |
|---|---|---|
| Count agents in flight rather than key the baseline per agent | `seal_baseline.py` runs at **dispatch**, and the harness has not created the agent yet, so there may be no identifier common to a dispatch and its stop. **Counting needs none** | Keying would have required an answer to criterion 1 before any code could be written, and criterion 1 can only be answered by a real dispatch. If the review shows a shared identifier exists, keying is a tightening, and I will record it as a follow-up rather than redesign mid-unit |
| B is judged against the state before the window opened, so B can fire for A's write | **A false positive, and that is the direction I chose.** The defect was a silent false negative. A loud flag beats a silent miss | Judging B at its own dispatch needs per-agent keying. The repository already forbids the only write that triggers this: the orchestrator does not write `INDEX.md` while a unit is building |
| `seal_check.py` decrements **before** the comparison | A firing exits 2. A write-back after that exit would never run, and every firing would leave the count one too high for ever | Writing back at the end is the obvious placement and it is wrong for exactly one case — the case the hook exists for |
| `session_id` plus a 12-hour window, not a window alone | An agent killed mid-run never fires `SubagentStop`, so the count strands. **This happened twice in two days.** A new `session_id` catches the session-ended case exactly | A window alone would leave a kill inside one session stranded for 12 hours. A `session_id` alone would leave it stranded for the whole session |
| `worktree_roots` returns `()` on any git failure | A guard that cannot ask the question must not then deny every scratch path. The failure direction leaves behaviour exactly as before this unit | Failing closed would break every unit's scratch probe the moment git was slow or absent |
| git is asked only when the target is **not** under the project | The common case is a path inside the project, which needs no subprocess | Asking always would put a git call before every `Write`, `Edit` and `Bash` of every subagent |
| `check_guard.py` **fails** rather than skips when the worktree cannot be made | A guard check that silently drops its newest cases is backlog item 140's shape, which I recorded yesterday | Skipping would make the count machine-dependent and hide item 142 again |
| `check_guard.py` gets git on `PATH` | With `PATH: ""` git is unreachable, `worktree_roots` returns `()`, and **every worktree case would pass as "allow" for the wrong reason** | Leaving it hermetic would have produced 60/60 that meant nothing |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| the worktree list | `worktree_roots` returns `()`, and the guard behaves as it did before this unit | deliberate, and stated in its docstring. **Not a rule 3 default**: no figure is substituted and no number is invented. A hook is a tripwire, and one that blocked a dispatch because git was slow would be worse than one that misses a check |
| the baseline file | `seal_check.py` falls back to the `HEAD` comparison it already had | unchanged by this unit |
| `in_flight` | missing or unreadable → the snapshot is treated as fresh and rewritten | the safe direction: a fresh snapshot judges the next agent correctly |
| `taken_at` | missing or unparseable → stale, so the snapshot is rewritten | same direction |

## What is not finished, and it is criterion 1

**I could not measure the harness payloads before implementing**, because the only way to see
them is a real dispatch, and a real dispatch is what this hook runs on. So the implementation
records them instead: `seal_baseline.py` writes `payload_keys` into
`.agent/.seal-baseline.json` — **key names only, because a payload carries prompts and a
prompt does not belong in a file the repository keeps.**

**The first real dispatch is the review that follows this entry.** Reviewer: read
`.agent/.seal-baseline.json` and report what `payload_keys` actually contains. If it holds an
identifier common to a dispatch and its stop, say so — it would let a later unit tighten the
count into a per-agent key and remove the false positive described above.

## Found

1. **`check_guard.py` ran the guard with `PATH: ""`.** Hermetic, and it would have made all
   12 new cases pass for the wrong reason. Fixed inside this unit because the cases are this
   unit's.
2. **A Pylance diagnostic, fixed**: `@contextmanager` with `-> Iterator[...]` is deprecated in
   favour of `-> Generator[...]`. `ingestion/session_extraction.py`'s
   `naming_unencodable_characters`, added by `P1e-test-order`, has the same shape and mypy
   does not complain. Not fixed here: it is out of this unit's scope. Worth a backlog line.
3. **Windows holds a lock on a worktree directory after a process reads from it.**
   `git worktree remove` fails the first time and works on a retry. Seen three times on
   2026-10-08. `check_guard.py`'s teardown is best-effort for that reason, and the check's
   exit code does not depend on cleanup succeeding.

---

# Round 2 — answering the review, by number

The code reviewer returned `changes_requested` with two `major`, two `minor` and two `note`
findings. Its entry is `.agent/journal/2026-10-08T1510-code_reviewer-p1f-worktree-guards.md`.
**Every finding is accepted. None was disputed.**

## F1 `major` — the seal takes no baseline at a real dispatch

**Confirmed, and the half the reviewer could not see is now measured too.** I left
`in_flight` at 1 before the review ran, as a natural experiment: if `seal_check.py` fired at
`SubagentStop` it would decrement to 0. **It still reads 1.** So the failure is not only
`seal_baseline.py` at dispatch. **Neither seal hook runs.**

The hook chain is not at fault and I proved that three ways: `seal_baseline.py` run directly
writes the file; `sh run_hook.sh seal_baseline.py` writes it; the syntax parses.

**Two things changed in answer, and the first is an instrument rather than a fix.**

1. `seal_baseline.py` now records `last_dispatch_seen` — payload key names, `agent_type`,
   `tool_name`, timestamp — **before any exit in `main`**, and carries it through a refresh.
   That is the only way to tell "the hook ran and exited early" from "the hook never ran",
   and the next real dispatch answers it.
2. **The role check is now scoped to `SendMessage`.** It existed because a subagent must not
   refresh its own baseline, and `SendMessage` is the one route a subagent has — `Agent` and
   `Task` are disallowed for all three roles. **The reviewer's second candidate cause was
   that the dispatch payload carries the TARGET agent's role**, in which case
   `(data.get("agent_type") or "") in ROLES` was true on every dispatch and the hook exited
   before writing. Scoping the check to `SendMessage` removes that cause and keeps the
   protection where it is reachable.

**This is not claimed as closed.** It is a candidate cause plus an instrument. The next
dispatch decides, and the `SubagentStop` half is untouched by either change.

## F2 `major` — a non-numeric `in_flight` crashed both hooks

**Reproduced before fixing, exactly as reported:**

```
before:  seal_baseline exit=1  ValueError: invalid literal for int() ... 'abc'
         seal_check    exit=1  ValueError: invalid literal for int() ... 'abc'
after:   seal_baseline exit=0
         seal_check    exit=0        in_flight now: 0
```

**My defect, and the reviewer named the consequence correctly**: a crashing hook is a guard
that is off, and before this unit a corrupt baseline healed at the next dispatch. Every read
of the field now goes through `as_count`, which returns 0 for anything that is not an `int`
(and rejects `bool`, which is an `int` in Python and would have counted).

**The second half of F2 is fixed too**: `.agent/.seal-baseline.json` is now in
`ALWAYS_DENIED`, with the reason "a subagent does not edit the instrument that measures it".
A `programmer` could write it before, which is how a subagent could have corrupted the seal's
own state.

## F3 `minor` and F6 `minor` — one change closes both

**The subprocess is gone.** `worktree_roots` is replaced by `worktree_root_of`, which reads
the filesystem: a worktree's `.git` is a **file** holding `gitdir: <project>/.git/worktrees/<name>`,
so walking up from the target to the first `.git` file and checking where it points
identifies a worktree of this repository and of no other.

| | before | after |
|---|---|---|
| 1 in-project target | 788 ms | 690 ms |
| 1 outside target | 863 ms | 986 ms |
| **6 outside targets** | **1,059 ms** (reviewer's figure) | **799 ms** |
| `PATH=""`, `tester` → `<wt>/analysis/dcf.py` | **ALLOW, silently** | **DENY** |

**F6 was the sharper of the two.** A guard may fail open; it must not fail open quietly. It
no longer fails open at all here, because it no longer needs git.

## F4 `note` — do the 12 new cases discriminate?

The reviewer measured 52/60 on a revert and asked whether the other four earn their place.
**Answered by two more mutants rather than by argument:**

| Mutant | Case table | Which cases caught it |
|---|---|---|
| A, revert the fix | **52/60** | the 8 new **deny** cases |
| B, treat every outside path as in-repo | **56/60** | the **pre-existing scratch** cases |
| C, treat every worktree path as denied | **57/60** | three of the four new **allow** cases, by name |

So each new case discriminates against some mutant; they do not all discriminate against the
same one. The allow cases exist for mutant C, which the scratch cases do not catch.

## F5 `note` — the window's reason was wrong

**Corrected, and the correction is in the code.** I wrote "shorter than a working day"; the
reviewer disproved it with session `01fb2109`, which spans 26 hours. A session is not a
working day, so that was never the bound. The number stays 12 because `session_id` already
covers the session-ended case exactly and this window only has to outlast one agent run,
the longest measured being about an hour.

## The reviewer's point about my own justification, which I accept

I defended the false positive by saying the orchestrator is forbidden from writing
`INDEX.md` while a unit is building. **The reviewer pointed out that `.claude/hooks/**` is
sealed too, and that this very unit establishes that the overall lead edits those hooks by
hand.** So a future hook unit overlapping a review would fire the seal on an innocent agent,
and no document forbids that trigger. That is a real argument for the per-agent key as a
follow-up, and it goes in the backlog rather than being waved away.

## Gates after the last edit of round 2

| Gate | Result |
|---|---|
| write guard | **60/60** |
| lint | 4 errors, every one `BLE001`, none in a file I touched |
| types | 2 errors in 2 files |
| census | 64 |
| route | 200 |

`guard_paths.py` is restored byte-identical after every mutant: sha256 `adb1c51a…`, and the
case table reads 60/60 again at the end.

---

# Round 3 — answering the round 2 review

The round 2 reviewer returned `changes_requested` with one blocking finding and three others.
Its entry is `.agent/journal/2026-10-08T1610-code_reviewer-p1f-worktree-guards-r2.md`. **It
confirmed F2 to F6 fixed, reproduced all three mutants exactly, and survived 21 attacks on
criterion 7** including a scratch directory holding its own clone, a `.git` file pointing at
another repository, junk and NUL bytes, junctions both ways, another drive, a UNC path and a
`<wt>_extra` sibling. All correct.

## G1 `major`, the only blocker — **my error, and the exact one the gate warns about**

`ruff check .` gave **5**, not 4: `ISC004` on the `ALWAYS_DENIED` entry I added in round 2.
Criterion 13 says in bold "Run `ruff check .` after the last edit". **I ran it before my last
edit**, which is the defect `STATUS.md` records from `P3c-one-number-tests` and which the
`P3d` and `P14g` testers each caught in their own files by running lint last. I did not.

Fixed, and **the first fix did not work**: I removed a semicolon, assuming the rule objected
to it. It objects to the adjacent literals. Parenthesised instead. `ruff check .` after the
last edit of this round: **4 errors, every one `BLE001`.**

## G2 `minor` — a comment asserting a cause the reviewer had refuted

Round 2 narrowed the role check to `SendMessage` and the comment said it removed the
"payload carries the target agent's role" cause. **The reviewer's measurement falsifies that
cause**: the hook does not run at all, so nothing about `agent_type` can explain it. The
narrowing stands on its own terms and the comment now says so, and names the real protection:
the `ALWAYS_DENIED` entry for the baseline file, measured denied for all three roles.

## G3 `note` — a docstring made false by round 2

`check_guard.py`'s `hook_env` still said the guard shells out to git. Corrected: git is on
`PATH` there only because `temporary_worktree` runs `git worktree add`, and **the guard under
test does not use it**.

## G4 `minor` — and my first fix for it was worse than the defect

`read_state` conflated "file absent" with "file unreadable". I split them. **Then I tested
the result and it was wrong**: with the file unreadable the hook wrote a state with **no
digests**, which makes `seal_check.py` skip all three comparisons in silence — no check at
all, permanently, where the defect was one restarted window.

The second fix is the right one. An unreadable file is unrecoverable: its digests are gone,
so a fresh snapshot is the only option that leaves a working seal, and it self-heals, which
is what the reviewer's F2 asked to preserve. **What G4 really asks is that the loss not be
silent**, so the replacement snapshot records `window_lost_at`. Measured:

```
  dispatch 1,2        in_flight= 2
  dispatch 3, corrupt in_flight= 1   digests present? True
  window_lost_at recorded? True -> 20:15:39
  a stop after that    exit= 0
```

## One more thing I did to myself, worth recording

I applied two of these patches through `python -c` inside a double-quoted bash string. **Bash
ate every backticked word as a command substitution**, and three identifiers vanished from a
comment — `seal_check.py`, `P1f-worktree-guards` and `window_lost_at` — leaving sentences
with holes. I found it by reading the file back, not by being told. Backlog item 75 is the
neighbour of this: **write files with the Write and Edit tools, not through a shell.**

## Criteria 1, 9 and 10 — the escalation, and my ruling

The reviewer refused to decide this and was right to. **The ruling is in the assignment**, as
an amendment above its criteria table: criterion 1 is **struck** to the item 143 unit, and 9
and 10 stand as **met for the hook's logic and not for its wiring**.

**The fact that forces it.** The instrument answered the question it was built for, twice, and
the answer is that no payload arrives. Criterion 1 cannot be measured from inside these four
files. **The fact that decides against holding the unit:** item 142 is independent of the
seal and it is *enforced*, because the write guard's own matcher does fire.

## Gates after the last edit of round 3

| Gate | Result |
|---|---|
| lint | **4 errors, every one `BLE001`** |
| write guard | **60/60** |
| types | 2 errors in 2 files, 21 checked |
| census | 64 |
| route | 200 |
