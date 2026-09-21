"""Valuation routes: assumptions input and DCF results."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import config
from analysis.capm import run_capm
from analysis.dcf import run_dcf
from analysis.normalizer import normalize_financials
from analysis.projector import derive_assumptions, project_fcffs
from analysis.wacc import calculate_wacc
from config import BASE_DIR
from ingestion.claude_extractor import (
    Provider,
    extract_financials,
    extract_multi_year,
    resolve_provider,
)
from ingestion.price_fetcher import fetch_price_data
from models.financial_statements import FinancialStatements
from models.valuation import ProjectionAssumptions

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# In-memory cache: extraction results from assumptions_page are reused in run_valuation
# so the LLM is only called once per upload.
_extraction_cache: dict[str, FinancialStatements] = {}


def _parse_files_param(files_str: str) -> list[tuple[int, str]]:
    """Parse the 'files' query param into [(fiscal_year, path), ...]."""
    result = []
    for entry in files_str.split(","):
        entry = entry.strip()
        if not entry:
            continue
        year_str, _, path = entry.partition(":")
        result.append((int(year_str), path))
    return result


def _extract_from_files(
    filings: list[tuple[int, str]],
    ticker: str,
    company_name: str,
) -> tuple[FinancialStatements, list]:
    """Run extraction for single or multi-file uploads.

    `provider` is passed explicitly on every branch. It used to be omitted, and the
    two public defaults differed, so the number of PDFs a user uploaded decided
    which model read them. One constant, named once, now decides it.
    """
    # Annotated, so the Literal survives the assignment. An unannotated local
    # widens to `str` and mypy can no longer check it against Provider.
    provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER

    if len(filings) == 1:
        _, pdf_path = filings[0]
        return extract_financials(pdf_path, ticker, company_name, provider=provider)

    # For multi-file, filter out entries with year=0 (couldn't guess year)
    valid = [(y, p) for y, p in filings if y > 0]
    if not valid:
        # Fallback: use the first file as a single extraction
        _, pdf_path = filings[0]
        return extract_financials(pdf_path, ticker, company_name, provider=provider)

    return extract_multi_year(valid, ticker, company_name, provider=provider)


@router.get("/assumptions", response_class=HTMLResponse)
async def assumptions_page(
    request: Request,
    ticker: str = "",
    company_name: str = "",
    files: str = "",
    # Legacy single-file param
    file_path: str = "",
):
    """Show assumptions page with defaults derived from historical data."""
    error = None
    defaults = {}

    # Build filings list from either new multi-file or legacy single-file param
    if files:
        filings = _parse_files_param(files)
    elif file_path:
        filings = [(0, file_path)]
    else:
        filings = []

    cache_key = files or file_path

    if filings:
        try:
            financials, non_recurring = _extract_from_files(filings, ticker, company_name)
            financials = normalize_financials(financials, non_recurring)
            _extraction_cache[cache_key] = financials
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
        "files": files or file_path,
        "defaults": defaults,
        "error": error,
    })


@router.post("/valuation", response_class=HTMLResponse)
async def run_valuation(
    request: Request,
    ticker: str = Form(...),
    company_name: str = Form(""),
    files: str = Form(""),
    projection_years: int = Form(5),
    terminal_growth_rate: float = Form(2.5),
    revenue_growth: str = Form(""),  # Comma-separated percentages
    operating_margin: float = Form(0),
    tax_rate: float = Form(0),
    da_pct: float = Form(0),
    capex_pct: float = Form(0),
    nwc_pct: float = Form(0),
    risk_free_rate: float = Form(4.0),
    equity_risk_premium: str = Form(""),
    beta_override: str = Form(""),
    cost_of_debt_override: str = Form(""),
    beta_lookback_years: int = Form(5),
    return_frequency: str = Form("monthly"),
):
    """Execute the full DCF valuation pipeline."""
    try:
        # 1. Use cached normalized financials from assumptions_page (avoids re-calling LLM)
        if files in _extraction_cache:
            financials = _extraction_cache.pop(files)
        else:
            # Fallback: extract + normalize if cache miss
            filings = _parse_files_param(files) if ":" in files else [(0, files)]
            raw_fin, non_recurring = _extract_from_files(filings, ticker, company_name)
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
            equity_risk_premium=float(equity_risk_premium) / 100 if equity_risk_premium.strip() else None,
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

        # Rule 6: which model read the filing, over which transport, on whose
        # credential, is an assumption about every figure on this page. It is read
        # back here rather than carried from the extraction because the extraction
        # may have happened on the earlier /assumptions request and been cached.
        # resolve_provider touches only the environment — no token, no network call.
        #
        # KNOWN LIMITATION (P2b-provider review round 1, finding F3). This is a
        # re-derivation, not a record: it names who WOULD read a filing now, not who
        # read this one. If the environment moved between the extraction and this
        # render — a Foundry variable set or unset — the label disagrees with the
        # event it describes, and rule 4 asks that a figure be traceable to its real
        # inputs. Fixing it means carrying the ProviderResolution alongside the
        # financials in _extraction_cache (`:31`, written at `:102` in
        # assumptions_page, read at `:148-154` here), which is backlog item 5 and
        # outside this unit's Files in scope.
        extraction = resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)

        # starlette 1.6.0 removed the deprecated TemplateResponse(name, context)
        # form; the signature is (request, name, context). Under the old call the
        # context dict bound to `name` and jinja raised "cannot use 'tuple' as a
        # dict key", so this route answered HTTP 500 on every request and the
        # labels below were never seen by a reader.
        return templates.TemplateResponse(request, "valuation_result.html", {
            "ticker": ticker,
            "company_name": company_name,
            "dcf": dcf_result,
            "capm": capm_result,
            "wacc": wacc_result,
            "assumptions": assumptions,
            "current_price": price_data.current_price,
            "extraction": extraction,
        })

    except Exception as e:
        # Same starlette 1.6.0 signature as the success branch above.
        return templates.TemplateResponse(request, "valuation_result.html", {
            "ticker": ticker,
            "company_name": company_name,
            "error": str(e),
            "dcf": None,
            "capm": None,
            "wacc": None,
            "assumptions": None,
            "current_price": 0,
            "extraction": None,
        })
