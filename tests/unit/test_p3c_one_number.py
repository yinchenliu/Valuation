"""One filing, one share price — `P3c-one-number` (backlog items 87, 92, 6, 97).

**What this file locks.**

  1. An untouched assumptions form and `pipeline.value_company` with no override
     price the same filing at the **same number** (item 87), and posting the
     figure the placeholder shows gives a **different**, lower one. Both halves
     are needed: without the second, the first would pass on a filing whose
     ratios round cleanly and prove nothing.
  2. A blank ratio field is `None` with origin `derived`; a typed `0` is `0.0`
     with origin `supplied` (item 6, rule 6).
  3. The CLI's historical FCFF table and the web's are built from the same
     statements and give the same figure for every year (item 92), and both name
     that basis in the same words (rule 6).
  4. A year the FCFF table cannot compute is printed with its reason by both
     entry points, and no figure is invented for it (rule 3).
  5. A multi-line stop renders with its newlines intact (item 97).

**Where every expected value comes from.** `docs/5-testing/strategy.md` section 1:
the expected side of an assertion must exist before the code runs. Here each one
is

  * **hand arithmetic** over `_unrounded_financials()`, written out in the block
    comment beside it. Every figure in that filing was chosen so the whole chain
    is checkable on paper: three revenue years in a ratio of 1 : 1.1 : 1.21, so
    the CAGR is exactly 10%; operating margins of exactly 1/7, 1/7 and 2/7 after
    the one non-recurring item lands, so the derived mean is exactly 4/21; D&A,
    CapEx and NWC at exactly 10%, 5% and 2% of revenue in every year.
  * a **closed-form identity**: two entry points running the same function on the
    same statements with the same overrides must return the same float, whatever
    that float is. The identity is the requirement; the number is not asserted.
  * a **monotonicity argument**: the DCF's FCFF is increasing in the operating
    margin and nothing else in the chain reads it, so a *smaller* margin must
    give a *smaller* share price. 19.0% < 19.047619…%, so the price a reader gets
    by typing the placeholder back must be below the price they get by leaving
    the field alone.

No number below was obtained by running the code and reading what it printed.

**The trap this file is built to avoid** is backlog item 108. The repository's
session-file fixture derives ratios of 30.0%, 20.0%, 3.0%, 7.0%, 1.5% and 100.0%,
each already exact to one decimal place — so rounding one to one decimal place
changes nothing and an item-87 regression test built on it is green before the
fix and after it. `_unrounded_financials()` exists because of that: its adjusted
operating margin is 4/21, which is 19.047619…%, and
`test_the_premise_of_this_file` fails if that ever stops being true.

**No key, no PDF, no network.** `extract_financials` and `pipeline.fetch_price_data`
are replaced; `TestClient` opens no socket.
"""

from __future__ import annotations

import argparse
import io
import re
from contextlib import redirect_stdout

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

import app as app_module
import cli
import pipeline
from api import routes_upload, routes_valuation
from ingestion.price_fetcher import PriceData
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)
from models.valuation import ProjectionAssumptions
from tests.unit._html_form import parse_form, placeholders
from tests.unit._session_route_helpers import (
    UnreadableErrorBox,
    error_text,
    require_error_text,
)

# The six ratio fields the form posts and the route converts. The names are the
# route's own `Form(...)` parameter names (`api/routes_valuation.py:531-535` and
# `:530`), not anything read off a page.
RATIO_FIELDS = (
    "revenue_growth",
    "operating_margin",
    "tax_rate",
    "da_pct",
    "capex_pct",
    "nwc_pct",
)

# The six keys `derive_assumptions` labels in its `sources` dict
# (`analysis/projector.py`'s docstring, "sources is a dict[str, AssumptionSource]
# under the same six ratio keys").
RATIO_KEYS = (
    "revenue_growth_rates",
    "operating_margin",
    "tax_rate",
    "da_pct_revenue",
    "capex_pct_revenue",
    "nwc_pct_revenue",
)

# The basis sentence, written out here as a literal. It is a literal in THREE
# implementation files — `cli.HISTORICAL_FCFF_BASIS`,
# `templates/assumptions.html` and `templates/valuation_result.html` — with
# nothing in the implementation checking that the three still agree (the
# programmer's finding F1, the reviewer's F2). This constant is the fourth copy
# and the only one that checks the other three.
HISTORICAL_FCFF_BASIS = (
    "Computed from the normalised statements, "
    "the same statements the valuation used."
)


# ---------------------------------------------------------------------------
# The filing, by hand
#
# Three fiscal years. Every figure is chosen so the whole chain is checkable on
# paper, and so that ONE derived ratio does not survive a round to one decimal
# place — which is the defect under test and the thing the repository's existing
# fixture cannot see (backlog item 108).
#
#                       2022      2023      2024
#   revenue              700       770       847      ratio 1 : 1.1 : 1.21
#   sga                  600       660       726
#   EBIT = rev - sga     100       110       121      margin 1/7 in every year
#   interest expense      10        10        10
#   EBT  = EBIT - int     90       100       111
#   tax expense         22.50     25.00     27.75     effective rate 25% each
#
# One non-recurring item: 2024, `sga`, `add_back`, 121, confidence `high`.
#   `adjusted_impact` is +121 (add_back); `sga` carries earnings sign -1
#   (`analysis/normalizer.py:55`), so the field moves by -121:
#     adjusted sga   2024 = 726 - 121 = 605
#     adjusted EBIT  2024 = 847 - 605 = 242       margin 242/847 = 2/7
#     adjusted EBT   2024 = 242 -  10 = 232
#     adjusted eff tax rate 2024 = 27.75 / 232    (was 27.75 / 111 = 25%)
#
# DERIVED, on the ADJUSTED statements (`analysis/projector.derive_assumptions`):
#
#   revenue growth  lookback = min(3, 3-1) = 2, so CAGR over 700 -> 847 in two
#                   periods = (847/700) ** (1/2) - 1 = 1.21 ** 0.5 - 1 = 1.1 - 1
#                                                                     = 0.10
#   operating margin  mean(1/7, 1/7, 2/7) = (4/7)/3 = 4/21 = 0.190476190476...
#   tax rate          mean(0.25, 0.25, 27.75/232)
#   D&A   % revenue   mean(70/700, 77/770, 84.7/847)       = 0.10
#   CapEx % revenue   mean(35/700, 38.5/770, 42.35/847)    = 0.05
#   NWC   % revenue   mean(14/700, 15.4/770, 16.94/847)    = 0.02
#
# 4/21 is 19.047619...%, and `f"{x * 100:.1f}"` shows it as "19.0". Those are
# different numbers, and that difference is backlog item 87.
# ---------------------------------------------------------------------------

