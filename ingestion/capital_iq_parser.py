"""[PHASE 1 LEGACY ADAPTER — for testing only]

This parser is a rigid row/column mapper for the specific Capital IQ Pro
"As Reported" Excel template. It works for Phase 1 validation but is NOT
the long-term data ingestion strategy.

PHASE 2 REPLACEMENT: ingestion/claude_extractor.py
  Claude reads any Excel layout + 10-K/10-Q PDF together, extracts the
  same FinancialStatements contract, and simultaneously flags non-recurring
  items — without any hard-coded row/column mappings.

DO NOT ADD NEW COMPANY-SPECIFIC MAPPINGS HERE. If a company's layout
differs, use the Phase 2 Claude extractor once it is implemented.

---

Parse S&P Capital IQ Pro Excel exports into FinancialStatements objects.

Capital IQ "As Reported" exports have a consistent format:
- Single .xlsx workbook with 3 sheets:
  - "Balance Sheet (As Reported)"
  - "Income Statement (As Reported)"
  - "Cash Flow (As Reported)"
- 11 header rows (blank, company name, source, period info, currency, units)
- Row 12 (0-indexed: 11) contains column headers: label + "2024 FY", "2023 FY", ...
- Row 13+: "Period Ended", "Currency", "Units", then data rows
- Values are strings: "350018", "-146306", "NA"
- Negative values use minus prefix (not parentheses)
- Units are in Millions
- Expenses on I/S are negative numbers

DESIGN: Section-aware bucketing
  CIQ exports use section headers (e.g. "Current Assets", "Operating Activities")
  that have NaN in the data columns.  The parser:
    1. Tracks which section it's in by detecting those header rows.
    2. Maps well-known line items to named dataclass fields.
    3. Accumulates ALL unmapped items into the "other" bucket for the
       current section (other_current_assets, other_non_current_assets, etc.).
    4. Skips "Total ..." rows so they don't double-count.
  This makes parsing robust across companies with different F/S layouts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
)


# ---------------------------------------------------------------------------
# Row label → dataclass field mappings (used by section-aware parsers)
# Keys are matched case-insensitively via substring.
# ---------------------------------------------------------------------------

# Balance Sheet: known items we want in named fields
# Anything NOT matched here gets bucketed by section.
BS_KNOWN: list[tuple[str, str]] = [
    ("cash and cash equivalents", "cash_and_equivalents"),
    ("non-marketable", "_non_marketable_securities"),   # must come before "marketable"
    ("marketable securities", "short_term_investments"),
    ("short-term investments", "short_term_investments"),
    ("accounts receivable", "accounts_receivable"),
    ("inventories", "inventory"),
    ("inventory", "inventory"),
    ("property and equipment", "ppe_net"),
    ("property, plant", "ppe_net"),
    ("net property", "ppe_net"),
    ("goodwill", "goodwill"),
    ("intangible assets", "intangible_assets"),
    ("accounts payable", "accounts_payable"),
    ("accrued compensation", "accrued_liabilities"),
    ("short-term debt", "short_term_debt"),
    ("short-term borrowings", "short_term_debt"),
    ("notes payable", "short_term_debt"),
    ("current portion of long-term", "current_portion_lt_debt"),
    ("current maturities of long-term", "current_portion_lt_debt"),
    ("long-term debt", "long_term_debt"),
    ("total shareholders equity", "total_equity"),
    ("total stockholders equity", "total_equity"),
    ("total shareholders' equity", "total_equity"),
    ("total stockholders' equity", "total_equity"),
]

# B/S section headers and which "bucket" field unmapped items go into
# IMPORTANT: more-specific patterns must come before less-specific ones
# because matching uses substring "in".  E.g. "noncurrent assets" before
# "current assets", otherwise "Noncurrent Assets" matches "current assets".
BS_SECTIONS: dict[str, str | None] = {
    "noncurrent assets":    "other_non_current_assets",
    "non-current assets":   "other_non_current_assets",
    "current assets":       "other_current_assets",
    "noncurrent liabilities": "other_non_current_liabilities",
    "non-current liabilities": "other_non_current_liabilities",
    "current liabilities":  "other_current_liabilities",
    "shareholders equity":  "_equity",   # equity items -> skip (we use total)
    "stockholders equity":  "_equity",
}

# Labels to always skip (totals, sub-totals, disclaimers)
BS_SKIP_PATTERNS: list[str] = [
    "total current assets",
    "total assets",
    "total current liabilities",
    "total liabilities",
    "total liabilities &",
    "total liabilities and",
    "data shown on this page",
    "period ended",
    "currency",
    "units",
]

# Income Statement: known items
IS_KNOWN: list[tuple[str, str]] = [
    # Specific patterns FIRST to avoid false matches
    ("cost of revenues", "cost_of_revenue"),
    ("cost of goods sold", "cost_of_revenue"),
    ("cost of sales", "cost_of_revenue"),
    ("sales and marketing", "_sales_and_marketing"),
    ("selling, general and admin", "sga"),
    ("selling general", "sga"),
    ("general and admin", "_general_and_admin"),
    ("research and development", "rd_expense"),
    ("research & development", "rd_expense"),
    ("depreciation & amort", "depreciation_amortization"),
    ("depreciation and amort", "depreciation_amortization"),
    ("other income/expense", "other_non_operating"),
    ("other income (expense)", "other_non_operating"),
    ("other non-operating", "other_non_operating"),
    ("interest expense", "interest_expense"),
    ("interest income", "interest_income"),
    ("provision for income tax", "tax_expense"),
    ("taxes and other", "tax_expense"),
    ("income tax", "tax_expense"),
    ("diluted shares", "diluted_shares_outstanding"),
    ("diluted weighted", "diluted_shares_outstanding"),
    # Revenue — general match LAST
    ("revenues", "revenue"),
    ("total revenue", "revenue"),
    ("net revenue", "revenue"),
]

IS_SKIP_PATTERNS: list[str] = [
    "operating income",
    "net income",
    "earnings before",
    "basic shares",
    "supplementary",
    "data shown on this page",
]

# Cash Flow: known items
CF_KNOWN: list[tuple[str, str]] = [
    ("net income", "net_income"),
    ("depreciation and impairment of property", "depreciation_amortization"),
    ("depreciation & amort", "depreciation_amortization"),
    ("depreciation and amort", "depreciation_amortization"),
    ("amortization and impairment of intangible", "_amortization_intangibles"),
    ("amortization of intangible", "_amortization_intangibles"),
    ("stock based compensation", "stock_based_compensation"),
    ("stock-based compensation", "stock_based_compensation"),
    ("share-based comp", "stock_based_compensation"),
    ("purchase of property and equipment", "capital_expenditures"),
    ("capital expenditure", "capital_expenditures"),
    ("purchases of property", "capital_expenditures"),
    ("acquisitions", "acquisitions"),
    ("repayment of debt", "debt_repaid"),
    ("repayments of debt", "debt_repaid"),
    ("proceeds from issuance of debt", "debt_issued"),
    ("issuance of debt", "debt_issued"),
    ("repurchases of common", "shares_repurchased"),
    ("repurchase of stock", "shares_repurchased"),
    ("dividend payment", "dividends_paid"),
    ("dividend", "dividends_paid"),
]

CF_SECTIONS: dict[str, str] = {
    "operating activities":  "other_operating",
    "investing activities":  "other_investing",
    "financing activities":  "other_financing",
    "other adjustments":     "_skip",
}

CF_SKIP_PATTERNS: list[str] = [
    "cash flow from operating",
    "cash flow from investing",
    "cash flow from financing",
    "cash flow net changes",
    "net change in cash",
    "foreign exchange rate",
    "data shown on this page",
]


def _safe_float(value) -> float:
    """Convert a cell value to float, handling NA, NaN, commas, parentheses."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return 0.0
        return float(value)
    s = str(value).strip()
    if s.upper() in ("NA", "N/A", "NM", "-", ""):
        return 0.0
    # Remove commas, handle parentheses as negative
    s = s.replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _parse_sheet(
    file_path: str | Path,
    sheet_name: str | int,
) -> tuple[pd.DataFrame, list[int], list[str]]:
    """Parse a Capital IQ sheet, returning the data and year info.

    Returns:
        (df, years, year_columns) where:
        - df has 'label' as first column, year columns as data
        - years is list of ints like [2024, 2023, 2022, ...]
        - year_columns is list of column names like ["2024 FY", "2023 FY", ...]
    """
    # Read with header at row 11 (0-indexed) — the "Recommended: S&P Capital IQ" row
    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=11,
        engine="openpyxl",
    )

    # First column is the label
    df = df.rename(columns={df.columns[0]: "label"})
    df["label"] = df["label"].astype(str).str.strip()

    # Extract year columns (format: "2024 FY", "2023 FY", etc.)
    years = []
    year_columns = []
    for col in df.columns[1:]:
        col_str = str(col).strip()
        match = re.match(r"(\d{4})\s*FY", col_str)
        if match:
            years.append(int(match.group(1)))
            year_columns.append(col_str)
        else:
            # Also try plain year
            try:
                y = int(col_str)
                if 1990 <= y <= 2100:
                    years.append(y)
                    year_columns.append(col_str)
            except ValueError:
                pass

    return df, years, year_columns


