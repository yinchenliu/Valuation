---
agent: tester
assignment: P4b-normalizer-verify
round: 1
status: complete
files_touched: [tests/unit/test_normalizer.py, tests/unit/test_normalizer_stops.py, tests/unit/test_normalizer_rule3_red.py]
verdict: pass
---

# P4b — the sign table derived from the accounting, and the two green tests put back inside the gate

> Opened before the first command and filled as each result landed. No implementation
> file was touched: `git status --short` shows `M tests/unit/test_normalizer.py`,
> `D tests/unit/test_normalizer_rule3_red.py`, `?? tests/unit/test_normalizer_stops.py`
> and nothing else of mine. (`M .claude/agents/tester.md` is the contract section added
> before I started; I did not write it.)

## What I did

Locked `_FIELD_EARNINGS_SIGN` with **twelve written-out cases — six fields × two
directions — plus one routing case**, every expected number derived from the *definition
of a non-GAAP adjustment* and from `IncomeStatement`'s own `ebit`/`ebt` definitions,
written into the test as arithmetic before the engine was run. **No expectation came from
the table under test and there is no loop over it.** I deliberately did not repeat the
method of the programmer and the reviewer: neither a finite difference nor a bump-and-read
appears anywhere in this unit. I then moved the two now-green rule-3 tests out of
`tests/unit/test_normalizer_rule3_red.py` into a new `tests/unit/test_normalizer_stops.py`,
strengthened each to assert the **year** as well as the type and the offending value,
deleted the red file, and fixed the known open item at the old `test_normalizer.py:223`
(`rd_expense == -50.0`, a figure no filing can print). Finally I proved the twelve cases
are falsifiable against a mutated copy outside the repository, and checked the
year-routing boundary — **which is a finding: an item whose year matches no statement is
silently discarded.**

## The two counts

| Count | Value | Unit |
|---|---|---|
| **Accuracy** | **76 of 76 match** | assertions **this unit added or changed** — 69 in the new sign section, 1 corrected routing expectation, 6 in the two recovered stop tests |
| **Accuracy, wider** | **114 of 114 pass** | every assertion in the normalizer's two test files (108 in `test_normalizer.py` + 6 in `test_normalizer_stops.py`) |
| **Coverage** | **4 of 4 functions**; **36 of 36 statements**; **16 of 16 branches**, 0 partial | functions, then statements, then branches of `analysis/normalizer.py` — measured, not estimated |

The four functions are `_resolve_field`, `_field_delta`, `apply_adjustments` and
`normalize_financials`. Every one is called by a test in `tests/unit/`. Measured with
`COVERAGE_FILE=c:/tmp/.cov_p4b … --cov=analysis --cov=models --cov-branch
--cov-report=term-missing` → `analysis\normalizer.py 36 0 16 0 100%`.

Test functions: `test_normalizer.py` 15 → **28** (13 added), `test_normalizer_stops.py`
**2** (both moved, none written from scratch). 30 collected across the two files.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the gate now runs the two recovered tests | **pass**, and the literal 92 is reproducible | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py" -k "not test_sign_"` → **`92 passed, 13 deselected in 3.21s`**, 0 failed — the baseline 90 plus the 2 recovered. The gate as written is now `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` → **`105 passed in 3.32s`**, 0 failed. `105 = 90 baseline + 2 recovered + 13 new`; see F4 |
| 2 | the whole suite is unchanged in shape | **pass** | `.venv/Scripts/python.exe -m pytest -q` → **`1 failed, 105 passed in 3.84s`**. Failure **set**, not count: `{tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent}` — identical to the baseline `1 failed, 92 passed` I measured before touching anything |
| 3 | only one red file remains | **pass** | `ls tests/unit/*_rule3_red.py` → one line, `tests/unit/test_dcf_rule3_red.py` |
| 4 | the sign is locked for 6 fields × 2 directions | **pass — 69 assertions, not 12** | 12 cases × 5 assertions each (the field, EBIT, EBT, ΔEBT, net income) + 9 in the non-operating routing case. Table below |
| 5 | the test is falsifiable | **pass — 9 of 69 assertions go red**, and 3 of 13 new test functions | `c:/tmp/p4b_mut/`, output below. Against the unmutated repository the same 69 checks give **0 red** |
| 6 | `analysis/normalizer.py` stays at 100% of statements | **pass** | `analysis\normalizer.py 36 0 16 0 100%` — statements **and** branches |
| 7 | `tests/` lints with exactly 1 error | **pass** | `.venv/Scripts/python.exe -m ruff check tests --output-format concise` → `tests\test_e2e_all_googl.py:106:16: BLE001 …`, `Found 1 error.` Repo-wide still `Found 5 errors`, all `BLE001`. `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` → `Found 33 errors in 4 files (checked 18 source files)`, unchanged |

