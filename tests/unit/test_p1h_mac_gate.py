"""Tests verifying stream-handler stop names the stream class on Python 3.11.

Rule 3 and Rule 4 require stops to name their inputs explicitly.
On Python 3.11, io.TextIOWrapper representation omits custom subclass names.
The stop message must include type(stream).__name__ directly.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from ingestion.session_extraction import naming_unencodable_characters


class StreamWithNoneErrors(io.TextIOWrapper):
    """Subclass with None errors property."""

    def __init__(self) -> None:
        super().__init__(io.BytesIO(), encoding="utf-8")
        self.reconfigured_calls: list[dict[str, Any]] = []

    @property
    def errors(self) -> None:  # type: ignore[override]
        return None

    def reconfigure(self, **kwargs: Any) -> None:
        self.reconfigured_calls.append(kwargs)


class StreamWithIntegerErrors(io.TextIOWrapper):
    """Subclass with integer errors property."""

    def __init__(self) -> None:
        super().__init__(io.BytesIO(), encoding="utf-8")
        self.reconfigured_calls: list[dict[str, Any]] = []

    @property
    def errors(self) -> int:  # type: ignore[override]
        return 42

    def reconfigure(self, **kwargs: Any) -> None:
        self.reconfigured_calls.append(kwargs)


class CustomTelemetryTextStream(io.TextIOWrapper):
    """Subclass with custom name to verify exact class name formatting."""

    def __init__(self) -> None:
        super().__init__(io.BytesIO(), encoding="utf-8")

    @property
    def errors(self) -> None:  # type: ignore[override]
        return None


def test_subclass_with_none_errors_names_subclass_in_typeerror() -> None:
    """Verify stop names subclass name when errors is None.

    Expected values derived by hand from string format specification:
    - Exception type: TypeError (not ValueError).
    - Exception message contains 'StreamWithNoneErrors'.
    - Exception message contains 'error handler reads as None'.
    """
    stream = StreamWithNoneErrors()

    with pytest.raises(TypeError) as exc_info, naming_unencodable_characters(stream):
        pytest.fail("The context block must not execute when errors is None")

    assert not isinstance(exc_info.value, ValueError)
    message = str(exc_info.value)

    # Hand-derived expected substrings:
    # 1. Target field name
    assert "error handler" in message
    # 2. Value read from stream
    assert "reads as None" in message
    # 3. Stream subclass name must be named explicitly
    assert "StreamWithNoneErrors" in message
    # 4. Stream repr must follow stream subclass name
    expected_stream_prefix = f"Stream: StreamWithNoneErrors {stream!r}"
    assert expected_stream_prefix in message
    # 5. Stream was not reconfigured before stop
    assert stream.reconfigured_calls == []


def test_subclass_with_integer_errors_names_subclass_in_typeerror() -> None:
    """Verify stop names subclass name when errors is an integer.

    Expected values derived by hand:
    - Exception type: TypeError.
    - Message contains 'StreamWithIntegerErrors'.
    - Message contains 'reads as 42'.
    """
    stream = StreamWithIntegerErrors()

    with pytest.raises(TypeError) as exc_info, naming_unencodable_characters(stream):
        pytest.fail("The context block must not execute when errors is an integer")

    assert not isinstance(exc_info.value, ValueError)
    message = str(exc_info.value)

    # Hand-derived expected substrings:
    assert "error handler" in message
    assert "reads as 42" in message
    assert "StreamWithIntegerErrors" in message
    expected_stream_prefix = f"Stream: StreamWithIntegerErrors {stream!r}"
    assert expected_stream_prefix in message
    assert stream.reconfigured_calls == []


def test_distinct_subclass_name_is_reported_verbatim() -> None:
    """Verify different subclass names appear verbatim in the stop message.

    Expected values derived by hand:
    - Subclass name 'CustomTelemetryTextStream' is included verbatim.
    - String prefix 'Stream: CustomTelemetryTextStream' matches format.
    """
    stream = CustomTelemetryTextStream()

    with pytest.raises(TypeError) as exc_info, naming_unencodable_characters(stream):
        pytest.fail("The context block must not execute")

    message = str(exc_info.value)
    assert "CustomTelemetryTextStream" in message
    expected_stream_prefix = f"Stream: CustomTelemetryTextStream {stream!r}"
    assert expected_stream_prefix in message
