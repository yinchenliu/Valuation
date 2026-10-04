"""Unit tests for statement UI rendering and data structures (P8b-statements-ui).

Verifies the seven statement blocks across GET /assumptions and POST /valuation:
  1. Adjusted Income Statement ($M)
  2. Cash Flow Statement ($M)
  3. Balance Sheet ($M) with balance_check_difference
  4. Non-recurring items APPLIED
  5. GAAP to Non-GAAP Reconciliation ($M)
  6. Historical Free Cash Flow to Firm (Post-Adjustment, $M)
  7. Assumptions Used (with source sentence and SUBSTITUTED badges)

Verifies Rule 3 handling:
  - Missing statements render "not extracted", never zero or default.
  - Substituted ratios carry the "SUBSTITUTED" marker and warning sentence.
  - Empty applied NRI renders "No non-recurring item was applied."
  - Imbalanced balance sheet difference is signed subtraction, no division.

Every expected value is derived by hand in comments above the assertion.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

import app as app_module
from analysis.projector import derive_assumptions
from api import routes_valuation
from ingestion.price_fetcher import PriceData
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)

SEVEN_BLOCK_HEADINGS = [
    "Adjusted Income Statement ($M)",
    "Cash Flow Statement ($M)",
    "Balance Sheet ($M)",
    "Non-recurring items APPLIED — these moved the figures above",
    "GAAP to Non-GAAP Reconciliation ($M)",
    "Historical Free Cash Flow to Firm (Post-Adjustment, $M)",
    "Assumptions Used",
]

SIX_RATIO_KEYS = [
    "revenue_growth_rates",
    "operating_margin",
    "tax_rate",
    "da_pct_revenue",
    "capex_pct_revenue",
    "nwc_pct_revenue",
]


# ---------------------------------------------------------------------------
# Hand-computed Fixtures
# ---------------------------------------------------------------------------

def _hand_built_two_year_stub() -> tuple[FinancialStatements, list[NonRecurringItem]]:
    """Two-year deterministic financial statements with 3 non-recurring items.

    Income Statement 2023:
      Revenue: 1000.0, COGS: 400.0 -> Gross Profit: 600.0 (60.0%)
      SG&A: 200.0, R&D: 50.0, D&A: 50.0 -> EBIT: 300.0 (30.0%)
      Interest: 20.0 -> EBT: 280.0
      Tax Expense: 70.0 -> Net Income: 210.0 (Tax Rate: 25.0%)
      Diluted Shares: 100.0 -> EPS: $2.10

    Income Statement 2024 (pre-adjustment):
      Revenue: 1200.0, COGS: 480.0 -> Gross Profit: 720.0 (60.0%)
      SG&A: 240.0, R&D: 60.0, D&A: 60.0 -> EBIT: 360.0 (30.0%)
      Interest: 20.0 -> EBT: 340.0
      Tax Expense: 85.0 -> Net Income: 255.0 (Tax Rate: 25.0%)
      Diluted Shares: 100.0 -> EPS: $2.55

    Non-recurring items for 2024:
      1. High confidence: 15.0 restructuring add_back to SG&A -> applied
      2. Medium confidence: 10.0 litigation add_back to SG&A -> applied
      3. Low confidence: 8.0 asset sale gain removal from SG&A -> WITHHELD (excluded)

    Adjusted Income Statement 2024:
      SG&A moves from 240.0 down by (15.0 + 10.0 = 25.0) to 215.0.
      Adjusted EBIT = 720.0 - 215.0 - 60.0 - 60.0 = 385.0.
      EBIT delta = 385.0 - 360.0 = +25.0.

    Cash Flow Statement:
      2023: CFO = 260.0, CapEx = -40.0
      2024: CFO = 310.0, CapEx = -50.0

    Balance Sheet 2024:
      Cash: 100.0, Short-term Inv: 50.0, AR: 80.0, Inv: 60.0, Other CA: 10.0 -> Total CA = 300.0
      PP&E: 400.0, Goodwill: 100.0, Intangibles: 50.0, Other NCA: 20.0 -> Total Assets = 870.0
      AP: 50.0, ST Debt: 30.0, Current LT Debt: 10.0, Accrued Liab: 20.0, Other CL: 10.0 -> Total CL = 120.0
      LT Debt: 200.0, Other NCL: 30.0 -> Total Liab = 350.0
      Equity: 520.0 -> Total Liab + Equity = 350.0 + 520.0 = 870.0
      Balance Check Difference = 870.0 - 870.0 = 0.0
      Total Debt = 30 + 10 + 200 = 240.0
      Net Debt = 240.0 - 100.0 - 50.0 = 90.0
      Net Working Capital = (300 - 150) - (120 - 40) = 150 - 80 = 70.0
    """
    inc = [
        IncomeStatement(
            year=2023,
            revenue=1000.0,
            cost_of_revenue=400.0,
            sga=200.0,
            rd_expense=50.0,
            depreciation_amortization=50.0,
            interest_expense=20.0,
            tax_expense=70.0,
            diluted_shares_outstanding=100.0,
        ),
        IncomeStatement(
            year=2024,
            revenue=1200.0,
            cost_of_revenue=480.0,
            sga=240.0,
            rd_expense=60.0,
            depreciation_amortization=60.0,
            interest_expense=20.0,
            tax_expense=85.0,
            diluted_shares_outstanding=100.0,
        ),
    ]
    cf = [
        CashFlowStatement(
            year=2023,
            net_income=210.0,
            depreciation_amortization=50.0,
            stock_based_compensation=10.0,
            change_in_working_capital=-15.0,
            other_operating_activities=5.0,
            capital_expenditures=-40.0,
            acquisitions=-20.0,
            debt_issued=50.0,
            debt_repaid=-10.0,
            shares_repurchased=-20.0,
            dividends_paid=-15.0,
        ),
        CashFlowStatement(
            year=2024,
            net_income=255.0,
            depreciation_amortization=60.0,
            stock_based_compensation=12.0,
            change_in_working_capital=-20.0,
            other_operating_activities=3.0,
            capital_expenditures=-50.0,
            other_investing_activities=-10.0,
            debt_repaid=-20.0,
            shares_issued=5.0,
            shares_repurchased=-10.0,
            dividends_paid=-20.0,
        ),
    ]
    bs = [
        BalanceSheet(
            year=2024,
            cash_and_equivalents=100.0,
            short_term_investments=50.0,
            accounts_receivable=80.0,
            inventory=60.0,
            other_current_assets=10.0,
            ppe_net=400.0,
            goodwill=100.0,
            intangible_assets=50.0,
            other_non_current_assets=20.0,
            accounts_payable=50.0,
            short_term_debt=30.0,
            current_portion_lt_debt=10.0,
            accrued_liabilities=20.0,
            other_current_liabilities=10.0,
            long_term_debt=200.0,
            other_non_current_liabilities=30.0,
            total_equity=520.0,
            # NCI memo lines: explicit 0.0, this company prints none (P10a).
            noncontrolling_interest_nonredeemable=0.0,
            noncontrolling_interest_redeemable=0.0,
            printed_unit_in_millions=1.0,
        ),
    ]
    fs = FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=inc,
        cash_flow_statements=cf,
        balance_sheets=bs,
    )
    nri = [
        NonRecurringItem(
            year=2024,
            amount=15.0,
            description="Restructuring facility closure",
            line_item="sga",
            category="restructuring",
            confidence="high",
            direction="add_back",
            page=1,
            printed_units="(Amounts in millions)",
            units_page=1,
            source="Note 12",
        ),
        NonRecurringItem(
            year=2024,
            amount=10.0,
            description="Litigation settlement fee",
            line_item="sga",
            category="litigation",
            confidence="medium",
            direction="add_back",
            page=1,
            printed_units="(Amounts in millions)",
            units_page=1,
            source="Note 14",
        ),
        NonRecurringItem(
            year=2024,
            amount=8.0,
            description="Asset sale gain",
            line_item="sga",
            category="other",
            confidence="low",
            direction="remove",
            page=1,
            printed_units="(Amounts in millions)",
            units_page=1,
            source="Note 16",
        ),
    ]
    return fs, nri


def _dummy_price_data() -> PriceData:
    return PriceData(
        ticker="TESTCO",
        stock_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        dates=pd.DatetimeIndex(pd.date_range("2024-01-31", periods=3, freq="D")),
        current_price=45.0,
        periods_per_year=12,
    )


VALUATION_FORM_DATA = {
    "ticker": "TESTCO",
    "company_name": "Test Company Inc",
    "files": "2023:test2023.pdf,2024:test2024.pdf",
    "projection_years": "5",
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
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(routes_valuation, "_extraction_cache", {}, raising=False)
    for var in (
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_FOUNDRY_RESOURCE",
        "ANTHROPIC_FOUNDRY_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder-no-call-is-made")

    def _closed_boundary(*args: object, **kwargs: object) -> None:
        raise AssertionError("boundary reached")

    monkeypatch.setattr(routes_valuation, "extract_financials", _closed_boundary)
    monkeypatch.setattr(routes_valuation, "extract_multi_year", _closed_boundary)
    monkeypatch.setattr(routes_valuation, "fetch_price_data", _closed_boundary)

    return TestClient(app_module.app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Direct Property Tests: BalanceSheet.balance_check_difference
# ---------------------------------------------------------------------------

def test_balance_check_difference_property_hand_computed() -> None:
    """Assignment step 12: balance_check_difference = total_assets - (total_liabilities + total_equity).

    Case 1: Exactly balanced
      total_assets = cash(100) + AR(200) + PPE(700) = 1000.0
      total_liab = AP(300) + LT_debt(300) = 600.0
      total_equity = 400.0
      total_liab + total_equity = 600.0 + 400.0 = 1000.0
      balance_check_difference = 1000.0 - 1000.0 = 0.0

    Case 2: Imbalanced (assets > liab + equity)
      total_assets = 1050.0
      total_liab + total_equity = 1000.0
      balance_check_difference = 1050.0 - 1000.0 = +50.0

    Case 3: Imbalanced (liab + equity > assets)
      total_assets = 970.0
      total_liab + total_equity = 1000.0
      balance_check_difference = 970.0 - 1000.0 = -30.0
    """
    # Case 1: Balanced -> 0.0
    bs_balanced = BalanceSheet(
        year=2024,
        cash_and_equivalents=100.0,
        accounts_receivable=200.0,
        ppe_net=700.0,
        accounts_payable=300.0,
        long_term_debt=300.0,
        total_equity=400.0,
        printed_unit_in_millions=1.0,
    )
    # Hand calculation: 1000.0 - (600.0 + 400.0) = 0.0
    assert bs_balanced.total_assets == 1000.0
    assert bs_balanced.total_liabilities == 600.0
    assert bs_balanced.total_equity == 400.0
    assert bs_balanced.balance_check_difference == pytest.approx(0.0)

    # Case 2: Asset-heavy -> +50.0
    bs_asset_heavy = BalanceSheet(
        year=2024,
        cash_and_equivalents=150.0,
        accounts_receivable=200.0,
        ppe_net=700.0,
        accounts_payable=300.0,
        long_term_debt=300.0,
        total_equity=400.0,
        printed_unit_in_millions=1.0,
    )
    # Hand calculation: 1050.0 - (600.0 + 400.0) = +50.0
    assert bs_asset_heavy.total_assets == 1050.0
    assert bs_asset_heavy.balance_check_difference == pytest.approx(50.0)

    # Case 3: Liability-heavy -> -30.0
    bs_liab_heavy = BalanceSheet(
        year=2024,
        cash_and_equivalents=70.0,
        accounts_receivable=200.0,
        ppe_net=700.0,
        accounts_payable=300.0,
        long_term_debt=300.0,
        total_equity=400.0,
        printed_unit_in_millions=1.0,
    )
    # Hand calculation: 970.0 - (600.0 + 400.0) = -30.0
    assert bs_liab_heavy.total_assets == 970.0
    assert bs_liab_heavy.balance_check_difference == pytest.approx(-30.0)


# ---------------------------------------------------------------------------
# Direct Function Tests: _build_ebit_reconciliation
# ---------------------------------------------------------------------------

def test_build_ebit_reconciliation_hand_computed() -> None:
    """Assignment step 12: build EBIT reconciliation between raw and normalised statements.

    Hand arithmetic:
      Year 2023:
        Raw EBIT = 1000 - 800 = 200.0
        Adj EBIT = 1000 - 800 = 200.0 (no adjustment)
        difference = 200.0 - 200.0 = 0.0
        missing_statement = None

      Year 2024:
        Raw EBIT = 1200 - 960 = 240.0
        Adj EBIT = 1200 - 920 = 280.0 (40.0 restructuring add_back)
        difference = 280.0 - 240.0 = +40.0
        missing_statement = None
    """
    raw_fs = FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=[
            IncomeStatement(year=2023, revenue=1000.0, sga=800.0),
            IncomeStatement(year=2024, revenue=1200.0, sga=960.0),
        ],
    )
    adj_fs = FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=[
            IncomeStatement(year=2023, revenue=1000.0, sga=800.0),
            IncomeStatement(year=2024, revenue=1200.0, sga=920.0),
        ],
    )

    records = routes_valuation._build_ebit_reconciliation(raw_fs, adj_fs)
    assert len(records) == 2

    # 2023: difference is 0.0
    assert records[0].year == 2023
    assert records[0].as_reported_ebit == pytest.approx(200.0)
    assert records[0].adjusted_ebit == pytest.approx(200.0)
    assert records[0].difference == pytest.approx(0.0)
    assert records[0].missing_statement is None

    # 2024: difference is +40.0 (280.0 - 240.0)
    assert records[1].year == 2024
    assert records[1].as_reported_ebit == pytest.approx(240.0)
    assert records[1].adjusted_ebit == pytest.approx(280.0)
    assert records[1].difference == pytest.approx(40.0)
    assert records[1].missing_statement is None


def test_build_ebit_reconciliation_missing_statement_flags() -> None:
    """Rule 3: a year missing from either side carries a named field, never a zero delta."""
    raw_fs = FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=[
            IncomeStatement(year=2023, revenue=1000.0, sga=800.0),
        ],
    )
    adj_fs = FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=[
            IncomeStatement(year=2024, revenue=1200.0, sga=920.0),
        ],
    )

    records = routes_valuation._build_ebit_reconciliation(raw_fs, adj_fs)
    assert len(records) == 2

    # 2023: raw present, adjusted missing
    assert records[0].year == 2023
    assert records[0].as_reported_ebit == pytest.approx(200.0)
    assert records[0].adjusted_ebit is None
    assert records[0].difference is None
    assert records[0].missing_statement == "adjusted income statement"

    # 2024: raw missing, adjusted present
    assert records[1].year == 2024
    assert records[1].as_reported_ebit is None
    assert records[1].adjusted_ebit == pytest.approx(280.0)
    assert records[1].difference is None
    assert records[1].missing_statement == "raw income statement"

    # None inputs return []
    assert routes_valuation._build_ebit_reconciliation(None, adj_fs) == []
    assert routes_valuation._build_ebit_reconciliation(raw_fs, None) == []


# ---------------------------------------------------------------------------
# Route Tests: 7 Blocks on GET /assumptions and POST /valuation
# ---------------------------------------------------------------------------

def test_get_assumptions_renders_seven_blocks_and_open_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criteria 5 & 3: GET /assumptions renders all 7 headings and collapsible blocks default to OPEN."""
    fs, nri = _hand_built_two_year_stub()
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs, nri))

    resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp.status_code == 200
    body = resp.text

    # All seven headings must appear
    for heading in SEVEN_BLOCK_HEADINGS:
        assert heading in body, f"Missing heading: {heading}"

    # On assumptions page, statements_open is true: <details class="statement-block" open>
    assert '<details class="statement-block" open>' in body


