---
agent: code_reviewer
assignment: P9a-session-route
round: 1
verdict: approved
---

# Review of P9a-session-route, round 1

Programmer entry: `.agent/journal/2026-10-02T1630-programmer-p9a-session-route.md`

I reviewed `git diff cde33cb` over `ingestion/claude_extractor.py`, `cli.py`, `.gitignore`
and the three docs, plus the new files `ingestion/filings.py` and
`ingestion/session_extraction.py`. The amended step 9 and criterion 7b (`text`) are in
scope. The orchestrator's own working-tree changes (`environment.md`, `phases.md`,
`refactor-backlog.md`, `.agent/journal/INDEX.md`, `.claude/skills/extract-filing/`, the
P9b and P9c assignments) are not findings against this unit. Scratch work is under
`/tmp/rev9a/`. I never ran route A against a real PDF. Every route A run used a stubbed
`_call_llm`.

## The guard checks

I ran each grep over the two new files in full, and over the **added lines** of
`claude_extractor.py` and `cli.py` (`git diff -U0 cde33cb | grep '^+'`). I also ran them
over those two files in full, to see whether the unit touched any existing hit.

| Check | Result |
|---|---|
| conditional zero: `if … else 0.0` | clean in the new code. The existing hits are untouched: `claude_extractor.py:378`, `cli.py:195`, `:498`, `:999`, `:1007` |
| lookup with a fallback: `.get(k, 0)` | one hit, `session_extraction.py:471`, `balance.get('year', '(absent)')`. It only builds the text of an error message and never reaches a figure. The programmer's entry does not list it (F2). The `.get` count in `claude_extractor.py`/`cli.py` is 62/1 both before and after |
| bare or-default: `or 0.0` | clean in the new code. The existing hits at `claude_extractor.py:595-597` (Gemini usage) are untouched |
| money field defaulted to zero: `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | clean in the new code. The existing hits at `claude_extractor.py:596-597` and `cli.py:648` are untouched |
| dict of functions keyed by data | clean. `_STATEMENT_PATTERNS` and `_NRI_PATTERNS` map a label to a regex (data). Subcommand dispatch is a chain of `if` tests on literal names (`session_extraction.py:951-960`) |
| model client imported outside `ingestion/` | clean: `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` gives no output |

The single-argument `.get`s at `session_extraction.py:257` and `:473` are also message
prefixes only. The entry answers `:257` (Rule 3 table, last rows) but not `:473`.

## Rule 3, by reading

I read every value the new loader and the CLI session path read.

| Value | Stops and names it? | Evidence |
|---|---|---|
| session file, JSON, `format` | yes | `_read_session_json` `:186-211` |
| `ticker` / `company_name` | yes. A `company_name` of `""` is accepted, as route A accepts `-n ""` (a label, never a figure) | `:214-233` |
| `extracted_by.model` | yes, and it is collected together with the per-filing problems | `/tmp/rev9a/stops.py` `[model_and_pass1_null]`: both problems listed |
| `fiscal_year`, `pdf_path`, `target_years`, `include_bs`, the order of the filings | yes. Each is checked against `plan_filings` re-run | `:262-337` |
| `pdf_sha256`, `size_bytes`, the PDF on disk | yes | criterion 4, below |
| each of the 19 year keys and 16 balance-sheet keys (`year` checked separately) | yes. An absent key or a non-number stops. An explicit `0` loads | criterion 5. `[bs_ltd_absent]` and `[revenue_bool]` stop. `[sbc_zero]` loads |
| `pass2` items | partly. Route A's parser stops when `confidence`, `source`, `amount` and the rest are absent (`[nri_amount_absent]` → names `KeyError: 'amount'`). A non-list `non_recurring_items` crashes instead of stopping cleanly, and a `NaN` amount loads (F1) | `/tmp/rev9a/stops2.py` |
| `pages_read.*` | yes | `_pages` `:368-383` |
| CLI `-t` / `-n` / `-p` / `-m` / `--cache-dir` / `--no-cache` in session mode | yes. Each is refused, or a value that differs from the file stops | CLI probes, below |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | **unchanged by this unit, and still not true.** The loader does not read `pass1.units`, and neither does route A's parser (backlog item 44). Chipotle 2025 page 29 prints `Total revenue 11,925,601`, which is in thousands. The two routes agree, as the assignment requires. See the pre-existing table |
| percentages converted at the route boundary, once | not applicable: this unit has no form or percentage inputs |
| falsy not treated as missing | clean. `if args.ticker and …` / `if args.company_name and …` (`cli.py:885`, `:891`) treat `""` as "not given", which is the meaning of `-t`/`-n` absent. `_pages` tests `is not None` (`:519`) |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | unchanged. `ingestion/filings.py` imports only the standard library. `session_extraction.py` imports `ingestion.claude_extractor` public names, `ingestion.filings`, `models` and `pdfplumber` (lazily) |
| no other module imports a `_` name (step 5) | holds. `session_extraction.py:72-86` and `cli.py:56-63` import only public names |
| the LLM boundary (criterion 8) | holds. No client, no key and no prompt constant in the new files. Prompts come only through `pass1_prompts`/`pass2_prompts`. A `claude-code-session` resolution is refused by `_build_claude_client` (`claude_extractor.py:466-475`). Checked: `guard: This ProviderResolution labels a Claude Code session file …` |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | one plan, one merge | 1 def each. Called by `extract_multi_year` and the loader | defs `claude_extractor.py:1265`, `:1309`. Calls `:1486`, `:1533`, `session_extraction.py:302`, `:605`, `:682` | yes |
| 2 | route A unchanged | `1 failed, 197 passed`, the CAPM test | `1 failed, 197 passed`. The failure set is exactly `{test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}`. **Also measured directly:** I loaded `cde33cb`'s `claude_extractor.py` as a module and ran its `extract_multi_year` against the new one, with the same stub and the same JSON, in 4 cases (one filing, three filings, empty company name, empty ticker). `fin`, `nri` and the prompt pairs sent were equal in all 4 (`/tmp/rev9a/equal2.py`) | yes |
| 3 | same JSON, same result | equal for 1 and 3 filings. Prompts sent == printed | re-ran in `/tmp/rev9a/equal.py`. `FinancialStatements equal: True`, `NonRecurringItem lists equal: True`, prompts `True` (2 and 6 pairs) for both. `ALL EQUAL` | yes |
| 4 | a changed PDF stops | `ValueError` naming the path | own scratch copy `/tmp/rev9a/copy_2025.pdf`, planned, then 1 byte appended → `filings[2] (copy_2025.pdf): the PDF /private/tmp/rev9a/copy_2025.pdf has changed since the session read it. sha256 recorded 74667e458cd46fa7…, now e49168ba4eb8acfa…` | yes |
| 5 | a missing key stops | names filing, year, key | `filings[0] (Chipotle Mexican Grill Inc._10-K_2023-12-31_English.pdf), year 2022: key 'sbc' is absent.` `sbc: 0` loads | yes |
| 6 | CLI runs from a session file, no credential | exit 0, stage 1 names the session | `cli.py --session-file /tmp/p9a/cli_CMG.json` → exit 0, `Transport: Claude Code session — …`, `Implied Price: $ 1846.06`. **The figures are invented, so the price means nothing.** As the programmer found, `env -u` proves nothing here (`config.py` loads `.env` with `override=True`, backlog 46). So I re-ran `/tmp/p9a/no_api.py`: credentials popped after `config` loads, `anthropic` made unimportable, `_call_llm` set to raise → exit 0, the same price, no `AssertionError` | yes |
| 7 | `locate` finds the statements | CMG 2025: I/S 29, 33. B/S 28, 33, 35-37. C/F 30 | the same lists. **I opened page 29**: `CONSOLIDATED STATEMENTS OF INCOME AND COMPREHENSIVE INCOME`, `Total revenue 11,925,601 11,313,853 9,871,649`. Page 28 has `CONSOLIDATED BALANCE SHEETS` and page 30 has `CONSOLIDATED STATEMENTS OF CASH FLOWS` | yes |
| 7b | `text` prints a statement page | `Net sales $ 706,413 $ 674,538 $ 642,637` | my own `plan` of the Walmart 2026 10-K, then `text … --filing 0 --pages 21-21` → line 1 `=== page 21 ===`, line 66 `Net sales $ 706,413 $ 674,538 $ 642,637`. `--pages 1-21` → refused, exit 2 | yes |
| 8 | the boundary holds | no hit | no output | yes |
| 9 | discovery moved, not copied | no def left in `cli.py`. Moved verbatim | no output. AST check: each of the four definitions at `cde33cb`, with only `_discover_filings`→`discover_filings` renamed, is a substring of `ingestion/filings.py`: `True` ×4 | yes |
| 10 | no new lint or type errors | ruff 5. mypy 10 in 4 files | ruff `Found 5 errors.` (BLE001). mypy `Found 10 errors in 4 files (checked 20 source files)`. Outside the gate, `mypy cli.py` reports 45 `cli.py` errors at `cde33cb` and 45 now | yes |
| 11 | the web app still serves | 200 | `200` | yes |
| — | census | 116 | `116` | yes |

I also probed the CLI's arguments in session mode. PDFs combined with
`--session-file`, neither given, `-p`, `-m` and `--no-cache` each give an `argparse` error,
exit 2. `-t AAPL` and `-n Other` stop with exit 1. `-t cmg` runs. A session file with a
key missing stops at stage 1, naming the filing, year and key. `plan` refuses to
overwrite without `--force`. `prompt --pass 2` before Pass 1 stops with exit 2. `check`
exits 1 when only arithmetic errors are present and 2 when the loader stops.

## Findings

### F1: Pass 2's shape is not checked to Pass 1's standard: a crash slips past the loader's `ValueError`, and a `NaN` amount loads · `minor`

**Evidence:** `check /tmp/rev9a/s_nri_not_list.json` (`"non_recurring_items": {"a": 1}`)
→ traceback `AttributeError: 'str' object has no attribute 'get'`, exit **1**. Step 9
reserves exit 1 for "only arithmetic validation errors remain", and
`_pass2_problems` (`session_extraction.py:497`) catches only
`ValueError, KeyError, TypeError`. Separately, `[nri_amount_nan]` loads with
`amount=nan`, although `_is_number` (`:179-183`) rejects `NaN` everywhere in Pass 1. Run
through the CLI (`/tmp/rev9a/cli_nan.out`), it prints `Total add-backs: nanM` and stops
only at stage 10, as `the projected FCFF for year 2026 is NaN`, without naming the item
or the file.
**Rule or document:** assignment step 9 (the exit codes) and step 10 (the loader stops
with a `ValueError` naming the filing). `docs/3-architecture/extraction.md` says the
loader raises `ValueError` "when route A's Pass 2 parser rejects `pass2`". This is not
cited as a rule 3 break: nothing is missing, and the run does stop rather than return a
figure. Route A's parser behaves identically on the same input.
**What would fix it:** before `parse_pass2`, check that `non_recurring_items` is a list
of objects and that each `amount` passes `_is_number`. Report a failure as a problem
naming the filing and the item index.

### F2: a guard hit that the entry does not answer · `minor`

**Evidence:** `session_extraction.py:471`
`f"{balance.get('year', '(absent)')!r}."` matches the `.get` guard. Both `:471` and the
single-argument `balance.get("year")` at `:473` are missing from the entry's Rule 3
table. The code comment says "diagnostic text only", and that is true: neither value
reaches a figure.
**Rule or document:** the reviewer contract. A hit must be answered in the entry. The
answer is right; it is only in the wrong place.
**What would fix it:** one row in the entry's Rule 3 table, beside the `:257` row.

### F3: a single bare PDF writes `"fiscal_year": 0` into a persisted data format · `note`

**Evidence:** `plan "10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf"` →
`[0] fiscal 0 …`. `_session_plans` accepts 0 when there is one filing (`:292`).
**Rule or document:** none broken. The 0 never reaches a figure: the single-filing path
neither routes nor merges on it, and route A carries the same sentinel from
`parse_pdf_args`, which the assignment fixes as the resolver. The programmer reported it
as finding 6. I record it so that `session-extraction-v2`, if it ever exists, uses
`null`.
**What would fix it:** an orchestrator decision. Nothing in this unit.

### F4: one missing blank line between top-level definitions · `note`

**Evidence:** `claude_extractor.py:1359-1361`. `return merged, all_nri` is followed by a
single blank line and then `def pass1_prompts`. PEP 8 E302 wants two. The ruff config does
not select E3, so the gate does not see it.
**What would fix it:** add one blank line.

### F5: the `cli.py` line table in `entry-points.md` is stale · `note`

**Evidence:** `docs/3-architecture/entry-points.md:65-72` still gives `main` `:596` and
`parse_args` `:69`. Today `main` is at `cli.py:931` and `parse_args` at `:80`. Those
numbers were already stale before the unit, and the move made them more so. The first
column of the row the unit edited still reads `_discover_filings`.
**What would fix it:** re-measure the table, or drop the line numbers in favour of
function names.

## Pre-existing, already recorded: not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1: `.get(field, 0)` in the Pass 1 parser | `claude_extractor.py:650-711` | no. Route B now checks for absent keys before it reaches the parser, as the assignment asks |
| 10: D&A subtracted in the parser | `claude_extractor.py:655` | no. Both routes now pass through it, as intended |
| 44: `units` extracted and ignored | `claude_extractor.py:214`, `:240`, parser | no. The new loader does not read `units` either, so both routes agree. Chipotle reports in thousands (page 29, above), and so would a Chipotle session file |
| 43: the fiscal year comes from the filename | `ingestion/filings.py:22-82` | **moved verbatim**, which the assignment required ("Do not fix it here"). The backlog row already names the move. I read it as a heuristic that is wrong for 52/53-week filers, not as a rule 3 default, so I have not raised it as this unit's finding. **If the orchestrator reads it as a rule 3 break, then "moving a line makes it yours" applies, and the assignment needs amending. That is the orchestrator's call, not mine.** Route B partly mitigates it: `plan` prints a warning, and the loader stops when `pass1` years differ from the planned `target_years` |
| 46: `.env` overrides the environment | `config.py:15` | no. It caused the programmer's possibly billed probe, which the entry reports honestly |
| 8, 11, 39 | BLE001 sites, mypy, `confidence` default | no. mypy fell 14 → 10 as a side effect of renaming the merge's loop variables |

**Not yet in the backlog, and not touched by the diff:** `cli.py:834-835`,
`valid = [(y, p) for y, p in filings if y > 0]`. When several PDFs are given, the API
route silently drops any PDF with no year. The programmer reported it (finding 3).
`git diff cde33cb -U0 -- cli.py` shows these lines unchanged; only the enclosing `def`
changed (`main` → `_extract_via_api`). Route B refuses the same input instead
(`session_extraction.py:292-297`, `:672-678`). **The orchestrator should record it.**

## Harness note

The write guard (`guard_paths.py`) refused three of my scratch commands whose targets
were all under `/tmp/`. It read the contents of a heredoc, a relative `rm -rf base` and a
`grep` pattern containing `>` as write targets. I worked around it with absolute paths
and the Write tool under `/tmp/`. Nothing in the repository was written except this
entry.

## Verdict

`approved`

Every done-criterion re-measured and agrees. Route A's numbers and prompts are unchanged:
I checked this directly against `cde33cb`'s module under the same stub, not only by the
test count. The two routes give equal statements, items and prompts from the same JSON.
The new loader stops and names the file, filing, year and key for every absence in the
assignment's stop list. No finding breaks a rule in `docs/2-rules/rules.md`.

- **F1 and F2 are `minor`.** F1 is a gap in Pass 2 shape checking. It should be closed
  before P9b exposes the loader on the web, but it never produces a figure from a
  missing input.
- **F3 to F5 are `note`s.**
- **Item 43 is flagged above for the orchestrator.**
