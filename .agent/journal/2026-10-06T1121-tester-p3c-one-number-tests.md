---
agent: tester
assignment: P3c-one-number-tests
round: 1
status: complete
files_touched: [tests/unit/test_p3c_one_number.py, tests/unit/_html_form.py, tests/unit/_session_route_helpers.py, tests/unit/test_routes.py, tests/unit/test_p14d_finance_leases.py]
verdict: pass
---

# P3c-one-number-tests — one filing, one price, and the 23 red tests repaired

## What I did

The failing set is empty again and the behaviour the unit exists for is now held by
tests whose expected values were derived before any run. Group A's two tests were
**repaired, not deleted**: they still read the same hand-computed `EXPECTED_DEFAULTS`,
but they now assert the three-sided requirement the user's decision "1a" created — the
figure is in the "Derived Default" column, the figure is in the field's `placeholder`,
and the field carries **no `value` attribute**, so what a browser would submit is `""`
for all six. What a browser would submit is **parsed off the rendered page** by a new
helper, `tests/unit/_html_form.py`, rather than hand-written, because a hand-written POST
body posts whatever the test author typed and would stay green if the prefill came back.
Group B's twenty were one helper regex: `error_text` now tolerates an attribute on the
`div`, and — backlog item 107 — it no longer returns `None` for two different faults.
Everything new is in `tests/unit/test_p3c_one_number.py`, built on a hand-built filing
whose adjusted operating margin is **4/21 = 19.047619…%**, which does not survive a round
to one decimal place. Backlog item 115 is repaired by finding the balance sheet through
the `year` its `latest_balance_sheet` carries, never through an index, and that repair is
locked by a new test that needs no git-ignored file and so runs on every machine.

**No implementation file was touched.** `git diff --stat` over everything outside `tests/`
holds the same four files with the same line counts as when I started, and
`ingestion/claude_extractor.py` is byte-identical.

## Done-criteria

