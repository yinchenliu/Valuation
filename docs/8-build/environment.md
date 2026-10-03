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

Extraction needs one. Nothing else does. **On the Windows machine it is not a key** — it
is an Entra ID sign-in. **On macOS it is a key.** No Foundry variable is set there and
`az` is not installed, so Claude is reached over the public API with
`ANTHROPIC_API_KEY` from `.env` (measured 2026-10-02). Read the whole of this section
before setting anything.

### The default

`config.DEFAULT_EXTRACTION_PROVIDER` is **`"claude"`**, and it is the only provider
default in the repository. `ingestion/`, `api/` and `cli.py` all read that constant,
so the CLI and the web app cannot disagree, and the number of PDFs you upload cannot
change which model reads them. The default Claude model is **`claude-opus-5`**
(`_DEFAULT_MODELS` in `ingestion/claude_extractor.py`).

### Provider vs transport — they are different things

There are two **providers**: `claude` and `gemini`. Claude is reachable over two
**transports**, and it is the same Claude either way:

| Configured | Transport | Client |
|---|---|---|
| `ANTHROPIC_FOUNDRY_BASE_URL` or `ANTHROPIC_FOUNDRY_RESOURCE` | Microsoft Foundry gateway | `anthropic.AnthropicFoundry` |
| neither | the public Anthropic API | `anthropic.Anthropic` |

Foundry is **not a third provider**, and `Provider` stays
`Literal["claude", "gemini"]`. Adding a third value would be wrong: the model did not
change, only the road to it did.

### Setup on the Windows machine (Foundry + Entra ID)

`ANTHROPIC_FOUNDRY_BASE_URL` is already set in the environment. There is **no API
key** and there will not be one. Two steps:

```
pip install -r requirements.txt     # brings azure-identity
az login                            # the credential; no key anywhere
```

That is all. `ingestion/claude_extractor.py` builds the token provider with
`get_bearer_token_provider(DefaultAzureCredential(), config.ENTRA_TOKEN_SCOPE)`.
**Library code never shells out to `az`** — a subprocess call is untestable and
breaks wherever the CLI is absent. `az login` only populates the credential store
that `DefaultAzureCredential` reads.

### The scope, and the 401 that tells you it is wrong

```
ENTRA_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
```

This is the **audience the gateway validates**. It is not a URL the platform calls,
and it is not a secret.

**`https://ai.azure.com/.default` is rejected.** If you use it you get an HTTP 401,
and the gateway names the audience it wanted in the body of that 401. That message is
the fastest diagnosis available for this whole area — read it before changing
anything else. A 401 here means the *scope*, not the sign-in.

### PDF input on Foundry is a beta feature

Native PDF ingestion through the Foundry gateway is **beta** on Anthropic's platform
availability table. It was measured working on 2026-09-21: a one-line PDF reading
`Total net revenues 4321` returned `4321`, and a three-year statement set extracted
with every arithmetic reconciliation passing.

**Treat a future failure here as a platform change, not as a defect in this
repository.** Check the availability table first.

### Setup elsewhere (no Foundry gateway)

Create `.env` in the repository root — `config.py` loads it, and `.gitignore` already
excludes it:

```
# Claude over the public Anthropic API — only when no Foundry gateway is configured:
ANTHROPIC_API_KEY=...
# Gemini — unreachable from the network this platform runs on, but kept working:
GEMINI_API_KEY=...
```

### Warning: `.env` wins over the environment

`config.py` loads `.env` with `override=True`. So a key in `.env` replaces the same
variable in the environment, and `env -u ANTHROPIC_API_KEY …` does **not** remove it.
**Never rely on unsetting a variable to prevent a paid API call while `.env` holds the
key.** Neither `env -u` nor an empty value works while `override=True`. To run with no
credential, replace `ingestion.claude_extractor._call_llm` with a stub, or move `.env`
aside. Backlog item 46 holds the measurement.

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
