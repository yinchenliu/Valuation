---
agent: code_reviewer
assignment: P6-honest-output (round 2) + P6b-wacc-fixture (round 1)
round: 2
verdict: approved
---

# Review of P6-honest-output round 2 and P6b-wacc-fixture

> Opened before the first command of the re-run, filled as each result landed. An
> earlier session was stopped mid-run and left no entry; everything below is re-measured
> in this session, not carried over.

Programmer entry: `.agent/journal/2026-09-22T1600-programmer-p6-honest-output-r2.md`
Tester entry: `.agent/journal/2026-09-22T1700-tester-p6b-wacc-fixture.md`
My round-1 review: `.agent/journal/2026-09-22T1500-code_reviewer-p6-honest-output.md`

Baseline for every comparison is `d2ba1e5` (= `git HEAD`). `docs/9-reference/refactor-backlog.md`
is modified in the tree and is the orchestrator's item 36; it is not attributed to either
unit and is not reviewed here.

---

## Check 1 — the accounting. The tester's answer holds, and the binary was wrong

Both halves verified against the dataclass, not against the entry.

| Claim | Verified |
|---|---|
| `total_debt` is exactly three fields and nothing else | `models/financial_statements.py:187-188` — `return self.short_term_debt + self.current_portion_lt_debt + self.long_term_debt` |
| `BalanceSheet` has **no** lease-liability field | `grep -in "lease" models/financial_statements.py` → **exit 1, no output.** The full field list at `:118-183` is cash, STI, AR, inventory, other current assets, PPE, goodwill, intangibles, other non-current assets, AP, short-term debt, current portion, accrued, other current liabilities, LTD, other non-current liabilities, total equity |
| `interest_expense` is a flow, `total_debt` a year-end stock | `IncomeStatement.interest_expense` at `:84`; `BalanceSheet` is a "Single-period balance sheet" at `:116` with a single `year` |

So finance-lease interest under ASC 842, securitisation interest and interest on
uncertain tax positions **cannot reach `total_debt` in this schema by construction** —
there is no field for them to land in. And a company that repaid its borrowings before
the balance sheet date reports a full year of interest beside a zero year-end balance.
Both halves of the tester's claim are true.

**Therefore: yes, a filing can report $20M of interest and $0 of total debt.** The
binary in `P6b-wacc-fixture` was wrong, and the tester was right to refuse both horns.
The pattern is **ambiguous**, not impossible.

One thing neither entry noticed, and it matters to the unit that fixes the message:
**the schema already carries the evidence that would disambiguate.**
`CashFlowStatement.debt_repaid` and `.debt_issued` exist at
`models/financial_statements.py:243-244`. A company that genuinely deleveraged shows a
large `debt_repaid` in the same year; a balance sheet that failed to extract shows
nothing. `cost_of_debt_with_source` is not given the cash flow statement, so it cannot
consult it today — but that is a reason to widen a signature later, not to guess now.

## Check 2 — "behaviour right, diagnosis wrong" is the correct reading. The stop stays

I confirm the tester's reading and I am not overturning it.

- **The stop stays.** `total_value` is not the issue; the two readings of
  `total_debt == 0, interest != 0` imply *different WACCs* — one where the debt term is
  legitimately absent, one where it was silently dropped and the share price is
  understated by the whole debt balance. Rule 3 is "stop, never guess", and picking
  either reading is a guess. The old `if total_debt == 0: return 0.0` picked one
  silently; that is backlog item 22. Removing the stop would reopen it.
- **The escape hatch is real and I exercised it.** `cost_of_debt_with_source` returns on
  `override is not None` at `analysis/wacc.py:83-88`, *before* the check, so a caller who
  knows they deleveraged can pass `--cost-of-debt` on the CLI or
  `cost_of_debt_override` on the web and the run proceeds. A stop with no way past it
  would have been a different judgement.
- **The message is wrong and that is F3 below.** It states an inference as a fact.

