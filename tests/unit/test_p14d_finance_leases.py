"""Tests for P14d: finance lease obligations are debt, operating lease obligations are not.

The user's decision "83a" (2026-10-04, backlog item 83). The unit changed three
things, and each is locked here:

1. `_FINANCIALS_BALANCE_SHEET_SCHEMA`: `short_term_debt` names the finance lease
   obligations due within one year, `long_term_debt` the long-term finance lease
   obligations, each excludes operating lease obligations, and
   `other_current_liabilities` names the operating lease obligations due within
   one year.
2. `_FINANCIALS_SYSTEM_PROMPT`, BALANCE SHEET RULES: one rule saying the same.
   Route B prints the same prompt (`session_extraction prompt --pass 1`).
3. `cli.CACHE_FORMAT` is "p14d-finance-leases-v1"; a pickle carrying any older
   marker is refused with a ValueError naming the new marker.

Where every expected value comes from (the tester card, `.claude/agents/tester.md`):

- The schema and prompt phrases are the wording the assignment
  `.agent/assignments/P14d-finance-leases.md` ("What to do", steps 1 and 2) asks for.
- The marker string is the one the assignment names (step 3).
- The Walmart debt arithmetic is built in the test from the figures printed on
  `10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf`, PDF page 22
  (printed page 53, "Consolidated Balance Sheets, As of January 31, (Amounts in
  millions)", column 2026), read off the page by the tester. The sums are worked by
  hand in the comments. No figure is taken from `extractions/WMT.json`, a cached
  pickle or a run of the code.

`extractions/` and `10K_filings/` are git-ignored. The one test that needs the real
session file and the real PDF is skipped when either is absent; every other test
runs on any machine. No paid API call and no network socket.
"""

from __future__ import annotations

import io
import json
import pickle
import re
import socket
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

import cli
from ingestion.claude_extractor import (
    _FINANCIALS_BALANCE_SHEET_SCHEMA,
    _FINANCIALS_SYSTEM_PROMPT,
    FilingPlan,
    Pass1ShapeError,
    parse_pass1,
    pass1_prompts,
)
from ingestion.session_extraction import (
    SESSION_FORMAT,
    cmd_check,
    cmd_prompt,
    load_session_extraction,
)
from models.financial_statements import FinancialStatements, NonRecurringItem
from tests.unit._printed_lines import printed_year

REPO_ROOT = Path(__file__).resolve().parents[2]
WMT_SESSION_PATH = REPO_ROOT / "extractions" / "WMT.json"

