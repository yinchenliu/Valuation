# Valuation Platform

Web-based DCF valuation platform. Parses 10-K/10-Q PDF filings via LLM, fetches market data via yfinance, and performs discounted cash flow valuation.

## Quick Reference

```bash
# Run the app
C:\Users\yinchenliu\Python3\python-3.14.2\python.exe -m uvicorn app:app --reload

# Run E2E test (LLM extractor, requires API key)
C:\Users\yinchenliu\Python3\python-3.14.2\python.exe tests/test_e2e_phase2_googl.py

# Install dependencies
C:\Users\yinchenliu\Python3\python-3.14.2\python.exe -m pip install -r requirements.txt
```

## Architecture

```
Upload 10-K PDF → LLM Extraction → FinancialStatements + NonRecurringItems (dataclass contracts)
                                              ↓
                  Deterministic Analysis: Normalize → CAPM → WACC → Project → FCFF → DCF
                                              ↓
                  FastAPI routes → Jinja2 templates → Browser
```

### LLM Boundary (extraction only)

The LLM's role is strictly limited to **data extraction from 10-K/10-Q PDFs**:
1. **Parse financial statements** — read the B/S, I/S, C/F from the filing and return the `FinancialStatements` dataclass contract. Every number must come directly from the source PDF. The LLM must NOT hallucinate, estimate, or project any financial figures.
2. **Analyze footnotes** — identify non-recurring/one-time items from the notes to financial statements and return the `NonRecurringItem` dataclass contract (description, amount, line item, direction, category, source reference).

The LLM is a **read-only extraction layer**. It does not make assumptions, projections, or valuation judgments.

### Deterministic Code (everything else)

All financial logic after extraction is handled by deterministic, auditable Python code so that **every number can be traced back to its formula and inputs**:
- **GAAP → Non-GAAP adjustments** (`normalizer.py`) — applies LLM-identified non-recurring items to raw financials
- **Ratio assumptions** (`projector.py`) — derives historical averages (margins, growth rates, CapEx/D&A/NWC as % of revenue)
- **Projections** (`projector.py`) — projects future financials from assumptions
- **Valuation** (`capm.py`, `wacc.py`, `fcff.py`, `dcf.py`) — CAPM beta regression, WACC, FCFF, DCF with terminal value

### Pipeline flow in code

`routes_valuation.py:run_valuation()` orchestrates the full pipeline:
1. `claude_extractor.extract_financials()` → `FinancialStatements` + `NonRecurringItem` list (from 10-K PDF)
2. `normalizer.normalize_financials()` → adjusted (Non-GAAP) financials
3. `projector.derive_assumptions()` → default projection assumptions from historicals
4. `price_fetcher.fetch_price_data()` → stock/market returns for CAPM
5. `capm.run_capm()` → beta, cost of equity
6. `wacc.calculate_wacc()` → weighted average cost of capital
7. `projector.project_fcffs()` → projected FCFFs
8. `dcf.run_dcf()` → enterprise value, equity value, implied share price

## Key Conventions

- **Single source of truth:** 10-K/10-Q PDFs are the only source for financial data. No Capital IQ or other third-party data feeds.
- **Units:** All financial data is in millions. Share prices are per-share.
- **FCFF approach:** Historical uses CFO-based (`CFO + Interest*(1-t) - CapEx`). Projected uses EBIT-based (`EBIT*(1-t) + D&A - CapEx - dNWC`).
- **Dataclass-driven:** `models/` defines the data contract. `FinancialStatements` is the central type that flows through the entire pipeline.
- **Form values are percentages:** The web UI sends values like `4.0` (meaning 4%), which routes convert to decimals (`0.04`) before passing to analysis functions.
- **Net debt:** Includes cash + short-term investments as liquid assets (standard IB equity bridge convention).

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `models/` | Dataclasses: `FinancialStatements`, `NonRecurringItem`, `DCFResult`, `ProjectionAssumptions`, etc. |
| `ingestion/` | LLM-powered 10-K PDF extraction (`claude_extractor.py`), yfinance price fetcher |
| `analysis/` | Deterministic valuation math: normalizer, CAPM, WACC, FCFF, projector, DCF |
| `api/` | FastAPI routes: upload, assumptions form, valuation execution |
| `templates/` | Jinja2 HTML: upload → assumptions → results pages |
| `static/` | CSS styling (`style.css`), charts placeholder |
| `tests/` | E2E tests and debug/audit scripts |