## Expected values — where every one came from

**The definition, and the only place any of these came from.** A non-recurring item is a
one-time amount sitting inside a reported line. Normalising strips it out to leave a
clean, repeatable base. So:

* `add_back` — the item is a one-time **expense**. A clean base does not bear it, so
  clean **pre-tax earnings are higher** than reported, by exactly the amount.
* `remove` — the item is a one-time **gain**. A clean base does not enjoy it, so clean
  **pre-tax earnings are lower** than reported, by exactly the amount.

That is true of the *earnings*, **whichever line the item sat on**. Which way the *line
itself* moves is a second and different question, answered by how that line enters
earnings: the five operating lines are summed into `total_operating_expenses` and
subtracted from revenue (`models/financial_statements.py:66-77`), so such a line must
**fall** for earnings to rise; `other_non_operating` is **added** by `ebt` (`:91`), so it
must **rise** for earnings to rise. I did not consult `_FIELD_EARNINGS_SIGN` to write any
number below, and the twelve cases are written out rather than looped over it.

Fixture `_full_statement()` — every adjustable line non-zero so no sign error can hide in
a zero:

```
revenue 1000, cost_of_revenue 400, sga 200, rd_expense 120,
depreciation_amortization 80, other_operating_expense 60,
interest_expense 30, interest_income 10, other_non_operating 90, tax_expense 60

total operating expenses = 400+200+120+80+60                  = 860
EBIT   = 1000 - 860                                           = 140
EBT    = 140 - 30 + 10 + 90                                   = 210
net income = 210 - 60                                         = 150
```

Amount is 50.0 in all twelve cases, so by the definition above **EBT must be 260 for
every `add_back` and 160 for every `remove`**, and net income 200 / 100, whatever the
field. That is the invariant; the per-field numbers are its consequence.

