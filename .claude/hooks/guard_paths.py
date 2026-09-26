#!/usr/bin/env python3
"""PreToolUse path guard for the Valuation subagents.

Claude Code has no per-agent edit-glob field, so the separation that AGENTS.md
calls "enforced by permission, not by good intentions" is enforced here.

The roles, and what each may write:

  programmer     everything except tests/
  code-reviewer  nothing except .agent/journal/
  tester         nothing except tests/ and .agent/journal/

Four paths are denied to every role, whatever its allow list says:

  * .agent/journal/INDEX.md  the orchestrator is its only writer (AGENTS.md).
  * STATUS.md                the orchestrator's measurement of the build.
  * AGENTS.md                the contract the roles are bound by.
  * .claude/                 a subagent does not edit the permissions that
                             bind it, nor the hook that enforces them.

Scope. Write, Edit and NotebookEdit are checked exactly. Bash is a tripwire,
not a sandbox: it parses the mutating forms (redirects, sed -i, tee, cp, mv,
rm, patch, git restore) and denies those. A shell can still write a file in a
way this script cannot see -- `python -c` is the obvious one. The SubagentStop
seal catches what slips past for the two files that matter most, and the code
reviewer catches out-of-scope files by reading the diff.

Paths outside the repository are allowed. Assignments call for scratch runs,
and those write outside the tree on purpose.

Exit 0 with no output = no decision, the normal permission flow applies.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path, PurePosixPath

# role -> (denied globs, allowed globs). An empty allow list means "allow
# anything the deny list does not catch". A non-empty allow list means
# "deny everything the allow list does not name".
ROLES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "programmer": (
        ("tests/**",),
        (),
    ),
    "code-reviewer": (
        (),
        (".agent/journal/**",),
    ),
    "tester": (
        (),
        ("tests/**", ".agent/journal/**"),
    ),
}

# Denied for every role above, whatever their allow list says.
ALWAYS_DENIED: tuple[tuple[str, str], ...] = (
    (".agent/journal/INDEX.md", "the orchestrator is its only writer (AGENTS.md)"),
    ("STATUS.md", "the orchestrator owns the measurement of the build (AGENTS.md)"),
    ("AGENTS.md", "it is the contract you are bound by; changing it is an escalation"),
    (".claude/**", "a subagent does not edit the permissions that bind it"),
)

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "StrReplace"}

PATH_KEYS = ("file_path", "notebook_path", "path", "filePath")


def emit_deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def repo_relative(target: str, project: Path, cwd: Path) -> str | None:
    """Return the repo-relative POSIX path, or None if outside the repository."""
    if not target:
        return None
    expanded = os.path.expandvars(os.path.expanduser(target.strip().strip('"').strip("'")))
    if not expanded:
        return None
    # A variable the hook's own environment cannot resolve stays literal, and
    # `$S/out.py` then reads as a repo-relative path called "$S". The guard
    # cannot know what the shell will expand, so it says so by declining to
    # guess. This is the documented threat model, not a hole: the guard is a
    # tripwire, a shell can already write a file it cannot see (`python -c`),
    # and the two files that must never move are sealed again at SubagentStop,
    # where a variable cannot help.
    if "$" in expanded or "%" in expanded:
        return None
    p = Path(expanded)
    if not p.is_absolute():
        p = cwd / p
    try:
        rel = os.path.relpath(os.path.normpath(str(p)), str(project))
    except ValueError:            # different drive on Windows
        return None
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return None
    return PurePosixPath(rel.replace(os.sep, "/")).as_posix()


def matches(rel: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return rel == prefix or rel.startswith(prefix + "/")
    return PurePosixPath(rel).match(pattern) or rel == pattern


def verdict(rel: str, role: str) -> str | None:
    """Return a denial reason, or None if the write is allowed."""
    for pattern, why in ALWAYS_DENIED:
        if matches(rel, pattern):
            return f"`{rel}` is closed to every subagent: {why}."
    denied, allowed = ROLES[role]
    for pattern in denied:
        if matches(rel, pattern):
            return (
                f"The `{role}` agent may not write `{rel}` (`{pattern}` is denied). "
                f"See .claude/agents/{role}.md."
            )
    if allowed and not any(matches(rel, pattern) for pattern in allowed):
        listed = ", ".join(f"`{p}`" for p in allowed)
        return (
            f"The `{role}` agent may write only {listed}. `{rel}` is outside that. "
            f"Report it in your journal entry instead; do not fix it."
        )
    return None


# --- Bash parsing -----------------------------------------------------------

REDIRECT = re.compile(r"(?:^|[\s;|&(])\d?>>?\s*([^\s;|&()<>]+)")
DD_OF = re.compile(r"\bdd\b[^;|&]*?\bof=([^\s;|&]+)")


def _strip_flags(words: list[str]) -> list[str]:
    """Positional arguments only. Empty strings go too: `sed -i "" s/a/b/ f`
    passes the backup suffix as its own empty argument, and keeping it would
    shift the script argument into the target position."""
    return [w for w in words if w and not w.startswith("-")]


def bash_targets(command: str) -> list[str]:
    """Best-effort list of paths this shell command writes to."""
    targets: list[str] = []
    targets += REDIRECT.findall(command)
    targets += DD_OF.findall(command)

    for segment in re.split(r"[;|&]+|\n", command):
        try:
            words = shlex.split(segment)
        except ValueError:
            words = segment.split()
        if not words:
            continue
        # walk each word so `env X=1 sed -i ...` and `git restore ...` are seen
        for i, word in enumerate(words):
            verb = PurePosixPath(word).name
            rest = words[i + 1:]
            if verb == "sed" and any(w.startswith("-i") or w == "--in-place" for w in rest):
                targets += _strip_flags(rest)[1:]      # skip the script argument
            elif verb in {"tee", "rm", "truncate", "shred", "unlink", "patch"}:
                targets += _strip_flags(rest)
            elif verb in {"cp", "mv", "install", "rsync", "ln"}:
                positional = _strip_flags(rest)
                if len(positional) >= 2:
                    targets.append(positional[-1])
            elif verb == "git" and rest:
                sub = _strip_flags(rest)
                if sub and sub[0] in {"restore", "checkout", "apply", "rm", "mv", "clean"}:
                    targets += sub[1:]
    return targets


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        sys.exit(0)                       # never block on a malformed payload

    role = (data.get("agent_type") or "").strip()
    if role not in ROLES:
        sys.exit(0)                       # the orchestrator and built-in agents are unguarded

    tool = data.get("tool_name") or ""
    tool_input = data.get("tool_input") or {}
    cwd = Path(data.get("cwd") or os.getcwd())
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)

    candidates: list[str] = []
    if tool in WRITE_TOOLS:
        for key in PATH_KEYS:
            value = tool_input.get(key)
            if isinstance(value, str):
                candidates.append(value)
        for edit in tool_input.get("edits") or []:
            if isinstance(edit, dict) and isinstance(edit.get("file_path"), str):
                candidates.append(edit["file_path"])
    elif tool == "Bash":
        command = tool_input.get("command")
        if isinstance(command, str):
            candidates = bash_targets(command)
    else:
        sys.exit(0)

    for candidate in candidates:
        rel = repo_relative(candidate, project, cwd)
        if rel is None:
            continue                      # outside the repository: scratch space, allowed
        reason = verdict(rel, role)
        if reason:
            emit_deny(reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
