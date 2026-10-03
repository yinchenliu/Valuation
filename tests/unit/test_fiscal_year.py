"""The fiscal year a filing's content gives, and the check against the filename's.

`ingestion/filings.py`, added by `P10c-fiscal-year` (backlog item 43, the user's
decision of 2026-10-02) and amended in its round 2. Three layers, tested apart:

1. `fiscal_year_from_evidence(cover_date, column_label)`: the pure decision, on
   strings. Every expected year below is the rule in
   `.agent/assignments/P10c-fiscal-year.md` ("Round 2", which replaced step 1's
   rule) applied by hand to the strings in the test:

   * a bare-year label wins when it is the cover date's year or the year before;
   * a bare-year label outside that range stops;
   * with date labels only, the year of the cover date, except that a year
     ending in January 1-7 belongs to the year before; the label must be the
     cover date.

   The rows of the assignment's table are the 16 filings the orchestrator
   scanned; their cover dates and labels are copied from that table, not read
   from any PDF.
2. `verify_filing_years`: the comparison and its message, driven by a stubbed
   evidence reader, so each case states exactly what the "filing" printed.
3. `read_fiscal_year_evidence`: the reader, driven by PDFs this file writes
   itself (`tests/unit/_text_pdf.py`), so the expected cover date, label and
   pages are the text and the page the test put there.

**`10K_filings/` is never read.** No network, no key.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ingestion import filings
from ingestion.filings import (
    FiscalYearEvidence,
    discover_filings,
    fiscal_year_from_evidence,
    fiscal_year_from_filename,
    parse_pdf_args,
    read_fiscal_year_evidence,
    verify_filing_years,
)
from tests.unit._text_pdf import write_10k_pdf, write_text_pdf

# ===========================================================================
# 1. fiscal_year_from_evidence, on strings
# ===========================================================================


@pytest.mark.parametrize(
    ("cover_date", "column_label", "expected"),
    [
        # AbbVie, Chipotle: December 31 of the filename year; bare-year label, the
        # same year. Label == cover year -> the label wins.
        ("December 31, 2023", "2023", 2023),
        ("December 31, 2024", "2024", 2024),
        ("December 31, 2025", "2025", 2025),
        # Okta, Walmart: January 31 of the filename year; label the same year.
        ("January 31, 2023", "2023", 2023),
        ("January 31, 2026", "2026", 2026),
        # L3Harris 2023-12-29: date labels; December -> the cover date's year.
        ("December 29, 2023", "December 29, 2023", 2023),
        # L3Harris 2025-01-03: date labels; January 3 is within January 1-7 ->
        # the year before: 2025 - 1 = 2024.
        ("January 3, 2025", "January 3, 2025", 2024),
        # L3Harris 2026-01-02: bare label 2025 = cover year 2026 - 1 -> in range,
        # the label wins: 2025.
        ("January 2, 2026", "2025", 2025),
        # Target-style (round 2): the year ended February 1, 2025 is called 2024.
        # 2024 = cover year - 1 -> in range, the label wins.
        ("February 1, 2025", "2024", 2024),
        # Round 2 behaviour change: a bare label equal to the cover year wins even
        # in early January (round 1 stopped here).
        ("January 2, 2026", "2026", 2026),
    ],
    ids=[
        "calendar-2023", "calendar-2024", "calendar-2025",
        "jan31-2023", "jan31-2026",
        "lhx-2023-12-29-dates", "lhx-2025-01-03-dates", "lhx-2026-01-02-bare",
        "target-style", "bare-label-equal-to-early-january-cover-year",
    ],
)
def test_the_content_year_for_each_row_of_the_rule(
    cover_date: str, column_label: str, expected: int
) -> None:
    assert fiscal_year_from_evidence(cover_date, column_label) == expected


@pytest.mark.parametrize(
    ("cover_date", "column_label"),
    [
        ("December 31, 2025", "2023"),  # two years before the cover year
        ("December 31, 2025", "2026"),  # the year AFTER the cover year
        ("February 1, 2025", "2026"),   # after, for a Target-style cover
        ("January 3, 2025", "2022"),    # far before, early-January cover
    ],
)
def test_a_bare_label_outside_the_cover_year_and_the_year_before_stops(
    cover_date: str, column_label: str
) -> None:
    """Round 2 rule: only {cover year, cover year - 1} is accepted. The message
    names the label and the cover date, so a reader can see both."""
    with pytest.raises(ValueError) as excinfo:
        fiscal_year_from_evidence(cover_date, column_label)
    message = str(excinfo.value)
    assert column_label in message
    assert cover_date in message


@pytest.mark.parametrize("day", [1, 2, 3, 4, 5, 6, 7])
def test_a_date_only_year_ending_in_the_first_seven_days_of_january_is_the_year_before(
    day: int,
) -> None:
    """52/53-week convention: a year ending January 1-7, 2026 is fiscal 2025."""
    printed = f"January {day}, 2026"
    assert fiscal_year_from_evidence(printed, printed) == 2025


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("January 8, 2026", 2026),     # day 8: past the seven-day window
        ("December 31, 2025", 2025),   # the calendar year end
        ("December 28, 2024", 2024),   # a 52/53-week end in late December
        ("February 3, 2024", 2024),    # a date-labelled retailer: cover year
    ],
)
def test_a_date_only_year_outside_the_january_window_is_the_cover_year(
    printed: str, expected: int
) -> None:
    assert fiscal_year_from_evidence(printed, printed) == expected


def test_a_date_label_that_is_not_the_cover_date_stops_naming_both() -> None:
    """The newest column dated differently from the cover: the filing (or the
    reader) contradicts itself, and no year is chosen."""
    with pytest.raises(ValueError) as excinfo:
        fiscal_year_from_evidence("January 3, 2025", "December 29, 2023")
    message = str(excinfo.value)
    assert "January 3, 2025" in message
    assert "December 29, 2023" in message


@pytest.mark.parametrize(
    ("cover_date", "column_label", "named"),
    [
        ("not a date", "2024", "not a date"),
        ("Jan 3, 2025", "2024", "Jan 3, 2025"),          # abbreviated month
        ("Smarch 3, 2025", "2024", "Smarch 3, 2025"),    # no such month
        ("February 30, 2025", "2024", "February 30, 2025"),  # no such day
        ("", "2024", "''"),
        ("December 31, 2024", "FY2024", "FY2024"),       # neither year nor date
        ("December 31, 2024", "Dec 31, 2024", "Dec 31, 2024"),
    ],
)
def test_a_malformed_string_stops_naming_it(
    cover_date: str, column_label: str, named: str
) -> None:
    with pytest.raises(ValueError) as excinfo:
        fiscal_year_from_evidence(cover_date, column_label)
    assert named in str(excinfo.value)


# ===========================================================================
# 2. verify_filing_years, with a stubbed reader
# ===========================================================================


def _stub(
    monkeypatch: pytest.MonkeyPatch,
    by_name: dict[str, FiscalYearEvidence | Exception],
) -> list[str]:
    """Replace the reader with a table: file name -> evidence, or an exception to
    raise (what the real reader raises when evidence cannot be read)."""
    asked: list[str] = []

    def fake(pdf_path: str) -> FiscalYearEvidence:
        name = Path(pdf_path).name
        asked.append(name)
        answer = by_name[name]
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(filings, "read_fiscal_year_evidence", fake)
    return asked


def _evidence(cover: str, cover_page: int, label: str, label_page: int) -> FiscalYearEvidence:
    return FiscalYearEvidence(
        path="unused", cover_date=cover, cover_page=cover_page,
        column_label=label, column_page=label_page,
    )


# LHX-style: the year ended January 3, 2025, labelled by date -> content 2024.
LHX_2025 = _evidence("January 3, 2025", 1, "January 3, 2025", 41)
# LHX-style: the year ended January 2, 2026, labelled "2025" -> content 2025.
LHX_2026 = _evidence("January 2, 2026", 1, "2025", 35)
# A calendar filer whose content gives 2024.
CAL_2024 = _evidence("December 31, 2024", 1, "2024", 50)

LHX_2025_PATH = "/filings/LHX/LHX_10-K_2025-01-03.pdf"
LHX_2026_PATH = "/filings/LHX/LHX_10-K_2026-01-02.pdf"
CAL_2024_PATH = "/filings/CAL/CAL_10-K_2024.pdf"


def test_verify_passes_when_the_content_gives_the_year(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _stub(monkeypatch, {"CAL_10-K_2024.pdf": CAL_2024})
    assert verify_filing_years([(2024, CAL_2024_PATH)], "year_path") is None
    assert asked == ["CAL_10-K_2024.pdf"]


def test_verify_stops_on_a_mismatch_naming_the_file_both_years_and_the_cli_remedy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given 2025; the content gives 2024 (January 3 -> the year before)."""
    _stub(monkeypatch, {"LHX_10-K_2025-01-03.pdf": LHX_2025})
    with pytest.raises(ValueError) as excinfo:
        verify_filing_years([(2025, LHX_2025_PATH)], "year_path")
    message = str(excinfo.value)
    assert "does not match the filing" in message
    assert "could not be confirmed" not in message
    assert "LHX_10-K_2025-01-03.pdf" in message
    assert "given fiscal year 2025" in message
    assert "content gives 2024" in message
    # The evidence, with its pages.
    assert "January 3, 2025" in message
    assert re.search(r"\bpage 41\b", message)
    # The CLI remedy names YEAR:PATH with the content year.
    assert f"2024:{LHX_2025_PATH}" in message


