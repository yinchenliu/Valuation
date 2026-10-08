---
agent: tester
assignment: P1f-worktree-guards-tests
round: 1
status: complete
files_touched: [tests/unit/_hook_harness.py, tests/unit/test_guard_paths_worktree.py, tests/unit/test_seal_hooks.py, tests/unit/test_seal_baseline_rule3_red.py]
verdict: fail
---

# P1f-worktree-guards-tests — the guard reaches into a worktree, the seal counts, and one load-bearing check does not fire

> Opened before the first command, filled as each result landed.

## The verdict in one paragraph

**All seventeen done-criteria pass.** 191 new tests, three seeds, 1573 passed / 2
skipped / 0 failed on the gate, 60/60 on the write guard, lint at 4 `BLE001`, and all
five commissioned mutants killed. **The verdict is `fail` for exactly one reason, and it
is a measurement, not a reading**: `seal_baseline.py:210-212` is the check the file's own
docstring calls "load bearing, not defensive tidiness", and it fires only when
`tool_name == "SendMessage"`. With `tool_name` **absent**, or `Agent`, or `Task`, a
payload carrying a subagent's role goes straight through, and I measured the consequence:
the snapshot is **retaken over the subagent's own write to `STATUS.md`**, which the
`SubagentStop` seal then clears. That is a stop path that defaults instead of stopping,
and `.claude/agents/tester.md` says such a thing is a `fail`, not an untestable case. The
round 2 reviewer named the same narrowing as **G2** and rated it `minor`; the round 3
answer fixed the comment and left the scope. **The orchestrator may well accept the unit
over it — two reviewers already have — but it is not mine to grade as `pass`.** The
requirement is now recorded in `tests/unit/test_seal_baseline_rule3_red.py`, which the
gate excludes.

Item 142, the half that is actually enforced today, is in good shape and nothing below
qualifies it.

## What I did

Three test files plus a harness, all under `tests/`. `_hook_harness.py` drives a hook two
ways — as a subprocess, the way the harness runs it, and by importing the module and
calling `main()` on a fake stdin, which is the driver a coverage report can see — and
builds a **scratch git repository with a real `git worktree add`** under pytest's tmp
space. No test adds a worktree to, or commits in, the repository under test.
`VALUATION_HOOKS_DIR` points both drivers at a copy of the hooks, which is how the five
mutation runs were made without editing a file in scope.

## The three traps, and that I refused each

1. **I did not write a test that depends on the harness delivering a payload, and I did
   not write a test that asserts the hooks never run.** Backlog item 143 appears in my
   test files only as a comment saying why it is not asserted in either direction. Every
   payload is constructed in the test. Nothing I wrote reads
   `.agent/.seal-baseline.json` in this repository, and nothing I wrote is sensitive to
   whether the harness ever starts these hooks. A test asserting "the hook never runs"
   would lock item 143 in as correct behaviour and turn red the day it is fixed. The
   `P14g` and `P1e` testers each refused that for their own units; so did I.
2. **Nothing skips.** `_hook_harness.require_git` raises `AssertionError` with the reason
   written out. `test_git_is_present_so_no_worktree_case_can_skip` is a test whose only
   job is to go red if git leaves this machine. The harness also asserts git's own layout
   fact — that a linked worktree's `.git` is a **file** — right after `worktree add`, so
   a worktree that was not really one cannot make 30 deny cases pass for the wrong
   reason. That is `check_guard.py`'s `PATH: ""` defect, stated as a test.
3. **I did not assert a fallback anywhere.** Two places where I was one keystroke from
   it, and what I wrote instead:
   - A corrupt baseline makes both hooks exit 0. Asserting only that would lock in a
     silence. Each of the six corrupt shapes therefore asserts exit 0 **together with**
     the count returning to 0 and the **next stop still firing on a real change**. The
     docstring for the test says so explicitly.
   - A payload whose `agent_type` is not one of the three roles is unguarded, in both the
     guard and the seal. I deliberately wrote **no** test for that: it is a scope
     boundary, and a test on it would go red the day someone tightens it. Named here
     instead.

