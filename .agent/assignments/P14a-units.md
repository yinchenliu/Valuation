---
id: P14a-units
phase: 14 — the Pass 1 role (the user's approval of `share_units`, 2026-10-04)
agent: programmer
depends_on: [P13h-zero-debt-confirm]
---

# Read the printed unit statements, check them on their pages, and convert every figure to millions once, in Python

## Objective

Every money figure in this repository is in millions (`docs/4-conventions/units-and-signs.md`).
But Pass 1 copies each figure as printed, and filings print in different units. Measured
with `pdfplumber` on the latest filing of each company in `10K_filings/`:

| Company | Page | Printed unit statement |
|---|---|---|
| Walmart, 10-K 2026-01-31 | 21 | `(Amounts in millions, except per share data)` |
| AbbVie, 10-K 2025-12-31 | 21 | `(in millions, except per share data)` |
| Chipotle, 10-K 2025-12-31 | 29 | `(in thousands, except per share data)` |
| Okta, 10-K 2026-01-31 | 58 | `(dollars in millions, shares in thousands, except per share data)` |

L3Harris's filings are not in this table: the scan did not find the statement above its
income statement. Find it, or report that it is printed in a form step 2 does not cover.

The schema asks for `units` as a free string, and no code reads it (backlog item 44). So
a Chipotle extraction holds thousands and the CLI prints them with an `M`. Okta prints
money in millions and its share count in thousands, so the share count is on a different
scale from the money figures, and the implied share price follows from both. No Chipotle
or Okta extraction exists here, so that error is not measured.

The user approved on 2026-10-04 (rule 1, `docs/2-rules/rules.md`): the model returns two
printed unit statements, each with its page, `units` for money and `share_units` for the
share count. This is option C applied to units. The page check confirms each text on
its page. Python reads the scale word from the text and converts. **The model converts
nothing, and it returns no scale word of its own.**

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Measured at `0a5a715` on 2026-10-04, before
`P13h`. Re-measure the gates on your base commit and use those numbers.

| Fact | Command | Result |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 857 passed at `0a5a715` |
| lint | `.venv/bin/python -m ruff check .` | 4 errors, all `BLE001` |
| types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 9 errors in 4 files |
| census | the grep in `docs/2-rules/rules.md` (quote `'--include=*.py'` under zsh) | 65 |
| `units` is never read | `grep -n '"units"\|\["units"\]' ingestion/*.py` | only the schema line in `claude_extractor.py` |
| Walmart | `.venv/bin/python cli.py --session-file extractions/WMT.json` | revenue 680,985 (FY2025 column), implied share price $28.02 |
| Walmart's session file | `extractions/WMT.json` | format `session-extraction-v2`, one filing (`Walmart Inc._10-K_2026-01-31_English.pdf`), `"units": "Millions"`, diluted shares 8,022 on page 22 |
| the unit statements | `pdfplumber` text of the pages in the table above | each statement is found on its page |

If any of these disagrees with what you measure, stop and report the disagreement.

## What to do

1. **The Pass 1 schema** (`ingestion/claude_extractor.py`, `_FINANCIALS_SCHEMA`). Replace
   the `units` string with an object `{"printed": ..., "page": ...}`: the statement of the
   unit of the money figures, exactly as printed (usually under the income statement's
   title), and the 1-based PDF page it is printed on. Add `share_units` with the same
   shape: the words that state the unit of the diluted share count, exactly as printed.
   If one statement covers both, `share_units` copies it with its page. Change the
   `diluted_shares` description so it no longer says "same units as F/S", and change
   the prompt's "same currency and units as the source" line so it says: copy every
   figure as printed, never convert it. Leave `currency` as it is.

2. **Read the scale in Python.** One named function reads a scale word from a printed
   statement, for money and for the share count. A lookup table may map each scale word
   to a number (rule 2 allows a table of numbers). These cases are required, and each
   one is a filing in this repository or the form that forced this unit:

   | Printed statement | Money scale | Share scale |
   |---|---|---|
   | `(Amounts in millions, except per share data)` | millions | millions |
   | `(in millions, except per share data)` | millions | millions |
   | `(in thousands, except per share data)` | thousands | thousands |
   | `(dollars in millions, shares in thousands, except per share data)` | millions | thousands |
   | `(In millions)` (an MD&A table, L3Harris 10-K 2023-12-29 page 17) | millions | millions |
   | `(in millions, except share and per share data)` | millions | **stop**, when `share_units` cites this text: it excepts the share count from its scale |
   | a text with no scale word, for example `(in dollars)` | **stop** | **stop** |

   "per share data" excepts only per-share figures, so it does not take the share count
   out of the scale. A stop is a `Pass1ShapeError` problem (both routes already report
   those), naming the field, the text and the page. It never falls back to millions
   (rule 3). Accept `thousands`, `millions` and `billions`, in any letter case.

3. **Check each unit statement on its page.** Use the page text and the normalisation
   that `P12a` uses for printed lines (`_read_cited_pages`, `_normalised_text`). In route
   A, a unit statement not found on its page is a failed check, retried with the
   others. **After the last retry it stops the run**, unlike a printed line, which is
   kept and shown. The reason: a wrong scale moves every figure by a factor of 1,000,
   and nothing downstream can detect it. In route B, the loader stops and `check` lists
   it. Each stop names the field, the page and the text.

4. **Convert once, per filing.** One public function converts one filing's statements
   and its Pass 2 items to millions: every money figure with the money scale, the
   diluted share count with the share scale. Both routes call it, after that filing's
   Pass 2 and before any merge:
   - route A: in `extract_financials`, so the one-filing path and `extract_multi_year`
     both get converted statements;
   - route B: in `load_session_extraction`, per filing, before the merge or the
     one-filing return.
   Pass 2's prompt is built from that filing's statements before the conversion, so the
   context figures the model sees are in the filing's own units, and its `amount` values
   are in those units too (the Pass 2 schema already says "same units as financials").
   Convert each figure once, after its printed lines are summed. Use one operation per
   figure: divide by 1,000 for thousands, multiply by 1,000 for billions. A float
   division by an integer is correctly rounded, and a multiplication by 0.001 is not.

5. **The balance check stays at 1 printed unit.** `BALANCE_CHECK_TOLERANCE` is "1 in the
   filing's own units" (`models/financial_statements.py:257`). After the conversion the
   figures are in millions, so for a filing in thousands the threshold must become
   0.001. `BalanceSheet` must carry what one printed unit is in millions, set by the
   conversion. Do not give that field a default that assumes millions (rule 3). The
   parser, the CLI (`cli.py:505-525`) and the page (`templates/_statements.html:333-345`)
   must apply and print the same threshold, in words a reader can check.

6. **The session file becomes `session-extraction-v3`.** A `v2` file stops with a
   message that names the change (`units` is now a printed statement with its page, and
   `share_units` is new) and the remedy: run the `extract-filing` skill again, or add
   the two keys from the filing's printed unit statement. Keep the `v1` refusal. The
   `plan` command prints the new schema through the shared prompt.

7. **The CLI pickle cache.** Change `CACHE_FORMAT` (`cli.py:224`), so a pickle written
   before this unit, which holds figures that were never converted, is refused by the
   existing marker check.

8. **Docs.** Update `docs/3-architecture/extraction.md` (the Pass 1 shape, the `v3`
   format, the unit check), `docs/2-rules/llm-boundary.md` (the two fields the model now
   returns), `docs/4-conventions/units-and-signs.md` (where the conversion happens, and
   the threshold of the balance check) and `docs/3-architecture/data-contract.md` (the
   new `BalanceSheet` field).

## How to work

- **Do not edit `tests/`.** List every test that turns red, by name, with its reason. The
  tester repairs it. Expect many: every Pass 1 fixture holds `"units": "Millions"`, and
  every `BalanceSheet(...)` in the tests lacks the new field.
- **Measure on an isolated tree.** Export `git archive HEAD` into your own subdirectory
  of the session scratchpad,
  `/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/49a4d4a7-ff32-4deb-a1ba-ba1f44e044e1/scratchpad/p14a_programmer/`,
  copy in only this unit's files, and run the gates there. Never `rm -rf` a path outside
  your subdirectory. Do not stash or reset the shared tree.
- For the Walmart criterion, make a `v3` copy of `extractions/WMT.json` in your
  subdirectory. Add only the two unit keys, read from page 21 of the Walmart filing.
  Change nothing else in it. Do not edit `extractions/WMT.json`: it is not in git, and
  the orchestrator upgrades it after the unit is accepted.
- Set `PYTHONDONTWRITEBYTECODE=1` when you run a changed tree.
- The write guard can refuse a Bash command that holds `>` or `=` inside a quoted
  pattern or a heredoc (backlog item 75). If it does, write the script to a file in your
  subdirectory and run the file.
- **Make no paid API call.** Route A's retry can be exercised with `_call_llm` stubbed,
  as the `P12a` and `P13g` testers did.
- Do not edit `docs/9-reference/refactor-backlog.md`, `STATUS.md` or the journal index.
  The orchestrator closes the item.

## Files in scope

- `ingestion/claude_extractor.py`
- `ingestion/session_extraction.py`
- `models/financial_statements.py`
- `cli.py`: `CACHE_FORMAT` (`:224`) and the balance check print (`:505-525`) only
- `templates/_statements.html`: the balance check header (`:333-345`) only
- `docs/3-architecture/extraction.md`
- `docs/2-rules/llm-boundary.md`
- `docs/4-conventions/units-and-signs.md`
- `docs/3-architecture/data-contract.md`

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Out of scope

- `.claude/skills/extract-filing/`: the write guard keeps subagents out of `.claude/`.
  The orchestrator teaches the skill the `v3` shape after acceptance.
- `extractions/WMT.json`: the orchestrator upgrades it after acceptance.
- `api/routes_valuation.py` and `cli.py`'s stage 8: the yfinance share fallback
  (`sharesOutstanding / 1e6`) is in millions already, so it agrees with the converted
  figures. Its conditional zero is item 72.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | each required case in step 2 gives its scale or its stop | the table in step 2, row by row | a `python -c` call per row on the scale function, and on `parse_pass1` for the stop rows |
| 2 | a filing in millions does not move | every figure of the Walmart `v3` copy identical to the `v2` parse at the base commit | parse both, compare every field of every statement |
| 3 | a filing in thousands is converted once | revenue lines `[11313853]` → 11313.853; diluted shares `[1370000]` → 1370.0; a Pass 2 amount of 5000 → 5.0 | a hand-built answer with `(in thousands, except per share data)`, through the route A and the route B paths |
| 4 | money and shares on two scales | revenue `[2610]` → 2610.0; diluted shares `[180000]` → 180.0 | a hand-built answer with Okta's statement |
| 5 | a unit statement not on its page stops | route B: the loader stops naming `units` or `share_units`, the page and the text. Route A: retried, then a stop with the same names | a session file and a stubbed `_call_llm`, on a real PDF from `10K_filings/` |
| 6 | the real statements pass the page check | found, for each row of the Objective's table | the page check on each real PDF and page |
| 7 | the balance check stays at 1 printed unit | thousands filing: a gap of 0.5 printed units is `OK`, a gap of 2 is `FAIL`; the CLI and the page print the same threshold | a `python -c` call, and the CLI and `TestClient` output for the same balance sheet |
| 8 | a `v2` session file stops with the remedy | `ValueError` naming `session-extraction-v2`, both keys and the remedy | `load_session_extraction` on `extractions/WMT.json` |
| 9 | an old pickle is refused | the existing marker message, naming the new `CACHE_FORMAT` | a pickle written with the old marker, through the CLI's cache read |
| 10 | Walmart, end to end, does not move | stages 1 to 10 identical to the base commit's `v2` run, except the present value of the terminal value, which may differ by 1 (item 70) | `cli.py --session-file <your v3 copy>`, against the base run |
| 11 | no paid API call | 0 calls | a guard on `_call_llm` or the network in each route A measurement |
| 12 | the suite fails only where expected | every red test named, with its reason | the full suite and the gate form, on the isolated tree |
| 13 | the gates do not get worse | ruff, mypy and census no higher than on your base commit; route 200 | the gate commands in `docs/8-build/environment.md` |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md`: rule 1 and the user's approval of 2026-10-04; rule 2 (a lookup
  table of numbers); rule 3; rule 6.
- `docs/4-conventions/units-and-signs.md`: every money figure is in millions.
- `docs/9-reference/refactor-backlog.md`: item 44, and the unit statements measured there.
- `docs/3-architecture/extraction.md`: the two routes, the session file, the page check.
- `10K_filings/Okta/Okta Inc._10-K_2026-01-31_English.pdf` page 58: money and shares on
  two scales.
- `10K_filings/Chipotle/Chipotle Mexican Grill Inc._10-K_2025-12-31_English.pdf` page 29:
  a filing in thousands.

## Known open items

- Item 70: Walmart's present value of the terminal value reads 214,819 or 214,820 on one
  tree. Criterion 10 allows that difference only.
- Item 63: a filing with no text layer fails every page check. After this unit it also
  stops on the unit check. None of the filings here lacks a text layer. Record it, do
  not fix it.
- Item 62: a failed reading check never reaches the web page.

## Backlog items this unit is NOT fixing

- Item 10: the D&A subtraction in the parser. `P14c` owns it.
- Items 61, 51: dead code in `claude_extractor.py`.
- Items 73, 74: the Pass 2 retry edges.
- Item 53: `session_extraction.py` imports `_NRI_SCHEMA` by its private name.
- Item 60: the stale `plan` message about the fiscal year.
- Item 64: the page check's joined-line form.
- Item 72: the conditional zeros at `cli.py:1035` and `:1043`.
- Item 1's sites in the files in scope.

## Round 2 amendment (orchestrator, 2026-10-04, from the round 1 review)

The review is `.agent/journal/2026-10-04T1037-code_reviewer-p14a-units.md`. Answer every
finding by number in your round 2 entry. Your round 1 code stays in the working tree;
build on it.

- **F1 (blocker).** The unit page check must match the statement as a whole printed
  unit: the full text the model returned, parentheses included, with only whitespace
  normalised as `P12a` does. A fragment such as `(in thousands)` cited on Okta page 58,
  where the page prints `(dollars in millions, shares in thousands, except per share
  data)`, must fail. Re-run the reviewer's 16-filing scan
  (`scratchpad/p14a_reviewer/`): every real statement must still be found on its page.
- **F2 (major, rule 3).** Recognise shares only in forms you can name, and stop on any
  other. After the `per share` and `per-share` phrases are removed, if the text still
  mentions a share or shares, the share scale is read only from a `shares in <scale>`
  clause. Any other mention of shares stops the share scale. These four must stop:
  `(In millions, excluding share data)`, `(in millions, other than shares)`,
  `(in millions, but not shares)`, `(in millions; shares in actual numbers)`. The 34
  real statements in the reviewer's scan must read as they do now.
- **F6, made a requirement.** Tie each unit statement to the figures it governs:
  `units.page` must be a page that at least one printed line of that filing's income
  statement fields cites. `share_units.page` must be the `units` page or a page that a
  `diluted_shares` line cites. Otherwise it is a unit problem that names the field, its
  page and the pages allowed, and it stops as step 3 says. L3Harris 10-K 2026 page 62
  (`(In thousands)` above a stock-award table) cited as `units` must stop. Walmart,
  Okta, Chipotle and AbbVie must pass.
- **F4 (minor). Scope widened** to `templates/_statements.html`'s balance check value
  cells (the reviewer's `:357-359`). Format them with the printed-unit decimals, as the
  CLI does, so a filing in thousands shows `+0.002`, not `+0`.
- **F7.** Make the doc and the code agree on the generic subjects. Keep only a word that
  a filing in `10K_filings/` prints in that position, and name the filing in a comment.
  Remove any other.
- **F3 (escalated, not yours to fix).** The Pass 2 schema asks for `amount` in the "same
  units as financials". So when a note prints another scale, the model scales the
  figure: Walmart's session file holds 700 from "$0.7 billion". That breaks rule 1, and
  it is older than this unit. It is now backlog item 77, and the user decides the fix.
  **Do not change the Pass 2 schema or prompt.** Correct the doc lines that claim the
  opposite (`llm-boundary.md:99,108`, `units-and-signs.md:46`): state what the schema
  asks, that the model can scale a note's figure, and that this is item 77. The
  conversion of Pass 2 amounts with the filing's money scale stays as it is.
- **F5, F8.** No change. The orchestrator records them in the backlog.

Add a criterion for each of F1, F2, F4 and F6, and re-run criteria 1 to 13. Keep the
round 1 measurements in your entry; write round 2 in a new entry,
`.agent/journal/YYYY-MM-DDTHHMM-programmer-p14a-units-r2.md`.
- **Your finding 4. Scope widened** to `cli.py`'s import block, for this only: call
  `bs.printed_total_check(difference)`, and remove the `BalanceSheet` import if nothing
  else in `cli.py` uses it.
- **Your finding 6.** `docs/3-architecture/extraction.md` is in scope: remove the stale
  "Known defects" row for `_run_nri_pass`'s `except Exception`, which `P13g` closed.
