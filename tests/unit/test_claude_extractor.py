"""The parse layer both extraction routes share: `ingestion/claude_extractor.py`.

Since `P9a-session-route`, route A (the API) and route B (a Claude Code session
file) meet at four public functions: `parse_pass1`, `parse_pass2`, `plan_filings`
and `merge_filing_extractions`. Every figure on every page passes through them, so
this file tests them directly, with JSON written by hand.

**Where every expected value comes from.** Each input below is a round number, and
each expected value is either the input itself (a field that must land unchanged),
a line of arithmetic written beside the assertion, or a rule quoted from a document:

- the routing table, `docs/3-architecture/extraction.md`, "Multi-PDF year routing";
- the sign of `capital_expenditures`, `docs/4-conventions/units-and-signs.md`;
- the three Pass 2 stops, the docstring of `_parse_nri_response` and
  `.agent/assignments/P9c-parse-tests.md` section 2.

**No value here was read off the code's output.**

**What is deliberately NOT asserted.** The parser subtracts `depreciation_amortization`
from `other_operating_expense` (backlog item 10). Locking either line's parsed value
would make that subtraction permanent and turn item 10's fix red. The test locks the
identity that must survive the fix instead: EBIT equals the stated operating income.
The parser also hard-codes `acquisitions`, the financing lines and
`current_portion_lt_debt` to `0.0` whatever the filing says; asserting those zeros
would lock a default (`docs/5-testing/strategy.md` section 2), so nothing here does.

No test in this file can reach the API: an autouse fixture replaces `_call_llm` with
a function that raises.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import ingestion.claude_extractor as ce
from ingestion.claude_extractor import (
    FilingPlan,
    merge_filing_extractions,
    parse_pass1,
    parse_pass2,
    plan_filings,
)
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)


@pytest.fixture(autouse=True)
def _no_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Close the API boundary. Nothing in this file should call the model."""

    def _refuse(*args: object, **kwargs: object) -> tuple[str, int, int]:
        raise AssertionError("a parse-layer test reached _call_llm")

    monkeypatch.setattr(ce, "_call_llm", _refuse)


# ---------------------------------------------------------------------------
# The hand-written Pass 1 year. Every value is chosen so the arithmetic is visible.
# ---------------------------------------------------------------------------
#
#   revenue                  1000
#   cost_of_revenue           400
#   gross_profit              600   = 1000 - 400
#   sga                       150
#   rd_expense                100
#   other_operating_expense    50   (D&A of 30 sits inside this line)
#   operating_income          300   = 1000 - 400 - 150 - 100 - 50
#   interest_income            10
#   interest_expense           20
#   other_non_operating        -5
#   tax_expense                57
#   net_income                228   = 300 + 10 - 20 + (-5) - 57
#   cfo                       290
#   capex                      70
#   sbc                        25
#   change_in_working_capital -15
#   diluted_shares             48
#
# Every value is distinct, so a field landing on the wrong attribute is caught.


def _year_2024() -> dict[str, Any]:
    return {
        "year": 2024,
        "revenue": 1000,
        "cost_of_revenue": 400,
        "gross_profit": 600,
        "sga": 150,
        "rd_expense": 100,
        "depreciation_amortization": 30,
        "other_operating_expense": 50,
        "operating_income": 300,
        "interest_expense": 20,
        "interest_income": 10,
        "other_non_operating": -5,
        "tax_expense": 57,
        "net_income": 228,
        "diluted_shares": 48,
        "cfo": 290,
        "capex": 70,
        "sbc": 25,
        "change_in_working_capital": -15,
    }


