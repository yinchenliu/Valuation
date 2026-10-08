---
agent: tester
assignment: P14g-unit-statement-pages-tests
round: 1
status: complete
files_touched: [tests/unit/test_p14a_units.py, tests/unit/test_p14g_unit_statement_pages.py]
verdict: pass
---

# P14g-unit-statement-pages-tests — the page-before rule is locked by hand arithmetic, the two checks are proved to hold one rule, and four mutations of it die

## What I did

Repaired the two tests that asserted the **old**, narrower rule — neither deleted, neither
weakened — and wrote `tests/unit/test_p14g_unit_statement_pages.py`: 26 test functions, 113
collected cases, 70 `assert` statements. Every expected value was worked out before the code
ran, from one of exactly three sources: the rule written as arithmetic
(`f(S) = S | {p-1 : p ∈ S, p > 1}`), a closed-form identity that holds for every input, or a
line read off PDF page 44, 45, 46 or 47 of `10K_filings/WMT/Walmart Inc._10-K_2024-01-31_
English.pdf` with `pdfplumber`. **No assertion in this unit came from the code's output.**

I then attacked my own suite with the four mutations the assignment names, each in a scratch
tree under `C:\tmp\p14gt\tree`, never in the repository. **All four died.** Coverage was
measured and intersected with `git diff -U0`, not estimated.

I also found and locked two refusal branches of `_unit_statement_failures` that no test
reached and that this unit makes newly reachable: the page before the figures may have **no
text layer at all** (it never could before P14g, because every allowed page used to carry a
printed figure), and an allowed page may lie **beyond the end of the PDF**. Both stop and
name the page. That took the function from 17/19 statements and 8/10 branches to 19/19 and
10/10.

## The second trap — recorded here, asserted nowhere

P14g widens, by one page, the window in which a model may cite **another table's** unit
statement: a `(in thousands)` note header on the page before a `(in millions)` income
statement is refused at `HEAD` and **accepted** after this unit, and every money figure would
then be divided by 1,000. Check B1 cannot see it, because B1's expected scale is itself read
from `units`. The programmer measured it and the reviewer rebuilt it independently; the
reviewer also established the fact that makes it a widening rather than a new hole — the same
wrong answer is already accepted at `HEAD` when the note and the figures share one page.

**I wrote no assertion about that answer.** A test asserting `len(failures) == 0` for it would
lock the hole as correct and turn red the day the unit that closes it lands. It is recorded
here and in finding F1 below, which is where it belongs. I did not re-run the probe either:
re-measuring it would only have tempted me to write the number down.

## Done-criteria

