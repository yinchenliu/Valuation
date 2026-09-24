---
agent: programmer
assignment: P7-low-confidence
round: 2
status: complete
files_touched: [ingestion/claude_extractor.py, analysis/normalizer.py]
verdict: —
---

# P7-low-confidence round 2 — the missing-key default is closed, and the $63.57 counterfactual is withdrawn

> Opened before the first command. Filled as each result landed.

## The correction first, because it is owed to the user

**The `$63.57` / `13.4%` figure in my round-1 entry is WITHDRAWN. It is not a
measurement, it is not an upper bound, and it should not be quoted.** It was computed by
grafting a non-recurring item recorded from the **FY2025** L3Harris 10-K onto the
**FY2024** extraction in `./cache`, which is a different document, and the FY2024
extraction already carries part of the same fiscal-2023 charge, so the graft
double-counted. Both defects are the reviewer's F2 and both are correct.

**I am withdrawing rather than redoing**, and the next section shows by execution why it
cannot be redone from the data on disk. **What stands unchanged is criterion 7's actual
measurement**: on the only L3Harris extraction that exists on disk, the user's decision
costs **$0.00** — `$411.39` with the exclusion and `$411.39` without it, because that
extraction contains no `low` item. That number was reproduced independently by the
reviewer and is not affected by F2.

## What I did

Two parser defaults, both on lines this unit rewrote, now stop and name their field:
`data.get("non_recurring_items", [])` (**F1**) and `item.get("source", "")` (**F3**). In
each case an **explicit** empty value is still accepted and an **absent key** stops, because
in both pairs the two mean opposite things and nothing downstream can recover the
difference. I also corrected the one place in code that cites the 1,140M item — the
`partition_by_confidence` docstring — to name the FY2025 filing it came from, so the wrong
provenance from my round-1 entry does not survive in the source. No other file changed;
the four gates are unchanged as sets and the suite is still `1 failed, 145 passed`.

**Zero tokens. No extraction, no network, no model call.** Every measurement below comes
from `./cache`, from a stubbed `_call_llm`, or from the test suite.

## Findings answered, by number

### F1 · `major` · `data.get("non_recurring_items", [])` — **fixed**

`ingestion/claude_extractor.py`, `_parse_nri_response`. An absent key now raises, naming
the field and listing the keys that did arrive; `"non_recurring_items": []` is accepted,
because the prompt asks for exactly that when the model finds nothing (`:297`).

I accept the finding without dispute. The reviewer's reading of the cost is right and is
specific to this unit: the CLI's `None. Every item the model identified was applied.` and
the page's silence are both **positive statements** about a parse. On the absent-key path
they were statements about a reply nobody read.

```
$ .venv/Scripts/python.exe c:/tmp/p7r2/parser.py
=== criterion 10: the 'non_recurring_items' key is absent ===
'{}' (empty object)          RAISES ValueError: Pass 2 returned no 'non_recurring_items'
                             field. ... Keys returned: []
a reply with other keys only RAISES ValueError: ... Keys returned: ['note', 'ticker']
the Pass 1 shape by mistake  RAISES ValueError: ... Keys returned: ['income_statements']

=== criterion 11: the key is present and explicitly empty ===
explicit []                  RETURNS 0 item(s): []

=== the happy path still parses ===
one complete item            RETURNS 1 item(s): [NonRecurringItem(year=2024, ...)]
```

**The stop is a stop, not a cosmetic raise.** `_run_nri_pass` catches
`(json.JSONDecodeError, KeyError)` on the first parse and, on the retry, `Exception` →
`return []`. If the new `ValueError` were caught by either, F1 would have been closed in
appearance only, so I exercised the wrapper with `_call_llm` stubbed — no network, no key,
no PDF:

```
$ .venv/Scripts/python.exe c:/tmp/p7r2/pass2_propagates.py
--- no 'non_recurring_items' key ---
  _run_nri_pass RAISES ValueError: Pass 2 returned no 'non_recurring_items' field...
  LLM calls made: 1  (a retry would make 2)
--- explicit empty list ---
  _run_nri_pass RETURNS []; LLM calls made: 1
```