# A balanced balance sheet, every value distinct:
#   assets      = 100 + 50 + 80 + 60 + 10 + 300 + 200 + 40 + 20 = 860
#   liabilities = 70 + 30 + 15 + 25 + 400 + 35                  = 575
#   equity      = 285;  575 + 285 = 860
def _balance_sheet_2024() -> dict[str, Any]:
    return {
        "year": 2024,
        "cash": 100,
        "short_term_investments": 50,
        "accounts_receivable": 80,
        "inventory": 60,
        "other_current_assets": 10,
        "ppe_net": 300,
        "goodwill": 200,
        "intangible_assets": 40,
        "other_non_current_assets": 20,
        "accounts_payable": 70,
        "accrued_liabilities": 30,
        "other_current_liabilities": 15,
        "short_term_debt": 25,
        "long_term_debt": 400,
        "other_non_current_liabilities": 35,
        "total_equity": 285,
    }


def _pass1(years: list[dict[str, Any]], balance: dict[str, Any] | None = None) -> str:
    return json.dumps({
        "ticker": "TST",
        "company_name": "Test Co",
        "currency": "USD",
        "units": "Millions",
        "historical_years": years,
        "latest_balance_sheet": balance if balance is not None else {},
    })


def _parse_one(year: dict[str, Any], balance: dict[str, Any] | None = None) -> tuple[
    FinancialStatements, list[str],
]:
    return parse_pass1(_pass1([year], balance), "TST", "Test Co")


# ===========================================================================
# 1. parse_pass1 — values
# ===========================================================================

def test_pass1_income_statement_fields_land_on_their_fields() -> None:
    fin, _ = _parse_one(_year_2024())
    (inc,) = fin.income_statements
    # Each expected value is the JSON input above, unchanged.
    assert inc.year == 2024
    assert inc.revenue == 1000.0
    assert inc.cost_of_revenue == 400.0
    assert inc.sga == 150.0
    assert inc.rd_expense == 100.0
    assert inc.interest_expense == 20.0
    assert inc.interest_income == 10.0
    assert inc.other_non_operating == -5.0
    assert inc.tax_expense == 57.0
    assert inc.diluted_shares_outstanding == 48.0
    # gross_profit is a property: 1000 - 400 = 600, the stated figure.
    assert inc.gross_profit == 600.0


def test_pass1_ticker_and_name_come_from_the_caller() -> None:
    # The caller's ticker and name are passed in; the JSON's are the same here, so
    # use different ones to see which wins. The caller's, per parse_pass1's call
    # in both routes (the file's ticker, or -t).
    fin, _ = parse_pass1(_pass1([_year_2024()]), "ABC", "Caller Inc")
    assert fin.ticker == "ABC"
    assert fin.company_name == "Caller Inc"


# Three placements of the same 30 of D&A. In each, the stated operating income
# reconciles to revenue - cost_of_revenue - sga - rd_expense - other_operating_expense:
#
#   inside other_opex:   1000 - 400 - 150 - 100 - 50 = 300
#   inside cost_of_rev:  1000 - 430 - 150 - 100 - 20 = 300
#   not reported (0):    1000 - 400 - 150 - 100 - 50 = 300
#
# Whatever line holds D&A, the parsed EBIT must equal the stated 300. This is the
# identity backlog item 10's fix must preserve; it does not lock the subtraction.
@pytest.mark.parametrize(
    ("label", "overrides"),
    [
        ("D&A inside other_operating_expense", {}),
        ("D&A inside cost_of_revenue",
         {"cost_of_revenue": 430, "gross_profit": 570, "other_operating_expense": 20}),
        ("no D&A reported", {"depreciation_amortization": 0}),
    ],
)
def test_pass1_ebit_equals_the_stated_operating_income(
    label: str, overrides: dict[str, Any],
) -> None:
    year = _year_2024() | overrides
    fin, errors = _parse_one(year)
    # The input reconciles, so the arithmetic check finds nothing (identity).
    assert errors == [], label
    (inc,) = fin.income_statements
    # ebit = revenue - total_operating_expenses (models/financial_statements.py);
    # expected = the stated operating_income, 300 (arithmetic in the comment above).
    assert inc.ebit == 300.0, label


