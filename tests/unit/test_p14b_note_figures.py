"""Tests for P14b: Pass 1 note/MD&A printed figures under filing unit statements (Check B1).

Check B1 (user decision of 2026-10-04, rule 1 option B):
Pass 1 allows a printed figure from a note or MD&A when the statement does not
print that field's row by itself, copied in the unit printed there without conversion.
Python verifies every Pass 1 printed row via `_row_scale_failures`:
the row's cited page, or the preceding page (page - 1), must print a parenthesised
unit statement of the filing's scale for that row's kind ("money figures" vs "share count").
If not, the run stops across Route A (retries exhausted -> ValueError) and
Route B (session_extraction check -> exit 2).

Verifies:
1. Unit statement on row's page confirms scale (0 failures).
2. Unit statement on preceding page (page - 1) confirms scale (0 failures).
3. No unit statement on page or page - 1 fails naming page, kind, expected scale, and all citing rows.
4. Grouping of multiple citing rows on the same page into a single failure per (page, kind).
5. Mismatched unit statement (expected millions, found thousands) fails naming expected and found statements.
6. Distinct kinds ("money figures" vs "share count") verified independently (e.g. Okta two scales).
7. Multi-scale limit: page with multiple statements ((In millions) and (In thousands)) confirms rows of either scale.
8. Unparenthesised prose ($1.2 billion in MD&A prose) cannot confirm scale and stops.
9. Page beyond PDF page count or page with no text layer stops.
10. Route A retry exhaustion raises ValueError listing unconfirmed scale failures.
11. Route B session_extraction check exits 2 on scale failures, and load_session_extraction raises ValueError.
12. Summary line output format verified:
    "  Row unit scales looked up on their cited pages: X checked, Y pages, Z pages not confirmed."
13. Rule 3 stops: missing keys (units, share_units, year, label, page) and invalid PDF bytes.
14. Real 10-K filings: Walmart, Chipotle, Okta, and L3Harris.

All expected values derived independently via hand arithmetic, closed-form properties,
or verified from real 10-K filing pages. No network calls.
"""

from __future__ import annotations

import copy
import hashlib
import json
import socket
from pathlib import Path
from typing import Any

import pytest

import ingestion.claude_extractor as ce
from ingestion.claude_extractor import (
    PASS1_BALANCE_SHEET_LINE_FIELDS,
    PASS1_YEAR_LINE_FIELDS,
    ProviderResolution,
    _row_scale_failures,
    unit_statement_page_failures,
)
from ingestion.session_extraction import (
    SESSION_FORMAT,
    cmd_check,
    load_session_extraction,
)
from tests.unit._session_route_helpers import (
    make_pdf,
    pass1_answer,
    pass2_answer,
)
from tests.unit._text_pdf import write_text_pdf

# ---------------------------------------------------------------------------
# Test fixtures and builders
# ---------------------------------------------------------------------------

_TICKER = "TST"
_COMPANY = "Test Corp"

_REAL_WALMART_PDF = Path("10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf")
_REAL_CHIPOTLE_PDF = Path("10K_filings/Chipotle/Chipotle Mexican Grill Inc._10-K_2025-12-31_English.pdf")
_REAL_OKTA_PDF = Path("10K_filings/Okta/Okta Inc._10-K_2026-01-31_English.pdf")
_REAL_LHX_PDF = Path("10K_filings/LHX/L3Harris Technologies Inc._10-K_2026-01-02_English.pdf")


def _historical_year(
    year: int = 2024,
    **overrides: Any,
) -> dict[str, Any]:
    """Build a complete historical year dict with all standard line fields."""
    entry: dict[str, Any] = {"year": year}
    for field in PASS1_YEAR_LINE_FIELDS:
        entry[field] = []
    entry.update(overrides)
    return entry


def _balance_sheet(
    year: int = 2024,
    **overrides: Any,
) -> dict[str, Any]:
    """Build a complete latest_balance_sheet dict with all standard line fields."""
    bs: dict[str, Any] = {"year": year}
    for field in PASS1_BALANCE_SHEET_LINE_FIELDS:
        bs[field] = []
    bs.update(overrides)
    return bs


