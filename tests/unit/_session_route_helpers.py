"""Shared inputs for the session-file route tests (P9b-route-tests).

Imported by `test_routes_session.py` and `test_routes_session_rule3_red.py`. The
name starts with an underscore so pytest does not collect it.

**Every figure here is written by hand, and every expected value in the two test
files is read off this file, not off a rendered page.** The session file below is
`session-extraction-v2` as the module docstring of `ingestion/session_extraction.py`
lays it out (v1 until P11a; since then every Pass 1 figure is a list of printed
rows, built by `tests/unit/_printed_lines.py` with the figures unchanged): one filing, so `plan_filings` gives `target_years = null` and
`include_bs = true` (the routing table, `docs/3-architecture/extraction.md`; the same
plan `tests/unit/test_session_extraction.py::one_filing` writes).

The PDF is written under `tmp_path` by `tests/unit/_pass1_pdf.py`, from the Pass 1
answer below: every row it cites, printed on its cited page (P12a). Its sha256 is
taken with `hashlib` here, as the test's own record of the bytes. Nothing reads `10K_filings/`.

**No test reaches the API or the network.** `open_closed_client` replaces
`ingestion.claude_extractor._call_llm`, the route module's `fetch_price_data` and
`yfinance.Ticker` with functions that raise, removes every credential variable after
`config` has filled the absent names from `.env` (it does so once, at import, and
never again; a variable removed before that import would be filled from `.env`,
backlog item 46), and points `UPLOAD_DIR` at `tmp_path`.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

import app as app_module
import config  # noqa: F401 -- imported FIRST so its one .env fill has run before we edit the env
import ingestion.claude_extractor as ce
from api import routes_upload, routes_valuation
from ingestion.claude_extractor import (
    FilingPlan,
    ProviderResolution,
    parse_pass1,
    pass1_prompts,
    pass2_prompts,
)
from ingestion.price_fetcher import PriceData
from ingestion.session_extraction import SESSION_FORMAT
from tests.unit._pass1_pdf import write_pass1_pdf
from tests.unit._printed_lines import printed_balance_sheet, printed_year

# ---------------------------------------------------------------------------
# The session file, by hand
# ---------------------------------------------------------------------------

TICKER = "TST"
COMPANY = "Test Co"
# Deliberately NOT a real model ID and NOT `_DEFAULT_MODELS["claude"]`, so a page
# that shows it can only have read it from this file.
MODEL = "model-id-declared-in-the-test-session"
FISCAL_YEAR = 2024

# One year is this base times an integer k. Every Pass 1 check is linear, so a year
# that reconciles at k = 1 reconciles at every k:
#   gross profit      600 = 1000 - 400
#   operating income  300 = 600 - 150 - 100 - 50
#   net income        228 = 300 + 10 - 20 + (-5) - 57
_BASE_YEAR: dict[str, float] = {
    "revenue": 1000, "cost_of_revenue": 400, "gross_profit": 600, "sga": 150,
    "rd_expense": 100, "depreciation_amortization": 30, "other_operating_expense": 50,
    "operating_income": 300, "interest_expense": 20, "interest_income": 10,
    "other_non_operating": -5, "tax_expense": 57, "net_income": 228,
    "diluted_shares": 48, "cfo": 290, "capex": 70, "sbc": 25,
    "change_in_working_capital": -15,
}

# Revenue by year, as written: 2023 is k = 1, 2024 is k = 2.
#   2023: 1000 * 1 = 1000 -> shown "1,000"
#   2024: 1000 * 2 = 2000 -> shown "2,000"
REVENUE_SHOWN = ["1,000", "2,000"]

# A low-confidence item. `partition_by_confidence`'s docstring
# (`analysis/normalizer.py:101-104`): `low` is EXCLUDED and moves nothing, so the
# revenue above is unchanged by it, and the result page lists it as excluded.
EXCLUDED_ITEM_DESCRIPTION = "Hand-written low-confidence item for the route tests"


def _year(year: int, k: int) -> dict[str, Any]:
    # P11a shape: each field one printed row, holding the base value times k.
    return printed_year(year, {key: [value * k] for key, value in _BASE_YEAR.items()})


def _balance_sheet(year: int) -> dict[str, Any]:
    # assets 100+50+80+60+10+300+200+40+20 = 860
    # liabilities 70+30+15+25+400+35 = 575; equity 285; 575 + 285 = 860.
    # P11a: the printed totals are those sums, 860 and 860.
    return printed_balance_sheet(year, {
        "cash": [100], "short_term_investments": [50],
        "accounts_receivable": [80], "inventory": [60], "other_current_assets": [10],
        "ppe_net": [300], "goodwill": [200], "intangible_assets": [40],
        "other_non_current_assets": [20], "accounts_payable": [70],
        "accrued_liabilities": [30], "other_current_liabilities": [15],
        "short_term_debt": [25], "long_term_debt": [400],
        "other_non_current_liabilities": [35], "total_equity": [285],
        # The two NCI memo lines (P10a): [] (an explicit 0 before P11a), this
        # company prints none. Required by the loader; never added to any total.
        "noncontrolling_interest_nonredeemable": [],
        "noncontrolling_interest_redeemable": [],
        "total_assets": [860], "total_liabilities_and_equity": [860],
    })


def pass1_answer() -> dict[str, Any]:
    return {
        "ticker": TICKER, "company_name": COMPANY, "currency": "USD",
        "units": {"printed": "(in millions)", "page": 50},
        "share_units": {"printed": "(in millions)", "page": 50},
        "historical_years": [_year(2023, 1), _year(2024, 2)],
        "latest_balance_sheet": _balance_sheet(2024),
    }


def pass2_answer() -> dict[str, Any]:
    """A WELL-FORMED Pass 2: every key the schema names, of the right type.

    P9d-pass2-checks changes the loader only for a malformed Pass 2, so nothing
    here depends on that work.
    """
    return {"non_recurring_items": [{
        "year": 2024, "description": EXCLUDED_ITEM_DESCRIPTION, "amount": 7.0,
        "line_item": "sga", "direction": "add_back", "category": "restructuring",
        "confidence": "low", "page": 50,
        "units": {"printed": "(in millions)", "page": 50},
        "source": "Note 99 (invented for the test)",
    }]}


def make_pdf(directory: Path) -> Path:
    """A real PDF printing every row of `pass1_answer()` and `pass2_answer()` on the page it cites.

    Since P12a both routes look each printed line up on its cited page, so the
    stand-in bytes this used to write would stop every run. The pages are built
    from the answer itself (`tests/unit/_pass1_pdf.py`); a test that changes a row
    afterwards calls `reprint_filing_pdf` on the filing.
    """
    path = directory / f"{TICKER}_10-K_{FISCAL_YEAR}.pdf"
    write_pass1_pdf(path, pass1_answer(), pass2_answer(), cover="Test filing for the P9b route tests")
    return path.resolve()


def session_dict(pdf: Path) -> dict[str, Any]:
    data = pdf.read_bytes()
    return {
        "format": SESSION_FORMAT,
        "ticker": TICKER,
        "company_name": COMPANY,
        "extracted_by": {"model": MODEL, "tool": "Claude Code", "date": "2026-10-02"},
        "filings": [{
            "fiscal_year": FISCAL_YEAR,
            "pdf_path": str(pdf),
            "pdf_sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "target_years": None,
            "include_bs": True,
            "pages_read": {"pass1": [50, 51, 52], "pass2": [50]},
            "pass1": pass1_answer(),
            "pass2": pass2_answer(),
        }],
    }


def write_session(directory: Path, data: dict[str, Any], name: str = "session.json") -> Path:
    path = directory / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path.resolve()


# ---------------------------------------------------------------------------
# The valuation form, and market data
# ---------------------------------------------------------------------------

# Every projection input is an explicit override, and beta, the ERP and the
# risk-free rate are supplied, so neither the regression nor the historical market
# return is reached (the same reasoning as `tests/unit/test_routes.py::_price_data`).
# Diluted shares in 2024 are 48 * 2 = 96, not 0, so the yfinance share-count
# fallback at `api/routes_valuation.py:625-628` is not reached either.
VALUATION_FORM: dict[str, str] = {
    "ticker": TICKER,
    "company_name": COMPANY,
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


def price_data() -> PriceData:
    return PriceData(
        ticker=TICKER,
        stock_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        dates=pd.DatetimeIndex(pd.date_range("2024-01-31", periods=3, freq="D")),
        current_price=45.0,
        periods_per_year=12,
    )


# ---------------------------------------------------------------------------
# Boundaries. Plain functions; each test module wraps them in its own fixtures,
# so no fixture name is imported (ruff F811) and no conftest is shared.
# ---------------------------------------------------------------------------

_CREDENTIAL_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_FOUNDRY_BASE_URL",
    "ANTHROPIC_FOUNDRY_RESOURCE",
    "ANTHROPIC_FOUNDRY_API_KEY",
    "GEMINI_API_KEY",
)


def _refuse(name: str):
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a route test reached {name}: args={args!r} kwargs={kwargs!r}")
    return refuse


def open_closed_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """A client over the real app with every boundary closed and no credential.

    `config` was imported at the top of this module, so its one fill from `.env`
    (absent names only, at import) has already run; removing the variables now
    cannot be undone by it.
    """
    monkeypatch.setattr(routes_upload, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(routes_valuation, "_extraction_cache", {}, raising=False)
    for var in _CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(ce, "_call_llm", _refuse("_call_llm"))
    monkeypatch.setattr(routes_valuation, "fetch_price_data", _refuse("fetch_price_data"))
    import yfinance
    monkeypatch.setattr(yfinance, "Ticker", _refuse("yfinance.Ticker"))
    return TestClient(app_module.app, raise_server_exceptions=False)


def install_price_stub(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int, int | str]]:
    """`fetch_price_data`, answering ONLY the ticker in the session file.

    Expected input: ("TST", 5, "monthly") -- the file's ticker, and the
    `beta_lookback_years` / `return_frequency` the form above sends. Anything else
    raises, so a route that priced the request's ticker instead of the file's fails.
    """
    calls: list[tuple[str, int, int | str]] = []

    def fake(ticker: str, lookback_years: int, frequency: str) -> PriceData:
        if (ticker, lookback_years, frequency) != (TICKER, 5, "monthly"):
            raise AssertionError(f"fetch_price_data given an input it was not: {ticker!r}")
        calls.append((ticker, lookback_years, frequency))
        return price_data()

    monkeypatch.setattr(routes_valuation, "fetch_price_data", fake)
    return calls


def install_loader_spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Count `load_session_extraction` calls, delegating to the real loader.

    How a test tells a cache hit (no new call) from a cache miss (one new call).
    """
    calls: list[str] = []
    real = routes_valuation.load_session_extraction

    def spy(path: str | Path):
        calls.append(str(path))
        return real(path)

    monkeypatch.setattr(routes_valuation, "load_session_extraction", spy)
    return calls


