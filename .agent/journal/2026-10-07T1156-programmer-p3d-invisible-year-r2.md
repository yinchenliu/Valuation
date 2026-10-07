---
agent: programmer
assignment: P3d-invisible-year
round: 2
status: complete
files_touched: [cli.py, ingestion/claude_extractor.py]
---

# P3d-invisible-year round 2 — the net-margin conditional zero, and F2 to F5

> Opened before the first command of round 2 and filled as each result landed.

## What I did

Round 1's design was approved and is untouched. This round answers the five review
findings and nothing else. **F1** (`major`, the only blocking one): `cli.py`'s net-margin
row carried `… .net_income / … .revenue if … .revenue else 0` into a function this unit
wrote, so a year with zero revenue printed a fabricated `0.0%`. The cell is now blank and
the year is named under the table as `not computable: net income margin, revenue is 0`.
**Per the overall lead's ruling I did not touch `models/financial_statements.py:108` or
`:132`**, so `Gross Margin` and `EBIT Margin` still print `0.0%` for the same year; the
ruling records that as accepted on purpose. **F2**: `target_years or …` became
`target_years if target_years is not None else …` after I read every caller and found
none that passes an empty list. **F3**: when the balance sheet the CLI shows is not
`latest_year`'s, a line under the heading now says which year the valuation's net debt and
capital weights came from. **F4**: I made the words identical rather than softening the
comment — the CLI reconciliation now prints the web's four-case phrase behind the web's
`not extracted:`. **F5**: left, as the ruling directs. Two files changed, `cli.py` and
`ingestion/claude_extractor.py`. Walmart does not move: with the market pinned, 370 lines,
`diff` empty, `$15.42` on both trees.

## Findings answered, by number

| # | Severity | What I did | Evidence |
|---|---|---|---|
| **F1** | `major`, blocking | **Fixed, in `cli.py` and nowhere else.** The relocated row calls a new `_net_margin_cell(income, w)` (`cli.py:420`), which returns a blank cell when `revenue == 0` and `_pct(net_income / revenue, w)` otherwise. `_print_net_margin_absences` (`cli.py:547`), called from `print_extracted_financials`, then names each such year under the table. No `raise` — a table that raises prints nothing at all | Probe section F1 on both trees. **HEAD:** `  Margin   30.0%   0.0%` for a 2024 whose revenue is 0, and **no line anywhere names it**. **After:** `  Margin   30.0%` then ten blanks, and under the table `  2024  not computable: net income margin, revenue is 0`. `C:\tmp\p3dr2_probe_head.txt` against `C:\tmp\p3dr2_probe_after.txt`, section F1 |
| **F2** | `minor` | **Fixed, after reading every caller.** `ingestion/claude_extractor.py:2329` is now `target_years if target_years is not None else financials.income_statement_years`. **No current caller passes an empty list** — see the caller walk below | Probe section F2. **HEAD and round 1:** `_build_is_summary(f, [])` returns both years of the whole filing. **After:** `'  (no data available)'`. `_build_is_summary(f, None)` and `(f, [2023])` are byte-identical on both trees |
| **F3** | `minor` | **Fixed.** `_print_latest_balance_sheet` prints one line under the heading when the sheet it shows is not the one the valuation reads. It compares against `income_statement_years`, the set `latest_year` itself reads, rather than calling `latest_year` — that property raises for a filing with no income statement, and such a filing is already told it has none | Probe section F3, the `LATEBS` filing (balance sheets 2025 and 2026, income statements 2024 and 2025): `EXTRACTED BALANCE SHEET — FY2026 ($M)` then `Shown: FY2026, the latest balance sheet extracted. The valuation below reads FY2025's balance sheet — the latest year with an income statement — for net debt and the capital weights, so the two are different sheets.` Not printed for Walmart, where both years are 2026 |
| **F4** | `note` | **I made the words identical, not the comment softer.** The CLI reconciliation builds the web's four-case phrase and prints it behind the web's `not extracted:`. The comment at `cli.py:822-841` now states the old wording, the new wording and the reason | Probe sections F4 and F4b, CLI beside web, same filing, same year. CLI `2024: not extracted: raw and adjusted income statement`; the production template block rendered out of `templates/_statements.html` gives `<td colspan="3" class="num">not extracted: raw and adjusted income statement</td>`. One-sided: CLI `2023: not extracted: adjusted income statement`, web `missing_statement='adjusted income statement'` |
| **F5** | `note` | **Left, as the ruling directs** ("Leave it. I record it. Do not widen your diff for it") | Probe section E, `BSONLY`: `No income statement extracted for any year.` is still followed by `2024  not extracted: income statement`. Unchanged from round 1 |

