# Valuation Platform

Web-based DCF valuation platform. Parses 10-K/10-Q PDF filings via LLM, fetches market data via yfinance, and performs discounted cash flow valuation.

## Quick Reference

The repo ships a venv at `.venv/`. Create it with any Python 3.11+ interpreter:
`python -m venv .venv`, then:

```bash
# Install dependencies
.venv/Scripts/python.exe -m pip install -r requirements.txt

# Run the app
.venv/Scripts/python.exe -m uvicorn app:app --reload

# Deterministic CLI valuation
.venv/Scripts/python.exe cli.py 10K_filings -t ABBV --cache-dir ./cache

# Agentic CLI valuation (the LLM sequences the tools; needs ANTHROPIC_API_KEY)
.venv/Scripts/python.exe cli.py 10K_filings -t ABBV --cache-dir ./cache --agentic

# Same loop, orchestrated by Gemini instead (needs GEMINI_API_KEY)
.venv/Scripts/python.exe cli.py 10K_filings -t ABBV --cache-dir ./cache --agentic \
    --agent-provider gemini

# Full offline test suite — no API calls, no network
.venv/Scripts/python.exe tests/run_all.py
```

## Architecture

```
Upload 10-K PDF → LLM Extraction → FinancialStatements + NonRecurringItems (dataclass contracts)
                                              ↓
                                    pipeline.py steps (deterministic math)
                                              ↓
                    ┌─────────────────────────┴─────────────────────────┐
        run_full_pipeline()                                   agent/ tool-calling loop
        (fixed 8-step order)                    (Claude or Gemini picks the order; same steps)
                    └─────────────────────────┬─────────────────────────┘
                                              ↓
                              FastAPI routes → Jinja2 templates → Browser
```

**Both paths call the same functions and must produce identical numbers.** The
agent chooses *which* step runs and *when*; it never computes a figure itself.
`tests/test_agent_tools.py` asserts the two paths agree.

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

For extraction the LLM is a **read-only layer** — it reports what the filing says
and does not compute anything.

Separately, an LLM may **orchestrate** the valuation (see `agent/` below), but the
same constraint holds there: it decides which deterministic tool to call, never
what a number should be.

**Multi-PDF smart routing** (`extract_multi_year()`): When multiple 10-K PDFs are provided, the oldest filing extracts all years (including comparatives), while newer filings extract only their primary fiscal year. B/S is extracted only from the most recent filing. This avoids duplicate extraction across overlapping comparative years.

### Deterministic Code (everything else)

All financial logic after extraction is handled by deterministic, auditable Python code so that **every number can be traced back to its formula and inputs**:
- **GAAP → Non-GAAP adjustments** (`normalizer.py`) — applies LLM-identified non-recurring items to raw financials
- **Ratio assumptions** (`projector.py`) — derives historical averages (margins, growth rates, CapEx/D&A/NWC as % of revenue)
- **Projections** (`projector.py`) — projects future financials from assumptions
- **Valuation** (`capm.py`, `wacc.py`, `fcff.py`, `dcf.py`) — CAPM beta regression, WACC, FCFF, DCF with terminal value

### Pipeline flow in code

`pipeline.py` is the single orchestrator, driven by the web routes, the CLI, and
the agent alike. It holds a `ValuationRun` (the filings plus every artifact) and
exposes each stage as an **independently re-runnable step**:

| Step | Wraps |
|------|-------|
| `step_extract` | `claude_extractor.extract_financials` / `extract_multi_year` |
| `step_normalize` | `normalizer.normalize_financials` → adjusted (non-GAAP) financials |
| `step_derive_assumptions` | `projector.derive_assumptions` → `DerivedAssumptions` |
| `step_fetch_market_data` | `price_fetcher.fetch_price_data` + share-count resolution |
| `step_capm` | `capm.run_capm` → beta, cost of equity |
| `step_wacc` | `wacc.calculate_wacc` |
| `step_project` | `projector.project_fcffs` |
| `step_dcf` | `dcf.run_dcf` → enterprise value, equity value, implied price |

`run_full_pipeline()` calls them in the conventional order. The agent calls them
in whatever order the filing warrants.

Steps are re-runnable **because** the agent needs to revisit them — e.g. lower
terminal growth and re-run `step_dcf` after a `wacc <= g` failure. Keep them
free of hidden state.

### Agentic orchestration (`agent/`)

- `tools.py` — each pipeline step as a model-callable tool. Tools take scalars
  plus the bound run, and return **compact JSON summaries**, never dataclasses.
  Artifacts stay server-side on the `ValuationRun`; that is what keeps
  `PriceData`'s numpy payload out of the conversation and each turn affordable.
- `loop.py` — a manual `while stop_reason == "tool_use"` loop (not the SDK tool
  runner) so the tool/system prefix stays byte-identical across turns and gets
  cached. **Tool registration order must stay stable** — tools render at position
  0 of the prompt, so reordering `TOOL_SPECS` invalidates the whole cached prefix.
- `transcript.py` — the audit trail: every tool call, its inputs, its result.

