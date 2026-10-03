"""What `P11a-printed-lines` changed, locked: Pass 1 returns printed rows, Python adds.

Since `ae27f47` every Pass 1 money field is a list of printed rows
(`{"label", "value", "page"}`), `figure_from_printed_lines` adds them, the printed
subtotals and totals are checked against Python's sums, and a failed check is shown
and kept, never repaired. This file holds one group per item of
`.agent/assignments/P11a-tests.md`, "What to do", 2 to 8:

  2. the sum;
  3. empty lists, per the orchestrator's round 2 decisions;
  4. the balance check, and its tolerance;
  5. route A's retries, with `_call_llm` stubbed;
  6. the stops on a malformed line or an absent key;
  7. the formats: a v1 session file, an old CLI cache;
  8. the outputs: the CLI's balance check and `templates/_statements.html`.

**Where every expected value comes from.** Each is hand arithmetic written in a
comment beside it, the input itself, or a name the P11a assignment requires a
message to carry (the field, the year, the line index, both format names). Two
values are read from the code ON PURPOSE, because the assignment says to: the
balance tolerance, `BalanceSheet.printed_total_tolerance()` ("read from the code,
not retyped"), and `SESSION_FORMAT` where a test only needs a valid file. **No
expected value here was read off the code's output.**

The base figures are those of `test_claude_extractor.py`, one printed row each:

  revenue 1000, cost_of_revenue 400, gross profit 600 = 1000 - 400
  sga 150, rd_expense 100, other_operating_expense 50 (D&A 30 inside)
  operating income 300 = 600 - 150 - 100 - 50
  interest_income 10, interest_expense 20, other_non_operating -5, tax 57
  net income 228 = 300 + 10 - 20 + (-5) - 57
  cfo 290, capex 70, sbc 25, change_in_working_capital -15, diluted_shares 48

  balance sheet: assets 100 + 50 + 80 + 60 + 10 + 300 + 200 + 40 + 20 = 860
                 liabilities 70 + 30 + 15 + 25 + 400 + 35 = 575; equity 285
                 L + E = 575 + 285 = 860; printed totals 860 and 860

**No test reaches the API or the network.** An autouse fixture replaces `_call_llm`
with a function that raises; the route A tests replace it again with a scripted
stub that raises when called more often than scripted. No test reads
`10K_filings/` or `extractions/`: the PDFs are a few bytes under `tmp_path`.
"""

from __future__ import annotations

import argparse
import json
import pickle
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

import app as app_module
import cli
import ingestion.claude_extractor as ce
from api import routes_valuation
from ingestion.claude_extractor import (
    Pass1ShapeError,
    ProviderResolution,
    figure_from_printed_lines,
    parse_pass1,
)
from ingestion.session_extraction import cmd_check, load_session_extraction
from models.financial_statements import BalanceSheet, FinancialStatements
from tests.unit._printed_lines import lines, printed_balance_sheet, printed_year
from tests.unit._session_route_helpers import (
    FISCAL_YEAR,
    make_pdf,
    session_dict,
    strip_tags,
    write_session,
)

TICKER = "TST"
COMPANY = "Test Co"


