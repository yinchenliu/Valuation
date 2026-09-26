---
agent: code_reviewer
assignment: P2b-provider
round: 1
verdict: changes_requested
---

# Review of P2b-provider, round 1

Programmer entry: `.agent/journal/2026-09-21T0030-programmer-p2b-provider.md`

Reviewed at `852f74b` + working tree. Baseline for every comparison below is
`git archive HEAD` exported to `c:/tmp/p2b_base` — I did not stash, and the repository
tree is unchanged by me (`git status --short` shows only the unit's seven files).

**The code is sound. No rule in `docs/2-rules/rules.md` is broken by this diff.** One
done-criterion stands unmet, and the reason the entry gives for it is disproven by
execution. That is F1, and it is the only thing blocking.

## The guard checks

Run over the seven Files in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | 5 hits, **all pre-existing**, none on an added line |
| lookup with a fallback — `.get(k, 0)` | 49 hits in `claude_extractor.py`, all pre-existing (backlog item 1); the **added** hits are all `os.environ.get(X, "")` |
| bare or-default — `or 0.0` | 3 hits, all in `_call_gemini`'s untouched retry block |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | 3 hits, all pre-existing (`cli.py:510`, `claude_extractor.py:563-564`) |
| dict of functions keyed by data | clean — `_DEFAULT_MODELS` maps a key to a **string**, which rule 2 allows |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → 0 |

Proof that no added line carries a rule-3 form:

```
git diff -U0 HEAD -- config.py cli.py api/ ingestion/ templates/ | grep "^+" \
  | grep -E "if [^)]+ else 0(\.0)?\b|\bor +(0|0\.0)|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0|\*\*kwargs|getattr\("
  → no output (exit 1)
```

The `os.environ.get(X, "")` hits are the question the greps raise, and **the programmer
answered them** in its own rule-3 table. I re-checked each by execution: every one is a
presence test consumed on the next line, and every branch out of it either names an
alternative or raises. Census `116 → 116`, measured on both trees.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| no credential of any kind | **yes**, `ValueError` naming `ANTHROPIC_API_KEY` *and* `az login`, before any network call | re-ran it; message in "Done-criteria" below |
| `GEMINI_API_KEY` absent | **yes** | `resolve_provider('gemini', None)` → `ValueError: GEMINI_API_KEY is not set…` |
| `azure.identity` absent | **yes**, at resolution, naming `pip install -r requirements.txt` then `az login` | `claude_extractor.py:1039` |
| `model=""` / `"   "` | **yes** — the old `model or _DEFAULT_MODELS[provider]` bare-or default is **removed** | both raise `ValueError: model was given as an empty string…` |
| `BASE_URL` and `RESOURCE` both set | **yes**, names both variables | raised on test |
| `BASE_URL` set but not a URL | **yes**, names the value | `ValueError: … is not a URL with a host: 'not-a-url'` |
| `response.content` with no text block | **yes**, names the block types; never parses `""` | `claude_extractor.py:494-500` |
| `response.stop_reason == "max_tokens"` | **yes**, never parses a truncated body | `claude_extractor.py:505-510` |
| a credential that vanished after resolution | **yes**, three `raise ValueError` sites | `claude_extractor.py:445, 453, 534` |

No value this unit reads produces a number when it is missing.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | unit moves no figure; the only number it produced is a probe extraction |
| percentages converted at the route boundary, once | untouched — `routes_valuation.py:165-173` unchanged |
| falsy not treated as missing | no new instance; the five at `:165-169` are untouched (backlog item 6) |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | `git diff --stat HEAD -- models/ analysis/` → empty |

`claude_extractor.py` now imports `config` at module level — allowed, and it is the
only file holding a model client.

**LLM boundary:** no prompt text, no schema field, no `_build_*_prompt` body changed —
only call-site arguments. No escalation is due. Confirmed by `git diff`.

## Done-criteria, re-run

Criterion 6's expectation was corrected by the orchestrator from `1 failed, 92 passed`
to `1 failed, 105 passed`; I measured against the corrected figure.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | one provider default | 1 definition, 11 references | `config.py:29` only definition; all other hits are `config.DEFAULT_EXTRACTION_PROVIDER` or prose | **yes** |
| 2 | **a real extraction through the gateway** | `4321` then `8765` off the page | ran it myself twice with **new** numbers: page `6174` → `revenue 6174.0`; page `2718` → `revenue 2718.0` | **yes** |
| 3 | provider, model, transport in CLI output | pass | `Provider: CLAUDE \| Model: claude-opus-5 \| Transport: Microsoft Foundry gateway (apm-use-claudecode-pd.azure-api.net) \| Credential: Entra ID token via DefaultAzureCredential…` | **yes** |
| 4 | the same three on the result page | blocked, not by this unit | **the block renders over real HTTP with an in-scope-only change** — see F1 | **no** |
| 5 | missing credential stops, both remedies | pass | re-ran with all four vars cleared → `ValueError` naming `ANTHROPIC_API_KEY` and `` `az login` `` | **yes** |
| 6 | suite unchanged | `1 failed, 105 passed`, same failure | before **and** after: `1 failed, 105 passed`, `test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` — identical **set**, not just count | **yes** |
| 7 | lint unchanged | 5 `BLE001`, same five | before: `:96, :220, cli:758, ce:795, e2e:106`; after the same five, line-shifted. `Found 5 errors.` both | **yes** |
| 8 | types not worse | 22 vs 33, strict subset, −11 +0 | set-diffed with line numbers stripped: **`comm -13` (new errors) is empty**; the 11 removed are exactly the `union-attr` on the old `content[0].text` | **yes** |
| 9 | rule-3 census | 116 | 116 on both trees | **yes** |
| 10 | no token printed or logged | 0 | 0 in two full extraction logs and in the rendered HTML; no `print` of a key anywhere. **One caveat — F2** | **mostly** |

### Criterion 2, my own run (not the programmer's)

```
PAGE TEXT: 'Total net revenues 6174'
  Provider: CLAUDE | Model: claude-opus-5 | Transport: Microsoft Foundry gateway
  (apm-use-claudecode-pd.azure-api.net) | Credential: Entra ID token via
  DefaultAzureCredential (`az login`), scope https://cognitiveservices.azure.com/.default
years: [0]
IS non-zero: {'revenue': 6174.0}
CF non-zero: {'net_income': 6174.0, 'other_operating_activities': -6174.0}
```

and, second run, page `2718` → `{'revenue': 2718.0}`. **The value tracks the page.**
`STATUS.md` trap 2 is satisfied: this is not a zero-default and it is not recalled.
Exactly one field is read from the page; everything else is `0.0` because a one-line PDF
prints nothing else, which the assignment predicted.

### The change the assignment did not ask for — I judge it **right**

`_call_claude` read `response.content[0].text`. Three things settle it:

1. **Criterion 2 could not have passed without it.** `claude-opus-5` emits a
   `ThinkingBlock` ahead of its answer; the old line raises `AttributeError`. My own
   first-run extraction went through the new code and completed.
2. **It stops, it does not fall back.** `if not text_blocks: raise ValueError(…)` naming
   the block types received (`claude_extractor.py:494-500`). A fallback to `""` here
   would have been rule 3; this is the opposite of one. Same for the new `max_tokens`
   stop.
3. **The mypy claim holds exactly.** 33 → 22, and the set difference in the *new*
   direction is empty. The 11 removed are all `union-attr` on that one line, which mypy
   had been reporting as an unconditional crash while it sat inside a "≤ 33" budget.

The file was in scope, the change was forced by a criterion, and it was recorded with
its traceback and its rejected alternative (pinning the model back). That is the
behaviour the rules ask for.

### The Gemini path is intact

`Provider` is still `Literal["claude", "gemini"]` — `typing.get_args` returns
`('claude', 'gemini')`, no third value. `_resolve_gemini` stops on a missing key and
returns a correct `ProviderResolution` with a dummy one. `_call_gemini`'s client
construction, `GenerateContentConfig`, finish-reason warning and 429/503 backoff are
byte-identical apart from taking the key from `os.environ` at the call site. Unreachable
from this network, so **not executed** — verified by reading, as the brief directs.

### Criterion 3 (HTTP 500) — verified, and pre-existing

Executed on the **baseline export**, with none of the unit's changes present:

```
BASELINE (git archive HEAD → c:/tmp/p2b_base) GET / -> 500
TypeError: cannot use 'tuple' as a dict key (unhashable type: 'dict')
starlette 1.6.0 | fastapi 0.141.1 | jinja2 3.1.6
TemplateResponse signature: (self, request: 'Request', name: 'str', context: …)
```

The claim is true and it is not this unit's. Which of the four sites are in scope:

| Site | In this unit's scope? |
|---|---|
| `api/routes_upload.py:42` | **no** — the file is not named in Files in scope at all |
| `api/routes_valuation.py:114` (`assumptions.html`) | **no** — in the file, but outside "`_extract_from_files` and the result context only" |
| `api/routes_valuation.py:231` (`valuation_result.html`, success) | **arguably yes** — this *is* the result context call |
| `api/routes_valuation.py:244` (`valuation_result.html`, error) | **arguably yes** — same |

So two, not three, are clearly outside. The programmer's own evidence table labels
`:228`/`:241` "the result context", which is the phrase its scope grants it.

## Findings

### F1 — criterion 4 was reachable over HTTP without leaving scope; the stated impossibility is wrong · `major`

**Evidence:** on a scratch copy of the working tree (`c:/tmp/p2b_mod`) with **only** the
two `valuation_result.html` call sites changed to `TemplateResponse(request, …)` —
`routes_upload.py:42` and `routes_valuation.py:114` left broken —

```
GET  /            -> 500   (still broken, out of scope, as expected)
POST /valuation   -> 200
  <h2>Extraction — who read the filing</h2>
    Provider CLAUDE | Model claude-opus-5
    Transport Microsoft Foundry gateway (apm-use-claudecode-pd.azure-api.net)
    Credential source Entra ID token via DefaultAzureCredential (`az login`), scope …
  re.search("eyJ…|Bearer |sk-ant") over the response -> 0 hits
```

**Rule or document:** `P2b-provider` done-criterion 4. The entry says *"fixing only the
two result-page calls would not make the page reachable, because `/` and `/assumptions`
are the route to it"*. That is factually false: `POST /valuation` is a route of its own,
and `routes_valuation.py:148-154` has a cache-miss branch that runs the full extraction,
so neither `/` nor `/assumptions` is required. I proved it by executing the whole
pipeline — real gateway extraction, `normalize_financials`, CAPM, WACC, DCF — over HTTP.

**What would fix it:** either two lines in `run_valuation` (`:231`, `:244`), which is
within a defensible reading of "the result context"; **or** the orchestrator amends the
assignment to move criterion 4 to `P5-web-routes` and records why. I note
`.agent/assignments/P5-web-routes.md` already exists and says it "finishes what
`P2b-provider` could not" — if that is the chosen route, the amendment belongs in the
P2b assignment, not left as an unmet criterion, because `P5` `depends_on: [P2b-provider]`
and the chain cannot both depend on P2b and supply P2b's evidence. **This is a choice
for the orchestrator, not for me.** The code itself needs no defence.

### F2 — the transport label can print an embedded credential · `minor`

**Evidence:** `ingestion/claude_extractor.py:987` uses `urlsplit(base_url).netloc`,
which carries userinfo. Executed:

```
ANTHROPIC_FOUNDRY_BASE_URL=https://user:supersecret@gw.example.net/x
resolve_provider('claude', None).transport_label
  -> 'Microsoft Foundry gateway (user:supersecret@gw.example.net)'
```

That string is printed to stdout by `describe_resolution` and rendered into
`valuation_result.html`.

**Rule or document:** assignment step 6 — *"Never print or log the token. Name the
credential source, not its value."* — and done-criterion 10. Not a `rules.md` rule,
hence `minor`; it needs an operator who put credentials in the URL, which nobody here
has done.

**What would fix it:** `urlsplit(base_url).hostname` instead of `.netloc` (and keep the
existing empty-host stop).

### F3 — the result page's extraction label is re-derived, not recorded · `minor`

**Evidence:** `api/routes_valuation.py:229` —
`extraction = resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)` — runs at
render time and reads the environment, while the figures on the page may come from
`_extraction_cache`, populated by an earlier request. The label describes *who would
read a filing now*, not *who read this one*.

**Rule or document:** rule 6 is satisfied in substance — the assumption is named and
shown. The concern is rule 4's spirit: the label can disagree with the event it
describes if the environment moves between the two requests. Same process and one
constant make that unlikely today, which is why this is `minor` and not `major`. The
programmer recorded the decision and its reason (the cache's value type is backlog item
5, out of scope) — I accept that reasoning.

**What would fix it:** carry the `ProviderResolution` in the cache alongside the
financials, when backlog item 5 is opened.

### F4 — a new module-level mutable global · `note`

**Evidence:** `ingestion/claude_extractor.py:416` `_ENTRA_TOKEN_PROVIDER` with a
`global` write in `_entra_token_provider`.

**Rule or document:** none. It holds a credential *object*, supplies no figure and hides
no missing input, so it is not rule 3 and not rule 2. The reason for caching it
(`DefaultAzureCredential()` probes on construction, six LLM calls per valuation) is
written in place and is correct. Recorded only so the next reader knows it was seen.

### F5 — backlog item 1 manufactures non-zero figures, confirmed · `note` (not a finding against this unit)

**Evidence:** my own two runs, independent of the programmer's:
`other_operating_activities: -6174.0` and `-2718.0` from pages printing a single number,
via `claude_extractor.py:637` `other_ops = cfo - net_income - da - sbc - delta_wc` over
`cfo=0.0` (`.get("cfo", 0)`).

The programmer's finding 2 is **verified**. The two claims are materially different and
the sharper one is true: item 1 does not only produce zeros, it produces a plausible,
signed, non-zero figure with the correct magnitude that a reader cannot distinguish from
a measurement. That belongs in the backlog item's text and may raise its priority. The
line is untouched by this unit, so it is not charged to it.

## Pre-existing, already recorded — not findings against this unit

The assignment names items 1, 5, 6, 7, 8, 10 and 20 as out of scope. I saw all of them
and re-report none.

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 — zero defaults | `claude_extractor.py:617-683` (49 sites) | **no** — line-shifted only |
| 5 — module-global extraction cache | `routes_valuation.py:31` | **no** |
| 6 — falsy treated as missing | `routes_valuation.py:165-169` | **no** |
| 7 — duplicated pipeline | `cli.py` / `api/` | **no** — one `argparse` line touched |
| 8 — blanket catches | `claude_extractor.py:934`, `routes_valuation.py:111, 243` | **no** — ruff reports the same five lines |
| 10 — D&A subtracted in the parser | `claude_extractor.py:622` | **no** |
| 20 — NaN beta | `analysis/` | **no** — `analysis/` untouched |

The programmer said it saw items 8 and 10 in the file it was editing. It did, at the
correct post-shift lines.

## Verdict

`changes_requested`

**F1 alone blocks.** Everything the unit was built to do, it did: one provider default
in one place, Foundry as a transport and not a third `Provider` value, an Entra
credential with no `az` subprocess, a stop that names both remedies, the resolution
labelled in both outputs, prompts untouched, and a real two-pass extraction whose figure
follows the page — which I reproduced twice with numbers the programmer never used. The
unasked `content[0].text` fix was correct, necessary, and stops rather than falls back;
it removed 11 mypy errors and added none. The HTTP 500 is real, pre-existing, and worse
than the defect this unit was written for. But done-criterion 4 stands unmet on a reason
that does not survive execution: the result page renders over real HTTP with a change
confined to the two result-context calls, and I ran the full pipeline through it to prove
that. Resolving F1 is a two-line change or a one-line amendment to the assignment — the
orchestrator's call, since `P5-web-routes` already claims the same ground while depending
on this unit. F2 and F3 are `minor` and do not block. Nothing in this diff breaks a rule
in `docs/2-rules/rules.md`.

**Scratch used, all outside the repository:** `c:/tmp/p2b_base` (baseline export),
`c:/tmp/p2b_mod` (the F1 experiment), `c:/tmp/rv_check.py`, `c:/tmp/rv_probe_6174.pdf`,
`c:/tmp/rv_probe_2718.pdf`, `c:/tmp/rv_out_*.txt`, `c:/tmp/mod_result2.html`. Both test
servers (ports 8211, 8212) terminated; `netstat` shows no listener. The repository tree
is exactly as the programmer left it.
