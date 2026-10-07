---
agent: programmer
assignment: P3d-invisible-year
round: 1
status: complete
files_touched: [models/financial_statements.py, analysis/projector.py, api/routes_valuation.py, cli.py, ingestion/claude_extractor.py, ingestion/session_extraction.py]
---

# P3d-invisible-year — a year any statement covers is now visible, and the branch written to report it runs

> Opened before the first command and filled as each result landed.

## What I did

`FinancialStatements.years` was built from `income_statements` alone, so a year with a
cash flow statement and a balance sheet and no income statement was in no table, carried
no reason, and nothing anywhere reported it (backlog item 116). **I widened `years` to
the union of all three statement types and added `income_statement_years` beside it** for
the readers that genuinely need an income statement per year. `latest_year` now reads the
narrow set, so its "holds no income statements" message is still true when it prints.
`analysis/projector.derive_assumptions` reads the wide set through one new call,
`_income_statements_for_years`, which **stops and names the field and the year** rather
than dereferencing `None` or skipping the year — the skip would move the derived growth
rate with nothing saying so, and I measured that it does (see Measurements). The two
branches written to report this case — `cli.py:839` and `api/routes_valuation.py:274` —
are untouched and now run. All twelve readers are visited and tabulated below. Walmart
does not move: with market data pinned, the whole 370-line CLI run is byte-identical
across the two trees.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the old behaviour is reproduced first | **pass** | `git archive HEAD` into `C:\tmp\p3d_head`, then `C:\tmp\p3d_probe.py` run there: `financials.years` is `[2023, 2025]`. **2024 is absent from the CLI FCFF table, from the web rows, from the CLI statements tables and from the reconciliation**, and no line of any of them names it. Its CFO 284, D&A 55, CapEx -44 and its balance sheet were extracted and dropped without a word. `C:\tmp\p3d_probe_head.txt` |
| 2 | that year is now visible in the CLI | **pass** | the same probe on the working tree: `print_historical_fcff` prints `  2024  not extracted: income statement`. `C:\tmp\p3d_probe_after.txt`, section B |
| 3 | that year is now visible on the web page | **pass** | `_historical_fcff_by_year` returns `row year=2024 computable=False missing=('income statement',)`, and the **production template block** (read out of `templates/_statements.html`, not retyped) renders six cells of `not extracted: income statement`. The statements table's Revenue row renders `Revenue \| 1,000 \| not extracted \| 1,200` against HEAD's `Revenue \| 1,000 \| 1,200`. Sections C and C2. **No template was edited** |
| 4 | both entry points say the same thing | **pass** | CLI `not extracted: income statement`; web `not extracted: income statement`. The same five words, because `cli.print_historical_fcff` and `_historical_fcff_by_year` build the same `missing` list from the same vocabulary |
| 5 | the projection refuses it **by name** | **pass** | section D: `ValueError: revenue is not available for fiscal year 2024: 'PROBE' has no income statement for it, so revenue, operating_margin and effective_tax_rate cannot be read for that year … The extracted years are [2023, 2024, 2025]; the years with an income statement are [2023, 2025]. …` Type and message printed. **Not an `AttributeError`**: at HEAD the same call returned assumptions with no stop at all |
| 6 | every one of the twelve readers is visited | **pass** | the table under "Decisions" below: twelve rows, file, line, set read, reason |
| 7 | `latest_year`'s message is true when it prints | **pass** | section E, a filing with one balance sheet and no income statement: `years = [2024]` (non-empty, where at HEAD it was `[]`) and `ValueError: FinancialStatements for 'BSONLY' holds no income statements, so there is no latest year.` — true, because the property reads `income_statement_years` and not `years` |
| 8 | Walmart does not move | **pass** | `C:\tmp\p3d_wmt_pinned.py` (market data pinned, no network) run on both trees: **370 lines, `diff` empty, "IDENTICAL"**. The live run of `cli.py --session-file extractions/WMT.json` on both trees in one sitting differs only in market-sourced figures and elapsed seconds — see Measurements |
| 9 | no figure moves for a filing whose years all have an income statement | **pass** | criterion 8 on `extractions/WMT.json` (three filings, five fiscal years 2022–2026, `years == income_statement_years`), plus the hand-built probe filing: its 2023 and 2025 FCFF rows, revenue, CFO, interest and CapEx are identical in `p3d_probe_head.txt` and `p3d_probe_after.txt` |
| 10 | types | **pass, 3 removed** | `5 errors in 2 files` → **`2 errors in 2 files`, 21 checked**. Removed: `analysis/projector.py:172, 225, 235`, the three `Item "None" of "IncomeStatement \| None" has no attribute …` — exactly the crash site the assignment names. Remaining: `analysis/projector.py:395` (`project_fcffs`, `latest_is.revenue`) and `api/routes_upload.py:28` (backlog item 28) |
| 11 | lint | **pass** | `ruff check .` run **after my last edit**: `Found 4 errors`, every one `BLE001` — `api/routes_valuation.py:463`, `:745`, `cli.py:1315`, `tests/test_e2e_all_googl.py:106`. The two route line numbers moved by my added docstrings; same two sites |
| 12 | census | **pass, unchanged** | the grep at `docs/2-rules/rules.md:102` with `pipeline.py` added: **64**. No site added and none removed |
| 13 | route | **pass** | `TestClient(app.app, raise_server_exceptions=False).get('/')` → **200** |
| 14 | the failing test set | **pass, no test changed state** | gate form before: `1224 passed, 2 skipped, 0 failed`; after: `1224 passed, 2 skipped, 0 failed`. **Both failing sets are empty**, so the sets are equal by name. Full suite after: see Measurements |
| 15 | neither dead branch was deleted | **pass** | `grep -n 'missing.append("income statement")' cli.py api/routes_valuation.py` → `cli.py:839` and `api/routes_valuation.py:274`. `git diff` shows both as **unchanged context**; only the docstrings above them changed. Both now run — criteria 2 and 3 |
| — | write guard | **pass** | `.claude/check_guard.py` → `48/48 guard cases correct` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| **Widen `years` to the union; add `income_statement_years` beside it** (rather than leave `years` narrow and add a `covered_years`) | `years` is the name every reader reaches for, and the one the jinja templates already use thirty-six times. The honest default for "the years this object covers" is every year any statement covers | A new `covered_years` would leave the silent omission as the default: a future reader who does not think about it gets exactly the defect item 116 names, and the templates would have kept it too. Widening makes the omission impossible to get by accident; the cost is that every reader needing an income statement had to be visited, which this unit does |
| `latest_year` reads `income_statement_years` | Fact 4 of the assignment: a message that names income statements must still be true when it prints. Verified by execution, criterion 7 | Reading the wide set would make `years` non-empty while the message says there are no income statements — a false stop message — and would break `get_income_statement(latest_year)` for `pipeline.value_company`, `project_fcffs` and `analysis/dcf`, all of which follow it with that call |
| `derive_assumptions` reads the **wide** set and stops by name | Assignment step 3, rule 3. **Measured:** at HEAD the probe filing's invisible 2024 made the CAGR read 2023→2025 as ONE year of growth, giving 20.0% a year where two years of growth is 9.54%. A silent skip is not neutral; it moves a figure | Reading `income_statement_years` here would not crash, and would be wrong in exactly that way with nothing saying so. `None.revenue` is not a stop: it names no field and no year, and the blanket `except Exception` (item 8) would render it as a string on the results page |
| `cli.print_extracted_financials`: income statement table on the narrow set, cash flow table on the wide set, each year the other table omits named underneath | Every income statement row dereferences `get_income_statement(y)`; the cash flow rows already carried a `None` guard. So the cash flow figures of an income-statement-less year now print instead of being dropped, and the year is named where it has no column, in the same words both entry points use | Putting the income statement table on the wide set is `None.revenue`. Leaving both on the narrow set keeps the extracted cash flow figures invisible, which is the defect |
| `cli.py`'s balance sheet section picks the **latest balance sheet**, not the balance sheet of the latest income-statement year | Item 116 in miniature: it chose a year out of a set built from the income statements alone. At HEAD the probe filing printed `EXTRACTED BALANCE SHEET — FY2025 … No balance sheet extracted.` **with a 2024 balance sheet in hand.** It also made `print_extracted_financials` raise out of `latest_year` once `years` could be non-empty with no income statement | Keeping `latest_year` here would have turned a filing with a balance sheet and no income statement into an unhandled `ValueError` at stage 2 — the louder-failure trap the assignment names. For every filing in this repository the two years are the same one and no figure moves (criterion 8) |
| `print_normalization` reports a year it cannot reconcile instead of passing over it, and its "No adjustments applied" line is computed over the years that **were** reconciled | Symmetry with the web's `_build_ebit_reconciliation`, which already had the three named-missing branches; and the summary sentence must not assert that no adjustment applied to years whose EBIT was never read | Reading the narrow set would leave the CLI silent where the page speaks, which is backlog item 92's shape (closed by `P3c`) reopening |
| `_build_is_summary`'s default becomes `income_statement_years` | Every line it formats is read off an income statement. The two sets were the same list before this unit, so **no prompt byte moves** | Taking the wide set would drop such a year at the existing `if inc:` with no word — the defect, not a fix for it |
| Three ingestion readers (`claude_extractor.py:2628/2642/3525`, `session_extraction.py:1075`) keep reading `.years`, now wide | All four are sentences that report **what was read or merged**. Pass 1 reads all three statements and the merge merges all three, so the wide set is the truthful one; a year read and then unnamed is item 116 | Narrowing them would preserve the silence these lines exist to break |

