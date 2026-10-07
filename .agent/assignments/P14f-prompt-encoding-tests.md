---
id: P14f-prompt-encoding-tests
phase: 14 — the Pass 1 and Pass 2 roles
agent: tester
depends_on: [P14f-prompt-encoding]
---

# Lock the console that cannot lose a character (item 113)

## Objective

`P14f-prompt-encoding` is the unit that stops `session_extraction prompt --pass 2`
failing on a Windows console. Its code reviewer approved it, round 1, with three `note`
findings and nothing blocking. You are its tester. **Its code is not committed.** One
file changed: `ingestion/session_extraction.py`, 47 insertions and 0 deletions.

**Fact 1, the defect.** `-m ingestion.session_extraction prompt extractions/WMT.json
--filing 0 --pass 2` exited **2** after 19 lines with
`'charmap' codec can't encode character '→' in position 2992`. The two arrows are at
`ingestion/claude_extractor.py:412-413`, inside the Pass 2 prompt's `direction` rules. So
route B's reader could not see the Pass 2 prompt on this machine, and the
`extract-filing` skill sends a session to that command as step 3.1.

**Fact 2, what the unit does.** `main()` calls one function on `sys.stdout` and
`sys.stderr` before it parses argv. That function sets **only** the error handler, to
**`namereplace`**, and leaves the encoding alone. The command now exits **0** with **82**
lines, and line 67 reads:

```
        "add_back" = one-time EXPENSE that inflated costs \N{RIGHTWARDS ARROW} remove to get clean earnings
```

**Fact 3, the choice that matters and the one you must hold in place.**
`namereplace`, not `replace`. The reviewer measured it:
`'arrow → sur \udcff ctrl \u0085 end'` encodes to
`b'arrow \\N{RIGHTWARDS ARROW} sur \\udcff ctrl \\x85 end'`. **`namereplace` is never
silent.** `replace` would print `?` and the reader could not tell which character was
there, or that one was there at all. A later change from `namereplace` to `replace` would
pass every test that only checks the exit code. **Your tests must make that change fail.**

**Fact 4, the boundary this unit must never cross.** The two arrows are prompt text that
route A sends the model. `AGENTS.md` makes any change to the LLM boundary an escalation.
The programmer's criterion 5, re-computed independently by the reviewer, is that **12 of
12 prompt digests are identical** across both trees: 3 filings × 2 passes × system and
user, with Pass 2's system prompt at `843ce6e7…`, length 3317, on both sides.

**What follows.** When this unit is done, a test holds the exit code, a test holds the
visible escape, a test holds that `replace` would not do, a test holds that a UTF-8
console is not degraded, and a test holds that no prompt byte moved.

## The trap this unit is most likely to fall into

**Read the first section of `.claude/agents/tester.md` before you write a line.** There is
no benchmark here, so the cheapest test to write is one that runs the code, reads what it
printed, and asserts that. **A test written that way verifies nothing and passes
forever.**

Three traps have already caught work in this repository:

1. `P3b`'s first CLI stop test ran `cli.py` through `runpy.run_path`, which executes the
   file into a fresh namespace, so a patch on the `cli` module was never the name that
   namespace bound and the assertion **could not fail** (backlog item 98).
2. `P1d`'s real-filing test asserted "no failures" twice and nothing else, so it passed
   with the check it tested replaced by `return []`.
3. **The reviewer of this very unit caught one in its own work, and you can meet the same
   one.** Its first digest comparison failed to import in **both** trees, so the `diff`
   of two empty outputs was trivially empty and the criterion looked green. It re-ran with
   `PYTHONPATH` set and confirmed 13 non-empty lines on each side. **Two empty results are
   not a match. Assert that each side produced something before you compare them.**

**A fourth trap belongs to this unit alone.** A test that asserts only
`returncode == 0` is green under `replace`, under `backslashreplace`, under
`xmlcharrefreplace` and under `ignore` — and `ignore` deletes the character outright.
**The exit code is the weakest assertion available here.** Assert on the rendered text.

## What is already true — verify, do not redo

Measured by the overall lead and re-run by the code reviewer on 2026-10-06, on the
**Windows** machine (`.venv/Scripts/python.exe`, Python 3.14.4), with
`ANTHROPIC_API_KEY= GEMINI_API_KEY=` and **no `PYTHONIOENCODING` set**:

| Fact | Result |
|---|---|
| gate | **1207 passed, 2 skipped, 0 failed**, failure set `{}` on both sides, compared by name |
| lint | 4 errors, every one `BLE001` |
| types | 5 errors in 2 files, 21 checked |
| census | 64 |
| route | 200 |
| guard | 48/48 |
| `prompt --pass 2`, before | exit **2**, 19 lines |
| `prompt --pass 2`, after | exit **0**, 82 lines |
| the mutation: the two calls deleted | exit **2**, 19 lines, the identical `charmap` message |
| all six subcommands, after | 6 of 6 at exit 0; the five that already passed are **byte-identical** |
| the encoding | `cp1252 surrogateescape` → `cp1252 namereplace`. **The encoding does not move** |
| em dash and ellipsis byte counts | identical before and after, for all six subcommands |
| criterion 6, with `PYTHONIOENCODING=utf-8` | byte-identical to `HEAD`'s output, `U+2192` count 2, `\N{` count 0 |

`ingestion/session_extraction.py` is sha256 `58b05fef…`. `ingestion/claude_extractor.py`
is `b459e4ee…` and `extractions/WMT.json` is `c436e427…`; neither is this unit's and
`WMT.json` is not in git. **Do not edit or delete it.**

