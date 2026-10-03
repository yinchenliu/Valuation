---
agent: programmer
assignment: P11a-printed-lines
round: 2
status: complete
files_touched: [ingestion/claude_extractor.py, models/financial_statements.py, docs/2-rules/llm-boundary.md, docs/3-architecture/extraction.md, docs/3-architecture/data-contract.md]
verdict:
---

# P11a-printed-lines round 2: answering review F1-F7

> Opened 2026-10-03 10:48, before the first command. Completed 10:55. Nothing committed.
> Review: `.agent/journal/2026-10-03T1046-code_reviewer-p11a-printed-lines.md`.
> Decisions: the "Round 2" section of `.agent/assignments/P11a-printed-lines.md`.
> Round 1 entry: `.agent/journal/2026-10-03T1029-programmer-p11a-printed-lines-run3.md`.
> I did not touch `.claude/skills/extract-filing/SKILL.md`, `.agent/assignments/`,
> `.agent/journal/INDEX.md` or `docs/9-reference/refactor-backlog.md`. They show as
> modified in `git status`; those edits are the orchestrator's.

## Progress log

- 10:48 opened. Read the review and the assignment's Round 2 section.
- Wrote the code: `check_row_from_printed_lines` (F1, and F2 for operating income),
  `PASS1_YEAR_NEVER_EMPTY_FIELDS` in `pass1_problems` (F2 for net income),
  `_is_finite_number` catching OverflowError plus `_shown` (F4), and
  `_validate_extracted_data` rewritten to return `_CheckFailure(message, retry_message)`
  with no WARN branch (F5, F7). `printed_total_check(None)` now returns
  `FAIL: not extracted`. ruff went back to 5 after one ISC004 (a two-part string inside
  a tuple, now parenthesised).
- The criterion 1 grep found 2 hits ("sum of"), both in my new retry text. That text
  described Python's work and asked for nothing, but I reworded it to "Python's total"
  so the grep is clean.
- Re-ran criteria 1-10, the findings script, the CLI and the page.

## Findings, answered by number

