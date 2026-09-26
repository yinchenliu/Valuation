---
agent: programmer
assignment: P8a-statements-data
round: 1
status: complete
files_touched: [api/routes_valuation.py]
verdict:
---

# P8a-statements-data — carry the parsed statements and the applied adjustments into both route contexts

> Opened before the first command; filled as each result landed.

## What I did

`api/routes_valuation.py` now holds one frozen `CachedExtraction` dataclass with four
named, typed fields — `raw_financials`, `normalised_financials`, `applied_items`,
`excluded_items` — in place of the 2-tuple the module-global cache used to hold, and
`_extraction_cache` is retyped to `dict[str, CachedExtraction]`. `assumptions_page`
writes all four; `run_valuation` reads all four on **both** the cache-hit and the
cache-miss branch. Two further values are built in the route and carried: a per-year
historical FCFF record (`_historical_fcff_by_year`, calling
`analysis/fcff.py:calculate_fcff_historical` over the **normalised** statements, with a
year whose income statement or cash flow statement is absent carried through marked
`is_computable=False` and naming what was missing, never zeroed and never dropped), and
a rule 6 source label per projection ratio (`_assumption_sources`, six literal keys and
six literal attribute reads off `overrides`; `_all_derived_assumption_sources` for the
assumptions page, which takes no override at all). All six context keys —
`raw_financials`, `financials`, `applied_non_recurring`, `excluded_non_recurring`,
`historical_fcff`, `assumption_sources` — are set on `GET /assumptions` (success and
failure), on `POST /valuation`'s success branch and on its error branch. **No template
was touched, nothing new is rendered, and no number moved:** the implied share price
under identical stubbed inputs is `33.208053691275175` before the change and
`33.208053691275175` after it, and every rendered body is byte-for-byte the same length
as before.

## Baseline, measured at 35be956 before any edit

