"""Verification of portable session file PDF paths (Phase 15c, backlog item 146).

This module verifies:
1. `_format_pdf_path` writes repo-relative paths for PDFs inside `config.BASE_DIR`
   and absolute paths for PDFs outside `config.BASE_DIR`.
2. `_resolve_pdf_path` resolves relative paths against `config.BASE_DIR` rather than
   the current working directory (`cwd`), and preserves absolute paths as recorded.
3. `cmd_plan` writes repo-relative paths for repository PDFs and absolute paths for
   external PDFs.
4. `load_session_extraction` loads repo-relative paths when executed from another
   working directory (e.g. temporary directory).
5. `load_session_extraction` loads absolute paths correctly when recorded.
6. When a PDF file is missing on disk, `load_session_extraction` raises ValueError
   and names both the recorded path and the resolved path.
7. Rule 3 stops: missing, empty, or non-string `pdf_path` stops and names the field.

Expected values are derived by closed-form identity and hand calculation.
No assertion copies the runtime output of the code under test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import config
import ingestion.claude_extractor as ce
from ingestion.session_extraction import (
    _format_pdf_path,
    _resolve_pdf_path,
    cmd_plan,
    load_session_extraction,
)
from tests.unit._text_pdf import write_text_pdf

# Constants for test filings inside the repository
WMT_SESSION_PATH = config.BASE_DIR / "extractions" / "WMT.json"
WMT_PDF_REL_2024 = "10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf"
WMT_PDF_REL_2026 = "10K_filings/WMT/Walmart Inc._10-K_2026-01-31_English.pdf"


@pytest.fixture(autouse=True)
def _no_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Close the LLM API boundary for every test in this module."""

    def _refuse(*args: object, **kwargs: object) -> tuple[str, int, int]:
        raise AssertionError("a session-route test reached _call_llm")

    monkeypatch.setattr(ce, "_call_llm", _refuse)


# ===========================================================================
# Unit tests: _format_pdf_path
# ===========================================================================


def test_format_pdf_path_repo_relative_for_path_inside_repo() -> None:
    """Format path inside config.BASE_DIR as repo-relative posix string."""
    # Closed-form identity: relative_to(BASE_DIR).as_posix() strips the base dir
    # and normalizes path separators to forward slash.
    abs_inside = config.BASE_DIR / "10K_filings" / "WMT" / "Walmart Inc._10-K_2024-01-31_English.pdf"
    expected = "10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf"

    formatted = _format_pdf_path(abs_inside)
    assert formatted == expected
    assert "\\" not in formatted
    assert not Path(formatted).is_absolute()


def test_format_pdf_path_absolute_for_path_outside_repo(tmp_path: Path) -> None:
    """Format path outside config.BASE_DIR as absolute string."""
    # Closed-form identity: Path outside config.BASE_DIR raises ValueError on
    # relative_to(BASE_DIR), so str(Path(path).resolve()) is returned.
    outside_file = tmp_path / "external" / "sample.pdf"
    expected = str(outside_file.resolve())

    formatted = _format_pdf_path(outside_file)
    assert formatted == expected
    assert Path(formatted).is_absolute()


# ===========================================================================
# Unit tests: _resolve_pdf_path
# ===========================================================================


