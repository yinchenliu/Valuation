"""Independently-derived tests for `analysis/normalizer.py`.

Every expected value in this file was computed by hand from the *definition* of a
non-GAAP adjustment before `analysis/normalizer.py` was run, and the arithmetic is
written out above each assertion. **None of them came from executing the code.**

The definition used throughout, taken from `NonRecurringItem`'s docstring
(`models/financial_statements.py:10-20`) and restated in `apply_adjustments`'
docstring:

  * ``add_back`` — the item is a one-time **expense** sitting inside the field.
    A clean base has it removed, so the expense field goes **down** by the amount
    and EBIT goes **up** by the amount.
  * ``remove``   — the item is a one-time **gain** sitting inside the field.
    A clean base has it stripped, so the expense field goes **up** by the amount
    and EBIT goes **down** by the amount.

Both directions are checked on the field *and* on the consequence (EBIT and the
operating margin), because a sign error on the field that cancels downstream is
invisible to a field-only assertion.

The "the sign, one field and one direction at a time" section near the bottom
states the same definition as an invariant on **pre-tax earnings**, which is the
level at which it holds for every line:

    removing a one-time **expense** (``add_back``) raises EBT by the amount;
    removing a one-time **gain**    (``remove``)   lowers EBT by the amount;

whichever line of the statement the item sat on. Every expected number there was
computed from ``IncomeStatement``'s own definitions of ``ebit`` and ``ebt``
(``models/financial_statements.py:66-91``) and written into the test before the
engine was run. **No expectation in this file was taken from
``analysis/normalizer.py``'s sign table, and none is a loop over it** — the table
is the thing under test, so an expectation read from it would be checking itself.
"""

from __future__ import annotations

import pytest

from analysis.normalizer import apply_adjustments, normalize_financials
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)

# --------------------------------------------------------------------------
# Fixtures, built by hand. No network, no key, no pickle.
# --------------------------------------------------------------------------

# Every test below starts from this statement, whose arithmetic is:
#
#   total operating expenses = 400 (COGS) + 200 (SG&A) = 600
#   EBIT                     = 1000 - 600            = 400
#   operating margin         = 400 / 1000            = 0.40
#
_BASE_REVENUE = 1000.0
_BASE_COGS = 400.0
_BASE_SGA = 200.0
_BASE_EBIT = 400.0        # 1000 - (400 + 200)
_BASE_MARGIN = 0.40       # 400 / 1000


def _base_statement(year: int = 2024) -> IncomeStatement:
    """Revenue 1000, COGS 400, SG&A 200 — so EBIT is 400 and the margin 0.40."""
    return IncomeStatement(
        year=year,
        revenue=_BASE_REVENUE,
        cost_of_revenue=_BASE_COGS,
        sga=_BASE_SGA,
    )


def _item(
    line_item: str,
    direction: str,
    amount: float,
    year: int = 2024,
) -> NonRecurringItem:
    """A non-recurring item with only the four fields the normaliser reads."""
    return NonRecurringItem(
        year=year,
        description="test item",
        amount=amount,
        line_item=line_item,
        direction=direction,
        category="restructuring",
    )


def _financials(statements: list[IncomeStatement]) -> FinancialStatements:
    return FinancialStatements(ticker="TEST", income_statements=list(statements))


# A statement with every one of the six adjustable lines non-zero, and both
# below-the-operating-line items populated, so that a sign error on any single
# field cannot hide inside a zero. Its arithmetic, from IncomeStatement's own
# definitions (models/financial_statements.py:66-97):
#
#   total operating expenses = 400 + 200 + 120 + 80 + 60          = 860
#   EBIT   = revenue - total operating expenses = 1000 - 860      = 140
#   EBT    = EBIT - interest_expense + interest_income
#            + other_non_operating = 140 - 30 + 10 + 90           = 210
#   net income = EBT - tax_expense = 210 - 60                     = 150
#
_FULL_EBIT = 140.0
_FULL_EBT = 210.0
_FULL_NET_INCOME = 150.0


