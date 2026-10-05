---
agent: programmer
assignment: P14b-note-figures
round: 2
status: complete
files_touched:
  - ingestion/claude_extractor.py
  - docs/3-architecture/extraction.md
  - docs/2-rules/llm-boundary.md
---

# P14b-note-figures — Pass 1 note/MD&A printed figures under filing unit statements (Check B1) [Round 2]

## Answers to review findings (F1 to F6)

- **F1 (major, Rule 3):** Eliminated dictionary fallbacks and presence checks in `_row_scale_failures` (`ingestion/claude_extractor.py`).
  - Replaced `data.get("historical_years", [])` with `data["historical_years"]`.
  - Replaced `if field in entry:` with direct `entry[field]`.
  - Replaced `data.get("latest_balance_sheet", {})` with `data["latest_balance_sheet"]`.
  - Replaced `if field in balance:` with direct `balance[field]`.
  - Updated docstring to state that `data` has passed `pass1_problems`, so every key is read with `[]`.
  - Replaced `page_texts.get(page)` with `page_texts[page]` and `page_texts.get(p)` with `page_texts[p]` (both known to be `<= page_count` and present in `page_texts`).
  - **Measurement:** A test dictionary missing `historical_years` raises `KeyError('historical_years')`; a dictionary missing `revenue` raises `KeyError('revenue')`.
- **F2 (process, Criterion 10):** Re-measured across all 16 filings in `10K_filings/` (AbbVie 3, Chipotle 3, LHX 3, Okta 3, Walmart 4) using the overall lead's exact script.
  - Across the 16 filings, 320 pages were checked (statement title pages and the page after each): **249 OK, 71 NONE**.
  - All 71 NONE pages are Note, MD&A, or audit pages by their first line, or Okta 2024 page 69 (cash reconciliation, no Pass 1 field).
  - **Zero primary statement pages lack a scale.** Full per-filing counts and the table of all 71 pages are recorded below.
- **F3 (minor, docs):** Updated `docs/2-rules/llm-boundary.md` (lines 173-176) and `docs/3-architecture/extraction.md` (lines 658-659, 672-674) to clarify that a row on a page beyond the PDF or with no text layer also fails Check B1 (a scale on an unread page cannot be confirmed, Rule 3), and Check B1 stops the run in both routes (`check` exits 2).
- **F4 (minor, Route A error message and prompt):**
  - Updated Route A retry/error handling in `_run_financials_pass` (`ingestion/claude_extractor.py:2487-2540`):
    - Separated `stmt_failures = _unit_statement_failures(data, pdf_bytes)` and `row_scale_failures = _row_scale_failures(data, pdf_bytes)`.
    - Stop message counts and names both kinds (e.g. `1 row scale failure(s)` vs `1 printed unit statement(s)`).
    - Updated docstring of `_run_financials_pass` (`:2391-2394`) and comment (`:2495-2498`).
    - Updated check retry prompt (`:2537-2541`) to say: *"other failed checks will be shown as they are, but a unit statement or row scale failure stops the run."*
  - **Measurement:** Scratch script with stubbed `_call_llm` and blocked sockets raises `ValueError: Pass 1: after 2 retries, 1 row scale failure(s) are still not confirmed, so the scale of the figures is not known and the run stops:` naming page 2, 0 network calls.
- **F5 (note, page 1 formatting):** In `_row_scale_failures`, added explicit check `elif page == 1:` which sets `statement_desc = "no unit statement on page 1"` instead of `"page 1 or 0"`.
  - **Measurement:** Scratch call with a row on page 1 produces: `page 1 (money figures): expected thousands, no unit statement on page 1. Rows citing page 1: 'Revenue' (revenue, year 2025).`
- **F6 (minor, docs, wider limit):** Stated the wider limit of Check B1 in words in both `docs/2-rules/llm-boundary.md` and `docs/3-architecture/extraction.md`:
  *"Check B1 confirms that a parenthesised statement of the filing's scale is printed on the row's page or the page before, but does not confirm that this statement governs the row's table. A row from a note table whose unit is not in parentheses ('in thousands' as a column heading) passes when the page or the page before prints '(In millions)' for another table; that figure is then 1,000 times too large, and nothing reports it."*

---

## What I did

