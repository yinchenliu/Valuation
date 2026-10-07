---
agent: code_reviewer
assignment: P3d-invisible-year
round: 1
verdict: changes_requested
---

# Review of P3d-invisible-year, round 1

Programmer entry: `.agent/journal/2026-10-07T1101-programmer-p3d-invisible-year.md`

Every measurement below is mine, executed on the Windows machine with
`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe`. No repository file was
written: the six in-scope files and `extractions/WMT.json` carry the same sha256 before
and after my run (`/c/tmp/rev_sha_before.txt` vs `/c/tmp/rev_sha_after.txt`, `diff`
empty). HEAD tree is a `git archive` export at `C:\tmp\rev_head`; the working tree copy
is `C:\tmp\rev_after`. No `git stash`. My probe is `C:\tmp\rev_probe.py`, my pinned
Walmart runner `C:\tmp\rev_wmt_pinned.py` — both written by me, not the programmer's.

## The guard checks

Run over the six files in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | hits, all pre-existing and unmoved, **except** `cli.py:506`, which this diff moved — **F1** |
| lookup with a fallback — `.get(k, 0)` | clean in scope (only hit is `@router.get("/assumptions", …)`, a decorator) |
| bare or-default — `or 0.0` | pre-existing at `claude_extractor.py:1926-1928`, unmoved. `claude_extractor.py:2319` is a bare `or` whose right operand this diff edited — **F2** |
| money field defaulted to zero — `: float = 0.0` | hits only in `models/financial_statements.py` dataclasses, none in the diff (backlog item 1) |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | `cli.py:861`, `claude_extractor.py:1927-1928`; none in the diff |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` returns nothing |

Added lines only, which is the test that matters:

```
git diff -U0 -- . ':(exclude).agent' | grep "^+" | grep -E "else 0|\.get\(..., ...\)|or 0|float = 0.0|kwargs|getattr\("
-> exactly one line: cli.py:506 (the relocated net-margin row)
```

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| income statement of a year in `financials.years`, in `derive_assumptions` | **yes** — `ValueError`, names `revenue` and fiscal year 2024 | my probe section D on `C:\tmp\rev_after`: `revenue is not available for fiscal year 2024: 'PROBE' has no income statement for it …` |
| `income_statement_years` in `latest_year` | **yes** | probe E: `FinancialStatements for 'BSONLY' holds no income statements, so there is no latest year.` with `years == [2024]` |
| income statement of a year, CLI FCFF table | **yes**, named row, no figure invented | probe B: `2024  not extracted: income statement` |
| income statement of a year, web FCFF rows | **yes** | probe C: `row year=2024 computable=False missing=('income statement',)` |
| income statement of a year, `_build_ebit_reconciliation` | **yes** | probe H: `missing_statement='raw and adjusted income statement'` |
| income statement of a year, CLI income-statement table | not read — table is on `income_statement_years`, the year named below it | probe B2 |
| cash flow statement of a year, CLI cash flow table | blank column, **year named below the table** | probe E, BSONLY: blank column then `2024  not extracted: cash flow statement` |
| net income margin when `revenue == 0`, CLI income-statement table | **no — prints `0.0%`** | `cli.py:506` — **F1** |
| `target_years` when the caller supplies `[]` | **no — silently becomes the whole filing's years** | `ingestion/claude_extractor.py:2319` — **F2** |
| balance sheet, CLI balance-sheet section | prints `No balance sheet extracted.` when there are none; otherwise the latest one that exists, with its year in the heading | probe B2 and E |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | unchanged — no figure crosses a unit boundary in this diff; Walmart byte-identical (criterion 8) |
| percentages converted at the route boundary, once | untouched by this diff |
| falsy not treated as missing | one site, **F2**. `if is_years:` / `if not years:` / `if not reconciled:` are list-emptiness tests where emptiness *is* the condition meant, so they are correct |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean — `analysis/projector.py` imports `config`, `analysis.fcff`, `models.*`, `numpy`; the only added import is `IncomeStatement` from `models/` |
| `models/` imports nothing from this repo | clean — `models/financial_statements.py` imports only `dataclasses` |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | old behaviour reproduced | `years == [2023, 2025]`, 2024 in no table | HEAD tree, my probe: `years : [2023, 2025]`; `income_statement_years` **absent**; 2024 in no FCFF row, no web row, no statements table, no reconciliation line | **yes** |
| 2 | year visible in the CLI | `2024  not extracted: income statement` | identical string from `print_historical_fcff` on the working tree | **yes** |
| 3 | year visible on the web page | row with `missing=('income statement',)`; template renders it | `_historical_fcff_by_year` gives that row; I rendered `templates/_statements.html` with jinja directly — HEAD: 6 `not extracted` cells, after: **24** | **yes** |
| 4 | both entry points say the same thing | same five words | CLI `not extracted: income statement` = web `missing_statements=('income statement',)` rendered the same. **The FCFF tables match.** The reconciliation wording does not — see F4 | **yes, for the criterion as written** |
| 5 | projection refuses **by name** | `ValueError` naming revenue and 2024 | `type: ValueError`; message names `revenue`, fiscal year 2024, both year sets, and what to do. **Not an `AttributeError`.** At HEAD the same call returned `revenue growth = [0.19999999999999996] × 5` with no stop | **yes** |
| 6 | twelve readers visited | table of 12 | I checked each row against the code (`grep -rn "\.years"` outside `tests/`): all twelve match the table. All 37 `financials.years` reads in `templates/_statements.html` are guarded `{% if stmt is not none %}` — I confirmed every one of the 36 statement lookups has the guard; the one unguarded reader is `latest_year` at `:295`, which the programmer reports (its finding 4) | **yes** |
| 7 | `latest_year` message true when it prints | quoted for a BS-only filing | `years = [2024]` (non-empty, `[]` at HEAD) and the message still says "holds no income statements" — true, because the property reads the narrow set | **yes** |
| 8 | Walmart does not move | 370 lines, diff empty | **my own** pinned runner (`pipeline.fetch_price_data` replaced, seed 20261007, `current_price=100.0`, no network) on both trees: 370 lines each with elapsed-time lines stripped, `diff` empty, implied share price `$15.42` on both | **yes** |
| 9 | no figure moves where every year has an income statement | WMT plus the probe | WMT `Years extracted: [2022, 2023, 2024, 2025, 2026]` identical on both trees; probe's 2023 and 2025 FCFF rows identical in my two probe outputs | **yes** |
| 10 | types ≤ 5 in 2 files | 5 → 2, three removed | HEAD: `projector.py:172, 225, 235, 345` + `routes_upload.py:28` = **5 in 2**. After: `projector.py:395` + `routes_upload.py:28` = **2 in 2, 21 checked**. The three removed are exactly the crash sites | **yes** |
| 11 | lint 4, all `BLE001` | 4 | `ruff check .` → `Found 4 errors`, all `BLE001`, run after my last command and with no repository file written | **yes** |
| 12 | census 64 or fewer | 64 | HEAD tree 64, working tree **64**. No site added, none removed | **yes** |
| 13 | route 200 | 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` → **200** | **yes** |
| 14 | failing set by name | both empty / the same two | Working tree full suite: `2 failed, 1224 passed, 2 skipped`. HEAD scratch tree: `2 failed, 1220 passed, 6 skipped`. **Failing set by name is identical on both**: `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`. (The 4 passed/skipped difference is the scratch tree lacking `extractions/` and `10K_filings/`, which are not in git — not a state change) | **yes** |
| 15 | neither dead branch deleted, both reachable | `cli.py:839`, `routes_valuation.py:274` | **Both halves confirmed myself.** `grep -n 'missing.append("income statement")' cli.py api/routes_valuation.py` → `cli.py:839`, `api/routes_valuation.py:274`; `git diff` shows both as unchanged context. **Reachable**: both printed/returned for 2024 in my probe, sections B and C | **yes** |
| — | write guard | 48/48 | `.claude/check_guard.py` → `48/48 guard cases correct` | **yes** |

