---
agent: code_reviewer
assignment: P1e-test-order
round: 1
verdict: approved
---

# Review of P1e-test-order, round 1

Programmer entry: `.agent/journal/2026-10-07T2244-programmer-p1e-test-order.md`

Diff reviewed: `requirements-dev.txt` **+1**, `ingestion/session_extraction.py` **+68 / −20**.
Nothing else is modified. (`.agent/journal/INDEX.md` is also modified in this tree; its one
added line is the overall lead's own row about the programmer entry, not this unit's write.)

**Repository untouched by me.** `ingestion/session_extraction.py` sha256
`55aff340a5224e4924eebe9fee76ac8b9ae42e24ff1508df5bbfaf67c7efa5cf` before and after every
command below; `requirements-dev.txt` `aee75169…`; `git status --short` identical at both
ends. Every probe ran from `C:\tmp\p1e_rv\` against the working tree and against a
`git archive HEAD` export at `C:\tmp\p1e_rv_head\` (`fceac799…`, equal to the programmer's
pre-edit hash). No `git stash`, no `-p no:randomly` in any command.

## The guard checks

Run over the two **Files in scope**.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean, 0 hits in the whole file |
| lookup with a fallback — `.get(k, …)` | clean |
| bare or-default — `or 0.0` / `or []` | clean |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (`grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no hit) |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `stream.errors`, the handler to put back | **yes** — `TypeError` naming the value and the stream, raised at `__enter__` before anything is set | `ingestion/session_extraction.py:1222-1233`; executed, below |
| `isinstance(stream, io.TextIOWrapper)` false | not a missing input: no encode step, so nothing is set and nothing is restored; the body runs | `:1217-1221`, unchanged behaviour from `P14f` |
| `previous` when stdout **is** stderr | nested restore in reverse; final state is the original | measured: `same-object case: before strict after strict -> RESTORED` |
| any money / filing / assumption figure | none is read by this diff | census unmoved at 64; prompt digests unmoved |

**The `TypeError` is a real rule 3 stop, not coverage padding**, and this is the judgement
the prompt asked for. Measured:

```
w.reconfigure(errors='namereplace'); w.reconfigure(errors=None) -> w.errors == 'namereplace'   # silently unchanged
io.TextIOWrapper(...).errors is always a str; only a subclass overriding `errors` returns None
```

So the branch is reachable only through a `TextIOWrapper` subclass, as the programmer's F7
says — but the case it catches is the one that matters: `errors is None` makes
`reconfigure(errors=previous)` a **silent no-op**, which leaves `namereplace` on a stream the
module does not own. That is item 124 again, quieter. Without the stop the code would
"restore" and say nothing. Reachability is explicitly not the test. Executed end to end with
a stdout that is fine and a stderr whose `errors` is `None`:

```
raised: ('TypeError', 'cannot name unencodable characters on this stream: its error handler reads as None, which …')
stdout handler after the aborted call: strict   <- the outer manager still restored
```

That also answers the exception-safety question the nested `with` raises.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | n/a — the diff reads no figure |
| percentages converted at the route boundary, once | n/a |
| falsy not treated as missing | clean; the one test is `isinstance(previous, str)`, not `if previous` |
| layering | `ingestion/` importing `collections.abc` only; no new repository import |
| `docs/2-rules/llm-boundary.md` | **no prompt byte moved**, by digest: `pass2_system` 3317 / `843ce6e79ea264ca15aee431bae877e2bf78d8c3d9bfb6c387d0325f9c863e7a` / 2 arrows; `pass1_system` 11437 / `f1ff5987…` / 0 |

## Done-criteria, re-run

