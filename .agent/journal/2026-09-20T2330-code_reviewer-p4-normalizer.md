---
agent: code_reviewer
assignment: P4-normalizer
round: 1
verdict: approved
---

# Review of P4-normalizer, round 1

Programmer entry: `.agent/journal/2026-09-20T2300-programmer-p4-normalizer.md`
Diff reviewed: `analysis/normalizer.py`, `85 insertions(+), 13 deletions(-)`, one file.

## The guard checks

Run over `analysis/normalizer.py` only.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean (0 hits) |
| lookup with a fallback — `.get(k, …)` | one hit, `analysis/normalizer.py:168` — `by_year.get(stmt.year, [])`. **Not in the diff**, and answered in the programmer's entry. Accepted: see the rule-3 table below |
| bare or-default — `or 0.0` | clean (0 hits) |
| money field defaulted to zero — `: float = 0.0` | clean (0 hits) |
| `**kwargs` on a calculation function | clean (0 hits) |
| `getattr(` on a name from outside the file | one hit, `:148`. **The name does not come from outside the file** — see the closed-set proof below. Not a finding |
| dict of functions keyed by data | clean. `_FIELD_EARNINGS_SIGN` maps `str -> float`; rule 2 allows a table of numbers explicitly |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → 0 hits |

`grep -n "print(" analysis/normalizer.py` → **0**. The stdout guess at the old `:50-51`
is gone; the three remaining `other_operating_expense"` hits (`:37`, `:38`, `:58`) are
table rows, no `return`.

## The sign table — re-derived independently

By reading: `ebit = revenue − total_operating_expenses`, and
`total_operating_expenses` (`models/financial_statements.py:66-73`) sums
`cost_of_revenue + sga + rd_expense + depreciation_amortization +
other_operating_expense`, so each of those five has `∂ebt/∂field = −1`.
`ebt` (`:91`) **adds** `other_non_operating`, so `∂ebt/∂other_non_operating = +1`.

By execution, my own script `c:/tmp/rev_p4_signs.py` — finite difference on **two** step
sizes (`+1.0` and `−7.5`) and against **both** `ebt` and `net_income`:

```
field                         dEBT/+1   dNI/+1  table  agree
cost_of_revenue                  -1.0     -1.0   -1.0   True
depreciation_amortization        -1.0     -1.0   -1.0   True
other_non_operating               1.0      1.0    1.0   True
other_operating_expense          -1.0     -1.0   -1.0   True
rd_expense                       -1.0     -1.0   -1.0   True
sga                              -1.0     -1.0   -1.0   True
MISMATCHES: none
```

**All six signs are correct.** Completeness is checked against the **range**, not the
length: `_LABEL_TO_FIELD` routes to exactly
`{cost_of_revenue, depreciation_amortization, other_non_operating,
other_operating_expense, rd_expense, sga}`; the sign table's key set is **equal** to it
(no missing field, no extra), and all six are real `dataclasses.fields` of
`IncomeStatement`.

Beyond the table, I checked the invariant the fix exists to restore — that the change in
`ebt` equals the item's declared `adjusted_impact` — over all 6 fields × 2 directions:
12/12 pass, `FAILS: none`. Two items on one field still accumulate (`ono` 80 → 10 on a
50 and a 20 remove), and `apply_adjustments(stmt, [])` still returns the same object.

## The import-time `assert` — judged, with the evidence

The trade was right, because **the `assert` is not the guard**; the bare subscript at
`:114` is. I broke a copy of the file outside the repository
(`c:/tmp/revp4/broken_norm.py`, the `other_non_operating` sign row deleted) and ran it
both ways:

```
=== import WITHOUT -O ===
AssertionError: _LABEL_TO_FIELD routes to a field with no entry in _FIELD_EARNINGS_SIGN: ['other_non_operating']
=== import WITH -O (assert stripped) ===
import succeeded under -O (assert stripped)
STOPPED: KeyError 'other_non_operating'
```

