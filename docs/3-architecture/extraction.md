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
| Prompt emphasises | number precision; every figure as the printed rows that make it up (`P11a`) | citation to a note, one-time nature |
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

`pdfplumber` is in `requirements.txt`. Route A never imports it. Route B's `locate` and
`text` subcommands do, to find pages and print their text layer for a session to read
(below); neither computes from what it reads.

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

The routing is decided in one function, `plan_filings`, which returns one frozen
`FilingPlan(fiscal_year, pdf_path, target_years, include_bs)` per filing. The merge is
one function, `merge_filing_extractions`. `extract_multi_year` (route A) and
`load_session_extraction` (route B) both call them; see "Two routes, one parser" below.

`extract_multi_year` exists because a 10-K holds comparative years. Extracting every
year from every filing would call the model three times for the same figures and produce
three versions of each.

### Where each filing's fiscal year comes from

**The filename names the year; the filing's own text must agree, or nothing is
extracted.** Backlog item 43, decided by the user on 2026-10-02, landed by `P10c`. All of
it is in `ingestion/filings.py`, and every route goes through it.

| Step | Function | What it does |
|---|---|---|
| name | `fiscal_year_from_filename` | the 4-digit year after a `10-K`/`10K` marker, else the first `19xx`/`20xx` in the name, else `None`. The **one** filename guesser: `discover_filings` and the web upload (`_guess_fiscal_year`) both call it |
| read | `read_fiscal_year_evidence` | `pdfplumber`, two printed facts and their pages: the cover's `For the fiscal year ended <Month D, YYYY>` (it must follow `ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d)` in the first 5 pages), and the **newest** column heading in the first line, within 5 lines below a `Consolidated Statement(s) of Income / Earnings / Operations [and Comprehensive Income]` title alone on its line, that carries two or more years or two or more dates |
| decide | `fiscal_year_from_evidence(cover_date, column_label)` | pure, on two strings; see the rule below |
| compare | `verify_filing_years(filings, remedy)` | for every filing whose year is given (not 0), stops with one `ValueError`: mismatches under "does not match the filing", unreadable or self-contradicting filings under "could not be confirmed against the filing". `remedy` is `"year_path"` (CLI, route B) or `"rename_and_upload"` (web) |

**The decision rule** (amended in `P10c` round 2, review F2).

- **A bare-year column label is the filing's own name for the year, and wins** when it is
  the cover date's year or the year before. That covers the calendar filer (December 31,
  2025 → `2025`), the 52/53-week filer whose year ends in early January (L3Harris:
  January 2, 2026 → `2025`), and the retailer that names a year for the calendar year it
  starts in (Target: February 1, 2025 → `2024`).
- **A bare-year label outside that range stops**, naming the label, the cover date and the
  page of each: that far from the period end it is more likely a misread than a
  convention.
- **With date labels only, the cover rule:** the year of the cover date, **except that a
  year ending in the first seven days of January belongs to the year before** (the
  52/53-week convention). The newest date label must equal the cover date, or it stops.

No model is involved; rule 1 does not apply.

Round 1 required a bare-year label to equal the cover rule. That stopped a Target-style
filing even when the user passed the right year, because the check stopped before
comparing; the review proved it with `("February 1, 2025", "2024")`.

**Where it runs.** `discover_filings` (a folder), `parse_pdf_args` (including every
explicit `YEAR:PATH`) — so the CLI's route A and route B's `plan` — and `POST /upload`
on the web ([entry-points.md](entry-points.md)). A bare path with no year (year 0) asks
for every year in the filing and is **not** verified.

**What a stop says.** The file, the year given, the cover date and its page, the column
label and its page, the year the content gives, and the remedy. In the CLI and route B:
pass `<content year>:<path>`, or rename the file so the year after `10-K` in its name is
the content year. On the web: rename the file so, and upload it again. A filing whose
evidence cannot be read stops too, under the heading "could not be confirmed against the
filing", saying which: no cover line (a 10-Q, a scanned PDF), no income statement
headings, not a PDF, or a label too far from the cover date.

Measured on the 16 filings under `10K_filings/` on 2026-10-02:

| Filing | Cover | Newest column label | Content year | Filename year |
|---|---|---|---|---|
| AbbVie, Chipotle | December 31 of the year | bare year (pages 21–30) | = filename | — |
| Okta, Walmart | January 31 of the year | bare year (pages 21–65) | = filename | — |
| L3Harris `…_2023-12-29_…` | December 29, 2023 | `December 29, 2023` (p28) | 2023 | 2023 |
| L3Harris `…_2025-01-03_…` | January 3, 2025 | `January 3, 2025` (p41) | **2024** | 2025 — **stops** |
| L3Harris `…_2026-01-02_…` | January 2, 2026 | `2025` (p35) | **2025** | 2026 — **stops** |

