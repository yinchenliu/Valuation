"""The six context keys `P8a-statements-data` added, on every branch that renders.

Done-criteria 6 and 7 of `.agent/assignments/P8a-statements-data.md`: all six
keys are set on `GET /assumptions` and on `POST /valuation`, on the success
branch **and** on the error branch.

Why a test rather than a glance at the source: an undefined name in a Jinja
context renders as nothing. A template reading `historical_fcff` on a branch
that never set it shows an empty table, and shows it exactly as it would show a
filing with no computable years. Nothing fails, nothing is logged, and the two
cases are indistinguishable in the browser. So "the key is defined on every
branch" has to be checked where the branch actually runs.

No network, no key, no PDF: `extract_financials`, `extract_multi_year` and
`fetch_price_data` are boundaries and are faked
(`docs/5-testing/strategy.md` section 3). The paths named in the form are never
opened.

Every expected figure below is derived by hand above the assertion that uses
it. Nothing came from running the route.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

import app as app_module
import pipeline
from api import routes_valuation
from ingestion.price_fetcher import PriceData
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)

# The six keys `P8b-statements-ui` is written against. Written out here, not
# read back off the context, so a key that disappears is a failure and not an
# empty loop.
SIX_KEYS = (
    "raw_financials",
    "financials",
    "applied_non_recurring",
    "excluded_non_recurring",
    "historical_fcff",
    "assumption_sources",
)

SIX_RATIOS = (
    "revenue_growth_rates",
    "operating_margin",
    "tax_rate",
    "da_pct_revenue",
    "capex_pct_revenue",
    "nwc_pct_revenue",
)


# --------------------------------------------------------------------------
# Fixtures, by hand.
# --------------------------------------------------------------------------


def _two_year_financials() -> FinancialStatements:
    """Two complete years.

    year  revenue  SG&A  EBIT  margin  tax_exp  EBT  tax rate
    2023     1000   800   200    0.20       50  200      0.25
    2024     1200   960   240    0.20       60  240      0.25

    year  D&A  D&A%  capex  capex%   dWC   nwc%
    2023  100  0.10    -50    0.05   -20   0.02
    2024  120  0.10    -60    0.05   -24   0.02
    """
    return FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=[
            IncomeStatement(year=2023, revenue=1000.0, sga=800.0, tax_expense=50.0,
                            diluted_shares_outstanding=100.0),
            IncomeStatement(year=2024, revenue=1200.0, sga=960.0, tax_expense=60.0,
                            diluted_shares_outstanding=100.0),
        ],
        balance_sheets=[
            # NCI: explicit 0.0 for both printed lines; this company has none
            # (P10a). A value, not a default: None would stop run_dcf.
            BalanceSheet(year=2024, cash_and_equivalents=100.0, long_term_debt=500.0,
                         noncontrolling_interest_nonredeemable=0.0,
                         noncontrolling_interest_redeemable=0.0,
                         printed_unit_in_millions=1.0),
        ],
        cash_flow_statements=[
            CashFlowStatement(year=2023, depreciation_amortization=100.0,
                              capital_expenditures=-50.0,
                              change_in_working_capital=-20.0),
            CashFlowStatement(year=2024, depreciation_amortization=120.0,
                              capital_expenditures=-60.0,
                              change_in_working_capital=-24.0),
        ],
    )


def _high_confidence_item() -> NonRecurringItem:
    """A 40.0 restructuring charge sitting in 2024 SG&A. APPLIED.

    `add_back` means the charge inflated an expense, so removing it improves
    adjusted earnings. SG&A is an expense line, so the field moves DOWN by 40
    while earnings move UP by 40 (`analysis/normalizer.py:186-197`).

        raw        2024 SG&A 960 -> EBIT 1200 - 960 = 240
        normalised 2024 SG&A 920 -> EBIT 1200 - 920 = 280
    """
    return NonRecurringItem(
        year=2024,
        description="Restructuring charge",
        amount=40.0,
        line_item="sga",
        direction="add_back",
        category="restructuring",
        confidence="high",
        page=1,
        printed_units="(Amounts in millions)",
        units_page=1,
    )


def _low_confidence_item() -> NonRecurringItem:
    """A 500.0 item the extractor was not sure about. WITHHELD, never applied.

    Deliberately an order of magnitude larger than the applied one: if the
    partition leaked it into the adjustment, 2024 EBIT would be 780 rather than
    280 and the assertion on the raw/normalised pair below would say so.
    """
    return NonRecurringItem(
        year=2024,
        description="Possible litigation accrual",
        amount=500.0,
        line_item="sga",
        direction="add_back",
        category="litigation",
        confidence="low",
        page=1,
        printed_units="(Amounts in millions)",
        units_page=1,
    )


def _price_data() -> PriceData:
    """Market data, hand-built. `yfinance` is a boundary.

    The returns are never regressed: the form supplies `beta_override` and an
    explicit equity risk premium. `current_price` is read for the market cap in
    WACC and for the upside comparison.
    """
    return PriceData(
        ticker="TESTCO",
        stock_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        dates=pd.DatetimeIndex(pd.date_range("2024-01-31", periods=3, freq="D")),
        current_price=45.0,
        periods_per_year=12,
    )


VALUATION_FORM = {
    "ticker": "TESTCO",
    "company_name": "Test Company Inc",
    "files": "2024:c:/tmp/p8a-context-keys-never-opened.pdf",
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


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Record every template context the routes build, and still render.

    `templates.TemplateResponse` is wrapped rather than replaced, so the page is
    still rendered and a context key that the template chokes on still produces
    the 500 it would in a browser.
    """
    contexts: list[dict[str, Any]] = []
    real = routes_valuation.templates.TemplateResponse

    def recording(request, name, context, *args, **kwargs):  # type: ignore[no-untyped-def]
        contexts.append(dict(context))
        return real(request, name, context, *args, **kwargs)

    monkeypatch.setattr(routes_valuation.templates, "TemplateResponse", recording)
    return contexts


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client over the real app with every boundary closed loudly."""
    monkeypatch.setattr(routes_valuation, "_extraction_cache", {}, raising=False)

    for var in (
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_FOUNDRY_RESOURCE",
        "ANTHROPIC_FOUNDRY_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "placeholder-no-call-is-made")

    def _closed_boundary(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "a unit test reached a boundary it did not fake: "
            f"args={args!r} kwargs={kwargs!r}"
        )

    monkeypatch.setattr(routes_valuation, "extract_financials", _closed_boundary)
    monkeypatch.setattr(routes_valuation, "extract_multi_year", _closed_boundary)
    monkeypatch.setattr(pipeline, "fetch_price_data", _closed_boundary)

    return TestClient(app_module.app, raise_server_exceptions=False)


def _fake_extraction(monkeypatch: pytest.MonkeyPatch, items: list[NonRecurringItem]) -> None:
    def fake(*args: object, **kwargs: object):
        return _two_year_financials(), list(items)

    monkeypatch.setattr(routes_valuation, "extract_financials", fake)
    monkeypatch.setattr(routes_valuation, "extract_multi_year", fake)


def _failing_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(*args: object, **kwargs: object):
        raise ValueError("the extractor could not read this filing")

    monkeypatch.setattr(routes_valuation, "extract_financials", fake)
    monkeypatch.setattr(routes_valuation, "extract_multi_year", fake)


# --------------------------------------------------------------------------
# GET /assumptions
# --------------------------------------------------------------------------


def test_get_assumptions_success_sets_all_six_keys_and_both_sides_of_the_adjustment(
    client: TestClient,
    captured: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Criterion 6, success branch, plus the raw/normalised pair the unit exists for.

    Hand arithmetic, from `_high_confidence_item` and `_low_confidence_item`:

        raw        2024 EBIT = 1200 - 960 = 240
        normalised 2024 EBIT = 1200 - 920 = 280   (the 40 add-back landed)

    If the low-confidence 500 had leaked into the adjustment the normalised
    EBIT would be 780, so the withholding is falsifiable here and not merely
    asserted by the partition's own test.
    """
    _fake_extraction(
        monkeypatch, [_high_confidence_item(), _low_confidence_item()]
    )

    response = client.get(
        "/assumptions",
        params={
            "ticker": "TESTCO",
            "company_name": "Test Company Inc",
            "files": "2024:c:/tmp/p8a-context-keys-never-opened.pdf",
        },
    )
    assert response.status_code == 200
    assert len(captured) == 1
    context = captured[0]

    for key in SIX_KEYS:
        assert key in context, key

    assert context["error"] is None

    # Both sides of the reconciliation are reachable, which is the rule 4 gap
    # this unit closed.
    raw = context["raw_financials"]
    normalised = context["financials"]
    assert raw is not None and normalised is not None
    assert raw.get_income_statement(2024).ebit == pytest.approx(240.0)
    assert normalised.get_income_statement(2024).ebit == pytest.approx(280.0)

    # Applied and withheld are both named, and the withheld one is not in the
    # applied list.
    assert [i.description for i in context["applied_non_recurring"]] == [
        "Restructuring charge"
    ]
    assert [i.description for i in context["excluded_non_recurring"]] == [
        "Possible litigation accrual"
    ]

    # One row per extracted year, both computable on this fixture.
    assert [row.year for row in context["historical_fcff"]] == [2023, 2024]
    assert all(row.is_computable for row in context["historical_fcff"])

    # CONTRACT: empty, or exactly six entries. Never partial.
    assert set(context["assumption_sources"]) == set(SIX_RATIOS)


