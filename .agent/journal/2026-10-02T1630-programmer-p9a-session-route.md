---
agent: programmer
assignment: P9a-session-route
round: 1
status: complete
files_touched: [ingestion/claude_extractor.py, ingestion/filings.py, ingestion/session_extraction.py, cli.py, .gitignore, docs/3-architecture/extraction.md, docs/2-rules/llm-boundary.md, docs/3-architecture/entry-points.md]
verdict:
---

# P9a-session-route — a session file as a second extraction route, meeting route A at the parser

Started 2026-10-02T1630 at commit `cde33cb`. Outcome: **`ok`**. Every scratch file is
under `/tmp/p9a/`.

## What I did

Lifted route A's plan, merge, prompts and parsers out of `extract_multi_year` and the
two runners into public functions in `ingestion/claude_extractor.py` (`FilingPlan`,
`plan_filings`, `merge_filing_extractions`, `pass1_prompts`, `pass2_prompts`,
`parse_pass1`, `parse_pass2`, plus `PASS1_YEAR_FIELDS` / `PASS1_BALANCE_SHEET_FIELDS`),
and made route A call them; extended `Transport` and `CredentialKind` with
`"claude-code-session"`. Moved filing discovery and hashing from `cli.py` to a new
`ingestion/filings.py`, verbatim. Wrote route B in `ingestion/session_extraction.py`:
the `session-extraction-v1` file, the loader `load_session_extraction` with the stop
list, the route label, and five subcommands (`plan`, `locate`, `text` — added by the
mid-run amendment — `prompt`, `check`). Added `--session-file` to `cli.py`, with stage 1
split into `_extract_via_api` (the old code, moved) and `_extract_from_session_file`.
Added `extractions/` to `.gitignore` and updated the three owning docs. Proved, with a
stubbed `_call_llm`, that the same JSON gives equal statements, equal items and
byte-equal prompts by both routes, for one filing and for three.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | one plan and one merge | **pass** | `grep -n "def plan_filings\|def merge_filing_extractions\|plan_filings(\|merge_filing_extractions(" ingestion/*.py` → definitions `claude_extractor.py:1265`, `:1309`; calls `claude_extractor.py:1486`, `:1533` (`extract_multi_year`), `session_extraction.py:302` (loader, via `_session_plans`), `:605` (loader), `:682` (`plan` subcommand). One definition each |
| 2 | route A unchanged | **pass** | gate: `1 failed, 197 passed` — the one failure is `test_capm.py::test_beta_stops_when_the_market_series_has_no_variation`, the same set as baseline. Also: the four prompt constants hash identically before/after (see Measurements) |
| 3 | same JSON, same result | **pass** | `/tmp/p9a/equal.py` (output `/tmp/p9a/equal.out`): one filing (Walmart 2026, bare path, fiscal 0) and three (Chipotle 2023-25). Both print `FinancialStatements equal: True`, `NonRecurringItem lists equal: True`, `prompts route A sent == prompts route B prints: True` (2 and 6 prompt pairs). The three-filing case includes a deliberate operating-income error in 2022 (route A ran both retries and kept the figures with `[Pass 1 WARN]`; route B returned the same error in `validation_errors`), a `low` item, and a duplicate 2023 item that the merge dropped in both. Negative control `/tmp/p9a/negative.py`: one `sbc` changed 25→26 in route B → `equal ... False` |
| 4 | a changed PDF stops | **pass** | `/tmp/p9a/stops.py`: a copy of the CMG 2025 PDF loads unchanged, then one byte appended → `ValueError: …stop_pdf.json: filings[2] (scratch_copy_2025.pdf): the PDF /tmp/p9a/scratch_copy_2025.pdf has changed since the session read it. sha256 recorded 74667e458cd46fa7…, now e49168ba4eb8acfa…; size recorded 343,973 bytes, now 343,974.` Deleted → `…is not on disk…` |
| 5 | a missing key stops | **pass** | same script: `sbc` deleted from 2022 → `ValueError: …stop_sbc.json: filings[0] (Chipotle Mexican Grill Inc._10-K_2023-12-31_English.pdf), year 2022: key 'sbc' is absent.` An explicit `revenue: 0` loads (`0.0`) |
| 6 | the CLI runs from a session file with no credential | **pass, with a caveat on the measuring command** | The assignment's `env -u …` command does **not** remove the credential here: `config.py:15` re-loads `.env` with `override=True` (see incident). It ran (`/tmp/p9a/cli_session.out`, exit 0) but that proves nothing about credentials. Stronger proof, `/tmp/p9a/no_api.py`: imports `config`, then pops every credential variable, makes `anthropic` and `google.genai` unimportable, replaces `_call_llm` with a raise, and shows `resolve_provider("claude")` now stops; then `cli.main()` with `--session-file /tmp/p9a/cli_CMG.json` → exit 0, stage 1 line `Provider: CLAUDE \| Model: claude-opus-5 \| Transport: Claude Code session — figures read from the PDF in a Claude Code session and stored in the session file /private/tmp/p9a/cli_CMG.json…  \| Credential: none — no API call was made…`, `Implied Price: $ 1846.06`. **The figures in that file are invented; the price means nothing.** No input to it came from a filing. (`cli_CMG.json` = `eq_CMG.json` with `long_term_debt` 300, because the first run correctly stopped at WACC on "interest expense with zero debt" — the invented data was inconsistent, not the code) |
| 7 | `locate` finds the statements | **pass** | `.venv/bin/python -m ingestion.session_extraction locate /tmp/p9a/cmg.json --filing 2` (Chipotle 2025 10-K, 60 pages): title lines — income 29, 33; balance sheet 28, 33, 35-37; cash flows 30. **Reviewer: open page 29** — `text … --pages 28-30` shows `CONSOLIDATED STATEMENTS OF INCOME AND COMPREHENSIVE INCOME` and `Total revenue 11,925,601 11,313,853 9,871,649` on 29, `CONSOLIDATED BALANCE SHEETS` on 28, `CONSOLIDATED STATEMENTS OF CASH FLOWS` on 30. Walmart 2026: income 21, B/S 22, C/F 23 all listed |
| 7b | `text` prints a statement page | **pass** | `.venv/bin/python -m ingestion.session_extraction text /tmp/p9a/wmt2026.json --filing 0 --pages 21-21` → line 1 `=== page 21 ===`, line 66 `Net sales $ 706,413 $ 674,538 $ 642,637`. `--pages 1-21` → `ERROR: --pages 1-21 is 21 pages; at most 20…`, exit 2 |
| 8 | the boundary holds | **pass** | `grep -n "import anthropic\|genai\|_SYSTEM_PROMPT\|API_KEY" ingestion/session_extraction.py ingestion/filings.py` → no output |
| 9 | discovery moved, not copied | **pass** | `grep -n "def _discover_filings\|def parse_pdf_args\|def fingerprint_filings\|class InputFingerprint" cli.py` → no output. Verbatim check against `git show HEAD:cli.py`: all three segments `present verbatim in ingestion/filings.py: True` (only rename `_discover_filings`→`discover_filings`) |
| 10 | no new lint or type errors | **pass** | ruff `Found 5 errors.`, all BLE001, the same five sites. mypy `Found 10 errors in 4 files (checked 20 source files)` — **down from 14**: the four `assignment` errors at the old merge (`stmt` reused for three statement types) are gone because the merge now names its loop variables `income`, `balance`, `cashflow` |
| 11 | the web app still serves | **pass** | `200` |

