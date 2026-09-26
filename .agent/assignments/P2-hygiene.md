---
id: P2-hygiene
phase: 2 — hygiene
agent: programmer
depends_on: []
---

# Remove the dead code, clear the source lint, and stop `config.py` touching the disk at import

## Objective

`ruff check .` reports 45 errors. 18 of them sit outside `tests/`, and 14 of those 18
are import ordering, unused imports and f-strings with no placeholder — noise that
makes every later diff harder to read. `models/company.py` is dead: nothing in the
repository imports `Company`. `config.py:8` creates a directory when the module is
imported, so importing a configuration module touches the filesystem.

None of these produces a wrong number. They are in front of the queue because they
make the diffs that *do* change numbers readable, and because a gate nobody can read
is a gate nobody runs.

**This unit must not change a single number.** If a figure moves, you have found a
disagreement, and the disagreement is the report.

## What is already true — verify, do not redo

Measured by the orchestrator at `bc19431`, 2026-09-20. If one disagrees when you run
it, **stop and report the disagreement** rather than working around it.

| Fact | Command |
|---|---|
| 45 ruff errors in total; 18 outside `tests/` | `.venv/Scripts/python.exe -m ruff check . --output-format concise` |
| 33 mypy errors in 4 files, 19 source files checked | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` |
| nothing imports `Company` | `grep -rn "models.company\|import Company" --include=*.py .` → no hits outside `.venv` |
| `.DS_Store` is tracked twice; 2 pickles are tracked under `cache/` | `git ls-files \| grep -iE "\.DS_Store\|^cache/"` |
| **there is no ruff configuration file anywhere** — not in the repository, not at the user level | `ls -a \| grep -i ruff` shows only `.ruff_cache`; `$APPDATA/ruff/` does not exist |

The last row matters. The rule set the gate enforces today is ruff 0.16.8's built-in
default. It can change when ruff is upgraded, and then the gate means something
different with no commit to point at.

The 18 errors outside `tests/`, exactly:

```
analysis/capm.py:8       I001    import block un-sorted
analysis/capm.py:25      RUF059  unpacked variable `intercept` never used
analysis/capm.py:25      RUF059  unpacked variable `p_value` never used
analysis/fcff.py:20      F401    `BalanceSheet` imported but unused
analysis/normalizer.py:7 I001    import block un-sorted
api/routes_upload.py:46  B008    function call `File` in an argument default
api/routes_valuation.py:3   I001 import block un-sorted
api/routes_valuation.py:96  BLE001  blind except          <- DEFERRED, leave it
api/routes_valuation.py:220 BLE001  blind except          <- DEFERRED, leave it
cli.py:758                  BLE001  blind except          <- DEFERRED, leave it
ingestion/claude_extractor.py:57   I001
ingestion/claude_extractor.py:390  I001
ingestion/claude_extractor.py:785  F541  f-string, no placeholder
ingestion/claude_extractor.py:795  BLE001  blind except   <- DEFERRED, leave it
ingestion/claude_extractor.py:796  F541
ingestion/claude_extractor.py:806  F541
ingestion/claude_extractor.py:820  I001
ingestion/price_fetcher.py:42      DTZ002  `datetime.today()` used
```

## What to do

1. **Delete `models/company.py`.** Nothing imports `Company`. Backlog item 12.

2. **Clear the 14 clearable lint errors.** `I001`, `F401` and `F541` are all
   auto-fixable. `.venv/Scripts/python.exe -m ruff check . --fix` is acceptable for
   these, but **read every hunk it produces before you keep it**, and
   **never pass `--unsafe-fixes`**.

3. **Fix the two `RUF059` in `analysis/capm.py:25`** by prefixing the discarded names
   with an underscore. Do not remove them from the unpacking and do not change the
   regression call. In your entry, say which statistics the function discards — a
   later unit may want the intercept, and the next reader should not have to rerun the
   code to learn it was thrown away.

4. **Fix `DTZ002` in `ingestion/price_fetcher.py:42` without moving the date.**
   `datetime.today()` returns a naive local timestamp. The replacement must produce
   **the same calendar date on this machine**, because that date sets the price
   lookback window and this unit changes no number.

   State in your entry which call you used and why it cannot shift the date by a day.
   A UTC-based replacement does shift it for a machine west of Greenwich in the
   evening; if you choose one, say so and stop, because that is a behaviour change and
   it is not yours to make.

5. **Remove the duplicate pandas import in `ingestion/price_fetcher.py`.** The module
   imports pandas at line 9 and again as `_pd` at line 65.

   **Do not touch the version branch at line 66** that chooses `"ME"` over `"M"`.
   `STATUS.md` section 3 records that branch as unverified against pandas 3.0. Changing
   it here would mix an unverified behaviour change into a hygiene unit.

6. **Move the directory creation out of `config.py`.** `config.py:8` runs
   `UPLOAD_DIR.mkdir(exist_ok=True)` at import. Importing a configuration module must
   not touch the filesystem.

   **Move it; do not delete it.** The upload route needs the directory to exist. Put
   the `mkdir` where the upload is written, in `api/routes_upload.py`, so the call
   happens when a file actually arrives.

7. **Add `ruff.toml` at the repository root** holding exactly two things:

   - `target-version`, matching the Python this repository runs (3.14).
   - a per-file ignore for `B008` on `api/*.py`, with a comment saying why:
     `file: UploadFile = File(...)` in a parameter default is the required FastAPI
     idiom, not a defect.

   **Use `ruff.toml`, not `pyproject.toml`.** A `pyproject.toml` would also become
   pytest's configuration anchor, and unit `P1-suite` is changing test collection in
   parallel.

   **Do not add a `select` or `ignore` list beyond that one per-file entry.** Leaving
   the rule set at ruff's default keeps the gate meaning what it means today. In
   particular, **`BLE001` must stay an error** — it is backlog item 8 and phase 5 owns
   it. Suppressing it here would delete the record of a defect instead of fixing it.

8. **Untrack the binaries.** `git rm --cached` for `.DS_Store`,
   `10K_filings/.DS_Store`, `cache/.cache_abbv_extraction.pkl` and
   `cache/.cache_lhx_extraction.pkl`. Then add `cache/` to `.gitignore`.

   **`git rm --cached` only. Never `git rm`.** The files stay on disk; only the
   tracking goes. Loading a pickle executes the code inside it, so a tracked pickle is
   an executable committed as data — `STATUS.md` section 6, trap 2.

   `.gitignore` already covers `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/` and
   `.agent/.seal-baseline.json`, and the misleading `CLAUDE.md` line is already
   resolved. Do not redo those.

## Files in scope

- `models/company.py` (delete)
- `analysis/capm.py`
- `analysis/fcff.py`
- `analysis/normalizer.py`
- `api/routes_upload.py`
- `api/routes_valuation.py` — **import block only.** Nothing else in this file.
- `ingestion/claude_extractor.py` — **imports and f-strings only.** No logic.
- `ingestion/price_fetcher.py`
- `config.py`
- `ruff.toml` (new)
- `.gitignore`

**Nothing else.** Work outside this list is a review finding, even when the change is
good.

## Out of scope

- **`tests/`** — your write guard denies it, and unit `P1-suite` is running there in
  parallel. Do not read it expecting it to be stable.
- **`cli.py`** — its only remaining error is a deferred `BLE001`, and the next unit
  needs the file free. Leave it untouched.
- **`pyproject.toml`** — see step 7.
- **`templates/`, `static/`, `app.py`, `models/financial_statements.py`,
  `models/valuation.py`, `analysis/dcf.py`, `analysis/wacc.py`,
  `analysis/projector.py`** — no unit owns them yet.
- **`tests/.cache_*.pkl`** — three scripts read them. `P1-suite` was told to leave them
  and so are you.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | outside `tests/`, only the deferred blind-except errors remain | **exactly 4 errors, every one `BLE001`** | `.venv/Scripts/python.exe -m ruff check . --exclude tests --output-format concise` |
| 2 | the type gate has not got worse | ≤ 33 errors, ≤ 4 files | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` |
| 3 | `Company` is gone and nothing looked for it | 0 hits | `grep -rn "models.company\|import Company" --include=*.py models analysis api ingestion cli.py app.py config.py` |
| 4 | no binary is tracked | 0 lines | `git ls-files \| grep -iE "\.DS_Store\|^cache/"` |
| 5 | importing the config touches no directory | 0 hits in `config.py`, ≥ 1 in the upload route | `grep -n mkdir config.py api/routes_upload.py` |
| 6 | the application still imports, with every route registered | exit 0, no output | `.venv/Scripts/python.exe -c "import app"` |
| 7 | every analysis module still imports | exit 0 | `.venv/Scripts/python.exe -c "import analysis.capm, analysis.fcff, analysis.normalizer, analysis.dcf, analysis.wacc, analysis.projector; print('ok')"` |
| 8 | `BLE001` is still an error, not suppressed | the 4 errors from criterion 1 are `BLE001` | same command as criterion 1 |
| 9 | no arithmetic changed | state the count in your entry | `git diff --stat` plus, for `analysis/`, `git diff analysis/` read line by line |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/9-reference/refactor-backlog.md` item 12 — the dead code and hygiene list, with
  the `file:line` for each.
- `docs/8-build/phases.md` phase 2 — criteria 1, 2 and 3. **Criterion 4 of that phase
  (one provider default) is deliberately not in this unit**; see below.
- `docs/2-rules/rules.md` — the six rules override this assignment.
- `STATUS.md` section 3 — the unverified pandas 3.0 resampling branch.
- `STATUS.md` section 6 trap 2 — why a tracked pickle is not an inert fixture.

## Known open items

- **The lint gate depends on ruff's built-in default rule set, with no configuration
  file to pin it.** A ruff upgrade can silently change what the gate enforces. Step 7
  deliberately does **not** pin it, because writing out today's rule set would freeze
  errors this repository has not yet seen. Report this in your entry; the orchestrator
  will record it as a new backlog item.

- `api/routes_valuation.py:182` imports `yfinance` inside a request handler and falls
  back to it for `sharesOutstanding`. That is a **rule 5** break — two sources for one
  number — and it is backlog item 12 and item 1's territory. **Moving the import would
  not fix it**, and would make the line look handled when it is not. Leave it exactly
  as it is, and say in your entry that you saw it.

## Backlog items this unit is NOT fixing

Naming these so the reviewer does not raise them as new, and so you do not widen your
own scope to reach them.

- **Item 1** — the 119 zero-default sites. Phase 6.
- **Item 2** — `analysis/dcf.py:80`, zero net debt. Phase 4.
- **Item 3** — `analysis/normalizer.py:46` guesses a field. Phase 4. You touch that
  file's **import block only**.
- **Item 5** — the module-global extraction cache. Not yet scheduled.
- **Item 6** — the five falsy-as-missing conversions. Phase 4.
- **Item 7** — `cli.py` and `api/` duplicate the pipeline. Phase 3.
- **Item 8** — the four blind `except Exception` handlers. Phase 5. **Explicitly left
  visible as lint errors**, by criterion 8.
- **Item 9** — the unlabelled cost-of-debt assumption. Phase 7.
- **Item 10** — the D&A subtraction at `ingestion/claude_extractor.py:479`. Phase 7.
  You touch that file's **imports and f-strings only**.
- **Item 11** — the 33 type errors. Phase 5. Criterion 2 only asks that you do not add
  one.
- **Item 13** — the provider default disagreeing between one-PDF and multi-PDF upload.

  **Orchestrator decision, 2026-09-20:** `docs/8-build/phases.md` puts this in phase 2,
  and this unit leaves it out. The fact that forced the decision: resolving the
  provider to one default makes the provider a named assumption, and
  `docs/2-rules/rules.md` rule 6 then requires it to be **visible in the output**. That
  display work is phase 7 criterion 2 and it touches `templates/` and `cli.py`'s
  printing layer. Splitting the two would leave a rule 6 break standing between the
  units. They ship together, in the next unit.
