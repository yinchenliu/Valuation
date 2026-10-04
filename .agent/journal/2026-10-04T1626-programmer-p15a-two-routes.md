---
agent: programmer
assignment: P15a-two-routes
round: 1
status: complete
files_touched:
  - config.py
  - cli.py
  - requirements.txt
  - ingestion/claude_extractor.py
  - README.md
  - docs/8-build/environment.md
  - docs/3-architecture/extraction.md
  - docs/3-architecture/data-contract.md
  - docs/2-rules/llm-boundary.md
---

# P15a-two-routes — Two routes only: Gemini API on route A, Claude Code session on route B

## What I did

Implemented the user's decisions of 2026-10-04:
- Removed the Microsoft Foundry gateway and Anthropic API paths completely from shipped code.
- Route A now reads filings through the Google Gemini API with `GEMINI_API_KEY`, and `gemini` is the default provider (`config.DEFAULT_EXTRACTION_PROVIDER = "gemini"`).
- Claude is reached exclusively through a Claude Code session file (`route B`, unchanged).
- Calling `resolve_provider("claude", ...)` or `-p claude` immediately stops and names route B and its remedies.
- `_resolve_gemini`'s stop when `GEMINI_API_KEY` is unset names both remedies (`GEMINI_API_KEY` for route A or `--session-file` for route B) and no longer points back to the default provider.
- `_call_llm` calls `_call_gemini` when `provider == "gemini"` and raises `ValueError` naming provider and transport otherwise.
- Deleted `_call_claude`, `_build_claude_client`, `_resolve_claude`, `_NO_CLAUDE_CREDENTIAL`, `_ENTRA_TOKEN_PROVIDER`, `_entra_token_provider`, `_foundry_endpoint_label`, `"foundry"` and `"anthropic-direct"` from `Transport`, `"foundry-api-key"`, `"entra-token"` and `"anthropic-api-key"` from `CredentialKind`, `_CLAUDE_MAX_TOKENS`, `config.EXTRACTION_EFFORT`, `config.ENTRA_TOKEN_SCOPE`, the `"claude"` entry of `_DEFAULT_MODELS`, and all `anthropic` and `azure` imports from shipped code.
- Removed `anthropic` and `azure-identity` from `requirements.txt`.
- Restricted `cli.py`'s `-p/--provider` choices to `["gemini"]` and updated its help text.
- Updated documentation across `docs/8-build/environment.md`, `docs/3-architecture/extraction.md`, `docs/3-architecture/data-contract.md`, `docs/2-rules/llm-boundary.md`, and `README.md`.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | no Foundry or Anthropic API path is left | pass | `grep -rniE --exclude='*.pyc' "foundry\|entra\|azure\|anthropic" ingestion config.py requirements.txt cli.py api templates` exits 1 (0 text hits). |
| 2 | the app imports without `anthropic` and `azure` | pass | `.venv/bin/python -c "import sys; sys.modules['anthropic'] = None; sys.modules['azure'] = None; import app, cli, ingestion.claude_extractor"` exits 0. |
| 3 | Claude on route A stops and names route B | pass | `.venv/bin/python -c "from ingestion.claude_extractor import resolve_provider; resolve_provider('claude', None)"` raises `ValueError: Claude reads a filing only in a Claude Code session (route B), on the user's decision of 2026-10-04. Run the 'extract-filing' skill and pass --session-file (CLI) or upload the session file (web). Route A uses Gemini, with GEMINI_API_KEY.` |
| 4 | Gemini is the default and resolves | pass | `GEMINI_API_KEY=fake-key .venv/bin/python -c "import config; from ingestion.claude_extractor import resolve_provider; print(resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None))"` returns `ProviderResolution(provider='gemini', model='gemini-3.1-pro-preview', reasoning_label="the provider's default; this code sets no thinking for Gemini", transport='gemini-direct', transport_label='Google Gemini API (generativelanguage.googleapis.com)', credential='gemini-api-key', credential_source='GEMINI_API_KEY (shell or parent process, not .env)')`. |
| 5 | no Gemini key names both routes | pass | `GEMINI_API_KEY= .venv/bin/python -c "import config; from ingestion.claude_extractor import resolve_provider; resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)"` raises `ValueError: GEMINI_API_KEY is not set, so extraction cannot start. Either remedy is sufficient:\n  (1) Set GEMINI_API_KEY in .env or the system environment to use the Gemini API (route A); or\n  (2) Extract in a Claude Code session with the 'extract-filing' skill and run with --session-file (route B).` |
| 6 | the CLI refuses `-p claude` | pass | `.venv/bin/python cli.py -p claude 10K_filings/Walmart` exits 2 with `cli.py: error: argument -p/--provider: invalid choice: 'claude' (choose from 'gemini')`. `cli.py --help` shows `LLM provider (default: gemini). Claude reads a filing only through --session-file`. |
| 7 | route A runs end to end with Gemini, stubbed | pass | Scratch test executed with `socket.socket.connect` monkeypatched to raise `RuntimeError("Network socket attempted!")`: `_call_gemini` stubbed with Walmart Pass 1 & Pass 2 JSON from `extractions/WMT.json`; `extract_financials` on Walmart FY2026 PDF with `provider="gemini"` matched route B statements and non-recurring items byte-for-byte; all page checks passed (89 printed lines found, 4 Pass 2 items found); 2 stub calls, 0 network socket attempts. |
| 8 | route B does not move | pass | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json` yields $28.02 implied share price; `Provider: CLAUDE \| Model: claude-opus-5-5 \| Reasoning: as the Claude Code session ran; not set by this code \| Transport: Claude Code session — figures read from the PDF in a Claude Code session... \| Credential: none — no API call was made`. |
| 9 | the web app | pass | `TestClient(app.app).get('/')` returns 200. `TestClient(app.app).get('/assumptions', params={'session_file': 'extractions/WMT.json'})` returns 200 and renders `CLAUDE` and `Claude Code session`. |
| 10 | the gates do not get worse | pass | Ruff: 4 errors (all `BLE001`, unchanged). Mypy: 8 errors in 3 files (improved from 9 errors in 4 files; `claude_extractor.py` is now clean). Census: 65 (unchanged). Guard: 48/48 (unchanged). |
| 11 | every red test is named | pass | 15 failures and 5 errors across the test suite, each strictly matching expected causes (see breakdown below) + 2 deliberately red tests. |
| 12 | not measured here | not run | A real Gemini call on Walmart: not run. It is a paid call on the user's key; the overall lead asks the user. |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Stop immediately in `resolve_provider("claude", ...)` | User's decisions of 2026-10-04 ("1a, 2a"); Rule 3 | Directing the user to route B (`extract-filing` / `--session-file`) and naming `GEMINI_API_KEY` for route A is informative and deterministic rather than falling back or failing at API time. |
| Stop in `_resolve_gemini` with both remedies | Assignment step 2; Rule 3 | Telling the user to either set `GEMINI_API_KEY` or use `--session-file` names both actionable remedies without circular references. |
| Delete `EXTRACTION_EFFORT` and `ENTRA_TOKEN_SCOPE` | Assignment step 4 & 5 | Neither setting is read by any code once Claude API / Foundry is removed. Leaving dead config values would mislead readers (Rule 6). |
| Delete unused imports (`base64`, `urlsplit`, `Callable`, `TYPE_CHECKING`) | Python hygiene; Ruff F401 / I001 | These imports were solely used by `_call_claude`, `_foundry_endpoint_label`, `_ENTRA_TOKEN_PROVIDER`, and `anthropic` stubs. |
| Group red tests by cause | Assignment done-criterion 11 | Tests modifying or stubbing deleted internals belong to the tester phase (`P15a-two-routes-tests`). |

## List of deletions

1. `_call_claude` (in `ingestion/claude_extractor.py`)
2. `_build_claude_client` (in `ingestion/claude_extractor.py`)
3. `_resolve_claude` (in `ingestion/claude_extractor.py`)
4. `_NO_CLAUDE_CREDENTIAL` (in `ingestion/claude_extractor.py`)
5. `_ENTRA_TOKEN_PROVIDER` (in `ingestion/claude_extractor.py`)
6. `_entra_token_provider` (in `ingestion/claude_extractor.py`)
7. `_foundry_endpoint_label` (in `ingestion/claude_extractor.py`)
8. `"foundry"` and `"anthropic-direct"` from `Transport` (in `ingestion/claude_extractor.py`)
9. `"foundry-api-key"`, `"entra-token"`, and `"anthropic-api-key"` from `CredentialKind` (in `ingestion/claude_extractor.py`)
10. `_CLAUDE_MAX_TOKENS` (in `ingestion/claude_extractor.py`)
11. `config.EXTRACTION_EFFORT` (in `config.py`)
12. `config.ENTRA_TOKEN_SCOPE` (in `config.py`)
13. `"claude"` entry of `_DEFAULT_MODELS` (in `ingestion/claude_extractor.py`)
14. `anthropic` and `azure` imports (in `ingestion/claude_extractor.py`)
15. `anthropic` and `azure-identity` from `requirements.txt`

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

## Measurements

### Gates comparison

| Gate | Before (`158f25d`) | After (`P15a-two-routes`) |
|---|---|---|
| Ruff | 4 errors (`BLE001`) | 4 errors (`BLE001`) |
| Mypy | 9 errors in 4 files | 8 errors in 3 files (`claude_extractor.py` clean) |
| Rule 3 census | 65 | 65 |
| Write guard | 48/48 | 48/48 |
| Route `GET /` | 200 | 200 |

### Breakdown of red tests in full suite (Criterion 11)

Ran `.venv/bin/python -m pytest -q --continue-on-collection-errors`: 15 failed, 5 errors, 984 passed.

1. **Tests stubbing `_call_claude` (4 errors in `tests/unit/test_claude_extractor.py`):**
   - `test_pass2_unreadable_twice_stops_naming_the_filing_and_both_errors`
   - `test_pass2_unreadable_then_readable_returns_the_items`
   - `test_pass2_readable_empty_list_is_no_items_on_the_first_call`
   - `test_the_network_guard_fires`
   *Cause:* Fixture `no_network` attempts `monkeypatch.setattr(ce, "_call_claude", _block)`.

2. **Tests importing deleted `_CLAUDE_MAX_TOKENS` / `EXTRACTION_EFFORT` (1 collection error in `tests/unit/test_p14b_reasoning.py`):**
   - `test_p14b_reasoning.py` collection error: `ImportError: cannot import name '_CLAUDE_MAX_TOKENS' from 'ingestion.claude_extractor'`.

3. **Tests asserting old `CREDENTIAL_NAMES` (`ANTHROPIC_API_KEY`, `ANTHROPIC_FOUNDRY_API_KEY`) (9 failures in `tests/unit/test_config_env.py`):**
   - `test_a_value_set_before_config_loads_wins_over_the_file`
   - `test_an_absent_name_is_filled_from_the_file`
   - `test_a_child_labels_a_value_inherited_from_the_files_fill_as_the_file[inherit-subprocess]`
   - `test_a_child_labels_a_value_inherited_from_the_files_fill_as_the_file[inherit-spawn]`
   - `test_a_child_labels_a_value_its_parent_chose_as_not_the_file[parent-chosen-subprocess]`
   - `test_a_child_labels_a_value_its_parent_chose_as_not_the_file[parent-chosen-spawn]`
   - `test_a_value_equal_to_the_files_reads_env_file`
   - `test_a_name_the_file_does_not_hold_reads_not_env`
   - `test_a_name_with_no_value_in_the_file_is_neither_filled_nor_labelled`
   *Cause:* `CREDENTIAL_NAMES` is now `("GEMINI_API_KEY",)`, so calling `credential_origin("ANTHROPIC_API_KEY")` raises `ValueError`.

4. **Tests asserting route A with Claude / Anthropic credentials (4 failures in route tests):**
   - `tests/unit/test_routes.py::test_post_valuation_names_who_read_the_filing`
   - `tests/unit/test_routes.py::test_post_valuation_distinguishes_the_two_transports`
   - `tests/unit/test_routes_session.py::test_route_a_label_survives_removing_the_key_on_a_cache_hit`
   - `tests/unit/test_routes_session.py::test_route_a_on_a_cache_miss_with_no_key_stops_on_the_credential`
   *Cause:* Route A no longer resolves `claude`, and its no-key error message names `GEMINI_API_KEY` instead of `No Anthropic credential resolved`.

5. **Known deliberately red tests (2 failures):**
   - `tests/unit/test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`
   - `tests/unit/test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`

Total red: 20 (18 from deleted Claude route A code / updated credentials + 2 pre-existing deliberately red).
Every red test is expected and owned by the upcoming test unit `P15a-two-routes-tests`.

## What I did not do

- Did not touch `tests/`: out of scope; owned by the tester in `P15a-two-routes-tests`.
- Did not touch `.env`: user file; out of scope.
- Did not touch `api/` or `ingestion/session_extraction.py`: out of scope.
- Did not add DeepSeek: user's decision 2a.
- Did not make any real API call to Gemini (criterion 12).

## Findings for the orchestrator

- Mypy errors dropped from 9 to 8 because removing `_call_claude` eliminated the `TypedDict` item content type error in `ingestion/claude_extractor.py`.
- In `tests/unit/test_claude_extractor.py`, the `no_network` fixture stubs `_call_claude`, which caused errors during test setup. The tester in `P15a-two-routes-tests` should stub `_call_gemini` or remove `_call_claude` patching.
- In `tests/unit/test_config_env.py`, 9 tests were asserting `ANTHROPIC_API_KEY` and `ANTHROPIC_FOUNDRY_API_KEY` in `CREDENTIAL_NAMES`; the tester in `P15a-two-routes-tests` should update them to `GEMINI_API_KEY`.
- In `tests/unit/test_p14b_reasoning.py`, tests import `_CLAUDE_MAX_TOKENS` and test Claude adaptive streaming parameters which were removed in this unit; the tester will adapt or replace these tests for Gemini.
