---
agent: code_reviewer
assignment: P14g-unit-statement-pages
round: 1
verdict: approved
---

# Review of P14g-unit-statement-pages, round 1

Programmer entry: `.agent/journal/2026-10-07T1556-programmer-p14g-unit-statement-pages.md`

Diff: one file, `ingestion/claude_extractor.py`, +71 / −15, four hunks, all inside the
unit-scale check region (`@@ -1417`, `-1470`, `-1485`, `-1565/-1619/-1651`). **In scope.**

Every measurement below is mine, run on my own scratch trees under `C:\tmp\rev14g\`
(`head/` = `git archive HEAD`, `after/` = `head/` with the working-tree
`claude_extractor.py` copied over, `rulex/` and `ruley/` = the two narrower rules I
implemented myself). I did not read or re-run anything under `C:\tmp\p14g\`. Every
command carried `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and `.venv/Scripts/python.exe`.
No repository file was written: `ingestion/claude_extractor.py` is
`d4a4783247f493460bd8656b2fd55f74761b6d87c9c039187d0b773be2d5cb68` and
`extractions/WMT.json` is
`c436e427ce3037d0f4c3131bacac479b876a36e05138d34cc577d81c008a3675` before my first
command and after my last.

## The guard checks

Run over `ingestion/claude_extractor.py`, the one file in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | **clean**, no hit anywhere in the file |
| lookup with a fallback — `.get(k, …)` | 5 hits, **every one outside the diff**: `:1953`, `:2170`, `:2171`, `:2220`, `:2764`. All are strings (`os.environ.get("GEMINI_API_KEY", "")`, `data.get("ticker", "")`, a `!r` message), none is money, none is a census site, none was touched |
| bare or-default — `or 0.0` / `or ''` | 3 hits, `:1982`, `:1983`, `:1984`, all in the Gemini transport, **all outside the diff** |
| money field defaulted to zero — `: float = 0.0` | **clean** |
| `**kwargs` on a calculation function | **clean**, no hit in the file |
| `getattr(` on a name from outside the file | 2 hits, `:1983`, `:1984`, on `response.usage_metadata`, attribute names are literals in the file, **outside the diff** |
| dict of functions keyed by data | **clean**. `_PAGES_ALLOWED_ARE` (`:1540-1549`) is a dict of **strings**, keyed by the two literal keys of `_UNIT_STATEMENT_FIELDS`, not by anything from data. Rule 2 allows a lookup of a value. The diff edited its two string values only |
| model client imported outside `ingestion/` | **clean**: `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output |

Not one grep hit falls on a line the diff touched. The census is **64** before and after,
unchanged.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `pages` into `_pages_and_page_before` | yes — empty in gives empty out, and then **no** page is allowed, so every unit statement fails and the run stops. There is no "default to the cited page" | `:1479-1499`; executed: `_pages_and_page_before(set()) -> []` |
| `data["historical_years"]`, `entry[field]`, `line["page"]` | yes, `KeyError` | `:1525-1532`, direct subscripts, unchanged by the diff |
| `data["units"]["page"]` | yes, `KeyError` | `:1534`, direct subscript, kept exactly as it was |
| `data["units"]["printed"]`, `data[key]["page"]` | yes, `KeyError` | `:1565-1568` |
| `page_texts[p]` in B1 | yes, `KeyError` — a page not read is never silently skipped | `:1712`. `pages_to_read` (`:1674`) and `pages_to_check` (`:1710`) are now the **same expression** applied to a superset and a subset, so they cannot disagree. This is strictly safer than the two hand-written copies it replaces |
| `_texts.get(page)` | **not present** — I looked for a `.get` introduced by the widening and there is none |

The diff adds no `.get` with a fallback, no bare `or`, no conditional zero, no defaulted
field. **No rule 3 finding.**

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | unaffected — the diff touches no arithmetic and no conversion. The Walmart stage table is byte-identical across the two trees (criterion 7 below) |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing | **clean in the diff.** The one falsiness in the changed region is `if p_text and p_text.strip()` at `:1713`, which is unchanged context and is about a text layer, not a number |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean; the diff is confined to `ingestion/` |
| prompt and schema untouched | **confirmed by hash, not by reading.** I took `inspect.getsource` of all sixteen prompt/schema objects in both trees and hashed the concatenation: `2d173063909141e8b8e5d440b7d7255126d0049633cb93167ab0856b1fa55b1e` in **both**. No LLM boundary change, so nothing to escalate under `AGENTS.md` |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | refusal reproduced at `HEAD` | refused, message quoted | **refused.** `head` tree, real 147-page PDF: `'units' … the statement '(Amounts in millions, except per share data)' cites page 45, which is not a page of the figures it states the unit of: the pages allowed are [46], the pages the income statement's printed lines cite.` Byte-for-byte the quoted message | **yes** |
| 2 | that citation now accepted | 0 failures | **0 failures**, `units allowed=[45, 46]`, `2 checked, 2 found, 0 not confirmed` | **yes** |
| 3 | the two checks state one rule, page-1 edge | one function, edge executed | **yes.** `_pages_and_page_before([1])=[1]`, `([2])=[1,2]`, `([1,2])=[1,2]`, `([46])=[45,46]`, `([1,46])=[1,45,46]`, `([])=[]`. Page 0 is never produced. B1's `sorted(_pages_and_page_before({page}), reverse=True)` is identical in value **and order** to `(page, page-1) if page>1 else (page,)` for every `page >= 1`, and `pages_to_read` is the same set expression it replaced | **yes** |
| 4 | `share_units` decided on purpose | `diluted_pages` widened, `units.page` not | the code does exactly that (`:1534`) and the docstring gives the reason. Executed: fy2026 `share_units` is `[21, 22]` before **and** after, because `21 = 22 − 1` already comes from the diluted page | **yes** |
| 5 | the price of the widening | measured, including a wrong answer now accepted | **confirmed and extended — see "Half two" below** | **yes** |
| 6 | nothing that used to be caught gets through | five refusals | **five refusals, mine, on the real PDF.** (a) page 44, two before: refused, `the pages allowed are [45, 46]`; (b) page 47, after: refused; (c) `(in thousands)` on page 46: refused, `was not found on page 46 … as a whole printed statement`; (d) `(Amounts in millions)` on the newly-allowed page 45: **refused**, `was not found on page 45` — the new page is still *checked*, not merely allowed; (e) `share_units` on page 44: refused | **yes** |
| 7 | no figure moves, Walmart | 387 lines byte-identical, `$30.87` | **byte-identical.** My own runner, my own pin (a seeded synthetic `PriceData`, so **no network at all**), `cli.py --session-file extractions/WMT.json` in both trees: 381 lines each, stdout sha256 `06c9c30aa71a11ff7f6f70f5eeab2608e8891bddcbc54fb493999c319ce7770f` on **both**, `diff` empty on stdout and on stderr, exit 0 both. My line count and share price differ from the programmer's because my pin differs; what the criterion asks is identity **across the trees**, and it holds | **yes** |
| 8 | `extractions/WMT.json` unchanged | sha256 identical | `c436e427…` before my first command and after my last | **yes** |
| 9 | types | 2 errors in 2 files | **2 errors in 2 files, 21 checked**: `analysis/projector.py:395`, `api/routes_upload.py:28` | **yes** |
| 10 | lint | 4, all `BLE001` | **4, all `BLE001`**: `api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106`. Run after my last write | **yes** |
| 11 | census | 64 | **64** | **yes** |
| 12 | route | 200 | **200** | **yes** |
| 13 | failing set, by name | before `{}`, after the two `test_p14a_units.py` tests | **before `{}`** (`head` tree: `1257 passed, 2 skipped` in 137.35s). **After** (`after` tree: `2 failed, 1255 passed, 2 skipped` in 135.96s) the set is exactly `{test_p14a_units.py::test_unit_statement_pages_allowed_constrains_pages, test_p14a_units.py::test_unit_statement_failures_stops_when_page_outside_allowed}`. Compared by name, not by count. Both trees carried `10K_filings/` and `extractions/` so nothing skipped on absence | **yes** |
| 14 | no paid call | stated | **confirmed, and I proved the second half rather than taking it.** My criterion-7 runner replaced `socket.socket` and `socket.create_connection` with raisers **before importing `cli`**, so any API call or yfinance call would have raised. Both runs completed, exit 0, and the run's own provenance line says `Credential: none — no API call was made; the extraction was read from the session file on disk`. Every other probe of mine read PDFs with `pdfplumber` only | **yes** |

