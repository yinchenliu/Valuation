---
agent: programmer
assignment: P2b-provider
round: 1
status: partial
files_touched: [requirements.txt, config.py, ingestion/claude_extractor.py, api/routes_valuation.py, cli.py, templates/valuation_result.html, docs/8-build/environment.md]
verdict: —
---

# P2b-provider — one provider default, Foundry as a transport, the resolution labelled

> Opened before the first command. Filled as each result landed.

**Extraction now runs on this machine.** A real two-pass extraction completed through
the Foundry gateway on an Entra ID credential, and the figure it returned tracks the
figure printed on the page — proved by changing the page and re-running.

**Status is `partial` for exactly one reason: done-criterion 4 cannot be measured over
HTTP.** The web app returns **HTTP 500 on every page, on the unmodified tree, before
my change** — starlette 1.6.0 removed the `TemplateResponse(name, context)` signature
this repository uses at all four call sites. Three of those four are outside my Files
in scope, so I did not widen scope to fix it. Full evidence, and the one-line fix,
under "Criterion 4". Everything else in the unit passes.

---

## Verification of "What is already true" — run before any edit

| Row in the assignment | Re-measured result |
|---|---|
| `ANTHROPIC_FOUNDRY_BASE_URL` set; `ANTHROPIC_FOUNDRY_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` unset | **agrees** — `SET len=62` / `UNSET` ×3. `ANTHROPIC_FOUNDRY_RESOURCE` also UNSET |
| `anthropic` 1.7.0 exports `AnthropicFoundry` | **agrees** — `anthropic 1.7.0`, `True` |
| `AnthropicFoundry` reads `base_url` from `ANTHROPIC_FOUNDRY_BASE_URL` | **agrees** — read from `inspect.getsource(anthropic.AnthropicFoundry.__init__)` |
| needs either `api_key` or `azure_ad_token_provider` | **agrees** — `raise AnthropicError("Missing credentials…")` when both are None |
| gateway accepts an Entra token on `…cognitiveservices.azure.com/.default` | **agrees** — HTTP 200 |
| `claude-opus-5` served | **agrees** — `served model: claude-opus-5` |
| native PDF ingestion works through the gateway | **agrees** — returned `4321` |
| the whole path works through the SDK | **agrees**, and through `azure-identity` with no `az` shell-out |
| `azure-identity` not installed | **agrees** — `ModuleNotFoundError: No module named 'azure'` |

### Three disagreements, reported not worked around

1. **The probe scripts are not on disk.** `c:/tmp/probe_sdk.py`, `c:/tmp/probe_pdf.py`,
   `c:/tmp/make_pdf.py` and `c:/tmp/probe.pdf` do not exist. `ls -la /c/tmp` lists 90
   files and none of them are these. I rebuilt `make_pdf.py` and `probe.pdf` from the
   description in the assignment and re-derived the working call myself. My PDF is
   **598 bytes**, not 597; `pdfplumber` reads `'Total net revenues 4321'` off it, which
   is the property that matters.

2. **Done-criterion 6 expects `1 failed, 92 passed`.** The tree measures
   **`1 failed, 105 passed`** *before I touched anything*. The assignment was written
   against `4f50fd8`; `HEAD` is `852f74b`, and `STATUS.md` at `81816be` also says 105.
   The 92 is stale. I held **1 failed / 105 passed** as the baseline.

3. **The web app is dead on this machine, before my change.** Not mentioned anywhere in
   the assignment or `STATUS.md`. See "Criterion 4".

### The working call, re-derived (scratch, not in the repository)

`c:/tmp/probe_sdk.py` — `get_bearer_token_provider(DefaultAzureCredential(), SCOPE)`
passed as `azure_ad_token_provider`, no `api_key`, no `resource`:

```
base_url: https://apm-use-claudecode-pd.azure-api.net/foundry/anthropic/
model returned: 4321
served model: claude-opus-5 | tokens in/out: 1617 4
```

**`azure-identity` installed: 1.25.3**, pulling `azure-core` 1.41.0, `msal` 1.39.0,
`msal-extensions` 1.3.1 and `PyJWT` 2.14.0.

---

## What I did

