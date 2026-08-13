"""Rendering the audit trail.

Every tool call the agent made, with its inputs and what came back. This is the
thing that makes the agentic path auditable rather than opaque: the old fixed
pipeline retained nothing at all, so there was no record of how a number was
reached beyond re-reading the code.
"""

from __future__ import annotations

import json

import pipeline

W = 70


def transcript_rows(run: pipeline.ValuationRun) -> list[dict]:
    """Flatten the run transcript into display-ready rows.

    Inputs and outputs are rendered to strings here rather than in the template —
    picking the interesting scalars out of a nested result is awkward in Jinja and
    unreadable when inlined.
    """
    rows = []
    for i, entry in enumerate(run.transcript, start=1):
        inputs = entry.get("inputs") or {}
        shown = {k: v for k, v in inputs.items() if v is not None}
        output = entry.get("output")

        rows.append({
            "n": i,
            "step": entry.get("step", ""),
            "kind": entry.get("kind", "pipeline"),
            "ok": entry.get("ok", True),
            "inputs_text": ", ".join(f"{k}={v}" for k, v in shown.items()),
            "output_text": entry.get("detail") or _summarise(output),
            "is_error": isinstance(output, dict) and "error" in output,
        })
    return rows


def _summarise(value) -> str:
    """One-line rendering of a tool result: the leading scalars, then list sizes."""
    if value is None:
        return ""
    if not isinstance(value, dict):
        return str(value)[:160]
    if "error" in value:
        return str(value["error"])

    parts: list[str] = []
    for key, item in value.items():
        if isinstance(item, bool):
            parts.append(f"{key}={'yes' if item else 'no'}")
        elif isinstance(item, (int, float)):
            parts.append(f"{key}={item:,}" if isinstance(item, int) else f"{key}={item:g}")
        elif isinstance(item, str):
            parts.append(f"{key}={item[:40]}")
        elif isinstance(item, list):
            parts.append(f"{key}[{len(item)}]")
        if len(parts) >= 5:
            break
    return ", ".join(parts)


def print_transcript(run: pipeline.ValuationRun) -> None:
    """Print the audit trail to the console."""
    print()
    print("=" * W)
    print("  AUDIT TRAIL")
    print("=" * W)
    print("  Every number above traces to one of these calls.\n")

    for row in transcript_rows(run):
        marker = " " if row["ok"] else "!"
        print(f"  {marker}{row['n']:>2}. {row['step']}")
        if row["inputs_text"]:
            print(f"        in : {row['inputs_text'][:160]}")
        if row["output_text"]:
            print(f"        out: {row['output_text'][:160]}")
    print()


def transcript_json(run: pipeline.ValuationRun) -> str:
    """Full transcript as JSON, for export or storage."""
    return json.dumps(
        {
            "run_id": run.run_id,
            "ticker": run.ticker,
            "company_name": run.company_name,
            "entries": run.transcript,
        },
        indent=2,
        default=str,
    )