Every command carried `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and `.venv/Scripts/python.exe`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Every expected value hand-sourced | **pass** | **72 `assert` statements in scope** (70 new + 2 repaired). **0 came from the code's output.** Each one's source is in the table under "Expected values" |
| 2 | The two red tests repaired, not deleted | **pass** | `git diff -- tests/unit/test_p14a_units.py`: two assertion lines changed and nothing else. `assert allowed["share_units"] == {29, 30}`, `len(failures) == 1`, `"'units'" in msg` and `"page 35" in msg` are all **context lines** in the diff — untouched. Both tests green: `-m pytest -q tests/unit/test_p14a_units.py::test_unit_statement_pages_allowed_constrains_pages tests/unit/test_p14a_units.py::test_unit_statement_failures_stops_when_page_outside_allowed` → `2 passed` |
| 3 | `_pages_and_page_before` covered | **pass** | page 1 (`[page-1]`), the empty set (two tests), page 0 never produced (60 cases, plus the whole 1..60 range at once), plus the `p+1` negative in the identity test |
| 4 | The two checks proved to read one rule | **pass** | `test_both_unit_scale_checks_accept_the_same_statement_pages`, 12 cases: the same PDF and the same answer through **both** checks, asserting each check's verdict against a hand-derived expectation **and** against the other. Plus `test_both_checks_read_the_one_function_that_holds_the_rule`, which fails if either check spells the rule itself again |
| 5 | The real Walmart fiscal 2024 case | **pass** | `test_walmart_fiscal_2024_header_on_the_page_before_its_figures_is_accepted`: allowed `{45, 46}`, `_unit_statement_failures(...) == []`. The figure pages are unchanged: `test_walmart_fiscal_2024_splits_its_income_statement_across_a_page_break` asserts page 46 still prints `Net sales $ 642,637 $ 605,881 $ 567,762` and page 45 prints no `Net sales` at all |
| 6 | The new page is still checked | **pass** | `test_walmart_fiscal_2024_the_newly_allowed_page_is_still_checked`: `(Amounts in millions)` cited on page 45 is refused, `was not found on page 45 … as a whole printed statement`, and the test asserts the refusal is **not** the pages-allowed one |
| 7 | The surviving refusals | **pass** | five, each with its reason — see "The refusals that survive" |
| 8 | Four mutations, each killed | **pass, 4 of 4 killed, 0 survived** | the table under "Mutations" |
| 9 | Coverage of what the unit added | **pass** | 71 added lines; 4 executable statements among them; **4 covered, 0 missed**. Commands and per-function numbers under "Coverage" |
| 10 | The gate | **pass** | `-m pytest -q --ignore-glob="*_rule3_red.py"` → **1370 passed, 2 skipped, 0 failed** in 141.90s. 1257 + my 113 = 1370, exactly the criterion's arithmetic |
| 11 | The failing set | **pass, empty** | the gate printed no `FAILED` and no `ERROR` line. Compared by name, not by count |
| 12 | Lint | **pass** | `-m ruff check .` → **4 errors, every one `BLE001`** (`api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106`). **Run after my last write — and it caught me.** See below |
| 13 | The write guard | **pass** | `.claude/check_guard.py` → **48/48 guard cases correct** |
| 14 | No LLM call was made | **pass** | every command above carried `ANTHROPIC_API_KEY= GEMINI_API_KEY=`, so no client could be constructed with a key. No test imports a model client; every PDF is read with `pdfplumber`; every synthetic PDF is bytes written by `tests/unit/_text_pdf.write_text_pdf`. The only network-capable library in the suite, `yfinance`, is not reached by any test I wrote |

**Criterion 12 caught me, which is the point of running it last.** My first `ruff check .` after
writing the tests reported **6** errors, not 4: two `ISC004` (unparenthesised implicit string
concatenation inside a `parametrize` tuple) in
`tests/unit/test_p14g_unit_statement_pages.py:700` and `:705` — my own file, exactly the
defect the criterion's history section warns about. I parenthesised both and re-ran: 4, all
`BLE001`. Had I linted beside the edit that prompted it, I would have reported 4 and been
wrong.

The three facts the assignment told me to re-measure and report any disagreement on:

| Fact | My result | Agrees with the assignment? |
|---|---|---|
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → **2 errors in 2 files, 21 checked** (`analysis/projector.py:395`, `api/routes_upload.py:28`) | yes |
| census | the grep at `docs/2-rules/rules.md:102` → **64** | yes |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` → **200** | yes |

I did not re-run the `HEAD` baseline: the assignment's "1257 tests, 2 failed" is confirmed by
arithmetic instead — the two tests it names were the only two failing, I repaired exactly
those two, and 1257 + 113 new = 1370 passed with an empty failing set.

## I confirmed each diagnosis before acting on it

The assignment told me to. I derived both by hand from the rule, before running anything.

**`test_unit_statement_pages_allowed_constrains_pages`.** The fixture's income rows cite
page 29 (revenue, cost_of_revenue, gross_profit, sga, operating_income, tax_expense,
net_income) and page 30 (diluted_shares); `depreciation_amortization`, `cfo` and `capex` cite
page 32 and are **not** in `_INCOME_STATEMENT_LINE_FIELDS`, so `income_pages = {29, 30}`.
`f({29,30}) = {29,30} | {28,29} = {28, 29, 30}`. The old assertion `{29, 30}` is the pre-P14g
rule. **Confirmed — repaired to `{28, 29, 30}`.**

