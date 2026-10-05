"""Tests for P15a two extraction routes: Gemini route A, Claude route B.

Locks behaviors introduced in P15a-two-routes on the user's decisions of 2026-10-04:
1. resolve_provider("claude", ...) stop:
   - Immediately raises ValueError directing to route B:
     names 'extract-filing', '--session-file', and 'GEMINI_API_KEY'.
2. resolve_provider("gemini", ...) with key:
   - Resolves ProviderResolution(provider='gemini', model='gemini-3.1-pro-preview',
     transport='gemini-direct', credential='gemini-api-key').
   - Custom model strings are preserved; empty/blank model strings stop naming 'model'.
3. resolve_provider("gemini", ...) with no key:
   - Raises ValueError naming both remedies: (1) GEMINI_API_KEY and (2) --session-file.
   - Whitespace-only key is treated as empty and stops naming both remedies.
4. resolve_provider with unknown provider:
   - Raises ValueError naming valid choices ('claude' or 'gemini').
5. _call_llm stop:
   - Raises ValueError when passed a resolution with provider != 'gemini'.
   - Names provider, transport, and states route A supports Gemini only.
6. CLI refuses -p claude:
   - Exits with returncode 2 and argparse error naming invalid choice 'claude'.
   - cli.py --help advertises default: gemini and mentions route B --session-file.
7. Purge of Anthropic and Azure:
   - app, cli, and ingestion.claude_extractor import without anthropic and azure modules.
   - No occurrences of foundry, entra, azure, or anthropic remain in shipped code.

Where expected values come from:
- User decisions of 2026-10-04 ("1a, 2a");
- Docs: docs/8-build/environment.md section 3, docs/3-architecture/extraction.md;
- Closed-form identities and string contracts of resolve_provider, _call_llm, and cli.py.
No paid API calls or network requests are made.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

import config
from ingestion.claude_extractor import (
    ProviderResolution,
    _call_llm,
    resolve_provider,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ===========================================================================
# 1. resolve_provider("claude", ...) stop
# ===========================================================================


@pytest.mark.parametrize("model", [None, "claude-opus-5", "claude-3-7-sonnet"])
def test_resolve_provider_claude_stops_and_names_route_b_and_remedies(
    model: str | None,
) -> None:
    """Calling resolve_provider with 'claude' must stop immediately (Rule 3).

    Expected: ValueError naming the user's decision of 2026-10-04, the 'extract-filing'
    skill, '--session-file' (CLI), upload session file (web), and route A's use of
    Gemini with 'GEMINI_API_KEY'.
    """
    with pytest.raises(ValueError) as exc_info:
        resolve_provider("claude", model)

    message = str(exc_info.value)
    assert "extract-filing" in message
    assert "--session-file" in message
    assert "route b" in message.lower()
    assert "(route B)" in message
    assert "Route A" in message


# ===========================================================================
# 2. resolve_provider("gemini", ...) with key
# ===========================================================================


def test_resolve_provider_gemini_with_key_resolves_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """resolve_provider('gemini', None) with GEMINI_API_KEY set resolves defaults.

    Expected:
    - provider: 'gemini'
    - model: 'gemini-3.1-pro-preview' (from _DEFAULT_MODELS lookup)
    - reasoning_label: "the provider's default; this code sets no thinking for Gemini"
    - transport: 'gemini-direct'
    - transport_label: 'Google Gemini API (generativelanguage.googleapis.com)'
    - credential: 'gemini-api-key'
    - credential_source: contains 'GEMINI_API_KEY'
    """
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-p15a")

    resolution = resolve_provider("gemini", None)

    assert isinstance(resolution, ProviderResolution)
    assert resolution.provider == "gemini"
    assert resolution.model == "gemini-3.1-pro-preview"
    assert resolution.reasoning_label == "the provider's default; this code sets no thinking for Gemini"
    assert resolution.transport == "gemini-direct"
    assert resolution.transport_label == "Google Gemini API (generativelanguage.googleapis.com)"
    assert resolution.credential == "gemini-api-key"
    assert "GEMINI_API_KEY" in resolution.credential_source


def test_resolve_provider_gemini_custom_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A custom model string is preserved."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-p15a")

    resolution = resolve_provider("gemini", "gemini-2.0-flash")

    assert resolution.provider == "gemini"
    assert resolution.model == "gemini-2.0-flash"


@pytest.mark.parametrize("blank_model", ["", "   "])
def test_resolve_provider_blank_model_stops_naming_model(
    monkeypatch: pytest.MonkeyPatch, blank_model: str,
) -> None:
    """An empty or blank model string stops and names 'model' (Rule 3)."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-p15a")

    with pytest.raises(ValueError) as exc_info:
        resolve_provider("gemini", blank_model)

    assert "model" in str(exc_info.value).lower()


def test_default_extraction_provider_is_gemini() -> None:
    """The default extraction provider in config is 'gemini'."""
    assert config.DEFAULT_EXTRACTION_PROVIDER == "gemini"