| # | Finding | Answer | Where | Proof |
|---|---|---|---|---|
| F1 | `[]` on a printed balance sheet total is shown as a printed 0 | **Fixed**, per decision 1. `[]` on `total_assets` / `total_liabilities_and_equity` is `None`. The status is `FAIL: not extracted`, with no gap and no printed 0. The run continues | `claude_extractor.py:505` `check_row_from_printed_lines`, used at `:1191-1197`; `models/financial_statements.py:267`; the parser's message at the `printed is None` branch of `_validate_extracted_data` | `/tmp/p11a/r2_findings.out`, "F1": `printed_total_assets: None \| difference: None`; the table row `Total Assets (none) 284,668 FAIL: not extracted`. `check` exits 1 with "the printed total_assets row was not extracted". CLI: `printed not extracted mapped 284,668 diff FAIL: not extracted`, and the run reaches Equity Value. Page: `<td class="num">not extracted</td> ... <td class="num">—</td> <td><strong>FAIL: not extracted</strong>`, status 200. Route A keeps the figures after 3 calls |
| F2 | `[]` on `operating_income` / `net_income` becomes a printed 0, and `net_income` enters the cash flow as 0 | **Fixed**, per decisions 2 and 3. `operating_income` `[]` is `None`: the check is skipped and labelled `SKIP: not printed (the filing prints no operating_income row)`, the same as gross profit. `net_income` `[]` is a shape problem in `pass1_problems`, so it stops in both routes. `net_income` is read only through `figure_from_printed_lines` after `pass1_problems` has passed, so no path can put an unprinted 0 into `CashFlowStatement.net_income` | `:258-260` (the three tuples); `:540` (the never-empty test); `:1104-1109`; `:1132` | "F2a": 2025 `Oper. Income (none) 29,348 SKIP: not printed ...`, no failure, `check` exit 0. "F2b": route A parse gives `Pass1ShapeError ["year 2024, 'net_income': is [], and this row is never absent from a filing. Read the printed row."]`. The route A loop makes 3 calls, each with the PDF, then stops with the same problem. Route B: `check` exit 2, and the loader names the file, `filings[0] (Walmart Inc._10-K_2026-01-31_English.pdf), year 2024, 'net_income'` |
| F3 | The route A cost row does not say retries re-send the PDF | **Fixed**, per decision 7. The cost cell now says each shape or check retry re-sends the whole PDF (up to 3x Pass 1 input tokens per filing), and that the JSON repair retry sends none | `docs/3-architecture/extraction.md:184` | read the file |
| F4 | An out-of-range integer `value` crashes | **Fixed**, per decision 4. `_is_finite_number` returns False on OverflowError. `_shown` describes such a value by its bit length rather than printing hundreds of digits | `:426`, `:441` | "F4", `10**400`: route A gives `Pass1ShapeError ["year 2026, 'capex': line 0: 'value' must be a finite JSON number, got an integer of 1329 bits, too large for a float."]`; route B `check` exits 2 with the same text plus the file and filing |
| F5 | Dead `WARN` branch | **Removed**, per decision 5. The status is now `FAIL` above `fail_pct`, else `OK` | `:748` | `grep -n WARN ingestion/claude_extractor.py` finds only the three unrelated console messages (Gemini finish reason, Pass 2) |
| F6 | Stale "explicit `0`" sentence | **Fixed**, per decision 7: "extracted as an empty list, `[]`, which reads as `0`" | `docs/3-architecture/data-contract.md:134` | read the file |
| F7 | The check retry hands the model the exact gap | **Fixed**, per decision 6. Each failure is a `_CheckFailure` with two wordings. `message` keeps the gap; `check`, the CLI and route A's console print it. `retry_message`, which goes to the model, names the check, the side, the printed row and the rows Python added (label, field, page), and states no amount | `:629` `_CheckFailure`; `:669` `_rows_listed`; `:1501` (console prints `message`); `:1509` (retry sends `retry_message`); `:1920` `parse_pass1` returns the messages, so route B is unchanged | "F7": in the retry for the dropped "Prepaid expenses" row, none of `4,124`, `4124`, `280,544`, `280544`, `284,668`, `284668` appears (the JSON is excluded from the search; it holds the values as it always has). The retry text reads `[2026] Balance sheet, assets side: the printed total_assets row ('Total assets' (total_assets, page 22)) does not agree with Python's total of the rows listed under cash, ... Rows Python added: 'Cash and cash equivalents' (cash, page 22); ...`. Income statement case (operating income +900): neither `900` nor `30,725` appears. Route B `check` keeps `diff=+4,124` (`keeps the gap: True`) |

I dispute nothing. The orchestrator settled F1 and F2 (the review escalated F2), and I
applied those decisions as written.

## Done-criteria re-run

Every criterion was re-run on the final tree at 10:50-10:54.

| # | Result | Evidence |
|---|---|---|
| 1 | **pass** | `grep -n -i "sum of\|combine\|minus\|adjust catch" ingestion/claude_extractor.py` returns 0 lines, after the reword above. A wider scan of the rendered prompt (`/tmp/p11a/r2_prompt1.txt`) finds only prohibitions and printed-row names, plus the new sentences "Never []: every income statement prints it", "[] if the filing prints no operating income row; never derive it" and `"net_income" is never []`. None asks for a computation |
| 2 | **pass** | `/tmp/p11a/r3_equal.py` → `ALL EQUAL`, exit 0. Prompts equal (2 and 6 pairs); 4 and 8 calls, 2 retries each, each retry carrying the PDF (`/tmp/p11a/r2_equal.out`) |
| 3 | **pass** | `/tmp/p11a/r3_crit3.py` → `figure_from_printed_lines -> 26695.0`, `capital_expenditures: -26695.0`; I/S and C/F equal to the cd7101d parser on v1 `extractions/WMT.json` |
| 4 | **pass** | `check r3_wmt_v2` exit 0, `Total Assets 284,668 284,668 +0 OK`. Gross profit now reads `SKIP: not printed (the filing prints no gross_profit row)` |
| 5 | **pass** | `check r3_wmt_drop` exit 1, `+4,124 FAIL`. CLI `diff +4,124 FAIL`, then Equity Value. Page status 200, `<strong>FAIL</strong>` |
| 6 | **pass** | `/tmp/p11a/r3_crit6.py`: 20 of 20 stop, 0 `NO STOP`, `[]` still reads 0 for a component field. Plus F2b (empty net_income) and F4 (`10**400`), both named, in both routes |
| 7 | **pass** | `check r3_wmt_v1fmt` exit 2, both formats named |
| 8 | **pass: 67** | census grep, unchanged from round 1 (114 at `631cf45`) |
| 9 | **pass: same 40** | gate 455 passed, 40 failed. By JUnit set (`/tmp/p11a/r2_final_junit.xml` against `/tmp/p11a/r3_base_junit.xml`): failing = baseline-passing minus now-passing; the same 40 as round 1; nothing newly passes; no test in one run only. Reasons by kind, unchanged from round 1 test for test: 28 old shape (bare number), 9 v1 refused, 2 `check` exit 2 on the old shape, 1 key tuple. The names are listed in the round 1 entry |
| 10 | **pass** | ruff `Found 5 errors.` (the five BLE001); mypy `Found 10 errors in 4 files`; `GET /` 200 |

## Decisions, each with its reason

| Decision | Reason | Alternative not taken |
|---|---|---|
| One function, `check_row_from_printed_lines(lines, field, where) -> float \| None`, for all four optional check rows | Rule 2: one named, typed function per meaning. "A check row's printed figure, or None when nothing is printed" is a different meaning from "a figure, where `[]` is 0" | An `if` inline at four call sites. That repeats one decision four times and lets them drift |
| `net_income` `[]` is caught in `pass1_problems`, not in the parser | Both routes already run `pass1_problems` first, so one place stops route A (after its shape retries) and the route B loader (naming the filing) | Raising in the parser would skip route B's "every problem in one list" and route A's shape retry |
| `printed_total_check(None)` returns `FAIL: not extracted` instead of `not extracted` | Decision 1: "The balance check shows FAIL and says the total was not extracted". The page's red-row test (`status != "OK"`) and the parser's failure test agree on it | A separate column for "extracted?". More markup, and it changes nothing a reader needs |
| Two wordings per failure in one frozen dataclass | Route B and the console must keep the gap; the model must not see it (decision 6). Building both where the numbers are known keeps them about the same check | Stripping amounts from the full message with a regex: fragile, and it could leave a figure in |
| The retry lists rows as label, field and page, without values | Decision 6: "lists the rows Python added", "does not state the gap amount". Listing values would let the model compute the gap from the prompt text alone. It still can from the JSON, which it must receive to correct | — |
| Integers beyond Python's 4,300-digit parse limit left as they are | These fail inside `json.loads`, before any line is checked. Both routes still stop with a ValueError naming the cause ("value has 5001 digits"), though not the line. Route B prints `STOPPED — Exceeds the limit (4300 digits) ...` and exits 2; route A raises the ValueError. Outside F4, which concerns integers too large for a float | A `parse_int` hook on every `json.loads` / `json.load`. Possible, but it widens the change for an input no filing produces. Recorded below |

No change in this round was made to reach a target number.

## Rule 3: rows that changed since round 1

| Value read | If it were missing or empty | Evidence |
|---|---|---|
| `total_assets` / `total_liabilities_and_equity` `[]` | `None` → `FAIL: not extracted`, counted as a failure, no printed 0 and no gap | F1 above |
| `operating_income` `[]` | `None`. The check is skipped as "not printed"; the value feeds nothing else (EBIT is derived on `IncomeStatement`) | F2a |
| `gross_profit` `[]` | `None`, skipped as "not printed" (unchanged in effect) | criterion 4 output |
| `net_income` `[]` | **stops**, in both routes, naming the year and the field (route B: and the file and filing) | F2b |
| a line `value` too large for a float | stops, naming the field, year and line index | F4 |
| a line `value` beyond 4,300 digits | stops (ValueError from `json`), naming the cause but not the line | decision row above |

Every other row of the round 1 rule 3 table stands as written there.

## Measurements

| Gate | `631cf45` | round 1 | round 2 |
|---|---|---|---|
| tests (gate form) | 495 / 0 | 455 / 40 | 455 / 40, the same 40 |
| ruff | 5 | 5 | 5 |
| mypy | 10 in 4 | 10 in 4 | 10 in 4 |
| census | 114 | 67 | 67 |

Scratch files for this round: `/tmp/p11a/r2_findings.py` / `.out`, `r2_f1_empty_total.json`,
`r2_f2a_empty_oi.json`, `r2_f2b_empty_ni.json`, `r2_f4_huge.json`, `r2_f4_5000digits.json`,
`r2_f7_drop.json`, `r2_prompt1.txt`, `r2_equal.out`, `r2_crit6.out`, `r2_retry.out`,
`r2_*.check.out`, `r2_*.cli.out`, `r2_*.route.out`, `r2_final_junit.xml`.

## What I did not do

- `tests/`: out of scope. The 40 fixtures still need the new shape, and the tester
  should add cases for this round's behaviour: an empty total gives `FAIL: not
  extracted`, an empty `operating_income` gives SKIP, an empty `net_income` stops, a
  `10**400` value is named, and the retry text holds no amount.
- The 4,300-digit integer case (decision row above).

## Findings for the orchestrator

1. **The prompt now says "Never []" for `net_income` and the two totals.** For the
   totals, an empty list still does not stop the run (decision 1): it shows as `FAIL: not
   extracted`. The prompt tells the model what is expected; the parser decides the
   consequence. This is consistent, but a reviewer should know the two differ on purpose.
2. **The retry still carries the JSON**, so a model can compute the gap from the values
   it was sent. Decision 6 removes only the stated amount. Backlog item 59 (checking each
   row against its page) remains the real defence.
3. The round 1 findings 2-5 stand, except the dead WARN branch, now removed (F5).
