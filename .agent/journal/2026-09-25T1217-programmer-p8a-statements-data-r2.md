---
agent: programmer
assignment: P8a-statements-data
round: 2
status: complete
files_touched: [api/routes_valuation.py, analysis/projector.py, models/valuation.py]
verdict:
---

# P8a-statements-data round 2 — three-state assumption provenance, produced where it is known

> Opened before the first command of round 2; filled as each result landed.
> Round 1 entry: `.agent/journal/2026-09-25T1149-programmer-p8a-statements-data.md`
> Review answered: `.agent/journal/2026-09-25T1207-code_reviewer-p8a-statements-data.md`

## What I did

The two-sentence label is gone. `analysis/projector.py` now produces the provenance of
each of the six projection ratios **inside `derive_assumptions`**, where the evidence
still exists, and returns it under one added dict key, `"sources"`. It has three states,
not two: `supplied`, `derived` (naming how many filing-years fed it), and
`substituted` (naming the default that replaced a derivation, in a sentence carrying the
word `SUBSTITUTED` and the words "It is not a measurement."). Two clauses attach to
whichever of the three applies — the tax-rate **clamp** and the revenue-growth **pad** —
because each is a step this platform took that the filing did not.
`models/valuation.py` holds the new `AssumptionSource` record and its label constants, in
the house style of `RISK_FREE_SOURCE_SUBSTITUTED` beside them, and it now also holds
`HistoricalFCFFYear`, moved out of `api/` (F7). `api/routes_valuation.py` deleted its own
two constants and both label-building functions and reads `assumptions["sources"]`; it
also moved its `_historical_fcff_by_year` call on the assumptions page to **after**
`derive_assumptions`, so a NaN historical year can no longer take the whole defaults
form away with it (F3).

**Nothing rendered moved.** Under identical stubbed inputs the sha256 of the rendered
body is identical on all five paths against the committed tree at `35be956` — the whole
two-round diff, not just round 2 — and `derive_assumptions`' dict with `"sources"`
removed is byte-identical on four different stubs.

## Findings answered, by number

