"""Tests for `tests/unit/_real_filings.py`, the real-filing lookup (P1d, item 101).

The defect this helper replaced was a guard that looked in the wrong folder and
skipped silently. A guard is only worth having if it is itself checked, so every
branch of `RealFiling` is exercised here, against a filings tree built under
`tmp_path`. **Nothing here reads `10K_filings/`**, so these tests run the same on
a machine that holds no filing at all.

Where every expected value comes from: the contract stated in `_real_filings`'s
module docstring, written down before the helper ran.

- the lookup is `<FILINGS_ROOT>/<ticker>/<pattern>`, so a file placed at exactly
  that path is found and one placed anywhere else is not;
- **exactly one match counts as found**, because a pattern matching two files
  names no one document;
- a miss names the path it tried, so `pytest -rs` tells a reader what was looked
  for;
- `read_bytes` on a miss stops and names the same path (rule 3: a missing input
  stops the run and names itself), it does not return empty bytes.

No network socket, no API key, no PDF library.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit import _real_filings
from tests.unit._real_filings import FILINGS_ROOT, REPO_ROOT, RealFiling


@pytest.fixture
def filings_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A filings tree under `tmp_path`, in place of the repository's."""
    root = tmp_path / "10K_filings"
    root.mkdir()
    monkeypatch.setattr(_real_filings, "FILINGS_ROOT", root)
    return root


def test_the_lookup_is_the_ticker_folder_not_the_company_name(filings_root: Path) -> None:
    """A file under `<root>/WMT/` is found by ticker and not by company name.

    This is the defect of item 101 stated as a test: the file name was right and
    the folder was the company name, and the guard reported "not found".
    """
    wmt = filings_root / "WMT"
    wmt.mkdir()
    (wmt / "Walmart Inc._10-K_2026-01-31_English.pdf").write_bytes(b"%PDF-1.4 one")

    by_ticker = RealFiling("WMT", "Walmart Inc._10-K_2026-01-31_English.pdf")
    assert by_ticker.found is True
    assert by_ticker.path == wmt / "Walmart Inc._10-K_2026-01-31_English.pdf"
    assert by_ticker.read_bytes() == b"%PDF-1.4 one"

    by_company_name = RealFiling("Walmart", "Walmart Inc._10-K_2026-01-31_English.pdf")
    assert by_company_name.found is False


def test_a_missing_file_is_not_found_and_the_reason_names_the_path_tried(
    filings_root: Path,
) -> None:
    """Zero matches: `found` is False and the reason holds the whole path tried."""
    (filings_root / "WMT").mkdir()

    absent = RealFiling("WMT", "Walmart Inc._10-K_2099-01-31_English.pdf")
    assert absent.found is False
    assert absent.path is None
    assert absent.tried == "10K_filings/WMT/Walmart Inc._10-K_2099-01-31_English.pdf"
    assert absent.skip_reason == (
        "no file on this machine matches "
        "10K_filings/WMT/Walmart Inc._10-K_2099-01-31_English.pdf"
    )


def test_a_ticker_folder_that_does_not_exist_is_a_miss_not_an_error(
    filings_root: Path,
) -> None:
    """No folder for the ticker: a miss, with the same reason. No exception."""
    assert not (filings_root / "CMG").exists()

    absent = RealFiling("CMG", "Chipotle Mexican Grill Inc._10-K_2025-12-31_English.pdf")
    assert absent.matches() == []
    assert absent.found is False
    assert "10K_filings/CMG/" in absent.skip_reason


def test_two_matches_name_no_one_document_so_the_lookup_misses(
    filings_root: Path,
) -> None:
    """A wildcard matching three fiscal years is a miss, and the reason says so.

    Reading "whichever sorted first" would silently test a different filing from
    the one the test's citations describe. The three L3Harris files on this
    machine are exactly that shape.
    """
    lhx = filings_root / "LHX"
    lhx.mkdir()
    for year in (2023, 2024, 2025):
        (lhx / f"L3Harris Technologies Inc._10-K_{year}_English.pdf").write_bytes(b"%PDF-1.4")

    wildcard = RealFiling("LHX", "L3Harris Technologies Inc._10-K_*_English.pdf")
    assert len(wildcard.matches()) == 3
    assert wildcard.found is False
    assert wildcard.path is None
    reason = wildcard.skip_reason
    assert "3 files match" in reason
    assert "names no one document" in reason
    for year in (2023, 2024, 2025):
        assert f"L3Harris Technologies Inc._10-K_{year}_English.pdf" in reason

    # The same folder, one whole file name: found.
    one = RealFiling("LHX", "L3Harris Technologies Inc._10-K_2025_English.pdf")
    assert one.found is True
    assert one.path == lhx / "L3Harris Technologies Inc._10-K_2025_English.pdf"


def test_a_directory_matching_the_pattern_is_not_a_filing(filings_root: Path) -> None:
    """Only files count. A folder whose name matches the pattern is not a filing."""
    wmt = filings_root / "WMT"
    wmt.mkdir()
    (wmt / "Walmart Inc._10-K_2026-01-31_English.pdf").mkdir()

    lookup = RealFiling("WMT", "Walmart Inc._10-K_2026-01-31_English.pdf")
    assert lookup.matches() == []
    assert lookup.found is False


def test_read_bytes_on_a_miss_stops_and_names_the_path_tried(filings_root: Path) -> None:
    """Rule 3: a missing filing stops and names itself. It never returns b''."""
    (filings_root / "OKTA").mkdir()

    absent = RealFiling("OKTA", "Okta Inc._10-K_2026-01-31_English.pdf")
    with pytest.raises(FileNotFoundError) as excinfo:
        absent.read_bytes()
    message = str(excinfo.value)
    assert "10K_filings/OKTA/Okta Inc._10-K_2026-01-31_English.pdf" in message


def test_filings_root_sits_at_the_repository_root() -> None:
    """The unpatched constants point at this repository, not at the process cwd.

    `FILINGS_ROOT` is absolute and is `<repo>/10K_filings`, so a test reading a
    filing works whatever directory pytest was started in. `REPO_ROOT` is the
    folder holding `docs/` and `tests/`.
    """
    assert FILINGS_ROOT.is_absolute()
    assert FILINGS_ROOT == REPO_ROOT / "10K_filings"
    assert (REPO_ROOT / "tests" / "unit" / "_real_filings.py").is_file()
    assert (REPO_ROOT / "docs" / "INDEX.md").is_file()
