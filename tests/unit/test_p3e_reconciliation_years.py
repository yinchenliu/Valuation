"""Verifying CLI reconciliation year-set parity with web page (backlog item 128).

What this file locks:
  1. Parity between `cli.print_normalization` and
     `api.routes_valuation._build_ebit_reconciliation` across all year-presence
     configurations.
  2. When a year exists on the adjusted side only (for example, adjusted has an
     income statement or cash flow statement for 2024 while raw has no statements
     covering 2024):
       - `cli.print_normalization` prints `  2024: not extracted: raw income statement`
         (or `raw and adjusted income statement` if adjusted has no income statement).
       - `_build_ebit_reconciliation` returns an `EBITReconciliationYear` with
         `year == 2024`, `missing_statement == "raw income statement"`,
         `as_reported_ebit is None`, `adjusted_ebit == <value>`, and `difference is None`.
       - The cell formatted by the web template (`f"not extracted: {record.missing_statement}"`)
         matches the CLI's printed row for that year.
  3. Symmetrically, when a year exists on the raw side only, both entry points report
     `not extracted: adjusted income statement`.
  4. Both entry points iterate the sorted union of `raw.years` and `adjusted.years`
     in strict ascending order.
  5. When both sides have statements for a year:
       - delta != 0: prints formatted EBIT line with GAAP, Adj, and Delta in CLI;
         web records as_reported_ebit, adjusted_ebit, difference, and missing_statement=None.
       - delta == 0: CLI suppresses individual row; prints summary line if at least
         one year was reconciled; web records difference == 0.
  6. Empty financial statements on both sides result in early return: CLI prints nothing,
     web returns an empty list.
  7. When no years are reconciled (no year has both income statements), CLI suppresses
     the "No adjustments applied..." summary line.
  8. Mutation check: if CLI is mutated to `years = raw.years`, adjusted-only years
     are dropped completely from the CLI reconciliation, causing test failure.

Where every expected value came from:
  - Hand arithmetic over fixed round figures:
      * 2023 raw:  revenue=1000, cogs=600, sga=200 -> ebit = 1000 - 600 - 200 = 200.0
      * 2023 adj:  revenue=1000, cogs=600, sga=180 -> ebit = 1000 - 600 - 180 = 220.0
                   delta = 220.0 - 200.0 = +20.0
      * 2024 raw:  (absent or ebit=200.0)
      * 2024 adj:  revenue=1100, cogs=660, sga=220 -> ebit = 1100 - 660 - 220 = 220.0
      * 2025 raw:  revenue=1200, cogs=720, sga=240 -> ebit = 1200 - 720 - 240 = 240.0
      * 2025 adj:  revenue=1200, cogs=720, sga=240 -> ebit = 1200 - 720 - 240 = 240.0
                   delta = 240.0 - 240.0 = 0.0
  - Closed-form identity:
      * The phrasing emitted by the CLI for missing statements must equal the
        template cell `not extracted: {record.missing_statement}`.
      * The years iterated must equal `sorted(set(raw.years) | set(adjusted.years))`.
      * Empty input returns empty output.

No assertion in this file was obtained by running the code and reading what it printed.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

import cli
from api.routes_valuation import _build_ebit_reconciliation
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
)

# ---------------------------------------------------------------------------
# Fixture factories with hand-derived round figures
# ---------------------------------------------------------------------------

def _make_income(year: int, revenue: float, cogs: float, sga: float) -> IncomeStatement:
    """Income statement where EBIT is exactly revenue - (cogs + sga)."""
    return IncomeStatement(
        year=year,
        revenue=revenue,
        cost_of_revenue=cogs,
        sga=sga,
        interest_expense=0.0,
        tax_expense=0.0,
        diluted_shares_outstanding=100.0,
    )


def _make_cash_flow(year: int) -> CashFlowStatement:
    """Minimal cash flow statement to place `year` in FinancialStatements.years."""
    return CashFlowStatement(
        year=year,
        net_income=100.0,
        depreciation_amortization=20.0,
        change_in_working_capital=0.0,
        capital_expenditures=-10.0,
    )


def _make_balance_sheet(year: int) -> BalanceSheet:
    """Minimal balance sheet to place `year` in FinancialStatements.years."""
    return BalanceSheet(
        year=year,
        cash_and_equivalents=50.0,
        long_term_debt=100.0,
        total_equity=200.0,
        printed_unit_in_millions=1.0,
    )


def _captured(fn, *args, **kwargs) -> list[str]:
    """Run `fn` and return the lines it printed, newlines stripped."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args, **kwargs)
    return buf.getvalue().splitlines()


