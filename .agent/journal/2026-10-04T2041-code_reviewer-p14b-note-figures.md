---
agent: code_reviewer
assignment: P14b-note-figures
round: 1
verdict: approved
---

# Review of P14b-note-figures, round 1

Programmer entry: `.agent/journal/2026-10-04T2011-programmer-p14b-note-figures.md`

## The guard checks

Run over the assignment's **Files in scope** (`ingestion/claude_extractor.py`, `docs/3-architecture/extraction.md`, `docs/2-rules/llm-boundary.md`):

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean in diff (0 hits across files in scope) |
| lookup with a fallback — `.get(k, 0)` | clean in diff. 2 hits in `ingestion/claude_extractor.py:1581, 1596` (`data.get("historical_years", [])` and `data.get("latest_balance_sheet", {})` in `_row_scale_failures`), both answered by programmer; 6 pre-existing hits outside diff |
| bare or-default — `or 0.0` | clean in diff. 3 pre-existing hits in `ingestion/claude_extractor.py:1918-1920` (token counts), untouched |
| money field defaulted to zero — `: float = 0.0` | clean in diff (0 hits) |
| `**kwargs` on a calculation function | clean in diff (0 hits) |
| `getattr(` on a name from outside the file | clean in diff. 2 pre-existing hits in `ingestion/claude_extractor.py:1919-1920` on Gemini usage metadata, untouched |
| dict of functions keyed by data | clean in diff (0 hits) |
| model client imported outside `ingestion/` | clean in diff (0 hits across `models/`, `analysis/`, `api/`) |

**A hit is a question, not automatically a finding.** The `.get` calls for `historical_years` and `latest_balance_sheet` provide empty container defaults after `pass1_problems` has already validated shape; if empty, 0 rows are checked and the check exits cleanly.

## Rule 3, by reading

The greps catch the four written forms. This table catches the rest. For every value the unit reads, ask: if it were missing, what happens?

| Value | Stops and names it? | Evidence |
|---|---|---|
| `units` in `_row_scale_failures` | Stops: `_filing_units` raises `KeyError` naming `units` if missing; earlier `pass1_problems` halts on missing unit statement | `ingestion/claude_extractor.py:1571` |
| `share_units` in `_row_scale_failures` | Stops: `_filing_units` raises `KeyError` naming `share_units` if missing; earlier `pass1_problems` halts | `ingestion/claude_extractor.py:1571` |
| `historical_years` in `_row_scale_failures` | Iterates `[]`, 0 rows checked, returns clean 0 checked; validated earlier by `pass1_problems` | `ingestion/claude_extractor.py:1581` |
| `latest_balance_sheet` in `_row_scale_failures` | Evaluates `{}` to falsy, skips B/S row checks; validated earlier by `pass1_problems` | `ingestion/claude_extractor.py:1596` |
| `entry["year"]` and `balance["year"]` | Stops: raises `KeyError` naming `'year'` if missing | `ingestion/claude_extractor.py:1582, 1598` |
| `line["page"]` and `line["label"]` | Stops: raises `KeyError` if missing; if page > page_count or page has no text layer, halts with `_CheckFailure` naming page | `ingestion/claude_extractor.py:1588-1594, 1604-1610, 1628-1645` |
| `pdf_bytes` in `_row_scale_failures` | Stops: invalid PDF bytes raises `ValueError` in `_read_cited_pages` via `pypdf.PdfReader` | `ingestion/claude_extractor.py:1617` |
| Unit statements on page / preceding page | Stops: if no candidate scale matches expected filing scale, creates `_CheckFailure` naming page, expected scale, and citing rows; Route A retries then raises `ValueError`, Route B exits 2 | `ingestion/claude_extractor.py:1668-1679, 2496-2503, 2929-2932` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean: `_row_scale_failures` validates printed scale matches filing scale words; conversion to millions happens once downstream in `convert_filing_to_millions` |
| percentages converted at the route boundary, once | clean: not applicable to this diff |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean: `if field in entry`, `if balance`, `if page > 1`, and `if expected in candidate_words` all test explicit containment or existence |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean: `analysis/` was untouched |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | the prompt allows option B | pass | Prompt contains Option B rule (`claude_extractor.py:310-314`). All occurrences of "convert" in prompt enforce prohibitions against conversion. `interest_expense` note instruction retained (`:319-320`). | Agree |
| 2 | Walmart is clean | pass | `session_extraction check extractions/WMT.json` exits 0. Output includes `Row unit scales looked up on their cited pages: 89 checked, 4 pages, 0 pages not confirmed.` | Agree |
| 3 | a row on a page with no unit statement stops | pass | Scratch copy `/tmp/wmt_p2.json` with revenue row on page 2 exits 2 with `page 2 (money figures): expected millions, no unit statement on page 2 or 1. Rows citing page 2: 'Total revenues' (revenue, year 2026).` | Agree |
| 4 | a row under another scale stops | pass | Real Chipotle 2025 PDF with expected `millions` and revenue row on page 29 yields 1 failure: `page 29 (money figures): expected millions, found (in thousands, except per share data). Rows citing page 29: 'Revenue' (revenue, year 2025).` | Agree |
| 5 | two scales, read by kind | pass | Real Okta 2026 PDF: page 58 with `units` millions and `share_units` thousands produces 0 failures; with `share_units` millions produces 1 failure for `share count`. | Agree |
| 6 | the stated limit holds as stated | pass | Real L3Harris 2026 PDF: page 62 with `(In millions)` and `(In thousands)` produces 0 failures with `units` millions, and 0 failures with `units` thousands. | Agree |
| 7 | route A stops after its retries | pass | Real Walmart PDF with stubbed `_call_llm` and revenue row on page 2 (sockets guarded): exhausts 2 retries (3 calls total, 0 network attempts) and raises `ValueError` naming page 2 scale failure. | Agree |
| 8 | Walmart does not move | pass | `cli.py --session-file extractions/WMT.json` runs clean with identical pipeline stages 1-10 plus new summary line; implied price $28.02. | Agree |
| 9 | the gates do not get worse | pass | Ruff: 4 errors (`BLE001`, unchanged). Mypy: 8 errors in 3 files (`claude_extractor.py` clean, unchanged). Census: 65 (unchanged). Guard: 48/48 (unchanged). `GET /`: 200 (unchanged). | Agree |
| 10 | the false-stop risk is measured | pass | Scanned all 16 filings: 0 false stops on primary statement pages (all have readable scales on page or page before). Note/MD&A occurrences without scale statements match programmer table. | Agree |
| 11 | every red test is named | pass | Pytest run: 33 failed, 1001 passed. Exactly 2 tests red on purpose (`test_projector_rule3_red.py`, `test_routes_session_rule3_red.py`); 31 fixture tests red on synthetic page 52 missing unit headers (to be addressed by tester in `P14b-note-figures-tests`). | Agree |