The tester was also right not to pin the wording: `strategy.md` §2 and its own step 4
forbid it, and no test it wrote turns red when the sentence is corrected — I checked, see
F3.

## Check 3 — the fixture repair is legitimate. Verified against `HEAD`, not against the entry

The decisive question is whether the titles and the docstring pre-existed, or were
written to justify the repair. They pre-existed:

```
$ git show HEAD:tests/unit/test_wacc.py | grep -n "No financial debt at all\|def test_wacc_with_no_debt\|def test_a_debt_free_company\|def test_cost_of_equity_survives"
 91:    """No financial debt at all. Payables are still there, and must not count."""
212: def test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt() -> None:
240: def test_a_debt_free_company_prices_at_its_cost_of_equity() -> None:
349: def test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt() -> None:
```

All four strings are quoted in the tester's entry exactly as they stand at `d2ba1e5`.
The fixture contradicted its **own** stated subject before either unit touched it.

**And no expectation moved.** Every removed line in `tests/` across the whole diff:

```
$ git diff -U0 -- tests/ | grep "^-" | grep -v "^---" | grep -E "assert|approx|pytest\.raises"
-    The identity holds for any Rd, which is why this test asserts the WACC and
```

One docstring line. **Zero assertions removed or altered**, and
`grep -rn "xfail\|skip"` over the four test files is empty. The repair is an input
change at three call sites, which is what the assignment permitted.

This is not tuning a test to fit code.

## Check 4 — the discrimination check, reproduced

`c:/tmp/p6rev2/discrim.py`, fixtures rebuilt by hand from `tests/unit/test_wacc.py:84-120`,
each repaired test given its debt back (`_balance_sheet_with_debt()` and the fixture's
original 20 of interest; beta 2.0 for the third, which has no debt to restore):

```
=== T1 test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt ===
  repaired: eq_w=1.0 debt_w=0.0 wacc=0.1
  debt back: eq_w=0.714286 debt_w=0.285714 wacc=0.225714
  A1 eq_w==1.0 fails?  True     A2 debt_w==0.0 fails?  True
  A3 wacc==COST_OF_EQUITY fails?  True     A4 wacc==0.10 fails?  True
=== T2 test_a_debt_free_company_prices_at_its_cost_of_equity ===
  repaired: debt_w=0.0 wacc=0.1 cod=0.0 tax=0.234375
  debt back: debt_w=0.285714 wacc=0.082143
  A1 debt_w==0.0 fails?  True     A2 wacc==0.10 fails?  True
=== T3 test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt ===
  repaired: coe=0.1 eq_w=1.0 debt_w=0.0
  beta 2.0: coe=0.140000
  A1 coe==0.10 fails?  True
```

**All 7 pre-existing assertions fail when the debt is restored.** The tester's three
headline figures reproduce to the digit: `0.10 → 0.082143`, weight `0.0 → 0.285714`,
`Re 0.10 → 0.14`. No assertion went vacuous. The repair is clean.

The fixture's derived tax rate does move, 75/300 = 0.25 → 75/320 = 0.234375, and I
confirmed it reaches no assertion: T1 and T3 supply `tax_rate_override` or never reach
the weighting, and T2 asserts an identity in which `t` is multiplied by a zero debt
weight. `cod=0.0 tax=0.234375` in the run above is the proof that both are live values
that no assertion reads.

## Check 5 — round 2's own fixes, exercised

**F1 — fixed.** `c:/tmp/p6rev2/http_probe.py`, real `TestClient` over `app.app`, the
three extraction/price boundaries faked, no network, no key, no PDF:

```
GET /assumptions -> 200
  field: <input type="number" id="risk_free_rate" name="risk_free_rate"
         placeholder="blank = assume 4.0% (config.DEFAULT_RISK_FREE_RATE)" step="0.1">
  value="4.0" on page? False

POST /valuation, risk_free_rate BLANK (field omitted entirely) -> 200, 10132 bytes
  Risk-Free Rate          | 4.00%
  Risk-Free Rate — source | ASSUMPTION — config.DEFAULT_RISK_FREE_RATE. No rate was supplied…
  ASSUMPTION present? True        'supplied by the caller' present? False

POST /valuation, risk_free_rate = "4.0" -> 200, 10084 bytes
  Risk-Free Rate — source | supplied by the caller (--risk-free-rate / …)
  ASSUMPTION present? False       'supplied by the caller' present? True
```

