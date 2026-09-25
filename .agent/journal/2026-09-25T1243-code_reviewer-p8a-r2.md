---
agent: code_reviewer
assignment: P8a-statements-data
round: 2
verdict: approved
---

# Review of P8a-statements-data, round 2

Programmer entry: `.agent/journal/2026-09-25T1217-programmer-p8a-statements-data-r2.md`
My round-1 entry: `.agent/journal/2026-09-25T1207-code_reviewer-p8a-statements-data.md`

Diff reviewed: `git --no-pager diff analysis/projector.py api/routes_valuation.py
models/valuation.py` — 534 insertions, 34 deletions across the three files the round-2
assignment allows. `docs/8-build/phases.md` is the orchestrator's and was not reviewed.

**Every number below is mine.** My scripts are `c:/tmp/rev_p8a_r2_sources.py`,
`c:/tmp/rev_p8a_r2_derive.py`, `c:/tmp/rev_p8a_r2_cli.py`, `c:/tmp/rev_p8a_r2_f3.py` and
my round-1 probe `c:/tmp/reviewer_p8a_probe.py`. None is adapted from the programmer's.
Baseline taken by `git stash push analysis/projector.py api/routes_valuation.py
models/valuation.py`, so "before" is the committed tree at `35be956` with **no P8a at
all**, then `git stash pop`.

## The guard checks

Run over the three files in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | 6 hits, **every one pre-existing**: `analysis/projector.py:72,169,271`, `models/valuation.py:229,233,324`. `:72` is the only one inside a line the diff rewrote; see "The `else 0.0` left verbatim" below, where I judge the programmer's deliberate call |
| lookup with a fallback — `.get(k, 0)` | one hit, `api/routes_valuation.py:408` `info.get("sharesOutstanding", 0)` — pre-existing, outside the diff hunks, backlog items 1 and 12. The other "hit" is the decorator at `:175` |
| bare or-default — `or 0.0` | clean (0 hits) |
| money field defaulted to zero — `: float = 0.0` | 10 hits in `models/valuation.py`, all pre-existing and none in a diff hunk. The three record types this unit adds or moves default **nothing**: `AssumptionSource()` → `TypeError: missing 3 required positional arguments: 'origin', 'detail', and 'observations'`; `HistoricalFCFFYear()` → 4; `_Derived()` → 2. All three are `frozen=True` |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean — 0 in all three files |
| dict of functions keyed by data | clean. `sources` is `dict[str, AssumptionSource]` under six **literal** keys, and `AssumptionSource` holds two strings and an int. The five `ASSUMPTION_*` constants are strings; `.format()` on a string is not a behaviour lookup. Rule 2 bans looking up behaviour, and nothing here is called |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output |

Repo-wide rule 3 census (`docs/2-rules/rules.md:65`): **116 before, 116 after**, and the
per-file counts `diff` clean. Criterion 9's own grep on `api/routes_valuation.py`: `1` →
`1`. `models/valuation.py` holds 13 on both sides, so the two new record types added
none.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `AssumptionSource.{origin,detail,observations}` | **yes** — nothing defaulted, `TypeError` names all three | executed above |
| `HistoricalFCFFYear.*` | **yes** — unchanged from round 1, file moved only | executed above |
| `_Derived.{value,observations}` | **yes** — both required, frozen | executed above |
| `assumptions["sources"]` in both routes | **yes** — a bare `[]` index. `KeyError: 'sources'` if `derive_assumptions` ever stopped producing it. No `.get`, no fallback | `api/routes_valuation.py:236,458` |
| `_historical_average([])` → `0.0` | **no stop** — backlog item 1, unchanged. What is new: `observations=0` travels with it and the output now says SUBSTITUTED | criterion 11, below |
| `_historical_cagr` on a degenerate window | **no stop** — unchanged. `observations=0`, labelled substituted. Proved on a one-year filing: `origin='substituted' value=[0.0, 0.0]` | my script, "ONE filing-year" |
| `nwc_pct` on an empty `nwc_pcts` | **no stop** — unchanged, `observations=0`, labelled substituted | criterion 11 |
| the tax clamp at `:207` | **no stop**, and no longer silent: when it moves the value the sentence names the pre-clamp figure and the band | criterion "CLAMP", below |
| `financials.get_cash_flow(year)` in `_historical_fcff_by_year` | no stop, **and no figure**: `fcff=None`, `is_computable=False`, `missing_statements=('cash flow statement',)`. Accepted at round 1 and unchanged | criterion 11 rows |
| the six context keys, every branch | cannot be absent — all six present in all five modes I drove | keys table below |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean — this unit computes no money figure. `derive_assumptions` returns ratios and the percentage formatting in the new sentences (`:.2%`, `:.0%`) is display only, applied to values already expressed as fractions |
| percentages converted at the route boundary, once | clean — no conversion added, moved or duplicated. `api/routes_valuation.py:369-373` and `:379-382` are byte-identical to the committed tree |
| falsy not treated as missing | clean **in the new code**. `derive_assumptions` tests `ov.X is not None` on all five floats, and I confirmed a deliberate zero survives: `ProjectionAssumptions(operating_margin=0.0)` → `origin='supplied'`. The five pre-existing `x / 100 if x else None` at `:369-373` are untouched (backlog item 6) — see F2's outcome, which I refine below |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean for the files in scope. `analysis/projector.py` adds imports only from `models/valuation`. (`analysis/capm.py:16` imports `ingestion.price_fetcher` — pre-existing, recorded at `docs/9-reference/refactor-backlog.md:514`, not in this unit's diff) |
| `models/` imports nothing from this repository | clean — `models/valuation.py` imports `dataclasses` and `typing` only |

