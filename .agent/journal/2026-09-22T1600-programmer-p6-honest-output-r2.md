---
agent: programmer
assignment: P6-honest-output
round: 2
status: partial
files_touched: [analysis/wacc.py, api/routes_valuation.py, templates/assumptions.html, config.py, models/valuation.py]
verdict: —
---

# P6-honest-output round 2 — the web path can now report a substituted rate, and a debt-free company is told apart from a balance sheet that did not extract

> Opened before the first command. Filled as each result landed.

## What I did

Three things, and nothing else. **No round-1 work was redone and no new extraction was
run** — F1 is a form default and a template, F2 is one branch in `analysis/wacc.py`, F6 is
a digit in a comment. Extraction spend this round: **zero tokens.** The round-1 diff is
untouched apart from the `analysis/wacc.py` branch F2 names.

**F1.** `api/routes_valuation.py`'s risk-free form field is now `str = Form("")` and
`templates/assumptions.html` no longer prefills it, so an unfilled field reaches `run_capm`
as `None` and the substituted-rate label is reachable on the web for the first time. The
constant is rendered into the field's **placeholder** from `config`, at the route boundary,
so the page still tells the reader what will be assumed without a second copy of `4.0`
living in a template — which is the defect that produced F1.

**F2.** `analysis/wacc.py`'s `if total_debt == 0: return 0.0` now draws the distinction
backlog item 22 is about. Zero debt with **zero** interest is a genuinely debt-free company:
it still returns `0.0`, now labelled `no debt reported`. Zero debt with **non-zero** interest
is a contradiction — a company that pays interest has debt — so the balance sheet did not
extract, and the run **stops**, naming the interest figure, its year, the debt figure, and
the three `BalanceSheet` fields that sum to it.

**F6.** `config.py`'s threshold table read `SE/beta = 0.395` where `sqrt(0.90/(0.10*58))` is
`0.3939`. Corrected to `0.394`, and all six figures in that table recomputed.

**F2 collides with done-criterion 7, and the collision is not resolvable inside my scope.**
Two existing tests in `tests/unit/test_wacc.py` build a "debt-free company" whose income
statement reports **20 of interest expense** — which is precisely the contradiction item 22
defines. Closing item 22 necessarily stops them. Section "The criterion 7 collision" below
proves that **no assertion in either test changed meaning**: every assertion still holds
once the fixture is made self-consistent. The repair is one argument in `tests/`, and
`tests/` is not mine to write.

## Findings answered, by number

### F1 · `major` · the web path could never report a substituted risk-free rate — **fixed**

Accepted without dispute. The reviewer is right, and so was my own round-1 finding 1.

Three edits, all inside the widened scope and **for this defect only**:

| File | Change |
|---|---|
| `api/routes_valuation.py:~140` | `risk_free_rate: float = Form(4.0)` → `risk_free_rate: str = Form("")` |
| `api/routes_valuation.py:~172` | `risk_free_rate=risk_free_rate / 100` → `float(risk_free_rate) / 100 if risk_free_rate.strip() else None` |
| `api/routes_valuation.py` (`assumptions_page` context) | new `default_risk_free_rate_display`, formatted from `config.DEFAULT_RISK_FREE_RATE` at the route boundary |
| `templates/assumptions.html:~84` | `value="4.0"` dropped; a placeholder rendered from that context value put in its place |

**Why a placeholder and not simply a blank field.** Deleting the prefill alone would have
closed the label defect and opened a worse one: a reader looking at an empty box has no way
to know a 4.00% is about to be assumed on their behalf. Rule 6 wants "a name, a default,
**the reason for that default**" *visible*. The placeholder names the constant
(`config.DEFAULT_RISK_FREE_RATE`) and its value, and the result page then names the reason.

**Why the value comes from `config` and is not retyped.** The literal `4.0` in the template
was half of the defect: the reviewer's own words were that "changing the constant would move
the CLI while leaving the web app at 4.0%". Putting `4.0` back into a placeholder string
would rebuild exactly that. The route formats the constant into the context dict and the
template only interpolates it, so there is now **one** definition of the web app's risk-free
default and it is the same one the CLI reads.

**Why the field is `str` and not `float | None`.** A `float` form field cannot express "the
user left this blank" without inventing a sentinel number, and a sentinel number is the
family of defect this whole unit exists to close. `""` is not a float. `equity_risk_premium`,
`beta_override` and `cost_of_debt_override` beside it already use exactly this shape, so this
is the pattern that was already there rather than a second one — which is what the
assignment's step 5 asks for.

