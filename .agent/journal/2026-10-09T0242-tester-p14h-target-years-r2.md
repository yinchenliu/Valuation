---
agent: tester
assignment: P14h-target-years-tests
round: 2
status: complete
files_touched: [tests/unit/test_p14h_target_years.py, .agent/journal/2026-10-09T0242-tester-p14h-target-years-r2.md]
verdict: pass
---

# P14h-target-years-tests — Round 2 rework for item 133

## What I did

Addressed review findings F1 and F2 from the overall lead review of P14h-target-years:
- **Finding F1 (major):** In `tests/unit/test_p14h_target_years.py`, deleted `test_real_prompt_hash_invariance`, `WMT_BASELINE_HASHES`, and the imports only they used (`contextlib`, `hashlib`, `io`, and `cmd_prompt`). Recorded the six WMT extraction prompt SHA256 hashes directly in this journal entry as the Criterion 4 measurement.
- **Finding F2 (minor):** In `tests/unit/test_p14h_target_years.py`, anchored `test_no_truthiness_test_of_target_years_in_source` to `Path(__file__).resolve().parents[2] / "ingestion" / "claude_extractor.py"` so that it resolves correctly regardless of pytest invocation working directory (verified passing when invoked from `/tmp`).

Re-ran the 17 unit tests, verified mutation kill against `main`'s `ingestion/claude_extractor.py` (8 failed, 9 passed under the mutant; 17 passed on production), measured branch and statement coverage (100% of both builders), and ran the full gate at seeds 7, 1234, and 99 (1 failed, 1619 passed across all three seeds; failure set identical to `main`). Lint, types, and Rule 3 census remain clean and identical to baseline.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | no truthiness test of `target_years` is left in the two builders | pass | `grep -n "if target_years:" ingestion/claude_extractor.py` returned exit code 1 with 0 matches; anchored test `test_no_truthiness_test_of_target_years_in_source` passed |
| 2 | an empty list stops Pass 1 | pass | `_build_financials_prompt([])` raises `ValueError: target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year.` (names `target_years`); locked by `test_build_financials_prompt_empty_list_stops_and_names_target_years`, `test_build_financials_prompt_empty_list_stops_with_include_bs_false`, `test_pass1_prompt_pair_empty_list_stops`, and `test_pass1_prompts_empty_tuple_in_plan_stops` |
| 3 | an empty list stops Pass 2 | pass | `_build_nri_prompt("...", [])` raises `ValueError: target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year.` (names `target_years`); locked by `test_build_nri_prompt_empty_list_stops_and_names_target_years`, `test_pass2_prompt_pair_empty_list_stops`, and `test_pass2_prompts_empty_tuple_in_plan_stops` |
| 4 | the six real prompts are unchanged | pass | Measured via CLI prompt command with path normalization across all 3 filings and both passes: f0p1 `cbf26b0a876034f6`, f0p2 `024bd96701e72481`, f1p1 `c401b7bb3096592c`, f1p2 `9391f61bfa21ac43`, f2p1 `4aa84c989703f3ce`, f2p2 `cc61ac590ca169f0` (all 6 match baseline) |
| 5 | `None` and a one-element list build the same text as on `main` | pass | Asserted against literal hand-derived text in `test_build_financials_prompt_none_bs_true_matches_hand_derived`, `test_build_financials_prompt_none_bs_false_matches_hand_derived`, `test_build_financials_prompt_single_year_bs_true_matches_hand_derived`, `test_build_financials_prompt_single_year_bs_false_matches_hand_derived`, `test_build_financials_prompt_multi_year_sorted_matches_hand_derived`, `test_build_nri_prompt_none_matches_hand_derived`, `test_build_nri_prompt_single_year_matches_hand_derived`, `test_build_nri_prompt_multi_year_sorted_matches_hand_derived`, and `test_prompt_pair_assembly_closed_form_identity` |
| 6 | the tests in 2 and 3 kill the old code | pass | Tested against `main`'s `claude_extractor.py` in temporary worktree: 8 failed (7 stop tests + 1 source check), 9 passed (DID NOT RAISE ValueError); on production codebase all 17 tests pass |
| 7 | the gate form at three orders | pass | Full gate runs: seed 7 (`1 failed, 1619 passed in 32.63s`), seed 1234 (`1 failed, 1619 passed in 33.54s`), seed 99 (`1 failed, 1619 passed in 33.99s`). Failure set equals `main`'s: `{tests/unit/test_session_extraction_console.py:774}` (item 145 on macOS). Passed count increased by 17 from 1602 to 1619 |
| 8 | lint, types, census unchanged | pass | `ruff check .` reported 4 errors (all `BLE001`, 0 in unit files); `mypy` reported 2 errors in 2 files (0 in unit files); Rule 3 census is 64 |
| 9 | the unit stayed in scope | pass | Only `tests/unit/test_p14h_target_years.py` modified in this rework; git status clean outside untracked journal entries |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Remove `test_real_prompt_hash_invariance` and `WMT_BASELINE_HASHES` from test suite | Finding F1 & `docs/5-testing/strategy.md` section 1 ("Every test holds on both machines") | The hash test had path separator differences on Windows and froze a photograph of code output. The 8 literal template tests already lock the text readably and portably. Criterion 4 is recorded as a one-time verification measurement in this journal. |
| Anchor `test_no_truthiness_test_of_target_years_in_source` using `Path(__file__).resolve().parents[2]` | Finding F2 | Resolving relative to `__file__` makes the test independent of cwd, preventing test failures when pytest is invoked from arbitrary locations such as `/tmp`. |

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
  - Worktree after P14h-target-years-tests round 2:
    * Seed 7: `1 failed, 1619 passed in 32.63s`
    * Seed 1234: `1 failed, 1619 passed in 33.54s`
    * Seed 99: `1 failed, 1619 passed in 33.99s`
  - Failure set across all seeds: `{tests/unit/test_session_extraction_console.py:774}` (item 145 on macOS, identical to `main`).
  - Passed test count increased by 17 (1602 -> 1619).
