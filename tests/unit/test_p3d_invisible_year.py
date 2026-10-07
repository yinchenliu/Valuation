"""A year any statement covers is visible — `P3d-invisible-year` (backlog item 116).

**What this file locks.**

  1. `FinancialStatements.years` is the union of the income statements, the
     balance sheets AND the cash flow statements; `income_statement_years` is
     the narrow set beside it, and `get_income_statement` returns a statement
     for every year of the narrow set and `None` for a year that is in the wide
     set and not the narrow one.
  2. `analysis/projector.derive_assumptions` **stops** on a covered year with no
     income statement, with a `ValueError` naming the field and the fiscal year.
     It never produces the one-year-window growth rate that the invisible year
     used to produce, and it never skips the year.
  3. The two branches written to report that case — `cli.print_historical_fcff`
     and `api/routes_valuation._historical_fcff_by_year` — both **run**, and
     both name the missing statement in the same words.
  4. The CLI reconciliation and `_build_ebit_reconciliation` name an
     unreconciled year in the same words, in all three missing-statement cases.
  5. `latest_year` still raises for a filing that holds a balance sheet and no
     income statement, and its message is true when it prints.
  6. The blank net-income-margin cell is exactly as wide as the cell it stands
     in for, holds no figure, and the year is named under the same table.
  7. No historical FCFF figure and no derived assumption moves for a filing
     whose years all have an income statement.

**Where every expected value comes from.** `docs/5-testing/strategy.md` section 1
and `.claude/agents/tester.md`: the expected side of every assertion exists
before the code runs. Each one here is

  * **hand arithmetic** over the filing built by `_income`, `_cash_flow` and
    `_balance` below, whose figures were chosen so the whole chain is checkable
    on paper. Revenue is 1,000 / 1,100 / 1,200; every expense line is a fixed
    fraction of revenue, so the operating margin is exactly 20% in all three
    years, the effective tax rate exactly 20%, D&A exactly 10% of revenue,
    CapEx exactly 6%, and historical FCFF exactly 20% of revenue. The arithmetic
    is written out beside each assertion.
  * a **closed-form identity**: two entry points fed the same statements must
    emit the same words for the same year; a blank cell must occupy exactly as
    many characters as the cell it replaces, so the later columns of its row do
    not move; `income_statement_years` must be a subset of `years`.
  * the **format string** itself for the one width figure — `_pct(v, w)` is
    `f"{v * 100:>{w}.1f}%"`, which is `w` characters of number and then one
    `%`, so a cell is `w + 1` wide. Derived from `cli.py:417`, not from a
    printed row.

No number below was obtained by running the code and reading what it printed.

**What this file deliberately does NOT assert.** `IncomeStatement.gross_margin`
(`models/financial_statements.py:108`) and `.operating_margin` (`:132`) return
`0.0` for a zero-revenue year, so the two margin rows above the net one print a
fabricated `0.0%`. That is backlog item 1 and the overall lead's ruling of
2026-10-07 leaves it on the record deliberately. Asserting it would make the
defect permanent and turn its fix red (`docs/5-testing/strategy.md` section 2.1),
so nothing here reads those two cells. The alignment test derives the column of
the net-margin cell from the format string and from a twin filing, never from
the row above it.

**No key, no PDF, no network.** Every statement is built in the test.
"""

from __future__ import annotations

import argparse
import io
import math
from contextlib import redirect_stdout

import pytest

import cli
from analysis.projector import derive_assumptions
from api.routes_valuation import _build_ebit_reconciliation, _historical_fcff_by_year
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
)

# ---------------------------------------------------------------------------
# The hand-built filing
#
# Three fiscal years. Every figure is a fixed fraction of that year's revenue,
# so every ratio below is exact and checkable on paper:
#
#   revenue            1,000   1,100   1,200
#   cost of revenue      600     660     720   (60% of revenue)
#   SG&A                 200     220     240   (20% of revenue)
#   -> EBIT              200     220     240   (20% of revenue)
#   interest expense      50      55      60   ( 5% of revenue)
#   -> EBT               150     165     180
#   tax expense           30      33      36   (20% of EBT)
#   -> net income        120     132     144   (12% of revenue)
#
#   cash flow: net income 120 / 132 / 144, D&A 100 / 110 / 120 (10% of
#   revenue), CapEx -60 / -66 / -72 (6% of revenue), no working capital change.
#   -> CFO               220     242     264
# ---------------------------------------------------------------------------

