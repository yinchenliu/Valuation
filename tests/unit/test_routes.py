"""HTTP tests for the four web routes.

**Why this file exists.** The web application answered HTTP 500 on every route
from `bc19431` to `d885d8d` and nothing in the suite noticed, because the check
in use was `import app`, which succeeded throughout. `import app` cannot see a
broken `TemplateResponse` call; only a request can. Backlog item 27.

**Every route below is asserted on its status code AND on its body.** All four
routes answer 200 or 303 today, and `POST /valuation` answers 200 on failure as
well as on success, so a status code alone cannot tell the success page from the
error page. That confusion is exactly what let the outage hide.

**Where the expected values come from.** Section 1 of `docs/5-testing/strategy.md`:
the expected side of an assertion must exist before the code runs. In this file
each one is either

  * hand arithmetic, written out in the comment above the assertion, over inputs
    chosen so that every derived figure is a round number a reader can check
    without running anything; or
  * a contract stated somewhere other than the code path under test — the route's
    own declared signature (`Form(...)` / `File(...)`), the redirect target's
    parser, or `docs/8-build/environment.md` section 3 for provider, model and
    transport.

No expected value here was obtained by running the code and reading what it
printed.

**No key, no PDF, no network.** `starlette.testclient.TestClient` opens no
socket. The three boundaries — `extract_financials`, `extract_multi_year` and
`fetch_price_data` — are replaced in the `client` fixture with a fake that fails
loudly, so a test that forgets to supply its own fake cannot silently reach out.
`FinancialStatements` and `PriceData` are built here by hand with only the fields
the routes read; no `.pkl` is loaded. `docs/5-testing/strategy.md` section 3.

**What this file deliberately does NOT assert.**

  * No fallback. `POST /valuation` with no `files` does not stop (see the entry
    for `P5b-route-tests`); this file does not pin that behaviour either way.
  * Not the cache. Every `POST /valuation` test below starts from an empty
    `_extraction_cache` and therefore takes the extract branch, so backlog item
    5's fix — removing the module-global cache that is `pop`ped on read — cannot
    turn any of these red.
  * Not the `":" in files` branch, backlog item 26. Where that branch is crossed
    the assertion is on the outcome (the extractor is handed the path the user
    named, drive letter intact), never on which branch produced it.
  * Not the blanket `except Exception` handlers, backlog item 8. The error-branch
    tests pin "a failure is reported to the reader on a rendered page, not as a
    blank 500", which stays true after those catches become typed exceptions.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

import app as app_module
from api import routes_upload, routes_valuation
from ingestion.price_fetcher import PriceData
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
)
from tests.unit._fiscal_year_stub import stub_evidence_reader
from tests.unit._text_pdf import write_10k_pdf

# ---------------------------------------------------------------------------
# Reading a rendered page
#
# These helpers only slice HTML. They hold no expected value.
# ---------------------------------------------------------------------------


def _input_tag(body: str, name: str) -> str:
    """The single `<input ... name="{name}" ...>` tag, attributes and all."""
    match = re.search(rf'<input[^>]*\sname="{re.escape(name)}"[^>]*>', body, re.DOTALL)
    assert match is not None, f'no <input name="{name}"> in the page'
    return match.group(0)


def _field_value(body: str, name: str) -> str:
    """The `value="..."` of the input called `name`, or "" when it has none."""
    match = re.search(r'value="([^"]*)"', _input_tag(body, name))
    return match.group(1) if match else ""


def _strip_tags(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment).strip()


def _rows_under(body: str, heading: str) -> dict[str, str]:
    """Every two-cell `<tr>` of the table that follows `<h2>{heading}</h2>`.

    Scoped to one section because two sections of `valuation_result.html` both
    carry a row labelled "Tax Rate".
    """
    start = body.index(f"<h2>{heading}</h2>")
    end = body.index("</table>", start)
    section = body[start:end]
    rows: dict[str, str] = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", section, re.DOTALL):
        cells = [_strip_tags(c) for c in re.findall(r"<td>(.*?)</td>", tr, re.DOTALL)]
        if len(cells) == 2:
            rows[cells[0]] = cells[1]
    return rows


def _projection_row(body: str) -> list[str]:
    """The cells of the one `<tbody>` on the page — the projected FCFF table."""
    tbody = re.search(r"<tbody>(.*?)</tbody>", body, re.DOTALL)
    assert tbody is not None, "no <tbody> in the page"
    return [_strip_tags(c) for c in re.findall(r"<td>(.*?)</td>", tbody.group(1), re.DOTALL)]


# ---------------------------------------------------------------------------
# Hand-built inputs
#
# Two years, chosen so that every default `derive_assumptions` produces is a
# round number. The arithmetic is written out above `EXPECTED_DEFAULTS` below.
# ---------------------------------------------------------------------------


def _two_year_financials() -> FinancialStatements:
    return FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=[
            # EBIT = 1000 - 800 = 200; margin 200/1000 = 20%.
            # EBT  = EBIT (no interest, no other income) = 200;
            # effective tax = 50/200 = 25%.
            IncomeStatement(year=2023, revenue=1000.0, sga=800.0, tax_expense=50.0,
                            diluted_shares_outstanding=100.0),
            # EBIT = 1200 - 960 = 240; margin 240/1200 = 20%.
            # EBT = 240; effective tax = 60/240 = 25%.
            IncomeStatement(year=2024, revenue=1200.0, sga=960.0, tax_expense=60.0,
                            diluted_shares_outstanding=100.0),
        ],
        balance_sheets=[
            # NCI: explicit 0.0 for both printed lines; this company has none
            # (P10a). A value, not a default: None would stop run_dcf.
            BalanceSheet(year=2024, cash_and_equivalents=100.0, long_term_debt=500.0,
                         noncontrolling_interest_nonredeemable=0.0,
                         noncontrolling_interest_redeemable=0.0),
        ],
        cash_flow_statements=[
            # D&A 100/1000 = 10%; CapEx 50/1000 = 5%; WC change -20/1000 -> +2%.
            CashFlowStatement(year=2023, depreciation_amortization=100.0,
                              capital_expenditures=-50.0,
                              change_in_working_capital=-20.0),
            # D&A 120/1200 = 10%; CapEx 60/1200 = 5%; WC change -24/1200 -> +2%.
            CashFlowStatement(year=2024, depreciation_amortization=120.0,
                              capital_expenditures=-60.0,
                              change_in_working_capital=-24.0),
        ],
    )


# Hand arithmetic over `_two_year_financials()`, from the formulas in
# `analysis/projector.py`'s docstrings and `docs/3-architecture/valuation-math.md`.
# Both years give the same ratio on purpose, so every average is that ratio and
# no long division is needed to check any line:
#
#   revenue growth  CAGR over the one available step = (1200/1000)^(1/1) - 1 = 20.0%
#   operating margin  mean(200/1000, 240/1200) = mean(20%, 20%)             = 20.0%
#   tax rate          mean( 50/200,   60/240)  = mean(25%, 25%)             = 25.0%
#   D&A   % revenue   mean(100/1000, 120/1200) = mean(10%, 10%)             = 10.0%
#   CapEx % revenue   mean( 50/1000,  60/1200) = mean( 5%,  5%)             =  5.0%
#   NWC   % revenue   mean( 20/1000,  24/1200) = mean( 2%,  2%)             =  2.0%
#
# The form shows one decimal place. `projection_years` defaults to 5
# (`models/valuation.py:155`), so the growth field carries the one rate five times.
EXPECTED_DEFAULTS = {
    "revenue_growth": "20.0, 20.0, 20.0, 20.0, 20.0",
    "operating_margin": "20.0",
    "tax_rate": "25.0",
    "da_pct": "10.0",
    "capex_pct": "5.0",
    "nwc_pct": "2.0",
}


def _one_year_financials() -> FinancialStatements:
    """A single year, so the projection below starts from revenue 1000 exactly.

    Every projection input is supplied as an explicit form override in the
    valuation test, so nothing here is read except `revenue` (the projection
    base), `diluted_shares_outstanding` (the denominator) and the balance sheet
    (net debt, and the debt weight in WACC).
    """
    return FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=[
            IncomeStatement(year=2024, revenue=1000.0, sga=800.0, tax_expense=50.0,
                            diluted_shares_outstanding=100.0),
        ],
        balance_sheets=[
            # total debt = 0 + 0 + 500 = 500; net debt = 500 - 100 - 0 = 400.
            # NCI: explicit 0.0 for both printed lines; this company has none
            # (P10a). A value, not a default: None would stop run_dcf.
            BalanceSheet(year=2024, cash_and_equivalents=100.0, long_term_debt=500.0,
                         noncontrolling_interest_nonredeemable=0.0,
                         noncontrolling_interest_redeemable=0.0),
        ],
    )


def _price_data() -> PriceData:
    """Market data, hand-built. `yfinance` is a boundary — strategy.md section 3.

    The returns are never read: the valuation test passes `beta_override` and an
    explicit equity risk premium, so neither the regression nor the historical
    market return is reached. `current_price` is read twice — for the market cap
    in WACC and for the upside comparison.
    """
    return PriceData(
        ticker="TESTCO",
        stock_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        dates=pd.DatetimeIndex(pd.date_range("2024-01-31", periods=3, freq="D")),
        current_price=45.0,
        periods_per_year=12,
    )


# The form `POST /valuation` receives. Percentages, because the route divides by
# 100 at its boundary. Chosen so the whole chain below is round.
VALUATION_FORM = {
    "ticker": "TESTCO",
    "company_name": "Test Company Inc",
    "files": "2024:c:/tmp/p5b-valuation-never-opened.pdf",
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    """A client over the real app, with every boundary closed.

    * `UPLOAD_DIR` is rebound into pytest's `tmp_path`, so `POST /upload` writes
      nothing into the repository. `uploads/` stays empty and untracked.
    * `_extraction_cache` is rebound to a fresh dict, so no test can see another
      test's extraction and every `POST /valuation` takes the extract branch.
      `raising=False` because backlog item 5 may delete that global.
    * The three boundaries fail loudly. A test that needs one supplies its own.
    * The provider environment is pinned, so `resolve_provider` — which reads the
      environment and nothing else — gives the same answer on a machine with a
      Foundry gateway configured and on one without. The value is a placeholder
      string; no client is built and no request is made.
    * `raise_server_exceptions=False` so that an unhandled exception arrives as
      the HTTP 500 a browser would see, which is the thing being tested.
    """
    monkeypatch.setattr(routes_upload, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(routes_valuation, "_extraction_cache", {}, raising=False)

    for var in (
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_FOUNDRY_RESOURCE",
        "ANTHROPIC_FOUNDRY_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder-no-call-is-made")

    def _closed_boundary(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "a unit test reached a boundary it did not fake: "
            f"args={args!r} kwargs={kwargs!r}"
        )

    monkeypatch.setattr(routes_valuation, "extract_financials", _closed_boundary)
    monkeypatch.setattr(routes_valuation, "extract_multi_year", _closed_boundary)
    monkeypatch.setattr(routes_valuation, "fetch_price_data", _closed_boundary)

    return TestClient(app_module.app, raise_server_exceptions=False)


@pytest.fixture
def extraction_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """Fake both extractors; record what the route handed them.

    The recorded arguments are what the assertions use: the contract is that the
    filing the user named is the filing the extractor is given.
    """
    calls: list[tuple] = []

    def fake_single(pdf_path: str, ticker: str, company_name: str = "", **kwargs: object):
        calls.append(("single", pdf_path, ticker, company_name))
        return _two_year_financials(), []

    def fake_multi(filings: list, ticker: str, company_name: str = "", **kwargs: object):
        calls.append(("multi", list(filings), ticker, company_name))
        return _two_year_financials(), []

    monkeypatch.setattr(routes_valuation, "extract_financials", fake_single)
    monkeypatch.setattr(routes_valuation, "extract_multi_year", fake_multi)
    return calls


# ===========================================================================
# GET /  — the front page
# ===========================================================================


def test_get_root_serves_the_upload_form(client: TestClient) -> None:
    """The front page renders, and the form it renders is the one /upload needs.

    Expected values: the declared signature of `POST /upload`
    (`api/routes_upload.py:51-57`) — `ticker: str = Form(...)`,
    `company_name: str = Form("")`, `pdf_files: list[UploadFile] = File(...)`.
    A form that does not POST multipart to `/upload` carrying those three names
    cannot reach that route, whatever the page looks like. Nothing here was read
    off a rendered page.
    """
    response = client.get("/")

    assert response.status_code == 200
    body = response.text

    # The outage's signature, to name it in the failure message when it returns.
    assert "Internal Server Error" not in body

    form = re.search(r"<form[^>]*>", body)
    assert form is not None, "the front page rendered no form"
    assert 'action="/upload"' in form.group(0)
    assert 'method="post"' in form.group(0)
    # A `File(...)` parameter can only be supplied by a multipart body.
    assert 'enctype="multipart/form-data"' in form.group(0)

    for field in ("ticker", "company_name", "pdf_files"):
        assert f'name="{field}"' in _input_tag(body, field)
    assert 'type="file"' in _input_tag(body, "pdf_files")


def test_the_form_on_the_front_page_is_accepted_by_the_route_it_targets(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read the form off `/`, submit exactly that, and require it to be accepted.

    Expected value: *not* 422. FastAPI answers 422 when a declared `Form`/`File`
    parameter is absent, so "the fields this page offers are the fields that route
    requires" is checkable without knowing anything about either page's text.

    The uploaded bytes are not a filing, so the P10c evidence reader is stubbed to
    say the file's content gives 2024, as its name does
    (`tests/unit/_fiscal_year_stub.py`). The verification itself still runs.
    """
    asked = stub_evidence_reader(monkeypatch, {"goog-10k-2024.pdf": 2024})
    body = client.get("/").text
    form = re.search(r'<form[^>]*action="([^"]+)"', body)
    assert form is not None, f"the front page offered no form: {body[:200]!r}"
    action = form.group(1)
    names = re.findall(r'<input[^>]*\sname="([^"]+)"', body)

    payload = {name: "GOOGL" for name in names if name != "pdf_files"}
    response = client.post(
        action,
        data=payload,
        files={"pdf_files": ("goog-10k-2024.pdf", b"%PDF-1.4 not a real filing")},
        follow_redirects=False,
    )

    assert response.status_code != 422, response.text
    assert response.status_code == 303
    assert asked == ["goog-10k-2024.pdf"]  # the year was verified, not skipped


