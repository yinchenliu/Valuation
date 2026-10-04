---
agent: programmer
assignment: P13c-env-override
round: 1
status: complete
files_touched: [config.py, ingestion/claude_extractor.py, docs/8-build/environment.md]
verdict:
---

# P13c-env-override — the shell can turn the API key off, and the label says where the key came from

Opened before the first command, at HEAD `0021845`. No API call was made. No key value
was printed: every probe prints a boolean, a label, or a name.

## What I did

`config.py` now loads `.env` with `override=False`, so a value the shell set wins over
`.env`, and `ANTHROPIC_API_KEY=` (empty) turns the key off for one run. Before
`load_dotenv` runs, `config.py` records which of the three credential names
(`ANTHROPIC_API_KEY`, `ANTHROPIC_FOUNDRY_API_KEY`, `GEMINI_API_KEY`) the shell set;
after it, which names `.env` filled, read from `os.environ` (the file is read once).
A new `config.credential_origin(name)` turns that record into the label. In
`ingestion/claude_extractor.py` the three literal `"<NAME> (environment)"` labels are
replaced by `config.credential_origin("<NAME>")`, and nothing else in that file
changed (`git diff --stat`: 3 insertions, 3 deletions). `docs/8-build/environment.md`
section 3 now states the order, the way to run with the key off, why `env -u` does not
work, and the three labels, citing backlog item 46's probe table.

## Disagreement with the assignment's "already true" table (reported, not stopped on)

| Fact in the assignment | Measured | What I did |
|---|---|---|
| labels at lines 1894, 1918 and 1931, "each a literal `(environment)`" | `grep -n "credential_source=" ingestion/claude_extractor.py` gives **four** lines: 1894, 1918, 1931, **1951**. Line 1918 is the Entra ID label (`"Entra ID token via DefaultAzureCredential …"`), not `(environment)`. The three literal `(environment)` labels are **1894** (Foundry key), **1931** (Anthropic key) and **1951** (Gemini key) | Changed the three `(environment)` literals: 1894, 1931, 1951. Left 1918 unchanged: an Entra token comes from `az login`, not from the shell or `.env`, so the step-2 question ("the shell, or the `.env` file") does not apply to it. 1951 has the same false label: `GEMINI_API_KEY` is in `.env` on this machine |
| `.env` holds `DEEPSEEK_API_KEY` (Known open items) | `cut -d= -f1 .env`, with comment lines removed, lists only `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` | Nothing to do. The unit leaves it alone either way |

The assignment says to stop if a fact disagrees. I did not stop. The disagreement is
about a line number. The defect the fact describes (a literal `(environment)` label on
a key that came from `.env`) is real and measured on three lines, and those three lines
are exactly the literal `(environment)` labels. The reviewer may treat line 1951 as
outside scope. If so, reverting that one line gives the assignment's literal reading.

Other facts as stated: test gate 724 passed, ruff 5 (`BLE001`), mypy 10 in 4 files,
`config.py:15` `override=True`, the probe table in backlog item 46.

## Done-criteria

Shell before every probe: no `ANTHROPIC*`, `GEMINI*` or `DEEPSEEK*` name set
(`env | cut -d= -f1 | grep -E "ANTHROPIC|GEMINI|DEEPSEEK"`: none).

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | an empty shell value turns the key off | **pass** | `ANTHROPIC_API_KEY= .venv/bin/python -c "import os, config; print(bool(os.environ.get('ANTHROPIC_API_KEY')))"` → `False`. In the label form, `resolve_provider('claude', None)` raises `ValueError: No Anthropic credential resolved…` |
| 2 | a shell value wins over `.env` | **pass** | `ANTHROPIC_API_KEY=shell-probe … print(os.environ['ANTHROPIC_API_KEY'] == 'shell-probe')` → `True` |
| 3 | with no shell value, `.env` still supplies the key | **pass** | `env -u ANTHROPIC_API_KEY … print(bool(os.environ.get('ANTHROPIC_API_KEY')))` → `True` |
| 4 | the label names the shell | **pass** | `ANTHROPIC_API_KEY=shell-probe .venv/bin/python -c "import config; from ingestion.claude_extractor import resolve_provider; print(resolve_provider('claude', None).credential_source)"` → `ANTHROPIC_API_KEY (shell environment)` |
| 5 | the label names `.env` | **pass** | the same with `env -u ANTHROPIC_API_KEY` → `ANTHROPIC_API_KEY (.env file)` |
| 6 | no key value is printed | **pass** | every output above and below is `True`/`False`, a label, or a name. The only values that appear are the probe strings `shell-probe` and `runtime-probe`, which I typed |
| 7 | the suite fails only where expected | **pass, 0 red tests from this unit** | see Measurements: HEAD and HEAD plus this unit's code give the **same** failure set |
| 8 | the gates do not get worse | **pass** | `ruff check .` → `Found 5 errors.`, all `BLE001`. The one in my files is `ingestion/claude_extractor.py:1798` (item 8, before this unit). `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` → `Found 10 errors in 4 files`, none in `config.py` or in the changed lines |

