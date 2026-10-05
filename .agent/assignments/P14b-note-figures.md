---
id: P14b-note-figures
phase: 14 — the Pass 1 role (rule 1 option B, the user's decision of 2026-10-03; check B1, the user's decision of 2026-10-04)
agent: programmer
depends_on: [P15a-two-routes]
---

# Pass 1 may take a printed figure from a note or MD&A; Python checks that each printed row sits under a unit statement of the filing's scale (B1)

## Objective

Python converts every Pass 1 row with one scale per kind: the money scale read from
`units`, and the share scale read from `share_units` (`convert_filing_to_millions`).
That is right only when each row is printed in that scale. Nothing checks it. The Pass 1
prompt already sends `interest_expense` to the notes ("Go to footnotes for the
breakout"), and rule 1 option B allows any field to come from a note or MD&A when the
statement does not print that line by itself. A note can print in another scale. Then
the row is converted with the wrong scale, off by a factor of 1,000, and nothing
downstream can detect it.

When this unit is done:

- the prompt allows a figure from a note or MD&A, as one printed line with its page,
  copied in the unit printed there (option B);
- Python checks every Pass 1 printed row: the row's page, or the page before it, must
  print a unit statement that states the filing's scale for that row's kind. If not,
  the run stops, as a unit statement not found stops (the user's choice B1 of
  2026-10-04). The model returns no new field.

## What is already true — verify, do not redo

Measured by the overall lead at `525b98f` (`P15a-two-routes`, accepted), macOS: gate
1032 passed with and without the empty-key prefix; full 2 failed (the known two); ruff 4;
mypy 8 in 3 files; census 65; guard 48/48. `tests/conftest.py` empties both API keys
for every test. After `P15a`, route A is Gemini: the stub in criterion 7 replaces `_call_llm`, so it
does not depend on the provider.

| Fact | Command | Result |
|---|---|---|
| Walmart, route B | `.venv/bin/python -m ingestion.session_extraction check extractions/WMT.json` | exit 0; `session-extraction-v4`; its Pass 1 rows cite PDF pages 21, 22, 23 and 27 |
| Walmart, end to end | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json` | implied price $28.02 |

The overall lead read the parenthesised unit statements of these pages with
`printed_scale` (whitespace normalised; groups holding `thousands`, `millions` or
`billions`):

| Filing | PDF page | Statements on the page, and the scale read |
|---|---|---|
| Walmart 10-K 2026-01-31 | 1 and 2 | none |
| Walmart 10-K 2026-01-31 | 21 | `(Amounts in millions, except per share data)`: money millions, shares millions |
| Chipotle 10-K 2025-12-31 | 28 and 29 | `(in thousands, except per share data)`: money thousands, shares thousands |
| Okta 10-K 2026-01-31 | 57 and 58 | `(dollars in millions, shares in thousands, except per share data)`: money millions, shares thousands |
| L3Harris 10-K 2026-01-02 | 62 | `(In millions)` and `(In thousands)`: two scales on one page |

A scan of the statement title pages of all 16 filings, and the page after each, found a
readable money scale on the page or the page before for every income statement page.
Some note pages print no statement, and some print two scales.

## What to do

1. **The prompt** (`_FINANCIALS_SYSTEM_PROMPT`). Add one rule under EXTRACTION RULES:
   when the statement does not print a field's row by itself, the figure may be taken
   from a note or from MD&A, as one printed line, with its label and its page as printed
   there, copied in the unit printed there and never converted. Keep the
   `interest_expense` line. **Reason:** rule 1 option B.
2. **The check** (`ingestion/claude_extractor.py`). Add `_row_scale_failures(data:
   dict[str, Any], pdf_bytes: bytes) -> list[_CheckFailure]`, beside
   `_unit_statement_failures`. For each printed row of every line field, in every year
   of `historical_years` and in `latest_balance_sheet` (when it is not `{}`):
   - the kind is `"share count"` for `diluted_shares`, and `"money figures"` for every
     other field;
   - the expected scale is the word `_filing_units(data)` reads for that kind;
   - the candidates are the parenthesised groups (`_PARENTHESISED_GROUP`, on the
     whitespace-normalised text) of the row's page and of the page before it, that
     hold `thousands`, `millions` or `billions`; each is read with `printed_scale(group,
     kind)`, and a group whose reading stops is not a candidate for that kind;
   - the row passes when one candidate's word equals the expected word;
   - a page beyond the PDF, or with no text layer, is not confirmed.
   Write **one failure per page and kind**, not one per row. It names the page, the
   kind, the expected scale, the statements found (or "no unit statement on page N or
   N - 1"), and each row that cites the page (field, year, label). Print one summary
   line, in the form of the other checks: rows checked, pages, pages not confirmed.
   **Reason:** a wrong scale moves a figure by a factor of 1,000 (P14a), and B1 is the
   user's choice of check.
3. **Every failure stops, as a unit statement failure does.**
   - Route A (`_run_financials_pass`): add these failures to `unit_failures`, so they
     go into the retry like the others and, after the last retry, raise with the unit
     statement failures.
   - Route B: `unit_statement_page_failures` returns them too, so the loader stops on
     them and `check` exits 2. Its docstring says so.
4. **Docs.** `docs/3-architecture/extraction.md`: option B in the Pass 1 rules; the
   check, with its rule, its stop, and its limit; `docs/2-rules/llm-boundary.md`: option
   B is in force, and how its unit is checked. **State the limit in words:** a page that
   prints statements of two scales (L3Harris 10-K 2026-01-02, page 62) passes a row of
   either scale. A figure printed in MD&A prose ("$1.2 billion") has no parenthesised
   statement, so a row that cites it stops.

## Files in scope

- `ingestion/claude_extractor.py`
- `docs/3-architecture/extraction.md`
- `docs/2-rules/llm-boundary.md`
- your journal entry, `.agent/journal/<timestamp>-programmer-p14b-note-figures.md`

**Nothing else.** The two docs files are in scope by the overall lead's decision.

## Out of scope

- `tests/`: the tester, in `P14b-note-figures-tests`.
- `ingestion/session_extraction.py`: it reaches the check through
  `unit_statement_page_failures`, with no change.
- The session file format: unchanged (`session-extraction-v4`). The model returns no
  new field.
- The `extract-filing` skill: the overall lead updates it after acceptance.
- A row in MD&A prose. B1 cannot confirm it; that is the stated limit.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. **Make no paid API call.**

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the prompt allows option B | the new rule present; no prompt sentence asks the model to convert | `grep -n` for the rule and for "convert" in the prompt, each hit explained |
| 2 | Walmart is clean | `check` exits 0; the summary line shows every row checked and 0 pages not confirmed | `session_extraction check extractions/WMT.json` |
| 3 | a row on a page with no unit statement stops | a copy of the Walmart file with one revenue row's `page` set to 2: `check` exits 2, naming page 2, `money figures`, "no unit statement on page 2 or 1", and that row | `session_extraction check <copy>` |
| 4 | a row under another scale stops | the real Chipotle 2025 PDF, a Pass 1 answer whose `units` statement reads millions and one `revenue` row on page 29 → one failure naming page 29, expected `millions`, found `(in thousands, except per share data)` | a scratch call of `_row_scale_failures` |
| 5 | two scales, read by kind | the real Okta 2026 PDF, `units` millions and `share_units` thousands, a `revenue` row and a `diluted_shares` row on page 58 → 0 failures; the same with `share_units` millions → one failure for the share count | the same scratch call |
| 6 | the stated limit holds as stated | the real L3Harris 2026-01-02 PDF, a money row on page 62, `units` millions → 0 failures; the same with `units` thousands → 0 failures | the same scratch call |
| 7 | route A stops after its retries | a stubbed `_call_llm` that returns the Walmart Pass 1 answer with one row on page 2, on the real Walmart PDF → `ValueError` after the retries, listing the page 2 failure; 0 network calls | a scratch script, sockets blocked |
| 8 | Walmart does not move | stages 1 to 10 identical to the run at the `P15a-two-routes` commit, except the new summary line; $28.02 | `cli.py --session-file extractions/WMT.json`, diffed |
| 9 | the gates do not get worse | ruff, mypy and census no higher than at the `P15a-two-routes` commit; `GET /` 200 | the gate commands |
| 10 | the false-stop risk is measured | for each of the 16 filings: the income statement, balance sheet and cash flow title pages (`locate`'s "title line" rule) and the page after each, with the money scale found on the page or the page before. List every such page that has none, with its first text line | a scratch script; the table goes in your entry |
| 11 | every red test is named | expected causes only: fixtures whose printed rows cite a page with no unit statement on it or the page before, and the 2 red on purpose | the full suite, failures grouped by cause |

## Citations

- `docs/2-rules/rules.md`, rule 1 option B, and P14a's rule that a unit not confirmed stops.
- `docs/3-architecture/extraction.md`, "The printed unit statements, and the conversion
  to millions": `printed_scale`, `_PARENTHESISED_GROUP`, the unit checks.
- The PDF pages in the table above.

## Known open items

- If criterion 10 lists a statement page with no scale, B1 stops a real filing. Report
  it in the handoff; the overall lead decides before acceptance.
- A Pass 1 row from MD&A prose cannot pass B1.

## Backlog items this unit is NOT fixing

Items 1, 10, 51, 53, 61, 63, 64, 73, 74, 78, 79, 80 in `claude_extractor.py`.
