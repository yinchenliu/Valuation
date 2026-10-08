---
agent: programmer
assignment: P14g-unit-statement-pages
round: 1
status: complete
files_touched: [ingestion/claude_extractor.py]
verdict:
---

# P14g-unit-statement-pages — the two unit-scale checks now state one rule, and the price of that is measured

## What I did

`_unit_statement_pages_allowed` allowed a unit statement only on a page that a figure it
governs is printed on. Check B1 (`_row_scale_failures`) has allowed the row's page **and
the page before it** since `P14b-note-figures`. The two checks therefore held two
different rules, and Walmart's fiscal 2024 10-K prints an income statement whose title,
unit statement and year header are the last four text lines of PDF page 45 and whose every
data row is on page 46 — so the correct reading, `units` on page 45, was refused.

One new function, `_pages_and_page_before`, now holds that rule once. Both checks read it:
`_unit_statement_pages_allowed` applies it to the set of pages a statement governs, and
`_row_scale_failures` applies it per row at `pages_to_check` and per PDF at
`pages_to_read`. The two failure-message strings in `_PAGES_ALLOWED_ARE` say "and the page
before each". Nothing else changed; no prompt byte and no schema byte moved.

**The widening has a price and I measured it by execution rather than asserting it.** On a
two-page PDF I wrote, where page 1 is a note headed `(in thousands)` and page 2 is the
income statement headed `(in millions)` with every figure, a model citing page 1's
`(in thousands)` as `units` is **refused at `HEAD` and accepted after this change**. Check
B1 cannot catch it, because B1's expected scale is itself read from `units`. Section
"Measurements" states that in full, with the run.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | The refusal is reproduced first | **pass** | `git archive HEAD` into `C:\tmp\p14g\head` (no `git stash`), then `PYTHONPATH=/c/tmp/p14g/head .venv/Scripts/python.exe /c/tmp/p14g/probe_allowed.py HEAD`. Message quoted below |
| 2 | That citation is now accepted | **pass** | the same probe against the repository tree: `units allowed=[45, 46]`, `Unit statements looked up on their cited pages: 2 checked, 2 found, 0 not confirmed.`, `failures: 0` |
| 3 | The two checks state one rule | **pass** | one function, `_pages_and_page_before` (`ingestion/claude_extractor.py:1479-1499`), read by `_unit_statement_pages_allowed:1533` and `:1534`, by `_row_scale_failures:1674` (`pages_to_read`) and by `_row_scale_failures:1710` (`pages_to_check`). Page-1 case executed: see "The page > 1 edge" below |
| 4 | `share_units` is decided on purpose | **pass** | the decision table below, and the docstring of `_unit_statement_pages_allowed` |
| 5 | What the widening admits | **pass** | the three tables under "Measurements", including the wrong answer that is now accepted, executed in both trees |
| 6 | Nothing that used to be caught gets through | **pass** | five refusals with their messages, below (the three the assignment names, plus two more) |
| 7 | No figure moves for the three Walmart filings | **pass** | `cli.py --session-file extractions/WMT.json`, both trees, one sitting, `pipeline.fetch_price_data` pinned to one pickled reading: 387 lines of stdout **byte-identical**, sha256 `9556b8dd…` on both. Implied share price `$30.87` both sides |
| 8 | `extractions/WMT.json` is unchanged | **pass** | sha256 `c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675` before the first command and after the last |
| 9 | Types | **pass** | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → **2 errors in 2 files**, 21 checked (`analysis/projector.py:395`, `api/routes_upload.py:28`). None removed, none added |
| 10 | Lint | **pass** | `-m ruff check .` run **after the last edit** → **4 errors, every one `BLE001`** (`api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106`) |
| 11 | Census | **pass** | the grep at `docs/2-rules/rules.md:102` → **64**. No site added, none removed |
| 12 | Route | **pass** | `TestClient(app.app, raise_server_exceptions=False).get('/')` → **200** |
| 13 | The failing test set | **pass, with two tests changed on purpose** | before `{}`, after `{test_p14a_units.py::test_unit_statement_pages_allowed_constrains_pages, test_p14a_units.py::test_unit_statement_failures_stops_when_page_outside_allowed}`. Both are tests of the **old, narrower** rule. Named and diagnosed below |
| 14 | No paid call was made | **pass** | every command carried `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. Every PDF was read with `pdfplumber`. The CLI ran `--session-file`, which is route B and calls no model. See "The one network call I did make" |

Write guard: `.claude/check_guard.py` → **48/48**.

## Criterion 1 — the refusal, at `HEAD`, quoted

Built from `extractions/WMT.json` `filings[0]` (fiscal 2024) with `units` moved to the
income statement's own printed line, `(Amounts in millions, except per share data)` on PDF
page 45:

```
'units' (the unit of the money figures): the statement '(Amounts in millions, except
per share data)' cites page 45, which is not a page of the figures it states the unit
of: the pages allowed are [46], the pages the income statement's printed lines cite.
A unit statement that is not confirmed stops the run: the scale read from it converts
every figure to millions, a wrong scale moves every figure by a factor of 1,000, and
nothing downstream can detect it.
```

Fact 2 of the assignment is confirmed against the real PDF (147 pages, `pdfplumber`). PDF
page 45's last four text lines are `Walmart Inc.` / `Consolidated Statements of Income` /
`Fiscal Years Ended January 31,` / `(Amounts in millions, except per share data) 2024 2023
2022`; PDF page 46's first line is `Revenues:` and its second is
`Net sales $ 642,637 $ 605,881 $ 567,762`.

## Criterion 4 — `share_units`, each part decided, with the reason

| Part of the allowed set | What kind of page it is | What I did | Why |
|---|---|---|---|
| `diluted_pages` — the pages `diluted_shares` printed lines cite | **row** pages: the page a figure is printed on | **widened**: `_pages_and_page_before(diluted_pages)` | This is exactly the kind of page B1's rule is about. A share count's column heading can be split from its rows by the same page break that splits the income statement's. Making it agree with B1 is the whole unit |
| `{data["units"]["page"]}` — the page the money unit statement is printed on | an **already-resolved statement** page, not a figure page | **left alone**: no predecessor added | There is no printed layout in which the share unit statement sits one page *before* the money unit statement: a filing either prints one statement covering both (Walmart) or two statements on one page (Okta). Adding `units.page - 1` would allow a page that no figure of this answer and no statement of this answer points at, and I could give no reason for it. A widening I cannot give a reason for is one I should not make |

**The choice is not free, and it shows in the numbers.** On `extractions/WMT.json`
`filings[2]` (fiscal 2026), `share_units`'s allowed set is `[21, 22]` before this change
and `[21, 22]` after — **unchanged** — because `units.page` is 21 and `21 = 22 - 1` is
already contributed by the `diluted_shares` page. Had I widened both parts, it would have
become `[20, 21, 22]`, and page 20 of that filing prints `(Amounts in millions)` heading an
Item 7A market-risk table. The narrower choice keeps that page out of `share_units`.

## Criterion 6 — what is still refused, with each message

Built on the real fiscal 2024 PDF. The income statement's figures are all on page 46, so
the allowed set is `[45, 46]`.

| Case | Cited | Refused? | The reason in the message |
|---|---|---|---|
| **a** two pages before the figures | page 44, `(Amounts in millions, except per share data)` | **yes**, 1 failure | `cites page 44, which is not a page of the figures it states the unit of: the pages allowed are [45, 46], the pages the income statement's printed lines cite, and the page before each of them` |
| **b** a page after the figures | page 47, `(Amounts in millions)` | **yes**, 1 failure | `cites page 47, which is not a page of the figures it states the unit of: the pages allowed are [45, 46], …` |
| **c** text not printed on the page it cites | page 46, `(in thousands)` | **yes**, 1 failure | `the statement '(in thousands)' was not found on page 46, the page it cites, as a whole printed statement` |
| **d** an allowed page, wrong text (the new page, checked) | page 45, `(Amounts in millions)` | **yes**, 1 failure | `the statement '(Amounts in millions)' was not found on page 45, the page it cites, as a whole printed statement` |
| **e** `share_units` two pages before the share count | page 44 | **yes**, 1 failure | `the pages allowed are [45, 46], the 'units' page, the pages the diluted share count's printed lines cite, and the page before each of those` |

