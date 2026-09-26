# Units and signs

**Open this before you write any arithmetic.** A unit error here is not subtle: it is
wrong by three or six orders of magnitude, and it still renders a share price.

---

## 1. Money is in millions. Everywhere.

Every figure in `models/`, `analysis/` and `ingestion/` is **millions of the reporting
currency**. Revenue of 350,018 means $350.018 billion.

**The two exceptions, and they are the only two:**

| Quantity | Unit | Where |
|---|---|---|
| share prices | per share, whole currency units | `PriceData.current_price`, `DCFResult.current_price`, `implied_share_price` |
| shares outstanding | millions of shares | `diluted_shares_outstanding` |

Millions ÷ millions gives a per-share figure in whole units, so the equity bridge works
without a conversion. **That is the reason share counts are in millions**, and it is
why converting one to units breaks the headline number silently.

### The one live conversion

`api/routes_valuation.py:184`:

```python
shares = info.get("sharesOutstanding", 0) / 1e6   # yfinance returns whole shares
```

yfinance reports whole shares; the repository wants millions. **Any new yfinance field
that carries a count or an amount needs the same conversion.** Market cap is computed
as `current_price * shares`, so it lands in millions too, which is what
`calculate_wacc` expects against a book debt figure already in millions.

## 2. Percentages: the form sends 4.0, the maths wants 0.04

| Layer | Form | Example |
|---|---|---|
| HTML form, CLI flag | **percent** | `4.0` |
| route / CLI parsing | ÷ 100, **once** | `4.0 / 100` |
| everything below | **decimal** | `0.04` |
| template display | × 100, or `{:.2%}` | `4.0%` |

**Convert exactly once, at the boundary.** A second conversion downstream gives 0.04%,
which produces a WACC near zero, which produces an enormous valuation that still looks
like a number.

### Falsy is not missing

`api/routes_valuation.py:150-154` does this five times:

```python
operating_margin=operating_margin / 100 if operating_margin else None,
```

`0` is falsy. A user who deliberately enters a 0% operating margin gets `None`, which
means "use the historical average" — the opposite of what they asked for. **The test is
`is not None`, never truthiness.** This is recorded as backlog item 6.

## 3. Signs

This is the part that is genuinely easy to get backwards, because the filing's
convention and the formula's convention differ.

| Field | As reported on the statement | As used in formulas here |
|---|---|---|
| `capital_expenditures` | **negative** (a cash outflow) | **positive magnitude** — every formula wraps it in `abs()` |
| `interest_expense` | positive (an expense) | **positive magnitude** — `abs()` applied |
| `debt_repaid` | negative | as reported |
| `shares_repurchased`, `dividends_paid` | negative | as reported |
| `change_in_working_capital` | **negative when NWC grows** (cash out) | **negated** — see below |

### ΔNWC: the negation, and why

The cash flow statement reports "changes in operating assets and liabilities" from the
**cash** point of view. Working capital growing **consumes** cash, so the CFS shows a
**negative** number.

The projection wants the opposite sign: a positive `nwc_pct_revenue` should mean
"working capital grows, and that reduces FCFF". So `analysis/projector.py:97` negates:

```python
nwc_pcts.append(-cf.change_in_working_capital / inc.revenue)
```

Then `calculate_fcff_projected` **subtracts** `delta_nwc`. Two sign flips that cancel
to the right answer.

**Check both halves together.** Changing one without the other reverses the effect of
working capital on the valuation and produces a plausible number in the wrong
direction.

### The `abs()` rule

Where a formula needs a magnitude, it calls `abs()` at the point of use rather than
trusting the sign:

```python
capex = abs(cash_flow.capital_expenditures)          # fcff.py:50
interest_expense = abs(income_statement.interest_expense)   # fcff.py:48
- abs(self.capital_expenditures)                     # valuation.py:100
```

This is deliberate. Extraction sign conventions vary between filings, so the formula
does not depend on getting one.

**But `abs()` also hides a sign error rather than stopping on it.** It is the right
call at a formula boundary and the wrong call anywhere a sign carries meaning. Do not
extend the pattern to a field where positive and negative mean different things —
`change_in_working_capital` is exactly such a field.

## 4. Rates and periods

| Quantity | Basis |
|---|---|
| `risk_free_rate`, `equity_risk_premium`, `wacc`, `terminal_growth_rate` | **annual**, decimal |
| `revenue_growth_rates` | **annual**, decimal, one per projection year |
| `PriceData.stock_returns` | **periodic** — monthly or daily, not annual |
| `periods_per_year` | 12 for monthly, 252 for daily |

`annualized_market_return()` in `analysis/capm.py:32` is the only place periodic returns
become an annual figure. Beta itself is unitless, so it needs no conversion — but it
**does** require the stock and market series to be at the same frequency, which
`fetch_price_data` guarantees by resampling both together.

## 5. The checks a reviewer runs

1. Does every new money literal read as millions? A `1_000_000` in this codebase is a
   trillion.
2. Is every percentage divided by 100 exactly once, at the boundary?
3. Does any new `if x:` test a numeric that could legitimately be `0`?
4. If a new field comes from yfinance, is it converted to millions?
5. If ΔNWC handling changed, did both the negation and the subtraction change?
