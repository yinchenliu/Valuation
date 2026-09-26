# One valuation, end to end

The sequence, and the file that owns each step. **Open the file that owns your step;
do not read the rest.**

---

```
 10-K / 10-Q PDF
       │
       ▼
 ┌─────────────────────────────────────────────────────┐
 │ 1. EXTRACT            ingestion/claude_extractor.py │  ← the only LLM step
 │    Pass 1: statements (I/S, C/F, B/S)               │
 │    Pass 2: non-recurring items, given Pass 1        │
 └─────────────────────────────────────────────────────┘
       │  FinancialStatements + list[NonRecurringItem]
       ▼
 ┌─────────────────────────────────────────────────────┐
 │ 2. NORMALISE          analysis/normalizer.py        │
 │    GAAP → Non-GAAP: apply each item to its line     │
 └─────────────────────────────────────────────────────┘
       │  FinancialStatements (adjusted)
       ▼
 ┌─────────────────────────────────────────────────────┐
 │ 3. DERIVE ASSUMPTIONS analysis/projector.py         │
 │    historical averages → growth, margin, tax,       │
 │    D&A %, CapEx %, ΔNWC %                           │
 └─────────────────────────────────────────────────────┘
       │  dict of assumptions  ──► shown to the user, editable
       ▼
 ┌─────────────────────────────────────────────────────┐
 │ 4. PRICE DATA         ingestion/price_fetcher.py    │  ← the only network step
 │    yfinance: stock and ^GSPC returns, current price │
 └─────────────────────────────────────────────────────┘
       │  PriceData
       ▼
 ┌─────────────────────────────────────────────────────┐
 │ 5. CAPM               analysis/capm.py              │
 │    OLS regression → beta → cost of equity           │
 └─────────────────────────────────────────────────────┘
       │  CAPMResult
       ▼
 ┌─────────────────────────────────────────────────────┐
 │ 6. WACC               analysis/wacc.py              │
 │    weight cost of equity and after-tax cost of debt │
 └─────────────────────────────────────────────────────┘
       │  WACCResult
       ▼
 ┌─────────────────────────────────────────────────────┐
 │ 7. PROJECT FCFF       analysis/projector.py + fcff.py│
 │    revenue → EBIT → NOPAT → FCFF, per year          │
 └─────────────────────────────────────────────────────┘
       │  list[ProjectedFCFF]
       ▼
 ┌─────────────────────────────────────────────────────┐
 │ 8. DCF                analysis/dcf.py               │
 │    discount, Gordon terminal value, equity bridge   │
 └─────────────────────────────────────────────────────┘
       │  DCFResult → implied share price
       ▼
   templates/valuation_result.html
```

---

## Which file owns which step

| Step | File | Formula owned by |
|---|---|---|
| 1 Extract | `ingestion/claude_extractor.py` | [3-architecture/extraction.md](../3-architecture/extraction.md) |
| 2 Normalise | `analysis/normalizer.py` | [3-architecture/valuation-math.md](../3-architecture/valuation-math.md) |
| 3 Assumptions | `analysis/projector.py` | same |
| 4 Price data | `ingestion/price_fetcher.py` | same |
| 5 CAPM | `analysis/capm.py` | same |
| 6 WACC | `analysis/wacc.py` | same |
| 7 Project | `analysis/projector.py`, `analysis/fcff.py` | same |
| 8 DCF | `analysis/dcf.py` | same |

## Two things about this sequence

**Only step 1 uses a model, and only step 4 touches the network.** Steps 2, 3 and 5 to
8 are pure functions of their inputs. That is the property the whole design exists to
protect — see [rule 1](../2-rules/rules.md).

**The sequence runs twice, in two places.** `api/routes_valuation.py:run_valuation()`
runs it for the web app; `cli.py:main()` runs it for the terminal. They are separate
implementations of the same eight steps, which means a fix applied to one is not
applied to the other. See
[3-architecture/entry-points.md](../3-architecture/entry-points.md).

## Where it can produce a number that means nothing

Steps 2 to 8 do not check that step 1 returned anything. Every money field in
`models/` defaults to `0.0`, so an extraction that failed entirely flows through all
eight steps and renders a share price.

**"The pipeline ran" is not evidence.** See [rule 3](../2-rules/rules.md) and
[9-reference/refactor-backlog.md](../9-reference/refactor-backlog.md) item 1.
