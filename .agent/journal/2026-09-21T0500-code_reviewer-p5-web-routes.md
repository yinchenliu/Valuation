---
agent: code_reviewer
assignment: P5-web-routes
round: 1
verdict: approved
---

# Review of P5-web-routes, round 1

Programmer entry: `.agent/journal/2026-09-21T0400-programmer-p5-web-routes.md`

Baseline for every comparison below: my own `git archive d885d8d` export at
`c:/tmp/rev5`, unmodified. Every figure in this entry was produced by a command I ran.
Nothing is carried from the programmer's entry.

The diff is **2 files, 2 call sites, 11 insertions / 3 deletions**, 9 insertions being
comments. Both files are in Files in scope. `git diff --stat` and `git status --short`
show nothing else.

## The guard checks

Over `api/routes_upload.py` and `api/routes_valuation.py` only.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean |
| lookup with a fallback — `.get(k, 0)` | hit at `api/routes_valuation.py:201` (`info.get("sharesOutstanding", 0)`) — **pre-existing, backlog item 1, line not touched** |
| bare or-default — `or 0.0` | hit at `api/routes_upload.py:67` (`f"{year or 0}:{path}"`) — **pre-existing, backlog item 1, line not touched**; programmer declared it (its finding 3) |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output |

Both hits are answered in the programmer's entry and both are recorded. Neither line
appears in the diff (`git diff -U0` hunks are `routes_upload.py:39-48` and
`routes_valuation.py:111-117` only).

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `request`, now the first positional argument at both sites | cannot be missing — a declared route parameter FastAPI injects | `api/routes_upload.py:40`, `api/routes_valuation.py:76` |
| the `assumptions.html` context dict | unchanged; one key removed (`"request"`), none defaulted | diff shows one deletion, and starlette re-supplies it |
| the omitted context on `upload.html` | starlette constructs `{}` then `context.setdefault("request", request)` | `inspect.getsource(Jinja2Templates.TemplateResponse)` → `context.setdefault("request", request)`; signature is `(self, request: 'Request', name: 'str', context=None, …)`, starlette **1.6.0** |

No added line introduces a default. Rule-3 census `grep` from `rules.md`: **116 before,
116 after**, and the two sets are identical line-for-line after stripping line numbers
(`diff` → no output).

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | no financial figure in the diff |
| percentages converted at the route boundary, once | unchanged; the five falsy conversions at `routes_valuation.py:167-175` are untouched (backlog item 6) |
| falsy not treated as missing | no new instance; `git diff` adds no `if x` guard |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | unaffected — `analysis/` not in the diff |

## Done-criteria, re-run

All seven re-measured by me. **Baseline = my own `d885d8d` export, not the programmer's.**

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | `GET /` serves | 500/21 B → 200/1648 B; six markers ABSENT → FOUND | baseline **500, 21 B, `b'Internal Server Error'`**; tree **200, 1648 B**; all six markers ABSENT → FOUND | **yes** |
| 2 | `GET /assumptions` serves | 500 → 200 | baseline **500, 21 B**; tree **200** | **yes** (see N1 on the byte count) |
| 3 | no old-form `TemplateResponse` | 4 calls, all `(request, name, …)` | `grep -n "TemplateResponse(" api/*.py` → 6 hits, 4 calls, all `(request, name, …)`; `:42` and `:243` are comment text | **yes** |
| 4 | type gate improves, adds nothing | 18 → 14, `comm -13` empty | **18 → 14**; `comm -13` **empty**; `comm -23` is exactly the 4 `TemplateResponse` `[arg-type]` errors | **yes** |
| 5 | suite unchanged | `1 failed, 105 passed`; gate `105 passed` | baseline and tree both `1 failed, 105 passed`, **same single test** `test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`; gate form `105 passed` both | **yes** |
| 6 | lint unchanged | 5, all `BLE001` | both trees `Found 5 errors.`, same five files; only `routes_valuation.py:257 → :259` moved, from the added comment | **yes** |
| 7 | census ≤ 116 | 116 → 116 | **116 → 116**, sets identical | **yes** |

Criterion 4, my own set-diff:

```
before=18 after=14
--- ADDED (comm -13) ---            (empty)
--- REMOVED (comm -23) ---
api\routes_upload.py:    Argument 1 to "TemplateResponse" ... expected "Request[State]"
api\routes_upload.py:    Argument 2 to "TemplateResponse" ... expected "str"
api\routes_valuation.py: Argument 1 to "TemplateResponse" ... expected "Request[State]"
api\routes_valuation.py: Argument 2 to "TemplateResponse" ... expected "str"
```

