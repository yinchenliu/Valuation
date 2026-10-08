---
id: P1e-test-order-tests
phase: 1 — the gates
agent: tester
depends_on: [P1e-test-order]
---

# Tests for `P1e-test-order`: repair the three tests whose assertion was the leak, and lock the restore

## Objective

`P1e-test-order` is written and its code reviewer approved it at round 1. It installs
`pytest-randomly` 5.0.0 (backlog item 127) and closes backlog item 124.

**Item 124.** `ingestion/session_extraction.main()` set the error handler on `sys.stdout`
and `sys.stderr` to `namereplace` and never put it back. `_pytest.capture.CaptureIO` is an
`io.TextIOWrapper` subclass, so under pytest that handler leaked into every test that ran
afterwards in the same process. The fix is a `contextlib.contextmanager`,
`naming_unencodable_characters`, that reads the handler, sets `namereplace`, and restores it
in a `finally`.

**Three tests are red and you repair them.** They are in
`tests/unit/test_session_extraction_console.py`:

| Test | Line | The one failing assertion |
|---|---|---|
| `test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[cp1252]` | `:329` | `assert record["errors"] == ["namereplace","namereplace"]` |
| `…[utf-8]` | `:329` | the same |
| `test_main_sets_the_handler_before_it_parses_argv` | `:346` | the same |

**`record["errors"]` is written after `main(argv)` returns, so that assertion IS the leak.**
Closing item 124 makes it false by design. **The code reviewer verified that per test rather
than reading the traceback**: it re-ran the same child for all four cases and every **other**
assertion in those tests still holds, `after == before == [encoding, encoding]` and
`code == 2`. Nothing is red because the fix is wrong.

## The trap this repository puts in front of you, stated first

**There is no benchmark in this repository.** No trustee file, no signed reference. So the
only thing that makes your expected values worth anything is that you derived them before
the code ran. **Running the code, reading the output and asserting that is the one failure
mode that passes forever.** `.claude/agents/tester.md` spends its first section on it.

## The second trap, and it is what this unit is about

**Do not delete an assertion to make a test green. The deleted assertion is usually the
subject.**

Each of the three tests above has a real subject that **survives** the fix, and the code
reviewer named both and measured one:

1. **The handler is `namereplace` at every write**, which is what makes the Windows console
   print `\N{RIGHTWARDS ARROW}` instead of exiting 2. It was `['namereplace','namereplace']`
   *during* the run before this unit and it still is. Only the reading **after** `main()`
   returns changed.
2. **The handler is set before argv is parsed**, which is `test_main_sets_the_handler_before_it_parses_argv`'s
   whole point, and it is why an argparse error message can print an arrow.

**Both are now measurable from inside the run**, where before they could only be read after
it. That is the repair: move the observation inside the block, do not drop it.

**A test that goes green because its subject was deleted is worse than a red test**, because
the gate then reports it as a guard.

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-08, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`, on
the working tree that holds this unit:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **3 failed, 1367 passed, 2 skipped**, and the three are the ones named above |
| full suite | `-m pytest -q` | **5 failed**: those three plus the two red on purpose |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 2 errors in 2 files, 21 checked |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.claude/check_guard.py` | 48/48 |

**If one of these disagrees when you run it, stop and report the disagreement.**

**The suite now shuffles, and one thing about that is yours to work with.** `pytest-randomly`
5.0.0 shuffles modules **and** tests within a module. **`-q` suppresses the
`Using --randomly-seed=` line** — I measured it: 0 matches with `-q`, and
`Using --randomly-seed=3689265847` without it. **So when something of yours goes red, re-run
it without `-q` to recover the seed, and name the seed in your entry.** Use
`--randomly-seed=<n>` for any measurement you need to repeat. **Do not put `-p no:randomly`
anywhere**: it is no longer a no-op.

**Read these two entries before you start.** They hold every probe already built, so you do
not rebuild them:

- `.agent/journal/2026-10-07T2244-programmer-p1e-test-order.md`
- `.agent/journal/2026-10-08T1112-code_reviewer-p1e-test-order.md`, whose probe covers the
  `SystemExit` path, the uncaught-exception path, and one object bound to both names.

## What to do

1. **Repair the three tests.** Move each observation of the handler **inside** the block, so
   the two subjects above are still asserted. Do not delete either subject, and do not delete
   a test.
2. **Rewrite the module docstring at `tests/unit/test_session_extraction_console.py:41-48`.**
   It states the leak as a live fact and justifies the file's three subprocesses by it. The
   leak is closed, so that text is now false. **The three subprocess tests themselves are
   still sound and stay** — the reviewer says so, and a subprocess is the only way to see a
   real console encoding.
3. **Lock the restore itself.** The handler must be back to what it was after `main()`
   returns, on **every** exit path: a normal return, the argparse `SystemExit`, and an
   uncaught exception. Derive what "what it was" means from the stream you construct, never
   from what the code printed.
4. **Lock that the handler is `namereplace` during the block**, which is the `P14f` behaviour
   this unit must not have weakened.
