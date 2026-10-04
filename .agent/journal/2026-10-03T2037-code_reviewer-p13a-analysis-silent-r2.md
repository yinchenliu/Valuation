---
agent: code_reviewer
assignment: P13a-analysis-silent
round: 2
verdict: approved
---

# Review of P13a-analysis-silent, round 2

- Programmer entry: `.agent/journal/2026-10-03T2033-programmer-p13a-analysis-silent-r2.md`
- Round 1 review: `.agent/journal/2026-10-03T2031-code_reviewer-p13a-analysis-silent.md`
- Assignment: step 2, "Round 2 amendment" (`.agent/assignments/P13a-analysis-silent.md:60-67`)

**How I measured it.** I exported `git archive 0021845` into `<scratchpad>/rev/r2` and
copied in only `analysis/normalizer.py` and `analysis/wacc.py`. `diff -rq` against the
round 1 baseline `<scratchpad>/rev/old` lists those two files and nothing else, apart from
`__pycache__`. `normalizer.py` is byte-identical to the file I reviewed in round 1
(`cmp`). Round 2 changed only `wacc.py`, by adding the block at `:231-244`. I did not touch
the shared tree.

## The guard checks

| Check | Result |
|---|---|
| conditional zero | clean |
| lookup with a fallback | `normalizer.py:269`. Unchanged; answered in round 1 |
| bare or-default | clean |
| money field defaulted to zero | clean |
| `**kwargs` | clean |
| `getattr(` from outside the file | `normalizer.py:221`. Unchanged; the name comes from a fixed set inside the file |
| dict of functions keyed by data | clean |
| model client outside `ingestion/` | clean (0 hits) |

The round 2 lines add no hit. The imports are unchanged.

## Rule 3, by reading (`calculate_wacc` weights, round 2)

| Value | Stops and names it? | Evidence (r2 tree) |
|---|---|---|
| `market_cap` NaN | yes. This stop already existed, and it runs before the new guard | `r34.py nan 100 5 none`: "market_cap is NaN …" |
| `market_cap + total_debt == 0` | yes. Names both fields and both values | (0, 0), (−100, 100), (300, −300) |
| `market_cap <= 0`, sum non-zero | **yes**. Names `market_cap` and its value, and claims no cause | (0, 100), (0, 100) with override 0.05, (−5, 100) |
| `market_cap` tiny but positive (1e-9) | forms weights | this is a value, not an absence. Not a finding |
| `total_debt` negative, `market_cap` > 0 | forms weights 1.2 / −0.2 | identical in `old`. See F4 |

**The order of the two checks.** In round 1 I suggested putting the new check before
the sum check. The programmer put it after. With both checks present, the inputs that
stop are the same in either order: the union of {sum == 0} and {market_cap ≤ 0}. Only the
message changes. Done-criterion 3 requires (0, 0) to name **both** inputs, and only
"sum first" satisfies that. The amendment does not fix the order. So I accept the
programmer's order. My round 1 wording was a suggestion, not a requirement.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | yes. Values are printed as they arrive |
| percentages at the route boundary | not touched |
| falsy not treated as missing | the new guard is `<= 0` on a value already checked to be finite. It does not test truthiness |
| `analysis/` layering | holds |