def test_pass1_cash_from_operations_equals_the_stated_cfo() -> None:
    fin, _ = _parse_one(_year_2024())
    (cfs,) = fin.cash_flow_statements
    # The parser builds a residual so that the property equals the JSON cfo: 290.
    assert cfs.cash_from_operations == 290.0
    # The named lines are the JSON inputs, unchanged.
    assert cfs.year == 2024
    assert cfs.net_income == 228.0
    assert cfs.depreciation_amortization == 30.0
    assert cfs.stock_based_compensation == 25.0
    assert cfs.change_in_working_capital == -15.0
    # The residual is the only line left: 290 - 228 - 30 - 25 - (-15) = 22.
    assert cfs.other_operating_activities == 22.0


def test_pass1_capex_is_stored_negative() -> None:
    fin, _ = _parse_one(_year_2024())
    (cfs,) = fin.cash_flow_statements
    # JSON capex is a positive 70 (the schema says POSITIVE). The statement stores
    # a cash outflow as negative: docs/4-conventions/units-and-signs.md, row
    # `capital_expenditures`, "negative (a cash outflow)". So -70.
    assert cfs.capital_expenditures == -70.0


def test_pass1_balance_sheet_fields_land_on_their_fields() -> None:
    fin, _ = _parse_one(_year_2024(), _balance_sheet_2024())
    (bs,) = fin.balance_sheets
    # Each expected value is the JSON input, unchanged; JSON key -> BalanceSheet field.
    assert bs.year == 2024
    assert bs.cash_and_equivalents == 100.0            # cash
    assert bs.short_term_investments == 50.0
    assert bs.accounts_receivable == 80.0
    assert bs.inventory == 60.0
    assert bs.other_current_assets == 10.0
    assert bs.ppe_net == 300.0
    assert bs.goodwill == 200.0
    assert bs.intangible_assets == 40.0
    assert bs.other_non_current_assets == 20.0
    assert bs.accounts_payable == 70.0
    assert bs.accrued_liabilities == 30.0
    assert bs.other_current_liabilities == 15.0
    assert bs.short_term_debt == 25.0
    assert bs.long_term_debt == 400.0
    assert bs.other_non_current_liabilities == 35.0
    assert bs.total_equity == 285.0
    # The input balances (860 = 575 + 285, comment above _balance_sheet_2024),
    # so the parsed sheet does too. A field dropped or swapped across the
    # assets/liabilities line would move this.
    assert bs.balance_check_difference == 0.0


def test_pass1_without_a_balance_sheet_gives_none() -> None:
    # `latest_balance_sheet: {}` is what the prompt asks for when the plan takes
    # the balance sheet from another filing. No sheet, not a sheet of zeros.
    fin, _ = _parse_one(_year_2024(), {})
    assert fin.balance_sheets == []


def test_pass1_years_are_returned_ascending() -> None:
    # Given 2024 then 2023; FinancialStatements.years is documented "sorted ascending".
    older = _year_2024() | {"year": 2023}
    fin, _ = parse_pass1(_pass1([_year_2024(), older]), "TST", "Test Co")
    assert [s.year for s in fin.income_statements] == [2023, 2024]
    assert [s.year for s in fin.cash_flow_statements] == [2023, 2024]


# ---------------------------------------------------------------------------
# 1b. The arithmetic check
# ---------------------------------------------------------------------------

def test_pass1_arithmetic_check_is_clean_when_everything_reconciles() -> None:
    # 600 = 1000 - 400; 300 = 600 - 150 - 100 - 50; 228 = 300 + 10 - 20 - 5 - 57.
    _, errors = _parse_one(_year_2024())
    assert errors == []


def test_pass1_arithmetic_check_names_year_and_field_on_a_gross_profit_miss() -> None:
    # Stated 610 against derived 1000 - 400 = 600: diff 10, 10 / 610 = 1.64% > 0.5%.
    year = _year_2024() | {"gross_profit": 610}
    _, errors = _parse_one(year)
    assert len(errors) == 1
    assert "2024" in errors[0]
    assert "Gross Profit" in errors[0]