`share_units = {units.page} | f(diluted_pages) = {29} | f({30}) = {29} | {29,30} = {29, 30}`.
**The second assertion is already correct and I left it exactly as it was.** It is the one line
in the suite that locks the criterion-4 decision — that the `units` page, an already-resolved
*statement* page, is **not** widened — so page 28 must not appear in it. The assignment cites
that assertion as `:291`; in the file as it stands the comment is at `:291` and the assertion
at `:292`. Same assertion, off-by-one in the citation only; I changed neither.

**`test_unit_statement_failures_stops_when_page_outside_allowed`.** Income rows all cite page
29, so `income_pages = {29}` and `f({29}) = {28, 29}`, printed as `[28, 29]`. **Confirmed —
repaired to `"the pages allowed are [28, 29]"`.** `len(failures) == 1`, `"'units'" in msg` and
`"page 35" in msg` all still hold by the same derivation: page 35 is six pages past the
figures and `35 ∉ {28, 29}`, so the stock-award table's `(in millions)` is still refused. I
changed none of the three.

## Expected values — testers only

**Never "what the code returned".** Every row below names where the expected side came from.

### Source A — the rule written as arithmetic: `f(S) = S | {p-1 : p ∈ S, p > 1}`

| Assertion | Expected | Hand arithmetic |
|---|---|---|
| `f(∅)` | `∅` | `∅ \| ∅` — nothing in, nothing out |
| `f({1})` | `{1}` | 1 is not > 1, so no predecessor. **This is the page-1 edge** |
| `f({2})` | `{1,2}` | `{2} \| {1}` |
| `f({1,2})` | `{1,2}` | `{1,2} \| {1}`; the predecessor is already there |
| `f({46})` | `{45,46}` | `{46} \| {45}` — Walmart fiscal 2024 |
| `f({1,46})` | `{1,45,46}` | `{1,46} \| {45}`; 1 contributes nothing |
| `f({5,6,7})` | `{4,5,6,7}` | `{5,6,7} \| {4,5,6}` |
| `f({3,10})` | `{2,3,9,10}` | `{3,10} \| {2,9}` — two separate statements |
| `f({2,100})` | `{1,2,99,100}` | `{2,100} \| {1,99}` |
| `allowed["units"]`, rows on 46 | `{45,46}` | income line pages `{46}`; `46-1=45` |
| `allowed["units"]`, rows on 46, cash flow on 52 | `{45,46}`, and `52 ∉`, `51 ∉` | `_INCOME_STATEMENT_LINE_FIELDS` excludes the five cash-flow fields, so page 52 never enters the set and so its predecessor never does either |
| `allowed["share_units"]`, units p20, diluted p22 | `{20,21,22}`, and `19 ∉` | `{units.page}=20` is **not** widened; `f({22})={21,22}`; `{20} ∪ {21,22}` |
| `allowed["units"]`, same answer | `{21,22}` | income pages `{22}`; `22-1=21`. Page 20 is a statement page, not a figure page |
| `allowed["units"]`, rows 30, diluted 31 | `{29,30,31}` | income pages `{30,31}`; predecessors `{29,30}` |
| `allowed["share_units"]`, same | `{30,31}` | `{30} ∪ f({31}) = {30} ∪ {30,31}` |
| `allowed["units"]`, no income rows | `∅`, message `the pages allowed are []` | `f(∅)=∅`. **No fallback to the cited page** |
| `allowed["units"]`, rows on 50 | `{49,50}` | `{50} \| {49}` |
| `allowed["units"]`, rows on 3 | `{2,3}` | `{3} \| {2}` |
| repaired `allowed["units"]` | `{28,29,30}` | derived above |
| repaired `"the pages allowed are [28, 29]"` | `[28,29]` | derived above |
| the 12 one-rule grid cases | accept iff `Q ∈ f({P})` | one line of arithmetic per case, in the parametrize comment |
| B1's message, rows p3, statement p1 | `no unit statement on page 3 or 2` and 2 failures | `f({3}) = {2,3}`, and the docstring states one failure per `(page, kind)`: money figures and share count |

