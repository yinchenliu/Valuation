---
agent: programmer
assignment: P14e-nri-dedupe
round: 2
status: complete
files_touched: [ingestion/claude_extractor.py]
verdict: n/a
---

# P14e-nri-dedupe round 2 — the identical row twice in one filing is one item, and that drop is reported too

Round 1 entry: `.agent/journal/2026-10-06T1229-programmer-p14e-nri-dedupe.md`
Review answered: `.agent/journal/2026-10-06T1412-code_reviewer-p14e-nri-dedupe.md`
(verdict `approved`, finding **F1**), through the assignment's
`## Round 2 amendment (overall lead), 2026-10-06`.

## What I did

Round 1 made the dedupe run across filings only, so a filing whose Pass 2 answer listed
the identical row twice — same year, amount, direction, description **and page** — produced
two items, silently. That is a silent double-count standing where `HEAD`'s silent drop
stood. The amendment's fix carries no judgement, and it is the one change in this round:
the within-filing comparison now has **its own key**, `nri_identity_within_filing`
= `(year, amount, direction, description, page)`, and the across-filing key `nri_identity`
is untouched at `(year, amount, direction, description)`.

`page` belongs in exactly one of them, and each half of that claim is measured below by
mutation, not asserted: **inside one PDF** the page is stable and it is what separates Asda
on page 66 from Seiyu on page 67, so removing it from the within-filing key drops a real
item (criterion 17 goes 2 → 1); **between two PDFs** the same disclosure moves page — `Note
1 … Investments, page 52` in the FY2024 10-K, `page 51` in the FY2025 — so adding it to the
across-filing key turns the merge's whole purpose off (criterion 19 goes 1 → 2).

A within-filing drop prints through the same `_print_repeated_item`, with the same two
`kept`/`dropped` rows and the same fields, and only its one headline line differs, because
the two comparisons drop for different reasons and a reader is owed the right one. Round
1's cross-filing headline is unchanged, character for character, in `REPEAT_ACROSS_FILINGS`.
**Neither direction is silent now.** Three docstrings say which key applies where and why —
`nri_identity`, `nri_identity_within_filing` and `merge_filing_extractions`.

One thing I tightened beyond the literal amendment, and the reason: my first version
registered every row of a filing in the within-filing dict, including rows the
across-filing comparison had just dropped. In the compound case — an earlier filing already
reported the item **and** this filing writes its own row twice — the second message then
said `kept:` of a row that had itself been dropped. The count was right and both drops were
reported, but the word was false. Registering only rows actually appended fixes it: every
`kept:` line now names an item that really is in the merged list. Measured both ways in
`hand_merge2_after.txt`, case `BOTH AT ONCE`.

