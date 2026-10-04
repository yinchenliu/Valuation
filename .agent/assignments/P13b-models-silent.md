---
id: P13b-models-silent
phase: 13 — silent defects first (the user's decision of 2026-10-03)
agent: programmer
depends_on: []
---

# Stop on no latest year and no share count; make confidence required; label a truncated growth list

## Objective

Four places turn an absent input into a value that reads as a measurement.

- **Item 15.** `FinancialStatements.latest_year` (`models/financial_statements.py:370-371`)
  returns `0` when there are no statements. "No data" becomes "year zero" with no error.
- **Item 32.** `DCFResult.implied_share_price` (`models/valuation.py:337-338`) returns
  `0.0` when `diluted_shares` is zero. A valuation with no share count shows a price of
  zero, which reads as a company worth nothing. `run_dcf` (`analysis/dcf.py`) takes
  `diluted_shares` and checks nothing.
- **Item 39.** `NonRecurringItem.confidence` (`models/financial_statements.py:35`)
  defaults to `"high"`, the strongest reading. No live path reaches the default today. It
  is the last place where absence becomes the strongest reading.
- **Item 42.** `analysis/projector.py:170` cuts a supplied growth list to
  `projection_years`. Five rates with `projection_years=2` give `[0.1, 0.2]`, and the
  label says `supplied` with no word about the three rates it dropped. The pad case has
  a clause (`ASSUMPTION_PADDED_CLAUSE_TEMPLATE`, `models/valuation.py:112`). The cut
  case has none.

Rule 3 covers items 15, 32 and 39. Rule 6 covers item 42: the reader typed five numbers
and must see that the valuation used two.

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Measured at `0021845` on 2026-10-03.

| Fact | Command | Result |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 724 passed |
| lint, types | the gates in `docs/8-build/environment.md` | ruff 5 (`BLE001`), mypy 10 in 4 files |
| census | the grep in `docs/2-rules/rules.md` | 67 |
| item 15 | `sed -n 370,371p models/financial_statements.py` | `return max(self.years) if self.years else 0` |
| callers of `latest_year` | `grep -rn latest_year analysis api cli.py templates` | `analysis/projector.py:306`, `analysis/dcf.py:194`, `api/routes_valuation.py:619`, `cli.py:458` and `:1032`, `templates/_statements.html:295` |
| item 32 | `sed -n 337,338p models/valuation.py` | `... if self.diluted_shares else 0.0` |
| `run_dcf` checks no share count | `grep -n diluted_shares analysis/dcf.py` | lines 157, 168, 218 only |
| item 39 | `sed -n 29,36p models/financial_statements.py` | `confidence: str = "high"`, followed by `source: str = ""` |
| one constructor in the code | `grep -rn "NonRecurringItem(" models analysis api ingestion cli.py` | `ingestion/claude_extractor.py:1484` |
| item 42 | `sed -n 166,186p analysis/projector.py` | pad clause only |

If any of these disagrees with what you measure, stop and report the disagreement.

## What to do

1. **Item 15.** `latest_year` raises `ValueError` when there are no statements, and the
   message says that there are no statements, so there is no latest year. Then read
   every caller in the table above. No caller may catch the error and turn it into a
   default. If the template at `templates/_statements.html:295` can render with no
   statements on any route, report how. Do not edit `api/`, `cli.py` or `templates/`.

2. **Item 32.** `run_dcf` stops before it discounts anything when `diluted_shares` is
   not a finite number greater than zero. The `ValueError` names `diluted_shares` and
   its value. `implied_share_price` loses its conditional zero: when `diluted_shares` is
   not greater than zero it raises a `ValueError` that names the field. Reason: rule 3,
   and backlog item 32's "Fix".

3. **Item 39.** Make `confidence` a required field with no default. The field order
   allows it: it follows `category`, which has no default. Check that the one
   constructor at `ingestion/claude_extractor.py:1484` already passes it. Do not edit
   that file. If it does not pass it, stop and report.

4. **Item 42.** Add `ASSUMPTION_TRUNCATED_CLAUSE_TEMPLATE` beside the pad template in
   `models/valuation.py`, in the same voice. It names how many rates were supplied, how
   many the projection used, and how many were dropped, and it says that the dropped
   rates reach no figure. `analysis/projector.py` appends it to the growth label when a
   supplied list is longer than `projection_years`.

5. **Do not edit `tests/`.** Tests that build a `NonRecurringItem` without `confidence`,
   or that assert the old label text, can turn red. List every test that turns red, by
   name, with the reason for each. The tester repairs them.

## Files in scope

- `models/financial_statements.py`
- `models/valuation.py`
- `analysis/dcf.py`
- `analysis/projector.py`

**Nothing else.** Work outside this list is a review finding, even if the change is
good. Two other units run in parallel: `P13a-analysis-silent` owns
`analysis/normalizer.py` and `analysis/wacc.py`, and `P13c-env-override` owns
`config.py` and `ingestion/claude_extractor.py`. Their changes can show in the full test
run.

## Out of scope

- `tests/`: the tester's.
- `api/`, `cli.py`, `templates/`, `ingestion/`: report what you find there, do not edit.
- `docs/9-reference/refactor-backlog.md` and `STATUS.md`: the orchestrator's.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | no statements, no latest year | `ValueError` that says there are no statements | `python -c` on `FinancialStatements(ticker="X").latest_year` |
| 2 | `run_dcf` stops on no share count | `ValueError` naming `diluted_shares`, for 0, a negative number and `nan` | a `python -c` call for each |
| 3 | the property stops on no share count | `ValueError` naming `diluted_shares` | a `DCFResult` built directly with `diluted_shares=0` |
| 4 | a positive share count keeps its price | `equity_value / diluted_shares`, by hand, for one case you state | a `python -c` call |
| 5 | `confidence` is required | `TypeError` when it is left out | `python -c` that builds a `NonRecurringItem` without it |
| 6 | a cut growth list is labelled | five rates and `projection_years=2` give `[0.1, 0.2]` and a label that names 5 supplied, 2 used, 3 dropped | a `python -c` call to the projector |
| 7 | a list of the right length gets no clause | no truncation clause in the label | the same call with two rates |
| 8 | Walmart is unchanged | the stage 2 to 5 output of the CLI is the same as at `0021845` | `.venv/bin/python cli.py --session-file extractions/WMT.json` on both trees, stages 2 to 5 compared (stage 6 onward uses live market data) |
| 9 | the suite fails only where expected | every red test named, with its reason | the full suite and the gate form |
| 10 | the gates do not get worse | ruff 5, mypy 10, census below 67 (item 32 removes one conditional zero) | the three gate commands |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md`, rules 3 and 6.
- `docs/9-reference/refactor-backlog.md`, items 15, 32, 39 and 42.
- `docs/3-architecture/data-contract.md`: the `models/` fields.
- `docs/4-conventions/units-and-signs.md`: the share count is in the units of the filing.

## Known open items

- Item 44: when the filing gives no share count, `api/routes_valuation.py` uses
  yfinance's `sharesOutstanding / 1e6`. That path is not yours. Your stop in `run_dcf`
  sees whatever share count reaches it.
- `models/valuation.py` carries about 40 assertions. Expect to answer for each one that
  your change touches.

## Backlog items this unit is NOT fixing

- Item 1: the zero-default fields in `models/`, including `diluted_shares: float = 0.0`.
- Item 23: `analysis/fcff.py` and empty statements. It goes with item 1.
- Item 41: the `else 0.05` at `analysis/projector.py:169`. The backlog says to delete it
  as part of item 1, not on its own.
- The bare `IndexError` on an empty revenue list in `analysis/projector.py`, locked by
  `tests/unit/test_projector_rule3_red.py`. It is a stop, not a silent defect.
- Item 31 in `analysis/dcf.py`: `discount_cash_flows` does not check `wacc` on a
  direct call.
