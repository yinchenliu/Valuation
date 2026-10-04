---
agent: programmer
assignment: P13c-env-override
round: 3
status: complete
files_touched: [config.py, docs/8-build/environment.md]
verdict:
---

# P13c-env-override, round 3 — the label compares the value in use with the file's value

Answers `.agent/journal/2026-10-03T2041-code_reviewer-p13c-env-override-r2.md`, under
the "Round 3 amendment" in step 2 of `.agent/assignments/P13c-env-override.md`. The
round 1 entry (`2026-10-03T2022-…`) and the round 2 entry (`2026-10-03T2031-…-r2`) are
unedited.

No API call was made. No key value was printed. To probe the case where the shell value
equals the file's value, a Python parent read the file's value into a variable and
handed it to a child's environment. Only the label was printed. The extractor diff is
still the three label lines from round 1 (1894, 1931, 1951): `git diff 0021845 --stat`
gives `3 insertions, 3 deletions`. This round changed only `config.py` and
`docs/8-build/environment.md`.

## What I did

`config.py` no longer calls `load_dotenv`. `_load_dotenv_without_override()` reads
`.env` once with `dotenv_values`. It writes each name with a non-`None` value into
`os.environ` only when the name is absent. A name that is set, even to `""`, is left
alone. It keeps the file's values for the three `CREDENTIAL_NAMES` in
`_DOTENV_CREDENTIAL_VALUES`, and keeps nothing else from the file.

`credential_origin(name)` compares `os.environ[name]` at call time with the file's
value. It returns `(.env file)` when they are equal. It returns
`(shell or parent process, not .env)` when they differ or when `.env` does not hold the
name. It still stops on an unknown name, and on a name that is unset or blank.

These are gone: `VALUATION_DOTENV_CREDENTIALS`, `_inherited_dotenv_names`,
`CREDENTIALS_FROM_SHELL` and `CREDENTIALS_FROM_DOTENV`, the SHA-256 digest
(`_START_UP_FINGERPRINTS`, `_fingerprint`) and `import hashlib`.

`docs/8-build/environment.md` section 3 now states:
- the order, with "filled by `config.py`" where it used to say `load_dotenv`;
- the label as a value comparison made when the label is built;
- that a shell value equal to the file's value reads `(.env file)`, and why that is
  harmless;
- that the label says nothing about a value's history;
- that `config.py` writes nothing to the environment except the names it fills.

## Answers by finding

### F4 (major): a child trusted the inherited marker — **fixed, by the amended contract**

The marker is gone, so nothing is inherited that can be trusted or forged. Each process
compares its own value with the file. The reviewer's two probes now give the second
label:

| Probe (reviewer's form) | Round 2 | Round 3 |
|---|---|---|
| `env -u ANTHROPIC_API_KEY`, the parent imports `config`, then `subprocess.run(…, env={**os.environ, 'ANTHROPIC_API_KEY': 'parent-chosen-probe'})` | `(.env file)` | `ANTHROPIC_API_KEY (shell or parent process, not .env)` |
| the same, as a `multiprocessing` spawn child after the parent sets `parent-chosen-probe` | — | `child:  ANTHROPIC_API_KEY (shell or parent process, not .env)` |
| `VALUATION_DOTENV_CREDENTIALS=ANTHROPIC_API_KEY ANTHROPIC_API_KEY=shell-probe` | `(.env file)` | `ANTHROPIC_API_KEY (shell or parent process, not .env)`. The variable is no longer read |

The doc's false `(.env file)` row ("has not been replaced since") and the marker
paragraph are both removed.

### F3 (note): three stale comments in `tests/` — **the tester's; not edited**

The comments are in `tests/unit/_session_route_helpers.py:21` and `:242`, and in
`tests/unit/test_session_extraction.py:30`. They describe `override=True`. They should
say that a value already in the environment wins, and that `config.py` fills only the
absent names. No assertion depends on them.

### Earlier findings under the new contract

| # | Status now | Note |
|---|---|---|
| F1 | still fixed | a spawned child under `env -u` gives `(.env file)` in both parent and child, because the inherited value equals the file's value |
| F2 | fixed differently | an in-process replacement gives `(shell or parent process, not .env)` by comparison. No digest is needed |

## Done-criteria, re-run

**Tree used:** every probe and suite run below used my own exports under
`scratchpad/p13c_programmer/`:
- `unit`: `git archive 0021845` with this unit's three files copied in (`cmp`
  confirmed identical to the working tree) and `.env` symlinked;
