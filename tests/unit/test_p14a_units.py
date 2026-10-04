"""Tests for P14a unit handling: printed_scale, page checks, conversion, and tolerances.

Verifies:
1. printed_scale reads scale words (thousands, millions, billions) and stops on missing,
   conflicting, or excepted scale mentions (Rule 3).
2. unit_statement_on_page requires exact parenthesised group or whole text line equality
   and rejects fragments.
3. _unit_statement_pages_allowed restricts unit statement citations to governed statement pages.
4. convert_filing_to_millions converts statement and Pass 2 figures once per filing
   by hand-derived arithmetic.
5. Balance check tolerance and decimal precision adhere to 1 printed unit (0.001 for thousands,
   1.0 for millions) and format differences with appropriate decimal precision.
6. Refusal of session-extraction-v2 format with remedy message and refusal of old CLI cache marker.

All expected values derived by hand arithmetic or closed-form identity.
No network calls. Test PDFs written as bytes to tmp_path.
"""

from __future__ import annotations

import json
import pickle
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

import cli
from ingestion.claude_extractor import (
    FilingUnits,
    PrintedScale,
    UnitStatement,
    _unit_statement_failures,
    _unit_statement_pages_allowed,
    convert_filing_to_millions,
    printed_scale,
    unit_statement_on_page,
)
from ingestion.session_extraction import load_session_extraction
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)
from tests.unit._text_pdf import write_text_pdf

# ---------------------------------------------------------------------------
# 1. printed_scale: scale words and stops (Rule 3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "unit_of", "expected_word", "expected_fraction"),
    [
        # Hand derivation: 1 thousand = 1 / 1,000 million = Fraction(1, 1000)
        ("in thousands", "money figures", "thousands", Fraction(1, 1000)),
        ("(in thousands)", "share count", "thousands", Fraction(1, 1000)),
        # Hand derivation: 1 million = 1 million = Fraction(1, 1)
        ("(In Millions)", "money figures", "millions", Fraction(1, 1)),
        ("in millions", "share count", "millions", Fraction(1, 1)),
        # Hand derivation: 1 billion = 1,000 million = Fraction(1000, 1)
        ("in billions", "money figures", "billions", Fraction(1000, 1)),
        ("(IN BILLIONS)", "share count", "billions", Fraction(1000, 1)),
    ],
    ids=["thousands-money", "thousands-shares", "millions-money", "millions-shares", "billions-money", "billions-shares"],
)
def test_printed_scale_reads_standard_scale_words(
    text: str, unit_of: Any, expected_word: str, expected_fraction: Fraction,
) -> None:
    """Hand derivation: scale words map to exact fractions in millions."""
    result = printed_scale(text, unit_of)
    assert result.word == expected_word
    assert result.in_millions == expected_fraction


@pytest.mark.parametrize(
    ("statement", "money_word", "money_fraction", "share_word", "share_fraction"),
    [
        # Walmart 10-K 2026-01-31 p21: generic subject "Amounts" applies to both
        ("(Amounts in millions, except per share data)", "millions", Fraction(1, 1), "millions", Fraction(1, 1)),
        # Okta 10-K 2026-01-31 p58: two clauses, distinct scales
        ("(dollars in millions, shares in thousands, except per share data)", "millions", Fraction(1, 1), "thousands", Fraction(1, 1000)),
        # Chipotle 10-K 2024-12-31 p29: clause with no subject applies to both
        ("(in thousands, except per share data)", "thousands", Fraction(1, 1000), "thousands", Fraction(1, 1000)),
        # L3Harris 10-K 2023-12-29 p17: bare clause applies to both
        ("(In millions)", "millions", Fraction(1, 1), "millions", Fraction(1, 1)),
        # Joint subjects
        ("(dollar and share amounts in thousands, unless otherwise specified)", "thousands", Fraction(1, 1000), "thousands", Fraction(1, 1000)),
    ],
    ids=["walmart", "okta", "chipotle", "l3harris", "joint-amounts"],
)
def test_printed_scale_real_world_filing_statements(
    statement: str, money_word: str, money_fraction: Fraction, share_word: str, share_fraction: Fraction,
) -> None:
    """Verifies standard unit statements from real 10-K filings."""
    money_scale = printed_scale(statement, "money figures")
    share_scale = printed_scale(statement, "share count")

    assert money_scale.word == money_word
    assert money_scale.in_millions == money_fraction
    assert share_scale.word == share_word
    assert share_scale.in_millions == share_fraction


