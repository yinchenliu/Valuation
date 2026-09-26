---
agent: programmer
assignment: P2-hygiene
round: 1
status: partial
files_touched: [models/company.py, analysis/capm.py, analysis/fcff.py, analysis/normalizer.py, api/routes_upload.py, api/routes_valuation.py, ingestion/claude_extractor.py, ingestion/price_fetcher.py, config.py, ruff.toml, .gitignore]
verdict: —
---

# P2-hygiene — remove dead code, clear source lint, stop `config.py` touching the disk at import

> Opened before the first command. Filled as each result landed.

**Status is `partial` for exactly one reason: done-criterion 1 measures 5 errors, not 4.**
The fifth is `UP017` in `.claude/hooks/seal_baseline.py`, a file this agent may never
write. It is surfaced by the `target-version = "py314"` that step 7 of this assignment
requires. Full analysis under "The one criterion that does not pass". Nothing else in
the unit is outstanding.

---

## Baseline — verified, not redone

Every "what is already true" row was re-measured before any edit. All five agree with
the orchestrator's measurement at `bc19431`.

| Fact | Result |
|---|---|
| 45 ruff errors total; 18 outside `tests/` | `Found 45 errors.` / `Found 18 errors.` — **agrees** |
| 33 mypy errors in 4 files, 19 source files | `Found 33 errors in 4 files (checked 19 source files)` — **agrees** |
| nothing imports `Company` | no output — **agrees** |
| `.DS_Store` tracked twice, 2 pickles under `cache/` | 4 lines, exactly the four named — **agrees** |
| no ruff configuration anywhere | `ls -a \| grep -i ruff` → only `.ruff_cache` — **agrees** |

The 18 source errors matched the assignment's list line for line, including the four
deferred `BLE001` sites. No disagreement to report.

## What I did

Deleted the dead `models/company.py`; cleared the 14 clearable lint errors (6 `I001`,
2 `RUF059`, 1 `F401`, 3 `F541`, 1 `B008`, 1 `DTZ002`); removed the duplicate pandas
import in `price_fetcher.py`; moved the `mkdir` out of `config.py` into the upload
write path; added `ruff.toml`; and untracked the four committed binaries. **No
arithmetic changed anywhere** — criterion 9 below, with the `analysis/` diff read line
by line.

Two changes needed a reason rather than a rule, and both are recorded under
"Decisions": the `DTZ002` fix had to stay *naive*, for a reason that inverted my first
assumption; and the `target-version` the assignment mandates surfaces a new error in a
file outside my scope, which I did not suppress.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | outside `tests/`, only deferred blind-excepts remain (expected exactly 4, all `BLE001`) | **fail — 5** | `.venv/Scripts/python.exe -m ruff check . --exclude tests --output-format concise` → `Found 5 errors.`: the 4 `BLE001`, plus `.claude\hooks\seal_baseline.py:108:46: UP017`. Restricted to the source tree this unit owns, `ruff check models analysis ingestion api config.py app.py cli.py` → `Found 4 errors.`, all `BLE001`. See below |
| 2 | type gate not worse (≤ 33 errors, ≤ 4 files) | **pass** | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` → `Found 33 errors in 4 files (checked 18 source files)`. Same 33 errors in the same 4 files; 18 files not 19 because `models/company.py` is gone |
| 3 | `Company` gone, nothing looked for it | **pass** | `grep -rn "models.company\|import Company" --include=*.py models analysis api ingestion cli.py app.py config.py` → 0 hits |
| 4 | no binary tracked | **pass** | `git ls-files \| grep -icE "\.DS_Store\|^cache/"` → `0` |
| 5 | importing config touches no directory | **pass** | `grep -n mkdir config.py api/routes_upload.py` → 0 in `config.py`, 2 in `api/routes_upload.py` (lines 24, 26). Proved by execution, not grep — see "Proof by execution" |
| 6 | app still imports, every route registered | **pass** | `.venv/Scripts/python.exe -c "import app"` → exit 0, no output. Routes proved present via the OpenAPI schema: `GET /`, `GET /assumptions`, `POST /upload`, `POST /valuation` |
| 7 | every analysis module still imports | **pass** | `.venv/Scripts/python.exe -c "import analysis.capm, analysis.fcff, analysis.normalizer, analysis.dcf, analysis.wacc, analysis.projector; print('ok')"` → `ok`, exit 0 |
| 8 | `BLE001` still an error, not suppressed | **pass** | `ruff check models analysis ingestion api config.py app.py cli.py` → all 4 errors are `BLE001`. `ruff.toml` contains 0 top-level `select`/`ignore`/`exclude` lines: `grep -cE '^(select\|ignore\|extend-select\|extend-ignore\|exclude)' ruff.toml` → `0` |
| 9 | no arithmetic changed | **pass** | `git diff --stat HEAD` → 10 files, +64/−40, of which `models/company.py` is −22 (deletion). `git diff HEAD -- analysis/` read line by line: see below |

### Criterion 9, in detail

`git --no-pager diff HEAD -- analysis/` contains, in full:

- `capm.py` — `import config` moved above the first-party imports (`I001`); a docstring
  paragraph added; `intercept` → `_intercept` and `p_value` → `_p_value` in the
  unpacking target list.
- `fcff.py` — the unused name `BalanceSheet` removed from an import. Confirmed unused by
  execution, not by ruff's word: `grep -n "BalanceSheet\|balance_sheet" analysis/fcff.py`
  → exit 1, zero occurrences.
- `normalizer.py` — one import line reflowed onto four lines.

**No operator, no numeric literal, and no expression changed in `analysis/`.** The
regression call in `calculate_beta` is byte-identical; only the names bound to two
discarded return slots differ.

Outside `analysis/`: `config.py` loses one `mkdir` line, `routes_upload.py` gains one,
`routes_valuation.py` has exactly 2 changed lines (one import swapped — verified with
`git diff HEAD -- api/routes_valuation.py | grep -cE "^[+-][^+-]"` → `2`),
`claude_extractor.py` is imports and three f-string prefixes only, `price_fetcher.py` is
the two changes described below.

**Independent check that no silent default was introduced.** The rule-3 census from
`docs/2-rules/rules.md` stood at **119** at `bc19431`; it now reads **117**:

```
grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" \
  --include=*.py models analysis api ingestion | wc -l     →  117
