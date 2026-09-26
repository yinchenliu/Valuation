---
agent: tester
assignment: P6b-wacc-fixture
round: 1
status: complete
files_touched: [tests/unit/test_wacc.py, tests/unit/test_capm.py, tests/unit/test_dcf.py, tests/unit/test_fcff.py]
verdict: pass
---

# P6b-wacc-fixture — the fixture describes a company it does not claim to be testing, and the stop it collides with is right for a reason its own message gets wrong

> Opened before the first command. Filled as each result landed.

## What I did

Ruled on the fixture, repaired it, and then proved the repair did not hollow out
anything. `_income_statement()` → `_income_statement(interest_expense=0.0)` at the three
call sites that pair it with `_balance_sheet_without_debt()`; **no expectation was
touched.** Then I verified every assertion in those three tests individually, including a
discrimination check that gives each one its debt back and confirms every assertion fails
again — an assertion that survives that is testing the input, not the code. Then I locked
both halves of backlog item 22's new branch (the stop, and the labelled zero), and closed
the coverage gap: **8 uncovered `raise` statements before, 0 after.**

I did **not** edit `analysis/`, and I did not weaken, skip or `xfail` anything.

## Criterion 1 — the ruling. This is the unit.

### The question, answered from the accounting

**Can a company report $20M of interest expense and $0 of total debt? Yes.** The two
figures are not commensurable and a real filing can print both.

Interest expense is a **flow** over the whole fiscal year. `BalanceSheet.total_debt` is a
**stock** at the single instant of the fiscal year-end, and in this codebase it is
specifically `short_term_debt + current_portion_lt_debt + long_term_debt`
(`models/financial_statements.py:187-188`) and nothing else. Two ordinary filings produce
the pair:

1. **Deleveraging inside the year.** A company that carried $400M of debt for eleven
   months and repaid all of it out of IPO, divestiture or refinancing proceeds before the
   balance sheet date reports a full year of interest expense beside a year-end debt
   balance of zero. Nothing was mis-extracted; both figures are right.
2. **Interest on obligations that are not in those three lines.** `BalanceSheet` here
   carries no lease-liability field at all (checked: `models/financial_statements.py:115-183`),
   so finance-lease interest under ASC 842, interest on securitisation and factoring
   facilities, and interest accrued on uncertain tax positions land in
   `other_current_liabilities` / `other_non_current_liabilities` if they are captured at
   all — **never** in `total_debt`. Interest expense beside `total_debt == 0` is then
   arithmetically correct on the face of the filing.

So the sentence the new code prints — *"A company that pays interest has debt, so the
debt balance ... did not extract"* — states an **inference as a fact**, and it over-claims.
That is finding 1 below.

### Why that does not make the stop wrong, and why I did not rule against `analysis/wacc.py`

The assignment put the question as a binary and the honest answer splits it. The pattern
is **ambiguous**, not impossible. It is consistent with a balance sheet that did not
extract *and* with a company that genuinely repaid everything, and those two readings
imply different WACCs — one where the debt term is legitimately absent, one where it was
silently dropped and the share price is understated by the whole debt balance. Neither
statement in the function's signature chooses between them.

Rule 3 is "stop, never guess." Picking either reading is a guess. The old
`if total_debt == 0: return 0.0` picked one, silently, and that is backlog item 22. The
new branch **refuses to pick**, names both figures so the reader can see the ambiguity
for themselves, and points at `--cost-of-debt` for the caller who knows which case they
are in. Stopping on an ambiguity the code cannot resolve is the correct behaviour, so
**the behaviour stands.** What does not stand is the diagnosis in the message, which
should name both readings rather than assert the extraction failed.

I did not write a red test against the wording. My brief says not to pin a label's exact
wording, and "should the platform refuse to value a company that legitimately
deleveraged, or ask the user?" is a product decision, not an arithmetic one. It is
escalated as finding 1, not encoded.

### And the fixture is wrong independently of all of that

This is the part that decides the unit, and it does not depend on the ruling above.

Each of the three tests names its own subject:

| Test | What it says it is testing |
|---|---|
| `test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt` | "with D = 0 the debt term vanishes" |
| `test_a_debt_free_company_prices_at_its_cost_of_equity` | a **debt-free company** |
| `test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt` | "no market capitalisation and **no debt**" |