### Source B — closed-form identities, true for every input, no worked example needed

| Assertion | Identity |
|---|---|
| `0 ∉ f({p})` and `min f({p}) ≥ 1`, for every `p ∈ 1..60`, and for `f({1..60})` | a PDF's first page is page 1. The `p > 1` guard is the only thing keeping 0 out: without it `f({1}) = {0,1}` |
| `S ⊆ f(S)` | a page the figures are printed on is never taken away |
| `f(S) ⊆ S ∪ {p-1 : p ∈ S, p > 1}` | nothing but a predecessor is ever added |
| `\|f(S)\| ≤ 2\|S\|` | at most one page added per page |
| `p+1 ∉ f(S)` whenever `p+1 ∉ S` | the page **after** is never admitted. A unit statement printed below the table it governs is a different table's |
| `f` does not mutate its argument | it is pure; `_unit_statement_pages_allowed` passes two different sets from one answer |
| in the grid: `unit_statement_accepted == b1_accepted` | the unit's whole objective. Each side is also asserted against its own hand-derived expectation, so the test cannot pass by both checks being wrong together |

### Source C — figures read off a filing page

`10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf`, read with `pdfplumber` before any
test was written (`C:\tmp\p14gt\read_wmt.py`), and re-asserted inside the suite.

| Assertion | Expected | Filing page |
|---|---|---|
| page count | `147` | the PDF |
| page 45's last four text lines | `Walmart Inc.` / `Consolidated Statements of Income` / `Fiscal Years Ended January 31,` / `(Amounts in millions, except per share data) 2024 2023 2022` | PDF page 45 |
| `"Net sales" not in` page 45 | the header page carries no figure of the statement | PDF page 45 |
| page 46 holds `Net sales $ 642,637 $ 605,881 $ 567,762` | the statement's first data row, fiscal 2024 revenue 642,637 | PDF page 46, 2nd text line |
| page 45's scale statements | exactly `['(Amounts in millions, except per share data)']` | PDF page 45 |
| page 46's scale statements | exactly `['(Amounts in millions)']` — the **Comprehensive Income** header, a different statement | PDF page 46 |
| `(Amounts in millions)` cited on page 45 is refused | page 45 does not print that group; `unit_statement_on_page` compares **whole** groups | PDF page 45 |
| `(in thousands)` cited on page 46 is refused | page 46 prints only `(Amounts in millions)` | PDF page 46 |
| page 44 prints no scale statement | so a model citing it reaches for something not there | PDF page 44 |
| page 47 prints `(Amounts in millions)` | the balance sheet's header, the page **after** the figures | PDF page 47 |

### Where no expected value came from

Not one assertion was taken from a run, from a `.pkl`, from `extractions/WMT.json`, or from
another test's assertion. **Count: 0 of 72.**

## The refusals that survive

Five, each with the reason the message gives. Four are on the real filing.

| Case | Cited | Refused for | Test |
|---|---|---|---|
| **a** two pages before the figures | `(Amounts in millions, except per share data)` p.44 | `cites page 44 … the pages allowed are [45, 46]` — `44 ∉ f({46})` | `…refusals_that_must_survive_the_widening[two-pages-before]` |
| **b** the page after the figures | `(Amounts in millions)` p.47 | `cites page 47 … the pages allowed are [45, 46]` — `f` never adds `p+1` | `…[the-page-after]` |
| **c** text not printed on the cited page | `(in thousands)` p.46 | `was not found on page 46, the page it cites, as a whole printed statement` | `…[text-not-printed-there]` |
| **d** the newly-allowed page, wrong text | `(Amounts in millions)` p.45 | `was not found on page 45 …`, and the test asserts it is **not** refused on pages-allowed grounds | `…the_newly_allowed_page_is_still_checked` |
| **e** `share_units` two pages before the share count | p.44 | `cites page 44 … the pages allowed are [45, 46], the 'units' page, the pages the diluted share count's printed lines cite, and the page before each of those` | `…share_units_two_pages_before_is_refused` |