```

The difference is exactly the two fields in the deleted dead file
(`git show HEAD:models/company.py` lines 16–17: `current_price: float = 0.0`,
`diluted_shares_outstanding: float = 0.0`). **This unit added zero new sites and
removed two**, both in code nothing imported.

## The one criterion that does not pass

Criterion 1 expects 4. It measures 5. The fifth is:

```
.claude\hooks\seal_baseline.py:108:46: UP017 [*] Use `datetime.UTC` alias
```

**Cause, isolated by measurement.** It is not caused by any source edit. It is caused by
step 7's instruction to set `target-version` to the Python this repository runs:

| `ruff.toml` | `ruff check . --exclude tests` |
|---|---|
| none at all | 5 errors — 4 `BLE001` + `B008` in `routes_upload.py` |
| `target-version = "py39"` + the `B008` per-file ignore | **4 errors, all `BLE001`** |
| `target-version = "py314"` + the `B008` per-file ignore (as assigned) | **5 errors** — 4 `BLE001` + `UP017` |
| `target-version = "py314"`, source tree only | **4 errors, all `BLE001`** |

Narrowed further: `ruff check .claude` alone is clean at `py310` and reports the `UP017`
at `py311`. `datetime.UTC` became available in Python 3.11, so the rule is correct and
only fires once ruff is told the true target. With no config, ruff inferred a target
older than 3.11 and the rule was dormant repo-wide.

**Why I did not make it green.** Three routes were available and I rejected all three:

1. *Fix the line* (`timezone.utc` → `UTC`). `.claude/` is categorically outside this
   agent's write scope — "**`.claude/`.** You do not edit the permissions that bind
   you" — and it is not in the assignment's Files in scope. I did not attempt the write.
2. *Lower `target-version` to `py39`.* This makes criterion 1 read 4. It is also
   precisely a code change made to reach a target number rather than on a reason, and it
   would make the config state something false about a repository running 3.14.4
   (`STATUS.md` section 3).
3. *Add an `exclude` for `.claude/`, or ignore `UP017`.* Step 7 says the file holds
   exactly two things and forbids a `select`/`ignore` list beyond the one per-file
   entry. It would also hide a correct finding, which is the same failure mode step 7
   cites for `BLE001`.

So the config is exactly as assigned, and the disagreement is reported rather than
worked around. **The fix is one line and belongs to whoever owns `.claude/`:**
`.claude/hooks/seal_baseline.py:108`, `datetime.now(timezone.utc)` →
`datetime.now(UTC)`, with the import adjusted. It is `[*]` auto-fixable.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `DTZ002` fixed as `datetime.now(UTC).astimezone().replace(tzinfo=None)` — deliberately still **naive** | yfinance's `_parse_user_dt` branches on `tzinfo`: a **naive** datetime is `tz_localize`d to the exchange timezone (wall-clock numbers kept, instant moved); an **aware** one is `tz_convert`ed (instant kept, wall-clock numbers moved). Read from the installed source via `inspect.getsource(yfinance.utils)` | My first instinct was the idiomatic aware `datetime.now(UTC).astimezone()`. The source proves that would send yfinance down the other branch and shift both window boundaries by the UTC offset — a behaviour change, and the assignment says such a change is not mine to make. Keeping it naive preserves the exact value yfinance receives; what changes is only that the naive-ness is now explicit and documented, which is what `DTZ002` exists to force |
| Left `_month` branch logic untouched, only renamed `_pd` → `pd` | `STATUS.md` section 3 records the pandas 3.0 resampling branch as unverified; the assignment forbids touching it | The branch expression is byte-identical apart from the alias. Verified the alias is the same object (`pf.pd is pd` → `True`) and the branch yields the same value on pandas 3.0.6 (`ME` both ways) |
| `RUF059` fixed by underscore prefix, plus a docstring naming what is discarded | Assignment step 3: do not remove them from the unpacking, do not change the regression call | The names stay in the tuple so the positional unpacking is unchanged; the docstring means the next reader learns the statistics were thrown away without rerunning the code |
| Added an explicit `UPLOAD_DIR.mkdir(exist_ok=True)` in `_save_upload`, even though the following `ticker_dir.mkdir(parents=True, ...)` would create it implicitly | Assignment step 6: "Move it; do not delete it" | Relying on `parents=True` would make the move invisible and would silently break if the `ticker_dir` layout ever changed. The explicit line carries a comment saying where it came from |
| `ruff.toml` left with no `select`/`ignore` list | Step 7, and the `BLE001` record it protects | Verified 0 top-level `select`/`ignore`/`exclude` lines |

**No code change in this unit was made to reach a target number.** The one place that
temptation existed — lowering `target-version` to turn criterion 1 green — is recorded
above as explicitly rejected.

## Rule 3 — what stops, and what does not

This unit reads no financial value. For completeness, every value its changed lines
read:

| Value read | If it were missing | Evidence |
|---|---|---|
| the system clock, `datetime.now(UTC)` | cannot be missing; no default, no fallback branch | `ingestion/price_fetcher.py:42`. Not a filing input — it sets the lookback window and is market-data plumbing |
| `pd.__version__` | cannot be missing once pandas imports; the module-level `import pandas as pd` at line 9 fails loudly first | `ingestion/price_fetcher.py:71` |
| `config.UPLOAD_DIR` | a module constant; absence is an `ImportError`, not a default | `api/routes_upload.py:24` |

**No "defaults to" row.** Confirmed by census above: 119 → 117, the delta being only the
two dead fields deleted with `models/company.py`.

`mkdir(exist_ok=True)` is idempotency, not a value default — it supplies no number and
hides no missing input.

## Rule 5 — the break I was told to leave, and did

`api/routes_valuation.py:180-184`, seen and left exactly as found:

```python
shares = latest_is.diluted_shares_outstanding
if shares == 0:
    import yfinance as yf
    info = yf.Ticker(ticker).info
    shares = info.get("sharesOutstanding", 0) / 1e6  # Convert to millions
