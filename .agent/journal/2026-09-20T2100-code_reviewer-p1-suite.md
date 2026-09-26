---
agent: code_reviewer
assignment: P1-suite
round: 1
verdict: approved
---

# Review of P1-suite, round 1

Entry under review: `.agent/journal/2026-09-20T2010-tester-p1-suite.md` (written by the
`tester` agent, read in place of a programmer entry).

Scope confirmed: `git status --short` shows this unit's changes confined to 9 modified
files under `tests/` and 3 new files under `tests/unit/` — exactly the 12 in
`files_touched`. Nothing outside `tests/**`. The `P2-hygiene` edits and the
`.claude/hooks/seal_baseline.py` change were excluded from every judgement below.

The unit's `verdict: fail` is a verdict about `analysis/dcf.py:80-81`, not about the
deliverable. I judged the deliverable.

## The guard checks

Run over `tests/**`.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | **14 hits**, all in the nine scripts, e.g. `tests/compare_models.py:98`, `tests/test_e2e_abbv.py:85`. All pre-existing, token-identical to `bc19431` — see the note below the table |
| lookup with a fallback — `.get(k, 0)` | **9 hits**, e.g. `tests/test_e2e_abbv.py:175` `info.get("sharesOutstanding", 0)`. Same, all pre-existing |
| bare or-default — `or 0.0` | **10 hits**, all `tests/compare_models.py:55-213`. Same |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | **14 hits**, all `tests/compare_models.py` and the two `_3years` scripts. Same |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output |

**Every hit is on a line this unit did not change semantically.** I proved that rather
than assuming it: I tokenised each of the nine scripts at `HEAD` and on disk and diffed
the token streams. The *only* token-level differences in all nine files are
`def main() -> None:`, `if __name__ == "__main__": main()`, the import re-ordering, the
removal of unused `pprint`, and three `f"…"` → `"…"` conversions. Command and result:

```
tokens HEAD -> working, per file, non-trivial diffs only:
_dump_lly_cache.py   +def +main ... -,pickle -,pprint  +if +__name__ +== +"__main__"
test_e2e_all_googl.py  ... -f"\n  === DCF RESULT ===" +"\n  === DCF RESULT ==="  ...
(9 files, no other NAME/NUMBER/STRING/OP token added, removed or altered)
```

None of these hits is a finding against this unit. They are instances of backlog item 1,
which the assignment and my brief both place out of scope. See the pre-existing table.

## Did the re-indentation change behaviour? — checked three ways

1. **String literals.** I compared every `STRING`/`FSTRING_MIDDLE` token between `HEAD`
   and disk. Result: identical in all nine files except the three deliberate F541 fixes,
   whose *content* is byte-identical (`'\n  Adjustments applied:'`,
   `'\n  === DCF RESULT ==='`), plus the new `"__main__"`. **No literal absorbed
   indentation.**
2. **Names made local.** `ast` walk of all 12 files: each script defines exactly one
   function (`main`), zero classes, zero `global`/`nonlocal`. There is no second
   function in any script that could still reference a name the wrapping made local.
   Multi-line strings appear only at line 1 (the module docstring, still at column 0).
3. **Mutable defaults.** `def main() -> None:` takes no arguments in all nine.

`pprint` was removed from `tests/_dump_lly_cache.py`; `grep -rn "pprint" tests/` → no
match, so the removal cannot NameError.

## Are the expected values independent of the code? — re-derived, not accepted

I re-derived a sample by hand from the formulas, without running `analysis/dcf.py`, and
checked the stated source actually produces the asserted number.

