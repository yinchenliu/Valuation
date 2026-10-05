"""`pipeline.py` (P3a-one-pipeline): the one valuation sequence both entry points call.

What this file locks, each from an expected value that exists before the code runs:

1. `adjust_financials` -- a `high` and a `medium` item move the income statement,
   a `low` item does not, and the raw statements are not mutated. Hand arithmetic.
2. `value_company`'s wiring -- the share count is the filing's (market cap = stub
   price x filing shares), the overrides reach CAPM (cost of equity = rf + beta x ERP),
   and the DCF is the one `run_dcf` gives on the result's own projection and WACC.
   Hand arithmetic, and one closed-form identity (WACC = cost of equity when the
   debt weight is 0).
3. The share count stop -- a latest-year diluted share count of 0, a negative number,
   NaN or infinity raises `ValueError` naming `diluted_shares`, the ticker and the
   year, before `fetch_price_data` and with no `yfinance.Ticker` call. The same stop
   reaches the CLI (exit 1, the message on stderr) and the web result page.
4. One price for both entry points -- `cli.main` and `POST /valuation`, on one session
   file with the same overrides and the same stubbed market data, report the same
   implied share price. The identity the unit exists for.

**No test here asserts a fallback.** No test reaches the network or a model: every
`fetch_price_data` is a stub on `pipeline`, `yfinance.Ticker` is replaced with a
function that records the call and raises, and `socket` connects are refused.
Nothing reads `extractions/` or `10K_filings/`; the session file and its PDF are
written under `tmp_path` by `tests/unit/_session_route_helpers.py`.
"""

from __future__ import annotations

import math
import runpy
import socket
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yfinance

import cli
import pipeline
from analysis.dcf import run_dcf
from ingestion.price_fetcher import PriceData
from models.financial_statements import (
    BalanceSheet,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)
from models.valuation import ProjectionAssumptions
from tests.unit._session_route_helpers import (
    TICKER as SESSION_TICKER,
)
from tests.unit._session_route_helpers import (
    VALUATION_FORM,
    error_text,
    install_price_stub,
    make_pdf,
    open_closed_client,
    session_dict,
    text_of,
    write_session,
)

TICKER = "TST"
YEAR = 2024


# ---------------------------------------------------------------------------
# Boundaries: closed for every test in this file
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refused(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a unit test tried to open a socket: {args!r}")

    monkeypatch.setattr(socket.socket, "connect", _refused)
    monkeypatch.setattr(socket.socket, "connect_ex", _refused)
    monkeypatch.setattr(socket, "create_connection", _refused)


@pytest.fixture
def ticker_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    """`yfinance.Ticker`, replaced by a recorder that raises.

    The deleted share count fallback did `import yfinance as yf; yf.Ticker(t).info`
    inside the function, so it would reach this attribute.
    """
    calls: list[tuple[Any, ...]] = []

    def _recorded(*args: object, **kwargs: object) -> None:
        calls.append(args)
        raise AssertionError(f"yfinance.Ticker was called: {args!r}")

    monkeypatch.setattr(yfinance, "Ticker", _recorded)
    return calls


def _price_data(current_price: float = 20.0) -> PriceData:
    # Stock returns equal market returns, so a regression beta would be exactly 1.0
    # (OLS on identical series, strategy.md section 1). The tests below supply a
    # beta of 1.2, so a run that dropped the override would show 1.0, not 1.2.
    return PriceData(
        ticker=TICKER,
        stock_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        dates=pd.DatetimeIndex(pd.date_range("2024-01-31", periods=3, freq="D")),
        current_price=current_price,
        periods_per_year=12,
    )


@pytest.fixture
def price_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int, str]]:
    """`pipeline.fetch_price_data`, answering with `_price_data()` and recording its input."""
    calls: list[tuple[str, int, str]] = []

    def _stub(ticker: str, lookback_years: int, frequency: str) -> PriceData:
        calls.append((ticker, lookback_years, frequency))
        return _price_data()

    monkeypatch.setattr(pipeline, "fetch_price_data", _stub)
    return calls


