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

## Results this file deliberately does NOT assert

Where a missing or malformed input produces a number instead of a stop,
**nothing about the substituted value is asserted**: an assertion would make
the defect permanent and turn its fix red
(`docs/5-testing/strategy.md` section 2).

1. When the company carries debt but reports no interest expense,
   `config.DEFAULT_COST_OF_DEBT` is substituted. The branch is executed here;
   the substituted rate is not asserted. Backlog item 9, rule 6.
2. Backlog item 38b (a): a cost-of-debt override beside a balance sheet with
   no debt lines and a reported interest expense returns weights 1.0 / 0.0,
   because the override returns before item 22's stop. The user is deciding
   its replacement (an explicit confirmation of a zero debt balance). No test
   here asserts that behaviour, either way.

Until `P13a-analysis-silent`, an entry stood here: when
`market_cap + total_debt == 0` the weights were set to 100% equity rather than
stopping (backlog item 38). That branch now raises, and so does a market cap of
zero or below; both stops are locked in the "weights cannot be formed" section.

Until `P13f-wacc-debt`, two more stood here: a negative debt balance formed
weights outside [0, 1] (backlog item 69), and `balance_sheet=None` raised a
bare `AttributeError` (item 38b (b)). Both now stop by name, and so does a
value that is not finite; they are locked in the "debt balance" and "not
finite" sections at the end of this file.
"""

from __future__ import annotations

import math
import re

import pytest

from analysis.wacc import (
    calculate_cost_of_debt,
    calculate_wacc,
    cost_of_debt_with_source,
)
from models.financial_statements import BalanceSheet, IncomeStatement
from models.valuation import CAPMResult

NAN = float("nan")

# ---------------------------------------------------------------------------
# Fixtures, built by hand so every derived figure is checkable on paper.
#
#   CAPMResult        Re = Rf + beta * ERP = 0.04 + 1.2 * 0.05 = 0.10
#
#   IncomeStatement   EBIT = 1000 - 680                  = 320
#                     EBT  = 320 - 20 (interest)         = 300
#                     t    = 75 / 300                    = 0.25
#
#                     `_income_statement(interest_expense=0.0)` is the SAME
#                     company with no borrowings, so:
#                     EBIT = 1000 - 680                  = 320  (unchanged —
#                          interest sits below the operating line)
#                     EBT  = 320 - 0                     = 320
#                     t    = 75 / 320                    = 0.234375
#                     No test that uses the zero-interest variant reads the
#                     tax rate: two supply `tax_rate_override` and the third
#                     asserts an identity that holds for every t.
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
    """No financial debt at all. Payables are still there, and must not count.

    **Pair this only with `_income_statement(interest_expense=0.0)`.** Every
    test below that uses this balance sheet says in its own docstring that its
    subject is a *debt-free company*, and a debt-free company reports no
    interest expense in the same year. Pairing it with the fixture's default
    20 of interest described a company that is debt-free and paying interest
    at once — a contradiction with its own stated subject, and the input on
    which three of the tests below were previously passing.
    """
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
    """Interest expense is used as a magnitude (`analysis/wacc.py:193`), so a
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
    1000/1000 and 0/1000. They are not the old all-equity fallback for
    E + D = 0 (backlog item 38), which this file never asserted and which now
    raises instead; see the "weights cannot be formed" section.

    The income statement reports no interest expense because the subject is a
    debt-free company. Neither the interest nor the tax rate reaches this
    test's arithmetic: the override supplies Rd, `tax_rate_override` supplies
    t, and both are multiplied by a zero debt weight regardless.
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(interest_expense=0.0),
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
    path in `cost_of_debt_with_source` runs rather than the override path.

        WACC = 1.0 * 0.10 + 0.0 * Rd * (1 - t) = 0.10

    The identity holds for **any** Rd and **any** t, because both are
    multiplied by a debt weight of zero. That is why this test asserts the
    WACC and says nothing about `result.cost_of_debt`: with no debt there is
    no rate to measure. It also says nothing about `result.tax_rate`, which on
    this path is the fixture's derived 75 / 320 = 0.234375.

    The income statement reports no interest expense. A company with no debt
    on its balance sheet and 20 of interest on its income statement is not the
    debt-free company this test names in its own title; it is the ambiguity
    `cost_of_debt_with_source` now refuses to resolve on the caller's behalf.
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(interest_expense=0.0),
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
    """`analysis/wacc.py:239-248`: a company with 250 of debt and no separately
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


def test_cost_of_equity_passes_through_unchanged_where_the_weights_can_be_formed() -> None:
    """The cost of equity the CAPM result carries in is the cost of equity the
    WACC result carries out, and it is the one the WACC is built from.

    **Rewritten at `P13a-tests`.** This test was
    `test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`. It
    called `calculate_wacc` with a market cap of 0 and no debt, and asserted
    only the pass-through, because that input reached the all-equity early
    return (backlog item 38) whose weights it refused to bless. `P13a`
    replaced that return with a stop (`analysis/wacc.py:320-334`), so the
    input no longer returns. The subject is kept here on an input where the
    weights can be formed. The old input is now a case of
    `test_weights_that_cannot_be_formed_stop_and_name_market_cap` below.

    A CAPM result unlike the fixture's is used, so the pass-through cannot be
    satisfied by the fixture's 0.10 arriving from anywhere else:

        Re    0.03 + 0.8 * 0.05            = 0.03 + 0.04 = 0.07
        E     300
        D     long-term debt 100            = 100
        V     300 + 100                     = 400
        E/V   300 / 400                     = 0.75
        D/V   100 / 400                     = 0.25
        Rd    20 / 100                      = 0.20
        t     75 / 300                      = 0.25
        WACC  0.75 * 0.07 + 0.25 * 0.20 * (1 - 0.25)
            = 0.0525      + 0.25 * 0.15
            = 0.0525      + 0.0375
            = 0.09
    """
    result = calculate_wacc(
        capm_result=CAPMResult(beta=0.8, risk_free_rate=0.03, equity_risk_premium=0.05),
        income_statement=_income_statement(),
        balance_sheet=BalanceSheet(year=2025, long_term_debt=100.0),
        market_cap=300.0,
    )

    assert result.cost_of_equity == pytest.approx(0.07)
    assert result.wacc == pytest.approx(0.09)


# ---------------------------------------------------------------------------
# The weights cannot be formed. Backlog item 38 and the P13a round 2
# amendment — `analysis/wacc.py:320-349`.
#
# E / (E + D) and D / (E + D) need a positive E. Two stops guard them:
#
#   * E + D == 0      0 / 0. The message names market_cap AND
#                     balance_sheet.total_debt, with both values.
#   * E <= 0          (sum non-zero) every weight is formed from E, so a market
#                     cap of zero or below is an absent input to all of them.
#                     The message names market_cap and its value.
#
# Neither message may state why the input is zero: the function cannot tell.
# Backlog item 37 records that mistake ("did not extract") in this same file.
#
# Not asserted here, on purpose: item 38b (a), an override beside zero debt
# lines and a reported interest expense. A NEGATIVE debt balance (item 69) now
# stops; it is locked in the "debt balance" section at the end of this file.
#
# The expected side of every assertion is an input the test supplied: the
# field names are the arguments, the values are the numbers passed in.
# ---------------------------------------------------------------------------


def _balance_sheet_with_debt_of(total_debt: float) -> BalanceSheet:
    """A balance sheet whose only debt line is long-term debt, so that
    total_debt is exactly the figure passed in.
    """
    return BalanceSheet(year=2025, accounts_payable=500.0, long_term_debt=total_debt)


def _wacc_on(market_cap: float, total_debt: float) -> None:
    """Call `calculate_wacc` on a market cap and a debt balance.

    A debt-free case uses the debt-free income statement (no interest), and a
    case with debt uses the fixture's 20 of interest, so that neither reaches
    item 22's interest-against-zero-debt stop and the weights stop is the one
    under test. No cost-of-debt override is passed: an override beside zero
    debt lines is backlog item 38b.
    """
    interest = 0.0 if total_debt == 0 else 20.0
    calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(interest_expense=interest),
        balance_sheet=_balance_sheet_with_debt_of(total_debt),
        market_cap=market_cap,
    )


# (market_cap, total_debt). The first pair is the input of the test this
# section replaced.
_CANNOT_FORM = [
    pytest.param(0.0, 0.0, id="zero-market-cap-and-zero-debt"),
    pytest.param(-100.0, 100.0, id="sum-is-zero"),
    pytest.param(0.0, 100.0, id="zero-market-cap-beside-debt"),
    pytest.param(-5.0, 100.0, id="negative-market-cap-beside-debt"),
]
_SUM_IS_ZERO = [
    pytest.param(0.0, 0.0, id="zero-market-cap-and-zero-debt"),
    pytest.param(-100.0, 100.0, id="sum-is-zero"),
]


def _stop_message(market_cap: float, total_debt: float) -> str:
    with pytest.raises(ValueError) as raised:
        _wacc_on(market_cap, total_debt)
    return str(raised.value)


def _as_floats(message: str) -> list[float]:
    return [float(n.replace(",", "")) for n in _numbers_in(message)]


@pytest.mark.parametrize(("market_cap", "total_debt"), _CANNOT_FORM)
def test_weights_that_cannot_be_formed_stop_and_name_market_cap(
    market_cap: float, total_debt: float
) -> None:
    """Rule 3. Each pair stops with `ValueError`, and the message names the
    field `market_cap` and the value that was passed for it.
    """
    message = _stop_message(market_cap, total_debt)

    assert "market_cap" in message
    assert market_cap in _as_floats(message)


@pytest.mark.parametrize(("market_cap", "total_debt"), _SUM_IS_ZERO)
def test_a_zero_sum_also_names_the_debt_balance_and_its_value(
    market_cap: float, total_debt: float
) -> None:
    """When E + D == 0 neither input alone is the absent one, so the message
    names both: `market_cap` and `balance_sheet.total_debt`, each with the
    value passed in.
    """
    message = _stop_message(market_cap, total_debt)

    assert "market_cap" in message
    assert "balance_sheet.total_debt" in message
    assert market_cap in _as_floats(message)
    assert total_debt in _as_floats(message)


@pytest.mark.parametrize(("market_cap", "total_debt"), _CANNOT_FORM)
def test_the_weights_stop_does_not_state_a_cause(market_cap: float, total_debt: float) -> None:
    """Backlog item 37. `calculate_wacc` sees two numbers. It cannot tell an
    extraction that failed from a share count that was absent upstream or a
    filing that was misread, so the message must not claim any of them.
    """
    lowered = _stop_message(market_cap, total_debt).lower()

    assert "extract" not in lowered
    assert "fail" not in lowered


def test_a_positive_market_cap_and_debt_form_the_weights_by_hand() -> None:
    """The stops above, and the debt-balance stops added by `P13f`, must not
    catch a company whose weights can be formed (`P13f` criterion 4).

        E    300, D 100 (long-term debt only), V 300 + 100 = 400
        E/V  300 / 400                                     = 0.75
        D/V  100 / 400                                     = 0.25
        Re   0.04 + 1.2 * 0.05                             = 0.10
        Rd   20 / 100                                      = 0.20
        t    75 / (1000 - 680 - 20) = 75 / 300             = 0.25
        WACC 0.75 * 0.10 + 0.25 * 0.20 * (1 - 0.25)
           = 0.075       + 0.25 * 0.15
           = 0.075       + 0.0375
           = 0.1125
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(),
        balance_sheet=_balance_sheet_with_debt_of(100.0),
        market_cap=300.0,
    )

    assert result.equity_weight == pytest.approx(0.75)
    assert result.debt_weight == pytest.approx(0.25)
    assert result.cost_of_debt == pytest.approx(0.20)
    assert result.tax_rate == pytest.approx(0.25)
    assert result.wacc == pytest.approx(0.1125)


