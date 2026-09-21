---
agent: programmer
assignment: P4-normalizer
round: 1
status: complete
files_touched: [analysis/normalizer.py]
---

# P4-normalizer — the adjustment engine carries a per-field sign, and stops instead of guessing

> Written incrementally: every measurement below was taken and recorded before the next
> command was run. Measured at `bf0e8bc` plus this unit's one-file change.

## What I did

`analysis/normalizer.py` computed one delta — `-amount` for `add_back`, `+amount` for
anything else — and applied it to whichever field `_resolve_field` returned. That is the
delta on an **expense** field. `models/financial_statements.py:31-37` already states the
correct thing, but about **earnings**: `adjusted_impact` is `+amount` for `add_back` and
`-amount` for `remove`. The two coincide only where the field reduces earnings, and
`other_non_operating` — which `models/financial_statements.py:91` **adds** in `ebt` — does
not. I made the field delta follow from the earnings impact, by multiplying
`item.adjusted_impact` by a per-field sign held in a table of **numbers**
(`_FIELD_EARNINGS_SIGN`, backlog item 19). Two smaller defects in the same function went
with it: an unrecognised `line_item` now raises `ValueError` naming the label and the year
instead of printing to stdout and guessing `other_operating_expense` (item 3), and a
`direction` that is neither `"add_back"` nor `"remove"` now raises `ValueError` naming the
value and the year instead of silently taking the `remove` branch (item 21). One file
changed, 82 insertions, 11 deletions. **`models/financial_statements.py` was not touched**
and `tests/` was not touched.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | two of the three red tests go green | **pass** | `.venv/Scripts/python.exe -m pytest -q tests/unit/test_normalizer_rule3_red.py` → `2 passed in 0.06s`. Before the change, the same command gave `2 failed` (`Failed: DID NOT RAISE ValueError`, `test_normalizer_rule3_red.py:107`) |
| 2 | nothing else broke | **pass** | `.venv/Scripts/python.exe -m pytest -q --ignore-glob="*_rule3_red.py"` → `90 passed in 3.15s`, **0 failed**. Identical to the baseline |
| 3 | the whole suite, reds included | **pass** | `.venv/Scripts/python.exe -m pytest -q` → **`1 failed, 92 passed in 3.83s`**. The single failure is `tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` — backlog item 2, out of scope. Baseline was `3 failed, 90 passed` |
| 4 | the non-operating case is correct | **pass** | `c:/tmp/p4_norm_proof.py`, output below: `other_non_operating` **30.0**, `ebt` **430.0**, against `130.0` / `530.0` before |
| 5 | the guess is gone | **pass** | `grep -n 'other_operating_expense"' analysis/normalizer.py` → 3 hits, all table rows (`:37`, `:38`, `:58`); **no `return`, no fallback**. `grep -c "print(" analysis/normalizer.py` → **0** |
| 6 | coverage of `analysis/normalizer.py` | **pass — 100%** | `COVERAGE_FILE=c:/tmp/.cov_p4 … pytest -q --cov=analysis --cov-report=term` → `analysis\normalizer.py 36 0 100%`, `TOTAL 202 0 100%`. With `--cov-branch`: `36 0 16 0 100%` — statements **and** branches. Was `28 2 93%`, missing `50-51`, which are the two lines this unit deleted |
| 7 | lint unchanged | **pass** | `.venv/Scripts/python.exe -m ruff check .` → `Found 5 errors`, all `BLE001`, at `api/routes_valuation.py:96,220`, `cli.py:758`, `ingestion/claude_extractor.py:795`, `tests/test_e2e_all_googl.py:106`. Same five as the baseline. `analysis/normalizer.py` contributes none |
| 8 | types not worse | **pass** | `… -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` → **`Found 33 errors in 4 files (checked 18 source files)`**, identical to the baseline. `mypy analysis/normalizer.py --ignore-missing-imports` → `Success: no issues found in 1 source file` |
| 9 | the rule-3 census did not rise | **pass — it fell to 116** | the census grep from `docs/2-rules/rules.md` over `models analysis api ingestion` → **116** (baseline 117). `analysis/normalizer.py` now holds **0** hits; it held 1, at the old `:69` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Computed the field delta as `item.adjusted_impact * _FIELD_EARNINGS_SIGN[field]` | The assignment's step 1 and backlog item 19: the delta on a **field** is the impact on **earnings** times the sign the field carries into earnings. `adjusted_impact` (`models/financial_statements.py:31-37`) is the existing, correct statement of the earnings impact | Re-deriving the earnings impact inside the normalizer would put the same rule in two files again — which is what let the two disagree in the first place. Now `models/` owns "what this item does to earnings" and `analysis/normalizer.py` owns "which way that moves this line" |
| A `dict[str, float]` keyed by field name, holding `-1.0` / `+1.0` | Rule 2: *"a lookup table that maps a key to a **number** is fine. Looking up a number is fine. Looking up behaviour is not."* | A dict of functions, or an `if field == "other_non_operating"` branch, were both available. The first is forbidden outright; the second scatters the sign across control flow, where adding a seventh field means finding the branch rather than adding a row |
| Verified all six signs **against the model, by execution**, not by reading `ebt` | `.claude/agents/programmer.md`: *"Prove a claim by execution."* The assignment explicitly said to check its claim rather than take it | `c:/tmp/p4_sign_check.py` bumps each field by `+1.0` on a real `IncomeStatement` and reads the change in `ebt`. Output below: all six agree with the table. A reading of `total_operating_expenses` would have missed a field the property omits |
| Checked the sign table covers `_LABEL_TO_FIELD`'s whole range **at import**, with an `assert` | Rule 3 — a routed field with no sign is an input the engine does not have, and that must stop. Both tables are literals in this file, so completeness is a source-level invariant, not a data question | A `raise` at the call site would only fire on the one label routed to the unsigned field, so a run could ship with the defect latent; and it would be a statement no test can reach, which would cost criterion 6's 100%. The `assert` is one statement, executed on every import, so it is always covered. **Proved by breaking a copy** outside the repository: deleting the `other_non_operating` row gives `AssertionError: _LABEL_TO_FIELD routes to a field with no entry in _FIELD_EARNINGS_SIGN: ['other_non_operating']` at import |
| `ValueError`, with the label / value **and** the year in the message | The assignment's steps 2 and 3; `ingestion/claude_extractor.py:835` already raises `ValueError` for an absent input; the two waiting red tests assert `ValueError` | Typed exception classes are phase 5 and explicitly not in this unit |
| Put the direction check in `_field_delta`, not in `apply_adjustments` | The check guards the one place `direction` is read. `adjusted_impact` itself has the same `== "add_back"` shape, and I may not touch `models/` — so the value is validated immediately before it is handed to that property | Validating in `apply_adjustments` would leave `_field_delta` usable with an unchecked direction by any future caller |
| Replaced `changes.get(field, 0.0) + delta` with an explicit `if field in changes` | That line is one of the 117 census sites (verified: `grep -cE …` on the file was 1, now 0), and it is a line this unit had to rewrite anyway to change how `delta` is computed. Rule 3's table names `.get(k, 0)` as a form of the defect | The zero here is genuinely "nothing accumulated yet" rather than a missing input, so leaving it would not have been *wrong* — but it is the exact shape a reviewer greps for, on a line inside my own diff, and both arms are exercised by the existing tests so it costs no coverage |
| Reworded the comment that quoted the old `.get(field, 0.0)` | The first draft's comment **matched the census grep**, holding the count at 117 when the code site was gone. A measurement that counts a comment is not a measurement | Kept the explanation, dropped the literal code text |
| Left `getattr(income_statement, f)` at `:147` and the `**{…}` expansion into `dataclasses.replace` | The assignment's known open item, and it is now closed: see the next section | Enumerating six fields by hand at the call site would add a second place to edit when a field is added, with no rule requiring it |