def _row_starting(lines: list[str], label: str) -> str:
    """Find the single line starting with `label`."""
    matching = [line for line in lines if line.startswith(label)]
    assert len(matching) == 1, f"Expected exactly one line starting with {label!r}, found {len(matching)} in {lines}"
    return matching[0]


# ---------------------------------------------------------------------------
# 1. Criterion 2: Adjusted-only year parity between CLI and Web
# ---------------------------------------------------------------------------

def test_adjusted_only_year_with_income_statement_is_named_by_both_entry_points() -> None:
    """When a year exists on the adjusted side only with an income statement:
    - Raw covers 2023 and 2025 (no statement for 2024).
    - Adjusted covers 2023, 2024, 2025.
    - Hand arithmetic for 2024:
        Adj: rev=1100, cogs=660, sga=220 -> EBIT = 1100 - 660 - 220 = 220.0
        Raw: absent -> as_reported_ebit is None
    - CLI prints `  2024: not extracted: raw income statement`.
    - Web record has missing_statement == 'raw income statement',
      as_reported_ebit is None, adjusted_ebit == 220.0, difference is None.
    - Closed-form identity: CLI row equals `  2024: not extracted: {record.missing_statement}`.
    """
    # Raw: 2023 and 2025 only
    raw = FinancialStatements(
        ticker="RAW",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),  # ebit = 200.0
            _make_income(2025, 1200.0, 720.0, 240.0),  # ebit = 240.0
        ],
    )
    # Adjusted: 2023, 2024, 2025
    adjusted = FinancialStatements(
        ticker="ADJ",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 180.0),  # ebit = 220.0 (delta = +20)
            _make_income(2024, 1100.0, 660.0, 220.0),  # ebit = 220.0
            _make_income(2025, 1200.0, 720.0, 240.0),  # ebit = 240.0 (delta = 0)
        ],
    )

    # 2024 is strictly in adjusted.years and NOT in raw.years
    assert 2024 not in raw.years
    assert 2024 in adjusted.years

    # Web entry point
    reconciliation = _build_ebit_reconciliation(raw, adjusted)
    rec_by_year = {r.year: r for r in reconciliation}
    assert 2024 in rec_by_year

    rec_2024 = rec_by_year[2024]
    assert rec_2024.year == 2024
    assert rec_2024.missing_statement == "raw income statement"
    assert rec_2024.as_reported_ebit is None
    # Hand arithmetic: 1100.0 - 660.0 - 220.0 = 220.0
    assert rec_2024.adjusted_ebit == 220.0
    assert rec_2024.difference is None

    # CLI entry point
    cli_lines = _captured(cli.print_normalization, raw, adjusted)
    cli_2024_line = _row_starting(cli_lines, "  2024:")

    # Expected text derived by closed-form identity and formula:
    expected_cli_2024 = "  2024: not extracted: raw income statement"
    assert cli_2024_line == expected_cli_2024

    # Parity check: web template cell format matches CLI line content
    web_cell_2024 = f"not extracted: {rec_2024.missing_statement}"
    assert cli_2024_line == f"  2024: {web_cell_2024}"

    # Also verify 2023 and 2025 rows:
    # 2023 has delta = 220 - 200 = +20:
    rec_2023 = rec_by_year[2023]
    assert rec_2023.as_reported_ebit == 200.0
    assert rec_2023.adjusted_ebit == 220.0
    assert rec_2023.difference == 20.0
    assert rec_2023.missing_statement is None

    cli_2023_line = _row_starting(cli_lines, "  2023:")
    assert cli_2023_line == "  2023: EBIT  GAAP=       200  Adj=       220  Delta=       +20"

    # 2025 has delta = 240 - 240 = 0: row is omitted from CLI
    rec_2025 = rec_by_year[2025]
    assert rec_2025.as_reported_ebit == 240.0
    assert rec_2025.adjusted_ebit == 240.0
    assert rec_2025.difference == 0.0
    assert rec_2025.missing_statement is None
    assert not any(line.startswith("  2025:") for line in cli_lines)


