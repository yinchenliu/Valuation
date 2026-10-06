---
id: P14f-prompt-encoding
phase: 14 — the Pass 1 and Pass 2 roles
agent: programmer
depends_on: []
---

# `prompt --pass 2` stops on a Windows console (item 113)

## Objective

**The fact.** On the Windows machine, with no environment variable set:

```
$ ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/Scripts/python.exe \
    -m ingestion.session_extraction prompt extractions/WMT.json --filing 0 --pass 2
=== SYSTEM PROMPT ? Pass 2, ...\extractions\WMT.json: filings[0] (...) ===
ERROR: 'charmap' codec can't encode character '→' in position 2992:
  character maps to <undefined>
exit 2
```

19 lines, then a stop. With `PYTHONIOENCODING=utf-8` in front of the same command: **exit
0 and 82 lines.**

**What follows.** `→` is `→`. Two of them are inside the Pass 2 prompt's `direction`
rules, at `ingestion/claude_extractor.py:412-413`:

```
"add_back" = one-time EXPENSE that inflated costs → remove to get clean earnings
"remove"   = one-time GAIN that inflated income → strip to get clean earnings
```

So **route B's reader cannot see the Pass 2 prompt on this machine** unless it already
knows a workaround that nothing in the repository tells it. The `extract-filing` skill
sends a session to `SE prompt` as step 3.1 of Pass 2.

**Measured 2026-10-06 by the overall lead. Exactly one subcommand fails**, and that
narrows the fix:

| Subcommand | Exit code, no `PYTHONIOENCODING` | Codec errors |
|---|---|---|
| `plan` | 0 | 0 |
| `locate` | 0 | 0 |
| `text` | 0 | 0 |
| `prompt --pass 1` | 0 | 0 |
| **`prompt --pass 2`** | **2** | **1** |
| `check` | 0 | 0 |

**The constraint that decides the fix.** Those two lines are **prompt text that route A
sends to the model.** [AGENTS.md](../../AGENTS.md) says any change to the LLM boundary is
an escalation. Replacing `→` with `->` would change what the model reads, for every
future route A extraction, to work around a console. **So the prompt text does not
change. The stream does.**

**What follows.** When this unit is done, every `session_extraction` subcommand runs to
completion on a Windows console with no environment variable set, and the bytes
`pass2_prompts` returns are the bytes it returned before.

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-06, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1175 passed, 2 skipped, 0 failed** |
| full suite | `-m pytest -q` | **2 failed**, the two red on purpose |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 5 errors in 2 files, 21 checked |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.claude/check_guard.py` | 48/48 |

**Facts about the code, each read on 2026-10-06:**

| Fact | Where |
|---|---|
| `cmd_prompt` prints the system prompt, the user prompt and a closing note to stdout | `ingestion/session_extraction.py:1021-1050` |
| `parse_pass1`'s arithmetic table is already redirected to stderr, so stdout holds the prompt and nothing else | `ingestion/session_extraction.py:1038-1040` |
| the two arrows that stop the run | `ingestion/claude_extractor.py:412-413` |
| ten more `→` characters in the same file, all in docstrings and comments, none printed | `ingestion/claude_extractor.py`, lines 6, 10, 28, 29, 30, 1971 and others |
| `ingestion/session_extraction.py` holds no `→` at all | `grep -c "→"` → 0 |

**`extractions/WMT.json` is your test input and it is not in git** (`.gitignore:33`).
**Do not edit it and do not delete it.**

## What to do

1. **Make the command finish on a console whose encoding cannot hold the character.**
   Fix the stream, not the text. Choose between reconfiguring the output stream and
   writing the prompt through an encoder that cannot stop, and **say in your entry which
   you chose and what the console then shows for `→`.** A fix that prints a replacement
   character silently is not acceptable: the reader must be able to tell that an arrow
   was there.
2. **Change no byte of any prompt.** `pass1_prompts` and `pass2_prompts` must return
   exactly what they return today. Prove it by hashing both returns before and after.
3. **Fix it once, for every subcommand**, not only for `prompt --pass 2`. The other five
   pass today by luck: none of them happens to print a character outside the console's
   code page. `check`'s and `plan`'s output already carry non-ASCII text in other places.
4. **Do not set `PYTHONIOENCODING` from inside the code** and do not tell the user to set
   it. An environment variable that the program needs, and does not set, is a defect that
   moved rather than closed.
5. **State the behaviour on a console that can hold the character.** A terminal set to
   UTF-8 must still print `→` as `→`. A fix that degrades the good case to repair the bad
   one is not a fix.
6. **Record what you find, do not widen your scope.** A defect outside this list goes in
   your log entry under "Found". The overall lead puts it in the backlog.

## Files in scope

- `ingestion/session_extraction.py`

**Nothing else.** If you conclude the fix belongs in `ingestion/claude_extractor.py` or in
a shared helper, **that is a finding: write it with its evidence and stop.** That file is
`P14e-nri-dedupe`'s file scope and that unit may be in flight.

## Out of scope

- **`tests/`.** The write guard denies it. This unit's tests are a separate assignment
  after the code review.
- **The prompt text itself.** Step 2. Any change to it is an escalation
  ([AGENTS.md](../../AGENTS.md), "Escalate, do not decide alone").
- **Backlog items 112 and 114.** Item 112 is `P14e-nri-dedupe`, in flight. Item 114 is
  `P14g-unit-statement-pages`. Both live in `ingestion/claude_extractor.py`.
- **`cli.py`'s own console output.** It is a separate entry point and no measurement
  above names it. If you find the same defect there, that is a finding.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`. **Run every criterion below with no
