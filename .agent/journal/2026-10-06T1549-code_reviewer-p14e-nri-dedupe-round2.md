---
agent: code_reviewer
assignment: P14e-nri-dedupe
round: 2
verdict: approved
---

# Review of P14e-nri-dedupe, round 2

Programmer entry: `.agent/journal/2026-10-06T1432-programmer-p14e-nri-dedupe-round2.md`
Round 1 review (a different reviewer): `.agent/journal/2026-10-06T1412-code_reviewer-p14e-nri-dedupe.md`

Diff reviewed: `git diff -- ingestion/claude_extractor.py` at `5291710` — one source file,
191 insertions, 7 deletions (rounds 1 and 2 together; `git diff --stat` also shows
`.agent/journal/INDEX.md`, one line, the lead's own index row). **Round 2 alone** is the
diff of round 1's file (`/c/tmp/p14e/after/ingestion/claude_extractor.py`, sha256
`578bd18a…`, the hash the round 1 reviewer measured at both ends of its run) against the
working tree: six hunks, all between `nri_identity` and the end of
`merge_filing_extractions`. I reviewed that six-hunk diff, and re-ran the whole unit.

**Repository files, before and after my run.** `ingestion/claude_extractor.py`
`b459e4ee…b69f7e35` at both ends; `extractions/WMT.json`
`c436e427…c008a3675` at both ends. Every execution of mine was in `C:\tmp\rev14e2\`
(`head` = `git archive` of `5291710`, `after` = the same archive with only this file replaced,
`round1` = the same archive with round 1's file, plus three one-line mutants). I wrote
nothing into the repository but this entry, and I mutated no file in it.

**`HEAD` moved during my run**, from `5291710` to `94df37a` ("round 2 entry, and the
tester assignment"). `git show --stat 94df37a` → three files, all under `.agent/`, **no
`.py` file**, so my `head` tree is still byte-identical in source to current `HEAD` and
every measurement below stands. The code is still uncommitted:
`git status --short` → `M ingestion/claude_extractor.py` and this entry, nothing else.

## The guard checks

Run over `git diff -U0 -- ingestion/claude_extractor.py`, the only file in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean |
| lookup with a fallback — `.get(k, 0)` | clean. The two `.get` calls added, `kept_rows_this_filing.get(row_key)` (`:3013`) and the pre-existing `kept_by_key.get(key)` (`:3021`), are one-argument presence tests |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean. `NriIdentityWithinFiling` is a tuple type alias; `kept_rows_this_filing` maps a tuple to an item, and `from_this_filing` maps a tuple to an `(item, filename)` pair — data, not behaviour. `REPEAT_ACROSS_FILINGS` / `REPEAT_WITHIN_ONE_FILING` are `str` constants and each call site passes one literally (`:3016`, `:3031`), so the call site is readable in git |
| model client imported outside `ingestion/` | clean (`grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output) |

`from_this_filing.setdefault(key, (item, filing_name))` (`:3028`) is not caught by the
`.get` grep and I checked it by reading: it is an insert-if-absent whose return value is
discarded, not a read-with-a-fallback. No value is substituted for a missing one.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `item.page` — **the field this round added to a key** | yes. `page: int`, required, no default, so an absent key stops in the Pass 2 parser before the merge runs | `models/financial_statements.py:77` |
| `item.year`, `item.amount`, `item.direction`, `item.description` (both identity functions) | yes — all four required with no default | `models/financial_statements.py:67-72` |
| `kept_rows_this_filing.get(row_key)` → `None` | n/a — a presence test. `None` means "this filing has not kept this row yet" and that branch does real work (the across-filing comparison); a hit prints and drops. No value substituted | `ingestion/claude_extractor.py:3013-3018` |
| `kept_by_key.get(key)` → `None` | unchanged from round 1, checked there at `:2930` | `ingestion/claude_extractor.py:3021-3032` |
| `headline: str` (the new parameter) | not a data value, and it has **no default**: both call sites pass a module constant, literal in git. A missing one is a `TypeError`, not a silent fallback | `:2904-2910`, `:3016`, `:3031` |
| census, before and after | **64 → 64**, the grep at `docs/2-rules/rules.md:102` over `models analysis api ingestion`, run in the working tree after the last edit. No site added, none removed |