**The twelve readers, each visited on 2026-10-07:**

| # | File | Line (now) | Set it reads | Why |
|---|---|---|---|---|
| 1 | `models/financial_statements.py` | 507 (`latest_year`), was 460 | **`income_statement_years`** | its docstring and its stop both name income statements, and three callers follow it with `get_income_statement(latest_year)`. Fact 4 |
| 2 | `analysis/projector.py` | 216 (`derive_assumptions`), was 167 | **`years`** (wide), through `_income_statements_for_years` | must not crash and must not silently skip; a covered year with no income statement stops and names `revenue` and the year |
| 3 | `api/routes_valuation.py` | 268 (`_historical_fcff_by_year`), was 261 | **`years`** (wide) | this is what makes the `income_statement is None` branch of fact 2 run |
| 4 | `api/routes_valuation.py` | 329 (`_build_ebit_reconciliation`), was 317 | **`years`** (wide), both sides | its three missing-statement branches already name what is absent; the `raw and adjusted income statement` branch is now reachable (probe section H) |
| 5 | `ingestion/claude_extractor.py` | 2319 (`_build_is_summary`), was 2309 | **`income_statement_years`** | every line it prints is read off an income statement; the wide set would drop such a year at `if inc:` with no word. The two sets were equal before this unit, so no prompt text moves |
| 6 | `ingestion/claude_extractor.py` | 2645 and 2661 (two Pass 2 stop messages), were 2628 and 2642 | **`years`** (wide) | both say "fiscal years … read in Pass 1", and Pass 1 reads all three statements |
| 7 | `ingestion/claude_extractor.py` | 3549 (the `MERGED:` print), was 3525 | **`years`** (wide) | it reports what the merge produced, so a merged year with no income statement belongs in the count and the list |
| 8 | `ingestion/session_extraction.py` | 1080 (the `Years:` summary), was 1075 | **`years`** (wide) | `check`'s summary of what the session file holds; the balance sheet years are already listed beside it |
| 9 | `cli.py` | 433–434 (`print_extracted_financials`), was 424 | **both**: `years` for the cash flow table, `income_statement_years` for the income statement table | see the decision table. Each year a table has no column for is named underneath |
| 10 | `cli.py` | 750 (`print_normalization`), was 669 | **`years`** (wide) | a year it cannot reconcile is named, in the web's words, instead of vanishing |
| 11 | `cli.py` | 822 (`print_historical_fcff`), was 721 | **`years`** (wide) | this is what makes the `is_ is None` branch of fact 2 run |
| 12 | `cli.py` | 1163–1164 (`main`, stage 1), was 1055 | **`years`** (wide), with `income_statement_years` printed beside it when they differ | the first place a reader meets the years. The narrow set is named too, because it is what the income statement table and the projection work from |

