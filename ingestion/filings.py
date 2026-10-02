"""Filing discovery and content fingerprinting, shared by every extraction route.

Moved verbatim from `cli.py` (P9a-session-route) so the CLI's API route and the
Claude Code session route (`ingestion/session_extraction.py`) resolve the same PDFs
to the same fiscal years and hash them the same way. A second copy of any of these
would be backlog item 7 again. The only change in the move is the public name
`discover_filings` (it was `_discover_filings`), because another module now imports it.

Known and deliberately not fixed here: the fiscal year comes from the FILENAME, not
from the filing. A 52/53-week filer such as L3Harris files its fiscal-2025 10-K with a
2026-01-02 period end, and `discover_filings` calls it 2026.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


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
    when present, otherwise from the first 4-digit year found in the name.
    """
    # Prefer a year that follows the 10-K marker; fall back to any year token.
    marker_pattern = re.compile(r"10[-_ ]?K[^0-9]*((?:19|20)\d{2})", re.IGNORECASE)
    year_pattern = re.compile(r"(?:19|20)\d{2}")

    filings_by_year: dict[int, Path] = {}
    skipped: list[str] = []

    for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue

        marker = marker_pattern.search(path.name)
        if marker:
            fiscal_year = int(marker.group(1))
        else:
            year_match = year_pattern.search(path.name)
            if not year_match:
                skipped.append(path.name)
                continue
            fiscal_year = int(year_match.group(0))

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

    return [
        (year, str(filings_by_year[year]))
        for year in sorted(filings_by_year)
    ]


def parse_pdf_args(
    pdf_strings: list[str], ticker: str | None = None
) -> list[tuple[int, str]]:
    """Resolve a ticker folder, 'YEAR:path', or bare PDF path.

    A bare path (no year prefix) returns [(0, path)] — year=0 signals
    'extract all years automatically'.
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
