---
id: P8a-statements-data
phase: 8 — show the chain
agent: programmer
depends_on: []
---

# Carry the parsed statements and the applied adjustments into both route contexts

## Objective

`api/routes_valuation.py:38` caches a 2-tuple: the **normalised** statements and the
**excluded** non-recurring items. The raw pre-adjustment statements and the **applied**
items are local variables in `assumptions_page` and are discarded when it returns.
`run_valuation` then reads that 2-tuple at `:195`.

So the result page can say what was withheld and cannot say what was applied, and
neither page can show a GAAP-to-non-GAAP reconciliation, because the raw statements no
longer exist by the time a template runs. That is the rule 4 gap named in
`docs/2-rules/rules.md:92`.

**This unit changes no number and renders nothing new.** It makes the four values
reachable from both route contexts, under named fields. `P8b-statements-ui` renders
them. When this unit is done, a `TestClient` call can read every one of the new context
keys off the response, and every figure already on both pages is byte-identical to
before.

## What is already true — verify, do not redo

Measured at `35be956` on 2026-09-25. If any of these disagrees when you run it, **stop
and report the disagreement** rather than editing around it.

| Fact | Command |
|---|---|
| 145 passed | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 5 lint errors, every one `BLE001` | `.venv/Scripts/python.exe -m ruff check .` |
| 14 type errors in 4 files | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` |
| `GET /` returns 200 | `.venv/Scripts/python.exe -c "from starlette.testclient import TestClient; import app; print(TestClient(app.app, raise_server_exceptions=False).get('/').status_code)"` |

`normalize_financials` (`analysis/normalizer.py:245`) returns a **new**
`FinancialStatements` through `dataclasses.replace`. It does not mutate its argument. So
the raw statements still exist at `assumptions_page:114` and at `run_valuation:205`; the
routes simply drop the reference. Verify this before you write anything that copies.

## What to do

1. **Define one frozen dataclass to hold a cached extraction, in this file.** Four
   named fields, each typed. Rule 2: one named thing with a fixed, typed signature, not
   a 4-tuple whose meaning is a position.

   ```
   raw_financials: FinancialStatements        # as extracted, before any adjustment
   normalised_financials: FinancialStatements # after the applied items land
   applied_items: list[NonRecurringItem]      # high and medium confidence
   excluded_items: list[NonRecurringItem]     # low confidence, never applied
   ```

   Name it `CachedExtraction`. Retype `_extraction_cache` to
   `dict[str, CachedExtraction]`. **Done-criterion 1 greps for the class definition.**

2. **Write all four fields at `assumptions_page`.** The route already computes each of
   them at `:113-114`. Keep the existing order: partition first, then normalise with the
   applied half only. The decision belongs to `analysis/` (rule 1), and
   `normalize_financials` keeps the signature its tests were written against.

3. **Read all four fields at `run_valuation`, on both branches.** The cache-hit branch
   at `:195` and the cache-miss fallback at `:198-205` must both produce the same four
   values. Two branches producing different values is how a page reports one exclusion
   and computes with another.

   **Leave the `.pop()` as a `.pop()`.** That is backlog item 5 and it is not this
   unit's. See "Backlog items this unit is NOT fixing".

4. **Add a historical FCFF row per extracted year, to both route contexts.** Call
   `calculate_fcff_historical(income_statement, cash_flow)` from `analysis/fcff.py:47`.
   Build it from the **normalised** statements, because that is what every other figure
   on the page is built from.

   **A year whose income statement or cash flow statement is missing is not dropped.**
   `cli.py:721-722` drops it with a bare `continue`, and a reader cannot tell a dropped
   year from a year that was never extracted. Carry the year through with the rows
   marked absent, so the template can print the words. Use an explicit per-year record
   with a named field saying whether the FCFF was computable — **never a
   `HistoricalFCFF` with zeros in it.** Rule 3: a zero that means "we do not know" and a
   zero that means "zero" are the same bytes.

5. **WITHDRAWN AT ROUND 2. This step was wrong.** It mandated exactly two sentences,
   and two sentences cannot state this provenance truthfully. See
   "Round 2 — the corrected step 5" at the end of this file, and do that instead.

6. **Add the raw and normalised statements, the applied items and the excluded items to
   both `TemplateResponse` context dicts.** Use these exact key names, because
   `P8b-statements-ui` is written against them:

   | Key | Value |
   |---|---|
   | `raw_financials` | `FinancialStatements`, pre-adjustment |
   | `financials` | `FinancialStatements`, post-adjustment |
   | `applied_non_recurring` | `list[NonRecurringItem]` |
   | `excluded_non_recurring` | `list[NonRecurringItem]` — **already present on the result page; keep the name** |
   | `historical_fcff` | the per-year records from step 4 |
   | `assumption_sources` | the dict from step 5 |

7. **Set every one of the six keys on the error branch too**, at `:319-333`. Empty
   lists and `None`, never absent. An undefined name in a Jinja context renders as
   nothing on the success path as readily as on the error path, which is how a template
   silently shows an empty table instead of failing.

8. **Keep the starlette 1.6.0 call signature**: `TemplateResponse(request, name,
   context)`. The removed `(name, context)` form made this application serve HTTP 500 on
   every page for the life of the repository, until `622262b`. `STATUS.md` section 1b
   has the record.

## Files in scope

**Round 1 allowed one file. Round 2 allows three.** The two additions are forced by
finding F1; see "Round 2" at the end of this file.

- `api/routes_valuation.py`
- `analysis/projector.py` — **added at round 2.** Only to record, per ratio, which of
  three things produced it.
- `models/valuation.py` — **added at round 2.** Only to hold the new provenance
  dataclass and its label constants, and the historical-FCFF year record moved out of
  `api/`.

**Nothing else.** Work outside this list is a review finding, even if the change is
good.

## Out of scope

- `templates/` — `P8b-statements-ui` owns every template change. **Do not add a row, a
  table or a block to any template in this unit.** This unit's output is invisible.
- `cli.py` — it already prints all seven blocks. It is the reference for *what* to show
  and **not** for how to build it. It holds three rule 3 sites; see "Known open items".
- `analysis/`, `models/`, `ingestion/` — no signature there needs to change. If you
  believe one does, stop and report it.
- `static/style.css` — `P8b-statements-ui` owns it.
- `tests/` — the tester writes it. Prove your criteria with inline
  `.venv/Scripts/python.exe -c "..."` commands and paste the output into your log entry.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the cache holds four named fields, not a tuple | 1 match each | `grep -n "class CachedExtraction" api/routes_valuation.py` and `grep -n "dict\[str, CachedExtraction\]" api/routes_valuation.py` |
| 2 | the test gate is unchanged | `145 passed` | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 3 | no new lint error | `Found 5 errors`, all `BLE001` | `.venv/Scripts/python.exe -m ruff check .` |
| 4 | no new type error | `Found 14 errors in 4 files` or fewer | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` |
| 5 | `GET /` still 200 | `200` | the TestClient command in "What is already true" |
| 6 | all six context keys are set on `GET /assumptions`, including on its error branch | 6 keys present | a `python -c` that monkeypatches `_extract_from_files` to return a two-year stub, calls the route through `TestClient`, and prints `sorted(captured_context)` — capture it by monkeypatching `templates.TemplateResponse` |
| 7 | all six keys are set on `POST /valuation`, on the success branch and the error branch | 6 keys present on both | the same technique, once per branch |
| 8 | **no number on either page moved** | identical implied share price | run the same stubbed inputs before and after your change; paste both share prices into the log entry |
| 9 | no new conditional zero or `.get` fallback entered the file | count does not rise | `grep -cE "if [^)]+ else 0(\.0)?\b\|\bor +0(\.0)?\b\|\.get\([^,]+, *0(\.0)?\)\|: *float *= *0\.0" api/routes_valuation.py` before and after |
| 10 | no `getattr` on a variable name | 0 matches | `grep -n "getattr" api/routes_valuation.py` |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md` — rule 2 (one named function, fixed typed signature; a lookup
  table may map a key to a number, never to behaviour), rule 3 (stop, never guess),
  rule 4 (line 92 states this unit's gap in as many words), rule 6 (an assumption is
  labelled).
- `docs/3-architecture/entry-points.md` — the two entry points, and the table at line 82
  showing where `cli.py` and `api/routes_valuation.py` duplicate each other.
- `docs/4-conventions/units-and-signs.md` — **read it before you touch any figure.**
  Every money value is in millions. Form values arrive as percentages and are divided by
  100 once, at the route boundary.
- `analysis/normalizer.py:94-147` — `partition_by_confidence`, and why the decision
  lives in `analysis/` rather than in `ingestion/`.
- `analysis/fcff.py:47` — `calculate_fcff_historical`, its signature and its formula.
- `STATUS.md` section 1b — the starlette signature, and why the outage was invisible.

## Known open items

- **`cli.py`'s print layer holds three rule 3 sites. Do not carry any of them across.**
  `:508` divides by revenue with a conditional zero. `:522-538` substitutes a blank
  string for a missing cash flow statement, seventeen times. `:593` divides by total
  assets with a conditional zero. Each turns "we have no data" into a figure that reads
  as a measurement.
- `derive_assumptions` (`analysis/projector.py:29`) returns a plain `dict` and records
  nothing about which values came from overrides. That is why step 5 builds the source
  labels in the route from the `overrides` object, rather than reading them back out of
  the returned dict. It is not a defect you are asked to fix.
- The provider label at `:295` is a re-derivation, not a record. It names who *would*
  read a filing now, not who read this one. That is a recorded limitation from
  `P2b-provider` review round 1, finding F3. **Do not fix it here**; fixing it means
  carrying the `ProviderResolution` in the cache, and while `CachedExtraction` is the
  right eventual home for it, adding a fifth field changes what this unit is and has no
  done-criterion.

## Backlog items this unit is NOT fixing

- **Item 5** — the module-global extraction cache, `pop`ped on read. This unit changes
  what the cache *holds*. It does not change that the cache is a module global, and it
  does not change `.pop()` to `[]`. Both are item 5 and both need a decision about
  multi-user behaviour that this unit does not have.
- **Item 7** — `cli.py` and `api/` duplicate the pipeline. This unit makes the route
  carry what the CLI already prints, which narrows the *output* gap and leaves the
  *orchestration* duplication exactly where it is. Phase 3 owns it.
- **Item 11** — `api/routes_valuation.py:261`, `balance_sheet` typed `BalanceSheet |
  None` against a `BalanceSheet` parameter. A live crash path, and one of the 14. Phase
  5 owns it. Criterion 4 asks only that you do not add a fifteenth.
- **Item 26** — `:198` branches on `":" in files`, a character every live path contains.
  Latent. You are editing the lines around it; leave the condition alone.
- **Item 29** — `POST /valuation` with no `files` runs an extraction on the empty
  string. Rule 3, and still open.
- **Item 6** — the five `x / 100 if x else None` conversions at `:216-220`. A deliberate
  `0` from the user is read as "not supplied". Phase 4 owns it. **This matters to the
  provenance label**: it must report what the code actually did, so a field the route
  converted to `None` reads as *not supplied*, even where the reader typed `0`. Do not
  repair the conversion to make the label truthful; report the behaviour as it is and
  say so in your log entry.

---

# Round 2 — the corrected step 5

**The code reviewer's finding F1 is upheld, and this assignment caused it.** Round 1's
step 5 mandated "exactly two sentences". Two sentences cannot state this provenance
truthfully. Answer every finding in
`.agent/journal/2026-09-25T1207-code_reviewer-p8a-statements-data.md` by number.

## The fact that forces the change

`analysis/projector.py:19` — `_historical_average([])` returns `0.0`. Lines 24-25 —
`_historical_cagr` returns `0.0` when a revenue is non-positive. Line 99 — an empty
`nwc_pcts` gives `0.0`.

So on a filing with income statements and no cash flow statements, `da_pct_revenue`,
`capex_pct_revenue` and `nwc_pct_revenue` all come back `0.0`, derived from nothing. The
reviewer proved this by execution. Round 1's code then labels all three `"derived from
the filing's history"`.

