"""Tests for P14b Pass 2 units: pass2_amount_scale, Pass 2 page checks,
individual item scaling, session format v4, and CLI cache marker.

Verifies:
1. pass2_amount_scale:
   - Inline regex forms ($0.7 billion, $5.2 million, $300 thousand, plurals, whitespace).
   - Statement delegation to printed_scale ((Amounts in millions), (in thousands)).
   - Stops on inline number mismatch, missing scale word, or unreadable scale word (Rule 3).
2. Pass 2 page checks (_pass2_item_failures and pass2_page_failures):
   - Figure check on cited page (_text_line_holds).
   - Inline unit words check (units_page == page, text on page).
   - Statement unit words check (units_page in (page, page - 1), whole statement on page).
   - Failure messages naming item, year, amount/units, and page.
3. Individual Pass 2 scaling in convert_filing_to_millions:
   - Mixed scales in one filing (billions, millions, thousands).
   - Filing in thousands with footnote item in millions ($5.2 million -> 5.2 $M)
     and statement item in thousands (5,200 under (in thousands) -> 5.2 $M).
4. Session format v4 and CLI cache:
   - Refusal of session-extraction-v3 with remedy naming v3, v4, page, units, extract-filing.
   - Refusal of old cache markers in cli._load_cache naming p14d-finance-leases-v1.

All expected values derived by hand arithmetic or closed-form identity.
No network calls. Test PDFs written as bytes to tmp_path.
"""

from __future__ import annotations

import json
import pickle
from fractions import Fraction
from pathlib import Path

import pytest

import cli
from ingestion.claude_extractor import (
    FilingUnits,
    PrintedScale,
    UnitStatement,
    _pass2_item_failures,
    convert_filing_to_millions,
    pass2_amount_scale,
    pass2_page_failures,
)
from ingestion.session_extraction import (
    SESSION_FORMAT,
    load_session_extraction,
)
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)
from tests.unit._text_pdf import write_text_pdf

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dummy_financials() -> FinancialStatements:
    """Minimal FinancialStatements container for conversion tests."""
    return FinancialStatements(
        ticker="TEST",
        company_name="Test Corp",
        income_statements=[
            IncomeStatement(
                year=2026,
                revenue=1000.0,
                cost_of_revenue=600.0,
                sga=100.0,
                rd_expense=50.0,
                depreciation_amortization=40.0,
                tax_expense=30.0,
                diluted_shares_outstanding=100.0,
            )
        ],
        balance_sheets=[
            BalanceSheet(
                year=2026,
                cash_and_equivalents=200.0,
                long_term_debt=300.0,
                total_equity=500.0,
                printed_total_assets=1000.0,
                printed_total_liabilities_and_equity=1000.0,
                noncontrolling_interest_nonredeemable=0.0,
                noncontrolling_interest_redeemable=0.0,
                printed_unit_in_millions=None,
            )
        ],
        cash_flow_statements=[
            CashFlowStatement(
                year=2026,
                net_income=180.0,
                capital_expenditures=-50.0,
            )
        ],
    )


def _dummy_units(money_word: str = "millions", money_frac: Fraction = Fraction(1, 1)) -> FilingUnits:
    """FilingUnits helper for conversion tests."""
    return FilingUnits(
        money=UnitStatement("units", f"(in {money_word})", 1, PrintedScale(money_word, money_frac)),
        shares=UnitStatement("share_units", f"(in {money_word})", 1, PrintedScale(money_word, money_frac)),
    )


