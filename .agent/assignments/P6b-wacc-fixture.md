---
id: P6b-wacc-fixture
phase: 7 — label the assumptions
agent: tester
depends_on: [P6-honest-output]
---

# Rule on a fixture that describes a company which cannot exist

## Objective

`P6-honest-output` round 2 closed backlog item 22. `analysis/wacc.py` now draws a
distinction it did not draw before:

| Case | Behaviour |
|---|---|
| zero debt, zero interest | a genuinely debt-free company. Returns `0.0`, **labelled** |
| zero debt, **non-zero interest** | **a contradiction.** Raises, naming both figures |

**Three tests in `tests/unit/test_wacc.py` now fail.** Its `_income_statement()` helper
defaults `interest_expense=20.0`, and three tests pair that with
`_balance_sheet_without_debt()`, whose total debt is `0`. That pairing **is** the
contradiction item 22 defines.

`pytest -q` reports `3 failed, 118 passed` against an expected `1 failed, 120 passed`.

**Your job is to rule on which side is wrong.** The programmer escalated rather than
deciding, and rather than narrowing its check to make the suite green. It was right to
escalate; the decision is a tester's.

## The question, put plainly

**Can a company report $20M of interest expense and $0 of total debt?**

- **If it can**, the new behaviour in `analysis/wacc.py` is wrong, the tests are right,
  and **that is your finding.** Report it and change nothing. You may not edit
  `analysis/`, and you must not weaken a test to accommodate code you believe is wrong.
- **If it cannot**, the fixture describes an impossible company, the tests were passing
  on an input that could never occur, and the fixture is yours to repair.

**Do not take the programmer's answer.** Its entry claims every assertion still holds
once the fixture is made self-consistent. Verify that yourself, assertion by assertion.
A fixture repaired to make a suite green is the failure mode this whole arrangement
exists to prevent, and the only thing separating a legitimate repair from that is
whether you checked.

## What is already true — verify, do not redo

Measured at `d2ba1e5` plus the uncommitted `P6-honest-output` work.

| Fact | Evidence |
|---|---|
| `pytest -q` → `3 failed, 118 passed` | the two new failures are in `tests/unit/test_wacc.py`; the third is the deliberate red |
| both new failures are at **setup**, not at an assertion | the programmer's round-2 entry |
| `_income_statement()` defaults `interest_expense=20.0` | `tests/unit/test_wacc.py` |
| `_balance_sheet_without_debt()` has total debt `0` | same file |
| lint 5, mypy 14, census 116, `GET /` 200 | unchanged |

## What to do

1. **Answer the question above, from the accounting, and write the reasoning down.**
   Interest expense is the cost of carrying debt. State what a zero balance alongside a
   non-zero cost means, and whether any real filing could produce it. Your answer
   decides the rest of this unit.

2. **If the fixture is wrong, repair it minimally.** Change the input, never an
   expectation. Then **prove every assertion in the three affected tests still holds**
   and still means what it meant — list them and say so one by one. An assertion that
   only passes because the input changed is an assertion that was testing the input.

3. **Lock the new stop.** `analysis/wacc.py` now raises on the contradiction. Assert the
   **exception type** and that the message names **both** figures — the interest and the
   debt. A message naming one is half a stop.

4. **Lock the labelled zero.** A genuinely debt-free company must still return `0.0`,
   and the label must say so. **Do not assert the label's exact wording** — assert that
   it identifies the case, or a reformat turns your test red for nothing.

5. **Close the coverage gap this unit and its predecessors opened.** Eight new `raise`
   statements across `analysis/` are reached by no test:
   `capm.py` 3, `dcf.py` 3, `wacc.py` 1, `fcff.py` 1 — re-measure, the count has moved.
   Each exists to catch a specific broken input. Supply it.

   **Do not chase the percentage.** Cover the ones whose triggering input you can state;
   name any you cannot reach and why.

## Files in scope

- `tests/unit/test_wacc.py`
- `tests/unit/test_capm.py`, `tests/unit/test_dcf.py`, `tests/unit/test_fcff.py` — **for
  step 5 only**, adding cases for the new stops.
- `tests/unit/test_wacc_stops.py` (new) — if you prefer the stops in their own file.

**Nothing else.** Do not touch `tests/unit/test_dcf_rule3_red.py`; it states backlog
item 2 and must stay red.

## Out of scope

- Every implementation file. If a test cannot pass without a code change, **that is your
  finding.**
- **Backlog item 22's other half**, which the programmer found and nobody has recorded:
  a supplied `--cost-of-debt` with a missing balance sheet still gets a **zero debt
  weight**, so the supplied rate vanishes from the WACC entirely. Fixing it would turn a
  **third** test red on the same fixture. **Report it; do not fix it and do not write a
  test that pins the current behaviour.**
- Backlog item **36**, the extraction variance. Its own unit.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | your ruling on the fixture is written down, with the accounting reasoning | a paragraph | your entry |
| 2 | the suite is back to its expected shape | **`1 failed, N passed`**, the failure being `test_dcf_rule3_red.py` | `pytest -q` |
| 3 | every assertion in the three affected tests is confirmed to still mean what it meant | one line per assertion | your entry |
| 4 | the contradiction stop is locked on type **and** both figures | ≥ 1 test | `pytest -q -k wacc` |
| 5 | the labelled zero-debt case is locked, without pinning the wording | ≥ 1 test | same |
| 6 | the new `raise` statements are covered, or each gap is named | state the count before and after | `COVERAGE_FILE=c:/tmp/.cov pytest -q --ignore-glob="*_rule3_red.py" --cov=analysis --cov-report=term-missing` |
| 7 | `tests/` lints with exactly 1 error | 1, the deferred `BLE001` | `ruff check tests --output-format concise` |

**Criterion 1 is the unit.** The tests follow from the ruling; the ruling does not
follow from the tests.

## Citations

- `docs/9-reference/refactor-backlog.md` item **22**.
- `docs/5-testing/strategy.md` section 2 — lock the stop, never assert a fallback.
- `docs/1-overview/glossary.md` — if you need the definition of interest expense.
- `.agent/journal/2026-09-22T1600-programmer-p6-honest-output-r2.md` — the escalation,
  and the claim you must verify rather than accept.

## Known open items

- The programmer says it proved every assertion still holds once the fixture is
  self-consistent. **Treat that as a claim.** It could not run your check, because it
  may not edit `tests/`.
- `tests/unit/test_capm.py:258` asserts `pytest.approx(-0.8)`, the output of the silent
  geometric-to-arithmetic switch in `analysis/capm.py`. **Not yours**, but do not
  disturb it.
