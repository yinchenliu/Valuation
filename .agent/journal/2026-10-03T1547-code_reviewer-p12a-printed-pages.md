---
agent: code_reviewer
assignment: P12a-printed-pages
round: 1
verdict: approved
---

# Review of P12a-printed-pages, round 1

Programmer entry: `.agent/journal/2026-10-03T1534-programmer-p12a-printed-pages.md`

Baseline `0839ad9`; the unit is uncommitted. The diff touches only the four files in
scope, plus the programmer's entry. `.agent/journal/INDEX.md` is the orchestrator's edit
and is not reviewed. Nothing under `tests/`, `cli.py`, `api/`, `models/`, `extractions/`
or `.claude/` moved (`git status --short`).

## The guard checks

Run over `ingestion/claude_extractor.py` and `ingestion/session_extraction.py`, before
(`git show 0839ad9:…`) and after, and on the diff's added lines.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | 0 before, 0 after |
| lookup with a fallback — `.get(k, …)` | 13 before, 13 after, **0 on added lines** |
| bare or-default | 3 before, 3 after, 0 on added lines |
| money field defaulted to zero | 0, 0 |
| `**kwargs` | 0, 0 |
| `getattr(` | 2 before, 2 after, 0 on added lines |
| dict of functions keyed by data | 0, 0 |
| model client imported outside `ingestion/` | clean (no hit in `models/`, `analysis/`, `api/`) |

The unit adds no hit. The pre-existing hits are in lines the unit did not touch.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| a line's `label`, `value`, `page` | yes. `pass1_problems` runs first in both routes and names the year, field and line. `page < 1` is rejected there, so `pdf.pages[page - 1]` cannot wrap to the last page | `claude_extractor.py:483`; route A walks only after `_parse_financials_response` returns; the wrapper re-runs `pass1_problems` and raises `Pass1ShapeError` |
| `latest_balance_sheet` = `{}` | not walked. `{}` is the defined answer for "balance sheet not asked for", the same as in `pass1_problems:603` | `if balance:` in `_printed_line_failures`. Programmer answered it |
| a cited page beyond the PDF | failed check naming the page and the page count | criterion 5, measured |
| a page with no text layer | failed check, "cannot be confirmed". It is never a pass | `if text is None or not text.strip()` in `_printed_line_failure` |
| a label that normalises to empty | `printed_line_on_page` returns False, so a failed check. It is never a pass | `if not wanted: return False` |
| the PDF itself | stops with `ValueError`; only `PdfminerException` and `MalformedPDFException` are caught | I read `pdfplumber/pdf.py:49-52`, `:155-161` and `page.py:265-268`: every open, page-listing and layout error is wrapped in `PdfminerException`. Ruff `BLE001` stays at 5 |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | not crossed. Pass 1 values are in the filing's own units (`claude_extractor.py:304`, "same currency and units as the source"), so the page check compares a value with the figure as printed. Chipotle's thousands compare correctly. No figure is converted |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing | `if balance:` is the defined `{}` sentinel on a value already proved to be a dict. `magnitude == 0` is explicit. No new `if x` on a figure |
| `analysis/` imports no `ingestion/`, `api/` or model client | unchanged. `pdfplumber` is imported inside `_read_cited_pages`, in `ingestion/` |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | one rule, one walk, two routes | 1 def each; route A `:1701`, wrapper `:2151`, route B `session_extraction.py:630` | one `def printed_line_on_page`, one `def _printed_line_failures`. Route A calls the walk at the `val_errors = val_errors + …` line; route B calls the wrapper once in `load_session_extraction` | yes |
| 2 | Walmart clean | exit 0; 89 checked, 89 found | `check extractions/WMT.json`: exit 0, `89 checked, 89 found, 0 not confirmed`, new Clean sentence. 0.63 s wall | yes |
| 3 | invented balancing row caught | exit 1, names field, line 0, label, page 22; balance OK | my own scratch copy: exit 1, `balance sheet 2026, 'other_current_assets' line 0: 'Other current assets' = 4,124 was not found on page 22`. `Total Assets` and `Total L + E` both `284,668 … +0 OK` | yes |
| 4 | wrong page caught | exit 1, page 23 | exit 1, `… was not found on page 23` | yes |
| 5 | page beyond the PDF | exit 1, 87 and 86 | exit 1, `cites page 87, but the PDF has 86 pages` | yes |
| 6 | the rule, by hand | 6 of 6 | 6 of 6: True, False, True, True, True, False | yes |
| 7 | retry names the row, no amount | yes | `_call_llm` stubbed to return the criterion 3 JSON, real Walmart bytes. The retry preamble names `'Other current assets'`, `other_current_assets` and `page 22`. Above the JSON none of the four amounts appears; every hit is in the JSON body | yes |
| 8 | figures kept after the last retry | 3 calls, `[Pass 1 FAIL]`, statements returned | 3 calls, PDF sent on all 3. `[Pass 1 FAIL] Checks still fail after 2 retries` and the page failure are printed. `FinancialStatements`, years [2024, 2025, 2026], `other_current_assets` 4124.0 | yes |
| 9 | unopenable PDF stops | `ValueError`, cause `PdfminerException` | wrapper on stand-in bytes: `ValueError: the PDF sha256 f323a2c6d3ab7975… (27 bytes) cannot be opened by pdfplumber (PdfminerException: …)`, `__cause__` is `pdfplumber.utils.exceptions.PdfminerException`. Through route B's `check` on a session file whose sha matches stand-in bytes: `STOPPED — the PDF sha256 f700f716… (28 bytes) …`, exit 2. See F2 | yes |
| 10 | gates do not regress | ruff 5 BLE001; mypy 10 in 4; census 67 | ruff `Found 5 errors`, all `BLE001`, at the same 5 sites. mypy `Found 10 errors in 4 files` (the exact command from the harness notes). Census 67 | yes |
| 11 | the red list | 24 red, all stand-in PDF | baseline at `0839ad9`, in a scratch worktree: **626 passed**. After: **24 failed, 602 passed**. The failure set, compared by name, equals the programmer's 24. Control, with the walk stubbed to `[]` through a scratch plugin: **626 passed**. So every red test is caused by the page check on stand-in bytes, and no reworded message breaks a test. Of the `_rule3_red` tests, `test_routes_session_rule3_red.py` moved from `:74` (its defect) to `:63` (setup, the PDF error). `test_projector_rule3_red.py` is unchanged at `:98` | yes |

