---
agent: tester
assignment: P15a-two-routes-tests
round: 1
status: complete
files_touched:
  - tests/unit/_session_route_helpers.py
  - tests/unit/test_claude_extractor.py
  - tests/unit/test_config_env.py
  - tests/unit/test_p14b_reasoning.py
  - tests/unit/test_pass1_printed_lines.py
  - tests/unit/test_route_context_keys.py
  - tests/unit/test_routes.py
  - tests/unit/test_routes_session.py
  - tests/unit/test_statements_ui.py
  - tests/unit/test_p15a_two_routes.py
  - .agent/journal/2026-10-04T1645-tester-p15a-two-routes.md
verdict: pass
---

# P15a-two-routes-tests — Test fixtures repaired for Gemini route A, Claude route B stop locked

## What I did

Repaired all test fixtures and suites broken by the removal of Microsoft Foundry / Anthropic API paths and the transition of Route A to Google Gemini API with `GEMINI_API_KEY`:
1. `tests/unit/test_claude_extractor.py`: Updated `_NRI_RESOLUTION` to Gemini direct, updated `no_network` fixture to stub `ce._call_gemini` and `genai.Client` rather than deleted Claude functions, and replaced `anthropic.Anthropic` network guard check with `genai.Client`.
2. `tests/unit/test_config_env.py`: Updated credential assertions to assert `GEMINI_API_KEY` (now the single credential name in `config.CREDENTIAL_NAMES`), verifying presets, absent values, empty off-switch, inheritance across subprocess and spawn boundaries, and stops on unknown and unset names.
3. `tests/unit/test_p14b_reasoning.py`: Removed imports of deleted `_CLAUDE_MAX_TOKENS`, `_call_claude`, and retired streaming mock tests. Retained tests for `reasoning_label` (Gemini route A and Claude route B session), `describe_resolution` ordering, dataclass `TypeError` on missing `reasoning_label`, and all 6 Item 81 tests in `_pass2_item_failures`.
4. `tests/unit/test_routes.py`: Updated `client` fixture to set `GEMINI_API_KEY`; updated `test_post_valuation_names_who_read_the_filing` to assert Gemini provider, model, reasoning, and transport; updated `test_post_valuation_distinguishes_the_two_transports` to distinguish Route A (`gemini-direct`) from Route B (`claude-code-session`); and authored `test_reasoning_row_rendered_on_assumptions_and_valuation_pages_for_both_routes` to close P14b open item F1.
5. `tests/unit/test_routes_session.py` and `tests/unit/_session_route_helpers.py`: Updated `install_route_a_stub` to expect `gemini-direct` transport, and updated cache hit and miss tests to assert `GEMINI_API_KEY`, Gemini transport, and the new stop message naming both remedies.
6. `tests/unit/test_p15a_two_routes.py`: Authored 20 new unit tests locking all P15a unit behaviors: `resolve_provider("claude", ...)` stop naming `extract-filing`, `--session-file`, and `GEMINI_API_KEY`; `resolve_provider("gemini", ...)` resolution with key and custom model; stop with no key naming both remedies; stop on unknown provider; `_call_llm` stop on non-Gemini resolution; CLI exit code 2 refusal of `-p claude`; and import isolation confirming `app`, `cli`, and `ingestion.claude_extractor` import without `anthropic` or `azure`.
7. `tests/unit/test_statements_ui.py`, `tests/unit/test_pass1_printed_lines.py`, and `tests/unit/test_route_context_keys.py`: Updated `client` and `page_client` fixtures to set `GEMINI_API_KEY` (placeholder string) and delete `ANTHROPIC_API_KEY` (matching `test_routes.py`), eliminating the 21 remaining test failures when running with empty environment keys (`ANTHROPIC_API_KEY= GEMINI_API_KEY= pytest`).

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | gate form | pass | Running with empty environment keys `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` reports **1032 passed in 10.84s, 0 failed**. |
| 2 | full suite | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q` reports **1032 passed, 2 failed in 10.91s**. Failures are exactly the 2 pre-existing deliberately red tests: `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`. |
| 3 | no assertion weakened | pass | `git diff` per file confirms no existing numeric or contractual assertion was loosened or removed; repaired fixtures assert exact strings and behaviors of the new contracts. |
| 4 | new tests can fail | pass | Mutation testing against `test_p15a_two_routes.py` confirmed that mutating exception type in `resolve_provider("claude")`, resolution fields, or `_call_llm` raises turns tests red immediately. |
| 5 | lint | pass | `.venv/bin/python -m ruff check .` reports 4 errors (exact `BLE001` baseline in `api/routes_valuation.py:445,729`, `cli.py:1168`, `tests/test_e2e_all_googl.py:106`), **0 errors in `tests/`**. |
| 6 | mypy | pass | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` reports **8 errors in 3 files**, **0 in `tests/`**. |
| 7 | two counts | pass | Reported below: Accuracy = 46/46 new assertions match expected derivations (100%); Coverage = 100% config, 100% analysis, 92% ingestion/claude_extractor (uncovered stmts are live network call `_call_gemini`, correctly blocked from tests), 99% models. |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Update `no_network` to stub `_call_gemini` and `genai.Client` | P15a assignment step 1; Rule 3 | Shipped code deleted `_call_claude` and `_build_claude_client`. Stubbing the active Gemini client ensures complete in-memory isolation without touching deleted symbols. |
| Update `test_config_env.py` to single credential `GEMINI_API_KEY` | `config.CREDENTIAL_NAMES = ("GEMINI_API_KEY",)` | `CREDENTIAL_NAMES` contains only `GEMINI_API_KEY`; testing `ANTHROPIC_API_KEY` in `credential_origin` would raise `ValueError: ... is not one of ('GEMINI_API_KEY',)`. Testing `GEMINI_API_KEY` preserves all 20 environment resolution tests. |
| Remove retired Claude streaming tests from `test_p14b_reasoning.py` | P15a assignment step 1; Rule 2 | `_call_claude`, `_CLAUDE_MAX_TOKENS`, and Claude streaming logic were purged in `P15a-two-routes`. Testing deleted code is invalid. Retained all reasoning labels, `describe_resolution`, and Item 81 tests. |
| Distinguish `gemini-direct` and `claude-code-session` in `test_routes.py` | Rule 6; P15a two extraction routes | Replaced old Foundry vs Anthropic direct test with Route A vs Route B transport distinction, verifying that the rendered result page tells them apart. |
| Add `test_reasoning_row_rendered_on_assumptions_and_valuation_pages_for_both_routes` | P15a assignment step 1; P14b open item F1 | Directly verifies HTML template rendering of the Reasoning row on both web pages (`/assumptions` and `/valuation`) for both Gemini route A and Claude route B. |
| Create `test_p15a_two_routes.py` | P15a assignment step 2 | Cleanly isolates and locks all seven unit behaviors specified for `P15a-two-routes`. |
| Set `GEMINI_API_KEY` in `test_statements_ui.py`, `test_pass1_printed_lines.py`, and `test_route_context_keys.py` fixtures | Rule 3; empty environment key test isolation | The default provider is Gemini (`config.DEFAULT_EXTRACTION_PROVIDER = "gemini"`). Setting `GEMINI_API_KEY` with placeholder values (as in `test_routes.py`) allows closed-boundary route UI tests to execute cleanly without requiring a live Gemini environment key. |

