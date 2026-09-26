---
id: P4d-cashflow-nan
phase: 4 — the highest-cost silent defects
agent: programmer
depends_on: [P4c-nan-stops]
---

# Guard the cash-flow side, and close the tax clamp twin

## Objective

`P4c-nan-stops` closed the NaN route through the **discount rate**. It did not close the
route through the **cash flows**, and the reviewer confirmed the second one is still
open — measured before **and** after that unit, in a middle projection year and in the
final year:

> a NaN in a single `ProjectedFCFF` produces `implied_share_price = nan`, with a finite
> WACC and no exception anywhere.

`analysis/dcf.py:46-57` sums and discounts the projected cash flows with no check on
what it is summing. That is backlog item 30, and it is now the highest-cost defect known
here.

The second half is item **23b**: `analysis/fcff.py:44` holds the tax clamp twin.
`max(0.0, min(nan, 0.50))` is **`0.0`** — Python's `min` and `max` keep their first
argument when a comparison is `False`, and every comparison against NaN is `False`. So
an unknown tax rate becomes a 0% rate and a full tax shield, which **raises** the
valuation. `analysis/wacc.py` held the identical clamp and `P4c-nan-stops` fixed it.

## What is already true — verify, do not redo

Measured at `eed4fe1`.

| Fact | Evidence |
|---|---|
| a NaN in one `ProjectedFCFF` → `implied_share_price = nan`, finite WACC | reviewer of `P4c-nan-stops`, 23-case probe |
| `max(0.0, min(nan, 0.50))` → `0.0` | orchestrator, and the same reviewer end to end |
| `analysis/wacc.py` checks **before** its clamp, at `:104` against the clamp at `:106` | `P4c-nan-stops` |
| `analysis/fcff.py` is at **100%** of statements; `dcf.py` at 93% | the coverage gate |
| suite `1 failed, 120 passed`; lint 5; types 14; census 116 | the gates |

## What to do

1. **Guard each projected cash flow in `analysis/dcf.py`.** `math.isnan`, never a
   comparison — a comparison is what let item 20 through. Name the **year**, not just
   the field, so a reader can find the offending projection.

   Cover both the explicit years and the final one used for the terminal value.

2. **Close the clamp twin in `analysis/fcff.py`.** Check **before** the clamp, as
   `analysis/wacc.py` does. After it the evidence is gone — the NaN has already become a
   plausible `0.0`.

3. **Follow the pattern that already exists.** `analysis/wacc.py` has
   `_require_finite`. Reuse the approach rather than inventing a second one. If you
   import it across modules, say so and check the layering: `analysis/` may import
   `analysis/`.

4. **Prove it by driving the chain**, not by reading. A NaN in a middle year and in the
   final year, before and after. Paste both. Scratch under `c:/tmp/`.

5. **Do not touch item 23's other half.** `analysis/fcff.py` holding no `raise` for
   wholly empty statements is the same backlog item and **not** this unit. You are
   adding one guard, not making the module rule-3 clean.

## Files in scope

- `analysis/dcf.py`
- `analysis/fcff.py`

**Nothing else.**

## Out of scope

- **`tests/`** — your write guard denies it. A tester follows you and will close the
  coverage gap for every new stop at once.
- `analysis/wacc.py` and `analysis/capm.py` — `P4c-nan-stops` finished them.
- **Item 2**, `analysis/dcf.py:80`, zero net debt. Its red test **must stay red**.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | a NaN in a middle-year `ProjectedFCFF` stops, naming the year | raises | your script; before and after |
| 2 | a NaN in the final-year `ProjectedFCFF` stops, naming the year | raises | same |
| 3 | a NaN tax rate into `calculate_fcff_historical` stops | raises, not `0.0` | same |
| 4 | **no existing assertion changed meaning** | `1 failed, 120 passed`, the failure being `test_dcf_rule3_red.py` | `pytest -q` |
| 5 | a healthy path is byte-identical | state the figure before and after | your script |
| 6 | lint unchanged | 5, all `BLE001` | `ruff check .` |
| 7 | types not worse | ≤ 14, a strict subset | the mypy gate, set-diffed |
| 8 | the census did not rise | ≤ 116 | the grep in `docs/2-rules/rules.md` |

**Criterion 5 is the one that matters, as it was last time.** These files carry
assertions derived by hand. The risk is not that a guard fails to fire; it is that a
healthy path moves.

**Coverage will fall again**, because new raises are new statements. Report the drop and
the lines. **Do not write an unreachable guard or restructure code to hold a
percentage** — the same instruction `P4c-nan-stops` was given, and followed.

## Citations

- `docs/9-reference/refactor-backlog.md` items **30** and **23b**.
- `docs/2-rules/rules.md` rule 3.
- `.agent/journal/2026-09-21T0800-code_reviewer-p4c-nan-stops.md` — the confirmation of
  item 30, and the `_require_finite` pattern to follow.

## Known open items

- `tests/unit/test_capm.py:258` asserts `pytest.approx(-0.8)`, the output of the silent
  geometric-to-arithmetic switch at `analysis/capm.py`. **Not your file and not your
  unit** — recorded so nobody trips on it later.

## Backlog items this unit is NOT fixing

- **Item 1** — the 116 zero-default sites.
- **Item 2** — zero net debt. Its red test stays red; criterion 4 depends on it.
- **Item 23's other half** — `analysis/fcff.py` holding no `raise` for empty statements.
- **Item 8** — the blanket catches. Do not add one, and do not wrap your raises.
