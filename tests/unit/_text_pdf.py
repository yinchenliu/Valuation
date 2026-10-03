"""Write a minimal, valid PDF whose pages carry the lines of text a test gives.

`ingestion.filings.read_fiscal_year_evidence` reads printed text with
`pdfplumber`. A test that wants to drive the reader itself, rather than stub it,
needs a PDF whose text it chose. This builds one from scratch: one Type 1 font
(Helvetica, one of the 14 standard fonts every PDF reader carries, so nothing is
embedded), one text line per given string, 20 points apart, and a correct
cross-reference table. Each string becomes one line of `extract_text()`.

No real filing is read, and `10K_filings/` is never touched: the expected value
of every test that uses this is the text the test itself wrote.
"""

from __future__ import annotations

from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_text_pdf(path: Path, pages: list[list[str]]) -> Path:
    """Write `pages` (a list of pages, each a list of lines) to `path`."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            "<< /Type /Pages /Kids ["
            + " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
            + f"] /Count {len(pages)} >>"
        ).encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, lines in enumerate(pages):
        ops = ["BT", "/F1 10 Tf"]
        for row, line in enumerate(lines):
            ops.append(f"1 0 0 1 50 {750 - 20 * row} Tm ({_escape(line)}) Tj")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>"
            ).encode()
        )
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()
    path.write_bytes(bytes(out))
    return path


COVER_MARKER = (
    "ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934"
)


def write_10k_pdf(
    path: Path,
    cover_date: str,
    heading_line: str,
    *,
    title: str = "CONSOLIDATED STATEMENTS OF OPERATIONS",
    filler_pages: int = 1,
) -> Path:
    """A three-part stand-in for a 10-K: a cover on page 1, `filler_pages` of
    prose, then the income statement's title and its column headings.

    The income statement is therefore on page `2 + filler_pages`.
    """
    cover = ["UNITED STATES", "FORM 10-K", COVER_MARKER,
             f"For the fiscal year ended {cover_date}", "Test Filer Inc."]
    filler = [["Item 7. Management's Discussion and Analysis"]] * filler_pages
    statement = [title, heading_line, "Revenue 1,000 900 800"]
    return write_text_pdf(path, [cover, *filler, statement])