Census: `116`, unchanged. (It read 118 mid-run because two of my comments quoted the
pattern `.get(field, 0)`; I reworded them. No code site was added.)

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Route A's runners and the wrappers both call new private builders `_pass1_prompt_pair` / `_pass2_prompt_pair` | step 5 allows either; the runners take `target_years`/`include_bs`, not a plan, and have no `pdf_path`/`fiscal_year` to build one | Making runners call the wrappers would need a fake `FilingPlan`. The two cannot diverge because the system prompt **and** the user prompt each come from one return statement, and the target years reach both through one helper `_plan_target_years`; criterion 3 shows `sent == printed` for 8 prompt pairs |
| The retry calls in the runners now pass the local `system_prompt` instead of the module constant | same object (`_pass1_prompt_pair` returns the constant itself; the equality stub tests `is`) | keeps every call in the runner on the one source |
| Split `_FINANCIALS_SCHEMA` into `_FINANCIALS_YEAR_SCHEMA` and `_FINANCIALS_BALANCE_SHEET_SCHEMA`, and export `PASS1_YEAR_FIELDS` / `PASS1_BALANCE_SHEET_FIELDS` | the loader must check "any key `_FINANCIALS_SCHEMA` names", and step 5 forbids importing a `_` name | the prompt's schema text is built from the same dicts, so the key list cannot drift from the prompt. Hashes of `_FINANCIALS_SCHEMA_STR` and `_FINANCIALS_SYSTEM_PROMPT` unchanged |
| The single-filing branch of `extract_multi_year` now passes `target_years=None, include_bs=True` explicitly from the plan | step 4: "keep that branch as it is"; those are exactly `extract_financials`' defaults | criterion 1 wants the plan used by route A; passing the plan's values is identical output and means the plan, not a default, decides. It is not passed through the merge |
| The loader re-runs `plan_filings` and stops if the file's order, `target_years` or `include_bs` differ | rule 2 (one plan); without it a hand-edited file merges differently from route A on the same filings | trusting the file's plan would give route B a second planner — the backlog item 7 shape |
| With several filings, `plan` and the loader stop on a filing with no fiscal year | rule 3 | route A's CLI silently drops such filings (`cli.py`, `valid = [(y, p) … if y > 0]`). Copying that would copy a silent drop; see Findings |
| A non-number (null, string, NaN, bool) in a schema key stops, naming the key | rule 3; `json` accepts `NaN` | route A's `float(None)` would raise a bare `TypeError` naming nothing |
| An empty `pages_read` for a written pass stops | rule 4: the locator is how a reader walks a figure back to a page | not in the assignment's stop list; it is the one addition beyond it besides the type checks. Easy to drop if the reviewer disagrees |
| All per-filing problems and the model problem are collected, then raised as one `ValueError` | the skill (`.claude/skills/extract-filing/SKILL.md` step 2.5) runs `check` before the model is set and expects Pass 1 problems | stopping at the first would hide every Pass 1 problem behind "model is null" |
| `SessionExtraction` has a sixth field, `filings: tuple[SessionFiling, ...]` | step 12 needs each PDF's sha256 prefix and pages at stage 1; P9b will need the same | re-reading the JSON in `cli.py` would be a second reader of the format |
| `-p` default changed to `None`, resolved to `config.DEFAULT_EXTRACTION_PROVIDER` after parsing | so `-p` with `--session-file` is refused rather than silently ignored | without `--session-file` the value is the same constant; help text unchanged. `-m`, `--cache-dir`, `--no-cache` are refused the same way |
| `print_non_recurring_items(items, identified_by)` takes the label as printed; the API caller passes `args.provider.upper()` | step 12 | API-route output byte-identical; session route prints `identified by a Claude Code session, model claude-opus-5 as declared` |
| `_build_claude_client` refuses a `claude-code-session` resolution | rule 6 | otherwise it would fall through to `ANTHROPIC_API_KEY` and make a paid call under a label that says none was made. Shown: `guard: This ProviderResolution labels a Claude Code session file …` |
| `locate` marks a page by a *title line* (title, no digit, ≤80 chars), not by position | measured: Walmart 2026 packs 2-3 printed pages per PDF page | listed pages include a few false positives; the true pages are always in the list on both filings measured |
| `--filing N` is 0-based | the skill writes into `filings[N].pass1` | matches the JSON array index in every message |
| Subcommand dispatch is an `if` chain on literal command names | rule 2 forbids a function selected at run time | `set_defaults(func=…)` would be a dispatch table |
| `# noqa: TRY004` on five `raise ValueError` after `isinstance` checks, with the reason in `_read_session_json`'s docstring | step 10 fixes the loader's exception as `ValueError` | a `TypeError` for "wrong JSON type in a data file" would split one contract into two exception types |

