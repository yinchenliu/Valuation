"""Valuation pipeline: one orchestrator, driven by the CLI, the web routes, and the agent.

This module used to exist twice — once inline in `api/routes_valuation.py` and
once inline in `cli.py` — as two straight-line copies of the same eight steps.

Everything here is deliberately structured as **independent, re-runnable steps
over a shared run object**, rather than one function that does all eight in
order. That is what lets the agent in `agent/` call them in whatever order the
filing actually calls for, retry a single step with different inputs, and inspect
what a previous step produced — none of which the straight-line version allowed.

The deterministic path is still available as `run_full_pipeline()`, which just
calls the steps in the conventional order.

It sits at the repo root rather than under `analysis/` because it spans both
ingestion and analysis; putting an ingestion-importing module inside `analysis/`
would reintroduce the layering inversion that moving `PriceData` just removed.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import config
from analysis.capm import run_capm
from analysis.dcf import run_dcf
from analysis.fcff import calculate_fcff_historical
from analysis.market_data import fetch_equity_risk_premium, fetch_risk_free_rate
from analysis.normalizer import normalize_financials
from analysis.projector import derive_assumptions, project_fcffs
from analysis.wacc import calculate_wacc
from ingestion.claude_extractor import extract_financials, extract_multi_year
from ingestion.price_fetcher import fetch_price_data
from models.financial_statements import FinancialStatements, NonRecurringItem
from models.market import PriceData
from models.valuation import (
    CAPMResult,
    DCFResult,
    DerivedAssumptions,
    ProjectedFCFF,
    ProjectionAssumptions,
    WACCResult,
)


class PipelineError(RuntimeError):
    """A step could not complete. Carries an actionable message for the caller.

    The agent surfaces these back to the model as recoverable tool errors rather
    than letting them abort the run, so it can adjust an input and try again.
    """


@dataclass
class ValuationRun:
    """All state for one valuation, from uploaded filings through to the DCF.

    Steps read what they need off the run and write their result back onto it, so
    a step can be re-run without re-running the ones before it.
    """

    ticker: str
    company_name: str = ""
    filings: list[tuple[int, str]] = field(default_factory=list)
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)

    # Artifacts, in pipeline order.
    raw_financials: FinancialStatements | None = None
    non_recurring: list[NonRecurringItem] = field(default_factory=list)
    adjusted_financials: FinancialStatements | None = None
    assumptions: DerivedAssumptions | None = None
    price_data: PriceData | None = None
    capm: CAPMResult | None = None
    wacc: WACCResult | None = None
    projected: list[ProjectedFCFF] = field(default_factory=list)
    dcf: DCFResult | None = None

    # Resolved along the way.
    diluted_shares: float = 0.0
    shares_source: str = ""

    # Ordered record of what ran. The agent appends tool calls here too.
    transcript: list[dict] = field(default_factory=list)

    def log(self, step: str, detail: str, **extra: Any) -> None:
        self.transcript.append(
            {"step": step, "detail": detail, "at": time.time(), **extra}
        )

    @property
    def financials(self) -> FinancialStatements | None:
        """The statements downstream steps should use: adjusted if normalised."""
        return self.adjusted_financials or self.raw_financials

    def require(self, *names: str) -> None:
        """Assert prerequisites, naming the step that produces each missing one."""
        produced_by = {
            "raw_financials": "extract_financials",
            "adjusted_financials": "normalize_financials",
            "assumptions": "derive_assumptions",
            "price_data": "fetch_market_data",
            "capm": "run_capm",
            "wacc": "calculate_wacc",
            "projected": "project_fcffs",
            "dcf": "run_dcf",
        }
        for name in names:
            if not getattr(self, name, None):
                raise PipelineError(
                    f"'{name}' is not available yet — call {produced_by.get(name, name)} first."
                )


class RunStore:
    """In-process store of ValuationRuns, keyed by run_id.

    Replaces the old module-global `_extraction_cache`, which was keyed by the raw
    `files` query string and popped on read — so re-submitting the assumptions
    form silently re-ran the whole LLM extraction. Reads here are non-destructive.
    """

    def __init__(self, ttl_seconds: int = 3600, max_runs: int = 64) -> None:
        self._runs: dict[str, ValuationRun] = {}
        self._ttl = ttl_seconds
        self._max = max_runs

    def _evict(self) -> None:
        now = time.time()
        for run_id in [r for r, run in self._runs.items() if now - run.created_at > self._ttl]:
            del self._runs[run_id]
        # Bound memory even if everything is within TTL.
        while len(self._runs) > self._max:
            oldest = min(self._runs, key=lambda r: self._runs[r].created_at)
            del self._runs[oldest]

    def put(self, run: ValuationRun) -> ValuationRun:
        self._evict()
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> ValuationRun | None:
        self._evict()
        return self._runs.get(run_id)

    def __contains__(self, run_id: object) -> bool:
        return run_id in self._runs

    def __len__(self) -> int:
        return len(self._runs)


# Shared by the web routes and the agent so a run started in one is visible in the other.
STORE = RunStore()


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_extract(
    run: ValuationRun,
    provider: str = "gemini",
    model: str | None = None,
    debug: bool = False,
) -> FinancialStatements:
    """Extract financial statements and non-recurring items from the filings.

    Routes single vs multi-PDF. `provider` is always passed explicitly: the two
    call sites used to default differently (single-file to Gemini, multi-file to
    Claude), so a multi-file upload quietly demanded a different API key.
    """
    if not run.filings:
        raise PipelineError("No filings attached to this run — nothing to extract.")

    dated = [(year, path) for year, path in run.filings if year > 0]

    if len(run.filings) == 1 or not dated:
        _, pdf_path = run.filings[0]
        financials, non_recurring = extract_financials(
            pdf_path, run.ticker, run.company_name,
            provider=provider, model=model, debug=debug,
        )
    else:
        financials, non_recurring = extract_multi_year(
            dated, run.ticker, run.company_name,
            provider=provider, model=model, debug=debug,
        )

    run.raw_financials = financials
    run.non_recurring = non_recurring
    run.log(
        "extract",
        f"Extracted {len(financials.years)} year(s), {len(non_recurring)} non-recurring item(s)",
        years=list(financials.years), provider=provider,
    )
    return financials


def step_normalize(run: ValuationRun) -> FinancialStatements:
    """Apply non-recurring adjustments (GAAP -> non-GAAP)."""
    run.require("raw_financials")
    adjusted = normalize_financials(run.raw_financials, run.non_recurring)
    run.adjusted_financials = adjusted
    run.log("normalize", f"Applied {len(run.non_recurring)} adjustment(s)")
    return adjusted


def step_derive_assumptions(
    run: ValuationRun,
    overrides: ProjectionAssumptions | None = None,
) -> DerivedAssumptions:
    """Resolve projection assumptions from history, honouring any overrides."""
    run.require("raw_financials")
    assumptions = derive_assumptions(run.financials, overrides)
    run.assumptions = assumptions
    run.log(
        "derive_assumptions",
        f"Derived assumptions; {len(assumptions.overridden)} overridden",
        overridden=list(assumptions.overridden),
    )
    return assumptions


def step_fetch_market_data(
    run: ValuationRun,
    lookback_years: int = config.DEFAULT_BETA_LOOKBACK_YEARS,
    frequency: str = config.DEFAULT_RETURN_FREQUENCY,
) -> PriceData:
    """Fetch price history for the beta regression, and resolve share count."""
    try:
        price_data = fetch_price_data(run.ticker, lookback_years, frequency)
    except Exception as exc:  # noqa: BLE001
        raise PipelineError(
            f"Could not fetch price data for '{run.ticker}': {exc}. "
            "Check the ticker symbol is valid and network access is available."
        ) from exc

    run.price_data = price_data
    resolve_diluted_shares(run)
    run.log(
        "fetch_market_data",
        f"{len(price_data.stock_returns)} return periods; price ${price_data.current_price:,.2f}",
        current_price=price_data.current_price,
    )
    return price_data


def resolve_diluted_shares(run: ValuationRun) -> float:
    """Diluted share count, from the filing if reported, else from yfinance.

    This fallback was duplicated across the route, the CLI, and seven test
    scripts; it lives here now.
    """
    run.require("raw_financials")
    financials = run.financials
    latest_is = financials.get_income_statement(financials.latest_year)

    shares = latest_is.diluted_shares_outstanding if latest_is else 0.0
    source = "filing (diluted shares outstanding)"

    if not shares:
        try:
            import yfinance as yf

            info = yf.Ticker(run.ticker).info
            shares = (info.get("sharesOutstanding") or 0) / 1e6  # to millions
            source = "yfinance sharesOutstanding"
        except Exception:  # noqa: BLE001
            shares = 0.0
            source = "unavailable"

    if not shares:
        raise PipelineError(
            f"Could not determine diluted shares outstanding for '{run.ticker}'. "
            "The filing did not report it and the yfinance lookup failed; supply it manually."
        )

    run.diluted_shares = shares
    run.shares_source = source
    return shares


def step_capm(
    run: ValuationRun,
    risk_free_rate: float | None = None,
    equity_risk_premium: float | str | None = None,
    beta_override: float | None = None,
) -> CAPMResult:
    """Estimate beta and cost of equity."""
    run.require("price_data")
    capm_result = run_capm(
        run.price_data,
        risk_free_rate=risk_free_rate,
        equity_risk_premium=equity_risk_premium,
        beta_override=beta_override,
    )
    run.capm = capm_result
    run.log(
        "run_capm",
        f"beta {capm_result.beta:.3f}, cost of equity {capm_result.cost_of_equity:.2%}",
        beta=capm_result.beta, cost_of_equity=capm_result.cost_of_equity,
    )
    return capm_result


def step_wacc(
    run: ValuationRun,
    cost_of_debt_override: float | None = None,
    tax_rate_override: float | None = None,
) -> WACCResult:
    """Weight cost of equity and cost of debt into a discount rate."""
    run.require("capm", "price_data")
    financials = run.financials
    latest_year = financials.latest_year
    latest_is = financials.get_income_statement(latest_year)
    latest_bs = financials.get_balance_sheet(latest_year)

    if latest_bs is None:
        raise PipelineError(
            f"No balance sheet available for FY{latest_year}; WACC needs debt figures. "
            "Re-extract including the balance sheet."
        )

    if tax_rate_override is None and run.assumptions is not None:
        tax_rate_override = run.assumptions.tax_rate

    market_cap = run.price_data.current_price * run.diluted_shares
    wacc_result = calculate_wacc(
        capm_result=run.capm,
        income_statement=latest_is,
        balance_sheet=latest_bs,
        market_cap=market_cap,
        cost_of_debt_override=cost_of_debt_override,
        tax_rate_override=tax_rate_override,
    )
    run.wacc = wacc_result
    run.log(
        "calculate_wacc",
        f"WACC {wacc_result.wacc:.2%} (E/V {wacc_result.equity_weight:.1%})",
        wacc=wacc_result.wacc,
    )
    return wacc_result


def step_project(run: ValuationRun) -> list[ProjectedFCFF]:
    """Project forward FCFFs from the resolved assumptions."""
    run.require("raw_financials", "assumptions")
    projected = project_fcffs(run.financials, run.assumptions)
    run.projected = projected
    run.log(
        "project_fcffs",
        f"Projected {len(projected)} year(s), FY{projected[0].year}-FY{projected[-1].year}"
        if projected else "Projected 0 years",
    )
    return projected


def step_dcf(run: ValuationRun) -> DCFResult:
    """Discount the projected FCFFs and bridge to an implied share price."""
    run.require("projected", "wacc", "assumptions", "price_data")
    try:
        dcf_result = run_dcf(
            projected_fcffs=run.projected,
            wacc_result=run.wacc,
            financials=run.financials,
            terminal_growth_rate=run.assumptions.terminal_growth_rate,
            current_price=run.price_data.current_price,
            diluted_shares=run.diluted_shares,
        )
    except ValueError as exc:
        # Most often WACC <= terminal growth, which makes the perpetuity
        # meaningless. Recoverable: lower terminal growth or revisit the discount
        # rate, then call this step again.
        raise PipelineError(
            f"{exc} Lower the terminal growth rate below the WACC "
            f"({run.wacc.wacc:.2%}), or revisit the cost of equity inputs."
        ) from exc

    run.dcf = dcf_result
    run.log(
        "run_dcf",
        f"Implied ${dcf_result.implied_share_price:,.2f} vs ${dcf_result.current_price:,.2f} "
        f"({dcf_result.upside_downside:+.1f}%)",
        implied_share_price=dcf_result.implied_share_price,
        upside_downside=dcf_result.upside_downside,
    )
    return dcf_result


def historical_fcffs(run: ValuationRun) -> list:
    """Historical CFO-based FCFF per year. Display/diagnostics only."""
    run.require("raw_financials")
    financials = run.financials
    out = []
    for year in financials.years:
        inc = financials.get_income_statement(year)
        cfs = financials.get_cash_flow(year)
        if inc and cfs:
            out.append(calculate_fcff_historical(inc, cfs))
    return out


# ---------------------------------------------------------------------------
# Deterministic driver
# ---------------------------------------------------------------------------

def run_full_pipeline(
    run: ValuationRun,
    overrides: ProjectionAssumptions | None = None,
    provider: str = "gemini",
    model: str | None = None,
    skip_extract: bool = False,
    debug: bool = False,
) -> ValuationRun:
    """Run the conventional eight-step sequence.

    This is the non-agentic path, kept as the default so the deterministic
    behaviour stays available and directly comparable against the agent's.
    """
    ov = overrides or ProjectionAssumptions()

    if not skip_extract:
        step_extract(run, provider=provider, model=model, debug=debug)
    step_normalize(run)
    step_derive_assumptions(run, ov)
    step_fetch_market_data(run, ov.beta_lookback_years, ov.return_frequency)
    step_capm(
        run,
        risk_free_rate=ov.risk_free_rate,
        equity_risk_premium=ov.equity_risk_premium,
        beta_override=ov.beta_override,
    )
    step_wacc(run, cost_of_debt_override=ov.cost_of_debt_override)
    step_project(run)
    step_dcf(run)
    return run
