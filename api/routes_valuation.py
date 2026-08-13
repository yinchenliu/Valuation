"""Valuation routes: assumptions input and DCF results."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import config
import pipeline
from config import BASE_DIR
from models.valuation import ProjectionAssumptions

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def parse_files_param(files_str: str) -> list[tuple[int, str]]:
    """Parse the 'files' form value into [(fiscal_year, path), ...].

    Entries are "year:path". Paths are Windows absolute paths more often than
    not, so the year is split off with a bounded left-hand match rather than a
    bare partition on ':' — otherwise "C:\\filings\\x.pdf" splits at the drive
    letter and int("C") raises.
    """
    result: list[tuple[int, str]] = []
    for entry in files_str.split(","):
        entry = entry.strip()
        if not entry:
            continue
        head, sep, tail = entry.partition(":")
        if sep and head.isdigit():
            result.append((int(head), tail))
        else:
            # No year prefix — a bare path (possibly with a drive letter).
            result.append((0, entry))
    return result


def _pct(value: float | None) -> float | None:
    """Convert a percentage form value to a decimal, preserving an explicit 0.

    `x / 100 if x else None` used to be the idiom here, which made a submitted 0
    indistinguishable from "not supplied" — wrong for nwc_pct in particular,
    where 0% is a legitimate assumption.
    """
    return None if value is None else value / 100


def _opt_float(raw: str) -> float | None:
    raw = (raw or "").strip()
    return float(raw) if raw else None


def _opt_pct(raw: str) -> float | None:
    value = _opt_float(raw)
    return None if value is None else value / 100


@router.get("/assumptions", response_class=HTMLResponse)
async def assumptions_page(
    request: Request,
    ticker: str = "",
    company_name: str = "",
    files: str = "",
    run_id: str = "",
    # Legacy single-file param
    file_path: str = "",
):
    """Extract the filings and show the assumptions form prefilled from history."""
    error = None
    defaults = {}
    run = pipeline.STORE.get(run_id) if run_id else None

    if files:
        filings = parse_files_param(files)
    elif file_path:
        filings = [(0, file_path)]
    else:
        filings = []

    if run is None and filings:
        run = pipeline.ValuationRun(
            ticker=ticker, company_name=company_name, filings=filings
        )
        try:
            pipeline.step_extract(run)
            pipeline.step_normalize(run)
            pipeline.STORE.put(run)
        except Exception as e:  # noqa: BLE001 — surfaced on the page
            error = str(e)
            run = None

    if run is not None and error is None:
        try:
            derived = pipeline.step_derive_assumptions(run)
            defaults = derived.to_dict()
            defaults["revenue_growth_display"] = [f"{g * 100:.1f}" for g in derived.revenue_growth_rates]
            defaults["operating_margin_display"] = f"{derived.operating_margin * 100:.1f}"
            defaults["tax_rate_display"] = f"{derived.tax_rate * 100:.1f}"
            defaults["da_pct_display"] = f"{derived.da_pct_revenue * 100:.1f}"
            defaults["capex_pct_display"] = f"{derived.capex_pct_revenue * 100:.1f}"
            defaults["nwc_pct_display"] = f"{derived.nwc_pct_revenue * 100:.1f}"
        except Exception as e:  # noqa: BLE001
            error = str(e)

    return templates.TemplateResponse(request, "assumptions.html", {
        "ticker": ticker,
        "company_name": company_name,
        "files": files or file_path,
        "run_id": run.run_id if run else "",
        "defaults": defaults,
        "error": error,
        "cfg": config,
        "default_terminal_growth_pct": config.DEFAULT_TERMINAL_GROWTH_RATE * 100,
        "default_projection_years": config.DEFAULT_PROJECTION_YEARS,
        "default_beta_lookback_years": config.DEFAULT_BETA_LOOKBACK_YEARS,
        "default_return_frequency": config.DEFAULT_RETURN_FREQUENCY,
        "agent_provider": _resolved_agent_provider(),
    })


def _resolved_agent_provider() -> str:
    """Which model family the agentic button will use, for pre-selecting the form.

    Credential problems belong on the agentic page, not on the assumptions form,
    so a bad AGENT_PROVIDER value falls back to a sane default here rather than
    breaking a page that has nothing to do with the agent.
    """
    import llm_client

    try:
        return llm_client.resolve_agent_provider()
    except llm_client.ClientConfigError:
        return "claude"


@router.post("/valuation", response_class=HTMLResponse)
async def run_valuation(
    request: Request,
    ticker: str = Form(...),
    company_name: str = Form(""),
    files: str = Form(""),
    run_id: str = Form(""),
    projection_years: int = Form(config.DEFAULT_PROJECTION_YEARS),
    terminal_growth_rate: float = Form(config.DEFAULT_TERMINAL_GROWTH_RATE * 100),
    revenue_growth: str = Form(""),  # Comma-separated percentages
    # These are Optional so a submitted 0 stays distinguishable from "blank".
    operating_margin: float | None = Form(None),
    tax_rate: float | None = Form(None),
    da_pct: float | None = Form(None),
    capex_pct: float | None = Form(None),
    nwc_pct: float | None = Form(None),
    risk_free_rate: str = Form(""),
    equity_risk_premium: str = Form(""),
    beta_override: str = Form(""),
    cost_of_debt_override: str = Form(""),
    beta_lookback_years: int = Form(config.DEFAULT_BETA_LOOKBACK_YEARS),
    return_frequency: str = Form(config.DEFAULT_RETURN_FREQUENCY),
):
    """Execute the full DCF valuation pipeline."""
    run = pipeline.STORE.get(run_id) if run_id else None

    try:
        if run is None:
            filings = parse_files_param(files)
            if not filings:
                raise pipeline.PipelineError(
                    "No filings found for this run. The extraction result may have expired — "
                    "please re-upload."
                )
            run = pipeline.ValuationRun(
                ticker=ticker, company_name=company_name, filings=filings
            )
            pipeline.step_extract(run)
            pipeline.step_normalize(run)
            pipeline.STORE.put(run)

        rev_growth_list = []
        if revenue_growth.strip():
            rev_growth_list = [float(x.strip()) / 100 for x in revenue_growth.split(",") if x.strip()]

        overrides = ProjectionAssumptions(
            projection_years=projection_years,
            terminal_growth_rate=terminal_growth_rate / 100,
            revenue_growth_rates=rev_growth_list,
            operating_margin=_pct(operating_margin),
            tax_rate=_pct(tax_rate),
            da_pct_revenue=_pct(da_pct),
            capex_pct_revenue=_pct(capex_pct),
            nwc_pct_revenue=_pct(nwc_pct),
            # Blank means "fetch the live 10Y Treasury", not "use 4%".
            risk_free_rate=_opt_pct(risk_free_rate),
            equity_risk_premium=_opt_pct(equity_risk_premium),
            beta_override=_opt_float(beta_override),
            cost_of_debt_override=_opt_pct(cost_of_debt_override),
            beta_lookback_years=beta_lookback_years,
            return_frequency=return_frequency,
        )

        pipeline.run_full_pipeline(run, overrides, skip_extract=True)

        return templates.TemplateResponse(request, "valuation_result.html", {
            "ticker": ticker,
            "company_name": company_name,
            "run_id": run.run_id,
            "files": files,
            "dcf": run.dcf,
            "capm": run.capm,
            "wacc": run.wacc,
            "assumptions": run.assumptions,
            "non_recurring": run.non_recurring,
            "raw_financials": run.raw_financials,
            "adjusted_financials": run.adjusted_financials,
            "shares_source": run.shares_source,
            "current_price": run.price_data.current_price if run.price_data else 0,
        })

    except Exception as e:  # noqa: BLE001
        return templates.TemplateResponse(request, "valuation_result.html", {
            "ticker": ticker,
            "company_name": company_name,
            "run_id": run.run_id if run else "",
            "files": files,
            "error": str(e),
            "dcf": None,
            "capm": None,
            "wacc": None,
            "assumptions": None,
            "non_recurring": [],
            "current_price": 0,
        })


@router.post("/valuation/agentic", response_class=HTMLResponse)
async def run_agentic(
    request: Request,
    ticker: str = Form(...),
    company_name: str = Form(""),
    files: str = Form(""),
    run_id: str = Form(""),
    effort: str = Form("high"),
    max_iterations: int = Form(30),
    agent_provider: str = Form(""),
):
    """Let an LLM sequence the valuation instead of running the fixed pipeline.

    `agent_provider` is "claude", "gemini", or blank to resolve from
    `AGENT_PROVIDER` and the configured credentials.

    Extraction still happens up front — it is the slow, expensive, genuinely
    fixed part, so there is nothing for the agent to decide about it. Everything
    after that is the agent's call.
    """
    from agent.loop import run_agentic_valuation
    from agent.transcript import transcript_rows

    run = pipeline.STORE.get(run_id) if run_id else None
    error = None
    result = None

    try:
        if run is None:
            filings = parse_files_param(files)
            if not filings:
                raise pipeline.PipelineError(
                    "No filings found for this run — it may have expired. Please re-upload."
                )
            run = pipeline.ValuationRun(
                ticker=ticker, company_name=company_name, filings=filings
            )
            pipeline.step_extract(run)
            pipeline.STORE.put(run)

        result = run_agentic_valuation(
            run,
            provider=agent_provider or None,
            max_iterations=max_iterations,
            effort=effort,
        )
        if result.error:
            error = result.error
    except Exception as e:  # noqa: BLE001
        error = str(e)

    return templates.TemplateResponse(request, "agent_run.html", {
        "ticker": ticker,
        "company_name": company_name,
        "run_id": run.run_id if run else "",
        "files": files,
        "error": error,
        "result": result,
        "transcript": transcript_rows(run) if run else [],
        "dcf": run.dcf if run else None,
        "capm": run.capm if run else None,
        "wacc": run.wacc if run else None,
        "assumptions": run.assumptions if run else None,
        "current_price": run.price_data.current_price if run and run.price_data else 0,
    })
