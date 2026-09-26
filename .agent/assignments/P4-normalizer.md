---
id: P4-normalizer
phase: 4 — the highest-cost silent defects
agent: programmer
depends_on: [P1c-flow]
---

# Make the adjustment engine respect the direction of the line it adjusts, and stop instead of guessing

## Objective

Two lines of the income statement move earnings in opposite directions. `ebit`
**subtracts** the operating expense lines. `models/financial_statements.py:91`
**adds** `other_non_operating` when computing `ebt`.

`analysis/normalizer.py:68` applies one sign rule to both. So an adjustment routed to a
non-operating line moves earnings **the wrong way, by twice the item's amount.**

That is backlog item 19, and it is the highest-cost defect known in this repository. It
is the only silent one that fires on **ordinary, complete input** — every other needs a
value to be missing. The case it breaks is the one `NonRecurringItem`'s own docstring
names: `gain_loss_asset_sale`.

Two smaller defects sit in the same 34-line function and are fixed in the same unit,
because separating them means touching it three times: an unrecognised line item
**guesses** a field (item 3), and an unrecognised direction **silently reverses** the
adjustment (item 21).

## What is already true — verify, do not redo

Measured at `796de9a` and `bf0e8bc`, 2026-09-20.

| Fact | Command |
|---|---|
| `pytest -q --ignore-glob="*_rule3_red.py"` → **90 passed, 0 failed** | the gate |
| `pytest -q` → **3 failed, 90 passed.** All three are red on purpose | |
| `analysis/normalizer.py` is at **93%** of statements, with 39 assertions against it | `pytest -q --ignore-glob="*_rule3_red.py" --cov=analysis --cov-report=term` |
| the 2 uncovered lines are `normalizer.py:50-51` — the guess this unit deletes | same command, `--cov-report=term-missing` |
| `ruff check .` → 5 errors, all `BLE001` | the lint gate |
| `mypy …` → 33 errors in 4 files, 18 files checked | the type gate |

**Set `COVERAGE_FILE` to a path under `c:/tmp/` before measuring coverage.** Two
processes in one tree collide on the root `.coverage`.

**The tests for this function already exist.** That is why this unit comes before the
rest of phase 4. You are not working blind; 39 assertions will tell you immediately if
you break the expense path.

## What to do

1. **Give each field a sign, and apply it.**

   The delta on a **field** is not the same as the impact on **earnings**.
   `models/financial_statements.py:31-37` already states the impact on earnings
   correctly:

   ```python
   @property
   def adjusted_impact(self) -> float:
       """add_back -> positive (removes expense -> improves EBIT)
          remove   -> negative (removes gain   -> reduces EBIT)"""
       return self.amount if self.direction == "add_back" else -self.amount
   ```

   So the delta on the field is `adjusted_impact × field_sign`, where `field_sign` is
   `-1` for a field that **reduces** earnings and `+1` for one that **raises** them.

   Of the fields `_LABEL_TO_FIELD` can return, only `other_non_operating` is `+1`.
   Check that claim against `models/financial_statements.py` yourself rather than taking
   it from me; the list may not be what I think it is.

   **This is permitted, and the permission is explicit.**
   [Rule 2](../../docs/2-rules/rules.md) forbids looking up *behaviour* and allows
   looking up a *number*: "a lookup table that maps a key to a **number** is fine."
   A sign is a number. Do not write a dict of functions, and do not branch on the field
   name with `if`.

   **Every field the table can return must have a sign.** A field with no entry is a
   missing input, and [rule 3](../../docs/2-rules/rules.md) says that stops.

2. **Stop instead of guessing the field.** `analysis/normalizer.py:50-51` prints a line
   to stdout and returns `other_operating_expense` for any label it does not recognise.
   Raise `ValueError` instead, naming **the unrecognised label** and **the year it came
   from**. Backlog item 3.

   Use `ValueError`. It is what this codebase already raises for an absent input —
   `ingestion/claude_extractor.py:835` — and it is what the waiting red test asserts.
   Typed exception classes are phase 5 and are **not** in this unit.

   **Delete the `print`.** A message on stdout that the web app never displays is not a
   signal.

3. **Stop instead of reversing on an unrecognised direction.**
   `analysis/normalizer.py:68` tests `== "add_back"`, so every other string — including
   `"Add_Back"` and a typo — silently takes the `remove` branch. Raise `ValueError`
   naming the value and the year, for anything that is neither `"add_back"` nor
   `"remove"`. Backlog item 21.