| # | Assertion (test name) | Expected | Where the expected value came from |
|---|---|---|---|
| 1 | `sign_cost_of_revenue_add_back` | cor **350**, EBIT **190**, EBT **260**, ΔEBT **+50**, NI **200** | hand arithmetic: expense line falls, `400-50=350`; `1000-(350+200+120+80+60)=190`; `190-30+10+90=260`; `260-210=+50`; `260-60=200` |
| 2 | `sign_cost_of_revenue_remove` | cor **450**, EBIT **90**, EBT **160**, ΔEBT **−50**, NI **100** | hand: gain stripped restores the expense, `400+50=450`; `1000-(450+200+120+80+60)=90`; `90-30+10+90=160`; `160-60=100` |
| 3 | `sign_sga_add_back` | sga **150**, EBIT **190**, EBT **260**, ΔEBT **+50**, NI **200** | hand: `200-50=150`; `1000-(400+150+120+80+60)=190`; `190-30+10+90=260` |
| 4 | `sign_sga_remove` | sga **250**, EBIT **90**, EBT **160**, ΔEBT **−50**, NI **100** | hand: `200+50=250`; `1000-(400+250+120+80+60)=90`; `90-30+10+90=160` |
| 5 | `sign_rd_expense_add_back` | rd **70**, EBIT **190**, EBT **260**, ΔEBT **+50**, NI **200** | hand: `120-50=70`; `1000-(400+200+70+80+60)=190` |
| 6 | `sign_rd_expense_remove` | rd **170**, EBIT **90**, EBT **160**, ΔEBT **−50**, NI **100** | hand: `120+50=170`; `1000-(400+200+170+80+60)=90` |
| 7 | `sign_depreciation_amortization_add_back` | d&a **30**, EBIT **190**, EBT **260**, ΔEBT **+50**, NI **200** | hand: `80-50=30`; `1000-(400+200+120+30+60)=190` |
| 8 | `sign_depreciation_amortization_remove` | d&a **130**, EBIT **90**, EBT **160**, ΔEBT **−50**, NI **100** | hand: `80+50=130`; `1000-(400+200+120+130+60)=90` |
| 9 | `sign_other_operating_expense_add_back` | ooe **10**, EBIT **190**, EBT **260**, ΔEBT **+50**, NI **200** | hand: `60-50=10`; `1000-(400+200+120+80+10)=190` |
| 10 | `sign_other_operating_expense_remove` | ooe **110**, EBIT **90**, EBT **160**, ΔEBT **−50**, NI **100** | hand: `60+50=110`; `1000-(400+200+120+80+110)=90` |
| 11 | `sign_other_non_operating_add_back` | ono **140**, EBIT **unchanged 140**, EBT **260**, ΔEBT **+50**, NI **200** | hand, from the accounting: a one-time expense buried in a net **income** line depressed that line by 50, so a clean base has it 50 **higher** — `90+50=140`; EBIT cannot move because nothing operating moved; `140-30+10+140=260` |
| 12 | `sign_other_non_operating_remove` | ono **40**, EBIT **unchanged 140**, EBT **160**, ΔEBT **−50**, NI **100** | hand: the gain inflated the line, so strip it — `90-50=40`; `140-30+10+40=160` |
| 13 | `sign_a_non_operating_item_leaves_every_operating_line_untouched` | cor **400**, sga **200**, rd **120**, d&a **80**, ooe **60**, int exp **30**, int inc **10**, tax **60**, ono **140** | the fixture's own inputs, unchanged, because a below-the-line item touches no operating line. Without this, a sign error that moved an operating line by the right amount in the right direction would still reach the right EBT |
| 14 | `test_a_research_and_development_label_moves_rd_expense_and_nothing_else` (**changed**) | rd **70** (was `-50`) | hand: `120-50=70` on `_full_statement()`. See "the known open item" |
| 15 | `test_an_unrecognised_line_item_stops_the_run` | `ValueError`; message contains `Goodwill impairment charge`, `line_item`, `2021` | rule 3 (`docs/2-rules/rules.md`) and the contract: the type, the offending value, **and the field**. The year is the strengthening this unit added |
| 16 | `test_an_unrecognised_direction_stops_the_run` | `ValueError`; message contains `direction`, `addback`, `2021` | same |

**Cases 11 and 12 are the substance of the unit**, and note what they assert that a
finite-difference check does not: that **EBIT does not move at all** for a non-operating
item. Applying the expense-line rule there instead gives `ono 40` and `EBT 160` — a 100
error on a 50 item, in a line nobody reads.

Every one of the 69 passed on its first execution. **Nothing was adjusted after a run.**

## Rule 3 — what stops, and what does not

| Value read | If it were missing / wrong | Evidence |
|---|---|---|
| `item.line_item`, unrecognised label | **stops** — `ValueError` naming the offending label, the field name `line_item`, and the year | locked by `tests/unit/test_normalizer_stops.py::test_an_unrecognised_line_item_stops_the_run`. Message names: `line_item`, `'Goodwill impairment charge'`, `2021` |
| `item.direction`, not `add_back`/`remove` | **stops** — `ValueError` naming the field `direction`, the offending value, and the year | locked by `…::test_an_unrecognised_direction_stops_the_run`. Message names: `direction`, `'addback'`, `2021` |
| `item.amount`, `item.year` | constructor stops — neither has a default (`models/financial_statements.py:22,24`) | not this unit's to lock; there is no fallback to reach |
| the sign of a routed field | `_FIELD_EARNINGS_SIGN[field]` is a bare subscript — no `.get`, no `or`, no conditional. Stops with `KeyError` naming the field | **not locked by a test, on instruction**: the assignment forbids depending on the import-time `assert`, which `-O` strips. I did not write one |
| `items == []` | returns the **same object** — the documented identity, not a missing input | already locked by two pre-existing tests; I re-ran them, both pass |
| **`item.year` matching no income statement** | **DOES NOT STOP. The whole item is silently discarded** | `analysis/normalizer.py:167-170`. Measured — see **F1**. This is the one stop path I could not lock, and the reason is below |