**Why `.strip()` on the string and not a falsy test on the number.** A user who types `0`
sends `"0"`, a non-empty string, and gets a genuine 0.0% rate. `if risk_free_rate` on a float
would have read that `0` as "missing" — backlog item 6's defect, five instances of which sit
in the same function and which I did **not** touch.

**Proof — a real `POST /valuation` through `TestClient`, blank risk-free field**
(`c:/tmp/p6r2/route_probe.py`; extraction and yfinance faked at the boundary, nothing else
stubbed, no network, no key, no PDF):

```
GET  /assumptions -> 200
  the field as rendered:
    name="risk_free_rate" placeholder="blank = assume 4.0% (config.DEFAULT_RISK_FREE_RATE)" step="0.1">
  value="4.0" present on the page? False

POST /valuation -> 200 (11003 bytes)
  error page? False

   YES  ASSUMPTION — config.DEFAULT_RISK_FREE_RATE
   no   supplied by the caller (--risk-free-rate …)
   YES  beta reliability verdict
   YES  substituted cost of debt
```

The rendered rows, tags stripped:

```
    Beta                       | 1.048
    Beta — source              | measured — OLS regression of this stock's returns on the S&P 500's, …
    Beta — reliability         | NOT RELIABLE — R-squared 0.164 is below the 0.200 minimum in
                                 config.MINIMUM_BETA_R_SQUARED. The market explains only 16.4% of thi…
    R-squared                  | 0.164
    Std error of beta          | 0.311
    Risk-Free Rate             | 4.00%
    Risk-Free Rate — source    | ASSUMPTION — config.DEFAULT_RISK_FREE_RATE. No rate was supplied and
                                 this platform fetches no treasury series, so the config…
    Cost of Debt (pre-tax)     | 4.00%
    Cost of Debt — source      | ASSUMPTION — config.DEFAULT_COST_OF_DEBT (4.00%) was SUBSTITUTED,
                                 because interest expense is not reported separately (0) whil…
```

**Both branches are reachable, which is the point.** The same form with `4.0` typed into the
field:

```
  and the same form WITH a rate typed in (4.0):
   POST /valuation -> 200
    YES  supplied by the caller
    no   ASSUMPTION — config.DEFAULT_RISK_FREE_RATE
```

The page now tells a reader who supplied a rate that they supplied it, and a reader who did
not that a constant was substituted. Before this change it said the first thing to everybody.

**Nothing else in `api/routes_valuation.py` was touched.** Items 5 (the module-global
extraction cache), 6 (the five `x / 100 if x else None` conversions, lines immediately above
my edit), 8 (the blanket `except Exception`), 26 and 29 are all still there and all still
theirs. `git diff` on that file is three hunks, all risk-free.

### F2 · `major` · `total_debt == 0 → 0.0` is backlog item 22 — **closed**

Accepted without dispute. I agree the line became mine when its arity changed, and I do not
contest `severity.md`.

The two cases, as the amendment specifies them:

| Case | Behaviour now | Why |
|---|---|---|
| `total_debt == 0`, `interest_expense == 0` | returns `0.0`, labelled `no debt reported: …` | a real measurement of a real debt-free company |
| `total_debt == 0`, `interest_expense != 0` | **raises `ValueError`**, naming both figures | a company paying interest has debt, so the balance sheet did not extract |

**Why interest expense is the right discriminator.** Backlog item 22 states it in as many
words: "A filing that reports an interest expense but from which no debt balance was
extracted is missing data, not a debt-free company." The income statement is the only other
statement in the function's signature, and it is the one that carries the evidence.

**Why it raises rather than labels.** The item-9 sibling one branch below *substitutes* a
rate and is correctly rule 6 — a cost of debt is not a filing figure. This one is different:
`total_debt` **is** a filing figure, read from three balance-sheet lines, and a zero standing
where the income statement says there was debt is a **missing input**. Rule 3, not rule 6.

**And the cost is not confined to the rate.** With `total_debt == 0` the debt *weight* in
`calculate_wacc` is also 0, so the entire debt term drops out of WACC. The firm is discounted
at its cost of equity, the discount rate is overstated, and the share price is understated —
on a clean run, with nothing in the output saying so. Item 22's own text anticipates this
("it will the moment the weights come from anywhere else"); in fact the weights already come
from the same zero, so it is live today, not latent.

