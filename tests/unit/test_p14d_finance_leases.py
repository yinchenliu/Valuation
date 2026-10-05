"""Tests for P14d finance lease obligations debt categorization and cache marker.

Locks behaviors introduced in P14d-finance-leases on the user's decision "83a" (2026-10-04):
1. Balance sheet schema descriptions (_FINANCIALS_BALANCE_SHEET_SCHEMA):
   - short_term_debt includes finance lease obligations due within one year and excludes operating lease obligations.
   - long_term_debt includes long-term finance lease obligations and excludes operating lease obligations.
   - other_current_liabilities includes operating lease obligations due within one year.
   - other_non_current_liabilities includes operating lease liabilities.
2. System prompt rules (_FINANCIALS_SYSTEM_PROMPT):
   - Explicit rule stating finance lease obligations are debt (current in short_term_debt,
     long-term in long_term_debt) and operating lease obligations are not debt (in catch-all fields).
3. CLI cache format marker (CACHE_FORMAT):
   - CACHE_FORMAT is "p14d-finance-leases-v1".
   - _load_cache refuses prior format markers (e.g. p14b-pass2-units-v1, p14a-units-in-millions-v1,
     p11a-printed-lines-v1) and names the expected marker "p14d-finance-leases-v1".
4. Route B prompt generation (session_extraction prompt):
   - session_extraction pass1_prompts and cmd_prompt output contains the finance lease debt rules.
5. Route B Walmart extraction check and debt line breakdown:
   - session_extraction check on extractions/WMT.json exits 0.
   - Hand arithmetic verification of Walmart debt breakdown (PDF page 22):
     short_term_debt: 6,596 + 3,542 + 856 = 10,994M
     long_term_debt: 34,624 + 5,905 = 40,529M
     total_debt: 10,994 + 40,529 = 51,523M
     net_debt: 51,523 - 10,727 (cash) = 40,796M
     Operating lease obligations (1,631M current, 11,041M non-current) are in other liabilities, not debt.
   - Route B Walmart valuation exits 0 with implied share price $28.02.

Where expected values come from:
- User decision "83a" (2026-10-04, backlog item 83).
- Hand arithmetic on filing figures cited from Walmart Inc._10-K_2026-01-31_English.pdf page 22:
  * Short-term borrowings: 6,596 (page 22)
  * Long-term debt due within one year: 3,542 (page 22)
  * Finance lease obligations due within one year: 856 (page 22)
  * Sum short_term_debt = 6,596 + 3,542 + 856 = 10,994.
  * Long-term debt: 34,624 (page 22)
  * Long-term finance lease obligations: 5,905 (page 22)
  * Sum long_term_debt = 34,624 + 5,905 = 40,529.
  * Sum total_debt = 10,994 + 40,529 = 51,523.
  * Cash and cash equivalents: 10,727 (page 22).
  * Net debt = 51,523 - 10,727 = 40,796.
  * Operating lease obligations due within one year: 1,631 (page 22, inside other_current_liabilities).
  * Long-term operating lease obligations: 13,941 (page 22, inside other_non_current_liabilities).
- Closed-form identity of CLI cache format marker check.
No paid API calls or real network socket connections are made.
"""

from __future__ import annotations

import io
import json
import pickle
import socket
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

import cli
from ingestion.claude_extractor import (
    _FINANCIALS_BALANCE_SHEET_SCHEMA,
    _FINANCIALS_SYSTEM_PROMPT,
    FilingPlan,
    pass1_prompts,
)
from ingestion.price_fetcher import PriceData
from ingestion.session_extraction import (
    cmd_check,
    cmd_prompt,
    load_session_extraction,
)
from models.financial_statements import FinancialStatements, NonRecurringItem
from models.valuation import CAPMResult