@pytest.fixture
def refused_price_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    """`pipeline.fetch_price_data`, recording and raising: a stop must come before it."""
    calls: list[tuple[Any, ...]] = []

    def _refused(*args: object, **kwargs: object) -> None:
        calls.append(args + tuple(kwargs.items()))
        raise AssertionError("fetch_price_data was called")

    monkeypatch.setattr(pipeline, "fetch_price_data", _refused)
    return calls


# ---------------------------------------------------------------------------
# Hand-built statements
# ---------------------------------------------------------------------------


def _income_statement(shares: float = 100.0) -> IncomeStatement:
    # revenue 1000, cost of revenue 600, SG&A 200, R&D 50 -> EBIT 150.
    # No interest expense: with no debt either, the cost of debt is 0 and debt-free.
    return IncomeStatement(
        year=YEAR,
        revenue=1000.0,
        cost_of_revenue=600.0,
        sga=200.0,
        rd_expense=50.0,
        tax_expense=37.5,
        diluted_shares_outstanding=shares,
    )


def _balance_sheet() -> BalanceSheet:
    # No debt line, cash 100 -> net debt = 0 - 100 = -100. NCI printed as 0 (none).
    return BalanceSheet(
        year=YEAR,
        cash_and_equivalents=100.0,
        noncontrolling_interest_nonredeemable=0.0,
        noncontrolling_interest_redeemable=0.0,
        printed_unit_in_millions=1.0,
    )


def _financials(shares: float = 100.0, with_balance_sheet: bool = True) -> FinancialStatements:
    return FinancialStatements(
        ticker=TICKER,
        company_name="Test Co",
        income_statements=[_income_statement(shares)],
        balance_sheets=[_balance_sheet()] if with_balance_sheet else [],
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
        equity_risk_premium=0.05,
        beta_override=1.2,
        beta_lookback_years=3,
        return_frequency="daily",
    )


def _item(confidence: str, amount: float, line_item: str, direction: str) -> NonRecurringItem:
    return NonRecurringItem(
        year=YEAR,
        description=f"hand-built {confidence} item",
        amount=amount,
        line_item=line_item,
        direction=direction,
        category="other",
        confidence=confidence,
        page=1,
        printed_units="(in millions)",
        units_page=1,
        source="invented for the test",
    )


# ===========================================================================
# 1. adjust_financials
# ===========================================================================


def test_adjust_financials_applies_high_and_medium_and_excludes_low() -> None:
    """Hand arithmetic, from `NonRecurringItem.adjusted_impact` and the field signs.

    high   add_back 10 on sga             : sga  200 - 10 = 190 (an expense removed)
    medium remove    5 on cost_of_revenue : COGS 600 + 5  = 605 (a gain stripped)
    low    add_back 30 on rd_expense      : excluded, R&D stays 50

    Raw EBIT      = 1000 - 600 - 200 - 50 = 150
    Adjusted EBIT = 1000 - 605 - 190 - 50 = 155 = 150 + 10 - 5   (low item moves nothing)
    Had the low item been applied too: R&D 20, EBIT 185.
    """
    high = _item("high", 10.0, "sga", "add_back")
    medium = _item("medium", 5.0, "cost_of_revenue", "remove")
    low = _item("low", 30.0, "rd_expense", "add_back")
    raw = _financials()

    result = pipeline.adjust_financials(raw, [high, medium, low])

    assert result.applied == [high, medium]
    assert result.excluded == [low]
    adjusted_is = result.adjusted.get_income_statement(YEAR)
    assert adjusted_is is not None
    assert adjusted_is.sga == pytest.approx(190.0)
    assert adjusted_is.cost_of_revenue == pytest.approx(605.0)
    assert adjusted_is.rd_expense == pytest.approx(50.0)
    assert adjusted_is.ebit == pytest.approx(155.0)


