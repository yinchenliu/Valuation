---
id: P8b-statements-ui
phase: 8 — show the chain
agent: programmer
depends_on: [P8a-statements-data]
---

# Render the parsed statements and every adjustment on both web pages

## Objective

`cli.py` prints seven blocks that the web application does not: the income statement,
the cash flow statement, the balance sheet with its balance check, the non-recurring
items that were **applied**, the GAAP to non-GAAP reconciliation, the historical FCFF
table, and the `(override)` tag on each assumption ratio. `templates/` shows only the
items that were **withheld**.

So a reader on the web can see what was excluded from a valuation and cannot see what
was included in it. That is the inversion of what a reader needs, and it is the rule 4
gap named in `docs/2-rules/rules.md:92`.

`P8a-statements-data` made all six values reachable from both route contexts. This unit
renders them. When it is done, `GET /assumptions` and `POST /valuation` each show all
seven blocks, and a reader can walk the implied share price back to a parsed line
without opening a terminal.

## What is already true — verify, do not redo

Re-measure each of these and **stop and report** rather than editing around a
disagreement. Fill in the commit from `git log --oneline -1` before you start.

| Fact | Command |
|---|---|
| the four gates stand where `STATUS.md` records them | the four commands in `docs/8-build/environment.md` |
| six context keys reach both templates | `grep -n "raw_financials\|applied_non_recurring\|historical_fcff\|assumption_sources" api/routes_valuation.py` |
| no template loads JavaScript | `grep -rn "<script" templates/` returns nothing |
| `static/charts.js` is one comment line and no template references it | `cat static/charts.js` and `grep -rn "charts.js" templates/` |

**A Jinja `{% include %}` shares the parent's context by default.** So one included file
can read `financials`, `raw_financials` and the rest from either page, with no argument
passing. Verify this before you design around it.

## What to do

### The shape

1. **Write one new file, `templates/_statements.html`, holding all seven blocks.** Both
   pages include it. Two copies of a table is the shape of backlog item 7, and a figure
   corrected in one copy and not the other is the defect that item records.

2. **Include it from `templates/assumptions.html` and from
   `templates/valuation_result.html`.** On the result page, place it **after** the DCF
   bridge and **before** the existing "What in this valuation was not measured" block,
   so the chain reads: price, then cost of capital, then the projection, then the
   parsed inputs it all came from.

3. **Use `<details>` and `<summary>` to collapse the three large statements.** It is
   plain HTML and every browser supports it. **Add no JavaScript.** Set one variable in
   the including template, `statements_open`, and use it on the three statement blocks
   only:

   - `templates/assumptions.html` sets it true. Reviewing the extraction is the whole
     purpose of that page.
   - `templates/valuation_result.html` sets it false. That page is already 242 lines.

   The adjustments, the reconciliation and the historical FCFF are short. Leave those
   three always open.

### The seven blocks

4. **Income statement**, one column per year in `financials.years`, in this row order,
   matching `cli.py:492-512` so a reader can compare the two outputs line by line:
   Revenue, COGS, Gross Profit, Gross Margin, SG&A, R&D, D&A, Other OpEx, EBIT,
   Operating Margin, Interest Expense, Other Non-Operating, EBT, Tax Expense, Net
   Income, Effective Tax Rate, Diluted Shares, EPS.

   Render the **normalised** statements, from `financials`. Head the block with the word
   **adjusted**, because that is what it is.

5. **Cash flow statement**, one column per year, matching `cli.py:521-539`: Net Income,
   D&A, SBC, Change in WC, Other Operating, CFO, CapEx, Acquisitions, Other Investing,
   CFI, Debt Issued, Debt Repaid, Shares Issued, Buybacks, Dividends, Other Financing,
   CFF.

6. **Balance sheet**, latest year only, matching `cli.py:555-582`. Assets in one column
   group, liabilities and equity in the other. Then three rows: Total Assets, Total
   Liabilities + Equity, and the difference between them. Then Total Debt, Net Debt and
   Net Working Capital.

7. **Non-recurring items applied**, from `applied_non_recurring`. Same six columns as
   the existing excluded table at `valuation_result.html:158-181`: Year, Amount, Line
   item, Direction, Description, Source. Head it **APPLIED — these moved the figures
   above**, and say in one sentence that an item here changed the income statement.

   When the list is empty, print `No non-recurring item was applied.` **Never an empty
   table with no sentence** — a table with no rows reads as a rendering failure.