def test_get_assumptions_error_branch_sets_all_six_keys(
    client: TestClient,
    captured: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Criterion 6, error branch. Defined and empty, never absent.

    `assumption_sources` must be `{}` and not six labels: no ratio was derived,
    and six labels here would describe a run that did not happen. This asserts
    the stated contract for a branch with no data, not a fallback for a figure.
    """
    _failing_extraction(monkeypatch)

    response = client.get(
        "/assumptions",
        params={"ticker": "TESTCO", "files": "2024:c:/tmp/p8a-never-opened.pdf"},
    )
    assert response.status_code == 200
    context = captured[0]

    for key in SIX_KEYS:
        assert key in context, key

    assert context["error"] == "the extractor could not read this filing"
    assert context["raw_financials"] is None
    assert context["financials"] is None
    assert context["applied_non_recurring"] == []
    assert context["excluded_non_recurring"] == []
    assert context["historical_fcff"] == []
    assert context["assumption_sources"] == {}


def test_get_assumptions_with_no_filing_named_sets_all_six_keys(
    client: TestClient, captured: list[dict[str, Any]]
) -> None:
    """Criterion 6, the third branch: no filing was named, so nothing ran."""
    response = client.get("/assumptions", params={"ticker": "TESTCO"})
    assert response.status_code == 200
    context = captured[0]

    for key in SIX_KEYS:
        assert key in context, key

    assert context["raw_financials"] is None
    assert context["assumption_sources"] == {}


# --------------------------------------------------------------------------
# POST /valuation
# --------------------------------------------------------------------------


def test_post_valuation_success_sets_all_six_keys(
    client: TestClient,
    captured: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Criterion 7, success branch.

    The form supplies all six ratios, so every label must read `supplied` — a
    figure the reader typed is not a measurement, and the result page has to say
    so (rule 6). That is also what distinguishes this from the assumptions page,
    where the same six came back `derived`.
    """
    _fake_extraction(
        monkeypatch, [_high_confidence_item(), _low_confidence_item()]
    )
    monkeypatch.setattr(
        pipeline, "fetch_price_data", lambda *a, **k: _price_data()
    )

    response = client.post("/valuation", data=VALUATION_FORM)
    assert response.status_code == 200
    context = captured[0]
    assert context.get("error") is None

    for key in SIX_KEYS:
        assert key in context, key

    assert context["raw_financials"] is not None
    assert context["financials"] is not None
    assert context["raw_financials"].get_income_statement(2024).ebit == pytest.approx(240.0)
    assert context["financials"].get_income_statement(2024).ebit == pytest.approx(280.0)
    assert [i.description for i in context["applied_non_recurring"]] == [
        "Restructuring charge"
    ]
    assert [i.description for i in context["excluded_non_recurring"]] == [
        "Possible litigation accrual"
    ]
    assert [row.year for row in context["historical_fcff"]] == [2023, 2024]

    sources = context["assumption_sources"]
    assert set(sources) == set(SIX_RATIOS)
    for ratio in SIX_RATIOS:
        assert sources[ratio].origin == "supplied", ratio
        assert sources[ratio].observations == 0, ratio


def test_post_valuation_error_branch_sets_all_six_keys(
    client: TestClient,
    captured: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Criterion 7, error branch. Defined and empty on all six."""
    _failing_extraction(monkeypatch)

    response = client.post("/valuation", data=VALUATION_FORM)
    assert response.status_code == 200
    context = captured[0]

    assert context["error"]
    for key in SIX_KEYS:
        assert key in context, key

    assert context["raw_financials"] is None
    assert context["financials"] is None
    assert context["applied_non_recurring"] == []
    assert context["excluded_non_recurring"] == []
    assert context["historical_fcff"] == []
    assert context["assumption_sources"] == {}


def test_the_cached_extraction_carries_all_four_fields_to_the_result_page(
    client: TestClient,
    captured: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cache-HIT branch must produce the same four values as the cache-miss one.

    Two branches producing different values is how a page reports one exclusion
    and computes with another. Here `GET /assumptions` fills the cache, then the
    boundary is closed again so that `POST /valuation` CANNOT re-extract: if it
    took the miss branch it would hit `_closed_boundary` and fail loudly rather
    than quietly agreeing.

    The four values asserted are the ones derived by hand above: raw 2024 EBIT
    240, normalised 280, one applied item, one withheld.
    """
    _fake_extraction(
        monkeypatch, [_high_confidence_item(), _low_confidence_item()]
    )
    files = VALUATION_FORM["files"]
    assumptions_response = client.get(
        "/assumptions", params={"ticker": "TESTCO", "files": files}
    )
    assert assumptions_response.status_code == 200

    # Close the extraction boundary: the POST below must read the cache.
    def _closed(*args: object, **kwargs: object) -> None:
        raise AssertionError("POST /valuation re-extracted instead of reading the cache")

    monkeypatch.setattr(routes_valuation, "extract_financials", _closed)
    monkeypatch.setattr(routes_valuation, "extract_multi_year", _closed)
    monkeypatch.setattr(
        pipeline, "fetch_price_data", lambda *a, **k: _price_data()
    )

    response = client.post("/valuation", data=VALUATION_FORM)
    assert response.status_code == 200

    result_context = captured[-1]
    assert result_context.get("error") is None
    assert result_context["raw_financials"].get_income_statement(2024).ebit == pytest.approx(240.0)
    assert result_context["financials"].get_income_statement(2024).ebit == pytest.approx(280.0)
    assert [i.description for i in result_context["applied_non_recurring"]] == [
        "Restructuring charge"
    ]
    assert [i.description for i in result_context["excluded_non_recurring"]] == [
        "Possible litigation accrual"
    ]

    # And the two branches agree with the assumptions page that filled the cache.
    assumptions_context = captured[0]
    assert (
        result_context["raw_financials"].get_income_statement(2024).ebit
        == assumptions_context["raw_financials"].get_income_statement(2024).ebit
    )
    assert (
        result_context["excluded_non_recurring"]
        == assumptions_context["excluded_non_recurring"]
    )