**Both branches exercised over HTTP, and they are opposites.** Criterion 4 is met on the
web for the first time.

I also exercised the falsy case the reviewer contract names explicitly, because the fix
introduces a new conversion at the route boundary:

```
POST /valuation, risk_free_rate = "0"  ->  Risk-Free Rate | 0.00%
                                           source | supplied by the caller (…)
```

A deliberate `0` is **not** read as missing. `.strip()` on the string is the right
shape; `if risk_free_rate` on a float would have been backlog item 6's defect, five
instances of which sit in the lines immediately above and which the unit correctly left
alone.

`grep -n "Form(4.0)" api/routes_valuation.py` → exit 1, no output. `grep -n 'value="4.0"'
templates/assumptions.html` → exit 1, no output. Criterion 4b met.

**Round-1 work not re-opened.** File mtimes, against the round-1 review written at 15:05:

```
2026-09-22 14:00:01  analysis/capm.py
2026-09-22 14:04:37  templates/valuation_result.html
2026-09-22 14:08:59  cli.py            <- all three predate the round-1 review
2026-09-22 15:09:38  analysis/wacc.py
2026-09-22 15:11:46  config.py
2026-09-22 15:12:01  models/valuation.py
2026-09-22 15:13:50  api/routes_valuation.py
2026-09-22 15:13:59  templates/assumptions.html
2026-09-22 15:50–15:52  the four tests/unit/ files  (the tester)
```

The three round-1 files were not touched after I reviewed them, and the tester touched
nothing outside `tests/unit/`.

**F6 — fixed, and I re-derived all six figures in the table**, not only the one I
reported:

```
$ .venv/Scripts/python.exe -c "import math; ..."
R2=0.30 SE/beta=0.2006 -> 0.201  95% +/- 39.3%
R2=0.20 SE/beta=0.2626 -> 0.263  95% +/- 51.5%
R2=0.10 SE/beta=0.3939 -> 0.394  95% +/- 77.2%
```

`config.py` now reads `0.201 / 39%`, `0.263 / 52%`, `0.394 / 77%`. All six correct.

## Check 6 — the gates, as sets

| Gate | Claimed | I measured | Agree? |
|---|---|---|---|
| Suite | `1 failed, 145 passed`, failure `test_dcf_rule3_red.py` | **`1 failed, 145 passed`**; sole failure `tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` | yes |
| Failure **set**, before | `{rule3_red, wacc::debt_free_company, wacc::no_market_cap_and_no_debt}` | re-measured by running `git archive HEAD tests` against the current `analysis/` → **exactly that set, `3 failed, 118 passed`** | yes |
| `analysis/` coverage, after | 255/255 stmts, 80/80 branches | **255/255, 80/80, 0 missed, 0 partial** | yes |
| `analysis/` coverage, before | 244/255, 8 uncovered raises | re-measured with the `HEAD` tests: **244/255, 11 missed** — `capm.py 65,73,87,136`, `dcf.py 35,68,124`, `fcff.py 40`, `wacc.py 41,129,216`. The 8 raises are `capm 65/73/87`, `dcf 35/68/124`, `fcff 40`, `wacc 41` → **8 → 0** | yes |
| Lint, repo | 5 `BLE001` | **`Found 5 errors`**, the same five files | yes |
| Lint, `tests/` | 1 | **`Found 1 error`**, `tests/test_e2e_all_googl.py:106` | yes |
| Types | 14, set-diffed | `comm` on the two sorted, line-number-stripped error lists (`c:/tmp/p6rev2/{base,head}_e.txt`): **only-in-base empty, only-in-head empty, in-both 14.** Identical sets | yes |
| Census | 116 | **116** | yes |
| `GET /` | 200 | **200** | yes |

