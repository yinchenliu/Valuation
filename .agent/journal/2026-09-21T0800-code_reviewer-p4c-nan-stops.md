---
agent: code_reviewer
assignment: P4c-nan-stops
round: 1
verdict: approved
---

# Review of P4c-nan-stops, round 1

Programmer entry: `.agent/journal/2026-09-21T0700-programmer-p4c-nan-stops.md`

Every measurement below is mine. I built my own probe at `c:/tmp/rv_p4c_chain.py` (23
cases, 6 of them controls) and ran it against a `git archive e01dddf` export at
`/c/tmp/rv_base` and against the working tree. Transcripts: `c:/tmp/rv_before.txt`,
`c:/tmp/rv_after.txt`. I did not run the programmer's script.

## The guard checks

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | hit at `analysis/dcf.py:101,102` — **backlog item 2, untouched by the diff**, its red test is required to stay red by criterion 4. Answered in the entry |
| lookup with a fallback — `.get(k, 0)` | clean |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (`grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output) |

No unanswered hit. `llm-boundary.md` does not apply: `ingestion/` is untouched.

## Every new guard is `math.isnan`, read one by one

| Guard | Form | Verdict |
|---|---|---|
| `analysis/capm.py:57` | `market_returns.size != stock_returns.size` | size comparison, not a value comparison — correct |
| `analysis/capm.py:65` | `market_returns.size < MINIMUM_REGRESSION_OBSERVATIONS` | size comparison — correct |
| `analysis/capm.py:79` | `math.isnan(slope) or math.isnan(r_value) or math.isnan(std_err)` | correct |
| `analysis/wacc.py:40` | `math.isnan(value)` | correct |
| `analysis/dcf.py:32` | `math.isnan(wacc) or math.isnan(terminal_growth_rate)` | correct, **and placed before** the `wacc <= terminal_growth_rate` line at `:39` |
| `analysis/wacc.py:104` | `_require_finite(tax_rate, …)` | correct, **and placed before** the clamp at `:106` |

**Not one value guard is a comparison.** The two comparisons that remain are on
`.size`, which is an `int` and cannot be NaN.

## Rule 3, by reading

| Value | Stops and names it? | Evidence (my probe) |
|---|---|---|
| `price_data.market_returns` empty, ERP supplied | yes, names `market_returns` | case A: before `implied_share_price=nan`; after `ValueError: market_returns and stock_returns hold 0 observations…` |
| series of unequal length | yes, names both | case E: before `ValueError: Array shapes are incompatible for broadcasting` (numpy's, names nothing); after names both fields and both counts |
| zero-variance market series | yes, names `market_returns` and its variance | case D: before `implied_share_price=nan`; after `…produced no finite beta… variance 0.0 over 3 observations` |
| `capm_result.cost_of_equity` NaN | yes | case M: before `wacc=nan`; after raises |
| `market_cap` NaN | yes | case N: before `nan`; after raises |
| `cost_of_debt` NaN (override) | yes | case P: before `nan`; after raises |
| `tax_rate` NaN | yes, **before the clamp** | case O: before `WACCResult.tax_rate == 0.0`; after raises |
| `wacc` NaN into `run_dcf` | yes | case R: before `nan`; after raises |
| `terminal_growth_rate` NaN | yes | case T: before `nan`; after raises |
| `projected_fcffs` empty | yes, names `projected_fcffs` | case S: before `IndexError: list index out of range`; after `ValueError: projected_fcffs is empty…` |
| a NaN inside one `ProjectedFCFF`, finite WACC | **no — `implied_share_price=nan`** | cases U, V: `nan` before **and** after. Pre-existing, not on the backlog, not touched. See F4 |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | no figure crosses a unit boundary in this diff; the new code only tests and raises |
| percentages converted at the route boundary, once | no route touched |
| falsy not treated as missing | clean — no new `if x` where `if x is not None` is meant; `_require_finite` tests `math.isnan`, not truthiness |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | `analysis/capm.py:16` imports `PriceData` from `ingestion/` — **backlog item 17, pre-existing, unchanged by the diff** and named in the entry. No new cross-layer import: the diff adds only `math` and uses `numpy`, already present |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | empty market series + supplied ERP stops, names the input | pass | my case A, full chain `run_capm → calculate_wacc → run_dcf`: `nan` price before, `ValueError` naming `market_returns` after | yes |
| 2 | no NaN reaches `run_dcf` from any path | pass | cases D, M, N, O, P, R, T all returned a NaN (or a silent `0.0`) before and all raise after | yes |
| 3 | empty `projected_fcffs` stops, names the field | pass | case S, `IndexError` → `ValueError: projected_fcffs is empty…` | yes |
| 4 | no existing assertion changed meaning | `1 failed, 120 passed`, same failure | `1 failed, 120 passed`. Failure **set** on both trees = `{tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent}`, same reason `DID NOT RAISE ValueError`. Collected node sets diffed: **identical, 121 nodes** | yes — set-diffed, not counted |
| 5 | coverage does not fall | **FAIL, disclosed**: `capm.py` 92%, `dcf.py` 93%, `wacc.py` 97%, 6 missed | reproduced exactly: `58, 66, 80` / `33, 82` / `41`. I read all six: every one is a new `raise ValueError(`. With `--cov-branch` the gap is the same 6 statements and their 6 partial branches, nothing else | yes — the number and the honesty both check out |
| 6 | lint unchanged | 5, all `BLE001` | `Found 5 errors`; `uniq -c` on the codes → `5 BLE001`, same five files | yes |
| 7 | types not worse | set-identical, 14 | my own `git archive e01dddf` export, line numbers stripped, `comm -13` and `comm -23` both **empty**, `before=14 after=14` | yes |
| 8 | census did not rise | 116 | the `rules.md` grep → **116** | yes |

### Criterion 3 of your seven — the control, to full precision

Six controls, byte-identical before and after
(`diff <(grep -A1 CONTROL rv_before.txt) <(grep -A1 CONTROL rv_after.txt)` → no output):

```
F. healthy 5-point chain   beta=1.596774193548387  std_error=0.10158303025640267
                           wacc=0.1146451612903226  implied_share_price=12.697763190328896
G. same, debt 600          implied_share_price=12.582903095558143
H. same, debt 0            implied_share_price=14.433528532009895
L. calculate_beta healthy  (1.596774193548387, 0.9880040322580649, 0.10158303025640267)
Q. calculate_wacc healthy  0.11480000000000001
W. run_dcf healthy         11.676916620873257
```

My inputs are not the programmer's, so my figure is not `10.2423…`; the point is the
same and stronger, because it is an independent set of healthy paths and **not one
digit of any of them moved**. The 120 hand-derived assertions agree.

### Criterion 4 of your seven — the threshold of 3, both halves

The scipy half, measured on a perfect fit `y = 2x + 1`, scipy 1.18.1:

```
n=0  slope nan  rvalue nan  stderr nan
n=1  slope nan  rvalue nan  stderr nan
n=2  slope 2.0  rvalue 1.0  stderr nan     <- finite slope, NaN standard error
n=3  slope 2.0  rvalue 1.0  stderr 0.0
```

Confirmed. My probe case C (n = 2) shows what that cost: before the change the full
chain **rendered a share price of `20.740976647274042` while carrying
`std_error=nan`** into `CAPMResult`; after it stops.

The derivation half holds too: `SE(beta) = sqrt(SSE / ((n - 2) · Sxx))` is undefined
unless `n - 2 >= 1`, i.e. `n >= 3`, and `calculate_beta`'s contract is three
statistics, all of which must be finite for it to return. The threshold was **not**
chosen to fit a number — it is the opposite of number-fitting, because adopting it
*removes* a number the old code produced (case C above) rather than preserving one. No
existing assertion covers n < 3; I checked, the collected node set is unchanged.

`MINIMUM_REGRESSION_OBSERVATIONS` is not a rule 6 assumption. It reaches no displayed
figure — it decides only whether the run stops — and its derivation is written above
its definition at `analysis/capm.py:19-28`. The programmer pre-empted this question
correctly.

### Criterion 5 of your seven — the clamp, confirmed

```
min(nan, 0.50) = nan        max(0.0, min(nan, 0.50)) = 0.0
```

and end to end, probe case O, `calculate_wacc(..., tax_rate_override=nan).tax_rate`:

```
before (e01dddf):  RETURNED 0.0        <- a NaN tax rate read as 0%, full tax shield
after:             RAISED ValueError: tax_rate (tax_rate_override or
                   income_statement.effective_tax_rate) is NaN, …
```

The check sits at `analysis/wacc.py:104`, the clamp at `:106`. **Before, as required** —
after the clamp it could never fire, because the clamp has already turned the evidence
into a plausible `0.0`. This is the same mechanism as item 20 in a second place and
the programmer found it while editing the line; fixing it here was right.

`analysis/fcff.py:44` holds the identical clamp
(`tax_rate = max(0.0, min(tax_rate, 0.50))`) and is **correctly untouched** —
`git status --porcelain` lists three modified files and `analysis/fcff.py` is not one
of them. That file is not in scope and widening scope would have been a finding. It
needs a backlog item; see F5.

### Criterion 6 of your seven — the `_require_finite` helper

**Judged a reasonable structure, not a way of hiding uncovered branches**, but it costs
the tester something and the tester must know it.

- Reachability: I reached all six new `raise` statements by execution — `capm.py:58`
  (case E), `:66` (A, B, C, I, K), `:80` (D, J), `dcf.py:33` (R, T), `:82` (S),
  `wacc.py:41` (M, N, O, P). **No unreachable guard was written to hold a percentage**,
  and the percentage was allowed to fall rather than be protected. Your written
  instruction was obeyed.
- The five call sites `wacc.py:94, 97, 104, 109, 111` are themselves statements and are
  all covered; the helper moves **one** uncovered line, not five behaviours. The
  alternative — five textually identical `if math.isnan(x): raise` blocks in one
  function — is worse to read.
- The cost: statement coverage can no longer tell *which* of the five guards has a
  test. One test on any call site turns `wacc.py:41` green. See F3 — the tester needs
  five cases, one per field name, not one.

The disclosure was volunteered precisely because it flatters the number. That is the
behaviour the process wants.

### Criterion 7 of your seven — the sets

Done above: failure set identical (set-diffed and node-set-diffed, not counted), lint
5/5 `BLE001` same five files, mypy `comm` both directions empty at 14, census 116.

## The two things not charged to the unit

**The three "Known open items" were left, and named.** Verified by reading the diff:

1. `analysis/capm.py:16` `from ingestion.price_fetcher import PriceData` — context line
   in the diff, unchanged. Item 17.
2. `analysis/capm.py:98-100` geometric → arithmetic switch — not in the diff at all.
3. `analysis/capm.py:137-138` `r_sq = 0.0` / `std_err = 0.0` under `beta_override` —
   not in the diff.

**`tests/unit/test_capm.py:258` does assert the switch's output.** Confirmed by
reading:

```
tests/unit/test_capm.py:240  def test_arithmetic_fallback_when_compounding_wipes_out()
tests/unit/test_capm.py:256      market = [-1.0, 0.2]
tests/unit/test_capm.py:258      assert result == pytest.approx(-0.8)
```

The docstring above it even says "formula chosen at run time, and the entry for this
unit reports it". So a future unit that raises at `analysis/capm.py:98-100` **will turn
that test red**, and the assignment for it must say so and must authorise the test
change. The programmer's report of this is accurate.

## Findings

### F1 — `_require_finite` tests NaN only, so its name over-promises · `note`

**Evidence:** `analysis/wacc.py:40` is `if math.isnan(value):` under a helper named
`_require_finite`; `math.isnan(float('inf'))` is `False` and `inf <= 0.025` is `False`.
**Rule or document:** none — this breaks no rule. I checked whether `inf` is reachable:
`IncomeStatement.effective_tax_rate` (`models/financial_statements.py:101`) guards its
divisor, and `calculate_cost_of_debt` returns early on `total_debt == 0`, so this
repository's own arithmetic produces NaN, not `inf`. It is a naming question, not a
live hole.
**What would fix it:** either rename to `_require_not_nan`, or widen the body to
`math.isfinite`. A future unit's call, not this one's.

### F2 — the terminal-value message's tail names WACC when the growth rate is the NaN · `note`

**Evidence:** probe case T — `ValueError: WACC (0.11512000000000001) and terminal growth
rate (nan) must both be numbers; … A NaN WACC means an input was absent or degenerate in
CAPM or in WACC` (`analysis/dcf.py:34-37`).
**Rule or document:** none. Rule 3's requirement is met — both fields are named and both
values printed, so the reader can see which one is NaN.
**What would fix it:** drop or condition the last sentence. Cosmetic.

### F3 — the five WACC guards collapse to one coverage line; the tester needs five cases · `note`

**Evidence:** `--cov-report=term-missing` → `analysis\wacc.py  34  1  97%  41`, one
missed line covering the call sites at `wacc.py:94, 97, 104, 109, 111`.
**Rule or document:** none — disclosed by the programmer in its own entry.
**What would fix it:** nothing in this unit. The tester that closes criterion 5 must
write one case per field name — `capm_result.cost_of_equity`, `cost_of_debt`,
`tax_rate`, `market_cap`, `balance_sheet.total_debt` — and assert the message, not just
that it raised.

### F4 — a NaN in one `ProjectedFCFF` still reaches `implied_share_price` · `note`, **and it needs its own backlog item**

**Evidence:** probe cases U and V, `run_dcf` with a finite `WACCResult` and a NaN in a
middle year (U) and in the final year (V): `RETURNED nan` **before and after**.
**Rule or document:** rule 3, but **not against this unit** — `analysis/dcf.py:46-57`
is unchanged in the diff, the defect is not on the backlog, and the assignment scoped
the unit to items 20 and 14. Widening scope would itself have been a finding.
**What would fix it:** `math.isnan` in `discount_cash_flows` naming the year, and one on
`final_fcff`. The programmer's diagnosis is exactly right and the fix is two lines.
**Answer to your question: yes, it wants its own backlog item.** All three stops this
unit added sit on the discount-rate side; the cash-flow side is unguarded, the upstream
is `analysis/projector.py` feeding on item 1's zero-defaulted money fields, and it
renders a NaN price on a clean run. Same cost class as item 20.

### F5 — the `fcff.py` twin of the clamp defect is unrecorded · `note`, **record it**

**Evidence:** `analysis/fcff.py:44` — `tax_rate = max(0.0, min(tax_rate, 0.50))`,
identical to the line fixed at `analysis/wacc.py:106`; `max(0.0, min(nan, 0.50))` is
`0.0`.
**Rule or document:** rule 3, **not against this unit** — the file is out of scope and
`git status` confirms it was not touched.
**What would fix it:** a backlog entry, either new or folded into item 23
(`analysis/fcff.py` holds no `raise` at all), which covers the file but not this
mechanism.

**No `blocker`. No `major`. No `minor`.** Every guard-check hit and every rule-3 "does
not stop" row in this review is either pre-existing-and-recorded or pre-existing-and-
now-reported; none is in a line this unit wrote or moved.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 2 — missing balance sheet → zero net debt | `analysis/dcf.py:101,102` | no. Not in the diff; its red test is still red, for the same reason |
| 9 — unlabelled `DEFAULT_COST_OF_DEBT` | `analysis/wacc.py:70` | no |
| 17 — `analysis/` imports `ingestion/` | `analysis/capm.py:16` | no. Context line only; no new cross-layer import |
| 22 — zero debt balance → 0% cost of debt | `analysis/wacc.py:64-65` | no |
| 1 — the 116 zero-default sites | repository-wide | no; census still 116 |
| — `equity_weight = 1.0` when `total_value == 0` | `analysis/wacc.py:114-121` | no. Not on the backlog; named in the programmer's entry, unchanged lines |

I saw each of these and they are already on the record.

## Earlier findings — re-reviews only

None; this is round 1.

## For the orchestrator, not a finding

`STATUS.md` §1 records `analysis/` at 100% coverage and §5 ranks item 20 as the highest
open defect. Both are now stale: coverage is 97% with six named uncovered `raise`
lines, and items 20 and 14 are closed by this unit. Neither the programmer nor I may
edit that file.

## Verdict

`approved`

The unit does what it was asked and proves it. I reproduced the three cases you named
plus twenty more, on my own script against my own baseline export, and the before/after
transcripts confirm every claim in the entry: the empty-series chain that rendered
`nan` now raises naming `market_returns`; the degenerate-variance case raises naming
`market_returns` and its variance; the empty `projected_fcffs` raises naming the field;
the NaN tax rate that was silently read as 0% now stops, and the check is on the right
side of the clamp. Every value guard is `math.isnan` and the only comparisons left are
on `.size`. The six controls are byte-identical to the last digit, the collected node
set and the failure set are unchanged, mypy is set-identical at 14, lint is 5/5
`BLE001`, and the census is 116. The one failed criterion — coverage 100% → 97% — is a
disclosed, enumerated, honestly-reported gap of six reachable `raise` statements, with
no unreachable guard written to protect the number; that is the outcome the assignment
asked for when it said an honest gap beats contorted code. F1-F5 are all `note`: two
cosmetic, one a handover instruction for the tester, and two pre-existing defects that
want backlog items of their own (F4 in particular).
