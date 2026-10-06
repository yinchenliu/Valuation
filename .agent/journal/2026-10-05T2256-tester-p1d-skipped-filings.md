---
agent: tester
assignment: P1d-skipped-filings
round: 1
status: complete
files_touched: [tests/unit/_real_filings.py, tests/unit/test_real_filings_helper.py, tests/unit/test_p14b_note_figures.py, tests/unit/test_p14d_finance_leases.py, tests/unit/test_p15a_two_routes.py, tests/conftest.py]
verdict: pass
---

# P1d-skipped-filings — the two filings this machine holds now run; the other two skip for a reason that names the path tried

## What I did

Replaced the four literal `Path("10K_filings/<Company>/...")` constants in
`tests/unit/test_p14b_note_figures.py` with `RealFiling(ticker, pattern)`
(`tests/unit/_real_filings.py`), which states the storage convention
`10K_filings/<TICKER>/<pattern>` once, resolves from the repository root rather than the
process working directory, counts **exactly one match** as found, and builds the skip
reason out of the path it tried. The Walmart guard looked in `10K_filings/Walmart/` and
the folder on disk is `10K_filings/WMT/`, so check B1's only test against a real Walmart
10-K skipped on the machine that holds that exact file name (item 101). It now runs and
passes. The L3Harris file on disk is named by fiscal-year label, not by period end date;
I opened its cover page and confirmed it **is** the filing the test describes, so that
test now runs and passes too. Chipotle and Okta are not on this machine and keep
skipping, with reasons that now name the path each looked for. Two text-only
corrections (`test_p14d_finance_leases.py:22`, `test_p15a_two_routes.py:238`) and item
102's comment in `tests/conftest.py` are in the same change. **No implementation file
was touched** — `ingestion/claude_extractor.py` is byte-identical before and after
(sha256 `ec77b4bc…`, 161300 bytes, checked at both ends of the mutation experiment).

Two findings came out of making the tests run: the L3Harris test **could not fail** under
a deleted check B1, and the Walmart test carried a revenue figure that the page it cites
does not print. Both are written up below.