```

Two sources for one number, mid-pipeline, behind an inline import — backlog items 1 and
12. Per the assignment, moving the import would make the line look handled when it is
not, so it is untouched; `git diff` on that file shows exactly 2 changed lines, both in
the import block. Worth noting for whoever picks it up: the line is *also* a rule 3 site
— `info.get("sharesOutstanding", 0)` defaults a share count to zero, which would make
the per-share denominator zero rather than stopping.

## Proof by execution

Criterion 5 is a grep, and a grep only proves a string is absent. I proved the behaviour
instead. `uploads/` was empty (`find uploads -type f | wc -l` → 0), so I removed it, ran
the import, then exercised the write path, then restored it empty as found:

```
removed uploads/ (was empty)
--- exists before import? ---            NO
config imported; UPLOAD_DIR = C:\Users\LiuYinchen\Valuation\uploads
UPLOAD_DIR exists after import: False
--- exists after importing config? ---   NO

before _save_upload, uploads exists: False
after  _save_upload, uploads exists: True
written to: C:\Users\LiuYinchen\Valuation\uploads\PROBE\probe_2024.pdf
bytes on disk: b'%PDF-1.4 probe'
```

Importing the configuration module now creates nothing; the directory appears only when
a file is actually written. Probe deleted afterwards; `uploads/` left empty and is
gitignored, so nothing tracked moved.

A side effect worth recording: `ingestion/claude_extractor.py:821` does
`import config as _  # noqa: F401 — triggers dotenv load`. Before this change, resolving
an LLM provider created a directory on disk as a side effect. It no longer does.