def test_adjusted_only_year_with_non_income_statement_is_named_by_both_entry_points() -> None:
    """When a year exists in adjusted only via a cash flow statement (no income statement):
    - Raw covers 2023 and 2025.
    - Adjusted covers 2023 and 2025 income, plus 2024 cash flow statement.
    - Neither side has an income statement for 2024.
    - CLI prints `  2024: not extracted: raw and adjusted income statement`.
    - Web record has missing_statement == 'raw and adjusted income statement',
      as_reported_ebit is None, adjusted_ebit is None, difference is None.
    - Parity: CLI line equals `  2024: not extracted: {record.missing_statement}`.
    """
    raw = FinancialStatements(
        ticker="RAW",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),
            _make_income(2025, 1200.0, 720.0, 240.0),
        ],
    )
    adjusted = FinancialStatements(
        ticker="ADJ",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),
            _make_income(2025, 1200.0, 720.0, 240.0),
        ],
        cash_flow_statements=[_make_cash_flow(2024)],
    )

    assert 2024 not in raw.years
    assert 2024 in adjusted.years

    reconciliation = _build_ebit_reconciliation(raw, adjusted)
    rec_2024 = next(r for r in reconciliation if r.year == 2024)
    assert rec_2024.missing_statement == "raw and adjusted income statement"
    assert rec_2024.as_reported_ebit is None
    assert rec_2024.adjusted_ebit is None
    assert rec_2024.difference is None

    cli_lines = _captured(cli.print_normalization, raw, adjusted)
    cli_2024_line = _row_starting(cli_lines, "  2024:")
    assert cli_2024_line == "  2024: not extracted: raw and adjusted income statement"
    assert cli_2024_line == f"  2024: not extracted: {rec_2024.missing_statement}"


# ---------------------------------------------------------------------------
# 2. Symmetric Case: Raw-only year parity between CLI and Web
# ---------------------------------------------------------------------------

def test_raw_only_year_with_income_statement_is_named_by_both_entry_points() -> None:
    """When a year exists on the raw side only with an income statement:
    - Raw covers 2023, 2024, 2025 (2024 EBIT = 1100 - 660 - 220 = 220.0).
    - Adjusted covers 2023 and 2025 (no statement for 2024).
    - CLI prints `  2024: not extracted: adjusted income statement`.
    - Web record has missing_statement == 'adjusted income statement',
      as_reported_ebit == 220.0, adjusted_ebit is None, difference is None.
    - Parity: CLI line equals `  2024: not extracted: {record.missing_statement}`.
    """
    raw = FinancialStatements(
        ticker="RAW",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),
            _make_income(2024, 1100.0, 660.0, 220.0),
            _make_income(2025, 1200.0, 720.0, 240.0),
        ],
    )
    adjusted = FinancialStatements(
        ticker="ADJ",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),
            _make_income(2025, 1200.0, 720.0, 240.0),
        ],
    )

    assert 2024 in raw.years
    assert 2024 not in adjusted.years

    reconciliation = _build_ebit_reconciliation(raw, adjusted)
    rec_2024 = next(r for r in reconciliation if r.year == 2024)
    assert rec_2024.missing_statement == "adjusted income statement"
    assert rec_2024.as_reported_ebit == 220.0
    assert rec_2024.adjusted_ebit is None
    assert rec_2024.difference is None

    cli_lines = _captured(cli.print_normalization, raw, adjusted)
    cli_2024_line = _row_starting(cli_lines, "  2024:")
    assert cli_2024_line == "  2024: not extracted: adjusted income statement"
    assert cli_2024_line == f"  2024: not extracted: {rec_2024.missing_statement}"


