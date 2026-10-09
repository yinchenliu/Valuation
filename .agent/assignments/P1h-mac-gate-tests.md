---
id: P1h-mac-gate-tests
phase: 1 — make the suite runnable
agent: tester
depends_on: [P1h-mac-gate]
---

# Verify the stream-handler stop names the stream's class on every Python (item 145)

## Objective

Verify that `naming_unencodable_characters` in `ingestion/session_extraction.py` raises
`TypeError` naming the stream's class explicitly when the stream's `errors` attribute is not
a string (specifically when it is `None`). The test must verify that the stop names the
subclass name on Python 3.11 where `repr(io.TextIOWrapper_subclass)` otherwise omits it,
and must verify mutation kill when `{type(stream).__name__}` is removed from the message.

## What is already true — verify, do not redo

- `tests/unit/test_session_extraction_console.py::test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream`
  passes (`1 passed`).
- The gate form passes at seeds 7, 1234, 99 (`0 failed, 1586 passed, 0 skipped`).
- The programmer modified `ingestion/session_extraction.py:1233-1234` to include
  `{type(stream).__name__}`.

## What to do

1. Create a new test file `tests/unit/test_p1h_mac_gate.py`.
2. Write tests covering `naming_unencodable_characters` when `errors` is not a string
   (e.g., `None`), testing against custom `io.TextIOWrapper` subclasses to ensure the
   subclass name appears in the raised `TypeError` message.
3. Test independent expected strings derived by hand (not copied from code output).
4. Perform a mutation check: verify that your new test fails if the explicit
   `{type(stream).__name__}` is removed from the `TypeError` message in
   `ingestion/session_extraction.py`, and passes when restored.
   (Do not leave the mutation in the file; restore the file immediately after measuring.)
5. Report accuracy and coverage counts.
6. Write your journal entry to `.agent/journal/<YYYY-MM-DDTHHMM>-tester-p1h-mac-gate.md`.

## Files in scope

- `tests/unit/test_p1h_mac_gate.py` (new test file)

**Nothing else.** You may not modify implementation code (`ingestion/session_extraction.py`
is strictly read-only, except during your temporary mutation check which must be reverted).

## Out of scope

- `tests/unit/test_session_extraction_console.py`: do not modify.
- `ingestion/`: implementation code is owned by the programmer.
- The four record files (`STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md`,
  `docs/9-reference/refactor-backlog.md`).

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | new test file exists and passes | `pass` | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_p1h_mac_gate.py` |
| 2 | gate form passes with new test included | `0 failed, 1587+ passed, 0 skipped` | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=7` |
| 3 | mutation check kills defect on Python 3.11 | test fails when subclass name is removed from message, passes when restored | verify failure under mutation and pass when reverted |
| 4 | unit stayed in scope | only `tests/unit/test_p1h_mac_gate.py` and tester journal entry | `git status` |

## Citations

- `docs/2-rules/rules.md`, rule 4 — a stop names the inputs it read.
- `docs/8-build/environment.md`, section 1 — Python 3.11 on macOS.
- `.agent/assignments/P1h-mac-gate.md` — unit assignment.

## Backlog items this unit is NOT fixing

- 53, 60, 95, 120, 123, 125, 146 (all in `ingestion/session_extraction.py`).
