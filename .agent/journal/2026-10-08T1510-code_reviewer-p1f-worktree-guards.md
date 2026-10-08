---
agent: code_reviewer
assignment: P1f-worktree-guards
round: 1
verdict: changes_requested
---

# Review of P1f-worktree-guards, round 1

Implementer entry: `.agent/journal/2026-10-08T1430-overall_lead-p1f-worktree-guards.md`
(written by the overall lead, because `.claude/hooks/*.py` is `ALWAYS_DENIED` to every
subagent. I treated every claim in it as unmeasured and re-ran all of them.)

Nothing in the repository was mutated. sha256 of all four files, before and after my run:

```
e66fb4fd…b50d1c  .claude/hooks/guard_paths.py      (identical after)
ed76f9e0…4a49a0  .claude/hooks/seal_baseline.py    (identical after)
6516da0a…5588d97 .claude/hooks/seal_check.py       (identical after)
35207feb…7022ab  .claude/check_guard.py            (identical after)
```

My worktree (`C:/tmp/p1f_wt`) was removed and `git worktree list` is back to one entry.
Scratch probes are mine, at `C:/tmp/p1f_rev/`; I did not reuse `C:\tmp\p1f_seal_probe.py`
(it no longer exists on disk).

## The guard checks

Run over the four files in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean |
| lookup with a fallback — `.get(k, 0)` | 2 hits, neither a value: `guard_paths.py:276` (`isinstance` test), `check_guard.py:132` (`SYSTEMROOT`) |
| bare or-default — `or 0.0` | 14 hits, all payload parsing. 9 pre-existing; 6 new in `seal_baseline.py:167,178,179,188,190` and `seal_check.py:120`. The entry answers the two that carry meaning (`in_flight`, `taken_at`) in its own rule-3 table — but see **F2**, where that answer is wrong |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean |

## Rule 3, by reading

No value in this diff reaches a displayed figure; these are hooks. The question still
applies to each value the unit reads.

| Value | Stops and names it? | Evidence |
|---|---|---|
| the worktree list | No — `()`, and the guard reverts to pre-fix behaviour | deliberate, stated in the docstring, reason given. Measured: with `PATH=""`, `tester → <wt>/analysis/dcf.py` is **allowed**. See **F6** |
| the baseline file, absent | No — falls back to the HEAD comparison | unchanged by this unit; measured `exit 0` |
| the baseline file, not JSON / not a dict | Treated as absent | measured: dispatch exit 0, stop exit 0 |
| `in_flight`, non-numeric | **No — both hooks crash and the seal performs no comparison** | measured `ValueError`, exit 1 on both. **F2** |
| `taken_at`, missing or unparseable | Treated as stale, snapshot rewritten | measured; matches the entry |

## Units and boundaries

No financial figure, no percentage, no `analysis/` import is touched by this diff.
Layering: `guard_paths.py` adds only `subprocess`; `check_guard.py` adds `contextlib`,
`shutil`, `collections.abc`. No repository import crosses a layer.

## Done-criteria, re-run

