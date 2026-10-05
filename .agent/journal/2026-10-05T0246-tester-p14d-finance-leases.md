---
agent: tester
assignment: P14d-finance-leases-tests
round: 1
status: partial
files_touched:
  - tests/unit/test_p14a_units.py
  - tests/unit/test_p14b_units.py
  - tests/unit/test_p14d_finance_leases.py
  - .agent/journal/2026-10-05T0246-tester-p14d-finance-leases.md
verdict: pass
---

# P14d-finance-leases-tests — Lock finance lease obligations debt categorization, schema, prompt and cache format

> **Open this file before your first command. Fill it as each result lands.**
> An agent stopped mid-run with everything in context and nothing on disk has
> done no work.

## What I did

Updated existing CLI cache marker tests in `tests/unit/test_p14a_units.py` and `tests/unit/test_p14b_units.py` to expect `"p14d-finance-leases-v1"` and assert refusal of older markers. Added `tests/unit/test_p14d_finance_leases.py` locking:
1. `_FINANCIALS_BALANCE_SHEET_SCHEMA` categorization for `short_term_debt` (includes finance lease obligations due within one year, excludes operating lease obligations), `long_term_debt` (includes long-term finance lease obligations, excludes operating lease obligations), and `other_current_liabilities` (includes operating lease obligations due within one year).
2. `_FINANCIALS_SYSTEM_PROMPT` balance sheet rules explicitly distinguishing finance lease obligations (treated as debt) from operating lease obligations (not debt).
3. Cache format marker bumped to `"p14d-finance-leases-v1"`, and refusal of pickles with older markers (including `"p14b-pass2-units-v1"`) raising `ValueError` naming the expected marker.
4. Route B prompt generation in `session_extraction prompt` emitting the finance lease debt rules.
5. Route B Walmart extraction check and valuation exit 0 with debt line breakdown summing to `short_term_debt` 10,994M, `long_term_debt` 40,529M, `total_debt` 51,523M, `net_debt` 40,796M, and implied share price $28.02.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | gate form (0 failed) | | |
| 2 | full suite (exactly 2 red) | | |
| 3 | no assertion weakened | | |
| 4 | new tests can fail | | |
| 5 | lint | | |
| 6 | mypy | | |
| 7 | two counts | | |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|

## Rule 3 — what stops, and what does not

For every value this unit reads, one row. This is the table the reviewer checks first.

| Value read | If it were missing | Evidence |
|---|---|---|

## Measurements

## Expected values — testers only

| Assertion | Expected | Where the expected value came from |
|---|---|---|

## What I did not do

## Findings for the orchestrator