8. **GAAP to non-GAAP reconciliation**, one row per year: EBIT as reported, EBIT
   adjusted, and the difference. **The difference is computed in the route, not in the
   template.** See step 12.

   When no year moved, print `No adjustment reached the income statement.` in as many
   words.

9. **Historical FCFF**, one row per year, from `historical_fcff`. Columns: Year,
   Revenue, CFO, After-tax interest, CapEx, FCFF, FCFF margin. A year whose record says
   it was not computable prints the words in every value cell. See step 10.

10. **The assumption source label**, from `assumption_sources`. On
    `valuation_result.html` add it to the existing "Assumptions Used" table at `:127`,
    one provenance line under each of the six ratios, in the same row as the figure.
    On `assumptions.html` add a short table of the same six, because that page shows the
    derived defaults and today says nothing about where they came from. Rule 6.

### The rules that bind every cell

11. **A value that was not extracted prints the words `not extracted`.** Never `0`,
    never `0.0`, never an empty cell, never a dash. This is rule 3 wearing its display
    face: a zero that means "we do not know" and a zero that means "zero" are the same
    bytes, and a reader cannot tell them apart either.

    `cli.py` breaks this three times and **you must not copy it**: `:508` divides by
    revenue with a conditional zero, `:522-538` substitutes a blank string for a missing
    cash flow statement seventeen times, and `:593` divides by total assets with a
    conditional zero.

    In practice this means: test `financials.get_cash_flow(y)` for `None` and print the
    words in that year's cells. Do the same for a missing income statement and a missing
    balance sheet.

12. **The template formats. It does not do arithmetic.** The one exception already
    established in this repository is multiplying a rate by 100 to show a percentage,
    at `valuation_result.html:63` and eleven other places. Follow that and nothing more.

    Two figures currently have nowhere to come from, so this unit adds them:

    - **The reconciliation delta.** Add a per-year record to both route contexts under
      the key `ebit_reconciliation`, each holding the year, the as-reported EBIT, the
      adjusted EBIT and the difference. Build it in `api/routes_valuation.py` from
      `raw_financials` and `financials`. A year missing from either side carries a named
      field saying so — never a zero delta.
    - **The balance check difference.** Add one property to `BalanceSheet` in
      `models/financial_statements.py`, beside `total_debt` and `net_debt`:

      ```
      balance_check_difference = total_assets - (total_liabilities + total_equity)
      ```

      One subtraction. **No division and no percentage**, which is what removes the
      conditional zero at `cli.py:593` rather than reproducing it. Print the difference
      in `$M` beside total assets, and let the reader judge the scale.

13. **Every money column header says `$M`.** Every money figure is in millions;
    `docs/4-conventions/units-and-signs.md` owns this and it is where the
    three-orders-of-magnitude errors come from. Share counts are in millions too. EPS
    and share prices are per share and carry no `$M`.

14. **Preserve the sign convention.** `capital_expenditures` is typically negative
    (`models/financial_statements.py:234`). `cli.py:825` prints `abs()` of it in the
    projection table. Show the value as stored and say `(negative = outflow)` in the
    column header. Do not silently flip a sign to make a column look tidy.

### The stylesheet

15. **Lift the inline provenance style into a class.** `valuation_result.html:10`
    defines a `PROV` variable holding an inline style string, and its own comment says a
    later unit that owns `static/style.css` should lift it into a `.provenance` rule.
    This unit owns that file. Add `.provenance` to `static/style.css`, replace every use
    of `PROV`, and delete the `{% set PROV = ... %}` line.

16. **Add the classes the new tables need to `static/style.css`.** Keep the existing
    visual language: the file already defines `.data-table`, `.section`, `.card`,
    `.highlight`, `.summary-card`, `.alert`. Reuse them. Add only what a wide multi-year
    table needs — a right-aligned numeric cell, a sticky first column, and a horizontal
    scroll container.

## Files in scope

- `templates/_statements.html` — **new**
- `templates/valuation_result.html`
- `templates/assumptions.html`
- `static/style.css`
- `api/routes_valuation.py` — **only** to add the `ebit_reconciliation` key to both
  contexts, per step 12. Nothing else in this file.
- `models/financial_statements.py` — **only** to add the one `balance_check_difference`
  property, per step 12. Nothing else in this file.

**Nothing else.** Work outside this list is a review finding, even if the change is
good.