def test_post_valuation_renders_seven_blocks_closed_details_and_order(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 6 & steps 2, 3: POST /valuation renders all 7 headings, closed details, correct order.

    Order: DCF bridge (Implied Share Price) -> Statements -> What in this valuation was not measured.
    """
    fs, nri = _hand_built_two_year_stub()
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs, nri))
    monkeypatch.setattr(routes_valuation, "fetch_price_data", lambda *a, **k: _dummy_price_data())

    resp = client.post("/valuation", data=VALUATION_FORM_DATA)
    assert resp.status_code == 200
    body = resp.text

    for heading in SEVEN_BLOCK_HEADINGS:
        assert heading in body, f"Missing heading: {heading}"

    # On valuation result page, statements_open is false: details does not have open attribute
    details_tags = re.findall(r'<details class="statement-block"[^>]*>', body)
    assert len(details_tags) == 3
    for tag in details_tags:
        assert "open" not in tag, f"statement details should not be open on POST /valuation: {tag}"

    # Verify structural chain order
    idx_price = body.index("Implied Share Price")
    idx_statements = body.index("Adjusted Income Statement ($M)")
    idx_unmeasured = body.index("What in this valuation was not measured")
    assert idx_price < idx_statements < idx_unmeasured, (
        f"Chain order inverted: price({idx_price}) < statements({idx_statements}) < unmeasured({idx_unmeasured})"
    )


# ---------------------------------------------------------------------------
# Hand-computed Data and Arithmetic in Rendered Tables
# ---------------------------------------------------------------------------

def test_applied_items_table_filters_confidence_hand_computed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 8: The applied items table lists high and medium items and NOT low items.

    Hand expectations:
      - Applied (high): "Restructuring facility closure" -> +15.0 impact
      - Applied (medium): "Litigation settlement fee" -> +10.0 impact
      - Excluded (low): "Asset sale gain" -> NOT in applied table
    """
    fs, nri = _hand_built_two_year_stub()
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs, nri))

    resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp.status_code == 200
    body = resp.text

    applied_heading = "Non-recurring items APPLIED — these moved the figures above"
    start = body.index(applied_heading)
    end = body.index("</table>", start)
    applied_table = body[start:end]

    assert "Restructuring facility closure" in applied_table
    assert "+15" in applied_table
    assert "Litigation settlement fee" in applied_table
    assert "+10" in applied_table
    assert "Asset sale gain" not in applied_table


