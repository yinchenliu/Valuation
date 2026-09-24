---
agent: code_reviewer
assignment: P7-low-confidence
round: 1
verdict: changes_requested
---

# Review of P7-low-confidence, round 1

Programmer entry: `.agent/journal/2026-09-22T1900-programmer-p7-low-confidence.md`

Diff: 5 files, +284/−27, exactly the Files in scope. `git status --porcelain` shows the
five and nothing else. `git diff --stat -- tests/` is **empty**. No scope finding.

## The recorded user decision — I checked the citation

`.agent/assignments/P7-low-confidence.md` quotes the decision, dates it **2026-09-22**,
and states its extent: *"It covers the treatment of `low`-confidence non-recurring items
and nothing else."* The citation is present and scoped.

**It waives no rule**, so it excluded no line from my findings. It specifies a behaviour
(`low` → documented, not applied); it does not permit a default, a guess or an unlabelled
constant. I treated every line in the diff under the normal rules. The diff implements
the decision and nothing broader — no second threshold, no setting, no `medium` handling
invented (`analysis/normalizer.py:87-88`).

## The guard checks

Run over the five Files in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | 5 hits, **all pre-existing, none in the diff** (`claude_extractor.py:356`, `cli.py:234,593,1007,1015`) |
| lookup with a fallback — `.get(k, 0)` | ~60 hits. Two sit on lines **this unit rewrote**: `claude_extractor.py:707` → **F1**, `:726` → **F3**. The rest are untouched (backlog item 1) |
| bare or-default — `or 0.0` | 3, `claude_extractor.py:562-564`, untouched |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | `normalizer.py:219` (inside `apply_adjustments`, untouched), `cli.py:738`, `claude_extractor.py:563-564` — all pre-existing |
| dict of functions keyed by data | clean. `_CONFIDENCE_APPLIED`/`_CONFIDENCE_EXCLUDED` are tuples of **strings** tested with `in`; the branch is literal `if/elif/else`. Rule 2 satisfied |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output |

The programmer's entry answers the `:726` hit (their finding 3). It does **not** answer
the `:707` hit — that is F1.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `NonRecurringItem.confidence` in `partition_by_confidence` | **yes** — names value, year, amount, line_item | `c:/tmp/p7rev/crit123.py`: `''`, `'unknown'`, `'HIGH?'`, `'0.9'`, `None`, `0.9`, `'  '` all raise `ValueError` naming the value **and** `2024` **and** `100` **and** `sga` |
| `"confidence"` key in a Pass 2 JSON item | **yes** — names year and description | `c:/tmp/p7rev/parser.py`: `ValueError: Pass 2 returned a non-recurring item with no 'confidence' field: year 2024, 'a charge'…` |
| `"non_recurring_items"` key in the Pass 2 response | **NO — returns `[]`** | `_parse_nri_response('{}')` → `[]`. **F1** |
| `"source"` key in a Pass 2 item | **no** — `''`, rendered `(none cited)` | `claude_extractor.py:726`. **F3** |
| `NonRecurringItem.confidence` on a Python-constructed item | **no** — `"high"` | `models/financial_statements.py:28`. **F4**, latent |
| `item.year` matching no statement | no — discarded | backlog item **25**, `normalizer.py:239`. **I saw it in the file under edit; not this unit's**, as the assignment instructs |

`"LOW"` and `" High "` do **not** raise — deliberate case/space folding, matching
`_resolve_field`'s `line_item.strip().lower()` at `normalizer.py:154`. Reasoned in the
entry's decision table. Not a finding.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | yes. `adjusted_impact` and `amount` are $M throughout; the template header says `Amount ($M)`; the CLI prints `M` on every withheld total |
| percentages converted at the route boundary, once | unchanged — the diff adds no percentage |
| falsy not treated as missing | no new instance. `if excluded:` / `{% if excluded_non_recurring %}` test list emptiness, which is the meaning intended |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | `analysis/normalizer.py` imports `dataclasses` + `models.financial_statements` only. (`analysis/capm.py:16` imports `ingestion` — backlog item **17**, untouched) |
| `normalize_financials` / `apply_adjustments` untouched | **confirmed.** `git diff analysis/normalizer.py` is a single purely-additive hunk `@@ -73,6 +73,77 @@`, entirely above `_resolve_field`. The 145 assertions keep their meaning |