def test_adjust_financials_does_not_mutate_the_raw_statements() -> None:
    """The raw figures after the call are the figures written above: 600, 200, 50, EBIT 150."""
    raw = _financials()
    raw_is = raw.income_statements[0]

    result = pipeline.adjust_financials(
        raw,
        [_item("high", 10.0, "sga", "add_back"), _item("medium", 5.0, "cost_of_revenue", "remove")],
    )

    assert result.adjusted is not raw
    assert raw.income_statements[0] is raw_is
    assert (raw_is.cost_of_revenue, raw_is.sga, raw_is.rd_expense) == (600.0, 200.0, 50.0)
    assert raw_is.ebit == pytest.approx(150.0)


def test_adjust_financials_stops_on_an_unrecognised_confidence() -> None:
    """Rule 3: an item this engine cannot rank stops and names `confidence`; it is not read as high."""
    with pytest.raises(ValueError, match="confidence") as raised:
        pipeline.adjust_financials(_financials(), [_item("certain", 10.0, "sga", "add_back")])
    assert "'certain'" in str(raised.value)


def test_adjust_financials_stops_on_an_item_year_with_no_statement() -> None:
    """Rule 3: an applied item for a year with no income statement is not dropped."""
    item = _item("high", 10.0, "sga", "add_back")
    item.year = 2019
    with pytest.raises(ValueError, match="year 2019") as raised:
        pipeline.adjust_financials(_financials(), [item])
    assert "no income statement" in str(raised.value)


# ===========================================================================
# 2. value_company: the wiring
# ===========================================================================


def test_value_company_share_count_and_market_cap_come_from_the_filing(
    price_calls: list[tuple[str, int, str]], ticker_calls: list[tuple[Any, ...]],
) -> None:
    """market_cap = stub price x filing shares = 20.0 x 100 = 2,000 (hand).

    The market data call receives the caller's ticker, lookback and frequency
    (3 and "daily", neither of which is a default).
    """
    run = pipeline.value_company(
        _financials(), _overrides(), ticker=TICKER, lookback_years=3, frequency="daily",
    )

    assert price_calls == [(TICKER, 3, "daily")]
    assert ticker_calls == []
    assert run.shares == 100.0
    assert run.market_cap == pytest.approx(2000.0)
    assert run.dcf_result.diluted_shares == 100.0
    assert run.dcf_result.current_price == 20.0
    assert run.latest_balance_sheet is not None
    assert run.latest_balance_sheet.year == YEAR


def test_value_company_overrides_reach_capm(
    price_calls: list[tuple[str, int, str]], ticker_calls: list[tuple[Any, ...]],
) -> None:
    """Cost of equity = rf + beta x ERP = 0.04 + 1.2 x 0.05 = 0.04 + 0.06 = 0.10 (hand).

    A regression beta on the stub's identical series would be 1.0, giving 0.09.
    Identity: debt 0 and interest 0 -> debt weight 0 -> WACC = cost of equity = 0.10.
    """
    run = pipeline.value_company(
        _financials(), _overrides(), ticker=TICKER, lookback_years=3, frequency="daily",
    )

    assert run.capm_result.beta == 1.2
    assert run.capm_result.risk_free_rate == 0.04
    assert run.capm_result.equity_risk_premium == 0.05
    assert run.capm_result.cost_of_equity == pytest.approx(0.10)
    assert run.wacc_result.debt_weight == 0.0
    assert run.wacc_result.equity_weight == 1.0
    assert run.wacc_result.wacc == pytest.approx(run.capm_result.cost_of_equity)
    assert run.wacc_result.wacc == pytest.approx(0.10)


