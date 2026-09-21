---
id: P2b-provider
phase: 2b — one provider, one transport, both labelled
agent: programmer
depends_on: [P2-hygiene]
---

# Make extraction run on this machine, with one named default and the resolution visible in the output

## Objective

**Extraction cannot run on this machine by either provider.** Gemini is unreachable
from this network. Claude is reachable, but only through a Microsoft Foundry gateway,
and `ingestion/claude_extractor.py:352` builds a plain `anthropic.Anthropic(api_key=…)`
which cannot reach it. `_resolve_provider` at `:830` then refuses to start unless
`ANTHROPIC_API_KEY` is in the environment, which it is not and will not be.

Underneath that sits backlog item 13: the provider is chosen by **how many PDFs you
upload**. `api/routes_valuation.py:46` calls `extract_financials`, which defaults to
`"gemini"`. Line 55 calls `extract_multi_year`, which defaults to `"claude"`. Neither
passes a provider.

When this unit is done: one default provider, named once, in `config.py`. Foundry used
as a **transport** when one is configured. And the resolved provider, model and
transport visible in both outputs, because which model read the filing is an assumption
and [rule 6](../../docs/2-rules/rules.md) says an assumption is labelled.

## What is already true — verify, do not redo

**Measured by the orchestrator at `4f50fd8`, 2026-09-20, by running it.** Every row
below is an executed result, not a documentation claim. If one disagrees when you run
it, **stop and report the disagreement.**

| Fact | Evidence |
|---|---|
| `ANTHROPIC_FOUNDRY_BASE_URL` is set in the environment; `ANTHROPIC_FOUNDRY_API_KEY`, `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` are **not** | the environment |
| the installed `anthropic` **1.7.0** exports `AnthropicFoundry` | `dir(anthropic)` |
| `AnthropicFoundry` reads `base_url` from `ANTHROPIC_FOUNDRY_BASE_URL` with no argument | its `__init__` docstring |
| it needs **either** `api_key` **or** `azure_ad_token_provider`, and raises if given neither | its `__init__` |
| the gateway accepts an **Entra ID bearer token** on scope `https://cognitiveservices.azure.com/.default` | HTTP 200 |
| scope `https://ai.azure.com/.default` is **rejected**, and the gateway names the right audience in its own 401 | HTTP 401 |
| `claude-opus-5` and `claude-haiku-4-5` are both served | HTTP 200, `served=claude-opus-5` |
| **native PDF ingestion works through the gateway** | a one-line PDF reading `Total net revenues 4321`; the model returned `4321` |
| the whole path works through the SDK, not only raw HTTP | `AnthropicFoundry(azure_ad_token_provider=lambda: tok)` returned `4321` from the same PDF |
| `az account get-access-token --scope https://cognitiveservices.azure.com/.default` succeeds | the user is signed in |
| **`azure-identity` is not installed** | `import azure.identity` → `ModuleNotFoundError` |
| there are **no PDFs on this machine**; `10K_filings/` holds one stray `.DS_Store` | `find 10K_filings -type f` |

My probe scripts are at `c:/tmp/probe_sdk.py`, `c:/tmp/probe_pdf.py` and
`c:/tmp/make_pdf.py`, and the test PDF is `c:/tmp/probe.pdf`. **Read them; they are the
shortest description of the working call.** Do not copy them into the repository.

## Decisions already taken — implement, do not re-open

The user chose these on 2026-09-20. They are not yours to revisit.

| Decision | Value |
|---|---|
| default provider | **`"claude"`** |
| default Claude model | **`"claude-opus-5"`** |
| credential | **Entra ID via `az login`**, not an API key |

## What to do

1. **Add `azure-identity` to `requirements.txt`.** It is the only supported way to
   produce a refreshing Entra token. Install it into the venv and record the version in
   your entry.

2. **Name the default once, in `config.py`.** A provider constant and the Entra scope
   constant. Nothing else reads a provider default after this.

3. **Make Foundry a transport, not a third provider.**

   `Provider` stays `Literal["claude", "gemini"]`. **The model is still Claude.** What
   changes is which client object carries the request:

   - a Foundry base URL or resource is configured → `AnthropicFoundry`, with
     `azure_ad_token_provider`;
   - otherwise → `anthropic.Anthropic`, with `ANTHROPIC_API_KEY`.

   Build the token provider with
   `azure.identity.get_bearer_token_provider(DefaultAzureCredential(), SCOPE)`.
   **Do not shell out to `az`.** A subprocess call from library code is untestable and
   breaks wherever the CLI is absent.

4. **Fix the stop in `_resolve_provider`.** Today it demands `ANTHROPIC_API_KEY` and
   raises if it is empty. That would refuse a working Foundry credential. The stop must
   fire when **no credential of any kind** resolves, and it must name what would fix it
   — the environment variable **or** `az login`. Keep it a `ValueError`; typed
   exceptions are phase 5.

   **This is still [rule 3](../../docs/2-rules/rules.md).** Do not let a missing
   credential produce a client that fails later with an unrelated message.

