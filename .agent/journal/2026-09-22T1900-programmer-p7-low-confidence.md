---
agent: programmer
assignment: P7-low-confidence
round: 1
status: complete
files_touched: [analysis/normalizer.py, ingestion/claude_extractor.py, cli.py, api/routes_valuation.py, templates/valuation_result.html]
verdict: —
---

# P7-low-confidence — a `low`-confidence item is documented, not applied, and both outputs say so

> Opened before the first command. Filled as each result landed.

## What I did

`analysis/normalizer.py` gained one function, `partition_by_confidence`, which splits the
Pass 2 items into `(applied, excluded)`: `low` is excluded, `medium` and `high` are
applied, and **anything else raises**, naming the value and the year. Both entry points
partition *before* they normalise and hand `normalize_financials` only the applied list,
so that function's signature — and the 145 assertions written against it — are untouched.
`ingestion/claude_extractor.py`'s `.get("confidence", "high")` is gone: an item that
arrives with no confidence tag now stops the parse and names the year and the description.
Both outputs print the excluded items in full — year, amount, line item, direction,
description, cited source — under a heading that says they were **not applied**, and the
headline share price carries the same sentence beside itself in both.

**Nothing was extracted and nothing was paid for.** The content-keyed cache
`P6-honest-output` wrote held a valid entry for the L3Harris FY2024 10-K; I checked the
key would hit before running anything (`c:/tmp/p7/key_dryrun.py` →
`differences: NONE -> this run would HIT the cache and pay for nothing`).

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | a `low` item is not applied to the statements | **pass** | `c:/tmp/p7/criteria_1_3.py`: `applied=0 excluded=1`, `sga=200.0 ebit=400.0`, `income statement UNCHANGED? True`. The **same item** through the unpartitioned path gives `sga=100.0 ebit=500.0` |
| 2 | `medium` and `high` are applied | **pass** | same script: `medium: sga=100.0 ebit=500.0 OK=True`; `high: sga=100.0 ebit=500.0 OK=True`; mixed list of all three → `applied amounts=[10.0, 20.0]`, `excluded amounts=[40.0]`, `sga=170.0` (hand: 200 − 10 − 20) |
| 3 | an absent or unrecognised confidence **stops**, naming the value and the year | **pass** | same script: `''`, `'unknown'`, `'HIGH?'`, `'0.9'` and a non-string `None` all raise `ValueError`, each naming the value **and** `2024`. Parser payload with the key removed → `ValueError: Pass 2 returned a non-recurring item with no 'confidence' field: year 2024, 'a charge'…` |
| 4 | the excluded items appear in the CLI output with their source | **pass** | `c:/tmp/p7/lhx_counterfactual.txt`, a real `cli.py` run — block pasted below. **On the real LHX extraction the block is empty and says so**, because that extraction contains no `low` item; see criterion 7 |
| 5 | the excluded items appear on the result page | **pass** | `c:/tmp/p7/route_probe.py`, a real `POST /valuation` through `TestClient` — 200, 11,971 bytes, not an error page. Rendered row: `2024 \| +120 \| sga \| add_back \| Legal settlement, components not separately disclosed \| Note 19 - Legal proceedings`. Both the cache-miss and the cache-hit branch |
| 6 | the output says the valuation **excludes** them | **pass** | page, beside the headline: `This price EXCLUDES 1 low-confidence non-recurring item(s), listed below. They were not applied to the financial statements.` CLI, in the final summary: `This price EXCLUDES 1 low-confidence non-recurring item(s) worth +1,140M of earnings adjustment in total` |
| 7 | the effect on LHX is measured | **pass** | `c:/tmp/p7/lhx_ab.py`, one extraction and one price fetch, pipeline run twice: **$411.39 with the exclusion and $411.39 without it — identical, nothing dropped**, because the model tagged all 15 items `high` (13) or `medium` (2). Detail and the counterfactual below |
| 8 | no existing assertion changed meaning | **pass** | `pytest -q` → **`1 failed, 145 passed`**, the failure being `tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`. Byte-identical to the baseline I measured before my first edit |
| 9 | lint 5, types ≤ 14 set-diffed, census ≤ 116, `GET /` 200 | **pass** | ruff **5**, all `BLE001`, the same five files; mypy **14 in 4 files**, `diff` against `git archive 54c5af8` with line numbers stripped → **IDENTICAL SETS**; census **116**; `GET / -> 200` |

