"""The CLI's `--confirm-zero-debt` flag. Backlog item 38b (a), `P13h-zero-debt-confirm`.

**The contract.** Step 3 of `.agent/assignments/P13h-zero-debt-confirm.md`: the
flag is `action="store_true"` in the "valuation overrides" group, and
`build_overrides` copies it into `ProjectionAssumptions.zero_debt_confirmed`.
`store_true` means present is True and absent is False, and a value attached to
the flag is a usage error (argparse's own contract for that action). Absent is
the state "the user confirmed nothing": it is not a substituted figure, and on
a company with zero debt beside interest expense it leads to item 22's stop,
which the last test here shows.

**Where the expected values come from.** The specification above and the
argparse documentation for `store_true`. The WACC figures in the last test are
hand arithmetic, written beside them. No expected value was read from a run.

**No network, no key, no PDF.** `parse_args` and `build_overrides` read
`sys.argv` and nothing else; `sys.argv` is patched. The `_no_socket` fixture
refuses every connection, so a test that reached out would fail rather than
wait. No file named on the patched command line is opened.
"""

from __future__ import annotations

import socket

import pytest

import cli
from analysis.wacc import calculate_wacc
from models.financial_statements import BalanceSheet, IncomeStatement
from models.valuation import CAPMResult


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refused(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a unit test opened a network connection: {args!r}")

    monkeypatch.setattr(socket.socket, "connect", _refused)
    monkeypatch.setattr(socket.socket, "connect_ex", _refused)
    monkeypatch.setattr(socket, "create_connection", _refused)


# Two command lines that parse without reading any file: the session-file form
# (the file is opened later, in `main`, not by `parse_args`) and the PDF form
# with an explicit ticker (so the directory check is not reached).
_COMMAND_LINES = [
    pytest.param(["cli.py", "--session-file", "p13h-never-opened.json"], id="session-file"),
    pytest.param(["cli.py", "p13h-never-opened.pdf", "-t", "TESTCO"], id="pdf"),
]


def _overrides(monkeypatch: pytest.MonkeyPatch, argv: list[str]):
    monkeypatch.setattr("sys.argv", argv)
    return cli.build_overrides(cli.parse_args())


@pytest.mark.parametrize("argv", _COMMAND_LINES)
def test_the_flag_sets_zero_debt_confirmed(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    overrides = _overrides(monkeypatch, [*argv, "--confirm-zero-debt"])
    assert overrides.zero_debt_confirmed is True


@pytest.mark.parametrize("argv", _COMMAND_LINES)
def test_without_the_flag_nothing_is_confirmed(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    overrides = _overrides(monkeypatch, argv)
    assert overrides.zero_debt_confirmed is False


def test_the_flag_takes_no_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """`store_true` refuses an attached value, so `--confirm-zero-debt=no`
    cannot be read as either answer. argparse exits with status 2 (usage).
    """
    monkeypatch.setattr(
        "sys.argv", ["cli.py", "--session-file", "p13h-never-opened.json", "--confirm-zero-debt=no"]
    )
    with pytest.raises(SystemExit) as raised:
        cli.parse_args()
    assert raised.value.code == 2


def test_help_lists_the_flag(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["cli.py", "--help"])
    with pytest.raises(SystemExit) as raised:
        cli.parse_args()
    assert raised.value.code == 0
    assert "--confirm-zero-debt" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# From the command line to the WACC, on a company with total debt 0 and
# interest expense 30. `main` passes `overrides.zero_debt_confirmed` to
# `calculate_wacc`; this test makes the same call with the parsed value.
#
#   Re   = 0.04 + 1.0 * 0.06               = 0.10
#   E    = 300, D = 0, V = 300
#   E/V  = 300 / 300 = 1.0, D/V = 0 / 300  = 0.0
#   WACC = 1.0 * 0.10 + 0.0 * Rd * (1 - t) = 0.10 = Re
# ---------------------------------------------------------------------------


def _wacc_from_command_line(monkeypatch: pytest.MonkeyPatch, argv: list[str]):
    overrides = _overrides(monkeypatch, argv)
    return calculate_wacc(
        capm_result=CAPMResult(beta=1.0, risk_free_rate=0.04, equity_risk_premium=0.06),
        income_statement=IncomeStatement(
            year=2025, revenue=1000.0, cost_of_revenue=600.0, interest_expense=30.0, tax_expense=80.0
        ),
        balance_sheet=BalanceSheet(year=2025, printed_unit_in_millions=1.0),
        market_cap=300.0,
        cost_of_debt_override=overrides.cost_of_debt_override,
        tax_rate_override=0.25,
        zero_debt_confirmed=overrides.zero_debt_confirmed,
    )


def test_the_flag_values_a_repaid_company_with_no_debt(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _wacc_from_command_line(
        monkeypatch, ["cli.py", "--session-file", "p13h-never-opened.json", "--confirm-zero-debt"]
    )
    assert result.equity_weight == 1.0
    assert result.debt_weight == 0.0
    assert result.wacc == result.cost_of_equity
    assert result.wacc == pytest.approx(0.10)


@pytest.mark.parametrize(
    "extra",
    [pytest.param([], id="no-override"), pytest.param(["--cost-of-debt", "0.05"], id="cost-of-debt")],
)
def test_without_the_flag_a_repaid_company_stops_even_with_a_cost_of_debt(
    monkeypatch: pytest.MonkeyPatch, extra: list[str]
) -> None:
    """Item 22's stop, and `--cost-of-debt` does not get past it (item 38b (a))."""
    with pytest.raises(ValueError, match="--confirm-zero-debt"):
        _wacc_from_command_line(
            monkeypatch, ["cli.py", "--session-file", "p13h-never-opened.json", *extra]
        )


# ---------------------------------------------------------------------------
# Stage 8 of `main`: the parsed flag is the one `calculate_wacc` receives.
#
# `main` is run with its three boundaries replaced: the session-file reader
# returns hand-built statements, the price fetch returns hand-built market
# data, and `calculate_wacc` is a spy that records its keyword and stops the
# run. Nothing after stage 8 runs, so no figure is asserted here: the subject
# is the hand-off, and the WACC itself is locked above and in `test_wacc.py`.
# ---------------------------------------------------------------------------


class _StoppedAtStage8(Exception):
    pass


def _run_main_to_stage_8(monkeypatch: pytest.MonkeyPatch, extra: list[str]) -> list:
    import numpy as np
    import pandas as pd

    from ingestion.price_fetcher import PriceData
    from models.financial_statements import CashFlowStatement, FinancialStatements

    financials = FinancialStatements(
        ticker="TESTCO",
        company_name="Test Company Inc",
        income_statements=[
            IncomeStatement(year=2023, revenue=1000.0, sga=800.0, tax_expense=50.0,
                            interest_expense=30.0, diluted_shares_outstanding=100.0),
            IncomeStatement(year=2024, revenue=1200.0, sga=960.0, tax_expense=60.0,
                            interest_expense=30.0, diluted_shares_outstanding=100.0),
        ],
        balance_sheets=[
            BalanceSheet(year=2024, cash_and_equivalents=100.0,
                         noncontrolling_interest_nonredeemable=0.0,
                         noncontrolling_interest_redeemable=0.0,
                         printed_unit_in_millions=1.0),
        ],
        cash_flow_statements=[
            CashFlowStatement(year=2023, depreciation_amortization=100.0,
                              capital_expenditures=-50.0, change_in_working_capital=-20.0),
            CashFlowStatement(year=2024, depreciation_amortization=120.0,
                              capital_expenditures=-60.0, change_in_working_capital=-24.0),
        ],
    )
    price = PriceData(
        ticker="TESTCO",
        stock_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float),
        dates=pd.DatetimeIndex(pd.date_range("2024-01-31", periods=3, freq="D")),
        current_price=45.0,
        periods_per_year=12,
    )

    def _closed(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a unit test reached a boundary it did not fake: {args!r}")

    received: list = []

    def spy(*args: object, **kwargs: object) -> None:
        received.append(kwargs.get("zero_debt_confirmed", "<not passed>"))
        raise _StoppedAtStage8

    monkeypatch.setattr(cli, "_extract_from_session_file",
                        lambda args: (financials, [], "hand-built", "hand-built"))
    monkeypatch.setattr(cli, "_extract_via_api", _closed)
    monkeypatch.setattr(cli, "fetch_price_data", lambda *a, **k: price)
    monkeypatch.setattr(cli, "calculate_wacc", spy)
    monkeypatch.setattr(
        "sys.argv",
        ["cli.py", "--session-file", "p13h-never-opened.json", "--beta", "1.0",
         "--risk-free-rate", "0.04", "--equity-risk-premium", "0.06", *extra],
    )
    with pytest.raises(_StoppedAtStage8):
        cli.main()
    return received


@pytest.mark.parametrize(
    ("extra", "expected"),
    [pytest.param(["--confirm-zero-debt"], True, id="flag"), pytest.param([], False, id="no-flag")],
)
def test_main_hands_the_flag_to_calculate_wacc(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], extra: list[str], expected: bool
) -> None:
    assert _run_main_to_stage_8(monkeypatch, extra) == [expected]