@pytest.fixture(autouse=True)
def _no_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Close the API boundary. A test that needs the model stubs it again."""

    def _refuse(*args: object, **kwargs: object) -> tuple[str, int, int]:
        raise AssertionError("a P11a test reached _call_llm")

    monkeypatch.setattr(ce, "_call_llm", _refuse)


# ===========================================================================
# Builders: the base figures above, in the printed-lines shape
# ===========================================================================

_BASE_YEAR: dict[str, list[float]] = {
    "revenue": [1000], "cost_of_revenue": [400], "gross_profit": [600], "sga": [150],
    "rd_expense": [100], "depreciation_amortization": [30],
    "other_operating_expense": [50], "operating_income": [300],
    "interest_expense": [20], "interest_income": [10], "other_non_operating": [-5],
    "tax_expense": [57], "net_income": [228], "diluted_shares": [48], "cfo": [290],
    "capex": [70], "sbc": [25], "change_in_working_capital": [-15],
}

_BASE_BALANCE_SHEET: dict[str, list[float]] = {
    "cash": [100], "short_term_investments": [50], "accounts_receivable": [80],
    "inventory": [60], "other_current_assets": [10], "ppe_net": [300],
    "goodwill": [200], "intangible_assets": [40], "other_non_current_assets": [20],
    "accounts_payable": [70], "accrued_liabilities": [30],
    "other_current_liabilities": [15], "short_term_debt": [25],
    "long_term_debt": [400], "other_non_current_liabilities": [35],
    "total_equity": [285], "noncontrolling_interest_nonredeemable": [],
    "noncontrolling_interest_redeemable": [], "total_assets": [860],
    "total_liabilities_and_equity": [860],
}


def year(y: int = 2024, **changes: Sequence[float]) -> dict[str, Any]:
    return printed_year(y, _BASE_YEAR | changes)


def balance(y: int = 2024, **changes: Sequence[float]) -> dict[str, Any]:
    return printed_balance_sheet(y, _BASE_BALANCE_SHEET | changes)


def answer(years: list[dict[str, Any]], bs: dict[str, Any] | None = None) -> str:
    return json.dumps({
        "ticker": TICKER, "company_name": COMPANY, "currency": "USD",
        "units": "Millions", "historical_years": years,
        "latest_balance_sheet": bs if bs is not None else {},
    })


def parse(years: list[dict[str, Any]], bs: dict[str, Any] | None = None) -> tuple[
    FinancialStatements, list[str],
]:
    return parse_pass1(answer(years, bs), TICKER, COMPANY)


# A balance sheet carrying a row of 4,124 (the size of Walmart's "Prepaid expenses
# and other", P11a criterion 5), with every total moved by it, by hand:
#   other_current_assets rows 10 and 4,124
#   assets = 860 + 4,124 = 4,984
#   equity = 285 + 4,124 = 4,409;  L + E = 575 + 4,409 = 4,984
# Printed totals 4,984 and 4,984. DROPPING the 4,124 row leaves the assets side
# mapping to 860 against a printed 4,984: a difference of 4,984 - 860 = +4,124.
WITH_ROW = {
    "other_current_assets": [10, 4124], "total_equity": [4409],
    "total_assets": [4984], "total_liabilities_and_equity": [4984],
}
DROPPED_ROW = WITH_ROW | {"other_current_assets": [10]}


def table_line(out: str, label: str, *also: str) -> str:
    """The one line of printed output that carries `label` and every part of `also`."""
    found = [line for line in out.splitlines()
             if label in line and all(part in line for part in also)]
    assert len(found) == 1, f"expected one line with {label!r}, {also!r}, got {found!r}"
    return found[0]


def cli_check_line(out: str, label: str) -> str:
    """The CLI's balance check row for `label`: the one reading "printed ... mapped"."""
    return table_line(out, label, " printed ", " mapped ")


# ===========================================================================
# 2. The sum
# ===========================================================================

def test_a_field_of_two_rows_is_their_sum() -> None:
    # Walmart 2026 capex: "Payments for property and equipment" 26,642 and
    # "Payments for business acquisitions" 53 (P11a criterion 3). 26,642 + 53 = 26,695.
    rows = lines("capex", [26642, 53], page=23)
    assert figure_from_printed_lines(rows, "capex", "year 2026") == 26695.0


def test_two_capex_rows_are_summed_and_stored_negative() -> None:
    fin, errors = parse([year(2026, capex=[26642, 53])])
    (cfs,) = fin.cash_flow_statements
    # 26,642 + 53 = 26,695, stored as a cash outflow: negative
    # (docs/4-conventions/units-and-signs.md, row `capital_expenditures`).
    assert cfs.capital_expenditures == -26695.0
    # capex is in no income statement check, and the rest reconciles.
    assert errors == []


def test_summed_rows_feed_the_checks() -> None:
    # sga as two rows, 100 + 50 = 150, the base figure: operating income still
    # 1000 - 400 - 150 - 100 - 50 = 300, so the check passes. other_current_assets
    # as two rows, 6 + 4 = 10, the base figure: assets still 860.
    fin, errors = parse([year(sga=[100, 50])], balance(other_current_assets=[6, 4]))
    assert fin.income_statements[0].sga == 150.0
    assert fin.balance_sheets[0].other_current_assets == 10.0
    assert errors == []


def test_a_field_of_two_rows_is_their_sum_by_route_b(tmp_path: Path) -> None:
    # The session helper's 2024 year is the base times k = 2: capex 140. Written
    # as two rows, 100 + 40 = 140; the loader must add them to the same 140.
    data = session_dict(make_pdf(tmp_path))
    data["filings"][0]["pass1"]["historical_years"][1]["capex"] = lines("capex", [100, 40])
    loaded = load_session_extraction(write_session(tmp_path, data))
    assert loaded.financials.get_cash_flow(2024).capital_expenditures == -140.0
    assert loaded.validation_errors == []


# ===========================================================================
# 3. Empty lists, per the orchestrator's round 2 decisions
# ===========================================================================

def test_an_empty_catch_all_on_the_income_statement_is_zero() -> None:
    # other_non_operating [] is 0. Net income then 300 + 10 - 20 + 0 - 57 = 233,
    # printed as 233, so the check passes.
    fin, errors = parse([year(other_non_operating=[], net_income=[233])])
    assert fin.income_statements[0].other_non_operating == 0.0
    assert errors == []


def test_an_empty_catch_all_on_the_balance_sheet_is_zero() -> None:
    # other_non_current_liabilities [] is 0. Liabilities 70 + 30 + 15 + 25 + 400
    # + 0 = 540; with equity 320, L + E = 540 + 320 = 860, the printed total.
    fin, errors = parse([year()], balance(other_non_current_liabilities=[],
                                          total_equity=[320]))
    assert fin.balance_sheets[0].other_non_current_liabilities == 0.0
    assert errors == []


