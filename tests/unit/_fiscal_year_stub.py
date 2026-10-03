"""A stand-in for `ingestion.filings.read_fiscal_year_evidence`, for tests that
give a fiscal year with bytes that are not a real 10-K.

Since `P10c-fiscal-year` (backlog item 43) every filing that carries a year is
verified against its cover date and its income statement's column label before
anything is extracted, and a file whose evidence cannot be read **stops**. That
stop is correct and is not weakened here. A test whose subject is something else
(the `YEAR:PATH` parser, the upload redirect, the plan's routing table) replaces
the *reader* instead, with one that returns the evidence a real filing for that
year would print. The *decision* (`fiscal_year_from_evidence`) and the
*comparison* (`verify_filing_years`) still run unchanged.

The evidence returned for year Y is a calendar filer's: cover "December 31, Y",
newest column labelled "Y". By the rule in `fiscal_year_from_evidence`'s
docstring, a bare-year label equal to the cover date's year wins, so the content
year is Y — known before the code runs.

No PDF is opened and `10K_filings/` is never read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion import filings
from ingestion.filings import FiscalYearEvidence


def calendar_year_evidence(pdf_path: str, year: int) -> FiscalYearEvidence:
    """What a December 31 filer's 10-K for `year` prints, on made-up pages."""
    return FiscalYearEvidence(
        path=pdf_path,
        cover_date=f"December 31, {year}",
        cover_page=1,
        column_label=str(year),
        column_page=40,
    )


def stub_evidence_reader(
    monkeypatch: pytest.MonkeyPatch, years_by_name: dict[str, int]
) -> list[str]:
    """Replace the reader. `years_by_name` maps a file NAME to the year its
    content gives. Returns the list of names the reader was asked about, so a
    test can show that verification ran rather than being bypassed. A name not
    in the map raises KeyError: the test asked about a file it did not expect.
    """
    asked: list[str] = []

    def fake_reader(pdf_path: str) -> FiscalYearEvidence:
        name = Path(pdf_path).name
        asked.append(name)
        return calendar_year_evidence(pdf_path, years_by_name[name])

    monkeypatch.setattr(filings, "read_fiscal_year_evidence", fake_reader)
    return asked
