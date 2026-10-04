---
agent: programmer
assignment: P13e-growth-input
round: 1
status: complete
files_touched: [analysis/projector.py]
---

# P13e-growth-input — copy the caller's growth list; stop on projection_years below 1

## What I did

I made two changes in `derive_assumptions` (`analysis/projector.py`), and changed nothing else.

- **Item 66.** The supplied branch now binds `rev_growth = list(ov.revenue_growth_rates)`,
  so the padding `append` works on a copy. Before the change, a call with `[0.1]` and
  `projection_years=3` left the caller's list as `[0.1, 0.1, 0.1]`. A second call then
  read those rates as supplied and dropped the REPEATED clause. Rule 6.
- **Item 67.** Directly after `ov` is resolved, and before any year, revenue or rate is
  read, the function raises `ValueError` naming `projection_years` and its value when
  the value is not an `int` of 1 or more. A `bool` is also refused. Rule 3.

The `else 0.05` in the padding loop (item 41) is still there, as the assignment says.

Both defects were reproduced on the `19298f3` tree before the change. The probe is in
the scratch tree, `scratchpad/p13e_programmer/probe.py`. Result on base:
`C1 caller list after call: [0.1, 0.1, 0.1]`, `C2 equal: False`,
`C3 projection_years=0: NO ERROR`, `C3 projection_years=-1: NO ERROR`.

## Done-criteria

All runs use an isolated tree. Two `git archive 19298f3` exports are under
`scratchpad/p13e_programmer/`: `base/` (untouched) and `work/` (only
`analysis/projector.py` copied in). `extractions/WMT.json` is copied into both because
it is untracked. `diff -rq base work` shows only `analysis/projector.py` and caches.
Interpreter: `.venv/bin/python`. Commands are run from the tree root, with `PYTHONPATH=.`
for the probe.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | caller's list unchanged | pass | `probe.py` on work: `C1 caller list after call: [0.1] same id: True same object on ov: True`; returned rates `[0.1, 0.1, 0.1]`, not the caller's object |
| 2 | second call keeps the pad clause | pass | same script: `C2 equal: True`. Both labels end "...only 1 rate(s) reached it, so the last rate was REPEATED to fill the remainder...". The first-call label is word-for-word the base tree's first-call label |
| 3 | `projection_years` below 1 stops | pass | `C3 projection_years=0: ValueError: projection_years must be an integer of 1 or more; got 0. ...`; same for `-1`. Extra checks: `True` and `2.0` also raise `ValueError` |
| 4 | Walmart unchanged | pass | `cli.py --session-file extractions/WMT.json` on both trees, exit 0 on both. `diff` finds exactly 2 lines (27, 274), and both are only the tree path in the session-file name. After `sed` maps `/base/` and `/work/` to one path: `IDENTICAL after path normalisation`. This covers all 10 stages, so stages 2 to 6 are included |
| 9 | suite fails only where expected | pass | full suite on work: `2 failed, 793 passed`. The failure set is `{test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input, test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops}`, the same set as base. Gate form (`--ignore-glob="*_rule3_red.py"`): `793 passed`. **No test turned red** |
| 10 | gates not worse | pass | ruff `Found 5 errors.` (base 5). mypy gate `Found 10 errors in 4 files` (base 10 in 4). `projector.py` alone: 4 errors on base and 4 on work. Census grep: `65` (base 65). `ruff check analysis/projector.py`: `All checks passed!` |

Walmart input from the filing: stage 2 prints Revenue 648,125 / 680,985 / 713,163.
Stage 6 growth 4.9% = (713,163 / 648,125)^(1/2) - 1 = 4.897% (`python3 -c`), which is
the derived CAGR over the 2-year lookback. The growth figure comes from the filing,
not from a default.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `list(...)` copy in the supplied branch only | The derived branch already builds a new list (`[cagr.value] * n`) | `copy` on both branches would add nothing |
| Check `projection_years` directly after `ov = ...` | The assignment says "check it before any rate is derived". It also runs before `financials.years` is read, so a bad value stops the run even when the financials are also bad | A check placed after the revenue list would let an `IndexError` on empty revenues come first |
| Refuse `bool` | `True` is an `int` subclass and would run as a 1-year projection. Nobody types a year count as a boolean, so treating it as 1 would be a silent coercion (rule 3) | Accepting it would pass "integer of 1 or more" in a literal reading only |
| Refuse non-`int` such as `2.0` | The assignment says "not an integer". `range(2.0)` at `project_fcffs` would raise a bare `TypeError` later anyway | `int(2.0)` coercion would be a silent conversion |

No change was made to reach a target number.

## Rule 3 — what stops, and what does not

| Value read | If it were missing / invalid | Evidence |
|---|---|---|
| `ov.projection_years` | stops and names `projection_years` when < 1, not an int, or a bool | probe C3; `analysis/projector.py:156-165` |
| `ov.revenue_growth_rates` | an empty list goes to the derived branch, which is labelled (unchanged behaviour) | `:173` |
| `overrides` | **defaults to `ProjectionAssumptions()`** (`ov = overrides or ...`, `:149`). This is pre-existing and not a zero. The defaults are then labelled as derived or substituted per ratio. Not in this unit's scope | `:149` |
| padding with an empty list | **`else 0.05`**. This cannot be reached (an empty supplied list takes the derived branch, and `projection_years >= 1` now guarantees the derived list is non-empty). Item 41, deliberately left | `:190` |

## Measurements

| Gate | base `19298f3` | work |
|---|---|---|
| full suite | 2 failed (both `*_rule3_red.py`), 793 passed | identical set |
| gate form | 793 passed | 793 passed |
| ruff | 5 (all BLE001) | 5 |
| mypy (exact gate command) | 10 in 4 files | 10 in 4 files |
| census | 65 | 65 |

No figure moved on Walmart.

## What I did not do

- Item 41 (`else 0.05`), the bare `IndexError` on an empty revenue list, and item 1's
  sites. The assignment excludes them.
- No test was written or edited. A tester should lock the following. Each expected
  value comes from the assignment's criteria, not from the code:
  - the caller's list keeps its identity and contents;
  - two calls give the same label;
  - `ValueError` naming `projection_years` for 0 and -1. Also for `True` and `2.0`, if
    the reviewer accepts that decision.

## Findings for the orchestrator

- `api/routes_valuation.py:503` takes `projection_years: int = Form(5)` with no lower
  bound. A 0 from the form now gets a `ValueError` from `derive_assumptions`. Whether
  the route turns that into a 4xx naming the field, or a 500, is not measured here.
  This is a candidate check for whoever owns the API route.