## Done-criteria, re-run

All fifteen executed by me.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | four named cache fields | 1 match each | `38:class CachedExtraction:` · `82:_extraction_cache: dict[str, CachedExtraction] = {}` | yes |
| 2 | test gate unchanged | `145 passed` | `145 passed, 1 warning` **before and after** — failure set empty on both sides, not merely equal counts | yes |
| 3 | no new lint error | `Found 5 errors`, all `BLE001` | `Found 5 errors`; concise output diffed with line/col stripped → **RUFF SET IDENTICAL** | yes |
| 4 | no new type error | `Found 14 errors in 4 files` | `Found 14 errors in 4 files`; error lines diffed with line numbers stripped → **MYPY SET IDENTICAL** | yes |
| 5 | `GET /` still 200 | `200` | `200` | yes |
| 6 | six keys on `GET /assumptions`, incl. error branch | pass | pass — modes `assumptions`, `assumptions_error`; all six present, `None`/`[]`/`{}` on the error branch | yes |
| 7 | six keys on `POST /valuation`, both branches | pass | pass — modes `cachehit`, `cachemiss`, `valuation_error` | yes |
| 8 | **no number on either page moved** | identical sha, five paths | **confirmed independently across all three stashed files.** Table below | yes |
| 9 | no new rule-3 site | `1` → `1`; census `116` → `116` | `1` → `1`; census `116` → `116`, per-file `diff` clean | yes |
| 10 | no `getattr` | `0` | `0` | yes |
| 11 | a ratio with no filing data is labelled substituted | pass | **pass** — output below | yes |
| 12 | a derived ratio names how many years | pass | **pass**, on my own hand count — below | yes |
| 13 | the page cannot contradict itself (corrected wording) | pass | **pass** on both stubs, using the assignment's corrected split | yes |
| 14 | no existing assumption value moved | pass, 4 stubs | **pass, 6 stubs** — `diff` of the dict with `"sources"` removed → identical. And `cli.py` still runs; see below | yes |
| 15 | one home for the labels | `0` | `0` for all four names, including `_assumption_sources` | yes |

### Criterion 8, my own measurement

`git stash push` over **all three** files, one script each side, body hash = `sha256` of
the bytes the route returned.

| Mode | Before (`35be956`) | After (round 2) |
|---|---|---|
| `assumptions` sha / len | `b3b8c62cf0c56184` / 5895 | `b3b8c62cf0c56184` / 5895 |
| `assumptions_error` sha / len | `c6b264093e63f60e` / 5924 | `c6b264093e63f60e` / 5924 |
| `cachehit` sha / len | `b0dc703956f7e6f6` / 11839 | `b0dc703956f7e6f6` / 11839 |
| `cachemiss` sha / len | `b0dc703956f7e6f6` / 11839 | `b0dc703956f7e6f6` / 11839 |
| `valuation_error` sha / len | `684f6ab4993c2db6` / 828 | `684f6ab4993c2db6` / 828 |
| implied share price | `33.208053691275175` | `33.208053691275175` |
| enterprise / equity value | `3720.805369127517` / `3320.805369127517` | identical |
| WACC | `0.09450000000000001` | `0.09450000000000001` |
| `defaults` dict, assumptions page | 8 keys, char-identical | identical **plus** `sources` |
| `assumptions` dict, result page | 8 keys, char-identical | identical **plus** `sources` |

