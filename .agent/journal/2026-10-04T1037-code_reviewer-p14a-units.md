---
agent: code_reviewer
assignment: P14a-units
round: 1
verdict: changes_requested
---

# Review of P14a-units, round 1

Programmer entry: `.agent/journal/2026-10-04T0951-programmer-p14a-units.md`

The diff is uncommitted, on `98b908e`. I measured on isolated trees in
`scratchpad/p14a_reviewer/`. `base/` is `git archive 98b908e`. `new/` is the same plus
the nine changed files. I set `PYTHONDONTWRITEBYTECODE=1` and made no paid API call.
Every route A run replaced `_call_llm` and `resolve_provider`. Network attempts: `[]`.

## The guard checks

Run over the five code files in scope. I compared the hit lines of base and new: the
md5 of the sorted hit lines is the same (`28a93aa1…`). **The diff adds no hit.**

| Check | Result |
|---|---|
| conditional zero | no hit in an added line. Pre-existing: `models/` 4, `cli.py` 3 (items 1, 72) |
| lookup with a fallback | no hit in an added line. Pre-existing: `claude_extractor.py` 13, `cli.py` 1 |
| bare or-default | no hit in an added line. Pre-existing: `claude_extractor.py:1607-1608` |
| money field defaulted to zero | no hit in an added line. Pre-existing: `models/` 42 (item 1). The new field has no default |
| `**kwargs` | clean |
| `getattr(` | no hit in an added line. Pre-existing: `claude_extractor.py:1607-1608`, `cli.py:704` |
| dict of functions | clean. `_SCALE_IN_MILLIONS` maps a word to a `Fraction`: a table of numbers (rule 2) |
| model client outside `ingestion/` | clean |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `pass1.units`, `pass1.share_units` absent, or v2 string shape | yes | `parse_pass1` on Walmart with `"units": "Millions"` and no `share_units` gives two problems that name both keys |
| `.printed` empty, `.page` 0, `.page` `True` | yes | each gives a `Pass1ShapeError` that names `pass1.units.<sub>` |
| a statement with no scale word | yes | `(in dollars)`: both keys stop |
| a statement that excepts shares with `except` | yes | row 6 of step 2: the share scale stops |
| a statement that excepts shares in other words | **no**, see **F2** | `(In millions, excluding share data)` gives `millions` for the share count |
| a unit statement not on its page | yes, but see **F1** | page 31 stops route B (`check` exit 2), and route A after 3 calls |
| `printed_unit_in_millions` missing or `None` | yes | `BalanceSheet(year=2024)` raises `TypeError`. With `None`, `printed_unit`, `printed_total_check`, `_tolerance` and `_decimals` all raise `ValueError` that names the field |
| a statement field the conversion does not list | yes | `_require_every_field_converted` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | yes after the conversion, on both routes. The exception is Pass 2 amounts whose note prints another scale (**F3**) |
| percentages at the route boundary | not touched |
| falsy not treated as missing | clean: `None if difference is None`, `if printed is None` |
| `analysis/` imports | not touched. `ingestion` now imports `printed_total_status` from `models`, which is allowed |

## The six questions

**1. `PRINTED_UNIT_DECIMALS = 6` (`models/financial_statements.py:27`) is correct handling of float error. It is not a rule 6 assumption.**
- It decides no figure. It decides only whether a gap of exactly 1 printed unit reads
  as 1, and so it reaches only the OK/FAIL status. My checklist row 5 is "a constant
  that reaches a displayed figure", and this constant reaches none.
- I measured it with 20,000 random lines printed as integers in thousands, each with a
  gap of exactly 1 printed unit:
  - with the guard, all 20,000 read OK;
  - without it, 12,700 read OK and 7,300 are misread as FAIL.
- A real difference is a multiple of the precision the filing prints. Rounding at 1e-6
  of a printed unit therefore cannot flip a real case.
- It is documented in `models/`, `data-contract.md` and `units-and-signs.md`. No page
  label is needed.

**2. No path reads a figure in printed units as if it were millions.**
- The objects before the conversion go to four places only:
  - the Pass 2 summary, which is meant to show printed units;
  - the arithmetic table and its messages, which say "in the filing's units";
  - `cmd_prompt --pass 2`;
  - `_print_pass1_tables`.
