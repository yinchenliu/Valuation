"""LLM client construction for every backend this project can talk to.

Two independent choices live here, and conflating them is the easy mistake:

1. **Which model family drives the agent** — Claude or Gemini. That is
   `AGENT_PROVIDER` (`claude` | `gemini`), resolved by `resolve_agent_provider`.
2. **Which backend serves Claude** — the first-party Anthropic API or Google
   Cloud's Vertex AI. That is `CLAUDE_PROVIDER` (`anthropic` | `vertex`),
   resolved by `resolve_provider`, and it has no bearing on Gemini.

Claude is reachable two ways, and they authenticate completely differently:

- **First-party Anthropic API** — an `sk-ant-...` key in `ANTHROPIC_API_KEY`.
- **Google Cloud Vertex AI** — no Anthropic key at all. Auth is Google
  credentials (Application Default Credentials or a service-account JSON), plus
  a GCP project and region.

A key issued by Google Cloud is the second kind, so passing it as
`ANTHROPIC_API_KEY` will not work. Set `CLAUDE_PROVIDER=vertex` along with the
project and region instead.

Model IDs on Vertex are the bare first-party strings — `claude-sonnet-5`, not
`anthropic.claude-sonnet-5` (that prefix is Amazon Bedrock's convention).

Gemini is the simplest of the three: an `AIza...` key in `GEMINI_API_KEY`, the
same one the PDF extractor already uses. `gemini_client` wraps it in the
Anthropic Messages interface so `agent/loop.py` stays provider-agnostic.
"""

from __future__ import annotations

import os

import config  # noqa: F401 — importing loads .env into os.environ

# Vertex serves a subset of the first-party feature set. Nothing this project
# relies on is missing (tool use, prompt caching, adaptive thinking, effort are
# all supported), but a few things are, so they are flagged rather than silently
# failing at request time.
VERTEX_UNSUPPORTED = (
    "mid-conversation system messages",
    "the Files, Batches and Models APIs",
    "the web_fetch server tool",
)


class ClientConfigError(RuntimeError):
    """Credentials are missing or inconsistent. Message is user-facing."""


def resolve_provider() -> str:
    """Which Claude backend to use: 'vertex' or 'anthropic'.

    Explicit `CLAUDE_PROVIDER` wins. Otherwise infer: Vertex needs a project id,
    so its presence without an Anthropic key is a clear signal.
    """
    explicit = (os.environ.get("CLAUDE_PROVIDER") or "").strip().lower()
    if explicit:
        if explicit not in {"anthropic", "vertex"}:
            raise ClientConfigError(
                f"CLAUDE_PROVIDER must be 'anthropic' or 'vertex', got {explicit!r}."
            )
        return explicit

    has_vertex = bool(_vertex_project())
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if has_vertex and not has_key:
        return "vertex"
    return "anthropic"


