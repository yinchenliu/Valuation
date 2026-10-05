"""Global pytest fixtures for the test suite."""

import pytest


@pytest.fixture(autouse=True)
def isolate_environment_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure every test runs with empty API keys by default.

    No test can read a live API key from .env or the host environment.
    A test that needs a key sets a placeholder itself.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
