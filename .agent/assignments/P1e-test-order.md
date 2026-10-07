---
id: P1e-test-order
phase: 1 — the gates
agent: programmer
depends_on: [P14f-prompt-encoding, P3d-invisible-year, P14g-unit-statement-pages]
---

# Install a test-order guard, and close the one order leak already recorded (items 127, 124)

## Objective

**Fact 1.** `pytest-randomly` is not installed. Measured on 2026-10-07:

```
.venv/Scripts/python.exe -c "import importlib.metadata as m; print(sorted(
  d.metadata['Name'] for d in m.distributions() if 'pytest' in (d.metadata['Name'] or '').lower()))"
['pytest', 'pytest-cov']
```

`requirements-dev.txt` lists `pytest`, `pytest-cov`, `ruff` and `mypy`, and nothing else.

**What follows.** Every run of this suite uses **one** fixed order. A test that passes only
because another test ran first passes forever, and the gate reports it green. Backlog item
127.

**Fact 2, and it is a live example rather than a worry.** Backlog item 124, found by the
`P14f-prompt-encoding` review on 2026-10-06. `ingestion/session_extraction.main()` sets the
error handler on `sys.stdout` and `sys.stderr` to `namereplace` and never restores it.
`_pytest.capture.CaptureIO` **is** an `io.TextIOWrapper` subclass, so that handler leaks
into every test that runs after it in the same process, and
`tests/unit/test_session_extraction.py:1180` calls `main()` in-process.

**Measured harmless today**: the gate passes either way. It is recorded because **the next
test that asserts on an encoding failure would pass or fail by test order**, and nothing
would say which. The `P14f` tester worked around it with three subprocesses and by
permutation, and wrote both workarounds down.

**Fact 3.** The user decided this on 2026-10-07, choosing option `a` over a pinned seed and
over leaving it: **install `pytest-randomly`.** The user's own framing, carried from the
queue: "It may turn tests red the first time it runs, **which is the point**."

**What follows.** When this unit is done, the suite runs in a different order every time,
every order-dependent failure is named, and the leak in fact 2 is closed without undoing
`P14f-prompt-encoding`.

## Do not start this unit beside another one

**This is the one scheduling rule this unit carries and it is not a preference.**
Installing `pytest-randomly` changes the result of **every** gate command in this
repository, for every unit, at once. A unit measuring its own gate in the same working tree
while this one installs a plugin gets a number that means nothing.

**Before your first command, run `git status` and read `.agent/QUEUE.md`. If any unit is
`building`, stop and say so.** The queue records why: on 2026-10-05 two units shared this
working tree and the failing count moved between two runs eight minutes apart, so neither
unit's gate figure meant anything.

## The trap in this unit, stated first

**A red test is the output of this unit, not a failure of it.** The user chose this option
knowing it turns tests red. So the wrong move here is the comfortable one: reaching for
`-p no:randomly`, or pinning a seed, or deleting an assertion, to get a green line.

**Three things are forbidden and each one would look like success:**

1. **Do not put `-p no:randomly` in any command, any document, or any config file.** It was
   deleted from nine documents on the user's decision of 2026-10-07 (item 126) because it
   asserted nothing when no plugin was installed. **Once the plugin is installed that flag
   stops being a no-op and starts being a way to switch the guard off.** Adding it back
   would turn a harmless string into a real defeat of the thing this unit installs.
2. **Do not pin a default seed** in a config file so every run repeats one order. The user
   was offered that as option `b` and did not choose it.
3. **Do not weaken or delete a test to make it pass under shuffling.** A test that fails
   under a new order has found something. Name it and hand it to the tester.

**For a measurement that must be repeatable, use `--randomly-seed=<n>` on that one command
and name the seed in your entry.** That is reproducibility. It is not a default.

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-07, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`, at
commit `0a9ed51`, **before this unit installs anything**:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1257 passed, 2 skipped, 0 failed** |
| full suite | `-m pytest -q` | **2 failed**, the two red on purpose, by name |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 2 errors in 2 files, 21 checked |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.claude/check_guard.py` | 48/48 |