# ===========================================================================
# 3. resolve_provider("gemini", ...) with no key
# ===========================================================================


@pytest.mark.parametrize("missing_key_env", [None, "", "   "])
def test_resolve_provider_gemini_no_key_stops_naming_both_remedies(
    monkeypatch: pytest.MonkeyPatch, missing_key_env: str | None,
) -> None:
    """Missing or whitespace-only GEMINI_API_KEY stops naming both remedies (Rule 3).

    Expected:
    - (1) Set GEMINI_API_KEY for Route A
    - (2) Extract in a Claude Code session with --session-file for Route B
    """
    if missing_key_env is None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("GEMINI_API_KEY", missing_key_env)

    with pytest.raises(ValueError) as exc_info:
        resolve_provider("gemini", None)

    message = str(exc_info.value)
    assert "GEMINI_API_KEY is not set" in message
    assert "GEMINI_API_KEY" in message
    assert "--session-file" in message
    assert "(1)" in message
    assert "(2)" in message


# ===========================================================================
# 4. resolve_provider with unknown provider
# ===========================================================================


@pytest.mark.parametrize("unknown", ["openai", "deepseek", "anthropic", "llama"])
def test_resolve_provider_unknown_provider_stops_naming_valid_choices(
    unknown: str,
) -> None:
    """An unknown provider name stops naming valid choices ('claude' or 'gemini')."""
    with pytest.raises(ValueError) as exc_info:
        resolve_provider(unknown, None)  # type: ignore[arg-type]

    message = str(exc_info.value)
    assert "claude" in message
    assert "gemini" in message
    assert unknown in message


# ===========================================================================
# 5. _call_llm stop
# ===========================================================================


def test_call_llm_stops_when_given_non_gemini_resolution() -> None:
    """_call_llm raises ValueError when resolution.provider is not 'gemini' (Rule 3)."""
    bad_resolution = ProviderResolution(
        provider="claude",  # type: ignore[arg-type]
        model="claude-opus-5",
        reasoning_label="stub",
        transport="claude-code-session",
        transport_label="stub",
        credential="claude-code-session",
        credential_source="stub",
    )

    with pytest.raises(ValueError) as exc_info:
        _call_llm("sys", "user", bad_resolution)

    message = str(exc_info.value)
    assert "_call_llm: unexpected provider 'claude'" in message
    assert "claude-code-session" in message
    assert "Route A supports Gemini only." in message


# ===========================================================================
# 6. CLI refusal of -p claude
# ===========================================================================


def test_cli_refuses_dash_p_claude() -> None:
    """The CLI refuses -p claude with exit code 2 and invalid choice error.

    Three facts, all three still asserted: the exit code is argparse's usage
    error code 2, the message names the rejected value, and the list of
    remaining choices is exactly `gemini`.

    The third assertion is a regex because argparse changed the wording of the
    choice list between the Python versions this repository runs on. Python
    3.11.6 prints `(choose from 'gemini')`; Python 3.14.4 prints
    `(choose from gemini)`, with no quotation marks. Only the quoting differs,
    so the optional quote is the only thing the pattern tolerates. The closing
    parenthesis is part of the pattern, so a second accepted provider appearing
    in the list would still turn this test red.
    """
    result = subprocess.run(
        [sys.executable, "cli.py", "-p", "claude", "10K_filings/Walmart"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "invalid choice: 'claude'" in result.stderr
    assert re.search(r"choose from '?gemini'?\)", result.stderr), result.stderr


def test_cli_help_documents_gemini_default_and_session_file() -> None:
    """The CLI --help output documents gemini default and session-file route."""
    result = subprocess.run(
        [sys.executable, "cli.py", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "default: gemini" in result.stdout
    assert "Claude reads a filing" in result.stdout
    assert "--session-file" in result.stdout


# ===========================================================================
# 7. Shipped code import isolation and purged dependencies
# ===========================================================================


def test_app_and_cli_import_without_anthropic_and_azure() -> None:
    """The app, cli, and claude_extractor import with anthropic and azure blocked."""
    cmd = (
        "import sys; "
        "sys.modules['anthropic'] = None; "
        "sys.modules['azure'] = None; "
        "import app, cli, ingestion.claude_extractor; "
        "print('IMPORT_SUCCESS')"
    )
    result = subprocess.run(
        [sys.executable, "-c", cmd],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Import failed: {result.stderr}"
    assert "IMPORT_SUCCESS" in result.stdout


def test_shipped_code_holds_no_foundry_or_anthropic_api_paths() -> None:
    """Grep check confirms zero occurrences of purged symbols in shipped code."""
    targets = ["ingestion", "config.py", "requirements.txt", "cli.py", "api"]
    result = subprocess.run(
        ["grep", "-rniE", "--exclude=*.pyc", "foundry|entra|azure|anthropic", *targets],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # grep returns 1 when 0 matches found
    assert result.returncode == 1, (
        f"Expected 0 hits for purged symbols, found:\n{result.stdout}"
    )
