# The formulas

Every calculation in `analysis/`, with the file and function that owns it. Terms are
defined in [1-overview/glossary.md](../1-overview/glossary.md); signs and units in
[4-conventions/units-and-signs.md](../4-conventions/units-and-signs.md).

**Each formula names one function.** That is [rule 2](../2-rules/rules.md). If you
cannot find the function, the formula does not exist yet.

---

## 1. Normalisation — `analysis/normalizer.py`

GAAP figures, with one-time items stripped out.

```
adjusted_field = reported_field + delta
```

where, per `apply_adjustments`:

| `direction` | delta | Effect on EBIT |
|---|---|---|
| `add_back` | `− amount` | the expense shrinks, adjusted earnings **rise** |
| `remove` | `+ amount` | the cost rises, adjusted earnings **fall** |

The item lands on **the field it was embedded in**, named by `NonRecurringItem.line_item`
and resolved by `_resolve_field`. Not always `other_operating_expense` — that was the
old behaviour and it moved money to the wrong line.

> **Defect, recorded.** `_resolve_field` (`normalizer.py:46`) **guesses**
> `other_operating_expense` for any label it does not recognise, prints a warning to
> stdout, and continues. An unknown label means the adjustment is applied to the wrong
> line and the margin moves. It must raise. Backlog item 3.

## 2. Assumptions — `analysis/projector.py:derive_assumptions`

Each assumption is a historical average, overridable by the user.

| Assumption | Derivation | Function |
|---|---|---|
| revenue growth | CAGR over a 3-year lookback | `_historical_cagr` |
| operating margin | mean of non-zero historical `ebit / revenue` | `_historical_average` |
| tax rate | mean of non-zero `tax_expense / ebt`, **clamped to [0, 0.50]** | `_historical_average` |
| D&A % revenue | mean of non-zero `D&A / revenue` | `_historical_average` |
| CapEx % revenue | mean of non-zero `abs(capex) / revenue` | `_historical_average` |
| ΔNWC % revenue | **plain** mean of `−change_in_working_capital / revenue` | `np.mean` |

```
CAGR = (last / first) ^ (1 / periods) − 1
```

**Three things here are not obvious and are deliberate:**

**The 3-year lookback** (`config.DEFAULT_REVENUE_GROWTH_LOOKBACK_YEARS`) exists so a
single macro year does not set the growth rate for the whole projection. A full-period
CAGR anchored on a 2020 trough overstates growth for five years.

**ΔNWC uses a plain mean, not `_historical_average`.** `_historical_average` drops
zeros; a zero working-capital change is a real observation, so dropping it would bias
the average. `projector.py:98` says so in a comment.

**The tax clamp to 50%** prevents a loss year — where `ebt` is small or negative —
producing an absurd effective rate that then multiplies through every projected year.

> **Defect, recorded.** `_historical_average` returns `0.0` for an empty list
> (`projector.py:19`). If extraction returned nothing, every assumption is `0.0`, and
> the DCF runs to completion on an all-zero company. Backlog item 1.

## 3. Historical FCFF — `analysis/fcff.py:calculate_fcff_historical`

**CFO-based**, because the cash flow statement is a reported fact:

```
FCFF = CFO + interest_expense × (1 − t) − CapEx
```

Interest is added **back** because US GAAP classifies interest paid as an operating
activity, so CFO is already net of it. FCFF is a **pre-financing** measure — cash
available to debt and equity holders both — so the financing cost has to come back out.
It is added after tax because interest is tax-deductible.

## 4. Projected FCFF — `analysis/fcff.py:calculate_fcff_projected`

**EBIT-based**, because there is no future cash flow statement to read:

```
EBIT   = revenue × operating_margin
NOPAT  = EBIT × (1 − t)
FCFF   = NOPAT + D&A − CapEx − ΔNWC
```

### The two are not interchangeable