## Findings

### F1 — the joined forms let a label match a figure printed on the next or previous row · `note`, an escalation to the orchestrator

**Evidence:** on Walmart page 22, `printed_line_on_page('Prepaid expenses and other', 84874, p22)` → True (84,874 is `Total current assets`, the next row), `('Prepaid expenses and other', 58851, p22)` → True (`Inventories`, the row above), and `('Inventories', 4124, p22)` → True.
**Rule or document:** none broken by the code. It is a faithful copy of the assignment's step 4: "L, a space, then the line below L". The joined form contains the whole label from the neighbouring row, plus the figure from L. But the docs this unit wrote say "It confirms a row is printed with that figure" (`extraction.md`, "Two limits"; `llm-boundary.md`, "within two limits"). That is not true: an adjacent row's figure under a real label passes. This is a third limit, wider than the column limit, and it is the misread a gap-closing model would most likely make. **This is not a finding against the programmer.** The rule is the orchestrator's.
**What would fix it:** a rule change, for the orchestrator to decide **before the tester writes fixtures that encode the current rule.** The narrowest change: count a joined form only when the label is not wholly on the neighbour line. I measured it: **89 of 89** Walmart lines are still found, and all three cases above become False. If the rule is not changed, the docs need a third limit.

### F2 — route B's stop names the unopenable PDF by sha256 prefix only, though the loader holds its file name · `minor`

