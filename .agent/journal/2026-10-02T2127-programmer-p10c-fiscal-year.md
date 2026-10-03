---
agent: programmer
assignment: P10c-fiscal-year
round: 1
status: complete
files_touched: [ingestion/filings.py, api/routes_upload.py, templates/upload.html, docs/3-architecture/extraction.md, docs/3-architecture/entry-points.md]
---

# P10c-fiscal-year — verify the filename's fiscal year against the filing's cover and column labels

## What I did

The filename still names the fiscal year, and every year so named is now verified
against the filing before anything is extracted (backlog item 43, the user's decision of
2026-10-02). In `ingestion/filings.py`: `fiscal_year_from_filename` is the one filename
guesser (the web's `_guess_fiscal_year` now delegates to it, so the old `(20\d{2})`
pattern is gone); `read_fiscal_year_evidence` reads, with `pdfplumber`, the cover's "For
the fiscal year ended <Month D, YYYY>" (it must follow "ANNUAL REPORT PURSUANT TO SECTION
13 OR 15(d)" in the first 5 pages) and the newest column heading within 5 lines below an
income-statement title standing alone on its line; `fiscal_year_from_evidence(cover_date,
column_label)` is the pure decision on two strings; `verify_filing_years` compares and
raises one `ValueError` listing every mismatch or unreadable filing, each with the file,
the year given, the cover date and page, the label and page, the content year and the
remedy. `discover_filings` and `parse_pdf_args` (every `YEAR:PATH`) call it; year 0 (a
bare path) is skipped. `POST /upload` calls it and, on a stop, re-renders `upload.html`
with the message at HTTP 400 and no redirect. Docs: extraction.md gains "Where each
filing's fiscal year comes from" and the stale "still comes from the filename" section is
rewritten; entry-points.md describes the upload stop.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the 13 agreeing filings pass | pass | `PYTHONPATH=. .venv/bin/python /tmp/p10c_c1_c3.py` -> AbbVie [2023, 2024, 2025] 10.5s, Chipotle [2023, 2024, 2025] 6.5s, Okta [2024, 2025, 2026] 12.7s, Walmart [2023 … 2026] 14.9s, no error. Evidence for all 16 printed (cover p1; label page 21–65) |
| 2 | L3Harris stops | pass | same script: `ValueError` naming `'L3Harris Technologies Inc._10-K_2025-01-03_English.pdf' is given fiscal year 2025, but its content gives 2024: the cover says 'For the fiscal year ended January 3, 2025' (page 1) and the newest column … is labelled 'January 3, 2025' (page 41). Pass 2024:<path> instead, or rename the file so its name carries 2024.` It also names the 2026-01-02 filing (given 2026, content 2025, label '2025' p35) in the same message |
| 3 | the remedy works | pass | same script: `parse_pdf_args(["2023:…2023-12-29…", "2024:…2025-01-03…", "2025:…2026-01-02…"])` -> `[(2023, …), (2024, …), (2025, …)]`; `plan_filings` on it -> 2023 all years no B/S, 2024 `(2024,)`, 2025 `(2025,)` with B/S |
| 4 | the decision rule on strings | pass | `PYTHONPATH=. .venv/bin/python /tmp/p10c_c4.py` -> all 10 rows `ok` (L3Harris: ('December 29, 2023','December 29, 2023') 2023; ('January 3, 2025','January 3, 2025') 2024; ('January 2, 2026','2025') 2025; the other 13 = filename year). Stops: ('January 2, 2026','2026'), ('December 31, 2025','2024'), ('January 3, 2025','December 29, 2023'), 'not a date', 'FY2024', 'Smarch 3, 2025'. Boundary: Jan 7 -> prior year, Jan 8 -> same year |
| 5 | web upload stops | pass | `PYTHONPATH=. .venv/bin/python /tmp/p10c_c5.py` (UPLOAD_DIR rebound to /tmp) -> L3Harris 2026 PDF: `status 400 location None`, alert shows the same message naming given 2026, content 2025; the form is re-rendered. The 2023-12-29 PDF still gets `303 /assumptions?…files=2023:…`. `GET /` 200, no alert block |
| 6 | route B plan uses the same check | pass | `.venv/bin/python -m ingestion.session_extraction plan 10K_filings/LHX -t LHX -o /tmp/x.json` -> `ERROR: The fiscal year given does not match the filing; …` (both L3Harris lines), `exit=2`, `/tmp/x.json` not written. Control: `plan 10K_filings/Okta` writes 3 filings, exit 0 |
| 7 | no regression apart from P10a's red tests | **fail as worded — by the assignment's own step 2** | Clean comparison in `/tmp/p10c-base` (HEAD `54c966f` + this unit's three code files): `pytest -q --ignore-glob="*_rule3_red.py"` -> **392 passed, 6 failed**; baseline at HEAD 397 passed, 1 failed (`test_capm.py`, item 45). The 5 new failures: `test_filings.py::test_parse_pdf_args_reads_year_colon_path` (`2024:/x/a.pdf`, a file that does not exist), `test_routes.py::test_the_form_on_the_front_page_is_accepted_by_the_route_it_targets`, `::test_post_upload_saves_the_file_and_redirects_naming_it`, `::test_post_upload_journey_reaches_a_rendered_assumptions_page` (each uploads `goog-10k-2024.pdf` / `testco-10k-2024.pdf` holding `b"%PDF-1.4 not a real filing"`, now 400 instead of 303/200), `test_session_extraction.py::test_plan_writes_route_a_plan_and_refuses_to_overwrite` (`make_pdf` writes stand-in bytes named `TST_10-K_<year>.pdf`). Every one gives a year with a file whose evidence cannot be read, and step 2 says that case **stops**. No assertion in them can pass without dropping that stop. In the shared tree (with P10a's work in progress) the gate shows 36 failed: P10a's 31 at my start plus exactly these 5 |
| 8 | lint and types | pass | `/tmp/p10c-head` (HEAD) vs `/tmp/p10c-base` (HEAD + this unit): `ruff check .` 5 errors both; `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` "Found 10 errors in 4 files" both, identical lines (`api/routes_upload.py:28` is the pre-existing `file.filename` `/` error, backlog item 28). Rule 3 census 116 both |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The cover line must follow "ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d)" | Proved by execution: a 15-page subset of AbbVie 2024 with no cover matched "…Annual Report on Form 10-K for the fiscal year ended December 31, 2023" in its MD&A (subset page 4) and read the wrong cover date. All 16 real filings carry the marker before the cover line on page 1 (`/tmp/p10c_cov.py`) | A bare "for the fiscal year ended" search reads prose as a cover. With the marker, the subset stops ("no 10-K cover line") instead |
| A date column label must equal the cover date, or stop | The assignment's rule gives the cover rule's year for date labels; a newest column dated differently from the cover means the reader found the wrong table or the filing contradicts itself. All three L3Harris date labels equal their covers | Ignoring the date label would make it evidence that is read and never checked |
| Column headings need two or more years or dates, within 5 lines below a title alone on its line | Measured: headings are 1–3 lines below the title in all 16; TOC entries carry a page number or "— Fiscal Year Ended …" after the title, sentences carry more words | A looser match picks TOC and prose lines (seen in the first scan: L3Harris p20, p39, AbbVie p33) |
| A filing with a year whose evidence cannot be read stops (no cover, no headings, not a PDF, missing file) | Assignment step 2: "When the evidence cannot be read … stop and say so"; rule 3 | This is what turns the 5 tests in criterion 7 red. A pass-through for unreadable files would be the silent default rule 3 forbids |
| All problems in one `ValueError`, not the first | The LHX folder has two wrong years; one message lets the user fix both at once | Criterion 2's message still names `…_2025-01-03_…`, given 2025, content 2024 |
| Web stop answers HTTP 400 with the page | A rejected input; criterion 5 only needs "the page shows the message; no redirect". Other error pages here answer 200 | 400 makes the stop visible to a client or test without reading HTML |
| The 7-day January window is a named constant `_JANUARY_DAYS_OF_PRIOR_YEAR` and is printed in the disagreement message | Assignment step 1 states the rule; rule 6 spirit: the convention is visible where it decides | It reaches a year, not a displayed money figure |
| Uploaded files are left in `uploads/<TICKER>/` after a stop | Out of the unit's ask; deleting adds a failure mode | Noted below |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| cover date | stops: "no 10-K cover line (…) in its first 5 pages" | `/tmp/p10c_rule3.py`, subset of AbbVie 2024 pages 11–25 |
| newest income-statement column label | stops: "no column headings (two or more years or dates) found under a 'Consolidated Statement(s) of …' title" | same script, subset pages 1–5 |
| the PDF itself | stops: "could not be opened as a PDF (No /Root object! …)" / "is not a readable file" | same script, `/tmp/p10c_fake.pdf`, `/tmp/p10c_gone.pdf` |
| cover / label strings in the pure function | stops: "is not a date printed as 'Month D, YYYY'", "is neither a bare year nor a date", "is not a calendar date" | `/tmp/p10c_c4.py` and the `February 30, 2025` check |
| filename year | `None` -> `discover_filings` stops naming the file (unchanged); web passes **year 0, not verified** (`year or 0`, `api/routes_upload.py:114`, pre-existing, backlog item 49) | a "defaults to 0" row, not this unit's; the assignment excludes item 49 |
| year 0 (bare path) | not verified, by the assignment's design: it asks for every year | `/tmp/p10c_rule3.py`: `parse_pdf_args(["/tmp/p10c_fake.pdf"])` -> `[(0, …)]` |