def test_verify_lists_every_bad_filing_in_one_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two wrong years and one right one: one ValueError naming both wrong files
    (2025 -> 2024, 2026 -> 2025) and not the right one."""
    _stub(monkeypatch, {
        "LHX_10-K_2025-01-03.pdf": LHX_2025,
        "LHX_10-K_2026-01-02.pdf": LHX_2026,
        "CAL_10-K_2024.pdf": CAL_2024,
    })
    with pytest.raises(ValueError) as excinfo:
        verify_filing_years(
            [(2024, CAL_2024_PATH), (2025, LHX_2025_PATH), (2026, LHX_2026_PATH)],
            "year_path",
        )
    message = str(excinfo.value)
    assert "LHX_10-K_2025-01-03.pdf" in message
    assert "LHX_10-K_2026-01-02.pdf" in message
    assert f"2024:{LHX_2025_PATH}" in message
    assert f"2025:{LHX_2026_PATH}" in message
    assert "CAL_10-K_2024.pdf" not in message
    assert message.count("does not match the filing") == 1  # one heading, two items


def test_verify_web_remedy_says_rename_and_upload_and_names_no_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub(monkeypatch, {"LHX_10-K_2026-01-02.pdf": LHX_2026})
    with pytest.raises(ValueError) as excinfo:
        verify_filing_years([(2026, LHX_2026_PATH)], "rename_and_upload")
    message = str(excinfo.value)
    assert "Rename the file" in message
    assert "upload it again" in message
    assert "is 2025" in message  # the year to rename to: the content year
    assert f"2025:{LHX_2026_PATH}" not in message  # YEAR:PATH is the CLI's remedy
    assert "Pass " not in message


def test_an_unreadable_cover_stops_under_its_own_heading_not_does_not_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round 2 F4: when the evidence cannot be read, nothing was compared, and the
    heading must say so."""
    _stub(monkeypatch, {
        "Q_10-K_2025.pdf": ValueError("'Q_10-K_2025.pdf': no 10-K cover line (stub)"),
    })
    with pytest.raises(ValueError) as excinfo:
        verify_filing_years([(2025, "/f/Q_10-K_2025.pdf")], "year_path")
    message = str(excinfo.value)
    assert "could not be confirmed against the filing" in message
    assert "does not match" not in message
    assert "Q_10-K_2025.pdf" in message
    assert "given fiscal year 2025" in message
    assert "no 10-K cover line (stub)" in message  # the reader's reason is carried