No prompt and no schema changed. `extractions/WMT.json` was read and never written; its
sha256 is `c436e427…3675` at the start of this run and at the end. Every mutant, variant
session file and probe lives in `C:\tmp\p14e2\`, outside the repository.

## Done-criteria

Every command ran with `ANTHROPIC_API_KEY= GEMINI_API_KEY= PYTHONIOENCODING=utf-8` and
`.venv/Scripts/python.exe`, on the Windows machine. Scratch trees:
`C:\tmp\p14e2\head` (`git archive HEAD`) and `C:\tmp\p14e2\after` (the same archive with
only `ingestion/claude_extractor.py` replaced by the working-tree file), each given a copy
of `extractions/` and `10K_filings/`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 15 | The identical row twice in one filing is one item, and the drop is reported | **pass**, twice over | (a) hand-built, `C:/tmp/p14e2/hand_merge2.py` case `CRITERION 15` → `RESULT: 1 item(s)`, `DROPS REPORTED: 1`, and the message names **both copies with page 66** (quoted below). (b) **real route B**: `C:/tmp/p14e2/WMT_dup_row.json` is `extractions/WMT.json` with filing 0's Asda row appended a second time, byte-identical; `-m ingestion.session_extraction check` → `EXIT=0`, 15 written, `non-recurring items: 14`, with the `[MERGE]` line at `check_WMT_dup_row.txt:57-59`. (c) **route A**: `probe_route_a_merge2.py::test_route_a_identical_row_twice_in_one_filing` → `COUNT: 5` and the same message |
| 16 | Asda and Seiyu still survive | **pass** | `hand_merge2.py` case `CRITERION 16` → `RESULT: 2 item(s)`, `DROPS REPORTED: 0`, both rows printed with pages 66 and 67 |
| 17 | Two rows alike in every field but the page, in one filing | **pass** | `hand_merge2.py` case `CRITERION 17` (the reviewer's boundary, from the other side: same description, pages 66 and 67) → `RESULT: 2 item(s)`, `DROPS REPORTED: 0`. The mutation below shows this is the criterion `page` is load-bearing for |
| 18 | Walmart does not move | **pass** | `C:/tmp/p14e/show_items.py extractions/WMT.json` in `after` → `TOTAL WRITTEN 14   MERGED 14`, `ASDA in list: True`, `SEIYU in list: True`. The same command in `head` → `MERGED 13`, `SEIYU in list: False`. Through `pipeline.adjust_financials`, every fiscal 2022 figure is **identical to round 1's `after` column**: items applied 14, `other_non_operating` -200.0, `ebit` 25942.0, `operating_margin` 0.045293441861602016, `effective_tax_rate` 0.19894587132937339 |
| 19 | The cross-filing behaviour does not move | **pass**, criteria 3, 4, 5 and 6 re-run three ways | **3**: `hand_merge2.py` case `CRITERIA 19 / 3, 4, 5` → `RESULT: 1 item(s)`; real route B on `C:/tmp/p14e2/WMT_rereport.json` (the FY2025 10-K also reporting the fiscal 2024 `$3.8 billion` item, which page 51 of that PDF prints) → `EXIT=0`, 15 written, `non-recurring items: 14`; route A probe → `'Restructuring A'` flagged by two filings appears once. **4**: the message is round 1's, word for word (quoted below). **5**: the merge returned, `check` exits 0 and goes on to print its summary. **6**: case `CRITERION 19 / 6` → `RESULT: 2 item(s)`, `DROPS REPORTED: 0` |
| 20 | Gates, after the last edit | **pass** | types `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → **Found 5 errors in 2 files (checked 21 source files)**: 4 `union-attr` in `analysis/projector.py`, 1 `operator` in `api/routes_upload.py`, **0 in `ingestion/`**. Lint `-m ruff check . --output-format=concise` → **Found 4 errors**, every one `BLE001` (`api/routes_valuation.py:451`, `:733`, `cli.py:1204`, `tests/test_e2e_all_googl.py:106`). Census, the grep at `docs/2-rules/rules.md:102` over `models analysis api ingestion` → **64**. Route `TestClient(app.app, raise_server_exceptions=False).get('/').status_code` → **200**. All four run in the repository root **after** the last edit |
| 21 | The failing test set | **pass** | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly`. `head` → `1175 passed, 2 skipped` in 112.57s, failure set **{ }**. `after` → `2 failed, 1173 passed, 2 skipped` in 115.07s, failure set **exactly** `{tests/unit/test_claude_extractor.py::test_merge_keeps_one_item_per_year_amount_direction, tests/unit/test_session_extraction.py::test_three_filings_both_routes_give_equal_statements_and_items}` — **the same two as round 1, by name, and no others** |

**The two messages, quoted.** Criterion 15, from the real route B run
(`C:/tmp/p14e2/check_WMT_dup_row.txt:57-59`):

```
  [MERGE] Non-recurring item listed twice by one filing - same year, amount, direction, description and page, so one printed line written twice - counted once, not twice:
    kept   : 2022  200.0 $M  add_back  'Incremental pre-tax loss on the divestiture of Asda (U.K. retail operations), recorded in other gains and losses'  [Walmart Inc._10-K_2024-01-31_English.pdf, page 66]
    dropped: 2022  200.0 $M  add_back  'Incremental pre-tax loss on the divestiture of Asda (U.K. retail operations), recorded in other gains and losses'  [Walmart Inc._10-K_2024-01-31_English.pdf, page 66]