def test_ebit_reconciliation_delta_matches_hand_arithmetic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 9: Reconciliation delta equals sum of applied items' adjusted_impact.

    Hand arithmetic:
      Applied item 1 impact: +15.0
      Applied item 2 impact: +10.0
      Sum of applied impacts = 15.0 + 10.0 = +25.0
      Raw 2024 EBIT = 1200 - 480 - 240 - 60 - 60 = 360.0
      Adjusted 2024 EBIT = 1200 - 480 - 215 - 60 - 60 = 385.0
      Delta = 385 - 360 = +25.0
    """
    fs, nri = _hand_built_two_year_stub()
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs, nri))

    resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp.status_code == 200
    body = resp.text

    recon_heading = "GAAP to Non-GAAP Reconciliation ($M)"
    start = body.index(recon_heading)
    end = body.index("</table>", start)
    recon_table = body[start:end]

    # Find the row for 2024
    rows = re.findall(r"<tr>(.*?)</tr>", recon_table, re.DOTALL)
    row_2024_cells = None
    for r in rows:
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.DOTALL)]
        if cells and cells[0] == "2024":
            row_2024_cells = cells
            break

    assert row_2024_cells is not None, "2024 reconciliation row not found"
    # cells: [Year, EBIT as reported, EBIT adjusted, Difference]
    assert row_2024_cells[0] == "2024"
    assert row_2024_cells[1] == "360"
    assert row_2024_cells[2] == "385"
    assert row_2024_cells[3] == "+25"


def test_assumption_sources_rendered_verbatim(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 10: Every ratio carries its own source sentence rendered verbatim."""
    fs, nri = _hand_built_two_year_stub()
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs, nri))

    derived = derive_assumptions(fs)
    sources = derived["sources"]

    resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp.status_code == 200
    body = resp.text

    for key in SIX_RATIO_KEYS:
        detail = sources[key].detail
        assert detail in body, f"Assumption source detail for {key} missing: {detail}"


