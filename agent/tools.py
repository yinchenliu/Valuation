"""Tool definitions exposed to the orchestrating model.

Every tool is a thin wrapper over a step in `pipeline.py`. Two rules hold
throughout, and together they are what keep the agentic path auditable:

1. **Tools compute nothing.** Each one calls an existing deterministic function
   and stores the result on the run. The model chooses *which* tool runs and
   *when*; it never supplies a figure that lands in the output.

2. **Artifacts stay server-side.** A tool takes a `run_id` plus scalars, and
   returns a compact JSON summary — never a dataclass, a matrix, or a full
   statement. That is what makes `PriceData`'s numpy payload a non-issue, and it
   keeps each loop turn small enough to be affordable.

Failures come back as `{"error": ...}` rather than raising, so the model can fix
an input and retry instead of the whole run dying.
"""

from __future__ import annotations

import functools
import json
from typing import Any, Callable

import pipeline
from models.valuation import ProjectionAssumptions

# The run every tool call operates on. Bound by the loop before it starts, so the
# model does not have to thread a run_id through each call (and cannot get it
# wrong). Tools still take an optional run_id for symmetry with the store.
_active_run: pipeline.ValuationRun | None = None

# Populated by @tool below. Order is insertion order and therefore stable, which
# matters: tools render at the very front of the prompt, so reshuffling this list
# between turns would invalidate the whole cached prefix.
TOOL_SPECS: list[dict] = []
TOOL_IMPLS: dict[str, Callable[..., dict]] = {}


def bind_run(run: pipeline.ValuationRun) -> None:
    global _active_run
    _active_run = run


def active_run() -> pipeline.ValuationRun:
    if _active_run is None:
        raise pipeline.PipelineError("No valuation run is bound to the tool layer.")
    return _active_run


def tool(name: str, description: str, properties: dict, required: list[str] | None = None):
    """Register a function as a model-callable tool.

    Wraps the implementation so any exception becomes a structured error result
    the model can act on, and records the call on the run's transcript.
    """

    def decorator(fn: Callable[..., dict]) -> Callable[..., dict]:
        TOOL_SPECS.append({
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
            "strict": True,
        })

        @functools.wraps(fn)
        def wrapper(**kwargs: Any) -> dict:
            kwargs.pop("run_id", None)  # the run is bound, not passed
            run = _active_run
            try:
                result = fn(**kwargs)
                ok = True
            except pipeline.PipelineError as exc:
                result = {"error": str(exc), "recoverable": True}
                ok = False
            except Exception as exc:  # noqa: BLE001
                result = {"error": f"{type(exc).__name__}: {exc}", "recoverable": True}
                ok = False

            if run is not None:
                run.transcript.append({
                    "step": name,
                    "kind": "tool_call",
                    "inputs": kwargs,
                    "output": result,
                    "ok": ok,
                })
            return result

        TOOL_IMPLS[name] = wrapper
        return wrapper

    return decorator


def call(name: str, arguments: dict) -> str:
    """Execute a tool by name and return its JSON result for a tool_result block."""
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return json.dumps({"error": f"Unknown tool '{name}'.", "recoverable": False})
    return json.dumps(impl(**(arguments or {})), default=str)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool(
    name="get_extraction_summary",
    description=(
        "Summarise what was extracted from the filings: fiscal years available, "
        "revenue and EBIT per year, whether a balance sheet is present, and the "
        "non-recurring items found. Call this first to see what you are working with."
    ),
    properties={},
)
def get_extraction_summary() -> dict:
    run = active_run()
    run.require("raw_financials")
    fin = run.raw_financials

    years = []
    for y in fin.years:
        inc = fin.get_income_statement(y)
        cfs = fin.get_cash_flow(y)
        years.append({
            "year": y,
            "revenue": round(inc.revenue, 1),
            "ebit": round(inc.ebit, 1),
            "net_income": round(inc.net_income, 1),
            "effective_tax_rate": round(inc.effective_tax_rate, 4),
            "has_cash_flow": cfs is not None,
        })

    latest_bs = fin.get_balance_sheet(fin.latest_year)
    return {
        "ticker": fin.ticker,
        "company_name": fin.company_name,
        "years": years,
        "balance_sheet_year": latest_bs.year if latest_bs else None,
        "total_debt": round(latest_bs.total_debt, 1) if latest_bs else None,
        "net_debt": round(latest_bs.net_debt, 1) if latest_bs else None,
        "non_recurring_items": [
            {
                "year": i.year,
                "description": i.description,
                "amount": i.amount,
                "line_item": i.line_item,
                "direction": i.direction,
                "category": i.category,
            }
            for i in run.non_recurring
        ],
        "normalized": run.adjusted_financials is not None,
    }