Worse, one render contradicts itself: `historical_fcff` reports the cash flow statement
was never extracted for those years, while `assumption_sources` says the D&A ratio came
from them.

**What follows.** By the time `derive_assumptions` returns `0.0`, the evidence is gone.
`da_pcts` is a local list and nothing outside the function can see whether it was empty.
A label computed in the route could only re-derive the condition at `:72`, which puts
one fact in two files — the shape of backlog item 7.

**So the provenance must be produced by the function that knows it.**

## What to do at round 2

### A. Move the two record types into `models/`

Answers the reviewer's F7. `HistoricalFCFFYear` is a model, and round 1 put it in `api/`
only because the scope allowed one file.

1. Move `HistoricalFCFFYear` from `api/routes_valuation.py` to `models/valuation.py`,
   unchanged. Import it back.

2. Add `AssumptionSource` to `models/valuation.py`, a frozen dataclass, every field
   required and none defaulted:

   ```
   origin: str              # exactly one of the three ORIGIN constants
   detail: str              # the sentence a reader sees
   observations: int        # filing-years that fed it; 0 when supplied or substituted
   ```

3. Add the label constants to `models/valuation.py`, beside
   `RISK_FREE_SOURCE_SUBSTITUTED` at `:25-38`, in **exactly that house style**: `Final`,
   a full sentence, and the word `SUBSTITUTED` in capitals on the substituted one. That
   block is the shape this repository already uses for a provenance label, and this
   scheme must not regress against it.

   Three origins, and no fourth:

   | Origin | When | The sentence must say |
   |---|---|---|
   | supplied | the reader filled the form field | who supplied it, and that it is still an assumption |
   | derived | at least one filing-year fed the average | **how many years**, taken from `observations` |
   | substituted | **no** filing-year fed it, so a default was used | `SUBSTITUTED`, the default value, and **"It is not a measurement."** |