Tools return `{"error": ..., "recoverable": true}` rather than raising, so the
model can adjust an input and retry instead of the run dying.

**Either Claude or Gemini can drive the loop, and there is only one loop.**
`gemini_client.py` adapts Gemini onto the Anthropic Messages request/response
shape, so `loop.py` never branches on provider. Forking per provider would put
the tool wiring, the parallel-result batching and the refusal handling in two
places, and would weaken the parity guarantee that both orchestration paths
produce identical numbers. Anything added to the loop must work on both.

Three translation details in `gemini_client.py` are easy to break silently:
Gemini 3's thought signatures must be echoed back (response blocks retain their
original `types.Part` for exactly this), function responses are keyed by tool
*name* rather than by `tool_use_id`, and Anthropic's `["number", "null"]` schema
unions become a separate `nullable` flag. `tests/test_agent_loop.py` covers all
three against real `google.genai.types` objects.

## Key Conventions

- **Single source of truth:** 10-K/10-Q PDFs are the only source for financial data. No Capital IQ or other third-party data feeds.
- **Units:** All financial data is in millions. Share prices are per-share.
- **FCFF approach:** Historical uses CFO-based (`CFO + Interest*(1-t) - CapEx`). Projected uses EBIT-based (`EBIT*(1-t) + D&A - CapEx - dNWC`).
- **Dataclass-driven:** `models/` defines the data contract. `FinancialStatements` is the central type that flows through the entire pipeline.
- **Form values are percentages:** The web UI sends values like `4.0` (meaning 4%), which routes convert to decimals (`0.04`) before passing to analysis functions. The CLI takes decimals directly.
- **Blank ≠ zero:** On the assumptions form, a blank field means "derive from history" and a submitted `0` means "use zero". Convert with `_pct()`, never `x/100 if x else None` — that idiom conflates the two and is wrong for `nwc_pct`.
- **Net debt:** Includes cash + short-term investments as liquid assets (standard IB equity bridge convention).
- **`config.py` is the single source of truth for defaults.** Do not restate a default as a literal in a dataclass field, a `Form(...)`, an argparse default, or a template — five constants were dead that way, so editing `config.DEFAULT_TERMINAL_GROWTH_RATE` changed nothing.
- **Market inputs carry provenance.** The risk-free rate is fetched live (`^TNX`) with an explicit labelled fallback; the ERP is a versioned constant with an as-of date, *not* the realised trailing market return (which is procyclical and can go negative, taking the WACC with it). See `analysis/market_data.py` and `config.ASSUMPTION_PROVENANCE`.
- **Layering:** `analysis/` must not import `ingestion/`. Shared contracts like `PriceData` live in `models/`. `pipeline.py` sits at the root precisely because it spans both.

## Project Structure

| Path | Purpose |
|------|---------|
| `pipeline.py` | The orchestrator: `ValuationRun`, `RunStore`, and one re-runnable function per step |
| `config.py` | All default assumptions + `ASSUMPTION_PROVENANCE` (source, as-of date, rationale) |
| `llm_client.py` | Provider resolution (`AGENT_PROVIDER`, `CLAUDE_PROVIDER`) and client construction |
| `gemini_client.py` | Gemini wearing the Anthropic Messages interface, so the agent loop stays provider-agnostic |
| `models/` | Dataclasses: `FinancialStatements`, `NonRecurringItem`, `DCFResult`, `DerivedAssumptions`, `PriceData` |
| `ingestion/` | LLM-powered 10-K PDF extraction (`claude_extractor.py`), yfinance price fetcher |
| `analysis/` | Deterministic valuation math: normalizer, CAPM, WACC, FCFF, projector, DCF, `market_data.py`, `rates.py` |
| `agent/` | Agentic orchestration: `tools.py`, `loop.py`, `transcript.py` |
| `api/` | FastAPI routes: upload, assumptions form, `/valuation`, `/valuation/agentic` |
| `templates/` | Jinja2 HTML: upload → assumptions → results / agent run |
| `static/` | CSS styling (`style.css`), charts placeholder |
| `tests/` | `run_all.py` runs the four offline suites; `test_e2e_*.py` are manual scripts that hit the real API |

## Testing

`tests/run_all.py` runs everything below offline — no API key, no network. Run it
on every change.

| Suite | Guards |
|-------|--------|
| `test_regression_golden.py` | Full pipeline over the committed pickles vs a JSON snapshot. Any numeric drift fails. Re-baseline deliberately with `--update`. |
| `test_agent_tools.py` | **Agentic and deterministic paths produce identical numbers**; tool failures are structured and recoverable. |
| `test_agent_loop.py` | Loop mechanics against stub clients: stable cacheable prefix, parallel results in one message, thinking blocks echoed, refusal handled, iteration cap — for **both** the Claude and Gemini backends, plus the Gemini schema/message translation. |
| `test_web_smoke.py` | Routes render, run store is non-destructive, explicit `0` is honoured. |

Price data is synthesised from a fixed seed so market movement never affects a
test result.
