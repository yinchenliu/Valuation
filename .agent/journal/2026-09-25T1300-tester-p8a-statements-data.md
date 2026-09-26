---
agent: tester
assignment: P8a-statements-data
round: 1
status: complete
files_touched: [tests/unit/test_projector_sources.py, tests/unit/test_historical_fcff_year.py, tests/unit/test_route_context_keys.py, tests/unit/test_normalizer_stops.py, tests/unit/test_projector_rule3_red.py]
verdict: pass
escalation: "a rule-3 stop in the file this unit edited names nothing and is NOT in the backlog — analysis/projector.py:162 raises a bare IndexError on an extraction with no income statements. It is the exact twin of backlog item 14, closed at ff632df in analysis/dcf.py. Stated red at tests/unit/test_projector_rule3_red.py. See 'Findings for the orchestrator'."
---

# P8a-statements-data — every provenance label verified by hand, and a bare `IndexError` found in the same function

## What I did

Verified the five things the assignment names, each against arithmetic derived
before the code was run: the substituted origin on a filing with no cash flow
statements, the observation count under both of the module's counting rules,
the derived origin naming the right integer, criterion 13 in its **corrected**
wording, and `HistoricalFCFFYear` for a year whose cash flow statement is
absent. I added the two done-criteria nobody could measure without a test (6 and
7, the six context keys on all five rendering branches), and I checked criterion
14 independently by running `derive_assumptions` from `35be956` and from
`6e58f13` over four stubs and diffing. Along the way I closed the projector's
one uncovered line honestly — by deriving a tax rate of 80% and asserting the
clamp clause — and found that `partition_by_confidence`, which this unit's route
calls before it normalises anything, had **zero** covered statements in its loop
body. I wrote no assertion that pins a rule-3 fallback; where the code defaults
instead of stopping, the `file:line` is named below and nothing is asserted in
either direction.

## Done-criteria

