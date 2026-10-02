---
id: P9b-session-web
phase: 9 — two extraction routes, one parser
agent: programmer
depends_on: [P9a-session-route]
---

# Let the web app value a company from an uploaded session file

## Objective

`P9a-session-route` added a second extraction route. A Claude Code session writes the two
JSON answers per filing to a **session file**, and `load_session_extraction` turns that
file into the same `FinancialStatements` and `NonRecurringItem` list that route A
produces. Today only `cli.py --session-file` can use it.

The web app is the entry point the user runs (`docs/0-start.md`). It shows all seven
statement blocks since Phase 8. So a session extraction must reach those pages too.

**One more fact forces part of this unit.** The result page labels the extraction with
`resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)` at
`api/routes_valuation.py:522`. That re-derives the label at render time. It does not
record it. The comment above it calls this a known limitation (`P2b-provider` review,
finding F3). With two routes, the gap turns into a false label: a session extraction
would render as "CLAUDE over the public API", because that is what *would* read a filing
now. Rule 6 forbids that. So the label must be recorded when the extraction runs, and
carried with it.

## What is already true — verify, do not redo

Fill in the commit from `git log --oneline -1` before you start. The interpreter on this
machine is `.venv/bin/python`.

| Fact | Command |
|---|---|
| the gates stand where `P9a-session-route`'s accepted entry records them | the commands in `docs/8-build/environment.md` section 4, with the macOS interpreter |
| the loader exists and stops on a bad file | `grep -n "def load_session_extraction\|class SessionExtraction" ingestion/session_extraction.py` |
| the label is re-derived at render time | `sed -n 505,525p api/routes_valuation.py` |
| the cache holds four named fields | `grep -n "class CachedExtraction" -A 25 api/routes_valuation.py` |
| the form forwards the filings as a hidden field | `grep -n "hidden" templates/assumptions.html` |
| the result page reads four label fields | `grep -n "extraction\." templates/valuation_result.html` |

If a row disagrees, **stop and report it.** Line numbers may have moved since this was
written. Find the code by name.

## What to do

1. **`templates/upload.html`: add a second form**, below the PDF form, headed "Use a
   Claude Code session file". It has one file input that accepts `.json` and posts to a
   new route `POST /upload-session`. One sentence explains it: the figures were read from
   the PDFs in a Claude Code session, and no API call is made. **Add no JavaScript.**
   No template in this repository loads any.

2. **`api/routes_upload.py`: add `POST /upload-session`.** Save the file under
   `uploads/session/`, the same way `_save_upload` saves a PDF. Then redirect with 303 to
   `/assumptions?session_file=<saved path>`. Do not parse the file here. The loader
   parses and stops at `/assumptions`, where its message reaches the page.

3. **`api/routes_valuation.py`, the cache entry.** Add a fifth required field to
   `CachedExtraction`: `extraction: ProviderResolution`. **No default**, for the reason
   its docstring gives for the other four.

4. **`api/routes_valuation.py`, one place that runs an extraction.** Today two places
   call `_extract_from_files`: `assumptions_page` and the cache-miss branch of
   `run_valuation`. Make one function that both call. It takes the `files`, the
   `file_path` and the `session_file` parameters, and returns the raw statements, the
   item list and the `ProviderResolution`:
   - with a `session_file`, it calls `load_session_extraction`. The ticker and the
     company name come from the loaded statements;
   - otherwise it runs route A as today, and records
     `resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)` **at the moment it
     extracts**.

   Two branches that each build the four cached values is how the two halves drifted
   before. The comment at the cache-miss branch says so.

5. **`assumptions_page` and `run_valuation` accept `session_file`.** It is a query
   parameter on the first and a form field on the second. The cache key is the first
   non-empty value of `session_file`, `files` and `file_path`. The ticker shown and
   forwarded comes from the loaded file when a session file is used.

6. **`run_valuation` renders the recorded label.** Replace the call at `:522` with the
   `extraction` value from the cache entry, or from the extraction the cache-miss branch
   just ran. Delete the "KNOWN LIMITATION" comment, because this unit fixes it. Keep a
   short comment saying why the label is recorded and not re-derived.

7. **`templates/assumptions.html`: forward `session_file`** as a hidden field, beside
   `files`. Show the route on that page too, with the same four label fields the result
   page shows. A reader who checks the extracted statements before choosing assumptions
   must know which route produced them.