### The stop path I did not lock, and why

`analysis/normalizer.py:167-170` builds `by_year` from the items and then iterates over the
**statements**, so any `by_year` key with no matching statement is never read. A
well-formed item — recognised label, legal direction, real amount — whose year matches no
statement is dropped with no return value, no log and no exception.

**I did not write a test for it**, and I want that recorded explicitly with both reasons:

1. A test asserting the drop (`sga` still 200, nothing raised) would be **asserting the
   fallback**, which `docs/5-testing/strategy.md` §2 and my contract forbid outright: it
   would make the silent discard permanent and turn its fix red.
2. The correct test is a **red** one asserting a `ValueError` that names the year — and a
   red test must live in `tests/unit/test_normalizer_rule3_red.py`, the exact file this
   unit was sent to delete. Writing it would contradict done-criterion 3 and re-open
   backlog item 24's shape on the same day it was closed.

So it is escalated as **F1**, not encoded. It needs its own unit, and the red test belongs
there.

## Measurements

### The suite, as failure sets

| | Before (my own baseline, before any edit) | After |
|---|---|---|
| `pytest -q` | `1 failed, 92 passed in 3.84s` | **`1 failed, 105 passed in 3.84s`** |
| failure **set** | `{test_dcf_rule3_red::test_run_dcf_stops_when_the_balance_sheet_is_absent}` | **identical** |
| `pytest -q --ignore-glob="*_rule3_red.py"` | `90 passed` — **two short, the defect** | **`105 passed`**, 0 failed |
| the same, minus this unit's new cases (`-k "not test_sign_"`) | — | **`92 passed, 13 deselected`**, 0 failed |
| `ls tests/unit/*_rule3_red.py` | 2 files | **1 file** |

### Criterion 5 — falsifiability, against a mutated copy outside the repository

`c:/tmp/p4b_mut/` holds a copy of `analysis/normalizer.py` with **exactly one line
changed** — verified, not asserted:

```
$ diff --strip-trailing-cr analysis/normalizer.py c:/tmp/p4b_mut/analysis/normalizer.py
59c59
<     "other_non_operating":       +1.0,
---
>     "other_non_operating":       -1.0,
```

The tests, run against the mutated module (confirmed by
`analysis.normalizer.__file__ == C:\tmp\p4b_mut\analysis\normalizer.py`,
`sign: -1.0`):

```
.........................FFF..                                           [100%]
FAILED tests/unit/test_normalizer.py::test_sign_other_non_operating_add_back_raises_pre_tax_earnings
FAILED tests/unit/test_normalizer.py::test_sign_other_non_operating_remove_lowers_pre_tax_earnings
FAILED tests/unit/test_normalizer.py::test_sign_a_non_operating_item_leaves_every_operating_line_untouched
3 failed, 27 passed in 0.12s
```

pytest stops a test at its first failing assert, which understates the blast radius, so
`c:/tmp/p4b_mut/count_reds.py` evaluates all 69 independently:

```
=== AGAINST THE MUTATED COPY ===
  RED  other_non_operating/add_back: other_non_operating: expected 140.0, got 40.0
  RED  other_non_operating/add_back: ebt:                 expected 260.0, got 160.0
  RED  other_non_operating/add_back: d(ebt):              expected  50.0, got -50.0
  RED  other_non_operating/add_back: net_income:          expected 200.0, got 100.0
  RED  other_non_operating/remove:  other_non_operating:  expected  40.0, got 140.0
  RED  other_non_operating/remove:  ebt:                  expected 160.0, got 260.0
  RED  other_non_operating/remove:  d(ebt):               expected -50.0, got  50.0
  RED  other_non_operating/remove:  net_income:           expected 100.0, got 200.0
  RED  routing: other_non_operating:                      expected 140.0, got  40.0

9 of 69 sign-section assertions go red

=== AGAINST THE REPOSITORY (control) ===
  (none)
0 of 69 sign-section assertions go red
```

