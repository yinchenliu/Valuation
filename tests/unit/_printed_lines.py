"""Build Pass 1 answers in the printed-lines shape (P11a), from `{field: [values]}`.

Since `P11a-printed-lines` every Pass 1 money field is a LIST OF PRINTED ROWS,
each `{"label": str, "value": number, "page": int}`, and Python adds a field's
rows (`ingestion/claude_extractor.py:figure_from_printed_lines`). This module is
the one place the tests turn a readable `{field: [values]}` into that shape, so a
fixture still reads as the figures it holds.

**It holds no expected value.** Every figure comes from the caller. The labels and
pages it writes are inventions of the test, chosen so that no label or page can be
mistaken for an amount in a message:

- a label is the field's name, with ", row N" when the field has several rows;
- a page is 50 for the income statement, 51 for the balance sheet and 52 for the
  cash flow statement. No amount used by the tests is 50, 51 or 52.

The underscore keeps pytest from collecting it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

INCOME_STATEMENT_PAGE = 50
BALANCE_SHEET_PAGE = 51
CASH_FLOW_PAGE = 52

# Where each field is printed, for the invented page number. The Pass 1 schema's
# own descriptions (`_FINANCIALS_YEAR_SCHEMA`) put D&A, CFO, capex, SBC and the
# working capital rows on the cash flow statement.
_CASH_FLOW_FIELDS = frozenset({
    "depreciation_amortization", "cfo", "capex", "sbc", "change_in_working_capital",
})


def _page_of(field: str, balance_sheet: bool) -> int:
    if balance_sheet:
        return BALANCE_SHEET_PAGE
    return CASH_FLOW_PAGE if field in _CASH_FLOW_FIELDS else INCOME_STATEMENT_PAGE


def lines(
    field: str, values: Sequence[float], *, page: int | None = None,
    balance_sheet: bool = False,
) -> list[dict[str, Any]]:
    """One printed row per value, in order. `[]` for no values: "not printed"."""
    where = page if page is not None else _page_of(field, balance_sheet)
    if len(values) == 1:
        return [{"label": field, "value": values[0], "page": where}]
    return [
        {"label": f"{field}, row {i + 1}", "value": value, "page": where}
        for i, value in enumerate(values)
    ]


def printed_year(year: int, figures: Mapping[str, Sequence[float]]) -> dict[str, Any]:
    """A `historical_years` entry: `year`, then each field's printed rows."""
    return {"year": year} | {field: lines(field, values) for field, values in figures.items()}


def printed_balance_sheet(
    year: int, figures: Mapping[str, Sequence[float]],
) -> dict[str, Any]:
    """A `latest_balance_sheet`: `year`, then each field's printed rows."""
    return {"year": year} | {
        field: lines(field, values, balance_sheet=True) for field, values in figures.items()
    }