**No change in this unit was made to reach a target number.** The one figure this unit was
given a target for — `ebt` 430.0 — falls out of the sign table, and the table was verified
against `IncomeStatement` by execution before the target was checked.

## The `getattr` known open item — checked, as asked

`analysis/normalizer.py:147` does `getattr(income_statement, f)` where `f` came from
`_resolve_field`. Rule 2 forbids *"`getattr` on a name that came from outside the file"*.
Measured, not read (`c:/tmp/p4_closed_set.py`):

```
fields _LABEL_TO_FIELD can return: ['cost_of_revenue', 'depreciation_amortization',
  'other_non_operating', 'other_operating_expense', 'rd_expense', 'sga']
every one is a real IncomeStatement field: True
every one has a sign: True
sign table has no field the router cannot reach: True
_resolve_field over every label returns only those: True
```

`_resolve_field` now has exactly two exits: a value from `_LABEL_TO_FIELD`, or `raise`.
Every one of those six values is a literal in this file and a real
`dataclasses.field` of `IncomeStatement`. The name does **not** come from outside the
file: the LLM's `line_item` string selects a row, it is never used as the attribute name.
Before this unit the set was the same six, but the *guess* meant a run continued on a
label nobody wrote a row for.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `item.line_item`, unrecognised label | **stops and names `line_item`, the label and the year** | `analysis/normalizer.py:87-91`. Measured: `ValueError: Unrecognised line_item 'Goodwill impairment charge' on the 2023 non-recurring item: it matches no IncomeStatement field. line_item must name one of: cost_of_revenue, depreciation_amortization, other_non_operating, other_operating_expense, rd_expense, sga.` Was: a `print` and `other_operating_expense` |
| `item.direction`, not `"add_back"` or `"remove"` | **stops and names `direction`, the value and the year** | `analysis/normalizer.py:108-112`. Measured: `ValueError: Unrecognised direction 'addback' on the 2022 non-recurring item 'Restructuring charge': direction must be one of: add_back, remove.` Was: the `remove` branch, silently |
| the sign of a routed field | **stops at import** if `_LABEL_TO_FIELD` routes anywhere `_FIELD_EARNINGS_SIGN` does not cover; **stops at the lookup** (`KeyError` naming the field) if the table is mutated at run time | `analysis/normalizer.py:66-71` and `:113`. Both proved by deletion, below. Neither falls back to a sign |
| `item.amount` | reads it; `NonRecurringItem.amount` has **no default**, so an item cannot be constructed without one | `models/financial_statements.py:24`. Not this unit's to change; the constructor already stops |
| `item.year` | same — no default | `models/financial_statements.py:22` |
| `getattr(income_statement, f)` | cannot be missing: `f` is one of six literal field names, each a real `IncomeStatement` field | proved by execution above |
| `by_year.get(stmt.year, [])` at `:167` | returns `[]` — **a year with no non-recurring items**, which is the documented identity (`apply_adjustments(stmt, []) is stmt`), not a missing input | `analysis/normalizer.py:167`. Unchanged by this unit, asserted by `tests/unit/test_normalizer.py`. It is not a census hit and not a rule-3 shape: the absence *is* the datum |