Every one of the fifteen stands on my own execution. The design choice — widen `years`,
add `income_statement_years`, point `latest_year` at the narrow set, make
`derive_assumptions` read the wide set and stop by name — is the right one and is argued
from reasons, not from a target number. The HEAD measurement that a silent skip would
have kept a 20.0% CAGR where two years of growth is 9.5% is real: I reproduced
`[0.19999999999999996] × 5` at HEAD myself.

## Findings

### F1 — the net-margin conditional zero was moved into new code, so it is this unit's · `major`

**Evidence:** `cli.py:506` —
`("  Margin", *[_pct(… .net_income / … .revenue if … .revenue else 0, col) for y in is_years])`.
It is the only line in the whole diff that `git diff | grep "^+"` matches against the
rule 3 shapes; it was deleted from `print_extracted_financials` and added inside the new
`_print_income_statement_table`.

**Rule or document:** `docs/2-rules/rules.md` rule 3, first row of its table (a
conditional zero). `docs/9-reference/severity.md`: "A defect the unit touched is the
unit's, backlog or not. **Moving a line makes it yours.**" The line's defect is
pre-existing and is one of backlog item 1's 64 census sites, but it is not in "a line the
unit did not touch" — the unit relocated it into a function it wrote.

**What would fix it:** in the relocated row, print a named absence instead of a number
when `revenue` is 0 — the same vocabulary the rest of this unit uses, e.g.
`"not computable: revenue is 0"` padded to `col` — rather than `0.0%`, which is
indistinguishable from a company that really earned nothing.

