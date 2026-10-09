---
agent: code_reviewer
assignment: P14h-target-years-tests
round: 2
verdict: approved
---

# Review of P14h-target-years-tests, round 2

Tester entry: `.agent/journal/2026-10-09T0242-tester-p14h-target-years-r2.md`
Test file: `tests/unit/test_p14h_target_years.py`

Every measurement is mine, on macOS with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/bin/python`. No repository file outside `.agent/journal/` was modified.

## The guard checks

Run over the assignment's **Files in scope** (`tests/unit/test_p14h_target_years.py`):

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean — 0 matches across `tests/unit/test_p14h_target_years.py` |
| lookup with a fallback — `.get(k, 0)` | clean — 0 matches across `tests/unit/test_p14h_target_years.py` |
| bare or-default — `or 0.0` | clean — 0 matches across `tests/unit/test_p14h_target_years.py` |
| money field defaulted to zero — `: float = 0.0` | clean — 0 matches across `tests/unit/test_p14h_target_years.py` |
| `**kwargs` on a calculation function | clean — 0 matches across `tests/unit/test_p14h_target_years.py` |
| `getattr(` on a name from outside the file | clean — 0 matches across `tests/unit/test_p14h_target_years.py` |
| dict of functions keyed by data | clean — 0 matches across `tests/unit/test_p14h_target_years.py` |
| model client imported outside `ingestion/` | clean — `tests/unit/test_p14h_target_years.py` imports no model client |

## Test-review mode: T1–T5 questions

| # | Question | Answer | Evidence |
|---|---|---|---|
| T1 | **Does every test call the code it is about?** | Yes | 16 of the 17 tests directly invoke production functions (`_build_financials_prompt`, `_pass1_prompt_pair`, `pass1_prompts`, `_build_nri_prompt`, `_pass2_prompt_pair`, `pass2_prompts`, `_build_is_summary`). 1 test (`test_no_truthiness_test_of_target_years_in_source`) checks source text to verify Criterion 1.<br><br>Mutation run in scratch worktree `/tmp/p14h-mutant`: reverting `ingestion/claude_extractor.py` to `main` (pre-item-133 code with `if target_years:`) caused **8 failed, 9 passed** (7 stop tests and 1 source check failed with `DID NOT RAISE ValueError` and `AssertionError`). Restoring code returned **17 passed**. Scratch worktree removed and pruned cleanly. |
| T2 | **Does every test hold on both machines (macOS, Python 3.11; Windows, Python 3.14)?** | Yes | All assertions compare in-memory string literals, exception types, and error message substrings. No platform-specific path separators, line endings, or interpreter-dependent representations. No `skipif` on Python version. Round 1 findings F1 (path-separator-sensitive hash tests) and F2 (cwd-relative path) are completely fixed. |
| T3 | **Is no fallback asserted?** | Yes | `grep -nE '^\s*assert .*(== *(0(\.0)?\b\|\[\]\|\{\}\|"")\|is None\b)' tests/unit/test_p14h_target_years.py` returned exit code 1 (0 matches). When `target_years=[]` or `plan.target_years=()`, tests assert that a `ValueError` naming `target_years` is raised, never a fallback. When `target_years=None`, `None` is the explicit API contract for "all years" and tests assert exact hand-derived prompt text. |
| T4 | **Is every expected-value source label true?** | Yes | All 29 assertions in the tester's "Expected values" table were verified against `docs/5-testing/strategy.md` section 1. Stop assertions cite Stated requirement (`rules.md` Rule 3 / assignment Criterion 2 & 3). Prompt text assertions cite hand derivations from literal template strings. Prompt pair assembly assertions cite Closed-form identity. No output photographic assertions. |
| T5 | **Is coverage measured, over the files in scope?** | Yes | Re-ran `.venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_p14h_target_years.py --cov=ingestion.claude_extractor --cov-branch --cov-report=term-missing`. Measured coverage of the 2 functions in scope: `_build_financials_prompt` (lines 2328–2357) has 11 of 11 statements (100%) and 6 of 6 branches (100%); `_build_nri_prompt` (lines 2411–2434) has 8 of 8 statements (100%) and 4 of 4 branches (100%). Total: 19 of 19 statements (100%) and 10 of 10 branch outcomes (100%). |

## Rule 3, by reading

For every value the test file reads or constructs:

| Value | Stops and names it? | Evidence |
|---|---|---|
| `target_years=[]` in `_build_financials_prompt` | Stops with `ValueError` naming `target_years` | `test_build_financials_prompt_empty_list_stops_and_names_target_years` (`test_p14h_target_years.py:202-208`) |
| `target_years=[]` with `include_bs=False` in `_build_financials_prompt` | Stops with `ValueError` naming `target_years` | `test_build_financials_prompt_empty_list_stops_with_include_bs_false` (`test_p14h_target_years.py:212-218`) |
| `target_years=[]` in `_pass1_prompt_pair` | Propagates `ValueError` naming `target_years` | `test_pass1_prompt_pair_empty_list_stops` (`test_p14h_target_years.py:222-226`) |
| `plan.target_years=()` in `pass1_prompts` | Propagates `ValueError` naming `target_years` | `test_pass1_prompts_empty_tuple_in_plan_stops` (`test_p14h_target_years.py:236-240`) |
| `target_years=[]` in `_build_nri_prompt` | Stops with `ValueError` naming `target_years` | `test_build_nri_prompt_empty_list_stops_and_names_target_years` (`test_p14h_target_years.py:249-255`) |
| `target_years=[]` in `_pass2_prompt_pair` | Propagates `ValueError` naming `target_years` | `test_pass2_prompt_pair_empty_list_stops` (`test_p14h_target_years.py:260-264`) |
| `plan.target_years=()` in `pass2_prompts` | Propagates `ValueError` naming `target_years` | `test_pass2_prompts_empty_tuple_in_plan_stops` (`test_p14h_target_years.py:275-279`) |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean — minimal fixture values in `_make_minimal_financials` follow millions convention |
| percentages converted at the route boundary, once | clean — no percentage values touched |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean — prompt builders use `if target_years is not None:` and `if not target_years: raise ValueError` |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean — `analysis/` untouched |
| `models/` imports nothing from this repo | clean — `models/` untouched |

## Done-criteria, re-run

| # | Criterion | Tester claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | no truthiness test of `target_years` is left in the two builders | pass | `grep -n "if target_years:" ingestion/claude_extractor.py` exited 1 (0 matches); `test_no_truthiness_test_of_target_years_in_source` passed | yes |
| 2 | an empty list stops Pass 1 | pass | `_build_financials_prompt([])` raises `ValueError` naming `target_years`; 4 tests pass | yes |
| 3 | an empty list stops Pass 2 | pass | `_build_nri_prompt("...", [])` raises `ValueError` naming `target_years`; 3 tests pass | yes |
| 4 | the six real prompts are unchanged | pass | Re-ran prompt extraction command over `extractions/WMT.json`: f0p1 `cbf26b0a876034f6`, f0p2 `024bd96701e72481`, f1p1 `c401b7bb3096592c`, f1p2 `9391f61bfa21ac43`, f2p1 `4aa84c989703f3ce`, f2p2 `cc61ac590ca169f0`. All 6 match baseline byte for byte | yes |
| 5 | `None` and a one-element list build the same text as on `main` | pass | 8 prompt template tests and 1 prompt pair assembly test pass against hand-derived text | yes |
| 6 | the tests in 2 and 3 kill the old code | pass | Tested in scratch worktree `/tmp/p14h-mutant`: 8 failed, 9 passed under mutant; 17 passed after restore | yes |
| 7 | the gate form at three orders | pass | Full gate runs: seed 7 (`1 failed, 1619 passed in 34.29s`), seed 1234 (`1 failed, 1619 passed in 34.51s`), seed 99 (`1 failed, 1619 passed in 34.03s`). Failure set equals `main`'s: `{tests/unit/test_session_extraction_console.py:774}` (item 145 on macOS). Passed test count increased from 1602 to 1619 (+17) | yes |
| 8 | lint, types, census unchanged | pass | `ruff check .` -> 4 errors (all `BLE001`, 0 in unit files); `mypy` -> 2 errors in 2 files (0 in unit files); Rule 3 census is 64 | yes |
| 9 | unit stayed in scope | pass | Only `tests/unit/test_p14h_target_years.py` modified in this rework; git status clean outside journal entries | yes |

## Findings

None.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 8 | `cli.py:1416` (`except Exception:`) | no |
| 21 | `tests/test_e2e_all_googl.py:106` (`except Exception:`) | no |
| 52 | `analysis/projector.py:395` (mypy error) | no |
| 114 | `api/routes_valuation.py:463, 745` (`except Exception:`) | no |
| 145 | `tests/unit/test_session_extraction_console.py:774` | no |

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| F1 | fixed | Deleted fragile `test_real_prompt_hash_invariance`, `WMT_BASELINE_HASHES`, and unused imports (`contextlib`, `hashlib`, `io`, `cmd_prompt`). Criterion 4 verified by CLI prompt command measurement recorded in journal. |
| F2 | fixed | Anchored source check in `test_no_truthiness_test_of_target_years_in_source` via `Path(__file__).resolve().parents[2] / "ingestion" / "claude_extractor.py"`. Verified passing when invoked from `/tmp/p14h-mutant`. |

## Verdict

`approved`

The tester's round 2 rework completely resolves findings F1 and F2 from round 1. In `tests/unit/test_p14h_target_years.py`, the 17 unit tests call production code directly, hold portably across platforms without path-separator dependencies, assert no fallbacks, use truthful source labels for all expected values, and achieve 100% statement and branch coverage across both prompt builders. The mutation test was independently re-executed in a scratch worktree outside the repository and confirmed that 8 tests fail under the pre-item-133 code (`DID NOT RAISE ValueError` and `assert "if target_years:" not in content`). Full suite gates pass at seeds 7, 1234, and 99 with the expected baseline failure set (item 145 on macOS) and 1619 passed tests. Lint, types, and Rule 3 census (64) remain clean. Ready for handoff to overall lead.
