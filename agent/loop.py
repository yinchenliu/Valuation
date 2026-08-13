"""The agentic loop.

The model is given the deterministic valuation tools and decides which to call,
in what order, and when to revisit one. It is explicitly *not* given a numbered
procedure — encoding the old fixed sequence in the system prompt would just
recreate the straight-line pipeline in prose.

Either Claude or Gemini can drive it. There is deliberately only one loop: both
providers are reached through the same `messages.create(...)` surface, with
`gemini_client` adapting Gemini onto it. Forking per provider would mean keeping
the tool wiring, the parallel-result batching and the refusal handling correct in
two places, and would weaken the parity guarantee that both orchestration paths
produce identical numbers.

A manual `while stop_reason == "tool_use"` loop is used rather than the SDK's
beta tool runner. The reason is prompt caching: the loop keeps one message list
and one frozen tool/system prefix across every turn, so each turn re-reads the
cached prefix instead of re-billing it (Anthropic via the explicit cache
breakpoint below, Gemini via implicit prefix caching). It also lets the
transcript record each turn's usage, which is how the cache-effectiveness check
is verified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import llm_client
import pipeline
from agent import tools
from models.valuation import ProjectionAssumptions

# Per-provider defaults, overridable per call and via the matching env var. On
# Vertex the Claude ID is the same bare string — no provider prefix.
DEFAULT_MODELS = {
    "claude": "claude-opus-5",
    "gemini": "gemini-3.6-flash",
}
MODEL_ENV_VARS = {
    "claude": "CLAUDE_AGENT_MODEL",
    "gemini": "GEMINI_AGENT_MODEL",
}
MAX_TOKENS = 16000


def resolve_model(provider: str, model: str | None = None, model_env_var: str | None = None) -> str:
    """The model ID a run will actually use, so callers can report it up front."""
    import os

    env_var = model_env_var or MODEL_ENV_VARS[provider]
    return model or os.environ.get(env_var) or DEFAULT_MODELS[provider]

SYSTEM_PROMPT = """\
You are an equity research analyst running a discounted cash flow valuation.

The financial statements have already been extracted from the company's filings.
Your job is to get from those statements to a defensible implied share price, and
to say how much confidence it deserves.

You have deterministic tools for every calculation. They are the only source of
numbers: you decide which to call and in what order, they do the arithmetic. Never
state a figure you did not get back from a tool, and never do the arithmetic
yourself — a number you computed in your head is not auditable and does not belong
in the output.

Work in whatever order the filing calls for. Inspect what was extracted before you
value it. If something looks wrong, investigate it rather than proceeding as though
it were fine. If a tool returns an error, read it — most are recoverable by
adjusting an input and calling again.

Judgement is yours to exercise and to justify:

- Assumptions left null are derived from the company's own history. That is usually
  the right default, but not always — a trailing average through an unusual year
  can be a poor guide to the future. If you override one, say why in your summary.
- A low regression r-squared means beta is poorly identified by this stock's price
  history, and the resulting cost of equity is weakly supported.
- A terminal value that dominates enterprise value means the answer rests mostly on
  the perpetuity assumption rather than the forecast period.
- Historical FCFF is a useful reality check on the projections.

