---
id: P15c-portable-session-paths
phase: 15 — two extraction routes
agent: programmer
depends_on: []
team: A (worktree `Valuation-wt/team-a`, branch `unit/team-a`)
---

# A session file names its PDFs relative to the repository, and loads from any directory (item 146)

## Objective

**The fact, on the writing side.** `session_extraction plan` records each PDF as an
absolute path. `cmd_plan` does `str(Path(pdf).resolve())` (`ingestion/session_extraction.py:873-875`
at `fde3e98`). Measured by the overall lead on `main`:

```
$ ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m ingestion.session_extraction plan \
    "2024:10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf" \
    "2026:10K_filings/WMT/Walmart Inc._10-K_2026-01-31_English.pdf" \
    -t WMT -n "Walmart Inc." -o <scratch>/plan.json --force
pdf_path values: ['/Users/yinchenliu/Documents/Git/DCF/Valuation/10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf',
                  '/Users/yinchenliu/Documents/Git/DCF/Valuation/10K_filings/WMT/Walmart Inc._10-K_2026-01-31_English.pdf']
```

**What followed.** `extractions/WMT.json` was written on the Windows machine and held
`C:\Users\LiuYinchen\Valuation\10K_filings\WMT\…`. On macOS the two tests that read it
skipped, and in a worktree the paths pointed at the main checkout's PDFs. The overall lead
rewrote the three values by hand to `10K_filings/WMT/<name>` at `2e9447a`.

**The fact, on the reading side.** The loader resolves a relative `pdf_path` against the
**working directory**. Measured on `main`, the same file:

| Working directory | `load_session_extraction("<repo>/extractions/WMT.json")` |
|---|---|
| the repository root | loads, 3 filings |
| `/tmp` | stops, for each filing: "the PDF 10K_filings/WMT/… is not on disk" |

So the hand fix holds only when a command runs from the repository root, and the next
`plan` run writes an absolute path again. Backlog item 146 holds both halves.

**When this unit is done**, `plan` writes a PDF inside the repository as a path relative to
the repository root, and the loader resolves a relative `pdf_path` against the repository
root, from any working directory. A session file with absolute paths still loads as before.

## What is already true — verify, do not redo

- `config.BASE_DIR` is `Path(__file__).parent` of `config.py`, so it is the repository
  root, and in a worktree it is the worktree root.
- `ingestion/filings.py`, `fingerprint_filings`, records `path=str(path.resolve())`. A
  relative path passed to it resolves against the working directory. So the loader must give
  it an absolute path.
- The gate form on `main` at `fde3e98`: **1606 passed, 0 failed, 0 skipped** at seeds 7,
  1234 and 99. Reproduce: `.venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=7`.
- The six real prompts hash as in `.agent/assignments/P14h-target-years.md`, "What is
  already true", with the repository path replaced by `<REPO>`.

If a measurement disagrees, stop and report the disagreement. Do not edit to make it agree.

## What to do

1. **Writing.** In `cmd_plan`, when a resolved PDF path is inside `config.BASE_DIR`, write it
   relative to `config.BASE_DIR`, with forward slashes on every machine
   (`10K_filings/WMT/<name>`). When it is outside, write the absolute path, as today.
   Reason: a tracked session file must name the same file on both machines and in every
   worktree.
2. **Reading.** Wherever the loader turns a recorded `pdf_path` into a file it opens,
   hashes or plans, resolve a relative path against `config.BASE_DIR`, never against the
   working directory. An absolute path is used as recorded. Reason: the same.
3. **Stops.** When a resolved PDF is not on disk, the message names the recorded
   `pdf_path` **and** the path it resolved to. Reason: rule 3, a stop names its input, and
   "not on disk" with a relative path does not say where the loader looked.
4. Update the format example in the module docstring (`"pdf_path": "/absolute/path/to/the.pdf"`)
   so it shows a repo-relative path, and say in one sentence that an absolute path is still
   accepted.

## Files in scope

- `ingestion/session_extraction.py` (programmer)
- `tests/unit/test_p15c_portable_session_paths.py` (tester, new file)

**Nothing else.** Work outside this list is a review finding, even if the change is good.
**If the fix cannot be made without changing `ingestion/filings.py`, stop**: write the
question under `## Questions for the overall lead` and tell the user. Do not edit it.

## Out of scope

- `ingestion/filings.py`: `plan_filings` and `fingerprint_filings` stay as they are.
- `ingestion/claude_extractor.py`: team B's unit `P14h-target-years` is in flight on it.
- `extractions/WMT.json`: the overall lead owns `extractions/`. It already holds relative
  paths.
- `.claude/skills/extract-filing/SKILL.md`: the overall lead owns `.claude/`.
- `.venv`, `requirements*.txt`: a unit branch installs nothing. The venv is shared.
- The four record files and `docs/`: see "Pilot rules".

## Done-criteria