## Criterion 7 in full — what the decision costs on the user's own filing

**Measured, on the extraction in `cache/`** (L3Harris FY2024 10-K,
`sha256 7d7ca6485a7eaf8e…`, 15 Pass 2 items). One `fetch_price_data` call, reused by both
runs, so the only difference between them is the partition:

```
extraction: L3Harris Technologies Inc._10-K_2024_English.pdf  sha=7d7ca6485a7eaf8e
            15 Pass 2 items; confidences: ['high', 'medium']
market:     price $239.83 (fetched ONCE and reused by every run below)

=== MEASURED: the L3Harris FY2024 extraction as it is ===
  partition: applied=15  excluded=0  -> []
  A. every item applied (before this unit)      items=15  op margin=11.09%  WACC=7.52%  implied=$411.39
  B. low-confidence excluded (after this unit)  items=15  op margin=11.09%  WACC=7.52%  implied=$411.39
  difference: $0.00  (identical)
```

**On this filing the user's decision costs nothing, and no item was dropped.** The model
tagged thirteen items `high` and two `medium` — the two `medium` are 2024's `+15M legal
reserve on sga` and `−46M gain on other_operating_expense` — and every one of the fifteen
is still applied. The full CLI run is `c:/tmp/p7/lhx_new.txt`: implied **$411.49** at that
moment's price of $239.94, and the excluded block reads
`None. Every item the model identified was applied.`

**The item the decision is actually about is not in this extraction.** It was in the
20 Sep extraction *of this same filing* and not in the 22 Sep one — 2023, `+1,140M on
sga`, `confidence: low`, "components not separately disclosed for 2023"
(`2026-09-22T1400-programmer-p6-honest-output.md:290`,
`2026-09-22T1500-code_reviewer-p6-honest-output.md:292`). Re-instating that recorded item
and running the same two paths:

```
=== COUNTERFACTUAL - not a valuation of L3Harris ===
  partition: applied=15  excluded=1  -> ['2023 1,140 sga (low)']
  C. every item applied, incl. the 1,140M `low`  items=16  op margin=13.05%  WACC=7.52%  implied=$474.96
  D. the 1,140M `low` excluded                   items=15  op margin=11.09%  WACC=7.52%  implied=$411.39
  difference: $-63.57  (-13.4% of C)
```

**This is a constructed input and I am labelling it as one.** It is not a reading of a
filing: the item's fields come from the journal record, not from the PDF, and $474.96 is
not a valuation of L3Harris. What it measures is the mechanism, on the item the decision
was made about: **one `low`-confidence item worth 1,140M moved the implied share price by
$63.57, or 13.4%, and now it does not move it at all.**

**On the run-to-run variance claim: my run neither confirms nor refutes it.** One
extraction cannot measure variance, and the extraction I had contains no `low` item. What
it does show is that the single largest recorded difference between the two LHX runs —
1,140M of add-back, worth $63.57 a share — was a `low` item and would now be excluded from
both. That is one data point about one item, **not a measurement of variance**, and the
assignment told me not to assert it.

## The CLI block, criterion 4

From `c:/tmp/p7/lhx_counterfactual.txt` — a real `python cli.py … --cache-dir c:/tmp/p7/cache`
run, exit 0, against the same L3Harris extraction with the recorded `low` item re-instated
(`c:/tmp/p7/make_counterfactual_cache.py` wrote that scratch cache; **nothing was written
inside the repository**):

```
NON-RECURRING ITEMS EXCLUDED - NOT applied to the F/S
======================================================================
  1 item(s) the model tagged LOW confidence were NOT applied
  to the financial statements, so the valuation below does not include them.
  Add-backs withheld: 1,140M  |  Removals withheld: 0M
  To apply one, re-read the note it cites and treat it by hand.

  [2023] +1,140M  RESTRUCTURING  (low confidence - EXCLUDED)  line_item=sga  direction=add_back
         LHX NeXt implementation costs and other charges in G&A (components not separately disclosed for 2023)
         Source: MD&A - General and Administrative Expenses (components not separately disclosed for 2023)