NEW_MARKER = "p14d-finance-leases-v1"


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no test makes network calls."""
    def _refused(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a unit test attempted a network connection: {args!r}")

    monkeypatch.setattr(socket.socket, "connect", _refused)
    monkeypatch.setattr(socket.socket, "connect_ex", _refused)
    monkeypatch.setattr(socket, "create_connection", _refused)


def _one_line(text: str) -> str:
    """Collapse every run of whitespace to one space, so a wrapped prompt reads as one line."""
    return re.sub(r"\s+", " ", text)


# ===========================================================================
# 1. Schema descriptions in _FINANCIALS_BALANCE_SHEET_SCHEMA
#    Expected phrases: assignment P14d-finance-leases, "What to do" step 1.
# ===========================================================================


def test_schema_short_term_debt_includes_finance_leases_excludes_operating() -> None:
    desc = _FINANCIALS_BALANCE_SHEET_SCHEMA["short_term_debt"]
    assert "short-term borrowings" in desc
    assert "finance lease obligations due within one year" in desc
    assert "Not operating lease obligations." in desc


def test_schema_long_term_debt_includes_finance_leases_excludes_operating() -> None:
    desc = _FINANCIALS_BALANCE_SHEET_SCHEMA["long_term_debt"]
    assert "long-term finance lease obligations" in desc
    assert "Not operating lease obligations." in desc


def test_schema_other_current_liabilities_includes_operating_lease_obligations() -> None:
    desc = _FINANCIALS_BALANCE_SHEET_SCHEMA["other_current_liabilities"]
    assert "operating lease obligations due within one year" in desc


def test_schema_other_non_current_liabilities_includes_operating_lease_liabilities() -> None:
    # Step 1: "it names operating lease liabilities already; keep it."
    desc = _FINANCIALS_BALANCE_SHEET_SCHEMA["other_non_current_liabilities"]
    assert "operating lease liabilities" in desc


def test_schema_no_catch_all_field_claims_finance_leases() -> None:
    # The rule is one-directional only if no catch-all invites a finance lease row:
    # the two other_ liability fields must not name "finance lease".
    for field in ("other_current_liabilities", "other_non_current_liabilities"):
        assert "finance lease" not in _FINANCIALS_BALANCE_SHEET_SCHEMA[field].lower(), field


# ===========================================================================
# 2. The rule in _FINANCIALS_SYSTEM_PROMPT
#    Expected content: assignment step 2 — finance lease obligations are debt
#    (current in short_term_debt, long-term in long_term_debt); operating lease
#    obligations are not debt and go to the catch-all fields.
# ===========================================================================


def _lease_rule(prompt: str) -> str:
    """The one bullet of the prompt that states the lease rule, on one line.

    Asserting each phrase inside this bullet, rather than anywhere in the prompt,
    matters: "short_term_debt" and "other_current_liabilities" also appear in the
    embedded schema, so a whole-prompt search would pass with the rule deleted.
    """
    flat = _one_line(prompt)
    start = flat.find("- finance lease obligations are debt")
    assert start != -1, "the prompt states no bullet beginning 'finance lease obligations are debt'"
    end = flat.find(" - ", start + 2)
    return flat[start:] if end == -1 else flat[start:end]


def test_system_prompt_states_the_lease_rule_inside_balance_sheet_rules() -> None:
    flat = _one_line(_FINANCIALS_SYSTEM_PROMPT)
    rules_at = flat.find("BALANCE SHEET RULES")
    rule_at = flat.find("- finance lease obligations are debt")
    assert rules_at != -1
    assert rule_at > rules_at, "the lease rule must sit under BALANCE SHEET RULES"

    rule = _lease_rule(_FINANCIALS_SYSTEM_PROMPT)
    # Finance leases: debt, split current / long-term between the two debt fields.
    assert '"short_term_debt"' in rule
    assert '"long_term_debt"' in rule
    assert rule.index('"short_term_debt"') < rule.index('"long_term_debt"')
    # Operating leases: not debt, in the two catch-all fields.
    assert "operating lease obligations are not debt" in rule
    assert '"other_current_liabilities"' in rule
    assert '"other_non_current_liabilities"' in rule
    assert rule.index("operating lease obligations are not debt") < rule.index(
        '"other_current_liabilities"'
    )


def test_route_a_pass1_prompt_carries_the_rule_and_schema() -> None:
    # pass1_prompts is the one function both routes take the Pass 1 prompt from.
    plan = FilingPlan(fiscal_year=2026, pdf_path="test.pdf", target_years=None, include_bs=True)
    system_prompt, _user_prompt = pass1_prompts(plan)
    rule = _lease_rule(system_prompt)
    assert "operating lease obligations are not debt" in rule
    assert "finance lease obligations due within one year" in system_prompt
    assert "long-term finance lease obligations" in system_prompt
    assert "Not operating lease obligations." in system_prompt


def test_route_b_cmd_prompt_prints_the_lease_rule(tmp_path: Path) -> None:
    """Route B: `session_extraction prompt --filing 0 --pass 1` prints the same rule.

    The session file is built here, not read from extractions/ (git-ignored). Pass 1's
    prompt needs only the plan: one filing, so plan_filings gives target_years None
    and include_bs True (docs/3-architecture/extraction.md routing table). No PDF is
    opened for Pass 1's prompt.
    """
    session = {
        "format": SESSION_FORMAT,
        "ticker": "WMT",
        "company_name": "Walmart Inc.",
        "extracted_by": {"model": "test", "tool": "Claude Code", "date": "2026-10-04"},
        "filings": [{
            "fiscal_year": 2026,
            "pdf_path": str(tmp_path / "not-opened.pdf"),
            "target_years": None,
            "include_bs": True,
            "pass1": None,
            "pass2": None,
        }],
    }
    path = tmp_path / "WMT.json"
    path.write_text(json.dumps(session), encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        ret = cmd_prompt(path, index=0, which_pass=1)
    assert ret == 0
    output = buf.getvalue()
    rule = _lease_rule(output)
    assert "operating lease obligations are not debt" in rule
    assert '"other_non_current_liabilities"' in rule
    assert "finance lease obligations due within one year" in output


# ===========================================================================
# 3. The CLI cache marker
#    Expected marker: assignment step 3.
# ===========================================================================


def test_cli_cache_format_marker_is_p14d_finance_leases() -> None:
    assert cli.CACHE_FORMAT == NEW_MARKER


def _key() -> cli.ExtractionKey:
    return cli.ExtractionKey(ticker="WMT", provider="claude", model="test-model", inputs=())


@pytest.mark.parametrize(
    "old_marker",
    [
        "p14b-pass2-units-v1",        # the marker P14d replaced
        "p14a-units-in-millions-v1",
        "p11a-printed-lines-v1",
        "legacy-v0",
    ],
)
def test_cli_cache_refuses_older_markers_and_names_p14d(tmp_path: Path, old_marker: str) -> None:
    items: list[NonRecurringItem] = []
    payload = (old_marker, _key(), FinancialStatements(ticker="WMT"), items)
    cache_path = tmp_path / f"cache_{old_marker}.pkl"
    cache_path.write_bytes(pickle.dumps(payload))

    with pytest.raises(ValueError, match=re.escape(repr(NEW_MARKER))) as excinfo:
        cli._load_cache(cache_path)
    assert "is not a cache entry written by this CLI" in str(excinfo.value)


def test_cli_cache_accepts_the_p14d_marker(tmp_path: Path) -> None:
    # Written with the literal marker, not cli.CACHE_FORMAT, so that a change to the
    # constant turns this red instead of moving with it.
    key = _key()
    fin = FinancialStatements(ticker="WMT")
    items: list[NonRecurringItem] = []
    cache_path = tmp_path / "valid_cache.pkl"
    cache_path.write_bytes(pickle.dumps((NEW_MARKER, key, fin, items)))

    loaded_key, loaded_fin, loaded_items = cli._load_cache(cache_path)
    assert loaded_key == key
    assert loaded_fin == fin
    assert loaded_items == items


def test_cli_cache_save_writes_p14d_marker_and_roundtrips(tmp_path: Path) -> None:
    key = cli.ExtractionKey(ticker="TST", provider="gemini", model="gemini-3.1-pro-preview", inputs=())
    fin = FinancialStatements(ticker="TST")
    items: list[NonRecurringItem] = []
    cache_path = tmp_path / "roundtrip.pkl"
    cli._save_cache(cache_path, key, fin, items)

    raw = pickle.loads(cache_path.read_bytes())
    assert raw[0] == NEW_MARKER

    loaded_key, loaded_fin, loaded_items = cli._load_cache(cache_path)
    assert loaded_key == key
    assert loaded_fin == fin
    assert loaded_items == items


@pytest.mark.parametrize(
    "bad_payload",
    [
        (),
        (NEW_MARKER,),
        (NEW_MARKER, "not-a-key"),
        (NEW_MARKER, "not-a-key", "fin"),
        (NEW_MARKER, "not-a-key", "fin", []),   # right marker and length, key not an ExtractionKey
        [NEW_MARKER, "key", "fin", []],          # a list, not a tuple
    ],
)
def test_cli_cache_rejects_malformed_payload(tmp_path: Path, bad_payload: object) -> None:
    # _load_cache's docstring: "ValueError: when the file is not a cache entry in this format."
    cache_path = tmp_path / "bad.pkl"
    cache_path.write_bytes(pickle.dumps(bad_payload))
    with pytest.raises(ValueError, match=re.escape(repr(NEW_MARKER))) as excinfo:
        cli._load_cache(cache_path)
    assert "is not a cache entry written by this CLI" in str(excinfo.value)


# ===========================================================================
# 4. Walmart FY2026: the debt arithmetic, built from the filing page
# ===========================================================================
#
# Every figure below is read off Walmart Inc._10-K_2026-01-31_English.pdf, PDF page 22
# (printed page 53), "Consolidated Balance Sheets", column "2026", (Amounts in
# millions). Each printed row is mapped to the Pass 1 field the P14d schema names.
#
#   ASSETS                                          field
#   Cash and cash equivalents              10,727   cash
#   Receivables, net                       11,172   accounts_receivable
#   Inventories                            58,851   inventory
#   Prepaid expenses and other              4,124   other_current_assets
#   Property and equipment, net           136,083   ppe_net
#   Operating lease right-of-use assets    14,750   other_non_current_assets
#   Finance lease right-of-use assets, net  6,123   other_non_current_assets
#   Goodwill                               28,735   goodwill
#   Other long-term assets                 14,103   other_non_current_assets
#   Total assets                          284,668   total_assets (check row)
#
#   LIABILITIES
#   Short-term borrowings                   6,596   short_term_debt
#   Accounts payable                       63,061   accounts_payable
#   Accrued liabilities                    31,187   accrued_liabilities
#   Accrued income taxes                      596   other_current_liabilities
#   Long-term debt due within one year      3,542   short_term_debt
#   Operating lease obligations due
#     within one year                       1,631   other_current_liabilities  (not debt)
#   Finance lease obligations due
#     within one year                         856   short_term_debt            (debt)
#   Long-term debt                         34,624   long_term_debt
#   Long-term operating lease obligations  13,941   other_non_current_liabilities (not debt)
#   Long-term finance lease obligations     5,905   long_term_debt             (debt)
#   Deferred income taxes and other        16,549   other_non_current_liabilities
#   Redeemable noncontrolling interest        293   other_non_current_liabilities (schema:
#                                                   "any row printed between liabilities
#                                                   and equity"); also the redeemable memo
#   Total shareholders' equity            105,887   total_equity
#   Nonredeemable noncontrolling interest   6,270   memo (inside total equity)
#   Total liabilities, redeemable NCI and
#     shareholders' equity                284,668   total_liabilities_and_equity (check row)
#
# The page prints no short-term investments row and no intangible assets row: [].
#
# Hand sums:
#   short_term_debt   = 6,596 + 3,542 + 856            = 10,994
#   long_term_debt    = 34,624 + 5,905                 = 40,529
#   total_debt        = 10,994 + 40,529                = 51,523
#   net_debt          = 51,523 - 10,727 (cash) - 0     = 40,796
#   other_current_liabilities     = 596 + 1,631        =  2,227
#   other_non_current_liabilities = 13,941 + 16,549 + 293 = 30,783
#   other_non_current_assets      = 14,750 + 6,123 + 14,103 = 34,976
#
# Balance check, both sides against the printed 284,668:
#   current assets  10,727 + 11,172 + 58,851 + 4,124          =  84,874 (page prints 84,874)
#   total assets    84,874 + 136,083 + 28,735 + 34,976         = 284,668
#   current liab.   63,061 + 31,187 + 2,227 + 10,994           = 107,469 (page prints 107,469)
#   liabilities     107,469 + 40,529 + 30,783                  = 178,781
#   L + E           178,781 + 105,887                          = 284,668
#
# The other placement (route A's Gemini run, STATUS.md section 3): the two finance
# lease rows in the catch-alls instead of debt.
#   short_term_debt   = 6,596 + 3,542                  = 10,138
#   long_term_debt    = 34,624                         = 34,624
#   net_debt          = 10,138 + 34,624 - 10,727       = 34,035
#   other_current_liabilities     = 596 + 1,631 + 856  =  3,083
#   other_non_current_liabilities = 30,783 + 5,905     = 36,688
#   The balance check still passes (each row moved within liabilities), which is why
#   no check sees the difference: 40,796 - 34,035 = 6,761 = 856 + 5,905.

WMT_PAGE = 22


def _row(label: str, value: float) -> dict[str, Any]:
    return {"label": label, "value": value, "page": WMT_PAGE}


def _walmart_balance_sheet(finance_leases_in_debt: bool) -> dict[str, Any]:
    """Pass 1's latest_balance_sheet for Walmart FY2026, rows as printed on page 22."""
    fl_current = _row("Finance lease obligations due within one year", 856)
    fl_long = _row("Long-term finance lease obligations", 5905)
    short_term_debt = [
        _row("Short-term borrowings", 6596),
        _row("Long-term debt due within one year", 3542),
    ]
    long_term_debt = [_row("Long-term debt", 34624)]
    other_current = [
        _row("Accrued income taxes", 596),
        _row("Operating lease obligations due within one year", 1631),
    ]
    other_non_current = [
        _row("Long-term operating lease obligations", 13941),
        _row("Deferred income taxes and other", 16549),
        _row("Redeemable noncontrolling interest", 293),
    ]
    if finance_leases_in_debt:
        short_term_debt.append(fl_current)
        long_term_debt.append(fl_long)
    else:
        other_current.append(fl_current)
        other_non_current.append(fl_long)
    return {
        "year": 2026,
        "cash": [_row("Cash and cash equivalents", 10727)],
        "short_term_investments": [],
        "accounts_receivable": [_row("Receivables, net", 11172)],
        "inventory": [_row("Inventories", 58851)],
        "other_current_assets": [_row("Prepaid expenses and other", 4124)],
        "ppe_net": [_row("Property and equipment, net", 136083)],
        "goodwill": [_row("Goodwill", 28735)],
        "intangible_assets": [],
        "other_non_current_assets": [
            _row("Operating lease right-of-use assets", 14750),
            _row("Finance lease right-of-use assets, net", 6123),
            _row("Other long-term assets", 14103),
        ],
        "accounts_payable": [_row("Accounts payable", 63061)],
        "accrued_liabilities": [_row("Accrued liabilities", 31187)],
        "other_current_liabilities": other_current,
        "short_term_debt": short_term_debt,
        "long_term_debt": long_term_debt,
        "other_non_current_liabilities": other_non_current,
        "total_equity": [_row("Total shareholders' equity", 105887)],
        "noncontrolling_interest_nonredeemable": [
            _row("Nonredeemable noncontrolling interest", 6270),
        ],
        "noncontrolling_interest_redeemable": [_row("Redeemable noncontrolling interest", 293)],
        "total_assets": [_row("Total assets", 284668)],
        "total_liabilities_and_equity": [
            _row("Total liabilities, redeemable noncontrolling interest, and "
                 "shareholders' equity", 284668),
        ],
    }


