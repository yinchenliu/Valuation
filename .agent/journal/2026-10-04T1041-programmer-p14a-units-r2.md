---
agent: programmer
assignment: P14a-units
round: 2
status: complete
files_touched: [cli.py, docs/2-rules/llm-boundary.md, docs/3-architecture/data-contract.md, docs/3-architecture/extraction.md, docs/4-conventions/units-and-signs.md, ingestion/claude_extractor.py, ingestion/session_extraction.py, models/financial_statements.py, templates/_statements.html]
---

# P14a-units round 2 — answer the review's findings F1-F8 and the amendment

Base commit `167d903` (round 1's base `99f8b1d` plus docs, the journal and P13h's tests).
Working tree verified against findings F1-F8, programmer findings 4 and 6, and the round 2 amendment.
No network calls made. Zero paid LLM calls.

## Base gates at `167d903` (measured, `base_gates.sh`)

| Gate | Result |
|---|---|
| full suite | 2 failed, 910 passed (the two `*_rule3_red.py` known reds) |
| gate form (`--ignore-glob="*_rule3_red.py"`) | 910 passed |
| ruff (`.venv/bin/python -m ruff check .`) | 4 errors (BLE001) |
| mypy (`models analysis ingestion api config.py app.py --ignore-missing-imports`) | 9 errors in 4 files (checked 20 source files) |
| census (`grep -rnE ... models analysis api ingestion \| wc -l`) | 65 |
| route check (`GET /`) | 200 |

Agrees with the review's base at `98b908e`.

---

## Findings, by number

### F1 (blocker) — Unit statement on page check matches whole statement, not fragments

- **Defect in round 1**: `unit_statement_on_page` stripped punctuation and checked normalised words anywhere on the page, allowing fragments such as `(in thousands)` to match inside Okta's `(dollars in millions, shares in thousands, except per share data)` on page 58.
- **Round 2 implementation**:
  - `unit_statement_on_page(printed, page_text)` in `ingestion/claude_extractor.py:1407-1431`:
    - Normalises only whitespace (`_whitespace_normalised` folds runs of whitespace and newlines to a single space). Case, commas, and parentheses are preserved.
    - If `printed` contains parentheses (`(` or `)`), it searches `_PARENTHESISED_GROUP.findall(_whitespace_normalised(page_text))` and requires exact equality to a parenthesised group on the page.
    - If no parentheses are present, it requires exact equality to an entire text line (`splitlines()`).
- **Measurements**:
  - Control on Okta 10-K 2026 page 58:
    - `unit_statement_on_page('(in thousands)', page_58)` -> `False`
    - `unit_statement_on_page('(dollars in millions, shares in thousands, except per share data)', page_58)` -> `True`
    - `unit_statement_on_page('dollars in millions, shares in thousands, except per share data', page_58)` (missing parens) -> `False`
    - Route B on `f1_okta_frag.json` stops with `ValueError: ... was not found on page 58, the page it cites, as a whole printed statement` (exit 2 in `check`).
    - Route A retries twice and stops with `ValueError` after 3 calls, 0 paid calls.
  - Reviewer's 16-filing scan (`r2_f1_scan.py` over 847 scanned parenthesised statements across 397 pages):
    - All 847 of 847 scanned statements found on their own page.
    - False positives for `(in thousands)` and `(in millions)` on the 34 two-scale pages that do not print them: round 1 rule = 48, round 2 rule = **0**.
    - Probe found where page does not print it whole: round 1 rule = 722, round 2 rule = **0**.

### F2 (major, Rule 3) — Stop on share or dollar mentions outside scale clauses

- **Defect in round 1**: Any statement excepting shares in words other than `"except ..."` fell through to the generic scale clause, giving shares the money scale instead of stopping.
- **Round 2 implementation**:
  - `_named_outside_its_clauses(printed, named, clauses)` in `ingestion/claude_extractor.py:679-689`:
    - Strips `per share` and `per-share` phrases (`_PER_SHARE`).
    - Counts occurrences of `named` (`_SHARE_WORD` or `_MONEY_WORD`) across the statement vs. within the subjects of parsed scale clauses.
    - If occurrences outside clauses > 0, returns `True`.
  - In `printed_scale(printed, unit_of)`:
    - For `share count`: stops if `_SHARE_WORD` is found in exception text or if `_named_outside_its_clauses` is True.
    - For `money figures`: stops if `_named_outside_its_clauses` is True for `_MONEY_WORD`.