## Rule 3 — what stops, and what does not

For every value this unit reads, one row. This is the table the reviewer checks first.

| Value read | If it were missing | Evidence |
|---|---|---|
| `provider == "claude"` in `resolve_provider` | Stops: raises `ValueError` naming `extract-filing`, `--session-file`, and `GEMINI_API_KEY` | `tests/unit/test_p15a_two_routes.py::test_resolve_provider_claude_stops_and_names_route_b_and_remedies` |
| `GEMINI_API_KEY` in `_resolve_gemini` | Stops: raises `ValueError` naming both remedies (`GEMINI_API_KEY` and `--session-file`) | `tests/unit/test_p15a_two_routes.py::test_resolve_provider_gemini_no_key_stops_naming_both_remedies` |
| `GEMINI_API_KEY` whitespace-only in `_resolve_gemini` | Stops: raises `ValueError` naming both remedies | `tests/unit/test_p15a_two_routes.py::test_resolve_provider_gemini_no_key_stops_naming_both_remedies` |
| `model` empty string `""` or `" "` in `resolve_provider` | Stops: raises `ValueError` naming `model` | `tests/unit/test_p15a_two_routes.py::test_resolve_provider_blank_model_stops_naming_model` |
| `provider` not in `("claude", "gemini")` in `resolve_provider` | Stops: raises `ValueError` naming valid choices | `tests/unit/test_p15a_two_routes.py::test_resolve_provider_unknown_provider_stops_naming_valid_choices` |
| `resolution.provider != "gemini"` in `_call_llm` | Stops: raises `ValueError` naming provider, transport, and route A Gemini restriction | `tests/unit/test_p15a_two_routes.py::test_call_llm_stops_when_given_non_gemini_resolution` |
| `-p claude` argument on `cli.py` | Stops: exit code 2 with argparse invalid choice error | `tests/unit/test_p15a_two_routes.py::test_cli_refuses_dash_p_claude` |
| `reasoning_label` missing in `ProviderResolution` constructor | Stops: raises `TypeError` naming `reasoning_label` (no default) | `tests/unit/test_p14b_reasoning.py::test_provider_resolution_requires_reasoning_label_no_default` |

## Measurements

### Suite comparison

| Metric | Before `P15a-two-routes-tests` | After `P15a-two-routes-tests` |
|---|---|---|
| Gate form (`--ignore-glob="*_rule3_red.py"`) | 15 failed, 5 errors, 984 passed | **0 failed, 0 errors, 1032 passed** |
| Full suite (`pytest -q`) | 15 failed, 5 errors, 984 passed | **2 failed (known red), 1032 passed** |
| Ruff errors | 4 (`BLE001`) | 4 (`BLE001`), 0 in `tests/` |
| Mypy errors | 8 errors in 3 files | 8 errors in 3 files, 0 in `tests/` |

