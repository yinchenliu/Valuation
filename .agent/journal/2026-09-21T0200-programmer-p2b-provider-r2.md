---
agent: programmer
assignment: P2b-provider
round: 2
status: partial
files_touched: [api/routes_valuation.py, ingestion/claude_extractor.py]
verdict: —
---

# P2b-provider round 2 — criterion 4 proved over HTTP, the userinfo leak closed, F3 escalated

> Opened before the first command. Filled as each result landed.

Review answered: `.agent/journal/2026-09-21T0130-code_reviewer-p2b-provider.md`
Round-1 entry, **not edited**: `.agent/journal/2026-09-21T0030-programmer-p2b-provider.md`

**Status is `partial` for one reason, and it is the one the amendment anticipated: F3
cannot be answered inside this unit's Files in scope.** I name the exact lines below and
stop there rather than widening. F1, F2 and F4 are answered, and criterion 4 — the
criterion the round exists for — now passes over a real ASGI request.

I dispute nothing. The reviewer was right on F1: my round-1 reason for calling criterion
4 unreachable was false, `POST /valuation` is its own route with a cache-miss branch that
runs the whole pipeline.

---

## Answers by finding number

### F1 · `major` · criterion 4 was reachable over HTTP — **fixed, and proved**

Three lines of code, both in `api/routes_valuation.py`, both `valuation_result.html`
call sites moved to the starlette 1.6.0 signature `(request, name, context)`:

```
api/routes_valuation.py:246   return templates.TemplateResponse(request, "valuation_result.html", {...})   # success
api/routes_valuation.py:259   return templates.TemplateResponse(request, "valuation_result.html", {...})   # error
```

`"request": request` was dropped from both context dicts, because starlette now does
`context.setdefault("request", request)` itself — verified by reading its source, not
assumed:

```
$ .venv/Scripts/python.exe -c "import inspect; from starlette.templating import Jinja2Templates; print(inspect.signature(Jinja2Templates.TemplateResponse))"
(self, request: 'Request', name: 'str', context: 'dict[str, Any] | None' = None, ...)
  ... context = context or {}
      context.setdefault("request", request)
starlette 1.6.0 | fastapi 0.141.1 | jinja2 3.1.6
```

**The two out-of-scope sites are untouched**, confirmed after the edit:

```
$ grep -n "TemplateResponse" api/routes_valuation.py api/routes_upload.py
api/routes_valuation.py:114:    return templates.TemplateResponse("assumptions.html", {      <- still old, P5-web-routes
api/routes_valuation.py:246:    return templates.TemplateResponse(request, "valuation_result.html", {
api/routes_valuation.py:259:    return templates.TemplateResponse(request, "valuation_result.html", {
api/routes_upload.py:42:        return templates.TemplateResponse("upload.html", {"request": request})   <- still old, P5-web-routes
```

`GET /` and `GET /assumptions` still answer **500**. That is expected and it is
`P5-web-routes`. Both statuses are in the criterion-4 output below.

### F2 · `minor`, treated as higher — **fixed**

`ingestion/claude_extractor.py:993`, one word, `.netloc` → `.hostname`, with the reason
written above it. Measured proof that the leak existed and is gone is criterion 11.

### F3 · `minor` · the page's label is re-derived, not recorded — **escalated, not fixed**

**This cannot be done inside my Files in scope.** The amendment says: "If that cannot be
done inside this unit's scope, say exactly which file would need to change and stop."

The file is `api/routes_valuation.py`, which is in scope — but only at
"`_extract_from_files`, the result context, and the two `TemplateResponse` calls that
render `valuation_result.html`. **Nothing else in this file.**" Carrying the resolution
from the extraction to the page needs **three regions that grant excludes**, and all
three are load-bearing, not cosmetic:

| Line, current tree | What it is | Why the fix needs it |
|---|---|---|
| `api/routes_valuation.py:31` | `_extraction_cache: dict[str, FinancialStatements]` | the value type must become `(FinancialStatements, ProviderResolution)` — this is exactly backlog item 5 |
| `api/routes_valuation.py:100` and `:102`, inside **`assumptions_page`** | `financials, non_recurring = _extract_from_files(...)` and `_extraction_cache[cache_key] = financials` | the extraction that produces the cached figures happens **here**, so the resolution must be recorded here. `assumptions_page` is not `_extract_from_files`, not the result context, and not a `valuation_result.html` call |
| `api/routes_valuation.py:148-154`, the cache read / miss branch inside `run_valuation` | `financials = _extraction_cache.pop(files)` else re-extract | the resolution must be unpacked here on both branches. This branch is not the result context either |

