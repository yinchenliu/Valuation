# `.claude/` — the agent contract

This directory runs the [AGENTS.md](../AGENTS.md) contract in Claude Code. It is a port
of the CLO_AUP build's setup, adapted to this repository.

```
.claude/
├── settings.json          the output style and the three hooks
├── agents/
│   ├── programmer.md      writes everything except tests/
│   ├── code-reviewer.md   writes its review entry only
│   └── tester.md          writes tests/ and its entry only
├── hooks/
│   ├── run_hook.sh        starts each hook with the venv interpreter, on Windows or macOS
│   ├── guard_paths.py     PreToolUse  — the per-agent write scope
│   ├── seal_baseline.py   PreToolUse on Agent/Task/SendMessage — snapshots the sealed files
│   └── seal_check.py      SubagentStop — the seal
├── output-styles/
│   └── ste100.md          byte-identical copy of the CLO_AUP original
├── skills/
│   └── main-agent/        the orchestrator's role
├── check_guard.py         60 cases the write guard must get right
└── README.md              this file
```

Verify the guard after any edit to `hooks/guard_paths.py`:

```
.venv/Scripts/python.exe .claude/check_guard.py    # Windows
.venv/bin/python .claude/check_guard.py            # macOS
```

→ `48/48 guard cases correct`, measured 2026-09-20 on Windows and 2026-10-02 on macOS.
The four scratch-path cases use `c:/tmp` on Windows and `/tmp` elsewhere: `c:/tmp` is a
relative path on macOS, so it gave 44/48 there.

It is not a pytest file and is not named like one. `STATUS.md` records the suite count
as a measurement, so nothing here may join it.

## What changed from the CLO_AUP port, and why

| CLO_AUP | Here | Why |
|---|---|---|
| tester ties to `benchmark/` | tester derives expected values by hand | **there is no benchmark in this repository.** Decided 2026-09-20 |
| `benchmark_seal.py` | `seal_check.py` | nothing to seal a benchmark against. It seals `STATUS.md`, the journal index, and `hooks/` |
| seals `benchmark/` against HEAD | seals `hooks/` against the dispatch snapshot | `.claude/` is new and uncommitted; a HEAD comparison would fire on every run |
| `permissions.deny` on `benchmark/**` | dropped | no such directory |
| programmer denied `tests/` and `benchmark/` | denied `tests/` only | same reason |
| `.venv/bin/python3` | `run_hook.sh` picks `.venv/bin/python` or `.venv/Scripts/python.exe` | **this repository runs on Windows and macOS.** See the last section |
| `/private/tmp/claude-501/…` scratch | `c:/tmp/` on Windows, `/tmp/` on macOS | same |
| the six CLO rules | six rules rewritten for this codebase | `docs/2-rules/rules.md`. Each one names the defect here that forced it |

The three agent prompts keep the CLO_AUP structure — startup order, the five rejections,
the four outcomes, the journal discipline, the harness notes — with the content rewritten
for DCF valuation.

## The write scope

`permission.edit` does not exist per-agent in Claude Code, so the separation lives in a
hook. `guard_paths.py` reads `agent_type` on every `PreToolUse` and answers `deny` for a
write outside that agent's scope. It is inert for the orchestrator and for every built-in
agent.

| Role | May write |
|---|---|
| `programmer` | everything except `tests/` |
| `code-reviewer` | `.agent/journal/` and nothing else |
| `tester` | `tests/` and `.agent/journal/` |

Four paths are denied to **every** role: `.agent/journal/INDEX.md`, `STATUS.md`,
`AGENTS.md`, and `.claude/` itself. The first three belong to the orchestrator. The last
one means a subagent cannot edit the permissions that bind it.

It checks `Write`, `Edit` and `NotebookEdit` exactly, by path. It checks `Bash` by
parsing the mutating forms — redirects, `sed -i`, `tee`, `cp`, `mv`, `rm`, `patch`,
`git restore`. **That half is a tripwire, not a sandbox.** A shell can still write a file
it cannot see; `python -c` is the obvious one.

Paths outside the repository are not guarded. Assignments call for scratch runs, and
those write outside the tree on purpose.

## The seal

`seal_check.py` closes that gap for the three things that matter most. It runs when a
subagent finishes and blocks the stop if any of them moved.

**It compares against a dispatch snapshot, not against HEAD.** HEAD is the wrong
baseline: AGENTS.md has the orchestrator write `STATUS.md` and the journal index *after a
subagent returns*, so the next subagent inherits those uncommitted lines. Sealed against
HEAD, they read as the subagent's own write, and the only way to clear the accusation is
`git checkout --`, which deletes the orchestrator's record — the seal destroying what it
exists to protect.

`seal_baseline.py` writes that snapshot into the gitignored
`.agent/.seal-baseline.json`. It runs on `PreToolUse` for `Agent`, `Task` and
`SendMessage` — every way a subagent starts or restarts. It refuses to run for a role, so
a subagent cannot reset the measurement taken of it.

A hash, not a copy: a subagent that changes a file and changes it back has changed
nothing, and that is the right answer.

A missing snapshot falls back to the HEAD comparison for the two tracked files, and skips
`hooks/`. Blunter, never a hole.

## The hooks start through `run_hook.sh`

`settings.json` runs every hook as `sh "${CLAUDE_PROJECT_DIR}/.claude/hooks/run_hook.sh"
<hook>.py`. The launcher runs the hook with `.venv/bin/python` if it exists, else with
`.venv/Scripts/python.exe`. It never uses a shebang or a bare `python`: Windows does not
honour `#!/usr/bin/env python3`, and a bare `python` resolves to whatever is first on
`PATH`. Claude Code runs hooks in Git Bash on Windows, so `sh` exists on both machines.

**Until 2026-10-02 `settings.json` named `.venv/Scripts/python.exe` directly.** On macOS
that file does not exist. The hook could not start, Claude Code treats that as a
non-blocking error, and every tool call went through. The guard and the seal were both
off on that machine, and nothing said so. `.agent/.seal-baseline.json` had never been
written there, which is how it was found.

**So a missing interpreter now fails closed where it matters.** If neither interpreter
exists and a subagent role is running, `run_hook.sh guard_paths.py` exits 2. Claude Code
then blocks the tool call and shows the agent the reason. The orchestrator is only
warned (exit 1), because it is unguarded by design and must stay able to create the
venv. The two seal hooks only warn: a blocked SubagentStop would wedge the subagent, and
the guard has already refused every write it could have made.

**The seal covers the launcher.** Both seal hooks hash every `.py` and `.sh` file in
`hooks/`. A subagent that disarmed `run_hook.sh` would disarm every hook at once.

**Claude Code reads hook settings when a session starts.** After you edit
`settings.json`, start a new session, or review the change in `/hooks`, before you rely
on it.