def test_a_mismatch_and_an_unreadable_filing_go_under_their_own_headings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub(monkeypatch, {
        "LHX_10-K_2025-01-03.pdf": LHX_2025,
        "Q_10-K_2025.pdf": ValueError("unreadable (stub)"),
    })
    with pytest.raises(ValueError) as excinfo:
        verify_filing_years([(2025, LHX_2025_PATH), (2025, "/f/Q_10-K_2025.pdf")],
                            "year_path")
    message = str(excinfo.value)
    mismatch_at = message.index("does not match the filing")
    unconfirmed_at = message.index("could not be confirmed against the filing")
    lhx_at = message.index("LHX_10-K_2025-01-03.pdf")
    q_at = message.index("Q_10-K_2025.pdf")
    assert mismatch_at < lhx_at < unconfirmed_at < q_at


def test_an_out_of_range_label_through_verify_names_label_cover_and_both_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover December 31, 2025 on page 3; label 2023 on page 57. 2023 is outside
    {2025, 2024}, so no content year exists: it stops, naming all four facts."""
    _stub(monkeypatch, {"X_10-K_2025.pdf": _evidence("December 31, 2025", 3, "2023", 57)})
    with pytest.raises(ValueError) as excinfo:
        verify_filing_years([(2025, "/f/X_10-K_2025.pdf")], "year_path")
    message = str(excinfo.value)
    assert "December 31, 2025" in message
    assert "'2023'" in message
    assert re.search(r"\bpage 3\b", message)
    assert re.search(r"\bpage 57\b", message)
    assert "could not be confirmed against the filing" in message


def test_year_zero_is_not_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare path (year 0) asks for every year in the filing, so there is no one
    year to compare (P10c step 2). The reader must not be consulted."""
    asked = _stub(monkeypatch, {})
    assert verify_filing_years([(0, "/f/anything.pdf")], "year_path") is None
    assert asked == []