**Those seven figures are the "before" of this unit.** Take them yourself at `HEAD` first.
If one disagrees, stop and report the disagreement rather than editing anything.

**What `P14f-prompt-encoding` established, which fact 2's fix must not undo.** Accepted at
`c9cb45e` on 2026-10-07, closing item 113:

- `-m ingestion.session_extraction prompt extractions/WMT.json --filing 0 --pass 2` exits
  **0** with **82** lines on a Windows console, where it exited 2 after 19 lines before.
- `main()` sets **only the error handler**, to **`namereplace`**, and leaves the encoding
  alone, so a UTF-8 console is not degraded.
- The handler is `namereplace` and not `replace` or `ignore` **on purpose**: the console
  prints `\N{RIGHTWARDS ARROW}`, so a reader can see a character was there and which one.
  The `P14f` tester measured that under `replace` and under `ignore` the command **still
  exits 0**, so an exit-code-only test is green on two of three mutants.
- **No prompt byte moved**, and three agents computed the digests separately:
  `pass2_system` length 3317, `843ce6e7…`, two arrows.

## What to do

1. **Record the "before" at `HEAD`**, all seven figures in the table above, with your own
   commands.
2. **Add `pytest-randomly` to `requirements-dev.txt` and install it.** Record the version
   it resolves to. Say nothing about what it will find until you have run it.
3. **Run the gate form at five named seeds**, and record the failing set **by name** for
   each one. Not a count: item 127 exists because a count hides which test moved. Use
   `--randomly-seed=<n>` with five seeds you name, and run the plain shuffled form too.
4. **Separate what you found into two lists**, and put both in your entry:
   - failures whose cause is in code you may edit, and
   - failures whose cause is in `tests/`, which the tester fixes.
   **A failure you cannot place goes in the second list with what you know.** Do not guess.
5. **Close fact 2 without undoing `P14f`.** `main()` must stop leaving a changed error
   handler on a stream it did not own, **and** every one of the four `P14f` facts above must
   still hold. Two shapes are plausible, restoring the handler or setting it under a
   `__main__` guard, and they are not equivalent: a `__main__` guard does not run for an
   in-process caller, and `cmd_prompt` redirects to `sys.stderr`. **Choose with a reason and
   execute both halves.** If a `P14f` test goes red because it asserts the handler is still
   set after `main()` returns, **that is a finding for your entry and for the tester, not a
   test for you to edit.**
6. **Re-run the same five seeds after your fix** and show what moved, by name.
7. **Say what the plugin changed beyond order.** `pytest-randomly` also reseeds the random
   number generators before each test. This repository uses `numpy`. **Measure whether any
   test's figures depend on that**, and name any that do.
8. **Record what you find, do not widen your scope.** A defect outside this list goes in
   your entry under "Found". The overall lead puts it in the backlog.

## Files in scope

- `requirements-dev.txt`
- `ingestion/session_extraction.py`

**Nothing else.** A change not traced to item 127 or item 124 is a review finding, even if
the change is good.

## Out of scope

- **`tests/`.** The write guard denies it. **Every order-dependent test failure is the
  tester's**, and this unit's tester assignment is written after the code review. Hand each
  one over by name.
- **`docs/8-build/environment.md`**, which owns what each dev dependency is for and how it
  is run. The overall lead writes it. Name in your entry what it needs to say.
- **`STATUS.md`**, `.agent/QUEUE.md`, `docs/` and `.claude/`. The overall lead owns them.
- **The two tests that are red on purpose.** Leave both red. They are
  `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`
  and `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`.
