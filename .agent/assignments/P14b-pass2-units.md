---
id: P14b-pass2-units
phase: 14 — the Pass 1 role (the user's decision "fix 77a", 2026-10-04)
agent: programmer
depends_on: [P14a-units]
---

# Each Pass 2 item copies its figure as printed, with its page and the printed words that state its unit. Python reads the scale and converts each item (backlog item 77)

## Objective

Pass 2's schema asks for each `amount` "in the same units as financials"
(`ingestion/claude_extractor.py`, `_NRI_SCHEMA`). So the model converts a note's figure
when the note prints another scale. Walmart's session file holds `700` for a charge
that page 27 prints as "$0.7 billion". That conversion breaks rule 1. For a filing in
thousands whose note prints "$5.2 million", the amount depends on whether the model
converts: 5,200 (correct only by the model's arithmetic) or 5.2 (then read as
thousands, 0.0052 $M, silently wrong).

When this unit is done, each Pass 2 item carries the figure as printed (`0.7`), the page
it is printed on, and the printed words that state its unit, with their page. Python
reads the scale from those words, looks both up on their pages, and converts each item
with its own scale. The model converts nothing. The session file format becomes
`session-extraction-v4`. The user approved this change to what the model returns on
2026-10-04 ("fix 77a"); it is recorded under rule 1 in `docs/2-rules/rules.md`.

## What is already true — verify, do not redo

Measured by the overall lead at `6f1166a`, on the macOS machine. If one disagrees, stop
and report it in your entry. Do not edit to make it agree.

| Fact | Command | Result |
|---|---|---|
| test gate | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 954 passed |
| full suite | the same without `--ignore-glob` | 2 failed (the 2 red on purpose), 954 passed |
| lint | `.venv/bin/python -m ruff check .` | 4 errors, all `BLE001` |
| types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 9 errors in 4 files |
| rule 3 census | the grep in `docs/2-rules/rules.md` (quote `'--include=*.py'` under zsh) | 65 |
| Walmart, route B | `.venv/bin/python -m ingestion.session_extraction check extractions/WMT.json` | exit 0; 89 of 89 lines found; file is `session-extraction-v3` |
| Walmart, end to end | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json` | revenue 713,163 (FY2026); PV of terminal value 214,819M; implied price $28.02; downside -73.1% |

Walmart's four Pass 2 items today (`extractions/WMT.json`), and where each figure is
printed in `10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf`, read with
`pdfplumber` by the overall lead:

| Year | Item | `amount` now | Printed | PDF page, text line |
|---|---|---|---|---|
| 2026 | PhonePe share-based payment charge, `sga`, `add_back` | 700 | `$0.7 billion` | 27: `$0.7 billion (a portion of which was based on grant-date fair value) in operating, ...` |
| 2026 | Other gains and losses, `other_non_operating`, `remove` | 2075 | `(2,075)` | 22: `Other (gains) and losses (2,075) 794 3,027` |
| 2025 | Other gains and losses, `add_back` | 794 | `794` | 22, the same line |
| 2024 | Other gains and losses, `add_back` | 3027 | `3,027` | 22, the same line |

The income statement's unit statement is on page 21:
`(Amounts in millions, except per share data) 2026 2025 2024`. The statement continues
onto page 22 with no new unit statement for it.

## What to do

1. **Schema and prompt** (`_NRI_SCHEMA`, `_NRI_SYSTEM_PROMPT` in
   `ingestion/claude_extractor.py`). Each item keeps its eight keys and gains two:
   - `amount`: "number — the ONE figure printed in the filing, positive, exactly as
     printed, in the unit printed with it or stated for its table. Never converted:
     Python reads 'units' and converts."
   - `page` (new): "int — the 1-based PDF page the figure is printed on".
   - `units` (new): `{"printed": "string — the words printed that state the unit of
     this figure, copied exactly: the figure with the scale word printed right after it
     (e.g. '$0.7 billion'), or the unit statement of the statement or table the figure
     is printed in (e.g. '(in millions, except per share data)')", "page": "int — the
     1-based PDF page those words are printed on"}`.
   - Remove "same units as financials" everywhere. Add to RULES: copy each amount as
     printed; never convert, add, subtract or net figures; one item is one printed
     figure. **Reason:** rule 1, and the user's decision "fix 77a".
2. **Python reads each item's scale.** Add one pure function,
   `pass2_amount_scale(printed: str, amount: float) -> PrintedScale`. It is the only
   place a Pass 2 scale is read (rule 2). Two forms, and nothing else:
   - **Inline form.** The whole of `printed`, whitespace-normalised and casefolded,
     matches: an optional `$`, one number (commas and a decimal point allowed), one or
     more spaces, then `thousand`, `million` or `billion`, with an optional `s`, and
     nothing after it. The scale is that word, mapped through `_SCALE_IN_MILLIONS`
     (use the plural key: `billion` reads as `billions`). The number in the text must
     equal `amount`. If it does not, stop and name both.
   - **Statement form.** Anything else goes to `printed_scale(printed, "money
     figures")`, the P14a reader, unchanged. Its stops apply as they are.
   - **Reason:** rule 1 (Python reads the scale), rule 3 (a text with no scale word
     stops; it never falls back to the filing's scale).
3. **Parse** (`_parse_nri_response`). Require `page` (an int of 1 or more, not a bool)
   and `units` (an object with a non-empty string `printed` and an int `page` of 1 or
   more), and `amount` a finite number above 0. Read the scale with step 2. Any problem
   raises `ValueError` naming the year, the description, the key and the reason. Keep
   the existing `confidence` and `source` stops as they are.
4. **Model** (`models/financial_statements.py`, `NonRecurringItem`). Add three
   required fields with no default, placed before `source`: `page: int`,
   `printed_units: str`, `units_page: int`. Change the `amount` comment: "as printed
   until `convert_filing_to_millions`; in millions after". **Reason:** rule 3 (no
   default), rule 4 (the trace to the page travels with the item).
5. **Page checks.** Add `_pass2_item_failures(items, pdf_bytes)` beside
   `_unit_statement_failures`, and a public wrapper `pass2_page_failures(json_str,
   pdf_bytes) -> list[str]` for route B, as `unit_statement_page_failures` is for
   Pass 1. For each item, read its pages with `_read_cited_pages`:
   - **The figure.** One text line of page `page` holds `amount`
     (`_text_line_holds(line, amount)`).
   - **The unit words, inline form.** `units.page` equals `page`, and the
     whitespace-normalised `units.printed` is a substring of the whitespace-normalised
     page text (`_whitespace_normalised`; case is compared as it is).
   - **The unit words, statement form.** `units.page` is `page` or `page - 1` (a
     statement or table that starts on the page before), and
     `unit_statement_on_page(units.printed, page_text)` is true on `units.page`.
   - A page beyond the PDF, or with no text layer, is not confirmed.
   - Each message names the item (year and description), what was not found, the text
     and the page.
6. **Every failure in step 5 stops the run.** It is not a failed check that is shown
   with the figures kept. **Reason:** the scale converts the item, a wrong one moves
   it by a factor of 1,000, and an amount not on its page cannot be traced (rules 3
   and 4). This is the P14a rule for a unit statement, applied to Pass 2.
   - **Route A** (`_run_nri_pass`): run step 5 after the parse. On any failure raise
     `ValueError` naming the ticker, the company, the years (as the retry stop in that
     function already does) and every failure. No new retry.
   - **Route B** (`ingestion/session_extraction.py`): the loader runs
     `pass2_page_failures` and stops on any, in the same way as
     `_unit_statement_problems`. `check` exits 2 on them.
7. **Conversion** (`convert_filing_to_millions`). Convert each item with its own scale:
   `pass2_amount_scale(item.printed_units, item.amount).in_millions`, through
   `_in_millions`. Never with the filing's money scale. Add `page`, `printed_units` and
   `units_page` to `_NON_RECURRING_ITEM_NOT_FIGURES`. Update the docstring: it says
   today that Pass 2 takes the money scale.
8. **Session format v4** (`ingestion/session_extraction.py`). `SESSION_FORMAT =
   "session-extraction-v4"`. Refuse a `session-extraction-v3` file by name, as v2 is
   refused: name both formats, the two new keys, and the remedy (run the
   `extract-filing` skill again, or add to each Pass 2 item `page` and `units` from the
   page where its figure is printed, and write `amount` as printed). Keep the v1 and
   v2 refusals. The shape checks (`_pass2_shape_problems`) check the types of `page`
   and `units`. The new keys reach `_PASS2_ITEM_FIELDS` from `_NRI_SCHEMA` by
   themselves. Update the module docstring's format block.
9. **The CLI cache** (`cli.py`). Change `CACHE_FORMAT` to `"p14b-pass2-units-v1"`. A
   pickle written before holds items with no `page` or `units`. Change nothing else in
   `cli.py`.
10. **Docs.** Replace each statement that says the user decides item 77, or that Pass
    2 asks for "same units as financials": `docs/2-rules/llm-boundary.md` (about lines
    99-118), `docs/4-conventions/units-and-signs.md` (about lines 46-51),
    `docs/3-architecture/extraction.md` (the Pass 2 section, the end of "The printed
    unit statements, and the conversion to millions", and the session format).
    `docs/3-architecture/data-contract.md`: the three new `NonRecurringItem` fields.

## Files in scope

- `ingestion/claude_extractor.py`
- `ingestion/session_extraction.py`
- `models/financial_statements.py`
- `cli.py`: the `CACHE_FORMAT` line only
- `docs/2-rules/llm-boundary.md`
- `docs/4-conventions/units-and-signs.md`
- `docs/3-architecture/extraction.md`
- `docs/3-architecture/data-contract.md`
- your journal entry, `.agent/journal/<timestamp>-programmer-p14b-pass2-units.md`

**Nothing else.** Work outside this list is a review finding, even if the change is
good. The "Never write `docs/`" rule for the build team does not apply to the four
docs files listed here: the overall lead put them in scope.

## Out of scope

- `tests/`: the tester repairs the fixtures this unit turns red, in `P14b-pass2-units-tests`.
- `extractions/WMT.json` and `.claude/skills/extract-filing/`: the overall lead upgrades
  them to v4 after acceptance. Make your Walmart v4 copy in a scratch folder outside
  the repository, never in `extractions/`.
- `api/`, `templates/`, the rest of `cli.py`: they show the converted amount and the
  source. Showing the printed amount and its unit is a later unit.
- A retry in route A for a Pass 2 page failure: a later decision.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. **Make no paid API call.**

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | no text asks the model to convert | 0 hits | `grep -rn "same units as financials" ingestion/` |
| 2 | the scale reader | `("$0.7 billion", 0.7)` → billions, 1000; `("$5.2 million", 5.2)` → millions, 1; `("$300 thousand", 300)` → thousands, 1/1000; `("(in thousands, except per share data)", 5200)` → thousands; `("(Amounts in millions, except per share data)", 2075)` → millions; each of `("$0.7 billion", 700)`, `("$0.7", 0.7)`, `("(in dollars)", 5)`, `("(Shares in thousands)", 5)` stops with a `ValueError` or `Pass1ShapeError` naming the reason | a scratch script calling `pass2_amount_scale` |
| 3 | Walmart v4 is clean | `check` exits 0 | a v4 copy of `extractions/WMT.json` in scratch: `format` set to v4; the PhonePe item `amount` 0.7, `page` 27, `units` `{"printed": "$0.7 billion", "page": 27}`; the three other items `amount` 2075, 794, 3027, `page` 22, `units` `{"printed": "(Amounts in millions, except per share data)", "page": 21}`. Nothing else changed |
| 4 | Walmart amounts in millions | 700.0, 2075.0, 794.0, 3027.0. By hand: 0.7 × 1,000 = 700; the others × 1 | `load_session_extraction` on the v4 copy, print each item's amount |
| 5 | Walmart end to end does not move | stages 1 to 10 identical to the v3 run in the table above, except the PV of the terminal value, which may differ by 1 (item 70); implied price $28.02 | `cli.py --session-file <v4 copy>`, diffed against the v3 run at `6f1166a` |
| 6 | a filing in thousands | an item `$5.2 million` → 5.2 $M; an item 5,200 under `(in thousands)` → 5.2 $M. By hand: 5.2 × 1; 5,200 / 1,000 | a stub `FilingUnits` in thousands through `convert_filing_to_millions` |
| 7 | each check stops and names the item | five edits of the v4 copy, one at a time, each stops (`check` exit 2), naming the item, the text and the page: (a) item 2025 `amount` 795 (not printed on page 22: the figure check); (b) item 2025 `units.page` 20 (not 22 or 21); (c) PhonePe `units.page` 26 (not 27); (d) item 2024 `units.printed` `(in thousands)` (not on page 21 as a whole statement); (e) PhonePe `amount` 0.8 (the inline text states 0.7: step 2). Do not use 0.8 for the figure check: page 27 prints 0.8 in a stock-award table | `session_extraction check` on each edited copy |
| 8 | route A stops on a mis-cited item and returns a correct one | a stubbed `_call_llm` returning a Pass 2 reply for the real Walmart PDF: the 2026 gains item with `amount` 2076 on page 22 → `ValueError` naming the item; the correct reply → items in printed units with `page`, `printed_units`, `units_page` set; 0 network calls | a scratch script with `_call_llm` replaced and sockets blocked |
| 9 | a v3 file is refused with the remedy | `ValueError` naming `session-extraction-v3`, `session-extraction-v4`, `page`, `units` and the remedy | `load_session_extraction("extractions/WMT.json")` |
| 10 | an old cache is refused | a pickle marked `p14a-units-in-millions-v1` is refused, naming `p14b-pass2-units-v1` | `cli._load_cache` on a scratch pickle |
| 11 | the gates do not get worse | ruff 4 or fewer, mypy 9 or fewer, census 65 or fewer, `GET /` 200 | the commands in the table above |
| 12 | every red test is named | each failing test listed with its cause. Expected causes only: `NonRecurringItem(...)` with no `page`, `printed_units`, `units_page`; Pass 2 fixtures with no `page` or `units`; v3 session fixtures; the old `CACHE_FORMAT` string; and the 2 red on purpose | the full suite, failures grouped by cause |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md`, rule 1, the decision "fix 77a" of 2026-10-04: what the model
  may now return for a Pass 2 item.
- `docs/9-reference/refactor-backlog.md`, item 77; the P14a review's F3 in
  `.agent/journal/2026-10-04T1037-code_reviewer-p14a-units.md`.
- `docs/3-architecture/extraction.md`, "The printed unit statements, and the conversion
  to millions": `printed_scale`, `unit_statement_on_page`, why a unit failure stops.
- `docs/4-conventions/units-and-signs.md`: every money figure in millions.
- `10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf` pages 21, 22 and 27:
  the text lines in the table above.

## Known open items

- Route A's stops in `_run_nri_pass` name the ticker, not the PDF (items 73, 79). Do not
  fix them here.
- `IncomeStatement.non_recurring_items` (a dict) is converted with the money scale in
  `convert_filing_to_millions`. No parser fills it. Leave it as it is, and say in your
  entry whether any code path fills it.
- The pages show the converted amount and the source text only.
- The figure check confirms that the number is printed on the page, not that it is the
  item's number: page 27 prints 0.8 in a stock-award table. State this limit in
  `extraction.md`, as P12a stated the limits of the Pass 1 check.

## Backlog items this unit is NOT fixing

Items 1 (zero defaults), 10 (D&A in the parser), 51 (dead `WARN`), 53 (private
`_NRI_SCHEMA` import: you may leave the import as it is), 61, 63, 64, 72 (`cli.py`
conditional zeros), 73, 74, 78, 79, 80. A reviewer must not raise them against this unit.

## Handoff

### Commits
- `dde9b25`: `P14b: copy printed amounts and units, scale in Python (item 77)`
- `21125ed`: `P14b tester: repair fixtures for session v4 and NonRecurringItem fields, lock unit behaviors`

### Verdicts
- Programmer: `complete` (round 1), entry: `.agent/journal/2026-10-04T1437-programmer-p14b-pass2-units.md`
- Code reviewer: `approved` (round 1), entry: `.agent/journal/2026-10-04T1506-code_reviewer-p14b-pass2-units.md`
- Tester: `pass` (round 1), entry: `.agent/journal/2026-10-04T1508-tester-p14b-pass2-units.md`

### Gates
- Test gate: 1001 passed (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`)
- Full suite: 2 failed (the known two), 1001 passed (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q`)
- Lint: 4 errors, all `BLE001` (`.venv/bin/python -m ruff check .`)
- Types: 9 errors in 4 files (`.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports`)
- Rule 3 census: 65 (`grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" '--include=*.py' models analysis api ingestion | wc -l`)
- Web root route: HTTP 200 (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -c "from starlette.testclient import TestClient; from app import app; print(TestClient(app).get('/').status_code)"`)
- Walmart Route B v4 check: exit 0; 89 of 89 printed lines found; 4 of 4 Pass 2 items confirmed (`.venv/bin/python -m ingestion.session_extraction check /tmp/wmt_v4.json`)
- Walmart end-to-end: revenue 713,163 (FY2026); PV of terminal value 214,819M; implied price $28.02; downside -73.1% (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file /tmp/wmt_v4.json`)

### Findings and notes
- `IncomeStatement.non_recurring_items`: verified that no parser populates this dict directly; only `normalizer.py` populates it where values are already in millions.
- Pass 2 figure check limitation: confirms number presence on a text line of the page, not table column semantics (documented in `docs/3-architecture/extraction.md`).

### Questions for the overall lead
None.


## Overall lead review

**Verdict: `accepted`**, 2026-10-04, at `21125ed`. Reviewed by the overall lead (Claude
Code), on the user's decision that it reviews each unit itself.

**Scope.** `dde9b25` touches only the files in scope and two journal entries.
`21125ed` touches `tests/`, its assignment, its entry and the journal index.

**Re-measured, not read** (every command with the keys empty):

| # | Result |
|---|---|
| 1 | `grep -rn "same units as financials" ingestion/` → 0 |
| 2 | `pass2_amount_scale`: the five valid rows give the stated scales; the four stop rows stop. Also stop: `$0.7 billion in charges`, `-$0.7 billion` |
| 3, 4 | my own v4 copy (the values in this assignment): `check` exit 0, 4 of 4 items, 89 of 89 lines; amounts 700.0, 2075.0, 794.0, 3027.0 |
| 5 | `cli.py` on the v4 copy against the v3 run of `6f1166a`: identical except the new "Pass 2 items looked up" line and the file path; $28.02, PV TV 214,819M |
| 6 | thousands filing: `$5.2 million` → 5.2, 5,200 under `(in thousands)` → 5.2, `$1.1 billion` → 1,100.0, each as derived by hand |
| 7 | (a) to (e) each exit 2 and name the right item |
| 8 | route A, stubbed `_call_llm`, real Walmart PDF, sockets blocked: `amount` 2076 → `ValueError` naming the item; the correct reply → four items with `page`, `printed_units`, `units_page`; 0 network attempts |
| 9, 10 | v3 refused naming both formats, `page`, `units`, the remedy; the old cache refused naming `p14b-pass2-units-v1` |
| 11 | gate 1001 passed; full 2 failed (the known two); ruff 4; mypy 9 in 4 files; census 65; `GET /` 200; guard 48/48 |

**Findings.**

- **F1, minor, not sent back.** `_pass2_item_failures` counts an item as failed when its
  description is a substring of a failure message. Walmart's 2024 description is a
  prefix of the 2025 one, so case 7(a) prints `4 checked, 2 found, 2 not confirmed` for
  one failed item. The stop and its problem list are right. Backlog item 81; assigned to
  `P14b-reasoning`, the next unit in this file.
- **F2, note.** Five blank lines remain where `_whitespace_normalised` was removed.
  Assigned to `P14b-reasoning`.
- **F3, the overall lead's own error.** Step 3 of this assignment required an `amount`
  above 0. That reversed `test_pass2_item_amount_zero_loads`, locked at `P9d-tests`, and
  the assignment did not say so. The tester followed the assignment. The change stands:
  an item of 0 moves no figure, and a 0 cannot be told from "not found". It is recorded
  under item 77.
- **F4, docs.** `extraction.md` still said route A coerces an `amount` of `"12"`. It now
  stops. The overall lead corrected the line.

**Done by the overall lead after acceptance:** `extractions/WMT.json` upgraded to v4 (the
v3 copy is in its scratchpad); the `extract-filing` skill teaches the v4 Pass 2 item;
backlog item 77 closed and item 81 added; `STATUS.md` re-measured.