# ---------------------------------------------------------------------------
# Rule 3 Stop & Absent Statement Tests
# ---------------------------------------------------------------------------

def test_missing_cash_flow_statement_renders_not_extracted_and_no_zeros(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 7: A year with no cash flow statement renders 'not extracted' and NO zero in CFS cells."""
    fs, _ = _hand_built_two_year_stub()
    # Remove 2024 cash flow statement
    fs_partial_cf = FinancialStatements(
        ticker=fs.ticker,
        company_name=fs.company_name,
        income_statements=fs.income_statements,
        cash_flow_statements=[fs.cash_flow_statements[0]],  # 2023 only
        balance_sheets=fs.balance_sheets,
    )
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs_partial_cf, []))

    resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp.status_code == 200
    body = resp.text

    # Cash Flow Statement table inspection
    cf_start = body.index("Cash Flow Statement ($M)")
    cf_end = body.index("</table>", cf_start)
    cf_table = body[cf_start:cf_end]

    # Exactly 17 rows of financial line items in Cash Flow Statement
    # For 2024 (second year column), every single cell must be 'not extracted'
    not_extracted_count = cf_table.count("not extracted")
    assert not_extracted_count == 17, f"Expected 17 'not extracted' in CFS, got {not_extracted_count}"

    # Verify no '0', '0.0', or '-' fallback in 2024 cells
    for tr in re.findall(r"<tr>(.*?)</tr>", cf_table, re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)
        if len(cells) == 3:  # line item label, 2023, 2024
            y2024_val = re.sub(r"<[^>]+>", "", cells[2]).strip()
            assert y2024_val == "not extracted"
            assert y2024_val not in ("0", "0.0", "-")

    # In Historical FCFF table, 2024 must show 'not extracted: cash flow statement'
    fcff_start = body.index("Historical Free Cash Flow to Firm (Post-Adjustment, $M)")
    fcff_end = body.index("</table>", fcff_start)
    fcff_table = body[fcff_start:fcff_end]
    assert "not extracted: cash flow statement" in fcff_table


def test_missing_balance_sheet_renders_not_extracted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rule 3: Missing balance sheet renders '<p>not extracted</p>', never zero-filled tables."""
    fs, _ = _hand_built_two_year_stub()
    fs_no_bs = FinancialStatements(
        ticker=fs.ticker,
        company_name=fs.company_name,
        income_statements=fs.income_statements,
        cash_flow_statements=fs.cash_flow_statements,
        balance_sheets=[],
    )
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs_no_bs, []))

    resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp.status_code == 200
    body = resp.text

    bs_start = body.index("Balance Sheet ($M)")
    bs_end = body.index("</details>", bs_start)
    bs_section = body[bs_start:bs_end]

    assert "<p>not extracted</p>" in bs_section
    assert "Balance Check Difference" not in bs_section


