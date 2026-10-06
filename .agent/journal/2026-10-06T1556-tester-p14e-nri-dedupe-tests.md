---
agent: tester
assignment: P14e-nri-dedupe-tests
round: 1
status: complete
files_touched: [tests/unit/test_p14e_nri_dedupe.py, tests/unit/test_claude_extractor.py, tests/unit/test_session_extraction.py]
verdict: pass
---

# P14e-nri-dedupe-tests — both keys held by hand-built cases, and all three mutants die

## What I did

`P14e-nri-dedupe` gives `merge_filing_extractions` two keys — `nri_identity`
`(year, amount, direction, description)` **across** filings, and
`nri_identity_within_filing`, the same four plus `page`, **inside** one filing's own
answer. The programmer and the round 2 code reviewer each measured that
`extractions/WMT.json` is green against three one-line mutants of that code, so the
real file cannot see either boundary. **I reproduced that measurement myself** (table
under criterion 9) and built every boundary case by hand instead.

Three files changed, all under `tests/`:

1. **`tests/unit/test_p14e_nri_dedupe.py`** — new, 31 tests, 69 assertions. The two
   keys read directly, the across-filing and within-filing merge cases, both drop
   reports asserted field by field, the compound case, the rule 3 stops for the
   fields the keys read, and the real Walmart file **labelled in the file as a
   regression guard and not as evidence about either key**.
2. **`tests/unit/test_claude_extractor.py:591`** — the first red test repaired and
   **renamed** (it named the three-field key this unit replaced):
   `test_merge_keeps_one_item_per_year_amount_direction` →
   `test_merge_keeps_one_item_per_year_amount_direction_and_description`. Its
   "duplicate" built with a *different* description is now a re-report built with the
   **same printed line on a different page**, which is what a re-report is.
3. **`tests/unit/test_session_extraction.py`** — the second red test repaired: the
   `three_filings` fixture's repeat was `dict(item_a, description="A, read again")`
   and is now `dict(item_a, page=51)`, same text, different page. One new two-route
   test and one new fixture for the within-filing key
   (`test_a_filing_that_lists_one_row_twice_gives_one_item_on_both_routes`, `:425`).