Identical rendered bytes on all five paths. These are also the same five hashes I
measured at round 1, so round 2 moved nothing against round 1 either. `sources` is the
only delta in either dict, and the rendered body is unchanged, so no template iterates
the dict — I checked: the one loop over `assumptions` in `templates/` is
`valuation_result.html:130`, over `assumptions.revenue_growth_rates`.

### Criterion 14's real consequence — `cli.py` still runs

The criterion measures the dict. What matters is the two readers. `cli.py` is out of
scope and I executed it against the new return value:

```
$ python c:/tmp/rev_p8a_r2_cli.py
keys: [... 'sources' ...]
--- cli.print_assumptions against the NEW dict:
  Revenue growth (per yr): ['20.0%', '20.0%', '20.0%']
  Operating margin:        20.00%   Tax rate: 25.00%   D&A / Revenue: 10.00%
  CapEx / Revenue: 5.00%   NWC chg / Revenue: 2.00%
  Projection years: 3      Terminal growth: 2.50%
--- project_fcffs against the NEW dict:
  2025 revenue=1440.00 fcff=259.2000  ·  2026 ... 311.0400  ·  2027 ... 373.2480
```

Neither reader iterates the dict — `grep -n "assumptions.items()\|assumptions.keys()\|for
.* in assumptions\|\*\*assumptions" cli.py analysis/projector.py api/routes_valuation.py
templates/*.html` returns only the `revenue_growth_rates` loop above. An added key is
therefore invisible to both. Criterion 14 holds in substance, not only in form.

### Criteria 11, 12, 13 and the observations question

Criterion 11 — three income statements, **no** cash flow statements. This is my round-1
F1 reproduction, run again:

```
da_pct_revenue     value=0.0 origin='substituted' obs=0
   ASSUMPTION — SUBSTITUTED. Nothing from the filing fed this figure — no year
   contributed an observation — so 0.00% was used in place of a derivation.
   It is not a measurement.
capex_pct_revenue  value=0.0 origin='substituted' obs=0   (same sentence)
nwc_pct_revenue    value=0.0 origin='substituted' obs=0   (same sentence)
rows: [(2023, False, ('cash flow statement',)), (2024, False, ...), (2025, False, ...)]
```

All three read `substituted`; each sentence carries `SUBSTITUTED` and `It is not a
measurement.` **F1 is fixed at its cause** — the label is produced by the function that
holds the evidence, not re-derived by the caller.

Criterion 12 — two complete filing-years. **My own hand count, written before I ran
anything:** revenue 1000→1200 (CAGR reads both endpoints, 2); EBIT 200/1000 and 240/1200,
neither zero, 2; tax 50/200 and 60/240, neither zero, 2; D&A 100/1000 and 120/1200, 2;
CapEx 50/1000 and 60/1200, 2; −ΔWC 20/1000 and 24/1200, 2. Measured: `observations=2` and
`origin='derived'` on all six. Agrees.

**The observations count is the non-zero length — verified by execution, not by reading.**
I built a stub whose 2023 has `revenue 1000 / sga 1000 / tax 0`, so
`operating_margin == 0.0` and `effective_tax_rate == 0.0` for that year, and 2024 normal:

```
per-year operating_margin:   [0.0, 0.2]
per-year effective_tax_rate: [0.0, 0.25]
operating_margin: value=0.2  origin='derived' obs=1     <- 1, not 2
tax_rate:         value=0.25 origin='derived' obs=1     <- 1, not 2
```

The same holds for the two ratios the assignment described as `len(list)`: with a zero
D&A in 2023, `da_pct_revenue` reports `obs=1` while `capex_pct_revenue` reports `obs=2`.
**The programmer departed from the assignment's letter here and it is right to have done
so**: `_historical_average` drops zeros from all four alike at `:71`, so `len(da_pcts)`
would have claimed two years fed an average one year fed — the same overstatement as F1
in a smaller form. The assignment's stated principle ("the number of filing-years that fed
it") is what the code implements, and the programmer names the departure and its reason in
its entry. `nwc_pct_revenue` keeps the full length, correctly, because it uses a plain
mean and a reported zero **is** an observation there: with a zero ΔWC in 2023 it reports
`obs=2` and the value halves to `0.01`. That is a measured average of a real zero, not a
substitution.

