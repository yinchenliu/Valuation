"""Tests for P14b Route A reasoning settings, ProviderResolution reasoning_label,
and item 81 fix in _pass2_item_failures.

Verifies:
1. _call_claude streaming request parameters and stream handling:
   - Request sends thinking={"type": "adaptive"}, output_config={"effort": config.EXTRACTION_EFFORT},
     max_tokens=64000 (_CLAUDE_MAX_TOKENS).
   - Forbidden parameters (temperature, top_p, top_k, budget_tokens) are never sent.
   - Response handling extracts text blocks only; thinking blocks are never read or returned.
   - Multiple text blocks are joined with newline.
   - Stop: ValueError naming missing text block when response has no text blocks.
   - Stop: ValueError naming 64,000-token ceiling when stop_reason == "max_tokens".
2. ProviderResolution reasoning_label and describe_resolution:
   - Route A Claude (public API and Foundry): "adaptive thinking, effort 'high' (config.EXTRACTION_EFFORT)".
   - Route A Gemini: "the provider's default; this code sets no thinking for Gemini".
   - Route B Claude Code session: "as the Claude Code session ran; not set by this code".
   - describe_resolution outputs "Reasoning: <label>" directly following "Model: <model>".
   - Stop: ProviderResolution dataclass constructor raises TypeError when reasoning_label is missing (no default).
3. Item 81 fix in _pass2_item_failures:
   - Pass 2 item failure counts are tracked per item directly (item_failed boolean).
   - An item whose description is a substring or prefix of another item's description does not corrupt counts.
   - Summary counts: e.g. 4 checked with 1 failing produces "4 checked, 3 found, 1 not confirmed".
   - An item with multiple check failures is counted as 1 not confirmed.

All expected values derived by hand arithmetic or closed-form identity.
No paid API calls or real network calls are made.
"""

from __future__ import annotations

import base64
import types
from pathlib import Path
from typing import Any, Self

import pytest

import config
import ingestion.claude_extractor as ce
from ingestion.claude_extractor import (
    _CLAUDE_MAX_TOKENS,
    ProviderResolution,
    _call_claude,
    _pass2_item_failures,
    describe_resolution,
    resolve_provider,
)
from ingestion.session_extraction import session_resolution
from models.financial_statements import NonRecurringItem
from tests.unit._text_pdf import write_text_pdf

# ===========================================================================
# Helpers & Mocks for _call_claude
# ===========================================================================


class MockContentBlock:
    """Mock Anthropic content block."""

    def __init__(self, block_type: str, text: str = "") -> None:
        self.type = block_type
        self.text = text


class MockUsage:
    """Mock Anthropic token usage."""

    def __init__(self, input_tokens: int = 120, output_tokens: int = 45) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class MockFinalMessage:
    """Mock final message returned by stream.get_final_message()."""

    def __init__(
        self,
        content: list[MockContentBlock],
        stop_reason: str = "end_turn",
        usage: MockUsage | None = None,
    ) -> None:
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage or MockUsage()


class MockStreamContext:
    """Context manager returned by client.messages.stream(...)."""

    def __init__(self, final_message: MockFinalMessage) -> None:
        self._final_message = final_message

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        pass

    def get_final_message(self) -> MockFinalMessage:
        return self._final_message


class MockMessages:
    """Mock client.messages implementing stream(...)."""

    def __init__(self, final_message: MockFinalMessage) -> None:
        self.final_message = final_message
        self.stream_calls: list[dict[str, Any]] = []

    def stream(self, **kwargs: Any) -> MockStreamContext:
        self.stream_calls.append(kwargs)
        return MockStreamContext(self.final_message)


class MockClaudeClient:
    """Mock Anthropic client."""

    def __init__(self, final_message: MockFinalMessage) -> None:
        self.messages = MockMessages(final_message)


def _make_claude_resolution() -> ProviderResolution:
    """ProviderResolution fixture for Claude."""
    return ProviderResolution(
        provider="claude",
        model="claude-opus-5",
        reasoning_label=f"adaptive thinking, effort {config.EXTRACTION_EFFORT!r} (config.EXTRACTION_EFFORT)",
        transport="anthropic-direct",
        transport_label="Anthropic public API (api.anthropic.com)",
        credential="anthropic-api-key",
        credential_source="stub",
    )


# ===========================================================================
# 1. _call_claude request parameters and stream handling
# ===========================================================================


