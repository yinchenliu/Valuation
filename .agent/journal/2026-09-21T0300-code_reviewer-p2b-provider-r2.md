---
agent: code_reviewer
assignment: P2b-provider
round: 2
verdict: approved
---

# Review of P2b-provider, round 2

Programmer entry: `.agent/journal/2026-09-21T0200-programmer-p2b-provider-r2.md`
Round-1 review: `.agent/journal/2026-09-21T0130-code_reviewer-p2b-provider.md`

Reviewed at `852f74b` + working tree. Baseline for every comparison is `git archive HEAD`
exported to `c:/tmp/rv2_base`. The repository tree is unchanged by me — `git status
--short` shows the unit's seven files plus the orchestrator's own assignment and the
journal entries.

Round 2 is three edits in two files. **Everything the amendment asked for is done or
correctly escalated, and I re-ran all of it.**

## The risky change: dropping `"request": request` — verified from source, safe

| Check | Result |
|---|---|
| starlette version | `1.6.0` (also fastapi `0.141.1`, jinja2 `3.1.6`) |
| does `TemplateResponse` supply `request` itself? | **yes** — `.venv/Lib/site-packages/starlette/templating.py:143-145`: `context = context or {}` then `context.setdefault("request", request)`, read with `inspect.getsource`, not from the entry |
| any template reading `request`? | **none** — `rg "request" templates/` → no matches, including `base.html` |
| does the page actually render? | yes, twice, 200, 6,985 and 7,003 bytes (below) |

Both belts hold: starlette rebinds it, and nothing in `templates/` uses it anyway. Not a
finding.

## The guard checks

Run over the seven Files in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | 5 hits, **all pre-existing** (`claude_extractor.py:356`, `cli.py:228,410,708,716`); none added |
| lookup with a fallback — `.get(k, 0)` | 64 in `claude_extractor.py`, 2 in `routes_valuation.py`, 1 in `cli.py` — all pre-existing (backlog item 1); every **added** one is `os.environ.get(X, "")`, answered in the programmer's round-1 rule-3 table |
| bare or-default — `or 0.0` | 3, all in `_call_gemini`'s untouched retry block |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | 3, all pre-existing |
| dict of functions keyed by data | clean |
| model client outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → 0 |

No added line carries a rule-3 form:

```
git diff -U0 HEAD -- config.py cli.py api/ ingestion/ templates/ requirements.txt \
  | grep "^+" | grep -E "if [^)]+ else 0(\.0)?\b|\bor +(0|0\.0)\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0|\*\*kwargs|getattr\("
  → exit=1, no output
```

## Rule 3, by reading — only the three values round 2 touches

| Value | Stops and names it? | Evidence |
|---|---|---|
| `urlsplit(base_url).hostname` returning `None` | **yes** — the empty-host stop was kept after the `.netloc` → `.hostname` switch | `ValueError: ANTHROPIC_FOUNDRY_BASE_URL is set but is not a URL with a host: 'not-a-url'`, re-run by me |
| `request` as the first `TemplateResponse` argument | cannot be missing — FastAPI injects it; the route does not start without it | `routes_valuation.py:126` |
| `extraction` in the result context | success branch: `resolve_provider` returns a `ProviderResolution` or raises. Error branch: explicitly `None`, and `templates/valuation_result.html` guards with `{% if extraction %}` — it shows nothing rather than a blank table | read + both branches rendered |

None of the three produces a number when absent.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | round 2 moves no figure; the probe EV/equity/price below are consistent in millions and per-share |
| percentages converted at the route boundary, once | `routes_valuation.py:161-176` untouched |
| falsy not treated as missing | no new instance; the five at `:165-169` are untouched (backlog item 6) |
| `analysis/` / `models/` untouched | `git diff --stat HEAD -- models/ analysis/` → empty |
| LLM boundary | no prompt text, no schema field, no `_build_*_prompt` body changed — the only `_FINANCIALS_SYSTEM_PROMPT` / `_NRI_SYSTEM_PROMPT` diff lines are call-site argument changes. No escalation due |

