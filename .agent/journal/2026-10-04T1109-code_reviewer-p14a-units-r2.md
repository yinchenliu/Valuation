---
agent: code_reviewer
assignment: P14a-units
round: 2
verdict: approved
---

# Review of P14a-units, round 2

Programmer entry: `.agent/journal/2026-10-04T1041-programmer-p14a-units-r2.md`
Round 1 review: `.agent/journal/2026-10-04T1037-code_reviewer-p14a-units.md`

Base commit `167d903` (or `98b908e`). Measured in the working tree with `.venv/bin/python` (`PYTHONDONTWRITEBYTECODE=1`).
Zero paid API calls. Network attempts intercepted and verified: `[]`.

## The guard checks

Run over the code files in scope (`cli.py`, `ingestion/claude_extractor.py`, `ingestion/session_extraction.py`, `models/financial_statements.py`).
The diff adds zero hits to any guard check.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean in diff. Pre-existing: `models/financial_statements.py:105,129,149,156`, `cli.py:207,1056,1064` |
| lookup with a fallback — `.get(k, 0)` | clean in diff. Pre-existing: `claude_extractor.py:1598,1606,1687,1901,1902,1963,2398,2407,2417,2418,2430,2467,2482`, `cli.py:1060` |
| bare or-default — `or 0.0` | clean in diff. Pre-existing: `claude_extractor.py:1716-1718` |
| money field defaulted to zero — `: float = 0.0` | clean in diff. Pre-existing: `models/` 42 (item 1). New field `printed_unit_in_millions` has no default |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean in diff. Pre-existing: `claude_extractor.py:1717-1718`, `cli.py:703` |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `pass1.units`, `pass1.share_units` absent or v2 string | yes | `parse_pass1` on v2 shape raises `Pass1ShapeError` naming both keys |
| `.printed` empty, `.page` 0, `.page` `True` | yes | each raises `Pass1ShapeError` naming `pass1.units.<sub>` |
| statement with no scale word (`(in dollars)`) | yes | both keys stop via `Pass1ShapeError` naming fields and reason |
| statement excepting shares (`except share data`) | yes | share scale stops via `Pass1ShapeError` |
| statement mentioning shares outside clauses (`excluding share data`, `other than shares`, `but not shares`, `shares in actual numbers`) | yes (F2 fixed) | `_named_outside_its_clauses` stops share scale and names field |
| unit statement fragment on page (`(in thousands)` on Okta p58) | yes (F1 fixed) | `unit_statement_on_page` returns `False`; Route B exits 2; Route A retries and stops |
| unit statement citing page not in income statement / diluted shares figures | yes (F6 fixed) | `_unit_statement_pages_allowed` stops; L3Harris p62 stops and names allowed pages |
| `printed_unit_in_millions` missing or `None` | yes | `BalanceSheet(year=2024)` raises `TypeError`; with `None`, `printed_unit`, `printed_total_check`, `_tolerance`, `_decimals` raise `ValueError` |
| statement field conversion does not list | yes | `_require_every_field_converted` stops |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | yes after conversion, on both routes. Pass 2 note scaling documented as item 77 (F3) |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean: `None if difference is None`, `if printed is None` |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | step 2 rows | 7 rows pass | `printed_scale` passes all 7 rows; stop rows through `parse_pass1` raise `Pass1ShapeError` naming field and reason | yes |
| 2 | millions filing does not move | 137 values identical | `load_session_extraction` on `WMT_v3.json` leaves all 137 values identical to base `WMT.json`; only addition is `printed_unit_in_millions = 1.0` | yes |
| 3 | thousands converted once | 11313.853 / 1370.0 / 5.0 | Chipotle converted once gives revenue 11313.853, diluted shares 1370.0, Pass 2 amount 5.0, unit 0.001; second conversion stops | yes |
| 4 | two scales | 2610.0 / 180.0 | Okta p58 gives revenue 2610.0 and diluted shares 180.0 | yes |
| 5 | not on its page stops | yes | `check` exits 2 naming field, text, page; Route A retries twice and stops after 3 calls with `ValueError` | yes |
| 6 | real statements found | 8 found | Walmart p21, AbbVie p21, Chipotle p29, Okta p58, LHX p35 (2026), p41 (2025), p28 (2023), p17 (2023) all `found=True` on cited page and `False` on page + 1 | yes |
| 7 | threshold at 1 printed unit | OK / FAIL, same text | Parser OK/FAIL at 0.001 tolerance; CLI and template header print `FAIL above 0.001 $M: 1 in the filing's printed unit, and 1 printed unit = 0.001 $M` | yes |
| 8 | v2 refused with remedy | yes | `ValueError` names `session-extraction-v2`, `session-extraction-v3`, `units`, `share_units`, and the remedy | yes |
| 9 | old pickle refused | yes | Pickle with `p11a-printed-lines-v1` refused by `_load_cache` naming `p14a-units-in-millions-v1` | yes |
| 10 | Walmart end to end | identical except labels | `cli.py --session-file WMT_v3.json`: Stages 1-10 identical to base, revenue 680,985, PV TV 214,819, implied price $28.02, downside -73.1%, 0 LLM calls | yes |
| 11 | no paid call | 0 | 0 calls, `[]` network attempts; socket connect mocked to raise on attempt | yes |
| 12 | reds named | 293 red | 293 failed, 619 passed (gate form: 291 failed, 619 passed: 163 Group A, 121 Group B, 6 Group E, 1 Group V) | yes |
| 13 | gates | ruff 4, mypy 9/4, census 65 | ruff 4 errors (BLE001), mypy 9 errors in 4 files, census 65, route check 200 | yes |
| F1 | whole statement match & fragment reject | pass | Okta p58 `(in thousands)` returns `False`; full statement returns `True`; scan across 16 filings (861 parenthesised groups) finds 861/861 with 0 fragment false positives | yes |
| F2 | stop on share mention outside clauses | pass | `(In millions, excluding share data)`, `(in millions, other than shares)`, `(in millions, but not shares)`, `(in millions; shares in actual numbers)` stop share scale | yes |
| F4 | template balance check cells format decimals | pass | `templates/_statements.html` formats balance check cells with `bs.printed_unit_decimals()`, printing `+0.002` and `FAIL` for 1,000.002 vs 1,000.000 | yes |
| F6 | statement pages tied to governed figures | pass | `units.page` restricted to income statement line pages; `share_units.page` restricted to `units.page` union `diluted_shares` pages. LHX 2026 p62 stops; Walmart, Okta, Chipotle, AbbVie pass | yes |