## Measurements

**Baseline.** The working tree already carries P10a/P10b's uncommitted edits (31 red at
start, P10a's run_dcf change). To compare against a clean tree, HEAD (`54c966f`) was
exported with `git archive HEAD | tar -x -C /tmp/p10c-base` (10K_filings and .venv
symlinked in). Gate there: `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`
-> **397 passed, 1 failed** (`test_capm.py::test_beta_stops_when_the_market_series_has_no_variation`).

**Evidence scan (scratch `/tmp/p10c_scan*.py`, pdfplumber 0.11.10).** Cover line found on
page 1 of all 16 filings. Income statement title lines (full-line match) and the header
within the next 5 lines:
- AbbVie: "Consolidated Statements of Earnings" -> "years ended December 31 (in millions, except per share data) 2023 2022 2021"
- Chipotle: "CONSOLIDATED STATEMENTS OF INCOME AND COMPREHENSIVE INCOME" -> "2023 2022 2021" (3 lines below)
- L3Harris 2023-12-29: "CONSOLIDATED STATEMENT OF OPERATIONS" (p28) -> "... December 29, 2023 December 30, 2022 December 31, 2021"
- L3Harris 2025-01-03: p41 -> "... January 3, 2025 December 29, 2023 December 30, 2022"
- L3Harris 2026-01-02: p35 -> "(In millions, except per share amounts) 2025 2024 2023"
- Okta: "CONSOLIDATED STATEMENTS OF OPERATIONS" -> "2024 2023 2022" (3 lines below)
- Walmart: "Consolidated Statements of Income" -> "(Amounts in millions, except per share data) 2023 2022 2021"
Table-of-contents lines carry a trailing page number or "— Fiscal Year Ended …", so a
full-line title match skips them.