def test_value_company_dcf_is_the_one_run_dcf_gives(
    price_calls: list[tuple[str, int, str]], ticker_calls: list[tuple[Any, ...]],
) -> None:
    """Hand arithmetic, one projected year, WACC 0.10, g 0.02:

    revenue 2025 = 1000 x 1.10                       = 1,100
    EBIT         = 1,100 x 0.20                      =   220
    NOPAT        = 220 x (1 - 0.25)                  =   165
    D&A = capex  = 1,100 x 0.05                      =    55
    change in NWC= 1,100 x 0.01                      =    11
    FCFF         = 165 + 55 - 55 - 11                =   154
    PV(FCFF)     = 154 / 1.10                        =   140
    TV           = 154 x 1.02 / (0.10 - 0.02) = 157.08 / 0.08 = 1,963.5
    PV(TV)       = 1,963.5 / 1.10                    = 1,785
    EV           = 140 + 1,785                       = 1,925
    net debt     = 0 - 100                           =  -100
    equity       = 1,925 + 100                       = 2,025
    implied      = 2,025 / 100                       = 20.25

    Then the closed-form check: `run_dcf` called directly on the result's own
    projection and WACC gives the same price.
    """
    financials = _financials()
    run = pipeline.value_company(
        financials, _overrides(), ticker=TICKER, lookback_years=3, frequency="daily",
    )

    assert [p.year for p in run.projected] == [2025]
    assert run.projected[0].revenue == pytest.approx(1100.0)
    assert run.projected[0].fcff == pytest.approx(154.0)
    assert run.dcf_result.pv_fcffs == pytest.approx(140.0)
    assert run.dcf_result.terminal_value == pytest.approx(1963.5)
    assert run.dcf_result.pv_terminal_value == pytest.approx(1785.0)
    assert run.dcf_result.net_debt == pytest.approx(-100.0)
    assert run.dcf_result.implied_share_price == pytest.approx(20.25)

    direct = run_dcf(
        projected_fcffs=run.projected,
        wacc_result=run.wacc_result,
        financials=financials,
        terminal_growth_rate=0.02,
        current_price=20.0,
        diluted_shares=100.0,
    )
    assert run.dcf_result.implied_share_price == pytest.approx(direct.implied_share_price)
    assert run.dcf_result.enterprise_value == pytest.approx(direct.enterprise_value)


def test_value_company_passes_a_market_data_failure_through_unchanged(
    monkeypatch: pytest.MonkeyPatch, ticker_calls: list[tuple[Any, ...]],
) -> None:
    def _fails(*args: object, **kwargs: object) -> None:
        raise ValueError("stub: no market data")

    monkeypatch.setattr(pipeline, "fetch_price_data", _fails)
    with pytest.raises(ValueError, match="^stub: no market data$"):
        pipeline.value_company(
            _financials(), _overrides(), ticker=TICKER, lookback_years=3, frequency="daily",
        )
    assert ticker_calls == []


def test_value_company_stops_on_a_missing_latest_balance_sheet(
    price_calls: list[tuple[str, int, str]], ticker_calls: list[tuple[Any, ...]],
) -> None:
    """Rule 3: no balance sheet, no debt balance. Stops naming `balance_sheet`; not set to 0."""
    with pytest.raises(ValueError, match="balance_sheet is None"):
        pipeline.value_company(
            _financials(with_balance_sheet=False), _overrides(),
            ticker=TICKER, lookback_years=3, frequency="daily",
        )
    assert ticker_calls == []


# ===========================================================================
# 3. The share count stop
# ===========================================================================

_NOT_A_SHARE_COUNT = [
    pytest.param(0.0, id="zero"),
    pytest.param(-5.0, id="negative"),
    pytest.param(math.nan, id="nan"),
    pytest.param(math.inf, id="inf"),
]


