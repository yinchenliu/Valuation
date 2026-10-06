---
id: P3c-one-number
phase: 3 — unify the pipeline (part 3)
agent: programmer
depends_on: [P3a-one-pipeline, P3b-pipeline-stops]
---

# The web page and the CLI give one number for one filing (items 87, 92, 6, 97)

## Objective

**Fact 1, backlog item 87.** `api/routes_valuation.py:436-441` formats each of the six
derived assumptions with `:.1f`, and `templates/assumptions.html` puts that rounded
string in the form's `value` attribute (lines 157, 166, 172, 182, 187, 192).
`POST /valuation` reads it back as a reader's override. So a reader who accepts every
default gets a price built from rounded ratios, and the CLI gets a price built from the
same ratios unrounded. **Walmart is $27.01 on the page and $28.02 in the CLI.**

Measured by the overall lead's read-only agent on 2026-10-05, on hand-built statements
with market data stubbed and every other input held fixed: an operating margin of
4.2537% rounded to 4.3% moves the share price **from $226.69 to $233.55, a difference of
$6.85 or 3.02%**. Rounding all six as the form posts them gives $233.07.

**Fact 2, backlog item 87's other half, and it is a rule 6 defect.** `run_valuation`
cannot tell a value the reader typed from one the form filled in: the six ratios arrive
as `float = Form(0)` (`api/routes_valuation.py:532-536`) with no companion flag. So the
result page labels every run "supplied by the caller — ... nothing in this platform checks
a figure you typed against the filing" (`models/valuation.py:90-94`), for a figure the
platform produced. On the page before it, the same figure sits under the heading "Derived
Default". **The label is wrong in both directions, and the rounding is named on neither
page.**

**Fact 3, backlog item 6.** The five conversions at `api/routes_valuation.py:621-625`
read a falsy number as "not supplied": `operating_margin / 100 if operating_margin else
None`. A reader who deliberately types `0` is told nothing and gets the derived value.
The comment at `:626-630` names this as item 6 and leaves it.

**Fact 4, backlog item 92.** `cli.py:1021` calls `print_historical_fcff(financials)` on
the statements as extracted. `api/routes_valuation.py:449` and `:670` call
`_historical_fcff_by_year` on `adjustment.adjusted`, the normalised statements, which is
the same object `value_company` is given. **Within one CLI run the FCFF table and the DCF
are built on two different sets of statements.** Walmart: the CLI shows
17,109 / 12,854 / 16,985 and the web 17,192 / 12,873 / 16,952. The field that differs is
`IncomeStatement.effective_tax_rate`: `analysis/normalizer.apply_adjustments` replaces
income-statement expense fields, so `ebit` and `ebt` move, `tax_expense` is stored and
does not, and `tax_expense / ebt` therefore changes. `calculate_fcff_historical` reads
that rate only for `after_tax_interest` (`analysis/fcff.py:78`). Neither table reaches
the DCF; both are display.

**Fact 5, found by the overall lead on 2026-10-05, not yet on the backlog.**
`cli.py:683-684` holds `if is_ is None or cf_ is None: continue`. A year the CLI cannot
compute **vanishes from the table with no word**. The web's `_historical_fcff_by_year`
records `is_computable` and `missing_statements` for the same year
(`api/routes_valuation.py:272-289`). The two entry points disagree about what to do with
a year that has no cash flow statement.

**Fact 6, backlog item 97.** `templates/upload.html:11` sets
`style="white-space: pre-line"` on its error block. `templates/assumptions.html:10` and
`templates/valuation_result.html:10` do not. So `P3b`'s new stop, which prints a file
list and two bullet remedies, collapses into one wrapped paragraph on both pages.

**What follows.** When this unit is done, a reader who changes nothing on the assumptions
form gets the same share price the CLI gives for the same filing and the same market
data; the result page says those ratios were derived, because they were; a typed `0` is a
`0`; both entry points compute the historical FCFF from the statements the valuation uses
and both say so; and a multi-line stop is readable on every page.

## The user's decision of 2026-10-05, option 1a

The user chose, in these words, "1a". The option as it was put to them:

> **Empty inputs, derived value shown beside them.** The six ratio inputs start empty.
> The derived value stays in the "Derived Default" column and becomes the input's
> placeholder. An untouched form posts nothing, so the pipeline derives at full precision
> and the web price equals the CLI price. A value the reader types is labelled "supplied".

**The reason this option and not another, and you may not revisit it.** The route already
uses `str = Form("")` for `risk_free_rate`, `equity_risk_premium`, `beta_override` and
`cost_of_debt_override`, and the comment at `api/routes_valuation.py:537-556` records
**why**: a `float` form field cannot express "the user left this blank" without inventing
a sentinel number, and when the route always reached the calculation with a value, the
output could never say a figure had been substituted. **Read that comment before you
write a line.** This unit applies the same, already-proven shape to the six ratios.

## What is already true — verify, do not redo