**Not a `.years` reader, checked and unaffected:** `pipeline.py:137` and `analysis/dcf.py:224` read `latest_year`, whose set did not change, so neither file is touched and `pipeline.py` stays out of the diff.

**A code change made to reach a target number is forbidden.** No change in this unit was
made to move a figure. One change was made because a figure *did* move at HEAD and should
not have: the invisible year's effect on the revenue CAGR, measured below.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| the income statement of a year in `financials.years` (`derive_assumptions`) | **stops and names `revenue` and the fiscal year** | `analysis/projector.py:_income_statements_for_years`; probe section D prints the type and the whole message |
| `financials.income_statement_years`, in `latest_year` | **stops and names the absence of income statements** | `models/financial_statements.py:latest_year`; probe section E executes it |
| the income statement of a year, in the CLI income statement table | not read for a year that has none: the table is built from `income_statement_years`, and the year is printed below as `not extracted: income statement` | probe section F |
| the cash flow statement of a year, in the CLI cash flow table | the column is blank, **and the year is named below the table** as `not extracted: cash flow statement`. The blank column is pre-existing (backlog, see Findings) | probe section F2 |
| the balance sheet, in the CLI balance sheet section | **prints `No balance sheet extracted.`** when `financials.balance_sheets` is empty; otherwise it shows the latest one that exists and labels its year | `cli.py:_print_latest_balance_sheet`; probe sections F and F2 |
| the income statement of a year, in `print_historical_fcff` / `_historical_fcff_by_year` | **a row naming `income statement`**, no figure invented | the two branches of fact 2, now reachable; probe sections B and C |
| the income statement of a year, in `_build_ebit_reconciliation` | **a record whose `missing_statement` names which side is absent** | probe section H |
| `revenue` in the session file (the figure the price is built from) | **stops**: `filings[2] (Walmart Inc._10-K_2026-01-31_English.pdf), year 2026: key 'revenue' is absent.` | `C:\tmp\p3d_filing_input.py`, run "revenue deleted" |

