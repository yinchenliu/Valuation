#!/usr/bin/env python3
"""Cases the PreToolUse write guard must get right.

Not a pytest file, and not named like one. The repository's suite count is a
measurement recorded in STATUS.md, so nothing here may join it.

Run it after any edit to .claude/hooks/guard_paths.py:

    .venv/bin/python .claude/check_guard.py           # macOS, Linux
    .venv/Scripts/python.exe .claude/check_guard.py   # Windows

Exit 0 = every case correct. Exit 1 = the failures, printed.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / ".claude" / "hooks" / "guard_paths.py"

# Scratch space outside the repository. It must be an absolute path on the
# machine running the check: `c:/tmp` is relative on macOS, so it resolves
# inside the repository there, and four allow cases went red for that reason
# alone. Measured 2026-10-02: 44/48 on macOS with `c:/tmp` everywhere.
SCRATCH = "c:/tmp" if os.name == "nt" else "/tmp"

# (role, tool, tool_input, expected, label)
CASES: list[tuple[str, str, dict, str, str]] = [
    # --- programmer: everything but tests/ ---
    ("programmer", "Write", {"file_path": "analysis/dcf.py"}, "allow", "programmer writes analysis"),
    ("programmer", "Edit", {"file_path": "models/valuation.py"}, "allow", "programmer writes models"),
    ("programmer", "Edit", {"file_path": "ingestion/claude_extractor.py"}, "allow", "programmer writes ingestion"),
    ("programmer", "Write", {"file_path": "api/routes_valuation.py"}, "allow", "programmer writes api"),
    ("programmer", "Write", {"file_path": "templates/upload.html"}, "allow", "programmer writes templates"),
    ("programmer", "Write", {"file_path": "tests/test_x.py"}, "deny", "programmer may not write tests"),
    ("programmer", "Write", {"file_path": ".agent/journal/e.md"}, "allow", "programmer writes its entry"),
    ("programmer", "Edit", {"file_path": ".agent/journal/INDEX.md"}, "deny", "INDEX.md is the orchestrator's"),
    ("programmer", "Edit", {"file_path": "STATUS.md"}, "deny", "STATUS.md is the orchestrator's"),
    ("programmer", "Edit", {"file_path": "AGENTS.md"}, "deny", "AGENTS.md is the contract"),
    ("programmer", "Edit", {"file_path": ".claude/hooks/guard_paths.py"}, "deny", "nobody disarms the guard"),
    ("programmer", "Edit", {"file_path": ".claude/agents/programmer.md"}, "deny", "nobody rewrites its own role"),
    # --- code reviewer: its entry and nothing else ---
    ("code-reviewer", "Write", {"file_path": ".agent/journal/r.md"}, "allow", "reviewer writes its entry"),
    ("code-reviewer", "Edit", {"file_path": "analysis/dcf.py"}, "deny", "reviewer may not edit code"),
    ("code-reviewer", "Write", {"file_path": "tests/t.py"}, "deny", "reviewer may not write tests"),
    ("code-reviewer", "Edit", {"file_path": "docs/INDEX.md"}, "deny", "reviewer may not edit docs"),
    ("code-reviewer", "Edit", {"file_path": "config.py"}, "deny", "reviewer may not edit config"),
    # --- tester: tests/ and its entry ---
    ("tester", "Write", {"file_path": "tests/test_dcf.py"}, "allow", "tester writes tests"),
    ("tester", "Write", {"file_path": "tests/conftest.py"}, "allow", "tester writes conftest"),
    ("tester", "Write", {"file_path": ".agent/journal/t.md"}, "allow", "tester writes its entry"),
    ("tester", "Edit", {"file_path": "analysis/wacc.py"}, "deny", "tester may not edit analysis"),
    ("tester", "Edit", {"file_path": "models/financial_statements.py"}, "deny", "tester may not edit models"),
    ("tester", "Edit", {"file_path": "config.py"}, "deny", "tester may not edit config"),
    ("tester", "Write", {"file_path": f"{SCRATCH}/scratch/x.py"}, "allow", "scratch space is not guarded"),
    # --- Bash, denied forms ---
    ("tester", "Bash", {"command": 'sed -i "" "s/a/b/" analysis/dcf.py'}, "deny", "sed -i on analysis"),
    ("tester", "Bash", {"command": "echo hi > analysis/x.py"}, "deny", "redirect into analysis"),
    ("tester", "Bash", {"command": "cat f >> models/valuation.py"}, "deny", "append into models"),
    ("tester", "Bash", {"command": "rm analysis/wacc.py"}, "deny", "rm in analysis"),
    ("programmer", "Bash", {"command": "echo x | tee tests/test_x.py"}, "deny", "tee into tests"),
    ("programmer", "Bash", {"command": f"cp {SCRATCH}/a STATUS.md"}, "deny", "cp over STATUS.md"),
    ("programmer", "Bash", {"command": "rm -rf .claude/hooks"}, "deny", "rm of the hooks"),
    ("code-reviewer", "Bash", {"command": "git restore analysis/dcf.py"}, "deny", "git restore of analysis"),
    # --- Bash, forms that must stay allowed ---
    ("tester", "Bash", {"command": f".venv/Scripts/python.exe -m pytest -q tests/ > {SCRATCH}/o.txt"}, "allow", "pytest redirected to scratch"),
    ("tester", "Bash", {"command": f'sed -i "" "s/a/b/" {SCRATCH}/s/x.py'}, "allow", "sed -i on a scratch file"),
    ("tester", "Bash", {"command": f'sed -i.bak "s/a/b/" {SCRATCH}/s/x.py'}, "allow", "sed -i.bak on a scratch file"),
    ("tester", "Bash", {"command": 'sed -i "" "s/a/b/" tests/test_x.py'}, "allow", "tester may sed its own tests"),
    ("tester", "Bash", {"command": 'grep -rn "kwargs" analysis/'}, "allow", "grep is not a write"),
    ("code-reviewer", "Bash", {"command": "git diff HEAD -- analysis/dcf.py"}, "allow", "git diff is not a write"),
    ("code-reviewer", "Bash", {"command": "md5sum STATUS.md"}, "allow", "reading STATUS.md is fine"),
    ("programmer", "Bash", {"command": ".venv/Scripts/python.exe -m ruff check ."}, "allow", "the lint gate"),
    ("programmer", "Bash", {"command": ".venv/Scripts/python.exe -m mypy models analysis"}, "allow", "the type gate"),
    # --- an unexpanded shell variable is not a path the guard can judge ---
    ("code-reviewer", "Bash", {"command": "cat > \"$E\" <<'EOF'\nx\nEOF"}, "allow", "heredoc into a variable path"),
    ("code-reviewer", "Bash", {"command": 'cp harness.py "$S/"'}, "allow", "cp into a variable path"),
    ("tester", "Bash", {"command": "cat > ${SCRATCH}/probe.py <<'PY'\nx\nPY"}, "allow", "braced variable path"),
    # ...but a literal path in the same command still decides it.
    ("code-reviewer", "Bash", {"command": 'cp "$S/x.py" analysis/dcf.py'}, "deny", "a literal target still decides"),
    ("tester", "Bash", {"command": "cat > analysis/x.py <<'EOF'\nx\nEOF"}, "deny", "heredoc into a literal denied path"),
    # --- roles the guard does not own ---
    ("Explore", "Edit", {"file_path": "analysis/dcf.py"}, "allow", "a built-in agent is unguarded"),
    ("", "Edit", {"file_path": "STATUS.md"}, "allow", "the orchestrator is unguarded here"),
]

# Cases that need a real git worktree of this repository. `{WT}` is replaced by
# its absolute path. Added by `P1f-worktree-guards` for backlog item 142: before
# it, every one of these was allowed, because a worktree is not under
# CLAUDE_PROJECT_DIR and the guard allowed whatever was not under it.
#
# These are listed apart from CASES because they cost a `git worktree add`. They
# are NOT optional: if the worktree cannot be made, the check fails rather than
# skipping, because a guard check that silently drops its newest cases is the
# defect backlog item 140 recorded.
WORKTREE_CASES: list[tuple[str, str, dict, str, str]] = [
    ("tester", "Write", {"file_path": "{WT}/analysis/dcf.py"}, "deny", "tester may not write analysis IN A WORKTREE"),
    ("tester", "Edit", {"file_path": "{WT}/models/valuation.py"}, "deny", "tester may not write models in a worktree"),
    ("tester", "Write", {"file_path": "{WT}/tests/unit/test_x.py"}, "allow", "tester MAY write tests in a worktree"),
    ("tester", "Write", {"file_path": "{WT}/.agent/journal/x.md"}, "allow", "tester may write its journal in a worktree"),
    ("programmer", "Write", {"file_path": "{WT}/tests/test_x.py"}, "deny", "programmer may not write tests in a worktree"),
    ("programmer", "Write", {"file_path": "{WT}/analysis/dcf.py"}, "allow", "programmer MAY write analysis in a worktree"),
    ("programmer", "Write", {"file_path": "{WT}/.claude/hooks/guard_paths.py"}, "deny", "the guard itself is closed in a worktree"),
    ("programmer", "Write", {"file_path": "{WT}/STATUS.md"}, "deny", "STATUS.md is closed in a worktree"),
    ("programmer", "Write", {"file_path": "{WT}/.agent/journal/INDEX.md"}, "deny", "INDEX.md is closed in a worktree"),
    ("code-reviewer", "Write", {"file_path": "{WT}/analysis/dcf.py"}, "deny", "code-reviewer writes nothing but its journal, in a worktree"),
    ("tester", "Bash", {"command": "rm -rf {WT}/analysis"}, "deny", "the Bash tripwire reaches into a worktree"),
    ("Explore", "Edit", {"file_path": "{WT}/analysis/dcf.py"}, "allow", "a built-in agent is unguarded in a worktree too"),
]


def hook_env() -> dict[str, str]:
    """The environment the guard runs under in this check.

    `PATH` is empty, which keeps the check hermetic, and the guard no longer
    needs anything on it: since round 2 of `P1f-worktree-guards` it finds a
    worktree by reading that tree's `.git` file rather than by running git.

    git is still added here, and only git's own directory, because
    `temporary_worktree` below runs `git worktree add` to build the tree the
    worktree cases need. **The guard under test does not use it.** Round 1 of
    this unit did shell out, and with `PATH` empty every worktree case would
    have passed as "allow" for the wrong reason; the code reviewer's F6 is what
    moved the guard off git entirely.
    """
    git = shutil.which("git")
    return {
        "CLAUDE_PROJECT_DIR": str(ROOT),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
        "PATH": str(Path(git).parent) if git else "",
    }


def ask(role: str, tool: str, tool_input: dict, cwd: str | None = None) -> str:
    payload = {
        "agent_type": role,
        "tool_name": tool,
        "cwd": cwd or str(ROOT),
        "hook_event_name": "PreToolUse",
        "tool_input": tool_input,
    }
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload), capture_output=True, text=True,
        env=hook_env(),
        check=False,
    )
    return "deny" if proc.stdout.strip() else "allow"


@contextlib.contextmanager
def temporary_worktree() -> Generator[Path | None]:
    """A real git worktree of this repository, removed afterwards.

    Yields None when git is missing or the add fails. Removal is best effort:
    Windows holds a lock on a worktree directory for a while after a process has
    read from it, so a failed cleanup must not fail the check. `git worktree
    prune` and the branch delete still run.
    """
    if not shutil.which("git"):
        yield None
        return
    path = Path(SCRATCH) / "guard_check_worktree"
    branch = "guard-check/tmp"
    subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(path)],
                   capture_output=True, text=True, check=False)
    subprocess.run(["git", "-C", str(ROOT), "branch", "-D", branch],
                   capture_output=True, text=True, check=False)
    made = subprocess.run(
        ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(path), "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if made.returncode != 0:
        yield None
        return
    try:
        yield path
    finally:
        subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(path)],
                       capture_output=True, text=True, check=False)
        subprocess.run(["git", "-C", str(ROOT), "worktree", "prune"],
                       capture_output=True, text=True, check=False)


def main() -> int:
    failures = []
    for role, tool, tool_input, expected, label in CASES:
        got = ask(role, tool, tool_input)
        if got != expected:
            failures.append(f"  want {expected:<5} got {got:<5}  {label}")

    total = len(CASES)
    with temporary_worktree() as wt:
        if wt is None:
            print(f"{total - len(failures)}/{total} guard cases correct")
            for line in failures:
                print(line)
            print("  FAIL: the worktree cases could not run -- git is missing or "
                  "`git worktree add` failed. They are not optional: without them "
                  "backlog item 142 is unguarded and nothing says so.")
            return 1
        total += len(WORKTREE_CASES)
        for role, tool, tool_input, expected, label in WORKTREE_CASES:
            filled = {k: v.replace("{WT}", str(wt).replace("\\", "/"))
                      for k, v in tool_input.items()}
            got = ask(role, tool, filled, cwd=str(wt))
            if got != expected:
                failures.append(f"  want {expected:<5} got {got:<5}  {label}")

    print(f"{total - len(failures)}/{total} guard cases correct")
    for line in failures:
        print(line)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