`discover_filings` on `10K_filings/LHX` therefore stops; the remedy is
`2023:<…2023-12-29…> 2024:<…2025-01-03…> 2025:<…2026-01-02…>`, which plans the three
filings as 2023 (all years), 2024 and 2025 (with the balance sheet).

**Cost.** Reading the evidence extracts text page by page until the income statement:
about 2 to 4 seconds a filing on the macOS machine (10.5 s for AbbVie's three, 14.9 s
for Walmart's four).

### The routing

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

## Two routes, one parser

Added by `P9a-session-route` on the user's decision of 2026-10-02.

| Route | Who reads the PDF | Code | Cost |
|---|---|---|---|
| A | the model, over the API | `extract_multi_year` / `extract_financials` | two API calls per filing, plus up to two Pass 1 retries. **Each shape or check retry re-sends the whole PDF** (since `P11a`), so a failing Pass 1 costs up to three times its input tokens per filing; a JSON-syntax repair retry sends no PDF |
| B | Claude, inside a Claude Code session | `ingestion/session_extraction.py` | the session only; no API call |

Both routes answer the **same prompts** with the **same JSON**, and both go through the
same functions from that JSON onwards. Each of these has one definition, in
`claude_extractor.py`, and both routes call it:

| Job | Function |
|---|---|
| which years and which balance sheet from which filing | `plan_filings` → `list[FilingPlan]` |
| the Pass 1 prompt for a plan | `pass1_prompts(plan)` |
| the Pass 2 prompt for a plan and that filing's own Pass 1 result | `pass2_prompts(plan, financials)` |
| Pass 1 JSON → every absent key and malformed printed line | `pass1_problems` |
| one field's printed lines → its figure | `figure_from_printed_lines` |
| Pass 1 JSON → statements, as printed, + failed checks | `parse_pass1` |
| Pass 2 JSON → items | `parse_pass2` |
| a printed unit statement → its scale | `printed_scale` (`P14a`) |
| a Pass 2 item's unit words and amount → scale and multiplier | `pass2_amount_scale` (`P14b`) |
| Pass 1 JSON → its two unit statements and their scales | `filing_units` |
| each unit statement looked up on its page | `unit_statement_page_failures` (route B); `_unit_statement_failures` (route A) |
| each Pass 2 item's figure and units looked up on its page | `pass2_page_failures` (route B); `_pass2_item_failures` (route A) (`P14b`) |
| one filing's statements and items → millions | `convert_filing_to_millions`, after that filing's Pass 2, before any merge |
| per-filing results → one result | `merge_filing_extractions` (several filings only; one filing is returned as converted, by both routes) |

Route A's runners build their prompts through the same private builders the two prompt
wrappers call (`_pass1_prompt_pair`, `_pass2_prompt_pair`), so the prompt route A sends
and the prompt route B prints are one string, not two copies.

`ingestion/session_extraction.py` holds no model client, no prompt text and no
credential. [llm-boundary.md](../2-rules/llm-boundary.md) still names
`claude_extractor.py` as the only file that may. Filing discovery and hashing live in
`ingestion/filings.py` (`discover_filings`, `parse_pdf_args`, the fiscal-year check,
`InputFingerprint`, `fingerprint_filings`), shared by the CLI, route B and the web upload.

### The label

Route B's `ProviderResolution` is `provider="claude"`, the model the session declared,
`transport="claude-code-session"`, `credential="claude-code-session"`. A session is a
**transport**, not a provider: the model is still Claude. The transport label names the
session file and says the model ID is as declared and cannot be verified; the credential
label says no API call was made. `_build_claude_client` refuses this resolution, so it
can never be used to make a call.

### The session file, `session-extraction-v4`

JSON, UTF-8, one file per company run, kept under `extractions/` (git-ignored: it is
data).

```json
{
  "format": "session-extraction-v4",
  "ticker": "CMG",
  "company_name": "Chipotle Mexican Grill, Inc.",
  "extracted_by": {"model": null, "tool": "Claude Code", "date": null},
  "filings": [
    {
      "fiscal_year": 2023,
      "pdf_path": "/absolute/path/to/the.pdf",
      "pdf_sha256": "…",
      "size_bytes": 1234567,
      "target_years": null,
      "include_bs": false,
      "pages_read": {"pass1": [], "pass2": []},
      "pass1": null,
      "pass2": null
    }
  ]
}
```

- `pass1` is the object `_FINANCIALS_SCHEMA` describes, `pass2` the one `_NRI_SCHEMA`
  describes: exactly what route A parses. Stored as JSON objects, not strings. The
  shape of `pass1` is below; `pass2` items hold `page` and `units` (`printed`, `page`)
  as printed.
- `pages_read` holds the 1-based PDF pages read for each pass. A locator: recorded and
  printed, never computed from.
- `extracted_by.model` is printed as declared. `tool` and `date` are a record for a
  human and are not read.
- A single bare PDF gets `fiscal_year` 0, exactly as `parse_pdf_args` gives route A.

**Four formats, one readable.** `session-extraction-v1` (before `P11a`) held one figure
per Pass 1 field, and some of those figures were sums the session worked out: capex,
the working capital change, short-term debt, every catch-all. `session-extraction-v2`
holds the printed lines and Python adds them. **A v1 file stops**, with a message that
names both formats and says the filing must be extracted again; it cannot be converted,
because a sum cannot be turned back into the rows it came from. The CLI's pickle cache
marker changed for the same reason (`p6-inputs-keyed-v1` → `p11a-printed-lines-v1`).

`session-extraction-v3` (`P14a`, backlog item 44) changes `pass1.units` from a free
string no code read into a printed unit statement with its page, and adds
`pass1.share_units` (see "The printed unit statements" below). **A v2 file stops**,
with a message that names the change and the remedy: run the `extract-filing` skill
again, or add the two keys to each filing's `pass1` from the filing's printed unit
statement and set `format` to `session-extraction-v3`. Its figures are not wrong; only
their unit was never read.

`session-extraction-v4` (`P14b`, backlog item 77, user decision "fix 77a" of 2026-10-04)
changes `pass2` items so each copies its printed `amount`, its `page`, and its `units`
(`{"printed": ..., "page": ...}`). Python scales each item with `pass2_amount_scale`.
**A v3 file stops**, with a message that names both formats, the two new keys (`page`
and `units`), and the remedy: run the `extract-filing` skill again, or add `page` and
`units` to each Pass 2 item from the page where its figure is printed, and write `amount`
as printed. The CLI's pickle cache marker changed with it (`p14a-units-in-millions-v1` →
`p14b-pass2-units-v1`): a cache written before held Pass 2 items with no page or units.