- Every `BalanceSheet` method that needs the unit stops on `None` (table above).
- Every consumer gets converted statements. I read each call site:
  - `api/routes_valuation.py:123,130,132,183`;
  - `cli.py:885,897,906,938`;
  - `extract_multi_year:2945,2973`.
- One limit: only `BalanceSheet` carries the marker. An unconverted `IncomeStatement`
  looks the same as a converted one (**F5**).

**3. The scale rules hold for every statement printed in the 16 filings, and there is one reachable gap.**
- My scan is my own (`scan_all.py`, `judge.py`). It took every parenthesised text with
  a scale word in all 16 PDFs: 34 distinct texts, 847 occurrences.
- Every reading is correct or stops. Examples:
  - `(Dollar amounts and retail square feet in millions)`: money millions, shares stop;
  - `(dollar and share amounts in thousands, unless otherwise specified)`: both thousands;
  - `(options in thousands, aggregate intrinsic value in millions)`: both stop;
  - `(Amounts in millions, except unit counts)`: both millions.
- All 847 are found on their own page.
- The gaps are in forms that are not in the 16 filings but are reachable: **F2** (an
  exception written without "except") and **F1** (a fragment passes the page check).

**4. Every filing is converted exactly once on both routes, and each Pass 2 amount takes the scale of its own filing.**
- `multi.py` merges two filings with a Pass 2 amount of 5000 each:
  - Walmart 10-K 2025-01-31, in millions;
  - Chipotle 10-K 2025, in thousands.
- Route A (`extract_multi_year`) and route B (a two-filing session) give the same
  result:
  - items `[(2023, 5000.0), (2025, 5.0)]`;
  - Chipotle revenue 11313.853, Walmart revenue unchanged;
  - one `Units:` line per filing.
- The one-filing paths give the same result on both routes (criterion 3 below).
- Whether the Pass 2 amount is in the filing's scale *before* the conversion is a
  separate question. It is **F3**.

**5. Scope is clean.**
- The line numbers in the assignment were measured at `0a5a715`. P13h moved the
  `cli.py` lines by +9.
- `CACHE_FORMAT` is at `0a5a715:224` and base `:233`. The balance block is at
  `0a5a715:505-525` and base `:514-534`. The edits are at base `:233` and `:515-533`.
- The template edits are at `:334-341`, inside `:333-345`.
- No file outside the list was written.

**6. This unit turns `tests/unit/test_cli_overrides.py` red: 5 of its 11 tests.**
- The fake `_extract_from_session_file` returns statements built by hand, so the loader
  and the conversion never run.
- The cause is `BalanceSheet(...)` at `:109` and `:173` without the required
  `printed_unit_in_millions`. They give `TypeError`.
- I added `printed_unit_in_millions=1.0` to both lines in a scratch copy. All 11 then
  pass, and `main()` reaches stage 8 through the new balance check.

**The red tests.** At `98b908e` the full suite gives **293 failed, 619 passed**. The base
gives 2 failed, 910 passed. The gate form gives 291 failed.
- My failure set holds the programmer's 254 exactly, by ID.
- The other 39 are all from tests that `98b908e` added:
  - `test_wacc` 22;
  - `test_routes` 10;
  - `test_cli_overrides` 5;
  - … and the rest.
- Each of the 39 fails on the required field: a `TypeError`, or a route that renders it.
- I checked the grouping with a probe. I gave the field a default of 1.0 in a scratch
  copy, and exactly 130 remain red: B 121, E 6, V 1, K 2.