| # | Criterion | Entry claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | payload fields measured | deferred to this review | **not measured — see F1.** `.agent/.seal-baseline.json` holds `["cwd","session_id","tool_name"]`, `session_id: "wrapper-test"`, from the lead's own hand-run probe. 20 minutes earlier it held `["cwd","hook_event_name","session_id","tool_name"]`, `session_id: "manual-test"`. **No harness payload has ever been recorded** | no |
| 2 | the seal shape chosen, and why | counting | the reasoning is sound *given* criterion 1 is unanswerable, but criterion 1 is unanswerable because of F1, not because no identifier exists | partly |
| 3 | item 142 "before" reproduced | allow, exit 0 | **yes.** `git show 0729d19:.claude/hooks/guard_paths.py` run against a real worktree: `tester → <wt>/analysis/dcf.py` → no output, exit 0. 7 of my 19 cases differ at that commit | yes |
| 4 | that write is now denied | byte-identical message | **yes.** "The `tester` agent may write only `tests/**`, `.agent/journal/**`. `analysis/dcf.py` is outside that." — identical to the in-project control | yes |
| 5 | allowed paths still pass in a worktree | yes | **yes**, plus relative paths with cwd inside the worktree (`analysis/dcf.py` → deny, `tests/x.py` → allow) | yes |
| 6 | `ALWAYS_DENIED` holds in a worktree | yes | **yes**: hook, `STATUS.md`, `INDEX.md` all denied; the Bash tripwire reaches in too | yes |
| 7 | **scratch still allowed** | yes | **yes**, 6 cases across 3 roles: `C:/tmp/**` for Write and Bash, and an unrelated outside path. A sibling directory named `<wt>_extra` is correctly *not* treated as a worktree; a lower-case drive letter *is* | yes |
| 8 | the hook's cost | 788 vs 863 ms, "within interpreter-startup noise" | the added work is **51.7 ms median** (`git worktree list --porcelain`, 15 runs, min 50.3 max 55.2) against a 400–1400 ms interpreter start, so the claim holds **for one candidate path**. It does not hold per call: see **F3** | partly |
| 9 | the seal no longer clears the first agent | FIRED, FIRED | **yes**, my own probe: A writes INDEX.md, B dispatched, A stops → FIRED (`in_flight` 2→1), B stops → FIRED (→0) | yes |
| 10 | the seal still clears an honest run | cleared | **yes**, exit 0 | yes |
| 11 | `check_guard.py` covers both | 60/60 | **yes, 60/60, exit 0.** Reverted `guard_paths.py` alone in an isolated scratch repo: **52/60, exit 1**, the 8 deny-in-a-worktree cases flipping. The other 4 new cases do not discriminate — **F4** | yes |
| 12 | the gate | 1382 passed, 2 skipped, 0 failed | **1382 passed, 2 skipped** at `--randomly-seed=7` (167 s) | yes |
| 13 | lint | 4, all `BLE001` | **4, all `BLE001`**, in `api/routes_valuation.py` ×2, `cli.py`, `tests/test_e2e_all_googl.py`. `ruff check .claude/` passes, so the new code is linted and clean | yes |
| 14 | types | 2 errors in 2 files | **2 errors in 2 files, 21 checked** | yes |
| 15 | census | 64 | **64** | yes |
| 16 | route | 200 | **200** | yes |

## Findings

### F1 — the seal takes no baseline at a real dispatch, so criterion 1 is unmet and criteria 9–10 are synthetic only · `major`

**Evidence:** the orchestrator's own transcript, session `01fb2109`, 2026-10-08T17:38:50Z
dispatches this review; at 17:38:56Z `cat .agent/.seal-baseline.json` returns
`No such file or directory` — after **14 real dispatches in that session**, two of them
today (14:37Z, 15:16Z) under the *old* hook. A filesystem-wide search
(`find C:/Users/LiuYinchen -name .seal-baseline.json -newermt 2026-10-08`) finds exactly
one file: the lead's hand-run probe, now stamped `session_id: "wrapper-test"`.

**Rule or document:** the assignment's criterion 1 and 2; `seal_baseline.py`'s own
docstring — "It runs on PreToolUse for Agent, Task and SendMessage … the orchestrator's
last action before that subagent runs."

**What it means.** The non-firing is **not caused by this diff** — it reproduces with the
old hook — so it is not a defect the unit introduced. But it is the hook the unit touched,
it is not in the backlog, and it has three consequences the unit cannot be accepted
without: criterion 1 has now been attempted and come back empty; the shape decision in
criterion 2 rests on a question that was never answerable by the route chosen; and the
item-141 fix has been demonstrated **only against payloads the lead wrote by hand**. In
the live harness the seal has been running on its blunt HEAD fallback the whole time.

**What would fix it:** find why the `Agent|Task|SendMessage` matcher produces no write
while the `Write|Edit|Bash` matcher demonstrably fires (two candidates, both cheap to
test: an async agent launch not running `PreToolUse` hooks, or the dispatch payload
carrying `agent_type` of the *target* role, which makes `seal_baseline.py:140` exit 0
before it writes). Then re-run criteria 9 and 10 against one real dispatch.