# One income-statement / cash-flow year, needed only because Pass 1 requires one. Its
# figures are the reconciling base of tests/unit/test_session_extraction.py, not
# Walmart's, and no assertion reads them:
#   gross 600 = 1000 - 400;  EBIT 300 = 600 - 150 - 100 - 50;  NI 228 = 300 + 10 - 20 - 5 - 57
_FILLER_YEAR: dict[str, list[float]] = {
    "revenue": [1000], "cost_of_revenue": [400], "gross_profit": [600], "sga": [150],
    "rd_expense": [100], "depreciation_amortization": [30], "other_operating_expense": [50],
    "operating_income": [300], "interest_expense": [20], "interest_income": [10],
    "other_non_operating": [-5], "tax_expense": [57], "net_income": [228],
    "diluted_shares": [48], "cfo": [290], "capex": [70], "sbc": [25],
    "change_in_working_capital": [-15],
}


def _walmart_pass1(finance_leases_in_debt: bool) -> dict[str, Any]:
    return {
        "ticker": "WMT",
        "company_name": "Walmart Inc.",
        "currency": "USD",
        "units": {"printed": "(Amounts in millions)", "page": WMT_PAGE},
        "share_units": {"printed": "(Amounts in millions)", "page": WMT_PAGE},
        "historical_years": [printed_year(2026, _FILLER_YEAR)],
        "latest_balance_sheet": _walmart_balance_sheet(finance_leases_in_debt),
    }