**Evidence:** `check` on a session file pointing at stand-in bytes prints `STOPPED — the PDF sha256 f700f7160a8d5857… (28 bytes) cannot be opened by pdfplumber …`. The call at `session_extraction.py:630` has `where` (`filings[0] (rv_standin.pdf)`) in hand and does not use it.
**Rule or document:** the assignment's "a `ValueError` naming the PDF". A sha prefix does identify the PDF. In a three-filing session, though, the reader must hash files to learn which one stopped, while every other loader stop names the filing by `where`. The programmer's reason (route A holds only bytes) is right for route A and does not apply to route B.
**What would fix it:** in `load_session_extraction`, re-raise the `ValueError` with the `where` prefix (`raise ValueError(f"{where}: {exc}") from exc`), and leave route A's wording as it is. This does not block approval.

### F3 — on the orchestrator's question: whole-word matching finds all 89 lines but does not close the programmer's own example · `note`

**Evidence:** a scratch whole-word variant (`f" {label} " in f" {text} "` after normalisation) finds **89 of 89** Walmart lines. But `('Debt', 34624, p22)` is still True under it, because `debt` is a whole word in `long term debt`. Whole words only stop a match inside a word (`tax` in `taxes`). An exact variant, where the normalised candidate *equals* the normalised label, also finds **89 of 89**. It makes `Debt` = 34,624 False and keeps `Debt` = 2,318 (the `Debt 2,318 2,249 2,259` row under `Interest:`) True. It also closes F1. **Neither variant was measured on the other 15 filings.** Footnote letters, `$` columns and row headers may break exact equality there.
**Rule or document:** none. This is the orchestrator's rule (programmer finding 1). The code copies it faithfully.
**What would fix it:** it is not needed for this unit's attack. An invented label is caught under the substring rule (criterion 3). The short-label looseness lets through only a real printed figure under a label fragment, and the arithmetic checks still apply. If the orchestrator tightens the rule, do it together with F1. The "exact" form is the one that closes both, but it should first be measured on all 16 filings.

### F4 — the red-on-purpose test no longer reaches its own assertion · `note`

**Evidence:** `test_routes_session_rule3_red.py` fails at `:63` (the PDF error in setup); at `0839ad9` it failed at `:74`, on its recorded defect.
**Rule or document:** none broken. The assignment puts `tests/` out of scope. The programmer reported it (its finding 3).
**What would fix it:** the tester gives this fixture a real PDF (`tests/unit/_text_pdf.py:write_text_pdf`) along with the 24.

### F5 — a filing with no text layer would spend route A's two retries on lines that cannot be confirmed · `note`

**Evidence:** the programmer's finding 2. By reading, `_printed_line_failure` returns a "no text layer" failure, and route A retries it like any other failure. No filing under `10K_filings/` has this problem today (the assignment's fact table: 16 of 16 have a text layer).
**Rule or document:** none. The failure is shown and never passes, which is what rule 3 requires.
**What would fix it:** a later unit, if it ever becomes live.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 8 — blanket `except Exception` | `ingestion/claude_extractor.py:1794` (moved down by the inserted block, same code) and four others | no. The line shifted, its text did not change; the new handler names two pdfplumber classes |
| 1 — census sites | 13 `.get(…, …)` and 3 or-defaults in the two files | no. None is on an added line; census 67 before and after |
| 62 — failed reading checks never reach the web page | `api/routes_valuation.py` | no, out of scope by assignment |

## Earlier findings — re-reviews only

Round 1: none.

## Verdict

`approved`

The code implements the assignment's rule faithfully and passes every done-criterion. I
re-ran each one: the 89 Walmart lines are found, the invented, wrong-page and
beyond-PDF rows are caught while the balance check stays OK, and the retry states no
amount. The 24 red tests are exactly the stand-in PDF failures; the control with the
walk stubbed passes 626 of 626, the same as the baseline. The gates hold at 5 / 10 / 67.
No rule is broken and no file outside scope was written. F2 is a `minor` the programmer
can take in a later round or the orchestrator can fold into a follow-up. **Before the
tester is dispatched, the orchestrator should decide F1 (and with it F3)**, because the
fixtures will encode step 4 of the rule as it stands. If step 4 stays, the docs owe a
third limit: a label is matched with a figure from an adjacent row.
