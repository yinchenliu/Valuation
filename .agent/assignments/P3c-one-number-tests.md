---
id: P3c-one-number-tests
phase: 3 — unify the pipeline (part 3)
agent: tester
depends_on: [P3c-one-number]
---

# Lock the one number, and repair the 22 tests the unit turned red (items 87, 92, 6, 97)

## Objective

`P3c-one-number` is the unit that makes the assumptions page and `cli.py` give one share
price for one filing. Its code reviewer approved it on 2026-10-06, round 1, with four
non-blocking findings. **Its four code files are not committed.** You are its tester.

**Fact 1.** Before the unit, `templates/assumptions.html` put each derived ratio, rounded
to one decimal place, in the form's `value` attribute, and `POST /valuation` read it back
as a reader's override. So a reader who changed nothing got a price built from rounded
ratios. Walmart was $27.01 on the page and $28.02 in the CLI. The unit moves the figure
to the input's `placeholder`, which no browser submits.

**Fact 2.** The five ratio fields were `float = Form(0)`, and `operating_margin / 100 if
operating_margin else None` read a typed `0` as "not supplied". They are now
`str = Form("")`, converted with `.strip()`.

**Fact 3.** `cli.py` built its historical FCFF table from the statements as extracted and
the web pages built theirs from the normalised statements. The CLI now uses the
normalised ones, and both entry points print one sentence naming that basis.

**Fact 4.** 22 tests are red in the working tree. **Every one is a test whose subject this
unit changed, and `tests/` was denied to the programmer, so the repair is yours.** The
groups are listed under "The 22, by name" below.

**What follows.** When this unit is done, every behaviour above is held by a test whose
expected value was derived by hand before the code ran, the failing set is empty again,
and each new test goes red when the behaviour it names is removed.

## The trap this unit is most likely to fall into

**Read the first section of `.claude/agents/tester.md` before you write a line.** There is
no benchmark in this repository. The cheapest way to write any test here is to run the
code, read the number it printed, and assert that. **A test written that way verifies
nothing and passes forever**, including against the defect it was meant to catch.

Two examples from this repository, both real:

1. `P3b`'s first CLI stop test ran `cli.py` through `runpy.run_path`, which executes the
   file into a fresh namespace. The patch on the `cli` module was never the name that
   namespace bound, so the assertion "neither extractor was called" **could not fail**
   (backlog item 98). A patch on a module that `cli` imports **from** still holds.
2. `P1d`'s `test_real_lhx_filing_multi_scale_limit` asserted "no failures" twice and
   nothing else, so it passed with check B1 replaced by `return []`. **Any test whose only
   assertion is "no failures" is green against a deleted check** (the `P1d` tester's
   finding 2).