Case **d** is the one I added beyond the assignment's three, and it is the one that proves
the new page is still *checked* rather than merely allowed: page 45 prints
`(Amounts in millions, except per share data)` and does **not** print `(Amounts in
millions)` on its own, so the model cannot cite the balance sheet's wording against the
income statement's page.

## The page > 1 edge, executed (criterion 3)

```
_pages_and_page_before([1])     = [1]
_pages_and_page_before([2])     = [1, 2]
_pages_and_page_before([1, 2])  = [1, 2]
_pages_and_page_before([46])    = [45, 46]
_pages_and_page_before([1, 46]) = [1, 45, 46]
```

And on a whole answer with every printed row moved to page 1:

```
every row on page 1 -> units allowed=[1] share_units allowed=[1]
B1 on the same answer:
  page 1 (money figures): expected millions, no unit statement on page 1. Rows citing page 1: …
  page 1 (share count):   expected millions, no unit statement on page 1. Rows citing page 1: …
```

Page 0 is never allowed by either check, and B1's own page-1 wording is unchanged.

B1's per-row expression changed shape but not value or order:
`(page, page - 1) if page > 1 else (page,)` became
`sorted(_pages_and_page_before({page}), reverse=True)`. For a one-element input those are
the same sequence in the same order, which matters because that order is the order the B1
failure message lists the statements it found in. The 31 B1 tests in
`tests/unit/test_p14b_note_figures.py`, including the two-scale message tests, all still
pass.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| One function, `_pages_and_page_before`, read by both checks | assignment step 2: "Make the two checks state one rule". Two checks that each spell a rule drift apart — that is exactly what item 114 is | The alternative, copying `page - 1` into the second check, reproduces the defect's cause |
| B1's `pages_to_read` and `pages_to_check` rewritten to call it | "state one rule" has to be true in code, not in a comment | Leaving B1 untouched would have left the rule written twice and asserted once |
| `share_units`'s `units.page` part **not** widened | see criterion 4 | measured: widening it would add page 20 of the fiscal 2026 filing, an MD&A market-risk table's header |
| The Pass 1 schema and prompt untouched | assignment step 7, fact 4; `docs/2-rules/llm-boundary.md` — a change there is an LLM boundary change to escalate | `:223` and `:227` already say "the 1-based PDF page it is printed on", which is the right instruction. The check was wrong, not the instruction |
| `extractions/WMT.json` not edited | assignment "Out of scope" | `filings[0]` cites the wrong statement's unit statement; that is a finding, below, not an edit |
| The two now-red tests in `tests/unit/test_p14a_units.py` not touched | `.claude/agents/programmer.md`: a programmer never writes or edits `tests/`; the assignment puts this unit's tests in a separate assignment | Editing them would be a programmer marking its own work |