`config.py` gains two `Final` constants — `DEFAULT_EXTRACTION_PROVIDER = "claude"` and
`ENTRA_TOKEN_SCOPE`. `ingestion/claude_extractor.py` gains a frozen
`ProviderResolution` dataclass and a public `resolve_provider`, which decides provider,
model, **transport** and **credential kind** from the environment alone — no token, no
network call — and raises naming both remedies when nothing resolves. `_call_claude`
now builds an `AnthropicFoundry` with an Entra token provider when a gateway is
configured and a plain `anthropic.Anthropic` otherwise. `provider`, `model` and
`api_key` were replaced throughout by the single typed `resolution`, which took the
API key out of six signatures. Both public entry points default to the config
constant, so the number of PDFs uploaded can no longer decide which model reads them.
The CLI prints all four labels on one line, and the result page shows them in their own
table.

One change was not in the assignment and was forced by criterion 2: `_call_claude` read
`response.content[0].text`, and `claude-opus-5` returns a `ThinkingBlock` ahead of its
answer on some requests. It is recorded under "Decisions" with the traceback that
forced it.

---

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | one provider default, in one place | **pass** | `grep -rn 'provider: Provider = \|DEFAULT_EXTRACTION_PROVIDER' config.py ingestion/ api/ cli.py` → **1 definition** (`config.py:29`). All 11 other hits are *references* to it or prose naming it; **no second literal**. Full output below |
| 2 | **a real extraction completes through the gateway** | **pass** | both passes ran; `revenue: 4321.0` off the page. Output below, and the page-changed re-run that proves the figure is not a default |
| 3 | provider, model and transport in the CLI output | **pass** | criterion 2's first line shows all three **plus the credential source** |
| 4 | the same three on the result page | **blocked — not by this unit** | the page renders all four correctly (block pasted below), but it cannot be reached over HTTP: **the unmodified tree returns HTTP 500 on `GET /`**. starlette 1.6.0, 4 call sites, 3 outside my scope |
| 5 | a missing credential stops and names both remedies | **pass** | `ValueError` naming `ANTHROPIC_API_KEY` **and** `az login`. Message below |
| 6 | the suite is unchanged | **pass** | `1 failed, 105 passed` — identical set before and after; the failure is `test_dcf_rule3_red.py`. (Criterion says 92; the tree said 105 before I touched it — disagreement 2 above) |
| 7 | lint unchanged | **pass** | `Found 5 errors.`, all `BLE001`, the same five |
| 8 | types not worse | **pass, and better** | **22 errors in 4 files**, against 33. A strict **subset**: 11 removed, **0 added** — `diff` of the normalised output below |
| 9 | the rule-3 census did not rise | **pass** | **116**, unchanged. No added line matches the census pattern |
| 10 | no token is printed or logged | **pass** | `grep -rn "token" ingestion/ api/ cli.py --include=*.py \| wc -l` → **34**; every one is a comment, a docstring, a `max_tokens` parameter, a token **count**, a `Literal` label or the provider object — **never a value**. Proved by execution too: `grep -cE "sk-ant\|Bearer \|eyJ[A-Za-z0-9_-]{10,}"` → **0** over the extraction stdout, and `re.search` → **False** over the rendered HTML |

### Criterion 1 — the full grep

```
config.py:29:DEFAULT_EXTRACTION_PROVIDER: Final = "claude"        <- the one definition
ingestion/claude_extractor.py:54:   (module docstring, prose)
ingestion/claude_extractor.py:1073: f"provider='{config.DEFAULT_EXTRACTION_PROVIDER}'."   (error text)
ingestion/claude_extractor.py:1126: provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER
ingestion/claude_extractor.py:1145: (docstring)
ingestion/claude_extractor.py:1180: provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER
ingestion/claude_extractor.py:1204: (docstring)
api/routes_valuation.py:56:  provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER
api/routes_valuation.py:226: extraction = resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)
cli.py:94, 98, 100:          comment, argparse default, help text
```

Before this unit the two public defaults were `"gemini"` (`extract_financials`) and
`"claude"` (`extract_multi_year`), and `api/routes_valuation.py` passed neither — which
is the whole of backlog item 13. **Both are now the same constant, and both call sites
pass it explicitly.**

### Criterion 2 — a real extraction, through the gateway

`c:/tmp/run_probe_extraction.py` calls the repository's own `extract_financials`
against `c:/tmp/probe.pdf`:

```
  Provider: CLAUDE  |  Model: claude-opus-5  |  Transport: Microsoft Foundry gateway
  (apm-use-claudecode-pd.azure-api.net)  |  Credential: Entra ID token via
  DefaultAzureCredential (`az login`), scope https://cognitiveservices.azure.com/.default
  PDF: probe.pdf (0.0 MB)
  [Pass 1] Extracting financials (all years) + B/S...
  [Pass 1] Tokens — input: 3,866  output: 376
  [Pass 1] Validation errors — sending feedback (retry 1/2)...
  [Pass 1] Retry tokens — input: 2,858  output: 406
  [Pass 2] Analyzing non-recurring items ...
  [Pass 2] Tokens — input: 2,673  output: 14
  [Pass 2] No non-recurring items identified

=== WHAT CAME BACK ===
years: [0]
income_statements: 1 | balance_sheets: 0 | cash_flow_statements: 1 | non-recurring items: 0
IncomeStatement — fields that CAME BACK non-zero: {'revenue': 4321.0}
IncomeStatement — fields left at 0.0 (not on the page): ['year', 'cost_of_revenue',
  'sga', 'rd_expense', 'depreciation_amortization', 'other_operating_expense',
  'interest_expense', 'interest_income', 'other_non_operating', 'tax_expense',
  'diluted_shares_outstanding']
CashFlowStatement — non-zero: {'net_income': 4321.0, 'other_operating_activities': -4321.0}
```

**Plainly, which fields came back and which did not.** Exactly **one** field was read
from the page: `revenue = 4321.0`. `net_income = 4321.0` in the cash flow is the same
figure carried across by the parser. Everything else in the list above is **0.0 because
it is not printed on a one-line PDF** — that is the expected result the assignment
predicted, and it is backlog item 1, not a defect of this unit. `years: [0]` for the
same reason: the page carries no fiscal year.

**"It ran" is not evidence — so here is the evidence that a figure came from the
filing.** `STATUS.md` trap 2 says a valuation runs from zeros. I changed the number
printed on the page and re-ran the same code:

| The page prints | The extraction returned |
|---|---|
| `Total net revenues 4321` | `revenue = 4321.0` |
| `Total net revenues 8765` | `revenue = 8765.0` |

The value tracks the page. It is not a default, and it is not recalled.

**Three-year run.** `c:/tmp/probe_filing.pdf`, a filing-*shaped* synthetic probe
document, extracted **[2022, 2023, 2024]** with **all nine arithmetic reconciliations
`OK` (+0)** — gross profit, operating income and net income for each year. That is the
two-pass extractor working at full width, not just on one line.

### Criterion 5 — the stop, with both remedies

Foundry URL and both API keys cleared, then `extract_financials` called:

```
ValueError raised. Message:

No Anthropic credential resolved, so extraction cannot start. Either remedy is sufficient:
  (1) Set ANTHROPIC_API_KEY in .env or the system environment, to use the public Anthropic API; or
  (2) Set ANTHROPIC_FOUNDRY_BASE_URL (or ANTHROPIC_FOUNDRY_RESOURCE) to a Microsoft
      Foundry gateway and sign in with `az login`, so DefaultAzureCredential can issue an
      Entra ID token for scope https://cognitiveservices.azure.com/.default. A Foundry
      gateway also accepts ANTHROPIC_FOUNDRY_API_KEY instead of `az login`.
See docs/8-build/environment.md section 3.
```

Names the variable **and** `az login`. It raises **before any network call** — the
first statement of `extract_financials` is `resolve_provider`, and `resolve_provider`
reads only `os.environ`. The old code demanded `ANTHROPIC_API_KEY` and would have
refused the working Foundry credential this machine actually has.

### Criterion 8 — the type diff, in full

```
$ diff <normalised mypy before> <normalised mypy after>
21c21
< Found 33 errors in 4 files (checked 18 source files)
---
> Found 22 errors in 4 files (checked 18 source files)
27,37d26
< ingestion\claude_extractor.py: error: Item "ThinkingBlock" of "..." has no attribute "text"
< ... 10 more union-attr errors on the same line ...
```

**Eleven removed, none added.** All eleven are the `union-attr` errors on
`response.content[0].text` — mypy had been reporting this defect all along, and it was
live. Nothing else moved.

---

## Criterion 4 — blocked, and why I did not widen my scope