Under `-O` an incomplete table produces **a stop that names the field**, not a number.
`_field_delta` reads `_FIELD_EARNINGS_SIGN[field]` with no `.get`, no `or`, no
conditional — there is nowhere for a default sign to enter. So the `assert` only moves
the stop earlier and makes it louder; stripping it costs a better message, not the rule-3
guarantee. Coverage did not buy a weaker guard. (`-O`/`PYTHONOPTIMIZE` appears nowhere in
this project outside vendored `numpy`, so in practice the `AssertionError` is what fires.)

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `item.line_item`, unrecognised | **yes** — `ValueError` naming the label **and the year** | `:88-92`. Measured: `Unrecognised line_item 'Goodwill impairment charge' on the 2023 non-recurring item: … must name one of: cost_of_revenue, …` |
| `item.direction`, not one of two | **yes** — `ValueError` naming the value **and the year** | `:108-113`. Measured with `"Add_Back"`: `Unrecognised direction 'Add_Back' on the 2022 non-recurring item 'Restructuring charge': direction must be one of: add_back, remove.` |
| the sign of a routed field | **yes** — `AssertionError` at import, or `KeyError` naming the field at the lookup under `-O` | proved by deletion, above |
| `item.amount`, `item.year` | constructor stops — no default on either | `models/financial_statements.py:22,24` |
| `getattr(income_statement, f)` at `:148` | cannot be missing — closed set of six literals | proved by execution, below |
| `by_year.get(stmt.year, [])` at `:168` | returns `[]`, deliberately. **Not a missing input**: `by_year` is built from `non_recurring` two lines above, so a year absent from it *is* a year with no items, and `apply_adjustments(stmt, [])` is the documented identity. Unchanged by this diff | `:163-168`; `tests/unit/test_normalizer.py:90-97` |

Rule-3 census over `models analysis api ingestion`: **116**, down from **117**. I ran the
grep at `HEAD` (via `git stash`) and on the working tree; the single delta is exactly the
line the entry names — old `analysis/normalizer.py:69`,
`changes[field] = changes.get(field, 0.0) + delta`. `analysis/normalizer.py` now holds
**0** census hits. The comment the programmer reworded no longer matches the grep, and
that rewording is the right call: a census that counts prose is not a census.

## Rule 2 — the `getattr`, as the assignment asked

Verified against the code, not the claim. `_resolve_field` has exactly two exits:
`return field` inside the loop over `_LABEL_TO_FIELD` (`:87`), and `raise ValueError`
(`:88`). There is no third path and no fallback return. Every `field` is the second
element of a literal tuple in this file, so the attribute name is chosen by a literal —
the LLM's `line_item` string only *selects a row*, it is never used as the name.
Confirmed by execution: the range of `_LABEL_TO_FIELD` is the six names above and all six
are real `IncomeStatement` fields. Rule 2 is satisfied. The `**{…}` expansion into
`dataclasses.replace` at `:146-149` is unchanged by this diff and its keys come from the
same closed set.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean — `delta` is `amount × ±1`, dimensionless multiplier, same units in and out |
| percentages converted at the route boundary, once | n/a — no percentage crosses this file |
| falsy not treated as missing | clean — `if item.direction not in _LEGAL_DIRECTIONS` and `if field in changes` are membership tests, not truthiness; a `0.0` delta is stored, not discarded |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean — imports are `dataclasses` and `models.financial_statements` only |

## Done-criteria, re-run

Every row below is my own execution, not the entry's.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | two red tests green | `2 passed` | `2 passed` (inside the full run) | yes |
| 2 | nothing else broke | `90 passed`, 0 failed | `90 passed in 3.17s` | yes |
| 3 | whole suite | `1 failed, 92 passed` | **`1 failed, 92 passed in 18.92s`**, the failure being `test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` | yes |
| 4 | non-operating case | `ono` 30.0, `ebt` 430.0 | `BEFORE ono=80.0 ebt=480.0` → `AFTER ono=30.0 ebt=430.0`, identical to a `CLEAN` statement built at 30.0; caller's statement untouched at 80.0 | yes |
| 5 | the guess is gone | 0 `print(`, no fallback return | `grep -n "print(" …` → 0; no `return "other_operating_expense"` | yes |
| 6 | coverage of `normalizer.py` | 100% | `analysis\normalizer.py 36 0 100%`, `TOTAL 202 0 100%` (`COVERAGE_FILE=c:/tmp/.cov_rev_p4`) | yes |
| 7 | lint unchanged | 5, all `BLE001` | `Found 5 errors`, all `BLE001` | yes |
| 8 | types not worse | 33 in 4 files | `Found 33 errors in 4 files (checked 18 source files)` | yes |
| 9 | census ≤ 117 | 116 | **116**, and 117 at `HEAD` | yes |

**No test was edited.** `git diff --stat` → one file, `analysis/normalizer.py`.
`git status --short --untracked-files=all -- tests/` → empty. Criterion 3 reports one
failure, not zero, and the failure set is `{test_dcf_rule3_red::…balance_sheet_is_absent}`
— compared as a set, not as a count. Public signatures are unchanged;
`_resolve_field` is private and has no caller outside this file (`grep -rn "_resolve_field"`
→ `analysis/normalizer.py` only).