Run every command **from the worktree root**, with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`
in front, unless the criterion says otherwise.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | `plan` writes repo-relative paths for PDFs in the repository | both values `10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf` and `…_2026-01-31_English.pdf` | the `plan` command in "Objective", into a scratch file outside the repository, then read its two `pdf_path` values |
| 2 | `plan` writes an absolute path for a PDF outside the repository | the absolute path | the tester's test, with a PDF under `tmp_path` |
| 3 | the tracked session file loads from another directory | `3` filings, no stop | `cd /tmp && PYTHONPATH=<worktree> <worktree>/.venv/bin/python -c "from ingestion.session_extraction import load_session_extraction as L; print(len(L('<worktree>/extractions/WMT.json').filings))"` |
| 4 | it still loads from the repository root | `3` filings, every page, unit and hash check passing | `.venv/bin/python -c "from ingestion.session_extraction import load_session_extraction as L; print(len(L('extractions/WMT.json').filings))"` |
| 5 | a session file with absolute paths still loads | loads, with the same figures | the tester's test: a copy of `extractions/WMT.json` under `tmp_path` with each `pdf_path` made absolute |
| 6 | a missing PDF names the recorded and the resolved path | both strings in the `ValueError` | the tester's test |
| 7 | the tests in 3 and 5 kill the old reading | red with resolution against the working directory restored, green without | the tester reports the mutation and both counts |
| 8 | the six real prompts are unchanged | the six hashes in `P14h-target-years.md` | the command there, for `--filing` 0, 1, 2 and `--pass` 1, 2 |
| 9 | the gate form at three orders | `0 failed`, `0 skipped`; passed = `main`'s 1606 plus the tester's new tests | `.venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=<n>` for n = 7, 1234, 99 |
| 10 | lint, types, census unchanged | `4 errors`, all `BLE001`, none in a unit file; `2 errors in 2 files`; `64` | `docs/8-build/environment.md`, section 4, and the grep at `docs/2-rules/rules.md:65` with `pipeline.py` added |
| 11 | the unit stayed in scope | only the two files above, this assignment, `P15c-portable-session-paths-tests.md` and new files under `.agent/journal/` | `git diff --name-only main...HEAD` |

**Every criterion is a measurement, never an opinion.**

## Pilot rules (worktree)

This unit runs in a git worktree, beside team B's unit. [docs/8-build/worktree-teams.md](../../docs/8-build/worktree-teams.md)
owns the scheme. These five points bind this unit:

1. **Do not write** `STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md` or
   `docs/9-reference/refactor-backlog.md`. The overall lead writes them on `main` after the
   merge. A subagent's own journal entry, with its own file name, is allowed.
2. **The build lead does not set a queue state.** It writes `## Handoff` at the end of this
   file, **commits it with the unit**, and tells the user "P15c-portable-session-paths is
   ready for the overall lead". In `P1h-mac-gate` round 2 the handoff was left uncommitted.
3. **The handoff names the commit hash. Do not amend a commit**: make a new one.
4. **Install nothing.** `.venv` in the worktree is a link to the main checkout's venv.
5. **No hook protects a Gemini subagent.** After each subagent run, run `git status` and
   reject the run if it wrote outside its role or outside Files in scope.

**A test must call the code it is about, and must hold on Python 3.11 and 3.14.**
`P1h-mac-gate` round 1 asserted a property of one Python version, and `P3e`'s review found a
test that called no production code (backlog item 148). The tester's trap is the first
section of `.claude/agents/tester.md`.

## Citations

- `docs/2-rules/rules.md`, rule 3 — a stop names its input; rule 4 — a figure walks back to
  its page, which needs the PDF the session read.
- `docs/9-reference/refactor-backlog.md`, items 117 and 146 — the history of this defect.
- `docs/3-architecture/extraction.md` — route B and the session file.

## Known open items

- Item 146 names `ingestion/session_extraction.py:873-875`. The lines may have moved under
  `P1h-mac-gate`; the code is the `resolved = [...]` list in `cmd_plan`.

## Backlog items this unit is NOT fixing

Each sits in `ingestion/session_extraction.py`. Leave them alone.

- 53 — `_NRI_SCHEMA` imported by its private name.
- 60 — the `plan` message "The fiscal year comes from the filename…".
- 95 — the unreachable fiscal-year check in `cmd_plan`.
- 120 — the repeated `[MERGE]` summary line.
- 123, 125 — the discarded `bool` and the replaced `surrogateescape` handler.

## Handoff

### Commits
- `f8e8caa`: `P15c-portable-session-paths: repo-relative PDF paths for tracked sessions (item 146)`

### Verdicts
- Programmer: `complete`, entry: `.agent/journal/2026-10-09T0220-programmer-p15c-portable-session-paths.md`
- Code reviewer: `approved`, entry: `.agent/journal/2026-10-09T0240-code_reviewer-p15c-portable-session-paths.md`
- Tester: `pass`, entry: `.agent/journal/2026-10-09T0245-tester-p15c-portable-session-paths.md`