**No change in this unit was made to reach a target number.** The one number this unit
could have moved — Walmart's implied share price — is byte-identical across the two trees.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `data["historical_years"]` | **stops**, `KeyError: 'historical_years'` | `ingestion/claude_extractor.py:1525` and `:1530` — direct subscript, no `.get`. Unchanged by this unit; `tests/unit/test_p14b_note_figures.py:826` already locks it |
| `entry[field]` for each income-statement field | **stops**, `KeyError: '<field>'` | `:1527` — direct subscript. `pass1_problems` runs before this and names the field first |
| `line["page"]` | **stops**, `KeyError: 'page'` | `:1524` and `:1530` — direct subscript |
| `data["units"]["page"]` | **stops**, `KeyError: 'units'` or `'page'` | `:1534` — direct subscript. This unit kept it exactly as it was |
| `pages` argument of `_pages_and_page_before` | an empty set in gives an empty set out, and then **every** citation of that statement fails and the run stops | `:1479-1499`; executed: an answer whose income rows are all on page 1 gives `units allowed=[1]`, and an answer with no income rows at all would give `allowed=[]`, so no page is allowed and `_unit_statement_failures` reports one failure per statement |
| `page_texts[page]` in B1 | **stops**, `KeyError` — a page not read is never silently skipped | `:1712` — direct subscript; `_pages_and_page_before` is the one expression that decides which pages were read, so `pages_to_read` and `pages_to_check` cannot disagree |

**No "defaults to" row.** This unit adds no `.get` with a fallback, no `or` default, no
conditional zero and no defaulted dataclass field. The census is 64 before and 64 after.

## Measurements

### The suite, compared by name

| | gate command | result | failing set |
|---|---|---|---|
| before | `-m pytest -q --ignore-glob="*_rule3_red.py"` in `C:\tmp\p14g\head` (`git archive HEAD`, with `10K_filings/` and `extractions/` copied in so no real-filing test skips) | `1257 passed, 2 skipped, 0 failed` in 139.36s | `{}` |
| after | the same command in the repository | `2 failed, 1255 passed, 2 skipped` in 139.75s | the two below |

