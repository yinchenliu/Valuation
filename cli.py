"""Local CLI for DCF valuation — runs the full pipeline with detailed output.

Usage:
    # Single 10-K (all years auto-discovered)
    python cli.py path/to/10K.pdf -t GOOGL -n "Alphabet Inc."

    # Multi-PDF (year-prefixed)
    python cli.py 2023:10K_2023.pdf 2024:10K_2024.pdf 2025:10K_2025.pdf \\
        -t LLY -n "Eli Lilly" -p gemini --cache-dir ./cache

    # Rerun from cache (skips LLM extraction)
    python cli.py 2023:10K_2023.pdf 2024:10K_2024.pdf 2025:10K_2025.pdf \\
        -t LLY -p gemini --cache-dir ./cache

    # With overrides
    python cli.py 10K.pdf -t AAPL --terminal-growth 0.03 --beta 1.1
"""

from __future__ import annotations

import argparse
import pickle
import re
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from analysis.capm import run_capm
from analysis.dcf import run_dcf
from analysis.fcff import calculate_fcff_historical
from analysis.normalizer import normalize_financials
from analysis.projector import derive_assumptions, project_fcffs
from analysis.wacc import calculate_wacc
from ingestion.claude_extractor import extract_financials, extract_multi_year
from ingestion.price_fetcher import fetch_price_data
from models.financial_statements import FinancialStatements, NonRecurringItem
from models.valuation import ProjectionAssumptions

W = 70  # output width
TOTAL_STEPS = 10
_t0 = 0.0  # set in main()


def _step(n: int, label: str) -> None:
    """Print a progress banner with step number and elapsed time."""
    elapsed = time.time() - _t0
    m, s = divmod(int(elapsed), 60)
    ts = f"{m}:{s:02d}" if m else f"{s}s"
    print(f"\n>>> [{n}/{TOTAL_STEPS}] {label}  ({ts} elapsed)")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Helpers: argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run a full DCF valuation from 10-K PDF(s).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    p.add_argument("pdfs", nargs="+",
                    help="PDF path(s). Use YEAR:PATH for multi-file (e.g. 2023:10K.pdf)")
    p.add_argument("-t", "--ticker", required=True, help="Stock ticker")
    p.add_argument("-n", "--company-name", default="", help="Company name")

    # Extraction
    g = p.add_argument_group("extraction")
    g.add_argument("-p", "--provider", default="gemini", choices=["claude", "gemini"])
    g.add_argument("-m", "--model", default=None, help="Override LLM model ID")
    g.add_argument("--cache-dir", default=None, help="Directory for pickle cache")
    g.add_argument("--no-cache", action="store_true", help="Force re-extraction")

    # Valuation overrides (all decimals)
    g = p.add_argument_group("valuation overrides (decimals)")
    g.add_argument("--projection-years", type=int, default=5)
    g.add_argument("--terminal-growth", type=float, default=None)
    g.add_argument("--revenue-growth", default=None,
                    help="Comma-separated per-year rates (e.g. 0.08,0.07,0.06)")
    g.add_argument("--operating-margin", type=float, default=None)
    g.add_argument("--tax-rate", type=float, default=None)
    g.add_argument("--capex-pct", type=float, default=None)
    g.add_argument("--da-pct", type=float, default=None)
    g.add_argument("--nwc-pct", type=float, default=None)
    g.add_argument("--risk-free-rate", type=float, default=None)
    g.add_argument("--equity-risk-premium", type=float, default=None)
    g.add_argument("--beta", type=float, default=None)
    g.add_argument("--cost-of-debt", type=float, default=None)
    g.add_argument("--lookback-years", type=int, default=5)
    g.add_argument("--frequency", default="monthly", choices=["daily", "monthly"])

    return p.parse_args()


def parse_pdf_args(pdf_strings: list[str]) -> list[tuple[int, str]]:
    """Parse 'YEAR:path' or bare 'path' into [(year, path), ...].

    A bare path (no year prefix) returns [(0, path)] — year=0 signals
    'extract all years automatically'.
    """
    filings: list[tuple[int, str]] = []
    for s in pdf_strings:
        m = re.match(r"^(\d{4}):(.+)$", s)
        if m:
            filings.append((int(m.group(1)), m.group(2)))
        else:
            filings.append((0, s))
    return filings