# ---------------------------------------------------------------------------
# 1. pass2_amount_scale: inline regex forms, statement forms, and stops
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "amount", "expected_word", "expected_fraction"),
    [
        # Hand derivation: 1 billion = 1,000 million = Fraction(1000, 1)
        ("$0.7 billion", 0.7, "billions", Fraction(1000, 1)),
        ("$0.7 billions", 0.7, "billions", Fraction(1000, 1)),
        ("0.7 billion", 0.7, "billions", Fraction(1000, 1)),
        (" $0.7   billion ", 0.7, "billions", Fraction(1000, 1)),
        ("$ 0.7 billion", 0.7, "billions", Fraction(1000, 1)),
        ("$0.7 BILLION", 0.7, "billions", Fraction(1000, 1)),
        # Hand derivation: 1 million = 1 million = Fraction(1, 1)
        ("$5.2 million", 5.2, "millions", Fraction(1, 1)),
        ("$5.2 millions", 5.2, "millions", Fraction(1, 1)),
        ("5.2 million", 5.2, "millions", Fraction(1, 1)),
        (" $5.2  million ", 5.2, "millions", Fraction(1, 1)),
        ("$5.2 Million", 5.2, "millions", Fraction(1, 1)),
        ("$1,200.5 million", 1200.5, "millions", Fraction(1, 1)),
        # Hand derivation: 1 thousand = 1 / 1,000 million = Fraction(1, 1000)
        ("$300 thousand", 300.0, "thousands", Fraction(1, 1000)),
        ("$300 thousands", 300.0, "thousands", Fraction(1, 1000)),
        ("300 thousand", 300.0, "thousands", Fraction(1, 1000)),
        (" 300   thousand ", 300.0, "thousands", Fraction(1, 1000)),
        ("$300 Thousand", 300.0, "thousands", Fraction(1, 1000)),
        ("$100,000 thousand", 100000.0, "thousands", Fraction(1, 1000)),
    ],
    ids=[
        "billion-standard",
        "billion-plural",
        "billion-no-dollar",
        "billion-spaces",
        "billion-space-after-dollar",
        "billion-upper",
        "million-standard",
        "million-plural",
        "million-no-dollar",
        "million-spaces",
        "million-mixed-case",
        "million-commas-decimal",
        "thousand-standard",
        "thousand-plural",
        "thousand-no-dollar",
        "thousand-spaces",
        "thousand-mixed-case",
        "thousand-commas",
    ],
)
def test_pass2_amount_scale_inline_forms(
    printed: str, amount: float, expected_word: str, expected_fraction: Fraction,
) -> None:
    """Verifies that inline unit expressions parse the scale word and multiplier."""
    scale = pass2_amount_scale(printed, amount)
    assert scale.word == expected_word
    assert scale.in_millions == expected_fraction


@pytest.mark.parametrize(
    ("statement", "amount", "expected_word", "expected_fraction"),
    [
        # Hand derivation: statement forms delegate to printed_scale
        ("(Amounts in millions, except per share data)", 2075.0, "millions", Fraction(1, 1)),
        ("(in thousands, except per share data)", 5200.0, "thousands", Fraction(1, 1000)),
        ("(in billions)", 10.0, "billions", Fraction(1000, 1)),
        ("(dollars in millions, shares in thousands, except per share data)", 15.0, "millions", Fraction(1, 1)),
        ("(In millions)", 123.4, "millions", Fraction(1, 1)),
        ("(in thousands)", 50.0, "thousands", Fraction(1, 1000)),
    ],
    ids=[
        "amounts-in-millions",
        "in-thousands-except",
        "in-billions",
        "dollars-millions-shares-thousands",
        "in-millions-capitalized",
        "in-thousands-bare",
    ],
)
def test_pass2_amount_scale_statement_delegation(
    statement: str, amount: float, expected_word: str, expected_fraction: Fraction,
) -> None:
    """Verifies that statement forms delegate to printed_scale(printed, 'money figures')."""
    scale = pass2_amount_scale(statement, amount)
    assert scale.word == expected_word
    assert scale.in_millions == expected_fraction


@pytest.mark.parametrize(
    ("printed", "amount", "expected_message_fragment"),
    [
        # Mismatch: inline text has 0.7, amount is 700.0 (converted by mistake)
        (
            "$0.7 billion",
            700.0,
            "the number in the inline unit text (0.7) does not equal the item amount (700.0)",
        ),
        # Mismatch: inline text has 0.7, amount is 0.8
        (
            "$0.7 billion",
            0.8,
            "the number in the inline unit text (0.7) does not equal the item amount (0.8)",
        ),
        # Mismatch: inline text has 5.2, amount is 5.0
        (
            "$5.2 million",
            5.0,
            "the number in the inline unit text (5.2) does not equal the item amount (5.0)",
        ),
        # Mismatch with commas: inline text has 1,200, amount is 120.0
        (
            "$1,200 million",
            120.0,
            "the number in the inline unit text (1200.0) does not equal the item amount (120.0)",
        ),
    ],
    ids=[
        "billion-700-mismatch",
        "billion-0.8-mismatch",
        "million-5.0-mismatch",
        "commas-120-mismatch",
    ],
)
def test_pass2_amount_scale_stops_on_inline_number_mismatch(
    printed: str, amount: float, expected_message_fragment: str,
) -> None:
    """Rule 3 stop: inline number must equal item amount exactly."""
    with pytest.raises(ValueError) as excinfo:
        pass2_amount_scale(printed, amount)
    assert expected_message_fragment in str(excinfo.value)


