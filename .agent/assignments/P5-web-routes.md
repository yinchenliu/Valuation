---
id: P5-web-routes
phase: 5 — make the web half work at all
agent: programmer
depends_on: [P2b-provider]
---

# Repair the last two template calls, so every route serves a page

## Objective

**The web application returns HTTP 500 on every route, and has done since before this
build started.**

`starlette` 1.6.0 requires `TemplateResponse(request, name, context)`. This repository
used the removed `TemplateResponse(name, context)` form at four call sites, which passes
a `str` where a `Request` belongs and a `dict` where a `str` belongs.

Measured by the orchestrator at `852f74b`:

```
the form this repository used  -> TypeError: cannot use 'tuple' as a dict key
                                  (unhashable type: 'dict')
the form starlette 1.6.0 needs -> rendered OK, status 200
```

`api/routes_upload.py`'s call is **unchanged since `bc19431`**, the first commit this
build measured. So `app.py` — one of the two entry points this product ships — has
never served a page in this environment.

**Nothing in the docs recorded it.** `STATUS.md` named a different mypy error as "the
live defect" while these four sat in the same mypy output. That is the miss this unit
closes.

**Two of the four are already repaired.** `P2b-provider` took the two that render
`valuation_result.html`, because its own criterion 4 could not be proved without them.
**This unit takes the remaining two.**

## What is already true — verify, do not redo

| Fact | Evidence |
|---|---|
| `starlette` is **1.6.0**, signature `TemplateResponse(self, request, name, context=None, …)` | `inspect.signature` |
| the two calls left | `api/routes_upload.py:42` and the `assumptions.html` call in `api/routes_valuation.py` |
| the two `valuation_result.html` calls already work | `P2b-provider` round 2; `POST /valuation` → 200 |
| `starlette.testclient.TestClient` imports, `httpx` 0.28.1 is installed | a route runs with no port, no key, no network |
| `import app` succeeds and registers all four routes | `P2-hygiene` criterion 6 |

**Re-measure `grep -n "TemplateResponse(" api/*.py` before you start.** `P2b-provider`
moved lines in `api/routes_valuation.py`, so the numbers above will have shifted.

## What to do

1. **Change the two remaining calls to `TemplateResponse(request, name, context)`.**

   Move `request` out of the context dict and into the first argument. **Leave
   `"request"` in the context as well if a template reads it** — check each template
   before removing it.

2. **Change nothing else in either file.** The blanket `except Exception`, the
   module-global cache, the five falsy-as-missing conversions and the yfinance fallback
   all stay. This unit is two lines plus its proof.

3. **Prove both routes over HTTP, not by reading.** `GET /` needs nothing.
   `GET /assumptions` reads the module-global extraction cache at
   `api/routes_valuation.py:25`; populate it in your scratch script rather than
   changing the route. Report the status code of each.

   Write any scratch script under `c:/tmp/`.

4. **Say which routes you could not reach**, so the tester that follows knows what is
   left to lock.

## Files in scope

- `api/routes_upload.py`
- `api/routes_valuation.py` — **the `assumptions.html` `TemplateResponse` call only.**
- `templates/` — **only** if a template reads `request` from the context.

**Nothing else.**

## Out of scope

- **`tests/`** — your write guard denies it. A tester locks these routes next; that is
  the test that would have caught this in the first place.
- **`ingestion/`, `analysis/`, `models/`, `config.py`, `cli.py`.**
- **The two `valuation_result.html` calls.** `P2b-provider` owns them; do not touch
  them even if they look wrong to you. If they are wrong, that is a finding.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the front page serves | **200**, and the body holds the upload form | `TestClient(app).get("/")` |
| 2 | the assumptions page serves | **200**, with a populated cache | `TestClient(app).get("/assumptions?…")`; paste the call |
| 3 | no `TemplateResponse` call uses the old form | 0 | `grep -n "TemplateResponse(" api/*.py`, read each |
| 4 | the type gate improves, and adds nothing | fewer errors, remainder a strict subset | `mypy …`, set-diffed against the tree before your change |
| 5 | the suite is unchanged | **1 failed, 105 passed**; gate form **105 passed** | `pytest -q` and `pytest -q --ignore-glob="*_rule3_red.py"` |
| 6 | lint unchanged | 5 errors, all `BLE001` | `.venv/Scripts/python.exe -m ruff check .` |
| 7 | the census did not rise | ≤ 116 | the grep in `docs/2-rules/rules.md` |

**Criterion 1 is the unit.** Until the front page returns 200, a user cannot start.

## Citations

- `docs/9-reference/refactor-backlog.md` item **11** — the type errors, of which these
  were always the most serious and were ranked below a different one.
- `docs/3-architecture/entry-points.md` — the routes.
- `.agent/journal/2026-09-21T0030-programmer-p2b-provider.md` — the unit that found
  this.
- `.agent/journal/2026-09-21T0130-code_reviewer-p2b-provider.md` — the confirmation on
  an unmodified baseline export, and which sites sit in which scope.

## Known open items

- **This unit changes what a gate means.** After it, `import app` succeeding is no
  longer the strongest available check; a route returning 200 is. Say so in your entry.

- The failing calls sit inside a function whose blanket `except Exception` renders the
  error onto a page — using the same broken call. **That is why the failure surfaced as
  a bare 500 rather than as a message.** Worth one line in your entry; it is the
  clearest argument in this repository for backlog item 8.

## Backlog items this unit is NOT fixing

- **Item 5** — the module-global extraction cache. You read it; you do not repair it.
- **Item 6** — falsy treated as missing, five times.
- **Item 7** — the duplicated pipeline.
- **Item 8** — the blanket catches, including the one around your change.
- **Item 1** — the zero defaults, including `info.get("sharesOutstanding", 0)`.
- **Item 11** — the remaining type errors. Criterion 4 asks only that the count fall.
