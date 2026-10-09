---
id: P1h-mac-gate
phase: 1 — make the suite runnable
agent: programmer
depends_on: []
team: A (worktree `Valuation-wt/team-a`, branch `unit/team-a`)
---

# The stream-handler stop names the stream's class on every Python (item 145)

## Objective

**The fact.** The build moved back to the macOS machine on 2026-10-08. Its venv runs
Python 3.11.6. There, with the empty-key prefix, the gate form gives **1 failed**:

```
$ ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider \
    "tests/unit/test_session_extraction_console.py::test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream"
>       assert "HandlerIsNotAName" in message          # the stream it read it from
E       assert 'HandlerIsNotAName' in "cannot name unencodable characters on this stream:
        its error handler reads as None, which is not a handler name, so the handler this
        would set could not be put back afterwards. Stream: <_io.TextIOWrapper encoding='cp1252'>"
1 failed
```

The same test passes on the Windows machine (Python 3.14.4, gate **1584 passed, 0 failed**
at `82ac523`).

**What follows.** The message at `ingestion/session_extraction.py:1230-1233` names the
stream with `{stream!r}`. On Python 3.11 and 3.12, `repr()` of an `io.TextIOWrapper`
subclass prints `_io.TextIOWrapper`, not the subclass. Measured by the overall lead on
this machine:

| Python | `repr(X(io.BytesIO(), encoding='cp1252'))` for `class X(io.TextIOWrapper)` |
|---|---|
| 3.11.6 (`.venv/bin/python`) | `<_io.TextIOWrapper encoding='cp1252'>` |
| 3.12.7 (`/opt/homebrew/bin/python3.12`) | `<_io.TextIOWrapper encoding='cp1252'>` |

So on this machine the stop names a class the stream is not. pytest's `CaptureIO` is such
a subclass (backlog item 124), so a stop raised under capture names the wrong class too.

**When this unit is done**, the message names the stream's own class on every Python this
repository runs (3.11 on macOS, 3.14 on Windows), and the test passes unchanged.

## What is already true — verify, do not redo

- The test above is the only failure in the gate form on macOS. At `29de775`, seeds 7,
  1234 and 99 each give **1 failed, 1585 passed, 0 skipped**. Reproduce:
  `.venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=7`.
- `pytest-randomly` 5.0.0 is installed in the macOS venv.

If a measurement disagrees, stop and report the disagreement. Do not edit to make it agree.

## What to do

1. In the `TypeError` message of `naming_unencodable_characters`
   (`ingestion/session_extraction.py`, the `raise TypeError(...)` under
   `if not isinstance(previous, str):`), name the stream's class explicitly, from
   `type(stream)`, on every Python version. Keep the `repr` as well: on a real console it
   carries the stream's `name` and `encoding`, which the class alone does not.
   Reason: rule 4 — a stop must name its inputs, and the stream is one of them.
2. Change nothing else in that function: not the exception type, not the order of the
   checks, not the other two sentences of the message. The test's docstring says why the
   type is `TypeError` and not `ValueError`.

## Files in scope

- `ingestion/session_extraction.py` (programmer)
- `tests/unit/test_p1h_mac_gate.py` (tester, new file)

**Nothing else.** Work outside this list is a review finding, even if the change is good.
**`tests/unit/test_session_extraction_console.py` does not change.** The fix goes in the
code, so the test that found the defect stays as it was written.

## Out of scope

- `ingestion/claude_extractor.py`: backlog item 133 waits for the next pilot round.
- `cli.py`, `api/`: team B's unit `P3e-reconciliation-years` is in flight on them.
- `.venv`, `requirements*.txt`: a unit branch installs nothing. The venv is shared.
- The four record files and `docs/`, `.claude/`, `extractions/`: see "Pilot rules".

## Done-criteria

