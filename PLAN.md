# Financial Valuation Platform — Implementation Plan

## Context
Build a web-based DCF valuation platform for a finance professional. The system ingests S&P Capital IQ Pro Excel exports (B/S, I/S, C/F), parses raw 10-K/10-Q PDFs via Claude API to identify non-recurring items, adjusts GAAP→Non-GAAP, projects future financials, and performs DCF valuation. Built incrementally in 3 phases.

**Python:** `C:\Users\yinchenliu\Python3\python-3.14.2\python.exe`

---

## Project Structure
```
C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform\
├── app.py                      # FastAPI entry point
├── requirements.txt
├── config.py                   # Settings (API keys, defaults)
│
├── models/                     # Data models
│   ├── financial_statements.py # B/S, I/S, C/F dataclasses
│   ├── company.py              # Company metadata
│   └── valuation.py            # DCF result models
│
├── ingestion/                  # Data input layer
│   ├── capital_iq_parser.py    # Parse Capital IQ Excel exports
│   ├── price_fetcher.py        # yfinance stock + S&P 500 data
│   └── pdf_parser.py           # Phase 2: 10-K/10-Q PDF parsing
│
├── analysis/                   # Core valuation engine
│   ├── normalizer.py           # GAAP → Non-GAAP adjustments
│   ├── projector.py            # Project future financials (3-5yr)
│   ├── fcff.py                 # FCFF calculation
│   ├── capm.py                 # CAPM beta + cost of equity
│   ├── wacc.py                 # Weighted avg cost of capital
│   └── dcf.py                  # DCF valuation + terminal value
│
├── api/                        # FastAPI routes
│   ├── routes_valuation.py     # Valuation endpoints
│   ├── routes_portfolio.py     # Phase 3: portfolio endpoints
│   └── routes_upload.py        # File upload endpoints
│
├── templates/                  # Jinja2 HTML templates
│   ├── base.html
│   ├── upload.html
│   ├── assumptions.html
│   └── valuation_result.html
│
├── static/                     # CSS/JS
│   ├── style.css
│   └── charts.js               # Chart.js for visualizations
│
└── tests/
    ├── test_capital_iq_parser.py
    ├── test_fcff.py
    ├── test_capm.py
    ├── test_dcf.py
    └── sample_data/            # Sample Capital IQ exports for testing
```

---

## Implementation Order (Phase 1)
1. `models/financial_statements.py` + `models/valuation.py` — data structures first ✅
2. `ingestion/capital_iq_parser.py` — Excel ingestion (need sample file to finalize mapping) ✅
3. `ingestion/price_fetcher.py` — yfinance integration ✅
4. `analysis/capm.py` → `analysis/wacc.py` → `analysis/fcff.py` → `analysis/projector.py` → `analysis/dcf.py` ✅
5. `app.py` + `api/routes_upload.py` + `api/routes_valuation.py` — web layer ✅
6. `templates/` + `static/` — UI ✅
7. `tests/` — unit tests for core math (TODO)

---

## Phase 1 — Core DCF Engine ✅ BUILT

### 1.1 Data Models (`models/`)

**`financial_statements.py`** — Dataclasses for:
- `IncomeStatement`: revenue, COGS, gross_profit, SGA, D&A, EBIT, interest_expense, tax_expense, net_income, plus granular line items
- `BalanceSheet`: cash, receivables, inventory, PP&E, total_assets, AP, current_liabilities, long_term_debt, total_equity, etc.
- `CashFlowStatement`: CFO, capex, CFI, CFF, net_change_in_cash, D&A, SBC, delta_working_capital
- `FinancialStatements`: container holding lists of annual I/S, B/S, C/F (multiple years)

**`valuation.py`** — Dataclasses for:
- `CAPMResult`: risk_free_rate, beta, market_premium, cost_of_equity
- `WACCResult`: cost_of_equity, cost_of_debt, tax_rate, debt_weight, equity_weight, wacc
- `DCFResult`: projected_fcffs, terminal_value, enterprise_value, equity_value, per_share_value, assumptions used

### 1.2 Capital IQ Excel Ingestion (`ingestion/capital_iq_parser.py`)
- Uses `pandas` + `openpyxl` to read the consistent Capital IQ template
- Maps Capital IQ row labels → dataclass fields via substring matching
- Parses multiple years of historical data (typically 3-5 years)
- Handles three separate files: B/S, I/S, C/F
- Returns `FinancialStatements` object
- **ACTION NEEDED:** Provide a sample Capital IQ export to fine-tune row label mappings

### 1.3 Price Data (`ingestion/price_fetcher.py`)
- Uses `yfinance` to fetch:
  - Historical daily prices for the target stock (configurable lookback)
  - Historical daily prices for S&P 500 (`^GSPC`)
