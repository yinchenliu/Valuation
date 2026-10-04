---
id: P13c-env-override
phase: 13 — silent defects first (the user's decision of 2026-10-03)
agent: programmer
depends_on: []
---

# Let the shell turn the API key off, and say where the key came from

## Objective

`config.py:15` is `load_dotenv(BASE_DIR / ".env", override=True)`. So a value in `.env`
replaces a value that the shell set, and nothing in the shell can turn the key off. On
2026-10-02 a run with `env -u ANTHROPIC_API_KEY` still started Pass 1 on the Chipotle
2023 10-K, and it is not known whether that call was billed. The credential label then
said `ANTHROPIC_API_KEY (environment)` for a key that came from the file. Backlog
item 46.

## What is already true — verify, do not redo

The interpreter is `.venv/bin/python`. Measured at `0021845` on 2026-10-03.

| Fact | Command | Result |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 724 passed |
| lint, types | the gates in `docs/8-build/environment.md` | ruff 5 (`BLE001`), mypy 10 in 4 files |
| the override | `grep -n load_dotenv config.py` | line 15, `override=True` |
| the labels | `grep -n "credential_source=" ingestion/claude_extractor.py` | lines 1894, 1918 and 1931, each a literal `(environment)` |
| the backlog's probe table | `docs/9-reference/refactor-backlog.md`, item 46 | with `override=False`, an empty shell value removes the key and `env -u` does not |

If any of these disagrees with what you measure, stop and report the disagreement.

## What to do

**Do not make an API call.** Do not run route A, `extract_financials`,
`extract_multi_year`, the web upload of a PDF, or `cli.py` with PDF arguments. `.env`
holds a live key, and a call costs money. Every check below imports `config` or calls
`resolve_provider`, which builds a label and sends nothing. Confirm that
`resolve_provider` sends nothing before you call it.

1. **`config.py`.** Change to `override=False`. Before `load_dotenv` runs, record which
   credential names the shell already set, so the code can later say where each key came
   from. Correct the comment on line 15 to state the real order.

2. **`ingestion/claude_extractor.py`.** Each of the three `credential_source` labels
   names the real source: the shell, or the `.env` file. Use the record from step 1. Do
   not read `.env` a second time.

3. **`docs/8-build/environment.md`.** State the order: a value set in the shell wins over
   `.env`. State the way to run with the key off: set it empty for one run
   (`ANTHROPIC_API_KEY= ...`). State that `env -u` does not turn it off, because
   `load_dotenv` fills an absent name from the file. The backlog's probe table is the
   evidence. Cite it.

   **Round 3 amendment (orchestrator, 2026-10-03, from the round 2 review's F4).** Two
   rounds show that a label which tries to name the history of a value ("the shell set
   it before start-up") breaks at each process boundary. Round 1 broke in a child
   process. Round 2's marker variable is trusted without a check, so a value that a
   parent chose reads `(.env file)`. **Narrow the contract to a fact that each process
   can check for itself: does the value in use equal the value in `.env`?**

   - Read `.env` once with `dotenv_values`. Fill each name that is absent from the
     environment yourself. A name that is set, even to an empty value, is not filled.
     This keeps the `override=False` behaviour and the empty-value off switch.
   - Remove `VALUATION_DOTENV_CREDENTIALS` and the in-memory digest. Write nothing to
     the environment except the names that you fill from `.env`.
   - `credential_origin(name)` compares the value in use at call time with the value
     read from `.env`. It returns exactly one of two labels: `(.env file)` when they are
     equal, or `(shell or parent process, not .env)` when they differ or `.env` does
     not hold the name. It still stops on a name it does not know, and on a name that
     is unset or blank.
   - The doc states the rule as a value comparison. It says that a shell value equal to
     the file's value also reads `(.env file)`, and why that is harmless: the key in use
     is the key in the file.

4. **Do not edit `tests/`.** Tests that assert the old label text can turn red. List
   every one, by name, with the reason. The tester repairs them.

## Files in scope

- `config.py`
- `ingestion/claude_extractor.py`, the three `credential_source` labels and nothing
  else in the file
- `docs/8-build/environment.md`

**Nothing else.** Work outside this list is a review finding, even if the change is
good. Two other units run in parallel: `P13a-analysis-silent` owns
`analysis/normalizer.py` and `analysis/wacc.py`, and `P13b-models-silent` owns
`models/`, `analysis/dcf.py` and `analysis/projector.py`.

## Out of scope

- `tests/`: the tester's.
- `ingestion/session_extraction.py`: route B uses no credential.
- `docs/9-reference/refactor-backlog.md` and `STATUS.md`: the orchestrator's.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | an empty shell value turns the key off | `False` | `ANTHROPIC_API_KEY= .venv/bin/python -c "import os, config; print(bool(os.environ.get('ANTHROPIC_API_KEY')))"` |
| 2 | a shell value wins over `.env` | `True` | `ANTHROPIC_API_KEY=shell-probe .venv/bin/python -c "import os, config; print(os.environ['ANTHROPIC_API_KEY'] == 'shell-probe')"` |
| 3 | with no shell value, `.env` still supplies the key | `True` | `env -u ANTHROPIC_API_KEY .venv/bin/python -c "import os, config; print(bool(os.environ.get('ANTHROPIC_API_KEY')))"` |
| 4 | the label names the shell | the label says the shell | criterion 2's form, printing the `credential_source` from `resolve_provider` |
| 5 | the label names `.env` | the label says `.env` | criterion 3's form, printing the same field |
| 6 | no key value is printed | no key text in any output | read every output above |
| 7 | the suite fails only where expected | every red test named, with its reason | the full suite and the gate form |
| 8 | the gates do not get worse | ruff 5, mypy 10 | the two gate commands |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/9-reference/refactor-backlog.md`, item 46: the fact, the probe table and the fix.
- `docs/2-rules/rules.md`, rule 6: a label that names the wrong source is a false label.
- `python-dotenv`: `load_dotenv(override=False)` does not replace a name that is already
  set, and it fills a name that is absent.

## Known open items

- `DEEPSEEK_API_KEY` is in `.env` and no code reads it. Leave it.

## Backlog items this unit is NOT fixing

- Item 8: the blanket `except Exception` in `ingestion/claude_extractor.py`.
- Items 10, 44, 50, 51, 61, 63 and 64 in `ingestion/claude_extractor.py`. Items 10, 44
  and 50 wait for the user's decision on the Pass 1 role.
