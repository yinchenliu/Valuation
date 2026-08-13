"""Agent loop tests against stub clients — no API calls, no keys.

The loop is the core new machinery, and most of the ways it can be wrong are
invisible until they cost money or silently degrade results:

- resending a tool/system prefix that differs byte-for-byte between turns, which
  defeats prompt caching entirely;
- splitting parallel tool results across several user messages, which trains the
  model out of making parallel calls;
- dropping thinking blocks from the echoed assistant turn;
- reading `content[0]` on a refusal, which raises instead of reporting.

Each of those is checked here by driving the real loop with a scripted client.

The Gemini backend is driven the same way, against a stub of the google-genai
client, because its failure modes are translation bugs rather than loop bugs and
are just as quiet: a dropped thought signature degrades multi-turn tool use
without erroring, and function responses keyed by the wrong name are simply
ignored by the model. Those tests build real `google.genai.types` objects, so a
schema the SDK would reject fails here rather than in production.

Usage:
    python tests/test_agent_loop.py
"""

from __future__ import annotations

import json
import os
import pickle
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import gemini_client  # noqa: E402
import pipeline  # noqa: E402
from agent import loop as agent_loop  # noqa: E402
from agent import tools as agent_tools  # noqa: E402

FIXTURE = BASE_DIR / "cache" / ".cache_abbv_extraction.pkl"
_failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")
        _failures.append(label)


# --- Stub response objects, shaped like the SDK's ---------------------------

@dataclass
class _Text:
    text: str
    type: str = "text"


@dataclass
class _Thinking:
    thinking: str = ""
    type: str = "thinking"


@dataclass
class _ToolUse:
    name: str
    input: dict
    id: str
    type: str = "tool_use"


@dataclass
class _Usage:
    input_tokens: int = 100
    output_tokens: int = 50
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class _Response:
    content: list
    stop_reason: str = "tool_use"
    usage: _Usage = field(default_factory=_Usage)


class StubClient:
    """Replays a scripted list of responses and records every request."""

    def __init__(self, script: list[_Response]) -> None:
        self._script = list(script)
        self.requests: list[dict] = []
        self.messages = self

    def create(self, **kwargs: Any) -> _Response:
        # Snapshot the message list: the loop appends to it in place, so storing
        # the reference would make every recorded request show the final state.
        recorded = dict(kwargs)
        recorded["messages"] = list(kwargs.get("messages", []))
        self.requests.append(recorded)
        if not self._script:
            return _Response(content=[_Text("Done.")], stop_reason="end_turn")
        response = self._script.pop(0)
        # Simulate the server reporting a cache read once the prefix is warm.
        if len(self.requests) > 1:
            response.usage.cache_read_input_tokens = 4096
        return response


@contextmanager
def _stub_credential(name: str):
    """Force a placeholder credential while a stubbed client is in play.

    `setdefault` is not enough: a `.env` that declares the key but leaves it
    blank puts an empty string in `os.environ`, which the client builders reject
    — so these tests would fail on a developer machine and pass on a bare one.
    """
    original = os.environ.get(name)
    os.environ[name] = "stub-key-for-tests"
    try:
        yield
    finally:
        if original is None:
            del os.environ[name]
        else:
            os.environ[name] = original


def _load_run() -> pipeline.ValuationRun:
    with open(FIXTURE, "rb") as fh:
        financials, non_recurring = pickle.load(fh)
    run = pipeline.ValuationRun(ticker=financials.ticker or "ABBV")
    run.raw_financials = financials
    run.non_recurring = non_recurring
    return run


def _drive(script: list[_Response], max_iterations: int = 10):
    """Run the real loop against a stub client."""
    run = _load_run()
    client = StubClient(script)

    import anthropic

    original = anthropic.Anthropic
    anthropic.Anthropic = lambda **kw: client  # type: ignore[assignment]
    try:
        # provider is pinned rather than resolved: this stubs the Anthropic
        # client, so it must not follow a machine's AGENT_PROVIDER to Gemini.
        with _stub_credential("ANTHROPIC_API_KEY"):
            result = agent_loop.run_agentic_valuation(
                run, provider="claude", max_iterations=max_iterations
            )
    finally:
        anthropic.Anthropic = original  # type: ignore[assignment]
    return run, client, result