and the balance sheet they share has the docstring *"No financial debt at all."*

**A debt-free company does not report interest expense in the same fiscal year.** Under
*either* reading of the ambiguity above, the fixture paired a balance sheet asserting no
debt whatsoever with an income statement saying the company paid 20 of interest. That is
a contradiction with the fixture's **own stated subject**, and it is a contradiction
whichever way the accounting question resolves.

So the repair is not "accommodating code I believe is wrong". It makes an input describe
the company its test claims to be about. The tests were passing on an input that did not
match their own titles.

## Criterion 3 — every assertion in the three affected tests, one by one

The repair is `_income_statement()` → `_income_statement(interest_expense=0.0)`. The only
figures that move are `IncomeStatement.ebt` (320 − 20 = 300 → 320 − 0 = 320) and
`effective_tax_rate` (75/300 = 0.25 → 75/320 = 0.234375). `ebit` is unchanged at
1000 − 680 = 320, because interest sits below the operating line. Confirmed by hand and
re-derived in `c:/tmp/p6b_check.py`.

### `test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt`

This test **passed before and passes now**; it was never one of the two failures. It
reads neither the interest nor the tax rate: `cost_of_debt_override=0.90` short-circuits
`cost_of_debt_with_source` before either statement is consulted, and `tax_rate_override=0.40`
means `effective_tax_rate` is never evaluated. **The repair changes nothing this test
reads.** I changed it anyway so the fixture describes one coherent company everywhere,
and because leaving it contradictory leaves a landmine for finding 2.

| # | Assertion | Still means what it meant | Discrimination check |
|---|---|---|---|
| 1 | `equity_weight == approx(1.0)` | E/V = 1000/(1000+0) = 1. Identity, no interest input | give it back real debt → 0.7143, **fails** |
| 2 | `debt_weight == approx(0.0)` | D/V = 0/1000 = 0 | → 0.2857, **fails** |
| 3 | `wacc == approx(COST_OF_EQUITY)` | WACC = 1·Re + 0·Rd·(1−t) = Re, for **any** Rd and t — which is why Rd is an absurd 0.90 | → 0.225714, **fails** |
| 4 | `wacc == approx(0.10)` | the same identity written as a literal; 0.04 + 1.2·0.05 = 0.10 | → 0.225714, **fails** |

### `test_a_debt_free_company_prices_at_its_cost_of_equity` — was red, now green

The only one of the three whose **path** changed: it now goes through the measured
debt-free branch (`analysis/wacc.py:129-135`) instead of the old unconditional zero-debt
return. That is exactly the behaviour item 22 introduced, and it is what this test's
title has always claimed to be exercising.

| # | Assertion | Still means what it meant | Discrimination check |
|---|---|---|---|
| 1 | `debt_weight == approx(0.0)` | D/V = 0/1000 = 0. The weight is computed from the balance sheet alone; interest is not an input to it | give it back real debt → 0.2857, **fails** |
| 2 | `wacc == approx(0.10)` | WACC = 1·Re + 0·Rd·(1−t) = Re. Before: Rd = 0.0, t = 0.25. After: Rd = 0.0, t = 0.234375. **Both are multiplied by a debt weight of zero, so neither reaches the answer.** The identity holds for every Rd and every t, and that generality is the point of the test | → 0.082143, **fails** |

The docstring said "`1 - 0.25`", which the repair made stale. I corrected the comment to
state the identity's true generality (any t) and to record that the tax rate on this path
is now 75/320. **The assertion is byte-identical; only the prose above it moved.** The
test still asserts nothing about `result.cost_of_debt` or `result.tax_rate`.

### `test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt` — was red, now green

| # | Assertion | Still means what it meant | Discrimination check |
|---|---|---|---|
| 1 | `cost_of_equity == approx(0.10)` | a pass-through of `CAPMResult.cost_of_equity` = 0.04 + 1.2·0.05 = 0.10 on the `total_value == 0` early return at `analysis/wacc.py:215-223`. Interest expense reaches no part of it | change beta to 2.0 → 0.14, **fails** |

This test still deliberately asserts **nothing** about the weights. I did not add an
assertion on the all-equity fallback, and I would not: it is a live rule-3 defect
(finding 3).

