---
id: P15a-two-routes
phase: 15 — two extraction routes (the user's decisions of 2026-10-04)
agent: programmer
depends_on: [P14b-reasoning]
---

# Two routes only: route A reads the filing through the Gemini API; Claude reads it only in a Claude Code session (route B)

## Objective

**The user's decisions of 2026-10-04:** "remove the foundry gateway, we only keep two
gateway, 1 is the api, another is the chat box from the claude code"; "I dont' have
anthropic api KEY, i only have gemini and deepseek"; then "1a, 2a": remove the Anthropic
API route with Foundry, and do not add DeepSeek now.

Route A has two providers today. Claude is the default (`config.DEFAULT_EXTRACTION_PROVIDER
= "claude"`) and reaches the model through a Microsoft Foundry gateway or the public
Anthropic API. Gemini is chosen with `-p gemini` and reads the PDF as a file. The user
holds no Anthropic key: the `.env` value of `ANTHROPIC_API_KEY` has 27 characters and
does not start with `sk-ant-`. So the default route A run on this machine cannot work,
and its label says that a key from `.env` was found.

When this unit is done:

- route A uses the Gemini API, and Gemini is the default provider;
- Claude is reached only through a Claude Code session file (route B, unchanged);
- `-p claude`, or any call of `resolve_provider("claude", ...)`, stops and names route B;
- the code holds no Foundry, Entra or Anthropic API path, and `anthropic` and
  `azure-identity` leave `requirements.txt`.

## What is already true — verify, do not redo

Measured by the overall lead at `158f25d` (`P14b-reasoning`, accepted): gate 1021 passed,
full 2 failed (the known two), ruff 4, mypy 9 in 4 files, census 65, guard 48/48.
`P14b-reasoning` added `reasoning_label`, `config.EXTRACTION_EFFORT`,
`_CLAUDE_MAX_TOKENS` and a streamed `_call_claude`.

| Fact | Command | Result |
|---|---|---|
| Claude route A code | `grep -n "def _call_claude\|def _build_claude_client\|def _resolve_claude\|def _entra_token_provider\|def _foundry_endpoint_label\|_NO_CLAUDE_CREDENTIAL =" ingestion/claude_extractor.py` | each present once |
| the dispatcher | `ingestion/claude_extractor.py`, `_call_llm` | `provider == "claude"` → `_call_claude`, otherwise `_call_gemini` |
| the CLI | `cli.py`, the `-p/--provider` option | `choices=["claude", "gemini"]` |
| the Gemini stop | `_resolve_gemini` | with no key, it says "or use provider='<the default>'". Once the default is Gemini, that remedy points back to Gemini |
| `anthropic` imports | `grep -rln "import anthropic" --include=*.py ingestion analysis api models cli.py app.py config.py` | `ingestion/claude_extractor.py` only |
| route B | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json` | $28.02; provider CLAUDE, transport "Claude Code session" |

## What to do

1. **`resolve_provider`.** Keep `Provider = Literal["claude", "gemini"]`: route B's
   resolution still names Claude. For `provider == "claude"`, raise `ValueError`: Claude
   reads a filing only in a Claude Code session (route B), on the user's decision of
   2026-10-04; run the `extract-filing` skill and pass `--session-file` (CLI) or upload
   the session file (web); route A uses Gemini, with `GEMINI_API_KEY`. **Reason:** the
   user's decision; rule 3 (stop and name the remedy).
2. **`_resolve_gemini`.** Its no-key stop names two remedies: set `GEMINI_API_KEY`; or
   extract in a Claude Code session and run with `--session-file`. It no longer points
   to the default provider.
3. **`_call_llm`.** Call `_call_gemini` when `resolution.provider == "gemini"`.
   Otherwise raise `ValueError` naming the provider and the transport. No other branch.
4. **Delete** `_call_claude`, `_build_claude_client`, `_resolve_claude`,
   `_NO_CLAUDE_CREDENTIAL`, `_ENTRA_TOKEN_PROVIDER`, `_entra_token_provider`,
   `_foundry_endpoint_label`, `"foundry"` and `"anthropic-direct"` from `Transport`, and
   `"foundry-api-key"`, `"entra-token"` and `"anthropic-api-key"` from `CredentialKind`.
   Then delete every name that no code reads any more: `_CLAUDE_MAX_TOKENS`,
   `config.EXTRACTION_EFFORT`, the `"claude"` entry of `_DEFAULT_MODELS`, and the
   `anthropic` import, if a grep shows no reader. List each deletion in your entry.
5. **`config.py`.** `DEFAULT_EXTRACTION_PROVIDER: Final = "gemini"`, with its comment
   rewritten: the user's decision of 2026-10-04, and that Gemini's reachability from
   this machine is not yet measured (the overall lead asks the user for one paid run).
   `CREDENTIAL_NAMES = ("GEMINI_API_KEY",)`. Delete `ENTRA_TOKEN_SCOPE`.
6. **`cli.py`.** `-p/--provider` takes `choices=["gemini"]`, and its help says that
   Claude reads a filing only through `--session-file`. Change nothing else in `cli.py`.
7. **`requirements.txt`.** Delete `azure-identity`. Delete `anthropic` if step 4 removed
   its last import from shipped code. Do not uninstall anything from `.venv`.
8. **The module docstring and comments** of `ingestion/claude_extractor.py`: the
   "PROVIDER, TRANSPORT AND CREDENTIAL" and "ENVIRONMENT VARIABLES" sections describe the
   two routes, one provider per route, and `GEMINI_API_KEY` only.
9. **Docs.** `docs/8-build/environment.md`: the credential and transport section names
   the two routes and `GEMINI_API_KEY`; the Foundry and Anthropic API setup is removed,
   with one sentence that records the removal, its date and the user's words.
   `docs/3-architecture/extraction.md`: the providers and transports; remove the
   `_call_claude` parameters that `P14b-reasoning` documented. `docs/3-architecture/data-contract.md`:
   the transport and credential values. `docs/2-rules/llm-boundary.md`: route A's model
   is Gemini, and option 0 on route A is the provider's default (the reasoning label says
   so). `README.md`: the two lines that name an Anthropic API key (about lines 19 and
   133) name the two routes instead.

## Files in scope

- `ingestion/claude_extractor.py`
- `config.py`
- `cli.py`: the `-p/--provider` option only
- `requirements.txt`
- `README.md`: the lines that name the Anthropic API or its key
- `docs/8-build/environment.md`
- `docs/3-architecture/extraction.md`
- `docs/3-architecture/data-contract.md`
- `docs/2-rules/llm-boundary.md`
- your journal entry, `.agent/journal/<timestamp>-programmer-p15a-two-routes.md`

**Nothing else.** The docs files and `README.md` are in scope by the overall lead's
decision.

## Out of scope

- `tests/`: the tester, in `P15a-two-routes-tests`. Many tests stub `_call_claude` or
  resolve `"claude"`; the tester moves them to Gemini or to the new stop.
- `api/`: it reads `config.DEFAULT_EXTRACTION_PROVIDER` and needs no change.
- `ingestion/session_extraction.py`: route B is unchanged.
- `.env`: the user's file. Never read a value from it, and never edit it.
- `.claude/skills/extract-filing/`: the overall lead updates its route table after
  acceptance.
- DeepSeek: not added (the user's decision 2a).

## Done-criteria

**Make no paid API call.** A fake key is a string such as `fake-key`; nothing may send it.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | no Foundry or Anthropic API path is left | 0 hits in shipped code, except in the route B stop's words, each explained | `grep -rniE "foundry\|entra\|azure\|anthropic" ingestion config.py requirements.txt cli.py api templates` |
| 2 | the app imports without `anthropic` and `azure` | the imports succeed | `.venv/bin/python -c "import sys; sys.modules['anthropic'] = None; sys.modules['azure'] = None; import app, cli, ingestion.claude_extractor"` |
| 3 | Claude on route A stops and names route B | `ValueError` naming the `extract-filing` skill, `--session-file` and `GEMINI_API_KEY` | a scratch call of `resolve_provider("claude", None)` |
| 4 | Gemini is the default and resolves | provider `gemini`, transport `gemini-direct`, model `gemini-3.1-pro-preview`, credential `gemini-api-key` | `GEMINI_API_KEY=fake-key`, a scratch call of `resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)` |
| 5 | no Gemini key names both routes | `ValueError` naming `GEMINI_API_KEY` and `--session-file`, and not "use provider='gemini'" | `GEMINI_API_KEY=`, the same call |
| 6 | the CLI refuses `-p claude` | argparse error naming the invalid choice; `--help` shows `default: gemini` | `cli.py -p claude 10K_filings/Walmart`; `cli.py --help` |
| 7 | route A runs end to end with Gemini, stubbed | `_call_gemini` replaced by a stub that returns Walmart's Pass 1 and Pass 2 JSON from `extractions/WMT.json`; `extract_financials` on the real Walmart PDF with `provider="gemini"` gives statements equal to route B's, every page check passes, 0 network attempts | a scratch script, sockets blocked |
| 8 | route B does not move | $28.02; provider CLAUDE, transport "Claude Code session" | `cli.py --session-file extractions/WMT.json` |
| 9 | the web app | `GET /` 200; `/assumptions` with the Walmart session file shows provider CLAUDE and transport "Claude Code session" | `TestClient` |
| 10 | the gates do not get worse | ruff, mypy and census no higher than at the `P14b-reasoning` commit | the gate commands |
| 11 | every red test is named | expected causes only: tests that stub `_call_claude` or `_build_claude_client`, resolve `"claude"` on route A, read `ENTRA_TOKEN_SCOPE`, `EXTRACTION_EFFORT` or the old `CREDENTIAL_NAMES`, or assert the old stop texts; and the 2 red on purpose | the full suite, failures grouped by cause |
| 12 | not measured here | a real Gemini call on Walmart | **not run.** It is a paid call on the user's key. Write that it is not measured; the overall lead asks the user |

## Citations

- The user's words, quoted in the Objective.
- `STATUS.md`, section 3: the `.env` key check (length and prefix only).
- `docs/8-build/environment.md`, section 3: the current credential and transport setup.

## Known open items

- No test checks the `Reasoning` row on the two web pages (the overall lead's review of
  `P14b-reasoning`, F1). The tester of this unit adds one, with the Gemini label and the
  route B label.

- `gemini-3.1-pro-preview` is the default Gemini model ID in `_DEFAULT_MODELS`. Nobody has
  called it from this machine. Criterion 12 is the first real call.
- `_call_gemini` sends `temperature=0.0` and asks for a JSON reply. Do not change it here.
- The Windows machine reached Claude only through Foundry. After this unit, route A
  there needs `GEMINI_API_KEY`.

## Backlog items this unit is NOT fixing

Items 1, 10, 51, 53, 61, 63, 64, 73, 74, 78, 79, 80 in `claude_extractor.py`; item 72
in `cli.py`.

## Overall lead review

**Verdict: `rework`**, 2026-10-04, by the overall lead, on the working tree at `3d32878`
plus the build team's uncommitted changes.

**The code meets every criterion.** Re-run with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:
criterion 1, 0 hits; 2, the imports succeed with `anthropic` and `azure` blocked; 3, the
`claude` stop names `extract-filing`, `--session-file` and `GEMINI_API_KEY`; 4, gemini /
gemini-direct / gemini-3.1-pro-preview / gemini-api-key; 5, the no-key stop names both
routes and not "use provider='gemini'"; 6, `-p claude` is an invalid choice and `--help`
shows `default: gemini`; 7, the stubbed Gemini run on the real Walmart PDF gives
statements and items equal to route B's, 0 network attempts; 8, $28.02 and the route B
label; 9, `/assumptions` with the session file shows CLAUDE, the route B reasoning label
and transport. Ruff 4, mypy 8 in 3 files (down from 9), census 65, guard 48/48.

**Findings. Answer each by number.**

- **F1, major (tester).** The test gate fails in the form `AGENTS.md` requires.
  `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q
  --ignore-glob="*_rule3_red.py"` → **21 failed, 1011 passed**. Without the empty keys,
  `.env` fills `GEMINI_API_KEY` with the user's real key, and the same command gives 1032
  passed. So 21 tests pass only on a machine whose `.env` holds a real Gemini key. The
  causes: `tests/unit/test_statements_ui.py:280`, `tests/unit/test_route_context_keys.py:222`
  and `tests/unit/test_pass1_printed_lines.py:854` set a placeholder `ANTHROPIC_API_KEY`,
  which no code reads now, and no `GEMINI_API_KEY`; the route A pages then resolve the
  default provider with no key. The tester's entry and the reviewer's line both report
  1032 passed: measured without the empty keys.
  **Fix:** set a placeholder `GEMINI_API_KEY` in those three tests, and remove the
  `ANTHROPIC_API_KEY` placeholders. Then add one autouse fixture in
  `tests/conftest.py` that sets `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` to `""` for
  every test, so no test can read a key from `.env`. A test that needs a key sets a
  placeholder itself. **Done when** the gate gives the same result with and without the
  empty-key prefix, and no test fails.
- **F2, minor (programmer).** `README.md` lost the line `- Python 3.10+` under
  Prerequisites. It names neither the Anthropic API nor a key, so it is outside the scope.
  Restore it.
- **F3, process (build lead).** Step 8 did not run: no gates, no commit, no `## Handoff`,
  and the queue still said `building`. After F1 and F2, run step 8 in full. Run every
  gate with the empty-key prefix.