**Where the check sits, and where it deliberately does not.** It is inside
`cost_of_debt_with_source`, *after* the caller-override branch. A caller who passes
`--cost-of-debt` has answered the question the function was asked, and on that path the
function reads neither statement. That leaves a real hole — an overridden cost of debt with
a missing balance sheet still yields a zero debt weight — but that hole is about the
**weights**, not about the rate, it is not what item 22 describes, and closing it would have
widened this unit into a third existing test. **It is finding 1 below**, not something I
quietly took.

**Proof — `c:/tmp/p6r2/f2_probe.py`**, fixtures by hand, no network:

```
=== CRITERION 10 — zero debt, zero interest: a debt-free company ===
  rate   = 0.0
  source = no debt reported: total debt on the balance sheet is 0 and the income statement
           reports no interest expense for 2025, so this company is debt-free and there is
           no rate to measure. The debt term drops out of the WACC, which is therefore the
           cost of equity.
  calculate_wacc -> wacc=0.1000  debt_weight=0.0  equity_weight=1.0  (no raise)

=== CRITERION 11 — zero debt, non-zero interest: a contradiction ===
  ValueError: the balance sheet reports total debt of 0 while the income statement reports
  interest expense of 20.00 for 2025. A company that pays interest has debt, so the debt
  balance (BalanceSheet.short_term_debt + BalanceSheet.current_portion_lt_debt +
  BalanceSheet.long_term_debt, year 2025) did not extract. The cost of debt is not
  substituted and the WACC is not computed from a zero debt weight: supply the debt
  balance, or supply a cost of debt explicitly with --cost-of-debt if the zero is correct.
  names the interest figure 20?  True
  names the debt figure 0?       True

=== the same contradiction through calculate_wacc ===
  ValueError raised, first 60 chars: the balance sheet reports total debt of 0 while the income s…

=== the measured and substituted branches are UNCHANGED ===
  interest 20 / debt 400 -> (0.05, 'measured from the filing: interest expense 20 / total debt 400')
  interest  0 / debt 400 -> 0.04
  override 0.055        -> (0.055, 'supplied by the caller (--cost-of-debt / …). Not derived from the filing.')
```

The measured branch still divides 20 / 400 = 0.05, the substituted branch still returns
`config.DEFAULT_COST_OF_DEBT`, and the override branch still short-circuits. Only the
zero-debt branch changed.

### F6 · `note` · a rounding slip in the threshold derivation — **fixed**

`config.py` read `R^2 = 0.10  ->  SE/beta = 0.395`. Recomputed:

```
$ .venv/Scripts/python.exe -c "import math; [print(f'R2={r:.2f}  SE/beta={math.sqrt((1-r)/(r*58)):.4f}  ->  rounds to {math.sqrt((1-r)/(r*58)):.3f}   95% interval +/- {1.96*math.sqrt((1-r)/(r*58)):.1%}') for r in (0.30,0.20,0.10)]"
R2=0.30  SE/beta=0.2006  ->  rounds to 0.201   95% interval +/- 39.3%
R2=0.20  SE/beta=0.2626  ->  rounds to 0.263   95% interval +/- 51.5%
R2=0.10  SE/beta=0.3939  ->  rounds to 0.394   95% interval +/- 77.2%
```

`0.395` → **`0.394`**. The reviewer's arithmetic is exact and mine was not. The other two
rows (0.201, 0.263) and all three interval widths (39% / 52% / 77%) are confirmed correct
and were left alone.

### F3, F4, F5, F7 · `minor` / `note` · **not fixed, and not mine to widen into**

All four are in `cli.py`, which is in my original Files in scope — but the round-2 amendment
names F1 and F2 as the work and says of `api/routes_valuation.py` that the widening is "for
this defect only". I read that as a narrow round, not an invitation to reopen round 1's
accepted files. They are real and they are listed as findings 2–5 below so an assignment can
be written from them. **F5 in particular will bite the tester** the amendment implies.

### F8 · the `confidence` defect · **seen, named, and left**

I saw it, I reported it myself as round-1 finding 2, and the reviewer confirmed it and
widened it. **It is backlog item 36** — `docs/9-reference/refactor-backlog.md` in the working
tree already carries it, written by the orchestrator, not by me (`git diff` on that file is
+62 lines all under "36.", and `docs/` is denied to my write guard). I touched nothing in
`ingestion/` or `analysis/normalizer.py`. It gets its own unit.

## The criterion 7 collision — the one thing this round did not deliver

`pytest -q` is **`3 failed, 118 passed`**, not `1 failed, 120 passed`. Both new failures are
in `tests/unit/test_wacc.py` and both have the same single cause.