- So 163 are group A (124 + 39), and the programmer's grouping is confirmed.

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | step 2 rows | 7 rows pass | `c1.py`: all 7 rows as the table says, and 23 probes. Stop rows through `parse_pass1`: row 6 stops the share scale, row 7 stops both | yes |
| 2 | millions filing does not move | 137 values identical | `dump.py`: v2 at base against v3 at new, 0 differ. The only addition is `printed_unit_in_millions = 1.0` | yes |
| 3 | thousands converted once | 11313.853 / 1370.0 / 5.0 | `hb.py`: route A (4 calls) and route B both give 11313.853, 1370.0, 5.0 and unit 0.001 | yes |
| 4 | two scales | 2610.0 / 180.0 | both routes give 2610.0 and 180.0 | yes |
| 5 | not on its page stops | yes | `c5.py`: route B names `units` or `share_units`, the text and page 31, and `check` exits 2. Route A stops after 3 Pass 1 calls with no Pass 2. A reply fixed at the retry proceeds | yes, **but see F1** |
| 6 | real statements found | 7 found | the objective's rows plus L3Harris: found on their page, not on the next. 847 of 847 scanned statements found | yes |
| 7 | threshold at 1 printed unit | OK / FAIL, same text | `c7b.py`: model 0.5 unit gives OK, 2 units give FAIL. The CLI and the page header both read `FAIL above 0.001 $M: 1 in the filing's printed unit, and 1 printed unit = 0.001 $M`. The page cells show `+0` beside FAIL (**F4**) | yes |
| 8 | v2 refused with remedy | yes | `ValueError` names `session-extraction-v2`, both keys and the remedy | yes |
| 9 | old pickle refused | yes | a pickle written by base `_save_cache` (`p11a-printed-lines-v1`) is refused by new `_load_cache`, which names `p14a-units-in-millions-v1` | yes |
| 10 | Walmart end to end | identical except labels | `run_cli.py`, guarded, 0 LLM calls. The diff has only the file name, the two new lines and the balance header. Revenue 680,985, PV TV 214,819, $28.02 in both | yes |
| 11 | no paid call | 0 | 0 calls, `[]` network attempts | yes |
| 12 | reds named | 254 at `99f8b1d` | 293 at `98b908e`: the 254 plus 39 from P13h's tests, all group A | yes |
| 13 | gates | ruff 4, mypy 9/4, census 65 | same on both trees, and the error lists `diff` empty. `GET /` gives 200 | yes |

## Findings

### F1 — The unit page check confirms a statement that the page does not print · `blocker`

**Evidence:**
- Session `hb_okta_frag.json` cites `units` and `share_units` as `(in thousands)` on
  page 58 of the Okta 10-K 2026.
- Page 58 does not print `(in thousands)`. `"(in thousands)" in text.lower()` is
  `False`.
- The check still reads `2 checked, 2 found, 0 not confirmed`. Revenue printed 2,610
  (in millions) becomes **2.61**.
- Across the 34 pages of the 16 filings that print two scales, `(in thousands)` or
  `(in millions)` is "found" on 41 page/fragment pairs where it is not printed.
- The cause is `claude_extractor.py:1357`. It checks the normalised *words*
  (parentheses and commas removed) anywhere on the page. So the words "in thousands",
  inside "shares in thousands", confirm a whole statement with a different meaning.

**Rule or document:**
- Rule 1, the approval of 2026-10-04: "The page check confirms each text on its page."
- Rule 3: the error is a wrong scale, factor 1,000, not a stop.
- The assignment says a unit statement is the one check that must stop. That reason
  makes this a blocker.

**What would fix it:** confirm the statement as a printed whole, not as a run of
words. For example:
- keep the parentheses and commas, and fold only case and whitespace; or
- require the normalised words to fill a whole parenthesised group, or a whole text
  line, on the page.

Add a control: `(in thousands)` must not be found on Okta page 58.

### F2 — `printed_scale` gives the share count a scale when the statement excepts shares in words other than "except" · `major`

**Evidence:** the share count gets a scale in each of these cases:
- `(In millions, excluding share data)` gives `millions`;
- `(in millions, other than share and per share data)` gives `millions`;
- `(in thousands, but not shares)` gives `thousands`;
- `(in millions; shares in actual numbers)` gives `millions`.

The cause is the generic branch at `claude_extractor.py:705-706`. It is reached
whenever no clause names shares and the exception text holds no "except … share".

**Rule or document:**
- Rule 3.
- The function's own contract at `:686`: "every case not read stops".

None of these forms is in the 16 filings. Reachability is not the test.

**What would fix it:** take the share scale from a generic clause only when the
statement names shares nowhere outside a share clause. Strip "per share" first. If it
does, stop. All seven required rows still pass, and so do the 34 real texts.

### F3 — The Pass 2 amounts depend on the model converting units, and the new docs say they do not · `major` (escalation)