def _full_statement(year: int = 2024) -> IncomeStatement:
    """Revenue 1000; all six adjustable lines non-zero; EBIT 140, EBT 210."""
    return IncomeStatement(
        year=year,
        revenue=1000.0,
        cost_of_revenue=400.0,
        sga=200.0,
        rd_expense=120.0,
        depreciation_amortization=80.0,
        other_operating_expense=60.0,
        interest_expense=30.0,
        interest_income=10.0,
        other_non_operating=90.0,
        tax_expense=60.0,
    )


# --------------------------------------------------------------------------
# The identity: nothing to adjust means nothing changes.
# docs/5-testing/strategy.md section 1 names this one.
# --------------------------------------------------------------------------


def test_apply_adjustments_with_no_items_returns_the_very_same_object() -> None:
    """Closed-form identity: an empty adjustment set is the identity map.

    Expected side: `is`, not `==`. A function that rebuilt an equal copy would
    still satisfy `==` while quietly detaching the caller's object.
    """
    statement = _base_statement()
    assert apply_adjustments(statement, []) is statement


def test_normalize_financials_with_no_items_returns_the_very_same_object() -> None:
    """Closed-form identity, at the top level.

    `docs/5-testing/strategy.md` section 1: "an IncomeStatement with no
    non-recurring items normalises to itself".
    """
    financials = _financials([_base_statement(2023), _base_statement(2024)])
    assert normalize_financials(financials, []) is financials


# --------------------------------------------------------------------------
# The two directions, each checked on the field AND on the consequence.
# --------------------------------------------------------------------------


def test_add_back_lowers_the_expense_field_and_raises_ebit_and_margin() -> None:
    """A one-time expense of 50 embedded in SG&A, added back.

    Hand arithmetic, from the definition (a one-time expense is removed to get a
    clean base, so the expense line falls and earnings improve):

        SG&A    : 200 - 50                 = 150
        EBIT    : 1000 - (400 + 150)       = 450
        margin  : 450 / 1000               = 0.45
        d(EBIT) : 450 - 400                = +50   (exactly the amount)
    """
    statement = _base_statement()
    adjusted = apply_adjustments(statement, [_item("sga", "add_back", 50.0)])

    assert adjusted.sga == pytest.approx(150.0)
    assert adjusted.ebit == pytest.approx(450.0)
    assert adjusted.operating_margin == pytest.approx(0.45)
    assert adjusted.ebit - _BASE_EBIT == pytest.approx(50.0)
    assert adjusted.operating_margin > _BASE_MARGIN


def test_remove_raises_the_expense_field_and_lowers_ebit_and_margin() -> None:
    """A one-time gain of 50 embedded in other operating expense, removed.

    Hand arithmetic, from the definition (a one-time gain is stripped to get a
    clean base, so the expense line is restored upwards and earnings fall):

        other_operating_expense : 0 + 50            = 50
        EBIT                    : 1000 - (400 + 200 + 50) = 350
        margin                  : 350 / 1000        = 0.35
        d(EBIT)                 : 350 - 400         = -50   (exactly the amount)
    """
    statement = _base_statement()
    adjusted = apply_adjustments(
        statement, [_item("other_operating_expense", "remove", 50.0)]
    )

    assert adjusted.other_operating_expense == pytest.approx(50.0)
    assert adjusted.ebit == pytest.approx(350.0)
    assert adjusted.operating_margin == pytest.approx(0.35)
    assert adjusted.ebit - _BASE_EBIT == pytest.approx(-50.0)
    assert adjusted.operating_margin < _BASE_MARGIN


def test_the_ebit_move_equals_the_items_own_declared_adjusted_impact() -> None:
    """Cross-file identity, and the cheapest guard against a reversed sign.

    `NonRecurringItem.adjusted_impact` (`models/financial_statements.py:31-37`)
    declares the signed effect on operating income: `+amount` for `add_back`,
    `-amount` for `remove`. It is written in a different file from the engine
    that applies it, so the two agreeing is a real constraint rather than a
    restatement.

        add_back 50 on an operating line  ->  adjusted_impact = +50  ->  dEBIT = +50
        remove   50 on an operating line  ->  adjusted_impact = -50  ->  dEBIT = -50

    Restricted to *operating* lines on purpose: `other_non_operating` sits below
    the operating line, so `adjusted_impact` cannot describe it. See the entry's
    findings.
    """
    for line_item, direction in (
        ("sga", "add_back"),
        ("rd_expense", "add_back"),
        ("cost_of_revenue", "remove"),
        ("other_operating_expense", "remove"),
    ):
        item = _item(line_item, direction, 50.0)
        adjusted = apply_adjustments(_base_statement(), [item])
        assert adjusted.ebit - _BASE_EBIT == pytest.approx(item.adjusted_impact)


