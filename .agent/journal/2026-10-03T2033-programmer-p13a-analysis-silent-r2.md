---
agent: programmer
assignment: P13a-analysis-silent
round: 2
status: complete
files_touched: [analysis/wacc.py]
---

# P13a-analysis-silent round 2: `calculate_wacc` also stops on a market cap that is not positive

Review answered: `.agent/journal/2026-10-03T2031-code_reviewer-p13a-analysis-silent.md`.
Round 1 entry: `.agent/journal/2026-10-03T2021-programmer-p13a-analysis-silent.md` (not edited).
Assignment: step 2, "Round 2 amendment" (`.agent/assignments/P13a-analysis-silent.md:60-67`).

## What I did

I added one guard to `calculate_wacc` (`analysis/wacc.py:231-244`, after the sum check at `:215-229`). When
`equity_value <= 0`, it raises a `ValueError` that names `market_cap` and its value. The
message says the weights E / (E + D) and D / (E + D) cannot be formed from it, and that
they are not set to 0.0 / 1.0. It states no cause. The sum check is kept, unchanged.
`analysis/normalizer.py` is unchanged from round 1.

## Answers to the review, by number

| # | Finding | Answer |
|---|---|---|
| F1 | major: `market_cap == 0` with debt returns 0.0 / 1.0 | **Fixed** per the amendment. (0, 100) and (−5, 100) now stop with the market_cap message. (300, 100) still gives 0.75 / 0.25. Measured below as criteria 3b, 3c and 4. No new red test. |
| F2 | note: `api/routes_valuation.py:411` cites `normalizer.py:245`, which is now 273 | **Acknowledged.** `api/` is out of scope; not edited. I reported it as round 1 finding 2. |
| F3 | note: backlog item 38's "second face" wording | **Acknowledged**: it is yours to restate. My round 1 measurements of (a) silent 1.0 / 0.0 with an override and zero debt lines, and (b) `AttributeError` at `wacc.py:211` for `balance_sheet=None`, stand. After the round 2 guard, (a) with `market_cap > 0` is unchanged, because the new guard does not touch it. |

## Done-criteria (re-run of 3-7, plus 1-2, on a fresh isolated tree)

Isolated tree: `git archive 0021845 | tar -x -C <scratchpad>/iso2`, then only
`analysis/normalizer.py` and `analysis/wacc.py` were copied in.
`diff -rq <scratchpad>/old <scratchpad>/iso2` lists exactly those two files. The only other
line is `extractions`, which exists only in `old`. Scripts are in
`/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/5a3eb59a-dd70-43de-8ee8-c16bbd7dd61e/scratchpad/`.
The `crit34.py` runs pass `cost_of_debt_override=0.05`; `crit34b.py` is the same without
the override. The shared tree was not disturbed.

| # | Criterion | Result | Evidence (iso2) |
|---|---|---|---|
| 1 | an item for a year with no statement stops | pass | `crit12.py 2019 add_back` → `ValueError: 1 non-recurring item(s) carry a year with no income statement in the financials: year 2019, line_item 'sga', description 'Restructuring charge, Note 12'. The income statement years are [2023, 2024]. ...` |
| 2 | an item for a matching year still applies | pass | `crit12.py 2024 add_back`: 2024 sga 150.0, ebit 250.0; 2023 sga 200, ebit 200. `remove`: 2024 sga 250.0, ebit 150.0 |
| 3 | sum == 0 stops, naming both inputs and values, no cause | pass | (0, 0) → `ValueError: market_cap is 0.00 and balance_sheet.total_debt is 0.00 (year 2024), so their sum is 0 and the capital weights E / (E + D) and D / (E + D) cannot be formed from them. ...`. (−100, 100) → the same message with −100.00 and 100.00 |
| 3b | (0, 100) stops, naming market_cap | pass | `ValueError: market_cap is 0.00, which is not greater than 0, so the capital weights E / (E + D) and D / (E + D) cannot be formed from it. The equity weight is not set to 0.0 and the debt weight is not set to 1.0. Supply a market_cap greater than 0.` The same without the override (`crit34b.py 0 100`). On `old`: `equity_weight 0.0 debt_weight 1.0` |
| 3c | (−5, 100) stops, naming market_cap | pass | `ValueError: market_cap is -5.00, which is not greater than 0, ...`. On `old`: `equity_weight -0.0526 debt_weight 1.0526` |
| 4 | (300, 100) keeps its weights | pass | `equity_weight 0.75 debt_weight 0.25`, with and without the override. Hand check: 300/400 and 100/400 |
| 5 | Walmart unchanged | pass | `wmt.py extractions/WMT.json` in iso2 vs the round 1 `0021845` reference: `cmp` → `WMT IDENTICAL`. Statement years [2024, 2025, 2026], 4 items, 0 outside, 4 applied |
| 6 | the suite fails only where expected | pass | iso2 full suite: `3 failed, 723 passed`, which is the 2 `*_rule3_red.py` plus `test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`. Gate form: `1 failed, 723 passed`, the same test. Baseline at `0021845`: 2 failed, 724 passed, so the set grows by exactly that one test, as in round 1 |
| 7 | the gates do not get worse | pass | iso2: ruff `Found 5 errors.`; `ruff check analysis/normalizer.py analysis/wacc.py` → `All checks passed!`; mypy (exact gate command) `Found 10 errors in 4 files (checked 20 source files)`; census 67; census over my two files 0 and 0 |

