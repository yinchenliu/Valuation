"""GAAP to Non-GAAP adjustment engine.

Applies LLM-identified non-recurring items to the specific income statement
field they are embedded in, rather than always adjusting other_operating_expense.
"""

from __future__ import annotations

import dataclasses

from models.financial_statements import FinancialStatements, IncomeStatement, NonRecurringItem

# Fallback: map human-readable labels to IS field names in case the LLM
# returns a description instead of the exact field name.
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


def _resolve_field(line_item: str) -> str:
    """Map an NRI line_item value to the matching IncomeStatement field name."""
    key = line_item.strip().lower()
    for label, field in _LABEL_TO_FIELD:
        if key == label or key.startswith(label):
            return field
    print(f"  [normalizer] Unrecognised line_item '{line_item}' — defaulting to other_operating_expense")
    return "other_operating_expense"


def apply_adjustments(
    income_statement: IncomeStatement,
    items: list[NonRecurringItem],
) -> IncomeStatement:
    """Apply NonRecurringItems to the correct IS field on this statement.

    add_back: item is a one-time expense embedded in the field — subtract it
              (lowers the cost, improves adjusted earnings).
    remove:   item is a one-time gain embedded in the field — add it back
              (raises the cost, reduces adjusted earnings to a clean base).
    """
    changes: dict[str, float] = {}
    for item in items:
        field = _resolve_field(item.line_item)
        delta = -item.amount if item.direction == "add_back" else item.amount
        changes[field] = changes.get(field, 0.0) + delta

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