The coverage "before" figure is not the tester's word: I exported `HEAD`'s `tests/` to
`c:/tmp/p6rev2/basetests` and ran it against the current `analysis/`, which reproduced
both the 3-failure set and the 11 missed statements in one command.

## The guard checks

Over the round-2 files in scope (`analysis/wacc.py`, `api/routes_valuation.py`,
`config.py`, `models/valuation.py`, `templates/assumptions.html`) and the four
`tests/unit/` files.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | 3 hits, **none added**: `models/valuation.py:147,151,216` — context, backlog item 1 |
| lookup with a fallback | 1 real hit, `api/routes_valuation.py:237` (`info.get("sharesOutstanding", 0)`) — context, items 1/5. The other grep hit is `@router.get("/assumptions", …)`, a decorator |
| bare or-default | 5 hits, `templates/assumptions.html:51,57,67,72,77` — all **pre-existing** jinja `or ''` on display strings, unchanged by the diff |
| money field `: float = 0.0` | 10 hits in `models/valuation.py`, **none added**; the round's only change to that file is comments |
| `**kwargs` | clean |
| `getattr(` | clean |
| dict of functions keyed by data | clean. The new `Final[str]` provenance constants are printed verbatim; nothing indexes behaviour by them |
| model client outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output |

Census over **added lines only**, across the entire uncommitted diff including `tests/`:

```
$ git diff -U0 -- cli.py config.py analysis/ models/ templates/ api/ tests/ | grep "^+" \
    | grep -E "if [^)]+ else 0(\.0)?\b|\bor +(0|0\.0|'')\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0|\*\*kwargs|getattr\("
exit=1        (no output)
```

**No new default of any of the five forms was added by either unit.**

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `total_debt == 0` with `interest != 0` | **yes** — `ValueError` naming both figures, both years and the three balance-sheet fields | `analysis/wacc.py:112-126`; locked by 3 tests |
| `total_debt == 0` with `interest == 0` | no — returns `0.0`, labelled | a **measurement** of a debt-free company, and the amendment requires it to keep working. Accepted |
| `cost_of_debt` override | no — returns the caller's number, labelled "not derived from the filing" | rule 6. Accepted |
| `risk_free_rate` form field, blank | no — substitutes `config.DEFAULT_RISK_FREE_RATE`, now labelled on **both** outputs | rule 6 by design; step 2 forbids the rule 5 half |
| `risk_free_rate` form field, `"0"` | no — 0.0% and labelled "supplied" | correct: falsy is not missing. Exercised over HTTP above |
| `risk_free_rate` form field, garbage | `float()` raises into the route's blanket handler | unchanged; item 8 |
| the five NaN guards in `calculate_wacc` | **yes**, each names its own field | `analysis/wacc.py:40-45`; 5 tests |
| **`market_cap + total_debt == 0`** | **NO — returns `equity_weight=1.0, debt_weight=0.0`** | `analysis/wacc.py:215-223`. **F4** |
| `--cost-of-debt` supplied with a zero debt balance | **NO — zero debt weight, the supplied rate vanishes** | `analysis/wacc.py:83-88` then `:230`. Item 22's other half, programmer finding 1, tester finding 2. **F5** |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean. The round adds no arithmetic on statement figures; the labels print `total_debt:,.0f` / `interest:,.0f` in the units the fields carry |
| percentages converted at the route boundary, once | clean, and improved. The new `default_risk_free_rate_display` is `f"{config.DEFAULT_RISK_FREE_RATE * 100:.1f}"` **in the route** (`api/routes_valuation.py:133`); the template only interpolates. The inbound conversion `float(risk_free_rate) / 100` is at `:208`, the same boundary as its four siblings. No double conversion: the page renders `4.00%` from `0.04` |
| falsy not treated as missing | **clean in the diff, and the new site does it right.** `risk_free_rate.strip()`, not `if risk_free_rate`. `"0"` → 0.00%, verified over HTTP. The five `x / 100 if x else None` at `:198-202` are item 6 and untouched |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | `analysis/wacc.py` clean (`config`, `models`, `math`). `analysis/capm.py:16` imports `ingestion.price_fetcher` — **pre-existing item 17**, a context line, not re-opened this round (mtime 14:00) |
| `models/` imports only stdlib / other `models/` | clean — `dataclasses`, `typing.Final` |

