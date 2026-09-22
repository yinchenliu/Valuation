---
agent: code_reviewer
assignment: P4d-cashflow-nan
round: 1
verdict: approved
---

# Review of P4d-cashflow-nan, round 1

Programmer entry: `.agent/journal/2026-09-21T0900-programmer-p4d-cashflow-nan.md`

Every measurement below is mine. I built my own probe at `c:/tmp/rev_p4d/probe.py` —
9 controls, 12 NaN cases, 4 reachability cases, **none of the programmer's inputs** —
and ran it against a `git archive eed4fe1` export at `/c/tmp/rev_p4d/full` (pytest,
lint, mypy, census) and `/c/tmp/rev_p4d/before` (the probe) and against the working
tree. Transcripts: `c:/tmp/rev_p4d/before.txt`, `c:/tmp/rev_p4d/after.txt`.

## The guard checks

Run over `analysis/dcf.py` and `analysis/fcff.py` only.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | hit at `analysis/dcf.py:143,144` — **backlog item 2, not in the diff**, answered in the entry; its red test is required to stay red by criterion 4 and is still red |
| lookup with a fallback — `.get(k, 0)` | clean |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (`grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output) |

No unanswered hit. `llm-boundary.md` does not apply: `ingestion/` is untouched.

## Check 1 — every new guard is `math.isnan`, never a comparison

`git diff -U0 | grep "^+" | grep -E "if |raise |max\(|min\("` returns exactly:

```
+    if math.isnan(value):      (analysis/dcf.py:34)
+        raise ValueError(
+    if math.isnan(value):      (analysis/fcff.py:39)
+        raise ValueError(
+    # Checked BEFORE the clamp below. …        (comment)
```

**Two added conditionals, both `math.isnan`. No comparison-based guard exists in the
diff**, and no `max`/`min` line was added or changed — the clamp at `analysis/fcff.py:74`
is a context line.

## Rule 3, by reading

| Value | Stops and names it? | Evidence (my probe) |
|---|---|---|
| `ProjectedFCFF.fcff`, any projected year, in `discount_cash_flows` | yes, names the **year** | N1/N3 (middle years 2027, 2028): before `price=nan`; after `ValueError: the projected FCFF for year 2027 is NaN…` |
| `ProjectedFCFF.fcff`, the final year | yes, names the year | N2/N4/N5 (2029, via `nopat`, `capital_expenditures`, `change_in_working_capital`): before `pv_fcffs=nan tv=nan price=nan`; after raises naming 2029 |
| a NaN arriving through `calculate_fcff_projected` | yes, at the DCF boundary, names the year | N8: before `price=nan`; after `…year 2027…` |
| `final_fcff` in `calculate_terminal_value` (direct call) | yes, names `final_fcff (the terminal value's base cash flow)` | N7: before `nan`; after raises |
| `tax_rate_override` in `calculate_fcff_historical` | yes, **before the clamp** | N9: before `tax_rate=0.0 after_tax_interest=10.0 fcff=115.0`; after raises |
| `income_statement.effective_tax_rate` (NaN `tax_expense`) | yes, names both sources | N10: same before/after as N9 |
| `wacc` in `discount_cash_flows` (direct call) | **no — returns `nan`** | N11: `nan` before **and** after. Pre-existing; the `run_dcf` chain still stops at `:137`. See F4 |
| `financials.get_balance_sheet(latest_year)` | **no — `0.0` net debt** | `analysis/dcf.py:143-144`, backlog item 2, not in the diff |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | no figure crosses a unit boundary in this diff; the added code only tests and raises |
| percentages converted at the route boundary, once | no route touched |
| falsy not treated as missing | clean — the guards test `math.isnan(value)`, not truthiness; `tax_rate_override … is not None` at `:64` is pre-existing and correct |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean — the diff adds only `import math` to `fcff.py`; `dcf.py` and `fcff.py` import `models/` and the standard library and nothing else |
| scope | only the two named files are modified (`git status --short` → `M analysis/dcf.py`, `M analysis/fcff.py`) |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | NaN in a middle year stops, naming the year | pass | my N1 (2027, `nopat`), N3 (2028, `depreciation_amortization`), N6 (direct call), N8 (via `calculate_fcff_projected`): `price=nan` before, `ValueError` naming the year after | yes |
| 2 | NaN in the final year stops, naming the year | pass | my N2, N4, N5 (2029, three different fields) and N7 (`calculate_terminal_value(nan, 0.018, 0.074)`): `nan` before, raises after | yes |
| 3 | NaN tax rate into `calculate_fcff_historical` stops, not `0.0` | pass | my N9, N10: `tax_rate=0.0 after_tax_interest=10.0 fcff=115.0` before, `ValueError` after | yes |
| 4 | no existing assertion changed meaning | `1 failed, 120 passed`, sets identical | `1 failed, 120 passed` on both trees; `diff` of the sorted `FAILED` lines → **no output**, the one entry being `tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`; `diff` of the sorted collected node lists → **no output, 121 nodes** | yes — set-diffed, not counted |
| 5 | a healthy path is byte-identical | nine controls, no `diff` output | **reproduced with my own inputs** — see below | yes |
| 6 | lint unchanged | 5, all `BLE001` | `Found 5 errors`; codes `uniq -c` → `5 BLE001` | yes |
| 7 | types not worse | set-identical at 14 | `14 → 14`; line numbers stripped, sorted, `comm -13` **empty** and `comm -23` **empty** | yes |
| 8 | census did not rise | 116 | the `rules.md` grep → **116** on both trees | yes |

### Check 2 — criterion 5, on my inputs, not the programmer's

My controls use a different company, a different WACC (`0.092` vs `0.086`), a different
terminal growth rate (`0.021`), four projection years instead of five, and a different
balance sheet. `diff` of the control block before against after → **no output**:

```
CONTROL A run_dcf 4y   pv_fcffs=373.1277213357483 tv=1791.790741893875
                       pv_tv=1255.7208466621703 ev=1628.8485679979185
                       net_debt=320.0 price=14.95826934854764
CONTROL B run_dcf 1y   price=13.33982628144439
CONTROL C discount_cash_flows healthy   373.9225610818776
CONTROL D terminal_value(157.3, 0.018, 0.074)   2859.4892857142863
CONTROL E hist, rate from filing        tax_rate=0.25 after_tax_interest=7.5  fcff=112.5
CONTROL F hist, override 0.80           tax_rate=0.5  after_tax_interest=5.0  fcff=110.0
CONTROL G hist, override -0.30          tax_rate=0.0  after_tax_interest=10.0 fcff=115.0
CONTROL H hist, override 0.33           tax_rate=0.33 after_tax_interest=6.699999999999999 fcff=111.69999999999999
CONTROL I calculate_fcff_projected      109.4
```

Nine control blocks at full `repr` precision, **not one digit moved**, on an independent
set of inputs. The only lines that differ between my two transcripts are the eleven NaN
cases that used to return a number-shaped `nan` or a fabricated `0.0`, plus the two
reachability lines. The programmer's own figure (`price=22.786835652868557`) is not
mine and does not need to be; the property asserted is the one that matters and it
holds on inputs it has never seen.

### Check 3 — the `final_fcff` placement, verified by execution

The reachability claim holds. With a NaN in the **final** year only, a stack trace taken
at the raise:

```
R2 run_dcf final-year NaN raised via <module>:208 <- run_dcf:133 <- discount_cash_flows:97 <- _require_finite:35
```

`run_dcf` stops at **line 133**, inside `discount_cash_flows`. Line 136
(`final_fcff = projected_fcffs[-1].fcff`) and line 137 are never reached, so a
`final_fcff` guard written in `run_dcf` **could not fire for any input** —
`discount_cash_flows` iterates the whole list, last element included, and reads the same
deterministic `ProjectedFCFF.fcff` property over the same stored fields. It would have
been exactly the unreachable guard the assignment forbade. The decision was right.

`calculate_terminal_value` is public (`R3: name='calculate_terminal_value'`, no leading
underscore; outside `analysis/dcf.py` itself only `tests/` calls it today, so the guard
protects a published entry point rather than a current caller) and **did** return
`nan` before this unit: `R7/N7` on the `eed4fe1` export gives
`direct terminal_value(nan,...): nan`. So the guard's home is the one place it is both
reachable and load-bearing.

### Check 4 — the clamp still clamps, and the check sits before it

Source order is `_require_finite` at `analysis/fcff.py:71-73`, the clamp at `:74` —
**before**, as `analysis/wacc.py:104` sits before `:106`. Behaviour, byte-identical
before and after:

```
CONTROL F  override  0.80  ->  tax_rate=0.5   (clamped high)
CONTROL G  override -0.30  ->  tax_rate=0.0   (clamped low)
N9         override   nan  ->  before: tax_rate=0.0 … | after: ValueError
R4         max(0.0, min(nan, 0.50)) = 0.0
```

The intended distinction holds exactly: a **known** out-of-range rate is still clamped in
both directions, an **unknown** one now stops. Had the check been placed after the clamp
it could never fire — R4 shows the NaN is already a plausible `0.0` by then.

### Check 5 — item 23b's measured cost, reproduced

On the programmer's stated shape (interest expense 10.0, filing rate 0.25), run against
the `eed4fe1` export:

```
filing rate = 0.25
23b filing rate:  tax_rate=0.25 after_tax_interest=7.5  fcff=112.5
23b NaN override: tax_rate=0.0  after_tax_interest=10.0 fcff=115.0      <- before
23b NaN override: RAISED ValueError: tax_rate (tax_rate_override or …)  <- after
```

Confirmed to the digit. The unknown rate **raised** FCFF by **2.5 in a single year**
through a full untaxed interest add-back, and `HistoricalFCFF.tax_rate` then reported
`0.0` as though it had been measured. My own control figures show the same mechanism
(`CONTROL E` vs `N9`).

### Check 6 — coverage, and whether it was gamed

Measured by me, `pytest -q --cov=analysis --cov-report=term-missing`, on the export and
on the working tree:

```
                 before                         after
analysis/dcf.py   29 stmts 2 miss  93%  33, 82   35 stmts 3 miss  91%  35, 68, 124
analysis/fcff.py  19       0      100%           24       1       96%  40
analysis/ TOTAL  226       6       97%          237       8        97%
```

Every figure in the entry reproduces. I read the shifted lines: old `:33` is the
WACC/growth NaN raise, now `:68`; old `:82` is the empty-`projected_fcffs` raise, now
`:124`. Both were already uncovered at `eed4fe1`. **Exactly two statements are newly
uncovered — `analysis/dcf.py:35` and `analysis/fcff.py:40` — and both are the `raise`
inside the new `_require_finite`.**

**Both are reachable, reached by my own probe.** Running *my* probe alone under
coverage:

```
analysis\dcf.py   35  2  94%  75, 124      <- :35 covered, and :68 too (my NaN-WACC case)
analysis\fcff.py  24  0 100%               <- :40 covered
```

I also re-ran the entry's own command against the programmer's probe and got
`dcf.py 35 3 91% 68, 75, 124` / `fcff.py 24 0 100%` — the same conclusion. No guard was
written that no input can reach, and nothing was restructured to hold a percentage; the
percentage was allowed to fall and was reported with the lines.

### The gates as sets

| Gate | Before (`eed4fe1` export) | After | How compared |
|---|---|---|---|
| `pytest -q` | `1 failed, 120 passed` | `1 failed, 120 passed` | — |
| failure set | `{tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent}` | identical | `diff` of sorted `FAILED` lines → no output |
| collected node set | 121 | 121 | `diff` of sorted node ids → no output |
| `ruff check .` | 5, `5 BLE001` | 5, `5 BLE001` | `uniq -c` on the codes |
| mypy (the scoped gate) | 14 in 4 files | 14 in 4 files | `comm -13` empty, `comm -23` empty |
| census | 116 | 116 | the `rules.md` grep |
| `GET /` | — | **200** | `TestClient(app.app, raise_server_exceptions=False)` |

## Findings

### F1 — `_require_finite` tests NaN only, so its name over-promises, now in three files · `note`

**Evidence:** `analysis/dcf.py:34` and `analysis/fcff.py:39` are both
`if math.isnan(value):` under a helper named `_require_finite`;
`math.isnan(float('inf'))` is `False`.
**Rule or document:** none. This is my own F1 from `P4c-nan-stops` carried into two more
files; I checked reachability of `inf` again and this repository's arithmetic on these
paths produces NaN, not `inf` (`ProjectedFCFF.fcff` is a sum of stored fields;
`effective_tax_rate` guards its divisor at `models/financial_statements.py:101`).
**What would fix it:** rename to `_require_not_nan`, or widen the body to
`math.isfinite`, in a unit that owns all three files at once. Not this one's.

### F2 — three of the missing-line numbers in the entry's probe-coverage paste are off by one · `note`

**Evidence:** the entry pastes `analysis\dcf.py 35 3 91% 67, 74, 123`; re-running the
entry's own command against the programmer's own probe gives
`analysis\dcf.py 35 3 91% 68, 75, 124`. The three cited numbers are the `if` lines, not
the `raise` lines.
**Rule or document:** none — the substantive claim (`:35` and `:40` both reached, the
three remaining misses all pre-existing) is true and I verified it independently.
**What would fix it:** correct the three numbers in the entry; nothing in the code.

### F3 — `_require_finite` now exists in three `analysis/` modules in near-identical form · `note`

**Evidence:** `analysis/wacc.py:23`, `analysis/dcf.py:17`, `analysis/fcff.py:28`.
**Rule or document:** none — it is not a registry, not a dispatch table and not a
data-keyed lookup, so rule 3 is not engaged; the programmer disclosed the choice and
argued it in its decisions table (the raised message differs in each home, and the
docstrings cross-reference `analysis/wacc.py:_require_finite`). I accept the reason.
**What would fix it:** if a fourth copy is ever wanted, promote one shared primitive
that takes the message tail as an argument — an orchestrator decision, not a
requirement now.

## Not charged to this unit — the three the programmer reported, and whether each wants a backlog item

| # | Item | Verified | Needs its own backlog item? |
|---|---|---|---|
| 1 | `discount_cash_flows`' `wacc` is unguarded on a **direct** call | yes — my N11, `discount_cash_flows(healthy, nan)` → `nan`, **before and after**; through `run_dcf` the chain still stops, my N12 raises at `dcf.py:137` | **yes.** One line, same shape as this unit's guards. Latent today only because two lines later something else raises — that is a coincidence of call order, not a defence |
| 2 | `calculate_fcff_projected` has seven unguarded float parameters | yes — my N8 passes `operating_margin=nan` and the stop lands one module later, in `discount_cash_flows`, naming *year 2027* rather than the bad assumption | **fold into item 23**, which already owns "`analysis/fcff.py` holds no `raise` at all". A new number would split one file's story in two |
| 3 | `models/valuation.py:138` renders a share price of `0.0` on zero diluted shares | yes — `self.equity_value / self.diluted_shares if self.diluted_shares else 0.0`; it is inside the 116 and the backlog names it only in passing, at `refactor-backlog.md:866`, as part of item 20's trace | **yes, its own item.** Item 1 is a bulk census nobody will act on line by line, and this is the **last** line before the headline figure — the same argument that earned item 2 its own number |

**On the first of these, transparently:** this unit did rewrite the line that consumes
`wacc` (`pv += fcff.fcff / (1 + wacc) ** i` → `pv += cash_flow / (1 + wacc) ** i`), so
"moving a line makes it yours" is arguable. I am not charging it, for two reasons that
both need to hold: the `wacc` parameter and its handling are textually unchanged, and
the assignment scoped the unit to "guard each projected **cash flow**" — widening that
scope unasked would itself have been a finding. The orchestrator should close it in a
named unit rather than leave it to the next person who edits the function.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 2 — missing balance sheet → zero net debt | `analysis/dcf.py:143-144` | no. Not in the diff; its red test is still red, for the same reason |
| 1 — the 116 zero-default sites | repository-wide | no; census still 116 |
| 23's other half — `analysis/fcff.py` holds no `raise` for wholly empty statements | `analysis/fcff.py` | no. Explicitly out of scope by assignment step 5 |
| 9 — unlabelled `DEFAULT_COST_OF_DEBT` | `analysis/wacc.py` | no; not in scope |
| 17 — `analysis/` imports `ingestion/` | `analysis/capm.py:16` | no |

I saw each of these and each is already on the record. Item 23's other half and item 2
were both named in the programmer's entry as deliberately untouched, and the diff
confirms it.

## For the orchestrator, not a finding

- **Items 30 and 23b are closed by this diff** and both are still listed as open in
  `docs/9-reference/refactor-backlog.md`; `STATUS.md:304` still ranks item 30 as the
  highest open defect. Neither the programmer nor I may edit those files.
- **Line-number drift.** `docs/2-rules/rules.md:71` and `refactor-backlog.md:134` cite
  `analysis/dcf.py:80` for item 2; that code now sits at `:143-144` after this diff (it
  was already `:101` before it). The citation was stale before this unit and is staler
  now. Worth one pass over the doc line references when the backlog is next edited.
- **The tester needs at least four cases**, as the programmer says: statement coverage
  cannot distinguish the two `dcf.py` call sites once `:35` is green. One middle-year
  NaN asserting the **year** appears in the message, one final-year NaN, one direct
  `calculate_terminal_value(nan, …)`, and one NaN tax rate asserting it **raises rather
  than returning `tax_rate=0.0`**. A test that only asserted `tax_rate <= 0.50` would
  have passed against the defect.

## Earlier findings — re-reviews only

Round 1 for this unit. For continuity with my `P4c-nan-stops` review: its **F4** (a NaN
in one `ProjectedFCFF` reaches the share price) is **fixed** here, confirmed by my N1-N8;
its **F5** (the `analysis/fcff.py:44` clamp twin) is **fixed** here, confirmed by my N9,
N10 and the 23b reproduction; its **F1** (the helper's name) is **not_fixed** and
recurs above as F1, still a `note`.

## Verdict

`approved`

The unit does what it was asked and proves it on inputs it has not seen. Both added
guards are `math.isnan` and there is no comparison-based guard in the diff. Nine healthy
control blocks are byte-identical to the last digit on my own company, my own WACC and
my own four-year projection, while all eleven NaN cases that previously returned
`price=nan` or a fabricated `tax_rate=0.0` now raise and name the year or the field. The
`final_fcff` placement is correct and I verified the reachability argument by stack
trace: `run_dcf` stops at `:133` inside `discount_cash_flows`, so the alternative would
have been an unreachable guard. The clamp still clamps `0.80 → 0.50` and `-0.30 → 0.0`,
and the check sits before it, where the evidence still exists. Item 23b's cost
reproduces exactly — the unknown rate raised FCFF by 2.5 in one year and reported
`tax_rate=0.0` as a measurement. Coverage fell by exactly two statements, both new
`raise` lines, both reached by my probe, with nothing restructured to protect a
percentage. Failure set, collection set and mypy set are `diff`/`comm`-identical, lint
is 5/5 `BLE001`, the census is 116, and `GET /` is 200. F1-F3 are all `note`: no rule is
cited against any line in this diff.
