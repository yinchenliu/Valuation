"""Local CLI for DCF valuation — runs the full pipeline with detailed output.

Usage:
    # Folder of 10-K PDFs (RECOMMENDED) — years auto-discovered from filenames.
    # Any filename prefix works, as long as each name contains its fiscal year:
    #   10K_filings/AbbVie Inc._10-K_2023-12-31_English.pdf
    #   10K_filings/AbbVie Inc._10-K_2024-12-31_English.pdf
    #   10K_filings/AbbVie Inc._10-K_2025-12-31_English.pdf
    python cli.py 10K_filings -t ABBV -n "AbbVie Inc." --cache-dir ./cache

    # Ticker folder (ticker inferred from the folder name, e.g. uploads/LLY)
    python cli.py path/to/LLY

    # Single 10-K (all years auto-discovered)
    python cli.py path/to/10K.pdf -t GOOGL -n "Alphabet Inc."

    # Multi-PDF (explicit year-prefixed, still supported)
    python cli.py 2023:10K_2023.pdf 2024:10K_2024.pdf 2025:10K_2025.pdf \\
        -t LLY -n "Eli Lilly" -p gemini --cache-dir ./cache

    # Rerun from cache (skips LLM extraction).
    # The cache is keyed on the PDFs themselves — path, size, mtime and
    # sha256 — plus the ticker, provider and model. Naming a DIFFERENT PDF
    # under the same ticker is a MISS, and the miss says which file changed.
    python cli.py 10K_filings -t ABBV -p gemini --cache-dir ./cache

    # With overrides
    python cli.py 10K.pdf -t AAPL --terminal-growth 0.03 --beta 1.1

    # From a Claude Code session file: no API call, no credential, no pickle.
    # The ticker, company and PDFs come from the file (see
    # `python -m ingestion.session_extraction --help`).
    python cli.py --session-file extractions/CMG.json
"""

from __future__ import annotations

import argparse
import pickle
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

import config
from analysis.capm import run_capm
from analysis.dcf import run_dcf
from analysis.fcff import calculate_fcff_historical
from analysis.normalizer import normalize_financials, partition_by_confidence
from analysis.projector import derive_assumptions, project_fcffs
from analysis.wacc import calculate_wacc
from ingestion.claude_extractor import (
    describe_resolution,
    extract_financials,
    extract_multi_year,
)
from ingestion.filings import InputFingerprint, fingerprint_filings, parse_pdf_args
from ingestion.price_fetcher import fetch_price_data
from ingestion.session_extraction import load_session_extraction
from models.financial_statements import (
    BALANCE_CHECK_TOLERANCE,
    FinancialStatements,
    NonRecurringItem,
)
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

    p.add_argument(
        "pdfs",
        nargs="*",
        help=(
            "A folder of 10-K PDFs (years inferred from filenames), a ticker "
            "folder, PDF path(s), or YEAR:PATH entries "
            "(e.g. 10K_filings/, LLY/, 10K.pdf, or 2023:10K.pdf). "
            "Omit when --session-file is given"
        ),
    )
    p.add_argument(
        "-t", "--ticker", default=None,
        help="Stock ticker; defaults to the folder name in directory mode",
    )
    p.add_argument("-n", "--company-name", default="", help="Company name")

    # Extraction
    g = p.add_argument_group("extraction")
    # The default is config.DEFAULT_EXTRACTION_PROVIDER and not a literal, so the CLI
    # and the web app cannot drift apart on which model reads a filing.
    #
    # argparse's default is None, and the configured default is applied after
    # parsing, so that -p given alongside --session-file can be refused rather than
    # silently ignored. Without --session-file the resolved value is the same
    # constant as before.
    g.add_argument(
        "-p", "--provider",
        default=None,
        choices=["claude", "gemini"],
        help=f"LLM provider (default: {config.DEFAULT_EXTRACTION_PROVIDER})",
    )
    g.add_argument("-m", "--model", default=None, help="Override LLM model ID")
    g.add_argument("--cache-dir", default=None, help="Directory for pickle cache")
    g.add_argument("--no-cache", action="store_true", help="Force re-extraction")
    g.add_argument(
        "--session-file", default=None, metavar="FILE",
        help=(
            "Read the extraction from a Claude Code session file "
            "(ingestion/session_extraction.py) instead of calling an API. "
            "Replaces the PDF arguments; the ticker comes from the file"
        ),
    )

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
    g.add_argument(
        "--confirm-zero-debt", action="store_true",
        help="Confirm that a total debt of 0 is real. Use it only when the "
             "company repaid all its debt during the year, so the balance "
             "sheet shows 0 while the income statement shows interest "
             "expense. The company is then valued with no debt. Without it "
             "that pattern stops the run; --cost-of-debt does not get past it",
    )
    g.add_argument("--lookback-years", type=int, default=5)
    g.add_argument("--frequency", default="monthly", choices=["daily", "monthly"])

    args = p.parse_args()

    if args.session_file is not None:
        if args.pdfs:
            p.error(
                "--session-file and PDF arguments cannot be combined: the session "
                "file names its own PDFs and verifies each by sha256"
            )
        if args.provider is not None or args.model is not None:
            p.error(
                "-p/--provider and -m/--model choose the API route. A session file "
                "records the model that read it; they do not apply"
            )
        if args.cache_dir is not None or args.no_cache:
            p.error(
                "--cache-dir and --no-cache apply to the API route. The session "
                "file is the stored extraction; no pickle cache is read or written"
            )
        if args.ticker:
            args.ticker = args.ticker.upper()
        return args

    if not args.pdfs:
        p.error("give the 10-K PDF(s) to extract, or --session-file FILE")
    if args.provider is None:
        args.provider = config.DEFAULT_EXTRACTION_PROVIDER

    if args.ticker:
        args.ticker = args.ticker.upper()
    elif len(args.pdfs) == 1 and Path(args.pdfs[0]).is_dir():
        args.ticker = Path(args.pdfs[0]).resolve().name.upper()
    else:
        p.error("-t/--ticker is required unless the single input is a ticker folder")
    return args


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
        equity_risk_premium=args.equity_risk_premium,
        cost_of_debt_override=args.cost_of_debt,
        zero_debt_confirmed=args.confirm_zero_debt,
        beta_override=args.beta,
        beta_lookback_years=args.lookback_years,
        return_frequency=args.frequency,
    )