**9, not 0.** The `ebit` assertion in each of the two cases correctly stays green — EBIT
does not move for a non-operating item whichever sign the table carries, which is itself
the reason the field-only half of the old defect was invisible. The other ten operating
cases stay green, which is what a *scoped* mutation should do: a test suite that goes
red everywhere on a one-line change is not localising anything.

### Criterion 6 — coverage

```
$ COVERAGE_FILE=c:/tmp/.cov_p4b .venv/Scripts/python.exe -m pytest -q \
    --cov=analysis --cov=models --cov-branch --cov-report=term-missing
analysis\normalizer.py              36      0     16      0   100%
models\financial_statements.py     151     13      2      0    92%   53, 57, 108, 129, 145, 162, 176, 203-207, 240, 252, 263
TOTAL                              448     16     62      1    97%
```

`analysis/normalizer.py` holds at **100% of statements and 100% of branches**, 0 partial.
`models/financial_statements.py`'s 13 uncovered statements are `gross_margin`, `eps`,
`BalanceSheet` and `CashFlowStatement` properties — outside this unit, and six of them
are conditional zeros that are themselves backlog item 1.

### The known open item — fixed, and it was cheap

`tests/unit/test_normalizer.py:223` asserted `rd_expense == -50.0`. The arithmetic was
right (`0 - 50` on a fixture whose R&D is zero) but the expected value is one **no filing
can print**, and a test whose expected value cannot occur is a weaker guard than one
whose can. The test now runs on `_full_statement()`, where R&D is 120 and the expected
value is `120 - 50 = 70`. The routing claim it makes — the item lands on `rd_expense`
and every other money field is byte-identical — is unchanged, and it still passes.

## What I did not do

- **Did not touch any implementation file.** Not `analysis/`, not `models/`. `git status
  --short` shows three test paths and my journal entry.
- **Did not write a test asserting a fallback.** Specifically not for the discarded-year
  case (F1), and not for the import-time `assert` the assignment ruled out.
- **Did not recreate `tests/unit/test_normalizer_rule3_red.py`** for F1. Reasons in the
  rule-3 section. The red test is owed; it belongs to F1's unit.
- **Did not use a finite difference, a bump-and-read, or `_FIELD_EARNINGS_SIGN` itself**
  to derive a single expected value. That method has been run twice already and would
  have added nothing.
- **Did not touch `tests/unit/test_dcf_rule3_red.py`.** It states backlog item 2 and it
  is still correctly red.

## Findings for the orchestrator

### F1 — a non-recurring item whose year matches no income statement is silently discarded · `major`, **silent**

**Evidence.** `analysis/normalizer.py:167-170` groups items into `by_year` and then
iterates the **statements**, reading `by_year.get(stmt.year, [])`. A key in `by_year` with
no matching statement is never read. Measured (`c:/tmp/p4b_year_boundary.py`), statements
2023 and 2024, one well-formed item — recognised label `sga`, legal direction `add_back`,
amount 50 — dated 2019:

```
statement years        : [2023, 2024]
item year              : 2019
RAISED                 : nothing
  2023: sga 200.0 -> 200.0, ebit 400.0 -> 400.0, same object: True
  2024: sga 200.0 -> 200.0, ebit 400.0 -> 400.0, same object: True
the 50 landed          : nowhere. It was discarded in silence.
```

**Why it is not hypothetical.** The item's year and the statements' years come from **two
separate LLM passes**: `ingestion/claude_extractor.py:259` (`int(yr["year"])`, pass 1) and
`:553` (`int(item["year"])`, pass 2, `_parse_nri_response`). Nothing reconciles them. In
the multi-filing path, `extract_multi_year` merges income statements year-by-year
(`:993-1001`) while accumulating **all** NRIs into `all_nri` (`:965`), so an item for a
year that lost the merge disappears too. The caller then renders a valuation labelled
*normalised* whose figures are in fact GAAP, with no signal anywhere — the same class of
defect as backlog item 3, which `P4-normalizer` has just closed one line above.

