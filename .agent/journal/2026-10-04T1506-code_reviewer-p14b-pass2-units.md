---
agent: code_reviewer
assignment: P14b-pass2-units
round: 1
verdict: approved
---

# Review of P14b-pass2-units, round 1

Programmer entry: `.agent/journal/2026-10-04T1437-programmer-p14b-pass2-units.md`

## The guard checks

Run over the assignment's **Files in scope** (`ingestion/claude_extractor.py`, `ingestion/session_extraction.py`, `models/financial_statements.py`, `cli.py`):

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean in diff. 7 pre-existing hits in `models/financial_statements.py` (108, 132, 152, 159) and `cli.py` (207, 1056, 1064), untouched |
| lookup with a fallback — `.get(k, 0)` | clean in diff. 14 pre-existing hits (13 in `claude_extractor.py`, 1 in `cli.py`), untouched |
| bare or-default — `or 0.0` | clean in diff. 3 pre-existing hits in `claude_extractor.py` (1910-1912) in token counter, untouched |
| money field defaulted to zero — `: float = 0.0` | clean in diff (`page`, `printed_units`, `units_page` added with no default). 40 pre-existing hits in `models/financial_statements.py` (backlog item 1), untouched |
| `**kwargs` on a calculation function | clean (0 hits) |
| `getattr(` on a name from outside the file | clean in diff. 3 pre-existing hits (2 in `claude_extractor.py:1911-1912`, 1 in `cli.py:703`), untouched |
| dict of functions keyed by data | clean (0 hits) |
| model client imported outside `ingestion/` | clean (0 hits) |

## Rule 3, by reading

The greps catch the four written forms. This table catches the rest. For every value the unit reads, ask: if it were missing, what happens?

| Value | Stops and names it? | Evidence |
|---|---|---|
| `amount` in Pass 2 response / session item | Stops: raises `ValueError` in `_parse_nri_response` (`:2163-2172`), records problem in `_pass2_shape_problems` (`:581`) | Criterion 2 & 7e tests |
| `page` in Pass 2 response / session item | Stops: raises `ValueError` in `_parse_nri_response` (`:2175-2185`), records problem in `_pass2_shape_problems` (`:585`) | Criterion 7 & pytest fixtures |
| `units` in Pass 2 response / session item | Stops: raises `ValueError` in `_parse_nri_response` (`:2188-2198`), records problem in `_pass2_shape_problems` (`:589`) | Criterion 7 & pytest fixtures |
| `units.printed` in Pass 2 response / session item | Stops: raises `ValueError` in `_parse_nri_response` (`:2199-2209`), records problem in `_pass2_shape_problems` (`:597`) | Criterion 7d test |
| `units.page` in Pass 2 response / session item | Stops: raises `ValueError` in `_parse_nri_response` (`:2210-2220`), records problem in `_pass2_shape_problems` (`:602`) | Criterion 7b, 7c tests |
| Inline unit scale value (`pass2_amount_scale`) | Stops: raises `ValueError` if inline number != `amount` (`:794`) | Criterion 2 & 7e tests |
| Statement scale word (`pass2_amount_scale`) | Stops: delegates to `printed_scale`; raises `ValueError` if scale word unreadable/absent | Criterion 2 error cases |
| Pass 2 figure on cited page (`_pass2_item_failures`) | Stops: raises `ValueError` in route A (`:2610`), exit 2 in route B `check` (`:631`) | Criterion 7a & 8 tests |
| Pass 2 inline unit words on cited page (`_pass2_item_failures`) | Stops: `units_page == page` required, substring match required; raises `ValueError` in route A, exit 2 in route B | Criterion 7c test |
| Pass 2 statement unit words on cited page (`_pass2_item_failures`) | Stops: `units_page in (page, page - 1)` required, `unit_statement_on_page` required; raises `ValueError` in route A, exit 2 in route B | Criterion 7b, 7d tests |
| Session format version (`_read_session_json`) | Stops: raises `ValueError` on v3 format naming v3, v4, new keys, and remedy (`:287`) | Criterion 9 test |
| CLI cache format marker (`cli._load_cache`) | Stops: raises `ValueError` on old cache markers naming `p14b-pass2-units-v1` (`:358`) | Criterion 10 test |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean: `convert_filing_to_millions` converts each Pass 2 item via `pass2_amount_scale(item.printed_units, item.amount).in_millions`, never with filing money scale |
| percentages converted at the route boundary, once | clean: not applicable to Pass 2 |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean: all 27 new/touched `if` branches test explicit types, explicit `None` checks (`page_text is None or not page_text.strip()`), positive numbers (`amount <= 0`), or boolean conditions |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean: `analysis/` was not touched |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | no text asks model to convert | 0 hits | `grep -rn "same units as financials" ingestion/` returned 0 hits (exit 1) | Agree |
| 2 | the scale reader | 5 converted, 4 stopped | 5 valid pairs scaled with exact fractions (billions=1000, millions=1, thousands=1/1000); 4 invalid pairs raised `ValueError` naming reason | Agree |
| 3 | Walmart v4 is clean | `check` exits 0 | `session_extraction check /tmp/wmt_v4_test.json`: exit 0; 89 of 89 printed lines found; 4 of 4 Pass 2 items confirmed | Agree |
| 4 | Walmart amounts in millions | [700.0, 2075.0, 794.0, 3027.0] | `session.non_recurring`: amounts `[700.0, 2075.0, 794.0, 3027.0]`; hand arithmetic matches | Agree |
| 5 | Walmart end to end does not move | $28.02, TV PV 214,819M | `cli.py --session-file /tmp/wmt_v4_test.json`: Revenue 713,163; EBIT Adj 30,525; TV PV 214,819M; EV 272,116M; Equity 224,757M; Price $28.02; Downside -73.1% | Agree |
| 6 | a filing in thousands | 5.2 $M for both | Stub filing in thousands: `$5.2 million` -> 5.2 $M; `5200` under `(in thousands)` -> 5.2 $M | Agree |
| 7 | each check stops and names item | 5 edits exit 2 | Re-executed all 5 edits (a)-(e): each exited with code 2, naming item, text, and page/mismatch | Agree |
| 8 | route A stops on mis-cited item | ValueError, 0 network calls | Stubbed `_call_llm` with blocked sockets: mis-cited item (2076 on p.22) raised `ValueError` naming item and year; valid item returned items with `page`, `printed_units`, `units_page` set | Agree |
| 9 | a v3 file is refused with remedy | ValueError naming v3, v4, remedy | `load_session_extraction("extractions/WMT.json")` raised `ValueError` naming `session-extraction-v3`, `session-extraction-v4`, `page`, `units`, and `extract-filing` remedy | Agree |
| 10 | old cache refused | ValueError naming p14b marker | `cli._load_cache` on pickle with old marker raised `ValueError` naming expected marker `p14b-pass2-units-v1` | Agree |
| 11 | gates do not get worse | ruff 4, mypy 9, census 65, route 200 | ruff 4 (all `BLE001`); mypy 9 in 4 files; census 65; `GET /` status 200 | Agree |
| 12 | every red test is named | 87 failures grouped | Gate suite (`--ignore-glob="*_rule3_red.py"`): 87 failed, 867 passed. Full suite: 89 failed, 867 passed (2 red on purpose + 87 expected). Breakdown: 58 from `NonRecurringItem` constructor signature, 28 from session v3 / pass2 fixtures missing `page`/`units`, 1 from CLI cache marker | Agree |