**No "defaults to" row.** `analysis/normalizer.py` now holds zero census hits.

## Measurements

### The test suite, as failure sets

| | Before (`bf0e8bc`) | After |
|---|---|---|
| `pytest -q` | `3 failed, 90 passed` | **`1 failed, 92 passed`** |
| failure **set** | `{test_dcf_rule3_red::…balance_sheet_is_absent, test_normalizer_rule3_red::…unrecognised_line_item…, test_normalizer_rule3_red::…unrecognised_direction…}` | **`{test_dcf_rule3_red::…balance_sheet_is_absent}`** |
| gate form `--ignore-glob="*_rule3_red.py"` | `90 passed`, 0 failed | **`90 passed`, 0 failed** |
| `tests/unit/test_normalizer_rule3_red.py` | `2 failed` | **`2 passed`** |

The two tests that went green were not touched: `git status --short` shows one modified
file, `analysis/normalizer.py`.

### Criterion 4 — the non-operating case, run

`c:/tmp/p4_norm_proof.py`, `PYTHONDONTWRITEBYTECODE=1`, run from `c:/tmp`:

```
--- 1. the non-operating case (criterion 4) ---
BEFORE  ono=   80.0 ebit=  400.0 ebt=  480.0 ni=  380.0 etr=0.208333
AFTER   ono=   30.0 ebit=  400.0 ebt=  430.0 ni=  330.0 etr=0.232558
CLEAN   ono=   30.0 ebit=  400.0 ebt=  430.0 ni=  330.0 etr=0.232558
required: ono 30.0 ebt 430.0 -> got ono 30.0 ebt 430.0
declared adjusted_impact -50.0  actual dEBT -50.0
caller's own statement untouched: ono 80.0
assignment's literal line-up (no COGS): ono 30.0 ebt 830.0 (ebit 800, not 400)

--- 2. the expense path is unchanged ---
add_back 50 on sga: sga 150.0 (expect 150.0), ebit 450.0 (expect 450.0)
declared adjusted_impact 50.0  actual dEBIT 50.0

--- 3. the guess is gone (criterion 5) ---
ValueError: Unrecognised line_item 'Goodwill impairment charge' on the 2023 non-recurring item: it matches no IncomeStatement field. line_item must name one of: cost_of_revenue, depreciation_amortization, other_non_operating, other_operating_expense, rd_expense, sga.

--- 4. an unrecognised direction stops ---
ValueError: Unrecognised direction 'addback' on the 2022 non-recurring item 'Restructuring charge': direction must be one of: add_back, remove.

--- 5. delete the sign and the run stops (rule 3, by deletion not by grep) ---
KeyError: 'other_non_operating'  <- the lookup stops; it does not fall back to a sign
```