**The web app returns HTTP 500 on every page, on the unmodified tree.** Measured, not
inferred: I stashed my entire change, started the app at `81816be`+ and requested `/`.

```
BASELINE (unmodified tree) GET / -> 500
occurrences of "cannot use 'tuple' as a dict key" in the log: 1
```

Cause, isolated:

```
starlette 1.6.0 | jinja2 3.1.6 | fastapi 0.141.1
TemplateResponse signature: (self, request: 'Request', name: 'str', context: ... )
```

Starlette **1.6.0 has removed** the deprecated `TemplateResponse(name, context)` form.
The repository uses that form at all four call sites, so `name` binds to the context
dict, and jinja fails trying to use a dict as a cache key. These are the same four
`arg-type` errors mypy has been reporting on those lines for two units.

```
api/routes_upload.py:42:      templates.TemplateResponse("upload.html", {...})          <- out of scope
api/routes_valuation.py:111:  templates.TemplateResponse("assumptions.html", {...})     <- out of scope
api/routes_valuation.py:228:  templates.TemplateResponse("valuation_result.html", {...}) <- the result context
api/routes_valuation.py:241:  templates.TemplateResponse("valuation_result.html", {...}) <- the result context
```

My Files in scope say `api/routes_valuation.py` — "**`_extract_from_files` and the
result context only. Nothing else in this file**" — and do not mention
`api/routes_upload.py` at all. Fixing only the two result-page calls would not make the
page reachable, because `/` and `/assumptions` are the route to it and both are outside
my scope. **The work needs a file outside my Files in scope, so I stopped and am
reporting it rather than widening my own scope.** The fix is mechanical, four lines:
`TemplateResponse("x.html", {...})` → `TemplateResponse(request, "x.html", {...})`.

**What I proved instead.** I ran the real pipeline end to end — real extraction through
the gateway, real `normalize_financials`, `derive_assumptions`, `fetch_price_data`,
`run_capm`, `calculate_wacc`, `project_fcffs`, `run_dcf` — then rendered the real
`templates/valuation_result.html` through **the app's own `Jinja2Templates` object**
(`from api.routes_valuation import templates`) with **the exact context the success
branch builds**. Extraction went through `api.routes_valuation._extract_from_files`,
the function this unit changed. Rendered output:

```html
<h2>Extraction — who read the filing</h2>
        <table class="data-table">
            <tr><td>Provider</td><td>CLAUDE</td></tr>
            <tr><td>Model</td><td>claude-opus-5</td></tr>
            <tr><td>Transport</td><td>Microsoft Foundry gateway (apm-use-claudecode-pd.azure-api.net)</td></tr>
            <tr><td>Credential source</td><td>Entra ID token via DefaultAzureCredential (`az login`), scope https://cognitiveservices.azure.com/.default</td></tr>
        </table>
```

`re.search(r"sk-ant|Bearer |eyJ", html)` over the whole rendered page → **False**.

**This is one step short of the criterion and I am not claiming otherwise.** The
template, the context and the data are real; the HTTP request is not. Re-measure
criterion 4 over HTTP once the starlette signature is fixed.

**The statement figures behind that page are from a synthetic probe document, and the
share price it rendered (41.77) is meaningless.** `MSFT` supplied only the market-data
leg. I am stating this loudly because `STATUS.md` trap 2 exists: that page is evidence
about the *labelling block* and about nothing else whatsoever.