5. **Pass `provider` explicitly at both boundaries.** `api/routes_valuation.py:46` and
   `:55` pass none today, which is the whole of backlog item 13. The CLI already has a
   `--provider` flag; make its default come from `config.py` rather than a literal.

6. **Make the resolution visible in both outputs.** [Rule 6](../../docs/2-rules/rules.md).

   - **CLI:** `ingestion/claude_extractor.py:878` already prints
     `Provider: X | Model: Y`. Add the transport, and say where the credential came
     from. One line.
   - **Web:** carry the resolved provider, model and transport to the result page and
     show them, next to the other assumptions. A figure read by `claude-opus-5` through
     a company gateway and the same model through the public API must be
     distinguishable by the reader.

   **Never print or log the token.** Name the credential *source*, not its value.

7. **Record the setup in `docs/8-build/environment.md` section 3.** It owns API keys
   and it now describes something that is not a key. Give the scope, the `az login`
   step, and the 401 message the gateway returns for the wrong audience — that message
   is the fastest diagnosis available and it should not have to be rediscovered.

## Files in scope

- `requirements.txt` — one line.
- `config.py` — two constants.
- `ingestion/claude_extractor.py` — the provider resolution, the Claude client
  construction, the two public defaults, and the existing print line at `:878`.
- `api/routes_valuation.py` — **`_extract_from_files`, the result context, and the two
  `TemplateResponse` calls that render `valuation_result.html`.** Nothing else in this
  file. (The third and fourth scope item were added in round 2; see the amendment at
  the end of this file.)
- `cli.py` — **the `--provider` default only.**
- `templates/` — the result page only.
- `docs/8-build/environment.md` — section 3 only.

**Nothing else.**

## Out of scope

- **`tests/`** — your write guard denies it.
- **`analysis/` and `models/`** — untouched. 93 tests depend on them.
- **The Gemini path.** Leave it working. It is unreachable from this network, not
  broken, and someone on another network will use it.
- **Typed exception classes and the blanket catches** — backlog item 8, phase 5. Do not
  add a new `except Exception`.
- **The pipeline duplication** between `cli.py` and `api/` — backlog item 7. You touch
  one line of `cli.py`.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | one provider default, in one place | 1 definition, and `grep` finds no other literal default | `grep -rn 'provider: Provider = \|DEFAULT_EXTRACTION_PROVIDER' config.py ingestion/ api/ cli.py` |
| 2 | **a real extraction completes through the gateway** | the figure is read off the PDF | run the pipeline against `c:/tmp/probe.pdf`; paste the output |
| 3 | the resolved provider, model and transport appear in the CLI output | all three shown | criterion 2's output |
| 4 | the same three appear on the result page | all three shown | start the app, run a valuation, paste the rendered block |
| 5 | a missing credential stops and names both remedies | raises, message names the variable **and** `az login` | run with the Foundry URL unset and no key; paste the message |
| 6 | the suite is unchanged | **1 failed, 92 passed** — the failure is `test_dcf_rule3_red.py` | `.venv/Scripts/python.exe -m pytest -q` |
| 7 | lint unchanged | 5 errors, all `BLE001` | `.venv/Scripts/python.exe -m ruff check .` |
| 8 | types not worse | ≤ 33 errors in ≤ 4 files | the mypy gate |
| 9 | the rule-3 census did not rise | ≤ 116 | the grep in `docs/2-rules/rules.md` |
| 10 | no token is printed or logged | 0 hits | `grep -rn "token" ingestion/ api/ cli.py` — every hit is a provider object or a comment, never a value |

**Criterion 2 is the unit.** Everything else is bookkeeping around it. Until a real
extraction completes, nothing here is proven.

`c:/tmp/probe.pdf` is a one-line PDF and will not populate a full `FinancialStatements`.
**That is expected.** Criterion 2 asks that the call completes and the model returns
what is on the page — not that a valuation runs. Say plainly in your entry which fields
came back and which did not.

## Citations

- `docs/9-reference/refactor-backlog.md` item **13** — the evidence, and the Foundry
  facts.
- `docs/2-rules/rules.md` rule 3 (stop, never guess), rule 5 (the filing is the only
  source of statement data) and rule 6 (an assumption is labelled).
- `docs/2-rules/llm-boundary.md` — **read it. You are touching `ingestion/`.**
- `docs/3-architecture/extraction.md` — the two passes and the providers.
- `docs/8-build/environment.md` section 3 — what you are rewriting.

## Known open items

- **This unit changes no field the model is asked to produce**, so it is not a change to
  the LLM boundary and needs no escalation. **If you find yourself adding or removing a
  field in a prompt schema, stop** — that is an escalation, per `AGENTS.md`.