Write guard: `.claude/check_guard.py` → **48/48**.

## Half two — the price of the widening, measured by me

### The hole is real: confirmed, both halves

I built my own two-page PDF (page 1 a note headed `(in thousands)`, page 2 the income
statement headed `(in millions)` carrying every figure) and my own Pass 1 answer. I did
not reuse the programmer's probe.

| | `head` | `after` |
|---|---|---|
| `units` = `(in millions)` page 2 (right) | accepted | accepted |
| `units` = `(in thousands)` page 1 (wrong) | **REFUSED** — `cites page 1 … the pages allowed are [2]` | **ACCEPTED**, 0 failures |
| check B1 on the wrong answer | **0 failures**, `42 checked, 1 pages, 0 pages not confirmed` | **0 failures**, same line |

`printed_scale('(in thousands)', 'money figures').in_millions` is `Fraction(1, 1000)`, so
every money figure would be divided by 1,000. **Both halves of the programmer's finding 1
are confirmed**, including the circularity: B1's expected word comes from
`_filing_units(data)`, which reads `units`, so B1 is asking whether a statement of the
scale `units` claims is printed near the rows — and the note on page 1 is exactly that
statement. B1 cannot catch this and it reports `0 pages not confirmed` in both trees.

### The one fact that changes how this should be priced