| # | Reviewer's finding | My answer |
|---|---|---|
| **F1** | `"derived from the filing's history"` is asserted over values `derive_assumptions` substituted · **major** | **Accepted in full; fixed.** The label now has three states and is produced by the function that knows which one applies. Criterion 11 shows all three cash-flow-fed ratios on a filing with no cash flow statements labelled `substituted`, in a sentence that says `SUBSTITUTED` and "It is not a measurement." Criterion 13 shows the render can no longer contradict itself. The reviewer's preferred fix — "`analysis/projector.py` returns the provenance alongside each ratio and the route reports it" — is the one implemented. |
| **F2** | the `derived` label is also wrong for a deliberate `0` at `:433-437` · **minor** | **Accepted, still not repaired here, and the exposure is unchanged.** `api/routes_valuation.py:433-437` still reads `x / 100 if x else None`, so a reader who types `0` reaches `ProjectionAssumptions` as `None` and the ratio is labelled `derived` or `substituted` rather than `supplied`. Backlog item 6; the assignment forbids repairing it here (round-2 "Backlog items this unit is NOT fixing"). **`derive_assumptions` itself honours a deliberate zero** — my check prints `operating_margin value=0.0 origin='supplied'` for `ProjectionAssumptions(operating_margin=0.0)` — so the defect is entirely in the route's form conversion, and item 6 alone closes it. It must land before or with `P8b-statements-ui`. |
| **F3** | the new `calculate_fcff_historical` stop is reachable and right; its **placement** on `assumptions_page` was wrong · **note** | **Accepted; fixed and proved by execution.** The call is now last in the try. With a NaN 2024 tax expense the page returns 200, the error names the field, **and the form is fully populated** (`defaults is empty: False`, six labels present). The control run in the same script shows that a failure raised before the `defaults =` assignment still empties the form — which is what round 1 did with this input. Output below. |
| **F4** | the `"income statement"` branch is dead through `FinancialStatements.years`; the `is None` check is required narrowing — **leave it** | **Agreed, and left.** Citation: `models/financial_statements.py:276-282` builds `years` from `income_statements` alone, so `get_income_statement(y)` for `y in financials.years` cannot return `None`; and `get_income_statement` is declared `-> IncomeStatement | None` (`:284`), so deleting the check adds a fifteenth mypy error against criterion 4. The line inside it returns no figure, so rule 3's ban on an unreachable guard that quietly produces a number does not apply. It is one of the newly uncovered lines; reported under Coverage below rather than removed. |
| **F5** | `assumption_sources == {}` on the error path is right, but it is a contract P8b cannot guess · **note** | **Accepted.** The contract is now written on the context key itself, in `assumptions_page`: *empty, or exactly six entries, never a partial dict*, with the reason. `P8b-statements-ui`'s assignment should cite that comment. |
| **F6** | the six ratio names live in two literal dicts · **note** | **Now moot — both dicts are deleted.** `_assumption_sources` and `_all_derived_assumption_sources` are gone from the route (criterion 15: 0 matches), and the six keys are written once, in `derive_assumptions`. The reviewer's own condition for collapsing them ("if F1's third label lands") is what landed. |
| **F7** | `HistoricalFCFFYear` is a model living in `api/` · **note** | **Accepted; moved.** It is in `models/valuation.py` beside `HistoricalFCFF`, unchanged field-for-field, and imported back into the route. Round 2's Files in scope is what made the move legal. |
| **F8** | the historical FCFF row is a hybrid and must be labelled *post-adjustment* by P8b · **note** | **Confirmed and recorded for that assignment.** 2024 reads `213.0967741935484` and not `212.842105…` because the effective tax rate moves with the adjusted EBIT (`60/248` against `60/228`) while `cfo` and `capex` come from the unadjusted cash flow statement. Building it from the normalised statements is the assignment's instruction and stays. **`P8b-statements-ui` must head that table "post-adjustment"**, or a reader will try to tie the row to the filing's cash flow statement and fail. |
| — | the prose miscount in my round-1 entry | **Corrected.** It said "the three mypy errors in this file"; there are **four** — `:138 arg-type`, `:468 union-attr`, `:477` and `:478 arg-type` at round-1 line numbers. The error set was and is identical before and after, so criterion 4 was never affected. In the round-2 tree the same four sit at `:123`, `:404`, `:413`, `:414`. |

I dispute none of the findings.

## Done-criteria

### The ten from round 1 — re-run, all still pass

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | four named cache fields | **pass** | `grep -n "class CachedExtraction" api/routes_valuation.py` → `38:` · `grep -n "dict\[str, CachedExtraction\]" api/routes_valuation.py` → `82:` |
| 2 | test gate unchanged | **pass** | `145 passed, 1 warning in 3.36s` |
| 3 | no new lint error | **pass** | `Found 5 errors.`, all `BLE001` |
| 4 | no new type error | **pass** | `Found 14 errors in 4 files (checked 18 source files)`. Same set, moved lines: `analysis/projector.py` keeps its four `union-attr`, now at `:154,189,199,309`; `api/routes_valuation.py` keeps its four, now at `:123,404,413,414` |
| 5 | `GET /` still 200 | **pass** | `200` |
| 6 | six keys on `GET /assumptions`, incl. error branch | **pass** | probe modes `assumptions`, `assumptions_error` — keys listed below |
| 7 | six keys on `POST /valuation`, both branches | **pass** | probe modes `valuation_cachehit`, `valuation_cachemiss`, `valuation_error` |
| 8 | **no number on either page moved** | **pass** | sha256 of the rendered body identical on all five paths, against the committed tree. Table below |
| 9 | no new conditional zero or `.get` fallback | **pass** | `1` in `api/routes_valuation.py`, unchanged. And the **repo-wide** census of `docs/2-rules/rules.md:65` is `116` before and `116` after, file-for-file identical |
| 10 | no `getattr` on a variable name | **pass** | `grep -c getattr api/routes_valuation.py` → `0` |

