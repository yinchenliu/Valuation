# How this repository is tested

**Open this before writing a test, or judging one.**

---

## 1. Where the expected value comes from

This repository has **no benchmark**. No trustee, no signed reference file, no published
figure to tie against. That is a deliberate decision, recorded 2026-09-20.

It removes the safest source of an expected value and leaves one trap wide open:

> **Running the code, reading what it printed, and writing that into an assertion.**

A test written that way passes forever and verifies nothing. It does not test the
formula; it photographs the current behaviour, **including the bug**. It goes green on
the day someone breaks the thing it was written to protect, because it was never
independent of it.

**So the expected side of every assertion must exist before the code runs.** Three
sources are acceptable, in this order:

| Source | How | Use it for |
|---|---|---|
| **Hand arithmetic** | inputs whose answer you can compute on paper, with the arithmetic written into the test as a comment | every formula in `analysis/` |
| **Closed-form identity** | a property that holds whatever the inputs | discounting, weighting, aggregation |
| **A figure read off a filing page** | open the PDF, read the printed number, cite the page | extraction tests only |

**Never** the code's own output. **Never** a cached `.pkl`. **Never** a number another
test already asserts.

### Choose inputs that make the arithmetic obvious

Do not test `calculate_terminal_value` with real GOOGL figures. You cannot check that by
hand, so you will end up pasting what the code said.

```python
# TV = FCFF_n * (1 + g) / (WACC - g) = 100 * 1.02 / 0.08 = 1275.0
assert calculate_terminal_value(100.0, 0.02, 0.10) == pytest.approx(1275.0)
```

Round numbers are not a weaker test. They are the only kind anyone can independently
check.

### Identities worth using here

| Identity | Why it holds |
|---|---|
| `WACC` with `debt_weight = 0` equals cost of equity | the debt term vanishes |
| `WACC` with `tax_rate = 0` equals the plain weighted average | the shield vanishes |
| a DCF with `g = 0` and constant `FCFF` → `FCFF / WACC` as n → ∞ | perpetuity |
| `NOPAT` with `tax_rate = 0` equals `EBIT` | |
| an `IncomeStatement` with no non-recurring items normalises to itself | `normalize_financials` returns early |
| `beta` of a series regressed on itself is exactly 1.0 | OLS on identical series |

That last one is the cheapest real test of `calculate_beta`, and it needs no market
data.

## 2. Lock the stop, not only the value

A correct value proves the happy path. It proves nothing about the absent case, and
[rule 3](../2-rules/rules.md) is entirely about the absent case.

For every input a function reads, write a second test: **remove the input, assert the
raise.**

- Assert the **exception type**.
- Assert the **message names the missing field**.

```python
with pytest.raises(MissingFigureError, match="net_debt"):
    run_dcf(..., financials=financials_without_balance_sheet, ...)
```

`pytest.raises(Exception)` alone passes against a bare `raise` and tells the next reader
nothing.

### Never assert a fallback

A test locking `net_debt == 0.0` when the balance sheet is missing makes
[backlog item 2](../9-reference/refactor-backlog.md) **permanent** and turns its fix
red.

**If you are about to assert a default, you have found a finding.** Report it; do not
encode it.

## 3. No network, no keys

A unit test must not need an API key, a PDF, or the internet.

- `yfinance` and the model clients are **boundaries**. Fake them.
- Build `FinancialStatements` in the test, by hand, with the few fields the function
  under test reads.
- Extraction tests use a **committed sample response**, not a live call.

A test that needs a key is not a test, it is a script. The distinction is not pedantry:
a suite that costs money to run is a suite nobody runs.

## 4. What `tests/` holds

Re-measured at `6cf34d3`:

| Measurement | `bc19431` | `6cf34d3` |
|---|---|---|
| `.py` files | 10 | **20** |
| `assert` statements | **0** | **483** |
| scripts guarded by `if __name__ == "__main__":` | **0** | **9 of 9** |
| tests collected | 0 | **146** |
| `pytest -q` | 3 collection errors | 145 pass, 1 red on purpose, 11 s |

