---
id: P10c-fiscal-year
phase: 10 — the user's fixes of 2026-10-02 (items 43, 45, 48)
agent: programmer
depends_on: []
---

# Take the fiscal year from the filename, and verify it against the filing

## Objective

The fiscal year comes from the filename (`ingestion/filings.py:discover_filings`, and
`api/routes_upload.py:_guess_fiscal_year` for the web). Backlog item 43. **The user
decided on 2026-10-02: keep the filename as the source, and verify it against the
content of the file.** A mismatch must stop and name both.

The orchestrator scanned all 16 filings under `10K_filings/` on 2026-10-02 with
`pdfplumber`. For each, the cover page's "For the fiscal year ended …" date, and the year
labels printed above the income statement's columns:

| Filing | Year from filename | Cover: fiscal year ended | Column labels above the income statement |
|---|---|---|---|
| AbbVie, Chipotle (3 each) | 2023, 2024, 2025 | December 31 of that year | bare years, newest first, newest = filename year |
| Okta, Walmart (3 and 4) | 2023 – 2026 | January 31 of that year | bare years, newest = filename year |
| L3Harris `…_2023-12-29_…` | 2023 | December 29, 2023 | **dates**: `December 29, 2023 December 30, 2022 December 31, 2021` |
| L3Harris `…_2025-01-03_…` | **2025** | January 3, 2025 | **dates**: `January 3, 2025 December 29, 2023 December 30, 2022` |
| L3Harris `…_2026-01-02_…` | **2026** | January 2, 2026 | **bare years: `2025 2024 2023`** |

So the filename date always equals the cover date. The year label does not: L3Harris
ends its 52/53-week year on the Friday nearest December 31, and calls the year that ends
on January 2, 2026 **fiscal 2025**. Its later filing labels the year ended January 3,
2025 **2024**. So the plan asks the 2025-01-03 filing for "fiscal year 2025 ONLY", which
it does not hold under that name, and the merge files each L3Harris year one year late.

## What to do

1. **Separate reading from deciding.** In `ingestion/filings.py`:
   - one function reads the evidence from a PDF with `pdfplumber`: the cover date (the
     first "For the fiscal year ended <Month D, YYYY>" in the first pages), and the
     newest column label above the income statement, when the label is a bare year;
   - one pure function decides the content year from that evidence, so a test can drive
     it with strings and no PDF:
     - a bare-year column label wins;
     - with date labels only, the year of the cover date, **except** that a year ending
       in the first seven days of January belongs to the year before. That is the
       52/53-week convention, and on the table above it gives 2023, 2024 and 2025 for
       L3Harris, and the filename year for the other 13 filings;
     - when a bare-year label and the cover rule disagree, stop. Name both.
   - Rule 1 does not apply here: no model is involved. This reads printed text.
2. **Verify every filing that carries a year**, in `discover_filings` and in
   `parse_pdf_args`, including an explicit `YEAR:PATH`. On a mismatch, raise
   `ValueError` naming the file, the year given, the cover date, the column label, the
   year the content gives, and the remedy: pass `<content year>:<path>`, or rename the
   file. When the evidence cannot be read (no cover line, for example a 10-Q or a scanned
   PDF), stop and say so. A bare path with no year (year 0) is not verified, because it
   asks for every year in the filing.
3. **The web upload.** Make `_guess_fiscal_year`'s result go through the same
   verification. A mismatch re-renders the upload page with the message, and nothing is
   extracted. **Do not keep a second year guesser:** if `discover_filings`' pattern and
   `_guess_fiscal_year`'s pattern differ, use one, in `ingestion/filings.py`.
4. **Docs.** `docs/3-architecture/extraction.md` ("Multi-PDF year routing": where the
   year comes from now) and `docs/3-architecture/entry-points.md` (the upload stop).

## Files in scope

- `ingestion/filings.py`
- `api/routes_upload.py`
- `templates/upload.html`, only to show the message
- `docs/3-architecture/extraction.md`, `docs/3-architecture/entry-points.md`
- your journal entry

`P10a` (the equity bridge) and `P10b` (`analysis/capm.py`) run in parallel. Neither
touches these files.

## Out of scope

- `ingestion/claude_extractor.py` and the prompts. A filing whose columns carry dates
  is still asked for "fiscal year 2024" with no date beside it. Record that as a finding;
  do not change the prompt.
- `tests/`. Prove each criterion with scratch scripts under `/tmp/`.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the 13 filings whose labels agree pass | no error | `discover_filings` on `10K_filings/AbbVie`, `Chipotle`, `Okta`, `Walmart` |
| 2 | L3Harris stops | `ValueError` naming `…_2025-01-03_…`, given 2025, content 2024, and the remedy | `discover_filings` on `10K_filings/LHX` |
| 3 | the remedy works | three filings planned as 2023, 2024, 2025 | `parse_pdf_args` with the three `YEAR:PATH` entries |
| 4 | the decision rule, without a PDF | each row of the table above | the pure function, on strings |
| 5 | the web upload stops on the same input | the upload page shows the message; no redirect to `/assumptions` | `TestClient` posting the L3Harris 2026 PDF |
| 6 | route B's `plan` uses the same check | `session_extraction plan 10K_filings/LHX -t LHX -o /tmp/x.json` stops with the same message | the command |
| 7 | no regression | the gate as before, apart from `P10a`'s named red tests | the test gate |
| 8 | lint and types | no new error | the two gates |

## Backlog items this unit is NOT fixing

- **Item 49**, the silent drop of a filing with no year in the API route. **Item 44**,
  units.