**No code was changed to reach a target number.**

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| session file / JSON / top-level object | stops, names the file | `_read_session_json` `session_extraction.py:186` |
| `format` | stops (absent or wrong) | `stops.py` `[format]` |
| `ticker` | stops (absent, empty) | `_read_identity:214` |
| `company_name` | stops if absent or not a string; **an empty string is accepted** and `parse_pass1` then takes the Pass 1 answer's name, as route A does with `-n ""` | `_read_identity:214`. A label, not a figure; matching route A was the requirement |
| `extracted_by.model` | stops (absent, empty, null) | `stops.py` `[model empty]`, `[model absent]` |
| `extracted_by.tool`, `.date` | **not read** | module docstring |
| `filings` | stops (absent, empty, not a list) | `_session_plans:262` |
| `fiscal_year`, `pdf_path`, `target_years`, `include_bs` | stop (absent, wrong type, differs from `plan_filings`) | `stops.py` `[plan edited by hand]` |
| `pdf_sha256`, `size_bytes` | stop (absent, wrong type) | `_pdf_problems:340` |
| the PDF itself | stops (missing, sha256 differs) | criterion 4 |
| `pass1`, `pass2` | stop (absent, null, not an object) | `stops.py` `[pass1 null]`, `[pass2 null]` |
| each of the 19 `PASS1_YEAR_FIELDS` | stops (absent, non-number); explicit 0 accepted | criterion 5; `[revenue null]` |
| each of the 17 `PASS1_BALANCE_SHEET_FIELDS` when `include_bs` | stops (absent, non-number; `year` must be a positive int) | `[B/S key absent]`, `[include_bs but no B/S year]` |
| `latest_balance_sheet` when not `include_bs` | stops unless exactly `{}` | `[B/S where plan has none]` |
| pass1 `ticker`, `company_name`, `currency`, `units` | **not checked by the loader.** `ticker` is never reached (the file's ticker is non-empty, so `parse_pass1`'s `ticker or data.get(...)` fallback is dead); `company_name` is reached only when the file's is `""` (row above); `currency`/`units` are read by nothing in the repository | backlog item 1's parser, unchanged by instruction |
| pass2 items | stop via route A's parser (no `confidence`, no `source`, missing `year`/`amount`/…), wrapped in a `ValueError` naming the filing | `[pass2 item without confidence]` |
| `pages_read.pass1/.pass2` | stop (absent, not a list of positive ints, empty for a written pass) | `[pages_read.pass2 empty]` |
| `_filing_label`'s `entry.get("pdf_path")` | used only to build a message prefix; the value is checked as required right after | `session_extraction.py:255` |
| CLI `-t` / `-n` in session mode | optional; when given and different from the file, stops | `/tmp/p9a/cli_args.sh` output |
| CLI `--session-file` with PDFs, or neither | `argparse` error, exit 2 | same |

