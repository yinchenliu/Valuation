---
agent: code_reviewer
assignment: P13c-env-override
round: 3
verdict: approved
---

# Review of P13c-env-override, round 3

Programmer entry: `.agent/journal/2026-10-03T2042-programmer-p13c-env-override-r3.md`
Earlier reviews: `2026-10-03T2030-code_reviewer-p13c-env-override.md` (round 1) and
`2026-10-03T2041-code_reviewer-p13c-env-override-r2.md` (round 2)

I judged this round against the **Round 3 amendment** under step 2 of the assignment. It
narrows the label to a value comparison. It narrows a contract and claims no exception
to a rule, so it needs no user decision.

**Tree used.** Under `scratchpad/p13c_reviewer/` I made three exports of HEAD
`17381f3`:

- `base`: untouched, no `.env`.
- `unit`: this unit's three files copied in (`cmp`-identical to the working tree), with
  `.env` and `.venv` symlinked.
- `unitn`: the same files, `.venv` only, no `.env`.

The shared tree was not touched, and I deleted nothing outside my subdirectory. No API
call was made: every probe stops at `resolve_provider`, which reads `os.environ` only.
No key value was printed. The equal-value probe handed the file's value to a child's
environment and printed only the label.

The programmer measured on `0021845`, not `17381f3`. I re-measured every criterion on
`17381f3`. The extractor diff against `17381f3` is still `3 insertions, 3 deletions` on
lines 1894, 1931 and 1951. Line 1951 is in scope by the orchestrator's decision
recorded in round 1.

## The amended contract, point by point

| Contract point | Result | Evidence |
|---|---|---|
| read `.env` once with `dotenv_values`, fill only absent names | yes | `config.py:53-57`. The fill rule matches `dotenv.main.DotEnv.set_as_environment_variables` (`k in os.environ and not override` → skip; `None` → skip), read in the installed package |
| an empty value is not filled: the off switch is kept | yes | criterion 1, including a spawned child |
| marker and digest removed | yes | the only `VALUATION*` names in `os.environ` after import are `[]`. `dir(config)` has no `FINGER`, `MARKER` or `FROM_` name. `hashlib` is no longer imported |
| nothing written to the environment except names filled from `.env` | yes | the names the import adds are `['ANTHROPIC_API_KEY', 'GEMINI_API_KEY']`, all of them `.env` names. The shipped-code env-write grep gives only `config.py:56`, the fill |
| exactly two labels, by comparison at call time | yes | `config.py` `credential_origin`. An in-process replacement made after import changes the label, so the comparison happens at call time |
| stops on an unknown name and on an unset or blank name | yes | `credential_origin('DEEPSEEK_API_KEY')` → `ValueError … is not one of (…)`. A blank Foundry key → `ValueError … is not set to a non-blank value` |
| the doc states the rule as a comparison, and the equal-value case with its reason | yes | `environment.md`, the section "Whether the key in use is the one in `.env` is in the output". My equal-value probe gives `(.env file)`, as the doc says |

The file's credential values are held in memory in `_DOTENV_CREDENTIAL_VALUES`, keyed by
the two names `.env` holds. That is the same exposure as `os.environ`, which already
holds them. No message interpolates a value: both `raise`s interpolate only `name` and
`CREDENTIAL_NAMES`. Nothing dumps the `config` namespace (checked in round 2, and
unchanged).

The interpolation difference from `load_dotenv` is real: `dotenv_values` passes
`override=True` to `resolve_variables`. The docstring states it, and `.env` has no `${`
(`grep -c` → 0). I make no finding of it.

## The guard checks

Run over `config.py` and `docs/8-build/environment.md`, and over the three changed extractor lines.

| Check | Result |
|---|---|
| conditional zero | clean |
| lookup with a fallback | clean |
| bare or-default | clean |
| money field defaulted to zero | clean |
| `**kwargs` | clean |
| `getattr(` | clean |
| dict of functions keyed by data | clean |
| model client outside `ingestion/` | clean |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| the `.env` file absent | not a value. It reads as no names, exactly as `load_dotenv` did. Every credential must then come from the environment, or `resolve_provider` stops | `unitn`: key present `False`, `_DOTENV_CREDENTIAL_VALUES == {}`. A shell key labels `(shell or parent process, not .env)` |
| the file's value for `name` absent | not a default. It gives the second label, which is the stated rule and true ("`.env` does not hold the name") | same probe |
| `name` / the credential at label time | yes | the stop probes above |

## Done-criteria, re-run at `17381f3`

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | empty shell value turns the key off | `False`, the child too | `False`. Label form: `ValueError: No Anthropic credential resolved`. Spawned child: `child key present: False` | yes |
| 2 | shell value wins | `True` | `True` | yes |
| 3 | `.env` supplies with no shell value | `True` | `True` | yes |
| 4 | label says not `.env` for a shell value | parent and child | one process, and parent → child → grandchild: `(shell or parent process, not .env)` for Anthropic, Gemini and Foundry | yes |
| 5 | label names `.env` | parent and child | one process, and parent → child → grandchild under `env -u`: `(.env file)` for Anthropic and Gemini | yes |
| 6 | no key value printed | none | none | yes |
| 7 | suite fails only where expected | same failure set as base | `base`: 2 failed, 773 passed. `unitn`: 2 failed, 773 passed. FAILED lines **identical** (the known `test_projector_rule3_red.py::…names_the_input` and `test_routes_session_rule3_red.py::…cache_hit_stops`). Gate form 773 passed in both. `unit` with `.env` linked and all three keys empty: the same 2 failed, 773 passed. This matches the orchestrator's expected baseline | yes |
| 8 | gates no worse | ruff 5, mypy 10 | `base` and `unitn`: `Found 5 errors.` (5× `BLE001`, sets identical) and `Found 10 errors in 4 files` (sets identical) | yes |