**F2's caller walk, which the ruling asked for by name.** `_build_is_summary` has one
caller, `_pass2_prompt_pair` (`:2393`). That has two: `_run_nri_pass` (`:2600`) and the
public `pass2_prompts` (`:3086`). `pass2_prompts` passes `_plan_target_years(plan)`.
`_run_nri_pass` receives `extract_financials`'s `target_years`, which is `None` by default
and is passed by `extract_multi_year` as `_plan_target_years(plan)`; `cli.py:1042/1057` and
`api/routes_valuation.py:120/127`, the four production call sites of the two public
functions, pass it at all. `_plan_target_years` returns `None` or
`list(plan.target_years)`, and `plan_filings` is the only producer of a `FilingPlan` in
this repository (`claude_extractor.py:2788`; `session_extraction.py:396` and `:875` both
call it) — it sets `target_years` to `None` or to a **one-element** tuple `(fiscal_year,)`.
**So no caller passes an empty list, and this changes what no current caller receives.**

## Done-criteria

Re-run **after my last edit**, which was the `w + 1` blank width in `_net_margin_cell`.
The repository's `cli.py` sha256 is `f87e2915…` for every measurement below.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the old behaviour is reproduced first | **pass** | `git archive HEAD` into `C:\tmp\p3dr2_head`; **no `git stash`**. `C:\tmp\p3dr2_probe.py` there: `years = [2023, 2025]`, `income_statement_years` **absent**, 2024 in no CLI FCFF row, no web row, no statements table and no reconciliation line. `C:\tmp\p3dr2_render.py` rendering the **production** blocks out of `templates/_statements.html`: `years in the rendered rows : [2023, 2025]`, `'not extracted' cells : 0`, reconciliation rows `2023` and `2025` only |
| 2 | the year is visible in the CLI | **pass** | `print_historical_fcff` on the working tree: `  2024  not extracted: income statement`. Probe section B2 |
| 3 | the year is visible on the web page | **pass** | `_historical_fcff_by_year` gives `row year=2024 computable=False missing=('income statement',)`; the production template block renders `years in the rendered rows : [2023, 2024, 2025]` and **6** `not extracted` cells against HEAD's 0. `C:\tmp\p3dr2_render_after.txt`. **No template was edited** |
| 4 | both entry points say the same thing | **pass** | CLI `not extracted: income statement`, web `not extracted: income statement`. **And now the reconciliation too**, which round 1 left different — F4 |
| 5 | the projection refuses it **by name** | **pass** | Probe section D: `type: ValueError`, message names `revenue`, fiscal year 2024, both year sets and the remedy. **Not an `AttributeError`.** At HEAD the same call returned assumptions with no stop |
| 6 | every reader is visited | **pass** | the table under "Decisions". **Twelve rows plus one new reader this round created** (`cli.py:647`), each with its line, its set and its reason. Enumerated by `grep -rn "\.years\b\|income_statement_years" --include=*.py . | grep -v "^./tests/"` |
| 7 | `latest_year`'s message is true when it prints | **pass** | Probe section E: `years = [2024]` (non-empty; `[]` at HEAD) and `ValueError: FinancialStatements for 'BSONLY' holds no income statements, so there is no latest year.` — true, because the property reads the narrow set |
| 8 | **Walmart does not move** | **pass** | `C:\tmp\p3dr2_wmt_pinned.py`, my own runner, `pipeline.fetch_price_data` replaced by a seeded stub, **no network**, one session-file path outside both trees so the provenance sentence wraps identically. Both trees: **370 lines, `diff` empty**, implied share price **$15.42** on each. The live pair in one sitting is below |
| 9 | no figure moves where every year has an income statement | **pass** | criterion 8 on `extractions/WMT.json` (five fiscal years, `years == income_statement_years`), plus the probe filing's 2023 and 2025 FCFF rows, identical in `p3dr2_probe_head.txt` and `p3dr2_probe_after.txt` (section G) |
| 10 | types | **pass, 3 fewer than the 5 the assignment allows** | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → **`Found 2 errors in 2 files (checked 21 source files)`**: `analysis/projector.py:395` and `api/routes_upload.py:28`. Unmoved from round 1; `cli.py` is not in this gate's file list |
| 11 | lint | **pass** | `-m ruff check .` run after my last edit → **`Found 4 errors`**, every one `BLE001`: `api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106`. `cli.py:1315 → :1411` is the same site, moved by my added docstrings |
| 12 | census | **pass, unchanged** | the grep at `docs/2-rules/rules.md:102`, with `pipeline.py` added: **64** on the working tree and **64** on the HEAD tree. **F1 removed a conditional zero the grep cannot see** — `cli.py` is outside the grep's four directories, as `STATUS.md` records for item 72 — so the figure does not move |
| 13 | route | **pass** | `TestClient(app.app, raise_server_exceptions=False).get('/')` → **200** |
| 14 | the failing test set | **pass, no test changed state** | gate form on the working tree: **`1224 passed, 2 skipped, 2 warnings in 175.65s`**, failing set **empty**. Full suite: **`2 failed, 1224 passed, 2 skipped`**, by name `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` — the two `STATUS.md` names, and the two red on purpose. Compared **by name**, never by count. **HEAD scratch tree, my own run: `1222 passed, 4 skipped, 0 failed`, failing set also empty.** The 2 passed/skipped difference is that tree lacking `10K_filings/`, which is not in git — not a state change |
| 15 | neither dead branch was deleted | **pass** | `grep -n 'missing.append("income statement")' cli.py api/routes_valuation.py` → `cli.py:935`, `api/routes_valuation.py:274`. `git diff -U0` matches **neither** as an added or a deleted line, so both are unchanged context. Both run: probe sections B2 and C |
| — | write guard | **pass** | `.claude/check_guard.py` → `48/48 guard cases correct` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| **F1's cell is blank, and the reason goes on a line under the table** | The ruling: "Use the same vocabulary this unit already established for a figure that is not there". This file's established shape for a cell it has no figure for is exactly that — `_print_cash_flow_table` prints `" " * col` and the caller names the year below. A blank invents no figure, which is what the round 1 reviewer itself said of the cash flow blanks | The reviewer's literal suggestion, `"not computable: revenue is 0"` padded to `col`, is **29 characters in a 10-character column**: it would push every later cell of that row out of line. Its words are kept, on the line under the table where they fit |
| **The blank is `w + 1` characters, not `w`** | `_pct` emits `w` characters of number and then the `%` sign, so a `w`-wide blank pulls every later column of that one row a character left. Measured: probe section F1b puts a zero-revenue 2023 **between** 2022 and 2024, and `31.7%` in the net-margin row sits under `31.7%` in the EBIT-margin row | A `w`-wide blank looked right in the first probe only because the zero year was the last column |
| **I did not touch `models/financial_statements.py:108` or `:132`** | The overall lead's ruling, 2026-10-07, with its two facts: `templates/_statements.html:44` and `:86` render the same two properties, and `templates/` is out of scope (fact A); `analysis/projector.py` reads `operating_margin` into the DCF, so changing it moves a figure and needs its own tests (fact B) | Repairing them here would make the CLI and the page disagree about one cell — the repository's third standing trap — or move the share price inside a display repair. **What the table now prints for a zero-revenue year: `Gross Profit` margin `0.0%`, `EBIT` margin `0.0%`, net income `  Margin` blank, with the reason named below.** The ruling accepts that difference on purpose |
| **F1 reports instead of raising** | The ruling: "Do not raise out of a table build: a table that raises prints nothing at all, and the reader loses the twelve rows that were fine" | A stop belongs where the figure is consumed (`derive_assumptions` has one), not where it is displayed |
| **F4: identical words, not a softened comment** | `docs/9-reference/severity.md` ranks a silent divergence between the two entry points above a stale comment, and backlog item 92 (closed by `P3c`) is exactly that defect: the CLI and the page showing different things for one filing. Criterion 4 of this assignment exists for the same reason | Softening the comment to "for the same reason" would have left the CLI saying `not reconciled: raw income statement, adjusted income statement` where the page says `not extracted: raw and adjusted income statement`, and recorded the drift instead of removing it |
| **F4 changes `not reconciled:` to `not extracted:` as well as the phrase** | The ruling says "make the words identical". The web's full cell is `not extracted: {{ row.missing_statement }}` (`templates/_statements.html:455`), so identical means the whole line, not half of it. It also makes one vocabulary across the whole CLI run: every absence this unit reports now reads `not extracted: …` or `not computable: …` | Changing the phrase alone would leave two different prefixes for one cell, which is the drift in miniature |
| **F3 compares against `income_statement_years`, not `financials.latest_year`** | It is the set `latest_year` itself reads (`models/financial_statements.py:507`), so the comparison is the property's own comparison, and it does not raise for a filing with no income statement | Calling `latest_year` here would need a `try/except ValueError` around a display line, and for a filing with no income statement would have to print a third sentence saying what the table above has already said twice (F5) |
| **F2 is fixed rather than left** | The ruling: "If none does, fix the shape." No caller passes an empty list — the walk is above, and every `FilingPlan` in this repository comes from `plan_filings`, which produces `None` or a one-element tuple | Leaving it would keep a bare `or` that reads a caller's "no years" as "every year" on a line this unit had already edited |

