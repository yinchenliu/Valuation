# The environment

**Measured 2026-09-20 at `bc19431` on Windows, and 2026-10-02 at `5dc28a0` on macOS.**
Re-measure when you change a dependency.

---

## 1. The interpreter

**This repository runs on two machines, and the venv puts the interpreter in a different
place on each.**

| Machine | Interpreter | Python | Built from | Created |
|---|---|---|---|---|
| Windows | `.venv/Scripts/python.exe` | **3.14.4** | `D:\Software\Python.Python.3.14\python.exe` | 2026-09-20 |
| macOS | `.venv/bin/python` | **3.11.6** | `/opt/homebrew/opt/python@3.11/bin/python3.11` | before 2026-09-26 |

**Never a bare `python`.** A bare `python` resolves to whatever is first on `PATH`.
Use the row for the machine you are on. A command copied from the other row fails with
"no such file", which is the fastest sign you are on the other machine.

**Most commands in these docs use the Windows form.** On macOS, replace
`.venv/Scripts/python.exe` with `.venv/bin/python`. The three agent role files in
`.claude/agents/` use the macOS form and say the same in reverse.

**The hooks find the interpreter themselves.** `.claude/settings.json` starts every hook
through `.claude/hooks/run_hook.sh`, which tries `bin` and then `Scripts`. Until
2026-10-02 it named the Windows path only. On macOS no hook could start, Claude Code
treated that as a non-blocking error, and the write guard and the seal were both off
with no message. See [`.claude/README.md`](../../.claude/README.md).

**The two machines run different Python versions.** `ruff.toml` sets
`target-version = "py314"`, so ruff can suggest syntax that Python 3.11 cannot run.
Run the test gate on macOS before accepting such a suggestion.

**The path in the old `CLAUDE.md` was wrong.** It named
`C:\Users\yinchenliu\Python3\python-3.14.2\python.exe`. That user directory does not
exist on the Windows machine — note `yinchenliu` against the actual `LiuYinchen`. Every
command in these docs uses the venv path instead, which is correct on any machine that
ran the setup below.

## 2. Creating it from scratch

Windows:

```bash
"D:/Software/Python.Python.3.14/python.exe" -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

macOS:

```bash
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` includes `requirements.txt`, so that one command installs both
the runtime dependencies and the gates.

### Verify it

```bash
.venv/Scripts/python.exe -c "import fastapi, pandas, numpy, scipy, yfinance, pdfplumber, anthropic; from google import genai; print('ok')"
```

`requirements.txt` pins no versions, so the two machines differ:

| Package | Windows, 2026-09-20 | macOS, 2026-10-02 |
|---|---|---|
| pandas | 3.0.6 | 3.0.6 |
| numpy | 2.5.3 | 2.4.6 |
| scipy | 1.18.1 | **1.17.1** |
| starlette | 1.6.0 | 1.7.0 |
| pytest | 9.1.1 | 9.1.1 |
| ruff | 0.16.8 | 0.16.9 |
| mypy | 2.3.1 | 2.3.1 |

**One test result depends on that difference.** On macOS, at `5dc28a0`,
`tests/unit/test_capm.py::test_beta_stops_when_the_market_series_has_no_variation`
fails. SciPy 1.17.1 raises its own `ValueError` for a constant regressor, before
`analysis/capm.py` reaches the check that names `market_returns`.

> **Warning — pandas 3.0 is a major version and no valuation has been run against it.**
> `ingestion/price_fetcher.py:66` branches on the pandas version to pick `"ME"` over
> `"M"` for month-end resampling. That branch is untested on 3.0 with real data. Treat
> any resampling result as unverified until a run confirms it.

## 3. The extraction credential

Extraction needs one on route A. Route B needs none.

On 2026-10-04, the Microsoft Foundry gateway and Anthropic API routes were removed on the user's decision ("remove the foundry gateway, we only keep two gateway, 1 is the api, another is the chat box from the claude code"; "I dont' have anthropic api KEY, i only have gemini and deepseek").

### The two routes

There are two routes to extraction:
- **Route A (API)**: reads the filing through the Google Gemini API, requiring `GEMINI_API_KEY`. The provider is `gemini` (transport `gemini-direct`).
- **Route B (Claude Code session)**: Claude reads the filing inside a Claude Code session (`extract-filing` skill) and writes a session file (`ingestion/session_extraction.py`). The provider is `claude` (transport `claude-code-session`). No API key is used.

### The default

`config.DEFAULT_EXTRACTION_PROVIDER` is **`"gemini"`**, and it is the only provider
default in the repository. `ingestion/`, `api/` and `cli.py` all read that constant,
so the CLI and the web app cannot disagree, and the number of PDFs you upload cannot
change which model reads them. The default Gemini model is **`gemini-3.1-pro-preview`**
(`_DEFAULT_MODELS` in `ingestion/claude_extractor.py`).

Calling `resolve_provider("claude", ...)` or `-p claude` stops and names route B.

### Setup for Route A

Create `.env` in the repository root — `config.py` loads it, and `.gitignore` already
excludes it:

```
GEMINI_API_KEY=...
```

### The order: the shell wins over `.env`

`config.py` reads `.env` once, with `dotenv_values`, and fills only the names that are
absent from the environment. A name that is set, even to an empty value, is not filled.
That is the behaviour of `load_dotenv(override=False)`. It has held since
`P13c-env-override` (2026-10-03). Before that, `config.py` used `override=True`. So
**a value set in the shell wins over `.env`.**

| You run | Result |
|---|---|
| `GEMINI_API_KEY=<key> …` | the shell's key is used, not the one in `.env` |
| `GEMINI_API_KEY= …` (empty) | **the key is off for that one run.** `resolve_provider` stops before any network call |
| `env -u GEMINI_API_KEY …` | **the key is NOT off.** The name is absent, so `config.py` fills it from `.env` |
| nothing | `.env` supplies the key |

**To run with the key off, set it empty for that run:**

```bash
GEMINI_API_KEY= .venv/bin/python cli.py …
```

**Never use `env -u` to prevent a paid API call while `.env` holds the key.** It does
not work under either load order. Backlog item 46
([refactor-backlog.md](../9-reference/refactor-backlog.md), item 46) holds the probe
table that measured this: with `override=False`, an empty shell value removes the key
and `env -u` does not. On 2026-10-02 an `env -u` run started Pass 1 on a real 10-K.

### Whether the key in use is the one in `.env` is in the output

`config.credential_origin` builds the `credential_source` label that
`describe_resolution` prints and the result page shows (rule 6). **The label is a
comparison of values, made at the moment the label is built.** The value in use in
`os.environ` is compared with the value that `.env` holds for the same name:

| Label | Meaning |
|---|---|
| `GEMINI_API_KEY (.env file)` | the value in use equals the value in `.env` |
| `GEMINI_API_KEY (shell or parent process, not .env)` | the value in use differs from the value in `.env`, or `.env` does not hold the name |

**A shell value that equals the file's value reads `(.env file)`.** That is harmless:
the key in use is the key in the file, whoever set it.

**The label says nothing about a value's history.** It does not say which process set
the value, or when. A child process inherits its parent's environment, and that
includes any value the parent filled from `.env`. Two attempts to record a value's
history were both broken at a process boundary (P13c rounds 1 and 2). So the label
states only a fact that each process can check for itself. A child spawned by
`python app.py` (uvicorn's reloader) labels the inherited key `(.env file)` when it is
the file's key. A value that a parent chose, or that code in the process replaced,
reads `(shell or parent process, not .env)`.

`config.py` writes nothing to the environment apart from the names it fills from
`.env`. It keeps the file's values for the three credential names in memory, to compare
them. It never prints them.

### What happens when nothing resolves

`resolve_provider` raises `ValueError` **before any network call**, naming both
remedies — the environment variable *and* `az login`. It never produces a client that
fails later with an unrelated message. That is rule 3, and it is the model for how the
rest of the codebase should behave.

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

| Machine | Scratch |
|---|---|
| Windows | `c:/tmp/` |
| macOS | `/tmp/` |

**Never write `c:/tmp/` on macOS.** It is a relative path there, so it lands inside the
repository.

Set `PYTHONDONTWRITEBYTECODE=1` so a script leaves no `__pycache__` behind.

## 6b. Reading a PDF page in a Claude Code session

Route B of the extraction (`docs/3-architecture/extraction.md`) has the session read the
filing. Claude Code's Read tool renders a PDF page only when `pdftoppm`, from the
poppler package, is installed.

**On the macOS machine it is not, and it cannot be installed as things stand.** Measured
2026-10-02: `brew install poppler` fails before it starts, because Homebrew 4.4.6 stops
with `unknown or unsupported macOS version: "27.0"`. Updating Homebrew is a change to
the machine outside this repository, so it is the user's decision.

**Route B does not need it.** `python -m ingestion.session_extraction text` prints a
page's text layer through `pdfplumber`, which the venv already has. On a text-based 10-K
that is enough, and it costs a session fewer tokens than a page image. Only a scanned
page needs the image.

## 7. What is gitignored, and one thing that is not

`.gitignore` covers `__pycache__/`, `.env`, `uploads/`, `.venv/`, `10K_filings/`.

**Two problems with it, both recorded in the backlog:**

1. It lists `CLAUDE.md`, but `CLAUDE.md` is **tracked**. Git does not ignore a tracked
   file, so the line does nothing except mislead — editing `CLAUDE.md` does dirty the
   tree.
2. It does not list `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/` or
   `.agent/.seal-baseline.json`. Running a gate or dispatching a subagent creates
   untracked directories.