## Done-criteria

Every command run with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | every expected value hand-sourced | **pass** | 133 written assertions in the two normal files, 0 of them taken from the code's output. The provenance table below gives the source of each group |
| 2 | worktree decisions locked for all three roles, as a subprocess | **pass** | `test_the_role_matrix_holds_inside_a_worktree` (12 cases, subprocess), `test_the_sealed_paths_are_denied_*` (18 in-process + 6 subprocess), `test_the_bash_tripwire_reaches_into_a_worktree` (7 subprocess + 7 in-process) |
| 3 | the deny message is **identical**, not merely "denied" | **pass** | `test_the_worktree_deny_message_is_identical_to_the_in_project_one`, `test_the_always_denied_message_is_identical_in_a_worktree`. Asserted as an identity against the in-project message, plus "names `analysis/dcf.py`", "names `tester`", "does not contain the worktree directory name", "contains no `..`" |
| 4 | the guard works with `PATH=""` | **pass** | `test_the_guard_denies_in_a_worktree_with_no_git_on_path[""]` and `[C:/nonexistent_directory]` — deny, **and the reason byte-identical to the run with a real `PATH`**; `test_scratch_is_still_allowed_with_no_git_on_path` holds the other direction |
| 5 | **scratch stays writable** | **pass** | seven shapes × three roles in-process + seven as a subprocess. The shapes I took, named: `plain` (no `.git` above it), `own_clone` (its own clone, `.git` a directory), `foreign` (`.git` file naming another repository's `worktrees/`), `junk` (`.git` file of junk and NUL/0xFF bytes), `empty` (`.git` file of no bytes), `submodule` (`.git` file naming `<project>/.git` itself), `wt_extra` (a sibling named `<wt>` plus a suffix — the prefix-match trap). Plus three scratch Bash forms, and the error-direction control `test_a_pruned_worktree_of_this_project_is_still_denied` |
| 6 | `worktree_root_of` covered directly, five cases | **pass** | from the root; from a file deep inside; the project itself; a scratch path; a `gitdir` pointing elsewhere (two sub-cases: another repository, and `<project>/.git` itself) |
| 7 | the seal's counting | **pass** | 0→1 `test_the_first_dispatch_of_a_window_takes_the_snapshot`; increment `test_a_second_dispatch_increments_and_does_not_retake_the_snapshot`; decrement `test_each_stop_decrements_by_one`; floor `test_the_count_cannot_go_below_zero`; a stop still fires `test_a_stop_fires_when_a_sealed_file_changed_and_still_decrements` and the two-agent `test_the_first_of_two_agents_is_no_longer_cleared_by_the_second_dispatch` |
| 8 | six corrupt shapes | **pass** | `test_a_corrupt_baseline_stops_neither_hook_and_heals`, 6 cases: `"abc"`, `true`, `null`, non-JSON, a JSON list, an empty file. Each asserts stop exit 0, dispatch exit 0, digests present, `in_flight` back to 0, **and the next stop firing**. Three re-taken as subprocesses |
| 9 | `window_lost_at`, with digests present | **pass** | `test_an_unreadable_baseline_is_replaced_by_a_snapshot_that_still_has_digests`. Killed by mutant **m5** |
| 10 | `as_count` rejects `bool` | **pass** | 12 direct cases, plus `test_as_count_rejects_bool_where_int_would_have_accepted_it` end to end: a baseline holding `true` must give `in_flight: 1` (a fresh window), not `2` (`int(True) + 1`) |
| 11 | five mutations, each killed | **pass** | table below, all five killed, with names |
| 12 | coverage of what the unit added | **pass, measured** | 87 of 95 executable added statements; table below |
| 13 | the gate | **pass** | **1573 passed, 2 skipped, 0 failed** at seeds **7**, **1234** and **99**. 1573 = 1382 + my 191 |
| 14 | the failing set (gate form) | **pass** | empty |
| 15 | lint | **pass** | 4 errors, every one `BLE001`, none in a file I wrote. **Run after my last write, and it caught me** — see "Criterion 15 caught me too" below |
| 16 | the write guard | **pass** | `60/60 guard cases correct`, exit 0 |
| 17 | no test skips silently | **pass** | `require_git` raises; `test_git_is_present_so_no_worktree_case_can_skip`; `add_worktree` asserts the `.git` file exists. 0 skips in my files (the suite's 2 skips are pre-existing and elsewhere) |

The assignment's "verify, do not redo" table reproduced exactly: gate **1382** before my
files (1573 − 191), full suite **2 failed by name** before my red file, lint **4 `BLE001`**,
types **2 errors in 2 files, 21 checked**, census **64**, write guard **60/60**. Nothing
disagreed.

## Expected values — where each came from

**Never "what the code returned".** Not one assertion in the two normal files took its
expected side from a run.

| Assertion group | Count | Where the expected value came from |
|---|---|---|
| the role matrix in a worktree, in the project, and at `verdict()` | 12 + 12 + 10 | **The contract**, written down before this unit existed: `AGENTS.md` and `.claude/agents/{programmer,tester,code-reviewer}.md`. A tester writes `tests/**` and `.agent/journal/**` and nothing else; a programmer writes everything except `tests/`; a reviewer writes only its journal |
| `ALWAYS_DENIED`, six targets × three roles | 18 + 6 | The same contract: `AGENTS.md` names `INDEX.md`, `STATUS.md` and itself; `.claude/**` and `.agent/.seal-baseline.json` are named in the guard's own list with their reasons |
| the deny message in a worktree | 2 tests | **A closed-form identity**: `message(<worktree>/analysis/dcf.py) == message(<project>/analysis/dcf.py)`. It holds whatever the wording is, so it cannot be satisfied by photographing either side. The supporting substring checks come from the repo-relative path computed by hand: `<wt>/analysis/dcf.py` relative to `<wt>` is `analysis/dcf.py` |
| the seven scratch shapes, `worktree_root_of`, `resolve_repo_relative` | 21 + 7 + 7 + 8 | **A fact about git's on-disk layout**, `gitrepository-layout(5)`, older than this repository: a linked worktree's `.git` is a FILE holding `gitdir: <main>/.git/worktrees/<name>`; an ordinary checkout's is a directory. Each shape is constructed to violate one clause of that and must therefore not be a worktree of this project |
| `PATH=""` and `PATH=C:/nonexistent` | 3 | **An identity again**: the decision and the reason must not move when `PATH` is emptied, because the function reads a file and runs no subprocess |
| `bash_targets` | 10 | **The shell's own semantics**, read off each command: `>`/`>>` write their operand, `tee` and `rm` write every positional, `cp`/`mv` write the last one, `sed -i` writes what follows the script, `git restore` writes its paths, `grep` and `git diff` write nothing |
| the three sealed digests | ~40 | **sha256 of bytes the test itself wrote**, computed in the test with `hashlib`. For the hooks directory, the formula from the hooks' own docstring written out independently — `sha256(name_bytes + file_bytes)` over the sorted set — so a `tree_digest` that stopped hashing the name fails it (`test_tree_digest_changes_when_a_file_is_renamed` proves that discrimination) |
| every count | ~25 | **Hand arithmetic on a counter**: 0→1, 1+1=2, 2−1=1, 1−1=0, `max(0, 0−1)=0`, and `2+1=3`. Each is written into the test as a comment |
| the 12-hour window | 3 | **The documented constant** `STALE_AFTER_HOURS = 12`: 11 hours inside, 13 outside, and the boundary test reads the constant rather than repeating the number |
| `as_count` on `True` | 13 | **Python's own rule that `bool` is a subclass of `int`**, which is why `int(True)` is 1 and why a count read that way would see one agent in flight where there is none |
| `is_stale` on a naive timestamp | 4 | **A timestamp with no zone cannot be compared to `now(UTC)`**, so "unknown" is the only honest answer |

**Two counts, with their units.**

- **Accuracy: 133 of 133 written assertions match** (48 in `test_guard_paths_worktree.py`,
  85 in `test_seal_hooks.py`), executed across **191 of 191 passing parametrised test
  cases**. **0 of 133 took their expected value from the code's output.** The 4 assertions
  in `test_seal_baseline_rule3_red.py` deliberately do not match; that is the finding.
- **Coverage, in functions:** the unit added **6** functions —
  `guard_paths._normalised`, `guard_paths.worktree_root_of`,
  `guard_paths.resolve_repo_relative`, `seal_baseline.read_state`,
  `seal_baseline.read_or_unreadable`, `seal_baseline.as_count`. **5 of 6 are touched by a
  test.** The sixth, `read_state`, is touched by nothing **because nothing in the
  repository calls it** — see Findings. It also changed `main` in all three hooks,
  `seal_baseline.is_stale` and `seal_check.main`'s decrement; all are touched.
- **Coverage, in statements and branches**, `--cov-branch` over `.claude/hooks`
  intersected with `git diff -U0`:

| File | added lines | of those, executable | covered | not covered |
|---|---|---|---|---|
| `guard_paths.py` | 86 | 36 | **32** | 4 — lines 155, 156, 163, 164 |
| `seal_baseline.py` | 185 | 47 | **45** | 2 — lines 115, 116 |
| `seal_check.py` | 21 | 12 | **10** | 2 — lines 127, 128 |
| **total** | 292 | **95** | **87** | **8** |

  File-level branch coverage from the same run: `guard_paths.py` 70/80 arcs,
  `seal_baseline.py` 17/18, `seal_check.py` 21/24, statements 283/322 overall.

  **The eight uncovered added statements, named.** `guard_paths.py:155-156` and `163-164`
  are the two `except (OSError, ValueError)` handlers inside `worktree_root_of`; reaching
  them needs a path that `is_file()` reports True for and that then fails to read, which I
  could not construct on Windows without a permissions trick, and a test that mocked
  `Path.read_text` would be testing the mock. `seal_check.py:127-128` is `except OSError:
  pass` on the baseline write-back; the file has to parse as a dict to reach it, so the
  directory-in-place trick that covers the same handler in `seal_baseline` cannot be used.
  `seal_baseline.py:115-116` is `read_state`, which has no caller — I deliberately left it
  uncovered rather than entrench dead code with a test.

  **These numbers understate what is exercised.** Coverage sees the in-process driver
  only, so every line reached solely through a subprocess — `main`'s tool dispatch, and
  the whole Bash path when driven that way — counts as missed even though 44 subprocess
  runs execute it. `test_the_two_drivers_agree_on_every_shape` is what entitles the fast
  driver to stand for the slow one: it takes five representative decisions both ways and
  asserts they are equal.

  **`.claude/check_guard.py` is not in the table.** 46 of its added lines are the twelve
  worktree cases and the `temporary_worktree` fixture. It is `ALWAYS_DENIED` to me and is
  not a pytest module, so it cannot be covered from `tests/`; it is measured by criterion
  16 instead, at 60/60.

## Criterion 11 — the five mutations, and what each killed

Each mutant is a **copy** of the three hooks under `C:\tmp\p1f_tests_mut\<name>\`, built
by `C:\tmp\p1f_tests_mut\mutate.py`, which refuses to patch unless its anchor is unique.
Nothing in the repository was edited. The suite is pointed at a mutant with
`VALUATION_HOOKS_DIR`. All runs at `--randomly-seed=7`.

| # | Mutation | Command | Failed | The names that went red |
|---|---|---|---|---|
| m1 | `main` calls `repo_relative` instead of `resolve_repo_relative` — **item 142 returning** | `VALUATION_HOOKS_DIR=…/m1_repo_relative pytest tests/unit/test_guard_paths_worktree.py tests/unit/test_seal_hooks.py` | **46 failed, 145 passed** | `test_the_sealed_paths_are_denied_to_every_role_in_a_worktree` ×18, `…_through_a_real_subprocess_too` ×6, `test_the_role_matrix_holds_inside_a_worktree` ×6, `test_the_bash_tripwire_reaches_into_a_worktree` ×5 and `…_in_process_too` ×5, `test_the_guard_denies_in_a_worktree_with_no_git_on_path` ×2, `test_the_worktree_deny_message_is_identical_to_the_in_project_one`, `test_the_always_denied_message_is_identical_in_a_worktree`, `test_a_relative_path_is_resolved_against_the_worktree_cwd`, `test_a_pruned_worktree_of_this_project_is_still_denied` |
| m2 | `worktree_root_of` returns the probe's parent for any outside path — **scratch denied** | same files, `…/m2_parent_as_worktree` | **58 failed, 133 passed** | `test_scratch_space_stays_writable_whatever_it_looks_like` ×14, `…_through_a_real_subprocess_too` ×7, `test_scratch_is_still_allowed_with_no_git_on_path`, `test_a_scratch_bash_command_is_still_allowed`, all five `test_worktree_root_of_*`, all four `test_resolve_repo_relative_*`, plus 12 + 4 sealed-path cases and 4 role-matrix cases flipping the other way |
| m3 | `seal_check.py` no longer decrements — the `finally`-equivalent removed | `…/m3_no_decrement pytest tests/unit/test_seal_hooks.py` | **10 failed, 47 passed** | `test_each_stop_decrements_by_one`, `test_a_stop_fires_when_a_sealed_file_changed_and_still_decrements`, `test_the_first_of_two_agents_is_no_longer_cleared_by_the_second_dispatch`, `test_a_stop_clears_a_run_that_changed_nothing`, `test_a_corrupt_baseline_stops_neither_hook_and_heals` ×6 |
| m4 | `as_count` replaced by `int(value or 0)` — **the round 1 crash** | `…/m4_int_as_count pytest tests/unit/test_seal_hooks.py` | **9 failed, 48 passed** | `test_as_count_returns_a_count_or_zero` ×6 (`True`, `"abc"`, `"3"`, `2.0`, a list, a dict), `test_as_count_rejects_bool_where_int_would_have_accepted_it`, `test_a_corrupt_baseline_stops_neither_hook_and_heals["abc"]`, `…_as_a_subprocess_either["abc"]` — the last one is the reviewer's exit-1 crash, caught as a subprocess |
| m5 | `window_lost_at` deleted and the **no-digest state** restored | `…/m5_no_digest_state pytest tests/unit/test_seal_hooks.py` | **4 failed, 53 passed** | `test_an_unreadable_baseline_is_replaced_by_a_snapshot_that_still_has_digests`, `test_a_corrupt_baseline_stops_neither_hook_and_heals` ×3 (non-JSON, a JSON list, an empty file) |

**No mutation survived.** m5 is the one the assignment asked for by name: the first fix
for G4 wrote a state with no digests, `seal_check.py` skips a comparison whose key is
absent, and all three comparisons were then skipped in silence. The assertion that
separates the two is the last one in that test — a changed `STATUS.md` must still exit 2.

## Rule 3 — what stops, and what does not

These are hooks, so no value here reaches a displayed figure and none may raise: a hook
that crashes is a guard that is off. The question still applies to each value read, and
the right form of "stop" for a tripwire is "refuses, and names what it refused".

| Value read | If it were missing | Evidence |
|---|---|---|
| a write target inside a worktree | **refuses and names the repo-relative path and the role** | `test_a_deny_reason_always_names_the_path_and_the_rule`, and the two message-identity tests |
| an `ALWAYS_DENIED` target | **refuses, names the path, and says "every subagent"** | `test_the_sealed_paths_are_denied_to_every_role_in_a_worktree`, 18 cases |
| a target under no worktree | returns `None`, allowed — **not a rule 3 default**: no figure is substituted, and this is the scratch discipline every unit depends on | `test_resolve_repo_relative_returns_none_for_scratch`, and 28 shape cases |
| an unexpanded `$VAR` in a path | declines to guess, documented threat model | `test_resolve_repo_relative_declines_to_guess_at_an_unexpanded_variable` |
| a changed sealed file | **fires, exit 2, and the message names the file** | the three sealed things each fire on their own; deletion fires; a change-and-undo does not |
| `in_flight`, any non-int | `as_count` → 0, a fresh window, self-healing | locked **with** the compensating assertions: count back to 0 and the next stop fires |
| `taken_at`, missing or unparseable | treated as stale, snapshot rewritten | `test_is_stale_is_true_for_anything_it_cannot_read`, 4 cases |
| the baseline, absent | falls back to HEAD — and **still fires** | `test_with_no_snapshot_the_seal_falls_back_to_head_and_still_fires` |
| the baseline, unwritable | silent, dispatch exits 0 | `test_a_baseline_that_cannot_be_written_does_not_stop_the_dispatch` |
| **`tool_name`, absent** | **No. The load-bearing role check is skipped entirely, and a subagent can have the snapshot retaken over its own write.** | `seal_baseline.py:210-212`; `tests/unit/test_seal_baseline_rule3_red.py`, 4 cases red |

### The stop path I could not lock, with its `file:line`

`.claude/hooks/seal_baseline.py:210-212`

```python
if (data.get("tool_name") or "") == "SendMessage" \
        and (data.get("agent_type") or "").strip() in ROLES:
    sys.exit(0)
```

Measured on 2026-10-08 against scratch projects under `C:\tmp`
(`probe_g2.py`, `probe_g2b.py`), baseline `in_flight: 1`, same session, `taken_at` far in
the future so staleness cannot be the cause:

```
  tool_name=SendMessage, agent_type=tester   in_flight 1 -> 1   REFUSED
  tool_name ABSENT,      agent_type=tester   in_flight 1 -> 2   let through
  tool_name=Agent,       agent_type=tester   in_flight 1 -> 2   let through
  tool_name=Task,        agent_type=tester   in_flight 1 -> 2   let through
```

And the sharp half, baseline `in_flight: 0` — the state between units — with the subagent
having already written to `STATUS.md`:

```
  tool_name=SendMessage, agent_type=tester   snapshot holds the tampered file: False
  tool_name ABSENT,      agent_type=tester   snapshot holds the tampered file: True
```

So with `tool_name` absent the snapshot is retaken over the subagent's own write, and
`seal_check.py` clears it at `SubagentStop`. **This is not a new finding** — the round 2
reviewer's **G2** stated the same cost in words, rated it `minor`, did not ask for a
revert, and asked for the scoping to be "either justified on its own terms or widened back
to 'any payload carrying a role'". Round 3 rewrote the comment and left the scope. I have
measured what the words predicted.

**What would fix it**, one line: widen to `(data.get("agent_type") or "").strip() in
ROLES`, or keep the tool scope and treat an absent `tool_name` as not exempt.

**Why I did not fix it or weaken the test.** `.claude/hooks/` is out of my scope and
`ALWAYS_DENIED` to me by permission. I did not write a test asserting the current narrow
behaviour, because that would make the narrowing permanent and turn the fix red — the
single most damaging thing a tester can write here.

## Measurements

```
gate   .venv/Scripts/python.exe -m pytest -q --randomly-seed=<n> --ignore-glob="*_rule3_red.py"
         seed 7     1573 passed, 2 skipped, 0 failed   194.7 s
         seed 1234  1573 passed, 2 skipped, 0 failed   196.5 s
         seed 99    1573 passed, 2 skipped, 0 failed   190.1 s
         1573 = 1382 (the unit's figure, reproduced) + 191 new
full   -m pytest -q      6 failed, 1573 passed, 2 skipped
         the failing SET, by name:
           tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input
           tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops
           tests/unit/test_seal_baseline_rule3_red.py::test_a_subagent_cannot_extend_the_window_by_any_route[None|Agent|Task]
           tests/unit/test_seal_baseline_rule3_red.py::test_a_subagent_cannot_have_the_snapshot_retaken_over_its_own_write
         the first two are the two that were red on purpose and I left both untouched.
         the last four are mine, and they are the finding. The gate excludes the pattern.
guard  .venv/Scripts/python.exe .claude/check_guard.py   60/60, exit 0
lint   -m ruff check .                                   4 errors, every one BLE001
types  -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports
                                                         2 errors in 2 files, 21 checked
census the grep at docs/2-rules/rules.md:102             64
```

**Nothing in the repository was mutated.** sha256 of the four files in scope, before my
first command and after my last:

```
81316b949aac92c8…261c8629  .claude/check_guard.py          identical after
213cbee6a3c0b68d…f6baeb94  .claude/hooks/guard_paths.py    identical after
d946ca2ce4a93c0e…048e7fa8  .claude/hooks/seal_baseline.py  identical after
e2bd742ca659ed3e…bc03fa3a  .claude/hooks/seal_check.py     identical after
```

`git worktree list` reads one entry, the repository itself. Every worktree I built was a
worktree of a **scratch** repository under pytest's tmp space, so the repository's
`.git/worktrees/` was never written. No `git stash`.

**`HEAD` moved during my run**, from `e9504ac` to `c985edb` (`a92194b` "Item 143 is
decided", `c985edb` "The pilot is two teams, not three"). Both touch only
`.agent/QUEUE.md` and `docs/9-reference/refactor-backlog.md`, so the diff under test is
unchanged.

## Decisions, each with its reason

| Decision | Reason | Why this and not the alternative |
|---|---|---|
| build a **scratch git repository** and add the worktree to that, not to this one | the assignment forbids mutating a repository file, and `git worktree add` writes `.git/worktrees/<name>` in the main checkout | `check_guard.py` adds a worktree to the real repository, which is right for a one-shot check and wrong for a suite that runs on every gate. It also removes the Windows lock problem from teardown entirely: nothing has to be `worktree remove`d |
| two drivers, subprocess and in-process | a subprocess costs ~0.85 s here; the full matrix as subprocesses took 64 s | the matrices run in-process and a representative sample of each is re-taken as a subprocess, with `test_the_two_drivers_agree_on_every_shape` holding the two together. Final cost 56 s for 191 tests. In-process is also the only driver a coverage report can see |
| `VALUATION_HOOKS_DIR` to redirect both drivers | the five mutants must run against a copy | the alternative is editing a file in scope and restoring it, which is the thing the assignment forbids and which `git stash` would make worse |
| assert the deny message as an **identity** rather than quoting it | a quoted string is a photograph of the current wording, and would go red on a harmless rewording while passing a message that named the wrong path | the identity is the actual requirement of item 142, and the four substring checks pin what a reader needs: the repo-relative path, the role, no absolute worktree path, no `..` |
| **no** test for "a non-role `agent_type` is unguarded" | it is a scope boundary, and a test on it would go red the day someone tightens it | `check_guard.py` already carries that case for the guard; duplicating it in a suite that must never obstruct a fix is the wrong place for it |
| **no** test for `read_state` | it is dead code; a test would entrench it | reported as a finding instead |
| a new `*_rule3_red.py` file rather than a silent note | `.claude/agents/tester.md` gives exactly this mechanism for "a requirement the code does not yet meet", and the gate excludes the pattern | a finding in prose is forgotten; a red test is not. It costs the full suite four reds, which this entry states plainly so `STATUS.md` can be updated in one edit |

## What I did not do

- **I did not test backlog item 143 in either direction**, as the assignment requires.
- **I did not extend `.claude/check_guard.py`'s case table.** It is `ALWAYS_DENIED` to me.
  Everything it would have gained is covered from `tests/` instead.
- **I did not touch the two tests that are red on purpose.** Both are still red, by name.
- **I did not cover four `except` handlers and one dead function** — named above with
  their line numbers and the reason each is out of reach.
- **I did not fix `seal_baseline.py:210-212`.** Out of scope, and enforced by permission.

## Findings for the orchestrator

1. **`seal_baseline.py:210-212` — the load-bearing role check fires only for
   `SendMessage`.** Measured above, both halves. The file's docstring claims the check
   "stops a subagent refreshing the measurement taken of it"; with `tool_name` absent, or
   `Agent`, or `Task`, it does not. One-line fix named above. This is the whole of my
   `fail`, and it is the round 2 reviewer's **G2** with a measurement attached rather than
   a new discovery. `tests/unit/test_seal_baseline_rule3_red.py` records it; **delete that
   file if you accept the narrowing, or fix the line and move the file's tests into
   `tests/unit/test_seal_hooks.py` in the same unit** — a green test left inside the red
   pattern is the defect at `38b903c` (backlog item 24).
2. **`seal_baseline.read_state` has no caller.** `grep -rn read_state .claude/` returns
   its own `def` and nothing else: the G4 fix moved every call to `read_or_unreadable` and
   left the wrapper, with a docstring that describes a distinction nothing uses. Ruff's
   default rule set does not flag an unused module-level function, so no gate will say so.
   Six lines to delete; worth a backlog line rather than an assignment.
3. **A second reason the `.claude/hooks` coverage figure will always look low.** Coverage
   cannot see a subprocess, and the Bash half of `guard_paths.main` is exercised that way
   by `check_guard.py` and by seven of my tests. If anyone later reports "the hooks are at
   88%", that number is the in-process half only. Stated here so it is not read as a gap.
4. **Backlog item 143 is untouched and unasserted by these tests.** When it is fixed, none
   of my 191 tests should move. If any of them does, the fix changed the hooks' behaviour
   and not only their wiring — which is itself worth knowing.

## Criterion 15 caught me too, and that is the point of it

I ran `ruff check .` **after** my last code write, as the criterion demands in bold, and
it reported **11 errors, not 4**. Seven were mine: six `RUF100` (`# noqa: ANN201`
directives for a rule this repository does not enable — I had copied the shape from a
file that does) and one `I001` (an unsorted import block in `test_seal_hooks.py`). I fixed
all seven by hand, re-ran the two test files (**191 passed**), re-ran the gate at all
three seeds (**1573 passed, 2 skipped, 0 failed** at 7, 1234 and 99), re-ran the full
suite (6 failed, the same six by name), re-ran `check_guard.py` (**60/60**) and re-ran all
five mutants at seed 7 — **46, 58, 10, 9 and 4 failures, unchanged, all five still
killed** — and only then ran lint again.

```
.venv/Scripts/python.exe -m ruff check . --output-format=concise
  api\routes_valuation.py:463:16  BLE001
  api\routes_valuation.py:745:12  BLE001
  cli.py:1411:12                  BLE001
  tests\test_e2e_all_googl.py:106 BLE001
  Found 4 errors.
```

The `P3c`, `P1f` round 2 and `P3d` entries all record the same defect from the other
side. Running it last is what turned my seven into a paragraph instead of a review
finding.

---

`ruff check .` was run **after** the last write to code in this unit. The only write after
it is this entry, which ruff does not read.