- **Backlog items 123 and 125** in `ingestion/session_extraction.py`. Both recorded. Item
  123 is `name_unencodable_characters` returning a `bool` the call site discards; item 125
  is the inherited `surrogateescape` handler being replaced rather than composed. **Item
  125 is adjacent to your fix. If your chosen shape closes it, say so and claim it. Do not
  widen to it on purpose.**

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`. Use `PYTHONIOENCODING=utf-8` for any
command that prints a prompt.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | No other unit was in flight | `git status` clean of another unit's files, and no `building` row in `.agent/QUEUE.md` | quote both |
| 2 | The "before" is recorded | the seven figures, taken by you at `HEAD` | the commands above |
| 3 | The plugin is installed and declared | `pytest-randomly` in `requirements-dev.txt`, and the installed version named | `importlib.metadata`, and the file |
| 4 | The order really changes | two runs produce two different orders | name the first three tests of each, or the seed line `pytest` prints |
| 5 | Five named seeds, failing set **by name** for each | a table: seed, failing test names. **Never a count alone** | `--randomly-seed=<n>` |
| 6 | The findings are split into two lists | what you can fix, and what the tester must | your entry |
| 7 | Item 124 is closed | `main()` leaves no changed error handler on a stream it did not own | execute it: call `main()` in-process and read the handler before and after |
| 8 | `P14f` does not regress | `prompt --pass 2` exits **0** with **82** lines and two `\N{RIGHTWARDS ARROW}`; the encoding is unchanged; `pass2_system` is length 3317, `843ce6e7…`, two arrows | run all four |
| 9 | The same five seeds after the fix | the table again, and what moved, by name | criterion 5's commands |
| 10 | What the plugin changed beyond order | any test whose figures depend on the reseeded generators, named; or "none, and here is how I looked" | your measurement |
| 11 | `-p no:randomly` appears nowhere | zero matches outside the journal and accepted assignments, which record what was run | `grep -rn "no:randomly" --include=* .` and read each hit |
| 12 | No default seed is pinned | no config file sets one | say where a seed could be set, and show it is not |
| 13 | Lint | 4 errors, every one `BLE001`. **Run `ruff check .` after your last edit** | `-m ruff check .` |
| 14 | Types | 2 errors in 2 files, or fewer. Name any you removed | the mypy command above |
| 15 | Census | 64, or fewer. Name any site you removed | the grep at `docs/2-rules/rules.md:102` |
| 16 | Route | 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` |
| 17 | The write guard | 48/48 | `.claude/check_guard.py` |

**There is no "0 failed" criterion here and that is deliberate.** The user chose the option
that turns tests red. **Criterion 5 replaces it**: the measurement this unit owes is the set
of failing names at each seed, not a green line. A unit that reports green by switching the
guard off has produced nothing.

## Citations

- `docs/9-reference/refactor-backlog.md`, item 127 (the absent guard) and item 124 (the
  live example).
- The user's decision of 2026-10-07, option `a`: install `pytest-randomly`.
- `.agent/assignments/P14f-prompt-encoding.md` — what `main()` does and why, and the four
  facts your fix must not undo.
- `.agent/journal/2026-10-06T2212-code_reviewer-p14f-prompt-encoding.md` — F2, which found
  item 124.
- `.agent/journal/2026-10-06T2312-tester-p14f-prompt-encoding.md` — the three subprocesses
  and the permutation it used to work around item 124, and the `replace` and `ignore`
  mutants that still exit 0.
- `requirements-dev.txt` — where the dependency goes.
- `.claude/agents/programmer.md` — your role card.

## Known open items

- **Never mutate a file in this repository, not even briefly.** A spot check left a
  `return []` in `ingestion/claude_extractor.py` on 2026-10-05 with a comment saying it had
  been restored. It had not, and a check was dead for about ten hours. Work in a scratch
  copy under `C:\tmp` and print the repository file's sha256 before and after.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- **Installing a package changes the shared `.venv`.** That is the one effect of this unit
  no scratch copy contains, which is why the scheduling rule above exists. Name the version
  you installed, so it can be undone.
- The suite takes about 135 to 225 seconds, and this unit runs it at least eleven times.
