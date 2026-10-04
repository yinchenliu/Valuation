---
agent: code_reviewer
assignment: P13c-env-override
round: 2
verdict: changes_requested
---

# Review of P13c-env-override, round 2

Programmer entry: `.agent/journal/2026-10-03T2031-programmer-p13c-env-override-r2.md`
Round 1 review: `.agent/journal/2026-10-03T2030-code_reviewer-p13c-env-override.md`

I measured on fresh `git archive 0021845` exports with only this unit's three files copied in:

- `unit2` has `.env` and `.venv` symlinked.
- `unit2n` has only `.venv`, for a suite run comparable to the HEAD run, which had no `.env`.

The shared tree was not touched. No API call was made. Every probe stops at
`resolve_provider`, which reads `os.environ` only (round 1, `claude_extractor.py:1955-1976`).
No key value was printed.

The extractor diff is still `3 insertions, 3 deletions`, on lines 1894, 1931 and 1951.
Line 1951 is in scope by the orchestrator's decision recorded in round 1.

## The three questions the orchestrator asked

1. **Is writing an environment variable from `config.py` acceptable?** Yes, in principle.
   - No rule in `docs/2-rules/rules.md` forbids it.
   - `config.py` is in scope.
   - The marker carries names, never values, and `.env` is still read once per process. That meets step 2.
   - Shipped code writes nothing else: `grep -rnE 'os\.environ\[[^]]*\] *=|putenv|environ\.setdefault|environ\.update|setenv' api ingestion analysis models cli.py app.py config.py` gives only `config.py:105`, the marker write.
   - The defect is in what a child does when it **reads** the marker. See F4.
2. **Could the in-memory digest leak a key?** No.
   - `_START_UP_FINGERPRINTS` is used only at `config.py:120` and `:153-154`. It is never written to `os.environ` and never put in an exception message.
   - No code dumps the `config` namespace: `grep -rnE "vars\(config\)|dir\(config\)|config\.__dict__|getmembers\(config"` over `api ingestion analysis models cli.py app.py tests` gives no match.
   - An unsalted SHA-256 of a high-entropy API key cannot be reversed. It sits in the same memory as the key itself, which `os.environ` already holds, so it adds no exposure.
   - No probe output contained a digest.
3. **Does the doc now state the labels truthfully?** Not fully.
   - The `(shell environment)` and third-label rows are true.
   - The `(.env file)` row says the value "has not been replaced since". That holds inside one process, not across a process boundary.
   - "Do not set it yourself: `config` stops on a name it does not record" leaves out that a recorded name is accepted without a check.
   - Both points are in F4.

## The guard checks

Run over `config.py` and `docs/8-build/environment.md`, and over the three changed extractor lines.

| Check | Result |
|---|---|
| conditional zero | clean |
| lookup with a fallback | clean (`_is_set` is `name in os.environ and bool(os.environ[name].strip())`) |
| bare or-default | clean |
| money field defaulted to zero | clean |
| `**kwargs` | clean |
| `getattr(` | clean |
| dict of functions keyed by data | clean. `_START_UP_FINGERPRINTS` maps a name to a string, which rule 2 allows |
| model client outside `ingestion/` | clean |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `VALUATION_DOTENV_CREDENTIALS` with a foreign name | yes | probe: `ValueError: VALUATION_DOTENV_CREDENTIALS names ['DEEPSEEK_API_KEY'], which are not among (…)` |
| the marker absent | not a value. It means "no ancestor imported `config`" | `config.py:57-58` |
| the marker with a recorded name | **no check of the value it vouches for**. See F4 | probe below |
| `name` / an unset credential in `credential_origin` | yes, unchanged from round 1 | — |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | empty shell value turns the key off | `False`, and the child too | `False`. A spawned child gives `child key present: False` | yes |
| 2 | shell value wins | `True` | `True` | yes |
| 3 | `.env` supplies with no shell value | `True` | `True` | yes |
| 4 | label names the shell | parent and child | spawn probe (parent → child → grandchild): `(shell environment)` ×3 for Anthropic, Gemini and Foundry | yes |
| 5 | label names `.env` | parent, child, grandchild | `(.env file)` ×3 for Anthropic and Gemini. The round-1 F1 case is fixed | yes for a pure spawn. **No when the parent hands the child a different value: F4** |
| 6 | no key value printed | none | none | yes |
| 7 | suite fails only where expected | same failure set as HEAD | `unit2n` (no `.env`): 2 failed, 724 passed. FAILED lines are **identical** to the HEAD export (the two known-red `*_rule3_red` tests). Gate form: 724 passed. `unit2` with `.env` linked and all three keys empty: the same 2 failed, 724 passed | yes |
| 8 | gates no worse | ruff 5, mypy 10 | `Found 5 errors.`, with the `BLE001` set identical to HEAD. `Found 10 errors in 4 files`, with the set identical to HEAD | yes |