## Out of scope

- `cli.py` — it already prints all seven blocks and is the reference for **what** to
  show. It is **not** a reference for how, and it holds three rule 3 sites named in
  step 11. Do not touch it, and do not copy from it.
- `templates/base.html` and `templates/upload.html` — no change is needed. If you
  believe one is, stop and report it.
- `static/charts.js` — one comment line, loaded by nothing. Leave it.
- `analysis/`, `ingestion/` — no signature there needs to change.
- `tests/` — the tester writes it. Prove your criteria with inline
  `.venv/Scripts/python.exe -c "..."` commands and paste the output into your log entry.

## Done-criteria

Criteria 5 to 10 are measured by rendering a page through `TestClient` with
`_extract_from_files` monkeypatched to return a **two-year stub** built by hand in the
command: two income statements, two cash flow statements, one balance sheet, and three
non-recurring items — one `high`, one `medium`, one `low`. Paste the command and its
output into your log entry.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the test gate is unchanged | `145 passed` | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | no new lint error | `Found 5 errors`, all `BLE001` | `.venv/Scripts/python.exe -m ruff check .` |
| 3 | no new type error | `Found 14 errors in 4 files` or fewer | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` |
| 4 | still no JavaScript anywhere in `templates/` | 0 matches | `grep -rn "<script" templates/` |
| 5 | `GET /assumptions` renders all seven block headings | 7 matches | one grep per heading over the rendered body |
| 6 | `POST /valuation` renders all seven block headings | 7 matches | same |
| 7 | a year with no cash flow statement renders the words | `not extracted` present, and **no `0` in that year's CFS cells** | render a stub whose second year has no cash flow statement; grep the body |
| 8 | the applied items table lists the `high` and `medium` items and **not** the `low` one | 2 rows applied, 1 row excluded | grep the rendered body for each item's description |
| 9 | the reconciliation shows a non-zero delta for the adjusted year | the delta equals the sum of the applied items' `adjusted_impact` for that year, **computed by hand in your log entry** | grep the body, then show the hand arithmetic |
| 10 | every ratio carries its own source sentence | 6 sentences rendered | render a stub, then assert each of the six `AssumptionSource.detail` strings appears verbatim in the body |
| 10b | a substituted ratio is visibly marked, not shown as an ordinary figure | `SUBSTITUTED` and `It is not a measurement.` both in the body | render a stub with income statements and **no** cash flow statements; grep the body |
| 11 | the inline `PROV` variable is gone and `.provenance` exists | 0 and 1 | `grep -n "PROV" templates/valuation_result.html` and `grep -n "\.provenance" static/style.css` |
| 12 | **no number already on either page moved** | identical implied share price | run the same stub before and after; paste both share prices |
| 13 | the new `BalanceSheet` property holds one subtraction and no division | 1 match, 0 matches | `grep -n "balance_check_difference" -A 3 models/financial_statements.py` |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md` — rule 3 (stop, never guess; step 11 is its display face),
  rule 4 (line 92 states this unit's gap), rule 6 (an assumption is labelled and
  **visible to the user**).
- `docs/4-conventions/units-and-signs.md` — **read it before you write any column
  header.** Millions, percentages, and the sign of every cash-flow field.
- `docs/3-architecture/data-contract.md` — the `models/` dataclasses, every field, and
  which are derived properties rather than extracted values.
- `docs/3-architecture/entry-points.md:117-122` — what `templates/` holds today, and the
  recorded statement that the result page does not show which assumptions were
  substituted.
- `cli.py:477-601` and `:607-751` — the seven blocks, as the reference for **what**.
- `STATUS.md` section 1b — why a template defect in this repository produced a blank 500
  and not a message, and why the error branch must be exercised, not reasoned about.

## Known open items

### What `P8a-statements-data` actually built — read these shapes before you write a row

`historical_fcff` is a `list[HistoricalFCFFYear]`, **not** a list of `HistoricalFCFF`.
Each record holds four fields:

| Field | Type | Meaning |
|---|---|---|
| `year` | `int` | always present, even for a year with no figures |
| `is_computable` | `bool` | false when a statement the formula needs was not extracted |
| `fcff` | `HistoricalFCFF \| None` | `None` when `is_computable` is false. **Never zeros** |
| `missing_statements` | `tuple[str, ...]` | e.g. `("cash flow statement",)`. Empty when computable |

