---
id: P13f-wacc-debt
phase: 13 — silent defects first, wave 2 (the user's "go" of 2026-10-03)
agent: programmer
depends_on: []
---

# Stop on a negative debt balance, on no balance sheet, and on interest with no debt under an override

## Objective

Three silent paths remain in `analysis/wacc.py` after `P13a` (`47b8b09`):

- **Item 69.** `total_debt` of −50 with a market cap of 300 gives
  `equity_weight 1.2, debt_weight -0.2`. The Pass 1 prompt makes every value positive,
  with the sign in the field name, so a negative debt balance is a bad value that no
  formula can use.
- **Item 38b (a).** With a supplied cost of debt, every debt line 0 and interest expense
  of 30, `calculate_wacc` returns weights 1.0 / 0.0. The override returns before item
  22's interest-against-zero-debt stop runs, so the inconsistency is never seen.
- **Item 38b (b).** `balance_sheet=None` raises a bare `AttributeError` at `:211`. It is
  reachable from `api/routes_valuation.py:621-634`, and it is the live crash path that
  mypy reports there (backlog item 11).

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Measured at `19298f3` on 2026-10-03.

| Fact | Command | Result |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 793 passed |
| full suite | `.venv/bin/python -m pytest -q` | 2 failed (both `*_rule3_red.py`), 793 passed |
| lint | `.venv/bin/python -m ruff check .` | 5 errors, all `BLE001` |
| types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 10 errors in 4 files |
| census | the grep in `docs/2-rules/rules.md` (quote `'--include=*.py'` under zsh) | 65 |
| item 38b (b) | `grep -n "calculate_wacc" api/routes_valuation.py` and the mypy gate | `Argument "balance_sheet" to "calculate_wacc" has incompatible type "BalanceSheet \| None"` |

If any of these disagrees with what you measure, stop and report the disagreement.

## What to do

1. **Item 69.** Stop with a `ValueError` naming `balance_sheet.total_debt` and its value
   when it is below zero. Say that the filing prints debt as a positive figure. Do not
   say that the extraction failed (item 37).
2. **Item 38b (a).** Run item 22's interest-against-zero-debt stop whether or not a cost
   of debt is supplied. A supplied rate does not make the data consistent.
3. **Item 38b (b).** Accept `BalanceSheet | None` in `calculate_wacc` and in
   `cost_of_debt_with_source`, and stop with a `ValueError` naming `balance_sheet` when it
   is `None`. If this removes the mypy error at `api/routes_valuation.py:634`, report the
   new count. Do not edit `api/`.

## Round 2 amendment (orchestrator, 2026-10-04, from the round 1 review)

- **Step 2 is withdrawn.** The review's F1 proved that it was a defect in this
  assignment: no entry point accepts a debt balance, so a company that really repaid its
  debt (item 37's case) stops with no way past, and the new message names a remedy that
  does not exist. Restore `analysis/wacc.py`'s override path and item 22's message
  exactly as they are at `f6da3e9`. The user decides the replacement (an explicit
  confirmation of a zero debt balance). Item 38b (a) stays open.
- **F2.** `_require_finite` (`:40`) tests only for NaN. Make it refuse every value that is
  not finite (`math.isfinite`), so an infinite `market_cap` or `total_debt` stops by name.
  It is used for other values too; an infinite one of those must also stop.
- **F3.** Check each debt line on the balance sheet, not only `total_debt`. A negative
  line stops by name, even when the total is not negative.
- **F4.** Check that interest expense is finite before item 22's comparison, so a NaN is
  not printed as a reported figure.

Add a criterion for each of F2, F3 and F4, and keep criteria 1, 3 and 4. Criterion 2 now
expects the `f6da3e9` behaviour: an override with zero debt lines and interest returns.

## How to work

- **Do not edit `tests/`.** List every test that turns red, by name, with its reason. The
  tester repairs it.
- **Measure on an isolated tree.** Export `git archive 19298f3` into your own scratch
  subdirectory, `scratchpad/p13f_programmer/`, copy in only this unit's files, and run the gates
  there. The scratchpad is shared by every agent in this session: never `rm -rf` a path
  outside your subdirectory. Do not stash or reset the shared tree.
- Three other wave 2 units run in parallel in the same tree. Their files are listed
  under "Files in scope" of their assignments: `P13d-upside-price`: `models/valuation.py`, `analysis/dcf.py`; `P13e-growth-input`: `analysis/projector.py`; `P13g-pass2-unread`: `ingestion/claude_extractor.py`. Do not touch them.
- Do not edit `docs/9-reference/refactor-backlog.md`, `STATUS.md` or the journal index.
  The orchestrator closes the items.

## Files in scope

- `analysis/wacc.py`

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | negative debt stops | `ValueError` naming `balance_sheet.total_debt` and -50, with no claim about the cause | a `python -c` call with (300, -50) |
| 2 | interest with no debt stops under an override | `ValueError` from item 22's stop | market cap 300, every debt line 0, interest 30, override 0.05 |
| 3 | no balance sheet stops by name | `ValueError` naming `balance_sheet`, not `AttributeError` | `calculate_wacc(..., balance_sheet=None, ...)` with and without an override |
| 4 | a normal case keeps its result | weights 0.75 / 0.25 and the same WACC as at `19298f3` for (300, 100) | a `python -c` call on both trees |
| 5 | mypy does not rise | 10 or fewer; report the exact count | the type gate |
| 9 | the suite fails only where expected | every red test named, with its reason | the full suite and the gate form, on the isolated tree |
| 10 | the gates do not get worse | ruff 5 or fewer, mypy 10 or fewer, census 65 or fewer | the gate commands |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md`: rule 3 (stop, never guess), rule 5 (market data is labelled), rule 6.
- `docs/9-reference/refactor-backlog.md`: items 69, 38b.
- `docs/5-testing/strategy.md`, section 2: why no test may lock the old behaviour.

## Backlog items this unit is NOT fixing

- Item 37: the zero-debt stop's message.
- Item 22's own logic, apart from running it under an override.
- Item 1's sites in this file.