```

Criterion 19, from `C:/tmp/p14e2/check_WMT_rereport.txt:57-59` — **identical to round 1's**:

```
  [MERGE] Non-recurring item already reported by an earlier filing - counted once, not twice:
    kept   : 2024  3,800.0 $M  add_back  'Net losses from fair value changes of equity and other investments, recognized in other gains and losses'  [Walmart Inc._10-K_2024-01-31_English.pdf, page 52]
    dropped: 2024  3,800.0 $M  add_back  'Net losses from fair value changes of equity and other investments, recognized in other gains and losses'  [Walmart Inc._10-K_2025-01-31_English.pdf, page 51]
```

## The mutation proof — `page` is load-bearing in exactly one key

A docstring claiming "`page` belongs here and not there" is an opinion until the code is
changed and something breaks. Two mutant trees, each one line different from `after`, each
run against the same eight hand-built cases (`C:/tmp/p14e2/hand_merge2.py`):

| Tree | The one line changed | 15 | 16 | **17** | **19 / 3,4,5** | 19 / 6 | three filings |
|---|---|---|---|---|---|---|---|
| `after` (this unit) | — | 1 item, 1 drop | 2, 0 | **2, 0** | **1, 1 drop** | 2, 0 | 1 item, 2 drops |
| `mut_nopage` | `page` **removed** from `nri_identity_within_filing` | 1, 1 | 2, 0 | **1 item, 1 drop — FAILS** | 1, 1 | 2, 0 | 1, 2 |
| `mut_pagecross` | `page` **added** to `nri_identity` | 1, 1 | 2, 0 | 2, 0 | **2 items, 0 drops — FAILS** | 2, 0 | **3 items, 0 drops** |

So the within-filing key needs `page` or a real item is dropped, and the across-filing key
must not have it or the merge stops merging and a re-reported item is counted once per
filing. **Neither mutant is caught by the real Walmart file**: both still give
`MERGED 14` with Asda and Seiyu present, because `extractions/WMT.json` has no cross-filing
year overlap and no repeated row. The boundary is only visible in the hand-built cases,
which is the reason they exist.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| A second named function, `nri_identity_within_filing`, rather than an inline tuple | The amendment, item 3: a reader meeting two keys must not have to infer the reason. A key that is the statement of what "the same row" means deserves a name and a docstring, as `nri_identity` already has | An inline `(item.year, …, item.page)` in the loop would put the two keys' difference in a line of code with no room for the reason. Two functions, two docstrings, one cross-reference each |
| Public, parallel to `nri_identity` | The reviewer's F4 — public is right and the tester will want to name it. Backlog item 53 is the complaint about reaching for a private name from outside | A private `_nri_identity_within_filing` would make the tester import a private symbol to assert the boundary cases 15, 16 and 17 |
| `page` in the within-filing key, out of the across-filing key | Measured both ways by mutation, above. Within one PDF the page is stable and it is the only field separating two same-size items printed on different pages; between PDFs it moves (`page 52` → `page 51` for the same Walmart note, confirmed by the reviewer from the file) | A single key cannot do both jobs: with `page` it never matches across filings, without it a literally repeated row is invisible. That is precisely why there are two |
| `source` stays out of both keys | It carries a page number (`"Note 12 … page 66"`), so across filings it moves for the same reason as `page`; within one filing it adds nothing `page` does not already give | Including it within the filing would make the key sensitive to a note title the model paraphrased, which is a judgement, not a fact |
| The within-filing comparison runs **first**, against this filing's **kept** rows only | Each dropped row must be reported exactly once, and every `kept:` line must name an item that is really in the merged list | Registering every row, kept or not, made the compound case print `kept:` of a row that had just been dropped — true count, false word. Measured in `hand_merge2_after.txt`, `BOTH AT ONCE`: now both drops are reported against the FY2024 item that was actually kept |
| One headline per comparison, as two module constants, passed as a typed `headline: str` | The amendment, item 2: report a within-filing drop as you report a cross-filing one. The two rows under the headline are identical; only the reason differs, and "already reported by an **earlier filing**" is false when both copies are in one filing | Reusing the cross-filing sentence verbatim would have printed a false clause. A second print function would have duplicated the `kept`/`dropped` formatting, which is where the `$M` unit comment lives. The constants are strings, not behaviour — no dispatch table |
| Round 1's cross-filing headline kept character for character | The amendment, item 4: round 1's message text stands | — |

**A code change made to reach a target number, rather than on a reason, is forbidden.**
Nothing here was changed to reach a number, and **this round moves no figure at all**: the
real Walmart run gives the same 14 items and the same fiscal 2022 effective tax rate
`0.19894587132937339` as round 1. The round-1 price move ($30.64 → $30.66) stands and is
not re-measured here, because no input to it changed; criterion 14 is not in this round's
list and no market call was made.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `item.year`, `item.amount`, `item.direction`, `item.description` (both identity functions) | **Cannot be missing.** All four are required fields of `NonRecurringItem` with no default, and the Pass 2 parser stops on an absent key before the merge runs | `models/financial_statements.py:67-72` |
| `item.page` — **new in this round, now in a key and not only in a message** | **Cannot be missing.** `page: int`, a required field with no default | `models/financial_statements.py:77`. This is the field the within-filing key added; it is as mandatory as the other four |
| `kept_rows_this_filing.get(row_key)` → `None` | **A presence test, not a default.** `None` means "this filing has not kept this row", and that branch goes on to the across-filing comparison; no value is substituted for a missing one. Both branches do real work, neither is empty | `ingestion/claude_extractor.py:3014-3018`. Same shape as round 1's `kept_by_key.get(key)`, which the reviewer checked at `:2930` |
| `kept_by_key.get(key)` → `None` | unchanged from round 1 | `ingestion/claude_extractor.py:3021-3032` |
| `headline` (the new parameter) | Not a data value: both call sites pass a module constant, literal in git. A missing one is a `TypeError` at import-time call sites, not a silent default — it has **no default** | `ingestion/claude_extractor.py:2904-2910`, `:3016`, `:3031` |

No "defaults to" row. This round adds no fallback and removes none. The census grep is
**64**, the same figure round 1 and the reviewer both measured.

## Measurements

**The repository files, before and after.**

| File | At the start of this run | Now |
|---|---|---|
| `ingestion/claude_extractor.py` | `578bd18ab3ac8ae71460f7ede740fda9747a134f87c88b281376eb7343d4d453` (round 1, the hash the lead and the reviewer both measured) | `b459e4eebc8f6cfc4172a24117e592f002f98ee5fe27187d2edeeb4fb69f7e35` (the deliberate change) |
| `extractions/WMT.json` | `c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675` | **unchanged**, `c436e427…3675` — read, never written |

`git status --short` now holds `M ingestion/claude_extractor.py` and this entry, nothing
else. `git diff --name-only` → `ingestion/claude_extractor.py` alone; 191 insertions, 7
deletions against `HEAD`, which is rounds 1 and 2 together. Round 2 alone is the diff of
`C:/tmp/p14e/after/ingestion/claude_extractor.py` (hash `578bd18a…`, round 1's file) against
the working tree: six hunks, all between `nri_identity` and the end of
`merge_filing_extractions`.

**During this run the lead committed `5291710`** ("round 1 entries, approved, round 2
amendment"). `git show --stat` confirms it touches **no `.py` file**, so my `head` tree,
archived from `b6dbdd0` before it landed, is byte-identical in source to current `HEAD`.

**No prompt and no schema.**
`git diff -- ingestion/claude_extractor.py | grep -icE "^[+-].*(_PASS1_|_PASS2_|_SCHEMA|prompt|SYSTEM|system_prompt|json_schema)"` → **0**.

**The suite, as failure SETS** (`-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly`):

| Tree | Result | Failure set |
|---|---|---|
| `head` (`HEAD`) | `1175 passed, 2 skipped` in 112.57s | **{ }** |
| `after` (round 2) | `1173 passed, 2 skipped, 2 failed` in 115.07s | **{ `tests/unit/test_claude_extractor.py::test_merge_keeps_one_item_per_year_amount_direction`, `tests/unit/test_session_extraction.py::test_three_filings_both_routes_give_equal_statements_and_items` }** |

The same two as round 1, and for the same reason: both build their "repeat" with a
**different** description (`"seen in the 2023 10-K"` against `"same item, seen again in the
2024 10-K"`; `dict(item_a, description="A, read again")`), so neither can pass under any
correct new key. **Round 2 makes neither test worse and adds no third.** `tests/` is out of
my scope and I wrote nothing there; the tester re-expresses both, and criteria 15, 16 and
17 give it three boundary cases that need no filing.