@pytest.mark.parametrize("unit_of", ["money figures", "share count"])
def test_printed_scale_stops_when_no_scale_word_present(unit_of: Any) -> None:
    """Rule 3: Statement without thousands/millions/billions stops and names the unit."""
    with pytest.raises(ValueError) as excinfo:
        printed_scale("(in actual numbers)", unit_of)
    message = str(excinfo.value)
    assert "thousands, millions or billions" in message
    assert unit_of in message


def test_printed_scale_in_dollars_stops() -> None:
    """Rule 3: (in dollars) stops for both money figures and share count."""
    with pytest.raises(ValueError, match="names dollars outside a clause"):
        printed_scale("(in dollars)", "money figures")

    with pytest.raises(ValueError, match="no scale word.*share count"):
        printed_scale("(in dollars)", "share count")


@pytest.mark.parametrize(
    "statement",
    [
        "(in millions, except share data)",
        "(in millions, except shares)",
        "(Amounts in millions, except share and per share data)",
    ],
    ids=["except-share-data", "except-shares", "except-share-and-per-share"],
)
def test_printed_scale_stops_when_statement_excepts_shares(statement: str) -> None:
    """Rule 3: Exception text mentioning shares stops the share count scale."""
    with pytest.raises(ValueError) as excinfo:
        printed_scale(statement, "share count")
    message = str(excinfo.value)
    assert "excepts the share count" in message
    assert "share count" in message


@pytest.mark.parametrize(
    "statement",
    [
        "(In millions, excluding share data)",
        "(in millions, other than shares)",
        "(in millions, but not shares)",
        "(in millions; shares in actual numbers)",
        "(in millions, other than share and per share data)",
        "(in thousands, but not shares)",
    ],
    ids=[
        "excluding-share-data",
        "other-than-shares",
        "but-not-shares",
        "shares-in-actual-numbers",
        "other-than-share-per-share",
        "thousands-not-shares",
    ],
)
def test_printed_scale_stops_when_shares_named_outside_clauses(statement: str) -> None:
    """F2 requirement: statements naming shares outside scale clauses stop."""
    with pytest.raises(ValueError) as excinfo:
        printed_scale(statement, "share count")
    message = str(excinfo.value)
    assert "names shares outside a clause" in message
    assert "share count" in message


@pytest.mark.parametrize(
    "statement",
    [
        "(in millions, excluding dollars)",
        "(shares in thousands, other than dollars)",
    ],
    ids=["excluding-dollars", "other-than-dollars"],
)
def test_printed_scale_stops_when_dollars_named_outside_clauses(statement: str) -> None:
    """Rule 3: Dollars mentioned outside scale clauses stop money scale."""
    with pytest.raises(ValueError) as excinfo:
        printed_scale(statement, "money figures")
    message = str(excinfo.value)
    assert "names dollars outside a clause" in message
    assert "money figures" in message


def test_printed_scale_stops_when_scale_word_inside_exception() -> None:
    """Rule 3: A scale word inside exception text cannot be resolved."""
    with pytest.raises(ValueError, match="prints a scale word inside its exception"):
        printed_scale("(in millions, except shares in thousands)", "share count")


def test_printed_scale_stops_on_conflicting_scales_for_same_unit() -> None:
    """Rule 3: Two different scales for the same subject stop with a clear error."""
    with pytest.raises(ValueError, match="states 2 different scales"):
        printed_scale("(dollars in millions, dollars in thousands)", "money figures")