- `head`: a plain `git archive 0021845`, with no `.env`.

The probes ran with `cwd` and `PYTHONPATH` set to `p13c_programmer/unit`. The shell had
no `ANTHROPIC*`, `GEMINI*`, `DEEPSEEK*` or `VALUATION*` name set.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | an empty shell value turns the key off | **pass** | `ANTHROPIC_API_KEY= … print(bool(os.environ.get('ANTHROPIC_API_KEY')))` → `False`. Spawned child: `child key present: False`. Label form: `ValueError: No Anthropic credential resolved…` |
| 2 | a shell value wins | **pass** | `ANTHROPIC_API_KEY=shell-probe … == 'shell-probe'` → `True` |
| 3 | `.env` supplies the key when the shell does not | **pass** | `env -u ANTHROPIC_API_KEY …` → `True` |
| 4 | the label says the key is not the file's when the shell set it | **pass, parent and child** | one process: `ANTHROPIC_API_KEY (shell or parent process, not .env)`. Spawn: `parent: … (shell or parent process, not .env)` / `child: … (shell or parent process, not .env)`. Gemini and Foundry give the same, each with its own name |
| 5 | the label names `.env` | **pass, parent and child** | one process: `ANTHROPIC_API_KEY (.env file)`. Spawn under `env -u ANTHROPIC_API_KEY`: `parent: ANTHROPIC_API_KEY (.env file)` / `child:  ANTHROPIC_API_KEY (.env file)`. Gemini spawn under `env -u GEMINI_API_KEY`: `.env file` in both |
| 6 | no key value is printed | **pass** | every output is a boolean, a label, a name, or an error message that names a field. Error messages never include a value: `credential_origin`'s two `raise`s interpolate only `name` and `CREDENTIAL_NAMES` |
| 7 | the suite fails only where expected | **pass, 0 red from this unit** | Gate form: `head` 724 passed, `unit` 724 passed. Full `tests/unit`: `2 failed, 724 passed` in both, with identical FAILED lines (`test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`, both known-red at HEAD). `unit` with `.env` unlinked: `2 failed, 724 passed`. `unit` with all three keys empty: 724 passed |
| 8 | the gates do not get worse | **pass** | ruff `Found 5 errors.` in both, all 5 `BLE001`, and the sorted sets (line numbers stripped) are identical. mypy `Found 10 errors in 4 files` in both, with identical sets. `ruff check config.py`: all checks passed. `mypy config.py`: no issues |

Probes the orchestrator required:

| Probe | Expected | Output |
|---|---|---|
| reviewer's F4 probe 1 (parent-chosen value in a child) | second label | `ANTHROPIC_API_KEY (shell or parent process, not .env)` from the subprocess form, and the same from the spawn form |
| reviewer's F4 probe 2 (`VALUATION_DOTENV_CREDENTIALS=ANTHROPIC_API_KEY ANTHROPIC_API_KEY=shell-probe`) | second label | `ANTHROPIC_API_KEY (shell or parent process, not .env)` |
| spawned child under `env -u ANTHROPIC_API_KEY` | `(.env file)` | `child:  ANTHROPIC_API_KEY (.env file)` |
| in-process replacement (`os.environ['ANTHROPIC_API_KEY']='runtime-probe'` after import) | second label | `ANTHROPIC_API_KEY (shell or parent process, not .env)` |

Further probes:

| Probe | Output |
|---|---|
| a shell value equal to the file's value. The parent holds the file's value and passes it to a child; only the label is printed | `ANTHROPIC_API_KEY (.env file)`, which is what the doc says |
| `credential_origin('DEEPSEEK_API_KEY')` | `stops: credential_origin: 'DEEPSEEK_API_KEY' is not one of (…).` |
| `credential_origin` on a blank Foundry key | `stops: … is not set to a non-blank value, so it has no origin to label.` |
| `VALUATION*` names in `os.environ` after `import config` | `[]` |
| no `.env` file: `env -u ANTHROPIC_API_KEY` | key present `False`, file credentials `{}`. A shell key gives `(shell or parent process, not .env)` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `dotenv_values` plus a fill loop, in place of `load_dotenv` | Round 3 amendment, bullet 1. One read gives both the fill and the comparison values | `load_dotenv` followed by `dotenv_values` would read the file twice |
| Fill only when `name not in os.environ` and the value is not `None` | the membership test and the `None` skip of `dotenv.main.DotEnv.set_as_environment_variables` (read in round 1). It keeps the empty-value off switch | — |
| Keep only the three credential values from the file | the comparison needs nothing else, so the rest of the file's values (e.g. `DEEPSEEK_API_KEY`, if present) are not kept in the module | Keeping the whole mapping would hold secrets no code uses |
| Plain `==` for the comparison | local, same process. There is no timing channel to an attacker | `hmac.compare_digest` adds nothing here |
| Interpolation left at the `dotenv_values` default | `.env` has no `${` (`grep -c '\${' .env` → `0`). The difference from `load_dotenv(override=False)` is in the docstring | — |

No change was made to reach a target number. The unit moves no figure.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| the `.env` file | reads as no names, as `load_dotenv` does. No figure comes from it. Every credential then has to come from the environment, or `resolve_provider` stops | "no `.env` file" probe |
| a `.env` line with no `=` (value `None`) | neither filled nor kept, as `load_dotenv` does | `config.py` `_load_dotenv_without_override` |
| `name` passed to `credential_origin` | stops and names it | probe above |
| the credential at label time | stops and names it when unset or blank | probe above |
| the file's value for `name` | absent means `.env` does not hold it, so the label is `(shell or parent process, not .env)`. That is the stated rule, and true | "no `.env` file" probe. Foundry spawn probe |

No "defaults to" row.

## Scratch trees — for the orchestrator's notice on the shared scratchpad

Before the notice arrived, I created and deleted generic directory names in the shared
scratchpad:
- **round 1:** I ran `rm -rf` on `scratchpad/iso` and `scratchpad/head`, both at
  creation and at cleanup;
- **rounds 2 and 3:** I ran `rm -rf` on `scratchpad/u` and `scratchpad/h` before
  re-creating them.

**The deleted `iso` tree the notice mentions may be the one I removed in round 1.** I
created `iso` and `head` myself, but I cannot rule out that another agent was using the
same names at that time.

After the notice I deleted nothing outside `scratchpad/p13c_programmer/`, and every
measurement in this entry came from that subdirectory. These items are mine, and I left
them in place rather than remove a path outside my subdirectory: `scratchpad/u`,
`scratchpad/h`, `scratchpad/{u,h}.{full,ruff,mypy}` and `scratchpad/spawn_probe.py`.
The round 1 files `full_before.txt`, `full_after.txt` and `gate_after.txt` are also mine.

## What I did not do

- `tests/` (F3).
- `app.py`. Not needed, and out of scope.
- I did not run uvicorn. The child probes use `multiprocessing` spawn, which is the
  reloader's mechanism, with no server.

## Findings for the orchestrator

1. A tester can pin the contract without depending on a key:
   - write a temporary `.env`, or patch `config._DOTENV_CREDENTIAL_VALUES`;
   - check that a value equal to the file's value gives `(.env file)`;
   - check that a different value gives `(shell or parent process, not .env)`;
   - check that an unknown name stops, and that a blank name stops.

   The fill behaviour (empty value not filled, absent name filled) needs a subprocess,
   or a `config` reload under a patched `os.environ`.
2. No test in the working tree references a round-2 name or label text. `grep -rln
   "shell environment\|CREDENTIALS_FROM\|VALUATION_DOTENV\|credential_origin\|(.env file)\|_START_UP" tests/`
   finds no match.
3. Backlog item 46 can close once this is accepted. `STATUS.md:380` should change with it.