# ---------------------------------------------------------------------------
# Helpers: cache
# ---------------------------------------------------------------------------

# P11a changed the extraction's shape: Pass 1 returns printed lines, and each
# BalanceSheet carries the two printed totals. A cache written before that holds
# figures some of which the model added up, and balance sheets with no printed
# totals, so it is refused by marker rather than read.
# P14a changed it again: every figure is converted to millions from the filing's
# printed unit statements, and each BalanceSheet carries printed_unit_in_millions.
# A cache written before that holds figures never converted (a filing in thousands
# reads 1,000 times too large) and balance sheets with no printed unit, so it is
# refused by the same marker check.
CACHE_FORMAT = "p14b-pass2-units-v1"


@dataclass(frozen=True)
class ExtractionKey:
    """Everything a cached extraction is an answer to.

    The PDFs, and the model that read them. Provider and model are in the key
    for the same reason the files are: `P2b-provider` made the output state
    which model produced the figures, so serving a Gemini extraction under a
    CLAUDE label would print a false label rather than merely a stale number.
    """

    ticker: str
    provider: str
    model: str
    inputs: tuple[InputFingerprint, ...]


def build_extraction_key(
    args: argparse.Namespace, filings: list[tuple[int, str]]
) -> ExtractionKey:
    """Assemble the key a cached extraction is stored under and compared by."""
    return ExtractionKey(
        ticker=args.ticker.upper(),
        provider=args.provider,
        model=args.model if args.model is not None else "(provider default)",
        inputs=fingerprint_filings(filings),
    )