## Scope

| File changed | In scope? |
|---|---|
| `requirements.txt`, `config.py`, `ingestion/claude_extractor.py`, `api/routes_valuation.py`, `cli.py`, `templates/valuation_result.html`, `docs/8-build/environment.md` | **yes**, all seven named |
| `api/routes_upload.py` | **not touched** — `git diff --stat HEAD -- api/routes_upload.py` empty; `:42` still the old call |
| `api/routes_valuation.py:114` | **not touched** — no diff hunk goes near it; `git diff -U0` hunks are `@@ -8,0`, `-15`, `-45`, `-48`, `-55`, `-57`, `-209,2`, `-217,0`, `-221,2`, `-230,0` |

Both `P5-web-routes` sites are intact. No scope finding.

## Done-criteria, re-run

Every row below I executed. Nothing is taken from the entry.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | one provider default | 1 definition | `config.py:29` only; all 11 other hits are `config.DEFAULT_EXTRACTION_PROVIDER` or prose | **yes** |
| 2 | real extraction through the gateway | `13579`/`27158` | **my own document, numbers never used before** — `15,400/14,000/12,500` and the 2× variant, both read back with 9/9 arithmetic reconciliations at `+0` | **yes** |
| 3 | provider, model, transport in CLI output | pass | `Provider: CLAUDE \| Model: claude-opus-5 \| Transport: Microsoft Foundry gateway (apm-use-claudecode-pd.azure-api.net) \| Credential: Entra ID token via DefaultAzureCredential (\`az login\`), scope …` | **yes** |
| 4 | three labels in a response the route returned | `POST /valuation -> 200` | **200 twice**, block below, `leak: False` both | **yes** |
| 5 | missing credential stops, both remedies | pass | re-ran with all four vars cleared → `ValueError` naming `ANTHROPIC_API_KEY` **and** `az login`, before any network call | **yes** |
| 6 | suite unchanged | `1 failed, 105 passed` | tree **and** `HEAD` export: `1 failed, 105 passed`, identical failure *set* — `test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` | **yes** |
| 7 | lint unchanged | 5 `BLE001` | 5 on both trees, same five files; **one line number in the entry is wrong — F5** | **yes**, with F5 |
| 8 / 12 | types better, nothing added | 33 → 18, `comm -13` empty | 33 → 18; `comm -13` **empty**; 15 removed = 4 `arg-type` on `TemplateResponse` + 11 `union-attr` on `content[0].text` | **yes** |
| 9 | census did not rise | 116 → 116 | 116 on the tree, 116 on the `HEAD` export | **yes** |
| 10 | no token printed or logged | 0 | `leak: False` on both rendered bodies; all 40 `token` hits in `ingestion/ api/ cli.py` are labels, comments or token **counts** | **yes** |
| 11 | userinfo base URL leaks nothing | 3 → 0 | reproduced on all four forms + the real gateway — below | **yes** |

### Criterion 4 and 2, reproduced — `POST /valuation` over a real ASGI request

My own synthetic probe, built by `c:/tmp/rv2_make_filing.py` (there is no PDF library on
this machine; `c:/tmp/rv2_mkpdf.py` writes the PDF by hand). `starlette.testclient.
TestClient(app, raise_server_exceptions=False)`, nothing stubbed — real Foundry
extraction, real `normalize_financials`, real CAPM/WACC/DCF, real yfinance leg.

I passed `files="2024:C:\tmp\rv2_probe.pdf"` — a **Windows absolute path with the
year prefix the upload route actually produces** — so both runs went through
`_parse_files_param` on a cache miss. It works. See F6.

