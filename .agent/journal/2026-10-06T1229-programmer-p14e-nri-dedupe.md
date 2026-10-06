---
agent: programmer
assignment: P14e-nri-dedupe
round: 1
status: complete
files_touched: [ingestion/claude_extractor.py]
verdict: n/a
---

# P14e-nri-dedupe — two different items of the same size are two items, and no drop is silent

## What I did

`merge_filing_extractions` deduplicated non-recurring items on
`(year, amount, direction)` across the whole merge, with no `else`. Two genuinely
different items that shared those three fields became one, and nothing reported it:
Walmart's fiscal 2024 10-K prints two incremental divestiture losses for fiscal 2022,
Asda on PDF page 66 and Seiyu on page 67, each `$0.2 billion`, both `add_back`, so 14
items written became 13 merged.

Two changes, both inside `merge_filing_extractions` and the two helpers added beside it:

1. **The dedupe now runs across filings only, never within one.** One filing's Pass 2
   answer is one list and two rows in it are two items. A filing's own keys join the
   seen-set only after every one of its rows has been appended.
2. **The key gained the printed description** (`nri_identity`, a new public function:
   `(year, amount, direction, description)`). The description is the one field that
   tells Asda from Seiyu. The page and the `source` are deliberately left out and the
   docstring says why: both carry a page number of *one* PDF, so a key holding either
   could never match across filings and every overlapping item would be double-counted
   — the case the dedupe exists for.
3. **Every drop is printed** (`_print_repeated_item`), naming the year, amount,
   direction, description, filing and page of the item kept **and** the item dropped. It
   prints from inside the merge, which is the one function both routes call, so both
   routes show it. It does **not** stop the run.