**Rule.** Rule 3. An item the engine cannot place is an input it does not have. The
unrecognised **label** now stops; the unplaceable **year** does not.

**What would fix it.** After building `by_year`, compare its key set against
`{s.year for s in financials.income_statements}` and raise `ValueError` naming the orphan
years and the item descriptions — the same shape and tone as the two messages
`analysis/normalizer.py:88` and `:109` already carry. **A red test stating this belongs in
a re-created `tests/unit/test_normalizer_rule3_red.py`, in that unit, not this one.**
I deliberately did not write it here: it would contradict done-criterion 3, and the only
alternative — asserting the silent drop — is the one thing my contract forbids outright.
Worth adding to the backlog as a new item.

### F2 — `NonRecurringItem.adjusted_impact`'s docstring says "operating income", and for one of the six fields that is false · `note`

**Evidence.** `models/financial_statements.py:33-36`: *"Signed impact on operating income
after adjustment. add_back -> positive (removes expense -> improves EBIT)."* For
`other_non_operating` **EBIT does not move at all** — the item sits below the operating
line. My cases 11 and 12 assert exactly that (`adjusted.ebit == 140.0`, unchanged), and
the pre-existing `test_the_ebit_move_equals_the_items_own_declared_adjusted_impact`
already had to restrict itself to operating lines for this reason and says so in its
docstring.

**Why it matters.** `analysis/normalizer.py:98-102` depends on `adjusted_impact` being the
effect on **pre-tax earnings**, which it is; the docstring says EBIT, which it is not. The
property is correct and the engine is correct — the prose would mislead the next reader
into re-deriving the defect the last unit removed. One word: *operating income* → *pre-tax
earnings (EBT)*. `models/` is out of my scope.

### F3 — `_resolve_field` matches on a **prefix**, so the new stop is a last resort rather than a strict check · `note`

`analysis/normalizer.py:86`: `if key == label or key.startswith(label)`. The stop fires
only on a label sharing no prefix with any of the twenty-one rows, so a description
beginning with e.g. `"cogs"` or `"depreciation"` routes without ever reaching the raise.
That is the documented intent (`:17-19`, "for the case where the LLM returns a description
instead of the exact field name") and I found no colliding pair among the current rows —
`"other non-operating income"` does not start with `"other operating"`. Recording it so
nobody reads "an unrecognised label now raises" as "every wrong label now raises".

### F4 — done-criterion 1's literal "92 passed" cannot survive any unit that adds a test · `note`

The gate is now `105 passed`, decomposing exactly as `90 baseline + 2 recovered + 13 new`.
I gave the literal 92 as a reproducible command (`-k "not test_sign_"`) so criterion 1 can
still be checked as written, but a criterion phrased as an absolute pass count converts
every added test into an apparent regression. `STATUS.md` will need `105`, and future
criteria are better phrased as a **failure set** plus a delta, which is how criterion 2 is
already phrased and why criterion 2 needed no such note.

### F5 — `STATUS.md` and two documents are stale in one more way after this unit · `note`, orchestrator-owned

Beyond what the `P4-normalizer` entry already listed: `docs/5-testing/strategy.md:126-129`
says the phase-1 gate is `pytest -q --ignore=tests/unit/test_dcf_rule3_red.py` → `19
passed`, and section 4's table is measured at `d1854fb` (13 files, 40 asserts, 20
collected). It is now 106 collected, and `tests/unit/` holds 8 files. Section 6's item 4
still says the normalizer's unknown-label case *"should raise and currently does not.
Write that test red"* — it raises, the test is green, and it now lives in
`tests/unit/test_normalizer_stops.py`.

## Verdict

`pass`.

All 69 sign assertions match expectations derived from the accounting before the code ran,
on the first execution, with nothing adjusted afterwards; 9 of them go red against a
one-line mutation, so they are checking something. Both stop paths that `P4-normalizer`
created are locked inside the gate, each on its exception type, its offending value, its
field name and now its year. The one stop path that does **not** stop —
`analysis/normalizer.py:167-170`, an item whose year matches no statement — is reported as
F1 rather than encoded, because the only test that could be written for it today is one
asserting the fallback.
