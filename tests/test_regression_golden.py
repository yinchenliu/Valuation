"""Golden-path regression harness.

Runs the full deterministic valuation pipeline against the committed extraction
pickles and compares every output against a stored JSON snapshot.

The point is to make refactors provably behaviour-preserving. To do that the run
has to be *fully offline and deterministic*, so price data is synthesised from a
fixed seed rather than fetched — otherwise the "before" and "after" numbers would
differ simply because the market moved between the two runs.

Usage:
    python tests/test_regression_golden.py            # compare against snapshot
    python tests/test_regression_golden.py --update   # (re)write the snapshot
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from analysis.capm import run_capm  # noqa: E402
from analysis.dcf import run_dcf  # noqa: E402
from analysis.fcff import calculate_fcff_historical  # noqa: E402
from analysis.normalizer import normalize_financials  # noqa: E402
from analysis.projector import derive_assumptions, project_fcffs  # noqa: E402
from analysis.wacc import calculate_wacc  # noqa: E402

SNAPSHOT_PATH = Path(__file__).parent / "golden_snapshot.json"

# Extraction fixtures: (label, pickle path). These are committed to the repo and
# hold (FinancialStatements, list[NonRecurringItem]) tuples.
FIXTURES = [
    ("ABBV", BASE_DIR / "cache" / ".cache_abbv_extraction.pkl"),
    ("LHX", BASE_DIR / "cache" / ".cache_lhx_extraction.pkl"),
    ("LLY", BASE_DIR / "tests" / ".cache_lly_extraction.pkl"),
    ("ABBV_flashlite", BASE_DIR / "tests" / ".cache_abbv_extraction.pkl"),
    ("ABBV_pro", BASE_DIR / "tests" / ".cache_abbv_extraction_pro.pkl"),
]

# Synthetic market inputs — fixed so the pipeline is reproducible offline.
SEED = 20240611
N_PERIODS = 60  # 5 years monthly
TRUE_BETA = 1.15
CURRENT_PRICE = 150.0
FALLBACK_SHARES = 1_800.0  # millions, used when the filing reports no diluted shares
ROUND_DP = 6

# The market series is rescaled to hit this annualised geometric return exactly.
# Pinning it matters: with unconstrained normal draws, volatility drag can push the
# realised return negative, which makes the derived ERP negative and the WACC
# negative, and run_dcf then raises. That is a real property of the current
# realised-return ERP, but it is not what this harness is here to measure.
TARGET_MARKET_RETURN = 0.09

# Risk-free rate pinned for reproducibility (see run_one).
BASELINE_RISK_FREE_RATE = 0.04


@dataclass
class _SyntheticPriceData:
    """Stand-in for ingestion.price_fetcher.PriceData.

    Structurally compatible: run_capm only reads stock_returns, market_returns,
    and periods_per_year.
    """

    ticker: str
    stock_returns: np.ndarray
    market_returns: np.ndarray
    dates: object
    current_price: float
    periods_per_year: int = 12


def _make_price_data(ticker: str) -> _SyntheticPriceData:
    rng = np.random.default_rng(SEED)

    # Draw a zero-drift market series, then rescale every gross return by a constant
    # so the compounded annual return lands exactly on TARGET_MARKET_RETURN. Scaling
    # gross returns preserves the shape (and therefore the regression beta) while
    # fixing the level.
    raw = rng.normal(0.0, 0.042, N_PERIODS)
    gross = 1.0 + raw
    realised_period_gross = float(np.prod(gross)) ** (1.0 / N_PERIODS)
    target_period_gross = (1.0 + TARGET_MARKET_RETURN) ** (1.0 / 12.0)
    market = gross * (target_period_gross / realised_period_gross) - 1.0

    idiosyncratic = rng.normal(0.0, 0.020, N_PERIODS)
    stock = TRUE_BETA * market + idiosyncratic
    return _SyntheticPriceData(
        ticker=ticker,
        stock_returns=stock,
        market_returns=market,
        dates=None,
        current_price=CURRENT_PRICE,
        periods_per_year=12,
    )


def _r(value) -> float:
    """Round a float so trivial FP drift doesn't fail the comparison."""
    return round(float(value), ROUND_DP)