| Fact | Command | Output |
|---|---|---|
| tests | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` | `145 passed, 1 warning in 3.74s` |
| lint | `.venv/Scripts/python.exe -m ruff check .` | `Found 5 errors.` |
| types | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | `Found 14 errors in 4 files (checked 18 source files)` |
| `GET /` | the TestClient one-liner | `200` |
| rule-3 grep count in `api/routes_valuation.py` | criterion 9 grep | `1` |
| `getattr` in `api/routes_valuation.py` | `grep -n getattr` | no match |

All six agree with the assignment's "What is already true" table. I also verified the
claim about `normalize_financials` by execution rather than by reading: the probe below
prints `raw EBIT=240.0  normalised EBIT=260.0` for 2024 off the *same* route context,
which is only possible because `normalize_financials` returned a new object and left its
argument alone (`analysis/normalizer.py:245`, `dataclasses.replace`).

## The probe

`c:/tmp/p8a_probe.py` (scratch, outside the repository). It sets the three provider
environment variables the way `tests/unit/test_routes.py`'s fixture does, replaces
`routes_valuation._extract_from_files` and `routes_valuation.fetch_price_data` with
hand-built stubs, captures the context by replacing `routes_valuation.templates.
TemplateResponse` with a wrapper that records `(name, dict(context))` and delegates to
the original, and drives the app through `starlette.testclient.TestClient`. No socket,
no PDF, no key.

The stub is three extracted years (2023, 2024, 2025) where **2025 deliberately has no
cash flow statement**, and three non-recurring items: one `high`, one `medium`, one
`low`. Modes: `assumptions`, `assumptions_error`, `valuation_cachehit` (GET
`/assumptions` first, so `POST /valuation` takes the cache branch), `valuation_cachemiss`,
`valuation_error`.

Run as:

```
PYTHONPATH=C:/Users/LiuYinchen/Valuation .venv/Scripts/python.exe c:/tmp/p8a_probe.py <mode>
```

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the cache holds four named fields, not a tuple | **pass** | `grep -n "class CachedExtraction" api/routes_valuation.py` → `34:class CachedExtraction:` · `grep -n "dict\[str, CachedExtraction\]" api/routes_valuation.py` → `95:_extraction_cache: dict[str, CachedExtraction] = {}` (one match each) |
| 2 | the test gate is unchanged | **pass** | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` → `145 passed, 1 warning in 3.40s` |
| 3 | no new lint error | **pass** | `.venv/Scripts/python.exe -m ruff check .` → `Found 5 errors.`; all five are `BLE001` and none is in a line this unit wrote |
| 4 | no new type error | **pass** | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` → `Found 14 errors in 4 files (checked 18 source files)` — the same 14, at shifted line numbers |
| 5 | `GET /` still 200 | **pass** | the TestClient one-liner → `200` |
| 6 | all six keys on `GET /assumptions`, including its error branch | **pass** | probe output below, modes `assumptions` and `assumptions_error` |
| 7 | all six keys on `POST /valuation`, success and error | **pass** | probe output below, modes `valuation_cachehit`, `valuation_cachemiss`, `valuation_error` |
| 8 | **no number on either page moved** | **pass** | `implied_share_price=33.208053691275175` before and after, on both branches; every `body_len` identical |
| 9 | no new conditional zero or `.get` fallback | **pass** | criterion 9 grep → `1` before, `1` after. The one match is the pre-existing `shares = info.get("sharesOutstanding", 0) / 1e6` at the yfinance fallback (rule 5 / rule 3, pre-existing, untouched) |
| 10 | no `getattr` on a variable name | **pass** | `grep -c getattr api/routes_valuation.py` → `0` |

### Criterion 6 and 7 — the literal probe output, after the change

```
=== assumptions
keys=['applied_non_recurring', 'assumption_sources', 'company_name', 'default_risk_free_rate_display', 'defaults', 'error', 'excluded_non_recurring', 'files', 'financials', 'historical_fcff', 'raw_financials', 'ticker']
implied_share_price=<no dcf in context>
body_len=5901
=== assumptions_error
keys=['applied_non_recurring', 'assumption_sources', 'company_name', 'default_risk_free_rate_display', 'defaults', 'error', 'excluded_non_recurring', 'files', 'financials', 'historical_fcff', 'raw_financials', 'ticker']
implied_share_price=<no dcf in context>
body_len=5918
=== valuation_cachehit
keys=['applied_non_recurring', 'assumption_sources', 'assumptions', 'capm', 'company_name', 'current_price', 'dcf', 'excluded_non_recurring', 'extraction', 'financials', 'historical_fcff', 'raw_financials', 'ticker', 'wacc']
implied_share_price=33.208053691275175
body_len=11827
=== valuation_cachemiss
keys=['applied_non_recurring', 'assumption_sources', 'assumptions', 'capm', 'company_name', 'current_price', 'dcf', 'excluded_non_recurring', 'extraction', 'financials', 'historical_fcff', 'raw_financials', 'ticker', 'wacc']
implied_share_price=33.208053691275175
body_len=11827
=== valuation_error
keys=['applied_non_recurring', 'assumption_sources', 'assumptions', 'capm', 'company_name', 'current_price', 'dcf', 'error', 'excluded_non_recurring', 'extraction', 'financials', 'historical_fcff', 'raw_financials', 'ticker', 'wacc']
implied_share_price=<no dcf in context>
body_len=831
```

All six keys appear in all five modes.

### Criterion 8 — the same stubbed inputs, before and after

Identical probe, identical stub, `git stash`-free comparison (baseline run taken before
the first edit):

| Mode | Before (35be956) | After |
|---|---|---|
| `valuation_cachehit` implied share price | `33.208053691275175` | `33.208053691275175` |
| `valuation_cachemiss` implied share price | `33.208053691275175` | `33.208053691275175` |
| `valuation_cachehit` enterprise value | `3720.805369127517` | `3720.805369127517` |
| `valuation_cachehit` equity value | `3320.805369127517` | `3320.805369127517` |
| `valuation_cachehit` WACC | `0.09450000000000001` | `0.09450000000000001` |
| `valuation_*` rendered body length | `11827` | `11827` |
| `assumptions` rendered body length | `5901` | `5901` |
| `assumptions_error` rendered body length | `5918` | `5918` |
| `valuation_error` rendered body length | `831` | `831` |

The `assumptions` page's `defaults` dict is character-identical before and after
(`revenue_growth_rates` `0.18321595661992318` ×5, `operating_margin`
`0.2150793650793651`, `tax_rate` `0.24461718284748343`, `da_pct_revenue` `0.1`,
`capex_pct_revenue` `0.05`, `nwc_pct_revenue` `0.02`).

Nothing moved. No figure was targeted and no change was made to reach one.

### The new keys actually carry the chain, not just the names

`--details`, mode `valuation_cachehit`:

```
  2023: raw EBIT=200.0  normalised EBIT=200.0
  2024: raw EBIT=240.0  normalised EBIT=260.0
  2025: raw EBIT=280.0  normalised EBIT=320.0
  applied=[(2025, 'Restructuring charge', 'high'), (2024, 'Litigation settlement', 'medium')]
  excluded=[(2024, 'Asset sale gain', 'low')]
  fcff 2023: computable=True missing=() value=177.3684210526316
  fcff 2024: computable=True missing=() value=213.0967741935484
  fcff 2025: computable=False missing=('cash flow statement',) value=None
  source capex_pct_revenue: derived from the filing's history
  source da_pct_revenue: derived from the filing's history
  source nwc_pct_revenue: derived from the filing's history
  source operating_margin: you supplied this value
  source revenue_growth_rates: you supplied this value
  source tax_rate: you supplied this value
