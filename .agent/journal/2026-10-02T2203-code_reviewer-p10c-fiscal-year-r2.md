---
agent: code_reviewer
assignment: P10c-fiscal-year
round: 2
verdict: approved
---

# Review of P10c-fiscal-year, round 2

Programmer entry: `.agent/journal/2026-10-02T2153-programmer-p10c-fiscal-year-r2.md`.
Round 1 review: `.agent/journal/2026-10-02T2150-code_reviewer-p10c-fiscal-year.md`.
Assignment: `.agent/assignments/P10c-fiscal-year.md`, including the "Round 2" section (`1089c90`).

Diff reviewed: `git diff 1089c90 -- ingestion/filings.py api/routes_upload.py templates/upload.html docs/3-architecture/extraction.md docs/3-architecture/entry-points.md`.
I measured everything in my own trees, built from `git archive 1089c90`.
`/tmp/p10c-r2rev/head` is HEAD only. `/tmp/p10c-r2rev/unit` is HEAD plus the five files.
`10K_filings/` is symlinked into both. Neither tree has a `.env`, and route A was not run.
The scratch scripts are in `/tmp/p10c-r2rev/s/`.

## The guard checks

These were run over the five files in scope.

| Check | Result |
|---|---|
| conditional zero: `if … else 0.0` | clean |
| lookup with a fallback: `.get(k, 0)` | one hit, `api/routes_upload.py:69` `@router.get("/", …)`. It is a route decorator, not a lookup |
| bare or-default | two hits, `routes_upload.py:100` `f.filename or ""` and `:115` `year or 0`. Both are unchanged context lines, already recorded (see below). **The round 1 hit at `filings.py:233` is gone.** `filings.py:240` now reads `text = page.extract_text()` (F1) |
| money field defaulted to zero | clean |
| `**kwargs` | clean |
| `getattr(` | clean |
| dict of functions keyed by data | clean. `_MONTHS` maps a name to a number, which rule 2 allows |
| model client outside `ingestion/` | clean (no hit in `models/ analysis/ api/`) |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| a page's text | no fallback. pdfplumber 0.11.10 declares `Page.extract_text(self, **kwargs: Any) -> str` | `filings.py:240`, `inspect.signature` |
| file, PDF bytes, cover line, column headings | each stops under "could not be confirmed against the filing", naming the file and what was missing | `parse_pdf_args(['2024:/tmp/p10c-r2rev/fake_10-K_2024.pdf', …])` prints "could not be opened as a PDF" under that heading |
| a bare-year label outside {cover year, cover year − 1} | stops, naming the label, the cover date and the page of each | evidence stubbed as `('December 31, 2025', p1, '2023', p40)`, under "could not be confirmed" |
| malformed strings (`''`, `Jan 3, 2025`, `FY2024`, `February 30, 2025`, `Janury 3, 2025`) | each stops, naming the string | `/tmp/p10c-r2rev/s/c4.py` |
| `remedy` | a required `Literal[...]` with no default, so mypy holds every caller to one of two values | `filings.py:291`, `:339` |
| filename year `None` on the web | year 0, not verified (`year or 0`) | pre-existing, item 49, out of scope |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | n/a. No financial figure is read or produced |
| percentages converted at the route boundary | n/a |
| falsy not treated as missing | new code uses `is not None` (`routes_upload.py:105`) and `year == 0` (`filings.py`, `verify_filing_years`) |
| layering | `analysis/` is untouched. `api/` → `ingestion.filings` is allowed. `filings.py` imports no model client |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | 13 agreeing filings pass | pass | `discover_filings`: AbbVie [2023,2024,2025] 10.5 s, Chipotle [2023–2025] 6.5 s, Okta [2024–2026] 12.8 s, Walmart [2023–2026] 14.9 s, no error. Every cover is on p1. Each label equals its year, on pp21–65 | yes |
| 2 | L3Harris stops | pass | "does not match the filing" names `…_2025-01-03_…`: given 2025, content 2024, cover p1, label `January 3, 2025` p41, then "Pass 2024:<path> instead, or rename…". It also names `…_2026-01-02_…`: 2026, content 2025, label `2025` p35 | yes |
| 3 | the remedy works | pass | `parse_pdf_args` on the three `YEAR:PATH` gives [2023, 2024, 2025]. `plan_filings` on them gives the years [2023, 2024, 2025] | yes |
| 4 | the rule on strings | pass | 12 rows `ok`: the table, plus Jan 7 → prior year and Jan 8 → same year. `("January 2, 2026", "2026")` now gives 2026, as the amended rule requires. 10 bad or out-of-range inputs each stop | yes |
| 4b | Target on strings | pass | `f("February 1, 2025", "2024") = 2024`. Through `verify_filing_years` with stubbed evidence, `2024:<path>` passes. Given 2025, it stops under "does not match" with the `2024:` remedy. That proves the round 1 trap is gone | yes |
| 5 | web upload stops | pass | `TestClient` posting the LHX 2026 PDF gives `400` with no location. The alert carries the message and ends "Rename the file so the year after '10-K' in its name is 2025, and upload it again." The form is re-rendered. The same bytes renamed `…_10-K_2025-01-02_…` give `303 …files=2025:…`, and the 2023-12-29 PDF gives `303 …files=2023:…`. `GET /` gives 200 with no alert. `<b>x<b>` in a filename is escaped | yes |
| 6 | route B `plan` | pass | `session_extraction plan 10K_filings/LHX -t LHX -o /tmp/p10c-r2rev/x.json` prints `ERROR:` and the same two entries with the CLI remedy. It exits 2 and does not write the file. The Okta control exits 0 and writes it | yes |
| 7 | no regression apart from step 2's stops | pass | Gate (`--ignore-glob="*_rule3_red.py"`): HEAD **367 passed, 31 failed**, and HEAD+unit **362 passed, 36 failed**. Diffing the FAILED **sets** adds exactly 5 and removes none: `test_filings::test_parse_pdf_args_reads_year_colon_path`, `test_routes::test_post_upload_journey_reaches_a_rendered_assumptions_page`, `test_routes::test_post_upload_saves_the_file_and_redirects_naming_it`, `test_routes::test_the_form_on_the_front_page_is_accepted_by_the_route_it_targets` and `test_session_extraction::test_plan_writes_route_a_plan_and_refuses_to_overwrite`. Each fails only on the step-2 stop: "'/x/a.pdf' is not a readable file", or `assert 400 == 303` / `400 == 200` | yes |
| 8 | lint and types | pass | ruff gives "Found 5 errors" in both trees, and is clean on the two changed `.py` files. mypy (full command) gives "Found 10 errors in 4 files" in both, and `diff` of the two outputs is empty. The rule 3 census is 114 in both | yes |