One call, no retry, no `return []`. The run stops.

### F3 · `minor` · `source=item.get("source", "")` — **fixed, not argued away**

The orchestrator's amendment asked me to fix the second `.get` in the hunk or say why it
is sound. **It is not sound, and I have fixed it** rather than defend it.

Rule 3's test is *"for every value a function reads, ask: if this were missing, what
happens?"* — it is not limited to values that reach a number. And the cited source is
precisely the value this unit exists to deliver: rule 4 wants a figure walked back to a
page, and an excluded item's whole use to a reader is the note they must re-read to apply
it by hand. `""` from the model and `""` from a dropped key were the same bytes.

```
=== F3: 'source' absent vs explicitly empty ===
item with no 'source' key    RAISES ValueError: Pass 2 returned a non-recurring item with
                             no 'source' field: year 2024, 'a charge'. ...
item with source=''          RETURNS 1 item(s): [NonRecurringItem(..., source='')]
```

**This makes the existing `(none cited)` render honest.** Before, it meant "either the
model cited nothing or the key was lost". Now it can only mean the first. I did not touch
the rendering in `cli.py` or the template, and I did not touch
`models/financial_statements.py:29`'s `source: str = ""` — that default is the reviewer's
F3/F4 unit and is out of my scope.

### F2 · `major` · the counterfactual — **withdrawn, with the reason measured**

I accept both defects without dispute and I checked the reviewer's citation myself.
`docs/9-reference/refactor-backlog.md:612` states it in the repository's own words:
*"The **FY2025** L3Harris 10-K was extracted twice"*, and it is that pair of runs whose
1,140M item is item 36's subject. The cache entry I measured is the FY2024 PDF:

```
$ .venv/Scripts/python.exe c:/tmp/p7r2/inspect_cache.py
cache key: ExtractionKey(ticker='LHX', ..., inputs=(InputFingerprint(...
  path='...\10K_filings\LHX\L3Harris Technologies Inc._10-K_2024_English.pdf',
  sha256='7d7ca6485a7eaf8eb698bcea6e081e8c6a70ebc6318852b8ff3d4ca92fa4ae15'),))
```

My round-1 sentence *"it was in the 20 Sep extraction of this same filing"* is **wrong**.
Two documents.

**Why I am withdrawing rather than de-duplicating.** The reviewer offered "drop the +115M
item from run C before grafting" as one repair. I checked whether that would produce a
defensible number, and it would not. The fiscal-2023 items the FY2024 extraction actually
contains:

```
  2023 +     30  cost_of_revenue          high  acquisition_costs   inventory fair-value step-up
  2023 +    296  other_operating_expense  high  impairment          goodwill, Commercial Aviation
  2023 +     78  other_operating_expense  high  impairment          other asset impairments
  2023 +    115  sga                      high  restructuring       LHX NeXt implementation costs in G&A
  2023 +    174  sga                      high  acquisition_costs   merger/acquisition/divestiture expenses
  2023 +     51  sga                      high  gain_loss_asset_sale business divestiture losses, net
  net adjusted_impact 2023: +744
```

The grafted item is `+1,140 sga` described as *"LHX NeXt implementation costs **and other
charges in G&A** (components not separately disclosed for 2023)"*. **Three** of the six
items above are `sga` charges in G&A for fiscal 2023 — 115 + 174 + 51 = **340** — and the
aggregate's own description says its components are not disclosed. So subtracting the 115
would still leave an unknown overlap with the other two, and the result would still splice
one document's coarse aggregate into another document's itemised reading. There is no
arithmetic on disk that resolves it, so any number I produced would be a guess wearing a
subtraction.

**Could I redo it on the right filing? Not without spending tokens.** No cache entry
anywhere on disk holds a `low`-confidence item, so the FY2025 Pass 2 list cannot be
recovered — only re-extracted. Checked without unpickling anything, by walking the opcode
stream:

```
$ .venv/Scripts/python.exe c:/tmp/p7r2/scan_caches.py
.cache_abbv_extraction.pkl        {'high': 40, 'medium': 3, 'low': 0}   exact 'low': 0
.cache_lhx_extraction.pkl         {'high': 22, 'medium': 1, 'low': 0}   exact 'low': 0
.cache_lhx_extraction_inputs.pkl  {'high': 13, 'medium': 2, 'low': 0}   exact 'low': 0
```

The FY2025 PDF is on disk (`10K_filings/LHX/L3Harris Technologies Inc._10-K_2025_English.pdf`)
but its extraction is not, and a correct A/B would need Pass 1 **and** Pass 2 over it. The
amendment says spend no tokens, so I did not.

**So: the magnitude of what one `low` item costs cannot be sized from the data on disk.**
The direction is not in doubt — withholding an add-back lowers adjusted EBIT, lowers the
margin, and lowers the implied price — but the repository holds no run in which that can
be measured. **Every number in my round-1 "COUNTERFACTUAL" block — `$474.96`, `$63.57`,
`13.4%`, run C's adjusted EBIT `3,310` — is withdrawn.** The criterion-4 CLI block pasted
in round 1 remains valid as a demonstration that the *output renders*, which is what
criterion 4 asked; it is not evidence of any magnitude, and its `$411.47` headline is the
same constructed input.

**What replaces it in the record:** on the L3Harris FY2024 filing, the only one whose
extraction exists, the decision costs **$0.00** and withholds **nothing** — 13 items
`high`, 2 `medium`, 0 `low`. That is criterion 7's honest answer, and it was already
reproduced independently by the reviewer from the same cache.

### F4, F5, F6, F7 — acknowledged, not touched

Out of my Files in scope and recorded by the orchestrator as following units. I confirm I
widened into none of them:

- **F4** `models/financial_statements.py:28` `confidence: str = "high"` — still there;
  `git status --short -- models/` is empty.
- **F5** the five dev scripts under `tests/` — `git status --short -- tests/` is empty.
- **F6** the page renders nothing when nothing is excluded; the CLI says so in words. I
  agree it is my own reason applied unevenly. `templates/valuation_result.html` is
  unchanged this round because the finding is a `note` and the amendment did not ask for
  it; **it is a real asymmetry and I am leaving it named here** so it is not lost.
- **F7** the stale comment at `api/routes_valuation.py:292-294` — unchanged this round,
  same reason. Its line references (`:31`, `:102`, `:148-154`) are now `:38`, `:115`,
  `:194-195`.

## Done-criteria

