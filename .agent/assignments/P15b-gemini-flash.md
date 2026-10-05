---
id: P15b-gemini-flash
phase: 15 — two extraction routes (the user's decision of 2026-10-04: "update the gemini model to 3.8 flash")
agent: programmer
depends_on: [P14b-note-figures]
---

# Route A's default model becomes `gemini-3.8-flash`; the CLI cache key records the model ID, never "(provider default)" (item 82)

## Objective

**The user's decision of 2026-10-04:** "update the gemini model to 3.8 flash".

Route A's default model is `gemini-3.1-pro-preview` (`_DEFAULT_MODELS` in
`ingestion/claude_extractor.py`). The user's key reaches `models/gemini-3.8-flash`
("Gemini 3.8 Flash", input 1,048,576 tokens, output 65,536). So the default changes to
`gemini-3.8-flash`.

Changing the default exposes a second defect. The CLI cache key stores the model as
`"(provider default)"` when `-m` is not given (`cli.py`, `build_extraction_key`). A
cache written under the old default would then match a run under the new default, and
the output would label figures read by `gemini-3.1-pro-preview` as read by
`gemini-3.8-flash` (rule 6). No route A cache exists on this machine today, so no figure
is wrong now. This is backlog item 82.

When this unit is done, the default is `gemini-3.8-flash`, and the cache key holds the
model ID that the run resolves, so a change of default is a cache miss that names both
models.

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-04 at `01ee284`.

| Fact | Command or source | Result |
|---|---|---|
| the model exists for the user's key | `client.models.list()` with `google-genai` | `models/gemini-3.8-flash`, `generateContent`, output limit 65,536 (the code sends `max_output_tokens=65536`) |
| it reads a filing page | page 21 of the Walmart 10-K 2026-01-31, alone, with the code's settings | `713,163` and `(Amounts in millions, except per share data)`; 2.0 s; 599 input, 42 output, 277 thinking tokens |
| a second page | page 22 | `(2,075)`, `794`, `3,027` and `8,022`, the figures printed there |
| the default | `ingestion/claude_extractor.py:141` | `"gemini": "gemini-3.1-pro-preview"` |
| the cache key | `cli.py`, `build_extraction_key` | `model=args.model if args.model is not None else "(provider default)"` |
| the resolver | `_resolve_model(provider, model)` | returns `_DEFAULT_MODELS[provider]` for `None`, stops on `""` |

Re-take the gate numbers at the `P14b-note-figures` commit.

## What to do

1. **The default.** `_DEFAULT_MODELS = {"gemini": "gemini-3.8-flash"}`, with a comment
   naming the user's decision and its date. Delete any comment that names another model
   as the default.
2. **A public resolver.** Rename `_resolve_model` to `resolve_model` (public, same
   signature, same stops) and update its callers. **Reason:** `cli.py` needs the model ID
   without building a resolution, which stops when no key is set.
3. **The cache key** (`cli.py`, `build_extraction_key`). Set `model=resolve_model(
   args.provider, args.model)`. Never the words "(provider default)". **Reason:** rule 6;
   the key must name the model that read the figures.
4. **Docs.** `docs/3-architecture/extraction.md` (about line 52) and
   `docs/8-build/environment.md` (about line 108): the default is `gemini-3.8-flash`, on the
   user's decision of 2026-10-04.

## Files in scope

- `ingestion/claude_extractor.py`: `_DEFAULT_MODELS`, its comment, `_resolve_model` and its callers
- `cli.py`: `build_extraction_key` and its import line
- `docs/3-architecture/extraction.md`
- `docs/8-build/environment.md`
- your journal entry, `.agent/journal/<timestamp>-programmer-p15b-gemini-flash.md`

**Nothing else.**

## Out of scope

- `tests/`: the tester, in `P15b-gemini-flash-tests`. Tests that pass a model ID
  explicitly keep it; tests that assert the default change.
- `tests/test_e2e_abbv.py`: a dev script with its own model string.
- `_call_gemini`'s settings (`temperature=0.0`, JSON reply): unchanged.
- `STATUS.md` and the `extract-filing` skill: the overall lead, after acceptance.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`, except where a fake key is
named. **Make no paid API call.**

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the default | `resolve_provider("gemini", None).model == "gemini-3.8-flash"`; the CLI's provider line names it | `GEMINI_API_KEY=fake-key`, a scratch call |
| 2 | no other default is named | `grep -rn "gemini-3.1-pro-preview" ingestion cli.py config.py api templates docs/3-architecture docs/8-build` → 0 | the grep |
| 3 | the cache key names the model | `build_extraction_key` with no `-m` → `model == "gemini-3.8-flash"`; with `-m gemini-3.5-flash` → that ID; the string `(provider default)` is in no key | a scratch call with a parsed `Namespace` |
| 4 | an old default is a miss that names both models | a key with `model="gemini-3.1-pro-preview"` against the current key → `describe_key_difference` returns `model: cached 'gemini-3.1-pro-preview', now 'gemini-3.8-flash'` | a scratch call |
| 5 | an empty model still stops | `resolve_model("gemini", "")` → `ValueError` naming the default `gemini-3.8-flash` | a scratch call |
| 6 | route B does not move | $28.02 | `cli.py --session-file extractions/WMT.json` |
| 7 | the gates do not get worse | ruff, mypy and census no higher than at the `P14b-note-figures` commit; `GET /` 200 | the gate commands, with the empty-key prefix |
| 8 | every red test is named | expected causes only: tests that assert the old default ID, tests that call `_resolve_model` by name, and the 2 red on purpose | the full suite, failures grouped by cause |
| 9 | not measured here | a whole-filing run on `gemini-3.8-flash` | **not run**; a paid call; the overall lead asks the user |

## Citations

- The user's words, quoted above.
- `docs/2-rules/rules.md`, rule 6: the model that read the figures is an assumption shown
  to the reader.
- `docs/9-reference/refactor-backlog.md`, item 82.

## Known open items

- Nobody has measured `gemini-3.8-flash` on a whole 10-K. Two single pages read correctly.

## Backlog items this unit is NOT fixing

Items 1, 10, 51, 53, 61, 63, 64, 73, 74, 78, 79, 80 in `claude_extractor.py`; item 72
in `cli.py`.
