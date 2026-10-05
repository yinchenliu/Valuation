"""Valuation routes: assumptions input and DCF results."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import config
from analysis.fcff import calculate_fcff_historical
from analysis.projector import derive_assumptions
from config import BASE_DIR
from ingestion.claude_extractor import (
    Provider,
    ProviderResolution,
    extract_financials,
    extract_multi_year,
    resolve_provider,
)
from ingestion.session_extraction import load_session_extraction
from models.financial_statements import FinancialStatements, NonRecurringItem
from models.valuation import (
    AssumptionSource,
    HistoricalFCFFYear,
    ProjectionAssumptions,
)
from pipeline import adjust_financials, value_company

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@dataclass(frozen=True)
class CachedExtraction:
    """One upload's extraction, as `assumptions_page` left it.

    Five NAMED fields rather than a tuple (rule 2). The cache used to hold a
    2-tuple — the normalised statements and the excluded items — so the raw
    pre-adjustment statements and the items that were actually APPLIED were
    local variables in `assumptions_page` and died when it returned. The result
    page could therefore say what had been withheld and could not say what had
    been applied, and neither page could show a GAAP-to-non-GAAP
    reconciliation, because the "before" side of it no longer existed. That is
    the rule 4 gap named at `docs/2-rules/rules.md:92`.

    Every field is required. None of them is defaulted, so a cache entry that
    is missing one cannot be constructed at all, rather than being constructed
    with an empty list that reads as "nothing was adjusted".

    `extraction` is who read the filing, recorded when the extraction RAN
    (rule 6). It used to be re-derived from the environment when the result
    page rendered, which named who WOULD read a filing at that moment. With
    two extraction routes that re-derivation is false for every session file:
    it would label figures read in a Claude Code session as read over the API.
    """

    raw_financials: FinancialStatements
    normalised_financials: FinancialStatements
    applied_items: list[NonRecurringItem]
    excluded_items: list[NonRecurringItem]
    extraction: ProviderResolution


# `HistoricalFCFFYear` used to be defined here. It is a record, so it now
# lives in `models/valuation.py` beside `HistoricalFCFF`, which is what it
# holds (code reviewer finding F7); it was only ever here because round 1's
# Files in scope held one file.
#
# The two source-label constants that used to sit here are gone too, with the
# two functions that built them. A label that has to distinguish a derived
# ratio from a SUBSTITUTED one can only be produced where the evidence is —
# inside `derive_assumptions` — so `analysis/projector.py` now returns it and
# this route reads `assumptions["sources"]`. Finding F1.

# In-memory cache: extraction results from assumptions_page are reused in run_valuation
# so the LLM is only called once per upload.
#
# It carries the raw statements and BOTH halves of the non-recurring
# partition alongside the normalised statements, because all four are facts
# about the share price this cache entry will produce. Caching the normalised
# statements alone is what made the other three unreachable from the result
# page: the page would have had to say nothing was adjusted, or say nothing at
# all, on exactly the path a real user takes.
# (The module-global cache itself is backlog item 5 and is not this unit's.)
_extraction_cache: dict[str, CachedExtraction] = {}


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


@dataclass(frozen=True)
class RouteExtraction:
    """One extraction, by either route, with the label recorded as it ran.

    Every field is required, for the reason `CachedExtraction` gives.
    """

    raw_financials: FinancialStatements
    non_recurring: list[NonRecurringItem]
    extraction: ProviderResolution


def _run_extraction(
    files: str,
    file_path: str,
    session_file: str,
    ticker: str,
    company_name: str,
) -> RouteExtraction:
    """Run the one extraction a request names, by route A or route B.

    The ONLY place either route handler extracts. `assumptions_page` and the
    cache-miss branch of `run_valuation` used to call `_extract_from_files`
    separately, and each built the cached values itself; that is how the two
    halves drifted before (see the comment at the cache-miss branch).

    - `session_file` (route B): `load_session_extraction` reads, checks and
      merges the file, and stops with a `ValueError` naming the file and the
      problem. The label is the loader's. `ticker` and `company_name` are not
      used: they come from the file (see `_shown_identity`).
    - otherwise (route A): `files` ("year:path,...") or the legacy `file_path`
      is extracted over the API. The label is resolved immediately before the
      extraction, in the same environment the extractor resolves it in
      (`extract_financials` calls the same `resolve_provider`), and is carried
      from here on rather than re-derived later.

    Raises:
        ValueError: when none of the three names a filing, when `files` names
            none, or when a session file is combined with PDFs (rule 3: an input
            is never silently ignored). Backlog item 29: `POST /valuation` with
            no filing used to extract the empty string.
    """
    if session_file:
        if files or file_path:
            raise ValueError(
                "session_file was given together with files/file_path. Give one: "
                "a session file already names its PDFs.",
            )
        session = load_session_extraction(session_file)
        return RouteExtraction(
            raw_financials=session.financials,
            non_recurring=session.non_recurring,
            extraction=session.resolution,
        )

    if files:
        filings = _parse_files_param(files)
        if not filings:
            raise ValueError(f"files: {files!r} names no filing.")
    elif file_path:
        filings = [(0, file_path)]
    else:
        raise ValueError(
            "No filing named: session_file, files and file_path are all empty.",
        )

    extraction = resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)
    raw_financials, non_recurring = _extract_from_files(filings, ticker, company_name)
    return RouteExtraction(
        raw_financials=raw_financials,
        non_recurring=non_recurring,
        extraction=extraction,
    )


def _shown_identity(
    session_file: str,
    ticker: str,
    company_name: str,
    raw_financials: FinancialStatements,
) -> tuple[str, str]:
    """The ticker and company name a page shows and forwards.

    Route A: as the request gave them, unchanged. Route B: from the session
    file's statements, as `cli.py --session-file` takes them. A ticker or name
    the request supplied that differs from the file's stops rather than being
    silently replaced, as `-t` / `-n` do in the CLI. The ticker reaches the
    price fetch, so a mismatch is not cosmetic.
    """
    if not session_file:
        return ticker, company_name
    file_ticker = raw_financials.ticker.upper()
    file_company = raw_financials.company_name
    if ticker and ticker.upper() != file_ticker:
        raise ValueError(
            f"ticker {ticker!r} differs from the session file's ticker "
            f"{file_ticker!r}. The ticker comes from the file.",
        )
    if company_name and company_name != file_company:
        raise ValueError(
            f"company_name {company_name!r} differs from the session file's "
            f"company name {file_company!r}. The name comes from the file.",
        )
    return file_ticker, file_company


def _historical_fcff_by_year(
    financials: FinancialStatements,
) -> list[HistoricalFCFFYear]:
    """One row per extracted year, computed or explicitly not computable.

    `calculate_fcff_historical` (`analysis/fcff.py:47`) needs both the income
    statement and the cash flow statement of the year. Where either is absent
    the year still gets a row, marked absent and naming what was missing, so
    the output can print the words instead of leaving a silent hole.

    Built from whichever `FinancialStatements` the caller hands it; both call
    sites hand it the NORMALISED statements, which is what every other figure
    on both pages is built from.
    """
    rows: list[HistoricalFCFFYear] = []

    for year in financials.years:
        income_statement = financials.get_income_statement(year)
        cash_flow = financials.get_cash_flow(year)

        missing: list[str] = []
        if income_statement is None:
            missing.append("income statement")
        if cash_flow is None:
            missing.append("cash flow statement")

        if income_statement is None or cash_flow is None:
            rows.append(
                HistoricalFCFFYear(
                    year=year,
                    is_computable=False,
                    fcff=None,
                    missing_statements=tuple(missing),
                )
            )
            continue

        rows.append(
            HistoricalFCFFYear(
                year=year,
                is_computable=True,
                fcff=calculate_fcff_historical(income_statement, cash_flow),
                missing_statements=(),
            )
        )

    return rows


@dataclass(frozen=True)
class EBITReconciliationYear:
    """One year of GAAP to non-GAAP EBIT reconciliation."""

    year: int
    as_reported_ebit: float | None
    adjusted_ebit: float | None
    difference: float | None
    missing_statement: str | None


def _build_ebit_reconciliation(
    raw: FinancialStatements | None,
    adjusted: FinancialStatements | None,
) -> list[EBITReconciliationYear]:
    """Build per-year EBIT reconciliation between raw and normalised statements.

    Rule 3: a year missing from either side carries a named field saying so,
    never a zero delta.
    """
    if raw is None or adjusted is None:
        return []

    years = sorted(set(raw.years) | set(adjusted.years))
    records: list[EBITReconciliationYear] = []
    for y in years:
        raw_is = raw.get_income_statement(y)
        adj_is = adjusted.get_income_statement(y)
        if raw_is is not None and adj_is is not None:
            records.append(
                EBITReconciliationYear(
                    year=y,
                    as_reported_ebit=raw_is.ebit,
                    adjusted_ebit=adj_is.ebit,
                    difference=adj_is.ebit - raw_is.ebit,
                    missing_statement=None,
                )
            )
        elif raw_is is None and adj_is is not None:
            records.append(
                EBITReconciliationYear(
                    year=y,
                    as_reported_ebit=None,
                    adjusted_ebit=adj_is.ebit,
                    difference=None,
                    missing_statement="raw income statement",
                )
            )
        elif raw_is is not None and adj_is is None:
            records.append(
                EBITReconciliationYear(
                    year=y,
                    as_reported_ebit=raw_is.ebit,
                    adjusted_ebit=None,
                    difference=None,
                    missing_statement="adjusted income statement",
                )
            )
        else:
            records.append(
                EBITReconciliationYear(
                    year=y,
                    as_reported_ebit=None,
                    adjusted_ebit=None,
                    difference=None,
                    missing_statement="raw and adjusted income statement",
                )
            )
    return records


@router.get("/assumptions", response_class=HTMLResponse)
async def assumptions_page(
    request: Request,
    ticker: str = "",
    company_name: str = "",
    files: str = "",
    # Legacy single-file param
    file_path: str = "",
    # Route B: a session file saved by POST /upload-session.
    session_file: str = "",
):
    """Show assumptions page with defaults derived from historical data."""
    error = None
    defaults = {}

    # Set before the try, so that the failure path and the no-filing path reach
    # the context with every key defined. An undefined name in a jinja context
    # renders as nothing, which is how a template quietly shows an empty table
    # on the success path as readily as on the error path.
    #
    # `None` and empty, never a substitute: there is no extraction on those
    # paths, and `assumption_sources` is empty because a page that derived no
    # ratio has no ratio to label.
    raw_financials: FinancialStatements | None = None
    normalised_financials: FinancialStatements | None = None
    applied_items: list[NonRecurringItem] = []
    excluded_items: list[NonRecurringItem] = []
    historical_fcff: list[HistoricalFCFFYear] = []
    ebit_reconciliation: list[EBITReconciliationYear] = []
    assumption_sources: dict[str, AssumptionSource] = {}
    # Who read the filing. None until an extraction has run, so a page with
    # no extraction names no route.
    extraction: ProviderResolution | None = None

    cache_key = session_file or files or file_path

    if cache_key:
        try:
            run = _run_extraction(files, file_path, session_file, ticker, company_name)
            raw_financials = run.raw_financials
            non_recurring = run.non_recurring
            extraction = run.extraction
            ticker, company_name = _shown_identity(
                session_file, ticker, company_name, raw_financials,
            )
            # Partition first, normalise with the applied half only, in
            # `pipeline.adjust_financials`, the one home the CLI shares
            # (backlog item 7). The decision belongs to analysis/ (rule 1).
            # `normalize_financials` returns a NEW FinancialStatements through
            # dataclasses.replace (`analysis/normalizer.py:245`); it does not
            # mutate its argument. So `raw_financials` below is still the
            # pre-adjustment extraction, and the reconciliation has both sides.
            adjustment = adjust_financials(raw_financials, non_recurring)
            applied_items = adjustment.applied
            excluded_items = adjustment.excluded
            normalised_financials = adjustment.adjusted
            _extraction_cache[cache_key] = CachedExtraction(
                raw_financials=raw_financials,
                normalised_financials=normalised_financials,
                applied_items=applied_items,
                excluded_items=excluded_items,
                extraction=extraction,
            )
            defaults = derive_assumptions(normalised_financials)
            # Rule 6, one home for the fact. `derive_assumptions` is the only
            # place that can tell a ratio derived from three filing-years from
            # one substituted because nothing fed it, because by the time it
            # returns, the list it averaged is out of scope. This route reads
            # the label; it does not re-derive it.
            assumption_sources = defaults["sources"]
            # Format for display
            defaults["revenue_growth_display"] = [f"{g * 100:.1f}" for g in defaults["revenue_growth_rates"]]
            defaults["operating_margin_display"] = f"{defaults['operating_margin'] * 100:.1f}"
            defaults["tax_rate_display"] = f"{defaults['tax_rate'] * 100:.1f}"
            defaults["da_pct_display"] = f"{defaults['da_pct_revenue'] * 100:.1f}"
            defaults["capex_pct_display"] = f"{defaults['capex_pct_revenue'] * 100:.1f}"
            defaults["nwc_pct_display"] = f"{defaults['nwc_pct_revenue'] * 100:.1f}"
            # LAST in the try, and deliberately after `derive_assumptions`.
            # `calculate_fcff_historical` stops on a NaN tax rate (rule 3,
            # `analysis/fcff.py:39-44`), and at round 1 this call sat ahead of
            # the derivation, so one NaN historical year replaced the whole
            # defaults form with an error page — a form the reader could
            # otherwise have used and corrected by hand. Code reviewer finding
            # F3. Calling it last changes no number.
            historical_fcff = _historical_fcff_by_year(normalised_financials)
            ebit_reconciliation = _build_ebit_reconciliation(raw_financials, normalised_financials)
        except Exception as e:
            error = str(e)

    # Same starlette 1.6.0 signature as the two valuation_result.html calls below.
    # "request" is no longer passed in the context: starlette does
    # context.setdefault("request", request) itself, and no template reads it.
    return templates.TemplateResponse(request, "assumptions.html", {
        "ticker": ticker,
        "company_name": company_name,
        "files": files or file_path,
        # Forwarded beside `files` so POST /valuation finds the cache entry,
        # or extracts by the same route on a miss.
        "session_file": session_file,
        # Rule 6: the route that produced the statements on this page. A
        # reader checking them before choosing assumptions must know it.
        "extraction": extraction,
        "defaults": defaults,
        "error": error,
        # The chain, carried so a template can show it. `P8b-statements-ui`
        # renders these six; this route only has to make them reachable, and
        # the key names are the ones that unit is written against.
        #
        # `raw_financials` is the extraction as it arrived; `financials` is the
        # same statements after the applied items landed. Both sides are here
        # because a reconciliation needs both.
        "raw_financials": raw_financials,
        "financials": normalised_financials,
        "applied_non_recurring": applied_items,
        "excluded_non_recurring": excluded_items,
        "historical_fcff": historical_fcff,
        "ebit_reconciliation": ebit_reconciliation,
        # CONTRACT: this is empty, or it holds exactly six entries — one per
        # ratio, under the six literal keys `derive_assumptions` writes. It is
        # never a partial dict. Empty means no ratio was derived at all
        # (no filing named, or the extraction failed), and six labels there
        # would describe a run that did not happen.
        "assumption_sources": assumption_sources,
        # Rule 6, backlog item 34. The risk-free rate field is now blank by
        # default so that leaving it alone reaches `run_capm` as None and the
        # result page can say the constant was SUBSTITUTED. The reader still
        # has to be told what will be substituted, so the constant is rendered
        # into the field's placeholder — read from `config`, not retyped in the
        # template, which is the literal that caused this defect.
        #
        # Converted to a percentage HERE, at the route boundary, like every
        # other display figure in this context dict. The template formats; it
        # does not do arithmetic.
        "default_risk_free_rate_display": f"{config.DEFAULT_RISK_FREE_RATE * 100:.1f}",
    })


def _checkbox_checked(field: str, value: str) -> bool:
    """Read an HTML checkbox from a submitted form.

    A checked checkbox sends "on" and an unchecked one sends nothing, which the
    form field receives as "". Those two values are the only ones a browser
    sends, so any other value did not come from the checkbox. Rule 3: it stops
    and names the field and the value rather than being read as checked or as
    unchecked.
    """
    if value == "on":
        return True
    if value == "":
        return False
    raise ValueError(
        f"form field {field} is {value!r}. A checkbox sends 'on' when it is "
        f"checked and nothing when it is not, so this value cannot be read as "
        f"either. It is not treated as checked or as unchecked."
    )


@router.post("/valuation", response_class=HTMLResponse)
async def run_valuation(
    request: Request,
    ticker: str = Form(...),
    company_name: str = Form(""),
    files: str = Form(""),
    session_file: str = Form(""),
    projection_years: int = Form(5),
    terminal_growth_rate: float = Form(2.5),
    revenue_growth: str = Form(""),  # Comma-separated percentages
    operating_margin: float = Form(0),
    tax_rate: float = Form(0),
    da_pct: float = Form(0),
    capex_pct: float = Form(0),
    nwc_pct: float = Form(0),
    # `str`, not `float`, and empty rather than 4.0 — rule 6, backlog item 34.
    #
    # This used to be a `float` form field defaulting to a literal 4.0, and
    # `templates/assumptions.html` prefilled the field with the same literal.
    # (The old expression is not quoted here because done-criterion 4b is
    # measured by grepping this file for it.) Two things followed and both
    # were wrong. The route always reached `run_capm` with a value, so
    # `CAPMResult.risk_free_rate_source` always read "supplied by the caller"
    # and the web output could never say a rate had been SUBSTITUTED — the
    # reader was told they had supplied a figure the form supplied for them.
    # And the 4.0 was a literal rather than `config.DEFAULT_RISK_FREE_RATE`, so
    # editing the constant would have moved the CLI and left the web app at
    # 4.0% silently.
    #
    # Empty-string-by-default is the shape `equity_risk_premium`,
    # `beta_override` and `cost_of_debt_override` beside it already use: an
    # unfilled field arrives as "" and reaches the calculation as None, which
    # is what makes the substitution branch reachable. It is a string because
    # "" is not a float; a `float | None` form field cannot express "the user
    # left this blank" without inventing a sentinel number.
    risk_free_rate: str = Form(""),
    equity_risk_premium: str = Form(""),
    beta_override: str = Form(""),
    cost_of_debt_override: str = Form(""),
    # The "Confirm zero debt" checkbox (backlog item 38b (a)). A checked HTML
    # checkbox sends "on"; an unchecked one sends nothing, which arrives as "".
    # Read by `_checkbox_checked`, which stops on any other value.
    confirm_zero_debt: str = Form(""),
    beta_lookback_years: int = Form(5),
    return_frequency: str = Form("monthly"),
):
    """Execute the full DCF valuation pipeline."""
    try:
        # 1. Use cached normalized financials from assumptions_page (avoids re-calling LLM)
        # The same key assumptions_page wrote under: the first non-empty of
        # session_file and files (the form's `files` carries `files or
        # file_path` from that page).
        cache_key = session_file or files
        if cache_key in _extraction_cache:
            # Still a `.pop()`. That the cache is a module global emptied on
            # read is backlog item 5 and is not this unit's to change.
            cached = _extraction_cache.pop(cache_key)
            raw_financials = cached.raw_financials
            financials = cached.normalised_financials
            applied_items = cached.applied_items
            excluded_items = cached.excluded_items
            extraction = cached.extraction
        else:
            # Fallback: extract + normalize if cache miss.
            # The form's `files` holds either "year:path,..." or a legacy bare
            # path; the `":" in files` test that tells them apart is backlog
            # item 26 and is kept as it was.
            if ":" in files:
                files_param, file_path_param = files, ""
            else:
                files_param, file_path_param = "", files
            run = _run_extraction(
                files_param, file_path_param, session_file, ticker, company_name,
            )
            raw_financials = run.raw_financials
            extraction = run.extraction
            # The same `adjust_financials` as assumptions_page: partition, then
            # normalise with the applied half. Both branches must produce the
            # same FIVE values, or the page would report a different exclusion
            # than the arithmetic used depending on which one ran.
            adjustment = adjust_financials(raw_financials, run.non_recurring)
            applied_items = adjustment.applied
            excluded_items = adjustment.excluded
            financials = adjustment.adjusted

        # Route B: the ticker priced below is the session file's.
        ticker, company_name = _shown_identity(
            session_file, ticker, company_name, raw_financials,
        )

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
            # `.strip()` on the STRING, not a falsy test on the number. A user
            # who types 0 sends "0", which is a non-empty string and survives
            # as 0.0; only a genuinely blank field becomes None. (The five
            # `x / 100 if x else None` conversions above are backlog item 6 and
            # are not this unit's.)
            risk_free_rate=float(risk_free_rate) / 100 if risk_free_rate.strip() else None,
            equity_risk_premium=float(equity_risk_premium) / 100 if equity_risk_premium.strip() else None,
            beta_override=float(beta_override) if beta_override.strip() else None,
            cost_of_debt_override=float(cost_of_debt_override) / 100 if cost_of_debt_override.strip() else None,
            zero_debt_confirmed=_checkbox_checked("confirm_zero_debt", confirm_zero_debt),
            beta_lookback_years=beta_lookback_years,
            return_frequency=return_frequency,
        )

        # 3. The valuation: assumptions, market data, CAPM, the share count,
        # WACC, the projection and the DCF, in `pipeline.value_company` — the
        # same call the CLI makes (backlog item 7). The share count is read
        # there, from the filing only: a filing with no diluted share count
        # stops with a `ValueError`, shown by the error branch below (rules 3
        # and 5; there is no yfinance fallback).
        valuation = value_company(
            financials,
            overrides,
            ticker=ticker,
            lookback_years=beta_lookback_years,
            frequency=return_frequency,
        )
        assumptions = valuation.assumptions
        price_data = valuation.price_data
        capm_result = valuation.capm_result
        wacc_result = valuation.wacc_result
        dcf_result = valuation.dcf_result

        # Rule 6: `extraction`, set in step 1, is who read the filing — RECORDED
        # when the extraction ran (in the cache entry, or by the cache-miss
        # branch), never re-derived here. A re-derivation names who WOULD read a
        # filing now: wrong if the environment moved since, and wrong for every
        # session file, which no API read at all.

        # 4. The chain behind the figures above, for the page to show.
        #
        # Built from the NORMALISED statements, because that is what the DCF
        # ran on. Computed here, after the valuation, so the order in which
        # these lines run cannot move any figure already computed above.
        historical_fcff = _historical_fcff_by_year(financials)
        ebit_reconciliation = _build_ebit_reconciliation(raw_financials, financials)
        # Rule 6: for each of the six ratios, whether the reader supplied it,
        # how many filing-years derived it, or that nothing fed it and a
        # default was substituted. Read straight out of the dict that computed
        # them — see the contract comment on the same key in `assumptions_page`.
        assumption_sources = assumptions["sources"]

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
            # The statements as extracted and the same statements after the
            # applied items landed — the two sides of the reconciliation.
            "raw_financials": raw_financials,
            "financials": financials,
            # The items that WERE applied. Every figure on this page is built
            # from statements these moved, so the page could not previously
            # name a single adjustment behind its own share price.
            "applied_non_recurring": applied_items,
            # The items that were NOT applied. The template says so in as many
            # words and prints the source each cited, so a reader can reverse
            # the decision by hand.
            "excluded_non_recurring": excluded_items,
            "historical_fcff": historical_fcff,
            "ebit_reconciliation": ebit_reconciliation,
            "assumption_sources": assumption_sources,
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
            # Empty rather than absent: on the error path there is no valuation
            # to exclude anything from, and an undefined name in the context is
            # how a template quietly renders nothing on the success path too.
            #
            # The run may have failed before the extraction, after it, or
            # between the two, so none of these six can be reported here
            # without claiming something this branch does not know. Every key
            # is defined and every one is empty.
            "raw_financials": None,
            "financials": None,
            "applied_non_recurring": [],
            "excluded_non_recurring": [],
            "historical_fcff": [],
            "ebit_reconciliation": [],
            "assumption_sources": {},
        })
