---
id: P9a-session-route
phase: 9 — two extraction routes, one parser
agent: programmer
depends_on: []
---

# Add a second extraction route: a session file that the shared parser reads

## Objective

Every extraction today is a paid API call. `extract_financials` makes two calls per
filing (Pass 1 and Pass 2), so three 10-Ks cost six calls, plus up to two retries per
filing (`ingestion/claude_extractor.py:879-937`).

**The user decided on 2026-10-02 to add a second route.** A Claude Code session reads the
PDF in the chat and writes the same two JSON answers that the API returns. It saves them
to a **session file**. The pipeline then reads that file instead of calling the API.

The two routes must meet at the parser. Today the plan (which years and which balance
sheet come from which filing) and the merge are inline in `extract_multi_year`
(`:1287-1360`). If the session route copies them, a later fix to one copy misses the
other. That is the shape of backlog item 7. So this unit first lifts the plan, the merge,
the prompts and the parsers into public functions that route A already calls. Then the
session route calls the same functions.

When this unit is done:

- the same two JSON strings give equal `FinancialStatements` and equal
  `NonRecurringItem` lists by either route;
- `cli.py --session-file FILE` runs a full valuation with no API credential set;
- the output names the route.

The web app is **not** in this unit. `P9b-session-web` adds it next, using the loader you
write here.

## What is already true — verify, do not redo

Fill in the commit from `git log --oneline -1` before you start. **This machine is
macOS. The interpreter is `.venv/bin/python`.** See `docs/8-build/environment.md`
section 1.

| Fact | Command | At `cde33cb` |
|---|---|---|
| test gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | **197 passed, 1 failed** |
| the one failure | same | `tests/unit/test_capm.py::test_beta_stops_when_the_market_series_has_no_variation`. SciPy 1.17.1 raises its own message. **Held by the user. Not this unit's** |
| lint | `.venv/bin/python -m ruff check .` | **5 errors**, all `BLE001` |
| types | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | **14 errors in 4 files** |
| home page | `TestClient(app.app, raise_server_exceptions=False).get('/')` | **200** |
| zero-default census | the grep at `docs/2-rules/rules.md:65` | **116** |
| the plan is inline | `sed -n 1278,1316p ingestion/claude_extractor.py` | the single-filing branch, then the routing loop |
| the merge is inline | `sed -n 1333,1360p ingestion/claude_extractor.py` | "prefer the primary filing", then NRI dedupe on `(year, amount, direction)` |
| filing discovery lives in `cli.py` | `grep -n "def _discover_filings\|def parse_pdf_args\|def fingerprint_filings\|class InputFingerprint" cli.py` | four definitions |
| nothing else imports them | `git grep -n "_discover_filings\|parse_pdf_args\|fingerprint_filings\|InputFingerprint" -- ':!cli.py'` | no hit outside docs and the journal |
| the result page reads four label fields | `grep -n "extraction\." templates/valuation_result.html` | `provider`, `model`, `transport_label`, `credential_source` |

If a row disagrees, **stop and report it** in your entry. Do not edit around it.

## What to do

### Part 1. One plan, one merge, one set of prompts and parsers — `ingestion/claude_extractor.py`

**Route A must not change a number.** Every step below is a move of existing code into a
named function that route A then calls. Rule 2: one function per job, fixed typed
signature, no `**kwargs`.

1. **Add a frozen dataclass `FilingPlan`** with four fields: `fiscal_year: int`,
   `pdf_path: str`, `target_years: tuple[int, ...] | None`, `include_bs: bool`. Use a
   tuple, not a list, so the frozen dataclass is hashable and cannot be mutated.

2. **Add `plan_filings(filings: list[tuple[int, str | Path]]) -> list[FilingPlan]`.** It
   returns exactly the routing `extract_multi_year` applies today:
   - one filing: `target_years=None`, `include_bs=True`. That is what the
     single-filing branch at `:1278-1285` passes to `extract_financials` through its
     defaults.
   - several filings, sorted ascending by fiscal year: the oldest gets `None` and no
     balance sheet, each middle one gets `(fiscal_year,)` and no balance sheet, and the
     newest gets `(fiscal_year,)` and the balance sheet.
   - an empty list raises the same `ValueError` as today.

3. **Add `merge_filing_extractions(...) -> tuple[FinancialStatements, list[NonRecurringItem]]`**
   holding the merge at `:1333-1360` unchanged: prefer the statement from the filing
   whose `fiscal_year` equals the statement year, and dedupe items on
   `(year, amount, direction)`. Its arguments are the per-filing results with their
   plans, plus `ticker` and `company_name`. Choose the exact signature; keep it typed.

