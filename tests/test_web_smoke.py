"""Web layer smoke test — templates render, routes wire up, no network.

Exercises the FastAPI app in-process with TestClient. A cached extraction is
preloaded into the run store so no LLM call happens, and price data is stubbed so
no market call happens.

Usage:
    python tests/test_web_smoke.py
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pipeline  # noqa: E402
from tests.test_regression_golden import FALLBACK_SHARES, _make_price_data  # noqa: E402

FIXTURE = BASE_DIR / "cache" / ".cache_abbv_extraction.pkl"
_failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")
        _failures.append(label)


def _seed_run() -> pipeline.ValuationRun:
    """Put a fully-extracted run in the store, with price data stubbed."""
    with open(FIXTURE, "rb") as fh:
        financials, non_recurring = pickle.load(fh)
    run = pipeline.ValuationRun(ticker=financials.ticker or "ABBV", company_name="AbbVie Inc.")
    run.raw_financials = financials
    run.non_recurring = non_recurring
    pipeline.step_normalize(run)
    pipeline.STORE.put(run)
    return run


def main() -> int:
    if not FIXTURE.exists():
        print(f"Fixture not found: {FIXTURE}")
        return 1

    from fastapi.testclient import TestClient
    import app as app_module

    # Stub the market fetch so the smoke test stays offline and deterministic.
    def _stub_fetch(run, lookback_years=5, frequency="monthly"):
        run.price_data = _make_price_data(run.ticker)
        latest = run.financials.get_income_statement(run.financials.latest_year)
        run.diluted_shares = latest.diluted_shares_outstanding or FALLBACK_SHARES
        run.shares_source = "test stub"
        run.log("fetch_market_data", "stubbed")
        return run.price_data

    pipeline.step_fetch_market_data = _stub_fetch

    client = TestClient(app_module.app)
    run = _seed_run()

    print("\n=== Routes ===")
    r = client.get("/")
    check("GET / renders upload page", r.status_code == 200 and "Upload" in r.text, str(r.status_code))

    r = client.get("/assumptions", params={"ticker": "ABBV", "run_id": run.run_id})
    check("GET /assumptions renders", r.status_code == 200, str(r.status_code))
    check("assumptions form carries run_id", run.run_id in r.text)
    check("risk-free field defaults to auto-fetch", 'placeholder="auto (live 10Y Treasury)"' in r.text)
    check("agentic button present", "/valuation/agentic" in r.text)
    check("orchestrating-model picker offers both providers",
          'name="agent_provider"' in r.text
          and 'value="claude"' in r.text and 'value="gemini"' in r.text)

    print("\n=== Deterministic valuation ===")
    r = client.post("/valuation", data={
        "ticker": "ABBV",
        "company_name": "AbbVie Inc.",
        "run_id": run.run_id,
        "files": "",
        "projection_years": 5,
        "terminal_growth_rate": 2.5,
        "revenue_growth": "",
        "risk_free_rate": "4.0",
        "beta_lookback_years": 5,
        "return_frequency": "monthly",
    })
    check("POST /valuation returns 200", r.status_code == 200, str(r.status_code))
    check("result page shows implied price", "Implied Share Price" in r.text)
    check("no unhandled error banner", "<strong>Error:</strong>" not in r.text,
          r.text.split("<strong>Error:</strong>")[-1][:200] if "<strong>Error:</strong>" in r.text else "")
    check("provenance rendered", "provenance" in r.text)
    check("NRI bridge rendered", "Non-Recurring Adjustments" in r.text)

    print("\n=== Run store is non-destructive ===")
    still_there = pipeline.STORE.get(run.run_id)
    check("run survives a read", still_there is not None)
    r2 = client.post("/valuation", data={
        "ticker": "ABBV", "run_id": run.run_id, "files": "",
        "projection_years": 5, "terminal_growth_rate": 2.5,
        "risk_free_rate": "4.0", "beta_lookback_years": 5, "return_frequency": "monthly",
    })
    check("resubmitting the form works without re-extraction",
          r2.status_code == 200 and "Implied Share Price" in r2.text)

    print("\n=== Explicit zero is honoured ===")
    r3 = client.post("/valuation", data={
        "ticker": "ABBV", "run_id": run.run_id, "files": "",
        "projection_years": 5, "terminal_growth_rate": 2.5,
        "nwc_pct": "0",  # legitimate assumption, must not fall back to history
        "risk_free_rate": "4.0", "beta_lookback_years": 5, "return_frequency": "monthly",
    })
    check("nwc_pct=0 accepted", r3.status_code == 200)
    stored = pipeline.STORE.get(run.run_id)
    check("nwc_pct=0 recorded as an override",
          stored.assumptions is not None and stored.assumptions.nwc_pct_revenue == 0.0
          and "nwc_pct_revenue" in stored.assumptions.overridden,
          f"nwc={stored.assumptions.nwc_pct_revenue if stored.assumptions else None}, "
          f"overridden={stored.assumptions.overridden if stored.assumptions else None}")

    print("\n=== Agentic route (no API key -> graceful error) ===")
    import os

    # Both keys are cleared and the provider is pinned per request: without that
    # this depends on which credentials the developer happens to have, and a real
    # key would take the suite off-machine.
    saved = {k: os.environ.pop(k, None) for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY")}
    try:
        r4 = client.post("/valuation/agentic", data={
            "ticker": "ABBV", "run_id": run.run_id, "files": "",
            "effort": "high", "max_iterations": 5, "agent_provider": "claude",
        })
        check("agentic route returns 200", r4.status_code == 200, str(r4.status_code))
        check("missing key reported clearly", "ANTHROPIC_API_KEY" in r4.text)
        check("audit trail section rendered", "Audit Trail" in r4.text)

        r5 = client.post("/valuation/agentic", data={
            "ticker": "ABBV", "run_id": run.run_id, "files": "",
            "effort": "high", "max_iterations": 5, "agent_provider": "gemini",
        })
        check("gemini provider routed, not rejected", r5.status_code == 200, str(r5.status_code))
        check("missing gemini key reported clearly", "GEMINI_API_KEY" in r5.text)
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value

    print()
    if _failures:
        print(f"FAIL — {len(_failures)} check(s) failed:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("PASS — web smoke test clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
