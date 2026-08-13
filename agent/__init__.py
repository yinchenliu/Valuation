"""Agentic orchestration for the valuation pipeline.

The LLM decides *which* deterministic tool to call and in what order. It never
produces a number itself — every figure in the output comes from a function in
`analysis/`, reached through a tool in `agent/tools.py`.
"""