Both changed tests are in `tests/unit/test_p14a_units.py` and both assert the **old,
narrower** rule. Neither is a regression; each is the unit's stated purpose, measured:

| Test | What it asserts | What it gets now | Is the refusal still there? |
|---|---|---|---|
| `test_unit_statement_pages_allowed_constrains_pages:290` | `allowed["units"] == {29, 30}` | `{28, 29, 30}` — page 28 is the page before page 29 | not a refusal test. Its **second** assertion, `allowed["share_units"] == {29, 30}`, is **still true** — I ran that data through the new function on its own and got `share_units [29, 30]`. The criterion-4 decision is what keeps it true |
| `test_unit_statement_failures_stops_when_page_outside_allowed:340` | `"the pages allowed are [29]" in msg` | the list is now `[28, 29]` | **yes.** The three assertions above it — `len(failures) == 1`, `"'units'" in msg`, `"page 35" in msg` — all still pass. A unit statement on a stock-award table page 6 pages away is still refused; only the printed list of allowed pages changed |

### Criterion 5, part 1 — the allowed sets of the three filings, before and after

Measured with `_unit_statement_pages_allowed` in each tree, on `extractions/WMT.json`.

| Filing | `units` before | `units` after | page added | `share_units` before | `share_units` after | page added |
|---|---|---|---|---|---|---|
| `filings[0]` fy2024 | `[46]` | `[45, 46]` | **45** | `[46]` | `[45, 46]` | **45** |
| `filings[1]` fy2025 | `[45]` | `[44, 45]` | **44** | `[45]` | `[44, 45]` | **44** |
| `filings[2]` fy2026 | `[21, 22]` | `[20, 21, 22]` | **20** | `[21, 22]` | `[21, 22]` | **none** |

**One correction to the assignment's fact 3, and it does not change its conclusion.** The
assignment's table gives "pages its printed lines cite" as `[46, 48]`, `[45, 48]` and
`[21, 22, 23]`. Those are the pages **all** printed lines cite. The allowed set is built
from `_INCOME_STATEMENT_LINE_FIELDS` only, which deliberately excludes
`depreciation_amortization`, `cfo`, `capex`, `sbc` and `change_in_working_capital` because
they are read from the cash flow statement (`:1442-1447`). So the pages the check actually
allowed at `HEAD` were `[46]`, `[45]` and `[21, 22]` — one page narrower in each case than
the assignment's table, and page 45 is still outside `[46]`, so the refusal is the one
fact 3 describes.

### Criterion 5, part 2 — what each added page prints, and which wrong answer it can carry

| Added page | Scale statements printed on it (`pdfplumber`, whole parenthesised groups) | Which wrong answer could now use it |
|---|---|---|
| fy2024 page **45** | `['(Amounts in millions, except per share data)']` — one, and it is the income statement's own header | **none on this filing.** The only text the check can now confirm on page 45 is the right one. Page 45 otherwise holds the internal-control audit report, which prints no parenthesised scale statement |
| fy2025 page **44** | `[]` — **zero** | **none.** Any citation of page 44 now reaches the second check and fails `was not found on page 44, the page it cites, as a whole printed statement` |
| fy2026 page **20** | `['(Amounts in millions)']` — heading an **Item 7A market-risk table**, not a financial statement | **a real one.** A model citing page 20's `(Amounts in millions)` as the income statement's `units` is refused at `HEAD` and accepted after this change. On this filing it reads *millions*, the same scale, so no figure moves — but the check is no longer the thing that would notice |

**None of the three added pages can move a figure in these three filings**, because every
scale statement on every one of them reads *millions*, which is the scale the filings
print in. That is a fact about Walmart, not about the check.

### Criterion 5, part 3 — the wrong answer the widening admits, executed

The honest price is not a page of Walmart's; it is the class of answer the check stopped
and now does not. I built it: a two-page PDF (`tests/unit/_text_pdf.write_text_pdf`, no
real filing touched), page 1 a note headed `(in thousands)`, page 2 the income statement
headed `(in millions)` with every figure on it. The model copies the note's statement.

```
### tree: HEAD-before
  [RIGHT: '(in millions)' on page 2] -> 0 failure(s)
  [WRONG: the note's '(in thousands)' on page 1] -> 1 failure(s)
     'units' …: the statement '(in thousands)' cites page 1, which is not a page of the
     figures it states the unit of: the pages allowed are [2], …
### tree: AFTER
  [RIGHT: '(in millions)' on page 2] -> 0 failure(s)
  [WRONG: the note's '(in thousands)' on page 1] -> 0 failure(s)
     *** ACCEPTED: every money figure would be read as thousands and divided by 1,000 ***
```

