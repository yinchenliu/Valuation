---
agent: tester
assignment: P15a-two-routes-tests
round: 2
status: complete
files_touched:
  - tests/conftest.py
  - .agent/journal/2026-10-04T1956-tester-p15a-two-routes-r2.md
verdict: pass
---

# P15a-two-routes-tests round 2 — Autouse empty-key fixture in tests/conftest.py and gate verification

## What I did

Addressed the Round 2 amendment (F1 from overall lead review) for `P15a-two-routes-tests`:
1. Created `tests/conftest.py` with an `autouse=True` fixture `isolate_environment_keys` that sets both `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` to `""` for every test using `monkeypatch.setenv`. This guarantees no test reads a live API key from `.env` or the host environment; any test needing a key sets a placeholder itself.
2. Verified that the test gate (`--ignore-glob="*_rule3_red.py"`) passes identically (1032 passed, 0 failed) with and without the empty-key prefix (`ANTHROPIC_API_KEY= GEMINI_API_KEY=`).
3. Verified that the full test suite (`pytest -q`) produces exactly 2 failures (the two pre-existing deliberately red tests) and 1032 passed tests under both invocations.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | gate form | pass | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`: **1032 passed in 11.09s, 0 failed**. |
| 2 | full suite | pass | `.venv/bin/python -m pytest -q`: **2 failed, 1032 passed in 11.23s** (only `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`). |
| 3 | no assertion weakened | pass | `git diff tests/` shows 0 modifications to existing tests; only new `tests/conftest.py` added. |
| 4 | new tests can fail | pass | Mutation testing in a scratch copy turned tests red: (1) token mismatch in `test_resolve_provider_claude` failed (exit code 1); (2) transport mismatch in `test_resolve_provider_gemini` failed (exit code 1); (3) mutant conftest injecting non-empty key caused missing-key stop test to fail (exit code 1). |
| 5 | lint | pass | `.venv/bin/python -m ruff check .`: 4 errors (exact baseline: `BLE001` in `api/routes_valuation.py:445,729`, `cli.py:1168`, `tests/test_e2e_all_googl.py:106`), **0 errors in `tests/`** and `tests/conftest.py`. |
| 6 | mypy | pass | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports`: **8 errors in 3 files**, **0 in `tests/`**. `mypy tests/conftest.py` reports success (0 issues). |
| 7 | two counts | pass | Accuracy = 46/46 new assertions match (100%); 1032 passed test cases suite-wide. Coverage = 100% config, 100% analysis, 99% models, 92% claude_extractor (uncovered lines are live network in `_call_gemini`, strictly blocked from tests). |

## Round 2 amendment criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| R2.1 | `tests/conftest.py` autouse fixture sets `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` to `""` | pass | `tests/conftest.py` defines `isolate_environment_keys` with `autouse=True` setting both variables to `""` via `monkeypatch`. |
| R2.2 | Gate with empty keys: 1032 passed, 0 failed | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`: **1032 passed in 11.04s, 0 failed**. |
| R2.3 | Gate without empty keys: 1032 passed, 0 failed | pass | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`: **1032 passed in 11.09s, 0 failed**. |
| R2.4 | Full suite under both invocations: exactly 2 failed (known red), 1032 passed | pass | With empty keys: `2 failed, 1032 passed in 11.29s`. Without empty keys: `2 failed, 1032 passed in 11.23s`. Identical results. |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Create `tests/conftest.py` with autouse fixture | Round 2 amendment F1; build lead instruction | Automatically isolates every test across the entire suite from host `.env` credentials, avoiding manual `monkeypatch` boilerplate in dozens of test modules. |
| Use `monkeypatch.setenv(..., "")` rather than `delenv` | Assignment instruction: "sets ANTHROPIC_API_KEY and GEMINI_API_KEY to ''" | Empty string represents the explicit "off-switch" per `P13c-env-override` contract, preventing `.env` fallback. |
| Keep `test_p15a_two_routes.py` unchanged | Preserves verified 1032 passing tests baseline | Test cases already rigorously cover all provider resolution, CLI, import, and route behaviors without count drift. |

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

| Metric | Baseline | Round 2 (with empty keys) | Round 2 (without empty keys) |
|---|---|---|---|
| Gate form (`--ignore-glob="*_rule3_red.py"`) | 1021 passed, 0 failed | **1032 passed, 0 failed** | **1032 passed, 0 failed** |
| Full suite (`pytest -q`) | 2 failed, 1021 passed | **2 failed, 1032 passed** | **2 failed, 1032 passed** |
| Ruff errors | 4 (`BLE001`) | 4 (`BLE001`), 0 in `tests/` | 4 (`BLE001`), 0 in `tests/` |
| Mypy errors | 8 errors in 3 files | 8 errors in 3 files, 0 in `tests/` | 8 errors in 3 files, 0 in `tests/` |
| Rule 3 census | 65 | 65 | 65 |
| Write guard | 48/48 | 48/48 | 48/48 |
| Route `GET /` | 200 | 200 | 200 |

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
- Real API calls and network calls were not made (`GEMINI_API_KEY=""` default isolation and in-memory stubs throughout).
- Deliberately did not modify the 2 known red tests (`test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`).
- Did not touch `STATUS.md` or `.agent/journal/INDEX.md` (reserved for orchestrator).

## Findings for the orchestrator

- None. Finding F1 from the overall lead review of `P15a-two-routes` is completely resolved and verified.
- The test suite gate passes 1032 tests (0 failed) both with and without the empty-key prefix (`ANTHROPIC_API_KEY= GEMINI_API_KEY=`). The full suite gives exactly the 2 known deliberately red tests and 1032 passed tests under both invocations.
- Verdict is `pass`.
