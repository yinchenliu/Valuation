---
id: P1c-flow
phase: 1b — close the coverage gap, part 2
agent: tester
depends_on: [P1-suite]
---

# First real tests for `analysis/normalizer.py` and `analysis/projector.py`

## Objective

`analysis/dcf.py` is at 100% of statements. The other five modules are at **0%**. This
unit takes the two hardest: `normalizer.py` (28 statements) and `projector.py` (68).

They are hardest because each holds a decision rather than only a formula.
`normalizer.py` decides which income statement line an adjustment lands on, and
`projector.py` decides what every assumption is when the user supplies none. Both make
those decisions silently today, and both reach the share price.

`docs/5-testing/strategy.md` section 6 names the two things most worth pinning here:
the **unknown-label case, which should raise and does not**, and the **ΔNWC sign,
which is the easiest thing in this repository to reverse**.

## What is already true — verify, do not redo

Measured by the orchestrator at `19f1767`, 2026-09-20.

| Fact | Command |
|---|---|
| `pytest -q` → `1 failed, 19 passed` | the one failure is `tests/unit/test_dcf_rule3_red.py`, red on purpose |
| `analysis/normalizer.py` and `projector.py` are at 0% | `pytest -q --cov=analysis --cov-report=term` |
| `analysis/projector.py` holds 4 of the 33 mypy errors | the type gate |
| no API key is set and no `.env` exists | `ls .env` |

**`1 failed` is the expected state.** A second unexpected failure is a real regression.

## What to do

1. **Write one file per module**: `tests/unit/test_normalizer.py`,
   `tests/unit/test_projector.py`. Build every fixture by hand. No network, no key, no
   `.pkl`.

2. **Pin the two adjustment directions, by hand.** `analysis/normalizer.py:68`:

   ```python
   delta = -item.amount if item.direction == "add_back" else item.amount
   ```

   The docstring at lines 60-63 states the intent: `add_back` is a one-time **expense**
   embedded in the field, so it is subtracted, which improves adjusted earnings;
   `remove` is a one-time **gain**, so it is added, which reduces them. Assert both
   directions on a field whose starting value you chose, with the arithmetic written
   into the test.

   Then assert the **consequence**, not only the field: an `add_back` must raise EBIT
   and the operating margin. A test that checks the field but not the margin misses a
   sign error that cancels downstream.

3. **Use the identity `docs/5-testing/strategy.md` section 1 names.** An
   `IncomeStatement` with no non-recurring items normalises to **itself** —
   `normalize_financials` returns early at line 89. Assert identity, not equality of a
   rebuilt copy.

4. **Pin the ΔNWC sign.** `analysis/projector.py:97`:

   ```python
   nwc_pcts.append(-cf.change_in_working_capital / inc.revenue)
   ```

   The comment at lines 86-87 states the convention: the cash flow statement reports a
   working-capital **increase** as negative, because it is a cash outflow, and the code
   negates so `nwc_pct` is **positive** when working capital grows.

   Write the test that fails if that negation is removed. Take it all the way through
   `calculate_fcff_projected`, because the sign only matters at the point it reduces
   FCFF. State in the test, as arithmetic, what a growing working capital must do to
   FCFF: reduce it.

5. **Pin the override path separately from the derived path.** `derive_assumptions`
   takes a `ProjectionAssumptions | None`. For each of `operating_margin`, `tax_rate`,
   `da_pct_revenue`, `capex_pct_revenue` and `nwc_pct_revenue`, assert that a supplied
   override reaches the output unchanged — **including a supplied `0.0`**. Backlog item
   6 is the same defect at the route boundary; this unit proves whether
   `derive_assumptions` itself honours a zero.

6. **Pin the revenue projection compounding.** `project_fcffs:135` compounds
   `last_revenue * (1 + growth)` year on year. With a starting revenue of `100.0` and a
   flat growth of `0.10` over 3 years, the revenues are `110`, `121`, `133.1` — check
   that by hand, not by running it. A test asserting only the first year cannot see a
   compounding error.

7. **Report every stop that should exist and does not**, with its `file:line`. Do not
   assert the fallback.

## Files in scope

- `tests/unit/test_normalizer.py` (new)
- `tests/unit/test_projector.py` (new)
- `tests/unit/test_normalizer_rule3_red.py`, `tests/unit/test_projector_rule3_red.py` —
  **only if** you write a red test, and only for a defect already on the backlog.

**Nothing else.** In particular, do **not** edit `tests/unit/__init__.py`,
`tests/unit/test_dcf.py`, `tests/unit/test_dcf_rule3_red.py`, or any of the nine
scripts. Unit `P1b-arith` is running in parallel and owns `tests/unit/test_fcff.py`,
`tests/unit/test_wacc.py` and `tests/unit/test_capm.py`.

`analysis/projector.py:11` imports `calculate_fcff_projected` from `analysis/fcff.py`,
so your tests will execute `fcff.py` too. That is expected. **Do not write tests for
`fcff.py` itself** — `P1b-arith` owns it, and two units asserting the same function is
duplicated work at best and a contradiction at worst.

## Out of scope

- Every implementation file. You may not edit `analysis/`. If a test cannot pass
  without a code change, **that is your finding** — report it.