```
GET  /            -> 500        (P5-web-routes, expected)
GET  /assumptions -> 500        (P5-web-routes, expected)
1x: POST /valuation -> 200   6985 bytes   leak: False
2x: POST /valuation -> 200   7003 bytes   leak: False

<h2>Extraction — who read the filing</h2>
        <table class="data-table">
            <tr><td>Provider</td><td>CLAUDE</td></tr>
            <tr><td>Model</td><td>claude-opus-5</td></tr>
            <tr><td>Transport</td><td>Microsoft Foundry gateway (apm-use-claudecode-pd.azure-api.net)</td></tr>
            <tr><td>Credential source</td><td>Entra ID token via DefaultAzureCredential (`az login`), scope https://cognitiveservices.azure.com/.default</td></tr>
        </table>
```

**The arithmetic, checked and not merely shaped.** Two documents identical but for every
income-statement and cash-flow line doubled; balance sheet, share count and ticker
identical. I pinned `beta_override`, `risk_free_rate`, `equity_risk_premium` and
`cost_of_debt_override` on the form, so WACC is identical across the two runs and the
relationship is exactly predictable — otherwise doubling *interest expense* also moves
the cost of debt, which is why the programmer's own increment (2.16) is not a round
number.

```
EV      1x= 84,682   2x=169,363   ratio=1.999988   (2.000000 up to the page's integer rounding)
NetDebt 1x=  2,500   2x=  2,500   identical, as designed
Shares          1,000  (from the document, both)
Price   1x= $82.18   2x=$166.86   ratio=2.0304
predicted 2x = 2*p1 + netdebt/shares = 2*82.18 + 2.5000 = 166.8600
observed  2x = 166.86                                     delta = +0.0000
```

WACC 9.44% and cost of debt 5.00% on **both** pages, so the only thing that moved is the
document. The displayed figure tracks the page exactly, and "a little more than double"
is confirmed to be precisely `net_debt / shares` — the mechanism the entry names.

**Both prices are meaningless as valuations and I repeat that deliberately.** The
statements come from a document I invented, headed `SYNTHETIC PROBE DOCUMENT (NOT A REAL
SEC FILING)`; only the market leg is real and it is `MSFT`'s. This is evidence about the
route and the label, and about nothing else. There is still no real 10-K on this machine.

### Criterion 11, reproduced across all three userinfo forms

`c:/tmp/rv2_userinfo.py`, calling the repository's own `resolve_provider(...).
transport_label`:

```
plain           https://gw.example.net/foundry/anthropic/
  netloc -> Microsoft Foundry gateway (gw.example.net)                        clean
  now    -> Microsoft Foundry gateway (gw.example.net)                        clean
userinfo        https://user:supersecret@gw.example.net/x
  netloc -> Microsoft Foundry gateway (user:supersecret@gw.example.net)       *** LEAKS ***
  now    -> Microsoft Foundry gateway (gw.example.net)                        clean
user only       https://admin@gw.example.net/x
  netloc -> Microsoft Foundry gateway (admin@gw.example.net)                  *** LEAKS ***
  now    -> Microsoft Foundry gateway (gw.example.net)                        clean
userinfo+port   https://user:supersecret@gw.example.net:8443/x
  netloc -> Microsoft Foundry gateway (user:supersecret@gw.example.net:8443)  *** LEAKS ***
  now    -> Microsoft Foundry gateway (gw.example.net)                        clean
real gateway    https://apm-use-claudecode-pd.azure-api.net/foundry/anthropic/
  now    -> Microsoft Foundry gateway (apm-use-claudecode-pd.azure-api.net)   clean