Every figure below is mine, from my own command. Twelve full gate runs, six per tree.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 2 | the "before" | 1370 passed / 2 skipped at `47a5bd9`, not the assignment's 1257 | 1370 passed, 2 skipped in all six `HEAD` orders; 1372 collected | **yes** — and the assignment's table is the stale one (its F1) |
| 3 | plugin installed and declared | `pytest-randomly` 5.0.0 | `[('pytest','9.1.1'),('pytest-cov','7.1.0'),('pytest-randomly','5.0.0')]`; the line is in `requirements-dev.txt` | yes |
| 4 | order really changes | different first file per seed | seed 1 → `test_routes_session.py::test_valuation_on_a_cache_hit_shows_the_session_label`; seed 2 → `test_normalizer_year_stop.py::…`; seed 3 → `test_dcf.py::…`. Intra-file order also moves: `test_dcf.py` first id differs between seeds 1 and 2 | yes |
| 5 | five seeds **before** the fix, by name | empty in all six | **empty in all six**, `1370 passed, 2 skipped` each, run in the `git archive HEAD` tree with the plugin | yes |
| 7 | item 124 closed | `HEAD` LEAKED, this tree RESTORED | my own probe, a `TextIOWrapper` I own installed as both streams: `HEAD` → `('namereplace','namereplace')` after `main()`; this tree → `('strict','strict')`. Also RESTORED on the argparse `SystemExit` path, on the `locate` path, and when one object is bound to both names. `CaptureIO` is an `io.TextIOWrapper` subclass: `True` | **yes** |
| 8 | `P14f` does not regress | all four hold | all four, mine: exit **0**, **82** console lines (`2>&1`), **2** `RIGHTWARDS ARROW`, **0** `charmap`; encoding `cp1252` before and after, errors restored to `strict`; **0** `?` bytes, so not `replace`; digests above | yes |
| 9 | five seeds **after** the fix | the same three names in all six | **the same three, in all six**, `3 failed, 1367 passed, 2 skipped` each. Nothing else moved | yes |
| 10 | beyond order: reseeded RNGs | none | `git grep -nE "\brandom\b\|np\.random\|numpy\.random\|\.shuffle\|getrandbits\|uuid4\|secrets\."` over every tracked `*.py` → **no hit**, against a control pattern that returns 10 files. Nothing in this repository draws from the generators the plugin reseeds | yes |
| 11 | `-p no:randomly` nowhere | 5 live hits, all prose | the same 5 (`STATUS.md:122`, `:659`, `refactor-backlog.md:161`, `:162`, `QUEUE.md:87`), every one prose *about* the flag. Zero in any command, config file or either edited file | yes |
| 12 | no default seed pinned | no config file exists | `pytest.ini`, `setup.cfg`, `tox.ini`, `pyproject.toml`, root `conftest.py` all absent; `git grep` for `addopts\|randomly.seed\|[pytest]\|tool.pytest` → no match; `PYTEST_ADDOPTS` unset | yes |
| 13 | lint | 4, all `BLE001` | **4, all `BLE001`**, after the last edit | yes |
| 14 | types | 2 in 2 files, 21 checked | **2 in 2 files**, `analysis/projector.py:395`, `api/routes_upload.py:28` | yes |
| 15 | census | 64 | **64** | yes |
| 16 | route | 200 | **200** | yes |
| 17 | write guard | 48/48 | **48/48** | yes |
| — | the two red on purpose | both still red | both still **FAILED**, neither went green | yes |

### The three red tests, per test, with the line

All three fail on one assertion and on nothing else:

```
tests/unit/test_session_extraction_console.py:329  (…[cp1252] and …[utf-8])
tests/unit/test_session_extraction_console.py:346  (…before_it_parses_argv)
>   assert record["errors"] == ["namereplace", "namereplace"]
E   AssertionError: assert ['strict', 'backslashreplace'] == ['namereplace', 'namereplace']
```

`record["errors"]` is written by `RECORD_STREAMS` (`:136-150`) **after `main(argv)` has
returned**. So the assertion is a reading of the leaked handler: it asserts that the handler
`main()` set is still on the caller's stream once `main()` is finished, which is exactly what
item 124 says must stop being true. **Red for the right reason, all three.**

I checked the rest of each test rather than inferring it. Re-running the same
`RECORD_STREAMS` child myself, all four cases:

```
cp1252 check          -> {"before":["cp1252","cp1252"],"after":["cp1252","cp1252"],"errors":["strict","backslashreplace"],"code":2}
cp1252 bad-subcommand -> {"before":["cp1252","cp1252"],"after":["cp1252","cp1252"],"errors":["strict","backslashreplace"],"code":2}
utf-8  check          -> {"before":["utf-8","utf-8"],  "after":["utf-8","utf-8"],  "errors":["strict","backslashreplace"],"code":2}
utf-8  bad-subcommand -> {"before":["utf-8","utf-8"],  "after":["utf-8","utf-8"],  "errors":["strict","backslashreplace"],"code":2}
```

Every other assertion in the three tests — `after == before == [encoding, encoding]` and
`code == 2` — **still holds**. Only the handler-after-return line is false, and it is false
because the handler was put back. `['strict','backslashreplace']` is Python's own pair, which
also confirms the programmer's F4 correction to item 125's write-up.

