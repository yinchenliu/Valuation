---
agent: code_reviewer
assignment: P14f-prompt-encoding
round: 1
verdict: approved
---

# Review of P14f-prompt-encoding, round 1

Programmer entry: `.agent/journal/2026-10-06T1655-programmer-p14f-prompt-encoding.md`

Diff: one file, `ingestion/session_extraction.py`, 47 insertions, 0 deletions — one
`import io`, one module constant, one 10-line function, two calls at the top of `main`.
Nothing else is in the working tree. Repository sha256 at the start **and** at the end of
my run: `session_extraction.py 58b05fef…`, `claude_extractor.py b459e4ee…`,
`extractions/WMT.json c436e427…`. All my runs were in `/c/tmp/p14fr/{head,fixed,mutant}`.
`env | grep -i pythonio` → exit 1 (nothing set) for every criterion but 6.

## The guard checks

Run over `ingestion/session_extraction.py`, the one path in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean, 0 hits |
| lookup with a fallback — `.get(k, 0)` | clean, 0 hits |
| bare or-default — `or 0.0` | clean, 0 hits |
| money field defaulted to zero — `: float = 0.0` | clean, 0 hits |
| `**kwargs` on a calculation function | clean, 0 hits |
| `getattr(` on a name from outside the file | clean, 0 hits |
| dict of functions keyed by data | clean, 0 hits |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → 0 hits |

## Rule 3, by reading

The unit reads one value and produces no figure.

| Value | Stops and names it? | Evidence |
|---|---|---|
| the runtime type of `sys.stdout` / `sys.stderr` | **no — returns `False` and sets nothing** | `ingestion/session_extraction.py:1185-1188`, called at `:1195-1196`. See F1: I judged the programmer's argument and I accept it |

**The judgement the orchestrator asked for (C).** I accept the programmer's reasoning,
and here is the test I applied rather than the one it applied. Rule 3's harm is a value
that means "we do not know" becoming a number that renders. Ask what happens on the
`False` branch: nothing is set, the stream keeps the handler it had, and the next
unencodable character raises `UnicodeEncodeError` — **the run stops with the same message
it stops with today**. The branch therefore fails *towards* a stop, never towards a
figure. That is the opposite of the defect rule 3 names, so the "it is only defensive"
counter-argument from my role card does not apply: this defence does not return `0.0`, it
returns the pre-existing stop. Not a rule 3 finding.

I also checked the predicate's claim empirically rather than reading it:
`name_unencodable_characters(io.StringIO())` → `False`, and a `StringIO` performs no
encode step, so no character can be lost in it. The claim holds for the substitute the
docstring names.

Rule 2 does not bite either. Rule 2 forbids `**kwargs`, an untyped argument bag, and a
function selected at run time. The signature is `name_unencodable_characters(stream:
object) -> bool`, fixed and typed; the call site is two literal lines of Python in git.
An unread return value is a maintainability question, not a rule 2 question — it is F1,
and it is a `note`.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | n/a — this unit reads and produces no financial figure |
| percentages converted at the route boundary, once | n/a |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean — the one test is `isinstance(stream, io.TextIOWrapper)`, a type test, not a truth test |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean — the one new import is `io`, stdlib |
| **LLM boundary** | clean, and measured: `claude_extractor.py` is byte-identical (`b459e4ee…`) and all 12 prompt digests are unchanged. See criterion 5 |

## Done-criteria, re-run