@tool(
    name="validate_arithmetic",
    description=(
        "Check the extracted income statements reconcile: gross profit, operating "
        "income and net income must each follow from their components within 0.5%. "
        "Returns the list of discrepancies. Use this to decide whether the "
        "extraction is trustworthy before valuing anything."
    ),
    properties={},
)
def validate_arithmetic() -> dict:
    from ingestion.claude_extractor import _validate_extracted_data

    run = active_run()
    run.require("raw_financials")

    llm_years = []
    for y in run.raw_financials.years:
        inc = run.raw_financials.get_income_statement(y)
        llm_years.append({
            "year": y,
            "revenue": inc.revenue,
            "cost_of_revenue": inc.cost_of_revenue,
            "gross_profit": inc.gross_profit,
            "sga": inc.sga,
            "rd_expense": inc.rd_expense,
            "other_operating_expense": inc.other_operating_expense + inc.depreciation_amortization,
            "operating_income": inc.ebit,
            "interest_expense": inc.interest_expense,
            "interest_income": inc.interest_income,
            "other_non_operating": inc.other_non_operating,
            "tax_expense": inc.tax_expense,
            "net_income": inc.net_income,
        })

    errors = _validate_extracted_data(llm_years)
    return {
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "note": (
            "Extraction reconciles." if not errors else
            "Discrepancies found. These come from the filing's own extracted figures; "
            "they do not block valuation but should be reported as a caveat."
        ),
    }


@tool(
    name="normalize_financials",
    description=(
        "Apply the identified non-recurring items to the income statements, "
        "producing adjusted (non-GAAP) figures. Returns the per-line deltas so you "
        "can see exactly what moved. Downstream steps use the adjusted statements."
    ),
    properties={},
)
def normalize_financials_tool() -> dict:
    run = active_run()
    adjusted = pipeline.step_normalize(run)

    deltas = []
    for y in adjusted.years:
        raw_is = run.raw_financials.get_income_statement(y)
        adj_is = adjusted.get_income_statement(y)
        if adj_is.non_recurring_items:
            deltas.append({
                "year": y,
                "changes": {k: round(v, 1) for k, v in adj_is.non_recurring_items.items()},
                "ebit_before": round(raw_is.ebit, 1),
                "ebit_after": round(adj_is.ebit, 1),
            })

    return {
        "adjustments_applied": len(run.non_recurring),
        "years_affected": [d["year"] for d in deltas],
        "deltas": deltas,
    }