| | Historical | Projected |
|---|---|---|
| Starts from | reported CFO | modelled EBIT |
| Treats SBC as | **non-cash** (inside CFO's add-backs) | **a cost** (inside operating margin) |
| Working capital | already inside CFO | modelled explicitly as ΔNWC |

For a company with heavy stock-based compensation the CFO-based figure is **materially
higher**. Both are defensible; they answer different questions. `models/valuation.py:43`
records this on `HistoricalFCFF`.

**Never compare a historical FCFF to a projected one and call the difference a trend.**
It is largely a definitional gap.

## 5. CAPM — `analysis/capm.py`

```
β                = slope of OLS(stock_returns ~ market_returns)
market_return    = (∏(1 + r))^(periods_per_year / n) − 1        # geometric
ERP              = market_return − Rf        # when not supplied
cost_of_equity   = Rf + β × ERP
```

`calculate_beta` uses `scipy.stats.linregress` and also returns R² and the standard
error. **Both are reported, not used.** A low R² means β is a weak estimate; that is a
fact about the measurement and it belongs in front of the user.

`annualized_market_return` compounds geometrically, then falls back to an arithmetic
annualisation if compounding wipes out (`gross <= 0`). That fallback is a genuine
numerical guard, not a rule 3 violation: it handles a mathematically impossible input,
it does not paper over a missing one.

## 6. WACC — `analysis/wacc.py`

```
Rd    = interest_expense / total_debt
WACC  = (E/V) × Re + (D/V) × Rd × (1 − t)
```

where `E` = market cap (price × diluted shares), `D` = **book** total debt, `V` = E + D.

Book value stands in for the market value of debt. For investment-grade debt near par
that is close; for distressed debt it is not, and nothing here detects the difference.

The tax rate is clamped to [0, 0.50], as in the assumptions.

> **Defect, recorded.** When `total_debt > 0` but `interest_expense == 0` — interest
> not separately reported — `wacc.py:43` substitutes `config.DEFAULT_COST_OF_DEBT`
> (4.0%). That assumption reaches WACC, every discounted cash flow, and the share
> price, and **nothing in the output says it happened.** [Rule 6](../2-rules/rules.md).
> Backlog item 9.

## 7. DCF — `analysis/dcf.py`

```
PV(FCFFs)  = Σ  FCFF_t / (1 + WACC)^t                for t = 1..n
TV         = FCFF_n × (1 + g) / (WACC − g)           Gordon Growth
PV(TV)     = TV / (1 + WACC)^n
EV         = PV(FCFFs) + PV(TV)
equity     = EV − net_debt − noncontrolling_interest
price      = equity / diluted_shares
upside %   = (price / current_price − 1) × 100
```

`calculate_terminal_value` **raises** when `WACC <= g` (`dcf.py:24`). That is the one
place in `analysis/` that already behaves the way [rule 3](../2-rules/rules.md)
requires everywhere. Copy its shape.

**Discounting is end-of-period.** Year 1 is discounted a full year. A mid-year
convention would divide by `(1 + WACC)^(t − 0.5)` and would raise the valuation by
roughly half a year's discount. This repository does not use one; if that changes it is
a decision to record, not a tweak.

### The terminal value usually dominates

With a 5-year window and typical rates, PV(TV) is commonly 70–80% of enterprise value.
So `g` and `WACC` matter far more than any single projected year, and the two appear
together in a denominator — `WACC − g` — which makes the result **highly sensitive**
when they are close. A move from `WACC − g = 0.06` to `0.05` raises TV by 20%.

Show both inputs next to the result. A share price whose terminal assumptions are not
visible is not auditable.

## 8. The equity bridge — `models/financial_statements.py:191`

```
net_debt = total_debt − cash_and_equivalents − short_term_investments
```

`total_debt` (`short_term_debt + long_term_debt`) includes finance lease obligations
(both current and long-term) and excludes operating lease obligations, on the user's
decision of 2026-10-04 ("83a", backlog item 83). Operating lease obligations are
operating liabilities and are excluded from financial debt (mapped to other
current/non-current liabilities).

Short-term investments count as liquid. They are marketable securities that can service
debt or be returned to shareholders, and excluding them **understates** the company's
liquidity and so **understates** equity value. This follows standard equity-bridge
practice and is recorded in the dataclass docstring.

### Noncontrolling interest — subtracted since `P10a` (backlog item 48)

```
noncontrolling_interest = nonredeemable + redeemable        total_noncontrolling_interest
equity                  = EV − net_debt − noncontrolling_interest
```

Pass 1 asks for **consolidated** net income and cash flows, which include the share of
the group that belongs to minority holders, so the enterprise value values the whole
group. The parent's equity is what is left after net debt **and** the noncontrolling
interests, at the book value the filing prints. No market value is estimated.

The filing prints the two parts on separate lines and their sum on none, so Pass 1 reads
each line (`noncontrolling_interest_nonredeemable`, inside equity;
`noncontrolling_interest_redeemable`, outside it) and
`analysis/dcf.py:total_noncontrolling_interest` adds them. That function is the only place
the sum is taken ([rule 1](../2-rules/rules.md)). It **stops**, naming the key and the year,
when either part is `None` ("not extracted") or NaN. A filing that prints no such line is
extracted as an explicit `0`.

`run_dcf` carries the total on `DCFResult` as its own field, beside `net_debt`, with a
source string naming both parts and their figures, and both outputs print it as a "Less:
Noncontrolling" line.

Walmart fiscal 2026 (PDF page 22): 6,270 nonredeemable + 293 redeemable = 6,563, or
about $0.82 a share on 8,022 million diluted shares.

### A missing balance sheet stops — backlog item 2, fixed in code by `P10a` round 2

`run_dcf` raises when the latest year has no balance sheet, naming net debt, cash and the
noncontrolling interests and the year. Before `P10a` it used `latest_bs.net_debt if
latest_bs else 0.0`: a missing balance sheet gave **zero net debt** and overstated equity
value by the entire debt balance, on a clean run, with no warning.