No prompt and no schema changed. `extractions/WMT.json` was read and never written: its
sha256 is `c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675` at the start
of this run and at the end of it. Every mutation, variant session file and probe lives in
`C:\tmp\p14e\`, outside the repository.

## Done-criteria

Every command below ran with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`, on the Windows machine, with `PYTHONIOENCODING=utf-8`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | The two Walmart items both survive | **pass** | `.venv/Scripts/python.exe C:/tmp/p14e/show_items.py extractions/WMT.json` → `TOTAL WRITTEN 14   MERGED 14`, `ASDA in list: True`, `SEIYU in list: True`. Both rows printed: `2022 200 add_back p66 Incremental pre-tax loss on the divestiture of Asda...` and `2022 200 add_back p67 ... Seiyu ...` |
| 2 | The old behaviour is reproduced first | **pass** | `git archive HEAD \| tar -x -C /c/tmp/p14e/head`, then the same script in that tree → `TOTAL WRITTEN 14   MERGED 13`, `ASDA in list: True`, `SEIYU in list: False`. No `git stash` was used; the working tree was never reverted |
| 3 | The same item re-reported by two filings is still merged once | **pass**, three ways | (a) hand-built, `C:/tmp/p14e/hand_merge.py` → `RESULT: 1 item(s)`. (b) **real route B**: `C:/tmp/p14e/WMT_rereport.json` adds the fiscal 2024 "Net losses from fair value changes…" item to the FY2025 10-K, where page 51 really does print `$3.8 billion` for fiscal 2024; `-m ingestion.session_extraction check` → `EXIT=0`, `non-recurring items: 14` from 15 written. (c) **real route A**, `C:/tmp/p14e/after/probe_route_a_merge.py` → `'Restructuring A'` flagged by two filings appears once |
| 4 | A drop is reported, naming both items | **pass** | route B, `check_rr.txt:57-59`: <br>`  [MERGE] Non-recurring item already reported by an earlier filing - counted once, not twice:`<br>`    kept   : 2024  3,800.0 $M  add_back  'Net losses from fair value changes of equity and other investments, recognized in other gains and losses'  [Walmart Inc._10-K_2024-01-31_English.pdf, page 52]`<br>`    dropped: 2024  3,800.0 $M  add_back  'Net losses from fair value changes of equity and other investments, recognized in other gains and losses'  [Walmart Inc._10-K_2025-01-31_English.pdf, page 51]` |
| 5 | A drop does not stop the run | **pass** | the route B `check` above **exits 0** and goes on to print `Years: [2022, 2023, 2024, 2025, 2026] \| balance sheet(s): [2026] \| non-recurring items: 14`. `hand_merge.py` prints `CRITERION 5: the merge returned…` after the drop |
| 6 | Two items in one filing are never merged | **pass**, both shapes | `hand_merge.py` 6a: one filing holding Asda and Seiyu, both `(2022, 200.0, add_back)` → `RESULT: 2 item(s)`, no drop printed. 6b: **the identical row written twice** in one filing → `RESULT: 2 item(s)`. Route A probe: `Severance D` and `A different charge, also 9`, both `(2024, 9.0, add_back)` in one filing, both survive |
| 7 | The key's fields are stated | **pass** | `nri_identity`'s docstring, `ingestion/claude_extractor.py:2814-2844`: one bullet per field in the key saying why it is there, then two bullets for `page` and `source` saying why they are not, then the statement that the match is exact equality with no tolerance and no similarity rule |
| 8 | Route A is unchanged in what it asks the model | **pass** | `git diff --name-only` → `ingestion/claude_extractor.py` alone. `git diff -U0` hunk headers: one `@@ … def _plan_target_years` (the two new helpers, added after it) and five inside `merge_filing_extractions`. `git diff \| grep -icE "^[+-].*(_PASS1_\|_PASS2_\|_SCHEMA\|prompt\|SYSTEM\|system_prompt\|json_schema)"` → **0** |
| 9 | Types | **pass** | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → **5 errors in 2 files**, 21 files checked: 4 `union-attr` in `analysis/projector.py`, 1 `operator` in `api/routes_upload.py`. None removed, none added, **0 in `ingestion/`**. Run after the last edit |
| 10 | Lint | **pass** | `-m ruff check .` → **Found 4 errors**, every one `BLE001`: `api/routes_valuation.py:451`, `:733`, `cli.py:1204`, `tests/test_e2e_all_googl.py:106`. Run after the last edit |
| 11 | Census | **pass** | the grep at `docs/2-rules/rules.md:102` over `models analysis api ingestion` → **64**; with `pipeline.py` added → **64**. No site removed and none added |
| 12 | Route | **pass** | `TestClient(app.app, raise_server_exceptions=False).get('/').status_code` → **200** |
| 13 | The failing test set | **pass**, with two tests to repair in `tests/` | see "Measurements" below. Before `{}`, after `{test_merge_keeps_one_item_per_year_amount_direction, test_three_filings_both_routes_give_equal_statements_and_items}`. Both assert the old key by name |
| 14 | The share price moves, and I say by how much | **pass**, with a correction to the assignment | **$30.64 → $30.66**, see below. The market call ran. **The fiscal 2022 operating margin does not move** — the assignment's stated mechanism is wrong for this item, and the reason is measured below |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The key is `(year, amount, direction, description)` | The assignment, "add what the model actually wrote: the printed description and the page, or the `source`". The description is the only field that separates the Asda loss from the Seiyu loss | **The page is not in the key.** The same item re-reported by a later filing sits on a different page of a different PDF, so a key holding the page can never match across filings and criterion 3 fails for every real filing. `source` carries a page number too (`"Note 12 … page 66"`), so it moves for the same reason. Putting either in would turn a silent drop into a silent double-count |
| Exact equality on the description, nothing else | Assignment item 4: "Decide nothing about what is 'the same item'… Do not add a similarity rule, a fuzzy match, or a tolerance" | No `.strip()`, no case folding, no token overlap. Two differently-worded descriptions are two items; that is a reading the printed text cannot settle, and it is not Python's to settle. See the finding below |
| The dedupe is per-filing-boundary, not global | Assignment item 1. One filing's Pass 2 answer is one list; two rows in it are two rows the model wrote, each with its own description and page | A global set cannot tell "the model listed two losses" from "two filings listed one loss". Deferring a filing's keys to after its own rows is the only thing that distinguishes them, and it is one line (`kept_by_key.update(from_this_filing)`) |
| The message is `print`ed from inside the merge | Assignment item 3: "Print it where the other merge and check messages already print, so both routes show it". The merge is the one function both routes call (`claude_extractor.py:3429`, `session_extraction.py:797`), and this file already prints its other check summaries (`:1400`, `:1553`, `:1689`, `:1838`) | Returning the messages would change `merge_filing_extractions`' return type and force an edit to `ingestion/session_extraction.py`, which is **out of scope** and which the assignment says does not own the merge |
| `kept_by_key` is a `dict`, not a `set` | The message has to name the item that was kept and the filing it came from, so the key must map to them | A `set` cannot answer "which item is this a repeat of" |
| `from_this_filing.setdefault` rather than `[key] =` | If one filing writes the identical row twice, both are kept (criterion 6b) and the **first** is the one a later filing's repeat is reported against | Overwriting would report the drop against the second copy, which is the same item; either is defensible, and the first-seen rule matches the rest of the merge |
| `NriIdentity` type alias | The tuple is spelled in three places (the function's return, and the merge's two dicts). One name so they cannot drift | Spelling it out three times is one careless edit away from a key and a dict that disagree |