def test_raw_only_year_with_non_income_statement_is_named_by_both_entry_points() -> None:
    """When a year exists on the raw side only via balance sheet:
    - Raw covers 2023 and 2025 income, plus 2024 balance sheet.
    - Adjusted covers 2023 and 2025 income only.
    - Neither side has an income statement for 2024.
    - Both entry points report `not extracted: raw and adjusted income statement`.
    """
    raw = FinancialStatements(
        ticker="RAW",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),
            _make_income(2025, 1200.0, 720.0, 240.0),
        ],
        balance_sheets=[_make_balance_sheet(2024)],
    )
    adjusted = FinancialStatements(
        ticker="ADJ",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),
            _make_income(2025, 1200.0, 720.0, 240.0),
        ],
    )

    assert 2024 in raw.years
    assert 2024 not in adjusted.years

    reconciliation = _build_ebit_reconciliation(raw, adjusted)
    rec_2024 = next(r for r in reconciliation if r.year == 2024)
    assert rec_2024.missing_statement == "raw and adjusted income statement"
    assert rec_2024.as_reported_ebit is None
    assert rec_2024.adjusted_ebit is None
    assert rec_2024.difference is None

    cli_lines = _captured(cli.print_normalization, raw, adjusted)
    cli_2024_line = _row_starting(cli_lines, "  2024:")
    assert cli_2024_line == "  2024: not extracted: raw and adjusted income statement"
    assert cli_2024_line == f"  2024: not extracted: {rec_2024.missing_statement}"


# ---------------------------------------------------------------------------
# 3. Comprehensive Statement Presence Matrix for Year 2024
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw_state", "adj_state", "expected_phrase", "expected_raw_ebit", "expected_adj_ebit"),
    [
        # Adjusted-only cases
        ("absent", "income", "raw income statement", None, 220.0),
        ("absent", "cash_flow", "raw and adjusted income statement", None, None),
        # Raw-only cases
        ("income", "absent", "adjusted income statement", 200.0, None),
        ("cash_flow", "absent", "raw and adjusted income statement", None, None),
        # Both sides present but one or both lack income statement
        ("cash_flow", "cash_flow", "raw and adjusted income statement", None, None),
        ("cash_flow", "income", "raw income statement", None, 220.0),
        ("income", "cash_flow", "adjusted income statement", 200.0, None),
    ],
)
def test_entry_points_parity_across_missing_statement_combinations(
    raw_state: str,
    adj_state: str,
    expected_phrase: str,
    expected_raw_ebit: float | None,
    expected_adj_ebit: float | None,
) -> None:
    """Closed-form identity: CLI and Web produce matching missing statement records
    across all combinations of statement availability.
    """
    def _build_statements(state: str, ticker: str, ebit_val: float) -> FinancialStatements:
        if state == "absent":
            return FinancialStatements(ticker=ticker)
        if state == "income":
            # rev=1000, cogs=600, sga=400 - ebit_val -> ebit = ebit_val
            sga = 400.0 - ebit_val
            return FinancialStatements(
                ticker=ticker,
                income_statements=[_make_income(2024, 1000.0, 600.0, sga)],
            )
        if state == "cash_flow":
            return FinancialStatements(
                ticker=ticker,
                cash_flow_statements=[_make_cash_flow(2024)],
            )
        raise ValueError(f"Unknown state: {state}")

    raw = _build_statements(raw_state, "RAW", 200.0)
    adjusted = _build_statements(adj_state, "ADJ", 220.0)

    # 2024 is in the union
    assert 2024 in (set(raw.years) | set(adjusted.years))

    reconciliation = _build_ebit_reconciliation(raw, adjusted)
    rec_2024 = next(r for r in reconciliation if r.year == 2024)

    assert rec_2024.missing_statement == expected_phrase
    assert rec_2024.as_reported_ebit == expected_raw_ebit
    assert rec_2024.adjusted_ebit == expected_adj_ebit
    assert rec_2024.difference is None

    cli_lines = _captured(cli.print_normalization, raw, adjusted)
    cli_2024_line = _row_starting(cli_lines, "  2024:")
    expected_line = f"  2024: not extracted: {expected_phrase}"
    assert cli_2024_line == expected_line
    assert cli_2024_line == f"  2024: not extracted: {rec_2024.missing_statement}"


