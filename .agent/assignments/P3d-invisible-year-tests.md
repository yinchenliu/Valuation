---
id: P3d-invisible-year-tests
phase: 3 — unify the pipeline (part 4)
agent: tester
depends_on: [P3d-invisible-year]
---

# Tests for `P3d-invisible-year`: a year any statement covers is visible, and the branch written to report it runs

## Objective

`P3d-invisible-year` is written and its code reviewer approved it at round 2. **Nothing
in `tests/` covers any of it.** The round 1 programmer says so itself: the new stop, both
newly-reachable branches, the third `_build_ebit_reconciliation` branch, the
balance-sheet-only CLI path and the `income_statement_years` property are exercised today
**only by a probe script in `C:\tmp` that is not committed**. A probe that lives outside
the repository proves the code once and guards it never.

**The fact that forced the unit.** `FinancialStatements.years` was built from
`self.income_statements` alone. So a year that had a cash flow statement and a balance
sheet but no income statement was in no table, carried no reason, and nothing anywhere
reported it. Both entry points held a branch written to report exactly that case
(`cli.py` and `api/routes_valuation.py`), and neither could run, because both iterate
that list. Backlog item 116.

**What the unit did.** `years` is now the union of all three statement kinds.
`income_statement_years` is a new property beside it, holding only the years that have an
income statement. `latest_year` reads the narrow set. `analysis/projector.derive_assumptions`
reads the wide set through a new `_income_statements_for_years`, which **stops and names
the field and the year** when a covered year has no income statement.

**When this unit is done, a test fails if any of that is undone.**

## The trap this repository puts in front of you, stated first

**There is no benchmark in this repository.** No trustee file, no signed reference, no
published figure. So the only thing that makes your expected values worth anything is
that you computed them **before** the code ran, from the formula.

**Running the code, reading the output and asserting that is the one failure mode that
passes forever.** `.claude/agents/tester.md` spends its first section on it. Read that
section before you write a line.

**Three numbers in this unit have a hand-derivable answer and you must derive all three
by hand:**

1. The CAGR the invisible year distorted. `(1200/1000)^(1/1) - 1` against
   `(1200/1000)^(1/2) - 1`. Work both out yourself and say which the code must now
   refuse to produce.
2. The column at which the blank net-margin cell starts. `_pct` emits `w` characters of
   number and then a `%`, so a blank of `w` pulls the row one character left. Derive the
   width from the format string, not from a printed row.
3. Every figure in the historical FCFF rows of the complete years, which must not move.

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-07, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`,
on the working tree that holds rounds 1 and 2:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1224 passed, 2 skipped, 0 failed** |
| full suite | `-m pytest -q` | **2 failed**, the two red on purpose, by name |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 2 errors in 2 files, 21 checked |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.claude/check_guard.py` | 48/48 |

**If one of these disagrees when you run it, stop and report the disagreement.** Do not
edit anything to make it agree.

**There is no test-order guard on this machine.** `pytest-randomly` is not installed, so
every run uses one fixed order, and that gap is backlog item 127, not yours to fix. **Do
not add `-p no:randomly` to any command**: it was deleted from every live document on the
user's decision of 2026-10-07 because it asserted nothing (item 126, closed). **What it
means for you**: compare two runs by the **set of failing test names**, never by count.

**Read these three entries before you start.** They hold the probe shapes, the mutations
already tried, and the reasons behind each decision, so you do not rediscover them:

- `.agent/journal/2026-10-07T1101-programmer-p3d-invisible-year.md` — round 1.
- `.agent/journal/2026-10-07T1156-programmer-p3d-invisible-year-r2.md` — round 2.
- `.agent/journal/2026-10-07T1420-code_reviewer-p3d-invisible-year-r2.md` — the approving
  review, which holds the five table shapes it tried and the `LATEBS` filing.

## What to do

1. **Build the probe filing as a fixture, in the repository.** Three fiscal years: 2023
   and 2025 complete, 2024 with a cash flow statement and a balance sheet and **no income
   statement**. This is the shape the whole unit exists for, and today it lives only in
   `C:\tmp`.
2. **Test the property pair.** `years` holds every year any statement covers.
   `income_statement_years` holds only the years with an income statement. The second is a
   subset of the first. `get_income_statement(y)` returns a statement for every year in
   the narrow set and `None` for a year that is in the wide set and not the narrow one.
3. **Test the stop by name.** `analysis/projector.derive_assumptions` on the probe filing
   raises, the exception names the **field** and the **fiscal year**, and the type is not
   `AttributeError`. **Assert the type as well as the message.** An `AttributeError` here
   is the cheapest wrong answer and it is what this criterion exists to catch.
4. **Test both dead branches, both now reachable.** `cli.print_historical_fcff` prints a
   row for 2024 naming the income statement, and
   `api/routes_valuation._historical_fcff_by_year` returns a row for 2024 whose `missing`
   names it. **Both entry points, not one.** A figure verified in one is not verified in
   the other.
5. **Test that the two entry points say the same words**, for the FCFF row and for the
   reconciliation. Round 2 made the reconciliation phrases identical
   (`not extracted: raw and adjusted income statement`). A test that lets them drift apart
   again is not a test.
6. **Test `latest_year`'s message on a filing with a balance sheet and no income statement
   at all.** `years` is non-empty, the property still raises, and the message is true when
   it prints.
7. **Test the net-margin cell and its absence line together.** The cell holds no figure at
   revenue 0, the column alignment holds with the zero-revenue year in the middle of
   three, and the line under the table names the year, the field and the reason.
   **The reviewer's N1 says nothing enforces that the two are called as a pair.** Write the
   test that would fail if a later edit called the table without the absence line.
