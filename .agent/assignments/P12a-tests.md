---
id: P12a-tests
phase: 12 — every printed line is found on the page it cites
agent: tester
depends_on: [P12a-printed-pages]
---

# Give the 24 fixtures real PDFs, and lock what the page check decides

## Objective

`P12a-printed-pages` (`a64818b`) makes both routes open the filing's PDF with
`pdfplumber` and look for each Pass 1 printed line on the page it cites. **24 tests in
the gate now fail.** Each one runs the session loader or route A's runner on stand-in PDF
bytes (`%PDF-1.4 stand-in …`), which `pdfplumber` cannot open, so the run stops. Both
reviews proved it: with the page check stubbed out, 626 of 626 pass. The programmer's
round 1 entry names the 24.

**One test that is red on purpose now fails for the wrong reason.**
`test_routes_session_rule3_red.py` fails in its setup at `:63` (the stand-in PDF), not
on backlog item 52's defect at `:74`. Until it is repaired, it guards nothing.

Read the assignment (both rounds), both programmer entries and both review entries
first:

- `.agent/assignments/P12a-printed-pages.md`
- `.agent/journal/2026-10-03T1534-programmer-p12a-printed-pages.md`
- `.agent/journal/2026-10-03T1547-code_reviewer-p12a-printed-pages.md`
- `.agent/journal/2026-10-03T1549-programmer-p12a-printed-pages-r2.md`
- `.agent/journal/2026-10-03T1557-code_reviewer-p12a-printed-pages-r2.md`

## What to do

1. **Repair the 24, and the red-on-purpose test.** Give each fixture a real PDF that
   prints every row its Pass 1 JSON cites, on the cited page, with
   `tests/unit/_text_pdf.py:write_text_pdf`. Write one helper that builds the pages from
   the fixture's own printed lines, so each fixture and its PDF cannot drift apart.
   **No assertion about a figure may change.** Session files record the PDF's sha256, so
   write the PDF before the session file. A test that must reach the defect it records
   (`test_routes_session_rule3_red.py`) must fail at its own assertion again, not in
   setup.

   **Do not stub the page check to make a fixture pass.** A stub is allowed only in a test
   whose subject is something else, and only if a separate test runs the real check on the
   same path. Name every stub in your entry, with the reason.
2. **The rule, `printed_line_on_page`, by hand.** It is pure, so derive each case from
   the rule as `docs/3-architecture/extraction.md`, "The page check", states it, before
   you run the code. Cover at least these:
   - the label and the figure on one line; parentheses, `$` and thousands commas;
   - a curly apostrophe against a straight one;
   - a label printing a year (`Senior notes due 2030`), compared without the year;
   - a value of 0 against a standalone dash, and against no dash;
   - a figure that only matches with a sign or in another magnitude (`26,642` against
     `2,664.2`): not found;
   - **a wrapped label**, split over two text lines, with the figures on either half:
     found;
   - **F1**: a label printed whole on the row above or below, with that row's figure
     taken by the neighbour: not found;
   - an empty normalised label (a label made only of figures): not found.
3. **The walk, with real PDFs you write.** For each outcome in the table in
   `extraction.md`, show that it happens: found; not found; a page beyond the last page
   (the message names both page numbers); a page with no text layer (a failed check that
   says "cannot be confirmed", **never** a pass); a PDF `pdfplumber` cannot open (route A:
   a `ValueError` naming the sha256; route B: the loader's message names the filing, and
   `check` exits 2). Every line field is walked, including the five check rows and the
   two noncontrolling interest memos. Each cited page is read once.
4. **Route B.** `check` exits 0 on a fixture whose every row is printed, and its "Clean"
   line says so. It exits 1 when the only problem is a line not found, and the message
   names where, the field, the line index, the label, the value and the page.
5. **Route A**, with `_call_llm` stubbed and a PDF you wrote: a line not found goes to the
   check retry; **the retry text names the label, the field and the page, and holds no
   value and no amount**; after the last retry the failure prints under `[Pass 1 FAIL]`
   and the statements are returned.
6. **The F7 attack, end to end.** A Pass 1 answer whose balance sheet balances because
   one row was invented (a label the PDF does not print, a value equal to the row it
   replaced): the balance check passes, and the page check fails naming that row. This
   is the case the unit exists for.

Never read `10K_filings/` or `extractions/`. Write every PDF under `tmp_path`. No test
may reach the API or the network.

## Files in scope

- any file under `tests/unit/`
- your journal entry

**Nothing else.** If a test can only pass by changing `ingestion/`, stop and report it.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the gate | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | the full suite | exactly 2 failures: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`, the second at its own assertion, not in setup | the failure list and tracebacks from `.venv/bin/python -m pytest -q` |
| 3 | no assertion weakened | none removed or loosened in the 24 | `git diff` per file, summarised in your entry |
| 4 | no fixture passes by a stub | every stub of the page check named, each with a reason and a sibling test that runs the real check | your entry |
| 5 | the new tests can fail | in a copy of `ingestion/claude_extractor.py` under `/tmp/` or the scratchpad, break: the joined-line F1 condition; the no-text-layer outcome (make it pass); the page-count check; the retry wording (add the value); the walk (skip the balance sheet) — and show each turns tests red | paste it in your entry |
| 6 | lint | 5 errors, none in your files | `.venv/bin/python -m ruff check .` |
| 7 | the census and the guard | 67; 48/48 | the grep at `docs/2-rules/rules.md:65`; `.venv/bin/python .claude/check_guard.py` |

**Every criterion is a measurement, never an opinion.**

## Known open items

- Backlog items 62, 63 and 64, new at `P12a`. Do not write tests that lock them in as
  expected behaviour. Write no test for item 64's case (a label written across two
  rows): its fix is not decided, so there is no expected value to assert.
- Item 52 is what `test_routes_session_rule3_red.py` records. Keep it red for that reason.

## Backlog items this unit is NOT fixing

All of them. A tester writes tests; it does not edit `ingestion/`.
