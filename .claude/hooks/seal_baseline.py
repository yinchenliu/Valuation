#!/usr/bin/env python3
"""PreToolUse snapshot of the sealed files, taken at dispatch.

The SubagentStop seal asks "did this subagent change a sealed file?". It cannot
ask git, because AGENTS.md has the orchestrator write to `.agent/journal/INDEX.md`
and `STATUS.md` *after a subagent returns*. By the time the next subagent starts,
the orchestrator's own uncommitted lines are already there. Comparing against
HEAD then accuses every subagent of the orchestrator's write, and the only way to
clear the accusation is to delete the orchestrator's record -- the seal destroying
what it exists to protect.

So the seal needs a baseline taken at the moment of dispatch instead. This hook
writes it. It runs on PreToolUse for Agent, Task and SendMessage -- every way a
subagent starts or restarts, which is the orchestrator's last action before that
subagent runs.

SendMessage is in that list because resuming an agent through it skips the Agent
matcher entirely, which would leave the seal comparing against a stale snapshot
and blaming the resumed agent for every orchestrator write since.

Subagents cannot call Agent or Task (`disallowedTools` in every role's
frontmatter). They CAN call SendMessage, so the role check below is what stops a
subagent refreshing the measurement taken of it. That check is load bearing, not
defensive tidiness.

Three things are sealed:

  .agent/journal/INDEX.md   the orchestrator is its only writer
  STATUS.md                 the orchestrator's measurement of the build
  .claude/hooks/*.py        the guard a subagent must not be able to disarm

The baseline is a hash, not a copy. A subagent that changes a file and changes it
back has changed nothing, and that is the right answer.

Exit 0 always. A missing baseline makes the seal fall back to HEAD for the two
tracked files, which is the older, blunter behaviour -- never a hole.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROLES = {"programmer", "code-reviewer", "tester"}
INDEX = Path(".agent/journal/INDEX.md")
STATUS = Path("STATUS.md")
HOOKS = Path(".claude/hooks")
BASELINE = Path(".agent/.seal-baseline.json")


def digest(path: Path) -> str | None:
    """sha256 of `path`, or None if it does not exist."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def tree_digest(directory: Path) -> str | None:
    """sha256 over the sorted (name, bytes) pairs of every .py in `directory`.

    Sorted so the result does not depend on directory order, and the name is
    hashed alongside the bytes so a rename is a change.
    """
    try:
        files = sorted(directory.glob("*.py"))
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

    # A subagent must never refresh the baseline. It cannot reach this hook via
    # Agent or Task -- both are disallowed for all three roles -- but the seal is
    # worth nothing if the thing it measures can be reset by the thing it measures.
    if (data.get("agent_type") or "").strip() in ROLES:
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)

    try:
        (project / BASELINE).parent.mkdir(parents=True, exist_ok=True)
        (project / BASELINE).write_text(
            json.dumps(
                {
                    "index_sha256": digest(project / INDEX),
                    "status_sha256": digest(project / STATUS),
                    "hooks_sha256": tree_digest(project / HOOKS),
                    "taken_at": datetime.now(UTC).isoformat(),
                    "tool": data.get("tool_name") or "",
                },
                indent=2,
            )
            + "\n"
        )
    except OSError:
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
