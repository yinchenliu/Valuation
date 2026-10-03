---
id: P10-tests
phase: 10 — the user's fixes of 2026-10-02 (items 43, 45, 48)
agent: tester
depends_on: [P10a-nci-bridge, P10b-capm-variance, P10c-fiscal-year]
---

# Test the three Phase 10 fixes, and repair the fixtures they turned red

## Objective

Three units changed behaviour on purpose, and existing fixtures do not meet the new
requirements:

- **`P10a-nci-bridge`** (item 48). The balance sheet holds two printed lines,
  `noncontrolling_interest_nonredeemable` and `noncontrolling_interest_redeemable`.
  `analysis/dcf.py:total_noncontrolling_interest` sums them and stops on `None` or NaN.
  The equity bridge subtracts the total. `run_dcf` stops when the latest balance sheet
  is missing (this closed item 2). **31 tests fail** because their fixtures or session
  files lack the two keys. The round 2 entry
  `.agent/journal/2026-10-02T2141-programmer-p10a-nci-bridge-r2.md` names them.
- **`P10b-capm-variance`** (item 45). The constant-market stop now runs before SciPy.
  The existing test passes; the message's other parts are untested.
- **`P10c-fiscal-year`** (item 43). Every filing that carries a year is verified against
  its cover date and its income statement column label. **5 tests fail** because they
  give a year with bytes that are not a filing. The entry
  `.agent/journal/2026-10-02T2127-programmer-p10c-fiscal-year.md` names them.

Read the three assignments, their programmer entries and their review entries first.
**No stop may be weakened to make a test green.** Repair the fixture instead.

## What to do

1. **Repair P10a's 31.** Give each balance sheet fixture both keys explicitly: `0.0`
   where the fixture's company has none (an explicit zero is a value, not a default),
   and round numbers where a test checks the bridge. Add both keys to every hand-written
   session file and to the literal list in
   `test_session_extraction.py::test_the_required_key_lists_are_the_schema`.
2. **Repair P10c's 5.** Each passes a year with fake PDF bytes. Either pass year 0 where
   the test is about something else, or replace the evidence reader
   (`ingestion.filings.read_fiscal_year_evidence`) with a stub that returns evidence
   matching the year. Say which, per test, in your entry.
3. **Move item 2's test** from `test_dcf_rule3_red.py` into `test_dcf.py`, unchanged in
   what it asserts, and delete the red file.
4. **P10a, new tests:** the bridge with round numbers (EV 1,000, net debt 200,
   nonredeemable 40, redeemable 10, 10 shares: equity 750, price 75.0, arithmetic in a
   comment); `total_noncontrolling_interest` stops on `None` and on NaN in each part,
   naming the key and the year; the parser gives `None` for an absent key, never `0.0`;
   neither part changes `total_assets`, `total_liabilities`, `total_equity` or the
   balance check.
5. **P10b, new tests:** the constant-market message names the repeated value and the
   count; a NaN observation still reaches the NaN stop.
6. **P10c, new tests**, against the **round 2** rule in `P10c-fiscal-year.md`:
   `fiscal_year_from_evidence` on strings, one case per row of the table there, plus a
   Target-style case (cover "February 1, 2025", label 2024 → 2024), a bare label outside
   the cover year and the year before (stops, naming label, cover date and pages), and
   date-only labels in the first seven days of January (the year before);
   `verify_filing_years` with a stubbed reader stops on a mismatch, names the file, both
   years and the remedy, and lists every bad filing in one message; an unreadable cover
   stops under its own heading, not "does not match"; the CLI remedy names `YEAR:PATH`
   and the web remedy says to rename and upload again; `POST /upload` with a mismatch
   answers 400 and does not redirect. **Never read
   `10K_filings/`**, which is not in git.

## Files in scope

- any file under `tests/unit/`
- `tests/unit/test_dcf_rule3_red.py`, to delete it
- your journal entry

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the gate | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | the full suite | exactly 2 failures: the cases in `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` | the failure list from `.venv/bin/python -m pytest -q` |
| 3 | no stop weakened | no assertion removed or loosened in the 36 repaired tests | `git diff` on each repaired file, summarised in your entry |
| 4 | the new tests can fail | break the bridge, one NCI stop, the January rule and the CAPM pre-check in a copy under `/tmp/`, and show tests go red | paste it in your entry |
| 5 | lint | 5 errors, none in your files | `.venv/bin/python -m ruff check .` |