def install_route_a_stub(
    monkeypatch: pytest.MonkeyPatch, pdf: Path,
) -> list[str]:
    """Replace `_call_llm` with a stub that answers only the two calls route A makes.

    Keyed on (system prompt, user prompt, PDF bytes, transport). The prompts are the
    ones `pass1_prompts` / `pass2_prompts` give for the one-filing plan; the
    transport must be the public API, because the test sets ANTHROPIC_API_KEY and
    no Foundry variable. Any other call raises.
    """
    plan = FilingPlan(fiscal_year=FISCAL_YEAR, pdf_path=str(pdf), target_years=None,
                      include_bs=True)
    pdf_bytes = pdf.read_bytes()
    p1_json = json.dumps(pass1_answer())
    own_financials, errors = parse_pass1(p1_json, TICKER, COMPANY)
    assert errors == [], f"the hand-written Pass 1 does not reconcile: {errors}"
    answers = {
        (*pass1_prompts(plan), pdf_bytes): ("pass1", p1_json),
        (*pass2_prompts(plan, own_financials), pdf_bytes): ("pass2", json.dumps(pass2_answer())),
    }
    calls: list[str] = []

    def stub(system_prompt: str, user_prompt: str, resolution: ProviderResolution,
             pdf_bytes: bytes | None = None) -> tuple[str, int, int]:
        key = (system_prompt, user_prompt, pdf_bytes or b"")
        if key not in answers or resolution.transport != "anthropic-direct":
            raise AssertionError(
                f"_call_llm given a call it was not: transport={resolution.transport!r} "
                f"prompt={user_prompt[:80]!r}",
            )
        which, text = answers[key]
        calls.append(which)
        return text, 0, 0

    monkeypatch.setattr(ce, "_call_llm", stub)
    return calls