- Calculates daily or monthly returns
- Returns aligned stock & market returns for CAPM regression

### 1.4 CAPM Beta (`analysis/capm.py`)
- **Formula:** `E(Ri) = Rf + β × (E(Rm) - Rf)`
- Runs OLS regression via `scipy.stats.linregress`: stock returns vs. market returns → slope = β
- Risk-free rate: configurable input (default 4.0%)
- Equity risk premium: configurable (default 5.5%)
- Output: `CAPMResult` with beta, cost of equity, R², std error

### 1.5 WACC (`analysis/wacc.py`)
- **Formula:** `WACC = (E/V) × Re + (D/V) × Rd × (1 - T)`
- E = market cap (shares × current price from yfinance)
- D = total debt from balance sheet (short-term + current portion LT + long-term)
- Rd = interest expense / total debt (or user override)
- Tax rate: effective rate from I/S (or user override), clamped to 0-50%

### 1.6 Financial Projector (`analysis/projector.py`)
- Derives default assumptions from historical averages:
  - **Revenue growth:** historical CAGR
  - **Operating margin:** historical average
  - **Tax rate:** historical average effective rate
  - **CapEx, D&A, NWC:** as % of revenue (historical averages)
- All assumptions overridable by user via web UI
- Projects FCFF for each forecast year

### 1.7 FCFF Calculation (`analysis/fcff.py`)
- **Formula:** `FCFF = EBIT × (1 - Tax Rate) + D&A - CapEx - Δ Working Capital`
- Supports both historical calculation (from financial statements) and projected (from assumptions)

### 1.8 DCF Engine (`analysis/dcf.py`)
- **Terminal Value:** `TV = FCFFn × (1 + g) / (WACC - g)` (Gordon Growth Model)
- **Enterprise Value:** `EV = Σ [FCFFt / (1+WACC)^t] + TV / (1+WACC)^n`
- **Equity Value:** `EV - Net Debt`
- **Per-Share Value:** `Equity Value / Diluted Shares Outstanding`
- Validates WACC > terminal growth rate

### 1.9 FastAPI Web App
- **Upload page (`/`):** Upload 3 Capital IQ Excel files + enter ticker
- **Assumptions page (`/assumptions`):** Review/override all projection assumptions with defaults pre-populated
- **Results page (`/valuation`):** Projected FCFFs table, CAPM & WACC breakdown, DCF bridge (EV → equity value → implied price), upside/downside vs. current price

### 1.10 Normalizer (`analysis/normalizer.py`)
- Manual adjustment interface for GAAP→Non-GAAP (Phase 2 will add LLM automation)
- Applies user-specified adjustments to other_operating_expense
- Tracks non-recurring items for audit trail

---

## Phase 2 — GAAP → Non-GAAP Adjustments (LLM-Powered)

### 2.1 PDF Text Extraction (`ingestion/pdf_parser.py`)
- Use `pdfplumber` or `PyMuPDF` to extract text from 10-K/10-Q PDFs
- Focus on: financial statements section, notes to financial statements, MD&A

### 2.2 LLM Analysis (Claude API via `anthropic` SDK)
- Send extracted text to Claude API with structured prompts:
  - "Identify all non-recurring, one-time, or unusual items in this income statement"
  - "Classify each adjustment: restructuring, impairment, litigation, gain/loss on sale, etc."
  - "Provide the dollar amount and the line item affected"
- Return structured JSON of adjustments

### 2.3 Adjustment Engine (`analysis/normalizer.py`)
- Apply LLM-identified adjustments to raw GAAP financials
- Show before/after comparison (GAAP vs. adjusted Non-GAAP)
- User can approve/reject each adjustment in the UI
- Recalculate projected financials from adjusted base

---

## Phase 3 — Portfolio & Watchlist

- **Portfolio tracker:** Input current holdings (ticker, shares, cost basis), track live prices, show P&L
- **Watchlist:** List of tickers to monitor, auto-run valuation periodically
- **Recommendations:** Compare DCF-implied value vs. market price → undervalued/overvalued signal
- Store data in SQLite database

---

## How to Run
```bash
cd C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform
C:\Users\yinchenliu\Python3\python-3.14.2\python.exe -m uvicorn app:app --reload
# Open http://127.0.0.1:8000
```

---

## Verification Plan (Phase 1)
1. **Unit tests:** Test FCFF calc, CAPM regression, WACC formula, DCF math with known inputs/outputs
2. **Integration test:** Upload sample Capital IQ export → verify end-to-end valuation output
3. **Manual sanity check:** Run valuation on a well-known company (e.g., AAPL), compare implied value to analyst consensus
4. **Run the web app:** `uvicorn app:app --reload` → upload files → verify dashboard renders correctly