DERIVED_OPERATING_MARGIN = 4 / 21          # mean(1/7, 1/7, 2/7)
DERIVED_OPERATING_MARGIN_SHOWN = "19.0"    # f"{4/21 * 100:.1f}"
DERIVED_TAX_RATE = (0.25 + 0.25 + 27.75 / 232) / 3
DERIVED_GROWTH = 0.10                      # (847/700) ** 0.5 - 1
DERIVED_DA_PCT = 0.10
DERIVED_CAPEX_PCT = 0.05
DERIVED_NWC_PCT = 0.02


def _income(year: int, revenue: float, sga: float, tax: float) -> IncomeStatement:
    return IncomeStatement(
        year=year,
        revenue=revenue,
        sga=sga,
        interest_expense=10.0,
        tax_expense=tax,
        diluted_shares_outstanding=100.0,
    )


def _cash_flow(year: int, net_income: float, revenue: float) -> CashFlowStatement:
    """D&A 10%, CapEx 5%, working-capital outflow 2% of the year's revenue."""
    return CashFlowStatement(
        year=year,
        net_income=net_income,
        depreciation_amortization=revenue * 0.10,
        change_in_working_capital=-revenue * 0.02,
        capital_expenditures=-revenue * 0.05,
    )


def _unrounded_financials(*, drop_2023_cash_flow: bool = False) -> FinancialStatements:
    """The filing above, as extracted. The non-recurring item is separate."""
    cash_flows = [
        # net income = EBT - tax: 90 - 22.50, 100 - 25.00, 111 - 27.75.
        _cash_flow(2022, 67.50, 700.0),
        _cash_flow(2023, 75.00, 770.0),
        _cash_flow(2024, 83.25, 847.0),
    ]
    if drop_2023_cash_flow:
        cash_flows = [cf for cf in cash_flows if cf.year != 2023]

    return FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=[
            _income(2022, 700.0, 600.0, 22.50),
            _income(2023, 770.0, 660.0, 25.00),
            _income(2024, 847.0, 726.0, 27.75),
        ],
        balance_sheets=[
            # Net debt = 500 - 100 = 400. The two NCI lines are explicit zeros —
            # this company has none — because `None` stops `run_dcf` (P10a).
            BalanceSheet(
                year=2024,
                cash_and_equivalents=100.0,
                long_term_debt=500.0,
                noncontrolling_interest_nonredeemable=0.0,
                noncontrolling_interest_redeemable=0.0,
                printed_unit_in_millions=1.0,
            ),
        ],
        cash_flow_statements=cash_flows,
    )


def _one_non_recurring_item() -> NonRecurringItem:
    """2024, sga, add_back, 121. `high`, so `partition_by_confidence` applies it."""
    return NonRecurringItem(
        year=2024,
        description="One-time restructuring charge, hand-built",
        amount=121.0,
        line_item="sga",
        direction="add_back",
        category="restructuring",
        confidence="high",
        page=1,
        printed_units="(Amounts in millions)",
        units_page=1,
    )


def _adjusted() -> FinancialStatements:
    """What both entry points value: the statements after the item lands."""
    return pipeline.adjust_financials(
        _unrounded_financials(), [_one_non_recurring_item()]
    ).adjusted


def _price_data() -> PriceData:
    """Market data, hand-built. `yfinance` is a boundary — strategy.md section 3.

    Stock returns and market returns are the SAME series, so the regression of
    one on the other has slope exactly 1.0 — the identity in
    `docs/5-testing/strategy.md` section 1. Nothing here needs to be true of any
    real company: both entry points read the same object, which is what the
    identity under test requires.
    """
    return PriceData(
        ticker="TESTCO",
        stock_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        dates=pd.DatetimeIndex(pd.date_range("2024-01-31", periods=3, freq="D")),
        current_price=45.0,
        periods_per_year=12,
    )


# The `cli.py` command line with NO valuation override given, as `cli.py:160-182`
# declares its defaults. Read off the argument declarations — a contract stated
# outside the code path under test — not off a run.
CLI_NO_OVERRIDE_DEFAULTS = {
    "projection_years": 5,
    "terminal_growth": None,
    "revenue_growth": None,
    "operating_margin": None,
    "tax_rate": None,
    "capex_pct": None,
    "da_pct": None,
    "nwc_pct": None,
    "risk_free_rate": None,
    "equity_risk_premium": None,
    "beta": None,
    "cost_of_debt": None,
    "confirm_zero_debt": False,
    "lookback_years": 5,
    "frequency": "monthly",
}


