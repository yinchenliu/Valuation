---
agent: programmer
assignment: P1e-test-order
round: 1
status: complete
files_touched: [requirements-dev.txt, ingestion/session_extraction.py]
verdict: n/a
---

# P1e-test-order — install `pytest-randomly`, name what shuffling finds, close item 124

> Opened before the first command. Filled as each result landed.

## What I did

`pytest-randomly` **5.0.0** is installed into the shared `.venv` and declared in
`requirements-dev.txt`, so every `pytest` run in this repository now uses a fresh random
order and prints the seed it used. I ran the gate form at **five named seeds — 1, 2, 3, 124
and 127 — plus an unseeded run, before and after the code change**, and recorded the failing
set **by name** each time. **Before the change the failing set is empty in all six orders.**
`ingestion/session_extraction.main()` no longer leaves a changed error handler on
`sys.stdout` and `sys.stderr`: a context manager reads each stream's handler, sets
`namereplace` for the body, and puts the original back in a `finally`. That closes backlog
item 124, measured in-process against a `git archive` of `HEAD` side by side. All four
`P14f-prompt-encoding` facts still hold, re-run on the final code. **The fix turns three
`P14f` tests red in every order, because those three assert the leak itself** — the exact
case the assignment told me to hand to the tester rather than edit, and `tests/` is
untouched.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | No other unit was in flight | **pass** | `git status`: one modified file, `.agent/QUEUE.md`, this unit's own row. `.agent/QUEUE.md`: rows 0–6i `accepted`, row 6j `building` (this unit), rows 7–9 `planned`; **no other row is `building`, `ready` or `rework`**. Quoted in full below |
| 2 | The "before" is recorded | **pass**, with one disagreement measured and explained | seven figures, table below |
| 3 | The plugin is installed and declared | **pass** | `pytest-randomly` **5.0.0**; `importlib.metadata` prints `[('pytest','9.1.1'),('pytest-cov','7.1.0'),('pytest-randomly','5.0.0')]`; `requirements-dev.txt` lists it |
| 4 | The order really changes | **pass** | four unseeded runs printed four different seeds; first-three tests differ; two named seeds give two different first files |
| 5 | Five named seeds, failing set by name | **pass** | seeds 1, 2, 3, 124, 127 + unseeded. **Failing set empty in all six** |
| 6 | Findings split into two lists | **pass** | both lists below. List A (mine to fix) is **empty**; list B (the tester's) holds **3** named tests |
| 7 | Item 124 is closed | **pass** | `main()` called in-process on a stream it does not own: `HEAD` → `strict` then `namereplace` (**LEAKED**); this tree → `strict` then `strict` (**RESTORED**) |
| 8 | `P14f` does not regress | **pass**, all four run on the final code | exit **0**, **82** console lines, **2** `\N{RIGHTWARDS ARROW}`; `('cp1252','namereplace')` at every write and the encoding unmoved; no lossy substitute present; `pass2_system` **3317** / `843ce6e7…` / **2** arrows |
| 9 | The same five seeds after the fix | **pass** | the same three names fail at every one of the six orders; nothing else moved |
| 10 | What the plugin changed beyond order | **pass — none, and here is how I looked** | it reseeds `random` and `numpy.random` (measured); **zero RNG call sites outside `.venv`**; 1367 tests pass under six different global seeds |
| 11 | `-p no:randomly` appears nowhere | **pass** | every hit read, below. Five hits in live documents, all prose *about* the flag; the rest are journal entries and accepted assignments. **No command, no config file** |
| 12 | No default seed is pinned | **pass** | no `pytest.ini`, `setup.cfg`, `tox.ini`, `pyproject.toml` or root `conftest.py`; no `addopts` anywhere; `PYTEST_ADDOPTS` empty; and four unseeded runs printed four different seeds |
| 13 | Lint | **pass** | `ruff check .` after the last edit → **4 errors, every one `BLE001`**, the same four sites |
| 14 | Types | **pass** | **2 errors in 2 files**, 21 checked — the same two. None removed, none added |
| 15 | Census | **pass** | **64** |
| 16 | Route | **pass** | **200** |
| 17 | Write guard | **pass** | **48/48 guard cases correct** |

---

## Log, in order

### Criterion 1 — no other unit was in flight

`git status` at the first command:

```
On branch main
Your branch is ahead of 'origin/main' by 6 commits.
Changes not staged for commit:
	modified:   .agent/QUEUE.md
no changes added to commit
```

The one modified file is `.agent/QUEUE.md`, and the modification is this unit's own row set
to `building` (row 6j). **No other unit's file is modified.** `HEAD` was `47a5bd9`.

`.agent/QUEUE.md`, every row's state: rows 0 through 6i `accepted`; row 6j
(`P1e-test-order`) `building` — this unit; rows 7, 8 and 9 `planned`. **No other row is
`building`, `ready` or `rework`.** The header says the same in words: "Every unit through
`P14g-unit-statement-pages` is `accepted`, and no subagent is in flight."

**The session ended mid-unit and the overall lead restarted it.** `HEAD` is now `8c0d526`.
`git show --stat 8c0d526` touches `.agent/QUEUE.md` and `docs/9-reference/refactor-backlog.md`
only — no `.py` file and no test — so the criterion 2 figures, taken at `47a5bd9`, still
describe this tree. Everything from criterion 3 on was run against `8c0d526` plus this unit's
two edits.

### Criterion 2 — the "before", taken by me at `47a5bd9`

| Fact | Result | Assignment's table (at `0a9ed51`) |
|---|---|---|
| gate `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1370 passed, 2 skipped, 0 failed**, 125.91s | 1257 passed, 2 skipped, 0 failed |
| full suite `-m pytest -q` | **2 failed, 1370 passed, 2 skipped**, 144.62s | 2 failed |
| the two failures, by name | `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` | the same two |
| lint `-m ruff check .` | **4 errors, every one `BLE001`** — `api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106` | 4, every one `BLE001` |
| types | **2 errors in 2 files**, 21 checked — `analysis/projector.py:395`, `api/routes_upload.py:28` | 2 in 2 files, 21 checked |
| census (the grep at `rules.md:102`) | **64** | 64 |
| route `TestClient(app.app, raise_server_exceptions=False).get('/')` | **200** | 200 |
| guard `.claude/check_guard.py` | **48/48 guard cases correct** | 48/48 |

**One figure disagreed, and I measured the cause rather than assuming it.** The gate's pass
count is 1370 here against the assignment's 1257. The assignment's table names the commit it
was taken at — `0a9ed51` — and `47a5bd9` is two commits later, the second being `309a797`,
`P14g-unit-statement-pages` and its tests. I counted collection in both trees rather than
reading `STATUS.md`'s claim that `P14g` added 113:

```
47a5bd9, in the repository:                       -m pytest -q --collect-only --ignore-glob="*_rule3_red.py"  ->  1372 collected
0a9ed51, in C:\tmp\p1e_0a9ed51 (git archive):     the same command                                            ->  1259 collected
```

1372 − 1259 = **113**, exactly `P14g`'s 113, and 1257 + 113 = 1370. The other six figures
agree exactly, which is what makes the one disagreement readable. **So the disagreement is
the assignment's table being two commits old, not this tree being something other than
`HEAD`.** I did not stop on it. Finding F1 below.

### Criterion 3 — the plugin is installed and declared

```
.venv/Scripts/python.exe -m pip install pytest-randomly   ->  Successfully installed pytest-randomly-5.0.0
importlib.metadata, after:   [('pytest', '9.1.1'), ('pytest-cov', '7.1.0'), ('pytest-randomly', '5.0.0')]
importlib.metadata, before:  ['pytest', 'pytest-cov']          (the assignment's fact 1, re-measured)
```

**Installed version: `pytest-randomly` 5.0.0.** `requirements-dev.txt` now lists it between
`pytest-cov` and `ruff`. **To undo this unit:** `pip uninstall pytest-randomly` and delete
that one line.

### Criterion 4 — the order really changes

Two unseeded runs, each with its own seed line and its first three tests:

```
run 1  tests/unit/test_p15a_two_routes.py::test_cli_help_documents_gemini_default_and_session_file
       tests/unit/test_p15a_two_routes.py::test_resolve_provider_claude_stops_and_names_route_b_and_remedies[claude-3-7-sonnet]
       tests/unit/test_p15a_two_routes.py::test_cli_refuses_dash_p_claude
       Using --randomly-seed=2499748579

run 2  tests/unit/test_pass1_printed_lines.py::test_an_absent_year_key_stops_route_a_naming_year_and_field[tax_expense]
       tests/unit/test_pass1_printed_lines.py::test_a_line_that_is_not_an_object_stops_naming_field_year_and_line[string]
       tests/unit/test_pass1_printed_lines.py::test_a_malformed_line_stops_route_b_naming_file_filing_field_year_and_line[value null]
       Using --randomly-seed=1631738109
```

Different files first, different tests first, different seed. Four unseeded runs across this
unit printed four different seeds: `2499748579`, `1631738109`, `2580582436`, `4142695305`,
and a fifth, `2583387543`, on the final full-suite run.

Tied to a named seed, so it is reproducible and not merely different:

```
--randomly-seed=1  ->  tests/unit/test_routes_session.py::test_valuation_on_a_cache_hit_shows_the_session_label (and two more from that file)
--randomly-seed=2  ->  tests/unit/test_normalizer_year_stop.py::test_a_balance_sheet_year_does_not_count_as_a_statement_year (and two more from that file)
```

**The plugin shuffles whole files as well as the tests inside a file**, which is the class
item 127 is about.

### Criterion 5 — five named seeds, the failing set BY NAME, before the item 124 fix

`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe -m pytest -q --randomly-seed=<n> --ignore-glob="*_rule3_red.py"`

| Seed | Failing set, **by name** | Summary line |
|---|---|---|
| 1 | **{ } — empty** | `1370 passed, 2 skipped, 2 warnings in 128.46s` |
| 2 | **{ }** | `1370 passed, 2 skipped, 2 warnings in 127.89s` |
| 3 | **{ }** | `1370 passed, 2 skipped, 2 warnings in 128.43s` |
| 124 | **{ }** | `1370 passed, 2 skipped, 2 warnings in 130.10s` |
| 127 | **{ }** | `1370 passed, 2 skipped, 2 warnings in 127.43s` |
| unseeded, `Using --randomly-seed=2580582436` | **{ }** | `1370 passed, 2 skipped, 2 warnings in 127.10s` |

**Six shuffled orders; the failing set is empty in all six.** That is the measurement this
unit owes, and it is not the result the user's framing anticipated ("it may turn tests red
the first time it runs"). It did not. What that does and does not prove is below.

### Criterion 7 — item 124 is closed, by execution

**Before.** `C:\tmp\p1e_leak\leak_demo.py` installs an `io.TextIOWrapper` it owns as
`sys.stdout` and `sys.stderr` — the same kind of object `_pytest.capture.CaptureIO` is,
printed as `True` by the script — calls `main(["check", "no-such-session-file.json"])`
**in-process**, and reads `stream.errors` before and after. Run against a `git archive` of
`HEAD` in `C:\tmp\p1e_head` and against this tree, from the one script:

```
### HEAD (C:\tmp\p1e_head\ingestion\session_extraction.py) ###
CaptureIO is an io.TextIOWrapper subclass: True
handler before main(): strict
handler after  main(): namereplace
LEAKED

### this tree, after the fix ###
handler before main(): strict
handler after  main(): strict
RESTORED
```

**And the handler is still on for the whole command**, measured from inside rather than
inferred from the output. `C:\tmp\p1e_leak\inside_main.py` installs an `io.TextIOWrapper`
subclass that records its own `(encoding, errors)` at every `write`:

```
### this tree ###                                   ### HEAD ###
writes recorded: 2                                  writes recorded: 2
state at every write: [('cp1252','namereplace')]    [('cp1252','namereplace')]
before main(): ('cp1252','strict')                  before main(): ('cp1252','strict')
after  main(): ('cp1252','strict')                  after  main(): ('cp1252','namereplace')
```

**Identical during the run, different after it.** That is exactly what item 124 asks for and
nothing more.

**No repository file was mutated for any measurement.** `ingestion/session_extraction.py`
sha256:

```
before my first edit:                 fceac7996c5d2beb744fd941a025f4f0649a599656a6710b6c4754c2800937ca
C:\tmp\p1e_head (git archive HEAD):   fceac7996c5d2beb744fd941a025f4f0649a599656a6710b6c4754c2800937ca   (equal — the scratch tree is HEAD)
after my last edit:                   55aff340a5224e4924eebe9fee76ac8b9ae42e24ff1508df5bbfaf67c7efa5cf
```

### Criterion 8 — `P14f-prompt-encoding` does not regress. All four, run on the final code.

| `P14f` fact | Result | How |
|---|---|---|
| 1. `prompt --pass 2` exits **0** with **82** lines on a Windows console, two `\N{RIGHTWARDS ARROW}` | **exit 0, 82 lines, 2 named arrows, 0 `charmap`** | `PYTHONIOENCODING=cp1252 … -m ingestion.session_extraction prompt extractions/WMT.json --filing 0 --pass 2 > file 2>&1` |
| 2. `main()` sets **only the error handler**, to `namereplace`, leaving the encoding alone | **`('cp1252','namereplace')` at every write; encoding `cp1252` before, during and after** | `inside_main.py`, above |
| 3. `namereplace` and not `replace` or `ignore` | the two rules read `costs \N{RIGHTWARDS ARROW} remove` and `income \N{RIGHTWARDS ARROW} strip`; `costs ? remove` **0**, `costs  remove` **0**, `\u2192` **0**, `&#8594;` **0** | `grep` over the captured output |
| 4. No prompt byte moved | `pass2_system` **3317**, `843ce6e79ea264ca15aee431bae877e2bf78d8c3d9bfb6c387d0325f9c863e7a`, **2** arrows; `pass1_system` **11437**, `f1ff5987…`, 0 arrows | `PYTHONIOENCODING=utf-8 … -c "import hashlib; …"` |

**Fact 1 needed one thing cleared up and it is not a regression — I nearly reported a false
one.** With the two streams redirected to **separate** files the command gives **65** stdout
lines, not 82. I ran the identical command inside the `git archive` of `HEAD`: **also 65 on
stdout, and 17 on stderr.** 65 + 17 = **82**. `cmd_prompt` sends `parse_pass1`'s arithmetic
table to stderr, so `P14f`'s 82 is what a console shows, where both streams land together.
With `2>&1` both trees give exactly 82 and 2 named arrows. The two outputs are
**byte-identical but for the session file's own path** in the two header lines, which differs
only because the HEAD copy runs from `C:\tmp\p1e_head`:

```
cmp head_both.txt fixed_both.txt  ->  differ: byte 1210, line 18
diff                              ->  18c18 and 74c74 only, both "=== SYSTEM/USER PROMPT — Pass 2, <path>\extractions\WMT.json: filings[0] (…) ==="
```

**So no byte of the prompt moved and no line of the output moved.** The final-code run is
byte-identical to the run taken before my last edit (`cmp` → identical).

### Criterion 9 — the same five seeds after the fix

`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe -m pytest -q --randomly-seed=<n> --ignore-glob="*_rule3_red.py"`, **re-run on the final code** after the last edit.

| Seed | Failing set, **by name** | Summary line |
|---|---|---|
| 1 | `test_session_extraction_console.py::test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[utf-8]`, `…[cp1252]`, `test_session_extraction_console.py::test_main_sets_the_handler_before_it_parses_argv` | `3 failed, 1367 passed, 2 skipped in 143.74s` |
| 2 | the same three | `3 failed, 1367 passed, 2 skipped in 149.77s` |
| 3 | the same three | `3 failed, 1367 passed, 2 skipped in 161.78s` |
| 124 | the same three | `3 failed, 1367 passed, 2 skipped in 155.64s` |
| 127 | the same three | `3 failed, 1367 passed, 2 skipped in 166.25s` |
| unseeded full suite, `Using --randomly-seed=2583387543` | the same three **plus the two red on purpose** | `5 failed, 1367 passed, 2 skipped in 145.82s` |

All three live in `tests/unit/test_session_extraction_console.py`. Their names in full:

```
tests/unit/test_session_extraction_console.py::test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[cp1252]
tests/unit/test_session_extraction_console.py::test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[utf-8]
tests/unit/test_session_extraction_console.py::test_main_sets_the_handler_before_it_parses_argv
```

**What moved, and why.** 1370 → 1367 passing, 0 → 3 failing. All three fail on one line,
`test_session_extraction_console.py:329` and `:346`:

```
assert record["errors"] == ["namereplace", "namereplace"]
E  AssertionError: assert ['strict', 'backslashreplace'] == ['namereplace', 'namereplace']
```

`record["errors"]` is read **after `main()` returns**, in a subprocess
(`RECORD_STREAMS`, `:145-148`). **So the assertion is the leak**: it asserts that the handler
`main()` set is still there when `main()` has finished, which is precisely what item 124 says
must stop being true. `['strict', 'backslashreplace']` is the pair Python itself puts on
`sys.stdout` and `sys.stderr`, now restored. **The two red-on-purpose tests are still red and
neither went green**, so nothing is hiding inside the ignored pattern.

**I did not touch these tests.** `tests/` is the tester's, the assignment names this exact
case ("that is a finding for your entry and for the tester, not a test for you to edit"), and
weakening a test to get a green line is one of the three forbidden moves.

### Criterion 6 — the two lists

**List A — failures whose cause is in code I may edit: empty.** No order-dependent failure
appeared in twelve gate runs (six orders before the change, six after), and the three
failures that did appear are not order-dependent: they fail in every one of the six orders
and in a fixed-order run of that file alone.

**List B — failures whose cause is in `tests/`, which the tester fixes: three.**

| # | Test | Why it is red, and what it is really asserting |
|---|---|---|
| B1 | `tests/unit/test_session_extraction_console.py::test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[cp1252]` | `:329` reads `sys.stdout.errors` / `sys.stderr.errors` **after `main()` has returned** and requires `namereplace`. Closing item 124 makes that false by design. **What the test means to assert is still true and is now measurable from inside**: the handler is `namereplace` at every write during the command (`inside_main.py`), the encoding does not move (`before == after == [encoding, encoding]`, still true), and the exit code is 2 |
| B2 | `…::test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[utf-8]` | the same line, the same cause |
| B3 | `…::test_main_sets_the_handler_before_it_parses_argv` | `:346`, the same assertion on an argv argparse rejects. Its real subject — that the handler is on **before** argv is parsed, so argparse's own usage message is covered — is untouched by this unit and still holds |

**Two further notes the tester will want**, neither a request to change behaviour:

- The file's module docstring (`:41-48`) states as a fact that "`main()` sets a handler on
  the process-global `sys.stdout` and never restores it" and explains the three subprocesses
  by it. That paragraph is now the description of a closed defect. The subprocesses can stay
  — they are sound — but the stated reason has changed.
- `main()` can now be called **in-process** from a test without leaking anything. That is the
  whole point of the change and it is what makes B1–B3 cheap to rewrite.

### Criterion 10 — what the plugin changed beyond order: **none, and here is how I looked**

**First, that the reseeding is real here.** `pytest-randomly` reseeds `random` and, when
numpy is importable, `numpy.random` before every test. A scratch test outside the repository
(`C:\tmp\p1e_rng\test_rng_reach.py`) records the first draw of each generator:

```
seed 1 -> {"stdlib": 0.9779870261322985, "numpy": 0.3815926135032507}
seed 2 -> {"stdlib": 0.8205838512097187, "numpy": 0.1165023155132956}
seed 3 -> {"stdlib": 0.581992449415208,  "numpy": 0.8271854252800559}
seed 1, run again -> identical to seed 1
```

So both generators are reseeded, differently per seed and reproducibly per seed. **The six
gate runs therefore varied the global RNG state as well as the order.**

**Second, whether anything here draws from them. Nothing does.** Two independent searches
over every `.py` file outside `.venv`, for `random`, `np.random`, `numpy.random`, `shuffle`,
`getrandbits`, `uuid4` and `secrets.`:

```
grep -rnE "\brandom\b|np\.random|numpy\.random|shuffle|getrandbits|uuid4|secrets\." --include=*.py .   ->  no match outside .venv
ripgrep, same pattern, *.py                                                                            ->  No matches found
```

The ripgrep run was controlled against a pattern that must match (`numpy|import scipy|pandas`
→ 10 files), so the empty result is a real negative and not a broken search.

**Third, the behavioural check.** 1367 tests pass under six different global seeds, so every
hand-derived expected value in the suite held against six different RNG states. `scipy`'s
`linregress` in `analysis/capm.py` is deterministic, and the network is closed by
`tests/conftest.py`'s `_no_socket`.

**Named tests whose figures depend on the reseeded generators: none.**

### Criterion 11 — `-p no:randomly` appears nowhere it could act

`grep -rn "no:randomly"` over the repository. **Every hit read.** Five are in live documents
and every one of them is prose *about* the flag, not a use of it:

| Hit | What it says | A command or config? |
|---|---|---|
| `STATUS.md:122` | "`-p no:randomly` is gone from every live document, on the user's decision '1a'…" | no — the record of item 126 |
| `STATUS.md:659` | item 126's closed row | no |
| `docs/9-reference/refactor-backlog.md:161` | item 127's row, naming what the deletion left behind | no |
| `docs/9-reference/refactor-backlog.md:162` | item 126's row | no |
| `.agent/QUEUE.md:87` | row 6j: "Three things it is forbidden to do… put `-p no:randomly` anywhere… **Once the plugin is installed, `-p no:randomly` stops being the no-op item 126 deleted and becomes a way to switch the guard off**" | no — this unit's own prohibition |

Every remaining hit is in `.agent/journal/*` or `.agent/assignments/*` — entries and accepted
assignments, which record what was run and what was asked. That is the exemption the
criterion states.

**Zero hits in any config file, any `addopts`, any command I ran, and neither of my two
edited files.** I did not use the flag once; where I needed a repeatable order I used
`--randomly-seed=<n>` and named the seed.

### Criterion 12 — no default seed is pinned

**Where a seed could be set, and that it is not:**

| Place | State |
|---|---|
| `pytest.ini` | **does not exist** |
| `setup.cfg` | **does not exist** |
| `tox.ini` | **does not exist** |
| `pyproject.toml` | **does not exist** — `ruff.toml`'s own header says this is deliberate, so that no file becomes pytest's configuration anchor |
| root `conftest.py` | **does not exist** |
| `tests/conftest.py` | no `randomly`, no `seed`, no `addopts`, no `pytest_collection_modifyitems` |
| any `addopts` in any tracked `.ini`/`.cfg`/`.toml`/`.py`/`.json` | `git grep -n -E "addopts\|randomly.seed\|randomly_seed\|^\[pytest\]\|tool\.pytest\|PYTEST_ADDOPTS"` → **no match** |
| `ruff.toml` | sets `target-version = "py314"` and one `B008` per-file ignore for `api/`. Nothing else |
| the `PYTEST_ADDOPTS` environment variable | **empty** |

**And the behaviour proves it rather than the absence of a file**: five unseeded runs printed
five different seeds (`2499748579`, `1631738109`, `2580582436`, `4142695305`, `2583387543`).
A pinned default would have printed one seed five times.

### Criteria 13 to 17 — the gates, after the last edit

| Gate | Result | Moved? |
|---|---|---|
| `-m ruff check .` | **4 errors, every one `BLE001`**: `api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106` | no |
| `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | **2 errors in 2 files**, 21 checked: `analysis/projector.py:395`, `api/routes_upload.py:28` | no. None removed, none added |
| census | **64** | no. No site added, none removed |
| route | **200** | no |
| `.claude/check_guard.py` | **48/48 guard cases correct** | no |

**Lint went to 5 in between, and that is worth recording.** My first draft of the stop raised
`ValueError`, and `ruff` reported `TRY004 Prefer TypeError exception for invalid type` at
`ingestion/session_extraction.py:1227`. I ran `ruff check .` **after** that edit, caught it,
and changed the exception to `TypeError` — which is also the right exception, because the
complaint is about the type of `stream.errors`. I then **re-ran all five seeds, the unseeded
full suite, the prompt command and the digests on the final code**, because a gate run taken
before the last edit is indistinguishable from one taken after it (`STATUS.md`, the
`P3c-one-number-tests` overturn).

---

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Close item 124 by **restoring the handler**, not by moving the call under a `__main__` guard | The assignment's step 5 names both shapes and says they are not equivalent. `main(argv)` is a public function an importer calls: `tests/unit/test_session_extraction.py:1180` calls it in-process, and the `P14f` tests call it through `-c … main(argv)` | A `__main__` guard does not run for an in-process caller, so **every such caller would get item 113 back** — the cp1252 `UnicodeEncodeError` on `prompt --pass 2`. The restore shape keeps the handler on for the whole of `main()`, by either entry, and still leaves the caller's stream as it found it. Measured both halves: identical during the run, restored after |
| A `contextlib.contextmanager` wrapping the whole body of `main()`, rather than two set/restore calls around the `try` | One `with` covers all six subcommands **and argparse's own usage message**, which prints to stderr before any subcommand is chosen — the property `P14f` built the call site to have (`test_main_sets_the_handler_before_it_parses_argv`) | Hand-written set/restore pairs would have to repeat the restore on the `SystemExit` argparse raises. The `finally` covers it for free |
| Keep `name_unencodable_characters` unchanged, and call it from the context manager | Backlog item 123 is explicitly out of this unit's scope, and six `P14f` tests call that function directly with a stream they own | Folding it into the context manager would have changed a function six tests exercise, for no reason item 124 names |
| Read `stream.errors` and **stop** if it is not a `str` | Rule 3. `reconfigure(errors=None)` means "leave the handler alone", so a non-name handler would **silently** leave `namereplace` behind — item 124 wearing a quieter face | A bare `stream.reconfigure(errors=previous)` would turn the one case where the restore cannot work into a silent no-op, which is the defect this unit is closing |
| `TypeError` rather than `ValueError` for that stop | `ruff` `TRY004`, and `main()`'s `except (ValueError, FileNotFoundError)` would otherwise be able to render it as an ordinary `ERROR: …` exit 2 | A stop that reads like a user input error is not a stop a reader can act on |
| Seeds 1, 2, 3, 124, 127 | 1, 2 and 3 are the cheapest reproducible orders for anyone re-running this; 124 and 127 are the two backlog items this unit closes and answers, so the commands in this entry carry their own provenance | Any five would do. Naming them is what the criterion asks |
| Reported the empty failing set as the result, rather than hunting for a seed that turns something red | The unit owes the failing set at **five named seeds**, not a red test. Searching seeds until one fails would be choosing a number first and a reason after | Had I found a red one, it would have gone in list A or list B with its cause |

**A code change made to reach a target number is forbidden.** I made none. The only code
change is the one item 124 names, and the only follow-up edit was an exception class the
linter named.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `stream.errors`, the handler to put back | **stops and names the stream and the value**: `TypeError("cannot name unencodable characters on this stream: its error handler reads as …, which is not a handler name, so the handler this would set could not be put back afterwards. Stream: …")` | `ingestion/session_extraction.py:1222-1233`. No default, no `or`, no conditional fallback |
| `isinstance(stream, io.TextIOWrapper)` | **not a missing input**: a stream that performs no encode step cannot lose a character, so there is nothing to set and nothing to restore. The context manager yields `False` and the body runs | `ingestion/session_extraction.py:1215-1219`, and `name_unencodable_characters`'s docstring, which `P14f` wrote and the review accepted |
| the previous handler on `sys.stderr` when it is the **same object** as `sys.stdout` | the nested managers restore in reverse: inner puts back `namereplace`, outer puts back the original. Final state is the original | measured: `leak_demo.py` sets both names to one stream and reports `RESTORED` |
| **no money figure, no filing figure and no assumption is read by this unit** | — | the diff touches one import, one new context manager and `main()`'s stream handling. The census is unmoved at 64, and the `prompt --pass 2` output is byte-identical to `HEAD`'s |

**No "defaults to" row.** This unit adds no silent default.

## Measurements

**The suite, as failure SETS and never as counts alone.**

| Tree | Order | Failing set, by name |
|---|---|---|
| `HEAD` + the plugin | seeds 1, 2, 3, 124, 127 and unseeded | **{ }** in all six |
| this tree (final code) | seeds 1, 2, 3, 124, 127 and unseeded | **{ `…console.py::test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[cp1252]`, `…[utf-8]`, `…console.py::test_main_sets_the_handler_before_it_parses_argv` }** in all six |
| this tree, full suite (no `--ignore-glob`) | unseeded | the three above **plus** `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` — the two red on purpose, both still red |

Lint 4 (`BLE001` ×4), types 2 in 2 files, census 64, route 200, guard 48/48 — every one
unmoved from the "before".

**No figure this platform displays moved.** This unit changes the error handler on two
console streams inside `session_extraction.main()`. No valuation path calls that function:
`cli.py` and the web routes reach route B through `load_session_extraction`, not through
`main()`. The 1367 passing tests include the whole valuation suite, and the Pass 1 and Pass 2
system prompts are byte-for-byte what `P14f` recorded.

## What I did not do

- **I did not edit `tests/`.** Three tests are red and their repair belongs to the tester,
  by name, in list B.
- **I did not pin a seed anywhere, and I did not use `-p no:randomly` once.**
- **I did not close backlog item 123.** `main()` still does not read the `bool`. The context
  manager yields it, so a caller that wants it can have it, but the call site in `main()`
  still discards it. Not claimed.
- **I did not close backlog item 125.** During the command the inherited handler is still
  **replaced** rather than composed; what changed is that the replacement no longer outlives
  the call. One fact in item 125's write-up is worth correcting — finding F4.
- **I did not touch `docs/8-build/environment.md`**, which is out of scope and owns what each
  dev dependency is for. What it needs to say is finding F5.
- **I did not re-measure a Walmart share price.** Nothing in the diff is on a valuation path,
  and no test asserting a figure changed state.

## Findings for the orchestrator

**F1 — the assignment's "before" table is two commits old.** `.agent/assignments/P1e-test-order.md`,
"What is already true", gives the gate as **1257 passed** at `0a9ed51`. At `47a5bd9` it is
**1370**, and the difference is exactly `P14g-unit-statement-pages`' 113 tests, measured by
collection in both trees (1372 − 1259 = 113). The other six figures agree exactly. The table
is right for the commit it names; a reader taking it as "today" would stop a unit for no
reason.

**F2 — three tests for the tester, by name**, all in
`tests/unit/test_session_extraction_console.py`:
`test_main_sets_the_handler_on_stdout_and_stderr_and_moves_neither_encoding[cp1252]`,
`…[utf-8]`, and `test_main_sets_the_handler_before_it_parses_argv`. Each asserts
`record["errors"] == ["namereplace","namereplace"]` **after `main()` has returned**, which is
the leak item 124 names. The subject each test means to cover is still true and is now
measurable from inside the run; `C:\tmp\p1e_leak\inside_main.py` shows one way. The file's
module docstring (`:41-48`) also states the leak as a live fact and justifies its three
subprocesses by it.

**F3 — `pytest-randomly` found no order dependence, and that is a weaker statement than it
looks.** Twelve gate runs over six distinct orders produced an empty order-dependent failing
set. But **the one order leak this repository has recorded, item 124, could never have been
found this way**: no test asserts on an encoding failure, so no order could make the leaked
handler change a result. The guard is worth having for the test that gets written tomorrow,
and today it has proved the suite clean in six orders out of 1372-factorial. It is not proof
that the suite is order-independent.

**F4 — a correction to item 125's write-up.** It says the inherited handler being replaced is
`surrogateescape`. Measured on this machine, with `PYTHONIOENCODING=<encoding>` set, the
handlers `main()` replaces are **`strict` on stdout and `backslashreplace` on stderr** — that
is the pair the three red tests now report. The item's substance (replaced rather than
composed, during the run) still stands; the handler it names does not.

**F5 — `docs/8-build/environment.md` needs four sentences** (out of my scope): that
`pytest-randomly` **5.0.0** is a dev dependency and what it is for (item 127); that every
gate command now runs in a random order and prints `Using --randomly-seed=<n>`; that a
measurement which must be repeatable uses `--randomly-seed=<n>` **on that one command** and
names the seed; and that **`-p no:randomly` must not be used**, because since this unit it is
no longer a no-op but a way to switch the guard off.

**F6 — to undo this unit**, `pip uninstall pytest-randomly` and delete the one line from
`requirements-dev.txt`. The installed version is **5.0.0**; the shared `.venv` is the one
effect of this unit no scratch copy contains.

**F7 — a branch the tester will find hard to reach, named so nobody deletes it quietly.**
The `TypeError` stop at `ingestion/session_extraction.py:1227` fires only when
`stream.errors` is not a `str`. Every `io.TextIOWrapper` I could construct returns a `str`,
so it is reachable only through a subclass whose `errors` property returns something else —
which is a legitimate two-line test. **It is not an unreachable guard added for coverage**:
without it, `reconfigure(errors=None)` leaves the changed handler in place and says nothing,
which is item 124 again.

**F8 — `prompt --pass 2` prints 65 lines on stdout and 17 on stderr.** `P14f`'s "82 lines" is
the console total of both streams. Any future criterion quoting 82 should say so, or it will
read as a regression to whoever redirects the two streams separately, as I did.

---

## Files changed

```
$ git diff --stat
 ingestion/session_extraction.py | 87 +++++++++++++++++++++++++++++++----------
 requirements-dev.txt            |  1 +
 2 files changed, 68 insertions(+), 20 deletions(-)
```

- `requirements-dev.txt`: **+1**, `pytest-randomly`, between `pytest-cov` and `ruff`.
- `ingestion/session_extraction.py`: **+67 −20** — one import
  (`collections.abc.Iterator`), the new `naming_unencodable_characters` context
  manager, and `main()` wrapping its body in it. The 20 deletions are `main()`'s old
  body re-indented by one level and its two bare set-up calls.

`git status --short` at the end: `M ingestion/session_extraction.py`,
`M requirements-dev.txt`, `?? .agent/journal/2026-10-07T2244-programmer-p1e-test-order.md`.
**Nothing else. No file outside Files in scope was written, and `tests/` is untouched.**

The in-process caller the fix protects, verified rather than taken from the assignment:
`tests/unit/test_session_extraction.py:1180`, `:1181` and `:1183` each call
`main([...])` in this process.
