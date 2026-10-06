---
agent: session-extraction (route B, extract-filing skill)
assignment: extract Walmart 10-K filings through route B into extractions/WMT.json
round: 1
status: complete
files_touched: [extractions/WMT.json, .agent/journal/2026-10-06T1109-session-extraction-wmt.md]
verdict: n/a
---

# session-extraction-wmt — Walmart FY2022–FY2026 read from three 10-K PDFs in this session

## What I did

Ran the `extract-filing` skill end to end on `10K_filings/WMT` (three PDFs: fiscal
2024, 2025, 2026). `SE plan` wrote the skeleton unchanged; I read the income
statement, cash flow statement and (filing 2 only) balance sheet pages through
`SE text`, wrote each filing's `pass1` into `extractions/WMT.json` as soon as it was
read, then each `pass2`, then set `extracted_by`. `SE check extractions/WMT.json`
exits 0: 129 printed lines checked and 129 found, 6 unit statements found, 14 Pass 2
figures and unit texts found, every printed subtotal and both balance sheet totals
agree with Python's sums with a difference of 0. No paid API call was made
(`ANTHROPIC_API_KEY= GEMINI_API_KEY=` in front of every command).

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | `SE check extractions/WMT.json` exits 0 | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe -m ingestion.session_extraction check extractions/WMT.json` -> `EXIT=0`, "Clean: every key present, every line well formed, every PDF unchanged, both unit statements found on their pages, every printed subtotal and total agrees with Python's sum of the lines, and every printed line was found on the page it cites." |
| 2 | Every figure read through `SE text` in this run | pass | pages read recorded in `pages_read`; filing 0 pass 1 45-49, filing 1 pass 1 45-48, filing 2 pass 1 21-23 |
| 3 | Balance sheet ties | pass | 2026 Total Assets 284,668 printed vs 284,668 derived, diff +0; Total L + E 284,668 vs 284,668, diff +0 |
| 4 | No figure adjusted to pass a check | pass | no check ever failed; nothing was changed after a check |
| 5 | Nothing written outside `extractions/` and `.agent/journal/` | pass | only `extractions/WMT.json` and this file |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| filing 0 `units`/`share_units` = `(Amounts in millions)` on PDF page 46 | The FY2024 PDF breaks the income statement across PDF pages: the title and `(Amounts in millions, except per share data)` are at the foot of page 45, every data row is on page 46. `_unit_statement_pages_allowed` requires `units` to cite a page an income statement row cites, i.e. page 46. Page 46 prints `(Amounts in millions)` as the Consolidated Statements of Comprehensive Income header. | Citing page 45 would stop the run (exit 2) on a correct reading. Both statements read as `millions` (`printed_scale`), so no scale moved. Reported to the user. |
| `Finance lease right-of-use assets, net` 6,123 -> `other_non_current_assets`, not `ppe_net` | The filing prints `Property and equipment, net` as its own row; the skill says "If the filing prints one row that is the whole field, list that one row", and "a row that matches no named field goes into its section's CATCH-ALL list". | Putting it in `ppe_net` would be my accounting judgement, not the filing's layout. Both land on the asset side, so the total assets check is unaffected. |
| Finance lease obligations in `short_term_debt` / `long_term_debt`; operating lease obligations in the catch-alls | user decision "83a", `P14d-finance-leases`; the Pass 1 prompt says the same | — |
| `revenue` = the printed `Total revenues` row, not `Net sales` + `Membership and other income` | "Never list a printed total together with the rows it totals"; the printed total is the whole field | — |
| FY2026 self-insured general liability claims expense "of approximately $0.9 billion" (filing 2, page 16) NOT flagged as a Pass 2 item | The MD&A names it as the driver of a higher recurring expense ("rising costs to resolve claims across retail and related industries"), not as a one-time, unusual or infrequent item. The Pass 2 prompt says "Only flag items with clear evidence in the filing. Do NOT guess." | Flagging it would add a rule the prompt does not state. Raised to the user as a judgement call with its page. |
| FY2023 "$0.2 billion dividend from one of our investments" (filing 0, page 36) NOT flagged | Not one of the kinds the Pass 2 prompt lists, and the filing does not call it non-recurring | Same reason as above |

**A code change made to reach a target number, rather than on a reason, is
forbidden.** No code was changed. No figure was changed after any check.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| a Pass 1 key | stops and names the key (`pass1_problems`) | route B's loader stops; `check` exits 2 |
| a unit statement not found on its page | stops and names the field, text and page | `_unit_statement_failures`, `_UNIT_NOT_CONFIRMED_STOPS` |
| a row whose scale cannot be confirmed on its page or the page before | stops (check B1) | `_row_scale_failures`; `check` exits 2 |
| a Pass 2 figure or unit text not found on its page | failed check, shown and kept | `_pass2_item_failures` |
| `extracted_by.model` | stops and names it | observed: "'extracted_by.model' is None" stopped the run before it was set |

No "defaults to" row: nothing in this run fell back to a value.

## Measurements

I did not run the test suite and did not run `pytest` at all (another agent is
measuring it). I did not run `cli.py`.

`SE check extractions/WMT.json`, exit 0:

- filing 0 (FY2024 10-K): printed lines 63 checked / 63 found; unit statements 2/2;
  row unit scales 63 checked over 2 pages, 0 not confirmed; Pass 2 items 9/9.
  Arithmetic: 2022/2023/2024 Oper. Income and Net Income all diff +0; Gross Profit
  SKIP (the filing prints no gross profit row).
- filing 1 (FY2025 10-K): printed lines 20/20; unit statements 2/2; row unit scales
  20 over 2 pages; Pass 2 items 2/2. 2025 Oper. Income +0, Net Income +0.
- filing 2 (FY2026 10-K): printed lines 46/46; unit statements 2/2; row unit scales
  46 over 3 pages; Pass 2 items 3/3. 2026 Oper. Income +0, Net Income +0,
  Total Assets +0, Total L + E +0.
- Merged: years [2022, 2023, 2024, 2025, 2026], balance sheet [2026],
  non-recurring items 13 (14 written, see the finding below).

Three figures with their pages (one per filing):

| Figure | Value | Page |
|---|---|---|
| FY2024 Total revenues | 648,125 | filing 0, PDF page 46 |
| FY2025 Net cash provided by operating activities | 36,443 | filing 1, PDF page 48 |
| FY2026 Total shareholders' equity | 105,887 | filing 2, PDF page 22 |

## Expected values — testers only

n/a — this is an extraction, not a test.

## What I did not do

- Did not value the extraction (`cli.py` was explicitly out of scope for this run).
- Did not run `pytest` or any test.
- Did not change any code, including the two defects below.

## Findings for the orchestrator

1. **`merge_filing_extractions` drops a distinct non-recurring item.** The dedupe key
   is `(year, amount, direction)` (`claude_extractor.py:2846`). Filing 0 Pass 2 holds
   two genuinely different printed FY2022 items — the Asda divestiture loss of
   `$0.2 billion` (page 66) and the Seiyu divestiture loss of `$0.2 billion`
   (page 67). Both are year 2022, amount 200.0 after conversion, direction
   `add_back`, so the Seiyu item is silently discarded: 14 items written, 13 merged.
   Nothing in the output says an item was dropped. Two distinct one-time losses of the
   same size in the same year is not rare.
2. **`SE prompt ... --pass 2` crashes on a cp1252 console.** On this Windows machine
   `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe -m ingestion.session_extraction prompt extractions/WMT.json --filing 0 --pass 2`
   printed `ERROR: 'charmap' codec can't encode character '→' in position 2992`
   and exited 2 after printing only the header of the system prompt. The `->` arrows
   in the Pass 2 prompt's `direction` rules are the cause. `PYTHONIOENCODING=utf-8`
   works around it. `--pass 1` is unaffected. An agent that does not know the
   workaround cannot read the Pass 2 prompt on this machine.
3. **A unit statement can fall on the PDF page before every row it governs.** In the
   FY2024 Walmart PDF the income statement's own
   `(Amounts in millions, except per share data)` is at the foot of PDF page 45 and
   every data row is on page 46, so `_unit_statement_pages_allowed` rejects the
   statement that actually governs the figures. Check B1 (`_row_scale_failures`)
   already allows "the page before"; `_unit_statement_pages_allowed` does not. Here a
   second printed statement on page 46 of the same scale made it passable; a filing
   without one would stop on a correct reading. Worth a backlog item.