# --------------------------------------------------------------------------
# Routing: the adjustment must land on the line the label names, and nowhere
# else. Each expected field here follows from the English meaning of the label,
# not from reading the lookup table.
# --------------------------------------------------------------------------


def _money_fields(statement: IncomeStatement) -> dict[str, float]:
    return {
        "revenue": statement.revenue,
        "cost_of_revenue": statement.cost_of_revenue,
        "sga": statement.sga,
        "rd_expense": statement.rd_expense,
        "depreciation_amortization": statement.depreciation_amortization,
        "other_operating_expense": statement.other_operating_expense,
        "interest_expense": statement.interest_expense,
        "interest_income": statement.interest_income,
        "other_non_operating": statement.other_non_operating,
        "tax_expense": statement.tax_expense,
    }


def test_a_research_and_development_label_moves_rd_expense_and_nothing_else() -> None:
    """An item described as research and development belongs on `rd_expense`.

    Hand arithmetic: `rd_expense` starts at 120 on `_full_statement()`, an
    add_back of 50 takes it to `120 - 50 = 70`, and every other money field
    must be byte-identical to the unadjusted statement. Checking "nothing else
    moved" is what turns a routing test into a routing test — asserting only
    `rd_expense` would pass even if the engine had also touched SG&A.

    It runs on `_full_statement()` rather than `_base_statement()` because the
    latter leaves `rd_expense` at 0, making the expected value `0 - 50 = -50`:
    correct arithmetic on the fixture, but a negative research expense is a
    figure no filing can print, and a test whose expected value cannot occur is
    a worse guard than one whose can. Raised as a note by the reviewer of
    `P1c-flow`; the routing claim under test is unchanged.
    """
    before = _money_fields(_full_statement())
    adjusted = apply_adjustments(
        _full_statement(), [_item("Research and development", "add_back", 50.0)]
    )
    after = _money_fields(adjusted)

    assert after["rd_expense"] == pytest.approx(70.0)
    for name, value in before.items():
        if name != "rd_expense":
            assert after[name] == pytest.approx(value), f"{name} moved and must not"


def test_a_cost_of_goods_label_lands_on_cost_of_revenue() -> None:
    """"Cost of goods sold" and `cost_of_revenue` are the same line.

    Hand arithmetic: 400 - 50 = 350, and EBIT rises to 1000 - (350 + 200) = 450.
    """
    adjusted = apply_adjustments(
        _base_statement(), [_item("Cost of goods sold", "add_back", 50.0)]
    )
    assert adjusted.cost_of_revenue == pytest.approx(350.0)
    assert adjusted.ebit == pytest.approx(450.0)


def test_a_selling_general_label_lands_on_sga() -> None:
    """"Selling, general and administrative" is SG&A.

    Hand arithmetic: 200 - 50 = 150, EBIT = 1000 - (400 + 150) = 450.
    """
    adjusted = apply_adjustments(
        _base_statement(),
        [_item("Selling, general and administrative expenses", "add_back", 50.0)],
    )
    assert adjusted.sga == pytest.approx(150.0)
    assert adjusted.ebit == pytest.approx(450.0)


def test_label_matching_ignores_case_and_surrounding_whitespace() -> None:
    """The label comes from an LLM, so its capitalisation is incidental.

    All three spellings name the same line, so all three must produce the same
    statement: SG&A 200 - 50 = 150.
    """
    for label in ("SG&A", "  sg&a  ", "Sg&A"):
        adjusted = apply_adjustments(_base_statement(), [_item(label, "add_back", 50.0)])
        assert adjusted.sga == pytest.approx(150.0), f"label {label!r} did not route"


# --------------------------------------------------------------------------
# Accumulation across several items.
# --------------------------------------------------------------------------