```
FAILED tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent   <- the expected red
FAILED tests/unit/test_wacc.py::test_a_debt_free_company_prices_at_its_cost_of_equity
FAILED tests/unit/test_wacc.py::test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt
```

**The cause.** `tests/unit/test_wacc.py` has two module-level fixtures:

```python
def _income_statement(interest_expense: float = 20.0) -> IncomeStatement:   # line 69
def _balance_sheet_without_debt() -> BalanceSheet:                          # line 87
    """No financial debt at all. Payables are still there, and must not count."""
    return BalanceSheet(year=2025, accounts_payable=500.0)
```

Both failing tests call `calculate_wacc(income_statement=_income_statement(), balance_sheet=_balance_sheet_without_debt(), …)` — **a "debt-free company" whose income statement reports 20 of interest expense.** That pairing *is* the contradiction backlog item 22 defines. Any implementation of criterion 11 stops on it. There is no placement of the check that closes item 22 and leaves those two calls alone: both go through `calculate_wacc`, and one of them (`test_a_debt_free_company_prices_at_its_cost_of_equity`) deliberately omits the cost-of-debt override precisely so that "the derivation path in `calculate_cost_of_debt` runs rather than the override path".

**No assertion changed meaning, and I can show it rather than assert it.** Criterion 7's words
are "no existing assertion changed meaning". Both tests now fail at *setup*, before their
asserts. Every assertion in both still holds once the fixture is made self-consistent —
`c:/tmp/p6r2/f2_probe.py`, final block:

```
=== the two red tests: their ASSERTIONS hold once the fixture is consistent ===
  test_a_debt_free_company_prices_at_its_cost_of_equity
    debt_weight == 0.0 ? True   wacc == 0.10 ? True
  test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt
    cost_of_equity == 0.10 ? True
```

**The repair is one argument, in a file I may not write.** In both tests,
`_income_statement()` → `_income_statement(interest_expense=0.0)`. That is all. A debt-free
company paying no interest is what both docstrings say they are testing:
"`test_a_debt_free_company_prices_at_its_cost_of_equity`" and "A company with no market
capitalisation and no debt". Setting the interest to zero also leaves both derivations intact
— neither test reads `result.cost_of_debt` or `result.tax_rate`, and both say in their own
docstrings that they deliberately do not, so the fixture's EBT moving from 300 to 320 reaches
no assertion.

**I did not touch `tests/`.** `git status --short -- tests/` and `git diff --stat -- tests/`
are both empty.