def test_resolve_pdf_path_resolves_relative_against_base_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Resolve relative path against config.BASE_DIR regardless of working directory."""
    # Closed-form identity: for relative path P, resolved path must equal (BASE_DIR / P).resolve().
    # Even if current working directory changes to tmp_path, resolved path must remain (BASE_DIR / P).resolve().
    rel_path = "10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf"
    expected = (config.BASE_DIR / rel_path).resolve()

    # In repository root
    assert _resolve_pdf_path(rel_path) == expected

    # In temporary directory (different cwd)
    monkeypatch.chdir(tmp_path)
    assert Path.cwd() == tmp_path.resolve()
    resolved_in_tmp = _resolve_pdf_path(rel_path)
    assert resolved_in_tmp == expected
    # Must NOT resolve against cwd
    assert resolved_in_tmp != (tmp_path / rel_path).resolve()


def test_resolve_pdf_path_preserves_absolute_path(tmp_path: Path) -> None:
    """Preserve recorded absolute path without modification."""
    # Closed-form identity: for absolute path P, _resolve_pdf_path(P) == Path(P).
    abs_path = (tmp_path / "filing.pdf").resolve()
    assert _resolve_pdf_path(str(abs_path)) == abs_path


# ===========================================================================
# Integration tests: cmd_plan (Criterion 1 & Criterion 2)
# ===========================================================================


def test_cmd_plan_writes_repo_relative_paths_for_repo_filings(tmp_path: Path) -> None:
    """`cmd_plan` writes repo-relative paths for PDFs inside the repository."""
    # Identity: Plan with two repository PDFs writes repo-relative posix paths.
    pdf_arg_2024 = f"2024:{WMT_PDF_REL_2024}"
    pdf_arg_2026 = f"2026:{WMT_PDF_REL_2026}"
    out_file = tmp_path / "plan_repo.json"

    ret = cmd_plan(
        [pdf_arg_2024, pdf_arg_2026],
        ticker="WMT",
        company_name="Walmart Inc.",
        output=out_file,
        force=True,
    )
    assert ret == 0

    data = json.loads(out_file.read_text(encoding="utf-8"))
    filings = data["filings"]
    # Hand arithmetic: 2 filings provided -> len(filings) == 2
    assert len(filings) == 2

    # Expected values derived from relative_to(BASE_DIR).as_posix()
    assert filings[0]["fiscal_year"] == 2024
    assert filings[0]["pdf_path"] == WMT_PDF_REL_2024
    assert not Path(filings[0]["pdf_path"]).is_absolute()
    assert "\\" not in filings[0]["pdf_path"]

    assert filings[1]["fiscal_year"] == 2026
    assert filings[1]["pdf_path"] == WMT_PDF_REL_2026
    assert not Path(filings[1]["pdf_path"]).is_absolute()
    assert "\\" not in filings[1]["pdf_path"]


def test_cmd_plan_writes_absolute_paths_for_external_filings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`cmd_plan` writes absolute paths for PDFs outside the repository."""
    # Identity: Plan with outside PDF writes str(pdf.resolve()).
    ext_pdf_2024 = tmp_path / "ext_2024.pdf"
    ext_pdf_2026 = tmp_path / "ext_2026.pdf"
    write_text_pdf(ext_pdf_2024, [["Walmart Inc. Fiscal 2024"]])
    write_text_pdf(ext_pdf_2026, [["Walmart Inc. Fiscal 2026"]])
    from tests.unit._fiscal_year_stub import stub_evidence_reader
    stub_evidence_reader(monkeypatch, {"ext_2024.pdf": 2024, "ext_2026.pdf": 2026})

    out_file = tmp_path / "plan_ext.json"
    ret = cmd_plan(
        [f"2024:{ext_pdf_2024}", f"2026:{ext_pdf_2026}"],
        ticker="WMT",
        company_name="Walmart Inc.",
        output=out_file,
        force=True,
    )
    assert ret == 0

    data = json.loads(out_file.read_text(encoding="utf-8"))
    filings = data["filings"]
    assert len(filings) == 2

    expected_2024 = str(ext_pdf_2024.resolve())
    expected_2026 = str(ext_pdf_2026.resolve())

    assert filings[0]["fiscal_year"] == 2024
    assert filings[0]["pdf_path"] == expected_2024
    assert Path(filings[0]["pdf_path"]).is_absolute()

    assert filings[1]["fiscal_year"] == 2026
    assert filings[1]["pdf_path"] == expected_2026
    assert Path(filings[1]["pdf_path"]).is_absolute()


# ===========================================================================
# Loader tests: load_session_extraction (Criterion 3, Criterion 4, Criterion 5)
# ===========================================================================


def test_load_session_extraction_loads_relative_paths_from_other_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`load_session_extraction` loads repo-relative paths when cwd is a temporary directory."""
    # Identity: Session file with repo-relative paths resolves against config.BASE_DIR,
    # so running with cwd changed to tmp_path loads all filings without error.
    monkeypatch.chdir(tmp_path)
    assert Path.cwd() == tmp_path.resolve()

    extraction = load_session_extraction(WMT_SESSION_PATH)
    # Hand calculation: Walmart session has 3 filings covering 5 historical years:
    # 2024 10-K gives 2022, 2023, 2024; 2025 10-K gives 2025; 2026 10-K gives 2026.
    # Total filings = 3, sorted years = [2022, 2023, 2024, 2025, 2026].
    assert len(extraction.filings) == 3
    assert extraction.financials.years == [2022, 2023, 2024, 2025, 2026]
    assert extraction.validation_errors == []


def test_load_session_extraction_loads_from_repo_root() -> None:
    """`load_session_extraction` loads repo-relative paths from the repository root."""
    # Identity: Running from repo root loads all 3 filings and 5 years cleanly.
    extraction = load_session_extraction(WMT_SESSION_PATH)
    assert len(extraction.filings) == 3
    assert extraction.financials.years == [2022, 2023, 2024, 2025, 2026]
    assert extraction.validation_errors == []


def test_load_session_extraction_loads_absolute_paths_when_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`load_session_extraction` loads absolute paths correctly when recorded."""
    # Identity: Replacing repo-relative paths with absolute paths yields the same
    # 3 filings and 5 financial statement years.
    raw_data: dict[str, Any] = json.loads(WMT_SESSION_PATH.read_text(encoding="utf-8"))
    for f in raw_data["filings"]:
        rel = f["pdf_path"]
        f["pdf_path"] = str((config.BASE_DIR / rel).resolve())

    session_copy = tmp_path / "WMT_absolute.json"
    session_copy.write_text(json.dumps(raw_data), encoding="utf-8")

    # Change directory to tmp_path to ensure independence of cwd
    monkeypatch.chdir(tmp_path)
    extraction = load_session_extraction(session_copy)
    assert len(extraction.filings) == 3
    assert extraction.financials.years == [2022, 2023, 2024, 2025, 2026]
    assert extraction.validation_errors == []