#: Every figure written out, so no float multiplication stands between the
#: arithmetic above and the fixture. Order: revenue, cost of revenue, SG&A,
#: interest expense, tax expense, cash-flow net income, cash-flow D&A, CapEx.
_FIGURES = {
    2023: (1000.0, 600.0, 200.0, 50.0, 30.0, 120.0, 100.0, -60.0),
    2024: (1100.0, 660.0, 220.0, 55.0, 33.0, 132.0, 110.0, -66.0),
    2025: (1200.0, 720.0, 240.0, 60.0, 36.0, 144.0, 120.0, -72.0),
}


def _income(year: int) -> IncomeStatement:
    revenue, cogs, sga, interest, tax, _, _, _ = _FIGURES[year]
    return IncomeStatement(
        year=year,
        revenue=revenue,
        cost_of_revenue=cogs,
        sga=sga,
        interest_expense=interest,
        tax_expense=tax,
        diluted_shares_outstanding=100.0,
    )


def _cash_flow(year: int) -> CashFlowStatement:
    _, _, _, _, _, net_income, da, capex = _FIGURES[year]
    return CashFlowStatement(
        year=year,
        net_income=net_income,
        depreciation_amortization=da,
        change_in_working_capital=0.0,
        capital_expenditures=capex,
    )


def _balance(year: int) -> BalanceSheet:
    revenue = _FIGURES[year][0]
    return BalanceSheet(
        year=year,
        cash_and_equivalents=revenue / 10.0,
        long_term_debt=revenue / 2.5,
        total_equity=revenue / 2.0,
        # The fixture's figures are already in millions, which is this
        # repository's unit for every money figure
        # (`docs/4-conventions/units-and-signs.md`), so one printed unit is one
        # million. The field is required and has no default, by rule 3.
        printed_unit_in_millions=1.0,
    )


def _complete_filing() -> FinancialStatements:
    """Every one of the three years has all three statements.

    This is the shape of every filing in this repository today, and the
    regression guard for criterion 9: no figure may move for it.
    """
    return FinancialStatements(
        ticker="FULL",
        company_name="Complete Filing Inc.",
        income_statements=[_income(y) for y in (2023, 2024, 2025)],
        balance_sheets=[_balance(y) for y in (2023, 2024, 2025)],
        cash_flow_statements=[_cash_flow(y) for y in (2023, 2024, 2025)],
    )


def _probe_filing() -> FinancialStatements:
    """2024 has a cash flow statement and a balance sheet and NO income statement.

    This is the shape the whole unit exists for. It is `_complete_filing()`
    with one income statement removed and nothing else changed, so any figure
    that differs between the two for 2023 or 2025 is a figure the invisible
    year moved.
    """
    return FinancialStatements(
        ticker="PROBE",
        company_name="Probe Filing Inc.",
        income_statements=[_income(y) for y in (2023, 2025)],
        balance_sheets=[_balance(y) for y in (2023, 2024, 2025)],
        cash_flow_statements=[_cash_flow(y) for y in (2023, 2024, 2025)],
    )


def _balance_sheet_only_filing() -> FinancialStatements:
    """One balance sheet, no income statement of any year, no cash flow."""
    return FinancialStatements(
        ticker="BSONLY",
        company_name="Balance Sheet Only Inc.",
        income_statements=[],
        balance_sheets=[_balance(2024)],
        cash_flow_statements=[],
    )


# ---------------------------------------------------------------------------
# Capture helpers
# ---------------------------------------------------------------------------