REPO_ROOT = Path(__file__).resolve().parents[2]
WMT_SESSION_PATH = REPO_ROOT / "extractions" / "WMT.json"


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no test makes network calls."""
    def _refused(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a unit test attempted a network connection: {args!r}")

    monkeypatch.setattr(socket.socket, "connect", _refused)
    monkeypatch.setattr(socket.socket, "connect_ex", _refused)
    monkeypatch.setattr(socket, "create_connection", _refused)


# ===========================================================================
# 1. Schema descriptions in _FINANCIALS_BALANCE_SHEET_SCHEMA
# ===========================================================================


def test_schema_short_term_debt_includes_finance_leases_excludes_operating() -> None:
    """short_term_debt schema description includes finance lease obligations due within 1 yr
    and explicitly excludes operating lease obligations.
    """
    desc = _FINANCIALS_BALANCE_SHEET_SCHEMA["short_term_debt"]
    assert "finance lease obligations due within one year" in desc
    assert "Not operating lease obligations." in desc


def test_schema_long_term_debt_includes_finance_leases_excludes_operating() -> None:
    """long_term_debt schema description includes long-term finance lease obligations
    and explicitly excludes operating lease obligations.
    """
    desc = _FINANCIALS_BALANCE_SHEET_SCHEMA["long_term_debt"]
    assert "long-term finance lease obligations" in desc
    assert "Not operating lease obligations." in desc


def test_schema_other_current_liabilities_includes_operating_lease_obligations() -> None:
    """other_current_liabilities schema description includes operating lease obligations due within 1 yr."""
    desc = _FINANCIALS_BALANCE_SHEET_SCHEMA["other_current_liabilities"]
    assert "operating lease obligations due within one year" in desc


def test_schema_other_non_current_liabilities_includes_operating_lease_liabilities() -> None:
    """other_non_current_liabilities schema description includes operating lease liabilities."""
    desc = _FINANCIALS_BALANCE_SHEET_SCHEMA["other_non_current_liabilities"]
    assert "operating lease liabilities" in desc


# ===========================================================================
# 2. System prompt rules in _FINANCIALS_SYSTEM_PROMPT
# ===========================================================================


def test_system_prompt_balance_sheet_rules_state_finance_lease_debt_distinction() -> None:
    """_FINANCIALS_SYSTEM_PROMPT explicitly instructs that finance lease obligations
    are debt and operating lease obligations are not debt.
    """
    prompt = _FINANCIALS_SYSTEM_PROMPT
    assert "finance lease obligations are debt" in prompt
    assert 'current portion due within one year\n      in "short_term_debt"' in prompt or (
        'in "short_term_debt"' in prompt and "finance lease" in prompt
    )
    assert 'long-term finance lease obligations in\n      "long_term_debt"' in prompt or (
        'in "long_term_debt"' in prompt and "finance lease" in prompt
    )
    assert "operating lease obligations are not debt" in prompt
    assert '"other_current_liabilities"' in prompt
    assert '"other_non_current_liabilities"' in prompt


# ===========================================================================
# 3. Cache format marker and refusal of older markers
# ===========================================================================


def test_cli_cache_format_marker_is_p14d_finance_leases() -> None:
    """CACHE_FORMAT constant in cli.py is p14d-finance-leases-v1."""
    assert cli.CACHE_FORMAT == "p14d-finance-leases-v1"


@pytest.mark.parametrize(
    "old_marker",
    [
        "p14b-pass2-units-v1",
        "p14a-units-in-millions-v1",
        "p11a-printed-lines-v1",
        "legacy-v0",
    ],
)
def test_cli_cache_refuses_older_markers_and_names_p14d(tmp_path: Path, old_marker: str) -> None:
    """cli._load_cache raises ValueError naming p14d-finance-leases-v1 when encountering older markers."""
    key = cli.ExtractionKey(ticker="WMT", provider="claude", model="test-model", inputs=())
    fin = FinancialStatements(ticker="WMT")
    items: list[NonRecurringItem] = []
    payload = (old_marker, key, fin, items)
    cache_path = tmp_path / f"cache_{old_marker}.pkl"
    cache_path.write_bytes(pickle.dumps(payload))

    with pytest.raises(ValueError) as excinfo:
        cli._load_cache(cache_path)

    msg = str(excinfo.value)
    assert "p14d-finance-leases-v1" in msg
    assert "is not a cache entry written by this CLI" in msg


def test_cli_cache_accepts_p14d_marker(tmp_path: Path) -> None:
    """cli._load_cache successfully reads a cache with marker p14d-finance-leases-v1."""
    key = cli.ExtractionKey(ticker="WMT", provider="claude", model="test-model", inputs=())
    fin = FinancialStatements(ticker="WMT")
    items: list[NonRecurringItem] = []
    payload = (cli.CACHE_FORMAT, key, fin, items)
    cache_path = tmp_path / "valid_cache.pkl"
    cache_path.write_bytes(pickle.dumps(payload))

    loaded_key, loaded_fin, loaded_items = cli._load_cache(cache_path)
    assert loaded_key == key
    assert loaded_fin == fin
    assert loaded_items == items


# ===========================================================================
# 4. Route B prompt generation
# ===========================================================================


def test_route_b_pass1_prompts_contain_finance_lease_rules() -> None:
    """pass1_prompts generates prompt containing the finance lease rules and schema descriptions."""
    plan = FilingPlan(
        fiscal_year=2026,
        pdf_path="test.pdf",
        target_years=(2024, 2025, 2026),
        include_bs=True,
    )
    system_prompt, _user_prompt = pass1_prompts(plan)
    assert "finance lease obligations are debt" in system_prompt
    assert "operating lease obligations are not debt" in system_prompt
    assert "finance lease obligations due within one year" in system_prompt
    assert "long-term finance lease obligations" in system_prompt
    assert "Not operating lease obligations." in system_prompt


def test_route_b_cmd_prompt_exits_zero_and_emits_lease_rules() -> None:
    """session_extraction cmd_prompt on WMT.json pass 1 exits 0 and prints lease rules."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        ret = cmd_prompt(WMT_SESSION_PATH, index=0, which_pass=1)
    assert ret == 0
    output = buf.getvalue()
    assert "finance lease obligations are debt" in output
    assert "operating lease obligations are not debt" in output
    assert "finance lease obligations due within one year" in output


