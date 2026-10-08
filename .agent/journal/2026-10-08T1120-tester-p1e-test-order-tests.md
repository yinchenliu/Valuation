---
agent: tester
assignment: P1e-test-order-tests
round: 1
status: complete
files_touched: [tests/unit/test_session_extraction_console.py]
verdict: pass
---

# P1e-test-order-tests — the three leak assertions moved inside the run, and the restore locked

> Opened before the first command. Filled as each result landed.

## What I did

The three red tests are **repaired, not deleted, and neither subject was dropped**. Each was
red on one line — `assert record["errors"] == ["namereplace","namereplace"]`, read **after
`main()` returned**, which is backlog item 124 itself. I moved the observation **inside** the
run three ways: a `TextIOWrapper` subclass that records `(encoding, errors)` at **every
write**; a spy on `_build_parser`, which `main` evaluates **before** `parse_args(argv)`, so
both handlers are read from inside the block and before argv exists; and, for the
before-argv test, the **bytes argparse itself wrote** — the rejected subcommand name holds
`U+2192`, so the message spells `\N{RIGHTWARDS ARROW}` under `namereplace` and would spell
`&#8594;` under the handler the test installed. Only **two** assertion lines were deleted in
the whole file, and both are the leak; one more moved from `record["code"] == 2` to
`stop.value.code == 2`, the same subject in the in-process form. I added **12** tests: the
restore on each of `main`'s three exit paths, the restore on a **real** inherited process
stream, the `namereplace` block and the handler that comes back proved on **bytes**, the
rule 3 `TypeError` stop with the outer stream still restored, the non-`TextIOWrapper`
pass-through, and `main`'s `plan` and `locate` arms, which nothing else reached through
`main`. The stale module docstring is rewritten. The six subprocess tests are
**byte-identical** to `HEAD`.

