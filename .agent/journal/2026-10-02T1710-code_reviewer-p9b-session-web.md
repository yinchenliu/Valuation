---
agent: code_reviewer
assignment: P9b-session-web
round: 1
verdict: approved
---

# Review of P9b-session-web, round 1

Programmer entry: `.agent/journal/2026-10-02T1658-programmer-p9b-session-web.md`

Diff reviewed: `git diff d97855b -- api/ templates/ docs/3-architecture/entry-points.md`
(5 files, +308/-65). This was measured on macOS with `.venv/bin/python`. The reviewer's
scratch files are in `/tmp/p9b_rev/`: `rev.py` covers criteria 1, 2, 3 and 5 plus extra
probes, and `rev4.py` covers criterion 4. Every financial figure in the scratch session
files is **invented**. They are the programmer's `/tmp/p9b/session_wmt*.json`, copied. The
real Walmart PDF they name is only hashed. In every script, `ingestion.claude_extractor._call_llm`
and `routes_valuation.fetch_price_data` are stubbed before the first request. No paid call
was made.

**Scope.** `git status` shows these as modified: `api/routes_upload.py`,
`api/routes_valuation.py`, `templates/upload.html`, `templates/assumptions.html` and
`docs/3-architecture/entry-points.md`. All five are in scope. `templates/valuation_result.html`
is unchanged (`git diff d97855b --stat` on it is empty). The untracked `tests/unit/*` files
and `.agent/journal/...tester-p9c...` belong to P9c, not this unit. The repository's
`uploads/` still holds only `LHX`.

## The guard checks

These were run over the seven paths in Files in scope, using bash (zsh does not word-split `$F`).

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean |
| lookup with a fallback — `.get(k, 0)` | `api/routes_valuation.py:628` `info.get("sharesOutstanding", 0)`. The line is **untouched** and already recorded (backlog, rule 5 / `refactor-backlog.md:389`). The two `@router.get(` hits are false positives |
| bare or-default — `or 0.0` | `api/routes_upload.py:88` (`f.filename or ""`), `:93` (`year or 0`), `templates/assumptions.html:165-191` (`… or ''` on display strings). All of them are **untouched** pre-existing lines (`refactor-backlog.md:1153` records `year or 0`) |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (`grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` gives no output) |