## Findings

### F7: The upload page still invites 10-Q PDFs, which the web now stops whenever the name carries a year · `note` (for the orchestrator)

**Evidence:** `templates/upload.html:8` and `:26` say "10-K/10-Q". A 10-Q has no "ANNUAL REPORT … fiscal year ended" cover, so `read_fiscal_year_evidence` stops, and the message under "could not be confirmed" offers no remedy. A web user can get through only by removing the year from the name, and item 49 then drops the file.
**Rule or document:** none broken. Assignment step 2 requires this stop, and the programmer's round 1 finding 2 already raised it. I record it again because the page text now promises something the route refuses.
**What would fix it:** an orchestrator decision: change the page text, or verify 10-Qs against their own cover line.

### F8: The CLI remedy prints an unquoted path, and every real filing name here holds spaces · `note`

**Evidence:** the criterion-2 output reads `Pass 2024:/Users/…/10K_filings/LHX/L3Harris Technologies Inc._10-K_2025-01-03_English.pdf instead`. Pasted into a shell, that becomes three arguments.
**Rule or document:** none.
**What would fix it:** quote the `YEAR:PATH` in `_remedy_text` (`filings.py:291`), for example with `shlex.quote`.

## Pre-existing, already recorded: not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 49, a filing with no year silently becomes year 0 | `api/routes_upload.py:115` `year or 0` | no (context line) |
| 28, `file.filename` used as a path segment | `api/routes_upload.py:28`. A filename holding `/` (`<script>x</script>_10-K_2024.pdf`) gives **500 in both trees** | no |
| adjacent to 28 and 49, `f.filename or ""` | `api/routes_upload.py:100` | no (context line) |

## Earlier findings: re-reviews only

| # | Outcome | Note |
|---|---|---|
| F1 | fixed | `filings.py:240` `text = page.extract_text()`. The bare-or grep finds nothing in `filings.py` |
| F2 | fixed | Implemented as the Round 2 rule (`filings.py:170`): the label wins within {cover year, cover year − 1}, and a label outside that range stops with both pages. Target's `2024:<path>` passes (4b). I did not widen or narrow the rule. It is the orchestrator's amendment, and `extraction.md` documents it |
| F3 | fixed | `entry-points.md:14-15` now says "measured at `P10c-fiscal-year` round 2 … on top of `1ae0069`". `api/` is identical between `1ae0069` and `1089c90`. I re-checked `routes_upload.py:70`, `:82`, `:129` and `routes_valuation.py:362`, `:497` against the file |
| F4 | fixed | There are two headings. A mixed call prints "does not match the filing" above the L3Harris entry and "could not be confirmed against the filing" above the fake PDF's |
| F5 | fixed | `remedy: Literal["year_path", "rename_and_upload"]` is required at both call sites. The web text says to rename and upload again, and a renamed upload of the same bytes gets 303 |
| F6 | withdrawn as a question | The Round 2 section of the assignment states that the orchestrator made the `SKILL.md` edit |

## Verdict

`approved`

Every round 1 finding is answered: F1, F3, F4 and F5 are fixed, F2 is fixed as amended, and F6 is explained by the assignment. I re-ran all eight done-criteria and the new 4b in clean trees built from `1089c90`, and each holds. The failure sets differ from HEAD by exactly the five step-2 tests the tester will repair, and nothing left the failing set. Lint, types and the rule 3 census are identical in both trees. F7 and F8 are notes and break no rule.