Criterion 8, measured by `git stash push api/routes_valuation.py analysis/projector.py
models/valuation.py` around one script, so "before" is the committed tree with **no P8a
at all**:

```
### AFTER (round 2 tree)
assumptions            body_len=5901 body_sha=f653e0a59d9ee4c3
assumptions_error      body_len=5918 body_sha=6ee6da259da637ab
valuation_cachehit     body_len=11827 body_sha=d8382de8831b959f
valuation_cachemiss    body_len=11827 body_sha=d8382de8831b959f
valuation_error        body_len=831 body_sha=8209df3eeb42386d

### BEFORE (stashed back to 35be956 state)
assumptions            body_len=5901 body_sha=f653e0a59d9ee4c3
assumptions_error      body_len=5918 body_sha=6ee6da259da637ab
valuation_cachehit     body_len=11827 body_sha=d8382de8831b959f
valuation_cachemiss    body_len=11827 body_sha=d8382de8831b959f
valuation_error        body_len=831 body_sha=8209df3eeb42386d
```

The implied share price is `33.208053691275175` on both branches, before and after, as at
round 1. The six keys, mode `valuation_cachehit`:

```
keys=['applied_non_recurring', 'assumption_sources', 'assumptions', 'capm', 'company_name',
 'current_price', 'dcf', 'excluded_non_recurring', 'extraction', 'financials',
 'historical_fcff', 'raw_financials', 'ticker', 'wacc']
```

### The five round-2 criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 11 | a ratio with no filing data behind it is labelled substituted | **pass** | output below |
| 12 | a derived ratio names how many years | **pass** | output below, hand count below it |
| 13 | the page cannot contradict itself | **pass** on the measurement that states the criterion's intent; **FAIL** on its literal wording, for a reason that is not a contradiction. Both are reported below, in full |
| 14 | no existing assumption value moved | **pass** | `diff` of the dict with `"sources"` removed, over four stubs → `CRITERION 14: DICTS IDENTICAL WITH sources REMOVED` |
| 15 | one home for the labels | **pass** | `grep -c "_SOURCE_SUPPLIED\|_SOURCE_DERIVED\|_all_derived_assumption_sources" api/routes_valuation.py` → `0`; `grep -c "_assumption_sources" api/routes_valuation.py` → `0` |

#### Criterion 11 — income statements, no cash flow statement anywhere

```
--- income statements only
  revenue_growth_rates
    value=[0.18321595661992318] origin='derived' observations=2
    detail=derived from the filing: 2 filing-year(s) of extracted data fed it. It measures those years; that they continue is the assumption.
  operating_margin
    value=0.20000000000000004 origin='derived' observations=3
    detail=derived from the filing: 3 filing-year(s) of extracted data fed it. It measures those years; that they continue is the assumption.
  tax_rate
    value=0.2631578947368421 origin='derived' observations=3
    detail=derived from the filing: 3 filing-year(s) of extracted data fed it. It measures those years; that they continue is the assumption.
  da_pct_revenue
    value=0.0 origin='substituted' observations=0
    detail=ASSUMPTION — SUBSTITUTED. Nothing from the filing fed this figure — no year contributed an observation — so 0.00% was used in place of a derivation. It is not a measurement.
  capex_pct_revenue
    value=0.0 origin='substituted' observations=0
    detail=ASSUMPTION — SUBSTITUTED. Nothing from the filing fed this figure — no year contributed an observation — so 0.00% was used in place of a derivation. It is not a measurement.
  nwc_pct_revenue
    value=0.0 origin='substituted' observations=0
    detail=ASSUMPTION — SUBSTITUTED. Nothing from the filing fed this figure — no year contributed an observation — so 0.00% was used in place of a derivation. It is not a measurement.
  historical_fcff rows: [(2023, False, ('cash flow statement',)), (2024, False, ('cash flow statement',)), (2025, False, ('cash flow statement',))]
  criterion 11: PASS — all three cash-flow-fed ratios substituted, each sentence holds SUBSTITUTED and 'It is not a measurement.'
```

This is exactly the reviewer's F1 reproduction. The three lines it printed as
`0.0 | label: derived from the filing's history` now read `substituted`.