By file, mine: before `projector` 4, `routes_upload` 3, `routes_valuation` 6,
`claude_extractor` 5 = 18; after 4 / 1 / 4 / 5 = 14. Identical to the programmer's table.

**One thing the programmer did not do, which I did: the error branch of
`assumptions_page`.** `GET /assumptions?ticker=ZZZ&files=2024:c:/tmp/does_not_exist.pdf`
→ **200**, 5798 B, rendering
`<div class="alert alert-error">[Errno 2] No such file or directory…</div>`. That is the
page that could not render before, and it is the concrete proof of the programmer's
"why it was a bare 500" paragraph: the handler under `routes_valuation.py:111`'s blanket
`except Exception` rendered through the very call that was broken.

**Scope, verified.** The two `valuation_result.html` calls at `:248` and `:261` have no
diff hunk; both still read `TemplateResponse(request, "valuation_result.html", {…})` and
both also omit `"request"` from the context, so this unit matches the shape
`P2b-provider` set rather than inventing a second one. `templates/` is untouched:
`grep -rn "request" templates/` → exit 1, `grep -rn "url_for" templates/` → exit 1.
**Both greps verified by me.** `ls templates/` is four files; none is in `git status`.

## Findings

### F1 — the entry's finding 4 is false, and it is contradicted by execution and by backlog item 26 · `minor`

The entry says `POST /upload` "passes exactly such a path — `C:\...\uploads\TICKER\x.pdf`"
and that `int("C")` will therefore raise on the `GET /` → `POST /upload` →
`GET /assumptions` journey. I exercised `POST /upload` over HTTP with
`api.routes_upload.UPLOAD_DIR` rebound to `c:/tmp/upload_sandbox` (nothing written into
the repository) and read the `Location` header:

```
well-named 2024 file    POST /upload -> 303  files='2024:C:\tmp\...\goog-10k-2024.pdf'
                        run_valuation:154 -> [(2024, 'C:\\tmp\\...\\goog-10k-2024.pdf')]   OK
no year in filename     POST /upload -> 303  files='0:C:\tmp\...\filing.pdf'
                        run_valuation:154 -> [(0, 'C:\\tmp\\...\\filing.pdf')]             OK
two files, one unnamed  POST /upload -> 303  files='2024:...pdf,0:...pdf'
                        run_valuation:154 -> [(2024, '...'), (0, '...')]                   OK
bare path (never built by the upload flow)
                        run_valuation:154 RAISED ValueError: invalid literal for int() with base 10: 'C'
```

**Evidence:** `api/routes_upload.py:67` — `f"{year or 0}:{path}"`; the year prefix always
supplies the first colon, and `str.partition` splits on the first colon only. The
orchestrator's measurement is right and the programmer's is wrong.

**Rule or document:** no rule in `rules.md` is broken, which is why this is not `major`.
It contradicts `docs/9-reference/refactor-backlog.md` item 26, whose **"Correction,
2026-09-21"** paragraph already records this exact disproof and credits the
`P2b-provider` round-2 review with it. The entry is also self-contradictory: its own
line 363 quotes `f"{year or 0}:{path}"` at `:61` while lines 403-406 assert a bare path
is passed.

**What would fix it:** withdraw finding 4, or restate it as what it actually is — item
26 is still worth fixing *in principle* (`":" in files` tests for a character every
Windows path contains), but it is **latent, not live**, and its rank does not change.
**The orchestrator should not re-rank item 26.**

### F2 — `POST /upload` was reachable; the stated reason for not reaching it does not hold · `minor`

The entry declines to exercise `POST /upload` because "it writes a PDF into
`<repo>/uploads/` … outside my Files in scope". Two things:

**Evidence:** `git check-ignore -v uploads` → `.gitignore:5:uploads/`, and
`ls -la uploads/` shows an empty, untracked, pre-existing directory — so a write there
is not a repository change at all. More to the point, one line in a scratch script
(`api.routes_upload.UPLOAD_DIR = <a path under c:/tmp>`) reaches the route without
touching the repository, as my F1 run demonstrates.

**Rule or document:** none. This is a judgement on evidence, not a rule break.

**What would fix it:** nothing in the code. It is recorded because it is the cause of
F1 — the one route the programmer did not run is the one route its false finding is
about, and the claim "I could only prove the journey by bypassing `POST /upload`" is
therefore also wrong.

### N1 — criterion 2's empty-form evidence does not paste its call, and its byte count is not reproducible · `note`