**A measurement hazard, recorded first because it changes how to read everything else.**
Part way through this unit a second agent began editing the same working tree
(`api/routes_valuation.py`, `cli.py`, `templates/assumptions.html`,
`templates/valuation_result.html`, plus
`.agent/journal/2026-10-05T2244-programmer-p3c-one-number.md` and
`.agent/assignments/P3c-one-number.md` appearing untracked). Those in-flight edits turn
**22 to 23 route tests red** in the live tree right now, and the count moved between two
runs eight minutes apart. My gate and suite figures below are therefore taken twice: in
the live repository before those edits landed, and again in an isolated copy at
`C:/tmp/p1d-mut` holding my six files and nothing else of the other unit. The two agree.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | The Walmart real-filing test runs | **pass** | `-m pytest -q -rs tests/unit/test_p14b_note_figures.py` → `33 passed, 2 skipped`; the skip list holds only Chipotle and Okta, and `test_real_walmart_filing_scale_confirmation` passes. Baseline, measured before any edit with `-m pytest -q -rs` over the whole suite: this file skipped four tests, `:899` Walmart, `:939` Chipotle, `:963` Okta, `:1007` L3Harris, each with the reason `… 10-K PDF not found` |
| 2 | The skip list is honest | **pass** | Full suite `-rsf` leaves three skips: `test_p14b_note_figures.py:971` `no file on this machine matches 10K_filings/CMG/Chipotle Mexican Grill Inc._10-K_2025-12-31_English.pdf`; `:999` the same shape for `10K_filings/OKTA/Okta Inc._10-K_2026-01-31_English.pdf`; `test_p14d_finance_leases.py:519` `extractions/WMT.json … absent`. `ls 10K_filings/*` gives nine PDFs under `ABBV/`, `LHX/`, `WMT/` and no CMG or OKTA folder; `ls extractions/` → `No such file or directory`. Each reason names a path, and each named path is absent |
| 3 | The L3Harris question answered by reading the PDF | **pass** | `pdfplumber` in a `-c` command, see "The L3Harris filing" below. Cover page: `For the fiscal year ended January 2, 2026`. PDF page 62 parentheses include `(In millions)` and `(In thousands)` |
| 4 | No literal company-name folder survives in `tests/` | **pass** | `grep -rn "10K_filings/Walmart\|10K_filings/Chipotle\|10K_filings/Okta" tests/` → three matches, all three inside prose describing the defect that was fixed (`test_p14b_note_figures.py:85`, `test_p15a_two_routes.py:238`, `_real_filings.py:9`). No code path builds a path from any of them |
| 5 | The gate is green | **pass** | Isolated copy: `-m pytest -q --ignore-glob="*_rule3_red.py"` → **1146 passed, 3 skipped, 0 failed**. Live repo, before the other unit's edits landed: `1139 passed, 3 skipped, 0 failed` (that run predates the 7 helper tests). Failing-name set before = `{}`, after = `{}` |
| 6 | Full suite shows only the two deliberate failures | **pass** | Isolated copy: `2 failed, 1146 passed, 3 skipped`. The set is `{test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input, test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops}` — byte-identical to the baseline set I captured before any edit |
| 7 | A newly-running test is a real measurement | **pass** | Mutation in `C:/tmp/p1d-mut/ingestion/claude_extractor.py`: `return []` inserted as the first line of `_row_scale_failures` (check B1 reverted). Walmart test → `FAILED … assert 0 == 1`. L3Harris test **passed under the mutation** until I added Case C; with Case C both go red: `2 failed`. Repository file untouched throughout, sha256 `ec77b4bc…` identical before and after |
| 8 | Item 102's comment is correct | **pass** | `git diff tests/conftest.py` (quoted below): names three tests, and states that the loopback test cannot detect a no-op because a loopback connection succeeds with no patch at all. The three named tests run green: `-m pytest -q tests/unit/test_routes.py::test_no_socket_refuses_an_address_that_leaves_the_machine …::test_no_socket_refuses_an_address_it_cannot_read …::test_no_socket_allows_the_loopback_address` plus `test_cli_refuses_dash_p_claude` → `4 passed` |
| 9 | Lint | **pass** | `-m ruff check .` → `Found 4 errors`, all four `BLE001` (`grep -c BLE001` over the output = 4). Both in the live repo and in the isolated copy. My six files alone: `All checks passed!` |
| 10 | Nothing outside `tests/` changed | **pass** | `git diff --stat -- . ':(exclude)tests'` → empty for my work. `git status --porcelain` lists `M tests/conftest.py`, `M tests/unit/test_p14b_note_figures.py`, `M tests/unit/test_p14d_finance_leases.py`, `M tests/unit/test_p15a_two_routes.py`, `?? tests/unit/_real_filings.py`, `?? tests/unit/test_real_filings_helper.py` — **and four files of the other agent's unit** (`api/routes_valuation.py`, `cli.py`, `templates/assumptions.html`, `templates/valuation_result.html`), which are not mine and which I did not open |

## The L3Harris filing — criterion 3, read today

