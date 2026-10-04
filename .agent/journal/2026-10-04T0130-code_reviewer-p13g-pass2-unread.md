---
agent: code_reviewer
assignment: P13g-pass2-unread
round: 1
verdict: approved
---

# Review of P13g-pass2-unread, round 1

Programmer entry: `.agent/journal/2026-10-04T0102-programmer-p13g-pass2-unread.md`

Diff reviewed: `git diff -- ingestion/claude_extractor.py`. It has one hunk, at `:1793-1821`, inside `_run_nri_pass`. No other line of the file moved. Scope is respected.

**Where I measured.** The write guard refused `scratchpad/p13g_reviewer/` inside the repository, so I measured outside it. I used two `git archive f6da3e9` exports in the session scratchpad (`.../scratchpad/p13g_reviewer/{tree,base}`). `tree` has only this unit's `ingestion/claude_extractor.py` copied in. Neither export has a `.env` (`ls -a | grep -c '^\.env$'` gives `0`). Every run removed the API key variables. `19298f3..f6da3e9` changes no `.py` file.

## The guard checks

I ran them over the `+` lines of the diff.

| Check | Result |
|---|---|
| conditional zero | clean |
| lookup with a fallback | clean |
| bare or-default | clean |
| money field defaulted to zero | clean |
| `**kwargs` | clean |
| `getattr(` | clean |
| dict of functions | clean |
| model client outside `ingestion/` (`models/ analysis/ api/`) | 0 hits |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| retry reply: unparseable, no field, null item, list item, string item | yes. A ValueError names ticker, company, Pass 1 years and both parse errors, with the cause chained | my cases c1, c3, c4, c5, c10 (below) |
| retry reply: `{"non_recurring_items": []}` | returns `[]`. That is a real answer, not a missing one | case c2b |
| retry reply: `"year": Infinity`, a 400-digit `amount`, nesting 200 000 levels deep | **stops**, with a raw `OverflowError` or `RecursionError`. The filing is not named | cases c6, c7, c8. See F1 |
| `financials.ticker`, `company_name`, `years` (message only) | printed with `!r` and no fallback | diff `:1813-1815` |

## Units and boundaries

| Check | Result |
|---|---|
| millions | no figure is touched |
| percentages at the route boundary | not applicable |
| falsy treated as missing | none |
| layering | the extractor only. No new import |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | an unparseable retry stops, naming the filing and the parse error | pass | c1: `RAISED ValueError calls=2 cause=ValueError`. The message names `'TEST'`, `'Test Co'` and both errors. Base: `RETURNED [] calls=2` | yes, for the four types. Not for the inputs in F1 |
| 2 | a parseable empty reply returns `[]` | pass | c2: `RETURNED [] calls=1`. c2b: `RETURNED [] calls=2`. c9 (bad, then good) returns 1 item | yes |
| 3 | no API call | pass | `_call_llm` is stubbed. `_call_claude`, `_call_gemini`, `anthropic.Anthropic.__init__`, `socket.connect` and `create_connection` all raise a BaseException that exits 2. Every case exited 0. No `.env`, no key in the environment | yes |
| 4 | lint falls by one | 4 | tree `Found 4 errors.`, all BLE001. Base 5, the extra one at `ingestion/claude_extractor.py:1798:16` | yes |
| 9 | fails only where expected | same 2 | tree and base each give `2 failed, 793 passed`. The **same two names**: `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`. Gate form: 793 passed on both | yes |
| 10 | gates do not get worse | ruff 4, mypy 10/4, census 65 | mypy `10 errors in 4 files` on both. Census `65` on both | yes |

I read the CLI and web claims and they hold. `cli.py:1143` prints `ERROR:` and exits 1. `_save_cache` at `cli.py:897` comes after the extraction. `api/routes_valuation.py:445` and `:703` render `error=str(e)`. `assumptions.html:9-10` shows it.

## The orchestrator's two questions

**Are the four caught types exactly what the parse raises?** Not too wide: I measured each one (ValueError c1/c3, TypeError c5, AttributeError c4/c10, KeyError per the programmer). AttributeError comes from the parse's own diagnostic `item.get` on an item that is not a dict. An AttributeError from a coding bug would be re-raised chained, not swallowed. **The list is too narrow by one or two types**: see F1.