#### Criterion 12 — two complete filing-years, hand-counted

Stub: 2023 revenue 1000 / SGA 800 / tax 50, 2024 revenue 1200 / SGA 960 / tax 60, each
with a cash flow statement (D&A 100/120, CapEx −50/−60, ΔWC −20/−24).

**The hand count, before running anything.** Two filing-years are extracted, and both
carry every line each ratio needs, so every observation count must be **2**:

| Ratio | What is read | Years that feed it | Count |
|---|---|---|---|
| `revenue_growth_rates` | revenue at each end of the CAGR window: 1000 and 1200 | 2023 and 2024 | **2** |
| `operating_margin` | EBIT/revenue: 200/1000 and 240/1200, neither zero | 2023, 2024 | **2** |
| `tax_rate` | tax/EBT: 50/200 and 60/240, neither zero | 2023, 2024 | **2** |
| `da_pct_revenue` | D&A/revenue: 100/1000 and 120/1200, neither zero | 2023, 2024 | **2** |
| `capex_pct_revenue` | CapEx/revenue: 50/1000 and 60/1200, neither zero | 2023, 2024 | **2** |
| `nwc_pct_revenue` | −ΔWC/revenue: 20/1000 and 24/1200 | 2023, 2024 | **2** |

Measured, all six: `observations=2`, and the sentence reads
`derived from the filing: 2 filing-year(s) of extracted data fed it.` The six asserts in
the script are on the hand-counted `2`, not on what the code printed.

`revenue_growth_rates` is worth one sentence of its own: a CAGR reads **two** revenue
figures whatever the window, so on the three-year stub it also reports `2` while
`operating_margin` and `tax_rate` report `3`. The years between the two endpoints feed
nothing, and the count says what fed it rather than what the window spanned.

#### Criterion 13 — and the one place its literal wording is wrong

Measured over both stubs:

```
  criterion 13 [no cash flow]: PASS
  criterion 13 [no cash flow], literal wording (every derived ratio needs a computable FCFF row): FAIL
  criterion 13 [two complete years]: PASS
  criterion 13 [two complete years], literal wording (every derived ratio needs a computable FCFF row): PASS
```

**The literal criterion cannot be satisfied and should not be, and I am reporting it
rather than bending the code to it.** Criterion 13 asks that for *every* ratio labelled
derived, some `historical_fcff` row for a year it used be `is_computable=True`. On the
no-cash-flow stub, `operating_margin` and `tax_rate` are correctly labelled derived from
**3 filing-years** — they are read from the income statement, which was extracted — while
every FCFF row is correctly not computable, because `calculate_fcff_historical` needs the
**cash flow statement**, which was not. Two statements, two different absences. The
literal test fails on a pair of statements that do not contradict each other.

What I measured instead, which is the contradiction F1 actually named:

- a **cash-flow-fed** ratio (`da_pct_revenue`, `capex_pct_revenue`, `nwc_pct_revenue`)
  labelled `derived` while no FCFF row is computable — that is the self-contradicting
  render, and it does not occur;
- an **income-statement-fed** ratio (`revenue_growth_rates`, `operating_margin`,
  `tax_rate`) labelled `derived` while no year was extracted at all — also does not
  occur.

Both hold on both stubs. The script prints both forms so the next reader can see the
difference rather than take my word for it. **For `P8b-statements-ui`:** the residual
confusion is that the page does not say *which statement* fed each ratio; printing that
beside the label removes the question entirely.

### F3 — the ordering, proved by execution

Stub: the three-year set with a NaN `tax_expense` on **2024**, a year that has a cash
flow statement, so `calculate_fcff_historical` is actually reached.