Command (`PYTHONIOENCODING=utf-8` because the default Windows code page cannot print the
cover page's ballot-box characters):

```
.venv/Scripts/python.exe -c "import pdfplumber, re, glob
for p in sorted(glob.glob('10K_filings/LHX/*.pdf')):
    with pdfplumber.open(p) as pdf:
        t = pdf.pages[0].extract_text() or ''
        print(p, len(pdf.pages), re.findall(r'[Ff]or the fiscal year ended[^\n]*', t))"
```

| File on disk | Pages | Cover page states |
|---|---|---|
| `L3Harris Technologies Inc._10-K_2023_English.pdf` | 191 | `For the fiscal year ended December 29, 2023` |
| `L3Harris Technologies Inc._10-K_2024_English.pdf` | 226 | `For the fiscal year ended January 3, 2025` |
| `L3Harris Technologies Inc._10-K_2025_English.pdf` | 89 | **`For the fiscal year ended January 2, 2026`** |

So `L3Harris Technologies Inc._10-K_2025_English.pdf` **is** the filing the constant named
as `…_10-K_2026-01-02_English.pdf`: same fiscal year end, 2026-01-02, stored under the
fiscal-year label instead of the period end date. The folder keeps two naming conventions
side by side — Walmart and AbbVie by period end date, L3Harris by fiscal-year label — so
neither can be inferred from the other, and the test now reads the cover page itself
rather than trusting the file name.

**Page 62 of that file** (PDF page index, 1-based, which is what `_row_scale_failures`
reads: `pdf.pages[page - 1]`, `ingestion/claude_extractor.py:1303`). Its parenthesised
text, in order:

```
['(In millions)', '(1)', '(1)', '(1)', '(2)', '(3)',
 '(collectively, the “L3Harris SIPs”)', '(e.g., RSUs and PSUs)',
 '(or board membership)', '(In thousands)']
```

Both `(In millions)` and `(In thousands)` are printed on that one page, as the test
claims: `(In millions)` heads the pension table, `(In thousands)` heads the
share-based-compensation table whose first row is `RSUs outstanding as of January 3, 2025
582 $ 210.28`. The page's text layer carries **no printed page number**, so the PDF index
is the only page number this citation can give (backlog item 100).

## The Walmart filing — the pages the test cites, read today

| PDF page (1-based) | What it prints |
|---|---|
| 1 | Cover page, `For the fiscal year ended January 31, 2026`. Parentheses: `(10-K)`, `(d)`, `(Exact name of registrant as specified in its charter)`, `(IRS Employer Identification No.)`, `(Zip Code)`, `(479)` … **no unit statement** |
| 2 | Table of contents. Parentheses: `("SEC")`, `(the "Exchange Act")`, `(including the use of artificial intelligence "AI")` … **no unit statement** |
| 21 | End of the audit report and the head of the Consolidated Statements of Income: `Fiscal Years Ended January 31,` / **`(Amounts in millions, except per share data) 2026 2025 2024`** / `Revenues:` / `Net sales $ 706,413 $ 674,538 $ 642,637` / `Membership and other income 6,750 6,447 5,488` / `Total revenues 713,163 680,985 648,125` |

The file is 86 pages. Page 21's text layer holds no printed page number either.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| One helper `RealFiling(ticker, pattern)` in `tests/unit/_real_filings.py` | Assignment step 1 | Four corrected literals go stale the next time a filing is added, and a literal cannot carry the skip reason. The helper states the convention once and owns the reason text |
| `FILINGS_ROOT` is absolute, from `Path(__file__).parents[2]` | The old constants were relative, so they also depended on the directory pytest was started in | A guard that depends on the working directory is a second way to skip silently |
| **Exactly one match counts as found**; two matches is a miss | A pattern matching the 2023, 2024 and 2025 L3Harris files names no one document | Taking "whichever sorted first" would read a different filing from the one the citations describe, and would still report green |
| Pointed the L3Harris lookup at `…_10-K_2025_English.pdf` | Its cover page states the fiscal year ended January 2, 2026 — the filing the test already described | This is not a retarget at a different document; the assignment's warning is what the cover-page read answers. The test now asserts the cover-page text so a future rename cannot quietly substitute another year |
| Added Case C to the L3Harris test | Cases A and B both expected zero failures, so the test passed with check B1 deleted (measured) | Leaving it would have replaced a skipping test with a test that cannot fail, which reads cleaner and measures no more |
| Corrected the Walmart row figure 680,984 → 713,163 | PDF page 21 prints `Total revenues 713,163 680,985 648,125` under `2026 2025 2024`; the test's row is `year=2026` | 680,984 is neither the 2026 figure nor the 2025 figure (680,985). `_row_scale_failures` reads pages, not values, so nothing moved — but a test citing a filing page should carry the figure that page prints |
| Corrected `test_p15a_two_routes.py:238` | Assignment step 5 allows it if the three assertions do not move | They do not: argparse rejects `-p claude` while parsing arguments, before `cli.py` opens any path, so exit code 2 and both stderr assertions are produced without the folder ever being read. Verified green after the change |

**A code change made to reach a target number, rather than on a reason, is forbidden.**
Nothing here was changed to make a figure look right. No assertion was weakened,
skipped or xfailed; the one test I changed the expected side of (the Walmart revenue
value) is a figure read off the filing page, not an assertion — `_row_scale_failures`
never compares it.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| the filing bytes, via `RealFiling.read_bytes()` | **stops** and names the path tried: `FileNotFoundError("no file on this machine matches 10K_filings/OKTA/Okta Inc._10-K_2026-01-31_English.pdf")` | `test_read_bytes_on_a_miss_stops_and_names_the_path_tried`. It never returns `b""`, which would have let a test "pass" against an empty PDF |
| the ticker folder | **misses, by design, and says so** — this is a guard, not a run. `found` is `False` and the reason names the folder | `test_a_ticker_folder_that_does_not_exist_is_a_miss_not_an_error` |
| a pattern matching several files | **misses** and the reason names every file that matched | `test_two_matches_name_no_one_document_so_the_lookup_misses` |
| Pass 1 `page`, `units`, `share_units`, `year`, `label` | **stops** — `KeyError`/`ValueError` naming the key | Already locked by `test_p14b_note_figures.py` section 13 (`test_rule_3_*`), unchanged by this unit and green |

No stop path in scope defaults instead of raising. `RealFiling` is test code; the
implementation stop paths it feeds are the ones check B1 already owns.

## Measurements

**Failure sets, not counts.**

| Run | Failing set | Passed | Skipped |
|---|---|---|---|
| Baseline, full suite, before any edit | `{test_projector_rule3_red::test_an_extraction_with_no_income_statements_stops_and_names_the_input, test_routes_session_rule3_red::test_valuation_with_session_file_and_files_on_a_cache_hit_stops}` | 1137 | 5 |
| After, full suite, isolated copy | **the same two names** | 1146 | 3 |
| Baseline, gate (`--ignore-glob="*_rule3_red.py"`) | `{}` | 1137 | 5 |
| After, gate, isolated copy | `{}` | 1146 | 3 |

+9 passing tests: 2 that used to skip (Walmart, L3Harris) and 7 new helper tests.
−2 skips: the two filings this machine holds.

**Lint.** `Found 4 errors`, all `BLE001`, unchanged. My six files: `All checks passed!`.

**The mutation (criterion 7), in full.** In `C:/tmp/p1d-mut` only:

```
def _row_scale_failures(data: dict[str, Any], pdf_bytes: bytes) -> list[_CheckFailure]:
    return []  # MUTATION: check B1 reverted
```

Run 1 (before Case C): `test_real_walmart_filing_scale_confirmation` **FAILED**
(`assert 0 == 1`), `test_real_lhx_filing_multi_scale_limit` **passed**.
Run 2 (after Case C): both **FAILED**. Repository copy of
`ingestion/claude_extractor.py`: 161300 bytes, sha256
`ec77b4bcfab6fa6a14ebc3fcd4cc74b928859e2de494fd0c6f1597c0f67cf719` before the experiment
and the same afterwards.

**Item 102, `git diff tests/conftest.py`** — comment only, no behaviour:

```
-# Two tests in `tests/unit/test_routes.py` hold this contract in place:
-# `test_no_socket_refuses_an_address_that_leaves_the_machine` and
-# `test_no_socket_allows_the_loopback_address`. Without the first, a later
-# change that turns the fixture into a no-op would pass every test in the suite.
+# Three tests in `tests/unit/test_routes.py` exercise this fixture:
+# `test_no_socket_refuses_an_address_that_leaves_the_machine`,
+# `test_no_socket_refuses_an_address_it_cannot_read` and
+# `test_no_socket_allows_the_loopback_address`.
+#
+# **The two refusal tests are what hold the contract.** The loopback test
+# cannot detect a fixture turned into a no-op: a connection to `127.0.0.1`
+# succeeds with no patch at all, so that test stays green against a fixture
+# that patches nothing. It states the Windows exception, it does not guard it.
+# Delete either refusal test and a later change that empties `_no_socket` would
+# pass every test in the suite.
```

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| Walmart, row on PDF page 21 → `_row_scale_failures(...) == []` | no failure | **Filing page.** Walmart FY2026 10-K, PDF page 21 prints `(Amounts in millions, except per share data)`; check B1 confirms a money row whose cited page prints a unit statement of the expected scale |
| Walmart, row moved to PDF page 2 → exactly 1 failure naming page 2 | 1 failure | **Filing pages 2 and 1.** Neither prints a parenthesised unit statement (page 2's only parentheses are `("SEC")`, `(the "Exchange Act")`, `(including the use of artificial intelligence "AI")`; page 1's are `(10-K)`, `(d)`, `(Zip Code)` …), and B1 consults the cited page and the one before it |
| Walmart row value `713163.0` | the printed figure | **Filing page 21**, row `Total revenues 713,163 680,985 648,125` under `2026 2025 2024` |
| L3Harris cover text `For the fiscal year ended January 2, 2026` | present | **Filing page 1**, read with pdfplumber today |
| L3Harris, expected millions, row on page 62 → `== []` | no failure | **Filing page 62** prints `(In millions)` |
| L3Harris, expected thousands, row on page 62 → `== []` | no failure | **Filing page 62** also prints `(In thousands)`; the multi-scale rule confirms a row of either scale |
| L3Harris Case C, row on page 2 → 1 failure naming page 2, `money figures`, `millions`, `'Revenue line' (revenue, year 2025)` | 1 failure | **Filing pages 2 and 1** print no unit statement (page 2's text layer holds no parentheses at all), and the four named parts are what check B1 is required to name — module docstring item 3, "fails naming page, kind, expected scale, and all citing rows". Not taken from the message the code emitted |
| `RealFiling("WMT", "<file>").found is True`, `.path == <root>/WMT/<file>`, `.read_bytes() == b"%PDF-1.4 one"` | as written | **The helper's stated contract**, written in `_real_filings.py`'s docstring before it ran; the bytes are the ones the test itself wrote |
| `RealFiling("Walmart", "<file>").found is False` | miss | **The contract**: the lookup is by ticker folder. This is item 101 stated as a test |
| `.skip_reason == "no file on this machine matches 10K_filings/WMT/Walmart Inc._10-K_2099-01-31_English.pdf"` | as written | **The contract**: a miss names the path it tried. The string is composed by hand from `10K_filings/` + ticker + pattern |
| three matching files → `found is False`, reason holds `3 files match`, `names no one document`, and all three file names | as written | **The contract**: exactly one match counts as found |
| a *directory* matching the pattern → `matches() == []` | miss | **The contract**: only files count |
| `read_bytes()` on a miss raises `FileNotFoundError` naming the path | raise | **Rule 3**: a missing input stops and names itself |
| `FILINGS_ROOT == REPO_ROOT / "10K_filings"`, absolute | as written | **The contract**: resolve from the repository, not the working directory. Checked against two files that must exist (`tests/unit/_real_filings.py`, `docs/INDEX.md`) |
| `test_cli_refuses_dash_p_claude`'s three assertions | unchanged | Not re-derived: they are P15a's, and the point of the change was that they **do not move**. Verified green with the corrected path |

**Not re-derived, and flagged as such:** the Chipotle (`page 29`) and Okta (`page 58`)
citations. This machine holds neither filing, so I could not read those pages. Both
docstrings now say the citation is the P14b tester's and has not been re-read here.

**Two counts, with their units.**

- **Accuracy: 41 of 41 assertions.** 3 re-derived in the Walmart test (filing pages), 8
  in the L3Harris test (filing pages + the stated requirement for Case C), 30 in
  `test_real_filings_helper.py` (the helper's written contract). Every one passes, and
  none has "what the code printed" as its source.
- **Coverage: 7 of 7 functions and 100% of branches in the code this unit added**
  (`tests/unit/_real_filings.py`: `folder`, `tried`, `matches`, `path`, `found`,
  `skip_reason`, `read_bytes`). Measured, not estimated:
  `-m pytest -q --cov=tests.unit._real_filings --cov-branch --cov-report=term-missing tests/unit/test_real_filings_helper.py`
  → `tests\unit\_real_filings.py 37 0 6 0 100%`.
- **Of the four real-filing guards: 2 of 4 execute on this machine** (was 0 of 4), and
  2 of 4 skip for a reason whose named path I confirmed is absent.

`--cov=analysis --cov=models` is not the measurement for this unit: it added no
`analysis/` or `models/` code and asserts nothing about either.

## What I did not do

- **Did not re-read the Chipotle and Okta pages.** Those filings are not on this machine
  and the assignment puts adding them out of scope. Their tests keep skipping.
- **Did not touch any implementation file.** The one code question this unit raises —
  whether `_row_scale_failures` is right — was answered by mutating a scratch copy, not
  the repository.
- **Did not chase the 22 route failures** now present in the live working tree. They are
  the other agent's in-flight edits (see below), not this unit's, and `api/` is outside
  my write scope.
- Left `C:/tmp/p1d-mut` in place so the criterion 7 mutation can be re-run; it holds a
  copy of the repository plus two PDFs and nothing of value.

## Findings for the orchestrator

1. **(Process, blocking for anyone measuring a gate.)** A second agent was editing this
   working tree while I measured it. `git status --porcelain` grew `M api/routes_valuation.py`,
   `M cli.py`, `M templates/assumptions.html`, `M templates/valuation_result.html`, plus
   `.agent/assignments/P3c-one-number.md` and
   `.agent/journal/2026-10-05T2244-programmer-p3c-one-number.md`, mid-run. With those
   edits in place the gate reports **22 failed** in one run and **23 failed** eight
   minutes later — `test_routes.py`, `test_routes_session.py`, `test_pipeline.py`,
   `test_p3b_pipeline_stops.py`. One of them,
   `test_get_assumptions_puts_the_derived_defaults_into_the_form`, fails deterministically
   on its own in the live tree (`assert '' == '20.0, 20.0, 20.0, 20.0, 20.0'`, the
   assumptions form renders an empty `revenue_growth`) and **passes in a copy of the tree
   taken before those edits**. So it is P3c's work in progress, not mine — but while two
   units share one working tree, neither one's gate figure means anything. Either
   serialise the units or give each a worktree.
2. **A real-filing test that could not fail.** `test_real_lhx_filing_multi_scale_limit`
   asserted `_row_scale_failures(...) == []` twice and nothing else. With check B1
   replaced by `return []` the test still passed. It is now mutation-sensitive (Case C),
   but the shape is worth a sweep: **any test whose only assertion is "no failures" is
   green against a deleted check.** Candidates are the other `== []` assertions in
   `tests/unit/test_p14b_note_figures.py`.
3. **A figure in a real-filing test matched no column on the page it cited.**
   `test_real_walmart_filing_scale_confirmation` carried `680984.0` for `year=2026`;
   PDF page 21 prints `713,163` for 2026 and `680,985` for 2025. Corrected here. Nothing
   asserted it either way, which is exactly why it survived — a figure that no assertion
   reads is a citation nobody checks. Worth a pass over the other real-filing tests.
4. **Chipotle and Okta citations are unverified on this machine.** Both tests assert
   message text about pages 29 and 58 of filings nobody here can open. They will go red
   on the first machine that does hold those files if either citation is wrong, and that
   will look like a regression. The docstrings now say so.
5. **Item 100 again.** Neither Walmart PDF page 21 nor L3Harris PDF page 62 carries a
   printed page number in its text layer, so a citation from these two filings can only
   give the PDF index. Where the backlog asks for both numbers, that is sometimes not
   available; the rule may need the exception written into it.
6. **Items 101 and 102 can be closed.** Item 101: no guard in `tests/` now builds a path
   from a company name. Item 102: the comment names three tests and states which two hold
   the contract.