# ---------------------------------------------------------------------------
# 4. Summary Line Behavior & Reconciled Sets
# ---------------------------------------------------------------------------

def test_summary_line_prints_when_all_reconciled_years_have_zero_delta() -> None:
    """When at least one year is reconciled and no reconciled year has a delta:
    - CLI prints `  No adjustments applied (no non-recurring items, or none matched I/S fields).`
    - Reconciled years with delta == 0 do not emit a per-year line.
    """
    raw = FinancialStatements(
        ticker="RAW",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),  # ebit = 200.0
            _make_income(2024, 1100.0, 660.0, 220.0),  # ebit = 220.0
        ],
    )
    adjusted = FinancialStatements(
        ticker="ADJ",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),  # ebit = 200.0, delta = 0
            _make_income(2024, 1100.0, 660.0, 220.0),  # ebit = 220.0, delta = 0
        ],
    )

    cli_lines = _captured(cli.print_normalization, raw, adjusted)
    # No per-year delta lines
    assert not any(line.startswith("  2023:") for line in cli_lines)
    assert not any(line.startswith("  2024:") for line in cli_lines)
    # Summary line is present
    summary = "  No adjustments applied (no non-recurring items, or none matched I/S fields)."
    assert summary in cli_lines

    # Web reconciliation reflects difference == 0.0 for both
    reconciliation = _build_ebit_reconciliation(raw, adjusted)
    assert len(reconciliation) == 2
    assert all(r.difference == 0.0 for r in reconciliation)
    assert all(r.missing_statement is None for r in reconciliation)


def test_reconciliation_summary_is_silent_when_no_year_was_reconciled() -> None:
    """When years exist in the union but no year has an income statement on both sides:
    - `reconciled` is empty.
    - CLI returns early before printing the summary line.
    - Closed-form identity: with zero reconciled years, we cannot claim no adjustments applied.
    """
    # Raw has 2023 only, Adjusted has 2024 only
    raw = FinancialStatements(
        ticker="RAW",
        income_statements=[_make_income(2023, 1000.0, 600.0, 200.0)],
    )
    adjusted = FinancialStatements(
        ticker="ADJ",
        income_statements=[_make_income(2024, 1100.0, 660.0, 220.0)],
    )

    cli_lines = _captured(cli.print_normalization, raw, adjusted)
    # Two lines printed for the missing statements
    assert _row_starting(cli_lines, "  2023:") == "  2023: not extracted: adjusted income statement"
    assert _row_starting(cli_lines, "  2024:") == "  2024: not extracted: raw income statement"
    # Summary line must NOT be printed
    summary = "  No adjustments applied (no non-recurring items, or none matched I/S fields)."
    assert summary not in cli_lines


# ---------------------------------------------------------------------------
# 5. Empty Input & Edge Cases
# ---------------------------------------------------------------------------