4. **Make `extract_multi_year` call both.** The single-filing case must still return what
   `extract_financials` returns, **without** passing it through the merge. The merge
   re-sorts and replaces the parsed ticker, so a merged single filing could differ from
   today's output. Keep that branch as it is.

5. **Add four public wrappers so no other module imports a name that starts with `_`:**
   - `pass1_prompts(plan: FilingPlan) -> tuple[str, str]`: the system prompt and the
     user prompt that route A sends for that plan.
   - `pass2_prompts(plan: FilingPlan, financials: FinancialStatements) -> tuple[str, str]`:
     the same for Pass 2, with the income statement summary built from `financials`.
   - `parse_pass1(json_str: str, ticker: str, company_name: str) -> tuple[FinancialStatements, list[str]]`:
     calls `_parse_financials_response`.
   - `parse_pass2(json_str: str) -> list[NonRecurringItem]`: calls `_parse_nri_response`.

   **Route A's runners must build their prompts through the same code path**, so the
   prompt route A sends and the prompt route B prints cannot drift apart. Either make
   `_run_financials_pass` and `_run_nri_pass` call the wrappers, or make the wrappers
   call the same builders those runners call. Show in your entry which one you chose
   and why the two cannot diverge.

6. **Extend two `Literal` types.** Add `"claude-code-session"` to `Transport` and to
   `CredentialKind`. A session route is a transport, not a provider. The model is still
   Claude. This follows the reasoning at `:112-114` and in
   `docs/8-build/environment.md` section 3 ("Provider vs transport").

### Part 2. Move filing discovery out of `cli.py` — new `ingestion/filings.py`

7. **Move, do not copy**, these four from `cli.py` into `ingestion/filings.py`:
   `_discover_filings` (rename it `discover_filings`), `parse_pdf_args`,
   `InputFingerprint` and `fingerprint_filings`. `cli.py` imports them. **No behaviour
   change.** The session route needs the same discovery and the same file hashing as
   the CLI, and a second copy is item 7 again.

### Part 3. The session route — new `ingestion/session_extraction.py`

**This module holds no model client, no prompt text and no API key.** `docs/2-rules/llm-boundary.md`
says `claude_extractor.py` is the only file that may hold them. It gets prompts from the
Part 1 wrappers and parses through them.

