#!/usr/bin/env python3
"""SubagentStop seal on the files no subagent may ever change.

The PreToolUse guard reads a shell command and can be fooled -- `python -c
"open(...,'w')"` writes a file it cannot see. This runs after the subagent
finishes and compares hashes instead of parsing a string.

It seals three things:

  .agent/journal/INDEX.md   the orchestrator is its only writer (AGENTS.md)
  STATUS.md                 the orchestrator's measurement of the build
  .claude/hooks/*.py, *.sh  the guard a subagent must not be able to disarm,
                            and run_hook.sh, which starts every hook

All three are compared against the snapshot `.claude/hooks/seal_baseline.py`
took at dispatch, not against HEAD. HEAD is the wrong baseline for the first
two: AGENTS.md has the orchestrator write them *after a subagent returns*, so
the next subagent inherits those uncommitted lines, and a HEAD comparison
blames it for the orchestrator's write. The only way to clear that accusation
is `git checkout --`, which deletes the orchestrator's record.

A missing snapshot falls back to the HEAD comparison for the two tracked
files. That is the blunter behaviour: it can raise a false alarm, but it never
lets a real change through. The hooks directory is skipped when there is no
snapshot, because a freshly created `.claude/` is untracked and would fire on
every run.

Exit 2 blocks the subagent from stopping and feeds stderr back to it.
Anything unexpected exits 0: a broken seal must never wedge the build.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROLES = {"programmer", "code-reviewer", "tester"}
INDEX = ".agent/journal/INDEX.md"
STATUS = "STATUS.md"
HOOKS = ".claude/hooks"
BASELINE = ".agent/.seal-baseline.json"


def dirty_against_head(project: str, path: str) -> list[str]:
    """`git status --porcelain` lines for `path`, or [] if git cannot answer."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", path],
            cwd=project, capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def digest(path: Path) -> str | None:
    """sha256 of `path`, or None if it does not exist."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def tree_digest(directory: Path) -> str | None:
    """sha256 over the sorted (name, bytes) pairs of every .py and .sh in `directory`.

    Must stay byte-identical to seal_baseline.tree_digest.
    """
    try:
        files = sorted([*directory.glob("*.py"), *directory.glob("*.sh")])
    except OSError:
        return None
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        try:
            h.update(f.name.encode("utf-8"))
            h.update(f.read_bytes())
        except OSError:
            return None
    return h.hexdigest()


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        sys.exit(0)

    if (data.get("agent_type") or "").strip() not in ROLES:
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    project = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    root = Path(project)

    try:
        baseline = json.loads((root / BASELINE).read_text())
    except (OSError, ValueError):
        baseline = None
    if not isinstance(baseline, dict):
        baseline = None

    # Backlog item 141. `seal_baseline.py` takes the snapshot when the number of
    # subagents in flight goes from 0 to 1 and only increments after that, so
    # this hook has to decrement, or the count never returns to 0 and the next
    # dispatch keeps a snapshot it should have replaced.
    #
    # Decrement FIRST, before any comparison can end this process. A seal that
    # fires exits 2, and if the write-back sat after that exit, every firing
    # would leave the count one too high for ever.
    if baseline is not None:
        raw = baseline.get("in_flight")
        count = raw if isinstance(raw, int) and not isinstance(raw, bool) else 0
        remaining = max(0, count - 1)
        updated = dict(baseline)
        updated["in_flight"] = remaining
        try:
            (root / BASELINE).write_text(json.dumps(updated, indent=2) + "\n")
        except OSError:
            pass                      # a tripwire does not stop a run over a locked file

    changed: list[str] = []

    if baseline is None:
        # No snapshot: fall back to HEAD for the two tracked files, and skip the
        # hooks directory rather than fire on an untracked `.claude/`.
        changed += dirty_against_head(project, INDEX)
        changed += dirty_against_head(project, STATUS)
    else:
        for label, key, actual in (
            (INDEX, "index_sha256", digest(root / INDEX)),
            (STATUS, "status_sha256", digest(root / STATUS)),
            (f"{HOOKS}/", "hooks_sha256", tree_digest(root / HOOKS)),
        ):
            if key not in baseline:
                continue
            if baseline[key] != actual:
                changed.append(f" M {label} (changed since this subagent was dispatched)")

    if not changed:
        sys.exit(0)

    print(
        "Sealed files changed during your run:\n"
        + "\n".join(f"  {line}" for line in changed)
        + "\n\n.agent/journal/INDEX.md and STATUS.md belong to the orchestrator. "
          ".claude/hooks/ holds the permissions that bind you. None of them is "
          "yours to change.\n"
          "Restore them with `git checkout -- <path>` (or delete the file if it "
          "is untracked), record what happened and why in your journal entry, "
          "and then finish.\n"
          "If you did NOT change the named file, do not restore it. Say so in "
          "your entry and finish. Destroying another agent's record to satisfy "
          "a seal is worse than the seal firing.",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