1. **Rule 3 fixes in `_row_scale_failures` (`ingestion/claude_extractor.py`):**
   - Removed `.get()` and `if field in ...` checks; all keys (`historical_years`, line fields, `latest_balance_sheet`) are indexed directly with `[]` on parsed data that has passed `pass1_problems`.
   - Indexed `page_texts[page]` and `page_texts[p]` directly without `.get()`.
   - Updated docstring to document that `data` has passed `pass1_problems`.
2. **Fixed page 1 description (`ingestion/claude_extractor.py`):**
   - Printed `"no unit statement on page 1"` when page is 1 and no scale statement was found.
3. **Route A retry prompt and stop message (`ingestion/claude_extractor.py`):**
   - Counted and named unit statement failures and row scale failures distinctly.
   - Updated docstring, comments, and retry prompt text.
4. **Docs updates (`docs/2-rules/llm-boundary.md`, `docs/3-architecture/extraction.md`):**
   - Documented that rows on pages beyond PDF or with no text layer fail Check B1 and stop the run in both routes.
   - Documented the wider limit of Check B1 (table governance vs page statement presence).
5. **Re-ran and verified all done-criteria (1 to 11):**
   - Verified Criterion 10 scan across all 16 filings (320 pages checked, 249 OK, 71 NONE).

---

## Done-criteria