# ---------------------------------------------------------------------------
# Reading a rendered page. These slice HTML; they hold no expected value.
# ---------------------------------------------------------------------------


def text_of(body: str) -> str:
    """The page with entities decoded, so `'` is not `&#39;`."""
    return html.unescape(body)


def strip_tags(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def label_rows(body: str) -> dict[str, str] | None:
    """The four rows under "Extraction — who read the filing", or None if absent."""
    heading = "<h2>Extraction — who read the filing</h2>"
    if heading not in body:
        return None
    start = body.index(heading)
    end = body.index("</table>", start)
    rows: dict[str, str] = {}
    for tr in re.findall(r"<tr>(.*?)</tr>", body[start:end], re.DOTALL):
        cells = [strip_tags(c) for c in re.findall(r"<td>(.*?)</td>", tr, re.DOTALL)]
        if len(cells) == 2:
            rows[cells[0]] = cells[1]
    return rows


def error_text(body: str) -> str | None:
    """The text of the page's `alert-error` box, or None if there is none."""
    match = re.search(r'<div class="alert alert-error">(.*?)</div>', body, re.DOTALL)
    return strip_tags(match.group(1)) if match else None


def hidden_value(body: str, name: str) -> str:
    match = re.search(rf'<input type="hidden" name="{re.escape(name)}" value="([^"]*)">', body)
    assert match is not None, f"no hidden input {name!r} on the page"
    return html.unescape(match.group(1))


def revenue_row(body: str) -> list[str]:
    """The cells of the Revenue row of the Adjusted Income Statement block."""
    match = re.search(
        r'<td class="sticky-col">Revenue</td>(.*?)</tr>', body, re.DOTALL,
    )
    assert match is not None, "no Revenue row on the page"
    return [strip_tags(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", match.group(1), re.DOTALL)]