```

Read from the top: the raw and the normalised sides differ exactly where an applied item
landed (+20 in 2024, the `medium` litigation item; +40 in 2025, the `high` restructuring
item), so the reconciliation has both of its sides; the `low` item is in `excluded` and
moved nothing. The form supplied `revenue_growth`, `operating_margin` and `tax_rate` and
omitted the other three, and the labels say exactly that. Mode `assumptions` gives the
same six keys with all six labelled `derived from the filing's history`.

**One input to the FCFF figures, traced to the filing (stub).** 2023:
CFO = 140 + 100 + 0 + (−20) + 0 = 220; EBT = 200 − 10 = 190, effective tax = 50/190 =
0.2631579; after-tax interest = 10 × (1 − 0.2631579) = 7.368421; CapEx = 50.
FCFF = 220 + 7.368421 − 50 = **177.368421**, which is what the route carried. The 2024
row is `213.0967741935484` rather than `212.842105`, and the difference is the proof that
the rows are built from the **normalised** statements: with the raw EBIT of 240 the
effective tax rate is 60/228 = 0.263158 and FCFF is 212.842105; with the normalised EBIT
of 260 it is 60/248 = 0.241935 and FCFF is 213.096774.

**Deleting an input changes the answer, and a missing statement is reported, not
zeroed.** Calling `_historical_fcff_by_year` directly over the stub:

```
with every statement present:
  2023 True () 177.368421
  2024 True () 212.842105
  2025 False ('cash flow statement',) None
with the 2023 cash flow statement deleted:
  2023 False ('cash flow statement',) None
  2024 True () 212.842105
  2025 False ('cash flow statement',) None
with 2023 CFS net income moved 140 -> 240:
  2023 True () 277.368421
  2024 True () 212.842105
  2025 False ('cash flow statement',) None
```

