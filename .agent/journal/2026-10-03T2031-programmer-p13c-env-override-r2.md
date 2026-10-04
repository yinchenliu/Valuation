---
agent: programmer
assignment: P13c-env-override
round: 2
status: complete
files_touched: [config.py, docs/8-build/environment.md]
verdict:
---

# P13c-env-override, round 2 — the origin record now survives a process boundary, and a replaced value is noticed

Answers `.agent/journal/2026-10-03T2030-code_reviewer-p13c-env-override.md`. Round 1 is
`.agent/journal/2026-10-03T2022-programmer-p13c-env-override.md`. I did not edit it.

No API call was made. No key value was printed. I measured in a `git archive 0021845`
export with this unit's three files copied in, `.env` symlinked and not copied. I made
no change to the shared tree outside the three files in scope. The extractor diff is
unchanged from round 1: the three label lines, 1894, 1931 and 1951.

## What I did

`config.py` now writes one environment variable of its own after `load_dotenv`:
`VALUATION_DOTENV_CREDENTIALS`. It holds the **names**, comma-separated, of the
credentials that `.env` filled. A child process inherits it. Before the child's
`config` classifies anything, it reads the variable and puts those names in
`CREDENTIALS_FROM_DOTENV`, not in `CREDENTIALS_FROM_SHELL`. The child then rewrites the
variable, so a grandchild gets the same record. `config.py` also keeps an in-memory
SHA-256 digest of each recorded value. When a value is replaced after start-up,
`credential_origin` sees that its digest changed and gives the third label.
`docs/8-build/environment.md` now says what each label means, says that `config.py`
writes the variable, and drops the false sentence.

## Answers by finding

### F1 (major): the child labels a `.env` key as "shell environment" — **fixed**

- **Reproduced first, on the round-1 code.** I ran a spawn probe in the export, under
  `env -u ANTHROPIC_API_KEY`: `parent: ANTHROPIC_API_KEY (.env file)` and
  `child:  ANTHROPIC_API_KEY (shell environment)`. That matches the reviewer's result.
- **The fix is a marker variable, as the reviewer suggested.** Why this way and not
  "detect that `load_dotenv` has already run":
  - Such detection is a single flag. It tells a child that an ancestor loaded `.env`,
    but not *which* names that load filled. A name the real shell set would still be in
    the child's environment.
  - So a single flag cannot keep the shell and `.env` apart. A list of names can, and
    it is the only extra fact needed.
  - It carries names and never values. The digests (F2) stay in memory and never enter
    the environment, so a child or `ps eww` sees no digest.
- **The marker is checked (rule 3).** `_inherited_dotenv_names` stops with a
  `ValueError` that names the variable when it lists a name outside `CREDENTIAL_NAMES`.
  An empty marker means "an ancestor loaded and filled nothing".
- **The doc sentence is corrected.**
  - `(shell environment)` now reads: "the value was in the environment when the process
    started and no `config` import filled it from `.env`, in this process or a parent.
    The shell set it, directly or through a parent process."
  - "No production code writes a credential variable" is removed. The doc now says
    `config.py` writes `VALUATION_DOTENV_CREDENTIALS` (names only) and nothing else
    apart from what `load_dotenv` fills.
  - Evidence:
    `grep -rnE 'os\.environ\[[^]]*\] *=|putenv|environ\.setdefault|environ\.update|setenv' api ingestion analysis models cli.py app.py config.py`
    matches only `config.py:105`, the marker write.
- **The child probe has been added to criteria 4 and 5.** See the table below. The probe
  script is the reviewer's mechanism, `multiprocessing.get_context("spawn")`, the same
  one uvicorn's reloader uses. The parent imports `config` and calls `resolve_provider`.
  The child does the same. There is no server and no client.

### F2 (note): a replaced value keeps its start-up label — **fixed in `config.py`**

The F1 work made this a small step. `_START_UP_FINGERPRINTS` maps each recorded name to
the SHA-256 of its value at start-up. `credential_origin` gives `(shell environment)` or
`(.env file)` only while the current value has the same digest. Any other value set now
gets `(set in this process after start-up; neither the shell nor .env)`.

| Probe | Output |
|---|---|
| `env -u ANTHROPIC_API_KEY`, then `os.environ['ANTHROPIC_API_KEY']='runtime-probe'` | `ANTHROPIC_API_KEY (set in this process after start-up; neither the shell nor .env)` |
| `ANTHROPIC_API_KEY=shell-probe`, then replaced in-process | the same third label |
| replaced, then restored to `shell-probe` | `ANTHROPIC_API_KEY (shell environment)`. The value is the shell's again, so the label is true |

**A limit remains.** A value replaced in a parent *after* its `config` loaded, and then
inherited by a child, gets its inherited label in the child. The digests are kept out of
the environment on purpose. No shipped output is affected:
- No shipped code writes a credential variable. The grep under F1 matches only the
  marker write.
- The one shipped child, uvicorn's worker, is spawned before any request runs.

### F3 (note): three stale comments in `tests/` — **acknowledged, not edited**

The comments are in `tests/unit/_session_route_helpers.py:21` and `:242`, and in
`tests/unit/test_session_extraction.py:30`. `tests/` belongs to the tester. No assertion
depends on these comments. They should now say `override=False`, and that the shell
wins.