**A code change made to reach a target number is forbidden.** No change in this round was
made to move a figure, and none moved one: Walmart is byte-identical across the two trees
under a pinned market series.

## Rule 3 — what stops, and what does not

Round 2's rows. Round 1's table stands and is not repeated.

| Value read | If it were missing | Evidence |
|---|---|---|
| `net_income / revenue` in the CLI income statement table, when `revenue` is 0 | **reports a named absence**: the cell is blank, and `  {year}  not computable: net income margin, revenue is 0` prints under the table. No figure is invented | `cli.py:_net_margin_cell` and `_print_net_margin_absences`; probe section F1, both trees |
| `gross_margin` and `operating_margin` in the same two rows, when `revenue` is 0 | **defaults to `0.0`, so the table prints `0.0%`** | `models/financial_statements.py:108` and `:132`. **A "defaults to" row against this unit's output, and it stays** on the overall lead's ruling of 2026-10-07, which names `templates/_statements.html:44`/`:86` and `analysis/projector.py` as the reasons and records it in the backlog (item 1) |
| `target_years` in `_build_is_summary`, when the caller supplies `[]` | **means "no year"**, which gives `  (no data available)`, not the whole filing | `ingestion/claude_extractor.py:2329`; probe section F2 |
| the year of the balance sheet the valuation reads, in the CLI balance sheet section | **named on the line** whenever it is not the year shown | `cli.py:_print_latest_balance_sheet`; probe section F3 |
| which side of the reconciliation has no income statement | **named, in the web's four-case vocabulary** | `cli.py:print_normalization`; probe sections F4 and F4b beside the rendered template |
| `revenue` in the session file, the figure the Walmart price is built from | **stops**: `filings[2] (Walmart Inc._10-K_2026-01-31_English.pdf), year 2026: key 'revenue' is absent.` | `C:\tmp\p3dr2_filing_input.py`, run "deleted", exit 1 |