- **Measurements (`r2_f2.py`)**:
  - All four amendment forms stop:
    - `(In millions, excluding share data)` -> money: millions; share count: STOP
    - `(in millions, other than shares)` -> money: millions; share count: STOP
    - `(in millions, but not shares)` -> money: millions; share count: STOP
    - `(in millions; shares in actual numbers)` -> money: millions; share count: STOP
    - Also: `(in millions, other than share and per share data)` -> STOP; `(in thousands, but not shares)` -> STOP.
  - Valid filings continue to read correctly:
    - `(dollars in millions, shares in thousands, except per share data)` -> money: millions; share count: thousands
    - `(dollar and share amounts in thousands, unless otherwise specified)` -> money: thousands; share count: thousands
    - `(Amounts in millions, except per share data)` -> money: millions; share count: millions
    - `(In millions)` -> money: millions; share count: millions
  - Stop through `parse_pass1` raises `Pass1ShapeError` naming `pass1.share_units` and the exact reason.

### F3 (escalated, backlog item 77) — Pass 2 schema documentation alignment

- **Status**: Escalated to user; backlog item 77.
- **Action taken**:
  - Schema and prompt in `ingestion/claude_extractor.py` were **not modified**.
  - Document lines claiming the opposite were corrected:
    - `docs/2-rules/llm-boundary.md:102-106`: documents that Pass 2 schema asks for `amount` in "same units as financials", model scales figures when note prints another scale (e.g. Walmart $0.7 billion -> 700), and this is backlog item 77.
    - `docs/2-rules/llm-boundary.md:116-118`: notes item 77 under what the model may never return.
    - `docs/4-conventions/units-and-signs.md:46-51`: documents that Pass 2 amounts are converted with filing's money scale, and notes item 77.

### F4 (minor, scope widened) — Statements UI formatting of balance check difference cells

- **Defect in round 1**: `templates/_statements.html:357-359` formatted cells with `{:,.0f}`, displaying `+0` beside `FAIL` for a filing in thousands with a difference of 0.002.
- **Round 2 implementation**:
  - `templates/_statements.html:356-363`:
    - Reads `{% set places = bs.printed_unit_decimals() %}`.
    - Formats printed, mapped, and difference cells with `{:,.{}f}` using `places`.
- **Measurements (`c7.py`)**:
  - For a thousands filing with 1,000.002 printed vs 1,000.000 mapped:
    - CLI prints: `Total Liab + Equity printed 1,000.002 mapped 1,000.000 diff +0.002 FAIL`
    - Web page (via `TestClient` on `/assumptions`) prints: `['1,000.002', '1,000.000', '+0.002', 'FAIL']`
    - Both agree and display `+0.002`, not `+0`.

### F5 (note) — Conversion guard covers BalanceSheet

- Verified that `convert_filing_to_millions` is called once per filing before merge on both routes:
  - Route A: `extract_financials` converts after Pass 2.
  - Route B: `load_session_extraction` converts per filing before merge.
- Recorded as backlog item note; no duplicate conversion occurs.

### F6 (requirement) — Constrain unit statement pages to governed figures

- **Round 2 implementation**:
  - `_unit_statement_pages_allowed(data)` in `ingestion/claude_extractor.py:1433-1450`:
    - `units`: restricted to pages cited by any printed line of income statement fields across all historical years.
    - `share_units`: restricted to `units.page` union pages cited by any printed line of `diluted_shares`.
  - In `_unit_statement_failures`: checks `page in pages_allowed[key]`; if not, fails with:
    `cites page <page>, which is not a page of the figures it states the unit of: the pages allowed are <pages>, <description>`.