## Findings

### F3 — `analysis/wacc.py:113-126` states an inference as a fact, and tells a legitimately deleveraged filer their extraction failed · `minor`

**Evidence:** `analysis/wacc.py:117-122` — *"A company that pays interest has debt, so
the debt balance (BalanceSheet.short_term_debt + … + BalanceSheet.long_term_debt, year
2025) **did not extract**."* Check 1 above shows two ordinary filings that produce the
pair with nothing mis-extracted.

**Rule or document:** none — and I have checked that carefully, because the severity
floor turns on it. The run **stops** and **names both figures and all three fields**, so
rule 3 is satisfied. No displayed figure is affected, so rule 4 and rule 6 are not
engaged. The defect is that a true statement about the *code's inability to resolve the
input* is written as a false statement about the *filing*. That is a stale/incorrect
message, which `severity.md` ranks as `minor` — "correct today, fragile tomorrow" — not
a rule break, and I am not widening a rule to reach it.

**Direction it errs:** stopping, not silent. The run refuses rather than lying about a
number. That is why it is not worse than `minor`.

**What would fix it:** name both readings in the sentence — "either the balance sheet
did not extract, or the company repaid its borrowings before the balance sheet date" —
and keep the `--cost-of-debt` remedy that is already there. **I confirmed no test turns
red by writing the rewrite and running it**, not by reading the assertions: in a copy of
the tree at `c:/tmp/p6rev2/wt`, `analysis/wacc.py:113-126` replaced with a message naming
both readings →

```
$ .venv/Scripts/python.exe -m pytest -q tests/unit/test_wacc.py
23 passed in 0.08s
```

The tester genuinely pinned no wording. A later unit could
also consult `CashFlowStatement.debt_repaid` (`models/financial_statements.py:243-244`)
to tell the two readings apart, but that widens a signature and is not message-only.

**This is the tester's finding 1 and I endorse it in full.** It needs a backlog item.

### F4 — `analysis/wacc.py:215-223` returns fabricated weights when both inputs are zero, and it is on no backlog item · `minor`

**Evidence:**

```
$ grep -n "total_value\|equity_weight\|all-equity" docs/9-reference/refactor-backlog.md
(no output)
$ git show HEAD:analysis/wacc.py | sed -n '114,121p'
    if total_value == 0:
        return WACCResult(… equity_weight=1.0, debt_weight=0.0,)
```

`total_value == 0` requires `market_cap == 0`, which requires a price of 0 or a share
count of 0 — there is no listed company for which it is a measurement. The branch is
reachable **only** with a missing input, and it answers with weights that assert "100%
equity financed". A zero that means "we do not know" and a zero that means "zero", again.

**Rule or document:** this site is a rule-3 shape, and it **predates both units** — so it
is reported here, not charged to them. The reasoning, stated openly because it is the one
judgement call in this review:

`if total_value == 0:`, `equity_weight=1.0` and `debt_weight=0.0` are all **context lines
in the diff**, byte-identical to `d2ba1e5` as the `git show` above proves. What the unit
did inside that block, in round 1, is append one unrelated keyword argument,
`+ cost_of_debt_source=cost_of_debt_source,`, after `debt_weight=0.0,`. Compare round-1
**F2**, which I *did* charge: there the defective expression itself was rewritten
(`- return 0.0` → `+ return 0.0, (`), so the fabricated zero passed through the
programmer's hands and came out of them. Here it did not — the values were never in a
changed line, and the appended argument was unavoidable, since `WACCResult` cannot carry
the label the assignment required unless both construction sites pass it. `severity.md`
says "moving a line makes it yours"; this line was not moved, it shifted position because
text above it grew, which is the same situation as `analysis/capm.py:16` that I recorded
rather than charged in round 1.

