---
agent: programmer
assignment: P14f-prompt-encoding
round: 1
status: complete
files_touched: [ingestion/session_extraction.py]
verdict:
---

# P14f-prompt-encoding — `prompt --pass 2` stops on a Windows console (item 113)

## What I did

`main()` now puts the `namereplace` error handler on `sys.stdout` and `sys.stderr`
before it parses argv, through one named function,
`name_unencodable_characters(stream: object) -> bool`. Nothing else changed: the
encoding of each stream is left exactly as the console declares it, so **every
character the console can already hold is written unchanged**, and only a character it
cannot hold is written as its Unicode name. On this console the Pass 2 prompt's two
`U+2192 RIGHTWARDS ARROW` now print as `\N{RIGHTWARDS ARROW}` instead of raising
`UnicodeEncodeError`, and the command finishes: **exit 2 and 19 lines becomes exit 0
and 82 lines**, the same 82 lines `PYTHONIOENCODING=utf-8` produced at `HEAD`. No byte
of any prompt moved — all **12** prompt digests (3 filings × {pass 1, pass 2} ×
{system, user}) are identical in the two trees.

The fix is in the stream because the text is not mine to change: those two lines are
the prompt route A sends to the model, and `AGENTS.md` makes any change to the LLM
boundary an escalation. `ingestion/claude_extractor.py` is byte-identical before and
after (`b459e4ee…`), as is `extractions/WMT.json` (`c436e427…`).

**Which of the two offered fixes I chose, and what the console then shows.** I chose
**reconfiguring the output stream**, not writing the prompt through a separate
encoder, and the handler is `namereplace`, not `replace`. Reconfiguring the stream
fixes every subcommand at one site (criterion 3 of "What to do") rather than only the
one that prints a prompt; a separate encoder around `cmd_prompt`'s four `print` calls
would leave `plan`, `locate`, `text` and `check` exactly as exposed as they are today,
and would have to be repeated at every future print. `namereplace` is the handler
because the assignment forbids a silent replacement: `replace` prints `?` and `ignore`
prints nothing, and a reader seeing `costs ? remove` cannot tell a dropped arrow from
a prompt that never had one. **The console shows `\N{RIGHTWARDS ARROW}`** — the
character's Unicode name, which names it exactly.

## Done-criteria

Every command below was run with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`,
`.venv/Scripts/python.exe`, and **no `PYTHONIOENCODING` set** except where criterion 6
sets it. `env | grep -i pythonio` returns nothing on this console.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | `prompt --pass 2` finishes | **pass** | `-m ingestion.session_extraction prompt extractions/WMT.json --filing 0 --pass 2 > out 2>&1` → **`exit=0`, 82 lines**. The two `direction` rules are output lines 67 and 68 |
| 2 | The old behaviour is reproduced first | **pass** | `git archive HEAD \| tar -x -C /c/tmp/p14f/head`, `extractions/WMT.json` copied in (it is not in git), same command with cwd there → **`exit=2`, 19 lines**, last line `ERROR: 'charmap' codec can't encode character '\u2192' in position 2992: character maps to <undefined>`. No `git stash` was used; `git status --short` shows only `M ingestion/session_extraction.py` |
| 3 | What the reader sees where the arrow was | **pass** | quoted below, byte for byte, from criterion 1's output through `cat -A` |
| 4 | All six subcommands finish | **pass** | **6 of 6 at exit 0**; table below |
| 5 | No prompt byte moved | **pass** | `hash_prompts.py` run with cwd in each tree → `diff` of the two outputs is **empty**: 12 of 12 sha256 digests identical |
| 6 | A UTF-8 console is not degraded | **pass** | `PYTHONIOENCODING=utf-8 … --pass 2` → `exit=0`, 82 lines, `U+2192` present on lines 67 and 68, **zero** `\N{` escapes anywhere; the whole output is byte-identical to `HEAD`'s UTF-8 output after normalising the session file's path |
| 7 | Nothing sets `PYTHONIOENCODING` in the code | **pass** | `grep -rn PYTHONIOENCODING ingestion/` → exit 1, no match. Over the whole repository (`--include=*.py`, `.venv` excluded) → exit 1, no match |
| 8 | Types | **pass** | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → **5 errors in 2 files (checked 21 source files)**. Unchanged: 4 in `analysis/projector.py`, 1 in `api/routes_upload.py`. **I removed none and added none**; `ingestion/session_extraction.py` holds 0 |
| 9 | Lint | **pass** | `-m ruff check .` **run after my last edit** → **`Found 4 errors`**, every one `BLE001`: `api/routes_valuation.py:451`, `:733`, `cli.py:1204`, `tests/test_e2e_all_googl.py:106` |
| 10 | Census | **pass** | the grep at `docs/2-rules/rules.md:102` → **64**. With `pipeline.py` added → 64 |
| 11 | Route | **pass** | `TestClient(app.app, raise_server_exceptions=False).get('/')` → **200** |
| 12 | The failing test set | **pass** | **no test changed state.** Sets below |

