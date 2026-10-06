---
agent: code_reviewer
assignment: P3b-pipeline-stops
round: 1
verdict: approved
---

# Review of P3b-pipeline-stops, round 1

Programmer entry: `.agent/journal/2026-10-05T1548-programmer-p3b-pipeline-stops.md`

Diff reviewed: the uncommitted change against `0a8ea54`, five files, exactly the
assignment's **Files in scope**. `git status --porcelain` lists those five and nothing
else — no scope breach.

Measured on Windows, `.venv/Scripts/python.exe`, every command prefixed
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`.

## The guard checks

Run over the five files in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | hits at `cli.py:205`, `pipeline.py:83`, `pipeline.py:176`. **Not touched / not code**: `:205` is backlog item 90, outside the diff; the two `pipeline.py` hits are new **comments** quoting the expression this unit deleted (F4) |
| lookup with a fallback — `.get(k, 0)` | hits only in `ingestion/claude_extractor.py:1897, 2114-5, 2164, 2679`, none inside the diff (the diff touches `:83`, `:2756-2766`, `:3248-3278` only). `api/routes_valuation.py:365` is a `@router.get` decorator, a false positive |
| bare or-default — `or 0.0` | `ingestion/claude_extractor.py:1926-1928`, outside the diff |
| money field defaulted to zero — `: float = 0.0` | clean. The new field is `total_debt: float`, no default (`pipeline.py:95`) |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | `claude_extractor.py:1927-8`, `cli.py:701`, both outside the diff |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` gives no hit |

No guard hit falls on a line this unit wrote, except the two comments in F4.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| fiscal year of each filing, >1 filing, CLI | **yes**, names every yearless file | `cli.py a.pdf b.pdf -t TESTCO` → `ERROR: 2 of 2 filings have no fiscal year:` + both names, `exit=1` |
| fiscal year of each filing, >1 filing, web | **yes** | `_run_extraction(files='0:a.pdf,2025:b.pdf', …)` → `ValueError … - a.pdf`; extractor recorders show `[]` |
| fiscal year, exactly one filing | allowed by design — 0 means "every year this filing presents" (`ingestion/filings.py:342-344`). Unchanged by this unit | `r([(0,'a.pdf')])` returns |
| negative year, >1 filing | **yes** — the test is `year <= 0`, not `== 0` | `r([(-1,'a.pdf'),(2025,'b.pdf')])` raises |
| empty `filings` list | returns; both callers already stop (`_run_extraction` raises `files: … names no filing.`; `plan_filings` raises on empty). Answered in the programmer's decision table | read |
| latest year's balance sheet in `value_company` | **yes**, names `balance_sheet`, ticker, year, says "not set to 0", before any market call | criterion 12 below |
| `run.total_debt` printed by CLI stage 8 | cannot be missing — the field is required and is set from `latest_bs.total_debt` after the stop | `pipeline.py:95, 193, 237`; `grep -n latest_bs cli.py` → no match |
| debt lines inside the balance sheet | unchanged — `analysis/wacc.py:_require_valid_debt` still stops line by line | `analysis/wacc.py:82-134`, untouched |

No new default, no new fallback, no falsy-as-missing test in the diff.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | pass — `total_debt` is `BalanceSheet.total_debt`, the same object `calculate_wacc` reads (`analysis/wacc.py:129`), printed by the unchanged `print_wacc` as `${:>12,.0f}M` (`cli.py:765`). No new conversion, no crossed boundary |
| percentages converted at the route boundary, once | n/a — the diff adds no form value |
| falsy not treated as missing | pass — `if latest_bs is None`, not `if latest_bs` (`pipeline.py:181`); `year <= 0` is an explicit numeric test, not a falsy one |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | pass — `analysis/` is untouched; the one new import is `api/routes_valuation.py:22 → ingestion.filings`, the direction already in use |

## Done-criteria, re-run