Re-measured at `6e58f13` with my tests added. The gate figure rises because I
added tests; every other figure is unchanged.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | cache holds four named fields | **pass** | `grep -n "class CachedExtraction" api/routes_valuation.py` → `38:`; `grep -n "dict\[str, CachedExtraction\]"` → `82:` |
| 2 | test gate | **pass** | `pytest -q --ignore-glob="*_rule3_red.py"` → `145 passed` before my work, `179 passed` after (+34 tests, 0 failures) |
| 3 | no new lint error | **pass** | `ruff check . --output-format=concise \| grep -oE "[A-Z]+[0-9]+" \| sort \| uniq -c` → `5 BLE001`, and `Found 5 errors` |
| 4 | no new type error | **pass** | `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` → `Found 14 errors in 4 files (checked 18 source files)` |
| 5 | `GET /` still 200 | **pass** | the TestClient one-liner → `200` |
| 6 | six context keys on `GET /assumptions`, incl. error branch | **pass** | `tests/unit/test_route_context_keys.py` — three branches: success, extractor raised, no filing named |
| 7 | six keys on `POST /valuation`, both branches | **pass** | same file — success, error, **and** the cache-hit branch with the extractor closed so a re-extraction fails loudly |
| 8 | no number on either page moved | **not re-verified by me** | I verified its `analysis/` half as criterion 14 below. The route half needs the pre-P8a `routes_valuation.py`, whose shape changed; the programmer's pasted share prices stand unchallenged but unconfirmed |
| 9 | no new conditional zero in the route | **pass** | the item-1 grep over `api/routes_valuation.py` → `1`. Item 1's census records `api/` at 2, so it fell |
| 10 | no `getattr` on a variable name | **pass** | `grep -c getattr api/routes_valuation.py` → `0` |
| 11 | a ratio with no filing data is substituted | **pass** | `test_the_three_cash_flow_ratios_are_substituted_when_no_cash_flow_was_extracted` |
| 12 | a derived ratio names how many years | **pass** | `test_the_income_statement_ratios_are_still_derived_with_no_cash_flow_statement` (2), `test_a_year_whose_margin_is_zero_is_not_counted_as_an_observation` (1 and 2 in one call) |
| 13 | the page cannot contradict itself, CORRECTED wording | **pass** | `test_the_two_pages_agree_on_every_fixture_in_this_file`, `test_no_cash_flow_statement_makes_the_bottom_three_substituted_and_the_top_three_derived` |
| 14 | no existing assumption value moved | **pass** | ran `C:/tmp/p8a_cmp.py` against `35be956`'s `analysis/projector.py` + `models/valuation.py` and against `6e58f13`, over four stubs (complete, no cash flow, supplied zeros with a clamped 90% tax rate, single year). `diff` → identical, 65 lines each |
| 15 | one home for the labels | **pass** | `grep -c "_SOURCE_SUPPLIED\|_SOURCE_DERIVED\|_all_derived_assumption_sources" api/routes_valuation.py` → `0` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Never assert the substituted **value** (`0.0`); assert instead that the sentence names whatever figure was used | `docs/5-testing/strategy.md` §2.1 "never assert a fallback". The zero is `analysis/projector.py:72`, `:90`, `:271` — backlog item 1 | `assert out["da_pct_revenue"] == 0.0` makes item 1 permanent and turns its fix red. `assert f"{out[ratio]:.2%}" in detail` states the real requirement — the label must be truthful about the figure it labels — and survives any default the fix picks |
| Assert the integer observation counts (1, 2) **and** the value they imply | the assignment: "compute by hand how many years feed each of the six ratios, and assert the integers" | an integer alone could be satisfied by a constant; a value alone cannot see an overstated count. `_one_zero_margin_year` returns 1 for two ratios and 2 for three others in the same call, which no constant satisfies |
| Add a closed-form bound, `observations <= len(financials.years)`, over every fixture | it holds whatever the inputs, so it does not go stale with a fixture | a count taken from `projection_years` (5 by default) rather than from the data passes every single-fixture test and fails this one |
| Reach `analysis/projector.py:214` with a derived 80% tax rate rather than leave the line uncovered | the assignment put closing that gap in scope "if you can reach that line honestly" | 8 / 10 = 0.80 is checkable on paper and the clamp to 0.50 follows from the band named at `:34-35`. No fixture was reverse-engineered from a printed output |
| Write **one** red test, for the bare `IndexError`, and **not** one demanding `derive_assumptions` stop on a missing cash flow statement | the second is backlog item 1, which the assignment defers explicitly and whose resolution (stop, versus label-and-continue) is an orchestrator decision, not mine. The first has a closed precedent — item 14 — and no recorded decision at all | a red test that contradicts an accepted design decision is scope creep wearing a rule's clothes. A red test for an unrecorded defect with a precedent is exactly what `docs/5-testing/strategy.md` §4 describes |
| Add three tests to `tests/unit/test_normalizer_stops.py` although the normalizer is outside my assignment | its `partition_by_confidence` loop body was **0% covered**, and `api/routes_valuation.py:219` — a line this unit wrote — calls it | the alternative was to report the hole and leave the one decision that says whether a 1,140M add-back moves a valuation (backlog item 36) untested for another unit |
| Put the new tests in three new files rather than extend `test_projector.py` and `test_routes.py` | each file states one unit's requirements and carries the reasoning for them | a reader looking for "what P8a claims" finds it in one place |

**No test was weakened, skipped or `xfail`ed, and no implementation file was
edited.** The mutation runs below were done on a copy under `c:/tmp/`.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `NonRecurringItem.confidence` (`analysis/normalizer.py:131`) | **stops and names `confidence`**, the offending value, the year and the description | `test_an_unrecognised_confidence_stops_the_run` — new, green, inside the gate |
| `NonRecurringItem.line_item` | **stops and names `line_item`** | `test_an_unrecognised_line_item_stops_the_run`, pre-existing, re-run green |
| `NonRecurringItem.direction` | **stops and names `direction`** | `test_an_unrecognised_direction_stops_the_run`, pre-existing, re-run green |
| `income_statement.effective_tax_rate` as NaN, into `calculate_fcff_historical` | **stops and names `tax_rate (tax_rate_override or income_statement.effective_tax_rate)`** | `analysis/fcff.py:39-44`; pinned by `tests/unit/test_fcff.py`, re-run green |
| `financials.income_statements` empty, into `derive_assumptions` | **stops, but names NOTHING** — `IndexError: list index out of range` | `analysis/projector.py:162`. **RED**: `tests/unit/test_projector_rule3_red.py`. Rule 3 requires both halves |
| `financials.cash_flow_statements` empty, into `derive_assumptions` | **defaults to `0.0`** for `da_pct_revenue`, `capex_pct_revenue`, `nwc_pct_revenue` | `analysis/projector.py:72` (`else 0.0`) and `:271` (`if nwc_pcts else 0.0`). **Backlog item 1**, deferred by the assignment. Not asserted in either direction. This unit's labelling is a mitigation, not the fix |
| a revenue of 0 or a one-year window, into `_historical_cagr` | **defaults to `0.0`** growth | `analysis/projector.py:89-90`. Same item. The label now says SUBSTITUTED, which is what I pinned instead |
| `IncomeStatement.ebt` of 0, into `effective_tax_rate` | **defaults to `0.0`** | `models/financial_statements.py:101`. Backlog item 1. My `_one_zero_margin_year` fixture routes *around* it (interest income 10, so EBT is 10 and the 0.00 rate is a real division) precisely so that no assertion of mine rests on it |
| `latest_is.diluted_shares_outstanding == 0`, in `run_valuation` | **falls back to yfinance**, mid-pipeline, behind an inline import | `api/routes_valuation.py:406-408`. Rule 5 violation, pre-existing and recorded. Left uncovered on purpose, as `docs/5-testing/strategy.md` §4 says those arcs are |