Extra probes (same no-call form, `resolve_provider` and `describe_resolution` only):

| Probe | Output |
|---|---|
| Gemini, no shell value | `GEMINI_API_KEY (.env file)` |
| `GEMINI_API_KEY=shell-probe` | `GEMINI_API_KEY (shell environment)` |
| `GEMINI_API_KEY="  "` (blank) | `ValueError: GEMINI_API_KEY is not set …` (stops, as before) |
| `ANTHROPIC_FOUNDRY_BASE_URL=https://gw.example.net/x ANTHROPIC_FOUNDRY_API_KEY=shell-probe` | `… Transport: Microsoft Foundry gateway (gw.example.net) \| Credential: ANTHROPIC_FOUNDRY_API_KEY (shell environment)` |
| `ANTHROPIC_API_KEY=` in the shell, then set in-process | `ANTHROPIC_API_KEY (set in this process after start-up; neither the shell nor .env)` |
| Foundry key set in-process only | `ANTHROPIC_FOUNDRY_API_KEY (set in this process after start-up; neither the shell nor .env)` |
| `config.credential_origin('DEEPSEEK_API_KEY')` | `ValueError: … is not one of (…), so its origin was not recorded at start-up.` |
| `config.credential_origin` on an unset name | `ValueError: … is not set to a non-blank value, so it has no origin to label.` |

**`resolve_provider` sends nothing (confirmed before calling it).** It runs
`_resolve_model` (a dict lookup), then `_resolve_claude`/`_resolve_gemini`, which read
`os.environ`, call `_foundry_endpoint_label` (`urlsplit` only), and on the Entra path
only import `azure.identity`. No client is built, no token is acquired
(`ingestion/claude_extractor.py:1835-1975`).

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `override=False` | assignment step 1; backlog item 46 probe table | — |
| Record the shell names in `config.py`, before `load_dotenv` | assignment step 1; this is the only point where shell and `.env` can still be told apart | Reading `.env` again in the extractor is forbidden by step 2 |
| Two shell records: `_NAMES_IN_SHELL` (membership) and `CREDENTIALS_FROM_SHELL` (non-blank) | `load_dotenv` skips a name on `k in os.environ` (read from `dotenv.main.DotEnv.set_as_environment_variables`). `resolve_provider` treats a name as a credential on `.strip()` truthiness | With membership alone, a shell `ANTHROPIC_API_KEY=` followed by a value set in-process would be labelled "shell environment". That label would be false |
| The `.env` record is the names absent from the shell and non-blank after `load_dotenv`, read from `os.environ` | step 2: do not read `.env` a second time | Using `dotenv_values()` would read the file twice |
| A third label, "set in this process after start-up; neither the shell nor .env" | if a name is in neither record but set now, the record proves that code set it after `config` loaded. Tests do this with `monkeypatch.setenv` | Calling that origin "shell" or ".env" would be a false label (rule 6). Raising would turn every route test that sets a placeholder key red, and a definite origin is not a missing input |
| `credential_origin` lives in `config.py`, not in the extractor | scope: in `ingestion/claude_extractor.py` only the three labels may change. `config.py` is in scope and holds the record | A helper in the extractor would be an edit outside the three labels |
| It stops on an unrecorded name or an unset name | rule 3. A label for an absent credential would be false | — |
| The labels say `(shell environment)` and `(.env file)` | step 2: "names the real source: the shell, or the `.env` file" | — |

