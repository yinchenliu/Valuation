---
agent: code_reviewer
assignment: P13e-growth-input
round: 1
verdict: approved
---

# Review of P13e-growth-input, round 1

Programmer entry: `.agent/journal/2026-10-04T0102-programmer-p13e-growth-input.md`

Diff: `analysis/projector.py` only, +21/-1 inside `derive_assumptions` (a `projection_years`
guard after `ov = ...`, and `list(...)` around the supplied growth list). No import added.

**Where I measured.** The write hook denies the in-repo `scratchpad/p13e_reviewer/` to this
agent, so the trees are under the session scratchpad outside the repository
(`/private/tmp/claude-501/.../scratchpad/p13e_reviewer/{base,work}`): two `git archive f6da3e9`
exports, `work` with only `analysis/projector.py` copied in, `extractions/WMT.json` copied into
both. `diff -rq base work` → only `analysis/projector.py`. The shared tree was not touched.

## The guard checks

| Check | Result |
|---|---|
| conditional zero | hits at `:73`, `:190`, `:307`. None is on a line the diff touched. `:190` is item 41 (excluded by the assignment, answered in the entry); `:73`, `:307` are in item 1's census |
| lookup with a fallback | clean |
| bare or-default | clean (`:149` `overrides or ProjectionAssumptions()` is pre-existing, not a literal, answered in the entry) |
| money field defaulted to zero | clean |
| `**kwargs` | clean |
| `getattr(` | clean |
| dict of functions keyed by data | clean |
| model client outside `ingestion/` | clean (`models/ analysis/ api/`) |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `ov.projection_years` | yes: `ValueError` naming the field and its `repr`, for <1, non-`int`, `bool` | `analysis/projector.py:156-165`; probe below |
| `ov.revenue_growth_rates` | empty goes to the labelled derived branch (unchanged) | `:173` |
| padding seed `else 0.05` | unreachable now that `projection_years >= 1` guarantees a non-empty derived list; item 41, left as instructed | `:190` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | no figure touched |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing | the guard uses `isinstance` and `< 1`, not a truthiness test |
| `analysis/` imports | no import added |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | caller's list unchanged | `[0.1]`, same id | base: `C1 after: [0.1, 0.1, 0.1]`; work: `C1 after: [0.1] same id: True ov holds: True returned is caller: False` | yes |
| 2 | second call keeps the pad clause | equal | base: `C2 equal: False | REPEATED in 2nd: False`; work: `C2 equal: True | REPEATED in 2nd: True`. First-call label is word-for-word the base label | yes |
| 3 | 0 and -1 stop | `ValueError` | base: `NO ERROR, years 0` / `-1`; work: `ValueError projection_years must be an integer of 1 or more; got 0.` and `got -1.`. `1` still runs | yes |
| 4 | Walmart stages 2-6 identical | identical after path normalisation | stages 2-6 identical in all three run pairs. Run 1 differed at stage 10 only (`PV of Terminal Value 214,819M` vs `214,820M`); runs 2 and 3 identical after path normalisation, and `work` run 1 vs `work` run 2 shows the same 1M flip on one tree. Not this unit's: see F3 | yes (stages 2-6) |
| 9 | red set | `2 failed, 793 passed`, same set | both trees: `2 failed, 793 passed`; failure sets compared by name, identical (`test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`); the projector red test fails with the same `IndexError` reason on both. Gate form 793 passed on both. No test turned red | yes |
| 10 | gates | ruff 5, mypy 10 in 4, census 65 | ruff `Found 5 errors.` both; mypy exact gate `Found 10 errors in 4 files` both, `projector.py` 4 and 4 (same four, shifted +17); census `65` both | yes |