def test_prefix_is_stable() -> None:
    """Tools and system prompt must be byte-identical on every turn."""
    print("\n=== Cacheable prefix stability ===")

    script = [
        _Response(content=[
            _Thinking("considering"),
            _Text("Let me look at what was extracted."),
            _ToolUse("get_extraction_summary", {}, "tu_1"),
        ]),
        _Response(content=[
            _ToolUse("validate_arithmetic", {}, "tu_2"),
            _ToolUse("get_historical_fcff", {}, "tu_3"),
        ]),
        _Response(content=[_Text("Summary of findings.")], stop_reason="end_turn"),
    ]
    run, client, result = _drive(script)

    check("loop ran three turns", len(client.requests) == 3, str(len(client.requests)))

    tool_payloads = [json.dumps(r["tools"], sort_keys=False) for r in client.requests]
    check("tool definitions byte-identical across turns", len(set(tool_payloads)) == 1)

    system_payloads = [json.dumps(r["system"]) for r in client.requests]
    check("system prompt byte-identical across turns", len(set(system_payloads)) == 1)

    first_system = client.requests[0]["system"]
    check(
        "cache breakpoint set on the system block",
        isinstance(first_system, list)
        and first_system[-1].get("cache_control", {}).get("type") == "ephemeral",
        str(first_system)[:120],
    )

    check(
        "adaptive thinking requested",
        client.requests[0].get("thinking", {}).get("type") == "adaptive",
    )
    check(
        "no sampling params sent (rejected on current models)",
        not any(k in client.requests[0] for k in ("temperature", "top_p", "top_k")),
    )
    check("effort configured", "effort" in client.requests[0].get("output_config", {}))
    check("cache reads accumulated", result.cache_read_tokens > 0, str(result.cache_read_tokens))


def test_parallel_results_in_one_message() -> None:
    """Two tool calls in one turn must come back in a single user message."""
    print("\n=== Parallel tool results ===")

    script = [
        _Response(content=[
            _ToolUse("get_extraction_summary", {}, "tu_1"),
            _ToolUse("get_historical_fcff", {}, "tu_2"),
        ]),
        _Response(content=[_Text("Done.")], stop_reason="end_turn"),
    ]
    run, client, result = _drive(script)

    second_request_messages = client.requests[1]["messages"]
    user_msgs = [m for m in second_request_messages if m["role"] == "user"]
    # kickoff + one results message
    check("results batched into one user message", len(user_msgs) == 2, str(len(user_msgs)))

    results_msg = user_msgs[-1]
    blocks = results_msg["content"]
    check("both tool_results in that message", len(blocks) == 2, str(len(blocks)))
    check(
        "tool_use_ids echoed correctly",
        {b["tool_use_id"] for b in blocks} == {"tu_1", "tu_2"},
    )
    check("result count recorded", result.tool_calls == 2, str(result.tool_calls))


def test_thinking_blocks_echoed() -> None:
    """Assistant content is echoed back whole, thinking blocks included."""
    print("\n=== Thinking block preservation ===")

    script = [
        _Response(content=[
            _Thinking("internal reasoning"),
            _ToolUse("get_extraction_summary", {}, "tu_1"),
        ]),
        _Response(content=[_Text("Done.")], stop_reason="end_turn"),
    ]
    run, client, result = _drive(script)

    assistant_msgs = [m for m in client.requests[1]["messages"] if m["role"] == "assistant"]
    check("assistant turn echoed", len(assistant_msgs) == 1)
    echoed = assistant_msgs[0]["content"]
    kinds = [getattr(b, "type", None) for b in echoed]
    check("thinking block preserved", "thinking" in kinds, str(kinds))
    check("tool_use block preserved", "tool_use" in kinds, str(kinds))


def test_tool_error_flagged() -> None:
    """A failing tool comes back as is_error so the model can recover."""
    print("\n=== Tool error signalling ===")

    script = [
        # calculate_wacc before run_capm — prerequisite violation
        _Response(content=[_ToolUse(
            "calculate_wacc",
            {"cost_of_debt_override": None, "tax_rate_override": None},
            "tu_1",
        )]),
        _Response(content=[_Text("I'll fetch market data first.")], stop_reason="end_turn"),
    ]
    run, client, result = _drive(script)

    blocks = [m for m in client.requests[1]["messages"] if m["role"] == "user"][-1]["content"]
    check("tool_result marked is_error", blocks[0].get("is_error") is True, str(blocks[0])[:160])
    payload = json.loads(blocks[0]["content"])
    check("error names the missing step", "run_capm" in payload.get("error", ""), payload.get("error", ""))