**Discrimination evidence:** `c:/tmp/p6b_check.py`. Every "would FAIL" line prints `True`.

## Criteria 4 and 5 — the stops I locked

| Stop | Test | Exception type | Fields / figures the message names |
|---|---|---|---|
| zero debt + reported interest (`wacc.py:113`) | `test_a_zero_debt_balance_beside_a_reported_interest_expense_stops` | `ValueError` | **both figures** (37 and 0, extracted as standalone numbers so `20.00`'s zeros cannot be mistaken for the debt figure), plus `short_term_debt`, `current_portion_lt_debt`, `long_term_debt`, and the phrase `interest expense` |
| the same, with a negative interest sign | `test_the_contradiction_stop_is_not_bypassed_by_a_negative_interest_sign` | `ValueError` | — locks that the guard is `!= 0` on a magnitude, not `> 0` |
| the same, through the valuation path | `test_the_contradiction_stops_calculate_wacc_too` | `ValueError` | — a WACC cannot be produced from the pair |
| `capm_result.cost_of_equity` NaN (`wacc.py:41`) | `test_a_nan_cost_of_equity_stops_and_names_the_capm_result` | `ValueError` | `cost_of_equity` |
| `cost_of_debt` NaN | `test_a_nan_cost_of_debt_override_stops_and_names_the_cost_of_debt` | `ValueError` | `cost_of_debt` |
| `tax_rate` NaN | `test_a_nan_tax_rate_stops_before_the_clamp_flattens_it_to_zero` | `ValueError` | `tax_rate` |
| `market_cap` NaN | `test_a_nan_market_cap_stops_and_names_the_market_cap` | `ValueError` | `market_cap` |
| `balance_sheet.total_debt` NaN | `test_a_nan_total_debt_stops_and_names_the_balance_sheet_field` | `ValueError` | `total_debt` |
| `calculate_beta` misaligned series (`capm.py:65`) | `test_beta_stops_when_the_two_return_series_are_not_the_same_length` | `ValueError` | `market_returns`, `stock_returns`, and both lengths |
| fewer than 3 observations (`capm.py:73`) | `test_beta_stops_below_the_minimum_number_of_observations` | `ValueError` | the count, `MINIMUM_REGRESSION_OBSERVATIONS`, `observations` |
| degenerate regression (`capm.py:87`) | `test_beta_stops_when_the_market_series_has_no_variation`, `..._when_a_return_observation_is_nan` | `ValueError` | `market_returns`, `variance` |
| NaN terminal base cash flow (`dcf.py:35`) | `test_terminal_value_stops_on_a_nan_final_cash_flow` | `ValueError` | `final_fcff` |
| NaN WACC / growth (`dcf.py:68`) | `test_terminal_value_stops_on_a_nan_wacc_before_the_spread_check`, `..._on_a_nan_growth_rate` | `ValueError` | `WACC`, `growth` |
| NaN projected year (`dcf.py:35` via `:97`) | `test_discounting_stops_on_a_nan_year_and_names_that_year` | `ValueError` | the **year**, `2027` |
| empty projection (`dcf.py:124`) | `test_run_dcf_stops_when_there_are_no_projected_cash_flows` | `ValueError` | `projected_fcffs` |
| NaN tax rate (`fcff.py:40`) | `test_historical_fcff_stops_on_a_nan_tax_rate_before_the_clamp_hides_it` | `ValueError` | `tax_rate` |

**The labelled zero (criterion 5)** — `test_a_genuinely_debt_free_company_measures_zero_and_the_label_says_so`
asserts the rate is `0.0` and that the label *identifies the case* without pinning its
wording: it contains `debt`, contains one of `no debt` / `debt-free` / `debt free`, and
does **not** contain `assumption`, `substituted` or `supplied by the caller`. A reformat
cannot turn it red. `test_the_debt_free_label_is_not_the_substituted_one` adds the only
thing that matters about a rule-6 label: the measured branch and the substituted branch
must not produce the same sentence. It asserts nothing about either *value*.

**Why asserting that `0.0` is not asserting a fallback.** Before item 22 it would have
been: the same `0.0` was returned when the balance sheet had simply failed to extract.
That case now raises — locked by the three tests above — so the `0.0` asserted here is
reachable only by the branch that measured it. The docstring says so in full.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `balance_sheet.total_debt == 0` with interest ≠ 0 | **stops**, naming both figures and the three balance-sheet fields | 3 tests, table above |
| `balance_sheet.total_debt == 0` with interest == 0 | returns `0.0`, **labelled as a measurement** | not a fallback: this is a complete description of a company and no input is missing |
| `capm_result.cost_of_equity`, `cost_of_debt`, `tax_rate`, `market_cap`, `balance_sheet.total_debt` — as NaN | **stops**, each naming its own field | 5 tests |
| `market_cap + total_debt == 0` | **DEFAULTS to `equity_weight=1.0`, `debt_weight=0.0`** | `analysis/wacc.py:215-223`. **I could not lock this stop, because the code does not raise.** Finding 3. No test I wrote asserts those weights |
| `--cost-of-debt` supplied with a zero debt balance | **DEFAULTS to a zero debt weight**, so the supplied rate is multiplied by 0 and vanishes | `analysis/wacc.py:83-88` returns before reading either statement; `analysis/wacc.py:230-231` then weights it at 0. Finding 2. **Deliberately not pinned by any test** |
| `analysis/dcf.py:80` net debt with no balance sheet | **DEFAULTS to 0.0** | backlog item 2; `tests/unit/test_dcf_rule3_red.py` states it and stays red. **Not touched** |

Two "defaults to" rows I could not lock, both named with `file:line`. Neither is asserted
anywhere in my diff.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the ruling, with the accounting reasoning | **pass** | the section above |
| 2 | suite back to `1 failed, N passed`, the failure being `test_dcf_rule3_red.py` | **pass** | `pytest -q` → **`1 failed, 145 passed`**; the sole failure is `tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`. Was `3 failed, 118 passed` |
| 3 | every assertion in the three affected tests confirmed | **pass** | one row per assertion above, 7 assertions, each with a discrimination check from `c:/tmp/p6b_check.py` |
| 4 | contradiction stop locked on type **and** both figures | **pass** | `pytest -q -k wacc` → **29 passed**; `test_a_zero_debt_balance_beside_a_reported_interest_expense_stops` asserts `ValueError` + both standalone numbers + three field names |
| 5 | labelled zero locked without pinning wording | **pass** | same command; two tests, neither containing a literal from the label's prose |
| 6 | new `raise` statements covered, count before and after | **pass** | **before: 8 uncovered raises** (`capm.py` 65/73/87, `dcf.py` 35/68/124, `fcff.py` 40, `wacc.py` 41) — the assignment's figure, re-measured and confirmed. **After: 0.** Command below |
| 7 | `tests/` lints with exactly 1 error | **pass** | `ruff check tests --output-format concise` → **`Found 1 error`**, `tests/test_e2e_all_googl.py:106 BLE001`, the deferred one |

## Measurements

**Suite, as failure sets rather than counts.**

| | Before | After |
|---|---|---|
| `pytest -q` | `3 failed, 118 passed` | **`1 failed, 145 passed`** |
| failing set | `{test_dcf_rule3_red::…balance_sheet_is_absent, test_wacc::…debt_free_company_prices…, test_wacc::…no_market_cap_and_no_debt}` | **`{test_dcf_rule3_red::…balance_sheet_is_absent}`** — the deliberate red, unchanged |

**Coverage of `analysis/`, measured not estimated.**

```
COVERAGE_FILE=c:/tmp/.cov pytest -q --ignore-glob="*_rule3_red.py" --cov=analysis --cov-branch --cov-report=term-missing
```

| | Before | After |
|---|---|---|
| statements | 244 / 255 (96%), **11 missed** | **255 / 255 (100%), 0 missed** |
| branches | — | **80 / 80 (100%), 0 partial** |
| uncovered `raise` statements | **8** | **0** |
| module-level functions in `analysis/` touched by ≥1 test | — | **23 of 23** |

The 11 missed statements before were the 8 raises plus `capm.py:136` and
`wacc.py:129`/`216` — the last two only because the two failing tests aborted at setup.

**Gates, none of which I moved** (my diff is `tests/` only; `git status` shows the
`analysis/`, `api/`, `cli.py`, `config.py`, `models/`, `templates/` modifications are the
uncommitted `P6-honest-output` work, not mine):

| Gate | Baseline | Now |
|---|---|---|
| Lint, whole repo | 5, all `BLE001` | **5, all `BLE001`** |
| Types (`mypy models analysis ingestion api config.py app.py --ignore-missing-imports`) | 14 in 4 files | **14 in 4 files** |
| Rule-3 census | 116 | **116** |

**`*_rule3_red.py` audit** (backlog item 24, checked because this unit touched a module
whose defect was just fixed): one such file exists, `tests/unit/test_dcf_rule3_red.py`,
and it is genuinely red — `pytest -q tests/unit/*_rule3_red.py` → `1 failed`. **No green
test is hiding inside the excluded glob.** Nothing to move out.

## Expected values — where each one came from

**Every entry below is hand arithmetic, a closed-form identity, a documented constant, or
rule 3's requirement. Nothing came from running the code.** `c:/tmp/p6b_check.py` supplied
no expected value to any test; it answers only "would this assertion still fail if the
thing it guards were broken".

| Assertion | Expected | Where it came from |
|---|---|---|
| `equity_weight == 1.0`, `debt_weight == 0.0` (3 repaired tests) | 1.0 / 0.0 | identity: E/V = 1000/(1000+0) = 1, D/V = 0/1000 = 0 |
| `wacc == 0.10` (2 repaired tests) | 0.10 | identity `WACC = 1·Re + 0·Rd·(1−t) = Re`, `strategy.md` §1; Re = 0.04 + 1.2·0.05 = 0.10 by hand |
| `cost_of_equity == 0.10` (1 repaired test) | 0.10 | hand: 0.04 + 1.2 × 0.05 = 0.04 + 0.06 = 0.10 |
| fixture arithmetic at `interest=0`: EBIT 320, EBT 320, t = 75/320 | 0.234375 | hand: 1000 − 680 = 320; 320 − 0 = 320; 75 ÷ 320 = 0.234375. Recorded in the fixture comment. **Asserted nowhere** — it is documented because it moved, not blessed |
| contradiction raises `ValueError` naming 37 and 0 | a raise | **rule 3**: "a missing input stops the run and names the field. It never falls back to zero." 37 chosen so the two figures cannot be confused |
| debt-free `cost_of_debt == 0.0` | 0.0 | definition: Rd is the rate paid on a debt balance; with no balance and no interest paid, any non-zero Rd would be an assumption that rule 6 would require to be labelled. 0.0 is the only value consistent with "nothing borrowed, nothing paid" |
| debt-free label identifies the case | contains `debt` + a no-debt phrase; contains no `assumption` / `substituted` / `supplied by the caller` | **rule 6**: a label exists to tell a measurement from a guess. Asserted as discrimination, never as wording |
| 5 NaN guards in `calculate_wacc` name their own field | a raise naming the field | rule 3 |
| `max(0.0, min(nan, 0.50)) == 0.0` | 0.0 | IEEE-754: every comparison against NaN is False, so `min`/`max` return their first argument. Written as a test so the premise behind the clamp-ordering guards is checked, not assumed |
| `nan <= x`, `nan > x`, `nan == nan` all False | False | IEEE-754 |
| beta stops below 3 observations | a raise naming 3 | `SE(beta) = sqrt(SSE / ((n−2)·Sxx))` ⇒ n − 2 ≥ 1 ⇒ n ≥ 3. Derived from the formula, and `MINIMUM_REGRESSION_OBSERVATIONS` is referenced rather than retyped |
| beta stops on a constant market series | a raise naming `variance` | OLS: beta = Cov(s,m)/Var(m); Var([0.01]×4) = 0 by inspection, so the slope divides by zero |
| beta stops on misaligned series of 3 and 4 | a raise naming both lengths | a regression pairs observations period by period; an unpaired observation has no partner |
| terminal-value NaN guards | a raise | rule 3 + the same IEEE-754 fact: `nan <= 0.02` is False so the existing spread check cannot catch it. Checked as arithmetic in `test_a_comparison_cannot_detect_the_nan_these_guards_catch` |
| `run_dcf([])` raises naming `projected_fcffs` | a raise | the terminal value is built from the final projected FCFF; an empty list has no final element |
| historical FCFF NaN tax guard | a raise naming `tax_rate` | rule 3; the consequence stated by hand: at t = 0.20 FCFF = 200 + 100·0.80 − 70 = 210, at t = 0 it is 200 + 100 − 70 = 230, so a silenced NaN reports the 230 |
| reliability label below `config.MINIMUM_BETA_R_SQUARED` | "not reliable", labels differ | the **constant** is the threshold, so half of it is on the warning side by construction. `>=` is inclusive, so exactly the minimum is on the acceptable side — the boundary most likely to be inverted |

### The two counts, with their units

- **Accuracy: 58 of 58 assertions added match an independently derived expectation.**
  Unit: assertions — 40 `assert` statements plus 18 `pytest.raises` context managers
  (wacc 19+8, capm 13+4, dcf 5+5, fcff 3+1). Plus the **7** pre-existing assertions in the
  three repaired tests, each re-verified individually above and each shown to still
  discriminate. **65 of 65 in total.**
- **Coverage: 23 of 23 module-level functions in `analysis/` are touched by at least one
  test; 255 of 255 statements and 80 of 80 branches.** Unit: functions, then statements,
  then branches. Before this unit: 244/255 statements, 8 `raise` statements unreached.

## Decisions, each with its reason

| Decision | Reason | Why this and not the alternative |
|---|---|---|
| Repaired the fixture rather than ruling against `analysis/wacc.py` | The three tests name a *debt-free company* in their own titles and docstrings, and the balance sheet's docstring says "No financial debt at all". 20 of interest contradicts that **whichever way** the accounting ambiguity resolves | Ruling against the code would have left a fixture that still describes a company its tests do not claim to be testing |
| Changed only the **input**, at three call sites. No expectation moved | Assignment step 2; `strategy.md` §1. An assertion that only passes because the input changed was testing the input | Adjusting an expected value to match a run is the failure mode this arrangement exists to prevent |
| Added a discrimination check for all 7 pre-existing assertions | The programmer's "every assertion still holds" is a claim about *passing*. Passing is not meaning: a vacuous assertion also passes | Running the three tests and seeing green proves only that they are green |
| Repaired the third call site too, though its test was already green | The override short-circuits before either statement is read, so the repair changes nothing it reads — but leaving one contradictory pairing behind blocks finding 2 exactly as it blocked this unit | Minimality that leaves a landmine is not minimal |
| Corrected the stale `1 - 0.25` in one docstring | The repair moved the fixture's tax rate to 75/320 and the comment would otherwise have been false. The identity is true for **every** t, which is stronger and is what the test actually relies on | A comment that lies about an input is how the original contradiction survived review |
| Did **not** write a red test against the over-claiming message | My brief forbids pinning a label's wording, and "should a legitimately deleveraged company be refused without an override?" is a product decision | Escalated as finding 1 |
| Did **not** assert the `total_value == 0` all-equity weights, nor the override+zero-debt weight | `strategy.md` §2 — asserting a fallback makes the defect permanent and turns its fix red | Findings 2 and 3 |
| Label tests assert discrimination, never a sentence | Assignment step 4 — "a reformat turns your test red for nothing" | A substring of the prose would break on any rewording |
| Used 37, not 20, for the contradiction message test | So the interest figure and the debt figure cannot be confused with one another when checking that the message names **both** | `"20" in message` and `"0" in message` are both satisfied by the single token `20.00` — half a stop, dressed as a whole one |

**No expected value was changed to reach a target number, and nothing was weakened,
skipped or `xfail`ed.**

## What I did not do

- **Did not edit any implementation file.** `git diff --stat` on my session touches only
  the four files in `tests/unit/`.
- **Did not touch `tests/unit/test_dcf_rule3_red.py`.** It states backlog item 2 and is
  still red.
- **Did not disturb `tests/unit/test_capm.py`'s `pytest.approx(-0.8)`** at the
  geometric-to-arithmetic switch, as instructed.
- **Did not fix, and did not pin, item 22's other half** (finding 2).
- **Did not touch backlog item 36.**
- **One scope note.** Step 5 names *raise statements*. `analysis/capm.py:136` — the
  "NOT RELIABLE" beta label added by `P6-honest-output` round 1 — is not a raise, but it
  was the last uncovered statement in `analysis/` and no unit test reached it, even though
  the programmer's own entry shows it rendered on the result page. It is in a file the
  assignment lists in scope, so I covered it with two tests that assert only that the two
  sides of `config.MINIMUM_BETA_R_SQUARED` are told apart. I am flagging the step-5
  widening rather than burying it.

## Findings for the orchestrator

1. **`analysis/wacc.py:113-126` states an inference as a fact, and its stop is therefore
   over-broad by one real case.** The message says *"A company that pays interest has
   debt, so the debt balance ... did not extract."* Two ordinary filings contradict that:
   (a) a company that repaid all its debt before the fiscal year-end reports a full year
   of interest beside a zero year-end balance — a **flow** against a **stock**; (b)
   `models/financial_statements.py` has **no lease-liability field**, so finance-lease
   interest under ASC 842, securitisation interest and interest on uncertain tax positions
   can never appear in `total_debt` by construction. **I am not asking for the stop to be
   removed** — the pattern is genuinely ambiguous and rule 3 says stop rather than guess.
   The fix is to the sentence: name **both** readings ("either the balance sheet did not
   extract, or the company repaid its borrowings before the balance sheet date") instead
   of asserting one. A user who deleveraged legitimately is currently told their filing
   failed to parse. One unit, message-only, no behaviour change, no test I wrote turns
   red — none of them asserts the wording.

2. **Item 22's other half is now unblocked, and the blocker was this fixture.** A supplied
   `--cost-of-debt` returns at `analysis/wacc.py:83-88` before either statement is read,
   so a missing balance sheet still yields `debt_value = 0` at `:211`, a debt weight of 0
   at `:230`, and the caller's rate multiplied by nothing. The programmer reported this
   and said the fix would turn a **third** test red —
   `test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt`, because
   it paired 20 of interest with a zero debt balance and an override. **That pairing is
   gone.** Its income statement now reports no interest, so a
   `total_debt == 0 and interest != 0` guard in `calculate_wacc` would not fire on it.
   I confirmed no test I wrote pins the current behaviour: the only test asserting a zero
   debt weight beside an override describes a *genuinely debt-free* company, for which a
   zero debt weight is correct rather than a fallback. **The weights fix can now be
   assigned and should be.**

3. **`analysis/wacc.py:215-223` returns `equity_weight=1.0, debt_weight=0.0` when
   `market_cap + total_debt == 0`, and this is on no backlog item.** I grepped
   `docs/9-reference/refactor-backlog.md` for it and found nothing. A company with no
   market capitalisation and no debt is not an all-equity company; it is a company whose
   inputs are missing, and rule 3 says that must stop and name the field. **This is the
   one stop path in `analysis/wacc.py` I could not lock, because the code defaults instead
   of raising.** No test asserts those weights — `test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`
   deliberately asserts only the pass-through cost of equity. It needs a backlog entry and
   a unit.

4. **The interest-expense discriminator inherits backlog item 1's blast radius, and the
   programmer flagged this against its own work.** `IncomeStatement.interest_expense`
   defaults to `0.0` (`models/financial_statements.py:84`). If an extractor ever fails to
   read interest expense, the figure arrives as `0.0` — indistinguishable from a company
   that reported none — and a company with debt lands in the *substituted* branch rather
   than the stop. The stop item 22 added is only as good as the extractor's ability to
   distinguish "zero" from "not found". That dependency is new and belongs with item 1.

5. **`tests/` now holds 146 tests and `analysis/` is at 100% statement and branch
   coverage.** `docs/5-testing/strategy.md` §4 is measured at `d1854fb` and says "the other
   five modules are at 0% — 170 statements that no test touches", and §6's "where to
   start" order is complete. That section is now badly out of date and will mislead the
   next agent into re-doing finished work. `docs/` is denied to my write guard.

**Scratch, all outside the repository:** `c:/tmp/p6b_check.py`, `c:/tmp/wacc_extra.py`,
`c:/tmp/capm_extra.py`, `c:/tmp/capm_extra2.py`, `c:/tmp/dcf_extra.py`,
`c:/tmp/fcff_extra.py`, `c:/tmp/.cov*`. Nothing copied into the repository. No network, no
API key, no PDF: every fixture is built by hand in the test file.