def describe_key_difference(cached: ExtractionKey, current: ExtractionKey) -> list[str]:
    """Name every way the cached extraction's question differs from this one.

    Returns an empty list when the two keys are identical, i.e. when a cache
    hit is honest. Otherwise one line per difference, each naming the file or
    the setting — "a cache miss happened" is not enough for a reader to know
    whether the extraction about to be paid for is necessary.
    """
    differences: list[str] = []

    if cached.ticker != current.ticker:
        differences.append(f"ticker: cached {cached.ticker!r}, now {current.ticker!r}")
    if cached.provider != current.provider:
        differences.append(
            f"provider: cached {cached.provider!r}, now {current.provider!r}"
        )
    if cached.model != current.model:
        differences.append(f"model: cached {cached.model!r}, now {current.model!r}")

    cached_by_path = {p.path: p for p in cached.inputs}
    current_by_path = {p.path: p for p in current.inputs}

    for path in current_by_path:
        if path not in cached_by_path:
            differences.append(f"NEW input, not in the cached extraction: {path}")
    for path in cached_by_path:
        if path not in current_by_path:
            differences.append(
                f"the cached extraction was built from a file NOT supplied this "
                f"run: {path}"
            )
    for path, now in current_by_path.items():
        was = cached_by_path.get(path)
        if was is None:
            continue
        if was.sha256 != now.sha256:
            differences.append(
                f"CONTENT CHANGED: {path}\n"
                f"      sha256 {was.sha256[:16]}… -> {now.sha256[:16]}…, "
                f"{was.size_bytes:,} -> {now.size_bytes:,} bytes"
            )
        elif was.year != now.year:
            differences.append(
                f"fiscal year re-assigned for {path}: {was.year} -> {now.year}"
            )

    return differences


