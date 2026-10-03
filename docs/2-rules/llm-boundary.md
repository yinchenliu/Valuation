# The LLM boundary

[Rule 1](rules.md) states the boundary in one line: the model extracts, it never
computes. This file states where the line sits in code, and what each side may do.

**Open this file when** you are changing anything in `ingestion/claude_extractor.py`, or
reviewing a change that adds a field to an extraction prompt.

---

## The line, in code

There are two sources of model text, and they meet at the parser.

```
 route A                                     route B
 PDF bytes ──► API call                      PDF ──► Claude Code session
 (claude_extractor.py)                       (reads pages via `locate` / `text`)
        │                                           │
        │ Pass 1 / Pass 2 JSON text                 │ the same JSON, stored in a
        │                                           │ session file (session_extraction.py)
        ▼                                           ▼
        └──────────────► parse_pass1 / parse_pass2 ◄┘
                         (claude_extractor.py)
                                 │   ▲
                                 │   the line is here
                                 ▼
          merge_filing_extractions ──► FinancialStatements + list[NonRecurringItem]
                                 │
                                 ▼
             everything downstream is deterministic Python
```

Above the line, a model reads a page — over the API in route A, inside a Claude Code
session in route B. Both answer the same prompts (`pass1_prompts`, `pass2_prompts`) with
the same JSON, and both are parsed by the same two functions. **The boundary is the same
line in both routes.** A session is bound by rule 1 exactly as the API model is.

`ingestion/claude_extractor.py` is the **only** file that may hold a model client, a
prompt, or an API key. `ingestion/session_extraction.py` holds none of them: it gets the
prompts from the wrappers and parses through them. Nothing under `analysis/`, `models/`
or `api/` imports `anthropic` or `google.genai`.

Since `P11a` both routes are equally strict about absence: every key the Pass 1 schema
names must be present, and every printed line well formed (`pass1_problems`), before
any figure is formed. An empty list is accepted and reads as 0 for a component field.
On a check row it is never a printed 0: `gross_profit` and `operating_income` skip their
check as "not printed", the two balance sheet totals fail as "not extracted", and an
empty `net_income` stops, because it starts the cash flow statement (`P11a` round 2).

## What the model may return

Only values that are **printed on a page of the filing**, plus the locator that says
where. In route B the locator is recorded: `pages_read` names the 1-based PDF pages read
for each pass, and is printed beside the figures, never computed from.

**Pass 1 returns printed lines, and Python adds them.** Every Pass 1 field is a list of
the rows that make it up, each `{"label", "value", "page"}`: the label as printed, the
one figure printed on that row, and its 1-based PDF page.
`claude_extractor.py:figure_from_printed_lines` adds a field's values, and it is the
only place a Pass 1 figure is formed. The user decided this on 2026-10-02 ("go with
option A", backlog item 56), which is the approval `AGENTS.md` requires for a change to
what the model returns. Before it, the prompt asked the model to add printed lines
together (capex, the working capital change, SG&A, short-term debt, every catch-all), to
subtract for gross profit, and to "adjust catch-alls to close any gap" on the balance
sheet. All of that is gone. The check rows (`gross_profit`, `operating_income`,
`net_income`, `total_assets`, `total_liabilities_and_equity`) are each one printed row.

| Pass | Returns | Source in the PDF |
|---|---|---|
| 1 — statements | I/S, C/F and B/S line items for the target years | the statement tables |
| 2 — non-recurring | candidate one-time items: description, amount, line item, direction, category | MD&A and the Notes |

Pass 1's balance sheet keys `noncontrolling_interest_nonredeemable` and
`noncontrolling_interest_redeemable` were added by `P10a` on the user's approval of
2026-10-02 ("item 48: fix"), as `AGENTS.md` requires for a new field. Each is one printed
line; the filing prints no total, so `analysis/dcf.py:total_noncontrolling_interest` adds
them, not the model. The keys `total_assets` and `total_liabilities_and_equity` were
added by `P11a` under the decision above; they are read only to check the balance sheet.

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

## The checks, and the one place a pass still crosses the line

**`_validate_extracted_data` checks the reading.** It compares each printed subtotal and
total with Python's sum of the lines mapped under it: gross profit (skipped when the
filing prints none), operating income and net income at 0.5%, and the balance sheet's
two printed totals at 1 in the filing's units. Since `P11a` the subtotal is a row the
model read and the components are rows the model read, so the check tests **reading**,
not the model's arithmetic. It is a **check**, not a repair: it never adjusts a figure,
and route A's retry asks the model to read the rows again, never to change a value so a
check passes. That retry sends the PDF with it: a model told to re-read a filing it
cannot see can only make the rows up. It names each failed check and the rows Python
added, and **states no amount**: told the gap, a model can write a row of that size,
and no check could tell it was never printed. A failure is shown and the figures are kept (the user, 2026-10-02: "if the
balance sheet check doesn't pass, just fail it and show it").

**The parser subtracts D&A from other operating expense**
(`claude_extractor.py:_parse_financials_response`):

```python
other_operating_expense=f["other_operating_expense"] - f["depreciation_amortization"],
```

This is a real accounting decision — whether the filing's "other operating expense"
already contains D&A — taken silently inside a parser. Since `P11a` both values are sums
of printed lines and neither can default to zero. It still belongs in `analysis/`, with
its reasoning written down. See
[docs/9-reference/refactor-backlog.md](../9-reference/refactor-backlog.md), item 10.

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
