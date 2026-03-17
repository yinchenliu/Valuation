# DCF Valuation Platform

A web-based discounted cash flow (DCF) valuation tool for equity analysis. Upload S&P Capital IQ Pro financial statement exports, configure assumptions, and get an implied share price in minutes.

## Quick Start

```bash
cd C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform

# Install dependencies
C:\Users\yinchenliu\Python3\python-3.14.2\python.exe -m pip install -r requirements.txt

# Run the server
C:\Users\yinchenliu\Python3\python-3.14.2\python.exe -m uvicorn app:app --reload

# Open http://127.0.0.1:8000
```

## User Workflow

1. **Upload** — Go to `/`, upload 3 Capital IQ Excel files (I/S, B/S, C/F) and enter the ticker symbol.
2. **Assumptions** — Review defaults derived from historical data. Override revenue growth, margins, WACC inputs, etc.
3. **Results** — View implied share price, CAPM/WACC breakdown, projected FCFFs, and valuation bridge.

## Project Structure

See [architecture.md](architecture.md) for full module documentation.

```
valuation_platform/
├── app.py                          # FastAPI entry point
├── config.py                       # Default settings & paths
├── requirements.txt
├── models/
│   ├── financial_statements.py     # I/S, B/S, C/F dataclasses
│   ├── company.py                  # Company metadata
│   └── valuation.py                # CAPM, WACC, DCF result models
├── ingestion/
│   ├── capital_iq_parser.py        # Parse Capital IQ Excel exports
│   └── price_fetcher.py            # yfinance historical prices
├── analysis/
│   ├── capm.py                     # CAPM beta regression + cost of equity
│   ├── wacc.py                     # Weighted average cost of capital
│   ├── fcff.py                     # Free cash flow to firm
│   ├── projector.py                # Project future financials
│   ├── dcf.py                      # DCF with Gordon Growth terminal value
│   └── normalizer.py               # GAAP → Non-GAAP adjustments
├── api/
│   ├── routes_upload.py            # File upload endpoints
│   └── routes_valuation.py         # Assumptions + valuation pipeline
├── templates/                      # Jinja2 HTML templates
├── static/                         # CSS
└── docs/                           # Documentation
```

## Key Formulas

| Formula | Definition |
|---------|-----------|
| **CAPM** | `E(Ri) = Rf + β × (Rm - Rf)` |
| **WACC** | `(E/V) × Re + (D/V) × Rd × (1 - T)` |
| **FCFF** | `EBIT × (1 - T) + D&A - CapEx - ΔWC` |
| **Terminal Value** | `FCFF_n × (1 + g) / (WACC - g)` |
| **Enterprise Value** | `Σ PV(FCFF_t) + PV(Terminal Value)` |
| **Equity Value** | `Enterprise Value - Net Debt` |
| **Implied Price** | `Equity Value / Diluted Shares` |

## Dependencies

- **fastapi** + **uvicorn** — Web framework and ASGI server
- **jinja2** — HTML templating
- **pandas** + **openpyxl** — Excel parsing
- **numpy** + **scipy** — CAPM regression
- **yfinance** — Historical stock & S&P 500 prices
- **python-multipart** — File upload support

## Roadmap

- **Phase 1** (Complete): Core DCF engine, Capital IQ parser, web UI
- **Phase 2** (Planned): PDF 10-K/10-Q parsing with Claude API for automated GAAP → Non-GAAP adjustments
- **Phase 3** (Planned): Portfolio tracking, watchlist, undervalued/overvalued recommendations