Plus the stock-award page six pages away, which the repaired
`test_unit_statement_failures_stops_when_page_outside_allowed` still refuses.

## Rule 3 — what stops, and what does not

Every value `_unit_statement_pages_allowed` reads, and every refusal branch of
`_unit_statement_failures`. **There is no "defaults to" row.**

| Value read | If it were missing | Locked by |
|---|---|---|
| `data["historical_years"]` | **stops**, `KeyError` naming `historical_years` | `test_pages_allowed_stops_when_historical_years_is_missing` |
| `entry[field]` for an income field | **stops**, `KeyError` naming `operating_income` | `test_pages_allowed_stops_when_an_income_field_is_missing_from_a_year` — an absent key must not read as `[]`, which means "the filing prints no such row" |
| `line["page"]` | **stops**, `KeyError` naming `page` | `test_pages_allowed_stops_when_a_printed_line_has_no_page` |
| `data["units"]` | **stops**, `KeyError` naming `units` | `test_pages_allowed_stops_when_the_units_statement_is_missing` |
| `data["units"]["page"]` | **stops**, `KeyError` naming `page` | `test_pages_allowed_stops_when_the_units_statement_has_no_page` |
| the `pages` argument, when empty | **no page is allowed and the statement is refused** — `the pages allowed are []`. Never a fallback to the page the statement cites | `test_an_answer_with_no_income_rows_allows_no_page_and_the_statement_is_refused` |
| the text layer of a newly-allowed page | **stops**, `cannot be confirmed, because page 2 has no text layer; it was not looked for` — names the page | `test_a_newly_allowed_page_with_no_text_layer_is_not_confirmed`. **This branch was unreachable before P14g**: every allowed page used to carry a printed figure, so it always had text. No test reached it until now |
| an allowed page past the end of the PDF | **stops**, `cites page 50, but the PDF has 3 pages` — names both | `test_an_allowed_page_beyond_the_filing_is_refused`. Also previously uncovered |

**Every stop path of `_unit_statement_failures` is now locked: 10 of 10 branches, measured.**
There is no stop path in this unit that I could not reach, and no branch that defaults instead
of raising.

## Mutations

Each applied to `C:\tmp\p14gt\tree\ingestion\claude_extractor.py` — a `git archive HEAD`
export with the working-tree file copied over it — and reverted from a pristine copy after
each run, with a byte-equality assertion. **The repository file was never touched**: its
sha256 is `d4a4783247f493460bd8656b2fd55f74761b6d87c9c039187d0b773be2d5cb68` before my first
command and after my last, the same digest the programmer and the reviewer recorded.
`extractions/WMT.json` is `c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675`
on both sides. `git stash` was not used.

Command, for each: `.venv/Scripts/python.exe C:\tmp\p14gt\mutate.py <name>`, which runs
`-m pytest -q --no-header -p no:cacheprovider tests/unit/test_p14g_unit_statement_pages.py
tests/unit/test_p14a_units.py` in the scratch tree. Baseline there: **157 passed**.

