---
id: P9c-parse-tests
phase: 9 — two extraction routes, one parser
agent: tester
depends_on: [P9a-session-route]
---

# Test the parse layer both extraction routes now share

## Objective

`ingestion/` has **no tests at all** (`STATUS.md` section 1, caveat 2). That is where
the model's JSON turns into `FinancialStatements`, so every figure on every page passes
through untested code before it reaches the 100%-covered `analysis/`.

`P9a-session-route` made that code shared. Route A (API) and route B (session file) now
meet at `parse_pass1`, `parse_pass2`, `plan_filings` and `merge_filing_extractions`. So
one set of tests now covers the parsing for both routes. The user asked on 2026-10-02 to
make sure the statement parsing, the normalisation and the analysis work. The last two
are covered at 100%. This unit covers the first.

## What to test

Read `.agent/assignments/P9a-session-route.md`, the programmer's entry and the review
entry first. They name the functions and the stop list.

### 1. `parse_pass1`: values, from a JSON you write by hand

Build one `historical_years` entry from round numbers, so each expected value is a line
of arithmetic in a comment. Assert, at least:

- each income statement field lands on the matching `IncomeStatement` field;
- **EBIT is the same whichever line holds D&A.** The parser subtracts
  `depreciation_amortization` from `other_operating_expense` (`claude_extractor.py`,
  backlog item 10). Do **not** lock that subtraction as an expectation, because item 10
  will move it. Lock the identity that must survive the move instead: for a JSON whose
  stated `operating_income` reconciles to
  `revenue − cost_of_revenue − sga − rd_expense − other_operating_expense`, the parsed
  `IncomeStatement.ebit` equals that stated figure. Read `models/financial_statements.py`
  to confirm how `ebit` is derived before you write it;
- `CashFlowStatement.cash_from_operations` equals the JSON `cfo` exactly. The parser
  builds a residual so that it does;
- `capital_expenditures` is the **negative** of the JSON `capex`
  (`docs/4-conventions/units-and-signs.md`);
- every balance sheet field maps to its `BalanceSheet` field, when `latest_balance_sheet`
  is present;
- the arithmetic check returns an error that names the year and the field when the
  stated gross profit misses `revenue − cost_of_revenue` by more than 0.5%, and returns
  none when it reconciles.

### 2. `parse_pass2`: the three stops, and the empty answer

- `"non_recurring_items": []` gives `[]`;
- an absent `non_recurring_items` key raises `ValueError`, and the message says the
  reply was not a Pass 2 answer;
- an item with no `confidence` raises, naming the year and the description;
- an item with no `source` raises, naming the year and the description;
- an explicit `"source": ""` is accepted.

### 3. `plan_filings`

The routing table in `docs/3-architecture/extraction.md`, "Multi-PDF year routing":
one filing, and three filings given out of order. Assert the four fields of each
`FilingPlan`. An empty list raises.

### 4. `merge_filing_extractions`

- a year present in two filings takes the statement from the filing whose
  `fiscal_year` equals that year;
- two items with the same `(year, amount, direction)` from two filings appear once.

### 5. The two routes give the same result

For one filing and for three filings: feed the same Pass 1 and Pass 2 JSON through
route A, with `_call_llm` replaced by a stub that returns them, and through route B, as
a session file. Assert the `FinancialStatements` are equal and the item lists are equal.
**This is the Phase 9 constraint in one test.** The programmer proved it with a scratch
script. A test keeps it proved.

The session file needs PDFs to hash. Write any bytes to files under `tmp_path`.
Nothing in this test may read `10K_filings/`, which is not in git.

### 6. The session loader's stops

One test per row of the stop list in `P9a-session-route.md` step 10. Each asserts
`ValueError` **and** that the message names what the step says it names: the file, the
filing index or PDF name, and, where it applies, the year and the key.

Add one that the list implies: an explicit `0` for a schema key is **accepted**. A stop
on absence must not turn into a stop on zero.

**Two requirements the loader does not meet yet.** The `P9a` review (finding F1) found
them. Write both in `tests/unit/test_session_extraction_rule3_red.py`, where the gate
excludes them, with the review entry as the source:

- a `pass2` whose `non_recurring_items` is not a list must stop with `ValueError`,
  naming the file and the filing. Today it raises `AttributeError`;
- a Pass 2 item whose `amount` is `NaN` must stop, naming the filing, the year and the
  description. Today it loads, and the run stops only at the DCF with a message that
  names no item.

`P9d` will make them pass. Its tester moves them out of the red file.

### 7. The route label

A session extraction's `ProviderResolution` has `transport == "claude-code-session"`,
and `describe_resolution` of it names the session route and the declared model.

## Files in scope

- new test files under `tests/unit/`, named `test_<module>.py`
- `tests/unit/test_<module>_rule3_red.py`, only for a requirement the code does not yet
  meet
- your journal entry under `.agent/journal/`

**Never let a test reach the API.** `config.py` loads `.env` with `override=True`, so
`monkeypatch.delenv` on a key can be undone by a later `load_dotenv`. Replace
`ingestion.claude_extractor._call_llm` in every route A test, and make the stub raise if
it is called with anything it was not given.

## Out of scope

- every file outside `tests/` and your entry.
- `locate`. It needs a real PDF, and `10K_filings/` is not in git. Record it as a
  coverage gap. Do not commit a PDF.
- the CAPM test failure at `tests/unit/test_capm.py:473`. Held by the user.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the seven groups above exist | ≥ 1 test each | `pytest --collect-only -q tests/unit/test_<your files>` |
| 2 | every expected value has a written source | a comment on each assertion | reading the file |
| 3 | the gate | every new test passes, or sits in a `*_rule3_red.py` file with its reason | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 4 | coverage of the new and moved code | measured, not estimated | `.venv/bin/python -m pytest -q --cov=ingestion --cov-report=term-missing` with `COVERAGE_FILE` set under `/tmp/` |
| 5 | at least two tests can fail | break the line under test in a copy under `/tmp/`, show the test go red | paste both in your entry |

## Citations

- `docs/5-testing/strategy.md`: what a test here must do.
- `docs/4-conventions/units-and-signs.md`: the sign of each cash-flow field.
- `docs/3-architecture/extraction.md`: the routing table.
- `docs/2-rules/rules.md`, rule 3.
