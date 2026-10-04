---
id: P15a-two-routes-tests
phase: 15 — two extraction routes (the user's decisions of 2026-10-04)
agent: tester
depends_on: [P15a-two-routes]
---

# Repair test fixtures for Gemini default route A, Claude route B stop, and lock two-routes behaviors

## Objective

`P15a-two-routes` is approved in round 1. Route A reads filings through the Gemini API with `GEMINI_API_KEY`, and `gemini` is the default provider (`config.DEFAULT_EXTRACTION_PROVIDER = "gemini"`). Claude is reached only through Claude Code session files (route B). Calling `resolve_provider("claude", ...)` or CLI `-p claude` stops and names route B and remedies. All Microsoft Foundry gateway and Anthropic API paths have been purged from shipped code, and `config.CREDENTIAL_NAMES = ("GEMINI_API_KEY",)`.

20 tests currently fail or error across the suite:
- 4 errors in `tests/unit/test_claude_extractor.py`: fixture `no_network` stubs deleted `_call_claude`.
- 1 collection error in `tests/unit/test_p14b_reasoning.py`: imports deleted `_CLAUDE_MAX_TOKENS`.
- 9 failures in `tests/unit/test_config_env.py`: asserts old `CREDENTIAL_NAMES` (`ANTHROPIC_API_KEY`, `ANTHROPIC_FOUNDRY_API_KEY`).
- 4 failures in route tests (`test_routes.py`, `test_routes_session.py`): asserts old route A Claude / Anthropic messages and transports.
- 2 known deliberately red tests (`test_projector_rule3_red.py`, `test_routes_session_rule3_red.py`).

Read first:
- `.agent/assignments/P15a-two-routes.md`
- Programmer entry: `.agent/journal/2026-10-04T1626-programmer-p15a-two-routes.md`
- Code reviewer entry: `.agent/journal/2026-10-04T1644-code_reviewer-p15a-two-routes.md`
- `.claude/agents/tester.md`

## What to do

1. **Repair the existing fixtures and test suites:**
   - `tests/unit/test_claude_extractor.py`: update `no_network` fixture to stub `_call_gemini` rather than deleted `_call_claude`. Update any tests asserting Claude on route A.
   - `tests/unit/test_config_env.py`: update credential tests to assert `GEMINI_API_KEY` (now the single credential name in `config.CREDENTIAL_NAMES`).
   - `tests/unit/test_p14b_reasoning.py`: remove imports of deleted `_CLAUDE_MAX_TOKENS` and retired Claude streaming tests. Retain tests for `reasoning_label`, `describe_resolution`, and item 81 fix.
   - `tests/unit/test_routes.py` and `tests/unit/test_routes_session.py`: update route A tests to reflect default provider `gemini`, `GEMINI_API_KEY`, and new stop messages.
   - Add test verifying `Reasoning` row on both web pages (`/assumptions` and `/valuation`) with Gemini label and route B label (known open item F1 from P14b-reasoning).
   - **No existing numerical assertion may change**, unless re-derived by hand in a comment.

2. **Lock P15a-two-routes unit behaviors in `tests/unit/test_p15a_two_routes.py`:**
   - Lock `resolve_provider("claude", ...)` stop: assert `ValueError` naming `extract-filing`, `--session-file`, and `GEMINI_API_KEY`.
   - Lock `resolve_provider("gemini", ...)` with key: assert `ProviderResolution(provider='gemini', model='gemini-3.1-pro-preview', transport='gemini-direct', credential='gemini-api-key')`.
   - Lock `resolve_provider("gemini", ...)` with no key: assert `ValueError` naming both remedies (`GEMINI_API_KEY` and `--session-file`).
   - Lock `resolve_provider` with unknown provider: assert `ValueError` naming valid choices.
   - Lock `_call_llm` stop: assert `ValueError` when given non-Gemini resolution.
   - Lock CLI refusal of `-p claude`: assert exit code 2 and invalid choice error message.
   - Lock that `anthropic` and `azure` are not imported by `app`, `cli`, or `ingestion.claude_extractor`.

Never make paid API calls or real network calls in tests. All stubs/mocks in memory.

## Files in scope

- `tests/`
- `.agent/journal/<YYYY-MM-DDTHHMM>-tester-p15a-two-routes.md`

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite | exactly 2 failures: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` | `.venv/bin/python -m pytest -q` |
| 3 | no assertion weakened | none removed or loosened in repaired fixtures | `git diff` per file |
| 4 | new tests can fail | mutants in a scratch copy turn tests red | verify with mutants |
| 5 | lint | 4 errors (BLE001 pre-existing), 0 in `tests/` | `.venv/bin/python -m ruff check .` |
| 6 | mypy | 8 errors in 3 files, 0 in `tests/` | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` |
| 7 | two counts | accuracy and coverage reported | tester log entry |