The reviewer re-checks F1 and F2 only. The other criteria stand as measured above.

## Handoff

### Commits
- `2b0b265`: `P15a-two-routes: Gemini API on route A, Claude Code session on route B`
- `75b31aa`: `P15a tester: repair fixtures for Gemini route A and GEMINI_API_KEY, lock two-routes behaviors`
- `e42b312`: `P15a-two-routes rework: isolate test environment keys in conftest.py, restore Python prerequisite`

### Verdicts
- Programmer: `complete` (round 1 & round 2), entries: `.agent/journal/2026-10-04T1626-programmer-p15a-two-routes.md`, `.agent/journal/2026-10-04T1945-programmer-p15a-two-routes-r2.md`
- Code reviewer: `approved` (round 1 & round 2), entries: `.agent/journal/2026-10-04T1644-code_reviewer-p15a-two-routes.md`, `.agent/journal/2026-10-04T1951-code_reviewer-p15a-two-routes-r2.md`
- Tester: `pass` (round 1 & round 2), entries: `.agent/journal/2026-10-04T1645-tester-p15a-two-routes.md`, `.agent/journal/2026-10-04T1956-tester-p15a-two-routes-r2.md`

### Gates
- Test gate (with empty keys): 1032 passed (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`)
- Test gate (without empty keys): 1032 passed (`.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`)
- Full suite: 2 failed (the known two), 1032 passed (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q`)
- Lint: 4 errors, all `BLE001` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m ruff check .`)
- Types: 8 errors in 3 files (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports`)
- Rule 3 census: 65 (`grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" '--include=*.py' models analysis api ingestion | wc -l`)
- Web root route: HTTP 200 (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -c "from starlette.testclient import TestClient; from app import app; print(TestClient(app).get('/').status_code)"`)
- Guard check: 48/48 correct (`.venv/bin/python .claude/check_guard.py`)
- Walmart Route B check: exit 0; 89 of 89 printed lines found; 4 of 4 Pass 2 items confirmed; `Reasoning: as the Claude Code session ran; not set by this code` printed (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m ingestion.session_extraction check extractions/WMT.json`)
- Walmart end-to-end: stages 1 to 10 match `21125ed`; PV of terminal value 214,819M; implied price $28.02; downside -73.1% (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json`)

### Findings and notes
- F1 (tester): resolved. Autouse fixture `isolate_environment_keys` in `tests/conftest.py` sets `ANTHROPIC_API_KEY=""` and `GEMINI_API_KEY=""` for all tests. Gate passes identically (1032 passed) with and without empty-key prefix.
- F2 (programmer): resolved. Restored `- Python 3.10+` under Prerequisites in `README.md`.
- F3 (process): resolved. Step 8 executed in full with empty keys.
- Criterion 12 (real Gemini API call on Walmart): not run because it is a paid API call; left for overall lead / user verification.

### Questions for the overall lead
None.

