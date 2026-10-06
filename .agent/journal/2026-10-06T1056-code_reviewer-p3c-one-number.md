---
agent: code_reviewer
assignment: P3c-one-number
round: 1
verdict: approved
---

# Review of P3c-one-number, round 1

Programmer entry: `.agent/journal/2026-10-05T2244-programmer-p3c-one-number.md`

Diff reviewed: `git diff HEAD` (`d060007`) over the four files in scope — 183 insertions,
29 deletions. `git status --porcelain` lists those four files and nothing else, so the
scope is clean. `ingestion/claude_extractor.py` is byte-identical to `HEAD`
(161300 bytes, `sha256 ec77b4bc…`, `git diff HEAD -- ingestion/claude_extractor.py`
empty), as the lead measured.

## The guard checks

Over `api/routes_valuation.py cli.py templates/assumptions.html templates/valuation_result.html`.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | one hit, `cli.py:226` (`terminal_growth … else 0.025`). **Untouched** — it was `cli.py:205` at `HEAD` and only moved because the unit added a constant above it. Backlog item 90, explicitly out of scope |
| lookup with a fallback — `.get(k, 0)` | clean (the one hit is the decorator `@router.get("/assumptions", …)`) |
| bare or-default — `or ''` | five hits, `templates/assumptions.html:208, 214, 224, 230, 236` — `defaults.*_display or ''` in the new `placeholder`. **Answered in the entry** ("Rule 3 — what stops", last row): on the no-filing and error paths `defaults` is `{}`, so the field renders with **no suggestion**, not a fabricated one. No number is invented and none is submitted; the identical guard already stood on the "Derived Default" column |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` | one hit, `cli.py:760` — pre-existing (`HEAD:701`), not in any hunk |
| dict of functions keyed by data | clean |
| model client outside `ingestion/` | clean (`grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no match) |

`print_historical_fcff(financials: FinancialStatements, basis: str)` is the only
signature the unit changed: named, typed, required, one call site (`cli.py:1086`).
Rule 2 holds.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| the five ratio form fields, blank | **not "missing"** — blank reaches `derive_assumptions` as `None`, which derives from the filing and labels the result `derived` (or `substituted`). Nothing defaults to 0 | measured: untouched form → `operating_margin=None tax_rate=None da_pct_revenue=None capex_pct_revenue=None nwc_pct_revenue=None`, `revenue_growth_rates=[]`, and six `derived from the filing` / zero `supplied by the caller` on the result page |
| the same five, typed `0` | kept as `0.0`, labelled `supplied` | measured: `operating_margin='0'` → `0.0`; at `HEAD` the same input gave `None` and the derived price |
| the same five, non-numeric | **stops** (`float('abc')` → `ValueError`, rendered on the result page). It does not name which field — see F1. Nothing is guessed, so this is not a rule 3 defect |
| a year with no income or cash flow statement, `cli.print_historical_fcff` | prints the year and names the missing statement; no figure invented | measured: `2023  not extracted: cash flow statement`, matching the web's `2023 False ('cash flow statement',)` |
| `basis`, `print_historical_fcff` | required positional — the table cannot print without naming its basis | `cli.py:695` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | unchanged; the unit moves no money figure through a new path |
| percentages converted at the route boundary, once | yes — `float(x) / 100` once per field at `:650-654`; measured `operating_margin='20'` → `0.2`. `terminal_growth_rate / 100` untouched |
| falsy not treated as missing | **five such sites deleted, none added.** The remaining `rev_growth_list if rev_growth_list else []` (`:640`) is untouched context — F3 |
| layering | no import moved; `cli.py` imports no `api/`, no route imports `cli` |

## Done-criteria, re-run