Criterion 13, the corrected wording, asserted over both stubs by me:

```
C13 no cash flow statements: rows=[(2023,False,('cash flow statement',)), ...]
  origins: growth=derived margin=derived tax=derived
           da=substituted capex=substituted nwc=substituted     -> PASS
C13 two complete years:      rows=[(2023,True,()), (2024,True,())]
  all six derived                                                -> PASS
```

No cash-flow-fed ratio is `derived` while every FCFF row is uncomputable, and no
income-statement-fed ratio is `derived` with no extracted year. **The programmer's
correction of criterion 13 is right and the assignment now carries it**; I confirm
independently that the original wording goes red against this code for a reason that is
not a contradiction (`operating_margin` and `tax_rate` are read off the income statement,
which was extracted).

### F3 — the ordering, proved by my own execution

Stub: two years, both with cash flow statements, 2024 `tax_expense = NaN`.

```
status 200
error: 'tax_rate (tax_rate_override or income_statement.effective_tax_rate) is NaN,
        so FCFF cannot be computed from it. ... Supply the missing input; it is not
        substituted with a default.'
defaults is empty: False
  operating_margin_display 20.0 · da 10.0 · capex 5.0 · nwc 2.0 · growth ['20.0' x5]
historical_fcff rows: 0
assumption_sources entries: 6
form rendered (has an <input name="operating_margin">): True
```

The named stop reaches the reader **and** the form survives. At round 1 the same input
replaced the whole defaults form with an error page. Fixed.

### The clamp and the pad clauses

Both judged by execution, not by reading.

**The clamp clause is honest and reachable.** Supplied `tax_rate=0.60`:

> `supplied by the caller … It was then CLAMPED into the 0% to 50% band this platform
> imposes: 60.00% fell outside it, so 50.00% is the figure every calculation downstream
> used.`

The band in the sentence comes from `_TAX_RATE_FLOOR`/`_TAX_RATE_CEILING`, the same two
names the clamp at `:207` uses, so the sentence cannot drift from the arithmetic. The
clause fires only when `tax_rate != pre_clamp_tax_rate`, so a substituted `0.0` that the
clamp leaves at `0.0` gets no clause — correct. Making it a clause rather than a fourth
origin is right: it lands on a supplied figure and a derived one alike, and an origin
would have erased which arrived.

**The pad clause fires, and only when padding happened.** One supplied rate,
`projection_years=5`:

> `supplied by the caller … The projection runs 5 year(s) and only 1 rate(s) reached it,
> so the last rate was REPEATED to fill the remainder. The repeat is this platform's, and
> it is not in the filing.`

Two supplied rates for `projection_years=2` → clause absent. So the clause is reachable
and states what happened.

**The `0.05` literal at `:169` is unreachable, and you were right to ask.** It can only
run when `rev_growth == []` and `ov.projection_years >= 1`. The supplied branch is entered
on a truthy list, so it is non-empty; the derived branch builds `[cagr.value] *
projection_years`, which is empty only when `projection_years <= 0`, and then the `while`
never runs. I exhausted 48 combinations of `projection_years ∈ {-2,-1,0,1,2,3,5,10}` and
`revenue_growth_rates ∈ {unset, [], [0.0], [0.1], [0.1,0.2], [0.0,0.0,0.0]}`:
`0.05 pad reached on 0 of 48 input combinations`.

**It is not a finding against this unit.** Line 169 is a context line in the diff, byte
for byte the committed text, and it is one of the three `analysis/projector.py` hits in
backlog item 1's census of 116. The unit added `rates_before_padding` above it and the
clause below it and changed neither the condition nor the literal. And because `0.05` is
unreachable, the new sentence — which says the last rate was *repeated* — is true on every
path that can actually run; had the literal been live the sentence would have been a lie.
Recorded for the orchestrator below rather than charged here.

### Coverage

`pytest -q --ignore-glob="*_rule3_red.py" --cov=analysis --cov=api --cov=models
--cov-report=term-missing`:

```
analysis\projector.py       114      1    99%   214
api\routes_valuation.py     132     13    90%   91, 120-121, 148, 207, 344-348, 406-408
models\valuation.py         127      3    98%   229, 233, 333
```