### The Pass 1 shape: printed lines, and Python's sums

`P11a`, on the user's decision of 2026-10-02 ("go with option A"). Both routes.

Every Pass 1 field except `year`, the three strings `ticker`, `company_name` and
`currency`, and the two unit statements `units` and `share_units` (below) is a **list
of printed lines**:

```json
"capex": [
  {"label": "Payments for property and equipment", "value": 26642, "page": 23},
  {"label": "Payments for business acquisitions, net of cash acquired", "value": 53, "page": 23}
]
```

- `label` is the row's label as printed, a non-empty string. `value` is the one figure
  printed on that row for that year, under the field's sign rule, a finite JSON number.
  `page` is the 1-based PDF page, a positive integer. All three are required.
- **The model never adds, subtracts or nets rows.** `figure_from_printed_lines` adds a
  field's values; it is the only place a Pass 1 figure is formed, for both routes.
- `[]` says the filing prints no such row, and for a component field reads as 0. The
  check rows differ (`P11a` round 2): `[]` on `gross_profit` or `operating_income` is
  `None` and that check is skipped as "not printed"; `[]` on `total_assets` or
  `total_liabilities_and_equity` is `None` and the check fails as "not extracted"; `[]`
  on `net_income` **stops** like an absent key, because every income statement prints
  it and it starts the cash flow statement. No path turns an unprinted row into a
  printed `0`. **An absent key stops**
  (rule 3), naming the field and the year; a malformed line stops naming the field, the
  year and the line index. Both are found by `pass1_problems` before any figure is
  formed, and route A's parser raises them as `Pass1ShapeError`, a `ValueError`.
- Every row of the income statement down to net income, and of the balance sheet, is
  accounted for once: in one field, or inside a printed total listed in one field. An
  unmapped row goes into its section's catch-all. A row printed between liabilities
  and equity (a redeemable noncontrolling interest) belongs to
  `other_non_current_liabilities`. The two noncontrolling interest memos copy a row
  that already belongs to another field, and are in no total.
- **Check fields**, read only to check the reading: `gross_profit`, `operating_income`
  and `net_income` in each year, and `total_assets` and `total_liabilities_and_equity`
  in the balance sheet, each the printed row. `gross_profit` may be `[]`: Walmart prints
  none. `operating_income` may be `[]` too. `net_income` may not: it is also the cash
  flow's starting figure, as before.

