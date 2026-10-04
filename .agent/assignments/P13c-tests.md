---
id: P13c-tests
phase: 13 — silent defects first (the user's decision of 2026-10-03)
agent: tester
depends_on: [P13c-env-override]
---

# Lock the key order and the key label, and correct the stale test comments

## Objective

`P13c-env-override` (committed at `5b03600` after three review rounds) closes backlog
item 46. `config.py` now reads `.env` once with `dotenv_values` and fills only names that
are absent from the environment. `config.credential_origin(name)` labels a key
`(.env file)` when the value in use equals the file's value, and
`(shell or parent process, not .env)` otherwise. **No test locks any of this.** A
regression to `override=True` would pass the whole suite today, and the next run with the
key "turned off" would make a paid call.

Read these first:

- `.agent/assignments/P13c-env-override.md`, including the round 3 amendment
- the three programmer entries and three review entries for `P13c-env-override` in
  `.agent/journal/` (`2026-10-03T2022`, `T2030`, `T2031`, `T2041`, `T2042`, `T2052`)
- `.claude/agents/tester.md`, from its first section.

## What to do

**Make no API call, and never print or assert a real key value.** The repository's
`.env` holds a live key. Every test must use a `.env` file that the test writes itself,
with invented values, in a temporary directory. A test must not read the real `.env`.

1. **Lock the order.** With a temporary `.env` that holds a name:
   - a value set in the environment before `config` loads wins over the file;
   - an empty value set before `config` loads stays empty (the off switch);
   - an absent name is filled from the file.
   `config` reads `BASE_DIR / ".env"` at import. Find a way to point it at your file
   that does not change `config.py`, for example a subprocess whose working copy of the
   module sees your directory, or a fresh import with the path patched before it runs.
   Say in your entry which way you chose and why it tests the shipped code path.

2. **Lock the two labels.** A value equal to the file's value gives `(.env file)`. A
   value that differs, or a name the file does not hold, gives
   `(shell or parent process, not .env)`. An unknown name and a blank value both raise
   `ValueError` naming the field. Do not lock the round 3 review's F5 case (a value set
   inside the process reads the second label) as correct behaviour. It is a recorded
   note, not a decision.

3. **Lock the round 1 and round 2 failures.** A spawned child process must label a value
   from your `.env` as `(.env file)`, and a value that a parent chose for the child as
   `(shell or parent process, not .env)`. These are the two cases that broke in review.

4. **Correct the stale comments.** `tests/unit/_session_route_helpers.py:21`, `:40` and
   `:242`, and `tests/unit/test_session_extraction.py:30`, still describe
   `override=True` or `load_dotenv`. Correct them to the current behaviour. Change no
   assertion in those files.

## Files in scope

- `tests/unit/test_config_env.py`, new
- `tests/unit/_session_route_helpers.py`, comments only
- `tests/unit/test_session_extraction.py`, comments only

**Nothing else.** Work in your own scratch subdirectory, `scratchpad/p13c_tester/`. The
scratchpad is shared; never `rm -rf` a path outside your subdirectory.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the gate form | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | the full suite | exactly the 2 known `*_rule3_red.py` failures | `.venv/bin/python -m pytest -q` |
| 3 | the real `.env` is never read by a new test | no new test passes or fails differently with the real `.env` moved aside | run the new file with and without `.env` present (move it back at once) |
| 4 | each behaviour is locked | each of steps 1 to 3 has a test that fails when the behaviour is reverted | in a scratch copy: `override=True` back; the label comparison removed; for step 3, `credential_origin` given the round 2 marker logic. Report which tests turn red |
| 5 | the comment edits change no assertion | only comment lines differ | `git diff` of the two helper files, read line by line |
| 6 | two counts | accuracy and coverage, as `tester.md` requires | its "Report two counts" section |

## Citations

- `docs/8-build/environment.md`, section 3: the order and the labels as documented.
- `docs/9-reference/refactor-backlog.md`, item 46: the probe table.
- `python-dotenv`: `dotenv_values` reads a file and returns a dict; it sets nothing.

## Backlog items this unit is NOT fixing

- Item 8: the blanket `except Exception` in `ingestion/claude_extractor.py`.
- The round 3 review's F5 and F6 notes on item 46.
