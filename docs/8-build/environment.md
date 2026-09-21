# The environment

**Measured 2026-09-20 at `bc19431`.** Re-measure when you change a dependency.

---

## 1. The interpreter

```
.venv/Scripts/python.exe
```

**Never a bare `python`.** This is Windows, so the interpreter is under `Scripts`, not
`bin` — a command copied from a Linux or macOS project will not run.

| | |
|---|---|
| Version | Python **3.14.4** |
| Built from | `D:\Software\Python.Python.3.14\python.exe` |
| Created | 2026-09-20 |

**The path in the old `CLAUDE.md` was wrong.** It named
`C:\Users\yinchenliu\Python3\python-3.14.2\python.exe`. That user directory does not
exist on this machine — note `yinchenliu` against the actual `LiuYinchen`. Every
command in these docs uses the venv path instead, which is correct on any machine that
ran the setup below.

## 2. Creating it from scratch

```bash
"D:/Software/Python.Python.3.14/python.exe" -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` includes `requirements.txt`, so that one command installs both
the runtime dependencies and the gates.

### Verify it

```bash
.venv/Scripts/python.exe -c "import fastapi, pandas, numpy, scipy, yfinance, pdfplumber, anthropic; from google import genai; print('ok')"
```

Installed versions at the time of writing: pandas **3.0.6**, numpy **2.5.3**,
scipy **1.18.1**, pytest **9.1.1**, ruff **0.16.8**, mypy **2.3.1**.

> **Warning — pandas 3.0 is a major version and no valuation has been run against it.**
> `ingestion/price_fetcher.py:66` branches on the pandas version to pick `"ME"` over
> `"M"` for month-end resampling. That branch is untested on 3.0 with real data. Treat
> any resampling result as unverified until a run confirms it.

## 3. API keys

Extraction needs one. Nothing else does.

Create `.env` in the repository root — `config.py:12` loads it, and `.gitignore`
already excludes it:

```
GEMINI_API_KEY=...
# Optional, only when the provider is switched to Claude:
# ANTHROPIC_API_KEY=...
```

Gemini is the default provider. `ingestion/claude_extractor.py:835` raises
`ValueError("GEMINI_API_KEY is not set. Add it to .env or system env.")` when it is
missing — which is a correct stop, and the model for how the rest of the codebase
should behave.

**No unit test may need a key.** See
[5-testing/strategy.md](../5-testing/strategy.md).

## 4. The three gates

| Gate | Command | Result at `bc19431` |
|---|---|---|
| Tests | `.venv/Scripts/python.exe -m pytest -q` | **3 collection errors, 0 tests** |
| Lint | `.venv/Scripts/python.exe -m ruff check .` | **45 errors** |
| Types | `.venv/Scripts/python.exe -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | **33 errors in 4 files** |

**No gate passes today.** That is the starting position. [STATUS.md](../../STATUS.md)
section 1 holds the breakdown and keeps the current figure; this file owns the
commands, not the counts.

### Why the test gate cannot even start

Every file in `tests/` executes its whole pipeline at **import** time — no
`if __name__ == "__main__":` guard anywhere. So `pytest` makes paid API calls during
collection and fails before running a test. Do not run `pytest` expecting it to be
free until that is fixed.

### mypy is scoped deliberately

`mypy .` is **not** the gate. It would include `tests/` and `cli.py`, which are
scripts. The gate names the four source packages plus the two root modules.

`--ignore-missing-imports` is required: `yfinance`, `pdfplumber` and `scipy` ship no
type stubs.

## 5. Running it

**Web app:**

```bash
.venv/Scripts/python.exe -m uvicorn app:app --reload
```

Then open `http://127.0.0.1:8000`. Upload a PDF, review the assumptions, run the
valuation.

**CLI:**

```bash
.venv/Scripts/python.exe cli.py --help
```

The CLI runs the same eight steps and caches extraction results, so it is the cheaper
way to iterate on `analysis/`. See
[3-architecture/entry-points.md](../3-architecture/entry-points.md).

## 6. Scratch space

Write scratch files **outside the repository**. The write guard does not police paths
outside it, and a scratch file inside it dirties the tree and can trip the seal.

```
c:/tmp/
```

Set `PYTHONDONTWRITEBYTECODE=1` so a script leaves no `__pycache__` behind.

## 7. What is gitignored, and one thing that is not

`.gitignore` covers `__pycache__/`, `.env`, `uploads/`, `.venv/`, `10K_filings/`.

**Two problems with it, both recorded in the backlog:**

1. It lists `CLAUDE.md`, but `CLAUDE.md` is **tracked**. Git does not ignore a tracked
   file, so the line does nothing except mislead — editing `CLAUDE.md` does dirty the
   tree.
2. It does not list `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/` or
   `.agent/.seal-baseline.json`. Running a gate or dispatching a subagent creates
   untracked directories.