| # | Mutation | Result | Test **names** that went red |
|---|---|---|---|
| **M1** | `return pages` — the old defect, no page before | **killed.** `24 failed, 133 passed`; **15** distinct names | `test_p14a_units::test_unit_statement_pages_allowed_constrains_pages`, `…::test_unit_statement_failures_stops_when_page_outside_allowed`, `test_pages_and_page_before_is_each_page_and_its_predecessor[*]`, `test_units_allowed_is_the_income_pages_and_the_page_before_each`, `test_units_allowed_ignores_the_cash_flow_statement_pages`, `test_share_units_widens_the_share_count_pages_but_not_the_units_page`, `test_share_units_allowed_when_the_share_count_sits_on_its_own_page`, `test_a_newly_allowed_page_with_no_text_layer_is_not_confirmed`, `test_an_allowed_page_beyond_the_filing_is_refused`, `test_both_unit_scale_checks_accept_the_same_statement_pages[*]`, `test_walmart_fiscal_2024_header_on_the_page_before_its_figures_is_accepted`, `test_walmart_fiscal_2024_the_newly_allowed_page_is_still_checked`, `test_walmart_fiscal_2024_refusals_that_must_survive_the_widening[*]`, `test_walmart_fiscal_2024_share_units_two_pages_before_is_refused`, `test_walmart_fiscal_2024_refusal_message_states_the_rule_it_applied` |
| **M2** | `pages \| {p-1 for p in pages}` — no `p > 1` guard, page 0 appears | **killed.** `67 failed, 90 passed`; **3** distinct names | `test_pages_and_page_before_never_produces_page_zero[*]`, `test_pages_and_page_before_is_each_page_and_its_predecessor[*]`, `test_pages_and_page_before_adds_at_most_the_predecessor_of_each_page[*]` |
| **M3** | `pages \| {p+1 for p in pages}` — the page **after** | **killed.** `36 failed, 121 passed`; **16** distinct names | the 15 of M1, plus `test_pages_and_page_before_adds_at_most_the_predecessor_of_each_page[*]` |
| **M4** | `elif unit_statement_on_page(printed, text):` → `elif True:` — stop checking the text once the page is allowed | **killed.** `2 failed, 155 passed`; **2** distinct names | `test_walmart_fiscal_2024_the_newly_allowed_page_is_still_checked`, `test_walmart_fiscal_2024_refusals_that_must_survive_the_widening[*]` (the `text-not-printed-there` case) |

**No mutation survived.** M4 is the thin one — two names — and it is the one that matters
most, because a widening that stopped checking the text would still satisfy criterion 2 and be
worthless. Both killers are on the real filing: the only way to kill it is to cite, on an
allowed page, a text that page does not print, and that case cannot be built without knowing
what a real page prints. The synthetic tests all print the statement on the page they cite, so
none of them can see this mutation. **Stated as a thinness rather than hidden**: if the two
Walmart tests ever skip (a machine without `10K_filings/WMT/`), M4 goes unguarded.

## Coverage

```
COVERAGE_FILE='C:\tmp\p14gt\.coverage' .venv/Scripts/python.exe -m pytest -q --no-header \
  -p no:cacheprovider --cov=ingestion --cov-branch \
  '--cov-report=json:C:\tmp\p14gt\cov_unit.json' --cov-report= \
  tests/unit/test_p14g_unit_statement_pages.py tests/unit/test_p14a_units.py
.venv/Scripts/python.exe C:\tmp\p14gt\cov_intersect.py C:\tmp\p14gt\cov_unit.json
```

`cov_intersect.py` parses the `@@` headers of `git diff -U0 -- ingestion/claude_extractor.py`
into the set of added line numbers and intersects it with coverage's `executed_lines` and
`missing_lines`. Measured from this unit's two test files alone — no other test file is in the
run, so nothing here is borrowed coverage.

```
added lines (git diff -U0)          : 71
  of which executable statements    : 4 -> [1479, 1499, 1674, 1710]
  covered                           : 4 -> [1479, 1499, 1674, 1710]
  missed                            : 0 -> []
branch arcs from an added line, taken : 0
branch arcs from an added line, missed: 0
```

The other 67 added lines are the docstring of `_pages_and_page_before`, comments, and the
**continuation** lines of two multi-line statements — `return {…}` at `:1532` (whose two
values the diff rewrote) and `_PAGES_ALLOWED_ARE = {…}` at `:1539` (whose two strings it
rewrote). Coverage attributes those to the statement's first line, and **both of those lines
are covered too**, so no changed statement is unexecuted.

