---
agent: programmer
assignment: P15a-two-routes
round: 2
status: complete
files_touched:
  - README.md
---

# P15a-two-routes round 2 — Answer review findings F1-F3 and restore Python prerequisite in README.md

## What I did

Addressed the overall lead's review findings for `P15a-two-routes` (round 2 revision):
- **F1 (tester)**: Owned by the tester. Notes that the test suite was updated in `75b31aa` to use placeholder `GEMINI_API_KEY` for route A tests; verified that with empty-key prefix (`ANTHROPIC_API_KEY= GEMINI_API_KEY=`), the test gate passes 1032 tests (0 failures).
- **F2 (programmer)**: Restored `- Python 3.10+` under `### Prerequisites` in `README.md`. In round 1, that line was inadvertently removed when replacing the provider prerequisites.
- **F3 (build lead)**: Process finding owned by the build lead; all gate commands re-measured below with the empty-key prefix.

## Findings, by number

### F1 (major, tester) — Test gate with empty keys
- **Review finding**: `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` failed 21 tests in round 1 because tests set placeholder `ANTHROPIC_API_KEY` rather than `GEMINI_API_KEY`.
- **Status for programmer**: `tests/` is out of scope for the programmer per `.claude/agents/programmer.md` ("What you may never touch: `tests/`"). Commit `75b31aa` (P15a tester) updated the test fixtures and route tests.
- **Re-measurement**:
  - `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` → **1032 passed** in 10.83s.
  - Without empty keys: `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` → **1032 passed** in 10.87s.
  - Full suite: `.venv/bin/python -m pytest -q` → **2 failed, 1032 passed** in 11.02s (only the two deliberately red tests fail: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`).

### F2 (minor, programmer) — Restore Python 3.10+ in README.md
- **Review finding**: `README.md` lost the line `- Python 3.10+` under Prerequisites. It names neither the Anthropic API nor a key, so it was outside the scope. Restore it.
- **Resolution**: Restored `- Python 3.10+` immediately above `- A Google Gemini API key (route A extraction) or a Claude Code session file (route B extraction)` in `README.md`.
- **Evidence**:
  ```markdown
  ### Prerequisites

  - Python 3.10+
  - A Google Gemini API key (route A extraction) or a Claude Code session file (route B extraction)
  ```
  `git diff README.md` shows exactly one line added back: `+ - Python 3.10+`.

### F3 (process, build lead) — Step 8 completion
- **Review finding**: Step 8 did not run: no gates, no commit, no `## Handoff`, and the queue still said `building`. After F1 and F2, run step 8 in full. Run every gate with the empty-key prefix.
- **Status for programmer**: Process finding owned by the build lead upon completion of programmer and tester runs.

---

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | no Foundry or Anthropic API path is left | pass | `grep -rniE --exclude='*.pyc' "foundry\|entra\|azure\|anthropic" ingestion config.py requirements.txt cli.py api templates` exits 1 (0 text hits). |
| 2 | the app imports without `anthropic` and `azure` | pass | `.venv/bin/python -c "import sys; sys.modules['anthropic'] = None; sys.modules['azure'] = None; import app, cli, ingestion.claude_extractor"` exits 0. |
| 3 | Claude on route A stops and names route B | pass | `.venv/bin/python -c "from ingestion.claude_extractor import resolve_provider; resolve_provider('claude', None)"` raises `ValueError: Claude reads a filing only in a Claude Code session (route B), on the user's decision of 2026-10-04. Run the 'extract-filing' skill and pass --session-file (CLI) or upload the session file (web). Route A uses Gemini, with GEMINI_API_KEY.` |
| 4 | Gemini is the default and resolves | pass | `GEMINI_API_KEY=fake-key .venv/bin/python -c "import config; from ingestion.claude_extractor import resolve_provider; print(resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None))"` returns `ProviderResolution(provider='gemini', model='gemini-3.1-pro-preview', reasoning_label="the provider's default; this code sets no thinking for Gemini", transport='gemini-direct', transport_label='Google Gemini API (generativelanguage.googleapis.com)', credential='gemini-api-key', credential_source='GEMINI_API_KEY (shell or parent process, not .env)')`. |
| 5 | no Gemini key names both routes | pass | `GEMINI_API_KEY= .venv/bin/python -c "import config; from ingestion.claude_extractor import resolve_provider; resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)"` raises `ValueError: GEMINI_API_KEY is not set, so extraction cannot start. Either remedy is sufficient:\n  (1) Set GEMINI_API_KEY in .env or the system environment to use the Gemini API (route A); or\n  (2) Extract in a Claude Code session with the 'extract-filing' skill and run with --session-file (route B).` |
| 6 | the CLI refuses `-p claude` | pass | `.venv/bin/python cli.py -p claude 10K_filings/Walmart` exits 2 with `cli.py: error: argument -p/--provider: invalid choice: 'claude' (choose from 'gemini')`. `cli.py --help` shows `LLM provider (default: gemini). Claude reads a filing only through --session-file`. |
| 7 | route A runs end to end with Gemini, stubbed | pass | Scratch test executed with `socket.socket.connect` monkeypatched to raise `RuntimeError("Network socket attempted!")`: `_call_gemini` stubbed with Walmart Pass 1 & Pass 2 JSON from `extractions/WMT.json`; `extract_financials` on Walmart FY2026 PDF with `provider="gemini"` matched route B statements (`stmts == b_stmts`) and items (`items == b_items`) byte-for-byte; all page checks passed (89 printed lines found, 4 Pass 2 items found); 2 stub calls, 0 network socket attempts. |
| 8 | route B does not move | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json` yields $28.02 implied share price; `Provider: CLAUDE \| Model: claude-opus-5-5 \| Reasoning: as the Claude Code session ran; not set by this code \| Transport: Claude Code session — figures read from the PDF in a Claude Code session... \| Credential: none — no API call was made`. |
| 9 | the web app | pass | `TestClient(app.app).get('/')` returns 200. `TestClient(app.app).get('/assumptions', params={'session_file': 'extractions/WMT.json'})` returns 200 and renders `CLAUDE` and `Claude Code session`. |
| 10 | the gates do not get worse | pass | Ruff: 4 errors (all `BLE001`, unchanged). Mypy: 8 errors in 3 files (improved from 9 errors in 4 files; `claude_extractor.py` is clean). Census: 65 (unchanged). Guard: 48/48 (unchanged). |
| 11 | every red test is named | pass | Only the 2 known deliberately red tests fail (`test_projector_rule3_red.py` and `test_routes_session_rule3_red.py`); 1032 tests pass. |
| 12 | not measured here | not run | A real Gemini call on Walmart: not run. It is a paid call on the user's key; the overall lead asks the user. |

---

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Restore `- Python 3.10+` in `README.md` | F2 from overall lead review | Preserves required prerequisites documentation outside the scope of provider changes. |
| Leave `tests/` to tester | `.claude/agents/programmer.md` rules | Programmer is strictly forbidden from editing `tests/`. |

---

## Rule 3 — what stops, and what does not

For every value this unit reads, one row. This is the table the reviewer checks first.

| Value read | If it were missing | Evidence |
|---|---|---|
| `provider` in `resolve_provider` | stops if `"claude"` naming route B; stops if not `"gemini"` naming valid choices | `ingestion/claude_extractor.py:2557-2566` |
| `model` in `_resolve_model` | stops if empty string (`""` or `" "`); uses default if `None` | `ingestion/claude_extractor.py:2516-2521` |
| `GEMINI_API_KEY` in `_resolve_gemini` | stops and names `GEMINI_API_KEY` and `--session-file` | `ingestion/claude_extractor.py:2525-2532` |
| `GEMINI_API_KEY` in `_call_gemini` | stops if empty string (`""`) | `ingestion/claude_extractor.py:1770-1774` |
| `resolution.provider` in `_call_llm` | stops and names provider and transport if not `"gemini"` | `ingestion/claude_extractor.py:1811-1815` |
| `-p/--provider` CLI argument in `cli.py` | stops with argparse invalid choice error if not `"gemini"` | `cli.py:121-127` |

---

## Measurements

### Gates comparison

| Gate | Before (`158f25d`) | After (`P15a-two-routes` r2) |
|---|---|---|
| Tests (gate form, with empty keys) | 1021 passed, 0 failed | **1032 passed, 0 failed** |
| Tests (full suite) | 2 failed, 1021 passed | **2 failed, 1032 passed** (the 2 red on purpose) |
| Ruff | 4 errors (`BLE001`) | 4 errors (`BLE001`) |
| Mypy | 9 errors in 4 files | 8 errors in 3 files (`claude_extractor.py` clean) |
| Rule 3 census | 65 | 65 |
| Write guard | 48/48 | 48/48 |
| Route `GET /` | 200 | 200 |

---

## What I did not do

- Did not touch `tests/`: out of scope for programmer; owned by the tester in `P15a-two-routes-tests`.
- Did not touch `.env`: user file; out of scope.
- Did not touch `STATUS.md` or `.agent/journal/INDEX.md`: sealed files owned exclusively by orchestrator.
- Did not touch `api/` or `ingestion/session_extraction.py`: out of scope.
- Did not add DeepSeek: user's decision 2a.
- Did not make any real API call to Gemini (criterion 12).

## Findings for the orchestrator

- None. Both F1 and F2 are satisfied. The gates pass cleanly under the required empty-key prefix.