### The `finally` does not un-name anything

The prompt asked me to satisfy myself that text written inside the block is already encoded
before the handler goes back. Measured on **bytes**, in-process, through a
`write_through=False` wrapper — the case where a flush at restore time could re-encode
something still pending:

```
exit code: 0
encoding before/after: ('cp1252','cp1252') ('cp1252','cp1252')
errors   before/after: ('strict','strict')   ('strict','strict')
count of \N{RIGHTWARDS ARROW} in the bytes: 2      count of b'?': 0
lines (stdout): 65   lines (stderr): 17            UnicodeEncodeError in output: False
```

Both arrows survive in the buffer as their Unicode names after the restore has run, so
`TextIOWrapper.write` encodes at write time and `reconfigure` flushes what is pending before
it changes the handler. 65 + 17 = 82, which is the programmer's F8 and it is right.

## Does this unit deliver the guard item 127 asked for?

The prompt asked for the reason, not the verdict. **Yes for the class item 127 names, with
two limits, and the programmer's F3 is correct but names only one of them.**

**What the plugin actually shuffles.** `pytest-randomly` 5.0.0,
`.venv/Lib/site-packages/pytest_randomly/__init__.py:222-269`, `_reorganize_items`: it sorts
modules by `crc32(f"{seed}::{module.__name__}")`, classes within a module by
`crc32(seed::qualname)`, and tests within a class or an unclassed group by
`crc32(seed::nodeid)`. So it shuffles **both** — whole files and the tests inside a file. I
executed both halves: three seeds give three different first modules, and inside
`tests/unit/test_dcf.py` alone seeds 1 and 2 give different first ids. Item 127 is written
about "order dependence between test files", and that is squarely covered; the intra-file
class is covered too.

**Limit 1, structural, and it is not in the entry.** Modules stay **contiguous blocks**. A
dependence that only shows when a test of module Y runs *between* two tests of module X is
unreachable at any seed. Narrow, but it should be recorded next to item 127 so nobody reads
"shuffled" as "all permutations" — F5 below.

**Limit 2, and this is F3's point, which I confirm and can sharpen.** Shuffling can only turn
something red where an assertion reads the leaked state. Item 124's leak changed no asserted
value — and the three tests that *do* observe the handler run `main()` in a **subprocess**,
so they could not see an in-process leak at any seed. No order could ever have found item
124. The guard found nothing today; what turned three tests red was the code fix, not the
plugin.

**So the unit delivers the mechanism the user chose, and does not deliver — and does not
claim — evidence that this suite is order-independent.** Six orders out of 1372! is the
honest framing and the programmer used it. Its value is prospective and continuous: every
future run draws a fresh order. Which makes F1 below the one thing that needs fixing for the
guard to pay off.

## Findings

### F1 — the gate command is `-m pytest -q`, and `-q` hides the seed · `minor`

**Evidence:**
`-m pytest tests/unit/test_dcf.py` prints `Using --randomly-seed=1216360797`;
`-m pytest -q tests/unit/test_dcf.py` prints no seed line at all. None of my six `-q` gate
runs recorded its seed.
**Rule or document:** no rule. It contradicts one sentence of the programmer's own F5, which
tells the overall lead to write that "every gate command now runs in a random order and
prints `Using --randomly-seed=<n>`". Every gate command in this repository carries `-q`, so
it does not print it.
**What would fix it:** `docs/8-build/environment.md` (the lead's, out of this unit's scope)
should say that the `-q` gate form suppresses the seed, so a gate figure recorded from it
describes **one unrecorded order** — and that a failure seen there must be re-run without
`-q`, or with `-rA`, to recover the seed before it can be reproduced. This is the correction
to F5, not a change to the code.

### F2 — the three red tests are the tester's, and the subject must survive the repair · `note`

**Evidence:** `tests/unit/test_session_extraction_console.py:329` and `:346`, quoted above.
**Rule or document:** the assignment, "If a `P14f` test goes red because it asserts the
handler is still set after `main()` returns, that is a finding for your entry and for the
tester, not a test for you to edit." The programmer obeyed it; `tests/` is untouched.
**What would fix it:** the tester's assignment should say explicitly that the two subjects
must still be covered after the repair and not deleted with the assertion — (a) the handler
is `namereplace` at **every write** during the command, and (b) it is on **before** argv is
parsed, which is what `test_main_sets_the_handler_before_it_parses_argv` exists for. Both are
now measurable in-process, because `main()` no longer leaks; a recording `TextIOWrapper`
subclass is one way and I executed it. Deleting the assertion without replacing it would
leave `P14f`'s whole purpose untested.

