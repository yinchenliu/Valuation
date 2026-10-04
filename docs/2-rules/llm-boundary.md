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

**Reasoning ahead of answers (Rule 1 option 0).** Option 0 is in force for route A from
`P14b-reasoning`: the model may reason before it answers, via adaptive thinking
(`thinking={"type": "adaptive"}`) with effort configured in `config.EXTRACTION_EFFORT`
(defaulting to `"high"`). The reasoning is not part of the answer, and no code reads
a thinking block, prints it, or logs it; only text blocks (`type == "text"`) are parsed.

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

**Pass 1 returns two printed unit statements, and Python reads the scale.** `units` is
the words that state the unit of the money figures, exactly as printed, with the page
they are printed on (`{"printed": "(in thousands, except per share data)", "page":
29}`); `share_units` is the same for the diluted share count, which a filing can print
on another scale (Okta: "(dollars in millions, shares in thousands, except per share
data)"). Approved by the user on 2026-10-04 ("approve", backlog item 44): option C
applied to units. The page check confirms each text on its page, as a whole printed
statement (a fragment such as `(in thousands)` of a longer statement is not
confirmed), and on a page of the figures it governs (`units` on a page the income
statement's lines cite, `share_units` on that page or the diluted share count's); a
statement not confirmed stops the run. `claude_extractor.py:printed_scale` reads the scale word in
each text, and `convert_filing_to_millions` converts every figure once. **The model
returns no scale word of its own and converts nothing**: the prompt tells it to copy
every figure as printed and never convert one. Before `P14a`, `units` was a free
string no code read, so a filing printed in thousands reached the valuation as
millions.

Pass 2 receives the Pass 1 income statement summary as context. That is an **anchor**,
not a calculation input: it exists so the model cites items that reconcile to figures we
already hold, rather than inventing a line the statement does not have. It shows the
figures as printed, before the conversion to millions, so the model sees the filing's
own units.
Since `P14b` (backlog item 77, user decision "fix 77a" on 2026-10-04), Pass 2 no longer asks for
`amount` in the "same units as financials". Each Pass 2 item copies its figure as printed,
with its `page`, and copies the unit words as printed (`units.printed`) with `units.page`
(either inline words such as `"$0.7 billion"` on the same page, or the unit statement of
the statement or table such as `"(Amounts in millions, except per share data)"` on the same
page or the page before). The page check confirms both figure and unit text on their
pages. Python (`pass2_amount_scale`) reads the scale and converts each item individually.
The model converts nothing.

## What the model may never return

- a margin, a growth rate, a ratio, or an average
- a projection of any kind
- a discount rate, a beta, a terminal value
- a judgement phrased as a number ("a reasonable normalised margin is 32%")
- a figure it did not read off a page, including one it is confident about
- a figure converted to another unit, or a unit (a scale word) the filing does not
  print. Pass 1 and Pass 2 ask for neither: each figure is copied as printed, and its
  unit statement is copied as printed. Python reads the scale word and converts the
  figure (P14a for Pass 1, P14b for Pass 2; user decision "fix 77a" on 2026-10-04)

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
added, and **states no amount**: told the gap, a model can write a row of that size.
A failure is shown and the figures are kept (the user, 2026-10-02: "if the
balance sheet check doesn't pass, just fail it and show it").

**The page check looks for each printed line on the page it cites** (`P12a`, backlog
item 59). Both routes open the filing's PDF with `pdfplumber` and look, on the cited
page, for one text line holding the line's label and its figure
(`claude_extractor.py:printed_line_on_page`); a label may wrap onto the next text line,
but a label printed whole on a neighbouring row never takes this row's figure. A line
not found, a page beyond the PDF, or a page with no text layer is a failed check,
retried, shown and kept exactly as an arithmetic failure is; a page that was not looked at never reads as confirmed (rule 3).
A PDF `pdfplumber` cannot open stops the run. So a row the filing never printed, written
to close a gap, is now caught, **within three limits**: the check confirms a row is
printed with that figure, not that the figure sits in the right year's column; a label
is matched as text, not as a whole printed row, so a short label can be found inside a
longer printed label, and a label that runs from one printed row into the next is found
with the figure of either row (a label the filing does not print); and it does not detect
a real row listed under two fields. The retry for a line not found names it by
label, field and page and states no value.
[docs/3-architecture/extraction.md](../3-architecture/extraction.md), "The page check",
holds the rule.

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
