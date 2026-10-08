"""Drive the `.claude/hooks` scripts from a test.

The hooks are not importable as a package: they are standalone scripts that the
Claude Code harness runs with a JSON payload on stdin. This module gives a test
two ways to drive one, and both are used on purpose.

* `run_hook` runs the file as a subprocess, the way the harness does. It is the
  faithful driver: it proves the file is executable, that it exits with the code
  its contract names, and -- with `path_value=""` -- that it needs nothing on
  `PATH`.
* `drive_main` imports the module and calls `main()` with a payload on a fake
  stdin. It costs about half a second less than a subprocess per call, and it is
  the driver that shows up in a coverage report.

`VALUATION_HOOKS_DIR` points both drivers at a copy of the hooks somewhere else.
That is how the mutation runs recorded in the tester's journal entry were made:
the four files in scope are never edited in place.

**Nothing here skips.** `require_git` raises instead of skipping when git is
missing, because a guard check that silently drops its newest cases is the
defect, not the report -- `.claude/check_guard.py` once ran the guard with
`PATH: ""`, which would have made every worktree case pass for the wrong reason,
and backlog item 140 is a mutation that survived the whole suite in silence on a
machine without the filings.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The three hook scripts this repository's permission separation rests on.
GUARD = "guard_paths.py"
SEAL_BASELINE = "seal_baseline.py"
SEAL_CHECK = "seal_check.py"


def hooks_dir() -> Path:
    """The directory holding the hooks under test."""
    override = os.environ.get("VALUATION_HOOKS_DIR")
    return Path(override).resolve() if override else REPO_ROOT / ".claude" / "hooks"


def load_hook(name: str) -> ModuleType:
    """Import one hook script by path.

    Deliberately NOT registered in `sys.modules`: two tests then cannot share a
    module object, and no import-order leak is possible (`P1e-test-order`).
    """
    path = hooks_dir() / name
    if not path.is_file():
        raise AssertionError(f"hook not found: {path}")
    spec = importlib.util.spec_from_file_location(f"_valuation_hook_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hook_env(project: Path, path_value: str | None = None) -> dict[str, str]:
    """The environment a hook runs under.

    `CLAUDE_PROJECT_DIR` is the only variable the hooks read. `SYSTEMROOT` is
    what a Python subprocess needs to start on Windows, and `PATH` is passed
    through unless a test is proving the guard does not need it.
    """
    return {
        "CLAUDE_PROJECT_DIR": str(project),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
        "PATH": os.environ.get("PATH", "") if path_value is None else path_value,
    }


class HookRun(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def run_hook(
    name: str,
    payload: dict[str, Any],
    project: Path,
    path_value: str | None = None,
) -> HookRun:
    """Run one hook as a subprocess, as the harness does."""
    proc = subprocess.run(
        [sys.executable, str(hooks_dir() / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=hook_env(project, path_value),
        check=False,
        timeout=120,
    )
    return HookRun(proc.returncode, proc.stdout, proc.stderr)


@contextlib.contextmanager
def temporary_env(values: dict[str, str]) -> Iterator[None]:
    saved = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, old in saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def drive_main(
    module: ModuleType,
    payload: dict[str, Any],
    project: Path,
    path_value: str | None = None,
) -> HookRun:
    """Call a loaded hook's `main()` with `payload` on stdin."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    saved_stdin = sys.stdin
    with temporary_env(hook_env(project, path_value)):
        sys.stdin = io.StringIO(json.dumps(payload))
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                module.main()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 0
        finally:
            sys.stdin = saved_stdin
    return HookRun(code, out.getvalue(), err.getvalue())


# --- the guard -------------------------------------------------------------


def guard_payload(
    role: str,
    tool: str,
    tool_input: dict[str, Any],
    cwd: Path,
) -> dict[str, Any]:
    return {
        "agent_type": role,
        "tool_name": tool,
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_input": tool_input,
    }


def decision_of(run: HookRun) -> tuple[str, str]:
    """`("allow", "")` or `("deny", <reason>)`, read off a guard run.

    The contract is the hook's own docstring: "Exit 0 with no output = no
    decision, the normal permission flow applies."
    """
    assert run.returncode == 0, f"the guard must always exit 0, got {run.returncode}\n{run.stderr}"
    text = run.stdout.strip()
    if not text:
        return ("allow", "")
    payload = json.loads(text)
    emitted = payload["hookSpecificOutput"]
    assert emitted["hookEventName"] == "PreToolUse"
    assert emitted["permissionDecision"] == "deny"
    return ("deny", emitted["permissionDecisionReason"])