**Is the first-attempt inconsistency a finding against this unit?** No. See F2. The unit did not touch those lines. They stop, so no rule is broken. The inconsistency is not in the backlog, so it needs a backlog item.

## Findings

### F1: the catch is narrower than the parse. `OverflowError` and `RecursionError` escape without naming the filing · `minor`

**Evidence:** case c6, a retry reply with `"year": Infinity`, gives `RAISED OverflowError calls=2 cause=None  msg: cannot convert float infinity to integer`. Case c7, a 400-digit `amount`, gives `OverflowError: int too large to convert to float`. Case c8, a 200 000-deep array, gives `RecursionError`. The comment at `ingestion/claude_extractor.py:1800-1805` says "The four types are the ones the parse raises", and that is not complete.
**Rule or document:** none of the six is broken: each input still stops the run, and nothing becomes `[]`. It falls short of the assignment's "Catch only the exception types the parse can raise" and of done-criterion 1 ("naming the filing") for these inputs. It also makes a code comment claim more than was measured.
**What would fix it:** add `OverflowError` to the tuple (`int(inf)` and `float(huge int)` are realistic model output). Either add `RecursionError` or state in the comment that a pathologically nested reply is left out. Correct the comment.

### F2: the first Pass 2 attempt stops inconsistently, with no retry and no filing name · `note`

**Evidence:** `ingestion/claude_extractor.py:1783` calls `_extract_json(raw)` outside the first `try`. `:1787` catches only `(json.JSONDecodeError, KeyError)`. So a reply with no `{`, a reply missing `non_recurring_items`, `confidence` or `source`, a TypeError or an AttributeError all stop on attempt one. They get no retry and the filing is not named. A KeyError does get a retry.
**Rule or document:** none. It stops, and the parse names the field. These lines are not in the diff, and the assignment fixes only the retry branch. **Not a finding against this unit.** `grep -n retry docs/9-reference/refactor-backlog.md` finds only item 61, so this is **not recorded**.
**What would fix it:** the orchestrator opens a backlog item. The fix: put both first-attempt calls inside the `try`, catch the same type list as the retry (after F1), and use one message shape. This matches the programmer's finding 1.

### F3: "names the filing" uses ticker, company and Pass 1 years, not the PDF path · `note`

**Evidence:** `_run_nri_pass(pdf_bytes, financials, resolution, ...)` at `:1754` receives no path. Its caller `extract_financials` at `:2234` holds `pdf_path`. Under F1's inputs the years list can be `[]`, so on a multi-filing run the message can name only the ticker.
**Rule or document:** none. The scope "`_run_nri_pass` only" forbids editing the caller. The programmer flagged this (its finding 2).
**What would fix it:** a later unit passes `Path(pdf_path).name` into `_run_nri_pass`. It can go with F2's unit.

## Pre-existing, already recorded, not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 8, the other blanket excepts | `api/routes_valuation.py:445`, `:703`, `cli.py:1143`, `tests/test_e2e_all_googl.py:106` | no |
| 61, the unreachable `return financials` after the Pass 1 retry | `ingestion/claude_extractor.py:1747` | no |
| (not recorded) the retry `_call_llm` sends no `pdf_bytes`, so the fix prompt re-sends only the malformed text | `:1793-1795` | no. It is consistent with "fix this JSON" and changes no figure. It is mentioned here only |

## Verdict

`approved`

The silent `return []` is gone. A reply that cannot be read now stops, with the filing identity and both parse errors. A real empty answer still returns `[]`. No test depended on the old behaviour. Lint fell 5 to 4. Every other gate and the failure set are unchanged. I measured all of this myself on an isolated export, with no network path reachable. F1 is a real gap in the completeness the orchestrator asked about. It breaks no rule, because every escaping input still stops, so it does not block. The orchestrator may send F1 back as a small fix with this unit, or fold it into the F2 backlog item. F2 and F3 belong to a separate unit.