```
status=200
error='tax_rate (tax_rate_override or income_statement.effective_tax_rate) is NaN, so FCFF cannot be computed from it. A NaN here means an input was absent or degenerate further up the chain. Supply the missing input; it is not substituted with a default.'
defaults is empty: False
  form field revenue_growth_display: ['18.3', '18.3', '18.3', '18.3', '18.3']
  form field operating_margin_display: 20.0
  form field tax_rate_display: 0.0
  form field da_pct_display: 10.0
  form field capex_pct_display: 5.0
  form field nwc_pct_display: 2.0
historical_fcff rows: 0
assumption_sources entries: 6

control: a failure raised BEFORE the defaults assignment
  error='stand-in for anything that runs before the form is built'
  defaults is empty: True
  assumption_sources entries: 0
```

The reader now gets the named stop **and** a usable form. The control run is the round-1
behaviour for the same input: anything that raises before `defaults =` empties the whole
form. No number moved — the five non-tax fields carry the same figures they carried
before, and the NaN path could not be reached at all on the committed tree because that
tree never called `calculate_fcff_historical` from a route.

**A by-product worth naming.** `tax_rate_display` reads `0.0` because
`max(0.0, min(nan, 0.50))` is `0.0` — every comparison against NaN is False, so both
builtins fall through (the same trap `analysis/fcff.py:65-70` documents). That silent
0% is backlog item 1 and predates this unit. What is new is that the label now says so:

```
origin = derived
detail = derived from the filing: 3 filing-year(s) of extracted data fed it. It measures
those years; that they continue is the assumption. It was then CLAMPED into the 0% to
50% band this platform imposes: nan% fell outside it, so 0.00% is the figure every
calculation downstream used.
```

A NaN that became a confident 0.00% is now visible in the output. The value did not move.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The provenance is computed in `derive_assumptions`, not in the route | Round-2 assignment section B; F1's own preferred fix. By the time the function returns, `da_pcts` is out of scope and no caller can see whether it was empty | A label re-derived in the route puts one fact in two files — backlog item 7 — and round 1 is the demonstration of what the caller gets wrong when it guesses |
| `_historical_average` and `_historical_cagr` return `_Derived(value, observations)` | The assignment: "Get that number out of the helper rather than recomputing the filter at the call site" | Returning a bare 2-tuple makes each field's meaning its position (rule 2). A private frozen record with two named fields costs six lines |
| **The `else 0.0` expressions were left exactly as they were** | Criterion 14, and honesty about the census. `float(np.mean(non_zero)) if non_zero else 0.0` still reads word-for-word as it did | Rewriting it as an `if/return` would have removed a hit from the rule-3 census in `docs/2-rules/rules.md:65` **while preserving the substitution** — the count would improve and the defect would not. Measured: the census is `116` before and `116` after, file-for-file |
| `observations` for `da_pct_revenue` / `capex_pct_revenue` is the **non-zero** count from the helper, not `len(da_pcts)` | The assignment says `len(list)` for these three and the non-zero count for `operating_margin`/`tax_rate`, but `_historical_average` drops zeros from all four alike (`:18`). `len(da_pcts)` would claim two years fed an average that one year fed | Following the letter there would have put a wrong integer in the sentence. The principle the assignment states — "the number of filing-years that fed it" — is what I implemented. `nwc_pct_revenue` keeps `len(nwc_pcts)` because it uses a plain mean and a reported zero **is** an observation there |
| A CAGR reports `observations=2` | Two revenue figures feed it, whatever the window spans (`:50`, `revenues[-1 - lookback]` and `revenues[-1]`) | Reporting `lookback + 1` would claim the intervening years fed a figure they did not touch |
| The clamp is a **clause appended to** whichever origin applies, not a fourth origin | Round-2 assignment step 7 | The clamp lands on a supplied figure and on a derived one alike; making it an origin would erase which of the two arrived |
| I added a **pad clause** for revenue growth, which the assignment did not ask for | Rule 6, and it is F1 in another dress: a reader who supplies one rate for a five-year projection has four rates chosen by this platform, and `origin='supplied'` alone claims all five are theirs | The clause is worded for either branch and fires only when the list actually grew. Output above shows it: "The projection runs 3 year(s) and only 1 rate(s) reached it, so the last rate was REPEATED…" |
| `_TAX_RATE_FLOOR` / `_TAX_RATE_CEILING` name the two literals already inline at the clamp | The sentence has to state the real band; a retyped band in the sentence is the defect that `templates/assumptions.html`'s literal `4.0` was | The figures are unchanged, so no value moved; criterion 14 confirms it |
| Two of the three sentences are `.format` templates | Each carries a fact about the particular run — the year count, or the substituted default. `models/valuation.py`'s existing labels are fixed strings because nothing about them varies | Hard-coding one sentence per ratio would be six near-copies that drift. Nothing is looked up by these values and none is called, so rule 2's ban on a dispatch table does not bite |
| `derive_assumptions` **adds** `"sources"` and changes no existing key | Round-2 assignment step 4; `cli.py:733` and `project_fcffs` read the dict by name and `cli.py` is out of scope | Criterion 14 measures it over four stubs, including a clamped one |
| `assumption_sources` on the assumptions page's failure path is still `{}` | F5; the reviewer confirmed the reasoning | Six labels there would describe a run that did not happen. The contract is now written on the key |