def test_the_same_company_with_a_supplied_cost_of_debt_keeps_its_weights() -> None:
    """The debt-balance guards run before the override returns, so they must
    not disturb a valid balance sheet on the override path either.

        E/V, D/V, Re, t  as above            = 0.75, 0.25, 0.10, 0.25
        Rd               supplied            = 0.05
        WACC 0.75 * 0.10 + 0.25 * 0.05 * 0.75
           = 0.075       + 0.009375
           = 0.084375
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(),
        balance_sheet=_balance_sheet_with_debt_of(100.0),
        market_cap=300.0,
        cost_of_debt_override=0.05,
    )

    assert result.equity_weight == pytest.approx(0.75)
    assert result.debt_weight == pytest.approx(0.25)
    assert result.cost_of_debt == pytest.approx(0.05)
    assert result.wacc == pytest.approx(0.084375)


# ---------------------------------------------------------------------------
# The stops. Backlog item 22 — `analysis/wacc.py:195-237`.
#
# A zero debt balance carries two incompatible meanings, and until item 22 was
# closed it returned the same 0.0 for both:
#
#   * the company has no borrowings, and 0.0 is a MEASUREMENT;
#   * the balance sheet did not extract, and 0.0 is a GUESS.
#
# The income statement tells them apart, so the two cases are now two
# behaviours and each is locked below. Neither expected value came from a run:
# the raise is required by rule 3 (a missing input stops and names the field),
# and the 0.0 is required by the definition of a rate on a balance of nothing.
# ---------------------------------------------------------------------------


def _numbers_in(message: str) -> list[str]:
    r"""Every standalone number in a message, so a test can ask whether a figure
    is named without pinning the sentence that names it.

    `(?<![\w.])` stops the 0s inside `20.00` or `2025` from being read as a
    standalone zero, which is what distinguishes "names the debt figure" from
    "the word zero appears somewhere".
    """
    return re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?", message)


def test_a_zero_debt_balance_beside_a_reported_interest_expense_stops() -> None:
    """Rule 3. The interest expense is evidence that the company had borrowings
    during the year, so a total debt of 0 standing beside it is an input the
    run cannot resolve: either the balance sheet did not extract, or the
    company repaid everything before the balance sheet date. Those two imply
    different WACCs and nothing in the two statements chooses between them, so
    the run must stop and say what it saw rather than pick one.

    37 is used rather than the fixture's 20 so that the interest figure and the
    debt figure cannot be confused with one another in the message.

    The expected behaviour is rule 3's, not a recorded output: "a missing input
    stops the run and names the field. It never falls back to zero."
    """
    with pytest.raises(ValueError) as excinfo:
        calculate_cost_of_debt(
            _income_statement(interest_expense=37.0),
            _balance_sheet_without_debt(),
        )

    message = str(excinfo.value)
    numbers = _numbers_in(message)

    # Both figures, so a reader can see the contradiction without re-running.
    assert any(n.startswith("37") for n in numbers), message
    assert any(n in {"0", "0.0", "0.00"} for n in numbers), message

    # And the fields, so a reader knows which three lines to go and look at.
    assert "short_term_debt" in message
    assert "current_portion_lt_debt" in message
    assert "long_term_debt" in message
    assert "interest expense" in message.lower()


def test_the_contradiction_stop_is_not_bypassed_by_a_negative_interest_sign() -> None:
    """A filing that reports interest expense as -37 is reporting the same 37 of
    interest; `analysis/wacc.py:193` takes its magnitude. The contradiction is
    therefore identical, and a guard written as `interest > 0` rather than
    `interest != 0` would let it through.
    """
    with pytest.raises(ValueError):
        calculate_cost_of_debt(
            _income_statement(interest_expense=-37.0),
            _balance_sheet_without_debt(),
        )


def test_the_contradiction_stops_calculate_wacc_too() -> None:
    """The stop must hold on the path a valuation actually takes. `calculate_wacc`
    reads the cost of debt through the same function, so a WACC cannot be
    produced from the contradictory pair either.

    Without the stop this run would return a WACC equal to the cost of equity —
    the debt weight is 0/1000 — which is the understated share price item 22
    describes, on a clean run with nothing in the output saying so.
    """
    with pytest.raises(ValueError):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(interest_expense=37.0),
            balance_sheet=_balance_sheet_without_debt(),
            market_cap=1000.0,
        )


def test_a_genuinely_debt_free_company_measures_zero_and_the_label_says_so() -> None:
    """The other half of the same branch, and it must NOT stop.

    No borrowings and no interest paid on them is a complete, self-consistent
    description of a company. There is no missing input, so rule 3 does not
    apply and the run proceeds.

    **Where the 0.0 comes from, before running anything.** Rd is the rate paid
    on the debt balance. With no debt outstanding there is no balance to pay a
    rate on, and the income statement confirms none was paid. Any non-zero Rd
    here would be a number neither read from the filing nor derived from one —
    an assumption, which rule 6 would then require to be labelled as one. 0.0
    is the only value consistent with "nothing was borrowed and nothing was
    paid", and the WACC identity is what makes it harmless: it is multiplied by
    a debt weight of zero.

    Asserting this 0.0 does **not** encode a fallback. Before item 22 it would
    have: the same 0.0 was returned when the balance sheet had simply failed to
    extract. That case now raises (the three tests above), so the 0.0 asserted
    here can only be reached by the branch that measured it.

    The label is checked for what it *identifies*, not for how it is worded —
    a reformat must not turn this red.
    """
    rate, source = cost_of_debt_with_source(
        _income_statement(interest_expense=0.0),
        _balance_sheet_without_debt(),
    )

    assert rate == pytest.approx(0.0)

    lowered = source.lower()
    # It identifies the case: a company with no debt.
    assert "debt" in lowered
    assert any(phrase in lowered for phrase in ("no debt", "debt-free", "debt free"))
    # And it does not claim to be either of the two things it is not: a
    # substituted constant, or a rate the caller supplied.
    assert "assumption" not in lowered
    assert "substituted" not in lowered
    assert "supplied by the caller" not in lowered


def test_the_debt_free_label_is_not_the_substituted_one() -> None:
    """The label exists to tell a measurement from a guess, so the two must not
    be the same sentence. A company with 400 of debt and no reported interest
    gets `config.DEFAULT_COST_OF_DEBT` substituted; a company with neither gets
    a measured 0.0. Nothing about either *value* is asserted here — only that
    the output distinguishes them, which is the whole purpose of rule 6.
    """
    _measured_rate, debt_free = cost_of_debt_with_source(
        _income_statement(interest_expense=0.0),
        _balance_sheet_without_debt(),
    )
    _substituted_rate, substituted = cost_of_debt_with_source(
        _income_statement(interest_expense=0.0),
        _balance_sheet_with_debt(),
    )

    assert debt_free != substituted
    assert "assumption" in substituted.lower()


# ---------------------------------------------------------------------------
# The NaN guards — `analysis/wacc.py:23-53`, one call site per input.
#
# NaN is the shape a missing input takes once it has been through a float
# calculation, and no comparison detects it: `nan <= x`, `nan > x` and
# `nan == nan` are all False. Each case below makes exactly one input NaN and
# leaves the rest finite, so the field the message names is the field that was
# broken. The expected behaviour is rule 3's, not a recorded output.
# ---------------------------------------------------------------------------


def test_a_nan_cost_of_equity_stops_and_names_the_capm_result() -> None:
    """A NaN beta — the shape a degenerate regression returns — makes
    Re = 0.04 + nan * 0.05 = nan. Without the guard that NaN reaches the
    WACC, the discount factor, and the rendered share price, raising nothing.
    """
    with pytest.raises(ValueError, match="cost_of_equity"):
        calculate_wacc(
            capm_result=CAPMResult(
                beta=NAN, risk_free_rate=0.04, equity_risk_premium=0.05
            ),
            income_statement=_income_statement(),
            balance_sheet=_balance_sheet_with_debt(),
            market_cap=600.0,
        )


def test_a_nan_cost_of_debt_override_stops_and_names_the_cost_of_debt() -> None:
    """Every other input here is the worked example's, which gives 0.075. Only
    the supplied cost of debt is NaN.
    """
    with pytest.raises(ValueError, match="cost_of_debt"):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=_balance_sheet_with_debt(),
            market_cap=600.0,
            cost_of_debt_override=NAN,
        )


def test_a_nan_tax_rate_stops_before_the_clamp_flattens_it_to_zero() -> None:
    """The guard has to sit before `max(0.0, min(tax_rate, 0.50))`, because
    `min(nan, 0.50)` is `nan` and `max(0.0, nan)` is `0.0`: both builtins
    return their first argument when every comparison is False. A NaN tax rate
    would therefore have become a plausible 0.0 — a full tax shield on the
    debt term — with the evidence destroyed.
    """
    with pytest.raises(ValueError, match="tax_rate"):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=_balance_sheet_with_debt(),
            market_cap=600.0,
            tax_rate_override=NAN,
        )


def test_a_nan_market_cap_stops_and_names_the_market_cap() -> None:
    """Market capitalisation is the equity weight's numerator, so a NaN here
    makes both weights NaN and the WACC with them.
    """
    with pytest.raises(ValueError, match="market_cap"):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=_balance_sheet_with_debt(),
            market_cap=NAN,
        )


def test_a_nan_total_debt_stops_and_names_the_balance_sheet_field() -> None:
    """The cost of debt is overridden and the tax rate supplied, so the only
    NaN left is the debt balance itself and the message must name it rather
    than the rate derived from it.
    """
    with pytest.raises(ValueError, match="total_debt"):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=BalanceSheet(year=2025, long_term_debt=NAN),
            market_cap=600.0,
            cost_of_debt_override=0.05,
            tax_rate_override=0.25,
        )


def test_the_nan_guards_are_needed_because_comparisons_do_not_detect_nan() -> None:
    """The premise every guard above rests on, stated as arithmetic rather than
    taken on trust. If any of these were False a comparison-based guard would
    have been enough and `math.isnan` would be ceremony.
    """
    another_nan = float("nan")
    assert (NAN <= 0.5) is False
    assert (NAN > 0.5) is False
    assert (NAN == another_nan) is False  # so `x == x` cannot be a guard either
    assert max(0.0, min(NAN, 0.50)) == 0.0  # the clamp that would hide it
    assert math.isnan(NAN) is True


# ---------------------------------------------------------------------------
# The debt balance. Backlog item 69 and review F3 of `P13f-wacc-debt` —
# `analysis/wacc.py:83-133` (`_require_valid_debt`).
#
# The Pass 1 prompt makes every extracted value positive, with the sign in the
# field name, and a filing prints each debt line as a positive figure. A
# negative debt line is therefore a bad value, and no formula here can use it.
# Left through, market cap 300 beside debt -50 forms V = 250 and weights
# 300 / 250 = 1.2 and -50 / 250 = -0.2, outside [0, 1].
#
# The expected side of every assertion is an input the test supplied: the field
# names are the fields the test made negative, the values are the numbers
# passed in. Item 37 forbids the message from saying why the value is wrong.
# ---------------------------------------------------------------------------

_OVERRIDE_OR_NOT = [
    pytest.param(None, id="no-override"),
    pytest.param(0.05, id="override-0.05"),
]


def _assert_claims_no_cause(message: str) -> None:
    """Backlog item 37: the function sees numbers, not why they are wrong."""
    lowered = message.lower()
    assert "extract" not in lowered, message
    assert "fail" not in lowered, message


@pytest.mark.parametrize("override", _OVERRIDE_OR_NOT)
def test_a_negative_total_debt_stops_and_names_the_total_and_its_value(
    override: float | None,
) -> None:
    """(market cap 300, total debt -50): the only debt line is long-term debt
    of -50, so total_debt = 0 + 0 + (-50) = -50. The run stops with
    `ValueError`, names `balance_sheet.total_debt` and the -50 passed in, and
    claims no cause. A supplied cost of debt does not make the balance usable:
    the weights read it whatever the rate.
    """
    with pytest.raises(ValueError) as raised:
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=_balance_sheet_with_debt_of(-50.0),
            market_cap=300.0,
            cost_of_debt_override=override,
        )
    message = str(raised.value)

    assert "balance_sheet.total_debt" in message
    assert -50.0 in _as_floats(message)
    _assert_claims_no_cause(message)


def test_a_negative_total_debt_stops_the_cost_of_debt_on_a_direct_call() -> None:
    """Without the stop the rate is interest / total debt = 20 / -50 = -0.4, a
    company paid to borrow. `cost_of_debt_with_source` is a public entry point,
    so the stop must hold there too, not only inside `calculate_wacc`.
    """
    with pytest.raises(ValueError) as raised:
        cost_of_debt_with_source(_income_statement(), _balance_sheet_with_debt_of(-50.0))
    message = str(raised.value)

    assert "balance_sheet.total_debt" in message
    assert -50.0 in _as_floats(message)
    _assert_claims_no_cause(message)


# (short_term_debt, current_portion_lt_debt, long_term_debt, the negative line).
# Each total is positive, so a check on the total alone passes all three:
#     -50 +   0 + 100 = 50
#       0 + -10 + 100 = 90
#     100 +   0 + -50 = 50
_NEGATIVE_LINE_UNDER_A_POSITIVE_TOTAL = [
    pytest.param(-50.0, 0.0, 100.0, "short_term_debt", id="short-term-minus-50"),
    pytest.param(0.0, -10.0, 100.0, "current_portion_lt_debt", id="current-portion-minus-10"),
    pytest.param(100.0, 0.0, -50.0, "long_term_debt", id="long-term-minus-50"),
]


@pytest.mark.parametrize("override", _OVERRIDE_OR_NOT)
@pytest.mark.parametrize(
    ("short_term", "current_portion", "long_term", "negative_line"),
    _NEGATIVE_LINE_UNDER_A_POSITIVE_TOTAL,
)
def test_a_negative_debt_line_under_a_positive_total_stops_and_names_the_line(
    short_term: float,
    current_portion: float,
    long_term: float,
    negative_line: str,
    override: float | None,
) -> None:
    """Review F3. The negative line is a bad value even when the total is not
    negative, so the run stops with `ValueError` and names that line as
    `balance_sheet.<line>`. Before the per-line check, short-term -50 beside
    long-term 100 passed as a total of 50.
    """
    with pytest.raises(ValueError) as raised:
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=BalanceSheet(
                year=2025,
                short_term_debt=short_term,
                current_portion_lt_debt=current_portion,
                long_term_debt=long_term,
            ),
            market_cap=300.0,
            cost_of_debt_override=override,
        )
    message = str(raised.value)

    assert f"balance_sheet.{negative_line}" in message
    _assert_claims_no_cause(message)


# ---------------------------------------------------------------------------
# No balance sheet. Backlog item 38b (b) — `analysis/wacc.py:56-80`.
#
# `api/routes_valuation.py` passes `financials.get_balance_sheet(latest_year)`,
# which is None when no balance sheet carries that year. The first read of
# `balance_sheet.total_debt` used to raise a bare `AttributeError` naming no
# input. The stop must be a `ValueError` naming the argument `balance_sheet`
# itself, so the pattern below refuses a `balance_sheet` followed by a dot or a
# letter: `balance_sheet.total_debt` is a field of it, not the argument.
# ---------------------------------------------------------------------------

_NAMES_THE_BALANCE_SHEET_ARGUMENT = r"balance_sheet(?![.\w])"


@pytest.mark.parametrize("override", _OVERRIDE_OR_NOT)
def test_no_balance_sheet_stops_calculate_wacc_and_names_it(override: float | None) -> None:
    """A `ValueError`, not an `AttributeError`, with and without a supplied
    cost of debt. A missing balance sheet is not a debt-free company.
    """
    with pytest.raises(ValueError, match=_NAMES_THE_BALANCE_SHEET_ARGUMENT):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=None,
            market_cap=300.0,
            cost_of_debt_override=override,
        )


@pytest.mark.parametrize("override", _OVERRIDE_OR_NOT)
def test_no_balance_sheet_stops_cost_of_debt_with_source_and_names_it(
    override: float | None,
) -> None:
    """The same stop on the public cost-of-debt entry point."""
    with pytest.raises(ValueError, match=_NAMES_THE_BALANCE_SHEET_ARGUMENT):
        cost_of_debt_with_source(_income_statement(), None, override)


# ---------------------------------------------------------------------------
# Values that are not finite. Review F2 of `P13f-wacc-debt` —
# `analysis/wacc.py:47` (`math.isfinite`).
#
# An infinity passes every sign test written as a comparison (`inf > 0`,
# `inf >= 0` are True, `inf < 0` is False) and then turns a weight into
# inf / inf, which is NaN. Each case makes exactly one input infinite and
# leaves the rest finite, so the field the message names is the field broken.
# ---------------------------------------------------------------------------

INF = math.inf


def test_the_finite_guards_are_needed_because_comparisons_pass_an_infinity() -> None:
    """The premises, as arithmetic. If any were False a sign test would be
    enough. The last two are why a total is checked as well as its lines: two
    finite doubles of 1e308 sum past the largest double (about 1.8e308), which
    IEEE 754 rounds to +inf.
    """
    assert (INF > 0) is True
    assert (INF < 0) is False
    assert math.isnan(INF / INF)
    assert max(0.0, min(INF, 0.50)) == 0.50  # the tax clamp that would hide it
    assert math.isfinite(1e308)
    assert 1e308 + 1e308 == INF


_DEBT_LINES = ["short_term_debt", "current_portion_lt_debt", "long_term_debt"]


@pytest.mark.parametrize("override", _OVERRIDE_OR_NOT)
@pytest.mark.parametrize("line", _DEBT_LINES)
def test_an_infinite_debt_line_stops_and_names_the_line(
    line: str, override: float | None
) -> None:
    """Market cap 300 beside a debt line of +inf: E/V = 300 / inf = 0 and
    D/V = inf / inf = NaN. The run stops instead and names the line.
    """
    with pytest.raises(ValueError, match=line):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=BalanceSheet(year=2025, **{line: INF}),
            market_cap=300.0,
            cost_of_debt_override=override,
        )


def test_a_negative_infinite_debt_line_stops_and_names_the_line() -> None:
    with pytest.raises(ValueError, match="long_term_debt"):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=_balance_sheet_with_debt_of(-INF),
            market_cap=300.0,
        )


def test_finite_debt_lines_that_sum_to_infinity_stop_and_name_the_total() -> None:
    """Each line is 1e308 and finite; their sum is +inf (premise above). The
    total is the field that is not finite, so the total is named.
    """
    with pytest.raises(ValueError, match="balance_sheet.total_debt"):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=BalanceSheet(year=2025, short_term_debt=1e308, long_term_debt=1e308),
            market_cap=300.0,
            cost_of_debt_override=0.05,
        )


def test_an_infinite_market_cap_stops_and_names_it() -> None:
    """E = inf beside D = 400: E/V = inf / inf = NaN."""
    with pytest.raises(ValueError, match="market_cap"):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=_balance_sheet_with_debt(),
            market_cap=INF,
        )


def test_an_infinite_cost_of_equity_stops_and_names_it() -> None:
    """Re = 0.04 + inf * 0.05 = inf, which would make the WACC inf."""
    with pytest.raises(ValueError, match="cost_of_equity"):
        calculate_wacc(
            capm_result=CAPMResult(beta=INF, risk_free_rate=0.04, equity_risk_premium=0.05),
            income_statement=_income_statement(),
            balance_sheet=_balance_sheet_with_debt(),
            market_cap=600.0,
        )


def test_an_infinite_cost_of_debt_override_stops_and_names_it() -> None:
    """D/V = 0.40 times an infinite Rd would make the WACC inf."""
    with pytest.raises(ValueError, match="cost_of_debt"):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=_balance_sheet_with_debt(),
            market_cap=600.0,
            cost_of_debt_override=INF,
        )


@pytest.mark.parametrize("tax", [INF, -INF], ids=["plus-inf", "minus-inf"])
def test_an_infinite_tax_override_stops_before_the_clamp(tax: float) -> None:
    """`max(0.0, min(inf, 0.50))` is 0.50 and `max(0.0, min(-inf, 0.50))` is
    0.0: the clamp would turn either into a plausible rate. The guard sits
    before it and names the tax rate.
    """
    with pytest.raises(ValueError, match="tax_rate"):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(),
            balance_sheet=_balance_sheet_with_debt(),
            market_cap=600.0,
            tax_rate_override=tax,
        )


# ---------------------------------------------------------------------------
# Interest expense that is not finite. Review F4 of `P13f-wacc-debt` —
# `analysis/wacc.py:192`.
#
# Item 22's stop compares `interest != 0`, and `nan != 0` is True, so a NaN
# interest expense beside zero debt used to reach that stop and be printed as
# "interest expense of nan", as if the income statement had reported it. The
# stop must name `income_statement.interest_expense` instead.
#
# No cost-of-debt override is passed anywhere here: with an override the
# interest expense is not read (item 38b (a), open), and this file asserts
# nothing about that path.
# ---------------------------------------------------------------------------

_NOT_FINITE = [
    pytest.param(NAN, id="nan"),
    pytest.param(INF, id="plus-inf"),
]


@pytest.mark.parametrize("interest", _NOT_FINITE)
def test_a_non_finite_interest_beside_zero_debt_stops_and_names_it(interest: float) -> None:
    with pytest.raises(ValueError, match="income_statement.interest_expense"):
        calculate_wacc(
            capm_result=_capm_result(),
            income_statement=_income_statement(interest_expense=interest),
            balance_sheet=_balance_sheet_without_debt(),
            market_cap=1000.0,
        )


@pytest.mark.parametrize("interest", _NOT_FINITE)
def test_a_non_finite_interest_stops_cost_of_debt_with_source_and_names_it(
    interest: float,
) -> None:
    """Both debt balances: zero (item 22's branch) and 400 (where the rate
    would be nan / 400 = nan, or inf / 400 = inf, and returned unchecked).
    """
    for balance_sheet in (_balance_sheet_without_debt(), _balance_sheet_with_debt()):
        with pytest.raises(ValueError, match="income_statement.interest_expense"):
            cost_of_debt_with_source(_income_statement(interest_expense=interest), balance_sheet)