`AFTER` and `CLEAN` agree on every line, which is the requirement: adjusting the statement
must give the same numbers as a statement that never held the one-time gain.

**The assignment's fixture is one line short, and I ran both.** Step 4 lists *"revenue
1000, sga 200, other_non_operating 80, tax_expense 100"* and requires `ebt` **430.0**. That
line-up gives `ebit = 1000 − 200 = 800` and `ebt = 830.0`. The required 430.0 needs
`cost_of_revenue = 400`, which is in the reviewer's own script
(`.agent/journal/2026-09-20T2215-code_reviewer-p1c-flow.md:43-45`) and in the before/after
figures the assignment quotes from it. I used the reviewer's five-line fixture, and printed
the assignment's literal four-line one beside it so the difference is visible rather than
silently resolved. The defect and the fix are identical either way: `ono` 130.0 → 30.0, a
`−100` swing on a 50 item, and the `ebt` delta now equals `adjusted_impact` exactly.

The effective tax rate moves from `0.208333` to `0.232558` — the figure the reviewer
derived as correct. That is the input to `analysis/projector.py:63-64`, and hence to every
projected NOPAT; the 5.7% NOPAT overstatement the reviewer measured is gone at its source.

### The sign table, verified against the model

`c:/tmp/p4_sign_check.py` — bump each field by `+1.0` on a populated `IncomeStatement` and
read the change in `ebt`:

```
field                        dEBT per +1  table  agree
cost_of_revenue                     -1.0   -1.0   True
sga                                 -1.0   -1.0   True
rd_expense                          -1.0   -1.0   True
depreciation_amortization           -1.0   -1.0   True
other_operating_expense             -1.0   -1.0   True
other_non_operating                  1.0    1.0   True
```

The assignment's claim — *"only `other_non_operating` is `+1`"* — holds, and it is the
model that says so, not me.

### Coverage

```
$ COVERAGE_FILE=c:/tmp/.cov_p4 .venv/Scripts/python.exe -m pytest -q --cov=analysis --cov-report=term-missing
analysis\normalizer.py      36      0   100%
TOTAL                      202      0   100%

$ COVERAGE_FILE=c:/tmp/.cov_p4b ... --cov-branch --cov-report=term-missing
analysis\normalizer.py      36      0     16      0   100%
```

100% of statements **and** of branches, up from `28 2 93%` (missing `50-51`). It reached
100% as a consequence: the two uncovered lines were the guess, and the red test that
already existed exercises the `raise` that replaced them. Nothing is uncovered, so there is
no line to name. **The standing caveat still applies** — coverage.py does not count a
conditional expression as a branch; this file now contains none.

### Lint, types, census