## What to do

1. **Hold the exit code and the line count**, for `prompt --pass 2`, with no
   `PYTHONIOENCODING` set.
2. **Hold the visible escape.** The rendered output contains `\N{RIGHTWARDS ARROW}` on the
   two `direction` lines. This is the assertion that makes `replace` fail.
3. **Hold the handler itself, not only its effect.** A test that reads
   `sys.stdout.errors` after the function runs is cheap and names the choice. Pair it with
   step 2: the first says what was chosen, the second says why it matters.
4. **Hold that the encoding is not changed.** Before and after, the encoding is the same
   name. A fix that reached UTF-8 by changing the encoding would pass steps 1 and 2 and
   break a console that cannot display it.
5. **Hold that a UTF-8 console is not degraded.** With `PYTHONIOENCODING=utf-8`, the
   output holds `→` itself and zero `\N{` escapes.
6. **Hold the LLM boundary.** `pass1_prompts` and `pass2_prompts` return the same bytes
   as before this unit. Hash them. **Assert that each hash is non-empty before comparing**,
   per trap 3 above. If you cannot build a "before" value without the `HEAD` tree, pin the
   Pass 2 system prompt's digest and length as literals: `843ce6e7…`, 3317.
7. **Hold the five subcommands that already worked.** None of their output moved.
8. **Mutate, and show each test goes red.** At least: `namereplace` → `replace`;
   `namereplace` → `ignore`; the two calls deleted. **Mutate a scratch copy only.** Print
   the repository file's sha256 before and after.
9. **Record what you find, do not widen your scope.** A defect outside this list goes in
   your entry under "Found".

## Files in scope

- `tests/` — any file under it.

**Nothing else.** The write guard denies everything else to you.

## Out of scope

- **`ingestion/session_extraction.py`.** It is the unit's code and it is approved. If you
  believe it is wrong, **that is a finding: write it and stop.** Do not edit it.
- **Backlog item 122**, `cli.py --debug` carrying the same defect on route A, where it
  stops **after** the paid API call. Recorded, and a unit of its own.
- **Backlog items 123, 124 and 125**, the review's three `note` findings. **Item 124 is
  the one you must not trip over**: `main()` changes a process-global stream handler and
  never restores it, and `tests/unit/test_session_extraction.py:1180` calls `main()`
  in-process. `_pytest.capture.CaptureIO` is an `io.TextIOWrapper` subclass, so the
  handler leaks into every test that runs later in the same process. It is harmless today
  and the gate is unchanged either way. **Write your tests so they do not depend on test
  order**, and say in your entry how you did it. Do not fix item 124; it needs the code.
- **The two tests that are red on purpose.** Leave both red.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`. **Run every criterion with no
`PYTHONIOENCODING` set**, except criterion 7.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | Your own baseline, before you write anything | the failing set, by name | the gate command, names captured to a file |
| 2 | The failing set is empty when you finish | `{}` | the same command, sets compared by name |
| 3 | The full suite shows only the two deliberate failures | exactly those two names | `-m pytest -q -p no:randomly` |
| 4 | The exit code and the line count are held | by test | step 1 |
| 5 | The visible escape is held | by test | step 2 |
| 6 | The handler and the encoding are both held | by test | steps 3 and 4 |
| 7 | A UTF-8 console is not degraded | by test | step 5, with the variable set |
| 8 | No prompt byte moved | 12 digests, or the two pinned literals, and **each asserted non-empty first** | step 6 |
| 9 | The five other subcommands are unmoved | by test | step 7 |
| 10 | **`replace` fails** | your tests go red | mutation, scratch copy, tests named |
| 11 | **`ignore` fails** | your tests go red | mutation, scratch copy, tests named |
| 12 | **The two calls deleted fails** | your tests go red | mutation, scratch copy, tests named |
| 13 | Your tests do not depend on test order | the same result with `-p no:randomly` and with the default random order, run twice | run both |
| 14 | Lint | 4 errors, every one `BLE001`. **Run `ruff check .` after your last edit**, not over your own files | `-m ruff check .` |
| 15 | Nothing outside `tests/` changed | `git diff --stat -- . ':(exclude)tests'` holds only `ingestion/session_extraction.py`, at 47 insertions and 0 deletions | before and after |
| 16 | Accuracy and coverage, with their units | "N of N assertions hand-sourced, 0 from the code's output", and the branch coverage of the behaviours you named | `--cov` on the modules your tests name |

**Every criterion is a measurement, never an opinion.** Criteria 10 and 11 exist because
the exit code alone is green under four different error handlers, one of which deletes the
character.

## Citations

- `.claude/agents/tester.md` — your role card.
- `.agent/assignments/P14f-prompt-encoding.md` — the unit.
- `.agent/journal/2026-10-06T1655-programmer-p14f-prompt-encoding.md` — the programmer.
- `.agent/journal/2026-10-06T2212-code_reviewer-p14f-prompt-encoding.md` — the review,
  with its own digest computation and the `namereplace` encode measurement.
- `docs/9-reference/refactor-backlog.md`, items 113, and 122 to 125.
- `AGENTS.md`, "Escalate, do not decide alone" — the LLM boundary.

## Known open items

- **Backlog item 98**: `runpy.run_path` executes a module into a fresh namespace.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- **`extractions/WMT.json` is not in git.** Do not edit it and do not delete it.
- The suite takes about 135 seconds.