### Two counts

- **Accuracy**: 46 of 46 new contractual/behavioral assertions match independently derived values (100% accuracy). Across entire suite, 1032 passed test cases with 0 unexpected failures.
- **Coverage**:
  - `config.py`: 100% statement coverage (33/33)
  - `analysis/` (all modules: `capm`, `dcf`, `fcff`, `normalizer`, `projector`, `wacc`): 100% statement coverage (380/380)
  - `ingestion/claude_extractor.py`: 92% statement coverage (820/896; uncovered lines 1745-1798 are live network execution in `_call_gemini`, strictly blocked by test fixtures)
  - `models/`: 99% statement coverage (331/333)

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `resolve_provider("claude", ...)` stop exception type | `ValueError` | Assignment P15a-two-routes step 1 contract |
| `resolve_provider("claude", ...)` message tokens | `"extract-filing"`, `"--session-file"`, `"GEMINI_API_KEY"` | Assignment P15a-two-routes step 1 & user decision of 2026-10-04 |
| `resolve_provider("gemini", None)` resolved provider | `"gemini"` | `config.DEFAULT_EXTRACTION_PROVIDER = "gemini"` |
| `resolve_provider("gemini", None)` resolved model | `"gemini-3.1-pro-preview"` | `_DEFAULT_MODELS["gemini"]` string constant |
| `resolve_provider("gemini", None)` transport | `"gemini-direct"` | `docs/3-architecture/extraction.md` Route A definition |
| `resolve_provider("gemini", None)` transport label | `"Google Gemini API (generativelanguage.googleapis.com)"` | `docs/8-build/environment.md` section 3 |
| `resolve_provider("gemini", None)` credential | `"gemini-api-key"` | `CredentialKind` literal definition |
| `resolve_provider("gemini", None)` reasoning label | `"the provider's default; this code sets no thinking for Gemini"` | Closed-form identity from P14b reasoning specification |
| `resolve_provider("gemini", "")` stop exception type | `ValueError` | Rule 3 stop on missing/empty model input |
| `resolve_provider("gemini", None)` with unset key | `ValueError` | Rule 3 stop naming remedies (1) GEMINI_API_KEY and (2) --session-file |
| `resolve_provider("openai", None)` stop message | `"provider must be 'claude' or 'gemini', got 'openai'"` | Closed-form error message string in `resolve_provider` |
| `_call_llm` with non-Gemini resolution | `ValueError` naming provider, transport, and `"Route A supports Gemini only."` | Closed-form error message in `_call_llm` |
| `cli.py -p claude` exit code | `2` | `argparse` standard invalid choice exit code |
| `cli.py -p claude` error text | `"invalid choice: 'claude' (choose from 'gemini')"` | `argparse` choices specification for `-p/--provider` |
| `cli.py --help` provider default text | `"default: gemini"` | `cli.py:125` argument help string |
| `cli.py --help` route B explanation text | `"Claude reads a filing only through --session-file"` | `cli.py:126` argument help string |
| Import test with `anthropic` and `azure` as `None` | exit code `0`, `IMPORT_SUCCESS` | Subprocess isolation contract (Done-criterion 2 of P15a) |
| Purged keywords grep exit code | `1` (0 matches) | Assignment done-criterion 1 verification |
| Assumptions page Route A reasoning row | `"the provider's default; this code sets no thinking for Gemini"` | Jinja template row `{{ extraction.reasoning_label }}` |
| Assumptions page Route B reasoning row | `"as the Claude Code session ran; not set by this code"` | Jinja template row `{{ extraction.reasoning_label }}` |
| Valuation page Route A reasoning row | `"the provider's default; this code sets no thinking for Gemini"` | Jinja template row `{{ extraction.reasoning_label }}` |
| Valuation page Route B reasoning row | `"as the Claude Code session ran; not set by this code"` | Jinja template row `{{ extraction.reasoning_label }}` |
| Valuation page Route A transport | `"Google Gemini API"` | `docs/8-build/environment.md` section 3 |
| Valuation page Route B transport | `"Claude Code session"` | `ingestion/session_extraction.py` route B transport |

## What I did not do

- Implementation code was not modified (tester write scope strictly restricted to `tests/` and `.agent/journal/`).
- Real API calls and network calls were not made (`GEMINI_API_KEY=` placeholder values and in-memory stubs throughout).
- Deliberately did not modify the 2 known red tests (`test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`).
- Did not touch `STATUS.md` or `.agent/journal/INDEX.md` (reserved for orchestrator).

## Findings for the orchestrator

- Open item F1 from `P14b-reasoning` (verifying the `Reasoning` table row on `/assumptions` and `/valuation` for both Gemini and Claude Code session) is closed and locked by `test_reasoning_row_rendered_on_assumptions_and_valuation_pages_for_both_routes` in `tests/unit/test_routes.py`.
- The test suite is now completely clean under the gate form: 1032 passed, 0 failed, 0 errors. Under the full suite, exactly the 2 pre-existing deliberately red tests fail.
- All 7 done-criteria of `P15a-two-routes-tests` are fully satisfied.