## Findings

None.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 (zero defaults in models) | `models/financial_statements.py` (40 float fields) | No (`page`, `printed_units`, `units_page` added with no default) |
| 8 (blanket `except Exception`) | `cli.py:1165` | No |
| 10 (D&A in Pass 1 parser) | `ingestion/claude_extractor.py:1260` | No |
| 51 (dead `WARN` branch) | `ingestion/claude_extractor.py:270` | No |
| 53 (private `_NRI_SCHEMA` import) | `ingestion/session_extraction.py:84` | No |
| 61 (AssertionError after retry loop) | `ingestion/claude_extractor.py:2532` | No |
| 63 (filing with no text layer) | `ingestion/claude_extractor.py:1611, 1647` | No |
| 64 (page check joined-line form) | `ingestion/claude_extractor.py:1460` | No |
| 70 (PV of terminal value variance) | stage 10 | No |
| 72 (conditional zeros in cli) | `cli.py:1056, 1064` | No |
| 73 (first Pass 2 reply stops without filing name) | `ingestion/claude_extractor.py:2570` | No |
| 74 (OverflowError/RecursionError in Pass 2) | `ingestion/claude_extractor.py:2600` | No |
| 78 (already converted guard sees BS only) | `ingestion/claude_extractor.py:3145` | No |
| 79 (route A unit stop names field/text/page but not PDF) | `ingestion/claude_extractor.py:2612` | No |
| 80 (arithmetic check in printed units) | `ingestion/claude_extractor.py:1568` | No |

## Verdict

`approved`

The unit satisfies all requirements of assignment `P14b-pass2-units` and backlog item 77 (user decision "fix 77a" of 2026-10-04). Pass 2 items copy figures, cited pages, and unit statement words as printed without model conversions; Python scales each item individually via pure function `pass2_amount_scale`. Both route A and route B confirm figure and unit statements on their cited pages and stop on any discrepancy. Session extraction format is cleanly upgraded to v4 with v3 refused naming remedies. CLI cache format is updated to `p14b-pass2-units-v1`. All 12 done-criteria pass upon re-execution, the gates remain stable, and all 87 test failures in the suite stem strictly from expected signature and fixture changes to be resolved by the tester in `P14b-pass2-units-tests`.