No "defaults to" row. I added no conditional zero, no `.get(..., 0)`, no bare `or`
default and no money field with a default; the census is unchanged at 64.

## Measurements

**Gates, Windows, `.venv/Scripts/python.exe`, Python 3.14.4, `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:**

| Gate | Before (at `f42418b`) | After |
|---|---|---|
| gate form, `-m pytest -q --ignore-glob="*_rule3_red.py"` | `1224 passed, 2 skipped, 0 failed` (225.90s) | **`1224 passed, 2 skipped, 0 failed`** (152.60s) |
| failing set, by name | **empty** | **empty** — no test changed state |
| full suite, `-m pytest -q` | 2 failed, the two red on purpose | **`2 failed, 1224 passed, 2 skipped`**, by name: `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` — the same two `STATUS.md` names |
| lint, `ruff check .` | 4, all `BLE001` | **4, all `BLE001`** |
| types | 5 errors in 2 files | **2 errors in 2 files**, 21 checked |
| census | 64 | **64** |
| route | 200 | **200** |
| write guard | 48/48 | **48/48** |

**`test_projector_rule3_red.py` stays red, and it should.** I read it, because my change
lands in the function it tests. Its input is `FinancialStatements(ticker="TEST")` — **no
statements of any kind**, so `years == []` on both trees and
`_income_statements_for_years` returns an empty list without stopping. The bare
`IndexError` at `revenues[-1 - lookback]` is still there. That is backlog item 14's twin,
a different defect from item 116, and it is out of this unit's scope. **It did not go
green, so nothing has to move out of the `*_rule3_red.py` pattern** (the trap `STATUS.md`
records at `38b903c`, backlog item 24).

**Walmart, the live run, both trees in one sitting** (`cli.py --session-file
extractions/WMT.json`, exit 0 on both). `diff` reports its first difference at line 244 of
387, so **lines 1–243 — the extraction, the statements, the non-recurring items, the
reconciliation, the historical FCFF table and the projection assumptions — are byte
identical.** Every later difference is market-sourced or a clock: current price
`108.71 → 108.72`, market cap `872,072M → 872,152M`, S&P annualised return
`11.04% → 11.05%`, WACC `7.78% → 7.79%`, implied price `$31.16 → $31.15`, and the
`(11s elapsed)`/`(7s elapsed)` stamps. That is the ±$0.01 drift the assignment names.

**Walmart with the market pinned, both trees** — this is the measurement that settles
criterion 8, because it removes the only thing that differed above.
`C:\tmp\p3d_wmt_pinned.py` replaces `pipeline.fetch_price_data` with a seeded stub (no
network), and the two runs are compared with the elapsed-time lines removed:

```
370 lines, diff empty  ->  IDENTICAL
```

Implied share price `$14.46` on both trees. **That $14.46 is a figure about this pipeline
and not about Walmart**: the market series behind it is invented. The real-market pair is
the $31.16 / $31.15 above.

**An input to that price came from the filing, and deleting it stops the run.**
`C:\tmp\p3d_filing_input.py`, against a **scratch copy**; the repository's session file
sha256 is `c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675` before and
after, unchanged.

```
as printed        Revenue  572,754 611,289 648,125 680,985 713,163   ->  $ 14.46
                  the FY2026 row: {'label': 'Total revenues', 'value': 713163, 'page': 21}
