---
agent: code_reviewer
assignment: P1f-worktree-guards
round: 2
verdict: changes_requested
---

# Review of P1f-worktree-guards, round 2

Implementer entry: `.agent/journal/2026-10-08T1430-overall_lead-p1f-worktree-guards.md`,
second half ("Round 2 — answering the review, by number"). Round 1 review:
`.agent/journal/2026-10-08T1510-code_reviewer-p1f-worktree-guards.md`. I am a different
run from that reviewer and re-executed every claim in both.

Nothing in the repository was mutated. sha256 of the four files in scope, before my first
command and after my last:

```
35207feb…7022ab  .claude/check_guard.py          identical after
adb1c51a…64b5a1  .claude/hooks/guard_paths.py    identical after
8e1268d9…0f6345  .claude/hooks/seal_baseline.py  identical after
e2bd742c…03fa3a  .claude/hooks/seal_check.py     identical after
```

`git worktree list` is back to one entry; my worktree, two junctions and seven hostile
scratch trees are removed or confined to `C:\tmp\p1f_r2\`. No `git stash`.

HEAD moved during my run, from `0729d19` to `e9504ac` ("Item 143: neither seal hook has
ever fired on this harness"). That commit touches only
`docs/9-reference/refactor-backlog.md`, so the diff under review is unchanged.

---

## The live experiment: did `seal_baseline.py` run at MY dispatch?

**No. `last_dispatch_seen` is absent, and the file was not touched at all.**

| | |
|---|---|
| my dispatch | ≈ 2026-10-08T19:00Z |
| `.agent/.seal-baseline.json` `taken_at` | `2026-10-08T18:43:01Z` — 17 minutes *before* me |
| its keys | `index_sha256, status_sha256, hooks_sha256, taken_at, tool, session_id, in_flight, payload_keys` |
| `last_dispatch_seen` | **absent** |
| `session_id` | `"x"` — a hand probe, not a harness value |
| mtime of the file | 14:43:02 local; mtime of `seal_baseline.py` is 14:43:**36**, 34 s *later* |

So the file on disk was written by the round-1 shape of the hook and then decremented to
`in_flight: 0` — it predates the round-2 instrument. A filesystem-wide search found no
`.seal-baseline.json` anywhere written after 14:43 local
(`find /c/Users/LiuYinchen /c/tmp -name .seal-baseline.json`; three hits, all older, two of
them scratch).

The instrument itself works. Run by hand against a scratch tree, the same hook writes
`last_dispatch_seen` even onto a corrupt baseline:

```
after dispatch on {"in_flight": "abc"}:  keys = [hooks_sha256, in_flight, index_sha256,
  last_dispatch_seen, payload_keys, session_id, status_sha256, taken_at, tool]
