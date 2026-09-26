---
agent: code_reviewer
assignment: P1c-flow
round: 1
verdict: approved
---

# Review of P1c-flow, round 1

Entry under review: `.agent/journal/2026-09-20T2145-tester-p1c-flow.md` (written by the
`tester` agent, read in place of a programmer entry).

Scope confirmed. `git status --short` shows this unit's additions are exactly
`tests/unit/test_normalizer.py`, `tests/unit/test_projector.py` and
`tests/unit/test_normalizer_rule3_red.py` — the three in **Files in scope**. No
implementation file is modified; `git diff --stat` is empty. `tests/unit/test_capm.py`,
`test_fcff.py` and `test_wacc.py` are `P1b-arith`'s and were excluded from every
judgement below, as instructed.

The unit's `verdict: fail` is a verdict about stop paths in `analysis/`, not about the
deliverable. I judged the deliverable.

## The guard checks

Run over the three files in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean |
| lookup with a fallback — `.get(k, 0)` | clean |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean — the two `assumptions = {...}` literals in `test_projector.py:505,539,588` map strings to **numbers**, which rule 2 explicitly allows |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output |

Every grep returned empty. Nothing to put to the tester.

## Task 1 — F1 re-derived. It holds.

I did not take the entry's word for it. Executed
(`c:/tmp/f1_check.py`, base revenue 1000 / COGS 400 / SG&A 200 /
`other_non_operating` 80 / `tax_expense` 100, then a `remove` of a one-time **gain** of
50 routed to `other_non_operating`):

```
BEFORE ono/ebit/ebt/ni/etr: 80.0 400.0 480.0 380.0 0.208333
AFTER  ono/ebit/ebt/ni/etr: 130.0 400.0 530.0 430.0 0.188679
CLEAN  ono/ebit/ebt/ni/etr: 30.0 400.0 430.0 330.0 0.232558
EBT error: 100.0  = 2x amount? True
adjusted_impact declared: -50.0 actual dEBT: 50.0
applied derived tax_rate 0.188679 NOPAT on EBIT 400 = 324.5283
clean   derived tax_rate 0.232558 NOPAT on EBIT 400 = 306.9767
```

**The chain, link by link.**

1. `normalizer.py:68` — `delta = -item.amount if item.direction == "add_back" else item.amount`.
   `remove` therefore yields `delta = +50`. That is the **expense** convention: raise the
   cost line, lower earnings.
2. `normalizer.py:38-40` routes `"other_non_operating"`, `"other non-operating"` and
   `"non-operating"` to the field `other_non_operating`, and `NonRecurringItem`'s
   docstring (`models/financial_statements.py:16`) names it a legal `line_item`.
3. `models/financial_statements.py:91` — `ebt = ebit - interest_expense + interest_income
   + other_non_operating`. The field is **added**. `+50` on the field is `+50` on EBT, not
   `−50`. `ebit` (`:77`) does not read the field at all, so the operating-line assertions
   in `test_normalizer.py` cannot see this.
4. Measured: EBT `480 → 530`. The clean base is `80 − 50 = 30` and EBT `430`. Error
   `+100` on a `50` item — **twice the amount, in the wrong direction**, because the
   applied move and the correct move are equal and opposite. Confirmed exactly as the
   entry states.
5. `net_income = ebt − tax_expense` (`:97`): `430` where `330` is right.
6. `effective_tax_rate = tax_expense / ebt` (`:101`): **0.1887 where 0.2326 is right** —
   understated by 4.4 percentage points, because the denominator is inflated.
7. `projector.py:63-64` averages `effective_tax_rate` across years into `tax_rate`.
   Measured: `0.188679` vs `0.232558`.
8. `fcff.py`'s `NOPAT = EBIT × (1 − t)`: on an EBIT of 400, **324.53 vs 306.98 — NOPAT
   overstated by 5.7%**, in every projected year, hence in every discounted cash flow
   and in the share price. The bias is favourable, which is the direction nobody
   questions.