### The printed unit statements, and the conversion to millions

`P14a`, on the user's approval of 2026-10-04 (rule 1, option C applied to units;
backlog item 44). Filings print in different units, measured on the latest filing of
each company in `10K_filings/`:

| Company | Page | Printed unit statement |
|---|---|---|
| Walmart, 10-K 2026-01-31 | 21 | `(Amounts in millions, except per share data)` |
| AbbVie, 10-K 2025-12-31 | 21 | `(in millions, except per share data)` |
| Chipotle, 10-K 2025-12-31 | 29 | `(in thousands, except per share data)` |
| Okta, 10-K 2026-01-31 | 58 | `(dollars in millions, shares in thousands, except per share data)` |
| L3Harris, 10-K 2026-01-02 | 35 | `(In millions, except per share amounts)`, under `CONSOLIDATED STATEMENT OF OPERATIONS`, on the same text line as the column years (2025-01-03: p41; 2023-12-29: p28) |

So the model returns two **printed unit statements**, each `{"printed": ..., "page":
...}`: `units`, the words that state the unit of the money figures (usually just under
the income statement's title), and `share_units`, the words that state the unit of the
diluted share count. When one statement covers both, `share_units` copies it with its
page. **The model converts nothing and returns no scale word of its own**: the prompt
says to copy every figure as printed and never convert one.

**Python reads the scale** (`printed_scale(printed, unit_of) -> PrintedScale`), from the
words, casefolded. The scale words are `thousands`, `millions` and `billions`;
`_SCALE_IN_MILLIONS` maps each to one printed unit in millions (1/1000, 1, 1000: a
table of numbers, rule 2). Each `in <scale>` clause has a subject, the words before it:
a subject naming dollars (or `$`) states the money scale, one naming shares states the
share scale, and none (or only `amounts`, the one word a filing here prints in that
place: Walmart 10-K 2026-01-31 page 21, `(Amounts in millions, except per share data)`)
states both. A subject named wins over none. "per share" and "per-share" except only
per-share figures, so they are removed first. **After that, shares are read in one form
only: a `<shares> in <scale>` clause** (`shares in thousands`, `dollar and share amounts
in thousands`). Any other mention of shares **stops the share scale**: an exception
(`except share and per share data`, `except shares`, `except share data`) and any words
this reader does not name (`excluding share data`, `other than shares`, `but not
shares`, `shares in actual numbers`). Dollars are read the same way for the money
scale: a mention of dollars outside a `<dollars> in <scale>` clause stops it. Every
case not read stops, as a `Pass1ShapeError` problem naming the field, the text and the
page; it never falls back to millions (rule 3):

| Printed statement | Money | Share count |
|---|---|---|
| `(Amounts in millions, except per share data)` | millions | millions |
| `(in thousands, except per share data)` | thousands | thousands |
| `(dollars in millions, shares in thousands, except per share data)` | millions | thousands |
| `(In millions)` | millions | millions |
| `(in millions, except share and per share data)` | millions | **stops** |
| `(In millions, excluding share data)`, `(in millions, other than shares)`, `(in millions, but not shares)`, `(in millions; shares in actual numbers)` | millions | **stops** |
| `(Shares in thousands)` | **stops** | thousands |
| `(in dollars)`, or any text with no scale word | **stops** | **stops** |
| two different scales for one kind, or a scale word inside the exception | **stops** | **stops** |

The shape and the reading are part of `pass1_problems`, so both routes report them
with every other Pass 1 problem, and route A's shape retry asks again.

**Each statement is looked up on its page** (`_read_cited_pages`), in two checks:

- **as a whole printed statement.** `unit_statement_on_page(printed, page_text)`
  normalises only whitespace, on both sides (each run made one space); case,
  parentheses and commas are compared as they are. A statement in parentheses must
  equal one whole parenthesised group of the page's text (its line breaks made
  spaces, so a statement that wraps, or that shares its text line with the column
  years, is found). A statement with no parenthesis must equal one whole text line. A
  fragment is never found: `(in thousands)` is not found on Okta's page 58, which
  prints `(dollars in millions, shares in thousands, except per share data)`. A
  printed line's check is looser (normalised words, `_normalised_text`); a unit
  statement's is not, because a fragment can state a different scale;
- **on a page of the figures it governs.** `units` must cite a page that a printed line
  of the income statement cites (revenue through `diluted_shares`, any year of the
  answer); `share_units` must cite the `units` page or a page a `diluted_shares` line
  cites. Otherwise the failure names the field, its page and the pages allowed. The
  words `(In thousands)` are printed on page 62 of the L3Harris 10-K 2026-01-02, above
  a stock-award table; cited as `units` there, they fail, because the income statement
  is on page 35.

