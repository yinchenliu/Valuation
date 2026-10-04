---
id: P13h-zero-debt-confirm
phase: 13 — silent defects first, wave 3 (the user's decision of 2026-10-04, option 1)
agent: programmer
depends_on: [P13f-wacc-debt]
---

# A company that repaid its debt: an explicit "confirm zero debt" choice replaces the cost-of-debt bypass

## Objective

Item 22's stop (`analysis/wacc.py`, `cost_of_debt_with_source`) fires when the balance
sheet reports total debt of 0 while the income statement reports interest expense. That
pattern usually means the debt balance was not read. But a company that repaid all its
debt during the year shows the same pattern, and it is real.

Today the only way past the stop is a supplied cost of debt (`--cost-of-debt`, or the
form's "Cost of Debt Override"). The override returns before the stop runs. With zero
debt the debt weight is 0, so the supplied rate reaches nothing: it works only as an
unstated "yes, the zero is real", and the label says "supplied by the caller". That is
item 38b (a).

The user decided on 2026-10-04: option 1. Add an explicit confirmation, a checkbox on the
assumptions form and `--confirm-zero-debt` on the CLI. When it is set, the run values the
company with no debt, and the cost-of-debt label says that the user confirmed the zero.
A supplied cost of debt no longer gets past the stop.

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Measured at `0a5a715` on 2026-10-04.

| Fact | Command | Result |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 857 passed |
| full suite | `.venv/bin/python -m pytest -q` | 2 failed (both `*_rule3_red.py`), 857 passed |
| lint | `.venv/bin/python -m ruff check .` | 4 errors, all `BLE001` |
| types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 9 errors in 4 files |
| census | the grep in `docs/2-rules/rules.md` (quote `'--include=*.py'` under zsh) | 65 |
| Walmart | `.venv/bin/python cli.py --session-file extractions/WMT.json` | implied share price $28.02; WACC 7.68%. Walmart carries debt, so this unit must not move it |
| the bypass | `calculate_wacc` with market cap 300, every debt line 0, interest expense 30, `cost_of_debt_override=0.05` | returns weights 1.0 / 0.0, label "supplied by the caller …" |

If any of these disagrees with what you measure, stop and report the disagreement.

## What to do

1. **`analysis/wacc.py`.** Add a keyword parameter `zero_debt_confirmed: bool = False` to
   `cost_of_debt_with_source`, `calculate_cost_of_debt` and `calculate_wacc`, and pass it
   through. The checks that run today before the override (`_require_balance_sheet`,
   `_require_valid_debt`) keep their place and order. Then apply this table. Each row
   names the reason.

   | total debt | interest expense | confirmed | override | result |
   |---|---|---|---|---|
   | 0 | not 0 | no | none or given | **stop**: item 22's `ValueError`. The override no longer gets past it. Its remedy text names `--confirm-zero-debt` on the CLI and the "Confirm zero debt" checkbox on the assumptions page, and no longer tells the reader to supply `--cost-of-debt` "if the zero is correct" |
   | 0 | not 0 | yes | none | rate 0.0. The label says that the user confirmed total debt of 0 although the income statement reports interest expense X for year Y, that the debt weight is therefore 0, and that the WACC is the cost of equity. It names the two places the confirmation comes from |
   | 0 | not 0 | yes | given | the supplied rate. The label says it was supplied, that the user confirmed total debt of 0, and that with a debt weight of 0 the rate does not reach the WACC |
   | 0 | 0 | either | none | today's debt-free result (0.0). If confirmed, the label also says that the user confirmed the zero |
   | 0 | 0 | either | given | the supplied rate. The label adds that the debt weight is 0, so the rate does not reach the WACC (rule 6: today's label lets a reader think the rate was used) |
   | above 0 | any | yes | any | **stop**: a `ValueError` naming `balance_sheet.total_debt`, its value, its three lines and the year, and saying that the user confirmed a debt of 0. The two inputs contradict each other, and the code cannot tell which one is wrong (rule 3) |
   | above 0 | any | no | any | unchanged |

   Item 22's interest check must stay finite-safe: `_require_finite` on the interest
   expense runs before every comparison with it, on every row, including when an
   override is given. Today it runs only on the path with no override.

2. **`models/valuation.py`.** Add `zero_debt_confirmed: bool = False` to
   `ProjectionAssumptions`, beside `cost_of_debt_override`, with a comment that says what
   it confirms and where it is set. A `bool` is not a money figure, and `False` is the
   state "the user confirmed nothing", so this default does not guess an input.

3. **`cli.py`.** Add `--confirm-zero-debt` (`action="store_true"`) to the
   "valuation overrides" group, with help text that says when to use it: the company
   repaid all its debt, so the balance sheet shows 0 while the income statement shows
   interest. Set `zero_debt_confirmed` in `build_overrides`, and pass
   `overrides.zero_debt_confirmed` to `calculate_wacc` in stage 8. The label already
   prints through `print_wacc` and the summary. Do not change anything else in stage 8.

4. **`api/routes_valuation.py`.** Add a form field `confirm_zero_debt: str = Form("")`
   to the valuation route. An HTML checkbox sends `"on"` when it is checked and nothing
   when it is not. So `""` is `False` and `"on"` is `True`. Any other value stops with a
   `ValueError` that names the field and the value (rule 3: do not guess). Set it on
   `ProjectionAssumptions` and pass it to `calculate_wacc`.

5. **`templates/assumptions.html`.** Add the checkbox (`name="confirm_zero_debt"`) beside
   the cost of debt override, with the visible label "Confirm zero debt" and one line of
   help: use it only when the company repaid all its debt, so the balance sheet shows 0
   while the income statement shows interest.

## How to work

- **Do not edit `tests/`.** List every test that turns red, by name, with its reason. The
  tester repairs it. Expect `test_wacc.py` cases that assert the old bypass or the old
  remedy text.
- **Measure on an isolated tree.** Export `git archive HEAD` into your own subdirectory
  of the session scratchpad,
  `/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/49a4d4a7-ff32-4deb-a1ba-ba1f44e044e1/scratchpad/p13h_programmer/`,
  copy in only this unit's files, and run the gates there. Never `rm -rf` a path outside
  your subdirectory. Do not stash or reset the shared tree. In-repo scratch paths are
  refused by the write guard.
- Set `PYTHONDONTWRITEBYTECODE=1` when you run a changed tree, so a stale `.pyc` cannot
  give a false result.
- The write guard can refuse a Bash command that holds `>` or `=` inside a quoted
  pattern or a heredoc (backlog item 75). If it does, write the script to a file in your
  subdirectory and run the file.
- Make no paid API call. Nothing in this unit needs one.
- Do not edit `docs/9-reference/refactor-backlog.md`, `STATUS.md` or the journal index.
  The orchestrator closes the item.

## Files in scope

- `analysis/wacc.py`
- `models/valuation.py`
- `cli.py`
- `api/routes_valuation.py`
- `templates/assumptions.html`
- `docs/3-architecture/valuation-math.md`, the WACC section only: state the confirmation
  and the new table, if that section describes item 22's stop or the override
- `docs/3-architecture/entry-points.md`: the new CLI flag and form field, if that file
  lists the overrides

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Out of scope

- `templates/valuation_result.html`: it already prints `wacc.cost_of_debt_source`, so the
  new label reaches the page without a change.
- `ingestion/`: `P14a-units` owns it next.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | interest with zero debt stops, with no override | `ValueError`; the message names `--confirm-zero-debt` and "Confirm zero debt", and no longer names `--cost-of-debt` as the remedy | a `python -c` call: market cap 300, every debt line 0, interest 30 |
| 2 | the bypass is gone | `ValueError`, the same stop | as 1, with `cost_of_debt_override=0.05` |
| 3 | a confirmed zero values the company with no debt | weights 1.0 / 0.0, `wacc == cost_of_equity`, cost of debt 0.0, label holds "confirmed" | as 1, with `zero_debt_confirmed=True` |
| 4 | a confirmed zero with an override keeps the rate and says it is not used | cost of debt 0.05, weights 1.0 / 0.0, `wacc == cost_of_equity`; label says the rate does not reach the WACC | as 3, with `cost_of_debt_override=0.05` |
| 5 | a confirmation against a real debt balance stops | `ValueError` naming `balance_sheet.total_debt`, 100, and the confirmation | market cap 300, debt 100, interest 5, `zero_debt_confirmed=True` |
| 6 | a debt-free company with an override says the rate is not used | label adds that clause; WACC unchanged from `0a5a715` | market cap 1000, debt 0, interest 0, override 0.90, tax 0.40, on both trees |
| 7 | a normal case keeps its result | weights 0.75 / 0.25 and the same WACC, to the last digit, as at `0a5a715` | market cap 300, debt 100, interest 5, on both trees |
| 8 | NaN interest stops by name under an override | `ValueError` naming `income_statement.interest_expense` | debt 0, interest `nan`, override 0.05 |
| 9 | the CLI flag reaches the WACC | `--help` lists `--confirm-zero-debt`; `build_overrides` on parsed args sets `zero_debt_confirmed` True | `cli.py --help`, and a `python -c` call on `parse_args` with a patched `sys.argv` |
| 10 | the form field reaches the WACC | `GET /assumptions` (with a filing named, as the route tests do) shows `name="confirm_zero_debt"`; `POST /valuation` with `confirm_zero_debt=on` calls `calculate_wacc` with `zero_debt_confirmed=True`, and with the field absent, `False`; the value `yes` shows the named stop | a `TestClient` script that patches `calculate_wacc` to record its arguments and patches the price fetch, no network |
| 11 | Walmart does not move | $28.02, WACC 7.68%, the same cost-of-debt label | `cli.py --session-file extractions/WMT.json`, both trees |
| 12 | the suite fails only where expected | every red test named, with its reason | the full suite and the gate form, on the isolated tree |
| 13 | the gates do not get worse | ruff 4 or fewer, mypy 9 or fewer, census 65 or fewer, route 200 | the gate commands in `docs/8-build/environment.md` |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md`: rule 3 (stop, never guess), rule 6 (an assumption is shown).
- `docs/9-reference/refactor-backlog.md`: items 22, 37, 38b and the user's decision under 38b.
- `.agent/journal/2026-10-04T0109-code_reviewer-p13f-wacc-debt.md`: F1, the case that
  forced this unit, and the proof that no entry point accepts a debt balance.
- `docs/5-testing/strategy.md`, section 2: why no test may lock the old behaviour.

## Known open items

- Item 8: a stop inside the valuation route shows on a page at HTTP 200, because of the
  blanket `except`. Criterion 10's "named stop" is that page.
- Item 76: the form's `projection_years` has no lower bound. Not this unit's.

## Backlog items this unit is NOT fixing

- Item 37: the wording of item 22's stop apart from its remedy text.
- Item 72: `cli.py:1035` (`shares`) and `cli.py:1043` (`latest_bs.total_debt if latest_bs else 0`).
  They sit beside the stage 8 line you change. Leave them.
- Item 6: the five `x / 100 if x else None` conversions in the valuation route.
- Item 5: the module-global extraction cache.
- Item 7: the duplicated pipeline in `cli.py` and `api/`. Make the same change in both.
- Item 1's sites in `models/valuation.py`.
- Item 68: the CLI prints no assumption label. The cost-of-debt label already prints.
