"""Filing discovery, fiscal-year verification and content fingerprinting, shared by every route.

Moved verbatim from `cli.py` (P9a-session-route) so the CLI's API route and the
Claude Code session route (`ingestion/session_extraction.py`) resolve the same PDFs
to the same fiscal years and hash them the same way. A second copy of any of these
would be backlog item 7 again. The only change in the move is the public name
`discover_filings` (it was `_discover_filings`), because another module now imports it.

The fiscal year still comes from the FILENAME (`fiscal_year_from_filename`, the one
year guesser; the web upload uses it too). Since P10c (backlog item 43, the user's
decision of 2026-10-02) every year so given is verified against the filing itself
before anything is extracted:

* `read_fiscal_year_evidence` reads two printed facts with `pdfplumber`: the cover's
  "For the fiscal year ended <Month D, YYYY>", and the newest column label above the
  income statement (a bare year such as "2025", or a date such as "January 3, 2025").
* `fiscal_year_from_evidence` decides the content year from those two strings alone.
* `verify_filing_years` compares, and stops on a mismatch, naming both.

No model is involved: this reads printed text, so rule 1 does not apply. A 52/53-week
filer is why it exists: L3Harris files the year ended 2026-01-02 as fiscal 2025, and its
filename says 2026.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# The year a filename names
# ---------------------------------------------------------------------------

# Prefer a year that follows the 10-K marker; fall back to any year token.
_MARKER_YEAR = re.compile(r"10[-_ ]?K[^0-9]*((?:19|20)\d{2})", re.IGNORECASE)
_ANY_YEAR = re.compile(r"(?:19|20)\d{2}")


def fiscal_year_from_filename(name: str) -> int | None:
    """The fiscal year a filename names, or None when it names none.

    The year is taken from a date/year token following a '10-K'/'10K' marker
    when present, otherwise from the first 4-digit year (19xx or 20xx) in the
    name. This is the only filename year guesser: `discover_filings` and the web
    upload (`api/routes_upload.py`) both call it. None is returned, not a
    default, so each caller decides what an unnamed year means.
    """
    marker = _MARKER_YEAR.search(name)
    if marker:
        return int(marker.group(1))
    year_match = _ANY_YEAR.search(name)
    if year_match:
        return int(year_match.group(0))
    return None


# ---------------------------------------------------------------------------
# The year the filing's content gives
# ---------------------------------------------------------------------------

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_DATE_TEXT = (
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2}\s*,\s*(?:19|20)\d{2}"
)
_PRINTED_DATE = re.compile(
    r"^\s*([A-Za-z]+)\s+(\d{1,2})\s*,\s*((?:19|20)\d{2})\s*$"
)
_BARE_YEAR = re.compile(r"^\s*((?:19|20)\d{2})\s*$")

# The cover line of a 10-K: "For the fiscal year ended <date>" following the cover's
# "ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d)". The marker is required because
# the same words recur in prose ("…Annual Report on Form 10-K for the fiscal year
# ended December 31, 2023" in AbbVie's 2024 MD&A), which is not this filing's cover.
# A 10-Q says "QUARTERLY REPORT … For the quarterly period ended" and does not
# match; a scanned PDF has no text layer. Both stop in the reader.
_COVER_LINE = re.compile(
    r"annual\s+report\s+pursuant\s+to\s+section\s+13\s+or\s+15\s*\(\s*d\s*\)"
    r"[\s\S]{0,400}?"
    r"for\s+the\s+fiscal\s+year\s+ended\s*:?\s*(" + _DATE_TEXT + r")",
    re.IGNORECASE,
)
# The income statement's title, alone on its line. A table-of-contents entry
# carries a page number or "— Fiscal Year Ended …" after the title, and a sentence
# carries more words, so neither matches.
_INCOME_STATEMENT_TITLE = re.compile(
    r"^\s*consolidated\s+statements?\s+of\s+(?:income|earnings|operations)"
    r"(?:\s+and\s+comprehensive\s+(?:income|loss|income\s*\(loss\)|\(loss\)\s*income))?"
    r"\s*$",
    re.IGNORECASE,
)
# Column headings: at least two dates, or at least two bare years ending the line.
_DATE_ANYWHERE = re.compile(_DATE_TEXT, re.IGNORECASE)
_TRAILING_YEARS = re.compile(r"(?:^|\s)((?:(?:19|20)\d{2}\s+)+(?:19|20)\d{2})\s*$")

# How many pages the cover line is looked for in, and how many lines below the
# income statement's title its column headings may sit. Measured on the 16 filings
# under 10K_filings/ on 2026-10-02: the cover line is on page 1 of every one, and the
# headings are 1 to 3 lines below the title.
_COVER_PAGES = 5
_HEADING_LINES_BELOW_TITLE = 5

# The 52/53-week convention: a fiscal year that ends on the Friday or Saturday
# nearest December 31 and lands in the first days of January is named for the
# year before. L3Harris names the year ended January 2, 2026 "2025". Seven days is
# the whole window a nearest-weekday rule can reach past December 31.
_JANUARY_DAYS_OF_PRIOR_YEAR = 7


def _parse_printed_date(text: str, what: str) -> date:
    """A date printed as 'Month D, YYYY'. Anything else stops, naming `what`."""
    match = _PRINTED_DATE.match(text)
    if match is None or match.group(1).lower() not in _MONTHS:
        raise ValueError(f"{what} {text!r} is not a date printed as 'Month D, YYYY'")
    try:
        return date(
            int(match.group(3)), _MONTHS[match.group(1).lower()], int(match.group(2))
        )
    except ValueError as exc:
        raise ValueError(f"{what} {text!r} is not a calendar date ({exc})") from exc


def _cover_rule_year(cover: date) -> int:
    """The fiscal year a cover date names under the 52/53-week convention."""
    if cover.month == 1 and cover.day <= _JANUARY_DAYS_OF_PRIOR_YEAR:
        return cover.year - 1
    return cover.year


def fiscal_year_from_evidence(cover_date: str, column_label: str) -> int:
    """Decide the fiscal year a filing's content gives, from two printed strings.

    Args:
        cover_date: the cover's "For the fiscal year ended" date, as printed,
            e.g. "January 3, 2025".
        column_label: the newest column label above the income statement, as
            printed: a bare year ("2025") or a date ("January 3, 2025").

    The rule (assignment P10c, the user's decision of 2026-10-02, amended in
    round 2 after review F2):

    * a bare-year label is the filing's own name for the year, and wins when it
      is the cover date's year or the year before. That covers the calendar
      filer (December 31, 2025 -> "2025"), the 52/53-week filer whose year ends
      in early January (L3Harris: January 2, 2026 -> "2025"), and the retailer
      that names a year for the calendar year it starts in (Target: February 1,
      2025 -> "2024");
    * a bare-year label outside that range stops: that far from the period end,
      it is more likely a misread than a convention;
    * with a date label, the cover rule gives the year: the year of the cover
      date, except that a year ending in the first seven days of January
      belongs to the year before (52/53-week). The label must be the cover date.

    Raises:
        ValueError: when either string is not what it should be, or when the
            label and the cover disagree. The message names both.
    """
    cover = _parse_printed_date(cover_date, "the cover date")
    bare = _BARE_YEAR.match(column_label)
    if bare:
        label_year = int(bare.group(1))
        if label_year not in (cover.year, cover.year - 1):
            raise ValueError(
                f"the income statement's newest column is labelled {label_year}, "
                f"but the cover's fiscal year ended {cover_date}. A label is "
                f"accepted only as the cover date's year ({cover.year}) or the "
                f"year before ({cover.year - 1}); one further away is more likely "
                "a misread than a naming convention, so no year is chosen"
            )
        return label_year
    if not _PRINTED_DATE.match(column_label):
        raise ValueError(
            f"the income statement's column label {column_label!r} is neither a "
            "bare year nor a date printed as 'Month D, YYYY'"
        )
    label = _parse_printed_date(column_label, "the income statement's column label")
    if label != cover:
        raise ValueError(
            f"the income statement's newest column is dated {column_label}, but "
            f"the cover's fiscal year ended {cover_date}. The filing contradicts "
            "itself; no year is chosen"
        )
    return _cover_rule_year(cover)


@dataclass(frozen=True)
class FiscalYearEvidence:
    """The two printed facts a filing's fiscal year is decided from, and where."""

    path: str
    cover_date: str
    cover_page: int
    column_label: str
    column_page: int