`printed_scale('(in millions)', 'money figures')` is `in_millions=Fraction(1, 1)` and
`printed_scale('(in thousands)', …)` is `Fraction(1, 1000)`, so the accepted answer turns
a printed revenue of 1,000 into **1.0 $M**.

**Check B1 does not catch it, and cannot.** B1's expected scale comes from
`_filing_units(data)`, which reads `units` — the very field in question. So B1 asks "is a
statement of the scale `units` claims printed near each row?", and the note on page 1 is
exactly that statement. B1 reported `5 checked, 1 pages, 0 pages not confirmed` in **both**
trees for the wrong answer. The page restriction in `_unit_statement_failures` was the only
guard, and the widening halves its strength: the window in which a model may cite another
table's unit statement goes from the figure's page to the figure's page **plus the page
before it**.

### Criterion 5, part 4 — how wide that window is, across the nine filings on this machine

For every page *F* of all nine PDFs, comparing the distinct scale words printed on *F* with
those on *F − 1*:

| | pages | share |
|---|---|---|
| total pages scanned (9 filings: ABBV ×3, LHX ×3, WMT ×3) | 1,104 | — |
| **A.** *F* prints no scale word and *F − 1* does — the split statement the widening exists for | **47** | 4.3% |
| **B.** *F* prints a scale word **and** *F − 1* prints a different one — the window the widening opens | **17** | 1.5% |

The 17 are: ABBV 2023 `[39, 49]`, ABBV 2024 `[27, 29, 37]`, ABBV 2025 `[28, 30, 36]`,
LHX 2023 `[]`, LHX 2024 `[73, 75]`, LHX 2025 `[21, 63, 65]`, WMT 2024 `[57]`,
WMT 2025 `[57]`, WMT 2026 `[14, 28]`.

**Not one of them is a page the income statement's rows cite in the three extractions this
repository holds** (those are 46, 45, and 21–22). So the widening buys 47 pages of correct
readings for 17 pages of new exposure, and on the filings actually extracted here the
exposure is zero. That is the payment, and it is a measurement, not a judgement about
whether the trade is right — the trade was set by the assignment, and part 3 above is the
line item a reviewer should price.

### Criterion 7 — the Walmart valuation, both trees, one sitting

`pipeline.fetch_price_data` was called once for real, pickled to `C:\tmp\p14g\price.pkl`,
and both runs returned that same `PriceData`, so the ±$0.01 market drift is removed by
construction rather than tolerated.

```
HEAD tree  : exit 0, 387 lines, sha256 9556b8ddc41c476c0e93f21cda264c4c5bba5bf2b8a61a453fb75c693e6d5b62
after tree : exit 0, 387 lines, sha256 9556b8ddc41c476c0e93f21cda264c4c5bba5bf2b8a61a453fb75c693e6d5b62
diff stdout: (empty)   diff stderr (minus the pin line): (empty)
Implied Share Price: $30.87 on both sides
```

**One input to that price came from the filing, and it is checked**: revenue 713,163 for
fiscal 2026 is printed on PDF page 21 of the fiscal 2026 10-K
(`Total revenues 713,163 680,985 648,125`), read here with `pdfplumber` and shown above.
$30.87 differs from `STATUS.md`'s $30.56 only because the market reading is from a
different day; the two runs compared here share one reading.

### No mutation was left in the repository

| When | sha256 of `ingestion/claude_extractor.py` |
|---|---|
| before my first command | `031101564e38b1165f602160aaae643fd344b685be8a94d62e10d1978486ff4d` (= `HEAD`, `git diff --stat` empty for that file) |
| after my last edit | `d4a4783247f493460bd8656b2fd55f74761b6d87c9c039187d0b773be2d5cb68` |

The second digest is **the fix**, not a probe. Every experiment — the `HEAD` baseline, the
page-1 answer, the five refusals, the two-scale PDF, the page scans — ran either in
`C:\tmp\p14g\head` (a `git archive HEAD` export) or against PDFs written under `C:\tmp`.
No probe ever wrote to a repository file. At the end of the run
`git status --porcelain` shows exactly two lines: `M ingestion/claude_extractor.py` and
`?? .agent/journal/2026-10-07T1556-programmer-p14g-unit-statement-pages.md`. (`.agent/QUEUE.md`
showed as modified in the session's opening snapshot and in my first `git diff --stat`, on a
CRLF normalisation git warned about; it is clean again and I never wrote to it.)