## Done-criteria, re-run

Everything below I executed. Nothing is taken from the entry.

| # | Criterion | Claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | `low` not applied | sga 200.0 unchanged | `applied=0 excluded=1 sga=200.0`; control through the unpartitioned path `sga=100.0` | **yes** |
| 2 | `medium`/`high` applied | sga 100.0; mixed → 170.0 | `medium: sga=100.0`, `high: sga=100.0`, mixed `applied=[10.0,20.0] excluded=[40.0] sga=170.0` (hand: 200−10−20) | **yes** |
| 3 | absent/unknown confidence stops | raises, names value + year | 7 malformed values all raise, each naming value, year, amount and line_item; parser stop names year + description | **yes** |
| 4 | CLI block with source | block as pasted | `c:/tmp/p7rev/cliblk.py` reproduces the pasted block **character for character**, incl. `Source: (none cited)` on an empty source and the empty-list sentence | **yes** |
| 5 | excluded items on the result page | rendered row | my own `TestClient` probe, `c:/tmp/p7rev/route.py`: `2024 \| +120 \| sga \| add_back \| Legal settlement… \| Note 19 - Legal proceedings`. The `high` 40M item is **not** in that table | **yes** |
| 6 | the output says it EXCLUDES them | banner beside headline | `Implied Share Price $33.21 … This price EXCLUDES 1 low-confidence non-recurring item(s) … They were not applied to the financial statements.` | **yes** |
| 7 | LHX effect measured | $411.39 vs $411.39 | see below | **yes**, with F2 on the counterfactual |
| 8 | no assertion changed meaning | `1 failed, 145 passed` | `1 failed, 145 passed`; failure set **diffed against a `git archive 54c5af8` export**: both are the single nodeid `tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`. Not counts — the same test | **yes** |
| 9 | lint 5 / types 14 set-diffed / census 116 / `GET /` 200 | unchanged | ruff **5**, all `BLE001`; set-diff vs baseline → `RUFF SETS IDENTICAL`. mypy **14 in 4 files**; `comm` against the baseline export, line numbers stripped → **both `comm -23` and `comm -13` empty**. census **116**. `GET /` → **200** | **yes** |

### Criterion 7, reproduced from `./cache` — no extraction run, zero tokens

`cli._load_cache` on `cache/.cache_lhx_extraction_inputs.pkl`:

```
input: …\10K_filings\LHX\L3Harris Technologies Inc._10-K_2024_English.pdf
       sha256 7d7ca6485a7eaf8eb698bcea6e081e8c6a70ebc6318852b8ff3d4ca92fa4ae15
items: 15   confidences: Counter({'high': 13, 'medium': 2})
partition: applied=15  excluded=0
applied is elementwise-identical to the raw list: True
```

**The "identical $411.39" claim is not merely reproduced, it is proven by construction.**
`applied` is the same list of the same objects in the same order as the raw Pass 2 list,
so runs A and B are one computation performed twice. The two `medium` items are exactly
as reported (2024 `+15M legal reserve on sga`, `−46M gain on other_operating_expense`).

End-to-end A/B with one deterministic stub `PriceData` reused by both runs
(`c:/tmp/p7rev/ab.py`) — **difference `$0.00`**, and `op margin=11.09%` reproduces the
entry's figure exactly. The absolute `$411.39` depends on a live yfinance fetch I
deliberately did not run; under my stub the pair is `$609.78 / $609.78`. The claim under
test was *identity*, and identity holds.

## Findings

### F1 — `data.get("non_recurring_items", [])`, on a line this unit rewrote, turns a malformed Pass 2 response into "no adjustments" · `major`

