---
id: P4b-normalizer-verify
phase: 4 — the highest-cost silent defects
agent: tester
depends_on: [P4-normalizer]
---

# Verify the sign fix by hand, and put the two now-green tests back inside the gate

## Objective

Unit `P4-normalizer` fixed the sign of the adjustment engine. Three agents checked it
and agreed. **None of them was the tester**, and the tester is the role whose whole
job is to derive the expected number before the code runs.

There is also a live defect in the gate itself, caused by the fix succeeding. The two
tests that state backlog items 3 and 21 were written red, and they went green. They are
still in `tests/unit/test_normalizer_rule3_red.py`, which the gate excludes by pattern.
**So the two tests that prove the fix works are the two the gate does not run.** That is
[backlog item 24](../../docs/9-reference/refactor-backlog.md), and it is live now.

## What is already true — verify, do not redo

Measured at `4f50fd8`, 2026-09-20.

| Fact | Command |
|---|---|
| `pytest -q` → **1 failed, 92 passed** | the one failure is `test_dcf_rule3_red.py` |
| `pytest -q --ignore-glob="*_rule3_red.py"` → **90 passed** | **two short**, which is the defect |
| `pytest -q tests/unit/test_normalizer_rule3_red.py` → **2 passed** | both went green |
| `analysis/normalizer.py` is at 100% of statements | `COVERAGE_FILE=c:/tmp/.cov pytest -q --cov=analysis --cov-report=term` |
| the census is 116 | the grep in `docs/2-rules/rules.md` |

## What to do

1. **Move the two green tests out of the red pattern.** Put them in
   `tests/unit/test_normalizer.py`, or in a new `tests/unit/test_normalizer_stops.py`,
   and delete `tests/unit/test_normalizer_rule3_red.py`.

   Keep the assertions as they are unless one is weak. Each must assert the **exception
   type** and that the **message names the offending value and the year**. If either
   does not, strengthen it and say so.

   After this, `ls tests/unit/*_rule3_red.py` must list **only**
   `test_dcf_rule3_red.py`, which states backlog item 2 and is still correctly red.

2. **Lock the sign for every field, in both directions.** This is the substance of the
   unit. `_FIELD_EARNINGS_SIGN` holds six entries and one of them differs from the other
   five. A single wrong sign moves earnings by twice an item's amount, silently, on
   ordinary input.

   Derive each expectation **from the definition of the statement**, not from the table
   and not from running the code:

   - a one-time **expense** removed (`add_back`) must **raise** pre-tax earnings by the
     amount, whichever line it sat on;
   - a one-time **gain** removed (`remove`) must **lower** pre-tax earnings by the
     amount, whichever line it sat on.

   **That is the invariant, and it is the whole point of the fix:** the change in `ebt`
   equals `item.adjusted_impact`, for every field and both directions. Twelve cases.
   Assert it as twelve cases, not as a loop over the sign table — a loop over the table
   under test would take its answer from the thing it is checking.

3. **Prove the test is falsifiable.** Copy `analysis/normalizer.py` to `c:/tmp/`, flip
   the sign of `other_non_operating` in the copy, and run your tests against it. State
   in your entry **how many assertions go red**. If the answer is zero, your test is
   checking nothing and the number is what tells the next reader that.

   `docs/8-build/environment.md` section 6 owns scratch space. Do not write the copy
   inside the repository.

4. **Check the boundary the fix created.** An unrecognised label now raises. Confirm
   that an adjustment on a **recognised** label with a year that matches no statement
   does something sensible, and report what. `analysis/normalizer.py` groups items by
   year before applying them.

## Files in scope

- `tests/unit/test_normalizer.py`
- `tests/unit/test_normalizer_stops.py` (new, if you choose that layout)
- `tests/unit/test_normalizer_rule3_red.py` (delete, once its tests have moved)

**Nothing else.** Do not touch `tests/unit/test_dcf_rule3_red.py`; it states backlog
item 2, which is open, and it must stay red.

## Out of scope

- Every implementation file. You may not edit `analysis/`. If a test cannot pass
  without a code change, **that is your finding** — report it.
- `analysis/capm.py` and the NaN defect, backlog item 20. Its own unit.
- The nine scripts and their dead `sys.path.insert`, backlog item 16.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the gate now runs the two recovered tests | **92 passed, 0 failed** | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | the whole suite is unchanged in shape | **1 failed**, the rest pass | `.venv/Scripts/python.exe -m pytest -q` |
| 3 | only one red file remains | one line: `test_dcf_rule3_red.py` | `ls tests/unit/*_rule3_red.py` |
| 4 | the sign is locked for 6 fields × 2 directions | **≥ 12 assertions** | your entry's table |
| 5 | the test is falsifiable | **≥ 1 assertion goes red** against the mutated copy; state how many | your scratch run, output in your entry |
| 6 | `analysis/normalizer.py` stays at 100% of statements | 100% | `COVERAGE_FILE=c:/tmp/.cov … --cov=analysis --cov-report=term` |
| 7 | `tests/` lints with exactly 1 error | 1, the deferred `BLE001` | `.venv/Scripts/python.exe -m ruff check tests --output-format concise` |

**Criterion 5 is the one that distinguishes this unit from a formality.** Twelve
assertions that all stay green when the sign is flipped are twelve assertions that
prove nothing.

## Citations

- `docs/9-reference/refactor-backlog.md` items **19**, **3**, **21** (closed, with what
  each now raises) and **24** (the gate defect this unit fixes).
- `docs/5-testing/strategy.md` sections 1, 2 and 5.
- `docs/2-rules/rules.md` rule 3.
- `models/financial_statements.py:31-37` — `adjusted_impact`, the correct statement of
  the effect on earnings. **This is the definition your expectations come from.**
- `.agent/journal/2026-09-20T2300-programmer-p4-normalizer.md` and
  `.agent/journal/2026-09-20T2330-code_reviewer-p4-normalizer.md` — what was already
  checked, and how. **Do not repeat their method.** They both used finite differences
  on the model. Derive yours from the accounting.

## Known open items

- `tests/unit/test_normalizer.py:223` asserts `rd_expense == -50.0` — a value no filing
  can produce. It is legal arithmetic on a fixture, and the reviewer of `P1c-flow`
  raised it as a note. **Fix it if it is cheap; report it if it is not.**
- `analysis/normalizer.py` carries an import-time `assert` checking the sign table
  covers the router's range. Python strips `assert` under `-O`, after which an
  incomplete table gives `KeyError` rather than a named message. That was judged
  acceptable, because a stop is preserved. **Do not write a test that depends on the
  assert firing**, since it does not fire under `-O`.

## Backlog items this unit is NOT fixing

- **Item 2** — `analysis/dcf.py:80`. Its red test stays red; criterion 2 depends on it.
- **Item 20** — the NaN beta.
- **Item 8** — the blanket catches. The raises this unit locks are rendered as bare
  strings by `api/routes_valuation.py:220`; that is real, recorded, and not yours.
