---
agent: tester
assignment: P15c-portable-session-paths-tests
round: 1
status: complete
files_touched: [tests/unit/test_p15c_portable_session_paths.py]
verdict: pass
---

# P15c-portable-session-paths-tests — Verifying portable session file PDF paths (item 146)

> **Opened before the first command. Filled as each result landed.**

## What I did

Created `tests/unit/test_p15c_portable_session_paths.py` with 14 test functions (43 static assert statements, 5 `pytest.raises` checks, 0 copied from runtime code output). Verified that `_format_pdf_path` formats paths relative to `config.BASE_DIR` with forward slashes for files inside the repository and formats external paths as absolute. Verified that `_resolve_pdf_path` resolves relative paths against `config.BASE_DIR` regardless of the current working directory (`cwd`) and preserves absolute paths as recorded. Verified that `cmd_plan` produces repo-relative paths for repository filings and absolute paths for external filings. Verified that `load_session_extraction` loads repo-relative paths when executed from another working directory (such as a temporary folder). Verified that when a PDF file is missing on disk, `load_session_extraction` raises `ValueError` naming both the recorded and resolved paths. Verified Rule 3 stops when `pdf_path` is missing, empty, or not a string. Verified mutation kill in a scratch directory: mutating relative path resolution to use `cwd` fails 4 tests. Measured gate suite at three random seeds (7, 1234, 99) with 1620 passing tests and 0 failures. Did not modify any implementation code.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | new test file exists and passes | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_p15c_portable_session_paths.py` passed (14 passed in 22.14s) |
| 2 | gate form passes with new test included | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=<seed>` passed: Seed 7: 1620 passed in 58.22s; Seed 1234: 1620 passed in 55.98s; Seed 99: 1620 passed in 57.92s (0 failed, 0 skipped across all runs) |
| 3 | mutation check kills defect | pass | Tested in scratch directory `/tmp/p15c_scratch`: mutating `_resolve_pdf_path` to resolve relative to `cwd` fails 4 tests (`test_cmd_plan_writes_repo_relative_paths_for_repo_filings`, `test_missing_pdf_relative_path_raises_naming_recorded_and_resolved_paths`, `test_resolve_pdf_path_resolves_relative_against_base_dir`, `test_load_session_extraction_loads_relative_paths_from_other_directory`). All 14 pass when restored |
| 4 | unit stayed in scope | pass | Only `tests/unit/test_p15c_portable_session_paths.py` and `.agent/journal/2026-10-09T0245-tester-p15c-portable-session-paths.md` created. Implementation code untouched |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Use scratch tree under `/tmp/p15c_scratch` for mutation test | `.claude/agents/tester.md` ("You may not modify implementation code") and guard hook `guard_paths.py` | Modifying repository files violates tester permissions; scratch directory isolates mutation testing without altering repository files |
| Test `monkeypatch.chdir(tmp_path)` in loader tests | Assignment done-criterion 3; item 146 ("run from another working directory") | Changing working directory explicitly tests that path resolution uses `config.BASE_DIR` instead of `os.getcwd()` |
| Test both relative and absolute missing PDF paths | Rule 3: a stop names its input and where it looked | Verifies that missing PDF stops report both recorded and resolved paths for relative and absolute paths |
| Use `stub_evidence_reader` for external PDF `cmd_plan` test | `tests/unit/_fiscal_year_stub.py` | Tests external path formatting in `cmd_plan` without creating multi-megabyte synthetic 10-K cover pages |
| Assert forward slashes and non-absolute format on relative paths | Requirement 1; portability across Windows and macOS | Verifies that paths do not contain Windows backslashes (`\`) or leading slashes |

## Rule 3 — what stops, and what does not

For every value this unit reads, one row. This is the table the reviewer checks first.

| Value read | If it were missing | Evidence |
|---|---|---|
| `entry["pdf_path"]` key | Stops and names `key 'pdf_path' is absent` | `ingestion/session_extraction.py:401`, `test_rule3_missing_pdf_path_key_stops_and_names_field` |
| `entry["pdf_path"]` empty string | Stops and names `'pdf_path' must be a non-empty string` | `ingestion/session_extraction.py:414`, `test_rule3_empty_pdf_path_stops_and_names_field` |
| `entry["pdf_path"]` non-string type | Stops and names `'pdf_path' must be a non-empty string` | `ingestion/session_extraction.py:414`, `test_rule3_non_string_pdf_path_stops_and_names_field` |
| PDF file on disk (relative path) | Stops and names recorded and resolved paths (`the PDF <recorded> (resolved to <resolved>) is not on disk`) | `ingestion/session_extraction.py:472`, `test_missing_pdf_relative_path_raises_naming_recorded_and_resolved_paths` |
| PDF file on disk (absolute path) | Stops and names recorded and resolved paths (`the PDF <recorded> (resolved to <resolved>) is not on disk`) | `ingestion/session_extraction.py:472`, `test_missing_pdf_absolute_path_raises_naming_recorded_and_resolved_paths` |

## Measurements

- **Accuracy**: 43 of 43 static assertions (and 5 `pytest.raises` checks) match an independently derived expectation. 0 assertions copied from running code output.
- **Coverage**: 100% of statements and branches added or modified by P15c in `ingestion/session_extraction.py`:
  - `_format_pdf_path` (`:352-359`): 8 statements, 100% covered.
  - `_resolve_pdf_path` (`:362-367`): 5 statements, 100% covered.
  - `_session_plans` (`:415, 421-422`): 100% covered.
  - `_pdf_problems` (`:467, 470-474`): 100% covered.
  - `cmd_plan` (`:912`): 100% covered.
- **Gates**:
  - Baseline: 1606 passed, 0 failed, 0 skipped.
  - Seed 7: 1620 passed, 0 failed, 0 skipped in 58.22s (+14 tests).
  - Seed 1234: 1620 passed, 0 failed, 0 skipped in 55.98s.
  - Seed 99: 1620 passed, 0 failed, 0 skipped in 57.92s.
- **Lint**: 4 errors (all pre-existing `BLE001`), 0 in `tests/unit/test_p15c_portable_session_paths.py`.
- **Types**: 2 errors in 2 files (`analysis/projector.py:395`, `api/routes_upload.py:28`), 0 in new test file.
- **Rule 3 Census**: 64 (unchanged).

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `test_format_pdf_path_repo_relative_for_path_inside_repo` formatted path | `"10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf"` | Closed-form identity: `path.relative_to(config.BASE_DIR).as_posix()` strips the repository root and uses forward slashes |
| `test_format_pdf_path_absolute_for_path_outside_repo` formatted path | `str(outside_file.resolve())` | Closed-form identity: path outside base raises `ValueError` on `relative_to` and returns `str(Path.resolve())` |
| `test_resolve_pdf_path_resolves_relative_against_base_dir` resolved path | `(config.BASE_DIR / rel_path).resolve()` | Closed-form identity: relative path resolves to `(config.BASE_DIR / rel).resolve()`, invariant across changing `os.getcwd()` |
| `test_resolve_pdf_path_preserves_absolute_path` resolved path | `abs_path` | Closed-form identity: `p.is_absolute()` returns `Path(abs_path)` unchanged |
| `test_cmd_plan_writes_repo_relative_paths_for_repo_filings` filing count | `2` | Hand arithmetic: 2 PDF arguments passed to plan -> 2 filings in output list |
| `test_cmd_plan_writes_repo_relative_paths_for_repo_filings` filing 0 path | `"10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf"` | Closed-form identity: repo filing formats to repo-relative posix path |
| `test_cmd_plan_writes_repo_relative_paths_for_repo_filings` filing 1 path | `"10K_filings/WMT/Walmart Inc._10-K_2026-01-31_English.pdf"` | Closed-form identity: repo filing formats to repo-relative posix path |
| `test_cmd_plan_writes_absolute_paths_for_external_filings` filing paths | `str(ext_pdf_2024.resolve())`, `str(ext_pdf_2026.resolve())` | Closed-form identity: files outside repo format to resolved absolute paths |
| `test_load_session_extraction_loads_relative_paths_from_other_directory` filing count | `3` | Hand arithmetic: Walmart session holds 3 filings (FY2024, FY2025, FY2026) |
| `test_load_session_extraction_loads_relative_paths_from_other_directory` years | `[2022, 2023, 2024, 2025, 2026]` | Closed-form identity: FY2024 gives 2022-2024, FY2025 gives 2025, FY2026 gives 2026 |
| `test_load_session_extraction_loads_from_repo_root` filing count and years | `3`, `[2022, 2023, 2024, 2025, 2026]` | Closed-form identity: loading from repo root matches loading from changed directory |
| `test_load_session_extraction_loads_absolute_paths_when_recorded` filing count and years | `3`, `[2022, 2023, 2024, 2025, 2026]` | Closed-form identity: session file with absolute paths loads identical filings and years |
| `test_missing_pdf_relative_path_raises...` error message substrings | `fake_rel`, `expected_resolved`, `expected_message` | Rule 3 requirement: message states `"the PDF <recorded> (resolved to <resolved>) is not on disk"` |
| `test_missing_pdf_absolute_path_raises...` error message substrings | `fake_abs`, `expected_message` | Rule 3 requirement: message states `"the PDF <recorded> (resolved to <resolved>) is not on disk"` |
| `test_rule3_missing_pdf_path_key_stops...` exception match | `"key 'pdf_path' is absent"` | Rule 3 requirement: missing dictionary key stops and names field |
| `test_rule3_empty_pdf_path_stops...` exception match | `"'pdf_path' must be a non-empty string"` | Rule 3 requirement: empty string stops and names field |
| `test_rule3_non_string_pdf_path_stops...` exception match | `"'pdf_path' must be a non-empty string"` | Rule 3 requirement: non-string value stops and names field |

## Mutations — killed

| # | Mutation | `file` | Result | Tests that went red |
|---|---|---|---|---|
| **M1** | In `_resolve_pdf_path`, resolve relative path against `cwd` (`Path(recorded_path).resolve()`) instead of `(config.BASE_DIR / p).resolve()` | `ingestion/session_extraction.py:367` | **4 failed, 10 passed** | `test_cmd_plan_writes_repo_relative_paths_for_repo_filings`, `test_missing_pdf_relative_path_raises_naming_recorded_and_resolved_paths`, `test_resolve_pdf_path_resolves_relative_against_base_dir`, `test_load_session_extraction_loads_relative_paths_from_other_directory` |

## What I did not do

- Did not edit implementation code under `ingestion/`, `models/`, `analysis/`, or `api/`.
- Did not touch `extractions/WMT.json` or documents under `docs/`.
- Did not touch the four record files (`STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md`, `docs/9-reference/refactor-backlog.md`).

## Findings for the orchestrator

None. Backlog item 146 is fully verified and locked.

## Verdict

pass