def _cli_overrides() -> ProjectionAssumptions:
    """What `cli.py` builds when the reader overrides nothing."""
    return cli.build_overrides(argparse.Namespace(**CLI_NO_OVERRIDE_DEFAULTS))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FILES = "2024:c:/tmp/p3c-never-opened.pdf"
BASE_FORM = {"ticker": "TESTCO", "company_name": "Test Company Inc", "files": FILES}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    """A client over the real app with every boundary closed and loudly faked."""
    monkeypatch.setattr(routes_upload, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(routes_valuation, "_extraction_cache", {}, raising=False)
    for var in (
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_FOUNDRY_RESOURCE",
        "ANTHROPIC_FOUNDRY_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "placeholder-no-call-is-made")

    def _closed(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            f"a unit test reached a boundary it did not fake: {args!r} {kwargs!r}"
        )

    monkeypatch.setattr(routes_valuation, "extract_multi_year", _closed)
    monkeypatch.setattr(routes_valuation, "extract_financials", _closed)
    monkeypatch.setattr(pipeline, "fetch_price_data", _closed)
    return TestClient(app_module.app, raise_server_exceptions=False)


@pytest.fixture
def filing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hand-built filing and the hand-built market, behind both boundaries."""
    monkeypatch.setattr(
        routes_valuation,
        "extract_financials",
        lambda *a, **k: (_unrounded_financials(), [_one_non_recurring_item()]),
    )
    monkeypatch.setattr(pipeline, "fetch_price_data", lambda *a, **k: _price_data())


@pytest.fixture
def valuations(monkeypatch: pytest.MonkeyPatch) -> list:
    """Record `(overrides, ValuationRun)` for every `POST /valuation`.

    A spy around the real `value_company`, so the route runs the real valuation
    and the test reads the result at full float precision instead of off a page
    the template has already rounded to the cent.
    """
    recorded: list = []
    real = routes_valuation.value_company

    def spy(adjusted, overrides, **kwargs):
        run = real(adjusted, overrides, **kwargs)
        recorded.append((overrides, run))
        return run

    monkeypatch.setattr(routes_valuation, "value_company", spy)
    return recorded


def _untouched_form(client: TestClient) -> dict[str, str]:
    """`GET /assumptions`, then what a browser would POST having typed nothing."""
    page = client.get("/assumptions", params=BASE_FORM)
    assert page.status_code == 200
    assert "Internal Server Error" not in page.text
    assert "alert-error" not in page.text, "the assumptions page rendered an error"
    return parse_form(page.text, "/valuation")


def _post(client: TestClient, form: dict[str, str]) -> str:
    response = client.post("/valuation", data=form)
    assert response.status_code == 200
    assert "Internal Server Error" not in response.text
    return response.text


# ===========================================================================
# 0. The premise: this filing CAN see backlog item 87
# ===========================================================================


def test_the_premise_of_this_file_a_ratio_that_does_not_round(
    client: TestClient, filing: None
) -> None:
    """The derived operating margin is 4/21, and "19.0" is not 4/21.

    This is the guard on backlog item 108. The repository's session fixture
    derives six ratios that are each already exact to one decimal place, so a
    test for item 87 built on it is green before the fix and after it. Every
    assertion in this file rests on the filing above NOT having that property,
    and this test is what fails if that ever stops being true.

    Hand arithmetic: the three adjusted operating margins are 100/700, 110/770
    and 242/847 — that is 1/7, 1/7 and 2/7 — so their mean is (4/7)/3 = 4/21.
    4/21 = 0.190476190476…, which `f"{x * 100:.1f}"` shows as "19.0".
    """
    adjusted = _adjusted()

    assert adjusted.get_income_statement(2024).sga == pytest.approx(605.0)   # 726 - 121
    assert adjusted.get_income_statement(2024).ebit == pytest.approx(242.0)  # 847 - 605
    margins = [
        adjusted.get_income_statement(y).operating_margin for y in (2022, 2023, 2024)
    ]
    assert margins == pytest.approx([1 / 7, 1 / 7, 2 / 7])

    assert DERIVED_OPERATING_MARGIN == pytest.approx(0.19047619047619047, rel=1e-15)
    assert f"{DERIVED_OPERATING_MARGIN * 100:.1f}" == DERIVED_OPERATING_MARGIN_SHOWN
    # The whole of item 87, in one line: what is shown is not what was derived.
    assert float(DERIVED_OPERATING_MARGIN_SHOWN) / 100 != DERIVED_OPERATING_MARGIN

    # And the page shows that rounded figure in both places a reader can see it.
    page = client.get("/assumptions", params=BASE_FORM)
    assert placeholders(page.text, "/valuation")["operating_margin"] == (
        DERIVED_OPERATING_MARGIN_SHOWN
    )
    assert f">{DERIVED_OPERATING_MARGIN_SHOWN}%<" in page.text


# ===========================================================================
# 1. The one number (assignment step 3)
# ===========================================================================


def test_an_untouched_form_prices_the_filing_exactly_as_the_cli_does(
    client: TestClient, filing: None, valuations: list
) -> None:
    """The identity: two entry points, one filing, one share price.

    Expected value: a **closed-form identity**, not a figure. `POST /valuation`
    and `cli.py` both end in `pipeline.value_company(adjusted, overrides, ...)`.
    Hand the same statements and the same overrides to one function and it must
    return the same float — so if the two prices differ, something between the
    form and that call changed an input. Before `P3c-one-number` something did:
    the form posted its derived ratios back, rounded to one decimal place.

    The POST body is not written out here. It is parsed off the rendered page by
    `_html_form.parse_form`, so this test submits what a browser would submit and
    goes red if a `value` attribute ever returns to any of the six fields.
    """
    form = _untouched_form(client)

    # Nothing is typed: every ratio field is submitted, and submitted empty.
    for field in RATIO_FIELDS:
        assert form[field] == "", field

    _post(client, form)
    web_overrides, web_run = valuations[-1]

    # The route built the same overrides `cli.py` builds with no flag given.
    assert web_overrides == _cli_overrides()

    cli_run = pipeline.value_company(
        _adjusted(),
        _cli_overrides(),
        ticker="TESTCO",
        lookback_years=5,
        frequency="monthly",
    )

    web_price = web_run.dcf_result.implied_share_price
    cli_price = cli_run.dcf_result.implied_share_price

    # Equal as IEEE-754 doubles — every binary digit, not "to the cent".
    assert web_price == cli_price, f"web {web_price!r} != cli {cli_price!r}"
    assert float(web_price) - float(cli_price) == 0.0

    # And the figure is real: a filing that priced at nothing would make the
    # identity above vacuous.
    assert float(web_price) > 0.0


def test_typing_the_figure_the_placeholder_shows_gives_a_lower_price(
    client: TestClient, filing: None, valuations: list
) -> None:
    """The companion fact, without which the identity above proves nothing.

    Expected value: a **monotonicity argument**, derived before the run. The DCF
    reads the operating margin in exactly one place — `calculate_fcff_projected`
    sets `ebit = revenue * operating_margin` (`analysis/fcff.py`) — and nothing
    else in the chain reads it: WACC is built from the balance sheet, the market
    data and the cost of debt, and net debt from the balance sheet. So FCFF, and
    therefore the equity value and the share price, are strictly increasing in
    the operating margin.

    19.0% is the figure the placeholder shows. 4/21 is 19.047619…%. The first is
    the smaller, so typing it back must give the SMALLER price. That is the whole
    of backlog item 87, stated as an inequality that is true before the code runs.
    """
    form = _untouched_form(client)
    _post(client, form)
    blank_overrides, blank_run = valuations[-1]
    blank_price = float(blank_run.dcf_result.implied_share_price)

    # Exactly what a reader does when they copy the grey figure into the box.
    typed = dict(form, operating_margin=DERIVED_OPERATING_MARGIN_SHOWN)
    _post(client, typed)
    typed_overrides, typed_run = valuations[-1]
    typed_price = float(typed_run.dcf_result.implied_share_price)

    # The two runs differ in exactly one input, and in the direction stated.
    assert blank_overrides.operating_margin is None
    assert typed_overrides.operating_margin == 0.19
    assert typed_overrides.operating_margin < DERIVED_OPERATING_MARGIN

    assert typed_price != blank_price
    assert typed_price < blank_price

    # Reported so the entry can quote the size of the gap this unit closed.
    gap = blank_price - typed_price
    assert gap > 0.0
    print(
        f"\nblank {blank_price!r}  typed-the-placeholder {typed_price!r}  "
        f"gap {gap!r} = {gap / blank_price:.6%}"
    )


# ===========================================================================
# 2. Blank means derive, a typed 0 means zero (assignment step 4)
# ===========================================================================


def test_an_untouched_form_builds_six_derived_and_no_supplied(
    client: TestClient, filing: None, valuations: list
) -> None:
    """Blank is not missing: it is the reader declining to override.

    Expected values: `ProjectionAssumptions`'s documented contract — a ratio of
    `None` means "derive it" (`analysis/projector.py:226`, `if
    ov.operating_margin is not None`) — and rule 6, which requires the platform's
    own figure to be labelled as the platform's. Six blank fields, six `derived`.
    """
    form = _untouched_form(client)
    _post(client, form)
    overrides, run = valuations[-1]

    assert overrides.operating_margin is None
    assert overrides.tax_rate is None
    assert overrides.da_pct_revenue is None
    assert overrides.capex_pct_revenue is None
    assert overrides.nwc_pct_revenue is None
    assert overrides.revenue_growth_rates == []

    origins = {key: run.assumptions["sources"][key].origin for key in RATIO_KEYS}
    assert origins == dict.fromkeys(RATIO_KEYS, "derived")

    # Derived at FULL precision — the hand arithmetic in the block comment above.
    assert run.assumptions["operating_margin"] == pytest.approx(
        DERIVED_OPERATING_MARGIN, rel=1e-12
    )
    assert run.assumptions["tax_rate"] == pytest.approx(DERIVED_TAX_RATE, rel=1e-12)
    assert run.assumptions["da_pct_revenue"] == pytest.approx(DERIVED_DA_PCT, rel=1e-12)
    assert run.assumptions["capex_pct_revenue"] == pytest.approx(
        DERIVED_CAPEX_PCT, rel=1e-12
    )
    assert run.assumptions["nwc_pct_revenue"] == pytest.approx(
        DERIVED_NWC_PCT, rel=1e-12
    )
    assert run.assumptions["revenue_growth_rates"] == pytest.approx(
        [DERIVED_GROWTH] * 5, rel=1e-12
    )


def test_a_typed_zero_is_a_zero_and_is_labelled_supplied(
    client: TestClient, filing: None, valuations: list
) -> None:
    """A reader who types 0 means 0%, and is told the figure was theirs.

    Expected values: the route's declared conversion,
    `float(operating_margin) / 100 if operating_margin.strip() else None`
    (`api/routes_valuation.py:650`). `"0".strip()` is truthy, so a typed zero
    survives as `0.0`. Backlog item 6: the old `float = Form(0)` field with
    `x / 100 if x else None` read it as "not supplied" and silently derived
    instead — the reader's deliberate zero vanished with no word anywhere.

    And at a 0% operating margin the valuation is arithmetic anyone can check:
    EBIT is 0 in every projected year, so NOPAT is 0; D&A, CapEx and NWC are
    10%, 5% and 2% of revenue, so FCFF is +3% of revenue each year and the
    equity value is that stream, discounted, less net debt of 400. It is a
    different number from the derived run, and that is all this test claims.
    """
    form = dict(_untouched_form(client), operating_margin="0")
    _post(client, form)
    overrides, run = valuations[-1]

    assert overrides.operating_margin == 0.0
    assert overrides.operating_margin is not None
    assert run.assumptions["operating_margin"] == 0.0
    assert run.assumptions["sources"]["operating_margin"].origin == "supplied"


# (form field, what is typed, the ProjectionAssumptions attribute, the value).
# Each typed figure divided by 100 is exact in binary — 12.5/100 = 0.125,
# 6.25/100 = 0.0625, 3.125/100 = 0.03125, 25/100 = 0.25 — so the expected side
# is an exact equality, not an approximation, and the arithmetic is one division
# anyone can do in their head. The conversion is the route's own, declared at
# `api/routes_valuation.py:650-654`: `float(x) / 100 if x.strip() else None`.
TYPED_RATIOS = [
    ("revenue_growth", "12.5, 6.25", "revenue_growth_rates", [0.125, 0.0625]),
    ("operating_margin", "12.5", "operating_margin", 0.125),
    ("tax_rate", "25", "tax_rate", 0.25),
    ("da_pct", "6.25", "da_pct_revenue", 0.0625),
    ("capex_pct", "3.125", "capex_pct_revenue", 0.03125),
    ("nwc_pct", "12.5", "nwc_pct_revenue", 0.125),
]


@pytest.mark.parametrize(
    ("field", "typed", "attribute", "expected"),
    TYPED_RATIOS,
    ids=[row[0] for row in TYPED_RATIOS],
)
def test_each_ratio_field_converts_at_the_boundary_and_is_labelled_supplied(
    client: TestClient, filing: None, valuations: list,
    field: str, typed: str, attribute: str, expected: object,
) -> None:
    """All six conversions, both sides of each: typed and blank.

    Expected values: hand arithmetic on the route's declared conversion — a
    percentage divided by 100, once, at the route boundary. Every figure here
    divides exactly in binary, so each assertion is an exact equality.

    This parametrisation exists because the tests above exercise
    `operating_margin` and `tax_rate` and leave `da_pct`, `capex_pct`,
    `nwc_pct` and `revenue_growth` with only their blank branch run. Four of the
    five sites this unit rewrote would then have had their typed branch
    untouched by any test, and a branch no test enters cannot fail.
    """
    form = dict(_untouched_form(client), **{field: typed})
    _post(client, form)
    overrides, run = valuations[-1]

    assert getattr(overrides, attribute) == expected
    assert run.assumptions["sources"][attribute].origin == "supplied"

    # The other five stayed blank, and blank still means derive.
    others = [key for key in RATIO_KEYS if key != attribute]
    assert [run.assumptions["sources"][key].origin for key in others] == ["derived"] * 5


@pytest.mark.parametrize("field", [row[0] for row in TYPED_RATIOS[1:]])
def test_a_typed_zero_survives_in_every_one_of_the_five_ratio_fields(
    client: TestClient, filing: None, valuations: list, field: str,
) -> None:
    """Backlog item 6, closed for all five fields — not only the one tested above.

    Expected value: `"0".strip()` is a non-empty string, so the route's declared
    conversion gives `0.0 / 100 = 0.0`. The old `float = Form(0)` field with
    `x / 100 if x else None` read it as absent and derived instead, so a reader's
    deliberate zero was replaced by a platform figure with no word anywhere.
    """
    attribute = {row[0]: row[2] for row in TYPED_RATIOS}[field]
    form = dict(_untouched_form(client), **{field: "0"})
    _post(client, form)
    overrides, run = valuations[-1]

    assert getattr(overrides, attribute) == 0.0
    assert getattr(overrides, attribute) is not None
    assert run.assumptions["sources"][attribute].origin == "supplied"


def test_one_field_typed_gives_one_supplied_and_five_derived(
    client: TestClient, filing: None, valuations: list
) -> None:
    """Rule 6: the page says which of the six came from the reader.

    Expected values: the same contract as above, counted. One typed field is one
    `supplied`; the other five are blank, so they are `derived`. Before this unit
    every untouched run reported six `supplied` for figures the platform itself
    had produced.
    """
    form = dict(_untouched_form(client), tax_rate="30")
    body = _post(client, form)
    overrides, run = valuations[-1]

    assert overrides.tax_rate == pytest.approx(0.30)  # 30 / 100, at the boundary
    origins = {key: run.assumptions["sources"][key].origin for key in RATIO_KEYS}
    assert origins["tax_rate"] == "supplied"
    assert sorted(origins.values()) == ["derived"] * 5 + ["supplied"]

    # And the reader can see it: the result page says so in words, rule 6.
    assert body.count("supplied by the caller") == 1
    assert body.count("derived from the filing") == 5


# ===========================================================================
# 3. The FCFF table, and the basis both entry points name (assignment step 5)
# ===========================================================================

# Hand arithmetic from `analysis/fcff.calculate_fcff_historical`:
#
#     FCFF = CFO + |interest expense| * (1 - t) - |CapEx|
#     t    = the YEAR'S effective tax rate on the statements handed in
#     CFO  = net income + D&A + SBC + change in WC + other   (the model's property)
#
#   2022  CFO = 67.50 + 70.0  - 14.00 = 123.50
#         t = 22.50/90 = 0.25, so interest after tax = 10 * 0.75 = 7.50
#         CapEx = 35.00
#         FCFF = 123.50 + 7.50 - 35.00                        =  96.00
#
#   2023  CFO = 75.00 + 77.0  - 15.40 = 136.60
#         t = 25.00/100 = 0.25  -> 7.50 ; CapEx = 38.50
#         FCFF = 136.60 + 7.50 - 38.50                        = 105.60
#
#   2024  CFO = 83.25 + 84.7  - 16.94 = 151.01
#         ADJUSTED t = 27.75/232, so interest after tax
#                    = 10 * (1 - 27.75/232) = 2042.5/232      =   8.80387931...
#         CapEx = 42.35
#         FCFF = 151.01 + 8.80387931... - 42.35               = 117.46387931...
#
#   2024 on the RAW statements, for contrast: t = 27.75/111 = 0.25, so interest
#   after tax is 7.50 and FCFF = 151.01 + 7.50 - 42.35 = 116.16. The CLI printed
#   that one until `P3c-one-number` while the web page printed 117 for the same
#   filing — backlog item 92. Rounded to the whole million the two are 116 and
#   117, so the assertion below sees the difference.
HAND_FCFF_2022 = 123.50 + 10.0 * (1 - 0.25) - 35.00
HAND_FCFF_2023 = 136.60 + 10.0 * (1 - 0.25) - 38.50
HAND_FCFF_2024_ADJUSTED = 151.01 + 10.0 * (1 - 27.75 / 232) - 42.35
HAND_FCFF_2024_RAW = 151.01 + 10.0 * (1 - 0.25) - 42.35


def _cli_fcff_table(financials: FinancialStatements) -> dict[int, list[str]]:
    """`cli.print_historical_fcff`'s rows, by year, as the columns it printed."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        cli.print_historical_fcff(financials, cli.HISTORICAL_FCFF_BASIS)
    rows: dict[int, list[str]] = {}
    for line in buffer.getvalue().splitlines():
        cells = line.split()
        if cells and re.fullmatch(r"(19|20)\d\d", cells[0]):
            rows[int(cells[0])] = cells[1:]
    return rows


def test_the_hand_fcff_figures_are_what_both_entry_points_report() -> None:
    """Both tables, against the arithmetic above — and against each other.

    Expected values: `HAND_FCFF_*`, written out from `analysis/fcff.py`'s formula
    in the block comment above. Neither table is compared to the other first:
    each is compared to the hand figure, so a test that went green on two tables
    that agreed on a wrong number is not possible here.
    """
    adjusted = _adjusted()

    # The web's rows.
    rows = {row.year: row for row in routes_valuation._historical_fcff_by_year(adjusted)}
    assert sorted(rows) == [2022, 2023, 2024]
    assert rows[2022].fcff.fcff == pytest.approx(HAND_FCFF_2022, rel=1e-12)
    assert rows[2023].fcff.fcff == pytest.approx(HAND_FCFF_2023, rel=1e-12)
    assert rows[2024].fcff.fcff == pytest.approx(HAND_FCFF_2024_ADJUSTED, rel=1e-12)

    # The CLI's rows. Column 5 of the banner's heading is FCFF
    # (Year, Revenue, CFO, Int*(1-t), CapEx, FCFF, FCFF%), printed `:,.0f`.
    printed = _cli_fcff_table(adjusted)
    assert sorted(printed) == [2022, 2023, 2024]
    assert printed[2022][4] == f"{HAND_FCFF_2022:,.0f}"
    assert printed[2023][4] == f"{HAND_FCFF_2023:,.0f}"
    assert printed[2024][4] == f"{HAND_FCFF_2024_ADJUSTED:,.0f}"

    # Which is NOT the figure the raw statements give, so this assertion is the
    # one that goes red if stage 5 is handed `financials` again (item 92). 117
    # against 116, with the same filing and the same formula.
    assert f"{HAND_FCFF_2024_RAW:,.0f}" != f"{HAND_FCFF_2024_ADJUSTED:,.0f}"
    assert printed[2024][4] != f"{HAND_FCFF_2024_RAW:,.0f}"

    # And every year agrees, entry point to entry point.
    for year in (2022, 2023, 2024):
        assert printed[year][4] == f"{rows[year].fcff.fcff:,.0f}", year


def test_cli_main_builds_its_fcff_table_from_the_normalised_statements(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Stage 5's ARGUMENT, which the test above cannot see.

    `test_the_hand_fcff_figures_are_what_both_entry_points_report` calls
    `print_historical_fcff(adjusted, ...)` itself, so it proves the function
    right and says nothing about what `main` hands it — and backlog item 92 was
    never in the function, it was in the call: stage 5 passed `financials` while
    the DCF two stages later ran on `adjusted`. A test that chooses the argument
    itself cannot fail on that, which is backlog item 98's lesson in a different
    costume. So this one runs `cli.main()` and reads what it printed.

    `cli.main()` is the entry `cli.py`'s `if __name__ == "__main__"` calls.
    **Not `runpy.run_path`**: that executes the file into a fresh namespace, so
    none of the patches below would be the names the fresh copy binds (backlog
    item 98). Every patch here is on an attribute of the `cli` module object that
    `main` reads through that module.

    Expected values: `HAND_FCFF_*`, the arithmetic in the block comment above.
    2024 is 117 on the normalised statements and 116 on the extracted ones, so
    this assertion moves if the argument does.
    """
    def _closed(*args: object, **kwargs: object) -> None:
        raise AssertionError("cli.main reached a boundary it did not fake")

    def fake_session(args: argparse.Namespace):
        args.ticker = "TESTCO"
        args.company_name = "Test Company Inc"
        return (
            _unrounded_financials(),
            [_one_non_recurring_item()],
            "hand-built",
            "hand-built",
        )

    runs: list = []
    real = cli.value_company

    def spy(adjusted, overrides, **kwargs):
        run = real(adjusted, overrides, **kwargs)
        runs.append(run)
        return run

    monkeypatch.setattr(cli, "_extract_from_session_file", fake_session)
    monkeypatch.setattr(cli, "_extract_via_api", _closed)
    monkeypatch.setattr(cli, "value_company", spy)
    monkeypatch.setattr(pipeline, "fetch_price_data", lambda *a, **k: _price_data())
    monkeypatch.setattr(
        "sys.argv", ["cli.py", "--session-file", "p3c-never-opened.json"]
    )

    cli.main()
    printed = capsys.readouterr().out

    section = printed[printed.index("HISTORICAL FCFF") :]
    rows: dict[int, list[str]] = {}
    for line in section.splitlines():
        cells = line.split()
        if cells and re.fullmatch(r"(19|20)\d\d", cells[0]):
            rows[int(cells[0])] = cells[1:]
        if cells and cells[0].startswith("==") and rows:
            break

    assert sorted(rows) == [2022, 2023, 2024]
    assert rows[2022][4] == f"{HAND_FCFF_2022:,.0f}"
    assert rows[2023][4] == f"{HAND_FCFF_2023:,.0f}"
    assert rows[2024][4] == f"{HAND_FCFF_2024_ADJUSTED:,.0f}"
    assert rows[2024][4] != f"{HAND_FCFF_2024_RAW:,.0f}"

    # And the basis is named in the run a reader actually sees.
    assert HISTORICAL_FCFF_BASIS in section

    # One run, and the same ratios the untouched web form derives.
    assert len(runs) == 1
    assert runs[0].assumptions["operating_margin"] == pytest.approx(
        DERIVED_OPERATING_MARGIN, rel=1e-12
    )


def test_cli_main_and_an_untouched_form_reach_the_same_share_price(
    client: TestClient, filing: None, valuations: list,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """The identity again, end to end, through the entry points themselves.

    The identity test above compares `POST /valuation` to a direct
    `pipeline.value_company` call that this file assembles. This one compares it
    to what `cli.main()` does with no override flag, so nothing between
    `parse_args` and the DCF is chosen by the test on the CLI side either.

    Expected value: the identity. One filing, one market, one price.
    """
    form = _untouched_form(client)
    _post(client, form)
    web_price = float(valuations[-1][1].dcf_result.implied_share_price)

    def fake_session(args: argparse.Namespace):
        args.ticker = "TESTCO"
        args.company_name = "Test Company Inc"
        return (
            _unrounded_financials(),
            [_one_non_recurring_item()],
            "hand-built",
            "hand-built",
        )

    runs: list = []
    real = cli.value_company
    monkeypatch.setattr(cli, "_extract_from_session_file", fake_session)
    monkeypatch.setattr(
        cli,
        "value_company",
        lambda a, o, **k: runs.append(real(a, o, **k)) or runs[-1],
    )
    monkeypatch.setattr(
        "sys.argv", ["cli.py", "--session-file", "p3c-never-opened.json"]
    )
    cli.main()
    capsys.readouterr()

    cli_price = float(runs[-1].dcf_result.implied_share_price)
    assert cli_price == web_price, f"cli {cli_price!r} != web {web_price!r}"


def test_the_basis_sentence_is_word_for_word_the_same_in_three_renderings(
    client: TestClient, filing: None
) -> None:
    """Rule 6: the table says which statements it was built from, once, everywhere.

    Expected value: the sentence, written out as `HISTORICAL_FCFF_BASIS` at the
    top of this file. It is a literal in three implementation files with nothing
    in the implementation checking that they match (the reviewer's finding F2), so
    this constant is the check. A reword in one place now goes red here.
    """
    assert cli.HISTORICAL_FCFF_BASIS == HISTORICAL_FCFF_BASIS

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        cli.print_historical_fcff(_adjusted(), cli.HISTORICAL_FCFF_BASIS)
    assert HISTORICAL_FCFF_BASIS in buffer.getvalue()

    assumptions_page = client.get("/assumptions", params=BASE_FORM).text
    assert HISTORICAL_FCFF_BASIS in assumptions_page

    result_page = _post(client, _untouched_form(client))
    assert HISTORICAL_FCFF_BASIS in result_page


# ===========================================================================
# 4. The year that cannot be computed (assignment step 6)
# ===========================================================================


def test_a_year_with_no_cash_flow_statement_is_named_by_both_entry_points(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rule 3: the year stays in the table and says what was missing.

    Expected values: the contract of `_historical_fcff_by_year`'s docstring —
    "where either is absent the year still gets a row, marked absent and naming
    what was missing" — and the words `_statements.html` renders for that row,
    which `cli.py` now prints for the same row. No expected FCFF figure exists
    for 2023 here, which is the point: nothing may be invented for it.

    This is **not** a test of a fallback. It asserts that the year is reported and
    that NO number is produced for it; a fix that made the whole run stop instead
    would be a different behaviour, and the assertions on 2022 and 2024 below say
    nothing about 2023's figure in either direction.
    """
    statements = _unrounded_financials(drop_2023_cash_flow=True)
    adjusted = pipeline.adjust_financials(
        statements, [_one_non_recurring_item()]
    ).adjusted

    rows = {row.year: row for row in routes_valuation._historical_fcff_by_year(adjusted)}
    assert sorted(rows) == [2022, 2023, 2024]
    assert rows[2023].is_computable is False
    assert rows[2023].fcff is None
    assert rows[2023].missing_statements == ("cash flow statement",)
    # The other two are untouched by the gap, and still match the hand figures.
    assert rows[2022].fcff.fcff == pytest.approx(HAND_FCFF_2022, rel=1e-12)
    assert rows[2024].fcff.fcff == pytest.approx(HAND_FCFF_2024_ADJUSTED, rel=1e-12)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        cli.print_historical_fcff(adjusted, cli.HISTORICAL_FCFF_BASIS)
    printed = buffer.getvalue()

    # The year is in the table, with its reason — not dropped by a bare
    # `continue`, which is what happened before `P3c-one-number`.
    assert "2023  not extracted: cash flow statement" in printed
    row_2023 = next(ln for ln in printed.splitlines() if ln.strip().startswith("2023"))
    # No figure was invented for it: the only digits on the row are the year.
    assert re.sub(r"\D", "", row_2023) == "2023", row_2023

    # And the web entry point renders the same words on the page.
    monkeypatch.setattr(
        routes_valuation,
        "extract_financials",
        lambda *a, **k: (statements, [_one_non_recurring_item()]),
    )
    monkeypatch.setattr(pipeline, "fetch_price_data", lambda *a, **k: _price_data())
    page = client.get("/assumptions", params=BASE_FORM).text
    assert "not extracted" in page
    assert "2023" in page


# ===========================================================================
# 5. The readable stop (assignment step 7)
# ===========================================================================


def test_a_multi_line_stop_renders_with_its_newlines_on_both_pages(
    client: TestClient,
) -> None:
    """Backlog item 97: a stop a reader can read.

    Expected values: the CSS contract, not this repository's. `white-space:
    pre-line` is the one value of that property that preserves a newline in HTML
    source while still collapsing runs of spaces (CSS Text Module Level 3). The
    stop used is `P3b`'s yearless-filing stop, which prints a file list and two
    remedies, so the message genuinely has newlines to lose.

    Nothing here asserts the wording of the stop — `P3b`'s own tests own that.
    This asserts that whatever the stop says arrives with its line breaks.
    """
    params = {"ticker": "T", "company_name": "T", "files": "0:a.pdf,2025:b.pdf"}

    page = client.get("/assumptions", params=params)
    assert page.status_code == 200
    assert '<div class="alert alert-error" style="white-space: pre-line">' in page.text
    shown = require_error_text(page.text)
    assert "a.pdf" in shown
    assert "\n" in shown, f"the stop arrived as one line: {shown!r}"
    assert len([ln for ln in shown.splitlines() if ln.strip()]) >= 3

    result = client.post("/valuation", data=dict(params, files="0:a.pdf,2025:b.pdf"))
    assert result.status_code == 200
    assert '<div class="alert alert-error" style="white-space: pre-line">' in result.text
    shown = require_error_text(result.text)
    assert "a.pdf" in shown
    assert "\n" in shown, f"the stop arrived as one line: {shown!r}"


# ===========================================================================
# 6. The helper that reads the box (assignment step 2, backlog item 107)
# ===========================================================================


def test_error_text_reads_the_box_on_the_upload_page() -> None:
    """`templates/upload.html`, which this helper could never read before.

    `upload.html:11` has carried `style="white-space: pre-line"` since before
    `19fe831`, and the helper's pattern required the div to carry NO attribute.
    So the one page the helper was blind to was blind in silence: it returned
    `None`, which every caller read as "this page reported no error".

    Expected value: the string handed to the template. The template is rendered
    through the application's own jinja environment, so this is the real file.
    """
    rendered = routes_upload.templates.env.get_template("upload.html").render(
        error="first line\nsecond line"
    )
    assert error_text(rendered) == "first line\nsecond line"


def test_error_text_returns_none_only_when_the_page_has_no_box() -> None:
    """A page with no error box is reported as having none. Not an error.

    Several tests assert `error_text(body) is None` to mean "this page reported
    success", so that reading must survive. What must NOT survive is `None`
    meaning two things at once — see the next test.
    """
    rendered = routes_upload.templates.env.get_template("upload.html").render(error="")
    assert "alert alert-error" not in rendered
    assert error_text(rendered) is None


def test_error_text_raises_when_the_box_is_there_and_it_cannot_read_it() -> None:
    """Backlog item 107: two faults must not share one return value.

    Before this unit the helper returned `None` both when the page carried no
    error box and when it carried one the pattern could not parse. The second is
    the helper being out of date with the template, and it is what happened on
    2026-10-05: twenty tests in four files failed with `assert None is not None`,
    a message that names neither the page, nor the box, nor the pattern.

    Expected value: the exception type and that its message names the pattern.
    The input is a box this helper's pattern cannot close — a single-quoted
    attribute holding a `>` — not anything the templates render today.
    """
    body = '<p>x</p><div class="alert alert-error" data-x=\'a>b\'>boom'
    with pytest.raises(UnreadableErrorBox, match="alert-error"):
        error_text(body)


def test_require_error_text_fails_by_name_when_there_is_no_box() -> None:
    """The stop-path form: "the reader was told", stated so its failure says so.

    Expected value: the exception type, and that the message names the box it
    looked for rather than reading `assert None is not None`.
    """
    with pytest.raises(AssertionError, match="no alert-error box on the page"):
        require_error_text("<html><body><p>all well</p></body></html>")