**So: `minor`, and it does not block.** Read the touch test at statement granularity
rather than line granularity and it becomes `major` and this review becomes
`changes_requested` — that reading is available to the orchestrator and I am naming it
rather than burying it.

**Direction it errs:** silent. It produces a WACC equal to the cost of equity on missing
inputs and the run continues to a rendered share price.

**What would fix it:** raise, naming `market_cap`, beside the existing
`_require_finite(equity_value, "market_cap")` at `:210`. **It needs a backlog item — it
is on none** (grep above), and this is the tester's finding 3, which I confirm.

**And the next unit must know this, because the tester's entry does not quite say it.**
The tester writes that "no test asserts those weights", which is true, but
`test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`
(`tests/unit/test_wacc.py:~390`) calls `calculate_wacc(..., market_cap=0.0)` and reads
`result.cost_of_equity`, so it requires the call **to return rather than raise**.
**Measured, not reasoned** — the fix inserted into a copy of the tree at
`c:/tmp/p6rev2/wt`:

```
$ .venv/Scripts/python.exe -m pytest -q tests/unit      # with the market_cap==0 raise
FAILED tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent
FAILED tests/unit/test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt
2 failed, 144 passed
```

**Exactly one test beyond the deliberate red.** The pinning is pre-existing — the test
exists verbatim at `d2ba1e5:tests/unit/test_wacc.py:349` — not something the tester
introduced, and the test's own docstring says it asserts only the pass-through. But "no
test pins it" is too strong: the assignment that closes F4 must budget for that one test,
and its repair is to move the `market_cap=0` case into a `pytest.raises` rather than to
delete the assertion.

### F5 — item 22's other half: a supplied cost of debt with a zero debt balance is multiplied by a zero weight and vanishes · `minor`, and it is now unblocked

**Evidence:** `analysis/wacc.py:83-88` returns on `override is not None` before either
statement is read; `:211` then takes `debt_value = balance_sheet.total_debt` = 0 and
`:230` weights the caller's rate at `0/V`.

**Rule or document:** a rule-3 shape, and backlog item 22's own text — which reaches only
the *rate*, not the weights. **Why it is `minor` and not charged as a rule break against
this unit:** the round-2 amendment defines item 22 entirely in terms of the cost of debt,
so the weights were outside the commissioned work; the values that are actually fabricated
live at `:211` and `:230`, both **unmodified context lines**; and the programmer named the
hole as its own finding 1 rather than banking it, with a placement argument I accept on
merit — a branch that reads neither statement is the wrong place for a balance-sheet
validity check. `severity.md`'s "the fix belongs to a future unit" bar applies to
downgrading a *rule break in the diff*; this is a different defect at a different site,
and the correct instrument for it is a backlog item, which is what I am asking for.

**Verified for the orchestrator's third question — the next unit is safe to dispatch,
and I measured it rather than reasoning about it.** In a copy of the tree at
`c:/tmp/p6rev2/wt` I inserted the guard the programmer proposed, at the line it proposed:

```python
    debt_value = balance_sheet.total_debt
    _require_finite(debt_value, "balance_sheet.total_debt")
    if debt_value == 0 and abs(income_statement.interest_expense) != 0:
        raise ValueError(...)
```
```
$ .venv/Scripts/python.exe -m pytest -q tests/unit
FAILED tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent
1 failed, 145 passed
```

**Zero tests block it.** The sole failure is the deliberate red. The pairing that used to
block it is gone: `tests/unit/test_wacc.py:249-263`,
`test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt`, now passes
`_income_statement(interest_expense=0.0)`, so the guard does not fire on it. And no test
written this round pins the current behaviour — the only test asserting a zero debt weight
beside an override is that same one, where for a genuinely debt-free company
`debt_weight = 0/1000 = 0` is the correct measurement; my discrimination run above shows
that assertion moving to 0.285714 and failing the moment real debt exists.