- **Measurements (`c5.py`)**:
  - Route B on Chipotle citing page 31 (an MD&A page, while statement is on page 29):
    - Stops with `ValueError: ... 'units' ... cites page 31, which is not a page of the figures it states the unit of: the pages allowed are [29], the pages the income statement's printed lines cite.`
    - `check` exits with code 2.
    - When `share_units` cites page 31: stops naming `share_units` and allowed pages.
  - Route A retries twice and stops with `ValueError`. If corrected on retry, proceeds to Pass 2.
  - L3Harris 10-K 2026 page 62 (`(In thousands)` above an RSU table) cited as `units` stops because income statement pages are [35].
  - Real filings (Walmart p21, Okta p58, Chipotle p29, AbbVie p21) pass because unit statements are on income statement / diluted share pages.

### F7 (note) — Generic subject words aligned with docs

- In `ingestion/claude_extractor.py:592`:
  - `_GENERIC_SUBJECT_WORDS: frozenset[str] = frozenset({"amounts"})`
  - Comment documents: `amounts` from Walmart 10-K 2026-01-31 page 21 (`(Amounts in millions, except per share data)`).
  - Stale words `amount`, `all`, `and` were removed.
- Matches `docs/3-architecture/extraction.md` line 208 ("only `amounts`").

### F8 (note) — Backlog item 61 dead code replaced with assertion

- In `ingestion/claude_extractor.py:2184`:
  - Replaced dead fall-through `return financials` with `raise AssertionError("unreachable: all attempts should have returned or raised")`.

### Programmer Finding 4 (widened scope) — CLI clean import

- In `cli.py`:
  - Removed unused import `BalanceSheet` from `models.financial_statements` import block.
  - Updated call at line 541: `status = bs.printed_total_check(difference)`.

### Programmer Finding 6 (widened scope) — Stale defect row removed

- In `docs/3-architecture/extraction.md`:
  - Removed stale "Known defects" row for `_run_nri_pass`'s `except Exception`, which was closed by `P13g`.

---

## Done-criteria, re-run

All measurements run against the working tree with pinned interpreter `.venv/bin/python`, `PYTHONDONTWRITEBYTECODE=1`.

| # | Criterion | Round 1 result | Round 2 result | Evidence |
|---|---|---|---|---|
| 1 | step 2 rows | pass | pass | `PYTHONPATH=. .venv/bin/python scratchpad/p14a_programmer_r2/c1.py`: all 7 required rows pass. `c1b.py`: stop rows via `parse_pass1` raise `Pass1ShapeError` naming field and reason. |
| 2 | millions filing does not move | pass | pass | `cmp.py` comparing base `extractions/WMT.json` against `WMT_v3.json`: 137 leaf values compared, 0 differ. Only addition is `balance[0].printed_unit_in_millions = 1.0`. |
| 3 | thousands converted once | pass | pass | `PYTHONPATH=. .venv/bin/python scratchpad/p14a_programmer_r2/c3_c4.py`: Route A and Route B both yield revenue `11313.853`, diluted shares `1370.0`, Pass 2 amount `5.0`, `printed_unit_in_millions = 0.001`. |
| 4 | two scales | pass | pass | `c3_c4.py`: Okta p58 yields revenue `2610.0`, diluted shares `180.0` on both routes. |
| 5 | unit statement not on its page stops | pass | pass | `PYTHONPATH=. .venv/bin/python scratchpad/p14a_programmer_r2/c5.py`: Route B exits 2 naming field, text, page; Route A retries twice and stops after 3 calls. |
| 6 | real statements pass page check | pass | pass | `PYTHONPATH=. .venv/bin/python scratchpad/p14a_programmer_r2/c6.py`: Walmart p21, AbbVie p21, Chipotle p29, Okta p58, L3Harris p35 (2026), p41 (2025), p28 (2023), p17 (2023) all `found=True` on cited page and `False` on page + 1. |
| 7 | balance check stays at 1 printed unit | pass | pass | `PYTHONPATH=. .venv/bin/python scratchpad/p14a_programmer_r2/c7.py`: parser OK/FAIL, model tolerance `0.001`, CLI and template header print `FAIL above 0.001 $M: 1 in the filing's printed unit, and 1 printed unit = 0.001 $M`. |
| 8 | v2 session file stops with remedy | pass | pass | `.venv/bin/python -c "from ingestion.session_extraction import load_session_extraction; load_session_extraction('extractions/WMT.json')"` raises `ValueError` naming `session-extraction-v2`, `units`, `share_units`, and the remedy. |
| 9 | old pickle refused | pass | pass | `c9_write.py` wrote cache with `p11a-printed-lines-v1`; `c9_read.py` stopped with `ERROR: ... expected format marker 'p14a-units-in-millions-v1' ... SystemExit 1`, 0 network calls. |
| 10 | Walmart end-to-end does not move | pass | pass | `run_cli_guarded.py --session-file WMT_v3.json`: Stages 1-10 identical to base, revenue 680,985, PV TV 214,819, implied price $28.02, downside -73.1%. 0 LLM calls. |
| 11 | no paid API call | pass | pass | `network attempts: []` across all route tests; socket connect mocked to raise on network attempt. |
| 12 | red tests named | 254 red | 293 red | `.venv/bin/python -m pytest -q`: 293 failed, 619 passed. Gate form (`--ignore-glob="*_rule3_red.py"`): 291 failed, 619 passed. All 291 failures are Group A (163, missing `printed_unit_in_millions`), Group B (121, missing v3 unit fields), Group E (6), Group V (1). |
| 13 | gates do not get worse | pass | pass | ruff: 4 errors; mypy: 9 errors in 4 files; census: 65; route check: 200. |