def build_overrides(args: argparse.Namespace) -> ProjectionAssumptions:
    rev_rates = []
    if args.revenue_growth:
        rev_rates = [float(x.strip()) for x in args.revenue_growth.split(",")]
    return ProjectionAssumptions(
        projection_years=args.projection_years,
        terminal_growth_rate=args.terminal_growth if args.terminal_growth is not None else 0.025,
        revenue_growth_rates=rev_rates,
        operating_margin=args.operating_margin,
        tax_rate=args.tax_rate,
        capex_pct_revenue=args.capex_pct,
        da_pct_revenue=args.da_pct,
        nwc_pct_revenue=args.nwc_pct,
        risk_free_rate=args.risk_free_rate,
        equity_risk_premium=args.equity_risk_premium if args.equity_risk_premium is not None else 0.055,
        cost_of_debt_override=args.cost_of_debt,
        beta_override=args.beta,
        beta_lookback_years=args.lookback_years,
        return_frequency=args.frequency,
    )


# ---------------------------------------------------------------------------
# Helpers: cache
# ---------------------------------------------------------------------------

def _cache_path(args: argparse.Namespace) -> Path | None:
    if not args.cache_dir:
        return None
    d = Path(args.cache_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d / f".cache_{args.ticker.lower()}_extraction.pkl"


def _load_cache(path: Path) -> tuple[FinancialStatements, list[NonRecurringItem]]:
    with open(path, "rb") as f:
        return pickle.load(f)


def _save_cache(
    path: Path,
    financials: FinancialStatements,
    non_recurring: list[NonRecurringItem],
) -> None:
    with open(path, "wb") as f:
        pickle.dump((financials, non_recurring), f)


# ---------------------------------------------------------------------------
# Helpers: printing
# ---------------------------------------------------------------------------

def _section(title: str) -> None:
    print("\n" + "=" * W)
    print(title)
    print("=" * W)


def _fmt(v: float, w: int = 10) -> str:
    """Right-aligned number with commas."""
    return f"{v:>{w},.0f}"


def _pct(v: float, w: int = 7) -> str:
    """Right-aligned percentage."""
    return f"{v * 100:>{w}.1f}%"


# ---------------------------------------------------------------------------
# Print: Extracted Financial Statements (Pass 1)
# ---------------------------------------------------------------------------

def print_extracted_financials(financials: FinancialStatements) -> None:
    years = financials.years
    if not years:
        print("  No financial data extracted.")
        return

    col = 10  # column width

    # --- Income Statement ---
    _section("EXTRACTED FINANCIAL STATEMENTS — INCOME STATEMENT (GAAP, $M)")
    label_col = 18
    header = " " * label_col + "".join(f"{y:>{col}}" for y in years)
    print(header)
    print(" " * label_col + "-" * (col * len(years)))

    rows: list[tuple[str, ...]] = [
        ("Revenue",        *[_fmt(financials.get_income_statement(y).revenue, col) for y in years]),
        ("COGS",           *[_fmt(financials.get_income_statement(y).cost_of_revenue, col) for y in years]),
        ("Gross Profit",   *[_fmt(financials.get_income_statement(y).gross_profit, col) for y in years]),
        ("  Margin",       *[_pct(financials.get_income_statement(y).gross_margin, col) for y in years]),
        ("SG&A",           *[_fmt(financials.get_income_statement(y).sga, col) for y in years]),
        ("R&D",            *[_fmt(financials.get_income_statement(y).rd_expense, col) for y in years]),
        ("D&A",            *[_fmt(financials.get_income_statement(y).depreciation_amortization, col) for y in years]),
        ("Other OpEx",     *[_fmt(financials.get_income_statement(y).other_operating_expense, col) for y in years]),
        ("EBIT",           *[_fmt(financials.get_income_statement(y).ebit, col) for y in years]),
        ("  Margin",       *[_pct(financials.get_income_statement(y).operating_margin, col) for y in years]),
        ("Interest Exp",   *[_fmt(financials.get_income_statement(y).interest_expense, col) for y in years]),
        ("Other Non-Op",   *[_fmt(financials.get_income_statement(y).other_non_operating, col) for y in years]),
        ("EBT",            *[_fmt(financials.get_income_statement(y).ebt, col) for y in years]),
        ("Tax Expense",    *[_fmt(financials.get_income_statement(y).tax_expense, col) for y in years]),
        ("Net Income",     *[_fmt(financials.get_income_statement(y).net_income, col) for y in years]),
        ("  Margin",       *[_pct(financials.get_income_statement(y).net_income / financials.get_income_statement(y).revenue if financials.get_income_statement(y).revenue else 0, col) for y in years]),
        ("  Tax Rate",     *[_pct(financials.get_income_statement(y).effective_tax_rate, col) for y in years]),
        ("Dil. Shares",    *[_fmt(financials.get_income_statement(y).diluted_shares_outstanding, col) for y in years]),
        ("EPS",            *[f"{financials.get_income_statement(y).eps:>{col}.2f}" for y in years]),
    ]
    for row in rows:
        print(f"{row[0]:<{label_col}}" + "".join(row[1:]))

    # --- Cash Flow Statement ---
    _section("EXTRACTED FINANCIAL STATEMENTS — CASH FLOW ($M)")
    print(header)
    print(" " * label_col + "-" * (col * len(years)))

    cf_rows: list[tuple[str, ...]] = [
        ("Net Income",  *[_fmt(financials.get_cash_flow(y).net_income, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("D&A",         *[_fmt(financials.get_cash_flow(y).depreciation_amortization, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("SBC",         *[_fmt(financials.get_cash_flow(y).stock_based_compensation, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("Chg in WC",   *[_fmt(financials.get_cash_flow(y).change_in_working_capital, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("Other Ops",   *[_fmt(financials.get_cash_flow(y).other_operating_activities, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("CFO",         *[_fmt(financials.get_cash_flow(y).cash_from_operations, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("CapEx",       *[_fmt(financials.get_cash_flow(y).capital_expenditures, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("Acquisitions",*[_fmt(financials.get_cash_flow(y).acquisitions, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("Other Inv",   *[_fmt(financials.get_cash_flow(y).other_investing_activities, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("CFI",         *[_fmt(financials.get_cash_flow(y).cash_from_investing, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("Debt Issued",  *[_fmt(financials.get_cash_flow(y).debt_issued, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("Debt Repaid",  *[_fmt(financials.get_cash_flow(y).debt_repaid, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("Shares Issued",*[_fmt(financials.get_cash_flow(y).shares_issued, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("Buybacks",     *[_fmt(financials.get_cash_flow(y).shares_repurchased, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("Dividends",    *[_fmt(financials.get_cash_flow(y).dividends_paid, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("Other Fin",    *[_fmt(financials.get_cash_flow(y).other_financing_activities, col) if financials.get_cash_flow(y) else " " * col for y in years]),
        ("CFF",          *[_fmt(financials.get_cash_flow(y).cash_from_financing, col) if financials.get_cash_flow(y) else " " * col for y in years]),
    ]
    for row in cf_rows:
        print(f"{row[0]:<{label_col}}" + "".join(row[1:]))

    # --- Balance Sheet (latest year only) ---
    latest = financials.latest_year
    bs = financials.get_balance_sheet(latest)
    _section(f"EXTRACTED BALANCE SHEET — FY{latest} ($M)")
    if bs is None:
        print("  No balance sheet extracted.")
        return

    bw = 14  # value column width
    lw = 22  # label column width
    gap = "    "

    assets_rows = [
        ("Cash",            bs.cash_and_equivalents),
        ("ST Investments",  bs.short_term_investments),
        ("A/R",             bs.accounts_receivable),
        ("Inventory",       bs.inventory),
        ("Other CA",        bs.other_current_assets),
        ("Total CA",        bs.total_current_assets),
        ("",                None),
        ("PP&E (net)",      bs.ppe_net),
        ("Goodwill",        bs.goodwill),
        ("Intangibles",     bs.intangible_assets),
        ("Other NCA",       bs.other_non_current_assets),
        ("Total Assets",    bs.total_assets),
    ]
    liab_rows = [
        ("A/P",             bs.accounts_payable),
        ("ST Debt",         bs.short_term_debt),
        ("Curr LT Debt",   bs.current_portion_lt_debt),
        ("Accrued",         bs.accrued_liabilities),
        ("Other CL",       bs.other_current_liabilities),
        ("Total CL",       bs.total_current_liabilities),
        ("",                None),
        ("LT Debt",        bs.long_term_debt),
        ("Other NCL",      bs.other_non_current_liabilities),
        ("Total Liab",     bs.total_liabilities),
        ("Equity",         bs.total_equity),
        ("L+E",            bs.total_liabilities + bs.total_equity),
    ]

    print(f"  {'ASSETS':<{lw}}{'':<{bw}}{gap}{'LIAB + EQUITY':<{lw}}")
    print(f"  {'-' * (lw + bw)}{gap}{'-' * (lw + bw)}")
    for (al, av), (ll, lv) in zip(assets_rows, liab_rows):
        left = f"  {al:<{lw}}{av:>{bw},.0f}" if av is not None else ""
        right = f"{ll:<{lw}}{lv:>{bw},.0f}" if lv is not None else ""
        print(f"{left:<{2 + lw + bw}}{gap}{right}")

    # Balance check
    diff = abs(bs.total_assets - (bs.total_liabilities + bs.total_equity))
    pct = diff / bs.total_assets * 100 if bs.total_assets else 0
    flag = "OK" if pct < 2.0 else "WARN"
    print(f"\n  Balance check: {flag}  (diff={diff:,.0f}, {pct:.2f}%)")

    # Key derived metrics
    print(f"\n  Total Debt:           {bs.total_debt:>12,.0f}")
    print(f"  Net Debt:             {bs.net_debt:>12,.0f}")
    print(f"  Net Working Capital:  {bs.net_working_capital:>12,.0f}")


# ---------------------------------------------------------------------------
# Print: Non-Recurring Items (Pass 2)
# ---------------------------------------------------------------------------

def print_non_recurring_items(
    items: list[NonRecurringItem],
    provider: str,
) -> None:
    _section(f"NON-RECURRING ITEMS (identified by {provider.upper()})")
    if not items:
        print("  None found.")
        return

    total_add = sum(i.amount for i in items if i.direction == "add_back")
    total_rem = sum(i.amount for i in items if i.direction == "remove")
    print(f"  Found {len(items)} items  |  "
          f"Total add-backs: {total_add:,.0f}M  |  Total removals: {total_rem:,.0f}M\n")

    for item in items:
        sign = "+" if item.direction == "add_back" else "-"
        print(f"  [{item.year}] {sign}{item.amount:,.0f}M  {item.category.upper()}  "
              f"({item.confidence} confidence)  line_item={item.line_item}")
        print(f"         {item.description}")
        if item.source:
            print(f"         Source: {item.source}")
        print()


# ---------------------------------------------------------------------------
# Print: GAAP -> Non-GAAP Reconciliation
# ---------------------------------------------------------------------------

def print_normalization(
    raw: FinancialStatements,
    adjusted: FinancialStatements,
) -> None:
    _section("GAAP -> NON-GAAP RECONCILIATION ($M)")
    years = raw.years
    if not years:
        return

    for y in years:
        r = raw.get_income_statement(y)
        a = adjusted.get_income_statement(y)
        delta = a.ebit - r.ebit
        if delta == 0:
            continue
        print(f"  {y}: EBIT  GAAP={r.ebit:>10,.0f}  Adj={a.ebit:>10,.0f}  "
              f"Delta={delta:>+10,.0f}")

    # Summary
    has_delta = any(
        adjusted.get_income_statement(y).ebit != raw.get_income_statement(y).ebit
        for y in years
    )
    if not has_delta:
        print("  No adjustments applied (no non-recurring items, or none matched I/S fields).")


# ---------------------------------------------------------------------------
# Print: Historical FCFF
# ---------------------------------------------------------------------------

def print_historical_fcff(financials: FinancialStatements) -> None:
    _section("HISTORICAL FCFF (CFO-based, $M)")
    years = financials.years
    print(f"  {'Year':>4}  {'Revenue':>9}  {'CFO':>8}  {'Int*(1-t)':>9}  "
          f"{'CapEx':>7}  {'FCFF':>8}  {'FCFF%':>6}")
    print("  " + "-" * 60)

    for y in years:
        is_ = financials.get_income_statement(y)
        cf_ = financials.get_cash_flow(y)
        if is_ is None or cf_ is None:
            continue
        h = calculate_fcff_historical(is_, cf_)
        print(f"  {y:>4}  {h.revenue:>9,.0f}  {h.cfo:>8,.0f}  "
              f"{h.after_tax_interest:>9,.0f}  {h.capital_expenditures:>7,.0f}  "
              f"{h.fcff:>8,.0f}  {h.fcff_margin:>5.1%}")


# ---------------------------------------------------------------------------
# Print: Assumptions
# ---------------------------------------------------------------------------

def print_assumptions(assumptions: dict, overrides: ProjectionAssumptions) -> None:
    _section("PROJECTION ASSUMPTIONS (from adjusted financials)")

    def _tag(field_name: str) -> str:
        """Return '(override)' if the user explicitly set this field."""
        val = getattr(overrides, field_name, None)
        if field_name == "revenue_growth_rates":
            return " (override)" if overrides.revenue_growth_rates else ""
        return " (override)" if val is not None else ""

    rates = assumptions["revenue_growth_rates"]
    print(f"  Revenue growth (per yr): {[f'{r:.1%}' for r in rates]}{_tag('revenue_growth_rates')}")
    print(f"  Operating margin:        {assumptions['operating_margin']:.2%}{_tag('operating_margin')}")
    print(f"  Tax rate:                {assumptions['tax_rate']:.2%}{_tag('tax_rate')}")
    print(f"  D&A / Revenue:           {assumptions['da_pct_revenue']:.2%}{_tag('da_pct_revenue')}")
    print(f"  CapEx / Revenue:         {assumptions['capex_pct_revenue']:.2%}{_tag('capex_pct_revenue')}")
    print(f"  NWC chg / Revenue:       {assumptions['nwc_pct_revenue']:.2%}{_tag('nwc_pct_revenue')}")
    print(f"  Projection years:        {assumptions['projection_years']}")
    print(f"  Terminal growth:          {assumptions['terminal_growth_rate']:.2%}")


# ---------------------------------------------------------------------------
# Print: CAPM
# ---------------------------------------------------------------------------

def print_capm(capm_result, price_data, args: argparse.Namespace) -> None:
    _section("CAPM")
    print(f"  Ticker:               {args.ticker}")
    print(f"  Lookback:             {args.lookback_years} years, {args.frequency} returns")
    print(f"  Observations:         {len(price_data.stock_returns)}")
    beta_src = "(override)" if args.beta is not None else "(regression)"
    print(f"\n  Beta:                 {capm_result.beta:.3f}  {beta_src}")
    print(f"  R-squared:            {capm_result.r_squared:.3f}")
    print(f"  Std error:            {capm_result.std_error:.3f}")
    print(f"\n  Risk-free rate:       {capm_result.risk_free_rate:.2%}")
    print(f"  Equity risk premium:  {capm_result.equity_risk_premium:.2%}")
    print(f"  Cost of equity:       {capm_result.cost_of_equity:.2%}")


# ---------------------------------------------------------------------------
# Print: WACC
# ---------------------------------------------------------------------------

def print_wacc(wacc_result, market_cap: float, total_debt: float) -> None:
    _section("WACC")
    total_cap = market_cap + total_debt
    print(f"  Market cap:           ${market_cap:>12,.0f}M")
    print(f"  Total debt:           ${total_debt:>12,.0f}M")
    print(f"  Total capital:        ${total_cap:>12,.0f}M")
    print(f"\n  Equity weight:        {wacc_result.equity_weight:.1%}")
    print(f"  Debt weight:          {wacc_result.debt_weight:.1%}")
    print(f"  Cost of equity:       {wacc_result.cost_of_equity:.2%}")
    print(f"  Cost of debt (pre-t): {wacc_result.cost_of_debt:.2%}")
    print(f"  Tax rate:             {wacc_result.tax_rate:.1%}")
    print(f"\n  WACC:                 {wacc_result.wacc:.2%}")


# ---------------------------------------------------------------------------
# Print: Projected FCFFs
# ---------------------------------------------------------------------------

def print_projected_fcffs(projected) -> None:
    _section("PROJECTED FCFF (EBIT-based, $M)")
    print(f"  {'Year':>4}  {'Revenue':>9}  {'EBIT':>9}  {'NOPAT':>9}  "
          f"{'D&A':>7}  {'CapEx':>7}  {'dNWC':>7}  {'FCFF':>9}")
    print("  " + "-" * 72)
    for p in projected:
        print(f"  {p.year:>4}  {p.revenue:>9,.0f}  {p.ebit:>9,.0f}  {p.nopat:>9,.0f}  "
              f"{p.depreciation_amortization:>7,.0f}  {abs(p.capital_expenditures):>7,.0f}  "
              f"{p.change_in_working_capital:>7,.0f}  {p.fcff:>9,.0f}")


# ---------------------------------------------------------------------------
# Print: DCF Result
# ---------------------------------------------------------------------------

def print_dcf_result(dcf) -> None:
    _section("DCF VALUATION")
    print(f"\n  PV of projected FCFFs:       ${dcf.pv_fcffs:>12,.0f}M")
    print(f"  Terminal Value (undiscounted):${dcf.terminal_value:>12,.0f}M")
    print(f"  PV of Terminal Value:        ${dcf.pv_terminal_value:>12,.0f}M")
    print(f"  {'':->42}")
    print(f"  Enterprise Value:            ${dcf.enterprise_value:>12,.0f}M")
    print(f"\n  Less: Net Debt               ${dcf.net_debt:>12,.0f}M")
    print(f"  Equity Value:                ${dcf.equity_value:>12,.0f}M")
    print(f"\n  Diluted Shares:               {dcf.diluted_shares:>12,.0f}M")
    print(f"  Implied Share Price:         ${dcf.implied_share_price:>11.2f}")
    print(f"  Current Market Price:        ${dcf.current_price:>11.2f}")

    direction = "UPSIDE" if dcf.upside_downside >= 0 else "DOWNSIDE"
    print(f"\n  {'=' * 42}")
    print(f"  {direction}:  {dcf.upside_downside:>+.1f}%")
    print(f"  {'=' * 42}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    global _t0
    _t0 = time.time()

    args = parse_args()
    filings = parse_pdf_args(args.pdfs)

    # ===== STAGE 1: EXTRACTION (LLM) ========================================
    cache = _cache_path(args)
    if cache and cache.exists() and not args.no_cache:
        _step(1, "Loading cached extraction")
        _section(f"LOADING CACHED EXTRACTION: {cache.name}")
        financials, adjustments = _load_cache(cache)
    else:
        _step(1, f"Extracting financials via {args.provider.upper()} — {len(filings)} PDF(s)")
        _section(f"EXTRACTING via {args.provider.upper()} "
                 f"({len(filings)} PDF{'s' if len(filings) > 1 else ''})")

        single = len(filings) == 1 and filings[0][0] == 0
        if single:
            financials, adjustments = extract_financials(
                pdf_path=filings[0][1],
                ticker=args.ticker,
                company_name=args.company_name,
                provider=args.provider,
                model=args.model,
                debug=True,
            )
        else:
            # Filter out year=0 entries, fall back to single if needed
            valid = [(y, p) for y, p in filings if y > 0]
            if not valid:
                financials, adjustments = extract_financials(
                    pdf_path=filings[0][1],
                    ticker=args.ticker,
                    company_name=args.company_name,
                    provider=args.provider,
                    model=args.model,
                    debug=True,
                )
            else:
                financials, adjustments = extract_multi_year(
                    filings=valid,
                    ticker=args.ticker,
                    company_name=args.company_name,
                    provider=args.provider,
                    model=args.model,
                    debug=True,
                )

        if cache:
            _save_cache(cache, financials, adjustments)
            print(f"  Cached to {cache.name}")

    years = financials.years
    print(f"  Ticker: {financials.ticker}  |  Company: {financials.company_name}")
    print(f"  Years extracted: {years}")

    # ===== STAGE 2: EXTRACTED F/S (Pass 1 output) ===========================
    _step(2, "Displaying extracted financial statements")
    print_extracted_financials(financials)

    # ===== STAGE 3: NON-RECURRING ITEMS (Pass 2 output) =====================
    _step(3, "Displaying non-recurring items")
    print_non_recurring_items(adjustments, args.provider)

    # ===== STAGE 4: NORMALIZE (GAAP -> Non-GAAP) ============================
    _step(4, "Normalizing financials (GAAP -> Non-GAAP)")
    adjusted = normalize_financials(financials, adjustments)
    print_normalization(financials, adjusted)

    # ===== STAGE 5: HISTORICAL FCFF =========================================
    _step(5, "Computing historical FCFF")
    print_historical_fcff(financials)

    # ===== STAGE 6: DERIVE ASSUMPTIONS ======================================
    _step(6, "Deriving projection assumptions")
    overrides = build_overrides(args)
    assumptions = derive_assumptions(adjusted, overrides)
    print_assumptions(assumptions, overrides)

    # ===== STAGE 7: CAPM ====================================================
    _step(7, "Fetching market data & running CAPM")
    price_data = fetch_price_data(
        args.ticker,
        lookback_years=args.lookback_years,
        frequency=args.frequency,
    )
    capm_result = run_capm(
        price_data,
        risk_free_rate=overrides.risk_free_rate,
        equity_risk_premium=overrides.equity_risk_premium,
        beta_override=overrides.beta_override,
    )
    print_capm(capm_result, price_data, args)

    # ===== STAGE 8: WACC ====================================================
    _step(8, "Calculating WACC")
    latest_is = adjusted.get_income_statement(adjusted.latest_year)
    latest_bs = adjusted.get_balance_sheet(adjusted.latest_year)

    shares = latest_is.diluted_shares_outstanding if latest_is else 0
    if shares == 0:
        import yfinance as yf
        info = yf.Ticker(args.ticker).info
        shares = info.get("sharesOutstanding", 0) / 1e6
        print(f"\n  Diluted shares from yfinance: {shares:,.0f}M (not in extracted F/S)")

    market_cap = price_data.current_price * shares
    total_debt = latest_bs.total_debt if latest_bs else 0

    wacc_result = calculate_wacc(
        capm_result=capm_result,
        income_statement=latest_is,
        balance_sheet=latest_bs,
        market_cap=market_cap,
        cost_of_debt_override=overrides.cost_of_debt_override,
        tax_rate_override=assumptions["tax_rate"],
    )
    print_wacc(wacc_result, market_cap, total_debt)

    # ===== STAGE 9: PROJECT FCFFs ===========================================
    _step(9, "Projecting future FCFFs")
    projected = project_fcffs(adjusted, assumptions)
    print_projected_fcffs(projected)

    # ===== STAGE 10: DCF ====================================================
    _step(10, "Running DCF valuation")
    dcf_result = run_dcf(
        projected_fcffs=projected,
        wacc_result=wacc_result,
        financials=adjusted,
        terminal_growth_rate=assumptions["terminal_growth_rate"],
        current_price=price_data.current_price,
        diluted_shares=shares,
    )
    print_dcf_result(dcf_result)

    # Done
    elapsed = time.time() - _t0
    m, s = divmod(int(elapsed), 60)
    print(f"\n>>> Done in {m}:{s:02d}" if m else f"\n>>> Done in {s}s")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