**One caveat, same as F4:** if the weights guard is placed so that it *also* fires on
`market_cap == 0`, `test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`
goes red — I measured both guards together and got `2 failed, 144 passed`. Keep the two
guards separate and the F5 half costs nothing.

**What would fix it:** a `total_debt == 0 and interest != 0` guard in `calculate_wacc`
beside `_require_finite(debt_value, …)`. **Needs a backlog item** — item 22's text does
not cover the weights.

### F6 — the tester widened step 5 to cover `analysis/capm.py:136`, and it was good sense, not scope creep · `note`

**Evidence:** `analysis/capm.py` is named in `P6b-wacc-fixture`'s **Files in scope** for
step 5; `:136` is the "NOT RELIABLE" beta label, not a `raise`. Before the tester it was
the last uncovered statement in that file (my coverage run: `capm.py … Missing 65, 73,
87, 136`).

**Rule or document:** none. Step 5's stated object is "close the coverage gap **this unit
and its predecessors opened**". `capm.py:136` is a statement `P6-honest-output` round 1
opened, in a file the assignment lists. Covering it is inside the step's purpose even
though it is outside the literal word "raise".

**Why it is right and not creep:** the two tests it added assert only that the two sides
of `config.MINIMUM_BETA_R_SQUARED` are told apart, and that the reliability label and the
source label differ. They pin no wording and no number, so they cannot go red on a
reformat — and `>=` at the boundary is the comparison most likely to be inverted by a
later edit. The tester flagged the widening in its own entry rather than burying it,
which is the behaviour the contract asks for. **No finding.**

## Earlier findings — round 1 outcomes

| # | Outcome | Note |
|---|---|---|
| **F1** | **fixed** | `Form(4.0)` and `value="4.0"` both gone (grep, exit 1). A real `POST /valuation` with the field blank renders `ASSUMPTION — config.DEFAULT_RISK_FREE_RATE` and **not** "supplied by the caller"; with `4.0` typed it renders the opposite. Both exercised over `TestClient` this session. The placeholder reads the constant from `config` through the route context, so the literal is not rebuilt in the template. `"0"` is correctly read as a supplied 0.00% |
| **F2** | **fixed** | Item 22 is closed as the amendment specified: `interest != 0` raises naming both figures, both years and the three fields (`analysis/wacc.py:112-126`); `interest == 0` returns `0.0` with a label that says it is a measurement (`:129-135`). Both branches are now covered by tests and the suite is `1 failed, 145 passed` |
| **F6** | **fixed** | `config.py` reads `SE/beta = 0.394`; I recomputed all three ratios and all three interval widths and all six are now exact |
| F3 | not_fixed | `cli.py`, out of round 2's stated scope. Real, `minor`, needs an assignment |
| F4 | not_fixed | same |
| F5 | not_fixed | same — and it is the one most likely to bite a future tester |
| F7 | not_fixed | same, `note` |
| F8 | withdrawn as a finding | it became **backlog item 36**, written by the orchestrator. Not attributed to either unit and not reviewed here |

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched? |
|---|---|---|
| 1 | the 116 zero-default sites | no — census **116** on both sides |
| 2 | `analysis/dcf.py:80`; `test_dcf_rule3_red.py` stays red | no — it is the sole remaining failure |
| 5 | `api/routes_valuation.py:31` module-global `_extraction_cache` | no |
| 6 | `api/routes_valuation.py:198-202`, falsy read as missing, five times | no — the new sixth conversion at `:208` deliberately does **not** copy them |
| 8 | the blanket `except Exception` | no — lint still 5 `BLE001`, same five sites |
| 17 | `analysis/capm.py:16` imports `ingestion.price_fetcher` | no — mtime 14:00, before the round-1 review. Seen and recorded, as asked |
| 26, 29, 31, 32, 36 | as recorded | no |