| Function | Statements | Branches |
|---|---|---|
| `_pages_and_page_before` (**added** by this unit) | **1 / 1** | 0 / 0 recorded |
| `_unit_statement_pages_allowed` (changed) | **3 / 3** | 0 / 0 recorded |
| `_unit_statement_failures` (the check the rule feeds) | **19 / 19** | **10 / 10** |
| `_row_scale_failures` (check B1; two lines changed) | 54 / 76 | 25 / 36 |

**Functions: 3 of 3** that this unit added or changed are touched by a test in this unit.

**Branches, honestly.** coverage.py records **zero** branch arcs for `_pages_and_page_before`.
Its one conditional, `if page > 1`, lives inside a set comprehension, and on Python 3.14
comprehensions are inlined, so no arc is emitted — a `0/0` that would read as "fully covered"
and mean nothing. The two sides are covered **behaviourally** instead, and the proof is M2:
removing the guard kills three test functions, including 60 parametrised cases of
`test_pages_and_page_before_never_produces_page_zero`. A branch no report can see is still a
branch, and the mutation is the measurement.

`_row_scale_failures`'s 22 uncovered statements are B1's own message and failure paths, added
by `P14b-note-figures` and covered by `tests/unit/test_p14b_note_figures.py` (31 tests), which
is outside this unit and was not in the coverage run. Both lines this unit changed in it,
`:1674` and `:1710`, are covered.

## The two counts, with their units

- **Accuracy: 72 of 72 `assert` statements** match an expectation derived before the code ran
  — 70 new, 2 repaired. **0 of 72** came from the code's output, a `.pkl`, a cached extraction
  or another test's assertion. Executed as **113 collected test cases** in the new file plus
  the 2 repaired ones.
- **Coverage: 3 of 3 functions** this unit added or changed are touched by a test; **4 of 4
  executable added statements** covered, **0 missed**; **10 of 10 branches** of
  `_unit_statement_failures`; the one conditional inside `_pages_and_page_before` is
  unreportable as an arc and is covered by mutation M2 instead.

## Decisions, each with its reason

| Decision | Reason | Why this and not the alternative |
|---|---|---|
| The one-rule test runs **both** checks on one PDF and asserts each against its own hand-derived verdict, then against the other | criterion 4 asks for a test that fails if either check gets its own rule back | Asserting only `a == b` would stay green if both checks broke the same way |
| …**and** a source-shape test alongside it | the behavioural test cannot tell one rule from two identical copies, and two copies is exactly how item 114 happened — B1 gained "the page before" in P14b and the other check did not | A copy drifts on the next edit. The shape test names `_pages_and_page_before` as the single home and requires both of B1's page lines to read it |
| Added two tests beyond the assignment: the no-text-layer page and the page past the end of the PDF | coverage found `_unit_statement_failures` at 17/19 statements and 8/10 branches, and **the widening makes the first newly reachable** — before P14g every allowed page carried a printed figure, so it always had text | Leaving them would have left two stop paths of the very function this unit widens unlocked, and a coverage gap reads as a clean report |
| Nothing asserted about the known hole | the assignment's second trap, and `.claude/agents/tester.md`: do not assert a behaviour whose fix would turn the test red | Recording it in this entry costs nothing and loses nothing |
| Did not re-run the hole's probe | the programmer measured it and the reviewer rebuilt it independently; a third measurement adds no information and only tempts me to write the number into a file | — |
| Walmart tests guarded by `RealFiling` + `skipif`, not by a literal path | `tests/unit/_real_filings.py` exists because a literal path once made four tests skip silently on a machine that held the file (backlog item 101) | A hard-coded path is backlog item 101 again |
| Did not add `-p no:randomly` to any command | the user's decision of 2026-10-07; it asserted nothing. Failing sets compared by **name** | — |
| Mutations run in `C:\tmp\p14gt\tree`, with a pristine copy and a byte-equality assert after each revert | a spot check left a `return []` in this exact file on 2026-10-05 and a check was dead for ten hours | `git stash` is forbidden, and editing in place is how that happened |