### F3 — the test file's module docstring now describes a closed defect · `note`

**Evidence:** `tests/unit/test_session_extraction_console.py:41-48`: "`main()` sets a handler
on the process-global `sys.stdout` and never restores it … (backlog item 124)".
**Rule or document:** none. `tests/` is out of this unit's scope; the programmer recorded it.
**What would fix it:** the tester rewrites that paragraph. The three subprocesses are still
sound and should stay; only their stated reason has changed.

### F4 — `naming_unencodable_characters` and `name_unencodable_characters` differ by one letter · `note`

**Evidence:** `ingestion/session_extraction.py:1178` and `:1198`, adjacent in the file and in
any grep.
**Rule or document:** none. The gerund is the conventional name for a context manager, and
the docstring distinguishes them clearly.
**What would fix it:** nothing is required. Recorded only because six `P14f` tests call the
non-gerund one directly, so a future reader will meet both names together.

### F5 — "shuffled" does not mean "all permutations", and item 127 should say so · `note`

**Evidence:** `.venv/Lib/site-packages/pytest_randomly/__init__.py:222-242` — modules are
sorted as whole blocks, so tests of two modules are never interleaved.
**Rule or document:** none; a completeness note for `docs/9-reference/refactor-backlog.md`
item 127, which the overall lead owns.
**What would fix it:** one clause in item 127's row recording what the guard can and cannot
reach, next to the programmer's F3.

## The programmer's own findings

F1 (the assignment's "before" table is two commits stale) — **I agree and I verified the
arithmetic from the record rather than by re-running**: this tree collects 1372 and the gate
is 1370 passed / 2 skipped in all six `HEAD` orders, and `P14g`'s accepted tester entry
already recorded 1370 = 1257 + 113. The table is right for the commit it names. The
assignment needs correcting by the overall lead, not by me.
F2, F3, F4, F6, F7, F8 — all confirmed by my own execution above. F5 is correct except for
the one sentence in F1 of this review.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 123 — `name_unencodable_characters` returns a `bool` the call site discards | `ingestion/session_extraction.py:1178-1194`, `main()` at `:1247` | **no**. The function is unchanged; the new `with` has no `as`, so the bool is still discarded. Correctly not claimed |
| 125 — the inherited handler is replaced, not composed | `ingestion/session_extraction.py:1234` | **no**. During the body it is still replaced; what changed is that the replacement no longer outlives the call. Correctly not claimed, with a correction to the item's text (its F4) |
| 4 × `BLE001` | `api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106` | no |
| 2 mypy errors | `analysis/projector.py:395`, `api/routes_upload.py:28` | no |

I saw each of these and each is already recorded.

**No recorded user decision is cited as an exception by this assignment, and none was needed:
nothing in the diff deviates from a rule.** The user's decision of 2026-10-07 (option `a`,
install `pytest-randomly`) is cited for the unit's existence, not for a deviation.

## Verdict

`approved`

The diff does what items 127 and 124 ask and nothing else: one declared dev dependency and
one context manager that reads a handler, sets it for the body, and puts it back in a
`finally`. I re-ran all twelve gate orders myself — empty failing set in six orders at
`HEAD`, exactly three failures in six orders here — built my own in-process leak probe
against a `git archive HEAD` tree and confirmed `LEAKED` there and `RESTORED` here on four
exit paths including argparse's `SystemExit`, and re-took all four `P14f` facts on bytes
rather than on exit codes. The three red tests are red because each asserts the leak itself,
on one line, with every other assertion in them still passing — the case the assignment told
the programmer to hand over rather than edit, and `tests/` is untouched. The shape was chosen
with a reason against the named alternative, and the rule 3 `TypeError` is a genuine stop,
not padding: `reconfigure(errors=None)` is a silent no-op, so without it the restore would
fail quietly and re-create item 124. No finding cites a rule; F1 is `minor` and the rest are
`note`, so nothing blocks. F1 and F5 are corrections the overall lead applies to
`docs/8-build/environment.md` and to backlog item 127; F2 and F3 are the tester's handover.
