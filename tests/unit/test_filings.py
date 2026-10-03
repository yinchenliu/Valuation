"""Filing resolution and hashing, `ingestion/filings.py` (moved from `cli.py` by P9a).

Both routes resolve and hash their PDFs here, and the session route's tie between a
figure and its filing (rule 5) is `fingerprint_filings`' sha256. So this file locks
the hash against `hashlib` computed independently, and the stops.

**The fiscal year is tested in `test_fiscal_year.py`, not here.** Backlog item 43
closed with `P10c-fiscal-year`: the year still comes from the filename, and every year
so given is now verified against the filing's cover date and income statement column
label. A test here that gives a year with bytes that are not a filing stubs the
evidence reader (`tests/unit/_fiscal_year_stub.py`); the verification still runs.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ingestion.filings import discover_filings, fingerprint_filings, parse_pdf_args
from tests.unit._fiscal_year_stub import stub_evidence_reader


def test_fingerprint_is_the_sha256_and_size_of_the_bytes(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    content = b"%PDF-1.4 ten bytes"
    pdf.write_bytes(content)
    (print_,) = fingerprint_filings([(2024, str(pdf))])
    # Expected: hashlib over the same bytes, and len() of them (18).
    assert print_.sha256 == hashlib.sha256(content).hexdigest()
    assert print_.size_bytes == len(content) == 18
    assert print_.year == 2024
    assert print_.path == str(pdf.resolve())


def test_fingerprint_order_is_by_year(tmp_path: Path) -> None:
    for name in ("x.pdf", "y.pdf"):
        (tmp_path / name).write_bytes(name.encode())
    prints = fingerprint_filings([(2025, str(tmp_path / "x.pdf")),
                                  (2023, str(tmp_path / "y.pdf"))])
    # Docstring: "in a stable order"; the sort key is (year, path). 2023 first.
    assert [p.year for p in prints] == [2023, 2025]


def test_fingerprint_stops_on_a_missing_file_naming_it(tmp_path: Path) -> None:
    missing = str(tmp_path / "gone.pdf")
    with pytest.raises(FileNotFoundError, match="gone.pdf"):
        fingerprint_filings([(2024, missing)])


def test_parse_pdf_args_reads_year_colon_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # 'YEAR:path' (docstring): the year is the four digits before the colon.
    # Since P10c every given year is verified against the filing; these paths are
    # not filings, so the evidence READER is stubbed to say what a real 10-K for
    # each year would print (tests/unit/_fiscal_year_stub.py). The comparison runs.
    asked = stub_evidence_reader(monkeypatch, {"a.pdf": 2024, "b.pdf": 2023})
    assert parse_pdf_args(["2024:/x/a.pdf", "2023:/x/b.pdf"]) == [
        (2024, "/x/a.pdf"), (2023, "/x/b.pdf")]
    assert asked == ["a.pdf", "b.pdf"]  # each given year was checked


def test_parse_pdf_args_refuses_a_folder_among_other_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="only PDF input"):
        parse_pdf_args([str(tmp_path), "2024:/x/a.pdf"])


def test_discover_stops_on_a_folder_with_no_pdf(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not a filing")
    with pytest.raises(ValueError, match="No 10-K PDFs found") as excinfo:
        discover_filings(tmp_path, "TST")
    assert str(tmp_path) in str(excinfo.value)