(These three runs call the helper on the *raw* stub, hence 212.842105 for 2024.) The
deleted year is neither dropped from the list nor given a zero: it is present, marked not
computable, and names the statement that was absent.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `CachedExtraction` is `@dataclass(frozen=True)` with four required fields, none defaulted | Rule 2: one named thing with a fixed, typed signature. Rule 3: a defaulted `list[NonRecurringItem] = []` would let a cache entry be built that silently claims "nothing was adjusted" | A 4-tuple makes each value's meaning its position. Proved the fields are required: `CachedExtraction(...)` missing one raises `TypeError: CachedExtraction.__init__() missing 1 required positional argument: 'excluded_items'` |
| A new `HistoricalFCFFYear` record rather than a `HistoricalFCFF` with zeros | Assignment step 4; rule 3 — "a zero that means we do not know and a zero that means zero are the same bytes" | `cli.py:721-722` drops the year with a bare `continue`, so a reader cannot tell a dropped year from a year never extracted. `missing_statements` is a tuple naming what was absent, and it too is required, not defaulted |
| The FCFF rows are built from the **normalised** statements on both routes | Assignment step 4 — that is what every other figure on both pages is built from | Building from raw would put a table on the page whose tax rates disagree with the DCF's, with nothing saying why. Demonstrated above: 213.096774 (normalised) vs 212.842105 (raw) for 2024 |
| `_historical_fcff_by_year` is called **after** the valuation in `run_valuation` (step 7) | Criterion 8: no number may move. Computing it last means no line it added can be read by anything above it | Placing it beside step 1 would have been tidier and would have put a new call ahead of every figure on the page |
| Six literal keys, six literal attribute reads in `_assumption_sources` | Rule 2 forbids an attribute read through a name that is not literal Python in git; `cli.py:738` does exactly that | A loop over field names is three lines shorter and unreviewable without running it |
| `assumptions_page` gets its labels from `_all_derived_assumption_sources()`, a literal six-key dict | Assignment step 5: "Write that explicitly rather than passing an empty `ProjectionAssumptions` and inferring it" | Inferring it from a throwaway object makes a fact about the route look like a computation |
| On `assumptions_page`'s failure and no-filing paths, `assumption_sources` is `{}` and not the six derived labels | A page that derived no ratio has no ratio to label; six labels there would describe figures the page does not show | The key is still always defined, which is what criterion 6 measures. Labelling nothing as "derived from the filing's history" would be a claim about a run that did not happen |
| The `.pop()` stayed a `.pop()`, the cache stayed a module global, `":" in files` was left alone | Backlog items 5 and 26; assignment "Backlog items this unit is NOT fixing" | I edited the lines on either side of both and changed neither |
| The provider label at `:295` stayed a re-derivation; no fifth field added to `CachedExtraction` | `P2b-provider` review round 1 finding F3; the assignment forbids it here and no done-criterion covers it | `CachedExtraction` is the right eventual home for the `ProviderResolution`, and adding it changes what this unit is |
| The stale comment above `_extraction_cache` was rewritten | It said the cache "carries the EXCLUDED non-recurring items alongside the normalised statements", which is now false — it carries four things | A comment that disagrees with the line below it is worse than none |
| `_SOURCE_SUPPLIED` / `_SOURCE_DERIVED` are `Final` | Matches the provenance-label convention already in `models/valuation.py:25-55` | Nothing looks a function up by these strings; they are looked *at*, never called, so rule 2's ban on a dispatch table does not bite |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `CachedExtraction.raw_financials` / `.normalised_financials` / `.applied_items` / `.excluded_items` | **stops** — `TypeError`, naming the field, at construction | `CachedExtraction(raw_financials=..., normalised_financials=..., applied_items=[])` → `missing 1 required positional argument: 'excluded_items'` |
| `HistoricalFCFFYear.year` / `.is_computable` / `.fcff` / `.missing_statements` | **stops** — `TypeError`, naming the field | `HistoricalFCFFYear(year=2024, is_computable=False, fcff=None)` → `missing 1 required positional argument: 'missing_statements'` |
| `financials.get_income_statement(year)` in `_historical_fcff_by_year` | **does not stop, and does not guess.** The year is carried with `is_computable=False` and `missing_statements=("income statement",)`, `fcff=None`. No figure is produced for it | the three-run execution above: the deleted year appears as `2023 False ('cash flow statement',) None` |
| `financials.get_cash_flow(year)` in `_historical_fcff_by_year` | same — carried, named, no figure | `2025 False ('cash flow statement',) None`, from the stub where 2025's CFS was never extracted |
| `overrides.revenue_growth_rates` (list) | cannot be missing: `ProjectionAssumptions.revenue_growth_rates` is `field(default_factory=list)` with no `None` state. Empty means "the reader typed nothing", and the label reads *derived* | `models/valuation.py:237`; probe mode `valuation_cachemiss` with `revenue_growth` omitted labels it derived |
| `overrides.operating_margin`, `.tax_rate`, `.da_pct_revenue`, `.capex_pct_revenue`, `.nwc_pct_revenue` | `None` means "not supplied" and the label reads *derived*. **A reader who deliberately types `0` also arrives as `None` and is labelled derived** — see the finding below | `api/routes_valuation.py:216-220`, `x / 100 if x else None`, backlog item 6. The label reports what the route did, and this unit did not repair the conversion to make the label true |
| `calculate_fcff_historical`'s `tax_rate` | **stops** — `ValueError` naming `tax_rate (tax_rate_override or income_statement.effective_tax_rate)` when NaN | `analysis/fcff.py:28-44`. New reachable stop, recorded under "what I did not do" |
| the six new context keys, on every branch | **cannot be absent.** Each is assigned before the `try` on `assumptions_page` and written literally in both `run_valuation` dicts | probe: all six keys in all five modes, including both error branches |

No "defaults to" row is a substitution this unit introduced. The one row that reads as a
default — the form's `0` — is pre-existing behaviour that this unit *reports* and is
recorded below as a finding.

## Measurements

Failure sets, not counts: the failure set is **empty before and empty after** —
`145 passed` both times, so no test changed state in either direction.