**Scratch artefacts**, all outside the repository, if the reviewer wants to re-run them:

| Path | What it is |
|---|---|
| `C:/tmp/p14e2/hand_merge2.py` | the eight hand-built cases; each captures the merge's own stdout, so `DROPS REPORTED: 0` is a counted absence of `[MERGE]` lines, not one I eyeballed |
| `C:/tmp/p14e2/hand_merge2_after.txt` | its output in `after` |
| `C:/tmp/p14e2/make_variants.py` | builds the two session-file variants from the repository's `WMT.json`, read-only |
| `C:/tmp/p14e2/WMT_dup_row.json`, `check_WMT_dup_row.txt` | criterion 15 through real route B |
| `C:/tmp/p14e2/WMT_rereport.json`, `check_WMT_rereport.txt` | criterion 19 through real route B |
| `C:/tmp/p14e2/probe_route_a_merge2.py` | both drops through route A, on `tests/unit/test_session_extraction.py`'s stub; run from a scratch tree, never from `tests/` |
| `C:/tmp/p14e2/mut_nopage`, `C:/tmp/p14e2/mut_pagecross` | the two one-line mutants |
| `C:/tmp/p14e2/pytest_head.txt`, `pytest_after.txt` | the two suite runs |

## What I did not do

- **I did not touch `tests/`.** The two red tests are unchanged in cause and count.
- **I did not reopen F2** (the differently-worded re-report across filings, still a silent
  double-count). The lead recorded it as backlog item 119 and ruled it out of this round; a
  tolerance or a fuzzy match would be rule 1's judgement written in Python.
