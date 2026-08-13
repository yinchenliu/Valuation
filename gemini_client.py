"""Google Gemini behind the Anthropic Messages interface.

`agent/loop.py` is written against one request/response shape: a
`client.messages.create(...)` that takes `system` blocks, Anthropic-style tool
specs and a `messages` list, and returns an object with `.content`,
`.stop_reason` and `.usage`. Rather than fork the loop per provider — which
would mean two places to keep the tool wiring, the parallel-result batching and
the refusal handling correct — Gemini is adapted *up* to that shape here.

The loop therefore stays provider-agnostic and the agentic/deterministic parity
tests keep testing one code path.

What the translation has to get right:

- **Thought signatures.** Gemini 3 returns an opaque signature alongside its
  function calls and expects it back on the next turn; dropping it degrades
  multi-turn tool use. Every response block keeps the original `types.Part`, and
  the assistant turn is rebuilt from those exact Parts, so signatures survive
  round-tripping untouched.
- **Tool results are keyed by name, not id.** Anthropic echoes a
  `tool_use_id`; Gemini wants the function's name. The id→name map is rebuilt by
  walking the message list, so the adapter holds no cross-turn state.
- **Schema dialects differ.** Anthropic takes JSON Schema with `["number",
  "null"]` unions; Gemini takes an OpenAPI subset with a separate `nullable`
  flag. See `_to_gemini_schema`.

Caching is not configured here: Anthropic needs an explicit `cache_control`
breakpoint, Gemini caches a repeated prefix implicitly. The loop's frozen
tool/system prefix is what earns the discount on both, so the `cache_control`
block the loop sends is simply ignored on this path.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

# Anthropic's effort levels mapped onto Gemini's thinking levels. Gemini exposes
# a coarser dial, so the top three efforts collapse onto "high".
_EFFORT_TO_THINKING_LEVEL = {
    "low": "low",
    "medium": "low",
    "high": "high",
    "xhigh": "high",
    "max": "high",
}

_RETRYABLE = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL")

# Gemini finish reasons that mean the model was stopped rather than done. The
# loop treats "refusal" as terminal, which is the right handling for all of them.
_REFUSAL_REASONS = {
    "SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT",
    "SPII", "IMAGE_SAFETY", "LANGUAGE",
}


# ---------------------------------------------------------------------------
# Response blocks — shaped like the Anthropic SDK's content blocks
# ---------------------------------------------------------------------------

@dataclass
class _Block:
    """Common base: `part` is the untouched Gemini Part this block came from.

    Keeping it is what lets the assistant turn be replayed byte-identical,
    thought signatures included.
    """

    part: Any = field(default=None, repr=False, compare=False)


@dataclass
class TextBlock(_Block):
    text: str = ""
    type: str = "text"


@dataclass
class ThinkingBlock(_Block):
    thinking: str = ""
    type: str = "thinking"


@dataclass
class ToolUseBlock(_Block):
    name: str = ""
    input: dict = field(default_factory=dict)
    id: str = ""
    type: str = "tool_use"


@dataclass
class OpaqueBlock(_Block):
    """A Part carrying no text or call — e.g. a bare thought signature.

    The loop ignores unknown block types, but it must still be echoed back or the
    signature is lost.
    """

    type: str = "opaque"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class Response:
    content: list
    stop_reason: str
    usage: Usage


# ---------------------------------------------------------------------------
# Schema translation
# ---------------------------------------------------------------------------

def _to_gemini_schema(node: dict):
    """Translate one JSON Schema node into a `types.Schema`.

    Handles the two dialect differences this project's tool specs actually hit:
    a `["number", "null"]` union becomes `type=NUMBER, nullable=True`, and an
    `enum` containing `null` drops the null and sets `nullable` instead.
    """
    from google.genai import types

    raw_type = node.get("type")
    nullable = False
    if isinstance(raw_type, list):
        nullable = "null" in raw_type
        concrete = [t for t in raw_type if t != "null"]
        json_type = concrete[0] if concrete else "string"
    else:
        json_type = raw_type or "string"

    enum_values = node.get("enum")
    if enum_values is not None:
        cleaned = [str(v) for v in enum_values if v is not None]
        nullable = nullable or len(cleaned) != len(enum_values)
        enum_values = cleaned or None

    schema = types.Schema(
        type=json_type.upper(),
        description=node.get("description"),
        nullable=nullable or None,
        enum=enum_values,
    )

    if json_type == "array" and node.get("items"):
        schema.items = _to_gemini_schema(node["items"])
    if json_type == "object":
        properties = node.get("properties") or {}
        schema.properties = {k: _to_gemini_schema(v) for k, v in properties.items()}
        # Anthropic's strict mode lists every parameter as required and relies on
        # explicit nulls. Gemini reads `required` as "must be present", which
        # pushes the model to fabricate values, so nullable parameters are
        # dropped from the list — the Python tools already default them to None.
        schema.required = [
            name for name in (node.get("required") or [])
            if not (schema.properties.get(name) and schema.properties[name].nullable)
        ] or None

    return schema


def to_function_declarations(tool_specs: list[dict]) -> list:
    """Anthropic tool specs -> Gemini FunctionDeclarations, order preserved."""
    from google.genai import types

    declarations = []
    for spec in tool_specs:
        input_schema = spec.get("input_schema") or {}
        # A no-argument tool must omit `parameters` entirely; an object schema
        # with no properties is rejected.
        parameters = (
            _to_gemini_schema(input_schema)
            if (input_schema.get("properties") or {})
            else None
        )
        declarations.append(types.FunctionDeclaration(
            name=spec["name"],
            description=spec.get("description", ""),
            parameters=parameters,
        ))
    return declarations


# ---------------------------------------------------------------------------
# Message translation
# ---------------------------------------------------------------------------

def _function_response_payload(raw: Any) -> dict:
    """Tool results travel as JSON strings; Gemini wants a dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"result": raw}
        return parsed if isinstance(parsed, dict) else {"result": parsed}
    return {"result": raw}


