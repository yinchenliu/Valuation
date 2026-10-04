---
agent: code_reviewer
assignment: P13c-env-override
round: 1
verdict: changes_requested
---

# Review of P13c-env-override, round 1

Programmer entry: `.agent/journal/2026-10-03T2022-programmer-p13c-env-override.md`

Measured on two exports of HEAD `0021845` (`git archive`) under the session scratchpad:
`head` (untouched) and `unit` (HEAD plus only this unit's `config.py`,
`ingestion/claude_extractor.py`, `docs/8-build/environment.md`). `.env` and `.venv` were
symlinked, not copied. The shared working tree was not touched. No API call was made:
I read `resolve_provider` (`ingestion/claude_extractor.py:1955-1976`) and its callees
before calling it. They read `os.environ` only, and build no client. No key value was
printed. `.env` was read for names only (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`).

**Orchestrator decision, recorded.** The assignment named lines 1894, 1918 and 1931.
That was the orchestrator's error: 1918 is the Entra ID label, and the three literal
`(environment)` labels were 1894, 1931 and 1951. The orchestrator ruled that the change
at 1951 (Gemini) is in scope. I do not raise it. Leaving 1918 unchanged is correct: an
Entra token comes from neither the shell nor `.env`.

## The guard checks

Run over `config.py` and `docs/8-build/environment.md` whole, and over the three changed
lines of `ingestion/claude_extractor.py` (1894, 1931, 1951). The rest of that file is
out of this unit's scope.

| Check | Result |
|---|---|
| conditional zero: `if … else 0.0` | clean |
| lookup with a fallback: `.get(k, 0)` | clean (`config.py` uses `name in os.environ and os.environ[name].strip()`, with no `.get` default) |
| bare or-default: `or 0.0` | clean |
| money field defaulted to zero: `: float = 0.0` | clean |
| `**kwargs` | clean |
| `getattr(` | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (`grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` gives no match) |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `name` given to `credential_origin` | yes. A name outside `CREDENTIAL_NAMES` raises and names it | `config.py` `credential_origin`, first `raise` |
| the credential at label time | yes. Unset or blank raises and names it. The three call sites test `.strip()` first, so this branch cannot be reached today, but it stops and returns no label | `config.py` `credential_origin`, second `raise` |
| `os.environ[name]` at import, for the record | not a value. Absent means "not from the shell". No figure is derived from it | `config.py` `_NAMES_IN_SHELL`, `CREDENTIALS_FROM_SHELL`, `CREDENTIALS_FROM_DOTENV` |
| the third label ("set in this process after start-up") | a deduction, not a fallback. In a single process, a name in neither record that is set now was set after `config` loaded | read. But see F1: across a process boundary the records are wrong before this branch is reached |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | n/a. The unit touches no figure |
| percentages converted at the route boundary, once | n/a |
| falsy not treated as missing | correct here. An empty shell value is meant to mean "off", and `.strip()` matches `resolve_provider`'s own test |
| layering | `config.py` adds only `import os`. `ingestion/claude_extractor.py` already imported `config` (line 100) |

## Done-criteria, re-run

All in the `unit` export unless stated. My shell had no `ANTHROPIC*`, `GEMINI*` or
`DEEPSEEK*` name set.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | empty shell value turns the key off | `False` | `False`. In the `head` export the same command gives `True`, which is the defect | yes |
| 2 | shell value wins | `True` | `True` | yes |
| 3 | `.env` supplies with no shell value | `True` | `True` | yes |
| 4 | label names the shell | `ANTHROPIC_API_KEY (shell environment)` | same. The Foundry probe gives `… Credential: ANTHROPIC_FOUNDRY_API_KEY (shell environment)` | yes, in one process. **No when the process is a child: F1** |
| 5 | label names `.env` | `ANTHROPIC_API_KEY (.env file)` | same. Gemini gives `GEMINI_API_KEY (.env file)` | yes, in one process. **No when the process is a child: F1** |
| 6 | no key value printed | none | none. Only booleans, labels, names and the probe string `shell-probe` | yes |
| 7 | suite fails only where expected | same failure set as HEAD | `.env` unlinked in both exports. Full suite: `head` 2 failed, 724 passed; `unit` 2 failed, 724 passed. `diff` of the FAILED lines: **identical** (`test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`, both known-red). Gate form: 724 passed in both. `unit` with `.env` linked and all three keys set empty: the same 2 failed, 724 passed. No test is red because of this unit | yes |
| 8 | gates no worse | ruff 5, mypy 10 | ruff `Found 5 errors.` in both, all `BLE001`, with identical sets (line numbers aside). mypy `Found 10 errors in 4 files` in both, with identical sets | yes |

## Findings

### F1 — In a child process the label says "shell environment" for a key that came from `.env` · `major`

**Evidence:** `app.py:14` imports `config` at module top, and `app.py:32` then calls
`uvicorn.run("app:app", …, reload=True)`. Uvicorn's reloader starts the worker with
`multiprocessing.get_context("spawn")` (`uvicorn/_subprocess.py:18`). So the parent has
already run `load_dotenv`, and the child inherits a `.env` value as if the shell had set
it. I reproduced this with the same mechanism and no server or API call: a parent that
imports `config`, then a spawned child that imports `config` and calls
`resolve_provider`, run under `env -u ANTHROPIC_API_KEY`:
```
parent: ANTHROPIC_API_KEY (.env file)
child:  ANTHROPIC_API_KEY (shell environment)
```
Any child process that inherits `os.environ` after `config` has loaded hits the same
defect. The documented launch, `python -m uvicorn app:app --reload`, is not affected. I
established that by reading the code, not by running it: `uvicorn/main.py` `run()` hands
the import string to `ChangeReload` without calling `config.load()`, so that parent never
imports `config`.

The unit's own doc says the opposite. The new `docs/8-build/environment.md` section says
the `(shell environment)` label means "the shell set it before start-up", and that "No
production code writes a credential variable, so this affects only tests". `load_dotenv`
in a parent process is production code writing a credential variable, and a child
inherits it.

**Rule or document:** `docs/2-rules/rules.md` rule 6 (the false label), as the
assignment's Citations apply it: "a label that names the wrong source is a false label."
This is the defect backlog item 46 records, a label naming a source the key did not come
from. Here it appears on one of the two entry points this product ships
(`docs/9-reference/refactor-backlog.md:1165`). Reachability is not the test.

**What would fix it:** make the record survive a process boundary. Two ways: `config.py`
writes the names it filled from `.env` into a marker variable that a child's `config`
import reads before it classifies, or a re-import detects that `load_dotenv` has
already run. Then correct the doc sentence. Either way is inside `config.py` and
`environment.md`, which are both in scope. Changing `app.py` is not in scope. Add a
spawned-child probe to criteria 4 and 5.

### F2 — A credential replaced in-process keeps its start-up label · `note`

**Evidence:** `config.py` `credential_origin` docstring: "A value replaced later in the
process keeps the start-up label". A test that runs `monkeypatch.setenv("ANTHROPIC_API_KEY", …)`
on a machine whose `.env` holds the key sees `(.env file)`. The programmer recorded
this limitation in its entry (finding 2) and in the doc. No production path changes a
credential in-process (`grep -rnE 'os\.environ\[|putenv|environ\.setdefault|environ\.update|setenv'`
over `api ingestion analysis models cli.py app.py config.py`: no match). No test
asserts the origin text. This is for the tester to know. It breaks no rule in shipped
output.

### F3 — Three stale test comments describe `override=True` · `note`

**Evidence:** `tests/unit/_session_route_helpers.py:21` and `:242`, and
`tests/unit/test_session_extraction.py:30`, as the programmer lists them. `tests/` is the
tester's. No assertion depends on these comments.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 8, blanket `except Exception` (`BLE001`) | `ingestion/claude_extractor.py:1798` | no |
| 46, the defect this unit fixes | `config.py:15` (old) | yes. Closure waits on F1. `STATUS.md:380` and the backlog entry belong to the orchestrator |
| none. The guard grep for a fallback lookup hits `os.environ.get(NAME, "").strip()` | `ingestion/claude_extractor.py:1855,1864,1874,1875,1887,1924,1939` | no. These are pre-existing and unchanged, and outside the three in-scope lines. Each blank result leads to a `raise` or to the next credential branch, never to a number, so I do not raise them as a rule 3 site |

## Verdict

`changes_requested`

F1 stands as `major`. The unit's purpose is that the label names the real source, and in
a child process started by `python app.py` it names the shell for a key that came from
`.env`, while the unit's own doc says this cannot happen in production. Everything else
holds. Criteria 1 to 3 and 6 to 8 pass on my own measurement. The failure set and both
gate sets are identical to HEAD. The guard checks are clean. The scope is exactly the
three files, with 1951 accepted by the orchestrator's decision.