8. **Test that no figure moves for a filing whose years all have an income statement.**
   This is the regression guard for every current input. Hand-source the expected figures.
9. **Mutate your own tests and record what each mutation kills.** At least these four, each
   in its own scratch tree, never in the repository:
   - `years` back to the income statements alone. Your suite must go red.
   - `_income_statements_for_years` skipping the year instead of stopping. Your suite must
     go red, and the test that catches it must be the one about the growth rate, not only
     the one about the exception.
   - `latest_year` reading the wide set. Your suite must go red.
   - the net-margin blank widened to `w` instead of `w + 1`. Your suite must go red.
   **A mutation your suite survives is a hole, and you report it rather than hide it.**
10. **Count what you covered, do not estimate it.** Intersect a `--cov-branch` report with
    the added line numbers from `git diff -U0`. Report statements covered and statements
    missed as counts, with the command.

## Files in scope

- `tests/` only.

**Nothing else.** The write guard denies the rest, and a tester that may edit the code it
judges is not a tester.

## Out of scope

- **Every file the unit changed.** If you believe the implementation is wrong, say so in
  your entry and return `fail`. Do not fix it.
- **The two tests that are red on purpose.** Leave both red.
  `tests/unit/test_projector_rule3_red.py`'s input has no statements of any kind, so
  `years == []` on both trees and the bare `IndexError` survives. That is backlog item 14's
  twin, a different defect from item 116.
- **Backlog item 127**, the absent test-order guard. Named above so you compare failing
  sets by name and never by count.
- **The reviewer's N2, N3 and N4**, and the round 2 programmer's four findings. Each is
  recorded. Do not widen your scope to them.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | Every expected value is hand-sourced | a count of assertions, and how many came from the code's output | **the second number must be 0.** State both in your entry |
| 2 | The three hand-derived numbers | the CAGR pair, the cell width, the unchanged FCFF figures | show the arithmetic, not the printed result |
| 3 | The property pair is covered | `years`, `income_statement_years`, and `get_income_statement` on a year in one and not the other | your tests |
| 4 | The stop names the field and the year | the type is `ValueError`, not `AttributeError`, and the message holds both | your tests |
| 5 | Both dead branches are covered, in both entry points | two tests, one per entry point | your tests |
| 6 | The two entry points say the same words | a test that fails if either phrase moves | your tests |
| 7 | `latest_year`'s message is true when it prints | a filing with a balance sheet and no income statement | your tests |
| 8 | The net-margin cell and its absence line are covered as a pair | a test that fails if the table is printed without the absence line | your tests, and N1 |
| 9 | No figure moves for a filing whose years all have an income statement | the figures, hand-sourced | your tests |
| 10 | Four mutations, each killed | for each: the mutation, the command, the failing count and the **names** of the tests that went red | your own scratch trees. **Report any mutation your suite survives** |
| 11 | Coverage of what the unit added | statements covered and statements missed, as counts | `--cov-branch` intersected with `git diff -U0`. Not an estimate |
| 12 | The gate | **1224 passed plus your new tests, 2 skipped, 0 failed** | `-m pytest -q --ignore-glob="*_rule3_red.py"` |
| 13 | The failing set | unchanged, compared **by name** | the gate form, before and after |
| 14 | Lint | 4 errors, every one `BLE001`. **Run `ruff check .` after your last edit** | `-m ruff check .` |
| 15 | The write guard | 48/48 | `.claude/check_guard.py` |

**Criterion 14 has its own history.** `P3c-one-number-tests` reported lint as "4
`BLE001`" and, beside it, "`All checks passed!` over my five files". Both cannot be true.
The acceptance re-run found a fifth error, `C402`, in a file that tester had written: it
ran ruff over its own files, then added two more tests, and never re-ran lint. **Run lint
after your last write, not beside the edit that prompted it.**

## Citations

- `.claude/agents/tester.md` — your role card. Its first section is the trap above.
- `docs/2-rules/rules.md` — rule 3 (a missing input stops and names itself).
- `docs/9-reference/refactor-backlog.md`, item 116.
- `.agent/assignments/P3d-invisible-year.md` — the unit, its fifteen criteria, and the
  `## Overall lead ruling on review round 1` that settles why two margin rows still print
  `0.0%`.
- `models/financial_statements.py` — `years`, `income_statement_years`, `latest_year`.
- `analysis/projector.py` — `_income_statements_for_years`, the stop.

## Known open items

- **Never mutate a file in this repository, not even briefly.** A spot check left a
  `return []` in `ingestion/claude_extractor.py` on 2026-10-05 with a comment saying it had
  been restored. It had not, and a check was dead for about ten hours. Work in a scratch
  copy under `C:\tmp` and print the repository file's sha256 before and after. `git stash`
  is forbidden.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- **`extractions/WMT.json` is not in git.** Three filings, five fiscal years, 2022 to 2026,
  balance sheet on `filings[2]`. Do not edit it and do not delete it.
- The suite takes about 135 to 225 seconds.

## Backlog items this unit is NOT fixing

- **Item 1**, the 64 silent zero-default sites, including
  `models/financial_statements.py:108` (`gross_margin`) and `:132` (`operating_margin`).
  Those two make `Gross Margin` and `EBIT Margin` print `0.0%` for a zero-revenue year,
  one line above the net-margin row that now says it cannot compute. **That difference is
  deliberate and the overall lead's ruling records why.** Do not test for it being fixed,
  and do not report it as a defect in this unit.
- **Item 8**, the blanket `except Exception` in both entry points. Four sites, each
  recorded. Do not rely on them in a test.
- **Item 41**, the unreachable `0.05` growth rate in `analysis/projector.py`.
- **Item 127**, the absent test-order guard.
