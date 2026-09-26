#!/usr/bin/env python3
"""Cases the PreToolUse write guard must get right.

Not a pytest file, and not named like one. The repository's suite count is a
measurement recorded in STATUS.md, so nothing here may join it.

Run it after any edit to .claude/hooks/guard_paths.py:

    .venv/Scripts/python.exe .claude/check_guard.py

Exit 0 = every case correct. Exit 1 = the failures, printed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / ".claude" / "hooks" / "guard_paths.py"

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
    ("tester", "Write", {"file_path": "c:/tmp/scratch/x.py"}, "allow", "scratch space is not guarded"),
    # --- Bash, denied forms ---
    ("tester", "Bash", {"command": 'sed -i "" "s/a/b/" analysis/dcf.py'}, "deny", "sed -i on analysis"),
    ("tester", "Bash", {"command": "echo hi > analysis/x.py"}, "deny", "redirect into analysis"),
    ("tester", "Bash", {"command": "cat f >> models/valuation.py"}, "deny", "append into models"),
    ("tester", "Bash", {"command": "rm analysis/wacc.py"}, "deny", "rm in analysis"),
    ("programmer", "Bash", {"command": "echo x | tee tests/test_x.py"}, "deny", "tee into tests"),
    ("programmer", "Bash", {"command": "cp c:/tmp/a STATUS.md"}, "deny", "cp over STATUS.md"),
    ("programmer", "Bash", {"command": "rm -rf .claude/hooks"}, "deny", "rm of the hooks"),
    ("code-reviewer", "Bash", {"command": "git restore analysis/dcf.py"}, "deny", "git restore of analysis"),
    # --- Bash, forms that must stay allowed ---
    ("tester", "Bash", {"command": ".venv/Scripts/python.exe -m pytest -q tests/ > c:/tmp/o.txt"}, "allow", "pytest redirected to scratch"),
    ("tester", "Bash", {"command": 'sed -i "" "s/a/b/" c:/tmp/s/x.py'}, "allow", "sed -i on a scratch file"),
    ("tester", "Bash", {"command": 'sed -i.bak "s/a/b/" c:/tmp/s/x.py'}, "allow", "sed -i.bak on a scratch file"),
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


def ask(role: str, tool: str, tool_input: dict) -> str:
    payload = {
        "agent_type": role,
        "tool_name": tool,
        "cwd": str(ROOT),
        "hook_event_name": "PreToolUse",
        "tool_input": tool_input,
    }
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload), capture_output=True, text=True,
        env={"CLAUDE_PROJECT_DIR": str(ROOT), "SYSTEMROOT": r"C:\Windows", "PATH": ""},
        check=False,
    )
    return "deny" if proc.stdout.strip() else "allow"


def main() -> int:
    failures = []
    for role, tool, tool_input, expected, label in CASES:
        got = ask(role, tool, tool_input)
        if got != expected:
            failures.append(f"  want {expected:<5} got {got:<5}  {label}")
    print(f"{len(CASES) - len(failures)}/{len(CASES)} guard cases correct")
    for line in failures:
        print(line)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