- Lint: 4 errors, all `BLE001` in pre-existing files (`api/routes_valuation.py:463, 745`, `cli.py:1416`, `tests/test_e2e_all_googl.py:106`); 0 in unit files.
- Types: 2 errors in 2 files (`analysis/projector.py:395`, `api/routes_upload.py:28`); 0 in unit files.
- Rule 3 census: 64 (`grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" --include="*.py" models analysis api ingestion pipeline.py | wc -l`).
- Criterion 4 measurement (six real prompt hashes on `extractions/WMT.json`):
  Command:
  ```bash
  for f in 0 1 2; do
    for p in 1 2; do
      h=$(ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m ingestion.session_extraction prompt extractions/WMT.json --filing $f --pass $p 2>&1 | sed "s#$PWD/#<REPO>/#g" | shasum -a 256 | cut -c1-16)
      echo "filing $f pass $p: $h"
    done
  done
  ```
  Measured hashes:
  - filing 0 pass 1: `cbf26b0a876034f6`
  - filing 0 pass 2: `024bd96701e72481`
  - filing 1 pass 1: `c401b7bb3096592c`
  - filing 1 pass 2: `9391f61bfa21ac43`
  - filing 2 pass 1: `4aa84c989703f3ce`
  - filing 2 pass 2: `cc61ac590ca169f0`
  All six hashes match the baseline table in `P14h-target-years.md` byte for byte.

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

**Accuracy count:** 29 / 29 assertions matching (100% accuracy).
**Coverage count:**
- Functions in scope: 2 functions (`_build_financials_prompt`, `_build_nri_prompt`). Statement coverage: 19 / 19 statements (100%).
- Branches in scope: 10 / 10 branch outcomes (100%):
  * `_build_financials_prompt`: 6 of 6 branches (target_years None / not None, target_years empty / non-empty, include_bs True / False).
  * `_build_nri_prompt`: 4 of 4 branches (target_years None / not None, target_years empty / non-empty).

## What I did not do

- Did not edit `ingestion/claude_extractor.py` or any implementation file (enforced by role permissions and scope).
- Did not edit `STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md`, or `docs/9-reference/refactor-backlog.md` (reserved for orchestrator / overall lead).
- Did not touch any out-of-scope backlog items.

## Findings for the orchestrator

None. Findings F1 and F2 from round 1 overall lead review are completely resolved.