@tool(
    name="derive_assumptions",
    description=(
        "Resolve the projection assumptions. Anything you leave null is derived "
        "from the company's own history; anything you set is used as given and "
        "flagged as an override. Rates are decimals (0.08 = 8%)."
    ),
    properties={
        "projection_years": {"type": ["integer", "null"], "description": "Forecast horizon in years."},
        "terminal_growth_rate": {"type": ["number", "null"], "description": "Perpetuity growth, decimal. Must be below the WACC."},
        "revenue_growth_rates": {
            "type": ["array", "null"],
            "items": {"type": "number"},
            "description": "Per-year revenue growth, decimals. Null derives a CAGR from history.",
        },
        "operating_margin": {"type": ["number", "null"], "description": "EBIT margin, decimal."},
        "tax_rate": {"type": ["number", "null"], "description": "Effective tax rate, decimal."},
        "da_pct_revenue": {"type": ["number", "null"], "description": "D&A as a share of revenue, decimal."},
        "capex_pct_revenue": {"type": ["number", "null"], "description": "CapEx as a share of revenue, decimal."},
        "nwc_pct_revenue": {"type": ["number", "null"], "description": "Change in NWC as a share of revenue, decimal."},
    },
    required=[
        "projection_years", "terminal_growth_rate", "revenue_growth_rates",
        "operating_margin", "tax_rate", "da_pct_revenue", "capex_pct_revenue",
        "nwc_pct_revenue",
    ],
)
def derive_assumptions_tool(
    projection_years=None,
    terminal_growth_rate=None,
    revenue_growth_rates=None,
    operating_margin=None,
    tax_rate=None,
    da_pct_revenue=None,
    capex_pct_revenue=None,
    nwc_pct_revenue=None,
) -> dict:
    import config

    run = active_run()
    overrides = ProjectionAssumptions(
        projection_years=projection_years or config.DEFAULT_PROJECTION_YEARS,
        terminal_growth_rate=(
            terminal_growth_rate if terminal_growth_rate is not None
            else config.DEFAULT_TERMINAL_GROWTH_RATE
        ),
        revenue_growth_rates=list(revenue_growth_rates or []),
        operating_margin=operating_margin,
        tax_rate=tax_rate,
        da_pct_revenue=da_pct_revenue,
        capex_pct_revenue=capex_pct_revenue,
        nwc_pct_revenue=nwc_pct_revenue,
    )
    derived = pipeline.step_derive_assumptions(run, overrides)
    out = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in derived.to_dict().items()}
    out["revenue_growth_rates"] = [round(g, 6) for g in derived.revenue_growth_rates]
    out["overridden"] = derived.overridden
    out["derived_from_history"] = [
        k for k in derived.to_dict() if k not in derived.overridden
    ]
    return out


@tool(
    name="fetch_market_data",
    description=(
        "Fetch the share price history needed for the beta regression, resolve the "
        "diluted share count, and report the current risk-free rate and equity risk "
        "premium with their sources. Required before run_capm."
    ),
    properties={
        "lookback_years": {"type": ["integer", "null"], "description": "Years of return history for the beta regression."},
        "frequency": {"type": ["string", "null"], "enum": ["monthly", "daily", None], "description": "Return frequency."},
    },
    required=["lookback_years", "frequency"],
)
def fetch_market_data_tool(lookback_years=None, frequency=None) -> dict:
    import config
    from analysis.market_data import fetch_equity_risk_premium, fetch_risk_free_rate

    run = active_run()
    price_data = pipeline.step_fetch_market_data(
        run,
        lookback_years or config.DEFAULT_BETA_LOOKBACK_YEARS,
        frequency or config.DEFAULT_RETURN_FREQUENCY,
    )
    rf = fetch_risk_free_rate()
    erp = fetch_equity_risk_premium()

    return {
        "ticker": run.ticker,
        "current_price": round(price_data.current_price, 2),
        "return_periods": int(len(price_data.stock_returns)),
        "periods_per_year": price_data.periods_per_year,
        "diluted_shares_millions": round(run.diluted_shares, 2),
        "diluted_shares_source": run.shares_source,
        "risk_free_rate": {
            "value": round(rf.value, 6), "source": rf.source,
            "as_of": rf.as_of.isoformat(), "is_fallback": rf.is_fallback,
        },
        "equity_risk_premium": {
            "value": round(erp.value, 6), "source": erp.source,
            "as_of": erp.as_of.isoformat(),
        },
    }


@tool(
    name="run_capm",
    description=(
        "Regress the stock's returns on the market's to estimate beta, then compute "
        "the cost of equity as Rf + beta * ERP. Leave the rates null to use the "
        "fetched/configured values. Check r_squared: a low value means beta is "
        "poorly identified and a sector beta override may be more defensible."
    ),
    properties={
        "risk_free_rate": {"type": ["number", "null"], "description": "Decimal. Null uses the live 10Y Treasury."},
        "equity_risk_premium": {"type": ["number", "null"], "description": "Decimal. Null uses the configured forward ERP."},
        "beta_override": {"type": ["number", "null"], "description": "Use this beta instead of regressing. Justify it in your summary."},
    },
    required=["risk_free_rate", "equity_risk_premium", "beta_override"],
)
def run_capm_tool(risk_free_rate=None, equity_risk_premium=None, beta_override=None) -> dict:
    run = active_run()
    capm = pipeline.step_capm(
        run,
        risk_free_rate=risk_free_rate,
        equity_risk_premium=equity_risk_premium,
        beta_override=beta_override,
    )
    return {
        "beta": round(capm.beta, 4),
        "r_squared": round(capm.r_squared, 4),
        "std_error": round(capm.std_error, 4),
        "risk_free_rate": round(capm.risk_free_rate, 6),
        "equity_risk_premium": round(capm.equity_risk_premium, 6),
        "cost_of_equity": round(capm.cost_of_equity, 6),
        "beta_was_overridden": beta_override is not None,
    }