leaking labels  before: 3   now: 0
real-gateway label byte-identical to round 1: True
empty-host stop fired -> ANTHROPIC_FOUNDRY_BASE_URL is set but is not a URL with a host: 'not-a-url'
```

All four claims hold, including the byte-identical one — **no round-1 evidence is
invalidated.**

### The F3 escalation — I tested the breakage claim and it is true

The programmer refused to widen scope and named the narrow alternative it rejected. I
executed that alternative rather than reading it. `c:/tmp/rv2_f3_narrow.py` makes
`_extract_from_files` return the `ProviderResolution` as a third element and calls
`assumptions_page`:

```
assumptions_page error field -> 'too many values to unpack (expected 2, got 3)'
assumptions_page defaults    -> {}
cache populated?             -> {}
failing line -> api/routes_valuation.py:100: financials, non_recurring = _extract_from_files(...)
```

Worse than a crash: `assumptions_page`'s blanket `except` at `:111` swallows it into an
error page, and `_extraction_cache` is never populated. Repairing `:100` is outside
"Nothing else in this file". And even repaired, the resolution still has to survive
`_extraction_cache` (`:31`, `dict[str, FinancialStatements]`) and be unpacked on both
branches of `:148-154` — neither is `_extract_from_files`, the result context, nor a
`valuation_result.html` call. **All three line references in the entry are accurate**
(`:31` is the cache, `:102` is the write, `:148-154` is the read/miss branch). The
escalation was correct and refusing to widen was right.

The `KNOWN LIMITATION` comment at `api/routes_valuation.py:228-238` is **an adequate
record, not an excuse**: it sits on the line this unit wrote, names the defect, names
rule 4, names the three lines and names backlog item 5 as the owner. A reader of that
line learns the label is a re-derivation without finding a journal entry. That is the
right shape for a deferral.

## Earlier findings

| # | Outcome | Note |
|---|---|---|
| F1 | **fixed** | Two `TemplateResponse` calls moved to `(request, name, context)`; `POST /valuation` → **200** twice on my own probe, full label block, `leak: False`. `GET /` and `GET /assumptions` still 500 and both out-of-scope sites untouched |
| F2 | **fixed** | `.netloc` → `.hostname` at `claude_extractor.py:993`; 3 leaking labels → 0 across all three userinfo forms; empty-host stop still fires; real-gateway label byte-identical |
| F3 | **not_fixed — escalation accepted** | The amendment authorised exactly this ("say exactly which file would need to change and stop"). I verified the narrower option breaks `assumptions_page:100` at run time. Does not block: rule 4's output-side trace gap is named in `rules.md` itself as pre-existing repository work, and this unit **narrowed** it — it added provenance where the page had none |
| F4 | **answered** | `_ENTRA_TOKEN_PROVIDER` kept, one-line reason given (`DefaultAzureCredential()` probes on construction; up to six calls per valuation). Breaks no rule |
| F5 (r1) | **note stands, not this unit's** | backlog item 1 producing a plausible non-zero `other_operating_activities` — the orchestrator has since written it into item 1 |

## Findings

### F5 — one lint line number in the entry is wrong · `note`

**Evidence:** the entry's Measurements table and its F3 section both say the blanket
catch is at `routes_valuation.py:247`. `.venv/Scripts/python.exe -m ruff check .` reports
`--> api\routes_valuation.py:257:12`; line 247 is inside the `KNOWN LIMITATION` comment.

**Rule or document:** none — the *set* of five `BLE001` sites is correct and I confirmed
it against the `HEAD` export. Only the printed line number is stale by 10.

**What would fix it:** nothing in the code. Noted so the next reader does not chase `:247`.

### F6 — the Windows-path defect is real, but its stated trigger is wrong, and backlog item 26 inherits the error · `note`

**Evidence:** the entry (finding 2) and `docs/9-reference/refactor-backlog.md:540` both
say *"every saved upload path on this platform contains a colon"*, so a real upload
reaches `int("C")`. It does not. `api/routes_upload.py:61` builds the parameter as
`f"{year or 0}:{path}"`, so the year prefix absorbs the first colon:

```
upload flow  '2024:C:\Users\...\uploads\GOOG\goog.pdf' -> [(2024, 'C:\\Users\\...\\goog.pdf')]   OK
legacy flow  'C:\Users\...\uploads\GOOG\goog.pdf'      -> ValueError: invalid literal for int() with base 10: 'C'
```

My two criterion-4 runs above both went through `_parse_files_param` on a **cache miss**
with a Windows absolute path and returned 200 — direct execution evidence that the
normal encoding survives `:152`.

The defect is genuine, but it fires only when `files` carries **no** year prefix, which
is the legacy `file_path` branch (`routes_valuation.py:92`, surfaced into the form at
`:118` and `templates/assumptions.html:18`) or a hand-built URL. So item 26's
"refresh a working valuation and get an integer-parsing message" cost story does not
hold for the upload flow, and its `stopping` rank may be too high.

**Rule or document:** none — this is the accuracy of a backlog entry, not code. The
programmer's cwd-relative workaround was also unnecessary.

**What would fix it:** the orchestrator amends item 26's trigger and cost paragraphs.
**Both files are outside my write scope**; this is a report, not a change. The fix
itself — do not encode on a character a path can contain — is right as written.

## Pre-existing, already recorded — not findings against this unit

The assignment names items 1, 5, 6, 7, 8, 10 and 20 as out of scope. I saw all seven and
re-report none. Item 5 is load-bearing in the F3 argument, which is not the same as
fixing it.

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 — zero defaults | `claude_extractor.py:617-683` | **no** — line-shifted only |
| 5 — module-global extraction cache | `routes_valuation.py:31` | **no** — cited by F3, unchanged |
| 6 — falsy treated as missing | `routes_valuation.py:165-169` | **no** |
| 7 — duplicated pipeline | `cli.py` / `api/` | **no** |
| 8 — blanket catches | `routes_valuation.py:111, 257`, `claude_extractor.py:934` | **no** — ruff reports the same five |
| 10 — D&A in the parser | `claude_extractor.py:637` | **no** |
| 20 — NaN beta | `analysis/` | **no** — `analysis/` untouched |
| 26 — Windows path as fiscal year | `routes_valuation.py:152` | **no** — already recorded by the orchestrator; see F6 for a correction to its text |

## Verdict

`approved`

Every round-1 finding is answered. F1 is fixed and I proved it the hard way: two probe
documents differing only in doubled statements both returned `POST /valuation -> 200`
with the full Provider/Model/Transport/Credential block and `leak: False`, and the
displayed share price moved from $82.18 to exactly `2 × 82.18 + net_debt/shares` —
`166.86`, delta `+0.0000`, with WACC and cost of debt pinned identical. The figure tracks
the document, not the run. **Both prices are from a document I invented and mean nothing
as valuations.** F2 is fixed on all three userinfo forms with the real gateway's label
byte-identical, so no round-1 evidence falls. F3's escalation is correct, and I confirmed
by execution that the narrow alternative breaks `assumptions_page:100` inside a blanket
catch; the in-code `KNOWN LIMITATION` is a record, not an excuse. The risky change —
dropping `"request": request` — is verified from `starlette/templating.py:145`, and no
template reads `request` in any case. Gates re-measured as sets: tests `1 failed, 105
passed` with the identical failing test on both trees, lint 5 `BLE001` at the same five
files, types 33 → 18 with `comm -13` empty, census 116 → 116. `GET /` and `GET
/assumptions` are still 500 and both `P5-web-routes` sites are untouched. Nothing in this
diff breaks a rule in `docs/2-rules/rules.md`. F5 and F6 are `note`s: a stale line number,
and a correction the orchestrator should fold into backlog item 26's text — neither is a
change to this unit.

**Scratch, all outside the repository:** `c:/tmp/rv2_base` (HEAD export),
`c:/tmp/rv2_mkpdf.py`, `c:/tmp/rv2_make_filing.py`, `c:/tmp/rv2_probe.pdf`,
`c:/tmp/rv2_probe_2x.pdf`, `c:/tmp/rv2_post.py`, `c:/tmp/rv2_body_{1x,2x}.html`,
`c:/tmp/rv2_userinfo.py`, `c:/tmp/rv2_f3_narrow.py`, `c:/tmp/rv2_{before,after}.txt`.
`TestClient` opens no listening socket; no server was started and none is running. The
repository tree is exactly as the programmer left it.