@pytest.mark.parametrize(
    ("stated", "expect_error"),
    [
        # |602 - 600| / 602 = 0.33%  <= 0.5%  -> passes
        (602, False),
        # |604 - 600| / 604 = 0.66%  >  0.5%  -> fails
        (604, True),
    ],
)
def test_pass1_gross_profit_tolerance_is_half_a_percent(
    stated: int, expect_error: bool,
) -> None:
    year = _year_2024() | {"gross_profit": stated}
    _, errors = _parse_one(year)
    assert bool(errors) is expect_error


# ===========================================================================
# 2. parse_pass2 — the empty answer and the three stops
# ===========================================================================

def _item(**overrides: Any) -> dict[str, Any]:
    item = {
        "year": 2024,
        "description": "Plant closure",
        "amount": 12.5,
        "line_item": "sga",
        "direction": "add_back",
        "category": "restructuring",
        "confidence": "high",
        "source": "Note 8 - Restructuring",
    }
    item.update(overrides)
    return item


def test_pass2_empty_list_is_an_empty_answer() -> None:
    # The prompt's own words: 'If no non-recurring items are found, return
    # {"non_recurring_items": []}'. An empty list means "read, found none".
    assert parse_pass2('{"non_recurring_items": []}') == []


def test_pass2_item_fields_land_on_their_fields() -> None:
    (item,) = parse_pass2(json.dumps({"non_recurring_items": [_item()]}))
    # Each expected value is the JSON input, unchanged.
    assert item == NonRecurringItem(
        year=2024,
        description="Plant closure",
        amount=12.5,
        line_item="sga",
        direction="add_back",
        category="restructuring",
        confidence="high",
        source="Note 8 - Restructuring",
    )


def test_pass2_absent_key_stops_saying_it_was_not_a_pass2_answer() -> None:
    with pytest.raises(ValueError, match="not a Pass 2 answer"):
        parse_pass2('{"items": []}')


def test_pass2_item_without_confidence_stops_naming_year_and_description() -> None:
    item = _item()
    del item["confidence"]
    with pytest.raises(ValueError, match="'confidence'") as excinfo:
        parse_pass2(json.dumps({"non_recurring_items": [item]}))
    assert "year 2024" in str(excinfo.value)
    assert "Plant closure" in str(excinfo.value)


def test_pass2_item_without_source_stops_naming_year_and_description() -> None:
    item = _item()
    del item["source"]
    with pytest.raises(ValueError, match="'source'") as excinfo:
        parse_pass2(json.dumps({"non_recurring_items": [item]}))
    assert "year 2024" in str(excinfo.value)
    assert "Plant closure" in str(excinfo.value)


def test_pass2_explicit_empty_source_is_accepted() -> None:
    # "An explicit "" is accepted and is rendered (none cited); an absent key
    # stops" (_parse_nri_response docstring). The value is the input, "".
    (item,) = parse_pass2(json.dumps({"non_recurring_items": [_item(source="")]}))
    assert item.source == ""


# ===========================================================================
# 3. plan_filings — the routing table
# ===========================================================================
#
# docs/3-architecture/extraction.md, "Multi-PDF year routing", for filings sorted
# ascending by fiscal year:
#
#   | Filing      | Years extracted       | Balance sheet? |
#   | oldest      | all                   | no             |
#   | each middle | its primary year only | no             |
#   | newest      | its primary year only | yes            |
#
# and, for one filing, P9a step 2: target_years None, include_bs True.

def test_plan_one_filing_takes_every_year_and_the_balance_sheet() -> None:
    (plan,) = plan_filings([(2025, "a.pdf")])
    assert plan.fiscal_year == 2025
    assert plan.pdf_path == "a.pdf"
    assert plan.target_years is None
    assert plan.include_bs is True


def test_plan_three_filings_given_out_of_order() -> None:
    plans = plan_filings([(2024, "b.pdf"), (2025, Path("c.pdf")), (2023, "a.pdf")])
    # Sorted ascending; oldest all years, no B/S; middle its year, no B/S;
    # newest its year with B/S. A Path is carried as its string.
    assert plans == [
        FilingPlan(fiscal_year=2023, pdf_path="a.pdf", target_years=None, include_bs=False),
        FilingPlan(fiscal_year=2024, pdf_path="b.pdf", target_years=(2024,), include_bs=False),
        FilingPlan(fiscal_year=2025, pdf_path="c.pdf", target_years=(2025,), include_bs=True),
    ]