def _pass1_dict(
    *,
    units_printed: str = "(in millions)",
    units_page: int = 1,
    share_units_printed: str = "(in millions)",
    share_units_page: int = 1,
    historical_years: list[dict[str, Any]] | None = None,
    latest_balance_sheet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal Pass 1 dictionary."""
    if historical_years is None:
        historical_years = [_historical_year(
            year=2024,
            revenue=[{"label": "Total revenues", "value": 1000.0, "page": 1}],
        )]
    return {
        "ticker": _TICKER,
        "company_name": _COMPANY,
        "currency": "USD",
        "units": {"printed": units_printed, "page": units_page},
        "share_units": {"printed": share_units_printed, "page": share_units_page},
        "historical_years": historical_years,
        "latest_balance_sheet": latest_balance_sheet if latest_balance_sheet is not None else {},
    }


def _session_dict(pdf: Path, pass1_data: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal session-extraction-v4 dictionary."""
    data = pdf.read_bytes()
    return {
        "format": SESSION_FORMAT,
        "ticker": _TICKER,
        "company_name": _COMPANY,
        "extracted_by": {"model": "test-model", "tool": "Claude Code", "date": "2026-10-04"},
        "filings": [{
            "fiscal_year": 2024,
            "pdf_path": str(pdf),
            "pdf_sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "target_years": None,
            "include_bs": True,
            "pages_read": {"pass1": [1, 2, 3], "pass2": [1]},
            "pass1": pass1_data,
            "pass2": pass2_answer(),
        }],
    }


# ===========================================================================
# 1. Scale confirmation on row page and preceding page
# ===========================================================================

def test_row_scale_confirmed_on_row_page(tmp_path: Path) -> None:
    """Row's own page carries a matching parenthesised unit statement -> 0 failures.

    Expected value derivation (hand arithmetic):
      Filing units: '(in millions)' -> money scale is 'millions'.
      Row: 'Total revenues' on page 1.
      Page 1 text holds '(in millions)'.
      Candidate words on page 1: ['millions'].
      'millions' == expected 'millions' -> 0 failures.
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["(in millions)", "Total revenues 1,000"],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Total revenues", "value": 1000.0, "page": 1}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert failures == []


def test_row_scale_confirmed_on_preceding_page(tmp_path: Path) -> None:
    """Row on page 2 has no statement, but page 1 (page - 1) has matching statement -> 0 failures.

    Expected value derivation (hand arithmetic):
      Filing units: '(in millions)' -> money scale is 'millions'.
      Row: 'Total revenues' on page 2.
      Page 1 holds '(in millions)'. Page 2 holds 'Total revenues 1,000' (no unit statement).
      pages_to_check for page 2: (2, 1).
      Candidate words across pages 2 and 1: ['millions'].
      'millions' == expected 'millions' -> 0 failures.
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["(in millions)"],
        ["Total revenues 1,000"],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Total revenues", "value": 1000.0, "page": 2}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert failures == []


def test_row_on_page_1_checks_page_1_only(tmp_path: Path) -> None:
    """Row on page 1 cannot check page 0 (page > 1 condition).

    Expected value derivation:
      Row is on page 1. Page 1 text has no unit statement.
      pages_to_check is (1,). Page 0 is not checked.
      Expected: millions. Statement desc: 'no unit statement on page 1'.
      1 failure naming page 1, money figures, expected millions.
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["Total revenues 1,000"],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Total revenues", "value": 1000.0, "page": 1}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert len(failures) == 1
    msg = failures[0].message
    assert "page 1 (money figures): expected millions, no unit statement on page 1" in msg
    assert "'Total revenues' (revenue, year 2024)" in msg


# ===========================================================================
# 2. Missing unit statement and grouping of rows
# ===========================================================================

def test_no_unit_statement_on_page_or_preceding_fails_with_named_details(tmp_path: Path) -> None:
    """No unit statement on page 3 or page 2 -> 1 failure naming page, kind, scale, and row.

    Expected value derivation:
      Row on page 3. Page 1 has '(in millions)'.
      Pages 2 and 3 have no unit statement.
      pages_to_check: (3, 2). Neither page has any parenthesised scale group.
      Failure message must state:
        'page 3 (money figures): expected millions, no unit statement on page 3 or 2. Rows citing page 3: 'Total revenues' (revenue, year 2024).'
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["(in millions)"],
        ["Overview section"],
        ["Total revenues 1,000"],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Total revenues", "value": 1000.0, "page": 3}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert len(failures) == 1
    expected_msg = (
        "page 3 (money figures): expected millions, no unit statement on page 3 or 2. "
        "Rows citing page 3: 'Total revenues' (revenue, year 2024)."
    )
    assert failures[0].message == expected_msg
    assert failures[0].retry_message == expected_msg


def test_multiple_rows_on_same_page_grouped_into_single_failure(tmp_path: Path) -> None:
    """Multiple rows on page 3 produce exactly one failure for (3, 'money figures') listing all rows.

    Expected value derivation:
      Three rows cite page 3:
        1. 'Total revenues' (revenue, year 2024)
        2. 'Cost of sales' (cost_of_revenue, year 2024)
        3. 'Cash from ops' (cfo, year 2023)
      All 3 rows share kind 'money figures' on page 3.
      Check B1 groups by (page, kind) -> exactly 1 failure for (3, 'money figures').
      All 3 citing rows appear in the single failure message, joined by '; '.
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["(in millions)"],
        ["Table header"],
        ["Total revenues 1000", "Cost of sales 400", "Cash from ops 300"],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[
            _historical_year(
                year=2024,
                revenue=[{"label": "Total revenues", "value": 1000.0, "page": 3}],
                cost_of_revenue=[{"label": "Cost of sales", "value": 400.0, "page": 3}],
            ),
            _historical_year(
                year=2023,
                cfo=[{"label": "Cash from ops", "value": 300.0, "page": 3}],
            ),
        ],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert len(failures) == 1
    msg = failures[0].message
    assert "page 3 (money figures): expected millions, no unit statement on page 3 or 2" in msg
    assert "'Total revenues' (revenue, year 2024)" in msg
    assert "'Cost of sales' (cost_of_revenue, year 2024)" in msg
    assert "'Cash from ops' (cfo, year 2023)" in msg


# ===========================================================================
# 3. Mismatched unit statements
# ===========================================================================

def test_mismatched_unit_statement_fails_naming_expected_and_found(tmp_path: Path) -> None:
    """Expected scale 'millions' but found '(in thousands)' -> failure naming both.

    Expected value derivation:
      Filing units: '(in millions)' -> expected scale is 'millions'.
      Page 1 has no statement. Page 2 prints '(in thousands)'.
      Row: 'Total revenues' on page 2.
      pages_to_check is (2, 1). Only page 2 has a scale statement: '(in thousands)'.
      Candidate group '(in thousands)' parses to scale word 'thousands'.
      'thousands' != 'millions'.
      Failure message:
        'page 2 (money figures): expected millions, found (in thousands). Rows citing page 2: 'Total revenues' (revenue, year 2024).'
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["Introduction without unit statement"],
        ["(in thousands)", "Total revenues 1,000,000"],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Total revenues", "value": 1000000.0, "page": 2}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert len(failures) == 1
    expected_msg = (
        "page 2 (money figures): expected millions, found (in thousands). "
        "Rows citing page 2: 'Total revenues' (revenue, year 2024)."
    )
    assert failures[0].message == expected_msg


# ===========================================================================
# 4. Distinct kinds: money figures vs share count
# ===========================================================================

def test_distinct_kinds_verified_independently_on_two_scale_statement(tmp_path: Path) -> None:
    """Money figures (millions) and share count (thousands) verified independently.

    Expected value derivation:
      Statement prints '(dollars in millions, shares in thousands, except per share data)'.
      Filing units:
        units: '(dollars in millions, shares in thousands, except per share data)' -> money = millions
        share_units: '(dollars in millions, shares in thousands, except per share data)' -> shares = thousands
      Rows on page 1:
        'Revenue' (revenue) -> kind = money figures, expected = millions.
        'Diluted shares' (diluted_shares) -> kind = share count, expected = thousands.
      printed_scale for money figures gives 'millions' (matches expected).
      printed_scale for share count gives 'thousands' (matches expected).
      Result: 0 failures.
    """
    stmt = "(dollars in millions, shares in thousands, except per share data)"
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        [stmt, "Revenue 5,000", "Diluted shares 120,000"],
    ])
    data = _pass1_dict(
        units_printed=stmt,
        units_page=1,
        share_units_printed=stmt,
        share_units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Revenue", "value": 5000.0, "page": 1}],
            diluted_shares=[{"label": "Diluted shares", "value": 120000.0, "page": 1}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert failures == []


def test_distinct_kinds_one_passes_and_one_fails(tmp_path: Path) -> None:
    """Money row passes under millions, while share row fails when share_units expects millions.

    Expected value derivation:
      Statement on page 1: '(dollars in millions, shares in thousands, except per share data)'.
      units: expects 'millions'.
      share_units: '(in millions)' -> expects 'millions'.
      On page 1:
        revenue -> kind 'money figures', expected 'millions' -> matches 'millions' -> PASS.
        diluted_shares -> kind 'share count', expected 'millions' -> found scale gives 'thousands' -> FAIL.
      Result: exactly 1 failure for (1, 'share count'):
        'page 1 (share count): expected millions, found (dollars in millions, shares in thousands, except per share data). Rows citing page 1: 'Diluted shares' (diluted_shares, year 2024).'
    """
    stmt = "(dollars in millions, shares in thousands, except per share data)"
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        [stmt, "Revenue 5,000", "Diluted shares 120,000"],
    ])
    data = _pass1_dict(
        units_printed=stmt,
        units_page=1,
        share_units_printed="(in millions)",
        share_units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Revenue", "value": 5000.0, "page": 1}],
            diluted_shares=[{"label": "Diluted shares", "value": 120000.0, "page": 1}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert len(failures) == 1
    assert "page 1 (share count): expected millions, found" in failures[0].message
    assert "'Diluted shares' (diluted_shares, year 2024)" in failures[0].message


# ===========================================================================
# 5. Multi-scale limit and MD&A prose limit
# ===========================================================================

def test_multi_scale_limit_page_with_multiple_statements_passes_either_scale(tmp_path: Path) -> None:
    """Page printing both '(In millions)' and '(In thousands)' passes rows of either scale.

    Check B1 stated limit in words:
      A page that prints statements of two scales passes a row of either scale,
      because candidate_words holds both 'millions' and 'thousands'.
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["(In millions)", "(In thousands)", "Row A 100"],
    ])

    # Case A: expected scale is millions -> candidate_words ['millions', 'thousands'] contains 'millions' -> 0 failures
    data_millions = _pass1_dict(
        units_printed="(In millions)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Row A", "value": 100.0, "page": 1}],
        )],
    )
    assert _row_scale_failures(data_millions, pdf.read_bytes()) == []

    # Case B: expected scale is thousands -> candidate_words ['millions', 'thousands'] contains 'thousands' -> 0 failures
    data_thousands = _pass1_dict(
        units_printed="(In thousands)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Row A", "value": 100.0, "page": 1}],
        )],
    )
    assert _row_scale_failures(data_thousands, pdf.read_bytes()) == []


def test_mda_unparenthesised_prose_cannot_confirm_scale_and_stops(tmp_path: Path) -> None:
    """Figure in MD&A prose ('$1.2 billion') without parentheses has no parenthesised statement -> stops.

    Check B1 stated limit in words:
      A figure printed in MD&A prose ("$1.2 billion") has no parenthesised statement,
      so a row that cites it stops.
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["Overview page without unit statement"],
        ["Management Discussion and Analysis", "Revenues were $1.2 billion for the year."],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Revenues", "value": 1200.0, "page": 2}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert len(failures) == 1
    assert "no unit statement on page 2 or 1" in failures[0].message


# ===========================================================================
# 6. Page beyond PDF page count and page with no text layer
# ===========================================================================

def test_page_beyond_pdf_page_count_stops(tmp_path: Path) -> None:
    """Row citing page 5 in a 2-page PDF stops naming page beyond page count.

    Expected value derivation:
      PDF has 2 pages. Row cites page 5.
      5 > 2 -> page 5 is beyond the last page of the filing (2 pages).
      1 failure naming page 5, money figures, expected millions, and the citing row.
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["(in millions)"],
        ["(in millions)", "Page 2 content"],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Total revenues", "value": 100.0, "page": 5}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert len(failures) == 1
    msg = failures[0].message
    assert "page 5 (money figures): expected millions, page 5 is beyond the last page of the filing (2 pages)" in msg
    assert "'Total revenues' (revenue, year 2024)" in msg


def test_page_with_no_text_layer_stops(tmp_path: Path) -> None:
    """Row citing page 2 where page 2 has no text layer stops.

    Expected value derivation:
      Page 2 has no text lines ([]).
      statement_desc: 'page 2 has no text layer'.
      1 failure naming page 2, money figures, expected millions, and the citing row.
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["(in millions)"],
        [],  # empty text layer
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Total revenues", "value": 100.0, "page": 2}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert len(failures) == 1
    msg = failures[0].message
    assert "page 2 (money figures): expected millions, page 2 has no text layer" in msg
    assert "'Total revenues' (revenue, year 2024)" in msg


# ===========================================================================
# 7. Balance sheet rows and empty data
# ===========================================================================

def test_balance_sheet_rows_checked_for_scale(tmp_path: Path) -> None:
    """Rows in latest_balance_sheet are checked under kind 'money figures'.

    Expected value derivation:
      Cash row in latest_balance_sheet cites page 3.
      Page 1 has '(in millions)'. Pages 2 and 3 have no unit statement.
      Failure emitted for page 3 (money figures) citing the cash row.
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["(in millions)"],
        ["Overview"],
        ["Cash and equivalents 500"],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[],
        latest_balance_sheet=_balance_sheet(
            year=2024,
            cash=[{"label": "Cash and equivalents", "value": 500.0, "page": 3}],
        ),
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert len(failures) == 1
    msg = failures[0].message
    assert "page 3 (money figures): expected millions, no unit statement on page 3 or 2" in msg
    assert "'Cash and equivalents' (cash, year 2024)" in msg


def test_empty_rows_returns_empty_failures_and_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """When historical_years and latest_balance_sheet hold 0 rows, returns [] and prints summary.

    Expected value derivation:
      0 rows checked -> total_rows == 0.
      Returns [] immediately.
      Summary line: '  Row unit scales looked up on their cited pages: 0 checked, 0 pages, 0 pages not confirmed.'
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[],
        latest_balance_sheet={},
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert failures == []
    out = capsys.readouterr().out
    assert "Row unit scales looked up on their cited pages: 0 checked, 0 pages, 0 pages not confirmed." in out


def test_summary_line_counts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Summary line correctly reports checked rows, pages count, and unconfirmed pages count.

    Expected value derivation (hand arithmetic):
      Page 1 has no statement, Page 2 has no statement.
      Row 1: revenue on page 1.
      Row 2: cfo on page 2.
      Row 3: capex on page 2.
      Total rows: 3 checked.
      Cited pages: {1, 2} -> 2 pages.
      Unconfirmed pages: {1, 2} -> 2 pages not confirmed.
      Summary line: '  Row unit scales looked up on their cited pages: 3 checked, 2 pages, 2 pages not confirmed.'
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["No unit statement here"],
        ["Neither here"],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        historical_years=[_historical_year(
            year=2024,
            revenue=[{"label": "Rev", "value": 10.0, "page": 1}],
            cfo=[{"label": "CFO", "value": 20.0, "page": 2}],
            capex=[{"label": "Capex", "value": 5.0, "page": 2}],
        )],
    )
    _row_scale_failures(data, pdf.read_bytes())
    out = capsys.readouterr().out
    assert "Row unit scales looked up on their cited pages: 3 checked, 2 pages, 2 pages not confirmed." in out


# ===========================================================================
# 8. Route A retry exhaustion and stop
# ===========================================================================

def test_route_a_retry_exhaustion_raises_value_error_on_unconfirmed_scale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Route A retries MAX_RETRIES times on scale failure, then raises ValueError listing the failure.

    Expected value derivation:
      MAX_RETRIES is 2. Total attempts made: 1 initial + 2 retries = 3 calls.
      Each call returns well-formed Pass 1 JSON where revenue cites page 3 (no unit statement on page 3 or 2).
      After 2 retries, unit_failures contains the Check B1 failure.
      Route A raises ValueError naming:
        'Pass 1: after 2 retries, 1 row scale failure(s) are still not confirmed, so the scale of the figures is not known and the run stops:'
        and lists 'page 3 (money figures): expected millions, no unit statement on page 3 or 2'.
    """
    # Prevent all network socket calls
    def _block_connect(*args: object, **kwargs: object) -> None:
        raise RuntimeError("network socket connect blocked in test")
    monkeypatch.setattr(socket.socket, "connect", _block_connect)

    pdf = make_pdf(tmp_path)
    pdf_bytes = pdf.read_bytes()

    p1 = copy.deepcopy(pass1_answer())
    # Modify 2024 revenue to cite page 3 where scale is not confirmed
    p1["historical_years"][1]["revenue"][0]["page"] = 3
    p1_json = json.dumps(p1)

    calls: list[str] = []

    def stub(*args: Any, **kwargs: Any) -> tuple[str, int, int]:
        calls.append(str(args))
        return p1_json, 10, 5

    monkeypatch.setattr(ce, "_call_llm", stub)

    resolution = ProviderResolution(
        provider="gemini", model="stub-gemini",
        reasoning_label="stub", transport="gemini-direct",
        transport_label="stub", credential="gemini-api-key",
        credential_source="stub",
    )

    with pytest.raises(ValueError) as excinfo:
        ce._run_financials_pass(
            pdf_bytes, _TICKER, _COMPANY, resolution, target_years=None, include_bs=True,
        )

    # 1 initial call + 2 retries = 3 calls
    assert len(calls) == 3
    err_msg = str(excinfo.value)
    assert "Pass 1: after 2 retries, 1 row scale failure(s) are still not confirmed" in err_msg
    assert "page 3 (money figures): expected millions" in err_msg
    assert "'revenue' (revenue, year 2024)" in err_msg


# ===========================================================================
# 9. Route B session check and loader stop
# ===========================================================================

def test_route_b_cmd_check_exits_2_on_scale_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Route B cmd_check exits 2 on Check B1 scale failures, and load_session_extraction raises.

    Expected value derivation:
      Session file points to synthetic PDF.
      Revenue row cites page 3, with no unit statement on page 3 or 2.
      unit_statement_page_failures returns the failure.
      load_session_extraction stops with ValueError ("the session file cannot be used").
      cmd_check catches ValueError, prints STOPPED, and returns exit code 2.
    """
    pdf = write_text_pdf(tmp_path / "TST_10-K_2024.pdf", [
        ["(in millions)"],
        ["Page 2 notes"],
        ["Total revenues 2,000"],
    ])
    p1 = copy.deepcopy(pass1_answer())
    p1["historical_years"][1]["revenue"][0]["page"] = 3
    sdata = _session_dict(pdf, p1)
    session_file = tmp_path / "session.json"
    session_file.write_text(json.dumps(sdata), encoding="utf-8")

    # 1. load_session_extraction raises ValueError
    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(session_file)
    assert "the session file cannot be used" in str(excinfo.value)
    assert "page 3 (money figures): expected millions, no unit statement on page 3 or 2" in str(excinfo.value)

    # 2. cmd_check exits 2
    exit_code = cmd_check(session_file)
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "STOPPED — " in out
    assert "page 3 (money figures): expected millions, no unit statement on page 3 or 2" in out


def test_unit_statement_page_failures_combines_unit_and_row_scale_failures(tmp_path: Path) -> None:
    """unit_statement_page_failures returns combined failures from Check A and Check B1.

    Expected value derivation:
      Check A: units citations allowed on governed pages; if units cites page 99 (beyond PDF), Check A fails.
      Check B1: row on page 3 with no unit statement on page 3 or 2 fails.
      unit_statement_page_failures returns failures from both checks.
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["(in millions)"],
        ["Page 2"],
        ["Total revenues 2,000"],
    ])
    p1 = copy.deepcopy(pass1_answer())
    p1["units"]["page"] = 99
    p1["historical_years"][1]["revenue"][0]["page"] = 3

    failures = unit_statement_page_failures(json.dumps(p1), pdf.read_bytes())
    assert len(failures) >= 2
    assert any("page 3 (money figures)" in f for f in failures)
    assert any("units" in f and "page 99" in f for f in failures)


# ===========================================================================
# 10. Rule 3 stops: missing keys and invalid inputs
# ===========================================================================

def test_rule_3_missing_units_key_stops_and_names_field(tmp_path: Path) -> None:
    """Missing 'units' key in data causes _filing_units to raise KeyError('units')."""
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    data = _pass1_dict()
    del data["units"]
    with pytest.raises(KeyError) as excinfo:
        _row_scale_failures(data, pdf.read_bytes())
    assert "units" in str(excinfo.value)


def test_rule_3_missing_share_units_key_stops_and_names_field(tmp_path: Path) -> None:
    """Missing 'share_units' key in data causes _filing_units to raise KeyError('share_units')."""
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    data = _pass1_dict()
    del data["share_units"]
    with pytest.raises(KeyError) as excinfo:
        _row_scale_failures(data, pdf.read_bytes())
    assert "share_units" in str(excinfo.value)


def test_rule_3_missing_year_key_stops_and_names_field(tmp_path: Path) -> None:
    """Missing 'year' key in historical_years entry raises KeyError('year')."""
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    entry = _historical_year(2024, revenue=[{"label": "Rev", "value": 100.0, "page": 1}])
    del entry["year"]
    data = _pass1_dict(historical_years=[entry])
    with pytest.raises(KeyError) as excinfo:
        _row_scale_failures(data, pdf.read_bytes())
    assert "year" in str(excinfo.value)


def test_rule_3_missing_historical_years_key_stops_and_names_field(tmp_path: Path) -> None:
    """Missing 'historical_years' key in data causes _row_scale_failures to raise KeyError('historical_years')."""
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    data = _pass1_dict()
    del data["historical_years"]
    with pytest.raises(KeyError) as excinfo:
        _row_scale_failures(data, pdf.read_bytes())
    assert "historical_years" in str(excinfo.value)


def test_rule_3_missing_line_field_in_historical_year_stops_and_names_field(tmp_path: Path) -> None:
    """Missing standard line field (e.g. 'revenue') in historical_years entry raises KeyError('revenue')."""
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    year_entry = _historical_year(2024)
    del year_entry["revenue"]
    data = _pass1_dict(historical_years=[year_entry])
    with pytest.raises(KeyError) as excinfo:
        _row_scale_failures(data, pdf.read_bytes())
    assert "revenue" in str(excinfo.value)


def test_rule_3_missing_latest_balance_sheet_key_stops_and_names_field(tmp_path: Path) -> None:
    """Missing 'latest_balance_sheet' key in data causes _row_scale_failures to raise KeyError('latest_balance_sheet')."""
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    data = _pass1_dict()
    del data["latest_balance_sheet"]
    with pytest.raises(KeyError) as excinfo:
        _row_scale_failures(data, pdf.read_bytes())
    assert "latest_balance_sheet" in str(excinfo.value)


def test_rule_3_missing_line_field_in_balance_sheet_stops_and_names_field(tmp_path: Path) -> None:
    """Missing standard line field (e.g. 'cash') in non-empty latest_balance_sheet raises KeyError('cash')."""
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    bs_entry = _balance_sheet(2024)
    del bs_entry["cash"]
    data = _pass1_dict(historical_years=[], latest_balance_sheet=bs_entry)
    with pytest.raises(KeyError) as excinfo:
        _row_scale_failures(data, pdf.read_bytes())
    assert "cash" in str(excinfo.value)


def test_rule_3_missing_year_in_balance_sheet_stops_and_names_field(tmp_path: Path) -> None:
    """Missing 'year' in non-empty latest_balance_sheet raises KeyError('year')."""
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    bs_entry = _balance_sheet(2024)
    del bs_entry["year"]
    data = _pass1_dict(historical_years=[], latest_balance_sheet=bs_entry)
    with pytest.raises(KeyError) as excinfo:
        _row_scale_failures(data, pdf.read_bytes())
    assert "year" in str(excinfo.value)


def test_rule_3_missing_line_label_key_stops_and_names_field(tmp_path: Path) -> None:
    """Missing 'label' in row dict raises KeyError('label')."""
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    data = _pass1_dict(historical_years=[_historical_year(
        year=2024,
        revenue=[{"value": 100.0, "page": 1}],
    )])
    with pytest.raises(KeyError) as excinfo:
        _row_scale_failures(data, pdf.read_bytes())
    assert "label" in str(excinfo.value)


def test_rule_3_missing_line_page_key_stops_and_names_field(tmp_path: Path) -> None:
    """Missing 'page' in row dict raises KeyError('page')."""
    pdf = write_text_pdf(tmp_path / "f.pdf", [["(in millions)"]])
    data = _pass1_dict(historical_years=[_historical_year(
        year=2024,
        revenue=[{"label": "Rev", "value": 100.0}],
    )])
    with pytest.raises(KeyError) as excinfo:
        _row_scale_failures(data, pdf.read_bytes())
    assert "page" in str(excinfo.value)


def test_rule_3_invalid_pdf_bytes_raises_value_error() -> None:
    """Invalid PDF bytes passed to _row_scale_failures raises ValueError."""
    data = _pass1_dict()
    with pytest.raises(ValueError) as excinfo:
        _row_scale_failures(data, b"not a valid pdf file")
    assert "PDF" in str(excinfo.value) or "open" in str(excinfo.value)


# ===========================================================================
# 11. Real 10-K Filings verification
# ===========================================================================

@pytest.mark.skipif(not _REAL_WALMART_PDF.exists(), reason="Walmart 10-K PDF not found")
def test_real_walmart_filing_scale_confirmation() -> None:
    """Real Walmart 10-K: page 21 prints '(Amounts in millions, except per share data)' -> 0 failures.
    Row citing page 2 (TOC/intro without scale) -> 1 failure naming page 2.

    Citations:
      Walmart 10-K page 21 prints: '(Amounts in millions, except per share data)'.
      Page 1 and 2 print no unit statement.
    """
    pdf_bytes = _REAL_WALMART_PDF.read_bytes()

    # Pass 1 with row on page 21 -> confirmed
    data_clean = _pass1_dict(
        units_printed="(Amounts in millions, except per share data)",
        units_page=21,
        share_units_printed="(Amounts in millions, except per share data)",
        share_units_page=21,
        historical_years=[_historical_year(
            year=2026,
            revenue=[{"label": "Total revenues", "value": 680984.0, "page": 21}],
        )],
    )
    assert _row_scale_failures(data_clean, pdf_bytes) == []

    # Row moved to page 2 -> stops
    data_bad = _pass1_dict(
        units_printed="(Amounts in millions, except per share data)",
        units_page=21,
        share_units_printed="(Amounts in millions, except per share data)",
        share_units_page=21,
        historical_years=[_historical_year(
            year=2026,
            revenue=[{"label": "Total revenues", "value": 680984.0, "page": 2}],
        )],
    )
    failures = _row_scale_failures(data_bad, pdf_bytes)
    assert len(failures) == 1
    assert "page 2 (money figures): expected millions, no unit statement on page 2 or 1" in failures[0].message


@pytest.mark.skipif(not _REAL_CHIPOTLE_PDF.exists(), reason="Chipotle 10-K PDF not found")
def test_real_chipotle_filing_scale_mismatch() -> None:
    """Real Chipotle 2025 10-K: page 29 prints '(in thousands, except per share data)'.
    Pass 1 with expected 'millions' and revenue on page 29 fails naming found statement.

    Citation:
      Chipotle 10-K page 29 prints: '(in thousands, except per share data)'.
    """
    pdf_bytes = _REAL_CHIPOTLE_PDF.read_bytes()
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=29,
        historical_years=[_historical_year(
            year=2025,
            revenue=[{"label": "Revenue", "value": 11250.0, "page": 29}],
        )],
    )
    failures = _row_scale_failures(data, pdf_bytes)
    assert len(failures) == 1
    msg = failures[0].message
    assert "page 29 (money figures): expected millions, found (in thousands, except per share data)" in msg
    assert "'Revenue' (revenue, year 2025)" in msg


@pytest.mark.skipif(not _REAL_OKTA_PDF.exists(), reason="Okta 10-K PDF not found")
def test_real_okta_filing_two_scales() -> None:
    """Real Okta 2026 10-K: page 58 prints '(dollars in millions, shares in thousands, except per share data)'.
    Independent verification of money figures (millions) and share count (thousands).

    Citation:
      Okta 10-K page 58 prints: '(dollars in millions, shares in thousands, except per share data)'.
    """
    pdf_bytes = _REAL_OKTA_PDF.read_bytes()
    stmt = "(dollars in millions, shares in thousands, except per share data)"

    # Clean case: units millions, share_units thousands
    data_clean = _pass1_dict(
        units_printed=stmt,
        units_page=58,
        share_units_printed=stmt,
        share_units_page=58,
        historical_years=[_historical_year(
            year=2026,
            revenue=[{"label": "Total revenue", "value": 2611.0, "page": 58}],
            diluted_shares=[{"label": "Diluted shares", "value": 172000.0, "page": 58}],
        )],
    )
    assert _row_scale_failures(data_clean, pdf_bytes) == []

    # Share units wrongly set to millions -> share count row fails
    data_wrong_shares = _pass1_dict(
        units_printed=stmt,
        units_page=58,
        share_units_printed="(in millions)",
        share_units_page=58,
        historical_years=[_historical_year(
            year=2026,
            revenue=[{"label": "Total revenue", "value": 2611.0, "page": 58}],
            diluted_shares=[{"label": "Diluted shares", "value": 172000.0, "page": 58}],
        )],
    )
    failures = _row_scale_failures(data_wrong_shares, pdf_bytes)
    assert len(failures) == 1
    msg = failures[0].message
    assert "page 58 (share count): expected millions, found (dollars in millions, shares in thousands, except per share data)" in msg
    assert "'Diluted shares' (diluted_shares, year 2026)" in msg


@pytest.mark.skipif(not _REAL_LHX_PDF.exists(), reason="L3Harris 10-K PDF not found")
def test_real_lhx_filing_multi_scale_limit() -> None:
    """Real L3Harris 2026 10-K: page 62 prints both '(In millions)' and '(In thousands)'.
    Confirmed under both expected millions and expected thousands.

    Citation:
      L3Harris 10-K page 62 prints both '(In millions)' and '(In thousands)'.
    """
    pdf_bytes = _REAL_LHX_PDF.read_bytes()

    # Case A: expected scale millions -> passes
    data_millions = _pass1_dict(
        units_printed="(In millions)",
        units_page=62,
        historical_years=[_historical_year(
            year=2025,
            revenue=[{"label": "Revenue line", "value": 21000.0, "page": 62}],
        )],
    )
    assert _row_scale_failures(data_millions, pdf_bytes) == []

    # Case B: expected scale thousands -> passes
    data_thousands = _pass1_dict(
        units_printed="(In thousands)",
        units_page=62,
        historical_years=[_historical_year(
            year=2025,
            revenue=[{"label": "Revenue line", "value": 21000000.0, "page": 62}],
        )],
    )
    assert _row_scale_failures(data_thousands, pdf_bytes) == []


def test_candidate_raising_value_error_is_discarded_for_kind(tmp_path: Path) -> None:
    """When a parenthesised scale group states no scale for a kind, printed_scale raises ValueError
    and the candidate is discarded (coverage lines 1662-1663).

    Expected value derivation:
      Page 1 has '(dollars in millions)'.
      Group holds 'millions', so it is in scale_groups.
      For kind 'share count':
        printed_scale('(dollars in millions)', 'share count') raises ValueError:
        'states no scale for share count'.
      The candidate is caught and discarded.
      Since no other candidate group exists, candidate_words is empty.
      1 failure is emitted for page 1 (share count).
    """
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["(dollars in millions)", "Diluted shares 50"],
    ])
    data = _pass1_dict(
        units_printed="(in millions)",
        units_page=1,
        share_units_printed="(in millions)",
        share_units_page=1,
        historical_years=[_historical_year(
            year=2024,
            diluted_shares=[{"label": "Diluted shares", "value": 50.0, "page": 1}],
        )],
    )
    failures = _row_scale_failures(data, pdf.read_bytes())
    assert len(failures) == 1
    assert "page 1 (share count): expected millions, found (dollars in millions)" in failures[0].message