The four untracked binaries were verified still present on disk after `git rm --cached`
(`ls -l` shows all four, unchanged size and mtime). `git rm` was never used.

## Measurements

| Gate | Before (`bc19431`) | After |
|---|---|---|
| Lint, whole repo | 45 errors | not comparable — `tests/` is being rewritten by `P1-suite` in parallel |
| Lint, outside `tests/` | 18 errors | **5** (4 `BLE001` + 1 `UP017` in `.claude/`) |
| Lint, source tree this unit owns | 18 errors | **4**, all `BLE001` |
| Types | 33 errors, 4 files, 19 files checked | **33 errors, 4 files, 18 files checked** — identical error set |
| Rule-3 census (`models analysis api ingestion`) | 119 | **117** |
| Tracked binaries | 4 | **0** |

**No figure this unit produced or moved.** No valuation was run, and none needed to be:
the unit changes no arithmetic, which criterion 9 establishes from the diff itself.

`tests/` shows as modified in `git status` (9 files, plus a new `tests/unit/`). That is
`P1-suite` working in parallel, not this unit. I wrote nothing under `tests/` and read
nothing from it.

## What I did not do

- **Did not fix `.claude/hooks/seal_baseline.py:108`.** Out of scope, by the agent
  contract and by the assignment's Files in scope. This is the sole reason criterion 1
  does not pass.
- **Did not touch `cli.py`**, per Out of scope. Its `BLE001` at line 758 remains, and is
  one of the 4 expected.
- **Did not touch the pandas version branch** at `price_fetcher.py:71` beyond the alias
  rename, per step 5 and `STATUS.md` section 3. It remains unverified against pandas 3.0.
- **Did not touch `api/routes_valuation.py:182`**, the rule 5 yfinance fallback, per
  Known open items.
- **Did not create `pyproject.toml`**, per step 7.
- **Did not touch `tests/*.pkl`**, which stay tracked.
- **Did not pin ruff's rule set**, per step 7.
- `ingestion/claude_extractor.py:389` has an `import re` inside `_call_gemini` shadowing
  the module-level `re` from line 60. Ruff does not flag it and it is a logic-adjacent
  edit in a file where I am limited to imports and f-strings, so I left it. Harmless
  today; noted so it is not rediscovered as new.

## Findings for the orchestrator

1. **The lint gate's rule set is still unpinned, and it is now demonstrably load-bearing**
   (the assignment asked me to report this; I can now put a number on it). `ruff.toml`
   sets `target-version` but no `select`, so the gate enforces ruff 0.16.8's built-in
   default. This unit measured the cost directly: changing only `target-version`, with
   no source edit, moved the error count from 4 to 5 and activated a rule (`UP017`) that
   had been dormant across the whole repository. A ruff upgrade can do the same with no
   commit to point at. Suggested backlog item.

2. **`.claude/hooks/seal_baseline.py:108` needs a one-line fix, and only the
   orchestrator can make it.** `datetime.now(timezone.utc)` → `datetime.now(UTC)`.
   Auto-fixable. Until it lands, criterion 1 of this unit reads 5 and any later unit
   running the same command will see the same extra error. A second, defensible option
   is to decide that the lint gate should not cover `.claude/` at all — agent-contract
   tooling is not product source — but that is a config decision beyond the two things
   step 7 allows, so I did not take it.

3. **`api/routes_valuation.py:184` is a rule 3 site as well as the known rule 5 site.**
   `info.get("sharesOutstanding", 0) / 1e6` defaults the share count to zero. Since
   `shares` is the denominator of the headline per-share figure, the failure mode is a
   division by zero or an infinite price rather than a named stop. Whoever takes backlog
   item 1 or 12 should treat the two defects on this line together.

4. **`uploads/` is now created lazily and nothing else creates it.** If any future entry
   point writes to `UPLOAD_DIR` without going through `api/routes_upload._save_upload`,
   it must call `mkdir` itself. Today `_save_upload` is the only writer
   (`grep -rn "UPLOAD_DIR" --include=*.py .` → 3 hits: the definition in `config.py`
   and two in `routes_upload.py`).
