---
id: P5b-route-tests
phase: 5 — make the web half work at all
agent: tester
depends_on: [P5-web-routes]
---

# Lock every route at its status code, so a total outage cannot pass the gate again

## Objective

The web application returned HTTP 500 on every route from `bc19431` to `d885d8d`.
**Nothing in the suite noticed.** `import app` succeeded throughout, and it was used as
a done-criterion during this build.

Four routes now serve. This unit writes the test that would have caught the outage, so
the next one cannot survive a green gate.

`docs/5-testing/strategy.md` section 3 says the model clients and `yfinance` are
**boundaries** — fake them. `starlette.testclient.TestClient` opens no socket and
`httpx` 0.28.1 is installed, so every route below runs with no key, no network and no
port.

## What is already true — verify, do not redo

Measured at `b2ab32f`, 2026-09-21.

| Fact | Command |
|---|---|
| `GET /` → **200**, 1648 bytes | `TestClient(app.app, raise_server_exceptions=False).get('/')` |
| `GET /assumptions` → **200** | same |
| `POST /valuation` → **200** with the provider/model/transport block | `P2b-provider` round 2 |
| `pytest -q --ignore-glob="*_rule3_red.py"` → **105 passed** | the gate |
| `ruff check tests` → 1 error, the deferred `BLE001` | |

## What to do

1. **Write `tests/unit/test_routes.py`.** One test per route, each asserting the status
   code **and** something in the body that proves the right page rendered. A status code
   alone does not distinguish the success page from the error page — both return 200 now.

   | Route | Expect | Also assert |
   |---|---|---|
   | `GET /` | 200 | the upload form and its target |
   | `GET /assumptions` | 200 | the derived defaults reached the form |
   | `POST /upload` | a redirect | the `Location` header carries `files=` |
   | `POST /valuation` | 200 | the provider, model and transport labels |

2. **Fake the two boundaries, and fake nothing else.** Both are reachable by name from
   the route modules, so `monkeypatch` reaches them without touching any source file:

   - `api.routes_valuation.extract_financials` and `.extract_multi_year` — the model.
   - `api.routes_valuation.fetch_price_data` — `yfinance`.
   - `api.routes_upload.UPLOAD_DIR` — redirect to pytest's `tmp_path` so `POST /upload`
     writes nothing into the repository. `uploads/` is gitignored and untracked; keep it
     that way.

   **Build the `FinancialStatements` your fake returns by hand**, with the few fields
   the route reads. Do not load a `.pkl`; `STATUS.md` section 6 says why.

3. **Lock the error branch too, and this is the part that matters most.** The outage
   surfaced as a bare 500 precisely because the error page rendered through the same
   broken call. So for each route, make the underlying call raise and assert the route
   returns **200 with the error visible in the body** — not 500, and not a blank page.

   The reviewer of `P5-web-routes` proved this is reachable: `assumptions_page`'s error
   branch renders `<div class="alert alert-error">[Errno 2] No such file…</div>`.

4. **Prove the test is falsifiable.** Copy `api/routes_upload.py` to `c:/tmp/`, revert
   its `TemplateResponse` call to the removed `(name, context)` form, and run your tests
   against the copy. **State how many assertions go red.** If the answer is zero, the
   test would not have caught the defect it was written for, and the number is what
   tells the next reader that.

5. **Do not assert a fallback.** `docs/5-testing/strategy.md` section 2. In particular
   `POST /valuation` reads a cache that is `pop`ped on read — backlog item 5. **Do not
   write a test that depends on the pop**, or item 5's fix turns it red.

## Files in scope

- `tests/unit/test_routes.py` (new)
- `tests/unit/conftest.py` (new, only if fixtures are shared across files)

**Nothing else.** Do not edit any existing test file, and do not touch
`tests/unit/test_dcf_rule3_red.py` — it states backlog item 2 and must stay red.

## Out of scope

- Every implementation file. If a route cannot be tested without a code change, **that
  is your finding** — report it.
- Backlog items 5, 6, 8, 26. You work around item 5; you do not repair it.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | all four routes are locked on status **and** body | 4 routes | your entry's table |
| 2 | the error branch of each template-rendering route is locked at 200 | 3 routes | same |
| 3 | the suite passes | **105 + your tests**, 0 failed | `pytest -q --ignore-glob="*_rule3_red.py"` |
| 4 | the whole suite is unchanged in shape | **1 failed**, the rest pass | `pytest -q` |
| 5 | **the test is falsifiable** | ≥ 1 assertion red against the reverted copy; state how many | your scratch run, output in your entry |
| 6 | no test needs a key, a PDF or the network | passes with both keys unset | criterion 3's command |
| 7 | nothing was written into the repository | `uploads/` still empty and untracked | `git status --short` and `ls uploads/` |
| 8 | `tests/` lints with exactly 1 error | 1, the deferred `BLE001` | `ruff check tests --output-format concise` |

**Criterion 5 is the unit.** A route test that stays green when the route is broken is
worse than no route test, because it reads as coverage.

## Citations

- `docs/9-reference/refactor-backlog.md` item **27** — the outage, with the before and
  after byte counts.
- `docs/5-testing/strategy.md` sections 2, 3 and 5.
- `STATUS.md` section 1b — the route table, and why a total outage showed as a blank
  500.
- `.agent/journal/2026-09-21T0500-code_reviewer-p5-web-routes.md` — how the reviewer
  reached `POST /upload` by rebinding `UPLOAD_DIR`, and how it exercised the error
  branch. **Read it before you start; it has already solved both of your hard parts.**

## Known open items

- **`POST /upload` has no HTTP proof from its own unit.** It writes into the repository
  and was outside that unit's scope. You are the first to be able to reach it cleanly.
- `api/routes_valuation.py:152` branches on `":" in files` — backlog item 26, latent.
  **Do not write a test that pins the current branch behaviour**, or item 26's fix turns
  it red. If you exercise it, assert the outcome, not the branch taken.
- The extraction cache is `pop`ped on read. A second `POST /valuation` with the same
  parameters takes the miss branch. **That is item 5, not a defect in your test** — but
  say in your entry which branch each of your tests took.

## Backlog items this unit is NOT fixing

- **Item 5** — the module-global cache.
- **Item 6** — falsy treated as missing.
- **Item 8** — the blanket catches. You are locking their *behaviour*, which is the
  opposite of endorsing them: a test that pins "the error is visible" stays true after
  they are replaced by typed exceptions.
- **Item 26** — the `files` branch.
