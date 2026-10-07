---
agent: code_reviewer
assignment: P3d-invisible-year
round: 2
verdict: approved
---

# Review of P3d-invisible-year, round 2

Programmer entry: `.agent/journal/2026-10-07T1156-programmer-p3d-invisible-year-r2.md`
Round 1 review: `.agent/journal/2026-10-07T1150-code_reviewer-p3d-invisible-year.md`

Every measurement is mine, on Windows with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. **No repository file was mutated**: `/c/tmp/r2rev_sha_before.txt`
against `/c/tmp/r2rev_sha_after.txt` over the seven source files and `extractions/WMT.json`,
`diff` empty → `NO REPOSITORY FILE MUTATED`. No `git stash`. HEAD tree is a `git archive HEAD`
export at `C:\tmp\r2_head`; the working-tree copy is `C:\tmp\r2_after`, built from `git ls-files`
and verified sha256-equal to the repository. My probes are `C:\tmp\r2rev_probe.py`,
`C:\tmp\r2rev_probe2.py` and my pinned Walmart runner `C:\tmp\r2rev_wmt.py` — mine, not the
programmer's.

**The overall lead's ruling of 2026-10-07 binds me.** `models/financial_statements.py:108`
(`gross_margin`) and `:132` (`operating_margin`) are left out of my findings on that ruling,
with its two stated reasons (`templates/_statements.html:44`/`:86` render the same two
properties and `templates/` is out of scope; `analysis/projector.py` reads `operating_margin`
into the DCF). **I verified the citation is in the assignment, and I say here that I excluded
those two lines deliberately.** I do not re-open F1's width.

## The guard checks

Over the six files in scope, on **added lines only**, which is the test that matters:

```
git diff -U0 -- <six files> | grep "^+" | grep -E "if [^)]+ else 0(\.0)?\b|\.get\([^,]+, *[^)]+\)|\bor +(0|0\.0|''|\"\"|\{\}|\[\])|: *float *= *0\.0|\*\*kwargs|getattr\("
-> exactly two lines, cli.py:425 and cli.py:561, BOTH docstring prose quoting the defect
```

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | **clean in code.** Round 2 *removed* the one hit round 1 added (`cli.py:506`); the two remaining matches are docstring text — see N2 |
| lookup with a fallback — `.get(k, 0)` | clean in the diff |
| bare or-default — `or 0.0` | **clean in the diff.** `claude_extractor.py:2329`'s bare `or` is gone — F2 |
| money field defaulted to zero — `: float = 0.0` | none in the diff (the `models/` dataclasses are backlog item 1, untouched) |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean in the diff |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → exit 1, no hits |

## Rule 3, by reading — round 2's rows only

| Value | Stops or names it? | Evidence (my probe) |
|---|---|---|
| `net_income / revenue` in the CLI I/S table when `revenue == 0` | **names it, invents nothing.** Cell is 11 blanks; `  2023  not computable: net income margin, revenue is 0` under the table | probe F1; F1c fires once per affected year, two lines for two zero years |
| `target_years == []` in `_build_is_summary` | **means "no year"** → `'  (no data available)'`. At HEAD it meant the whole filing | probe F2, both trees |
| the balance sheet year the valuation reads, CLI | **named on the line** when it differs; absent when it does not | probe F3 / F3b |
| which side of the reconciliation has no I/S | **named, in the web's exact four-case phrase** | probe F4, char-equal |
| `gross_margin` / `operating_margin` at `revenue == 0` | still `0.0%` | `models/financial_statements.py:108`, `:132` — **excluded on the lead's ruling**, see above |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | unchanged — no figure crosses a unit boundary in round 2; Walmart byte-identical |
| percentages converted at the route boundary, once | untouched |
| falsy not treated as missing | **F2 removed the one site.** `if is_years:` / `if not reconciled:` / `if not financials.balance_sheets:` are list-emptiness tests where emptiness *is* the condition meant |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean; `analysis/projector.py` unchanged this round |
| `models/` imports nothing from this repo | clean; unchanged this round |

