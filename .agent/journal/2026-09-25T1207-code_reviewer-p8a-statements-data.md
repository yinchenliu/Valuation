---
agent: code_reviewer
assignment: P8a-statements-data
round: 1
verdict: changes_requested
---

# Review of P8a-statements-data, round 1

Programmer entry: `.agent/journal/2026-09-25T1149-programmer-p8a-statements-data.md`

Diff reviewed: `git --no-pager diff api/routes_valuation.py` (287 insertions). The second
file in the working tree, `docs/8-build/phases.md`, is the orchestrator's and was not
reviewed.

Every number below was re-measured by me. My probe is `c:/tmp/reviewer_p8a_probe.py`,
built from `tests/unit/test_routes.py`'s fixtures, not from the programmer's script. It
fingerprints the **output** (`sha256` of the rendered body, plus the result-page figures
off the captured context) and never names a new context key, so the identical script runs
against the code before the change and after it. Baseline taken by
`git stash push api/routes_valuation.py`, then `git stash pop`.

## The guard checks

Run over `api/routes_valuation.py`, the one file in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean (0 hits) |
| lookup with a fallback — `.get(k, 0)` | one hit, `api/routes_valuation.py:472` `info.get("sharesOutstanding", 0)` — pre-existing, untouched by the diff, backlog items 1 and 12; the other "hit" is the decorator `@router.get("/assumptions", …)` |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | clean. `CachedExtraction` and `HistoricalFCFFYear` default **nothing**; I confirmed construction raises `TypeError` naming the omitted field |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean — `grep -c getattr` → `0` |
| dict of functions keyed by data | clean. `_assumption_sources` returns a dict of **strings**, six literal keys, six literal attribute reads; rule 2 allows a key→value table and this one holds no behaviour |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output |

Criterion 9's own grep: `1` before, `1` after — the same single `sharesOutstanding` line.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `CachedExtraction.{raw_financials,normalised_financials,applied_items,excluded_items}` | **yes** — no field defaulted, `TypeError` names the omission at construction | `api/routes_valuation.py:52-55` |
| `HistoricalFCFFYear.{year,is_computable,fcff,missing_statements}` | **yes** — same, nothing defaulted | `api/routes_valuation.py:71-74` |
| `financials.get_income_statement(year)` / `get_cash_flow(year)` in `_historical_fcff_by_year` | **no stop — but no figure either.** The year is carried with `is_computable=False`, `fcff=None`, and `missing_statements` naming the absent statement | `_historical_fcff_by_year` over a stub with no 2025 cash flow → `fcff 2025 computable=False missing=('cash flow statement',) value=None` |
| `financials.years` when empty | no rows, no figure, no stop | a valuation over an empty extraction already dies upstream at `latest_is.diluted_shares_outstanding` (backlog item 15); not reached here |
| `overrides.revenue_growth_rates` | n/a — `list`, non-empty means supplied; a user-typed `0` arrives as `[0.0]`, non-empty, and reads *supplied*. Correct | `api/routes_valuation.py:431` |
| `overrides.{operating_margin,tax_rate,da_pct_revenue,capex_pct_revenue,nwc_pct_revenue}` | `is not None`, which is the right test **in this function**; the lie is injected one screen up at `:433-437` — see F2 | backlog item 6 |
| `calculate_fcff_historical`'s `tax_rate` | **yes** — `ValueError` naming `tax_rate (tax_rate_override or income_statement.effective_tax_rate)` | `analysis/fcff.py:70-73`; reachability proved below |
| the six new context keys, every branch | cannot be absent; all six present in all five modes I drove | probe `--keys`, five modes |