The programmer's figures reproduce exactly. **Line 214 is `tax_source = replace(`, the
body of the clamp clause, and I executed it** — the supplied-60% run above and the NaN run
both enter it. It is not an unreachable guard. `api/routes_valuation.py:148` is F4's dead
`missing.append("income statement")`, which I ruled *leave it* at round 1 and still do: it
is the type narrowing that keeps mypy at 14, and it returns no figure, so rule 3's
objection to an unreachable guard that quietly produces a number does not bite. `:344-348`
is the cache-hit branch — one pre-existing uncovered statement (`:195` at round 1) spelled
out as five by `CachedExtraction`; my probe reaches it every run in mode `cachehit`, so it
is live. No line the unit added is dead.

## The `else 0.0` left verbatim — the judgement you asked for

`analysis/projector.py:72` still reads `float(np.mean(non_zero)) if non_zero else 0.0`,
now as an argument to `_Derived(...)` instead of after a `return`. The programmer left the
expression word for word on purpose, so that the census at `docs/2-rules/rules.md:65`
would not fall while the substitution survived.

**I endorse that call, and I want the reason on the record.** Rewriting it as an
`if …: return` would have removed a hit from a count the whole repository uses as its rule
3 proxy, while the guess it measures went on producing a `0.0` that reaches a share price.
The backlog itself warns about exactly this failure mode at
`docs/9-reference/refactor-backlog.md:104-108` — *"A comment can inflate this number …
Check any future delta against the diff, not the count."* A census that improves because
code was reworded is not a census. The measured result is `116` before and `116` after,
file for file.

**I considered charging it under "a defect the unit touched is the unit's" and decided it
does not bite here**, for three reasons I can defend. The defect is not relocated: it is
the same expression, in the same function, over the same list, and only its wrapper
changed. Removing it means stopping instead of returning `0.0`, which moves numbers —
forbidden by criteria 8 and 14, which the *assignment* imposes and the orchestrator owns.
And round 1 already ruled these zeros pre-existing under backlog item 1; nothing new has
been learned about them since, so charging them now would punish precisely the disclosure
round 1 demanded.

**What the orchestrator must not lose:** rule 3 still wants a stop here and does not have
one. What this unit bought is rule 6 — the guess is now visible, named and carrying the
words `It is not a measurement.` Backlog item 1 remains the only owner of the stop, and it
now has one more reason to be sequenced.

## Findings

### F9 — a supplied growth list longer than `projection_years` is silently truncated, and the new clause names only the pad · `note`

**Evidence:**

```
TRUNCATION: supplied 5 rates, projection_years=2 -> [0.1, 0.2]
  label: supplied by the caller — the assumptions form, or the matching CLI option.
         Still an assumption, not a measurement: ...        (no clause)
```

**Rule or document:** none broken. Nothing is described as measured — the two rates shown
are the caller's, and `origin='supplied'` is true. The `[: ov.projection_years]` slice at
`:170` is a context line, untouched by the diff, and the discarded input is backlog item
6's family, not rule 6's.
**Why it is worth a line anyway:** the comment at `:171-176` states the principle — "A
repeated rate is this platform's figure … the label has to say so" — and the pad and the
truncate are the same two lines. Whoever finishes the provenance work (P8b, or item 6)
should append a matching clause, or the reader who typed five rates and got two never
learns which three were dropped.

### F10 — an absence on an error path still reaches the context as an empty collection, and P8b must not render it as "none" · `note`

**Evidence:** my F3 run — extraction succeeded, `derive_assumptions` succeeded,
`_historical_fcff_by_year` raised, and the context carries `financials` with two real
years beside `historical_fcff rows: 0`.
**Rule or document:** none broken **in this unit**, which renders nothing. `error` is in
the same context and distinguishes the case. This is the identical hand-off I recorded at
round 1 for `is_computable=False` rows, and the assignment mandates the empty-not-absent
shape in step 7 for a real reason (an undefined Jinja name renders as nothing on the
success path too).
**What would fix it:** a done-criterion in `P8b-statements-ui` that no statements block,
adjustment list, FCFF table or label table is rendered when `error` is set — otherwise an
empty table on the error page reads as "nothing was adjusted / no year was extracted",
which is F1's defect arriving through the template instead of the label.

No `blocker`, no `major`, no `minor` stands.

## Earlier findings

