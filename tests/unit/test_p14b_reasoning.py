"""Tests for P14b reasoning settings, ProviderResolution reasoning_label,
and item 81 fix in _pass2_item_failures.

Verifies:
1. ProviderResolution reasoning_label and describe_resolution:
   - Route A Gemini: "the provider's default; this code sets no thinking for Gemini".
   - Route B Claude Code session: "as the Claude Code session ran; not set by this code".
   - describe_resolution outputs "Reasoning: <label>" directly following "Model: <model>".
   - Stop: ProviderResolution dataclass constructor raises TypeError when reasoning_label is missing (no default).
2. Item 81 fix in _pass2_item_failures:
   - Pass 2 item failure counts are tracked per item directly (item_failed boolean).
   - An item whose description is a substring or prefix of another item's description does not corrupt counts.
   - Summary counts: e.g. 4 checked with 1 failing produces "4 checked, 3 found, 1 not confirmed".
   - An item with multiple check failures is counted as 1 not confirmed.

All expected values derived by hand arithmetic or closed-form identity.
No paid API calls or real network calls are made.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.claude_extractor import (
    ProviderResolution,
    _pass2_item_failures,
    describe_resolution,
    resolve_provider,
)
from ingestion.session_extraction import session_resolution
from models.financial_statements import NonRecurringItem
from tests.unit._text_pdf import write_text_pdf

# ===========================================================================
# 1. reasoning_label and describe_resolution
# ===========================================================================


def test_gemini_route_a_reasoning_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route A Gemini: reasoning_label states provider default and no thinking configured."""
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key-67890")

    resolution = resolve_provider("gemini", "gemini-3.1-pro-preview")

    expected_label = "the provider's default; this code sets no thinking for Gemini"
    assert resolution.reasoning_label == expected_label
    assert resolution.provider == "gemini"

    line = describe_resolution(resolution)
    assert f"Model: gemini-3.1-pro-preview  |  Reasoning: {expected_label}  |  Transport:" in line


def test_route_b_session_resolution_reasoning_label() -> None:
    """Route B: reasoning_label states session ran without code setting thinking."""
    session_file = Path("extractions/WMT.json")
    resolution = session_resolution("claude-opus-5", session_file)

    expected_label = "as the Claude Code session ran; not set by this code"
    assert resolution.reasoning_label == expected_label
    assert resolution.transport == "claude-code-session"

    line = describe_resolution(resolution)
    assert f"Model: claude-opus-5  |  Reasoning: {expected_label}  |  Transport:" in line


def test_describe_resolution_places_reasoning_directly_following_model() -> None:
    """Test that describe_resolution places Reasoning: <label> directly following Model: <model>."""
    for provider, model, label in [
        ("claude", "claude-opus-5", "adaptive thinking, effort 'high' (config.EXTRACTION_EFFORT)"),
        ("gemini", "gemini-3.1-pro-preview", "the provider's default; this code sets no thinking for Gemini"),
        ("claude", "custom-model", "as the Claude Code session ran; not set by this code"),
    ]:
        res = ProviderResolution(
            provider=provider,  # type: ignore[arg-type]
            model=model,
            reasoning_label=label,
            transport="gemini-direct" if provider == "gemini" else "claude-code-session",
            transport_label="stub-transport",
            credential="gemini-api-key" if provider == "gemini" else "claude-code-session",
            credential_source="stub-source",
        )
        line = describe_resolution(res)
        expected_substring = f"Model: {model}  |  Reasoning: {label}  |  Transport:"
        assert expected_substring in line


def test_provider_resolution_requires_reasoning_label_no_default() -> None:
    """Rule 3 stop: ProviderResolution dataclass has no default for reasoning_label."""
    with pytest.raises(TypeError) as exc_info:
        ProviderResolution(  # type: ignore[call-arg]
            provider="gemini",
            model="gemini-3.1-pro-preview",
            transport="gemini-direct",
            transport_label="stub",
            credential="gemini-api-key",
            credential_source="stub",
        )
    assert "reasoning_label" in str(exc_info.value)