The programmer's further probes reproduced:

- `importlib.reload(config)` gives `(.env file)`.
- An empty marker with a shell key gives `(shell environment)`.
- F2: a replaced value gets the third label, and a value restored to its start-up value gets `(shell environment)` again.

## Findings

### F4 — A child trusts the inherited marker without checking the value, so it labels a value from a parent "(.env file)" · `major`

**Evidence:** two probes in `unit2`.

A parent that imported `config` passes a child a key it chose:
```
env -u ANTHROPIC_API_KEY python -c "import os, subprocess, sys, config; subprocess.run([sys.executable, '-c', 'import config; …credential_source'], env={**os.environ, 'ANTHROPIC_API_KEY': 'parent-chosen-probe'})"
→ ANTHROPIC_API_KEY (.env file)
```
A marker set by hand with a recorded name, under a shell key:
```
VALUATION_DOTENV_CREDENTIALS=ANTHROPIC_API_KEY ANTHROPIC_API_KEY=shell-probe python -c "import config; …"
→ ANTHROPIC_API_KEY (.env file)
```
In both cases the value did not come from `.env`.

**Why it matters now.** Any process that imports `config` puts the marker in its own `os.environ`, and pytest is such a process. The programmer's round-2 finding 1 asks the tester for subprocess cases such as "a spawn child under a shell value, labelled `(shell environment)`". From pytest those are built as `env={**os.environ, "ANTHROPIC_API_KEY": …}`, which inherits the marker. On a machine whose `.env` holds the key, those cases get `(.env file)`. The next unit would then either fail for no visible reason or pin the false label.

**The doc is also wrong here.** The `(.env file)` row says the value "has not been replaced since", and the marker paragraph presents "stops on a name it does not record" as the guard. The programmer's entry states the cross-process limit. The doc does not.

**Rule or document:** `docs/2-rules/rules.md` rule 6, applied as the assignment's Citations apply it: "a label that names the wrong source is a false label." Round-1 F1 was the same class, and reachability is not the test.

**What would fix it.** Inside `config.py`, read `.env` once per process with `dotenv_values` and fill absent names yourself, in place of `load_dotenv`. That is still one read. Then label an inherited, marker-named name `(.env file)` only when its value equals the file's value. Otherwise label it as set before start-up by a parent process, or stop. Update the doc rows to match.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 8, blanket `except Exception` | `ingestion/claude_extractor.py:1798` | no |
| 46, the defect this unit fixes | `config.py` | yes. Closure waits on F4 |

The `os.environ.get(NAME, "").strip()` guards before each label are pre-existing and
unchanged, as in round 1. Each blank result raises or moves to the next branch, never to a number.

## Earlier findings

| # | Outcome | Note |
|---|---|---|
| F1 | fixed | spawned child and grandchild of a `.env` parent label `(.env file)`, and of a shell parent `(shell environment)`. The false doc sentence is removed. F4 is a new defect in the fix's read side, not F1 left standing |
| F2 | fixed | the in-memory digest gives the third label to a value replaced in-process. The digest does not leak (question 2 above) |
| F3 | not_fixed | correctly left to the tester, because `tests/` is outside the programmer's scope. It stays a `note` and does not block |

## Verdict

`changes_requested`

F4 is a `major`. A child labels `(.env file)` a value that its parent or the shell supplied
whenever the inherited marker names it. Pytest inherits the marker, so the tester's
recommended subprocess cases would reach the false label. Everything else in round 2
holds:

- F1 and F2 are fixed.
- The marker write and the digest are acceptable.
- All eight criteria re-measure as claimed for a pure spawn.
- The failure set and both gate sets match HEAD.

This is round 2. If round 3 does not close F4, the orchestrator should judge whether to
narrow the labelling contract in the assignment instead.