def test_two_add_backs_on_one_field_accumulate() -> None:
    """Two one-time expenses in SG&A, 30 and 20.

    Hand arithmetic: 200 - 30 - 20 = 150, EBIT = 1000 - (400 + 150) = 450,
    i.e. EBIT improves by the *total* 50, not by the last item alone.
    """
    adjusted = apply_adjustments(
        _base_statement(),
        [_item("sga", "add_back", 30.0), _item("sga", "add_back", 20.0)],
    )
    assert adjusted.sga == pytest.approx(150.0)
    assert adjusted.ebit == pytest.approx(450.0)


def test_opposite_directions_on_one_field_net_off() -> None:
    """A one-time expense of 50 and a one-time gain of 20, both inside SG&A.

    Hand arithmetic, from the definitions:
        SG&A  : 200 - 50 + 20              = 170
        EBIT  : 1000 - (400 + 170)         = 430
        check : 400 + 50 - 20              = 430   (same number, two ways)
    """
    adjusted = apply_adjustments(
        _base_statement(),
        [_item("sga", "add_back", 50.0), _item("sga", "remove", 20.0)],
    )
    assert adjusted.sga == pytest.approx(170.0)
    assert adjusted.ebit == pytest.approx(430.0)


def test_two_items_on_different_fields_both_apply() -> None:
    """An add_back of 50 in SG&A and a remove of 30 in cost of revenue.

    Hand arithmetic:
        SG&A            : 200 - 50         = 150
        cost_of_revenue : 400 + 30         = 430
        EBIT            : 1000 - (430 + 150) = 420
        check           : 400 + 50 - 30    = 420
    """
    adjusted = apply_adjustments(
        _base_statement(),
        [_item("sga", "add_back", 50.0), _item("cost_of_revenue", "remove", 30.0)],
    )
    assert adjusted.sga == pytest.approx(150.0)
    assert adjusted.cost_of_revenue == pytest.approx(430.0)
    assert adjusted.ebit == pytest.approx(420.0)


# --------------------------------------------------------------------------
# normalize_financials: year routing, and what it must leave alone.
# --------------------------------------------------------------------------


def test_an_item_is_applied_to_its_own_year_only() -> None:
    """A 2024 restructuring charge cannot move the 2023 income statement.

    Hand arithmetic: 2024 SG&A 200 - 50 = 150; 2023 SG&A stays at 200 and the
    2023 statement is returned as the identical object, because a year with no
    items is the identity case above.
    """
    statements = [_base_statement(2023), _base_statement(2024)]
    financials = _financials(statements)

    result = normalize_financials(financials, [_item("sga", "add_back", 50.0, 2024)])

    assert result.income_statements[0] is statements[0]
    assert result.income_statements[0].sga == pytest.approx(200.0)
    assert result.income_statements[1].sga == pytest.approx(150.0)
    assert result.income_statements[1].year == 2024


def test_normalize_financials_does_not_mutate_its_input() -> None:
    """A derivation must not edit the statements it derives from.

    Hand arithmetic: the caller still holds a 2024 statement with SG&A 200 and
    EBIT 400 after normalisation has produced one with 150 and 450.
    """
    statement = _base_statement(2024)
    financials = _financials([statement])

    result = normalize_financials(financials, [_item("sga", "add_back", 50.0, 2024)])

    assert statement.sga == pytest.approx(200.0)
    assert statement.ebit == pytest.approx(400.0)
    assert result.income_statements[0].sga == pytest.approx(150.0)


def test_normalize_financials_leaves_the_other_statements_alone() -> None:
    """Adjusting the income statement must not disturb the balance sheet or CFS.

    Expected side: the same figures the fixture supplied — 250 of cash and a
    capital expenditure of -40 — because no adjustment in this repository
    touches either statement.
    """
    financials = FinancialStatements(
        ticker="TEST",
        income_statements=[_base_statement(2024)],
        balance_sheets=[BalanceSheet(year=2024, cash_and_equivalents=250.0)],
        cash_flow_statements=[
            CashFlowStatement(year=2024, capital_expenditures=-40.0)
        ],
    )

    result = normalize_financials(financials, [_item("sga", "add_back", 50.0, 2024)])

    assert result.ticker == "TEST"
    assert len(result.balance_sheets) == 1
    assert result.balance_sheets[0].cash_and_equivalents == pytest.approx(250.0)
    assert len(result.cash_flow_statements) == 1
    assert result.cash_flow_statements[0].capital_expenditures == pytest.approx(-40.0)