---

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| **Fixed `response.content[0].text`**, which was not in the assignment | Criterion 2 could not pass without it. `claude-opus-5` returned `AttributeError: 'ThinkingBlock' object has no attribute 'text'` on the very first real extraction. The old code assumed the first block is the answer; with opus-5 it is sometimes the reasoning | Could have pinned the model back to `claude-sonnet-4-6` to dodge it. That would be changing code to make a symptom go away, against a decision the user already took, and would leave a latent crash for the next model. Instead the text blocks are **selected by type**, and **no text block stops** rather than parsing `""` into a statement of zeros |
| Added a stop on `stop_reason == "max_tokens"` | Same call path, and newly load-bearing: a reasoning model spends output budget before answering, so truncation is likelier than it was. A truncated JSON body parses into a statement missing whatever was not written, and every missing money field defaults to `0.0` downstream | Silence was the alternative. The existing retry loop catches truncation only if it happens to break the JSON; a response cut off at a clean boundary would parse and be wrong. **This is beyond the literal assignment and I flag it as such** |
| `resolve_provider` made **public**, and called from the result context | The result page must label the extraction even when it did not run the extraction — `run_valuation` usually serves from `_extraction_cache`. The function reads `os.environ` only: no token, no network, safe in a request handler | Threading the resolution through the cache would mean changing the cache's value type, and the cache (`api/routes_valuation.py:25`) is backlog item 5 and out of scope |
| `ProviderResolution` holds **no key and no token** | Criterion 10, and it is rendered into a page. A display object that can carry a secret will eventually leak one | An `api_key` field would have been convenient and is exactly how a token reaches a template by accident |
| Credential **kind** is a typed field; `_build_claude_client` branches on it, never re-decides | Rule 2. One decision point. If the builder re-read the environment it could pick a different credential from the one the label names, and the page would then lie | |
| The Entra token provider is a **module-level lazy singleton** | `DefaultAzureCredential()` probes several credential sources on construction, and `get_bearer_token_provider` caches and refreshes the token itself. Rebuilding per call means that probe — and an `az` subprocess — six times per valuation | Not a data cache and not a default: it holds a credential *object*, supplies no number and hides no missing input. Documented in place |
| `get_bearer_token_provider(DefaultAzureCredential(), …)`, never a `subprocess` call to `az` | Assignment step 3, and it is right: a shell-out is untestable and breaks where the CLI is absent | Proved by execution — `c:/tmp/probe_sdk.py` and every extraction in this entry ran through `azure-identity` with no `az` invocation |
| `Final` with **no annotation** on the config constants | Gives `DEFAULT_EXTRACTION_PROVIDER` the inferred type `Literal["claude"]`, so it satisfies `Provider` **without `config.py` importing from `ingestion/`** | An explicit `: str` would widen it and break every call site's type check; importing `Provider` into `config.py` would invert the dependency |
| `provider: Provider = …` annotated in `_extract_from_files` | An unannotated local widens the Literal to `str` and mypy stops checking it — it cost 3 new `arg-type` errors until I annotated it | |
| `_resolve_model` **stops** on an empty-string model instead of falling through to the default | Rule 3. `model or _DEFAULT_MODELS[provider]` was a bare `or` default — `--model ""` would have silently become opus-5 | |
| `ANTHROPIC_FOUNDRY_BASE_URL` **and** `_RESOURCE` both set → stop | The SDK raises `ValueError("base_url and resource are mutually exclusive")` from inside its constructor. Catching it at resolution names the two variables and the remedy | |
| The transport label carries the **gateway host** | Criterion: "a figure read by `claude-opus-5` through a company gateway and the same model through the public API must be distinguishable by the reader." The model name alone does not distinguish them | A hostname is not a credential, and the SDK already prints it |
| Did **not** fix the starlette `TemplateResponse` signature | 3 of the 4 sites are outside Files in scope; fixing only the 2 in scope would not make the page reachable | See "Criterion 4" |

**No code change in this unit was made to reach a target number.** The one place that
temptation existed — pinning the model back to `claude-sonnet-4-6` so `content[0].text`
kept working — is recorded above as explicitly rejected.

---

## Rule 3 — what stops, and what does not

Every value this unit reads. **There is no "defaults to" row.**

| Value read | If it were missing | Evidence |
|---|---|---|
| `ANTHROPIC_FOUNDRY_BASE_URL` / `_RESOURCE` | not a stop by itself — **selects the transport**. If both are absent the code falls to the public-API branch, which then stops if `ANTHROPIC_API_KEY` is also absent | `claude_extractor.py:_resolve_claude`; criterion 5's run cleared all of them and the run stopped |
| `ANTHROPIC_FOUNDRY_API_KEY` | not a stop — **selects Entra ID** instead, which is the intended path here | `_resolve_claude`. This machine has it unset and extraction works |
| `ANTHROPIC_API_KEY` | **stops**, naming it and naming `az login` | criterion 5 output above |
| the `azure.identity` module | **stops**, naming `pip install -r requirements.txt` and `az login` — at resolution, not at the first API call | `_resolve_claude`, `except ModuleNotFoundError` → `ValueError` |
| `GEMINI_API_KEY` (provider=`gemini`) | **stops**, naming it and naming the default provider | `_resolve_gemini` |
| `model` argument | `None` → the named default for that provider, which **is** the labelled assumption and is shown in the output. `""` → **stops** | `_resolve_model` |
| the credential, re-read in `_build_claude_client` / `_call_gemini` | **stops** — "resolved at startup but is empty now" | three `raise ValueError` sites |
| `response.content` blocks | no text block → **stops**, naming the block types received. Never parses `""` | `_call_claude`; this fired for real on the first run |
| `response.stop_reason` | `max_tokens` → **stops**. A partial answer is never parsed | `_call_claude` |
| the Foundry base URL's host | not a URL with a host → **stops** | `_foundry_endpoint_label` |

