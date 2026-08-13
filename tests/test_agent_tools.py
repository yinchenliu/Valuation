"""Agent tool-layer tests — no API calls.

Two things are verified here, both offline:

1. **Cross-check.** Driving the valuation through the agent's tools produces
   numbers identical to the deterministic pipeline. If the agent only sequences
   and never computes, the two cannot diverge; any difference means a tool is
   doing arithmetic it should be delegating.

2. **Failure recovery.** A tool that fails returns a structured, recoverable
   error rather than raising, so the model can adjust an input and call again.

Price data is synthesised from a fixed seed (shared with the golden-snapshot
harness) so neither the network nor market movement is involved.

Usage:
    python tests/test_agent_tools.py
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pipeline  # noqa: E402
from agent import tools  # noqa: E402
from models.valuation import ProjectionAssumptions  # noqa: E402
from tests.test_regression_golden import (  # noqa: E402
    BASELINE_RISK_FREE_RATE,
    FALLBACK_SHARES,
    _make_price_data,
)

FIXTURE = BASE_DIR / "cache" / ".cache_abbv_extraction.pkl"

_failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")
        _failures.append(label)


def _load_run() -> pipeline.ValuationRun:
    with open(FIXTURE, "rb") as fh:
        financials, non_recurring = pickle.load(fh)
    run = pipeline.ValuationRun(ticker=financials.ticker or "ABBV")
    run.raw_financials = financials
    run.non_recurring = non_recurring
    return run


def _stub_market_data(run: pipeline.ValuationRun) -> None:
    """Attach deterministic price data and shares, bypassing the network."""
    run.price_data = _make_price_data(run.ticker)
    run.diluted_shares = (
        run.financials.get_income_statement(run.financials.latest_year).diluted_shares_outstanding
        or FALLBACK_SHARES
    )
    run.shares_source = "test fixture"


def test_cross_check() -> None:
    """Agent tool path and deterministic path must agree exactly."""
    print("\n=== Cross-check: agent tools vs deterministic pipeline ===")

    # --- Deterministic path ---
    det = _load_run()
    _stub_market_data(det)
    pipeline.step_normalize(det)
    pipeline.step_derive_assumptions(det, ProjectionAssumptions())
    pipeline.step_capm(det, risk_free_rate=BASELINE_RISK_FREE_RATE)
    pipeline.step_wacc(det)
    pipeline.step_project(det)
    pipeline.step_dcf(det)

    # --- Agent tool path, in a deliberately different order where order is free ---
    agt = _load_run()
    _stub_market_data(agt)
    tools.bind_run(agt)

    summary = tools.TOOL_IMPLS["get_extraction_summary"]()
    check("get_extraction_summary returns years", bool(summary.get("years")))

    validation = tools.TOOL_IMPLS["validate_arithmetic"]()
    check("validate_arithmetic returns a verdict", "passed" in validation)

    hist = tools.TOOL_IMPLS["get_historical_fcff"]()
    check("get_historical_fcff returns years", bool(hist.get("years")))

    tools.TOOL_IMPLS["normalize_financials"]()
    tools.TOOL_IMPLS["derive_assumptions"](
        projection_years=None, terminal_growth_rate=None, revenue_growth_rates=None,
        operating_margin=None, tax_rate=None, da_pct_revenue=None,
        capex_pct_revenue=None, nwc_pct_revenue=None,
    )
    tools.TOOL_IMPLS["run_capm"](
        risk_free_rate=BASELINE_RISK_FREE_RATE, equity_risk_premium=None, beta_override=None,
    )
    tools.TOOL_IMPLS["calculate_wacc"](cost_of_debt_override=None, tax_rate_override=None)
    tools.TOOL_IMPLS["project_fcffs"]()
    dcf_out = tools.TOOL_IMPLS["run_dcf"]()

    check("run_dcf produced a price", "implied_share_price" in dcf_out, str(dcf_out)[:200])

    # --- The comparison that matters ---
    check(
        "beta identical",
        abs(det.capm.beta - agt.capm.beta) < 1e-12,
        f"{det.capm.beta} vs {agt.capm.beta}",
    )
    check(
        "WACC identical",
        abs(det.wacc.wacc - agt.wacc.wacc) < 1e-12,
        f"{det.wacc.wacc} vs {agt.wacc.wacc}",
    )
    check(
        "enterprise value identical",
        abs(det.dcf.enterprise_value - agt.dcf.enterprise_value) < 1e-9,
        f"{det.dcf.enterprise_value} vs {agt.dcf.enterprise_value}",
    )
    check(
        "implied share price identical",
        abs(det.dcf.implied_share_price - agt.dcf.implied_share_price) < 1e-9,
        f"{det.dcf.implied_share_price} vs {agt.dcf.implied_share_price}",
    )
    check(
        "projected FCFFs identical",
        [round(p.fcff, 9) for p in det.projected] == [round(p.fcff, 9) for p in agt.projected],
    )
    print(f"\n  Both paths: implied ${det.dcf.implied_share_price:,.2f}, "
          f"WACC {det.wacc.wacc:.4%}, beta {det.capm.beta:.4f}")


def test_error_is_recoverable() -> None:
    """A failing tool returns a structured error instead of raising."""
    print("\n=== Failure recovery ===")

    run = _load_run()
    tools.bind_run(run)

    # WACC before CAPM — a prerequisite violation.
    out = tools.TOOL_IMPLS["calculate_wacc"](cost_of_debt_override=None, tax_rate_override=None)
    check("missing prerequisite -> error dict", "error" in out, str(out)[:160])
    check("error names the producing step", "run_capm" in out.get("error", ""), out.get("error", ""))
    check("error marked recoverable", out.get("recoverable") is True)

    # Terminal growth above the WACC — the classic recoverable DCF failure.
    run2 = _load_run()
    _stub_market_data(run2)
    tools.bind_run(run2)
    pipeline.step_normalize(run2)
    tools.TOOL_IMPLS["derive_assumptions"](
        projection_years=5, terminal_growth_rate=0.99, revenue_growth_rates=None,
        operating_margin=None, tax_rate=None, da_pct_revenue=None,
        capex_pct_revenue=None, nwc_pct_revenue=None,
    )
    tools.TOOL_IMPLS["run_capm"](
        risk_free_rate=BASELINE_RISK_FREE_RATE, equity_risk_premium=None, beta_override=None,
    )
    tools.TOOL_IMPLS["calculate_wacc"](cost_of_debt_override=None, tax_rate_override=None)
    tools.TOOL_IMPLS["project_fcffs"]()
    bad = tools.TOOL_IMPLS["run_dcf"]()
    check("wacc <= g -> error dict", "error" in bad, str(bad)[:160])
    check(
        "error tells the model how to recover",
        "terminal growth" in bad.get("error", "").lower(),
        bad.get("error", ""),
    )

    # And the model can in fact recover by lowering terminal growth.
    tools.TOOL_IMPLS["derive_assumptions"](
        projection_years=5, terminal_growth_rate=0.02, revenue_growth_rates=None,
        operating_margin=None, tax_rate=None, da_pct_revenue=None,
        capex_pct_revenue=None, nwc_pct_revenue=None,
    )
    tools.TOOL_IMPLS["project_fcffs"]()
    good = tools.TOOL_IMPLS["run_dcf"]()
    check("retry after lowering g succeeds", "implied_share_price" in good, str(good)[:160])


def test_transcript_records_calls() -> None:
    """Every tool call lands on the run's transcript."""
    print("\n=== Transcript ===")
    run = _load_run()
    _stub_market_data(run)
    tools.bind_run(run)
    tools.TOOL_IMPLS["get_extraction_summary"]()
    tools.TOOL_IMPLS["normalize_financials"]()

    tool_entries = [e for e in run.transcript if e.get("kind") == "tool_call"]
    check("tool calls recorded", len(tool_entries) >= 2, f"{len(tool_entries)} entries")
    check("entries carry inputs and output", all("output" in e for e in tool_entries))

    from agent.transcript import transcript_json
    check("transcript serialises to JSON", len(transcript_json(run)) > 50)


def main() -> int:
    if not FIXTURE.exists():
        print(f"Fixture not found: {FIXTURE}")
        return 1

    test_cross_check()
    test_error_is_recoverable()
    test_transcript_records_calls()

    print()
    if _failures:
        print(f"FAIL — {len(_failures)} check(s) failed:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("PASS — all agent tool-layer checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
