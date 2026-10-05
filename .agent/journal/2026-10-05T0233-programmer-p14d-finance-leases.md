---
agent: programmer
assignment: P14d-finance-leases
round: 1
status: complete
files_touched:
  - ingestion/claude_extractor.py
  - cli.py
  - docs/3-architecture/data-contract.md
  - docs/3-architecture/valuation-math.md
  - docs/3-architecture/extraction.md
---

# P14d-finance-leases — Finance lease obligations are debt; operating lease obligations are not (backlog item 83)

## What I did

Implemented user decision "83a" (backlog item 83): finance lease obligations are debt, operating lease obligations are not.
In `ingestion/claude_extractor.py`, updated `_FINANCIALS_BALANCE_SHEET_SCHEMA` so that `short_term_debt` explicitly includes finance lease obligations due within one year and excludes operating lease obligations; `long_term_debt` explicitly includes long-term finance lease obligations and excludes operating lease obligations; and `other_current_liabilities` explicitly includes operating lease obligations due within one year. In `_FINANCIALS_SYSTEM_PROMPT` (BALANCE SHEET RULES), added the explicit rule that finance lease obligations are debt (current in `short_term_debt`, long-term in `long_term_debt`) and operating lease obligations are not debt (in `other_current_liabilities` and `other_non_current_liabilities`).
In `cli.py`, bumped `CACHE_FORMAT` to `"p14d-finance-leases-v1"` to invalidate previous route A caches that might have placed finance leases in catch-all liabilities.
In documentation, updated `docs/3-architecture/data-contract.md`, `docs/3-architecture/valuation-math.md`, and `docs/3-architecture/extraction.md` to document the lease treatment.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the schema names the rule | pass | `grep -n "finance lease\|operating lease" ingestion/claude_extractor.py` shows hits on lines 190, 193, 194, 195, 196, and 341-343. Lines 194 and 195 name finance lease obligations and state "Not operating lease obligations."; line 193 names operating lease obligations due within one year; lines 341-343 state the balance sheet rule. |
| 2 | both routes read the rule | pass | `.venv/bin/python -m ingestion.session_extraction prompt extractions/WMT.json --filing 0 --pass 1 \| grep "finance lease"` outputs both schema lines and prompt rule text. |
| 3 | route B's Walmart does not move | pass | `.venv/bin/python -m ingestion.session_extraction check extractions/WMT.json` exits 0 (clean). `.venv/bin/python cli.py --session-file extractions/WMT.json` outputs: `short_term_debt` 10,994 (6,596 + 3,542 + 856), `long_term_debt` 40,529 (34,624 + 5,905), total debt 51,523, net debt 40,796, implied price $28.02, downside -73.1%. |
| 4 | an old cache is refused | pass | Scratch pickle marked `p14b-pass2-units-v1` loaded via `cli._load_cache` raises `ValueError` naming expected marker `'p14d-finance-leases-v1'`. |
| 5 | the gates do not get worse | pass | `ruff check .` -> 4 errors (all BLE001); `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` -> 8 errors in 3 files; Rule 3 census -> 65; `GET /` -> 200; `check_guard.py` -> 48/48. |
| 6 | every red test is named | pass | Full suite: 4 failed, 1064 passed. Deliberately red on purpose (2): `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`. Cache marker bump (2): `test_p14a_units.py::test_old_cli_cache_marker_p11a_refused` and `test_p14b_units.py::test_cli_cache_refuses_old_marker` (both assert the previous marker `'p14b-pass2-units-v1'`). |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Finance leases in `short_term_debt` and `long_term_debt` | User decision "83a" (2026-10-04); backlog item 83 | Finance lease obligations represent asset financing liabilities; operating lease obligations are operating expenses/liabilities. Prevents model divergence between Gemini (route A) and Claude (route B). |
| Operating leases in catch-all liabilities | User decision "83a"; assignment P14d-finance-leases | Operating lease obligations are not funded debt in enterprise valuation; keeping them in `other_current_liabilities` and `other_non_current_liabilities` preserves balance sheet balance without affecting total debt. |
| Bump `CACHE_FORMAT` to `"p14d-finance-leases-v1"` | Assignment P14d-finance-leases step 3 | Prevents re-using stale pickles from earlier route A extractions where finance leases might have been categorized outside debt. |

## Rule 3 — what stops, and what does not

For every value this unit reads, one row. This is the table the reviewer checks first.

| Value read | If it were missing | Evidence |
|---|---|---|
| CLI cache payload format marker | stops and raises `ValueError` naming `p14d-finance-leases-v1` | `cli.py:361-367` |

## Measurements

### Suite counts before and after

- **Before** (at commit `ac4af5a`):
  - Pytest full suite: 1068 collected, 1066 passed, 2 failed:
    - `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`
    - `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`
- **After**:
  - Pytest full suite: 1068 collected, 1064 passed, 4 failed:
    - `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` (deliberate red)
    - `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` (deliberate red)
    - `tests/unit/test_p14a_units.py::test_old_cli_cache_marker_p11a_refused` (asserts old expected marker `repr("p14b-pass2-units-v1") in message`)
    - `tests/unit/test_p14b_units.py::test_cli_cache_refuses_old_marker` (asserts old expected marker `"p14b-pass2-units-v1" in msg`)

### Lint
- `ruff check .`: 4 errors, all `BLE001` (unchanged from `ac4af5a`).

### Types
- `mypy models analysis ingestion api config.py app.py --ignore-missing-imports`: 8 errors in 3 files (`projector.py`: 4, `routes_upload.py`: 1, `routes_valuation.py`: 3) (unchanged from `ac4af5a`).

### Rule 3 Census
- `grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" --include='*.py' models analysis api ingestion | wc -l`: 65 (unchanged).

### Routes
- `TestClient(app.app, raise_server_exceptions=False).get('/')`: 200 (unchanged).

### Guard
- `.venv/bin/python .claude/check_guard.py`: 48/48 (unchanged).

### Walmart figures (route B)
- Extraction check: clean, 89/89 lines found, 0 unconfirmed, checks OK.
- `short_term_debt`: 10,994 (6,596 + 3,542 + 856)
- `long_term_debt`: 40,529 (34,624 + 5,905)
- `total_debt`: 51,523
- `net_debt`: 40,796
- `implied_share_price`: $28.02 (unchanged)
- `downside`: -73.1% (unchanged)

## What I did not do

- Did not touch `tests/` (owned by tester in unit `P14d-finance-leases-tests`).
- Did not modify `analysis/` (debt calculation formulas unchanged).
- Did not modify `extractions/WMT.json` (already followed the rule).
- Made no paid API calls (`ANTHROPIC_API_KEY=` and `GEMINI_API_KEY=` kept empty).

## Findings for the orchestrator

None.