def _match_label(label: str, mapping: list[tuple[str, str]]) -> str | None:
    """Match a Capital IQ row label to a field name using ordered mapping."""
    label_lower = label.lower().strip()
    for pattern, field_name in mapping:
        if pattern in label_lower:
            return field_name
    return None


def _should_skip(label: str, skip_patterns: list[str]) -> bool:
    """Return True if this label is a total/sub-total row we should ignore."""
    label_lower = label.lower().strip()
    return any(p in label_lower for p in skip_patterns)


def _normalize(text: str) -> str:
    """Normalize text for matching: lowercase, strip, replace fancy apostrophes."""
    # CIQ exports sometimes use RIGHT SINGLE QUOTATION MARK (\u2019) instead
    # of a regular ASCII apostrophe (\u0027).  Normalize both away.
    return text.lower().strip().replace("\u2019", "").replace("\u0027", "").replace("'", "")


def _is_section_header(label: str, raw_val, sections: dict) -> str | None | bool:
    """Check if this row is a section header.

    Returns:
        - A bucket field name (str) if matched to a section with a bucket
        - False if no match (not a section header)
        - The mapped value otherwise (could be special sentinel)
    """
    if raw_val is not None:
        if not (isinstance(raw_val, float) and pd.isna(raw_val)):
            if not (isinstance(raw_val, str) and raw_val.strip() == ""):
                return False  # has actual data → not a section header
    label_norm = _normalize(label)
    for pattern, bucket in sections.items():
        if _normalize(pattern) in label_norm:
            return bucket  # str or special sentinel
    return False