# ---------------------------------------------------------------------------
# 2. unit_statement_on_page: exact whole statement vs fragments (F1)
# ---------------------------------------------------------------------------


def test_unit_statement_on_page_matches_exact_parenthesised_group() -> None:
    """Parenthesised unit statements match against parenthesised groups on page."""
    page_text = "CONSOLIDATED STATEMENTS OF OPERATIONS\n(in thousands)\nRevenues 1,000"
    assert unit_statement_on_page("(in thousands)", page_text) is True


def test_unit_statement_on_page_normalises_whitespace_and_newlines() -> None:
    """Whitespace runs and newlines fold to a single space."""
    page_text = "CONSOLIDATED FINANCIAL STATEMENTS\n(Amounts in millions,\nexcept per share data)\nRevenues 500"
    # Matches even when line-wrapped across text lines
    assert unit_statement_on_page("(Amounts in millions, except per share data)", page_text) is True
    assert unit_statement_on_page("(Amounts   in  millions,   except per share data)", page_text) is True


def test_unit_statement_on_page_rejects_fragments_on_two_scale_pages() -> None:
    """F1 blocker test: Fragment (in thousands) must NOT match inside Okta's statement."""
    okta_page_58 = (
        "OKTA, INC.\n"
        "CONSOLIDATED STATEMENTS OF OPERATIONS\n"
        "(dollars in millions, shares in thousands, except per share data)\n"
        "Revenue 2,610"
    )
    # The fragment is rejected
    assert unit_statement_on_page("(in thousands)", okta_page_58) is False
    assert unit_statement_on_page("(in millions)", okta_page_58) is False
    assert unit_statement_on_page("(dollars in millions)", okta_page_58) is False

    # The full statement is accepted
    full_stmt = "(dollars in millions, shares in thousands, except per share data)"
    assert unit_statement_on_page(full_stmt, okta_page_58) is True


def test_unit_statement_on_page_without_parentheses_matches_whole_text_line() -> None:
    """A statement without parentheses matches an entire text line."""
    page_text = "Income Statement\nin millions\nRevenue 100"
    assert unit_statement_on_page("in millions", page_text) is True
    # Substring within line does not match
    assert unit_statement_on_page("millions", page_text) is False


def test_unit_statement_on_page_empty_returns_false() -> None:
    """Empty or whitespace-only statements return False."""
    assert unit_statement_on_page("", "page with (in millions)") is False
    assert unit_statement_on_page("   ", "page with (in millions)") is False


# ---------------------------------------------------------------------------
# 3. _unit_statement_pages_allowed: governed figure page constraints (F6)
# ---------------------------------------------------------------------------


def test_unit_statement_pages_allowed_constrains_pages() -> None:
    """F6: units is restricted to income statement pages; share_units to income or diluted pages."""
    data = {
        "units": {"printed": "(in millions)", "page": 29},
        "share_units": {"printed": "(in millions)", "page": 30},
        "historical_years": [
            {
                "year": 2024,
                "revenue": [{"label": "Revenue", "value": 100.0, "page": 29}],
                "cost_of_revenue": [{"label": "Cost", "value": 60.0, "page": 29}],
                "gross_profit": [{"label": "Gross", "value": 40.0, "page": 29}],
                "sga": [{"label": "SGA", "value": 20.0, "page": 29}],
                "rd_expense": [],
                "depreciation_amortization": [{"label": "DA", "value": 5.0, "page": 32}],  # cash flow page
                "other_operating_expense": [],
                "operating_income": [{"label": "Operating Income", "value": 20.0, "page": 29}],
                "interest_expense": [],
                "interest_income": [],
                "other_non_operating": [],
                "tax_expense": [{"label": "Tax", "value": 5.0, "page": 29}],
                "net_income": [{"label": "Net Income", "value": 15.0, "page": 29}],
                "diluted_shares": [{"label": "Shares", "value": 50.0, "page": 30}],
                "cfo": [{"label": "CFO", "value": 25.0, "page": 32}],
                "capex": [{"label": "CapEx", "value": -10.0, "page": 32}],
                "sbc": [],
                "change_in_working_capital": [],
            }
        ],
    }

    allowed = _unit_statement_pages_allowed(data)
    # units allowed only on income statement line pages: {29, 30}
    assert allowed["units"] == {29, 30}
    # share_units allowed on units.page (29) | diluted_shares pages (30): {29, 30}
    assert allowed["share_units"] == {29, 30}


