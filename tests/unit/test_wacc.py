"""Unit tests for `analysis/wacc.py`.

Every expected value in this file was derived **before the code ran**, from the
hand arithmetic written out above the assertion or from a closed-form identity
that must hold whatever the inputs are. No expected value here was obtained by
running the code and recording what it printed.
See `docs/5-testing/strategy.md` section 1.

Nothing here needs an API key, a PDF, or the network.
See `docs/5-testing/strategy.md` section 3.

The formulas, from `docs/3-architecture/valuation-math.md` section 6:

    Rd   = interest_expense / total_debt
    WACC = (E/V) * Re + (D/V) * Rd * (1 - t)

where E is market capitalisation, D is **book** total debt, V = E + D. Money is
in millions (`docs/4-conventions/units-and-signs.md` section 1); rates are
decimals.

## Two results this file deliberately does NOT assert

`analysis/wacc.py` holds two places where a missing input produces a number
instead of a stop. Both are executed here, so the branch is covered, but
**nothing about the substituted value is asserted** — an assertion would make
the defect permanent and turn its fix red
(`docs/5-testing/strategy.md` section 2).

1. `analysis/wacc.py:41-43` — when the company carries debt but reports no
   interest expense, `config.DEFAULT_COST_OF_DEBT` is substituted and nothing
   in the output says so. Backlog item 9, rule 6.
2. `analysis/wacc.py:77-84` — when `market_cap + total_debt == 0` the weights
   are set to 100% equity rather than stopping. A company with no market cap
   and no debt is not an all-equity company; it is missing data. Rule 3.
"""

from __future__ import annotations

import pytest

from analysis.wacc import calculate_cost_of_debt, calculate_wacc
from models.financial_statements import BalanceSheet, IncomeStatement
from models.valuation import CAPMResult

# ---------------------------------------------------------------------------
# Fixtures, built by hand so every derived figure is checkable on paper.
#
#   CAPMResult        Re = Rf + beta * ERP = 0.04 + 1.2 * 0.05 = 0.10
#
#   IncomeStatement   EBIT = 1000 - 680                  = 320
#                     EBT  = 320 - 20 (interest)         = 300
#                     t    = 75 / 300                    = 0.25
#
#   BalanceSheet      total_debt = short-term 100
#                                + current portion 50
#                                + long-term 250         = 400
#                     Accounts payable and other non-current liabilities are
#                     set to large values on purpose: neither is financial
#                     debt, so counting either would break every weight below.
# ---------------------------------------------------------------------------

COST_OF_EQUITY = 0.10


def _capm_result() -> CAPMResult:
    return CAPMResult(beta=1.2, risk_free_rate=0.04, equity_risk_premium=0.05)


def _income_statement(interest_expense: float = 20.0) -> IncomeStatement:
    return IncomeStatement(
        year=2025,
        revenue=1000.0,
        cost_of_revenue=680.0,
        interest_expense=interest_expense,
        tax_expense=75.0,
    )


def _balance_sheet_with_debt() -> BalanceSheet:
    return BalanceSheet(
        year=2025,
        accounts_payable=500.0,
        short_term_debt=100.0,
        current_portion_lt_debt=50.0,
        long_term_debt=250.0,
        other_non_current_liabilities=9999.0,
    )


def _balance_sheet_without_debt() -> BalanceSheet:
    """No financial debt at all. Payables are still there, and must not count."""
    return BalanceSheet(year=2025, accounts_payable=500.0)


# ---------------------------------------------------------------------------
# The cost of equity the fixture supplies
# ---------------------------------------------------------------------------


def test_the_capm_fixture_supplies_a_ten_percent_cost_of_equity() -> None:
    """Re = Rf + beta * ERP = 0.04 + 1.2 * 0.05 = 0.04 + 0.06 = 0.10.

    Pinned here so the WACC arithmetic below is about `analysis/wacc.py` and
    not about how `CAPMResult` computes its own property.
    """
    assert _capm_result().cost_of_equity == pytest.approx(COST_OF_EQUITY)


# ---------------------------------------------------------------------------
# calculate_cost_of_debt
# ---------------------------------------------------------------------------


def test_cost_of_debt_is_interest_over_total_debt() -> None:
    """Rd = interest_expense / total_debt = 20 / (100 + 50 + 250)
                                          = 20 / 400
                                          = 0.05

    The 500 of accounts payable and the 9999 of other non-current liabilities
    in the fixture are not financial debt. Counting the payables would give
    20 / 900 = 0.0222; counting everything would give 20 / 10899.
    """
    rate = calculate_cost_of_debt(_income_statement(), _balance_sheet_with_debt())
    assert rate == pytest.approx(0.05)