Run every command **from the worktree root**, with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`
in front.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the test that found the defect passes, unchanged | `1 passed` | `.venv/bin/python -m pytest -q -p no:cacheprovider "tests/unit/test_session_extraction_console.py::test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream"` |
| 2 | that test file did not change | no output | `git diff main -- tests/unit/test_session_extraction_console.py` |
| 3 | the gate form is green at three orders | `0 failed` at each seed; the passed count is `main`'s plus the tester's new tests; the skipped set equals `main`'s | `.venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=<n>` for n = 7, 1234, 99 |
| 4 | the full suite fails only the two tests that are red on purpose | `2 failed`, both in `*_rule3_red.py` | `.venv/bin/python -m pytest -q -p no:cacheprovider --randomly-seed=7` |
| 5 | lint unchanged | `4 errors`, every one `BLE001`, none in a file this unit wrote | `.venv/bin/python -m ruff check .` |
| 6 | types unchanged | `2 errors in 2 files` | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` |
| 7 | rule 3 census unchanged | `64` | the grep at `docs/2-rules/rules.md:65`, with `pipeline.py` added and `'--include=*.py'` quoted |
| 8 | the unit stayed in scope | only the two files above, this assignment, `P1h-mac-gate-tests.md` and new files under `.agent/journal/` | `git diff --name-only main...HEAD` |
| 9 | a test that kills the defect on Python 3.11 | the tester's new test goes red when the class name is removed from the message, and green with it | the tester reports the mutation and both counts |

**Every criterion is a measurement, never an opinion.**

## Pilot rules (worktree)

This unit runs in a git worktree, beside team B's unit. [docs/8-build/worktree-teams.md](../../docs/8-build/worktree-teams.md)
owns the scheme. These four points bind this unit:

1. **Do not write** `STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md` or
   `docs/9-reference/refactor-backlog.md`. Every merge would conflict on them. The
   overall lead writes them on `main` after the merge. A subagent's own journal entry,
   with its own file name, is allowed.
2. **The build lead does not set a queue state.** It writes `## Handoff` at the end of
   this file, commits on `unit/team-a`, and tells the user "P1h-mac-gate is ready for the
   overall lead".
3. **Install nothing.** `.venv` in the worktree is a link to the main checkout's venv.
4. **No hook protects a Gemini subagent.** After each subagent run, run `git status` and
   reject the run if it wrote outside its role or outside Files in scope.

## Citations

- `docs/2-rules/rules.md`, rule 4 — a stop names the inputs it read.
- `docs/8-build/environment.md`, section 1 — the two machines run different Pythons.
- `tests/unit/test_session_extraction_console.py:742-775` — the test and its docstring.

## Known open items

- Backlog item 124 is closed. `CaptureIO` is mentioned above only as an example of a
  subclass.

## Backlog items this unit is NOT fixing

Each sits in `ingestion/session_extraction.py`. Leave them alone.

- 53 — `_NRI_SCHEMA` imported by its private name.
- 60 — the `plan` message about the fiscal year.
- 95 — the unreachable fiscal-year check in `cmd_plan`.
- 120 — the repeated `[MERGE]` summary line.
- 123, 125 — the discarded `bool` and the replaced `surrogateescape` handler.
- 146 — `cmd_plan` writes absolute PDF paths into a session file.

## Handoff

### Commits
- `42034c2`: `P1h-mac-gate: stream-handler stop names the stream's class on every Python (item 145)`

### Verdicts
- Programmer: `complete`, entry: `.agent/journal/2026-10-09T0121-programmer-p1h-mac-gate.md`
- Code reviewer: `approved`, entry: `.agent/journal/2026-10-09T0133-code_reviewer-p1h-mac-gate.md`
- Tester: `pass`, entry: `.agent/journal/2026-10-09T0135-tester-p1h-mac-gate.md`

### Gates
- Test gate (seed 7): `0 failed, 1589 passed, 0 skipped in 33.48s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=7`)
- Test gate (seed 1234): `0 failed, 1589 passed, 0 skipped in 34.06s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=1234`)
- Test gate (seed 99): `0 failed, 1589 passed, 0 skipped in 33.53s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=99`)
- Full suite (seed 7): `2 failed, 1589 passed in 33.83s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider --randomly-seed=7`)
  Failures are only the two intentional red tests: `test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_valuation_with_session_file_and_files_on_a_cache_hit_stops`.