I judge `_historical_fcff_by_year`'s deliberate non-stop **correct**, and the
programmer's argument for it sound. Rule 3's defect is a value that is missing producing
a *number*. This produces `None` beside an explicit `is_computable=False` and a tuple
naming the statement that was absent — the opposite of a zero that means "unknown". It
is also what the assignment prescribes in step 4. **The correctness of that judgement
now depends entirely on `P8b-statements-ui`**: if the template renders `row.fcff.fcff`
into a blank cell instead of printing the words, the explicit record collapses back into
the indistinguishability rule 3 exists to prevent. That belongs in P8b's assignment as a
done-criterion, not as a finding here.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean — the new code carries `FinancialStatements` and `HistoricalFCFF` objects unchanged and computes no money figure of its own |
| percentages converted at the route boundary, once | clean — no conversion added or moved; `:433-437` and `:444-447` are byte-identical in the diff |
| falsy not treated as missing | clean **in the new code**: `is not None` on the five floats, non-empty on the list. The five pre-existing `x / 100 if x else None` conversions are untouched (backlog item 6) |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean — this unit adds one import, `api/ → analysis.fcff`, which is the permitted direction |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | four named cache fields | 1 match each | `35:class CachedExtraction:` · `97:_extraction_cache: dict[str, CachedExtraction] = {}` | yes |
| 2 | test gate unchanged | `145 passed` | `145 passed, 1 warning` before **and** after — failure set empty on both sides, not merely equal counts | yes |
| 3 | no new lint error | `Found 5 errors`, all `BLE001` | `Found 5 errors`; I diffed the **concise output line-by-line, line numbers normalised**: identical set | yes |
| 4 | no new type error | `Found 14 errors in 4 files` | `Found 14 errors in 4 files`; I diffed the error lines with line numbers stripped → `MYPY SET IDENTICAL` | yes |
| 5 | `GET /` still 200 | `200` | `200` | yes |
| 6 | six keys on `GET /assumptions`, incl. error branch | pass | pass — modes `assumptions`, `assumptions_error`; all six present, `{}`/`None`/`[]` on the error branch | yes |
| 7 | six keys on `POST /valuation`, both branches | pass | pass — modes `cachehit`, `cachemiss`, `valuation_error` | yes |
| 8 | **no number moved** | `33.208053691275175` both sides | **confirmed independently.** See the table below | yes |
| 9 | no new rule-3 site | `1` → `1` | `1` → `1` | yes |
| 10 | no `getattr` | `0` | `0` | yes |

### Criterion 8, my own measurement

`git stash` / `git stash pop` around one script. The body hash is `sha256` of the bytes
the route actually returned.

| Mode | Before | After |
|---|---|---|
| `assumptions` body sha / len | `b3b8c62cf0c56184` / 5895 | `b3b8c62cf0c56184` / 5895 |
| `assumptions` full `defaults` dict | `operating_margin 0.2150793650793651`, `tax_rate 0.24461718284748343`, growth `0.18321595661992318`×5, `da 0.1`, `capex 0.05`, `nwc 0.02` | character-identical |
| `assumptions_error` body sha / len | `c6b264093e63f60e` / 5924 | `c6b264093e63f60e` / 5924 |
| `cachehit` body sha / len | `b0dc703956f7e6f6` / 11839 | `b0dc703956f7e6f6` / 11839 |
| `cachemiss` body sha / len | `b0dc703956f7e6f6` / 11839 | `b0dc703956f7e6f6` / 11839 |
| `cachehit` implied share price | `33.208053691275175` | `33.208053691275175` |
| `cachehit` enterprise / equity value | `3720.805369127517` / `3320.805369127517` | identical |
| `cachehit` WACC | `0.09450000000000001` | `0.09450000000000001` |
| `cachehit` full `assumptions` dict | all eight keys | identical |
| `valuation_error` body sha / len | `684f6ab4993c2db6` / 828 | `684f6ab4993c2db6` / 828 |

Identical rendered bytes on all five paths, not merely identical share prices. Criterion
8 holds. **No figure was targeted anywhere in this diff**; every decision in the
programmer's entry carries a reason, not a number to reach.

## Findings

### F1 — the new `"derived from the filing's history"` label is asserted over values `derive_assumptions` substituted rather than derived · `major`

**Evidence:**

```
$ .venv/Scripts/python.exe -c "... FinancialStatements with two income statements and NO cash flow statements ..."
da_pct_revenue    = 0.0 | label: derived from the filing's history
capex_pct_revenue = 0.0 | label: derived from the filing's history
nwc_pct_revenue   = 0.0 | label: derived from the filing's history
rows: [(2023, False, ('cash flow statement',)), (2024, False, ('cash flow statement',))]
```

**Rule or document:** rule 6 — "An assumption that is not labelled is indistinguishable
from a measurement, and a reader will treat it as one." This is worse than unlabelled:
the route now states in words that a substituted `0.0` came from the filing's history.
Note the self-contradiction in the same render — `historical_fcff` says the cash flow
statement was absent for those very years, while `assumption_sources` says the D&A ratio
was derived from them.

The label has only two states, and the quantity it describes has three.
`analysis/projector.py:19` returns `0.0` from `_historical_average([])`; `:53` pads
revenue growth with a hardcoded `0.05`; `:24-26` returns a `0.0` CAGR; `:99` substitutes
`0.0` for NWC. Each is a substitution, and `_SOURCE_DERIVED` claims a measurement for all
of them. The **zeros** are pre-existing (backlog item 1, `analysis/` 5 hits) and are not
my finding; the **claim about their provenance** is new in this diff and is.