@pytest.mark.parametrize(
    ("printed", "amount", "expected_message_fragment"),
    [
        # Number without dollar sign and without scale word
        ("0.7", 0.7, "it holds no scale word (thousands, millions or billions)"),
        ("5", 5.0, "it holds no scale word (thousands, millions or billions)"),
        # Number with dollar sign but without scale word -> dollars outside scale clause
        ("$0.7", 0.7, "it names dollars outside a clause of the form '<dollars> in <scale>'"),
        ("$5", 5.0, "it names dollars outside a clause of the form '<dollars> in <scale>'"),
        # Dollars outside clause
        ("(in dollars)", 5.0, "it names dollars outside a clause of the form '<dollars> in <scale>'"),
        # Share units without money figures
        ("(Shares in thousands)", 5.0, "it holds no scale word (thousands, millions or billions) that states the unit of the money figures"),
        # Empty string
        ("", 1.0, "it holds no scale word (thousands, millions or billions)"),
    ],
    ids=[
        "missing-scale-word-0.7",
        "missing-scale-word-5",
        "dollars-without-scale-0.7",
        "dollars-without-scale-5",
        "in-dollars-outside-clause",
        "shares-in-thousands-only",
        "empty-string",
    ],
)
def test_pass2_amount_scale_stops_on_missing_or_unreadable_scale(
    printed: str, amount: float, expected_message_fragment: str,
) -> None:
    """Rule 3 stop: must state a recognizable money scale word."""
    with pytest.raises(ValueError) as excinfo:
        pass2_amount_scale(printed, amount)
    assert expected_message_fragment in str(excinfo.value)


# ---------------------------------------------------------------------------
# 2. Pass 2 page checks: _pass2_item_failures and pass2_page_failures
# ---------------------------------------------------------------------------


def test_pass2_page_checks_figure_found_and_not_found(tmp_path: Path) -> None:
    """Figure check: amount must appear on a text line of cited page."""
    # Page 1: cover/other text
    # Page 2: Note 4: Restructuring expenses of 700.0 were incurred, with units statement.
    pdf_path_both = write_text_pdf(
        tmp_path / "filing_both.pdf",
        [
            ["Item 1. Business"],
            ["Note 4. Restructuring", "(in millions)", "Restructuring expenses: 700.0"],
        ],
    )
    pdf_bytes_both = pdf_path_both.read_bytes()

    # Case A: Amount 700.0 found on page 2
    item_ok = NonRecurringItem(
        year=2026,
        description="restructuring charges",
        amount=700.0,
        line_item="sga",
        direction="add_back",
        category="restructuring",
        confidence="high",
        page=2,
        printed_units="(in millions)",
        units_page=2,
        source="Note 4",
    )
    failures = _pass2_item_failures([item_ok], pdf_bytes_both)
    assert failures == []

    # Case B: Amount 750.0 not found on page 2
    item_missing_amount = NonRecurringItem(
        year=2026,
        description="restructuring charges",
        amount=750.0,
        line_item="sga",
        direction="add_back",
        category="restructuring",
        confidence="high",
        page=2,
        printed_units="(in millions)",
        units_page=2,
        source="Note 4",
    )
    failures_b = _pass2_item_failures([item_missing_amount], pdf_bytes_both)
    assert len(failures_b) == 1
    msg = failures_b[0].message
    # Assert message names item, year, amount, page
    assert "non-recurring item (2026, 'restructuring charges')" in msg
    assert "amount 750.0 was not found on page 2" in msg
    assert "no text line there holds that figure" in msg