def test_parse_pdf_args_verifies_an_explicit_year_colon_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub(monkeypatch, {"LHX_10-K_2025-01-03.pdf": LHX_2025})
    with pytest.raises(ValueError, match="content gives 2024"):
        parse_pdf_args([f"2025:{LHX_2025_PATH}"])
    # The remedy works: the content year, passed explicitly, is accepted.
    assert parse_pdf_args([f"2024:{LHX_2025_PATH}"]) == [(2024, LHX_2025_PATH)]


# ===========================================================================
# 3. read_fiscal_year_evidence, on PDFs this file writes
# ===========================================================================


def test_the_reader_finds_the_cover_date_and_the_newest_bare_year_label(tmp_path: Path) -> None:
    """Cover on page 1; one filler page; the statement on page 3. The heading
    lists 2022 2023 2024 oldest first, so 'newest' is tested, not 'first'."""
    pdf = write_10k_pdf(tmp_path / "CAL_10-K_2024.pdf", "December 31, 2024",
                        "(In millions) 2022 2023 2024")
    evidence = read_fiscal_year_evidence(str(pdf))
    assert evidence.cover_date == "December 31, 2024"
    assert evidence.cover_page == 1
    assert evidence.column_label == "2024"
    assert evidence.column_page == 3


def test_the_reader_finds_the_newest_date_label(tmp_path: Path) -> None:
    pdf = write_10k_pdf(
        tmp_path / "LHX_10-K_2025-01-03.pdf", "January 3, 2025",
        "(In millions) December 30, 2022 January 3, 2025 December 29, 2023",
        filler_pages=2,
    )
    evidence = read_fiscal_year_evidence(str(pdf))
    assert evidence.cover_date == "January 3, 2025"
    assert evidence.column_label == "January 3, 2025"
    assert evidence.column_page == 4  # cover 1, filler 2-3, statement 4


def test_the_reader_stops_on_a_10q_cover(tmp_path: Path) -> None:
    """A 10-Q has no 'ANNUAL REPORT ... For the fiscal year ended' cover line."""
    pdf = write_text_pdf(tmp_path / "Q_10-Q_2025.pdf", [
        ["FORM 10-Q", "QUARTERLY REPORT PURSUANT TO SECTION 13 OR 15(d)",
         "For the quarterly period ended March 31, 2025"],
        ["CONSOLIDATED STATEMENTS OF OPERATIONS", "(In millions) 2025 2024"],
    ])
    with pytest.raises(ValueError) as excinfo:
        read_fiscal_year_evidence(str(pdf))
    assert "no 10-K cover line" in str(excinfo.value)
    assert "Q_10-Q_2025.pdf" in str(excinfo.value)


def test_the_reader_does_not_take_a_prose_mention_for_the_cover(tmp_path: Path) -> None:
    """P10c round 1 decision: the cover marker is required, because the same words
    recur in prose about an earlier year."""
    pdf = write_text_pdf(tmp_path / "P_10-K_2024.pdf", [
        ["as described in our Annual Report on Form 10-K",
         "for the fiscal year ended December 31, 2023"],
        ["CONSOLIDATED STATEMENTS OF OPERATIONS", "(In millions) 2024 2023 2022"],
    ])
    with pytest.raises(ValueError, match="no 10-K cover line"):
        read_fiscal_year_evidence(str(pdf))