# --------------------------------------------------------------------------
# The sign, one field and one direction at a time. Six fields x two
# directions = twelve cases, written out.
#
# THE DEFINITION, and the only place these expectations come from:
#
#   A non-recurring item is a one-time amount sitting inside a reported line.
#   Normalising strips it out to leave a clean, repeatable base.
#
#     * add_back - the item is a one-time **expense**. A clean base does not
#       bear it, so clean pre-tax earnings are **higher** than reported, by
#       exactly the amount.
#     * remove   - the item is a one-time **gain**. A clean base does not
#       enjoy it, so clean pre-tax earnings are **lower** than reported, by
#       exactly the amount.
#
#   That is true of the *earnings*, whichever line of the statement the item
#   sat on. Which way the *line itself* moves is a second, different question,
#   and it follows from how that line enters earnings:
#
#     - the five operating lines are summed into total_operating_expenses and
#       subtracted from revenue (models/financial_statements.py:66-77), so
#       such a line must FALL for earnings to rise;
#     - other_non_operating is **added** by ebt (:91), so it must RISE for
#       earnings to rise.
#
#   Every number below was derived that way and written down before the engine
#   was run. None of it was read from _FIELD_EARNINGS_SIGN, and there is
#   deliberately no loop over that table here: the table is the thing under
#   test, so an expectation taken from it would be checking itself.
#
# The fixture is _full_statement(): EBIT 140, EBT 210, net income 150. The
# amount is 50.0 throughout, so in every one of the twelve cases
#
#     add_back -> EBT 210 + 50 = 260, net income 150 + 50 = 200
#     remove   -> EBT 210 - 50 = 160, net income 150 - 50 = 100
#
# and EBIT moves with EBT on the five operating lines but **must not move at
# all** on other_non_operating, which sits below the operating line.
# --------------------------------------------------------------------------