**No "defaults to" row for a figure.**

## Measurements

### Baseline at `cde33cb` — every row of the assignment's "already true" table agrees

| Fact | Measured |
|---|---|
| test gate | `1 failed, 197 passed` — the one failure is `tests/unit/test_capm.py::test_beta_stops_when_the_market_series_has_no_variation` |
| lint | `Found 5 errors.` |
| types | `Found 14 errors in 4 files (checked 18 source files)`; 5 in `claude_extractor.py` (`:486`, `:1338`, `:1341`, `:1342`, `:1345`) |
| home page | `200` |
| census | `116` (note: under zsh the `--include=*.py` must be quoted, or zsh's glob error makes the count read 0) |
| four definitions in `cli.py` | `:140`, `:203`, `:258`, `:296` |
| imports elsewhere | none outside docs/journal |
| result page label fields | `provider`, `model`, `transport_label`, `credential_source` at `templates/valuation_result.html:290-293` |

Prompt hashes before any change (`/tmp/p9a/prompt_hashes_before.txt`), to prove route A's
prompts are byte-identical afterwards:

```
_FINANCIALS_SYSTEM_PROMPT 2b107058997b8662
_NRI_SYSTEM_PROMPT a1027b5f8d5469e8
_FINANCIALS_SCHEMA_STR ef0a78a87467737c
_NRI_SCHEMA_STR db4a1a6f78732339
None True 192b8313f41ff80f      (_build_financials_prompt(target_years, include_bs))
[2024] False 54f25eea0b96f156
[2025] True 23347d69a61e95d9
None False 95a39001817b7b7d
```

### After

| Gate | Result |
|---|---|
| test gate | `1 failed, 197 passed` — failure set `{test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}`, identical to baseline. (Full `pytest -q`: 3 failed = that one plus the two `*_rule3_red.py` tests, neither touched) |
| lint | `Found 5 errors.` — BLE001 at `api/routes_valuation.py:326`, `:568`, `cli.py:1107`, `ingestion/claude_extractor.py:1051`, `tests/test_e2e_all_googl.py:106`: the same five sites, moved lines |
| types | `Found 10 errors in 4 files (checked 20 source files)` |
| home page | `200` |
| census | `116` |
| prompt hashes | all four constants identical to the baseline above |

## Scope amendment received mid-run

The orchestrator amended the assignment after dispatch (2026-10-02): step 9 gained a
fifth subcommand, `text FILE --filing N --pages A-B`, measured by a new criterion 7b.
Reason given: the Read tool cannot render PDF pages on this Mac (no `pdftoppm`), so a
session reads statements from the PDF text layer. Implemented as part of this unit.

## Progress log

- Part 1 done in `ingestion/claude_extractor.py`. Prompt hashes re-measured after the
  schema split: all four constants identical to the baseline.
- A first scripted edit misplaced the `extract_multi_year` body into `plan_filings`
  (my anchor string matched both functions); repaired by a second script before any run.
  Ruff and mypy on the file then reported only the pre-existing `:519` (was `:486`) error.
- Part 2 done: the four definitions cut from `cli.py` into `ingestion/filings.py` by a
  script (cut, not retyped); `cli.py` imports them; `hashlib` and `re` imports dropped
  from `cli.py` (ruff F401 after the move).
- Part 3 written: `ingestion/session_extraction.py`. `plan`, `locate`, `text`, `prompt`,
  `check` all exercised on `/tmp/p9a/wmt2026.json` and `/tmp/p9a/cmg.json`.
- `locate` first used "title in the first 6 lines of the page" and found no income or
  balance sheet heading on Walmart 2026: that PDF prints two or three printed pages per
  PDF page, so titles sit mid-page. Changed to a *title line* rule (holds the title, no
  digit, at most 80 chars). Re-measured: Walmart income 21, B/S 22, C/F 23 are all
  listed; Chipotle 2025 income 29, B/S 28, C/F 30 are all listed (plus a few false
  positives from wrapped note text; it is a locator, not a decision).
- `check` first stopped on the null model before listing Pass 1 problems, which would
  defeat the skill's step 2.5. The model problem is now collected with the per-filing
  problems; one `check` lists all.
- **Incident, recorded as it happened.** Probing the CLI's argument errors, my script's
  last case was the API route, `env -u ANTHROPIC_API_KEY … cli.py 10K_filings/Chipotle
  -t CMG`, meant to show the API route still stops on a missing credential. It did not
  stop: `config.py:15` runs `load_dotenv(BASE_DIR / ".env", override=True)`, so the key
  in `.env` is re-loaded after `env -u` removed it. The run printed `Credential:
  ANTHROPIC_API_KEY (environment)` and `[Pass 1] Extracting financials (all years)...`
  for the Chipotle 2023 10-K and exited 1. Its error line was lost to my output filter
  (stderr unbuffered, stdout piped), so **I cannot say whether one Pass 1 API call was
  billed**. I did not re-run it. No other run in this unit reached the API route.
  Consequence for criterion 6: `env -u` does not prove "no credential"; see the
  criterion's row for the stronger proof used instead.

## What I did not do

- **`api/`, `templates/`** — out of scope (P9b). `api/routes_valuation.py:123`'s mypy
  `arg-type` error (`list[tuple[int, str]]` against `list[tuple[int, str | Path]]`) is
  untouched; `plan_filings` takes the same parameter type by the assignment's fixed
  signature, and route B annotates its list to satisfy it.
- **Route A's parser** — unchanged, as instructed (backlog items 1 and 10).
- **The fiscal-year-from-filename gap** — moved, not fixed (LHX 2026).
- **No real session extraction.** Every figure in every scratch session file is
  invented; the only real inputs are the PDFs (hashed) and the page texts `locate` and
  `text` printed.
- **No tests** — the tester's.
- `git status` also shows `docs/8-build/environment.md`, `docs/8-build/phases.md` and
  `docs/9-reference/refactor-backlog.md` modified, and `.claude/skills/extract-filing/`
  plus two more assignments untracked. **Not mine**: they were changed outside this
  unit (`phases.md` was already modified at dispatch). I did not open or edit them.
- `docs/3-architecture/extraction.md` still opens "1,023 lines" and its "Known defects"
  table still says 46 `.get` calls and 16 mypy errors. Stale before this unit; I did not
  re-measure them, so I did not change them.

## Findings for the orchestrator

1. **`env -u ANTHROPIC_API_KEY` does not unset the credential on this machine.**
   `config.py:15` is `load_dotenv(BASE_DIR / ".env", override=True)`. Criterion 6's
   command therefore cannot prove "no credential", and any instruction that tells a
   user to unset a variable to avoid a paid call is wrong while `.env` holds the key.
   `override=True` also means `.env` beats an explicit environment variable, the
   reverse of the usual precedence. Worth a unit, or a line in
   `docs/8-build/environment.md` section 3.
2. **Possible paid call during this unit.** One probe ran route A for the Chipotle
   2023 10-K because of finding 1 (see the progress log). I cannot tell whether a Pass 1
   call was billed.
3. **Route A's CLI silently drops a filing with no fiscal year when several are given**
   (`cli.py` `_extract_via_api`: `valid = [(y, p) for y, p in filings if y > 0]`). Rule
   3. Route B refuses the same input instead, so the two routes now differ on that
   input: A drops a PDF without a word, B stops and names it.
4. **mypy fell 14 → 10** as a side effect of the merge move (backlog item 11: four of
   the five `claude_extractor.py` errors were the reused `stmt` variable). STATUS's
   figure is now stale.
5. **`locate` is a heuristic.** On the two filings measured, every true statement page
   is in its list, with a few false positives from wrapped note text. A filing whose
   titles carry a digit on the same line (e.g. "Consolidated Balance Sheets 2025")
   would be listed only under "mentioned on". The skill should tell a session to confirm
   with `text` before reading figures.
6. **A single bare PDF is planned with `fiscal_year` 0**, as `parse_pdf_args` gives
   route A. The session file then carries `"fiscal_year": 0`. Not a defect in the merge
   (the single-filing path never uses it), but it is a sentinel in a data file.