The nine scripts now wrap their module body in `def main()` behind a guard, so
`pytest` no longer runs an LLM call, a network fetch or a DCF at import. **They were
kept, not deleted** — `tests/compare_models.py` compares provider output and
`tests/test_e2e_*.py` exercise real filings end to end.

**They are still not evidence of correctness**, and no report may cite them as such.

**Two things to know before you run one.**

1. Every script carries a `sys.path.insert` to a path belonging to a different Windows
   user, so `python tests/<name>.py` fails with `ModuleNotFoundError`. Use
   `.venv/Scripts/python.exe -m tests.<name>` until
   [backlog item 16](../9-reference/refactor-backlog.md) lands.
2. `tests/unit/test_dcf_rule3_red.py` **fails on purpose.** It states the requirement
   that `run_dcf` must stop when the balance sheet is absent. It goes green when
   backlog item 2 is fixed, and **it is kept, not deleted**. The phase-1 gate is
   `pytest -q --ignore-glob="*_rule3_red.py"` → `145 passed` until then.
   A second red test means a real regression.

   **The gate keys on the pattern, not on a filename.** An earlier revision named one
   file by path and went stale the moment a second red test landed. And when a red test
   goes green, **move it out of the pattern in the same unit** — otherwise the gate stops
   running the very test that proves the fix.

### Where the gap is now · re-measured at `6cf34d3`

```
analysis/   255 of 255 statements, 80 of 80 branches   100%
api/        118 of 126 statements                       94%
ingestion/  no tests at all
models/     exercised only through analysis/ and api/
```

**An earlier revision of this section said "the other five modules are at 0%".** That
was true at `d1854fb` and false from `796de9a` onward. It is corrected here because a
testing document that misstates the suite is worse than one that says nothing.

`analysis/` is finished. **`ingestion/` is the gap**: no test touches it, it holds 49 of
the 116 zero-default sites, and it is where the extraction boundary sits — the one place
where a figure enters this repository from outside.

**The eight uncovered arcs in `api/` are uncovered on purpose.** Each is a fallback or a
recorded backlog item a tester refused to pin, because a test asserting a known defect
makes its fix turn red. See the cache-hit branch, the yfinance share-count fallback and
the legacy `file_path` branch.

## 5. Two counts, never one

| Count | Question | Unit |
|---|---|---|
| **Accuracy** | of the values asserted, how many match? | assertions |
| **Coverage** | of the functions and branches added, how many does any test touch? | functions, then branches |

A function no test calls cannot fail, so a coverage gap reads as a clean report — and
the cleaner it reads, the worse it is. **State the unit of every count.** "12 passed" is
not a measurement until you say 12 of what, out of how many.

Measure it, do not estimate it:

```bash
.venv/Scripts/python.exe -m pytest -q --cov=analysis --cov=models --cov-report=term-missing
```

## 6. Where to start · re-measured at `6cf34d3`

The original list here ordered the six `analysis/` modules. **All six are done**, at 255
of 255 statements and 80 of 80 branches. The order below replaces it.

1. **`ingestion/`.** No test touches it. It holds 49 of the 116 zero-default sites and
   the whole extraction boundary — the one place a figure enters this repository from
   outside. Use a **committed sample response**, never a live call; a suite that costs
   money to run is a suite nobody runs.
2. **The `api/` arcs that are not deliberate.** Eight are uncovered; each is currently a
   fallback a tester refused to pin. When a backlog item closes, its arc becomes
   testable — cover it then, in the same unit.
3. **`models/`.** Exercised only through `analysis/` and `api/` today. Its properties
   carry the arithmetic that four testers have leaned on without testing directly.

Three habits this suite established, worth keeping:

- **Prove the test can fail.** Mutate the line under test in a copy under `c:/tmp/` and
  report how many assertions go red. Zero is a finding about your test.
- **Restore what you removed.** When you repair a fixture, give the removed input back
  and confirm every assertion fails again. An assertion that stays green went vacuous.
- **Do not take a claim you can run.** Three reviewers overturned a claim they had been
  handed, in each case by executing it rather than reading it.

A red test that states a true requirement is doing its job. Do not weaken it.
