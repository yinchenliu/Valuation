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

### LLM Boundary (extraction only — two-pass architecture)

The LLM's role is strictly limited to **data extraction from 10-K/10-Q PDFs**, split into two focused passes per PDF:

**Pass 1 — Financial Statement Extraction (table reading)**
- Extract I/S, C/F, and optionally B/S for target years only
- Prompt focused on number precision and arithmetic reconciliation
- Year-targeted: can extract specific fiscal years instead of all years in a filing

**Pass 2 — Non-Recurring Item Analysis (footnote reasoning)**
- Analyze MD&A and Notes for one-time/unusual items
- Receives the extracted I/S summary from Pass 1 as context to anchor findings
- Returns `NonRecurringItem` list (description, amount, line item, direction, category, source)

The LLM is a **read-only extraction layer**. It does not make assumptions, projections, or valuation judgments.

**Multi-PDF smart routing** (`extract_multi_year()`): When multiple 10-K PDFs are provided, the oldest filing extracts all years (including comparatives), while newer filings extract only their primary fiscal year. B/S is extracted only from the most recent filing. This avoids duplicate extraction across overlapping comparative years.

### Deterministic Code (everything else)

All financial logic after extraction is handled by deterministic, auditable Python code so that **every number can be traced back to its formula and inputs**:
- **GAAP → Non-GAAP adjustments** (`normalizer.py`) — applies LLM-identified non-recurring items to raw financials
- **Ratio assumptions** (`projector.py`) — derives historical averages (margins, growth rates, CapEx/D&A/NWC as % of revenue)
- **Projections** (`projector.py`) — projects future financials from assumptions
- **Valuation** (`capm.py`, `wacc.py`, `fcff.py`, `dcf.py`) — CAPM beta regression, WACC, FCFF, DCF with terminal value

### Pipeline flow in code

`routes_valuation.py:run_valuation()` orchestrates the full pipeline:
1. `claude_extractor.extract_financials()` → Pass 1 (I/S + C/F + B/S) → Pass 2 (NRIs using I/S context) → `FinancialStatements` + `NonRecurringItem` list
   - For multi-PDF: `extract_multi_year()` routes years to filings, merges results
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