def _captured(fn, *args, **kwargs) -> list[str]:
    """Run `fn` and return the lines it printed, newlines stripped."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        fn(*args, **kwargs)
    return buffer.getvalue().split("\n")


def _is_rule(line: str) -> bool:
    """A banner rule: `cli._section` prints a line of `=` above and below its title."""
    stripped = line.strip()
    return bool(stripped) and set(stripped) == {"="}


def _section_lines(lines: list[str], banner_fragment: str) -> list[str]:
    """The lines between the banner that holds `banner_fragment` and the next banner."""
    start = next(i for i, line in enumerate(lines) if banner_fragment in line)
    first = start + 2 if _is_rule(lines[start + 1]) else start + 1
    out: list[str] = []
    for line in lines[first:]:
        if _is_rule(line):
            break
        out.append(line)
    return out


def _row_after(lines: list[str], label: str) -> str:
    """The line printed immediately after the one starting with `label`."""
    index = next(i for i, line in enumerate(lines) if line.startswith(label))
    return lines[index + 1]


def _row_starting(lines: list[str], label: str) -> str:
    return next(line for line in lines if line.startswith(label))


def _fcff_row(lines: list[str], year: int) -> list[str]:
    """The whitespace-separated fields of the FCFF table row for `year`."""
    row = next(line for line in lines if line.strip().startswith(f"{year} "))
    return row.split()


# ===========================================================================
# 1. The property pair
# ===========================================================================

def test_years_is_the_union_of_all_three_statement_kinds() -> None:
    """`years` holds every year ANY statement covers.

    Hand-enumerated from the fixture, not from the code: the income statements
    cover {2023, 2025}, the balance sheets {2023, 2024, 2025} and the cash flow
    statements {2023, 2024, 2025}. The union, sorted ascending, is
    [2023, 2024, 2025].
    """
    assert _probe_filing().years == [2023, 2024, 2025]


def test_income_statement_years_holds_only_the_years_with_an_income_statement() -> None:
    """Hand-enumerated: the fixture builds income statements for 2023 and 2025 only."""
    assert _probe_filing().income_statement_years == [2023, 2025]


def test_income_statement_years_is_a_subset_of_years_and_here_a_strict_one() -> None:
    """Closed-form identity: a year with an income statement is a year some statement covers.

    The second half is what keeps the first from being vacuous. If the two sets
    were equal for this filing, the whole unit would be untested by it.
    """
    financials = _probe_filing()
    assert set(financials.income_statement_years) <= set(financials.years)
    assert set(financials.years) - set(financials.income_statement_years) == {2024}


def test_get_income_statement_is_none_exactly_for_a_year_in_the_wide_set_alone() -> None:
    """The contract `income_statement_years` states: a statement for every year in it, `None` for no other.

    And 2024 really is covered: the fixture gives it a balance sheet and a cash
    flow statement, so its figures were extracted. That is the case backlog item
    116 is about.
    """
    financials = _probe_filing()
    for year in financials.income_statement_years:
        statement = financials.get_income_statement(year)
        assert statement is not None
        assert statement.year == year
    assert financials.get_income_statement(2024) is None
    assert financials.get_cash_flow(2024) is not None
    assert financials.get_balance_sheet(2024) is not None


# ===========================================================================
# 2. The stop, by name
# ===========================================================================

def test_derive_assumptions_stops_and_names_the_field_and_the_fiscal_year() -> None:
    """Rule 3. The type is `ValueError` and the message holds the field and the year.

    `AttributeError` is the cheapest wrong answer here — `None.revenue` names
    no field and no year — so the type is asserted as well as the message.
    """
    with pytest.raises(ValueError) as excinfo:
        derive_assumptions(_probe_filing())

    assert excinfo.type is ValueError
    message = str(excinfo.value)
    assert "revenue" in message
    assert "2024" in message
    # The message tells the reader which years it has and which it lacks, so
    # the two sets it names must be the filing's own two sets.
    assert "[2023, 2024, 2025]" in message
    assert "[2023, 2025]" in message


def test_derive_assumptions_never_produces_the_one_year_window_the_invisible_year_gave() -> None:
    """The growth rate the invisible year distorted, and the rate it should have been.

    Hand arithmetic, both of them:

        2023 revenue 1,000 and 2025 revenue 1,200 are TWO fiscal years apart.
            two years of growth : (1200/1000) ** (1/2) - 1 = 0.0954451150103...
            one year of growth  : (1200/1000) ** (1/1) - 1 = 0.2

    Before this unit, 2024 was in no year list, so the window held the two
    endpoints alone, `lookback` was `min(3, 2 - 1) = 1`, and the CAGR read two
    years of growth as one: **20.0% a year** where the endpoints justify
    9.5445%. That 20.0% is the figure the code must now refuse to produce.

    It must refuse the 9.5445% too. The 2024 revenue is not in the filing, so
    neither figure is a measurement of this company, and dropping the year from
    the window is exactly what moved the number. A skip is not neutral; this
    test is the one that says so, and it is distinct from the test above
    because a skip returns normally and raises nothing to catch.
    """
    one_year_window = (1200.0 / 1000.0) ** (1 / 1) - 1   # = 0.2
    two_year_window = (1200.0 / 1000.0) ** (1 / 2) - 1   # = 0.09544511501033...

    try:
        assumptions = derive_assumptions(_probe_filing())
    except ValueError as exc:
        assert "2024" in str(exc)
        return

    produced = assumptions["revenue_growth_rates"]
    pytest.fail(
        f"derive_assumptions returned revenue_growth_rates={produced} for a "
        f"filing whose 2024 income statement is absent. The invisible year "
        f"produces {one_year_window:.4%} a year by reading two fiscal years of "
        f"growth as one; the endpoints alone justify {two_year_window:.4%}. "
        f"Neither is a measurement of this filing, so the run must stop."
    )


def test_a_complete_filing_still_derives_its_assumptions() -> None:
    """The stop fires on the absence and on nothing else.

    Without this, a `_income_statements_for_years` that raised unconditionally
    would pass every test above.
    """
    assumptions = derive_assumptions(_complete_filing())
    assert assumptions["revenue_growth_rates"]


# ===========================================================================
# 3. Both dead branches, in both entry points
# ===========================================================================

def test_the_cli_fcff_table_prints_a_row_for_the_year_with_no_income_statement() -> None:
    """`cli.print_historical_fcff`'s `is_ is None` branch, now reachable.

    The expected row is the fixture's own: 2024 has a cash flow statement and
    no income statement, so the only statement the row can name as missing is
    the income statement.
    """
    lines = _captured(
        cli.print_historical_fcff, _probe_filing(), "statements as extracted"
    )
    assert "  2024  not extracted: income statement" in lines
    # The years around it still carry their figures, so the row did not replace
    # the table.
    assert _fcff_row(lines, 2023)[0] == "2023"
    assert _fcff_row(lines, 2025)[0] == "2025"


def test_the_web_fcff_rows_hold_a_row_for_the_year_with_no_income_statement() -> None:
    """`api/routes_valuation._historical_fcff_by_year`'s `income_statement is None` branch.

    Both entry points, not one: a figure verified in one is not verified in the
    other.
    """
    rows = {row.year: row for row in _historical_fcff_by_year(_probe_filing())}

    assert sorted(rows) == [2023, 2024, 2025]
    assert rows[2024].is_computable is False
    assert rows[2024].fcff is None
    assert rows[2024].missing_statements == ("income statement",)
    assert rows[2023].is_computable is True
    assert rows[2025].is_computable is True


def test_the_cash_flow_figures_of_the_invisible_year_are_printed() -> None:
    """The figures that were extracted and then dropped without a word.

    Hand arithmetic for 2024: CFO = net income 132 + D&A 110 = 242, and CapEx
    is -66. The cash flow table is one label column of 18 characters followed by
    one 10-character cell per year of `years`, so 2024's cell is the second,
    at characters 28 to 38.
    """
    lines = _captured(cli.print_extracted_financials, _probe_filing())
    cash_flow_section = _section_lines(lines, "CASH FLOW ($M)")

    cfo_row = _row_starting(cash_flow_section, "CFO")
    capex_row = _row_starting(cash_flow_section, "CapEx")

    assert cfo_row[28:38].strip() == "242"
    assert capex_row[28:38].strip() == "-66"
    # And the year is named, because the income statement table has no column
    # for it.
    assert "  2024  not extracted: income statement" in lines


# ===========================================================================
# 4. The two entry points say the same words
# ===========================================================================

def test_both_entry_points_name_the_missing_income_statement_in_the_same_words() -> None:
    """Closed-form identity: one filing, one year, one sentence.

    The web's cell is built by `templates/_statements.html:501`, which renders
    `not extracted{% if row.missing_statements %}: {{ row.missing_statements |
    join(', ') }}{% endif %}`. The CLI's line is the same sentence behind the
    year. The identity is the requirement; the words themselves are not
    asserted as a figure.
    """
    financials = _probe_filing()

    web_row = next(
        row for row in _historical_fcff_by_year(financials) if row.year == 2024
    )
    web_cell = "not extracted: " + ", ".join(web_row.missing_statements)

    cli_lines = _captured(
        cli.print_historical_fcff, financials, "statements as extracted"
    )
    cli_line = _row_starting(cli_lines, "  2024  ")

    assert cli_line == f"  {2024:>4}  {web_cell}"


@pytest.mark.parametrize(
    ("raw_has_2024_income", "adjusted_has_2024_income", "expected_phrase"),
    [
        (False, False, "raw and adjusted income statement"),
        (False, True, "raw income statement"),
        (True, False, "adjusted income statement"),
    ],
)
def test_both_entry_points_name_an_unreconciled_year_in_the_same_words(
    raw_has_2024_income: bool,
    adjusted_has_2024_income: bool,
    expected_phrase: str,
) -> None:
    """Closed-form identity, over all three missing-statement cases.

    The expected phrase on each row is the case itself stated in words: a year
    absent from the raw side alone is a missing "raw income statement", absent
    from the adjusted side alone a missing "adjusted income statement", and
    absent from both "raw and adjusted income statement". The web renders it at
    `templates/_statements.html:455` as `not extracted: {{ row.missing_statement
    }}`; the CLI prints the same sentence behind the year.

    The first row is the branch this unit made reachable: a 2024 that has a cash
    flow statement and no income statement on either side.
    """
    def _side(has_2024_income: bool, ticker: str) -> FinancialStatements:
        income_years = (2023, 2024, 2025) if has_2024_income else (2023, 2025)
        return FinancialStatements(
            ticker=ticker,
            income_statements=[_income(y) for y in income_years],
            cash_flow_statements=[_cash_flow(y) for y in (2023, 2024, 2025)],
        )

    raw = _side(raw_has_2024_income, "RAW")
    adjusted = _side(adjusted_has_2024_income, "ADJ")

    web_record = next(
        record for record in _build_ebit_reconciliation(raw, adjusted)
        if record.year == 2024
    )
    assert web_record.missing_statement == expected_phrase
    assert web_record.difference is None
    web_cell = f"not extracted: {web_record.missing_statement}"

    cli_line = _row_starting(_captured(cli.print_normalization, raw, adjusted), "  2024:")
    assert cli_line == f"  2024: {web_cell}"


# ===========================================================================
# 5. `latest_year`'s message is true when it prints
# ===========================================================================

def test_latest_year_stops_for_a_filing_with_a_balance_sheet_and_no_income_statement() -> None:
    """Rule 3, and fact 4 of the unit: the message must still be TRUE when it prints.

    `years` is non-empty for this filing — hand-enumerated, the one balance
    sheet covers 2024 — so a `latest_year` reading the wide set would return
    2024 and every `get_income_statement(latest_year)` after it would be `None`.
    It reads the narrow set, which is empty, so it stops.

    The message's claim is asserted as a claim, not as a string: it says the
    filing holds no income statements, and `income_statement_years` is checked
    to be empty on the same object.
    """
    financials = _balance_sheet_only_filing()

    assert financials.years == [2024]
    assert financials.income_statement_years == []

    with pytest.raises(ValueError) as excinfo:
        # Bound to a name only so `ruff`'s B018 does not read a property access
        # as a useless expression. `latest_year` is a property, so reading it is
        # the call under test.
        _ = financials.latest_year

    assert excinfo.type is ValueError
    message = str(excinfo.value)
    assert "BSONLY" in message
    assert "no income statements" in message


def test_latest_year_is_the_latest_year_that_has_an_income_statement() -> None:
    """Hand-enumerated: the probe's income statements cover 2023 and 2025, so 2025.

    `years` ends at 2025 too, so this alone would not catch a `latest_year`
    reading the wide set; the test above is the one that does. This one keeps
    the happy path from drifting.
    """
    assert _probe_filing().latest_year == 2025


def test_a_balance_sheet_only_filing_still_prints_its_statements_without_raising() -> None:
    """A table build must not raise, even where every income statement is absent.

    Hand-enumerated: there is no income statement of any year, so the table is
    replaced by a sentence and 2024 is named below it.
    """
    lines = _captured(cli.print_extracted_financials, _balance_sheet_only_filing())
    assert "  No income statement extracted for any year." in lines
    assert "  2024  not extracted: income statement" in lines
    assert "  2024  not extracted: cash flow statement" in lines


# ===========================================================================
# 6. The blank net-margin cell and its absence line
# ===========================================================================

@pytest.mark.parametrize("width", [6, 7, 10, 12])
def test_the_blank_net_margin_cell_is_as_wide_as_the_cell_it_stands_in_for(width: int) -> None:
    """Derived from the format string at `cli.py:417`, not from a printed row.

        _pct(v, w) is f"{v * 100:>{w}.1f}%"

    which emits `w` characters of right-aligned number and then one `%`. A cell
    is therefore `w + 1` characters wide, and a blank of `w` would pull every
    later column of that one row a character to the left.
    """
    zero_revenue = IncomeStatement(year=2024, revenue=0.0)

    blank = cli._net_margin_cell(zero_revenue, width)

    assert len(blank) == width + 1
    assert len(blank) == len(cli._pct(0.123, width))


def test_the_blank_net_margin_cell_holds_no_figure() -> None:
    """Rule 3: a cell that cannot be computed invents nothing.

    `0.0%` is the six characters a company that really earned nothing on real
    revenue would print, so the blank must hold no digit at all.
    """
    blank = cli._net_margin_cell(IncomeStatement(year=2024, revenue=0.0), 10)

    assert blank.strip() == ""
    assert not any(character.isdigit() for character in blank)


def test_a_computed_net_margin_cell_is_the_margin() -> None:
    """Hand arithmetic: net income 120 on revenue 1,000 is 12.0%.

    120 / 1000 = 0.12, and `_pct(0.12, 10)` is `"{:>10.1f}%".format(12.0)`,
    which is six spaces, `12.0`, `%` — eleven characters.
    """
    assert cli._net_margin_cell(_income(2023), 10) == "      12.0%"


def test_a_zero_revenue_year_in_the_middle_does_not_shift_the_later_columns() -> None:
    """The alignment, measured against a twin filing rather than eyeballed.

    Two filings, identical but for the middle year's income statement: one has
    revenue 0, the other the fixture's 1,100. Whatever the middle cell holds,
    the 2025 cell of the net-margin row must start at the same character in
    both, or a reader comparing the column against the rows above it reads the
    wrong year.

    Hand arithmetic for the two outer cells, which are the same in both
    filings: 120 / 1,000 = 0.12 and 144 / 1,200 = 0.12, so both print
    `      12.0%` — eleven characters, six spaces then `12.0%`.

    The derived column positions are the second half: the label column is 18
    characters (`cli.py:471`) and each cell is `col + 1 = 11`, so the three
    cells start at 18, 29 and 40.
    """
    zero_year = IncomeStatement(year=2024, revenue=0.0)

    with_zero = FinancialStatements(
        ticker="ZERO",
        income_statements=[_income(2023), zero_year, _income(2025)],
        cash_flow_statements=[_cash_flow(y) for y in (2023, 2024, 2025)],
    )
    twin = FinancialStatements(
        ticker="TWIN",
        income_statements=[_income(y) for y in (2023, 2024, 2025)],
        cash_flow_statements=[_cash_flow(y) for y in (2023, 2024, 2025)],
    )

    def _net_margin_row(financials: FinancialStatements) -> str:
        section = _section_lines(
            _captured(cli.print_extracted_financials, financials),
            "INCOME STATEMENT (GAAP, $M)",
        )
        return _row_after(section, "Net Income")

    zero_row = _net_margin_row(with_zero)
    twin_row = _net_margin_row(twin)

    # The derived positions.
    assert zero_row[18:29] == "      12.0%"
    assert zero_row[29:40] == " " * 11
    assert zero_row[40:51] == "      12.0%"

    # The identity: the blank does not move the column beside it.
    assert zero_row[40:51] == twin_row[40:51]


def test_the_income_statement_table_and_its_absence_line_are_printed_as_a_pair() -> None:
    """One call, both halves. Reviewer finding N1.

    `_net_margin_cell` prints a blank and `_print_net_margin_absences` says why.
    Nothing in the code enforces that the two are called together, so this test
    is what does: it fails if a later edit prints the table without the line.

    Hand-enumerated: the only zero-revenue year in this filing is 2024, so that
    is the only year the line may name.
    """
    financials = FinancialStatements(
        ticker="ZERO",
        income_statements=[
            _income(2023),
            IncomeStatement(year=2024, revenue=0.0),
            _income(2025),
        ],
        cash_flow_statements=[_cash_flow(y) for y in (2023, 2024, 2025)],
    )

    lines = _captured(cli.print_extracted_financials, financials)
    section = _section_lines(lines, "INCOME STATEMENT (GAAP, $M)")

    # Half one: the cell is blank.
    assert _row_after(section, "Net Income")[29:40] == " " * 11
    # Half two: the same output names the year, the field and the reason.
    assert "  2024  not computable: net income margin, revenue is 0" in section
    # And it names that year once and no other.
    absences = [line for line in section if "not computable" in line]
    assert len(absences) == 1


# ===========================================================================
# 7. No figure moves for a filing whose years all have an income statement
# ===========================================================================

#: Hand arithmetic, one row per year. FCFF = CFO + |interest| * (1 - t) - |CapEx|
#: (`analysis/fcff.py:81`), with t the effective tax rate, which is 30/150 =
#: 33/165 = 36/180 = 0.20 in all three years.
#:
#:   2023  CFO 120 + 100 = 220; 50 * 0.8 = 40; CapEx 60 -> 220 + 40 - 60 = 200
#:   2024  CFO 132 + 110 = 242; 55 * 0.8 = 44; CapEx 66 -> 242 + 44 - 66 = 220
#:   2025  CFO 144 + 120 = 264; 60 * 0.8 = 48; CapEx 72 -> 264 + 48 - 72 = 240
#:
#: and the margin is 200/1000 = 220/1100 = 240/1200 = 20.0% in every year.
_EXPECTED_FCFF = {
    #        revenue,  cfo,   after-tax interest, capex, fcff
    2023: (1000.0, 220.0, 40.0, 60.0, 200.0),
    2024: (1100.0, 242.0, 44.0, 66.0, 220.0),
    2025: (1200.0, 264.0, 48.0, 72.0, 240.0),
}


def test_the_web_fcff_figures_of_a_complete_filing() -> None:
    """Every figure hand-derived above. This is the regression guard for every current input."""
    rows = {row.year: row for row in _historical_fcff_by_year(_complete_filing())}

    assert sorted(rows) == [2023, 2024, 2025]
    for year, (revenue, cfo, after_tax_interest, capex, fcff) in _EXPECTED_FCFF.items():
        row = rows[year]
        assert row.is_computable is True
        assert row.missing_statements == ()
        assert row.fcff is not None
        assert row.fcff.revenue == pytest.approx(revenue)
        assert row.fcff.cfo == pytest.approx(cfo)
        assert row.fcff.after_tax_interest == pytest.approx(after_tax_interest)
        assert row.fcff.capital_expenditures == pytest.approx(capex)
        assert row.fcff.fcff == pytest.approx(fcff)
        assert row.fcff.fcff_margin == pytest.approx(0.20)


def test_the_cli_fcff_figures_of_a_complete_filing() -> None:
    """The same hand-derived figures through the other entry point.

    The row is `year, revenue, CFO, interest*(1-t), CapEx, FCFF, FCFF%`
    (`cli.py:943`), printed with thousands separators.
    """
    lines = _captured(
        cli.print_historical_fcff, _complete_filing(), "statements as extracted"
    )

    for year, (revenue, cfo, after_tax_interest, capex, fcff) in _EXPECTED_FCFF.items():
        fields = _fcff_row(lines, year)
        numbers = [float(field.replace(",", "")) for field in fields[1:6]]
        assert fields[0] == str(year)
        assert numbers == [revenue, cfo, after_tax_interest, capex, fcff]
        assert fields[6] == "20.0%"


def test_the_invisible_year_moves_no_figure_of_the_years_around_it() -> None:
    """Closed-form identity: 2023 and 2025 are the same statements in both filings.

    The probe filing is the complete one with the 2024 income statement removed
    and nothing else changed, so every 2023 and 2025 figure must be identical.
    If widening `years` had disturbed a neighbouring year, this is where it
    would show.
    """
    complete = {row.year: row for row in _historical_fcff_by_year(_complete_filing())}
    probe = {row.year: row for row in _historical_fcff_by_year(_probe_filing())}

    for year in (2023, 2025):
        assert probe[year].fcff is not None
        assert complete[year].fcff is not None
        assert probe[year].fcff.fcff == complete[year].fcff.fcff
        assert probe[year].fcff.revenue == complete[year].fcff.revenue
        assert probe[year].fcff.cfo == complete[year].fcff.cfo
        assert probe[year].fcff.after_tax_interest == complete[year].fcff.after_tax_interest
        assert probe[year].fcff.capital_expenditures == complete[year].fcff.capital_expenditures
    # And the hand-derived figures, so the identity cannot pass on two equal
    # wrong numbers.
    assert probe[2023].fcff.fcff == pytest.approx(200.0)
    assert probe[2025].fcff.fcff == pytest.approx(240.0)


def test_the_derived_assumptions_of_a_complete_filing() -> None:
    """Every ratio hand-derived from the fixture.

        revenue growth  the window is min(3, 3 - 1) = 2 years, from 1,000 to
                        1,200, so (1200/1000) ** (1/2) - 1 = sqrt(1.2) - 1
                        = 0.0954451150103...
        operating margin  EBIT / revenue is 200/1000 = 220/1100 = 240/1200
                        = 0.20 in each year; the mean of three 0.20s is 0.20
        tax rate        30/150 = 33/165 = 36/180 = 0.20, inside the [0%, 50%]
                        band, so the clamp does not move it
        D&A / revenue   100/1000 = 110/1100 = 120/1200 = 0.10
        CapEx / revenue  60/1000 =  66/1100 =  72/1200 = 0.06
        NWC / revenue   no working capital change in any year, and the plain
                        mean of three zeros is 0.0
    """
    assumptions = derive_assumptions(_complete_filing())

    expected_growth = math.sqrt(1.2) - 1
    assert assumptions["revenue_growth_rates"] == [
        pytest.approx(expected_growth)
    ] * assumptions["projection_years"]
    assert assumptions["operating_margin"] == pytest.approx(0.20)
    assert assumptions["tax_rate"] == pytest.approx(0.20)
    assert assumptions["da_pct_revenue"] == pytest.approx(0.10)
    assert assumptions["capex_pct_revenue"] == pytest.approx(0.06)
    assert assumptions["nwc_pct_revenue"] == pytest.approx(0.0)


def test_the_web_reconciliation_of_a_complete_filing_names_nothing_missing() -> None:
    """The happy path of `_build_ebit_reconciliation`, so the three branches above are not the only ones run.

    Hand arithmetic: raw and adjusted hold the same income statements here, so
    every difference is exactly 0.0 and no statement is named as missing.
    """
    records = _build_ebit_reconciliation(_complete_filing(), _complete_filing())

    assert [record.year for record in records] == [2023, 2024, 2025]
    for record in records:
        assert record.missing_statement is None
        assert record.difference == 0.0
    # EBIT is 20% of revenue in every year.
    assert [record.as_reported_ebit for record in records] == [200.0, 220.0, 240.0]


# ===========================================================================
# 8. The three remaining branches this unit added
# ===========================================================================

def test_the_reconciliation_summary_is_silent_when_no_year_was_reconciled() -> None:
    """A sentence must not assert that no adjustment applied to a year whose EBIT was never read.

    Hand-enumerated: neither side holds an income statement of any year, so no
    year can be reconciled. The reader is told which statement is missing, and
    the summary line — which claims that no non-recurring item moved EBIT — must
    not print, because nothing was compared.

    This asserts the absence of a claim, not a fallback: no figure is involved
    either way.
    """
    def _side(ticker: str) -> FinancialStatements:
        return FinancialStatements(
            ticker=ticker,
            income_statements=[],
            cash_flow_statements=[_cash_flow(2024)],
        )

    lines = _captured(cli.print_normalization, _side("RAW"), _side("ADJ"))

    assert "  2024: not extracted: raw and adjusted income statement" in lines
    assert not any("No adjustments applied" in line for line in lines)


def test_the_balance_sheet_section_names_the_sheet_the_valuation_reads() -> None:
    """When the latest balance sheet is not the sheet the valuation nets debt from, the line says so.

    Hand-enumerated from the fixture built here: the balance sheets cover 2025
    and 2026, so the latest is **FY2026** and that is the sheet shown. The
    income statements cover 2024 and 2025, so `latest_year` is **FY2025** and
    that is the sheet `pipeline.value_company` reads. The two differ, so the
    divergence line prints and names both years.

    FY2025's balance sheet exists in this filing, so the sentence is true of it.
    """
    financials = FinancialStatements(
        ticker="LATEBS",
        income_statements=[_income(2024), _income(2025)],
        balance_sheets=[
            _balance(2025),
            BalanceSheet(
                year=2026,
                cash_and_equivalents=130.0,
                long_term_debt=520.0,
                total_equity=650.0,
                printed_unit_in_millions=1.0,
            ),
        ],
        cash_flow_statements=[_cash_flow(2024), _cash_flow(2025)],
    )

    assert financials.latest_year == 2025
    assert max(sheet.year for sheet in financials.balance_sheets) == 2026

    lines = _captured(cli.print_extracted_financials, financials)
    heading = _row_starting(lines, "EXTRACTED BALANCE SHEET")
    divergence = _row_starting(lines, "  Shown: FY2026")

    assert heading == "EXTRACTED BALANCE SHEET — FY2026 ($M)"
    assert "FY2025's balance sheet" in divergence
    assert "latest year with an income statement" in divergence
    # And it does not print when the two years agree.
    agreeing = _captured(cli.print_extracted_financials, _complete_filing())
    assert not any(line.startswith("  Shown: FY") for line in agreeing)


def test_cli_main_names_the_year_with_no_income_statement_at_stage_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    _no_socket: None,
) -> None:
    """The first place a reader meets the years names the invisible one — and then the run stops.

    `cli.main()` is the entry `cli.py`'s `if __name__ == "__main__"` calls. Not
    `runpy.run_path`: that would execute the file into a fresh namespace and
    none of the patches below would be the names the fresh copy binds (backlog
    item 98).

    Hand-enumerated: the probe filing's statements cover 2023, 2024 and 2025,
    and its income statements cover 2023 and 2025, so stage 1 must print both
    lists. `pipeline.value_company` calls `derive_assumptions` before it fetches
    any market data (`pipeline.py:135`), so the run stops there, by name, with
    nothing valued — which is rule 3 reaching the operator rather than a share
    price built on two of the three years.
    """
    def _closed(*args: object, **kwargs: object) -> None:
        raise AssertionError("cli.main reached a boundary it did not fake")

    def _fake_session(args: argparse.Namespace):
        args.ticker = "PROBE"
        args.company_name = "Probe Filing Inc."
        return _probe_filing(), [], "hand-built", "hand-built"

    monkeypatch.setattr(cli, "_extract_from_session_file", _fake_session)
    monkeypatch.setattr(cli, "_extract_via_api", _closed)
    monkeypatch.setattr(
        "sys.argv", ["cli.py", "--session-file", "p3d-never-opened.json"]
    )

    with pytest.raises(ValueError) as excinfo:
        cli.main()

    assert "2024" in str(excinfo.value)
    assert "revenue" in str(excinfo.value)

    printed = capsys.readouterr().out
    assert "  Years extracted: [2023, 2024, 2025]" in printed
    assert "  Years with an income statement: [2023, 2025]" in printed