**Evidence:**
- `claude_extractor.py:376` asks for `amount` in the "same units as financials".
- The Walmart session (`extractions/WMT.json`) holds `amount: 700` with source
  "… Printed as $0.7 billion". The model converted billions to millions.
- This unit converts that amount with the filing's money scale. Its docs now state:
  - "its amounts are in [the filing's own units]" (`llm-boundary.md:99`,
    `units-and-signs.md:46`);
  - and that the model may never return "a figure converted to another unit"
    (`llm-boundary.md:108`).
- For a filing in thousands whose note prints "$5.2 million", the result depends on
  the model. It either converts (5,200, against rule 1) or does not (5.2 / 1,000 =
  0.0052, silent). The line at `:376` is not touched, and the backlog does not list
  this defect.

**Rule or document:**
- Rule 1, and the approval "The model converts nothing".
- Step 4 of the assignment relies on the Pass 2 schema ("already says 'same units as
  financials'"). **The assignment conflicts with the rule.** Per my brief, the
  orchestrator corrects it.

**What would fix it:** give each Pass 2 item its own printed unit statement and page,
the same shape as `units`, and convert it in Python. Or the user decides. Until then,
correct the three doc lines so they do not claim it.

### F4 — The page's balance check cells print `+0` beside `FAIL` for a filing in thousands · `minor`

**Evidence:**
- `templates/_statements.html:357-359` formats with `{:,.0f}`. With `c7b.py` the page
  shows `285 | 285 | +0 | FAIL`.
- The CLI shows `+0.002 FAIL` for the same sheet.
- The lines are outside the unit's template scope (`:333-345`). The programmer raised
  this as its finding 1.

**Rule or document:** step 5 of the assignment, "in words a reader can check".

**What would fix it:** format the three cells with `bs.printed_unit_decimals()`, as the
CLI does. The orchestrator must widen the scope to `:357-359`.

### F5 — The "already converted" guard sees balance sheets only · `note`

**Evidence:** `claude_extractor.py:2740`. A filing with `include_bs=False`, which is every
route A filing except the newest, carries no marker. A second call would convert it
again without a stop.

No call site converts twice. I measured one call per filing on both routes.

### F6 — The page check proves the words are printed, not that they govern the figures · `note`

**Evidence:**
- On page 62 of the L3Harris 10-K 2026, `(In thousands)` heads an RSU table.
- Cited as `units` on that page, it reads `thousands` and is found. The statements
  print in millions.
- This is a limit of the approved option C, not a defect of this code.
- For the orchestrator: decide whether `units.page` must be a page that the
  income-statement lines cite, or a neighbouring page. Walmart cites `units` on page 21
  and its diluted row on page 22.

### F7 — The doc's generic-subject words differ from the code · `note`

**Evidence:**
- `docs/3-architecture/extraction.md`: "none (or only `amounts`) states both".
- `claude_extractor.py:588` also accepts `amount`, `all` and `and`.

### F8 — Backlog item 61 was touched · `note`

**Evidence:** `claude_extractor.py:2157`. The unreachable `return financials` is now `raise
AssertionError(...)`. It is still dead code, but it now stops instead of returning a
value, which is allowed. Update the text of item 61.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 | `models/financial_statements.py` money fields `= 0.0`; `claude_extractor.py` `.get(…)` sites | no |
| 72 | `cli.py` conditional zeros | no |
| 53 | `session_extraction.py` imports `_NRI_SCHEMA` | the import block grew, but that line is unchanged |
| 63 | no text layer: now also stops on the unit check | recorded by the programmer, as the assignment asks |
| 64 | the page check's joined-line form for printed lines | no |
| 10 | D&A subtraction in the parser | no |

## Verdict

`changes_requested`

- **F1 (blocker).** The page check is the only safeguard against a wrong scale, and it
  confirms a fragment the page does not print. On Okta it divides every money figure
  by 1,000 with no stop.
- **F2 (major).** An exception written without "except" gives the share count a scale
  where it must stop (rule 3).
- **F3 (major, escalation).** The assignment's step 4 relies on a Pass 2 schema that
  makes the model convert units, which rule 1's approval forbids. The orchestrator must
  correct the assignment or take it to the user. The programmer cannot settle it
  within the current scope.
- **F4** needs the template scope widened.
- **F5 to F8** are notes.

The other done-criteria hold on my own measurements.
