---
agent: code_reviewer
assignment: P8b-statements-ui
round: 1
verdict: approved
---

# Review of P8b-statements-ui, round 1

Programmer entry: `.agent/journal/2026-09-26T1716-programmer-p8b-statements-ui.md`

## The guard checks

Run over the assignment's **Files in scope**, not over the whole repository.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean in touched code; 5 pre-existing hits in `models/financial_statements.py` (lines 57, 81, 101, 108, 299) untouched |
| lookup with a fallback — `.get(k, 0)` | clean in touched code; 2 pre-existing hits in `api/routes_valuation.py` (line 246 route decorator, line 482 backlog item 1/rule 5) untouched |
| bare or-default — `or 0.0` | clean in touched code; 5 pre-existing hits in `templates/assumptions.html` form inputs (lines 147, 153, 163, 168, 173) untouched |
| money field defaulted to zero — `: float = 0.0` | clean in touched code; 42 pre-existing hits in `models/financial_statements.py` (backlog item 1) untouched |
| `**kwargs` on a calculation function | clean (0 hits) |
| `getattr(` on a name from outside the file | clean (0 hits) |
| dict of functions keyed by data | clean (0 hits) |
| model client imported outside `ingestion/` | clean (0 hits) |

**A hit is a question, not automatically a finding.** All hits above are in pre-existing lines outside the diff of this work unit. The unit added `@property def balance_check_difference` to `BalanceSheet` with no new fields and no defaults, strictly adhering to assignment step 12.

## Rule 3, by reading

The greps catch the four written forms. This table catches the rest. For every value the unit reads, ask: if it were missing, what happens?

| Value | Stops and names it? | Evidence |
|---|---|---|
| `financials.get_income_statement(y)` | Renders `not extracted` in all 18 line item cells for that year; no zero fallback | `templates/_statements.html:23, 30, 37, 44, 51, 58, 65, 72, 79, 86, 93, 100, 107, 114, 121, 128, 135, 142` |
| `financials.get_cash_flow(y)` | Renders `not extracted` in all 17 line item cells for that year; no zero fallback | `templates/_statements.html:170, 177, 184, 191, 198, 205, 212, 219, 226, 233, 240, 247, 254, 261, 268, 275, 282` |
| `financials.get_balance_sheet(latest_y)` | Renders `<p>not extracted</p>`; no zero metric calculations | `templates/_statements.html:353` |
| `raw_financials.get_income_statement(y)` / `adjusted.get_income_statement(y)` | Sets `difference: None` and `missing_statement: str`; template renders `not extracted: <missing_statement>` | `api/routes_valuation.py:214-239`, `templates/_statements.html:416` |
| `assumption_sources` empty or missing | Guarded by `{% if not error and assumption_sources %}`; suppresses table when no ratios derived | `templates/assumptions.html:15` |
| Substituted ratio default | Marked with `<span class="substituted-marker">SUBSTITUTED</span>` and provenance `It is not a measurement.` | `templates/assumptions.html:34`, `templates/valuation_result.html:142` |
| Empty applied NRI list | Prints `No non-recurring item was applied.` (never an empty table shell) | `templates/_statements.html:388` |
| Unadjusted reconciliation year | Prints `No adjustment reached the income statement.` | `templates/_statements.html:427` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean — all table and column headers declare `($M)`; diluted shares declares `(M)`; EPS is per share `$` |
| percentages converted at the route boundary, once | clean — only multiplied by 100 in Jinja template formatting for display |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean — strict `is None` and `is not None` checks throughout `api/routes_valuation.py` and `is not none` in Jinja |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean — `analysis/` was untouched by this unit (pre-existing `analysis/capm.py:16` import is backlog item 17) |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | test gate unchanged | `145 passed` baseline; 178 passed, 1 failed (scipy 1.17+ linregress message) | 178 passed, 1 failed | yes |
| 2 | no new lint error | `Found 5 errors`, all `BLE001` | `Found 5 errors.` (all BLE001) | yes |
| 3 | no new type error | `Found 14 errors in 4 files` | `Found 14 errors in 4 files` (checked 18 source files) | yes |
| 4 | still no JavaScript in `templates/` | 0 matches | 0 matches (`grep -rn "<script" templates/`) | yes |
| 5 | `GET /assumptions` renders all 7 block headings | 7 matches | 7 matches verified by execution | yes |
| 6 | `POST /valuation` renders all 7 block headings | 7 matches | 7 matches verified by execution | yes |
| 7 | missing cash flow statement year renders `not extracted` | `not extracted` present, no `0` in CFS cells | 17 occurrences of `not extracted`, 0 occurrences of `0` or `0.0` in CFS cells | yes |
| 8 | applied NRI table lists high and medium, excludes low | 2 rows applied, 1 excluded | High and Medium present; Low excluded | yes |
| 9 | reconciliation shows non-zero delta equal to applied items | delta is +25 (15.0 + 10.0 = +25.0) | delta is +25, matches hand arithmetic | yes |
| 10 | every ratio carries source sentence | 6 sentences rendered verbatim | 6 sentences verified verbatim in rendered body | yes |
| 10b | substituted ratio visibly marked | `SUBSTITUTED` and `It is not a measurement.` | Both present on `/assumptions` and `/valuation` | yes |
| 11 | inline `PROV` variable gone, `.provenance` exists | 0 and 1 | 0 in `templates/valuation_result.html`, 1 in `static/style.css:235` | yes |
| 12 | no number already on either page moved | implied share price `$22.58` before and after | `$22.58` before and after on `_one_year_financials` stub | yes |
| 13 | `BalanceSheet` property holds one subtraction and no division | 1 subtraction, 0 divisions | `self.total_assets - (self.total_liabilities + self.total_equity)` | yes |