```

**I extended the experiment to the one route round 2 bets on.** At 20:06:54Z I recorded
`sha256 = f30b09d1…74374c2e` for `.agent/.seal-baseline.json`, called `SendMessage` live
(it returned `No agent named '…' is reachable`, which is after `PreToolUse`), and at
20:07:05Z the file read **byte-identical, same sha256**. So the `PreToolUse` matcher
`Agent|Task|SendMessage` is dead for `SendMessage` too, not only for `Agent`. That is new
beyond backlog item 143, which tested `Agent` only.

**What this means for the round 2 change.** The role check was rescoped to `SendMessage`
to remove the candidate cause "the dispatch payload carries the TARGET agent's role". That
cause is now falsified: the hook does not run, so it never reached the role check on any
route. The rescoping is beside the point as a fix — see **G2**.

**The `SubagentStop` half, read the same way.** `in_flight` reads `0` now. If
`seal_check.py` fires at my own `SubagentStop`, it will decrement and `max(0, 0-1)` keeps
it at `0`, so the count cannot discriminate this time. **The discriminating key is
`last_dispatch_seen`**: `seal_check.py` does `updated = dict(baseline)` and so preserves
every key, but it writes nothing new. So after my stop the file should still have no
`last_dispatch_seen`, and `taken_at` should still read `18:43:01Z`. **If `taken_at` or the
hashes change, `seal_check.py` fired.** They should not, because nothing fires.

---

## The guard checks

Run over the four files in scope only.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean |
| lookup with a fallback — `.get(k, 0)` | 2 hits, neither a value: `guard_paths.py:291` (`isinstance` test), `check_guard.py:132` (`SYSTEMROOT`) |
| bare or-default — `or 0.0` | 16 hits, all payload parsing, no figure. The two that carry meaning (`in_flight`, `taken_at`) now go through `as_count` / `is_stale` — this is round 1's F2, fixed. One new hit changes behaviour: `seal_baseline.py:188`, see **G2** |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean |

`subprocess` no longer appears in `guard_paths.py` at all — the only hit is the word
inside a docstring at line 134. Round 1's F3 and F6 both turned on that call.

## Rule 3, by reading

No value in this diff reaches a displayed figure; these are hooks. The question still
applies to each value read.

| Value | Stops and names it? | Evidence |
|---|---|---|
| the worktree list | n/a — there is no list any more; `worktree_root_of` reads `<dir>/.git` | measured: `PATH=""` and `PATH=C:/nonexistent` both still **deny** `<wt>/analysis/dcf.py` |
| `in_flight`, any non-int | No — `as_count` returns 0, and that is the self-healing direction | 6 corrupt shapes, both hooks exit 0, count returns to 0 |
| `taken_at`, missing or unparseable | treated as stale, snapshot rewritten | `is_stale` returns True for non-`str`, bad ISO and naive datetimes |
| the baseline file, absent / not a dict | treated as absent, fresh snapshot | measured, exit 0 both hooks |
| `tool_name`, missing | **No — the role check is skipped entirely.** See **G2** | `seal_baseline.py:188` |
| the baseline file, transient read failure mid-window | **No — the window is silently restarted.** See **G4** | `seal_baseline.py:177` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | n/a, no figure in this diff |
| percentages converted at the route boundary, once | n/a |
| falsy not treated as missing | `as_count` correctly rejects `bool`, which `int()` would have accepted. No new falsy-is-missing shape |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | unchanged; `guard_paths.py` now imports **fewer** modules than round 1 |

## Done-criteria, re-run

| # | Criterion | Entry claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | payload fields measured | instrument added, answer deferred to this dispatch | **the instrument answered: the hook never runs.** `last_dispatch_seen` absent; `SendMessage` probe left the file byte-identical. **No harness payload has been observed on any of the three routes.** Criterion 1 is unmeetable by this unit — see **F1** below | no, and it cannot be |
| 3 | item 142 "before" reproduced | allow, exit 0 | **yes**, `git show HEAD:.claude/hooks/guard_paths.py` in an isolated scratch repo: **52/60**, the 8 deny-in-a-worktree cases flipping to allow | yes |
| 4 | that write is now denied | byte-identical message | **yes** | yes |
| 5 | allowed paths still pass in a worktree | yes | **yes**, including relative paths with `cwd` inside the worktree (`tests/x.py` allow, `analysis/dcf.py` deny, `./STATUS.md` deny, `echo hi > STATUS.md` deny) | yes |
| 6 | `ALWAYS_DENIED` holds in a worktree | yes | **yes**; and `.agent/.seal-baseline.json` is now denied to all three roles | yes |
| 7 | **scratch still allowed** | yes | **yes — 21 cases, including 9 built to break it.** Table below | yes |
| 8 | the hook's cost | 799 ms for 6 outside targets | **yes, and better than claimed.** In-process, `resolve_repo_relative` ×6 outside targets = **0.415 ms median** (max 0.728), against ~50 ms *per path* for the round-1 subprocess. End to end, 6 outside targets: current min **409.7 ms**, pre-unit HEAD min **325.7 ms**, n=11 — interpreter start dominates | yes |
| 9 | the seal no longer clears the first agent | FIRED, FIRED | **yes**, my own sequence: A writes INDEX.md, B dispatched, A stops → exit 2 (`in_flight` 2→1), B stops → exit 2 (→0). **Synthetic only**, per F1 | yes, synthetically |
| 10 | the seal still clears an honest run | cleared | **yes**, exit 0, `in_flight` 1→0. Synthetic only | yes, synthetically |
| 11 | `check_guard.py` covers both | 60/60 | **yes, 60/60, exit 0** | yes |
| 12 | the gate | 1382 passed, 2 skipped | **1382 passed, 2 skipped, 2 warnings** at `--randomly-seed=238039579`, 140.55 s | yes |
| 13 | lint, after the last edit | "4 errors, every one `BLE001`, none in a file I touched" | **5 errors. One is `ISC004` at `.claude/hooks/guard_paths.py:79`, added by this unit's round-2 edit.** See **G1** | **no** |
| 14 | types | 2 errors in 2 files | **2 errors in 2 files, 21 checked** | yes |
| 15 | census | 64 | **64** | yes |
| 16 | route | 200 | **200** | yes |

### Criterion 7, the nine cases built to break it

`worktree_root_of` walks parents looking for a `.git` **file**. I tried to defeat it.

```
allow  scratch holding its OWN clone (.git is a directory)
allow  deeper inside that clone
allow  .git FILE pointing at ANOTHER repository's .git/worktrees/w
allow  .git FILE holding junk and NUL/0xFF bytes
allow  .git FILE empty
allow  .git FILE pointing at <project>/.git itself (submodule shape, not a worktree)
allow  junction (mklink /J) into a scratch clone
allow  another drive (D:/…), and a UNC path (\\server\share\…)
deny   .git FILE pointing at <project>/.git/worktrees/<pruned>   <- correct: still this repo's checkout
deny   junction into the real worktree
deny   lower-case drive letter, backslashes, and a path through `..`
allow  sibling directory named `<wt>_extra`
```

All 21 as expected. The one that surprised me, `ghost_wt`, denies — and it should: a
directory whose `.git` names this project's `worktrees/` is this repository's checkout
whether or not git has pruned the entry, and the error direction is closed, not open.

---

## Findings

### G1 — the lint gate is red, and the entry says it is green · `major`

**Evidence:**

```
$ .venv/Scripts/python.exe -m ruff check .
ISC004 Unparenthesized implicit string concatenation in collection
  --> .claude\hooks\guard_paths.py:79:6