```

and the arithmetic downstream of it, in the same run — 2023's delta is 744, **not** 1,884:

```
GAAP -> NON-GAAP RECONCILIATION ($M)
  2022: EBIT  GAAP=     1,127  Adj=     1,921  Delta=      +794
  2023: EBIT  GAAP=     1,426  Adj=     2,170  Delta=      +744
  2024: EBIT  GAAP=     1,918  Adj=     2,313  Delta=      +395

FINAL VALUATION SUMMARY
  Implied Price:      $     411.47
  This price EXCLUDES 1 low-confidence non-recurring item(s)
  worth +1,140M of earnings adjustment in total (listed in full above).
```

and the gathered block at the foot of the same run:

```
  Non-recurring items excluded
    1 item(s) the model tagged LOW confidence were NOT applied to the financial
    statements, on the user's decision of 2026-09-22. Each is listed above with its year,
    amount, line item, direction, description and cited source.
    [2023] +1,140M on sga - LHX NeXt implementation costs and other charges in G&A
    (components not separately disclosed for 2023) (source: MD&A - General and
    Administrative Expenses (components not separately disclosed for 2023))
```

**At least one input to that share price came from the filing.** The cache entry is keyed
on the sha256 of `10K_filings/LHX/L3Harris Technologies Inc._10-K_2024_English.pdf`, and
the run prints FY2024 revenue **21,325** and GAAP EBIT **1,918** off it, with total debt
12,236 and interest expense 675 driving a *measured* cost of debt of 5.52% — none of which
is a default.

## The page, criteria 5 and 6

`c:/tmp/p7/route_probe.py`: a real `POST /valuation` through `starlette`'s `TestClient`,
with `extract_financials`, `extract_multi_year` and `fetch_price_data` faked at the
boundary and nothing else stubbed. No key, no PDF, no network. Two items are returned by
the fake extractor: one `high` (40M) and one `low` (120M), both `add_back` on `sga`.

```
=== POST /valuation, extract branch (cache miss) ===
  status 200, 11,971 bytes, error page? False
  heading present? True

  --- the raw table rows ---
    Year | Amount ($M) | Line item | Direction | Description | Source cited in the filing
    2024 | +120 | sga | add_back | Legal settlement, components not separately disclosed | Note 19 - Legal proceedings

  --- beside the headline figure ---
    Implied Share Price $22.58
    This price EXCLUDES 1 low-confidence non-recurring item(s), listed below.
    They were not applied to the financial statements.

  page mentions the low item's source? True
  page mentions the applied HIGH item in the excluded table? False
```

and the prose above that table, tags stripped:

```
  The 1 item(s) below were NOT applied to the financial statements, so every figure on
  this page - including the implied share price - is computed without them. The model
  that read the filing tagged each one low confidence, and on the user's decision of
  2026-09-22 a low-confidence item is documented rather than adjusted. To apply one,
  read the note it cites below and treat it by hand.
```

**The cache-hit branch is exercised too, because it is the path a real user takes**
(`GET /assumptions` then `POST /valuation`):

```
  GET /assumptions -> 200; cache now holds ['2024:c:/tmp/p7-never-opened.pdf']
  cached value is a tuple of (financials, excluded): FinancialStatements, 1 excluded item(s)
  cached sga (800 - 40 applied, 120 withheld) = 760.0
  POST /valuation -> 200; excluded block present? True
  and it still cites the source? True