def _has_data(raw_val) -> bool:
    """Return True if the cell has actual numeric data (not None/NaN/empty)."""
    if raw_val is None:
        return False
    if isinstance(raw_val, float) and pd.isna(raw_val):
        return False
    if isinstance(raw_val, str) and raw_val.strip() in ("", "NA", "N/A", "NM", "-"):
        return False
    return True


# ---------------------------------------------------------------------------
# Section-aware parsers
# ---------------------------------------------------------------------------

def parse_balance_sheet(
    file_path: str | Path,
    sheet_name: str | int = "Balance Sheet (As Reported)",
) -> list[BalanceSheet]:
    """Parse Capital IQ balance sheet using section-aware bucketing.

    Unknown items within 'Current Assets' auto-bucket into other_current_assets,
    unknown items within 'Noncurrent Liabilities' into other_non_current_liabilities, etc.
    """
    df, years, year_columns = _parse_sheet(file_path, sheet_name)

    statements = []
    for year, col in zip(years, year_columns):
        # Named fields (first match wins within a field, but multiple items with
        # the same mapped field get SUMMED — e.g. multiple debt rows)
        fields: dict[str, float] = {}
        # Buckets for each section (accumulated)
        buckets: dict[str, float] = {
            "other_current_assets": 0.0,
            "other_non_current_assets": 0.0,
            "other_current_liabilities": 0.0,
            "other_non_current_liabilities": 0.0,
        }
        current_bucket: str | None = None  # which section we're in

        for _, row in df.iterrows():
            label = str(row["label"]).strip()
            if not label or label == "nan":
                continue
            raw_val = row.get(col, None)

            # Check section header
            sec = _is_section_header(label, raw_val, BS_SECTIONS)
            if sec is not False:
                # sec is a bucket name or "_equity" sentinel
                if sec and not sec.startswith("_"):
                    current_bucket = sec
                else:
                    current_bucket = None  # equity section or other skip
                continue

            # Skip rows with no data
            if not _has_data(raw_val):
                continue

            val = _safe_float(raw_val)

            # Try named field mapping BEFORE skip check.
            # This lets "Total Shareholders Equity" match total_equity
            # while other totals (Total Assets, Total Current Assets)
            # still get skipped since they have no BS_KNOWN match.
            field = _match_label(label, BS_KNOWN)
            if field:
                if field.startswith("_"):
                    # Fields prefixed with _ are "recognized but not named" —
                    # route them into the current section bucket instead.
                    if current_bucket and current_bucket in buckets:
                        buckets[current_bucket] += val
                else:
                    # SUM into named field (handles multiple rows for same concept)
                    fields[field] = fields.get(field, 0.0) + val
                continue

            # Skip total/sub-total rows (only if not already captured as named field)
            if _should_skip(label, BS_SKIP_PATTERNS):
                continue

            if current_bucket and current_bucket in buckets:
                # Unmapped → bucket by section
                buckets[current_bucket] += val

        stmt = BalanceSheet(
            year=year,
            cash_and_equivalents=fields.get("cash_and_equivalents", 0),
            short_term_investments=fields.get("short_term_investments", 0),
            accounts_receivable=fields.get("accounts_receivable", 0),
            inventory=fields.get("inventory", 0),
            other_current_assets=buckets["other_current_assets"],
            ppe_net=fields.get("ppe_net", 0),
            goodwill=fields.get("goodwill", 0),
            intangible_assets=fields.get("intangible_assets", 0),
            other_non_current_assets=buckets["other_non_current_assets"],
            accounts_payable=fields.get("accounts_payable", 0),
            short_term_debt=fields.get("short_term_debt", 0),
            current_portion_lt_debt=fields.get("current_portion_lt_debt", 0),
            accrued_liabilities=fields.get("accrued_liabilities", 0),
            other_current_liabilities=buckets["other_current_liabilities"],
            long_term_debt=fields.get("long_term_debt", 0),
            other_non_current_liabilities=buckets["other_non_current_liabilities"],
            total_equity=fields.get("total_equity", 0),
        )
        statements.append(stmt)

    return sorted(statements, key=lambda s: s.year)


