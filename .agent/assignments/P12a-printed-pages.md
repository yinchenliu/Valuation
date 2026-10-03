---
id: P12a-printed-pages
phase: 12 — every printed line is found on the page it cites
agent: programmer
depends_on: [P11a-printed-lines, P11a-tests]
---

# Each Pass 1 printed line is looked up on its cited page, for both routes

## Objective

Since `P11a`, every Pass 1 figure is a list of printed lines, each `{label, value, page}`,
and Python adds them. **Nothing checks that a line was printed at all.** A model can
add a row the filing never printed, with a plausible label and page, and every check
Python has passes (backlog item 59, from the `P11a` review's F7). Route A's retry no
longer states the gap amount, but that only makes such a row harder to write. It does not
detect one.

When this unit is done, both routes open the filing's PDF with `pdfplumber` and look for
each printed line on its cited page: its label and its figure, on one text line. A line
that is not found is a **failed check**. It is shown, and the figures are kept, exactly
as a failed balance check is. That follows the user's decision of 2026-10-02 for a
failed reading check ("if the balance sheet check doesn't pass, just fail it and show
it"). The orchestrator applies it here; the user can overturn it.

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Fill in the commit from `git log --oneline -1`.
The scratch scripts below are the orchestrator's, measured at `cca1c99` on 2026-10-03.
Write your own; do not read these as code to copy.

| Fact | Command or method | At `cca1c99` |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 626 passed, 0 failed |
| lint, types, census | the gates in `docs/8-build/environment.md`; the grep at `docs/2-rules/rules.md:65` (quote `'--include=*.py'` under zsh) | ruff 5 (all `BLE001`), mypy 10 in 4 files, census 67 |
| the Walmart session file is v2 | `extractions/WMT.json`, one filing, `Walmart Inc._10-K_2026-01-31_English.pdf` | 89 printed lines: 3 years and one balance sheet, pages 21, 22, 23, 27 |
| every one of the 89 lines is found by the rule below | a scratch script: `pdfplumber` text of the cited page, one line holding both the label and the figure | **89 of 89**, in 0.7 s |
| all 16 filings under `10K_filings/` have a text layer, and print each statement row on one line, label first, then the figures | a scratch scan for `Total assets`, `Net income`, `Accrued …` rows | 16 of 16. Chipotle prints thousands (`8,044,362`); Okta prints a curly apostrophe (`stockholders’ equity`) |
| Walmart page 22 prints `Prepaid expenses and other 4,124 4,011`; no line on page 22 reads `Other current assets`; page 23 holds no `4,124` | a scratch read of pages 22 and 23 | as stated. The PDF has 86 pages |
| route A has the PDF as bytes, and route B reads the PDF to check its sha256 | `_run_financials_pass(pdf_bytes, …)`; `session_extraction._pdf_problems` | |
| route B prints failed checks in `check` and in the CLI | `session_extraction.cmd_check`; `cli.py:946` | |

If any of these disagrees with what you measure, stop and report it. Do not edit to make
it agree.

## The rule: when a printed line is found on its page

One pure function decides it, so a tester can derive every case by hand with no PDF:

```
printed_line_on_page(label: str, value: float, page_text: str) -> bool
```

1. **Figures on a text line.** A figure is a number as a statement prints it: an
   optional `(`, an optional `$` with optional spaces, digits with optional thousands
   commas, an optional decimal part, an optional `)`. Its magnitude is the number with
   the commas, `$` and parentheses removed. A dash standing alone (`—`, `–` or `-`) is a
   printed zero.
2. **A text line holds the value** when one of its figures has a magnitude equal to
   `abs(value)`. A value of `0` is held by a figure `0` or by a standalone dash.
   Parentheses and the field's sign rule do not matter, because the magnitude is compared.
3. **Normalised text.** Remove every figure, then casefold, then replace each run of
   characters that is neither a letter nor a digit with one space, then strip. Apply
   this to the label and to the page text alike. So `stockholders’ equity` and
   `stockholders' equity` are the same, and a label that prints a year (`Senior notes
   due 2030`) is compared without it on both sides.
4. **The line is found** when some text line L of the page holds the value, and the
   normalised label is not empty and is a substring of the normalised text of one of
   these: L alone; the line above L, a space, then L; L, a space, then the line below L.
   The two joined forms allow a label that wraps onto a second text line.

Then, per printed line:

- **Found:** nothing to report.
- **Not found:** a failed check.
- **The page is beyond the PDF's last page:** a failed check that says so, naming the
  page count.
- **The page has no text layer** (`extract_text()` gives `None` or only whitespace): a
  failed check that says the line cannot be confirmed, because that page has no text
  layer. **Never a pass.** A line that was not looked at must not read as confirmed
  (rule 3).
- **The PDF cannot be opened by `pdfplumber`:** stop, with a `ValueError` naming the PDF.
  Do not catch a broad exception to do it (backlog item 8); catch the exception type
  `pdfplumber` actually raises, and name it in your entry.

Every printed line is checked: every line field of every `historical_years` entry and
of `latest_balance_sheet`, including the five check rows and the two noncontrolling
interest memo fields. Read each cited page's text once per filing, not once per line.

## What to do

1. **`ingestion/claude_extractor.py`.** Add, next to `_validate_extracted_data`:
   - `printed_line_on_page`, the pure rule above. Public, typed, no I/O.
   - one private function that reads the text of the cited pages from `pdf_bytes`
     (`pdfplumber.open(io.BytesIO(pdf_bytes))`, imported inside the function as
     `session_extraction.py` does). Keep it separate from the rule, so a test can give
     page texts without a PDF.
   - one private function that walks a Pass 1 answer (the parsed JSON object, after
     `pass1_problems` has passed) and returns a `list[_CheckFailure]`, one per line not
     found. `message` names where (`year 2026` or `balance sheet 2026`), the field, the
     line index, the label, the value and the page, and why (not found, page beyond the
     PDF, no text layer). `retry_message` names where, the field, the line index, the
     label and the page, and asks for the row to be read again with its page. **It states
     no value and no amount**, for the reason `_CheckFailure`'s docstring gives.
   - one public wrapper for route B, beside `parse_pass1`, taking the Pass 1 JSON string
     and `pdf_bytes`, returning the `message` of each failure. One definition of the walk
     serves both routes.
2. **Route A, `_run_financials_pass`.** After `_parse_financials_response` returns, add
   the page failures to its check failures. They then go through the existing retry and
   the existing final print, unchanged. Reword the check-retry prompt's opening so it is
   true for both kinds of failure: Python added the printed lines and compared the sums
   with the printed totals, **and looked for each line on the page it cites**. Keep every
   sentence that forbids changing a value to make a check pass.
3. **Route B, `ingestion/session_extraction.py`.** In `load_session_extraction`, after
   `parse_pass1`, add the page failures for that filing to `validation_errors`, with the
   same `where` prefix. Read the PDF bytes from `plan.pdf_path`, which the loader has
   already checked against its sha256. `check` keeps its exit codes: 1 when the only
   problems are failed checks. Its "Clean" sentence must also say that every printed
   line was found on its page.
4. **Docs.** `docs/2-rules/llm-boundary.md`, "The checks": the page check, and that the
   "no check could tell" sentence about an invented row is now answered by it, within the
   limits below. `docs/3-architecture/extraction.md`: the rule, where each route runs it,
   its cost (measure it on Walmart), the PDF that cannot be opened, the route A retry,
   and the two limits below. Change no other section.

## The limits of this check — write them into the docs, do not fix them

- **It confirms a row is printed with that figure, not that the figure is in the right
  year's column.** Walmart's `Prepaid expenses and other` with value `4,011` (the prior
  year) on page 22 is found. A column check needs word positions, not text lines.
- **It does not detect a real row listed under two fields.** The prompt forbids it;
  nothing checks it.

## Files in scope

- `ingestion/claude_extractor.py`
- `ingestion/session_extraction.py`
- `docs/2-rules/llm-boundary.md`
- `docs/3-architecture/extraction.md`
- your journal entry

**Nothing else.** Work outside this list is a review finding, even if the change is
good.

## Out of scope

- `tests/`. **Every test that runs the session loader or route A's runner on stand-in
  PDF bytes will now stop**, because `pdfplumber` cannot open `%PDF-1.4 stand-in …`.
  That is expected. List each failing test by name and reason in your entry. A tester
  rewrites the fixtures after review: `tests/unit/_text_pdf.py:write_text_pdf` already
  writes a real PDF with chosen text lines. Prove each criterion with scratch scripts
  under the scratchpad or `/tmp/`, never under `tests/`.
- `cli.py`, `api/`, `templates/`, `models/`. Route B's failed checks already print in
  the CLI (`cli.py:946`). **No failed reading check reaches the web page today**, for
  either route; that is new backlog item 62, owned by a later unit.
- `.claude/skills/extract-filing/SKILL.md`. The orchestrator updates it after review.
- `extractions/WMT.json`. Read it; never write it.
- Pass 2. Its items cite notes, and this unit checks Pass 1 lines only.
- The CLI pickle cache marker. A cache hit skips extraction and so skips this check,
  exactly as it skips the arithmetic check today. Do not change `CACHE_FORMAT`.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | one rule, one walk, both routes call the walk | 1 definition each; route A and route B each call it once | `grep -n "def printed_line_on_page" ingestion/`, and a grep for the walk and its two call sites |
| 2 | Walmart's real file is clean | exit 0; 89 lines checked, 89 found | `.venv/bin/python -m ingestion.session_extraction check extractions/WMT.json`, and a scratch count |
| 3 | an invented row that balances is caught | exit 1; the failure names `other_current_assets`, line 0, `Other current assets`, page 22; the balance check stays `OK` | a scratch copy of `WMT.json` with `Prepaid expenses and other` relabelled `Other current assets`, value 4124, page 22 |
| 4 | a wrong page is caught | exit 1; the failure names page 23 | the scratch copy with the real label and page 23 |
| 5 | a page beyond the PDF is caught | exit 1; the failure names page 87 and the 86 pages | the scratch copy with page 87 |
| 6 | the rule, by hand | each of these returns what is written: `("Total assets", 284668, "Total assets $ 284,668 $ 260,823")` True; `("Capex", 26642, "Payments for property and equipment (26,642)")` False; `("Payments for business acquisitions, net of cash acquired", 53, "Payments for business acquisitions, net of cash (53) (12)\nacquired")` True; `("Other", 0, "Other —")` True; `("Total stockholders' equity", 105887, "Total stockholders’ equity 105,887")` True; `("Total assets", 284668, "Total assets $ 260,823")` False | a scratch script calling `printed_line_on_page` |
| 7 | route A's retry names the row, never an amount | the retry text names the label, field and page; none of `4,124`, `4124`, `284,668`, `284668` appears outside the JSON | the criterion 3 JSON through `_run_financials_pass` with `_call_llm` stubbed and the real Walmart 2026 PDF bytes |
| 8 | route A keeps the figures after its last retry | the failure printed under `[Pass 1 FAIL]`; the statements returned | the same stubbed run, with the stub returning the same JSON every time |
| 9 | a PDF `pdfplumber` cannot open stops | `ValueError` naming the PDF; no broad `except` added | stand-in bytes through the route B wrapper |
| 10 | the gates do not regress | ruff 5, all `BLE001`; mypy ≤ 10, no new error; census 67 | the three gate commands |
| 11 | the red list | every failing test, by name and reason; each reason is the stand-in PDF or a message this unit reworded | the test gate before and after |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md` — rule 1 (the model reads), rule 3 (a line not looked at is
  never confirmed), rule 4 (each figure walks back to a page; this check is the first
  code that tests the walk).
- `docs/2-rules/llm-boundary.md`, "The checks" — the retry states no amount, and why.
- `docs/3-architecture/extraction.md`, "Validation" and "The loader" — where the checks
  run in each route today.
- `.agent/journal/2026-10-03T1046-code_reviewer-p11a-printed-lines.md`, F7 — the attack
  this unit defends against.
- `10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf`, page 22 — the balance
  sheet rows of criteria 3 to 5.

## Known open items

- The web page shows no failed reading check, for either route. New backlog item 62.
  Not this unit.
- `_print_pass1_tables` (route B, after a stop) prints the arithmetic failures only. Do
  not add the page check there: after a stop the PDF may be the reason.

## Backlog items this unit is NOT fixing

Items 1 (outside the new code, which must add no census hit), 8, 10, 11, 44, 46, 50,
51, 53, 57, 58, 60, 61, 62.