**The `True` / `2.0` refusal (orchestrator asked me to judge).** Accepted. The assignment's
words are "not an integer of 1 or more". `bool` is an `int` subclass only by Python's
implementation; letting `True` run as a 1-year projection is a silent coercion, which rule 3
forbids. `2.0` on base already died with a bare `TypeError: can't multiply sequence by
non-int of type 'float'` at `:184`, so refusing it with a named `ValueError` turns an unnamed
stop into a named one and moves no figure. All live callers pass a Python `int`
(`cli.py:142` `type=int`, `api/routes_valuation.py:503` `int = Form(5)`). The web form's
`"2.0"` is coerced to `int` 2 by FastAPI before it arrives and runs on both trees.

## Findings

### F1 — the stop message gives a length reason for a type refusal · `note`

**Evidence:** work probe: `C3 2.0 ValueError projection_years must be an integer of 1 or more; got 2.0. A projection shorter than one year has no cash flow to discount.` (same for `True`, `'3'`).
**Rule or document:** none broken; the field and value are named. The second sentence is wrong for those inputs.
**What would fix it:** drop the second sentence, or say it only when the value is an `int` below 1.

### F2 — line citations into `projector.py` drift by +17 · `note`

**Evidence:** `grep -rnoE "projector\.py:[0-9]+" docs tests STATUS.md` → e.g. `tests/unit/test_projector_rule3_red.py:99` cites `:162`, `tests/unit/test_projector_sources.py:98` cites `:226`, `tests/unit/test_historical_fcff_year.py:317` cites `:189`; `STATUS.md:414` and `refactor-backlog.md:667` cite `:169` (already stale at base; `else 0.05` is now `:190`).
**Rule or document:** none. Prose citations, not assertions; no test reads them.
**What would fix it:** the tester and orchestrator refresh them when they next touch those files.

### F3 — Walmart CLI stage 10 is not reproducible run to run · `note` (not this unit's)

**Evidence:** the same `work` tree, two runs: `diff cli_work.txt cli_work_2.txt` → `241c241 < PV of Terminal Value: $ 214,820M --- > $ 214,819M`. Base runs show the same value set. Stages 2-6 never moved.
**Rule or document:** none in scope. Probably live market data sitting near a rounding edge. Not in the backlog (`grep -niE "nondetermin|run to run" refactor-backlog.md STATUS.md` → nothing).
**What would fix it:** the orchestrator records it, so that later "Walmart identical" criteria compare stages 2-6 or pin market data.

### F4 — web route answer to `projection_years=0` (measured, `api/` out of scope) · `note`

**Evidence:** `TestClient(app).post("/valuation", data={ticker: WMT, session_file: <abs WMT.json>, projection_years: "0"})`, route B, `fetch_price_data` stubbed to raise. Base: `0 -> 200 | STUB: fetch_price_data reached` (also `-1`): the run went on to market data. Work: `0 -> 200 | projection_years must be an integer of 1 or more; got 0.` (also `-1`), stopped before any market-data call.
**Rule or document:** the HTTP 200 comes from the blanket `except Exception` at `api/routes_valuation.py:703` (backlog item 8, already recorded). It is not a 500, and the page names the field.
**What would fix it:** the orchestrator decides whether a later `api/` unit adds `ge=1` on the form field and a 4xx. Not required here.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 41 dead `else 0.05` | `analysis/projector.py:190` | no (shifted only) |
| 1 conditional zeros | `analysis/projector.py:73`, `:307` | no |
| 11 four `union-attr` errors | `analysis/projector.py:172, 225, 235, 345` | no (shifted only) |
| empty revenues gives bare `IndexError` (red test) | `analysis/projector.py:172-180` | no |
| 8 blanket `except Exception` | `api/routes_valuation.py:703` | no |
| 6 falsy-as-missing `x / 100 if x else None` | `api/routes_valuation.py:588-592` | no |

## Verdict

`approved`

Both defects are fixed as the assignment asks, and I measured each one: the caller's list keeps its
identity and contents, the second call keeps the REPEATED clause, and 0 and -1 stop with a
`ValueError` naming `projection_years` before any rate is derived. Scope is the one file. No
guard hit is on a touched line. The failure set, ruff, mypy and the census are unchanged by
name and by count. All four findings are notes and none blocks.