# (JSON key, the BalanceSheet memo, the label of its row in the parser's table,
#  in the CLI, and on the page). The labels are the code's own row names, used to
#  find the row; they are not expected values.
TOTALS = [
    pytest.param("total_assets", "printed_total_assets", "Total Assets",
                 "Total Assets", "Total Assets", id="total_assets"),
    pytest.param("total_liabilities_and_equity", "printed_total_liabilities_and_equity",
                 "Total L + E", "Total Liab + Equity", "Total Liabilities + Equity",
                 id="total_liabilities_and_equity"),
]


@pytest.mark.parametrize(("key", "memo", "table_label", "cli_label", "page_label"), TOTALS)
def test_an_empty_printed_total_is_not_extracted_and_fails(
    key: str, memo: str, table_label: str, cli_label: str, page_label: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Round 2 decision 1: `[]` on a printed total is None, "not extracted"; the
    check FAILs saying so, and no printed 0 and no gap of the whole sheet appear."""
    fin, errors = parse([year()], balance(**{key: []}))
    (bs,) = fin.balance_sheets
    assert getattr(bs, memo) is None
    # The figures are kept: the mapped assets are still 860 (input, by hand).
    assert bs.total_assets == 860.0
    # One failure, naming the total and saying it was not extracted.
    assert len(errors) == 1
    assert key in errors[0]
    assert "not extracted" in errors[0]
    # No printed 0, and no gap of the whole 860 side: the message states no amount.
    assert f"{key}=0" not in errors[0]
    assert "860" not in errors[0]
    assert "diff" not in errors[0]
    # The check table printed by the parser.
    row = table_line(capsys.readouterr().out, table_label)
    assert "(none)" in row
    assert "FAIL: not extracted" in row
    assert "-860" not in row
    assert not re.search(r"\s0\s", row), row


@pytest.mark.parametrize(("key", "memo", "table_label", "cli_label", "page_label"), TOTALS)
def test_an_empty_printed_total_reaches_the_cli_as_not_extracted(
    key: str, memo: str, table_label: str, cli_label: str, page_label: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fin, _ = parse([year(2023), year(2024)], balance(**{key: []}))
    capsys.readouterr()
    cli.print_extracted_financials(fin)
    row = cli_check_line(capsys.readouterr().out, cli_label)
    # printed "not extracted"; mapped 860 (by hand); no difference; FAIL.
    assert re.search(r"printed\s+not extracted\s+mapped\s+860\s+diff\s+FAIL: not extracted$",
                     row), row
    assert "-860" not in row


def test_empty_gross_profit_and_operating_income_skip_their_checks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Round 2 decision 2, and the P11a assignment for gross profit: `[]` means the
    filing prints no such row. The check is skipped and says "not printed". Had
    `[]` been read as a printed 0, both checks would FAIL by 600 and 300."""
    fin, errors = parse([year(gross_profit=[], operating_income=[])])
    assert errors == []
    out = capsys.readouterr().out
    for label in ("Gross Profit", "Oper. Income"):
        row = table_line(out, label)
        assert "SKIP" in row and "not printed" in row, row
    # Net income is still checked: 228 against 228 (by hand above).
    assert table_line(out, "Net Income").rstrip().endswith("OK")
    # The derived figures stand: gross profit 1000 - 400 = 600, EBIT 300.
    assert fin.income_statements[0].gross_profit == 600.0
    assert fin.income_statements[0].ebit == 300.0


def test_an_empty_net_income_stops_route_a_naming_year_and_field() -> None:
    """Round 2 decision 3: `[]` on net_income stops; no 0 reaches the cash flow."""
    with pytest.raises(Pass1ShapeError) as excinfo:
        parse([year(2024, net_income=[])])
    assert any("year 2024" in p and "'net_income'" in p for p in excinfo.value.problems), (
        excinfo.value.problems)


def test_an_empty_net_income_stops_route_b_naming_file_filing_year_and_field(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = make_pdf(tmp_path)
    data = session_dict(pdf)
    data["filings"][0]["pass1"]["historical_years"][1]["net_income"] = []  # year 2024
    path = write_session(tmp_path, data)
    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)
    assert any(
        all(part in line for part in (str(path), "filings[0]", pdf.name, "year 2024",
                                      "'net_income'"))
        for line in str(excinfo.value).splitlines()
    ), str(excinfo.value)
    # `check` stops on it: exit 2, not 1 (a failed check) and not 0.
    assert cmd_check(path) == 2
    assert "'net_income'" in capsys.readouterr().out


# ===========================================================================
# 4. The balance check
# ===========================================================================

def test_printed_totals_that_agree_pass(capsys: pytest.CaptureFixture[str]) -> None:
    fin, errors = parse([year()], balance())
    assert errors == []
    out = capsys.readouterr().out
    # 860 printed, 860 mapped, difference +0, both sides (by hand).
    assert re.search(r"Total Assets\s+860\s+860\s+\+0\s+OK$", table_line(out, "Total Assets"))
    assert re.search(r"Total L \+ E\s+860\s+860\s+\+0\s+OK$", table_line(out, "Total L + E"))
    assert fin.balance_sheets[0].printed_total_assets_difference == 0.0


def test_a_row_of_4124_kept_balances() -> None:
    # Control for the next test: with the row, 4,984 against 4,984 (by hand above).
    _, errors = parse([year()], balance(**WITH_ROW))
    assert errors == []


def test_a_dropped_row_of_4124_fails_names_the_difference_and_keeps_the_figures(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fin, errors = parse([year()], balance(**DROPPED_ROW))
    (bs,) = fin.balance_sheets
    # Only the assets side fails; L + E is 575 + 4,409 = 4,984, as printed.
    assert len(errors) == 1
    assert "total_assets" in errors[0]
    # The difference, named: 4,984 - 860 = +4,124.
    assert "+4,124" in errors[0]
    # Kept, never repaired: the row as read, the mapped sum, the printed total.
    assert bs.other_current_assets == 10.0
    assert bs.total_assets == 860.0
    assert bs.printed_total_assets == 4984.0
    assert bs.printed_total_assets_difference == 4124.0
    row = table_line(capsys.readouterr().out, "Total Assets")
    assert re.search(r"4,984\s+860\s+\+4,124\s+FAIL$", row), row


def test_the_tolerance_is_the_one_the_code_applies() -> None:
    # Read from the code, not retyped (P11a-tests, "What to do" 4).
    tol = BalanceSheet.printed_total_tolerance()
    assert BalanceSheet.printed_total_check(tol) == "OK"
    assert BalanceSheet.printed_total_check(-tol) == "OK"
    assert BalanceSheet.printed_total_check(tol + 1) == "FAIL"
    assert BalanceSheet.printed_total_check(-(tol + 1)) == "FAIL"


@pytest.mark.parametrize(
    ("over", "fails"),
    [(0, False), (1, True)],
    ids=["exactly the tolerance passes", "one more fails"],
)
@pytest.mark.parametrize("sign", [1, -1], ids=["printed above", "printed below"])
def test_a_difference_of_the_tolerance_passes_and_one_more_fails(
    over: int, fails: bool, sign: int,
) -> None:
    # printed total_assets = 860 +/- (tolerance + over); mapped stays 860, so the
    # difference is exactly +/-(tolerance + over).
    tol = BalanceSheet.printed_total_tolerance()
    printed = 860 + sign * (tol + over)
    _, errors = parse([year()], balance(total_assets=[printed]))
    assert bool(errors) is fails, errors


# ===========================================================================
# 5. Route A's retries, with _call_llm stubbed
# ===========================================================================

_RESOLUTION = ProviderResolution(
    provider="claude", model="stub-model", transport="anthropic-direct",
    transport_label="stub", credential="anthropic-api-key",
    credential_source="stub: no call is made",
)


def run_route_a(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, answers: list[str],
) -> tuple[list[tuple[str, bytes | None]], Any, bytes]:
    """Run route A's Pass 1 on scripted answers, one per call, in order.

    Returns the calls as (user prompt, PDF bytes sent), the outcome (the
    statements, or the exception raised), and the PDF bytes. A call beyond the
    script raises.
    """
    pdf = tmp_path / "TST_10-K_2024.pdf"
    pdf.write_bytes(b"%PDF-1.4 stand-in bytes for the P11a retry tests\n")
    pdf_bytes = pdf.read_bytes()
    calls: list[tuple[str, bytes | None]] = []

    def stub(system_prompt: str, user_prompt: str, resolution: ProviderResolution,
             pdf_bytes: bytes | None = None) -> tuple[str, int, int]:
        if len(calls) >= len(answers):
            raise AssertionError(f"call {len(calls) + 1} was not scripted: {user_prompt[:80]!r}")
        calls.append((user_prompt, pdf_bytes))
        # Token counts 10 in, 5 out: invented, so the console line that reports
        # them can be checked against the stub's own numbers.
        return answers[len(calls) - 1], 10, 5

    monkeypatch.setattr(ce, "_call_llm", stub)
    try:
        outcome: Any = ce._run_financials_pass(
            pdf_bytes, TICKER, COMPANY, _RESOLUTION, target_years=None, include_bs=True,
        )
    except ValueError as exc:
        outcome = exc
    return calls, outcome, pdf_bytes


GOOD = answer([year()], balance())
MISSING_SBC = answer([{k: v for k, v in year().items() if k != "sbc"}], balance())
DROPPED = answer([year()], balance(**DROPPED_ROW))
NOT_JSON = '{"historical_years": [}'


def test_the_shape_retry_sends_the_pdf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    calls, outcome, pdf = run_route_a(monkeypatch, tmp_path, [MISSING_SBC, GOOD])
    assert len(calls) == 2
    assert calls[0][1] == pdf
    assert calls[1][1] == pdf
    assert "'sbc'" in calls[1][0]
    # The second answer is used: sbc 25 (input).
    assert outcome.get_cash_flow(2024).stock_based_compensation == 25.0
    # A full-PDF retry is labelled with its cost: the stub's 10 in and 5 out.
    assert "Retry tokens — input: 10  output: 5" in capsys.readouterr().out


def test_the_check_retry_sends_the_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls, outcome, pdf = run_route_a(monkeypatch, tmp_path, [DROPPED, GOOD])
    assert len(calls) == 2
    assert calls[1][1] == pdf
    assert outcome.get_balance_sheet(2024).total_assets == 860.0


def test_the_json_repair_retry_does_not_send_the_pdf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls, outcome, pdf = run_route_a(monkeypatch, tmp_path, [NOT_JSON, GOOD])
    assert len(calls) == 2
    assert calls[0][1] == pdf
    assert calls[1][1] is None
    assert isinstance(outcome, FinancialStatements)


def _retry_text(prompt: str, previous_answer: str) -> str:
    """The retry prompt without the JSON it carries back (decision 6 accepts that
    the JSON holds the values; it is the wording around it that must not)."""
    assert prompt.endswith(previous_answer), "the retry no longer ends with the answer"
    return prompt[: -len(previous_answer)]


def test_the_balance_check_retry_states_no_gap_and_no_total(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls, _, _ = run_route_a(monkeypatch, tmp_path, [DROPPED, GOOD])
    text = _retry_text(calls[1][0], DROPPED)
    # It names the failing total and its side (round 2 decision 6)...
    assert "total_assets" in text
    assert "assets side" in text
    # ...and states no amount: not the gap 4,124, not the printed total 4,984,
    # not the mapped sum 860 (by hand above), in any spelling.
    for amount in ("4,124", "4124", "4,984", "4984", "860"):
        assert amount not in text, f"the retry text states {amount}: {text}"


def test_the_income_statement_check_retry_states_no_gap_and_no_total(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # operating income printed 1,200 against 1000 - 400 - 150 - 100 - 50 = 300:
    # a gap of 900, over 0.5%. Net income is checked against the components, not
    # against operating income, so it alone fails.
    wrong = answer([year(operating_income=[1200])], balance())
    calls, _, _ = run_route_a(monkeypatch, tmp_path, [wrong, GOOD])
    text = _retry_text(calls[1][0], wrong)
    assert "operating_income" in text
    for amount in ("900", "1,200", "1200", "300"):
        assert amount not in text, f"the retry text states {amount}: {text}"


def test_after_the_last_retry_an_absent_key_stops(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls, outcome, pdf = run_route_a(monkeypatch, tmp_path, [MISSING_SBC] * 3)
    # The first call and two retries (MAX_RETRIES in _run_financials_pass), each
    # with the PDF; then the stop, naming the year and the key.
    assert len(calls) == 3
    assert all(sent == pdf for _, sent in calls)
    assert isinstance(outcome, Pass1ShapeError)
    assert any("year 2024" in p and "'sbc'" in p for p in outcome.problems)


def test_after_the_last_retry_malformed_json_stops(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls, outcome, _ = run_route_a(monkeypatch, tmp_path, [NOT_JSON] * 3)
    assert len(calls) == 3
    # A stop (json.JSONDecodeError is a ValueError), never statements.
    assert isinstance(outcome, json.JSONDecodeError)


def test_after_the_last_retry_an_empty_net_income_stops(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    empty_ni = answer([year(net_income=[])], balance())
    calls, outcome, _ = run_route_a(monkeypatch, tmp_path, [empty_ni] * 3)
    assert len(calls) == 3
    # A stop, not statements: no 0 can reach CashFlowStatement.net_income.
    assert isinstance(outcome, Pass1ShapeError)
    assert any("year 2024" in p and "'net_income'" in p for p in outcome.problems)


def test_after_the_last_retry_a_failed_check_is_kept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls, outcome, _ = run_route_a(monkeypatch, tmp_path, [DROPPED] * 3)
    assert len(calls) == 3
    # Shown and kept, as read: the figures of the dropped-row answer (by hand above).
    bs = outcome.get_balance_sheet(2024)
    assert bs.other_current_assets == 10.0
    assert bs.total_assets == 860.0
    assert bs.printed_total_assets == 4984.0


# ===========================================================================
# 6. The stops: each names the field, the year and the line index
# ===========================================================================
#
# capex is given two rows, 40 + 30 = 70 (the base figure), and row 1 is broken,
# so "line 1" can only have come from the row, not from a default index of 0.

_DEL = object()

LINE_STOPS = [
    pytest.param("label", _DEL, id="label absent"),
    pytest.param("value", _DEL, id="value absent"),
    pytest.param("page", _DEL, id="page absent"),
    pytest.param("label", "", id="label empty"),
    pytest.param("label", "   ", id="label blank"),
    pytest.param("label", 5, id="label not a string"),
    pytest.param("value", float("nan"), id="value NaN"),
    pytest.param("value", float("inf"), id="value infinite"),
    pytest.param("value", float("-inf"), id="value minus infinite"),
    pytest.param("value", 10 ** 400, id="value too large for a float"),
    pytest.param("value", "40", id="value a string"),
    pytest.param("value", True, id="value a bool"),
    pytest.param("value", None, id="value null"),
    pytest.param("page", 1.5, id="page a fraction"),
    pytest.param("page", "52", id="page a string"),
    pytest.param("page", 0, id="page 0"),
    pytest.param("page", -1, id="page negative"),
    pytest.param("page", True, id="page a bool"),
    pytest.param("page", None, id="page null"),
]


def _break_row(rows: list[dict[str, Any]], key: str, value: Any) -> None:
    if value is _DEL:
        del rows[1][key]
    else:
        rows[1][key] = value


@pytest.mark.parametrize(("key", "value"), LINE_STOPS)
def test_a_malformed_line_stops_route_a_naming_field_year_and_line(
    key: str, value: Any,
) -> None:
    entry = year(2024, capex=[40, 30])
    _break_row(entry["capex"], key, value)
    with pytest.raises(Pass1ShapeError) as excinfo:
        parse([entry])
    assert any(
        all(part in p for part in ("year 2024", "'capex'", "line 1", f"'{key}'"))
        for p in excinfo.value.problems
    ), excinfo.value.problems


@pytest.mark.parametrize(("key", "value"), LINE_STOPS)
def test_a_malformed_line_stops_route_b_naming_file_filing_field_year_and_line(
    tmp_path: Path, key: str, value: Any,
) -> None:
    pdf = make_pdf(tmp_path)
    data = session_dict(pdf)
    # The session's 2024 capex is 70 * 2 = 140; written as rows 100 and 40.
    rows = lines("capex", [100, 40])
    _break_row(rows, key, value)
    data["filings"][0]["pass1"]["historical_years"][1]["capex"] = rows
    path = write_session(tmp_path, data)
    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)
    parts = (str(path), "filings[0]", pdf.name, "year 2024", "'capex'", "line 1", f"'{key}'")
    assert any(all(part in line for part in parts)
               for line in str(excinfo.value).splitlines()), str(excinfo.value)


@pytest.mark.parametrize("not_an_object", [30, "30", None, [30]],
                         ids=["number", "string", "null", "list"])
def test_a_line_that_is_not_an_object_stops_naming_field_year_and_line(
    not_an_object: Any,
) -> None:
    entry = year(2024, capex=[40, 30])
    entry["capex"][1] = not_an_object
    with pytest.raises(Pass1ShapeError) as excinfo:
        parse([entry])
    assert any(
        all(part in p for part in ("year 2024", "'capex'", "line 1", "JSON object"))
        for p in excinfo.value.problems
    ), excinfo.value.problems


def test_figure_from_printed_lines_itself_stops_on_a_malformed_line() -> None:
    # The one function that forms a figure refuses a bad line on its own, not only
    # behind pass1_problems: field, where, and line index named.
    rows = lines("capex", [40, 30])
    del rows[1]["page"]
    with pytest.raises(Pass1ShapeError) as excinfo:
        figure_from_printed_lines(rows, "capex", "year 2024")
    assert any(all(part in p for part in ("year 2024", "'capex'", "line 1", "'page'"))
               for p in excinfo.value.problems), excinfo.value.problems


@pytest.mark.parametrize("not_an_object", ["[]", "7", '"text"'])
def test_a_pass1_answer_that_is_not_an_object_stops(not_an_object: str) -> None:
    with pytest.raises(Pass1ShapeError, match="JSON object"):
        parse_pass1(not_an_object, TICKER, COMPANY)


def test_a_malformed_balance_sheet_line_names_the_balance_sheet_year() -> None:
    bs = balance()
    bs["cash"][0]["page"] = 0
    with pytest.raises(Pass1ShapeError) as excinfo:
        parse([year()], bs)
    assert any(
        all(part in p for part in ("balance sheet 2024", "'cash'", "line 0", "'page'"))
        for p in excinfo.value.problems
    ), excinfo.value.problems


@pytest.mark.parametrize("key", [k for k in _BASE_YEAR])
def test_an_absent_year_key_stops_route_a_naming_year_and_field(key: str) -> None:
    entry = year(2024)
    del entry[key]
    with pytest.raises(Pass1ShapeError) as excinfo:
        parse([entry])
    assert any("year 2024" in p and f"'{key}'" in p and "absent" in p
               for p in excinfo.value.problems), excinfo.value.problems


@pytest.mark.parametrize("key", [k for k in _BASE_BALANCE_SHEET])
def test_an_absent_balance_sheet_key_stops_route_a_naming_year_and_field(key: str) -> None:
    bs = balance()
    del bs[key]
    with pytest.raises(Pass1ShapeError) as excinfo:
        parse([year()], bs)
    assert any("balance sheet 2024" in p and f"'{key}'" in p and "absent" in p
               for p in excinfo.value.problems), excinfo.value.problems


# ===========================================================================
# 7. The formats
# ===========================================================================

def test_a_v1_session_file_stops_naming_both_formats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    # The two format names, from the P11a assignment, step 4.
    data = session_dict(make_pdf(tmp_path)) | {"format": "session-extraction-v1"}
    path = write_session(tmp_path, data)
    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)
    message = str(excinfo.value)
    assert str(path) in message
    assert "'session-extraction-v1'" in message
    assert "'session-extraction-v2'" in message
    # Step 4 also says the message tells the reader to extract the filing again:
    # the generic "unknown format" stop would name both formats but not this.
    assert re.search(r"extract the filing again", message, re.IGNORECASE), message
    assert cmd_check(path) == 2
    capsys.readouterr()


def _cache_payload(marker: str) -> tuple[Any, ...]:
    fin, _ = parse([year()], balance())
    key = cli.ExtractionKey(ticker=TICKER, provider="claude", model="stub-model", inputs=())
    return (marker, key, fin, [])


def test_a_cli_cache_under_the_old_marker_is_refused(tmp_path: Path) -> None:
    # "p6-inputs-keyed-v1": the marker before P11a (P11a assignment, "What is
    # already true"); step 7 changes it, so an old-shape cache is refused.
    old = tmp_path / "old.pkl"
    old.write_bytes(pickle.dumps(_cache_payload("p6-inputs-keyed-v1")))
    assert cli.CACHE_FORMAT != "p6-inputs-keyed-v1"
    with pytest.raises(ValueError, match="not a cache entry written by this CLI") as excinfo:
        cli._load_cache(old)
    assert repr(cli.CACHE_FORMAT) in str(excinfo.value)


def test_a_cli_cache_under_the_current_marker_loads(tmp_path: Path) -> None:
    # Control for the refusal above: the same payload under the current marker
    # reads back (identity: what was written is what is read).
    payload = _cache_payload(cli.CACHE_FORMAT)
    current = tmp_path / "current.pkl"
    current.write_bytes(pickle.dumps(payload))
    key, fin, items = cli._load_cache(current)
    assert key == payload[1]
    assert fin == payload[2]
    assert items == []


# ===========================================================================
# 8. The outputs: the CLI balance check, and the statements page
# ===========================================================================

def _cli_balance_rows(fin: FinancialStatements, capsys: pytest.CaptureFixture[str]) -> tuple[
    str, str, str,
]:
    capsys.readouterr()
    cli.print_extracted_financials(fin)
    out = capsys.readouterr().out
    header = table_line(out, "Balance check")
    return header, cli_check_line(out, "Total Assets"), cli_check_line(out, "Total Liab + Equity")


def test_the_cli_session_route_shows_a_failed_check_and_keeps_the_figures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    # The session helper's 860 sheet with the 4,124 row dropped (by hand above):
    # other_current_assets 10, equity 4,409, printed totals 4,984 and 4,984.
    data = session_dict(make_pdf(tmp_path))
    data["filings"][0]["pass1"]["latest_balance_sheet"] |= {
        field: lines(field, values, balance_sheet=True) for field, values in DROPPED_ROW.items()
    }
    path = write_session(tmp_path, data)
    args = argparse.Namespace(session_file=str(path), ticker=None, company_name=None)
    fin, _, _, _ = cli._extract_from_session_file(args)
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    # Under the [FAIL] notice (not the parser's table above it): the failed check,
    # naming the total and the gap 4,984 - 860 = +4,124, kept in the human wording.
    shown = out.split("[FAIL]", 1)[1].splitlines()
    assert any("total_assets" in line and "+4,124" in line for line in shown), out
    bs = fin.get_balance_sheet(2024)
    assert (bs.other_current_assets, bs.total_assets, bs.printed_total_assets) == (
        10.0, 860.0, 4984.0)


def test_the_cli_balance_check_says_ok_when_the_totals_agree(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fin, _ = parse([year(2023), year(2024)], balance())
    header, assets, le = _cli_balance_rows(fin, capsys)
    tol = BalanceSheet.printed_total_tolerance()
    assert f"FAIL above {tol:,.0f}" in header
    assert re.search(r"printed\s+860\s+mapped\s+860\s+diff\s+\+0\s+OK$", assets), assets
    assert re.search(r"printed\s+860\s+mapped\s+860\s+diff\s+\+0\s+OK$", le), le


def test_the_cli_balance_check_says_fail_on_a_dropped_row(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fin, _ = parse([year(2023), year(2024)], balance(**DROPPED_ROW))
    _, assets, le = _cli_balance_rows(fin, capsys)
    # 4,984 printed, 860 mapped, +4,124 (by hand above); L + E 4,984 both ways.
    assert re.search(r"printed\s+4,984\s+mapped\s+860\s+diff\s+\+4,124\s+FAIL$", assets), assets
    assert re.search(r"printed\s+4,984\s+mapped\s+4,984\s+diff\s+\+0\s+OK$", le), le


def test_the_cli_balance_check_has_no_two_percent_tolerance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Printed 860 + tolerance + 1 against 860. With the default tolerance of the
    # code that is 862: 2 / 860 = 0.23%, well inside the 2% the CLI used to allow
    # (P11a assignment, cli.py:498), so the old check would have said OK.
    tol = BalanceSheet.printed_total_tolerance()
    printed = 860 + tol + 1
    assert (printed - 860) / 860 < 0.02
    fin, _ = parse([year(2023), year(2024)], balance(total_assets=[printed]))
    _, assets, _ = _cli_balance_rows(fin, capsys)
    assert assets.rstrip().endswith("FAIL"), assets


@pytest.fixture
def page_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """The statements page with every boundary closed, as test_statements_ui.py does:
    the extraction is replaced per test, and no price or model call is possible."""
    monkeypatch.setattr(routes_valuation, "_extraction_cache", {}, raising=False)
    for var in ("ANTHROPIC_FOUNDRY_BASE_URL", "ANTHROPIC_FOUNDRY_RESOURCE",
                "ANTHROPIC_FOUNDRY_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder-no-call-is-made")

    def _closed(*args: object, **kwargs: object) -> None:
        raise AssertionError("boundary reached")

    monkeypatch.setattr(routes_valuation, "extract_financials", _closed)
    monkeypatch.setattr(routes_valuation, "extract_multi_year", _closed)
    monkeypatch.setattr(routes_valuation, "fetch_price_data", _closed)
    return TestClient(app_module.app, raise_server_exceptions=False)


def _page_rows(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fin: FinancialStatements,
) -> tuple[str, dict[str, tuple[bool, list[str]]]]:
    """The balance check table's header, and per row (failed class?, cell texts)."""
    monkeypatch.setattr(routes_valuation, "_extract_from_files", lambda *a, **k: (fin, []))
    response = client.get(
        f"/assumptions?ticker={TICKER}&company_name=Test+Co&files="
        f"2023:t23.pdf,{FISCAL_YEAR}:t24.pdf",
    )
    assert response.status_code == 200
    body = response.text
    start = body.index("Balance Check (printed total")
    table = body[start: body.index("</table>", start)]
    header = strip_tags(table[: table.index("</th>")])
    rows: dict[str, tuple[bool, list[str]]] = {}
    for attrs, inner in re.findall(r"<tr([^>]*)>(.*?)</tr>", table, re.DOTALL):
        cells = [strip_tags(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", inner, re.DOTALL)]
        if cells:
            rows[cells[0]] = ("check-fail" in attrs, cells[1:])
    return header, rows


def test_the_page_shows_ok_when_the_totals_agree(
    page_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fin, _ = parse([year(2023), year(2024)], balance())
    header, rows = _page_rows(page_client, monkeypatch, fin)
    tol = BalanceSheet.printed_total_tolerance()
    assert f"FAIL above {tol:,.0f}" in header
    assert rows["Total Assets"] == (False, ["860", "860", "+0", "OK"])
    assert rows["Total Liabilities + Equity"] == (False, ["860", "860", "+0", "OK"])


def test_the_page_shows_fail_visibly_on_a_dropped_row(
    page_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fin, _ = parse([year(2023), year(2024)], balance(**DROPPED_ROW))
    _, rows = _page_rows(page_client, monkeypatch, fin)
    # 4,984 printed, 860 mapped, +4,124, FAIL, in the failed style (by hand above).
    assert rows["Total Assets"] == (True, ["4,984", "860", "+4,124", "FAIL"])
    assert rows["Total Liabilities + Equity"] == (False, ["4,984", "4,984", "+0", "OK"])


@pytest.mark.parametrize(("key", "memo", "table_label", "cli_label", "page_label"), TOTALS)
def test_the_page_shows_an_empty_total_as_not_extracted_never_zero(
    page_client: TestClient, monkeypatch: pytest.MonkeyPatch,
    key: str, memo: str, table_label: str, cli_label: str, page_label: str,
) -> None:
    fin, _ = parse([year(2023), year(2024)], balance(**{key: []}))
    _, rows = _page_rows(page_client, monkeypatch, fin)
    failed, cells = rows[page_label]
    assert failed
    # printed "not extracted", mapped 860 (by hand), no difference, FAIL.
    assert cells[0] == "not extracted"
    assert cells[1] == "860"
    assert cells[2] == "—"
    assert cells[3].startswith("FAIL")
    assert "not extracted" in cells[3]