5. **Test the rule 3 stop.** `naming_unencodable_characters` raises `TypeError` when
   `stream.errors` is not a `str`, because `reconfigure(errors=None)` means "leave the
   handler alone" and would silently keep `namereplace` — item 124 wearing a quieter face.
   **Assert the type as well as the message**, and assert that the outer stream is still
   restored when the inner one raises.
6. **Test the non-`TextIOWrapper` path.** A stream that does not encode is yielded through
   without a set and without a restore.
7. **Mutate your own tests and record what each mutation kills.** At least these four, each
   in its own scratch tree, never in the repository:
   - The `finally` removed, so the handler leaks again. This is item 124 returning.
   - The restore moved before the body instead of after it.
   - The `TypeError` stop replaced by a silent `return`.
   - `namereplace` changed to `replace`, which still exits 0 and loses the character. The
     `P14f` tester measured that an exit-code-only test is green on this one.
   **A mutation your suite survives is a hole, and you report it rather than hide it.**
8. **Count what you covered, do not estimate it.** Intersect a `--cov-branch` report with the
   added line numbers from `git diff -U0`.

## Files in scope

- `tests/` only.

**Nothing else.** The write guard denies the rest.

## Out of scope

- **`ingestion/session_extraction.py` and `requirements-dev.txt`.** If you believe the
  implementation is wrong, say so in your entry and return `fail`. Do not fix it.
- **The two tests that are red on purpose**, `test_projector_rule3_red.py` and
  `test_routes_session_rule3_red.py`. Leave both red. They are different from your three.
- **Backlog items 123 and 125** in `ingestion/session_extraction.py`. Neither is closed by
  this unit and the programmer correctly did not claim them.
- **`docs/8-build/environment.md`.** The overall lead writes it. It needs the new dependency,
  the `-q` seed suppression, and that `-p no:randomly` must not be used.
- **Finding your own order dependence.** Twelve gate runs over six orders found none. You are
  not asked to hunt for more.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | Every expected value is hand-sourced | a count of assertions, and how many came from the code's output | **the second must be 0** |
| 2 | The three tests are repaired, not deleted, and neither subject is lost | both subjects still asserted, per test | `git diff` on the file, and your entry naming where each subject moved to |
| 3 | The stale module docstring is rewritten | `:41-48` no longer states the leak as live | `git diff` |
| 4 | The three subprocess tests still exist | unchanged | `git diff` |
| 5 | The restore holds on every exit path | normal return, argparse `SystemExit`, uncaught exception | your tests |
| 6 | The handler is `namereplace` during the block | asserted from inside | your tests |
| 7 | The rule 3 stop | type is `TypeError`, the message names the value and the stream, and the outer stream is still restored | your tests |
| 8 | The non-`TextIOWrapper` path | yielded through, nothing set, nothing restored | your tests |
| 9 | Four mutations, each killed | for each: the mutation, the command, the failing count and the **names** that went red | your own scratch trees. **Report any mutation your suite survives** |
| 10 | Coverage of what the unit added | statements covered and missed, as counts | `--cov-branch` intersected with `git diff -U0` |
| 11 | The gate | **1370 passed, 2 skipped, 0 failed**, which is 1367 plus the three you repaired plus any you add | `-m pytest -q --ignore-glob="*_rule3_red.py"` |
| 12 | The failing set | **empty**, compared by name | the gate form |
| 13 | The gate under shuffling | criterion 11 at three named seeds as well | `--randomly-seed=<n>` |
| 14 | Lint | 4 errors, every one `BLE001`. **Run `ruff check .` after your last edit** | `-m ruff check .` |
| 15 | The write guard | 48/48 | `.claude/check_guard.py` |

**Criterion 14 has its own history.** `P3c-one-number-tests` reported "4 `BLE001`" beside
"`All checks passed!` over my five files"; the acceptance run found a fifth error in a file
that tester had written, because it ran lint, then added two tests, and never re-ran it. The
`P3d` and `P14g` testers each caught one in their own file by running lint last. **Run lint
after your last write.**

## Citations

- `.claude/agents/tester.md` — your role card. Its first section is the first trap above.
- `docs/2-rules/rules.md` — rule 3.
- `docs/9-reference/refactor-backlog.md`, items 124 and 127.
- `.agent/assignments/P1e-test-order.md` — the unit, and the three forbidden moves.
- `.agent/assignments/P14f-prompt-encoding.md` — why the handler is `namereplace` and not
  `replace` or `ignore`.
- `ingestion/session_extraction.py` — `naming_unencodable_characters`, `main`.

## Known open items

- **Never mutate a file in this repository, not even briefly.** A spot check left a
  `return []` in `ingestion/claude_extractor.py` on 2026-10-05 with a comment saying it had
  been restored. It had not, and a check was dead for about ten hours. Work in a scratch copy
  under `C:\tmp` and print the repository file's sha256 before and after. `git stash` is
  forbidden, and now there is a second reason: a worktree shares the stash stack.
- **Backlog item 75**: the write guard refuses a `>` or a heredoc inside a Bash command.
  Write files with the Write tool.
- **`10K_filings/` and `extractions/` are now tracked**, as of 2026-10-08. A clean checkout
  has them. Items 117 and 140 were about their absence.
- The suite takes about 120 to 150 seconds.