def test_the_reader_stops_when_no_income_statement_headings_are_found(tmp_path: Path) -> None:
    pdf = write_text_pdf(tmp_path / "N_10-K_2024.pdf", [
        ["FORM 10-K", "ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d)",
         "For the fiscal year ended December 31, 2024"],
        ["No statements in this stand-in."],
    ])
    with pytest.raises(ValueError) as excinfo:
        read_fiscal_year_evidence(str(pdf))
    assert "no column headings" in str(excinfo.value)
    assert "N_10-K_2024.pdf" in str(excinfo.value)


def test_the_reader_stops_on_bytes_that_are_not_a_pdf(tmp_path: Path) -> None:
    fake = tmp_path / "F_10-K_2024.pdf"
    fake.write_bytes(b"%PDF-1.4 not a real filing")
    with pytest.raises(ValueError) as excinfo:
        read_fiscal_year_evidence(str(fake))
    assert "could not be opened as a PDF" in str(excinfo.value)
    assert "F_10-K_2024.pdf" in str(excinfo.value)


def test_the_reader_stops_on_a_missing_file(tmp_path: Path) -> None:
    gone = tmp_path / "gone.pdf"
    with pytest.raises(ValueError, match="is not a readable file"):
        read_fiscal_year_evidence(str(gone))


# ===========================================================================
# 4. End to end on written PDFs: discover_filings, with no stub at all
# ===========================================================================


def _lhx_like_folder(directory: Path) -> dict[int, Path]:
    """Three filings shaped like the assignment's L3Harris rows, named by the
    filename date, as L3Harris names them."""
    return {
        2023: write_10k_pdf(directory / "LHX_10-K_2023-12-29.pdf", "December 29, 2023",
                            "(In millions) December 29, 2023 December 30, 2022 December 31, 2021"),
        2025: write_10k_pdf(directory / "LHX_10-K_2025-01-03.pdf", "January 3, 2025",
                            "(In millions) January 3, 2025 December 29, 2023 December 30, 2022"),
        2026: write_10k_pdf(directory / "LHX_10-K_2026-01-02.pdf", "January 2, 2026",
                            "(In millions, except per share amounts) 2025 2024 2023"),
    }


def test_discover_filings_stops_on_the_two_lhx_like_filings_and_names_both(
    tmp_path: Path,
) -> None:
    """By the table: 2023-12-29 -> 2023 (agrees); 2025-01-03 -> 2024 (filename
    2025); 2026-01-02 -> label 2025 (filename 2026). One message, two files."""
    _lhx_like_folder(tmp_path)
    with pytest.raises(ValueError) as excinfo:
        discover_filings(tmp_path, "LHX")
    message = str(excinfo.value)
    assert "LHX_10-K_2023-12-29.pdf" not in message
    assert "'LHX_10-K_2025-01-03.pdf' is given fiscal year 2025, but its content gives 2024" in message
    assert "'LHX_10-K_2026-01-02.pdf' is given fiscal year 2026, but its content gives 2025" in message


def test_the_cli_remedy_is_accepted_for_the_lhx_like_filings(tmp_path: Path) -> None:
    paths = _lhx_like_folder(tmp_path)
    args = [f"2023:{paths[2023]}", f"2024:{paths[2025]}", f"2025:{paths[2026]}"]
    assert parse_pdf_args(args) == [
        (2023, str(paths[2023])), (2024, str(paths[2025])), (2025, str(paths[2026]))]


def test_discover_filings_returns_agreeing_filings_by_year(tmp_path: Path) -> None:
    """Two calendar filings whose content gives the filename's year: no stop, and
    the list is ordered by year (`discover_filings`: `sorted(filings_by_year)`)."""
    newer = write_10k_pdf(tmp_path / "CAL_10-K_2024-12-31.pdf", "December 31, 2024",
                          "(In millions) 2024 2023 2022")
    older = write_10k_pdf(tmp_path / "CAL_10-K_2023-12-31.pdf", "December 31, 2023",
                          "(In millions) 2023 2022 2021")
    assert discover_filings(tmp_path, "CAL") == [
        (2023, str(older.resolve())), (2024, str(newer.resolve()))]
    # A folder given to parse_pdf_args goes the same way.
    assert parse_pdf_args([str(tmp_path)]) == [
        (2023, str(older.resolve())), (2024, str(newer.resolve()))]