def parse_income_statement(
    file_path: str | Path,
    sheet_name: str | int = "Income Statement (As Reported)",
) -> list[IncomeStatement]:
    """Parse Capital IQ income statement.

    Handles:
    - Expenses as negative numbers (converted to positive)
    - Split SGA: "Sales and Marketing" + "General and Administrative"
    - Unmapped operating expense items bucketed into other_operating_expense
    """
    df, years, year_columns = _parse_sheet(file_path, sheet_name)

    # I/S sections: "Revenues", "Expenses", "Taxes and Other Expenses",
    # "Supplementary Info" — we mainly care about bucketing unmapped
    # operating expense items
    IS_SECTION_HEADERS = [
        "revenues", "expenses", "taxes and other expenses",
        "supplementary info",
    ]

    statements = []
    for year, col in zip(years, year_columns):
        fields: dict[str, float] = {}
        other_opex = 0.0  # bucket for unmapped expense items
        in_expenses_section = False

        for _, row in df.iterrows():
            label = str(row["label"]).strip()
            if not label or label == "nan":
                continue
            raw_val = row.get(col, None)

            # Detect section headers
            label_lower = label.lower()
            is_section = any(label_lower == sh for sh in IS_SECTION_HEADERS)
            if is_section and not _has_data(raw_val):
                in_expenses_section = "expense" in label_lower
                continue

            # Skip total/supplementary rows
            if _should_skip(label, IS_SKIP_PATTERNS):
                continue

            if not _has_data(raw_val):
                continue

            val = _safe_float(raw_val)

            # Try named field mapping
            field = _match_label(label, IS_KNOWN)
            if field:
                fields[field] = fields.get(field, 0.0) + val
            elif in_expenses_section:
                # Unmapped expense line → bucket
                other_opex += val

        # Build statement — convert negative expenses to positive
        cost_of_revenue = abs(fields.get("cost_of_revenue", 0))
        rd_expense = abs(fields.get("rd_expense", 0))
        tax_expense = abs(fields.get("tax_expense", 0))

        sga = abs(fields.get("sga", 0))
        if sga == 0:
            sales_marketing = abs(fields.get("_sales_and_marketing", 0))
            general_admin = abs(fields.get("_general_and_admin", 0))
            sga = sales_marketing + general_admin

        da = abs(fields.get("depreciation_amortization", 0))

        stmt = IncomeStatement(
            year=year,
            revenue=fields.get("revenue", 0),
            cost_of_revenue=cost_of_revenue,
            sga=sga,
            rd_expense=rd_expense,
            depreciation_amortization=da,
            other_operating_expense=abs(other_opex),
            interest_expense=abs(fields.get("interest_expense", 0)),
            interest_income=fields.get("interest_income", 0),
            other_non_operating=fields.get("other_non_operating", 0),
            tax_expense=tax_expense,
            diluted_shares_outstanding=fields.get("diluted_shares_outstanding", 0),
        )
        statements.append(stmt)

    return sorted(statements, key=lambda s: s.year)


