---
id: P15a-drop-foundry
phase: 15 — two extraction routes (the user's decision of 2026-10-04)
agent: programmer
depends_on: [P14b-note-figures]
---

# Remove the Microsoft Foundry gateway: Claude is reached through the Anthropic API (route A) or a Claude Code session (route B), and nothing else

## Objective

**The user's decision of 2026-10-04:** "remove the foundry gateway, we only keep two
gateway, 1 is the api, another is the chat box from the claude code".

Route A reaches Claude over one of two transports today (`_resolve_claude`): a
Microsoft Foundry gateway when `ANTHROPIC_FOUNDRY_BASE_URL` or
`ANTHROPIC_FOUNDRY_RESOURCE` is set, with a Foundry key or an Entra ID token from
`azure-identity`; otherwise the public Anthropic API with `ANTHROPIC_API_KEY`. The
Foundry path holds two credential kinds, a token provider, an endpoint label, a config
constant, a dependency and a second remedy in the "no credential" stop. The macOS
machine sets no Foundry variable (`STATUS.md`, section 3), so it uses the public API
already.

When this unit is done, route A reaches Claude through the public Anthropic API only.
Route B, the Claude Code session file, does not change. A Foundry variable that is still
set stops the run and names itself, so a run never goes to another account than the
one its environment names. Gemini is not touched: the user's answer on Gemini is open.

## What is already true — verify, do not redo

Measured by the overall lead at `7d0aa26`. Re-take the gate numbers at the
`P14b-note-figures` commit.

| Fact | Command | Result |
|---|---|---|
| Foundry in the code | `grep -rniE "foundry\|entra\|azure" ingestion config.py requirements.txt api cli.py templates` | hits in `ingestion/claude_extractor.py` (docstring, `Transport`, `CredentialKind`, `_ENTRA_TOKEN_PROVIDER`, `_entra_token_provider`, `_build_claude_client`, `_NO_CLAUDE_CREDENTIAL`, `_foundry_endpoint_label`, `_resolve_claude`, the `_DEFAULT_MODELS` comment), `config.py` (`CREDENTIAL_NAMES`, `ENTRA_TOKEN_SCOPE`), `requirements.txt` (`azure-identity`) |
| `.env` names | `cut -d= -f1 .env` | `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`; no Foundry name |
| Walmart, route B | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json` | $28.02, transport "Claude Code session" |

## What to do

1. **`_resolve_claude`.** Delete the Foundry branches. Before the `ANTHROPIC_API_KEY`
   test, stop when any of `ANTHROPIC_FOUNDRY_BASE_URL`, `ANTHROPIC_FOUNDRY_RESOURCE` or
   `ANTHROPIC_FOUNDRY_API_KEY` is set and not empty. The message names each variable
   that is set, says that the Foundry gateway was removed on the user's decision of
   2026-10-04, and says to unset it. **Reason:** rule 3 and rule 6. A run must not reach
   a different account than the one its environment names, with no word said.
2. **Delete** `_ENTRA_TOKEN_PROVIDER`, `_entra_token_provider`, `_foundry_endpoint_label`,
   the two Foundry branches of `_build_claude_client`, `"foundry"` from `Transport`, and
   `"foundry-api-key"` and `"entra-token"` from `CredentialKind`.
3. **`_NO_CLAUDE_CREDENTIAL`.** Two remedies, the two routes: (1) set
   `ANTHROPIC_API_KEY`, for the Anthropic API; (2) extract the filing in a Claude Code
   session with the `extract-filing` skill and run with `--session-file`, which makes no
   API call.
4. **Comments and the module docstring** of `ingestion/claude_extractor.py`: the
   "PROVIDER, TRANSPORT AND CREDENTIAL" and "ENVIRONMENT VARIABLES" sections name the
   two routes and no Foundry variable; the `_DEFAULT_MODELS` comment no longer says the
   model is served by the Foundry gateway.
5. **`config.py`.** Delete `ENTRA_TOKEN_SCOPE`. Delete `"ANTHROPIC_FOUNDRY_API_KEY"` from
   `CREDENTIAL_NAMES`.
6. **`requirements.txt`.** Delete `azure-identity`. Do not uninstall it from `.venv`.
7. **Docs.** `docs/8-build/environment.md`: the credential and transport section names
   the two routes, the one key, and the new stop; the Foundry setup is removed, with one
   sentence that records the removal and its date. `docs/3-architecture/data-contract.md`:
   the transport and credential values. Change no other doc.

## Files in scope

- `ingestion/claude_extractor.py`
- `config.py`
- `requirements.txt`
- `docs/8-build/environment.md`
- `docs/3-architecture/data-contract.md`
- your journal entry, `.agent/journal/<timestamp>-programmer-p15a-drop-foundry.md`

**Nothing else.**

## Out of scope

- `tests/`: the tester removes the Foundry cases and locks the new stop, in
  `P15a-drop-foundry-tests`.
- Gemini (`_resolve_gemini`, `_call_gemini`, `GEMINI_API_KEY`): open question to the user.
- `.env`: the user's file. Never edit it.
- `STATUS.md`, the backlog and `docs/9-reference/`: the overall lead, after acceptance.

## Done-criteria

**Make no paid API call.** A fake key is a string such as `sk-fake`; nothing may send it.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | no Foundry path is left | 0 hits, except the new stop's message | `grep -rniE "foundry\|entra\|azure" ingestion config.py requirements.txt api cli.py templates` |
| 2 | the module imports without `azure` | the import succeeds | `.venv/bin/python -c "import sys; sys.modules['azure'] = None; import ingestion.claude_extractor"` |
| 3 | the API route resolves | transport `anthropic-direct`, label `Anthropic public API (api.anthropic.com)`, credential `anthropic-api-key` | `ANTHROPIC_API_KEY=sk-fake`, a scratch call of `resolve_provider("claude", None)` |
| 4 | a Foundry variable stops the run | three runs, one variable each (`ANTHROPIC_FOUNDRY_BASE_URL=https://x.example.com`, `ANTHROPIC_FOUNDRY_RESOURCE=x`, `ANTHROPIC_FOUNDRY_API_KEY=k`), each with `ANTHROPIC_API_KEY=sk-fake`: `ValueError` naming that variable and the removal | the same scratch call |
| 5 | no key names both routes | `ValueError` naming `ANTHROPIC_API_KEY`, the `extract-filing` skill and `--session-file`, and no Foundry word | the scratch call with every key empty |
| 6 | route B does not move | $28.02; transport "Claude Code session" | `cli.py --session-file extractions/WMT.json` |
| 7 | the gates do not get worse | ruff, mypy and census no higher than at the `P14b-note-figures` commit; `GET /` 200 | the gate commands |
| 8 | every red test is named | expected causes only: tests of the Foundry and Entra paths, tests that read `config.ENTRA_TOKEN_SCOPE` or the old `CREDENTIAL_NAMES`, the old `_NO_CLAUDE_CREDENTIAL` text, and the 2 red on purpose | the full suite, failures grouped by cause |

## Citations

- The user's decision, quoted in the Objective.
- `docs/8-build/environment.md`, section 3: how Foundry was set up, and why.
- `STATUS.md`, section 3: the macOS machine sets no Foundry variable.

## Known open items

- The Windows machine reached Claude only through Foundry. After this unit, route A
  there needs `ANTHROPIC_API_KEY`. Route B works on both machines.
- Gemini: the overall lead asked the user whether "the api" means the Anthropic API
  only. If the user removes Gemini, the overall lead amends this assignment before it
  is `ready`.

## Backlog items this unit is NOT fixing

Items 1, 10, 51, 53, 61, 63, 64, 73, 74, 78, 79, 80 in `claude_extractor.py`.