@pytest.mark.parametrize("shares", _NOT_A_SHARE_COUNT)
def test_value_company_stops_on_a_share_count_that_is_not_finite_and_above_zero(
    shares: float,
    refused_price_calls: list[tuple[Any, ...]],
    ticker_calls: list[tuple[Any, ...]],
) -> None:
    """Rules 3 and 5: the filing is the share count's only source.

    Expected: `ValueError` naming `diluted_shares`, the ticker and the fiscal year;
    no market data call; no `yfinance.Ticker` call.
    """
    with pytest.raises(ValueError) as raised:
        pipeline.value_company(
            _financials(shares=shares), _overrides(),
            ticker=TICKER, lookback_years=3, frequency="daily",
        )

    message = str(raised.value)
    assert "diluted_shares" in message
    assert TICKER in message
    assert str(YEAR) in message
    assert refused_price_calls == []
    assert ticker_calls == []


# --- the same stop, through both entry points ------------------------------


def _session_without_diluted_shares(directory: Path) -> Path:
    """The helpers' session file, with the latest year's `diluted_shares` printed as []."""
    pdf = make_pdf(directory)
    data = session_dict(pdf)
    years = data["filings"][0]["pass1"]["historical_years"]
    latest = next(y for y in years if y["year"] == 2024)
    assert latest["diluted_shares"], "the helper's 2024 year carries a share count to remove"
    latest["diluted_shares"] = []
    return write_session(directory, data, name="no_shares.json")


def test_the_share_count_stop_reaches_the_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    refused_price_calls: list[tuple[Any, ...]],
    ticker_calls: list[tuple[Any, ...]],
) -> None:
    """`python cli.py --session-file <no shares>`: exit 1, the message on stderr.

    Runs `cli.py` as `__main__` in this process, so its own exit handling is what
    is tested and the stubs on `pipeline` and `yfinance` stay in force.
    """
    session = _session_without_diluted_shares(tmp_path)
    monkeypatch.setattr("sys.argv", ["cli.py", "--session-file", str(session)])

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(Path(cli.__file__)), run_name="__main__")

    assert raised.value.code == 1
    err = capsys.readouterr().err
    assert "ERROR: diluted_shares" in err
    assert f"'{SESSION_TICKER}'" in err
    assert "fiscal year 2024" in err
    assert refused_price_calls == []
    assert ticker_calls == []