# ===========================================================================
# POST /upload
# ===========================================================================


def test_post_upload_saves_the_file_and_redirects_naming_it(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expected values, each from a contract stated outside the code path:

    * 303, because the route is declared `status_code=303`
      (`api/routes_upload.py:76`) — a POST that redirects to a GET.
    * `ticker=GOOGL` from lower-case input: the route's `ticker.upper()` contract,
      and the directory it writes to is `UPLOAD_DIR/<TICKER>`.
    * `files=2024:<path>`: `_guess_fiscal_year`'s docstring — "a 4-digit year from
      the filename" — and the `year:path` shape the *receiving* parser expects
      (`_parse_files_param`, `api/routes_valuation.py:34-43`).
    * the bytes on disk are the bytes uploaded.

    The bytes are not a filing, so the P10c evidence reader is stubbed to say
    the content gives 2024, as the name does (`tests/unit/_fiscal_year_stub.py`).
    """
    asked = stub_evidence_reader(monkeypatch, {"goog-10k-2024.pdf": 2024})
    response = client.post(
        "/upload",
        data={"ticker": "googl", "company_name": "Alphabet Inc"},
        files={"pdf_files": ("goog-10k-2024.pdf", b"%PDF-1.4 not a real filing")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert asked == ["goog-10k-2024.pdf"]  # the year was verified, not skipped
    location = response.headers["location"]
    assert urlparse(location).path == "/assumptions"

    query = parse_qs(urlparse(location).query)
    assert query["ticker"] == ["GOOGL"]
    assert query["company_name"] == ["Alphabet Inc"]

    files_param = query["files"][0]
    year, _, path = files_param.partition(":")
    assert year == "2024"

    saved = tmp_path / "uploads" / "GOOGL" / "goog-10k-2024.pdf"
    assert saved.exists(), f"nothing written to {saved}"
    assert saved.read_bytes() == b"%PDF-1.4 not a real filing"
    # The path handed on is the file actually written, drive letter and all.
    assert path.replace("\\", "/").lower().endswith("uploads/googl/goog-10k-2024.pdf")
    assert path.lower() == str(saved).lower()


def test_post_upload_journey_reaches_a_rendered_assumptions_page(
    client: TestClient, extraction_calls: list[tuple], tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Follow the redirect. The page at the other end must render, not 500.

    Expected values: the ticker the user typed, upper-cased, reaches the page;
    and the extractor is handed the file that was saved — a Windows drive letter
    inside the `year:path` pair must survive the round trip. That is an outcome,
    not a branch: backlog item 26 may change how `files` is parsed without
    changing which file gets read.

    The bytes are not a filing, so the P10c evidence reader is stubbed to say
    the content gives 2024, as the name does (`tests/unit/_fiscal_year_stub.py`).
    """
    asked = stub_evidence_reader(monkeypatch, {"testco-10k-2024.pdf": 2024})
    response = client.post(
        "/upload",
        data={"ticker": "testco", "company_name": "Test Company Inc"},
        files={"pdf_files": ("testco-10k-2024.pdf", b"%PDF-1.4 not a real filing")},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Internal Server Error" not in response.text
    assert "Valuation Assumptions: TESTCO" in response.text
    assert asked == ["testco-10k-2024.pdf"]  # the year was verified, not skipped

    saved = tmp_path / "uploads" / "TESTCO" / "testco-10k-2024.pdf"
    assert len(extraction_calls) == 1
    kind, pdf_path, ticker, company_name = extraction_calls[0]
    assert kind == "single"
    assert pdf_path.lower() == str(saved).lower()
    assert ticker == "TESTCO"
    assert company_name == "Test Company Inc"


def test_post_upload_with_a_year_the_filing_contradicts_answers_400_and_does_not_redirect(
    client: TestClient, tmp_path
) -> None:
    """P10c step 3: the year in the uploaded name is verified against the filing,
    and a mismatch re-renders the upload page with the message. No stub here: the
    PDF is written by the test (`tests/unit/_text_pdf.py`), shaped like the
    assignment's L3Harris 2026-01-02 row.

    Expected, by the round 2 rule: cover "January 2, 2026", label "2025" -> 2025
    is the cover year - 1, in range, so the content gives 2025. The name gives
    2026. So: 400 (the route's documented status), no Location header, and the
    web remedy (rename to 2025 and upload again), not the CLI's YEAR:PATH.
    """
    pdf = write_10k_pdf(tmp_path / "src.pdf", "January 2, 2026",
                        "(In millions, except per share amounts) 2025 2024 2023")
    response = client.post(
        "/upload",
        data={"ticker": "lhx", "company_name": "Test Filer Inc."},
        files={"pdf_files": ("LHX_10-K_2026-01-02.pdf", pdf.read_bytes())},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "location" not in response.headers
    body = response.text
    assert "does not match the filing" in body
    assert "LHX_10-K_2026-01-02.pdf" in body
    assert "given fiscal year 2026" in body
    assert "content gives 2025" in body
    assert "upload it again" in body
    assert "Pass 2025:" not in body  # no YEAR:PATH remedy on the web
    assert 'name="pdf_files"' in body  # the upload form is shown again


def test_post_upload_of_the_same_filing_renamed_to_its_content_year_redirects(
    client: TestClient, tmp_path
) -> None:
    """The control for the test above: the same bytes, named for 2025, pass the
    check and reach the 303 redirect with files=2025:<path>."""
    pdf = write_10k_pdf(tmp_path / "src.pdf", "January 2, 2026",
                        "(In millions, except per share amounts) 2025 2024 2023")
    response = client.post(
        "/upload",
        data={"ticker": "lhx", "company_name": "Test Filer Inc."},
        files={"pdf_files": ("LHX_10-K_2025-01-02.pdf", pdf.read_bytes())},
        follow_redirects=False,
    )
    assert response.status_code == 303
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["files"][0].startswith("2025:")


@pytest.mark.parametrize("missing", ["ticker", "pdf_files"])
def test_post_upload_stops_and_names_a_missing_required_field(
    client: TestClient, missing: str
) -> None:
    """Rule 3 at the HTTP boundary: a missing required input stops and names itself.

    Expected value: 422, because `ticker: str = Form(...)` and
    `pdf_files: list[UploadFile] = File(...)` are declared without defaults
    (`api/routes_upload.py:52-57`), and FastAPI's contract for an absent required
    field is 422 with the field named in the body. `docs/2-rules/rules.md` rule 3.
    """
    data = {"ticker": "GOOGL", "company_name": ""}
    files = {"pdf_files": ("goog-10k-2024.pdf", b"%PDF-1.4")}
    if missing == "ticker":
        del data["ticker"]
    else:
        files = {}

    response = client.post("/upload", data=data, files=files, follow_redirects=False)

    assert response.status_code == 422
    assert missing in response.text


# ===========================================================================
# GET /assumptions
# ===========================================================================


def test_get_assumptions_puts_the_derived_defaults_into_the_form(
    client: TestClient, extraction_calls: list[tuple]
) -> None:
    """The derived defaults reach the form, and each one is hand-computed above.

    Expected values: `EXPECTED_DEFAULTS`, derived by hand from
    `_two_year_financials()` — see the arithmetic written out beside it. Both
    years carry the same ratio, so every average is that ratio.
    """
    response = client.get(
        "/assumptions",
        params={
            "ticker": "TESTCO",
            "company_name": "Test Company Inc",
            "files": "2024:c:/tmp/p5b-never-opened.pdf",
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "Internal Server Error" not in body
    assert "alert-error" not in body, "a successful extraction rendered an error"

    # This is the page it claims to be, and it posts to the route that values it.
    assert "Valuation Assumptions: TESTCO" in body
    assert 'action="/valuation"' in body

    for field, expected in EXPECTED_DEFAULTS.items():
        assert _field_value(body, field) == expected, field

    # The filing the user named is carried forward to the POST, unchanged.
    assert _field_value(body, "files") == "2024:c:/tmp/p5b-never-opened.pdf"
    assert _field_value(body, "ticker") == "TESTCO"

    # And it is the file the extractor was handed. Outcome, not branch.
    assert extraction_calls == [
        ("single", "c:/tmp/p5b-never-opened.pdf", "TESTCO", "Test Company Inc")
    ]


def test_get_assumptions_reads_two_filings_with_the_multi_year_extractor(
    client: TestClient, extraction_calls: list[tuple]
) -> None:
    """Two filings, two fiscal years, one extraction covering both.

    Expected values: the two (year, path) pairs the user named, in order, reach
    the extractor — the contract of `_extract_from_files`'s docstring — and the
    page that comes back carries the same hand-computed defaults as the
    single-filing case, because the fake returns the same financials.
    """
    response = client.get(
        "/assumptions",
        params={
            "ticker": "TESTCO",
            "company_name": "Test Company Inc",
            "files": "2023:c:/tmp/p5b-2023.pdf,2024:c:/tmp/p5b-2024.pdf",
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "alert-error" not in body
    for field, expected in EXPECTED_DEFAULTS.items():
        assert _field_value(body, field) == expected, field

    assert extraction_calls == [
        (
            "multi",
            [(2023, "c:/tmp/p5b-2023.pdf"), (2024, "c:/tmp/p5b-2024.pdf")],
            "TESTCO",
            "Test Company Inc",
        )
    ]


def test_get_assumptions_reports_a_failed_extraction_on_a_rendered_page(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure must reach the reader as a page, not as a blank 500.

    This is the branch that made the outage invisible: the error page rendered
    through the same broken call as the success page, so the user saw
    `Internal Server Error` with no message at all. Backlog item 27.

    Expected values: 200, and the text of the failure visible in the body. The
    requirement — "a failure is reported to the user" — is independent of *how*
    the route catches it, so this test stays true when backlog item 8 replaces
    the blanket `except Exception` with typed exceptions.
    """
    message = "extraction failed: no text layer in the 2024 filing"

    def fake_extract(*args: object, **kwargs: object) -> None:
        raise RuntimeError(message)

    monkeypatch.setattr(routes_valuation, "extract_financials", fake_extract)

    response = client.get(
        "/assumptions",
        params={"ticker": "TESTCO", "files": "2024:c:/tmp/p5b-never-opened.pdf"},
    )

    assert response.status_code == 200
    body = response.text
    assert "Internal Server Error" not in body
    assert "alert-error" in body
    assert message in body
    # It is still the assumptions page, and no figure was invented for the form.
    assert "Valuation Assumptions: TESTCO" in body
    for field in ("operating_margin", "tax_rate", "da_pct", "capex_pct", "nwc_pct"):
        assert _field_value(body, field) == "", field


def test_get_assumptions_with_no_filing_named_still_renders(client: TestClient) -> None:
    """A bare GET must not answer 500. Backlog item 27; nothing more is claimed.

    Deliberately silent on what the page *says* when no filing is named. The
    route currently renders a blank form and reports nothing, which is a rule-3
    question recorded as a finding in this unit's entry — it is not asserted here
    in either direction, so fixing it cannot turn this red.
    """
    response = client.get("/assumptions")

    assert response.status_code == 200
    assert "Internal Server Error" not in response.text
    assert 'action="/valuation"' in response.text


# ===========================================================================
# POST /valuation
# ===========================================================================


def _run_valuation(client: TestClient) -> str:
    response = client.post("/valuation", data=VALUATION_FORM)
    assert response.status_code == 200
    assert "Internal Server Error" not in response.text
    return response.text


def test_post_valuation_renders_the_completed_valuation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The success page, every figure on it computed by hand first.

    Inputs: `_one_year_financials()` (revenue 1000, 100m diluted shares, debt 500,
    cash 100) and `_price_data()` (price 45.00), with `VALUATION_FORM` supplying
    every assumption explicitly so nothing is derived from history.

    Formulas from `analysis/`'s module docstrings and
    `docs/3-architecture/valuation-math.md`:

      projection, year 2025
        revenue  = 1000 * 1.10                      = 1100
        EBIT     = 1100 * 20%                       =  220
        NOPAT    = 220 * (1 - 25%)                  =  165
        D&A      = 1100 * 10%                       =  110
        CapEx    = 1100 *  5%                       =   55
        dNWC     = 1100 *  2%                       =   22
        FCFF     = 165 + 110 - 55 - 22              =  198

      CAPM   Re  = Rf + beta * ERP = 4% + 1.0 * 6%  =   10.00%

      WACC   E   = 45.00 * 100 shares              = 4500
             D   = 0 + 0 + 500                     =  500
             E/V = 4500/5000 = 90%,  D/V = 10%
             WACC = 0.9*10% + 0.1*6%*(1-25%)
                  = 9% + 0.45%                     =    9.45%

      DCF    PV(FCFF) = 198 / 1.0945               =  180.90  -> "181"
             TV       = 198 * 1.02 / (0.0945-0.02) = 2710.87  -> "2,711"
             PV(TV)   = 2710.87 / 1.0945           = 2476.81  -> "2,477"
             EV       = 180.90 + 2476.81           = 2657.72  -> "2,658"
             net debt = 500 - 100                  =  400
             equity   = 2657.72 - 400              = 2257.72  -> "2,258"
             price    = 2257.72 / 100 shares       =   22.577 -> "$22.58"
             upside   = (22.577/45 - 1) * 100      =  -49.83% -> "-49.8%"

    Not one of those numbers was read off a rendered page.
    """
    monkeypatch.setattr(
        routes_valuation,
        "extract_financials",
        lambda *a, **k: (_one_year_financials(), []),
    )
    monkeypatch.setattr(routes_valuation, "fetch_price_data", lambda *a, **k: _price_data())

    body = _run_valuation(client)

    assert "DCF Valuation: TESTCO" in body
    assert "alert-error" not in body, "the success path rendered the error page"

    assert re.search(
        r'<h3>Implied Share Price</h3>\s*<div class="big-number">\$22\.58</div>', body
    )
    assert re.search(
        r'<h3>Current Price</h3>\s*<div class="big-number">\$45\.00</div>', body
    )
    assert re.search(
        r'<h3>Upside / Downside</h3>\s*<div class="big-number">-49\.8%</div>', body
    )

    # Literal template text, so jinja does not escape the ampersand.
    capm = _rows_under(body, "CAPM & WACC")
    assert capm["Beta"] == "1.000"
    assert capm["Risk-Free Rate"] == "4.00%"
    assert capm["Equity Risk Premium"] == "6.00%"
    assert capm["Cost of Equity"] == "10.00%"
    assert capm["Cost of Debt (pre-tax)"] == "6.00%"
    assert capm["Tax Rate"] == "25.00%"
    assert capm["Equity Weight (E/V)"] == "90.0%"
    assert capm["Debt Weight (D/V)"] == "10.0%"
    assert capm["WACC"] == "9.45%"

    assert _projection_row(body) == [
        "2025", "1,100", "220", "165", "110", "55", "22", "198",
    ]

    bridge = _rows_under(body, "DCF Valuation Bridge")
    assert bridge["PV of Projected FCFFs"] == "181"
    assert bridge["Terminal Value (undiscounted)"] == "2,711"
    assert bridge["PV of Terminal Value"] == "2,477"
    assert bridge["Enterprise Value"] == "2,658"
    assert bridge["Less: Net Debt"] == "(400)"
    assert bridge["Equity Value"] == "2,258"
    assert bridge["Diluted Shares Outstanding"] == "100"
    assert bridge["Implied Share Price"] == "$22.58"

    used = _rows_under(body, "Assumptions Used")
    assert used["Projection Years"] == "1"
    assert used["Terminal Growth Rate"] == "2.00%"
    assert used["Revenue Growth Rates"] == "10.0%"
    assert used["Operating Margin"] == "20.0%"
    assert used["Tax Rate"] == "25.0%"
    assert used["D&A (% of Revenue)"] == "10.0%"
    assert used["CapEx (% of Revenue)"] == "5.0%"
    assert used["NWC (% of Revenue)"] == "2.0%"


def test_post_valuation_shows_and_subtracts_the_noncontrolling_interests(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P10a step 5: the result page shows the NCI term and its source, and the
    bridge subtracts it. The inputs are the test above's, with the two printed
    NCI lines set to 40 (nonredeemable) and 10 (redeemable) instead of 0.

    NCI enters neither the projection nor WACC (`analysis/wacc.py` reads debt
    and market cap only), so every figure above the bridge is the test above's:

      EV       = 198/1.0945 + (198*1.02/0.0745)/1.0945
               = 180.905 + 2476.813                    = 2657.718 -> "2,658"
      net debt = 500 - 100                             =  400     -> "(400)"
      NCI      = 40 + 10                               =   50     -> "(50)"
      equity   = 2657.718 - 400 - 50                   = 2207.718 -> "2,208"
      price    = 2207.718 / 100 shares                 =   22.077 -> "$22.08"
    """
    base = _one_year_financials()
    (sheet,) = base.balance_sheets
    sheet.noncontrolling_interest_nonredeemable = 40.0
    sheet.noncontrolling_interest_redeemable = 10.0
    monkeypatch.setattr(routes_valuation, "extract_financials", lambda *a, **k: (base, []))
    monkeypatch.setattr(routes_valuation, "fetch_price_data", lambda *a, **k: _price_data())

    body = _run_valuation(client)

    assert "alert-error" not in body, "the success path rendered the error page"
    bridge = _rows_under(body, "DCF Valuation Bridge")
    assert bridge["Enterprise Value"] == "2,658"
    assert bridge["Less: Net Debt"] == "(400)"
    assert bridge["Less: Noncontrolling Interest"] == "(50)"
    assert bridge["Equity Value"] == "2,208"
    assert bridge["Implied Share Price"] == "$22.08"
    # Rule 4: the source row names both printed parts and their figures.
    assert "nonredeemable 40 + redeemable 10" in body
    assert "total_noncontrolling_interest" in body


def test_post_valuation_names_who_read_the_filing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rule 6: the result page names provider, model, transport and credential.

    Expected values from `docs/8-build/environment.md` section 3, not from the
    code: the only provider default is `claude`; the default Claude model is
    `claude-opus-5`; and with no Foundry variable set the transport is "the
    public Anthropic API". The `client` fixture pins exactly that environment.
    """
    monkeypatch.setattr(
        routes_valuation,
        "extract_financials",
        lambda *a, **k: (_one_year_financials(), []),
    )
    monkeypatch.setattr(routes_valuation, "fetch_price_data", lambda *a, **k: _price_data())

    body = _run_valuation(client)

    extraction = _rows_under(body, "Extraction — who read the filing")
    assert extraction["Provider"] == "CLAUDE"
    assert extraction["Model"] == "claude-opus-5"
    assert "Anthropic" in extraction["Transport"]
    assert "api.anthropic.com" in extraction["Transport"]
    assert "Foundry" not in extraction["Transport"]
    assert "ANTHROPIC_API_KEY" in extraction["Credential source"]


def test_post_valuation_distinguishes_the_two_transports(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same model, different road: rule 6 requires the page to tell them apart.

    Expected value from `docs/8-build/environment.md` section 3's transport
    table: with `ANTHROPIC_FOUNDRY_BASE_URL` set the transport is the Microsoft
    Foundry gateway, and the page must say so and must not claim the public API.
    Only the environment is read — no client is built and no request is made.
    """
    monkeypatch.setattr(
        routes_valuation,
        "extract_financials",
        lambda *a, **k: (_one_year_financials(), []),
    )
    monkeypatch.setattr(routes_valuation, "fetch_price_data", lambda *a, **k: _price_data())
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_BASE_URL", "https://gw.example.invalid/api")
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_API_KEY", "placeholder-no-call-is-made")

    body = _run_valuation(client)

    extraction = _rows_under(body, "Extraction — who read the filing")
    assert extraction["Provider"] == "CLAUDE"
    assert extraction["Model"] == "claude-opus-5"
    assert "Foundry" in extraction["Transport"]
    assert "gw.example.invalid" in extraction["Transport"]
    assert "api.anthropic.com" not in extraction["Transport"]
    # A label, never a credential: the key itself must not reach the page.
    assert "placeholder-no-call-is-made" not in body


def test_post_valuation_reports_a_failure_on_a_rendered_page(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The error branch of the result page, which is where the outage hid.

    Expected values: 200, the failure's text visible to the reader, and no
    valuation figure anywhere on the page — a run that failed must not show a
    share price. Independent of how the route catches the failure, so backlog
    item 8 cannot turn it red.
    """
    message = "market data unavailable for TESTCO"

    def failing_fetch(*args: object, **kwargs: object) -> None:
        raise RuntimeError(message)

    monkeypatch.setattr(
        routes_valuation,
        "extract_financials",
        lambda *a, **k: (_one_year_financials(), []),
    )
    monkeypatch.setattr(routes_valuation, "fetch_price_data", failing_fetch)

    response = client.post("/valuation", data=VALUATION_FORM)

    assert response.status_code == 200
    body = response.text
    assert "Internal Server Error" not in body
    assert "alert-error" in body
    assert message in body
    assert "DCF Valuation: TESTCO" in body
    assert "big-number" not in body, "a failed run showed a valuation figure"
    assert "Implied Share Price" not in body


@pytest.mark.parametrize("missing", ["ticker"])
def test_post_valuation_stops_and_names_a_missing_required_field(
    client: TestClient, missing: str
) -> None:
    """Rule 3 at the HTTP boundary. `ticker: str = Form(...)` is the one form
    field `run_valuation` declares without a default
    (`api/routes_valuation.py:129`), so its absence must stop the request and
    name it rather than reach the pipeline.
    """
    form = {k: v for k, v in VALUATION_FORM.items() if k != missing}

    response = client.post("/valuation", data=form)

    assert response.status_code == 422
    assert missing in response.text
