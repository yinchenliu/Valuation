---
agent: tester
assignment: P14h-target-years-tests
round: 1
status: complete
files_touched: [tests/unit/test_p14h_target_years.py, .agent/journal/2026-10-09T0218-tester-p14h-target-years.md]
verdict: pass
---

# P14h-target-years-tests — Verifying target_years prompt builder stops and prompt invariance (item 133)

## What I did

Created unit test suite `tests/unit/test_p14h_target_years.py` containing 23 independent unit tests verifying Rule 3 stops on empty `target_years` lists, closed-form template prompt string generation against hand-derived literal expectations, prompt pair assembly invariance, and real filing extraction prompt invariance across all three filings in `extractions/WMT.json` for both Pass 1 and Pass 2. Verified that all tests call production code directly (item 148), that pre-item-133 code (`if target_years:` without stop) is killed under mutation, that the full gate passes with the single expected failure (item 145 on macOS), and that lint, types, and Rule 3 census are clean and unchanged.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | no truthiness test of `target_years` is left in the two builders | pass | `grep -n "if target_years:" ingestion/claude_extractor.py` returned exit code 1 with 0 matches; locked by `test_no_truthiness_test_of_target_years_in_source` |
| 2 | an empty list stops Pass 1 | pass | `_build_financials_prompt([])` raises `ValueError: target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year.` (names `target_years`); locked by `test_build_financials_prompt_empty_list_stops_and_names_target_years`, `test_build_financials_prompt_empty_list_stops_with_include_bs_false`, `test_pass1_prompt_pair_empty_list_stops`, and `test_pass1_prompts_empty_tuple_in_plan_stops` |
| 3 | an empty list stops Pass 2 | pass | `_build_nri_prompt("...", [])` raises `ValueError: target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year.` (names `target_years`); locked by `test_build_nri_prompt_empty_list_stops_and_names_target_years`, `test_pass2_prompt_pair_empty_list_stops`, and `test_pass2_prompts_empty_tuple_in_plan_stops` |
| 4 | the six real prompts are unchanged | pass | Six real prompts on `extractions/WMT.json` match baseline hashes: filing 0 pass 1 `cbf26b0a876034f6`, pass 2 `024bd96701e72481`; filing 1 pass 1 `c401b7bb3096592c`, pass 2 `9391f61bfa21ac43`; filing 2 pass 1 `4aa84c989703f3ce`, pass 2 `cc61ac590ca169f0`; locked by `test_real_prompt_hash_invariance` across 6 test parameters |
| 5 | `None` and a one-element list build the same text as on `main` | pass | Asserted against literal hand-derived text in `test_build_financials_prompt_none_bs_true_matches_hand_derived`, `test_build_financials_prompt_none_bs_false_matches_hand_derived`, `test_build_financials_prompt_single_year_bs_true_matches_hand_derived`, `test_build_financials_prompt_single_year_bs_false_matches_hand_derived`, `test_build_financials_prompt_multi_year_sorted_matches_hand_derived`, `test_build_nri_prompt_none_matches_hand_derived`, `test_build_nri_prompt_single_year_matches_hand_derived`, `test_build_nri_prompt_multi_year_sorted_matches_hand_derived`, and `test_prompt_pair_assembly_closed_form_identity` |
| 6 | the tests in 2 and 3 kill the old code | pass | Mutation probe reverting to `if target_years:` fails 7 tests (DID NOT RAISE ValueError) and passes 10 happy path tests; on production codebase all 23 tests pass |
| 7 | the gate form at three orders | pass | Full gate runs: seed 7 (`1 failed, 1625 passed in 31.23s`), seed 1234 (`1 failed, 1625 passed in 31.98s`), seed 99 (`1 failed, 1625 passed in 32.25s`). Failure set equals `main`'s: `tests/unit/test_session_extraction_console.py:774` (item 145 on macOS). Passed count increased by 23 from 1602 to 1625 |
| 8 | lint, types, census unchanged | pass | `ruff check .` reported 4 errors (all `BLE001`, 0 in unit files); `mypy` reported 2 errors in 2 files (0 in unit files); Rule 3 census is 64 |
| 9 | unit stayed in scope | pass | Only `ingestion/claude_extractor.py`, `tests/unit/test_p14h_target_years.py`, assignments, and journal entries touched; `git diff --stat` shows `ingestion/claude_extractor.py \| 14 ++++++++++++--` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Derive prompt strings by hand from builder template specifications | `.claude/agents/tester.md` "The hardest rule, and the reason you exist" | No expected value may be obtained by running the code and photographing output. Writing out the literal string derived from the template ensures true independence. |
| Call production functions directly (`_build_financials_prompt`, `_build_nri_prompt`, `_pass1_prompt_pair`, `_pass2_prompt_pair`, `pass1_prompts`, `pass2_prompts`, `cmd_prompt`) | Assignment "What to do" item 2 & backlog item 148 | Ensures tests execute the real production code rather than mock stubs or isolated duplicates. |
| Test empty tuple `target_years=()` via `FilingPlan` in `pass1_prompts` and `pass2_prompts` | Rule 3 propagation through caller interfaces | Proves that the Rule 3 stop in the low-level builder protects high-level callers through `_plan_target_years`. |
| Verify all six real prompt hashes in `extractions/WMT.json` directly | Assignment Criterion 4 | Ensures that no regression occurred in real filing prompt generation across all passes and filings. |
| Use mutation probe without modifying git working tree | Scope restriction in tester instructions & `.claude/hooks/guard_paths.py` | Tester may not edit implementation files; mutation probe verified that the old logic fails the empty-list assertions while the new code passes. |

