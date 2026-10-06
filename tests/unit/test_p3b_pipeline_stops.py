"""`P3b-pipeline-stops`: the yearless-filing stop (item 49) and the CLI's debt figure (item 72).

Every expected value below exists before the code runs. There are three kinds and
each assertion says which it is:

* **The stated contract.** `parse_pdf_args`' docstring says a bare path is year 0 and
  that a year is never read from the file name there; `require_fiscal_year_per_filing`'s
  contract is "with more than one filing, every filing needs a fiscal year above 0,
  and the stop names EVERY filing that has none". A list of file names is not a
  computed number: the expected message content is the input list itself.
* **A figure read off a filing page.** Walmart's fiscal 2026 balance sheet, 10-K
  page 22 — the same five rows `tests/unit/test_p14d_finance_leases.py` builds:
  short-term borrowings 6,596 + long-term debt due within one year 3,542 + finance
  lease obligations due within one year 856 = 10,994; long-term debt 34,624 +
  long-term finance lease obligations 5,905 = 40,529. Hand sum **51,523**.
* **Hand arithmetic and a closed-form identity.** The share count and the stub price
  below are chosen so that total capital is exactly 100,000: market cap = 48,477 x 1.00
  = 48,477, and 48,477 + 51,523 = 100,000, so the debt weight is exactly 0.51523 and
  the equity weight exactly 0.48477. Both are checked against the identity
  D / (E + D) as well as against the decimal.

**No test here asserts a fallback**, and none asserts a figure this repository's code
produced. No test opens a PDF, reads `10K_filings/` or `extractions/`, calls a model or
reaches the network: `_no_socket` (tests/conftest.py) is applied to every test in the
file, each extractor is replaced by a recorder, and `fetch_price_data` is a stub.
"""

from __future__ import annotations

import builtins
import dataclasses
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pdfplumber
import pytest
import yfinance

import cli
import pipeline
from api import routes_valuation
from ingestion.filings import parse_pdf_args, require_fiscal_year_per_filing
from ingestion.price_fetcher import PriceData
from models.financial_statements import (
    BalanceSheet,
    FinancialStatements,
    IncomeStatement,
)
from models.valuation import ProjectionAssumptions
from tests.unit._fiscal_year_stub import stub_evidence_reader
from tests.unit._session_route_helpers import (
    error_text,
    open_closed_client,
    text_of,
)

pytestmark = pytest.mark.usefixtures("_no_socket")


# ===========================================================================
# Backlog item 49 — a filing with no fiscal year stops and is named
# ===========================================================================
#
# Behaviour 1. The contract: the message names EVERY yearless filing, not the
# first. Two of three are yearless, so both their names are expected in the
# message and the name of the filing that HAS a year is not.


def test_require_fiscal_year_names_every_yearless_filing_not_only_the_first() -> None:
    with pytest.raises(ValueError) as raised:
        require_fiscal_year_per_filing([(0, "a.pdf"), (2025, "b.pdf"), (0, "c.pdf")])

    message = str(raised.value)
    assert "a.pdf" in message
    assert "c.pdf" in message
    # The filing that has a year is not one of the offenders, so it is not named.
    assert "b.pdf" not in message


def test_require_fiscal_year_names_the_only_yearless_filing() -> None:
    """Criterion 1 of the code unit: two filings, one yearless, named."""
    with pytest.raises(ValueError) as raised:
        require_fiscal_year_per_filing([(0, "a.pdf"), (2025, "b.pdf")])
    message = str(raised.value)
    assert "a.pdf" in message
    assert "b.pdf" not in message


def test_the_stop_gives_each_entry_point_the_remedy_that_works_there() -> None:
    """Round 2, finding F1: one message serves two entry points, so each remedy is placed.

    The two facts, each read off the code and not off this message:
    `parse_pdf_args` gives a bare path year 0 and never reads the file name for a
    year, so only `YEAR:PATH` works on the command line; `api/routes_upload.py`
    takes every year from the file name and offers no way to type one, so only
    renaming works there.
    """
    with pytest.raises(ValueError) as raised:
        require_fiscal_year_per_filing([(0, "a.pdf"), (2025, "b.pdf")])

    lines = str(raised.value).splitlines()
    command_line = [line for line in lines if "command line" in line]
    web_upload = [line for line in lines if "web upload" in line]
    assert len(command_line) == 1, lines
    assert len(web_upload) == 1, lines

    # The remedy that works on the command line, on the command line's line only.
    assert "YEAR:PATH" in command_line[0]
    assert "YEAR:PATH" not in web_upload[0]
    # The remedy that works on the upload page, on the upload page's line only.
    assert "rename the file" in web_upload[0]
    assert "rename the file" not in command_line[0]


