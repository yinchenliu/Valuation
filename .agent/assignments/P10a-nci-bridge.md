---
id: P10a-nci-bridge
phase: 10 — the user's fixes of 2026-10-02 (items 43, 45, 48)
agent: programmer
depends_on: []
---

# Subtract noncontrolling interest in the equity bridge

## Objective

The Pass 1 schema asks for **consolidated** net income, which includes the share that
belongs to noncontrolling interests, and for total equity including them. So the
projected cash flows value the whole group. `analysis/dcf.py` then goes from enterprise
value to equity value by subtracting net debt only (`models/valuation.py:319-320`). The
minority holders' share is never subtracted, and the schema has no field that could hold
it. Backlog item 48.

Measured on the Walmart fiscal 2026 session file: nonredeemable noncontrolling interest
6,270 plus redeemable noncontrolling interest 293 (PDF page 22) = 6,563, divided by 8,022
diluted shares = about $0.82 of the $28.84 implied price.

**The user approved this change to the LLM boundary on 2026-10-02** ("item 48: fix").
`AGENTS.md` requires that approval for a new field the model is asked to read. Cite it in
your entry.

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Fill in the commit from `git log --oneline -1`.

| Fact | Command | At `c17ae41` |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 397 passed, 1 failed (`test_capm.py:473`, which `P10b` fixes in parallel) |
| lint, types | the two gates in `docs/8-build/environment.md` | ruff 5, mypy 10 in 4 files |
| the bridge subtracts net debt only | `grep -n "def equity_value" -A 3 models/valuation.py` | `enterprise_value - net_debt` |
| the balance sheet schema | `grep -n "_FINANCIALS_BALANCE_SHEET_SCHEMA" -A 20 ingestion/claude_extractor.py` | 17 keys, no noncontrolling interest |
| route B derives its key list from that schema | `grep -n "PASS1_BALANCE_SHEET_FIELDS" ingestion/*.py` | so a new schema key is required in session files with no code change there |

## What to do

1. **The schema.** Add `"noncontrolling_interest"` to the balance sheet part of the Pass 1
   schema in `ingestion/claude_extractor.py`. Describe it in the schema text as: the book
   value of **all** noncontrolling interests on the latest balance sheet, the
   nonredeemable amount in equity **plus** any redeemable amount shown outside equity;
   0 if the filing reports none; a memo figure that is already inside `total_equity` or
   another line, never added to any total. Add one line to the balance sheet rules in the
   system prompt saying the same. **Change no other prompt text.**

2. **The parser.** Read the key in `_parse_financials_response`. **Do not add a
   `.get(..., 0)`.** Backlog item 1 counts 116 such sites, and this unit must not add a
   117th. When the key is absent, the field is `None`, which means "not extracted".

3. **The model.** Add `noncontrolling_interest: float | None = None` to `BalanceSheet` in
   `models/financial_statements.py`. `None` is not a zero default: it is the absence, and
   step 4 stops on it. It is **not** part of `total_assets`, `total_liabilities`,
   `total_equity` or the balance check.

4. **The bridge.** `run_dcf` subtracts the latest balance sheet's
   `noncontrolling_interest` from enterprise value after net debt. When it is `None`,
   `run_dcf` raises `ValueError` naming the field and the balance sheet year (rule 3).
   Carry the figure on `DCFResult` as its own field, so `equity_value` is
   `enterprise_value - net_debt - noncontrolling_interest` and every reader can see each
   term. **No zero default on the new `DCFResult` field.** If the dataclass field order
   forces a default, use `field(kw_only=True)` with no default.

5. **The output.** Show the new term wherever the bridge is shown, with its source:
   - `cli.py`: the DCF block ("Less: Noncontrolling interest", beside "Less: Net Debt"),
     and the balance sheet block as a memo line;
   - `templates/valuation_result.html`: the bridge;
   - `templates/_statements.html`: the balance sheet block, as a memo line. A `None`
     prints `not extracted`, never `0` or a blank (`P8b` rule).

6. **Docs.** `docs/3-architecture/valuation-math.md` (the bridge formula),
   `docs/3-architecture/data-contract.md` (the field), and
   `docs/2-rules/llm-boundary.md` (one line: the field was added on the user's approval
   of 2026-10-02).

## Files in scope

- `ingestion/claude_extractor.py`
- `models/financial_statements.py`
- `models/valuation.py`
- `analysis/dcf.py`
- `cli.py`
- `templates/valuation_result.html`
- `templates/_statements.html`
- `api/routes_valuation.py`, **only** if the result page cannot reach the new field
  through the objects it already has
- `docs/3-architecture/valuation-math.md`, `docs/3-architecture/data-contract.md`,
  `docs/2-rules/llm-boundary.md`
- your journal entry

## Out of scope

- `tests/`. **Existing tests that call `run_dcf` with a balance sheet that has no
  noncontrolling interest will now stop.** That is the intended behaviour. List every
  test that goes red and why in your entry. The tester updates them with an explicit
  value. Do not weaken the stop to keep them green.
- `analysis/capm.py` (`P10b`), `ingestion/filings.py` and `api/routes_upload.py`
  (`P10c`). Both run in parallel with you.
- `ingestion/session_extraction.py`. It derives its key list from the schema.
- `extractions/WMT.json`. The orchestrator adds the new key to it after this unit.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the bridge | equity value = EV − net debt − NCI | a scratch script: EV 1,000, net debt 200, NCI 50, shares 10 → equity 750, price 75.0 |
| 2 | absence stops | `ValueError` naming `noncontrolling_interest` and the year | the same script with `None` |
| 3 | route B requires the key | the loader stops on a session file without it, naming the key | `check` on a scratch copy of a session file |
| 4 | the output shows it | the CLI DCF block and the result page show the term | a CLI run on a scratch session file, and `TestClient` on `POST /valuation` with price data stubbed |
| 5 | no new zero default | the census does not rise above 116 | the grep at `docs/2-rules/rules.md:65` |
| 6 | the red list | every test that now fails, with its reason | the test gate, before and after |
| 7 | lint and types | ruff 5, mypy ≤ 10 | the two gates |

## Backlog items this unit is NOT fixing

- **Item 1**, the existing `.get(field, 0)` reads. **Item 2**, the missing balance sheet
  (its red test must stay red, for the same reason as before). **Item 10**. **Item 44**,
  units.