def test_call_claude_sends_adaptive_thinking_effort_and_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that _call_claude streams with adaptive thinking, EXTRACTION_EFFORT, and 64000 tokens."""
    resolution = _make_claude_resolution()
    final_msg = MockFinalMessage([MockContentBlock("text", '{"revenue": 1000}')])
    mock_client = MockClaudeClient(final_msg)

    monkeypatch.setattr(ce, "_build_claude_client", lambda res: mock_client)

    system_prompt = "You are an extractor."
    user_prompt = "Extract revenue."
    text, in_tok, out_tok = _call_claude(system_prompt, user_prompt, resolution)

    assert len(mock_client.messages.stream_calls) == 1
    call_kwargs = mock_client.messages.stream_calls[0]

    # Hand-verified parameter assertions:
    # 1. Model matches resolution.model
    assert call_kwargs["model"] == "claude-opus-5"
    # 2. max_tokens is exactly 64,000 (_CLAUDE_MAX_TOKENS)
    assert call_kwargs["max_tokens"] == 64000
    assert call_kwargs["max_tokens"] == _CLAUDE_MAX_TOKENS
    # 3. thinking is adaptive
    assert call_kwargs["thinking"] == {"type": "adaptive"}
    # 4. output_config carries effort from config.EXTRACTION_EFFORT ('high')
    assert call_kwargs["output_config"] == {"effort": "high"}
    assert call_kwargs["output_config"] == {"effort": config.EXTRACTION_EFFORT}
    # 5. Prompts passed correctly
    assert call_kwargs["system"] == system_prompt
    assert call_kwargs["messages"] == [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}]

    # Return value matches text block and usage
    assert text == '{"revenue": 1000}'
    assert in_tok == 120
    assert out_tok == 45


def test_call_claude_sends_no_forbidden_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that _call_claude does not send temperature, top_p, top_k, or budget_tokens."""
    resolution = _make_claude_resolution()
    final_msg = MockFinalMessage([MockContentBlock("text", '{"ok": true}')])
    mock_client = MockClaudeClient(final_msg)

    monkeypatch.setattr(ce, "_build_claude_client", lambda res: mock_client)

    _call_claude("sys", "usr", resolution)

    call_kwargs = mock_client.messages.stream_calls[0]
    forbidden_params = ("temperature", "top_p", "top_k", "budget_tokens")
    for param in forbidden_params:
        assert param not in call_kwargs, f"Forbidden parameter {param!r} was sent in request"


def test_call_claude_encodes_pdf_document_in_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that _call_claude embeds pdf_bytes as a document block before user prompt."""
    resolution = _make_claude_resolution()
    final_msg = MockFinalMessage([MockContentBlock("text", '{"ok": true}')])
    mock_client = MockClaudeClient(final_msg)

    monkeypatch.setattr(ce, "_build_claude_client", lambda res: mock_client)

    sample_pdf = b"%PDF-1.4 sample content"
    expected_b64 = base64.standard_b64encode(sample_pdf).decode("utf-8")

    _call_claude("sys", "usr", resolution, pdf_bytes=sample_pdf)

    call_kwargs = mock_client.messages.stream_calls[0]
    content = call_kwargs["messages"][0]["content"]

    assert len(content) == 2
    # First block is the PDF document
    assert content[0] == {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": expected_b64,
        },
    }
    # Second block is the user prompt
    assert content[1] == {"type": "text", "text": "usr"}


def test_call_claude_never_reads_or_returns_thinking_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that thinking blocks are skipped and never leak into the returned text."""
    resolution = _make_claude_resolution()
    secret_thinking = "CONFIDENTIAL_INTERNAL_REASONING_CHAIN_12345"
    final_msg = MockFinalMessage([
        MockContentBlock("thinking", secret_thinking),
        MockContentBlock("text", '{"revenue": 5000}'),
    ])
    mock_client = MockClaudeClient(final_msg)

    monkeypatch.setattr(ce, "_build_claude_client", lambda res: mock_client)

    text, in_tok, out_tok = _call_claude("sys", "usr", resolution)

    # Secret thinking must never be returned
    assert secret_thinking not in text
    # Only text block content is returned
    assert text == '{"revenue": 5000}'
    assert in_tok == 120
    assert out_tok == 45


def test_call_claude_joins_multiple_text_blocks_with_newline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that multiple text blocks are joined with a newline and thinking blocks ignored."""
    resolution = _make_claude_resolution()
    final_msg = MockFinalMessage([
        MockContentBlock("thinking", "thought A"),
        MockContentBlock("text", '{"part1": 1}'),
        MockContentBlock("thinking", "thought B"),
        MockContentBlock("text", '{"part2": 2}'),
    ])
    mock_client = MockClaudeClient(final_msg)

    monkeypatch.setattr(ce, "_build_claude_client", lambda res: mock_client)

    text, _, _ = _call_claude("sys", "usr", resolution)

    # Hand-derived concatenation: '{"part1": 1}' + '\n' + '{"part2": 2}'
    assert text == '{"part1": 1}\n{"part2": 2}'
    assert "thought A" not in text
    assert "thought B" not in text


def test_call_claude_stops_when_no_text_block_in_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rule 3 stop: ValueError when model returns only thinking blocks or no text blocks."""
    resolution = _make_claude_resolution()
    # Response contains thinking block only, no text block
    final_msg = MockFinalMessage([MockContentBlock("thinking", "Only thoughts here")])
    mock_client = MockClaudeClient(final_msg)

    monkeypatch.setattr(ce, "_build_claude_client", lambda res: mock_client)

    with pytest.raises(ValueError) as exc_info:
        _call_claude("sys", "usr", resolution)

    msg = str(exc_info.value)
    # Names the model, names missing text block, names block types received
    assert "claude-opus-5" in msg
    assert "returned no text block, so there is nothing to parse" in msg
    assert "Block types received: thinking." in msg