def test_unit_statement_failures_stops_when_page_outside_allowed(tmp_path: Path) -> None:
    """F6: Unit statement citing an MD&A page or stock-award table page fails."""
    # Statements are printed on page 29, but units cites page 35
    data = {
        "ticker": "TST",
        "company_name": "Test Co",
        "units": {"printed": "(in millions)", "page": 35},
        "share_units": {"printed": "(in millions)", "page": 29},
        "historical_years": [
            {
                "year": 2024,
                "revenue": [{"label": "Revenue", "value": 100.0, "page": 29}],
                "cost_of_revenue": [],
                "gross_profit": [],
                "sga": [],
                "rd_expense": [],
                "depreciation_amortization": [],
                "other_operating_expense": [],
                "operating_income": [],
                "interest_expense": [],
                "interest_income": [],
                "other_non_operating": [],
                "tax_expense": [],
                "net_income": [{"label": "Net Income", "value": 100.0, "page": 29}],
                "diluted_shares": [{"label": "Shares", "value": 10.0, "page": 29}],
                "cfo": [],
                "capex": [],
                "sbc": [],
                "change_in_working_capital": [],
            }
        ],
        "latest_balance_sheet": {},
    }

    # Generate a PDF with (in millions) on page 35 and page 29
    pdf_pages: list[list[str]] = [[] for _ in range(35)]
    pdf_pages[28] = ["(in millions)", "Revenue 100", "Net Income 100", "Shares 10"]
    pdf_pages[34] = ["(in millions)", "Stock Award Table"]
    pdf_path = write_text_pdf(tmp_path / "f.pdf", pdf_pages)

    failures = _unit_statement_failures(data, pdf_path.read_bytes())
    assert len(failures) == 1
    msg = failures[0].message
    assert "'units'" in msg
    assert "page 35" in msg
    assert "the pages allowed are [29]" in msg


# ---------------------------------------------------------------------------
# 4. convert_filing_to_millions: hand arithmetic derivation
# ---------------------------------------------------------------------------


