---
agent: programmer
assignment: P12a-printed-pages
round: 2
status: complete
files_touched: [ingestion/claude_extractor.py, ingestion/session_extraction.py, docs/2-rules/llm-boundary.md, docs/3-architecture/extraction.md, .agent/journal/2026-10-03T1549-programmer-p12a-printed-pages-r2.md]
---

# P12a-printed-pages, round 2: a joined form no longer borrows a neighbour's figure, and route B names the filing

This round builds on the round 1 tree. That tree is uncommitted, on top of `0839ad9`
(`git log --oneline -1`). Run on 2026-10-03, macOS, `.venv/bin/python`. Nothing is committed.

This entry answers the review
`.agent/journal/2026-10-03T1547-code_reviewer-p12a-printed-pages.md` and the
assignment's "Round 2" section. The round 1 entry,
`.agent/journal/2026-10-03T1534-programmer-p12a-printed-pages.md`, is unchanged.

## Findings, by number

| # | Finding | Answer |
|---|---|---|
| F1 | a joined form lets a label take the figure of the row above or below | **Fixed, as the orchestrator decided.** In `printed_line_on_page`, the line above joined to L becomes a candidate only when the normalised label is **not** a substring of the normalised line above on its own. The line below follows the same condition. L alone is unchanged. The docstring states the new condition, and so do both docs. Criterion 6b below measures it |
| F2 | route B's stop names the unopenable PDF by sha256 only | **Fixed.** `load_session_extraction` wraps the `printed_line_page_failures` call: `except ValueError as exc: raise ValueError(f"{where}: {exc}") from exc`. `check` now prints `STOPPED — <session file>: filings[0] (r2_standin.pdf): the PDF sha256 af72424bc7b54768… (27 bytes) cannot be opened by pdfplumber …`. Route A's wording is unchanged, because route A holds only the bytes. `_filing_problems` has already passed the Pass 1 shape, so the only `ValueError` that can reach this handler is the PDF's. A comment at the call site says so |
| F3 | whole-word or exact matching | **Not adopted, per the orchestrator.** The substring rule stays, changed only by F1. The docs now state the short-label looseness as a limit, in one sentence: "A short label can be found inside a longer printed label, with that row's own figure". `extraction.md` gives the measured example: `Debt` with `34,624` returns True on Walmart page 22, whose row reads `Long-term debt 34,624 33,401` |
| F4 | the red-on-purpose test fails in its setup | **Not mine (tester).** Re-measured: `test_routes_session_rule3_red.py` still fails at `:63` (setup) and `test_projector_rule3_red.py` at `:98`. Both are as in round 1 |
| F5 | a filing with no text layer spends route A's retries | **Not mine (orchestrator's backlog).** No code change |

## Done-criteria, re-run on the final tree

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 2 | Walmart's real file is clean | **pass** | `.venv/bin/python -m ingestion.session_extraction check extractions/WMT.json` exits 0 and prints `Printed lines looked up on their cited pages: 89 checked, 89 found, 0 not confirmed.` plus the Clean sentence. Wall time 0.63 s |
| 3 | an invented row that balances is caught | **pass** | Scratch `r2_c3.json` (`r2_make.py`, a copy of WMT.json with `other_current_assets` = `[{"Other current assets", 4124, 22}]`). `check` exits 1: `balance sheet 2026, 'other_current_assets' line 0: 'Other current assets' = 4,124 was not found on page 22`. `Total Assets` and `Total L + E` both read `284,668 284,668 +0 OK` |
| 4 | a wrong page is caught | **pass** | `r2_c4.json` keeps the real label and cites page 23. `check` exits 1: `… 'Prepaid expenses and other' = 4,124 was not found on page 23` |
| 5 | a page beyond the PDF is caught | **pass** | `r2_c5.json` cites page 87. `check` exits 1: `… cites page 87, but the PDF has 86 pages.` |
| 6 | the rule, by hand | **pass, 6 of 6** | Scratch `r2_c6.py` returns True, False, True, True, True, False, as written. The wrapped label (`Payments for business acquisitions, net of cash acquired`) is still True |
| 6b | a neighbour's figure is refused, on real Walmart page 22 | **pass, 3 of 3** | `r2_c6.py` reads page 22 with `pdfplumber`. `('Prepaid expenses and other', 84874)` returns False, `('Prepaid expenses and other', 58851)` returns False, and `('Inventories', 4124)` returns False. The review measured all three True before this change. Controls on the same page, each a real row with its own figure, stay True: `('Prepaid expenses and other', 4124)`, `('Inventories', 58851)` and `('Total current assets', 84874)`. Walmart is still 89 of 89 (criterion 2), and criteria 3 to 5 still hold |
| 9 | a PDF `pdfplumber` cannot open stops | **pass** | Scratch `r2_c9.py`. The stand-in bytes `b"%PDF-1.4 stand-in for r2 c9"` go through the wrapper and raise `ValueError: the PDF sha256 af72424bc7b54768… (27 bytes) cannot be opened by pdfplumber (PdfminerException: No /Root object! …)`, with cause `pdfplumber.utils.exceptions.PdfminerException`. A session file whose sha matches those bytes goes through `load_session_extraction` and raises `ValueError: <path>/r2_c9.json: filings[0] (r2_standin.pdf): the PDF sha256 …`. Its cause is that `ValueError`, whose own cause is `PdfminerException`. `check` exits 2. `git diff -U0 ingestion \| grep "^+.*except"` lists only the round 1 `except (PdfminerException, MalformedPDFException)` and this round's `except ValueError`. Neither is broad, and ruff `BLE001` stays at 5 |
| 10 | the gates do not regress | **pass** | ruff `Found 5 errors.`, all `BLE001`. mypy (the exact harness command): `Found 10 errors in 4 files`. With line numbers stripped, the 10 error lines are identical to the `0839ad9` baseline. Census (`rules.md:65`, `'--include=*.py'` quoted): **67** |
| 11 | the red list | **pass** | Gate form `-q --ignore-glob="*_rule3_red.py" -p no:cacheprovider` gives **24 failed, 602 passed**. Compared by name, the set equals round 1's 24 and the reviewer's (`diff` empty). `cannot be opened by pdfplumber` appears 31 times in the output. Control run: the walk replaced by `lambda data, pdf_bytes: []` through the scratch plugin `no_page_check.py` gives **626 passed**. So every red test is the stand-in PDF, and neither F2's new `where` prefix nor any rewording breaks a test |