@tool(
    name="calculate_wacc",
    description=(
        "Weight the cost of equity and after-tax cost of debt by market values to "
        "get the discount rate. Cost of debt is derived from interest expense over "
        "total debt unless overridden."
    ),
    properties={
        "cost_of_debt_override": {"type": ["number", "null"], "description": "Pre-tax cost of debt, decimal."},
        "tax_rate_override": {"type": ["number", "null"], "description": "Decimal. Null uses the derived assumption."},
    },
    required=["cost_of_debt_override", "tax_rate_override"],
)
def calculate_wacc_tool(cost_of_debt_override=None, tax_rate_override=None) -> dict:
    run = active_run()
    wacc = pipeline.step_wacc(
        run,
        cost_of_debt_override=cost_of_debt_override,
        tax_rate_override=tax_rate_override,
    )
    return {
        "wacc": round(wacc.wacc, 6),
        "cost_of_equity": round(wacc.cost_of_equity, 6),
        "cost_of_debt_pretax": round(wacc.cost_of_debt, 6),
        "tax_rate": round(wacc.tax_rate, 6),
        "equity_weight": round(wacc.equity_weight, 4),
        "debt_weight": round(wacc.debt_weight, 4),
    }


@tool(
    name="project_fcffs",
    description=(
        "Project free cash flow to the firm for each forecast year from the resolved "
        "assumptions: FCFF = EBIT*(1-t) + D&A - CapEx - change in NWC."
    ),
    properties={},
)
def project_fcffs_tool() -> dict:
    run = active_run()
    projected = pipeline.step_project(run)
    return {
        "years": [
            {
                "year": p.year,
                "revenue": round(p.revenue, 1),
                "ebit": round(p.ebit, 1),
                "nopat": round(p.nopat, 1),
                "fcff": round(p.fcff, 1),
            }
            for p in projected
        ]
    }


@tool(
    name="run_dcf",
    description=(
        "Discount the projected FCFFs at the WACC, add the discounted terminal "
        "value, and bridge enterprise value to an implied share price. Fails if the "
        "terminal growth rate is not below the WACC — if that happens, lower "
        "terminal growth via derive_assumptions and try again."
    ),
    properties={},
)
def run_dcf_tool() -> dict:
    run = active_run()
    dcf = pipeline.step_dcf(run)
    return {
        "pv_fcffs": round(dcf.pv_fcffs, 1),
        "terminal_value": round(dcf.terminal_value, 1),
        "pv_terminal_value": round(dcf.pv_terminal_value, 1),
        "terminal_value_pct_of_ev": round(
            dcf.pv_terminal_value / dcf.enterprise_value * 100, 1
        ) if dcf.enterprise_value else None,
        "enterprise_value": round(dcf.enterprise_value, 1),
        "net_debt": round(dcf.net_debt, 1),
        "equity_value": round(dcf.equity_value, 1),
        "diluted_shares_millions": round(dcf.diluted_shares, 2),
        "implied_share_price": round(dcf.implied_share_price, 2),
        "current_price": round(dcf.current_price, 2),
        "upside_downside_pct": round(dcf.upside_downside, 1),
    }


@tool(
    name="get_historical_fcff",
    description=(
        "Historical CFO-based FCFF per year (CFO + after-tax interest - CapEx). "
        "Useful as a sanity check that the projected FCFFs are in a plausible range "
        "relative to what the company has actually generated."
    ),
    properties={},
)
def get_historical_fcff() -> dict:
    run = active_run()
    return {
        "years": [
            {
                "year": h.year,
                "revenue": round(h.revenue, 1),
                "cfo": round(h.cfo, 1),
                "capex": round(h.capital_expenditures, 1),
                "fcff": round(h.fcff, 1),
                "fcff_margin": round(h.fcff_margin, 4),
            }
            for h in pipeline.historical_fcffs(run)
        ]
    }