### Criterion 3 — the two rendered lines, byte for byte

From criterion 1's output, lines 67 and 68, through `grep -n RIGHTWARDS … | cat -A`
(`$` is `cat -A`'s end-of-line marker, not a character in the output):

```
67:        "add_back" = one-time EXPENSE that inflated costs \N{RIGHTWARDS ARROW} remove to get clean earnings$
68:        "remove"   = one-time GAIN that inflated income \N{RIGHTWARDS ARROW} strip to get clean earnings$
```

Everything else on those lines is unchanged. Decoding both whole outputs and diffing
them as text — `HEAD` with `PYTHONIOENCODING=utf-8` read as UTF-8, against the fixed
tree with no variable read as cp1252, with the session file's path normalised —
gives **82 lines against 82 lines and exactly two differing lines**, differing at the
arrow and nowhere else:

```
@@ -67,2 +67,2 @@
-        "add_back" = one-time EXPENSE that inflated costs \u2192 remove to get clean earnings
-        "remove"   = one-time GAIN that inflated income \u2192 strip to get clean earnings
+        "add_back" = one-time EXPENSE that inflated costs \\N{RIGHTWARDS ARROW} remove to get clean earnings
+        "remove"   = one-time GAIN that inflated income \\N{RIGHTWARDS ARROW} strip to get clean earnings
```

The em dash `—` (U+2014) and the ellipsis `…` (U+2026) that `check`, `plan` and the
prompt headers print are **in** cp1252, so they are untouched by the handler and still
print as themselves. That is the point of leaving the encoding alone.

### Criterion 4 — the six subcommands, at `HEAD` and after

Combined `stdout`+`stderr`, cwd in the relevant tree, no `PYTHONIOENCODING`.

| Subcommand | `HEAD` exit | `HEAD` lines | After, exit | After, lines |
|---|---|---|---|---|
| `plan C:/…/10K_filings/WMT -t WMT -o <scratch> --force` | 0 | 5 | **0** | 5 |
| `locate extractions/WMT.json --filing 0` | 0 | 23 | **0** | 23 |
| `text extractions/WMT.json --filing 0 --pages 21-22` | 0 | 112 | **0** | 112 |
| `prompt … --pass 1` | 0 | 154 | **0** | 154 |
| **`prompt … --pass 2`** | **2** | **19** | **0** | **82** |
| `check extractions/WMT.json` | 0 | 67 | **0** | 67 |

The `HEAD` column reproduces the assignment's table exactly: one subcommand fails, and
it is `prompt --pass 2`.

**The five that already passed are byte-identical after the fix.** `cmp_outputs.py`
normalises the two scratch paths and diffs each pair: `plan IDENTICAL`, `locate
IDENTICAL`, `text IDENTICAL`, `prompt1 IDENTICAL`, `check IDENTICAL`. So the handler
changed no byte of any output that did not previously stop the run.

### Criterion 5 — the prompt digests

`hash_prompts.py` (in `/c/tmp/p14f/`, outside both trees, so one script measures both)
imports `pass1_prompts`, `pass2_prompts` and `parse_pass1` from the tree on
`PYTHONPATH`, builds the three `FilingPlan`s from `extractions/WMT.json`, and prints
`sha256(text.encode("utf-8"))` and `len` of each of the four returned strings per
filing.

```
filings[0] pass1 system f1ff5987e972f5015305353eb68dd0f26285fe72de2576ccaf008496624f6d67 len 11437
filings[0] pass1 user   95a39001817b7b7d1559f39accd18b02e2a781a26fe2889127133facaf080067 len 268
filings[0] pass2 system 843ce6e79ea264ca15aee431bae877e2bf78d8c3d9bfb6c387d0325f9c863e7a len 3317
filings[0] pass2 user   eb70cad1e7c48362eaa085c15c5b1b0b472b94205df0f67578ad9de7a063266d len 498
filings[1] pass1 system f1ff5987e972f5015305353eb68dd0f26285fe72de2576ccaf008496624f6d67 len 11437
filings[1] pass1 user   0f5c4be31276af9ce7e969901262c65c52606bd55a2467799b16c4dad716a567 len 261
filings[1] pass2 system 843ce6e79ea264ca15aee431bae877e2bf78d8c3d9bfb6c387d0325f9c863e7a len 3317
filings[1] pass2 user   9a79cd82181524579217d05891c4f938771521d45f8c941db1487e1632ca5cf6 len 246
filings[2] pass1 system f1ff5987e972f5015305353eb68dd0f26285fe72de2576ccaf008496624f6d67 len 11437
filings[2] pass1 user   1845f79516595076617594d50d00ce8c52c552ef9e140237685b027f909877f3 len 234
filings[2] pass2 system 843ce6e79ea264ca15aee431bae877e2bf78d8c3d9bfb6c387d0325f9c863e7a len 3317
filings[2] pass2 user   97e94d849f2b63f6a324ca663632a237e8102406401bcdb9242194d099c6c057 len 247
python 3.14.4
```

`diff hash_head.txt hash_final.txt` → **empty, exit 0**. The Pass 2 system prompt that
holds the two arrows is `843ce6e7…`, 3,317 characters, in both trees.

### The fix is both necessary and sufficient, proved by execution

A `git archive HEAD` tree with **only** `ingestion/session_extraction.py` replaced by
my version:

| Tree | `prompt --pass 2` |
|---|---|
| `HEAD` untouched | **exit 2**, 19 lines |
| `HEAD` + my one file | **exit 0**, 82 lines |
| `HEAD` + my one file, **with the two `name_unencodable_characters` calls deleted** | **exit 2**, 19 lines, same `charmap` message |

The third row is a mutant written **into the scratch tree**, never into the
repository. Repository hashes at the start and at the end of the run:

```
ingestion/claude_extractor.py  b459e4eebc8f6cfc4172a24117e592f002f98ee5fe27187d2edeeb4fb69f7e35  (HEAD, and now)
extractions/WMT.json           c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675  (copy taken before my first edit, and now)
ingestion/session_extraction.py 2730e0339bbf675ea52c6b64b5ad531dea06b38b25e666f08e1a86597069254e  (HEAD)
ingestion/session_extraction.py 58b05fef1c5df517ab544eb7070d700391cef2ea83678d4b39148a2ed62843e0  (now — the one file in scope)
```

`git status --short` → `M ingestion/session_extraction.py` and this entry, nothing
else. `git diff --stat` → `1 file changed, 47 insertions(+)`, no deletions.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Fix the **stream**, not the prompt text | The two `→` are at `claude_extractor.py:412-413`, inside the Pass 2 prompt's `direction` rules — text route A sends to the model. `AGENTS.md`, "Escalate, do not decide alone", makes any change to the LLM boundary an escalation; `docs/2-rules/llm-boundary.md` makes `claude_extractor.py` the only file that may hold a prompt | Replacing `→` with `->` would change what every future route A extraction reads, to work around one console. It is also outside my file scope |
| `reconfigure(errors=…)` on `sys.stdout`/`sys.stderr` in `main()`, rather than an encoder around the four `print` calls in `cmd_prompt` | "What to do" step 3: fix it once, for every subcommand. All six subcommands print through these two streams, and `cmd_prompt` additionally redirects `parse_pass1`'s table to `sys.stderr` (`:1040`, `:1039` at `HEAD` — the one `import io` I added shifts every later line by 1) | An encoder around `cmd_prompt` leaves `plan`, `locate`, `text` and `check` exactly as exposed as they are today — they pass "by luck", as the assignment says — and has to be repeated at every print added later |
| Handler `namereplace` | "What to do" step 1: a fix that prints a replacement character silently is not acceptable, the reader must be able to tell an arrow was there. `namereplace` writes `\N{RIGHTWARDS ARROW}`, which names the exact character | `replace` writes `?` and `ignore` writes nothing: a reader cannot distinguish either from a prompt that never had an arrow. `backslashreplace` would write `\u2192`, correct but less readable to a human than the character's name |
| The **encoding** is left alone; only the error handler is set | Criterion 6: a UTF-8 console must still print `→` as `→`. An error handler only runs for a character the encoding cannot hold, so on UTF-8 it never runs | Forcing `encoding="utf-8"` would send UTF-8 bytes to a cp1252 console and print mojibake (`â†'`) for the arrow **and** for every em dash in `check`'s output — a fix that corrupts text that works today |
| No `PYTHONIOENCODING`, set or advised | "What to do" step 4 | An environment variable the program needs and does not set is a defect that moved rather than closed. The grep in criterion 7 is the check |
| The function takes `stream: object` and narrows with `isinstance` | Typeshed types `sys.stdout` as `TextIO`, which has no `reconfigure`; `isinstance(stream, io.TextIOWrapper)` narrows it for mypy and for the reader at once. Criterion 8 is unchanged at 5 errors | A `cast` or a `# type: ignore` would silence the checker instead of answering it. `STATUS.md` section 1: treat a type error here as a defect report |
| The new comment is written in ASCII | The assignment's fact table records `ingestion/session_extraction.py` holds no `→`. My first draft of the comment put three in it; I removed them and re-measured the count back to **0** | A file explaining a console that cannot hold a character should not need that console to hold one to be read |

**No change in this unit was made to reach a target number.** The only figures it moves
are an exit code and a line count, and both are the assignment's stated objective.

## Rule 3 — what stops, and what does not

This unit reads no financial value and produces no figure. It reads exactly one thing.

| Value read | If it were missing | Evidence |
|---|---|---|
| the runtime type of `sys.stdout` / `sys.stderr` | **does not stop; returns `False` and sets nothing** | `ingestion/session_extraction.py:1172-1188` (the function), called at `:1195-1196`. See the paragraph below — I do not believe this is a rule 3 defect, and I state the reasoning so a reviewer can overturn it |

**Why I did not make it stop, stated plainly so it can be disputed.** Rule 3 binds a
*missing input*: a value the run needs and does not have, which must not become a zero
or a default. Here there is no missing value. The predicate
`isinstance(stream, io.TextIOWrapper)` is not "is the encoding known?" — it is "does
this stream encode text to bytes at all?". A substitute that is not a `TextIOWrapper`
(an `io.StringIO` a caller put in `sys.stdout`'s place) keeps `str` and performs no
encode step, so **no character can be lost in it** and there is nothing an error
handler could do. Stopping the run because stdout was replaced by an object that
cannot lose a character would stop a run that is already safe. The function returns
`True`/`False` rather than `None` so that the outcome is a value a caller or a test can
assert on, instead of an invisible branch. `main` does not read it, which is the one
place a reviewer may reasonably want a finding — I chose not to print a note on every
run of all six subcommands, because that would change the byte-identical outputs
recorded under criterion 4.

A `TextIOWrapper` whose `reconfigure` raises (a detached or closed stream) is **not**
caught: the exception propagates. That is deliberate — it is a broken stream, not a
missing input.

## Measurements

**Failure sets, by name, not counts.**

The controlled pair is two scratch trees that differ in **one file**: both are
`git archive HEAD` with `extractions/WMT.json` copied in; the second also has my
final `ingestion/session_extraction.py` (sha `58b05fef…`, re-copied **after** my last
edit and re-run).

| Tree | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly` | Failure set |
|---|---|---|
| `/c/tmp/p14f/head` (before) | `1205 passed, 4 skipped` in 124.17s | **{ }** |
| `/c/tmp/p14f/mutant` (after, final file) | `1205 passed, 4 skipped` in 122.41s | **{ }** |

Both scratch trees skip 4 rather than 2: `tests/unit/_real_filings.py` resolves
`10K_filings/` from the tree root, and neither scratch tree holds the PDFs, so the two
Walmart/L3Harris real-filing tests skip there as well as the two for Chipotle and
Okta. That is a property of the scratch trees, not of this unit, and it is identical
on both sides of the pair.

The repository itself, run **after my last edit**:

| Run | Result | Failure set |
|---|---|---|
| gate `-q --ignore-glob="*_rule3_red.py" -p no:randomly -rs` | **1207 passed, 2 skipped, 0 failed**, 124.10s | **{ }** |
| full `-q -p no:randomly` | **2 failed, 1207 passed, 2 skipped**, 133.94s | **{ `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` }** — the two red on purpose |

The two skips are named by `-rs`: the Chipotle and Okta PDFs, which this machine does
not hold. **1207 / 2 / 0 is `STATUS.md`'s figure at `5567b39` exactly**, so no test
changed state.

**Gates, all run after my last edit** (sha `58b05fef…`):

| Gate | Result |
|---|---|
| Lint, `-m ruff check .` | **4 errors**, every one `BLE001` |
| Types, `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | **5 errors in 2 files**, 21 files checked |
| Census, the grep at `docs/2-rules/rules.md:102` | **64** |
| Route, `TestClient(app.app, raise_server_exceptions=False).get('/')` | **200** |
| Write guard, `.claude/check_guard.py` | **48/48** |

**The figure this unit moves**, and the input that produced it:
`prompt extractions/WMT.json --filing 0 --pass 2` on the real Walmart FY2024 10-K
(`10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf`, read through the session
file's Pass 1) goes from **exit 2 / 19 lines** to **exit 0 / 82 lines**. The 82 lines
are the same 82 `PYTHONIOENCODING=utf-8` produced at `HEAD`.

## What I did not do

- **I did not touch `ingestion/claude_extractor.py`.** The two arrows stay where they
  are, and that file is byte-identical (`b459e4ee…`). It is also `P14e`'s / `P14g`'s
  file scope.
- **I did not add tests.** `tests/` is out of scope for this unit and the write guard
  denies it. A tester has three things to lock that I measured by hand: the twelve
  prompt digests, the six exit codes, and the mutant in the table above (deleting the
  two calls must turn a test red).
- **I did not touch `cli.py` or `app.py`**, which the assignment puts out of scope.
  See the findings — one of them is live.
- I did not print a note when `name_unencodable_characters` returns `False`, for the
  reason in the rule 3 section.

## Findings for the orchestrator

1. **`cli.py --debug` has the same defect, live, on route A, and it stops *after* the
   paid API call.** `ingestion/claude_extractor.py:2420` and `:2593` print the model's
   raw response to stdout:
   `print(f"\n{'='*65}\nPASS 1 RAW RESPONSE\n{'='*65}\n{raw}\n{'='*65}\n")`. `raw` is
   whatever the model returned; nothing bounds it to the console's code page. A model
   answer holding one character outside cp1252 raises `UnicodeEncodeError` on this
   machine between the API call and the parse, so the extraction is paid for and then
   thrown away. Neither `cli.py` nor `app.py` configures its streams — this unit fixed
   `session_extraction.main` only. **An assignment could be written from this line
   alone**: give `cli.py`'s entry point the same two calls, or move
   `name_unencodable_characters` to a place both entry points can call. I did not
   widen my scope to do it.
2. **The repository's complete inventory of characters its own console cannot hold**,
   measured over every `.py` outside `.venv/` and `.claude/` by trying
   `ch.encode("cp1252")` on each character:
   - `ingestion/claude_extractor.py` — 14 × U+2192. **Two are printed** (`:412-413`,
     the Pass 2 prompt, which this unit now renders safely). The other twelve are at
     `:6`, `:10`, `:28-30`, `:1971`, `:2124`, `:3453-3455` — module and function
     docstrings, never printed.
   - `models/financial_statements.py:161` — 1 × U+2192, in a `#` comment, never
     printed.
   - `tests/test_e2e_phase2_googl.py:4-5` — 2 × U+2192, in the module docstring.
   - `tests/unit/test_statements_ui.py:832` — 1 × **U+2212 MINUS SIGN**, inside an
     assertion on rendered HTML: `assert "Balance Check Difference (Total Assets − [Liabilities + Equity])" in bs_metrics_table`. So a **template** prints U+2212 to the
     web page. That is served as UTF-8 and is fine on the page, but it means the
     balance-check string cannot be printed to this console either. Worth knowing
     before anyone moves that string into the CLI.
3. **`check`, `plan` and the `prompt` headers print `—` (U+2014) and `…` (U+2026).**
   Both are **in** cp1252, which is the whole reason the other five subcommands pass
   today. They would stop on a console whose code page is, for example, cp437 or
   cp850 — a plain `cmd.exe` default on some installations. The fix in this unit
   covers that case too, because it is about the stream rather than about any one
   character; the `cp437` case is not measured here because this machine's console is
   cp1252.
4. **`sys.stdout.errors` is `surrogateescape` on this machine, not `strict`.** Printed
   by `.venv/Scripts/python.exe -c "import sys; print(sys.stdout.encoding, sys.stdout.errors)"`
   → `cp1252 surrogateescape`. That handler does **not** rescue an ordinary
   unencodable character such as U+2192 — it only passes lone surrogates through — so
   it is not an existing defence and it was not one. Recorded because a reader seeing
   a non-`strict` handler may assume the stream was already safe.