A page beyond the PDF or with no text layer is not confirmed.
**Unlike a printed line, a unit statement not confirmed stops the run**: route A
retries it with the other failed checks and, after the last retry, raises `ValueError`
naming the field, the text and the page; route B's loader lists it among its problems
and stops, and `check` exits 2. The reason: the scale converts every figure, a wrong
one moves every figure by a factor of 1,000, and nothing downstream can detect it.

**The conversion, once per filing.** `convert_filing_to_millions(financials,
non_recurring, units)` converts every money figure of the filing's statements with the
money scale, the diluted share count with the share scale, and each Pass 2 item with its
own scale via `pass2_amount_scale(item.printed_units, item.amount)` (`P14b`, backlog
item 77, user decision "fix 77a" on 2026-10-04). It sets each balance sheet's
`printed_unit_in_millions`. One operation per figure, after its printed lines are summed:
divide by 1,000 for thousands, multiply by 1,000 for billions, multiply by 1 (exact) for
millions, so a filing in millions does not move by a bit. It stops on a balance sheet
already converted, and on a statement field it does not list. Both routes call it
**after that filing's Pass 2 and before any merge**: route A in `extract_financials` (so
the one-filing path and `extract_multi_year` both get converted statements), route B in
`load_session_extraction`. Pass 2's prompt is built from the statements as printed, so
the context figures the model sees are in the filing's own units. Pass 2's schema asks for
each `amount` as printed, its `page`, and its unit words (`units.printed`) with their
`page` (`units.page`). Both routes confirm each Pass 2 item's figure and unit words on
their cited pages (`pass2_page_failures` / `_pass2_item_failures`), stopping on any
failure. The model converts nothing.
`parse_pass1` alone returns the statements as printed.

### The subcommands

`python -m ingestion.session_extraction <command>`. `--filing N` is the 0-based index
into `filings`.

| Command | Does |
|---|---|
| `plan <pdf args> -t TICKER [-n NAME] -o FILE [--force]` | resolves the filings with `parse_pdf_args`, plans them with `plan_filings`, hashes them with `fingerprint_filings`, writes the skeleton. Refuses to overwrite without `--force`. With several filings, refuses one with no fiscal year. Stops when a filing's given year disagrees with its content (`verify_filing_years`) |
| `locate FILE --filing N` | after checking the PDF's sha256, prints the pages holding a statement title (income/operations/earnings, balance sheet, cash flows) and the non-recurring keywords, with match counts. A *title line* is a line holding the title, no digit, at most 80 characters. **Page numbers and counts only, never a figure** |
| `text FILE --filing N --pages A-B` | after checking the PDF's sha256, prints the text layer of those 1-based pages under `=== page N ===` markers. At most 20 pages per call. Added because the Read tool cannot render PDF pages on the macOS machine (no `pdftoppm`) |
| `prompt FILE --filing N --pass 1\|2` | prints the system and user prompt from `pass1_prompts` / `pass2_prompts`. Pass 2 requires that filing's Pass 1 to pass the key check first, because its summary is built from it |
| `check FILE` | runs the loader; prints every problem, the check table, each filing's two unit statements with the scale read from each, and the failed checks. Exit 0 clean, 1 failed checks only, 2 the loader stops |

### The loader, and what stops it

`load_session_extraction(path) -> SessionExtraction` (the merged statements and items,
in millions, the label, the validation errors, the file path, and one `SessionFiling`
per filing with its plan, sha256, size, pages read and its two unit statements with
their scales).

It raises `ValueError`, naming the file, the filing index and its PDF, and the year and
key where one applies, when:

- `format` is not `session-extraction-v4` (a `session-extraction-v1` file is refused by
  name: extract it again; a `session-extraction-v2` file is refused by name: extract it
  again, or add `units` and `share_units` from the filing's printed unit statement; a
  `session-extraction-v3` file is refused by name: run the `extract-filing` skill again,
  or add `page` and `units` to each Pass 2 item and write `amount` as printed);
- `ticker` is absent or empty, or `company_name` is absent or not a string;
- `extracted_by.model` is absent or empty;
- the filings are not in `plan_filings` order, or a recorded `target_years` or
  `include_bs` differs from what `plan_filings` gives — the plan is never taken on trust;
