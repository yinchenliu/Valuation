---
agent: tester
assignment: P3d-invisible-year-tests
round: 1
status: complete
files_touched: [tests/unit/test_p3d_invisible_year.py]
verdict: pass
---

# P3d-invisible-year tests — a year any statement covers is visible, and the branch written to report it runs

> Opened before the first command and filled as each result landed.

## What I did

One new file, `tests/unit/test_p3d_invisible_year.py`: **28 test functions, 33
collected, 101 assertions, 0 of them taken from the code's output.** It builds the
probe filing the unit exists for — 2023 and 2025 complete, 2024 with a balance
sheet and a cash flow statement and **no income statement** — in the repository
rather than in `C:\tmp`, and locks the property pair, the stop by name, both
newly-reachable branches in **both** entry points, the words the two entry points
share, `latest_year`'s message, the blank net-margin cell with its absence line,
and the historical FCFF figures and derived assumptions of a filing whose years
all have an income statement. **Seven mutations were applied to seven separate
scratch trees under `C:\tmp` and every one was killed; none survived.** Coverage
of what the unit added is **78 of 78 added executable statements, 0 missed, 0
partial branches**, measured with `--cov-branch` intersected with `git diff -U0`
and not estimated. No repository file outside `tests/` was written: the sha256 of
all six implementation files is identical before and after (below). `git stash`
was not used.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | every expected value hand-sourced | **pass** | **101 assertions; 0 came from the code's output.** The table under "Expected values" gives the source of each. The only figures in the file are the fixture's own inputs, arithmetic over them, and widths read off a format string |
| 2 | the three hand-derived numbers | **pass** | the CAGR pair, the cell width and the unchanged FCFF figures are derived below, with the arithmetic and not the printed result |
| 3 | the property pair is covered | **pass** | `test_years_is_the_union_of_all_three_statement_kinds`, `test_income_statement_years_holds_only_the_years_with_an_income_statement`, `test_income_statement_years_is_a_subset_of_years_and_here_a_strict_one`, `test_get_income_statement_is_none_exactly_for_a_year_in_the_wide_set_alone` |
| 4 | the stop names the field and the year | **pass** | `test_derive_assumptions_stops_and_names_the_field_and_the_fiscal_year` asserts `excinfo.type is ValueError` **and** that the message holds `revenue`, `2024`, `[2023, 2024, 2025]` and `[2023, 2025]`. Not an `AttributeError`: the type is asserted identically, not by `isinstance` |
| 5 | both dead branches, in both entry points | **pass** | CLI: `test_the_cli_fcff_table_prints_a_row_for_the_year_with_no_income_statement`. Web: `test_the_web_fcff_rows_hold_a_row_for_the_year_with_no_income_statement`. Coverage confirms `cli.py:934-935` and `api/routes_valuation.py:273-274` both **EXECUTED** (`C:\tmp\p3dt_cov_intersect2.py`) |
| 6 | the two entry points say the same words | **pass** | `test_both_entry_points_name_the_missing_income_statement_in_the_same_words` (FCFF row) and `test_both_entry_points_name_an_unreconciled_year_in_the_same_words` over all three missing-statement cases. Mutation F (the CLI phrase back to round 1's comma-join) turns both red |
| 7 | `latest_year`'s message is true when it prints | **pass** | `test_latest_year_stops_for_a_filing_with_a_balance_sheet_and_no_income_statement`: `years == [2024]` (non-empty), `income_statement_years == []`, `ValueError` naming `BSONLY` and `no income statements`. The claim is checked as a claim, against the same object |
| 8 | the cell and its absence line are covered as a pair | **pass** | `test_the_income_statement_table_and_its_absence_line_are_printed_as_a_pair` runs `print_extracted_financials` **once** and asserts both halves of that one output. Mutation E (the table printed without `_print_net_margin_absences`) turns it red, which is reviewer finding N1 made testable |
| 9 | no figure moves for a filing whose years all have an income statement | **pass** | `test_the_web_fcff_figures_of_a_complete_filing`, `test_the_cli_fcff_figures_of_a_complete_filing`, `test_the_derived_assumptions_of_a_complete_filing`, `test_the_invisible_year_moves_no_figure_of_the_years_around_it`. Every figure hand-sourced |
| 10 | four mutations, each killed | **pass, seven applied, seven killed, none survived** | the table under "Mutations" |
| 11 | coverage of what the unit added | **pass** | **78 of 78 added executable statements covered, 0 missed, 0 partial branches** on added lines, over all six changed files. `--cov-branch` JSON intersected with `git diff -U0` by `C:\tmp\p3dt_cov_intersect2.py` |
| 12 | the gate | **pass** | `-m pytest -q --ignore-glob="*_rule3_red.py"` → **`1257 passed, 2 skipped`, 0 failed** (137.44s), run **after my last write**. 1257 = the assignment's 1224 + my 33 |
| 13 | the failing set, by name | **pass, unchanged** | gate form: failing set **empty**, as before. Full suite: `2 failed, 1257 passed, 2 skipped`, by name `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` — the two `STATUS.md` names, compared by name and never by count |
| 14 | lint | **pass** | `-m ruff check .` run **after my last write** → **`Found 4 errors`**, every one `BLE001`: `api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106`. An earlier run found a **fifth**, `B018` in my own file at `:514` (`financials.latest_year` read bare inside `pytest.raises`); I bound it to `_` and re-ran lint afterwards. That is criterion 14's own history and it nearly repeated |
| 15 | the write guard | **pass** | `.claude/check_guard.py` → `48/48 guard cases correct` |

**The "verify, do not redo" table agrees on every row.** gate `1224 + 33`; full
suite 2 failed, the two by name; lint 4 `BLE001`; types `Found 2 errors in 2 files
(checked 21 source files)` — `analysis/projector.py:395` and
`api/routes_upload.py:28`; census `64`; route `200`; guard `48/48`. **No
disagreement to report.**

## The three hand-derived numbers

**1. The CAGR the invisible year distorted.** The probe filing's revenue is 1,000
in 2023 and 1,200 in 2025, which is **two** fiscal years apart.

```
two years of growth : (1200/1000) ** (1/2) - 1 = sqrt(1.2) - 1 = 0.09544511501033215   ->  9.5445% a year
one year of growth  : (1200/1000) ** (1/1) - 1 =                 0.2                   -> 20.0000% a year
```

**The code must refuse to produce the 20.0000%.** That is the figure a window
holding only the two endpoints gives, and before this unit 2024 was in no year
list, so `lookback` was `min(3, 2 - 1) = 1` and the CAGR read two years of growth
as one. It must refuse the 9.5445% too, because 2024's revenue is not in the
filing and neither figure is a measurement of this company — so it stops rather
than choosing between them.

The arithmetic was done before the code ran. It was then corroborated
independently: under mutation B (the projector skipping the year instead of
stopping) the code produced `revenue_growth_rates=[0.19999999999999996] * 5`,
which is my 0.2 to within one ulp. That is corroboration of a figure I had
already derived, not its source.

**2. The column at which the blank net-margin cell starts.** From the format
string at `cli.py:417`, not from a printed row:

```
_pct(v, w)  ==  f"{v * 100:>{w}.1f}%"     ->  w characters of number, then one '%'
                                          ->  a computed cell is w + 1 characters
```

At `col = 10` a cell is **11** characters. The label column is 18 (`cli.py:471`),
so the three cells of a three-year row start at **18, 29 and 40**. A blank of `w`
would pull every later column of that one row one character left.
`test_a_zero_revenue_year_in_the_middle_does_not_shift_the_later_columns` asserts
those three positions **and** the identity against a twin filing whose middle year
has revenue, so it does not depend on the constants staying 10 and 18.

**3. Every figure of the historical FCFF rows, which must not move.**
`FCFF = CFO + |interest| * (1 - t) - |CapEx|` (`analysis/fcff.py:81`), with `t` the
effective tax rate. The fixture's effective tax rate is `30/150 = 33/165 =
36/180 = 0.20` in all three years, so `1 - t = 0.8`:

```
2023  CFO 120 + 100 = 220 ; 50 * 0.8 = 40 ; CapEx 60  ->  220 + 40 - 60 = 200 ; 200/1000 = 20.0%
2024  CFO 132 + 110 = 242 ; 55 * 0.8 = 44 ; CapEx 66  ->  242 + 44 - 66 = 220 ; 220/1100 = 20.0%
2025  CFO 144 + 120 = 264 ; 60 * 0.8 = 48 ; CapEx 72  ->  264 + 48 - 72 = 240 ; 240/1200 = 20.0%
```

and the derived assumptions of the same filing:

```
revenue growth   window = min(3, 3 - 1) = 2 years, 1,000 -> 1,200 : sqrt(1.2) - 1 = 0.0954451150103...
operating margin 200/1000 = 220/1100 = 240/1200 = 0.20, mean of three = 0.20
tax rate         0.20, inside the [0%, 50%] band, so the clamp does not move it
D&A / revenue    100/1000 = 110/1100 = 120/1200 = 0.10
CapEx / revenue   60/1000 =  66/1100 =  72/1200 = 0.06
NWC / revenue    no working-capital change in any year; the plain mean of three zeros = 0.00
```

## Expected values — every assertion's source

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `years` of the probe filing | `[2023, 2024, 2025]` | hand-enumerated from the fixture: income {2023, 2025} ∪ balance {2023, 2024, 2025} ∪ cash flow {2023, 2024, 2025} |
| `income_statement_years` of the probe filing | `[2023, 2025]` | hand-enumerated: the fixture builds income statements for those two years |
| `income_statement_years ⊆ years`, and the difference is `{2024}` | subset, strict | closed-form identity (a year with an income statement is a year some statement covers), plus the hand-enumerated difference that keeps it from being vacuous |
| `get_income_statement(y)` for every narrow year / for 2024 | a statement / `None` | the contract `income_statement_years`' docstring states; hand-enumerated from the fixture |
| `get_cash_flow(2024)`, `get_balance_sheet(2024)` | not `None` | hand-enumerated: 2024 **is** covered, which is what makes it the item-116 case |
| `derive_assumptions(probe)` raises | `ValueError`, naming `revenue`, `2024`, `[2023, 2024, 2025]`, `[2023, 2025]` | rule 3 as the assignment states it (`.agent/assignments/P3d-invisible-year.md`, step 3), plus the two hand-enumerated year sets |
| `derive_assumptions(probe)` never returns a growth rate | neither 20.0000% nor 9.5445% | hand arithmetic, number 1 above |
| `derive_assumptions(complete)` returns a growth list | non-empty | closed-form: the stop must fire on the absence and on nothing else |
| CLI FCFF row for 2024 | `  2024  not extracted: income statement` | hand-enumerated: 2024 has a cash flow statement and no income statement, so the income statement is the only statement the row can name |
| web FCFF row for 2024 | `is_computable=False`, `fcff=None`, `missing_statements=("income statement",)` | the same enumeration, through the other entry point |
| 2024's CFO and CapEx cells in the CLI cash-flow table | `242`, `-66` at characters 28–38 | hand arithmetic: CFO = net income 132 + D&A 110 = 242; CapEx is the fixture's -66. The position is derived: 18-character label, 10-character cells, 2024 is the second |
| CLI FCFF line == web cell for 2024 | `f"  {2024:>4}  " + "not extracted: " + ", ".join(missing)` | closed-form identity, with the web half built the way `templates/_statements.html:501` builds it |
| reconciliation phrase, three cases | `raw income statement` / `adjusted income statement` / `raw and adjusted income statement`, and CLI == `f"  2024: not extracted: {web}"` | the case stated in words, plus the closed-form identity; the web half is built the way `templates/_statements.html:455` builds it |
| `BSONLY.years`, `.income_statement_years` | `[2024]`, `[]` | hand-enumerated from the fixture: one balance sheet, no income statements |
| `BSONLY.latest_year` raises | `ValueError` naming `BSONLY` and `no income statements` | rule 3 and fact 4 of the unit's assignment; the claim is then verified against `income_statement_years` on the same object, so the message is asserted as true and not as text |
| `probe.latest_year` | `2025` | hand-enumerated: the latest of `[2023, 2025]` |
| blank cell width, `w ∈ {6, 7, 10, 12}` | `w + 1`, and `== len(_pct(…, w))` | the format string at `cli.py:417`, number 2 above |
| blank cell contents | no digit, strips to `""` | rule 3: a cell that cannot be computed invents nothing |
| `_net_margin_cell(_income(2023), 10)` | `"      12.0%"` | hand arithmetic: 120 / 1,000 = 0.12 → `"{:>10.1f}%".format(12.0)` is six spaces, `12.0`, `%` |
| net-margin row cell positions | 18, 29, 40; middle 11 spaces; third == the twin filing's third | derived column positions (number 2) **and** a closed-form identity against a twin filing |
| the absence line | `  2024  not computable: net income margin, revenue is 0`, exactly once | hand-enumerated: 2024 is the only zero-revenue year in that filing |
| historical FCFF, all three years, both entry points | revenue / CFO / after-tax interest / CapEx / FCFF / margin per the block above | hand arithmetic, number 3 |
| probe 2023 and 2025 FCFF == complete 2023 and 2025 FCFF | identical | closed-form identity: the probe is the complete filing with one income statement removed and nothing else changed. Pinned to 200.0 and 240.0 so it cannot pass on two equal wrong numbers |
| derived assumptions of the complete filing | growth `sqrt(1.2) - 1`, margin 0.20, tax 0.20, D&A 0.10, CapEx 0.06, NWC 0.00 | hand arithmetic, number 3 |
| reconciliation of a filing against itself | every `difference == 0.0`, no `missing_statement`, EBIT `[200, 220, 240]` | closed-form identity (a filing reconciled against itself differs nowhere) plus hand arithmetic: EBIT is 20% of revenue |
| the reconciliation summary, when nothing reconciled | the `No adjustments applied` line is **absent** | the sentence must not assert that no adjustment applied to a year whose EBIT was never read. An absent claim, not a fallback |
| the balance-sheet divergence line | heading `FY2026`, line naming `FY2025's balance sheet`; absent when the two agree | hand-enumerated from the fixture: latest balance sheet 2026, latest income-statement year 2025 |
| `cli.main` stage 1 | `  Years extracted: [2023, 2024, 2025]` and `  Years with an income statement: [2023, 2025]`, then a `ValueError` naming `revenue` and `2024` | the two hand-enumerated year sets, and rule 3 reaching the operator |

**No assertion in this file was obtained by running the code and reading what it
printed.**

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| the income statement of a year in `financials.years` (`derive_assumptions`) | **stops, naming `revenue` and the fiscal year** | `analysis/projector.py:121-133`; `test_derive_assumptions_stops_and_names_the_field_and_the_fiscal_year`, which asserts `excinfo.type is ValueError` |
| `income_statement_years` in `latest_year` | **stops, naming the ticker and the absence of income statements** | `models/financial_statements.py:508-513`; `test_latest_year_stops_for_a_filing_with_a_balance_sheet_and_no_income_statement` |
| the same, reached through the CLI | **the stop propagates out of `cli.main`**, after stage 1 has named both year lists | `test_cli_main_names_the_year_with_no_income_statement_at_stage_one` |
| the income statement of a year, CLI FCFF table | **a row naming `income statement`**; no figure invented | `cli.py:934-935`; two tests, plus coverage showing the line EXECUTED |
| the income statement of a year, web FCFF rows | **`is_computable=False`, `fcff=None`, `missing_statements=("income statement",)`** | `api/routes_valuation.py:273-274`; same |
| the cash flow statement of a year | **a row naming `cash flow statement`**, and the year named under the CLI table | `test_a_balance_sheet_only_filing_still_prints_its_statements_without_raising` |
| either side of the reconciliation | **a record naming which side is absent**, in one vocabulary for both entry points | `test_both_entry_points_name_an_unreconciled_year_in_the_same_words`, three cases |
| `net_income / revenue` when `revenue == 0` | **a blank cell holding no digit, and the year, the field and the reason named under the table** | `cli.py:446-448` and `:571-573`; four tests, one of which asserts both halves of a single output |
| the balance sheet, when none was extracted | **`No balance sheet extracted.`** | `cli.py:636-639` |
| **`gross_margin` and `operating_margin` when `revenue == 0`** | **defaults to `0.0`, so the two rows above print a fabricated `0.0%`** | `models/financial_statements.py:108` and `:132` — see below |

**The one stop path I could not lock, and why that is not a `fail` here.**
`IncomeStatement.gross_margin` (`models/financial_statements.py:108`) and
`.operating_margin` (`:132`) carry `if self.revenue else 0.0`, so for a
zero-revenue year the `Gross Margin` and `EBIT Margin` rows print `0.0%` one and
two lines above a net-margin row that says the figure is absent. That is a
default where rule 3 asks for a stop, and `templates/_statements.html:44` and
`:86` print the same `0.0%` on the web page.

**I wrote no assertion about those two cells.** A test locking `0.0%` there would
make the defect permanent and turn its fix red — the single most damaging thing a
tester can write in this repository. The alignment test derives the net-margin
column from the format string and from a twin filing, never from the row above it,
so nothing in this file reads either property.

It is **backlog item 1**, it is named in the assignment under "Backlog items this
unit is NOT fixing", and the **overall lead's ruling of 2026-10-07** records the
two facts that leave it (`templates/` is out of this unit's scope, and
`analysis/projector.py` reads `operating_margin` into the DCF, so changing the
property moves a figure). The reviewer excluded it on the same ruling. It is
reported here and it does not move my verdict, which judges the unit against its
own fifteen criteria.

## Mutations — seven applied, seven killed, none survived

Each in its own scratch tree under `C:\tmp`, built from a copy of the working
tree. **No repository file was mutated.** Command for each:
`.venv/Scripts/python.exe -m pytest tests/unit/test_p3d_invisible_year.py -q` with
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`, run from the scratch tree
(`C:\tmp\p3dt_mutate.py`, `C:\tmp\p3dt_mutate2.py`).

| # | Mutation | `file` | Result | Tests that went red |
|---|---|---|---|---|
| **A** | `years` back to the income statements alone | `models/financial_statements.py` | **14 failed, 19 passed** | `test_years_is_the_union_of_all_three_statement_kinds`, `test_income_statement_years_is_a_subset_of_years_and_here_a_strict_one`, `test_derive_assumptions_stops_and_names_the_field_and_the_fiscal_year`, `test_derive_assumptions_never_produces_the_one_year_window_the_invisible_year_gave`, `test_the_cli_fcff_table_prints_a_row_for_the_year_with_no_income_statement`, `test_the_web_fcff_rows_hold_a_row_for_the_year_with_no_income_statement`, `test_the_cash_flow_figures_of_the_invisible_year_are_printed`, `test_both_entry_points_name_the_missing_income_statement_in_the_same_words`, `test_both_entry_points_name_an_unreconciled_year_in_the_same_words[False-False-…]` and `[False-True-…]`, `test_latest_year_stops_for_a_filing_with_a_balance_sheet_and_no_income_statement`, `test_a_balance_sheet_only_filing_still_prints_its_statements_without_raising`, `test_the_reconciliation_summary_is_silent_when_no_year_was_reconciled`, `test_cli_main_names_the_year_with_no_income_statement_at_stage_one` |
| **B** | `_income_statements_for_years` **skips** the year instead of stopping | `analysis/projector.py` | **3 failed, 30 passed** | `test_derive_assumptions_stops_and_names_the_field_and_the_fiscal_year`, **`test_derive_assumptions_never_produces_the_one_year_window_the_invisible_year_gave`**, `test_cli_main_names_the_year_with_no_income_statement_at_stage_one` |
| **C** | `latest_year` reads the wide set | `models/financial_statements.py` | **2 failed, 31 passed** | `test_latest_year_stops_for_a_filing_with_a_balance_sheet_and_no_income_statement`, `test_the_balance_sheet_section_names_the_sheet_the_valuation_reads` |
| **D** | the net-margin blank widened to `w` instead of `w + 1` | `cli.py` | **5 failed, 28 passed** | `test_the_blank_net_margin_cell_is_as_wide_as_the_cell_it_stands_in_for[6|7|10|12]`, `test_a_zero_revenue_year_in_the_middle_does_not_shift_the_later_columns` |
| **E** | the income statement table printed **without** `_print_net_margin_absences` | `cli.py` | **1 failed, 32 passed** | `test_the_income_statement_table_and_its_absence_line_are_printed_as_a_pair` |
| **F** | the CLI reconciliation phrase back to round 1's comma-join | `cli.py` | **2 failed, 31 passed** | `test_both_entry_points_name_an_unreconciled_year_in_the_same_words[False-False-…]`, `test_the_reconciliation_summary_is_silent_when_no_year_was_reconciled` |
| **G** | the dead branch `missing.append("income statement")` deleted from the CLI | `cli.py` | **2 failed, 31 passed** | `test_the_cli_fcff_table_prints_a_row_for_the_year_with_no_income_statement`, `test_both_entry_points_name_the_missing_income_statement_in_the_same_words` |

**The assignment's four are A to D, and B is killed by the growth-rate test as
well as by the exception test**, which is what it asks for. Its failure message
reads

```
Failed: derive_assumptions returned revenue_growth_rates=[0.19999999999999996, …]
for a filing whose 2024 income statement is absent. The invisible year produces
20.0000% a year by reading two fiscal years of growth as one; the endpoints alone
justify 9.5445%. Neither is a measurement of this filing, so the run must stop.
```

E, F and G are three more I added because three criteria would otherwise rest on a
test whose failure I had not seen: N1's unenforced pair, the two entry points
drifting apart, and criterion 15's deleted branch. **No mutation survived.**

## Measurements

**Two counts, with their units.**

- **Accuracy: 101 of 101 assertions match an independently derived expectation**
  — 97 `assert` statements, 3 `pytest.raises` blocks and 1 `pytest.fail`, over 28
  test functions and 33 collected cases. **0 of 101 came from the code's output.**
- **Coverage: 78 of 78 executable statements this unit added are covered, 0
  missed**, with **0 partial branches** on any added line. By **function**: the
  unit added or changed **17** functions that carry an added executable statement;
  **16 of 17 are touched by this file**, and **17 of 17 by the suite** — the one
  this file does not reach is `ingestion/claude_extractor._build_is_summary`
  (`:2329`, review finding F2), which `tests/unit/test_claude_extractor.py`
  already covers.

Measured, not estimated:

```
.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py" \
  --cov=analysis --cov=models --cov=api --cov=cli --cov=ingestion --cov=pipeline \
  --cov-branch --cov-report=json:C:/tmp/p3dt_cov2.json
C:\tmp\p3dt_cov_intersect2.py        # git diff -U0 added lines  x  executed_lines
```

```
models/financial_statements.py: added stmts 11, covered 11, missed 0, partial branches 0
analysis/projector.py         : added stmts 13, covered 13, missed 0, partial branches 0
api/routes_valuation.py       : added stmts  0, covered  0, missed 0   (docstring only)
    dead branch line 273: EXECUTED      dead branch line 274: EXECUTED
cli.py                        : added stmts 53, covered 53, missed 0, partial branches 0
    dead branch line 934: EXECUTED      dead branch line 935: EXECUTED
ingestion/claude_extractor.py : added stmts  1, covered  1, missed 0
ingestion/session_extraction.py: added stmts 0, covered  0, missed 0   (comment only)
TOTAL added executable statements: 78    covered: 78    missed: 0
```

**The two newly-reachable branches are executed, and so is the third
`_build_ebit_reconciliation` branch** (`api/routes_valuation.py:365`, the `else`
that names `raw and adjusted income statement`).

**Gates, Windows, `.venv/Scripts/python.exe`, Python 3.14.4,
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`, every one run after my last write:**

| Gate | The assignment's figure | Mine |
|---|---|---|
| gate form | `1224 passed, 2 skipped, 0 failed` | **`1257 passed, 2 skipped`, 0 failed** (137.44s) = 1224 + 33 |
| failing set, by name | empty | **empty** |
| full suite | 2 failed, the two red on purpose | **`2 failed, 1257 passed, 2 skipped`**, the same two by name |
| lint | 4, all `BLE001` | **4, all `BLE001`** |
| types | 2 errors in 2 files | **`Found 2 errors in 2 files (checked 21 source files)`** |
| census | 64 | **64** |
| route | 200 | **200** |
| write guard | 48/48 | **48/48** |

**`test_projector_rule3_red.py` is still red and nothing moves out of the
pattern.** I checked it, because my unit touches the function it tests. Its input
is `FinancialStatements(ticker="TEST")` — no statements of any kind — so
`years == []`, `_income_statements_for_years` returns an empty list without
stopping, and the bare `IndexError` at `revenues[-1 - lookback]` survives. That is
backlog item 14's twin, out of scope, and the assignment says to leave it red. No
green test is sitting inside a `*_rule3_red.py` file (backlog item 24's trap).

**Scratch discipline.** No repository file outside `tests/` was written. sha256
before and after every command above, printed in the same session:

```
beaf810a5dafe7fef76eaef3ca12ec571778906acfa241b3341070a597dfbee8  models/financial_statements.py
8d42786e17f19eac056f288bc3197670403d2cbcd8eb6b330bcc5ee711515242  analysis/projector.py
ba69c8a8997245b8cc70fb612d015e066fa8aef656f7f8893aadd0619b036961  api/routes_valuation.py
f87e29150304273023e42452a15ce41143c45915d1717642374ba2e4b8c0265d  cli.py
031101564e38b1165f602160aaae643fd344b685be8a94d62e10d1978486ff4d  ingestion/claude_extractor.py
fceac7996c5d2beb744fd941a025f4f0649a599656a6710b6c4754c2800937ca  ingestion/session_extraction.py
```

Identical on both readings. The scratch trees are `C:\tmp\p3dt_base` and seven
`C:\tmp\p3dt_<mutation>` copies. **`git stash` was not used.** `extractions/WMT.json`
was neither read nor written: every statement in this file is built in the test, so
no filing, no PDF, no key and no socket is needed — `cli.main` is exercised under
the `_no_socket` fixture with both extraction boundaries replaced.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The fixture's figures are written out as literals, not as `scale * base` | `1000.0 * 1.1` is `1100.0000000000001`, and an "exact" hand figure that is off by an ulp makes every equality assertion a judgement call about tolerance | A table of eight literals per year keeps `EBIT == 220.0` and `effective_tax_rate == 0.2` exactly true, so the reader can check the arithmetic and the test can assert it without hedging |
| Every ratio in the fixture is the same in all three years (margin 20%, tax 20%, D&A 10%, CapEx 6%) | the mean of three equal numbers is that number, so the derived assumptions are checkable with no averaging arithmetic | Three different ratios would need a three-term mean written out, and a reader checking it would be checking my arithmetic rather than the code's |
| The probe filing is the complete filing **minus one income statement** and nothing else | it makes "no figure moved" a closed-form identity rather than a second set of hand figures | Two unrelated fixtures would prove the figures right twice and say nothing about whether widening `years` disturbed a neighbouring year |
| The alignment test asserts derived positions **and** an identity against a twin filing | the positions catch the `w` blank directly; the identity survives a later change to `col` or `label_col` | Either alone is weaker: positions alone go stale on a layout change, the identity alone passes if both rows shift together |
| Nothing in this file reads `gross_margin` or `operating_margin` at zero revenue | `docs/5-testing/strategy.md` section 2.1: a test that asserts a known default makes its fix red. The ruling of 2026-10-07 leaves those two lines deliberately | Asserting `0.0%` would have been the easiest way to pin the table's shape, and it is exactly the assertion the role card names as the most damaging one available to me |
| Three mutations beyond the four asked for (E, F, G) | three criteria — N1's pair, the shared words, the undeleted branch — otherwise rested on tests whose failure I had not seen | "Prove the test can fail" (`docs/5-testing/strategy.md` section 6). A test nobody has seen fail is a test nobody has measured |
| `_ = financials.latest_year` inside `pytest.raises` | `ruff` B018 reads a bare property access as a useless expression, and it is a real fifth lint error in a file I wrote | Leaving it would have repeated `P3c-one-number-tests`' exact failure: lint measured over the wrong set and a fifth error found at acceptance |

**A test written to reach a target number, rather than on a reason, is
forbidden.** No expected value here was adjusted after a run. The one value I
re-derived after seeing output is the 20.0000% CAGR, and it was derived first (the
arithmetic is above), then found to agree with what mutation B produced.

## What I did not do

- **I did not touch any implementation file.** Three things I would otherwise have
  wanted — the `0.0%` in the two margin rows, the over-asserting balance-sheet
  sentence (reviewer N3) and the wording "revenue is 0" (N4) — are findings, not
  fixes, and two of them are explicitly out of my scope.
- **I did not test the reviewer's N2, N3 or N4, nor the round 2 programmer's four
  findings.** The assignment puts each out of scope. `test_the_balance_sheet_section_names_the_sheet_the_valuation_reads`
  covers the F3 line's **true** case only (FY2025's balance sheet exists in that
  filing), so it does not pin N3's over-assertion in either direction.
- **I did not add a `*_rule3_red.py` file.** Every requirement I could state is met
  by the code, so nothing in this unit belongs in the pattern the gate excludes.
- **I did not run the e2e scripts.** They need a key and hold no assertions
  between them; `docs/5-testing/strategy.md` section 4 says they are not evidence.
- **I did not re-measure Walmart.** Criteria 8 and 9 of the unit's own assignment
  were measured by the programmer and re-measured by the reviewer on their own
  pinned runners; my criterion 9 is the hand-built complete filing, which is what
  this assignment asks for.

## Findings for the orchestrator

1. **`cli.print_normalization` iterates `raw.years` while
   `api/routes_valuation._build_ebit_reconciliation` iterates
   `sorted(set(raw.years) | set(adjusted.years))`.** My parity test over all three
   missing-statement cases passes only because its two fixtures give both sides the
   same year set. **A year present on the adjusted side and absent from the raw
   side's `years` would reach the page and not the CLI**, and no test in this
   repository would see it. The reviewer named this at the end of its round 2
   entry and did not charge it to the unit; I confirm it is real and that my suite
   does not cover it. One line, `cli.py:845`, and it wants an owner.
2. **Reviewer N1 is now enforced at the one call site, and only there.**
   `test_the_income_statement_table_and_its_absence_line_are_printed_as_a_pair`
   fails if `print_extracted_financials` stops calling `_print_net_margin_absences`.
   It cannot see a **second** caller of `_print_income_statement_table` that omits
   the line. The pair is still a convention and not a contract; if a second caller
   is ever added, the test will stay green while the defect returns.
3. **`cli.main` has no `try`/`except` of its own** — the `ERROR:` handler lives in
   the `if __name__ == "__main__"` block (`cli.py:1406-1413`), so a `ValueError`
   out of `derive_assumptions` reaches an importing caller raw. That is what makes
   `test_cli_main_names_the_year_with_no_income_statement_at_stage_one` possible
   and it is the right shape for a test, but it means the two entry points differ
   in how a stop surfaces: the web renders it through the blanket
   `except Exception` (backlog item 8) and the CLI prints `ERROR: {e}` only when
   run as a script. Worth a line in whichever unit closes item 8.
4. **`ingestion/claude_extractor.py:2280` and `:2358` still read `if target_years:`**
   — the shape F2 removed at `:2329`. The round 2 programmer recorded it; my suite
   does not touch either line, and the one added statement at `:2329` is covered by
   the existing `tests/unit/test_claude_extractor.py` and not by this file.
