---
agent: code_reviewer
assignment: P14b-note-figures
round: 2
verdict: approved
---

# Review of P14b-note-figures, round 2

Programmer entry: `.agent/journal/2026-10-04T2130-programmer-p14b-note-figures.md`

## The guard checks

Run over the assignment's **Files in scope** (`ingestion/claude_extractor.py`, `docs/3-architecture/extraction.md`, `docs/2-rules/llm-boundary.md`).

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean (0 hits) |
| lookup with a fallback — `.get(k, 0)` | clean in unit; 5 existing hits in `ingestion/claude_extractor.py` (lines 1891, 2108, 2109, 2158, 2673) untouched |
| bare or-default — `or 0.0` | clean in unit; 3 existing hits in `_call_gemini` (lines 1920-1922) untouched |
| money field defaulted to zero — `: float = 0.0` | clean (0 hits) |
| `**kwargs` on a calculation function | clean (0 hits) |
| `getattr(` on a name from outside the file | clean in unit; 2 existing hits in `_call_gemini` (lines 1921-1922) untouched |
| dict of functions keyed by data | clean (0 hits) |
| model client imported outside `ingestion/` | clean (0 hits in `models/`, `analysis/`, `api/`) |

## Rule 3, by reading

The greps catch the four written forms. This table catches the rest. For every value
the unit reads, ask: if it were missing, what happens?

| Value | Stops and names it? | Evidence |
|---|---|---|
| `data["historical_years"]` in `_row_scale_failures` | stops and raises `KeyError('historical_years')` | `ingestion/claude_extractor.py:1583`, verified by scratch test |
| `entry[field]` for line fields in `historical_years` | stops and raises `KeyError('<field>')` | `ingestion/claude_extractor.py:1587`, verified by scratch test |
| `data["latest_balance_sheet"]` in `_row_scale_failures` | stops and raises `KeyError('latest_balance_sheet')` | `ingestion/claude_extractor.py:1597`, verified by scratch test |
| `balance[field]` for line fields in `latest_balance_sheet` | stops and raises `KeyError('<field>')` | `ingestion/claude_extractor.py:1602`, verified by scratch test |
| `page_texts[page]` in `_row_scale_failures` | stops and raises `KeyError(page)` if missing from text dictionary | `ingestion/claude_extractor.py:1637` |
| `page_texts[p]` in candidate check | stops and raises `KeyError(p)` if missing from text dictionary | `ingestion/claude_extractor.py:1650` |
| `units.money.scale.word` / `units.shares.scale.word` | stops in `_filing_units` if statements are missing or scale cannot be read | `ingestion/claude_extractor.py:1573-1577` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean — Pass 1 note/MD&A figures are copied as printed, unit scale verified by Check B1, and converted to millions once by `convert_filing_to_millions` |
| percentages converted at the route boundary, once | clean — no percentage inputs added or touched |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean — no falsy conditionals introduced |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean — verified no imports of `ingestion/` or `api/` |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | the prompt allows option B | pass | pass (`grep -n` shows Option B rule at line 310; all 4 prompt occurrences of "convert" forbid conversion) | Agree |
| 2 | Walmart is clean | pass | pass (`session_extraction check extractions/WMT.json` exits 0; `89 checked, 4 pages, 0 pages not confirmed`) | Agree |
| 3 | a row on a page with no unit statement stops | pass | pass (copy of WMT with revenue on page 2: `check` exits 2, naming page 2, `money figures`, "no unit statement on page 2 or 1", and that row) | Agree |
| 4 | a row under another scale stops | pass | pass (scratch call on Chipotle 2025 PDF, units `millions`: 1 failure naming page 29, expected `millions`, found `(in thousands...)`) | Agree |
| 5 | two scales, read by kind | pass | pass (scratch call on Okta 2026 PDF: Case A 0 failures; Case B with `share_units` millions: 1 failure for diluted shares on page 58) | Agree |
| 6 | the stated limit holds as stated | pass | pass (scratch call on LHX 2026 PDF page 62 with two statements: 0 failures with `millions`, 0 failures with `thousands`) | Agree |
| 7 | route A stops after its retries | pass | pass (scratch script with stubbed `_call_llm` and blocked sockets on Walmart PDF: `ValueError` after 3 calls, 0 network calls, stop message names `1 row scale failure(s)`) | Agree |
| 8 | Walmart does not move | pass | pass (`cli.py --session-file extractions/WMT.json`: stages 1-10 clean in 2s, PV of TV $214,819M, Implied Price $28.02, Downside -73.1%, matches baseline `525b98f`) | Agree |
| 9 | the gates do not get worse | pass | pass (Ruff 4 errors `BLE001`; Mypy 8 errors in 3 files with `claude_extractor.py` clean; Census 65; `GET /` 200; Guard 48/48) | Agree |
| 10 | the false-stop risk is measured | pass | pass (Script run over all 16 filings: 320 pages checked, 249 OK, 71 NONE, 0 primary statement pages lack scale; per-filing counts match) | Agree |
| 11 | every red test is named | pass | pass (2 deliberate red tests in `*_rule3_red.py`; 21 tests in `test_p14b_note_figures.py` raise `KeyError` on incomplete synthetic fixtures, to be locked/updated by tester in round 2; 1032 other tests pass) | Agree |

## Findings

None.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 8 (blanket `except Exception`) | `api/routes_valuation.py:445, 729`, `cli.py:1168`, `tests/test_e2e_all_googl.py:106` | No |
| 11 (type errors) | `analysis/projector.py`, `api/routes_upload.py`, `api/routes_valuation.py` | No |

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| F1 | fixed | Removed `.get()` and `if field in` presence checks in `_row_scale_failures`; all keys accessed via direct `[]`. Verified via scratch tests raising `KeyError('historical_years')`, `KeyError('revenue')`, `KeyError('latest_balance_sheet')`, and `KeyError('cash')`. |
| F2 | fixed | Criterion 10 scan re-measured across all 16 filings with exact lead script: 320 pages checked, 249 OK, 71 NONE. 0 primary statement pages lack a scale. Filing-by-filing counts match programmer's round 2 table. |
| F3 | fixed | Updated `docs/2-rules/llm-boundary.md` and `docs/3-architecture/extraction.md` to state that a row citing a page beyond the PDF or with no text layer also fails Check B1 and stops the run in both routes (`check` exits 2). |
| F4 | fixed | Updated Route A stop message, docstrings, comments, and retry prompt text in `_run_financials_pass` to distinguish and count unit statement and row scale failures (`kinds_str`). Verified via scratch test. |
| F5 | fixed | Added `elif page == 1:` formatting `"no unit statement on page 1"` instead of `"page 1 or 0"`. Verified via scratch test. |
| F6 | fixed | Stated wider limit in both docs files (`llm-boundary.md` and `extraction.md`): Check B1 confirms presence of a parenthesised scale statement on the page or preceding page, but does not guarantee the statement governs a specific table. |

## Verdict

`approved`

All six review findings (F1 to F6) from round 1 have been fully addressed and verified by direct execution. Rule 3 fallbacks have been removed in favor of strict `[]` indexing; Route A error reporting and docstrings distinguish row scale failures; documentation files accurately reflect Check B1's stop behavior and architectural limits; and Criterion 10 was verified across all 16 filings with 0 primary statement false stops. The unit is approved.