**No change in this diff was made to reach a number.** The one number in the round-2
work is criterion 14's requirement that no number move, and it is the constraint, not the
target.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `AssumptionSource.origin` / `.detail` / `.observations` | **stops** — `TypeError` naming the field; nothing is defaulted | `models/valuation.py`, frozen dataclass, three required fields |
| `HistoricalFCFFYear.*` | **stops** — unchanged from round 1, moved file only | `models/valuation.py` |
| `_Derived.value` / `.observations` | **stops** — both required | `analysis/projector.py` |
| `_historical_average([])` | **does not stop.** It returns `0.0`, exactly as before — backlog item 1, untouched. **What is new: it also returns `observations=0`, and the output now says the figure was SUBSTITUTED and is not a measurement** | criterion 11 output |
| `_historical_cagr` on a non-positive or degenerate window | **does not stop.** Returns `0.0`, as before, now with `observations=0` and the substituted label | `analysis/projector.py`; a one-year filing reaches it with `periods=0` |
| the tax clamp | **does not stop** and does not silently move a figure any more: when it changes the value the sentence names the pre-clamp figure and the band | the NaN output above, `nan% fell outside it, so 0.00%` |
| `assumptions["sources"]` in the route | **stops** — a `KeyError` naming `sources` if `derive_assumptions` ever stopped producing it. No `.get`, no fallback | `api/routes_valuation.py`; criterion 9's grep is unchanged at `1` |
| `financials.get_cash_flow(year)` in `_historical_fcff_by_year` | unchanged from round 1: no stop, no figure, the year is carried marked not computable | criterion 11's `historical_fcff rows` line |

**One "defaults to" row stands, and it is the same one as at round 1:** the two zero
substitutions in `analysis/projector.py` are still zero substitutions. This unit was
scoped to label them, not to remove them; removing them moves numbers and criterion 14
forbids it. Backlog item 1 still owns the fix.

## Measurements

| Gate | Committed tree (`35be956`) | Round 2 |
|---|---|---|
| pytest (`--ignore-glob="*_rule3_red.py"`) | `145 passed` | `145 passed, 1 warning in 3.36s` — failure set empty on both sides |
| ruff | `Found 5 errors.` all `BLE001` | `Found 5 errors.` all `BLE001` |
| mypy (pinned command) | `Found 14 errors in 4 files (checked 18 source files)` | identical count, identical set, shifted lines |
| `GET /` | `200` | `200` |
| rule-3 census, whole repo (`rules.md:65`) | `116` | `116`, and identical per file |
| criterion 9 grep, `api/routes_valuation.py` | `1` | `1` |
| rendered body sha256, five paths | — | identical, table above |

### Coverage — it fell, as the assignment said it would

Measured with `pytest -q --ignore-glob="*_rule3_red.py" --cov=analysis --cov=api
--cov=models --cov-report=term-missing`, before by `git stash`:

| Module | Before | After |
|---|---|---|
| `analysis/projector.py` | 68 statements, 0 missed, 100% | 114 statements, **1 missed**, 99% — line `214` |
| `api/routes_valuation.py` | 95 statements, 8 missed, 92% | 132 statements, **13 missed**, 90% |
| `models/valuation.py` | 108 statements, 3 missed, 97% | 127 statements, **3 missed**, 98% — the same three pre-existing properties |