def test_pass2_page_checks_figure_page_beyond_pdf_or_no_text(tmp_path: Path) -> None:
    """Figure check fails when page is beyond PDF length or page has no text."""
    pdf_path = write_text_pdf(
        tmp_path / "filing.pdf",
        [
            ["Page 1 title"],
            [" "],  # Page 2 has only blank whitespace
        ],
    )
    pdf_bytes = pdf_path.read_bytes()

    # Case A: Page 5 beyond 2-page PDF
    item_beyond = NonRecurringItem(
        year=2026,
        description="litigation",
        amount=50.0,
        line_item="sga",
        direction="add_back",
        category="litigation",
        confidence="high",
        page=5,
        printed_units="(in millions)",
        units_page=1,
        source="Note 10",
    )
    failures_beyond = _pass2_item_failures([item_beyond], pdf_bytes)
    assert any("amount 50.0 cites page 5, but the PDF has 2 pages" in f.message for f in failures_beyond)

    # Case B: Page 2 has no text layer
    item_no_text = NonRecurringItem(
        year=2026,
        description="litigation",
        amount=50.0,
        line_item="sga",
        direction="add_back",
        category="litigation",
        confidence="high",
        page=2,
        printed_units="(in millions)",
        units_page=1,
        source="Note 10",
    )
    failures_no_text = _pass2_item_failures([item_no_text], pdf_bytes)
    assert any("amount 50.0 cannot be confirmed, because page 2 has no text layer" in f.message for f in failures_no_text)


def test_pass2_page_checks_inline_units(tmp_path: Path) -> None:
    """Inline unit words check:
    - units_page must equal page.
    - printed_units must be a substring of normalised page text.
    """
    pdf_path = write_text_pdf(
        tmp_path / "filing.pdf",
        [
            ["Item 1. Business"],
            ["Note 3. Investment", "Gain on PhonePe sale was $0.7 billion in fiscal 2026."],
        ],
    )
    pdf_bytes = pdf_path.read_bytes()

    # Happy path: units_page == page == 2, text '$0.7 billion' on page 2
    item_ok = NonRecurringItem(
        year=2026,
        description="PhonePe gain",
        amount=0.7,
        line_item="cost_of_revenue",
        direction="subtract",
        category="gain_on_sale",
        confidence="high",
        page=2,
        printed_units="$0.7 billion",
        units_page=2,
        source="Note 3",
    )
    assert _pass2_item_failures([item_ok], pdf_bytes) == []

    # Failure 1: units_page != page
    item_wrong_page = NonRecurringItem(
        year=2026,
        description="PhonePe gain",
        amount=0.7,
        line_item="cost_of_revenue",
        direction="subtract",
        category="gain_on_sale",
        confidence="high",
        page=2,
        printed_units="$0.7 billion",
        units_page=1,  # Cites page 1 instead of page 2
        source="Note 3",
    )
    failures_1 = _pass2_item_failures([item_wrong_page], pdf_bytes)
    assert len(failures_1) == 1
    assert "non-recurring item (2026, 'PhonePe gain')" in failures_1[0].message
    assert "inline units '$0.7 billion' cites page 1, but must equal the figure's page 2." in failures_1[0].message

    # Failure 2: text not found on page
    item_text_not_found = NonRecurringItem(
        year=2026,
        description="PhonePe gain",
        amount=0.7,
        line_item="cost_of_revenue",
        direction="subtract",
        category="gain_on_sale",
        confidence="high",
        page=2,
        printed_units="$0.7 million",  # Says million instead of billion
        units_page=2,
        source="Note 3",
    )
    failures_2 = _pass2_item_failures([item_text_not_found], pdf_bytes)
    assert len(failures_2) == 1
    assert "inline units '$0.7 million' was not found on page 2." in failures_2[0].message

    # Failure 3: units_page beyond PDF
    item_units_beyond = NonRecurringItem(
        year=2026,
        description="PhonePe gain",
        amount=0.7,
        line_item="cost_of_revenue",
        direction="subtract",
        category="gain_on_sale",
        confidence="high",
        page=2,
        printed_units="$0.7 billion",
        units_page=5,
        source="Note 3",
    )
    failures_3 = _pass2_item_failures([item_units_beyond], pdf_bytes)
    assert any("units '$0.7 billion' cites page 5, but the PDF has 2 pages." in f.message for f in failures_3)