def test_the_share_count_stop_reaches_the_web_result_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`POST /valuation` with the same file: the error block shows the message."""
    client = open_closed_client(monkeypatch, tmp_path)
    # Recorders replace the refusing stubs `open_closed_client` installed, so a call
    # is counted, not only refused.
    price: list[tuple[Any, ...]] = []
    tick: list[tuple[Any, ...]] = []

    def _price(*args: object, **kwargs: object) -> None:
        price.append(args)
        raise AssertionError("fetch_price_data was called")

    def _ticker(*args: object, **kwargs: object) -> None:
        tick.append(args)
        raise AssertionError("yfinance.Ticker was called")

    monkeypatch.setattr(pipeline, "fetch_price_data", _price)
    monkeypatch.setattr(yfinance, "Ticker", _ticker)
    session = _session_without_diluted_shares(tmp_path)

    response = client.post("/valuation", data=VALUATION_FORM | {"session_file": str(session)})

    assert response.status_code == 200
    shown = error_text(response.text)
    assert shown is not None
    assert "diluted_shares" in shown
    assert f"'{SESSION_TICKER}'" in shown
    assert "fiscal year 2024" in shown
    assert "Implied Share Price" not in text_of(response.text)
    assert price == []
    assert tick == []


# ===========================================================================
# 4. One price for both entry points
# ===========================================================================

# The web form's fields (percent) and the CLI's flags (decimals), the same values.
# `VALUATION_FORM` supplies every override, so no form default is rounded (item 87).
_CLI_FLAGS_FOR_THE_FORM = [
    "--projection-years", "1",
    "--terminal-growth", "0.02",      # form 2.0
    "--revenue-growth", "0.10",       # form 10
    "--operating-margin", "0.20",     # form 20
    "--tax-rate", "0.25",             # form 25
    "--da-pct", "0.10",               # form 10
    "--capex-pct", "0.05",            # form 5
    "--nwc-pct", "0.02",              # form 2
    "--risk-free-rate", "0.04",       # form 4.0
    "--equity-risk-premium", "0.06",  # form 6
    "--beta", "1.0",                  # form 1.0
    "--cost-of-debt", "0.06",         # form 6
    "--lookback-years", "5",          # form 5
    "--frequency", "monthly",         # form monthly
]


def test_the_form_and_the_flags_above_state_the_same_overrides() -> None:
    """The comparison below is only fair if the two inputs agree: percent / 100 = decimal."""
    flags = dict(zip(_CLI_FLAGS_FOR_THE_FORM[::2], _CLI_FLAGS_FOR_THE_FORM[1::2], strict=True))
    pairs = {
        "--terminal-growth": "terminal_growth_rate", "--revenue-growth": "revenue_growth",
        "--operating-margin": "operating_margin", "--tax-rate": "tax_rate",
        "--da-pct": "da_pct", "--capex-pct": "capex_pct", "--nwc-pct": "nwc_pct",
        "--risk-free-rate": "risk_free_rate", "--equity-risk-premium": "equity_risk_premium",
        "--cost-of-debt": "cost_of_debt_override",
    }
    for flag, field in pairs.items():
        assert float(flags[flag]) == pytest.approx(float(VALUATION_FORM[field]) / 100), flag
    assert float(flags["--beta"]) == float(VALUATION_FORM["beta_override"])
    assert flags["--projection-years"] == VALUATION_FORM["projection_years"]
    assert flags["--lookback-years"] == VALUATION_FORM["beta_lookback_years"]
    assert flags["--frequency"] == VALUATION_FORM["return_frequency"]


def test_cli_and_web_report_the_same_implied_share_price(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Identity: one session file, one set of overrides, one stub -> one price.

    Each entry point's `DCFResult` is captured by wrapping `pipeline.run_dcf`, which
    `value_company` calls once per run. The two prices must be equal, and so must
    the two-decimal figures each entry point shows.
    """
    session = write_session(tmp_path, session_dict(make_pdf(tmp_path)))
    client = open_closed_client(monkeypatch, tmp_path)
    price_calls = install_price_stub(monkeypatch)  # answers ("TST", 5, "monthly") only

    results: list[Any] = []
    real_run_dcf = pipeline.run_dcf

    def _capture(**kwargs: Any) -> Any:
        result = real_run_dcf(**kwargs)
        results.append(result)
        return result

    monkeypatch.setattr(pipeline, "run_dcf", _capture)

    # Web: straight to POST /valuation, empty cache -> the cache-miss branch.
    response = client.post("/valuation", data=VALUATION_FORM | {"session_file": str(session)})
    assert response.status_code == 200
    assert error_text(response.text) is None, error_text(response.text)
    assert len(results) == 1
    web = results[0]

    # CLI: the same file, the same overrides as decimals.
    monkeypatch.setattr(
        "sys.argv", ["cli.py", "--session-file", str(session), *_CLI_FLAGS_FOR_THE_FORM],
    )
    capsys.readouterr()
    cli.main()
    out = capsys.readouterr().out
    assert len(results) == 2
    from_cli = results[1]

    assert price_calls == [(SESSION_TICKER, 5, "monthly")] * 2
    assert math.isfinite(web.implied_share_price)
    assert from_cli.implied_share_price == pytest.approx(web.implied_share_price, rel=1e-12)
    assert from_cli.wacc == pytest.approx(web.wacc, rel=1e-12)
    assert from_cli.diluted_shares == web.diluted_shares

    shown = f"${web.implied_share_price:.2f}"
    assert f"Implied Price:      ${web.implied_share_price:>11.2f}" in out
    assert (
        f"<td><strong>Implied Share Price</strong></td><td><strong>{shown}</strong></td>"
        in response.text
    )

