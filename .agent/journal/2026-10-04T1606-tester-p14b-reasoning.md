---
agent: tester
assignment: P14b-reasoning-tests
round: 1
status: complete
files_touched:
  - tests/unit/test_claude_extractor.py
  - tests/unit/test_page_check.py
  - tests/unit/test_pass1_printed_lines.py
  - tests/unit/test_session_extraction.py
  - tests/unit/test_p14b_reasoning.py
verdict: pass
---

# P14b-reasoning-tests — Repair fixtures for ProviderResolution reasoning_label, lock streaming adaptive thinking and item 81 fix

## What I did

Repaired test fixtures across 4 test files failing during collection due to required `reasoning_label` on `ProviderResolution` (`test_claude_extractor.py:628`, `test_page_check.py:735`, `test_pass1_printed_lines.py:412`, `test_session_extraction.py:265`), strengthened `describe_resolution` assertions in `test_session_extraction.py:839` to lock `Reasoning: <label>` after `Model:`, and authored comprehensive test suite `tests/unit/test_p14b_reasoning.py` (20 new tests, 61 new assertions) verifying:
1. `_call_claude` request parameters: streaming request sends `thinking={"type": "adaptive"}`, `output_config={"effort": config.EXTRACTION_EFFORT}`, `max_tokens=64000` (`_CLAUDE_MAX_TOKENS`), and no forbidden parameters (`temperature`, `top_p`, `top_k`, `budget_tokens`). Embeds PDF bytes as document content block.
2. `_call_claude` response handling: extracts text blocks only; thinking blocks (`type == "thinking"`) are never read or returned; multiple text blocks are newline-joined. Stops with `ValueError` naming missing text block when response contains none; stops with `ValueError` naming 64,000-token output ceiling when `stop_reason == "max_tokens"`.
3. `reasoning_label` and `describe_resolution`: locked labels across Route A Claude direct (`adaptive thinking, effort 'high' (config.EXTRACTION_EFFORT)`), Route A Claude Foundry, Route A Gemini (`the provider's default; this code sets no thinking for Gemini`), and Route B session (`as the Claude Code session ran; not set by this code`). Confirmed `describe_resolution` outputs `Reasoning: <label>` directly after `Model: <model>`. Locked constructor `TypeError` stop on missing `reasoning_label`.
4. Item 81 fix in `_pass2_item_failures`: direct per-item tracking (`item_failed` boolean), preventing substring/prefix description collision, summary counts (`4 checked, 3 found, 1 not confirmed`), and deduplicating multiple check failures for a single item.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | gate form | pass | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` -> 1021 passed, 0 failed in 8.60s |
| 2 | full suite | pass | `.venv/bin/python -m pytest -q` -> 1021 passed, exactly 2 failures: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` in 8.73s |
| 3 | no assertion weakened | pass | `git diff tests/` shows only `reasoning_label` added to 4 `ProviderResolution` instantiations and 2 assertions added to `test_session_extraction.py`; no existing numerical assertion was removed, loosened, or weakened |
| 4 | new tests can fail | pass | Verified in `/tmp/mutant_p14b` with 4 mutants:<br>1) `thinking={"type": "disabled"}` -> exit 1 (`test_call_claude_sends_adaptive_thinking_effort_and_max_tokens` red)<br>2) `_CLAUDE_MAX_TOKENS = 32000` -> exit 1 (`test_call_claude_sends_adaptive_thinking_effort_and_max_tokens` red)<br>3) `item_failed = False` -> exit 1 (5 tests red)<br>4) Reverting to old bug 81 substring matching -> exit 1 (`test_pass2_item_failures_superstring_item_fails_substring_does_not_corrupt_counts` red) |
| 5 | lint | pass | `.venv/bin/python -m ruff check .` -> 4 errors (exact pre-existing baseline BLE001), 0 in `tests/` |
| 6 | mypy | pass | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` -> 9 errors in 4 files (exact baseline), 0 in `tests/` |
| 7 | two counts | pass | Accuracy: 63/63 assertions in scope match (100%); Coverage: 100% statements/branches in `_call_claude`, 100% in `describe_resolution`, 100% in `_pass2_item_failures` counting; 92% overall repository coverage (2437 statements, 207 missed) |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Use mock classes (`MockClaudeClient`, `MockMessages`, `MockStreamContext`) for `_call_claude` tests | Assignment item 2 & Rule 1 / Rule 6; tester strategy: no network, no paid API calls | Avoids any network or real API call while exercising the real `_call_claude` streaming code path, block parsing, and token counting. |
| Dedicated test suite `tests/unit/test_p14b_reasoning.py` for new P14b tests | Assignment scope; clean isolation of reasoning settings, streaming behavior, and item 81 tests | Keeps `test_p14b_units.py` focused on unit scaling (item 77) and provides a clean test module for adaptive thinking and item 81. |
| Populate `_NRI_RESOLUTION` and test `_RESOLUTION` with `reasoning_label="adaptive thinking, effort 'high' (config.EXTRACTION_EFFORT)"` | `ProviderResolution` dataclass has no default (Rule 3) | Matches Route A Claude label contract without hardcoding arbitrary strings. |
| Test item 81 with prefix and superstring description pairs (`"Restructuring"` vs `"Restructuring charges"`) | Backlog item 81 root cause was substring matching item descriptions in check failure messages | Directly tests the exact collision pattern that corrupted counts before the fix. |

## Rule 3 — what stops, and what does not

For every value this unit reads, one row. This is the table the reviewer checks first.

| Value read | If it were missing | Evidence |
|---|---|---|
| `ProviderResolution.reasoning_label` in constructor | stops with `TypeError` naming `reasoning_label` (no default) | `ingestion/claude_extractor.py:151`, `tests/unit/test_p14b_reasoning.py:test_provider_resolution_requires_reasoning_label_no_default` |
| Text block in Claude stream response | stops with `ValueError` naming model, missing text block, and block types received | `ingestion/claude_extractor.py:1860-1863`, `tests/unit/test_p14b_reasoning.py:test_call_claude_stops_when_no_text_block_in_response` |
| Claude stream response hitting token limit (`stop_reason == "max_tokens"`) | stops with `ValueError` naming model, 64,000 ceiling, and remedy | `ingestion/claude_extractor.py:1868-1873`, `tests/unit/test_p14b_reasoning.py:test_call_claude_stops_when_hit_max_tokens_ceiling` |
| Pass 2 item amount absent on cited page | stops with `_CheckFailure` naming non-recurring item, year, description, amount, and page | `ingestion/claude_extractor.py:1625-1634`, `tests/unit/test_p14b_reasoning.py:test_pass2_item_failures_prefix_item_fails_substring_does_not_corrupt_counts` |
| Pass 2 item cited page > PDF page count | stops with `_CheckFailure` naming page and PDF page count | `ingestion/claude_extractor.py:1598-1608`, `tests/unit/test_p14b_reasoning.py:test_pass2_item_failures_single_item_multiple_failures_counted_once` |
| Pass 2 item units cited page > PDF page count | stops with `_CheckFailure` naming units page and PDF page count | `ingestion/claude_extractor.py:1637-1647`, `tests/unit/test_p14b_reasoning.py:test_pass2_item_failures_single_item_multiple_failures_counted_once` |

## Measurements

- Test suite before repairs:
  - 4 collection errors: `test_claude_extractor.py`, `test_page_check.py`, `test_pass1_printed_lines.py`, `test_session_extraction.py` due to `TypeError: ProviderResolution.__init__() missing 1 required positional argument: 'reasoning_label'`.
- Test suite after repairs and new tests:
  - Gate form: 1021 passed, 0 failed in 8.60s (`.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`).
  - Full suite: 1021 passed, 2 failed in 8.73s (`.venv/bin/python -m pytest -q`). The 2 failures are the expected red-on-purpose tests:
    1) `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`
    2) `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`
- Lint: `ruff check .` -> 4 errors (exact baseline BLE001 in `api/routes_valuation.py:445`, `api/routes_valuation.py:729`, `cli.py:1165`, `tests/test_e2e_all_googl.py:106`), 0 in `tests/`.
- Types: `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` -> 9 errors in 4 files (exact baseline), 0 in `tests/`.
- Guard: `check_guard.py` -> 48/48 cases correct.
- Census: 65 (exact baseline).

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `_call_claude` request `thinking` | `{"type": "adaptive"}` | Requirement specification; Rule 1 option 0 |
| `_call_claude` request `output_config` | `{"effort": "high"}` | Closed-form identity: `config.EXTRACTION_EFFORT` definition (`"high"`) |
| `_call_claude` request `max_tokens` | `64000` | Module constant `_CLAUDE_MAX_TOKENS = 64000` |
| `_call_claude` forbidden parameters | absent (`temperature`, `top_p`, `top_k`, `budget_tokens`) | Closed-form identity: Anthropic API specification (adaptive thinking forbids custom sampling parameters) |
| `_call_claude` text filtering | `'{"revenue": 5000}'` (excludes secret thinking) | Closed-form identity: only blocks with `type == "text"` are returned; thinking blocks discarded |
| `_call_claude` text joining | `'{"part1": 1}\n{"part2": 2}'` | Hand string concatenation: `'{"part1": 1}' + '\n' + '{"part2": 2}'` |
| `_call_claude` token usage return | `input_tokens=120, output_tokens=45` | Mock input values directly asserted |
| Claude route A reasoning label | `"adaptive thinking, effort 'high' (config.EXTRACTION_EFFORT)"` | Closed-form template: `f"adaptive thinking, effort {config.EXTRACTION_EFFORT!r} (config.EXTRACTION_EFFORT)"` with `config.EXTRACTION_EFFORT = "high"` |
| Gemini route A reasoning label | `"the provider's default; this code sets no thinking for Gemini"` | Specification string constant |
| Route B session reasoning label | `"as the Claude Code session ran; not set by this code"` | Specification string constant |
| `describe_resolution` output order | `Model: <m>  |  Reasoning: <r>  |  Transport:` | Closed-form template order of `describe_resolution` |
| Clean Pass 2 check summary | `"4 checked, 4 found, 0 not confirmed."` | Hand arithmetic: 4 items checked, 0 failures -> 4 - 0 = 4 found, 0 not confirmed |
| Prefix item fails check summary | `"4 checked, 3 found, 1 not confirmed."` | Hand arithmetic: 4 items checked, 1 failing -> 4 - 1 = 3 found, 1 not confirmed |
| Superstring item fails check summary | `"4 checked, 3 found, 1 not confirmed."` | Hand arithmetic: 4 items checked, 1 failing -> 4 - 1 = 3 found, 1 not confirmed |
| Two items fail check summary | `"4 checked, 2 found, 2 not confirmed."` | Hand arithmetic: 4 items checked, 2 failing -> 4 - 2 = 2 found, 2 not confirmed |
| All items fail check summary | `"4 checked, 0 found, 4 not confirmed."` | Hand arithmetic: 4 items checked, 4 failing -> 4 - 4 = 0 found, 4 not confirmed |
| Single item 2 failures check summary | `"1 checked, 0 found, 1 not confirmed."` | Hand arithmetic: 1 item checked, 1 item failing -> 1 - 1 = 0 found, 1 not confirmed (per-item deduplication) |

**Two counts, with their units:**
- **Accuracy**: 63 of 63 assertions match (100% accuracy).
- **Coverage**:
  - `_call_claude`: 100% statement coverage (37/37 statements), 100% branch coverage (6/6 branches).
  - `describe_resolution`: 100% statement coverage (2/2 statements).
  - `_pass2_item_failures`: 100% statement and branch coverage of failure counting and item_failed tracking.
  - Overall repository coverage: 2437 statements, 207 missed (92% coverage across `analysis/`, `models/`, and `ingestion/`).

## What I did not do

- Implementation code was not modified (tester write scope strictly confined to `tests/` and `.agent/journal/`).
- Real API calls or network requests were not made (`ANTHROPIC_API_KEY= GEMINI_API_KEY=` throughout).
- Did not touch `STATUS.md` or `.agent/journal/INDEX.md` (preserved for orchestrator).

## Findings for the orchestrator

None. All 7 done-criteria pass, all existing fixtures are repaired without loosening any assertions, and all P14b reasoning settings, stops, and item 81 counts are locked.