**This is an escalation, not a decision I took.** Criterion 11 ("interest with no debt
balance **stops**") and criterion 7 (`1 failed, 120 passed`, no test edited) cannot both hold
against `tests/unit/test_wacc.py` as written. I implemented the criterion the amendment
introduced, because that is the work that was commissioned this round, and I am reporting the
cost in full rather than quietly narrowing the check until the suite went green — narrowing
it to dodge two tests would be changing code to reach a target, which is forbidden. **The
orchestrator chooses**: queue the two-line tester repair, or revert F2 and record a decision
on `analysis/wacc.py`'s zero-debt branch. I am not picking that side.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | different PDF, same ticker → **miss** | **pass, round 1, verified by the reviewer** | not redone; no extraction run this round |
| 2 | unchanged PDF → **hit** | **pass, round 1, verified** | not redone |
| 3 | the miss names what changed | **pass, round 1, verified** | not redone |
| 4 | the **web** path reports a substituted risk-free rate | **pass** | `c:/tmp/p6r2/route_probe.py` — real `POST /valuation`, `ASSUMPTION — config.DEFAULT_RISK_FREE_RATE` **YES**, `supplied by the caller` **no**; block pasted under F1 |
| 4b | the form default is no longer a literal | **pass** | `grep -n "Form(4.0)" api/routes_valuation.py` → **exit 1, no output**; `grep -n 'value="4.0"' templates/assumptions.html` → **exit 1, no output** |
| 5 | weak regression labelled beside the beta | **pass** | same rendered page: `Beta — reliability | NOT RELIABLE — R-squared 0.164 is below the 0.200 minimum…`, the row under `Beta` |
| 6 | substituted cost of debt labelled | **pass** | same rendered page, interest 0 against 500 of debt: `Cost of Debt — source | ASSUMPTION — config.DEFAULT_COST_OF_DEBT (4.00%) was SUBSTITUTED…` |
| 7 | no existing assertion changed meaning | **FAIL — `3 failed, 118 passed`** | `pytest -q`. Both new failures fail at **setup**, not at an assertion; see "The criterion 7 collision" |
| 8 | the routes still serve | **pass** | `GET /` **200**, `GET /assumptions` **200**, `POST /valuation` **200** (11,003 bytes, not an error page) |
| 9 | lint 5 / types ≤14 / census ≤116 | **pass** | **5 / 14 / 116**, mypy **set**-diffed, below |
| 10 | debt-free company returns `0.0`, labelled, no raise | **pass** | `c:/tmp/p6r2/f2_probe.py` — `rate = 0.0`, `source = no debt reported: …`, `calculate_wacc -> wacc=0.1000 debt_weight=0.0 (no raise)` |
| 11 | interest with no debt balance **stops**, naming both | **pass** | same script — `ValueError: the balance sheet reports total debt of 0 while the income statement reports interest expense of 20.00 for 2025…`; `names the interest figure 20? True`, `names the debt figure 0? True` |

Criteria 1, 2, 3 were verified by the reviewer by falsification (`17,062` appears **zero**
times in the FY2025 PDF; the live sha256 matches run 2's hit message byte for byte) and by
exercising the key with fabricated files. **I did not re-run them and I spent no extraction
tokens.** Nothing in this round's diff touches `cli.py`.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The web risk-free field is `str = Form("")`, not `float \| None` | A `float` field cannot carry "blank". Expressing it would need a sentinel number, and a sentinel number is the defect family this unit exists to close | `equity_risk_premium`, `beta_override` and `cost_of_debt_override` in the same signature already use `str = Form("")`. Assignment step 5: follow the pattern, do not invent a second |
| The field is blank with a **placeholder**, not blank and silent | Rule 6 wants "a name, a default, **the reason for that default**" visible. An empty box tells the reader nothing about the 4.00% about to be assumed for them | Deleting the prefill alone would close the label defect and open a worse one |
| The placeholder's number comes from `config` via the route context, not typed into the template | The template literal `4.0` was half of F1: the reviewer's own words, "changing the constant would move the CLI while leaving the web app at 4.0%". Retyping it in a placeholder rebuilds that exactly | One definition of the web default, and it is the same constant the CLI reads |
| The percentage conversion for that placeholder happens in the route, not in the template | The units convention: percentages convert at the route boundary, once. Every other display figure in that context dict is formatted the same way | A `{{ x * 100 }}` in jinja puts arithmetic in the template, where no test and no type checker looks |
| `.strip()` on the string, not `if risk_free_rate` on the number | A user who types `0` must get 0.0%, not a substitution. `"0"` is a non-empty string; `0.0` is falsy | `if x` would be backlog item 6's defect, five instances of which sit in the lines immediately above. I did not touch them and I did not copy them |
| Item 22's discriminator is **interest expense**, not a heuristic | Backlog item 22 states it: "A filing that reports an interest expense but from which no debt balance was extracted is missing data, not a debt-free company" | Any threshold ("debt is 0 but revenue is large") would be a number chosen to make cases pass — tuning to a target, forbidden |
| The zero-debt contradiction **raises**; the zero-interest substitution one branch below still **labels** | `total_debt` is a filing figure read from three balance-sheet lines, so a wrong zero is a missing input — rule 3. A cost of debt is not a filing figure, so substituting one is rule 6, and `rules.md`'s own "Why" paragraph names that exact site as the rule-6 exemplar | Making both stop would refuse legitimate runs; making both label would leave item 22 open |
| The check sits **after** the override branch | A caller who passed `--cost-of-debt` answered the question the function was asked; on that path it reads neither statement. A balance-sheet validity check inside a branch that does not read the balance sheet is misplaced | It leaves a real hole in the **weights**. I did not take it silently — it is finding 1, written so an assignment can be cut from it |
| F2 was implemented even though it turns two tests red | Criterion 11 is the work the amendment commissioned. The alternative — narrowing the check until the suite went green — is changing code to reach a target | I report the collision in full and name the one-argument repair, and I leave the choice to the orchestrator |
| The old `Form(4.0)` and `value="4.0"` expressions are **described**, not quoted, in the new comments | Criterion 4b is measured by grepping this file for that exact string. A comment quoting it makes the criterion unmeasurable | The history is still recorded, in words, one line above the code |
| `ProjectionAssumptions.risk_free_rate`'s comment "None = fetch from market" was corrected | It is false — nothing in this platform reads a treasury series, which is the whole basis of backlog item 34. A comment that lies about a data source is how F1 survived a round | `models/valuation.py` is in Files in scope. No field, type or default changed; the diff is comment-only |

**No code change in this round was made to reach a target number.** The one place I could
have been accused of it is F2's placement, and I have written above why the override branch
is excluded on merit and named the hole it leaves as a finding rather than banking it.

## Rule 3 — what stops, and what does not

Every value this round's diff reads. One row each.

| Value read | If it were missing | Evidence |
|---|---|---|
| `balance_sheet.total_debt == 0` with `interest_expense != 0` | **stops**, naming the interest figure, its year, the debt figure and the three `BalanceSheet` fields that sum to it | `c:/tmp/p6r2/f2_probe.py`, criterion 11 block — `ValueError: the balance sheet reports total debt of 0 while the income statement reports interest expense of 20.00 for 2025…` |
| `balance_sheet.total_debt == 0` with `interest_expense == 0` | **does not stop — returns `0.0`, labelled `no debt reported`** | Not a defect and not a guess: this is a *measurement* of a debt-free company, and the amendment's table requires it to keep working. `analysis/wacc.py`, the branch's own comment says which of the two meanings it is asserting and on what evidence |
| `risk_free_rate` form field, when blank | **does not stop — substitutes `config.DEFAULT_RISK_FREE_RATE`, and now says so on the web** | Rule 6 by design. A risk-free rate is not extracted from a filing, so no measurement is being papered over; step 2 forbids the rule 5 half. The label is the closure |
| `risk_free_rate` form field, when non-empty | **does not stop — `float(...)` raises on garbage**, which the route's blanket handler turns into the error page | Unchanged behaviour, identical to `equity_risk_premium` beside it. The blanket handler is backlog item 8 and is not mine |
| `config.DEFAULT_RISK_FREE_RATE`, read for the placeholder | **cannot be missing** — a module-level constant; an absent name is an `ImportError` at startup | `config.py`. Not a runtime input |
| `interest_expense` with debt > 0, when 0 | **does not stop — substitutes `config.DEFAULT_COST_OF_DEBT`, labelled** | Unchanged from round 1. Backlog item 9, closed as *labelled*; `rules.md`'s rule 6 "Why" paragraph names this exact site |

**One "defaults to" row is a finding against my own unit and I am writing it anyway:** the
zero-debt / zero-interest branch returns `0.0`. I record it as a *measurement* rather than a
guess, and the amendment's table says the same, but a reviewer should test that claim rather
than take it — the discriminator is a single `!=` on one field, and if an extractor ever
returns `interest_expense = 0.0` as its own missing-value default (backlog item 1's shape,
and `ingestion/` has ~30 of those), then a company with debt and a failed interest read lands
in the **substituted** branch, not the stop. That path is item 1's, not mine, but the
dependency is new and I am naming it.

**No new default was added.** The census grep over this round's added lines only:

```
$ git diff -U0 -- analysis/wacc.py api/routes_valuation.py templates/ config.py models/ \
    | grep "^+" | grep -E "if [^)]+ else 0(\.0)?\b|\bor +(0|0\.0)\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0|\*\*kwargs|getattr\("
exit=1        (no output)
```

## Rules 1, 2, 4, 5 and 6

- **Rule 1.** `ingestion/` untouched. No prompt, no schema field, no extractor code. **No
  extraction was run at all this round** — zero tokens. No number in this diff came from a
  model.
- **Rule 2.** No new function. `cost_of_debt_with_source` keeps its three named, typed
  parameters and its `tuple[float, str]` return. No `**kwargs`, no `getattr` on an outside
  name, no dict of functions. The `str` form field is a FastAPI declaration, not an argument
  bag.
- **Rule 3.** One new stop, one branch that deliberately does not stop, both in the table
  above.
- **Rule 4.** Improved on the web half. A reader of the *rendered page* can now name where
  the risk-free rate came from on a run where nobody supplied one — which was the half of
  item 34 that was still open. The chain from a share price back to a filing page is still
  not on the page.
- **Rule 5.** **No new data source.** `ingestion/` untouched; `grep -rn "treasury\|TNX\|risk_free" ingestion/`
  still returns nothing.
- **Rule 6.** Item 34 is now closed on **both** outputs rather than one. Item 22 is closed by
  telling a measurement and a missing input apart instead of labelling the ambiguity.

## Measurements

| Gate | Baseline (`d2ba1e5`) | Round 1 | **This round** | Verdict |
|---|---|---|---|---|
| Tests | `1 failed, 120 passed` | `1 failed, 120 passed` | **`3 failed, 118 passed`** | **regressed by 2** — both `tests/unit/test_wacc.py`, both at setup, both from one contradictory fixture. See the collision section |
| Lint | 5, all `BLE001` | 5 | **5** | unchanged |
| Types | 14 in 4 files | 14 | **14 in 4 files** | unchanged, **set**-diffed not counted |
| Rule-3 census | 116 | 116 | **116** | unchanged |
| `GET /` | 200 | 200 | **200** | — |

**Types, set-diffed rather than counted.** `git archive d2ba1e5` exported to
`c:/tmp/p6r2/base`, mypy re-run there with the documented gate
(`docs/8-build/environment.md:148`), both error lists sorted and `diff`ed:

```
=== only in BASE ===
api\routes_valuation.py:197: … no attribute "diluted_shares_outstanding"  [union-attr]
api\routes_valuation.py:206: … "IncomeStatement | None"; expected "IncomeStatement"  [arg-type]
api\routes_valuation.py:207: … "BalanceSheet | None"; expected "BalanceSheet"  [arg-type]
=== only in HEAD ===
api\routes_valuation.py:233: … no attribute "diluted_shares_outstanding"  [union-attr]
api\routes_valuation.py:242: … "IncomeStatement | None"; expected "IncomeStatement"  [arg-type]
api\routes_valuation.py:243: … "BalanceSheet | None"; expected "BalanceSheet"  [arg-type]
=== in both === 11
```

The three that move are the **same three errors shifted 36 lines** by my comment block. With
line numbers stripped the two sets are byte-identical:

```
$ diff <(sed 's/py:[0-9]*:/py:L:/' base.txt|sort) <(sed 's/py:[0-9]*:/py:L:/' head.txt|sort)
IDENTICAL SETS (14 = 14)
```

**Every other test file is green.** `pytest -q tests/unit/test_routes.py tests/unit/test_capm.py`
→ **`29 passed`**, including `test_post_valuation_renders_the_completed_valuation`, which
posts `"risk_free_rate": "4.0"` and now parses it out of a `str` field. `pytest -q
tests/unit/test_wacc.py` → `2 failed, 10 passed`, the two named above.

**Round-2 diff: 5 files.** `analysis/wacc.py`, `api/routes_valuation.py`,
`templates/assumptions.html`, `config.py` (one digit), `models/valuation.py` (comment only).
`cli.py`, `analysis/capm.py` and `templates/valuation_result.html` carry round-1 work and were
**not** re-opened. `tests/`, `ingestion/`, `static/`, `STATUS.md`, `.agent/journal/INDEX.md`
and `docs/` are untouched — `docs/9-reference/refactor-backlog.md` shows modified in
`git status` and that is the **orchestrator's** item 36 (+62 lines, all under heading "36."),
written before this round began; `docs/` is denied to my write guard.

**Figures this round moved:** none, in any valuation. No extraction, no valuation run. The
only behavioural change to a number is that a web run with a blank risk-free field now
reaches `run_capm` with `None` instead of `4.0` — and substitutes `config.DEFAULT_RISK_FREE_RATE`,
which **is** `0.04`. The arithmetic is identical; only the label changed.

**Scratch, all outside the repository:** `c:/tmp/p6r2/f2_probe.py`,
`c:/tmp/p6r2/route_probe.py`, `c:/tmp/p6r2/base/`, `c:/tmp/p6r2/{b,h,b2,h2,base_errs,head_errs}.txt`.
Nothing copied into the repository. `TestClient` opens no socket.

## What I did not do

- **Did not re-run any extraction.** F1, F2 and F6 are a form default, a template, a comment
  digit and a branch. Round 1's three runs stand and the reviewer verified criterion 1 by
  falsification. Spend this round: **zero tokens**.
- **Did not redo any round-1 work.** `cli.py`, `analysis/capm.py` and
  `templates/valuation_result.html` are byte-identical to the state the reviewer checked.
- **Did not touch the `confidence` defect.** It is **backlog item 36**. `ingestion/` and
  `analysis/normalizer.py` are untouched.
- **Did not touch anything else in `api/routes_valuation.py`.** Items 5, 6, 8, 26 and 29 all
  live in that file and none is mine. The five `x / 100 if x else None` conversions of item 6
  are the lines immediately above my edit and I left every one of them.
- **Did not touch `tests/`.** `git diff --stat -- tests/` is empty. The two red tests need a
  one-argument fixture repair and a tester owns it.
- **Did not fix F3, F4, F5 or F7.** All four are `cli.py`, and the amendment scoped this round
  to F1 and F2. Findings 2–5 below.
- **Did not close the override-path hole in `calculate_wacc`'s weights.** Finding 1 below.
- **Saw and left `analysis/capm.py:16`** — `from ingestion.price_fetcher import PriceData`,
  backlog item 17, a layering break. Not mine, not touched this round.
- **Saw and left** `cli.py`'s blanket `except Exception` (item 8) and its yfinance
  share-count fallback (items 1 and 12).

## Findings for the orchestrator

1. **An overridden cost of debt hides a missing balance sheet, and item 22 does not cover
   it.** `cost_of_debt_with_source` returns on `override is not None` before it reads either
   statement, so a run with `--cost-of-debt` (or the web's `cost_of_debt_override` field) and
   a balance sheet that did not extract still gets `debt_value = 0` in `calculate_wacc`, a
   debt weight of 0, and a WACC equal to the cost of equity. The rate the caller supplied is
   then multiplied by a zero weight and vanishes. This is the **weights** half of item 22 and
   it is not written down anywhere; item 22's text only reaches the rate. The fix is a
   `total_debt == 0 and interest_expense != 0` guard in `calculate_wacc` beside the existing
   `_require_finite(debt_value, …)` — but it turns a **third** existing test red
   (`test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt`, which pairs
   `_income_statement()`'s 20 of interest with `_balance_sheet_without_debt()` and an override
   of 0.90), so it needs the same tester repair as the two in the collision section. Worth one
   unit that does the fixture and the guard together.

2. **`tests/unit/test_wacc.py`'s fixture pair encodes the contradiction item 22 names**, and
   it will keep blocking rule-3 work in `analysis/wacc.py` until it is repaired.
   `_income_statement()` defaults `interest_expense=20.0` and is passed to
   `_balance_sheet_without_debt()` in **three** tests. The repair is
   `_income_statement(interest_expense=0.0)` at each of the three call sites; I proved by
   execution that every assertion in all three still holds. **This is the smallest,
   highest-value tester assignment on the board right now** — without it, criteria 10 and 11
   cannot coexist with criterion 7, and finding 1 cannot be done at all.

3. **`cli.py` has no tests, and the cache key is the thing most likely to regress silently**
   (round-1 finding 5, and the reviewer's F5 sharpens it). `ExtractionKey` and
   `InputFingerprint` are defined in `cli.py`, so a cache entry written by `python cli.py`
   pickles them as `__main__.ExtractionKey` and **cannot be read back by anything that
   imports `cli` as a module** — `pickle.load` raises `AttributeError` *before* the
   format-marker check, so the helpful `ValueError` is unreachable on the most likely real
   corruption. A tester building a fixture from a real CLI run hits this first thing. Fix and
   test together: move the two dataclasses out of `__main__`, or serialise the key as a plain
   dict.

4. **A user with an old-format cache pays for a full re-extraction and is told nothing**
   (reviewer F3). `.cache_{ticker}_extraction.pkl` beside the new `_inputs` name is never a
   candidate path, so the run goes straight to extracting with no message. One printed line —
   naming the old file, saying it is ignored because unpickling executes code, and warning
   that this run will re-extract — costs nothing and is consistent with this unit's own stated
   reason for refusing to overwrite a paid extraction silently.

5. **Two `cli.py` stops escape `main()` as raw tracebacks** (reviewer F4):
   `build_extraction_key`'s `FileNotFoundError` and `_load_cache`'s `ValueError` are raised
   outside the `try` that turns `parse_pdf_args`' `ValueError` into `SystemExit(f"ERROR: …")`
   two lines above. Rule 3 is satisfied — the run stops and names the path — only the
   presentation is inconsistent.

6. **The page's provenance rows are invisible to `tests/unit/test_routes.py`'s `_rows_under`
   helper** (round-1 finding 4, unchanged and still true). That helper matches `<td>(.*?)</td>`
   with no attributes; the label rows are `<td style="…">`. A tester writing against criteria
   4, 5 or 6 on the page must match differently. My own verification used a regex that accepts
   attributes (`c:/tmp/p6r2/route_probe.py`), which is the shape the helper needs.

7. **`static/style.css` still has no `.provenance` class** (round-1 finding 3), so **eight**
   `style="{{ PROV }}"` attributes (`grep -c` on the file) duplicate one declaration in
   `templates/valuation_result.html`. Cosmetic, but it is the kind of duplication that goes
   stale. A unit owning `static/` should lift it and delete the `{% set %}`.
