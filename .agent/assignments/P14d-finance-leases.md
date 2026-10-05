---
id: P14d-finance-leases
phase: 14 — the Pass 1 role (the user's decision of 2026-10-04: "83a")
agent: programmer
depends_on: [P14b-note-figures]
---

# Finance lease obligations are debt; operating lease obligations are not. The Pass 1 schema says so (backlog item 83)

## Objective

The Pass 1 schema describes `short_term_debt` as "the current portion of LT debt, notes
payable and commercial paper rows" and `long_term_debt` as "long-term debt beyond 1
year" (`ingestion/claude_extractor.py`, `_FINANCIALS_BALANCE_SHEET_SCHEMA`). It does not
say where a finance lease obligation goes. Two models read the same Walmart 10-K
(2026-01-31, PDF page 22) and placed its two finance lease rows differently: Claude
(route B) put "Finance lease obligations due within one year 856" and "Long-term finance
lease obligations 5,905" in debt; Gemini (route A) put them in the catch-all liabilities.
Both balance sheets balance, so no check sees the difference. Net debt was 40,796M
against 34,035M, and WACC 7.68% against 7.74%.

**The user's decision of 2026-10-04: "83a"** — a finance lease obligation is debt. When
this unit is done, the schema and the prompt say: finance lease obligations are debt
(the current one in `short_term_debt`, the long-term one in `long_term_debt`); operating
lease obligations are not debt (the catch-all fields). Both routes read the same text.
Route B's Walmart file already maps the rows that way, so no Walmart figure moves.

## What is already true — verify, do not redo

Measured by the overall lead at `545d13b`.

| Fact | Source | Result |
|---|---|---|
| route B's Walmart mapping | `extractions/WMT.json`, `latest_balance_sheet` | `short_term_debt`: Short-term borrowings 6,596, Long-term debt due within one year 3,542, Finance lease obligations due within one year 856. `long_term_debt`: Long-term debt 34,624, Long-term finance lease obligations 5,905. Operating lease obligations 1,631 and 13,941 are in the two catch-all fields |
| the schema text | `_FINANCIALS_BALANCE_SHEET_SCHEMA` | `short_term_debt` and `long_term_debt` as quoted above; `other_non_current_liabilities` already names "operating lease liabilities" |
| net debt | `docs/3-architecture/valuation-math.md:180` | `net_debt = total_debt − cash_and_equivalents − short_term_investments` |
| Walmart, route B | `cli.py --session-file extractions/WMT.json`, keys empty | net debt 40,796; implied price $28.02 |

The gates at the `P14b-note-figures` commit, `ac4af5a`, measured by the overall lead with
`ANTHROPIC_API_KEY= GEMINI_API_KEY=` on macOS: gate 1066 passed (with and without the
prefix); full suite 2 failed (the two red on purpose), 1066 passed; ruff 4, all `BLE001`;
mypy 8 errors in 3 files; census 65; `GET /` 200; guard 48/48. `check
extractions/WMT.json` now also prints the check B1 line: `Row unit scales looked up on
their cited pages: 89 checked, 4 pages, 0 pages not confirmed.`

## What to do

1. **The schema** (`_FINANCIALS_BALANCE_SHEET_SCHEMA`).
   - `short_term_debt`: the current portion of long-term debt, short-term borrowings, notes
     payable and commercial paper rows, **and the finance lease obligations due within
     one year**, each as its own line. Not operating lease obligations.
   - `long_term_debt`: long-term debt beyond one year **and the long-term finance lease
     obligations**, each as its own line. Not operating lease obligations.
   - `other_current_liabilities`: add "operating lease obligations due within one year"
     to the rows it names.
   - `other_non_current_liabilities`: it names operating lease liabilities already; keep it.
2. **The prompt** (`_FINANCIALS_SYSTEM_PROMPT`, BALANCE SHEET RULES). Add one rule:
   finance lease obligations are debt (current in `short_term_debt`, long-term in
   `long_term_debt`); operating lease obligations are not debt and go to the catch-all
   fields. **Reason:** the user's decision "83a"; both models must place the same row in
   the same field.
3. **The CLI cache** (`cli.py`). Change `CACHE_FORMAT` to `"p14d-finance-leases-v1"`. A
   route A cache written before may hold finance leases outside debt. Change nothing else
   in `cli.py`.
4. **Docs.** `docs/3-architecture/data-contract.md`: what `short_term_debt` and
   `long_term_debt` hold, finance leases included, operating leases excluded.
   `docs/3-architecture/valuation-math.md`, at the net debt formula: `total_debt`
   includes finance lease obligations and excludes operating lease obligations, on the
   user's decision of 2026-10-04. `docs/3-architecture/extraction.md`: the Pass 1 rule.

## Files in scope

- `ingestion/claude_extractor.py`: `_FINANCIALS_BALANCE_SHEET_SCHEMA` and `_FINANCIALS_SYSTEM_PROMPT` only
- `cli.py`: the `CACHE_FORMAT` line only
- `docs/3-architecture/data-contract.md`
- `docs/3-architecture/valuation-math.md`
- `docs/3-architecture/extraction.md`
- your journal entry, `.agent/journal/<timestamp>-programmer-p14d-finance-leases.md`

**Nothing else.**

## Out of scope

- `analysis/`: `total_debt` and `net_debt` are unchanged; only what the extraction puts
  in the two fields changes.
- `extractions/WMT.json` and the `extract-filing` skill: the overall lead (the file already
  follows the rule; the skill gets the rule after acceptance).
- The session file format: unchanged. No key is added.
- `tests/`: the tester, in `P14d-finance-leases-tests`.
- A Gemini run that shows the model follows the rule: a paid call, not part of this unit.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. **Make no paid API call.**

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the schema names the rule | `short_term_debt` and `long_term_debt` name finance lease obligations; each names operating lease obligations as excluded; `other_current_liabilities` names operating lease obligations due within one year | `grep -n "finance lease\|operating lease" ingestion/claude_extractor.py`, each hit explained |
| 2 | both routes read the rule | the Pass 1 prompt that route B prints holds the new rule | `.venv/bin/python -m ingestion.session_extraction prompt extractions/WMT.json --filing 0 --pass 1`, grep for "finance lease" |
| 3 | route B's Walmart does not move | `check` exits 0; `short_term_debt` 10,994 (6,596 + 3,542 + 856), `long_term_debt` 40,529 (34,624 + 5,905); net debt 40,796; $28.02 | `session_extraction check extractions/WMT.json`; `cli.py --session-file extractions/WMT.json` |
| 4 | an old cache is refused | a pickle marked `p14b-pass2-units-v1` is refused, naming `p14d-finance-leases-v1` | `cli._load_cache` on a scratch pickle |
| 5 | the gates do not get worse | ruff, mypy and census no higher than at the `P14b-note-figures` commit; `GET /` 200 | the gate commands, with the empty-key prefix |
| 6 | every red test is named | expected causes only: tests that assert the old schema text or the old `CACHE_FORMAT`, and the 2 red on purpose | the full suite, failures grouped by cause |

## Citations

- The user's decision "83a", 2026-10-04; backlog item 83.
- `STATUS.md`, section 3: the Gemini run and the comparison with route B.
- `10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf`, PDF page 22: the two
  finance lease rows and the two operating lease rows.

## Known open items

- A 10-K that prints finance leases inside "Long-term debt" with no row of their own
  needs nothing: the printed row is already debt.

## Backlog items this unit is NOT fixing

Items 1, 10, 51, 53, 61, 63, 64, 73, 74, 78, 79, 80, 84, 85 in `claude_extractor.py`;
items 72 and 82 in `cli.py`.
