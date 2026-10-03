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
import re

import numpy as np
import pandas as pd
import pytest

import config
from analysis.capm import (
    MINIMUM_REGRESSION_OBSERVATIONS,
    annualized_market_return,
    calculate_beta,
    describe_beta_reliability,
    run_capm,
)
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


# ---------------------------------------------------------------------------
# The three stops in `calculate_beta` — `analysis/capm.py:64-93`.
#
# `stats.linregress` raises nothing for an empty or a degenerate series: it
# returns `nan` for every statistic. A `nan` beta cannot be caught downstream
# by a comparison, because `nan <= x` and `nan > x` are both False, so the
# function that produced it is where the run has to stop.
#
# Each expected value below is rule 3's requirement — stop, and name the input
# that was inadequate — not a message recorded from a run. The tests assert the
# exception type and the field the message names, never its wording.
# ---------------------------------------------------------------------------


def test_beta_stops_when_the_two_return_series_are_not_the_same_length() -> None:
    """Beta regresses one series on the other period by period, so an
    observation in `stock_returns` has no partner if the two are not aligned.
    Three market periods against four stock periods is not a shorter history,
    it is a broken pairing, and no beta is defined for it.

    Both lengths must appear so a reader can see which series is short.
    """
    with pytest.raises(ValueError) as excinfo:
        calculate_beta(
            PriceData(
                ticker="TEST",
                stock_returns=np.asarray([0.01, 0.02, 0.03, 0.04], dtype=float),
                market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
                dates=pd.DatetimeIndex(pd.date_range("2020-01-31", periods=3)),
                current_price=100.0,
                periods_per_year=12,
            )
        )

    message = str(excinfo.value)
    assert "market_returns" in message
    assert "stock_returns" in message
    assert "3" in message and "4" in message


def test_beta_stops_below_the_minimum_number_of_observations() -> None:
    """SE(beta) = sqrt( SSE / ((n - 2) * Sxx) ), so n - 2 must be at least 1 and
    n must therefore be at least 3. At n = 2 the slope of a perfect fit is a
    finite 1.0 while the standard error is nan, which is the worst of the three
    cases: a plausible beta carrying a diagnostic that does not exist.

    Two observations is one below `MINIMUM_REGRESSION_OBSERVATIONS`, which is
    derived in `analysis/capm.py` from the formula above rather than chosen.
    """
    with pytest.raises(ValueError) as excinfo:
        calculate_beta(_price_data([0.01, 0.02], [0.01, 0.02], 12))

    message = str(excinfo.value)
    assert "2" in message, "the message must name how many observations arrived"
    assert str(MINIMUM_REGRESSION_OBSERVATIONS) in message
    assert "observations" in message.lower()


# scipy warns about catastrophic cancellation on a constant regressor, which is
# exactly the degeneracy under test. Filtered so it does not read as an
# unexplained warning in the suite's output; the assertion is unchanged.
@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_beta_stops_when_the_market_series_has_no_variation() -> None:
    """OLS estimates beta as Cov(stock, market) / Var(market). A market series
    that returns the same figure every period has Var(market) = 0, so the slope
    is a division by zero and no beta exists — the market explains nothing,
    whatever the stock did.

    Var([0.01, 0.01, 0.01, 0.01]) = 0 by inspection: every observation equals
    the mean. The stock series is deliberately *not* constant, so the only
    degeneracy is on the regressor.
    """
    with pytest.raises(ValueError) as excinfo:
        calculate_beta(
            _price_data([0.01, 0.02, 0.03, 0.04], [0.01, 0.01, 0.01, 0.01], 12)
        )

    message = str(excinfo.value)
    assert "market_returns" in message
    assert "variance" in message.lower()


def test_beta_stops_when_a_return_observation_is_nan() -> None:
    """A NaN anywhere in either series makes every regression statistic NaN.
    This is the shape a gap in the price history takes by the time it reaches
    the regression, and it must not be returned as a beta.
    """
    with pytest.raises(ValueError) as excinfo:
        calculate_beta(
            _price_data([0.01, float("nan"), 0.03, 0.04], [0.01, 0.02, 0.03, 0.04], 12)
        )

    assert "beta" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# P10b-capm-variance (backlog item 45): the constant-market stop runs BEFORE
# SciPy, so the repository's message is the one the reader sees, and it names
# the repeated value and the number of observations.
# ---------------------------------------------------------------------------


class _LinregressMustNotRun:
    """Stands in for `scipy.stats` so a test can prove the stop came first."""

    @staticmethod
    def linregress(*args: object, **kwargs: object) -> None:
        raise AssertionError("stats.linregress was reached; the pre-check must stop first")