Rule 1 is kept: both keys are exact equality on named fields, with no tolerance, no
normalisation and no similarity rule. Nothing here decides that two texts mean one charge.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | yes. The `$M` label in `_print_repeated_item` is unchanged from round 1 and still correct: both routes run `convert_filing_to_millions` per filing before the merge. Measured on the real file through route B: the raw Asda item is `0.2`, the printed row is `200.0 $M` (`/c/tmp/rev14e2/check_dup.txt:58`) |
| percentages converted at the route boundary, once | n/a — this unit touches no route boundary |
| falsy not treated as missing | yes. `repeated_row is not None` and `repeated is None`, not `if repeated_row:` / `if repeated:` (`:3014`, `:3022`) |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | unchanged — this unit adds no import |

## Done-criteria, re-run

Every row is my own execution, with `ANTHROPIC_API_KEY= GEMINI_API_KEY=
PYTHONIOENCODING=utf-8` and `.venv/Scripts/python.exe`. My hand-built cases are
`/c/tmp/rev14e2/hand.py`; each captures the merge's own stdout, so `DROPS REPORTED: 0` is
a counted absence of `[MERGE]` lines.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 15 | Identical row twice in one filing is one item, drop reported | 1 item, 1 drop, both copies named with page | hand case → `RESULT: 1 item(s)   DROPS REPORTED: 1`, `kept`/`dropped` both `[FY2024.pdf, page 66]`. **Real route B**, my own `/c/tmp/rev14e2/WMT_dup_row.json` (a copy of `WMT.json` with filing 0's Asda row appended verbatim): `check` → `EXIT=0`, `non-recurring items: 14` from 15 written, `[MERGE]` block at `check_dup.txt:57-59` | yes |
| 16 | Asda and Seiyu still survive | 2 items, 0 drops | hand case → `RESULT: 2 item(s)   DROPS REPORTED: 0`, pages 66 and 67 | yes |
| 17 | Alike in every field but the page, one filing | 2 items, no drop | hand case (same description, pages 66 and 67) → `RESULT: 2 item(s)   DROPS REPORTED: 0` | yes |
| 18 | Walmart does not move | `MERGED 14`, Asda and Seiyu present; fiscal 2022 identical to round 1 | `after` → `MERGED 14  ASDA True  SEIYU True`; `head` → `MERGED 13  SEIYU False` (criterion 2 still reproduces). Through `pipeline.adjust_financials`, fiscal 2022 in `after` and in my `round1` tree are **identical**: applied 14, `other_non_operating -200.0`, `ebit 25942.0`, `operating_margin 0.045293441861602016`, `ebt 23906.0`, `tax_expense 4756.0`, `effective_tax_rate 0.19894587132937339` | yes |
| 19 | Cross-filing behaviour does not move | criteria 3, 4, 5, 6 unchanged; message identical | **3**: one item re-reported by a later filing → `RESULT: 1 item(s)` in both `round1` and `after`. **4**: the `[MERGE]` block names year, amount, direction, description, filing and page of both, and is **byte-identical** between `round1` and `after`. **5**: the merge returned and my script printed after it; route B `check` → `EXIT=0`. **6**: two different items in one filing → `RESULT: 2 item(s)   DROPS REPORTED: 0`. Three filings re-reporting one item → 1 item, 2 drops, both against the first-kept, same in both trees | yes |
| 20 | Gates after the last edit | types 5 in 2, lint 4 all `BLE001`, census 64, route 200 | **types** `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → `Found 5 errors in 2 files (checked 21 source files)`: 4 `union-attr` in `analysis/projector.py`, 1 `operator` in `api/routes_upload.py`, **0 in `ingestion/`**. **lint** `-m ruff check . --output-format=concise` → `Found 4 errors`, all `BLE001` (`api/routes_valuation.py:451`, `:733`, `cli.py:1204`, `tests/test_e2e_all_googl.py:106`). **census** 64. **route** 200. All four in the repository root | yes |
| 21 | The failing test set | the same two as round 1, no others | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly`. `head` → `1173 passed, 4 skipped` in 151.14s, failure set **{ }**. `after` → `2 failed, 1171 passed, 4 skipped` in 145.82s, failure set **exactly** `{tests/unit/test_claude_extractor.py::test_merge_keeps_one_item_per_year_amount_direction, tests/unit/test_session_extraction.py::test_three_filings_both_routes_give_equal_statements_and_items}`. `diff` of the two sorted `FAILED`/`ERROR` lists is the two lines and nothing else. **My skip count is 4, not the lead's 2**, in *both* trees, because my scratch trees have no `10K_filings/`; the two trees are therefore comparable with each other, which is what criterion 21 asks | yes |
| 8 | Route A unchanged in what it asks the model | no prompt, no schema | `git diff \| grep -icE "^[+-].*(_PASS1_\|_PASS2_\|_SCHEMA\|prompt\|SYSTEM\|system_prompt\|json_schema)"` → **0** | yes |

Criteria 1–14 were re-run and agreed by the round 1 reviewer; of those, 2, 4, 5, 6, 8–12
I re-ran again above and they still hold. Criterion 14 (the market call) is not in this
round's list, and the identical fiscal 2022 figures above are the stronger statement: no
figure moved at all between round 1 and round 2.

## The four things the lead asked for

**A — the unasked tightening. The reason is real, the change is correct, and it moves a
message and not a count.** I built the mutant the programmer's reason describes
(`/c/tmp/rev14e2/mut_notighten`, one line: `kept_rows_this_filing[row_key] = item` moved
above the `repeated_row is not None` test, so every row registers whether or not it was
kept) and ran the same cases. In the compound case — an earlier filing already reported
the item **and** this filing writes its row twice — both trees give `RESULT: 1 item(s)
DROPS REPORTED: 2`, so the **count is identical**. The difference is one word: the mutant
prints `kept   : … [F2025.pdf, page 51]`, naming the row it had itself just dropped, where
`after` prints `kept   : … [F2024.pdf, page 52]`, the item that really is in the merged
list. Every other case in my set is identical between the two. So the tightening is
exactly what the programmer says it is — it makes `kept:` true and changes nothing else —
and an unasked change with a reason that holds is not a finding.

**B — the two keys, re-measured by mutation in my own trees.** Both mutations reproduce.

| Tree | The one line changed | 15 | 16 | **17** | **19 / 3,4,5** | 19 / 6 | three filings |
|---|---|---|---|---|---|---|---|
| `after` | — | 1 item, 1 drop | 2, 0 | **2, 0** | **1, 1 drop** | 2, 0 | 1 item, 2 drops |
| `mut_nopage` | `page` removed from `nri_identity_within_filing` | 1, 1 | 2, 0 | **1 item, 1 drop — FAILS 17** | 1, 1 | 2, 0 | 1, 2 |
| `mut_pagecross` | `page` added to `nri_identity` | 1, 1 | 2, 0 | 2, 0 | **2 items, 0 drops — FAILS 19/3** | 2, 0 | **3 items, 0 drops** |

So `page` is load-bearing in the within-filing key (without it a real item of the same
size on another page is dropped) and must be absent from the across-filing key (with it
the merge stops merging and a re-reported item is counted once per filing). The docstrings
say exactly this, and now so does an execution.

**C — `extractions/WMT.json` catches neither mutant. Confirmed, and the tester assignment
needs to hear it.** `after`, `mut_nopage`, `mut_pagecross` and `mut_notighten` **all**
give `MERGED 14` with `ASDA in list: True` and `SEIYU in list: True` on the real file;
only `head` gives `MERGED 13 / SEIYU False`. The real file has no cross-filing year overlap
and no repeated row, so it cannot see the boundary this round draws. **A tester that
measures this unit only against `extractions/WMT.json` would pass three broken versions of
it.** The hand-built cases 15, 16, 17 and 19 are not optional. This is the programmer's
finding 2 and I reproduced it independently.

**D — round 1's cross-filing behaviour did not move.** I ran my cases against round 1's
file (`578bd18a…`) and against the working tree. The cross-filing `[MERGE]` block is
identical character for character, including the headline
`Non-recurring item already reported by an earlier filing - counted once, not twice:`;
criteria 3, 4, 5, 6 and the three-filing case give the same results in both. `nri_identity`
returns the same four-field tuple in both — `diff` shows only docstring additions (a
cross-reference to the new function and the measured `page 52` → `page 51` example), with
the `return` line and the signature untouched. Through `pipeline.adjust_financials` on the
real file, every fiscal 2022 figure is identical between `round1` and `after` (table under
criterion 18). The only two cases that move between round 1 and round 2 are the ones the
amendment asked to move: the identical row twice (2 items, silent → 1 item, 1 reported
drop) and three identical rows (3 → 1, 2 reported drops).

## Findings

### F5 — a doubled row that an earlier filing also reported prints two byte-identical `[MERGE]` blocks · `note`

**Evidence:** `/c/tmp/rev14e2/hand.py`, case `BOTH AT ONCE` → `RESULT: 1 item(s)
DROPS REPORTED: 2`, and the two blocks are identical in all three lines, both
`dropped: 2023  10.0 $M  add_back  'R'  [F2025.pdf, page 51]`.
**Rule or document:** none. Both drops are reported, each dropped row is named once, the
count is right and the `kept:` line is true — this is the correct behaviour under the
amendment, and it is only a reader's problem: two identical blocks look like one message
printed twice. The related wording point is the same note: `REPEAT_WITHIN_ONE_FILING` says
"listed twice by one filing" and prints twice when a row appears three times
(`THREE IDENTICAL ROWS` → 2 blocks, both saying "twice").
**What would fix it:** nothing in this unit. It is the other half of the programmer's
finding 1 — a per-run total beside `non-recurring items: 14` would make the count
checkable at a glance — and that line is owned by `ingestion/session_extraction.py`, out
of scope. For the orchestrator's backlog, not the programmer's.

No other finding. I looked specifically for a new rule 3 site, a falsy-as-missing test, a
unit crossing, a dispatch table and a scope escape, and found none.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 119 — a differently-worded cross-filing re-report is a silent double-count | `refactor-backlog.md:154` | no, and settled by the lead as out of this round. I reproduced it (`DIFFERENT WORDING` case → 2 items, 0 drops) and I am not reopening it |
| 62 — no failed reading check reaches the web page, either route | `refactor-backlog.md:97` | no. Both `[MERGE]` messages inherit the same gap; the assignment told the programmer to stop at a finding |
| 112 — this unit's defect | `refactor-backlog.md:147` | yes, and closed. Its write-up now carries round 1's effective-tax-rate correction, which closes the earlier reviewer's F3 |
| 113 — Pass 2 prompt console encoding | out of scope by the assignment | no. I used `PYTHONIOENCODING=utf-8` throughout |
| 53, 73, 79, 80, 84, 114 — same file, each recorded | out of scope by the assignment | no |

The 4 `BLE001` lint sites and the 5 mypy errors are all outside this file and unchanged at
`HEAD`.

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| F1 — identical row twice in one filing kept twice, silently (`minor`) | **fixed** | The amendment's key landed. Criterion 15 in my own run: `RESULT: 1 item(s)   DROPS REPORTED: 1`, and the real route B variant gives 14 merged from 15 written with the drop printed. Criteria 16 and 17 show the boundary holds from both sides |
| F2 — differently-worded cross-filing re-report is a silent double-count (`note`) | **not_fixed, by decision** | Recorded as backlog item 119 (`refactor-backlog.md:154`) and ruled out of this round by the amendment's "Not in this round". Deciding two texts mean one charge is rule 1's judgement for the model. Not reopened |
| F3 — the programmer's finding 3 attributed to the backlog a sentence only in the assignment (`note`) | **fixed** | Item 112's write-up now names the effective tax rate and the measured values (`refactor-backlog.md:147`), and the assignment carries the "Corrected 2026-10-06, after round 1" paragraph |
| F4 — `nri_identity` is public with no caller outside the file (`note`) | **not_fixed, and right as it is** | Still no external caller (`grep -rn "nri_identity\|REPEAT_ACROSS_FILINGS\|REPEAT_WITHIN_ONE_FILING\|NriIdentity" --include=*.py .` hits only `ingestion/claude_extractor.py`). `nri_identity_within_filing` and the two headline constants are public for the same stated reason — the tester needs to name them rather than copy a literal. I agree, and the programmer raised it itself (its finding 3) |

## Verdict

`approved`

The round 2 diff does one thing: it gives the within-filing comparison its own five-field
key, reports its drops through the same function and the same two rows as the cross-filing
one, and says in three docstrings which key applies where and why `page` is in one and not
the other. I re-ran all seven amendment criteria and the earlier ones that could have
moved, and they agree. The claim that `page` is load-bearing in exactly one key reproduces
under my own mutants, in both directions. The claim that round 1 did not move reproduces:
the cross-filing message is byte-identical and every fiscal 2022 Walmart figure is
unchanged. The one unasked change — registering a row in the within-filing map only when
it is kept — has a reason that holds, and I measured that it moves a false `kept:` word
and no count at all. No guard check hits, the census is unmoved at 64, no rule in
`docs/2-rules/rules.md` is broken, and the only finding is a `note` about readability that
belongs to `ingestion/session_extraction.py`. **Two things for the orchestrator:** the
tester assignment must carry the hand-built cases 15, 16, 17 and 19, because
`extractions/WMT.json` passes three different broken versions of this merge; and the two
red tests still build their repeat with a different description and still need
re-expressing, unchanged in cause and count from round 1.
