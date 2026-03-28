# DCF Valuation Platform

A web-based discounted cash flow (DCF) valuation tool that extracts financial data from SEC 10-K/10-Q filings using an LLM and performs fully deterministic valuation analysis.

## How It Works

1. **Upload** a 10-K or 10-Q PDF filing with a ticker symbol
2. **Extract** — the LLM reads the PDF and pulls out financial statements (I/S, C/F, B/S) and non-recurring items from footnotes
3. **Review assumptions** — historical-derived defaults (growth rates, margins, WACC) are shown on an editable form
4. **Valuation** — deterministic Python code runs the full DCF: normalize financials, CAPM beta regression, WACC, projected FCFFs, and terminal value to arrive at an implied share price

The LLM is strictly an extraction layer — it reads numbers from PDFs. All projections, adjustments, and valuation math are handled by auditable, deterministic code.

## Setup

### Prerequisites

- Python 3.10+
- An Anthropic API key (for PDF extraction via Claude)

### Installation

```bash
git clone <repo-url>
cd valuation_platform

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your-api-key-here
```

### Run

```bash
uvicorn app:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

## Project Structure

```
valuation_platform/
├── app.py                  # FastAPI entry point
├── config.py               # Default assumptions and project paths
├── ingestion/
│   ├── claude_extractor.py # LLM-powered 10-K/10-Q PDF extraction (two-pass)
│   └── price_fetcher.py    # Stock/market price data via yfinance
├── analysis/
│   ├── normalizer.py       # GAAP → Non-GAAP adjustments using extracted non-recurring items
│   ├── capm.py             # CAPM beta regression (stock vs S&P 500)
│   ├── wacc.py             # Weighted average cost of capital
│   ├── projector.py        # Derive assumptions from historicals & project future financials
│   ├── fcff.py             # Free cash flow to firm calculation
│   └── dcf.py              # Discounted cash flow valuation with terminal value
├── models/
│   ├── financial_statements.py  # Core dataclasses (FinancialStatements, NonRecurringItem)
│   ├── valuation.py             # ProjectionAssumptions, DCFResult
│   └── company.py               # Company metadata
├── api/
│   ├── routes_upload.py    # PDF upload endpoint
│   └── routes_valuation.py # Assumptions form & valuation execution
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS
└── tests/                  # End-to-end tests
```

## Valuation Pipeline

```
10-K PDF
  → LLM Pass 1: Extract financial statements (I/S, C/F, B/S)
  → LLM Pass 2: Identify non-recurring items from MD&A and footnotes
  → Normalize financials (apply non-recurring adjustments)
  → Fetch stock & market returns (yfinance)
  → CAPM beta regression → Cost of equity
  → WACC calculation
  → Project future FCFFs
  → DCF with terminal value → Implied share price
```

## Key Design Decisions

- **Single source of truth**: 10-K/10-Q PDFs are the only source for financial data — no third-party data feeds
- **LLM boundary**: The LLM extracts data from PDFs and nothing else. It does not make projections or valuation judgments
- **Two-pass extraction**: Pass 1 reads financial tables; Pass 2 analyzes footnotes for non-recurring items, using Pass 1 output as context
- **All financials in millions**, share prices per-share
- **FCFF**: Historical uses CFO-based (`CFO + Interest*(1-t) - CapEx`); projected uses EBIT-based (`EBIT*(1-t) + D&A - CapEx - dNWC`)

## Tech Stack

- **FastAPI** + **Uvicorn** — async web framework
- **Jinja2** — server-side HTML templates
- **Anthropic Claude API** — PDF financial data extraction
- **yfinance** — historical stock and market price data
- **SciPy / NumPy / Pandas** — numerical computation and data handling
