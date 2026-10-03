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
| A | the model, over the API | `extract_multi_year` / `extract_financials` | two API calls per filing, plus up to two retries |
| B | Claude, inside a Claude Code session | `ingestion/session_extraction.py` | the session only; no API call |

Both routes answer the **same prompts** with the **same JSON**, and both go through the
same functions from that JSON onwards. Each of these has one definition, in
`claude_extractor.py`, and both routes call it:

| Job | Function |
|---|---|
| which years and which balance sheet from which filing | `plan_filings` → `list[FilingPlan]` |
| the Pass 1 prompt for a plan | `pass1_prompts(plan)` |
| the Pass 2 prompt for a plan and that filing's own Pass 1 result | `pass2_prompts(plan, financials)` |
| Pass 1 JSON → statements + arithmetic errors | `parse_pass1` |
| Pass 2 JSON → items | `parse_pass2` |
| per-filing results → one result | `merge_filing_extractions` (several filings only; one filing is returned as parsed, by both routes) |

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

### The session file, `session-extraction-v1`

JSON, UTF-8, one file per company run, kept under `extractions/` (git-ignored: it is
data).

```json
{
  "format": "session-extraction-v1",
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
  describes: exactly what route A parses. Stored as JSON objects, not strings.
- `pages_read` holds the 1-based PDF pages read for each pass. A locator: recorded and
  printed, never computed from.
- `extracted_by.model` is printed as declared. `tool` and `date` are a record for a
  human and are not read.
- A single bare PDF gets `fiscal_year` 0, exactly as `parse_pdf_args` gives route A.

### The subcommands

`python -m ingestion.session_extraction <command>`. `--filing N` is the 0-based index
into `filings`.

| Command | Does |
|---|---|
| `plan <pdf args> -t TICKER [-n NAME] -o FILE [--force]` | resolves the filings with `parse_pdf_args`, plans them with `plan_filings`, hashes them with `fingerprint_filings`, writes the skeleton. Refuses to overwrite without `--force`. With several filings, refuses one with no fiscal year. Stops when a filing's given year disagrees with its content (`verify_filing_years`) |
| `locate FILE --filing N` | after checking the PDF's sha256, prints the pages holding a statement title (income/operations/earnings, balance sheet, cash flows) and the non-recurring keywords, with match counts. A *title line* is a line holding the title, no digit, at most 80 characters. **Page numbers and counts only, never a figure** |
| `text FILE --filing N --pages A-B` | after checking the PDF's sha256, prints the text layer of those 1-based pages under `=== page N ===` markers. At most 20 pages per call. Added because the Read tool cannot render PDF pages on the macOS machine (no `pdftoppm`) |
| `prompt FILE --filing N --pass 1\|2` | prints the system and user prompt from `pass1_prompts` / `pass2_prompts`. Pass 2 requires that filing's Pass 1 to pass the key check first, because its summary is built from it |
| `check FILE` | runs the loader; prints every problem, the arithmetic table, and the validation errors. Exit 0 clean, 1 arithmetic validation errors only, 2 the loader stops |

### The loader, and what stops it

`load_session_extraction(path) -> SessionExtraction` (the merged statements, the items,
the label, the validation errors, the file path, and one `SessionFiling` per filing with
its plan, sha256, size and pages read).

It raises `ValueError`, naming the file, the filing index and its PDF, and the year and
key where one applies, when:

- `format` is not `session-extraction-v1`;
- `ticker` is absent or empty, or `company_name` is absent or not a string;
- `extracted_by.model` is absent or empty;
- the filings are not in `plan_filings` order, or a recorded `target_years` or
  `include_bs` differs from what `plan_filings` gives — the plan is never taken on trust;
- with several filings, a `fiscal_year` is not a positive integer;
- a filing's `pass1` or `pass2` is `null`;
- a PDF is missing, or its sha256 differs from `pdf_sha256` (rule 5);
- **any key `_FINANCIALS_SCHEMA` names is absent** from a `historical_years` entry, or
  from `latest_balance_sheet` when `include_bs` is true, or holds a non-number. An
  explicit `0` is accepted. **This is stricter than route A on purpose**: route A's
  parser reads an absent field as zero (backlog item 1), and is unchanged;
- a year appears twice in one `pass1`, or the plan's `target_years` is set and the
  years in `pass1` differ from it;
- `include_bs` is true and `latest_balance_sheet` is empty or has no positive `year`,
  or it is false and `latest_balance_sheet` is not `{}`;
- `pass2.non_recurring_items` is not a list, an item is not an object, an item lacks
  any key `_NRI_SCHEMA` names, its `amount` is not a finite JSON number (`NaN`, `"12"`,
  `true` and `null` all stop), or its `year` is not a JSON integer. Each problem names
  the item by its index, year and description. Added by `P9d-pass2-checks`; route A's
  parser still coerces `"12"` to 12.0 and `2025.7` to 2025 (backlog item 1);
- route A's Pass 2 parser rejects `pass2` (for example an item with no `confidence`);
- `pages_read` for a written pass is absent or empty.

Every problem is collected before stopping, so one `check` lists them all.

**Arithmetic validation errors are returned, not raised.** Route A keeps its figures
with a warning after its last retry; route B must reach the same result from the same
JSON. Route B has no retry loop: `check` prints the errors, and the session reads the
page again and corrects the file.

### The fiscal year is verified against the filing

Until `P10c`, `discover_filings` took the year from the filename unchecked, and
L3Harris's fiscal-2025 10-K (period end 2026-01-02) was planned as 2026. Both routes now
go through `verify_filing_years`; see "Where each filing's fiscal year comes from" above.

**Still open: the prompt names a year, never a date.** A filing whose columns carry dates
(L3Harris before fiscal 2025) is asked for "fiscal year 2024" with no date beside it.
With the remedy, the 2025-01-03 filing is asked for 2024, and its column is headed
`January 3, 2025`. The prompts are in `ingestion/claude_extractor.py`, outside `P10c`.

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