Every row below is my own command on this machine, `ANTHROPIC_API_KEY= GEMINI_API_KEY=`
and `.venv/Scripts/python.exe`. "Before" is `git archive HEAD` exported to
`/c/tmp/cr_before` (no `git stash`). My scripts are at `/c/tmp/cr_p3c/`.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | untouched form = CLI price | equal, delta 0.0 | on the session fixture: page `$277.78`, `cli.main()` `$277.78`. The untouched form posts `''` for all six | yes |
| 1b | the rounding actually moved the price | $1.29 / 1.269% on its hand filing | my own hand filing (adjusted margin 4.2537%): blank → `28.858040823256875`, the figure the **old** form posted back (`4.3`) → `28.957323583093856`, **+0.344%**. Different filing, same defect | yes |
| 2 | the before tree differs | prefilled `value`s, six `supplied` | before tree: `operating_margin value='30.0'`, …, result page **6 × "supplied by the caller", 0 × "derived"**, and `operating_margin='0'` → `None` (item 6 live) | yes |
| 3 | no derived value in a `value` attribute | no match | `grep -n 'value="{{ defaults\.' templates/assumptions.html` → exit 1. The only `value=` left are four hidden fields and `terminal_growth_rate` (item 90) | yes |
| 4 | shown twice, column and placeholder | 6 of 6 | rendered: all six inputs have **no `value` attribute** and a placeholder (`30.0`, `20.0`, `3.0`, `7.0`, `1.5`, and the growth list); the "Derived Default" column block (`templates/assumptions.html:36-125`) is unchanged | yes |
| 5 | a typed `0` is kept | `0.0` | `operating_margin=0` → `ProjectionAssumptions.operating_margin == 0.0`, origin `supplied`, other five `derived` | yes |
| 6 | a blank field is `None` | `None` | all five `None` | yes |
| 7 | untouched form → `derived` | 6 of 6 | result page: 6 × "derived from the filing", 0 × "supplied by the caller" | yes |
| 8 | one typed → `supplied` | 1 and 5 | 1 × "supplied by the caller", 5 × "derived from the filing" | yes |
| 9 | the form says what blank and typing mean | three sentences | all three render on `GET /assumptions`; absent in the before tree | yes |
| 10 | CLI FCFF = web FCFF | equal | CLI `4,016 / 4,416 / 4,856` against `_historical_fcff_by_year(adjusted)` `4015.8 / 4415.8 / 4855.880352371935` — every year equal | yes |
| 11 | the CLI's figures changed, by how much | 2024 `+1.63` on its filing | on mine: 2024 raw `4855.8` → adjusted `4855.880352371935`, **delta `+0.0804`**; 2022/2023 delta `0.0`. Cause confirmed: 2024 effective tax rate `0.21000…` raw against `0.20598…` adjusted | yes |
| 12 | both entry points name the basis | one sentence, three places | identical sentence found on `GET /assumptions`, on `POST /valuation` and in real `cli.main()` output under the `HISTORICAL FCFF` banner; absent everywhere in the before tree | yes |
| 13 | an uncomputable year is reported | reported | CLI `2023  not extracted: cash flow statement`; web `2023 False ('cash flow statement',)` | yes |
| 14 | multi-line stop readable | three templates | `grep -rn "white-space" templates/` → `assumptions.html:14`, `upload.html:11`, `valuation_result.html:16` | yes |
| 15 | types | 5 errors in 2 files | `Found 5 errors in 2 files (checked 21 source files)` — 4 `analysis/projector.py`, 1 `api/routes_upload.py`. None added, none removed | yes |
| 16 | lint | 4, all `BLE001` | `Found 4 errors.`, all `BLE001` | yes |
| 17 | census | 64 | 64 | yes |
| 18 | route | 200 | 200. Write guard 48/48 | yes |
| 19 | the failing set, by name | 22, two groups | **before (my own `git archive HEAD` run): `1144 passed, 5 skipped`, failing set `{}`. After: `22 failed, 1124 passed, 3 skipped`.** `diff` of the two sorted `FAILED` lists = the 22, nothing else. Every name is in one of the programmer's two groups | yes |

On criterion 19 I checked the attribution rather than taking it:

- **Group B (20) is the helper's regex, not a changed message.** `/c/tmp/cr_p3c/v3.py`
  posts the same empty `/valuation` in both trees. Both render status 200 and the
  identical text `Error: No filing named: session_file, files and file_path are all
  empty.`; the only difference is `<div class="alert alert-error" style="white-space:
  pre-line">` against `<div class="alert alert-error">`, and
  `_session_route_helpers.error_text` returns `None` in the after tree and the full
  message in the before tree. The stop, its wording and its status are untouched.
- **Group A (2)** asserts the derived default is in the field's `value` attribute —
  exactly the prefill the user's decision of 2026-10-05 ("1a") removed. The figures are
  still on the page twice.

Both groups are `tests/` repairs and `tests/` is denied to the programmer.

The skip count moved between my runs (5 in the exported tree, 3 then 2 here). The
exported tree has no `10K_filings/`, and the lead reports a separate agent writing
`extractions/WMT.json` during my run. **I compared failing sets by name, not counts**, so
neither affects this review.