## Done-criteria, re-run in the export

The shell had no `ANTHROPIC*`, `GEMINI*`, `DEEPSEEK*` or `VALUATION*` name set.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | an empty shell value turns the key off | **pass** | `ANTHROPIC_API_KEY= … print(bool(os.environ.get('ANTHROPIC_API_KEY')))` → `False`. In a spawned child under the same shell: `child key present: False`. In the label form, `resolve_provider` raises `No Anthropic credential resolved` |
| 2 | a shell value wins | **pass** | `ANTHROPIC_API_KEY=shell-probe …` → `True` |
| 3 | `.env` supplies the key when the shell does not | **pass** | `env -u ANTHROPIC_API_KEY …` → `True` |
| 4 | the label names the shell | **pass, parent and child** | one process: `ANTHROPIC_API_KEY (shell environment)`. Spawn probe: `parent: ANTHROPIC_API_KEY (shell environment)` / `child:  ANTHROPIC_API_KEY (shell environment)`. Gemini and Foundry spawn probes give the same, each with its own name |
| 5 | the label names `.env` | **pass, parent and child** | one process: `ANTHROPIC_API_KEY (.env file)`. Spawn probe: `parent: ANTHROPIC_API_KEY (.env file)` / `child:  ANTHROPIC_API_KEY (.env file)`, where round 1 gave `child: … (shell environment)`. Grandchild: `grandchild: ANTHROPIC_API_KEY (.env file)`. Gemini spawn: `.env file` in both |
| 6 | no key value is printed | **pass** | every output is a boolean, a label, a name, or the marker's names (`'ANTHROPIC_API_KEY,GEMINI_API_KEY'`, or `''` when the shell set both) |
| 7 | the suite fails only where expected | **pass, 0 red tests from this unit** | Gate form: HEAD export 724 passed, unit export 724 passed. Full `tests/unit`: 2 failed, 724 passed in both, with identical FAILED lines (`test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`, both known-red at HEAD). Unit export with `.env` unlinked: 724 passed. With all three keys empty: 724 passed |
| 8 | the gates do not get worse | **pass** | ruff `Found 5 errors.` in both exports, all `BLE001`. The sorted sets (line numbers stripped) are identical. mypy `Found 10 errors in 4 files` in both. `ruff check config.py`: all checks passed. `mypy config.py`: no issues |

Further probes, all in the export:

| Probe | Output |
|---|---|
| `importlib.reload(config)` under `env -u ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY (.env file)`: a re-import in one process reads its own marker |
| `VALUATION_DOTENV_CREDENTIALS=DEEPSEEK_API_KEY python -c "import config"` | `ValueError: VALUATION_DOTENV_CREDENTIALS names ['DEEPSEEK_API_KEY'], which are not among (…). Only config.py writes this variable; unset it.` |
| `VALUATION_DOTENV_CREDENTIALS= ANTHROPIC_API_KEY=shell-probe` | `ANTHROPIC_API_KEY (shell environment)` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| A marker of names, in `os.environ` | F1: the record must survive a process boundary, and only `os.environ` crosses a spawn. The fix stays in `config.py`, as scope requires | A "loaded already" flag cannot tell an inherited shell value from an inherited `.env` value. Changing `app.py` is out of scope |
| Digests in memory only, never in the marker | F2, and a secret's digest has no reason to be in a child's environment or in `ps` | Holding a copy of each value would keep the secret in a second place. Identity checks on `os.environ` strings fail, because each read decodes a new string |
| The marker is checked, and import stops on a foreign name | rule 3 | Ignoring a foreign name would trust a variable this module did not write |
| `_is_set` has one definition (`name in os.environ and bool(os.environ[name].strip())`) | it is the same test as `resolve_provider`'s `.strip()`, and it uses no `.get` fallback | — |

No change was made to reach a target number. The unit moves no figure.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `VALUATION_DOTENV_CREDENTIALS` | absent means no ancestor loaded `config`, so nothing was inherited from `.env`. That is a fact, not a default for a value. A foreign name **stops** and names the variable | probe above. `config.py` `_inherited_dotenv_names` |
| `os.environ[<credential>]` at import | absent or blank means "not supplied". No figure comes from it | `config.py` `_is_set` |
| `name` passed to `credential_origin` | stops and names it | round-1 probe, unchanged |
| the credential at label time | stops and names it when unset or blank | round-1 probe, unchanged |

No "defaults to" row.

## What I did not do

- `tests/` (F3).
- `app.py`. The fix does not need it, and it is out of scope.
- I did not run uvicorn. The child probe uses the spawn mechanism that uvicorn uses,
  with no server.

## Findings for the orchestrator

1. A tester could pin F1 and F2 with these cases:
   - a spawn child of a parent whose `.env` filled the key, labelled `(.env file)`;
   - a spawn child under a shell value, labelled `(shell environment)`;
   - a value replaced in-process, which gets the third label;
   - a foreign name in `VALUATION_DOTENV_CREDENTIALS`, which stops the import.

   Each needs a subprocess or a spawned child, because the record is taken at import.
2. `VALUATION_DOTENV_CREDENTIALS` is a new environment name that this repository owns.
   It should go wherever such names are listed, if anywhere.
