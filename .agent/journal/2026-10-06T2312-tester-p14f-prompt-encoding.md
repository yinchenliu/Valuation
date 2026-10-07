---
agent: tester
assignment: P14f-prompt-encoding-tests
round: 1
status: complete
files_touched: [tests/unit/test_session_extraction_console.py]
verdict: pass
---

# P14f-prompt-encoding — the console that may not lose a character, locked

> Opened before the first command, filled as each result landed.

## What I did

One new file, `tests/unit/test_session_extraction_console.py` — **17 tests, 550
lines**, holding `name_unencodable_characters` and `main`'s two calls to it. Nothing
outside `tests/` was written. **Every mutation was made in a scratch tree under
`c:/tmp/p14ft/`**; the repository's three named files are byte-identical before and
after.

The one thing the unit turns on is the handler, and the exit code cannot hold it:
`replace`, `backslashreplace`, `xmlcharrefreplace` and `ignore` all exit 0 and the last
deletes the character. So the load-bearing assertions are on **rendered bytes**, not on
a return code — and both `replace` and `ignore` turn eight of my seventeen tests red
while leaving the exit code at 0, which is exactly the measurement criteria 10 and 11
ask for.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | my own baseline, by name | **pass** | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly --junit-xml=c:/tmp/p14ft/baseline.xml` → **1207 passed, 2 skipped**, 116.15 s. Failure set parsed from the XML **by name**: **{ }** |
| 2 | failing set empty when I finish | **pass** | the same command → **1224 passed, 2 skipped, 0 failed**, 159.91 s. Failure set from the XML, by name: **{ }**. 1224 = 1207 + my 17 |
| 3 | full suite shows only the two deliberate failures | **pass** | `-m pytest -q -p no:randomly` → **2 failed, 1224 passed, 2 skipped**, 147.18 s. The set, by name: `tests.unit.test_projector_rule3_red::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `tests.unit.test_routes_session_rule3_red::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` — exactly the two red on purpose, and **both are still genuinely red**, so backlog item 24's "a green test left inside the excluded pattern" does not apply here |
| 4 | the exit code and the line count are held | **pass** | `test_prompt_pass2_prints_the_whole_prompt_on_a_cp1252_console`: `returncode == 0` **and** the line count equals `len(system lines) + len(user lines) + 5`, an identity derived from `cmd_prompt`'s five framing prints. Red in `head` (exit 2) and in `deleted` |
| 5 | the visible escape is held | **pass** | the same test and `test_prompt_pass2_output_holds_no_silent_substitute`: every prompt line holding `U+2192` must arrive with `\N{RIGHTWARDS ARROW}` in its place, and must **not** arrive in the `?`, deleted, `\u2192` or `&#8594;` spelling |
| 6 | the handler and the encoding are both held | **pass** | `test_the_handler_is_namereplace_and_the_encoding_does_not_move` (`errors == "namereplace"`, `encoding == "cp1252"` unchanged), `test_a_character_the_console_already_holds_is_written_unchanged` (`—` → `0x97`, `…` → `0x85`), and at `main` level `test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[cp1252|utf-8]` asserts `after == before` for both stream encodings |
| 7 | a UTF-8 console is not degraded | **pass** | `test_a_utf8_console_is_not_degraded` (bytes `b"\xe2\x86\x92"`, no `\N{`) and `test_prompt_pass2_on_a_utf8_console_prints_the_arrow_itself` (`PYTHONIOENCODING=utf-8` in the child only; the parent shell has none set) |
| 8 | no prompt byte moved | **pass** | `test_the_two_system_prompts_are_byte_for_byte_what_they_were`: both constants asserted **non-empty first**, then length and sha256 against literals I measured myself in `git archive 0bc41a1` — `pass1_system len 11437 f1ff5987…`, `pass2_system len 3317 843ce6e7… arrows 2`. Plus `test_the_prompts_the_command_prints_are_the_prompts_route_a_sends`, which asserts both strings non-empty and then finds each verbatim in the UTF-8 run's output |
| 9 | the five other subcommands are unmoved | **pass** | `test_prompt_pass1_on_a_cp1252_console_is_whole_and_unescaped` (no `\N{`, em dash still `0x97`, same line-count identity) and `test_check_on_a_cp1252_console_still_prints_the_characters_it_holds` (`…` still `0x85`, no `\N{`). `plan`, `locate` and `text` are covered **by construction**, not by luck: `test_main_sets_the_handler_before_it_parses_argv` proves the handler is on both streams before argparse chooses a subcommand, so one call site covers all six |
| 10 | **`replace` fails** | **pass** | scratch tree `replace`: **8 red of 17**, named below. The command still **exits 0** — the two end-to-end tests got past their `returncode == 0` assertion and died on the rendering |
| 11 | **`ignore` fails** | **pass** | scratch tree `ignore`: **8 red of 17**, the same eight. Also still **exit 0** |
| 12 | the two calls deleted fails | **pass** | scratch tree `deleted`: **5 red of 17** |
| 13 | my tests do not depend on test order | **pass, by a different measurement — see the finding** | `pytest-randomly` **is not installed** in this venv, so there is no random order to run; `-p no:randomly` is a no-op here. Measured instead by permutation: the leaking file first, my file first, my file alone, and all 17 ids run one per process in reverse declaration order |
| 14 | lint | **pass** | `-m ruff check .` **run after my last edit to `tests/`** → **`Found 4 errors`**, every one `BLE001`, at `api/routes_valuation.py:451`, `:733`, `cli.py:1204`, `tests/test_e2e_all_googl.py:106` — the same four the programmer and the reviewer measured. My file adds none |
| 15 | nothing outside `tests/` changed | **pass** | `git diff --stat -- . ':(exclude)tests'` → `ingestion/session_extraction.py | 47 +++…`, **1 file changed, 47 insertions(+)**, 0 deletions. `git status --short` → `M ingestion/session_extraction.py`, plus my two untracked files (the test and this entry) |
| 16 | accuracy and coverage, with units | **pass** | below |

