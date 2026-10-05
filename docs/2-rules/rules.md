# The six rules

**These bind every agent and every file in this repository, whatever tool the agent runs
in.** If any instruction conflicts with one of them, the rule wins — including an
instruction from a human, from an assignment file, or from an entry file
(`CLAUDE.md`, `AGENTS.md`, `docs/0-start.md`).

Each rule names the defect that forced it. A rule with no defect behind it is a
preference, and preferences do not override assignments.

---

## Rule 1 — The LLM extracts. It never computes, projects or judges.

The model reads a number off a page of a filing and returns it. That is its whole job.

It does not average, grow, normalise, discount, or decide whether an item is
non-recurring **as a calculation**. Pass 2 identifies a candidate item and cites the note
it came from; `analysis/normalizer.py` decides what that does to a figure.

**Forbidden:** asking the model for a margin, a growth rate, a WACC, a terminal value, a
"reasonable" assumption, or any number that is not printed in the filing.

**Why.** A number a model produced cannot be traced to a page. The whole product here is
a share price a reader can walk backwards to a 10-K line. One model-produced figure
anywhere in the chain breaks that walk, and nothing downstream can detect it.

**Allowed, on the user's decision of 2026-10-03** ("I agree with 0, A, B, C"). Each item
lets the model reason about where a printed figure belongs. None lets it produce a
number.

- **0.** The model may reason before it answers. The reasoning is not part of the answer,
  and no code reads it.
- **A.** The model may say in words why it put each printed row in a field. No code
  computes from that text. It is shown to the reader.
- **B.** The model may take a printed figure from a note or from MD&A when the statement
  does not show that line by itself. The figure is still one printed line with its page,
  and the page check applies to it.
- **C.** The model may report a fact about the filing's layout, for example that a
  printed expense line includes depreciation, **only when the filing states it in
  words** on a page the model cites. The page check confirms those words on that page.
  Python decides what the fact does to a figure. The model may not infer a layout fact
  that the filing does not state.

