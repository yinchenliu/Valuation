---
agent: code_reviewer
assignment: P15a-two-routes
round: 1
verdict: approved
---

# Review of P15a-two-routes, round 1

Programmer entry: `.agent/journal/2026-10-04T1626-programmer-p15a-two-routes.md`

## The guard checks

Run over the assignment's **Files in scope** (`config.py`, `cli.py`, `requirements.txt`, `ingestion/claude_extractor.py`, `README.md`, `docs/8-build/environment.md`, `docs/3-architecture/extraction.md`, `docs/3-architecture/data-contract.md`, `docs/2-rules/llm-boundary.md`):

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean in diff. 3 pre-existing hits in `cli.py:210, 1059, 1067` (backlog item 72), untouched |
| lookup with a fallback — `.get(k, 0)` | clean in diff. `_resolve_gemini` reads `os.environ.get("GEMINI_API_KEY", "").strip()` and immediately stops if empty; 5 pre-existing hits in `ingestion/claude_extractor.py` (1751, 1968, 1969, 2018) and `cli.py:1063`, untouched |
| bare or-default — `or 0.0` | clean in diff. 3 pre-existing hits in `ingestion/claude_extractor.py:1780-1782` (backlog item 1/63), untouched |
| money field defaulted to zero — `: float = 0.0` | clean in diff (0 hits) |
| `**kwargs` on a calculation function | clean in diff (0 hits) |
| `getattr(` on a name from outside the file | clean in diff. 3 pre-existing hits in `ingestion/claude_extractor.py:1781-1782` and `cli.py:706`, untouched |
| dict of functions keyed by data | clean in diff (0 hits) |
| model client imported outside `ingestion/` | clean in diff (0 hits) |

**A hit is a question, not automatically a finding.** All pre-existing hits in files in scope are outside modified lines and untouched.

## Rule 3, by reading

The greps catch the four written forms. This table catches the rest. For every value the unit reads, ask: if it were missing, what happens?