## Rule 3 — what stops, and what does not

For every value this unit reads, one row. This is the table the reviewer checks first.

| Value read | If it were missing | Evidence |
|---|---|---|
| `target_years` (`_build_financials_prompt`) | Stops with `ValueError` naming `target_years` when empty list `[]` passed; `None` selects all years | `ingestion/claude_extractor.py:2336-2341`, locked by `test_build_financials_prompt_empty_list_stops_and_names_target_years` |
| `target_years` (`_build_nri_prompt`) | Stops with `ValueError` naming `target_years` when empty list `[]` passed; `None` selects all years | `ingestion/claude_extractor.py:2419-2424`, locked by `test_build_nri_prompt_empty_list_stops_and_names_target_years` |
| `include_bs` (`_build_financials_prompt`) | Non-optional boolean flag defaulting to `True` | `ingestion/claude_extractor.py:2330` |
| `is_summary` (`_build_nri_prompt`) | Required positional `str` argument; missing causes `TypeError` | `ingestion/claude_extractor.py:2412` |

## Measurements

- Suite counts:
  - `main` baseline: 1 failed, 1602 passed
  - Worktree after P14h-target-years-tests:
    * Seed 7: `1 failed, 1625 passed in 31.23s`
    * Seed 1234: `1 failed, 1625 passed in 31.98s`
    * Seed 99: `1 failed, 1625 passed in 32.25s`
  - Failure set across all seeds: `{tests/unit/test_session_extraction_console.py:774}` (item 145 on macOS, identical to `main`).
  - Passed test count increased by 23 (1602 -> 1625).