## Findings

None.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 (silent zero-default sites) | `ingestion/claude_extractor.py` | No |
| 10 (D&A subtraction buried in parser) | `ingestion/claude_extractor.py:479` | No |
| 51 (arithmetic check WARN branch dead) | `ingestion/claude_extractor.py:2026` | No |
| 53 (session loader imports `_NRI_SCHEMA` privately) | `ingestion/claude_extractor.py` | No |
| 61 (retry loop exception swallowing) | `ingestion/claude_extractor.py` | No |
| 63 (filing with no text layer uses up retries) | `ingestion/claude_extractor.py:1530` | No |
| 64 (page check multi-row label binding) | `ingestion/claude_extractor.py:1396` | No |
| 73 (bad first Pass 2 replies stop with no retry) | `ingestion/claude_extractor.py:2570` | No |
| 74 (retry `OverflowError`) | `ingestion/claude_extractor.py:1931` | No |
| 78 ("already converted" guard sees B/S only) | `ingestion/claude_extractor.py:3060` | No |
| 79 (Route A unit stop does not name PDF) | `ingestion/claude_extractor.py:2497` | No |
| 80 (arithmetic check table in printed units without label) | `ingestion/claude_extractor.py:2045` | No |

## Earlier findings — re-reviews only

None (round 1).

## Verdict

`approved`

Work unit `P14b-note-figures` correctly implements Rule 1 Option B in Pass 1 and Check B1 in Python (`_row_scale_failures`). All Pass 1 printed rows across `historical_years` and `latest_balance_sheet` are verified against parenthesised unit statements on the citing page or preceding page. Missing or mismatched scales cleanly stop execution across Route A (retries exhausted -> `ValueError`) and Route B (`unit_statement_page_failures` -> exit code 2). All 11 done-criteria were verified by execution with empty API keys and zero paid API calls. All quality gates remain stable. Ready for tester dispatch on `P14b-note-figures-tests`.