**I considered and rejected two downgrades**, both of which `severity.md` names: "the fix
belongs to a census unit" and "no filing in this repository has zero revenue". Neither is
a ground to call this a `note`. **One thing the orchestrator should weigh**, because it is
a reason to widen rather than to downgrade: the two rows immediately above it, `EBIT
Margin` and `Gross Margin`, read `IncomeStatement.operating_margin` and `.gross_margin`,
which carry the identical `if self.revenue else 0.0` at `models/financial_statements.py:108`
and `:132` and are **not** in this diff. Fixing `cli.py:506` alone leaves the same table
printing `0.0%` in two neighbouring rows for the same year. If the orchestrator widens
scope, widen it to those two as well, or the fix is cosmetic.

### F2 — `target_years or …` treats a caller's empty list as "not supplied" · `minor`

**Evidence:** `ingestion/claude_extractor.py:2319` —
`years = target_years or financials.income_statement_years`. This diff edited that line
(the right operand moved from `financials.years`), so it is in the diff.

**Rule or document:** the reviewer card's "Falsy is not missing": a caller that asks for
*no* years gets the whole filing's years, which is a different request, and the Pass 2
prompt then shows the model income statements it was not asked about. I am not ranking
this `major`: the unit did not write the `or`, only its right operand; the census grep
does not count it; and the programmer disclosed it himself as his finding 2 rather than
leaving it to be found.

**What would fix it:** `target_years if target_years is not None else
financials.income_statement_years`. The signature is already `list[int] | None`, so this
is behaviour-identical for every caller today and one token wide.

### F3 — the balance sheet the CLI shows can now be a different year from the one the valuation uses · `minor`

**Evidence:** `cli.py:_print_latest_balance_sheet` picks
`max(financials.balance_sheets, key=lambda sheet: sheet.year)`, where it previously read
`financials.get_balance_sheet(financials.latest_year)`. `pipeline.py:181-194` still nets
debt from `adjusted.get_balance_sheet(latest_year)`, and `latest_year` is now the latest
**income-statement** year.

**Rule or document:** none — it breaks no rule, which is why it is `minor` and not
`major`. For every filing in this repository the two years are the same one and nothing
moves (criterion 8, verified). But for a filing whose newest balance sheet sits on a year
with no income statement, stage 2 would print `EXTRACTED BALANCE SHEET — FY2026` with its
own `Net Debt`, while the WACC and the equity bridge are built from FY2025's balance
sheet, and no line says the two are different sheets. The heading does carry the year, so
the reader is not lied to; they are left to notice.

**What would fix it:** one sentence under the heading when the shown year is not
`latest_year`, saying which year the valuation's net debt and capital weights came from.
The change itself is right — it is what stops a BS-only filing raising out of
`latest_year` here, and the programmer's reason for it is sound.