### Gates
- Test gate (seed 7): `0 failed, 1620 passed, 0 skipped in 56.69s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=7`)
- Test gate (seed 1234): `0 failed, 1620 passed, 0 skipped in 57.12s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=1234`)
- Test gate (seed 99): `0 failed, 1620 passed, 0 skipped in 56.50s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=99`)
- Full suite (seed 7): `2 failed, 1620 passed in 56.74s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider --randomly-seed=7`)
  Failures are only the two intentional red tests: `test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_valuation_with_session_file_and_files_on_a_cache_hit_stops`.
- Unit tests: `14 passed in 21.84s` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_p15c_portable_session_paths.py`)
- Tracked session load from `/tmp`: `3` filings loaded, no stop (`cd /tmp && PYTHONPATH=<worktree> <worktree>/.venv/bin/python -c "from ingestion.session_extraction import load_session_extraction as L; print(len(L('<worktree>/extractions/WMT.json').filings))"`)
- Tracked session load from repo root: `3` filings loaded (`.venv/bin/python -c "from ingestion.session_extraction import load_session_extraction as L; print(len(L('extractions/WMT.json').filings))"`)
- Lint: `4 errors`, all `BLE001`, 0 in unit files (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m ruff check .`)
- Types: `2 errors in 2 files` (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports`)
- Rule 3 census: `64` (`grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" '--include=*.py' models analysis api ingestion pipeline.py | wc -l`)
- Web root: HTTP 200 (`ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -c "from starlette.testclient import TestClient; from app import app; print(TestClient(app).get('/').status_code)"`)

### Findings and notes
- Criterion 1: `cmd_plan` writes repo-relative paths with forward slashes for files inside `config.BASE_DIR` (`10K_filings/WMT/...`).
- Criterion 2: `cmd_plan` writes absolute paths for files outside `config.BASE_DIR`.
- Criterion 3 & 4: Tracked session file loads from `/tmp` as well as repository root (3 filings, all checks passing).
- Criterion 5: Session files with recorded absolute paths continue to load cleanly.
- Criterion 6: Missing PDF stops name both recorded and resolved paths (`the PDF <recorded> (resolved to <resolved>) is not on disk`).
- Criterion 7 (mutation kill): Mutating `_resolve_pdf_path` to resolve against `cwd` instead of `config.BASE_DIR` fails 4 tests in `tests/unit/test_p15c_portable_session_paths.py`. All 14 tests pass when restored.
- Criterion 8: Prompt hashes match `P14h-target-years.md` byte-for-byte for all 6 combinations.

### Questions for the overall lead
None.


## Overall lead review

**Round 1, 2026-10-08. Verdict: `accepted`.** Branch `unit/team-a` at `f8e8caa` (the unit)
and `6c55e7d` (the handoff, committed, no amend). This unit was built before the test review
joined the loop (`919afd7`), so I ran T1 to T5 myself.

| # | Check | I measured | Agree? |
|---|---|---|---|
| 1 | `plan` writes repo-relative paths | `['10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf', '10K_filings/WMT/Walmart Inc._10-K_2026-01-31_English.pdf']` | yes |
| 3 | the tracked file loads from `/tmp` | 3 filings, `validation_errors == []` | yes |
| 4 | and from the repository root | 3 filings, `validation_errors == []` | yes |
| 7 | the tests kill the old reading | M1, a relative path resolved against the working directory: **5 failed, 9 passed** from `/tmp`. M2, `plan` writing the absolute path: **2 failed, 12 passed**. Control 14 passed | yes |
| 8 | the six real prompts | the six hashes of `P14h-target-years.md` | yes |
| T1 | every test calls the code | yes: `_format_pdf_path`, `_resolve_pdf_path`, `cmd_plan`, `load_session_extraction` | yes |
| T3 | no fallback asserted | the search finds `ret == 0` (a command's success) and `validation_errors == []` (criterion 4 states it) | yes |
| T5 | coverage | `_format_pdf_path` 7 of 7 statements; `_resolve_pdf_path` 5 of 5 statements, 2 of 2 branches | — |

**Three findings, none `major`, recorded as backlog item 150 for a tester-only follow-up.**

- **F1, `minor` (T2).** `test_cmd_plan_writes_repo_relative_paths_for_repo_filings` passes
  `2024:10K_filings/WMT/…` to `cmd_plan`, which resolves it against the working directory,
  as a CLI should. So the test fails when pytest starts elsewhere: from `/tmp`, **1 failed,
  13 passed**. Pass `config.BASE_DIR / WMT_PDF_REL_2024` instead.
- **F2, `minor` (T4).** The two missing-PDF tests assert `fake_rel in err_text` and the
  resolved path, which criterion 6 states, and then also the whole message copied from the
  code's f-string. The last assertion is a photograph of wording
  (`docs/5-testing/strategy.md`, section 1).
- **N1, `note`.** The 14 tests take **21.7 s**, and the gate form went from about 33 s to
  about 57 s: every load reads the three real Walmart PDFs (3.6 s each), and the `cmd_plan`
  test 7.5 s. Every gate run in this repository now pays that. One real-file load is the
  requirement; the others can share it or use `tests/unit/_text_pdf.py`.