When you have an implied share price, stop calling tools and write a short summary:
what the valuation says, which assumptions drive it, and what would most change the
answer. Be direct about weaknesses. A caveated number is more useful than a
confident one that hides its own fragility.
"""


@dataclass
class AgentResult:
    """Outcome of one agentic run."""

    completed: bool
    narrative: str = ""
    iterations: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    stop_reason: str = ""
    error: str = ""
    provider: str = ""
    model: str = ""
    backend: str = ""
    usage_by_turn: list[dict] = field(default_factory=list)


def _build_kickoff(run: pipeline.ValuationRun, overrides: ProjectionAssumptions | None) -> str:
    fin = run.raw_financials
    lines = [
        f"Value {fin.company_name or run.ticker} ({run.ticker}).",
        "",
        f"Extracted fiscal years: {', '.join(str(y) for y in fin.years)}.",
        f"Non-recurring items identified: {len(run.non_recurring)}.",
    ]
    if overrides is not None:
        requested = {
            "projection_years": overrides.projection_years,
            "terminal_growth_rate": overrides.terminal_growth_rate,
            "revenue_growth_rates": overrides.revenue_growth_rates or None,
            "operating_margin": overrides.operating_margin,
            "tax_rate": overrides.tax_rate,
            "da_pct_revenue": overrides.da_pct_revenue,
            "capex_pct_revenue": overrides.capex_pct_revenue,
            "nwc_pct_revenue": overrides.nwc_pct_revenue,
            "beta_override": overrides.beta_override,
            "risk_free_rate": overrides.risk_free_rate,
            "equity_risk_premium": overrides.equity_risk_premium,
            "cost_of_debt_override": overrides.cost_of_debt_override,
        }
        explicit = {k: v for k, v in requested.items() if v is not None}
        if explicit:
            lines += [
                "",
                "The user supplied these assumptions explicitly — use them unless you find "
                "a concrete reason not to, and flag it if you deviate:",
                json.dumps(explicit, indent=2),
            ]
    return "\n".join(lines)


def run_agentic_valuation(
    run: pipeline.ValuationRun,
    overrides: ProjectionAssumptions | None = None,
    model: str | None = None,
    effort: str = "high",
    max_iterations: int = 30,
    verbose: bool = False,
    provider: str | None = None,
    model_env_var: str | None = None,
) -> AgentResult:
    """Let the model drive the valuation for an already-extracted run.

    `provider` picks the model family — "claude", "gemini", or None to resolve it
    from `AGENT_PROVIDER` and the available credentials.

    Extraction happens before this is called: it is the expensive, slow, and
    genuinely fixed part of the process, so there is nothing for an agent to
    decide about it.
    """
    run.require("raw_financials")
    tools.bind_run(run)

    # Claude (first-party or on Vertex AI) or Gemini, whichever the environment
    # resolves to. Both clients speak the same request/response shape from here on.
    try:
        resolved_provider = llm_client.resolve_agent_provider(provider)
        client = llm_client.build_agent_client(resolved_provider, max_retries=4)
    except llm_client.ClientConfigError as exc:
        raise pipeline.PipelineError(
            f"{exc}\n\nOr drop --agentic to use the deterministic pipeline."
        ) from exc
    messages: list[dict] = [
        {"role": "user", "content": _build_kickoff(run, overrides)}
    ]

    resolved_model = resolve_model(resolved_provider, model, model_env_var)
    result = AgentResult(completed=False, provider=resolved_provider,
                         model=resolved_model,
                         backend=llm_client.describe_agent_backend(resolved_provider))

    # Frozen prefix: the tool list and system prompt are byte-identical on every
    # turn, so the cache breakpoint on the system block covers tools + system and
    # each subsequent turn reads it rather than re-processing it. Gemini caches a
    # repeated prefix implicitly and ignores the breakpoint, so the stability is
    # what matters on both paths, not the annotation.
    system_blocks = [{
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }]

    for iteration in range(1, max_iterations + 1):
        result.iterations = iteration
        try:
            response = client.messages.create(
                model=resolved_model,
                max_tokens=MAX_TOKENS,
                system=system_blocks,
                tools=tools.TOOL_SPECS,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": effort},
            )
        except Exception as exc:  # noqa: BLE001
            result.error = f"{type(exc).__name__}: {exc}"
            return result

        usage = response.usage
        turn_usage = {
            "iteration": iteration,
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        }
        result.usage_by_turn.append(turn_usage)
        result.input_tokens += turn_usage["input_tokens"]
        result.output_tokens += turn_usage["output_tokens"]
        result.cache_read_tokens += turn_usage["cache_read_input_tokens"]
        result.cache_write_tokens += turn_usage["cache_creation_input_tokens"]
        result.stop_reason = response.stop_reason or ""

        # Check stop_reason before touching content: a refusal returns an empty
        # content list, and indexing block 0 would raise.
        if response.stop_reason == "refusal":
            result.error = "The model declined to continue (stop_reason=refusal)."
            return result

        # Preserve the full content list, including thinking blocks — they must be
        # echoed back unchanged for the next turn on the same model.
        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        texts = [b.text for b in response.content if getattr(b, "type", None) == "text"]

        if verbose:
            for text in texts:
                if text.strip():
                    print(f"  [agent] {text.strip()}")
            for block in tool_uses:
                shown = {k: v for k, v in (block.input or {}).items() if v is not None}
                print(f"  [tool]  {block.name}({json.dumps(shown, default=str) if shown else ''})")

        if not tool_uses:
            result.completed = run.dcf is not None
            result.narrative = "\n\n".join(t.strip() for t in texts if t.strip())
            return result

        tool_results = []
        for block in tool_uses:
            result.tool_calls += 1
            payload = tools.call(block.name, block.input or {})
            is_error = '"error"' in payload[:40]
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": payload,
                **({"is_error": True} if is_error else {}),
            })
            if verbose and is_error:
                print(f"  [tool]  -> {payload[:200]}")

        # All results for a turn go back in a single user message; splitting them
        # trains the model out of making parallel calls.
        messages.append({"role": "user", "content": tool_results})

    result.error = f"Stopped after {max_iterations} iterations without finishing."
    result.completed = run.dcf is not None
    return result