- Lint: 4 errors, all `BLE001` in pre-existing files (`api/routes_valuation.py:463, 745`, `cli.py:1416`, `tests/test_e2e_all_googl.py:106`); 0 in unit files.
- Types: 2 errors in 2 files (`analysis/projector.py:395`, `api/routes_upload.py:28`); 0 in unit files.
- Rule 3 census: 64 (`grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" --include="*.py" models analysis api ingestion pipeline.py | wc -l`).
- Prompt hashes:
  - filing 0 pass 1: `cbf26b0a876034f6`
  - filing 0 pass 2: `024bd96701e72481`
  - filing 1 pass 1: `c401b7bb3096592c`
  - filing 1 pass 2: `9391f61bfa21ac43`
  - filing 2 pass 1: `4aa84c989703f3ce`
  - filing 2 pass 2: `cc61ac590ca169f0`

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `test_no_truthiness_test_of_target_years_in_source`: `assert "if target_years:" not in content` | `True` | Criterion 1 requirement: truthiness check removed from source |
| `test_build_financials_prompt_empty_list_stops_and_names_target_years`: `pytest.raises(ValueError)` | `ValueError` | Rule 3 stop requirement on missing/empty input |
| `test_build_financials_prompt_empty_list_stops_and_names_target_years`: `assert "target_years" in msg` | `True` | Rule 3 names missing parameter |
| `test_build_financials_prompt_empty_list_stops_and_names_target_years`: `assert msg == EXPECTED_EMPTY_YEARS_MESSAGE` | `"target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year."` | Exact diagnostic message required by assignment |
| `test_build_financials_prompt_empty_list_stops_with_include_bs_false`: `pytest.raises(ValueError)` | `ValueError` | Rule 3 stop with `include_bs=False` |
| `test_build_financials_prompt_empty_list_stops_with_include_bs_false`: `assert msg == EXPECTED_EMPTY_YEARS_MESSAGE` | `"target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year."` | Exact diagnostic message required by assignment |
| `test_pass1_prompt_pair_empty_list_stops`: `pytest.raises(ValueError)` | `ValueError` | Rule 3 propagation through `_pass1_prompt_pair` |
| `test_pass1_prompts_empty_tuple_in_plan_stops`: `pytest.raises(ValueError)` | `ValueError` | Rule 3 propagation through `pass1_prompts` with empty plan target years |
| `test_build_nri_prompt_empty_list_stops_and_names_target_years`: `pytest.raises(ValueError)` | `ValueError` | Rule 3 stop requirement on missing/empty input |
| `test_build_nri_prompt_empty_list_stops_and_names_target_years`: `assert "target_years" in msg` | `True` | Rule 3 names missing parameter |
| `test_build_nri_prompt_empty_list_stops_and_names_target_years`: `assert msg == EXPECTED_EMPTY_YEARS_MESSAGE` | `"target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year."` | Exact diagnostic message required by assignment |
| `test_pass2_prompt_pair_empty_list_stops`: `pytest.raises(ValueError)` | `ValueError` | Rule 3 propagation through `_pass2_prompt_pair` |
| `test_pass2_prompts_empty_tuple_in_plan_stops`: `pytest.raises(ValueError)` | `ValueError` | Rule 3 propagation through `pass2_prompts` with empty plan target years |
| `test_build_financials_prompt_none_bs_true_matches_hand_derived`: `assert actual == EXPECTED_PASS1_NONE_BS_TRUE` | Hand-derived literal template string for Pass 1 (`target_years=None`, `include_bs=True`) | Template formula derivation: header + all-years instruction + balance sheet instruction |
| `test_build_financials_prompt_none_bs_false_matches_hand_derived`: `assert actual == EXPECTED_PASS1_NONE_BS_FALSE` | Hand-derived literal template string for Pass 1 (`target_years=None`, `include_bs=False`) | Template formula derivation: header + all-years instruction + no-balance sheet instruction |
| `test_build_financials_prompt_single_year_bs_true_matches_hand_derived`: `assert actual == EXPECTED_PASS1_2024_BS_TRUE` | Hand-derived literal template string for Pass 1 (`target_years=[2024]`, `include_bs=True`) | Template formula derivation: header + "2024 ONLY" + balance sheet instruction |
| `test_build_financials_prompt_single_year_bs_false_matches_hand_derived`: `assert actual == EXPECTED_PASS1_2024_BS_FALSE` | Hand-derived literal template string for Pass 1 (`target_years=[2024]`, `include_bs=False`) | Template formula derivation: header + "2024 ONLY" + no-balance sheet instruction |
| `test_build_financials_prompt_multi_year_sorted_matches_hand_derived`: `assert actual == EXPECTED_PASS1_MULTI_BS_TRUE` | Hand-derived literal template string for Pass 1 (`target_years=[2025, 2023]`, `include_bs=True`) | Template formula derivation: sorted year list "2023, 2025 ONLY" |
| `test_build_nri_prompt_none_matches_hand_derived`: `assert actual == EXPECTED_PASS2_NONE` | Hand-derived literal template string for Pass 2 (`target_years=None`) | Template formula derivation: all-years instruction + summary block |
| `test_build_nri_prompt_single_year_matches_hand_derived`: `assert actual == EXPECTED_PASS2_2024` | Hand-derived literal template string for Pass 2 (`target_years=[2024]`) | Template formula derivation: "2024." instruction + summary block |
| `test_build_nri_prompt_multi_year_sorted_matches_hand_derived`: `assert actual == EXPECTED_PASS2_MULTI` | Hand-derived literal template string for Pass 2 (`target_years=[2025, 2023]`) | Template formula derivation: sorted year list "2023, 2025." instruction + summary block |
| `test_prompt_pair_assembly_closed_form_identity`: Pass 1 system prompt identity | `assert p1_sys == _FINANCIALS_SYSTEM_PROMPT` | Closed-form identity: `_pass1_prompt_pair` returns `(_FINANCIALS_SYSTEM_PROMPT, _build_financials_prompt)` |
| `test_prompt_pair_assembly_closed_form_identity`: Pass 1 user prompt identity | `assert p1_user == EXPECTED_PASS1_NONE_BS_TRUE` | Closed-form identity with hand-derived expected text |
| `test_prompt_pair_assembly_closed_form_identity`: Pass 2 system prompt identity | `assert p2_sys == _NRI_SYSTEM_PROMPT` | Closed-form identity: `_pass2_prompt_pair` returns `(_NRI_SYSTEM_PROMPT, _build_nri_prompt)` |
| `test_prompt_pair_assembly_closed_form_identity`: Pass 2 user prompt identity | `assert p2_user == expected_p2_user` | Closed-form identity with user prompt from `_build_nri_prompt` |
| `test_real_prompt_hash_invariance` (6 cases): exit code | `exit_code == 0` | CLI contract |
| `test_real_prompt_hash_invariance` (6 cases): filing 0 pass 1 | `cbf26b0a876034f6` | Baseline hash recorded in `P14h-target-years.md` |
| `test_real_prompt_hash_invariance` (6 cases): filing 0 pass 2 | `024bd96701e72481` | Baseline hash recorded in `P14h-target-years.md` |
| `test_real_prompt_hash_invariance` (6 cases): filing 1 pass 1 | `c401b7bb3096592c` | Baseline hash recorded in `P14h-target-years.md` |
| `test_real_prompt_hash_invariance` (6 cases): filing 1 pass 2 | `9391f61bfa21ac43` | Baseline hash recorded in `P14h-target-years.md` |
| `test_real_prompt_hash_invariance` (6 cases): filing 2 pass 1 | `4aa84c989703f3ce` | Baseline hash recorded in `P14h-target-years.md` |
| `test_real_prompt_hash_invariance` (6 cases): filing 2 pass 2 | `cc61ac590ca169f0` | Baseline hash recorded in `P14h-target-years.md` |

**Accuracy count:** 35 / 35 assertions matching (100% accuracy).
**Coverage count:**
- Functions touched by unit: 2 functions (`_build_financials_prompt`, `_build_nri_prompt`). Coverage: 2/2 functions (100%).
- Branches touched by unit: 4 decision points (8 branch outcomes: both `is not None` outcomes and both empty check outcomes in each function). Coverage: 8/8 branch outcomes (100%).

## What I did not do

- Did not edit `ingestion/claude_extractor.py` or any implementation file (enforced by role permissions and scope).
- Did not edit `STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md`, or `docs/9-reference/refactor-backlog.md` (reserved for orchestrator / overall lead).
- Did not touch any out-of-scope backlog items (items 10, 51, 61, 63, 64, 73, 74, 78, 79, 80, 84, 85, 119, 120, 121, 122, 138, 145).

## Findings for the orchestrator

None. Backlog item 133 is fully verified, passes all done-criteria, and is protected by tests calling production code directly.
