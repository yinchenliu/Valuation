#!/bin/sh
# Runs one hook script from this directory with the project's own interpreter.
#
#   sh "$CLAUDE_PROJECT_DIR/.claude/hooks/run_hook.sh" guard_paths.py
#
# settings.json calls this instead of naming an interpreter, because the venv
# puts the interpreter in a different place on each machine this repository
# runs on:
#
#   macOS, Linux  .venv/bin/python
#   Windows       .venv/Scripts/python.exe   (Claude Code runs hooks in Git Bash)
#
# Until 2026-10-02 settings.json named the Windows path only. On macOS the hook
# command could not start, Claude Code treats that as a non-blocking error, and
# every tool call went through: the write guard and the seal were both off, and
# nothing said so. `.agent/.seal-baseline.json` had never been written on that
# machine, which is how it was found.
#
# So a missing interpreter may not pass silently where it matters. For the write
# guard, when a subagent role is running, this exits 2: the tool call is blocked
# and the agent is told why. The orchestrator is not blocked. It is unguarded by
# design, and it must stay able to run the commands that create the venv. The two
# seal hooks only warn: blocking a SubagentStop would wedge the subagent, and the
# guard has already refused every write it could have made.

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
hook="$root/.claude/hooks/$1"

for py in "$root/.venv/bin/python" "$root/.venv/Scripts/python.exe"; do
    if [ -x "$py" ]; then
        exec "$py" "$hook"
    fi
done

missing="No interpreter at $root/.venv/bin/python or $root/.venv/Scripts/python.exe, so the hook $1 did not run. Create the venv: docs/8-build/environment.md section 2."

if [ "$1" = "guard_paths.py" ] \
    && grep -Eq '"agent_type"[[:space:]]*:[[:space:]]*"(programmer|code-reviewer|tester)"'; then
    echo "$missing A subagent may not run with the write guard off." >&2
    exit 2
fi

echo "$missing" >&2
exit 1