### F4 — a new comment claims the CLI uses the web's words, and it does not · `note`

**Evidence:** `cli.py:748` says the unreconciled year is named "in the same words the
web's `_build_ebit_reconciliation` uses for the same year". My probe, same filing, same
year: CLI prints `2024: not reconciled: raw income statement, adjusted income statement`;
the web record is `missing_statement='raw and adjusted income statement'`
(`api/routes_valuation.py:371`).

**Rule or document:** none. A stale/incorrect comment, which `severity.md` lists under
`note`. Criterion 4 is about the FCFF tables, and those do match word for word.

**What would fix it:** either build the CLI string with the web's four-case vocabulary,
or soften the comment to "for the same reason" rather than "in the same words".

### F5 — a filing with no income statement at all reports the same fact twice · `note`

**Evidence:** my probe section E, BSONLY: `print_extracted_financials` prints
`No income statement extracted for any year.` and then `2024  not extracted: income
statement` for every year in the list. On a five-year filing that is one sentence plus
five lines saying the same thing.

**Rule or document:** none. Readability only.

**What would fix it:** skip the per-year lines when `is_years` is empty, since the
sentence above already covers every year.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 (census, 64 sites) | `models/financial_statements.py:108, 132, 152, 159`; `analysis/projector.py:73, 357`; the `: float = 0.0` fields | **no** — unmoved, unchanged. Census 64 at HEAD and 64 after |
| 1 (census) | `cli.py:506` | **yes** — see F1 |
| 8 (blanket `except Exception`) | `api/routes_valuation.py:463`, `:745`, `cli.py:1315` | no — the four `BLE001` lint errors are these, and the diff does not rely on them |
| 41 (unreachable `0.05` growth) | `analysis/projector.py:240` | no — still unreachable |
| 28 | `api/routes_upload.py:28` | no — the remaining mypy error, out of scope |
| the 17 blank cash-flow cells (`… if financials.get_cash_flow(y) else " " * col`) | `cli.py:_print_cash_flow_table` | **relocated**, but the branch substitutes **whitespace, not a number**, and the unit now names each such year under the table. No figure is invented, so it is not a rule 3 break. The programmer reports it (his finding 1) and it belongs in the backlog as its own unit |
| `templates/_statements.html:295` calls `latest_year` inside `{% set %}` | — | no — `templates/` is outside scope. The programmer's finding 4 is correct that widening `years` makes the path easier to reach; `latest_year` raised on that filing before this unit too |

I also confirm the two tests red on purpose are still red and did not go green:
`test_projector_rule3_red.py`'s input is a `FinancialStatements` with no statements of any
kind, so `years == []` on both trees and `_income_statements_for_years` returns an empty
list without stopping. The bare `IndexError` at `revenues[-1 - lookback]` is untouched.

The programmer's four findings for the orchestrator are all real and all correctly
characterised; I verified 1, 2 and 4 against the code and 3 by execution (a BS-only year
now stops `derive_assumptions` where it used to be dropped — that is the rule 3 answer and
it is right, and nothing in this repository is of that shape today).

## Earlier findings — re-reviews only

None. This is round 1.

## Verdict

`changes_requested`

**F1 blocks, and only F1.** Everything the assignment asked for is done and every one of
the fifteen done-criteria holds under my own execution, including the two the assignment
set as traps: neither dead branch was deleted and both now run, and `derive_assumptions`
stops with a `ValueError` naming `revenue` and fiscal year 2024 rather than an
`AttributeError`. Walmart is byte-identical across the two trees under my own pinned
market series. The design is argued from reasons and the twelve-reader table is accurate.
The single thing standing between this and `approved` is that a rule 3 conditional zero
was carried into a function this unit wrote, which `docs/9-reference/severity.md` makes
the unit's own defect regardless of the backlog. F2 and F3 are `minor` and do not block,
though F2's fix is one token and the line is already in the diff, so it is cheap to take
in the same round. If the orchestrator decides F1's proper home is a census unit covering
`models/financial_statements.py:108` and `:132` alongside it, that is a scope widening for
the orchestrator to make — it is not a downgrade I am allowed to grant.