### Additional criteria from round 2 amendment

| Criterion | Result | Evidence |
|---|---|---|
| F1 criterion: whole unit statement matching; fragment rejection | pass | `PYTHONPATH=. .venv/bin/python scratchpad/p14a_programmer_r2/r2_f1_frag.py`: `(in thousands)` on Okta p58 returns `False`; full statement returns `True`. `r2_f1_scan.py`: 847 of 847 scanned statements found on their page; fragment false positives on two-scale pages: 0. |
| F2 criterion: shares scale stops when mentioned outside clause | pass | `PYTHONPATH=. .venv/bin/python scratchpad/p14a_programmer_r2/r2_f2.py`: `(In millions, excluding share data)`, `(in millions, other than shares)`, `(in millions, but not shares)`, `(in millions; shares in actual numbers)` all stop share scale. |
| F4 criterion: template formats balance check cells with decimals | pass | `PYTHONPATH=. .venv/bin/python scratchpad/p14a_programmer_r2/c7.py`: cells display `+0.002` and `FAIL` for 1,000.002 vs 1,000.000. |
| F6 criterion: unit statement page restricted to governed figures | pass | `PYTHONPATH=. .venv/bin/python scratchpad/p14a_programmer_r2/c5.py`: statement citing p31 stops because allowed pages are [29]. L3Harris 10-K 2026 p62 RSU table stops. Walmart, Okta, Chipotle, AbbVie pass. |

---

## Gate checks

Commands run with `.venv/bin/python`:

1. **Ruff lint**:
   ```
   .venv/bin/python -m ruff check .
   ```
   Result: **4 errors** (all pre-existing `BLE001` blind Exception catches: `api/routes_valuation.py:445`, `api/routes_valuation.py:729`, `cli.py:1165`, `tests/test_e2e_all_googl.py:106`). Identical to base.

2. **Mypy type check**:
   ```
   .venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports
   ```
   Result: **9 errors in 4 files** (checked 20 source files). Identical to base.

3. **Rule 3 census**:
   ```
   grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" '--include=*.py' models analysis api ingestion | wc -l
   ```
   Result: **65**. Identical to base.

4. **Route check**:
   ```
   .venv/bin/python -c "from starlette.testclient import TestClient; import app; print(TestClient(app.app, raise_server_exceptions=False).get('/').status_code)"
   ```
   Result: **200**.

5. **Test suite**:
   ```
   .venv/bin/python -m pytest -q
   ```
   Result: **293 failed, 619 passed**.
   Gate form:
   ```
   .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"
   ```
   Result: **291 failed, 619 passed**.
   All 293 failures are expected: 2 pre-existing intentional rule 3 red tests (`test_projector_rule3_red.py`, `test_routes_session_rule3_red.py`) plus 291 tests failing because `BalanceSheet` requires `printed_unit_in_millions` and test fixtures lack `session-extraction-v3` unit statements.