def parse_cash_flow(
    file_path: str | Path,
    sheet_name: str | int = "Cash Flow (As Reported)",
) -> list[CashFlowStatement]:
    """Parse Capital IQ cash flow statement using section-aware bucketing.

    Unmapped items within Operating/Investing/Financing sections are
    accumulated into the "other" field for that section.
    """
    df, years, year_columns = _parse_sheet(file_path, sheet_name)

    statements = []
    for year, col in zip(years, year_columns):
        fields: dict[str, float] = {}
        buckets = {
            "other_operating": 0.0,
            "other_investing": 0.0,
            "other_financing": 0.0,
        }
        current_bucket: str | None = None

        for _, row in df.iterrows():
            label = str(row["label"]).strip()
            if not label or label == "nan":
                continue
            raw_val = row.get(col, None)

            # Check section header
            sec = _is_section_header(label, raw_val, CF_SECTIONS)
            if sec is not False:
                current_bucket = sec if (sec and sec != "_skip") else None
                continue

            # Skip total rows
            if _should_skip(label, CF_SKIP_PATTERNS):
                continue

            if not _has_data(raw_val):
                continue

            val = _safe_float(raw_val)

            # Try named field mapping
            field = _match_label(label, CF_KNOWN)
            if field:
                fields[field] = fields.get(field, 0.0) + val
            elif current_bucket and current_bucket in buckets:
                buckets[current_bucket] += val

        # D&A: combine property depreciation + intangible amortization
        da = fields.get("depreciation_amortization", 0) + fields.get("_amortization_intangibles", 0)

        stmt = CashFlowStatement(
            year=year,
            net_income=fields.get("net_income", 0),
            depreciation_amortization=da,
            stock_based_compensation=fields.get("stock_based_compensation", 0),
            change_in_working_capital=0,  # CIQ doesn't have a single WC line; derived from B/S
            other_operating_activities=buckets["other_operating"],
            capital_expenditures=fields.get("capital_expenditures", 0),
            acquisitions=fields.get("acquisitions", 0),
            other_investing_activities=buckets["other_investing"],
            debt_issued=fields.get("debt_issued", 0),
            debt_repaid=fields.get("debt_repaid", 0),
            shares_issued=fields.get("shares_issued", 0),
            shares_repurchased=fields.get("shares_repurchased", 0),
            dividends_paid=fields.get("dividends_paid", 0),
            other_financing_activities=buckets["other_financing"],
        )
        statements.append(stmt)

    return sorted(statements, key=lambda s: s.year)


def parse_capital_iq(
    file_path: str | Path,
    ticker: str,
    company_name: str = "",
) -> FinancialStatements:
    """Parse a Capital IQ workbook (single file with 3 sheets) into FinancialStatements.

    Args:
        file_path: Path to the Capital IQ .xlsx export.
        ticker: Stock ticker symbol.
        company_name: Optional company name.
    """
    return FinancialStatements(
        ticker=ticker,
        company_name=company_name,
        income_statements=parse_income_statement(file_path),
        balance_sheets=parse_balance_sheet(file_path),
        cash_flow_statements=parse_cash_flow(file_path),
    )