The assignment's step-4 fixture is one line short of its own required answer; that is the
orchestrator's error, recorded as such in the task. The programmer found it, ran both
line-ups and printed both. I reproduced both: with `cost_of_revenue = 400` the fix gives
`ebt` 430.0 as required; with the assignment's literal four lines it gives 830.0 because
`ebit` is 800. **Finding it and reporting it rather than silently resolving it is correct
behaviour**, and the fix is what the arithmetic says it is either way — the `ebt` delta
now equals `adjusted_impact` exactly, on every field and both directions.

## Findings

### F1 — the entry's diff size is wrong: it says 82/11, `git` says 85/13 · `minor`

**Evidence:** `git diff --numstat` → `85	13	analysis/normalizer.py`; entry line 29 says
"82 insertions, 11 deletions".
**Rule or document:** no rule in `docs/2-rules/rules.md`. It is a measurement in a journal
entry that does not match execution — most likely counted before the comment reword the
entry itself describes.
**What would fix it:** correct the two numbers in the entry. Nothing in the code changes.

### F2 — the completeness check is one-directional, and the error message advertises the wrong table · `note`

**Evidence:** `analysis/normalizer.py:67` uses `issuperset`, so a sign-table key with no
`_LABEL_TO_FIELD` row passes; `:91` builds the list of legal values a user sees from
`sorted(_FIELD_EARNINGS_SIGN)` rather than from the router's range.
**Rule or document:** none. Today the two sets are equal (I measured: `table keys not in
range: []`), so the message is accurate and nothing is wrong.
**What would fix it:** either assert set **equality**, or derive the message's list from
`{field for _, field in _LABEL_TO_FIELD}`, so a future sign row cannot advertise a value
`_resolve_field` would reject. Not required for this unit.

### F3 — the programmer's own F1 is real and belongs to a future unit · `note`

**Evidence:** `ingestion/claude_extractor.py:187` lists the six legal `line_item` values
and `ingestion/` has no tests; a non-compliant value now raises mid-valuation into
`api/routes_valuation.py`'s blanket `except Exception`.
**Rule or document:** none broken by this diff — converting a silent wrong number into a
stop is exactly what rule 3 requires, and the message is written to read well on the
results page.
**What would fix it:** a unit, after backlog item 8, that tests the extractor's
`line_item` contract and decides where an input error surfaces in the web app.
Orchestrator-owned.

The entry's F2 (the assignment/backlog fixture) and F3 (`STATUS.md`,
`docs/2-rules/rules.md:74-76` and `docs/3-architecture/valuation-math.md:28-31` now stale)
are correct and orchestrator-owned; I confirmed `rules.md:74-76` still names
`analysis/normalizer.py:46` as a live danger site and that site no longer exists. The
entry's F4 (`adjusted_impact`'s own `else -self.amount`) is real, is out of scope, and is
now unreachable through this file because `_field_delta` validates `direction` first.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 2 — zero net debt | `analysis/dcf.py:80` | no. Its red test stays red; criterion 3 depends on it |
| 1 — the zero-default census | 116 sites across `models/`, `ingestion/`, `api/` | no. This unit removed one of them and added none |
| 8 — blind `except Exception` | the 5 `BLE001` sites | no. The unit added no `except` |
| — | `analysis/normalizer.py:168` `.get(stmt.year, [])` | **no** — outside the diff hunks, and not a missing input: the absence is the datum |

## Verdict

`approved`

The sign table is correct on all six entries by my own independent derivation and by
finite difference against `ebt` and `net_income` on two step sizes; it covers
`_LABEL_TO_FIELD`'s range exactly; and the invariant the whole unit exists to restore —
`Δebt == adjusted_impact` — holds on all twelve field/direction combinations. The
import-time `assert` is a louder early stop layered over a real guard: with the assert
stripped by `-O`, an incomplete table raises `KeyError` naming the field, so no coverage
target bought a weaker check. Both new `ValueError`s name what backlog items 3 and 21
require, the `print` is gone, no test was edited, `git diff --stat` shows one file, the
suite reports `1 failed, 92 passed` with the expected single out-of-scope failure, and the
census fell 117 → 116 on exactly the line claimed. No finding cites a rule; F1 is a
`minor` bookkeeping error in the entry and F2/F3 are `note`s. Nothing blocks the tester.
