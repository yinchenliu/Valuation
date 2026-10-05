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

## Round 2 amendment (overall lead, one-team mode)

**Why a second tester run.** The first tester run (Gemini) stopped part way when the
build team's quota ran out. Its entry,
`.agent/journal/2026-10-05T0246-tester-p14d-finance-leases.md`, says `status: partial`,
and every evidence table in it is empty. Its three test files are committed as found at
`78d21c4`. You continue from them. Write a new entry. Do not edit the old one.

**Three findings in the committed tests. Answer each by number in your entry.**

- **T1. One test asserts the code's own output.**
  `test_route_b_walmart_valuation_share_price_ties_to_28_02` patches CAPM and the price
  with values copied from a run (beta `0.5662169972765607`, equity risk premium
  `0.06892192021225155`, price `104.26000213623047`). Its docstring takes enterprise
  value 272,116M as given, not derived. That is the trap in the first section of
  `.claude/agents/tester.md`. Delete the test, or replace it with one whose expected
  value is derived by hand from inputs you choose. The Walmart end-to-end price is done-criterion 3 of
  `P14d-finance-leases`, and the overall lead measures it. It is not a unit test.
- **T2. Four tests read a file that git does not track.** `.gitignore` ignores
  `extractions/` and `10K_filings/`. `test_route_b_cmd_prompt_exits_zero_and_emits_lease_rules`,
  `test_route_b_walmart_session_check_exits_zero`,
  `test_route_b_walmart_debt_lines_breakdown_by_hand_arithmetic` and the T1 test read
  `extractions/WMT.json`. On a machine without that file, they fail. For the debt
  arithmetic, build the input inside the test from the figures printed on Walmart's PDF
  page 22, cited in a comment, so that the test runs on every machine. A test that still
  needs the real session file or a real PDF carries
  `pytest.mark.skipif(not path.exists(), reason=...)`, as
  `tests/unit/test_p14b_note_figures.py:874` does.
- **T3. Every other test, checked against the tester card.** For each test in the three
  files, the expected value must exist before the code runs. In your entry, list each
  test that you keep, change or delete, with the reason.

**Done-criteria.** The table above holds, with one change: criterion 1 expects 0 failed,
and the passed count is whatever the suite now holds. Criterion 4 (mutants) covers the
schema text, the prompt rule and the cache marker: a scratch copy without each one must
turn a test red. Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`.