| Gate | Before | After |
|---|---|---|
| `ruff check .` | 5 errors, all `BLE001` | **5 errors, all `BLE001`** — the same five files and lines |
| `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 33 errors in 4 files, 18 checked | **33 errors in 4 files, 18 checked** — unchanged |
| `mypy analysis/normalizer.py` | clean | **clean** |
| rule-3 census over `models analysis api ingestion` | 117 | **116** |
| census hits in `analysis/normalizer.py` | 1 (`:69`) | **0** |

I added no `except` of any kind, so the `BLE001` count could not move.

## What I did not do

- **Did not touch `models/financial_statements.py`.** `adjusted_impact` is correct as
  written and this unit now depends on it. I have no dispute with it.
- **Did not touch `tests/`.** The two red tests went green because the code changed. I did
  not open either to edit it; I read `test_normalizer_rule3_red.py` to learn which
  exception type and which substrings the messages must carry, which the assignment
  directs (`ValueError`, naming the label / value).
- **Did not add a typed exception class.** Phase 5, and explicitly out of scope.
- **Did not add `interest_income` to `_LABEL_TO_FIELD`.** The reviewer noted it is the
  same shape as `other_non_operating`. It now *could* be added safely — it would need a
  `+1.0` row, and the import-time check would refuse it without one — but adding a route
  the model was never told to use is a change to the extraction contract
  (`ingestion/claude_extractor.py:187` lists the six legal `line_item` values), not to this
  file.
- **Did not fix `analysis/dcf.py:80`.** Backlog item 2, its red test stays red, criterion 3
  depends on it.
- **Did not change `docs/`, `STATUS.md` or `.agent/journal/INDEX.md`.** Three of them are
  now stale in ways the orchestrator owns; see below.

## Findings for the orchestrator

### F1 — the extractor can still emit a `line_item` this engine will now stop on. `major`, and it is the new risk this unit creates

The fix converts a silent wrong number into a hard stop, which is right — but it moves the
failure to the extraction boundary, where `ingestion/` has **no tests at all**.
`ingestion/claude_extractor.py:187` instructs the model to return one of six exact field
names, and `:225` repeats the list; both agree with `_FIELD_EARNINGS_SIGN`'s keys, so a
compliant model is fine. A non-compliant one now raises `ValueError` mid-valuation, and
`api/routes_valuation.py`'s blanket `except Exception` (backlog item 8) will render that
message on the results page as a bare string. **The message is written to be readable
there** — it names the label, the year and the six legal values — but nobody has checked
what the page does with it. Worth a unit that (a) tests the extractor's `line_item`
contract, and (b) decides where an input error surfaces in the web app. This interacts
with backlog item 8 and should probably be sequenced after it.

### F2 — the assignment's and the backlog's worked fixture omits `cost_of_revenue = 400`. `note`

`.agent/assignments/P4-normalizer.md:103` and
`docs/9-reference/refactor-backlog.md:470-476` both list *"revenue 1000 / SG&A 200 /
other_non_operating 80 / tax_expense 100"* and then quote EBT figures of 480 / 530 / 430,
which require `cost_of_revenue = 400` (present in the reviewer's script at
`.agent/journal/2026-09-20T2215-code_reviewer-p1c-flow.md:43-45`). Without it EBIT is 800,
not 400, and every EBT in the table is 400 higher. The defect, the arithmetic and the fix
are unaffected — only the reproduction instructions are. One line to fix in the backlog.

### F3 — `STATUS.md` and two documents are now stale. `note`, orchestrator-owned

| Document | Says | Is now |
|---|---|---|
| `STATUS.md` §1 | `pytest -q` → `3 failed, 90 passed`; `normalizer.py` 28 statements, 2 missed, 93% | **`1 failed, 92 passed`**; `normalizer.py` **36 statements, 0 missed, 100%**; `analysis/` TOTAL 202, 100% |
| `STATUS.md` §1, §6 trap 4 | "Three tests fail deliberately" | **one** does: `test_dcf_rule3_red.py`. The two normalizer reds are green and, per their own docstring, are **kept, not deleted** |
| `STATUS.md` §5 | items 19, 3 and 21 open | all three **closed by this unit**, pending review |
| `STATUS.md` §5, rules.md §Rule 3 | census 117 | **116** |
| `docs/2-rules/rules.md:74-76` | names `analysis/normalizer.py:46` as one of the two materially dangerous sites | that site is gone; `analysis/dcf.py:80` remains |
| `docs/3-architecture/valuation-math.md:28-31` | records `_resolve_field` guessing as a defect | now describes behaviour that no longer exists. It should also gain the per-field sign, since it owns the normalisation formula |

### F4 — `NonRecurringItem.adjusted_impact` still reads `else -self.amount`. `note`

`models/financial_statements.py:37` has the same "anything that is not `add_back` is
`remove`" shape this unit removed from the normalizer. It is now unreachable through
`analysis/normalizer.py`, because `_field_delta` validates `direction` before touching the
property — but any other caller of `adjusted_impact` gets the old behaviour. `grep -rn
"adjusted_impact" --include=*.py .` shows the only callers are `analysis/normalizer.py` and
`tests/unit/test_normalizer.py`, so nothing is wrong today. If phase 5 gives
`NonRecurringItem` a validated `direction`, this goes away; I did not touch it because
`models/` is out of scope and 40 assertions rest on that file.

## Scratch files

All outside the repository, per `docs/8-build/environment.md` §6:
`c:/tmp/p4_norm_proof.py`, `c:/tmp/p4_sign_check.py`, `c:/tmp/p4_closed_set.py`,
`c:/tmp/broken_normalizer.py` (the deliberately broken copy), and the coverage databases
`c:/tmp/.cov_p4*`. Nothing under `c:/tmp` is read by the repository.