So step 9's "prints the words" means: test `is_computable`, and when it is false print
`not extracted: <the joined missing_statements>`. Reading `row.fcff.revenue` without
that test raises on a year with no cash flow statement, and the blanket handler at
`:317` would render that as an error page.

**Head the historical FCFF table `post-adjustment`.** Each row is a hybrid: a normalised
EBIT and tax rate against an **unadjusted** CFO, because a non-recurring item moves the
income statement and the cash flow statement is carried as extracted. That is why a
worked example reads `213.0967741935484` and not `212.842105`. It is correct, and the
heading has to say which side of the adjustment the reader is looking at.

`assumption_sources` is a `dict[str, AssumptionSource]`, **not** a dict of plain
strings. `AssumptionSource` lives in `models/valuation.py` and has three fields:

| Field | Type | Meaning |
|---|---|---|
| `origin` | `str` | one of `ASSUMPTION_ORIGIN_SUPPLIED`, `_DERIVED`, `_SUBSTITUTED` |
| `detail` | `str` | the sentence to show the reader. **Print this.** |
| `observations` | `int` | filing-years that fed it; `0` when supplied or substituted |

**A `substituted` ratio must not look like a `derived` one.** Its sentence carries the
word `SUBSTITUTED` and says "It is not a measurement." Give that row a visible marker,
the same weight the excluded non-recurring table already carries. A reader who skims the
percentages and not the sentences is exactly the reader rule 6 exists for.

### Three findings the P8a programmer raised, confirmed or not by its reviewer

1. **`assumption_sources` is `{}`, not six labels, on `GET /assumptions`'s failure path
   and on its no-filing path.** A page that derived no ratio has no ratio to label.
   **Your template must handle the empty dict** and print no source table at all in that
   case, rather than six rows of an undefined value. Test it: request `/assumptions`
   with no `files` parameter.

2. **Backlog item 6 makes one of the six labels lie, and this unit is what makes the lie
   visible.** `api/routes_valuation.py:216-220` reads `x / 100 if x else None`, so a
   reader who deliberately types `0` into a ratio field reaches the route as `None` and
   is labelled `derived from the filing's history`. The label reports what the code did.
   **Do not repair the conversion** — Phase 4 owns it. Do not soften the label either.

3. **A year with a cash flow statement and no income statement is invisible on both
   pages.** `FinancialStatements.years` derives from `income_statements` alone
   (`models/financial_statements.py:276-282`), so such a year is in no list you iterate.
   That is a gap in the model, not in your templates. **Do not work around it** and do
   not add a second year list.

### The rest

- **The error branch renders through the same template.** `api/routes_valuation.py:319`
  renders `valuation_result.html` with `dcf=None` on failure. Your include sits inside
  the `{% elif dcf %}` branch, so it is not reached on that path. **Confirm that by
  execution**, not by reading: `STATUS.md` section 1b records a total outage that
  survived because the error page rendered through the broken call it was reporting.
- `derive_assumptions` returns a plain `dict`, so `assumptions` in the template context
  is a dict and its keys are read with `assumptions.operating_margin` in Jinja, which
  resolves a dict key. The existing template already relies on this at `:128-135`.
- Backlog item 6 means a user who types `0` in a ratio field has it read as "not
  supplied". `assumption_sources` therefore reports that field as derived. **That label
  is correct about what the code did.** Do not repair the conversion here.

## Backlog items this unit is NOT fixing

- **Item 5** — the module-global extraction cache, `pop`ped on read. Unchanged by this
  unit. A refresh of the result page still re-runs the paid extraction.
- **Item 7** — `cli.py` and `api/` duplicate the pipeline. This unit closes the *output*
  half of that gap and leaves the *orchestration* duplication where it is. Phase 3 owns
  it. **Do not extract a shared function in this unit.**
- **Item 8** — the blanket `except Exception` at `:317`. Phase 5 owns it. You are
  rendering through the template it catches into; leave the handler alone.
- **Item 11** — the 14 type errors, one of them a live crash path at `:261`. Phase 5
  owns them. Criterion 3 asks only that you add no fifteenth.
- **Item 1** — the 116 zero-default sites, 60 of them in `models/`. You are adding a
  property to `models/financial_statements.py`; **add no field and no default**, so the
  count does not rise. Phase 6 owns the count.
- **Item 32** — `models/valuation.py:138` renders a share price of `0.0` on zero diluted
  shares. Not in scope and not in a file you touch.