# ===========================================================================
# 3. Item 81 fix in _pass2_item_failures
# ===========================================================================


def _build_test_pdf_bytes(tmp_path: Path, lines_page1: list[str]) -> bytes:
    """Create a 1-page test PDF with the specified text lines."""
    pdf_path = tmp_path / "test_item81.pdf"
    write_text_pdf(pdf_path, [lines_page1])
    return pdf_path.read_bytes()


def _make_nri(
    description: str,
    amount: float,
    page: int = 1,
    printed_units: str = "(Amounts in millions)",
    units_page: int = 1,
) -> NonRecurringItem:
    """Helper creating a valid NonRecurringItem for test assertions."""
    return NonRecurringItem(
        year=2024,
        description=description,
        amount=amount,
        line_item="sga",
        direction="add_back",
        category="restructuring",
        confidence="high",
        page=page,
        printed_units=printed_units,
        units_page=units_page,
    )


def test_pass2_item_failures_tracking_clean_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Item 81 clean: 4 items checked, 4 found, 0 not confirmed."""
    # Hand derivation: 4 items, 0 check failures -> 4 - 0 = 4 found, 0 not confirmed
    pdf_bytes = _build_test_pdf_bytes(
        tmp_path,
        [
            "(Amounts in millions)",
            "Restructuring 100",
            "Restructuring charges 200",
            "Asset impairment 300",
            "Asset impairment charges 400",
        ],
    )

    items = [
        _make_nri("Restructuring", 100.0),
        _make_nri("Restructuring charges", 200.0),
        _make_nri("Asset impairment", 300.0),
        _make_nri("Asset impairment charges", 400.0),
    ]

    failures = _pass2_item_failures(items, pdf_bytes)
    assert failures == []

    captured = capsys.readouterr()
    assert "Pass 2 items looked up on their cited pages: 4 checked, 4 found, 0 not confirmed." in captured.out


def test_pass2_item_failures_prefix_item_fails_substring_does_not_corrupt_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Item 81 bug lock: Item A ('Restructuring') fails, Item B ('Restructuring charges') passes.

    Under the old substring-matching bug, checking if Item A failed could collide with Item B.
    With direct per-item tracking (item_failed boolean), exactly 1 item fails:
    Hand derivation: 4 checked, 1 failing -> 4 - 1 = 3 found, 1 not confirmed.
    """
    pdf_bytes = _build_test_pdf_bytes(
        tmp_path,
        [
            "(Amounts in millions)",
            # 100 is absent!
            "Restructuring charges 200",
            "Asset impairment 300",
            "Asset impairment charges 400",
        ],
    )

    items = [
        # Item A: amount 100.0 is not on page 1 -> FAILS
        _make_nri("Restructuring", 100.0),
        # Item B: description contains 'Restructuring', amount 200.0 is on page 1 -> PASSES
        _make_nri("Restructuring charges", 200.0),
        # Item C: amount 300.0 is on page 1 -> PASSES
        _make_nri("Asset impairment", 300.0),
        # Item D: amount 400.0 is on page 1 -> PASSES
        _make_nri("Asset impairment charges", 400.0),
    ]

    failures = _pass2_item_failures(items, pdf_bytes)
    assert len(failures) == 1
    assert "non-recurring item (2024, 'Restructuring'): amount 100.0 was not found on page 1" in failures[0].message

    captured = capsys.readouterr()
    # Hand calculation: 4 checked - 1 failed = 3 found, 1 not confirmed
    assert "Pass 2 items looked up on their cited pages: 4 checked, 3 found, 1 not confirmed." in captured.out