def _newest_column_label(line: str) -> str | None:
    """The newest column heading on a heading line, as printed, or None."""
    dates = [" ".join(found.split()) for found in _DATE_ANYWHERE.findall(line)]
    if len(dates) >= 2:
        return max(dates, key=lambda text: _parse_printed_date(text, "a column heading"))
    years = _TRAILING_YEARS.search(line)
    if years:
        return str(max(int(y) for y in years.group(1).split()))
    return None


def read_fiscal_year_evidence(pdf_path: str) -> FiscalYearEvidence:
    """Read the cover date and the income statement's newest column label.

    Raises:
        ValueError: when the file cannot be opened as a PDF, when no cover line
            is found in the first pages (a 10-Q, or a scanned PDF with no text
            layer), or when no income statement column headings are found.
            Each message names the file and what was not found. Rule 3: the year
            is never assumed from the filename alone.
    """
    import pdfplumber
    from pdfplumber.utils.exceptions import PdfminerException

    path = Path(pdf_path)
    if not path.is_file():
        raise ValueError(
            f"{pdf_path!r} is not a readable file, so its fiscal year cannot be "
            "checked against its content"
        )
    cover: tuple[str, int] | None = None
    column: tuple[str, int] | None = None
    try:
        with pdfplumber.open(path) as pdf:
            for index, page in enumerate(pdf.pages):
                text = page.extract_text()
                if cover is None and index < _COVER_PAGES:
                    found = _COVER_LINE.search(text)
                    if found:
                        cover = (" ".join(found.group(1).split()), index + 1)
                if column is None:
                    lines = text.splitlines()
                    for at, line in enumerate(lines):
                        if not _INCOME_STATEMENT_TITLE.match(line):
                            continue
                        below = lines[at + 1: at + 1 + _HEADING_LINES_BELOW_TITLE]
                        labels = [_newest_column_label(b) for b in below]
                        newest = next((lab for lab in labels if lab is not None), None)
                        if newest is not None:
                            column = (newest, index + 1)
                            break
                if column is not None and (cover is not None or index >= _COVER_PAGES - 1):
                    break
    except PdfminerException as exc:
        raise ValueError(
            f"{path.name!r} could not be opened as a PDF ({exc}), so its fiscal "
            "year cannot be checked against its content"
        ) from exc
    if cover is None:
        raise ValueError(
            f"{path.name!r}: no 10-K cover line ('ANNUAL REPORT PURSUANT TO "
            "SECTION 13 OR 15(d)' then 'For the fiscal year ended <Month D, YYYY>') "
            f"in its first {_COVER_PAGES} pages, so its fiscal year cannot be checked "
            "against its content. A 10-Q, or a scanned PDF with no text layer, "
            "has none"
        )
    if column is None:
        raise ValueError(
            f"{path.name!r}: no column headings (two or more years or dates) found "
            "under a 'Consolidated Statement(s) of Income/Earnings/Operations' "
            "title, so its fiscal year cannot be checked against its content"
        )
    return FiscalYearEvidence(
        path=str(path),
        cover_date=cover[0],
        cover_page=cover[1],
        column_label=column[0],
        column_page=column[1],
    )