I saw each of these and each is already on the backlog.

## Scratch, all outside the repository

`c:/tmp/p6rev2/discrim.py` (the discrimination reproduction), `c:/tmp/p6rev2/http_probe.py`
(the two-branch HTTP probe), `c:/tmp/p6rev2/basetests/` (`HEAD`'s `tests/`, for the
before-coverage and before-failure-set), `c:/tmp/p6rev2/base/` (`HEAD` export, for the
mypy set-diff), `c:/tmp/p6rev2/wt/` (a copy of the working tree in which I inserted the
F3, F4 and F5 fixes to measure what each would cost), `c:/tmp/p6rev2/{base,head}_e.txt`,
`c:/tmp/.cov_rev`, `c:/tmp/.cov_base`. **Nothing was copied into the repository, no
extraction was run, no network call was made, and I wrote no file in this repository
except this entry.**

## Verdict

`approved`

**Both units did their work and I want to be precise about what is and is not blocking.**
P6-honest-output round 2 closed all three findings it was given, and I verified each by
execution rather than by reading: the web path now reaches the substitution branch and the
supplied branch on a real `POST /valuation`, a deliberate `0` survives as 0.00%, the
literal `4.0` is gone from both the route and the template, item 22's two cases are drawn
apart, and the `0.394` correction holds along with the other five figures in that table.
P6b's ruling is right on the accounting — I re-derived both halves from the dataclass, and
`grep -in "lease" models/financial_statements.py` returning nothing is the crux: the
pattern is producible, so the binary was wrong and refusing both horns was correct. The
fixture repair is legitimate, proved by the strongest evidence in either entry: all seven
pre-existing assertions fail again when the debt is restored, which I reproduced to the
digit. Every gate re-measured as sets, not counts — the failure set is the single
deliberate red, the type errors are identical modulo line numbers, coverage went 244/255
to 255/255 with the eight raises going 8 → 0, and I measured the "before" myself by running
`HEAD`'s tests against the current `analysis/`.

**No `blocker` and no `major` stands, so I approve.** F3, F4 and F5 are all `minor`, and
the reason none of them is `major` is written out in each rather than asserted: F3 stops
the run and names every field, so it breaks no rule — it is a false sentence, not a wrong
number; F4's fabricated weights sit in lines that are **byte-identical context** in the
diff; F5's fabricated weight sits at `:211` and `:230`, also untouched, and the round-2
amendment scoped item 22 to the rate. I considered charging F4 as `major` on my own
round-1 F2 precedent and decided against it on a stated distinction — in F2 the zero was
in a rewritten line, here it never was. **That is the one judgement call in this review
and I have flagged it in F4 so it can be overturned without another round.** If the
orchestrator reads "moving a line makes it yours" at statement rather than line
granularity, F4 is `major` and this becomes `changes_requested`; nothing else would move.

**What must happen next, and none of it is a revision of these two units.** Three backlog
items: F3 (the over-claiming message, message-only, costs nothing — 23/23 wacc tests stay
green with the rewrite in place), F4 (`market_cap == 0` fabricates weights, on no item at
all, and the one pre-existing test at `tests/unit/test_wacc.py:~390` must move into a
`pytest.raises` with it), and F5 (item 22's weights half, which item 22's text does not
reach). **F5 is now fully unblocked and should be dispatched: I inserted the guard and
measured `1 failed, 145 passed` — zero tests block it.** That was the specific question
asked, and the answer is that the tester's fixture repair is what unblocked it.

**Do not send either agent a third round against the same brief.** There is no defect in
either diff that the programmer or the tester should have caught. The programmer escalated
the criterion 7 collision instead of narrowing its check until the suite went green, and
the tester refused a binary that was wrong and then proved its own repair with a
discrimination check rather than by showing green — those are the two behaviours this
arrangement exists to produce, and both happened without being asked twice.
