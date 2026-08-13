"""PreToolUse guard: keep the qa-tester subagent inside tests/.

The qa-tester agent is defined as a read-only reviewer of production code that may
only author test code. Instructions alone make that a convention; this hook makes
it a rule.

Claude Code passes the hook a JSON payload on stdin containing `agent_type`, so the
restriction applies to that one subagent and leaves the main agent (and every other
subagent) untouched.

Denies, for agent_type == "qa-tester" only:
  * Write / Edit / NotebookEdit to any path outside <project>/tests/
  * git commands that mutate history or the working tree
  * re-baselining the golden snapshot (--update), which would erase the very drift
    the agent exists to catch

Exit 0 always: a deny is expressed as JSON on stdout, per the PreToolUse contract.
Anything unexpected falls through to "allow" rather than wedging the session.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

GUARDED_AGENT = "qa-tester"
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
ALLOWED_SUBDIR = "tests"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Exact-shape matches only. A loose pattern here would block legitimate read-only
# git use (status, log, diff), which the agent needs to scope a regression.
BLOCKED_BASH = [
    (
        re.compile(r"\bgit\s+(commit|push|reset|revert|rebase|merge|cherry-pick|stash)\b"),
        "qa-tester does not change git state. Report the finding; the fixer commits.",
    ),
    (
        re.compile(r"\bgit\s+(checkout|restore)\b.*--"),
        "qa-tester does not discard working-tree changes.",
    ),
    (
        re.compile(r"test_regression_golden\.py.*--update"),
        "Re-baselining the golden snapshot erases the numeric drift you were asked "
        "to detect. Report the drift instead.",
    ),
]


def deny(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # Malformed input is not the agent's fault — do not block on it.

    if payload.get("agent_type") != GUARDED_AGENT:
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool in WRITE_TOOLS:
        raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if not raw:
            return 0

        target = Path(raw)
        if not target.is_absolute():
            target = Path(payload.get("cwd") or PROJECT_ROOT) / target

        try:
            resolved = target.resolve()
        except OSError:
            deny(f"Could not resolve {raw!r}; refusing the write.")

        tests_dir = (PROJECT_ROOT / ALLOWED_SUBDIR).resolve()
        if resolved != tests_dir and tests_dir not in resolved.parents:
            deny(
                f"qa-tester may only write under {tests_dir}. "
                f"{resolved} is production code and is read-only to this agent.\n"
                "Do not fix the bug. Put the failing case in a test under tests/ and "
                "describe the fix in your report so it can be applied separately."
            )
        return 0

    if tool == "Bash":
        command = tool_input.get("command", "")
        for pattern, reason in BLOCKED_BASH:
            if pattern.search(command):
                deny(reason)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