4. **Prove the fix by execution, not by reading.** Write a scratch script **outside the
   repository**, under `c:/tmp/`, that builds this case and prints the result:

   ```
   revenue 1000, sga 200, other_non_operating 80, tax_expense 100
   remove a one-time gain of 50 from other_non_operating
   ```

   | | Before this unit | Required after |
   |---|---|---|
   | `other_non_operating` | 130.0 | **30.0** |
   | `ebt` | 530.0 | **430.0** |

   Put the actual output in your entry. `docs/8-build/environment.md` section 6 owns
   scratch space; set `PYTHONDONTWRITEBYTECODE=1`.

5. **Do not touch `models/financial_statements.py`.** Its `adjusted_impact` is already
   correct and 40 assertions rest on it. If you believe it is wrong, stop and say so;
   that is an escalation, not an edit.

## Files in scope

- `analysis/normalizer.py`

**Nothing else.** One file. Work outside it is a review finding, even when the change
is good.

## Out of scope

- **`tests/`** — your write guard denies it. Three red tests are waiting and two of them
  must go green as a result of your change. **You do not edit them to make that happen.**
- **`models/financial_statements.py`** — see step 5.
- **`analysis/projector.py`**, which consumes the normalised statements. Its tests will
  tell you if you broke it.
- **Typed exception classes.** Phase 5.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | two of the three red tests go green | `2 passed` | `.venv/Scripts/python.exe -m pytest -q tests/unit/test_normalizer_rule3_red.py` |
| 2 | nothing else broke | **90 passed, 0 failed** | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 3 | the whole suite, reds included | **1 failed, 92 passed** — the one failure is `test_dcf_rule3_red.py` | `.venv/Scripts/python.exe -m pytest -q` |
| 4 | the non-operating case is correct | `other_non_operating` **30.0**, `ebt` **430.0** | your scratch script, output pasted in your entry |
| 5 | the guess is gone | 0 hits | `grep -n "other_operating_expense\"" analysis/normalizer.py` shows no fallback return, and `grep -n "print(" analysis/normalizer.py` → 0 |
| 6 | coverage of `analysis/normalizer.py` | **100%** of statements | `COVERAGE_FILE=c:/tmp/.cov pytest -q --cov=analysis --cov-report=term` |
| 7 | lint unchanged | 5 errors, all `BLE001` | `.venv/Scripts/python.exe -m ruff check .` |
| 8 | types not worse | ≤ 33 errors in ≤ 4 files | the mypy gate |
| 9 | the rule-3 census did not rise | ≤ 117 | the grep in `docs/2-rules/rules.md` |

**Criterion 3 is the one that matters most.** If it reports `0 failed`, you changed a
test, and that is a blocker. If it reports more than one failure, you broke something.

## Citations

- `docs/9-reference/refactor-backlog.md` items **19**, **3** and **21** — the evidence
  and the measured cost of each.
- `docs/2-rules/rules.md` rule 2 (a lookup table of numbers is allowed; of behaviour is
  not) and rule 3 (stop, never guess).
- `models/financial_statements.py:31-37` — `adjusted_impact`, the correct statement of
  the effect on earnings.
- `models/financial_statements.py:91` — `ebt`, which adds `other_non_operating`.
- `.agent/journal/2026-09-20T2145-tester-p1c-flow.md` — the unit that found this.
- `.agent/journal/2026-09-20T2215-code_reviewer-p1c-flow.md` — the independent
  confirmation, with the worked arithmetic.

## Known open items

- **`analysis/normalizer.py:76`** uses `getattr(income_statement, f)` where `f` came
  from `_resolve_field`. Once step 2 lands, `f` can only be a value from
  `_LABEL_TO_FIELD`, so the set is closed and rule 2 is satisfied. **Say in your entry
  that you checked this**, because a reviewer will ask.

- The two lines this unit deletes are the only two `analysis/normalizer.py` statements
  not covered by a test today. Coverage should reach 100% as a consequence, not as a
  target. If it does not, say which line is uncovered and why.

## Backlog items this unit is NOT fixing

- **Item 1** — the 117 zero-default sites. Phase 6.
- **Item 2** — `analysis/dcf.py:80`. Its red test stays red; criterion 3 depends on it.
- **Item 20** — the NaN beta. Its own unit.
- **Item 8** — the blind `except Exception` handlers. Phase 5. Do not add one, and do
  not wrap your new raises in anything.
