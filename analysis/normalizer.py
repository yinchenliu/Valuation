"""GAAP to Non-GAAP adjustment engine.

Applies LLM-identified non-recurring items to the specific income statement
field they are embedded in, rather than always adjusting other_operating_expense.
"""

from __future__ import annotations

import dataclasses

from models.financial_statements import (
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)

# Map human-readable labels to IS field names, for the case where the LLM returns a
# description instead of the exact field name. A label that matches no row here is
# not guessed at — _resolve_field stops.
_LABEL_TO_FIELD: list[tuple[str, str]] = [
    ("cost_of_revenue",            "cost_of_revenue"),
    ("cost of revenue",            "cost_of_revenue"),
    ("cost of goods",              "cost_of_revenue"),
    ("cogs",                       "cost_of_revenue"),
    ("sga",                        "sga"),
    ("sg&a",                       "sga"),
    ("selling, general",           "sga"),
    ("general and administrative", "sga"),
    ("general_and_administrative", "sga"),
    ("sales and marketing",        "sga"),
    ("selling and marketing",      "sga"),
    ("rd_expense",                 "rd_expense"),
    ("r&d",                        "rd_expense"),
    ("research and development",   "rd_expense"),
    ("depreciation_amortization",  "depreciation_amortization"),
    ("depreciation",               "depreciation_amortization"),
    ("other_operating_expense",    "other_operating_expense"),
    ("other operating",            "other_operating_expense"),
    ("other_non_operating",        "other_non_operating"),
    ("other non-operating",        "other_non_operating"),
    ("non-operating",              "other_non_operating"),
]

# The sign each field carries into earnings: -1 for a field that *reduces* earnings,
# +1 for one that *raises* them. It is a number, not a behaviour, which is what
# rule 2 permits (docs/2-rules/rules.md: "a lookup table that maps a key to a number
# is fine").
#
# The five operating lines are subtracted by IncomeStatement.total_operating_expenses
# and so by ebit (models/financial_statements.py:66-77). other_non_operating is
# *added* by ebt (models/financial_statements.py:91), so a larger value there means
# larger earnings, not smaller.
_FIELD_EARNINGS_SIGN: dict[str, float] = {
    "cost_of_revenue":           -1.0,
    "sga":                       -1.0,
    "rd_expense":                -1.0,
    "depreciation_amortization": -1.0,
    "other_operating_expense":   -1.0,
    "other_non_operating":       +1.0,
}

# Every field _LABEL_TO_FIELD can return must carry a sign. A field with no sign is
# an input this engine does not have, and rule 3 says that stops. Both tables are
# literals in this file, so the check belongs at import, where no code path can hide
# it — not at the call site, where it would only fire on the label that happens to
# be routed there.
assert set(_FIELD_EARNINGS_SIGN).issuperset(
    field for _, field in _LABEL_TO_FIELD
), (
    "_LABEL_TO_FIELD routes to a field with no entry in _FIELD_EARNINGS_SIGN: "
    f"{sorted({f for _, f in _LABEL_TO_FIELD} - set(_FIELD_EARNINGS_SIGN))}"
)

_LEGAL_DIRECTIONS: tuple[str, str] = ("add_back", "remove")


def _resolve_field(line_item: str, year: int) -> str:
    """Map an NRI line_item value to the matching IncomeStatement field name.

    Raises ValueError on a label the table does not hold. Rule 3: a line_item this
    engine cannot place is an input it does not have, so it stops and names the
    label rather than guessing a field and moving the wrong line.
    """
    key = line_item.strip().lower()
    for label, field in _LABEL_TO_FIELD:
        if key == label or key.startswith(label):
            return field
    raise ValueError(
        f"Unrecognised line_item '{line_item}' on the {year} non-recurring item: "
        f"it matches no IncomeStatement field. line_item must name one of: "
        f"{', '.join(sorted(_FIELD_EARNINGS_SIGN))}."
    )


def _field_delta(item: NonRecurringItem, field: str) -> float:
    """The change to apply to `field` for one non-recurring item.

    NonRecurringItem.adjusted_impact (models/financial_statements.py:31-37) is the
    signed effect on *earnings*: +amount for add_back, -amount for remove. The change
    to the *field* is that impact multiplied by the sign the field carries into
    earnings. The two coincide only on a field that reduces earnings, which is why a
    single rule applied to both kinds of line moved earnings the wrong way.

    Raises ValueError on a direction that is neither "add_back" nor "remove". Rule 3:
    direction has exactly two legal values (models/financial_statements.py:26), and a
    third is an input this engine does not have.
    """
    if item.direction not in _LEGAL_DIRECTIONS:
        raise ValueError(
            f"Unrecognised direction '{item.direction}' on the {item.year} "
            f"non-recurring item '{item.description}': direction must be one of: "
            f"{', '.join(_LEGAL_DIRECTIONS)}."
        )
    return item.adjusted_impact * _FIELD_EARNINGS_SIGN[field]


def apply_adjustments(
    income_statement: IncomeStatement,
    items: list[NonRecurringItem],
) -> IncomeStatement:
    """Apply NonRecurringItems to the correct IS field on this statement.

    add_back: item is a one-time expense embedded in the field — removing it
              improves adjusted earnings.
    remove:   item is a one-time gain embedded in the field — stripping it
              reduces adjusted earnings to a clean base.

    Which way the *field* moves depends on the field: an expense line moves opposite
    to earnings, other_non_operating moves with them. _field_delta carries that sign.
    """
    changes: dict[str, float] = {}
    for item in items:
        field = _resolve_field(item.line_item, item.year)
        delta = _field_delta(item, field)
        # Written out rather than as a dict lookup with a zero fallback: that zero
        # would mean "nothing accumulated yet", and rule 3's table names the shape.
        # Two items on one field accumulate; the first item on a field starts it.
        if field in changes:
            changes[field] += delta
        else:
            changes[field] = delta

    if not changes:
        return income_statement

    return dataclasses.replace(
        income_statement,
        **{f: getattr(income_statement, f) + delta for f, delta in changes.items()},
    )


def normalize_financials(
    financials: FinancialStatements,
    non_recurring: list[NonRecurringItem],
) -> FinancialStatements:
    """Apply non-recurring adjustments across all years.

    Groups NRIs by year and applies each to the correct IS field.
    """
    if not non_recurring:
        return financials

    by_year: dict[int, list[NonRecurringItem]] = {}
    for item in non_recurring:
        by_year.setdefault(item.year, []).append(item)

    adjusted_is = [
        apply_adjustments(stmt, by_year.get(stmt.year, []))
        for stmt in financials.income_statements
    ]

    return dataclasses.replace(financials, income_statements=adjusted_is)