Every row below was executed by me. Scratch scripts under `c:/tmp/`.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | one yearless of two stops and names it | pass | `ValueError: 1 of 2 filings have no fiscal year:\n  - a.pdf (given as 'a.pdf')` | yes |
| 2 | every yearless named | pass | `2 of 3 …` listing `a.pdf` and `c.pdf` | yes |
| 3 | one bare path allowed | pass | returns, `C3 ok` | yes |
| 4 | several, all with years, allowed | pass | returns, `C4 ok` | yes |
| 5 | CLI stops, names both, opens no PDF | pass | `ERROR: 2 of 2 …` both named, `exit=1` | yes |
| 6 | CLI still accepts one bare path | pass | reaches the fingerprint stage: `ERROR: extraction input 'a.pdf' is not a readable file, so its content cannot be fingerprinted…`, `exit=1` — past `parse_pdf_args` | yes |
| 7 | web route stops, no extraction | pass | `ValueError: 1 of 2 …`; `extractor calls: []` with both extractors replaced by recorders | yes |
| 8 | message reaches the page | pass | `GET /assumptions` → 200, `'a.pdf' in body: True`; `POST /valuation` → 200, same; `extractor calls: []` | yes |
| 9 | neither entry point filters | pass | `grep -n "valid = " cli.py api/routes_valuation.py` → `rc=1`, no match | yes |
| 10 | CLI conditional zero gone | pass | `grep -n "latest_bs.total_debt if latest_bs" cli.py` → `rc=1`; `grep -n "latest_bs" cli.py` → `rc=1` | yes |
| 11 | CLI prints the pipeline's figure | pass | `cli.py:1058: print_wacc(wacc_result, run.market_cap, run.total_debt)` — 1 match | yes |
| 12 | no balance sheet stops, names the field, no market call | pass | `balance_sheet is None for 'TST' in fiscal year 2024 … The debt balance is not set to 0 …`; `fetch_price_data calls: []`. Twin with a balance sheet does reach the recorder, so the stop is the balance sheet's | yes |
| 13 | types | 5 in 2, disputes the assignment's "3 files" | `Found 5 errors in 2 files (checked 21 source files)` — `analysis/projector.py` ×4, `api/routes_upload.py:28` ×1 | yes — and the assignment's expected value is wrong, see below |
| 14 | lint | 4, all `BLE001` | `Found 4 errors.`, all `BLE001` (`routes_valuation:451`, `:709`, `cli:1139`, `test_e2e_all_googl:106`) | yes |
| 15 | census | 64 | `64` | yes |
| 16 | route | 200 | `GET /` → 200 | yes |
| 17 | no new failing test, by name | 0 failed | **1107 passed, 5 skipped, 0 failed in 142.25s** (gate form). Full suite adds exactly the two red-on-purpose: `test_projector_rule3_red::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` | yes |

**Criterion 17 is a set comparison, and I made it one.** Failing set with the diff in
place = {} in the gate form; = the two `_rule3_red` names in the full form. Both are
subsets of the post-`P1b` baseline the overall lead supplied (0 failed gate-form, 2
failed full). No name was added. The assignment's "14 failed, 1090 passed" baseline is
stale, as the lead stated and the programmer reported; I measured against the live one.

**Criterion 13's expected value is wrong in the assignment**, not in the code: it says
"5 errors in 3 files"; the measurement is 5 in 2, because `api/routes_valuation.py:128`
was that file's only error. The programmer disclosed this (its finding 2) and the lead
confirmed 5-in-2 independently. Not a finding against the unit; the orchestrator should
correct `STATUS.md` section 1 to **5 errors in 2 files**.

**`test_value_company_stops_on_a_missing_latest_balance_sheet` already exists at `HEAD`**
(`git show HEAD:tests/unit/test_pipeline.py` line 386) and passed before, because
`calculate_wacc` raised the same words later. It still passes, now from the earlier stop.

## Findings

### F1 — the new stop's second remedy is false on the CLI path · `minor`

**Evidence:** two files already named `ABBV_10-K_2025-12-31.pdf` and
`ABBV_10-K_2024-12-31.pdf`, passed as bare paths, are told
`or rename the file so the year after '10-K' in its name is that year` —
`.venv/Scripts/python.exe cli.py "c:/tmp/ABBV_10-K_2025-12-31.pdf" "c:/tmp/ABBV_10-K_2024-12-31.pdf" -t ABBV`
→ the same stop, `exit=1`. `ingestion/filings.py:498-506` never calls
`fiscal_year_from_filename` for a path argument; only the folder branch
(`discover_filings`) and the web upload read the year off a name.
**Rule or document:** no rule in `rules.md`. The wording came from the assignment's own
step 1, so this is the assignment's defect as much as the code's. The remedy is true for
the web-upload route and for a ticker folder, false for a list of CLI paths — the path
on which this message is most often seen.
**What would fix it:** name the two remedies that work on the path that raised — give
each as `YEAR:PATH`, or pass the folder — and drop the rename advice, or qualify it with
"when the filings are given as a folder".

### F2 — this unit made `ingestion/session_extraction.py:864-871` dead, and did not record it · `minor`

**Evidence:** `se.cmd_plan(['a.pdf','b.pdf'],'T','T',Path('c:/tmp/x_plan.json'),False)`
now raises the **new** message (`2 of 2 filings have no fiscal year: …`), not
`cmd_plan`'s own `"With more than one filing each needs a fiscal year. No year for: …"`.
`cmd_plan` calls `parse_pdf_args` (`ingestion/session_extraction.py:863`), which now
raises first on every branch that could yield a year ≤ 0.
**Rule or document:** no rule. It contradicts the assignment's own objective — "one named
function holds the rule … the rule lives in one function because item 49 says 'Make the
change in both entry points, or after item 7 in one place'" — by leaving a third,
unreachable copy. Assignment step 8 asks for such a discovery under "Found"; the
programmer's four findings do not include it. `session_extraction.py` is out of scope, so
not deleting it was correct; not reporting it was the miss.
**What would fix it:** the orchestrator adds a backlog line for deleting
`session_extraction.py:864-871`. Nothing in this unit's five files changes.