def to_contents(messages: list[dict]) -> list:
    """Anthropic `messages` -> Gemini `contents`.

    The tool_use_id -> function name map is rebuilt from the assistant turns in
    this very list, so the adapter keeps no state between calls.
    """
    from google.genai import types

    id_to_name: dict[str, str] = {}
    contents = []

    for message in messages:
        role = message.get("role")
        content = message.get("content")

        if role == "assistant":
            parts = []
            for block in content or []:
                if getattr(block, "type", None) == "tool_use":
                    id_to_name[block.id] = block.name
                part = getattr(block, "part", None)
                if part is not None:
                    parts.append(part)
                elif getattr(block, "type", None) == "text":
                    parts.append(types.Part(text=block.text))
            if parts:
                contents.append(types.Content(role="model", parts=parts))
            continue

        if isinstance(content, str):
            contents.append(types.Content(role="user", parts=[types.Part(text=content)]))
            continue

        parts = []
        for block in content or []:
            kind = block.get("type")
            if kind == "tool_result":
                parts.append(types.Part.from_function_response(
                    name=id_to_name.get(block.get("tool_use_id"), "unknown_tool"),
                    response=_function_response_payload(block.get("content")),
                ))
            elif kind == "text":
                parts.append(types.Part(text=block.get("text", "")))
        if parts:
            contents.append(types.Content(role="user", parts=parts))

    return contents


def _finish_reason_name(candidate) -> str:
    reason = getattr(candidate, "finish_reason", None)
    if reason is None:
        return ""
    return (getattr(reason, "name", None) or str(reason).rsplit(".", 1)[-1]).upper()


def _system_text(system) -> str:
    """The loop sends system as cache-annotated blocks; Gemini wants a string."""
    if isinstance(system, str):
        return system
    return "\n\n".join(
        block.get("text", "") for block in (system or []) if isinstance(block, dict)
    )


# ---------------------------------------------------------------------------
# The client
# ---------------------------------------------------------------------------

def _genai_client(api_key: str):
    """Constructing the real SDK client. Patched in tests."""
    from google import genai

    return genai.Client(api_key=api_key)