| Assertion | Stated source | My re-derivation | Agree? |
|---|---|---|---|
| `calculate_terminal_value(100.0, 0.02, 0.10) == 1275.0` | hand | `100·1.02 / (0.10−0.02) = 102/0.08 = 1275` | yes |
| `calculate_terminal_value(50.0, 0.0, 0.10) == 500.0` | identity | `g=0` ⇒ `FCFF/WACC = 50/0.10 = 500` | yes |
| `calculate_terminal_value(100.0, 0.04, 0.05) == 10400.0` | hand | `104/0.01 = 10400` | yes |
| `calculate_terminal_value(-100.0, 0.02, 0.10) == -1275.0` | identity (linearity) | `−102/0.08 = −1275` | yes |
| `discount_cash_flows([100,100], 0.25) == 144.0` | hand | `100/1.25 + 100/1.5625 = 80 + 64` | yes |
| `discount_cash_flows([100], 1.0) == 50.0` | hand, pins `t=1` | `100/2^1 = 50`; a `t=0` convention gives `100` | yes — this is the assertion that makes the exponent convention falsifiable |
| `run_dcf` worked example, all 9 derived figures | hand | `PV 144` · `TV 105/0.20 = 525` · `PV TV 525/1.5625 = 336` (exact: `1.5625·336 = 525`) · `EV 480` · net debt `(0+0+100)−30−0 = 70` (checked against `BalanceSheet.net_debt` at `models/financial_statements.py:187-198`) · equity `410` · `410/10 = 41` · `(41/20−1)·100 = 105` | yes, all nine |
| `run_dcf` perpetuity identity, `EV == 1000.0` for n=1..5 | closed form | n=3: `100/1.1+100/1.21+100/1.331 = 248.685`; `TV = 1000`, `PV(TV) = 1000/1.331 = 751.315`; sum `1000.0`. Holds for every n | yes |
| `WACCResult(Ke=.25, Kd=.90, t=.40, E/V=1, D/V=0).wacc == 0.25` | identity | `1·0.25 + 0·0.90·0.60 = 0.25` | yes |
| `ProjectedFCFF(80,30,−25,5).fcff == 80.0` and with `+25` | hand | `80+30−|∓25|−5 = 80` both ways | yes |
| raise messages name both figures | requirement | `f"WACC ({wacc:.4f}) must exceed terminal growth rate ({g:.4f})"` renders `WACC (0.0300) … (0.0500)`; `"0.03" in msg` and `"0.05" in msg` both hold. At `wacc == g == 0.05`, `msg.count("0.05") == 2`, so `>= 2` holds | yes |

**No assertion I checked was a photograph of output.** Every one is reachable from the
formula alone, and two of them (`wacc = 1.0`, and the n-invariant perpetuity) would go
red on an off-by-one in the discounting exponent — which is exactly what an
output-photograph test cannot do. The entry's process claim ("matched on the first
execution, no expectation revised") is not verifiable by me; the arithmetic, which is
the substantive question, is.

## Does any test lock a defect as an expectation?

**No.** Checked every assertion in both new files and both fixture builders.

- `result.net_debt == 70.0` and `result.cash == 30.0` are read from a balance sheet the
  fixture supplies. Neither is the `dcf.py:80-81` fallback.
- `implied_share_price == 41.0` is asserted with `diluted_shares = 10.0`, not `0`, so it
  does not lock `models/valuation.py:138`'s zero-share fallback.
- `upside_downside == 105.0` is asserted with `current_price = 20.0`, not `0`, so it does
  not lock `models/valuation.py:146-147`.
- `discount_cash_flows([], w) == 0.0` is **not** asserted. The entry states why, and the
  reason is correct: that one would encode an accumulator's zero as a rule-3 default.
- `tests/unit/test_dcf_rule3_red.py` asserts the **correct** behaviour (a `ValueError`
  naming the balance sheet) and is red. That is what `docs/5-testing/strategy.md` §2 and
  the assignment's "Known open items" require, and it is the opposite of locking the
  defect.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `wacc` vs `terminal_growth_rate`, incl. the `<=` boundary | yes | `analysis/dcf.py:24-27`; locked on type and on both figures by 3 tests. `pytest -q -k terminal` → `7 passed` |
| latest balance sheet in `run_dcf` | **no — defaults to `0.0`** | `analysis/dcf.py:80-81`. Backlog item 2, out of scope. Red test written, not asserted as a fallback |
| `projected_fcffs[-1]` when empty | stops, does not name | `analysis/dcf.py:73`. Entry reports it as a finding rather than photographing a bare `IndexError`. Correct handling |
| the unit's own new code (`tests/unit/*`) | n/a — no fallback, no `.get`, no `or`, no defaulted money field | guard greps clean on `tests/unit/` |