A ninth link the entry did not draw, and which makes the defect self-evident:
`NonRecurringItem.adjusted_impact` **declares** `−50.0` for this item while the engine
delivers `+50.0` to earnings. Two files in this repository already disagree in writing.
`test_normalizer.py:159-183` asserts that identity and deliberately restricts it to
operating lines — the restriction is honest and documented in the test's own docstring,
but it is also the exact boundary at which the defect lives.

F1 is real, it is on no backlog, no prior entry names it, and it is the most
consequential thing this unit found.

## Task 2 — are the expected values independent of the code?

Re-derived by hand, without running anything, for a sample spanning both files:

| Sampled expectation | My derivation | Agrees |
|---|---|---|
| `_three_year_financials` operating margin `0.30` | `(20/100 + 60/200 + 160/400)/3 = (0.20+0.30+0.40)/3` | yes |
| … tax rate `0.20` | EBT = EBIT (no interest, no non-operating line set), so `(4/20 + 18/60 + 16/160)/3 = (0.20+0.30+0.10)/3` | yes |
| … capex `0.15`, D&A `0.20`, nwc `0.04` | `(0.05+0.15+0.25)/3`, `(0.10+0.20+0.30)/3`, `(0.02+0.06+0.04)/3` | yes |
| … growth `[1.0]*5` | `lookback = min(3, 3−1) = 2`; `(400/100)^(1/2) − 1 = 1.00`; `projection_years` default 5 | yes |
| lookback fixture `[1,100,200,400,800]` → `1.00` | `min(3,4)=3`; `(800/100)^(1/3) − 1 = 2 − 1`. Whole period `800^(1/4) − 1 = 4.318` — a factor of four away, so the fixture genuinely discriminates | yes |
| worked example year 2 FCFF `193.6` | `1210×0.20×0.75 + 121 − 60.5 − 48.4 = 181.5 + 121 − 108.9` | yes |
| compose test FCFF `200.0` | `400×2 = 800`; `800×0.30×0.80 = 192`; `192 + 160 − 120 − 32` | yes |
| ΔNWC grown FCFF `150.0` | `1000×0.20×0.75 + 100 − 50 − 50` | yes |
| `add_back` 50 on SG&A → EBIT `450`, margin `0.45` | `1000 − (400+150)` | yes |