def ask_guard(
    role: str,
    tool: str,
    tool_input: dict[str, Any],
    project: Path,
    cwd: Path,
    path_value: str | None = None,
) -> tuple[str, str]:
    """The guard's decision, taken through a real subprocess."""
    return decision_of(
        run_hook(GUARD, guard_payload(role, tool, tool_input, cwd), project, path_value)
    )


def ask_guard_in_process(
    guard: ModuleType,
    role: str,
    tool: str,
    tool_input: dict[str, Any],
    project: Path,
    cwd: Path,
    path_value: str | None = None,
) -> tuple[str, str]:
    """The same decision, taken by calling `main()` directly.

    A subprocess costs the better part of a second on this machine, so the
    matrices that run to tens of cases use this driver and a sample of each is
    re-taken through `ask_guard` -- plus
    `test_the_two_drivers_agree_on_every_shape`, which holds the two together.
    """
    return decision_of(
        drive_main(guard, guard_payload(role, tool, tool_input, cwd), project, path_value)
    )


# --- git, which must never be skipped over ---------------------------------


def require_git() -> str:
    """The git executable, or a loud failure.

    **This raises. It does not skip.** A skipped test reports green, and the
    worktree half of `P1f-worktree-guards` is exactly the half that cannot be
    exercised without a real `git worktree add`.
    """
    git = shutil.which("git")
    if git is None:
        raise AssertionError(
            "git is not on PATH, so no worktree case in this file can run. "
            "This FAILS rather than skips on purpose: `.claude/check_guard.py` "
            "once ran the guard with PATH empty, which would have made every "
            "worktree case pass for the wrong reason, and backlog item 140 is a "
            "mutation that survived the suite in silence on a machine without "
            "the filings. Install git, or this guard is untested."
        )
    return git


def git(args: list[str], cwd: Path) -> str:
    """Run git in `cwd`, failing loudly with its output if it does not succeed."""
    proc = subprocess.run(
        [require_git(), "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"`git {' '.join(args)}` failed in {cwd} with {proc.returncode}:\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
    return proc.stdout


#: Enough identity to commit without reading the machine's global git config.
COMMIT_IDENTITY = [
    "-c", "user.email=tester@example.invalid",
    "-c", "user.name=P1f tester",
    "-c", "commit.gpgsign=false",
]


def make_scratch_repository(root: Path, *, name: str = "project") -> Path:
    """A git repository under `root`, laid out like this one.

    Built from nothing in scratch space so that no test ever adds a worktree to,
    or commits in, the repository under test.
    """
    project = root / name
    for folder in (
        project / ".agent" / "journal",
        project / ".claude" / "hooks",
        project / "analysis",
        project / "models",
        project / "tests" / "unit",
        project / "docs",
    ):
        folder.mkdir(parents=True, exist_ok=True)
    (project / "STATUS.md").write_bytes(b"status\n")
    (project / "AGENTS.md").write_bytes(b"agents\n")
    (project / "config.py").write_bytes(b"X = 1\n")
    (project / ".agent" / "journal" / "INDEX.md").write_bytes(b"index\n")
    (project / "analysis" / "dcf.py").write_bytes(b"X = 1\n")
    (project / "models" / "valuation.py").write_bytes(b"X = 1\n")
    (project / ".claude" / "hooks" / "guard_paths.py").write_bytes(b"X = 1\n")
    git(["init", "-b", "main"], project)
    git(["add", "-A"], project)
    git([*COMMIT_IDENTITY, "commit", "-m", "scratch"], project)
    return project


def add_worktree(project: Path, path: Path) -> Path:
    """`git worktree add --detach path HEAD`, with git's layout fact asserted.

    A linked worktree's `.git` is a FILE holding `gitdir: <main>/.git/worktrees/
    <name>`; a normal checkout's is a directory. That is documented in
    `gitrepository-layout(5)` and it is the premise `worktree_root_of` rests on,
    so the test asserts it rather than assuming it.
    """
    git(["worktree", "add", "--detach", str(path), "HEAD"], project)
    marker = path / ".git"
    assert marker.is_file(), (
        f"{marker} is not a file. A linked worktree's .git is a file holding a "
        "`gitdir:` line; if git ever stopped doing that, `worktree_root_of` "
        "would be reading the wrong thing and every deny case below would be "
        "passing for the wrong reason."
    )
    return path