def test_convert_filing_to_millions_thousands_filing() -> None:
    """Hand arithmetic for thousands filing:
    Each money figure is divided by 1,000:
      revenue:               15,000,000 / 1,000 = 15,000.0 $M
      cost_of_revenue:        9,000,000 / 1,000 =  9,000.0 $M
      sga:                    1,500,000 / 1,000 =  1,500.0 $M
      rd_expense:               500,000 / 1,000 =    500.0 $M
      depreciation:             600,000 / 1,000 =    600.0 $M
      tax_expense:              700,000 / 1,000 =    700.0 $M
      nri sga add_back:         200,000 / 1,000 =    200.0 $M
      diluted_shares:           500,000 / 1,000 =    500.0 million shares
    Balance sheet:
      cash:                   2,000,000 / 1,000 =  2,000.0 $M
      long_term_debt:         4,000,000 / 1,000 =  4,000.0 $M
      total_equity:           6,000,000 / 1,000 =  6,000.0 $M
      printed_total_assets:  10,000,000 / 1,000 = 10,000.0 $M
      printed_total_liab_eq: 10,000,000 / 1,000 = 10,000.0 $M
      printed_unit_in_millions: 0.001
    Cash flow:
      net_income:             2,700,000 / 1,000 =  2,700.0 $M
      capex:                 -1,200,000 / 1,000 = -1,200.0 $M
    Pass 2 item:
      amount:                   200,000 / 1,000 =    200.0 $M
    """
    fin = FinancialStatements(
        ticker="THOU",
        company_name="Thousands Co",
        income_statements=[
            IncomeStatement(
                year=2024,
                revenue=15_000_000.0,
                cost_of_revenue=9_000_000.0,
                sga=1_500_000.0,
                rd_expense=500_000.0,
                depreciation_amortization=600_000.0,
                tax_expense=700_000.0,
                diluted_shares_outstanding=500_000.0,
                non_recurring_items={"restructuring": 200_000.0},
            )
        ],
        balance_sheets=[
            BalanceSheet(
                year=2024,
                cash_and_equivalents=2_000_000.0,
                long_term_debt=4_000_000.0,
                total_equity=6_000_000.0,
                printed_total_assets=10_000_000.0,
                printed_total_liabilities_and_equity=10_000_000.0,
                noncontrolling_interest_nonredeemable=0.0,
                noncontrolling_interest_redeemable=0.0,
                printed_unit_in_millions=None,
            )
        ],
        cash_flow_statements=[
            CashFlowStatement(
                year=2024,
                net_income=2_700_000.0,
                capital_expenditures=-1_200_000.0,
            )
        ],
    )
    items = [
        NonRecurringItem(
            year=2024,
            description="Restructuring note",
            amount=200_000.0,
            line_item="sga",
            direction="add_back",
            category="restructuring",
            confidence="high",
            page=1,
            printed_units="(in thousands)",
            units_page=1,
            source="Note 5",
        )
    ]
    units = FilingUnits(
        money=UnitStatement("units", "(in thousands)", 1, PrintedScale("thousands", Fraction(1, 1000))),
        shares=UnitStatement("share_units", "(in thousands)", 1, PrintedScale("thousands", Fraction(1, 1000))),
    )

    converted_fin, converted_items = convert_filing_to_millions(fin, items, units)

    inc = converted_fin.income_statements[0]
    assert inc.revenue == pytest.approx(15_000.0)
    assert inc.cost_of_revenue == pytest.approx(9_000.0)
    assert inc.sga == pytest.approx(1_500.0)
    assert inc.rd_expense == pytest.approx(500.0)
    assert inc.depreciation_amortization == pytest.approx(600.0)
    assert inc.tax_expense == pytest.approx(700.0)
    assert inc.diluted_shares_outstanding == pytest.approx(500.0)
    assert inc.non_recurring_items["restructuring"] == pytest.approx(200.0)

    bs = converted_fin.balance_sheets[0]
    assert bs.cash_and_equivalents == pytest.approx(2_000.0)
    assert bs.long_term_debt == pytest.approx(4_000.0)
    assert bs.total_equity == pytest.approx(6_000.0)
    assert bs.printed_total_assets == pytest.approx(10_000.0)
    assert bs.printed_total_liabilities_and_equity == pytest.approx(10_000.0)
    assert bs.printed_unit_in_millions == pytest.approx(0.001)

    cf = converted_fin.cash_flow_statements[0]
    assert cf.net_income == pytest.approx(2_700.0)
    assert cf.capital_expenditures == pytest.approx(-1_200.0)

    assert converted_items[0].amount == pytest.approx(200.0)