## Findings

None. All findings F1 to F8 and programmer findings 4 and 6 have been resolved and verified.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 | `models/financial_statements.py` money fields `= 0.0`; `claude_extractor.py` `.get(…)` sites | no |
| 72 | `cli.py` conditional zeros | no |
| 53 | `session_extraction.py` imports `_NRI_SCHEMA` | import block widened, line unchanged |
| 63 | no text layer stops unit check | recorded by programmer |
| 64 | page check joined-line form | no |
| 10 | D&A subtraction in parser | no |
| 77 | Pass 2 schema asks for amount in "same units as financials" | docs updated to cite item 77 |

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| F1 (blocker) | fixed | `unit_statement_on_page` requires full parenthesised group or whole text line equality. Okta p58 fragment `(in thousands)` returns `False`; full statement returns `True`. 16-filing scan (861 groups) confirms 861/861 found and 0 false positive fragments |
| F2 (major) | fixed | `_named_outside_its_clauses` stops share scale when statement mentions shares outside `<shares> in <scale>` clauses (`excluding share data`, `other than shares`, `but not shares`, `shares in actual numbers`) |
| F3 (escalated) | fixed | Docs in `docs/2-rules/llm-boundary.md:102-106,116-118` and `docs/4-conventions/units-and-signs.md:46-51` updated to document Pass 2 schema unit behavior and backlog item 77 |
| F4 (minor) | fixed | `templates/_statements.html:358-363` formats balance check printed, mapped, and difference cells with `bs.printed_unit_decimals()` (`+0.002`, not `+0`) |
| F5 (note) | fixed | Conversion occurs exactly once per filing before merge on both routes; documented |
| F6 (requirement) | fixed | `_unit_statement_pages_allowed` restricts `units` to income statement line pages, `share_units` to `units.page` union `diluted_shares` pages. LHX 2026 p62 stops; real filings pass |
| F7 (note) | fixed | `_GENERIC_SUBJECT_WORDS = frozenset({"amounts"})` in code matches `docs/3-architecture/extraction.md:347` |
| F8 (note) | fixed | `claude_extractor.py:2267` dead code replaced with `raise AssertionError` |
| Programmer finding 4 | fixed | Removed unused `BalanceSheet` from `cli.py` import block; `bs.printed_total_check(difference)` |
| Programmer finding 6 | fixed | Stale known defect row for `_run_nri_pass` removed from `docs/3-architecture/extraction.md` |

## Verdict

`approved`

All blocker, major, minor, and note findings from round 1 have been resolved in code and documentation. Guard checks, Rule 3 reading checks, and done-criteria 1 to 13 plus the round 2 amendment criteria all pass on independent execution. The test suite produces the expected 293 failures (291 fixture/field + 2 known reds), gates are clean, and zero paid API calls or network attempts were made.