def test_pass2_item_failures_superstring_item_fails_substring_does_not_corrupt_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Item 81 bug lock: Item B ('Restructuring charges') fails, Item A ('Restructuring') passes.

    Hand derivation: 4 checked, 1 failing -> 4 - 1 = 3 found, 1 not confirmed.
    """
    pdf_bytes = _build_test_pdf_bytes(
        tmp_path,
        [
            "(Amounts in millions)",
            "Restructuring 100",
            # 200 is absent!
            "Asset impairment 300",
            "Asset impairment charges 400",
        ],
    )

    items = [
        # Item A: amount 100.0 is on page 1 -> PASSES
        _make_nri("Restructuring", 100.0),
        # Item B: amount 200.0 is absent -> FAILS
        _make_nri("Restructuring charges", 200.0),
        # Item C: amount 300.0 is on page 1 -> PASSES
        _make_nri("Asset impairment", 300.0),
        # Item D: amount 400.0 is on page 1 -> PASSES
        _make_nri("Asset impairment charges", 400.0),
    ]

    failures = _pass2_item_failures(items, pdf_bytes)
    assert len(failures) == 1
    assert "non-recurring item (2024, 'Restructuring charges'): amount 200.0 was not found on page 1" in failures[0].message

    captured = capsys.readouterr()
    assert "Pass 2 items looked up on their cited pages: 4 checked, 3 found, 1 not confirmed." in captured.out


def test_pass2_item_failures_multiple_failing_items_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Item 81: 2 items fail out of 4 -> 4 checked, 2 found, 2 not confirmed."""
    # Hand derivation: 4 checked, 2 failing -> 4 - 2 = 2 found, 2 not confirmed
    pdf_bytes = _build_test_pdf_bytes(
        tmp_path,
        [
            "(Amounts in millions)",
            # 100 is absent -> Item A fails
            "Restructuring charges 200",  # Item B passes
            # 300 is absent -> Item C fails
            "Asset impairment charges 400",  # Item D passes
        ],
    )

    items = [
        _make_nri("Restructuring", 100.0),
        _make_nri("Restructuring charges", 200.0),
        _make_nri("Asset impairment", 300.0),
        _make_nri("Asset impairment charges", 400.0),
    ]

    failures = _pass2_item_failures(items, pdf_bytes)
    assert len(failures) == 2

    captured = capsys.readouterr()
    assert "Pass 2 items looked up on their cited pages: 4 checked, 2 found, 2 not confirmed." in captured.out


def test_pass2_item_failures_all_items_fail_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Item 81: all 4 items fail -> 4 checked, 0 found, 4 not confirmed."""
    # Hand derivation: 4 checked, 4 failing -> 4 - 4 = 0 found, 4 not confirmed
    pdf_bytes = _build_test_pdf_bytes(tmp_path, ["(Amounts in millions)"])

    items = [
        _make_nri("Restructuring", 100.0),
        _make_nri("Restructuring charges", 200.0),
        _make_nri("Asset impairment", 300.0),
        _make_nri("Asset impairment charges", 400.0),
    ]

    failures = _pass2_item_failures(items, pdf_bytes)
    assert len(failures) == 4

    captured = capsys.readouterr()
    assert "Pass 2 items looked up on their cited pages: 4 checked, 0 found, 4 not confirmed." in captured.out


def test_pass2_item_failures_single_item_multiple_failures_counted_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Item 81: An item with both figure and unit failures increments not_confirmed_count only once.

    Hand derivation: 1 item checked, 1 item failed -> 1 - 1 = 0 found, 1 not confirmed.
    Even though len(failures) == 2 (two check failure messages for this one item).
    """
    # 1-page PDF
    pdf_bytes = _build_test_pdf_bytes(tmp_path, ["(Amounts in millions)"])

    # Item cites page 99 for figure and page 99 for units, when PDF has 1 page
    item = _make_nri("Restructuring", 100.0, page=99, units_page=99)

    failures = _pass2_item_failures([item], pdf_bytes)
    # Hand derivation: 2 failures appended for this item (amount page beyond, units page beyond)
    assert len(failures) == 2
    assert "amount 100.0 cites page 99, but the PDF has 1 pages" in failures[0].message
    assert "units '(Amounts in millions)' cites page 99, but the PDF has 1 pages" in failures[1].message

    captured = capsys.readouterr()
    # not_confirmed_count must be 1, NOT 2!
    assert "Pass 2 items looked up on their cited pages: 1 checked, 0 found, 1 not confirmed." in captured.out