def test_a_bare_path_whose_name_carries_a_year_is_still_yearless() -> None:
    """Round 2's criterion 18, as a unit test: the file NAME is not a year here.

    `parse_pdf_args` gives every bare path year 0 whatever it is called, so two
    files already named `ABBV_10-K_2025-12-31.pdf` and `ABBV_10-K_2024-12-31.pdf`
    reach this stop. Expected from that contract: both names in the message.
    """
    named = [(0, "ABBV_10-K_2025-12-31.pdf"), (0, "ABBV_10-K_2024-12-31.pdf")]
    with pytest.raises(ValueError) as raised:
        require_fiscal_year_per_filing(named)
    message = str(raised.value)
    assert "ABBV_10-K_2025-12-31.pdf" in message
    assert "ABBV_10-K_2024-12-31.pdf" in message


def test_parse_pdf_args_does_not_read_a_year_out_of_a_file_name(
    tmp_path: Path, pdf_opens: list[str],
) -> None:
    """Round 2: the test above hands `parse_pdf_args`' contract to the function it tests.

    It builds the `(0, name)` pairs itself, so it assumes the very thing it
    claims — that a year in the file name does not count. This one gives
    `parse_pdf_args` the two names, so the 0 is the parser's: `^(\\d{4}):(.+)$`
    (`ingestion/filings.py:526`) matches a YEAR: PREFIX and nothing else, and a
    path that does not match becomes `(0, s)`. Expected from that contract:
    both files named in the stop, and no PDF opened.
    """
    paths = []
    for name in ("ABBV_10-K_2025-12-31.pdf", "ABBV_10-K_2024-12-31.pdf"):
        path = tmp_path / name
        path.write_bytes(b"%PDF-1.4 not a real filing")
        paths.append(str(path))

    with pytest.raises(ValueError) as raised:
        parse_pdf_args(paths, "ABBV")

    message = str(raised.value)
    assert "ABBV_10-K_2025-12-31.pdf" in message
    assert "ABBV_10-K_2024-12-31.pdf" in message
    assert pdf_opens == []


# Behaviour 2. The contract names three inputs that return: one filing with year 0
# (a bare path means "every year this filing presents"), several filings that all
# have a year, and an empty list (both callers stop on empty themselves).


def test_require_fiscal_year_allows_one_filing_with_no_year() -> None:
    assert require_fiscal_year_per_filing([(0, "a.pdf")]) is None


def test_require_fiscal_year_allows_several_filings_that_all_have_a_year() -> None:
    assert require_fiscal_year_per_filing([(2024, "a.pdf"), (2025, "b.pdf")]) is None


def test_require_fiscal_year_allows_an_empty_list() -> None:
    """The function does not own the empty rule: `parse_pdf_args` and `_run_extraction` do."""
    assert require_fiscal_year_per_filing([]) is None


# The two tests below close the premise the one above rests on. Returning for an
# empty list is only not a rule-3 fallback if the caller stops, so the caller is
# asked. Expected from the two call sites: `cli.py:185` calls `p.error(...)`,
# which argparse turns into `SystemExit(2)`; `api/routes_valuation.py:189` raises
# `ValueError` naming `files`.


def test_the_cli_stops_before_the_fiscal_year_rule_when_no_pdf_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["cli.py", "-t", "TESTCO"])

    with pytest.raises(SystemExit) as raised:
        cli.parse_args()

    assert raised.value.code == 2


def test_the_web_route_stops_before_the_fiscal_year_rule_when_files_names_none(
    route_extractor_calls: dict[str, list[Any]],
) -> None:
    with pytest.raises(ValueError) as raised:
        routes_valuation._run_extraction(
            files=",",
            file_path="",
            session_file="",
            ticker="T",
            company_name="T",
        )

    assert "files" in str(raised.value)
    assert route_extractor_calls == {"single": [], "multi": []}