# ===========================================================================
# 5. Route B Walmart extraction check and debt line breakdown
# ===========================================================================


def test_route_b_walmart_session_check_exits_zero() -> None:
    """session_extraction check on extractions/WMT.json passes all validations and exits 0."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        ret = cmd_check(WMT_SESSION_PATH)
    assert ret == 0


def test_route_b_walmart_debt_lines_breakdown_by_hand_arithmetic() -> None:
    """Walmart FY2026 balance sheet debt breakdown ties exactly to hand arithmetic from PDF page 22.

    Hand arithmetic (Walmart Inc._10-K_2026-01-31_English.pdf page 22):
    ---------------------------------------------------------------------
    Short-term debt lines:
      - Short-term borrowings:                                  6,596
      - Long-term debt due within one year:                     3,542
      - Finance lease obligations due within one year:            856
      Sum short_term_debt: 6,596 + 3,542 + 856                = 10,994 M

    Long-term debt lines:
      - Long-term debt:                                        34,624
      - Long-term finance lease obligations:                    5,905
      Sum long_term_debt: 34,624 + 5,905                      = 40,529 M

    Total debt:
      short_term_debt (10,994) + long_term_debt (40,529)      = 51,523 M

    Cash and short-term investments:
      - Cash and cash equivalents (page 22):                   10,727
      - Short-term investments:                                     0
      Sum liquid cash:                                        = 10,727 M

    Net debt:
      total_debt (51,523) - liquid cash (10,727)              = 40,796 M

    Operating lease obligations (excluded from debt):
      - Operating lease obligations due within 1 yr: 1,631 M (page 22, inside other_current_liabilities)
      - Long-term operating lease obligations:      13,941 M (page 22, inside other_non_current_liabilities)
    """
    session = load_session_extraction(WMT_SESSION_PATH)
    bs = session.financials.get_balance_sheet(2026)
    assert bs is not None

    # Expected values derived by hand arithmetic above:
    assert bs.short_term_debt == 10994.0
    assert bs.long_term_debt == 40529.0
    assert bs.total_debt == 51523.0
    assert bs.cash_and_equivalents == 10727.0
    assert bs.short_term_investments == 0.0
    assert bs.net_debt == 40796.0

    # Verify underlying lines in session raw extraction
    raw_session = json.loads(WMT_SESSION_PATH.read_text("utf-8"))
    filing_pass1 = raw_session["filings"][0]["pass1"]
    bs_raw = filing_pass1["latest_balance_sheet"]

    st_debt_lines = bs_raw["short_term_debt"]
    assert len(st_debt_lines) == 3
    assert {line["label"]: line["value"] for line in st_debt_lines} == {
        "Short-term borrowings": 6596,
        "Long-term debt due within one year": 3542,
        "Finance lease obligations due within one year": 856,
    }
    # Hand sum: 6596 + 3542 + 856 = 10994
    assert sum(line["value"] for line in st_debt_lines) == 10994

    lt_debt_lines = bs_raw["long_term_debt"]
    assert len(lt_debt_lines) == 2
    assert {line["label"]: line["value"] for line in lt_debt_lines} == {
        "Long-term debt": 34624,
        "Long-term finance lease obligations": 5905,
    }
    # Hand sum: 34624 + 5905 = 40529
    assert sum(line["value"] for line in lt_debt_lines) == 40529

    # Total debt hand sum: 10994 + 40529 = 51523
    assert sum(line["value"] for line in st_debt_lines) + sum(line["value"] for line in lt_debt_lines) == 51523

    # Operating leases are explicitly in other liabilities, not debt
    other_cl_lines = bs_raw["other_current_liabilities"]
    op_lease_current = [line for line in other_cl_lines if "operating lease" in line["label"].lower()]
    assert len(op_lease_current) == 1
    assert op_lease_current[0]["label"] == "Operating lease obligations due within one year"
    assert op_lease_current[0]["value"] == 1631

    other_ncl_lines = bs_raw["other_non_current_liabilities"]
    op_lease_noncurrent = [line for line in other_ncl_lines if "operating lease" in line["label"].lower()]
    assert len(op_lease_noncurrent) == 1
    assert op_lease_noncurrent[0]["label"] == "Long-term operating lease obligations"
    assert op_lease_noncurrent[0]["value"] == 13941


def test_route_b_walmart_valuation_share_price_ties_to_28_02() -> None:
    """Route B Walmart valuation matches baseline implied share price $28.02 and net debt 40,796M.

    Hand valuation tie:
    - Current share price: $104.26
    - Market cap = 8,022M diluted shares * $104.26 = $836,374M
    - Total debt = $51,523M
    - Net debt = $40,796M
    - Noncontrolling interest (nonredeemable 6,270 + redeemable 293) = $6,563M
    - Enterprise value = $272,116M
    - Equity value = $272,116M - $40,796M - $6,563M = $224,757M
    - Implied share price = $224,757M / 8,022M shares = $28.01757... -> $28.02
    - Downside = ($28.01757... - $104.26) / $104.26 = -73.1%
    """
    price_mock = PriceData(
        ticker="WMT",
        stock_returns=np.zeros(60),
        market_returns=np.zeros(60),
        dates=pd.DatetimeIndex(pd.date_range("2021-01-01", periods=60, freq="D")),
        current_price=104.26000213623047,
        periods_per_year=12,
    )
    capm_mock = CAPMResult(
        beta=0.5662169972765607,
        risk_free_rate=0.04,
        equity_risk_premium=0.06892192021225155,
        r_squared=0.182,
        std_error=0.158,
    )

    buf = io.StringIO()
    with (
        patch("cli.fetch_price_data", return_value=price_mock),
        patch("cli.run_capm", return_value=capm_mock),
        patch("sys.argv", ["cli.py", "--session-file", str(WMT_SESSION_PATH)]),
        redirect_stdout(buf),
    ):
        cli.main()

    stdout = buf.getvalue()
    assert "Total debt:           $      51,523M" in stdout
    assert "Less: Net Debt               $      40,796M" in stdout
    assert "Implied Share Price:         $      28.02" in stdout
    assert "DOWNSIDE:  -73.1%" in stdout


def test_cli_cache_save_and_load_roundtrip(tmp_path: Path) -> None:
    """cli._save_cache writes CACHE_FORMAT p14d-finance-leases-v1 which _load_cache reads."""
    key = cli.ExtractionKey(ticker="TST", provider="gemini", model="gemini-3.1-pro-preview", inputs=())
    fin = FinancialStatements(ticker="TST")
    items: list[NonRecurringItem] = []
    cache_path = tmp_path / "roundtrip.pkl"
    cli._save_cache(cache_path, key, fin, items)

    # Check written bytes first element is CACHE_FORMAT
    raw = pickle.loads(cache_path.read_bytes())
    assert raw[0] == "p14d-finance-leases-v1"
    assert raw[0] == cli.CACHE_FORMAT

    loaded_key, loaded_fin, loaded_items = cli._load_cache(cache_path)
    assert loaded_key == key
    assert loaded_fin == fin
    assert loaded_items == items


@pytest.mark.parametrize(
    "bad_payload",
    [
        (),
        ("p14d-finance-leases-v1",),
        ("p14d-finance-leases-v1", "not-a-key"),
        ("p14d-finance-leases-v1", "not-a-key", "fin"),
        ["p14d-finance-leases-v1", "key", "fin", []],  # list not tuple
    ],
)
def test_cli_cache_rejects_malformed_payload(tmp_path: Path, bad_payload: object) -> None:
    """_load_cache raises ValueError naming expected marker when payload is not valid 4-tuple."""
    cache_path = tmp_path / "bad.pkl"
    cache_path.write_bytes(pickle.dumps(bad_payload))
    with pytest.raises(ValueError) as excinfo:
        cli._load_cache(cache_path)
    assert "p14d-finance-leases-v1" in str(excinfo.value)
    assert "is not a cache entry written by this CLI" in str(excinfo.value)