Remedy = Literal["year_path", "rename_and_upload"]
"""What a user can do about a wrong year: pass YEAR:PATH (the CLI and route B's
`plan`), or rename the file and upload it again (the web upload)."""


def _remedy_text(remedy: Remedy, content_year: int, pdf_path: str) -> str:
    if remedy == "year_path":
        return (
            f"Pass {content_year}:{pdf_path} instead, or rename the file so the "
            f"year after '10-K' in its name is {content_year}."
        )
    return (
        f"Rename the file so the year after '10-K' in its name is "
        f"{content_year}, and upload it again."
    )


def _year_mismatch(
    year: int, pdf_path: str, remedy: Remedy
) -> tuple[Literal["mismatch", "unconfirmed"], str] | None:
    """Check one filing. None when its content gives `year`.

    Otherwise ("mismatch", message) when the content gives another year, or
    ("unconfirmed", message) when the evidence could not be read or contradicts
    itself, so no content year exists to compare with.
    """
    name = Path(pdf_path).name
    try:
        evidence = read_fiscal_year_evidence(pdf_path)
    except ValueError as exc:
        return ("unconfirmed", f"{name!r}, given fiscal year {year}: {exc}.")
    where = (
        f"the cover says 'For the fiscal year ended {evidence.cover_date}' "
        f"(page {evidence.cover_page}) and the newest column above the income "
        f"statement is labelled '{evidence.column_label}' "
        f"(page {evidence.column_page})"
    )
    try:
        content_year = fiscal_year_from_evidence(
            evidence.cover_date, evidence.column_label
        )
    except ValueError as exc:
        return ("unconfirmed", f"{name!r}, given fiscal year {year}: {where}; {exc}.")
    if content_year == year:
        return None
    return (
        "mismatch",
        f"{name!r} is given fiscal year {year}, but its content gives "
        f"{content_year}: {where}. "
        + _remedy_text(remedy, content_year, pdf_path),
    )