def run_one(label: str, pickle_path: Path) -> dict:
    """Run the full deterministic pipeline for one fixture."""
    with open(pickle_path, "rb") as fh:
        financials, non_recurring = pickle.load(fh)

    adjusted = normalize_financials(financials, non_recurring)
    assumptions = derive_assumptions(adjusted)

    price_data = _make_price_data(adjusted.ticker or label)
    # Pin the risk-free rate: run_capm now fetches ^TNX live when it is None, and a
    # moving market input would make this harness non-reproducible. The ERP is left
    # to its default so the snapshot does exercise the configured value.
    capm_result = run_capm(price_data, risk_free_rate=BASELINE_RISK_FREE_RATE)

    latest_year = adjusted.latest_year
    latest_is = adjusted.get_income_statement(latest_year)
    latest_bs = adjusted.get_balance_sheet(latest_year)

    shares = latest_is.diluted_shares_outstanding or FALLBACK_SHARES
    market_cap = price_data.current_price * shares

    wacc_result = calculate_wacc(
        capm_result=capm_result,
        income_statement=latest_is,
        balance_sheet=latest_bs,
        market_cap=market_cap,
        tax_rate_override=assumptions["tax_rate"],
    )

    projected = project_fcffs(adjusted, assumptions)
    dcf = run_dcf(
        projected_fcffs=projected,
        wacc_result=wacc_result,
        financials=adjusted,
        terminal_growth_rate=assumptions["terminal_growth_rate"],
        current_price=price_data.current_price,
        diluted_shares=shares,
    )

    historical_fcff = []
    for year in adjusted.years:
        inc = adjusted.get_income_statement(year)
        cfs = adjusted.get_cash_flow(year)
        if inc and cfs:
            h = calculate_fcff_historical(inc, cfs)
            historical_fcff.append({"year": h.year, "fcff": _r(h.fcff)})

    return {
        "ticker": adjusted.ticker,
        "years": list(adjusted.years),
        "non_recurring_count": len(non_recurring),
        "adjusted_income": {
            str(y): {
                "revenue": _r(adjusted.get_income_statement(y).revenue),
                "ebit": _r(adjusted.get_income_statement(y).ebit),
                "net_income": _r(adjusted.get_income_statement(y).net_income),
                "effective_tax_rate": _r(adjusted.get_income_statement(y).effective_tax_rate),
            }
            for y in adjusted.years
        },
        "assumptions": {
            k: ([_r(x) for x in v] if isinstance(v, list) else _r(v) if isinstance(v, (int, float)) else v)
            for k, v in assumptions.items()
        },
        "capm": {
            "beta": _r(capm_result.beta),
            "risk_free_rate": _r(capm_result.risk_free_rate),
            "equity_risk_premium": _r(capm_result.equity_risk_premium),
            "cost_of_equity": _r(capm_result.cost_of_equity),
            "r_squared": _r(capm_result.r_squared),
            # Source strings are deterministic here (rf is pinned, ERP is the
            # configured constant); as-of dates are omitted because the override
            # path stamps today's date and would churn the snapshot daily.
            "erp_source": capm_result.erp_source,
            "erp_is_fallback": capm_result.erp_is_fallback,
        },
        "wacc": {
            "wacc": _r(wacc_result.wacc),
            "cost_of_equity": _r(wacc_result.cost_of_equity),
            "cost_of_debt": _r(wacc_result.cost_of_debt),
            "tax_rate": _r(wacc_result.tax_rate),
            "equity_weight": _r(wacc_result.equity_weight),
            "debt_weight": _r(wacc_result.debt_weight),
        },
        "projected_fcffs": [
            {
                "year": p.year,
                "revenue": _r(p.revenue),
                "ebit": _r(p.ebit),
                "nopat": _r(p.nopat),
                "fcff": _r(p.fcff),
            }
            for p in projected
        ],
        "historical_fcff": historical_fcff,
        "dcf": {
            "pv_fcffs": _r(dcf.pv_fcffs),
            "terminal_value": _r(dcf.terminal_value),
            "pv_terminal_value": _r(dcf.pv_terminal_value),
            "enterprise_value": _r(dcf.enterprise_value),
            "net_debt": _r(dcf.net_debt),
            "equity_value": _r(dcf.equity_value),
            "diluted_shares": _r(dcf.diluted_shares),
            "implied_share_price": _r(dcf.implied_share_price),
            "upside_downside": _r(dcf.upside_downside),
        },
    }


def build_snapshot() -> dict:
    results: dict[str, object] = {}
    for label, path in FIXTURES:
        if not path.exists():
            print(f"  [SKIP] {label}: {path} not found")
            continue
        try:
            results[label] = run_one(label, path)
            print(f"  [OK]   {label}")
        except Exception as exc:  # noqa: BLE001 — record, don't abort the sweep
            results[label] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"  [FAIL] {label}: {type(exc).__name__}: {exc}")
    return results


def _diff(path: str, expected, actual, out: list[str]) -> None:
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                out.append(f"{path}.{key}: ADDED = {actual[key]!r}")
            elif key not in actual:
                out.append(f"{path}.{key}: REMOVED (was {expected[key]!r})")
            else:
                _diff(f"{path}.{key}", expected[key], actual[key], out)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            out.append(f"{path}: length {len(expected)} -> {len(actual)}")
        for i, (e, a) in enumerate(zip(expected, actual)):
            _diff(f"{path}[{i}]", e, a, out)
    elif expected != actual:
        out.append(f"{path}: {expected!r} -> {actual!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="write the snapshot instead of comparing")
    args = parser.parse_args()

    print("Running deterministic pipeline over extraction fixtures...")
    current = build_snapshot()

    if args.update or not SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
        action = "Updated" if args.update else "Created"
        print(f"\n{action} snapshot: {SNAPSHOT_PATH}")
        return 0

    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    diffs: list[str] = []
    _diff("", expected, current, diffs)

    if not diffs:
        print(f"\nPASS — {len(current)} fixture(s) match the golden snapshot.")
        return 0

    print(f"\nFAIL — {len(diffs)} difference(s) vs the golden snapshot:\n")
    for line in diffs:
        print(f"  {line}")
    print("\nIf these changes are intended, re-run with --update.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