## Done-criteria, re-run (r2 tree; `old` for comparison)

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | an item for a year with no statement stops | ValueError naming 2019 … | `ValueError: 1 non-recurring item(s) carry a year with no income statement … year 2019, line_item 'sga', …`. `old`: no stop | yes |
| 2 | an item for a matching year applies | 2024 sga 150, ebit 250 | the same; 2023 untouched | yes |
| 3 | sum == 0 stops, both inputs named, no cause | yes | (0, 0) with and without override, and (−100, 100): the two-input message. `old`: 1.0 / 0.0 | yes |
| 3b | amendment: (0, 100) stops naming market_cap | yes | `ValueError: market_cap is 0.00, which is not greater than 0, …`, with and without override. `old`: 0.0 / 1.0, WACC 0.0447 | yes |
| 3c | amendment: (−5, 100) stops | yes | `market_cap is -5.00, …`. `old`: −0.0526 / 1.0526 | yes |
| 4 | 300 / 100 gives 0.75 / 0.25 | yes | `equity_weight 0.75 debt_weight 0.25`, identical in `old` | yes |
| 5 | Walmart unchanged | IDENTICAL | `r5.py extractions/WMT.json` in `old` and `r2`, `cmp`: **IDENTICAL** | yes |
| 6 | suite fails only where expected | 3 failed / 723; gate 1 failed | full: `3 failed, 723 passed`. Comparing the lists of failing tests with `old`, the one test added is `test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`. Gate form: `1 failed, 723 passed`, the same test. **The new guard turns nothing else red** | yes |
| 7 | gates not worse | ruff 5, mypy 10 / 4, census 67 | ruff and mypy (exact gate command) give output **byte-identical** to `old`: `Found 5 errors.` and `Found 10 errors in 4 files (checked 20 source files)`. Census 67 | yes |

## Findings (round 2)

### F4: a negative debt balance forms weights outside [0, 1] · `note`

**Evidence:** `r34.py 300 -50 5 0.05` returns `equity_weight 1.2 debt_weight -0.2` in **both**
`old` and `r2`. The output is identical, so this diff did not make it worse.
**Rule or document:** none that I can cite against this unit. Rule 3 is about an
absent input. A negative `total_debt` is a malformed value, not a missing one. The
weight lines `wacc.py:235-236` are untouched. The backlog does not record it
(`grep -niE "negative (debt|total_debt)"`: no hit). The programmer reported it, and the
orchestrator has said it will record it. **If it is not recorded, it is open and owned by nobody.**
**What would fix it:** a backlog line first. The fix is for a later unit to decide.

### F5: the market_cap message describes the 0 / 100 case, not the negative case · `note`

**Evidence:** `wacc.py:240-243` says "The equity weight is not set to 0.0 and the debt
weight is not set to 1.0". For (−5, 100), the old code would have produced −0.0526 / 1.0526.
**Rule or document:** none. The message is true, names the field and the value, and
claims no cause. It is only less relevant when the value is negative.
**What would fix it:** nothing is required. A later edit could say "the weights are not
formed" without naming specific values.

## Earlier findings

| # | Outcome | Note |
|---|---|---|
| F1 | **fixed** | the amendment is implemented at `wacc.py:231-244`. (0, 100) and (−5, 100) now stop, and (300, 100) is unchanged. My scratch probe in round 1 showed this costs no extra red test, and the real implementation confirms it |
| F2 | not_fixed, as expected | it is out of scope (`api/routes_valuation.py:411` still cites `normalizer.py:245`). It is a note, for the orchestrator or the next unit touching `api/` |
| F3 | not_fixed, as expected | the backlog wording of item 38's second face is the orchestrator's to restate. I re-ran both cases in `r2`: override with zero debt lines gives 1.0 / 0.0, and `balance_sheet=None` gives `AttributeError`. Both are identical to `old`, and the excluded face is unchanged |

## Pre-existing, already recorded: not findings against this unit

The same as round 1: items 38 (second face), 11, 37, 1, 12 / rule 5
(`sharesOutstanding`), 8, and the stale prose in `valuation-math.md`. None of them was touched in
round 2.

## Verdict

`approved`

F1 is fixed, as the amendment requires. Every done-criterion re-runs as claimed. The
failure set grows by exactly the one predicted test. Ruff and mypy are byte-identical
to the baseline, the census is 67, and Walmart's normalised statements are unchanged. No
`blocker` or `major` stands. F2 to F5 are notes. **F4 needs a backlog line from the
orchestrator before this unit is closed**, so that the negative-debt case has an owner.