def verify_filing_years(filings: list[tuple[int, str]], remedy: Remedy) -> None:
    """Check every (year, path) whose year is given against the filing's content.

    A year of 0 means "every year in the filing" (a bare path) and is not
    checked: there is no single year to compare. `remedy` names what the caller's
    user can do about a wrong year (see `Remedy`).

    Raises:
        ValueError: listing every filing whose year disagrees with its content,
            under one heading, and every filing whose year could not be
            confirmed (unreadable evidence, or a filing that contradicts
            itself), under another.
    """
    mismatched: list[str] = []
    unconfirmed: list[str] = []
    for year, pdf_path in filings:
        if year == 0:
            continue
        problem = _year_mismatch(year, pdf_path, remedy)
        if problem is None:
            continue
        kind, message = problem
        (mismatched if kind == "mismatch" else unconfirmed).append(message)
    sections: list[str] = []
    if mismatched:
        sections.append(
            "The fiscal year given does not match the filing:\n"
            + "\n".join(f"  - {m}" for m in mismatched)
        )
    if unconfirmed:
        sections.append(
            "The fiscal year given could not be confirmed against the filing:\n"
            + "\n".join(f"  - {m}" for m in unconfirmed)
        )
    if sections:
        raise ValueError("\n".join(sections) + "\nNothing was extracted.")