**Round 2 F4 probes, re-run:**

| Probe | Round 2 | Round 3 |
|---|---|---|
| a `config` parent hands a subprocess `ANTHROPIC_API_KEY=parent-chosen-probe` | `(.env file)` | `ANTHROPIC_API_KEY (shell or parent process, not .env)` |
| the same, as spawn child and grandchild after the parent set the value | — | `(shell or parent process, not .env)` ×2 |
| `VALUATION_DOTENV_CREDENTIALS=ANTHROPIC_API_KEY ANTHROPIC_API_KEY=shell-probe` | `(.env file)` | `ANTHROPIC_API_KEY (shell or parent process, not .env)`. The variable is not read |

## Findings

### F5 — The second label's words name a history the contract says it does not state · `note`, for the orchestrator

**Evidence:** `env -u ANTHROPIC_API_KEY python -c "import os, config; os.environ['ANTHROPIC_API_KEY']='runtime-probe'; …"`
→ `ANTHROPIC_API_KEY (shell or parent process, not .env)`. Code in this process set that
value, not the shell and not a parent. The doc says "The label says nothing about a
value's history", but the words "shell or parent process" do name one.

**Why this is a `note` and not a rule finding:**

- The text is the amendment's, word for word ("returns exactly one of two labels"). The programmer had no latitude.
- On both shipped entry points, `cli.py` and the web app, the label is true. No shipped code sets a credential in-process: the env-write grep gives only `config.py:56`, the `.env` fill. So a value that differs from the file's was in the environment when the process started.
- It is untrue only when Python code in the same process sets the variable: a test's `monkeypatch`, or a notebook.
- The doc states that case exactly ("…or that code in the process replaced, reads `(shell or parent process, not .env)`").
- Rule 6's text governs assumptions in figures.

**What would fix it:** if the orchestrator reads its own rule-6 citation ("a label that
names the wrong source is a false label") as covering in-process library use, the
second label could be `(not the .env value)`. That wording is true in every case. It is
a one-word change to the contract, and it is the orchestrator's decision, not the
programmer's.

### F6 — A value equal to the file's apart from surrounding whitespace reads "not .env" · `note`

**Evidence:** the file's value plus a trailing space, handed to a child →
`ANTHROPIC_API_KEY (shell or parent process, not .env)`. The client strips the value
before use (`ingestion/claude_extractor.py:1128` `.strip()`), so the key sent is the file's
key. The doc defines the label as a comparison of the value in `os.environ`, so the doc
is truthful about this. It is a corner, recorded so that a tester does not take it for
a defect.

### F3 (round 1), extended — one more stale test comment · `note`

`tests/unit/_session_route_helpers.py:40` ("so its load_dotenv has run") is stale as
well, because `config.py` no longer calls `load_dotenv`. The other stale comments are
`:21` and `:242`, and `tests/unit/test_session_extraction.py:30`. All belong to the
tester, and no assertion depends on them.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 8, blanket `except Exception` | `ingestion/claude_extractor.py:1798` | no |
| 46, the defect this unit fixes | `config.py` | yes. It can close on this approval. `STATUS.md:380` belongs to the orchestrator |

## Earlier findings

| # | Outcome | Note |
|---|---|---|
| F1 | fixed | a spawned child and grandchild of a `.env` parent label `(.env file)`, because the inherited value equals the file's value |
| F2 | fixed | in-process replacement is caught by the comparison. No digest is needed. The wording is F5 |
| F3 | not_fixed | `tests/` belongs to the tester. It stays a `note` and is extended above |
| F4 | fixed | the marker is gone. Both round-2 probes now give the second label |

## For the orchestrator, outside the code

The programmer's entry reports `rm -rf` on generic directory names in the shared
scratchpad in round 1: `scratchpad/iso` and `scratchpad/head`. **My round 1 and round 2
exports were `scratchpad/head`, `scratchpad/unit`, `scratchpad/unit2` and
`scratchpad/unit2n`.** I also ran `rm -rf` on `scratchpad/head` and `scratchpad/unit`
at creation in round 1, and on `scratchpad/unit2` and `scratchpad/unit2n` in round 2.
Each of the two units may have removed the other's tree of the same name. Neither
review's numbers depend on that: each tree was rebuilt from `git archive` before it
was measured. In this round I created and deleted nothing outside `p13c_reviewer/`.

## Verdict

`approved`

The code meets the Round 3 amendment on every point, and the doc states the labels as
the comparison the code makes. All eight criteria re-measure as claimed on `17381f3`.
The failure set and both gate sets are identical to the baseline. F1, F2 and F4 are
fixed. F5 and F6 are notes: F5 is an optional wording question for the orchestrator,
and F6 needs no action.
