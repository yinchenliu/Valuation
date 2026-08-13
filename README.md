# DCF Valuation Platform

A web-based discounted cash flow (DCF) valuation tool that extracts financial data from SEC 10-K/10-Q filings and analyze non-recurring items using an LLM and performs fully deterministic valuation analysis.

## How It Works

1. **Upload** a 10-K or 10-Q PDF filing with a ticker symbol
2. **Extract** — the LLM reads the PDF and pulls out financial statements (I/S, C/F, B/S) and non-recurring items from footnotes
3. **Review assumptions** — historical-derived defaults (growth rates, margins, WACC) are shown on an editable form
4. **Valuation** — deterministic Python code runs the full DCF: normalize financials, CAPM beta regression, WACC, projected FCFFs, and terminal value to arrive at an implied share price

The LLM is strictly an extraction layer — it reads numbers from PDFs. All projections, adjustments, and valuation math are handled by auditable, deterministic code.

## Setup

### Prerequisites

- Python 3.10+
- A Google Gemini API key (default) or Anthropic API key (for PDF extraction)

### Installation

```bash
git clone <repo-url>
cd valuation_platform

pip install -r requirements.txt
```

Copy `.env.example` to `.env` in the project root and fill in what you need:

```bash
cp .env.example .env
```

`.env` is gitignored and is loaded by `config.py` at import time.

**Claude auth comes in two flavours — pick one:**

| Where your key is from | What to set |
|---|---|
| Anthropic Console (`sk-ant-...`) | `ANTHROPIC_API_KEY` |
| **Google Cloud (Vertex AI)** | `CLAUDE_PROVIDER=vertex`, `CLAUDE_VERTEX_PROJECT_ID`, `CLAUDE_VERTEX_REGION` |
| Google AI Studio (`AIza...`) | `GEMINI_API_KEY` — Gemini only, see [Agentic mode](#agentic-mode) |

Vertex does **not** use an Anthropic API key — putting a Google-issued key in
`ANTHROPIC_API_KEY` will fail. It authenticates with Google credentials instead:

```bash
pip install "anthropic[vertex]"
gcloud auth application-default login     # or set GOOGLE_APPLICATION_CREDENTIALS
```

Then enable the model in Vertex AI Model Garden for your project. Model IDs are
the same bare strings on both backends (`claude-sonnet-5`), with no prefix.

### Run

```bash
uvicorn app:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

### Run the CLI from a ticker folder

Put the company's 10-K PDFs in a folder named for its ticker:

```text
10K_filings/
└── LLY/
  ├── LLY_10K_2023-12-31.pdf
  ├── LLY_10K_2024-12-31.pdf
  └── LLY_10K_2025-12-31_English.pdf
```

Then pass only the folder. The ticker is inferred from the folder name and the
fiscal year from the first four digits of each filing date:

```bash
python cli.py 10K_filings/LLY
```

Both `10K` and `10-K` are accepted in filenames. The existing explicit form
also remains available:

```bash
python cli.py 2023:10K_2023.pdf 2024:10K_2024.pdf -t LLY
```

## Project Structure

```
valuation_platform/
├── app.py                  # FastAPI entry point
├── config.py               # Default assumptions and project paths
├── pipeline.py             # ValuationRun + one re-runnable function per step
├── llm_client.py           # Picks the provider and builds its client
├── gemini_client.py        # Gemini behind the Anthropic Messages interface
├── agent/                  # Agentic orchestration: tools, loop, transcript
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
  → Fetch stock & market returns (yfinance), risk-free rate (^TNX)
  → CAPM beta regression → Cost of equity
  → WACC calculation
  → Project future FCFFs
  → DCF with terminal value → Implied share price
```

Every stage lives in `pipeline.py` as an independently re-runnable step. The
fixed order above is `run_full_pipeline()`; agentic mode calls the same steps in
whatever order the filing warrants.

## Agentic mode

The same eight steps can be run in a fixed order or sequenced by an LLM:

```bash
# Fixed pipeline (default)
python cli.py 10K_filings/LLY

# The model decides which tool to call next, and reports an audit trail
python cli.py 10K_filings/LLY --agentic

# Same loop, orchestrated by Gemini instead of Claude
python cli.py 10K_filings/LLY --agentic --agent-provider gemini
```

In agentic mode the model inspects what was extracted, validates the arithmetic,
decides which assumptions to accept or override, and can retry a step with
different inputs — for example lowering terminal growth after a `WACC <= g`
failure. It gets one tool per pipeline step and **calls those tools for every
number**; it never does arithmetic itself. The run ends with a printed audit
trail of each call, its inputs, and its result.

Both modes call the same deterministic functions, so they produce the same
numbers for the same assumptions. `tests/test_agent_tools.py` asserts this.

### Choosing the orchestrating model

| | Claude | Gemini |
|---|---|---|
| Credentials | `ANTHROPIC_API_KEY`, or Vertex (see [Setup](#setup)) | `GEMINI_API_KEY` |
| Default model | `claude-opus-5` | `gemini-3.1-pro-preview` |
| Override the model | `CLAUDE_AGENT_MODEL` | `GEMINI_AGENT_MODEL` |

Select with `--agent-provider`, the `AGENT_PROVIDER` env var, or the dropdown on
the assumptions page. Left unset it resolves to Claude; Gemini is picked
automatically only when `GEMINI_API_KEY` is the sole credential configured, so
adding a Gemini key for PDF extraction never silently reroutes an agent run.

Note `AGENT_PROVIDER` (which model family orchestrates) is a separate question
from `CLAUDE_PROVIDER` (how Claude itself is reached — first-party or Vertex).

There is only one loop. Gemini is adapted onto the Anthropic Messages
request/response shape in `gemini_client.py` rather than given its own loop, so
the tool wiring, parallel-call batching and refusal handling have a single
implementation — and the parity guarantee above holds for both providers.

## Key Design Decisions

- **Single source of truth**: 10-K/10-Q PDFs are the only source for financial data — no third-party data feeds
- **LLM boundary**: The LLM extracts data from PDFs, and may sequence the analysis. It never computes a figure — every number comes from deterministic Python
- **Two-pass extraction**: Pass 1 reads financial tables; Pass 2 analyzes footnotes for non-recurring items, using Pass 1 output as context
- **All financials in millions**, share prices per-share
- **FCFF**: Historical uses CFO-based (`CFO + Interest*(1-t) - CapEx`); projected uses EBIT-based (`EBIT*(1-t) + D&A - CapEx - dNWC`)
- **Market inputs carry provenance**: the risk-free rate is fetched live (10Y Treasury, `^TNX`) with a labelled fallback; the equity risk premium is a versioned constant with an as-of date, shown alongside the result

## Testing

```bash
python tests/run_all.py
```

Four suites, all offline — no API key and no network. They run from committed
extraction fixtures with price data synthesised from a fixed seed, so results
never shift with the market.

## Tech Stack

- **FastAPI** + **Uvicorn** — async web framework
- **Jinja2** — server-side HTML templates
- **Google Gemini API** (default) or **Anthropic Claude API** — PDF financial data extraction; either can also orchestrate the agentic loop
- **yfinance** — historical stock and market price data
- **SciPy / NumPy / Pandas** — numerical computation and data handling
