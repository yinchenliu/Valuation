---
agent: code_reviewer
assignment: P10c-fiscal-year
round: 1
verdict: changes_requested
---

# Review of P10c-fiscal-year, round 1

Programmer entry: `.agent/journal/2026-10-02T2127-programmer-p10c-fiscal-year.md`

Diff reviewed: `git diff 54c966f -- ingestion/filings.py api/routes_upload.py templates/upload.html docs/3-architecture/extraction.md docs/3-architecture/entry-points.md`.
I measured everything in my own trees, built from `git archive 54c966f`:
`/tmp/p10c-rev-head` (HEAD only) and `/tmp/p10c-rev-unit` (HEAD plus this unit's three
code files). Neither tree has a `.env`. Route A was not run.

## The guard checks

These were run over the five files in scope.

| Check | Result |
|---|---|
| conditional zero: `if … else 0.0` | clean |
| lookup with a fallback: `.get(k, 0)` | one hit, `api/routes_upload.py:69` `@router.get("/", …)`, which is a route decorator and not a lookup |
| bare or-default: `or 0.0` / `or ""` | 3 hits. `routes_upload.py:100` `f.filename or ""` and `:114` `year or 0` are unchanged context lines (pre-existing, see below). **`ingestion/filings.py:233` `page.extract_text() or ""` is new, and the entry does not answer it.** That is **F1** |
| money field defaulted to zero: `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean. `_MONTHS` maps a name to a **number**, which rule 2 allows |
| model client imported outside `ingestion/` | clean (no hit in `models/ analysis/ api/`) |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| file path | yes: "is not a readable file" | probed with `/tmp/p10c-rev` (a directory) and `/x/a.pdf` |
| PDF bytes | yes: "could not be opened as a PDF" | probed with an empty file and with `b"%PDF-1.4 not a real filing"` |
| cover date | yes: "no 10-K cover line … in its first 5 pages" | probed with a 200 KB truncation of an Okta 10-K |
| column label | yes: "no column headings …", or "is not a date printed as 'Month D, YYYY'" | `fiscal_year_from_evidence("January 26, 2025", "Jan 26, 2025")` gives the stop |
| a page's text | **no.** `or ""` turns a missing text layer into an empty page, and the search moves on | F1 |
| filename year `None` | `discover_filings` stops naming the file (unchanged). The web passes it on as year 0, unverified: `year or 0` at :114, item 49 | pre-existing |
| sentinels `cover`/`column = None`, `next(…, None)` | each is checked, and a `None` stops | `filings.py:256-268` |
| `_JANUARY_DAYS_OF_PRIOR_YEAR = 7`, `_COVER_PAGES`, `_HEADING_LINES_BELOW_TITLE` | named and measured, and each feeds a year decision, never a displayed figure. Rule 6 does not bind them. The 7 is printed in the disagreement message | `filings.py:96-109` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | n/a. No financial figure is read or produced |
| percentages converted at the route boundary, once | n/a |
| falsy not treated as missing | new code uses `is not None` (`routes_upload.py:105`) and `year == 0` (`filings.py:316`). The `year or 0` at :114 is pre-existing |
| `analysis/` imports no `ingestion/`, `api/`, model client | untouched. `api/` → `ingestion.filings` is allowed. `filings.py` imports no model client; `pdfplumber` is imported inside the reader |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | 13 agreeing filings pass | pass | `discover_filings`: AbbVie [2023,2024,2025] 10.5 s, Chipotle [2023,2024,2025] 6.7 s, Okta [2024,2025,2026] 12.8 s, Walmart [2023..2026] 15.0 s, no error. The label pages I opened (Walmart 2026 p21, AbbVie 2024 p21, Okta 2024 p65) are the real income statements | yes |
| 2 | L3Harris stops | pass | `ValueError` names `…_2025-01-03_…`, given 2025, content 2024, cover p1, label `January 3, 2025` p41, remedy `Pass 2024:<path> … or rename`. The same message also names `…_2026-01-02_…` (2026, content 2025) | yes |
| 3 | remedy works | pass | `parse_pdf_args` with the three `YEAR:PATH` gives [2023, 2024, 2025]. `plan_filings` gives 2023 `target_years=None`, 2024 `(2024,)`, 2025 `(2025,)` with `include_bs=True` | yes |
| 4 | decision rule on strings | pass | all 8 table rows `ok`. Jan 7 gives the prior year, Jan 8 the same year. Every disagreement stops | yes |
| 5 | web upload stops | pass | `TestClient` posting the LHX 2026 PDF gives `400`, `location None`, the alert carries the message (HTML-escaped), and the form is re-rendered. The 2023-12-29 PDF gives `303 /assumptions?…files=2023:…`. `GET /` gives 200 with no alert. A `<script>` in the filename is escaped | yes |
| 6 | route B `plan` | pass | `python -m ingestion.session_extraction plan 10K_filings/LHX -t LHX -o /tmp/p10c-rev/x.json` prints `ERROR:` with the same two lines and `exit=2`, and the file is not written. Okta control: exit 0, file written | yes |
| 7 | no regression apart from step 2's stops | "fail as worded" | Gate (`--ignore-glob="*_rule3_red.py"`): HEAD **397 passed, 1 failed** (`test_capm…no_variation`). HEAD+unit **392 passed, 6 failed**. As sets, the new failures are exactly the 5 named, and nothing left the failing set. Each fails on the step-2 stop and nothing else: `test_parse_pdf_args_reads_year_colon_path` fails with "'/x/a.pdf' is not a readable file". The three `test_routes.py` tests get 400, and the alert reads "'goog-10k-2024.pdf' / 'testco-10k-2024.pdf' could not be opened as a PDF (No /Root object!…)". `test_plan_writes_route_a_plan…` fails with "'TST_10-K_2024.pdf' could not be opened as a PDF" | yes. The tests contradict step 2, and the tester will repair them |
| 8 | lint and types | pass | ruff: 5 errors in both trees, and `ruff check` on the two changed `.py` files is clean. mypy (full command): "10 errors in 4 files" in both, identical lines (`diff` empty). Rule 3 census: 116 in both | yes |

## Findings

### F1: `page.extract_text() or ""` is a bare or-default, and the entry does not answer it · `major`

**Evidence:** `ingestion/filings.py:233`. The greps hit it. pdfplumber 0.11.10 declares `Page.extract_text(self, **kwargs) -> str`, so the `or ""` is a fallback that can never run.
**Rule or document:** rules.md rule 3, the "bare `or` default" form. This prompt's reviewer instructions say outright that reachability is not the test. If a page's text were ever `None`, the reader would treat it as a blank page and keep searching. It would not stop and say that page could not be read. A hit the programmer does not answer is a finding.
**What would fix it:** delete the `or ""`. `text = page.extract_text()` is already typed `str`, and nothing else changes.

### F2: Filers that name a fiscal year for its starting calendar year stop, and no `YEAR:PATH` gets them past it · `note` (escalation to the orchestrator)

**Evidence:** `fiscal_year_from_evidence("February 1, 2025", "2024")` raises "…names fiscal 2025 under the cover rule … The filing contradicts itself; no year is chosen".
That is a retailer such as Target, whose 52/53-week year ends near January 31 and is called "2024".
Because `_year_problem` raises before it compares the year, `2024:<path>` stops as well. The only way through is a bare path (year 0).
The message says the filing contradicts itself, and for such a filer that is not true.
**Rule or document:** none broken. The code follows the assignment's step 1 to the letter: "when a bare-year label and the cover rule disagree, stop". The rule is fitted to the 16 filings in `10K_filings/`, and none of them is such a filer. This is a question about the specification, not a defect in the code. The orchestrator should decide whether the rule needs a second window or "the label wins".

### F3: `entry-points.md` updates the line numbers but keeps "measured at `P9b-session-web`" · `note`

**Evidence:** `docs/3-architecture/entry-points.md:14-15` still says "Line numbers measured at `P9b-session-web`". The table under it now carries post-P10c numbers (`:70`, `:82`, `:128`), and I checked each one against the file.
**What would fix it:** say the numbers were measured at P10c, or drop the claim.

### F4: The stop's heading says "does not match" when the evidence could not be read · `note`

**Evidence:** `filings.py:319-321`. The header "The fiscal year given does not match the filing" is printed above "'goog-10k-2024.pdf' … could not be opened as a PDF".
**What would fix it:** a neutral header, such as "The fiscal year given could not be confirmed against the filing".

### F5: The web message's remedy names a server path · `note` (the programmer's finding 5, which I agree with)

**Evidence:** the criterion-5 alert reads "Pass 2025:/private/tmp/p10c-rev-unit/uploads/LHX/L3Harris…pdf instead, or rename the file". A web user can only use the second half.

### F6: An out-of-scope file changed in the tree after the programmer's entry · `note`, not counted against this unit

**Evidence:** `.claude/skills/extract-filing/SKILL.md` was modified at 21:43:40 and the entry was last written at 21:43:04. The change rewrites lines 63-65, which are the stale lines the entry's finding 3 names. It is not in the entry's `files_touched` or in any assignment's scope that I could find (`grep -l SKILL.md .agent/assignments/*.md`: no hit). It is also not in the commit-time `git status`. Nothing ties it to this programmer. The orchestrator should confirm who wrote it.

Also seen, and not a finding: `verify_filing_years` runs 2-4 s of `pdfplumber` a filing inside `async def upload_files`, so it blocks the event loop. `assumptions_page` already runs a blocking extraction the same way, so this is the existing pattern. Every CLI run, a cache hit included, now pays this cost before the cache check (`cli.py:783`). `extraction.md` documents the cost.

## Pre-existing, already recorded: not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 49, a filing with no year silently becomes year 0 | `api/routes_upload.py:114` `year or 0` | no (context line). The assignment excludes item 49 |
| 28, `file.filename` (`str \| None`) used as a path segment | `api/routes_upload.py:28`. The mypy line is identical in both trees | no |
| (adjacent to 28 and 49) `f.filename or ""` | `api/routes_upload.py:100` | no (context line). A `None` name gives year `None`, so the file is not verified and becomes year 0 under item 49 |

## Earlier findings: re-reviews only

n/a, round 1.

## Verdict

`changes_requested`

The unit does what it was asked, and I proved every one of the eight done-criteria by execution in clean trees. The five red tests fail for step 2's reason and no other.
One finding blocks: **F1** (`filings.py:233`, an unanswered rule-3 bare or-default). The fix is one token and does not change behaviour.
F2 is a question about the specification for the orchestrator, not a defect in this code. F3 to F6 are notes.