**Where each expectation actually comes from, checked against the documents rather than
the entry.** The five `0.0`-override tests are sourced to
`docs/4-conventions/units-and-signs.md:50-61` ("`0` is falsy … the test is `is not
None`, never truthiness") — a document, not the code. The capex-magnitude test is
sourced to the same file's §3 table, line 69. The ΔNWC direction is derivable from
`ProjectedFCFF.fcff` (`models/valuation.py:96-102`) subtracting ΔNWC, with no reference
to `projector.py:97` at all. The two identity tests are `docs/5-testing/strategy.md` §1,
line 55.

The fixture is also chosen so that **no derived figure is zero** (0.30 / 0.20 / 0.20 /
0.15 / 0.04). That is what makes each `0.0`-override assertion falsifiable, and it keeps
`_historical_average`'s zero-dropping defect out of every expectation. That is careful
work, not luck.

Assert counts reconcile exactly: `grep -c` gives **39 / 69 / 4**, matching the entry.
121 executions = 108 static + 3 (the `adjusted_impact` loop, 4 cases) + 8 (the
nine-field routing loop) + 2 (the three-spelling loop). The arithmetic checks.

## Task 3 — the mutation evidence, reproduced

I did not accept the table. I copied `analysis/`, `models/` and `config.py` to
`c:/tmp/p1c_rev_mut/src/`, copied `test_projector.py` beside them, and applied each
mutation to the **copy**. The repository was not touched.

| Mutation applied to the copy | Result I measured |
|---|---|
| drop the `−` at `projector.py:97` | **5 tests RED**, including `test_a_growing_working_capital_reduces_fcff_by_the_amount_it_grew`: `Obtained: 250.0`, expected `150.0` — the sign exactly reversed, at the FCFF level, as claimed |
| `last_revenue = revenue` → `pass` at `:148` | **3 tests RED** (`…compounds_year_on_year`, `…own_growth_rate`, the worked example) |
| `lookback = len(revenues) - 1` at `:49` | **1 test RED** — `test_the_revenue_cagr_uses_only_the_lookback_window` |
| `if ov.operating_margin` for `is not None` at `:60` | **1 test RED** — `test_a_supplied_operating_margin_of_zero_reaches_the_output` |

All four reproduce. The ΔNWC assertion — the one `docs/5-testing/strategy.md` §6 calls
the easiest thing here to reverse — is falsifiable at the point the sign changes money,
not merely at the point it is computed.

## Task 4 — does any test lock a defect?

Read every assertion and every fixture in all three files. **No test asserts a rule-3
fallback.** Three cases needed a decision and each is right:

- `test_a_growing_working_capital_reduces_fcff_by_the_amount_it_grew:459` uses
  `change_in_working_capital=0.0`. That zero flows through `np.mean([0.0])` at
  `projector.py:99`, **not** the `else 0.0` arm — the list is non-empty because the
  fixture supplies a `CashFlowStatement`. If `:99` were fixed to stop on an empty list,
  this test stays green. It does not lock anything.
- `test_capex_enters_as_a_magnitude_whichever_sign_the_filing_used` supplies one year, so
  it **executes** `_historical_cagr`'s `return 0.0` at `:25` and the resulting
  `[0.0]*5` growth. It asserts only `capex_pct_revenue`. Executing a fallback without
  asserting it is the correct handling, and the entry says so at F7.
- The five `0.0`-override tests assert a **supplied** zero reaching the output — the
  opposite of a fallback, and the requirement `units-and-signs.md` §2 states.

**The two red tests each state a requirement that is true.** `test_an_unrecognised_line_item_stops_the_run`
is backlog item 3 and rule 3, and the assignment ordered it written red.
`test_an_unrecognised_direction_stops_the_run` is rule 3 against a field with exactly two
legal values (`models/financial_statements.py:26`); a third value is an input the engine
does not have. Neither asserts the guess — neither mentions `other_operating_expense ==
−50.0` or `sga == 250.0` anywhere — so neither turns the eventual fix red. Confirmed by
reading `test_normalizer_rule3_red.py:63-113`.

## Rule 3, by reading — over the tests, since the unit writes no implementation

| Value the tests read | Stops and names it? | Evidence |
|---|---|---|
| every fixture figure | n/a — all are literals supplied in the test | `test_projector.py:85-145`, `test_normalizer.py:53-81` |
| `config.DEFAULT_REVENUE_GROWTH_LOOKBACK_YEARS` | asserted as a precondition before it is relied on | `test_projector.py:217` |
| network, API key, `.pkl`, PDF | none read. Imports are `config`, `analysis.*`, `models.*`, `pytest` only | `test_projector.py:37-46`, `test_normalizer.py:25-34` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | consistent — every fixture is a bare number in one unit, and no assertion crosses a unit boundary |
| percentages converted at the route boundary, once | n/a — this unit does not touch `api/`. All rates enter `derive_assumptions` already as decimals (`0.20`, not `20`), which is correct below the boundary |
| falsy not treated as missing | the unit **tests for** this, five times, and the mutation above proves the test catches it |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | unchanged by this unit; grep over `models/ analysis/ api/` clean |

## Done-criteria, re-run

Every number below is mine, measured with `COVERAGE_FILE` under `c:/tmp/`.

| # | Criterion | Entry claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | no unexpected failure | `90 passed`, 0 failed | `--ignore-glob="*_rule3_red.py"` → **`90 passed in 3.37s`**. Full `pytest -q` → **`3 failed, 90 passed`**, failure **set** = `{test_dcf_rule3_red::…balance_sheet_is_absent, test_normalizer_rule3_red::…line_item…, test_normalizer_rule3_red::…direction…}`. Compared as a set, not a count | yes |
| 2 | `normalizer.py` 100% | 100% (93% green-only) | `28 0 100%` with the red file; **`28 2 93% missing 50-51`** without it. Both figures reproduce, on the two different commands the entry names | yes |
| 3 | `projector.py` ≥ 90%, uncovered named | 100%, none | `68 0 22 0 100%` with `--cov-branch`. Nothing to name | yes |
| 4 | ΔNWC locked through to FCFF | 13 assertions | present and falsifiable — mutation reproduced above | yes |
| 5 | supplied `0.0` reaches output, 5 fields | 5 of 5 | `test_projector.py:336-384`, one test per field, each falsifiable against a non-zero derived answer | yes |
| 6 | every assertion sourced | 108 static / 121 executions | counts reconcile exactly (39+69 = 108; +3+8+2 = 121). I walked the tables against both files and found no unsourced assertion | yes |
| 7 | `tests/` lints with exactly 1 error | 1, the deferred `BLE001` | `ruff check tests --output-format concise` → `tests\test_e2e_all_googl.py:106:16: BLE001` / `Found 1 error.` | yes |

I also re-ran the entry's type claim: `mypy analysis/projector.py analysis/normalizer.py
--ignore-missing-imports` → **4 errors, at `:43`, `:59`, `:63`, `:129`, all
`union-attr`** — exactly as stated, and F10's split between the three type-level ones and
the one live crash path is correct by reading `models/financial_statements.py:276-282`.

I independently confirmed four of the entry's findings about `analysis/` by execution
rather than reading: **F4** (`ov.revenue_growth_rates` is `[0.1, 0.2, 0.2, 0.2]` in the
caller's own object after `derive_assumptions` returns), **F6**
(`_historical_average([0.0, 0.40]) = 0.4`, mean `0.20`), **F7** (one year of history →
`[0.0, 0.0, 0.0, 0.0, 0.0]`), **F8** (`0.90 → 0.5`, `−0.10 → 0.0`). **F5**'s
unreachability argument is sound by derivation: `rev_growth` enters the `while` either
non-empty or with `projection_years <= 0`, in which case the loop body never runs.

## Findings

### F1 — two tests call the growth-rate padding and truncation "the documented behaviour" and cite no document · `note`

**Evidence:** `tests/unit/test_projector.py:263` — *"The documented behaviour is to
extend the list to the projection horizon by repeating the final supplied rate"*;
`grep -rn "pad\|truncat" docs/ --include=*.md` returns nothing about growth rates.
**Rule or document:** none — and I checked hard before writing this, because if a rule
applied it would be `major` and the unit would not be approved. The reasoning: the
nearest thing to a document is `models/valuation.py:158`, `# Revenue growth — list per
year or single rate applied to all`, which does declare that a short list extends rather
than being an error. Under that declared field contract the year-3 rate is **not a
missing input**, so rule 3 does not bite, and the extended value is derived from a
user-supplied, user-visible assumption, so rule 6 does not bite either. What remains is
a sourcing defect: the entry's table sources these two assertions to *"the only extension
that introduces no new assumption of its own"*, which is the tester's own rationale, not
a document — the weakest sourcing anywhere in an otherwise exemplary table.
**What would fix it:** cite `models/valuation.py:158` in the two docstrings, or say in
the entry that the contract is declared in a dataclass comment and nowhere else.

### F2 — the routing test asserts a negative expense line · `note`

**Evidence:** `tests/unit/test_projector.py` — no; `tests/unit/test_normalizer.py:223`,
`assert after["rd_expense"] == pytest.approx(-50.0)`, from a fixture where `rd_expense`
starts at `0.0`.
**Rule or document:** none. The arithmetic is right and the test's purpose — proving the
adjustment lands on `rd_expense` and on none of the other nine money fields — is served.
But an R&D expense of `−50` is a statement no filing can produce: a one-time expense
cannot be embedded in a line with a zero balance. The next reader will pause on it.
**What would fix it:** start `rd_expense` at `100.0` in that one fixture and assert
`50.0`. The routing assertion is unchanged; the statement becomes one that could exist.

### F3 — one expectation rests on an unasserted default · `note`

**Evidence:** `tests/unit/test_projector.py:165`, `assert out["revenue_growth_rates"] ==
[pytest.approx(1.0)] * 5` — the `5` is `ProjectionAssumptions.projection_years`
(`models/valuation.py:155`), which the test neither supplies nor asserts.
**Rule or document:** none. It is an inconsistency with the unit's own standard: the file
pins `config.DEFAULT_REVENUE_GROWTH_LOOKBACK_YEARS == 3` as an explicit precondition at
`:217` for exactly this reason, and then does not do the same for the horizon default.
**What would fix it:** one line, `assert ProjectionAssumptions().projection_years == 5`,
or pass `projection_years` explicitly.

### F4 — the assignment contradicts itself on red tests, and the tester had to choose · `note`, for the orchestrator

**Evidence:** `.agent/assignments/P1c-flow.md:99-100` — red files are permitted *"only
for a defect already on the backlog"*; `:154-158` — known open item 2 names a defect
**not** on the backlog and says *"whether to write this red is your call."*
**Rule or document:** neither; this is an assignment defect, not a code defect. The
tester took the specific instruction over the general one, wrote the red, and stated the
cost plainly (expected failures 1 → 3). That is the defensible reading and I am not
treating it as a scope violation.
**What would fix it:** the orchestrator reconciles the two paragraphs in the next
assignment of this shape.

### F5 — F1's severity in the entry understates it · `note`, for the orchestrator

**Evidence:** the entry rates its own F1 `major`. Measured above, it is a **silent wrong
number** that reaches the share price through the effective tax rate, with a favourable
bias and no signal anywhere.
**Rule or document:** `docs/9-reference/refactor-backlog.md:20` — *"Silent: produces a
wrong number on a clean run. Nothing downstream detects it"* — the category the backlog
ranks first, and the one it gives items 2 and 3.
**What would fix it:** open it as a backlog item at that weight, jointly with F2 since
they are the same two lines, and note that `interest_income` is the same shape and must
not be added to `_LABEL_TO_FIELD` until the sign question is settled.

No finding in this review cites a rule in `docs/2-rules/rules.md`. That is the reason all
five are notes, and I checked each against the three arguments that are not grounds to
downgrade before writing it.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 — zero-default sites | `analysis/projector.py:19, 25, 99`, `normalizer.py:51` | no. Executed by the tests, asserted by none. Reported as F6/F7/F9 |
| 3 — unknown NRI line item guesses | `analysis/normalizer.py:50-51` | no. Stated as a red test, not fixed, not asserted as a fallback |
| 6 — falsy treated as missing | `api/routes_valuation.py:150-154` | no. The unit tests `derive_assumptions`, which correctly uses `is not None` at `:60, 64, 74, 83, 89` |
| 15 — `latest_year` returns `0` | `models/financial_statements.py:295` | no. Named as the upstream of F10 |

All seven "known open items" the assignment lists are reported in the entry with a
`file:line`, and I confirmed four of them by execution. None is asserted anywhere.

`STATUS.md`'s single-file `--ignore` no longer covering the suite is the orchestrator's,
per my brief, and the entry flags it as F12. Not a finding against this unit.

## Verdict

`approved`

This is the strongest deliverable I have reviewed in this repository. Both modules go
from 0% to 100% of statements and branches; every expectation I re-derived by hand
matched; every expectation I traced led to a document or to arithmetic, never to the
code's output; all four mutations reproduced, including the ΔNWC sign reversal at the
FCFF level, which is the one thing this assignment existed to make falsifiable. No test
asserts a fallback, and the two red tests state requirements that are true rather than
behaviours that differ. F1 — the `other_non_operating` sign inversion — holds under my
own arithmetic and under execution: the error is twice the item amount, it inverts the
effective tax rate, and it overstates every projected NOPAT by 5.7% on the case I ran.
It is new, it is on no backlog, and it deserves an assignment of its own. My five
findings are all notes; none blocks, and none should delay the unit.
