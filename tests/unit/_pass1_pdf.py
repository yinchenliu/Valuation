"""A real PDF that prints every row a Pass 1 answer cites, on the page it cites.

Since `P12a-printed-pages` both routes open the filing with `pdfplumber` and look
for each Pass 1 printed line, its label and its figure, on one text line of its
cited page (`ingestion/claude_extractor.py:printed_line_on_page`). A fixture that
hands the loader or route A's runner a few stand-in bytes now stops, because
`pdfplumber` cannot open them.

This module is the ONE place a fixture's PDF is built, and it is built from the
fixture's own printed lines, so the two cannot drift apart: change a row in the
JSON, rebuild, and the page prints the new row.

**It holds no expected value.** Every label, figure and page comes from the
caller's JSON. Each row is printed as `<label> <figure>` on its own text line of
its cited page, the way a statement prints a row: label first, then the figure.
A figure is written as a statement writes one (the rule's step 1,
`docs/3-architecture/extraction.md`, "The page check"):

- thousands commas (`4,984`), and a decimal part only when there is one;
- a negative value in parentheses (`(5)`): the rule compares magnitudes, so the
  sign is the statement's business, not the check's;
- a value of 0 as a dash standing alone (`-`), the way statements print a nil row.

Page 1 carries a cover line naming the filing, so two fixtures with the same rows
still have different bytes and different sha256s. Pages that no row cites are
blank. Nothing here reads `10K_filings/`.

The underscore keeps pytest from collecting it.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from tests.unit._text_pdf import write_text_pdf

# Lines 12 points apart (the font is 10 points, so each row stays its own text
# line). write_text_pdf puts line n at y = 750 - 12 n on a 792-point page, so line
# 62 is the last one above the bottom edge (750 - 12 * 62 = 6): 63 lines a page.
_LEADING = 12
_MAX_LINES_PER_PAGE = 63


def printed_figure(value: float) -> str:
    """A value as a statement prints it: `1,000`, `(5)`, `2.5`, `-` for 0."""
    if value == 0:
        return "-"
    magnitude = abs(value)
    if float(magnitude).is_integer():
        text = f"{int(magnitude):,}"
    else:
        text = f"{magnitude:,}"
    return f"({text})" if value < 0 else text


def _is_printed_row(row: object) -> bool:
    """A well-formed row: a label string, a finite number, a page of 1 or more.

    A fixture that breaks a row on purpose (to test a stop) breaks it after the PDF
    is written; such a row is not printed, because there is nothing to print.
    """
    if not isinstance(row, Mapping):
        return False
    label, value, page = row.get("label"), row.get("value"), row.get("page")
    return (
        isinstance(label, str)
        and isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(value)
        and isinstance(page, int) and not isinstance(page, bool) and page >= 1
    )


def _rows_of(block: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    """Every printed row of one year entry or one balance sheet, field by field."""
    for value in block.values():
        if isinstance(value, list):
            yield from (row for row in value if _is_printed_row(row))


def pass1_pages(*answers: object) -> dict[int, list[str]]:
    """Each cited page and the text lines it prints, from one or more answers.

    Several answers (route A's scripted first answer and its retry) are printed
    on the same pages, so every row each of them cites is on its page. A row
    printed twice is printed once. Anything that is not a JSON object (a scripted
    non-JSON answer) has no rows.
    """
    pages: dict[int, list[str]] = {}
    for answer in answers:
        if not isinstance(answer, Mapping):
            continue
        blocks: list[Mapping[str, Any]] = [
            entry for entry in answer.get("historical_years", [])
            if isinstance(entry, Mapping)
        ]
        balance = answer.get("latest_balance_sheet")
        if isinstance(balance, Mapping) and balance:
            blocks.append(balance)
        for block in blocks:
            for row in _rows_of(block):
                text = f"{row['label']} {printed_figure(row['value'])}"
                lines = pages.setdefault(row["page"], [])
                if text not in lines:
                    lines.append(text)
        for key in ("units", "share_units"):
            unit_obj = answer.get(key)
            if isinstance(unit_obj, Mapping):
                printed = unit_obj.get("printed")
                page = unit_obj.get("page")
                if isinstance(printed, str) and isinstance(page, int) and page >= 1:
                    lines = pages.setdefault(page, [])
                    if printed not in lines:
                        lines.append(printed)
        nri_items = answer.get("non_recurring_items", [])
        if isinstance(nri_items, list):
            for item in nri_items:
                if isinstance(item, Mapping):
                    page = item.get("page")
                    amt = item.get("amount")
                    desc = item.get("description", "NRI")
                    if isinstance(page, int) and isinstance(amt, (int, float)) and page >= 1:
                        text = f"{desc} {printed_figure(amt)}"
                        lines = pages.setdefault(page, [])
                        if text not in lines:
                            lines.append(text)
                    unit_obj = item.get("units")
                    if isinstance(unit_obj, Mapping):
                        u_printed = unit_obj.get("printed")
                        u_page = unit_obj.get("page")
                        if isinstance(u_printed, str) and isinstance(u_page, int) and u_page >= 1:
                            lines = pages.setdefault(u_page, [])
                            if u_printed not in lines:
                                lines.append(u_printed)
    for page, lines in pages.items():
        assert len(lines) <= _MAX_LINES_PER_PAGE, (
            f"page {page} would print {len(lines)} lines; write_text_pdf fits "
            f"{_MAX_LINES_PER_PAGE}"
        )
    return pages


def write_pass1_pdf(path: Path, *answers: object, cover: str = "Test filing") -> Path:
    """Write a PDF that prints every row of `answers` on its cited page.

    Page 1 holds `cover` (and any row that cites page 1). The PDF runs to the
    highest page any row cites, and to at least one page.
    """
    pages = pass1_pages(*answers)
    last = max([1, *pages])
    texts = [list(pages.get(number, [])) for number in range(1, last + 1)]
    texts[0].insert(0, cover)
    return write_text_pdf(path, texts, leading=_LEADING)


def reprint_filing_pdf(filing: dict[str, Any], *, cover: str | None = None) -> None:
    """Rewrite a session filing's PDF from its own `pass1`, and record its new hash.

    For a test that changes a row of the session's Pass 1 after the PDF was first
    written: the PDF then prints the changed row, and the session file records the
    sha256 and size of the bytes now on disk, so the loader's hash check still holds.
    """
    path = Path(filing["pdf_path"])
    answers_to_print = [filing["pass1"]]
    if filing.get("pass2"):
        answers_to_print.append(filing["pass2"])
    write_pass1_pdf(path, *answers_to_print, cover=cover or f"Test filing {path.name}")
    data = path.read_bytes()
    filing["pdf_sha256"] = hashlib.sha256(data).hexdigest()
    filing["size_bytes"] = len(data)
