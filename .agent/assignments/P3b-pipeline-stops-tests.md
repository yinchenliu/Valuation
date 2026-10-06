---
id: P3b-pipeline-stops-tests
phase: 3 — unify the pipeline (part 2)
agent: tester
depends_on: [P3b-pipeline-stops]
---

# Lock every behaviour `P3b-pipeline-stops` changed, with expected values derived by hand

## Objective

**The fact.** `P3b-pipeline-stops` closed backlog items 49 and 72. Its code reviewer
approved it after re-running all 17 done-criteria, and round 2 answered findings F1 and
F4. Not one of those measurements is a test: each was a command the programmer or the
reviewer ran by hand, and nothing in `tests/` fails today if the behaviour is reverted.

**What follows.** A revert of any part of this unit passes the suite. So the unit is not
locked, and the next change to either entry point can reopen item 49 with nothing to
report it.

When this unit is done, each behaviour below has a test whose expected value you derived
**before** you ran the code, and a mutation that reverts the behaviour turns a named test
red.

## What is already true — verify, do not redo

Measured by the overall lead on the **Windows** machine (`.venv/Scripts/python.exe`,
Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| gate, at `0a8ea54` on a clean export | `-m pytest -q --ignore-glob="*_rule3_red.py"` | 1107 passed, 5 skipped, 0 failed |
| full suite | `-m pytest -q` | 2 failed (the two red on purpose), 1107 passed |
| types | the mypy command in `docs/8-build/environment.md`, with `pipeline.py` | 5 errors in 2 files |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |

**The code you are testing is uncommitted** in five files: `ingestion/filings.py`,
`ingestion/claude_extractor.py`, `cli.py`, `api/routes_valuation.py`, `pipeline.py`.
Read `git diff` before you write a line.

**One test already exists and already passes**: `tests/unit/test_pipeline.py`,
`test_value_company_stops_on_a_missing_latest_balance_sheet`. It passed before this unit
through `calculate_wacc`'s later stop and passes now through the earlier one. **It does
not prove the new behaviour**: the new facts are that the stop happens **before**
`fetch_price_data` and that the message names `balance_sheet`, the ticker and the year.

**This machine holds no session file and no cached extraction.** `extractions/` is empty.
`10K_filings/` holds `ABBV/`, `LHX/` and `WMT/`. No end-to-end valuation of a real filing
is available, and no criterion below asks for one.

## What to do

Write tests for each behaviour below. **Derive every expected value from the formula, the
filing page, or the stated contract, before you run the code.** The first section of your
role card is the trap this repository has already met.

**Backlog item 49 — a filing with no fiscal year stops and is named.**

1. `require_fiscal_year_per_filing` raises for several filings when one has no year, and
   the message names **every** yearless file, not the first. Test two of three yearless.
2. It returns for: one filing with year 0; several filings that all have a year; an
   empty list (both callers stop on empty themselves, and the function does not own that
   rule).
3. A negative year counts as no year. The rule the assignment states is "a fiscal year
   above 0".
4. `parse_pdf_args` with two bare paths raises **before any PDF is opened**. Record the
   opens; do not take the absence of an error as proof.
5. `cli.main` with two bare paths exits non-zero with `ERROR:` and names both files, and
   neither `extract_financials` nor `extract_multi_year` is called.
6. `_run_extraction` with `files='0:a.pdf,2025:b.pdf'` raises, names `a.pdf`, and calls
   neither extractor.
7. `GET /assumptions` and `POST /valuation` with that same `files` value each render the
   message at HTTP 200 (backlog item 8 owns the status code) with the file name in the
   body.
8. **The filing that used to be dropped now reaches the extractor.** With three filings
   that all have a year, `extract_multi_year` receives all three, in both entry points.
   Before this unit, a `year > 0` filter stood between them. Assert on the argument the
   stub recorded.
9. A single bare path still reaches `extract_financials` in both entry points, with the
   path it was given. This unit changed nothing for one filing, and a test must hold that.

**Backlog item 72 — the CLI prints the debt balance WACC used.**

10. `value_company` stops when the latest fiscal year has no balance sheet: the message
    names `balance_sheet`, the ticker and the fiscal year, and **`fetch_price_data` is
    not called**. The twin matters as much: the same statements **with** a balance sheet
    do reach `fetch_price_data`, so the test proves the stop is the balance sheet's.
11. `ValuationRun.total_debt` equals the hand sum of the three debt lines. Use Walmart's
    fiscal 2026 balance sheet as printed on **page 22** of its 10-K, the same rows
    `tests/unit/test_p14d_finance_leases.py` already builds: short-term borrowings 6,596
    + long-term debt due within one year 3,542 + finance lease obligations due within one
    year 856 = **10,994**; long-term debt 34,624 + long-term finance lease obligations
    5,905 = **40,529**. Hand sum **51,523**. Write the arithmetic in the test.
12. The figure stage 8 prints is that same figure: capture the CLI's stage 8 output and
    assert the number, with market data stubbed.
13. The debt weight identity: `wacc_result.debt_weight == total_debt / (market_cap +
    total_debt)`. Derive both sides by hand from your stub's market cap. This is what
    makes criterion 11 mean "the figure shown is the figure used", not "two readings of
    one balance sheet agreed".

**The mutations.** Revert each behaviour in a scratch copy, run the suite, and record
which named tests go red. A behaviour whose revert turns nothing red is not locked.

14. Put the `valid = [(y, p) for y, p in filings if y > 0]` filter back in `cli.py`.
15. Put it back in `api/routes_valuation.py`.
16. Make `require_fiscal_year_per_filing` return without raising.
17. Put `total_debt = latest_bs.total_debt if latest_bs else 0` back in `cli.py` stage 8,
    with `ValuationRun.latest_balance_sheet` optional again.

**Restore the tree after every mutation.** `git diff` must show the same five files and
your `tests/` files, and nothing else, when you finish.

## Files in scope

- `tests/unit/` — new files, or additions to the existing ones. Name a new file for the
  unit, for example `tests/unit/test_p3b_pipeline_stops.py`.
- `tests/conftest.py` — only if a fixture belongs there. `P1b-windows-gate` put the one
  `_no_socket` fixture there; use it, do not write a second one.

**Nothing else.** The write guard denies every path outside `tests/`.

## Out of scope

- Every implementation file. If a test cannot be written without changing one, that is a
  finding: write it in your entry and stop. Do not change the code to make a test pass.
- Backlog items 93, 94, 95, and items 5, 8, 26, 87 to 92. Each is recorded.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | Every behaviour 1 to 13 has a test | 13 of 13, each named in your entry beside the behaviour | `-m pytest -q <your files>` |
| 2 | The gate is green | 0 failed | `-m pytest -q --ignore-glob="*_rule3_red.py"` |
| 3 | The full suite shows only the two deliberate failures | 2 failed | `-m pytest -q` |
| 4 | Each of the four mutations turns a named test red | 4 of 4, with the names | the mutation runs |
| 5 | Coverage of the new function | 100% of `require_fiscal_year_per_filing`'s statements and branches | `coverage run --branch -m pytest ...` then `coverage report --include="ingestion/filings.py"`. Set `COVERAGE_FILE` to a path in the scratchpad first |
| 6 | Accuracy count | every assertion's expected value derived by hand, and the count stated | your entry: N of N, and the source of each |
| 7 | Nothing outside `tests/` changed | every path starts with `tests/`, beside the five files of the code unit | `git status --porcelain` |
| 8 | Lint | 4 errors, every one `BLE001` | `-m ruff check .` |

**Every criterion is a measurement, never an opinion.**

## Citations

- `.claude/agents/tester.md` — your role card, and the trap it opens with: running the
  code, reading the output, and asserting that.
- `.agent/assignments/P3b-pipeline-stops.md` — the unit, its 18 criteria and the round 2
  amendment.
- `.agent/journal/2026-10-05T1625-code_reviewer-p3b-pipeline-stops.md` — the review, and
  the two things it told the overall lead.
- `10K_filings/WMT/` — Walmart's fiscal 2026 10-K, page 22, for the debt rows in
  behaviour 11.
- `docs/2-rules/rules.md` — rules 3 and 5.

## Known open items

- Backlog item 75: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- The suite takes about 135 seconds. Measure once, not after every edit.
- `tests/unit/test_pipeline.py:386` already holds a test for the missing balance sheet.
  Extend it or write beside it; do not duplicate its name.

---

## Round 2 amendment (overall lead), 2026-10-05

**The fact.** Round 1 stopped before it finished. `tests/unit/test_p3b_pipeline_stops.py`
holds 825 lines and 24 test functions, and
`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe -m pytest -q tests/unit/test_p3b_pipeline_stops.py`
gives **25 passed** (measured by the overall lead, 2026-10-05). But
`.agent/journal/2026-10-05T1747-tester-p3b-pipeline-stops-tests.md` says
`status: in progress` and `verdict: pending`, and every evidence table in it is empty.

**What follows.** Not one of criteria 1 to 8 is measured. The four mutations did not run,
so **no behaviour in this unit is known to be locked**. A test that passes proves the code
agrees with the test today. Only the mutation proves the test would report a revert.

**You did not write these tests.** Do not assume the round 1 session derived any expected
value by hand. Check each one yourself, from the formula, the filing page or the stated
contract, and say in your entry which of the three each assertion came from.

### What to do in round 2

1. **Audit every assertion in `tests/unit/test_p3b_pipeline_stops.py`.** For each, name
   its source: the stated contract, a figure read off a filing page, or hand arithmetic.
   **If an assertion's expected value could only have come from running the code, say so
   and replace it with a hand-derived one.** That is this repository's named trap and the
   first section of your role card.
2. **Check the Walmart page 22 figures against the PDF**, `10K_filings/WMT/`. The file
   header claims 6,596 + 3,542 + 856 = 10,994 and 34,624 + 5,905 = 40,529, hand sum
   51,523. Confirm each row on the page, or report the difference.
3. **Map behaviours 1 to 13 of this assignment to test names.** Name the test beside each
   behaviour. A behaviour with no test is a finding: write the test.
4. **Run the four mutations (14 to 17) and record which named tests go red.** A mutation
   that turns nothing red is a finding, not a note. Restore the tree after each one, and
   prove it is restored with `git status --porcelain`.
5. **Measure criteria 2, 3, 5, 7 and 8** exactly as the table states them.
6. **Fill the entry.** Replace the placeholder file with the real one: frontmatter
   `status: complete`, a verdict, every evidence table filled, and the accuracy count
   (N of N, with the source of each).

### Criterion 9, new (round 2)

The two helper modules the file imports, `tests/unit/_fiscal_year_stub.py` and
`tests/unit/_session_route_helpers.py`, are already in git and this unit must not change
them. Measure it: `git status --porcelain tests/` names
`tests/unit/test_p3b_pipeline_stops.py` and nothing else under `tests/unit/`, beside any
file you add in step 3.

---

## Overall lead review, 2026-10-05

**Accepted.** The tester returned `pass`. I re-ran its measurements rather than reading
them, on the Windows machine (`.venv/Scripts/python.exe`, Python 3.14.4), with
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| What | My result | The tester's claim |
|---|---|---|
| gate, `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1136 passed, 5 skipped, 0 failed** | the same |
| full suite, `-m pytest -q` | **2 failed, 1136 passed, 5 skipped**, and the 2 are the two red on purpose | the same |
| the new file alone | 29 passed | the same |
| lint | 4 errors, every one `BLE001` | the same |
| types | 5 errors in 2 files | the same |
| census | 64 | the same |
| `GET /` | 200 | — |
| write guard | 48/48 | — |
| `git status --porcelain` | the five code files, four `.agent` files, the backlog, and `tests/unit/test_p3b_pipeline_stops.py`. Nothing else | the same |

**I re-ran mutation 16 myself**, because a mutation nobody repeats is a claim. I inserted
`return` as the first statement of `require_fiscal_year_per_filing`, ran the new file
alone, and restored the file from a copy, confirmed byte-identical with
`filecmp.cmp(shallow=False)`. Result: **12 failed, 17 passed**, and the 12 names are
exactly the 12 the tester lists. So item 49's stop is locked.

**The three audit findings are the reason this round was worth running.** A1 is the one
that matters: round 1's CLI stop test ran `cli.py` through `runpy.run_path`, which
executes the file into a fresh namespace, so `monkeypatch.setattr(cli,
"extract_financials", ...)` patched a name that namespace never bound. The assertion
`cli_extractor_calls == {"single": [], "multi": []}` was then true whatever the code did.
**A test that cannot fail is worse than no test**, because the gate reports it green.

**Finding 5 checked by me, and it is narrower than the tester could see.** `grep -rn
runpy tests/ --include=*.py` gives one other live site,
`tests/unit/test_pipeline.py:465`. That one is sound, and the reason is a difference the
backlog item must state: its fixtures patch `pipeline.fetch_price_data`
(`tests/unit/test_pipeline.py:132`) and yfinance, not an attribute of `cli`. `cli.py:64`
holds `from pipeline import adjust_financials, value_company`, so the fresh namespace
re-binds the same function object, and `value_company` reads `fetch_price_data` from
`pipeline`'s globals at call time, where the patch is. The trap is real; that site does
not fall into it. Recorded as backlog item 98.

**Findings recorded, not fixed here:** item 98 (`runpy` and monkeypatching), item 99
(`api/routes_valuation.py:199`, the legacy `file_path` branch, reached by no test and not
guarded by `require_fiscal_year_per_filing`), item 100 (a filing citation must give the
printed page and the PDF index, not one number for both).

The unit and its tests are committed together, because the code was never committed on
its own.