class GeminiMessagesClient:
    """A Gemini client wearing the Anthropic Messages API's shape.

    Only the surface `agent/loop.py` uses is implemented — `messages.create`.
    """

    def __init__(self, api_key: str, max_retries: int = 4) -> None:
        self._api_key = api_key
        self._max_retries = max_retries
        self._client = None
        self._call_index = 0
        # Older Gemini models take `thinking_budget` rather than `thinking_level`.
        # Rather than gate on a model-name list that will go stale, the first
        # rejection flips this off for the rest of the run.
        self._thinking_level_supported = True
        self.messages = self

    # -- request -----------------------------------------------------------

    def _build_config(self, *, system, tools, max_tokens: int, effort: str):
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=_system_text(system) or None,
            max_output_tokens=max_tokens,
            tools=[types.Tool(function_declarations=to_function_declarations(tools or []))]
            if tools else None,
        )
        if self._thinking_level_supported:
            config.thinking_config = types.ThinkingConfig(
                thinking_level=_EFFORT_TO_THINKING_LEVEL.get(effort, "high"),
                include_thoughts=True,
            )
        return config

    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system=None,
        tools=None,
        output_config: dict | None = None,
        thinking: dict | None = None,  # noqa: ARG002 — Anthropic-only, implied here
        **_ignored: Any,
    ) -> Response:
        effort = (output_config or {}).get("effort", "high")
        contents = to_contents(messages)

        if self._client is None:
            self._client = _genai_client(self._api_key)

        attempt = 0
        while True:
            attempt += 1
            try:
                raw = self._client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=self._build_config(
                        system=system, tools=tools, max_tokens=max_tokens, effort=effort
                    ),
                )
                return self._to_response(raw)
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                if self._thinking_level_supported and "thinking" in message.lower():
                    # The model does not take thinking_level. Drop it and try
                    # again rather than failing the whole valuation — and do not
                    # spend a retry on it, since it is a config fix, not a
                    # transient fault.
                    self._thinking_level_supported = False
                    attempt -= 1
                    continue
                if attempt >= self._max_retries or not any(t in message for t in _RETRYABLE):
                    raise
                wait = 2 ** attempt
                suggested = re.search(r"retry in ([\d.]+)s", message, re.IGNORECASE)
                if suggested:
                    wait = max(wait, float(suggested.group(1)) + 1)
                time.sleep(wait)

    # -- response ----------------------------------------------------------

    def _to_response(self, raw) -> Response:
        self._call_index += 1
        candidate = (raw.candidates or [None])[0]
        parts = []
        if candidate is not None and candidate.content is not None:
            parts = candidate.content.parts or []

        blocks: list = []
        for i, part in enumerate(parts):
            if part.function_call is not None:
                call = part.function_call
                blocks.append(ToolUseBlock(
                    part=part,
                    name=call.name or "",
                    input=dict(call.args or {}),
                    # Gemini usually omits the id; the loop only needs it to pair
                    # a result back to its call within the turn.
                    id=call.id or f"gem_{self._call_index}_{i}",
                ))
            elif part.thought:
                blocks.append(ThinkingBlock(part=part, thinking=part.text or ""))
            elif part.text:
                blocks.append(TextBlock(part=part, text=part.text))
            else:
                blocks.append(OpaqueBlock(part=part))

        finish = _finish_reason_name(candidate) if candidate is not None else ""
        block_reason = getattr(getattr(raw, "prompt_feedback", None), "block_reason", None)

        if any(b.type == "tool_use" for b in blocks):
            stop_reason = "tool_use"
        elif block_reason is not None or finish in _REFUSAL_REASONS:
            stop_reason = "refusal"
        elif finish == "MAX_TOKENS":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        meta = getattr(raw, "usage_metadata", None)

        def _count(name: str) -> int:
            return getattr(meta, name, 0) or 0 if meta is not None else 0

        return Response(
            content=blocks,
            stop_reason=stop_reason,
            usage=Usage(
                input_tokens=_count("prompt_token_count"),
                # Gemini reports reasoning tokens separately; Anthropic folds them
                # into output, so they are summed here to keep totals comparable.
                output_tokens=_count("candidates_token_count") + _count("thoughts_token_count"),
                cache_read_input_tokens=_count("cached_content_token_count"),
                # Implicit caching has no separate write charge.
                cache_creation_input_tokens=0,
            ),
        )
