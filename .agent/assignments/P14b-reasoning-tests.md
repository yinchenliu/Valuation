---
id: P14b-reasoning-tests
phase: 14 — the Pass 1 role (rule 1 option 0, the user's decision of 2026-10-03)
agent: tester
depends_on: [P14b-reasoning]
---

# Repair test fixtures for ProviderResolution reasoning_label, lock streaming adaptive thinking and item 81 fix

## Objective

`P14b-reasoning` is approved in round 1. Route A sends `thinking={"type": "adaptive"}` and `output_config={"effort": config.EXTRACTION_EFFORT}` through a streamed request (`client.messages.stream(...)` and `get_final_message()`), caps at `_CLAUDE_MAX_TOKENS = 64000`, adds required `reasoning_label: str` to `ProviderResolution` (no default), surfaces it in `describe_resolution` and HTML templates, and fixes item 81 in `_pass2_item_failures`.

4 test files fail at import/collection due to missing `reasoning_label` in `ProviderResolution` constructor calls:
- `tests/unit/test_claude_extractor.py`
- `tests/unit/test_page_check.py`
- `tests/unit/test_pass1_printed_lines.py`
- `tests/unit/test_session_extraction.py`

Read first:
- `.agent/assignments/P14b-reasoning.md`
- Programmer entry: `.agent/journal/2026-10-04T1548-programmer-p14b-reasoning.md`
- Code reviewer entry: `.agent/journal/2026-10-04T1604-code_reviewer-p14b-reasoning.md`
- `.claude/agents/tester.md`

## What to do

1. **Repair the existing fixtures and ProviderResolution calls:**
   - Add `reasoning_label` to `ProviderResolution` instantiations in test helpers across `tests/unit/`.
   - Update `describe_resolution` test assertions to verify `Reasoning: <label>` appears after `Model:`.
   - If any test stubs `_call_claude`, ensure stub provides `client.messages.stream(...)` with `get_final_message()`.
   - **No existing numerical assertion may change**, unless re-derived by hand in a comment.

2. **Lock `_call_claude` request parameters and stream handling:**
   - Test that requests send `thinking={"type": "adaptive"}`, `output_config={"effort": config.EXTRACTION_EFFORT}`, `max_tokens=64000`.
   - Test that no forbidden parameters (`temperature`, `top_p`, `top_k`, `budget_tokens`) are sent.
   - Test that thinking blocks are never read or returned; only text blocks (`type == "text"`) are returned.
   - Test stops: raises `ValueError` naming missing text block when response contains no text blocks; raises `ValueError` naming 64,000 ceiling when `stop_reason == "max_tokens"`.

3. **Lock `reasoning_label` and `describe_resolution`:**
   - Route A Claude: `f"adaptive thinking, effort {config.EXTRACTION_EFFORT!r} (config.EXTRACTION_EFFORT)"`.
   - Route A Gemini: `"the provider's default; this code sets no thinking for Gemini"`.
   - Route B: `"as the Claude Code session ran; not set by this code"`.
   - Test that `describe_resolution` outputs `Reasoning: <label>` directly following `Model:`.

4. **Lock item 81 fix in `_pass2_item_failures`:**
   - Test that Pass 2 item failure counts are tracked per item directly.
   - Verify that an item whose description is a substring or prefix of another item's description does not corrupt counts.
   - Test summary counts: e.g. 4 items with 1 failing produces `4 checked, 3 found, 1 not confirmed`.

Never make paid API calls or real network calls in tests. All stubs/mocks in memory.

## Files in scope

- `tests/`
- `.agent/journal/<YYYY-MM-DDTHHMM>-tester-p14b-reasoning.md`

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite | exactly 2 failures: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` | `.venv/bin/python -m pytest -q` |
| 3 | no assertion weakened | none removed or loosened in repaired fixtures | `git diff` per file |
| 4 | new tests can fail | mutants in a scratch copy turn tests red | verify with mutants |
| 5 | lint | 4 errors (BLE001 pre-existing), 0 in `tests/` | `.venv/bin/python -m ruff check .` |
| 6 | mypy | 9 errors in 4 files, 0 in `tests/` | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` |
| 7 | two counts | accuracy and coverage reported | tester log entry |