def test_refusal_handled() -> None:
    """A refusal is reported, not raised on content[0]."""
    print("\n=== Refusal handling ===")

    script = [_Response(content=[], stop_reason="refusal")]
    run, client, result = _drive(script)

    check("loop returned instead of raising", result is not None)
    check("refusal reported", "refusal" in result.error.lower(), result.error)
    check("not marked completed", result.completed is False)


def test_iteration_cap() -> None:
    """The loop stops at max_iterations instead of running forever."""
    print("\n=== Iteration cap ===")

    # An endless stream of tool calls.
    script = [
        _Response(content=[_ToolUse("get_extraction_summary", {}, f"tu_{i}")])
        for i in range(20)
    ]
    run, client, result = _drive(script, max_iterations=4)

    check("stopped at the cap", result.iterations == 4, str(result.iterations))
    check("cap reported", "iterations" in result.error.lower(), result.error)


# --- Gemini backend ---------------------------------------------------------

class StubGeminiClient:
    """Replays scripted GenerateContentResponses and records every request."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.requests: list[dict] = []
        self.models = self

    def generate_content(self, **kwargs: Any):
        self.requests.append(kwargs)
        if not self._script:
            return _gemini_response([_gemini_text("Done.")])
        return self._script.pop(0)


def _gemini_text(text: str, thought: bool = False):
    from google.genai import types

    return types.Part(text=text, thought=thought or None)


def _gemini_call(name: str, args: dict | None = None, signature: bytes = b"sig"):
    from google.genai import types

    return types.Part(
        function_call=types.FunctionCall(name=name, args=args or {}),
        thought_signature=signature,
    )


def _gemini_response(parts: list, finish_reason: str = "STOP", cached: int = 0):
    from google.genai import types

    return types.GenerateContentResponse(
        candidates=[types.Candidate(
            content=types.Content(role="model", parts=parts),
            finish_reason=finish_reason,
        )],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=1000,
            candidates_token_count=50,
            thoughts_token_count=10,
            cached_content_token_count=cached,
        ),
    )


def _drive_gemini(script: list, max_iterations: int = 10, stub=None):
    """Run the real loop against a stub google-genai client."""
    run = _load_run()
    stub = stub or StubGeminiClient(script)

    original = gemini_client._genai_client
    gemini_client._genai_client = lambda api_key: stub  # type: ignore[assignment]
    try:
        with _stub_credential("GEMINI_API_KEY"):
            result = agent_loop.run_agentic_valuation(
                run, provider="gemini", max_iterations=max_iterations
            )
    finally:
        gemini_client._genai_client = original  # type: ignore[assignment]
    return run, stub, result


def test_gemini_translation() -> None:
    """The same loop, driven by Gemini, translated correctly in both directions."""
    print("\n=== Gemini backend ===")

    script = [
        _gemini_response([
            _gemini_text("Looking at the extraction.", thought=True),
            _gemini_call("get_extraction_summary", signature=b"sig-1"),
        ]),
        _gemini_response([
            _gemini_call("validate_arithmetic", signature=b"sig-2"),
            _gemini_call("get_historical_fcff", signature=b"sig-3"),
        ], cached=4096),
        _gemini_response([_gemini_text("Summary of findings.")], cached=4096),
    ]
    run, stub, result = _drive_gemini(script)

    check("loop ran three turns", len(stub.requests) == 3, str(len(stub.requests)))
    check("provider recorded on the result", result.provider == "gemini", result.provider)
    check("gemini model resolved", result.model.startswith("gemini"), result.model)
    check("gemini backend described", "Gemini" in result.backend, result.backend)

    # The cacheable prefix argument applies here too: Gemini caches a repeated
    # prefix implicitly, so a tool list that differs between turns still costs.
    declarations = [r["config"].tools[0].function_declarations for r in stub.requests]
    payloads = [
        json.dumps([d.model_dump(mode="json", exclude_none=True) for d in group])
        for group in declarations
    ]
    check("function declarations byte-identical across turns", len(set(payloads)) == 1)
    check(
        "every tool exposed, order preserved",
        [d.name for d in declarations[0]] == [s["name"] for s in agent_tools.TOOL_SPECS],
    )
    check(
        "no-argument tools omit parameters",
        next(d for d in declarations[0] if d.name == "get_extraction_summary").parameters is None,
    )
    nullable = next(
        d for d in declarations[0] if d.name == "derive_assumptions"
    ).parameters.properties["terminal_growth_rate"]
    check("nullable union converted to nullable flag", nullable.nullable is True)

    systems = [r["config"].system_instruction for r in stub.requests]
    check("system instruction stable across turns", len(set(systems)) == 1)
    check("system instruction carries the prompt", "analyst" in systems[0], systems[0][:60])
    check(
        "thinking level requested",
        stub.requests[0]["config"].thinking_config is not None,
    )

    contents = stub.requests[2]["contents"]
    user_turns = [c for c in contents if c.role == "user"]
    # kickoff + one content per tool round (1 call, then 2 parallel calls) — the
    # second round must not be split across two contents.
    check("one user content per tool round", len(user_turns) == 3, str(len(user_turns)))
    responses = user_turns[-1].parts
    check("both function responses in that content", len(responses) == 2, str(len(responses)))
    by_name = {p.function_response.name: p.function_response.response for p in responses}
    check(
        "function responses keyed by tool name",
        set(by_name) == {"validate_arithmetic", "get_historical_fcff"},
        str(sorted(by_name)),
    )
    check(
        "tool result JSON decoded into a response dict",
        isinstance(by_name.get("get_historical_fcff"), dict)
        and "years" in by_name["get_historical_fcff"],
        str(by_name.get("get_historical_fcff"))[:120],
    )

    model_turns = [c for c in contents if c.role == "model"]
    signatures = {p.thought_signature for c in model_turns for p in c.parts if p.thought_signature}
    check(
        "thought signatures echoed back unchanged",
        {b"sig-1", b"sig-2", b"sig-3"} <= signatures,
        str(sorted(signatures)),
    )
    check(
        "thought part preserved on the echoed turn",
        any(p.thought for c in model_turns for p in c.parts),
    )

    check("all three tool calls executed", result.tool_calls == 3, str(result.tool_calls))
    check("narrative captured", result.narrative == "Summary of findings.", result.narrative)
    check("cache reads accumulated", result.cache_read_tokens > 0, str(result.cache_read_tokens))
    check(
        "thinking tokens folded into output",
        result.output_tokens == 3 * 60, str(result.output_tokens),
    )


class RejectThinkingLevelClient(StubGeminiClient):
    """Rejects `thinking_level` once, the way an older model would."""

    def __init__(self, script: list) -> None:
        super().__init__(script)
        self.rejected = False

    def generate_content(self, **kwargs: Any):
        if not self.rejected:
            self.rejected = True
            self.requests.append(kwargs)
            raise ValueError(
                "Unknown name \"thinking_level\": Cannot find field."
            )
        return super().generate_content(**kwargs)


def test_gemini_thinking_level_downgrade() -> None:
    """A model that will not take thinking_level still completes the run."""
    print("\n=== Gemini thinking-level fallback ===")

    stub = RejectThinkingLevelClient([_gemini_response([_gemini_text("Done.")])])
    run, stub, result = _drive_gemini([], stub=stub)

    check("retried after the rejection", len(stub.requests) == 2, str(len(stub.requests)))
    check("first attempt sent thinking_config",
          stub.requests[0]["config"].thinking_config is not None)
    check("retry dropped thinking_config",
          stub.requests[1]["config"].thinking_config is None)
    check("run finished rather than erroring", result.error == "", result.error)
    check("narrative captured", result.narrative == "Done.", result.narrative)


def test_gemini_refusal_handled() -> None:
    """A blocked Gemini response reports, rather than raising on empty parts."""
    print("\n=== Gemini refusal handling ===")

    run, stub, result = _drive_gemini([_gemini_response([], finish_reason="SAFETY")])

    check("loop returned instead of raising", result is not None)
    check("refusal reported", "refusal" in result.error.lower(), result.error)
    check("not marked completed", result.completed is False)


def main() -> int:
    if not FIXTURE.exists():
        print(f"Fixture not found: {FIXTURE}")
        return 1

    test_prefix_is_stable()
    test_parallel_results_in_one_message()
    test_thinking_blocks_echoed()
    test_tool_error_flagged()
    test_refusal_handled()
    test_iteration_cap()
    test_gemini_translation()
    test_gemini_thinking_level_downgrade()
    test_gemini_refusal_handled()

    print()
    if _failures:
        print(f"FAIL — {len(_failures)} check(s) failed:")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("PASS — agent loop behaves correctly against the stub client.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