This repository already owns the right shape for this, and the programmer cites the same
lines for `Final`: `models/valuation.py:24-55` gives every provenance label three or four
states — `UNRECORDED`, `SUBSTITUTED` ("ASSUMPTION — … It is not a measurement of any
market"), `SUPPLIED`, `REGRESSION`. Two sentences here is a regression against that
convention.

**The assignment mandates the two-sentence scheme** (step 5: "Each value is one of
exactly two sentences"), so the assignment conflicts with rule 6 and the rule wins. I am
not widening the rule to fit the code and I am not choosing the third sentence's wording
— **this needs the orchestrator to correct the assignment**, either by naming a third
label here or by moving provenance into `derive_assumptions`' return (which the
assignment currently puts out of scope).

**What would fix it:** a third state — the route can test the same inputs
`derive_assumptions` tests (was there a cash flow statement for any year? more than one
revenue year?) and say "no history was available; a constant was substituted" — or, the
better fix, `analysis/projector.py` returns the provenance alongside each ratio and the
route reports it.

### F2 — confirming the programmer's finding 2: the `derived` label is also wrong for a deliberate `0` · `minor`

**Evidence:** `api/routes_valuation.py:433`, `operating_margin=operating_margin / 100 if operating_margin else None` (through `:437`); a user who types `0` reaches `_assumption_sources` as `None` and is labelled `"derived from the filing's history"`.
**Rule or document:** backlog item 6, and rule 6 once rendered. The falsy test itself is **pre-existing and recorded**, untouched by this diff, and the assignment explicitly told the programmer to report rather than repair it. Confirmed and correctly reported.
**What would fix it:** nothing in this unit. It is a real consequence for sequencing: item 6 must land before or with `P8b-statements-ui`, or the mislabel moves from a local variable to the page. Same family as F1 and the same fix is likely to cover both.

### F3 — confirming the programmer's finding 1: the new `calculate_fcff_historical` call adds a reachable stop, and it is the right stop · `note`

**Evidence:** the NaN path is reachable, not theoretical — `json.loads('{"revenue": NaN}')` succeeds (Python's decoder accepts bare `NaN`), `ingestion/claude_extractor.py:605,721` parse the model's reply with a plain `json.loads`, and a NaN `revenue` propagates: `IncomeStatement(revenue=nan).ebt` → `nan`, which is **truthy**, so `effective_tax_rate` returns `nan` rather than the `0.0` branch, and `calculate_fcff_historical` raises `ValueError: tax_rate (tax_rate_override or income_statement.effective_tax_rate) is NaN …`.
**Rule or document:** rule 3. A stop that names the field, surfaced to the reader on the rendered error page, is the behaviour the rule asks for. **Confirmed, and it is not a defect.**
**One thing the programmer did not say, for the tester:** the call is last in `run_valuation` (step 7) but is placed **before** `derive_assumptions` in `assumptions_page` (`:310` vs `:314`). So on the assumptions page a NaN in any single historical year now replaces the whole defaults form with an error page, where it previously rendered `nan` into the form fields. That is still the better behaviour, but it is a second behaviour change and it is the one a tester can reach with a stub.

### F4 — confirming the programmer's finding 4: the `"income statement"` branch is unreachable, and a year with only a cash flow statement is invisible · `note`

**Evidence:**

```
years [2024]
rows [(2024, True, ())]     # 2023 has a cash flow statement and no income statement, and gets no row at all
```

`models/financial_statements.py:276-282` builds `years` from `income_statements` alone,
so `get_income_statement(year)` for `year in financials.years` never returns `None`.
**Rule or document:** none. The `is None` check is **required** — it is what narrows
`IncomeStatement | None` for mypy, and removing it would add a fifteenth type error. Only
the `missing.append("income statement")` line inside it is dead, and it returns no
number, so rule 3's ban on an unreachable guard that quietly returns a figure does not
bite. Leave it. The second half of the finding — a year with a cash flow statement and no
income statement is invisible on both pages — I reproduced above; it is a gap in
`FinancialStatements.years`, nobody owns it, and it is not this route's.

### F5 — overturning the programmer's finding 3 in part: `assumption_sources == {}` is right, but it is a contract P8b cannot guess · `note`

**Evidence:** probe mode `assumptions_error` → `keys [... 'assumption_sources' ...]`, value `{}`.
**Rule or document:** none broken. The reasoning is correct: a page that derived no ratio
has no ratio to label, and six "derived" labels there would describe a run that did not
happen. **Confirmed.** But the key's type is then `dict[str,str]` that is *either* empty
*or* exactly six entries, and nothing states which. That belongs in `P8b-statements-ui`'s
assignment as an explicit contract line, which is what the programmer asked for.

### F6 — the six ratio names now live in two literal dicts · `note`

**Evidence:** `api/routes_valuation.py:212-231` (`_assumption_sources`) and `:244-251` (`_all_derived_assumption_sources`) each spell out the same six keys.
**Rule or document:** none. Rule 2 is satisfied — both are named functions with fixed typed signatures, and the duplication is what buys the literal attribute reads that keep `getattr` out of the file. The assignment mandates the second function in as many words ("Write that explicitly rather than passing an empty `ProjectionAssumptions` and inferring it"), and the programmer gives the reason. I accept it.
**What would fix it, if F1's third label lands:** the two functions become three states over one key list, and that is the moment to collapse them — a seventh ratio added to one dict and not the other renders as nothing in a Jinja template, silently. Worth a line in whichever unit takes F1.

### F7 — `HistoricalFCFFYear` is a model living in `api/` · `note`

**Evidence:** `api/routes_valuation.py:58-74`.
**Rule or document:** none. `docs/3-architecture/` puts records in `models/`, but the
assignment's Files in scope is one file and putting it anywhere else would have been the
scope violation. Flagging it only so it is on the record for a later move.

### F8 — the historical FCFF row is a hybrid figure and must be labelled as one by P8b · `note`

**Evidence:** the programmer's own arithmetic, which I re-derived: 2024 FCFF is `213.0967741935484` from the normalised statements and `212.842105…` from the raw, because the effective tax rate moves with the adjusted EBIT (`60/248` vs `60/228`) while `cfo` and `capex` come from the unadjusted cash flow statement.
**Rule or document:** rule 4 — a reader must be able to walk the figure back. It is walkable, because `raw_financials` and `applied_non_recurring` are now in the same context. But a row headed "historical FCFF" that a reader cannot match against the filing's cash flow statement needs to say **post-adjustment** on the page. Building it from the normalised statements is the assignment's instruction and is the right choice; only the label is missing, and the label is P8b's.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 / 12 — `.get("sharesOutstanding", 0)`, and rule 5's second source | `api/routes_valuation.py:472` | no — outside the diff hunks |
| 5 — module-global cache, `pop`ped on read | `api/routes_valuation.py:97,407` | the cache's **contents** changed; `.pop()` and the global did not, as the assignment requires |
| 6 — five `x / 100 if x else None` | `api/routes_valuation.py:433-437` | no — comment lines above them moved, the expressions did not |
| 11 — `BalanceSheet \| None` into a `BalanceSheet` parameter | `api/routes_valuation.py:468,477,478` | no — same three errors, shifted lines, set-identical under mypy |
| 26 — `":" in files` | `api/routes_valuation.py:415` | no — the line is unchanged inside an edited hunk |
| 29 — `POST /valuation` with no `files` | `api/routes_valuation.py:415` | no |
| 1 — `_historical_average([]) → 0.0` and the `0.05` growth pad | `analysis/projector.py:19,53` | not touched — but F1 is about the new **claim** made about those values, which is this unit's |
| 8 — blanket `except Exception` (the 5 `BLE001`) | `api/routes_valuation.py:322,556` | no — set-identical ruff output |
| P2b-provider F3 — the provider label is a re-derivation | `api/routes_valuation.py:511` | no; the assignment forbids the fifth cache field and the programmer left it |

## Scope

`git --no-pager diff --stat` → `api/routes_valuation.py` and `docs/8-build/phases.md`.
The second is the orchestrator's, stated as such in the task and in the programmer's
entry. No template, no `static/`, no `cli.py`, no `analysis/`, `models/`, `ingestion/`,
no `tests/`. **Scope is clean.**

## One inaccuracy in the programmer's entry, for the record

Its Measurements section says "the three mypy errors in this file". There are **four**:
`:138 arg-type`, `:468 union-attr`, `:477` and `:478 arg-type`. The total, the set and
the criterion are all unaffected — I diffed the full error set with line numbers stripped
and it is identical before and after — so this is a miscount in prose, not a regression.

## Verdict

`changes_requested`.

The engineering here is good and the hard criterion holds: I reproduced criterion 8
independently and the rendered bytes are identical on all five paths, so this unit moved
no number. Scope is clean, the guard checks are clean, the failure sets of all three
gates are set-identical rather than merely equal in count, and the two judgement calls
the task asked me to weigh — the deliberate non-stop in `_historical_fcff_by_year`, and
the duplicated six-key dict — are both correctly reasoned and I accept them.

**F1 is what stands.** The unit introduces a sentence that tells a reader a number was
derived from the filing's history when `analysis/projector.py` substituted a constant
for it, and it does so in the same render where a sibling key reports that the statement
those numbers would have come from was never extracted. That is rule 6, and severity is
not a free choice. The assignment's "exactly two sentences" is what forces it, so the
assignment conflicts with the rule and the rule wins: **the orchestrator corrects the
assignment**, here or in a unit sequenced before `P8b-statements-ui` renders the label.
F2 is the same defect arriving from the other direction and should be fixed by the same
change. Everything else is a `note`, and four of them are hand-offs `P8b-statements-ui`'s
assignment needs (F5, F6, F8) or a test the tester should pin (F3).