`os.environ.get(k, "")` appears several times. **None of these is a rule-3 default**:
the empty string is a *presence test* consumed on the next line, it never becomes a
figure, and every branch out of it either selects a named alternative or raises. The
census confirms it — 116 before, **116 after**, and no added line matches the pattern:

```
git diff -U0 -- config.py cli.py api/ ingestion/ | grep "^+" | grep -E <census pattern>
  → none
```

**I removed one bare-`or` default** (`model or _DEFAULT_MODELS[provider]`) and added
none. It is not in the census count because the census pattern only matches `or 0`.

---

## Rules 1, 5 and 6

**Rule 1 — no number came from a model.** This unit adds no field to either prompt
schema, removes none, and changes no prompt text. `git diff` touches neither
`_FINANCIALS_SCHEMA`, `_FINANCIALS_SYSTEM_PROMPT`, `_NRI_SYSTEM_PROMPT` nor either
`_build_*_prompt`. The LLM boundary has not moved, so no escalation is due.

**One thing I checked and want on the record.** The probe extraction returned
`other_operating_activities = -4321.0`, a figure that appears nowhere on the page. It
is **not** a model-produced number. `claude_extractor.py:637` computes it as a
deterministic residual in Python:

```python
other_ops = cfo - net_income - da - sbc - delta_wc   # residual
```

`cfo` was `0.0` because it is not printed on the page, `net_income` was `4321.0`, so
the residual is `-4321.0`. The arithmetic is correct; its *inputs* are zero-defaults.
It is a sharp demonstration that backlog item 1 does not merely produce zeros — **it
manufactures non-zero figures** out of "we do not know". Filed as a finding.

**Rule 5 — no statement figure came from anywhere but the filing.** Proved above by
changing the page and watching the value follow. `api/routes_valuation.py:182`, the
yfinance `sharesOutstanding` fallback, is untouched and still a rule-5 break; it is
backlog items 1 and 12 and outside my scope.

**Rule 6 — the assumption is labelled.** Which model read the filing, over which
transport, on whose credential, is now visible in both outputs — CLI line and result
page table — and each carries its source by name. That is what this unit adds.

---

## Measurements

| Gate | Before (`852f74b`) | After | Verdict |
|---|---|---|---|
| Tests | `1 failed, 105 passed` | `1 failed, 105 passed` | identical failure set |
| Lint | 5 errors, all `BLE001` | **5 errors, all `BLE001`** | same five lines |
| Types | 33 errors, 4 files, 18 checked | **22 errors, 4 files, 18 checked** | strict subset: −11, +0 |
| Rule-3 census | 116 | **116** | unchanged |
| `import app` | ok | ok | |

Files changed: 7, `+496 / −75`. Every one is in Files in scope. `git stash list` is
empty and nothing else in the tree moved.

**Figures this unit moved:** none in any valuation. The only numbers it produced are
the probe extractions, and their input is named above.

**Cleanup:** both local servers (ports 8137, 8138) terminated; `netstat` shows 0
listeners. Scratch lives in `c:/tmp/` only — nothing was copied into the repository.

---

## What I did not do

- **Did not fix the starlette `TemplateResponse` signature.** 3 of 4 sites outside
  Files in scope. This is the sole reason criterion 4 is not `pass`.
- **Did not touch the Gemini path's behaviour.** It still resolves, still stops when
  `GEMINI_API_KEY` is absent, still retries on 429/503. What changed is that it takes
  a `ProviderResolution` and reads its key from the environment at the call site rather
  than receiving it through six signatures. **It remains untestable from this network**,
  so I could not execute it — a reviewer should treat Gemini as unverified by me.