- `analysis/fcff.py`, `wacc.py`, `capm.py`. `P1b-arith` owns them.
- Any root-level configuration file. Outside your write scope.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the suite runs with no unexpected failure | only `*_rule3_red.py` files fail | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` → 0 failed |
| 2 | `analysis/normalizer.py` statement coverage | **100%** | `... --cov=analysis --cov-report=term` |
| 3 | `analysis/projector.py` statement coverage | ≥ 90%, every uncovered line named in your entry | same command |
| 4 | the ΔNWC sign is locked through to FCFF | ≥ 1 assertion, stated as arithmetic | your entry's table |
| 5 | a supplied override of `0.0` reaches the output | 1 assertion per field, 5 fields | your entry's table |
| 6 | every assertion's expected value is sourced in your entry | 1 row per assertion | the table in your entry |
| 7 | `tests/` still lints with exactly 1 error | 1, the deferred `BLE001` | `.venv/Scripts/python.exe -m ruff check tests --output-format concise` |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/5-testing/strategy.md` — section 1, section 2, section 3, section 6.
- `docs/2-rules/rules.md` rule 3 and rule 6.
- `docs/4-conventions/units-and-signs.md` — **read before writing arithmetic.** It owns
  the sign of every cash-flow field, which is most of this unit.
- `docs/3-architecture/valuation-math.md` — normalisation and the assumptions.
- `.agent/journal/2026-09-20T2010-tester-p1-suite.md` — the prior unit. Its
  "Expected values" table is the shape yours must take.

## Known open items

Report each; do not assert its fallback; do not rediscover it as new.

1. **`analysis/normalizer.py:50-51`** — an unrecognised `line_item` prints a line to
   stdout and **guesses** `other_operating_expense`. The adjustment lands on the wrong
   line, operating margin moves, and every projected year moves with it. The only
   signal is a `print` that the web app never displays. **Backlog item 3.**
   `docs/5-testing/strategy.md` section 6 says to **write that test red.** Do so, in
   `tests/unit/test_normalizer_rule3_red.py`.

2. **`analysis/normalizer.py:68`** — the direction test is `== "add_back"`, so **every
   other string**, including `"Add_Back"`, `"addback"` and a typo, silently takes the
   `remove` branch and moves the adjustment the wrong way. Rule 3. **Not on the backlog
   yet** — report it. Whether to write this red is your call; say which you chose and
   why.

3. **`analysis/projector.py:19`** — `_historical_average` returns `0.0` for an empty
   list, and drops genuine zeros from the average. A year with a real 0% margin is
   excluded rather than counted. Rule 3. **Not on the backlog yet** — report it.

4. **`analysis/projector.py:24-26`** — `_historical_cagr` returns `0.0` whenever
   `first <= 0`, `last <= 0` or `periods <= 0`. So a company with one year of data, or
   a zero in the base year, gets a silent 0% growth forecast. Rule 3. Report it.

5. **`analysis/projector.py:55`** — `rev_growth.append(rev_growth[-1] if rev_growth
   else 0.05)`. A bare **5% growth assumption**, in a literal, unlabelled, reaching
   every projected year. Rule 6. Report it.

6. **`analysis/projector.py:65`** — the tax rate is silently clamped to `[0.0, 0.50]`.
   Rule 6. Report it. `P1b-arith` was told to report the same clamp at
   `analysis/wacc.py:71`; naming it twice is expected, not duplication.

7. **`analysis/projector.py:127-129`** — `get_income_statement(latest_year)` can return
   `None`, and `.revenue` is read straight off it. These are 4 of the 33 mypy errors.
   Report it with the `file:line`.

## Backlog items this unit is NOT fixing

- **Item 1** — the 117 zero-default sites. Phase 6.
- **Item 3** — the NRI guess. Phase 4. **Stated as a red test, never fixed here.**
- **Item 6** — falsy treated as missing at the route boundary. Phase 4. Your step 5
  tests `derive_assumptions`, not the route.
- **Item 15** — `latest_year` returns `0` for an empty extraction.

## On writing a red test

Put it in a file named `*_rule3_red.py` so the gate's `--ignore-glob` covers it, give
it a docstring naming the backlog item it states, and **list every red test you wrote
in your entry**. A red test nobody knows about is a broken gate.

Where the correct behaviour is a judgement rather than a fact — the tax clamp bounds,
the 5% growth default — **report it and write no test.** That is an escalation, not a
gap.

---

## Correction by the orchestrator, 2026-09-20, after the unit closed

**This assignment contradicted itself, and the reviewer caught it.** "Files in scope"
said a red test was allowed "only for a defect already on the backlog". "Known open
items" item 2 then told the tester that writing one for `analysis/normalizer.py:68` —
which is **not** on the backlog — was its own call. The tester followed the specific
instruction over the general one, which is the defensible reading, and its red test for
the unrecognised `direction` is kept.

**The rule, corrected, for every later assignment:** a red test may state any defect
whose **correct behaviour is a fact rather than a judgement**, whether or not it is
already on the backlog. Being on the backlog was never the point; being unambiguous is.
The tax clamp bounds and the 5% growth default stay untested for that reason, and only
that reason.