revenue halved    Revenue  572,754 611,289 648,125 680,985 356,582   ->  $-35.26
revenue deleted   SystemExit: … year 2026: key 'revenue' is absent.
```

**What the invisible year did to a figure, measured at HEAD.** This is why
`derive_assumptions` stops rather than skipping. On the probe filing (2023 revenue 1,000;
2024 with no income statement; 2025 revenue 1,200), HEAD's `years` was `[2023, 2025]`, so
`len(revenues) - 1 = 1` and the CAGR read **two** fiscal years of growth as **one**:

```
HEAD:  lookback = min(3, 1) = 1  ->  (1200/1000)^(1/1) - 1 = 20.000% a year
hand:  two years of growth       ->  (1200/1000)^(1/2) - 1 =  9.545% a year
after: ValueError naming revenue and fiscal year 2024
```

HEAD printed `revenue growth = [0.19999999999999996] * 5` with nothing anywhere saying a
year was missing from the window. **A silent skip in the projector would have kept that
number**, which is why step 3's stop is a stop.

**Scratch discipline.** No repository file was mutated for a measurement. The HEAD tree is
a `git archive` export at `C:\tmp\p3d_head`; every mutation was made to a copy under
`C:\tmp`. `git stash` was not used. The session file's sha256 is printed before and after
the mutation run, above, and is unchanged.

## What I did not do

- **`pipeline.py` is not in the diff.** No reader of `.years` sits there; its `latest_year`
  read is unaffected because that property's set did not change. The assignment allowed the
  file "only if" a reader sat there, and none does.
- **`tests/` is untouched.** This unit's tests are a separate assignment. The
  `_income_statements_for_years` stop, both newly-reachable branches, the
  `_build_ebit_reconciliation` third branch, the balance-sheet-only CLI path and the
  `income_statement_years` property are all currently exercised only by my probe, which
  lives in `C:\tmp` and is not committed.
- **`analysis/projector.py:395` (`project_fcffs`, `latest_is.revenue`) is left as it is**,
  and it is the one mypy error I did not remove. It is safe by construction —
  `latest_year` comes from `income_statement_years` — and the only ways to silence it are
  an unreachable raise or an `assert`, both of which add a line no input can reach. I
  judged a dead guard worse than a type error the checker keeps reporting.
- **The `inc and` clause in the D&A, CapEx and NWC loops of `derive_assumptions` is now
  always true**, because `_income_statements_for_years` has already proved every year has
  one. I left all three loops alone: changing them moves no figure and the assignment is
  explicit that a change not traced to a reader of `.years` is a finding. A later unit can
  simplify them.
- **I did not touch `templates/`** — it is outside my scope, and nothing needed it: the
  statements table and the historical FCFF table both render the new year correctly as
  they stand, which is itself evidence that the two template authors expected this case too.

## Findings for the orchestrator

1. **The CLI cash flow table still prints a blank column for a year with no cash flow
   statement.** I added a line naming each such year under the table, so it is no longer
   silent, but the blank column itself reads as "nothing happened" rather than "not
   extracted". It is pre-existing (`cli.py`, the seventeen `if financials.get_cash_flow(y)
   else " " * col` expressions) and it is seventeen copies of one decision. The web's
   equivalent prints the words `not extracted` in the cell. Worth a unit of its own; it is
   also seventeen instances of the conditional-expression shape the census grep cannot see
   (backlog item 71's neighbourhood).
2. **`_build_is_summary`'s `target_years or financials.income_statement_years` is a bare
   `or` default.** An empty list supplied by the caller falls through to the whole filing's
   years, which is not the same request. The census grep does not match it because the
   right-hand side is not `0`. Pre-existing; I left it, since changing it is not traced to
   a reader of `.years`.
3. **A year reached only by a balance sheet now stops the valuation where it used to be
   dropped.** That is the rule 3 answer and I believe it is right, but it is a live
   behaviour change for any future filing of that shape: `derive_assumptions` stops instead
   of valuing the company off the years it could see. Nothing in this repository is of that
   shape today — `extractions/WMT.json` has `years == income_statement_years` — so no
   current input is affected. Worth stating in `STATUS.md` when this lands.
4. **`templates/_statements.html:295` calls `financials.latest_year` inside a `{% set %}`.**
   For a filing with no income statement at all that raises `ValueError` through jinja, and
   the blanket `except Exception` (item 8) renders it as a string. My change does not create
   this — `latest_year` raised on that filing before too — but widening `years` makes such a
   filing reach the template with a non-empty year list for the first time, so the path is
   now easier to hit. `templates/` was outside my scope. The CLI's equivalent is fixed here
   (`_print_latest_balance_sheet`); the page's is not.
5. **Backlog item 41** (`analysis/projector.py`'s unreachable `0.05` growth rate) is still
   unreachable after this unit, and still the cheapest hit in item 1's census.