### Criteria 10-12, the mutation table

Five scratch trees, each `git archive 0bc41a1` with my test file copied in and one
`ingestion/session_extraction.py` written **as bytes** (so `fixed` is byte-identical to
the repository's, hash `58b05fef…`, and is the control):

| Tree | `session_extraction.py` sha256 | My file |
|---|---|---|
| `head` (no fix) | `2730e0339bbf675ea52c…` | **12 red of 17** |
| `fixed` (control) | `58b05fef1c5df517ab54…` | **17 passed** |
| `replace` | `1606ca3c740281a4987a…` | **8 red of 17** |
| `ignore` | `2c4c8aafeb6e0cc10735…` | **8 red of 17** |
| `deleted` (the two calls removed, 90 bytes) | `f106580b09d671b0fb29…` | **5 red of 17** |

The eight red under **both** `replace` and `ignore`:

```
test_the_handler_is_namereplace_and_the_encoding_does_not_move
test_an_unencodable_character_is_written_as_its_unicode_name
test_the_handler_chosen_is_not_one_that_loses_the_character
test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[cp1252]
test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[utf-8]
test_main_sets_the_handler_before_it_parses_argv
test_prompt_pass2_prints_the_whole_prompt_on_a_cp1252_console
test_prompt_pass2_output_holds_no_silent_substitute
```

The five red with the two calls deleted are the last five of those (the three `main`
tests and the two end-to-end `prompt --pass 2` tests); the seven that build their own
`TextIOWrapper` stay green there, correctly, because the function itself is untouched.

**The measurement criteria 10 and 11 exist for.** Under `replace` and under `ignore` the
command still **exits 0**: both end-to-end tests assert `returncode == 0` *first* and
reached the next assertion, which read

```
replace :: ...prints_the_whole_prompt...      assert 0 == 2
ignore  :: ...prints_the_whole_prompt...      assert 0 == 2
replace :: ...holds_no_silent_substitute...   assert '        "ad...ean earnings' not in '=== SYSTEM ...'
ignore  :: ...holds_no_silent_substitute...   assert '        "ad...ean earnings' not in '=== SYSTEM ...'
```

`assert 0 == 2` is the arrow-count identity: zero named arrows arrived where the prompt
holds two. A suite that checked only the exit code would have been **green on all three
mutants but one**.

### Criterion 13, and why it is measured differently

`pytest-randomly` is not in this venv (`importlib.metadata` lists `pytest` and
`pytest-cov` only; `-p randomly` → `ImportError: No module named 'randomly'`;
`--randomly-seed=1` → `unrecognized arguments`). There is therefore **no default random
order on this machine** — `-p no:randomly` disables a plugin that is not there, and the
suite always runs in collection order. Criterion 13 cannot be measured as written. What
I measured instead, which answers the question the criterion is about (backlog item 124:
`main()` leaves `errors='namereplace'` on pytest's `CaptureIO` for every later test):

| Order | Result |
|---|---|
| `test_session_extraction.py` then my file — the leak happens **before** my tests | **173 passed**, 63.4 s |
| my file then `test_session_extraction.py` — my tests run **before** the leak | **173 passed**, 66.2 s |
| my file alone | **17 passed**, 6.5 s |
| each of the 17 ids in **its own process**, in reverse declaration order | **17 of 17 green, 0 red** |

**How the tests were written so that order cannot matter**, which is the assignment's
real question: no test in the file reads or writes `sys.stdout`, `sys.stderr` or any
other process global. Each stream test builds its **own** `io.TextIOWrapper` over an
`io.BytesIO` it owns, and every test of `main` runs it in a **subprocess**, whose
streams die with it. So the item-124 leak is invisible to this file in either
direction — and my file does not add a second leak of its own.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The end-to-end tests build their **own** session file under `tmp_path` | `docs/5-testing/strategy.md` §3: a unit test must not need a key, a PDF or the internet. The builders in `tests/unit/test_session_extraction.py` already write a real PDF printing each cited line | Running `extractions/WMT.json` would make the test depend on a file **not in git** (the assignment forbids touching it) and on this machine's console code page. Neither would run anywhere else |
| Each child's console code page is set **explicitly** (`PYTHONIOENCODING=cp1252` or `utf-8`) | The defect is "a console that cannot hold `U+2192`". Naming the code page in the child makes the test ask that question on every machine, not only on a Windows cp1252 one | Inheriting the parent's console makes the test a no-op on a UTF-8 host and the regression walks straight back in. **My own shell has no `PYTHONIOENCODING` set**, as the criteria require; the variable exists only in the children these tests spawn |
| Assertions are on **bytes**, decoded only where a line is compared | The question is what reached the console. Decoding first would hide exactly the loss being tested | A `text=True` subprocess would silently re-encode and could make `ignore` look identical to `namereplace` |
| The expected rendering is built from the **prompt's own lines**, `line.replace("→", "\\N{RIGHTWARDS ARROW}")` | The prompt text is an **input** to `session_extraction`, read from `ingestion/claude_extractor.py:412-413`; the escape form is the documented `namereplace` contract | Pasting the two rendered lines as literals would photograph the output, and would also break on a prompt re-indentation that is not a defect |
| The LLM boundary is pinned at the **two system prompt constants**, not at the file's sha256 | `_pass1_prompt_pair` / `_pass2_prompt_pair` return `_FINANCIALS_SYSTEM_PROMPT` and `_NRI_SYSTEM_PROMPT` unchanged, so one digest each covers every filing. Both measured in `git archive 0bc41a1` | Hashing `claude_extractor.py` would turn red on every legitimate change to a file this unit does not own. Hashing the user prompts needs `WMT.json`'s plan, which is not in git |
| I did not write a `*_rule3_red.py` file | Nothing in this unit defaults where it should stop; see the rule 3 table | A red file stating a requirement the code meets would be a lie, and the gate would never run it |

**No assertion here was written to make a figure look right.** Every expected value in
the file predates the run that produced it; the table below names the source of each.

## Rule 3 — what stops, and what does not

The unit reads exactly one thing, and produces no figure.

| Value read | If it were missing | Evidence |
|---|---|---|
| the runtime type of `sys.stdout` / `sys.stderr` | **returns `False` and sets nothing — and that is not a rule 3 defect** | `ingestion/session_extraction.py:1185-1186`. Locked by `test_a_stream_that_cannot_lose_a_character_keeps_every_character` |
| a `TextIOWrapper` whose buffer is gone | **stops** — `ValueError`, message names `detach` | `test_a_detached_stream_is_not_swallowed`: `pytest.raises(ValueError, match="detach")` |

**Stop paths locked:** one — the detached stream, whose message names `detach`.
**Stop paths I could not lock:** none, and there is no defaulted figure to report.

**Why the `False` branch is not a finding, stated so it can be overturned.** Rule 3's
harm is a value meaning "we do not know" rendering as a number. Here there is no missing
input: the predicate asks "does this stream encode text to bytes at all?", and a stream
that does not (an `io.StringIO`) **cannot lose a character**, so there is nothing an
error handler could do to it. My test asserts the substantive property — the arrow
written into a `StringIO` is still there afterwards — and only then the `False`. I
deliberately did **not** write a test asserting a fallback value; `False` here is not a
fallback for a figure, it is the statement "this stream was already safe". The programmer
argued this at length and the reviewer accepted it; I reach the same answer by a third
route, which is that the branch fails **towards** the pre-existing `UnicodeEncodeError`,
never towards a number.

## Measurements

**Failure sets, by name.**

| Run | Result | Failure set |
|---|---|---|
| gate, before I wrote anything | 1207 passed, 2 skipped, 0 failed, 116.15 s | **{ }** |
| gate, after my last edit | **1224 passed, 2 skipped, 0 failed**, 159.91 s | **{ }** |
| full suite, after my last edit | **2 failed, 1224 passed, 2 skipped**, 147.18 s | **{ `test_projector_rule3_red::…stops_and_names_the_input`, `test_routes_session_rule3_red::…on_a_cache_hit_stops` }** — the two red on purpose, unchanged |

Compared **by name**, not by count: the gate's failure set is `{ }` on both sides, and
the full suite's set is the same two names `STATUS.md` §1 carries. The only figure that
moved is the passing count, +17, which is my file.

**Repository hashes, start and end of my run** — nothing in the repository was mutated.
Every mutation lived in `c:/tmp/p14ft/{head,fixed,replace,ignore,deleted}`:

```
                                 start                 end
ingestion/session_extraction.py  58b05fef1c5df517…     58b05fef1c5df517ab544eb7070d700391cef2ea83678d4b39148a2ed62843e0
ingestion/claude_extractor.py    b459e4eebc8f6cfc…     b459e4eebc8f6cfc4172a24117e592f002f98ee5fe27187d2edeeb4fb69f7e35
extractions/WMT.json             c436e427ce3037d0…     c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675
```

`extractions/WMT.json` was never opened for writing and never read by a test.

**Gates after my last edit:** lint **4 errors, all `BLE001`** (unchanged, criterion 14).
I did not re-run types, census, route or the write guard: my file adds nothing to
`models/ analysis/ ingestion/ api/ config.py app.py`, which is what the types gate reads,
and nothing outside `tests/` changed (criterion 15).

## Expected values — testers only

Every row names where the expected side came from. **Not one came from this code's
output.** Sources, as cited in the test file's own docstring:

- **(A) the `namereplace` contract** — the stdlib `codecs` error-handler table: an
  unencodable character is written `\N{` + its Unicode name + `}`. The Unicode name of
  `U+2192` is `RIGHTWARDS ARROW`, from the Unicode character database. The two
  specifications give `b'\\N{RIGHTWARDS ARROW}'` before anything runs.
- **(B) the cp1252 code chart** — `U+2014 EM DASH` is `0x97`, `U+2026 HORIZONTAL
  ELLIPSIS` is `0x85`; both are *in* cp1252.
- **(C) the UTF-8 encoding rule, by hand** — `U+2192` = `0b0010_0001_1001_0010` →
  `1110_0010 10_000110 10_010010` = `b'\xe2\x86\x92'`.
- **(D) an identity** that holds whatever the prompt says.
- **(E) a before-value measured in `git archive 0bc41a1`**, the tree whose
  `session_extraction.py` is `2730e033…` — i.e. before this unit's code existed. I ran
  the digest script myself in that tree.
- **(F) the prompt source**, `ingestion/claude_extractor.py:412-413` — an **input** to
  the command under test, read off the file, never off the output.

| # | Assertion | Expected | Source |
|---|---|---|---|
| 1 | `name_unencodable_characters(cp1252 wrapper) is True` | `True` | (D) the function's one job on a stream that encodes |
| 2 | `stream.errors` after the call | `"namereplace"` | assignment Fact 2/3: the one standard handler that is never silent |
| 3 | `stream.encoding` after the call | `"cp1252"`, unchanged | (D) an error handler is not an encoding |
| 4 | `'costs → remove'` written to a cp1252 stream | `b'costs \\N{RIGHTWARDS ARROW} remove'` | **(A)** |
| 5 | the same bytes ≠ `ignore` / `replace` / `backslashreplace` / `xmlcharrefreplace` of the same string | four inequalities, each computed in the test by `str.encode` — the stdlib codec, not the unit | **(A)** + the stdlib codec as its own oracle |
| 6 | `b"RIGHTWARDS ARROW" in rendered` | present | **(A)** |
| 7 | `'— …'` written to a cp1252 stream | `b'\x97 \x85'` | **(B)** |
| 8 | `'costs → remove'` written to a utf-8 stream | `b'costs \xe2\x86\x92 remove'`, no `\N{` | **(C)** |
| 9 | an arrow written into an `io.StringIO` | still `'→'` | **(D)** a stream that never encodes cannot lose a character |
| 10 | `name_unencodable_characters(StringIO()) is False` | `False` | (D), and see the rule 3 section — this is not a fallback figure |
| 11 | a detached wrapper | raises `ValueError` naming `detach` | (D) a broken stream is an error, not an absent input |
| 12 | `main` → `sys.stdout.errors`, `sys.stderr.errors` | `["namereplace", "namereplace"]` | assignment Fact 2: **both** streams, because `cmd_prompt` sends `parse_pass1`'s table to stderr |
| 13 | `main` → stream encodings after vs before | equal, `[enc, enc]` for `enc` in cp1252, utf-8 | (D) |
| 14 | `main(["check", "<absent file>"])` | exit `2` | P9a step 9's exit-code contract, re-stated in `session_extraction.py:1054-1055` |
| 15 | `main(["no-such-subcommand"])` | exit `2`, handler already set | argparse's documented exit code for an unparsable argv; the ordering claim is the assignment's Fact 2, "before it parses argv" |
| 16 | `prompt --pass 2` on cp1252 | exit `0` | the unit's stated objective (item 113) |
| 17 | its stdout line count | `len(system.split("\n")) + len(user.split("\n")) + 5` | **(D)**, from `cmd_prompt`'s five framing prints (`session_extraction.py:1044-1050`): header, blank + header, blank + closing line |
| 18 | named arrows in that output | `== (system + user).count("→")`, and that count `== 2` | **(D)** + **(F)**: nothing dropped, nothing doubled |
| 19 | each prompt line holding `→` | arrives as `line.replace("→", "\\N{RIGHTWARDS ARROW}")` | **(A)** + **(F)** |
| 20 | the same lines in the `?`, deleted, `\u2192`, `&#8594;` spellings | **absent** | **(A)**: these are what the four other handlers would have written |
| 21 | `prompt --pass 2` on utf-8 | arrow's own bytes, count equal to the prompts', no `\N{` | **(C)** + **(D)** |
| 22 | `prompt --pass 1` on cp1252 | no `\N{` at all; `0x97` present; same line-count identity | **(B)** + **(D)**; Pass 1's prompts hold zero arrows, asserted in the test |
| 23 | `check` on cp1252 | exit 0, `0x85` present, no `\N{` | **(B)**; `cmd_check` abbreviates each hash with `…` (`session_extraction.py:1068`) |
| 24 | `_FINANCIALS_SYSTEM_PROMPT` non-empty, then len and sha256 | `11437`, `f1ff5987e972f501…` | **(E)** |
| 25 | `_NRI_SYSTEM_PROMPT` non-empty, then len and sha256 | `3317`, `843ce6e79ea264ca…` | **(E)** |
| 26 | arrows in `_NRI_SYSTEM_PROMPT` | `2` | **(E)** (`arrows 2` in the before-tree run) + **(F)** |
| 27 | the printed prompts contain the module's own strings | both non-empty first, then `in` the output | **(D)** identity: route B prints what route A sends |

**Trap 3, handled explicitly.** Rows 24, 25 and 27 assert **non-empty before
comparing**: `assert _FINANCIALS_SYSTEM_PROMPT` / `assert _NRI_SYSTEM_PROMPT` /
`assert system and user`. Rows 18 and 26 assert the arrow count is 2 **before** the
rendering is examined, so a prompt that lost its arrows could not make the rendering
test pass vacuously. Two empty results are not a match.

**My own before-tree measurement, for rows 24-26** (`git archive 0bc41a1`,
`session_extraction.py` = `2730e033…`, `PYTHONPATH` set so the import could not fail
silently, and the script exits non-zero on an empty constant):

```
pass1_system len 11437 sha256 f1ff5987e972f5015305353eb68dd0f26285fe72de2576ccaf008496624f6d67 arrows 0
pass2_system len 3317 sha256 843ce6e79ea264ca15aee431bae877e2bf78d8c3d9bfb6c387d0325f9c863e7a arrows 2
python 3.14.4
```

Both agree with the figures the programmer and the reviewer measured independently.

### The two counts, with their units

**Accuracy — of assertions.** **27 of 27 distinct asserted values match an
independently derived expectation; 0 of 27 came from the code's output.** (The 17 tests
hold more `assert` statements than that; 27 is the count of distinct *expected values*,
each a row above. Each row names its source.)

**Coverage — of the functions and branches this unit added**, measured, not estimated:

| Unit | Added by `P14f` | Touched by a test |
|---|---|---|
| functions | 1 (`name_unencodable_characters`) | **1 of 1** |
| statements in it | 2 (`:1186`, `:1187-1188`) | **2 of 2** |
| branch arcs in it | 2 (the `isinstance` test, True and False) | **2 of 2** |
| module-level lines added | `import io`, `:1169` constant, `:1172` def | **3 of 3** |
| call sites | 2 (`:1195`, `:1196`) | **2 of 2** |

Commands:
`-m pytest -q tests/unit/test_session_extraction_console.py --cov=ingestion.session_extraction --cov-branch --cov-report=json` → of lines 1155-1199, executed `[1169, 1172, 1185, 1186, 1187, 1188, 1191]`, and **no missing branch in that range** (the only partial arcs reported are at `:1199`, `main`'s pre-existing subcommand dispatch, which this unit did not add). The two call sites `:1195-1196` are exercised **behaviourally** by the three subprocess tests, which a coverage meter in the parent process cannot see; running my file together with `tests/unit/test_session_extraction.py` reports them executed with **no missing line in 1155-1199**.

The module as a whole is 82.4% of statements with both files, which is not this unit's
figure and is not claimed as one.

## What I did not do

- **I did not test against `extractions/WMT.json`.** It is not in git, the assignment
  forbids editing or deleting it, and a test keyed to it would pass only on this machine.
  The 82-line figure in the assignment is a property of that file, not of the code; the
  line-count **identity** my tests assert is the general statement of it and it holds for
  any session.
- **I did not add a `*_rule3_red.py` file.** Nothing here defaults where it should stop.
- **I did not fix backlog item 124**, and did not touch `ingestion/session_extraction.py`.
- I did not write an end-to-end test for `plan`, `locate` and `text`. They print through
  the same two streams, and `test_main_sets_the_handler_before_it_parses_argv` proves the
  handler is set before argparse picks a subcommand, so all six are covered by that one
  ordering fact rather than by three more PDF-building subprocess tests.

## Findings for the orchestrator

1. **`pytest-randomly` is not installed, so `-p no:randomly` is a no-op and this
   repository has no random test order.** Measured:
   `importlib.metadata` lists exactly `pytest` and `pytest-cov`; `-p randomly` →
   `ImportError: No module named 'randomly'`; `--randomly-seed=1` →
   `error: unrecognized arguments`. **This matters beyond my criterion 13.** Every gate
   command in the assignments, in `docs/8-build/environment.md` and in three journal
   entries carries `-p no:randomly`, which reads as "I pinned the order against a
   shuffler". There is no shuffler. The suite has always run in collection order here,
   so **order dependence between test files is currently untested in this repository** —
   and backlog item 124 is precisely an order-dependent side effect. Two ways to close
   it, and an assignment could be written from either: install `pytest-randomly` and pin
   a seed in the gate, or drop `-p no:randomly` from the documented commands and say
   plainly that the order is collection order. The first is the one that would have
   caught item 124 automatically. **It is not a defect of `P14f`** — the flag predates
   it — but `P14f`'s own assignment asks for a measurement that cannot be taken.
2. **Backlog item 124 is live and my tests had to be written around it.**
   `tests/unit/test_session_extraction.py:1180` calls `main()` in-process, and
   `_pytest.capture.CaptureIO` is an `io.TextIOWrapper` subclass, so
   `errors='namereplace'` stays on pytest's captured stdout for every test that runs
   after it in the same process. Harmless today and I did not fix it (it needs the
   code). The cost is visible in my file: **no test of `main` could be written
   in-process**, so three of my seventeen spend a subprocess each. If item 124 is closed
   by restoring the handler in a `finally`, those three can become ordinary in-process
   tests and the file gets faster — worth noting in that item.
3. **The reviewer's F1 now has the consumer it was missing.** F1 said
   `name_unencodable_characters` returns a `bool` no caller reads while the docstring
   promises one will. Three of my tests read it
   (`is True` on a cp1252 wrapper, `is True` on a utf-8 one, `is False` on a
   `StringIO`), which is the first of the two fixes the reviewer offered. The docstring
   sentence is now true. **No code change is needed for F1**; it can be closed.
4. **The `check` subcommand's ellipsis is the only cp1252-encodable non-ASCII character
   my end-to-end tests could hold it to.** If backlog item 122 (`cli.py --debug`, the
   same defect on route A, after the paid call) is given the same two calls, the test
   pattern in my file transfers directly: build the child with an explicit
   `PYTHONIOENCODING`, assert on bytes, and assert the named escape rather than the exit
   code. The three mutants `replace`, `ignore` and "calls deleted" are the measurement
   that proves it; a returncode-only test is green under two of the three.

## Verdict

`pass`.

Every value in scope matches an expectation that existed before the code ran — the
`namereplace` contract and the Unicode name of `U+2192`, the cp1252 code chart, the
UTF-8 encoding rule worked out by hand, four identities, and two digests I measured
myself in `git archive 0bc41a1`. **27 of 27 expected values are independently sourced;
0 came from the code's output.** The one function the unit added is covered at **1 of 1
function, 2 of 2 statements, 2 of 2 branch arcs**, and both call sites are exercised.
The single stop path — a detached stream — is locked by type and by a message naming
`detach`. **No stop path defaults instead of raising**: the one `False` branch is not a
defaulted figure, it is the statement that a stream which never encodes cannot lose a
character, and my test asserts that property rather than the return value alone.

The measurement the unit turns on holds: `namereplace` → `replace` and `namereplace` →
`ignore` each turn **8 of my 17 tests red while the command still exits 0**, and
deleting the two calls turns **5** red. A suite that asserted only the exit code would
have been green on two of those three.

One criterion, 13, could not be measured as written, because the random order it names
does not exist on this machine. I measured order-independence by explicit permutation
instead and reported the gap as finding 1 rather than deciding it away.
