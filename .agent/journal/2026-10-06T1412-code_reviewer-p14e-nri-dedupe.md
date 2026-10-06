---
agent: code_reviewer
assignment: P14e-nri-dedupe
round: 1
verdict: approved
---

# Review of P14e-nri-dedupe, round 1

Programmer entry: `.agent/journal/2026-10-06T1229-programmer-p14e-nri-dedupe.md`

Diff reviewed: `git diff -- ingestion/claude_extractor.py` at `b6dbdd0`, 98 insertions,
7 deletions, one file. `git diff --name-only` also lists `.agent/journal/INDEX.md`
(one line, the lead's own index row for the programmer's entry) — not the programmer's,
`files_touched` names one file and the diff agrees.

**Repository files, before and after my run.** `ingestion/claude_extractor.py`
`578bd18ab3ac8ae71460f7ede740fda9747a134f87c88b281376eb7343d4d453` at both ends;
`extractions/WMT.json` `c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675`
at both ends. Every run of mine was in `C:\tmp\rev14e\head` (`git archive HEAD`) and
`C:\tmp\rev14e\after` (the same archive with only this file replaced), each given a copy
of `extractions/` and `10K_filings/`. I wrote nothing into the repository but this entry.

## The guard checks

Run over `ingestion/claude_extractor.py`'s diff (`git diff -U0`), which is the only file
in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean |
| lookup with a fallback — `.get(k, 0)` | clean. `kept_by_key.get(key)` at `:2930` is one-argument and is a presence test |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean. `NriIdentity` is a tuple type alias; `kept_by_key` maps a tuple to a `(item, filename)` pair — data, not behaviour. Rule 2's "lookup a number, never behaviour" is kept |
| model client imported outside `ingestion/` | clean (`grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output) |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `item.year`, `item.amount`, `item.direction`, `item.description` in `nri_identity` | yes — all four are required fields with no default, so an absent key stops in the parser before the merge | `models/financial_statements.py:67-72` |
| `item.page` (message only) | yes — required, no default | `models/financial_statements.py:77` |
| `plan.pdf_path` (`Path(...).name`) | yes — required field of `FilingPlan`, and `plan_filings` raises on an empty list | `ingestion/claude_extractor.py:2754`, `:2775-2776` |
| `kept_by_key.get(key)` → `None` | n/a — a presence test, not a default. Both branches do work: `None` appends the item, a hit prints and drops. No value is substituted for a missing one | `ingestion/claude_extractor.py:2930-2939` |
| census, before and after | **64 → 64**, the grep at `docs/2-rules/rules.md:102` over `models analysis api ingestion`, run in my own `head` tree and in the working tree. No site added, none removed |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | **yes, measured.** The `$M` label in `_print_repeated_item` is correct: both routes run `convert_filing_to_millions` per filing before the merge (`claude_extractor.py:3135`, called inside `extract_financials` at `:3415`; route B at `session_extraction.py:794-797`). The raw WMT item is `0.2`, the merged item is `200.0` |
| percentages converted at the route boundary, once | n/a — this unit touches no route boundary |
| falsy not treated as missing | **yes.** `repeated is None`, not `if repeated`. An `if repeated:` would have been wrong here for a different reason, but the `is None` form is the correct one and it is what is written (`:2931`) |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | unchanged — this unit adds no import at all |

## Done-criteria, re-run

Every row below is my own execution, in my own scratch trees, with
`ANTHROPIC_API_KEY= GEMINI_API_KEY= PYTHONIOENCODING=utf-8` and
`.venv/Scripts/python.exe`.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | Both Walmart items survive | 14 merged, Asda and Seiyu both present | `MERGED 14`; `2022 200.0 add_back p66 … Asda` and `2022 200.0 add_back p67 … Seiyu` both printed; `ASDA True SEIYU True` | yes |
| 2 | Old behaviour reproduced at `HEAD` | 13 merged, Seiyu absent | `git archive HEAD` tree → `MERGED 13`, `ASDA True`, `SEIYU False`. No `git stash` | yes |
| 3 | One item re-reported by two filings is merged once | 1 item | my own hand-built merge: two filings, same `(2023, 10.0, add_back, "Restructuring charges in the Mexico segment")`, different pages (52, 51) → `RESULT: 1 item(s)`. Three filings re-reporting it → `RESULT: 1 item(s)`, two `[MERGE]` lines both reported against the first-kept | yes |
| 4 | A drop is reported, naming both | names year, amount, direction, description, filing, page of both | my own output: `kept   : 2023  10.0 $M  add_back  'Restructuring charges in the Mexico segment'  [F2023.pdf, page 52]` / `dropped: … [F2024.pdf, page 51]` | yes |
| 5 | A drop does not stop the run | returns, run continues | the merge returned and my script printed its result after the `[MERGE]` line; the route B `check` on the real file exits 0 | yes |
| 6 | Two items in one filing are never merged | both survive, both shapes | 6a Asda+Seiyu in one filing → `RESULT: 2 item(s)`, nothing printed. 6b the identical row twice in one filing → `RESULT: 2 item(s)`. See **F1** on 6b | yes, and F1 |
| 7 | The key's fields are stated | docstring names each | `ingestion/claude_extractor.py:2813-2845`: one bullet per field in the key, two bullets for `page` and `source` saying why they are out, then the exact-equality statement | yes |
| 8 | Route A unchanged in what it asks the model | no prompt, no schema | `git diff \| grep -icE "^[+-].*(_PASS1_\|_PASS2_\|_SCHEMA\|prompt\|SYSTEM\|system_prompt\|json_schema)"` → **0**. `git diff --name-only` → one source file | yes |
| 9 | Types ≤ 5 in 2 | 5 in 2 | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → **Found 5 errors in 2 files (checked 21 source files)**: 4 `union-attr` in `analysis/projector.py`, 1 `operator` in `api/routes_upload.py`. **0 in `ingestion/`** | yes |
| 10 | Lint 4, every one `BLE001` | 4, all `BLE001` | `-m ruff check . --output-format=concise` → `api/routes_valuation.py:451`, `:733`, `cli.py:1204`, `tests/test_e2e_all_googl.py:106`, all `BLE001`. **Found 4 errors** | yes |
| 11 | Census ≤ 64 | 64 | **64** in the working tree, **64** in my `head` tree. Unchanged | yes |
| 12 | Route 200 | 200 | `TestClient(app.app, raise_server_exceptions=False).get('/').status_code` → **200** | yes |
| 13 | Failure sets, by name | before `{ }`, after two named tests | `head` → **1175 passed, 2 skipped** in 112.14s, failure set **{ }**. `after` → **2 failed, 1173 passed, 2 skipped** in 114.04s, failure set **exactly** `{tests/unit/test_claude_extractor.py::test_merge_keeps_one_item_per_year_amount_direction, tests/unit/test_session_extraction.py::test_three_filings_both_routes_give_equal_statements_and_items}`. Compared by name, not by count | yes |
| 14 | The share price moves | $30.64 → $30.66 | my own pair: `head` market $106.87, derived tax rate **23.15%**, implied **$30.65**; `after` market $106.86, derived tax rate **23.11%**, implied **$30.67**. Exit 0 both. Same direction, same size (+$0.02) | yes |

**Both red tests encode the old key and neither can pass under any correct new key.**
`tests/unit/test_claude_extractor.py:590-603` builds its "duplicate" as
`_nri(2023, 10.0, "add_back", "same item, seen again in the 2024 10-K")` against a first
item worded `"seen in the 2023 10-K"` — two different texts — and its own comment names
the key it asserts: `# Key (year, amount, direction), first seen kept`.
`tests/unit/test_session_extraction.py:249` writes its repeat as
`dict(item_a, description="A, read again")`, again a different text. `tests/` was denied
to the programmer by the write guard and is out of scope by the assignment. **The tester
assignment must re-express both fixtures with the same printed description**, which is
what a re-report of one item actually looks like.

## The four questions the lead asked

**A — the other side of the trade. Measured, and the trade is favourable. No user
decision is needed yet.**

The new failure mode is real and I reproduced it: two filings reporting one item with
different wording survive as two, and nothing prints
(`C:\tmp\rev14e\hand_merge.py`, "differently-worded re-report" case → `RESULT: 2 item(s)`,
no `[MERGE]` line). But its trigger is strictly rarer than the one it replaces, and that
is measurable, not a matter of taste:

- `plan_filings` (`ingestion/claude_extractor.py:2789-2798`) gives the **oldest** filing
  `target_years=None` and **every other filing its own fiscal year alone**, and
  `_build_nri_prompt` (`:2338-2340`) puts that year list in the Pass 2 instruction. So on
  the planned path the years each filing is asked about are **disjoint**, and a
  cross-filing re-report can only arise if the model volunteers a year it was not asked
  for.
- In the one real multi-filing extraction we have, it did not. `extractions/WMT.json`:
  filing 0 reports 2022/2023/2024, filing 1 reports 2025 only, filing 2 reports 2026
  only. **Zero cross-filing year overlap, so zero opportunity for either a re-report or
  a double-count.**
- The mode this unit closed fired immediately on that same real file: 1 silent drop in
  14 items, 200 $M, on the first real multi-year run.

So the old mode's trigger is "two distinct items of the same size in one filing" —
observed once in fourteen items — and the new mode's trigger is "the model disobeys the
year scope **and** re-words the item" — observed zero times and structurally discouraged.
I am not asking the user to choose. It belongs in the backlog with this entry and the
programmer's finding 1 as its evidence, so that the first real case is recognised rather
than argued about.

**B — `page` and `source` must stay out of the key. The reason holds, and I measured it
rather than accepting it.** The full `source` strings in `extractions/WMT.json` carry a
page number, and the same disclosure moves page between filings:
`'Note 1 - Summary of Significant Accounting Policies, Investments, page 52'` in the
FY2024 10-K and `'Note 1 - Summary of Significant Accounting Policies, Investments,
page 51'` in the FY2025 10-K. A key holding `page` or `source` could therefore never
match the same note across two filings, criterion 3 would fail for every real pair, and
the silent drop would become a silent double-count. The programmer's reason is correct
and the file proves it.

**C — the correction to the assignment's fact 3. Verified by my own execution; the
programmer is right and the assignment was the defect.** Through
`pipeline.adjust_financials` on the real file, fiscal 2022:

| Fiscal 2022 | `head` | `after` |
|---|---|---|
| items applied | 13 | 14 |
| `other_non_operating` | -400.0 | **-200.0** |
| `ebit` | 25942.0 | 25942.0 — **unchanged** |
| `operating_margin` | 0.045293441861602016 | 0.045293441861602016 — **unchanged** |
| `ebt` | 23706.0 | **23906.0** (exactly 200 apart) |
| `tax_expense` | 4756.0 | 4756.0 — unchanged |
| `effective_tax_rate` | 0.20062431451953092 | **0.19894587132937339** |

All four fiscal 2022 Pass 2 items carry `line_item='other_non_operating'`, which the
normalizer applies below EBIT, so the operating margin cannot move and the
operating-margin series is identical in both trees. **The assignment's fact 3 names the
wrong mechanism.** Backlog item 112's own write-up
(`docs/9-reference/refactor-backlog.md:147`) says only "200 $M of add-back is lost from
fiscal 2022" and makes **no** operating-margin claim — the sentence the programmer's
finding 3 attributes to the backlog is in the assignment, not the backlog. See **F3**.
What needs correcting is the assignment, and item 112 would be improved by naming the
effective tax rate as the figure that moves.

**D — a drop that prints only to a console. Stopping there was right.** The assignment
is explicit in two places: item 3 says "Print it where the other merge and check messages
already print, so both routes show it", and **Files in scope** says "If you believe the
message also belongs on a web page, that is a finding: write it and stop." The programmer
wrote it (its finding 2) and stopped. The gap is exactly backlog item 62
(`docs/9-reference/refactor-backlog.md:97`), which already records that no failed reading
check reaches the web page for either route, and this message belongs in the same fix.
Carrying it onto the page would have required editing `ingestion/session_extraction.py`
to change the merge's return type — explicitly out of scope. Not a finding against this
unit.

## Findings

### F1 — the identical row written twice in one filing is now kept twice, silently · `minor`

**Evidence:** my own `C:\tmp\rev14e\hand_merge.py`, case 6b — one filing's answer holding
the *same* `NonRecurringItem` (same year, amount, direction, description **and page 66**)
twice → `RESULT: 2 item(s)`, and no `[MERGE]` line printed. At `HEAD` the second copy was
dropped.
**Rule or document:** no rule in `docs/2-rules/rules.md` is broken — nothing is missing,
nothing is guessed, nothing is unlabelled — so this is not a `major`. It is the direct
consequence of the assignment's item 1, "Never dedupe two items that came from the same
filing's answer", which the programmer obeyed exactly, and its criterion 6 scored this
behaviour a pass. I am raising it for the orchestrator, not against the programmer.
**What would fix it:** within one filing, `page` *does* separate the two real items
(Asda 66, Seiyu 67) and the reason for excluding it — that pages move between PDFs —
does not apply inside a single PDF. A within-filing key of
`(year, amount, direction, description, page)` would keep Asda and Seiyu and collapse a
literally identical row, with no judgement and no tolerance. That is a change to the
assignment, so it is the orchestrator's to make, not the programmer's.

### F2 — a differently-worded re-report across filings is a silent double-count · `note`

**Evidence:** `C:\tmp\rev14e\hand_merge.py`, "differently-worded re-report" case → two
filings, one item, texts `"Restructuring charges"` and `"Charges for the restructuring of
certain businesses"` → `RESULT: 2 item(s)`, nothing printed.
**Rule or document:** none. Assignment item 4 forbids a similarity rule, a fuzzy match or
a tolerance, so the programmer could not have closed this and was right to write it and
stop. Its likelihood is measured under **A** above and is strictly lower than the mode
this unit closed.
**What would fix it:** a backlog item recording the mode with the programmer's finding 1
and the measurement under **A** as its evidence, so the first real case is recognised. A
tolerance is not the fix.

### F3 — the programmer's finding 3 attributes to the backlog a sentence that is only in the assignment · `note`

**Evidence:** `docs/9-reference/refactor-backlog.md:147` (item 112) contains no
operating-margin claim; the sentence "the fiscal 2022 operating margin is understated by
that amount" is at `.agent/assignments/P14e-nri-dedupe.md:49-50`.
**Rule or document:** none — an accuracy point in the entry, not in the code. The
*measurement* in the programmer's finding 3 is correct and I reproduced it under **C**.
**What would fix it:** the assignment is what needs correcting; item 112 is merely silent
on the mechanism and would be improved by naming the effective tax rate.

### F4 — `nri_identity` is public with no caller outside the file · `note`

**Evidence:** `grep -rn "nri_identity" --include=*.py .` → hits only in
`ingestion/claude_extractor.py`.
**Rule or document:** none. The programmer raised this itself (its finding 4) and gave a
reason: it is the statement of what "the same item" means and a test should be able to
name it, against backlog item 53's complaint about importing `_NRI_SCHEMA` privately.
**What would fix it:** nothing, unless the orchestrator prefers it private. I think public
is right and the tester will want it.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 62 — no failed reading check reaches the web page, either route | `refactor-backlog.md:97` | no. The new `[MERGE]` message inherits the same gap; the assignment told the programmer to stop at a finding, and it did |
| 84 — check B1 confirms a unit statement on the row's page, not its table | `refactor-backlog.md:119`, `ingestion/claude_extractor.py` | no |
| 112 — this unit's defect | `refactor-backlog.md:147` | yes, and closed. Its write-up needs the correction under **C** |
| 113 — Pass 2 prompt console encoding | out of scope by the assignment | no. I used `PYTHONIOENCODING=utf-8` throughout |
| 73, 79, 80, 114 — same file, each recorded | out of scope by the assignment | no |

The two lint `BLE001` sites in `api/` and the one in `cli.py`, and the five mypy errors,
are all outside this file and unchanged at `HEAD`.

## Verdict

`approved`

The diff does one thing and does it for a reason. The dedupe now runs across filings only,
the key gained the one field that separates the Asda loss from the Seiyu loss, and every
drop prints both items with their filings and pages from the single function both routes
call. I reproduced all fourteen done-criteria myself, including the failure sets by name
and the share price on a live market call, and I agree with every one. No guard check
hits, the census is unmoved at 64, and no rule in `docs/2-rules/rules.md` is broken — F1
is a real behaviour change with no rule behind it and it follows the assignment's own
instruction, F2 to F4 are notes. Two things are the orchestrator's, not the programmer's:
the assignment's fact 3 is wrong about the mechanism and the measurement under **C**
settles it, and the tester assignment must re-express
`test_merge_keeps_one_item_per_year_amount_direction` and
`test_three_filings_both_routes_give_equal_statements_and_items`, both of which build
their "repeat" with a *different* description and so assert the defect this unit closed.
