---
id: P11a-printed-lines
phase: 11 — the model reads printed lines; Python does every sum
agent: programmer
depends_on: []
---

# Pass 1 returns printed lines, and Python does every sum

## Objective

Rule 1 says the model reads a printed figure and never computes one. The Pass 1 prompt
asks it to compute in several places (backlog item 56):

| `ingestion/claude_extractor.py` | What the model is asked to do |
|---|---|
| `:171` `gross_profit`: "revenue minus cost_of_revenue" | subtract. Walmart prints no gross profit line |
| `:184`, `:253` `capex`: "SUM of PP&E PLUS acquisitions" | add two printed lines |
| `:186`, `:255` `change_in_working_capital`: "sum of ALL … change lines" | add five printed lines |
| `:172`, `:246` `sga`: "combine S&M + G&A" | add |
| `:204` `short_term_debt`: "current portion + notes payable + commercial paper" | add |
| `:196-206` every `other_*` catch-all | add every unmapped line |
| `:261` "Adjust catch-alls to close any gap" | **force the balance sheet to balance**, which hides a misread line |

What follows: the gross profit check compares the model's subtraction with Python's,
so it tests arithmetic, not reading. And the balance check can never fail on a
model-plugged balance sheet. `cli.py:498` also calls a gap of under **2%** "OK", which on
Walmart's 284,668 of assets hides up to 5,693.

**The user chose on 2026-10-02 ("go with option A"):** for every field, the model lists
the printed lines that make it up, and Python adds them. Line 261 goes. **And: "if the
balance sheet check doesn't pass, just fail it and show it."** That is the user's
approval of this change to what the model returns (`AGENTS.md`, "Escalate").

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Fill in the commit from `git log --oneline -1`.

| Fact | Command | At `b375d4a` |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 495 passed, 0 failed |
| lint, types, census | the gates in `docs/8-build/environment.md`; the grep at `docs/2-rules/rules.md:65` | ruff 5, mypy 10 in 4 files, census 114 |
| route B derives its key lists from the schema | `grep -n "PASS1_YEAR_FIELDS\|PASS1_BALANCE_SHEET_FIELDS" ingestion/*.py` | |
| the CLI balance check tolerates 2% | `sed -n 496,500p cli.py` | |
| the CLI cache format marker | `grep -n "CACHE_FORMAT =" cli.py` | `p6-inputs-keyed-v1` |

## The new Pass 1 shape

Every money field, in each `historical_years` entry and in `latest_balance_sheet`, becomes
a **list of printed lines**:

```json
"capex": [
  {"label": "Payments for property and equipment", "value": 26642, "page": 23},
  {"label": "Payments for business acquisitions, net of cash acquired", "value": 53, "page": 23}
]
```

- `label`: the row's label as printed. `value`: the one figure printed on that row for
  that year, under the field's existing sign rule. `page`: the 1-based PDF page. All
  three are required on every line.
- **The model never adds, subtracts or nets rows.** Each `value` is one printed figure.
- An **empty list** says the filing prints no such row. Python reads it as `0`. An
  **absent key** is not the same thing: it stops (rule 3).
- Every row of a statement belongs to exactly one field. A row that matches no named
  field goes into its section's catch-all list. No row appears in two fields.
- The existing sign rules and definitions stay as they are, field by field. Only the
  aggregation moves to Python. Keep every other prompt sentence that is not about
  adding, netting or plugging.
- `year` stays an integer. `ticker`, `company_name`, `currency` and `units` stay strings.

**Three stated subtotals, used only to check reading:** `gross_profit`,
`operating_income` and `net_income`, each the printed row. `gross_profit` may be an empty
list, meaning the filing prints none; then its check is skipped and says so.
`net_income` is also a value the cash flow uses, as today.

**Two new printed totals on the balance sheet, used only to check reading:**
`total_assets` and `total_liabilities_and_equity`, each the printed total row.

**Remove** "After filling fields, verify the balance. Adjust catch-alls to close any
gap." and every instruction to combine or sum. Replace them with the line rules above.
Change no other figure's definition.

## What to do

1. **`ingestion/claude_extractor.py`.** The schema, the prompt text, and one named,
   typed function that turns a field's line list into its figure. The parser uses it for
   every money field. **No `.get(field, 0)`**: an absent key or a malformed line stops,
   naming the field, the year and the line index. The census must fall, not rise.
