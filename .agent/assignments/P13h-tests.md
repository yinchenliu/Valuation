---
id: P13h-tests
phase: 13 — silent defects first, wave 3
agent: tester
depends_on: [P13h-zero-debt-confirm]
---

# Lock the "confirm zero debt" behaviour: the bypass is gone, the confirmation works, and its label says so

## Objective

`P13h-zero-debt-confirm` is committed at `bc30be4` and approved in round 1. It closes
part (a) of backlog item 38b, on the user's option 1 of 2026-10-04. No test locks it,
and no test turned red. The comment at `tests/unit/test_wacc.py:31-35` says no test
asserts item 38b (a) "either way". That is now stale: the user decided, so lock the
decision.

Read first: `.agent/assignments/P13h-zero-debt-confirm.md` (its table in step 1 is the
specification), the programmer entry `2026-10-04T0936-programmer-p13h-zero-debt-confirm.md`,
the review `2026-10-04T0948-code_reviewer-p13h-zero-debt-confirm.md`, and
`.claude/agents/tester.md` from its first section. The reviewer's probe scripts
`rv_wacc.py`, `rv_route.py` and `rv_cli.py` are in
`/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/49a4d4a7-ff32-4deb-a1ba-ba1f44e044e1/scratchpad/p13h_reviewer/`.
Read them for the inputs. Do not copy their printed output as an expected value.

## What to do

1. **Each row of the assignment's table** in step 1, through `calculate_wacc` and
   `cost_of_debt_with_source`:
   - zero debt, interest 30, no override, not confirmed: `ValueError`; the message names
     `--confirm-zero-debt` and "Confirm zero debt";
   - the same with override 0.05: the same `ValueError` (the bypass is gone);
   - confirmed, no override: weights 1.0 / 0.0, WACC equal to the cost of equity, cost of
     debt 0.0, and a label that says the user confirmed the zero;
   - confirmed with override 0.05: cost of debt 0.05, weights 1.0 / 0.0, WACC equal to
     the cost of equity, and a label that says the rate does not reach the WACC;
   - zero debt, zero interest, override given: the label says the rate does not reach
     the WACC;
   - confirmed beside debt 100: `ValueError` naming `balance_sheet.total_debt` and the
     confirmation;
   - debt above 0, not confirmed: weights and WACC by hand for (300, 100) with interest 5.
2. **NaN and infinite interest** with zero debt, under an override and under a
   confirmation: `ValueError` naming `income_statement.interest_expense`.
3. **The CLI flag.** `--confirm-zero-debt` sets `ProjectionAssumptions.zero_debt_confirmed`
   through `build_overrides`, and its absence leaves it `False`. Patch `sys.argv`; make no
   network call.
4. **The form field.** On `POST /valuation`: `on` reaches `calculate_wacc` as `True`, an
   absent field or `""` as `False`, and any other value (`yes`, `ON`) shows the named
   stop and never calls `calculate_wacc`. `GET /assumptions` with a filing named shows
   `name="confirm_zero_debt"`. Use the route test helpers that exist; patch the price
   fetch, so no network call is made.
5. **Rewrite the stale comment** at `tests/unit/test_wacc.py:31-35` so it states what is
   now locked.

Derive every expected weight, WACC and rate by hand from the formula in
`analysis/wacc.py`'s module docstring, and write the derivation beside the assertion.

## Files in scope

- `tests/unit/test_wacc.py`
- `tests/unit/test_routes.py`
- `tests/unit/test_cli_overrides.py` (new)

**Nothing else.** The `P14a-units` programmer runs at the same time and edits
`ingestion/`, `models/financial_statements.py`, `cli.py`, `templates/_statements.html`
and four docs. Do not touch them. The write guard refuses scratch paths inside the
repository, so work in your own subdirectory of the session scratchpad:
`/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/49a4d4a7-ff32-4deb-a1ba-ba1f44e044e1/scratchpad/p13h_tester/`.
Export `git archive bc30be4` and copy in your test files. Never `rm -rf` outside your
directory, and do not stash or reset the shared tree. Set `PYTHONDONTWRITEBYTECODE=1`
when you run mutants.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form on the isolated tree | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite on the isolated tree | exactly the 2 known `*_rule3_red.py` failures | `.venv/bin/python -m pytest -q` |
| 3 | each behaviour is locked | each of steps 1 to 4 has a test that turns red when its code is reverted to `a993b94` or its check is removed | mutants in a scratch copy |
| 4 | no network call and no paid API call | 0 | a guard in each route and CLI test |
| 5 | two counts | accuracy and coverage, as `tester.md` requires | its "Report two counts" section |