def test_convert_filing_to_millions_billions_filing() -> None:
    """Hand arithmetic for billions filing:
    Multiplied by 1,000:
      revenue:        3.5 * 1,000 = 3,500.0 $M
      diluted_shares: 0.1 * 1,000 =   100.0 million shares
      printed_unit_in_millions: 1000.0
    """
    fin = FinancialStatements(
        ticker="BIL",
        company_name="Billions Co",
        income_statements=[
            IncomeStatement(
                year=2024,
                revenue=3.5,
                diluted_shares_outstanding=0.1,
            )
        ],
        balance_sheets=[
            BalanceSheet(
                year=2024,
                cash_and_equivalents=1.2,
                printed_unit_in_millions=None,
            )
        ],
        cash_flow_statements=[CashFlowStatement(year=2024)],
    )
    units = FilingUnits(
        money=UnitStatement("units", "(in billions)", 1, PrintedScale("billions", Fraction(1000, 1))),
        shares=UnitStatement("share_units", "(in billions)", 1, PrintedScale("billions", Fraction(1000, 1))),
    )

    converted_fin, _ = convert_filing_to_millions(fin, [], units)
    assert converted_fin.income_statements[0].revenue == pytest.approx(3_500.0)
    assert converted_fin.income_statements[0].diluted_shares_outstanding == pytest.approx(100.0)
    assert converted_fin.balance_sheets[0].cash_and_equivalents == pytest.approx(1_200.0)
    assert converted_fin.balance_sheets[0].printed_unit_in_millions == pytest.approx(1000.0)


def test_convert_filing_to_millions_two_scales_okta() -> None:
    """Okta case: money in millions (x 1), shares in thousands (/ 1000).
    Hand arithmetic:
      revenue:        2,610.0 * 1      = 2,610.0 $M
      diluted_shares: 180,000.0 / 1000 =   180.0 million shares
    """
    fin = FinancialStatements(
        ticker="OKTA",
        company_name="Okta Inc",
        income_statements=[
            IncomeStatement(
                year=2025,
                revenue=2610.0,
                diluted_shares_outstanding=180000.0,
            )
        ],
        balance_sheets=[
            BalanceSheet(year=2025, cash_and_equivalents=500.0, printed_unit_in_millions=None)
        ],
        cash_flow_statements=[CashFlowStatement(year=2025)],
    )
    units = FilingUnits(
        money=UnitStatement("units", "(dollars in millions)", 58, PrintedScale("millions", Fraction(1, 1))),
        shares=UnitStatement("share_units", "(shares in thousands)", 58, PrintedScale("thousands", Fraction(1, 1000))),
    )

    converted_fin, _ = convert_filing_to_millions(fin, [], units)
    assert converted_fin.income_statements[0].revenue == pytest.approx(2610.0)
    assert converted_fin.income_statements[0].diluted_shares_outstanding == pytest.approx(180.0)
    assert converted_fin.balance_sheets[0].printed_unit_in_millions == pytest.approx(1.0)


def test_convert_filing_to_millions_duplicate_conversion_stops() -> None:
    """Rule 3: Converting an already-converted filing stops to prevent double-conversion."""
    fin = FinancialStatements(
        ticker="DUP",
        balance_sheets=[
            BalanceSheet(year=2024, printed_unit_in_millions=1.0)
        ],
    )
    units = FilingUnits(
        money=UnitStatement("units", "(in millions)", 1, PrintedScale("millions", Fraction(1, 1))),
        shares=UnitStatement("share_units", "(in millions)", 1, PrintedScale("millions", Fraction(1, 1))),
    )
    with pytest.raises(ValueError, match="already carry printed_unit_in_millions"):
        convert_filing_to_millions(fin, [], units)


# ---------------------------------------------------------------------------
# 5. Balance check tolerance and decimals
# ---------------------------------------------------------------------------


def test_balance_check_thousands_tolerance_and_status() -> None:
    """Tolerance for thousands is 0.001 $M (1 printed unit).
    Hand comparison:
      gap <= 0.001: OK
      gap > 0.001: FAIL
    """
    bs = BalanceSheet(year=2024, printed_unit_in_millions=0.001)

    assert bs.printed_total_tolerance() == pytest.approx(0.001)
    assert bs.printed_unit_decimals() == 3

    # Exact tolerance passes
    assert bs.printed_total_check(0.001) == "OK"
    assert bs.printed_total_check(-0.001) == "OK"

    # Above tolerance fails
    assert bs.printed_total_check(0.002) == "FAIL"
    assert bs.printed_total_check(-0.002) == "FAIL"

    # None fails
    assert bs.printed_total_check(None) == "FAIL: not extracted"