Measured by the overall lead at `19fe831`, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1137 passed, 5 skipped, 0 failed** |
| full suite | `-m pytest -q` | **2 failed**, 1137 passed, 5 skipped. The 2 are red on purpose |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | **5 errors in 2 files** |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.claude/check_guard.py` | 48/48 |

**A second unit may be in flight while you work: `P1d-skipped-filings`, a tester unit in
`tests/` only.** Your criterion is the **set** of failing test names, not the count. Save
the set before you start and after you finish, and name every difference.

**This machine holds no session file and no cached extraction.** `extractions/` is empty
and `10K_filings/` holds nine PDFs under `ABBV/`, `LHX/` and `WMT/`. **There is no
end-to-end Walmart run available here.** No criterion below asks for one. Build your
evidence from hand-made `FinancialStatements` with `pipeline.fetch_price_data` stubbed,
the way `tests/unit/test_pipeline.py` does. Do not try to reproduce $27.01 and $28.02.

**Facts about the code, each read today:**

| Fact | Where |
|---|---|
| The six display strings, all `:.1f` | `api/routes_valuation.py:436-441` |
| The "Derived Default" column heading and its six cells | `templates/assumptions.html:40`, and 48, 61, 74, 87, 100, 113 |
| The six form inputs, and `step="0.1"` on five of them | `templates/assumptions.html:157, 166, 172, 182, 187, 192` |
| Two hints that will become false: `0 = use historical average`, `0 = derive from financials` | `templates/assumptions.html`, under `operating_margin` and `tax_rate` |
| The four fields that already use `str = Form("")`, and the comment that says why | `api/routes_valuation.py:537-560` |
| The `.strip()` pattern those four use, and the comment that contrasts it with item 6 | `api/routes_valuation.py:626-634` |
| `ProjectionAssumptions.operating_margin is not None` is the only test `derive_assumptions` makes | `analysis/projector.py:226-228` |
| `defaults["sources"]` already carries `derived` or `substituted` per field, and the page reads it | `api/routes_valuation.py:428-434` |
| `revenue_growth` is already `str = Form("")` and is parsed with `.strip()` | `api/routes_valuation.py:531, 613-615` |
| The CLI's banner names the method and not the basis | `cli.py:675`, `HISTORICAL FCFF (CFO-based, $M)` |
| The CLI drops an uncomputable year with `continue` | `cli.py:683-684` |
| The web records `is_computable` and `missing_statements` for the same year | `api/routes_valuation.py:272-289` |
| `adjusted` is in scope at the CLI's stage 5 call site | `cli.py:1011`, three lines above |

## What to do

1. **Change the six ratio form fields to `str = Form("")`**: `operating_margin`,
   `tax_rate`, `da_pct`, `capex_pct`, `nwc_pct`. (`revenue_growth` is already a string;
   leave its type alone.) Convert each with the `.strip()` pattern the four fields below
   them already use, so a typed `0` survives as `0.0` and only a blank field becomes
   `None`. **This closes backlog item 6 for those five fields.** Say so in a comment, and
   correct the comment at `:626-630`, which names them as item 6 and not this unit's.
2. **Stop putting a derived value in a form `value` attribute.** The six inputs render
   empty. Put the rounded figure in `placeholder` instead, so the reader still sees it in
   the field.
3. **Keep the "Derived Default" column exactly as it is.** It is the honest home for the
   figure, and `assumption_sources` already labels each one `derived` or `substituted`.
4. **Say, in words next to the fields, what blank means and what typing means.** A reader
   who types the figure shown in the placeholder does **not** get the same answer as a
   reader who leaves the field blank, because the placeholder is rounded to one decimal
   place and the derived value is not. State that. Replace the two false hints
   (`0 = use historical average`, `0 = derive from financials`) with true ones. Rule 6:
   an assumption that is shown must be shown for what it is.
5. **Set `step="any"` on the five number inputs that carry `step="0.1"` for a ratio.** A
   reader who wants to type 4.25 must be able to. Leave `terminal_growth_rate`'s own
   attributes alone; they are item 90's and item 90 is not this unit's.
6. **Make `cli.py` compute the historical FCFF from the normalised statements**: pass
   `adjusted`, not `financials`, at `cli.py:1021`. **This changes printed numbers**, and
   it is the point: the table beside a valuation must be built from the statements the
   valuation used.
7. **Name the basis in both entry points.** The CLI's banner and the web's historical
   FCFF table must each say which statements the figures came from. One sentence each.
   Use the same words in both.
8. **Make the CLI report a year it cannot compute**, as the web does. A year with no
   income statement or no cash flow statement must appear in the table with the reason,
   not vanish. Do not invent a figure for it.
9. **Add `style="white-space: pre-line"` to the error block** in
   `templates/assumptions.html:10` and `templates/valuation_result.html:10`, matching
   `templates/upload.html:11`. That is item 97.
10. **Record what you find, do not widen your scope.** If you find a defect outside this
    list, write it in your log entry under "Found". The overall lead puts it in the
    backlog.

## Files in scope

- `api/routes_valuation.py`
- `templates/assumptions.html`
- `templates/valuation_result.html`
- `cli.py`

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Out of scope

- **`tests/`.** The write guard denies it, and `P1d-skipped-filings` may be editing it
  while you work. Your unit's own tests are a separate assignment after the code review.
- **`analysis/projector.py` and `models/valuation.py`.** `derive_assumptions` already
  takes `None` to mean "derive" and already returns `sources`. If you believe a change is
  needed there, that is a finding: write it and stop.
- **`pipeline.py`.** No number moves there.
- **Item 88**, the `assumptions` bare dict. The user accepted it until item 88 is fixed
  (decision of 2026-10-05). Do not change the signature.
- **Item 90**, the terminal growth literal in four places. **Its backlog row was
  corrected on 2026-10-05 and the correction changes its fix**:
  `config.DEFAULT_TERMINAL_GROWTH_RATE` already exists and is read by nothing. Leave all
  four literals alone.
- **Items 5, 26, 82, 89, 94, 99.** Each sits in a file you touch. Each is recorded.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | An untouched form gives the CLI's price | the two prices are **equal to the cent**, and say to how many decimal places they agree | build one `FinancialStatements` by hand with a ratio that does not round cleanly (for example an operating margin of 4.2537%); stub `pipeline.fetch_price_data`; run `pipeline.value_company` with no overrides, and `POST /valuation` with every ratio field absent. Print both prices |
| 2 | The old behaviour is reproduced first, so criterion 1 means something | the same two commands at `19fe831` give **different** prices | `git stash` is forbidden: use `git archive 19fe831` into a scratch directory and run there |
| 3 | No derived value reaches a form `value` attribute | no match | `grep -n "value=\"{{ defaults\." templates/assumptions.html` |
| 4 | The derived figure is still shown twice: the column and the placeholder | 6 of 6 fields, by name | `grep -n "placeholder" templates/assumptions.html`, and render the page and show the column |
| 5 | A typed `0` is kept | `ProjectionAssumptions.operating_margin == 0.0`, not `None` | `POST /valuation` with `operating_margin=0`; print the assumption the route built |
| 6 | A blank field is `None` | `operating_margin is None` | the same, with the field absent |
| 7 | The result page says `derived`, not `supplied`, for an untouched form | 6 of 6 origins read `derived` | render `POST /valuation` with no ratio fields; print the six origins |
| 8 | The result page says `supplied` for a typed value | that one origin reads `supplied`, the other five `derived` | the same, with one field typed |
| 9 | The form states what blank means and what typing means | the text is on the page | render `GET /assumptions` and print the sentences |
| 10 | The CLI's historical FCFF equals the web's for the same filing | every year equal | one hand-built `FinancialStatements` with at least one applied non-recurring item; print `print_historical_fcff`'s table and `_historical_fcff_by_year`'s list side by side |
| 11 | The CLI's figures changed, and by how much | name the years and the differences | the same statements through `19fe831`'s `cli.py` and through yours |
| 12 | Both entry points name the basis | the same sentence appears in the CLI output and on both pages | render and print |
| 13 | A year with no cash flow statement is reported, not dropped | the year appears with its reason, in both entry points | build statements with one year missing its cash flow statement |
| 14 | The multi-line stop is readable | both templates carry `white-space: pre-line` | `grep -n "white-space" templates/` |
| 15 | Types | **5 errors in 2 files**, or fewer. Name any you removed | the mypy command above |
| 16 | Lint | 4 errors, every one `BLE001` | `-m ruff check .` |
| 17 | Census | 64, or fewer. Name any site you removed | the grep at `docs/2-rules/rules.md:102` |
| 18 | Route | 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` |
| 19 | The failing test set | **name every test that changed state, and why.** Tests that post the six ratios as numbers will fail; each is a test whose subject this unit changed, and the tester repairs them | `-m pytest -q --ignore-glob="*_rule3_red.py"`, before and after, compared by name |

**Every criterion is a measurement, never an opinion.** Criteria 2 and 11 exist because a
change that moves a number must show the number before and the number after.

## Citations

- `docs/2-rules/rules.md` — rule 6 forces facts 2 and 3; rule 3 forces fact 5.
- `docs/9-reference/refactor-backlog.md`, items 87, 92, 6 and 97, each with the 2026-10-05
  measurements.
- `api/routes_valuation.py:537-556` — the comment that records why `str = Form("")` is
  the right shape. The precedent this unit follows.
- `api/routes_valuation.py:272-289` — `_historical_fcff_by_year`, and the shape fact 5
  asks `cli.py` to match.
- `analysis/normalizer.py:190-273` — what normalisation changes, and what it leaves alone.
- `.claude/agents/programmer.md` — your role card.

## Known open items

- **Backlog item 8** (blanket `except Exception`): a stop renders at HTTP 200, not 4xx.
  Not yours.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- **Backlog item 87's browser half**: `step="0.1"` makes a browser enforce the same grid a
  second time. Step 5 covers it. This was read from the attribute, not measured against a
  real browser.
- The suite takes about 135 seconds.