def test_sign_cost_of_revenue_add_back_raises_pre_tax_earnings() -> None:
    """A one-time expense of 50 inside cost of revenue, added back.

        cost_of_revenue : 400 - 50                           = 350
        EBIT            : 1000 - (350 + 200 + 120 + 80 + 60) = 190
        EBT             : 190 - 30 + 10 + 90                 = 260   (210 + 50)
        net income      : 260 - 60                           = 200
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("cost_of_revenue", "add_back", 50.0)]
    )
    assert adjusted.cost_of_revenue == pytest.approx(350.0)
    assert adjusted.ebit == pytest.approx(190.0)
    assert adjusted.ebt == pytest.approx(260.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(50.0)
    assert adjusted.net_income == pytest.approx(200.0)


def test_sign_cost_of_revenue_remove_lowers_pre_tax_earnings() -> None:
    """A one-time gain of 50 sitting inside cost of revenue, removed.

        cost_of_revenue : 400 + 50                           = 450
        EBIT            : 1000 - (450 + 200 + 120 + 80 + 60) = 90
        EBT             : 90 - 30 + 10 + 90                  = 160   (210 - 50)
        net income      : 160 - 60                           = 100
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("cost_of_revenue", "remove", 50.0)]
    )
    assert adjusted.cost_of_revenue == pytest.approx(450.0)
    assert adjusted.ebit == pytest.approx(90.0)
    assert adjusted.ebt == pytest.approx(160.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(-50.0)
    assert adjusted.net_income == pytest.approx(100.0)


def test_sign_sga_add_back_raises_pre_tax_earnings() -> None:
    """A one-time expense of 50 inside SG&A, added back.

        sga        : 200 - 50                             = 150
        EBIT       : 1000 - (400 + 150 + 120 + 80 + 60)   = 190
        EBT        : 190 - 30 + 10 + 90                   = 260   (210 + 50)
        net income : 260 - 60                             = 200
    """
    adjusted = apply_adjustments(_full_statement(), [_item("sga", "add_back", 50.0)])
    assert adjusted.sga == pytest.approx(150.0)
    assert adjusted.ebit == pytest.approx(190.0)
    assert adjusted.ebt == pytest.approx(260.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(50.0)
    assert adjusted.net_income == pytest.approx(200.0)


def test_sign_sga_remove_lowers_pre_tax_earnings() -> None:
    """A one-time gain of 50 sitting inside SG&A, removed.

        sga        : 200 + 50                             = 250
        EBIT       : 1000 - (400 + 250 + 120 + 80 + 60)   = 90
        EBT        : 90 - 30 + 10 + 90                    = 160   (210 - 50)
        net income : 160 - 60                             = 100
    """
    adjusted = apply_adjustments(_full_statement(), [_item("sga", "remove", 50.0)])
    assert adjusted.sga == pytest.approx(250.0)
    assert adjusted.ebit == pytest.approx(90.0)
    assert adjusted.ebt == pytest.approx(160.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(-50.0)
    assert adjusted.net_income == pytest.approx(100.0)


def test_sign_rd_expense_add_back_raises_pre_tax_earnings() -> None:
    """A one-time expense of 50 inside R&D, added back.

        rd_expense : 120 - 50                             = 70
        EBIT       : 1000 - (400 + 200 + 70 + 80 + 60)    = 190
        EBT        : 190 - 30 + 10 + 90                   = 260   (210 + 50)
        net income : 260 - 60                             = 200
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("rd_expense", "add_back", 50.0)]
    )
    assert adjusted.rd_expense == pytest.approx(70.0)
    assert adjusted.ebit == pytest.approx(190.0)
    assert adjusted.ebt == pytest.approx(260.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(50.0)
    assert adjusted.net_income == pytest.approx(200.0)


def test_sign_rd_expense_remove_lowers_pre_tax_earnings() -> None:
    """A one-time gain of 50 sitting inside R&D, removed.

        rd_expense : 120 + 50                             = 170
        EBIT       : 1000 - (400 + 200 + 170 + 80 + 60)   = 90
        EBT        : 90 - 30 + 10 + 90                    = 160   (210 - 50)
        net income : 160 - 60                             = 100
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("rd_expense", "remove", 50.0)]
    )
    assert adjusted.rd_expense == pytest.approx(170.0)
    assert adjusted.ebit == pytest.approx(90.0)
    assert adjusted.ebt == pytest.approx(160.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(-50.0)
    assert adjusted.net_income == pytest.approx(100.0)


def test_sign_depreciation_amortization_add_back_raises_pre_tax_earnings() -> None:
    """A one-time expense of 50 inside D&A, added back.

        depreciation_amortization : 80 - 50               = 30
        EBIT       : 1000 - (400 + 200 + 120 + 30 + 60)   = 190
        EBT        : 190 - 30 + 10 + 90                   = 260   (210 + 50)
        net income : 260 - 60                             = 200
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("depreciation_amortization", "add_back", 50.0)]
    )
    assert adjusted.depreciation_amortization == pytest.approx(30.0)
    assert adjusted.ebit == pytest.approx(190.0)
    assert adjusted.ebt == pytest.approx(260.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(50.0)
    assert adjusted.net_income == pytest.approx(200.0)


def test_sign_depreciation_amortization_remove_lowers_pre_tax_earnings() -> None:
    """A one-time gain of 50 sitting inside D&A, removed.

        depreciation_amortization : 80 + 50               = 130
        EBIT       : 1000 - (400 + 200 + 120 + 130 + 60)  = 90
        EBT        : 90 - 30 + 10 + 90                    = 160   (210 - 50)
        net income : 160 - 60                             = 100
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("depreciation_amortization", "remove", 50.0)]
    )
    assert adjusted.depreciation_amortization == pytest.approx(130.0)
    assert adjusted.ebit == pytest.approx(90.0)
    assert adjusted.ebt == pytest.approx(160.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(-50.0)
    assert adjusted.net_income == pytest.approx(100.0)


def test_sign_other_operating_expense_add_back_raises_pre_tax_earnings() -> None:
    """A one-time expense of 50 inside other operating expense, added back.

        other_operating_expense : 60 - 50                 = 10
        EBIT       : 1000 - (400 + 200 + 120 + 80 + 10)   = 190
        EBT        : 190 - 30 + 10 + 90                   = 260   (210 + 50)
        net income : 260 - 60                             = 200
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("other_operating_expense", "add_back", 50.0)]
    )
    assert adjusted.other_operating_expense == pytest.approx(10.0)
    assert adjusted.ebit == pytest.approx(190.0)
    assert adjusted.ebt == pytest.approx(260.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(50.0)
    assert adjusted.net_income == pytest.approx(200.0)


def test_sign_other_operating_expense_remove_lowers_pre_tax_earnings() -> None:
    """A one-time gain of 50 sitting inside other operating expense, removed.

        other_operating_expense : 60 + 50                 = 110
        EBIT       : 1000 - (400 + 200 + 120 + 80 + 110)  = 90
        EBT        : 90 - 30 + 10 + 90                    = 160   (210 - 50)
        net income : 160 - 60                             = 100
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("other_operating_expense", "remove", 50.0)]
    )
    assert adjusted.other_operating_expense == pytest.approx(110.0)
    assert adjusted.ebit == pytest.approx(90.0)
    assert adjusted.ebt == pytest.approx(160.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(-50.0)
    assert adjusted.net_income == pytest.approx(100.0)


def test_sign_other_non_operating_add_back_raises_pre_tax_earnings() -> None:
    """A one-time expense of 50 inside other non-operating income, added back.

    This is the case the whole unit exists for, and the one where the line and
    the earnings move the **same** way. other_non_operating is a net income
    line: ebt *adds* it (models/financial_statements.py:91). A one-time expense
    buried in it depressed the reported figure by 50, so a clean base has that
    figure 50 **higher**, not lower:

        other_non_operating : 90 + 50                     = 140
        EBIT                : unchanged                   = 140
            (nothing operating moved - the item sits below the operating line)
        EBT                 : 140 - 30 + 10 + 140         = 260   (210 + 50)
        net income          : 260 - 60                    = 200

    Applying the expense-line rule here instead would give other_non_operating
    40 and EBT 160: a 100 error on a 50 item, reported nowhere.
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("other_non_operating", "add_back", 50.0)]
    )
    assert adjusted.other_non_operating == pytest.approx(140.0)
    assert adjusted.ebit == pytest.approx(_FULL_EBIT)
    assert adjusted.ebt == pytest.approx(260.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(50.0)
    assert adjusted.net_income == pytest.approx(200.0)


def test_sign_other_non_operating_remove_lowers_pre_tax_earnings() -> None:
    """A one-time gain of 50 inside other non-operating income, removed.

    The gain inflated the reported non-operating line, so a clean base has it
    50 **lower**, and pre-tax earnings fall by the amount:

        other_non_operating : 90 - 50                     = 40
        EBIT                : unchanged                   = 140
        EBT                 : 140 - 30 + 10 + 40          = 160   (210 - 50)
        net income          : 160 - 60                    = 100
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("other_non_operating", "remove", 50.0)]
    )
    assert adjusted.other_non_operating == pytest.approx(40.0)
    assert adjusted.ebit == pytest.approx(_FULL_EBIT)
    assert adjusted.ebt == pytest.approx(160.0)
    assert adjusted.ebt - _FULL_EBT == pytest.approx(-50.0)
    assert adjusted.net_income == pytest.approx(100.0)


