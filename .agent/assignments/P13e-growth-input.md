---
id: P13e-growth-input
phase: 13 — silent defects first, wave 2 (the user's "go" of 2026-10-03)
agent: programmer
depends_on: []
---

# Stop changing the caller's growth list, and stop on a projection shorter than one year

## Objective

Two defects in `derive_assumptions` (`analysis/projector.py`):

- **Item 66, silent.** `rev_growth = ov.revenue_growth_rates` (`:157`) binds the
  caller's own list, and the `while` loop then appends to it. `[0.1]` with
  `projection_years=3` becomes `[0.1, 0.1, 0.1]` in the caller's object. A second call
  with the same assumptions reads the repeated rates as supplied and drops the
  `REPEATED` clause. Rule 6: the label then says the user chose a rate that this
  platform repeated.
- **Item 67.** `projection_years` is never checked. Below 1, the growth label describes
  a projection that never runs (the `P13b` review's F1). Rule 3: an input that cannot
  form a projection stops and names the field.

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Measured at `19298f3` on 2026-10-03.

| Fact | Command | Result |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 793 passed |
| full suite | `.venv/bin/python -m pytest -q` | 2 failed (both `*_rule3_red.py`), 793 passed |
| lint | `.venv/bin/python -m ruff check .` | 5 errors, all `BLE001` |
| types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 10 errors in 4 files |
| census | the grep in `docs/2-rules/rules.md` (quote `'--include=*.py'` under zsh) | 65 |
| item 66 | `sed -n 155,172p analysis/projector.py` | `rev_growth = ov.revenue_growth_rates`, then `.append` in the loop |

If any of these disagrees with what you measure, stop and report the disagreement.

## What to do

1. **Item 66.** Work on a copy of the supplied list. The caller's list must be the same
   object with the same contents after the call. The labels must not change for a first
   call.
2. **Item 67.** `derive_assumptions` stops with a `ValueError` naming
   `projection_years` and its value when it is not an integer of 1 or more. Check it
   before any rate is derived.
3. Leave the `else 0.05` at `:169` alone (item 41, with item 1).

## How to work

- **Do not edit `tests/`.** List every test that turns red, by name, with its reason. The
  tester repairs it.
- **Measure on an isolated tree.** Export `git archive 19298f3` into your own scratch
  subdirectory, `scratchpad/p13e_programmer/`, copy in only this unit's files, and run the gates
  there. The scratchpad is shared by every agent in this session: never `rm -rf` a path
  outside your subdirectory. Do not stash or reset the shared tree.
- Three other wave 2 units run in parallel in the same tree. Their files are listed
  under "Files in scope" of their assignments: `P13d-upside-price`: `models/valuation.py`, `analysis/dcf.py`; `P13f-wacc-debt`: `analysis/wacc.py`; `P13g-pass2-unread`: `ingestion/claude_extractor.py`. Do not touch them.
- Do not edit `docs/9-reference/refactor-backlog.md`, `STATUS.md` or the journal index.
  The orchestrator closes the items.

## Files in scope

- `analysis/projector.py`

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the caller's list is unchanged | `[0.1]` stays `[0.1]`, same `id`, after a call with `projection_years=3` | a `python -c` call |
| 2 | a second call keeps the pad clause | the growth label of the second call equals the first | the same script, two calls |
| 3 | `projection_years` below 1 stops | `ValueError` naming the field, for 0 and -1 | a `python -c` call for each |
| 4 | Walmart is unchanged | CLI stages 2 to 6 identical to `19298f3` | `.venv/bin/python cli.py --session-file extractions/WMT.json` on both trees |
| 9 | the suite fails only where expected | every red test named, with its reason | the full suite and the gate form, on the isolated tree |
| 10 | the gates do not get worse | ruff 5 or fewer, mypy 10 or fewer, census 65 or fewer | the gate commands |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md`: rule 3 (stop, never guess), rule 5 (market data is labelled), rule 6.
- `docs/9-reference/refactor-backlog.md`: items 66, 67.
- `docs/5-testing/strategy.md`, section 2: why no test may lock the old behaviour.

## Backlog items this unit is NOT fixing

- Item 41: the dead `else 0.05`.
- The bare `IndexError` on an empty revenue list, locked by `tests/unit/test_projector_rule3_red.py`.
- Item 1's sites in this file.