### B. Record the origin inside `derive_assumptions`

4. `derive_assumptions` returns the same dict with **one new key**, `"sources"`, holding
   `dict[str, AssumptionSource]` under the same six literal keys as before.

   **Add a key. Change no existing key and no existing value.** `cli.py:733`,
   `project_fcffs:132-144` and `api/routes_valuation.py` all read this dict by name, and
   `cli.py` is out of scope. A new key breaks none of them. Criterion 14 measures it.

5. Count the observations where the list is built, not afterwards. `da_pcts`,
   `capex_pcts` and `nwc_pcts` each accumulate in a loop at `:68-73`, `:77-82` and
   `:92-97`. The length of that list **before** the average is taken is the observation
   count, and zero means substituted.

   For `operating_margin` and `tax_rate`, `_historical_average` drops zero values at
   `:18`, so the count is the length of the **non-zero** list, not of `years`. Get that
   number out of the helper rather than recomputing the filter at the call site.

6. **`_historical_cagr` returning `0.0` is a substitution too.** Its guard at `:24` fires
   on a non-positive revenue, and a 0% growth rate presented as measured is the same
   defect as a 0% D&A ratio presented as measured.

7. **The tax-rate clamp at `:65` is not a fourth origin.** When
   `max(0.0, min(tax_rate, 0.50))` moves the value, say so inside the `detail` sentence
   of whichever origin applies, and name both the pre-clamp figure and the band. A
   clamped figure reported as derived is a measurement the filing did not produce.