def test_pass2_page_checks_statement_units(tmp_path: Path) -> None:
    """Statement unit words check:
    - units_page must be page or page - 1.
    - unit_statement_on_page(printed_units, page_text) must be true.
    """
    pdf_path = write_text_pdf(
        tmp_path / "filing.pdf",
        [
            ["Item 1. Business"],
            ["Note 7. Restructuring table header", "(in millions)"],
            ["Note 7 continued", "Severance costs: 50.0"],
        ],
    )
    pdf_bytes = pdf_path.read_bytes()

    # Happy path A: unit statement on page - 1 (page 2 for figure on page 3)
    item_prev_page = NonRecurringItem(
        year=2026,
        description="severance",
        amount=50.0,
        line_item="sga",
        direction="add_back",
        category="severance",
        confidence="high",
        page=3,
        printed_units="(in millions)",
        units_page=2,  # page - 1 is allowed
        source="Note 7",
    )
    assert _pass2_item_failures([item_prev_page], pdf_bytes) == []

    # Happy path B: unit statement on same page (page 2 for figure on page 2)
    # Add a figure to page 2 to test same page
    pdf_path_same = write_text_pdf(
        tmp_path / "filing_same.pdf",
        [
            ["Item 1. Business"],
            ["Note 7. Restructuring table", "(in millions)", "Severance costs: 50.0"],
        ],
    )
    item_same_page = NonRecurringItem(
        year=2026,
        description="severance",
        amount=50.0,
        line_item="sga",
        direction="add_back",
        category="severance",
        confidence="high",
        page=2,
        printed_units="(in millions)",
        units_page=2,
        source="Note 7",
    )
    assert _pass2_item_failures([item_same_page], pdf_path_same.read_bytes()) == []

    # Failure 1: units_page is not page or page - 1 (e.g. page 3 figure cites units on page 1)
    item_too_far = NonRecurringItem(
        year=2026,
        description="severance",
        amount=50.0,
        line_item="sga",
        direction="add_back",
        category="severance",
        confidence="high",
        page=3,
        printed_units="(in millions)",
        units_page=1,  # Must be 3 or 2
        source="Note 7",
    )
    failures_1 = _pass2_item_failures([item_too_far], pdf_bytes)
    assert len(failures_1) == 1
    assert "unit statement '(in millions)' cites page 1, but must be page 3 or 2." in failures_1[0].message

    # Failure 2: unit statement not found on page as whole statement
    # Page 2 has "(in millions)", but test item asserts "(in thousands)"
    item_not_found = NonRecurringItem(
        year=2026,
        description="severance",
        amount=50.0,
        line_item="sga",
        direction="add_back",
        category="severance",
        confidence="high",
        page=3,
        printed_units="(in thousands)",
        units_page=2,
        source="Note 7",
    )
    failures_2 = _pass2_item_failures([item_not_found], pdf_bytes)
    assert len(failures_2) == 1
    assert "unit statement '(in thousands)' was not found on page 2 as a whole printed statement." in failures_2[0].message


def test_pass2_page_failures_public_wrapper(tmp_path: Path) -> None:
    """Verifies the public pass2_page_failures(json_str, pdf_bytes) function."""
    pdf_path = write_text_pdf(
        tmp_path / "filing.pdf",
        [
            ["Item 1. Business"],
            ["Note 3. PhonePe", "Gain on sale $0.7 billion"],
        ],
    )
    pdf_bytes = pdf_path.read_bytes()

    # 1. Empty items list returns [] without error
    empty_json = json.dumps({"non_recurring_items": []})
    assert pass2_page_failures(empty_json, pdf_bytes) == []

    # 2. Valid item returns []
    valid_json = json.dumps({
        "non_recurring_items": [
            {
                "year": 2026,
                "description": "PhonePe gain",
                "amount": 0.7,
                "line_item": "cost_of_revenue",
                "direction": "subtract",
                "category": "gain_on_sale",
                "confidence": "high",
                "source": "Note 3",
                "page": 2,
                "units": {"printed": "$0.7 billion", "page": 2},
            }
        ]
    })
    assert pass2_page_failures(valid_json, pdf_bytes) == []

    # 3. Failing item returns list of failure message strings
    invalid_json = json.dumps({
        "non_recurring_items": [
            {
                "year": 2026,
                "description": "PhonePe gain",
                "amount": 0.8,  # Amount 0.8 not on page 2
                "line_item": "cost_of_revenue",
                "direction": "subtract",
                "category": "gain_on_sale",
                "confidence": "high",
                "source": "Note 3",
                "page": 2,
                "units": {"printed": "$0.8 billion", "page": 2},
            }
        ]
    })
    fails = pass2_page_failures(invalid_json, pdf_bytes)
    assert len(fails) >= 1
    assert any("amount 0.8 was not found on page 2" in msg for msg in fails)