- **Did not add a third `Provider` value.** `Provider` is still
  `Literal["claude", "gemini"]`, per the assignment.
- **Did not add an `except Exception`.** Backlog item 8 is untouched: ruff still
  reports **5 `BLE001`**, the same five lines. (`grep "except Exception"` over
  `ingestion/ api/ cli.py` returns 5, one more than ruff flags there — the extra is
  `_call_gemini`'s retry handler, which re-raises and so is not a blind catch. It
  predates this unit.)
- **Saw and left `claude_extractor.py:637` (was `:479`)** — the D&A subtraction inside
  the parser, backlog item 10 and named in `docs/2-rules/llm-boundary.md`. Not mine.
- **Saw and left the blanket catch at `claude_extractor.py:934` (was `:795`)** —
  backlog item 8. Not mine.
- **Did not touch `tests/`.** No test asserts anything about this change; `ingestion/`
  and `api/` still have no tests at all.
- **Did not update `STATUS.md`** or the journal index. Orchestrator's.

---

## Findings for the orchestrator

1. **The web application cannot render a single page on this machine, and could not
   before this unit.** `GET /` → HTTP 500 on the unmodified tree. starlette 1.6.0
   removed `TemplateResponse(name, context)`; the repository uses it at all four call
   sites. **This is a bigger outage than the one this unit was written to fix** — it
   means every web result ever reported from this tree on these versions was an error
   page. It was invisible because `pytest` never starts the app and mypy's report of it
   (4 `arg-type` errors) was filed as a typing nicety. The fix is four lines:
   `TemplateResponse(request, "x.html", {...})` in `api/routes_upload.py:42` and
   `api/routes_valuation.py:111, 228, 241`. It needs one assignment covering both
   files, and it unblocks done-criterion 4 of this unit.

2. **Backlog item 1 manufactures non-zero figures, not just zeros.** Concrete,
   measured: a cash-flow field came back `-4321.0` for a page that prints one number,
   because `other_ops = cfo - net_income - da - sbc - delta_wc` was computed over
   zero-defaulted inputs (`claude_extractor.py:637`). The item is currently described
   in terms of "a zero that means we do not know". It should say that those zeros
   propagate through real arithmetic into figures that look measured. This may raise
   the item's priority.

3. **`response.content[0].text` was a live crash that the type gate had already
   found.** Eleven of the 33 mypy errors were `union-attr` on that one line. They sat
   in the "not worse than 33" budget for two units while being an unconditional
   `AttributeError` against any reasoning model. Worth asking whether the type gate
   should be read for *content* rather than for its count — several of the remaining 22
   may be the same kind of thing. `api/routes_valuation.py:190` (`BalanceSheet | None`)
   is already flagged in `STATUS.md` as exactly that.

4. **`ingestion/` and `api/` still have no tests.** This unit adds `resolve_provider`,
   `_resolve_model`, `_resolve_claude`, `_resolve_gemini`, `_foundry_endpoint_label`
   and `_build_claude_client` — six functions that are **pure over `os.environ`**, make
   no network call and need no key. They are the first genuinely unit-testable code in
   `ingestion/`, and the stop paths in them are exactly the kind a tester can assert on
   with `monkeypatch.delenv`. A tester assignment here would be cheap and would cover
   criterion 5 permanently rather than by one pasted message.

5. **The probe artefacts named in the assignment were not on disk.** `c:/tmp/probe.pdf`
   and the three probe scripts were absent. I rebuilt them and they are there now
   (`make_pdf.py`, `probe.pdf`, `probe_8765.pdf`, `probe_filing.pdf`, `probe_sdk.py`,
   `run_probe_extraction.py`, `probe_no_credential.py`, `render_result_page.py`). `c:/tmp`
   is scratch and not guaranteed to survive; if these matter for the next unit they
   need a home that is not `c:/tmp`, and `docs/8-build/environment.md` section 6 owns
   scratch policy.

6. **There is still no real filing on this machine.** Every extraction in this entry ran
   against a PDF I generated. The plumbing is proven; **the extractor's accuracy against
   a real 10-K is not**, and the multi-PDF year-routing orchestrator
   (`extract_multi_year`'s merge logic) has never been executed against more than one
   real document. Getting one 10-K onto this machine is now the highest-value next step,
   because for the first time there is a working client to point at it.