Found 5 errors.
```

The other four are the known `BLE001`s. Running ruff over the HEAD copy of the same file
and the working copy side by side: HEAD clean, working copy one `ISC004`. The offending
lines are the round-2 `.agent/.seal-baseline.json` entry added to `ALWAYS_DENIED` at
`guard_paths.py:78-80`.

**Rule or document:** the assignment, criterion 13 — "Lint | 4 errors, every one `BLE001`.
**Run `ruff check .` after the last edit**". The entry's round-2 gate table claims "4
errors, every one `BLE001`, none in a file I touched". Measured, that is false, and the
new error is in a file and on lines this unit wrote. The criterion carries that bold
instruction precisely because the last edit is the one that gets missed, and it was.

**What would fix it:** wrap the two string fragments in parentheses, or join them into one
string, then re-run `ruff check .` as the last command.

### G2 — the role check was narrowed on a hypothesis this dispatch falsifies · `minor`

**Evidence:** `seal_baseline.py:188` —
`if (data.get("tool_name") or "") == "SendMessage" and (…agent_type…) in ROLES:`. My live
`SendMessage` at 20:07:00Z left `.agent/.seal-baseline.json` at sha256 `f30b09d1…74374c2e`,
unchanged from 20:06:54Z, so the hook did not run on that route either.

**Rule or document:** no rule in `rules.md`; this is the file's own docstring — "the role
check below is what stops a subagent refreshing the measurement taken of it. **That check
is load bearing, not defensive tidiness.**" The entry's stated reason for narrowing it is
"the reviewer's second candidate cause was that the dispatch payload carries the TARGET
agent's role … Scoping the check to `SendMessage` removes that cause". Measurement says
the cause is neither candidate: the hook is not invoked at all, on any of the three tools.
So a load-bearing check was narrowed for a reason that no longer holds, and the narrowing
has its own cost: a payload whose `tool_name` is absent, or is `Agent` or `Task`, now
passes the check whatever `agent_type` says, where before any role exited.

What I did confirm, and it limits the exposure to near zero today: `Agent, Task` are in
`disallowedTools` for all three roles (`.claude/agents/{programmer,tester,code-reviewer}.md:7`),
and the real protection added by round 2 — `.agent/.seal-baseline.json` in `ALWAYS_DENIED`
— denies the direct write for all three roles, measured. So I do not ask for the narrowing
to be reverted. I ask for the comment above it to stop asserting a cause that has been
tested and refuted, and for the scoping either to be justified on its own terms or to be
widened back to "any payload carrying a role".

**What would fix it:** replace the four comment lines citing the "TARGET agent's role"
candidate with what was measured — the hook is not invoked, backlog item 143 — and say in
one line why `SendMessage` is the right scope on its own merits.

### G3 — `check_guard.py`'s `hook_env` docstring describes the round-1 design · `note`

**Evidence:** `.claude/check_guard.py:124-128` — "Since `P1f-worktree-guards` the guard
asks git which worktrees exist, so git has to be reachable or every worktree case would
pass as 'allow' for the wrong reason." Round 2 removed the subprocess; I verified the
worktree cases pass with `PATH=""`. The sentence is now false, and it is the justification
for the only non-hermetic thing in the check's environment.

**Rule or document:** none. A stale docstring on the line that explains an environment
choice, which is exactly the kind a later reader trusts.

**What would fix it:** say that git is needed by `temporary_worktree` (which does shell
out, correctly) and no longer by the guard, so `PATH` may be narrowed or dropped.

### G4 — a transient read failure at dispatch N>1 silently restarts the in-flight window · `note`

**Evidence:** `seal_baseline.py:177` — `seen = read_state(path) or {}`, then
`seen["last_dispatch_seen"] = observation`, then `write_state(path, seen)` **before** the
role check and before `previous` is computed. `read_state` returns `None` on `OSError` as
well as on corrupt JSON. On a locked-file read at the second dispatch of a window, the
file is replaced by `{"last_dispatch_seen": …}`, `previous` is then that one-key dict,
`as_count(None)` is 0, `fresh` is True, and a new snapshot is taken mid-window with
`in_flight: 1` — which is item 141's false negative for the agent already in flight.

**Rule or document:** none; the entry's own round-2 reasoning that the instrument is
written "before any exit in `main`" is right, and this is the one side effect of doing it
by rewriting the whole file. Windows file locking is not hypothetical here — the entry
records it three times for worktree directories.

**What would fix it:** distinguish "unreadable" from "absent" in `read_state`, or write the
observation only after `previous` has been captured from the same read.

---

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| **143**, neither seal hook has ever fired on this harness, recorded at `e9504ac` during my run | `.claude/settings.json` `PreToolUse` matcher `Agent\|Task\|SendMessage`, and the `SubagentStop` block | the unit touched both hooks but **did not cause this**: it reproduces at HEAD, and the cause is the matcher, which is not in Files in scope. My `SendMessage` measurement **extends** item 143: the matcher is dead for `SendMessage` as well as `Agent`, which the item does not yet say |
| 140, a check that silently drops cases | `check_guard.py` worktree teardown | the unit fails rather than skips — it closes the shape |
| 141, 142 | both are what this unit fixes | — |

`.agent/QUEUE.md` is modified in the working tree and is not in Files in scope. It is the
orchestrator's queue bookkeeping, carries no code, and I checked it: not a finding.

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| F1 `major` | **not_fixed, and not fixable inside this unit** | The round-2 instrument is the right answer to "find why", and it answered: the hook never runs, on any of the three tools. That is now backlog item 143 and it is **not a defect of this diff** — it reproduces at HEAD. But the assignment's criteria 1, 9 and 10 still cannot be met: no harness payload has been observed, so the counting-versus-keying decision of criterion 2 rests on a question that remains unanswered, and criteria 9 and 10 remain synthetic. **This is an assignment-versus-reality conflict and it is the orchestrator's to resolve, not mine.** Either criteria 1, 9 and 10 are struck from this unit and handed to the item-143 unit, or this unit waits for item 143. I do not decide which, and I do not count it among the findings that block |
| F2 `major` | **fixed** | 6 corrupt shapes — `"abc"`, `true`, `null`, non-JSON, a JSON list, an empty file — all give dispatch exit 0 and stop exit 0, `in_flight` back to 0. Self-healing is restored: a dispatch onto `{"in_flight": "abc"}` writes a full fresh snapshot and the next stop FIRES correctly (exit 2). `as_count` rejects `bool`, which `int()` would have accepted. The second half is fixed too: `.agent/.seal-baseline.json` is denied to `programmer`, `tester` and `code-reviewer` |
| F3 `minor` | **fixed** | The subprocess is gone. `resolve_repo_relative` ×6 outside targets = **0.415 ms median** in-process. The round-1 1,059 ms figure does not reproduce: end to end, 6 outside targets min **409.7 ms** against the pre-unit guard's **325.7 ms**, n=11 |
| F4 `note` | **fixed — all three mutants reproduced exactly** | A (revert to HEAD) **52/60**, the 8 deny cases. B (every outside path in-repo) **56/60**, and the four it flips are the pre-existing scratch cases, by name: `scratch space is not guarded`, `pytest redirected to scratch`, `sed -i on a scratch file`, `sed -i.bak on a scratch file`. C (every worktree path denied) **57/60**, and the three are exactly the ones named: `tester MAY write tests in a worktree`, `tester may write its journal in a worktree`, `programmer MAY write analysis in a worktree`. The fourth allow case, `Explore → <WT>/analysis`, is caught by none of the three, because `Explore` exits before any path is resolved — the entry's "three of the four" is honest about that |
| F5 `note` | **fixed** | `seal_baseline.py:86-100` now says the 12 hours is bounded by the longest single agent run, names the session that disproved the old reason, and keeps the number. The reasoning is correct as written |
| F6 `minor` | **fixed** | `PATH=""` and `PATH=C:/nonexistent` both **deny** `<wt>/analysis/dcf.py` and both still allow `C:/tmp/anything/analysis/dcf.py`. It no longer fails open, because it no longer needs git |

## Verdict

`changes_requested`

One `major` stands and it is **G1**: `ruff check .` reports 5 errors where criterion 13
requires 4, the fifth is `ISC004` on lines this unit added at `guard_paths.py:79`, and the
entry's round-2 gate table states the opposite. It is a one-line fix and the criterion
spells out the discipline that would have caught it. Everything the round-1 review asked
for is genuinely done: **F2 through F6 are all fixed and I re-measured each one
independently**, including the three mutants, the nine hostile scratch trees and the
no-git case. The item 142 half of this unit is in good shape — 60/60, the mutants
discriminate, criterion 7 survived every attack I could build, and the cost fell by two
orders of magnitude when the subprocess went away. **F1 is not a standing finding against
the code**: the round-2 instrument did its job and proved the cause lies outside this
diff, which is now backlog item 143 — and I extended that item by showing with a live
`SendMessage` that the matcher is dead on that route too, not only on `Agent`. But it
leaves criteria 1, 9 and 10 unmeetable here, and **that is an assignment-level decision
for the orchestrator**: strike them and hand them to the item-143 unit, or hold this unit
until the hooks are invoked at all. G2 asks only that a refuted cause stop being asserted
in a comment above a check the file calls load bearing; G3 and G4 are small.
