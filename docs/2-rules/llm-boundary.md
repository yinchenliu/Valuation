# The LLM boundary

[Rule 1](rules.md) states the boundary in one line: the model extracts, it never
computes. This file states where the line sits in code, and what each side may do.

**Open this file when** you are changing anything in `ingestion/claude_extractor.py`, or
reviewing a change that adds a field to an extraction prompt.

---

## The line, in code

```
PDF bytes ──► claude_extractor.py ──► FinancialStatements + list[NonRecurringItem]
             ▲                      ▲
             │                      │
      the model works here    the line is here
                                    │
                                    ▼
             everything downstream is deterministic Python
```

`ingestion/claude_extractor.py` is the **only** file that may hold a model client, a
prompt, or an API key. Nothing under `analysis/`, `models/` or `api/` imports
`anthropic` or `google.genai`.

## What the model may return

Only values that are **printed on a page of the filing**, plus the locator that says
where.

| Pass | Returns | Source in the PDF |
|---|---|---|
| 1 — statements | I/S, C/F and B/S line items for the target years | the statement tables |
| 2 — non-recurring | candidate one-time items: description, amount, line item, direction, category | MD&A and the Notes |

Pass 2 receives the Pass 1 income statement summary as context. That is an **anchor**,
not a calculation input: it exists so the model cites items that reconcile to figures we
already hold, rather than inventing a line the statement does not have.

## What the model may never return

- a margin, a growth rate, a ratio, or an average
- a projection of any kind
- a discount rate, a beta, a terminal value
- a judgement phrased as a number ("a reasonable normalised margin is 32%")
- a figure it did not read off a page, including one it is confident about

**A model that is asked for one of these will answer.** That is the failure mode. It
does not refuse and it does not flag; it returns a plausible number in the right shape,
and the shape is what the parser checks.

## Where the two passes already cross the line

Two places, both live today. Both are findings, recorded here so they are not
rediscovered as new.

**`_validate_extracted_data` reconciles arithmetic** (`claude_extractor.py:240`). It
compares stated `gross_profit` against `revenue - cost_of_revenue` and reports a
percentage difference. That is deterministic Python checking the model's arithmetic,
which is correct and should stay. Note it is a **check**, not a repair: it must never
adjust a figure to make the reconciliation close.

**The parser subtracts D&A from other operating expense**
(`claude_extractor.py:479`):

```python
other_operating_expense=float(yr.get("other_operating_expense", 0))
                       - float(yr.get("depreciation_amortization", 0)),
```

This is a real accounting decision — whether the filing's "other operating expense"
already contains D&A — taken silently inside a parser, on values that each default to
zero. It belongs in `analysis/`, with its reasoning written down, and it must stop rather
than default. See [docs/9-reference/refactor-backlog.md](../9-reference/refactor-backlog.md).

## The one question for a reviewer

> **If the model returned a different number here, would any deterministic code
> notice?**

If the answer is no, and the field is not a figure printed in the filing, the boundary
has moved and the change is a finding.

---

## Related

- [rules.md](rules.md) — rule 1 and rule 5
- [docs/3-architecture/extraction.md](../3-architecture/extraction.md) — how the two
  passes are wired, and the multi-PDF routing