def test_substituted_ratio_badges_and_provenance(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 10b: A substituted ratio is visibly marked with 'SUBSTITUTED' and 'It is not a measurement.'"""
    fs, _ = _hand_built_two_year_stub()
    # No cash flow statements -> D&A%, CapEx%, NWC% cannot be derived and are substituted
    fs_no_cf = FinancialStatements(
        ticker=fs.ticker,
        company_name=fs.company_name,
        income_statements=fs.income_statements,
        cash_flow_statements=[],
        balance_sheets=fs.balance_sheets,
    )
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs_no_cf, []))
    monkeypatch.setattr(routes_valuation, "fetch_price_data", lambda *a, **k: _dummy_price_data())

    # Check GET /assumptions
    resp_get = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp_get.status_code == 200
    assert "SUBSTITUTED" in resp_get.text
    assert "It is not a measurement." in resp_get.text
    assert "substituted-marker" in resp_get.text

    # Check POST /valuation with blank ratio inputs that trigger substitution
    form_blank_ratios = dict(VALUATION_FORM_DATA)
    form_blank_ratios["revenue_growth"] = ""
    form_blank_ratios["operating_margin"] = ""
    form_blank_ratios["tax_rate"] = ""
    form_blank_ratios["da_pct"] = ""
    form_blank_ratios["capex_pct"] = ""
    form_blank_ratios["nwc_pct"] = ""

    resp_post = client.post("/valuation", data=form_blank_ratios)
    assert resp_post.status_code == 200
    assert "SUBSTITUTED" in resp_post.text
    assert "It is not a measurement." in resp_post.text
    assert "substituted-marker" in resp_post.text


def test_empty_applied_items_renders_explanatory_sentence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Assignment step 7: When applied items list is empty, print 'No non-recurring item was applied.'"""
    fs, _ = _hand_built_two_year_stub()
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs, []))

    resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp.status_code == 200
    body = resp.text

    applied_heading = "Non-recurring items APPLIED — these moved the figures above"
    start = body.index(applied_heading)
    end = body.index("<h2>", start + len(applied_heading))
    section = body[start:end]

    assert "No non-recurring item was applied." in section
    assert "<table" not in section