def test_cost_of_debt_is_the_same_for_either_interest_sign() -> None:
    """Interest expense is used as a magnitude (`analysis/wacc.py:40`), so a
    filing that reports it as -20 must give the same 20 / 400 = 0.05.

    Carrying the sign through would give -0.05, i.e. a company paid to borrow.
    """
    positive = calculate_cost_of_debt(
        _income_statement(interest_expense=20.0), _balance_sheet_with_debt()
    )
    negative = calculate_cost_of_debt(
        _income_statement(interest_expense=-20.0), _balance_sheet_with_debt()
    )
    assert positive == pytest.approx(0.05)
    assert negative == pytest.approx(0.05)


def test_cost_of_debt_override_replaces_the_derived_rate() -> None:
    """The override is returned unchanged and the financials are not consulted.

    The same fixtures imply 20 / 400 = 0.05, so a run that ignored the override
    would return 0.05 rather than the 0.065 supplied.
    """
    rate = calculate_cost_of_debt(
        _income_statement(), _balance_sheet_with_debt(), override=0.065
    )
    assert rate == pytest.approx(0.065)


# ---------------------------------------------------------------------------
# calculate_wacc — the worked example
# ---------------------------------------------------------------------------


def test_wacc_worked_example() -> None:
    """The whole formula, by hand, before running anything.

        E            market cap                              =  600
        D            100 + 50 + 250                          =  400
        V            600 + 400                               = 1000
        E/V          600 / 1000                              = 0.60
        D/V          400 / 1000                              = 0.40
        Re           0.04 + 1.2 * 0.05                       = 0.10
        Rd           20 / 400                                = 0.05
        t            75 / 300                                = 0.25
        WACC         0.60 * 0.10 + 0.40 * 0.05 * (1 - 0.25)
                   = 0.06       + 0.40 * 0.0375
                   = 0.06       + 0.015
                   = 0.075
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(),
        balance_sheet=_balance_sheet_with_debt(),
        market_cap=600.0,
    )

    assert result.cost_of_equity == pytest.approx(0.10)
    assert result.cost_of_debt == pytest.approx(0.05)
    assert result.tax_rate == pytest.approx(0.25)
    assert result.equity_weight == pytest.approx(0.60)
    assert result.debt_weight == pytest.approx(0.40)
    assert result.wacc == pytest.approx(0.075)


def test_the_weights_sum_to_one() -> None:
    """Closed-form identity: E/V + D/V = (E + D)/V = V/V = 1, whatever E and D
    are, provided V is not zero. Checked at a lopsided split that shares no
    figure with the worked example: E = 900, D = 400, V = 1300.
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(),
        balance_sheet=_balance_sheet_with_debt(),
        market_cap=900.0,
    )
    assert result.equity_weight + result.debt_weight == pytest.approx(1.0)
    assert result.equity_weight == pytest.approx(900.0 / 1300.0)
    assert result.debt_weight == pytest.approx(400.0 / 1300.0)


# ---------------------------------------------------------------------------
# The two closed-form identities named in docs/5-testing/strategy.md section 1
# ---------------------------------------------------------------------------


def test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt() -> None:
    """Closed-form identity: with D = 0 the debt term vanishes, so

        WACC = 1.0 * Re + 0.0 * Rd * (1 - t) = Re = 0.10

    whatever Rd and t are. The cost of debt is overridden to an absurd 90% and
    the tax rate to 40% precisely so that the independence is visible: if the
    debt term reached the answer at all, 0.10 could not survive it.

    Market cap is 1000, not 0, so the weights here are the computed
    1000/1000 and 0/1000 — **not** the `wacc.py:77-84` all-equity fallback,
    which this file never asserts.
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(),
        balance_sheet=_balance_sheet_without_debt(),
        market_cap=1000.0,
        cost_of_debt_override=0.90,
        tax_rate_override=0.40,
    )

    assert result.equity_weight == pytest.approx(1.0)
    assert result.debt_weight == pytest.approx(0.0)
    assert result.wacc == pytest.approx(COST_OF_EQUITY)
    assert result.wacc == pytest.approx(0.10)


def test_a_debt_free_company_prices_at_its_cost_of_equity() -> None:
    """The same identity without the cost-of-debt override, so the derivation
    path in `calculate_cost_of_debt` runs rather than the override path.

        WACC = 1.0 * 0.10 + 0.0 * Rd * (1 - 0.25) = 0.10

    The identity holds for any Rd, which is why this test asserts the WACC and
    says nothing about `result.cost_of_debt`: with no debt there is no rate to
    measure, and `analysis/wacc.py:37-38` returns 0.0 for it. Asserting that
    0.0 would encode "no debt" and "no data" as the same thing.
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(),
        balance_sheet=_balance_sheet_without_debt(),
        market_cap=1000.0,
    )

    assert result.debt_weight == pytest.approx(0.0)
    assert result.wacc == pytest.approx(0.10)


