"""Valuation routes: assumptions input and DCF results."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from analysis.capm import run_capm
from analysis.dcf import run_dcf
from analysis.normalizer import normalize_financials
from analysis.projector import derive_assumptions, project_fcffs
from analysis.wacc import calculate_wacc
from config import BASE_DIR
from ingestion.claude_extractor import extract_financials
from models.financial_statements import FinancialStatements
from ingestion.price_fetcher import fetch_price_data
from models.valuation import ProjectionAssumptions

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# In-memory cache: extraction results from assumptions_page are reused in run_valuation
# so the LLM is only called once per PDF upload.
# Key: file_path -> (normalized FinancialStatements)
_extraction_cache: dict[str, FinancialStatements] = {}


@router.get("/assumptions", response_class=HTMLResponse)
async def assumptions_page(
    request: Request,
    ticker: str = "",
    company_name: str = "",
    file_path: str = "",
):
    """Show assumptions page with defaults derived from historical data."""
    error = None
    defaults = {}

    if file_path:
        try:
            financials, non_recurring = extract_financials(file_path, ticker, company_name)
            financials = normalize_financials(financials, non_recurring)
            # Cache the normalized financials so run_valuation doesn't re-call the LLM
            _extraction_cache[file_path] = financials
            defaults = derive_assumptions(financials)
            # Format for display
            defaults["revenue_growth_display"] = [f"{g * 100:.1f}" for g in defaults["revenue_growth_rates"]]
            defaults["operating_margin_display"] = f"{defaults['operating_margin'] * 100:.1f}"
            defaults["tax_rate_display"] = f"{defaults['tax_rate'] * 100:.1f}"
            defaults["da_pct_display"] = f"{defaults['da_pct_revenue'] * 100:.1f}"
            defaults["capex_pct_display"] = f"{defaults['capex_pct_revenue'] * 100:.1f}"
            defaults["nwc_pct_display"] = f"{defaults['nwc_pct_revenue'] * 100:.1f}"
        except Exception as e:
            error = str(e)

    return templates.TemplateResponse("assumptions.html", {
        "request": request,
        "ticker": ticker,
        "company_name": company_name,
        "file_path": file_path,
        "defaults": defaults,
        "error": error,
    })


@router.post("/valuation", response_class=HTMLResponse)
async def run_valuation(
    request: Request,
    ticker: str = Form(...),
    company_name: str = Form(""),
    file_path: str = Form(...),
    projection_years: int = Form(5),
    terminal_growth_rate: float = Form(2.5),
    revenue_growth: str = Form(""),  # Comma-separated percentages
    operating_margin: float = Form(0),
    tax_rate: float = Form(0),
    da_pct: float = Form(0),
    capex_pct: float = Form(0),
    nwc_pct: float = Form(0),
    risk_free_rate: float = Form(4.0),
    equity_risk_premium: float = Form(5.5),
    beta_override: str = Form(""),
    cost_of_debt_override: str = Form(""),
    beta_lookback_years: int = Form(5),
    return_frequency: str = Form("monthly"),
):
    """Execute the full DCF valuation pipeline."""
    try:
        # 1. Use cached normalized financials from assumptions_page (avoids re-calling LLM)
        if file_path in _extraction_cache:
            financials = _extraction_cache.pop(file_path)
        else:
            # Fallback: extract + normalize if cache miss (e.g. direct POST)
            raw_fin, non_recurring = extract_financials(file_path, ticker, company_name)
            financials = normalize_financials(raw_fin, non_recurring)

        # 2. Build assumptions (from post-adjustment financials)
        rev_growth_list = []
        if revenue_growth.strip():
            rev_growth_list = [float(x.strip()) / 100 for x in revenue_growth.split(",")]

        overrides = ProjectionAssumptions(
            projection_years=projection_years,
            terminal_growth_rate=terminal_growth_rate / 100,
            revenue_growth_rates=rev_growth_list if rev_growth_list else [],
            operating_margin=operating_margin / 100 if operating_margin else None,
            tax_rate=tax_rate / 100 if tax_rate else None,
            da_pct_revenue=da_pct / 100 if da_pct else None,
            capex_pct_revenue=capex_pct / 100 if capex_pct else None,
            nwc_pct_revenue=nwc_pct / 100 if nwc_pct else None,
            risk_free_rate=risk_free_rate / 100,
            equity_risk_premium=equity_risk_premium / 100,
            beta_override=float(beta_override) if beta_override.strip() else None,
            cost_of_debt_override=float(cost_of_debt_override) / 100 if cost_of_debt_override.strip() else None,
            beta_lookback_years=beta_lookback_years,
            return_frequency=return_frequency,
        )

        assumptions = derive_assumptions(financials, overrides)

        # 3. Fetch price data and run CAPM
        price_data = fetch_price_data(ticker, beta_lookback_years, return_frequency)
        capm_result = run_capm(
            price_data,
            risk_free_rate=overrides.risk_free_rate,
            equity_risk_premium=overrides.equity_risk_premium,
            beta_override=overrides.beta_override,
        )

        # 4. Calculate WACC
        latest_year = financials.latest_year
        latest_is = financials.get_income_statement(latest_year)
        latest_bs = financials.get_balance_sheet(latest_year)

        # Get diluted shares: from financials if available, otherwise from yfinance
        shares = latest_is.diluted_shares_outstanding
        if shares == 0:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            shares = info.get("sharesOutstanding", 0) / 1e6  # Convert to millions
        market_cap = price_data.current_price * shares

        wacc_result = calculate_wacc(
            capm_result=capm_result,
            income_statement=latest_is,
            balance_sheet=latest_bs,
            market_cap=market_cap,
            cost_of_debt_override=overrides.cost_of_debt_override,
            tax_rate_override=assumptions["tax_rate"],
        )

        # 5. Project FCFFs
        projected = project_fcffs(financials, assumptions)

        # 6. Run DCF
        dcf_result = run_dcf(
            projected_fcffs=projected,
            wacc_result=wacc_result,
            financials=financials,
            terminal_growth_rate=assumptions["terminal_growth_rate"],
            current_price=price_data.current_price,
            diluted_shares=shares,
        )

        return templates.TemplateResponse("valuation_result.html", {
            "request": request,
            "ticker": ticker,
            "company_name": company_name,
            "dcf": dcf_result,
            "capm": capm_result,
            "wacc": wacc_result,
            "assumptions": assumptions,
            "current_price": price_data.current_price,
        })

    except Exception as e:
        return templates.TemplateResponse("valuation_result.html", {
            "request": request,
            "ticker": ticker,
            "company_name": company_name,
            "error": str(e),
            "dcf": None,
            "capm": None,
            "wacc": None,
            "assumptions": None,
            "current_price": 0,
        })