## What I did not do

- **I did not touch `ingestion/claude_extractor.py`.** Its sha256 is unchanged, verified before
  the first command and after the last. I believe the implementation is correct for the rule
  the assignment mandates; the one thing I would change is a lead decision, not mine (F1).
- **I did not delete or weaken either red test.** Two assertion lines changed; the other four
  assertions across the two tests are context lines in the diff.
- **I did not assert the known hole**, in either direction. Asserting it is accepted would lock
  it; asserting it is refused would be a red test for a decision the lead has already taken.
- **I did not edit `extractions/WMT.json`**, and no test I wrote reads it. Its `filings[0]`
  still cites the Comprehensive Income header; that is finding 2 of the programmer's entry and
  is not mine.
- **I did not touch `test_projector_rule3_red.py` or `test_routes_session_rule3_red.py`.** Both
  are red on purpose and both stayed red; the gate excludes them and reported 0 failures.
- **No `*_rule3_red.py` file was created.** Everything I wrote states a requirement the code
  **does** meet, so all of it belongs in a file the gate runs. I also checked the trap the role
  card names — a green test stranded inside a `*_rule3_red.py` file, backlog item 24 — against
  the two existing red files: neither is green, so there is nothing to move.
- Backlog item 127, the absent test-order guard, is untouched.

## Findings for the orchestrator

### F1 — the hole is now guarded by a test suite that deliberately says nothing about it, and that needs to be on the record where the fix will be written · `note`

The widening's price (a `(in thousands)` note header on the page before a `(in millions)`
income statement is now accepted, and every money figure would be divided by 1,000) is measured
in the programmer's entry and independently in the reviewer's, including the reviewer's 2x2
showing that neither narrower rule works. **My suite asserts nothing about it, on purpose, and
that means nothing in `tests/` will tell the next reader it exists.** When the item is opened
against item 114's close — for B1's circular expected scale, which is the root — the assignment
should say explicitly that the fixing unit's tester writes the first assertion about this case,
and that `tests/unit/test_p14g_unit_statement_pages.py`'s module docstring is where the
silence is explained and should be amended at the same time.

### F2 — mutation M4 is killed only by tests that need a real filing on the machine · `note`

"The newly-allowed page is still *checked*" is the property that stops the widening from being
worthless, and only two tests kill a mutation that removes it — both of them
`skipif`-guarded on `10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf`. A machine
without that file would run my suite green with that property unguarded, and `pytest -q` would
say `2 skipped` and nothing more. The structural reason is that a synthetic PDF built by a
test prints the statement on the page the test then cites, so it cannot express "an allowed
page that does not print the text". It **can** be expressed synthetically — write a PDF whose
page `N-1` prints a *different* scale statement from the one the answer cites — but that
fixture is one line away from the known hole's fixture, and building it would have put me in
the position of deciding what the right answer for that shape is. I did not build it. If the
orchestrator wants M4 guarded on every machine, that is a small assignment with a decision in
it, and it should be written as one.

### F3 — `_row_scale_failures` is at 25/36 branches from this unit's tests, and its own 31 tests live in another file · `note`

Not a defect, and not this unit's scope: `tests/unit/test_p14b_note_figures.py` covers B1.
Worth recording only because the two lines P14g changed in B1 (`:1674`, `:1710`) are covered
by **both** files now, and a future refactor of B1 should keep the one-rule test in
`test_p14g_unit_statement_pages.py` in view — it is the only test that asserts the two checks
agree, and it lives in neither function's "own" file.

### F4 — the assignment cites `test_p14a_units.py:291` for an assertion that sits at `:292` · `note`

Off by one: `:291` is the comment, `:292` the `assert allowed["share_units"] == {29, 30}`. The
instruction was unambiguous and I left the assertion untouched. Worth correcting if the line
is cited again, since the next reader may use it to check that nothing moved.