## Half one — F1 to F5, each verified by my own execution

**F1.** `_net_margin_cell` returns `" " * (w + 1)` at `revenue == 0`, else `_pct(...)`.
I checked the three things asked.
*No figure is invented*: probe F1, the cell is `'           '` — 11 spaces, zero digits.
*Alignment with the zero year in the MIDDLE of three*: I built 2022/2023/2024 with 2023 at zero
revenue and printed the column start of every cell of all three margin rows:

```
gross  [(18,'      40.0%'), (29,'       0.0%'), (40,'      40.0%')]
ebit   [(18,'      40.0%'), (29,'       0.0%'), (40,'      40.0%')]
net    [(18,'      40.0%'), (29,'           '), (40,'      40.0%')]
```

The 2024 cell of the net row starts at column 40, the same column as the two rows above it.
`w + 1` is correct, and it is correct for the reason the entry gives: `_pct` emits `w` digits
**and** a `%`. *A table build cannot raise*: probe F1, F1b (zero revenue **and** a missing cash
flow statement in one filing), F1c (every year zero) and sections A, E, F3 all print
`RAISED: None`. **fixed.**

**F2.** `ingestion/claude_extractor.py:2329` is
`years = target_years if target_years is not None else financials.income_statement_years`.
I walked the callers myself rather than reading the entry's walk:
`_build_is_summary` ← `_pass2_prompt_pair:2393` ← `_run_nri_pass:2600` and `pass2_prompts:3086`.
`pass2_prompts` passes `_plan_target_years(plan)`, which returns `None` or `list(plan.target_years)`.
`grep -rn "FilingPlan(" --include=*.py .` gives **two** production constructions, both in
`plan_filings` (`:2809` `target_years=None`, `:2820` `target_years=None if fiscal_year == oldest_year
else (fiscal_year,)`) — never empty. `_run_nri_pass` takes `extract_financials`'s `target_years`,
whose production call sites (`api/routes_valuation.py:120`, `cli.py:1138`) do not pass it at all,
so it is the `None` default. No `target_years=[]` or `=()` anywhere in the repository, tests
included. Behaviour: probe F2, `[]` → `'  (no data available)'` after, the whole filing at HEAD;
`None` and `[2023]` byte-identical on both trees. **fixed, and the claim that no caller passes
an empty list is mine now too.**

**F3.** Probe F3, filing `LATEBS` (I/S 2024+2025, B/S 2025+2026): heading
`EXTRACTED BALANCE SHEET — FY2026 ($M)` followed by
`Shown: FY2026, the latest balance sheet extracted. The valuation below reads FY2025's balance
sheet — the latest year with an income statement — for net debt and the capital weights, so the
two are different sheets.` Probe F3b, a filing where the two years agree: `divergence line
present: False`. The line appears exactly when the two differ. **fixed** — with one caveat
I raise as N3.

**F4.** I rendered both sides and compared character by character, using the production phrase
from `templates/_statements.html:455` (`not extracted: {{ row.missing_statement }}`):

```
year 2023  web: 'not extracted: adjusted income statement'
           cli: 'not extracted: adjusted income statement'          IDENTICAL: True
year 2024  web: 'not extracted: raw and adjusted income statement'
           cli: 'not extracted: raw and adjusted income statement'  IDENTICAL: True
```

Both the one-sided and the both-sided case. At HEAD the same CLI call raised
`AttributeError: 'NoneType' object has no attribute 'ebit'`. **fixed.**

**F5.** Left, as the ruling directs. Probe E: `No income statement extracted for any year.`
is still followed by `2024  not extracted: income statement`. **withdrawn by the ruling** — the
overall lead records it; it is not this unit's to close.

## Half two — all fifteen done-criteria, re-run on my own scratch trees