The new code has two forms the greps miss. The programmer answered both:
`cache_key = session_file or files or file_path` selects between strings, and an empty
result means "no filing", which stops in `_run_extraction`. `Path(file.filename).name if
file.filename else ""` produces `""` only so that the next line can stop with a 400 that names
`session_file`.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| upload field `session_file` absent / empty filename | yes, 422 `loc: ["body","session_file"]` | `rev.py` P7 `''` → 422 |
| filename `.`, `..`, `a/..`, `/` | yes, 400 `session_file: the uploaded file has no usable filename (…)` | `rev.py` P7. `../../esc.json` is saved as `uploads/session/esc.json` and does not escape the directory |
| `session_file`, `files`, `file_path` all empty, on `POST /valuation` | yes, `No filing named: session_file, files and file_path are all empty.` (closes backlog item 29) | `rev.py` P3 |
| the same, on `GET /assumptions` | no extraction and no error, which is the page's landing state, unchanged | `rev.py` P4: `200 None None` |
| `files` naming no entry | yes, `files: ',' names no filing.` | `api/routes_valuation.py:191-193` |
| session file missing / not JSON / key absent | yes, the loader's message names the file and the problem | `rev.py` P5, P6, C5 |
| route A credential | yes, `resolve_provider` stops at extraction time | `rev4.py` A4 |
| `CachedExtraction.extraction`, `RouteExtraction.*` | the class cannot be built without them, because no field has a default | `api/routes_valuation.py:67`, `:135-144` |
| request ticker that differs from the session file's | yes, it stops and names both, before any price fetch | `rev.py` P2 |
| `extraction` on the run_valuation success path | bound on both branches (`:552`, `:567`) | read |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | the diff moves no figure across a unit boundary |
| percentages converted at the route boundary, once | untouched. Item 6's five conversions are not in the diff |
| falsy not treated as missing | every new truthiness test is on a `str` (`session_file`, `files`, `ticker`, `company_name`). None is on a number |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | `analysis/` is not in the diff. `api/` gains `ingestion.session_extraction`, which the layering allows |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | upload page offers both routes | 200, 2 forms, `/upload-session`, 0 scripts | `rev.py` C1: `200 2 True 0` | yes |
| 2 | session file reaches assumptions | 303, then 200, 7 blocks, label `Claude Code session` | C2: `303 /assumptions?session_file=%2Ftmp%2Fp9b_rev%2F…`, `200 err None`, all 7 headings `True`, label `('Transport', 'Claude Code session — figures read from the PDF …')`, `('Credential source', 'none — no API call was made; …')`, hidden ticker `WMT` | yes |
| 3 | result page shows recorded label | `Claude Code session` in body, hit and miss | C3: hit `200 err None \| CC session True \| public API False \| prices ['WMT']`. Miss: `200 err None \| CC session True` | yes |
| 4 | label survives env change | public API label after the key is unset | `rev4.py` (every `ANTHROPIC_*`, `CLAUDE_*` and `AZURE_*` variable popped after `config` loaded, then a dummy key set). A1 label `Anthropic public API (api.anthropic.com)`, stub calls `['anthropic-direct','anthropic-direct']`. A2 re-derivation stops. A3 cache hit `200 None True`, same label. A4 miss → `No Anthropic credential resolved…`, 0 new calls | yes |
| 5 | bad session file shows the message | 200, names the file and the problem | C5: `200 /private/tmp/p9b_rev/uploads/session/session_wmt_bad.json: … year 2025: key 'sbc' is absent.` The label is not shown | yes |
| 6 | route A unchanged | `1 failed, 197 passed`, same failure set | P9a's set (the three new tester files ignored) gives `1 failed, 197 passed`. The baseline `git archive d97855b` in `/tmp/p9b_rev_base` gives `1 failed, 197 passed`. Both failure sets are `{test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}`. The full tree with P9c's files gives `1 failed, 353 passed`, the same set | yes |
| 7 | no new lint/type errors | ruff 5, mypy 10 in 4, same set | ruff `Found 5 errors.`, all BLE001, at the five sites the programmer lists. mypy `Found 10 errors in 4 files (checked 20 source files)`. The set, with line numbers stripped, `diff`s **identical** to the baseline tree's | yes |
| 8 | one extraction function | 1 def, 2 callers | `grep -n "_run_extraction"`: def `:147`, callers `:399`, `:563`. `_extract_from_files(` is called only at `:202` | yes |
| — | census | 116 | 116 | yes |
| — | `GET /` | 200 | 200 | yes |

The cited line numbers in `docs/3-architecture/entry-points.md` were checked against
the source: routes `:66/:78/:107` and `:362/:497`, `.pop()` at `:548`, and every row of the
`cli.py` table (`:85`, `:189`, `:219-246`, `:295-348`, `:382-743`, `:762`/`:867`, `:934`, 1,109
lines). They are all correct.

## Findings

### F1: `session_file` together with `files` is ignored on a cache hit, and stops only on a miss · `minor`

**Evidence:** `rev.py` P1 posts a form carrying both a cached `session_file` and
`files=2026:/nonexistent.pdf`. The cache hit gives `200 err None | CC session True`, and the
same form on a cache miss gives `session_file was given together with files/file_path. Give one…`.
The cause is `api/routes_valuation.py:544`, `cache_key = session_file or files`, which is
consulted before `_run_extraction`'s check at `:178-182`.
**Rule or document:** none of the six rules. No value is guessed and no figure changes, since
the cached session file is what is valued and labelled. The unit's own documentation is untrue
on this path, though: `entry-points.md` step 2 says "A `session_file` together with
`files`/`file_path` stops", and the programmer's decision table says "an input is never
silently ignored". It can be reached only by a hand-built POST, or by submitting an
`/assumptions` error page that carried both after an earlier visit had cached the session file.
**What would fix it:** make the same check before the cache lookup in `run_valuation`, or move
it into one small helper that both the key computation and `_run_extraction` call.