- Defect test: `1 passed in 0.02s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider "tests/unit/test_session_extraction_console.py::test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream"`)
- New unit tests: `3 passed in 0.03s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_p1h_mac_gate.py`)
- Lint: `4 errors`, all `BLE001`, 0 in unit files (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m ruff check .`)
- Types: `2 errors in 2 files` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports`)
- Rule 3 census: `64` (`grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" '--include=*.py' models analysis api ingestion pipeline.py | wc -l`)
- Web root: HTTP 200 (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -c "from starlette.testclient import TestClient; from app import app; print(TestClient(app).get('/').status_code)"`)

### Findings and notes
- Criterion 9 (mutation kill): 3 of 3 tests in `tests/unit/test_p1h_mac_gate.py` killed the mutation when `{type(stream).__name__} ` was removed on Python 3.11 (`3 failed in 0.04s` with `AssertionError: assert '<SubclassName>' in ...`), and passed when restored (`3 passed in 0.03s`).
- Test file `tests/unit/test_session_extraction_console.py` was not modified (`git diff main -- tests/unit/test_session_extraction_console.py` produced no output).
- Pre-existing backlog items 53, 60, 95, 120, 123, 125, 146 in `ingestion/session_extraction.py` remain untouched.

### Questions for the overall lead
None.


## Overall lead review

**Round 1, 2026-10-08. Verdict: `rework`. One finding to fix (F1), one record to correct
(F2).** The code change is accepted as it stands: the programmer does not run again.

### What I re-ran, from this worktree, with the empty-key prefix

| # | Criterion | I measured | Agree? |
|---|---|---|---|
| 1 | the defect test passes, unchanged | `1 passed` | yes |
| 2 | `test_session_extraction_console.py` unchanged | empty diff | yes |
| 3 | gate form, seeds 7, 1234, 99 | `1589 passed` at each, 0 failed, 0 skipped | yes |
| 4 | full suite | `2 failed, 1589 passed`, the two `*_rule3_red.py` tests | yes |
| 5 | lint | `4 errors`, all `BLE001`, none in a unit file | yes |
| 6 | types | `2 errors in 2 files` | yes |
| 7 | census | `64` | yes |
| 8 | scope | the 2 files in scope, 2 assignment files, 3 journal entries | yes |
| 9 | mutation | I removed `{type(stream).__name__} ` in a scratch worktree: `4 failed` (the 3 new tests and the defect test); restored: `4 passed` | yes, **on Python 3.11 only** — see F1 |

### F1 — the three new tests fail on the Windows machine. Fix it.

**The fact.** `tests/unit/test_p1h_mac_gate.py:71`, `:104` and `:131` each assert
`"<ClassName>" not in repr(stream)`, as a "precondition". That asserts a property of the
**interpreter**, not of the code. On Python 3.13 and later, `repr()` of a `TextIOWrapper`
subclass names the subclass. The proof is in this repository: at `82ac523` on the Windows
machine (Python 3.14.4), `test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream`
passed while the message carried `{stream!r}` and nothing else, and it asserts the subclass
name.

**What follows.** On the Windows machine all 3 new tests go red against correct code. I
cannot run 3.14 here, so I gave the three classes a `repr` that names the subclass, as 3.14
prints it, and ran the tests on the correct code: **3 of 3 fail, each at its precondition
line.** That is item 145 again, in the other direction.

**The fix, in `tests/unit/test_p1h_mac_gate.py` only (a tester change; the programmer does
not run).** Delete the three `assert "<ClassName>" not in repr(stream)` lines, their
`# Precondition` comments, and the docstring line "repr(stream) on Python 3.11 omits the
subclass name". The `expected_stream_prefix` assertion already carries the test: it needs
`Stream: <ClassName> ` before the `repr`, which only the fix writes. **I measured that fix
before asking for it**, on a scratch copy, under both `repr` forms:

| Code | Python 3.11 `repr` | 3.14-style `repr` |
|---|---|---|
| correct code | 3 pass | 3 pass |
| mutant (class name removed) | 3 FAIL | 3 FAIL |

Do not add a `skipif` on the Python version. A test that kills the mutant on both machines
is the aim, and the fix above is one.

### F2 — the handoff names a commit that is not on the branch. Correct it.

`## Handoff` names `42034c2`. The branch holds `3b1225d`: the reflog shows
`commit (amend)` from `42034c2`. Name the commit that is on the branch. **For the rework,
make a new commit; do not amend**, so the record shows both rounds.

### To finish the rework

1. Dispatch the tester with F1. It changes `tests/unit/test_p1h_mac_gate.py` only.
2. Re-run criterion 9 and the gates (criteria 3 to 8).
3. Commit on `unit/team-a` as a new commit, append `## Handoff, round 2` with the commit,
   the counts and the commands, and tell the user "P1h-mac-gate is ready for the overall
   lead".