def test_balance_check_millions_tolerance_and_status() -> None:
    """Tolerance for millions is 1.0 $M (1 printed unit).
    Hand comparison:
      gap <= 1.0: OK
      gap > 1.0: FAIL
    """
    bs = BalanceSheet(year=2024, printed_unit_in_millions=1.0)

    assert bs.printed_total_tolerance() == pytest.approx(1.0)
    assert bs.printed_unit_decimals() == 0

    assert bs.printed_total_check(1.0) == "OK"
    assert bs.printed_total_check(-1.0) == "OK"
    assert bs.printed_total_check(2.0) == "FAIL"
    assert bs.printed_total_check(-2.0) == "FAIL"


def test_balance_check_decimals_formatting_for_thousands() -> None:
    """F4 requirement: difference cells format decimals so +0.002 is not displayed as +0."""
    bs = BalanceSheet(year=2024, printed_unit_in_millions=0.001)
    places = bs.printed_unit_decimals()
    assert places == 3

    diff = 0.002
    formatted = f"{diff:+,.{places}f}"
    assert formatted == "+0.002"
    assert formatted != "+0"


def test_unconverted_balance_sheet_stops_and_names_printed_unit_in_millions() -> None:
    """Rule 3: BalanceSheet with printed_unit_in_millions=None stops on check methods."""
    bs = BalanceSheet(year=2024, printed_unit_in_millions=None)

    with pytest.raises(ValueError, match="'printed_unit_in_millions' is None"):
        bs.printed_unit()

    with pytest.raises(ValueError, match="'printed_unit_in_millions' is None"):
        bs.printed_total_tolerance()

    with pytest.raises(ValueError, match="'printed_unit_in_millions' is None"):
        bs.printed_unit_decimals()

    with pytest.raises(ValueError, match="'printed_unit_in_millions' is None"):
        bs.printed_total_check(0.0)


# ---------------------------------------------------------------------------
# 6. Session format v2 refusal and CLI cache format refusal
# ---------------------------------------------------------------------------


def test_session_extraction_v2_refused_with_remedy(tmp_path: Path) -> None:
    """Rule 3 & Step 7: session-extraction-v2 is refused by name with remedy message."""
    v2_data = {
        "format": "session-extraction-v2",
        "ticker": "OLD",
        "company_name": "Old Format Co",
        "extracted_by": {"model": "claude-3-opus", "tool": "Claude Code", "date": "2026-10-01"},
        "filings": [],
    }
    path = tmp_path / "session_v2.json"
    path.write_text(json.dumps(v2_data), encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)

    message = str(excinfo.value)
    assert "'session-extraction-v2'" in message
    assert "'session-extraction-v4'" in message
    assert "'units'" in message
    assert "'share_units'" in message
    assert "Remedy: run the extract-filing skill again" in message


def test_old_cli_cache_marker_p11a_refused(tmp_path: Path) -> None:
    """Step 7: Cache format before P14a (p11a-printed-lines-v1) is refused by _load_cache."""
    cache_path = tmp_path / "old_cache.pkl"
    dummy_key = cli.ExtractionKey(ticker="TST", provider="claude", model="test-model", inputs=())
    dummy_fin = FinancialStatements(ticker="TST")
    # Write cache with previous marker p11a-printed-lines-v1
    cache_path.write_bytes(pickle.dumps(("p11a-printed-lines-v1", dummy_key, dummy_fin, [])))

    with pytest.raises(ValueError) as excinfo:
        cli._load_cache(cache_path)

    message = str(excinfo.value)
    assert "not a cache entry written by this CLI" in message
    assert repr("p14b-pass2-units-v1") in message