def test_call_claude_stops_when_response_content_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rule 3 stop: ValueError when model returns empty content list."""
    resolution = _make_claude_resolution()
    final_msg = MockFinalMessage([])
    mock_client = MockClaudeClient(final_msg)

    monkeypatch.setattr(ce, "_build_claude_client", lambda res: mock_client)

    with pytest.raises(ValueError) as exc_info:
        _call_claude("sys", "usr", resolution)

    msg = str(exc_info.value)
    assert "claude-opus-5" in msg
    assert "Block types received: none at all." in msg


def test_call_claude_stops_when_hit_max_tokens_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rule 3 stop: ValueError when model hits the 64,000-token ceiling before finishing."""
    resolution = _make_claude_resolution()
    final_msg = MockFinalMessage(
        content=[MockContentBlock("text", '{"partial_json":')],
        stop_reason="max_tokens",
    )
    mock_client = MockClaudeClient(final_msg)

    monkeypatch.setattr(ce, "_build_claude_client", lambda res: mock_client)

    with pytest.raises(ValueError) as exc_info:
        _call_claude("sys", "usr", resolution)

    msg = str(exc_info.value)
    # Names the model, names 64,000-token ceiling, names remedy
    assert "claude-opus-5" in msg
    assert "hit the 64,000-token output ceiling before finishing its response" in msg
    assert "Re-run against fewer target years, or raise max_tokens in _call_claude." in msg


# ===========================================================================
# 2. reasoning_label and describe_resolution
# ===========================================================================


def test_claude_route_a_direct_reasoning_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route A Claude direct: reasoning_label reflects adaptive thinking and config.EXTRACTION_EFFORT."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-direct-key-12345")
    monkeypatch.delenv("ANTHROPIC_FOUNDRY_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_FOUNDRY_API_KEY", raising=False)

    resolution = resolve_provider("claude", "claude-opus-5")

    expected_label = f"adaptive thinking, effort {config.EXTRACTION_EFFORT!r} (config.EXTRACTION_EFFORT)"
    # Closed-form hand expectation: config.EXTRACTION_EFFORT is 'high'
    assert expected_label == "adaptive thinking, effort 'high' (config.EXTRACTION_EFFORT)"
    assert resolution.reasoning_label == expected_label

    line = describe_resolution(resolution)
    assert "Model: claude-opus-5  |  Reasoning: adaptive thinking, effort 'high' (config.EXTRACTION_EFFORT)  |  Transport:" in line


def test_claude_route_a_foundry_api_key_reasoning_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route A Claude Foundry with key: reasoning_label reflects adaptive thinking and effort."""
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_BASE_URL", "https://example.foundry.azure.com")
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_API_KEY", "foundry-test-api-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    resolution = resolve_provider("claude", "claude-opus-5")

    expected_label = f"adaptive thinking, effort {config.EXTRACTION_EFFORT!r} (config.EXTRACTION_EFFORT)"
    assert resolution.reasoning_label == expected_label
    assert resolution.transport == "foundry"

    line = describe_resolution(resolution)
    assert f"Model: claude-opus-5  |  Reasoning: {expected_label}  |  Transport:" in line


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
            transport="anthropic-direct",  # type: ignore[arg-type]
            transport_label="stub-transport",
            credential="anthropic-api-key",  # type: ignore[arg-type]
            credential_source="stub-source",
        )
        line = describe_resolution(res)
        expected_substring = f"Model: {model}  |  Reasoning: {label}  |  Transport:"
        assert expected_substring in line


def test_provider_resolution_requires_reasoning_label_no_default() -> None:
    """Rule 3 stop: ProviderResolution dataclass has no default for reasoning_label."""
    with pytest.raises(TypeError) as exc_info:
        ProviderResolution(  # type: ignore[call-arg]
            provider="claude",
            model="claude-opus-5",
            transport="anthropic-direct",
            transport_label="stub",
            credential="anthropic-api-key",
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