def _vertex_project() -> str:
    return (
        os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
        or os.environ.get("CLAUDE_VERTEX_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or ""
    ).strip()


def _vertex_region() -> str:
    return (
        os.environ.get("CLOUD_ML_REGION")
        or os.environ.get("ANTHROPIC_VERTEX_REGION")
        or os.environ.get("CLAUDE_VERTEX_REGION")
        or "global"
    ).strip()


def build_client(max_retries: int = 4):
    """Construct the Anthropic client for the configured backend.

    Returns an object exposing the standard `messages.create` / `.stream`
    surface, so callers do not need to care which backend they got.
    """
    provider = resolve_provider()

    if provider == "vertex":
        project_id = _vertex_project()
        if not project_id:
            raise ClientConfigError(
                "Vertex AI needs a GCP project id. Set CLAUDE_VERTEX_PROJECT_ID "
                "(or GOOGLE_CLOUD_PROJECT) in .env."
            )
        try:
            from anthropic import AnthropicVertex
        except ImportError as exc:
            raise ClientConfigError(
                "Vertex support is not installed. Run:\n"
                '  pip install "anthropic[vertex]"'
            ) from exc

        # Vertex has no api_key parameter. Credentials resolve, in order:
        #   1. an explicit OAuth access token (short-lived, ~1h)
        #   2. GOOGLE_APPLICATION_CREDENTIALS -> service-account JSON
        #   3. Application Default Credentials from `gcloud auth ... login`
        access_token = (os.environ.get("CLAUDE_VERTEX_ACCESS_TOKEN") or "").strip() or None

        try:
            return AnthropicVertex(
                project_id=project_id,
                region=_vertex_region(),
                access_token=access_token,
                max_retries=max_retries,
            )
        except Exception as exc:  # noqa: BLE001
            raise ClientConfigError(
                f"Could not create the Vertex AI client: {exc}\n"
                "Vertex authenticates with Google credentials — it has no API-key\n"
                "parameter. Use one of:\n"
                "  - gcloud auth application-default login\n"
                "  - GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json\n"
                "  - CLAUDE_VERTEX_ACCESS_TOKEN=ya29... (expires in ~1 hour)\n"
                "Note: an AIza... key is a Google AI Studio key for Gemini and will\n"
                "not authenticate Claude on Vertex — use it as GEMINI_API_KEY instead."
            ) from exc

    try:
        import anthropic
    except ImportError as exc:
        raise ClientConfigError(
            "The 'anthropic' package is required to use Claude. Install it with:\n"
            "  pip install anthropic"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ClientConfigError(
            "No Claude credentials found.\n"
            "  - First-party Anthropic API: set ANTHROPIC_API_KEY in .env\n"
            "  - Google Cloud (Vertex AI):  set CLAUDE_PROVIDER=vertex plus\n"
            "      CLAUDE_VERTEX_PROJECT_ID and CLAUDE_VERTEX_REGION, and\n"
            "      authenticate with Google credentials (a Google-issued key is\n"
            "      not an ANTHROPIC_API_KEY)."
        )
    return anthropic.Anthropic(api_key=api_key, max_retries=max_retries)


def describe_backend() -> str:
    """One-line description of the configured Claude backend, for logs and the UI."""
    provider = resolve_provider()
    if provider == "vertex":
        return f"Vertex AI (project {_vertex_project() or '?'}, region {_vertex_region()})"
    return "Anthropic API"


# ---------------------------------------------------------------------------
# Agent provider: which model family drives the agentic loop
# ---------------------------------------------------------------------------

AGENT_PROVIDERS = ("claude", "gemini")


def _has_claude_credentials() -> bool:
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("CLAUDE_PROVIDER")
        or _vertex_project()
    )


def resolve_agent_provider(explicit: str | None = None) -> str:
    """Which model family orchestrates the valuation: 'claude' or 'gemini'.

    An explicit argument wins, then `AGENT_PROVIDER`. Failing both, Gemini is
    chosen only when it is the sole option configured — so adding a Gemini key
    for PDF extraction never silently reroutes an agent run that was working.
    """
    choice = (explicit or os.environ.get("AGENT_PROVIDER") or "").strip().lower()
    if choice:
        if choice not in AGENT_PROVIDERS:
            raise ClientConfigError(
                f"AGENT_PROVIDER must be one of {', '.join(AGENT_PROVIDERS)}, got {choice!r}."
            )
        return choice

    if os.environ.get("GEMINI_API_KEY") and not _has_claude_credentials():
        return "gemini"
    return "claude"


def build_agent_client(provider: str | None = None, max_retries: int = 4):
    """Construct the client driving the agentic loop, for either model family.

    Both returned objects expose the same `messages.create(...)` surface over the
    same request and response shapes, so the loop does not branch on provider.
    See `gemini_client` for how the Gemini side is adapted onto it.
    """
    if resolve_agent_provider(provider) == "gemini":
        import gemini_client

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ClientConfigError(
                "No Gemini credentials found.\n"
                "  - Set GEMINI_API_KEY in .env (an AIza... key from Google AI Studio)\n"
                "  - Or set AGENT_PROVIDER=claude to orchestrate with Claude instead."
            )
        return gemini_client.GeminiMessagesClient(api_key=api_key, max_retries=max_retries)

    return build_client(max_retries=max_retries)


def describe_agent_backend(provider: str | None = None) -> str:
    """One-line description of the agent's backend, for logs and the UI."""
    if resolve_agent_provider(provider) == "gemini":
        return "Google Gemini API"
    return describe_backend()