# ---------------------------------------------------------------------------
# 3. Individual Pass 2 scaling in convert_filing_to_millions
# ---------------------------------------------------------------------------


def test_convert_filing_to_millions_mixed_scales_in_one_filing() -> None:
    """Individual item scaling:
    Filing statements are printed in millions.
    Pass 2 items have mixed scales:
    1. PhonePe footnote item: $0.7 billion
       Hand derivation: 0.7 * 1,000 = 700.0 $M
    2. Restructuring charges: (Amounts in millions, except per share data), amount = 2075.0
       Hand derivation: 2075.0 * 1 = 2075.0 $M
    3. Legal settlement: $300 thousand, amount = 300.0
       Hand derivation: 300.0 * (1 / 1000) = 0.3 $M
    4. Severance footnote table: (in thousands), amount = 5200.0
       Hand derivation: 5200.0 * (1 / 1000) = 5.2 $M
    """
    fin = _dummy_financials()
    units = _dummy_units(money_word="millions", money_frac=Fraction(1, 1))

    items = [
        NonRecurringItem(
            year=2026,
            description="PhonePe gain",
            amount=0.7,
            line_item="cost_of_revenue",
            direction="subtract",
            category="gain_on_sale",
            confidence="high",
            page=27,
            printed_units="$0.7 billion",
            units_page=27,
            source="Note 3",
        ),
        NonRecurringItem(
            year=2026,
            description="Restructuring costs",
            amount=2075.0,
            line_item="sga",
            direction="add_back",
            category="restructuring",
            confidence="high",
            page=22,
            printed_units="(Amounts in millions, except per share data)",
            units_page=21,
            source="Note 4",
        ),
        NonRecurringItem(
            year=2026,
            description="Legal settlement",
            amount=300.0,
            line_item="sga",
            direction="add_back",
            category="litigation",
            confidence="high",
            page=45,
            printed_units="$300 thousand",
            units_page=45,
            source="Note 8",
        ),
        NonRecurringItem(
            year=2026,
            description="Severance expense",
            amount=5200.0,
            line_item="sga",
            direction="add_back",
            category="severance",
            confidence="high",
            page=50,
            printed_units="(in thousands)",
            units_page=50,
            source="Note 11",
        ),
    ]

    _, converted_items = convert_filing_to_millions(fin, items, units)

    assert len(converted_items) == 4
    # Hand calculation verification:
    # Item 0: 0.7 * 1000 = 700.0
    assert converted_items[0].amount == pytest.approx(700.0)
    # Item 1: 2075.0 * 1 = 2075.0
    assert converted_items[1].amount == pytest.approx(2075.0)
    # Item 2: 300.0 * (1 / 1000) = 0.3
    assert converted_items[2].amount == pytest.approx(0.3)
    # Item 3: 5200.0 * (1 / 1000) = 5.2
    assert converted_items[3].amount == pytest.approx(5.2)


