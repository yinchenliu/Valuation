---
agent: programmer
assignment: P10c-fiscal-year
round: 2
status: complete
files_touched: [ingestion/filings.py, api/routes_upload.py, docs/3-architecture/extraction.md, docs/3-architecture/entry-points.md]
---

# P10c-fiscal-year, round 2 — the label wins within one year of the cover; F1, F3, F4, F5

Review answered: `.agent/journal/2026-10-02T2150-code_reviewer-p10c-fiscal-year.md`.
Round 1 entry: `.agent/journal/2026-10-02T2127-programmer-p10c-fiscal-year.md`.
Assignment: the "Round 2" section of `.agent/assignments/P10c-fiscal-year.md` (`1089c90`).

## What I did

I replaced the decision rule in `fiscal_year_from_evidence` with the amended one. A
bare-year label wins when it is the cover date's year or the year before. A label outside
that range stops. Date-only labels keep the cover rule, where January 1–7 belongs to the
year before, and must equal the cover date. I also deleted the `or ""` (F1).

`verify_filing_years` now sorts problems under two headings, "does not match the filing"
and "could not be confirmed against the filing" (F4). It takes a typed
`remedy: Literal["year_path", "rename_and_upload"]`, so the web says "rename … and upload
it again" (F5). `discover_filings` and `parse_pdf_args` pass `"year_path"`, and
`upload_files` passes `"rename_and_upload"`. An out-of-range label's stop now carries the
cover and label pages, because `_year_mismatch` reads the evidence first and decides
second. Docs: the rule, the two headings and the two remedies in `extraction.md`, and
F3 and F5 in `entry-points.md`. `templates/upload.html` is unchanged since round 1.

## Findings, by number