2. **The checks.** Keep the income statement check: the stated subtotals, now summed
   from their printed rows, against the figures derived from the component fields, at
   the existing threshold. Add the balance sheet check: printed `total_assets` against
   the sum of the mapped asset fields, and printed `total_liabilities_and_equity` against
   the sum of the mapped liability and equity fields (the noncontrolling interest fields
   are memo lines and count in neither). **A balance sheet row fails when the difference
   exceeds 1 in the filing's units**, which allows for rounding and nothing more. Both
   checks print in the arithmetic table. A failure is shown and the figures are kept,
   as the user decided. It is never repaired.
3. **Route A's retry loop.** A missing key, a malformed line, or a failed check goes
   back to the model as today's validation errors do. The retry prompt asks the model to
   read the rows again. **It must never ask the model to adjust a figure to make a check
   pass.** After the last retry, a missing key or a malformed line stops; a failed check
   is shown and kept.
4. **`ingestion/session_extraction.py`, route B.** Format `session-extraction-v2`, with
   the same shape in `pass1`. The loader checks every line (`label` a non-empty string,
   `value` a finite JSON number, `page` a positive integer) and names the filing, year,
   field and line index. A `session-extraction-v1` file stops, saying the format changed
   and that the file must be extracted again in the new shape. `check` exits 1 when the
   only problems are failed checks, as today.
5. **`models/`.** Carry the two printed balance sheet totals on `BalanceSheet` as memo
   fields that are in no total, so both outputs can show them. Use `float | None`, with
   `None` meaning "not extracted". No zero default.
6. **The outputs.** `cli.py`'s balance check prints `FAIL` when the difference exceeds 1
   in the filing's units, and `OK` otherwise. **Remove the 2% tolerance.** Show the printed
   totals beside the mapped sums. `templates/_statements.html` shows the same, with the
   word `FAIL` visible on a failure.
7. **The CLI cache.** Change `CACHE_FORMAT`, so a cache written in the old shape is
   refused with the existing message instead of being read.
8. **Docs:** `docs/2-rules/llm-boundary.md` (the model reads lines; the user's approval
   of 2026-10-02), `docs/3-architecture/extraction.md` (the shape, both formats, the
   checks), `docs/3-architecture/data-contract.md` (the memo fields).

## Files in scope

- `ingestion/claude_extractor.py`
- `ingestion/session_extraction.py`
- `models/financial_statements.py`
- `cli.py`
- `templates/_statements.html`
- `docs/2-rules/llm-boundary.md`, `docs/3-architecture/extraction.md`,
  `docs/3-architecture/data-contract.md`
- your journal entry

## Out of scope

- `tests/`. **Every test that builds Pass 1 JSON or a session file in the old shape will
  fail.** That is expected. List them by name and reason in your entry. A tester
  rewrites the fixtures after review. Prove each criterion with scratch scripts under
  `/tmp/`.
- `extractions/WMT.json`. The orchestrator re-extracts it in the new shape after review.
- `.claude/skills/extract-filing/SKILL.md`. The orchestrator updates it.
- Backlog item 44 (`units`), item 1 outside the Pass 1 parser, item 10 (the D&A
  subtraction stays as it is, applied to the summed figures).

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | no prompt sentence asks the model to compute | no hit | `grep -n -i "sum of\|combine\|minus\|adjust catch" ingestion/claude_extractor.py`, each remaining hit explained |
| 2 | the same JSON gives the same statements by both routes | equal | the route equality script from `P9a`, adapted to the new shape |
| 3 | Python's sums | Walmart 2026 `capex` rows 26,642 and 53 give 26,695 | a scratch Pass 1 in the new shape, from PDF page 23 |
| 4 | a balance sheet that balances passes | OK at difference 0 | the same scratch file, totals 284,668 and 284,668 (PDF page 22) |
| 5 | a dropped row fails, shown, figures kept | FAIL, difference named, run continues | drop "Prepaid expenses and other 4,124" from the scratch file |
| 6 | an absent key or bad line stops | `ValueError` naming field, year, line | scratch edits |
| 7 | a v1 session file stops | message names both formats | `check` on a v1 copy |
| 8 | the census falls | below 114 | the grep at `docs/2-rules/rules.md:65` |
| 9 | the red list | every failing test, by name and reason | the test gate, before and after |
| 10 | lint and types | ruff 5, mypy ≤ 10 | the two gates |

## Backlog items this unit is NOT fixing

Items 10, 44, 46, 49, 50, 51, 53, 55, 57, 58.