**A third trap is specific to this unit.** Backlog item 108: the repository's one
session-file fixture derives ratios of 30.0%, 20.0%, 3.0%, 7.0%, 1.5% and 100.0%, each
already exact to one decimal place. **A regression test for item 87 built on that fixture
is green before the fix and after it**, because rounding to one decimal takes nothing from
a figure that already has one. Build a filing whose adjusted operating margin does not
round cleanly, as the programmer and the reviewer each did independently.

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-06, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`,
on the working tree that holds `P3c`'s four uncommitted files:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly` | **22 failed, 1124 passed, 3 skipped** |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 5 errors in 2 files, 21 files checked |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.claude/check_guard.py` | 48/48 |

**The skip count may be 2, not 3, when you run.** A route B extraction agent wrote
`extractions/WMT.json` on 2026-10-06. `tests/unit/test_p14d_finance_leases.py:519` skips
while that file is absent and runs when it is present. **Take your own baseline before you
write anything, and compare failing sets by name, never counts.**

The code reviewer's own measurements, each re-run rather than read from the programmer:

| Fact | Result |
|---|---|
| untouched form against `cli.main()`, on the session fixture | both `$277.78` |
| its own hand-built filing, adjusted margin 4.2537%: blank against the figure the old form posted back | `28.858040823256875` against `28.957323583093856`, **+0.344%** |
| the before tree (`git archive HEAD`) | renders `operating_margin value='30.0'`, says "supplied by the caller" **6 times** and "derived" **0 times**, and turns a typed `0` into `None` |
| CLI FCFF table against `_historical_fcff_by_year(adjusted)` | `4,016 / 4,416 / 4,856`, every year equal |
| the effect of passing `adjusted` | 2024 moves `+0.0804` through the effective tax rate `0.21000…` → `0.20598…` |

**Do not copy any figure in those two tables into an assertion.** They are the reviewer's,
taken on the reviewer's own inputs. Build your own inputs and derive your own expected
values from the formula.

## The 22, by name

**Group A — 2 tests. The unit's direct subject.** Both read the form field's `value`
attribute and assert it holds the derived default. That prefill is backlog item 87 and is
what the user's decision "1a" of 2026-10-05 removed.

| File | Test |
|---|---|
| `tests/unit/test_routes.py` | `test_get_assumptions_puts_the_derived_defaults_into_the_form` |
| `tests/unit/test_routes.py` | `test_get_assumptions_reads_two_filings_with_the_multi_year_extractor` |

**Group B — 20 tests. One test-helper regex, not one message.**
`tests/unit/_session_route_helpers.py:368` extracts the error box with
`re.search(r'<div class="alert alert-error">(.*?)</div>', body, re.DOTALL)`, which
requires the `div` to carry **no attribute**. Item 97 adds
`style="white-space: pre-line"` to that div, so the helper returns `None`.

| File | Tests |
|---|---|
| `tests/unit/test_routes_session.py` | `test_assumptions_with_a_ticker_that_differs_from_the_file_stops_naming_both`, `test_assumptions_with_a_company_name_that_differs_from_the_file_stops_naming_both`, `test_valuation_with_a_ticker_that_differs_from_the_file_stops_before_pricing`, `test_route_a_on_a_cache_miss_with_no_key_stops_on_the_credential`, `test_valuation_with_no_filing_stops_naming_all_three_fields`, `test_assumptions_with_files_naming_no_entry_stops_naming_files`, `test_assumptions_with_a_session_file_that_is_not_there_stops_naming_it`, `test_a_session_file_missing_one_pass1_key_renders_the_loaders_message`, `test_a_bad_session_file_uploaded_through_the_form_reaches_the_page_named`, `test_valuation_with_session_file_and_files_on_a_cache_miss_stops` |
| `tests/unit/test_routes.py` | `test_post_valuation_with_the_box_unchecked_stops_at_item_22[absent]`, `[empty]`, `[absent-with-override]`, `test_post_valuation_with_a_value_no_checkbox_sends_stops_and_names_it[yes]`, `[ON]`, `[true]`, `[1]`, `[ on]` |
| `tests/unit/test_p3b_pipeline_stops.py` | `test_the_stop_reaches_the_assumptions_page` |
| `tests/unit/test_pipeline.py` | `test_the_share_count_stop_reaches_the_web_result_page` |

**The stop, its wording and its HTTP status did not change.** The programmer proved that
by execution and the reviewer re-proved it: the same empty `POST /valuation` renders
identical text and status in both trees, and only the attribute on the `div` differs.

## What to do

1. **Repair Group A.** Assert that the six inputs render with an **empty** `value`, that
   the derived figure is on the page **twice** (the "Derived Default" column and the
   input's `placeholder`), and add the assertion the old tests could not make: **an
   untouched form posts `""` for all six.** Parse what a browser would submit from the
   rendered form, rather than hand-writing a POST body.
2. **Repair Group B, and fix the helper's real defect.** Widen
   `_session_route_helpers.error_text` to `<div class="alert alert-error"[^>]*>`. **Then
   make it fail loudly**: a helper that returns `None` when the box is missing and when
   the box is unreadable turns two different faults into one result (backlog item 107).
   It must raise, or return a value whose absence fails an assertion by name. Add one test
   that `error_text` reads the box on **`templates/upload.html`**, which it has never been
   able to read.
3. **Lock the one number.** Build a `FinancialStatements` by hand whose **adjusted**
   operating margin does not round cleanly to one decimal place. Stub
   `pipeline.fetch_price_data`. Assert that `pipeline.value_company` with no override and
   `POST /valuation` with every ratio field absent give the **same** share price, and say
   to how many places they agree. Then assert the companion fact: posting the figure the
   placeholder shows gives a **different** price. **Both assertions are needed.** The
   second is what makes the first mean something.
4. **Lock the blank/typed distinction.** A typed `0` builds
   `ProjectionAssumptions.operating_margin == 0.0` with origin `supplied`. A blank field
   builds `None` with origin `derived`. An untouched form gives six `derived` and zero
   `supplied`. One field typed gives one `supplied` and five `derived`.
5. **Lock the FCFF basis.** For one hand-built filing with at least one applied
   non-recurring item, assert that the CLI's table and `_historical_fcff_by_year` give the
   same figure for every year. **Derive at least one of those figures by hand from
   `analysis/fcff.py`'s formula** and show the arithmetic in your entry. Assert that the
   same basis sentence appears in the CLI output and on both pages.
6. **Lock the uncomputable year.** Statements with one year missing its cash flow
   statement: that year appears in both entry points with its reason, and no figure is
   invented for it.
7. **Lock the readable stop.** Both templates carry `white-space: pre-line`, and a real
   multi-line stop renders with its newlines intact. Use `P3b`'s yearless-filing stop,
   which prints a file list and two remedies.
8. **Mutate, and show each test goes red.** For every behaviour in steps 3 to 7, make the
   code wrong in a **scratch copy** of the repository, run the test, and record which tests
   went red by name. **Never mutate a file in this repository.** Restore nothing by hand:
   work in the copy and confirm the repository file's sha256 is unchanged at both ends.
9. **Record what you find, do not widen your scope.** A defect outside this list goes in
   your entry under "Found". The overall lead puts it in the backlog.

## Files in scope

- `tests/` — any file under it, including `tests/unit/_session_route_helpers.py`.

**Nothing else.** The write guard denies everything else to you, and a write outside
`tests/` is a review finding even when the change is good.

## Out of scope

- **Every implementation file.** `api/routes_valuation.py`, `cli.py`,
  `templates/assumptions.html` and `templates/valuation_result.html` are the unit's code
  and are already approved. If you believe one of them is wrong, **that is a finding:
  write it and stop.** Do not edit it.
- **Backlog items 103, 104, 105, 106, 109, 110, 111.** Each came out of this unit's review
  and each is recorded. None is yours to fix.
- **Backlog item 108**, the session fixture that cannot see item 87. You must not build
  your item 87 test on that fixture (step 3 says so). Repairing the fixture itself is a
  separate unit.
- **The two tests that are red on purpose**, `tests/unit/test_projector_rule3_red.py` and
  `tests/unit/test_routes_session_rule3_red.py`. Leave both red. If one goes green, move
  it out of the `*_rule3_red.py` pattern in this unit (backlog item 24's rule).

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`. Add `-p no:randomly` when you compare
two runs.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | Your own baseline, taken before you write anything | the failing set, by name | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly`, names captured to a file |
| 2 | The failing set is empty when you finish | `{}` | the same command, sets compared by name, not by count |
| 3 | The full suite shows only the two deliberate failures | exactly those two names | `-m pytest -q -p no:randomly` |
| 4 | Group A is repaired, not deleted | both tests run and assert the placeholder, the column and the empty `value` | run both by name |
| 5 | An untouched form posts `""` for all six ratio fields | 6 of 6 | parse the rendered form and print what a browser would submit |
| 6 | The one number | the two prices agree, and you say to how many decimal places | step 3's hand-built filing |
| 7 | The companion fact | posting the placeholder's figure gives a **different** price, and you give the difference as a number and a percentage | the same filing |
| 8 | A typed `0` and a blank field | `0.0` with `supplied`; `None` with `derived` | print the `ProjectionAssumptions` the route built |
| 9 | The FCFF tables agree, and one year is derived by hand | every year equal; the hand arithmetic shown | step 5 |
| 10 | The basis sentence is in three renderings | the same words in the CLI output, `GET /assumptions` and `POST /valuation` | render and print |
| 11 | The uncomputable year | present with its reason in both entry points | step 6 |
| 12 | The multi-line stop renders with its newlines | the rendered HTML, quoted | step 7 |
| 13 | `error_text` reads a box that carries an attribute, and fails loudly when there is no box | both, by test | step 2 |
| 14 | Every new test is mutation-sensitive | for each mutation: the mutation, and the tests that went red, by name | step 8, in a scratch copy |
| 15 | The repository's implementation files are untouched | `git diff --stat -- . ':(exclude)tests'` holds only `P3c`'s four approved files, with the same line counts as when you started | `git diff --stat`, before and after |
| 16 | Lint | 4 errors, every one `BLE001`; and `All checks passed!` for your own files | `-m ruff check .` |
| 17 | Accuracy and coverage, with their units | "N of N assertions hand-sourced, 0 from the code's output", and the coverage of what you added | `--cov` on the modules your tests name |

**Every criterion is a measurement, never an opinion.**

## Citations

- `.claude/agents/tester.md` — your role card. Its first section is the trap above.
- `.agent/assignments/P3c-one-number.md` — the unit you are testing, and the user's
  decision "1a" of 2026-10-05 quoted in full.
- `.agent/journal/2026-10-05T2244-programmer-p3c-one-number.md` — the programmer's entry,
  with all 22 red tests named and Group B's cause proved by execution.
- `.agent/journal/2026-10-06T1056-code_reviewer-p3c-one-number.md` — the review.
- `docs/2-rules/rules.md` — rule 3 (a missing value stops) and rule 6 (a shown assumption
  is shown for what it is).
- `docs/9-reference/refactor-backlog.md`, items 87, 92, 6, 97 (the unit) and 103 to 111
  (what its review found).

## Known open items

- **Backlog item 98**: `runpy.run_path` executes a module into a fresh namespace, so a
  patch on that module object is not the name the fresh copy binds. One sound `runpy` site
  exists, `tests/unit/test_pipeline.py:465`, because it patches `pipeline.fetch_price_data`
  and not an attribute of `cli`.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- **Backlog item 8**: a stop renders at HTTP 200, not 4xx. Assert on the body, not on the
  status.
- **`extractions/WMT.json` exists on this machine since 2026-10-06.** One test reads it.
  Do not delete it and do not edit it.
- The suite takes about 110 seconds.