As a spot check outside the list, I also re-ran criteria 7 and 8 (scratch `c7_c8.py`,
with the real Walmart bytes and `_call_llm` stubbed). The retry names `'Other current
assets'`, `other_current_assets` and `page 22`. None of `4,124`, `4124`, `284,668` or
`284668` appears outside the JSON. `[Pass 1 FAIL]` is printed, and the statements are
returned with `other_current_assets` = 4124.0.

## Decisions, each with its reason

| Decision | Reason | Why this and not the alternative |
|---|---|---|
| The neighbour test uses the neighbour line alone, normalised by the same `_normalised_text` | Round 2 decision 1: "not wholly inside the normalised text of the neighbouring line alone" | Testing against the joined text instead would refuse every wrap |
| The F2 handler catches `ValueError`, not a new exception class | Decision 3 says re-raise "the `ValueError`". The other subclasses the wrapper can raise (`Pass1ShapeError`, `JSONDecodeError`) cannot occur here, because `_filing_problems` has already passed the shape and the JSON is `json.dumps` output | A new class would add surface the assignment did not ask for. If one of those subclasses ever did occur, the `where` prefix would be correct for it too |
| `extraction.md` "Two limits" becomes "Three limits" | Decision 4: keep the short-label looseness as a limit, in one sentence | — |
| The docs' sentence "it confirms a row is printed with that figure" is kept | Decision 1 says remove it only where it is still false. After the change, a match needs the figure on L itself, and a label printed whole on a neighbour no longer counts. The column limit already qualifies the sentence | See finding 1 below for the one residual case |

No code was changed to reach a target number.

## Rule 3

The round adds no default and no fallback. The F2 handler re-raises, so it never swallows
the error. The census stays at 67, and no `.get(`, `or` default or `else 0` was added.

## Findings for the orchestrator

1. **A label made up of the end of one row and the start of the next is still found.**
   Measured on page 22: `printed_line_on_page('other Total current assets', 84874, p22)`
   returns True. No neighbour holds that label whole, so the joined form counts, by the
   new rule's own wording. The figure is still L's own (`Total current assets 84,874`), so
   the attack in F1, a real label taking a neighbour's figure, is closed. Only a label
   that a model wrote across two printed rows gets through. I did not add this to the docs,
   because decision 4 limits the docs to the one short-label sentence.

## What I did not do

- I did not touch `tests/`, `STATUS.md`, `.agent/journal/INDEX.md`, the round 1 entry or
  any file outside scope. `git status --short` shows only the four in-scope files modified,
  plus this entry.
- I did not change route A's unopenable-PDF wording (decision 3).

Scratch files are under
`/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/abfaba0a-dbfc-4078-8cbf-99abdeae9e3b/scratchpad/`:
`r2_c6.py`, `r2_make.py`, `r2_c3.json`, `r2_c4.json`, `r2_c5.json`, `r2_c9.py`,
`r2_c9.json`, `r2_after.txt`, `r2_after_set.txt`, `mypy_r2.txt` and `no_page_check.py`.