**Evidence:** `ingestion/claude_extractor.py:707`; `_parse_nri_response('{}')` → `[]`
(`c:/tmp/p7rev/parser.py`). The line is in the diff — the unit converted the
comprehension clause into the `for` statement of the new loop.

**Rule or document:** `rules.md` rule 3, row "a `.get` with a fallback". A Pass 2 reply
that omits the key and one that returns `"non_recurring_items": []` are the same bytes,
and the run continues with GAAP figures as though the model had found nothing.

**Why it matters more after this unit than before it.** The CLI now prints
`None. Every item the model identified was applied.` and the page prints nothing — both
are positive statements about a parse that did not happen. The unit's whole subject is
telling a reader what was and was not applied; this is the one path on which both outputs
say "nothing was withheld" when the truth is "nothing was read".

The three standard downgrades do not apply: the assignment's "change that one line and
nothing else" is an assignment, and the rule beats the assignment; "the extractor always
supplies the key" is reachability, which is not the test.

**What would fix it:** `if "non_recurring_items" not in data: raise ValueError(...)`
naming the field — four lines, inside the function this unit already rewrote, so it is
not a scope widening. The orchestrator should amend the assignment's "one line" wording.

### F2 — the counterfactual's 1,140M item came from a *different filing*, and grafting it double-counts fiscal 2023 · `major`

**The label itself is fine, and I want that on the record**, because it was the
orchestrator's question: the block is headed `=== COUNTERFACTUAL - not a valuation of
L3Harris ===`, says *"This is a constructed input and I am labelling it as one"*, and the
figures table marks it *"counterfactual; the item's fields come from the journal, not from
the PDF."* Nobody can read `$474.96` as measured. The arithmetic checks:
474.96 − 411.39 = 63.57, and 63.57/474.96 = 13.38% ≈ 13.4%.

**Two things under the label are wrong.**

**(a) Provenance.** The entry says the item was *"in the 20 Sep extraction **of this same
filing**"*. It was not. `2026-09-22T1500-code_reviewer-p6-honest-output.md:300-302`
attributes fiscal-2023's `1,591M with the low-confidence item` (= 451 + 1,140) to **the
FY2025 filing**, and `2026-09-22T1400-programmer-p6-honest-output.md:115,285` identifies
run 1 — the run `lhx_real.txt` is compared against as *"the same PDF"* — as the **FY2025
PDF**. This unit's cache entry is the **FY2024** PDF (sha `7d7ca648…`). Two documents.

**(b) An undisclosed double count.** The FY2024 extraction **already carries the same
charge for the same year**:

```
fiscal 2023, from cache/.cache_lhx_extraction_inputs.pkl:
    +115  sga   high   LHX NeXt implementation costs included in G&A
  … six items, net +744M
grafted: +1,140  sga  low  "LHX NeXt implementation costs and other charges in G&A
                            (components not separately disclosed for 2023)"