8. **Add no default to any new field**, and add no `= 0.0`. Backlog item 1 counts
   `models/`, and criterion 9's grep must not rise.

### C. Use it in the route

9. Delete `_SOURCE_SUPPLIED`, `_SOURCE_DERIVED`, `_assumption_sources` and
   `_all_derived_assumption_sources` from `api/routes_valuation.py`. The route reads
   `assumptions["sources"]` and passes it to the context under the unchanged key
   `assumption_sources`. **One home for the fact**, which also closes the reviewer's F6
   note about two dicts holding one thing.

10. `assumptions_page` already calls `derive_assumptions` at `:314`, so its six labels
    come from the same place. **Its failure and no-filing paths keep `{}`** — the
    reviewer confirmed that reasoning in F5. State the contract in a comment on the
    context key: **empty, or exactly six entries. Never a partial dict.**

11. **Move the `_historical_fcff_by_year` call on `assumptions_page` to after the
    `derive_assumptions` call.** The reviewer found (F3) that round 1 placed it at
    `:310`, before `derive_assumptions` at `:314`. `calculate_fcff_historical` raises on
    a NaN tax rate, so a NaN year now replaces the whole defaults form with an error
    page, where it previously rendered the fields. Calling it last means a year it
    rejects cannot remove a form the reader could otherwise have used. **This changes no
    number.**

