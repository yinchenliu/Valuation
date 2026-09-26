# Extraction

`ingestion/claude_extractor.py`, 1,023 lines, the largest file in the repository. It is
the **only** file that may hold a model client, a prompt, or an API key.

What the model may and may not return is owned by
[2-rules/llm-boundary.md](../2-rules/llm-boundary.md). This file owns **how the passes
are wired**.

---

## The two passes

Per PDF, two focused calls rather than one broad one.

| | Pass 1 — statements | Pass 2 — non-recurring |
|---|---|---|
| Reads | the statement tables | MD&A and the Notes |
| Prompt emphasises | number precision, arithmetic reconciliation | citation to a note, one-time nature |
| Returns | I/S, C/F, optionally B/S, for target years | `list[NonRecurringItem]` |
| Context given | the PDF | the PDF **plus** Pass 1's I/S summary |
| Schema | `_FINANCIALS_SCHEMA` | `_NRI_SCHEMA` |
| Builder | `_build_financials_prompt` | `_build_nri_prompt` |
| Runner | `_run_financials_pass` | `_run_nri_pass` |

**Why two.** Reading a table and reasoning over footnotes are different tasks. One
prompt that asks for both does neither well, and a failure in one half corrupts the
other. Splitting them also means Pass 2 can be given Pass 1's output as an anchor.

**The anchor is context, not arithmetic.** `_build_is_summary` formats the extracted
income statement so Pass 2 cites items that reconcile to figures already held, rather
than inventing a line the statement does not have.

## The PDF goes to the model whole

No `pdfplumber` text extraction in the path. The raw bytes are base64-encoded
(`_read_pdf_bytes`) and sent for native document ingestion, so the model sees the table
layout rather than a flattened text rendering.

`pdfplumber` is still in `requirements.txt`. Nothing in the extraction path imports it.

## Providers

```python
_DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-6",
    "gemini": "gemini-3.1-pro-preview",
}
```

`_call_llm` dispatches to `_call_claude` or `_call_gemini`. `_resolve_provider`
(`:815`) picks the model ID and reads the key, and **raises when the key is absent** —
naming the variable and where to put it. That is the correct shape for a missing input,
and the rest of the codebase should copy it.

> **Defect — the provider changes with the number of files uploaded.** Measured at
> `bc19431`:
>
> | Function | Default provider |
> |---|---|
> | `extract_financials` (`:848`) | `"gemini"` |
> | `extract_multi_year` (`:901`) | `"claude"` |
> | `cli.py --provider` (`:93`) | `"gemini"` |
>
> `api/routes_valuation.py:_extract_from_files` calls the first for one filing and the
> second for several, and passes **no** `provider` argument either way. So uploading one
> PDF uses Gemini and uploading two uses Claude — a different model, a different key, and
> different extraction output for the same company, with nothing in the UI saying so.
> Recorded as backlog item 13.

> **Note.** `claude-sonnet-4-6` is not a current model ID. Verify against the Claude API
> model list before relying on the Claude provider.

## Multi-PDF year routing

`extract_multi_year` exists because a 10-K holds comparative years. Extracting every
year from every filing would call the model three times for the same figures and produce
three versions of each.

The routing, for filings sorted ascending by fiscal year:

| Filing | Years extracted | Balance sheet? |
|---|---|---|
| **oldest** | **all** — picks up its comparatives | no |
| each middle | its primary year only | no |
| **newest** | its primary year only | **yes** |

```
2023 10-K → 2023, 2022, 2021    (no B/S)
2024 10-K → 2024                (no B/S)
2025 10-K → 2025                (with B/S)
```

**Two consequences that reach the rest of the pipeline:**

1. **A balance sheet exists for exactly one year.** `get_balance_sheet(y)` returns
   `None` for every other year **by design**, not by failure. This is the root of
   [backlog item 2](../9-reference/refactor-backlog.md) and of 16 `union-attr` type
   errors. Any call site must handle it, and handling it means stopping, not
   substituting zero.
2. **A single filing takes a different path entirely.** `extract_multi_year` delegates
   straight to `extract_financials` when given one filing — which is where the provider
   divergence above becomes reachable.

## Validation

`_validate_extracted_data` (`:240`) reconciles the model's arithmetic against its own
figures:

- stated `gross_profit` against `revenue − cost_of_revenue`
- stated `operating_income` against the computed EBIT
- stated `net_income` against the computed one

It reports a **percentage difference**. It is deterministic Python checking the model's
work, which is correct and must stay.

**It is a check, not a repair.** It must never adjust a figure to close a
reconciliation. A reconciliation that fails is a reason to stop, not to edit.

The stated values (`gross_profit`, `operating_income`, `net_income`) are read **only for
this comparison**. They are never stored — those are derived properties on
`IncomeStatement`. See [data-contract.md](data-contract.md).

## Known defects in this file

Full detail in [9-reference/refactor-backlog.md](../9-reference/refactor-backlog.md).

| | |
|---|---|
| **46 `.get(field, 0)` calls** | a figure the model omitted becomes `0.0` and flows through the whole valuation. Item 1 |
| **D&A subtracted inside the parser** (`:479`) | an accounting decision taken silently in a parser, on two defaulted values. Item 10 |
| **16 mypy errors** | the most of any file. Item 11 |
| **`except Exception`** (`:795`) | collapses every Pass 2 failure into one string. Item 8 |
| **Provider default divergence** | above. Item 13 |