- **I did not carry either message to a web page.** Backlog item 62, out of scope, and the
  reviewer agreed round 1 was right to stop.
- I did not re-run the live market call. This round moves no figure in the Walmart run, and
  I show that by the identical fiscal 2022 derived values rather than by a price.
- I did not change `ingestion/session_extraction.py`. Both messages are printed, not
  returned, so neither joins `SessionExtraction.validation_errors` and neither appears in
  `check`'s "problem(s)" block — by design, since a repeat is not a problem.

## Findings for the orchestrator

1. **The compound case is now reported twice, and that is deliberate — but a reader has to
   add up.** When an earlier filing reported an item **and** the later filing writes its own
   row twice, the merge prints two `[MERGE]` blocks, both naming the same kept item
   (`hand_merge2_after.txt`, `BOTH AT ONCE`: `DROPS REPORTED: 2`, `RESULT: 1 item(s)`).
   That is correct — two rows were dropped, each is named — but nothing prints a total. This
   is round 1's finding 5 again, from a new angle: a summary line beside
   `Years: … | non-recurring items: 14` saying how many items the merge dropped would make
   the count checkable at a glance instead of by reading 50 lines. Owned by
   `ingestion/session_extraction.py`, out of this unit's scope.
2. **Neither mutant of the two keys is caught by the only real multi-filing file we have.**
   `mut_nopage` and `mut_pagecross` each break one criterion, and **both still give
   `MERGED 14`** on `extractions/WMT.json` with Asda and Seiyu present. A tester that
   measures this unit only against the Walmart file would pass both broken versions. The
   tester assignment needs the hand-built boundary cases 15, 16, 17 and 19, not just the
   real file. `C:/tmp/p14e2/hand_merge2.py` is the shape they take.
3. **`REPEAT_ACROSS_FILINGS` and `REPEAT_WITHIN_ONE_FILING` are public module constants.**
   I made them public for the same reason `nri_identity` is: a test asserting "the drop was
   reported" should match the sentence by name rather than copy a literal that then drifts.
   If the orchestrator prefers them private, it is a two-line change.
