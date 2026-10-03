---
agent: programmer
assignment: P11a-printed-lines
round: 1
status: partial
files_touched: []
verdict:
---

# P11a-printed-lines (run 2) — Pass 1 returns printed lines; Python does every sum

> In progress. Opened 2026-10-03T1010 at commit cd7101d. Run 1
> (`2026-10-02T2233-programmer-p11a-printed-lines.md`) changed nothing.

## What I did

(in progress)

### Progress log

- Code written in `models/financial_statements.py` (memo totals, check status),
  `ingestion/claude_extractor.py` (schema, prompt, `printed_line_problems`,
  `figure_from_printed_lines`, `pass1_problems`, checks, parser, retry loop) and
  `ingestion/session_extraction.py` (v2, v1 refused, shape via `pass1_problems`).
- Scratch Walmart v2 file `/tmp/p11a/wmt_v2.json`, built by `/tmp/p11a/build_wmt.py`
  from rows on PDF pages 21-23 and 27 (pdfplumber text `/tmp/p11a/wmt_pages.txt`).
  `check` → exit 0; Total Assets 284,668 / 284,668 `+0 OK`; Total L + E
  284,668 / 284,668 `+0 OK`; gross profit `SKIP` in all three years.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|

## Measurements

### Baseline at `cd7101d` (before any change), every "already true" row agrees

| Fact | Measured |
|---|---|
| test gate `--ignore-glob="*_rule3_red.py"` | `495 passed`; pass list saved to `/tmp/p11a/baseline_passed.txt` |
| ruff | `Found 5 errors.` |
| mypy gate | `Found 10 errors in 4 files (checked 20 source files)` |
| census (rules.md:65, `'--include=*.py'` quoted) | `114`: claude_extractor 49, financial_statements 47, valuation 13, projector 3, routes_upload 1, routes_valuation 1 |
| route B key lists | `session_extraction.py:425` and `:487` iterate `PASS1_YEAR_FIELDS` / `PASS1_BALANCE_SHEET_FIELDS` from `claude_extractor.py:224-225` |
| CLI balance check | `cli.py:496-500`, `flag = "OK" if pct < 2.0 else "WARN"` |
| CACHE_FORMAT | `cli.py:215`, `p6-inputs-keyed-v1` |

## What I did not do

## Findings for the orchestrator