def _cache_path(args: argparse.Namespace) -> Path | None:
    """Where this ticker's cached extraction lives.

    Still one file per ticker, deliberately: the key is compared on *read*, not
    encoded in the filename, because a filename-encoded key can only produce a
    silent miss. Comparing on read is what lets the miss say which file changed
    and what it changed from.

    The `_inputs` suffix is not decoration. `.cache_{ticker}_extraction.pkl` is
    the old, ticker-only-keyed name, and two such files predating this build sit
    in `cache/`. Unpickling executes code in the pickle, so they must not be
    opened even to reject them; a new name means they are never a candidate
    path at all.
    """
    if not args.cache_dir:
        return None
    d = Path(args.cache_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d / f".cache_{args.ticker.lower()}_extraction_inputs.pkl"


def _load_cache(
    path: Path,
) -> tuple[ExtractionKey, FinancialStatements, list[NonRecurringItem]]:
    """Read a cache entry and its key.

    Raises:
        ValueError: when the file is not a cache entry in this format. It is
            not treated as a miss and silently overwritten: a file under this
            exact name that this code did not write is a fact the user needs,
            and re-extracting costs real money.
    """
    with open(path, "rb") as f:
        payload = pickle.load(f)

    if (
        not isinstance(payload, tuple)
        or len(payload) != 4
        or payload[0] != CACHE_FORMAT
        or not isinstance(payload[1], ExtractionKey)
    ):
        raise ValueError(
            f"{path} is not a cache entry written by this CLI (expected format "
            f"marker {CACHE_FORMAT!r}). Delete the file, or run with "
            f"--no-cache, or point --cache-dir elsewhere. It is not being "
            f"overwritten automatically, because that would silently discard "
            f"an extraction that cost money to produce."
        )

    _marker, key, financials, non_recurring = payload
    return key, financials, non_recurring


def _save_cache(
    path: Path,
    key: ExtractionKey,
    financials: FinancialStatements,
    non_recurring: list[NonRecurringItem],
) -> None:
    with open(path, "wb") as f:
        pickle.dump((CACHE_FORMAT, key, financials, non_recurring), f)


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

    # Balance check: each printed total row against the sum of the lines mapped
    # under it. FAIL when the difference exceeds 1 in the filing's printed unit,
    # which allows for rounding and nothing more (the user, 2026-10-02: "if the
    # balance sheet check doesn't pass, just fail it and show it"). A failure is
    # shown and the figures are kept; nothing here repairs one. The figures are in
    # millions, so the threshold in millions is 1 printed unit (0.001 for a filing
    # in thousands). The threshold and the status are bs.printed_total_check's,
    # the same the parser and the page use.
    print(f"\n  Balance check — printed total against the sum of the mapped lines "
          f"(FAIL above {bs.printed_total_tolerance():,g} $M: "
          f"{BALANCE_CHECK_TOLERANCE:,g} in the filing's printed unit, and 1 printed "
          f"unit = {bs.printed_unit():,g} $M):")
    # $M to the printed unit, so a gap below 1 $M (a filing in thousands) shows.
    places = bs.printed_unit_decimals()
    for check_label, printed, mapped, difference in (
        ("Total Assets", bs.printed_total_assets, bs.total_assets,
         bs.printed_total_assets_difference),
        ("Total Liab + Equity", bs.printed_total_liabilities_and_equity,
         bs.total_liabilities_and_equity,
         bs.printed_total_liabilities_and_equity_difference),
    ):
        # `bs` supplies its own printed unit, so the threshold is 1 printed unit of
        # this filing.
        status = bs.printed_total_check(difference)
        printed_text = "not extracted" if printed is None else f"{printed:,.{places}f}"
        diff_text = "" if difference is None else f"{difference:+,.{places}f}"
        print(f"    {check_label:<20}  printed {printed_text:>13}  "
              f"mapped {mapped:>12,.{places}f}  diff {diff_text:>8}  {status}")

    # Key derived metrics
    print(f"\n  Total Debt:           {bs.total_debt:>12,.0f}")
    print(f"  Net Debt:             {bs.net_debt:>12,.0f}")
    print(f"  Net Working Capital:  {bs.net_working_capital:>12,.0f}")
    # Memo: the two noncontrolling interest lines as printed, each already inside
    # Equity or another line above, so in no total. None is "not extracted" and
    # is printed as such, never as 0 (the P8b rule). Not summed here: the one
    # sum is analysis/dcf.py:total_noncontrolling_interest, shown in the DCF block.
    for nci_label, nci in (
        ("NCI, nonredeemable:", bs.noncontrolling_interest_nonredeemable),
        ("NCI, redeemable:", bs.noncontrolling_interest_redeemable),
    ):
        nci_text = "not extracted" if nci is None else f"{nci:,.0f}"
        print(f"  {nci_label:<22}{nci_text:>12}  (memo; already inside the lines above)")


# ---------------------------------------------------------------------------
# Print: Non-Recurring Items (Pass 2)
# ---------------------------------------------------------------------------

def print_non_recurring_items(
    items: list[NonRecurringItem],
    identified_by: str,
) -> None:
    """Print the items that WILL be applied to the statements.

    `items` is the applied half of `partition_by_confidence`, never the raw Pass 2
    list. The heading says so, because a list printed under "non-recurring items"
    that is not the list the arithmetic used is the defect this unit closes
    wearing a different face. The excluded half is printed by
    print_excluded_non_recurring_items, below.

    `identified_by` names who read the filing, as the caller states it: the
    provider for the API route, or the Claude Code session and its declared model
    for the session route. A heading that said CLAUDE with no route would hide
    which of the two produced these items (rule 6).
    """
    _section(f"NON-RECURRING ITEMS APPLIED (identified by {identified_by})")
    if not items:
        print("  None applied.")
        return

    total_add = sum(i.amount for i in items if i.direction == "add_back")
    total_rem = sum(i.amount for i in items if i.direction == "remove")
    print(f"  Applying {len(items)} items  |  "
          f"Total add-backs: {total_add:,.0f}M  |  Total removals: {total_rem:,.0f}M\n")

    for item in items:
        sign = "+" if item.direction == "add_back" else "-"
        print(f"  [{item.year}] {sign}{item.amount:,.0f}M  {item.category.upper()}  "
              f"({item.confidence} confidence)  line_item={item.line_item}")
        print(f"         {item.description}")
        if item.source:
            print(f"         Source: {item.source}")
        print()


def print_excluded_non_recurring_items(items: list[NonRecurringItem]) -> None:
    """Print the items that were NOT applied, with everything needed to reverse it.

    The user's decision, 2026-09-22: "For low confidence, just leave a note and
    document, but don't need to adjust the F/S." Documenting it means the year,
    the amount, the line item, the direction, the description and the source the
    model cited — a reader who disagrees can apply any one of these by hand from
    this block alone.

    The wording says "NOT applied" in as many words. A list printed without that
    sentence reads as a summary of what was done, which is the opposite of what
    it is.
    """
    _section("NON-RECURRING ITEMS EXCLUDED — NOT applied to the F/S")
    if not items:
        print("  None. Every item the model identified was applied.")
        return

    total_add = sum(i.amount for i in items if i.direction == "add_back")
    total_rem = sum(i.amount for i in items if i.direction == "remove")
    print(f"  {len(items)} item(s) the model tagged LOW confidence were NOT applied")
    print("  to the financial statements, so the valuation below does not "
          "include them.")
    print(f"  Add-backs withheld: {total_add:,.0f}M  |  "
          f"Removals withheld: {total_rem:,.0f}M")
    print("  To apply one, re-read the note it cites and treat it by hand.\n")

    for item in items:
        sign = "+" if item.direction == "add_back" else "-"
        print(f"  [{item.year}] {sign}{item.amount:,.0f}M  {item.category.upper()}  "
              f"({item.confidence} confidence — EXCLUDED)  "
              f"line_item={item.line_item}  direction={item.direction}")
        print(f"         {item.description}")
        print(f"         Source: {item.source if item.source else '(none cited)'}")
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

def _wrap_label(text: str, indent: str = "      ") -> str:
    """Wrap a provenance sentence under the figure it qualifies.

    Rule 6 asks for the assumption to be *visible*, which on a terminal means
    it has to sit beside its number rather than run off the right margin.
    """
    return textwrap.fill(
        text,
        width=W + 20,
        initial_indent=indent,
        subsequent_indent=indent,
    )


def print_capm(capm_result, price_data, args: argparse.Namespace) -> None:
    _section("CAPM")
    print(f"  Ticker:               {args.ticker}")
    print(f"  Lookback:             {args.lookback_years} years, {args.frequency} returns")
    print(f"  Observations:         {len(price_data.stock_returns)}")

    # Rule 6, backlog item 35. The verdict sits on the line under the beta, not
    # two lines away past the diagnostics, because the reader who stops at the
    # beta is exactly the reader this label exists for.
    print(f"\n  Beta:                 {capm_result.beta:.3f}")
    print(_wrap_label(f"source: {capm_result.beta_source}"))
    print(_wrap_label(f"reliability: {capm_result.beta_reliability}"))
    print(f"  R-squared:            {capm_result.r_squared:.3f}")
    print(f"  Std error:            {capm_result.std_error:.3f}")

    # Rule 6, backlog item 34.
    print(f"\n  Risk-free rate:       {capm_result.risk_free_rate:.2%}")
    print(_wrap_label(f"source: {capm_result.risk_free_rate_source}"))
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
    # Rule 6, backlog item 9.
    print(_wrap_label(f"source: {wacc_result.cost_of_debt_source}"))
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
    print(f"  Less: Noncontrolling Int.    ${dcf.noncontrolling_interest:>12,.0f}M")
    print(f"        source: {dcf.noncontrolling_interest_source}")
    print(f"  Equity Value:                ${dcf.equity_value:>12,.0f}M")
    print(f"\n  Diluted Shares:               {dcf.diluted_shares:>12,.0f}M")
    print(f"  Implied Share Price:         ${dcf.implied_share_price:>11.2f}")
    print(f"  Current Market Price:        ${dcf.current_price:>11.2f}")

    direction = "UPSIDE" if dcf.upside_downside >= 0 else "DOWNSIDE"
    print(f"\n  {'=' * 42}")
    print(f"  {direction}:  {dcf.upside_downside:>+.1f}%")
    print(f"  {'=' * 42}")


def _extract_via_api(
    args: argparse.Namespace,
) -> tuple[FinancialStatements, list[NonRecurringItem], str]:
    """Stage 1 on the API route: the pickle cache, or a paid extraction.

    Returns the statements, the non-recurring items, and the label that says where
    they came from. Moved out of main() unchanged when the session route was added.
    """
    try:
        filings = parse_pdf_args(args.pdfs, args.ticker)
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    # ===== STAGE 1: EXTRACTION (LLM) ========================================
    #
    # Backlog item 33. The cache is keyed on the PDFs themselves — path, size,
    # mtime and sha256 — plus the ticker, provider and model. A hit therefore
    # means "these exact files, read by this exact model", and it is safe to
    # skip the extraction. Anything else is a miss that names what changed.
    cache = _cache_path(args)
    current_key = build_extraction_key(args, filings)
    cache_label = ""

    cached_payload: tuple[FinancialStatements, list[NonRecurringItem]] | None = None
    if cache and cache.exists() and not args.no_cache:
        cached_key, cached_financials, cached_adjustments = _load_cache(cache)
        differences = describe_key_difference(cached_key, current_key)
        if differences:
            _step(1, "Cached extraction REJECTED — the inputs changed")
            _section(f"CACHE MISS: {cache.name} answers a different question")
            print("  The cached extraction was NOT used. What differs:")
            for line in differences:
                print(f"    - {line}")
            print(
                "\n  A cached extraction is only reused when the files, the "
                "ticker, the provider\n  and the model all match. Re-extracting "
                "from the files named on the command line."
            )
            sys.stdout.flush()
        else:
            cached_payload = (cached_financials, cached_adjustments)

    if cached_payload is not None and cache is not None:
        _step(1, "Loading cached extraction")
        _section(f"LOADING CACHED EXTRACTION: {cache.name}")
        print("  Reused because every input matches the run that produced it:")
        for fp in current_key.inputs:
            print(
                f"    - {Path(fp.path).name}  sha256 {fp.sha256[:16]}…  "
                f"{fp.size_bytes:,} bytes"
            )
        print(f"    - read by {current_key.provider} / {current_key.model}")
        print("  No PDF was opened and no extraction was paid for on this run.")
        financials, adjustments = cached_payload
        cache_label = (
            f"cached extraction reused from {cache.name}, "
            f"keyed on the {len(current_key.inputs)} file(s) above"
        )
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

        cache_label = "live extraction of " + ", ".join(
            Path(fp.path).name for fp in current_key.inputs
        )
        if cache:
            _save_cache(cache, current_key, financials, adjustments)
            print(f"  Cached to {cache.name}, keyed on the file(s) just read")

    return financials, adjustments, cache_label


def _extract_from_session_file(
    args: argparse.Namespace,
) -> tuple[FinancialStatements, list[NonRecurringItem], str, str]:
    """Stage 1 on the session route: read a Claude Code session file. No API call.

    Returns the statements, the non-recurring items, the extraction-source label for
    the closing summary, and the "identified by" label for stage 3. The ticker and
    company name come from the file; a -t or -n that differs from it stops the run.
    No pickle cache is read or written: the session file is the stored extraction.
    """
    _step(1, "Reading the extraction from a Claude Code session file")
    _section(f"EXTRACTION FROM SESSION FILE: {Path(args.session_file).name}")
    try:
        session = load_session_extraction(args.session_file)
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    file_ticker = session.financials.ticker
    if args.ticker and args.ticker != file_ticker.upper():
        raise SystemExit(
            f"ERROR: -t {args.ticker} differs from the session file's ticker "
            f"{file_ticker!r}. Omit -t; the ticker comes from the file."
        )
    file_company = session.financials.company_name
    if args.company_name and args.company_name != file_company:
        raise SystemExit(
            f"ERROR: -n {args.company_name!r} differs from the session file's "
            f"company name {file_company!r}. Omit -n; the name comes from the file."
        )
    args.ticker = file_ticker.upper()
    args.company_name = file_company

    resolution = session.resolution
    print(f"  {describe_resolution(resolution)}")
    print("  Filings, each verified against the sha256 recorded when it was planned:")
    for record in session.filings:
        pages1 = ", ".join(str(n) for n in record.pages_pass1)
        pages2 = ", ".join(str(n) for n in record.pages_pass2)
        print(
            f"    - [{record.index}] {Path(record.plan.pdf_path).name}  "
            f"sha256 {record.pdf_sha256[:16]}…  {record.size_bytes:,} bytes"
        )
        print(f"        pages read: pass 1 {pages1}; pass 2 {pages2}")
    if session.validation_errors:
        print("\n  [FAIL] Failed checks in the session file. The figures are kept "
              "and shown;\n  route A keeps them the same way after its last retry:")
        for error in session.validation_errors:
            print(f"    {error}")
    print("  No API call was made and no pickle cache was read or written.")

    source_label = (
        f"Claude Code session file {session.session_file}. The figures were read "
        f"by {resolution.model} (as the session declared it; the model ID cannot "
        f"be verified) in a Claude Code session, from "
        + ", ".join(Path(r.plan.pdf_path).name for r in session.filings)
        + ", each verified against its recorded sha256. No API call was made."
    )
    identified_by = (
        f"a Claude Code session, model {resolution.model} as declared"
    )
    return session.financials, session.non_recurring, source_label, identified_by


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    global _t0
    _t0 = time.time()

    args = parse_args()
    if args.session_file is not None:
        financials, adjustments, cache_label, identified_by = (
            _extract_from_session_file(args)
        )
    else:
        financials, adjustments, cache_label = _extract_via_api(args)
        identified_by = args.provider.upper()

    years = financials.years
    print(f"  Ticker: {financials.ticker}  |  Company: {financials.company_name}")
    print(f"  Years extracted: {years}")

    # ===== STAGE 2: EXTRACTED F/S (Pass 1 output) ===========================
    _step(2, "Displaying extracted financial statements")
    print_extracted_financials(financials)

    # ===== STAGE 3: NON-RECURRING ITEMS (Pass 2 output) =====================
    _step(3, "Displaying non-recurring items")
    # The partition happens BEFORE normalisation and outside it: rule 1 puts the
    # decision in analysis/, and normalize_financials keeps the signature its
    # tests were written against. Only `applied` reaches the arithmetic.
    applied, excluded = partition_by_confidence(adjustments)
    print_non_recurring_items(applied, identified_by)
    print_excluded_non_recurring_items(excluded)

    # ===== STAGE 4: NORMALIZE (GAAP -> Non-GAAP) ============================
    _step(4, "Normalizing financials (GAAP -> Non-GAAP)")
    adjusted = normalize_financials(financials, applied)
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
        zero_debt_confirmed=overrides.zero_debt_confirmed,
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
    # ===== FINAL SUMMARY ========================================================
    _section("FINAL VALUATION SUMMARY")
    print(f"  Ticker:             {args.ticker}")
    print(f"  Company:            {args.company_name}")
    print(f"  Current Price:      ${price_data.current_price:>11.2f}")
    print(f"  Implied Price:      ${dcf_result.implied_share_price:>11.2f}")
    # The headline figure says what it excludes, beside itself. A share price
    # that silently differs from the one a reader would compute from the printed
    # adjustments is the defect this exclusion exists to fix, wearing a
    # different face.
    if excluded:
        withheld = sum(i.adjusted_impact for i in excluded)
        print(f"  This price EXCLUDES {len(excluded)} low-confidence "
              f"non-recurring item(s)")
        print(f"  worth {withheld:+,.0f}M of earnings adjustment in total "
              f"(listed in full above).")

    direction = "UPSIDE" if dcf_result.upside_downside >= 0 else "DOWNSIDE"
    print(f"  Valuation:          {direction} of {dcf_result.upside_downside:>+10.1f}%")
    print(f"  {'=' * 42}")

    # Rule 6, gathered. The three numbers above that were neither read from the
    # filing nor derived by formula from one, plus where the filing figures
    # themselves came from on this run. Each is printed in full beside its own
    # figure earlier; this block exists so that a reader who scrolls to the
    # answer still meets them.
    _section("WHAT IN THIS VALUATION WAS NOT MEASURED")
    print("  Extraction source")
    print(_wrap_label(cache_label, indent="    "))
    print("\n  Risk-free rate")
    print(_wrap_label(f"{capm_result.risk_free_rate:.2%} — "
                      f"{capm_result.risk_free_rate_source}", indent="    "))
    print("\n  Beta")
    print(_wrap_label(f"{capm_result.beta:.3f} — {capm_result.beta_source}",
                      indent="    "))
    print(_wrap_label(f"reliability: {capm_result.beta_reliability}", indent="    "))
    print("\n  Cost of debt (pre-tax)")
    print(_wrap_label(f"{wacc_result.cost_of_debt:.2%} — "
                      f"{wacc_result.cost_of_debt_source}", indent="    "))
    # What was left out is as much a fact about this price as what was assumed,
    # so it is repeated here for the reader who scrolled past stage 3 to the
    # answer. Same reason the three labels above are repeated.
    print("\n  Non-recurring items excluded")
    if excluded:
        print(_wrap_label(
            f"{len(excluded)} item(s) the model tagged LOW confidence were NOT "
            f"applied to the financial statements, on the user's decision of "
            f"2026-09-22. Each is listed above with its year, amount, line "
            f"item, direction, description and cited source.", indent="    "))
        for item in excluded:
            print(_wrap_label(
                f"[{item.year}] {item.adjusted_impact:+,.0f}M on "
                f"{item.line_item} — {item.description} "
                f"(source: {item.source if item.source else 'none cited'})",
                indent="    "))
    else:
        print(_wrap_label(
            "none — every item the model identified carried medium or high "
            "confidence and was applied.", indent="    "))
    print(f"\n  {'=' * 42}")
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