def test_walmart_finance_leases_in_debt_give_net_debt_40_796() -> None:
    financials, failures = parse_pass1(
        json.dumps(_walmart_pass1(finance_leases_in_debt=True)), "WMT", "Walmart Inc.",
    )
    assert failures == []
    bs = financials.get_balance_sheet(2026)
    assert bs is not None

    # Hand sums in the block comment above section 4.
    assert bs.short_term_debt == 10994.0
    assert bs.long_term_debt == 40529.0
    assert bs.total_debt == 51523.0
    assert bs.net_debt == 40796.0
    # Operating leases sit in the catch-alls, outside debt.
    assert bs.other_current_liabilities == 2227.0
    assert bs.other_non_current_liabilities == 30783.0
    # Both sides of the balance sheet tie to the printed 284,668.
    assert bs.total_assets == 284668.0
    assert bs.total_liabilities_and_equity == 284668.0


def test_walmart_finance_leases_outside_debt_give_net_debt_34_035() -> None:
    # The contrast that motivated decision 83a: the same page, the two finance lease
    # rows in the catch-alls. Net debt falls by exactly 856 + 5,905 = 6,761 and the
    # balance check still passes.
    financials, failures = parse_pass1(
        json.dumps(_walmart_pass1(finance_leases_in_debt=False)), "WMT", "Walmart Inc.",
    )
    assert failures == []
    bs = financials.get_balance_sheet(2026)
    assert bs is not None
    assert bs.short_term_debt == 10138.0
    assert bs.long_term_debt == 34624.0
    assert bs.net_debt == 34035.0
    assert bs.other_current_liabilities == 3083.0
    assert bs.other_non_current_liabilities == 36688.0
    assert bs.total_assets == 284668.0
    assert bs.total_liabilities_and_equity == 284668.0