- with several filings, a `fiscal_year` is not a positive integer;
- a filing's `pass1` or `pass2` is `null`;
- a PDF is missing, or its sha256 differs from `pdf_sha256` (rule 5);
- **any key `_FINANCIALS_SCHEMA` names is absent** from a `historical_years` entry, or
  from `latest_balance_sheet` when it is not `{}`, or is not a list of printed lines, or
  a line lacks `label`, `value` or `page` or holds one of the wrong kind (an empty
  label, a `NaN`, `"12"` or `true` value, a page below 1). An empty list is accepted.
  These are `pass1_problems`, the same check route A's parser runs since `P11a`;
- `pass1.units` or `pass1.share_units` is absent, not `{"printed": <non-empty string>,
  "page": <positive integer>}`, or its scale cannot be read (`printed_scale`); also
  `pass1_problems`;
- a unit statement is not found on the page it cites as a whole printed statement, its
  page is not a page of the figures it governs, or the page is beyond the PDF or has
  no text layer (`P14a`; route A retries this, then stops);
- a year appears twice in one `pass1`, or the plan's `target_years` is set and the
  years in `pass1` differ from it;
- `include_bs` is true and `latest_balance_sheet` is empty or has no positive `year`,
  or it is false and `latest_balance_sheet` is not `{}`;
- `pass2.non_recurring_items` is not a list, an item is not an object, an item lacks
  any key `_NRI_SCHEMA` names, its `amount` is not a finite JSON number (`NaN`, `"12"`,
  `true` and `null` all stop), its `year` is not a JSON integer, its `page` is not a
  positive integer, its `units` is not `{"printed": <non-empty string>, "page": <positive integer>}`,
  or its scale cannot be read (`pass2_amount_scale`). Each problem names the item by its
  index, year and description (`P9d-pass2-checks`, `P14b`); route A's parser now
  stops on an `amount` of `"12"` (`P14b`), and still coerces a `year` of `2025.7` to 2025
  (backlog item 1);
- a Pass 2 item is not found on its cited page: its figure is not held by any text line on
  `page`, or its unit words are not confirmed on `units.page` (`pass2_page_failures`, `P14b`).
  Unlike Pass 1 printed lines, Pass 2 item failures stop the run;
- route A's Pass 2 parser rejects `pass2` (for example an item with no `confidence`);
- `pages_read` for a written pass is absent or empty.