| # | Outcome | Note |
|---|---|---|
| F1 — `derived` asserted over substituted values · `major` | **fixed** | Fixed at its cause, not at the call site. The three cash-flow-fed ratios read `substituted` on my own round-1 reproduction, with `SUBSTITUTED` and `It is not a measurement.` in the sentence; the self-contradicting render is gone (criterion 13). The fix is the one I named as preferable: `analysis/projector.py` returns the provenance and the route reports it. I searched the rest of the diff for the same defect and found none — every `observations == 0` path (empty average, degenerate CAGR, empty `nwc_pcts`) reaches `substituted`, and the two new clauses state real steps |
| F2 — the `derived` label is also wrong for a deliberate `0` · `minor` | **not_fixed, and I narrow my own finding** | `api/routes_valuation.py:369-373` is unchanged; backlog item 6 and the assignment forbids repairing it here. But I overstated the harm at round 1. The value the page shows in that case **is** the historical average, and "derived from the filing: N filing-year(s)" is a true statement about it. The defect is that the reader's `0` was discarded, which is item 6's — a dropped input, not a mislabelled figure. I confirmed `derive_assumptions` itself honours a deliberate zero: `ProjectionAssumptions(operating_margin=0.0)` → `origin='supplied'`. Item 6 should still land before or with P8b, for the reason the programmer gives |
| F3 — the `calculate_fcff_historical` stop is right; its placement was wrong | **fixed** | Proved by my own execution above: 200, the named stop, and a fully populated form |
| F4 — the `"income statement"` branch is dead; the `is None` check is required narrowing | **not_fixed, as I directed** | Left in place. The programmer agrees with a citation (`models/financial_statements.py:276-282`, and `get_income_statement -> IncomeStatement \| None`). It is `api/routes_valuation.py:148` in the coverage miss list, reported rather than deleted, which is what I asked for |
| F5 — `{}` on the error path is right but is a contract P8b cannot guess | **fixed** | Written on the context key itself at `api/routes_valuation.py:255-260`: *empty, or exactly six entries, never a partial dict*, with the reason. P8b's assignment should cite that comment |
| F6 — the six ratio names in two literal dicts | **fixed** | Moot: both functions are deleted (criterion 15 → 0) and the six keys are written once, in `derive_assumptions`. The condition I set for collapsing them is the one that landed |
| F7 — `HistoricalFCFFYear` is a model living in `api/` | **fixed** | Moved to `models/valuation.py` field for field, imported back. Legal because round 2 widened Files in scope |
| F8 — the historical FCFF row is a hybrid | **not_fixed by design, recorded** | Confirmed again: 2024 is `213.0967741935484` and not `212.842105…` because the effective tax rate moves with the adjusted EBIT (`60/248` vs `60/228`) while `cfo` and `capex` come from the unadjusted cash flow statement. Building it from the normalised statements is correct and stays. `P8b-statements-ui` must head that table **post-adjustment** |

**My round-1 prose miscount, corrected here as the assignment asked.** My round-1 entry
said "The three mypy errors in this file"; there are **four** in
`api/routes_valuation.py` — at round-1 line numbers `:138 arg-type`, `:468 union-attr`,
`:477` and `:478 arg-type`; in the round-2 tree the same four sit at `:123`, `:404`,
`:413`, `:414`. The error **set** was and is identical before and after, so criterion 4
was never affected by the miscount.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 — `_historical_average([]) → 0.0` | `analysis/projector.py:72` | **the line was rewritten**, the expression and the behaviour were not. Judged above, deliberately not charged |
| 1 — the `0.05` growth pad, and unreachable | `analysis/projector.py:169` | no — context line, byte-identical. Unreachability proved above (0 of 48 inputs) |
| 1 — `nwc_pcts` empty → `0.0` | `analysis/projector.py:271` | no — the expression is unchanged; only a `sources[...]` assignment was added after it |
| 1 — 10 `: float = 0.0` and 3 conditional zeros in `models/valuation.py` | `models/valuation.py:153,154,229,233,305-316,324,327,342` | no — file count `13` → `13` |
| 1 / 12 — `.get("sharesOutstanding", 0)`, rule 5's second source | `api/routes_valuation.py:408` | no — outside the diff hunks |
| 5 — module-global cache, `pop`ped on read | `api/routes_valuation.py:82,344` | the cache's **contents** changed; the global and the `.pop()` did not, as the assignment requires |
| 6 — five `x / 100 if x else None` | `api/routes_valuation.py:369-373` | no — byte-identical to `35be956` |
| 11 — `BalanceSheet \| None` into a `BalanceSheet` parameter | `api/routes_valuation.py:404,413,414` | no — same errors, shifted lines, set-identical under mypy |
| 26 — `":" in files` · 29 — empty `files` | `api/routes_valuation.py:351` | no — the condition is unchanged inside an edited hunk |
| 8 — blanket `except Exception` (the 5 `BLE001`) | `api/routes_valuation.py` | no — ruff output set-identical |
| backlog `:514` — `analysis/capm.py` imports `ingestion.price_fetcher` | `analysis/capm.py:16` | no — not in scope, not in the diff. Recorded, and the doc says no rule forbids it |
| `cli.py:736` — `getattr(overrides, field_name, None)` | `cli.py:736` | no — `cli.py` is out of scope and untouched; the name is a literal from that file |
| P2b-provider F3 — the provider label is a re-derivation | `api/routes_valuation.py:446` | no — the assignment forbids the fifth cache field and the programmer left it |

