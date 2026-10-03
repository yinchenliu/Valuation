---
id: P11a-tests
phase: 11 — the model reads printed lines; Python does every sum
agent: tester
depends_on: [P11a-printed-lines]
---

# Rewrite the fixtures into the printed-lines shape, and lock what P11a changed

## Objective

`P11a-printed-lines` made every Pass 1 money field a list of printed rows
(`{"label", "value", "page"}`), with Python doing every sum, and made session files
`session-extraction-v2`. **40 tests fail** because their fixtures still use the old shape.
The round 1 review checked each of the 40 and found only that reason. The programmer's
round 2 entry `.agent/journal/2026-10-03T1048-programmer-p11a-printed-lines-r2.md` names
them, and lists the round 2 behaviours that need tests.

Read the assignment (both rounds), the run 3 and round 2 programmer entries, and both
review entries first.

## What to do

1. **Rewrite the 40.** Build every Pass 1 fixture and session file in the new shape.
   Write one helper that turns `{field: [values]}` into printed rows with labels and
   pages, so the fixtures stay readable. **No assertion about a figure may change**,
   except where the fixture now has two rows for one field and the expected sum is
   re-derived by hand in a comment.
2. **The sum.** A field of several rows equals their sum: Walmart-style capex rows
   26,642 and 53 give 26,695, stored as −26,695 (`docs/4-conventions/units-and-signs.md`).
3. **Empty lists, per the round 2 decisions:**
   - a catch-all `[]` is 0;
   - `total_assets: []` or `total_liabilities_and_equity: []` gives "not extracted": the
     check fails, and **no printed 0** appears in the check table, the CLI or the page;
   - `gross_profit: []` and `operating_income: []` skip their check and say "not printed";
   - `net_income: []` stops both routes, naming the year and the field, and **no 0
     reaches `CashFlowStatement.net_income`**.
4. **The balance check.** Printed totals that agree pass. A dropped row of 4,124 fails
   with the difference named, and the figures are kept. The tolerance is the one the code
   applies (`BalanceSheet.printed_total_tolerance()`), read from the code, not retyped. A
   difference of exactly the tolerance passes; one more fails.
5. **Route A's retries**, with `_call_llm` stubbed: the shape retry and the check retry
   send the PDF; the JSON repair retry does not; **the check retry text contains no gap
   amount and no total**; after the last retry a missing key stops and a failed check is
   kept.
6. **Stops:** a line without `label`, `value` or `page`; a non-finite or too-large
   `value`; a non-integer page; an absent key. Each names the field, year and line index.
7. **Formats:** a `session-extraction-v1` file stops naming both formats; a CLI cache
   with the old `CACHE_FORMAT` marker is refused.
8. **The outputs:** the CLI balance check prints `FAIL` on a failed check and `OK`
   otherwise, with no 2% tolerance; `templates/_statements.html` shows `FAIL` visibly.

Never read `10K_filings/`. Write PDFs as bytes under `tmp_path`. No test may reach the
API or the network.

## Files in scope

- any file under `tests/unit/`
- your journal entry

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the gate | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | the full suite | exactly 2 failures: the cases in `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` | the failure list from `.venv/bin/python -m pytest -q` |
| 3 | no assertion weakened | none removed or loosened in the 40 | `git diff` per file, summarised in your entry |
| 4 | the new tests can fail | break the sum, the totals' "not extracted", the net income stop, the tolerance and the retry wording in a copy under `/tmp/`, and show tests go red | paste it in your entry |
| 5 | lint | 5 errors, none in your files | `.venv/bin/python -m ruff check .` |