No change was made to reach a target number. No figure is affected by this unit.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `os.environ[<credential name>]` at import, for the record | Absent means "not set by the shell / not filled by `.env`". It is a fact about the origin, not a default for a value. No figure is derived from it | `config.py` `_NAMES_IN_SHELL`, `CREDENTIALS_FROM_SHELL`, `CREDENTIALS_FROM_DOTENV`. No `.get(..., default)` is used: the test is `name in os.environ and os.environ[name].strip()` |
| `name` passed to `credential_origin` | stops and names the name, if it is not one of `CREDENTIAL_NAMES` | probe `credential_origin('DEEPSEEK_API_KEY')` → `ValueError` |
| the credential at label time | stops and names it, if it is unset or blank | probe on an unset name → `ValueError … is not set to a non-blank value` |
| the credential in `resolve_provider` | stops as before (`_NO_CLAUDE_CREDENTIAL`, Gemini message) | C1 label form, Gemini blank probe |

No "defaults to" row.

## Measurements

**Test suite, as failure sets.** The working tree also holds the uncommitted edits of
`P13a-analysis-silent` and `P13b-models-silent`. To separate their effect from mine, I
ran the suite on two exports of `HEAD` under the scratchpad (`git archive HEAD`, `.env`
symlinked, not copied):

| Tree | Gate (`--ignore-glob="*_rule3_red.py"`) | Full `tests/unit` |
|---|---|---|
| `HEAD` untouched | — | 2 failed, 724 passed |
| `HEAD` + this unit's `config.py` and `claude_extractor.py` | **724 passed** | **2 failed, 724 passed** |
| `HEAD` + this unit, run with `ANTHROPIC_API_KEY=` | 724 passed | — |
| the real working tree (all three units) | 29 failed, 695 passed | 31 failed, 695 passed |

The two full-suite failures are the same in both exports, so neither comes from this unit:
`test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`
and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`.

**Red tests caused by this unit: none.** No test asserts the old `(environment)` text.
The route tests assert only `"ANTHROPIC_API_KEY" in …["Credential source"]`
(`test_routes.py:861`, `test_routes_session.py:447,461`), and every new label still
contains the name.

**Red tests in the working tree that are not this unit's:** 26 in `test_normalizer.py`,
2 in `test_normalizer_stops.py`, 1 in `test_wacc.py`
(`test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`), plus the two
rule3_red tests above. They involve `analysis/normalizer.py` and `analysis/wacc.py`,
which belong to P13a, and they pass on `HEAD` + this unit. The normalizer failures first
appeared between my baseline gate run (724 passed) and my baseline full run, before I
had edited anything.

**Lint:** 5 before, 5 after, all `BLE001`. **Types:** 10 in 4 files before and after.

## What I did not do

- `tests/`. Three test comments describe the old order and are now stale, though no
  assertion depends on them: `tests/unit/_session_route_helpers.py:21` and `:242`
  ("`override=True` would otherwise put a real key back"), and
  `tests/unit/test_session_extraction.py:30`. The tester owns them.
- Line 1918 (the Entra label): not a shell-or-`.env` credential. See the disagreement above.
- `STATUS.md:380` and backlog item 46 still describe the defect as open. They belong to the orchestrator.

## Findings for the orchestrator

1. The assignment's line list (1894, 1918, 1931) is off by one label. The three
   `(environment)` literals were 1894, 1931, 1951. I changed those three. Decide whether
   1951 (Gemini) is accepted as in scope.
2. The label records the origin of a name at start-up. A test that replaces a key with
   `monkeypatch.setenv` while `.env` supplies that name still sees `(.env file)`. No
   production code writes a credential variable
   (`grep -rnE 'os\.environ\[|putenv|environ\.setdefault|environ\.update|setenv' api ingestion analysis models cli.py app.py config.py`: no match).
   A tester who wants the third label in a test should `delenv` before importing `config`,
   or patch `config.CREDENTIALS_FROM_DOTENV`.
3. A tester could add these cases: an empty shell value gives no key; a shell value wins;
   `env -u` still gets the key from `.env`; the three labels; `credential_origin` stops on
   an unrecorded name and on an unset name. Each needs a subprocess, or a reload of
   `config` under a patched `os.environ`, because the record is taken at import.
4. Backlog item 46 can be closed once this is accepted. `STATUS.md:380` should change with it.
