---
id: P14d-finance-leases-tests
phase: 14 — the Pass 1 role (the user's decision of 2026-10-04: "83a")
agent: tester
depends_on: [P14d-finance-leases]
---

# Lock finance lease obligations debt categorization, schema, prompt and cache format

## Objective

`P14d-finance-leases` is approved. Finance lease obligations are debt (current portion in `short_term_debt`, long-term obligations in `long_term_debt`), and operating lease obligations are not debt (in `other_current_liabilities` and `other_non_current_liabilities`). The Pass 1 schema and system prompt state this rule. `CACHE_FORMAT` in `cli.py` is bumped to `"p14d-finance-leases-v1"`.

Read first:
- `.agent/assignments/P14d-finance-leases.md`
- Programmer entry: `.agent/journal/2026-10-05T0233-programmer-p14d-finance-leases.md`
- Code reviewer entry: `.agent/journal/2026-10-05T0245-code_reviewer-p14d-finance-leases.md`
- `.claude/agents/tester.md`

## What to do

1. **Repair existing cache format tests:**
   - In `tests/unit/test_p14a_units.py` and `tests/unit/test_p14b_units.py`, update tests asserting the old cache format marker so they expect `"p14d-finance-leases-v1"` and verify that older markers (such as `"p14b-pass2-units-v1"`) are refused.
   - **No existing numerical assertion may change**, unless re-derived by hand in a comment.

2. **Lock P14d unit behaviors in `tests/unit/test_p14d_finance_leases.py`:**
   - Schema descriptions: `_FINANCIALS_BALANCE_SHEET_SCHEMA` contains finance lease obligations in `short_term_debt` and `long_term_debt`, explicitly excludes operating lease obligations, and names operating lease obligations due within one year in `other_current_liabilities`.
   - Prompt rules: `_FINANCIALS_SYSTEM_PROMPT` contains the explicit rule that finance lease obligations are debt and operating lease obligations are not.
   - Cache format: `CACHE_FORMAT` is `"p14d-finance-leases-v1"`, and pickles with prior format markers (e.g. `"p14b-pass2-units-v1"`) raise `ValueError` naming `"p14d-finance-leases-v1"`.
   - Route B prompt generation: `session_extraction prompt` output contains the finance lease debt rules.
   - Route B Walmart extraction and valuation: check exits 0, debt line breakdown sums to `short_term_debt` 10,994M, `long_term_debt` 40,529M, `total_debt` 51,523M, `net_debt` 40,796M, and implied share price $28.02.

Never make paid API calls or real network calls in tests. All stubs/mocks in memory.

## Files in scope

- `tests/`
- `.agent/journal/<YYYY-MM-DDTHHMM>-tester-p14d-finance-leases.md`

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form | 0 failed (1066 passed) | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite | exactly 2 failures: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q` |
| 3 | no assertion weakened | none removed or loosened in repaired tests | `git diff` per file |
| 4 | new tests can fail | mutants in a scratch copy turn tests red | verify with mutants |
| 5 | lint | 4 errors (BLE001 pre-existing), 0 in `tests/` | `.venv/bin/python -m ruff check .` |
| 6 | mypy | 8 errors in 3 files, 0 in `tests/` | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` |
| 7 | two counts | accuracy and coverage reported | tester log entry |