def test_unadjusted_reconciliation_renders_explanatory_sentence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Assignment step 8: When no year moved, print 'No adjustment reached the income statement.'"""
    fs, _ = _hand_built_two_year_stub()
    # Pass empty NRI so no adjustments are made
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs, []))

    resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp.status_code == 200
    body = resp.text

    recon_heading = "GAAP to Non-GAAP Reconciliation ($M)"
    start = body.index(recon_heading)
    end = body.index("<h2>", start + len(recon_heading))
    section = body[start:end]

    assert "No adjustment reached the income statement." in section


def test_empty_assumption_sources_suppresses_table(
    client: TestClient,
) -> None:
    """Finding 1 / edge case: When no files parameter is passed to /assumptions, assumption_sources is empty and table is suppressed."""
    resp = client.get("/assumptions?ticker=TESTCO")
    assert resp.status_code == 200
    body = resp.text

    # No files were passed, so assumption_sources is {}, and Assumptions Used block should not render
    assert "Assumptions Used" not in body


# ---------------------------------------------------------------------------
# Hygiene & Regression Invariants
# ---------------------------------------------------------------------------

def test_no_javascript_in_any_template() -> None:
    """Criterion 4: Still no JavaScript anywhere in templates/."""
    from pathlib import Path

    templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
    for tmpl in templates_dir.glob("*.html"):
        content = tmpl.read_text(encoding="utf-8")
        assert "<script" not in content.lower(), f"Found <script> tag in {tmpl.name}"


def test_css_contains_provenance_and_templates_have_no_prov_variable() -> None:
    """Criterion 11: PROV variable is removed from valuation_result.html and .provenance exists in CSS."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    val_tmpl = root / "templates" / "valuation_result.html"
    css = root / "static" / "style.css"

    assert "PROV" not in val_tmpl.read_text(encoding="utf-8")
    assert ".provenance" in css.read_text(encoding="utf-8")