### F3 — the invariant the two new comments assert is only enforced on one of `parse_pdf_args`' two return paths · `note`

**Evidence:** `ingestion/filings.py:500-503` returns `discover_filings(...)` before
`:507 require_fiscal_year_per_filing(filings)` ever runs, yet `cli.py:891-892` says
"`parse_pdf_args` called `require_fiscal_year_per_filing` above".
**Rule or document:** none. True today only because `discover_filings` stops on a
filename with no year (`ingestion/filings.py:456-461`) — a second file's behaviour, not
this function's.
**What would fix it:** call it once after both branches, or say in the comment that the
folder branch is covered by `discover_filings`' own stop.

### F4 — two new comments reproduce the conditional zero they describe · `note`

**Evidence:** `grep -rnE "if [^)]+ else 0(\.0)?\b" pipeline.py` → `83`, `176`, both
quoting `latest_bs.total_debt if latest_bs else 0`.
**Rule or document:** none — they are comments, and the census grep covers
`models analysis api ingestion` only, so the figure 64 is unaffected and criterion 10's
grep targets `cli.py`. But the programmer's decision table claims "The three explanatory
comments describe the deleted lines instead of quoting them", and two of the three quote
it. A reviewer grepping the repository for the pattern now lands on prose.
**What would fix it:** either describe the deleted line in words in `pipeline.py` too, or
correct the claim in the entry.

### F5 — `ValuationRun.latest_balance_sheet` is now read by no production code · `note`

**Evidence:** `grep -rn "latest_balance_sheet" --include=*.py .` outside `tests/` and
`ingestion/` gives only `pipeline.py:75, 94, 236` — the field's own definition and its
assignment; `total_debt` is what the CLI needed from it. `tests/unit/test_pipeline.py:298`
still asserts on it.
**Rule or document:** none. Dead field. The programmer raised this itself (its finding 4);
recorded here so the outcome is tracked.
**What would fix it:** a later unit deletes the field, with the test assertion.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 90 — terminal growth default is a literal | `cli.py:205` | no |
| 8 — blanket `except Exception` renders the new stop at 200 | `api/routes_valuation.py:451`, `:709`, `cli.py:1139` | no. Criterion 8 expects 200 by the assignment |
| 26 — the `files` branch tests for a character every path contains | `api/routes_valuation.py:95-100` | no |
| 5 — module-global extraction cache | `api/routes_valuation.py` | no |
| 82 — cache key stores the model as "(provider default)" | `cli.py` | no |
| the 46 `.get(field, 0)` and `or 0` sites in `ingestion/claude_extractor.py` | `:1897, 1926-8, 2114-5, 2164, 2679` | no — the diff touches `:83`, `:2756-2766`, `:3248-3278` |
| 72 — the `total_debt` conditional zero | `cli.py` (backlog line 107) | **yes — closed by this unit.** Verified gone |
| 49 — yearless filings dropped silently | `cli.py`, `api/routes_valuation.py` (backlog line 864) | **yes — closed by this unit.** Both filters gone, both entry points stop |

I also saw the entry-point asymmetry that a single `2024:a.pdf` takes the web's
single-file branch (`api/routes_valuation.py:117`) but the CLI's multi-year branch
(`cli.py:880`). The assignment explicitly says to keep each single-filing branch exactly
as it is, so it is out of scope and not a finding here.

## Earlier findings — re-reviews only

None. Round 1.

## Verdict

`approved`

No blocker and no major stands. Every one of the seventeen done-criteria was re-executed
and matches, measured against the live post-`P1b` baseline rather than the assignment's
stale table: the gate form gives 1107 passed, 5 skipped, 0 failed, and the full suite
adds only the two red-on-purpose names. Both halves of the unit do what rule 3 asks — a
yearless filing among several now stops before any PDF is opened and names every offender
on both entry points, and a missing balance sheet stops before `fetch_price_data`,
naming the field, the ticker and the year, and saying the debt balance is not set to 0.
The identity that matters is intact: `run.total_debt` is `latest_bs.total_debt`, the same
object `analysis/wacc.py:_require_valid_debt` weights the capital with, so no displayed
figure moved. The four findings are two `minor` and two `note`: F1 is a user-facing
remedy inherited from the assignment's own wording that is false on the CLI path, F2 is a
dead third copy of the rule that this unit orphaned in an out-of-scope file and did not
report, F3 and F4 are comment accuracy. None of them cites a rule, none forces
`changes_requested`, and F2 and F5 are orchestrator backlog work rather than edits to
these five files. The tester may be dispatched.