**A code change made to reach a target number, rather than on a reason, is forbidden.**
Nothing here was changed to reach a number. The only figure this unit moves is the one
the restored item puts back, and it moves in the direction the restored item requires
(one more `add_back` in fiscal 2022 → fiscal 2022 pre-tax income higher by 200 $M →
fiscal 2022 effective tax rate lower → the projection's tax rate lower → NOPAT higher →
price higher). The arithmetic is checked by hand below.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `item.year`, `item.amount`, `item.direction`, `item.description` (in `nri_identity`) | **Cannot be missing.** All four are required fields of `NonRecurringItem` with no default (`models/financial_statements.py:67-72`), and the Pass 2 parser stops on an absent key before the merge runs | `models/financial_statements.py:67-72`; route B's `_filing_problems` / `parse_pass2` stop first |
| `item.page` (printed in the message only) | required field, no default (`models/financial_statements.py:77`) | same |
| `plan.pdf_path` (the filing name in the message) | required field of `FilingPlan`, no default; `plan_filings` raises on an empty list | `claude_extractor.py`, `FilingPlan` |
| `kept_by_key.get(key)` → `None` | **This is a presence test, not a default.** `None` means "no earlier filing reported this", and that branch appends the item — it substitutes no value for a missing one. Both branches do real work; neither is empty | `claude_extractor.py:2929-2939`. The census grep is unchanged at **64**, so no new site of the forbidden shape was added |

No "defaults to" row. This unit adds no fallback, and it removes none.

## Measurements

**The repository file, before and after.** `ingestion/claude_extractor.py`
`ec77b4bcfab6fa6a14ebc3fcd4cc74b928859e2de494fd0c6f1597c0f67cf719` at `acfdb0e` →
`578bd18ab3ac8ae71460f7ede740fda9747a134f87c88b281376eb7343d4d453` now (the deliberate
change). **`extractions/WMT.json` is `c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675` at both ends** — read, never written. Every experiment ran in `C:\tmp\p14e\head`
(`git archive HEAD`) and `C:\tmp\p14e\after` (the same archive with only this file
replaced), each given a copy of `10K_filings/` and `extractions/`. No mutation was ever
written into the repository.

**The suite, as failure SETS.** `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly`,
run in both scratch trees so the two runs see the same filings:

| Tree | Result | Failure set |
|---|---|---|
| `head` (`acfdb0e`) | `1175 passed, 2 skipped` in 130.07s | **{ }** |
| `after` (this unit, final code) | `1173 passed, 2 skipped, 2 failed` in 111.21s | **{ `tests/unit/test_claude_extractor.py::test_merge_keeps_one_item_per_year_amount_direction`, `tests/unit/test_session_extraction.py::test_three_filings_both_routes_give_equal_statements_and_items` }** |

Both tests changed state, and **both of them assert the defect**:

- `test_merge_keeps_one_item_per_year_amount_direction` (`tests/unit/test_claude_extractor.py:590-603`)
  builds `first = _nri(2023, 10.0, "add_back", "seen in the 2023 10-K")` and
  `duplicate = _nri(2023, 10.0, "add_back", "same item, seen again in the 2024 10-K")` —
  **two different descriptions** — and asserts the second is dropped. Its own comment
  names the key it is testing: "Key (year, amount, direction), first seen kept". Under
  the new key the two texts are two items and 4 in gives 4 out.
- `test_three_filings_both_routes_give_equal_statements_and_items`
  (`tests/unit/test_session_extraction.py:346-365`) fails at **line 361 only**, on the
  hand-written list of expected descriptions. Its fixture writes the repeat as
  `dict(item_a, description="A, read again")` (`:249`) — again a different text. The
  failure message is `At index 2 diff: 'A, read again' != 'Settlement C'`.
  **The two assertions above it still pass:** `assert route_b.financials == fin_a` and
  `assert route_b.non_recurring == items_a` (`:354-355`). So route A and route B still
  produce the identical merged item list after this change.

`tests/` is out of my scope and I wrote nothing there. Both tests need a tester to
re-express the "one item, two filings" case with the **same** printed description, which
is what a re-report actually looks like.

**Criterion 14 — the fiscal 2022 figures and the share price, before and after.**
`cli.py --session-file extractions/WMT.json`, run in each scratch tree, exit 0 in all
four runs. Because the market call is live, I ran the pair twice, in opposite order, to
separate the change from market drift:

| Run | Tree | Market price | Derived tax rate | Implied price |
|---|---|---|---|---|
| 1 | `head` | $106.71 | 23.15% | **$30.64** |
| 2 | `after` | $106.72 | 23.11% | **$30.66** |
| 3 | `after` | $106.74 | 23.11% | **$30.66** |
| 4 | `head` | $106.75 | 23.15% | **$30.63** |

`head` gives $30.64 and $30.63; `after` gives $30.66 twice. **The change is worth about
+$0.02 to +$0.03 a share**; market drift over the four runs is ±$0.01.

The filing half, which needs no market call, at full precision
(`C:/tmp/p14e/fy2022.py`, through `pipeline.adjust_financials`):