def test_balance_sheet_table_renders_difference_and_metrics_hand_computed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Steps 6 & 12: Balance sheet table renders balance check difference and key metrics.

    Hand arithmetic for balanced BS:
      Total Assets: 870.0
      Total Liabilities + Equity: 870.0
      Balance Check Difference = 870 - 870 = +0
      Total Debt = 30 + 10 + 200 = 240
      Net Debt = 240 - 100 - 50 = 90
      Net Working Capital = (300 - 150) - (120 - 40) = 70

    Hand arithmetic for imbalanced BS (cash = 150 instead of 100):
      Total Assets: 920.0
      Total Liabilities + Equity: 870.0
      Balance Check Difference = 920 - 870 = +50
      Net Debt = 240 - 150 - 50 = 40
    """
    fs, nri = _hand_built_two_year_stub()
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs, nri))

    resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp.status_code == 200
    body = resp.text

    bs_start = body.index("Balance Check &amp; Key Metrics")
    bs_end = body.index("</table>", bs_start)
    bs_metrics_table = body[bs_start:bs_end]

    # Check balanced metrics
    assert "Balance Check Difference (Total Assets − [Liabilities + Equity])" in bs_metrics_table
    assert "+0" in bs_metrics_table
    assert "240" in bs_metrics_table  # Total Debt
    assert "90" in bs_metrics_table   # Net Debt
    assert "70" in bs_metrics_table   # Net Working Capital

    # Now test imbalanced balance sheet
    bs_imbalanced = BalanceSheet(
        year=2024,
        cash_and_equivalents=150.0,  # +50
        short_term_investments=50.0,
        accounts_receivable=80.0,
        inventory=60.0,
        other_current_assets=10.0,
        ppe_net=400.0,
        goodwill=100.0,
        intangible_assets=50.0,
        other_non_current_assets=20.0,
        accounts_payable=50.0,
        short_term_debt=30.0,
        current_portion_lt_debt=10.0,
        accrued_liabilities=20.0,
        other_current_liabilities=10.0,
        long_term_debt=200.0,
        other_non_current_liabilities=30.0,
        total_equity=520.0,
        noncontrolling_interest_nonredeemable=0.0,
        noncontrolling_interest_redeemable=0.0,
        printed_unit_in_millions=1.0,
    )
    fs_imbalanced = FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=fs.income_statements,
        cash_flow_statements=fs.cash_flow_statements,
        balance_sheets=[bs_imbalanced],
    )
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs_imbalanced, []))

    resp_imb = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp_imb.status_code == 200
    body_imb = resp_imb.text
    bs_imb_start = body_imb.index("Balance Check &amp; Key Metrics")
    bs_imb_end = body_imb.index("</table>", bs_imb_start)
    bs_imb_table = body_imb[bs_imb_start:bs_imb_end]

    assert "+50" in bs_imb_table
    assert "40" in bs_imb_table  # Net Debt is now 40


def test_implied_share_price_unchanged_on_baseline_stub(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 12: No number already on either page moved.

    Baseline on tests/unit/test_routes.py _one_year_financials stub: $22.58.
    """
    baseline_fs = FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=[
            IncomeStatement(year=2024, revenue=1000.0, sga=800.0, tax_expense=50.0,
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
    )
    baseline_form = {
        "ticker": "TESTCO",
        "company_name": "Test Company Inc",
        "files": "2024:baseline.pdf",
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

    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (baseline_fs, []))
    monkeypatch.setattr(routes_valuation, "fetch_price_data", lambda *a, **k: _dummy_price_data())

    resp = client.post("/valuation", data=baseline_form)
    assert resp.status_code == 200

    match = re.search(r"<h3>Implied Share Price</h3>\s*<div class=\"big-number\">([^<]+)</div>", resp.text)
    assert match is not None
    # Baseline expected implied share price is $22.58
    assert match.group(1).strip() == "$22.58"


def test_money_headers_and_sign_conventions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Assignment steps 13 & 14: Every money column header says $M; CapEx says (negative = outflow)."""
    fs, nri = _hand_built_two_year_stub()
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fs, nri))

    resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:t23.pdf,2024:t24.pdf")
    assert resp.status_code == 200
    body = resp.text

    assert "Line Item ($M)" in body
    assert "Diluted Shares (M)" in body
    assert "CapEx (negative = outflow)" in body
    assert "Amount ($M)" in body
    assert "EBIT as reported ($M)" in body
    assert "EBIT adjusted ($M)" in body
    assert "Difference ($M)" in body