**The hole is not created by this unit. It already exists at `HEAD` whenever the two
statements share a page.** I put the `(in thousands)` note header on the *same* page as
the income statement's figures and ran both trees:

```
### tree: head    note's '(in thousands)' on the SAME page as the figures: ACCEPTED (0 unit-statement, 0 B1)
### tree: after   note's '(in thousands)' on the SAME page as the figures: ACCEPTED (0 unit-statement, 0 B1)
```

So the class of wrong answer — "cite another table's unit statement, in a different
scale, near the figures" — is accepted at `HEAD` already. What this unit changes is the
**width of the window**, from the figure's page to the figure's page plus the page before
it. That is a widening of an existing hole by one page, not a new hole.

### The 2x2: both narrower rules, implemented and executed

I implemented each rule in its own scratch tree (`rulex/`, `ruley/`) by giving
`_unit_statement_pages_allowed` the PDF bytes and gating the predecessor page per figure
page, then ran the two cases against each.

| Rule | Walmart fy2024, `units` = `(Amounts in millions, except per share data)` p.45 (the reading the unit exists for) | The bad case, `units` = `(in thousands)` p.1 |
|---|---|---|
| `HEAD` — no page before | **REFUSED** (the defect item 114 names) | REFUSED |
| **as built** — B1's rule, page before always | **ACCEPTED** (fixed) | **ACCEPTED** (the hole) |
| **rule X** — page before allowed only when the figure's own page prints *no* scale statement | **REFUSED** — `allowed units=[46]`, message `cites page 45 … the pages allowed are [46]` | REFUSED (hole closed) |
| **rule Y** — page before allowed only when the figure's own page prints no statement the `units` text equals | **ACCEPTED** — `allowed units=[45, 46]` (fix kept) | **ACCEPTED** — `allowed units=[1, 2]` (hole open) |

**The caller's reading is confirmed on both counts, by execution.**

- **Rule X breaks the unit.** PDF page 46 of the fiscal 2024 filing prints exactly one
  scale statement, `['(Amounts in millions)']` — the Consolidated Statements of
  Comprehensive Income header — so rule X blocks page 45 and refuses the correct reading.
  Measured directly with `pdfplumber`: page 45's scale groups are
  `['(Amounts in millions, except per share data)']`, page 46's are
  `['(Amounts in millions)']`.
- **Rule Y leaves the hole open.** In the bad case page 2 prints `(in millions)` and
  `units` is `(in thousands)`; the texts differ, so the predecessor is still allowed and
  the wrong answer is still accepted.

Neither narrower rule works. A rule that both keeps the Walmart fix and closes the hole
would have to compare the *scale word* each candidate statement reads — that is a
different check from "which pages may be cited", and it is the check B1 would be if B1's
expected word did not come from `units`.

### Exposure on the real inputs, re-measured