## Findings

### F1 — a non-numeric entry stops without naming which of nine fields was rejected · `minor`

**Evidence:** `api/routes_valuation.py:650` — `float(operating_margin)` raises
`could not convert string to float: 'abc'`, which the blanket `except Exception` renders
verbatim on the result page.
**Rule or document:** none. I considered rule 3 and it does not apply: the run **stops**,
no value is defaulted and no number is invented, so this is a message-quality defect, not
a guess. It is stopping, not silent. The shape is pre-existing for `risk_free_rate`,
`equity_risk_premium`, `beta_override` and `cost_of_debt_override`, and the assignment's
step 1 directs the unit to copy it; this unit extends it to five more fields, which is
why I record it rather than pass over it.
**What would fix it:** one typed helper, `_optional_percent(field: str, value: str) ->
float | None`, raising `ValueError(f"{field}: ...")`, used by all nine — the programmer's
own F2. A backlog item, not a change to this unit.

### F2 — the FCFF basis sentence is a literal in three files with nothing checking they match · `note`

**Evidence:** `cli.py:86-89` (`HISTORICAL_FCFF_BASIS`),
`templates/assumptions.html:314`, `templates/valuation_result.html:259`. I confirmed all
three render the same sentence by execution; nothing enforces that.
**Rule or document:** none broken today — rule 6 is satisfied, because all three say the
same true thing. A reword in one would break it silently.
**What would fix it:** the constant in `pipeline.py`, passed into both template contexts.
All three candidate homes are outside this unit's file scope, so the programmer recorded
it and stopped, which is the correct move. For the backlog.

### F3 — `revenue_growth_rates=rev_growth_list if rev_growth_list else []` · `note`

**Evidence:** `api/routes_valuation.py:640` — both branches are the same empty list.
**Rule or document:** none. Untouched context in this diff (it is three lines above five
sites the unit deleted) and not on the backlog, so I record it as the programmer did (its
F9) rather than as a finding against the unit.
**What would fix it:** delete the conditional. Backlog.

### F4 — on `GET /assumptions` the basis sentence says "the valuation used" before any valuation has run · `note`

**Evidence:** `templates/assumptions.html:314`, reached on a page that renders before
`POST /valuation`.
**Rule or document:** none. Substantively true — `assumptions_page` builds the table from
`normalised_financials` (`api/routes_valuation.py:449`) and the DCF later runs on the same
object — but the tense is one step ahead of the page.
**What would fix it:** "the same statements the valuation uses". Cosmetic; it should ride
along with F2's single constant rather than be edited in three places now.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 90 — terminal growth literal | `cli.py:226`, `api/routes_valuation.py:530`, `templates/assumptions.html:151` | no — `cli.py:205` only shifted to `:226` because lines were added above it. The assignment forbids touching all four literals |
| 88 — `assumptions` bare dict | `api/routes_valuation.py:699` (`assumptions["sources"]`) | no. User decision of 2026-10-05, "Accept until item 88" |
| 8 — blanket `except Exception` | `api/routes_valuation.py:451, 733`, `cli.py:1204` | no. The four `BLE001` lint errors are these |
| 5, 26, 82, 89, 94, 99 | `api/routes_valuation.py`, `cli.py`, `analysis/capm.py` | no |

I saw each of these and left them out.

The assignment cites one user decision, of 2026-10-05, "1a", quoted in full with the
option as it was put. It covers the six ratio inputs rendering empty with the derived
figure as placeholder, which is what the code does. I checked the citation is there and
reviewed those lines against the rules anyway — the decision changes the shape, not the
rules, and rules 3 and 6 are satisfied by it.

## Verdict

`approved`

The unit does what the assignment asks and nothing else: four files, no test touched, the
extractor byte-identical. The two defects it exists to close are closed by my own
measurement, not the programmer's — an untouched form now posts `''` and prices at full
precision (the web price equals the CLI's), a typed `0` survives as `0.0`, the result page
labels an untouched form `derived` six times where the before tree labelled it `supplied`
six times, and the CLI's FCFF table now equals the web's year for year and both name their
basis. The 22 failing tests are all this unit's subject or the one `tests/` helper regex;
I reproduced the empty before-set myself and proved the helper attribution by execution,
so the tester's repair is bounded and known. No finding cites a rule: F1 is `minor` and
F2-F4 are `note`s for the backlog, none of which blocks.