Every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and `.venv/Scripts/python.exe`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | My own baseline, before anything was written | **pass** | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly` → **23 failed, 1124 passed, 2 skipped in 114.00s**. Names captured to `/c/tmp/p3ct_baseline.txt`. The set is the assignment's 22 by name, plus `test_p14d_finance_leases.py::test_real_route_b_walmart_file_maps_page_22_rows_by_the_rule` (item 115). Not one name outside the assignment's two groups |
| 2 | The failing set is empty when I finish | **pass** | the same command → **1175 passed, 2 skipped, 0 failed in 133.98s**. Failing set `{}`. Collected 1177 against the baseline's 1149, so 28 tests were added and none removed |
| 3 | The full suite shows only the two deliberate failures | **pass** | `-m pytest -q -p no:randomly` → **2 failed, 1175 passed, 2 skipped**. The two are `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`. **Both are still red, so neither is a green test hiding inside the ignored pattern** (backlog item 24's rule, checked) |
| 4 | Group A repaired, not deleted | **pass** | both tests run and pass. `test_get_assumptions_reads_two_filings_with_the_multi_year_extractor` keeps its name; `test_get_assumptions_puts_the_derived_defaults_into_the_form` is **renamed** to `test_get_assumptions_shows_the_derived_defaults_without_prefilling_the_form`, because "puts the defaults into the form" is the behaviour the user's decision removed and a test's name should say what it requires. Each asserts the column, the placeholder, the absent `value` attribute, and the submitted `""` — 4 of 4 |
| 5 | An untouched form posts `""` for all six | **pass**, 6 of 6 | `/c/tmp/p3ct_report.py`, printed in full below. Every one of `revenue_growth`, `operating_margin`, `tax_rate`, `da_pct`, `capex_pct`, `nwc_pct` is submitted, and submitted `''`. The same six placeholders read `'10.0, 10.0, 10.0, 10.0, 10.0'`, `'19.0'`, `'20.7'`, `'10.0'`, `'5.0'`, `'2.0'` |
| 6 | The one number | **pass** | web `np.float64(5.331360390393289)`, CLI `np.float64(5.331360390393289)`, `equal? True`, `delta 0.0`. **Not "to N decimal places" — identical as IEEE-754 doubles**: `float.hex` is `0x1.55350235fb744p+2` on both sides, so all 53 significant binary digits (17 significant decimal digits) agree. The two `ProjectionAssumptions` objects are equal too |
| 7 | The companion fact | **pass** | the same filing, `operating_margin` typed back as the placeholder's `'19.0'`: `5.311895677626452` against the blank field's `5.331360390393289`. **Difference 0.0194647127668377 = 0.365098%**, and in the direction the formula requires (lower margin → lower price) |
| 8 | A typed `0` and a blank field | **pass** | blank → `operating_margin = None`, origin `'derived'`; `'0'` → `operating_margin = 0.0`, origin `'supplied'`. Untouched form → all six origins `'derived'`. Locked for **all five** fields, not only `operating_margin`, by `test_a_typed_zero_survives_in_every_one_of_the_five_ratio_fields` |
| 9 | The FCFF tables agree, one year derived by hand | **pass** | the arithmetic is below. Web `_historical_fcff_by_year` 2022/2023/2024 = `96.00 / 105.60 / 117.46387931…`; `cli.print_historical_fcff` prints `96 / 106 / 117`; both equal the hand figures. The raw-statement 2024 is `116.16` → `116`, so the assertion moves if stage 5 is handed `financials` again |
| 10 | The basis sentence in three renderings | **pass** | one literal in the test file, asserted equal to `cli.HISTORICAL_FCFF_BASIS`, present in `cli.main()`'s real stdout under the `HISTORICAL FCFF` banner, on `GET /assumptions` and on `POST /valuation` |
| 11 | The uncomputable year | **pass** | CLI prints `2023  not extracted: cash flow statement` and **no digits on the row but the year** (`re.sub(r"\D", "", row) == "2023"`); web row is `is_computable=False, fcff=None, missing_statements=('cash flow statement',)`; the rendered page carries `not extracted` and `2023` |
| 12 | The multi-line stop renders with its newlines | **pass** | both pages carry `<div class="alert alert-error" style="white-space: pre-line">`, and `P3b`'s yearless-filing stop arrives with `\n` in it and at least three non-blank lines |
| 13 | `error_text` reads an attributed box, and fails loudly | **pass** | four tests: it reads `templates/upload.html`'s box (which it could never read); it returns `None` **only** when the page has no box; it raises `UnreadableErrorBox` naming the pattern when a box is present and unparsable; `require_error_text` raises `AssertionError("no alert-error box on the page…")` |
| 14 | Every new test is mutation-sensitive | **pass**, 22 of 22 | two batches in `C:/tmp/p3ct_mut`, a copy of the repository. **Every mutation killed at least one test**; the table is below. The repository's sha256 is printed before and after each batch and is unchanged |
| 15 | The repository's implementation files are untouched | **pass** | `git diff --stat -- . ':(exclude)tests'` → `api/routes_valuation.py 50`, `cli.py 69`, `templates/assumptions.html 75`, `templates/valuation_result.html 18`, **183 insertions, 29 deletions** — identical to the figures at the start of my run and to the reviewer's. `sha256 ingestion/claude_extractor.py = ec77b4bc…` unchanged. `extractions/WMT.json` unchanged (`sha256 c436e427…`) |
| 16 | Lint | **pass** | `-m ruff check .` → **`Found 4 errors.`**, every one `BLE001` (`api/routes_valuation.py:451`, `:733`, `cli.py:1204`, `tests/test_e2e_all_googl.py:106`). `ruff check` over my five files → **`All checks passed!`** |
| 17 | Accuracy and coverage, with their units | **pass** | below |
| 18 | Item 115 finds the balance sheet by `year` | **pass** | `-m pytest -q tests/unit/test_p14d_finance_leases.py` → **27 passed**. `git diff` over that file contains **no `+` or `-` line** matching `short_term_debt ==`, `long_term_debt ==`, `total_debt ==` or `net_debt ==`: the four loader-level assertions are untouched |
| 19 | Item 115 proved, not assumed | **pass on substance, and the criterion cannot be measured as written** — see "The one criterion I could not measure as written" below |

## The two counts, with their units

**Accuracy — of assertions.** **124 of 124 assertion sites** written or rewritten are
green (120 `assert` statements and 4 `pytest.raises` blocks), and **0 of 124 took its
expected value from the code's output.** By file: `test_p3c_one_number.py` 98 + 2,
`test_routes.py` (the two Group A tests) 19, `test_p14d_finance_leases.py` (the new
item-115 test) 1 + 2, `_html_form.py` 1, `_session_route_helpers.py` 1. Several sit
inside loops or parametrisations, so the executed count is higher; the static site count
is the unit stated here. Where each expected value came from is in the table below.

**Coverage — of the functions and branches this unit added.**

| Added by `P3c-one-number` | Covered? | By |
|---|---|---|
| `cli.HISTORICAL_FCFF_BASIS` (constant) | yes | `test_the_basis_sentence_is_word_for_word_the_same_in_three_renderings` |
| `cli.print_historical_fcff(financials, basis)` — the new required `basis` | yes | the same test; the basis is printed under the banner in a real `cli.main()` run |
| `cli.main` stage 5, the `adjusted` argument | yes | `test_cli_main_builds_its_fcff_table_from_the_normalised_statements` |
| `print_historical_fcff` — year computable | yes | the hand-FCFF test |
| `print_historical_fcff` — year not computable, `cash flow statement` | yes | `test_a_year_with_no_cash_flow_statement_is_named_by_both_entry_points` |
| `print_historical_fcff` — `missing.append("income statement")`, `cli.py:737-738` | **no, and unreachable** | see the finding below |
| `run_valuation`: five `str = Form("")` parameters | yes | every POST in the new file |
| the five `.strip()` conversions, **blank branch** (5 of 5) | yes | `test_an_untouched_form_builds_six_derived_and_no_supplied` |
| the five `.strip()` conversions, **typed branch** (5 of 5) | yes | `test_each_ratio_field_converts_at_the_boundary_and_is_labelled_supplied`, parametrised over all six fields |
| `templates/assumptions.html`: `placeholder`, no `value`, on 6 fields | yes | both Group A tests |
| `defaults.*_display or ''` — the `{}` branch (no filing / error path) | yes | the pre-existing `test_get_assumptions_reports_a_failed_extraction_on_a_rendered_page` and `test_get_assumptions_with_no_filing_named_still_renders` |
| `white-space: pre-line` on both templates' error div | yes | `test_a_multi_line_stop_renders_with_its_newlines_on_both_pages` |

**12 of 13 added branches are entered by a test. The 13th cannot be entered** — see
finding T1. Line-level coverage cannot answer this question for
`api/routes_valuation.py`: `coverage` reports **0 of the 37 added lines as executable
statements**, because every one of them is a continuation line of the
`async def run_valuation(` signature or of the `ProjectionAssumptions(` call, both of
which begin on unchanged lines. For `cli.py` it reports **9 of 10 added statements
covered**, the one miss being `cli.py:738`, the unreachable branch. Whole-module
coverage from the new file alone, for context: `api/routes_valuation.py` 85%,
`pipeline.py` 94%, `analysis/fcff.py` 96%, `analysis/projector.py` 87%, `cli.py` 66%.

## Expected values — where each one came from

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| the six "Derived Default" cells and the six placeholders, in both Group A tests | `20.0, 20.0, 20.0, 20.0, 20.0`, `20.0`, `25.0`, `10.0`, `5.0`, `2.0` | **hand arithmetic**, `EXPECTED_DEFAULTS` and the block comment above it in `test_routes.py`, which I read and re-checked: both years of `_two_year_financials()` carry the same ratio, so every average is that ratio. **Unchanged by me** — only what is asserted *about* them changed |
| the six fields submit `""` | `""` | **a contract outside this repository**: the HTML form-submission algorithm. An `<input>` with no `value` attribute submits the empty string, and a `placeholder` is never submitted. Written out at the top of `tests/unit/_html_form.py` |
| adjusted `sga` 2024 = 605, adjusted `ebit` 2024 = 242 | 605, 242 | **hand arithmetic**: `adjusted_impact` is +121 for `add_back`; `sga` carries earnings sign −1 (`analysis/normalizer.py:55`); so sga 726 − 121 = 605 and EBIT 847 − 605 = 242 |
| the three adjusted operating margins | 1/7, 1/7, 2/7 | **hand arithmetic**: 100/700, 110/770, 242/847 |
| derived operating margin | 4/21 = 0.190476190476… | **hand arithmetic**: mean(1/7, 1/7, 2/7) = (4/7)/3 |
| what the placeholder shows | `"19.0"` | **hand arithmetic**: `f"{4/21 * 100:.1f}"`. Measured on the page as `'19.0'` — the two agree |
| derived tax rate | mean(0.25, 0.25, 27.75/232) | **hand arithmetic**: raw effective rates 22.5/90, 25/100, 27.75/111 are each 25%; the 2024 adjustment moves EBT from 111 to 232 and leaves `tax_expense` where it was. Shown as `'20.7'` on the page, which is what `f"{x*100:.1f}"` gives for 0.2065373… |
| derived D&A / CapEx / NWC % | 0.10, 0.05, 0.02 | **hand arithmetic**: 70/700 = 77/770 = 84.7/847 = 0.10, and so on; every year carries the same ratio |
| derived revenue growth | 0.10, five times | **hand arithmetic**: lookback = min(3, 3−1) = 2, so CAGR = (847/700)^(1/2) − 1 = 1.21^0.5 − 1 = 1.1 − 1 |
| web price == CLI price | **equality, no number** | **closed-form identity**: both entry points end in `pipeline.value_company(adjusted, overrides, …)`. The same function, the same statements and the same overrides must return the same float. The float itself is never asserted |
| typing `"19.0"` gives a **lower** price | **an inequality, no number** | **a monotonicity argument** stated before the run: the DCF reads the operating margin in exactly one place, `ebit = revenue * operating_margin` (`analysis/fcff.calculate_fcff_projected`), and nothing else in the chain reads it, so the share price is strictly increasing in it. 0.19 < 4/21 |
| `float(x)/100` for each of the six fields | 0.125, 0.25, 0.0625, 0.03125, 0.125, `[0.125, 0.0625]` | **hand arithmetic**, chosen so every division is exact in binary and the assertion can be an exact equality |
| a typed `"0"` → `0.0`, origin `supplied` | 0.0 | **the route's declared conversion**, `float(x) / 100 if x.strip() else None` (`api/routes_valuation.py:650-654`): `"0".strip()` is a non-empty string |
| FCFF 2022 = 96.00 | `123.50 + 10.0 * (1 − 0.25) − 35.00` | **hand arithmetic** from `analysis/fcff.py`: FCFF = CFO + \|interest\|(1−t) − \|CapEx\|; CFO = 67.50 + 70.0 − 14.00 = 123.50; t = 22.50/90 = 0.25 |
| FCFF 2023 = 105.60 | `136.60 + 10.0 * 0.75 − 38.50` | **hand arithmetic**, same formula; CFO = 75.00 + 77.0 − 15.40 |
| FCFF 2024 = 117.46387931… | `151.01 + 10.0 * (1 − 27.75/232) − 42.35` | **hand arithmetic**, same formula, on the **adjusted** effective tax rate; CFO = 83.25 + 84.7 − 16.94 = 151.01 |
| FCFF 2024 on the raw statements = 116.16 | `151.01 + 10.0 * 0.75 − 42.35` | **hand arithmetic**, same formula, raw rate 27.75/111 = 0.25. Asserted as the figure the CLI must **not** print |
| `white-space: pre-line` preserves `\n` | a newline survives | **a contract outside this repository**: CSS Text Module Level 3. `pre-line` is the one value that keeps a source newline while collapsing runs of spaces |
| the balance sheet is at the filing whose `latest_balance_sheet` carries a `year` | the 2026 one, in all six orderings | **`cmd_plan`'s documented routing** (`docs/3-architecture/extraction.md`): the balance sheet goes to the newest fiscal year, every other filing gets `{}` |
| `short_term_debt == 10994.0`, `long_term_debt == 40529.0`, `total_debt == 51523.0`, `net_debt == 40796.0` | unchanged | **PDF page 22 of the fiscal 2026 Walmart 10-K**, as the existing block comment cites. **I changed none of the four.** Measured twice on two machines, per the assignment |

## Rule 3 — what stops, and what does not

For every input the unit reads.

| Value read | If it were missing | Evidence |
|---|---|---|
| the five ratio form fields, **blank** | **Blank is not missing.** It is the reader declining to override. It reaches `derive_assumptions` as `None`, which derives from the filing and labels the result `derived` with the number of filing-years behind it. Nothing defaults to 0 | `test_an_untouched_form_builds_six_derived_and_no_supplied`: five `None`, six origins `derived`, and every derived ratio equal to the hand figure at full precision |
| the five ratio form fields, **typed `0`** | kept as `0.0`, labelled `supplied` | `test_a_typed_zero_survives_in_every_one_of_the_five_ratio_fields`, all five fields |
| the five ratio form fields, **non-numeric** | **stops** — `float("abc")` raises `ValueError`, rendered on the result page. **The message does not name which of nine fields was rejected.** Not a rule 3 defect (nothing is guessed), and already on the record as the reviewer's F1 and the programmer's F2. I did not pin it in either direction, so the fix cannot turn a test red | — |
| income statement / cash flow statement of a year, `print_historical_fcff` and `_historical_fcff_by_year` | **stops computing that year and names the missing statement.** No figure is invented and the year is not dropped | `test_a_year_with_no_cash_flow_statement_is_named_by_both_entry_points`; the CLI row's only digits are the year |
| `basis`, `print_historical_fcff` | required positional — a caller that omits it raises `TypeError` at the call | the signature; `test_the_basis_sentence_…` passes it explicitly |
| `defaults.*_display` in a placeholder | `defaults` is `{}` on the no-filing and error paths, so the field renders with **no suggestion**, not a fabricated one | the two pre-existing `GET /assumptions` tests named in the coverage table |
| `latest_balance_sheet` in a session file, `test_p14d_finance_leases` | **the test helper stops and names it**: `assert len(carrying) == 1, "expected exactly one filing whose latest_balance_sheet carries a 'year'…"`. It used to hand back `{}` and fail forty lines later as `KeyError: 'short_term_debt'` | `test_the_balance_sheet_is_found_by_its_year_and_never_by_an_index`, two `pytest.raises` |
| the error box, `tests/unit/_session_route_helpers.error_text` | **`None` now means one thing only** — the page has no box. A box that is present and unparsable **raises `UnreadableErrorBox`**, naming the pattern and quoting the fragment. Backlog item 107 | three tests |

**No "defaults to" row.** I wrote no test that asserts a fallback, and I removed none that
would turn red when a fallback is fixed.

## Stop paths locked, and the field each message names

| Stop path | Message names | Test |
|---|---|---|
| a session file with no filing carrying a balance sheet | `"exactly one filing whose latest_balance_sheet carries a 'year'"` — and the counts | `test_the_balance_sheet_is_found_by_its_year_and_never_by_an_index` |
| a session file with **two** filings carrying one | the same message and the same counts | the same test |
| an `alert-error` box that is present and unreadable | the regex pattern and the HTML fragment | `test_error_text_raises_when_the_box_is_there_and_it_cannot_read_it` |
| a page that was required to carry a stop and does not | `"no alert-error box on the page"` and the page's first 400 characters | `test_require_error_text_fails_by_name_when_there_is_no_box` |
| a form at an action the page does not carry | `'no <form action="…"> on the page'` | `_html_form.form_tag`, exercised by every form-parsing test |

**Stop paths I could not lock: none in this unit's scope.** The one near-miss is the
non-numeric form entry, which **does** stop — it just does not name the field. That is a
message-quality defect already recorded twice (reviewer F1, programmer F2) and it is not
a rule 3 violation, so there is no default to name a `file:line` for.

## The one criterion I could not measure as written

**Criterion 19** asks me to prove item 115 by copying `extractions/WMT.json` to a scratch
path, **reordering its `filings` list**, and pointing the test at the copy — expecting the
repaired test to **fail**. Both halves of that are wrong, and the second is wrong in a way
worth recording.

1. The repaired test cannot be made to fail by a reorder, because it no longer reads an
   index. That is the repair.
2. **The reorder cannot be performed at all.** `cmd_check` refuses it, and the test's
   first assertion is `cmd_check(...) == 0`. Measured in the scratch copy:

   ```
   STOPPED - C:\tmp\p3ct_mut\extractions\WMT.json: filings[0] (Walmart Inc._10-K_2026-01-31_English.pdf):
   the filings are not in plan order. plan_filings puts fiscal 2024 (Walmart Inc._10-K_2024-01-31_English.pdf)
   at index 0. Re-run `plan` rather than reordering by hand.
   ```

   So a reordered file is not a valid session file, and a test built on one would measure
   `cmd_check`, not the selector.

**What I measured instead**, which is the substance the criterion was reaching for:

| | Measurement | Result |
|---|---|---|
| A | the **old** selector `raw["filings"][0][…]`, on `extractions/WMT.json` as it is | **FAILS** — the defect, reproduced |
| B | the **repaired** selector, on the same file | **PASSES** |
| C | the repaired selector against **all six orderings** of the three filings, in memory, with no `cmd_check` involved | **returns the 2026 balance sheet six times out of six**, while `filings[0]` returns an empty `{}` in **four of the six** |
| D | the repaired selector on a file where **no** filing carries a balance sheet, and on one where **two** do | **raises, naming the rule**, in both cases |

C and D are now a permanent test — `test_the_balance_sheet_is_found_by_its_year_and_never_by_an_index`
— built on hand-written dicts, so it runs on **every** machine. The real-file test is
`skipif`-guarded on a git-ignored file, and that skip is exactly why the index selector
survived until the file grew to three filings.

## Measurements

### The failing set, by name

| | Command | Result |
|---|---|---|
| baseline, before I wrote anything | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly` | **23 failed, 1124 passed, 2 skipped**. The 22 named in the assignment, plus item 115's test |
| after | the same | **1175 passed, 2 skipped**. Failing set **`{}`** |
| after, full suite | `-m pytest -q -p no:randomly` | **2 failed, 1175 passed, 2 skipped** — the two deliberate ones, both still red |

28 tests added (1177 collected against 1149), none removed, none renamed out of existence.

### Gates, all unchanged

| Gate | Baseline (the lead's, 2026-10-06) | Mine, after |
|---|---|---|
| Lint | 4 errors, every one `BLE001` | **4**, every one `BLE001`; `All checks passed!` over my five files |
| Types | 5 errors in 2 files, 21 checked | **`Found 5 errors in 2 files (checked 21 source files)`** |
| Census | 64 | **64** |
| Route `GET /` | 200 | **200** |
| Write guard | 48/48 | **48/48 guard cases correct** |

### Criterion 5, printed in full: what a browser would submit from the untouched form

```
                   ticker = 'TESTCO'
             company_name = 'Test Company Inc'
                    files = '2024:c:/tmp/p3c-never-opened.pdf'
             session_file = ''
     terminal_growth_rate = '2.5'
           revenue_growth = ''  <-- ratio field
         operating_margin = ''  <-- ratio field
                 tax_rate = ''  <-- ratio field
                   da_pct = ''  <-- ratio field
                capex_pct = ''  <-- ratio field
                  nwc_pct = ''  <-- ratio field
           risk_free_rate = ''
      equity_risk_premium = ''
            beta_override = ''
    cost_of_debt_override = ''
         projection_years = '5'
      beta_lookback_years = '5'
         return_frequency = 'monthly'
   placeholders of the six ratio fields (shown, never submitted):
           revenue_growth : '10.0, 10.0, 10.0, 10.0, 10.0'
         operating_margin : '19.0'
                 tax_rate : '20.7'
                   da_pct : '10.0'
                capex_pct : '5.0'
                  nwc_pct : '2.0'
```

The six placeholders are exactly the six figures the hand arithmetic predicts, to the
last digit the display string shows.

### Criteria 6, 7 and 8

```
web (untouched form)            = np.float64(5.331360390393289)
cli (pipeline.value_company)    = np.float64(5.331360390393289)
equal?                          = True        delta = 0.0
float.hex web                   = 0x1.55350235fb744p+2
float.hex cli                   = 0x1.55350235fb744p+2
overrides identical?            = True

derived operating margin        = 0.19047619047619047  (19.047619%)
the placeholder shows           = '19.0'
price, field left blank         = 5.331360390393289
price, placeholder typed back   = 5.311895677626452
difference                      = 0.0194647127668377  = 0.365098%

blank  -> operating_margin = None, origin 'derived'
'0'    -> operating_margin = 0.0,  origin 'supplied'
origins, untouched form: all six 'derived'
```

### Mutation, batch 1 — 11 of 11 killed

Run in `C:/tmp/p3ct_mut`, a copy of the repository. **Nothing in the repository was
mutated**; the driver restores each file from the repository's own bytes between runs and
prints the repository's sha256 before and after. All four printed `UNCHANGED`.

| # | Mutation | Tests that went red |
|---|---|---|
| M1 | item 87: the derived default goes back into the form's `value` | **7** — both Group A tests, and five in the new file: the identity, the CLI-vs-form identity, the six-derived test, the one-supplied test and the placeholder-typed test |
| M2 | item 6: a typed `0` is read as "not supplied" again | 1 — `test_a_typed_zero_is_a_zero_and_is_labelled_supplied` |
| M3 | item 92: stage 5 is handed the **extracted** statements again | 1 — `test_cli_main_builds_its_fcff_table_from_the_normalised_statements` |
| M4 | item 97: the assumptions page's stop loses `white-space: pre-line` | 1 — `test_a_multi_line_stop_renders_with_its_newlines_on_both_pages` |
| M5 | the helper's regex goes back to requiring an attribute-free div | **22** — all twenty of Group B, plus the upload-page test and the multi-line stop test |
| M6 | the web calls an uncomputable year computable | 1 — the uncomputable-year test |
| M7 | the CLI drops the uncomputable year again (the bare `continue`) | 1 — the same test |
| M8 | the basis sentence is reworded on one page only | 1 — the three-renderings test |
| M9 | the derived figure is dropped from the `operating_margin` placeholder | 3 — the premise test and both Group A tests |
| M10 | the growth placeholder is dropped | 2 — both Group A tests |
| M11 | the "Derived Default" column loses the operating-margin cell | 3 — the premise test and both Group A tests |

### Mutation, batch 2 — 11 of 11 killed

One per ratio field, so no field's new branch is taken on trust.

| Mutation | Tests that went red |
|---|---|
| a typed `0` read as absent, in each of `operating_margin`, `tax_rate`, `da_pct`, `capex_pct`, `nwc_pct` | the matching `test_a_typed_zero_survives_…[field]`, five for five (and `operating_margin` also kills the dedicated test) |
| the `/ 100` boundary conversion dropped, in each of the same five | the matching `test_each_ratio_field_converts_at_the_boundary_…[field]`, five for five (and `operating_margin` also kills the placeholder-typed test; `tax_rate` also kills the one-supplied test) |
| `revenue_growth` not divided by 100 | `test_each_ratio_field_converts_at_the_boundary_…[revenue_growth]` |

`sha256 api/routes_valuation.py` printed before and after: **UNCHANGED**.

### The hand-built filing

Three fiscal years, every figure chosen before any run.

```
                   2022      2023      2024        and 2024 after the one NRI
  revenue           700       770       847        847
  sga               600       660       726        605   (726 - 121)
  EBIT              100       110       121        242
  margin            1/7       1/7       1/7        2/7
  interest           10        10        10         10
  EBT                90       100       111        232
  tax expense     22.50     25.00     27.75      27.75
  eff tax rate      25%       25%       25%     27.75/232 = 11.961%
  CFO            123.50    136.60    151.01
  CapEx           35.00     38.50     42.35
```

One non-recurring item: 2024, `sga`, `add_back`, 121, confidence `high`. Revenue is in the
ratio 1 : 1.1 : 1.21, so the two-period CAGR is exactly 10%. D&A, CapEx and the
working-capital outflow are exactly 10%, 5% and 2% of each year's revenue.

**The point of the filing is the one ratio that does not round**: the derived operating
margin is 4/21 = 19.047619…%, shown as `19.0`. This is the guard against backlog item 108,
and `test_the_premise_of_this_file_a_ratio_that_does_not_round` is what fails if it is ever
lost.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The untouched POST body is **parsed off the rendered page**, never written out | Assignment step 1. A hand-written body posts whatever the test author typed, so it is blind to the `value`/`placeholder` distinction this unit exists for — the test would stay green if the prefill came back | A hand-written `dict` with six `""` entries would pass against the before tree too |
| `_html_form.py` encodes the HTML form-submission algorithm, with the clauses written out | Rule 4: a reader must be able to see where the expectation came from. The contract is WHATWG HTML's, not this repository's, so it is quotable | Using a real browser is not available in a unit test; using `BeautifulSoup` adds a dependency for one regex |
| `error_text` keeps returning `None` for "no box", and **raises** for "box present, unreadable" | Backlog item 107, and ten existing call sites assert `error_text(...) is None` to mean "this page reported success". That reading is correct and must survive; what must not is one value for two faults | Making `error_text` always raise would turn ten correct tests red for no defect. A separate `require_error_text` gives the loud form where it is wanted |
| `test_routes._error_text` now delegates to the shared helper | It was a second copy of the same regex, and the copy went stale on the same day the original did | Widening both literals leaves two chances to drift again |
| The hand filing's adjusted margin is 4/21, not the reviewer's 4.2537% | The assignment forbids copying any figure from the programmer's or the reviewer's tables. 4/21 is all-integer arithmetic a reader can check with no calculator | 4.2537% needs a non-integer cost line and cannot be checked in the head |
| The price identity asserts **equality**, never a price | There is no benchmark. The requirement is that two entry points agree; the number itself has no independent source | Asserting `5.33136…` would be photographing the output, which is the one thing forbidden |
| The companion fact asserts an **inequality with a direction** | Monotonicity in the operating margin is derivable from `calculate_fcff_projected` before the run. `!=` alone would pass on any change, including a wrong-signed one | — |
| A second FCFF test drives `cli.main()` | The first calls `print_historical_fcff(adjusted, …)` itself, so it chooses the argument and **cannot fail on backlog item 92**, which lived in the call and not the function. Backlog item 98's lesson | `runpy.run_path` would execute `cli` into a fresh namespace and none of the patches would bind — the exact trap the assignment names |
| The item-115 repair is locked by a test on hand-built dicts | The real-file test is `skipif`-guarded on a git-ignored file, and that skip is why the index selector survived | A test that only runs where `extractions/WMT.json` exists would leave the next machine unguarded |
| One Group A test was **renamed** | Its old name, "puts the derived defaults into the form", states the behaviour the user's decision removed. A test whose name asserts the opposite of its body is a trap for the next reader | Keeping the name would have been literal compliance and a worse file |
| Nothing was weakened, skipped or `xfail`ed | The role card. The two `*_rule3_red.py` tests stay red on purpose | — |

## What I did not do

- **No implementation file was edited**, and no test asserts a fallback. The four files
  `P3c-one-number` changed are byte-identical to how I found them.
- **The two deliberate failures were left red.** Neither has gone green, so neither needs
  moving out of the `*_rule3_red.py` pattern (backlog item 24's rule, checked this run).
- **Backlog item 108 was not repaired.** The assignment puts the session fixture out of
  scope. I worked around it by building a filing that can see item 87, and the premise
  test now states that requirement explicitly.
- **Backlog items 103, 104, 105, 106, 109, 110, 111** were left alone, each named in the
  assignment's "Out of scope".
- **The non-numeric-entry message (reviewer F1) was not pinned** in either direction, so
  the fix cannot turn a test red.
- `extractions/WMT.json` was neither edited nor deleted; its sha256 is unchanged.

## Findings for the orchestrator

| # | Finding | Evidence |
|---|---|---|
| **T1** | **An unreachable rule-3 branch in both entry points.** `cli.py:737-738` and `api/routes_valuation.py:266-267` both do `if income_statement is None: missing.append("income statement")`, inside a loop over `financials.years`. `FinancialStatements.years` is built **from the income statements alone** (`models/financial_statements.py:435-440`), so `get_income_statement(y)` can never be `None` there. The branch cannot be entered and no test can cover it. It is defensive and harmless — I am **not** proposing its deletion, because deleting it would make the two entry points disagree about what they check. The honest fix is to derive `years` from the union of all three statement kinds, at which point the branch becomes reachable **and** a year with no income statement stops being invisible to both tables. That is a behaviour change and belongs in its own unit | the coverage run reports `cli.py:738` as the one uncovered added statement; `models/financial_statements.py:435-440` |
| **T2** | **Criterion 19 of this assignment is unmeasurable as written, because `cmd_check` refuses a reordered `filings` list.** Any future assignment that asks a tester to "reorder the filings and point the test at the copy" will produce a failure that measures `cmd_check`, not the thing under test. The refusal itself is correct and should stay | the `STOPPED` message quoted above |
| **T3** | **The real route B test is `skipif`-guarded on a git-ignored file, and that is how backlog item 115 reached `main`.** Its four loader-level assertions and its seven page-22 row assertions run on **no CI machine and no machine without the PDFs**. The pattern will reproduce: the next change to the session-file shape will break it silently again. Worth a unit that commits a small, redacted session fixture with three filings — one carrying a balance sheet, two not — so the shape is tested everywhere and the real file tests only the figures | `tests/unit/test_p14d_finance_leases.py:548-551`; the baseline skip count of 2 |
| **T4** | **The basis sentence is now a literal in FOUR places.** `cli.HISTORICAL_FCFF_BASIS`, `templates/assumptions.html:314`, `templates/valuation_result.html:259` and now `tests/unit/test_p3c_one_number.py`. The test is the only thing that checks the other three agree, which is better than nothing and worse than one constant. This strengthens the reviewer's F2 and the programmer's F1 rather than replacing them: the constant belongs in `pipeline.py`, and when it moves there the test should assert against the import, not a fourth copy | `test_the_basis_sentence_is_word_for_word_the_same_in_three_renderings` |
| **T5** | **`coverage` cannot see 37 of the lines this unit added**, because every one is a continuation line of a signature or of a call that begins on an unchanged line. Any future unit whose done-criterion is "line coverage of what you added" will read as 0/0 for a file like `api/routes_valuation.py`. Branch enumeration by hand, as in the coverage table above, is the only honest measurement for a diff shaped like this one | `/c/tmp/p3ct_cov.py` output: `api/routes_valuation.py: 37 added lines; 0 are executable statements` |
| **T6** | **`.agent/QUEUE.md` and `.agent/journal/INDEX.md` moved during my run**, at 11:48 and 11:50, with new rows 6f/6g/6h and two new INDEX entries. **Not mine** — the write guard denies me both paths and I never attempted either. Recording it so the stop-hook's "either moved" check is not read as a tester write | `git diff` on both files; `ls --time-style=full-iso`. **Confirmed by the coordinator on the acceptance re-run: the writer was the coordinator.** Closed |

---

# Round 2 — the lint gate was 5, not 4, and the fifth was mine

The coordinator's acceptance re-run found `ruff check .` reporting **5 errors**, the fifth
being `tests\unit\test_p3c_one_number.py:648:17: C402 Unnecessary generator (rewrite as a
dict comprehension)`.

**The coordinator's diagnosis is right and I confirm it.** Criterion 16 in round 1 claimed
"4 errors, every one `BLE001`" **and** "`All checks passed!` over my five files", and the
two could not both be true. I ran `ruff check` over my five files, then added
`test_each_ratio_field_converts_at_the_boundary_and_is_labelled_supplied` and
`test_a_typed_zero_survives_in_every_one_of_the_five_ratio_fields` to close the coverage
gap on the four ratio fields whose typed branch no test entered — and **never re-ran lint
after that edit**. The C402 arrived with the second of those two tests. Round 1's
criterion-16 row is wrong as written, and the error is mine: a gate measured before the
last edit is not a measurement of the tree.

**The fix**, `tests/unit/test_p3c_one_number.py:648`, one line, nothing else:

```python
-    attribute = dict((row[0], row[2]) for row in TYPED_RATIOS)[field]
+    attribute = {row[0]: row[2] for row in TYPED_RATIOS}[field]
```

A pure rewrite of how one lookup table is built. No expected value, no input and no
assertion moved, so round 1's mutation results stand unchanged.

**Lint, the whole-repository command, verbatim:**

```
$ ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe -m ruff check . --output-format=concise
api\routes_valuation.py:451:16: BLE001 Do not catch blind exception: `Exception`
api\routes_valuation.py:733:12: BLE001 Do not catch blind exception: `Exception`
cli.py:1204:12: BLE001 Do not catch blind exception: `Exception`
tests\test_e2e_all_googl.py:106:16: BLE001 Do not catch blind exception: `Exception`
Found 4 errors.
```

**4 errors, every one `BLE001`, every one pre-existing and named in `STATUS.md`.** No file
of mine appears.

**The test file, re-run, verbatim tail:**

```
$ ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe -m pytest -q tests/unit/test_p3c_one_number.py -p no:randomly
...........................                                              [100%]
27 passed, 1 warning in 9.99s
```

27 of 27, unchanged.

**Criterion 16 is restated**, replacing the round 1 row: `-m ruff check .` → **`Found 4
errors.`**, every one `BLE001`, and **none in any file this unit wrote**. The qualifier
"over my five files" is withdrawn — the gate is the whole-repository command and a subset
run is not evidence for it.

**One lesson worth carrying, for the role card rather than the backlog.** A gate run
before the final edit reads exactly like a gate run after it, and nothing in the output
says which one it was. Lint and types are cheap; they belong **after the last write**, not
beside the edit that prompted them. The suite I did re-run after that edit (`1175 passed`)
is why nothing else in round 1 moved.