def test_convert_filing_to_millions_filing_in_thousands_with_footnote_in_millions() -> None:
    """Filing printed in thousands with a footnote item in millions.
    Crucial Rule 1 test:
    - Filing statements are in thousands (multiplier 1 / 1000).
    - Item 1 is an inline footnote item in millions: $5.2 million, amount = 5.2.
      Hand derivation: 5.2 * 1 = 5.2 $M.
      (Must NOT be multiplied by filing scale 1/1000 to get 0.0052!)
    - Item 2 is a statement item in thousands: (in thousands), amount = 5200.0.
      Hand derivation: 5200.0 * (1 / 1000) = 5.2 $M.
    """
    fin = _dummy_financials()
    # Filing scale is thousands
    units = FilingUnits(
        money=UnitStatement("units", "(in thousands)", 1, PrintedScale("thousands", Fraction(1, 1000))),
        shares=UnitStatement("share_units", "(in thousands)", 1, PrintedScale("thousands", Fraction(1, 1000))),
    )

    items = [
        NonRecurringItem(
            year=2026,
            description="Acquisition expense in footnote",
            amount=5.2,
            line_item="sga",
            direction="add_back",
            category="acquisition",
            confidence="high",
            page=35,
            printed_units="$5.2 million",
            units_page=35,
            source="Note 6",
        ),
        NonRecurringItem(
            year=2026,
            description="Restructuring in statement table",
            amount=5200.0,
            line_item="sga",
            direction="add_back",
            category="restructuring",
            confidence="high",
            page=20,
            printed_units="(in thousands)",
            units_page=20,
            source="Note 4",
        ),
    ]

    converted_fin, converted_items = convert_filing_to_millions(fin, items, units)

    # Statement revenue: 1000.0 * (1 / 1000) = 1.0 $M
    assert converted_fin.income_statements[0].revenue == pytest.approx(1.0)

    # Both items evaluate to 5.2 $M despite having different raw amounts and scales
    assert converted_items[0].amount == pytest.approx(5.2)
    assert converted_items[1].amount == pytest.approx(5.2)


# ---------------------------------------------------------------------------
# 4. Session format v4 and CLI cache
# ---------------------------------------------------------------------------


def test_session_extraction_v3_refused_with_remedy(tmp_path: Path) -> None:
    """A session file with format 'session-extraction-v3' is refused by name,
    explaining that Pass 2 shape changed with 'page' and 'units', and giving the remedy.
    """
    v3_session = {
        "format": "session-extraction-v3",
        "provider": "anthropic",
        "model": "claude-test",
        "filings": [],
    }
    path = tmp_path / "test_session_v3.json"
    path.write_text(json.dumps(v3_session), encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)

    msg = str(excinfo.value)
    # Required remedy message components per assignment:
    # v3, v4, page, units, extract-filing
    assert "session-extraction-v3" in msg
    assert SESSION_FORMAT in msg  # session-extraction-v4
    assert "'page'" in msg or "page" in msg
    assert "'units'" in msg or "units" in msg
    assert "extract-filing" in msg


def test_cli_cache_refuses_old_marker(tmp_path: Path) -> None:
    """cli._load_cache refuses cache files written under older markers
    (such as p14a-units-in-millions-v1, p14b-pass2-units-v1) and names the expected marker p14d-finance-leases-v1.
    """
    # Create fake extraction key
    key = cli.ExtractionKey(
        ticker="WMT",
        provider="anthropic",
        model="claude-test",
        inputs=(),
    )
    fin = _dummy_financials()
    items: list[NonRecurringItem] = []

    # Old cache format markers
    for old_marker in ("p14a-units-in-millions-v1", "p14b-pass2-units-v1"):
        old_payload = (old_marker, key, fin, items)
        cache_path = tmp_path / f".cache_wmt_extraction_inputs_{old_marker}.pkl"
        with open(cache_path, "wb") as f:
            pickle.dump(old_payload, f)

        with pytest.raises(ValueError) as excinfo:
            cli._load_cache(cache_path)

        msg = str(excinfo.value)
        assert "p14d-finance-leases-v1" in msg
        assert "expected format marker" in msg


def test_cli_cache_accepts_v1_marker(tmp_path: Path) -> None:
    """cli._load_cache accepts cache files written with CACHE_FORMAT p14d-finance-leases-v1."""
    key = cli.ExtractionKey(
        ticker="WMT",
        provider="anthropic",
        model="claude-test",
        inputs=(),
    )
    fin = _dummy_financials()
    items = [
        NonRecurringItem(
            year=2026,
            description="Restructuring",
            amount=700.0,
            line_item="sga",
            direction="add_back",
            category="restructuring",
            confidence="high",
            page=22,
            printed_units="(in millions)",
            units_page=21,
            source="Note 4",
        )
    ]

    valid_payload = (cli.CACHE_FORMAT, key, fin, items)
    cache_path = tmp_path / ".cache_wmt_extraction_inputs.pkl"
    with open(cache_path, "wb") as f:
        pickle.dump(valid_payload, f)

    loaded_key, loaded_fin, loaded_items = cli._load_cache(cache_path)
    assert loaded_key == key
    assert loaded_fin == fin
    assert loaded_items == items