def test_plan_empty_list_stops() -> None:
    with pytest.raises(ValueError, match="empty"):
        plan_filings([])


# ===========================================================================
# 4. merge_filing_extractions
# ===========================================================================

def _plan(fiscal_year: int) -> FilingPlan:
    return FilingPlan(fiscal_year=fiscal_year, pdf_path=f"{fiscal_year}.pdf",
                      target_years=None, include_bs=False)


def _fin(rows: list[tuple[int, float]]) -> FinancialStatements:
    """One income, cash flow and balance sheet per (year, marker); the marker tags
    which filing a statement came from."""
    return FinancialStatements(
        ticker="IGNORED",
        company_name="Ignored",
        income_statements=[IncomeStatement(year=y, revenue=m) for y, m in rows],
        cash_flow_statements=[CashFlowStatement(year=y, net_income=m) for y, m in rows],
        balance_sheets=[BalanceSheet(year=y, cash_and_equivalents=m) for y, m in rows],
    )


def test_merge_prefers_the_filing_whose_fiscal_year_is_the_statement_year() -> None:
    # Filing fiscal 2023 holds 2022 (marker 1), 2023 (2), 2024 (3).
    # Filing fiscal 2024 holds 2022 (marker 5), 2023 (6), 2024 (7).
    #
    # Rule (merge_filing_extractions docstring, P9a step 3): for each year, prefer
    # the filing whose fiscal_year equals that year; otherwise the first seen.
    #   2022: neither is primary -> first seen, fiscal-2023 filing -> 1
    #   2023: primary is fiscal-2023, seen FIRST; the later one must not overwrite -> 2
    #   2024: primary is fiscal-2024, seen SECOND; it must overwrite -> 7
    extractions = [
        (_plan(2023), _fin([(2022, 1.0), (2023, 2.0), (2024, 3.0)]), []),
        (_plan(2024), _fin([(2022, 5.0), (2023, 6.0), (2024, 7.0)]), []),
    ]
    merged, items = merge_filing_extractions(extractions, "TST", "Test Co")
    expected = {2022: 1.0, 2023: 2.0, 2024: 7.0}
    assert {s.year: s.revenue for s in merged.income_statements} == expected
    assert {s.year: s.net_income for s in merged.cash_flow_statements} == expected
    assert {s.year: s.cash_and_equivalents for s in merged.balance_sheets} == expected
    # Ascending by year, and labelled with the caller's ticker and name.
    assert [s.year for s in merged.income_statements] == [2022, 2023, 2024]
    assert (merged.ticker, merged.company_name) == ("TST", "Test Co")
    assert items == []


def _nri(year: int, amount: float, direction: str, description: str) -> NonRecurringItem:
    return NonRecurringItem(year=year, description=description, amount=amount,
                            line_item="sga", direction=direction, category="other",
                            confidence="high", source="Note 1")


def test_merge_keeps_one_item_per_year_amount_direction() -> None:
    first = _nri(2023, 10.0, "add_back", "seen in the 2023 10-K")
    duplicate = _nri(2023, 10.0, "add_back", "same item, seen again in the 2024 10-K")
    opposite = _nri(2023, 10.0, "remove", "same year and amount, opposite direction")
    other = _nri(2024, 4.0, "add_back", "only in the 2024 10-K")
    extractions = [
        (_plan(2023), _fin([]), [first]),
        (_plan(2024), _fin([]), [duplicate, opposite, other]),
    ]
    _, items = merge_filing_extractions(extractions, "TST", "Test Co")
    # Key (year, amount, direction), first seen kept (P9a step 3):
    #   (2023, 10, add_back) twice -> once, the first; (2023, 10, remove) is a
    #   different key and stays; (2024, 4, add_back) stays. 4 in, 3 out.
    assert items == [first, opposite, other]