The assignment's criterion 2 says "paste the call". The entry pastes the call for the
real-extraction run (`GET /assumptions?ticker=PRBE&files=2024:probe_filing_2024.pdf`) but
not for the `5673 B` empty-form run. Byte length varies with the query string:
`/assumptions` → 5638, `?ticker=PRBE` → 5650, `?ticker=GOOGL&company_name=Alphabet+Inc`
→ 5682. **The status code, 200, reproduces on every one of them**, so the criterion is
met; only the byte figure is unverifiable. Breaks no rule.

## The four things the brief asked me to settle

1. **Before/after reproduced.** Confirmed above, against my own `d885d8d` export. 21
   bytes is literally `b'Internal Server Error'`.

2. **Nothing outside scope moved.** Confirmed. Both `templates/` greps return exit 1 and
   `templates/` has no diff.

3. **Set-diff.** Confirmed, my own baseline: 18 → 14, added empty, the 4 removed are
   exactly the errors on the two changed lines.

4. **The disputed claim — the orchestrator is right, the programmer is wrong.** See F1.
   No sequence of requests through `POST /upload` reaches the `ValueError`; the only way
   in is the legacy `file_path` branch at `api/routes_valuation.py:91-92` or a
   hand-built parameter, which is exactly what item 26 already says. **Item 26 stays
   `latent`.** (Both item 26 and the entry cite `:152`; the line is `:154` in this tree.)

5. **The unproved route.** See F2 — it was not the honest maximum. It was honestly
   *declared*, which is why it is `minor` and not worse.

6. **Your two documents. Both corrections are right; neither is charged to the unit.**

   - **The cache.** Verified: `api/routes_valuation.py:31` is the global, `:102` is
     `_extraction_cache[cache_key] = financials` inside `assumptions_page` — a **write**
     — and `:148` is `if files in _extraction_cache` inside `run_valuation` — the
     **read**. `assumptions_page` has no cache-hit branch. Pre-populating the cache
     would have changed nothing, so the programmer was right to ignore the instruction
     and run a real extraction instead, and right to correct rather than dispute it.
   - **The `STATUS.md` split.** The correct split at `d885d8d` is
     **`api/routes_valuation.py` 6, `ingestion/claude_extractor.py` 5,
     `analysis/projector.py` 4, `api/routes_upload.py` 3 = 18.** Your hypothesis about
     the cause is confirmed: including `note:` lines adds 2 to `routes_valuation` and 1
     to `routes_upload`, giving exactly `STATUS.md:43-44`'s `8 / 5 / 4 / 4 = 21`.
     `STATUS.md:166` is wrong in the same place — `routes_upload.py` held **3** errors,
     of which **2** were the template call and 1 is the surviving
     `routes_upload.py:27 Unsupported operand types for / ("Path" and "None")`.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 | `api/routes_upload.py:67` (`year or 0`), `api/routes_valuation.py:201` (`.get(…, 0)`) — the two `api/` census sites | no |
| 5 | module-global cache, `api/routes_valuation.py:31/102/148` | no — read only |
| 6 | five falsy-as-missing conversions, `api/routes_valuation.py:167-175` | no |
| 7 | duplicated pipeline | no |
| 8 | blanket `except Exception`, `api/routes_valuation.py:111` and `:259` | no — the comment above `:117` shifted `:257` to `:259`, the block itself is byte-identical |
| 11 | the remaining 14 type errors | no — 4 removed, 0 added |
| 26 | `api/routes_valuation.py:154` | no |
| 27 | the two 500s | **yes — this unit closes it** |

I saw each of these and each is already recorded. Items 1, 5, 6, 7, 8 and 11 are named
out of scope by the assignment.

## Verdict

`approved`

The code is right and I proved it myself rather than reading it: all seven criteria
re-measured against my own `d885d8d` export and all seven match, the diff is confined to
the two named call sites, `templates/` is untouched and both greps behind that claim
check out, and the two `valuation_result.html` calls `P2b-provider` owns are byte
identical. `GET /` returns 200 and serves the upload form for the first time in this
environment, and the error branch of `GET /assumptions` — which the programmer did not
exercise and I did — now renders too. No rule in `rules.md` is broken by any added line
and the rule-3 census is unmoved at 116, set-identical.

Two `minor` findings stand and neither forces a revision: the entry's **finding 4 is
false** (F1) and the route it is about was reachable (F2). **The orchestrator must not
act on the programmer's finding 4 and must not re-rank backlog item 26**, which already
records the correct answer. If the unit is re-dispatched for any other reason, F1 should
be withdrawn in the revision entry.

One thing worth carrying forward, and the assignment predicted it: `import app`
succeeding is no longer the strongest check on the web half — it passed through the
entire outage. `TestClient(app.app).get('/').status_code == 200` is, and `api/` still
has no test that asserts it.