| Filing | `units` before → after | page added | what that page prints |
|---|---|---|---|
| `filings[0]` fy2024 | `[46]` → `[45, 46]` | 45 | `['(Amounts in millions, except per share data)']` — the income statement's own header |
| `filings[1]` fy2025 | `[45]` → `[44, 45]` | 44 | `[]` — no scale statement at all |
| `filings[2]` fy2026 | `[21, 22]` → `[20, 21, 22]` | 20 | `['(Amounts in millions)']`, an uncertain-tax/market-risk page |
| `share_units` fy2026 | `[21, 22]` → `[21, 22]` | none | the criterion-4 choice is what keeps page 20 out of `share_units` |

Every added page reads *millions* or prints nothing, which is the scale these filings are
printed in. **Exposure on the three extractions this repository holds is zero**, measured,
not asserted.

### Should the unit ship as built? Yes — and here is the reason, not the verdict

Four facts, each executed above.

1. **It fixes a stopping defect on a correct reading.** At `HEAD` the one citation that
   names the income statement's own printed unit line is refused and the run exits. That
   is the worst kind of check failure: it punishes the right answer.
2. **The hole it widens already exists.** The same wrong answer is accepted at `HEAD` when
   the note and the figures share a page. The unit moves the window edge by one page; it
   does not open a new class.
3. **Neither narrower rule is available.** Rule X costs the fix, rule Y buys nothing. I
   implemented both and ran both. The programmer was right to refuse to invent a third
   rule on its own authority — `AGENTS.md` and its own role card put that decision with
   the lead — and right to write the price down instead.
4. **The root is elsewhere.** The thing that lets any of this through is that B1's
   expected scale is read from `units`. That is a defect in `_row_scale_failures`, in a
   different function, and no rule in `docs/2-rules/rules.md` is broken by this diff. It
   belongs in the backlog against item 114's close, which is exactly where the programmer
   put it.

The widening is paid for, measured, reversible, and does not reach a figure. **Approved.**

## The two red tests — each diagnosed, with its line

Both are red because they assert the **old, narrower rule**. Neither is red because the
new code is wrong. I ran each and read the assertion that fired.

| Test | Line | Why it is red | Is the behaviour under test still there? |
|---|---|---|---|
| `tests/unit/test_p14a_units.py::test_unit_statement_pages_allowed_constrains_pages` | `:289` `assert allowed["units"] == {29, 30}` → `assert {28, 29, 30} == {29, 30}`, "Extra items in the left set: 28" | **asserts the old rule.** Page 28 is the page before income page 29, which is precisely what the unit adds | **yes.** I ran the same fixture through the new function on its own: `units [28, 29, 30]`, `share_units [29, 30]`, so the test's *second* assertion (`allowed["share_units"] == {29, 30}`, `:291`) is **still true** and would pass once the first is updated |
| `tests/unit/test_p14a_units.py::test_unit_statement_failures_stops_when_page_outside_allowed` | `:340` `assert "the pages allowed are [29]" in msg` | **asserts the old rule's printed list.** The list is now `[28, 29]` | **yes.** The three assertions above it — `len(failures) == 1` (`:336`), `"'units'" in msg` (`:338`), `"page 35" in msg` (`:339`) — all pass. A unit statement on a stock-award table six pages away is still refused; only the printed list changed |

The programmer did not touch `tests/` and the assignment forbids it. Correct. These two
are the tester's assignment, and the tester should be told that `:291` is already right.

## Findings

### F1 — the widening doubles the window in which a model may cite another table's unit statement, and no check can see it · `note`

**Evidence:** my own probe, both trees: `[WRONG: the note's '(in thousands)' on page 1]`
→ `1 failure(s)` at `head`, `0 failure(s)` after; B1 `0 failures` in **both**.
**Rule or document:** **none is broken.** The unit-statement check still confirms the text
on the page it cites (`criterion 6d`: the newly-allowed page 45 refuses a text page 45
does not print), which is what rule 1's 2026-10-04 decision requires. Nothing here is a
rule 3 default, a model-produced number, or an unlabelled assumption. The assignment's
step 2 mandates B1's rule, and the price is what criterion 5 asked for and got.
**Why `note` and not `major`:** I could not name a rule, and the same wrong answer is
accepted at `HEAD` when the two statements share a page — executed above. The root cause
is B1's expected scale being read from `units`, a different defect in a different
function.
**What would fix it:** not this unit. Open a backlog item against item 114's close for
B1's circularity, with my 2x2 attached so the next reader does not re-propose rule X or
rule Y. A check that compares the *scale word* of every scale statement printed on the
allowed pages, and stops when two of them disagree, is the shape that would work; it is a
new primitive and a lead decision.