| Gate | Before | After |
|---|---|---|
| pytest (`--ignore-glob="*_rule3_red.py"`) | `145 passed, 1 warning in 3.74s` | `145 passed, 1 warning in 3.40s` |
| ruff | `Found 5 errors.` (all `BLE001`) | `Found 5 errors.` (all `BLE001`) |
| mypy (the full pinned command) | `Found 14 errors in 4 files (checked 18 source files)` | `Found 14 errors in 4 files (checked 18 source files)` |
| `GET /` | `200` | `200` |
| criterion 9 grep count, `api/routes_valuation.py` | `1` | `1` |
| `grep -c getattr api/routes_valuation.py` | `0` | `0` |

The three mypy errors in this file are the same three as before, at shifted line numbers:
`:465 union-attr` on `diluted_shares_outstanding`, `:474` and `:475 arg-type` into
`calculate_wacc` (backlog item 11, Phase 5). No fifteenth was added — the two `is None`
checks in `_historical_fcff_by_year` narrow `IncomeStatement | None` and
`CashFlowStatement | None` before either reaches `calculate_fcff_historical`.

**Figures this unit moved: none.** `33.208053691275175` before, `33.208053691275175`
after, on both branches, under the stub described above.

## What I did not do

- **No template, stylesheet, `cli.py`, `analysis/`, `models/`, `ingestion/` or `tests/`
  change.** `git diff --stat` shows `api/routes_valuation.py` alone (the second file in
  the diff, `docs/8-build/phases.md`, was already modified in the working tree when I
  started — it is not mine and I did not touch it). Nothing new renders; `P8b-statements-ui`
  owns that.
- **I did not carry any of `cli.py`'s three rule 3 print sites across.** `:508` and
  `:593` divide by a conditional zero; `:522-538` substitutes a blank for a missing cash
  flow statement seventeen times. Nothing in this diff substitutes anything.
- **I did not fix backlog items 5, 6, 7, 11, 26 or 29,** nor the provider re-derivation
  at F3. Each is named in the assignment as out of scope, and the code around all of
  them is where I was editing.
- **I did not change `normalize_financials`, `partition_by_confidence`, or
  `calculate_fcff_historical`.** No signature outside this file needed to move.

## Findings for the orchestrator

1. **A new stop became reachable on both routes, and it is the right stop.**
   `calculate_fcff_historical` raises `ValueError` when the effective tax rate is NaN
   (`analysis/fcff.py:39-44`). Before this unit the web app never called it, so a filing
   that produced a NaN tax rate for a historical year rendered a share price and said
   nothing; now that year's FCFF row raises and the route renders its error page. That is
   rule 3 behaving, and it is a behaviour change even though no number moved on any run I
   made. A tester should pin it deliberately. It cannot be reached from the current stub,
   so I could not exercise it end-to-end through a route without inventing an input.
2. **Backlog item 6 makes one of the six new labels lie, and it now lies in the output
   rather than only in a local variable.** `api/routes_valuation.py:216-220` converts
   `operating_margin`, `tax_rate`, `da_pct`, `capex_pct` and `nwc_pct` with
   `x / 100 if x else None`, so a reader who deliberately types `0` reaches
   `ProjectionAssumptions` as `None` and `assumption_sources` labels that ratio
   `"derived from the filing's history"`. The assignment told me to report the behaviour
   rather than repair the conversion, and I have. **Once `P8b-statements-ui` renders
   these labels, that mislabelling is visible to a user**, which raises item 6 from
   latent to shown. Phase 4 owns the conversion; the two units should not land far apart.
3. **`assumption_sources` on `GET /assumptions` is `{}` on the failure and no-filing
   paths**, not six derived labels. I judged that a page that derived no ratio has no
   ratio to label, and every key is still defined. If `P8b-statements-ui` is written
   expecting six entries whenever the key exists, it needs to handle the empty dict —
   worth stating in that unit's assignment.
4. **`FinancialStatements.years` is derived from `income_statements` alone**
   (`models/financial_statements.py:276-282`), so the `"income statement"` branch of
   `_historical_fcff_by_year` is presently unreachable through that property: a year with
   no income statement is not in `years` at all and gets no row. The check is there
   because `get_income_statement` returns `IncomeStatement | None` and because the
   invariant is a property of another module, not of this one. **A year that has a cash
   flow statement and no income statement is invisible on both pages today.** That is a
   gap in `FinancialStatements.years`, not in this route, and nobody owns it.