`PYTHONIOENCODING` set**, because that is the condition under test.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | `prompt --pass 2` finishes | **exit 0**, and the output holds the two `direction` rules | `-m ingestion.session_extraction prompt extractions/WMT.json --filing 0 --pass 2`, exit code and line count |
| 2 | The old behaviour is reproduced first | the same command at `HEAD` gives **exit 2** and about 19 lines | `git archive HEAD` into a scratch directory. **`git stash` is forbidden** |
| 3 | What the reader sees where the arrow was | quote the two rendered lines, byte for byte | criterion 1's output |
| 4 | All six subcommands finish | 6 of 6 at exit 0 | `plan`, `locate`, `text`, `prompt --pass 1`, `prompt --pass 2`, `check` |
| 5 | No prompt byte moved | the sha256 of `pass1_prompts` and `pass2_prompts` returns is identical before and after | hash both returns in both trees for the same filing |
| 6 | A UTF-8 console is not degraded | with `PYTHONIOENCODING=utf-8`, `→` still prints as `→` | criterion 1's command with the variable set |
| 7 | Nothing sets `PYTHONIOENCODING` in the code | no match | `grep -rn PYTHONIOENCODING ingestion/` |
| 8 | Types | 5 errors in 2 files, or fewer. Name any you removed | the mypy command above |
| 9 | Lint | 4 errors, every one `BLE001`. **Run it after your last edit** | `-m ruff check .` |
| 10 | Census | 64, or fewer | the grep at `docs/2-rules/rules.md:102` |
| 11 | Route | 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` |
| 12 | The failing test set | name every test that changed state and why | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly`, before and after, compared **by name** |

**Every criterion is a measurement, never an opinion.** Criterion 2 exists because a fix
whose "before" was never reproduced is a fix for a defect nobody has seen.

## Citations

- `docs/9-reference/refactor-backlog.md`, item 113, with the 2026-10-06 measurements.
- `AGENTS.md`, "Escalate, do not decide alone" — any change to the LLM boundary.
- `ingestion/session_extraction.py:1021-1050` — `cmd_prompt`, and the `redirect_stdout`
  that already keeps the arithmetic table off stdout.
- `.claude/skills/extract-filing/SKILL.md`, step 3.1 — the step that cannot run today.
- `.claude/agents/programmer.md` — your role card.

## Known open items

- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- **Never mutate a file in this repository**, not even briefly. A spot check left a
  `return []` in `ingestion/claude_extractor.py` on 2026-10-05 with a comment saying it had
  been restored, and check B1 was dead for about ten hours. Work in a scratch copy and
  print the repository file's sha256 before and after.
- The suite takes about 130 seconds.