## Scope

`git --no-pager diff --stat` → `analysis/projector.py`, `api/routes_valuation.py`,
`models/valuation.py`, and `docs/8-build/phases.md`. The first three are exactly the
round-2 Files in scope. The fourth is the orchestrator's, stated as such in my task and in
the programmer's entry. No template, no `static/`, no `cli.py`, no `ingestion/`, no
`tests/`. **Scope is clean.** The programmer disputes nothing, so there is nothing to
escalate on that ground.

## For the orchestrator

1. **Criterion 13's corrected wording is in the assignment and is the one a tester must
   use.** I confirm the original goes red against correct code. The tester's assertion
   should split the six ratios by the statement that feeds each, exactly as the assignment
   now writes it.
2. **Backlog item 1 keeps the whole defect.** `analysis/projector.py:72,169,271` still
   substitute; this unit labels them and may not remove them. Item 1 also owns the
   asymmetry the programmer names: `analysis/fcff.py` stops on a NaN tax rate while
   `analysis/projector.py` turns it into a confident 0.00% via `max(0.0, min(nan, 0.50))`.
   I reproduced the broader half too — a NaN `sga` gives `operating_margin = nan` labelled
   `derived, obs=2`, with no clamp to expose it.
3. **`analysis/projector.py:169`'s `0.05` is unreachable** — proved above. It is a rule 3
   site that can never fire, which means removing it is free of any number movement. That
   is the cheapest hit in item 1's census and should be named there.
4. **P8b-statements-ui needs four lines in its assignment**, three of which the programmer
   also asks for: head the historical FCFF table *post-adjustment* (F8); render
   `is_computable=False` as words, never a blank cell (round 1); print which statement
   feeds each ratio beside its label; and **F10** — render no statements block, adjustment
   list, FCFF table or label table when `error` is set.
5. **Backlog item 6 should be sequenced before or with P8b**, so a reader's typed `0` is
   not discarded on a page that has just started explaining where every figure came from.

## Verdict

`approved`.

F1 is fixed at its cause, by the fix I named as preferable: `derive_assumptions` now
produces the provenance where the evidence still exists, with three states and not two,
and the route reads it instead of guessing. I reproduced my own round-1 defect case and
all three cash-flow-fed ratios read `substituted` in a sentence carrying `SUBSTITUTED` and
`It is not a measurement.` I re-measured all fifteen criteria myself, including criterion
8 across all three stashed files — identical rendered bytes on five paths, identical share
price, identical enterprise and equity value and WACC — and the three gates are
**set-identical**, not merely equal in count. The `observations` count is the non-zero
length and I proved it with a zero-margin year: it reports `1`, not `2`. The clamp clause
is reachable and states what happened; the pad clause fires only when padding happened;
the `0.05` it pads with is unreachable, pre-existing and untouched, and its unreachability
is what makes the new sentence true. The one coverage miss is the clamp clause body, which
I executed. `cli.py` runs unchanged against the new return value. The programmer's
decision to leave `float(np.mean(non_zero)) if non_zero else 0.0` word for word rather
than restructure it is correct and I endorse it in writing: a rule 3 census that improves
because a line was reworded, while the guess it measures survives, is worse than no census
— the backlog says so in as many words. Both findings are `note`, both are hand-offs, and
neither blocks. Dispatch the tester.