One forward-compat observation, not a rule break: the fixtures lean on `models/` zero
defaults (`IncomeStatement(year=2024)`, unset `short_term_debt`). The assignment
explicitly authorises that ("Use it to build fixtures, but do not assert on a default it
produced"), and no assertion rests on an *absent-means-zero* semantic. See F1.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | consistent — equity `410` (millions) / `10.0` (millions of shares) → `$41.00` per share, matching the repo convention visible at `tests/test_e2e_abbv.py:175` (`sharesOutstanding / 1e6`) |
| percentages converted at the route boundary, once | n/a — no route touched. `upside_downside` is asserted as `105.0`, the percent-number the property returns, not a fraction |
| falsy not treated as missing | clean. The unit deliberately exercises real zeros (`wacc = 0.0`, `g = 0.0`) as *values*, and adds no `if x` site of its own |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | unchanged by this unit. The new tests import only `pytest`, `analysis.dcf`, `models.financial_statements`, `models.valuation` — no key, no PDF, no network |

## Done-criteria, re-run

Every number below I executed myself on the combined tree.

| # | Criterion | Claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | collects with no key, 0 errors | 20 collected, 0 errors | `pytest -q --collect-only` → `20 tests collected in 0.09s`, no `ERROR`. `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` both `None`; `ls .env` → no such file | yes |
| 2 | 0 failed | 1 failed, deliberate | `pytest -q` → `1 failed, 19 passed in 0.23s`. Failure set = `{tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent}`, exactly the deliberate red. I compared the **set**, not the count | yes |
| 3 | ≥ 6 assertions, each sourced | 38 (35 on `dcf.py`) | `ast` count: `test_dcf.py` = **38** asserts / 15 test funcs; `test_dcf_rule3_red.py` = **1** assert / 1 func. 38 − 3 model-property asserts = 35 | yes |
| 4 | `WACC <= g` locked on type **and** message | 7 passed | `pytest -q -k terminal` → `7 passed, 13 deselected`. Type `ValueError` asserted, both figures asserted, `wacc == g` boundary covered | yes |
| 5 | a script still reaches the extraction call | pass as re-measured; command as written already broken at `bc19431` | `python tests/test_e2e_googl_3years.py` → `ModuleNotFoundError`. I reproduced the baseline independently: `git show HEAD:tests/test_e2e_googl_3years.py > c:/tmp/p1check/baseline_googl.py` then running it → `ModuleNotFoundError: No module named 'ingestion'` at module level. `python -m tests.test_e2e_googl_3years` → prints its banner and stops at `ValueError: GEMINI_API_KEY is not set.` from `ingestion/claude_extractor.py:836` | yes — the substance is met and the broken command is provably pre-existing |
| 6 | `tests/` clean except one `BLE001` | 1 | `ruff check tests --output-format concise` → `tests\test_e2e_all_googl.py:106:16: BLE001` / `Found 1 error.` I also confirmed the config does not hide anything: `ruff check --show-settings` lists `blind-except (BLE001)`, `unsorted-imports (I001)` and `f-string-missing-placeholders (F541)` as enabled | yes |
| 7 | coverage measured | 100% stmts, 100% branch | `pytest -q --cov=analysis.dcf --cov-branch --cov-report=term-missing` → `analysis\dcf.py 24 0 4 0 100%` | yes. The entry's caveat — that coverage.py does not count the `if latest_bs else 0.0` conditional *expression* as a branch — is correct and important, and I am glad it is written down |

Repo-wide: `ruff check .` → 5 errors, all `BLE001`, one of them the deferred
`tests/test_e2e_all_googl.py:106`. `mypy` is scoped by `docs/8-build/environment.md:95`
to exclude `tests/`, so this unit does not touch the type gate.

## Findings

### F1 — the fixture's stated arithmetic names five balance-sheet components but sets only three · `minor`

**Evidence:** `tests/unit/test_dcf.py:243-245` documents
`net debt = total_debt - cash - short-term investments = (0 + 0 + 100) - 30 - 0`, but the
`BalanceSheet` at `tests/unit/test_dcf.py:253-258` sets only `cash_and_equivalents`,
`short_term_investments` and `long_term_debt`; the two leading zeros come from the
`short_term_debt` and `current_portion_lt_debt` field defaults at
`models/financial_statements.py:155-156`.
**Rule or document:** not a rule break — the assignment sanctions building fixtures on
`models/` defaults, and `70.0` stays correct after backlog item 1. It is a
maintainability point: the comment claims a derivation the code does not fully state,
and the fixture will need editing when item 1 makes the fields required.
**What would fix it:** pass `short_term_debt=0.0, current_portion_lt_debt=0.0`
explicitly, so the five terms in the comment are the five terms in the code.

### F2 — the entry's function count is wrong · `note`

**Evidence:** the entry's "What I did" says "15 test functions"; `ast` gives 15 in
`tests/unit/test_dcf.py` plus 1 in `tests/unit/test_dcf_rule3_red.py` = **16**. The
assert count (39) and collected count (20) in the same sentence are both correct.
**Rule or document:** `docs/5-testing/strategy.md` §5 — state the unit of every count.
**What would fix it:** say 16, or say "15 in `test_dcf.py`".

### F3 — nothing mechanically distinguishes the deliberate red from a regression · `note`

**Evidence:** `pytest -q` → `1 failed, 19 passed`. The only marker is the filename
`test_dcf_rule3_red.py` and a docstring; a future gate that says "0 failed" will read
this as broken, and the entry has to supply
`--ignore=tests/unit/test_dcf_rule3_red.py` by hand.
**Rule or document:** none — `xfail` is correctly refused by `.claude/agents/tester.md`,
and the red test itself is right. This is about the gate, which the orchestrator owns.
**What would fix it:** the orchestrator states the phase-1 gate as
`pytest -q --ignore=tests/unit/test_dcf_rule3_red.py` → `19 passed`, and records that
the ignore is removed when backlog item 2 lands.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 2 — zero net debt on an absent balance sheet | `analysis/dcf.py:80-81` | no (outside write scope). Correctly reported, not asserted |
| 8 — blanket `except Exception` | `tests/test_e2e_all_googl.py:106` | only re-indented. Deliberately left; the entry says why, and `ruff.toml:9-14` says the same |
| 12 — tracked `tests/*.pkl` | `tests/.cache_*.pkl` | no. Not loaded, deleted or untracked |
| 1 — zero-default / `or 0` / `.get(k, 0)` sites | the 33 guard-grep hits listed above, all in the nine scripts | re-indented only, token-identical otherwise |

I saw all of these and am not reporting them. One observation for the orchestrator, about
a document rather than this unit: **backlog item 1's reproduction grep
(`docs/9-reference/refactor-backlog.md:52-54`) runs over `models analysis api ingestion`
and therefore excludes `tests/`.** The 33 hits above are uncounted by the `119` figure.
They are dev scripts, not pipeline code, and `docs/5-testing/strategy.md:119` already
says they "are not evidence of correctness" — but the item should say so explicitly,
rather than leaving a reader to infer that `tests/` is clean.

I also confirm the entry's finding 4 (the dead
`sys.path.insert(0, r"C:\Users\yinchenliu\…")` in all nine scripts) is real and
pre-existing, and that its consequence for done-criterion 5 is proven, not asserted.
Leaving it was the right call: repairing it is a path-resolution decision across nine
files, not a test.

## Verdict

`approved`

The deliverable is correct, in scope and maintainable. The re-indentation of 1,438 lines
is provably behaviour-preserving at token level — I checked string literals, locals,
classes and globals rather than trusting the mechanical-script claim. Every expected
value I re-derived matches its stated source, and two of them (the `wacc = 1.0` factor
and the n-invariant perpetuity) are genuinely falsifiable against an off-by-one, which is
the property an output-photographed suite cannot have. No assertion locks a rule-3
fallback, in the tests or in the fixtures; the one place a fallback could have been
asserted was correctly turned into a red test instead. All seven done-criteria re-measured
and agreed, including criterion 5, whose literal command I proved broken at `bc19431`
against an unmodified baseline copy. The three findings are one `minor` and two `note`s;
none blocks. The `fail` in the unit's own entry belongs to `analysis/dcf.py:80-81`, which
this unit was forbidden to touch and reported correctly.