The nine from round 1 are **unchanged and re-verified** where my edit could have moved them
(8 and 9 below). Criteria 1-7 are untouched by this round: I changed no code that they
exercise, and the amendment records them as verified by the reviewer's own execution.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 10 | a Pass 2 reply with **no** `non_recurring_items` key **stops**, naming it | **pass** | `c:/tmp/p7r2/parser.py`: three shapes of reply without the key all raise `ValueError` naming the field and listing the keys that arrived. `c:/tmp/p7r2/pass2_propagates.py`: it propagates out of `_run_nri_pass` after **one** LLM call — not swallowed by the `(JSONDecodeError, KeyError)` catch, not converted to `[]` by the retry's `except Exception` |
| 11 | a reply with an **explicit empty list** is accepted | **pass** | same script: `explicit [] -> RETURNS 0 item(s): []`; through the wrapper, `_run_nri_pass RETURNS []` and prints `[Pass 2] No non-recurring items identified` |
| 12 | the $63.57 figure is withdrawn, or replaced by a correct one | **pass — withdrawn** | the first section of this entry, and the F2 section. The reason is measured, not asserted: `c:/tmp/p7r2/inspect_cache.py` shows the FY2024 sha and the three overlapping fiscal-2023 `sga` items; `c:/tmp/p7r2/scan_caches.py` shows no `low` item in any cache on disk |
| — | F3's `source` absence stops; an explicit `""` is accepted | **pass** | `c:/tmp/p7r2/parser.py`, the F3 block |
| 8 | no existing assertion changed meaning | **pass** | `.venv/Scripts/python.exe -m pytest -q` → **`1 failed, 145 passed`**, the failure being the single nodeid `tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`. `git status --short -- tests/` empty — no test edited |
| 9 | lint 5, types set-diffed, census 116, `GET /` 200 | **pass** | all four re-measured below against a `git archive 54c5af8` export |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| An absent `non_recurring_items` raises; an explicit `[]` is accepted | Rule 3, and the prompt at `claude_extractor.py:297` asks for `{"non_recurring_items": []}` when nothing is found, so the explicit form is a real answer with a real meaning | Raising on `[]` too would stop every clean filing that genuinely has no one-time items. The distinction the rule is about is **absence**, not emptiness |
| The stop lists `sorted(data)` — the keys that did arrive | A reader debugging this needs to know whether the model returned the Pass 1 shape, a prose apology, or a typo'd key | `KeyError('non_recurring_items')` names the field but says nothing about what came instead |
| The `ValueError` is deliberately **not** added to the retry's `except` clause | The retry path ends in `except Exception: ... return []` (`:958`). Routing this stop into it would convert "nothing was read" back into "nothing was found" — F1 rebuilt one layer out | Repairing malformed JSON is what that retry is for; a reply with no Pass 2 field at all is not malformed JSON, it is the wrong answer |
| An absent `source` raises; an explicit `""` is accepted | Rule 3 binds every value a function reads, and rule 4 makes the citation the thing that lets a reader walk the figure back. The excluded block's entire purpose is that citation | I considered defending it as "it reaches no number". It does not reach a number, and it is still the one field a reader of an excluded item must have. The orchestrator asked for a fix or a defence; the defence does not survive rule 4 |
| `(none cited)` was left exactly as it renders | It is now unambiguous — it can only mean the model returned an empty citation, because a missing key no longer reaches it | Changing the wording as well would have edited `cli.py` and the template for no behavioural gain |
| `item.get('year')` / `item.get('description')` **inside the two raise messages** are kept | They are diagnostics about an item already known to be malformed, and they take no fallback value — an absent key renders `None`. Using `item["year"]` there would raise a `KeyError` **while building the message**, hiding the field that is actually missing | This is the one shape of `.get` in the hunk that survives, and it is named here rather than left for a reviewer to find |
| The `partition_by_confidence` docstring now names the **FY2025** filing | `docs/9-reference/refactor-backlog.md:612` records that filing and that pair of runs. My round-1 entry put the wrong provenance in the journal; leaving the code's only citation of the item unattributed would let the error re-form | It is a docstring inside the function this unit added — behaviour-neutral, in scope, and verified by the suite re-run. It also now says the item is a **recorded run, not a measurement** |
| The counterfactual is withdrawn, not repaired | Measured above: the graft's overlap with three fiscal-2023 `sga` items is undisclosed by the item's own description, and no cache on disk holds a `low` item to redo it on the right filing | A de-duplicated figure would still cross two documents and still need three caveats. The amendment says withdrawing is a complete answer, and it is the honest one |