## Done-criteria — round 2 adds five to the ten already passing

Re-run all ten from the table above. They must still pass. Then:

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 11 | a ratio with **no** filing data behind it is labelled substituted, not derived | `origin` is the substituted constant; the sentence holds `SUBSTITUTED` and `It is not a measurement.` | build a `FinancialStatements` with income statements and **no** cash flow statements; print the three cash-flow-fed labels |
| 12 | a ratio with filing data behind it names **how many years** | the integer equals the number of years that fed it, **counted by hand in your entry** | a two-year stub, both years complete; print `observations` and the sentence |
| 13 | the page cannot contradict itself | **see the corrected wording below** | assert it over both stubs in a `python -c`, and paste the output |

**Criterion 13 was wrong as first written, and the round-2 programmer caught it.** The
original wording asked that every ratio labelled derived have a computable
`historical_fcff` row. That fails against *correct* code: `analysis/projector.py:59` and
`:63` build `operating_margin` and `tax_rate` from income statements alone, while a
historical FCFF row needs the income statement **and** the cash flow statement. On a
filing with no cash flow statements both labels are rightly `derived` and every FCFF row
is rightly not computable.

**The corrected criterion.** Split the six ratios by which statement feeds each:

| Ratio | Fed by |
|---|---|
| `revenue_growth_rates`, `operating_margin`, `tax_rate` | the income statement only |
| `da_pct_revenue`, `capex_pct_revenue`, `nwc_pct_revenue` | the income statement **and** the cash flow statement |

A ratio labelled `derived` must have at least one year in which **the statements it
needs** were extracted. For the bottom three only, that condition is the same one
`historical_fcff` reports, so those three are the ones that may never disagree with the
FCFF table.

**The tester must use this wording, not the original.** A test written to the first
version goes red against correct code.
| 14 | **no existing assumption value moved** | all eight pre-existing keys identical | call `derive_assumptions` on one stub before and after; diff the dict with `"sources"` removed |
| 15 | one home for the labels | 0 matches for each deleted name | `grep -n "_SOURCE_SUPPLIED\|_SOURCE_DERIVED\|_all_derived_assumption_sources" api/routes_valuation.py` |

**Coverage will fall in `analysis/` and that is expected.** `STATUS.md` records 255 of
255 statements and 80 of 80 branches there. You cannot write `tests/`; the tester closes
the gap, as `P6b-wacc-fixture` did. **Do not add an unreachable guard, and do not
restructure code to hold a percentage.** Report the new uncovered lines in your entry.

## The three reviewer findings you must answer in words

- **F3.** The reviewer showed the `calculate_fcff_historical` stop is genuinely
  reachable: `json.loads` accepts a bare `NaN`, `ingestion/claude_extractor.py:605,721`
  parse with a plain `json.loads`, and a NaN revenue makes `ebt` NaN, which is truthy,
  so `effective_tax_rate` returns NaN. Step 11 is the fix for the placement half.
  Confirm the ordering change by execution.
- **F4.** The `"income statement"` branch is dead through `FinancialStatements.years`,
  but the `is None` check is required type narrowing — removing it adds a fifteenth mypy
  error. The reviewer's verdict is **leave it**. Do not delete it. Say in your entry
  whether you agree, with a citation.
- **F8.** The historical FCFF row is a hybrid: a normalised EBIT and tax rate against an
  unadjusted CFO. That is why 2024 reads `213.0967741935484` and not `212.842105`. It is
  correct, and `P8b-statements-ui` must head that table *post-adjustment*. Record the
  fact in your entry so that assignment can cite it.

## One thing to correct in your own round-1 entry

It says "The three mypy errors in this file"; there are four — `:138`, `:468`, `:477`,
`:478`. The error **set** is identical before and after, so criterion 4 is unaffected.
Correct the prose in your round-2 entry.