def discover_filings(directory: Path, ticker: str) -> list[tuple[int, str]]:
    """Discover 10-K PDFs in a directory, inferring fiscal year from each filename.

    The prefix does not matter — the ticker, the full company name, or anything
    else may lead the filename. Each PDF only needs to contain a 4-digit fiscal
    year, ideally as part of a filing date. Examples that all work:

        ABBV_10K_2024.pdf
        ABBV_10-K_2024-12-31.pdf
        AbbVie Inc._10-K_2024-12-31_English.pdf
        Eli Lilly and Company_10-K_2024-12-31_English_237118761_1.pdf

    The year is taken from a date/year token following a '10-K'/'10K' marker
    when present, otherwise from the first 4-digit year found in the name
    (`fiscal_year_from_filename`). Every year is then verified against the
    filing's content (`verify_filing_years`); a mismatch stops.
    """
    filings_by_year: dict[int, Path] = {}
    skipped: list[str] = []

    for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue

        fiscal_year = fiscal_year_from_filename(path.name)
        if fiscal_year is None:
            skipped.append(path.name)
            continue

        if fiscal_year in filings_by_year:
            other = filings_by_year[fiscal_year].name
            raise ValueError(
                f"Multiple 10-K PDFs resolve to fiscal year {fiscal_year}: "
                f"{other!r} and {path.name!r}"
            )
        filings_by_year[fiscal_year] = path.resolve()

    if skipped:
        names = ", ".join(repr(name) for name in skipped)
        raise ValueError(
            f"Could not infer a fiscal year from PDF filename(s): {names}. "
            f"Include a 4-digit year in the filename, e.g. "
            f"'{ticker}_10-K_2024-12-31.pdf' or '{ticker}_10K_2024.pdf'."
        )
    if not filings_by_year:
        raise ValueError(
            f"No 10-K PDFs found in {directory}. Add PDF filings whose names "
            f"contain a fiscal year, e.g. '{ticker}_10-K_2024-12-31.pdf'."
        )

    filings = [
        (year, str(filings_by_year[year]))
        for year in sorted(filings_by_year)
    ]
    verify_filing_years(filings, "year_path")
    return filings


def parse_pdf_args(
    pdf_strings: list[str], ticker: str | None = None
) -> list[tuple[int, str]]:
    """Resolve a ticker folder, 'YEAR:path', or bare PDF path.

    A bare path (no year prefix) returns [(0, path)] — year=0 signals
    'extract all years automatically', and is not verified. Every 'YEAR:path'
    is verified against the filing's content (`verify_filing_years`), as a
    folder's filings are in `discover_filings`.
    """
    if len(pdf_strings) == 1 and Path(pdf_strings[0]).is_dir():
        directory = Path(pdf_strings[0])
        resolved_ticker = (ticker or directory.resolve().name).upper()
        return discover_filings(directory, resolved_ticker)

    filings: list[tuple[int, str]] = []
    for s in pdf_strings:
        if Path(s).is_dir():
            raise ValueError("A ticker folder must be the only PDF input")
        m = re.match(r"^(\d{4}):(.+)$", s)
        if m:
            filings.append((int(m.group(1)), m.group(2)))
        else:
            filings.append((0, s))
    verify_filing_years(filings, "year_path")
    return filings


@dataclass(frozen=True)
class InputFingerprint:
    """What one extraction input was, precisely enough to detect a swap.

    Backlog item 33. The cache used to be keyed on the ticker alone, so
    `cli.py "…LHX_2025.pdf" -t LHX --cache-dir ./cache` returned, in two
    seconds, a complete valuation computed from a pickle written days earlier
    from a different document — and printed nothing to say the PDF named on the
    command line had never been opened.

    `sha256` is the authority: a file rewritten with its timestamp preserved
    still changes it. `size_bytes` and `mtime_ns` are carried so the miss
    message can say *how* a file differs in terms a reader can check with
    `ls -l`, not only that its digest moved.
    """

    year: int
    path: str
    size_bytes: int
    mtime_ns: int
    sha256: str


def fingerprint_filings(filings: list[tuple[int, str]]) -> tuple[InputFingerprint, ...]:
    """Hash and stat every input PDF, in a stable order.

    Raises:
        FileNotFoundError: when an input path does not exist. Rule 3 — a cache
            decision must not be made from a file the run cannot read.
    """
    prints: list[InputFingerprint] = []
    for year, raw_path in filings:
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"extraction input {raw_path!r} is not a readable file, so its "
                "content cannot be fingerprinted and no cache decision can be "
                "made about it"
            )
        stat = path.stat()
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        prints.append(
            InputFingerprint(
                year=year,
                path=str(path.resolve()),
                size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                sha256=digest.hexdigest(),
            )
        )
    return tuple(sorted(prints, key=lambda p: (p.year, p.path)))