**I edited no implementation code.** `ingestion/claude_extractor.py` is
`b459e4ee…b69f7e35`, 171,384 bytes, at the start of my run and at the end;
`extractions/WMT.json` is `c436e427…c008a3675`, 36,626 bytes, at both ends. Every
mutant lives in `C:\tmp\p14et\`, outside the repository, built by
`C:\tmp\p14et\make_mutants.py` from a `git archive HEAD` tree with only the
working-tree file copied in. **No file in the repository was ever mutated.**

## Done-criteria

Every command below ran with `ANTHROPIC_API_KEY= GEMINI_API_KEY=
PYTHONIOENCODING=utf-8` and `.venv/Scripts/python.exe`, on the Windows machine.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | My own baseline, before I wrote anything | **pass** | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly` → `2 failed, 1173 passed, 2 skipped` in 124.26s. Failing set, **by name**: `{tests/unit/test_claude_extractor.py::test_merge_keeps_one_item_per_year_amount_direction, tests/unit/test_session_extraction.py::test_three_filings_both_routes_give_equal_statements_and_items}` — exactly the two the assignment names, and no others. `C:/tmp/p14et/baseline_gate.txt` |
| 2 | The failing set is empty when I finish | **pass** | the same command → `1207 passed, 2 skipped` in 120.70s, exit 0, failing set **{ }**. `C:/tmp/p14et/final_gate.txt`. 1207 − 1175 collected = **32 tests added** (31 in the new file + 1 in `test_session_extraction.py`) |
| 3 | The full suite shows only the two deliberate failures | **pass** | `-m pytest -q -p no:randomly` → `2 failed, 1207 passed, 2 skipped`, failing set **exactly** `{tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input, tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops}`. **Both are still red, so neither moves out of the `*_rule3_red.py` pattern in this unit.** `C:/tmp/p14et/final_full.txt` |
| 4 | The two red tests are repaired, not deleted | **pass** | both run by name → `2 passed in 2.56s`. Neither is deleted, no assertion was weakened: the session test still asserts `route_b.financials == fin_a`, `route_b.non_recurring == items_a`, `len(calls) == 6` and the full description list; the extractor test gained assertions rather than losing any (3 items expected → 4, plus a page check) |
| 5 | The across-filing key is held | **pass** | `test_nri_identity_is_the_four_fields_it_was_given`, `test_nri_identity_ignores_the_page_because_a_page_moves_between_filings`, `test_nri_identity_separates_items_that_differ_in_any_of_its_four_fields` (4 params), `test_one_item_re_reported_by_a_later_filing_is_one_item`, `test_three_filings_re_reporting_one_item_give_one_item_and_two_drops`, `test_two_filings_whose_rows_differ_in_a_key_field_give_two_items` (3 params), `test_a_differently_worded_re_report_is_counted_twice_backlog_item_119` |
| 6 | The within-filing key is held | **pass** | `test_nri_identity_within_filing_is_the_four_fields_plus_the_page`, `test_nri_identity_within_filing_separates_two_rows_by_the_page_alone`, `test_the_identical_row_written_twice_in_one_filing_is_one_item`, `test_asda_and_seiyu_are_two_items_in_one_filing`, `test_two_rows_alike_in_every_field_but_the_page_are_two_items`, `test_three_identical_rows_in_one_filing_give_one_item_and_two_drops` |
| 7 | **`page` is load-bearing in the within-filing key** | **pass** | mutant `mut_nopage` (one line: `item.page` → `0` in `nri_identity_within_filing`'s return). **3 of my tests go red**, named below. The 2-item case `test_two_rows_alike_in_every_field_but_the_page_are_two_items` becomes 1 item, exactly as the programmer measured |
| 8 | **`page` is excluded from the across-filing key, and that matters** | **pass** | mutant `mut_pagecross` (one line: `item.page` appended to `nri_identity`'s return). **13 of my tests go red**, including **both repaired tests**. The 1-item case `test_one_item_re_reported_by_a_later_filing_is_one_item` becomes 2 items |
| 9 | The real file cannot see either boundary | **pass**, re-measured by me | `C:/tmp/p14et/show_items.py` in five trees: `head` → `MERGED 13, ASDA True, SEIYU False`; the unit, `mut_nopage`, `mut_pagecross` and `mut_notighten` → **all four `MERGED 14, ASDA True, SEIYU True`**. Table below. **A tester measuring this unit against `extractions/WMT.json` alone would pass three broken versions of it.** My `test_the_real_walmart_file_…` passed in all three mutant trees, which is the same fact from the test side |
| 10 | Both drop messages are held | **pass** | `test_a_cross_filing_drop_names_the_year_amount_direction_text_filing_and_page`, `test_a_within_filing_drop_names_both_copies_with_the_same_filing_and_page`, `test_the_two_headlines_differ_so_a_reader_is_told_which_comparison_dropped`. Each of the six fields is looked for on its own via `fields_missing_from`, never as a whole sentence, so a reword is not a failure |
| 11 | A drop does not stop the run | **pass** | `test_a_drop_does_not_stop_the_run_and_the_statements_still_merge`: the merge returns, the item list is right, and the **statements** are the control that it ran past the drop — `{2023: 2023.0, 2024: 2024.0}` and both balance sheets. Through route B: `test_a_filing_that_lists_one_row_twice_…` asserts `route_b.validation_errors == []`, so a repeat is reported without becoming a problem |
| 12 | The compound case | **pass** | `test_every_kept_line_names_an_item_that_is_really_in_the_merged_list`: earlier filing reported it **and** the later filing writes its row twice on the same page. 3 in, 1 out, 2 drops, both of the across-filing kind, and every `kept:` row matches an item that really is in the merged list — plus the negative half, that no `kept:` row names `F2024.pdf` or `page 51`. **This is the one test that kills `mut_notighten`** |
| 13 | Both routes | **pass** | real route B loader: `test_three_filings_both_routes_give_equal_statements_and_items`, `test_a_filing_that_lists_one_row_twice_gives_one_item_on_both_routes`, `test_the_real_walmart_file_…` (all `load_session_extraction`). `extract_multi_year` stubbed: the first two, through `run_route_a`. **0 network attempts**: `conftest.isolate_environment_keys` empties both keys, the module's autouse `_no_api` makes `_call_llm` raise, the route A stub raises on any prompt it was not given, and the new test carries `@pytest.mark.usefixtures("_no_socket")`, which refuses every non-loopback address |
| 14 | Walmart still merges 14 | **pass** | `test_the_real_walmart_file_keeps_every_item_it_lists_including_asda_and_seiyu` → 14 written, 14 merged, Asda `(66, 2022, 200.0, add_back)` and Seiyu `(67, 2022, 200.0, add_back)` both present. **Labelled in the file as a regression guard, not evidence about either key**, and section 8's header says so in capitals |
| 15 | Lint | **pass** | `-m ruff check . --output-format=concise` **after my last edit** → `Found 4 errors`, every one `BLE001`: `api/routes_valuation.py:451`, `:733`, `cli.py:1204`, `tests/test_e2e_all_googl.py:106`. None added, none removed |
| 16 | Nothing outside `tests/` changed | **pass** | `git diff --stat -- . ':(exclude)tests'` → `ingestion/claude_extractor.py | 198 ++…`, **1 file changed, 191 insertions, 7 deletions** — the same line counts as when I started. `git status --short` → `M ingestion/claude_extractor.py`, `M tests/unit/test_claude_extractor.py`, `M tests/unit/test_session_extraction.py`, `?? tests/unit/test_p14e_nri_dedupe.py`, `?? ` this entry |
| 17 | Accuracy and coverage, with their units | **pass** | see "Two counts" below |

Types, not asked for but run after the last edit: `-m mypy models analysis ingestion
api config.py app.py --ignore-missing-imports` → **5 errors in 2 files (checked 20
source files)**, 4 `union-attr` in `analysis/projector.py`, 1 `operator` in
`api/routes_upload.py`, **0 in `ingestion/`** and 0 anywhere my tests touch.

## The mutation proof — my own trees, my own mutants

Three mutants, each exactly one line different from the working-tree file, each built
by `C:\tmp\p14et\make_mutants.py` into a copy of `C:\tmp\p14et\base` (`git archive
HEAD` + the working-tree `ingestion/claude_extractor.py` + the working-tree `tests/` +
read-only copies of `extractions/WMT.json` and `10K_filings/WMT/`). The script asserts
its pattern matches **exactly once** before writing.

| Tree | The one line changed | my tests, run as a set |
|---|---|---|
| `base` (the unit) | — | **221 passed, 0 failed** |
| `mut_nopage` | `page` dropped from `nri_identity_within_filing`'s return | **3 failed, 218 passed** |
| `mut_pagecross` | `page` appended to `nri_identity`'s return | **13 failed, 208 passed** |
| `mut_notighten` | a row registers in `kept_rows_this_filing` whether or not it was kept | **1 failed, 220 passed** |

The set run is `tests/unit/test_p14e_nri_dedupe.py tests/unit/test_claude_extractor.py
tests/unit/test_session_extraction.py`.

**`mut_nopage` — criterion 7.** Red:

- `test_nri_identity_within_filing_is_the_four_fields_plus_the_page`
- `test_nri_identity_within_filing_separates_two_rows_by_the_page_alone`
- `test_two_rows_alike_in_every_field_but_the_page_are_two_items`

**`mut_pagecross` — criterion 8.** Red, including both repaired tests:

- `test_nri_identity_is_the_four_fields_it_was_given`
- `test_nri_identity_ignores_the_page_because_a_page_moves_between_filings`
- `test_nri_identity_within_filing_is_the_four_fields_plus_the_page`
- `test_nri_identity_within_filing_separates_two_rows_by_the_page_alone`
- `test_one_item_re_reported_by_a_later_filing_is_one_item`
- `test_three_filings_re_reporting_one_item_give_one_item_and_two_drops`
- `test_a_cross_filing_drop_names_the_year_amount_direction_text_filing_and_page`
- `test_the_two_headlines_differ_so_a_reader_is_told_which_comparison_dropped`
- `test_a_drop_does_not_stop_the_run_and_the_statements_still_merge`
- `test_every_kept_line_names_an_item_that_is_really_in_the_merged_list`
- `test_a_later_filing_writing_two_rows_that_differ_only_in_the_page_drops_both`
- **`tests/unit/test_claude_extractor.py::test_merge_keeps_one_item_per_year_amount_direction_and_description`**
- **`tests/unit/test_session_extraction.py::test_three_filings_both_routes_give_equal_statements_and_items`**

**`mut_notighten` — the round 2 tightening.** Red: `test_every_kept_line_names_an_item_that_is_really_in_the_merged_list`, and only that one. **It took a correction to get there, and the correction is worth recording.** My first version of the compound case gave the later filing two rows on *different* pages (51 and 49); under that shape the mutant behaves identically to the unit, and **`mut_notighten` survived my whole suite**. The tightening only bites when the later filing's two rows are the **same printed line** — same page — so that the first, already dropped across filings, becomes a false `kept:` for the second. I rewrote the case to that shape and kept the differing-page shape as a second test
(`test_a_later_filing_writing_two_rows_that_differ_only_in_the_page_drops_both`).

## Criterion 9, re-measured by me

`C:\tmp\p14et\show_items.py`, read-only, run in five trees with `PYTHONPATH` set to
the tree:

| Tree | `ingestion/claude_extractor.py` sha256 | Result |
|---|---|---|
| `head` (`deb11d8`, no unit) | `ec77b4bc…0f67cf719` | `TOTAL WRITTEN 14   MERGED 13`, `ASDA True`, **`SEIYU False`** |
| `base` (the unit) | `b459e4ee…b69f7e35` | `TOTAL WRITTEN 14   MERGED 14`, `ASDA True`, `SEIYU True` |
| `mut_nopage` | one line changed | `MERGED 14`, `ASDA True`, `SEIYU True` |
| `mut_pagecross` | one line changed | `MERGED 14`, `ASDA True`, `SEIYU True` |
| `mut_notighten` | one line changed | `MERGED 14`, `ASDA True`, `SEIYU True` |

**Confirmed independently: the real Walmart file is green against all three mutants.**
`mut_nopage` does not merge Asda into Seiyu because those two differ in *description*
as well as page, so the four-field key already separates them; the file has no
cross-filing year overlap and no repeated row, so neither of the other two mutants has
anything to bite on. Criteria 7, 8 and 12 are the only reason either key is tested.

## Expected values — testers only

**Where every expected value came from. No value below was read off a run.** The
merge is not arithmetic, so the first column of sources is the *key's definition* —
two tuples are equal exactly when every field is equal, which makes each item count a
piece of arithmetic anyone can do on paper from the inputs. That derivation is written
into each test as a comment.

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `nri_identity(item) == (2022, 200.0, "add_back", "<text>")` | the four fields passed in | **identity**: the across-filing key is `(year, amount, direction, description)` (assignment Fact 3 table; `claude_extractor.py:2818` docstring). The expected tuple **is** the input |
| `nri_identity(page 52) == nri_identity(page 51)` | equal | **identity**: `page` is not one of the four fields, so changing it cannot change the tuple |
| `nri_identity(base) != nri_identity(changed)`, 4 params | unequal | **identity**: tuples differing in one component are unequal, one parameter per field of the key |
| `nri_identity_within_filing(item) == (…, 66)` and `== (*nri_identity(item), item.page)` | the five fields passed in | **identity**: the within-filing key is the four fields plus `page` (Fact 3 table; `:2860` docstring) |
| `nri_identity_within_filing(p66) != nri_identity_within_filing(p67)` | unequal | **identity**: 66 ≠ 67 in the fifth component |
| two filings, same four fields, pages 52 and 51 → `items == [first]`, 1 drop | 2 in, 1 out | **hand arithmetic on the key**: both rows give one across-filing key; first seen kept. 2 − 1 = 1 |
| three filings, same four fields → `items == [first]`, 2 drops | 3 in, 1 out, 2 drops | **hand arithmetic**: one key, 3 − 1 = 2 rows dropped, one report each |
| filings differing in year / amount / direction → `items == [earlier, later]`, 0 drops | 2 in, 2 out | **hand arithmetic**: two distinct keys, nothing to merge |
| differently-worded re-report → 2 items, 0 drops | 2 in, 2 out | **hand arithmetic on the key**, recorded as backlog item 119's measured behaviour. The test asserts neither that it is right nor that it is wrong (rule 1) |
| identical row twice in one filing → `items == [asda, unrelated]`, 1 drop | 3 in, 2 out | **hand arithmetic on the within-filing key**: two rows share all five fields, the third is a different year |
| Asda + Seiyu in one filing → 2 items, 0 drops, `sum(amount) == 400.0` | 2 in, 2 out, 400 $M | **filing page**: `10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf`, **PDF page 66** — "the Company recorded an incremental pre-tax loss of **$0.2 billion** in other gains and losses" (Asda, U.K., divested February 2021); **PDF page 67** — the same sentence for Seiyu (Japan, divested March 2021), and "the first quarter of **fiscal 2022**". I opened both pages with `pdfplumber` and read the lines. $0.2bn + $0.2bn = **400 $M**; the two differ in description *and* page |
| two rows alike but for the page → 2 items, 0 drops | 2 in, 2 out | **hand arithmetic on the within-filing key**: 66 ≠ 67, so two keys |
| three identical rows → 1 item, 2 drops | 3 in, 1 out | **hand arithmetic**: one key, 3 − 1 = 2 |
| each drop row names year, amount, direction, description, filing, page | the six fields | **the requirement**, assignment step 5. Each is looked for as its own text; the sentence around them is not asserted |
| the two headlines differ, and each run gets the right one | `REPEAT_WITHIN_ONE_FILING` then `REPEAT_ACROSS_FILINGS` | **the requirement**: the two comparisons drop for different reasons (round 2 amendment item 2). The constants are imported by name, never copied as literals |
| the merge returns with `{2023: 2023.0, 2024: 2024.0}` and both balance sheets | those two years | **the merge's stated year rule** (its own docstring, P9a step 3): prefer the filing whose `fiscal_year` equals the statement year. Each filing is primary for its own year, so both survive with the marker the fixture gave them |
| compound case → 1 item, 2 across-filing drops, every `kept:` names the 2023 row | 3 in, 1 out | **hand arithmetic on both keys**: the within-filing comparison runs against *this filing's kept rows*, and this filing keeps neither, so both fall to the across-filing comparison |
| `parse_pass2` with no `page` raises `ValueError` matching `'page'` | a stop naming the field | **rule 3** and the parser's own message contract (`:2193-2206`): `page` must be present and a positive 1-based page |
| `parse_pass2` with `page=0` raises `ValueError` matching `'page'` | a stop naming the field | same |
| `parse_pass2` missing `year`/`description`/`amount`/`direction` raises naming the field | a stop naming the field | **rule 3**: all four are required fields of `NonRecurringItem` with no default (`models/financial_statements.py:67-72`) |
| real Walmart file → merged count == written count == 14, Asda `(66, 2022, 200.0, add_back)`, Seiyu `(67, 2022, 200.0, add_back)` | 14 | **derived from the session file, not from a run**, and the two premises are asserted first: (1) the three filings report **disjoint** fiscal years, so no across-filing key can collide whatever the key holds; (2) inside each filing no two rows agree on all five key fields, so no within-filing key can collide. With no collision possible, every written row survives, so merged == written, and written is `9 + 2 + 3 = 14` counted off the JSON. The two figures are the **filing-page** values above |
| repaired `test_merge_keeps_one_item_per_year_amount_direction_and_description` → `[first, opposite, differently_worded, other]`, `items[0].page == 52` | 5 in, 4 out | **hand arithmetic on the across-filing key**, written out in the test's docstring, one line per row |
| repaired `three_filings` → `["Restructuring A", "Impairment B", "Settlement C", "Severance D"]` | 5 written, 4 out | **hand arithmetic**, in the comment above the fixture: A's re-report shares all four key fields with A and only the page moves |
| new `two_filings_with_a_doubled_row` → `["Impairment G", "Restructuring E", "Settlement F"]`, `validation_errors == []`, `len(calls) == 4` | 4 written, 3 out | **hand arithmetic**, in the comment above the fixture: E's second row shares all five within-filing fields; nothing else collides. 4 calls = 2 per filing × 2 filings, no retry |
| `route_b.financials == fin_a` and `route_b.non_recurring == items_a` | equal | **closed-form identity**: same JSON in, same statements and items out. The two routes meet at this one merge |

**No assertion in this unit came from the code's output.**

## Two counts, with their units

**Accuracy — of assertions.** **80 of 80 assertion statements** are hand-sourced, and
**0 came from the code's output**: 69 in `tests/unit/test_p14e_nri_dedupe.py` and 11
added or changed in the two repaired tests. Every one maps to a row of the table above
— a key definition applied by hand, a closed-form identity, a requirement quoted from
the assignment, or a figure I read off PDF pages 66 and 67. All 80 pass.

**Coverage — of the functions, then the branches, this unit added.**

- **Functions: 4 of 4 touched.** `nri_identity` (`:2818`) and
  `nri_identity_within_filing` (`:2860`) are called directly by name;
  `_print_repeated_item` (`:2905`) is exercised through both of its headlines; the
  rewritten body of `merge_filing_extractions` (`:2934`) is exercised by every merge
  case.
- **Statements: 29 of 29 executable lines added by the diff are covered, 0 missed.**
  Measured, not estimated: `-m pytest --cov=ingestion --cov-branch
  --cov-report=json` over the three test files, intersected with the added line
  numbers taken from `git diff -U0 -- ingestion/claude_extractor.py`.
- **Branches: 0 missing branch arcs touch any line this unit added.** Both sides of
  `repeated_row is not None` and both sides of `repeated is None` are taken, and
  `from_this_filing.setdefault` is exercised with and without a prior entry.
- For context, the whole file is `1007 statements, 205 missed, 380 branches, 71
  partial, 76%` under these three test files; the gap is elsewhere in the module and
  is not this unit's.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `item.page` — **the field this unit put into a key** | **stops, and the message names `'page'`** and the item's year and description | `test_an_item_with_no_page_stops_and_the_message_names_page` and `test_an_item_whose_page_is_not_a_positive_page_number_stops_naming_page`, against `ingestion/claude_extractor.py:2193-2206`. Also a required field with no default, `models/financial_statements.py:77` |
| `item.amount` | **stops, naming `'amount'`** plus the year and description | `test_an_item_missing_any_other_key_field_stops_and_names_it[amount]`, `claude_extractor.py:2183` |
| `item.year`, `item.description`, `item.direction` | **stop, and the exception names the field** — as a bare `KeyError`, not the parser's own `ValueError`, so the item is not named. See finding 1 | `test_an_item_missing_any_other_key_field_stops_and_names_it[year|description|direction]`, `claude_extractor.py:2252-2262` |
| `plan.pdf_path` (the filing name in both messages) | required field of `FilingPlan`, no default | checked by reading, as both earlier reviewers did; no new site |
| `kept_rows_this_filing.get(row_key)` → `None` | **not a default.** A presence test: `None` means "this filing has not kept this row", and that branch goes on to the across-filing comparison. Both branches do real work and both are exercised by my tests | `claude_extractor.py:3013-3018` |
| `kept_by_key.get(key)` → `None` | **not a default**, same shape. `None` appends the item; a hit reports and drops. Both branches exercised | `claude_extractor.py:3021-3032` |

**No "defaults to" row, and no stop path I could not lock.** I looked specifically for
a branch where the merge substitutes a value for a missing one and found none; the two
`.get` calls are one-argument presence tests, and `from_this_filing.setdefault` is an
insert-if-absent whose return value is discarded. **I wrote no test that asserts a
fallback.**

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The repaired `three_filings` repeat is `dict(item_a, page=51)`, not `dict(item_a)` | A re-report copies the printed line, so only the page moves — the round 1 reviewer measured `page 52` → `page 51` for one real Walmart note | A same-page repeat would still merge under `mut_pagecross`, so the test would be green against a broken across-filing key. With the page moved, **that test is one of the 13 that go red** |
| The renamed extractor test keeps `opposite` and gains `differently_worded` | The old test proved three of the four fields separate items; the description was the field it could not test, because it was not in the key | Dropping `opposite` would have lost a case the old test held. 5 in, 4 out tests all four fields in one place |
| A new file rather than more cases in `test_claude_extractor.py` | 31 tests about one pair of keys, with the "why hand-built, not WMT" reasoning at the top where a reader meets it first | Spread through an 817-line file, the warning in criterion 9 would be invisible, and the next tester would reach for the real file |
| `fields_missing_from` returns the missing names, and the assertion is `== []` | A test that fails must name the field that went missing | `assert names_item(...)` prints `assert False` and tells the next reader nothing |
| The two headline constants are imported by name | The programmer made them public for exactly this (round 2 finding 3) | A copied literal drifts the first time the sentence is reworded, and the test then fails for the wrong reason |
| The real-file test guards on the session file **and** every PDF it cites | `extractions/` and `10K_filings/` are both outside git. Backlog item 101: a guard that misses is a test reporting neither pass nor fail | A bare `exists()` on the JSON would pass on a machine without the PDFs and then fail inside the loader |
| Backlog item 119 is recorded as one test, named for the item | The assignment's "Out of scope": one test may record it as the measured behaviour, named as item 119 | Leaving it untested would make a change to item 119 silent. The test's docstring says in words that it endorses nothing |

## What I did not do

- **I did not touch `ingestion/claude_extractor.py`.** Hash identical at both ends,
  verified before and after every mutation run.
- **I did not weaken, skip or `xfail` anything.** The two `*_rule3_red.py` tests are
  still red and stay where they are; I confirmed both fail for their stated reasons.
- **I did not assert any fallback**, and I found none to assert.
- I did not test backlog item 62 (a drop reaching the console and not the web page) or
  reopen item 119. Both are out of scope by the assignment.
- I did not re-run the live market call. Criterion 14 of the programmer's list is not
  in mine, and a test that needs a market is not a unit test.

## Findings for the orchestrator

1. **`_parse_nri_response` stops on five Pass 2 fields with a bare `KeyError` that
   names the field but not the item** · `minor`, **pre-existing, not this unit's**.
   `confidence`, `source`, `amount`, `page` and `units` each get a `ValueError` whose
   message also names the item's year and description — the two things a reader needs
   to find it in the filing, and the parser's own docstring says so. But `year`,
   `description`, `line_item`, `direction` and `category` are read as `item["year"]`
   &c. at `ingestion/claude_extractor.py:2252-2262`, so an absent one raises
   `KeyError('year')` from inside a dataclass call: the field is named, the item is
   not, and the message does not say which filing or which of fourteen items. My
   `test_an_item_missing_any_other_key_field_stops_and_names_it` locks the stop and
   the field for four of them, deliberately accepting either exception type, so the
   test will not turn red when this is fixed. **Worth a backlog item**: five more
   `ValueError`s in the shape the other five already have.
2. **A compound-case test with the later filing's rows on *different* pages does not
   catch the round 2 tightening** · `note`, about tests, not about the code. I wrote
   that version first and `mut_notighten` survived my entire suite. The tightening
   (register a row in `kept_rows_this_filing` only when it is kept) bites only when
   the later filing's two rows are the **same printed line**. Anyone extending this
   unit's tests should know that the same-page shape is the one that holds it; it is
   in `test_every_kept_line_names_an_item_that_is_really_in_the_merged_list`, and
   losing that shape would make the tightening untested while the suite stayed green.
3. **`extractions/WMT.json` records absolute `pdf_path`s.** My real-file test skips
   cleanly when they do not resolve, but the file is not portable between machines and
   is not in git, so the one real multi-filing regression guard this repository has
   runs on exactly one machine. Not this unit's to fix; worth knowing before anyone
   cites `MERGED 14` as a gate result.
4. **Round 2 finding 1 / round 2 review F5 stand, and my tests record them without
   asserting them away.** The compound case prints two `[MERGE]` blocks with no total,
   and `REPEAT_WITHIN_ONE_FILING` says "listed twice" while printing twice for a row
   that appears three times. My `test_three_identical_rows_in_one_filing_…` asserts
   the two headlines and the count, not the wording, so a fix that adds a total or
   rewords the sentence will not turn it red. The carrier line is owned by
   `ingestion/session_extraction.py`, out of scope.

## Verdict

`pass`

Every value in scope matches an expectation that existed before the code ran — a key
definition applied by hand, a closed-form identity between the two routes, a
requirement quoted from the assignment, or a figure I read off PDF pages 66 and 67 of
the Walmart 10-K. Every stop path the merge's inputs have is locked, each by exception
type and by a message that names the field, and none of them defaults. Both keys are
held by cases that go red under a one-line mutation in the direction the docstrings
claim, measured in my own scratch trees, and the third mutant — the one the round 2
reviewer built — dies too. The real Walmart file passes all three mutants, which I
reproduced myself, so it appears once, labelled as the regression guard it is.
