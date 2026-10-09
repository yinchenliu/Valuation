---
agent: tester
assignment: P1h-mac-gate
round: 2
status: complete
files_touched: [tests/unit/test_p1h_mac_gate.py]
verdict: pass
---

# P1h-mac-gate — stream-handler stop names stream class on every Python (round 2)

> Opened before the first command, filled as each result landed.

## What I did

Reworked `tests/unit/test_p1h_mac_gate.py` to resolve finding F1 from the overall lead review.
Deleted the three precondition assertions (`assert "<ClassName>" not in repr(stream)`),
their `# Precondition` comments, and the docstring line regarding Python 3.11 repr behavior.
Retained all hand-derived assertions including `expected_stream_prefix`, which requires
`Stream: <ClassName> ` preceding `repr(stream)`.
Verified that all 3 tests pass on Python 3.11, re-ran the mutation check killing the defect
when the stream class name is removed, and verified all gates across random seeds.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the test that found the defect passes, unchanged | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider "tests/unit/test_session_extraction_console.py::test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream"` -> `1 passed in 0.02s` |
| 2 | that test file did not change | pass | `git diff main -- tests/unit/test_session_extraction_console.py` -> empty diff |
| 3 | the gate form is green at three orders | pass | Seed 7: `1589 passed in 33.64s` (0 failed, 0 skipped); Seed 1234: `1589 passed in 34.42s` (0 failed, 0 skipped); Seed 99: `1589 passed in 34.67s` (0 failed, 0 skipped) |
| 4 | the full suite fails only the two tests that are red on purpose | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider --randomly-seed=7` -> `2 failed, 1589 passed in 34.30s` (failures: `test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_valuation_with_session_file_and_files_on_a_cache_hit_stops`) |
| 5 | lint unchanged | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m ruff check .` -> `Found 4 errors.` (all pre-existing `BLE001`, 0 in unit files) |
| 6 | types unchanged | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` -> `Found 2 errors in 2 files` (pre-existing) |
| 7 | rule 3 census unchanged | pass | `grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" '--include=*.py' models analysis api ingestion pipeline.py | wc -l` -> `64` |
| 8 | the unit stayed in scope | pass | `git diff --name-only main...HEAD` shows only in-scope files; `git status --short` shows only `tests/unit/test_p1h_mac_gate.py` modified and round 2 journal entry added |
| 9 | a test that kills the defect on Python 3.11 | pass | In scratch worktree, removing `{type(stream).__name__} ` from `ingestion/session_extraction.py:1234` caused all 3 new tests and the defect test to fail (`4 failed in 0.05s`, with `AssertionError: assert '<SubclassName>' in ...`). Restoring it resulted in `4 passed in 0.03s`. |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Delete the three `assert "<ClassName>" not in repr(stream)` assertions and comments | Finding F1 in `.agent/assignments/P1h-mac-gate.md` | Precondition asserted CPython 3.11-specific representation behavior, causing test failures on Python 3.14+ |
| Retain `expected_stream_prefix = f"Stream: {ClassName} {stream!r}"` | Finding F1; `docs/5-testing/strategy.md` section 1 | Asserts that `{type(stream).__name__} ` explicitly precedes the stream representation, which kills the mutant on both Python 3.11 and Python 3.14+ |

## Rule 3 — what stops, and what does not

For every value this unit reads, one row.

| Value read | If it were missing | Evidence |
|---|---|---|
| `stream.errors` | stops and names `error handler`, read value (`None`, `42`), and stream class name | `ingestion/session_extraction.py:1223-1234`, verified by `tests/unit/test_p1h_mac_gate.py` |

Stop paths not locked:
None.

## Measurements

- Suite before unit: `1586 passed` (gate form).
- Suite after unit rework: `1589 passed in 33.64s` (gate form, seed 7, 0 failed, 0 skipped).
- Full suite: `2 failed, 1589 passed in 34.30s` (only the two intentional red tests failed).
- Unit tests (`tests/unit/test_p1h_mac_gate.py`): `3 passed in 0.03s`.
- Defect test (`test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream`): `1 passed in 0.02s`.
- Lint: `Found 4 errors.` (all pre-existing BLE001, none in unit files).
- Types: `Found 2 errors in 2 files` (pre-existing, none in unit files).
- Rule 3 census: `64`.
- Mutation kill: 4 of 4 tests killed the mutant on Python 3.11 when class name was removed from message (3 new tests + defect test).

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `exc_info.value` not `ValueError` | True | API contract: `main` catches `ValueError`, so stop must be `TypeError` |
| `"error handler"` in message | True | Stop message template specification for `stream.errors` |
| `"reads as None"` in message | True | Hand derivation: formatted `previous!r` when errors is `None` |
| `"StreamWithNoneErrors"` in message | True | Hand derivation: `{type(stream).__name__}` for `StreamWithNoneErrors` |
| `"Stream: StreamWithNoneErrors " + repr(stream)` in message | True | Hand derivation: `{type(stream).__name__} {stream!r}` formatting |
| `stream.reconfigured_calls == []` | True | Closed-form identity: stream not reconfigured when pre-check raises |
| `exc_info.value` not `ValueError` | True | API contract: stop must be `TypeError` |
| `"error handler"` in message | True | Stop message template specification for `stream.errors` |
| `"reads as 42"` in message | True | Hand derivation: formatted `previous!r` when errors is `42` |
| `"StreamWithIntegerErrors"` in message | True | Hand derivation: `{type(stream).__name__}` for `StreamWithIntegerErrors` |
| `"Stream: StreamWithIntegerErrors " + repr(stream)` in message | True | Hand derivation: `{type(stream).__name__} {stream!r}` formatting |
| `stream.reconfigured_calls == []` | True | Closed-form identity: stream not reconfigured when pre-check raises |
| `"CustomTelemetryTextStream"` in message | True | Hand derivation: `{type(stream).__name__}` for `CustomTelemetryTextStream` |
| `"Stream: CustomTelemetryTextStream " + repr(stream)` in message | True | Hand derivation: `{type(stream).__name__} {stream!r}` formatting |

Counts:
- Accuracy: 14 of 14 assertions match expected values (assertions).
- Coverage: 1 function touched (`naming_unencodable_characters`), specifically branch `not isinstance(previous, str)` -> `raise TypeError(...)`.

## What I did not do

- Did not modify any code in `ingestion/`, `models/`, `analysis/`, or `api/`.
- Did not modify `tests/unit/test_session_extraction_console.py`.
- Did not modify git commit history or handoff sections (reserved for build lead).

## Findings for the orchestrator

None.