`extractions/WMT.json`: `c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675`
before the first command and after the last.

### The one network call I did make

No LLM API call of any kind was made. Every command carried `ANTHROPIC_API_KEY=
GEMINI_API_KEY=`; every PDF was read locally with `pdfplumber`; the CLI ran through
`--session-file`, which is route B and holds no client. The **one** network call in this
run was `yfinance`, made once by `pipeline.fetch_price_data` so that criterion 7's "pin
the market call" had a value to pin, and reused from a pickle for both runs. That is market
data under rule 5, labelled as such by the CLI itself.

## What I did not do

- **I did not touch `tests/`.** Two tests of the old rule are now red
  (`tests/unit/test_p14a_units.py:290` and `:340`). They are diagnosed above, line by line,
  with the assertion each one fails on and what the new value is. Repairing them is the
  tester's assignment.
- **I did not touch the Pass 1 prompt or schema** (step 7, fact 4). They already ask for
  "the 1-based PDF page it is printed on", which is correct.
- **I did not edit `extractions/WMT.json`**, though `filings[0]` cites the wrong
  statement's unit statement. See the findings.
- **I did not narrow the rule below B1's**, although part 3 above shows a narrower one
  would be safer. Step 2 says the allowed set "must allow what B1 allows". Inventing a
  third rule here would re-create item 114 in a new form. It is a finding instead.
- Backlog items 119, 120, 121, 122, 133 and 8 in this file are untouched.

## Findings for the orchestrator

1. **The unit statement check is now the only guard against "cite another table's unit
   statement", and after this unit it covers two pages instead of one — while check B1
   cannot help at all, because B1's expected scale is read from `units` itself.** Measured
   in "Criterion 5, part 3": a `(in thousands)` note header on the page before a
   `(in millions)` income statement is refused at `HEAD` and accepted here, and B1 reports
   `0 pages not confirmed` in both trees. 17 of 1,104 pages across the nine filings on this
   machine have that shape. **A narrower rule exists and would keep every correct reading
   in this repository**: allow the page before only when the figure's own page prints *no*
   scale statement of its own (the split-statement case, 47 pages), rather than always.
   On Walmart fy2024 that still accepts page 45, because page 46's only statement,
   `(Amounts in millions)`, belongs to the Comprehensive Income statement — so the rule
   would need to be "no statement the `units` text equals", which is a third rule and needs
   a decision. I did not make it: step 2 of the assignment mandates B1's rule, and widening
   is a decision the lead owns. This is the item to open against item 114's close.
2. **`extractions/WMT.json` `filings[0]` cites the wrong statement's unit statement, and
   this unit makes the right one citable.** It carries `units = {"printed": "(Amounts in
   millions)", "page": 46}`. Page 46 prints exactly one scale statement, `(Amounts in
   millions)`, and it is the header of the **Consolidated Statements of Comprehensive
   Income**; the Consolidated Statements of Income's own header, `(Amounts in millions,
   except per share data)`, is on page 45 and was not citable until now. Both read as
   millions, so **no figure moves** — proved by the byte-identical 387-line CLI output. The
   file is out of my scope. Re-extracting or hand-correcting `filings[0]` to page 45 would
   make the repository's one real route B file cite the statement it claims to describe.
3. **The assignment's fact 3 table and the check's allowed set are two different sets.**
   Fact 3 lists `[46, 48]`, `[45, 48]`, `[21, 22, 23]`; the check allowed `[46]`, `[45]`,
   `[21, 22]`, because `_INCOME_STATEMENT_LINE_FIELDS` excludes the five cash-flow fields
   on purpose. Worth correcting in the backlog entry for item 114 so the next reader does
   not measure against the wider set.
4. **Scratch artefacts** are under `C:\tmp\p14g\`: `head/` (the `git archive HEAD` export,
   with `10K_filings/` and `extractions/` copied in), `probe_allowed.py`,
   `probe_measure.py`, `probe_refusals.py`, `probe_cost.py`, `probe_window2.py`,
   `probe_scale_statements.py`, `run_cli.py`, `price.pkl`, `cli_before.txt`,
   `cli_after.txt`, `gate_before.txt`, `gate_after.txt`. A reviewer can re-run any of them
   with `PYTHONPATH` pointed at either tree.
