---
id: P9b-route-tests
phase: 9 — two extraction routes, one parser
agent: tester
depends_on: [P9b-session-web]
---

# Test the web routes for the session file, and the recorded label

## Objective

`P9b-session-web` (accepted at `be1c077`) added `POST /upload-session`, a `session_file`
parameter on `GET /assumptions` and `POST /valuation`, one `_run_extraction` for both
routes, and a label recorded when the extraction runs. Its programmer and its reviewer
proved each criterion with scratch scripts. Nothing in `tests/` holds those proofs, and
`api/` coverage fell from 95% to 88% and 77% because of it (`STATUS.md` section 1).

This unit turns those proofs into tests.

Read the assignment `.agent/assignments/P9b-session-web.md`, the programmer entry
`.agent/journal/2026-10-02T1658-programmer-p9b-session-web.md` and the review entry
`.agent/journal/2026-10-02T1710-code_reviewer-p9b-session-web.md` first. The existing
route tests in `tests/unit/test_routes.py` and `tests/unit/test_route_context_keys.py`
show how this repository stubs the extraction and the price data.

## What to test

1. **`GET /`** shows both forms, and the second posts to `/upload-session`.
2. **`POST /upload-session`** saves the file under `uploads/session/` and answers 303
   with `session_file` in the location. A file with no usable name answers 400, and the
   body names `session_file`. Point `config.UPLOAD_DIR` (or the module's copy of it) at
   `tmp_path`, so no test writes into the repository.
3. **`GET /assumptions?session_file=…`** answers 200, shows the label `Claude Code
   session`, and takes the ticker from the file. A ticker in the request that differs
   from the file stops, and the page names both.
4. **`POST /valuation` with `session_file`**, on a cache hit and on a cache miss, shows
   the session label. Stub `fetch_price_data`.
5. **The label is recorded, not re-derived.** A route A extraction made with a key set
   still shows the public API label after the key is removed, on a cache hit. Stub
   `_call_llm`. A cache miss with the key removed stops on the credential.
6. **A request that names no filing stops** on both routes. This closed backlog item 29;
   lock it.
7. **A bad session file shows the loader's message**: a session file missing one Pass 1
   key renders 200 with a message naming the file and the key.
8. **Backlog item 52**, as a red test in `tests/unit/test_routes_session_rule3_red.py`:
   on a cache hit, `POST /valuation` with both `session_file` and `files` must stop, as
   it does on a cache miss. Today it ignores `files`.

**The expected values come from the session file you write by hand.** Use round numbers,
any bytes for the PDF under `tmp_path`, and record its sha256 in the file with
`ingestion.filings.fingerprint_filings` or `hashlib`. Never read `10K_filings/`, which is
not in git.

**Never let a test reach the API or the network.** `config.py` loads `.env` with
`override=True` (backlog item 46), so removing a key with `monkeypatch.delenv` can be
undone. Stub `ingestion.claude_extractor._call_llm` and the route module's
`fetch_price_data` in every test that could reach them, and make each stub raise on an
input it was not given.

## Files in scope

- new test files under `tests/unit/`
- `tests/unit/test_routes_session_rule3_red.py`
- your journal entry under `.agent/journal/`

## Out of scope

- everything outside `tests/` and your entry.
- `ingestion/session_extraction.py`: `P9d` changes it in parallel with you, only for a
  malformed Pass 2. Use a well-formed Pass 2 in every test here.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the eight groups exist | ≥ 1 test each | `pytest --collect-only -q` on your files |
| 2 | every expected value has a written source | a comment on each assertion | reading the file |
| 3 | the gate | every new test passes, or sits in a `*_rule3_red.py` file with its reason | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 4 | `api/` coverage | measured, with `COVERAGE_FILE` under `/tmp/` | `.venv/bin/python -m pytest -q --cov=api --cov-report=term-missing` |
| 5 | at least two tests can fail | break the line under test in a copy under `/tmp/`, show the test go red | paste both in your entry |