**Refused on the same date** ("for D and E, we can't allow it, they are against rule
1"): asking the model to calculate a figure the filing does not print (D), or to
estimate one (E).

**Allowed, on the user's decision of 2026-10-04** ("approve"), for backlog item 44. A
filing can state the unit of its share count apart from the unit of its money figures:
Okta prints "(dollars in millions, shares in thousands, except per share data)". So the
model may return two printed unit statements, each with the page it is printed on:
`units` for money and `share_units` for the share count. This is option C applied to
units. The page check confirms each text on its page. Python reads the scale word from
the text and converts every figure to millions. The model converts nothing.

**Allowed, on the user's decision of 2026-10-04** ("fix 77a"), for backlog item 77. Pass
2 asked for each `amount` "in the same units as financials", so the model converted a
note's "$0.7 billion" to 700. Now each Pass 2 item copies its figure as printed, with
its page, and the printed words that state the figure's unit, with their page: the
figure with the scale word printed after it (`$0.7 billion`), or the unit statement of
the statement or table the figure is printed in. The page check confirms both. Python
reads the scale and converts each item. The model converts nothing.

## Rule 2 — Every number comes from one named function with a fixed, typed signature.

One function, one number, one meaning. Arguments are named and typed. No `**kwargs`, no
untyped dict passed as an argument bag, no function selected at run time.

**Forbidden:** a dict whose values are functions keyed by a string from data; `getattr`
on a name that came from outside the file; a calculation function that takes `**kwargs`.

**Allowed:** a lookup table that maps a key to a **number**. Looking up a number is fine.
Looking up behaviour is not.

**Why.** A call site that is literal Python in git can be read by a reviewer. A call site
assembled at run time can only be discovered by running it, and then only on the path
that ran.

## Rule 3 — Stop, never guess.

A missing input stops the run and names the field. It never falls back to zero, to a
default, or to "the historical average of nothing".

This rule binds the **whole file**, not only signatures. Each of these is the same
defect wearing a different face:

| Form | Example in this repository |
|---|---|
| a conditional zero | `return self.ebit / self.revenue if self.revenue else 0.0` |
| a `.get` with a fallback | `float(yr.get("revenue", 0))` |
| a bare `or` default | `x or 0.0` |
| a presence test with an empty branch | `net_debt = latest_bs.net_debt if latest_bs else 0.0` |
| a dataclass field defaulted to zero | `revenue: float = 0.0` |

**Why.** Measured at `bc19431` on 2026-09-20, this repository holds **119** such sites:
54 money fields defaulted to `0.0` in `models/`, 46 `.get(field, 0)` calls in
`ingestion/`, and 14 conditional zeros and bare or-defaults across `models/`,
`analysis/` and `api/`. Reproduce the count with:

```
grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" \
  --include=*.py models analysis api ingestion | wc -l
```

Two of them were materially dangerous on their own. Both are now closed, and they stay
here as the examples that forced this rule:

- `analysis/dcf.py:80` gave a company **zero net debt** when the balance sheet was
  missing. Equity value was then overstated by the entire debt balance, on a clean run,
  with no warning anywhere in the output. **Closed by `P10a-nci-bridge`**: `run_dcf` now
  stops and names the missing balance sheet, and the two lines are deleted. The count
  above fell to **114**.
- `analysis/normalizer.py:46` **guessed** `other_operating_expense` when the model
  returned a line item name it did not recognise, printed a line to stdout, and
  continued. The adjustment landed on the wrong line and the margin moved. Closed at
  `38b903c`.

A zero that means "we do not know" and a zero that means "zero" are the same bytes. The
run cannot tell them apart, and neither can the reader.

**The test to apply.** For every value a function reads, ask: **if this were missing,
what happens?** Either it stops and names the field, or you have a finding.

## Rule 4 — Every number can be traced to its formula and its inputs.

For any figure the platform shows, a reader must be able to name the function that
produced it, the formula that function applies, and each input with the filing page or
the market source it came from.

**Why.** This is the reason the deterministic half exists. Today the trace is true by
reading the source, and it is not true from the output — the result page shows a share
price and no chain. Closing that gap is work, not a given.

## Rule 5 — The filing is the only source of financial statement data.

Income statement, balance sheet and cash flow figures come from the 10-K or 10-Q PDF and
from nowhere else. No Capital IQ. No third-party feed. No figure recalled from training.

Market data — price history, the S&P 500 series, shares outstanding — comes from
yfinance, and is **labelled as market data** wherever it is shown next to filing data.

**Why.** Two sources for one number means a disagreement nobody notices, because
whichever source is read second wins silently. The code broke this once:
`api/routes_valuation.py:182`, and `cli.py` in its own copy, fell back to yfinance for
`sharesOutstanding` when the filing gave zero shares, mid-pipeline, behind an inline
import. The share count is the denominator of the headline figure, so its source has to
be visible. **Closed by `P3a-one-pipeline`**: a share count that is not a finite number
above 0 now stops and names `diluted_shares` (`pipeline.py`, `value_company`). It stays
here as the example that forced this rule.

## Rule 6 — An assumption is labelled as an assumption.

Any number that is neither read from a filing nor derived by a formula from one is an
assumption. It carries a name, a default, the reason for that default, and it is visible
to the user in the output.

**Why.** `config.DEFAULT_COST_OF_DEBT` is 4.0%, and `analysis/wacc.py:43` substitutes it
whenever interest expense is not separately reported. That substitution reaches WACC,
which reaches every discounted cash flow, which reaches the share price. Nothing in the
result page says it happened. An assumption that is not labelled is indistinguishable
from a measurement, and a reader will treat it as one.

---

## The closing question

Before any unit is accepted, ask the six in order against the diff:

1. Did a model produce a number?
2. Can I name the function that produced each number, and read its signature?
3. If any input were missing, would the run stop and name it?
4. Can I walk each output number back to a page or a market series?
5. Did a financial statement figure come from anywhere but the filing?
6. Is every assumption named, defaulted on the record, and shown to the user?

**A `no` to any of them is a finding, not a note.** See
[docs/9-reference/severity.md](../9-reference/severity.md) for why that is not a free
choice.