### F2 — a baseline whose `in_flight` is not a number crashes both hooks, disables the seal, and no longer self-heals · `major`

**Evidence:** my probe, `C:/tmp/p1f_rev/seal_probe.py`:

```
in_flight = "abc"    dispatch exit=1  stop exit=1  ValueError: invalid literal for int() with base 10: 'abc'
```

and the write guard allows the file to be written by a role:
`programmer → .agent/.seal-baseline.json : allow` (also allowed in a worktree).

**Rule or document:** `seal_baseline.py`'s docstring — "the role check below is what stops
a subagent refreshing the measurement taken of it. **That check is load bearing, not
defensive tidiness.**" Writing `{"in_flight": "abc"}` is a refresh by another name: it is
the one value a subagent can put in that file that makes `seal_check.py:120` raise before
any comparison runs, and `run_hook.sh` documents that the seal hooks only warn, so the
subagent finishes unchecked and silently. The entry's own rule-3 table claims
`in_flight` "missing or unreadable → the snapshot is treated as fresh and rewritten";
measured, that is true for `null` and for a non-dict file, and **false** for a
non-numeric value.

Before this unit the same file could not do this: `seal_check.py` only compared hashes by
key, and `seal_baseline.py` rewrote the file unconditionally at every dispatch, so a
corrupt file healed itself on the next dispatch. Both properties are gone.

**What would fix it:** read the count through a helper that returns `0` for anything that
is not an `int`, the way `read_state` already returns `None` for anything that is not a
dict — in both hooks.

### F3 — `worktree_roots` is called once per candidate path, not once per process · `minor`

**Evidence:** `guard_paths.py:293` calls `resolve_repo_relative` inside the candidate
loop, and `resolve_repo_relative` calls `worktree_roots` with no cache. Measured, same
payload shape: `rm -f` with **1** scratch target → min **454 ms**; with **6** outside
targets (`rm` ×4, `cp`, a redirection) → min **1059 ms**; 4 *in-project* targets → min
**525 ms**. That is roughly one 50–120 ms `git` call per outside path.

**Rule or document:** the assignment, "What to do" step 4 — "If `git worktree list` is
slow, **cache it for the life of the process** and say what you measured." The hook is one
process per tool call, so the life of the process is exactly this loop. The entry's
criterion-8 measurement used a single-candidate payload and so could not see it.

**What would fix it:** `@functools.cache` on `worktree_roots`.

### F4 — four of the twelve new guard cases do not distinguish the fix from its absence · `note`

**Evidence:** with `guard_paths.py` reverted to `0729d19` in an isolated scratch repo and
the new `check_guard.py` unchanged: **52/60**. The eight deny-in-a-worktree cases flip;
`tester → <WT>/tests`, `tester → <WT>/.agent/journal`, `programmer → <WT>/analysis` and
`Explore → <WT>/analysis` pass either way. They are useful as regression guards for the
allow direction, which is what criterion 7 protects, so this is a note and not a defect —
but the entry's "12 worktree cases" is better read as "8 that prove item 142 and 4 that
protect scratch".

### F5 — the 12-hour window's stated reason is not supported by this repository's sessions · `note`

**Evidence:** `seal_baseline.py` — "shorter than a working day, so an abandoned count
cannot survive to the next one". Session `01fb2109` carries dispatches from
2026-10-07T15:01Z to 2026-10-08T17:38Z: **over 26 hours and 14 dispatches under one
`session_id`**. So the `session_id` lever does not catch a stranded count inside a long
session, and 12 hours is the whole backstop, not a short one.

The number is still defensible, because the error direction is loud: a window that is too
**long** judges the next agent against a pre-kill snapshot and fires a false positive,
while a window that is too **short** re-opens item 141's silent false negative. Erring
long is right. Only the reason as written needs correcting.

### F6 — a missing `git` silently restores the item-142 hole, and nothing says so · `minor`

**Evidence:** measured with `PATH=""`, which is not hypothetical — it is the environment
`check_guard.py` itself used until this unit changed it:

```
tester  <wt>/analysis/dcf.py   no git -> allow
tester  <project>/analysis/dcf.py no git -> deny
```

**Rule or document:** no rule; this is the judgement the entry asked for, so I give my
reason rather than a verdict. For an *outside* path the failure direction is correct —
denying every scratch path when git is slow would break every unit. But the result of the
failure is not "no decision", it is **"allow" for a path that is inside the repository**,
which is exactly the defect this unit exists to close, restored under a condition that
produces no output anywhere. A guard may fail open; it should not fail open quietly.

**What would fix it:** either one line on stderr when `git` could not be reached and the
target was outside the project (stderr from a `PreToolUse` hook does not block), or drop
the subprocess altogether — a worktree root is identifiable without git, because
`<root>/.git` is a *file* whose first line reads `gitdir: …/worktrees/<name>`. Walking up
from the target and reading that file answers the same question with no `PATH`
dependency, and it would close **F3** at the same time.

## The three judgements you asked for, on my own account

**The false positive you chose.** Right trade, and for the reason you give: a loud flag
beats a silent miss, and the message already tells an agent that did not touch the file to
say so and finish rather than restore it. One correction to the reasoning, though. You
justify it by `main-agent` forbidding `INDEX.md` writes while a unit builds — but
`INDEX.md` is not the only sealed thing. `.claude/hooks/**` is sealed too, and *this unit
establishes that the overall lead edits those hooks by hand* (you edited three of them at
16:41Z today). The next hook unit that overlaps a review will fire the seal on an innocent
reviewer, and that trigger is not forbidden by any document. It is still the right
direction — but it strengthens the case for the per-agent key as a follow-up rather than
leaving it optional.

**`worktree_roots` returning `()`.** See F6. Direction defensible, silence not.

**The 12-hour window.** See F5. Number defensible, stated reason not.

## Criterion 1 — what `payload_keys` actually contains

You asked me to read it and report plainly. It contains **nothing from the harness**.

At 17:39:14Z it held `["cwd","hook_event_name","session_id","tool_name"]` with
`session_id: "manual-test"`; at 18:01:34Z, while I was reviewing, it was rewritten to
`["cwd","session_id","tool_name"]` with `session_id: "wrapper-test"`. Both are the keys of
payloads *you* echoed into the hook by hand, visible as such in the session transcript at
17:39:12Z and after. The real dispatch at 17:38:50Z wrote nothing at all, which is F1.

So: **no identifier common to a dispatch and its stop has been observed**, because no
dispatch payload has been observed. Fact 3 of the assignment is still open, and the
counting shape remains the only justified choice until F1 is explained. I cannot tell you
whether a per-agent key is available, and neither can that file in its present state.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 140 (a check that silently drops cases) | `check_guard.py` worktree teardown | the unit explicitly fails rather than skips — the right answer, and it closes the shape rather than repeating it |
| the `Iterator`/`Generator` contextmanager shape in `ingestion/session_extraction.py` | reported in the entry's "Found" 2 | not touched, correctly left out of scope |

`.agent/QUEUE.md` is modified in the working tree (row 6k, `ready` → `building`) and is
not in **Files in scope**. It is the orchestrator's own queue bookkeeping, carries no
code, and the entry does not list it as touched. I checked it and it is not a finding.

## Verdict

`changes_requested`

Two `major` findings stand. **F2** is the one I would fix first: this unit's purpose is to
make a tripwire harder to defeat, and it has introduced a value — writable by a
`programmer`, reachable by accident — that turns both halves of that tripwire off with a
`ValueError` and no self-healing. **F1** is not a defect the diff caused, but it means the
unit's central seal claim has only ever been demonstrated against hand-written payloads,
and the one criterion that was deferred to this review has come back empty; the cause has
to be found before criteria 1, 2, 9 and 10 can be called measured. Everything in the item
142 half of the unit I re-ran independently and it is correct, including the criterion the
assignment named as most fragile: scratch space under `C:/tmp` stays allowed for every
role, 6 cases, and the 60-case table drops to 52 when the fix is reverted. F3 and F6 are
small and both are closed by the same change.