def test_parse_pdf_args_does_not_verify_a_bare_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare path is year 0 ('extract all years', the docstring) and is not read."""
    asked = _stub(monkeypatch, {})
    assert parse_pdf_args(["/f/anything.pdf"]) == [(0, "/f/anything.pdf")]
    assert asked == []


def test_discover_filings_stops_on_a_name_with_no_year_naming_it(tmp_path: Path) -> None:
    (tmp_path / "annual-report.pdf").write_bytes(b"%PDF-1.4 never opened")
    with pytest.raises(ValueError) as excinfo:
        discover_filings(tmp_path, "TST")
    assert "Could not infer a fiscal year" in str(excinfo.value)
    assert "annual-report.pdf" in str(excinfo.value)


def test_discover_filings_stops_on_two_names_with_one_year_naming_both(tmp_path: Path) -> None:
    (tmp_path / "A_10-K_2024.pdf").write_bytes(b"%PDF-1.4 never opened")
    (tmp_path / "B_10-K_2024-12-31.pdf").write_bytes(b"%PDF-1.4 never opened")
    with pytest.raises(ValueError) as excinfo:
        discover_filings(tmp_path, "TST")
    message = str(excinfo.value)
    assert "fiscal year 2024" in message
    assert "A_10-K_2024.pdf" in message
    assert "B_10-K_2024-12-31.pdf" in message


def test_the_reader_skips_a_title_with_no_headings_under_it(tmp_path: Path) -> None:
    """A title alone on its line with no column headings within the next lines
    (an index entry, say) is passed over; the real statement on page 3 is used."""
    pdf = write_text_pdf(tmp_path / "T_10-K_2024.pdf", [
        ["FORM 10-K", "ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d)",
         "For the fiscal year ended December 31, 2024"],
        ["Consolidated Statements of Operations", "see Item 8 below"],
        ["Consolidated Statements of Operations", "(In millions) 2024 2023 2022"],
    ])
    evidence = read_fiscal_year_evidence(str(pdf))
    assert evidence.column_label == "2024"
    assert evidence.column_page == 3


def test_the_reader_finds_a_cover_that_follows_the_statement(tmp_path: Path) -> None:
    """Within the first five pages the order does not matter: statement on
    page 1, cover on page 2."""
    pdf = write_text_pdf(tmp_path / "O_10-K_2024.pdf", [
        ["CONSOLIDATED STATEMENTS OF EARNINGS", "(In millions) 2024 2023 2022"],
        ["FORM 10-K", "ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d)",
         "For the fiscal year ended December 31, 2024"],
    ])
    evidence = read_fiscal_year_evidence(str(pdf))
    assert (evidence.cover_date, evidence.cover_page) == ("December 31, 2024", 2)
    assert (evidence.column_label, evidence.column_page) == ("2024", 1)


# ===========================================================================
# 5. fiscal_year_from_filename — the one filename year guesser (P10c step 3)
# ===========================================================================


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # The four examples in discover_filings' docstring: the year after 10-K.
        ("ABBV_10K_2024.pdf", 2024),
        ("ABBV_10-K_2024-12-31.pdf", 2024),
        ("AbbVie Inc._10-K_2024-12-31_English.pdf", 2024),
        ("Eli Lilly and Company_10-K_2024-12-31_English_237118761_1.pdf", 2024),
        # The marker year is preferred over an earlier year token in the name.
        ("2019 archive_10-K_2024.pdf", 2024),
        # The marker is matched case-insensitively.
        ("goog-10k-2024.pdf", 2024),
        # No marker: the first 4-digit 19xx/20xx year in the name.
        ("annual-report-2023-final.pdf", 2023),
    ],
)
def test_fiscal_year_from_filename(name: str, expected: int) -> None:
    assert fiscal_year_from_filename(name) == expected


def test_fiscal_year_from_filename_is_none_when_the_name_names_no_year() -> None:
    """None, not a default year: each caller decides what an unnamed year means
    (the docstring)."""
    assert fiscal_year_from_filename("annual-report.pdf") is None
