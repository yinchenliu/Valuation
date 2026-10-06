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

**P11a-tests.** Since `P11a-printed-lines` every Pass 1 money field is a list of
printed rows (`tests/unit/_printed_lines.py`). The fixtures below were rewritten
into that shape with every figure unchanged: each field is one printed row holding
the value it held before, so every expected value below is the one it was.
"""

from __future__ import annotations

import json
import socket
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from google import genai

import ingestion.claude_extractor as ce
from ingestion.claude_extractor import (
    FilingPlan,
    Pass1ShapeError,
    ProviderResolution,
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
from tests.unit._printed_lines import lines, printed_balance_sheet, printed_year
from tests.unit._text_pdf import write_text_pdf

# `_no_socket` lives in `tests/conftest.py` — one definition, not three copies.
# Until P1c this module patched `socket.socket.connect` and
# `socket.create_connection` itself, inside `no_network` below, with no loopback
# exception. That is the version P1b-windows-gate measured as broken: on Windows
# `asyncio.ProactorEventLoop` builds its self-pipe through `127.0.0.1`, so a
# blanket refusal fails tests for a reason that has nothing to do with the
# product. The two socket patches are deleted; the fixture that refuses a
# network address for this module is now the one in `tests/conftest.py`.
pytestmark = pytest.mark.usefixtures("_no_socket")


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
# Each field is ONE printed row holding the value above (P11a shape).


def _year_2024() -> dict[str, Any]:
    return printed_year(2024, {
        "revenue": [1000],
        "cost_of_revenue": [400],
        "gross_profit": [600],
        "sga": [150],
        "rd_expense": [100],
        "depreciation_amortization": [30],
        "other_operating_expense": [50],
        "operating_income": [300],
        "interest_expense": [20],
        "interest_income": [10],
        "other_non_operating": [-5],
        "tax_expense": [57],
        "net_income": [228],
        "diluted_shares": [48],
        "cfo": [290],
        "capex": [70],
        "sbc": [25],
        "change_in_working_capital": [-15],
    })


def _rows(overrides: dict[str, Sequence[float]], balance_sheet: bool = False) -> dict[str, Any]:
    """`{field: [values]}` as printed rows, to merge over a fixture with `|`."""
    return {
        field: lines(field, values, balance_sheet=balance_sheet)
        for field, values in overrides.items()
    }


# A balanced balance sheet, every value distinct:
#   assets      = 100 + 50 + 80 + 60 + 10 + 300 + 200 + 40 + 20 = 860
#   liabilities = 70 + 30 + 15 + 25 + 400 + 35                  = 575
#   equity      = 285;  575 + 285 = 860
# P11a added the two printed totals, read only to check the reading: the filing
# prints "Total assets 860" and "Total liabilities and equity 860", the sums above.
def _balance_sheet_2024() -> dict[str, Any]:
    return printed_balance_sheet(2024, {
        "cash": [100],
        "short_term_investments": [50],
        "accounts_receivable": [80],
        "inventory": [60],
        "other_current_assets": [10],
        "ppe_net": [300],
        "goodwill": [200],
        "intangible_assets": [40],
        "other_non_current_assets": [20],
        "accounts_payable": [70],
        "accrued_liabilities": [30],
        "other_current_liabilities": [15],
        "short_term_debt": [25],
        "long_term_debt": [400],
        "other_non_current_liabilities": [35],
        "total_equity": [285],
        # Memo lines (P10a): each already inside another line, in no total, so
        # the 860 = 575 + 285 balance above does not move. 7 and 3 are used by
        # no other key, so a swap or a mis-mapping cannot pass by accident.
        "noncontrolling_interest_nonredeemable": [7],
        "noncontrolling_interest_redeemable": [3],
        "total_assets": [860],
        "total_liabilities_and_equity": [860],
    })


def _pass1(years: list[dict[str, Any]], balance: dict[str, Any] | None = None) -> str:
    return json.dumps({
        "ticker": "TST",
        "company_name": "Test Co",
        "currency": "USD",
        "units": {"printed": "(in millions)", "page": 50},
        "share_units": {"printed": "(in millions)", "page": 50},
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
#   not reported ([]):   1000 - 400 - 150 - 100 - 50 = 300
#
# Whatever line holds D&A, the parsed EBIT must equal the stated 300. This is the
# identity backlog item 10's fix must preserve; it does not lock the subtraction.
# "Not reported" was an explicit 0 before P11a; in the printed-lines shape it is
# [], "the filing prints no such row", which reads as 0 for a component field.
@pytest.mark.parametrize(
    ("label", "overrides"),
    [
        ("D&A inside other_operating_expense", {}),
        ("D&A inside cost_of_revenue",
         {"cost_of_revenue": [430], "gross_profit": [570], "other_operating_expense": [20]}),
        ("no D&A reported", {"depreciation_amortization": []}),
    ],
)
def test_pass1_ebit_equals_the_stated_operating_income(
    label: str, overrides: dict[str, Sequence[float]],
) -> None:
    year = _year_2024() | _rows(overrides)
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
    assert bs.noncontrolling_interest_nonredeemable == 7.0
    assert bs.noncontrolling_interest_redeemable == 3.0
    # The input balances (860 = 575 + 285, comment above _balance_sheet_2024),
    # so the parsed sheet does too. A field dropped or swapped across the
    # assets/liabilities line would move this.
    assert bs.balance_check_difference == 0.0
    # P11a: the two printed totals are memos carried as read, 860 and 860 (input).
    assert bs.printed_total_assets == 860.0
    assert bs.printed_total_liabilities_and_equity == 860.0


NCI_KEYS = ("noncontrolling_interest_nonredeemable", "noncontrolling_interest_redeemable")
NCI_FIELDS = NCI_KEYS  # the BalanceSheet field carries the JSON key's name


# Before P11a an absent or null NCI key parsed to None ("not extracted"), and
# `analysis/dcf.py:total_noncontrolling_interest` stopped on it. Since P11a the
# parser itself stops on both, earlier and naming the key and the balance sheet
# year (`pass1_problems`). The requirement both tests protect, "never zero", is
# unchanged; only the place the run stops moved. The two tests assert the stop.

@pytest.mark.parametrize("key", NCI_KEYS)
def test_pass1_an_absent_nci_key_stops_never_zero(key: str) -> None:
    """Rule 3 at the parser (P10a step 2, P11a): an absent key stops, naming it.
    A `.get(key, 0)` here would make it 0.0 and overstate the share price by the
    whole minority stake.
    """
    balance = _balance_sheet_2024()
    del balance[key]
    with pytest.raises(Pass1ShapeError) as excinfo:
        _parse_one(_year_2024(), balance)
    # Expected parts: the year and the key (P11a assignment, step 1).
    assert any(
        "balance sheet 2024" in p and f"'{key}'" in p and "absent" in p
        for p in excinfo.value.problems
    ), excinfo.value.problems
    # Exactly the one key removed is reported: the other NCI key (7 or 3) is fine.
    assert len(excinfo.value.problems) == 1


@pytest.mark.parametrize("key", NCI_KEYS)
def test_pass1_a_null_nci_key_stops_never_zero(key: str) -> None:
    balance = _balance_sheet_2024() | {key: None}
    with pytest.raises(Pass1ShapeError) as excinfo:
        _parse_one(_year_2024(), balance)
    assert any(
        "balance sheet 2024" in p and f"'{key}'" in p and "must be a list" in p
        for p in excinfo.value.problems
    ), excinfo.value.problems


def test_pass1_explicit_zero_nci_is_kept_as_zero() -> None:
    """The prompt asks for [] when the filing prints no such line (P11a: "[] if the
    filing prints none"). That is a value and must land as 0.0, not as None: `is
    None`, not falsiness, decides. The redeemable key is also given as one printed
    row of 0, the other way a filing can say "none"; it must land as 0.0 too."""
    balance = _balance_sheet_2024() | _rows(
        {"noncontrolling_interest_nonredeemable": []}, balance_sheet=True,
    ) | _rows({"noncontrolling_interest_redeemable": [0]}, balance_sheet=True)
    fin, _ = _parse_one(_year_2024(), balance)
    (bs,) = fin.balance_sheets
    assert bs.noncontrolling_interest_nonredeemable == 0.0
    assert bs.noncontrolling_interest_redeemable == 0.0
    assert bs.noncontrolling_interest_nonredeemable is not None
    assert bs.noncontrolling_interest_redeemable is not None


def test_pass1_without_a_balance_sheet_gives_none() -> None:
    # `latest_balance_sheet: {}` is what the prompt asks for when the plan takes
    # the balance sheet from another filing. No sheet, not a sheet of zeros.
    fin, _ = _parse_one(_year_2024(), {})
    assert fin.balance_sheets == []


def test_pass1_years_are_returned_ascending() -> None:
    # Given 2024 then 2023; FinancialStatements.years is documented "sorted ascending".
    older = _year_2024() | {"year": 2023}  # `year` stays an integer in the P11a shape
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
    year = _year_2024() | _rows({"gross_profit": [610]})
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
    year = _year_2024() | _rows({"gross_profit": [stated]})
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
        "page": 24,
        "units": {"printed": "(Amounts in millions)", "page": 24},
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
        page=24,
        printed_units="(Amounts in millions)",
        units_page=24,
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
        balance_sheets=[BalanceSheet(year=y, cash_and_equivalents=m, printed_unit_in_millions=1.0) for y, m in rows],
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


def _nri(year: int, amount: float, direction: str, description: str,
         page: int = 1) -> NonRecurringItem:
    return NonRecurringItem(year=year, description=description, amount=amount,
                            line_item="sga", direction=direction, category="other",
                            confidence="high", page=page,
                            printed_units="(Amounts in millions)", units_page=1,
                            source="Note 1")


def test_merge_keeps_one_item_per_year_amount_direction_and_description() -> None:
    """The across-filing key, `nri_identity`: (year, amount, direction, description).

    Renamed from `test_merge_keeps_one_item_per_year_amount_direction`, which named
    the three-field key P14e-nri-dedupe replaced (backlog item 112), and which built
    its "duplicate" with a *different* description — not what a re-report looks like.
    A later filing that re-reports an item copies the printed line, so the text is
    the same; only the PDF page moves, and `page` is out of this key for exactly
    that reason.

    The expected list is read off the key's definition, not off a run:
      - `repeat` agrees with `first` on all four fields (the page differs, and the
        page is not in the key) -> the same item, first seen kept;
      - `opposite` differs in `direction` -> a different key, kept;
      - `differently_worded` differs in `description` -> a different key, kept.
        This is backlog item 119's measured behaviour, recorded, not endorsed:
        deciding that two texts mean one charge is the model's judgement (rule 1),
        so Python keeps both;
      - `other` differs in `year` and `amount` -> a different key, kept.
    5 in, 4 out, in first-seen order.
    """
    first = _nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", page=52)
    repeat = _nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", page=51)
    opposite = _nri(2023, 10.0, "remove", "Restructuring charges, Mexico segment")
    differently_worded = _nri(2023, 10.0, "add_back", "Charges for the Mexico reorganisation")
    other = _nri(2024, 4.0, "add_back", "only in the 2024 10-K")
    extractions = [
        (_plan(2023), _fin([]), [first]),
        (_plan(2024), _fin([]), [repeat, opposite, differently_worded, other]),
    ]
    _, items = merge_filing_extractions(extractions, "TST", "Test Co")
    assert items == [first, opposite, differently_worded, other]
    # The repeat was dropped, not the first: the kept item still carries page 52.
    assert items[0].page == 52


# ===========================================================================
# 5. Route A's Pass 2 retry: an unreadable reply stops, it is never "no items"
# ===========================================================================
#
# P13g-tests. `_run_nri_pass` retries once when the Pass 2 reply does not parse.
# Backlog item 50: when the retry did not parse either, it used to print a warning
# and return [], so "the reply could not be read" reached the page as "the filing
# has no non-recurring items". Rule 3 requires a stop that names the filing. The
# requirement, not the code, is the source of every expectation below:
#
#   - two unreadable replies -> ValueError naming the ticker, the company and both
#     parse errors, after exactly two calls (one attempt, one retry);
#   - an unreadable reply, then a readable one -> the items the readable one lists,
#     each field the JSON input unchanged;
#   - {"non_recurring_items": []} -> [], on the first call, with no retry. The
#     prompt's own words: an empty list means "read, found none".
#
# The parse errors' expected text is computed by the standard library's json.loads
# on the very same reply text, never by the code under test.
#
# NOT locked here, by the assignment: the review's F1 (an OverflowError or a
# RecursionError from the retry escapes without the filing's name) and F2 (some bad
# first replies stop with no retry). Both are backlog items; a test here would make
# today's behaviour permanent.
#
# No call can leave the process: `_call_llm` is a scripted stub, every road to a
# model client raises `_NetworkReached` (a BaseException, so no `except Exception`
# anywhere can swallow it), and the module-level `_no_socket` fixture
# (`tests/conftest.py`) refuses every socket address that leaves this machine with
# an `AssertionError`. The control test proves each road fires.

# Captured at import, before the autouse fixture swaps it, for the control test.
_REAL_CALL_LLM = ce._call_llm

_NRI_RESOLUTION = ProviderResolution(
    provider="gemini", model="gemini-3.1-pro-preview",
    reasoning_label="the provider's default; this code sets no thinking for Gemini",
    transport="gemini-direct",
    transport_label="stub", credential="gemini-api-key",
    credential_source="stub: no call is made",
)


class _NetworkReached(BaseException):
    """Raised by every road to the network while the guard is up."""


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every road to a model client raise; remove every key.

    The socket itself is not patched here. `_no_socket` (`tests/conftest.py`) is
    applied to every test in this module by the `pytestmark` above, and it is the
    one definition of that rule. The model-client patches below are the guard;
    the socket patch was only ever the backstop.
    """

    def _block(*args: object, **kwargs: object) -> Any:
        raise _NetworkReached("a network road was taken")

    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(ce, "_call_gemini", _block)
    monkeypatch.setattr(genai.Client, "__init__", _block)


def _nri_financials() -> FinancialStatements:
    # Two Pass 1 years, so the filing's identity is ticker, company and years.
    return FinancialStatements(
        ticker="ZQX",
        company_name="Zeta Quarry Holdings",
        income_statements=[IncomeStatement(year=2023, revenue=900.0),
                           IncomeStatement(year=2024, revenue=1000.0)],
    )


def _run_pass2(monkeypatch: pytest.MonkeyPatch, answers: list[str],
               pdf_bytes: bytes | None = None,
               ) -> tuple[list[bytes | None], Any]:
    """Run `_run_nri_pass` on scripted replies, one per call, in order.

    Returns the PDF bytes sent with each call, and the outcome: the item list, or
    the exception raised. A call beyond the script raises AssertionError, which is
    not caught here.
    """
    calls: list[bytes | None] = []

    def stub(system_prompt: str, user_prompt: str, resolution: ProviderResolution,
             pdf_bytes: bytes | None = None) -> tuple[str, int, int]:
        if len(calls) >= len(answers):
            raise AssertionError(f"call {len(calls) + 1} was not scripted")
        calls.append(pdf_bytes)
        return answers[len(calls) - 1], 0, 0

    monkeypatch.setattr(ce, "_call_llm", stub)
    try:
        outcome: Any = ce._run_nri_pass(pdf_bytes or b"%PDF-stub", _nri_financials(), _NRI_RESOLUTION)
    except ValueError as exc:  # the outcome under test
        outcome = exc
    return calls, outcome


def _stdlib_parse_error(text: str) -> json.JSONDecodeError:
    """The error the standard library raises on `text`: the independent expectation."""
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        return exc
    raise AssertionError(f"{text!r} parsed; the test needs a reply that does not")


# Two replies, each with braces (so a JSON object is found) and each malformed in
# a different way, so the two parse errors carry different text.
_BAD_FIRST = '{this is not json}'
_BAD_RETRY = '{"non_recurring_items": [}'


def test_pass2_unreadable_twice_stops_naming_the_filing_and_both_errors(
    monkeypatch: pytest.MonkeyPatch, no_network: None,
) -> None:
    first_error = _stdlib_parse_error(_BAD_FIRST)
    retry_error = _stdlib_parse_error(_BAD_RETRY)
    assert str(first_error) != str(retry_error)  # precondition: two distinct errors

    calls, outcome = _run_pass2(monkeypatch, [_BAD_FIRST, _BAD_RETRY])

    # The stop, never the old `return []`.
    assert isinstance(outcome, ValueError), f"expected a ValueError, got {outcome!r}"
    message = str(outcome)
    # One attempt and one retry: exactly two calls.
    assert len(calls) == 2
    # The filing, by what Pass 1 read from it: the inputs of _nri_financials().
    assert "ZQX" in message
    assert "Zeta Quarry Holdings" in message
    # Both parse errors, each the standard library's own text on that reply.
    assert str(first_error) in message
    assert str(retry_error) in message


def test_pass2_unreadable_then_readable_returns_the_items(
    monkeypatch: pytest.MonkeyPatch, no_network: None, tmp_path: Path,
) -> None:
    item = {
        "year": 2023,
        "description": "Quarry litigation settlement",
        "amount": 40.0,
        "line_item": "other_operating_expense",
        "direction": "add_back",
        "category": "litigation",
        "confidence": "medium",
        "page": 1,
        "units": {"printed": "(Amounts in millions)", "page": 1},
        "source": "Note 11 - Contingencies",
    }
    pdf_path = write_text_pdf(
        tmp_path / "nri.pdf",
        [["Quarry litigation settlement 40.0", "(Amounts in millions)"]],
    )
    calls, outcome = _run_pass2(
        monkeypatch, [_BAD_FIRST, json.dumps({"non_recurring_items": [item]})],
        pdf_bytes=pdf_path.read_bytes(),
    )
    assert len(calls) == 2  # the retry was needed, and was made
    # Each expected value is the JSON input, unchanged.
    assert outcome == [NonRecurringItem(
        year=2023,
        description="Quarry litigation settlement",
        amount=40.0,
        line_item="other_operating_expense",
        direction="add_back",
        category="litigation",
        confidence="medium",
        page=1,
        printed_units="(Amounts in millions)",
        units_page=1,
        source="Note 11 - Contingencies",
    )]


def test_pass2_readable_empty_list_is_no_items_on_the_first_call(
    monkeypatch: pytest.MonkeyPatch, no_network: None,
) -> None:
    calls, outcome = _run_pass2(monkeypatch, ['{"non_recurring_items": []}'])
    # "Read, found none" is a real answer: [] and no retry.
    assert outcome == []
    assert len(calls) == 1


def test_the_network_guard_fires(no_network: None) -> None:
    """Control: each road out of this module is closed, and by whom.

    The two model-client roads are closed by `no_network` above and raise
    `_NetworkReached`. The socket road is closed by `_no_socket`
    (`tests/conftest.py`), applied to this module by `pytestmark`, and raises
    `AssertionError` naming the address it refused. The expected type and the
    expected text are the fixture's stated contract (`tests/conftest.py:88`,
    `:93`), not anything this run printed.
    """
    with pytest.raises(_NetworkReached):
        _REAL_CALL_LLM("system", "user", _NRI_RESOLUTION)
    with pytest.raises(_NetworkReached):
        genai.Client(api_key="not-a-key")
    # 192.0.2.1 is TEST-NET-1 (RFC 5737) and example.invalid is .invalid
    # (RFC 2606): neither can resolve to anything real, so a refusal here is the
    # fixture's and no packet can leave on a regression.
    with pytest.raises(AssertionError, match="example.invalid"):
        socket.create_connection(("example.invalid", 443))
    with socket.socket() as sock, pytest.raises(AssertionError, match="192.0.2.1"):
        sock.connect(("192.0.2.1", 443))
    with socket.socket() as sock, pytest.raises(AssertionError, match="192.0.2.1"):
        sock.connect_ex(("192.0.2.1", 443))