## Findings

### F1 — CapEx column header in Historical FCFF table includes `(negative = outflow)` while `HistoricalFCFF.capital_expenditures` is stored positive · `note`

**Evidence:** `templates/_statements.html:446` (`<th class="num">CapEx ($M, negative = outflow)</th>`) vs `analysis/fcff.py:79` (`capex = abs(cash_flow.capital_expenditures)`).
**Rule or document:** Assignment step 9 ("Columns: Year, Revenue, CFO, After-tax interest, CapEx, FCFF, FCFF margin") vs Step 14. Step 14 addresses the cash flow statement where CapEx is typically negative in `CashFlowStatement`. In `HistoricalFCFF`, CapEx is stored as a positive quantity because it is subtracted in the definition formula `FCFF = CFO + Interest*(1-t) - CapEx`.
**What would fix it:** Update the header in `templates/_statements.html:446` to `<th class="num">CapEx ($M)</th>` to avoid giving the impression that displayed positive values represent inflows.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| Item 1 (silent zero-defaults) | `models/financial_statements.py:47-252` | no — unit only added `balance_check_difference` property |
| Item 6 (`x / 100 if x else None`) | `api/routes_valuation.py:284-288` | no |
| Item 7 (CLI/API duplication) | `cli.py`, `api/` | no |
| Item 8 (blanket `except Exception`) | `api/routes_valuation.py:326, 568` | no |
| Item 11 (14 type errors) | `api/routes_valuation.py`, etc. | no |
| Item 17 (`analysis/capm.py` imports `ingestion/`) | `analysis/capm.py:16` | no |
| Item 39 (`confidence` defaults to `"high"`) | `models/financial_statements.py:28` | no |
| SciPy 1.17+ error message mismatch | `tests/unit/test_capm.py:473` | no |

## Earlier findings — re-reviews only

N/A — Round 1.

## Verdict

`approved`

Work unit P8b-statements-ui is approved. The implementation delivers all seven blocks across `GET /assumptions` and `POST /valuation`, satisfies all 13 done-criteria by execution, respects Rule 3 by explicitly rendering `not extracted` for missing statements without numeric defaults, isolates the reconciliation calculation to `api/routes_valuation.py`, lifts inline styles into `static/style.css`, and stays strictly within the assigned file scope. Finding F1 is a note regarding a column header label in the Historical FCFF table and does not block approval.