run C adjusted EBIT 2023 = 3,310   (GAAP 1,426 + 1,884)
run D adjusted EBIT 2023 = 2,170   (GAAP 1,426 +   744)
```
(`c:/tmp/p7rev/ab.py`, `c:/tmp/p7rev/cf.py`.)

Run C normalises one fiscal year with a coarse aggregate from one document **plus** the
itemised reading of part of the same charge from another. The entry notices the 744 and
presents it as a correctness check — but 744 is run D; run C is the 1,884 it contrasts
against. So `$63.57 / 13.4%` is not "what one `low` item is worth"; it is what a
double-counted graft is worth. My reproduction gives the same op margins (13.05% vs
11.09%) and −12.9% under a stub market series, so the *direction* is real and the
*magnitude* is not defensible.

**Rule or document:** no code rule — nothing ships. But it is the repository's own
standard applied to its own record: a constructed number that reads as a quantity will be
quoted as one, and this one will be, because criterion 7 is the assignment's stated point.

**What would fix it:** correct the provenance sentence to name the FY2025 filing, and
either drop the `+115M` item from run C before grafting, or state in one line that run C
double-counts the 2023 LHX NeXt charge and that `13.4%` is therefore an upper bound.

### F3 — `source=item.get("source", "")`, also on a rewritten line, conflates "cited nothing" with "dropped" · `minor`

**Evidence:** `ingestion/claude_extractor.py:726`; `_parse_nri_response` on an item with
no `source` key returns `''` (`c:/tmp/p7rev/parser.py`).

**Rule or document:** rule 4's edge. It reaches no number, so rule 3's stop-test does not
bite; but the cited source is the one thing the excluded block exists to give a reader,
and `(none cited)` cannot say which of the two happened.

**The programmer named this** (their finding 3, and their rule-3 table), so it is a
recorded question, not an unanswered one — hence `minor`. Its root is
`models/financial_statements.py:29 source: str = ""`, which is out of scope. Same unit as
F4.

### F4 — `models/financial_statements.py:28` still defaults `confidence` to `"high"` · `minor`, and it needs a backlog item

**Evidence:** `models/financial_statements.py:28` — `confidence: str = "high"`.

**My ruling on how much of the user's decision this leaves open: the type, not the
pipeline.** I traced every live construction of a `NonRecurringItem`. There is exactly
one in pipeline code — `_parse_nri_response`, which now stops. The cache path unpickles a
stored field, so it cannot hit the default. `api/` and `cli.py` construct none. So on
**every path a user can reach today**, an unstated confidence stops the run and the user's
decision is fully in force. The default is reachable only from `tests/` (F5) and from code
not yet written.

That is latent, not open — but it is the last place in the chain where absence becomes the
*strongest* reading, and "unreachable code that quietly returns a value" is precisely what
the assignment's step 3 removed one layer up. **Backlog item: yes.** It is a `models/`
change (drop the default, make the field required) whose blast radius lands in `tests/`,
so it is one unit of `models/` plus a tester — not a patch.

**The programmer was right to stop.** The assignment said *"If you believe it needs a
change, stop and say so"*, and they did, in their own words, as a finding against their
own unit. I am not treating that as a defect in the unit.

### F5 — five dev scripts under `tests/` now misrepresent what the pipeline does · `minor`, and it needs a backlog item

**Evidence:** `grep -rn "normalize_financials" tests/` →
`test_e2e_abbv.py:136`, `test_e2e_abbv_3years.py:115`, `test_e2e_googl_3years.py:130`,
`test_e2e_lly.py:136`, `_run_lly_dcf.py:21` — all pass the raw Pass 2 list.

**My ruling: yes, they now misrepresent it, and the misrepresentation is new.** Before
this unit they computed what the pipeline computed. After it they apply `low`-confidence
items the CLI and the web app withhold, print no excluded block, and so produce a share
price for a real filing that **neither entry point would produce**, with nothing on screen
saying the two disagree. These are the scripts a reader points at a real PDF. They are
`tests/`, out of scope, write-guarded — so not a finding against the unit, but the
divergence is real and dated from this commit. One tester unit adds
`partition_by_confidence` to all five and pins the CLI's excluded block.

### F6 — the page says nothing when nothing was excluded; the CLI says so in words · `note`

**Evidence:** `templates/valuation_result.html:145` `{% if excluded_non_recurring %}`
renders no block at all on an empty list; `cli.py:655` prints
`None. Every item the model identified was applied.`

Breaks no rule. But it is the programmer's own stated reason applied unevenly — their
cli.py decision table says *"a blank space is indistinguishable from a block that failed
to render"*. On the real LHX run that sentence is what made criterion 7's null result
legible; a web reader of the same run gets silence.

### F7 — a comment this unit moved the referents of, and whose premise it overtook · `note`

**Evidence:** `api/routes_valuation.py:292-294` still reads *"carrying the
ProviderResolution alongside the financials in `_extraction_cache` (`:31`, written at
`:102` … read at `:148-154`), which is backlog item 5 and outside this unit's Files in
scope."* The declaration is now `:38`, the write `:115`, and this unit **did** carry a
second value alongside the financials.

## The cache tuple and backlog item 5

**It does not widen item 5**, and the route tests pass for a reason that does not cover
it. Both verified:

- Three call sites, all in `api/routes_valuation.py` (`:38`, `:115`, `:194-195`). No new
  global, no new `pop`, no new consumer, no new lifetime. The value's shape changed; the
  cache's shape did not.
- `tests/unit/test_routes.py:268` rebinds `_extraction_cache` to `{}` before every test,
  and `:40` says so on purpose. Every `POST /valuation` test therefore takes the **extract
  branch**. The tuple unpack at `:195` is executed by **no test in the suite**. That is
  correct behaviour for those tests and a gap for the tester, not a defect here.
- I exercised the hit branch myself (`c:/tmp/p7rev/route.py`): `GET /assumptions` →
  `cache value type: tuple len 2 -> FinancialStatements, 1 excluded`, cached
  `sga = 760.0` (800 − 40 applied, 120 withheld — hand arithmetic), then
  `POST /valuation` → 200 with the excluded block present **and** the cited source intact.

One thing the tester should know: the excluded table's `<tbody>` sits at template line 169,
**after** the projection table's at line 92, so `_projection_row`'s "the one `<tbody>`"
helper still finds the right table when a test finally supplies a `low` item. Verified by
line order, not by hope.

## Layering and the LLM boundary

`docs/2-rules/llm-boundary.md` read, as required. The model produces no number in this
diff; the change to `ingestion/` **removes** a default and adds a stop, and touches no
prompt, schema field or client. The decision `low → not applied` is literal Python in
`analysis/normalizer.py`, which is where rule 1 puts it — before this unit `analysis/`
did not decide, it applied whatever it was handed. The boundary moved in the direction
the rule points.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 25 — adjustment whose year matches no statement | `analysis/normalizer.py:239` | no. **I saw it, in the file under edit**, and left it |
| 1 — 116 zero-default sites | `ingestion/claude_extractor.py:325-683` etc. | no. Census re-measured at **116** |
| 17 — `analysis/` imports `ingestion/` | `analysis/capm.py:16` | no |
| 5, 6, 8, 26, 29 | `api/routes_valuation.py` | only item 5's declaration line; see above |
| 36's schema half — no confidence field outside `NonRecurringItem` | — | no, correctly escalated as out of scope |

## For the tester, not findings

`partition_by_confidence` adds ~20 statements to `analysis/normalizer.py` with **no test**
— the assignment records `analysis/` at 255/255 statements and 80/80 branches before this
unit, and that will have fallen. Criterion 9 does not gate coverage, and `tests/` was
write-guarded for the programmer, so this is the next unit's, not a defect here.

## Verdict

`changes_requested`

**F1 and F2 stand.** F1 is rule 3 on a line this diff rewrote, and it is the one path on
which both of this unit's new outputs make a positive false statement — "nothing was
withheld" about a Pass 2 reply that was never read. F2 is not a code defect and the
counterfactual's label is genuinely unmistakable, but the entry's own record of where the
1,140M item came from is wrong, and the `13.4%` it reports is inflated by a fiscal-2023
double count the entry does not disclose; criterion 7 is the assignment's stated point, so
that record has to be right before it is accepted.

**Everything the unit was commissioned to do, it did, and I verified all nine criteria by
execution rather than by reading the entry.** The partition is correct and sound on seven
malformed inputs, `normalize_financials` and `apply_adjustments` are genuinely untouched,
the parser stop names the year and the description, both outputs say "NOT applied" in as
many words with the cited source beside each item, the cache tuple works on the path a
real user takes without widening item 5, and all four gates are unchanged as **sets**, not
as counts. F4 and F5 are the two things the programmer stopped on rather than widened
into; both were the right call under the assignment, and **both need backlog items** —
F4 as a `models/`-plus-tester unit, F5 as a tester unit over the five scripts.