| Fiscal 2022 figure | `head` | `after` |
|---|---|---|
| items applied | 13 | **14** |
| total add-backs (CLI stage 3) | 16,147M | **16,347M** |
| adjusted `other_non_operating` | -400.0 | **-200.0** |
| adjusted net income | 18,950.0 | **19,150.0** |
| adjusted EBIT | 25,942.0 | 25,942.0 — **unchanged** |
| adjusted operating margin | 0.045293441861602016 | 0.045293441861602016 — **unchanged** |
| effective tax rate | 0.20062431451953092 | **0.19894587132937339** |
| historical FCFF, `Int*(1-t)` / FCFF | 1,594 / 12,310 | **1,597 / 12,313** |

Checked by hand: `effective_tax_rate = tax_expense / ebt`, tax 4,756.0 unchanged, so
`ebt` is `4756/0.20062431451953092 = 23,705.7` before and
`4756/0.19894587132937339 = 23,905.7` after — **exactly 200 apart**, the restored item.
The projection's tax rate is the mean of the five years' effective rates:
`(0.20062431 + 0.25535332 + 0.21748284 + 0.22776749 + 0.25613748) / 5 = 0.23147309`
before, `0.23113740` after. The CLI prints 23.15% and 23.11%.

**Correction to the assignment, fact 3.** The assignment says the lost 200 $M understates
"that year's operating margin" and that "the three-year average the projection uses moves
with it". **Measured, it does not.** All four of Walmart's fiscal 2022 Pass 2 items carry
`line_item: "other_non_operating"`, which `analysis/normalizer.py` applies **below** EBIT,
so the fiscal 2022 adjusted operating margin is `0.045293441861602016` in both trees and
the operating-margin average the projector uses is `0.04249410775242838` in both. What
the dropped item really moved is the **fiscal 2022 effective tax rate**, and through the
derived `tax_rate` assumption it moves NOPAT in all five projected years and the terminal
value. The defect and its cost are real; the mechanism stated in the assignment is not
the one that fires for this item. A different item, classified to an operating line, would
move the margin exactly as the assignment describes.

## What I did not do

- **I did not touch `tests/`.** The two tests that go red both encode the old key; they
  are a tester's to re-express. Named above with their line numbers and their fixtures.
- I did not change `ingestion/session_extraction.py`. The drop message is printed, not
  returned, precisely so that file needs no edit. A consequence: the message does **not**
  join `SessionExtraction.validation_errors`, so it does not appear in `check`'s
  "problem(s)" block — by design, since a repeat is not a problem.
- I did not put the message on a web page. The assignment says that, if I think it
  belongs there, it is a finding and I stop. It is below, as finding 2.
- I did not add a `low`-confidence or similarity rule of any kind.

## Findings for the orchestrator

1. **Two differently-worded descriptions of one item are now two items, and nothing
   reports that either.** This is the deliberate half of the trade: the merge refuses to
   judge that `"Restructuring charges"` and `"Charges for the reorganization and
   restructuring of certain businesses"` are one charge, because deciding that is rule
   1's forbidden judgement in Python's clothing. Measured on the route A probe: an item
   re-reported with the text changed to `"A, read again"` survives as a second item, and
   that is a silent **double-count** of the same shape as the silent drop this unit
   closed — it just fails the other way. **Nothing in this repository would report it.**
   If a real pair is ever found, it is a decision for the user, not a tolerance for a
   programmer. Worth a backlog item with this entry as its evidence.
2. **A drop is reported on the console and nowhere else.** Route B's `check` and the CLI
   print it; the web routes print it to the server console, where no reader sees it. That
   is backlog item 62's shape exactly ("No failed reading check reaches the web page, for
   either route"), and this message belongs in the same fix. It is **not** a
   `validation_error`, so it would need its own carrier.
3. **The assignment's fact 3 is corrected above**, with the measurement. Backlog item
   112's write-up in `docs/9-reference/refactor-backlog.md` says "the fiscal 2022
   operating margin is understated by that amount"; it is not, because the model
   classified all four items to `other_non_operating`. The cost is real but it lands on
   the derived tax rate. The backlog entry should be corrected when 112 is closed.
4. **`nri_identity` is public and nothing outside this file calls it.** I made it public
   because it is the statement of what "the same item" means, and a reviewer or a test
   should be able to call it by name rather than reach for a private one — backlog item
   53 is the complaint that the session loader imports `_NRI_SCHEMA` by its private name.
   If the orchestrator prefers it private, that is a one-line change.
5. **`check`'s exit code does not distinguish "clean" from "clean, and one item was
   merged away".** `check_rr.txt` exits 0 with a `[MERGE]` line in the middle of 50 lines
   of output. A summary line beside `Years: … | non-recurring items: 14` saying how many
   were merged away would make it countable. Out of this unit's scope (that summary is
   printed by `ingestion/session_extraction.py`).