| Value | Stops and names it? | Evidence |
|---|---|---|
| `provider == "claude"` in `resolve_provider` | Stops: raises `ValueError` naming route B, the `extract-filing` skill, `--session-file` (CLI), session file upload (web), and route A's use of Gemini with `GEMINI_API_KEY` | `ingestion/claude_extractor.py:2556-2562` |
| `provider` not `"gemini"` in `resolve_provider` | Stops: raises `ValueError` naming invalid provider | `ingestion/claude_extractor.py:2563-2564` |
| `GEMINI_API_KEY` in `_resolve_gemini` | Stops: raises `ValueError` naming both remedies (GEMINI_API_KEY in .env/env for route A, or `--session-file` with Claude Code session for route B) | `ingestion/claude_extractor.py:2525-2531` |
| `resolution.provider != "gemini"` in `_call_llm` | Stops: raises `ValueError` naming unexpected provider and transport | `ingestion/claude_extractor.py:1810-1814` |
| `-p claude` CLI argument in `cli.py` | Stops: argparse error stating invalid choice `'claude'` (choose from `'gemini'`) | `cli.py:124` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean: stubbed Gemini extraction matched route B byte-for-byte and gave identical $28.02 valuation |
| percentages converted at the route boundary, once | clean: no changes to financial parameter conversions |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean: provider comparisons use explicit string equality; missing model defaults cleanly when `None` and stops on empty string `""` |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean: `analysis/` was untouched |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | no Foundry or Anthropic API path is left | pass | `grep -rniE --exclude='*.pyc' "foundry\|entra\|azure\|anthropic" ingestion config.py requirements.txt cli.py api templates` exits 1 (0 hits). | Agree |
| 2 | the app imports without `anthropic` and `azure` | pass | `.venv/bin/python -c "import sys; sys.modules['anthropic'] = None; sys.modules['azure'] = None; import app, cli, ingestion.claude_extractor"` exits 0. | Agree |
| 3 | Claude on route A stops and names route B | pass | Scratch call of `resolve_provider("claude", None)` raises `ValueError` naming `extract-filing`, `--session-file`, and `GEMINI_API_KEY`. | Agree |
| 4 | Gemini is the default and resolves | pass | `GEMINI_API_KEY=fake-key` resolves `ProviderResolution(provider='gemini', model='gemini-3.1-pro-preview', reasoning_label="the provider's default; this code sets no thinking for Gemini", transport='gemini-direct', transport_label='Google Gemini API (generativelanguage.googleapis.com)', credential='gemini-api-key', credential_source='GEMINI_API_KEY (shell or parent process, not .env)')`. | Agree |
| 5 | no Gemini key names both routes | pass | `GEMINI_API_KEY=` raises `ValueError` naming both remedies (1) `GEMINI_API_KEY` and (2) `--session-file`. | Agree |
| 6 | the CLI refuses `-p claude` | pass | `.venv/bin/python cli.py -p claude 10K_filings/Walmart` exits 2 with invalid choice error. `cli.py --help` shows `default: gemini` and explains Claude reads filings through `--session-file`. | Agree |
| 7 | route A runs end to end with Gemini, stubbed | pass | Sockets blocked with `socket.socket.connect` raising `RuntimeError`. `_call_gemini` stubbed with Walmart Pass 1/2 from `extractions/WMT.json` against real Walmart 10-K PDF: financials and NRI matched route B byte-for-byte; 89/89 printed lines verified on cited pages; 4/4 NRI verified on cited pages; 2 stub calls, 0 network socket attempts. | Agree |
| 8 | route B does not move | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json`: implied price $28.02, downside -73.1%, Provider: CLAUDE, Model: claude-opus-5-5, Reasoning: as the Claude Code session ran; not set by this code, Transport: Claude Code session, Credential: none. | Agree |
| 9 | the web app | pass | `TestClient(app.app).get('/')` returns 200. `TestClient(app.app).get('/assumptions', params={'session_file': 'extractions/WMT.json'})` returns 200 and renders `CLAUDE` and `Claude Code session`. | Agree |
| 10 | the gates do not get worse | pass | ruff: 4 errors (`BLE001`, exact baseline).<br>mypy: 8 errors in 3 files (improved from 9 in 4 files; `claude_extractor.py` clean).<br>Rule 3 census: 65 (exact baseline).<br>write guard: 48/48 (exact baseline). | Agree |
| 11 | every red test is named | pass | Suite has 15 failed, 5 errors, 984 passed (20 total issues: 4 tests stub deleted `_call_claude`, 1 test imports deleted `_CLAUDE_MAX_TOKENS`, 9 tests assert old `CREDENTIAL_NAMES`, 4 route tests assert old Anthropic route A messages, and 2 known deliberately red tests). Strictly expected causes; out of scope for programmer and assigned to `P15a-two-routes-tests`. | Agree |
| 12 | not measured here | not run | Real Gemini API call on Walmart not run (paid API call). | Agree |

## Findings

None.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 (zero defaults in models) | `models/financial_statements.py` | No |
| 8 (blanket `except Exception`) | `cli.py:1168` | No |
| 10 (D&A in Pass 1 parser) | `ingestion/claude_extractor.py:1260` | No |
| 11 (1 mypy error in `_call_claude`) | `ingestion/claude_extractor.py` | **Closed by this unit** (deleted `_call_claude`) |
| 51 (dead `WARN` branch) | `ingestion/claude_extractor.py:270` | No |
| 53 (private `_NRI_SCHEMA` import) | `ingestion/session_extraction.py:84` | No |
| 61 (AssertionError after retry loop) | `ingestion/claude_extractor.py:2532` | No |
| 63 (filing with no text layer) | `ingestion/claude_extractor.py:1611, 1647` | No |
| 64 (page check joined-line form) | `ingestion/claude_extractor.py:1460` | No |
| 70 (PV of terminal value variance) | stage 10 | No |
| 72 (conditional zeros in cli) | `cli.py:210, 1059, 1067` | No |
| 73 (first Pass 2 reply stops without filing name) | `ingestion/claude_extractor.py:2570` | No |
| 74 (OverflowError/RecursionError in Pass 2) | `ingestion/claude_extractor.py:2600` | No |
| 78 (already converted guard sees BS only) | `ingestion/claude_extractor.py:3145` | No |
| 79 (route A unit stop names field/text/page but not PDF) | `ingestion/claude_extractor.py:2612` | No |
| 80 (arithmetic check in printed units) | `ingestion/claude_extractor.py:1568` | No |

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| — | — | Round 1 |

## Verdict

`approved`

The unit cleanly implements the user's decisions of 2026-10-04 ("1a, 2a") across all files in scope. The Microsoft Foundry gateway, Entra ID authentication, and Anthropic API paths have been completely purged from shipped code, with `anthropic` and `azure-identity` removed from `requirements.txt`. Route A now routes exclusively to Gemini with `config.DEFAULT_EXTRACTION_PROVIDER = "gemini"` and `CREDENTIAL_NAMES = ("GEMINI_API_KEY",)`. Route B remains unchanged for Claude Code session extractions, and any invocation of Claude on route A (`resolve_provider("claude", ...)` or CLI `-p claude`) stops immediately and directs the user to route B. All 11 testable done-criteria pass upon re-execution, gates remain clean with mypy improving from 9 to 8 errors, and the 20 test suite failures/errors are strictly confirmed to stem from deleted Claude route A code and credential configurations to be addressed by the tester in `P15a-two-routes-tests`.
