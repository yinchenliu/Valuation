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

    The income statement reports no interest expense: the test's own title
    says "no debt", and the interest figure reaches no assertion here — the
    early return at `analysis/wacc.py:215` passes `cost_of_equity` straight
    through.
    """
    result = calculate_wacc(
        capm_result=_capm_result(),
        income_statement=_income_statement(interest_expense=0.0),
        balance_sheet=_balance_sheet_without_debt(),
        market_cap=0.0,
    )

    assert result.cost_of_equity == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# The stops. Backlog item 22 — `analysis/wacc.py:93-135`.
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
    interest; `analysis/wacc.py:91` takes its magnitude. The contradiction is
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
# The NaN guards — `analysis/wacc.py:23-45`, one call site per input.
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