| # | Criterion | I measured | Agree? |
|---|---|---|---|
| 1 | old behaviour reproduced | HEAD tree, my probe: `years : [2023, 2025]`, `income_statement_years present: False`, 2024 in no CLI table, no web row (`C` lists 2023 and 2025 only), no reconciliation line | **yes** |
| 2 | year visible in the CLI | `  2024  not extracted: income statement` from `print_historical_fcff` and from the statements block | **yes** |
| 3 | year visible on the web page | `row year=2024 is_computable=False missing=('income statement',)` | **yes** |
| 4 | both entry points say the same thing | FCFF: `not extracted: income statement` on both. Reconciliation: now char-identical too — F4 | **yes** |
| 5 | projection refuses **by name** | `type: ValueError`; names `revenue`, fiscal year 2024, both year sets and the remedy. **Not an `AttributeError`.** HEAD, same call: no stop, `[0.19999999999999996] × 5` | **yes** |
| 6 | every reader visited | my own enumeration `grep -rn "\.years\b\|income_statement_years" --include=*.py . \| grep -v "^./tests/"` matches the entry's 13-row table; the new reader `cli.py:647` is declared | **yes** |
| 7 | `latest_year` message true when it prints | `years = [2024]` (non-empty; `[]` at HEAD) and `FinancialStatements for 'BSONLY' holds no income statements, so there is no latest year.` — true, the property reads the narrow set | **yes** |
| 8 | **Walmart does not move** | **my own** runner, `pipeline.fetch_price_data` replaced by a seeded stub (`default_rng(20261007)`, 60 monthly obs, `current_price=100.0`), no network, one session file outside both trees. Both trees: **386 lines, `diff` exit 0**, `Implied Share Price: $ 655.03` on each. (My stub differs from the programmer's, so my figure is not his $15.42 — identity across trees is the test, and it holds) | **yes** |
| 9 | no figure moves where every year has an I/S | criterion 8 on `WMT.json` (`years == income_statement_years`), plus the probe filing's 2023 and 2025 FCFF rows identical in my two probe outputs | **yes** |
| 10 | types ≤ 5 in 2 files | assignment's command: **`Found 2 errors in 2 files (checked 21 source files)`** — `analysis/projector.py:395`, `api/routes_upload.py:28`. Role-card command: same 2, 20 files | **yes, 3 better** |
| 11 | lint 4, all `BLE001` | **`Found 4 errors`**: `api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106`. Run after my last write | **yes** |
| 12 | census 64 or fewer | the `rules.md:102` grep: **64 at HEAD, 64 after.** No code site added; one removed in `cli.py`, which the grep's four directories do not cover | **yes** |
| 13 | route 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` → **200** | **yes** |
| 14 | failing set by name | Full suite, **both trees, my own runs.** Working tree: `2 failed, 1224 passed, 2 skipped`. HEAD scratch: `2 failed, 1220 passed, 6 skipped`. **Failing set by NAME identical**: `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`. Gate form on the working tree: **`1224 passed, 2 skipped`, failing set empty.** The 4 passed/skipped gap is the scratch tree lacking `extractions/` and `10K_filings/`, not in git — not a state change | **yes** |
| 15 | **neither dead branch deleted, both reachable** | **Both halves mine.** Present: `inspect.getsource` of `cli.print_historical_fcff` and `rv._historical_fcff_by_year` both contain `missing.append("income statement")`; `git diff -U0` matches neither as `+` or `-`, so both are unchanged context. Reachable: both fired for 2024 in probe sections B and C | **yes** |
| — | write guard | `.claude/check_guard.py` → `48/48 guard cases correct` | **yes** |

**Criteria 8, 11, 12 and 14 — the four a late edit moves — were re-measured by me after round 2's
last edit and all four hold.** Criterion 15, the trap, holds on both halves.

## My own judgement on the blank cell

**Asked: is a blank cell plus a named line under the table an honest answer to rule 3, or does it
repeat the defect it was meant to repair? It is honest, and here is why, not just that.**

Rule 3 asks two things of a value that is not there: do not put a number in its place, and name
it. Both are met, and the second is met better than anywhere else in this table.

*No number.* The cell holds eleven space characters. There is nothing for a reader to misread as
a measurement. That alone separates it from the defect: `0.0%` was a figure, and a figure that a
company genuinely earning nothing would print identically. A blank is not a figure.

*Named.* The line under the table carries the **year**, the **field** and the **reason** —
`2023  not computable: net income margin, revenue is 0`. The cash flow blanks that the round 1
programmer reported as its own finding 1 carry the year and the statement, not the field. So this
is the same *shape* as that finding but strictly more information, and the information added is
exactly the part rule 3 asks for. A reader's position is strictly improved: before, they read a
number and could not know it was fabricated; now they read nothing and are told, two lines down,
which figure is absent and why. Information went up. It cannot be the same defect.

*The alternative was measured, not assumed.* Round 1's suggested `"not computable: revenue is 0"`
in the cell is 29 characters in a 10-wide column. I confirmed the column grid myself: putting it
in the cell destroys the alignment of every later year of that row. The words were kept and moved
to the one place they fit. That is a reason, and the entry argues it as one — not from a target
number.

*What I do not call honest, and it is not this unit's to fix.* One line above the blank,
`EBIT  Margin` prints `0.0%` for that same year, and it is just as fabricated. The table now
speaks two languages about one year. That is real, and it is **the overall lead's recorded,
reasoned acceptance of 2026-10-07** bound to `models/financial_statements.py:108` and `:132`, with
`templates/_statements.html:44`/`:86` and the DCF path as its two stated facts. I leave those
lines out of my findings, as instructed, and I record that the partial repair is visible to a
reader in exactly the way the ruling predicted.

## Findings

All four break no rule in `docs/2-rules/rules.md`. **None blocks.**

### N1 — the table helper and its absence line are a pair nothing enforces · `note`

**Evidence:** probe2 section H — `cli._print_income_statement_table(z, [2023], 10, 18)` called
alone prints `  Margin` followed by a blank and **no reason anywhere**.
**Rule or document:** none. One call site today (`print_extracted_financials`), and both
docstrings say they belong together.
**What would fix it:** a second caller is the moment this bites; until then it is a name for the
next reader to notice.

### N2 — two new docstring lines match the rule 3 census grep · `note`

**Evidence:** the `rules.md:102` grep widened to `cli.py` gives **65 at HEAD, 67 after**; the two
new hits are `cli.py:425` (`read \`… if … .revenue else 0\` until round 2 of`) and `cli.py:561`
(``same `if self.revenue else 0.0` at …``), both prose.
**Rule or document:** none — the official census (four directories) is 64 → 64 and `cli.py` is
outside it, so criterion 12 passes. But a future unit that widens the census to `cli.py` will
count two comments as defects.
**What would fix it:** quote the shape without the literal `else 0`, e.g. "a conditional zero".

