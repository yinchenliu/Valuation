"""Two-pass LLM extraction for 10-K/10-Q SEC filings.

ARCHITECTURE
============
  PASS 1 — Financial Statements (year-targeted, table extraction)
    PDF → LLM → I/S + C/F (+ optional B/S) for target years only
    Each figure is returned as the printed rows that make it up; Python adds them.

  PASS 2 — Non-Recurring Items (year-targeted, footnote reasoning)
    PDF + I/S summary from Pass 1 → LLM → NonRecurringItem list
    Prompt focused on semantic reading of MD&A and notes.

Why two passes?
  - Table extraction (precision) and footnote reasoning (semantics) are
    fundamentally different tasks. A single prompt forces the LLM to do both,
    and neither gets full attention.
  - Pass 2 receives the extracted I/S as context, so it can anchor NRI amounts
    to concrete line items and verify plausibility.

SMART MULTI-PDF ORCHESTRATOR
=============================
When multiple 10-K PDFs are provided (e.g. 2025, 2024, 2023 filings):
  - Oldest filing: extract ALL years (picks up comparative years)
  - Other filings: extract ONLY the primary fiscal year
  - Balance sheet: only from the most recent filing

Example with 3 filings:
  2025 10-K → extract [2025] + B/S          (1 year,  2 API calls)
  2024 10-K → extract [2024] only           (1 year,  2 API calls)
  2023 10-K → extract [2023, 2022, 2021]    (3 years, 2 API calls)
  Total: 5 unique years, 6 API calls
  Old way: 9 year-extractions, 3 API calls — but each call was overloaded

USAGE
=====
    from ingestion.claude_extractor import extract_financials, extract_multi_year

    # Single PDF (both passes, extracts all years)
    financials, nri = extract_financials("GOOGL_10K_2025.pdf", ticker="GOOGL")

    # Multi-year smart extraction
    financials, nri = extract_multi_year(
        filings=[
            (2025, "GOOGL_10K_2025.pdf"),
            (2024, "GOOGL_10K_2024.pdf"),
            (2023, "GOOGL_10K_2023.pdf"),
        ],
        ticker="GOOGL",
    )

PROVIDER, TRANSPORT AND CREDENTIAL
==================================
There are two *routes* to extraction:
  - Route A (API): Google Gemini API, with GEMINI_API_KEY. The provider is "gemini",
    the transport is "gemini-direct". The default provider is named once, in
    `config.DEFAULT_EXTRACTION_PROVIDER = "gemini"`.
  - Route B (Claude Code session): Claude reads the filing inside a Claude Code
    session (`extract-filing` skill) and writes a session file
    (`ingestion/session_extraction.py`). The provider is "claude", the transport is
    "claude-code-session", and no API key is used.

Claude reads a filing only through route B. `resolve_provider("claude", ...)` stops
and names route B.

Which model read the filing, over which transport, on whose credential, is an
assumption about every figure downstream — rule 6. `resolve_provider` returns that
as a `ProviderResolution`, the CLI prints it and the web result page shows it.

ENVIRONMENT VARIABLES
=====================
    GEMINI_API_KEY              — required when provider="gemini" (route A).

See docs/8-build/environment.md section 3.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import math
import os
import re
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

import config
from models.financial_statements import (
    BALANCE_CHECK_TOLERANCE,
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
    printed_total_status,
)

Provider = Literal["claude", "gemini"]

# How the request reaches the provider.
# Route A: "gemini-direct" calls the Google Gemini API.
# Route B: "claude-code-session" reads figures from a session file written during
# a Claude Code session (ingestion/session_extraction.py).
Transport = Literal[
    "gemini-direct", "claude-code-session",
]

# Which credential the transport carries. The kind, never the value.
# "claude-code-session" carries none: the session file is read from disk.
CredentialKind = Literal[
    "gemini-api-key",
    "claude-code-session",
]


@dataclass(frozen=True)
class ProviderResolution:
    """Who read the filing, over what, on whose credential.

    Every field is a label. **No field holds a key or a token**, so this object is
    safe to print and to render into a page — which is the point of it: rule 6 says
    an assumption is shown to the reader, and "claude-opus-5 via a company gateway"
    and "claude-opus-5 via the public API" must be distinguishable in the output.
    """

    provider: Provider
    model: str
    reasoning_label: str
    transport: Transport
    transport_label: str
    credential: CredentialKind
    credential_source: str


# Default model IDs per provider. A lookup of a *string*, not of behaviour.
_DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-3.1-pro-preview",
}


# ===========================================================================
# PASS 1: Financial Statement Extraction — schema & prompt
# ===========================================================================

# One historical year of Pass 1. Named on its own so the session route can require
# every key it names (PASS1_YEAR_FIELDS, below) without importing a private name,
# and so the two cannot drift: the prompt's schema text is built from this dict.
#
# Every key but `year` is a LIST OF PRINTED LINES (see _PRINTED_LINE_SCHEMA): the
# model copies each row that makes up the field, and Python adds them
# (figure_from_printed_lines). The model never adds, subtracts or nets rows (rule 1;
# the user's decision of 2026-10-02, backlog item 56).
_FINANCIALS_YEAR_SCHEMA: dict[str, str] = {
    "year": "int — fiscal year (e.g. 2024)",
    "revenue": "lines — total net revenue / net sales",
    "cost_of_revenue": "lines — COGS / cost of goods sold / cost of services",
    "gross_profit": "lines — the printed gross profit row, for validation only. [] if the filing prints no gross profit row; never derive it",
    "sga": "lines — SG&A (selling + general + admin): the SG&A row, or each of the separately printed selling / marketing and general & administrative rows. Positive.",
    "rd_expense": "lines — R&D / research and development. Positive.",
    "depreciation_amortization": "lines — D&A from cash flow statement operating section",
    "other_operating_expense": "lines — CATCH-ALL: every other operating cost row not listed above",
    "operating_income": "lines — the printed EBIT / income from operating activities row; this should be from income statement. [] if the filing prints no operating income row; never derive it",
    "interest_expense": "lines — gross interest expense on debt. POSITIVE. Use footnote breakout if I/S shows only net interest.",
    "interest_income": "lines — interest / investment income. POSITIVE.",
    "other_non_operating": "lines — CATCH-ALL: every other income/expense row below the operating line not listed above (signed)",
    "tax_expense": "lines — income tax provision. POSITIVE.",
    "net_income": "lines — the printed TOTAL CONSOLIDATED net income row (net income INCLUDING noncontrolling interests, i.e. after tax_expense, BEFORE any allocation to noncontrolling interests). Do NOT use 'net income attributable to common shareholders' or 'attributable to the parent'. Never []: every income statement prints it.",
    "diluted_shares": "lines — the diluted weighted-avg shares row, as printed. Its unit is the one 'share_units' states",
    "cfo": "lines — the 'Net cash provided by operating activities' row",
    "capex": "lines — the 'Purchases of PP&E' row and the 'Acquisitions and intangible asset purchases' row(s) from the investing section, each as its own line. Do NOT include securities. POSITIVE.",
    "sbc": "lines — stock-based compensation (from CFS operating section)",
    "change_in_working_capital": "lines — each individual 'Changes in assets and liabilities' row from the Cash Flow Statement operating section, one line per row. SIGNED: negative = WC increase (cash outflow), positive = WC decrease (cash inflow).",
}

# The one balance sheet Pass 1 returns when the plan asks for it.
_FINANCIALS_BALANCE_SHEET_SCHEMA: dict[str, str] = {
    "year": "int — the most recent fiscal year in the filing",
    "cash": "lines — cash and cash equivalents (period-end)",
    "short_term_investments": "lines — marketable securities / short-term investments",
    "accounts_receivable": "lines",
    "inventory": "lines — [] if not applicable",
    "other_current_assets": "lines — CATCH-ALL: every other current asset row not listed above",
    "ppe_net": "lines — PP&E net of accumulated depreciation",
    "goodwill": "lines",
    "intangible_assets": "lines — intangibles other than goodwill",
    "other_non_current_assets": "lines — CATCH-ALL: every non-current asset row not listed above. Includes non-marketable securities, deferred income taxes (asset), operating lease ROU assets, equity method investments, etc.",
    "accounts_payable": "lines",
    "accrued_liabilities": "lines — accrued expenses / compensation",
    "other_current_liabilities": "lines — CATCH-ALL: every current liability row not listed above. Includes operating lease obligations due within one year, deferred revenue, accrued revenue share, etc.",
    "short_term_debt": "lines — the current portion of long-term debt, short-term borrowings, notes payable and commercial paper rows, and the finance lease obligations due within one year, each as its own line. Not operating lease obligations.",
    "long_term_debt": "lines — long-term debt beyond one year and the long-term finance lease obligations, each as its own line. Not operating lease obligations.",
    "other_non_current_liabilities": "lines — CATCH-ALL: every non-current liability row not listed above, and any row printed between liabilities and equity (e.g. redeemable noncontrolling interest, mezzanine). Includes operating lease liabilities, pension, deferred tax liabilities, etc.",
    "total_equity": "lines — total stockholders equity",
    "noncontrolling_interest_nonredeemable": "lines — MEMO: the noncontrolling interest row printed INSIDE equity on the latest balance sheet (e.g. 'Nonredeemable noncontrolling interest'). [] if the filing prints none. It is already inside total_equity; never add it to any total.",
    "noncontrolling_interest_redeemable": "lines — MEMO: the redeemable noncontrolling interest row printed OUTSIDE equity (mezzanine, between liabilities and equity) on the latest balance sheet. [] if the filing prints none. It is already inside another line; never add it to any total.",
    "total_assets": "lines — CHECK ONLY: the printed 'Total assets' row. Never []: every balance sheet prints it",
    "total_liabilities_and_equity": "lines — CHECK ONLY: the printed total row for liabilities and equity (including any mezzanine items, e.g. 'Total liabilities, redeemable noncontrolling interest, and shareholders' equity'). Never []: every balance sheet prints it",
}

# The shape of one printed line. Every "lines" field above is a JSON list of these.
_PRINTED_LINE_SCHEMA: dict[str, str] = {
    "label": "string — the row's label exactly as printed",
    "value": "number — the ONE figure printed on that row for that year, under the field's sign rule",
    "page": "int — the 1-based PDF page the row is printed on",
}

# `units` and `share_units` are each one printed unit statement: the words that state
# the unit of a set of figures, exactly as printed, and the page they are printed on.
# The model copies the words; Python reads the scale word in them (`printed_scale`)
# and converts (rule 1; the user's approval of 2026-10-04, backlog item 44). The
# model returns no scale word of its own and converts nothing.
_FINANCIALS_SCHEMA = {
    "ticker": "string",
    "company_name": "string",
    "currency": "string (e.g. 'USD')",
    "units": {
        "printed": "string — the statement of the unit of the money figures, exactly as printed (usually just under the income statement's title), e.g. '(in millions, except per share data)'",
        "page": "int — the 1-based PDF page it is printed on",
    },
    "share_units": {
        "printed": "string — the words that state the unit of the diluted share count, exactly as printed. If one statement covers both, copy it here too, with its page",
        "page": "int — the 1-based PDF page it is printed on",
    },
    "historical_years": [_FINANCIALS_YEAR_SCHEMA],
    "latest_balance_sheet": _FINANCIALS_BALANCE_SHEET_SCHEMA,
}

# The two printed unit statements a Pass 1 answer carries, each with the figures it
# states the unit of: `units` the money figures, `share_units` the diluted share count.
_UNIT_STATEMENT_FIELDS: tuple[tuple[str, UnitOf], ...] = (
    ("units", "money figures"),
    ("share_units", "share count"),
)
PASS1_UNIT_FIELDS: tuple[str, ...] = tuple(key for key, _ in _UNIT_STATEMENT_FIELDS)

# Every key a Pass 1 answer must carry, per historical year and in the balance sheet.
# Both routes require them: an absent key stops, naming the field and the year
# (rule 3). An empty list is the answer for a row the filing does not print.
PASS1_YEAR_FIELDS: tuple[str, ...] = tuple(_FINANCIALS_YEAR_SCHEMA)
PASS1_BALANCE_SHEET_FIELDS: tuple[str, ...] = tuple(_FINANCIALS_BALANCE_SHEET_SCHEMA)

# The keys that hold a list of printed lines: every key but `year`.
PASS1_YEAR_LINE_FIELDS: tuple[str, ...] = tuple(k for k in PASS1_YEAR_FIELDS if k != "year")
PASS1_BALANCE_SHEET_LINE_FIELDS: tuple[str, ...] = tuple(
    k for k in PASS1_BALANCE_SHEET_FIELDS if k != "year"
)

# `[]` means "the filing prints no such row", and for most fields that reads as 0.
# Three kinds of row are different (review round 1, F1 and F2; the orchestrator's
# round 2 decisions):
# - net_income is printed by every income statement and starts the cash flow
#   statement, so `[]` is a shape problem: both routes stop, never a 0.
# - gross_profit and operating_income are check rows a filing may not print: `[]`
#   is None, and that check is skipped and labelled "not printed".
# - total_assets and total_liabilities_and_equity are check rows every balance
#   sheet prints: `[]` is None, "not extracted", and the check FAILs saying so.
PASS1_YEAR_NEVER_EMPTY_FIELDS: tuple[str, ...] = ("net_income",)
_YEAR_CHECK_ROWS: tuple[str, ...] = ("gross_profit", "operating_income")
_BALANCE_SHEET_CHECK_ROWS: tuple[str, ...] = ("total_assets", "total_liabilities_and_equity")

_FINANCIALS_SCHEMA_STR = json.dumps(_FINANCIALS_SCHEMA, indent=2)
_PRINTED_LINE_SCHEMA_STR = json.dumps(_PRINTED_LINE_SCHEMA, indent=2)

_FINANCIALS_SYSTEM_PROMPT = textwrap.dedent(f"""\
    You are a senior financial analyst. Your ONLY task is to extract numerical
    financial data from a 10-K/10-Q filing — Income Statement, Cash Flow
    Statement, and (if requested) Balance Sheet.

    OUTPUT: Return ONLY a valid JSON object. No markdown fences, no explanation.
    The first character of your response must be {{.

    SCHEMA:
    {_FINANCIALS_SCHEMA_STR}

    PRINTED LINES:
    Every field marked "lines" is a JSON list of the printed rows that make it up,
    each row in this shape:
    {_PRINTED_LINE_SCHEMA_STR}
    Example: "capex": [{{"label": "Purchases of property and equipment",
    "value": 1200, "page": 41}}, {{"label": "Acquisitions, net of cash acquired",
    "value": 35, "page": 41}}]
    - Each "value" is ONE figure printed on that row for that year. NEVER add,
      subtract or net rows, and never write a figure you worked out: Python adds
      the lines of each field.
    - If the filing prints one row that is the whole field, list that one row.
      Otherwise list each row that makes it up. Never list a printed total
      together with the rows it totals.
    - An empty list [] means the filing prints no such row. Never leave a key out.
    - Every row of the income statement down to net income, and every row of the
      balance sheet, is accounted for exactly once: listed in one field, or
      inside a printed total that is listed in one field. A row that matches no
      named field goes into its section's CATCH-ALL list. No row appears in two
      fields. Two kinds of field are outside this rule: the check fields
      (gross_profit, operating_income, net_income, total_assets,
      total_liabilities_and_equity), and the two noncontrolling interest MEMO
      fields, which copy a row that already belongs to another field.
    - "label" is the row's label as printed; "page" is the 1-based PDF page.

    EXTRACTION RULES:
    - Extract ONLY the fiscal years specified in the user instructions.
    - Copy every figure as printed, in the unit the filing prints it in. NEVER
      convert a figure to another unit: Python reads "units" and "share_units"
      and converts.
    - "units" and "share_units" are statements the filing prints, copied word for
      word with their page. Never write a unit the filing does not print.
    - When the statement does not print a field's row by itself, the figure may
      be taken from a note or from MD&A, as one printed line, with its label and
      its page as printed there, copied in the unit printed there and never
      converted.
    - All values must be POSITIVE (signs implied by field name).
    - If a line item is not reported, use an empty list [].
    - Do NOT invent or estimate numbers. Only extract what is explicitly stated.
    - For "sga": list the SG&A row, or the Sales & Marketing row and the General &
      Administrative row as separate lines when the filing prints them separately.
    - For "interest_expense": gross interest on debt (positive). Go to footnotes
      for the breakout if only net interest is on the I/S.
    - For "cfo": use the total "Net cash provided by operating activities".
    - For "net_income": use TOTAL CONSOLIDATED net income (includes noncontrolling
      interests; after tax). NEVER use "net income attributable to
      common shareholders / to the parent", which is net of noncontrolling interests.
    - For "capex": the 'Purchases of PP&E' row and the 'Acquisitions/intangible
      asset purchases' row(s) from the investing section, each its own line. Do
      NOT include securities. Absolute value.
    - For "change_in_working_capital": every individual asset/liability change
      row from the CFS operating section, one line per row. SIGNED per CFS convention.
    - "gross_profit", "operating_income" and "net_income" are the printed
      subtotal rows. Python checks them against the component fields; they are
      read, never derived. "gross_profit" and "operating_income" are [] when
      the filing prints no such row. "net_income" is never [].

    BALANCE SHEET RULES (when requested):
    - "total_assets" and "total_liabilities_and_equity" are the printed total
      rows. Python checks each against the lines you mapped under it. Do NOT
      change any line to make the check pass: a gap means a row was misread,
      missed or listed twice, and it is reported as it is.
    - "other_" catch-all fields must capture ALL unmapped rows.
    - finance lease obligations are debt (current portion due within one year
      in "short_term_debt", long-term finance lease obligations in
      "long_term_debt"); operating lease obligations are not debt and go to the
      catch-all fields ("other_current_liabilities" and
      "other_non_current_liabilities").
    - "noncontrolling_interest_nonredeemable" and "noncontrolling_interest_redeemable"
      are memos, each copied from its own printed row ([] if the filing prints none).
      Keep them in their own fields. Each is already inside another line; never
      add it to any total.

    If the user says "skip the balance sheet", set latest_balance_sheet to {{}}.""")


# ===========================================================================
# PASS 2: Non-Recurring Item Analysis — schema & prompt
# ===========================================================================

_NRI_SCHEMA = {
    "non_recurring_items": [
        {
            "year": "int — fiscal year the item affects",
            "description": "string — precise description of the item",
            "amount": "number — the ONE figure printed in the filing, positive, exactly as printed, in the unit printed with it or stated for its table. Never converted: Python reads 'units' and converts.",
            "line_item": "string — Income Statement field where this item is embedded. Must be one of: cost_of_revenue | sga | rd_expense | depreciation_amortization | other_operating_expense | other_non_operating",
            "direction": "string — 'add_back' (one-time expense to remove) or 'remove' (one-time gain to strip)",
            "category": "string — restructuring | impairment | litigation | gain_loss_asset_sale | acquisition_costs | covid | other",
            "confidence": "string — high | medium | low",
            "source": "string — filing reference, e.g. 'Note 8 — Restructuring Charges'",
            "page": "int — the 1-based PDF page the figure is printed on",
            "units": {
                "printed": "string — the words printed that state the unit of this figure, copied exactly: the figure with the scale word printed right after it (e.g. '$0.7 billion'), or the unit statement of the statement or table the figure is printed in (e.g. '(in millions, except per share data)')",
                "page": "int — the 1-based PDF page those words are printed on",
            },
        }
    ]
}

_NRI_SCHEMA_STR = json.dumps(_NRI_SCHEMA, indent=2)

_NRI_SYSTEM_PROMPT = textwrap.dedent(f"""\
    You are a senior financial analyst specializing in earnings quality analysis.
    Your task is to identify NON-RECURRING, one-time, unusual, or infrequent items
    from a 10-K/10-Q filing that distort the company's recurring earnings.

    You will receive:
    1. The full 10-K/10-Q PDF filing (to read MD&A and Notes to Financial Statements)
    2. A summary of the extracted Income Statement (to anchor your findings)

    OUTPUT: Return ONLY a valid JSON object. No markdown fences, no explanation.
    The first character of your response must be {{.

    SCHEMA:
    {_NRI_SCHEMA_STR}

    WHAT TO LOOK FOR (read MD&A and Notes thoroughly):
    - Restructuring / severance / workforce reduction charges
    - Goodwill or asset impairment write-downs
    - Gains or losses on sale of assets, business units, or investments
    - Legal settlements, litigation charges or recoveries
    - Acquisition / integration / transaction costs
    - One-time regulatory charges or fines
    - Items explicitly called out in MD&A as non-recurring or unusual

    RULES:
    - Copy each amount as printed; never convert, add, subtract or net figures;
      one item is one printed figure.
    - For "line_item": use the EXACT field name from the Income Statement where
      the item is embedded: cost_of_revenue | sga | rd_expense |
      depreciation_amortization | other_operating_expense | other_non_operating
    - For "direction":
        "add_back" = one-time EXPENSE that inflated costs → remove to get clean earnings
        "remove"   = one-time GAIN that inflated income → strip to get clean earnings
    - Only flag items with clear evidence in the filing. Do NOT guess.
    - Use the provided I/S summary to verify amounts are plausible relative
      to the line item totals.
    - If no non-recurring items are found, return: {{"non_recurring_items": []}}""")


# ---------------------------------------------------------------------------
# Printed lines: the model copies rows, Python adds them
# ---------------------------------------------------------------------------
# Rule 1, and the user's decision of 2026-10-02 (backlog item 56, option A): every
# Pass 1 figure arrives as the list of printed rows that make it up, and the ONE
# function below turns a list into its figure. Neither route reads a figure any
# other way, so no sum is the model's and no absent key becomes a zero.

class Pass1ShapeError(ValueError):
    """A Pass 1 answer with an absent key or a malformed printed line.

    `problems` holds every one found, each naming the field, the year and the line
    index, so route A can send them all back to the model in one retry and route B
    can list them all in one `check`. A ValueError, so every caller that stops on a
    bad answer stops on this one too.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = list(problems)
        super().__init__(
            f"the Pass 1 answer cannot be used. {len(self.problems)} problem(s):\n"
            + "\n".join(f"  - {p}" for p in self.problems)
        )


def _is_json_int(value: object) -> bool:
    """True for a JSON integer. A bool is not one, although Python says it is."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value: object) -> bool:
    """True for a finite JSON number. `json` accepts NaN and Infinity; we do not.

    A JSON integer too large for a float is not one either: `math.isfinite` raises
    OverflowError on it, and that would end the run in a traceback instead of a
    problem that names the field, the year and the line (review F4).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _shown(value: object) -> str:
    """`value` for a problem message. An integer too large for a float is described
    by its size, not printed: its repr can run to thousands of digits."""
    if _is_json_int(value) and isinstance(value, int) and value.bit_length() > 1024:
        return f"an integer of {value.bit_length()} bits, too large for a float"
    return repr(value)


def printed_line_problems(lines: object) -> list[str]:
    """Every problem with one field's list of printed lines; [] when it is usable.

    A line is a JSON object with a non-empty string `label`, a finite number
    `value` and a positive integer `page`. Each problem names the line by its
    0-based index; the caller adds the field and the year.
    """
    if not isinstance(lines, list):
        return [(
            f"must be a list of printed lines (label, value, page); [] means the "
            f"filing prints no such row. Got {type(lines).__name__} {lines!r}."
        )]
    problems: list[str] = []
    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            problems.append(
                f"line {index}: must be a JSON object with label, value and page, "
                f"got {type(line).__name__} {line!r}.",
            )
            continue
        for key in ("label", "value", "page"):
            if key not in line:
                problems.append(f"line {index}: key '{key}' is absent.")
        if "label" in line and (not isinstance(line["label"], str) or not line["label"].strip()):
            problems.append(
                f"line {index}: 'label' must be the row's label as printed, a "
                f"non-empty string, got {line['label']!r}.",
            )
        if "value" in line and not _is_finite_number(line["value"]):
            problems.append(
                f"line {index}: 'value' must be a finite JSON number, got {_shown(line['value'])}.",
            )
        if "page" in line and (not _is_json_int(line["page"]) or line["page"] < 1):
            problems.append(
                f"line {index}: 'page' must be a positive integer (a 1-based PDF "
                f"page), got {line['page']!r}.",
            )
    return problems


def figure_from_printed_lines(lines: object, field: str, where: str) -> float:
    """The figure a field's printed lines make: their values, added together.

    The one place a Pass 1 figure is formed, for both routes. An empty list is 0,
    because it is the answer "the filing prints no such row". A malformed list
    stops, naming `where` (the year or the balance sheet), the field and the line.

    Raises:
        Pass1ShapeError: when any line is malformed.
    """
    problems = printed_line_problems(lines)
    if problems or not isinstance(lines, list):
        raise Pass1ShapeError([f"{where}, '{field}': {p}" for p in problems])
    return math.fsum(float(line["value"]) for line in lines)


def check_row_from_printed_lines(lines: object, field: str, where: str) -> float | None:
    """A check row's printed figure, or None when its list is empty.

    For the five rows read only to check the reading (gross_profit,
    operating_income, total_assets, total_liabilities_and_equity; net_income is a
    figure and goes through figure_from_printed_lines). An empty list here is not
    a printed 0: the check either skips and says "not printed" (gross profit,
    operating income) or fails and says "not extracted" (the two totals). A 0 the
    filing never printed must not appear as a printed figure (rule 3; review F1, F2).

    Raises:
        Pass1ShapeError: when any line is malformed.
    """
    if isinstance(lines, list) and not lines:
        return None
    return figure_from_printed_lines(lines, field, where)


# ---------------------------------------------------------------------------
# Printed unit statements: the model copies them, Python reads the scale
# ---------------------------------------------------------------------------
# Backlog item 44, on the user's approval of 2026-10-04 (rule 1, option C applied to
# units). Filings print in different units: Walmart "(Amounts in millions, except
# per share data)", Chipotle "(in thousands, except per share data)", Okta "(dollars
# in millions, shares in thousands, except per share data)". The model copies two
# such statements, each with its page: `units` for the money figures and
# `share_units` for the diluted share count. Python reads the scale word in each
# (`printed_scale`), the page check confirms each text on its page, and
# `convert_filing_to_millions` converts every figure once. The model returns no
# scale word of its own and converts nothing.

# One printed unit, in millions, for each scale word the reader accepts. Rule 2: a
# table of numbers. A Fraction, so that the conversion divides by 1,000 (thousands)
# or multiplies by 1,000 (billions) in one operation on a whole number, never
# multiplies by 0.001, which has no exact binary form.
_SCALE_IN_MILLIONS: dict[str, Fraction] = {
    "thousands": Fraction(1, 1000),
    "millions": Fraction(1),
    "billions": Fraction(1000),
}

# "in thousands", "in millions", "in billions", in any letter case (the text is
# casefolded first). The words before it, back to the previous clause, are the
# clause's subject: "dollars in millions", "shares in thousands", "in millions".
_SCALE_CLAUSE = re.compile(r"\bin\s+(thousands|millions|billions)\b")
# "per share" (and "per-share") excepts only per-share figures, never the share count.
_PER_SHARE = re.compile(r"\bper[\s-]+shares?\b")
_SHARE_WORD = re.compile(r"\bshares?\b")
_EXCEPT_WORD = re.compile(r"\bexcept\b")
# "in millions of dollars": the word after "of" names the figures, as a subject does.
_OF_WORD = re.compile(r"\s+of\s+(\$|\w+)")
_MONEY_WORD = re.compile(r"\$|\bdollars?\b")
# A subject made only of these words states the unit of every figure, money and
# shares alike, and so does a clause with no subject at all ("(In millions)", the
# L3Harris 10-K 2023-12-29 page 17). Only a word a filing in 10K_filings/ prints in
# that position is listed:
# - "amounts": Walmart 10-K 2026-01-31 page 21, "(Amounts in millions, except per
#   share data)".
_GENERIC_SUBJECT_WORDS: frozenset[str] = frozenset({"amounts"})

UnitOf = Literal["money figures", "share count"]


@dataclass(frozen=True)
class PrintedScale:
    """A scale word read from a printed unit statement, and what one printed unit
    of it is in millions."""

    word: str
    in_millions: Fraction


@dataclass(frozen=True)
class _ScaleClause:
    """One "<subject> in <scale>" clause of a printed unit statement."""

    word: str
    subject: str
    mentions_money: bool
    mentions_shares: bool
    generic: bool


def _unit_statement_clauses(printed: str) -> tuple[list[_ScaleClause], str]:
    """The scale clauses of a printed unit statement, and its exception text.

    The text is casefolded and cut at commas, semicolons and parentheses. In each
    piece, the words after "except" are exception text, and so is every later piece
    that holds no scale word ("except share, per share and ratio data" is one list).
    Each "in <scale>" outside the exception text is a clause, and its subject is the
    words before it back to the previous clause.

    Raises:
        ValueError: a scale word is printed inside the exception text, whose meaning
            ("except X in millions") this reader does not decide.
    """
    clauses: list[_ScaleClause] = []
    exception_parts: list[str] = []
    in_exception = False
    for piece in re.split(r"[,;()]", printed.casefold()):
        head, *tail = _EXCEPT_WORD.split(piece, maxsplit=1)
        if tail:
            in_exception = True
            exception_parts.append(tail[0])
        elif in_exception and not _SCALE_CLAUSE.search(piece):
            exception_parts.append(piece)
            continue
        previous_end = 0
        for match in _SCALE_CLAUSE.finditer(head):
            # The subject, and an "of <word>" just after the scale word ("in
            # millions of dollars"), say which figures the clause is about.
            of_word = _OF_WORD.match(head, match.end())
            subject = _PER_SHARE.sub(" ", head[previous_end:match.start()]) + (
                f" {of_word.group(1)}" if of_word else ""
            )
            previous_end = match.end()
            mentions_money = _MONEY_WORD.search(subject) is not None
            mentions_shares = _SHARE_WORD.search(subject) is not None
            clauses.append(_ScaleClause(
                word=match.group(1),
                subject=subject,
                mentions_money=mentions_money,
                mentions_shares=mentions_shares,
                generic=(not mentions_money and not mentions_shares
                         and set(re.findall(r"\w+", subject)) <= _GENERIC_SUBJECT_WORDS),
            ))
    exception_text = " ".join(exception_parts)
    if _SCALE_CLAUSE.search(exception_text):
        raise ValueError(
            "it prints a scale word inside its exception ('except ...'), and which "
            "figures that scale applies to is not read here",
        )
    return clauses, exception_text


def _one_scale(words: set[str], unit_of: UnitOf) -> str | None:
    """The one scale word in `words`; None when there is none; a stop when two differ."""
    if len(words) > 1:
        raise ValueError(
            f"it states {len(words)} different scales ({', '.join(sorted(words))}) "
            f"for the {unit_of}, so which one applies is not known",
        )
    return next(iter(words)) if words else None


def _named_outside_its_clauses(
    printed: str, named: re.Pattern[str], clauses: list[_ScaleClause],
) -> bool:
    """True when the statement, its "per share" phrases removed, names `named`
    (dollars, or shares) more often than the subjects of its scale clauses do: the
    word is printed somewhere else, in a form this reader does not name ("excluding
    share data", "other than shares", "shares in actual numbers")."""
    everywhere = len(named.findall(_PER_SHARE.sub(" ", printed.casefold())))
    in_clauses = sum(len(named.findall(clause.subject)) for clause in clauses)
    return everywhere > in_clauses


def printed_scale(printed: str, unit_of: UnitOf) -> PrintedScale:
    """The scale of the money figures or of the share count, read from the words of
    a printed unit statement. The one place a scale is read, for both routes.

    A clause whose subject names dollars (or "$") states the money scale; one whose
    subject names shares states the share scale; one with no subject, or only
    "amounts", states both ("(Amounts in millions, except per share data)"). A
    clause naming its subject wins over one that does not. "per share" (and
    "per-share") excepts only per-share figures, so it is removed before anything
    else is read. After that, shares are read in one form only: a "<shares> in
    <scale>" clause ("shares in thousands", "dollar and share amounts in
    thousands"). A statement that names shares anywhere else stops the share
    scale: in an exception ("except share and per share data", "except shares"),
    or in words this reader does not name ("excluding share data", "other than
    shares", "shares in actual numbers"). Dollars are read the same way for the
    money scale. Scale words are "thousands", "millions" and "billions", in any
    letter case.

    Never falls back to millions (rule 3): every case not read stops.

    Raises:
        ValueError: no scale word states the unit of `unit_of`, two scales do, the
            statement names shares (or dollars) outside a scale clause, or a scale
            word is printed inside the exception text. The message says which, and
            the caller adds the field, the text and the page.
    """
    clauses, exception_text = _unit_statement_clauses(printed)
    if unit_of == "money figures":
        if _named_outside_its_clauses(printed, _MONEY_WORD, clauses):
            raise ValueError(
                "it names dollars outside a clause of the form '<dollars> in <scale>', "
                "so which scale the money figures take is not read here. Cite the "
                "words that state the unit of the money figures",
            )
        word = _one_scale({c.word for c in clauses if c.mentions_money}, unit_of)
    else:
        if _SHARE_WORD.search(_PER_SHARE.sub(" ", exception_text)):
            raise ValueError(
                "it excepts the share count from its scale ('except "
                f"{' '.join(exception_text.split())}'), so it does not state the unit of the "
                "share count. Cite the words that do",
            )
        if _named_outside_its_clauses(printed, _SHARE_WORD, clauses):
            raise ValueError(
                "it names shares outside a clause of the form '<shares> in <scale>', so "
                "whether the share count takes a scale it states is not read here. "
                "Cite the words that state the unit of the share count",
            )
        word = _one_scale({c.word for c in clauses if c.mentions_shares}, unit_of)
    if word is None:
        word = _one_scale({c.word for c in clauses if c.generic}, unit_of)
    if word is None:
        raise ValueError(
            f"it holds no scale word (thousands, millions or billions) that states "
            f"the unit of the {unit_of}",
        )
    return PrintedScale(word=word, in_millions=_SCALE_IN_MILLIONS[word])


def _whitespace_normalised(text: str) -> str:
    """Every run of whitespace (a line break included) made one space, stripped."""
    return " ".join(text.split())


# Inline unit scale for Pass 2: optional $, one number (commas/decimal allowed),
# one or more spaces, then thousand, million or billion (with optional s).
_INLINE_SCALE = re.compile(
    r"^\$?\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s+(thousands?|millions?|billions?)$"
)


def _is_inline_scale(printed: str) -> bool:
    """True when `printed` matches the Pass 2 inline unit form."""
    return _INLINE_SCALE.match(_whitespace_normalised(printed).casefold()) is not None


def pass2_amount_scale(printed: str, amount: float) -> PrintedScale:
    """The scale of one Pass 2 non-recurring item. The ONE place a Pass 2 scale
    is read (rule 2).

    Two forms, and nothing else:
    - Inline form: optional $, one number (commas and decimal point allowed),
      one or more spaces, then thousand, million or billion, with an optional s,
      and nothing after it. The scale is that word, mapped through _SCALE_IN_MILLIONS
      (using the plural key: billion reads as billions). The number in the text
      must equal `amount`. If it does not, stop and name both.
    - Statement form: anything else goes to printed_scale(printed, "money figures"),
      the P14a reader, unchanged. Its stops apply as they are.

    Raises:
        ValueError: the text states no scale word, an invalid scale, or an inline
            number that does not equal `amount`.
    """
    norm = _whitespace_normalised(printed).casefold()
    match = _INLINE_SCALE.match(norm)
    if match:
        text_num = float(match.group(1).replace(",", ""))
        if text_num != amount:
            raise ValueError(
                f"the number in the inline unit text ({text_num}) does not "
                f"equal the item amount ({amount})"
            )
        word = match.group(2)
        if not word.endswith("s"):
            word += "s"
        return PrintedScale(word=word, in_millions=_SCALE_IN_MILLIONS[word])
    return printed_scale(printed, "money figures")


@dataclass(frozen=True)
class UnitStatement:
    """One printed unit statement of a Pass 1 answer: the words, their page, and the
    scale Python read in them."""

    field: str
    printed: str
    page: int
    scale: PrintedScale


@dataclass(frozen=True)
class FilingUnits:
    """The two printed unit statements of one filing's Pass 1 answer: `units` (the
    money figures) and `share_units` (the diluted share count)."""

    money: UnitStatement
    shares: UnitStatement


def _unit_statement_problems(data: dict[str, Any]) -> list[str]:
    """Every problem with the two printed unit statements of a Pass 1 answer.

    Each must be a JSON object with a non-empty string `printed` and a positive
    integer `page`, and its scale must be readable (`printed_scale`). A problem
    names the field, the text and the page.
    """
    problems: list[str] = []
    for key, unit_of in _UNIT_STATEMENT_FIELDS:
        if key not in data:
            problems.append(
                f"key 'pass1.{key}' is absent. It is the statement of the unit of the "
                f"{unit_of}, exactly as printed, with its page: "
                '{"printed": ..., "page": ...}.',
            )
            continue
        statement = data[key]
        if not isinstance(statement, dict):
            problems.append(
                f"'pass1.{key}' must be a JSON object {{\"printed\": ..., \"page\": ...}}: "
                f"the statement of the unit of the {unit_of} exactly as printed, and its "
                f"page. Got {type(statement).__name__} {statement!r}.",
            )
            continue
        shape: list[str] = [
            f"'pass1.{key}': key '{sub}' is absent." for sub in ("printed", "page")
            if sub not in statement
        ]
        if "printed" in statement and (
            not isinstance(statement["printed"], str) or not statement["printed"].strip()
        ):
            shape.append(
                f"'pass1.{key}.printed' must be the statement of units exactly as "
                f"printed, a non-empty string, got {statement['printed']!r}.",
            )
        if "page" in statement and (not _is_json_int(statement["page"]) or statement["page"] < 1):
            shape.append(
                f"'pass1.{key}.page' must be a positive integer (a 1-based PDF page), "
                f"got {statement['page']!r}.",
            )
        if shape:
            problems += shape
            continue
        try:
            printed_scale(statement["printed"], unit_of)
        except ValueError as exc:
            problems.append(
                f"'pass1.{key}' {statement['printed']!r} (page {statement['page']}): "
                f"the scale of the {unit_of} cannot be read: {exc}.",
            )
    return problems


def _filing_units(data: dict[str, Any]) -> FilingUnits:
    """The two unit statements of a Pass 1 answer that `pass1_problems` has passed."""
    def statement(key: str, unit_of: UnitOf) -> UnitStatement:
        return UnitStatement(
            field=key,
            printed=data[key]["printed"],
            page=data[key]["page"],
            scale=printed_scale(data[key]["printed"], unit_of),
        )

    return FilingUnits(
        money=statement("units", "money figures"),
        shares=statement("share_units", "share count"),
    )


def _line_field_problems(
    entry: dict[str, Any],
    label: str,
    fields: tuple[str, ...],
    never_empty: tuple[str, ...],
) -> list[str]:
    """Every absent key and every malformed line among `fields` of one entry, and
    every field in `never_empty` given as `[]`."""
    problems: list[str] = []
    for key in fields:
        if key not in entry:
            problems.append(
                f"{label}: key '{key}' is absent. Write [] only for a row the "
                "filing does not print.",
            )
            continue
        problems += [f"{label}, '{key}': {p}" for p in printed_line_problems(entry[key])]
        if key in never_empty and entry[key] == []:
            problems.append(
                f"{label}, '{key}': is [], and this row is never absent from a "
                "filing. Read the printed row.",
            )
    return problems


def pass1_problems(data: object) -> list[str]:
    """Every shape problem in a Pass 1 answer; [] when it can be parsed.

    Both routes run this before any figure is formed: route A's parser raises
    Pass1ShapeError on a non-empty result, and route B's loader prefixes each
    problem with the session file and the filing. An absent key is never read as
    zero (rule 3). `latest_balance_sheet` must be present: `{}` is the answer for
    "skip the balance sheet", and anything else must carry every key. The two
    printed unit statements, `units` and `share_units`, must be present, well
    formed, and each must state a scale Python can read (`printed_scale`): a
    statement whose scale cannot be read stops, and never falls back to millions.
    """
    if not isinstance(data, dict):
        return [f"the Pass 1 answer must be a JSON object, got {type(data).__name__}."]
    problems: list[str] = _unit_statement_problems(data)

    if "historical_years" not in data:
        problems.append("key 'pass1.historical_years' is absent.")
    elif not isinstance(data["historical_years"], list) or not data["historical_years"]:
        problems.append("'pass1.historical_years' must be a non-empty list.")
    else:
        for position, entry in enumerate(data["historical_years"]):
            if not isinstance(entry, dict):
                problems.append(f"historical_years[{position}] must be a JSON object.")
                continue
            if "year" not in entry:
                label = f"historical_years[{position}]"
                problems.append(f"{label}: key 'year' is absent.")
            elif not _is_json_int(entry["year"]):
                label = f"historical_years[{position}]"
                problems.append(
                    f"{label}: 'year' must be an integer, got {entry['year']!r}.",
                )
            else:
                label = f"year {entry['year']}"
            problems += _line_field_problems(
                entry, label, PASS1_YEAR_LINE_FIELDS, PASS1_YEAR_NEVER_EMPTY_FIELDS,
            )

    if "latest_balance_sheet" not in data:
        problems.append(
            "key 'pass1.latest_balance_sheet' is absent. It is {} when the balance sheet "
            "is skipped.",
        )
        return problems
    balance = data["latest_balance_sheet"]
    if not isinstance(balance, dict):
        problems.append("'pass1.latest_balance_sheet' must be a JSON object.")
        return problems
    if not balance:
        return problems  # {}: the balance sheet was not asked for
    bs_label = "balance sheet"
    if "year" not in balance:
        problems.append("balance sheet: key 'year' is absent.")
    elif not _is_json_int(balance["year"]) or balance["year"] <= 0:
        problems.append(
            f"balance sheet: 'year' must be a positive integer, got {balance['year']!r}.",
        )
    else:
        bs_label = f"balance sheet {balance['year']}"
    problems += _line_field_problems(balance, bs_label, PASS1_BALANCE_SHEET_LINE_FIELDS, ())
    return problems


# ---------------------------------------------------------------------------
# Checks: the printed subtotals and totals against Python's sums
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _YearFigures:
    """One Pass 1 year. `figures` holds every line field but the two optional check
    rows, summed. `gross_profit` and `operating_income` are the printed check rows,
    None when the answer's list was empty: the filing prints no such row, and that
    check is skipped and says so. `lines` is the year's answer as read, so a failed
    check can name the rows Python added."""

    year: int
    figures: dict[str, float]
    gross_profit: float | None
    operating_income: float | None
    lines: dict[str, Any]


@dataclass(frozen=True)
class _CheckFailure:
    """One failed check, in two wordings.

    `message` is for a human and for a Claude Code session following the skill:
    for an arithmetic check, the printed figure, Python's sum, the gap and the
    tolerance; for a page check, the line's label, value and page and why it is
    not confirmed. `check`, the CLI and route A's console print it.
    `retry_message` goes back to the model in route A's retry: it names the check,
    the side and the rows Python added, or the line by label, field and page, and
    states no value and no amount. A model told the exact gap can add a row of
    that size (review F7; the orchestrator's round 2 decision 6); the page check
    now looks for such a row, and a retry that states no figure still gives the
    model none to aim at.
    """

    message: str
    retry_message: str


# The component fields each check adds, in the order the formula reads.
_GROSS_PROFIT_FIELDS: tuple[str, ...] = ("revenue", "cost_of_revenue")
_OPERATING_INCOME_FIELDS: tuple[str, ...] = (
    "revenue", "cost_of_revenue", "sga", "rd_expense", "other_operating_expense",
)
_NET_INCOME_FIELDS: tuple[str, ...] = _OPERATING_INCOME_FIELDS + (
    "interest_income", "interest_expense", "other_non_operating", "tax_expense",
)
_ASSET_FIELDS: tuple[str, ...] = (
    "cash", "short_term_investments", "accounts_receivable", "inventory",
    "other_current_assets", "ppe_net", "goodwill", "intangible_assets",
    "other_non_current_assets",
)
_LIABILITY_AND_EQUITY_FIELDS: tuple[str, ...] = (
    "accounts_payable", "accrued_liabilities", "other_current_liabilities",
    "short_term_debt", "long_term_debt", "other_non_current_liabilities", "total_equity",
)

_RETRY_HINT = (
    "A row was misread, missed, or listed under two fields; read those rows "
    "again from the filing."
)


def _rows_listed(lines: dict[str, Any], fields: tuple[str, ...]) -> str:
    """The rows listed under `fields`, by label, field and page. No values."""
    rows = [
        f"'{line['label']}' ({field}, page {line['page']})"
        for field in fields for line in lines[field]
    ]
    return "; ".join(rows) if rows else "no rows"


def _validate_extracted_data(
    years: list[_YearFigures],
    balance: BalanceSheet | None,
    balance_lines: dict[str, Any] | None,
    fail_pct: float = 0.5,
) -> list[_CheckFailure]:
    """Check the reading: printed subtotals and totals against Python's sums.

    Income statement, each year: the printed gross profit, operating income and
    net income rows against the figures the component fields give, failing above
    `fail_pct` percent. Gross profit and operating income are skipped, and say so,
    when the filing prints no such row. Balance sheet: the printed total assets row
    against the mapped asset lines, and the printed total liabilities and equity
    row against the mapped liability and equity lines (the noncontrolling interest
    memos are in neither), failing when the difference exceeds 1 in the filing's
    units, or when the total was not extracted (`printed_total_status`). The
    figures here are as printed, before the conversion to millions, so a
    difference is already in printed units.

    A check is a check, never a repair: nothing here changes a figure. Returns one
    _CheckFailure per failure (empty = all passed); neither wording asks for a
    figure to be changed to pass.
    """
    print(f"\n{'='*65}")
    print("EXTRACTED DATA VALIDATION — ARITHMETIC CHECK")
    print(f"{'='*65}")
    print(f"  {'Year':<6}  {'Field':<18}  {'Printed':>10}  {'Derived':>10}  {'Diff':>9}  Status")
    print(f"  {'-'*64}")

    failures: list[_CheckFailure] = []

    for yr in sorted(years, key=lambda y: y.year):
        f = yr.figures
        year = yr.year
        rev, cogs = f["revenue"], f["cost_of_revenue"]
        sga, rd, other_opex = f["sga"], f["rd_expense"], f["other_operating_expense"]
        int_exp, int_inc = f["interest_expense"], f["interest_income"]
        other_nop, tax = f["other_non_operating"], f["tax_expense"]

        # DA is broken out of other_opex in the IS model (net zero on EBIT),
        # so the raw-JSON check excludes DA to avoid double-counting.
        gp_derived   = rev - cogs
        ebit_derived = gp_derived - sga - rd - other_opex
        ni_derived   = ebit_derived + int_inc - int_exp + other_nop - tax

        # (label, field, printed row or None, derived, formula with figures,
        #  formula with field names only, the component fields)
        checks: list[tuple[str, str, float | None, float, str, str, tuple[str, ...]]] = [
            ("Gross Profit", "gross_profit", yr.gross_profit, gp_derived,
             f"revenue({rev:,.0f}) - cost_of_revenue({cogs:,.0f})",
             "revenue - cost_of_revenue", _GROSS_PROFIT_FIELDS),
            ("Oper. Income", "operating_income", yr.operating_income, ebit_derived,
             f"revenue({rev:,.0f}) - cost_of_revenue({cogs:,.0f}) - sga({sga:,.0f}) - rd_expense({rd:,.0f}) - other_operating_expense({other_opex:,.0f})",
             "revenue - cost_of_revenue - sga - rd_expense - other_operating_expense",
             _OPERATING_INCOME_FIELDS),
            ("Net Income", "net_income", f["net_income"], ni_derived,
             f"operating_income({ebit_derived:,.0f}) + interest_income({int_inc:,.0f}) - interest_expense({int_exp:,.0f}) + other_non_operating({other_nop:,.0f}) - tax_expense({tax:,.0f})",
             ("revenue - cost_of_revenue - sga - rd_expense - other_operating_expense "
              "+ interest_income - interest_expense + other_non_operating - tax_expense"),
             _NET_INCOME_FIELDS),
        ]

        for label, field, stated, derived, formula, formula_names, fields in checks:
            if stated is None:
                print(f"  {year:<6}  {label:<18}  {'(none)':>10}  {derived:>10,.0f}  "
                      f"{'':>9}  SKIP: not printed (the filing prints no {field} row)")
                continue
            diff = stated - derived
            if diff == 0:
                status = "OK"
            else:
                base = abs(stated) if stated != 0 else abs(derived)
                status = "FAIL" if abs(diff) / base * 100 > fail_pct else "OK"
            print(f"  {year:<6}  {label:<18}  {stated:>10,.0f}  {derived:>10,.0f}  {diff:>+9,.0f}  {status}")
            if status == "FAIL":
                failures.append(_CheckFailure(
                    message=(
                        f"[{year}] {label}: printed={stated:,.0f} but the component "
                        f"fields give {derived:,.0f} (diff={diff:+,.0f}; the check "
                        f"allows {fail_pct}%). Derivation: {formula} = {derived:,.0f}. "
                        f"{_RETRY_HINT}"
                    ),
                    retry_message=(
                        f"[{year}] {label}: the printed {field} row "
                        f"({_rows_listed(yr.lines, (field,))}) does not agree with "
                        f"{formula_names}, each field taken as Python's total of its rows. "
                        f"Rows Python added: {_rows_listed(yr.lines, fields)}. {_RETRY_HINT}"
                    ),
                ))

    if balance is not None and balance_lines is not None:
        bs = balance
        assets_formula = (
            f"cash({bs.cash_and_equivalents:,.0f}) + short_term_investments({bs.short_term_investments:,.0f}) "
            f"+ accounts_receivable({bs.accounts_receivable:,.0f}) + inventory({bs.inventory:,.0f}) "
            f"+ other_current_assets({bs.other_current_assets:,.0f}) + ppe_net({bs.ppe_net:,.0f}) "
            f"+ goodwill({bs.goodwill:,.0f}) + intangible_assets({bs.intangible_assets:,.0f}) "
            f"+ other_non_current_assets({bs.other_non_current_assets:,.0f})"
        )
        le_formula = (
            f"accounts_payable({bs.accounts_payable:,.0f}) + accrued_liabilities({bs.accrued_liabilities:,.0f}) "
            f"+ other_current_liabilities({bs.other_current_liabilities:,.0f}) + short_term_debt({bs.short_term_debt:,.0f}) "
            f"+ long_term_debt({bs.long_term_debt:,.0f}) + other_non_current_liabilities({bs.other_non_current_liabilities:,.0f}) "
            f"+ total_equity({bs.total_equity:,.0f})"
        )
        for label, side, field, printed, mapped, difference, formula, fields in (
            ("Total Assets", "assets", "total_assets", bs.printed_total_assets,
             bs.total_assets, bs.printed_total_assets_difference, assets_formula,
             _ASSET_FIELDS),
            ("Total L + E", "liabilities and equity", "total_liabilities_and_equity",
             bs.printed_total_liabilities_and_equity, bs.total_liabilities_and_equity,
             bs.printed_total_liabilities_and_equity_difference, le_formula,
             _LIABILITY_AND_EQUITY_FIELDS),
        ):
            # As printed: the difference is in printed units, the threshold's own.
            status = printed_total_status(difference)
            printed_text = "(none)" if printed is None else f"{printed:,.0f}"
            diff_text = "" if difference is None else f"{difference:+,.0f}"
            print(f"  {bs.year:<6}  {label:<18}  {printed_text:>10}  {mapped:>10,.0f}  {diff_text:>9}  {status}")
            if status == "OK":
                continue
            if printed is None:
                failures.append(_CheckFailure(
                    message=(
                        f"[{bs.year}] Balance sheet {label}: the printed {field} row was "
                        "not extracted (the answer lists no row for it), so the "
                        f"{side} side cannot be checked. Every balance sheet prints "
                        "this total; read its row."
                    ),
                    retry_message=(
                        f"[{bs.year}] Balance sheet, {side} side: the printed {field} "
                        "row was not extracted (the answer lists no row for it). "
                        "Every balance sheet prints this total; read its row."
                    ),
                ))
                continue
            failures.append(_CheckFailure(
                message=(
                    f"[{bs.year}] Balance sheet {label}: printed {field}={printed_text} "
                    f"but the mapped lines sum to {mapped:,.0f} (diff={diff_text}; the "
                    f"check allows {BALANCE_CHECK_TOLERANCE:,.0f} in the filing's "
                    f"units, for rounding). Mapped: {formula}. {_RETRY_HINT}"
                ),
                retry_message=(
                    f"[{bs.year}] Balance sheet, {side} side: the printed {field} row "
                    f"({_rows_listed(balance_lines, (field,))}) does not agree with "
                    f"Python's total of the rows listed under {', '.join(fields)}. Rows Python "
                    f"added: {_rows_listed(balance_lines, fields)}. {_RETRY_HINT}"
                ),
            ))

    print(f"\n{'='*65}")

    return failures


# ---------------------------------------------------------------------------
# Checks: each printed line looked up on the page it cites
# ---------------------------------------------------------------------------
# Backlog item 59 (the P11a review's F7): the arithmetic checks above cannot tell
# a row the filing printed from one the model wrote, if it balances. This check
# opens the PDF and looks for each line's label and figure on one text line of
# its cited page. It confirms a row is printed with that figure; it does not
# confirm the figure is in the right year's column, nor that a real row is listed
# under one field only (docs/3-architecture/extraction.md, "The page check").

# A figure as a statement prints it: an optional "(", an optional "$" with
# optional spaces, digits with optional thousands commas, an optional decimal
# part, an optional ")". The comma form must be whole groups of three.
_PRINTED_FIGURE = re.compile(r"\(?(?:\$\s*)?(?:\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?:\.\d+)?\)?")
# A dash standing alone on a text line is a printed zero.
_PRINTED_ZERO_DASHES: frozenset[str] = frozenset({"—", "–", "-"})


def _figure_magnitude(figure: str) -> float:
    """A printed figure without its commas, "$", spaces and parentheses."""
    return float(re.sub(r"[^\d.]", "", figure))


def _text_line_holds(text_line: str, magnitude: float) -> bool:
    """True when one figure on `text_line` has this magnitude. A magnitude of 0 is
    also held by a dash standing alone."""
    if any(_figure_magnitude(m.group(0)) == magnitude
           for m in _PRINTED_FIGURE.finditer(text_line)):
        return True
    return magnitude == 0 and any(
        token in _PRINTED_ZERO_DASHES for token in text_line.split()
    )


def _normalised_text(text: str) -> str:
    """Remove every figure, casefold, turn each run of characters that is neither a
    letter nor a digit into one space, strip."""
    return re.sub(r"[\W_]+", " ", _PRINTED_FIGURE.sub("", text).casefold()).strip()


def printed_line_on_page(label: str, value: float, page_text: str) -> bool:
    """True when some text line of `page_text` holds `abs(value)` and the label.

    A text line L holds the value when one of its figures has that magnitude
    (signs and parentheses are not compared), or, for a value of 0, when it holds
    a dash standing alone. The label is found when its normalised text is not
    empty and is a substring of the normalised text of L, of the line above L
    joined to L by a space, or of L joined to the line below it by a space: a
    label may wrap onto a second text line. A joined form counts only when the
    label is not wholly inside the neighbouring line alone, so a label printed
    whole on the row above or below never takes L's figure. Normalised: figures
    removed, casefolded, every run of characters that is neither a letter nor a
    digit made one space, stripped; the same for the label and the page.

    Pure: no PDF, no I/O. docs/3-architecture/extraction.md states the rule.
    """
    wanted = _normalised_text(label)
    if not wanted:
        return False
    magnitude = abs(float(value))
    text_lines = page_text.splitlines()
    for index, text_line in enumerate(text_lines):
        if not _text_line_holds(text_line, magnitude):
            continue
        candidates = [text_line]
        # A joined form is for a label that wraps: neither half holds it whole.
        # A neighbour that holds the whole label is its own row, with its own figure.
        if index > 0 and wanted not in _normalised_text(text_lines[index - 1]):
            candidates.append(f"{text_lines[index - 1]} {text_line}")
        if index + 1 < len(text_lines) and wanted not in _normalised_text(text_lines[index + 1]):
            candidates.append(f"{text_line} {text_lines[index + 1]}")
        if any(wanted in _normalised_text(candidate) for candidate in candidates):
            return True
    return False


def _pdf_identity(pdf_bytes: bytes) -> str:
    """The PDF named by what both routes hold: its bytes. Route B's session file
    records the same sha256 beside the PDF's path."""
    return f"sha256 {hashlib.sha256(pdf_bytes).hexdigest()[:16]}… ({len(pdf_bytes):,} bytes)"


def _read_cited_pages(
    pdf_bytes: bytes, pages: set[int],
) -> tuple[int, dict[int, str | None]]:
    """The PDF's page count, and the text layer of each cited page within it.

    A cited page beyond the last page has no entry; the caller reports it. Each
    page is read once, however many lines cite it.

    Raises:
        ValueError: pdfplumber cannot open or read the PDF (it raises
            PdfminerException, or MalformedPDFException for a malformed page),
            naming the PDF by its sha256 and size.
    """
    import pdfplumber
    from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page_count = len(pdf.pages)
            texts: dict[int, str | None] = {
                page: pdf.pages[page - 1].extract_text()
                for page in sorted(pages) if page <= page_count
            }
    except (PdfminerException, MalformedPDFException) as exc:
        raise ValueError(
            f"the PDF {_pdf_identity(pdf_bytes)} cannot be opened by pdfplumber "
            f"({type(exc).__name__}: {exc}), so no printed line can be looked up on "
            "the page it cites. The run stops.",
        ) from exc
    return page_count, texts


def _printed_line_failure(
    where: str,
    field: str,
    index: int,
    line: dict[str, Any],
    page_count: int,
    page_texts: dict[int, str | None],
) -> _CheckFailure | None:
    """One printed line looked up on its cited page: None when found, else the
    failure. A page with no text layer is a failure, never a pass: a line that was
    not looked at is not confirmed (rule 3)."""
    label, value, page = line["label"], line["value"], line["page"]
    row = f"{where}, '{field}' line {index}"
    read_again = (
        "Read this row again from the filing, with its label as printed and the "
        "page it is printed on."
    )
    if page > page_count:
        return _CheckFailure(
            message=(
                f"{row}: '{label}' = {value:,} cites page {page}, but the PDF has "
                f"{page_count} pages. {read_again}"
            ),
            retry_message=(
                f"{row}: the row '{label}' cites page {page}, beyond the last page "
                f"of the filing ({page_count} pages). {read_again}"
            ),
        )
    text = page_texts[page]
    if text is None or not text.strip():
        return _CheckFailure(
            message=(
                f"{row}: '{label}' = {value:,} cannot be confirmed, because page "
                f"{page} has no text layer; the line was not looked for, and it is "
                "not confirmed."
            ),
            retry_message=(
                f"{row}: the row '{label}' cannot be confirmed on page {page}, "
                f"because that page has no text layer. {read_again}"
            ),
        )
    if printed_line_on_page(label, value, text):
        return None
    return _CheckFailure(
        message=(
            f"{row}: '{label}' = {value:,} was not found on page {page}: no text line "
            f"there holds both that label and that figure. {read_again}"
        ),
        retry_message=(
            f"{row}: the row '{label}' was not found on page {page}, the page it "
            f"cites. {read_again}"
        ),
    )


def _printed_line_failures(data: dict[str, Any], pdf_bytes: bytes) -> list[_CheckFailure]:
    """Look every printed line of a Pass 1 answer up on the page it cites.

    `data` is the parsed answer after `pass1_problems` has passed, so every key is
    read with `[]`. Every line field is walked: each historical year's, then the
    balance sheet's, the check rows and the noncontrolling interest memos
    included. Returns one _CheckFailure per line not found, in that order. Both
    routes call this, route A in `_run_financials_pass` and route B through
    `printed_line_page_failures`.

    Raises:
        ValueError: the PDF cannot be opened by pdfplumber.
    """
    cited: list[tuple[str, str, int, dict[str, Any]]] = []
    for entry in data["historical_years"]:
        where = f"year {entry['year']}"
        for field in PASS1_YEAR_LINE_FIELDS:
            cited += [(where, field, index, line) for index, line in enumerate(entry[field])]
    balance = data["latest_balance_sheet"]
    if balance:  # {}: the balance sheet was not asked for
        where = f"balance sheet {balance['year']}"
        for field in PASS1_BALANCE_SHEET_LINE_FIELDS:
            cited += [(where, field, index, line) for index, line in enumerate(balance[field])]

    page_count, page_texts = _read_cited_pages(pdf_bytes, {line["page"] for *_, line in cited})
    failures: list[_CheckFailure] = []
    for where, field, index, line in cited:
        failure = _printed_line_failure(where, field, index, line, page_count, page_texts)
        if failure is not None:
            failures.append(failure)
    print(f"  Printed lines looked up on their cited pages: {len(cited)} checked, "
          f"{len(cited) - len(failures)} found, {len(failures)} not confirmed.")
    return failures


# ---------------------------------------------------------------------------
# Checks: each printed unit statement looked up on the page it cites
# ---------------------------------------------------------------------------
# P14a. A unit statement is checked on the page it cites (`_read_cited_pages`), with
# one difference in consequence from a printed line: a printed line not found is
# shown and kept, but a unit statement not confirmed STOPS the run once route A's
# retries are spent, and stops route B's loader at once. A wrong scale moves every
# figure by a factor of 1,000, and nothing downstream can detect it.
#
# Two checks (review round 1, F1 and F6):
# - the statement is printed on its page as a whole: one parenthesised group, or
#   one whole text line, equal to the text the model returned with only its
#   whitespace normalised. The words of "(in thousands)" are on Okta's page 58,
#   inside "(dollars in millions, shares in thousands, except per share data)";
#   the statement "(in thousands)" is not, and it is not confirmed;
# - the statement is on a page of the figures it governs: `units` on a page that a
#   printed line of the income statement cites, `share_units` on the `units` page
#   or a page that a `diluted_shares` line cites. "(In thousands)" heads a
#   stock-award table on page 62 of the L3Harris 10-K 2026-01-02, whose statements
#   print in millions on page 35.

_UNIT_NOT_CONFIRMED_STOPS = (
    "A unit statement that is not confirmed stops the run: the scale read from it "
    "converts every figure to millions, a wrong scale moves every figure by a factor "
    "of 1,000, and nothing downstream can detect it."
)

# The income statement's line fields: the figures the `units` statement governs.
# `depreciation_amortization`, `cfo`, `capex`, `sbc` and `change_in_working_capital`
# are read from the cash flow statement, so their pages are not the income
# statement's.
_INCOME_STATEMENT_LINE_FIELDS: tuple[str, ...] = (
    "revenue", "cost_of_revenue", "gross_profit", "sga", "rd_expense",
    "other_operating_expense", "operating_income", "interest_expense",
    "interest_income", "other_non_operating", "tax_expense", "net_income",
    "diluted_shares",
)

# One parenthesised group of a page's text, with no parenthesis inside it.
_PARENTHESISED_GROUP = re.compile(r"\([^()]*\)")


def unit_statement_on_page(printed: str, page_text: str) -> bool:
    """True when `printed` is printed on the page as a whole printed unit.

    Only whitespace is normalised, on both sides (`_whitespace_normalised`): case,
    parentheses, commas and every other character are compared as they are. A
    statement in parentheses must equal one whole parenthesised group of the page's
    text, taken with its line breaks made spaces, so a statement that wraps onto a
    second text line is found, and so is one printed on the same text line as the
    column headings (L3Harris: "(In millions, except per share amounts) 2025 2024
    2023"). A statement with no parenthesis must equal one whole text line. A
    fragment of a longer statement is never found: "(in thousands)" is not found
    on a page that prints "(dollars in millions, shares in thousands, except per
    share data)".

    Pure: no PDF, no I/O.
    """
    wanted = _whitespace_normalised(printed)
    if not wanted:
        return False
    if "(" in wanted or ")" in wanted:
        groups = _PARENTHESISED_GROUP.findall(_whitespace_normalised(page_text))
        return wanted in groups
    return any(_whitespace_normalised(text_line) == wanted
               for text_line in page_text.splitlines())


def _unit_statement_pages_allowed(data: dict[str, Any]) -> dict[str, set[int]]:
    """For each unit statement, the pages it may cite: the pages of the figures it
    governs. `units`: every page a printed line of the income statement cites, in
    any year of the answer. `share_units`: the `units` page, and every page a
    `diluted_shares` line cites."""
    income_pages = {
        line["page"]
        for entry in data["historical_years"]
        for field in _INCOME_STATEMENT_LINE_FIELDS
        for line in entry[field]
    }
    diluted_pages = {
        line["page"] for entry in data["historical_years"] for line in entry["diluted_shares"]
    }
    return {
        "units": income_pages,
        "share_units": {data["units"]["page"]} | diluted_pages,
    }


# What each statement's allowed pages are, in the words of the failure message.
_PAGES_ALLOWED_ARE: dict[str, str] = {
    "units": "the pages the income statement's printed lines cite",
    "share_units": "the 'units' page and the pages the diluted share count's printed lines cite",
}


def _unit_statement_failures(data: dict[str, Any], pdf_bytes: bytes) -> list[_CheckFailure]:
    """Look both printed unit statements of a Pass 1 answer up on the pages they cite.

    `data` is the parsed answer after `pass1_problems` has passed. Returns one
    _CheckFailure per statement that cites a page outside the pages of the figures
    it governs (`_unit_statement_pages_allowed`), a page beyond the PDF, or a page
    with no text layer (a page not looked at is not confirmed; rule 3), or that is
    not printed on its page as a whole (`unit_statement_on_page`). Each message
    names the field, the text and the page.

    Raises:
        ValueError: the PDF cannot be opened by pdfplumber.
    """
    statements = [
        (key, unit_of, data[key]["printed"], data[key]["page"])
        for key, unit_of in _UNIT_STATEMENT_FIELDS
    ]
    pages_allowed = _unit_statement_pages_allowed(data)
    page_count, page_texts = _read_cited_pages(
        pdf_bytes, {page for *_, page in statements},
    )
    failures: list[_CheckFailure] = []
    for key, unit_of, printed, page in statements:
        copy_again = (
            f"Copy the statement of the unit of the {unit_of} again, word for word as "
            "the filing prints it, with the page it is printed on."
        )
        text = page_texts[page] if page <= page_count else None
        if page not in pages_allowed[key]:
            reason = (
                f"cites page {page}, which is not a page of the figures it states the "
                f"unit of: the pages allowed are {sorted(pages_allowed[key])}, "
                f"{_PAGES_ALLOWED_ARE[key]}"
            )
        elif page > page_count:
            reason = f"cites page {page}, but the PDF has {page_count} pages"
        elif text is None or not text.strip():
            reason = (f"cannot be confirmed, because page {page} has no text layer; it "
                      "was not looked for")
        elif unit_statement_on_page(printed, text):
            continue
        else:
            reason = (f"was not found on page {page}, the page it cites, as a whole "
                      "printed statement")
        failures.append(_CheckFailure(
            message=(
                f"'{key}' (the unit of the {unit_of}): the statement {printed!r} "
                f"{reason}. {_UNIT_NOT_CONFIRMED_STOPS}"
            ),
            retry_message=(
                f"'{key}': the unit statement {printed!r} {reason}. {copy_again}"
            ),
        ))
    print(f"  Unit statements looked up on their cited pages: {len(statements)} checked, "
          f"{len(statements) - len(failures)} found, {len(failures)} not confirmed.")
    return failures


def _row_scale_failures(data: dict[str, Any], pdf_bytes: bytes) -> list[_CheckFailure]:
    """Check that each Pass 1 printed row sits under a unit statement of the filing's scale.

    Check B1 (user decision of 2026-10-04, rule 1 option B). `data` is the parsed
    answer after `pass1_problems` has passed, so every key is read with `[]`.
    For each printed row of every line field in historical_years and latest_balance_sheet
    (when not {}):
    - the kind is "share count" for diluted_shares, and "money figures" for every other field;
    - the expected scale is the word _filing_units(data) reads for that kind;
    - the candidates are the parenthesised groups (_PARENTHESISED_GROUP, on whitespace-normalised
      text) of the row's page and of the page before it, that hold thousands, millions or
      billions; each is read with printed_scale(group, kind), and a group whose reading stops
      is not a candidate for that kind;
    - the row passes when one candidate's word equals the expected word;
    - a page beyond the PDF, or with no text layer, is not confirmed.

    Produces one failure per page and kind, naming the page, the kind, the expected scale,
    the statements found (or "no unit statement on page N or N - 1", or "no unit statement on page 1"),
    and each row that cites the page (field, year, label). Print one summary line:
      Row unit scales looked up on their cited pages: rows checked, pages, pages not confirmed.
    """
    units = _filing_units(data)
    expected_scale: dict[UnitOf, str] = {
        "money figures": units.money.scale.word,
        "share count": units.shares.scale.word,
    }

    rows_by_page_kind: dict[tuple[int, UnitOf], list[dict[str, Any]]] = {}
    all_cited_pages: set[int] = set()
    total_rows = 0

    for entry in data["historical_years"]:
        year = entry["year"]
        for field in PASS1_YEAR_LINE_FIELDS:
            kind: UnitOf = "share count" if field == "diluted_shares" else "money figures"
            for line in entry[field]:
                total_rows += 1
                page = line["page"]
                all_cited_pages.add(page)
                rows_by_page_kind.setdefault((page, kind), []).append({
                    "field": field,
                    "year": year,
                    "label": line["label"],
                })

    balance = data["latest_balance_sheet"]
    if balance:
        year = balance["year"]
        for field in PASS1_BALANCE_SHEET_LINE_FIELDS:
            kind = "money figures"
            for line in balance[field]:
                total_rows += 1
                page = line["page"]
                all_cited_pages.add(page)
                rows_by_page_kind.setdefault((page, kind), []).append({
                    "field": field,
                    "year": year,
                    "label": line["label"],
                })

    if total_rows == 0:
        print("  Row unit scales looked up on their cited pages: 0 checked, 0 pages, 0 pages not confirmed.")
        return []

    pages_to_read = all_cited_pages | {p - 1 for p in all_cited_pages if p > 1}
    page_count, page_texts = _read_cited_pages(pdf_bytes, pages_to_read)

    failures: list[_CheckFailure] = []
    unconfirmed_pages: set[int] = set()
    _SCALE_WORDS = ("thousands", "millions", "billions")

    for (page, kind) in sorted(rows_by_page_kind.keys(), key=lambda k: (k[0], k[1])):
        rows = rows_by_page_kind[(page, kind)]
        expected = expected_scale[kind]
        rows_str = "; ".join(f"'{r['label']}' ({r['field']}, year {r['year']})" for r in rows)

        if page > page_count:
            statement_desc = f"page {page} is beyond the last page of the filing ({page_count} pages)"
            failures.append(_CheckFailure(
                message=f"page {page} ({kind}): expected {expected}, {statement_desc}. Rows citing page {page}: {rows_str}.",
                retry_message=f"page {page} ({kind}): expected {expected}, {statement_desc}. Rows citing page {page}: {rows_str}.",
            ))
            unconfirmed_pages.add(page)
            continue

        text = page_texts[page]
        if text is None or not text.strip():
            statement_desc = f"page {page} has no text layer"
            failures.append(_CheckFailure(
                message=f"page {page} ({kind}): expected {expected}, {statement_desc}. Rows citing page {page}: {rows_str}.",
                retry_message=f"page {page} ({kind}): expected {expected}, {statement_desc}. Rows citing page {page}: {rows_str}.",
            ))
            unconfirmed_pages.add(page)
            continue

        scale_groups: list[str] = []
        pages_to_check = (page, page - 1) if page > 1 else (page,)
        for p in pages_to_check:
            p_text = page_texts[p]
            if p_text and p_text.strip():
                norm = _whitespace_normalised(p_text)
                for g in _PARENTHESISED_GROUP.findall(norm):
                    if any(w in g.casefold() for w in _SCALE_WORDS) and g not in scale_groups:
                        scale_groups.append(g)

        candidate_words: list[str] = []
        for g in scale_groups:
            try:
                cand_scale = printed_scale(g, kind)
                candidate_words.append(cand_scale.word)
            except ValueError:
                pass

        if expected in candidate_words:
            continue

        unconfirmed_pages.add(page)
        if scale_groups:
            statement_desc = f"found {', '.join(scale_groups)}"
        elif page == 1:
            statement_desc = "no unit statement on page 1"
        else:
            prev_page = page - 1
            statement_desc = f"no unit statement on page {page} or {prev_page}"

        msg = (
            f"page {page} ({kind}): expected {expected}, {statement_desc}. "
            f"Rows citing page {page}: {rows_str}."
        )
        failures.append(_CheckFailure(message=msg, retry_message=msg))

    print(f"  Row unit scales looked up on their cited pages: {total_rows} checked, "
          f"{len(all_cited_pages)} pages, {len(unconfirmed_pages)} pages not confirmed.")
    return failures


def _pass2_item_failures(
    items: list[NonRecurringItem], pdf_bytes: bytes,
) -> list[_CheckFailure]:
    """Look each Pass 2 non-recurring item's figure and unit words up on their cited pages.

    For each item:
    - The figure: one text line of page `page` holds `amount` (_text_line_holds).
    - Unit words, inline form: `units_page` equals `page`, and whitespace-normalised
      `printed_units` is a substring of whitespace-normalised page text.
    - Unit words, statement form: `units_page` is `page` or `page - 1`, and
      unit_statement_on_page(printed_units, page_text) is true on `units_page`.
    - A page beyond the PDF, or with no text layer, is not confirmed.

    Returns one _CheckFailure per unconfirmed figure or unit statement.
    """
    if not items:
        return []
    cited_pages: set[int] = {item.page for item in items} | {item.units_page for item in items}
    page_count, page_texts = _read_cited_pages(pdf_bytes, cited_pages)
    failures: list[_CheckFailure] = []
    not_confirmed_count = 0

    for item in items:
        item_label = f"non-recurring item ({item.year}, {item.description!r})"
        item_failed = False

        # 1. The figure check on item.page
        if item.page > page_count:
            failures.append(_CheckFailure(
                message=(
                    f"{item_label}: amount {item.amount} cites page {item.page}, but "
                    f"the PDF has {page_count} pages."
                ),
                retry_message=(
                    f"{item_label}: amount {item.amount} cites page {item.page}, "
                    f"beyond the last page of the filing ({page_count} pages)."
                ),
            ))
            item_failed = True
        else:
            page_text = page_texts.get(item.page)
            if page_text is None or not page_text.strip():
                failures.append(_CheckFailure(
                    message=(
                        f"{item_label}: amount {item.amount} cannot be confirmed, "
                        f"because page {item.page} has no text layer; it was not looked for."
                    ),
                    retry_message=(
                        f"{item_label}: amount {item.amount} cannot be confirmed on "
                        f"page {item.page}, because that page has no text layer."
                    ),
                ))
                item_failed = True
            elif not any(_text_line_holds(line, item.amount) for line in page_text.splitlines()):
                failures.append(_CheckFailure(
                    message=(
                        f"{item_label}: amount {item.amount} was not found on page {item.page}: "
                        "no text line there holds that figure."
                    ),
                    retry_message=(
                        f"{item_label}: amount {item.amount} was not found on page {item.page}."
                    ),
                ))
                item_failed = True

        # 2. The unit words check on item.units_page
        if item.units_page > page_count:
            failures.append(_CheckFailure(
                message=(
                    f"{item_label}: units {item.printed_units!r} cites page {item.units_page}, but "
                    f"the PDF has {page_count} pages."
                ),
                retry_message=(
                    f"{item_label}: units {item.printed_units!r} cites page {item.units_page}, "
                    f"beyond the last page of the filing ({page_count} pages)."
                ),
            ))
            item_failed = True
        else:
            units_text = page_texts.get(item.units_page)
            if units_text is None or not units_text.strip():
                failures.append(_CheckFailure(
                    message=(
                        f"{item_label}: units {item.printed_units!r} cannot be confirmed, "
                        f"because page {item.units_page} has no text layer; it was not looked for."
                    ),
                    retry_message=(
                        f"{item_label}: units {item.printed_units!r} cannot be confirmed on "
                        f"page {item.units_page}, because that page has no text layer."
                    ),
                ))
                item_failed = True
            elif _is_inline_scale(item.printed_units):
                if item.units_page != item.page:
                    failures.append(_CheckFailure(
                        message=(
                            f"{item_label}: inline units {item.printed_units!r} cites page "
                            f"{item.units_page}, but must equal the figure's page {item.page}."
                        ),
                        retry_message=(
                            f"{item_label}: inline units {item.printed_units!r} cites page "
                            f"{item.units_page}, but must equal {item.page}."
                        ),
                    ))
                    item_failed = True
                elif _whitespace_normalised(item.printed_units) not in _whitespace_normalised(units_text):
                    failures.append(_CheckFailure(
                        message=(
                            f"{item_label}: inline units {item.printed_units!r} was not found on "
                            f"page {item.units_page}."
                        ),
                        retry_message=(
                            f"{item_label}: inline units {item.printed_units!r} not found on page {item.units_page}."
                        ),
                    ))
                    item_failed = True
            else:
                if item.units_page not in (item.page, item.page - 1):
                    failures.append(_CheckFailure(
                        message=(
                            f"{item_label}: unit statement {item.printed_units!r} cites page "
                            f"{item.units_page}, but must be page {item.page} or {item.page - 1}."
                        ),
                        retry_message=(
                            f"{item_label}: unit statement {item.printed_units!r} cites page "
                            f"{item.units_page}, but must be page {item.page} or {item.page - 1}."
                        ),
                    ))
                    item_failed = True
                elif not unit_statement_on_page(item.printed_units, units_text):
                    failures.append(_CheckFailure(
                        message=(
                            f"{item_label}: unit statement {item.printed_units!r} was not found on "
                            f"page {item.units_page} as a whole printed statement."
                        ),
                        retry_message=(
                            f"{item_label}: unit statement {item.printed_units!r} not found on page {item.units_page}."
                        ),
                    ))
                    item_failed = True

        if item_failed:
            not_confirmed_count += 1

    print(f"  Pass 2 items looked up on their cited pages: {len(items)} checked, "
          f"{len(items) - not_confirmed_count} found, {not_confirmed_count} not confirmed.")
    return failures


# ---------------------------------------------------------------------------
# PDF reader — raw bytes for native LLM ingestion
# ---------------------------------------------------------------------------

def _read_pdf_bytes(path: str | Path) -> bytes:
    """Read raw PDF bytes for native document ingestion by the LLM."""
    pdf_path = Path(path)
    data = pdf_path.read_bytes()
    size_mb = len(data) / (1024 * 1024)
    print(f"  PDF: {pdf_path.name} ({size_mb:.1f} MB)")
    return data


# ---------------------------------------------------------------------------
# JSON cleaner
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> str:
    """Strip markdown fences and return the outermost JSON object."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in LLM response.\nRaw (first 500 chars):\n{raw[:500]}")
    return raw[start: end + 1]


# ---------------------------------------------------------------------------
# Provider-specific API calls
# ---------------------------------------------------------------------------




def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    resolution: ProviderResolution,
    pdf_bytes: bytes | None = None,
    max_retries: int = 5,
) -> tuple[str, int, int]:
    """Call Google Gemini. Returns (response_text, input_tokens, output_tokens).

    Retries automatically on 429 (rate limit) and 503 (overloaded) errors
    with exponential backoff.
    """
    import re
    import time

    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY resolved at startup but is empty now. "
            "Extraction cannot continue.",
        )
    model = resolution.model
    client = genai.Client(api_key=api_key)

    contents: list = []
    if pdf_bytes:
        contents.append(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))
    contents.append(user_prompt)

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=65536,
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            finish_reason = None
            if response.candidates:
                finish_reason = str(response.candidates[0].finish_reason)
            text = response.text or ""
            in_tok = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            out_tok = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            if finish_reason and finish_reason not in ("FinishReason.STOP", "STOP", "1"):
                print(f"  [WARN] Gemini finish_reason={finish_reason} — response may be truncated")
            return text, in_tok, out_tok
        except Exception as e:
            error_str = str(e)
            is_retryable = "429" in error_str or "503" in error_str or "RESOURCE_EXHAUSTED" in error_str or "UNAVAILABLE" in error_str
            if not is_retryable or attempt == max_retries:
                raise
            # Try to extract suggested retry delay from error message
            wait = 2 ** attempt  # default exponential backoff
            delay_match = re.search(r"retry in ([\d.]+)s", error_str, re.IGNORECASE)
            if delay_match:
                wait = max(wait, float(delay_match.group(1)) + 1)
            print(f"  [RETRY {attempt}/{max_retries}] {e.__class__.__name__} — waiting {wait:.0f}s ...")
            time.sleep(wait)
    raise RuntimeError("Unreachable")


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    resolution: ProviderResolution,
    pdf_bytes: bytes | None = None,
) -> tuple[str, int, int]:
    """Route to the correct provider API."""
    if resolution.provider == "gemini":
        return _call_gemini(system_prompt, user_prompt, resolution, pdf_bytes=pdf_bytes)
    raise ValueError(
        f"_call_llm: unexpected provider {resolution.provider!r} with transport "
        f"{resolution.transport!r}. Route A supports Gemini only.",
    )


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------

def _parse_financials_response(
    json_str: str,
    ticker: str,
    company_name: str,
) -> tuple[FinancialStatements, list[_CheckFailure]]:
    """Parse Pass 1 JSON → FinancialStatements, as printed, + failed checks.

    The figures are in the filing's own units; `convert_filing_to_millions`
    converts them to millions once, after Pass 2. The checks here run on the
    figures as printed, so the balance check's 1 printed unit is 1.

    Every figure is `figure_from_printed_lines` over the field's printed lines, and
    every key is read with `[]` after `pass1_problems` has proved it present: an
    absent key, a malformed line or an empty net_income raises Pass1ShapeError
    naming the field, the year and the line (rule 3). The five check rows go
    through `check_row_from_printed_lines`, so an empty one is None, never a
    printed 0. A failed check is returned, never repaired: the figures are kept as
    read.

    Raises:
        json.JSONDecodeError: the text is not JSON.
        Pass1ShapeError: an absent key or a malformed printed line.
    """
    data = json.loads(json_str)
    problems = pass1_problems(data)
    if problems:
        raise Pass1ShapeError(problems)

    years: list[_YearFigures] = []
    income_statements: list[IncomeStatement] = []
    balance_sheets: list[BalanceSheet] = []
    cash_flow_statements: list[CashFlowStatement] = []

    for entry in data["historical_years"]:
        year = entry["year"]
        f = {
            key: figure_from_printed_lines(entry[key], key, f"year {year}")
            for key in PASS1_YEAR_LINE_FIELDS if key not in _YEAR_CHECK_ROWS
        }
        years.append(_YearFigures(
            year=year,
            figures=f,
            gross_profit=check_row_from_printed_lines(
                entry["gross_profit"], "gross_profit", f"year {year}",
            ),
            operating_income=check_row_from_printed_lines(
                entry["operating_income"], "operating_income", f"year {year}",
            ),
            lines=entry,
        ))

        income_statements.append(IncomeStatement(
            year=year,
            revenue=f["revenue"],
            cost_of_revenue=f["cost_of_revenue"],
            sga=f["sga"],
            rd_expense=f["rd_expense"],
            depreciation_amortization=f["depreciation_amortization"],
            # Backlog item 10, unchanged by P11a: D&A is taken out of the summed
            # other operating expense here, in the parser.
            other_operating_expense=f["other_operating_expense"] - f["depreciation_amortization"],
            interest_expense=f["interest_expense"],
            interest_income=f["interest_income"],
            other_non_operating=f["other_non_operating"],
            tax_expense=f["tax_expense"],
            diluted_shares_outstanding=f["diluted_shares"],
        ))

        # Reconstruct CFS so cash_from_operations == cfo exactly
        cfo = f["cfo"]
        net_income = f["net_income"]
        da = f["depreciation_amortization"]
        sbc = f["sbc"]
        capex = f["capex"]
        delta_wc = f["change_in_working_capital"]
        other_ops = cfo - net_income - da - sbc - delta_wc   # residual

        cash_flow_statements.append(CashFlowStatement(
            year=year,
            net_income=net_income,
            depreciation_amortization=da,
            stock_based_compensation=sbc,
            change_in_working_capital=delta_wc,
            other_operating_activities=other_ops,
            capital_expenditures=-capex,   # stored as negative per convention
            acquisitions=0.0,
            other_investing_activities=0.0,
            debt_issued=0.0,
            debt_repaid=0.0,
            shares_issued=0.0,
            shares_repurchased=0.0,
            dividends_paid=0.0,
            other_financing_activities=0.0,
        ))

    # latest_balance_sheet: {} means it was not asked for; anything else carries
    # every key (pass1_problems). The two noncontrolling interest memos and the two
    # printed totals are each their own printed lines, in no total: the NCI sum is
    # analysis/dcf.py:total_noncontrolling_interest's, and the totals only check.
    bs_data = data["latest_balance_sheet"]
    balance: BalanceSheet | None = None
    if bs_data:
        bs_year = bs_data["year"]
        b = {
            key: figure_from_printed_lines(bs_data[key], key, f"balance sheet {bs_year}")
            for key in PASS1_BALANCE_SHEET_LINE_FIELDS
            if key not in _BALANCE_SHEET_CHECK_ROWS
        }
        balance = BalanceSheet(
            year=bs_year,
            cash_and_equivalents=b["cash"],
            short_term_investments=b["short_term_investments"],
            accounts_receivable=b["accounts_receivable"],
            inventory=b["inventory"],
            other_current_assets=b["other_current_assets"],
            ppe_net=b["ppe_net"],
            goodwill=b["goodwill"],
            intangible_assets=b["intangible_assets"],
            other_non_current_assets=b["other_non_current_assets"],
            accounts_payable=b["accounts_payable"],
            short_term_debt=b["short_term_debt"],
            current_portion_lt_debt=0.0,
            accrued_liabilities=b["accrued_liabilities"],
            other_current_liabilities=b["other_current_liabilities"],
            long_term_debt=b["long_term_debt"],
            other_non_current_liabilities=b["other_non_current_liabilities"],
            total_equity=b["total_equity"],
            noncontrolling_interest_nonredeemable=b["noncontrolling_interest_nonredeemable"],
            noncontrolling_interest_redeemable=b["noncontrolling_interest_redeemable"],
            printed_total_assets=check_row_from_printed_lines(
                bs_data["total_assets"], "total_assets", f"balance sheet {bs_year}",
            ),
            printed_total_liabilities_and_equity=check_row_from_printed_lines(
                bs_data["total_liabilities_and_equity"], "total_liabilities_and_equity",
                f"balance sheet {bs_year}",
            ),
            # The figures are as printed, not yet in millions: None says so, and
            # BalanceSheet.printed_total_check stops on it. The conversion
            # (convert_filing_to_millions) sets it from the printed money scale.
            printed_unit_in_millions=None,
        )
        balance_sheets.append(balance)

    validation_errors = _validate_extracted_data(
        years, balance, bs_data if balance is not None else None,
    )

    financials = FinancialStatements(
        ticker=ticker or data.get("ticker", ""),
        company_name=company_name or data.get("company_name", ""),
        income_statements=sorted(income_statements, key=lambda x: x.year),
        balance_sheets=sorted(balance_sheets, key=lambda x: x.year),
        cash_flow_statements=sorted(cash_flow_statements, key=lambda x: x.year),
    )
    return financials, validation_errors


def _parse_nri_response(json_str: str) -> list[NonRecurringItem]:
    """Parse Pass 2 JSON → NonRecurringItem list.

    Three absences are distinguished from three empty-but-present values, because
    in each pair the two mean opposite things and the run cannot recover the
    difference later (rule 3):

    - `non_recurring_items` **absent** means the reply was never a Pass 2 answer,
      and nothing was read. `"non_recurring_items": []` means the model read the
      filing and found none — the prompt asks for exactly that (`:297`). The CLI
      and the result page both state, in words, what was withheld; on an absent
      key they would state "nothing was withheld" about a reply nobody parsed.
    - `confidence` is read with `[]`, not with a fallback to "high". The prompt
      asks for it on every item (`:255`), and `analysis/normalizer.py` now decides
      from it whether the item touches the statements at all. Defaulting an absent
      tag to the *strongest* value would hand that engine a certainty the model
      never expressed, and the adjustment would land at full weight with nothing
      saying so. Rule 3, in the optimistic direction.
    - `source` is the citation a reader follows to reverse an exclusion by hand
      (rule 4), so "the model cited no note" and "the key never arrived" must not
      collapse into the same empty string. An explicit `""` is accepted and is
      rendered `(none cited)`; an absent key stops.

    A KeyError here would name the field but not the item, so the loop raises a
    ValueError that names the year and the description as well — the two things a
    reader needs to find the item in the filing. The `.get` calls inside the
    messages below are deliberate: they are diagnostics printed about an item that
    is already known to be malformed, and a KeyError raised while building the
    message would hide the field that is actually missing.
    """
    data = json.loads(json_str)
    if "non_recurring_items" not in data:
        raise ValueError(
            "Pass 2 returned no 'non_recurring_items' field. An empty list is a "
            "valid answer and means the model found none; an absent field means "
            "the reply was not a Pass 2 answer and nothing was read. These are "
            f"not the same, so the run stops here. Keys returned: "
            f"{sorted(data)!r}"
        )
    items: list[NonRecurringItem] = []
    for item in data["non_recurring_items"]:
        item_desc = f"year {item.get('year')}, {item.get('description')!r}"
        if "confidence" not in item:
            raise ValueError(
                f"Pass 2 returned a non-recurring item with no 'confidence' "
                f"field: {item_desc}. The prompt requires one of "
                f"high | medium | low on every item, and it is not assumed to "
                f"be 'high': analysis/normalizer.py decides from this tag "
                f"whether the item is applied to the financial statements."
            )
        if "source" not in item:
            raise ValueError(
                f"Pass 2 returned a non-recurring item with no 'source' field: "
                f"{item_desc}. The prompt requires the filing reference on "
                f"every item, and an absent one is not read as an empty citation: "
                f"the source is what lets a reader find the note and apply a "
                f"withheld item by hand."
            )
        if "amount" not in item:
            raise ValueError(
                f"Pass 2 returned a non-recurring item with no 'amount' field: "
                f"{item_desc}. 'amount' must be a finite number above 0."
            )
        amount_val = item["amount"]
        if not _is_finite_number(amount_val) or float(amount_val) <= 0:
            raise ValueError(
                f"Pass 2 returned a non-recurring item whose 'amount' is not a "
                f"finite number above 0: {item_desc}, got {amount_val!r}."
            )
        amount = float(amount_val)

        if "page" not in item:
            raise ValueError(
                f"Pass 2 returned a non-recurring item with no 'page' field: "
                f"{item_desc}. 'page' must be a positive integer (a 1-based PDF page)."
            )
        page_val = item["page"]
        if not _is_json_int(page_val) or page_val < 1:
            raise ValueError(
                f"Pass 2 returned a non-recurring item whose 'page' is not a "
                f"positive integer (a 1-based PDF page): {item_desc}, got {page_val!r}."
            )
        page = int(page_val)

        if "units" not in item:
            raise ValueError(
                f"Pass 2 returned a non-recurring item with no 'units' field: "
                f"{item_desc}. 'units' must be an object with 'printed' and 'page'."
            )
        units_val = item["units"]
        if not isinstance(units_val, dict):
            raise ValueError(  # noqa: TRY004
                f"Pass 2 returned a non-recurring item whose 'units' is not a JSON "
                f"object: {item_desc}, got {type(units_val).__name__} {units_val!r}."
            )
        if "printed" not in units_val:
            raise ValueError(
                f"Pass 2 returned a non-recurring item with no 'units.printed' field: "
                f"{item_desc}."
            )
        printed_val = units_val["printed"]
        if not isinstance(printed_val, str) or not printed_val.strip():
            raise ValueError(
                f"Pass 2 returned a non-recurring item whose 'units.printed' is not a "
                f"non-empty string: {item_desc}, got {printed_val!r}."
            )
        if "page" not in units_val:
            raise ValueError(
                f"Pass 2 returned a non-recurring item with no 'units.page' field: "
                f"{item_desc}."
            )
        units_page_val = units_val["page"]
        if not _is_json_int(units_page_val) or units_page_val < 1:
            raise ValueError(
                f"Pass 2 returned a non-recurring item whose 'units.page' is not a "
                f"positive integer (a 1-based PDF page): {item_desc}, got {units_page_val!r}."
            )
        units_page = int(units_page_val)

        try:
            pass2_amount_scale(printed_val, amount)
        except ValueError as exc:
            raise ValueError(
                f"Pass 2 returned a non-recurring item whose unit scale cannot be read: "
                f"{item_desc}, 'units' {printed_val!r}: {exc}"
            ) from exc

        items.append(
            NonRecurringItem(
                year=int(item["year"]),
                description=item["description"],
                amount=amount,
                line_item=item["line_item"],
                direction=item["direction"],
                category=item["category"],
                confidence=item["confidence"],
                page=page,
                printed_units=printed_val,
                units_page=units_page,
                source=item["source"],
            )
        )
    return items


# ---------------------------------------------------------------------------
# User prompt builders
# ---------------------------------------------------------------------------

def _build_financials_prompt(
    target_years: list[int] | None = None,
    include_bs: bool = True,
) -> str:
    """Build the user prompt for Pass 1 (financial extraction).

    The PDF is sent as a native document attachment, not embedded in the prompt.
    """
    if target_years:
        year_str = ", ".join(str(y) for y in sorted(target_years))
        year_instruction = (
            f"Extract Income Statement and Cash Flow data for fiscal year(s): "
            f"{year_str} ONLY. Do NOT extract other years."
        )
    else:
        year_instruction = (
            "Extract Income Statement and Cash Flow data for ALL fiscal years "
            "present in the filing (typically 2-3 years)."
        )

    if include_bs:
        bs_instruction = "Also extract the latest balance sheet."
    else:
        bs_instruction = "Do NOT extract the balance sheet. Set latest_balance_sheet to {}."

    return (
        f"Extract financial data from the attached 10-K/10-Q PDF filing.\n\n"
        f"TARGET YEARS: {year_instruction}\n"
        f"BALANCE SHEET: {bs_instruction}"
    )


def _build_is_summary(
    financials: FinancialStatements,
    target_years: list[int] | None = None,
) -> str:
    """Format extracted I/S as context for Pass 2 (NRI analysis)."""
    years = target_years or financials.years
    lines = []
    for y in years:
        inc = financials.get_income_statement(y)
        if inc:
            # Show other_operating_expense as the LLM originally provided it
            # (before DA subtraction) so it matches what the NRI pass will reference
            other_opex_raw = inc.other_operating_expense + inc.depreciation_amortization
            lines.append(
                f"  FY{y}: Revenue={inc.revenue:,.0f}  "
                f"COGS={inc.cost_of_revenue:,.0f}  "
                f"SG&A={inc.sga:,.0f}  "
                f"R&D={inc.rd_expense:,.0f}  "
                f"D&A={inc.depreciation_amortization:,.0f}  "
                f"Other_OpEx={other_opex_raw:,.0f}  "
                f"EBIT={inc.ebit:,.0f}  "
                f"Other_NonOp={inc.other_non_operating:,.0f}"
            )
    return "\n".join(lines) if lines else "  (no data available)"


def _build_nri_prompt(
    is_summary: str,
    target_years: list[int] | None = None,
) -> str:
    """Build the user prompt for Pass 2 (NRI analysis).

    The PDF is sent as a native document attachment, not embedded in the prompt.
    """
    if target_years:
        year_str = ", ".join(str(y) for y in sorted(target_years))
        year_instruction = f"Analyze non-recurring items for fiscal year(s): {year_str}."
    else:
        year_instruction = "Analyze non-recurring items for ALL fiscal years in the filing."

    return (
        f"{year_instruction}\n\n"
        f"EXTRACTED INCOME STATEMENT (for reference — use to anchor your findings):\n"
        f"{is_summary}"
    )


def _pass1_prompt_pair(
    target_years: list[int] | None,
    include_bs: bool,
) -> tuple[str, str]:
    """The (system, user) prompt pair for Pass 1. The ONE place it is assembled.

    `_run_financials_pass` (route A) and `pass1_prompts` (route B) both call this,
    so the prompt the API receives and the prompt a session is shown cannot differ.
    """
    return _FINANCIALS_SYSTEM_PROMPT, _build_financials_prompt(target_years, include_bs)


def _pass2_prompt_pair(
    financials: FinancialStatements,
    target_years: list[int] | None,
) -> tuple[str, str]:
    """The (system, user) prompt pair for Pass 2. The ONE place it is assembled.

    `financials` is that filing's own Pass 1 result, before any merge: route A's
    `_run_nri_pass` receives exactly that, and the session route parses that
    filing's stored Pass 1 answer to get it.
    """
    is_summary = _build_is_summary(financials, target_years)
    return _NRI_SYSTEM_PROMPT, _build_nri_prompt(is_summary, target_years)


# ---------------------------------------------------------------------------
# Pass 1: Financial Statement Extraction (with retry)
# ---------------------------------------------------------------------------

def _run_financials_pass(
    pdf_bytes: bytes,
    ticker: str,
    company_name: str,
    resolution: ProviderResolution,
    target_years: list[int] | None = None,
    include_bs: bool = True,
    debug: bool = False,
) -> tuple[FinancialStatements, FilingUnits]:
    """Execute Pass 1: extract I/S, C/F, and optionally B/S.

    Returns the statements AS PRINTED, in the filing's own units, and the two
    printed unit statements with the scale Python read in each. The caller builds
    Pass 2's prompt from the statements as printed and then converts both passes
    to millions (`convert_filing_to_millions`, in `extract_financials`).

    Raises:
        ValueError: a unit statement or a printed row's unit scale is still not
            confirmed after the last retry (P14a, P14b), naming the field or page;
            or the PDF cannot be opened by pdfplumber.
        json.JSONDecodeError, Pass1ShapeError: the answer still cannot be parsed
            after the last retry.
    """
    # The same builder `pass1_prompts` calls, so the prompt sent here and the one
    # the session route prints for the same plan are one string, not two copies.
    system_prompt, user_prompt = _pass1_prompt_pair(target_years, include_bs)

    year_label = f"for {sorted(target_years)}" if target_years else "(all years)"
    bs_label = " + B/S" if include_bs else ""
    print(f"  [Pass 1] Extracting financials {year_label}{bs_label}...")

    raw, in_tok, out_tok = _call_llm(
        system_prompt, user_prompt, resolution,
        pdf_bytes=pdf_bytes,
    )
    if in_tok or out_tok:
        print(f"  [Pass 1] Tokens — input: {in_tok:,}  output: {out_tok:,}")

    if debug:
        print(f"\n{'='*65}\nPASS 1 RAW RESPONSE\n{'='*65}\n{raw}\n{'='*65}\n")

    # Parse + Validate + Retry loop. Three kinds of answer go back to the model:
    # text that is not JSON, an answer with an absent key, a malformed printed
    # line or a unit statement whose scale cannot be read (Pass1ShapeError), and an
    # answer whose printed subtotals or totals fail their check or whose printed
    # lines or unit statements are not found on their cited pages. Each retry asks
    # the model to READ the rows again; none asks it to change a figure so that a
    # check passes (rule 1). After the last retry, the first two stop the run, a
    # unit statement not found stops the run (P14a: a wrong scale moves every
    # figure by 1,000), and any other failed check is shown and kept. A PDF that
    # pdfplumber cannot open stops at once: nothing could be looked up, so no retry
    # could help.
    MAX_RETRIES = 2
    json_str = _extract_json(raw)

    for attempt in range(1 + MAX_RETRIES):
        try:
            financials, val_errors = _parse_financials_response(
                json_str, ticker, company_name,
            )
        except json.JSONDecodeError as exc:
            ctx_start = max(0, exc.pos - 120)
            ctx_end = min(len(json_str), exc.pos + 120)
            print(f"\n  [Pass 1 JSON error] {exc}")
            print(f"  Context: ...{json_str[ctx_start:ctx_end]}...")

            if attempt >= MAX_RETRIES:
                raise
            print(f"  Retrying — asking {resolution.provider.upper()} to repair JSON...")
            fix_prompt = (
                "The following JSON is malformed. Return ONLY the corrected JSON "
                "object with no markdown fences and no additional text.\n\n"
                + json_str
            )
            raw2, _, _ = _call_llm(
                system_prompt, fix_prompt, resolution,
            )
            json_str = _extract_json(raw2)
            continue
        except Pass1ShapeError as exc:
            print(f"\n  [Pass 1 shape error] {exc}")
            if attempt >= MAX_RETRIES:
                raise
            print(f"  Retrying — asking {resolution.provider.upper()} to supply the "
                  f"missing keys and lines (retry {attempt + 1}/{MAX_RETRIES})...")
            error_list = "\n".join(f"  - {p}" for p in exc.problems)
            fix_prompt = (
                "The following JSON does not have the shape the schema requires.\n\n"
                "PROBLEMS:\n" + error_list + "\n\n"
                "Every field except 'year' is a list of printed lines, each "
                '{"label": ..., "value": ..., "page": ...}, and an empty list means '
                "the filing prints no such row. 'units' and 'share_units' are each "
                '{"printed": ..., "page": ...}: the words that state the unit of the '
                "money figures and of the share count, copied exactly as printed, "
                "with their page. Read the missing rows from the "
                "filing and return the whole JSON with every key present. Each value "
                "is one figure printed on its row; do not add rows together. Return "
                "ONLY the corrected JSON.\n\n"
                + json_str
            )
            # The filing goes with the retry: the prompt asks for rows to be read
            # from it, and a model that cannot see it can only make one up.
            raw2, in2, out2 = _call_llm(
                system_prompt, fix_prompt, resolution, pdf_bytes=pdf_bytes,
            )
            if in2 or out2:
                print(f"  [Pass 1] Retry tokens — input: {in2:,}  output: {out2:,}")
            json_str = _extract_json(raw2)
            continue

        # The answer parsed. Each unit statement and each printed line is now
        # looked up on the page it cites (P14a; backlog item 59): one not found is
        # a failed check like any other, and retried. A PDF pdfplumber cannot open
        # stops here.
        data = json.loads(json_str)
        stmt_failures = _unit_statement_failures(data, pdf_bytes)
        row_scale_failures = _row_scale_failures(data, pdf_bytes)
        unit_failures = stmt_failures + row_scale_failures
        val_errors = val_errors + unit_failures + _printed_line_failures(data, pdf_bytes)
        if not val_errors:
            return financials, _filing_units(data)

        if attempt >= MAX_RETRIES:
            # A unit statement still not found or row scale failure stops: its
            # scale converts every figure, and a wrong one cannot be detected
            # downstream.
            if unit_failures:
                counts: list[str] = []
                if stmt_failures:
                    counts.append(f"{len(stmt_failures)} printed unit statement(s)")
                if row_scale_failures:
                    counts.append(f"{len(row_scale_failures)} row scale failure(s)")
                kinds_str = " and ".join(counts)
                raise ValueError(
                    f"Pass 1: after {MAX_RETRIES} retries, "
                    f"{kinds_str} are still not confirmed, so the scale of the figures is "
                    "not known and the run stops:\n"
                    + "\n".join(f"  - {failure.message}" for failure in unit_failures),
                )
            # Any other failed check: the figures are kept and the failure is
            # shown; it is never repaired here.
            print(f"\n  [Pass 1 FAIL] Checks still fail after {MAX_RETRIES} retries. "
                  "The figures are kept as read and the failures are shown:")
            for failure in val_errors:
                print(f"    {failure.message}")
            return financials, _filing_units(data)

        print(f"\n  [Pass 1] Checks failed — asking for the rows to be read again "
              f"(retry {attempt + 1}/{MAX_RETRIES})...")
        # The retry wording names each failed check, its side and the rows Python
        # added, or the line not found by label, field and page, and states no
        # value and no amount (review F7): a model told the gap can write a row of
        # that size.
        error_list = "\n".join(f"  - {failure.retry_message}" for failure in val_errors)
        fix_prompt = (
            "Python added up the printed lines in the following JSON and compared "
            "the sums with the subtotals and totals the filing prints, and looked "
            "for each line and each unit statement on the page it cites. These "
            "checks failed:\n\n"
            "FAILED CHECKS:\n" + error_list + "\n\n"
            "A failed check means a row was misread, missed, listed under two "
            "fields, or not found on the page it cites. Read the statement rows "
            "again from the filing, and correct a "
            "line only where it does not match the row printed in the filing. Do "
            "NOT change any value to make a check pass. If every line matches the "
            "filing, return it unchanged; other failed checks will be shown as "
            "they are, but a unit statement or row scale failure stops the run. "
            "Return ONLY the JSON.\n\n"
            + json_str
        )
        # The filing goes with the retry, as above: rows are re-read from it.
        raw2, in2, out2 = _call_llm(
            system_prompt, fix_prompt, resolution, pdf_bytes=pdf_bytes,
        )
        if in2 or out2:
            print(f"  [Pass 1] Retry tokens — input: {in2:,}  output: {out2:,}")
        json_str = _extract_json(raw2)

    # Unreachable: the last attempt returns or raises in every branch above.
    raise AssertionError("Pass 1 retry loop ended without a result")


# ---------------------------------------------------------------------------
# Pass 2: Non-Recurring Item Analysis
# ---------------------------------------------------------------------------

def _run_nri_pass(
    pdf_bytes: bytes,
    financials: FinancialStatements,
    resolution: ProviderResolution,
    target_years: list[int] | None = None,
    debug: bool = False,
) -> list[NonRecurringItem]:
    """Execute Pass 2: analyze footnotes for non-recurring items.

    Receives the extracted FinancialStatements from Pass 1 so it can build
    an I/S summary as context for the LLM.
    """
    # The same builder `pass2_prompts` calls; see _run_financials_pass.
    system_prompt, user_prompt = _pass2_prompt_pair(financials, target_years)

    year_label = f"for {sorted(target_years)}" if target_years else ""
    print(f"  [Pass 2] Analyzing non-recurring items {year_label}...")

    raw, in_tok, out_tok = _call_llm(
        system_prompt, user_prompt, resolution,
        pdf_bytes=pdf_bytes,
    )
    if in_tok or out_tok:
        print(f"  [Pass 2] Tokens — input: {in_tok:,}  output: {out_tok:,}")

    if debug:
        print(f"\n{'='*65}\nPASS 2 RAW RESPONSE\n{'='*65}\n{raw}\n{'='*65}\n")

    json_str = _extract_json(raw)

    try:
        nri = _parse_nri_response(json_str)
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"  [Pass 2 WARN] Failed to parse NRI response: {exc}")
        print("  Retrying once...")
        fix_prompt = (
            "The following JSON is malformed. Return ONLY the corrected JSON object "
            "with no markdown fences.\n\n" + json_str
        )
        raw2, _, _ = _call_llm(
            system_prompt, fix_prompt, resolution,
        )
        # Backlog item 50, and item 8's site here. This branch used to print a
        # warning and return [], so "the reply could not be read" reached the CLI
        # and the result page as "the filing has no non-recurring items" — the
        # one difference `_parse_nri_response` exists to keep (rule 3). It stops.
        # The four types are the ones the parse raises, each measured on a stub
        # reply: ValueError (no JSON object, malformed JSON, an absent
        # `non_recurring_items`, `confidence` or `source`, a year that is not an
        # integer), KeyError (an absent `year`, `amount` or other item field),
        # TypeError (`non_recurring_items` not a list, a null item or amount) and
        # AttributeError (an item that is a JSON list). Nothing else is caught.
        try:
            nri = _parse_nri_response(_extract_json(raw2))
        except (ValueError, KeyError, TypeError, AttributeError) as retry_exc:
            # The filing as this function knows it: no path reaches here, so it
            # is named by what Pass 1 read from it. Each value is printed as it
            # is (repr), so an empty ticker shows as '' and is not replaced.
            raise ValueError(
                f"Pass 2 (non-recurring items) could not be read for the filing "
                f"with ticker {financials.ticker!r}, company "
                f"{financials.company_name!r}, fiscal years {financials.years} "
                f"read in Pass 1. The model's reply did not parse "
                f"({type(exc).__name__}: {exc}), and the reply to one retry did "
                f"not parse either ({type(retry_exc).__name__}: {retry_exc}). "
                f"Nothing was read about non-recurring items, which is not the "
                f"same as the filing having none, so the run stops here."
            ) from retry_exc

    failures = _pass2_item_failures(nri, pdf_bytes)
    if failures:
        error_list = "\n".join(f"  - {f.message}" for f in failures)
        raise ValueError(
            f"Pass 2 (non-recurring items) page check failed for the filing "
            f"with ticker {financials.ticker!r}, company "
            f"{financials.company_name!r}, fiscal years {financials.years} "
            f"read in Pass 1. {len(failures)} item(s) could not be confirmed "
            f"on the page they cite:\n{error_list}"
        )

    if nri:
        print(f"  [Pass 2] Found {len(nri)} non-recurring item(s):")
        for item in nri:
            sign = "+" if item.direction == "add_back" else "-"
            # As printed, in the filing's own unit: converted to millions later,
            # with Pass 1 (convert_filing_to_millions).
            print(f"    {item.year} {sign}{item.amount:g} (as printed) on "
                  f"{item.line_item} — {item.description[:60]}")
    else:
        print("  [Pass 2] No non-recurring items identified")

    return nri


# ---------------------------------------------------------------------------
# Provider, transport and credential resolution
# ---------------------------------------------------------------------------

def _resolve_model(provider: Provider, model: str | None) -> str:
    """Resolve the model ID. An explicitly empty model stops rather than defaulting."""
    if model is None:
        return _DEFAULT_MODELS[provider]
    if not model.strip():
        raise ValueError(
            "model was given as an empty string. Pass a model ID, or omit it "
            f"entirely to use this provider's default ({_DEFAULT_MODELS[provider]}).",
        )
    return model


def _resolve_gemini(model: str) -> ProviderResolution:
    """Choose the transport and the credential for Gemini, or stop naming both remedies."""
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        raise ValueError(
            "GEMINI_API_KEY is not set, so extraction cannot start. "
            "Either remedy is sufficient:\n"
            "  (1) Set GEMINI_API_KEY in .env or the system environment to use the Gemini API (route A); or\n"
            "  (2) Extract in a Claude Code session with the `extract-filing` skill and run with --session-file (route B).",
        )
    return ProviderResolution(
        provider="gemini",
        model=model,
        reasoning_label="the provider's default; this code sets no thinking for Gemini",
        transport="gemini-direct",
        transport_label="Google Gemini API (generativelanguage.googleapis.com)",
        credential="gemini-api-key",
        credential_source=config.credential_origin("GEMINI_API_KEY"),
    )


def resolve_provider(
    provider: Provider,
    model: str | None,
) -> ProviderResolution:
    """Resolve provider, model, transport and credential, or stop.

    Reads the environment only. It acquires no token and makes no network call, so
    it is cheap enough to call from a request handler purely to label a result page.

    Raises ValueError, naming the field and the remedy, when no credential of any
    kind resolves (rule 3). A missing credential must never produce a client that
    fails later with an unrelated message.
    """
    if provider == "claude":
        raise ValueError(
            "Claude reads a filing only in a Claude Code session (route B), on the "
            "user's decision of 2026-10-04. Run the `extract-filing` skill and pass "
            "--session-file (CLI) or upload the session file (web). "
            "Route A uses Gemini, with GEMINI_API_KEY.",
        )
    if provider != "gemini":
        raise ValueError(f"provider must be 'claude' or 'gemini', got '{provider}'")

    resolved_model = _resolve_model(provider, model)
    return _resolve_gemini(resolved_model)


def describe_resolution(resolution: ProviderResolution) -> str:
    """One line naming who read the filing, over what, on whose credential (rule 6)."""
    return (
        f"Provider: {resolution.provider.upper()}  |  "
        f"Model: {resolution.model}  |  "
        f"Reasoning: {resolution.reasoning_label}  |  "
        f"Transport: {resolution.transport_label}  |  "
        f"Credential: {resolution.credential_source}"
    )


# ===========================================================================
# Shared by both extraction routes: the plan, the merge, the prompts, the parsers
# ===========================================================================
#
# Route A (this file's API calls) and route B (a Claude Code session writing a
# session file, ingestion/session_extraction.py) meet here. Each job below has
# exactly one implementation, and both routes call it, so a fix to the plan or the
# merge cannot land in one route and miss the other (the shape of backlog item 7).

@dataclass(frozen=True)
class FilingPlan:
    """What one filing is asked for: which years, and whether its balance sheet.

    `target_years` is None for "every year the filing presents". A tuple, not a
    list, so the plan is hashable and cannot be mutated after `plan_filings`
    produced it.
    """

    fiscal_year: int
    pdf_path: str
    target_years: tuple[int, ...] | None
    include_bs: bool


def plan_filings(filings: Sequence[tuple[int, str | Path]]) -> list[FilingPlan]:
    """Decide which years and which balance sheet come from which filing.

    `Sequence`, not `list`: `list` is invariant in its element type, so a
    caller holding a `list[tuple[int, str]]` — which both entry points do —
    could not pass it without a cast. `Sequence` is covariant, and nothing
    here mutates the argument.

    One filing: every year it presents, and its balance sheet. Several, sorted
    ascending by fiscal year: the oldest gives every year it presents and no
    balance sheet, each middle one gives its own year only and no balance sheet,
    and the newest gives its own year and the balance sheet.

    Raises:
        ValueError: when `filings` is empty.
    """
    if not filings:
        raise ValueError("filings list is empty")

    if len(filings) == 1:
        fiscal_year, pdf_path = filings[0]
        return [FilingPlan(
            fiscal_year=fiscal_year,
            pdf_path=str(pdf_path),
            target_years=None,
            include_bs=True,
        )]

    filings_sorted = sorted(filings, key=lambda x: x[0])  # ascending by year
    oldest_year = filings_sorted[0][0]
    newest_year = filings_sorted[-1][0]
    return [
        FilingPlan(
            fiscal_year=fiscal_year,
            pdf_path=str(pdf_path),
            target_years=None if fiscal_year == oldest_year else (fiscal_year,),
            include_bs=fiscal_year == newest_year,
        )
        for fiscal_year, pdf_path in filings_sorted
    ]


def _plan_target_years(plan: FilingPlan) -> list[int] | None:
    """The plan's target years in the list form the prompt builders take."""
    if plan.target_years is None:
        return None
    return list(plan.target_years)


# The four fields `nri_identity` returns, named once so the merge's two
# dictionaries cannot drift from it. See `nri_identity` for why each is there.
NriIdentity = tuple[int, float, str, str]

# The five fields `nri_identity_within_filing` returns, named once for the same
# reason. See that function for why `page` is in this key and not in the one
# above.
NriIdentityWithinFiling = tuple[int, float, str, str, int]


def nri_identity(item: NonRecurringItem) -> NriIdentity:
    """What makes one non-recurring item the same item as another, ACROSS filings.

    The merge uses two keys, and this is the one it applies between filings.
    `nri_identity_within_filing` is the one it applies inside a single filing's
    answer; the difference between them is `page`, and the reason is below.

    Four fields, and each is here for a reason:

    - `year`: an item belongs to one fiscal year, and the same charge in two
      years is two charges.
    - `amount`: the figure, in millions by the time the merge runs
      (`convert_filing_to_millions` has run per filing). Two different figures
      are two different items.
    - `direction`: `add_back` or `remove` decides the sign of the adjustment, so
      the same figure in opposite directions is not the same item.
    - `description`: the text the model copied from the page. **This is the one
      field that tells two different items of the same size apart**, and it is
      the field the old key left out. Walmart fiscal 2022 prints two $0.2
      billion incremental divestiture losses, Asda and Seiyu; without the
      description they are one item and 200 $M of add-back disappears
      (backlog item 112).

    Two fields the model also wrote are deliberately NOT here:

    - `page`: a 1-based PDF page of ONE filing. The same item re-reported by a
      later filing is printed on another page of another PDF, so a key holding
      the page could never match across filings, and every overlapping item
      would be counted twice. That is the case the dedupe exists for. Measured:
      the same Walmart disclosure is "Note 1 - Summary of Significant Accounting
      Policies, Investments, page 52" in the FY2024 10-K and "... page 51" in
      the FY2025 10-K.
    - `source`: the model's note reference, which carries a page number
      ("Note 12 ... page 66"), so it moves between filings for the same reason.

    The match is exact equality on all four. There is no tolerance, no
    normalisation and no similarity rule: a judgement about whether two
    differently-worded descriptions mean one item is not Python's to make.
    """
    return (item.year, item.amount, item.direction, item.description)


def nri_identity_within_filing(item: NonRecurringItem) -> NriIdentityWithinFiling:
    """What makes one row the same row as another INSIDE one filing's answer.

    The four fields of `nri_identity`, plus `page`.

    `page` is here, and it is absent from the across-filing key, because the two
    comparisons ask different questions and the page answers only one of them:

    - Across filings, the question is "did a later filing re-report the item an
      earlier one already gave us?" Two filings are two PDFs, and the same
      disclosure moves page between them, so a key holding `page` could never
      match and every overlap would be double-counted.
    - Within one filing, the question is "did the model write one printed line
      twice?" There is one PDF, so the page is stable, and it is what separates
      two real items of the same size: Walmart's fiscal 2024 10-K prints the
      incremental loss on the Asda divestiture on PDF page 66 and the one on the
      Seiyu divestiture on page 67, each $0.2 billion, both fiscal 2022, both
      add_back. Two rows that agree on the year, the amount, the direction, the
      description AND the page are one printed line written twice, not two
      charges; the merge keeps the first and reports the second.

    Two rows alike in every field but the page are therefore two items here, and
    nothing is dropped.

    `source` stays out of both keys: it carries a page number too, so it adds
    nothing the page does not already give within one filing, and it moves
    between filings for the reason above.

    The match is exact equality on all five, with no tolerance, no normalisation
    and no similarity rule, for the reason given in `nri_identity`.
    """
    return (item.year, item.amount, item.direction, item.description, item.page)


# The one line that opens a drop report. One per comparison, because the two
# comparisons drop for different reasons and a reader is owed the right one: the
# first is a later filing re-reporting an item, the second is one filing's answer
# carrying the same printed line twice. The rows under either are the same.
REPEAT_ACROSS_FILINGS = ("Non-recurring item already reported by an earlier filing "
                         "- counted once, not twice:")
REPEAT_WITHIN_ONE_FILING = ("Non-recurring item listed twice by one filing - same "
                            "year, amount, direction, description and page, so one "
                            "printed line written twice - counted once, not twice:")


def _print_repeated_item(
    kept_item: NonRecurringItem,
    kept_filing: str,
    dropped_item: NonRecurringItem,
    dropped_filing: str,
    headline: str,
) -> None:
    """Report one non-recurring item dropped by the merge as a repeat.

    `headline` is `REPEAT_ACROSS_FILINGS` or `REPEAT_WITHIN_ONE_FILING`, naming
    which of the merge's two comparisons dropped the item. Neither direction is
    silent, and both print the same two rows.

    Printed where the merge's and `check`'s other messages are printed, so both
    routes show it. It is not an error and it does not stop the run: two filings
    that present the same fiscal year can both flag the same item, and the merge
    must count it once.
    """
    print(f"  [MERGE] {headline}")
    for label, item, filing in (
        ("kept   ", kept_item, kept_filing),
        ("dropped", dropped_item, dropped_filing),
    ):
        # `$M`: both callers run `convert_filing_to_millions` on each filing
        # before the merge, so an item's amount is in millions here.
        print(f"    {label}: {item.year}  {item.amount:,} $M  {item.direction}  "
              f"{item.description!r}  [{filing}, page {item.page}]")


def merge_filing_extractions(
    extractions: list[tuple[FilingPlan, FinancialStatements, list[NonRecurringItem]]],
    ticker: str,
    company_name: str,
) -> tuple[FinancialStatements, list[NonRecurringItem]]:
    """Merge per-filing results into one set of statements and one item list.

    `extractions` is in plan order (ascending fiscal year), as `plan_filings`
    returns it. For each statement year, the statement from the filing whose
    `fiscal_year` equals that year is preferred; otherwise the first one seen is
    kept.

    Non-recurring items are deduplicated by two keys, each for one comparison,
    first seen kept in both:

    - ACROSS filings, on `nri_identity` — (year, amount, direction,
      description). `page` is out of this key because the same disclosure sits
      on a different page of a different PDF in a later filing.
    - WITHIN one filing's answer, on `nri_identity_within_filing` — the same
      four fields plus `page`. One PDF's page numbers are stable, so `page` is
      what tells two real items of the same size apart (Asda on page 66 from
      Seiyu on page 67); only a row identical in all five is one printed line
      written twice. Two rows differing in any field, the page included, are
      two items.

    Every item dropped by either comparison is printed by
    `_print_repeated_item`, naming the item kept and the item dropped with the
    filing and page each came from, and saying which comparison dropped it. A
    drop never stops the run, because two filings reporting one item is normal
    (backlog item 112).
    """
    all_income: dict[int, IncomeStatement] = {}
    all_balance: dict[int, BalanceSheet] = {}
    all_cashflow: dict[int, CashFlowStatement] = {}
    all_nri: list[NonRecurringItem] = []
    # key -> (the item kept under it, the filing that item came from). A dict,
    # not a set: the message naming a drop has to name what was kept.
    kept_by_key: dict[NriIdentity, tuple[NonRecurringItem, str]] = {}

    for plan, fin, nri in extractions:
        fiscal_year = plan.fiscal_year

        # Merge: prefer the "primary" filing (where fiscal_year matches the year)
        for income in fin.income_statements:
            y = income.year
            if y not in all_income or y == fiscal_year:
                all_income[y] = income
        for balance in fin.balance_sheets:
            y = balance.year
            if y not in all_balance or y == fiscal_year:
                all_balance[y] = balance
        for cashflow in fin.cash_flow_statements:
            y = cashflow.year
            if y not in all_cashflow or y == fiscal_year:
                all_cashflow[y] = cashflow

        # Dedupe non-recurring items by the two keys, each inside its own
        # comparison. See this function's docstring and the two identity
        # functions for why `page` is in one key and not the other.
        #
        # One filing's Pass 2 answer is one list, and two rows in it that differ
        # anywhere are two items: the model wrote each with its own printed
        # description and its own page. Walmart's fiscal 2024 10-K prints an
        # incremental loss on the Asda divestiture (PDF page 66) and one on the
        # Seiyu divestiture (page 67), each $0.2 billion, both fiscal 2022, both
        # add_back. They are two losses, not one. So this filing's own
        # across-filing keys join `kept_by_key` only after all of its rows have
        # been handled.
        filing_name = Path(plan.pdf_path).name
        from_this_filing: dict[NriIdentity, tuple[NonRecurringItem, str]] = {}
        # The rows this filing contributed, by the five-field key. A dict, not a
        # set, because the message naming a drop has to name what was kept —
        # and only rows actually kept go in, so the item it names is one that
        # really is in the merged list.
        kept_rows_this_filing: dict[NriIdentityWithinFiling, NonRecurringItem] = {}
        for item in nri:
            # The within-filing comparison runs first, against this filing's own
            # kept rows: a row identical to one of them in all five fields is
            # the same printed line written twice.
            row_key = nri_identity_within_filing(item)
            repeated_row = kept_rows_this_filing.get(row_key)
            if repeated_row is not None:
                _print_repeated_item(repeated_row, filing_name, item, filing_name,
                                     REPEAT_WITHIN_ONE_FILING)
                continue

            key = nri_identity(item)
            repeated = kept_by_key.get(key)
            if repeated is None:
                all_nri.append(item)
                kept_rows_this_filing[row_key] = item
                # setdefault: if this filing wrote two rows that differ only in
                # the page, both are kept above, and the first is the one a
                # later filing's repeat is reported against.
                from_this_filing.setdefault(key, (item, filing_name))
            else:
                kept_item, kept_filing = repeated
                _print_repeated_item(kept_item, kept_filing, item, filing_name,
                                     REPEAT_ACROSS_FILINGS)
        kept_by_key.update(from_this_filing)

    merged = FinancialStatements(
        ticker=ticker,
        company_name=company_name,
        income_statements=sorted(all_income.values(), key=lambda x: x.year),
        balance_sheets=sorted(all_balance.values(), key=lambda x: x.year),
        cash_flow_statements=sorted(all_cashflow.values(), key=lambda x: x.year),
    )
    return merged, all_nri

def pass1_prompts(plan: FilingPlan) -> tuple[str, str]:
    """The (system, user) prompt route A sends for this plan's Pass 1."""
    return _pass1_prompt_pair(_plan_target_years(plan), plan.include_bs)


def pass2_prompts(
    plan: FilingPlan,
    financials: FinancialStatements,
) -> tuple[str, str]:
    """The (system, user) prompt route A sends for this plan's Pass 2.

    `financials` must be this filing's own Pass 1 result, unmerged.
    """
    return _pass2_prompt_pair(financials, _plan_target_years(plan))


def parse_pass1(
    json_str: str,
    ticker: str,
    company_name: str,
) -> tuple[FinancialStatements, list[str]]:
    """Parse a Pass 1 answer into statements plus one message per failed check.

    The statements are AS PRINTED, in the filing's own units, and each balance
    sheet's `printed_unit_in_millions` is None: `convert_filing_to_millions`
    converts them, after Pass 2 (whose prompt is built from them as printed).

    The messages are the full wording (printed figure, Python's sum, the gap), the
    one route B's `check` and the CLI print. Route A's retry uses the wording
    without amounts, inside `_run_financials_pass`.
    """
    financials, failures = _parse_financials_response(json_str, ticker, company_name)
    return financials, [failure.message for failure in failures]


def printed_line_page_failures(json_str: str, pdf_bytes: bytes) -> list[str]:
    """One message per Pass 1 printed line not found on the page it cites.

    Route B's page check, the same walk route A runs in `_run_financials_pass`.
    `pdf_bytes` is the filing the answer was read from. An empty list means every
    printed line was found on its page.

    Raises:
        json.JSONDecodeError: the text is not JSON.
        Pass1ShapeError: an absent key or a malformed printed line.
        ValueError: the PDF cannot be opened by pdfplumber.
    """
    data = json.loads(json_str)
    problems = pass1_problems(data)
    if problems:
        raise Pass1ShapeError(problems)
    return [failure.message for failure in _printed_line_failures(data, pdf_bytes)]


def parse_pass2(json_str: str) -> list[NonRecurringItem]:
    """Parse a Pass 2 answer into non-recurring items."""
    return _parse_nri_response(json_str)


def filing_units(json_str: str) -> FilingUnits:
    """The two printed unit statements of a Pass 1 answer, with the scale Python
    read in each (`printed_scale`).

    Raises:
        json.JSONDecodeError: the text is not JSON.
        Pass1ShapeError: an absent key, a malformed printed line, or a unit
            statement whose scale cannot be read.
    """
    data = json.loads(json_str)
    problems = pass1_problems(data)
    if problems:
        raise Pass1ShapeError(problems)
    return _filing_units(data)


def unit_statement_page_failures(json_str: str, pdf_bytes: bytes) -> list[str]:
    """One message per printed unit statement or row scale check not confirmed on its page.

    Route B's unit check, the same lookup route A runs in `_run_financials_pass`.
    The loader stops on any: a wrong scale moves every figure by 1,000. Returns
    failures from both _unit_statement_failures and _row_scale_failures.

    Raises:
        json.JSONDecodeError: the text is not JSON.
        Pass1ShapeError: the answer's shape is not usable.
        ValueError: the PDF cannot be opened by pdfplumber.
    """
    data = json.loads(json_str)
    problems = pass1_problems(data)
    if problems:
        raise Pass1ShapeError(problems)
    return [
        failure.message
        for failure in _unit_statement_failures(data, pdf_bytes) + _row_scale_failures(data, pdf_bytes)
    ]


def pass2_page_failures(json_str: str, pdf_bytes: bytes) -> list[str]:
    """One message per Pass 2 item figure or unit words not found on its cited page.

    Route B's item check, the same lookup route A runs in `_run_nri_pass`.
    The loader stops on any: a wrong scale moves an item by 1,000, and an amount
    not on its page cannot be traced (rules 3 and 4).

    Raises:
        json.JSONDecodeError: the text is not JSON.
        ValueError: the answer cannot be parsed by _parse_nri_response, or the PDF
            cannot be opened by pdfplumber.
    """
    items = parse_pass2(json_str)
    return [failure.message for failure in _pass2_item_failures(items, pdf_bytes)]


# ---------------------------------------------------------------------------
# The conversion to millions: once per filing, after Pass 2, before any merge
# ---------------------------------------------------------------------------
# docs/4-conventions/units-and-signs.md: every money figure is in millions, the
# share count in millions of shares. Both routes call `convert_filing_to_millions`
# on each filing's statements and Pass 2 items, after that filing's Pass 2 (whose
# prompt is built from the statements as printed, so the model sees and answers in
# the filing's own units) and before any merge.

# Every field of each statement the conversion handles, beside `year`. A field
# added to a model and not listed here stops the conversion by name, rather than
# reaching the valuation unconverted (rule 3).
_INCOME_STATEMENT_CONVERTED: frozenset[str] = frozenset({
    "revenue", "cost_of_revenue", "sga", "rd_expense", "depreciation_amortization",
    "other_operating_expense", "interest_expense", "interest_income",
    "other_non_operating", "tax_expense", "diluted_shares_outstanding",
    "non_recurring_items",
})
_BALANCE_SHEET_CONVERTED: frozenset[str] = frozenset({
    "cash_and_equivalents", "short_term_investments", "accounts_receivable",
    "inventory", "other_current_assets", "ppe_net", "goodwill", "intangible_assets",
    "other_non_current_assets", "accounts_payable", "short_term_debt",
    "current_portion_lt_debt", "accrued_liabilities", "other_current_liabilities",
    "long_term_debt", "other_non_current_liabilities", "total_equity",
    "noncontrolling_interest_nonredeemable", "noncontrolling_interest_redeemable",
    "printed_total_assets", "printed_total_liabilities_and_equity",
    "printed_unit_in_millions",
})
_CASH_FLOW_CONVERTED: frozenset[str] = frozenset({
    "net_income", "depreciation_amortization", "stock_based_compensation",
    "change_in_working_capital", "other_operating_activities", "capital_expenditures",
    "acquisitions", "other_investing_activities", "debt_issued", "debt_repaid",
    "shares_issued", "shares_repurchased", "dividends_paid", "other_financing_activities",
})
_NON_RECURRING_ITEM_CONVERTED: frozenset[str] = frozenset({"amount"})
_NON_RECURRING_ITEM_NOT_FIGURES: frozenset[str] = frozenset({
    "year", "description", "line_item", "direction", "category", "confidence", "source",
    "page", "printed_units", "units_page",
})


def _require_every_field_converted(
    cls: type, converted: frozenset[str], not_figures: frozenset[str],
) -> None:
    """Stop when `cls` has a field the conversion does not list."""
    unlisted = sorted({f.name for f in dataclasses.fields(cls)} - converted - not_figures)
    if unlisted:
        raise ValueError(
            f"{cls.__name__} has field(s) {unlisted} that the conversion to millions "
            "does not handle, so they would reach the valuation in the filing's own "
            "units. List each in claude_extractor.py's conversion.",
        )


def _in_millions(value: float, scale: Fraction) -> float:
    """`value`, printed in units of `scale`, in millions. ONE operation: divide by
    1,000 for thousands, multiply by 1,000 for billions, multiply by 1 (exact) for
    millions. A float division by an integer is correctly rounded; a
    multiplication by 0.001 is not, so it is never used."""
    if scale.denominator == 1:
        return value * scale.numerator
    if scale.numerator != 1:
        raise ValueError(f"a scale of {scale} millions is neither 1/n nor n")
    return value / scale.denominator


def _optional_in_millions(value: float | None, scale: Fraction) -> float | None:
    """`_in_millions`, keeping None ("not extracted") as None."""
    return None if value is None else _in_millions(value, scale)


def convert_filing_to_millions(
    financials: FinancialStatements,
    non_recurring: list[NonRecurringItem],
    units: FilingUnits,
) -> tuple[FinancialStatements, list[NonRecurringItem]]:
    """One filing's statements and Pass 2 items, converted to millions once.

    Every money figure with the money scale read from `units` (the `units`
    statement), the diluted share count with the share scale (the `share_units`
    statement), and every balance sheet's `printed_unit_in_millions` set to the
    money scale, so its check stays at 1 printed unit. Each Pass 2 item is
    converted with its own scale read from its printed unit words
    (`pass2_amount_scale`), never with the filing's money scale.

    Both routes call this, per filing, after that filing's Pass 2 and before any
    merge: route A in `extract_financials`, route B in `load_session_extraction`.
    Each figure is converted once, after its printed lines are summed.

    Raises:
        ValueError: a balance sheet already carries `printed_unit_in_millions` (the
            filing was converted before; a second conversion would move every
            figure again), or a statement has a field this conversion does not list.
    """
    _require_every_field_converted(
        IncomeStatement, _INCOME_STATEMENT_CONVERTED, frozenset({"year"}))
    _require_every_field_converted(
        BalanceSheet, _BALANCE_SHEET_CONVERTED, frozenset({"year"}))
    _require_every_field_converted(
        CashFlowStatement, _CASH_FLOW_CONVERTED, frozenset({"year"}))
    _require_every_field_converted(
        NonRecurringItem, _NON_RECURRING_ITEM_CONVERTED, _NON_RECURRING_ITEM_NOT_FIGURES)
    _require_every_field_converted(
        FinancialStatements,
        frozenset({"income_statements", "balance_sheets", "cash_flow_statements"}),
        frozenset({"ticker", "company_name"}),
    )
    converted_already = [
        bs.year for bs in financials.balance_sheets if bs.printed_unit_in_millions is not None
    ]
    if converted_already:
        raise ValueError(
            f"the balance sheet(s) {converted_already} of {financials.ticker!r} already "
            "carry printed_unit_in_millions, so this filing was converted to millions "
            "before. A second conversion would move every figure again; it stops.",
        )

    money = units.money.scale.in_millions
    shares = units.shares.scale.in_millions
    print(f"  Units: money {units.money.printed!r} (page {units.money.page}) -> "
          f"{units.money.scale.word}; share count {units.shares.printed!r} (page "
          f"{units.shares.page}) -> {units.shares.scale.word}. Converted to millions.")

    income_statements = [
        replace(
            inc,
            revenue=_in_millions(inc.revenue, money),
            cost_of_revenue=_in_millions(inc.cost_of_revenue, money),
            sga=_in_millions(inc.sga, money),
            rd_expense=_in_millions(inc.rd_expense, money),
            depreciation_amortization=_in_millions(inc.depreciation_amortization, money),
            other_operating_expense=_in_millions(inc.other_operating_expense, money),
            interest_expense=_in_millions(inc.interest_expense, money),
            interest_income=_in_millions(inc.interest_income, money),
            other_non_operating=_in_millions(inc.other_non_operating, money),
            tax_expense=_in_millions(inc.tax_expense, money),
            diluted_shares_outstanding=_in_millions(inc.diluted_shares_outstanding, shares),
            non_recurring_items={
                key: _in_millions(amount, money)
                for key, amount in inc.non_recurring_items.items()
            },
        )
        for inc in financials.income_statements
    ]
    balance_sheets = [
        replace(
            bs,
            cash_and_equivalents=_in_millions(bs.cash_and_equivalents, money),
            short_term_investments=_in_millions(bs.short_term_investments, money),
            accounts_receivable=_in_millions(bs.accounts_receivable, money),
            inventory=_in_millions(bs.inventory, money),
            other_current_assets=_in_millions(bs.other_current_assets, money),
            ppe_net=_in_millions(bs.ppe_net, money),
            goodwill=_in_millions(bs.goodwill, money),
            intangible_assets=_in_millions(bs.intangible_assets, money),
            other_non_current_assets=_in_millions(bs.other_non_current_assets, money),
            accounts_payable=_in_millions(bs.accounts_payable, money),
            short_term_debt=_in_millions(bs.short_term_debt, money),
            current_portion_lt_debt=_in_millions(bs.current_portion_lt_debt, money),
            accrued_liabilities=_in_millions(bs.accrued_liabilities, money),
            other_current_liabilities=_in_millions(bs.other_current_liabilities, money),
            long_term_debt=_in_millions(bs.long_term_debt, money),
            other_non_current_liabilities=_in_millions(bs.other_non_current_liabilities, money),
            total_equity=_in_millions(bs.total_equity, money),
            noncontrolling_interest_nonredeemable=_optional_in_millions(
                bs.noncontrolling_interest_nonredeemable, money),
            noncontrolling_interest_redeemable=_optional_in_millions(
                bs.noncontrolling_interest_redeemable, money),
            printed_total_assets=_optional_in_millions(bs.printed_total_assets, money),
            printed_total_liabilities_and_equity=_optional_in_millions(
                bs.printed_total_liabilities_and_equity, money),
            printed_unit_in_millions=float(money),
        )
        for bs in financials.balance_sheets
    ]
    cash_flow_statements = [
        replace(
            cf,
            net_income=_in_millions(cf.net_income, money),
            depreciation_amortization=_in_millions(cf.depreciation_amortization, money),
            stock_based_compensation=_in_millions(cf.stock_based_compensation, money),
            change_in_working_capital=_in_millions(cf.change_in_working_capital, money),
            other_operating_activities=_in_millions(cf.other_operating_activities, money),
            capital_expenditures=_in_millions(cf.capital_expenditures, money),
            acquisitions=_in_millions(cf.acquisitions, money),
            other_investing_activities=_in_millions(cf.other_investing_activities, money),
            debt_issued=_in_millions(cf.debt_issued, money),
            debt_repaid=_in_millions(cf.debt_repaid, money),
            shares_issued=_in_millions(cf.shares_issued, money),
            shares_repurchased=_in_millions(cf.shares_repurchased, money),
            dividends_paid=_in_millions(cf.dividends_paid, money),
            other_financing_activities=_in_millions(cf.other_financing_activities, money),
        )
        for cf in financials.cash_flow_statements
    ]
    items = [
        replace(
            item,
            amount=_in_millions(
                item.amount,
                pass2_amount_scale(item.printed_units, item.amount).in_millions,
            ),
        )
        for item in non_recurring
    ]
    converted = replace(
        financials,
        income_statements=income_statements,
        balance_sheets=balance_sheets,
        cash_flow_statements=cash_flow_statements,
    )
    return converted, items


# ===========================================================================
# Public API
# ===========================================================================

def extract_financials(
    pdf_path: str | Path,
    ticker: str = "",
    company_name: str = "",
    provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER,
    model: str | None = None,
    target_years: list[int] | None = None,
    include_bs: bool = True,
    debug: bool = False,
) -> tuple[FinancialStatements, list[NonRecurringItem]]:
    """Extract financial data from a single 10-K/10-Q PDF using two LLM passes.

    The raw PDF is sent directly to the LLM for native document ingestion
    (no intermediate text extraction).

    Pass 1: Extract I/S + C/F (+ optional B/S) for target years.
    Pass 2: Analyze footnotes for non-recurring items, using Pass 1 I/S as context.
    Then both are converted to millions once (`convert_filing_to_millions`), from
    the scales Python read in the filing's printed unit statements. Pass 2's prompt
    is built from the statements as printed, before the conversion.

    Args:
        pdf_path:      Path to the PDF filing.
        ticker:        Stock ticker.
        company_name:  Company name.
        provider:      "claude" or "gemini". Defaults to
                       config.DEFAULT_EXTRACTION_PROVIDER.
        model:         Override model ID.
        target_years:  Specific fiscal years to extract. None = all years in filing.
        include_bs:    Whether to extract the balance sheet (default True).
        debug:         Print raw LLM responses.

    Returns:
        (FinancialStatements, list[NonRecurringItem]), every figure in millions.
    """
    resolution = resolve_provider(provider, model)

    # Rule 6: which model read this filing, over which transport, on whose
    # credential, is an assumption about every figure below. Say it out loud.
    print(f"\n  {describe_resolution(resolution)}")
    pdf_bytes = _read_pdf_bytes(pdf_path)

    # Pass 1: Financial data extraction, as printed, with its unit statements
    financials, units = _run_financials_pass(
        pdf_bytes, ticker, company_name, resolution,
        target_years=target_years, include_bs=include_bs, debug=debug,
    )

    # Pass 2: Non-recurring item analysis (receives Pass 1 I/S as context, as
    # printed, so its amounts are in the filing's own units too)
    nri = _run_nri_pass(
        pdf_bytes, financials, resolution,
        target_years=target_years, debug=debug,
    )

    # Both passes to millions, once, before any merge (extract_multi_year merges).
    return convert_filing_to_millions(financials, nri, units)


def extract_multi_year(
    filings: Sequence[tuple[int, str | Path]],
    ticker: str = "",
    company_name: str = "",
    provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER,
    model: str | None = None,
    debug: bool = False,
) -> tuple[FinancialStatements, list[NonRecurringItem]]:
    """Smart multi-PDF extraction with year-targeting.

    Raw PDFs are sent directly to the LLM for native document ingestion.

    Minimizes redundant LLM calls by extracting each year from only one filing:
      - Oldest filing: extract ALL years (picks up comparative years like Y-1, Y-2)
      - Other filings: extract ONLY the primary fiscal year
      - Balance sheet: extracted only from the most recent filing

    Example:
        filings = [(2025, "10K_2025.pdf"), (2024, "10K_2024.pdf"), (2023, "10K_2023.pdf")]
        → 2023 10-K: extract all years (2023, 2022, 2021)  — no B/S
        → 2024 10-K: extract [2024] only                   — no B/S
        → 2025 10-K: extract [2025] only                   — with B/S

    Args:
        filings:       Sequence of (fiscal_year, pdf_path) tuples. `Sequence`,
                       not `list`, for the reason `plan_filings` gives: `list`
                       is invariant, so a `list[tuple[int, str]]` — what both
                       entry points hold — would not satisfy `list[tuple[int,
                       str | Path]]`. Nothing here mutates it.
        ticker:        Stock ticker.
        company_name:  Company name.
        provider:      "claude" or "gemini". Defaults to
                       config.DEFAULT_EXTRACTION_PROVIDER — the same default as
                       extract_financials, so the number of PDFs uploaded cannot
                       change which model reads them.
        model:         Override model ID.
        debug:         Print raw LLM responses.

    Returns:
        Merged (FinancialStatements, list[NonRecurringItem]) across all filings.
    """
    plans = plan_filings(filings)  # raises on an empty list

    if len(plans) == 1:
        # Single filing — just extract everything. Deliberately NOT passed through
        # merge_filing_extractions: the merge re-sorts and replaces the parsed
        # ticker, and a single filing's result is returned exactly as parsed.
        plan = plans[0]
        return extract_financials(
            pdf_path=plan.pdf_path,
            ticker=ticker, company_name=company_name,
            provider=provider, model=model,
            target_years=_plan_target_years(plan), include_bs=plan.include_bs,
            debug=debug,
        )

    # Print extraction plan
    print(f"\n{'='*65}")
    print(f"MULTI-YEAR EXTRACTION PLAN — {ticker or 'Unknown'}")
    print(f"{'='*65}")
    for plan in plans:
        if plan.target_years is None:
            plan_text = "all years (oldest filing)"
        else:
            plan_text = f"year {plan.fiscal_year} only"
        bs = " + B/S" if plan.include_bs else ""
        print(f"  {Path(plan.pdf_path).name} -> {plan_text}{bs}")
    print(f"{'='*65}")

    # Execute extraction for each filing, in plan order
    extractions: list[tuple[FilingPlan, FinancialStatements, list[NonRecurringItem]]] = []
    for plan in plans:
        print(f"\n{'='*65}")
        print(f"EXTRACTING: {Path(plan.pdf_path).name}  (fiscal {plan.fiscal_year})")
        print(f"{'='*65}")

        fin, nri = extract_financials(
            pdf_path=plan.pdf_path,
            ticker=ticker,
            company_name=company_name,
            provider=provider,
            model=model,
            target_years=_plan_target_years(plan),
            include_bs=plan.include_bs,
            debug=debug,
        )
        extractions.append((plan, fin, nri))

    merged, all_nri = merge_filing_extractions(extractions, ticker, company_name)

    print(f"\n{'='*65}")
    print(f"MERGED: {len(merged.years)} years {merged.years}, "
          f"{len(all_nri)} non-recurring item(s)")
    print(f"{'='*65}")

    return merged, all_nri
