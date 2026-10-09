---
id: P15c-portable-session-paths-tests
phase: 15 — two extraction routes
agent: tester
depends_on: [P15c-portable-session-paths]
---

# Verify portable session file PDF paths (item 146)

## Objective

Verify that `ingestion/session_extraction.py` writes repo-relative paths for PDFs inside the
repository and absolute paths for PDFs outside, resolves relative paths against `config.BASE_DIR`
regardless of the current working directory, preserves and loads absolute paths as recorded,
and names both recorded and resolved paths when a PDF is missing on disk.

## What is already true — verify, do not redo

- `cmd_plan` and `load_session_extraction` in `ingestion/session_extraction.py` have been updated
  by the programmer and approved by the code reviewer.
- The gate form passes at seeds 7, 1234, 99 (`0 failed, 1606 passed, 0 skipped`).
- `extractions/WMT.json` holds repo-relative paths (`10K_filings/WMT/...`).

## What to do

1. Create a new test file `tests/unit/test_p15c_portable_session_paths.py`.
2. Write tests covering:
   - `plan` writes repo-relative paths for PDFs inside the repository (Criterion 1).
   - `plan` writes absolute paths for PDFs outside the repository (Criterion 2).
   - `load_session_extraction` loads repo-relative paths even when `os.chdir` changes the working directory to a temporary directory (Criterion 3).
   - `load_session_extraction` loads absolute paths correctly when recorded (Criterion 5).
   - When a PDF is missing on disk, `load_session_extraction` raises `ValueError` naming both the recorded `pdf_path` and the resolved path (Criterion 6).
3. Derive expected values independently by hand. Do not copy output from the code.
4. Verify mutation kill: show that your new tests fail if relative paths are resolved against the working directory (`cwd`) rather than `config.BASE_DIR`, and pass when restored.
5. Report accuracy and coverage counts.
6. Write your journal entry to `.agent/journal/<YYYY-MM-DDTHHMM>-tester-p15c-portable-session-paths.md` from `.agent/TEMPLATE-log-entry.md`.

## Files in scope

- `tests/unit/test_p15c_portable_session_paths.py` (new test file)

**Nothing else.** You may not modify implementation code under `ingestion/`, `models/`, `analysis/`, or `api/`.

## Out of scope

- `ingestion/session_extraction.py` (owned by programmer).
- `extractions/` and `docs/`.
- The four record files (`STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md`, `docs/9-reference/refactor-backlog.md`).

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | new test file exists and passes | `pass` | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_p15c_portable_session_paths.py` |
| 2 | gate form passes with new test included | `0 failed, 1607+ passed, 0 skipped` | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=7` |
| 3 | mutation check kills defect | test fails when relative paths resolve against cwd, passes when restored | verify failure under mutation and pass when restored |
| 4 | unit stayed in scope | only `tests/unit/test_p15c_portable_session_paths.py` and tester journal entry | `git status` |

## Citations

- `docs/2-rules/rules.md`, rule 3 — a stop names its input.
- `docs/9-reference/refactor-backlog.md`, item 146.
- `.agent/assignments/P15c-portable-session-paths.md`.