**No new "defaults to" row is this round's own**: the census is 64 on both trees, and the
one `0.0` row above is the backlog item the ruling explicitly leaves.

**One warning for the reviewer's grep.** `git diff -U0 -- cli.py ingestion/claude_extractor.py |
grep "^+" | grep -E "else 0|\.get\([^,]+, *0\)|\bor +0|float = 0\.0|kwargs|getattr\("`
returns **two added lines**, and both are **docstring text quoting the defect**, not code:
`read \`… .net_income / … .revenue if … .revenue else 0\` until round 2 of` and
``same `if self.revenue else 0.0` at `models/financial_statements.py:108` ``. The first
records what the F1 cell used to be; the second records why the two rows above it are
left. **No executable line this round adds matches any rule 3 shape.**

## Measurements

**Gates, Windows, `.venv/Scripts/python.exe`, Python 3.14.4, `ANTHROPIC_API_KEY=
GEMINI_API_KEY=`, every one run after the last edit:**

| Gate | HEAD (`f42418b`) | After round 2 |
|---|---|---|
| gate form, `-m pytest -q --ignore-glob="*_rule3_red.py"` | **my own run on `C:\tmp\p3dr2_head`: `1222 passed, 4 skipped, 0 failed`** (138.80s) | **`1224 passed, 2 skipped, 0 failed`** (175.65s) |
| failing set, by name | **empty** (`grep -c "^FAILED"` → 0) | **empty** — no test changed state |
| full suite, `-m pytest -q` | 2 failed, the two red on purpose | **`2 failed, 1224 passed, 2 skipped`**, the same two by name |
| lint, `-m ruff check .` | 4, all `BLE001` | **4, all `BLE001`** |
| types | 5 errors in 2 files | **2 errors in 2 files**, 21 checked |
| census | 64 | **64** |
| route | 200 | **200** |
| write guard | 48/48 | **48/48** |