**No expected value in this file came from running the code.** Every one is the codecs
error-handler table, the Unicode name of U+2192, the UTF-8 encoding rule, an identity ("the
stream leaves as it arrived"), or a value this test put on the stream itself before the call.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Every expected value is hand-sourced | **pass** — 56 assertions added, **0** from the code's output | the table in "Expected values" below names the source of every one |
| 2 | The three tests are repaired, not deleted, and neither subject is lost | **pass** | `git diff` deletes exactly **two** assertion lines, both `record["errors"] == ["namereplace","namereplace"]`; every test function at `HEAD` still exists by name. Where each subject moved to is the table below |
| 3 | The stale module docstring is rewritten | **pass** | `git diff`: the paragraph that said "`main()` … never restores it" is replaced by one that states item 124 closed and says why the reading moved inside |
| 4 | The three subprocess tests still exist | **pass**, and unchanged to the byte | `HEAD:…:350,551` vs now `801,1002` → `diff` empty. That span is sections 3, 4 and 5: all **six** subprocess tests, the three `prompt --pass 2` ones among them |
| 5 | The restore holds on every exit path | **pass** | normal return (`check` → 2, `prompt` → 0, `plan`/`locate` → 0), argparse `SystemExit`, uncaught `RuntimeError`; and at the block's own level, body-raises and `SystemExit` |
| 6 | The handler is `namereplace` during the block | **pass** | at **every write** on both streams, and at `_build_parser()` before argv is parsed; and on bytes, inside vs after the block |
| 7 | The rule 3 stop | **pass** | `TypeError`, not a `ValueError`; message holds `None`, `error handler` and the stream's class; nothing was set before it stopped; the outer stream is back to the caller's handler |
| 8 | The non-`TextIOWrapper` path | **pass** | yields `False`, `reconfigure` never called on the way in or out, the character survives |
| 9 | Four mutations, each killed | **pass**, **0 survived** | table below: 13, 12, 2 and 15 named failures |
| 10 | Coverage of what the unit added | **pass** — **28 of 28** added executable statements covered, **0** missed; **0** missing branch arcs among them | `--cov-branch` JSON ∩ `git diff -U0` |
| 11 | The gate | **pass** — **1382 passed, 2 skipped, 0 failed** | `-q --ignore-glob="*_rule3_red.py"`. 1367 + 3 repaired + **12** added = 1382. See finding F1 on the criterion's literal 1370 |
| 12 | The failing set | **pass — empty**, by name | `-rf` printed no `FAILED` line in any of the four gate runs |
| 13 | The gate under shuffling | **pass** at seeds **1**, **124**, **127** and unseeded **2103899238** | all four: `1382 passed, 2 skipped` |
| 14 | Lint | **pass** — 4 errors, every one `BLE001`, **run after my last write** | `api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106`. None in my file; `ruff check tests/unit/test_session_extraction_console.py` → `All checks passed!` |
| 15 | The write guard | **pass** | `48/48 guard cases correct` |

Extra gates, all unmoved: types **2 errors in 2 files, 21 checked**; census **64**; route **200**.

## "What is already true" — verified, and one disagreement, which is arithmetic not conflict

| Fact | The assignment | I measured | Agree? |
|---|---|---|---|
| gate before my work | 3 failed, 1367 passed, 2 skipped, the three named | `tests/unit/test_session_extraction_console.py` alone: **3 failed, 14 passed**, the three by name, both on `:329` and `:346` | yes |
| full suite | 5 failed | after my work **2 failed** (the two red on purpose, by name), 1382 passed | the three are repaired, so this is the expected movement |
| lint | 4, all `BLE001` | **4, all `BLE001`**, same four sites | yes |
| types | 2 in 2 files, 21 checked | **2 in 2 files, 21 checked**, same two | yes |
| census | 64 | **64** | yes |
| route | 200 | **200** | yes |
| guard | 48/48 | **48/48** | yes |
| `-q` hides the seed | the overall lead measured it | confirmed: my unseeded gate run **without** `-q` printed `Using --randomly-seed=2103899238` | yes |

**No repository file was mutated, not once.** `ingestion/session_extraction.py` sha256
`55aff340a5224e4924eebe9fee76ac8b9ae42e24ff1508df5bbfaf67c7efa5cf` and
`requirements-dev.txt` `aee75169…` **before my first command and after my last**, printed at
both ends and again after every mutation run. Every probe and every mutation ran in
`C:\tmp\p1e_t` and `C:\tmp\p1e_mut` (a `tar` copy of the working tree). No `git stash`, no
`-p no:randomly` in any command I ran.

## Where each deleted subject moved to — criterion 2, per test

| Test | Subject the red line carried | Where it lives now |
|---|---|---|
| `…moves_neither_encoding[cp1252]` / `[utf-8]` | the handler is `namereplace` on **both** streams | `assert inside == [("namereplace","namereplace")]` — read by the `_build_parser` spy, **inside** the `with` and before argv is parsed — and `assert set(out.states) == {(encoding,"namereplace")}`, the state recorded at **every write** the command made |
| the same two | the encoding does not move | kept verbatim in spirit: built with `encoding`, every recorded write carries `encoding`, `(out.encoding, err.encoding) == (encoding, encoding)` after |
| the same two | exit 2 on a missing session file | `assert code == 2`, unchanged |
| the same two | *(new)* the stream is the caller's | `assert (out.errors, err.errors) == (CALLER_HANDLER, CALLER_HANDLER)` |
| the same two | the real-process-stream reading the old form had | **not lost**: it moved into `test_main_leaves_a_real_process_stream_as_it_found_it[cp1252|utf-8]`, which still runs `main` in a subprocess at a `PYTHONIOENCODING` console encoding and keeps the old `record["after"] == record["before"] == [encoding, encoding]` and `record["code"] == 2` lines — with the leak assertion replaced by the identity `record["errors"] == record["errors_before"]` |
| `…before_it_parses_argv` | the handler is on **before** argv is parsed | two readings: the spy at `_build_parser()`, which `main` evaluates before `parse_args`; and the **bytes argparse wrote** — the rejected subcommand carries `U+2192`, so the usage message spells `\N{RIGHTWARDS ARROW}`, which only `namereplace` produces, at a write made before any subcommand existed |
| `…before_it_parses_argv` | argparse's exit code | moved from `record["code"] == 2` to `stop.value.code == 2`, same comment |
| `…before_it_parses_argv` | *(new)* `SystemExit` is not an `Exception`, and the `finally` still restores | `assert (out.errors, err.errors) == (CALLER_HANDLER, CALLER_HANDLER)` on that path |

**The proof that the subject survived is the mutation, not my word for it.** With the
`finally` removed — item 124 returning — all three repaired tests go red again
(`no_finally`, below), and with `namereplace` changed to `replace` all three go red again
(`replace_handler`). A test that had been emptied of its subject would have stayed green
under both.

## Expected values — testers only

**56 assertions added. 0 came from the code's output.** Grouped; every row names its source.

| Assertion(s) | Expected | Where the expected value came from |
|---|---|---|
| `stream.errors == "namereplace"` inside the block; `set(out.states) == {(enc,"namereplace")}`; `inside == [("namereplace","namereplace")]`; `seen == [("namereplace","namereplace")]` (4 tests, 9 assertions) | `namereplace` | **`P14f`'s stated requirement** and the stdlib error-handler table: it is the only standard handler that leaves a reader able to name the character that was there. The literal string is written out; nothing imports `UNENCODABLE_CHARACTER_HANDLER`, which would be comparing the code with itself |
| `inside_bytes == b"inside \N{RIGHTWARDS ARROW}\n"` | those bytes | **hand**: the `namereplace` contract (`\N{` + Unicode name + `}`) applied to `U+2192`, whose Unicode name is `RIGHTWARDS ARROW`; every other character is ASCII, which cp1252 writes unchanged |
| `after_bytes == b"after &#8594;\n"` | those bytes | **hand**: the `xmlcharrefreplace` contract (`&#` + decimal code point + `;`) and `0x2192 = 2*4096 + 1*256 + 9*16 + 2 = 8192+256+144+2 = 8594` |
| `NAMED_ARROW.encode("ascii") in message` and `XMLCHARREF_ARROW not in message` (argparse's own output) | the named form, never the xml form | the same two rows of the same table. This pair is the discriminator: the only way the arrow reaches a cp1252 stream as `\N{…}` is a handler set before argparse wrote |
| `printed.count(NAMED_ARROW…) == arrows` / `printed.count(UTF8_ARROW) == arrows` | `arrows`, computed from the prompt pair built in the test from `claude_extractor` | **identity + input**: `arrows` is read off the command's *input* (the prompt module), never its output; the rendering of each is the `namereplace` contract on cp1252 and the UTF-8 encoding rule (`U+2192` → `b"\xe2\x86\x92"`, worked at the head of the file) on utf-8 |
| `(out.errors, err.errors) == (CALLER_HANDLER, CALLER_HANDLER)` (8 tests, 10 assertions) and `stream.errors == CALLER_HANDLER` (3) | `xmlcharrefreplace` | **the test put it there.** `owned_stream`/`RecordingStream` construct the stream with `errors=CALLER_HANDLER`, a handler **no path in the unit ever sets**, so the assertion cannot pass by accident and cannot be satisfied by a leaked value |
| `(out.encoding, err.encoding) == (encoding, encoding)` (3) and the encoding half of every recorded write | the encoding the test built the stream with | **construction + the `P14f` requirement** that the fix is the handler and never the encoding |
| `record["errors"] == record["errors_before"]` (2) | *the same pair*, whatever it is | **closed-form identity**: `main()` does not own `sys.stdout`/`sys.stderr`, so whatever handler they carried in they carry out. It holds for any Python default, so no part of it is a photograph. This is the assertion item 124 fails |
| `"namereplace" not in record["errors_before"]` (2) | true | **the `sys` documentation**: a piped `stdout` is `strict` and a piped `stderr` is `backslashreplace`. A vacuity guard on the identity above |
| `code == 2` (×3 forms), `stop.value.code == 2` (×2) | 2 | **stated behaviour**: P9a step 9 for the loader stop, and argparse's documented exit code for an unparsable argv |
| `(plan_code, locate_code) == (0, 0)`, `code == 0` (prompt) | 0 | **stated behaviour**: `cmd_plan`, `cmd_locate` and `cmd_prompt` return 0 on success; the skeleton path does not exist yet and the PDF is the one the session file hashes |
| `was_set is True` / `was_set is False` (3) | True for a `TextIOWrapper`, False otherwise | **the function's stated contract**, which `P14f` wrote and its review accepted: "Returns True when the handler was set and False when the stream does not encode" |
| `stream.reconfigured == []` inside and after (2), `stream.reconfigured == []` on the stopping stream (1) | empty | **the requirement**, not an observation: a stream with no encode step must be a pass-through, and a stop must happen **before** anything is set, or the stop itself leaks |
| `not isinstance(stop.value, ValueError)`; `"None" in message`; `"error handler" in message`; `"HandlerIsNotAName" in message` | `TypeError`, naming the value and the stream | **rule 3**, which requires the field to be named, and `main`'s own `except (ValueError, FileNotFoundError)`: a `ValueError` here would be rendered as an ordinary `ERROR: …` exit 2 and the stop would vanish. The type is part of the requirement |
| `outer.errors == CALLER_HANDLER` after the inner stop | the caller's handler | **the requirement**: `main` nests two of these blocks, so a stop in the second must not leave the first changed |
| `arrows == PASS2_SYSTEM_ARROWS`, `out.states` / `err.states` non-empty (6) | 2; non-empty | **vacuity guards**, stated as such: a prompt with no arrow, or a command that printed nothing, would make the test above it pass for the wrong reason |

**Two counts, with their units.**

- **Accuracy: 56 of 56 assertions** added match their independently derived expectation
  (29 of 29 test ids in the file pass; 1382 of 1382 in the gate). **0** expected values came
  from the code's output.
- **Coverage, in two units.**
  - **Functions: 2 of 2.** The unit adds one function, `naming_unencodable_characters`, and
    modifies one, `main`. Both are called by tests in this file.
  - **Statements: 28 of 28** of the unit's added executable lines, **0 missed**.
    **Branches: 0 missing arcs** among the added lines (21 missing arcs remain in the
    module as a whole, none of them on an added line). Measured, not estimated:
    `--cov=ingestion.session_extraction --cov-branch --cov-report=json` over `tests/unit`
    in the scratch tree, intersected with the 67 added lines from
    `git diff -U0 ingestion/session_extraction.py` (28 of those 67 are executable; the rest
    are the docstring, comments and blanks). The module as a whole went from **85% to 94%**
    when the `plan` and `locate` arms were added, which is how I found the two uncovered
    statements (`:1252`, `:1255`) and closed them rather than reporting them as a gap.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `stream.errors`, the handler to put back | **stops and names the value and the stream**: `TypeError("cannot name unencodable characters on this stream: its error handler reads as None, which is not a handler name … Stream: <HandlerIsNotAName …>")` | locked by `test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream`: type asserted, `not isinstance(…, ValueError)` asserted, three substrings of the message asserted, and `reconfigured == []` proves it stopped before it set anything |
| the same, when it is the **second** of `main`'s two blocks | the first block is still restored | `test_the_outer_stream_is_restored_when_the_inner_one_stops` |
| `isinstance(stream, io.TextIOWrapper)` false | **not a missing input, and I did not write a test that asserts a default.** There is no absent field: an object that keeps `str` performs no encode step, so no character can be lost and there is nothing to set or to put back. What I locked is the *pass-through property* — yields `False`, `reconfigure` never called either way, the character survives — not a fallback figure | `test_a_stream_that_does_not_encode_is_yielded_through_with_nothing_set`. Flagged for the orchestrator as F4 in case it reads this differently from the `P14f` review, which accepted it |
| a stream that cannot be reconfigured at all (detached) | **raises**, already locked at `HEAD` and untouched | `test_a_detached_stream_is_not_swallowed` |

**No stop path was unreachable, and none defaults instead of raising.** There is no
`file:line` to report under that heading.

## Measurements

**The suite, as failure SETS.** Every run `ANTHROPIC_API_KEY= GEMINI_API_KEY=
.venv/Scripts/python.exe`, after my last write to `tests/`.

| Run | Order | Failing set, by name | Summary |
|---|---|---|---|
| gate `-q --ignore-glob="*_rule3_red.py"` | `--randomly-seed=1` | **{ }** | `1382 passed, 2 skipped` |
| gate | `--randomly-seed=124` | **{ }** | `1382 passed, 2 skipped` |
| gate | `--randomly-seed=127` | **{ }** | `1382 passed, 2 skipped` |
| gate, unseeded, run **without `-q`** so the seed prints | `Using --randomly-seed=2103899238` | **{ }** | `1382 passed, 2 skipped` |
| full suite `-q` | unseeded | **{ `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` }** — the two red on purpose, untouched | `2 failed, 1382 passed, 2 skipped` |
| the file alone, before my work | — | the three named in the assignment, on `:329` and `:346` | `3 failed, 14 passed` |
| the file alone, after | — | **{ }** | `29 passed` |

**Nothing of mine went red at any point**, so there is no seed to recover for a failure. The
seeds above are named so every figure can be repeated.

**Criterion 9 — the four mutations, each in `C:\tmp\p1e_mut`, never in the repository.**
Driver: `C:\tmp\p1e_t\mutate.py`, which asserts its anchor matches exactly once, runs
`pytest tests/unit/test_session_extraction_console.py`, and restores the pristine text and
re-checks its digest after every run.

| # | Mutation | Command | Failing count | The names that went red |
|---|---|---|---|---|
| 1 | the `finally` removed — **item 124 returning** | `mutate.py no_finally` | **13 failed, 16 passed** | all three repaired tests (`…moves_neither_encoding[cp1252]`, `[utf-8]`, `…before_it_parses_argv`), `…prints_through_both_streams…[cp1252]`/`[utf-8]`, `…puts_both_handlers_back_when_a_subcommand_raises`, `…leaves_a_real_process_stream_as_it_found_it[cp1252]`/`[utf-8]`, `…plan_and_locate_go_through_the_block_too`, `…inside_the_block_the_handler_names…`, `…is_back_when_the_body_raises`, `…is_back_on_systemexit`, `…outer_stream_is_restored…` |
| 2 | the restore moved **before** the body | `mutate.py restore_first` | **12 failed, 17 passed** | the three repaired tests, both `…prints_through_both_streams…`, `…plan_and_locate…`, `…puts_both_handlers_back…`, the three block-level restore tests, **and two tests I did not write**: `test_prompt_pass2_prints_the_whole_prompt_on_a_cp1252_console`, `test_prompt_pass2_output_holds_no_silent_substitute` |
| 3 | the `TypeError` stop replaced by a silent `pass` | `mutate.py silent_stop` | **2 failed, 27 passed** | `…stops_and_names_the_value_and_the_stream`, `…outer_stream_is_restored_when_the_inner_one_stops` |
| 4 | `namereplace` → `replace` (still exits 0, loses the character) | `mutate.py replace_handler` | **15 failed, 14 passed** | the three repaired tests, both `…prints_through_both_streams…`, `…plan_and_locate…`, `…puts_both_handlers_back…`, the three block-level tests, and the four `P14f` tests that already guarded it |

**No mutation survived.** Mutation 3 is killed by exactly the two tests written for it, which
is the right shape: a narrow defect found by a narrow test. Mutation 1 is the one that
matters for criterion 2 — it is item 124 put back, and the three repaired tests catch it.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The three repaired tests call `main()` **in this process**, over a stream they build | That is what closing item 124 bought, and it is the only way to read the handler *while* the command runs. `monkeypatch` puts the real pair back however the test ends, so nothing can leak even if the unit regressed | A subprocess can only report state *after* `main` returns — which is exactly the reading that is now the defect. Keeping the subprocess would have forced either the leak assertion back or a weaker test |
| ...and the subprocess form is **kept**, as `test_main_leaves_a_real_process_stream_as_it_found_it` | A subprocess is the only way to see a *real* console encoding and a real inherited `sys.stdout`, and the restore is most meaningful exactly there. The old test's `after == before == [encoding, encoding]` and `code == 2` lines live on inside it | Deleting it would have dropped the `PYTHONIOENCODING` coverage the old form had, which would be losing a subject by the back door |
| `CALLER_HANDLER = "xmlcharrefreplace"` | A handler **no path in the unit sets**. A restore assertion against `strict` could be satisfied by Python's own default; against this one it cannot be satisfied by anything but a real restore | Using `strict` would have made "restored" and "never set" indistinguishable in a future regression |
| The before-argv test uses a rejected subcommand that **holds `U+2192`** | It turns the subject from an attribute reading into a **byte** reading: `\N{RIGHTWARDS ARROW}` in argparse's own message can only come from `namereplace`, at a write made before any subcommand existed | The old ASCII name could only be checked by reading `.errors` afterwards, which is the leak |
| Added `test_plan_and_locate_go_through_the_block_too` | The coverage intersection showed `:1252` and `:1255` — `main`'s `plan` and `locate` arms — as the only added statements no test reached. "One `with` covers every subcommand" is a claim about those arms | Reporting them as a known gap was the alternative. A gap reads as a clean report, and closing it cost one test and took the module from 85% to 94% |
| Did **not** import `UNENCODABLE_CHARACTER_HANDLER` to assert against | An assertion that the code equals itself passes forever | The literal `"namereplace"` is written out, so changing the constant turns the tests red — which mutation 4 proves |

**A test changed to reach a target number is forbidden. I changed none.** No assertion was
weakened, skipped or `xfail`ed; the two deleted lines are the leak and each has a named
replacement covering the same subject.

## What I did not do

- **I did not edit `ingestion/session_extraction.py` or `requirements-dev.txt`.** Both are
  byte-identical at both ends, printed above. I found nothing wrong with the implementation.
- **I did not touch the two tests red on purpose.** Both still fail, by name, in the full
  suite.
- **I did not touch `docs/8-build/environment.md`** or backlog items 123, 125 or 127.
- **I did not hunt for an order dependence.** Twelve runs over six orders already found none,
  and the assignment puts that out of scope; my four gate runs add four more orders with an
  empty failing set.

## Findings for the orchestrator

**F1 — criterion 11's number is superseded by its own arithmetic, and the criterion says so.**
It expects "**1370 passed**, which is 1367 plus the three you repaired plus any you add". I
added **12**, so the gate is **1382 passed, 2 skipped, 0 failed**. The literal 1370 is the
figure with zero tests added; the clause after it is the rule, and 1367 + 3 + 12 = 1382
satisfies it. Nothing to fix — recorded so the next reader does not treat 1382 as a
disagreement.

**F2 — I confirm the reviewer's F1 from my own run.** The gate form carries `-q` and prints
no seed; the same command without `-q` printed `Using --randomly-seed=2103899238`. Any gate
figure taken with `-q` describes **one unrecorded order**. `docs/8-build/environment.md`
still needs that sentence, and the three others in the programmer's F5.

**F3 — a scratch copy of this repository skips 12 more tests than the repository does, and
silently.** My mutation and coverage tree is a `tar` copy that excludes `10K_filings/` and
`extractions/`: `tests/unit` there reports **14 skipped** against the repository's **2**. The
12 are skipped, not failed, so a measurement taken in a scratch tree reads as clean. It did
not affect anything here — the module's added lines are fully covered and all four mutations
were killed by tests that need neither folder — but anyone who copies the tree for a
mutation run should copy those two folders or say which figure they excluded. Both are
tracked as of 2026-10-08, so the exclusion is now a choice rather than a fact of the machine.

**F4 — one judgement I made that the orchestrator may want to overturn.**
`naming_unencodable_characters` **yields `False`** for a stream that is not an
`io.TextIOWrapper` instead of stopping. I treated that as *not* a rule 3 default — there is
no absent field, and an object that keeps `str` cannot lose a character — and I locked the
pass-through property rather than the value. That matches `P14f`'s accepted docstring and
this unit's review. If the orchestrator reads it the other way, the test to change is
`test_a_stream_that_does_not_encode_is_yielded_through_with_nothing_set`, and the change is a
`*_rule3_red.py` file, not an edit to that test.

**F5 — nothing is left in a `*_rule3_red.py` file that has gone green.** I checked, since
this unit fixed a defect: the only two such files are `test_projector_rule3_red.py` and
`test_routes_session_rule3_red.py`, both still red in the full-suite run above, so neither is
the backlog-item-24 case. None of my tests needed that pattern — every requirement I wrote is
met by the code as it stands.

**F6 — `test_main_leaves_a_real_process_stream_as_it_found_it` is the regression guard for
item 124 and it is cheap to lose.** It is the only test that reads a **real** inherited
`sys.stdout`, and it asserts an identity rather than a value, so it looks like it asserts
nothing to a fast reader. Mutation 1 kills it. Worth a line in whatever records item 124 as
closed.