def test_constant_market_stop_names_the_repeated_value_and_the_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seven observations, every market return 0.03. The stock series varies, so
    the only degeneracy is on the regressor. Var([0.03] * 7) = 0 by inspection.

    Expected, from P10b's assignment step 1 (names `market_returns`, says its
    variance is zero, gives the observation count) and P10-tests step 5 (the
    repeated value): "market_returns", "variance", 0.03 and 7. SciPy is replaced
    by a stand-in that fails if called, so the message cannot be SciPy's.
    """
    from analysis import capm

    monkeypatch.setattr(capm, "stats", _LinregressMustNotRun)
    with pytest.raises(ValueError) as excinfo:
        calculate_beta(
            _price_data([0.01, 0.05, -0.02, 0.04, 0.00, 0.03, -0.01], [0.03] * 7, 12)
        )

    message = str(excinfo.value)
    assert "market_returns" in message
    assert "variance" in message.lower()
    assert "0.03" in message, "the repeated value must be named"
    assert re.search(r"\b7 observations\b", message), "the count must be named"


def test_constant_market_stop_fires_on_values_whose_float_variance_is_not_zero() -> None:
    """Identity, not `np.var(...) == 0.0` (P10b step 1). Twelve copies of 0.1:
    the float mean of twelve 0.1s is not exactly 0.1, so the float variance is a
    tiny non-zero number, yet the series is constant and must stop as one.
    The premise is checked first, so the test cannot pass vacuously.
    """
    assert np.var(np.array([0.1] * 12)) != 0.0  # the premise: float variance > 0
    with pytest.raises(ValueError) as excinfo:
        calculate_beta(_price_data([0.01 * k for k in range(12)], [0.1] * 12, 12))
    message = str(excinfo.value)
    assert "market_returns" in message
    assert re.search(r"\b12 observations\b", message)


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.parametrize(
    ("stock", "market"),
    [
        # one NaN in a market series that is otherwise constant at 0.01: NaN
        # compares unequal to 0.01, so the identity pre-check must NOT claim it
        ([0.01, 0.02, 0.03, 0.04, 0.05], [0.01, 0.01, 0.01, 0.01, float("nan")]),
        # one NaN in an otherwise varied market series
        ([0.01, 0.02, 0.03, 0.04, 0.05], [0.02, float("nan"), 0.01, 0.03, 0.05]),
        # one NaN in the stock series, the market varied
        ([0.01, float("nan"), 0.03, 0.04, 0.05], [0.02, 0.04, 0.01, 0.03, 0.05]),
    ],
    ids=["nan-in-constant-market", "nan-in-varied-market", "nan-in-stock"],
)
def test_a_nan_observation_still_reaches_the_nan_stop(
    stock: list[float], market: list[float]
) -> None:
    """P10b step 2: the NaN check after the regression is kept, and a NaN
    observation reaches it. It stops with a ValueError; it is not reported as a
    constant market (the pre-check's "same value" wording), and no beta returns.

    The NaN stop's wording is backlog item 55 (it still blames market variance),
    so only what survives that fix is asserted: the type, that "nan" appears (the
    message reports the NaN statistics), and that it is not the constant stop.
    """
    with pytest.raises(ValueError) as excinfo:
        calculate_beta(_price_data(stock, market, 12))
    message = str(excinfo.value)
    assert "nan" in message.lower()
    assert "same value" not in message


# ---------------------------------------------------------------------------
# `describe_beta_reliability` — `analysis/capm.py:130-145`. A rule 6 label, not
# a stop, and the branch that warns was reached by no test in this file.
#
# Neither test below asserts the label's wording: a reformat must not turn them
# red. What is asserted is that the two branches are told apart, and that each
# is selected by the side of `config.MINIMUM_BETA_R_SQUARED` its input falls
# on — which is the whole of what the function promises.
# ---------------------------------------------------------------------------


def test_a_beta_below_the_r_squared_minimum_is_labelled_unreliable() -> None:
    """`config.MINIMUM_BETA_R_SQUARED` is the threshold, so an R-squared of
    half it is on the warning side of the comparison by construction — the
    expectation follows from the constant, not from a recorded run.

    An R-squared of 0.10 means the market explains a tenth of this stock's
    return variation, so the beta regressed from it is a number with a wide
    confidence interval and the reader has to be told.
    """
    weak = describe_beta_reliability(
        r_squared=config.MINIMUM_BETA_R_SQUARED / 2,
        std_error=0.4,
        beta=1.0,
        observations=58,
    )

    assert "config.MINIMUM_BETA_R_SQUARED" in weak
    assert "not reliable" in weak.lower()


def test_the_two_reliability_labels_are_not_the_same_sentence() -> None:
    """The label exists to distinguish a beta worth presenting from one that is
    not, so the two sides of the threshold must not read alike. The strong case
    is the threshold itself — `>=` is inclusive, so exactly the minimum is on
    the acceptable side, and that is the boundary most likely to be inverted.
    """
    at_the_threshold = describe_beta_reliability(
        r_squared=config.MINIMUM_BETA_R_SQUARED,
        std_error=0.1,
        beta=1.0,
        observations=58,
    )
    below_the_threshold = describe_beta_reliability(
        r_squared=config.MINIMUM_BETA_R_SQUARED / 2,
        std_error=0.4,
        beta=1.0,
        observations=58,
    )

    assert at_the_threshold != below_the_threshold
    assert "not reliable" not in at_the_threshold.lower()