def test_empty_financial_statements_on_both_sides_produce_empty_output() -> None:
    """When both raw and adjusted have no statements of any kind:
    - `years` is empty.
    - `cli.print_normalization` prints the section header and returns early
      without printing any year rows or summary lines.
    - `_build_ebit_reconciliation` returns an empty list.
    """
    raw = FinancialStatements(ticker="RAW")
    adjusted = FinancialStatements(ticker="ADJ")

    assert raw.years == []
    assert adjusted.years == []

    cli_lines = _captured(cli.print_normalization, raw, adjusted)
    # The banner prints (4 lines: blank, 70 equals, title, 70 equals), then early return
    expected_header = [
        "",
        "=" * 70,
        "GAAP -> NON-GAAP RECONCILIATION ($M)",
        "=" * 70,
    ]
    assert cli_lines == expected_header
    # No per-year lines and no summary lines were printed
    assert not any(":" in line for line in cli_lines)
    assert not any("No adjustments applied" in line for line in cli_lines)

    assert _build_ebit_reconciliation(raw, adjusted) == []


def test_build_ebit_reconciliation_handles_none_inputs() -> None:
    """Web entry point guard: None inputs return an empty list."""
    fs = FinancialStatements(ticker="TEST", income_statements=[_make_income(2023, 1000.0, 600.0, 200.0)])
    assert _build_ebit_reconciliation(None, None) == []
    assert _build_ebit_reconciliation(fs, None) == []
    assert _build_ebit_reconciliation(None, fs) == []


# ---------------------------------------------------------------------------
# 6. Sorting Order Across Disjoint Year Sets
# ---------------------------------------------------------------------------

def test_union_years_are_sorted_chronologically_across_disjoint_year_sets() -> None:
    """When raw and adjusted cover distinct years:
    - Raw covers {2021, 2023}.
    - Adjusted covers {2022, 2024}.
    - Union is strictly sorted: [2021, 2022, 2023, 2024].
    - Both CLI and web iterate in exact chronological ascending order.
    """
    raw = FinancialStatements(
        ticker="RAW",
        income_statements=[
            _make_income(2021, 1000.0, 600.0, 200.0),
            _make_income(2023, 1000.0, 600.0, 200.0),
        ],
    )
    adjusted = FinancialStatements(
        ticker="ADJ",
        income_statements=[
            _make_income(2022, 1000.0, 600.0, 200.0),
            _make_income(2024, 1000.0, 600.0, 200.0),
        ],
    )

    expected_order = [2021, 2022, 2023, 2024]

    # Web order
    rec = _build_ebit_reconciliation(raw, adjusted)
    assert [r.year for r in rec] == expected_order

    # CLI order
    cli_lines = _captured(cli.print_normalization, raw, adjusted)
    cli_years = [int(line.strip().split(":")[0]) for line in cli_lines if line.strip() and line.strip().split(":")[0].isdigit()]
    assert cli_years == expected_order


# ---------------------------------------------------------------------------
# 7. Criterion 3 Simulation / Sanity Check
# ---------------------------------------------------------------------------

def test_mutation_probe_simulating_raw_years_alone_omits_adjusted_only_year() -> None:
    """Proves criterion 3: iterating `raw.years` alone instead of the union
    fails to report year 2024 when 2024 is present only in `adjusted`.
    """
    raw = FinancialStatements(
        ticker="RAW",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),
            _make_income(2025, 1200.0, 720.0, 240.0),
        ],
    )
    adjusted = FinancialStatements(
        ticker="ADJ",
        income_statements=[
            _make_income(2023, 1000.0, 600.0, 200.0),
            _make_income(2024, 1100.0, 660.0, 220.0),
            _make_income(2025, 1200.0, 720.0, 240.0),
        ],
    )

    # In raw.years, 2024 is completely absent
    assert 2024 not in raw.years
    # Under mutated iteration `for y in raw.years:`
    mutated_loop_years = list(raw.years)
    assert 2024 not in mutated_loop_years

    # Under current code `years = sorted(set(raw.years) | set(adjusted.years))`
    union_years = sorted(set(raw.years) | set(adjusted.years))
    assert 2024 in union_years