### N3 — the F3 divergence line can name a balance sheet that does not exist · `note`

**Evidence:** probe2 section G — a filing with I/S 2024+2025 and its only balance sheet on 2026
prints `The valuation below reads FY2025's balance sheet …` while
`g.get_balance_sheet(g.latest_year)` is `None`.
**Rule or document:** none — no figure is invented, and `pipeline.py:182` then stops and names the
missing balance sheet, which is the rule 3 answer. The sentence is a display line that over-asserts.
**What would fix it:** say "reads FY2025's balance sheet, if one was extracted", or test
`get_balance_sheet(max(is_years))` before naming it.

### N4 — "revenue is 0" asserts a measurement the code cannot distinguish from an absence · `note`

**Evidence:** `cli.py:_print_net_margin_absences` prints `revenue is 0`;
`models/financial_statements.py:98` is `revenue: float = 0.0`, so an unextracted revenue reaches
that branch as a zero.
**Rule or document:** none against this unit — the dataclass default is backlog item 1 in a line
this unit did not touch, and the new line prints no figure either way. It is the message's wording.
**What would fix it:** "the extracted revenue for this year is 0" rather than "revenue is 0".

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 (census) | `models/financial_statements.py:108`, `:132` | **no**, and **excluded on the overall lead's ruling of 2026-10-07**, whose citation I checked is in the assignment |
| 1 (census) | `cli.py:506` → `_net_margin_cell` | **yes, and now removed** — this was round 1's F1 |
| 1 (census) | the `: float = 0.0` fields, `analysis/projector.py:73, 357` | no — unmoved; census 64 on both trees |
| 8 (blanket `except Exception`) | `api/routes_valuation.py:463`, `:745`, `cli.py:1411` | no — these are the four `BLE001` |
| 41 (unreachable `0.05`) | `analysis/projector.py` | no |
| 28 | `api/routes_upload.py:28` | no — the remaining mypy error, out of scope |
| the 17 blank cash-flow cells | `cli.py:_print_cash_flow_table` | relocated in round 1; whitespace, not a number, and each such year is named below the table. Already recorded, and the round 1 review accepted it |

