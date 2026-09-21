"""Unit tests for `analysis/capm.py`.

Every expected value in this file was derived **before the code ran**, from the
hand arithmetic written out above the assertion or from a closed-form identity
that must hold whatever the inputs are. The one regression with an imperfect
fit is solved in full by the ordinary-least-squares normal equations in the
comment above it. No expected value here was obtained by running the code and
recording what it printed. See `docs/5-testing/strategy.md` section 1.

Nothing here needs an API key, a PDF, or the network: every `PriceData` is
built in this file from literal returns. `yfinance` is imported as a side
effect of importing `ingestion.price_fetcher`, but no call is made and no
request is issued. See `docs/5-testing/strategy.md` section 3.

`PriceData` is imported from `ingestion/` because `analysis/capm.py:14` does —
a layering break recorded as backlog item 17. This import is evidence for that
item, not a choice made here.

The formulas, from `docs/3-architecture/valuation-math.md` section 5:

    beta           = slope of OLS(stock_returns ~ market_returns)
    market_return  = (prod(1 + r)) ** (periods_per_year / n) - 1
    ERP            = market_return - Rf          (when not supplied)
    cost_of_equity = Rf + beta * ERP

Returns are **periodic**, not annual (`docs/4-conventions/units-and-signs.md`
section 4); `periods_per_year` is what converts them.

## Results this file deliberately does NOT assert

`analysis/capm.py:82-85` sets `r_squared` and `std_error` to `0.0` whenever
`beta_override` is supplied, so a reader cannot tell "no regression was run"
from "the regression explained nothing". Where a test below supplies a beta
override it asserts that the beta passes through and says nothing about the
two diagnostics — asserting them would bless the defect
(`docs/5-testing/strategy.md` section 2).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import config
from analysis.capm import annualized_market_return, calculate_beta, run_capm
from ingestion.price_fetcher import PriceData

# ---------------------------------------------------------------------------
# Fixture builder. `dates` and `current_price` are carried by `PriceData` but
# read by nothing in `analysis/capm.py`; they are supplied consistently anyway
# so the fixture is not internally contradictory.
# ---------------------------------------------------------------------------


def _price_data(
    stock_returns: list[float],
    market_returns: list[float],
    periods_per_year: int,
) -> PriceData:
    n = len(market_returns)
    return PriceData(
        ticker="TEST",
        stock_returns=np.asarray(stock_returns, dtype=float),
        market_returns=np.asarray(market_returns, dtype=float),
        dates=pd.DatetimeIndex(pd.date_range("2020-01-31", periods=n)),
        current_price=100.0,
        periods_per_year=periods_per_year,
    )


# ---------------------------------------------------------------------------
# calculate_beta — OLS slope
# ---------------------------------------------------------------------------


def test_beta_of_a_series_regressed_on_itself_is_exactly_one() -> None:
    """Closed-form identity named in `docs/5-testing/strategy.md` section 1.

    Regressing a series on itself is the line y = x: the slope is 1, the fit
    is perfect so R^2 = 1, and there is no residual so the standard error of
    the slope is 0. This holds for any non-constant series and needs no market
    data at all.
    """
    returns = [0.01, -0.02, 0.03, 0.04, -0.01]
    beta, r_squared, std_error = calculate_beta(_price_data(returns, returns, 12))

    assert beta == pytest.approx(1.0)
    assert r_squared == pytest.approx(1.0)
    assert std_error == pytest.approx(0.0, abs=1e-12)


def test_beta_recovers_an_exact_multiple_and_discards_the_intercept() -> None:
    """Closed-form identity: if every stock return is 2 * the market return
    plus a constant 0.01, the relation is exactly linear with slope 2, so OLS
    must return 2.0 and a perfect fit whatever the constant is.

    The 0.01 is Jensen's alpha. `calculate_beta` discards the intercept — its
    docstring says so — and this test is what makes that visible: a function
    that returned the intercept in the slope's place would give 0.01 here.
    """
    market = [0.01, -0.02, 0.03, 0.04, -0.01]
    stock = [2 * r + 0.01 for r in market]
    beta, r_squared, std_error = calculate_beta(_price_data(stock, market, 12))

    assert beta == pytest.approx(2.0)
    assert r_squared == pytest.approx(1.0)
    assert std_error == pytest.approx(0.0, abs=1e-12)


def test_beta_on_an_imperfect_fit_solved_by_hand() -> None:
    """The regression with a real residual, solved on paper first.

        x (market)  -0.02  -0.01   0.00   0.01   0.02      mean 0
        y (stock)   -0.03  -0.01   0.01   0.01   0.04      mean 0.004

        y - ybar    -0.034 -0.014  0.006  0.006  0.036

        Sxy = sum (x - xbar)(y - ybar)
            = 0.00068 + 0.00014 + 0 + 0.00006 + 0.00072   = 0.00160
        Sxx = sum (x - xbar)^2
            = 0.0004 + 0.0001 + 0 + 0.0001 + 0.0004       = 0.00100
        Syy = sum (y - ybar)^2
            = 0.001156 + 0.000196 + 0.000036 + 0.000036 + 0.001296
                                                          = 0.00272

        beta = Sxy / Sxx = 0.0016 / 0.001                  = 1.6
        R^2  = Sxy^2 / (Sxx * Syy)
             = 0.00000256 / (0.001 * 0.00272)
             = 256 / 272 = 16 / 17                         = 0.941176...

        SSE  = Syy - beta^2 * Sxx = 0.00272 - 2.56 * 0.001 = 0.00016
        s^2  = SSE / (n - 2) = 0.00016 / 3
        SE(beta) = sqrt(s^2 / Sxx) = sqrt(0.00016 / (3 * 0.001))
                 = sqrt(4 / 75)                            = 0.230940...

    An exact-multiple fixture cannot distinguish a correct slope from a
    mis-weighted one, because every reasonable estimator agrees when the fit
    is perfect. This one can.
    """
    market = [-0.02, -0.01, 0.0, 0.01, 0.02]
    stock = [-0.03, -0.01, 0.01, 0.01, 0.04]
    beta, r_squared, std_error = calculate_beta(_price_data(stock, market, 12))

    assert beta == pytest.approx(1.6)
    assert r_squared == pytest.approx(16.0 / 17.0)
    assert std_error == pytest.approx(math.sqrt(4.0 / 75.0))


# ---------------------------------------------------------------------------
# annualized_market_return — geometric
# ---------------------------------------------------------------------------


def test_one_return_with_one_period_per_year_annualizes_to_itself() -> None:
    """Closed-form identity: with n = 1 and periods_per_year = 1 the exponent
    is 1, so the formula is (1 + r) ** 1 - 1 = r, exactly.

        (1 + 0.25) ** (1 / 1) - 1 = 0.25
    """
    result = annualized_market_return(_price_data([0.25], [0.25], 1))
    assert result == pytest.approx(0.25)


def test_twelve_monthly_zero_returns_annualize_to_zero() -> None:
    """A year of flat months is a flat year.

        prod(1 + 0) = 1, and 1 ** (12 / 12) - 1 = 0.0
    """
    zeros = [0.0] * 12
    result = annualized_market_return(_price_data(zeros, zeros, 12))
    assert result == pytest.approx(0.0)


def test_a_constant_annual_return_annualizes_to_itself_whatever_the_count() -> None:
    """Closed-form identity: for a constant periodic return r over n periods,
    prod(1 + r) = (1 + r) ** n, so the annualized figure is

        ((1 + r) ** n) ** (periods_per_year / n) - 1 = (1 + r) ** ppy - 1

    which depends on `periods_per_year` but not on n. With r = 0.25 and one
    period per year that is 0.25 for four periods exactly as for one — the
    geometric mean of four identical 25% years.
    """
    four_years = [0.25] * 4
    result = annualized_market_return(_price_data(four_years, four_years, 1))
    assert result == pytest.approx(0.25)


def test_compounding_across_a_half_year_of_periods() -> None:
    """Hand arithmetic where the exponent is neither 1 nor 1/n.

        prod(1 + r) = 1.5 * 0.8 * 1.5 * 0.8 = 1.2 * 1.2 = 1.44
        exponent    = periods_per_year / n  = 2 / 4      = 0.5
        annualized  = 1.44 ** 0.5 - 1 = 1.2 - 1          = 0.20

    The arithmetic mean of the same series is (0.5 - 0.2 + 0.5 - 0.2) / 4
    = 0.15, and 0.15 * 2 = 0.30, so this assertion tells the geometric
    formula apart from an arithmetic one.
    """
    market = [0.5, -0.2, 0.5, -0.2]
    result = annualized_market_return(_price_data(market, market, 2))
    assert result == pytest.approx(0.20)


def test_annualized_market_return_stops_when_there_are_no_market_returns() -> None:
    """Rule 3: a missing input stops the run and names the field.

    This is the one stop that already exists in `analysis/capm.py` (line 43).
    The type and the field named in the message are both asserted; a bare
    `pytest.raises(Exception)` would pass against any raise at all and tell
    the next reader nothing.
    """
    empty = _price_data([], [], 12)

    with pytest.raises(ValueError) as excinfo:
        annualized_market_return(empty)

    message = str(excinfo.value)
    assert "market return" in message.lower(), (
        f"the message must name the missing input: {message!r}"
    )


def test_run_capm_propagates_the_missing_market_returns_stop() -> None:
    """The same stop, reached through `run_capm`, which is where the pipeline
    actually enters. It must survive the composition rather than only being
    reachable by calling `annualized_market_return` directly.
    """
    empty = _price_data([], [], 12)

    with pytest.raises(ValueError) as excinfo:
        run_capm(empty, risk_free_rate=0.03, beta_override=1.0)

    assert "market return" in str(excinfo.value).lower()


def test_arithmetic_fallback_when_compounding_wipes_out() -> None:
    """`analysis/capm.py:45-47` — **a fallback, not the documented formula.**

    A periodic return of -1.0 is a total loss, so the compounded gross return
    is 0 and no geometric annualization exists (0 ** anything is 0 or
    undefined, and the result would be a flat -100% regardless of what
    followed). The function switches to an arithmetic annualization instead.
    `docs/3-architecture/valuation-math.md` section 5 calls this a genuine
    numerical guard for a mathematically impossible input rather than a rule 3
    default, which is why it is asserted here at all — but it is a second
    formula chosen at run time, and the entry for this unit reports it.

        prod(1 + r) = (1 - 1.0) * (1 + 0.2) = 0 * 1.2 = 0, so gross <= 0
        mean(r)     = (-1.0 + 0.2) / 2 = -0.4
        annualized  = -0.4 * 2 (periods per year) = -0.8
    """
    market = [-1.0, 0.2]
    result = annualized_market_return(_price_data(market, market, 2))
    assert result == pytest.approx(-0.8)


# ---------------------------------------------------------------------------
# run_capm — the whole model
# ---------------------------------------------------------------------------


def test_run_capm_end_to_end_with_the_erp_derived_from_history() -> None:
    """Every step by hand, before running anything.

        market returns   0.5, -0.2, 0.5, -0.2 at 2 periods per year
        stock returns    exactly 2x the market return, period by period

        beta             slope of an exact 2x relation              = 2.0
        R^2              perfect fit                                = 1.0
        SE(beta)         no residual                                = 0.0
        market return    1.44 ** (2 / 4) - 1 = 1.2 - 1              = 0.20
        ERP              0.20 - 0.03                                = 0.17
        cost of equity   0.03 + 2.0 * 0.17 = 0.03 + 0.34            = 0.37

    The risk-free rate is 0.03, deliberately NOT `config.DEFAULT_RISK_FREE_RATE`
    (0.04), so that a run which ignored the supplied rate and took the default
    would give an ERP of 0.16 and a cost of equity of 0.36, not 0.37.
    """
    market = [0.5, -0.2, 0.5, -0.2]
    stock = [2 * r for r in market]
    result = run_capm(_price_data(stock, market, 2), risk_free_rate=0.03)

    assert result.beta == pytest.approx(2.0)
    assert result.r_squared == pytest.approx(1.0)
    assert result.std_error == pytest.approx(0.0, abs=1e-12)
    assert result.risk_free_rate == pytest.approx(0.03)
    assert result.equity_risk_premium == pytest.approx(0.17)
    assert result.cost_of_equity == pytest.approx(0.37)


def test_a_supplied_equity_risk_premium_is_used_as_given() -> None:
    """With an ERP supplied, the S&P 500 history is not consulted at all —
    `analysis/capm.py:72-73` takes the supplied value and never calls
    `annualized_market_return`.

    The market series here is **empty**, which is what makes that falsifiable:
    a run that computed the ERP from history would stop with the ValueError
    locked two tests above instead of returning a number.

        cost of equity = Rf + beta * ERP
                       = 0.05 + 1.5 * 0.06
                       = 0.05 + 0.09
                       = 0.14

    The beta override is asserted to pass through. `r_squared` and
    `std_error` are deliberately NOT asserted: `capm.py:84-85` sets both to
    0.0, which is indistinguishable from a regression that explained nothing.
    See this file's module docstring.
    """
    result = run_capm(
        _price_data([], [], 12),
        risk_free_rate=0.05,
        equity_risk_premium=0.06,
        beta_override=1.5,
    )

    assert result.beta == pytest.approx(1.5)
    assert result.risk_free_rate == pytest.approx(0.05)
    assert result.equity_risk_premium == pytest.approx(0.06)
    assert result.cost_of_equity == pytest.approx(0.14)


def test_cost_of_equity_is_linear_in_beta() -> None:
    """Closed-form identity: cost_of_equity = Rf + beta * ERP is affine in
    beta, so with Rf and ERP held fixed, doubling beta must move the cost of
    equity by exactly one ERP.

        beta 1.0 -> 0.05 + 1.0 * 0.06 = 0.11
        beta 2.0 -> 0.05 + 2.0 * 0.06 = 0.17
        difference                    = 0.06 = ERP

    A beta of 0 must give the risk-free rate itself, which is the boundary
    the whole model rests on: an asset with no market exposure earns Rf.
    """
    one = run_capm(
        _price_data([], [], 12),
        risk_free_rate=0.05,
        equity_risk_premium=0.06,
        beta_override=1.0,
    )
    two = run_capm(
        _price_data([], [], 12),
        risk_free_rate=0.05,
        equity_risk_premium=0.06,
        beta_override=2.0,
    )
    zero = run_capm(
        _price_data([], [], 12),
        risk_free_rate=0.05,
        equity_risk_premium=0.06,
        beta_override=0.0,
    )

    assert one.cost_of_equity == pytest.approx(0.11)
    assert two.cost_of_equity == pytest.approx(0.17)
    assert two.cost_of_equity - one.cost_of_equity == pytest.approx(0.06)
    assert zero.cost_of_equity == pytest.approx(0.05)


def test_the_risk_free_rate_defaults_to_the_named_constant() -> None:
    """Rule 6: an assumption carries a name, a default, and is visible in the
    output. When no risk-free rate is supplied, `analysis/capm.py:70` uses
    `config.DEFAULT_RISK_FREE_RATE`, and the value must reach `CAPMResult` so
    a reader can see which rate the valuation ran on.

    The expected side here is `config.py:20`, the recorded default — not a
    literal copied out of a run. The cost of equity is then that same
    documented rate plus 1.0 * 0.06 by the CAPM formula.

    This does not bless a rule 3 fallback: the risk-free rate is never
    extracted from a filing, so there is no missing measurement being papered
    over. What the output still cannot show is *whether* the default was used
    or the same number was supplied; that is reported in this unit's entry.
    """
    result = run_capm(
        _price_data([], [], 12),
        equity_risk_premium=0.06,
        beta_override=1.0,
    )

    assert result.risk_free_rate == pytest.approx(config.DEFAULT_RISK_FREE_RATE)
    assert result.cost_of_equity == pytest.approx(config.DEFAULT_RISK_FREE_RATE + 0.06)
