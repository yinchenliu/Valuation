---
agent: code_reviewer
assignment: P13a-analysis-silent
round: 1
verdict: changes_requested
---

# Review of P13a-analysis-silent, round 1

Programmer entry: `.agent/journal/2026-10-03T2021-programmer-p13a-analysis-silent.md`

I measured this unit on its own. I exported `git archive 0021845` into
`<scratchpad>/rev/old` (the baseline) and into `<scratchpad>/rev/iso`, and copied only
`analysis/normalizer.py` and `analysis/wacc.py` into `iso`. `diff -rq old iso` lists those
two files and nothing else. I did not touch the shared tree.

## The guard checks

Run over `analysis/normalizer.py` and `analysis/wacc.py`.

| Check | Result |
|---|---|
| conditional zero: `if … else 0.0` | clean |
| lookup with a fallback: `.get(k, 0)` | hit at `normalizer.py:269`, `by_year.get(stmt.year, [])`. This is a context line the unit did not change. The programmer answered it: after the new check, every item sits in the bucket of some statement, so `[]` means "no items for this year". It no longer stands in for a missing value. I accept that. |
| bare or-default: `or 0.0` | clean |
| money field defaulted to zero: `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | hit at `normalizer.py:221`. The unit did not touch it. The name comes from `_resolve_field`, which accepts only the fixed `_LABEL_TO_FIELD` set and stops on anything else, so it is not a name from data. |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (`grep -rnE "anthropic|google\.genai|from google" models/ analysis/ api/`: no output) |

Imports are unchanged. `normalizer.py` imports `dataclasses` and `models/`. `wacc.py`
imports `math`, `config` and `models/`. Census over the two files: 0 before and 0 after.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `NonRecurringItem.year` with no matching income statement | **yes**. It names the year, `line_item`, description and the statement years. It does not say which year is wrong | `r12.py 2019 add_back` in iso |
| several unmatched items | **yes**, all of them in one message | `r12.py 2019 add_back 2031`: "2 non-recurring item(s) … year 2019 … ; year 2031 …" |
| an empty `financials.income_statements` with items | **yes**. The message gives years `[]` (by reading lines 247-248) | — |
| `market_cap + balance_sheet.total_debt == 0` | **yes**. The message names both fields, both values and the BS year, and makes no claim about the cause | `r34.py 0 0 0 none` in iso |
| `market_cap == 0` with `total_debt > 0` | **no**. The run returns `equity_weight 0.0, debt_weight 1.0` | **F1** |
| `balance_sheet` is `None` | no. It raises a bare `AttributeError` at `wacc.py:211` | backlog items 11 and 38, see below |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | yes. No conversion was added. The message prints the values as they arrive |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing | no new instance. `if not non_recurring` is a line the unit did not change, and an empty list really does mean no items |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | holds for both files |

## Done-criteria, re-run

My own scripts are in `<scratchpad>/rev/` (`r12.py`, `r34.py`, `r5.py`). I ran each in `iso`, and in `old` for comparison.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | an item for a year with no statement stops | ValueError naming 2019, `sga`, the description, [2023, 2024] | `ValueError: 1 non-recurring item(s) carry a year with no income statement in the financials: year 2019, line_item 'sga', description 'Restructuring charge, Note 12'. The income statement years are [2023, 2024]. …`. In old, the same input returns sga 200 → 200 with no stop | yes |
| 2 | an item for a matching year still applies | 2024 sga 200 → 150, ebit 200 → 250; remove gives 250 / 150 | the same numbers, identical in old. 2023 is untouched | yes |
| 3 | sum == 0 stops, with no cause claimed | ValueError naming both | ValueError for (0, 0), for (0, 0) with override 0.05, and for (−100, +100). Old returned 1.0 / 0.0 for all three | yes |
| 4 | 300 / 100 gives 0.75 / 0.25 | 0.75 / 0.25 | `equity_weight 0.75 debt_weight 0.25`, identical in old | yes |
| 5 | Walmart unchanged | IDENTICAL | `r5.py extractions/WMT.json` in old and in iso, then `cmp`: **IDENTICAL**. Statement years [2024, 2025, 2026], item years within them, 4 applied, 0 excluded, 3 statements moved. So the adjustments are live, not a no-op | yes |
| 6 | suite fails only where expected | iso: 3 failed / 723 passed; gate 1 failed | old full: `2 failed, 724 passed`. iso full: `3 failed, 723 passed`. **`diff` of the FAILED sets** adds exactly `test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`. Gate form: old `724 passed`, iso `1 failed, 723 passed`, the same test. Its error is the new ValueError. It is expected under assignment step 3 | yes |
| 7 | gates do not get worse | ruff 5, mypy 10 / 4, census 67 | ruff `Found 5 errors.` in both trees, and the two outputs are **byte-identical**. mypy (exact gate command) `Found 10 errors in 4 files (checked 20 source files)` in both, also byte-identical. Census 67 in both | yes |
| step 4 | no sentence in `valuation-math.md` states either old behaviour | none found | I read sections 1 and 6 (lines 12-34, 125-151) and found no such sentence | yes |

## Findings

### F1: `market_cap == 0` with debt still produces weights from nothing, 0.0 / 1.0 · `major`

**Evidence:** `r34.py 0 100 5 none` in iso returns
`equity_weight 0.0 debt_weight 1.0 cost_of_debt 0.05 wacc 0.0447`. That is the after-tax
cost of debt standing in for the WACC. The path is `wacc.py:209` and then `:215`, where the guard fires only on
the sum, and then `:235-236`.

**Rule or document:** rule 3. The assignment's own objective says "a company with no
market value … is absent data". For a priced, listed company, a market cap of exactly
`0.0` can only come from absent inputs. The upstream source is reachable:
`api/routes_valuation.py:624-629` and `cli.py:1035-1042` compute `price × shares`, and
`shares` falls back to `info.get("sharesOutstanding", 0)`. The new stop is narrower than
the absence it targets. Half of the same 0 / 0 shape still passes: with E = 0, every
weight is formed from a missing E. The defect is silent and **understates the discount
rate**, so it overstates value, and the WACC is displayed. This exact case is not in
`refactor-backlog.md`: item 38 names only the sum. The upstream `.get("sharesOutstanding", 0)` is
recorded (item 12's sub-section, rule 5), and item 32 covers the zero-share price, but
neither covers the weights. So the pre-existing exemption does not apply. It sits in the
function and the guard this unit rewrote.

**What would fix it:** in `wacc.py`, the file in scope, stop when `market_cap` is not
positive and name `market_cap` and its value, before the sum check. Measured cost on a
scratch copy (`<scratchpad>/rev/probe`, guard `equity_value <= 0`): the gate form is
`1 failed, 723 passed`, the **same single test** the unit already turns red. No new red
test. The programmer followed step 2 literally, so the **orchestrator must widen
step 2**. Rule 3 outranks the assignment's narrower wording (severity.md, "the fix
belongs to a future unit").

### F2: a source comment cites a line this diff moved · `note`

**Evidence:** `api/routes_valuation.py:411` cites "`analysis/normalizer.py:245`" for
`dataclasses.replace`. The line is now `normalizer.py:273`, confirmed with
`git show 0021845:analysis/normalizer.py | grep -n "dataclasses.replace(financials"` → 245.
**Rule or document:** none. It is a stale comment. `api/` is outside this unit's scope, and the
programmer correctly reported it rather than editing it.
**What would fix it:** whichever unit next touches `api/routes_valuation.py` updates
the citation, or the comment cites the function name and drops the line number.

### F3: backlog item 38's "second face" does not describe what the code does · `note`

**Evidence:** item 38 says a supplied `--cost-of-debt` "with a missing balance sheet still gets
a zero debt weight". I measured two separate behaviours, in iso and identically in old:
(a) a BalanceSheet whose debt lines are all 0, with interest 30, `market_cap` 300 and override 0.05, returns
`equity_weight 1.0 debt_weight 0.0`. The override bypasses item 22's interest-vs-zero-debt
stop because `cost_of_debt_with_source` returns before it reaches that check. (b) `balance_sheet=None` with an
override raises `AttributeError: 'NoneType' object has no attribute 'total_debt'`, which is
stopping but unnamed (item 11).
**Rule or document:** none against this unit. The assignment excludes this face
explicitly, and the lines involved (`:211`, `:235-236`, `cost_of_debt_with_source`) are
untouched. I confirm the programmer's report.
**What would fix it:** the orchestrator restates item 38's second face as (a) silent and
(b) stopping when it records the item's closure.

## Pre-existing, already recorded: not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 38, second face (see F3) | `wacc.py:211`, `:235-236` | no. Excluded by the assignment |
| 11, `BalanceSheet \| None` into `calculate_wacc` | `api/routes_valuation.py:633-634` | no |
| 37, the zero-debt stop states "did not extract" as fact | `wacc.py:113-125` | no. The unit's new message avoids the same mistake |
| 1, zero-default sites (`effective_tax_rate` `else 0.0` and others in `models/`) | `models/financial_statements.py:108` | no |
| 12 / rule 5, `info.get("sharesOutstanding", 0)` | `api/routes_valuation.py:628`, `cli.py:1039` | no. This is the upstream source of F1's zero, but F1 is about the weights |
| 8, blanket `except Exception` renders the new stops as `str(e)` | `api/routes_valuation.py:445-446` | no. The stop stays visible |
| stale prose in `valuation-math.md` (lines 31-34 still say `_resolve_field` guesses, which was closed at `38b903c`; lines 159-161 say "the one place") | `docs/3-architecture/valuation-math.md` | no. The programmer reported it, and I confirmed lines 31-34 by reading. It is the doc owner's to fix |

No user-decision exception is claimed in the assignment, so none needed checking.

## Verdict

`changes_requested`

The two stops are correct, and every done-criterion re-runs as claimed. The failure set
grows by exactly the one expected test. Ruff, mypy and the census are byte-identical
to the baseline, and Walmart's normalised statements are unchanged. **F1 blocks.** It is
a rule-3 gap in the guard this unit rewrote: a zero market cap with any debt still forms
weights from an absent input, silently, and it overstates value. The fix is in a file
already in scope, and it costs no extra red test. The programmer followed step 2 as
written, though, so the orchestrator should widen step 2 before round 2. F2 and F3 are
notes for the orchestrator and need nothing from the programmer.