8. **`docs/3-architecture/entry-points.md`:** add the new route to the routes table, and
   update "The flow" for the session file. While you are in the file, refresh the
   `cli.py` line table under "The CLI". The `P9a` review found it stale (finding F5).

**Added after `P9a` was accepted at `ad52e1a`.** The loader's real interface is in
`ingestion/session_extraction.py` and in `P9a`'s programmer entry. `SessionExtraction`
has six fields, including `filings`, which holds each PDF's sha256 and pages read. Use
it if you show the session's filings on a page. **Warning:** `config.py` loads `.env`
with `override=True`, so `env -u ANTHROPIC_API_KEY` does not remove the key on this
machine (backlog item 46). For criterion 4, set and unset the variable inside the
script after `config` is imported, and replace `ingestion.claude_extractor._call_llm`
with a stub so route A can never make a real call.

## Files in scope

- `api/routes_upload.py`
- `api/routes_valuation.py`
- `templates/upload.html`
- `templates/assumptions.html`
- `templates/valuation_result.html`, **only** if the label rows need a change. They
  should not.
- `docs/3-architecture/entry-points.md`
- your journal entry under `.agent/journal/`

**Nothing else.**

## Out of scope

- `ingestion/`: `P9a-session-route` owns the loader. If it lacks something you need,
  stop and report. Do not change it.
- `tests/`: the tester writes the route tests. Prove each criterion with `TestClient`
  scripts under `/tmp/`, and paste them and their output in your entry.
- `cli.py`.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | the upload page offers both routes | 200, two forms, `/upload-session` in the body | `TestClient.get('/')` |
| 2 | a session file reaches the assumptions page | 200, the seven statement blocks, the label shows `Claude Code session` | `TestClient`: post a scratch session file to `/upload-session` and follow the redirect. The scratch file's PDFs must exist, so use one real PDF from `10K_filings/` with invented figures. Say the figures are invented |
| 3 | the result page shows the recorded label | `Claude Code session` in the body of `POST /valuation` | `TestClient`, with `fetch_price_data` stubbed so the run makes no network call |
| 4 | the label survives a change of environment | a route A extraction made with `ANTHROPIC_API_KEY` set still renders the public API label after the variable is unset before `POST /valuation` | `TestClient` with `monkeypatch`-style environment edits in the script |
| 5 | a bad session file shows the loader's message | 200, the message names the file and the problem | `TestClient`: a session file with one key removed |
| 6 | route A is unchanged | the gate as `P9a` left it | the test gate |
| 7 | no new lint or type errors | ruff and mypy counts as `P9a` left them, or lower | the two gates |
| 8 | one extraction function | 1 definition, 2 callers | `grep -n` on its name in `api/routes_valuation.py` |

## Citations

- `docs/2-rules/rules.md`: rule 3 (stop, never guess) and rule 6 (label the
  assumption).
- `docs/3-architecture/entry-points.md`: the flow and the four surprises in it.
- The `P2b-provider` review round 1 entry in `.agent/journal/`: finding F3, the
  re-derived label.
- `P9a-session-route`'s accepted programmer entry: the loader's signature and its stop
  list.

## Known open items

- Route A's arithmetic validation errors reach stdout only, not the web page. The
  session loader returns them in `SessionExtraction`. **Do not show them on the page in
  this unit.** The two routes would then differ in what the reader sees. Showing both is
  a later unit.
- Uploading a file with the same name as an earlier upload overwrites it, as PDF uploads
  do today.

## Backlog items this unit is NOT fixing

- **Item 5.** The module-global cache emptied by `.pop()`. Keep the `.pop()`.
- **Item 6.** The five `x / 100 if x else None` conversions.
- **Item 8.** The blanket `except Exception` in both routes.
- **Item 26.** The `":" in files` test on the legacy branch.
- **Item 28.** `api/routes_upload.py:27`, `str | None` as a path segment. Do not copy the
  pattern into the new route: a missing filename must stop, naming the field.
- **Item 29.** `POST /valuation` with no `files`. With three parameters now, a request
  with none of them must not run an extraction on an empty string. **If the shared
  function from step 4 makes this a stop at no extra cost, do it and say so.** Otherwise
  leave it.