8. **The file format.** JSON, UTF-8. One file per company run:

   ```json
   {
     "format": "session-extraction-v1",
     "ticker": "CMG",
     "company_name": "Chipotle Mexican Grill, Inc.",
     "extracted_by": {"model": null, "tool": "Claude Code", "date": null},
     "filings": [
       {
         "fiscal_year": 2023,
         "pdf_path": "/absolute/path/to/the.pdf",
         "pdf_sha256": "…",
         "size_bytes": 1234567,
         "target_years": null,
         "include_bs": false,
         "pages_read": {"pass1": [], "pass2": []},
         "pass1": null,
         "pass2": null
       }
     ]
   }
   ```

   - `pass1` holds the object `_FINANCIALS_SCHEMA` describes. `pass2` holds the object
     `_NRI_SCHEMA` describes. **These are exactly the JSON the API route parses.** Store
     them as JSON objects, not as strings.
   - `pages_read` holds the 1-based PDF page numbers the session read for each pass. It
     is a locator, which `docs/2-rules/llm-boundary.md` allows ("plus the locator that
     says where"). It is recorded and printed, never computed from.
   - `extracted_by.model` is the model ID the session declares. The tool cannot verify
     it. Print it as declared.

9. **Subcommands**, run as `.venv/bin/python -m ingestion.session_extraction <command>`:

   | Command | Does |
   |---|---|
   | `plan <pdf args> -t TICKER [-n NAME] -o FILE` | resolves the filings with `parse_pdf_args`, plans them with `plan_filings`, hashes them with `fingerprint_filings`, and writes a skeleton with `pass1`, `pass2` and the model set to `null`. **Refuses to overwrite an existing file** unless `--force` is given: a filled session file is work that cost a session's time. |
   | `locate FILE --filing N` | prints the 1-based page numbers in that filing's PDF where the statement titles appear (income or operations, balance sheet, cash flows) and where the non-recurring keywords appear (restructuring, impairment, litigation, settlement, gain or loss on sale, divestiture, severance, acquisition-related, write-down). Uses `pdfplumber`, which is already in `requirements.txt`. **It prints page numbers and match counts, never a figure** (rule 1). |
   | `text FILE --filing N --pages A-B` | prints the text layer of those 1-based pages of that filing's PDF, each under a `=== page N ===` marker, with `pdfplumber`'s `extract_text()`. **Added by the orchestrator on 2026-10-02, after dispatch.** The Read tool cannot render a PDF page on this Mac: it needs `pdftoppm`, and Homebrew 4.4.6 cannot install it on macOS 27.0. The text layer also costs a session fewer tokens than page images. It prints the filing's own text. It computes nothing. Refuse a range wider than 20 pages, so a session cannot load a whole 10-K by accident. |
   | `prompt FILE --filing N --pass 1\|2` | prints the system and user prompt from `pass1_prompts` or `pass2_prompts` for that filing's plan. Pass 2 needs that filing's `pass1` to parse, because the summary is built from it. |
   | `check FILE` | runs the loader and prints the arithmetic table and every problem. Exit 0 when clean, 1 when only arithmetic validation errors remain, 2 when the loader stops. |

10. **The loader.** `load_session_extraction(path: str | Path) -> SessionExtraction`,
    where `SessionExtraction` is a frozen dataclass holding the merged
    `FinancialStatements`, the `list[NonRecurringItem]`, a `ProviderResolution` that
    labels the route, the validation errors as `list[str]`, and the session file's path.

    It **stops** with a `ValueError` that names the file, the filing index and its PDF
    name, and, where one applies, the year and the key, when:

    - `format` is not `session-extraction-v1`;
    - `extracted_by.model` is missing or empty;
    - a filing's `pass1` or `pass2` is `null`;
    - a PDF is missing on disk, or its sha256 differs from `pdf_sha256`. Hash with
      `fingerprint_filings`. This is what ties the figures to the filing (rule 5), as
      `P6-honest-output` did for the CLI cache (backlog item 33);
    - **any key that `_FINANCIALS_SCHEMA` names is absent** from a `historical_years`
      entry, or from `latest_balance_sheet` when `include_bs` is true. An explicit `0`
      is accepted. An absent key is not. **This is stricter than route A on purpose.**
      Route A's parser reads `.get(field, 0)` (backlog item 1). Do not change route A's
      parser.
    - a filing's planned `target_years` is set and the years in `pass1` differ from it;
    - `include_bs` is true and `latest_balance_sheet` is empty or has no `year`, or it is
      false and `latest_balance_sheet` is not `{}`.

    Then it parses each filing with `parse_pass1` and `parse_pass2`, and combines them
    exactly as route A does: for one filing, the parsed result as it is; for several,
    `merge_filing_extractions`. **Arithmetic validation errors are returned and printed,
    not raised.** Route A keeps the figures with a warning after its last retry
    (`:912-916`), and both routes must reach the same result from the same JSON.

11. **The route label.** Build the `ProviderResolution` with `provider="claude"`, the
    declared model, `transport="claude-code-session"`, `credential="claude-code-session"`,
    a `transport_label` that says the figures were read in a Claude Code session and
    names the session file, and a `credential_source` that says no API call was made.
    `describe_resolution` must then print it unchanged. Rule 6.

### Part 4. The CLI — `cli.py`

12. **Add `--session-file FILE`** to the extraction argument group. With it:
    - no PDF positional arguments are allowed. Give a clear `argparse` error when both
      or neither are given. The positional becomes `nargs="*"`;
    - the ticker comes from the file. `-t` is optional, and a `-t` that differs from the
      file's ticker is an error;
    - no pickle cache is read or written. The session file is the stored extraction;
    - stage 1 prints `describe_resolution` of the session label, then each PDF with its
      sha256 prefix and the pages read;
    - every later place that names the provider, such as
      `print_non_recurring_items(applied, args.provider)` at `:969`, names the session
      route instead. A heading that says `CLAUDE` with no transport would hide which
      route produced the figures (rule 6).

    Without `--session-file`, the CLI behaves exactly as today.

### Part 5. Repository files

13. **`.gitignore`:** add `extractions/`, with a comment. Session files hold a company's
    figures. They are data, like `10K_filings/` and `cache/` (`docs/INDEX.md`, "docs/
    holds documents. It never holds data").

14. **Docs.** Update the three files that own this subject:
    - `docs/3-architecture/extraction.md`: a section "Two routes, one parser" with the
      file format, the four subcommands and the stop list.
    - `docs/2-rules/llm-boundary.md`: the diagram under "The line, in code" now has two
      sources of model text that meet at `parse_pass1` and `parse_pass2`.
    - `docs/3-architecture/entry-points.md`: the CLI flag.

## Files in scope

- `ingestion/claude_extractor.py`
- `ingestion/filings.py` (new)
- `ingestion/session_extraction.py` (new)
- `cli.py`
- `.gitignore`
- `docs/3-architecture/extraction.md`
- `docs/2-rules/llm-boundary.md`
- `docs/3-architecture/entry-points.md`
- your journal entry under `.agent/journal/`

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Out of scope

- `api/`, `templates/`: `P9b-session-web`, next.
- `tests/`: the tester writes them after review. Prove each criterion with scratch
  scripts under `/tmp/`, and paste the output in your entry.
- `.claude/`: the orchestrator writes the Claude Code skill that drives a session through
  `plan`, `locate`, `text`, `prompt` and `check`.
- `analysis/capm.py` and its SciPy failure: held by the user.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | one plan and one merge | 1 definition each, called by `extract_multi_year` and by the loader | `grep -n "def plan_filings\|def merge_filing_extractions\|plan_filings(\|merge_filing_extractions(" ingestion/*.py` |
| 2 | route A unchanged | the gate as before: 197 passed, 1 failed (the CAPM test) | the test gate |
| 3 | same JSON, same result | equal `FinancialStatements` and equal item lists, for a one-filing and a three-filing plan | a scratch script: route A through `extract_multi_year` with `_call_llm` replaced by a stub that returns the stored JSON, and route B through a session file holding the same JSON. Paste the script and its output |
| 4 | a changed PDF stops | `ValueError` naming the path | scratch copy of a PDF, one byte appended after `plan` |
| 5 | a missing key stops | `ValueError` naming the filing, the year and the key | delete `sbc` from one year in a scratch file |
| 6 | the CLI runs from a session file with no credential | a DCF result printed, and the stage 1 line names `Claude Code session` | `env -u ANTHROPIC_API_KEY -u GEMINI_API_KEY -u ANTHROPIC_FOUNDRY_BASE_URL -u ANTHROPIC_FOUNDRY_RESOURCE .venv/bin/python cli.py --session-file /tmp/….json`. The figures in a scratch file are invented, so the price means nothing. Say so in the entry |
| 7b | `text` prints a statement page | the line `Net sales $ 706,413 $ 674,538 $ 642,637` | `.venv/bin/python -m ingestion.session_extraction text <plan of the 2026 Walmart 10-K> --filing 0 --pages 21-21` |
| 7 | `locate` finds the statements | the three statement pages of one real 10-K | `.venv/bin/python -m ingestion.session_extraction locate …` on a file under `10K_filings/`. Name one page; the reviewer opens it |
| 8 | the boundary holds | no hit | `grep -n "import anthropic\|genai\|_SYSTEM_PROMPT\|API_KEY" ingestion/session_extraction.py ingestion/filings.py` |
| 9 | discovery moved, not copied | no definition left in `cli.py` | `grep -n "def _discover_filings\|def parse_pdf_args\|def fingerprint_filings\|class InputFingerprint" cli.py` |
| 10 | no new lint or type errors | ruff 5, mypy 14 in 4 files, or fewer | the two gates |
| 11 | the web app still serves | 200 | the route gate |

**Every criterion is a measurement, never an opinion.**

## Citations

- `docs/2-rules/rules.md`: rule 1 (the LLM extracts), rule 2 (one named function), rule 3
  (stop, never guess), rule 5 (the filing is the only source), rule 6 (label the
  assumption).
- `docs/2-rules/llm-boundary.md`: where the line sits, and that a locator is allowed.
- `docs/3-architecture/extraction.md`: the two passes and the multi-PDF routing.
- `docs/8-build/environment.md` section 3: provider against transport.
- `docs/8-build/phases.md`: Phase 9 and its criteria.
- `.agent/journal/` entries for `P2b-provider` and `P6-honest-output`: how the
  `ProviderResolution` label and the content-keyed cache were built.

## Known open items

- **The filing year comes from the filename, not from the filing.**
  `10K_filings/LHX/L3Harris Technologies Inc._10-K_2026-01-02_English.pdf` is the 10-K
  for the fiscal year ended 2026-01-02, which L3Harris calls fiscal 2025. The year
  `_discover_filings` infers is 2026. That gap lies in the code you move. **Do not fix it
  here.** Moving the code must not change its behaviour. The orchestrator records it in
  the backlog.
- Route A's retry loop sends validation errors back to the model. The session route has
  no loop. `check` prints the same errors, and the session corrects the file and runs
  `check` again. The skill the orchestrator writes says so.

## Backlog items this unit is NOT fixing

- **Item 1.** The `.get(field, 0)` reads in `_parse_financials_response`. Route B's key
  check is new and lives in the loader. Route A's parser is unchanged.
- **Item 7.** Steps 2 to 8 duplicated between `cli.py` and `api/`.
- **Item 8.** `except Exception` at `claude_extractor.py:990` and in `cli.py`.
- **Item 10.** The D&A subtraction at `claude_extractor.py:622`. Both routes now pass
  through it, which is the point. Fixing it is still a separate unit.
- **Item 11.** The five mypy errors in `claude_extractor.py`.
- **Item 36.** The variance between two extractions of one filing. A session extraction
  is a third reading. Do not compare readings in this unit.
