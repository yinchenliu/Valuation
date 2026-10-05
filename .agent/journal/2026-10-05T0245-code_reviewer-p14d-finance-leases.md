---
agent: code_reviewer
assignment: P14d-finance-leases
round: 1
verdict: approved
---

# Review of P14d-finance-leases, round 1

Programmer entry: `.agent/journal/2026-10-05T0233-programmer-p14d-finance-leases.md`

## The guard checks

Run over the assignment's **Files in scope** (`ingestion/claude_extractor.py`, `cli.py`, `docs/3-architecture/data-contract.md`, `docs/3-architecture/valuation-math.md`, `docs/3-architecture/extraction.md`).

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean in touched lines; 3 pre-existing in `cli.py` (lines 210, 1059, 1067) untouched |
| lookup with a fallback — `.get(k, 0)` | clean in touched lines; 5 pre-existing in `ingestion/claude_extractor.py` (lines 1896, 2113, 2114, 2163, 2678), 1 in `cli.py` (line 1063) untouched |
| bare or-default — `or 0.0` | clean in touched lines; 3 pre-existing in `ingestion/claude_extractor.py` (lines 1925-1927) untouched |
| money field defaulted to zero — `: float = 0.0` | clean (0 hits) |
| `**kwargs` on a calculation function | clean (0 hits) |
| `getattr(` on a name from outside the file | clean in touched lines; 2 pre-existing in `ingestion/claude_extractor.py` (lines 1926-1927), 1 in `cli.py` (line 706) untouched |
| dict of functions keyed by data | clean (0 hits) |
| model client imported outside `ingestion/` | clean (0 hits in `models/`, `analysis/`, `api/`) |

## Rule 3, by reading

The greps catch the four written forms. This table catches the rest. For every value
the unit reads, ask: if it were missing, what happens?

| Value | Stops and names it? | Evidence |
|---|---|---|
| `payload[0]` (format marker) in `cli._load_cache` | stops and raises `ValueError` explicitly naming expected marker `'p14d-finance-leases-v1'` | `cli.py:237, 361-367`, re-verified by scratch test |
| Schema & prompt text in `ingestion/claude_extractor.py` | constant strings defining schema descriptions and prompt instructions; no runtime dynamic value lookup | `ingestion/claude_extractor.py:193-195, 341-343` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean — debt lines extracted from filing tables as printed; converted once to millions per filing by `convert_filing_to_millions` |
| percentages converted at the route boundary, once | clean — no percentage inputs added or modified |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean — no falsy conditionals added |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean — `analysis/` untouched; layering intact |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | the schema names the rule | pass | pass (`grep -n "finance lease\|operating lease" ingestion/claude_extractor.py` hits lines 190, 193, 194, 195, 196, 341-343; lines 194 and 195 explicitly include finance leases in debt and exclude operating leases; line 193 includes operating leases due within one year in other current liabilities; prompt lines 341-343 state the rule) | Agree |
| 2 | both routes read the rule | pass | pass (`.venv/bin/python -m ingestion.session_extraction prompt extractions/WMT.json --filing 0 --pass 1 \| grep "finance lease"` outputs both schema lines and prompt rule text) | Agree |
| 3 | route B's Walmart does not move | pass | pass (`session_extraction check extractions/WMT.json` exits 0; `cli.py --session-file extractions/WMT.json` outputs `short_term_debt` 10,994, `long_term_debt` 40,529, total debt 51,523, net debt 40,796, implied price $28.02, downside -73.1%, matches baseline) | Agree |
| 4 | an old cache is refused | pass | pass (scratch pickle marked `p14b-pass2-units-v1` raises `ValueError` naming expected marker `'p14d-finance-leases-v1'`) | Agree |
| 5 | the gates do not get worse | pass | pass (`ruff check .` -> 4 errors, all `BLE001`; `mypy` -> 8 errors in 3 files; Rule 3 census -> 65; `GET /` -> 200; `check_guard.py` -> 48/48) | Agree |
| 6 | every red test is named | pass | pass (Full suite: 4 failed, 1064 passed. 2 deliberate red in `*_rule3_red.py`; 2 old cache format marker tests in `test_p14a_units.py` and `test_p14b_units.py` asserting `p14b-pass2-units-v1`, out of scope for programmer and reserved for tester in `P14d-finance-leases-tests`) | Agree |

## Findings

None.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 72 (conditional zeros in CLI) | `cli.py:1059, 1067` | No |
| 82 (CLI cache key model default) | `cli.py:347` | No |
| 8 (blanket `except Exception`) | `api/routes_valuation.py:445, 729`, `cli.py:1168`, `tests/test_e2e_all_googl.py:106` | No |
| 11 (type errors) | `analysis/projector.py`, `api/routes_upload.py`, `api/routes_valuation.py` | No |

## Verdict

`approved`

Work unit `P14d-finance-leases` implements the user's decision "83a" (backlog item 83) correctly and completely within the exact files in scope. The balance sheet schema and system prompt now instruct both extraction routes that finance lease obligations are debt (current portion in `short_term_debt`, long-term obligations in `long_term_debt`) and operating lease obligations are not debt (mapped to `other_current_liabilities` and `other_non_current_liabilities`). `CACHE_FORMAT` in `cli.py` was bumped to `"p14d-finance-leases-v1"`, and cache validation stops and names the expected marker. Walmart extraction and valuation remain exact ($28.02, net debt 40,796M). All gates pass with no regression, and the only test failures are the two deliberate red tests plus two existing cache marker tests in `test_p14a_units.py` and `test_p14b_units.py` to be locked by the tester in `P14d-finance-leases-tests`.
