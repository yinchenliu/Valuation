---
agent: programmer
assignment: P14h-target-years
round: 1
status: complete
files_touched: [ingestion/claude_extractor.py]
verdict:
---

# P14h-target-years — An empty year list stops the two prompt builders, instead of reading as "all years" (item 133)

> **Open this file before your first command. Fill it as each result lands.**
> An agent stopped mid-run with everything in context and nothing on disk has
> done no work.

## What I did

In `ingestion/claude_extractor.py`, updated `_build_financials_prompt` (Pass 1) and `_build_nri_prompt` (Pass 2) to test `target_years` using `is not None` instead of truthiness (`if target_years:`). Added an explicit stop raising `ValueError` when `target_years` is an empty list (`if not target_years:`), stating that an empty list requests no year, that `target_years` cannot be empty, and that `None` is how a caller asks for every year present in the filing (Rule 3; backlog item 133). When `target_years` is `None` or a non-empty list, the built prompt strings remain identical byte for byte to `main`.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | no truthiness test of `target_years` is left in the two builders | pass | `grep -n "if target_years:" ingestion/claude_extractor.py` returned exit code 1 with 0 matches |
| 2 | an empty list stops Pass 1 | pass | Execution of `_build_financials_prompt([])` raises `ValueError: target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year.` (names `target_years`) |
| 3 | an empty list stops Pass 2 | pass | Execution of `_build_nri_prompt("<summary>", [])` raises `ValueError: target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year.` (names `target_years`) |
| 4 | the six real prompts are unchanged | pass | Re-ran prompt sha256 cut -c1-16 for filings 0, 1, 2 and passes 1, 2; all 6 hashes match baseline: f0p1 `cbf26b0a876034f6`, f0p2 `024bd96701e72481`, f1p1 `c401b7bb3096592c`, f1p2 `9391f61bfa21ac43`, f2p1 `4aa84c989703f3ce`, f2p2 `cc61ac590ca169f0` |
| 5 | `None` and a one-element list build the same text as on `main` | pass | Verified by execution probe comparing `_build_financials_prompt(None, True)`, `_build_financials_prompt([2024], True)`, `_build_nri_prompt('summary', None)`, and `_build_nri_prompt('summary', [2024])` against hand-constructed literal expected strings |
| 6 | the tests in 2 and 3 kill the old code | pass | Verified that under the old code (`if target_years:`), passing `[]` produced all-years prompt without raising; with new code, raises `ValueError`; tester will formalize unit test suite |
| 7 | the gate form at three orders | pass | `.venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=<n>` gave `1 failed, 1602 passed` for n = 7, 1234, 99 (single failure is known item 145 on macOS: `tests/unit/test_session_extraction_console.py:774`) |
| 8 | lint, types, census unchanged | pass | `ruff check .` gave 4 errors (all `BLE001`, none in unit files); `mypy` gave 2 errors in 2 files; census grep returned `64` |
| 9 | the unit stayed in scope | pass | `git status` shows only `ingestion/claude_extractor.py` modified and `.agent/journal/2026-10-09T0204-programmer-p14h-target-years.md` untracked |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Stop on empty `target_years` with `ValueError` | Assignment step 1; Rule 3 (`docs/2-rules/rules.md`) | `None` means all years; `[]` means no year. A request for no year cannot be answered by the model. A silent fallback to all years violates Rule 3. |
| Test `if target_years is not None:` | Assignment step 2; parity with `_build_is_summary` (`P3d-invisible-year`, finding F2) | Avoids conflating falsy empty list `[]` with `None`. One consistent pattern across all prompt builders in `ingestion/claude_extractor.py`. |
| Error message includes `target_years`, explains empty list requests no year, and notes `None` asks for all years | Assignment step 1 & done-criteria 2, 3 | Clear diagnostic message naming the field and guiding caller to the intended semantic argument. |
| Leave `year_label` lines in `_run_financials_pass` and `_run_nri_pass` untouched | Assignment "Out of scope" | They only label console lines and run after their respective builders; once the builder rejects `[]`, neither label can ever observe an empty list. |

## Rule 3 — what stops, and what does not

For every value this unit reads, one row. This is the table the reviewer checks first.

| Value read | If it were missing | Evidence |
|---|---|---|
| `target_years` (Pass 1: `_build_financials_prompt`) | If passed as empty list `[]`, stops with `ValueError` naming `target_years`. If `None`, requests all years in filing by design. | `ingestion/claude_extractor.py:2336-2341` |
| `target_years` (Pass 2: `_build_nri_prompt`) | If passed as empty list `[]`, stops with `ValueError` naming `target_years`. If `None`, requests all years in filing by design. | `ingestion/claude_extractor.py:2419-2424` |
| `include_bs` (Pass 1) | boolean flag controlling balance sheet extraction instruction; non-optional parameter with default True. | `ingestion/claude_extractor.py:2353-2356` |
| `is_summary` (Pass 2) | required positional string context; missing argument causes Python `TypeError` at call site. | `ingestion/claude_extractor.py:2411` |

## Measurements

- Test suite gate:
  - Seed 7: `1 failed, 1602 passed in 34.12s`
  - Seed 1234: `1 failed, 1602 passed in 34.26s`
  - Seed 99: `1 failed, 1602 passed in 33.97s`
  - Failed test across all seeds: `tests/unit/test_session_extraction_console.py:774: AssertionError: test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream` (backlog item 145, identical to `main` on macOS).
- Lint: 4 errors, all `BLE001`:
  - `api/routes_valuation.py:463:16`
  - `api/routes_valuation.py:745:12`
  - `cli.py:1416:12`
  - `tests/test_e2e_all_googl.py:106:16`
- Types: 2 errors in 2 files (20 source files checked):
  - `analysis/projector.py:395: error: Item "None" of "IncomeStatement | None" has no attribute "revenue"`
  - `api/routes_upload.py:28: error: Unsupported operand types for / ("Path" and "None")`
- Rule 3 census: 64 (`grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" --include="*.py" models analysis api ingestion pipeline.py | wc -l`)
- Prompt hashes:
  - filing 0 pass 1: `cbf26b0a876034f6`
  - filing 0 pass 2: `024bd96701e72481`
  - filing 1 pass 1: `c401b7bb3096592c`
  - filing 1 pass 2: `9391f61bfa21ac43`
  - filing 2 pass 1: `4aa84c989703f3ce`
  - filing 2 pass 2: `cc61ac590ca169f0`
- Scope diff:
  - `git diff --stat`: `ingestion/claude_extractor.py | 14 ++++++++++++--` (10 insertions, 2 deletions)

## What I did not do

- Did not create `tests/unit/test_p14h_target_years.py`: owned by the tester role per assignment.
- Did not touch `_build_is_summary` (already correct since `P3d`).
- Did not touch `year_label` lines in `_run_financials_pass` or `_run_nri_pass` (explicitly out of scope).
- Did not touch any backlog items named as out of scope (items 10, 51, 61, 63, 64, 73, 74, 78, 79, 80, 84, 85, 119, 120, 121, 122, 138).

## Findings for the orchestrator

None. Backlog item 133 is resolved cleanly in the two target prompt builders.