def test_wacc_at_a_zero_tax_rate_is_the_plain_weighted_average() -> None:
    """Closed-form identity: at t = 0 the interest tax shield vanishes and
    WACC collapses to the plain weighted average of the two costs.

        E/V   750 / (750 + 250)                = 0.75
        D/V   250 / 1000                       = 0.25
        WACC  0.75 * 0.10 + 0.25 * 0.08 * 1.0
            = 0.075       + 0.02
            = 0.095

    At the fixture's own 25% rate the same inputs would give
    0.075 + 0.25 * 0.08 * 0.75 = 0.090, so this is not a rate-independent
    assertion — it tells the two apart.
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(),
        balance_sheet=BalanceSheet(year=2025, long_term_debt=250.0),
        market_cap=750.0,
        cost_of_debt_override=0.08,
        tax_rate_override=0.0,
    )

    assert result.tax_rate == pytest.approx(0.0)
    assert result.equity_weight == pytest.approx(0.75)
    assert result.debt_weight == pytest.approx(0.25)
    assert result.wacc == pytest.approx(0.095)


def test_the_tax_shield_only_reduces_the_debt_term() -> None:
    """Closed-form identity, derived from the formula rather than from a run:
    the difference between the untaxed and taxed WACC is exactly
    (D/V) * Rd * t, because the equity term carries no tax factor.

        untaxed  0.75 * 0.10 + 0.25 * 0.08              = 0.095
        at t=0.25 0.75 * 0.10 + 0.25 * 0.08 * 0.75      = 0.090
        difference (D/V) * Rd * t = 0.25 * 0.08 * 0.25  = 0.005
    """
    taxed = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(),
        balance_sheet=BalanceSheet(year=2025, long_term_debt=250.0),
        market_cap=750.0,
        cost_of_debt_override=0.08,
        tax_rate_override=0.25,
    )

    assert taxed.wacc == pytest.approx(0.090)
    assert 0.095 - taxed.wacc == pytest.approx(0.005)


# ---------------------------------------------------------------------------
# The two substituted values, executed but never asserted
# ---------------------------------------------------------------------------


def test_weights_are_still_the_reported_ones_when_interest_is_not_reported() -> None:
    """`analysis/wacc.py:41-43`: a company with 250 of debt and no separately
    reported interest expense is given `config.DEFAULT_COST_OF_DEBT` instead.

    **This test asserts nothing about that rate.** Backlog item 9 records it as
    a rule 6 defect, and its recorded fix changes the function's signature, so
    an assertion on the value — whether `== 0.04` or `!= 0.0` — would either
    turn that fix red or silently keep passing against it. What is asserted
    here is the arithmetic that does not depend on the substitution:

        E/V   750 / 1000  = 0.75
        D/V   250 / 1000  = 0.25
        Re    0.04 + 1.2 * 0.05 = 0.10
        t     supplied          = 0.25

    The branch is executed, so it is covered; it is simply not blessed.
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(interest_expense=0.0),
        balance_sheet=BalanceSheet(year=2025, long_term_debt=250.0),
        market_cap=750.0,
        tax_rate_override=0.25,
    )

    assert result.cost_of_equity == pytest.approx(0.10)
    assert result.tax_rate == pytest.approx(0.25)
    assert result.equity_weight == pytest.approx(0.75)
    assert result.debt_weight == pytest.approx(0.25)


def test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt() -> None:
    """`analysis/wacc.py:77-84`: when E + D = 0 the function returns weights of
    100% equity and 0% debt rather than stopping.

    **This test asserts nothing about those weights.** A company with no market
    capitalisation and no debt is not an all-equity company; it is a company
    whose inputs are missing, and rule 3 says that must stop and name the
    field. Asserting `equity_weight == 1.0` here would make the defect
    permanent and turn its fix red (`docs/5-testing/strategy.md` section 2).

    What is asserted is the one figure that is a pass-through of an argument
    and so is independent of the defect: the cost of equity the CAPM result
    carried in, 0.04 + 1.2 * 0.05 = 0.10.
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(),
        balance_sheet=_balance_sheet_without_debt(),
        market_cap=0.0,
    )

    assert result.cost_of_equity == pytest.approx(0.10)