### F2: the comment above `_extraction_cache` still says "all four are facts" · `note`

**Evidence:** `api/routes_valuation.py:84-86`. The cache entry now has five fields, and the
`CachedExtraction` docstring was updated to say "Five NAMED fields".
**Rule or document:** none. The comment is stale.
**What would fix it:** add a clause that the fifth field records who read the filing.

### F3: route A's label is resolved beside the extractor's own resolution, not taken from it · `note`

**Evidence:** `api/routes_valuation.py:201` calls `resolve_provider(config.DEFAULT_EXTRACTION_PROVIDER, None)`,
and `ingestion/claude_extractor.py:1427` resolves again inside `extract_financials`.
**Rule or document:** none. Step 4 of the assignment asks for exactly this call "at the moment
it extracts", and both calls read only the environment, a few microseconds apart in one request.
The programmer raised this as its finding 1. Making the record exact means the extractor must
return its `ProviderResolution`, which is an `ingestion/` change for a later unit.
**What would fix it:** nothing in this unit.

### F4: `/upload-session` saves any file type under `uploads/session/` · `note`

**Evidence:** `rev.py` P6. `x.txt` (`hello`) gets a 303 and is saved as
`uploads/session/x.txt`, and then `/assumptions` shows `…/x.txt: not valid JSON (Expecting value: …)`.
**Rule or document:** none. The loader stops, names the file and gives the reason. That is the
design step 2 asked for ("Do not parse the file here"). The `accept=".json"` attribute is only
a browser hint.
**What would fix it:** nothing is required. A later unit can refuse a non-`.json` suffix at upload.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 5 (module-global cache, `.pop()`) | `api/routes_valuation.py:548` | the key changed, `.pop()` kept as instructed. The behaviour is unchanged |
| 6 (falsy-as-missing ×5) | `run_valuation` body | no |
| 8 (blanket `except Exception`) | `api/routes_valuation.py:445`, `:703` | no. They moved only by line number |
| 26 (`":" in files`) | `api/routes_valuation.py:557` | it moved into a two-way assignment with the same test and the same result, as the assignment allowed. Not made worse |
| 28 (`file.filename` as path segment) | `api/routes_upload.py:28` | no. The new route does not copy the pattern |
| rule 5 `sharesOutstanding` fallback | `api/routes_valuation.py:628` | no |
| `year or 0` | `api/routes_upload.py:93` | no |
| P9a review F1 (`non_recurring_items` not a list → `AttributeError`) | `ingestion/session_extraction.py` | no. It can now be reached from the web, as the programmer reported. P9d owns it |

Programmer finding 3 is correct: the "Where they duplicate each other" table and the
"Templates" paragraph in `entry-points.md` were stale before this unit, and they sit outside
the three edits the assignment asked for. I saw them, and I am leaving them to the orchestrator.

## Earlier findings — re-reviews only

None. This is round 1.

## Verdict

`approved`

Every done-criterion was re-run independently and agrees with the programmer's report. The test
failure set, the ruff sites and the mypy error set are identical to the baseline at `d97855b`.
The guard greps find nothing on the lines this unit touched. Rule 6 is now satisfied on both
routes: the label is recorded when the extraction runs, carried in a required field and rendered
on both pages, and the render-time re-derivation has been removed. Backlog item 29 is closed for
`POST /valuation` at no extra cost, as the assignment allowed. F1 is a `minor` inconsistency
between the docs and a crafted-request path, and it changes no figure or label. F2 to F4 are
notes. Nothing blocks.