- `ingestion/claude_extractor.py:479` subtracts D&A inside the parser (backlog item
  10), and `:795` holds a blanket catch (item 8). **Both are in the file you are
  editing and neither is yours.** Say in your entry that you saw them.

- PDF input is a **beta** feature on Microsoft Foundry, per Anthropic's platform
  availability table. It works today — I measured it. Note it in
  `docs/8-build/environment.md` so a future failure is diagnosed in one step rather
  than three.

## Backlog items this unit is NOT fixing

- **Item 1** — the 116 zero-default sites, 49 of which are in the file you are editing.
- **Item 5** — the module-global extraction cache in `api/routes_valuation.py`.
- **Item 6** — falsy treated as missing, five times in `api/routes_valuation.py`.
- **Item 7** — the duplicated pipeline.
- **Item 8** — the blanket catches, including `:795` in your file.
- **Item 10** — the D&A subtraction in the parser.
- **Item 20** — the NaN beta.

---

# Round 2 — orchestrator amendment, 2026-09-21

Review `.agent/journal/2026-09-21T0130-code_reviewer-p2b-provider.md` returned
`changes_requested` with one `major`. **Answer every finding by its number in your
entry.** You may dispute one; a dispute needs a citation.

## The assignment was wrong, and that is mine to fix

Your entry said criterion 4 was unreachable because `/` and `/assumptions` are the route
to the result page. **The reviewer disproved that by execution.** `POST /valuation` is
its own route, and `api/routes_valuation.py:148-154` holds a cache-miss branch that runs
the whole pipeline. On a scratch copy with **only** the two `valuation_result.html`
calls repaired:

```
GET  /          -> 500   (still broken, genuinely out of scope)
POST /valuation -> 200,  with the full Provider/Model/Transport/Credential block
```

**Those two calls are now in scope.** The other two — `api/routes_upload.py:42` and
`api/routes_valuation.py:114` — stay out, and unit `P5-web-routes` takes them.

The reviewer also spotted that `P5-web-routes` lists `depends_on: [P2b-provider]`, so it
cannot supply this unit's evidence. Correct, and that is why the scope moved here
instead.

## What to do

**F1 · `major` · criterion 4.** Repair the two `valuation_result.html`
`TemplateResponse` calls to the `starlette` 1.6.0 signature, `(request, name, context)`.
Then prove criterion 4 the way the reviewer did: `POST /valuation` returns **200** and
the body carries the resolved provider, model and transport. Paste the status line and
the rendered block.

Leave `GET /` and `GET /assumptions` broken. They are `P5-web-routes`.

**F2 · `minor`, and treat it as higher than that.** `ingestion/claude_extractor.py:987`
uses `urlsplit(base_url).netloc`, which **carries userinfo**. The reviewer demonstrated
that a base URL of `https://user:supersecret@gw.example.net/x` produces the label
`Microsoft Foundry gateway (user:supersecret@gw.example.net)` — printed to stdout and
rendered into the result page.

**That is a credential printed in the output**, which is exactly what criterion 10
exists to prevent. The fix is one word: `.hostname`. Add a case to your scratch proof
showing a userinfo URL no longer leaks.

**F3 · `minor`.** The page's label is re-derived from the environment at render time
rather than recorded from the extraction that produced the figures. So the page can
report a transport that did not run — an environment change between extraction and
render is enough. [Rule 4](../../docs/2-rules/rules.md) asks that a number be traceable
to its inputs, and the transport is part of that trace.

Record the resolution **at the extraction** and carry it to the page. If that cannot be
done inside this unit's scope, say exactly which file would need to change and stop;
that is an escalation, not a widening.

**F4 · `note`.** The module-level `_ENTRA_TOKEN_PROVIDER` global. It breaks no rule.
Answer it in one line — keep it, or say why you are changing it. Do not redesign.

## Revised done-criteria

Criterion 4 replaces the original. Everything else stands.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 4 | the three labels appear in a response the route returned | **`POST /valuation` → 200**, all three in the body | `starlette.testclient.TestClient`; paste the status and the block |
| 11 | a userinfo base URL leaks nothing | the label shows the host only | your scratch proof |
| 12 | the type gate still improves, and adds nothing | < 33, and `comm -13` against the baseline set is empty | the reviewer's method, in its entry |

## What has not changed

The reviewer confirmed by execution, on the tree you left: criterion 2 reproduces with
its own numbers (`6174` and `2718` printed, `6174.0` and `2718.0` extracted); the mypy
set is a strict subset with nothing added; the suite is `1 failed, 105 passed` on both
trees; lint is 5 `BLE001` on both; the census is `116 → 116`; and the missing-credential
stop names both remedies before any network call.

**Your unasked change to `_call_claude` was judged right** — it stops rather than falls
back, and criterion 2 could not have passed without it. Keep it.
