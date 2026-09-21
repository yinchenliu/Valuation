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

## 4. What `tests/` holds today, and why it is not a suite

Measured at `bc19431`:

| Measurement | Value |
|---|---|
| files | 10 |
| `assert` statements | **0** |
| files guarded by `if __name__ == "__main__":` | **0** |
| `pytest -q` | 3 collection errors, 0 tests |

Because nothing is guarded, every file runs its whole pipeline — LLM call, network
fetch, DCF — at **import**. `pytest` therefore makes paid API calls during collection
and fails before running a test.

**These are scripts, and they are useful.** `tests/compare_models.py` compares provider
output; `tests/test_e2e_*.py` exercise real filings end to end. Keep them. Move them
where `pytest` does not collect them, or guard them behind `__main__`.

**They are not evidence of correctness**, and no report may cite them as such.

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

## 6. Where to start

The backlog's suggested order puts tests first, because nothing else can be verified
without them. In priority:

1. `analysis/dcf.py` — `calculate_terminal_value`, `discount_cash_flows`. Pure
   arithmetic, trivially hand-checkable, and the `WACC <= g` raise is already correct
   and worth locking.
2. `analysis/fcff.py` — both formulas, with the SBC divergence made explicit.
3. `analysis/wacc.py` — the identities above, plus the cost-of-debt fallback as a
   **finding**, not an assertion.
4. `analysis/normalizer.py` — `add_back` and `remove` directions, and the unknown-label
   case, which should raise and currently does not. **Write that test red.**
5. `analysis/projector.py` — the ΔNWC sign, which is the easiest thing here to reverse.

A red test that states a true requirement is doing its job. Do not weaken it.