One more I saw and am **not** charging to this unit: `cli.py:845` iterates `raw.years` while
`api/routes_valuation.py:329` iterates `sorted(set(raw.years) | set(adjusted.years))`, so a year
present only on the adjusted side would reach the page and not the CLI. `git diff` shows
`years = raw.years` as **unchanged context**, `normalize_financials` preserves the year set, and
the comment the unit added scopes its parity claim to "for the same year", which is accurate. It
belongs in the backlog, not here.

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| F1 | **fixed** | `_net_margin_cell` + `_print_net_margin_absences`. No figure invented; alignment holds with the zero year in the middle of three (`w + 1` is right, and right for the stated reason); no table build raises in any of my five shapes. The two margin rows above still print `0.0%` — left on the lead's ruling, which I checked and honoured |
| F2 | **fixed** | `target_years if target_years is not None else …`. I walked every caller myself: both production `FilingPlan` constructions are in `plan_filings` and give `None` or a one-element tuple; no `target_years=[]` exists anywhere, tests included |
| F3 | **fixed** | The line prints when the shown sheet is not the one the valuation reads, and not when it is. See N3 for its one over-assertion |
| F4 | **fixed** | Words made identical rather than the comment softened, which is the stronger of the two options the finding offered. Char-equal on both the one-sided and the both-sided case |
| F5 | **withdrawn** | By the overall lead's ruling of 2026-10-07 ("Leave it. I record it"). Still present, unchanged, and correctly left |

## Verdict

`approved`

**Nothing blocks.** All five round 1 findings are answered, and the four that the orchestrator
asked me to verify by execution rather than by reading — F1's blank cell and its alignment, F2's
caller walk, F3's divergence line, F4's character-identical wording — hold under my own probes on
my own scratch trees. All fifteen done-criteria hold after round 2's late `cli.py` edit, including
the four a late edit moves (Walmart byte-identical under my own pinned market series, lint 4 all
`BLE001`, census 64 → 64, failing set compared by name and identical) and criterion 15, the trap:
both dead branches are unchanged context in `git diff` and both fired for fiscal year 2024 in my
probe. The blank cell is an honest answer to rule 3 — it emits no figure and names the year, the
field and the reason, which is more than the cash flow blanks beside it say — and the one place
the table still lies, `Gross Margin` and `EBIT Margin` at zero revenue, is the overall lead's
recorded acceptance with its citation present in the assignment, so I left those two lines out of
my findings and say so here. My four findings are all `note`: a helper pair nothing enforces, two
docstring lines that will trip a future census grep, one display sentence that can name a balance
sheet that does not exist, and one that calls a defaulted zero a measured one. None cites a rule;
none needs a round 3. The unit is ready for the tester.