**Two "defaults to" rows are findings against the file this unit edited.** Both
are backlog item 1 and both were explicitly deferred; the unit's own change made
them *visible* rather than fixing them, which is what the SUBSTITUTED label is.

## Measurements

**Suite, as failure sets:**

| | before my work | after |
|---|---|---|
| `pytest -q --ignore-glob="*_rule3_red.py"` | `145 passed` | `179 passed` |
| failures inside the gate | {} | {} |
| red, outside the gate | {`test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`} | {that one, `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`} |
| `ruff check .` | 5, all `BLE001` | 5, all `BLE001` |
| `mypy … --ignore-missing-imports` | 14 in 4 files | 14 in 4 files |
| `GET /` | 200 | 200 |

**I re-ran `tests/unit/test_dcf_rule3_red.py` and it is still red** — backlog
item 2 is still open, so it is correctly still outside the gate. No red test in
this repository has gone green and been left inside the excluded pattern
(backlog item 24's failure mode).

**Coverage**, `pytest -q --ignore-glob="*_rule3_red.py" --cov=analysis
--cov=models --cov=api --cov-branch --cov-report=term-missing`:

| File | before | after |
|---|---|---|
| `analysis/projector.py` | 113 of 114 stmts, missing `214` | **114 of 114 stmts, 36 of 36 branches** |
| `analysis/normalizer.py` | 43 of 49 stmts, missing `131-137` | **49 of 49 stmts, 22 of 22 branches** |
| `analysis/` overall | 307 of 314 stmts | **314 of 314 stmts, 100 of 100 branches** |
| `api/routes_valuation.py` | 119 of 132, missing `91, 120-121, 148, 207, 344-348, 406-408` | **124 of 132**, missing `91, 120-121, 148, 207, 362->365, 406-408` |
| TOTAL (`analysis` + `models` + `api`) | 721 of 757 stmts | **733 of 757 stmts; 134 branches, 7 partial** |

`344-348` is the cache-hit branch; it is now covered, by a test that closes the
extraction boundary so the miss branch cannot silently supply the same answer.
`148` is the `"income statement"` arm and is **provably dead**: `years` is built
from `income_statements` (`models/financial_statements.py:276-282`), so
`get_income_statement(year)` cannot return `None` for a year in `years`. That is
the reviewer's F4 and **I agree with "leave it"** — it is required type
narrowing and removing it adds a fifteenth mypy error. `406-408` is the yfinance
share-count fallback and stays uncovered on purpose.

**Proof the tests can fail.** Eleven mutations, each applied to a copy of the
tree under `c:/tmp/p8a_mut/` and reverted, never to the repository:

| # | Mutation | Tests red |
|---|---|---|
| M1 | `_source_for` always returns `derived` (finding F1 rebuilt) | 8 |
| M2 | `observations = len(values)` instead of `len(non_zero)` | 3 |
| M3 | a year with a missing statement is dropped (`cli.py`'s bare `continue`) | 3 |
| M4 | the clamp clause is never appended | 2 |
| M5 | the NWC branch counts non-zero values only | 1 |
| M6 | `_historical_cagr`'s guard reports 2 observations instead of 0 | 2 |
| M7 | `historical_fcff` dropped from the `POST` error context | 1 |
| M9 | low-confidence items are applied instead of withheld | 5 |
| M10 | an unknown confidence defaults to `high` instead of stopping | 1 |
| M11 | the cache-hit branch hands the raw statements on as the normalised ones | 1 |
| M12 | `applied_non_recurring` is dropped from both contexts | 3 |

Every mutation was caught; the baseline restored to 55 passed each time. Zero
would have been a finding about my tests.

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `da/capex/nwc` origin on a filing with no cash flow statements | `substituted`, `observations == 0` | **hand derivation from the source**, `analysis/projector.py:228-231`, `:244-246`, `:265-268`: each loop body runs only when `get_cash_flow(y)` is truthy; `cash_flow_statements` is `[]`, so `get_cash_flow` returns `None` for both years and all three lists stay empty. Zero observations is the definition of substituted |
| the substituted sentence | contains `SUBSTITUTED` and `It is not a measurement.` | the assignment's round-2 origin table, "the sentence must say" column |
| the substituted sentence names its figure | `f"{value:.2%}" in detail` | **closed-form identity**: a label must be truthful about the figure it labels, whatever that figure is. Chosen so no `0.0` is pinned |
| `operating_margin` on the income-only stub | `0.25`, `observations == 2` | **hand arithmetic**: margins 20/100 = 0.20 and 60/200 = 0.30; neither is zero so neither is dropped; (0.20 + 0.30) / 2 = 0.25 |
| `tax_rate` on the income-only stub | `0.25`, `observations == 2` | **hand arithmetic**: 4/20 = 0.20 and 18/60 = 0.30; EBT = EBIT because no interest line is set; (0.20 + 0.30) / 2 = 0.25 |
| `revenue_growth_rates` on the income-only stub | `[1.00] * 5`, `observations == 2` | **hand arithmetic**: lookback = min(3, 2 − 1) = 1; (200/100)^(1/1) − 1 = 2 − 1 = 1.00. Two endpoints feed a CAGR, so 2 |
| `operating_margin` and `tax_rate` on the zero-margin stub | `0.30` / `0.20`, `observations == 1` | **hand arithmetic**: margins 0/100 = 0.00 and 60/200 = 0.30 → non-zero list `[0.30]`, mean 0.30, count 1. Tax 0/10 = 0.00 and 12/60 = 0.20 → `[0.20]`, mean 0.20, count 1. **1, not 2** |
| `da/capex/nwc` on the zero-margin stub | `0.15` / `0.10` / `0.04`, all `observations == 2` | **hand arithmetic**: (0.10+0.20)/2, (0.05+0.15)/2, (0.02+0.06)/2 |
| `da_pct_revenue` on the zero-D&A stub | `0.20`, `observations == 1` | **hand arithmetic**: 0/100 = 0.00 dropped, 40/200 = 0.20 kept → one value, mean 0.20 |
| `nwc_pct_revenue` on the same stub | `0.03`, `observations == 2` | **hand arithmetic**: the NWC branch takes a plain mean, so the zero counts: (0.00 + 0.06) / 2 = 0.03. Same two years, different count — the two rules separated |
| `capex_pct_revenue` on the same stub | `0.10`, `observations == 2` | **hand arithmetic**: (0.05 + 0.15) / 2 = 0.10. The control |
| `observations <= len(financials.years)` on every fixture | true | **closed-form identity**: a ratio cannot be fed by more filing-years than were extracted |
| `derived` ⟺ `observations > 0` on every source | true | **closed-form identity**, from the assignment's three-origin table. It is the unit, in one biconditional |
| tax rate on the 80% stub | `0.50`; origin still `derived`; detail names `80.00%`, `50.00%`, `0%`–`50%` | **hand arithmetic**: EBIT = 100 − 90 = 10; EBT = 10; 8/10 = 0.80; `max(0.0, min(0.80, 0.50))` = 0.50. The band is named at `analysis/projector.py:34-35` |
| supplied tax rate of 0.90 | `0.50`; origin still `supplied` | **hand arithmetic** + the round-2 rule that the clamp is not a fourth origin |
| padded growth label | `4 year(s)`, `2 rate(s)`, `REPEATED` | **hand derivation**: two rates supplied, `projection_years` 4 |
| a 1-year filing's growth origin | `substituted` | **hand derivation**: lookback = min(3, 1 − 1) = 0 → `periods <= 0` guard at `:89` |
| `HistoricalFCFFYear` for 2023 with no cash flow | `is_computable=False`, `fcff=None`, `missing_statements == ("cash flow statement",)` | **hand derivation** from `api/routes_valuation.py:142-161` and `models/financial_statements.py:290` |
| 2024 FCFF on that fixture | `240.0` | **hand arithmetic** from `analysis/fcff.py:54`: CFO = 200 + 100 + 0 − 40 + 0 = 260; t = 50/250 = 0.20; interest add-back 50 × 0.80 = 40; CapEx = \|−60\| = 60; **260 + 40 − 60 = 240.0**. Cross-checked a second way: 260 − 60 = 200 operating-less-investing, + 40 financing add-back = 240 |
| 2024 EBIT on that fixture | `300.0` | **hand arithmetic**: 1000 − (600 + 100) = 300 |
| both-complete fixture FCFFs | `19.0` and `40.0` | **hand arithmetic**: (16 + 10 − 2) − 5 = 19; (42 + 40 − 12) − 30 = 40. No interest line, so the add-back term is 0 in both |
| an empty `FinancialStatements` gives `[]` rows | `[]` | **hand derivation**: no income statement means no extracted year. Asserted as "no rows", explicitly **not** "a row of zeros" |
| `AssumptionSource` / `HistoricalFCFFYear` default nothing | every `dataclasses.Field.default is MISSING` | **the assignment**, round 2 steps 2 and 8, and rule 3 |
| raw vs normalised 2024 EBIT through both routes | `240.0` and `280.0` | **hand arithmetic**: SG&A 960; an `add_back` of 40 on an expense line moves the field down by 40 (`_FIELD_EARNINGS_SIGN["sga"] = -1`), so SG&A → 920 and EBIT → 1200 − 920 = 280. The withheld item is 500, so a leak would read 780 |
| the six context keys on five branches | present; `None`/`[]`/`{}` on the error branches | **the assignment**, step 7: "Empty lists and `None`, never absent" |
| `assumption_sources` has 0 or exactly 6 entries | never partial | **the assignment**, round 2 step 10, stated as a contract in the route |
| criterion 14, eight keys before and after | byte-identical JSON | **independent execution of the pre-unit code** at `35be956`, not of the post-unit code. This is the one row whose expected side is a program output, and the program is the *previous* revision, which is what "no value moved" means |

No filing page was read: nothing in the code under test opens a PDF. No
assertion in any of these files took its expected value from running
`6e58f13`.

**Two counts, with their units.**

- **Accuracy: 187 of 187 assertion statements match** (75 + 48 + 56 in the three
  new files, 8 added to `test_normalizer_stops.py`), across 34 new green tests.
  Several sit inside loops over 3 or 6 ratios, so the executed count is higher;
  187 is the static count. **0 mismatches.** One further test, 3 assertions, is
  red on purpose in `tests/unit/test_projector_rule3_red.py`.
- **Coverage: 10 of 10 functions and dataclasses this unit added or changed are
  exercised** — `_Derived`, `_historical_average`, `_historical_cagr`,
  `_source_supplied`, `_source_for`, `derive_assumptions`, `AssumptionSource`,
  `HistoricalFCFFYear`, `CachedExtraction`, `_historical_fcff_by_year`. **Of
  branches: `analysis/projector.py` is 36 of 36; `_historical_fcff_by_year` is
  3 of 4, the fourth (`api/routes_valuation.py:148`) being unreachable by
  construction.** `analysis/` as a whole is 314 of 314 statements and 100 of 100
  branches.

## What I did not do

- **Criterion 8.** I did not re-run the full stubbed valuation against
  `35be956`'s `api/routes_valuation.py`, because that file's shape changed and
  the comparison would have been between two different call signatures rather
  than between two numbers. I verified its `analysis/` half instead, as
  criterion 14, which is the half where a moved number would have come from.
  The programmer's pasted share prices are unconfirmed by me.
- **I wrote no red test for backlog item 1's appearance in this file**
  (`analysis/projector.py:72`, `:90`, `:271`). Whether the fix is "stop" or
  "label and continue" is an orchestrator decision, and this unit's labelling is
  the recorded interim answer. The three sites are in the rule-3 table above.
- **`api/routes_valuation.py:91, 120-121, 207` stay uncovered.** `91` is a
  malformed `files` string, `120-121` is the no-valid-year fallback that sits
  beside backlog item 26, `207` is the legacy `file_path` branch. None is this
  unit's and each would need a decision about the item-26 condition first.
- **I did not fix anything.** No file outside `tests/` was edited.

## Findings for the orchestrator

1. **NEW, unrecorded — `analysis/projector.py:162` stops without naming the
   field.** On a `FinancialStatements` with no income statements,
   `lookback = min(3, len([]) - 1) = -1`, and `revenues[-1 - (-1)]` and
   `revenues[-1]` both index an empty list: `IndexError: list index out of
   range`, before `_historical_cagr`'s own guard is reached. Rule 3 requires the
   stop **and** the name. This is the exact twin of **backlog item 14**, closed
   at `ff632df` in `analysis/dcf.py` by turning the same bare `IndexError` into
   a `ValueError` naming the empty input, and it is not in the backlog for
   `analysis/projector.py`. It is reachable: item 1 makes an extraction that
   returned nothing produce empty lists, and `api/routes_valuation.py`'s blanket
   `except Exception` (item 8) renders `str(e)`, so what a user sees today is the
   words "list index out of range" on the assumptions page. Stated red at
   `tests/unit/test_projector_rule3_red.py`; the fix is one `raise` and the test
   goes green, at which point it must be **moved into
   `tests/unit/test_projector_sources.py`** or the gate will never run it
   (backlog item 24).

2. **`analysis/normalizer.py:125-137` had zero covered statements at
   `6e58f13`.** `partition_by_confidence` was added at `7354698` — the unit that
   decides whether a non-recurring item moves the valuation or is withheld from
   it, the direct answer to backlog item 36 — and **no test called it with a
   non-empty list**. Its rule-3 stop, its case folding and the medium/low split
   were all unexercised. I have covered them (3 tests, 8 assertions, now inside
   the gate), but the gap reaching an accepted unit is worth a note against
   whoever tested `7354698`.

3. **`docs/5-testing/strategy.md` §4 is stale.** It states `analysis/` at "255 of
   255 statements, 80 of 80 branches", measured at `6cf34d3`. It is **314
   statements and 100 branches** at `6e58f13`, still 100% of both. The "tests
   collected 146 / 145 pass" line is now **181 collected / 179 pass**. Its warning that a second
   red test means a real regression also needs qualifying: there are two red
   tests now, and the second is deliberate.

4. **Reviewer finding F4: I agree, leave it.** `api/routes_valuation.py:148`,
   the `"income statement"` arm, is unreachable — `FinancialStatements.years`
   is built from `income_statements` alone
   (`models/financial_statements.py:276-282`), so `get_income_statement(year)`
   cannot be `None` for a year in `years`. The `is None` check is required type
   narrowing and deleting it adds a fifteenth mypy error. It is the one branch
   of this unit's new code no honest test can reach, and my entry records it
   rather than my reaching it dishonestly.

5. **Reviewer finding F8, confirmed for `P8b-statements-ui` to cite.** The
   historical FCFF row is a hybrid: `calculate_fcff_historical` takes EBIT and
   the effective tax rate from the **normalised** income statement and CFO and
   CapEx from the **unadjusted** cash flow statement, because the route builds
   the table from the normalised statements and `normalize_financials` only ever
   replaces `income_statements` (`analysis/normalizer.py:245`). So the row is
   post-adjustment on its income-statement inputs and pre-adjustment on its
   cash-flow inputs, and `P8b` must head that table post-adjustment and say so.
   None of my FCFF value assertions depends on it: the fixtures that assert a
   figure carry no non-recurring items, and the route test that carries them
   asserts the rows exist and are computable, not what they equal.

6. **Backlog item 6's effect on the label is as the assignment said, and it is
   visible now.** A reader who types `0` into a form field reaches
   `api/routes_valuation.py:216-220`'s `x / 100 if x else None`, arrives as
   `None`, and is labelled **substituted** — "Nothing from the filing fed this
   figure" — when in fact the reader supplied it. `derive_assumptions` itself
   honours a supplied `0.0` correctly (`tests/unit/test_projector.py`, five
   tests), so the defect is entirely at the route boundary. The new provenance
   scheme does not create it, but it does make it **printable**, which raises its
   cost: phase 4 now has a user-visible false sentence to fix, not only a wrong
   number.