Every row below I executed myself, with `.venv/Scripts/python.exe`,
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`, and no `PYTHONIOENCODING` except row 6. The `head`
tree is `git archive 44788e8` (no `.py` moved since `10eb315`) with `extractions/WMT.json`
copied in; its `session_extraction.py` hashes `2730e033…`, the programmer's `HEAD` figure.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | `prompt --pass 2` finishes | exit 0, 82 lines | **exit 0, 82 lines**, `RIGHTWARDS ARROW` on 2 lines, no `ERROR:` | yes |
| 2 | old behaviour reproduced | exit 2, 19 lines | **exit 2, 19 lines**, line 18 `ERROR: 'charmap' codec can't encode character '→' in position 2992`. `git archive`, no `git stash` | yes |
| 3 | the two rendered lines | quoted | `cat -A` of lines 67-68 reproduces the programmer's quote **byte for byte**, incl. the `$` EOL marker | yes |
| 4 | all six subcommands | 6 of 6 exit 0 | `head`: `0,0,0,0,**2**,0`. `fixed`: **`0,0,0,0,0,0`**. The five that already passed are **byte-identical** after path normalisation (`plan`, `locate`, `text`, `prompt --pass 1`, `check` all `IDENTICAL`) | yes |
| 5 | no prompt byte moved | 12 of 12 digests identical | **I wrote my own script** (`/c/tmp/p14fr/rev_hash_prompts.py`), imported `pass1_prompts`/`pass2_prompts`/`parse_pass1` from each tree via `PYTHONPATH`, hashed all 4 strings × 3 filings. `diff` of the two 13-line outputs is **empty**. My digests equal the programmer's, incl. `pass2 system 843ce6e7… len 3317` in both trees | yes |
| 6 | UTF-8 console not degraded | exit 0, 82 lines, `→` as `→` | **exit 0, 82 lines**, `U+2192` count **2**, `\N{` count **0**, `U+2014` count 4 — and the `fixed` UTF-8 output is **byte-identical to `head`'s** after path normalisation | yes |
| 7 | nothing sets `PYTHONIOENCODING` | no match | `grep -rn PYTHONIOENCODING ingestion/` → exit 1. Whole repo `--include=*.py --exclude-dir=.venv` → exit 1 | yes |
| 8 | types | 5 errors in 2 files | **5 errors in 2 files (checked 21 source files)**: 4 `analysis/projector.py`, 1 `api/routes_upload.py`. 0 in `ingestion/` | yes |
| 9 | lint | 4, every one `BLE001` | **`Found 4 errors`**, and `ruff check . \| grep -oE "^[A-Z]+[0-9]+" \| sort \| uniq -c` → **`4 BLE001`** | yes |
| 10 | census | 64 | **64** | yes |
| 11 | route | 200 | **200** | yes |
| 12 | failing test set | no test changed state | `-q --ignore-glob="*_rule3_red.py" -p no:randomly` on the working tree → **1207 passed, 2 skipped, 0 failed**. Failure set **{ }** after, **{ }** at `HEAD` (`STATUS.md` §1 at `5567b39`, and the lead's own re-measure). Compared **by name**: both empty | yes |

Also re-run: write guard **48/48**.

### D — necessary and sufficient, my own mutation

Three trees differing in one file; the mutant is the fixed file with **only** the two
calls at `:1195-1196` deleted (`diff fixed mutant` → exactly those two lines).

| Tree | `prompt --pass 2` |
|---|---|
| `head` | **exit 2**, 19 lines |
| `fixed` | **exit 0**, 82 lines |
| `mutant` | **exit 2**, 19 lines |

`diff head.out mutant.out` differs only in the scratch path: the same
`ERROR: 'charmap' codec can't encode character '→' in position 2992`. The two calls
are the whole fix, and nothing else in the 47 lines is load-bearing on its own.

### A — the two halves of the handler argument, tested

**Half one, the encoding is genuinely left alone.** In the `fixed` tree:
`sys.stdout.encoding, sys.stdout.errors` is `cp1252 surrogateescape` before the call and
**`cp1252 namereplace`** after. The encoding does not move; only the handler does. So the
alternative the programmer rejected — forcing `encoding="utf-8"` onto a cp1252 console —
is correctly rejected, and the rejection is visible in the measurement.

**Half two, nothing already printable is touched.** Counting raw bytes in all twelve
outputs: the em dash (`0x97`) and ellipsis (`0x85`) counts are **identical** in `head` and
`fixed` for every subcommand — `plan` 1/3, `prompt --pass 1` 3/0, `check` 5/3. The only
output that gains anything is `prompt --pass 2`, which gains exactly **2** `\N{` escapes.
No output anywhere contains a `?` substitution or a replacement character. The claim holds
on both halves.

**`namereplace` over `replace` is the right choice and the assignment forces it.** Step 1
forbids a silent replacement. Measured directly on a cp1252 `TextIOWrapper`:
`'arrow → sur \udcff ctrl \u0085 end'` writes as
`b'arrow \\N{RIGHTWARDS ARROW} sur \\udcff ctrl \\x85 end'` — `namereplace` is never
silent, falling back to a visible escape even for a character with no Unicode name.
`replace` would have written `?`, which step 1 rules out.

I also confirmed the programmer's finding 4 rather than reading it: on a cp1252 stream
with `errors='surrogateescape'`, writing `→` still raises
`UnicodeEncodeError: 'charmap' codec can't encode character '→'`. The inherited
handler was not a defence.

## Findings

### F1 — `name_unencodable_characters` returns a `bool` that no caller reads, and the docstring promises one will · `note`

**Evidence:** `ingestion/session_extraction.py:1180-1181` — *"Returns True when the handler
was set and False when the stream does not encode, so a caller can tell the two apart"* —
against `:1195-1196`, where both calls discard the value.
**Rule or document:** none. I checked rule 3 and rule 2 above and neither is broken: the
`False` path leads to the pre-existing stop, not to a number, and the signature is fixed
and typed with a literal call site. This is the maintainability half only.
**What would fix it:** either let the tester assert on the return (which is what the
programmer's entry anticipates, and is a legitimate consumer), or drop the sentence from
the docstring so the next reader does not look for a caller that is not there. **This does
not block.**

### F2 — `main()` mutates process-global streams and never restores them, and it is called in-process by the suite · `note`

**Evidence:** `tests/unit/test_session_extraction.py:1180` calls `main(["check", …])` in
the pytest process, and `_pytest.capture.CaptureIO` **is** an `io.TextIOWrapper` subclass
(`issubclass(...)` → `True`), so that one call leaves `errors='namereplace'` on the
captured stdout for every test that runs after it.
**Rule or document:** none. Measured harmless: the gate is **1207 passed, 2 skipped, 0
failed** with the change, the same failure set as `HEAD`.
**What would fix it:** nothing, today. Recorded because an entry point that configures its
own streams is correct, but `main` here is also an ordinary importable function, and the
next person who calls it from a library context will inherit the side effect silently.

### F3 — the inherited `surrogateescape` handler is replaced rather than composed, and the entry does not say so · `note`

**Evidence:** `sys.stdout.errors` goes `surrogateescape → namereplace`. On the same
stream, a lone surrogate previously round-tripped to its original byte; it now prints
`\udcff` (measured above).
**Rule or document:** none. The entry's finding 4 says `surrogateescape` was never a
defence against `U+2192`, which I confirmed, but it does not state that the change
*removes* it.
**What would fix it:** nothing in the code — the new behaviour is visible where the old
one was raw bytes, which is the direction the assignment asks for. Recorded so a future
reader does not rediscover it as a regression.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 122 — `cli.py --debug` has item 113's defect on route A and stops **after** the paid API call | `ingestion/claude_extractor.py:2420`, `:2593`, `cli.py`, `app.py` | **no.** `claude_extractor.py` is byte-identical (`b459e4ee…`); neither `cli.py` nor `app.py` is in the working tree |
| 113 — the defect this unit closes | `ingestion/session_extraction.py` (`cmd_prompt`) | yes, and it is fixed |

**I saw item 122 and it is already recorded.** I was asked to judge whether stopping there
was right, and it was. The assignment's "Out of scope" names `cli.py`'s console output
explicitly and tells the programmer to write it as a finding instead; the programmer did,
with two file-and-line citations and the cost (a paid call lost between the API and the
parse); the orchestrator backlogged it as 122. That is the process working, not a scope
gap. It is also not a rule break — it is a crash risk in untouched lines — so my role
card's "an out-of-scope call site forces `changes_requested`" does not apply here.

The programmer's findings 2, 3 and 4 are likewise recorded in item 122's entry and in this
review. None is a defect of this unit.

**No recorded user decision was claimed by this assignment, and none was needed.**

## Earlier findings — re-reviews only

None. This is round 1.

## Verdict

`approved`

All twelve done-criteria re-run and all twelve agree, including the two I was told not to
take on report: I computed the twelve prompt digests with my own script in both trees and
the diff is empty, and I built the mutant myself and watched it go back to exit 2 with the
identical `charmap` message. The fix is the smallest one that could work — it changes the
stream, never the prompt — and the LLM boundary is untouched by measurement, not by
assertion. The one judgement the programmer asked for goes its way: the `False` branch of
`name_unencodable_characters` leads to the pre-existing stop, never to a number, so it is
not rule 3, and a fixed typed signature with a literal call site is not rule 2. The three
findings are all `note`: an unread return value, an un-restored global side effect, and a
replaced error handler worth recording. None cites a rule and none blocks. Dispatch the
tester; the three things worth locking are the twelve digests, the six exit codes, and the
mutant that deletes `:1195-1196`.