**No code change in this round was made to reach a target number.** Both changes remove a
value the code was inventing. The only figure this round moves is the one I took **out** of
circulation.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `non_recurring_items` key, Pass 2 reply | **stops**, naming the field and listing the keys that arrived | `c:/tmp/p7r2/parser.py`; propagation out of `_run_nri_pass` proved in `c:/tmp/p7r2/pass2_propagates.py` |
| `confidence` key, Pass 2 item | **stops**, naming the year and the description | `c:/tmp/p7r2/parser.py`, last block — unchanged from round 1 |
| `source` key, Pass 2 item | **stops**, naming the year and the description | `c:/tmp/p7r2/parser.py`, F3 block. **Changed this round** |
| `year`, `description`, `amount`, `line_item`, `direction`, `category` on a Pass 2 item | **stop** — plain `item["…"]` subscripts, raising `KeyError` | `ingestion/claude_extractor.py`, unchanged; the `KeyError` is caught by the repair retry at `:945`, which is pre-existing and not mine |
| `item.get('year')` / `item.get('description')` inside the two raise messages | **does not stop — renders `None`** | **Deliberate, and a "defaults to" row I am writing against myself.** They are message diagnostics about an already-failing item; a `KeyError` raised while formatting would mask the missing field the message exists to report. They reach no figure |
| `NonRecurringItem.confidence` when constructed in Python without one | **does not stop — `"high"`** | `models/financial_statements.py:28`. Reviewer's F4, out of scope, unchanged |
| `NonRecurringItem.source` when constructed in Python without one | **does not stop — `""`** | `models/financial_statements.py:29`. Same unit as F4. The **parser** path is now closed; the dataclass default is not |
| `item.year` matching no statement | **does not stop — the adjustment is discarded** | Backlog item 25, `analysis/normalizer.py`. I saw it again in the file I was editing and left it |

No new default was added. The census grep over this round's added lines:

```
$ git diff -U0 | grep "^+" | grep -E "if [^)]+ else 0(\.0)?\b|\bor +(0|0\.0)\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0|\*\*kwargs|getattr\("
exit=1        (no output)
```

## Rules 1, 2, 4, 5, 6

- **Rule 1.** No number in this round's diff came from a model. **No model was called at
  all** — the only `_call_llm` in evidence is a stub in `c:/tmp/`. `docs/2-rules/llm-boundary.md`
  re-read, as required for an `ingestion/` change: no prompt, no schema field and no client
  was touched; the change **removes** two defaults and adds two stops.
- **Rule 2.** No new function, no new signature, no `**kwargs`, no `getattr`, no dispatch
  on data. Two `if … not in …: raise` guards and one subscript.
- **Rule 4.** Improved. `source` is the link from a withheld item to the note it came from,
  and it can no longer arrive silently empty.
- **Rule 5.** No new data source. Nothing was fetched.
- **Rule 6.** Unchanged from round 1 — the exclusion is stated beside the headline figure in
  both outputs with the date of the decision. **And one assumption came off the record this
  round:** the withdrawn `13.4%` was a constructed figure presented as a quantity, and it is
  now labelled as withdrawn rather than as an approximation.

## Measurements

| Gate | Baseline (`54c5af8`, re-exported this round) | After | Verdict |
|---|---|---|---|
| Tests | `1 failed, 145 passed` | **`1 failed, 145 passed`** | unchanged; the same single nodeid, `test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` |
| Lint | 5, all `BLE001` | **5** | `diff` of the concise output with line/column stripped → **`RUFF SETS IDENTICAL`** |
| Types | 14 errors in 4 files | **14 in 4 files** | `comm -23` and `comm -13` against the baseline export, line numbers stripped → **both empty** |
| Rule-3 census | 116 | **116** | same grep, run in both trees |
| `GET /` | 200 | **200** | `GET / -> 200 1648 bytes` |

Commands, in full:

```
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check . --output-format concise
.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports
grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" \
  --include=*.py models analysis api ingestion | wc -l
```

Diff against `HEAD`: **5 files, +319 / −27**, exactly the Files in scope — round 1 recorded
+284 / −27, so this round is **+35 / −0** across `ingestion/claude_extractor.py` and
`analysis/normalizer.py`.
`git status --short -- models/ tests/ docs/ STATUS.md .agent/journal/INDEX.md` is **empty**.
The three files in `cache/` keep their original sizes and mtimes (`ls -la cache/`): every
cache access this round was a read.

Figures this unit moves, restated:

| Figure | Before | After | Input |
|---|---|---|---|
| LHX FY2024 implied share price | $411.39 | **$411.39** | the FY2024 cache entry, 15 items, 13 `high` + 2 `medium`, **0 `low`** — measured |
| the effect of one `low` item on a share price | *(round 1 claimed $63.57 / 13.4%)* | **withdrawn — not measurable from data on disk** | see F2 |

Scratch, all outside the repository: `c:/tmp/p7r2/{parser,pass2_propagates,inspect_cache,
scan_caches}.py`, `c:/tmp/p7r2/{mypy_base,mypy_head,ruff_base,ruff_head}.txt`,
`c:/tmp/p7r2/base/` (the `54c5af8` export). Nothing was written into the repository and no
cache file was read destructively or overwritten.

## What I did not do

- **Did not run an extraction.** Spend: **zero tokens**, as the amendment required. That is
  also the reason F2 is a withdrawal rather than a corrected measurement.
- **Did not touch `models/`** — F4's `confidence: str = "high"` and `source: str = ""` are
  both still at `models/financial_statements.py:28-29`.
- **Did not touch `tests/`** — F5's five dev scripts still pass the unpartitioned list.
- **Did not change `templates/valuation_result.html` or `cli.py`** this round. F6's
  asymmetry (the page prints nothing on an empty excluded list; the CLI prints a sentence)
  is unaddressed and is a `note`.
- **Did not update the stale comment at `api/routes_valuation.py:292-294`** (F7).
- **Did not fix backlog item 25** — the adjustment whose year matches no statement. Seen
  again, in the file I edited.
- **Did not touch backlog items 1, 2, 5, 6, 7, 8, 10, 26, 29, 31, 32, 36's schema half, 37, 38.**

## Findings for the orchestrator

1. **The types gate has two different commands and they disagree.** The harness note in my
   prompt says `mypy models analysis ingestion api`, which reports **18 errors in 6 files**;
   `docs/8-build/environment.md:148` specifies
   `mypy models analysis ingestion api config.py app.py --ignore-missing-imports`, which
   reports **14 in 4** and is the number every P6/P7 entry has quoted. I used the documented
   one. Two agents measuring "the types gate" with the two commands will report different
   counts and one will look like a regression. **The environment doc's own expected value is
   also stale: it records `33 errors in 4 files`, and the tree has held 14 since at least
   `54c5af8`.** One small docs unit.

2. **`extract_non_recurring_items`' retry path can still turn a stop into silence.**
   `ingestion/claude_extractor.py:957-959` is `except Exception: … return []`. It is only
   reachable after a first-attempt `JSONDecodeError`/`KeyError`, so the three stops this
   unit added bypass it — but any future stop added inside `_parse_nri_response` that the
   first attempt routes into the retry would be swallowed and the run would continue with
   "no non-recurring items found". That is backlog item 8 sitting directly under this unit's
   subject, and it is worth pulling forward.

3. **Nothing on disk records what an extraction actually returned.** The FY2025 Pass 2 list
   — the only one that ever contained a `low` item — exists nowhere but in journal prose,
   which is why F2 ends in a withdrawal rather than a measurement. A unit that writes the
   raw Pass 2 JSON beside the pickle would make "what did the model say last time" an
   answerable question for **zero** tokens. Round 1 raised this as finding 5; this round it
   is what blocked a correction the user is owed.

4. **The five dev scripts (F5) now have a second reason to be fixed.** They construct
   `NonRecurringItem`s and call `normalize_financials` directly, so they bypass both the
   partition **and** the parser stops this unit added. Whatever the tester unit does to
   them, the `models/` default (F4) has to land with it or the scripts will keep silently
   supplying `confidence="high"` and `source=""`.

5. **The withdrawal needs to reach wherever `$63.57` was reported.** The amendment says the
   figure was given to the user before this review ran. My entry withdraws it, and
   `analysis/normalizer.py`'s docstring no longer carries the wrong provenance, but the
   backlog and `STATUS.md` are the orchestrator's to check — I did not read them for the
   figure and I cannot write them.