**Walmart with the market pinned, both trees.** `C:\tmp\p3dr2_wmt_pinned.py` replaces
`pipeline.fetch_price_data` with a seeded stub (`default_rng(20261007)`, 60 monthly
observations, `current_price=100.0`), so no network call is made and the market series is
the same on both runs. Both runs read **one** session file, `C:\tmp\p3dr2_wmt\WMT.json`,
outside both trees: the provenance sentence prints the file's absolute path and wraps at a
fixed width, so two scratch directory names of different lengths rewrap it and the diff
reports a text difference that is not a figure.

```
370 lines, diff empty  ->  IDENTICAL
Implied Share Price:  $ 15.42   on both trees
```

**That $15.42 is a figure about this pipeline and not about Walmart**: the market series
behind it is invented.

**Walmart live, both trees in one sitting** (`cli.py --session-file …`, exit 0 on both).
Implied share price **$30.86 on both**. `diff` with the elapsed lines stripped reports
**six** differences and every one is market-sourced or a clock: current price
`108.17 → 108.18`, market cap `867,700M → 867,780M`, total capital
`919,223M → 919,303M`, terminal value `337,734M → 337,735M`, PV of terminal value
`231,699M → 231,700M`, and `Done in 11s → 7s`. **Lines 1–283 are byte-identical** — the
extraction, the statements, the non-recurring items, the reconciliation, the historical
FCFF table and the projection assumptions. That is the ±$0.01 market drift the assignment
names, and here it did not even reach the cent of the headline figure.

**An input to that price came from the filing, and deleting it stops the run.**
`C:\tmp\p3dr2_filing_input.py`, against **scratch copies** under `C:\tmp\p3dr2_mut`:

```
the FY2026 revenue row as printed: {'label': 'Total revenues', 'value': 713163, 'page': 21}

printed   exit=0  Implied Share Price:  $  15.42
halved    exit=0  Implied Share Price:  $ -36.41
deleted   exit=1  … filings[2] (Walmart Inc._10-K_2026-01-31_English.pdf), year 2026:
                  key 'revenue' is absent. Write [] only for a row the filing does not print.
```

**The column alignment of the blank cell, measured rather than eyeballed.** Probe section
F1b builds a filing whose **middle** year has zero revenue:

```
EBIT
  Margin                30.0%       0.0%      31.7%
Net Income               300         0       380
  Margin                30.0%                 31.7%
  2023  not computable: net income margin, revenue is 0
```

`31.7%` in the net-margin row sits under `31.7%` in the EBIT-margin row. With a `w`-wide
blank it sat one character to the left.

**Scratch discipline.** No repository file was mutated for a measurement. The HEAD tree is
a `git archive HEAD` export at `C:\tmp\p3dr2_head`; the working-tree copy is
`C:\tmp\p3dr2_after`, built from `git ls-files` and verified sha256-equal to the
repository for all seven source files. **`git stash` was not used.** The repository's
sha256 before and after every measurement (`C:\tmp\p3dr2_sha_before.txt` against
`C:\tmp\p3dr2_sha_after.txt`): `models/financial_statements.py`, `analysis/projector.py`,
`api/routes_valuation.py`, `ingestion/session_extraction.py`, `pipeline.py` and
`extractions/WMT.json` (`c436e427…`) **unchanged**; `ingestion/claude_extractor.py`
unchanged after its F2 edit; `cli.py` moved once, by my own `w + 1` edit, which is the
last code edit of this round and precedes every gate above.

**The twelve readers, re-checked after round 2 with their new line numbers.** The sets are
round 1's and none moved; the enumeration is
`grep -rn "\.years\b\|income_statement_years" --include=*.py . | grep -v "^./tests/"`.