# Behaviour 3. "A fiscal year above 0" is the rule, so a negative year is no year.


@pytest.mark.parametrize("year", [-1, -2025])
def test_require_fiscal_year_treats_a_negative_year_as_no_year(year: int) -> None:
    with pytest.raises(ValueError) as raised:
        require_fiscal_year_per_filing([(year, "a.pdf"), (2025, "b.pdf")])
    assert "a.pdf" in str(raised.value)


# Behaviour 4. `parse_pdf_args` with two bare paths stops before any PDF is opened.


@pytest.fixture
def pdf_opens(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every `.pdf` a test opens, by either door `read_fiscal_year_evidence` uses.

    `pdfplumber.open` is recorded and refused; `builtins.open` is recorded and
    delegated, so nothing else in the run breaks. The absence of an error is not
    the measurement -- the empty list is.
    """
    opened: list[str] = []
    real_open = builtins.open

    def _recording_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        if str(file).lower().endswith(".pdf"):
            opened.append(str(file))
        return real_open(file, *args, **kwargs)

    def _recorded_pdfplumber(path: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(path))
        raise AssertionError(f"pdfplumber.open was called: {path!r}")

    monkeypatch.setattr(builtins, "open", _recording_open)
    monkeypatch.setattr(pdfplumber, "open", _recorded_pdfplumber)
    return opened


def test_parse_pdf_args_stops_on_two_bare_paths_before_opening_a_pdf(
    tmp_path: Path, pdf_opens: list[str],
) -> None:
    """Both files exist and hold bytes, so an open would succeed. None happens."""
    first = tmp_path / "a.pdf"
    second = tmp_path / "c.pdf"
    for path in (first, second):
        path.write_bytes(b"%PDF-1.4 not a real filing")

    with pytest.raises(ValueError) as raised:
        parse_pdf_args([str(first), str(second)], "TESTCO")

    message = str(raised.value)
    assert "a.pdf" in message
    assert "c.pdf" in message
    assert pdf_opens == []


# Behaviour 5. `cli.main` with two bare paths: non-zero exit, `ERROR:`, both names,
# and neither extractor called.


@pytest.fixture
def cli_extractor_calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """`cli.extract_financials` / `cli.extract_multi_year`, replaced by recorders.

    Each records what it was given and returns hand-built statements, so a test can
    assert on the argument rather than on the absence of a crash.
    """
    calls: dict[str, list[Any]] = {"single": [], "multi": []}

    def _single(pdf_path: str, ticker: str, company_name: str, **kwargs: Any) -> Any:
        calls["single"].append(pdf_path)
        return _financials(), []

    def _multi(filings: Any, ticker: str = "", company_name: str = "", **kwargs: Any) -> Any:
        calls["multi"].append(list(filings))
        return _financials(), []

    def _single_kw(**kwargs: Any) -> Any:
        return _single(kwargs["pdf_path"], kwargs.get("ticker", ""), kwargs.get("company_name", ""))

    def _multi_kw(**kwargs: Any) -> Any:
        return _multi(kwargs["filings"], kwargs.get("ticker", ""), kwargs.get("company_name", ""))

    monkeypatch.setattr(cli, "extract_financials", _single_kw)
    monkeypatch.setattr(cli, "extract_multi_year", _multi_kw)
    return calls


def test_cli_main_stops_on_two_bare_paths_and_names_both_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cli_extractor_calls: dict[str, list[Any]],
    pdf_opens: list[str],
) -> None:
    """Exit is non-zero: `SystemExit` carries a string, which CPython reports as status 1.

    `_extract_via_api` turns `parse_pdf_args`' `ValueError` into
    `SystemExit(f"ERROR: {exc}")` (`cli.py:828`), so the expected code is that
    string, and `sys.exit`'s documented contract makes a string code exit status 1.

    Round 2: this called `runpy.run_path(cli.__file__, run_name="__main__")`.
    `runpy` executes the file into a FRESH namespace, so `cli.extract_financials`
    monkeypatched on the imported module was not the name that namespace bound,
    and `cli_extractor_calls == {...: []}` was true whatever the fresh copy did.
    `cli.main()` is the same entry (`cli.py:1133`, `if __name__ == "__main__"`),
    and the recorders are the names it resolves, so the empty lists are a
    measurement.
    """
    first = tmp_path / "a.pdf"
    second = tmp_path / "c.pdf"
    for path in (first, second):
        path.write_bytes(b"%PDF-1.4 not a real filing")
    monkeypatch.setattr(
        "sys.argv", ["cli.py", str(first), str(second), "-t", "TESTCO"],
    )

    with pytest.raises(SystemExit) as raised:
        cli.main()

    code = raised.value.code
    assert isinstance(code, str)
    assert code != 0
    assert code.startswith("ERROR:")
    assert "a.pdf" in code
    assert "c.pdf" in code
    assert cli_extractor_calls == {"single": [], "multi": []}
    assert pdf_opens == []


# Behaviour 6. `_run_extraction(files='0:a.pdf,2025:b.pdf')` stops, names `a.pdf`,
# and calls neither extractor.


@pytest.fixture
def route_extractor_calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """`routes_valuation.extract_financials` / `extract_multi_year`, as recorders."""
    calls: dict[str, list[Any]] = {"single": [], "multi": []}

    def _single(pdf_path: str, ticker: str = "", company_name: str = "", **kwargs: Any) -> Any:
        calls["single"].append(pdf_path)
        return _financials(), []

    def _multi(filings: Any, ticker: str = "", company_name: str = "", **kwargs: Any) -> Any:
        calls["multi"].append(list(filings))
        return _financials(), []

    monkeypatch.setattr(routes_valuation, "extract_financials", _single)
    monkeypatch.setattr(routes_valuation, "extract_multi_year", _multi)
    return calls


def test_run_extraction_stops_on_a_yearless_filing_and_names_it(
    route_extractor_calls: dict[str, list[Any]],
) -> None:
    with pytest.raises(ValueError) as raised:
        routes_valuation._run_extraction(
            files="0:a.pdf,2025:b.pdf",
            file_path="",
            session_file="",
            ticker="T",
            company_name="T",
        )

    message = str(raised.value)
    assert "a.pdf" in message
    assert "b.pdf" not in message
    assert route_extractor_calls == {"single": [], "multi": []}


# Behaviour 7. The same `files` value on each page: HTTP 200 (backlog item 8 owns the
# status code) and the file name in the body.


def test_the_stop_reaches_the_assumptions_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    client = open_closed_client(monkeypatch, tmp_path)
    calls = route_extractor_recorders(monkeypatch)

    response = client.get(
        "/assumptions", params={"ticker": "T", "files": "0:a.pdf,2025:b.pdf"},
    )

    assert response.status_code == 200
    shown = error_text(response.text)
    assert shown is not None
    assert "a.pdf" in shown
    assert calls == {"single": [], "multi": []}


def test_the_stop_reaches_the_valuation_result_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    client = open_closed_client(monkeypatch, tmp_path)
    calls = route_extractor_recorders(monkeypatch)

    response = client.post(
        "/valuation",
        data=_VALUATION_FORM_FOR_FILES | {"files": "0:a.pdf,2025:b.pdf"},
    )

    assert response.status_code == 200
    body = text_of(response.text)
    assert "a.pdf" in body
    assert "Implied Share Price" not in body
    assert calls == {"single": [], "multi": []}


# Behaviour 8. The filing that used to be dropped now reaches the extractor: three
# filings, all with a year, all three given to `extract_multi_year`, in both entry
# points. Expected value: the input list itself.


def test_three_filings_with_years_all_reach_extract_multi_year_in_the_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cli_extractor_calls: dict[str, list[Any]],
) -> None:
    paths = _three_pdfs(tmp_path)
    stub_evidence_reader(
        monkeypatch, {"a.pdf": 2023, "b.pdf": 2024, "c.pdf": 2025},
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli.py",
            f"2023:{paths['a.pdf']}",
            f"2024:{paths['b.pdf']}",
            f"2025:{paths['c.pdf']}",
            "-t", "TESTCO",
        ],
    )
    args = cli.parse_args()

    cli._extract_via_api(args)

    assert cli_extractor_calls["single"] == []
    assert cli_extractor_calls["multi"] == [
        [
            (2023, str(paths["a.pdf"])),
            (2024, str(paths["b.pdf"])),
            (2025, str(paths["c.pdf"])),
        ],
    ]


def test_three_filings_with_years_all_reach_extract_multi_year_in_the_web_route(
    monkeypatch: pytest.MonkeyPatch,
    route_extractor_calls: dict[str, list[Any]],
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "placeholder-not-a-live-key")

    routes_valuation._run_extraction(
        files="2023:a.pdf,2024:b.pdf,2025:c.pdf",
        file_path="",
        session_file="",
        ticker="T",
        company_name="T",
    )

    assert route_extractor_calls["single"] == []
    assert route_extractor_calls["multi"] == [
        [(2023, "a.pdf"), (2024, "b.pdf"), (2025, "c.pdf")],
    ]


# Behaviour 9. One bare path still reaches `extract_financials`, with the path given.
# This unit changed nothing for one filing.


def test_one_bare_path_still_reaches_extract_financials_in_the_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cli_extractor_calls: dict[str, list[Any]],
) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 not a real filing")
    monkeypatch.setattr("sys.argv", ["cli.py", str(pdf), "-t", "TESTCO"])
    args = cli.parse_args()

    cli._extract_via_api(args)

    assert cli_extractor_calls["multi"] == []
    assert cli_extractor_calls["single"] == [str(pdf)]


def test_one_bare_path_still_reaches_extract_financials_in_the_web_route(
    monkeypatch: pytest.MonkeyPatch,
    route_extractor_calls: dict[str, list[Any]],
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "placeholder-not-a-live-key")

    routes_valuation._run_extraction(
        files="0:a.pdf",
        file_path="",
        session_file="",
        ticker="T",
        company_name="T",
    )

    assert route_extractor_calls["multi"] == []
    assert route_extractor_calls["single"] == ["a.pdf"]


# The other half of behaviour 8: the `valid = [(y, p) for y, p in filings if y > 0]`
# filter is gone from both entry points, so neither can drop a filing from the list it
# was handed. Both entry points now stop before that branch
# (`require_fiscal_year_per_filing`), so the branch is reached below with the guard
# bypassed -- a stub parser in the CLI, a direct call in the web route. That is
# deliberate: the requirement is "no entry point silently drops a filing", and a
# requirement no test can reach is a requirement a later edit can revert in silence.
# Neither test asserts what the dropped filing used to do; each asserts that the list
# given is the list extracted.


def test_the_cli_never_drops_a_filing_from_the_list_it_was_given(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cli_extractor_calls: dict[str, list[Any]],
) -> None:
    paths = _three_pdfs(tmp_path)
    given = [(0, str(paths["a.pdf"])), (2025, str(paths["b.pdf"]))]
    monkeypatch.setattr(cli, "parse_pdf_args", lambda pdfs, ticker=None: list(given))
    monkeypatch.setattr("sys.argv", ["cli.py", str(paths["a.pdf"]), "-t", "TESTCO"])
    args = cli.parse_args()

    cli._extract_via_api(args)

    assert cli_extractor_calls["single"] == []
    assert cli_extractor_calls["multi"] == [given]


def test_the_web_route_never_drops_a_filing_from_the_list_it_was_given(
    route_extractor_calls: dict[str, list[Any]],
) -> None:
    given = [(0, "a.pdf"), (2025, "b.pdf")]

    routes_valuation._extract_from_files(list(given), "T", "T")

    assert route_extractor_calls["single"] == []
    assert route_extractor_calls["multi"] == [given]


# ===========================================================================
# Backlog item 72 — the CLI prints the debt balance WACC used
# ===========================================================================
#
# Walmart's fiscal 2026 balance sheet, 10-K page 22. The rows and their mapping are
# the ones `tests/unit/test_p14d_finance_leases.py` builds from the same page:
#
#   Short-term borrowings                             6,596  -> short_term_debt
#   Long-term debt due within one year                3,542  -> short_term_debt
#   Finance lease obligations due within one year       856  -> short_term_debt
#   Long-term debt                                   34,624  -> long_term_debt
#   Long-term finance lease obligations                5,905  -> long_term_debt
#
#   short_term_debt         = 6,596 + 3,542 + 856   = 10,994
#   current_portion_lt_debt =                           0     (every current debt row
#                                                              above maps to
#                                                              short_term_debt)
#   long_term_debt          = 34,624 + 5,905        = 40,529
#   total_debt              = 10,994 + 0 + 40,529   = 51,523
#
# The share count and the stub price are chosen so the capital total is round:
#   market cap   = 48,477 shares x $1.00            = 48,477
#   total capital= 48,477 + 51,523                  = 100,000
#   debt weight  = 51,523 / 100,000                 = 0.51523
#   equity weight= 48,477 / 100,000                 = 0.48477

WMT_TICKER = "WMT"
WMT_YEAR = 2026
WMT_SHORT_TERM_DEBT = 6596.0 + 3542.0 + 856.0
WMT_LONG_TERM_DEBT = 34624.0 + 5905.0
WMT_TOTAL_DEBT = 51523.0
WMT_SHARES = 48477.0
STUB_PRICE = 1.0
WMT_MARKET_CAP = 48477.0


def _walmart_balance_sheet() -> BalanceSheet:
    return BalanceSheet(
        year=WMT_YEAR,
        short_term_debt=WMT_SHORT_TERM_DEBT,
        current_portion_lt_debt=0.0,
        long_term_debt=WMT_LONG_TERM_DEBT,
        # Not part of this test's subject and not read off the filing: written as
        # explicit inputs, so net debt is the debt balance itself.
        cash_and_equivalents=0.0,
        short_term_investments=0.0,
        noncontrolling_interest_nonredeemable=0.0,
        noncontrolling_interest_redeemable=0.0,
        printed_unit_in_millions=1.0,
    )


def _walmart_income_statement() -> IncomeStatement:
    # Round inputs, not filing figures: revenue 100,000, COGS 70,000, SG&A 10,000
    # -> EBIT 20,000. Interest expense 2,600 so the cost of debt is measured from
    # the filing rather than substituted (rule 6); it moves no figure asserted here.
    return IncomeStatement(
        year=WMT_YEAR,
        revenue=100000.0,
        cost_of_revenue=70000.0,
        sga=10000.0,
        interest_expense=2600.0,
        tax_expense=4000.0,
        diluted_shares_outstanding=WMT_SHARES,
    )


def _walmart_financials(with_balance_sheet: bool = True) -> FinancialStatements:
    return FinancialStatements(
        ticker=WMT_TICKER,
        company_name="Walmart Inc.",
        income_statements=[_walmart_income_statement()],
        balance_sheets=[_walmart_balance_sheet()] if with_balance_sheet else [],
    )


def _overrides() -> ProjectionAssumptions:
    """Every projection input supplied, so nothing is derived from history."""
    return ProjectionAssumptions(
        projection_years=1,
        terminal_growth_rate=0.02,
        revenue_growth_rates=[0.10],
        operating_margin=0.20,
        tax_rate=0.25,
        capex_pct_revenue=0.05,
        da_pct_revenue=0.05,
        nwc_pct_revenue=0.01,
        risk_free_rate=0.04,
        equity_risk_premium=0.06,
        beta_override=1.0,
        beta_lookback_years=3,
        return_frequency="daily",
    )


def _price_data(ticker: str = WMT_TICKER) -> PriceData:
    return PriceData(
        ticker=ticker,
        stock_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        dates=pd.DatetimeIndex(pd.date_range("2026-01-31", periods=3, freq="D")),
        current_price=STUB_PRICE,
        periods_per_year=12,
    )


@pytest.fixture
def price_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int, str]]:
    calls: list[tuple[str, int, str]] = []

    def _stub(ticker: str, lookback_years: int, frequency: str) -> PriceData:
        calls.append((ticker, lookback_years, frequency))
        return _price_data(ticker)

    monkeypatch.setattr(pipeline, "fetch_price_data", _stub)
    return calls


@pytest.fixture
def ticker_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []

    def _recorded(*args: object, **kwargs: object) -> None:
        calls.append(args)
        raise AssertionError(f"yfinance.Ticker was called: {args!r}")

    monkeypatch.setattr(yfinance, "Ticker", _recorded)
    return calls


# Behaviour 10. A missing balance sheet for the latest year stops, names the field,
# the ticker and the year, and `fetch_price_data` is not called. The twin: the same
# statements WITH a balance sheet do reach `fetch_price_data`.


def test_value_company_stops_on_a_missing_balance_sheet_before_any_market_call(
    price_calls: list[tuple[str, int, str]], ticker_calls: list[tuple[Any, ...]],
) -> None:
    with pytest.raises(ValueError) as raised:
        pipeline.value_company(
            _walmart_financials(with_balance_sheet=False),
            _overrides(),
            ticker=WMT_TICKER,
            lookback_years=3,
            frequency="daily",
        )

    message = str(raised.value)
    assert "balance_sheet" in message
    assert WMT_TICKER in message
    assert str(WMT_YEAR) in message
    assert price_calls == []
    assert ticker_calls == []


def test_the_same_statements_with_a_balance_sheet_do_reach_fetch_price_data(
    price_calls: list[tuple[str, int, str]], ticker_calls: list[tuple[Any, ...]],
) -> None:
    """The twin of the stop above: it is the balance sheet that stopped the run."""
    pipeline.value_company(
        _walmart_financials(),
        _overrides(),
        ticker=WMT_TICKER,
        lookback_years=3,
        frequency="daily",
    )

    assert price_calls == [(WMT_TICKER, 3, "daily")]
    assert ticker_calls == []


def test_valuation_run_requires_total_debt_and_a_balance_sheet_with_no_default() -> None:
    """The contract `ValuationRun`'s docstring states, as a test.

    Two sentences of `pipeline.ValuationRun`: "`latest_balance_sheet` ... is never
    `None`" and "`total_debt` is that balance sheet's debt balance ... carried here
    rather than re-read by each caller", closing with "Every field is required.
    None is defaulted."

    Round 2 added this because mutation 17 -- the conditional zero put back in
    stage 8, with `latest_balance_sheet` optional again -- leaves
    `test_cli_stage_8_prints_the_debt_balance_wacc_used` green: when the balance
    sheet IS there, `run.total_debt` and `latest_bs.total_debt if latest_bs else 0`
    are the same figure, so the print test cannot tell them apart. The field
    itself is what the mutation deletes, so the field itself is asserted.

    Expected, from that contract and from `dataclasses.MISSING`'s meaning: the
    field names include `total_debt` and `latest_balance_sheet`, the annotation
    of `latest_balance_sheet` admits no `None`, and no field carries a default.
    """
    by_name = {f.name: f for f in dataclasses.fields(pipeline.ValuationRun)}

    assert "total_debt" in by_name
    assert "latest_balance_sheet" in by_name
    assert "None" not in str(by_name["latest_balance_sheet"].type)
    for name, field in by_name.items():
        assert field.default is dataclasses.MISSING, name
        assert field.default_factory is dataclasses.MISSING, name


# Behaviour 11. `ValuationRun.total_debt` is the hand sum of the debt lines.


def test_total_debt_is_the_hand_sum_of_walmarts_debt_lines(
    price_calls: list[tuple[str, int, str]], ticker_calls: list[tuple[Any, ...]],
) -> None:
    """10-K page 22: 6,596 + 3,542 + 856 = 10,994; 34,624 + 5,905 = 40,529.

    10,994 + 0 + 40,529 = 51,523.
    """
    assert WMT_SHORT_TERM_DEBT == 10994.0
    assert WMT_LONG_TERM_DEBT == 40529.0

    run = pipeline.value_company(
        _walmart_financials(),
        _overrides(),
        ticker=WMT_TICKER,
        lookback_years=3,
        frequency="daily",
    )

    assert run.total_debt == pytest.approx(51523.0)


# Behaviour 13. The debt weight identity, from the same run: the figure carried is
# the figure weighted.


def test_the_debt_weight_is_total_debt_over_market_cap_plus_total_debt(
    price_calls: list[tuple[str, int, str]], ticker_calls: list[tuple[Any, ...]],
) -> None:
    """market cap = 48,477 x $1.00 = 48,477; 48,477 + 51,523 = 100,000.

    debt weight   = 51,523 / 100,000 = 0.51523
    equity weight = 48,477 / 100,000 = 0.48477
    """
    run = pipeline.value_company(
        _walmart_financials(),
        _overrides(),
        ticker=WMT_TICKER,
        lookback_years=3,
        frequency="daily",
    )

    assert run.market_cap == pytest.approx(48477.0)
    assert run.wacc_result.debt_weight == pytest.approx(0.51523)
    assert run.wacc_result.equity_weight == pytest.approx(0.48477)
    # The identity, on the run's own figures.
    assert run.wacc_result.debt_weight == pytest.approx(
        run.total_debt / (run.market_cap + run.total_debt),
    )


# Behaviour 12. Stage 8 prints that same figure.


def test_cli_stage_8_prints_the_debt_balance_wacc_used(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    price_calls: list[tuple[str, int, str]],
    ticker_calls: list[tuple[Any, ...]],
) -> None:
    """The extraction is a boundary and is stubbed; everything after it is the real code.

    Expected: the WACC block shows the 51,523 derived on page 22 above, and the
    48,477 market cap, and no zero debt balance.
    """
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 not a real filing")

    def _stub_extraction(args: Any) -> tuple[Any, list[Any], str]:
        return _walmart_financials(), [], "stubbed extraction for the test"

    monkeypatch.setattr(cli, "_extract_via_api", _stub_extraction)
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli.py", str(pdf), "-t", WMT_TICKER,
            "--projection-years", "1",
            "--terminal-growth", "0.02",
            "--revenue-growth", "0.10",
            "--operating-margin", "0.20",
            "--tax-rate", "0.25",
            "--da-pct", "0.05",
            "--capex-pct", "0.05",
            "--nwc-pct", "0.01",
            "--risk-free-rate", "0.04",
            "--equity-risk-premium", "0.06",
            "--beta", "1.0",
            "--lookback-years", "3",
            "--frequency", "daily",
        ],
    )
    capsys.readouterr()

    cli.main()

    out = capsys.readouterr().out
    wacc_block = out[out.index("WACC") :]
    # The format is `cli.print_wacc`'s; the figure is the hand sum above.
    assert f"Total debt:           ${51523.0:>12,.0f}M" in wacc_block
    assert f"Market cap:           ${48477.0:>12,.0f}M" in wacc_block
    assert f"Total debt:           ${0.0:>12,.0f}M" not in wacc_block
    assert price_calls == [(WMT_TICKER, 3, "daily")]
    assert ticker_calls == []


# ---------------------------------------------------------------------------
# Small helpers used above
# ---------------------------------------------------------------------------

_VALUATION_FORM_FOR_FILES: dict[str, str] = {
    "ticker": "T",
    "company_name": "T",
    "files": "",
    "session_file": "",
    "projection_years": "1",
    "terminal_growth_rate": "2.0",
    "revenue_growth": "10",
    "operating_margin": "20",
    "tax_rate": "25",
    "da_pct": "10",
    "capex_pct": "5",
    "nwc_pct": "2",
    "risk_free_rate": "4.0",
    "equity_risk_premium": "6",
    "beta_override": "1.0",
    "cost_of_debt_override": "6",
    "beta_lookback_years": "5",
    "return_frequency": "monthly",
}


def _financials() -> FinancialStatements:
    """Statements a stubbed extractor hands back. No test asserts a figure in them."""
    return FinancialStatements(
        ticker="TESTCO",
        company_name="Test Co",
        income_statements=[_walmart_income_statement()],
        balance_sheets=[_walmart_balance_sheet()],
    )


def _three_pdfs(directory: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        path = directory / name
        path.write_bytes(b"%PDF-1.4 not a real filing " + name.encode())
        paths[name] = path
    return paths


def route_extractor_recorders(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """The route recorders, as a plain function for the two client tests.

    They run after `open_closed_client`, which installs refusing stubs of its own;
    these replace them with recorders whose message names no path, so a page that
    showed a file name can only have got it from the stop.
    """
    calls: dict[str, list[Any]] = {"single": [], "multi": []}

    def _single(*args: Any, **kwargs: Any) -> Any:
        calls["single"].append(args)
        raise AssertionError("an extractor was called")

    def _multi(*args: Any, **kwargs: Any) -> Any:
        calls["multi"].append(args)
        raise AssertionError("an extractor was called")

    monkeypatch.setattr(routes_valuation, "extract_financials", _single)
    monkeypatch.setattr(routes_valuation, "extract_multi_year", _multi)
    return calls
