---
id: P14b-reasoning
phase: 14 — the Pass 1 role (rule 1 option 0, the user's decision of 2026-10-03)
agent: programmer
depends_on: [P14b-pass2-units]
---

# Route A asks Claude to reason before it answers, at a named effort, with room to finish; the reasoning setting is shown; fix item 81

## Objective

Rule 1 option 0 allows the model to reason before it answers, and no code may read the
reasoning. Route A's `_call_claude` sends no `thinking` and no effort, and caps the
response at `max_tokens=8096`. On `claude-opus-5` (the default model, `_DEFAULT_MODELS`)
the API then thinks adaptively at effort `high` by default, and the thinking tokens
count toward the same 8,096. The code already met this: its comment says a `thinking`
block arrives ahead of the answer on some requests. So a long Pass 1 answer can reach the
cap and stop ("hit the 8,096-token output ceiling"), and the output never says that the
model reasoned or at what effort (rule 6).

When this unit is done, route A sends `thinking={"type": "adaptive"}` and an effort
named once in `config.py`, through a streamed request with room for the thinking and
the answer. It still reads only the text blocks. Both pages and the CLI show the
reasoning setting beside the provider, model and transport. This changes no model
behaviour on `claude-opus-5` today. It makes the setting explicit and visible, and it
removes the cap that thinking can reach.

The unit also fixes backlog item 81, found in the overall lead's review of
`P14b-pass2-units`.

## What is already true — verify, do not redo

Measured by the overall lead at `21125ed` (the `P14b-pass2-units` commits), macOS.

| Fact | Command | Result |
|---|---|---|
| test gate | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 1001 passed |
| full suite | the same without `--ignore-glob` | 2 failed (the 2 red on purpose), 1001 passed |
| lint, types, census, route | the commands in `P14b-pass2-units.md` | ruff 4, mypy 9 in 4 files, census 65, `GET /` 200 |
| Walmart, route B | `.venv/bin/python -m ingestion.session_extraction check extractions/WMT.json` | exit 0; the file is now `session-extraction-v4` |
| Walmart, end to end | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json` | PV of terminal value 214,819M; implied price $28.02 |
| item 81 | a copy of `extractions/WMT.json` with the 2025 "Other gains and losses" item's `amount` set to 795, then `session_extraction check <copy>` | exit 2, one problem listed, but the summary line prints `4 checked, 2 found, 2 not confirmed` |

**The API facts for this unit, from Anthropic's current API reference** (the overall
lead read them; do not use another form):

- On `claude-opus-5`, `thinking={"type": "adaptive"}` is the form to send. A request that
  omits `thinking` also runs adaptive.
- `thinking={"type": "enabled", "budget_tokens": N}` returns HTTP 400 on this model. Do
  not send it.
- `temperature`, `top_p` and `top_k` return HTTP 400 on this model. Do not send them.
- Effort is `output_config={"effort": "<level>"}`, one of `low`, `medium`, `high`,
  `xhigh`, `max`. It is inside `output_config`, not a top-level parameter. On
  `claude-opus-5` the default is `high`.
- Thinking blocks come back with empty text by default (`display` is `"omitted"`). Thinking
  tokens count toward `max_tokens`.
- A large `max_tokens` needs a streamed request, or the Python SDK refuses it before
  sending, to avoid an HTTP timeout. Use `client.messages.stream(...)` as a context
  manager and `stream.get_final_message()`; the returned message has the same
  `content`, `stop_reason` and `usage` as `messages.create` returns.

## What to do

1. **`config.py`.** Add `EXTRACTION_EFFORT: Final = "high"`, with a comment in the form
   of the other assumptions there: it is an assumption (rule 6), what it controls (how
   much the model reasons before it answers, and so the output tokens paid for), why
   `high` (the API default for `claude-opus-5`, so this unit moves no model behaviour,
   and extraction is the step every figure depends on), and that it is shown in the
   output.
2. **`_call_claude`** (`ingestion/claude_extractor.py`). Send `thinking={"type":
   "adaptive"}` and `output_config={"effort": config.EXTRACTION_EFFORT}`. Replace
   `max_tokens=8096` with one module constant, `_CLAUDE_MAX_TOKENS = 64000`, used both in
   the request and in the "output ceiling" stop message (today the message repeats the
   literal `8096`). Make the request through `client.messages.stream(...)` and
   `get_final_message()`. Keep every check after the call as it is: text blocks
   selected by `type == "text"`, the stop on no text block, the stop on `stop_reason ==
   "max_tokens"`. Read no field of a thinking block, print none, and log none (rule 1
   option 0: no code reads the reasoning).
3. **The reasoning label** (rule 6). Add `reasoning_label: str` to `ProviderResolution`
   (a label, like its other fields; no default). Set it at every constructor:
   - route A, Claude (each `return ProviderResolution(` in `_resolve_claude`):
     `f"adaptive thinking, effort {config.EXTRACTION_EFFORT!r} (config.EXTRACTION_EFFORT)"`;
   - route A, Gemini (`_resolve_gemini`): `"the provider's default; this code sets no
     thinking for Gemini"`. Do not change `_call_gemini`;
   - route B (`ingestion/session_extraction.py`, the resolution built for a session
     file): `"as the Claude Code session ran; not set by this code"`.
   `describe_resolution` adds `Reasoning: <label>` after the model. The two templates
   add one row, `Reasoning`, after the `Model` row.
4. **Item 81** (`_pass2_item_failures`). Count the items not confirmed from the items
   themselves: record, for each item, whether any of its checks failed, and count those.
   Never match a description against a message. The summary must read `4 checked, 3
   found, 1 not confirmed` for the item 81 copy in the table above.
5. **Tidy.** Remove the run of blank lines that `P14b-pass2-units` left where
   `_whitespace_normalised` used to be (before `unit_statement_on_page`). Change nothing
   else there.
6. **Docs.** `docs/2-rules/llm-boundary.md`: state that option 0 is in force for route
   A from this unit, how (adaptive thinking, effort from `config.EXTRACTION_EFFORT`), and
   that no code reads a thinking block. `docs/3-architecture/extraction.md`: the call
   parameters of `_call_claude`, the 64,000 ceiling, and the reasoning label.

## Files in scope

- `config.py`
- `ingestion/claude_extractor.py`
- `ingestion/session_extraction.py`: the `ProviderResolution(...)` call only
- `templates/assumptions.html`: one row
- `templates/valuation_result.html`: one row
- `docs/2-rules/llm-boundary.md`
- `docs/3-architecture/extraction.md`
- your journal entry, `.agent/journal/<timestamp>-programmer-p14b-reasoning.md`

**Nothing else.** The build team's "never write `docs/`" rule does not apply to the two
docs files listed here.

## Out of scope

- `tests/`: the tester repairs the `ProviderResolution(...)` fixtures (4 files) and the
  `describe_resolution` assertion, in `P14b-reasoning-tests`.
- `_call_gemini`: Gemini's thinking settings are not verified here. A later unit.
- Rule 1 option B (a Pass 1 figure from a note or MD&A): the overall lead holds it for a
  user decision on how its unit is checked. Do not change the Pass 1 prompt.
- `cli.py`: it prints `describe_resolution`, so it shows the label with no change.
- The CLI cache marker: `ProviderResolution` is not in the pickle (`cli.py` pickles the
  marker, the key, the statements and the items).

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. **Make no paid API call.**

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the request carries the reasoning setting | the stub client receives `thinking == {"type": "adaptive"}`, `output_config == {"effort": "high"}`, `max_tokens == 64000`, and no `temperature`, `top_p`, `top_k` or `budget_tokens` anywhere in the call | a scratch script: replace `_build_claude_client` with a stub whose `messages.stream` records its keyword arguments and returns a stream whose `get_final_message()` gives one text block `{}` and `stop_reason "end_turn"`; call `_call_claude` |
| 2 | a thinking block is not read | the stub message `[thinking block with text "SECRET", text block "{\"a\": 1}"]` → `_call_claude` returns `"{\"a\": 1}"`; `SECRET` appears in no return value and no printed output | the same stub, stdout captured |
| 3 | the stops still hold | a stub with only a thinking block → the "no text block" `ValueError`; a stub with `stop_reason "max_tokens"` → the ceiling `ValueError`, naming 64,000 | the same stub |
| 4 | the effort is named once | 1 definition; `_call_claude` reads it | `grep -rn "EXTRACTION_EFFORT" config.py ingestion/` |
| 5 | the label is shown | `describe_resolution` prints `Reasoning: adaptive thinking, effort 'high' (config.EXTRACTION_EFFORT)` for route A Claude; the CLI on Walmart prints `Reasoning: as the Claude Code session ran; not set by this code`; both pages show a `Reasoning` row | a scratch call of `_resolve_claude` with a fake key; `cli.py --session-file extractions/WMT.json`; `TestClient` on `/assumptions` and `/valuation` with the Walmart session file, grep the HTML |
| 6 | item 81 is fixed | the item 81 copy prints `4 checked, 3 found, 1 not confirmed` and still exits 2 with one problem; the clean Walmart file still prints `4 checked, 4 found, 0 not confirmed` | `session_extraction check` on each |
| 7 | Walmart does not move | stages 1 to 10 identical to the run at `21125ed`, except the new `Reasoning` text and the PV of the terminal value within 1 (item 70); implied price $28.02 | `cli.py --session-file extractions/WMT.json`, diffed |
| 8 | the gates do not get worse | ruff 4 or fewer, mypy 9 or fewer, census 65 or fewer, `GET /` 200 | the gate commands |
| 9 | every red test is named | expected causes only: `ProviderResolution(...)` without `reasoning_label` (4 test files), the `describe_resolution` line assertion, tests that stub `client.messages.create` for `_call_claude`, and the 2 red on purpose | the full suite, failures grouped by cause |
| 10 | not measured here | a real route A call through the Foundry gateway with these parameters | **not run.** It is a paid call. Write in your entry that it is not measured; the overall lead asks the user |

## Citations

- `docs/2-rules/rules.md`, rule 1, option 0 (the user's decision of 2026-10-03), and rule 6.
- `ingestion/claude_extractor.py`, `_call_claude`: the comment on the `thinking` block.
- `docs/9-reference/refactor-backlog.md`, item 81.

## Known open items

- Route A has not run through the gateway with `output_config` or with a streamed
  request. If the gateway rejects either, every route A extraction fails with an API
  error. Criterion 10 is the user's paid check.
- Rule 1 option B waits for the user's decision on how a Pass 1 figure from a note or
  MD&A is checked for its unit.

## Backlog items this unit is NOT fixing

Items 1, 10, 51, 53, 61, 63, 64, 73, 74, 78, 79, 80 (all in `claude_extractor.py`), and
item 72 (`cli.py`). Item 81 is in scope.

## Handoff

### Commits
- `49cf0f5`: `P14b-reasoning: route A adaptive thinking and effort, reasoning label, item 81 fix`
- `158f25d`: `P14b-reasoning tester: repair ProviderResolution fixtures, lock streaming thinking and item 81`

### Verdicts
- Programmer: `complete` (round 1), entry: `.agent/journal/2026-10-04T1548-programmer-p14b-reasoning.md`
- Code reviewer: `approved` (round 1), entry: `.agent/journal/2026-10-04T1604-code_reviewer-p14b-reasoning.md`
- Tester: `pass` (round 1), entry: `.agent/journal/2026-10-04T1606-tester-p14b-reasoning.md`

### Gates
- Test gate: 1021 passed (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"`)
- Full suite: 2 failed (the known two), 1021 passed (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q`)
- Lint: 4 errors, all `BLE001` (`.venv/bin/python -m ruff check .`)
- Types: 9 errors in 4 files (`.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports`)
- Rule 3 census: 65 (`grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" '--include=*.py' models analysis api ingestion | wc -l`)
- Web root route: HTTP 200 (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -c "from starlette.testclient import TestClient; from app import app; print(TestClient(app).get('/').status_code)"`)
- Guard check: 48/48 correct (`.venv/bin/python .claude/check_guard.py`)
- Walmart Route B check: exit 0; 89 of 89 printed lines found; 4 of 4 Pass 2 items confirmed; `Reasoning: as the Claude Code session ran; not set by this code` printed (`.venv/bin/python -m ingestion.session_extraction check extractions/WMT.json`)
- Walmart end-to-end: stages 1 to 10 match `21125ed`; PV of terminal value 214,819M; implied price $28.02; downside -73.1% (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python cli.py --session-file extractions/WMT.json`)

### Findings and notes
- Criterion 10 (real route A call through Foundry gateway): not run because it is a paid API call; left for overall lead / user verification.

### Questions for the overall lead
None.


## Overall lead review

**Verdict: `accepted`**, 2026-10-04, at `158f25d`, by the overall lead.

**Scope.** `49cf0f5` touches only the files in scope and two journal entries. `158f25d`
touches `tests/`, its assignment, its entry and the journal index.

**Re-measured** (keys empty, sockets blocked where a call could start):

| # | Result |
|---|---|
| 1 | stub client: `thinking={"type": "adaptive"}`, `output_config={"effort": "high"}`, `max_tokens=64000`; no `temperature`, `top_p`, `top_k` or `budget_tokens`; `messages.create` not used |
| 2 | a thinking block holding `SECRET` and a text block: the return is the text only; `SECRET` in no return value and no printed output |
| 3 | only a thinking block → the "no text block" stop; `stop_reason "max_tokens"` → the stop naming 64,000 |
| 4 | `EXTRACTION_EFFORT`: 1 definition in `config.py`; read by `_call_claude` and the three Claude labels |
| 5 | CLI on Walmart: `Reasoning: as the Claude Code session ran; not set by this code`; `GET /assumptions` and `POST /valuation` with the Walmart session file: 200, and each shows the `Reasoning` row with that text |
| 6 | item 81: the 795 copy prints `4 checked, 3 found, 1 not confirmed`, exit 2, 1 problem; the clean file `4 checked, 4 found, 0 not confirmed`, exit 0 |
| 7 | Walmart: identical to the `P14b-pass2-units` run except the `Reasoning` text and the file path; $28.02 |
| 8 | gate 1021 passed; full 2 failed (the known two); ruff 4; mypy 9 in 4 files; census 65; guard 48/48 |
| 10 | not measured, and it cannot be: the user has no Anthropic key |

**Findings.**

- **F1, note.** No test checks the `Reasoning` row on the two web pages; only the
  overall lead's run above shows it. Sent to `P15a-two-routes`, whose tester locks the
  Gemini label there.
- **F2, note, the user's later decision.** The user decided "1a" after this unit
  started: route A becomes Gemini only. `P15a-two-routes` deletes this unit's streamed
  `_call_claude`, `_CLAUDE_MAX_TOKENS`, `config.EXTRACTION_EFFORT` and the three Claude
  labels. The reasoning label on `ProviderResolution`, the Gemini and route B labels,
  the two template rows and the item 81 fix stay.