```

`sga = 760.0` is the check that matters: 800 − 40 with the `high` item applied, and the
120 withheld. The arithmetic and the page agree.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The partition is a function in `analysis/normalizer.py`, called by the two entry points, and `normalize_financials` is untouched | Assignment step 1, and rule 1: "the model identifies a candidate and cites its note; `analysis/` decides what that does to a figure" | Filtering inside `normalize_financials` would change what 145 assertions mean; filtering in `ingestion/` would put the decision back on the wrong side of the boundary |
| One function returning `tuple[list, list]`, not a small result dataclass | Every result dataclass in this repository lives in `models/valuation.py`, and `models/` is **out of scope** for this unit. A one-off dataclass in `analysis/` would be the second place such a type lives | Two functions (`applied_…`, `excluded_…`) would iterate the same list twice and let a caller use one and forget the other. The docstring states the order, and both call sites unpack on one line |
| `low` excluded, `medium` and `high` applied, no threshold constant and no setting | The user's decision of 2026-09-22 names low confidence and nothing else. Assignment step 2 | A configurable threshold is a way to reinstate the defect under a value nobody reads |
| Two tuples of **strings**, never a mapping from a tag to a function | Rule 2 permits a table that maps a key to a value and forbids one that maps a key to behaviour | A `dict[str, Callable]` keyed on a string that came from the model is exactly the registry rule 2 bans |
| An unrecognised confidence **raises**, and is not silently excluded | Rule 3, and the two adjacent defects in the same file (unknown label, unknown direction) both raise since `38b903c`. Excluding an unknown would be as much a guess as applying it — it would silently drop a real adjustment | The message names the value, the year, the amount and the line item, so the reader can find the item in the filing |
| Case and surrounding whitespace are folded before the comparison | `_resolve_field` in the same file already folds them for `line_item` (`key = line_item.strip().lower()`). `"LOW"` is not an unknown tag, it is `low` shouted | Raising on `"Low"` would stop a run over a capital letter and teach a user to fight the tool |
| `str(item.confidence)` rather than `item.confidence.strip()` | A JSON `null` or a number that reached the field arrives as `None`/`float` and must raise the **named** `ValueError`, not an `AttributeError` from inside the loop. Proved: `None -> ValueError, names None? True; names the year? True` | An `isinstance` check with a second message would give the same value two error paths |
| The extractor raises a `ValueError` naming the year and the description, rather than letting `item["confidence"]` raise `KeyError` | A bare `KeyError('confidence')` names the field but not which of fifteen items lacks it. Rule 3 asks the stop to name the field; a reader also needs to find the item | I kept the change inside `_parse_nri_response` and touched nothing else in that file — `source`'s `.get(..., "")` on the next line is untouched and is finding 3 below |
| `print_non_recurring_items`' heading became "NON-RECURRING ITEMS **APPLIED**" and its counter "Applying 15 items" | It is no longer the Pass 2 list; it is the list the arithmetic used. A list printed under an unqualified heading that is not the list the arithmetic used is this unit's own defect wearing a different face | Leaving the heading alone would have left the CLI claiming the model found 15 items on a run where it found 16 |
| `_extraction_cache` now stores `(financials, excluded)` | On the path a real user takes, the extraction happens in `GET /assumptions` and the result page is a different request. Storing the statements alone made the excluded items unreachable from the page on exactly that path | Re-deriving them in `run_valuation` would mean a second extraction. The module-global cache itself is backlog item 5 and is **not** fixed here |
| The empty case prints a sentence rather than nothing | "None. Every item the model identified was applied." is a fact the reader needs; a blank space is indistinguishable from a block that failed to render | It is also what made criterion 7's null result legible on the real LHX run |
| An item with no `source` renders `(none cited)` | The absence is made visible rather than left as an empty cell that reads as "fine". It reaches no number | Printing nothing would hide that the model cited no note for an item it was already unsure of |

**No code change in this unit was made to reach a target number.** The one figure this unit
moves is the implied share price when a `low` item is present, and it moves *because the
item is withheld*, which is the change that was commissioned. The LHX price did not move at
all, and I am reporting that rather than reaching for a filing that would have made the
number more interesting.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `NonRecurringItem.confidence`, in `partition_by_confidence` | **stops**, naming the value, the year, the amount and the line item | `c:/tmp/p7/criteria_1_3.py`: `''`, `'unknown'`, `'HIGH?'`, `'0.9'`, `None` → `ValueError`, each naming the value and `2024` |
| the `confidence` key in a Pass 2 JSON item | **stops**, naming the year and the description | same script: `ValueError: Pass 2 returned a non-recurring item with no 'confidence' field: year 2024, 'a charge'…` |
| `NonRecurringItem.source`, printed for an excluded item | **does not stop — renders `(none cited)`** | Deliberate, and it reaches no number: the item is excluded from the arithmetic by definition, and the cell is what tells the reader the model cited nothing. The underlying `source: str = ""` default in `models/` and the parser's `.get("source", "")` are finding 3 |
| `NonRecurringItem.confidence` when the object is **constructed in Python without one** | **does not stop — `models/financial_statements.py:28` defaults it to `"high"`** | **This is a finding against my own unit and I am writing it.** `models/` is out of this unit's scope and the assignment says to stop and say so rather than change it. Finding 1 |
| `item.year`, `item.amount`, `item.line_item`, `item.direction` | unchanged from before this unit: `direction` and `line_item` already stop (`38b903c`); `year` silently discards the adjustment when it matches no statement | Backlog item 25, `analysis/normalizer.py:167-170` — **I saw it, in the file I was editing, and left it**, as the assignment instructs |

**No new default was added.** The census grep over this unit's added lines only:

```
$ git diff -U0 | grep "^+" | grep -E "if [^)]+ else 0(\.0)?\b|\bor +(0|0\.0)\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0|\*\*kwargs|getattr\("
exit=1        (no output)
```

## Rules 1, 2, 4, 5, 6

- **Rule 1.** No number in this diff came from a model. The change to `ingestion/` removes
  a default and adds a stop; no prompt, no schema field, no model call was touched. **The
  boundary moved back where the rule puts it**: the model still identifies a candidate and
  cites its note, and `analysis/` now decides what that does to a figure instead of
  applying whatever it was handed. **No extraction was run — zero tokens.**
- **Rule 2.** One new function, `partition_by_confidence(non_recurring: list[NonRecurringItem])
  -> tuple[list[NonRecurringItem], list[NonRecurringItem]]`. Named, typed, no `**kwargs`,
  no `getattr` on an outside name. The two confidence tables map strings to membership,
  not to behaviour; nothing in this diff is dispatched on a value that came from data.
- **Rule 4.** Improved. The excluded items are the one part of the chain that previously
  vanished between the extraction and the share price; both outputs now print each with
  the note it cited, so a reader can walk it back to a page and apply it by hand.
- **Rule 5.** No new data source. `ingestion/` gained no fetch, and the filing remains the
  only source of the statement figures.
- **Rule 6.** The exclusion is stated beside the headline figure and again in the gathered
  "what was not measured" block, in both outputs, with the date of the decision that
  produced it.

## Measurements

| Gate | Baseline (`54c5af8`, measured before my first edit) | After | Verdict |
|---|---|---|---|
| Tests | `1 failed, 145 passed` | **`1 failed, 145 passed`** | unchanged; the failure is `test_dcf_rule3_red.py`, the deliberate red |
| Lint | 5, all `BLE001` | **5** | unchanged, same five sites |
| Types | 14 in 4 files | **14 in 4 files** | **set**-diffed against `git archive 54c5af8`, line numbers stripped → `IDENTICAL SETS` |
| Rule-3 census | 116 | **116** | unchanged |
| `GET /` | 200 | **200** | — |

Diff: **5 files, +284 / −27**, exactly the Files in scope. `git status --short -- tests/
STATUS.md .agent/journal/INDEX.md docs/` is **empty**.

Figures this unit moved, with the input that produced them:

| Figure | Before | After | Input |
|---|---|---|---|
| LHX implied share price | $411.39 | **$411.39** | the FY2024 cache entry, 15 items, none `low` |
| the same, with the recorded 1,140M `low` item present | $474.96 | **$411.39** | counterfactual; the item's fields come from the journal, not from the PDF |

Scratch, all outside the repository: `c:/tmp/p7/{criteria_1_3,route_probe,lhx_ab,key_dryrun,
load_cache,make_counterfactual_cache}.py`, `c:/tmp/p7/{lhx_new,lhx_counterfactual,
base_errs,head_errs}.txt`, `c:/tmp/p7/base/`, `c:/tmp/p7/cache/`. Nothing was copied into
the repository and no repository cache file was written or overwritten.

## What I did not do

- **Did not run an extraction.** The cache hit was verified before anything ran
  (`differences: NONE`). Spend: **zero tokens**. The 89-page FY2025 filing was therefore
  never opened, and neither was the 191-page 2023 one.
- **Did not touch `models/`.** `NonRecurringItem.confidence` still defaults to `"high"` at
  `models/financial_statements.py:28`. That is the same optimistic default this unit
  removed from the parser, one layer down, and the assignment says to stop and say so.
  **Finding 1.**
- **Did not touch `tests/`.** Five dev scripts under `tests/` call `normalize_financials`
  with the raw Pass 2 list and so bypass the partition. **Finding 2.**
- **Did not touch the other half of backlog item 36.** There is still no confidence field
  outside `NonRecurringItem`, so the 10,443 / 11,116 total-debt disagreement remains
  inexpressible. Out of scope, and an LLM-boundary change is an escalation.
- **Did not fix backlog item 25**, `analysis/normalizer.py:167-170` — an adjustment whose
  year matches no statement is silently discarded. **I saw it in the file I was editing.**
- **Did not touch `ingestion/claude_extractor.py` beyond `_parse_nri_response`.** The
  `.get("source", "")` on the next line, the ~30 other zero-defaults, the D&A subtraction
  (item 10) and the blanket `except Exception` (item 8) are all still there.
- **Did not touch backlog items 1, 2, 5, 6, 7, 8, 10, 26, 29, 31, 32, 37, 38.**

## Findings for the orchestrator

1. **`models/financial_statements.py:28` still defaults `confidence` to `"high"`.** This
   unit closed the parser's optimistic default and the normalizer now stops on an
   unrecognised tag — but any code that constructs a `NonRecurringItem` in Python without
   naming a confidence still gets `"high"` silently, and `partition_by_confidence` will
   apply it. The five dev scripts in `tests/` and any future caller are in that position.
   The fix is to make the field required (no default), which is a `models/` change with a
   blast radius across `tests/` — **one unit, `models/` plus a tester**. It is the last
   place in the chain where an absent confidence becomes the strongest reading.

2. **Five scripts under `tests/` call `normalize_financials` with the unpartitioned
   list** — `test_e2e_abbv.py:136`, `test_e2e_abbv_3years.py:115`,
   `test_e2e_googl_3years.py:130`, `test_e2e_lly.py:136`, `_run_lly_dcf.py:21`. They
   therefore still apply `low`-confidence items, and they are the scripts a reader is most
   likely to run against a real filing. `tests/` is not mine. One tester unit adds the
   partition to all five and pins the CLI's excluded block.

3. **`source` has the same shape `confidence` had.** `models/financial_statements.py:29`
   defaults it to `""` and `ingestion/claude_extractor.py` reads it with
   `.get("source", "")`, so "the model cited no note" and "the parser dropped it" are the
   same empty string. It matters more now than it did yesterday: the cited source is what
   lets a reader reverse an exclusion by hand, and rule 4 wants the figure traceable to a
   page. The displayed `(none cited)` makes the absence visible but cannot say which of
   the two it is.

4. **The run-to-run variance measurement is still owed, and is now cheap to do.** One unit
   that extracts the same filing three times and diffs the Pass 2 lists would settle
   whether low-confidence items are disproportionately the ones that vary — the claim this
   assignment correctly refused to let me assert. It costs three extractions, and the
   content-keyed cache means it cannot be faked by a cache hit.

5. **The 20 Sep LHX extraction is gone, and with it the only real `low`-confidence item
   this repository has ever produced.** Neither cache file on disk contains one
   (`cache/.cache_lhx_extraction.pkl` disassembled with `pickletools.genops`, without
   unpickling it: `has low: False`). That is why criterion 7's real measurement is a null
   result and the 13.4% figure is a counterfactual. A unit that keeps the raw Pass 2 JSON
   beside the pickle — not just the parsed objects — would make this kind of question
   answerable after the fact.
