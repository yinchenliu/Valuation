---
id: P13g-pass2-unread
phase: 13 — silent defects first, wave 2 (the user's "go" of 2026-10-03)
agent: programmer
depends_on: []
---

# Stop when route A cannot read Pass 2, instead of reporting no items

## Objective

`_run_nri_pass` (`ingestion/claude_extractor.py:1754`) retries once when the Pass 2
reply does not parse. If the retry also fails, a blanket `except Exception` prints a
warning and returns `[]`. So "the model's reply could not be read" becomes "the filing has
no non-recurring items", and the CLI and the result page say that no item was found.
`_parse_nri_response` tells the two apart; this branch erases the difference. Backlog
item 50, whose fix is "Raise, naming the filing. With item 8." Route B is not affected:
its loader already stops.

**Make no API call.** Route A sends a paid request. Test the branch by replacing the
client call with a stub that returns unparseable text, as the `P9c` tests do.

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Measured at `19298f3` on 2026-10-03.

| Fact | Command | Result |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 793 passed |
| full suite | `.venv/bin/python -m pytest -q` | 2 failed (both `*_rule3_red.py`), 793 passed |
| lint | `.venv/bin/python -m ruff check .` | 5 errors, all `BLE001` |
| types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 10 errors in 4 files |
| census | the grep in `docs/2-rules/rules.md` (quote `'--include=*.py'` under zsh) | 65 |
| the blanket except | `.venv/bin/python -m ruff check ingestion/claude_extractor.py` | 1 `BLE001`, at line 1798 |

If any of these disagrees with what you measure, stop and report the disagreement.

## What to do

1. Replace the blanket `except Exception` in `_run_nri_pass` that returns `[]` with a stop:
   a `ValueError` (or a named subclass already in the file, if one fits) that names the
   filing, says that Pass 2's reply could not be parsed after the retry, and gives the
   parse error. Catch only the exception types the parse can raise. Rule 3, and item 8.
2. Keep the case where the model's reply parses and lists no items: that still returns
   `[]`.
3. Report what the CLI and the web route now show when this stop fires. Do not edit
   them.

## How to work

- **Do not edit `tests/`.** List every test that turns red, by name, with its reason. The
  tester repairs it.
- **Measure on an isolated tree.** Export `git archive 19298f3` into your own scratch
  subdirectory, `scratchpad/p13g_programmer/`, copy in only this unit's files, and run the gates
  there. The scratchpad is shared by every agent in this session: never `rm -rf` a path
  outside your subdirectory. Do not stash or reset the shared tree.
- Three other wave 2 units run in parallel in the same tree. Their files are listed
  under "Files in scope" of their assignments: `P13d-upside-price`: `models/valuation.py`, `analysis/dcf.py`; `P13e-growth-input`: `analysis/projector.py`; `P13f-wacc-debt`: `analysis/wacc.py`. Do not touch them.
- Do not edit `docs/9-reference/refactor-backlog.md`, `STATUS.md` or the journal index.
  The orchestrator closes the items.

## Files in scope

- `ingestion/claude_extractor.py`, `_run_nri_pass` only

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | an unparseable Pass 2 after the retry stops | an exception naming the filing and the parse error | a stubbed client that returns unparseable text twice |
| 2 | a parseable reply with no items still returns `[]` | `[]` | a stub that returns `{"non_recurring_items": []}` |
| 3 | no API call was made | no network client created in any check | read each check; the stub replaces the call |
| 4 | lint falls by one | ruff 4, all `BLE001` | the lint gate |
| 9 | the suite fails only where expected | every red test named, with its reason | the full suite and the gate form, on the isolated tree |
| 10 | the gates do not get worse | ruff 5 or fewer, mypy 10 or fewer, census 65 or fewer | the gate commands |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md`: rule 3 (stop, never guess), rule 5 (market data is labelled), rule 6.
- `docs/9-reference/refactor-backlog.md`: items 50, and item 8's site in `_run_nri_pass`.
- `docs/5-testing/strategy.md`, section 2: why no test may lock the old behaviour.

## Backlog items this unit is NOT fixing

- Items 51, 61, 63, 64 and the Pass 1 retry loop.
- Item 10 and item 44: Phase 14.
- The other blanket `except` sites of item 8, in `api/` and `cli.py`.