## Red tests

- **Caused by this unit: one.** `tests/unit/test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`.
  Its inputs are (0, 0), so the sum check fires: `ValueError: market_cap is 0.00 and balance_sheet.total_debt is 0.00 (year 2025), ...`.
  The test requires the call to return. Assignment step 3 expected this; the tester rewrites the test.
  **The new market_cap guard turns no additional test red.**
- **Shared tree** (P13b's and P13c's edits present): `31 failed, 695 passed`. The 31 are
  26 in `test_normalizer.py`, 2 in `test_normalizer_stops.py`, the 2 `*_rule3_red.py`, and
  the 1 in `test_wacc.py` above.
  The 28 normalizer failures are the same as in round 1. All are
  `TypeError: NonRecurringItem.__init__() missing 1 required positional argument: 'confidence'`,
  caused by `models/financial_statements.py`, which is P13b's file. They are not caused by
  this unit, and they do not appear in iso2.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Sum check first, market_cap check second | Criterion 3 asks (0, 0) to name **both** inputs and both values. With the sum check first, (0, 0) and (−x, x) get that message, and every other non-positive market_cap gets the market_cap message. The amendment says "the sum check stays for the case that it still covers"; it does not fix the order | The reviewer suggested "before the sum check". Then (0, 0) would name only market_cap, and criterion 3 as written would fail. Both orders stop on exactly the same inputs; only the message differs. |
| Guard on `equity_value <= 0`, after `_require_finite(equity_value, "market_cap")` | amendment: "not greater than zero". The NaN check stays first, because `nan <= 0` is False and the NaN check is the only one that catches it | Measured: `crit34.py nan 100` → the existing NaN message |
| No cause in the message | backlog item 37; amendment: "with no claim about the cause" | A zero market cap may come from the `sharesOutstanding` fallback or from a missing price. This function cannot tell which. |
| Message does not print total_debt | amendment: "naming `market_cap` and its value". This stop depends on market_cap alone | — |

No change was made to reach a target number.

## Rule 3: what stops, and what does not (`calculate_wacc` weights)

| Value read | If it were missing | Evidence |
|---|---|---|
| `market_cap` NaN | stops, names `market_cap` (pre-existing) | `crit34.py nan 100` |
| `market_cap + total_debt == 0` | stops, names both and both values | criterion 3 |
| `market_cap <= 0`, sum non-zero | stops, names `market_cap` and its value | criteria 3b, 3c |
| `total_debt` negative with `market_cap > 0` and a non-zero sum | **forms weights**, with debt_weight < 0 (not in scope; no backlog item names it; reported below) | executed: `crit34.py 300 -50` in iso2 → `equity_weight 1.2 debt_weight -0.2` |
| `balance_sheet` None | `AttributeError` at `wacc.py:211`, unnamed (item 11 / item 38 second face; excluded) | round 1 |
| zero debt lines, override supplied, interest ≠ 0, `market_cap > 0` | **weights default to 1.0 / 0.0** (item 38 second face; excluded) | round 1, face A |

## What I did not do

- Did not edit `api/` (F2), the backlog (F3), `tests/`, `STATUS.md` or `INDEX.md`. Did not commit.
- `analysis/normalizer.py` was not touched in round 2.

## Findings for the orchestrator

1. **Negative debt is not guarded.** Example: `market_cap` 300 and `total_debt` −50. Executed in iso2 (`crit34.py 300 -50`), this
   returns `equity_weight 1.2 debt_weight -0.2`. It is reachable only if a debt line
   arrives negative, and it is the same family as F1. I did not test whether the
   extraction can produce a negative debt line. It needs a backlog line before anyone
   decides to fix it.