Every problem is collected before stopping, so one `check` lists them all. One more stop
comes after that list, while the filings are parsed: **a PDF `pdfplumber` cannot open**
stops the loader with a `ValueError` that names the filing (the session file, the filing
index and its PDF's file name) and the PDF's sha256 and size, because no printed
line could be looked up on its page (`P12a`; see "The page check" below).

**Failed checks are returned, not raised**: the arithmetic checks and, since `P12a`, each
printed line not found on its cited page. Route A keeps its figures and shows the
failures after its last retry; route B must reach the same result from the same JSON.
Route B has no retry loop: `check` prints the failures, and the session reads the rows
again and corrects a line only where it does not match the filing.

### The fiscal year is verified against the filing

Until `P10c`, `discover_filings` took the year from the filename unchecked, and
L3Harris's fiscal-2025 10-K (period end 2026-01-02) was planned as 2026. Both routes now
go through `verify_filing_years`; see "Where each filing's fiscal year comes from" above.

**Still open: the prompt names a year, never a date.** A filing whose columns carry dates
(L3Harris before fiscal 2025) is asked for "fiscal year 2024" with no date beside it.
With the remedy, the 2025-01-03 filing is asked for 2024, and its column is headed
`January 3, 2025`. The prompts are in `ingestion/claude_extractor.py`, outside `P10c`.

## Validation

`_validate_extracted_data` checks the **reading**, after Python has added each field's
printed lines. Both checks print in one table, `EXTRACTED DATA VALIDATION — ARITHMETIC
CHECK`.

**Income statement, every year.** The printed subtotal rows against the figures the
component fields give, failing above **0.5%**:

- `gross_profit` against `revenue − cost_of_revenue`. **Skipped, and the table says
  "not printed", when `gross_profit` is `[]`**: the filing prints no such row;
- `operating_income` against `revenue − cost_of_revenue − sga − rd_expense −
  other_operating_expense`, **skipped and labelled the same way when it is `[]`**;
- `net_income` against that EBIT `+ interest_income − interest_expense +
  other_non_operating − tax_expense`.

**Balance sheet, when there is one.** The printed `total_assets` row against the sum of
the nine mapped asset fields (`BalanceSheet.total_assets`), and the printed
`total_liabilities_and_equity` row against the sum of the seven mapped liability and
equity fields (`BalanceSheet.total_liabilities_and_equity`). The noncontrolling interest
memos count in neither. **A row fails when the difference exceeds 1 in the filing's
printed unit** (`BALANCE_CHECK_TOLERANCE`, `printed_total_status`): rounding, and
nothing more. The parser checks the figures as printed, so its threshold is 1. The CLI
and the page check them after the conversion, in millions, through
`BalanceSheet.printed_total_check`, at `printed_unit_in_millions` (0.001 $M for a filing
in thousands); the difference is rounded to `PRINTED_UNIT_DECIMALS` (6) places of a
printed unit first, because the conversion leaves binary noise of about 1e-8 printed
units, which without the rounding failed 14,294 of 20,000 gaps of exactly 1 printed
unit (`P14a`). A total given as `[]` is not extracted, and its row reads `FAIL: not
extracted` with no gap. The CLI's old 2% tolerance, which on Walmart's 284,668 of assets hid up to
5,693, is gone.

**It is a check, not a repair.** Nothing adjusts a figure to close a gap, and the prompt
no longer asks the model to: "Adjust catch-alls to close any gap" was deleted by `P11a`,
because a model-plugged balance sheet can never fail its check. On the user's decision
of 2026-10-02 ("if the balance sheet check doesn't pass, just fail it and show it"), a
failure is shown in the CLI, in `check`, and on the statements page with the word
`FAIL`, and the figures are kept.

**Route A's retries.** Three kinds of answer go back to the model, up to two retries:
text that is not JSON, an answer with an absent key, a malformed line or an unreadable
unit statement, and an answer whose checks fail (a unit statement not found on its page
is one of these, and after the last retry it stops the run). Each retry asks the model to **read the rows again**; none asks it
to change a value so that a check passes. The shape retry and the check retry send the
PDF again with the prompt, since `P11a` run 3: a model asked to read rows from a filing it
cannot see can only make them up. The JSON repair retry is syntactic and sends none.
**The check retry states no amount** (`P11a` round 2, review F7): it names each failed
check, its side, and the rows Python added (label, field, page), but not the printed
figure, the sum or the gap. A model told the exact gap can add a row of that size; since
`P12a` the page check below looks for such a row, within its limits. The
full wording, with the gap, is what `check`, the CLI and route A's console print: each
failure is a `_CheckFailure` holding both.
After the last retry the first two stop the run, and a failed check is shown and kept.
A line not found on its page is a failed check of the third kind, and goes through the
same retry and the same final print. The check retry's opening says so: Python added the
printed lines, compared the sums with the printed totals, **and looked for each line on
the page it cites**. Its page wording names where, the field, the line index, the label
and the page, asks for the row to be read again with its label as printed and its page,
and states no value and no amount.

### The page check: each printed line on the page it cites

Added by `P12a` (backlog item 59, from the `P11a` review's F7). Until it, nothing checked
that a line was printed at all: a model could add a row the filing never printed, with a
plausible label and page, and if it balanced every check passed.

**The rule** is one pure function, `claude_extractor.printed_line_on_page(label, value,
page_text) -> bool`, with no PDF and no I/O:

1. A **figure** is a number as a statement prints it: an optional `(`, an optional `$`
   with optional spaces, digits with optional thousands commas (whole groups of three),
   an optional decimal part, an optional `)`. Its magnitude is the number without the
   commas, `$` and parentheses. A dash standing alone (`—`, `–` or `-`, a whitespace
   token) is a printed zero.
2. A text line **holds the value** when one of its figures has a magnitude equal to
   `abs(value)`; a value of 0 is held by a figure `0` or a standalone dash. Signs and
   parentheses are not compared.
3. **Normalised text**: remove every figure, casefold, replace each run of characters
   that is neither a letter nor a digit with one space, strip; for the label and the
   page alike. So `stockholders’ equity` equals `stockholders' equity`, and `Senior notes
   due 2030` is compared without its year on both sides.
4. **The line is found** when a text line L of the page holds the value and the
   normalised label, not empty, is a substring of the normalised text of L; of the line
   above L, a space, then L; or of L, a space, then the line below L. The joined forms
   let a label wrap onto a second text line, and each counts only when the normalised
   label is **not wholly inside the neighbouring line alone** (`P12a` round 2, review
   F1). A wrapped label is split, so neither half holds it whole; a label printed whole
   on the row above or below is that row's, and never takes L's figure. Walmart's
   `Prepaid expenses and other` with `84,874` (the `Total current assets` row below it)
   or `58,851` (the `Inventories` row above it) is not found.

**The walk**, `_printed_line_failures(data, pdf_bytes)`, takes a Pass 1 answer that has
passed `pass1_problems` and looks up **every** printed line: every line field of every
`historical_years` entry and of `latest_balance_sheet`, the five check rows and the two
noncontrolling interest memos included. `_read_cited_pages` opens the PDF once with
`pdfplumber` and reads each cited page's text once, however many lines cite it. Per line:

| Outcome | Result |
|---|---|
| found | nothing to report |
| not found | a failed check: no text line on that page holds both the label and the figure |
| the page is beyond the PDF's last page | a failed check naming the page and the page count |
| the page has no text layer (`extract_text()` gives `None` or only whitespace) | a failed check: the line **cannot be confirmed**. Never a pass: a line not looked at is not confirmed (rule 3) |
| `pdfplumber` cannot open the PDF | **the run stops**: `ValueError` naming the PDF by sha256 and size; route B's loader prefixes the filing's `where` (session file, filing index, PDF file name), since route A holds only the bytes. `pdfplumber` raises `pdfplumber.utils.exceptions.PdfminerException` (and `MalformedPDFException` for a malformed page); only those two are caught, never a broad `Exception` |

Each failure is a `_CheckFailure`. `message` names where (`year 2026` or `balance sheet
2026`), the field, the line index, the label, the value, the page and why. `retry_message`
names the same without the value.

**Where each route runs it.** Route A, in `_run_financials_pass`, after
`_parse_financials_response` returns: the page failures join the arithmetic ones, every
attempt, on the PDF bytes it already sends to the model. Route B, in
`load_session_extraction`, after `parse_pass1`, through the public wrapper
`printed_line_page_failures(json_str, pdf_bytes) -> list[str]`, on the bytes of
`plan.pdf_path`, whose sha256 the loader has just checked. Its failures join
`validation_errors` with the same `where` prefix; `check` exits 1 when failed checks are
the only problems, and its "Clean" line says every printed line was found on its page.
One walk serves both routes. The CLI prints route B's failures; **no failed reading
check reaches the web page today**, for either route (backlog item 62). A CLI pickle cache
hit skips extraction, and so skips this check, as it skips the arithmetic one.

**Cost**, measured on Walmart's fiscal 2026 10-K (86 pages, 89 printed lines on pages
21, 22, 23 and 27) on the macOS machine: about **0.55 s** per walk, nearly all of it
`pdfplumber` reading the four cited pages. 89 of 89 lines are found.

**Limits. None is fixed; each is stated so nobody reads more into a pass.**

- **It confirms a row is printed with that figure, not that the figure is in the right
  year's column.** Walmart's `Prepaid expenses and other` with value `4,011` (the prior
  year's) on page 22 is found, because the same text line prints `4,124 4,011`. A column
  check needs word positions, not text lines.
- **A label is matched as text, not as a whole printed row.** A short label can be
  found inside a longer printed label, with that row's own figure: `Debt` with `34,624`,
  the figure of Walmart's `Long-term debt` row on page 22, is found. And a label that
  runs from one printed row into the next is found with the figure of either row:
  `Prepaid expenses and other Total` with `84,874` is found (`P12a` round 2 review, F6).
  Either way the model must write a label the filing does not print; a printed label
  never takes a neighbouring row's figure. A stricter join is backlog item 64.
- **It does not detect a real row listed under two fields.** The prompt forbids it;
  nothing checks it.
- **The Pass 2 figure check confirms that the number is printed on the page, not that it is the item's number.**
  For example, page 27 of Walmart's 10-K prints `0.8` in a stock-award table, so a PhonePe
  item citing `0.8` on page 27 would pass the figure check alone if the inline unit words
  did not independently state `0.7` (`P14b`).

The check rows (`gross_profit`, `operating_income`, `net_income`, the two balance sheet
totals) are read **only for this comparison**. They are never stored as figures: the
first three are derived properties on `IncomeStatement`, and the two totals are memo
fields on `BalanceSheet`. See [data-contract.md](data-contract.md).

## Known defects in this file

Full detail in [9-reference/refactor-backlog.md](../9-reference/refactor-backlog.md).

| | |
|---|---|
| ~~46 `.get(field, 0)` calls~~ | **closed in the Pass 1 parser by `P11a`**: every key is read with `[]` after `pass1_problems` proved it present. The file's census count fell 49 → 2; the two left are the Gemini token counts (`getattr(…, 0) or 0`), not figures. Item 1 |
| **D&A subtracted inside the parser** (`_parse_financials_response`) | an accounting decision taken silently in a parser, now on two summed figures that are never defaulted. Item 10 |
| **1 mypy error** (measured at `P11a`; 16 when this table was written) | `_call_claude`'s `content` list against the SDK's TypedDict. Item 11 |
| **Provider default divergence** | above. Item 13 |