@pytest.mark.parametrize("field", ["short_term_debt", "long_term_debt"])
def test_walmart_absent_debt_field_stops_and_names_it(field: str) -> None:
    # Rule 3: an absent debt key is not read as 0. claude_extractor.pass1_problems
    # reports it and parse_pass1 raises Pass1ShapeError (a ValueError), naming the key.
    pass1 = _walmart_pass1(finance_leases_in_debt=True)
    del pass1["latest_balance_sheet"][field]
    with pytest.raises(Pass1ShapeError, match=field):
        parse_pass1(json.dumps(pass1), "WMT", "Walmart Inc.")


# ===========================================================================
# 5. Route B's real Walmart file, where it exists (git-ignored; skipped elsewhere)
# ===========================================================================


def _wmt_pdf_paths() -> list[Path]:
    if not WMT_SESSION_PATH.is_file():
        return []
    data = json.loads(WMT_SESSION_PATH.read_text(encoding="utf-8"))
    return [Path(f["pdf_path"]) for f in data.get("filings", [])]


_WMT_REAL_FILES_PRESENT = WMT_SESSION_PATH.is_file() and all(
    p.is_file() for p in _wmt_pdf_paths()
)


@pytest.mark.skipif(
    not _WMT_REAL_FILES_PRESENT,
    reason="extractions/WMT.json or the Walmart 10-K PDF it names is absent (both git-ignored)",
)
def test_real_route_b_walmart_file_maps_page_22_rows_by_the_rule() -> None:
    """The real route B file: `check` exits 0, and its debt rows are page 22's rows.

    Expected: exit code 0 is the assignment's done-criterion 3 for P14d-finance-leases.
    The rows and values are those read off PDF page 22 (block comment, section 4),
    not the file's own figures.
    """
    buf = io.StringIO()
    with redirect_stdout(buf):
        ret = cmd_check(WMT_SESSION_PATH)
    assert ret == 0, buf.getvalue()

    raw = json.loads(WMT_SESSION_PATH.read_text(encoding="utf-8"))
    bs_raw = raw["filings"][0]["pass1"]["latest_balance_sheet"]

    def rows(field: str) -> dict[str, float]:
        return {line["label"]: line["value"] for line in bs_raw[field]}

    assert rows("short_term_debt") == {
        "Short-term borrowings": 6596,
        "Long-term debt due within one year": 3542,
        "Finance lease obligations due within one year": 856,
    }
    assert rows("long_term_debt") == {
        "Long-term debt": 34624,
        "Long-term finance lease obligations": 5905,
    }
    assert rows("other_current_liabilities")["Operating lease obligations due within one year"] == 1631
    assert rows("other_non_current_liabilities")["Long-term operating lease obligations"] == 13941

    # Loaded and converted (the page prints "(Amounts in millions)", so one printed
    # unit is 1.0 million): the hand sums of section 4.
    bs = load_session_extraction(WMT_SESSION_PATH).financials.get_balance_sheet(2026)
    assert bs is not None
    assert bs.short_term_debt == 10994.0
    assert bs.long_term_debt == 40529.0
    assert bs.total_debt == 51523.0
    assert bs.net_debt == 40796.0