Gate failure sets, as sets: `/tmp/p10c-baseline.txt` (HEAD) and `/tmp/p10c-after.txt`
(HEAD + this unit). New in after: the 5 tests named under criterion 7. Nothing left the
failing set. Timing: verification costs 2–4 s a filing (folder totals in criterion 1).

## What I did not do

- Did not touch the 5 tests that now fail (`tests/` is the tester's). Each needs a real
  10-K fixture with a year, or a bare path (year 0), or to assert the new stop.
- Did not change the prompt (out of scope). A date-column filing is still asked for
  "fiscal year 2024" with no date beside it; with the remedy, L3Harris's 2025-01-03
  filing is asked for 2024 and its column is headed "January 3, 2025".
- Did not change `ingestion/session_extraction.py` (not in scope): `plan` still prints
  "The fiscal year comes from the filename. Check each one against the filing's cover
  page before extracting." after a successful plan; the second sentence is now done by
  the code.
- Did not fix item 49 (`year or 0` in `upload_files`) or item 28 (`file.filename` as a
  path segment).

## Findings for the orchestrator

1. **Criterion 7 contradicts step 2.** Five existing tests give a year with a file whose
   content cannot be read (stand-in bytes, or a path that does not exist) and assert the
   run continues. Step 2 says it stops. A tester unit should update them: a real-PDF
   fixture (e.g. a page subset of a filing under `10K_filings/`, built with
   `pypdfium2`, which is installed), a bare path, or an assertion of the stop. Named in
   criterion 7.
2. **A 10-Q with a year in its filename is now refused** on the web and the CLI ("no
   10-K cover line"). The upload page still says "10-K/10-Q". Remedy today: a bare path
   (CLI) or a filename with no year (web, then item 49 applies). Whether a 10-Q needs its
   own cover rule ("For the quarterly period ended") is a product decision.
3. **Stale text outside this unit's scope:** `.claude/skills/extract-filing/SKILL.md:63-65`
   ("The year comes from the filename… If a year is wrong, stop and tell the user"),
   `ingestion/session_extraction.py`'s `plan` closing line, the status of
   `docs/9-reference/refactor-backlog.md` item 43, and
   `tests/unit/test_filings.py`'s module docstring ("Deliberately not tested: the fiscal
   year…").
4. **The prompt names a year, never a date** (assignment's "record as a finding"): for
   date-column filers the model is asked for "fiscal year 2024" while the column says
   "January 3, 2025". Owner: whoever next holds `ingestion/claude_extractor.py`.
5. The remedy text says "Pass <year>:<path>", which a web user cannot do; "or rename the
   file" is the web remedy. Kept one message so the CLI, route B and the web say the same
   thing.