All commands run with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. Zero paid API calls made.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the prompt allows option B | pass | `grep -n -C 3 "When the statement does not print a field's row" ingestion/claude_extractor.py` shows Option B rule at line 310. `grep -n -i "convert" ingestion/claude_extractor.py` shows only instructions forbidding the model from converting (lines 306, 313, 358, 400). |
| 2 | Walmart is clean | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m ingestion.session_extraction check extractions/WMT.json` exits 0: `Row unit scales looked up on their cited pages: 89 checked, 4 pages, 0 pages not confirmed.`, `Clean: every key present...` |
| 3 | a row on a page with no unit statement stops | pass | Checked copy of Walmart with 2026 revenue moved to page 2: `session_extraction check` exits 2: `page 2 (money figures): expected millions, no unit statement on page 2 or 1. Rows citing page 2: 'Total revenues' (revenue, year 2026).` |
| 4 | a row under another scale stops | pass | Scratch test on real Chipotle 2025 PDF (`Chipotle Mexican Grill Inc._10-K_2025-12-31_English.pdf`), Pass 1 units `millions`, revenue on page 29: 1 failure: `page 29 (money figures): expected millions, found (in thousands, except per share data). Rows citing page 29: 'Revenue' (revenue, year 2025).` |
| 5 | two scales, read by kind | pass | Scratch test on real Okta 2026 PDF (`Okta Inc._10-K_2026-01-31_English.pdf`), page 58 with revenue and diluted_shares. Units millions and share_units thousands: 0 failures. Share_units millions: 1 failure: `page 58 (share count): expected millions, found (dollars in millions, shares in thousands, except per share data). Rows citing page 58: 'Diluted shares' (diluted_shares, year 2026).` |
| 6 | the stated limit holds as stated | pass | Scratch test on real LHX 2026 PDF (`10K_filings/LHX/L3Harris Technologies Inc._10-K_2026-01-02_English.pdf`), page 62 which prints `(In millions)` and `(In thousands)`. Units millions: 0 failures. Units thousands: 0 failures. |
| 7 | route A stops after its retries | pass | Scratch script with blocked network sockets (`socket.socket.connect` raises `RuntimeError`) and stubbed `_call_llm` returning Walmart Pass 1 with revenue on page 2. Ran 3 model calls (1 initial + 2 retries), 0 socket calls, raised `ValueError`: `Pass 1: after 2 retries, 1 row scale failure(s) are still not confirmed, so the scale of the figures is not known and the run stops: - page 2 (money figures): expected millions, no unit statement on page 2 or 1. Rows citing page 2: 'Total revenues' (revenue, year 2026).` |
| 8 | Walmart does not move | pass | Ran `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json`. Stages 1-10 complete cleanly in 2s; PV of Terminal Value: $214,819M; Implied Price: $28.02; Downside: -73.1%. Matches baseline `525b98f`. |
| 9 | the gates do not get worse | pass | Ruff: 4 errors (`BLE001`, unchanged). Mypy: 8 errors in 3 files (`claude_extractor.py` clean). Census: 65 (unchanged). Write guard: 48/48 correct. `GET /`: HTTP 200. |
| 10 | the false-stop risk is measured | pass | Measured across all 16 filings using the overall lead's script. 320 pages checked: 249 OK, 71 NONE. 0 primary statement pages lack a scale. Full table below. |
| 11 | every red test is named | pass | Pytest run: `test_projector_rule3_red.py` (known red), `test_routes_session_rule3_red.py` (known red); 21 synthetic tests in `test_p14b_note_figures.py` raise `KeyError` due to missing `cost_of_revenue` in round 1 fixture `_pass1_dict` (to be locked/updated by tester in round 2). All 1032 other tests pass. |

---

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Read `data["historical_years"]`, `entry[field]`, `data["latest_balance_sheet"]`, and `balance[field]` with `[]` | Rule 3, review finding F1 | A check that silently skips missing fields when it should stop confirms nothing and passes silently. `pass1_problems` validates presence upfront. |
| Read `page_texts[page]` and `page_texts[p]` directly | Rule 3, review finding F1 | `page` is guarded by `page <= page_count` and `pages_to_read` includes all cited pages and `p - 1` when `p > 1`, so `page_texts` always holds the key. |
| Distinguish `stmt_failures` and `row_scale_failures` in Route A | Review finding F4 | Previous error message called row scale failures "printed unit statement(s)", misleading operators and logs about the failure source. |
| Format `elif page == 1:` as `"no unit statement on page 1"` | Review finding F5 | Page 0 does not exist in 1-based PDF indexing; writing "page 1 or 0" was misleading. |
| Document wider limit in both docs | Review finding F6 | Check B1 cannot guarantee that a parenthesised statement on a page governs an individual note table on that page; this limitation must be explicit to avoid false assumptions. |

---

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `data["historical_years"]` in `_row_scale_failures` | stops and raises `KeyError('historical_years')` | `claude_extractor.py:1580`, verified by scratch test |
| `entry[field]` for each line field in `_row_scale_failures` | stops and raises `KeyError('<field>')` | `claude_extractor.py:1586`, verified by scratch test |
| `data["latest_balance_sheet"]` in `_row_scale_failures` | stops and raises `KeyError('latest_balance_sheet')` | `claude_extractor.py:1594`, verified by scratch test |
| `balance[field]` for each line field in `_row_scale_failures` | stops and raises `KeyError('<field>')` | `claude_extractor.py:1598`, verified by scratch test |
| `page_texts[page]` in `_row_scale_failures` | stops and raises `KeyError(page)` if outside `page_texts` | `claude_extractor.py:1634` |
| `page_texts[p]` in candidate check | stops and raises `KeyError(p)` if outside `page_texts` | `claude_extractor.py:1647` |

---

## Measurements

### Gates
- **Pytest (excluding p14b test file):** 2 failed (known red), 1032 passed (`.venv/bin/python -m pytest -q --ignore=tests/unit/test_p14b_note_figures.py`)
- **Pytest (full suite):** 23 failed (2 known red + 21 in `test_p14b_note_figures.py` awaiting tester round 2 update), 1040 passed
- **Ruff:** 4 errors (all `BLE001`, unchanged)
- **Mypy:** 8 errors in 3 files (`claude_extractor.py` clean, unchanged)
- **Rule 3 Census:** 65 (`grep -rnE ... | wc -l`, unchanged)
- **Web root route:** HTTP 200
- **Guard check:** 48/48 correct (`.venv/bin/python .claude/check_guard.py`)

### Criterion 10 — Scan across all 16 filings
Script:
```python
import glob, re
from ingestion.session_extraction import (_STATEMENT_PATTERNS, _matches, _page_texts,
    _page_count, _TITLE_LINE_MAX_CHARS)
from ingestion.claude_extractor import (_PARENTHESISED_GROUP, _whitespace_normalised,
    printed_scale)

def money_scales(text):
    out = []
    if not text:
        return out
    for g in _PARENTHESISED_GROUP.findall(_whitespace_normalised(text)):
        if any(w in g.casefold() for w in ('thousands', 'millions', 'billions')):
            try:
                out.append((g, printed_scale(g, 'money figures').word))
            except ValueError:
                pass
    return out

