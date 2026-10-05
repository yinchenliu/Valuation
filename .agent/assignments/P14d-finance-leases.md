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

## Handoff

Written by the overall lead in one-team mode (`.agent/QUEUE.md`, from 2026-10-05).

### Commits
- `78d21c4`: the build team's programmer and code reviewer runs (Antigravity, Gemini), and its partial tester run, committed as found on the user's decision "2a".
- `9e49bef`: the Claude tester, round 2.

### Verdicts
- Programmer: `complete` (Gemini), `.agent/journal/2026-10-05T0233-programmer-p14d-finance-leases.md`
- Code reviewer: `approved` (Gemini), `.agent/journal/2026-10-05T0245-code_reviewer-p14d-finance-leases.md`
- Tester, round 1: `partial` (Gemini; the quota ran out; every evidence table empty), `.agent/journal/2026-10-05T0246-tester-p14d-finance-leases.md`
- Tester, round 2: `pass` (Claude), `.agent/journal/2026-10-04T2330-tester-p14d-finance-leases.md`

### Gates
All with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`, macOS, at `9e49bef`:
- Gate form: 1092 passed (`.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`)
- Full suite: 2 failed (the two red on purpose), 1092 passed (`.venv/bin/python -m pytest -q`)
- Clean checkout (a worktree with no `extractions/` and no `10K_filings/`): gate 1087 passed, 5 skipped
- ruff: 4 errors, all `BLE001`; mypy: 8 errors in 3 files; census: 65; `GET /`: 200; guard: 48/48

### Findings and notes
- The tester's finding 1: the comment above `CACHE_FORMAT` (`cli.py:229-237`) names only the P11a and P14a marker changes. The assignment allowed only the `CACHE_FORMAT` line, so it is not against this unit.
- The tester's finding 2: tests criterion 5 says "0 in `tests/`", but `tests/test_e2e_all_googl.py:106` has always held one of the four `BLE001` errors. The criterion was wrong, not the tests.
- The tester's finding 3: the Claude tester's entry is stamped with the local clock (23:30 EDT) and the Gemini entries a few hours ahead, so the newer entry sorts first.

### Questions for the overall lead
None.

## Overall lead review

**Verdict: `accepted`**, 2026-10-05, by the overall lead, on `9e49bef`.

**Scope.** `78d21c4` and `9e49bef` touch the five files in scope (the schema and prompt
only in `ingestion/claude_extractor.py`, the `CACHE_FORMAT` line only in `cli.py`, the
three docs files), three test files, the journal and the tests assignment. The model
returns no new field.

| # | Result, re-run with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` |
|---|---|
| 1 | `grep -n -i "finance lease\|operating lease" ingestion/claude_extractor.py`: `short_term_debt` and `long_term_debt` name finance lease obligations and say "Not operating lease obligations"; `other_current_liabilities` names operating lease obligations due within one year; the prompt rule at `:341-345` |
| 2 | `session_extraction prompt extractions/WMT.json --filing 0 --pass 1` holds the schema text and the prompt rule |
| 3 | `check extractions/WMT.json` exit 0; `cli.py --session-file`: ST debt 10,994, LT debt 40,529, total debt 51,523, net debt 40,796, $28.02; output identical to the `P14b-note-figures` run but for the elapsed seconds. Page 22 of the Walmart PDF prints 6,596, 3,542, 856, 34,624 and 5,905, the figures the tests cite |
| 4 | a scratch pickle marked `p14b-pass2-units-v1` is refused, naming `p14d-finance-leases-v1` |
| 5 | ruff 4, mypy 8 in 3 files, census 65, `GET /` 200, guard 48/48 |
| 6 | full suite 2 failed, the two red on purpose |

**The tests.** On a clean checkout the P14d test file gives 25 passed and 1 skipped. With
the prompt rule deleted from a scratch copy, 3 of its tests go red.

**No finding against this unit.** The stale `CACHE_FORMAT` comment is backlog item 86.