### F2 — the two red tests assert the old rule; neither reports a defect in the new code · `note`

**Evidence:** `test_p14a_units.py:289` fails `assert {28, 29, 30} == {29, 30}`;
`:340` fails `assert "the pages allowed are [29]" in msg` where the list is now
`[28, 29]`. The three assertions at `:336`, `:338`, `:339` still pass.
**Rule or document:** none. `tests/` is out of the programmer's scope by assignment and
by `.claude/agents/programmer.md`.
**What would fix it:** the follow-up tester assignment updates `:289` to `{28, 29, 30}`
and `:340` to `[28, 29]`, and leaves `:291` alone, which is already correct under the new
rule and is the assertion that locks the criterion-4 decision.

### F3 — the assignment's fact 3 names a wider set than the check ever used · `note`

**Evidence:** `head` tree, executed: the allowed sets at `HEAD` are `[46]`, `[45]`,
`[21, 22]`, not the assignment's `[46, 48]`, `[45, 48]`, `[21, 22, 23]`, because
`_INCOME_STATEMENT_LINE_FIELDS` (`:1442-1447`) deliberately excludes the five cash-flow
fields.
**Rule or document:** none — the assignment's conclusion is unaffected, since page 45 is
outside `[46]` either way.
**What would fix it:** the orchestrator corrects item 114's backlog text. The programmer
reported this itself; I confirmed it rather than took it.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 119 | `ingestion/claude_extractor.py`, `nri_identity` / `merge_filing_extractions` | no |
| 120 | `_print_repeated_item`, `REPEAT_WITHIN_ONE_FILING` | no |
| 121 | `:2252-2262` | no |
| 122 | `:2420`, `:2593` | no |
| 133 | `:2280`, `:2358` | no |
| 8 | the blanket `except Exception` (the 4 `BLE001`) | no |
| 115, 117 | `tests/unit/test_p14d_finance_leases.py:519`, `:536` | no |

I saw the `.get`/`or`/`getattr` hits at `:1953`, `:1982-1984`, `:2170-2171`, `:2220`,
`:2764` and they are untouched pre-existing lines in the Gemini transport and the merge;
none is a census site and none is in the diff. Not findings against this unit.

The out-of-scope item the programmer reported — `extractions/WMT.json` `filings[0]` cites
the Comprehensive Income header rather than the income statement's own — I confirmed with
`pdfplumber` (page 46's only scale group is `(Amounts in millions)`; page 45's is
`(Amounts in millions, except per share data)`). The file is out of the unit's scope by
assignment and the programmer correctly left it alone. **No figure moves either way**,
which my byte-identical CLI comparison proves.

## Earlier findings — re-reviews only

Not applicable; this is round 1.

## Verdict

`approved`

Every one of the fourteen criteria holds when I run it rather than read it, including the
two the unit turns on: the `HEAD` refusal is reproduced word for word, and the price of
the widening is real. The diff is one file, confined to the two checks fact 1 names plus
the one pure function that now holds their shared rule; no prompt byte and no schema byte
moved, confirmed by hashing the source of all sixteen prompt and schema objects in both
trees. No guard grep hits a line the diff touched, the census is 64 either side, and no
value the new code reads can go missing without a `KeyError` that names it. I built the
bad case myself and confirmed both halves of the programmer's finding 1; I then
implemented both narrower rules it proposes and **overturned neither of the caller's
predictions** — rule X refuses the Walmart fiscal 2024 reading the unit exists to accept,
rule Y leaves the bad case accepted. The decisive fact for shipping is one the programmer
did not state and I measured: the same wrong answer is already accepted at `HEAD` when the
note and the figures share a page, so this unit widens an existing window by one page
rather than opening a new one, while closing a defect that stopped a correct reading. No
rule in `docs/2-rules/rules.md` is broken, so F1 to F3 are `note`s and none blocks. The
residual risk is B1's circular expected scale, which lives in a different function and
belongs in the backlog against item 114's close, with the 2x2 above attached.
