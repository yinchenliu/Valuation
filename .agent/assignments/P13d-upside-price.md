---
id: P13d-upside-price
phase: 13 — silent defects first, wave 2 (the user's "go" of 2026-10-03)
agent: programmer
depends_on: []
---

# Stop on no current price instead of reporting 0% upside

## Objective

`DCFResult.upside_downside` (`models/valuation.py:369-373`) returns `0.0` when
`current_price == 0`. A result with no market price then reads as "fairly valued", which
is a measurement, not an absence. Backlog item 65. It is item 32's shape on the other
input of the comparison: `P13b` (`aa6f80d`) made `run_dcf` and `implied_share_price` stop
on a share count that is not a finite number above zero. `run_dcf` takes `current_price`
(`analysis/dcf.py:156`) and checks nothing.

The web route already stops earlier on a zero price today: `market_cap` is
`current_price * shares` (`api/routes_valuation.py:629`), and since `P13a` WACC stops on
a market cap of zero. So this unit closes the direct path, the CLI path, and the property.

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Measured at `19298f3` on 2026-10-03.

| Fact | Command | Result |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 793 passed |
| full suite | `.venv/bin/python -m pytest -q` | 2 failed (both `*_rule3_red.py`), 793 passed |
| lint | `.venv/bin/python -m ruff check .` | 5 errors, all `BLE001` |
| types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 10 errors in 4 files |
| census | the grep in `docs/2-rules/rules.md` (quote `'--include=*.py'` under zsh) | 65 |
| item 65 | `sed -n 369,373p models/valuation.py` | `if self.current_price == 0: return 0.0` |
| `run_dcf` checks no price | `grep -n current_price analysis/dcf.py` | lines 156, 167, 233 only |

If any of these disagrees with what you measure, stop and report the disagreement.

## What to do

1. `run_dcf` stops before it discounts anything when `current_price` is not a finite
   number greater than zero. The `ValueError` names `current_price` and its value, and
   says that it is market data, not a filing figure (rule 5 labels market data).
2. `upside_downside` loses its conditional zero. When `current_price` is not a finite
   number greater than zero, it raises a `ValueError` that names the field. Use the
   same test as step 1, as `P13b` did for `diluted_shares`.
3. Read every caller of `upside_downside` (`grep -rn upside_downside api cli.py templates
   analysis models`). No caller may catch the error and turn it into a default. Report
   any caller that can now raise where it did not. Do not edit those callers.

## How to work

- **Do not edit `tests/`.** List every test that turns red, by name, with its reason. The
  tester repairs it.
- **Measure on an isolated tree.** Export `git archive 19298f3` into your own scratch
  subdirectory, `scratchpad/p13d_programmer/`, copy in only this unit's files, and run the gates
  there. The scratchpad is shared by every agent in this session: never `rm -rf` a path
  outside your subdirectory. Do not stash or reset the shared tree.
- Three other wave 2 units run in parallel in the same tree. Their files are listed
  under "Files in scope" of their assignments: `P13e-growth-input`: `analysis/projector.py`; `P13f-wacc-debt`: `analysis/wacc.py`; `P13g-pass2-unread`: `ingestion/claude_extractor.py`. Do not touch them.
- Do not edit `docs/9-reference/refactor-backlog.md`, `STATUS.md` or the journal index.
  The orchestrator closes the items.

## Files in scope

- `models/valuation.py`
- `analysis/dcf.py`

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | `run_dcf` stops on no price | `ValueError` naming `current_price`, for 0, a negative price, `nan` and `inf` | a `python -c` call for each |
| 2 | the property stops on no price | `ValueError` naming `current_price` | a `DCFResult` built directly with `current_price=0` |
| 3 | a positive price keeps its upside | `(implied / current - 1) * 100`, worked by hand for one case you state | a `python -c` call |
| 4 | the census does not rise | 64 or fewer (the conditional zero goes) | the census grep |
| 9 | the suite fails only where expected | every red test named, with its reason | the full suite and the gate form, on the isolated tree |
| 10 | the gates do not get worse | ruff 5 or fewer, mypy 10 or fewer, census 65 or fewer | the gate commands |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md`: rule 3 (stop, never guess), rule 5 (market data is labelled), rule 6.
- `docs/9-reference/refactor-backlog.md`: items 65.
- `docs/5-testing/strategy.md`, section 2: why no test may lock the old behaviour.

## Backlog items this unit is NOT fixing

- Item 1: the zero-default fields in `models/valuation.py`.
- Item 31: `discount_cash_flows` on a direct call.
