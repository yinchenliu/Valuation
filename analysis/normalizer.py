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

# What each confidence tag the extractor may return does to the statements.
#
# The user's decision, 2026-09-22: "For low confidence, just leave a note and
# document, but don't need to adjust the F/S." So a `low` item is listed, with
# its description and its cited source, and **not** applied. `medium` and `high`
# are applied, exactly as before.
#
# Two tuples of strings, not a mapping to behaviour: rule 2 permits a table that
# maps a key to a value and forbids one that maps a key to a function. Nothing
# here is called; partition_by_confidence does the deciding in literal Python.
#
# There is no threshold constant and no setting. A knob here would let the
# decision be reversed by a value nobody reads, which is the shape of the defect
# this closes.
_CONFIDENCE_APPLIED: tuple[str, str] = ("high", "medium")
_CONFIDENCE_EXCLUDED: tuple[str] = ("low",)


def partition_by_confidence(
    non_recurring: list[NonRecurringItem],
) -> tuple[list[NonRecurringItem], list[NonRecurringItem]]:
    """Split non-recurring items into (applied, excluded) on their confidence.

    Returns two lists, in that order, each in the order the items arrived:

      applied  — `high` and `medium`. These go to normalize_financials and move
                 the income statement.
      excluded — `low`. These move nothing. The caller must print them, with the
                 source each cited, so a reader can put one back by hand.

    **The decision is here and not in `ingestion/`.** Rule 1: the model
    identifies a candidate item and cites the note it came from; `analysis/`
    decides what that does to a figure. Until this function existed `analysis/`
    did not decide — it applied whatever it was handed, so the 1,140M add-back
    the model itself tagged `low` in the **FY2025** L3Harris 10-K extraction moved
    the valuation exactly as far as a figure read cleanly off a page (backlog item
    36, which records that filing and that run). No cache entry on disk now holds
    a `low` item, so this docstring cites the recorded run, not a measurement.

    Raises:
        ValueError: on a confidence this engine does not recognise, naming the
            value and the year. Rule 3. An absent tag must never be read as
            `high`: defaulting an unknown to the *strongest* reading is the same
            guess as defaulting a missing number to zero, in the direction that
            silently maximises the adjustment.
    """
    applied: list[NonRecurringItem] = []
    excluded: list[NonRecurringItem] = []

    for item in non_recurring:
        # str() rather than a bare .strip(): a JSON null or a number that reached
        # the field arrives here as None or float, and must raise the named
        # ValueError below rather than an AttributeError from inside this loop.
        # Case and surrounding space are folded, as _resolve_field folds them for
        # line_item: "LOW" is not an unknown label, it is `low` shouted.
        key = str(item.confidence).strip().lower()
        if key in _CONFIDENCE_APPLIED:
            applied.append(item)
        elif key in _CONFIDENCE_EXCLUDED:
            excluded.append(item)
        else:
            raise ValueError(
                f"Unrecognised confidence {item.confidence!r} on the {item.year} "
                f"non-recurring item '{item.description}' "
                f"({item.amount:,.0f} on {item.line_item}): confidence must be "
                f"one of: "
                f"{', '.join(_CONFIDENCE_APPLIED + _CONFIDENCE_EXCLUDED)}. "
                f"It is not assumed to be 'high' — an item this engine cannot "
                f"rank is an input it does not have."
            )

    return applied, excluded


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

    Raises:
        ValueError: when any item's year is not the year of an income statement
            in `financials`, before any adjustment is applied. Rule 3, backlog
            item 25. The item's year and the statements' years come from two
            separate extraction passes and nothing reconciles them. Until this
            check, the loop below walked the statements and never looked at an
            item whose year matched none of them, so that adjustment was dropped
            while the result was still labelled normalised. The message names
            each such item and the statement years that exist; it does not say
            which of the two years is wrong, because this function cannot know.
    """
    if not non_recurring:
        return financials

    statement_years = [stmt.year for stmt in financials.income_statements]
    unmatched = [item for item in non_recurring if item.year not in statement_years]
    if unmatched:
        listed = "; ".join(
            f"year {item.year}, line_item '{item.line_item}', "
            f"description '{item.description}'"
            for item in unmatched
        )
        raise ValueError(
            f"{len(unmatched)} non-recurring item(s) carry a year with no income "
            f"statement in the financials: {listed}. The income statement years "
            f"are {sorted(statement_years)}. An item for a year with no statement "
            f"cannot be applied, and it is not dropped: the result would be "
            f"labelled normalised without it. Supply the income statement for "
            f"that year, or correct the item's year."
        )

    by_year: dict[int, list[NonRecurringItem]] = {}
    for item in non_recurring:
        by_year.setdefault(item.year, []).append(item)

    adjusted_is = [
        apply_adjustments(stmt, by_year.get(stmt.year, []))
        for stmt in financials.income_statements
    ]

    return dataclasses.replace(financials, income_statements=adjusted_is)