| # | Finding | Answer |
|---|---|---|
| F1 | `page.extract_text() or ""` | **Fixed.** `ingestion/filings.py`: `text = page.extract_text()`. `grep -n 'or ""' ingestion/filings.py` gives no hit (exit 1). mypy on the file is clean, because pdfplumber declares `-> str` |
| F2 | Target-style filers stop even with `YEAR:PATH` | **Fixed, per the orchestrator's amended rule.** `fiscal_year_from_evidence("February 1, 2025", "2024")` gives **2024**. `/tmp/p10c_c4r2.py`, row "Target-style". A label outside {cover year, cover year − 1} stops. `("December 31, 2025", "2023")`, `("December 31, 2025", "2026")` and `("February 1, 2025", "2026")` each stop. Through `verify_filing_years` the stop names the label, the cover date and each page (stubbed evidence, cover p1, label p40, shown below) |
| F3 | entry-points.md "measured at `P9b-session-web`" | **Fixed.** It now says "measured at `P10c-fiscal-year` round 2 (2026-10-02, on top of `1ae0069`)". I checked every number in the route table against the files: `routes_upload.py:70`, `:82`, and **`:129`** (round 2's new argument line moved `upload_session_file` from :128), plus `routes_valuation.py:362`, `:497` and `:548` |
| F4 | "does not match" heading on unreadable evidence | **Fixed.** Two headings. A mixed call (`parse_pdf_args(['2024:/tmp/p10c_fake.pdf', '2025:…2025-01-03…'])`) prints "The fiscal year given does not match the filing:" above the L3Harris line, and "The fiscal year given could not be confirmed against the filing:" above the fake PDF's line. It ends "Nothing was extracted." A label out of range, or a date label that is not the cover date, goes under "could not be confirmed", because the filing gives no year to compare |
| F5 | web remedy names a server path | **Fixed.** The web message now ends "Rename the file so the year after '10-K' in its name is 2025, and upload it again." (`/tmp/p10c_c5.py`). Proved by execution: posting the same L3Harris 2026 bytes renamed `…_10-K_2025-01-02_English.pdf` gives `303 /assumptions?…files=2025:…` |
| F6 | SKILL.md edited out of scope | Not mine. The orchestrator states in the Round 2 section that it made that edit. I did not touch `.claude/` |

## Done-criteria, re-run in round 2

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | 13 agreeing filings pass | pass | `PYTHONPATH=. .venv/bin/python /tmp/p10c_c1_c3.py`: AbbVie [2023,2024,2025] 10.6 s, Chipotle [2023,2024,2025] 6.6 s, Okta [2024,2025,2026] 12.8 s, Walmart [2023..2026] 14.9 s, no error |
| 2 | L3Harris stops | pass | Same script: "The fiscal year given does not match the filing:" lists `…_2025-01-03_…` (given 2025, content 2024, cover p1, label 'January 3, 2025' p41, "Pass 2024:<path> instead, or rename the file so the year after '10-K' in its name is 2024.") and `…_2026-01-02_…` (given 2026, content 2025, label '2025' p35) |
| 3 | remedy works | pass | Same script: [(2023,…), (2024,…), (2025,…)]. `plan_filings` gives 2023 None/no B/S, 2024 (2024,), 2025 (2025,) with B/S |
| 4 | decision rule on strings | pass | `PYTHONPATH=. .venv/bin/python /tmp/p10c_c4r2.py`: all 10 table rows `ok`. Date-only labels: Jan 7 gives the prior year, Jan 8 the same year |
| 4b | **new:** Target-style on strings | pass | Same script: `f('February 1, 2025', '2024') = 2024` |
| 5 | web upload stops | pass | `/tmp/p10c_c5.py`: LHX 2026 PDF gives `400`, location None, the alert shows the message with the web remedy, and the form is re-rendered. The 2023-12-29 PDF gives `303 /assumptions?…files=2023:…`. `GET /` gives 200 with no alert |
| 6 | route B `plan` | pass | `.venv/bin/python -m ingestion.session_extraction plan 10K_filings/LHX -t LHX -o /tmp/x.json` prints `ERROR:` with the same two lines and the CLI remedy, `exit=2`, and `/tmp/x.json` is not written. The Okta control gives exit 0 |
| 7 | no regression apart from step 2's stops | pass, on the reviewer's reading in round 1 | Clean trees from `git archive HEAD` (`1089c90`). HEAD: **31 failed, 367 passed**. HEAD plus this unit: **36 failed, 362 passed**. `diff` of the FAILED sets adds exactly the 5 named in round 1 and removes none. Each fails on the step-2 stop only: "'/x/a.pdf' is not a readable file", "'TST_10-K_2024.pdf' could not be opened as a PDF", `assert 400 == 303`. They now sit under the "could not be confirmed" heading |
| 8 | lint and types | pass | Both trees: ruff "Found 5 errors". mypy (full command) "Found 10 errors in 4 files", and the `diff` of the two outputs is empty. Rule 3 census 114 in both |

The out-of-range stop through the verifier, with pages. I stubbed
`read_fiscal_year_evidence` to return cover 'December 31, 2025' p1 and label '2023' p40:
> The fiscal year given could not be confirmed against the filing:
>   - 'Fake_10-K_2025.pdf', given fiscal year 2025: the cover says 'For the fiscal year ended December 31, 2025' (page 1) and the newest column above the income statement is labelled '2023' (page 40); the income statement's newest column is labelled 2023, but the cover's fiscal year ended December 31, 2025. A label is accepted only as the cover date's year (2025) or the year before (2024); …

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `remedy` is a required `Literal["year_path", "rename_and_upload"]` argument, and the texts are an `if` in `_remedy_text` | F5 needs two remedies. Rule 2 allows a fixed, typed signature, and this selects text, not behaviour | Returning structured problems and formatting at each caller would copy the message body into `api/`. A default value would let a new caller give the wrong remedy silently |
| An out-of-range label and a date label that is not the cover date go under "could not be confirmed", not "does not match" | The filing yields no year, so nothing was compared. F4's point is that a heading must say which happened | — |
| The remedy names "the year after '10-K' in its name" | That is what `fiscal_year_from_filename` reads first. "Carries 2024" would not move a name whose first year token comes before the marker | Proved by the rename upload: 303 with `files=2025:` |
| Behaviour change: `("January 2, 2026", "2026")` now gives 2026. Round 1 stopped | The amended rule says a bare label equal to the cover date's year wins | Required by the Round 2 section. None of the 16 filings has this shape |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| a page's text | **no fallback now**. `extract_text()` returns `str` (F1) | `grep 'or ""'` gives no hit |
| cover date | stops: "no 10-K cover line …", under "could not be confirmed" | `/tmp/p10c_rule3.py` (AbbVie pages 11–25) |
| column label | stops: "no column headings …" | same script (AbbVie pages 1–5) |
| the PDF | stops: "could not be opened as a PDF" / "is not a readable file" | same script |
| a label too far from the cover | stops, naming label, cover and pages | the stubbed run above |
| filename year `None` on the web | **year 0, not verified** (`year or 0`, pre-existing, item 49) | unchanged context line, out of scope |

## Measurements

- Gate failure sets: `/tmp/p10c-r2-head.gate.txt` and `/tmp/p10c-r2-unit.gate.txt`.
- mypy outputs: `/tmp/p10c-r2-head.mypy.txt` and `/tmp/p10c-r2-unit.mypy.txt` (identical).
- Timing is unchanged from round 1 (2–4 s per filing).

## What I did not do

- `tests/`: the 5 tests named under criterion 7 still need the tester.
- `ingestion/session_extraction.py`'s `plan` closing line and backlog item 43's status. These are out of scope, as in round 1.

## Findings for the orchestrator

1. None of the 16 filings exercises the amended "year before" branch with a bare label
   except L3Harris 2026. The Target case is proved on strings only. A real Target-style
   10-K would be the first end-to-end proof.
2. Round 1's findings 1, 2 and 4 stand: the 5 tests, 10-Q filenames that carry a year, and the
   prompt that names a year and never a date.