# ===========================================================================
# Missing PDF tests: Rule 3 (Criterion 6)
# ===========================================================================


def test_missing_pdf_relative_path_raises_naming_recorded_and_resolved_paths(
    tmp_path: Path,
) -> None:
    """When a relative PDF path does not exist on disk, ValueError names recorded and resolved paths."""
    raw_data: dict[str, Any] = json.loads(WMT_SESSION_PATH.read_text(encoding="utf-8"))
    fake_rel = "10K_filings/WMT/nonexistent_filing_missing_for_test.pdf"
    raw_data["filings"][0]["pdf_path"] = fake_rel

    session_copy = tmp_path / "WMT_missing_rel.json"
    session_copy.write_text(json.dumps(raw_data), encoding="utf-8")

    expected_resolved = str((config.BASE_DIR / fake_rel).resolve())
    expected_message = f"the PDF {fake_rel} (resolved to {expected_resolved}) is not on disk"

    with pytest.raises(ValueError) as exc_info:
        load_session_extraction(session_copy)

    err_text = str(exc_info.value)
    assert fake_rel in err_text
    assert expected_resolved in err_text
    assert expected_message in err_text


def test_missing_pdf_absolute_path_raises_naming_recorded_and_resolved_paths(
    tmp_path: Path,
) -> None:
    """When an absolute PDF path does not exist on disk, ValueError names recorded and resolved paths."""
    raw_data: dict[str, Any] = json.loads(WMT_SESSION_PATH.read_text(encoding="utf-8"))
    fake_abs = str((tmp_path / "nonexistent_abs_filing.pdf").resolve())
    raw_data["filings"][0]["pdf_path"] = fake_abs

    session_copy = tmp_path / "WMT_missing_abs.json"
    session_copy.write_text(json.dumps(raw_data), encoding="utf-8")

    expected_message = f"the PDF {fake_abs} (resolved to {fake_abs}) is not on disk"

    with pytest.raises(ValueError) as exc_info:
        load_session_extraction(session_copy)

    err_text = str(exc_info.value)
    assert fake_abs in err_text
    assert expected_message in err_text


# ===========================================================================
# Rule 3 Stop tests: absent, empty, or non-string pdf_path
# ===========================================================================


def test_rule3_missing_pdf_path_key_stops_and_names_field(tmp_path: Path) -> None:
    """When 'pdf_path' key is absent, loader stops and names key 'pdf_path'."""
    raw_data: dict[str, Any] = json.loads(WMT_SESSION_PATH.read_text(encoding="utf-8"))
    del raw_data["filings"][0]["pdf_path"]

    session_copy = tmp_path / "WMT_no_key.json"
    session_copy.write_text(json.dumps(raw_data), encoding="utf-8")

    with pytest.raises(ValueError, match="key 'pdf_path' is absent"):
        load_session_extraction(session_copy)


def test_rule3_empty_pdf_path_stops_and_names_field(tmp_path: Path) -> None:
    """When 'pdf_path' is an empty string, loader stops and names 'pdf_path'."""
    raw_data: dict[str, Any] = json.loads(WMT_SESSION_PATH.read_text(encoding="utf-8"))
    raw_data["filings"][0]["pdf_path"] = ""

    session_copy = tmp_path / "WMT_empty_path.json"
    session_copy.write_text(json.dumps(raw_data), encoding="utf-8")

    with pytest.raises(ValueError, match="'pdf_path' must be a non-empty string"):
        load_session_extraction(session_copy)


def test_rule3_non_string_pdf_path_stops_and_names_field(tmp_path: Path) -> None:
    """When 'pdf_path' is not a string, loader stops and names 'pdf_path'."""
    raw_data: dict[str, Any] = json.loads(WMT_SESSION_PATH.read_text(encoding="utf-8"))
    raw_data["filings"][0]["pdf_path"] = 12345

    session_copy = tmp_path / "WMT_int_path.json"
    session_copy.write_text(json.dumps(raw_data), encoding="utf-8")

    with pytest.raises(ValueError, match="'pdf_path' must be a non-empty string"):
        load_session_extraction(session_copy)