| # | File | Line (now) | Set it reads | Changed in round 2? |
|---|---|---|---|---|
| 1 | `models/financial_statements.py` | 507 (`latest_year`) | `income_statement_years` | no |
| 2 | `analysis/projector.py` | 216 (`derive_assumptions`) | `years` (wide) | no |
| 3 | `api/routes_valuation.py` | 268 (`_historical_fcff_by_year`) | `years` (wide) | no |
| 4 | `api/routes_valuation.py` | 329 (`_build_ebit_reconciliation`) | `years` (wide), both sides | no |
| 5 | `ingestion/claude_extractor.py` | 2329 (`_build_is_summary`) | `income_statement_years` | **the set is the same; the `or` became `is not None`** — F2 |
| 6 | `ingestion/claude_extractor.py` | 2655 and 2671 (two Pass 2 stops) | `years` (wide) | no |
| 7 | `ingestion/claude_extractor.py` | 3559 (the `MERGED:` print) | `years` (wide) | no |
| 8 | `ingestion/session_extraction.py` | 1080 (the `Years:` summary) | `years` (wide) | no |
| 9 | `cli.py` | 464–465 (`print_extracted_financials`) | both | **the income statement table now also names each zero-revenue year** — F1 |
| 10 | `cli.py` | 845 (`print_normalization`) | `years` (wide) | **the missing-statement phrase is now the web's** — F4 |
| 11 | `cli.py` | 918 (`print_historical_fcff`) | `years` (wide) | no |
| 12 | `cli.py` | 1259–1260 (`main`, stage 1) | `years` (wide), with the narrow set beside it | no |
| **13** | `cli.py` | **647** (`_print_latest_balance_sheet`) | **`income_statement_years`** | **new this round.** F3 added it: the set `latest_year` reads, used to decide whether the sheet shown is the sheet the valuation uses |

## What I did not do

- **`models/financial_statements.py:108` and `:132` are untouched**, on the overall lead's
  ruling. So is every other file round 1 changed: `models/financial_statements.py`,
  `analysis/projector.py`, `api/routes_valuation.py` and `ingestion/session_extraction.py`
  were not written this round, and each carries the same sha256 in
  `C:\tmp\p3dr2_sha_before.txt` and `C:\tmp\p3dr2_sha_after.txt`, so their part of
  `git diff` against `HEAD` is round 1's unaltered. Round 2's diff is two files.
- **F5 is left**, as the ruling directs.
- **`templates/` is untouched.** The render in criteria 1 and 3 reads the production block
  out of `templates/_statements.html` and renders it; it writes nothing.
- **`tests/` is untouched.** The write guard denies it, and this unit's tests are a separate
  assignment. `_net_margin_cell`, `_print_net_margin_absences`, the F3 divergence line and
  the F4 four-case phrase are exercised only by `C:\tmp\p3dr2_probe.py`, which is not
  committed.
- **I did not dispute any finding.** All five are answered as ruled.
- **`ingestion/claude_extractor.py:2280` and `:2358` still read `if target_years:`**, the
  same falsy test F2 names, in `_build_financials_prompt` and `_build_nri_prompt`. Neither
  line is in this unit's diff and neither is traced to a reader of `.years`, so I left both
  — see Findings.

## Findings for the orchestrator

1. **The `if target_years:` shape survives at two more sites F2 did not cover.**
   `ingestion/claude_extractor.py:2280` (`_build_financials_prompt`) and `:2358`
   (`_build_nri_prompt`) both read a caller's empty list as "not supplied" and omit the
   year-restriction sentence from the prompt. With F2 fixed, an empty `target_years` now
   gives Pass 2 a summary saying `(no data available)` while the prompt beside it does not
   say which years were asked for — the two halves of one prompt would disagree. **No
   caller passes an empty list today** (the walk is above), so nothing is live. One unit,
   three lines, and it should take all three together.
2. **Round 1's finding 1 stands: the CLI cash flow table still prints a blank column** for
   a year with no cash flow statement, seventeen copies of
   `… if financials.get_cash_flow(y) else " " * col`. F1 has now put a **second** kind of
   blank cell in the statements block, one that means "the statement is here and this one
   ratio is not". Both are named under their table, so neither is silent, but a reader now
   meets two blanks with two meanings. If a unit ever replaces the cash flow blanks with
   words, it should give the net-margin cell the same words.
3. **The three margin rows of the CLI income statement table now disagree about what a
   zero-revenue year is.** `Gross Margin` and `EBIT Margin` print `0.0%`; net `Margin` is
   blank with its reason named. This is the ruling's accepted partial repair, recorded here
   so the census unit for backlog item 1 can close it together with
   `templates/_statements.html:44` and `:86`, which print the same fabricated `0.0%` on the
   web page today.
4. **Round 1's findings 3, 4 and 5 are unchanged** and still want an owner: a year reached
   only by a balance sheet now stops `derive_assumptions` where it used to be dropped (a
   live behaviour change for a filing shape nothing in this repository has today);
   `templates/_statements.html:295` calls `latest_year` inside a `{% set %}` and raises
   through jinja for a filing with no income statement; and backlog item 41's unreachable
   `0.05` is still the cheapest hit in item 1's census.