The newly uncovered lines, each reached by execution in this entry so that none is dead
code:

- `analysis/projector.py:214` — the body of the tax-clamp clause. Reached twice above:
  the supplied-60% run (`CLAMPED into the 0% to 50% band … 60.00% fell outside it`) and
  the NaN run.
- `api/routes_valuation.py:148` — `missing.append("income statement")`, F4's line. Dead
  through `FinancialStatements.years`, required as type narrowing, reviewer's verdict is
  leave it.
- `api/routes_valuation.py:344-348` — the cache-hit branch. It was **already uncovered**
  as one statement before this unit (`:195`); `CachedExtraction` turned that statement
  into five, so four of the five new misses are one pre-existing uncovered branch
  spelled out. The suite deliberately does not pin the cache (backlog item 5,
  `tests/unit/test_routes.py:39-42`). My probe reaches it every run — mode
  `valuation_cachehit` — so it is live, not dead.

**I added no unreachable guard and restructured nothing to hold a percentage.** The
tester closes the gap.

## What I did not do

- **No template, stylesheet, `cli.py`, `ingestion/` or `tests/` change.**
  `git diff --stat` → `analysis/projector.py`, `api/routes_valuation.py`,
  `models/valuation.py`, plus `docs/8-build/phases.md`, which was already modified in the
  working tree when I started and is the orchestrator's.
- **I did not repair backlog item 6** (`x / 100 if x else None`), item 1 (the zeros
  themselves), item 5, 7, 11, 26 or 29, nor the provider re-derivation.
- **I did not touch `partition_by_confidence`, `normalize_financials` or
  `calculate_fcff_historical`.** No signature outside the three files moved.
- **I did not delete the dead `"income statement"` line** (F4), and I did not add a test
  to cover the clamp clause.

## Findings for the orchestrator

1. **Criterion 13's literal wording is wrong and should be corrected before a tester is
   pointed at it.** "For every ratio labelled derived, at least one `historical_fcff` row
   for a year it used has `is_computable=True`" fails for `operating_margin` and
   `tax_rate` on a filing with no cash flow statements, where both labels are correct and
   both FCFF rows are correctly absent. The check that states the intent splits the six
   ratios by which statement feeds them; my script prints both and the difference is in
   this entry. A tester writing the literal assertion would produce a red test against
   correct code.
2. **`P8b-statements-ui` should print, beside each ratio, which statement fed it.** That
   is what removes the residual confusion in finding 1 above, and it is a one-column
   change to whatever table shows `assumption_sources`.
3. **`P8b-statements-ui` must head the historical FCFF table "post-adjustment"** (F8),
   and must render `is_computable=False` rows as words and not as a blank cell (the
   reviewer's condition at the end of its rule-3 section).
4. **Backlog item 6 is now the last thing standing between the output and a true
   provenance label.** `derive_assumptions` honours a deliberate `0.0`; only the route's
   `x / 100 if x else None` conversion turns a typed zero into "not supplied". Once P8b
   renders the label, that mislabel is on the page. Item 6 should be sequenced before or
   with P8b.
5. **A NaN tax rate still becomes a silent 0.00% in the projection**, because
   `max(0.0, min(nan, 0.50))` is `0.0`. This unit makes it *visible* — the clamp clause
   names `nan%` — but the value still reaches every downstream figure as a 0% tax rate.
   `analysis/fcff.py` stops on the same input; `analysis/projector.py` does not. That
   asymmetry is backlog item 1 territory and nobody owns the projector half.
6. **`derive_assumptions`' revenue-growth branch mutates its caller's list.**
   `rev_growth = ov.revenue_growth_rates` then `rev_growth.append(...)` at `:152-154`
   appends into the `ProjectionAssumptions` the caller passed in. Pre-existing, untouched
   by this unit, and harmless today only because both entry points build a fresh list per
   request. It is not in the backlog.