I checked whether a narrower change would do, and it will not. The obvious one —
`_extract_from_files` returns the `ProviderResolution` as a third tuple element — is a
change to a function that **is** in scope, but it breaks `assumptions_page:100`
(`financials, non_recurring = _extract_from_files(...)`) at run time, and repairing that
caller is out of scope. A new module-level parallel cache is out of scope for the same
reason as `:31`. Adding a helper function is "nothing else in this file" too.

**What I did instead, inside scope:** the limitation is now written where a reader of the
code meets it, not only in a journal entry. `api/routes_valuation.py:224-238` — the
comment on the line the reviewer flagged, which this unit introduced in round 1 — now
names the defect, names rule 4, and names the three lines above as the fix. No behaviour
changed.

I note for the record that the reviewer rated F3 `minor`, wrote "rule 6 is satisfied in
substance", accepted the round-1 reasoning, and proposed the same remedy I am naming
("carry the `ProviderResolution` in the cache alongside the financials, when backlog item
5 is opened"). So this is a scheduling question, not a disagreement.

### F4 · `note` · the module-level `_ENTRA_TOKEN_PROVIDER`

**Keeping it, unchanged.** `DefaultAzureCredential()` probes several credential sources
on construction and a valuation makes up to six model calls; rebuilding it per call pays
that probe six times, and `get_bearer_token_provider` already caches and refreshes the
token itself. It holds a credential *object*, supplies no figure and hides no missing
input, so it is neither rule 2 nor rule 3 — which is what the reviewer concluded. No
redesign.

---

## Done-criteria

Criterion 4 is the amended one; 11 and 12 are new in round 2. Criteria 1, 2, 3, 5, 6, 7,
9 and 10 were confirmed by the reviewer's own execution in round 1 and are **re-measured
here on the round-2 tree**, because two files moved since.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | one provider default, in one place | **pass** | `grep -rn 'provider: Provider = \|DEFAULT_EXTRACTION_PROVIDER' config.py ingestion/ api/ cli.py` → one definition, `config.py:29`; every other hit is `config.DEFAULT_EXTRACTION_PROVIDER` or prose. Output below |
| 2 | a real extraction completes through the gateway | **pass** | two fresh runs with numbers never used before, through `POST /valuation`. Output below |
| 3 | provider, model and transport in the CLI output | **pass** | first line of criterion 2's output, plus the credential source |
| 4 | **the three labels in a response the route returned** | **pass** | `POST /valuation -> 200`, block pasted below, `TestClient` |
| 5 | a missing credential stops, naming both remedies | **pass** | re-run on this tree; message below |
| 6 | the suite is unchanged | **pass** | `1 failed, 105 passed`; the failure is `test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` |
| 7 | lint unchanged | **pass** | `Found 5 errors.`, all `BLE001`, the same five files |
| 8 / 12 | types not worse, and nothing added | **pass, better than round 1** | **18** errors, was 33 at `HEAD`; `comm -13` against the baseline set is **empty**. Below |
| 9 | the rule-3 census did not rise | **pass** | **116** on this tree, **116** on the `HEAD` export |
| 10 | no token printed or logged | **pass** | `leak: False` over both rendered pages, by `re.search`; the `grep` hits are all labels, comments and token *counts* |
| 11 | a userinfo base URL leaks nothing | **pass** | 3 leaking labels under `.netloc`, **0** under `.hostname`. Below |

### Criterion 4 — `POST /valuation`, over a real ASGI request

`c:/tmp/r2_post_valuation.py`, `starlette.testclient.TestClient(app)`, run with
cwd `c:/tmp` (a Windows absolute path cannot be used: `run_valuation:152` treats `:` as
the year/path separator, so a drive letter would be parsed as a fiscal year — noted as a
finding below).

Nothing is stubbed. This is a real Foundry extraction, a real `normalize_financials`, a
real CAPM/WACC/DCF and a real yfinance market-data leg.

```
  Provider: CLAUDE  |  Model: claude-opus-5  |  Transport: Microsoft Foundry gateway
  (apm-use-claudecode-pd.azure-api.net)  |  Credential: Entra ID token via
  DefaultAzureCredential (`az login`), scope https://cognitiveservices.azure.com/.default
  PDF: r2_probe_filing.pdf (0.0 MB)
  [Pass 1] Extracting financials (all years) + B/S...
  [Pass 1] Tokens — input: 4,386  output: 959

  EXTRACTED DATA VALIDATION — ARITHMETIC CHECK
  Year    Field                   Stated     Derived       Diff  Status
  2022    Gross Profit             6,400       6,400         +0  OK
  2022    Oper. Income             3,900       3,900         +0  OK
  2022    Net Income               3,024       3,024         +0  OK
  2023    Gross Profit             7,000       7,000         +0  OK
  2023    Oper. Income             4,250       4,250         +0  OK
  2023    Net Income               3,312       3,312         +0  OK
  2024    Gross Profit             8,000       8,000         +0  OK
  2024    Oper. Income             5,000       5,000         +0  OK
  2024    Net Income               3,920       3,920         +0  OK
  [Pass 2] No non-recurring items identified

POST /valuation -> 200
content-type: text/html; charset=utf-8  bytes: 6999
GET  /            -> 500
GET  /assumptions -> 500

=== the extraction block, as the route rendered it ===
<h2>Extraction — who read the filing</h2>
        <table class="data-table">
            <tr><td>Provider</td><td>CLAUDE</td></tr>
            <tr><td>Model</td><td>claude-opus-5</td></tr>
            <tr><td>Transport</td><td>Microsoft Foundry gateway (apm-use-claudecode-pd.azure-api.net)</td></tr>
            <tr><td>Credential source</td><td>Entra ID token via DefaultAzureCredential (`az login`), scope https://cognitiveservices.azure.com/.default</td></tr>
        </table>

=== is an error page? ===
no alert-error block

=== credential leak check over the whole response ===
  leak: False          (re.search "sk-ant|Bearer |eyJ[A-Za-z0-9_-]{10,}")
```

Provider, model **and** transport are all in a body the route returned, with 200. That is
criterion 4, and criterion 3 for the CLI line, and criterion 10 on the rendered page.

### Criterion 2 — "it ran" is not evidence. The number on the page moves the number on the screen.

`STATUS.md` trap 2 says this pipeline will produce a share price out of zeros, so a 200
proves nothing on its own. Two documents, differing only in that **every income-statement
and cash-flow line is doubled** (balance sheet, share count and ticker identical), through
the same route:

| Document | `Total net revenues` on the page | `Implied Share Price` in the response |
|---|---|---|
| `c:/tmp/r2_probe_filing.pdf` | `13579  12000  11000` | **$48.12** |
| `c:/tmp/r2_probe_filing_2x.pdf` | `27158  24000  22000` | **$98.40** |

Doubling the cash flows a little more than doubles the price, because net debt is
unchanged at 2,500 while enterprise value doubles — so it is not a scaling artefact
either, it is the arithmetic the code says it is. **An input to the displayed figure came
from the document.**

**Both figures are meaningless as valuations and I am saying so loudly.** The statements
come from a synthetic probe document I generated (`c:/tmp/r2_make_filing.py`, header line
"SYNTHETIC PROBE DOCUMENT (NOT A REAL SEC FILING)"), not from a filing. Only the
market-data leg is real, and it is `MSFT`'s. This run is evidence about **the labelling
block and the route**, and about nothing else whatsoever. There is still no real 10-K on
this machine.

The nine arithmetic reconciliations at `+0` are a separate, useful fact: the extractor
read three full years off a filing-shaped page and its own validation pass agreed.

### Criterion 11 — the userinfo leak, before and after

`c:/tmp/r2_userinfo_leak.py`. The "round 1" column is `urlsplit(url).netloc` computed in
the script; the "now" column is the repository's own `resolve_provider(...).transport_label`.

```
  plain              'https://gw.example.net/foundry/anthropic/'
    round 1 (.netloc)   -> Microsoft Foundry gateway (gw.example.net)                        clean
    now     (.hostname) -> Microsoft Foundry gateway (gw.example.net)                        clean
  userinfo           'https://user:supersecret@gw.example.net/x'
    round 1 (.netloc)   -> Microsoft Foundry gateway (user:supersecret@gw.example.net)       *** LEAKS ***
    now     (.hostname) -> Microsoft Foundry gateway (gw.example.net)                        clean
  user only          'https://admin@gw.example.net/x'
    round 1 (.netloc)   -> Microsoft Foundry gateway (admin@gw.example.net)                  *** LEAKS ***
    now     (.hostname) -> Microsoft Foundry gateway (gw.example.net)                        clean
  userinfo + port    'https://user:supersecret@gw.example.net:8443/x'
    round 1 (.netloc)   -> Microsoft Foundry gateway (user:supersecret@gw.example.net:8443)  *** LEAKS ***
    now     (.hostname) -> Microsoft Foundry gateway (gw.example.net)                        clean
  the real gateway   'https://apm-use-claudecode-pd.azure-api.net/foundry/anthropic/'
    round 1 (.netloc)   -> Microsoft Foundry gateway (apm-use-claudecode-pd.azure-api.net)   clean
    now     (.hostname) -> Microsoft Foundry gateway (apm-use-claudecode-pd.azure-api.net)   clean
  labels carrying a credential — round 1: 3, now: 0
  empty-host stop: fired -> ANTHROPIC_FOUNDRY_BASE_URL is set but is not a URL with a host: 'not-a-url'
```

Three things are established and the third matters: the leak was real and I reproduced it;
it is closed on every form of userinfo, not only the reviewer's; **the label for the real
gateway is byte-identical**, so no evidence from round 1 is invalidated. The empty-host
stop (rule 3) still fires.

`.hostname` also drops the port. A port names nothing, and no Foundry endpoint here
carries one.

### Criterion 12 — the type gate, set-diffed against the baseline

Baseline is `git archive HEAD` exported to `c:/tmp/p2b_base_r2`, the reviewer's method.
Both runs use the gate from `docs/8-build/environment.md:148`. Line numbers stripped,
sorted, `comm`'d.

```
before: 33  after: 18
=== ADDED (comm -13: in after, not in before) ===
=== (end added) ===              <- empty
=== REMOVED (comm -23) === 15 lines:
  4 x api\routes_valuation.py: Argument 1/2 to "TemplateResponse" ... [arg-type]
 11 x ingestion\claude_extractor.py: Item "<block type>" ... has no attribute "text" [union-attr]
```

**33 → 18, nothing added.** The 11 `union-attr` are round 1's `content[0].text` fix. The
4 new ones are this round's: mypy had been reporting the starlette signature break as two
`arg-type` errors per call site, on exactly the two lines that were answering HTTP 500.
That is the third time in this unit that the type gate turned out to be reporting a live
crash inside a "not worse than 33" budget.

### Criterion 5 — the stop, re-run on this tree

All four credential variables cleared, then `extract_financials`:

```
ValueError raised before any network call:
No Anthropic credential resolved, so extraction cannot start. Either remedy is sufficient:
  (1) Set ANTHROPIC_API_KEY in .env or the system environment, to use the public Anthropic API; or
  (2) Set ANTHROPIC_FOUNDRY_BASE_URL (or ANTHROPIC_FOUNDRY_RESOURCE) to a Microsoft
      Foundry gateway and sign in with `az login`, so DefaultAzureCredential can issue an
      Entra ID token for scope https://cognitiveservices.azure.com/.default. A Foundry
      gateway also accepts ANTHROPIC_FOUNDRY_API_KEY instead of `az login`.
See docs/8-build/environment.md section 3.
```

### Criterion 1 — the full grep on this tree

```
config.py:29:DEFAULT_EXTRACTION_PROVIDER: Final = "claude"          <- the one definition
ingestion/claude_extractor.py:54    (module docstring, prose)
ingestion/claude_extractor.py:1079  f"provider='{config.DEFAULT_EXTRACTION_PROVIDER}'."   (error text)
ingestion/claude_extractor.py:1132  provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER
ingestion/claude_extractor.py:1151  (docstring)
ingestion/claude_extractor.py:1186  provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER
ingestion/claude_extractor.py:1210  (docstring)
api/routes_valuation.py:59          provider: Provider = config.DEFAULT_EXTRACTION_PROVIDER
api/routes_valuation.py:239         extraction = resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)
cli.py:94, 98, 100                  comment, argparse default, help text
```

---

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Dropped `"request": request` from both context dicts | starlette 1.6.0 does `context.setdefault("request", request)` itself — read from `inspect.getsource`, not assumed. Leaving it would be a duplicate binding of the same object | Keeping it is harmless but misleading: a reader would think the old form still applied. Verified by execution — the page renders and `{{ request }}`-dependent `base.html` works |
| `.hostname`, not a regex or a manual `split("@")` | `urlsplit` already parses userinfo correctly, including the `user@` form with no password and the `:port` suffix. A hand-rolled strip would miss one of the three | Proved on all three forms, criterion 11 |
| Kept the existing empty-host stop after switching to `.hostname` | `.hostname` returns `str \| None`; without the stop a `None` would become the label `"Microsoft Foundry gateway (None)"` — a guess, rule 3 | Re-measured: the stop still fires on `'not-a-url'` |
| **F3 escalated, not implemented** | The amendment's own instruction, and the three excluded line ranges listed above. Backlog item 5 owns the cache's value type | Implementing it means editing `assumptions_page` and the module global. That is widening my own scope, which the brief forbids in as many words |
| Added a `KNOWN LIMITATION` comment at `api/routes_valuation.py:229` instead | Rule 4: the next reader of that line should learn that the label is re-derived without having to find a journal entry. The line is one this unit wrote and is inside the result context | Silence was the alternative, and it is how the defect got past round 1 |
| Kept `_ENTRA_TOKEN_PROVIDER` | F4, one line, above | — |
| Left `GET /` and `GET /assumptions` at 500 | `P5-web-routes` owns `api/routes_upload.py:42` and `api/routes_valuation.py:114` | Two more lines would have fixed them, and that is the point: they are not mine |
| A **new** probe document with numbers never used before (13579 / 27158) | Round 1 used 4321 and 8765, the reviewer used 6174 and 2718. Re-running an old number proves the code recalls it, not that it reads it | The doubled variant is the sharper test: it moves the *displayed* figure, not just the extracted one |

**No code change in this round was made to reach a target number.** The only figures this
round produced are two probe valuations, and both are declared meaningless above.

---

## Rule 3 — what stops, and what does not

Only the values this round's three edits touch. Round 1's full table stands and was
checked by the reviewer.

| Value read | If it were missing | Evidence |
|---|---|---|
| `urlsplit(base_url).hostname` | **stops**, naming the variable and the offending value | `ValueError: ANTHROPIC_FOUNDRY_BASE_URL is set but is not a URL with a host: 'not-a-url'`, criterion 11 output |
| `request`, now the first argument to `TemplateResponse` | cannot be missing — it is a required route parameter FastAPI injects; absent it, the route does not start | `run_valuation(request: Request, ...)`, `api/routes_valuation.py:126` |
| `extraction`, the label object in the result context | cannot be `None` on the success branch — `resolve_provider` returns a `ProviderResolution` or raises. On the error branch it is explicitly `None` and the template's `{% if extraction %}` shows nothing rather than a blank table | `templates/valuation_result.html:117` |

**No "defaults to" row.** No added line matches the census pattern:

```
$ git diff -U0 HEAD -- config.py cli.py api/ ingestion/ templates/ | grep "^+" \
    | grep -E "if [^)]+ else 0(\.0)?\b|\bor +(0|0\.0)\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0|\*\*kwargs|getattr\("
exit=1        (no output)
```

Census: **116** on this tree, **116** on the `HEAD` export. Unchanged.

## Rules 1, 4, 5 and 6

- **Rule 1.** No prompt text, no schema field, no `_build_*_prompt` body was touched this
  round. The three edits are a URL parser, two response constructors and a comment. No
  escalation is due.
- **Rule 4.** F3 is a rule-4 gap and it is still open. It is now named in the code as well
  as here.
- **Rule 5.** No statement figure moved. `api/routes_valuation.py:197` (the yfinance
  `sharesOutstanding` fallback) is untouched and still a rule-5 break; backlog items 1 and
  12.
- **Rule 6.** Now satisfied **in an output a reader can actually reach**, which it was not
  at the end of round 1 — that is the whole content of F1.

---

## Measurements

| Gate | `HEAD` (`852f74b`, exported) | Round 1 | **Round 2** | Verdict |
|---|---|---|---|---|
| Tests | `1 failed, 105 passed` | `1 failed, 105 passed` | **`1 failed, 105 passed`** | identical failure set, `test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` |
| Lint | 5, all `BLE001` | 5 | **5, all `BLE001`** | same five: `routes_valuation.py:111, 247`, `cli.py:766`, `claude_extractor.py:934`, `tests/test_e2e_all_googl.py:106` |
| Types | 33 errors, 4 files | 22 | **18 errors, 4 files** | strict subset, `comm -13` empty |
| Rule-3 census | 116 | 116 | **116** | unchanged |
| `POST /valuation` | 500 (not measured at `HEAD`; the reviewer measured `GET /` at 500) | 500 | **200** | F1 |

Round-2 diff: **2 files, 3 edits** — `ingestion/claude_extractor.py` one expression plus
its comment, `api/routes_valuation.py` two `TemplateResponse` calls plus one comment. Both
files are in Files in scope. Whole-unit diff is 8 files, of which
`.agent/assignments/P2b-provider.md` is the orchestrator's own amendment, not mine.

**Figures this unit moved:** none in any valuation. The two probe share prices ($48.12 and
$98.40) come from a synthetic document and are evidence about the route, not about a
company.

**Cleanup.** `TestClient` opens no listening socket, so there is no server to stop;
`netstat` shows no listener on 8137, 8138, 8211 or 8212. All scratch is outside the
repository: `c:/tmp/r2_make_filing.py`, `c:/tmp/r2_make_filing_2x.py`,
`c:/tmp/r2_probe_filing.pdf`, `c:/tmp/r2_probe_filing_2x.pdf`,
`c:/tmp/r2_post_valuation.py`, `c:/tmp/r2_post_body_*.html`,
`c:/tmp/r2_userinfo_leak.py`, `c:/tmp/r2_mypy_{before,after}*.txt`,
`c:/tmp/p2b_base_r2/` (the `HEAD` export). Nothing was copied into the repository.

---

## What I did not do

- **Did not carry the resolution from the extraction to the page (F3).** Three excluded
  line ranges, listed under F3 with what each is needed for. Escalated.
- **Did not touch `api/routes_upload.py:42` or `api/routes_valuation.py:114`.** They are
  `P5-web-routes`, and `GET /` and `GET /assumptions` still return 500. Verified after my
  edit, not assumed.
- **Did not redesign `_ENTRA_TOKEN_PROVIDER`.** F4 says do not, and there is no reason to.
- **Did not touch `tests/`.** `ingestion/` and `api/` still have no tests, and
  `POST /valuation` — now the only working route — has none either.
- **Did not re-open anything the reviewer confirmed.** Criterion 2's method, the
  `_call_claude` block-selection fix, the Gemini path, the mypy subset claim and the census
  all stand as round 1 left them.
- **Saw and left** `ingestion/claude_extractor.py:637` (D&A subtracted in the parser,
  backlog item 10) and `:934` (blanket catch, item 8), both in the file I edited. Also
  `api/routes_valuation.py:31` (item 5), `:165-169` (item 6) and `:197` (items 1 and 12).
- **Did not update `STATUS.md`** or the journal index. Orchestrator's.

---

## Findings for the orchestrator

1. **`P5-web-routes` is now two lines, not four, and it is still the highest-value
   outage.** `POST /valuation` answers 200 on this tree; `GET /` and `GET /assumptions`
   answer 500, so a user cannot reach the working route through a browser — there is no
   page from which to submit the form. The remaining sites are
   `api/routes_upload.py:42` and `api/routes_valuation.py:114`, and the change is the
   same one I made: `TemplateResponse(request, "x.html", {...})`.

2. **`run_valuation:152` cannot accept a Windows absolute path.**
   `filings = _parse_files_param(files) if ":" in files else [(0, files)]` — a real upload
   path is `C:\...\uploads\x.pdf`, which contains `:`, so it takes the multi-file branch
   and `int("C")` raises `ValueError`, which the blanket `except` at `:247` turns into an
   error page reading `invalid literal for int() with base 10: 'C'`. I had to run my proof
   with `cwd=c:/tmp` and a bare filename to avoid it. This is a real defect on the only
   route that currently works, it is outside my scope, and it deserves its own item:
   the year/path separator needs to be something a Windows path cannot contain, or the
   split needs to be `rpartition`-based. **It may be masked today only because
   `routes_upload.py` is itself broken.**

3. **The type gate has now caught three live crashes while sitting inside a "≤ 33"
   budget** — 11 `union-attr` on `content[0].text` (round 1) and 4 `arg-type` on the two
   `TemplateResponse` calls (this round), each of which was an unconditional failure on
   every request. Reading the gate for *content* rather than for its count would have
   found the HTTP 500 two units ago. The 18 that remain include
   `api/routes_valuation.py:204-205` (`IncomeStatement | None`, `BalanceSheet | None`
   passed where non-optional is expected) — `STATUS.md` already flags that family.

4. **A tester assignment for the six environment-pure resolution functions is still
   unwritten** (round 1, finding 4) and criterion 11 has just added a seventh case worth
   locking down: `_foundry_endpoint_label` must never return userinfo. That is a
   three-line `monkeypatch.setenv` test and it would have caught F2 before a reviewer did.

5. **There is still no real filing on this machine** (round 1, finding 6). Every number in
   this entry came from a document I generated. The route, the transport, the labels and
   the arithmetic are proved; **the extractor's accuracy against a real 10-K is not.**