pdfs = sorted(glob.glob('10K_filings/*/*.pdf'))
for pdf in pdfs:
    total = _page_count(pdf)
    pages = dict(_page_texts(pdf, 1, total))
    name = pdf.split('/')[-1].replace('_English.pdf', '')
    for label, pattern in _STATEMENT_PATTERNS:
        heads = [n for n, t in pages.items() if t and any(
            _matches(l, pattern) and len(l.strip()) <= _TITLE_LINE_MAX_CHARS
            and not re.search(r'\d', l) for l in t.splitlines())]
        for h in heads:
            for p in (h, h + 1):
                if p > total:
                    continue
                found = money_scales(pages.get(p)) + (money_scales(pages.get(p - 1)) if p > 1 else [])
                words = sorted({w for _, w in found})
                first = (pages.get(p) or '').strip().splitlines()[:1]
                tag = 'OK ' if found else 'NONE'
                # record results
```

**Summary: 320 checked, 249 OK, 71 NONE**

| Filing | Checked | OK | NONE |
|---|---|---|---|
| AbbVie Inc._10-K_2023-12-31 | 16 | 16 | 0 |
| AbbVie Inc._10-K_2024-12-31 | 12 | 12 | 0 |
| AbbVie Inc._10-K_2025-12-31 | 10 | 10 | 0 |
| Chipotle Mexican Grill Inc._10-K_2023-12-31 | 12 | 9 | 3 |
| Chipotle Mexican Grill Inc._10-K_2024-12-31 | 18 | 6 | 12 |
| Chipotle Mexican Grill Inc._10-K_2025-12-31 | 16 | 6 | 10 |
| L3Harris Technologies Inc._10-K_2023-12-29 | 28 | 27 | 1 |
| L3Harris Technologies Inc._10-K_2025-01-03 | 38 | 33 | 5 |
| L3Harris Technologies Inc._10-K_2026-01-02 | 32 | 26 | 6 |
| Okta Inc._10-K_2024-01-31 | 24 | 15 | 9 |
| Okta Inc._10-K_2025-01-31 | 22 | 12 | 10 |
| Okta Inc._10-K_2026-01-31 | 20 | 9 | 11 |
| Walmart Inc._10-K_2023-01-31 | 18 | 18 | 0 |
| Walmart Inc._10-K_2024-01-31 | 20 | 18 | 2 |
| Walmart Inc._10-K_2025-01-31 | 18 | 16 | 2 |
| Walmart Inc._10-K_2026-01-31 | 16 | 16 | 0 |
| **Total** | **320** | **249** | **71** |

**All 71 NONE Occurrences (all Note, MD&A, or audit pages by first line; 0 primary statement pages):**
1. `Chipotle Mexican Grill Inc._10-K_2023-12-31` | balance sheet | title p27 | checked p28 | `41`
2. `Chipotle Mexican Grill Inc._10-K_2023-12-31` | balance sheet | title p29 | checked p29 | `We defer revenue associated with the estimated selling price`
3. `Chipotle Mexican Grill Inc._10-K_2023-12-31` | balance sheet | title p29 | checked p30 | `potential common shares would have an anti-dilutive effect.`
4. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | income statement | title p34 | checked p34 | `income, net on the consolidated statements of income and com`
5. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | income statement | title p34 | checked p35 | `At least annually, or when impairment indicators are present`
6. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | income statement | title p37 | checked p37 | `Table of Contents`
7. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | income statement | title p37 | checked p38 | `vesting period. Compensation expense is recognized ratably f`
8. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | balance sheet | title p34 | checked p34 | `income, net on the consolidated statements of income and com`
9. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | balance sheet | title p34 | checked p35 | `At least annually, or when impairment indicators are present`
10. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | balance sheet | title p36 | checked p36 | `We are involved in various claims and legal actions that ari`
11. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | balance sheet | title p36 | checked p37 | `Table of Contents`
12. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | balance sheet | title p37 | checked p37 | `Table of Contents`
13. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | balance sheet | title p37 | checked p38 | `vesting period. Compensation expense is recognized ratably f`
14. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | balance sheet | title p38 | checked p38 | `vesting period. Compensation expense is recognized ratably f`
15. `Chipotle Mexican Grill Inc._10-K_2024-12-31` | balance sheet | title p38 | checked p39 | `impact of adopting the new rules and continue to monitor the`
16. `Chipotle Mexican Grill Inc._10-K_2025-12-31` | income statement | title p33 | checked p33 | `for the identical or similar investment of the same issuer.`
17. `Chipotle Mexican Grill Inc._10-K_2025-12-31` | income statement | title p33 | checked p34 | `Leasehold improvements and buildings 3-20 years`
18. `Chipotle Mexican Grill Inc._10-K_2025-12-31` | balance sheet | title p33 | checked p33 | `for the identical or similar investment of the same issuer.`
19. `Chipotle Mexican Grill Inc._10-K_2025-12-31` | balance sheet | title p33 | checked p34 | `Leasehold improvements and buildings 3-20 years`
20. `Chipotle Mexican Grill Inc._10-K_2025-12-31` | balance sheet | title p35 | checked p35 | `43`
21. `Chipotle Mexican Grill Inc._10-K_2025-12-31` | balance sheet | title p35 | checked p36 | `including historical redemption patterns, and expected remit`
22. `Chipotle Mexican Grill Inc._10-K_2025-12-31` | balance sheet | title p36 | checked p36 | `including historical redemption patterns, and expected remit`
23. `Chipotle Mexican Grill Inc._10-K_2025-12-31` | balance sheet | title p36 | checked p37 | `achievement versus stated targets or criteria over a three-y`
24. `Chipotle Mexican Grill Inc._10-K_2025-12-31` | balance sheet | title p37 | checked p37 | `achievement versus stated targets or criteria over a three-y`
25. `Chipotle Mexican Grill Inc._10-K_2025-12-31` | balance sheet | title p37 | checked p38 | `begin capitalizing software costs when 1) management has aut`
26. `L3Harris Technologies Inc._10-K_2023-12-29` | balance sheet | title p31 | checked p32 | `Inventories — Inventories are valued at the lower of cost (d`
27. `L3Harris Technologies Inc._10-K_2025-01-03` | income statement | title p49 | checked p49 | `earnings and cash flows arising from the follow-on revenues`
28. `L3Harris Technologies Inc._10-K_2025-01-03` | income statement | title p49 | checked p50 | `and obligations. We do not account for contract modification`
29. `L3Harris Technologies Inc._10-K_2025-01-03` | balance sheet | title p37 | checked p37 | `impact of tax planning strategies changes, we could be requi`
30. `L3Harris Technologies Inc._10-K_2025-01-03` | balance sheet | title p37 | checked p38 | `We have exposure to interest rate risk associated with our f`
31. `L3Harris Technologies Inc._10-K_2025-01-03` | balance sheet | title p91 | checked p92 | `____________________________________________________________`
32. `L3Harris Technologies Inc._10-K_2026-01-02` | income statement | title p42 | checked p42 | `operating and finance leases, respectively.`
33. `L3Harris Technologies Inc._10-K_2026-01-02` | income statement | title p42 | checked p43 | `We categorize revenue and costs for performance obligations`
34. `L3Harris Technologies Inc._10-K_2026-01-02` | balance sheet | title p33 | checked p33 | `sufficient to generate the amount of future taxable income n`
35. `L3Harris Technologies Inc._10-K_2026-01-02` | balance sheet | title p33 | checked p34 | `____________________________________________________________`
36. `L3Harris Technologies Inc._10-K_2026-01-02` | balance sheet | title p42 | checked p42 | `operating and finance leases, respectively.`
37. `L3Harris Technologies Inc._10-K_2026-01-02` | balance sheet | title p42 | checked p43 | `We categorize revenue and costs for performance obligations`
38. `Okta Inc._10-K_2024-01-31` | income statement | title p73 | checked p73 | `Short-Term Investments`
39. `Okta Inc._10-K_2024-01-31` | income statement | title p73 | checked p74 | `Shorter of estimated useful life or`
40. `Okta Inc._10-K_2024-01-31` | balance sheet | title p70 | checked p70 | `cancellable and non-refundable. Furthermore, if a customer r`
41. `Okta Inc._10-K_2024-01-31` | balance sheet | title p70 | checked p71 | `contracts and incremental sales to existing customers) are d`
42. `Okta Inc._10-K_2024-01-31` | balance sheet | title p71 | checked p71 | `contracts and incremental sales to existing customers) are d`
43. `Okta Inc._10-K_2024-01-31` | balance sheet | title p71 | checked p72 | `83`
44. `Okta Inc._10-K_2024-01-31` | balance sheet | title p73 | checked p73 | `Short-Term Investments`
45. `Okta Inc._10-K_2024-01-31` | balance sheet | title p73 | checked p74 | `Shorter of estimated useful life or`
46. `Okta Inc._10-K_2024-01-31` | cash flow statement | title p68 | checked p69 | `Cash and cash equivalents $ 334 $ 264 $ 260`
47. `Okta Inc._10-K_2025-01-31` | income statement | title p67 | checked p67 | `unrealized losses in securities that the Company intends to`
48. `Okta Inc._10-K_2025-01-31` | income statement | title p67 | checked p68 | `expected future cash flows associated with individual assets`
49. `Okta Inc._10-K_2025-01-31` | balance sheet | title p64 | checked p64 | `Revenue is derived from subscription fees (which include sup`
50. `Okta Inc._10-K_2025-01-31` | balance sheet | title p64 | checked p65 | `factors. Sales commissions for renewal contracts are deferre`
51. `Okta Inc._10-K_2025-01-31` | balance sheet | title p65 | checked p65 | `factors. Sales commissions for renewal contracts are deferre`
52. `Okta Inc._10-K_2025-01-31` | balance sheet | title p65 | checked p66 | `volatility. The risk-free interest rate was based on the U.S`
53. `Okta Inc._10-K_2025-01-31` | balance sheet | title p66 | checked p66 | `volatility. The risk-free interest rate was based on the U.S`
54. `Okta Inc._10-K_2025-01-31` | balance sheet | title p66 | checked p67 | `unrealized losses in securities that the Company intends to`
55. `Okta Inc._10-K_2025-01-31` | cash flow statement | title p53 | checked p54 | `When we acquire a business, the purchase price is allocated`
56. `Okta Inc._10-K_2025-01-31` | cash flow statement | title p62 | checked p63 | `NOTES TO CONSOLIDATED FINANCIAL STATEMENTS`
57. `Okta Inc._10-K_2026-01-31` | income statement | title p65 | checked p65 | `Cash and cash equivalents consist of cash on hand and highly`
58. `Okta Inc._10-K_2026-01-31` | income statement | title p65 | checked p66 | `OKTA, INC.`
59. `Okta Inc._10-K_2026-01-31` | balance sheet | title p61 | checked p62 | `Use of Estimates`
60. `Okta Inc._10-K_2026-01-31` | balance sheet | title p63 | checked p63 | `The Company determines SSP based on observable, if available`
61. `Okta Inc._10-K_2026-01-31` | balance sheet | title p63 | checked p64 | `requirements in certain foreign jurisdictions. Severance cos`
62. `Okta Inc._10-K_2026-01-31` | balance sheet | title p64 | checked p64 | `requirements in certain foreign jurisdictions. Severance cos`
63. `Okta Inc._10-K_2026-01-31` | balance sheet | title p64 | checked p65 | `Cash and cash equivalents consist of cash on hand and highly`
64. `Okta Inc._10-K_2026-01-31` | balance sheet | title p65 | checked p65 | `Cash and cash equivalents consist of cash on hand and highly`
65. `Okta Inc._10-K_2026-01-31` | balance sheet | title p65 | checked p66 | `OKTA, INC.`
66. `Okta Inc._10-K_2026-01-31` | balance sheet | title p67 | checked p67 | `Operating Leases and Incremental Borrowing Rate`
67. `Okta Inc._10-K_2026-01-31` | cash flow statement | title p61 | checked p62 | `Use of Estimates`
68. `Walmart Inc._10-K_2024-01-31` | income statement | title p54 | checked p54 | `the redemption value of the redeemable noncontrolling intere`
69. `Walmart Inc._10-K_2024-01-31` | balance sheet | title p54 | checked p54 | `the redemption value of the redeemable noncontrolling intere`
70. `Walmart Inc._10-K_2025-01-31` | income statement | title p53 | checked p53 | `The recoverability of the deferred tax assets is evaluated b`
71. `Walmart Inc._10-K_2025-01-31` | income statement | title p53 | checked p54 | `63`

---

## What I did not do

- Did not touch `tests/` (`tests/unit/test_p14b_note_figures.py`). Per `programmer.md`, `tests/` is out of scope for the programmer; the tester updates test fixtures and locks F1 and F5 in round 2.
- Did not touch files outside the assigned scope (`ingestion/claude_extractor.py`, `docs/3-architecture/extraction.md`, `docs/2-rules/llm-boundary.md`).

---

## Findings for the orchestrator

None. All review findings F1 through F6 are addressed and verified.