def test_sign_a_non_operating_item_leaves_every_operating_line_untouched() -> None:
    """The routing half of the non-operating case.

    A below-the-line item must not touch a single operating line. The expected
    values are simply _full_statement()'s own inputs, unchanged, plus the one
    line the item sits on:

        cost_of_revenue 400, sga 200, rd_expense 120,
        depreciation_amortization 80, other_operating_expense 60,
        interest_expense 30, interest_income 10, tax_expense 60,
        other_non_operating 90 + 50 = 140

    Without this, a sign error that moved an operating line by the right amount
    in the right direction would still reach the right EBT.
    """
    adjusted = apply_adjustments(
        _full_statement(), [_item("other non-operating", "add_back", 50.0)]
    )
    assert adjusted.cost_of_revenue == pytest.approx(400.0)
    assert adjusted.sga == pytest.approx(200.0)
    assert adjusted.rd_expense == pytest.approx(120.0)
    assert adjusted.depreciation_amortization == pytest.approx(80.0)
    assert adjusted.other_operating_expense == pytest.approx(60.0)
    assert adjusted.interest_expense == pytest.approx(30.0)
    assert adjusted.interest_income == pytest.approx(10.0)
    assert adjusted.tax_expense == pytest.approx(60.0)
    assert adjusted.other_non_operating == pytest.approx(140.0)
