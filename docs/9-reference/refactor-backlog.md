# Refactor backlog

Every known defect, with its evidence and what it costs. **Re-measured at `7354698`,
2026-09-22.** Seventeen are closed: 3, 4, 9, 13, 14, 19, 20, 21, 22, 23b, 24, 27, 30, 33, 34, 35, and 12 mostly. **Item 36 is half closed** — see it.

**Items 14 to 38 did not exist when this build started, and every one of 19 to 38 was
found by running the code rather than by reading it.** Items 33 to 38 came from the
first runs against a real filing. That is the single strongest
argument for the test suite that found them — and for the gates it added, since three of
them were found by a reviewer re-running a measurement it had been handed.

**Read this before reporting a defect as new**, and before writing an assignment that
touches one of these files. An item listed here, in a line a unit did not touch, is
**not** a finding against that unit — see
[.claude/agents/code-reviewer.md](../../.claude/agents/code-reviewer.md).

---

## How to read this

Two axes. **The second one outranks the first.**

| | |
|---|---|
| **Silent** | produces a wrong number on a clean run. Nothing downstream detects it |
| **Stopping** | raises, or refuses to run. Visible the moment it happens |

A silent defect that moves the headline share price outranks everything else, however
small the diff that causes it. A stopping defect is close to harmless: the run refuses
rather than lying.

---

## Ranked by cost

| # | Item | Silent? | Area | State at `7354698` |
|---|---|---|---|---|
| 1 | **116** silent zero-default sites | **silent** | `models/` 60, `ingestion/` 49, `analysis/` 5, `api/` 2 | open |
| 2 | Missing balance sheet gives zero net debt | **silent** | `analysis/dcf.py` | **closed by `P10a-nci-bridge`**: `run_dcf` stops and names the missing balance sheet; census 116 → 114 |
| 3 | Unknown NRI line item guesses a field | **silent** | `analysis/normalizer.py` | **closed at `38b903c`** |
| 4 | No test suite; `pytest` cannot collect | stopping | `tests/` | **closed** — 146 tests |
| 5 | Module-global extraction cache, popped on use | mixed | `api/routes_valuation.py` | open |
| 6 | Falsy treated as missing, five times | **silent** | `api/routes_valuation.py` | open |
| 7 | `cli.py` and `api/` duplicate the pipeline | **silent** | both | **closed by `P3a-one-pipeline` (`dc81088`), locked at `ac736e7`**: `pipeline.py` (`adjust_financials`, `value_company`) holds the eight valuation calls once; both entry points call it; the CLI and web outputs for Walmart are unchanged ($28.02), and a test shows one price for both |
| 8 | Blanket `except Exception` at five sites | **silent** | `api/`, `cli.py`, `ingestion/`, `tests/` | open, **now the only lint errors** |
| 9 | Unlabelled cost-of-debt assumption | **silent** | `analysis/wacc.py` | **closed at `6cf34d3`** |
| 10 | D&A subtraction buried in the parser | **silent** | `ingestion/claude_extractor.py` | open |
| 11 | **14** type errors, down from 33 | stopping | 4 files | open; every removal so far was a real defect |
| 12 | Dead code and stale repository hygiene | — | several | **mostly closed** |
| 13 | Provider changed with the number of PDFs uploaded | stopping, here | `ingestion/`, `api/` | **closed at `0e4649f`** |
| 14 | Empty `projected_fcffs` raises a bare `IndexError` | stopping | `analysis/dcf.py` | **closed at `ff632df`** |
| 15 | `latest_year` returns `0` for an empty extraction | **silent** | `models/financial_statements.py` | **closed by `P13b-models-silent` (`aa6f80d`)**: `latest_year` raises when there are no statements |
| 16 | Nine scripts point at a path that does not exist | stopping | `tests/` | new |
| 17 | `analysis/` imports from `ingestion/` | — | `analysis/capm.py` | new |
| 18 | The lint gate's rule set is unpinned | — | `ruff.toml` | open |
| 19 | One sign rule applied to two kinds of line | **silent** | `analysis/normalizer.py` | **closed at `38b903c`** |
| 20 | A NaN beta is returned, not raised | **silent** | `analysis/capm.py` | **closed at `ff632df`** |
| 21 | An unrecognised `direction` silently reverses | **silent** | `analysis/normalizer.py` | **closed at `38b903c`** |
| 22 | Zero debt balance gives a 0% cost of debt | **silent** | `analysis/wacc.py` | **closed at `6cf34d3`**; its weights half is item 38 |
| 23 | `analysis/fcff.py` holds no `raise` for empty statements, **and `calculate_fcff_projected` has seven unguarded float parameters** | **silent** | `analysis/fcff.py` | open; **the clamp twin (23b) is closed at `2ca620a`** |
| 24 | A red test that goes green stays outside the gate | — | `tests/` | **closed at `81816be`** |
| 25 | An adjustment whose year matches no statement is discarded | **silent** | `analysis/normalizer.py` | **closed by `P13a-analysis-silent` (`47b8b09`)**: `normalize_financials` raises, naming each unmatched item and the statement years |
| 26 | The `files` branch tests for a character every path contains | stopping, **latent** | `api/routes_valuation.py` | **new.** Live only on the legacy no-year branch |
| 27 | `GET /` and `GET /assumptions` return **500** | stopping | `api/` | **closed at `622262b`** |
| 28 | `api/routes_upload.py:27` — `str \| None` used as a path segment | stopping | `api/routes_upload.py` | **new.** The last type error in that file |
| 29 | `POST /valuation` with no `files` runs an extraction on an empty path | **silent** | `api/routes_valuation.py` | **closed at `be1c077` (`P9b`)**: `POST /valuation` with no filing stops: "No filing named: session_file, files and file_path are all empty". Re-run by the orchestrator at `6830188`. It renders at HTTP 200, through item 8's blanket `except` |
| 30 | A NaN in one `ProjectedFCFF` reaches the share price | **silent** | `analysis/dcf.py` | **closed at `2ca620a`** |
| 31 | `discount_cash_flows`' `wacc` is unguarded on a direct call | **silent** | `analysis/dcf.py` | **new, latent.** The `run_dcf` chain stops two lines later |
| 32 | `models/valuation.py:138` renders a share price of `0.0` on zero diluted shares | **silent** | `models/valuation.py` | **closed by `P13b-models-silent` (`aa6f80d`)**: `run_dcf` and `implied_share_price` stop on a share count that is not a finite number above 0 |
| 33 | The CLI cache is keyed on the **ticker alone**, so the PDFs you pass are silently ignored | **silent** | `cli.py` | **closed at `6cf34d3`** |
| 34 | The risk-free rate is a hardcoded `0.04` presented as measured | **silent** | `config.py`, `analysis/capm.py`, `api/` | **closed at `6cf34d3`** |
| 35 | A beta from a regression explaining 10% of variance is reported without qualification | **silent** | `analysis/capm.py` | **closed at `6cf34d3`** |
| 36 | **The same PDF extracted twice gave share prices 16% apart** | **silent** | `ingestion/`, `analysis/` | **half closed at `7354698`.** `low` items are now withheld; the variance itself is unmeasured |
| 39 | `models/financial_statements.py:28` defaults `confidence` to `"high"` | **silent** | `models/` | **closed by `P13b-models-silent` (`aa6f80d`)**: `confidence` has no default |
| 40 | Five dev scripts now produce a price neither entry point would | — | `tests/` | **new, and created by `7354698`** |
| 37 | `analysis/wacc.py`'s new stop states an inference as a fact | — | `analysis/wacc.py` | **new.** Message only; 23 of 23 wacc tests stay green with the rewrite |
| 38 | `analysis/wacc.py` fabricates a 100% equity weighting when market cap and debt are both zero | **silent** | `analysis/wacc.py` | **closed by `P13a-analysis-silent` (`47b8b09`)**: a sum of 0, and a market cap of 0 or below, stop. Its second face is item 38b, open |
| 43 | The fiscal year comes from the filename's date, not from the filing | **silent** | `ingestion/filings.py`, `api/routes_upload.py` | **closed by `P10c-fiscal-year`**: the filename year is verified against the cover date and the column label, and a mismatch stops |
| 44 | The `units` field is extracted and then ignored | **silent**, latent | `ingestion/claude_extractor.py`, `api/routes_valuation.py` | **closed by `P14a-units` (`bf428d3`), locked at `69436d9`**: Pass 1 returns two printed unit statements, `units` and `share_units`, each page-checked; Python reads the scale word and converts each filing to millions once, on both routes. Its follow-ups are items 77 to 80 |
| 45 | `calculate_beta` checks for a constant market series only after SciPy has already raised | stopping | `analysis/capm.py` | **new at `cde33cb`.** SciPy 1.17.1 raises first, so the stop does not name `market_returns`. **Held by the user, 2026-10-02** |
| 46 | `.env` overrides the environment, so unsetting a key does not stop a paid call | **silent** | `config.py` | **closed by `P13c-env-override`, round 3**: `.env` fills only absent names, so a shell value wins and an empty one turns the key off; `config.credential_origin` labels a key `(.env file)` or `(shell or parent process, not .env)` by comparing values. Open note, the round 3 review's F5: a value set inside the process by a test or notebook also reads the second label; no shipped code does that |
| 47 | The income statement shown on both pages has no interest income row, so EBT does not add up from the rows shown | — | `cli.py`, `templates/_statements.html` | **new at `cde33cb`.** Display only: the figure is in EBT, but a reader cannot see it |
| 48 | The equity bridge does not subtract noncontrolling interest | **silent** | `analysis/dcf.py`, `models/`, the Pass 1 schema | **closed by `P10a-nci-bridge`**: two printed keys, summed in `total_noncontrolling_interest`. Walmart $28.84 → $28.02 |
| 49 | Given several PDFs, the API route drops any PDF with no fiscal year and says nothing | **silent** | `cli.py`, `api/routes_valuation.py` | **new at `P9a`.** Route B stops on the same input, so the two routes now differ on it. **Closed by `P3b-pipeline-stops`, locked by `P3b-pipeline-stops-tests`:** `ingestion/filings.require_fiscal_year_per_filing` holds the rule once, `parse_pdf_args` and `_run_extraction` both call it, and both `valid = [(y, p) for y, p in filings if y > 0]` filters are deleted. With more than one filing, a filing with no year stops the run and the message names **every** offender, before any PDF is opened. One bare path is still allowed. The stop message gives each entry point the remedy that works there: `YEAR:PATH` on the command line, rename and upload again on the web page. The mutation that makes the function return without raising turns **12** named tests red |
| 50 | Route A returns `[]` when Pass 2 cannot be parsed twice, so "nothing was read" looks like "none found" | **silent** | `ingestion/claude_extractor.py` | **closed by `P13g-pass2-unread` (`bce6fae`)**: the retry raises, naming the filing and both parse errors. Its follow-ups are items 73 and 74 |
| 51 | The arithmetic check's `WARN` branch can never run | — | `ingestion/claude_extractor.py` | **new, found by `P9c`.** Dead code |
| 52 | On a cache hit, `POST /valuation` ignores `files` sent together with `session_file`; a cache miss stops on the same form | — | `api/routes_valuation.py` | **new, found by the `P9b` review.** Reachable only by a hand-built request; moves no figure or label |
| 53 | `ingestion/session_extraction.py` imports `_NRI_SCHEMA` by its private name | — | `ingestion/` | **new, the `P9d` review's F1, minor.** Export `PASS2_ITEM_FIELDS` from `claude_extractor.py` as `P9a` did for Pass 1, and remove the comment at `session_extraction.py:91-94` |
| 54 | `GET /assumptions` with no filing named shows an empty form and no message | — | `api/routes_valuation.py` | **new, found by the `P9b` tester.** No extraction runs and no figure is shown; the page just does not say why it is empty |
| 55 | After `P10b`, only a NaN reaches `calculate_beta`'s NaN check, but its message still blames a market series with no variation | — | `analysis/capm.py` | **new, the `P10b` review's F1, minor.** A NaN in `stock_returns` is reported as a market with no variation; message only |
| 56 | Pass 1 asked the model to compute: sums, a subtraction, and a balance-sheet plug | **silent** | `ingestion/claude_extractor.py` | **closed by `P11a-printed-lines`**: every money field is a list of printed rows, Python sums; the plug is gone and the balance check compares printed totals |
| 57 | The upload page invites 10-Q PDFs, but a 10-Q with a year in its name always stops at the year check, with no remedy | — | `templates/upload.html`, `ingestion/filings.py` | **new, the `P10c` review's F7.** A 10-Q has no "fiscal year ended" cover line |
| 58 | The CLI year remedy prints `YEAR:PATH` unquoted, and every filing name here has spaces | — | `ingestion/filings.py` | **new, the `P10c` review's F8.** Pasting it into a shell splits the path |
| 59 | Nothing checked that a printed line's label and value appear on the page it cites | **silent** | `ingestion/` | **closed by `P12a-printed-pages`**: both routes look up each Pass 1 line's label and figure on its cited page with `pdfplumber`; a line not found is a failed check, retried in route A, shown, figures kept. Walmart 89 of 89 found. Three limits, stated in `extraction.md` |
| 60 | `session_extraction plan` still ends with "The fiscal year comes from the filename. Check each one against the filing's cover page", although `P10c` now checks it | — | `ingestion/session_extraction.py` | **new.** Message only; tells a session to do by hand what the code already does |
| 61 | The `return financials` after Pass 1's retry loop cannot be reached | — | `ingestion/claude_extractor.py` | **new, found by the `P11a` tester.** Dead code. Since `P14a` it is `raise AssertionError`, so it is no longer a silent `return` (the `P14a` review's F8) |
| 62 | A failed reading check (an income statement subtotal, or a printed line not found on its page) never reaches the web page, for either route | **silent**, on the web | `api/routes_valuation.py`, `templates/` | **new, found writing `P12a`.** Route A prints failures to the server console; route B's `validation_errors` print in `check` and the CLI only. The balance check shows `FAIL` on the page because it is recomputed from the memo totals |
| 63 | A filing with no text layer uses up route A's two Pass 1 retries on lines that can never be confirmed | — | `ingestion/claude_extractor.py` | **new, the `P12a` review's F5.** Every line fails "cannot be confirmed", so the retries cost two full-PDF calls and change nothing. None of the 16 filings here lacks a text layer |
| 64 | The page check's joined-line form lets a label written across two printed rows take either row's figure | — | `ingestion/claude_extractor.py` | **new, the `P12a` round 2 review's F6.** Needs a label the filing does not print. Candidate: a joined form counts only when the neighbouring line prints no figure; 89 of 89 on Walmart, but Walmart uses no joined form, and it refuses a wrap whose other half prints a year. Measure on a filing with real wrapped rows first |
| 65 | `DCFResult.upside_downside` returns `0.0` when the current price is `0` | **silent** | `models/valuation.py` | **closed by `P13d-upside-price` (`2a09d3c`)**: `run_dcf` and `upside_downside` stop on a price that is not finite and above 0 |
| 66 | `derive_assumptions` pads the caller's growth list in place | **silent** | `analysis/projector.py` | **closed by `P13e-growth-input` (`d1b4ad2`)**: `derive_assumptions` works on a copy |
| 67 | `projection_years` is never checked | — | `analysis/projector.py` | **closed by `P13e-growth-input` (`d1b4ad2`)**: a `projection_years` that is not an int of 1 or more stops by name |
| 68 | The CLI prints no assumption label | **silent**, on the CLI | `cli.py` | **new, the `P13b` review's O1.** `print_assumptions` (`cli.py:677-695`) prints the rates and an `(override)` tag, never the label text. So `SUBSTITUTED`, `REPEATED` and `DROPPED` are invisible on the CLI; the web page shows them (rule 6) **Measured again 2026-10-08 at `e7f3023`** on the tracked Walmart file: the CLI prints six bare rates, and `sources` holds `origin=derived` with a sentence for each. `print_assumptions` is now at `cli.py:957`. **Assigned to `P3f-cli-assumption-labels`** (pilot team B) |
| 69 | A negative debt balance gives WACC weights above 1 and below 0 | **silent** | `analysis/wacc.py` | **closed by `P13f-wacc-debt` (`5c4fb67`)**: each debt line and the total must be finite and not negative |
| 70 | Walmart's stage 10 is not reproducible: PV of terminal value reads 214,819M or 214,820M between runs on one tree | — | stage 6 onward | **new, the `P13e` review's F3.** Cause not measured; live market data is the first suspect |
| 71 | The rule 3 census grep cannot see a conditional zero written on two lines | — | `docs/2-rules/rules.md` | **new, the `P13d` programmer and review.** `if x == 0:` / `return 0.0` is not counted, so the census undercounts |
| 72 | `cli.py:1035` and `:1043` hold conditional zeros (`shares`, `latest_bs.total_debt if latest_bs else 0`) | **silent** | `cli.py` | **new, the `P13f` programmer and review.** The census does not search `cli.py` **Half closed by `P3a-one-pipeline`:** the `shares` site is gone (`pipeline.py` reads the share count directly and stops on one that is not above 0). The `total_debt` display line stays in `cli.py` for `P3b-pipeline-stops`. **Closed by `P3b-pipeline-stops`, locked by `P3b-pipeline-stops-tests`:** `pipeline.ValuationRun` carries a required `total_debt`, `value_company` stops and names `balance_sheet`, the ticker and the fiscal year when the latest year has no balance sheet — **before any market call** — and `cli.py` stage 8 prints `run.total_debt`. The conditional zero is gone, and `ValuationRun.latest_balance_sheet` is no longer optional, so stage 8 has no branch left to default on. Walmart page 22 (printed page 54): 10,994 + 40,529 = **51,523**, and `wacc_result.debt_weight` equals `total_debt / (market_cap + total_debt)` on the same figure |
| 73 | Some bad first Pass 2 replies stop with no retry and no filing name | — | `ingestion/claude_extractor.py` | **new, the `P13g` review's F2.** `_extract_json(raw)` sits outside the first `try`, and that `except` catches only `JSONDecodeError` and `KeyError`. Pass the PDF path in so the filing can be named (F3) |
| 74 | An `OverflowError` or `RecursionError` from the Pass 2 retry escapes without naming the filing | — | `ingestion/claude_extractor.py` | **new, the `P13g` review's F1, minor.** The run still stops; the comment at the catch overstates the four types |
| 75 | The write guard reads text inside a Bash command as a file path | — | `.claude/hooks/guard_paths.py` | **new, five testers and reviewers.** A `>` or `=` inside a quoted pattern or heredoc, `sed -i`, and `2>/dev/null` are refused; in-repo `scratchpad/` paths are refused. No wrong write was allowed |
| 76 | The web form's `projection_years` has no lower bound, and the stop it reaches shows at HTTP 200 | — | `api/routes_valuation.py` | **new, the `P13e` review's F4.** The 200 comes from item 8's blanket `except` |
| 77 | Pass 2 asks the model to convert a note's figure into the statements' units | **silent** | `ingestion/claude_extractor.py` | **closed by `P14b-pass2-units` (`dde9b25`), locked at `21125ed`**: each Pass 2 item copies its figure as printed, its `page`, and the printed words that state its unit with their page; Python reads the scale (`pass2_amount_scale`), looks both up on their pages, and converts each item. Session format v4. Walmart's PhonePe item is now 0.7 from `$0.7 billion`, page 27, and still 700 $M after conversion. **Side effect, set by the assignment:** an `amount` of 0 now stops; it loaded since `P9d-tests` |
| 78 | The "already converted" guard sees balance sheets only | — | `ingestion/claude_extractor.py` | **new, the `P14a` review's F5.** A filing with no balance sheet, which is every route A filing but the newest, carries no marker. No call site converts twice today |
| 79 | Route A's unit stop names the field, the text and the page, but not the PDF | — | `ingestion/claude_extractor.py` | **new, the `P14a` programmer.** `_run_financials_pass` holds only bytes. The same shape as item 73 |
| 80 | The arithmetic check table and route B's failed-check messages are in printed units, and say nothing about it | — | `ingestion/claude_extractor.py` | **new, the `P14a` programmer.** For a filing in thousands, `printed=11,313,853` appears beside statements shown in $M |
| 81 | The Pass 2 page check's summary line miscounts the items not confirmed | — | `ingestion/claude_extractor.py` | **closed by `P14b-reasoning` (`49cf0f5`), locked at `158f25d`**: each item records whether any of its checks failed, and the summary counts those items |
| 82 | The CLI cache key stores the model as "(provider default)" when `-m` is not given | **silent**, latent | `cli.py` | **new, the overall lead, 2026-10-04.** After the default model changes, a cache written under the old default matches, and figures read by the old model are labelled with the new one (rule 6). No route A cache exists on this machine yet. Assigned to `P15b-gemini-flash` |
| 83 | The Pass 1 schema does not say whether a finance lease obligation is debt | **silent** | `ingestion/claude_extractor.py` (the `short_term_debt` and `long_term_debt` descriptions) | **closed by `P14d-finance-leases` (`78d21c4`), locked at `9e49bef`**: the schema and the prompt say that finance lease obligations are debt (current in `short_term_debt`, long-term in `long_term_debt`) and operating lease obligations are not; `CACHE_FORMAT` is `p14d-finance-leases-v1`. Route B's Walmart does not move: net debt 40,796, $28.02. The tests rebuild Walmart's page 22 and show that the other mapping gives net debt 34,035 with a balance sheet that still ties. No Gemini run has shown that route A follows the rule; that is a paid call |
| 84 | Check B1 confirms a unit statement on the row's page, not that it governs the row's table | **silent**, latent | `ingestion/claude_extractor.py` (`_row_scale_failures`) | **new, the `P14b-note-figures` review's F6, 2026-10-04.** A Pass 1 row from a note table whose unit is a column heading, not in parentheses ("in thousands"), passes when the page or the page before prints "(In millions)" for another table. The figure is then 1,000 times too large, and nothing reports it. A page that prints two scales (L3Harris 10-K 2026-01-02, PDF page 62) passes a row of either scale. Stated in `docs/3-architecture/extraction.md` and `docs/2-rules/llm-boundary.md`; the `extract-filing` skill tells route B to stop and ask. No real case is measured: the criterion 10 scan found a scale on every primary statement page of the 16 filings |
| 85 | Three texts name the unit statement stop and not check B1 | — | `ingestion/claude_extractor.py`, `ingestion/session_extraction.py` | **new, the `P14b-note-figures` review, 2026-10-04.** The comment above route A's retry loop (`claude_extractor.py:2416-2426`), the first sentence of the check retry prompt ("looked for each line and each unit statement on the page it cites"), and `check`'s "Clean" line, which lists every check that passed and does not name B1. No behaviour changes |
| 86 | The comment above `CACHE_FORMAT` names only the P11a and P14a marker changes | — | `cli.py:229-237` | **new, the `P14d-finance-leases` tester, 2026-10-05.** The marker changed again for `P14b-pass2-units` and `P14d-finance-leases`, and the comment does not say why. No behaviour changes |
| 87 | The web page and the CLI give different prices for the same filing: the assumptions form rounds each default to one decimal and posts it back as an override | **silent**, on the web | `api/routes_valuation.py` (`assumptions_page`, the `*_display` defaults), `templates/assumptions.html` | **new, the `P3a-one-pipeline` programmer, confirmed by its reviewer, 2026-10-05.** Walmart: operating margin 4.25% shows as 4.3%, and a user who accepts every default gets $27.01 on the web page; the CLI gets $28.02 from the same filing and the same market data. Older than `P3a`. **Measured 2026-10-05 by the overall lead's read-only agent, and it is worse than the row said.** (a) The six rounded strings are the form's `value` attributes (`templates/assumptions.html:157, 166, 172, 182, 187, 192`), and five of the six inputs also carry `step="0.1"`, so a browser enforces the same grid a second time. (b) `POST /valuation` **cannot** tell a value the reader typed from one the form filled in: the six ratios arrive as bare `float = Form(0)` with no companion flag, and `operating_margin / 100 if operating_margin else None` is the only test. The four neighbouring overrides are `str = Form("")` precisely so that "left blank" is expressible; the six ratios were not given that treatment. (c) **Rule 6 is broken in both directions.** On `GET /assumptions` the rounded figure sits under the heading "Derived Default" with the provenance "derived from the filing"; on `POST /valuation` the same figure carries "supplied by the caller — the assumptions form… nothing in this platform checks a figure you typed against the filing". So a number the platform produced is attributed to the reader, and the rounding itself is named on neither page. (d) **Size, executed on hand-built statements with market data stubbed:** an operating margin of 4.2537% rounded to 4.3% moves the share price from **$226.69 to $233.55, a difference of $6.85 or 3.02%**; rounding all six as the form posts them gives **$233.07**, 2.81% away. (e) `cli.py` rounds nothing on this path: its 24 format sites are all inside `print_*` functions and none is read back |
| 88 | The valuation assumptions are a bare `dict` passed between functions | — | `analysis/projector.py` (`derive_assumptions` returns it; `project_fcffs(financials, assumptions: dict)` takes it), `pipeline.py` | **new, the `P3a-one-pipeline` review's F2, 2026-10-05.** Rule 2 forbids an untyped dict as an argument bag. Keys are read by name (`assumptions["tax_rate"]`, `["terminal_growth_rate"]`), so a missing key is a `KeyError` at run time, not a type error. Fix: a typed return from `derive_assumptions` **The user's decision of 2026-10-05** ("Accept until item 88") accepts `pipeline.py`'s `assumptions: dict` until this item is fixed |
| 89 | `run_capm` prints from inside a calculation | — | `analysis/capm.py:215` | **new, the `P3a-one-pipeline` programmer and review, 2026-10-05.** It prints "ERP from history: ..." to stdout, so the web server's console gets it and the CLI shows it wherever the call happens to run. The `CAPMResult` should carry the figures, and the CLI print them. **Measured 2026-10-05 by the overall lead's read-only agent.** An AST scan of every `.py` under `analysis/` finds **exactly one** write to any stream in the whole package, this one. It fires on the default path, the `else` of `if equity_risk_premium is not None`. Both entry points reach it through the single call site `pipeline.py:201`: the CLI terminal gets it between the stage 5 and stage 6 banners, two stages before the CAPM section that discusses it, and the web server console gets it where no browser ever sees it. **Of the three numbers it prints, `CAPMResult` already carries two** (`risk_free_rate`, `equity_risk_premium`); the one it does not carry is the **annualized S&P 500 return**, which is the rule 4 link for the ERP. A second gap: there is no `equity_risk_premium_source` field, so a `CAPMResult` cannot say whether its ERP was supplied or computed |
| 90 | The default terminal growth rate is a literal in two places | — | `cli.py:205` (`0.025`), `api/routes_valuation.py` (`terminal_growth_rate: float = Form(2.5)`) | **new, the `P3a-one-pipeline` review, 2026-10-05.** The same shape as item 34's risk-free literal: not a named `config` constant, so editing one moves one entry point only. Rule 6 asks for a named default with its reason. **Corrected 2026-10-05 by the overall lead's read-only agent, and the correction changes the fix.** The constant **already exists**: `config.DEFAULT_TERMINAL_GROWTH_RATE = 0.025` (`config.py:118`). It is read by nothing. `grep -rn` over the repository gives one hit each, the definition itself, for **five** constants: `DEFAULT_PROJECTION_YEARS`, `DEFAULT_TERMINAL_GROWTH_RATE`, `DEFAULT_EQUITY_RISK_PREMIUM`, `DEFAULT_BETA_LOOKBACK_YEARS`, `DEFAULT_RETURN_FREQUENCY`. So editing `config.py` today moves **neither** entry point. The terminal growth rate is a literal in **four** places, not two: `cli.py:205` (`0.025`), `api/routes_valuation.py:530` (`Form(2.5)`), `templates/assumptions.html:147` (`value="2.5"`), and `models/valuation.py:397` (`terminal_growth_rate: float = 0.025`, the default `derive_assumptions` falls back to at `analysis/projector.py:149`). Projection years, beta lookback and return frequency each repeat in three places the same way |
| 91 | Seven scripts in `tests/` run their own valuation sequence, each with the yfinance share count fallback | — | `tests/test_e2e_abbv.py:175`, `test_e2e_abbv_3years.py:204`, `test_e2e_lly.py:175`, `test_e2e_googl_3years.py:219`, `test_e2e_all_googl.py:74`, `test_e2e_phase2_googl.py:123`, `tests/_run_lly_dcf.py:31` | **new, the `P3a-one-pipeline` programmer and tester, 2026-10-05.** Each holds `info.get("sharesOutstanding", 0) / 1e6`, which `P3a` removed from the pipeline (rules 3 and 5). The census does not scan `tests/`. Point them at `pipeline.value_company`, or delete them (item 40) |
| 92 | The CLI and the web pages show different historical FCFF for the same filing | — | `cli.py` (`print_historical_fcff(financials)`, the statements as extracted), `api/routes_valuation.py` (`_historical_fcff_by_year(normalised_financials)`) | **new, the `P3a-one-pipeline` programmer, 2026-10-05.** Walmart: the CLI shows 17,109 / 12,854 / 16,985 and the web pages 17,192 / 12,873 / 16,952. Normalisation changes the effective tax rate, which changes after-tax interest. Display only: neither table reaches the DCF. One of the two is the wrong basis, and nothing on either page says which statements it used. **Measured 2026-10-05 by the overall lead's read-only agent.** The web side has **two** call sites, not one: `api/routes_valuation.py:449` (`assumptions_page`) and `:670` (`run_valuation`), and both receive `adjustment.adjusted`, the same object `value_company` is given. **The web side is internally consistent; the CLI is not** — `cli.py:1021` passes the raw `financials` while `cli.py:1029` values `adjusted`. **The field that differs is `IncomeStatement.effective_tax_rate`**, and the function that moves it is `analysis/normalizer.apply_adjustments`: it replaces income-statement expense fields only, so `ebit` and `ebt` move, `tax_expense` is stored and does not, and `tax_expense / ebt` therefore changes. `calculate_fcff_historical` reads that rate only for `after_tax_interest = interest_expense * (1 - tax_rate)` (`analysis/fcff.py:78`), which is why the Walmart pairs differ by small signed amounts (83 / 19 / −33 on figures near 17,000). Demonstrated on one hand-built year: FCFF 1,188.37 raw against 1,195.21 normalised, CFO, CapEx and interest identical. **The function that feeds the DCF is `analysis/projector.project_fcffs`** (`pipeline.py:220`), which builds every projected FCFF from `assumptions` and reads no historical FCFF at all |
| 93 | Two more copies of the no-network rule refuse the loopback address, and carry the defect `P1b-windows-gate` fixed | — | `tests/unit/test_claude_extractor.py:637` (`_NetworkReached`), `tests/unit/test_p14b_note_figures.py:645` (`RuntimeError`) | **new, the `P1b-windows-gate` tester, 2026-10-05.** `P1b` put one `_no_socket` fixture in `tests/conftest.py` that allows `127.0.0.1`, `::1` and `localhost`, because a blanket refusal breaks the Windows `ProactorEventLoop` self-pipe and turns every `TestClient` request into a 500. These two copies still refuse every address. Neither fails today, because neither module builds an event loop. Fold both onto the conftest fixture. **Closed by `P1c-test-network-copies`, 2026-10-05.** Both socket patches are deleted and both modules carry `pytestmark = pytest.mark.usefixtures("_no_socket")`. `grep` over `tests/` now finds the three patched doors in `tests/conftest.py` and nowhere else. `--setup-show` counts 34 setups against 34 tests in `test_claude_extractor.py` and 31 against 31 tests that run in `test_p14b_note_figures.py`, against 0 and 1 before. `test_claude_extractor.py` keeps its key deletions and both model-client patches, which are the real guard there; `_NetworkReached` stays because three sites read it and its `BaseException` base is what keeps `except Exception` in `ingestion/` from swallowing it. A control test in each module turns red when the fixture is made a no-op. Gate 1137 passed, 0 failed. No third copy exists: the search covered socket patching, `getaddrinfo`, `urlopen`, `requests`, `httpx` and every fixture named `no_network`, `block_network` or `offline` |
| 94 | `_parse_files_param` stops with a bare `int()` message that names neither the field nor the file | — | `api/routes_valuation.py` | **new, the `P3b-pipeline-stops` programmer, 2026-10-05.** `_parse_files_param('a.pdf,b.pdf')` raises `ValueError: invalid literal for int() with base 10: 'a.pdf'`, and that text reaches the web page through item 8's blanket `except`. So a user who omits the `year:` prefix is told about base 10. It stops, so it is not rule 3's first half; it is the naming half. Adjacent to item 26, the same `files` branch |
| 95 | A third copy of the "every filing needs its fiscal year" rule is now unreachable | — | `ingestion/session_extraction.py` (`cmd_plan`) | **new, the `P3b-pipeline-stops` review's F2, 2026-10-05.** `cmd_plan(['a.pdf','b.pdf'])` now raises `require_fiscal_year_per_filing`'s message, because `parse_pdf_args` runs first. The check inside `cmd_plan` can no longer run. `P3b`'s objective is that the rule lives in one function, so this copy should go; deleting it was outside `P3b`'s file scope |
| 96 | `ValuationRun.latest_balance_sheet` is read by no production code | — | `pipeline.py` | **new, the `P3b-pipeline-stops` programmer and the review's F5, 2026-10-05.** `P3b` added `total_debt`, which is what the CLI needed from the balance sheet. The whole balance sheet is now read only by one assertion in `tests/unit/test_pipeline.py`. Deleting the field is a one-line change plus that assertion |
| 97 | Two templates render a multi-line error as one wrapped paragraph | — | `templates/assumptions.html`, `templates/valuation_result.html` | **new, the `P3b-pipeline-stops` round 2 programmer, 2026-10-05.** `templates/upload.html` sets `white-space: pre-line` on its error block and these two do not, so a `ValueError` with a file list and bullet remedies collapses into one paragraph on `GET /assumptions` and `POST /valuation`. Display only, and older than `P3b`: it applies to every multi-line stop those pages render |
| 98 | `runpy.run_path` defeats a patch on the module it re-executes, and a test that relies on one cannot fail | **silent, in `tests/`** | `tests/unit/test_pipeline.py:465` | **new, the `P3b-pipeline-stops-tests` round 2 tester, 2026-10-05.** Round 1's CLI stop test ran `cli.py` under `runpy.run_path(..., run_name="__main__")` and asserted `cli_extractor_calls == {"single": [], "multi": []}` after `monkeypatch.setattr(cli, "extract_financials", ...)`. `runpy` executes into a **fresh namespace**, so the patch on the `cli` module object was never the name the fresh copy bound, and the assertion was true whatever the code did. Fixed inside `tests/` by calling `cli.main()`. **The distinction the next reader needs:** a patch on a module that `cli` imports **from** still holds, because the fresh namespace re-binds the same function object. Measured by the overall lead: `grep -rn runpy tests/ --include=*.py` gives one other live site, `tests/unit/test_pipeline.py:465`, and it patches `pipeline.fetch_price_data` (`tests/unit/test_pipeline.py:132`) and yfinance, never an attribute of `cli` (`cli.py:64`, `from pipeline import adjust_financials, value_company`). **So that site is sound today.** The item is the trap, not a live defect |
| 99 | The legacy single-`file_path` branch is the one door into the extractor that no test and no fiscal-year rule guards | — | `api/routes_valuation.py:199` | **new, the `P3b-pipeline-stops-tests` tester, 2026-10-05.** `filings = [(0, file_path)]`. Correct as written, because one filing with year 0 is the allowed case, and `require_fiscal_year_per_filing` therefore has nothing to say about it. But coverage shows line 199 is reached by no test in the whole suite, so nothing would report it if a second filing ever arrived that way. Adjacent to item 26, the same route |
| 101 | A `skipif` guard names a filings folder that no machine uses, so a real-filing check skips on a machine that holds the filing | **silent, in `tests/`** | `tests/unit/test_p14b_note_figures.py:80-83` | **new, the overall lead's review of `P1c-test-network-copies`, 2026-10-05.** `_REAL_WALMART_PDF` is `10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf`. The folder on this machine is `10K_filings/WMT/` and it holds that exact file name, so `test_real_walmart_filing_scale_confirmation` skips although the filing is present. `_REAL_LHX_PDF` misses for a second reason: it names `..._10-K_2026-01-02_English.pdf` and the file on disk is `L3Harris Technologies Inc._10-K_2025_English.pdf`. `_REAL_CHIPOTLE_PDF` and `_REAL_OKTA_PDF` are legitimate skips here — this machine holds ABBV, LHX and WMT only, nine PDFs. **A test that skips reports neither pass nor fail**, so check B1's only real-filing evidence has not run on this machine. Measured: `find 10K_filings -name "*.pdf"` gives 9 files under `ABBV/`, `LHX/` and `WMT/`; `pytest -q -rs` names the four skips. The folder convention everywhere else in the repository is the ticker. `tests/unit/test_p14d_finance_leases.py:22` cites `10K_filings/Walmart/` in a docstring with the same error. `tests/unit/test_p15a_two_routes.py:238` passes `10K_filings/Walmart` to the CLI, which is harmless: argparse rejects `-p claude` before any path is read |
| 102 | The one `_no_socket` fixture's comment names two contract tests, and there are three | — | `tests/conftest.py:44-48` | **new, the `P1c-test-network-copies` tester, 2026-10-05.** The three are `test_no_socket_refuses_an_address_that_leaves_the_machine`, `test_no_socket_refuses_an_address_it_cannot_read` and `test_no_socket_allows_the_loopback_address`. A second fact belongs in the same comment: **the loopback test does not detect a fixture turned into a no-op**, because a loopback connection succeeds with no patch at all. The two refusal tests are what hold the contract. Text only, no behaviour changes |
| 100 | A filing citation gives one page number, and it is sometimes the PDF index and sometimes the printed page | — | `docs/5-testing/strategy.md`, `tests/unit/test_p14d_finance_leases.py`, `tests/unit/test_p3b_pipeline_stops.py`, `.agent/assignments/P3b-pipeline-stops-tests.md` | **new, the `P3b-pipeline-stops-tests` tester, 2026-10-05.** Walmart's Consolidated Balance Sheets are the **22nd page** of `10K_filings/WMT/Walmart Inc._10-K_2026-01-31_English.pdf` and are printed as the filing's own page **54**. Three texts say "page 22" with no word for which. Every figure cited is confirmed correct; only the wording is ambiguous. A reader opening the paper filing at page 22 finds nothing. Fix: one convention line, "a citation gives the printed page, with the PDF index beside it" |
| 103 | Nine form fields stop on a non-numeric entry with a message that does not name the field | — | `api/routes_valuation.py:650-658` | **new, the `P3c-one-number` programmer (F2) and its code reviewer (F1), 2026-10-06.** `float("abc")` raises `could not convert string to float: 'abc'`, and the blanket `except Exception` renders that on the result page. **Not rule 3: the run stops, nothing is defaulted or guessed.** Pre-existing for `risk_free_rate`, `equity_risk_premium`, `beta_override` and `cost_of_debt_override`; `P3c` gave the same shape to the five projection ratios, on the assignment's instruction. A reader cannot tell which of nine fields was rejected. Fix: one typed helper, `_optional_percent(field: str, value: str) -> float \| None`, used by all nine |
| 104 | The historical-FCFF basis sentence is a literal in three files and nothing checks that they still match | — | `cli.py:86-89`, `templates/assumptions.html:314`, `templates/valuation_result.html:259` | **new, the `P3c-one-number` programmer (F1) and its code reviewer (F2), 2026-10-06.** The sentence states which statements the FCFF table was built from. A reword in one file leaves the other two asserting a basis the figures may not have. **Rule 6: a label that can go stale silently is the defect that rule exists for.** Its single home is `pipeline.py`, the one module both entry points import, with the route passing it into both template contexts. All three candidate homes were outside `P3c`'s file scope, so the programmer recorded it and stopped, which the reviewer confirmed was right. **Updated 2026-10-06 by the `P3c-one-number-tests` tester (T4): there are now four copies, not three.** Its own test holds the sentence a fourth time and is the only thing checking that the other three still agree. So the sentence is held in place by a test rather than by a single definition, which is weaker than one home and better than nothing |
| 105 | `revenue_growth_rates=rev_growth_list if rev_growth_list else []`, both branches identical | — | `api/routes_valuation.py:640` | **new, the `P3c-one-number` programmer (F9) and its code reviewer (F3), 2026-10-06.** The conditional does nothing. No number moves. The census grep does not match it: that grep matches `else 0`, not `else []`. It sits three lines above five conditional-zero sites `P3c` removed |
| 106 | On `GET /assumptions` the basis sentence names a valuation that has not run | — | `templates/assumptions.html:314` | **new, the `P3c-one-number` code reviewer's F4, 2026-10-06.** The sentence reads "Computed from the normalised statements, the same statements the valuation used." The assumptions page renders before any valuation runs. Substantively true, one tense ahead. Fold into item 104's fix |
| 107 | `error_text` returns `None` for any error box that carries an attribute, so a missing box and an unreadable one are the same result | **silent, in `tests/`** | `tests/unit/_session_route_helpers.py:368` | **new, the `P3c-one-number` programmer's F6, 2026-10-06.** The regex is `<div class="alert alert-error">(.*?)</div>`, which requires the `div` to carry no attribute. `templates/upload.html:11` has carried `style="white-space: pre-line"` since before `19fe831`, so the helper has never been able to read the upload page's error box. `P3c` added the same attribute to the other two templates, and 20 tests in four files went red at once. **Proved by execution:** the same empty `POST /valuation` renders identical text and status in both trees, and only the attribute differs. Fix is four characters, `<div class="alert alert-error"[^>]*>`, **and** the helper must assert the box is on the page rather than return `None` |
| 108 | The repository's one session-file fixture cannot see item 87: every ratio it derives already rounds cleanly | **silent, in `tests/`** | the session fixture built by `tests/unit/` helpers | **new, the `P3c-one-number` programmer's F8, 2026-10-06.** Its six derived ratios are 30.0%, 20.0%, 3.0%, 7.0%, 1.5% and 100.0%, each already exact to one decimal place. Run end to end through it at `19fe831`, the web price equals the CLI price (`1243.176933388447`, delta 0.0), because rounding to one decimal takes nothing from a figure that already has one. **A regression test for item 87 built on that fixture is green before the fix and after it.** The fixture needs one ratio that does not round |
| 109 | `templates/_statements.html` prints `not extracted` six times for one uncomputable year | — | `templates/_statements.html:500-505` | **new, the `P3c-one-number` programmer's F4, 2026-10-06.** Once per column, so a year missing one statement produces six copies of the same sentence across the row. The CLI prints it once. Display only, no figure moves |
| 110 | `risk_free_rate` and `equity_risk_premium` still carry `step="0.1"` | **latent** | `templates/assumptions.html:254`, `:259` | **new, the `P3c-one-number` programmer's F3, 2026-10-06.** A browser refuses `4.25` in either field. They are blank-by-default fields whose substituted constant is `4.0`, so the grid does not bite today. `P3c`'s step 5 named only the five projection ratios. The same one-word fix, `step="any"` |
| 111 | The derived ratio is shown at one decimal place on every page, so the price cannot be reproduced by hand | — | `api/routes_valuation.py:436-441`, `templates/assumptions.html`, `templates/valuation_result.html` | **new, the `P3c-one-number` programmer's F7, 2026-10-06.** The "Derived Default" column, the input placeholder and the result page's provenance block all show `4.3%` for `0.04253700000000001`. **Rule 4: the chain is not walkable to the figure that produced the price.** `P3c` made the rounding harmless, because no rounded figure is submitted any more, but it did not make the used figure readable |
| 112 | Two different non-recurring items with the same year, amount and direction: the second is dropped and nothing says so | **silent, and it moves a number** | `ingestion/claude_extractor.py` (`merge_filing_extractions`, the NRI dedupe) | **new, the route B Walmart extraction of 2026-10-06, confirmed by the overall lead's own count.** The key is `(item.year, item.amount, item.direction)` and the guard is `if key not in nri_keys` with no `else`. Walmart's FY2024 10-K prints **two** incremental divestiture losses for fiscal 2022, each `$0.2 billion`: Asda on PDF page 66 and Seiyu on PDF page 67 (Note 12, Disposals, Acquisitions and Related Items). Both are `add_back`, both are 2022. **Measured:** 14 items written to `extractions/WMT.json`, 13 distinct keys, 13 in the merged list. So 200 $M of add-back is lost from fiscal 2022 and no message names it. The dedupe exists because overlapping filings re-report the same year, and two filings reporting the same item is the case it is right about. Fix: key on the source and the page as well, or report every drop. **Rule 3 and rule 6: a dropped input must not be silent.** **The path the 200 $M takes, measured 2026-10-06 by the `P14e` programmer and re-run by its code reviewer:** not the operating margin. All four Walmart fiscal 2022 items carry `line_item: "other_non_operating"`, which the normalizer applies **below** EBIT, so `operating_margin` is `0.045293441861602016` and `ebit` is `25942.0` with the item and without it. What moves is the fiscal 2022 **effective tax rate**: `ebt` `23706.0 → 23906.0`, exactly 200 apart, against an unchanged `tax_expense` of `4756.0`, so the rate goes `0.20062431451953092 → 0.19894587132937339` and the derived `tax_rate` assumption `23.147309% → 23.113740%`. That reaches NOPAT in all five projected years and the terminal value. Implied price `$30.65 → $30.67` on one live pair, against a market drift of ±$0.01 between runs |
| 113 | `session_extraction prompt --pass 2` exits 2 on a Windows console and prints only its header | **stopping, on Windows** | `ingestion/session_extraction.py` (`cmd_prompt`), the Pass 2 prompt text | **new, the route B Walmart extraction of 2026-10-06, reproduced by the overall lead.** `-m ingestion.session_extraction prompt extractions/WMT.json --filing 0 --pass 2` → `ERROR: 'charmap' codec can't encode character '→' in position 2992` and **exit 2**, after 19 lines of output. The `→` arrows are in the Pass 2 prompt's `direction` rules. `PYTHONIOENCODING=utf-8` in front of the same command gives **exit 0** and 82 lines. `--pass 1` is unaffected. **An agent that does not know the workaround cannot read the Pass 2 prompt on this machine**, and the error names an encoding rather than the remedy. Fix: write the stream as UTF-8 in `cmd_prompt`, or use ASCII in the prompt text. The same class as the `extract-filing` skill's ASCII rule for console output |
| 114 | The two unit-scale checks disagree about where a unit statement may be printed | **stopping, on a correct reading** | `ingestion/claude_extractor.py` (`_unit_statement_pages_allowed` against `_row_scale_failures`) | **new, the route B Walmart extraction of 2026-10-06, confirmed by the overall lead against the code.** Check B1 reads the row's page **and the page before it**. `_unit_statement_pages_allowed` returns, for `units`, exactly the set of pages an income statement printed line cites, with no "page before". Walmart's FY2024 10-K splits its income statement: the title and `(Amounts in millions, except per share data)` sit at the foot of PDF page 45 and **every data row is on page 46**. So citing page 45, which is where the statement is printed, stops the run at exit 2 on a reading that is right. The extraction cited page 46, which prints `(Amounts in millions)` as the Consolidated Statements of Comprehensive Income header: a real printed statement, on the page of the figures, of the same scale. No figure moved and no scale word was invented. Fix: give `_unit_statement_pages_allowed` the same "or the page before" rule B1 has. **CLOSED by `P14g-unit-statement-pages`, 2026-10-07.** One new pure function, `_pages_and_page_before`, holds B1's rule once, and `_unit_statement_pages_allowed` and both of B1's page lines read it. The citation of page 45 is now accepted, `units allowed=[45, 46]`. **No prompt byte and no schema byte moved**, confirmed by the reviewer by hashing `inspect.getsource` of all sixteen prompt and schema objects in both trees. **The newly-allowed page is still checked, not merely allowed**: `(Amounts in millions)` cited on page 45 is still refused, because that text is not printed there. B1's rewritten line is identical in **value and order** to the old `(page, page-1)` for every `page >= 1`. Walmart does not move: the whole CLI run is byte-identical across both trees. **Two corrections to this item's own text, each found by an agent that measured rather than read.** First, the allowed sets at `HEAD` were `[46]`, `[45]` and `[21, 22]`, not the wider `[46, 48]`, `[45, 48]`, `[21, 22, 23]` the overall lead wrote into the assignment: `_INCOME_STATEMENT_LINE_FIELDS` excludes the five cash-flow fields on purpose, and the programmer and the reviewer each caught it separately. The conclusion is unaffected. Second, **the fix carries a price and it is now item 138**: the widening takes the window in which a model may cite another table's unit statement from one page to two, and nothing can see it, because B1's expected scale is read from `units` itself. Tests: `tests/unit/test_p14g_unit_statement_pages.py`, 26 functions, 113 cases, 72 of 72 assertions hand-sourced and 0 from the code's output, four mutations applied and four killed. Items 138, 139 and 140 opened |
| 115 | The real route B test reads the balance sheet from `filings[0]`, and the plan puts it on the newest filing | **silent, in `tests/`** | `tests/unit/test_p14d_finance_leases.py:536` | **new, the overall lead, 2026-10-06, the first run against a multi-filing route B file.** `bs_raw = raw["filings"][0]["pass1"]["latest_balance_sheet"]`. `cmd_plan` gives the balance sheet to the filing with the newest fiscal year and writes `{}` for every other filing, so with three Walmart filings the balance sheet is on `filings[2]` and the test reads an empty dict: `KeyError: 'short_term_debt'` at `:539`. **The test passed only because the macOS session file held one filing.** Its four loader-level assertions (`short_term_debt == 10994.0`, `long_term_debt == 40529.0`, `total_debt == 51523.0`, `net_debt == 40796.0`) are correct and pass against the new three-filing file, measured. Fix: select the filing whose `latest_balance_sheet` carries a `year`, never an index. **A test that hard-codes a filing index is not a test of the route, it is a test of one file** |
| 116 | A year with no income statement is invisible in every table, and the branch written to report it cannot run | **silent, and it hides a whole year** | `models/financial_statements.py:434-440` (`years`), `cli.py:737-738`, `api/routes_valuation.py:266-267` | **new, the `P3c-one-number-tests` tester's T1, 2026-10-06, confirmed by the overall lead against the code.** `FinancialStatements.years` is built from `self.income_statements` alone. Both entry points then loop over `years` and ask `get_income_statement(year)`, so that call can never return `None` and `if income_statement is None: missing.append("income statement")` is unreachable in both. **Do not delete the branch.** The branch is right and the set it iterates is wrong: a year that has a cash flow statement and a balance sheet but no income statement is not in `years`, so it appears in no table, carries no reason, and nothing reports it. Fix: build `years` from all three statement kinds, which makes the branch reachable **and** closes the silent hole. Two call sites must then be re-checked, because every consumer of `years` today may assume an income statement exists. **CLOSED by `P3d-invisible-year`, 2026-10-07.** `years` is now the union of all three statement kinds, and a new `income_statement_years` sits beside it for the readers that need an income statement per year. All twelve readers outside `tests/` were visited and tabulated with the set each now reads and why. **Neither dead branch was deleted** — the trap the assignment named — and both now fire: coverage reports `cli.py:934-935` and `api/routes_valuation.py:273-274` as EXECUTED, and both print the same five words, `not extracted: income statement`. `latest_year` reads the narrow set, so its "holds no income statements" stop is still true when it prints. `analysis/projector.derive_assumptions` reads the wide set through a new `_income_statements_for_years`, which **stops and names `revenue` and the fiscal year** rather than dereferencing `None`. **The measurement that justifies the stop, taken at `HEAD` by the programmer and reproduced independently by the reviewer**: the invisible year made the revenue CAGR read two fiscal years of growth as one, `(1200/1000)^(1/1) - 1 = 20.0%` against the hand figure `9.545%`, and `HEAD` printed `revenue growth = [0.19999…] × 5` with nothing naming the missing year, so **a silent skip would have kept the 20%**. Tests: `tests/unit/test_p3d_invisible_year.py`, 28 functions, 33 cases, 101 of 101 assertions hand-sourced and 0 from the code's output, 78 of 78 added statements covered and 0 missed, seven mutations applied and seven killed. Items 128 to 137 opened for what it found and did not fix |
| 117 | The only test of a real route B file is `skipif`-guarded on a git-ignored file, so it runs on no clean checkout | **silent, in `tests/`** | `tests/unit/test_p14d_finance_leases.py:519`, `.gitignore:33` | **new, the `P3c-one-number-tests` tester's T3, 2026-10-06.** Eleven assertions guard the route B balance-sheet mapping and the finance-lease rule (decision 83a), and every one skips unless `extractions/WMT.json` happens to be on the machine. **That skip is how item 115 reached `main`**: the test carried `filings[0]` for two commits and nothing could report it. The same shape as item 101. Fix: commit a small three-filing route B fixture built from a filing in the repository, so the mapping is checked on every machine, and keep the real-file test as an extra. **Widened 2026-10-06 by the `P14e-nri-dedupe` tester's finding 3**: a session file also records **absolute** `pdf_path` values, so even a copied file names paths that exist on one machine. Any committed fixture must hold relative paths, or the loader must resolve a relative path against the session file  **CLOSED at `32b3f06`, 2026-10-08**, on the user's instruction: `extractions/` is now tracked, so the guard runs on every checkout. **The cost of its absence was measured by the `P1e-test-order` tester the same day**: a scratch copy without `10K_filings/` and `extractions/` skips **12 more tests in silence**, 14 skipped against 2, and a mutation or coverage figure taken in such a tree reads as clean |
| 118 | `coverage` counts none of a continuation-line diff as an executable statement | — | the measurement, not the code | **new, the `P3c-one-number-tests` tester's T5, 2026-10-06.** `P3c` added 37 lines to `api/routes_valuation.py` and coverage.py reports **0** of them as statements, because every one is a continuation line of an existing statement. So a done-criterion phrased "line coverage of the lines this unit added" reads `0/0` on a diff of that shape and says nothing. **An assignment must ask for branch coverage of the behaviours, named**, not for line coverage of a diff |
| 119 | Two filings that re-report one item in different words are counted twice, and nothing says so | **silent, latent** | `ingestion/claude_extractor.py` (`nri_identity`, `merge_filing_extractions`) | **new, the `P14e-nri-dedupe` programmer's finding 1 and its code reviewer's F2, 2026-10-06.** The across-filing key is `(year, amount, direction, description)`. Two filings describing one charge in different words therefore produce two items, and no drop happens, so nothing prints. This is item 112's defect failing the other way. **It was left open deliberately: deciding that two texts mean one charge is a judgement rule 1 gives to the model, not to Python**, and a tolerance or a fuzzy match in the merge would be that judgement written in code. **Measured, and the trigger is rarer than item 112's was.** `plan_filings` (`claude_extractor.py:2789-2798`) gives the oldest filing every year it presents and every other filing its own fiscal year alone, and `_build_nri_prompt` (`:2338-2340`) puts that year list in the Pass 2 instruction. So on the planned path the years are disjoint and a cross-filing re-report needs the model to volunteer a year it was not asked for. In the real Walmart file it never did: filing 0 covers 2022, 2023 and 2024, filing 1 covers 2025, filing 2 covers 2026, **zero cross-filing overlap**. Item 112's mode fired at once, 1 drop in 14 items. **If a real pair appears, it is the user's decision and not a programmer's tolerance** |
| 120 | A row repeated three times in one filing prints two identical `[MERGE]` blocks, each saying "listed twice" | — | `ingestion/claude_extractor.py` (`_print_repeated_item`, `REPEAT_WITHIN_ONE_FILING`), `ingestion/session_extraction.py` (the summary line) | **new, the `P14e-nri-dedupe` round 2 review's F5, 2026-10-06.** The counts are right: three copies give one item and two drops reported. The words are not: the two `[MERGE]` blocks are byte-identical, so a reader cannot tell two drops from one block printed twice, and "listed twice" is false for a third copy. **No rule is broken and no figure moves.** The fix is the `P14e` programmer's own finding 4: a per-run drop total beside `non-recurring items: 14`, so merged-away items are countable. That summary lives in `ingestion/session_extraction.py`, which was out of the unit's scope |
| 121 | Five Pass 2 fields stop with a bare `KeyError` that names the field and not the item; five others name the year and the description | **minor, pre-existing** | `ingestion/claude_extractor.py:2252-2262` (`_parse_nri_response`) | **new, the `P14e-nri-dedupe` tester's finding 1, 2026-10-06.** `year`, `description`, `line_item`, `direction` and `category` raise a bare `KeyError`. `confidence`, `source`, `amount`, `page` and `units` each raise a `ValueError` naming the year and the description. **The stop is right in both cases and rule 3 is satisfied.** What differs is what a reader can do with it: on a filing with fourteen items, a `KeyError: 'direction'` does not say which one. Fix: give all ten the `ValueError` shape. The `P14e` tests accept either exception type, so they will not turn red when it is fixed |
| 122 | `cli.py --debug` has item 113's defect on route A, and it stops **after** the paid API call | **stopping, on Windows, and it costs money** | `ingestion/claude_extractor.py:2420` and `:2593`, `cli.py`, `app.py` | **new, the `P14f-prompt-encoding` programmer's finding 1, 2026-10-06.** Both lines print the model's raw response to stdout. **One character outside cp1252 in a model answer raises `UnicodeEncodeError` between the call and the parse**, so the call is paid for and its answer is lost. Neither `cli.py` nor `app.py` configures its streams; `P14f` fixed `ingestion/session_extraction.py` alone, because that was its file scope. The fix is the same one function on the same two streams at each entry point. **Full inventory of cp1252-unencodable characters in `.py` source, measured by encoding every character**: `claude_extractor.py` 14 × U+2192, of which only `:412-413` are printed; `models/financial_statements.py:161` one, in a comment; `tests/test_e2e_phase2_googl.py:4-5` two, in a docstring; `tests/unit/test_statements_ui.py:832` one **U+2212 MINUS SIGN**, asserted against rendered HTML, so a template sends U+2212 to the web page. **`sys.stdout.errors` is `surrogateescape` on this machine, not `strict`, and that is not a defence**: it rescues lone surrogates only, never U+2192 |
| 123 | `name_unencodable_characters` returns a `bool` its docstring says a caller can use, and the call site discards it | — | `ingestion/session_extraction.py:1180-1181`, `:1195-1196` | **new, the `P14f-prompt-encoding` review's F1, 2026-10-06.** The docstring promises "so a caller can tell the two apart" and `main()` reads neither return value. **Not a rule break**: the reviewer tested the `False` branch and it fails towards the pre-existing stop, never towards a number. Fix: let a test assert on the return, or delete the sentence |
| 124 | `main()` changes a process-global stream handler and never restores it, and a test calls `main()` in-process | **latent, in `tests/`** | `ingestion/session_extraction.py` (`main`), `tests/unit/test_session_extraction.py:1180` | **new, the `P14f-prompt-encoding` review's F2, 2026-10-06.** `_pytest.capture.CaptureIO` **is** an `io.TextIOWrapper` subclass, so the `namereplace` handler leaks into every test that runs after it in the same process. **Measured harmless today**: the gate is `1207 passed, 2 skipped, 0 failed` either way. It is recorded because the next test that asserts on an encoding failure would pass or fail by test order. Fix: restore the handler, or set it in a `__main__` guard rather than in `main()`  **CLOSED by `P1e-test-order`, 2026-10-08.** `main()` now runs inside a `contextlib.contextmanager`, `naming_unencodable_characters`, that reads the handler, sets `namereplace`, and restores it in a `finally`. **Closed by execution and confirmed twice**: the programmer and then the code reviewer each ran their own probe against a `git archive HEAD` tree and this one, and `HEAD` leaves `namereplace` where this tree leaves the handler it found. The reviewer went past the happy path to the argparse `SystemExit` route, an uncaught-exception route, and one object bound to both stream names. **The shape was chosen against the alternative**: a `__main__` guard would not run for the in-process caller at `tests/unit/test_session_extraction.py:1180` and would hand it item 113 back. **It carries a rule 3 stop**: a handler that is not a `str` raises `TypeError`, because `reconfigure(errors=None)` means leave the handler alone and would silently keep `namereplace`, which is this defect in a quieter form. The overall lead ran that stop as its own acceptance mutation: made silent, it turns 2 tests red |
| 125 | The inherited `surrogateescape` handler is replaced, not composed, and no text says so | — | `ingestion/session_extraction.py` | **new, the `P14f-prompt-encoding` review's F3, 2026-10-06.** A lone surrogate used to round-trip to its original byte and now prints as `\udcff`. **Visible rather than raw is the direction the unit wanted**, so this is not a defect; the programmer's entry simply does not record that the change removes the old behaviour. One sentence |
| 127 | No test-order guard exists, so order dependence between test files is untested | **silent, latent** | the test suite as a whole | **new, 2026-10-07. This is what item 126 left behind once the flag was deleted.** `pytest-randomly` is not installed, so every run uses one fixed order, and a test that passes only because another test ran first passes forever. **Item 124 is a live example of the class**: `ingestion/session_extraction.main()` leaves a `namereplace` handler on a `_pytest.capture.CaptureIO` stream, which is an `io.TextIOWrapper` subclass, for every later test in the same process. The `P14f` tester worked around it with three subprocesses and by permutation, and recorded both. Fix: install `pytest-randomly`. **It may turn tests red the first time it runs, which is the point**, so it is a unit of its own and not a cleanup. **DECIDED by the user on 2026-10-07, option `a`: install it.** The two options it was weighed against are recorded because they shape the unit: a pinned default seed (`b`) buys one measurement and then stops measuring, and leaving it (`c`) keeps a suite figure that one ordering produced. **Assigned as `P1e-test-order`, written and waiting on a clear queue**, because installing the plugin changes the result of every gate command in this repository at once. **Its assignment carries no "0 failed" criterion**, on purpose: what it owes is the failing set **by name** at each of five named seeds. **One consequence of the decision needs stating wherever the flag is discussed:** `-p no:randomly` was a no-op while nothing was installed, which is why item 126 deleted it. Once the plugin is installed the same string stops being a no-op and becomes a way to switch the guard off, so the assignment forbids it in any command, document or config file  **CLOSED by `P1e-test-order`, 2026-10-08**, on the user's decision 1a: `pytest-randomly` 5.0.0 is installed and declared in `requirements-dev.txt`. **The guard found nothing, and that was reported as a result rather than dressed up**: sixteen gate runs across ten orders, each with the same failing set. **The programmer then said why the negative is weaker than it looks and the reviewer sharpened it**: the three tests that observe the handler run in a **subprocess**, so item 124, the one known order leak, could never have been found this way at any seed. **Two limits belong with this item.** First, `pytest-randomly` shuffles modules **and** the tests within a module, so this item's class, order dependence between files, is covered, but **modules stay contiguous blocks**, so a dependence needing module Y's test to run between two of module X's is unreachable at any seed. Do not read shuffled as all permutations. Second, **`-q` suppresses the `Using --randomly-seed=` line**, measured both ways, and every documented gate command uses `-q`, so a red gate records no order unless it is re-run without `-q`. `docs/8-build/environment.md` now states all of it |
| 126 | `-p no:randomly` was in nine live and recorded documents and asserted nothing | **silent, and it had been quoted as a guard** | `STATUS.md`, `.agent/QUEUE.md`, this file, six `.agent/assignments/*.md`, nine `.agent/journal/*.md` | **closed on the user's decision "1a", 2026-10-07.** `importlib.metadata` lists exactly two pytest distributions, `pytest` and `pytest-cov`; `-m pytest -p randomly` raises `ImportError: No module named 'randomly'`; and pytest accepts **disabling** an absent plugin in silence, so every command carrying the flag ran and the flag asserted nothing. The flag is deleted from every live document. **Journal entries and accepted assignments keep it**, because they record what was run and what was asked, and rewriting them would falsify the record. **Two corrections to the first write-up, both the overall lead's**: this row named `docs/8-build/environment.md` as a carrier and **that file never held the flag** (`grep -n randomly docs/8-build/environment.md` returns no match), and the count was nine documents, not "every documented gate command". The first was taken from the `P14f` tester's finding on report instead of being grepped. **What the deletion does not fix is item 127** | **new, the `P14f-prompt-encoding` tester's finding 1, 2026-10-06, reproduced by the overall lead.** `importlib.metadata` lists exactly two pytest distributions, `pytest` and `pytest-cov`. `-m pytest -p randomly` raises `ImportError: Error importing plugin "randomly": No module named 'randomly'`. Disabling a plugin that is absent is accepted silently, so **every command carrying `-p no:randomly` runs, and the flag asserts nothing.** **What follows is the part that matters: test order is fixed, so order dependence between files is untested on this machine, and backlog item 124 is exactly that class of defect** — `main()` leaves a `namereplace` handler on a `CaptureIO` stream for every later test in the process. The tester worked around it by permutation (leaking file first 173 passed, its file first 173 passed, each of its 17 ids one per process in reverse order all green) and by construction (no test of its own touches `sys.stdout` or `sys.stderr`, and all three `main` tests run in a subprocess). **Two fixes, and they are not equivalent.** Install `pytest-randomly`, which gives a real guard and may turn tests red the first time it runs; or delete the flag everywhere, which is honest and adds nothing, because nothing was there |
| 128 | The CLI reconciliation iterates `raw.years` where the page iterates the union of both sides, so a year only the adjusted statements reach is on the page and not in the CLI | **silent, latent** | `cli.py:845` against `api/routes_valuation.py:329` | **new, the `P3d-invisible-year` code reviewer and its tester, 2026-10-07, found independently by both.** `cli.py` sets `years = raw.years`; `api/routes_valuation._build_ebit_reconciliation` sets `years = sorted(set(raw.years) \| set(adjusted.years))`. **Both agents refused to charge it to `P3d-invisible-year` and both were right**: `git diff -U0 -- cli.py` matches that line with neither `+` nor `-`, so it is unchanged context and `docs/9-reference/severity.md:83` does not reach it. The overall lead confirmed that at acceptance. Unreachable today, because the normaliser returns a statement for every raw year. **The tester says in so many words that its own suite does not cover this**: its parity test passes only because its fixtures give both sides the same year set. This is the repository's third standing trap, two entry points drifting apart, in the one place `P3d` did not look **CLOSED by `P3e-reconciliation-years` (`2887387`, merged as `f4059c7`), 2026-10-08**: `cli.print_normalization` iterates `sorted(set(raw.years) | set(adjusted.years))`, as `_build_ebit_reconciliation` does. `tests/unit/test_p3e_reconciliation_years.py` holds the year-on-one-side-only cases this item said no test covered; restoring `years = raw.years` gives 6 failed, 11 passed. The first unit built by an Antigravity build lead in a worktree |
| 129 | `Gross Margin` and `EBIT Margin` print a fabricated `0.0%` for a zero-revenue year, one line above a net-margin row that says the figure is absent | **silent** | `models/financial_statements.py:108` (`gross_margin`), `:132` (`operating_margin`), rendered by `cli.py` and `templates/_statements.html:44`, `:86` | **new, the `P3d-invisible-year` code reviewer's F1, 2026-10-07, and the overall lead's ruling on it.** Both properties carry `… / self.revenue if self.revenue else 0.0`, which are two of item 1's 64 sites. `P3d` fixed the net-margin row beside them and **deliberately left these two**, so one row of that table now tells the truth and the two above it do not. **Two facts forced that ruling and both must hold for whoever closes this.** First, `templates/_statements.html:44` and `:86` render the same two properties, so a repair inside `cli.py` alone splits the two entry points. Second, `analysis/projector.py` reads `operating_margin` into `op_margins`, whose average reaches the DCF and the share price, so changing the property **moves a figure** and is not a display repair. **Close it with item 1's census unit, taking both entry points and the projector together.** The `P3d` tester wrote no assertion about those two cells on purpose, saying that locking them would make the defect permanent and turn its fix red |
| 130 | Seventeen cash flow cells print whitespace for a year with no cash flow statement, where the page prints the words | — | `cli.py` (`_print_cash_flow_table`, the 17 `… if financials.get_cash_flow(y) else " " * col` expressions) | **new, the `P3d-invisible-year` round 1 programmer's finding 1, 2026-10-07, confirmed by its code reviewer.** The branch substitutes **whitespace, not a number**, so no figure is invented and it is not a rule 3 break. `P3d` added a line naming each such year under the table, so it is no longer silent, but the blank cell itself still reads as "nothing happened" rather than "not extracted". The web prints `not extracted` in the cell. Seventeen copies of one decision, so it wants a unit of its own. It is also seventeen instances of the conditional shape the census grep cannot see |
| 131 | `templates/_statements.html:295` calls `financials.latest_year` inside a `{% set %}`, and that property raises | **latent** | `templates/_statements.html:295` | **new, the `P3d-invisible-year` round 1 programmer's finding 4, 2026-10-07, confirmed by its code reviewer as the one unguarded template reader of the 37.** For a filing with no income statement at all, `latest_year` raises a `ValueError` through jinja, which the blanket `except Exception` (item 8) renders as a string on the results page. **`P3d` did not create it** — `latest_year` raised on that filing before too — but widening `years` lets such a filing reach the template with a non-empty year list for the first time, so the path is now easier to reach. The CLI's equivalent is fixed (`_print_latest_balance_sheet`); the page's is not. `templates/` was outside `P3d`'s scope |
| 132 | `_print_income_statement_table` and `_print_net_margin_absences` are a pair that nothing enforces | **latent** | `cli.py` (`_print_income_statement_table`, `_print_net_margin_absences`) | **new, the `P3d-invisible-year` round 2 code reviewer's N1, 2026-10-07, and the tester's finding 2.** Called alone, the table prints a blank net-margin cell and no reason for it, which is the silent form of the defect `P3d` repaired. The tester wrote the mutation and it goes red, but **it is enforced at the one call site only**: a second caller that omits the absence line leaves the test green. The tester says so itself |
| 133 | Two more `if target_years:` sites survive the one `P3d` fixed | — | `ingestion/claude_extractor.py:2280`, `:2358` | **new, the `P3d-invisible-year` round 2 programmer, 2026-10-07, and its tester's finding 4.** `P3d` changed `:2329` to `target_years if target_years is not None else …` after the reviewer walked every caller and found that none passes an empty list. These two carry the same shape. Not live for the same reason, and the fix is the same one token. Take all three in one unit **CLOSED by `P14h-target-years` (`a67a225`, tests `3ad257e`, merged as `ea430d0`), 2026-10-08**: `_build_financials_prompt` and `_build_nri_prompt` test `target_years is not None`, and an empty list stops with a `ValueError` naming `target_years`. **Not the one-token fix this item named**: `is not None` alone would have sent the model a prompt naming no year. `None` and a non-empty list build the same text as before; the six real Walmart prompts hash as before. Restoring `main`'s builders gives 8 failed, 9 passed |
| 134 | The new balance sheet divergence line can name a balance sheet that does not exist | — | `cli.py` (`_print_latest_balance_sheet`) | **new, the `P3d-invisible-year` round 2 code reviewer's N3, 2026-10-07.** `P3d` added a line saying so when the balance sheet the CLI shows is not the one `pipeline.value_company` reads, which closed a real silent divergence. For a filing whose only balance sheet is 2026 the line reads "the valuation below reads FY2025's balance sheet" while `get_balance_sheet(2025)` is `None`. **No figure is invented**: `pipeline.py:182` then stops and names it. The sentence is wrong before the stop prints |
| 135 | "revenue is 0" asserts a measurement the code cannot tell from an absence | — | `cli.py` (`_print_net_margin_absences`) | **new, the `P3d-invisible-year` round 2 code reviewer's N4, 2026-10-07.** `revenue: float = 0.0`, so an income statement whose revenue was never extracted and one whose revenue is really zero are the same bytes. The line `not computable: net income margin, revenue is 0` states the second. It is item 1 wearing a sentence rather than a number, and it closes with item 1 |
| 136 | `cli.main` has no `try`/`except` of its own, so a stop surfaces differently in the two entry points | — | `cli.py` (`main`, and the `if __name__ == "__main__"` block) | **new, the `P3d-invisible-year` tester's finding 3, 2026-10-07.** The `ERROR:` handler sits in the `if __name__ == "__main__"` block, so a stop raised inside `main` reaches a caller that imports and calls `main()` as a bare exception, and reaches a command-line user as a printed line. `P3d` added a stop that both entry points can raise, which is what made the difference visible. Worth a line in whichever unit closes item 8 |
| 137 | A filing with no income statement at all reports that fact once per year as well as once for the filing | — | `cli.py` (`print_extracted_financials`) | **new, the `P3d-invisible-year` round 1 code reviewer's F5, 2026-10-07. Readability only; it cites no rule.** `print_extracted_financials` prints `No income statement extracted for any year.` and then `not extracted: income statement` for every year in the list. On a five-year filing that is one sentence plus five lines saying the same thing. The overall lead ruled it left on purpose, so that `P3d`'s diff did not widen for it. Fix: skip the per-year lines when the income statement year list is empty |
| 138 | **Nothing cross-checks the `units` claim, because check B1 reads its expected scale from `units` itself** | **silent, and it multiplies every money figure** | `ingestion/claude_extractor.py` (`_row_scale_failures` through `_filing_units`, against `_unit_statement_failures`) | **new, the `P14g-unit-statement-pages` programmer's criterion 5 and its code reviewer, 2026-10-07, each measured independently.** B1 asks "is a statement of the scale `units` claims printed near each row?" and reads that expected scale from `_filing_units(data)`, which reads `units`. **That is circular**: for an answer that cites the wrong statement's unit line, B1 reports `0 pages not confirmed`. The page restriction in `_unit_statement_failures` is the only guard. **Measured, on a two-page PDF the programmer built and the reviewer rebuilt from scratch**: page 1 a note headed `(in thousands)`, page 2 the income statement headed `(in millions)` with every figure, and `printed_scale` gives `Fraction(1, 1000)` against `Fraction(1, 1)`, so every money figure is divided by 1,000. **The hole is older than `P14g`. The reviewer put the same note on the SAME page as the figures and it is accepted at `HEAD` too**, so `P14g` widened an existing window from one page to two and did not open one. Across the nine filings on this machine, 47 of 1,104 pages have the split shape the widening serves and 17 have the shape it exposes, and none of the 17 is a page the income statement cites in the three extractions held here. **Two narrower rules were priced by execution and BOTH FAIL, so do not re-propose either**: rule X, "allow the page before only when the figure's own page prints no scale statement", refuses Walmart fiscal 2024 (`allowed units=[46]`) and so breaks the defect `P14g` fixed; rule Y, "allow the page before only when the figure's own page prints no statement the `units` text equals", accepts the bad case (`allowed units=[1, 2]`) and so leaves the hole. The 2x2 is in `.agent/journal/2026-10-07T1642-code_reviewer-p14g-unit-statement-pages.md`. **The shape that would work is a new primitive**: compare the scale word of every statement printed on the allowed pages and stop when two disagree. **Its tester writes the first assertion about this case.** `tests/` says nothing about it today, on purpose: the `P14g` tester refused to assert `len(failures) == 0` for the wrong answer, because that would lock the hole and turn red when it is closed, and it wrote that refusal into its new file's module docstring so the silence is findable. **DEFERRED by the user on 2026-10-07, option `a`: leave it in queue order.** It was offered as the next unit, ahead of the queue, and was not taken. **The two facts behind that**: the hole is older than `P14g`, because the same wrong answer on the figures' own page is accepted at `HEAD` too, and no filing this repository holds can reach it, because the three extractions cite pages 46, 45 and 21 to 22 and none of the 17 exposed pages is among them. So the queue runs `P1e-test-order`, then `P14c-layout-facts`, then the deferred route A work, and this waits |
| 139 | `extractions/WMT.json` `filings[0]` cites the Comprehensive Income statement's unit header, not the income statement's own | — | `extractions/WMT.json`, `filings[0]` | **new, the `P14g-unit-statement-pages` programmer, 2026-10-07, confirmed by the overall lead against the PDF.** It carries `units = {"printed": "(Amounts in millions)", "page": 46}`. PDF page 46 prints exactly one scale statement and it is the **Consolidated Statements of Comprehensive Income** header. The Consolidated Statements of Income's own header, `(Amounts in millions, except per share data)`, is on page 45, and **`P14g` makes it citable for the first time**: before that unit the check refused page 45, which is why the extraction reads as it does. `filings[1]`, the same company's next filing, cites page 45 with the full text. **No figure moves**, proved by the byte-identical CLI output across both trees: both texts read millions. Fix: re-extract or hand-correct `filings[0]` to page 45, so the repository's one real route B file cites the statement it claims to describe. The file is not in git |
| 150 | Three test findings in `tests/unit/test_p15c_portable_session_paths.py`: a `cmd_plan` test that depends on the working directory, two tests that assert the code's whole message, and 22 s of real-PDF loads that slow every gate run | **minor, in `tests/`** | `tests/unit/test_p15c_portable_session_paths.py` | **new, the overall lead's review of `P15c-portable-session-paths`, 2026-10-08.** (F1) `test_cmd_plan_writes_repo_relative_paths_for_repo_filings` passes `2024:10K_filings/WMT/…`, which `cmd_plan` resolves against the working directory: from `/tmp`, 1 failed, 13 passed. Pass `config.BASE_DIR / <path>`. (F2) the two missing-PDF tests assert both paths, as criterion 6 states, and then the whole message copied from the f-string (`docs/5-testing/strategy.md`, section 1). (N1) the 14 tests take 21.7 s and the gate form went from about 33 s to about 57 s on macOS: every load reads the three real Walmart PDFs, 3.6 s each, and the `cmd_plan` test 7.5 s. One real-file load is the requirement; the rest can share it or use `tests/unit/_text_pdf.py`. A tester-only change |
| 149 | `test_build_ebit_reconciliation_handles_none_inputs` locks in a fallback: `None` statements give `[]` | **silent, in `tests/`, and it guards a rule 3 shape** | `tests/unit/test_p3e_reconciliation_years.py:495-500`, against `api/routes_valuation.py:326-327` | **new, the overall lead, 2026-10-08, found while answering the user's question about the subagents' work, and missed at the `P3e-reconciliation-years` acceptance.** The test asserts `_build_ebit_reconciliation(None, None) == []`, and the same with either side `None`. That pins the branch `if raw is None or adjusted is None: return []`, a presence test with an empty branch, which is one of the five faces of rule 3 in `docs/2-rules/rules.md`. Both callers (`api/routes_valuation.py:462` and `:707`) pass statements the route assigned a few lines above; whether `None` can reach the function was not measured. `.claude/agents/tester.md` forbade a test that asserts a fallback, and the tester wrote one anyway; nothing reviewed the test. Fix: delete the test (a tester change), and decide in the same unit whether the branch should stop and name the missing statements or be deleted as unreachable (a programmer change in `api/routes_valuation.py`). The search in `docs/5-testing/strategy.md`, section 2, finds the three lines |
| 148 | `test_mutation_probe_simulating_raw_years_alone_omits_adjusted_only_year` calls no production code, so it cannot fail | **silent, in `tests/`** | `tests/unit/test_p3e_reconciliation_years.py` (the last test) | **new, the overall lead's review of `P3e-reconciliation-years`, 2026-10-08, note N1.** It builds two `FinancialStatements` and asserts facts about Python sets; it never calls `cli.print_normalization` or `_build_ebit_reconciliation`. Measured: it **passes under the mutant** (`years = raw.years`) that the file's other six tests kill. Its docstring says it proves criterion 3, which the other six do. `docs/5-testing/strategy.md:16` names the shape. Harmless today, misleading to the next reader. Fix: delete it, or make it call `cli.print_normalization`. A tester-only change |
| 147 | `.claude/check_guard.py` run from inside a worktree reports 52/60: its 8 worktree cases assume the main checkout is the project | — | `.claude/check_guard.py`, possibly `.claude/hooks/guard_paths.py` | **new, the overall lead, 2026-10-08, setting up the macOS worktrees.** From `Valuation/` the check is **60/60**. From `Valuation-wt/team-a`, with the same interpreter, it is **52/60**, and the 8 wrong cases are all "in a worktree" cases, each `want deny got allow`: tester into `analysis/` and `models/`, programmer into `tests/`, the guard itself, `STATUS.md`, `INDEX.md`, the code reviewer, the Bash tripwire. Not measured: whether that is the check building its scratch worktree from the wrong root, or the guard missing a sibling worktree when the project is itself a worktree. **The second would matter only to a Claude Code session opened inside a worktree.** No Claude session builds in the pilot, and no Claude hook runs for Antigravity, so it does not block the pilot. Run the check from the main checkout |
| 146 | `session_extraction plan` writes an absolute PDF path into a session file, so a tracked session file works in one checkout on one machine | **silent, in `tests/`** | `ingestion/session_extraction.py:873-875` (`cmd_plan`, `str(Path(pdf).resolve())`) | **new, the overall lead, 2026-10-08, on the move back to the macOS machine.** `extractions/WMT.json` was written on the Windows machine and carried `C:\Users\LiuYinchen\Valuation\10K_filings\WMT\…` in all three `pdf_path` values. On macOS the two tests that read it skipped: `tests/unit/test_p14d_finance_leases.py:589` and `tests/unit/test_p14e_nri_dedupe.py:656`. In a Windows worktree the same paths resolve to the **main checkout's** PDFs, not the worktree's. **So item 117's closure held on one machine in one directory only.** The overall lead rewrote the three values to `10K_filings/WMT/<name>` (repo-relative), which `load_session_extraction` accepts: every page check, unit check and hash check passed on a scratch copy, and the two tests then ran and passed. **The cause is not fixed**: the next `plan` run writes an absolute path again. Fix: when the PDF is under the repository, record the repo-relative path, and resolve a relative path against the repository root, not the working directory. Item 117 named this widening on 2026-10-06 **Measured again 2026-10-08 at `fde3e98`, the reading half**: with the hand-made relative paths, `load_session_extraction` loads `extractions/WMT.json` from the repository root and stops from `/tmp` ("the PDF 10K_filings/WMT/… is not on disk"), because a relative path resolves against the working directory. **Assigned to `P15c-portable-session-paths`** (pilot team A) **CLOSED by `P15c-portable-session-paths` (`f8e8caa`, merged as `698fdb4`), 2026-10-08**: `cmd_plan` writes a PDF inside `config.BASE_DIR` as a repo-relative POSIX path, and the loader resolves a relative `pdf_path` against `config.BASE_DIR`; an absolute path still loads, and a missing PDF names the recorded and the resolved path. Measured on `main`: `extractions/WMT.json` loads 3 filings with no failed check from `/tmp` as from the repository root |
| 145 | The stream-handler stop in `naming_unencodable_characters` names the stream by `repr`, and on Python 3.11 and 3.12 that `repr` hides a subclass | **stopping, on macOS: the gate form is red** | `ingestion/session_extraction.py:1230-1233` | **new, the overall lead, 2026-10-08, on the move back to the macOS machine (Python 3.11.6).** `tests/unit/test_session_extraction_console.py::test_a_handler_that_is_not_a_name_stops_and_names_the_value_and_the_stream` fails at line 774: the message ends `Stream: <_io.TextIOWrapper encoding='cp1252'>` and the test asserts the subclass name `HandlerIsNotAName`. Measured: `repr()` of an `io.TextIOWrapper` subclass prints `_io.TextIOWrapper` on 3.11.6 and on 3.12.7, and the test passes on the Windows machine's 3.14.4. So the gate form on macOS is **1 failed** at seeds 7, 1234 and 99. Assigned to `P1h-mac-gate`: the message names `type(stream)` itself; the test does not change **CLOSED by `P1h-mac-gate` (`3b1225d`, `c227cc0`, merged as `d13be2d`), 2026-10-08**: the message reads `Stream: {type(stream).__name__} {stream!r}`. The gate form on macOS is **1606 passed, 0 failed, 0 skipped** at seeds 7, 1234 and 99. Round 1's three new tests asserted that `repr()` hides the subclass, which is false on Python 3.13+; round 2 removed those lines, and the tests now kill the mutant under both `repr` forms. Built by Antigravity build lead A in a worktree |
| 144 | The seal needs the mods layer, because `SubagentStart` and `SubagentStop` do not fire for background agents | **silent, and a guard the repository believes is live is not** | `.claude/settings.json`, a plugin with a hooks module that does not exist yet | **new, the overall lead, 2026-10-08, after item 143's configuration half was fixed and measured.** With `SubagentStart` and `SubagentStop` correctly configured and both hooks instrumented to record before any exit, one real background subagent was dispatched and allowed to finish: **the state file was never created**. Running both hooks by hand with the same payload shape writes it, so the scripts are not at fault. **Every dispatch this repository makes is a background one**, so the seal cannot be reached by a settings hook at all. **The documented alternative is the mods layer's `agent.spawn` event**, which fires when a subagent is about to start and carries `e.isTeammate`. It needs a `.claude-plugin` directory with a hooks module, not a shell command, so it is a different kind of build from everything in this repository so far. **Before building it, test the cheap thing first**: dispatch one **foreground** subagent and see whether the two events fire there. If they do, the limitation is background-only and the finding should go to https://github.com/anthropics/claude-code/issues with the measurement attached. **Not a blocker on the worktree pilot**: the write guard is a separate hook on a separate event and it does fire |
| 143 | **Neither seal hook has ever fired on this harness.** `PreToolUse` on `Agent` and `SubagentStop` are configured, and the write guard's `PreToolUse` on `Write|Edit|Bash` does fire, so the seal alone is dead | **silent, and a guard the repository believes is live is not** | `.claude/settings.json` (the `PreToolUse` matcher `Agent|Task|SendMessage`, and the `SubagentStop` block), `.claude/hooks/seal_baseline.py`, `.claude/hooks/seal_check.py` | **new, the overall lead, 2026-10-08, found while building `P1f-worktree-guards` and confirmed three ways.** (1) After a real `Agent` dispatch, `.agent/.seal-baseline.json` did not exist. (2) `in_flight` was left at 1 on purpose before a review ran: had `seal_check.py` fired at that `SubagentStop` it would read 0. It still read 1. (3) `P1f` round 2 added an instrument, `last_dispatch_seen`, written **before any exit in `main`** precisely so that "the hook ran and exited early" could be told from "the hook never ran". After the next real dispatch it is **ABSENT**. So the cause is not inside either hook: **they are not invoked.** **The hook chain is not at fault and that was checked separately**: `seal_baseline.py` run directly writes the file, and so does `sh run_hook.sh seal_baseline.py`. **The write guard is unaffected** and its own `PreToolUse` matcher does fire, which is why role separation has held. **What this costs:** `.agent/journal/INDEX.md`, `STATUS.md` and `.claude/hooks/` have been unsealed for every subagent run in this repository, and `AGENTS.md` and `STATUS.md` both describe the seal as live. **Two candidates to test, in order:** `SubagentStart` is a hook event this harness lists, and it fires per subagent, so it is a better home for the baseline than `PreToolUse` on `Agent` and would pair exactly with `SubagentStop` — giving the per-agent key item 141 could not have; and `seal_check.py` exits at `agent_type not in ROLES`, so if the `SubagentStop` payload carries no `agent_type` the hook may be running and exiting silently, which the same kind of instrument would settle. **`P1f-worktree-guards` does not close this** and does not claim to: it repairs what the hooks do when they run  **DECIDED by the user on 2026-10-08: close this BEFORE deploying the multi-worktree team scheme.** It was offered against the alternative of deploying with the seal known-dead and named, and that was not taken. **The fact behind the choice**: three teams in three worktrees is the first time this repository will run more than one agent in flight, which is the exact condition the seal exists to cover and has never been tested under, because it has never run at all. Assigned as `P1g-seal-wiring`, which starts once `P1f-worktree-guards` is accepted  **CAUSE FOUND, 2026-10-08, with documentation rather than by guess.** `PreToolUse` filters on **tool names only**, and `Agent`, `Task` and `SendMessage` are **not tool names**. So the second `PreToolUse` block could never match anything, whatever its script did. That is the baseline half, settled: it is a configuration error, not a harness defect, and not a fault in `seal_baseline.py`. **`SubagentStart` and `SubagentStop` are the correct events**, and the documented payload for both carries `agent_type` **and `agent_id`, an identifier common to a subagent's start and its stop**. **That is better than the fix item 141 settled for.** `P1f-worktree-guards` counted agents in flight because no identifier was available at dispatch time, and accepted a deliberate false positive as the price: the second agent is judged against the state before the window opened, so it can fire for the first agent's write. **`agent_id` removes that price**, because each agent can be keyed to its own snapshot. **One thing is NOT settled and must be measured, not assumed.** Whether these two events fire for **background** agents is undocumented, and every dispatch in this repository is a background one. The `SubagentStop` block IS configured and has never fired, but `seal_check.py` exits at `agent_type not in ROLES` **before** it decrements, so "fired with an `agent_type` this repository does not expect" looks identical to "never fired". **The unit must instrument both hooks before any exit, the way `P1f` instrumented the dispatch side, and then dispatch one agent and read what landed.** A fallback exists if the events turn out not to fire for background agents: the mods layer has an `agent.spawn` event, which needs a hooks module rather than a shell command  **HALF CLOSED by `P1g-seal-wiring`, 2026-10-08, and the other half is measured and cannot be closed from a settings file.** The configuration is now correct: `seal_baseline.py` moved from the invalid `PreToolUse` matcher to **`SubagentStart`**, `seal_check.py` stays on `SubagentStop`, and both hooks now record what they were sent **before any exit** (`last_dispatch_seen` and `last_stop_seen`). Both run correctly by hand with a realistic payload. **Then the decisive test, and it failed.** The baseline file was deleted, one real background subagent was dispatched and allowed to finish, and the file **was never created**. So with the documented event names, **neither `SubagentStart` nor `SubagentStop` fires for a background agent**, and every dispatch this repository makes is a background one. **That matches the one thing the documentation does not state.** The events are documented, their payloads are documented as carrying `agent_type` and `agent_id`, and whether they fire for background or async agents is not documented at all. **What is left is not a settings change.** The remaining route is the mods layer, whose `agent.spawn` event fires when a subagent is about to start. That needs a plugin with a hooks module rather than a shell command, which is a different kind of build. Recorded as item 144. **What this costs, stated plainly: the seal has never worked and still does not.** `.agent/journal/INDEX.md`, `STATUS.md` and `.claude/hooks/` are unsealed for every subagent run. **The write guard is unaffected and does fire**, which is why role separation has held throughout, and `P1f-worktree-guards` extended it into worktrees |
| 142 | **The write guard is off inside a git worktree**: every path outside `CLAUDE_PROJECT_DIR` is allowed without a role check | **silent, and it disarms the guard** | `.claude/hooks/guard_paths.py:218-221` | **new, the overall lead, 2026-10-08, measured while answering the user's question about running agent teams in worktrees.** `main()` computes `project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)`, then for each write target does `rel = repo_relative(candidate, project, cwd)` and, when `rel is None`, `continue` with the comment "outside the repository: scratch space, allowed". **A git worktree lives outside the project directory, so every write in one is `rel is None`.** Measured by executing the hook on two payloads with the same role and the same repo-relative target: a `tester` writing `analysis/dcf.py` **inside** the project is denied with "The `tester` agent may write only `tests/**`, `.agent/journal/**`", and the same `tester` writing `<worktree>/analysis/dcf.py` produces **no output at all** and exit 0. **So in a worktree a tester may rewrite the code it judges**, which `AGENTS.md` calls out as the thing the split exists to prevent: "This is enforced by permission, not by good intentions." In a worktree it is back to good intentions. **The `rel is None` branch is correct for its purpose** — scratch trees under `C:\tmp` must stay writable — so the fix is not to delete it but to teach the hook which outside paths are worktrees of this repository: `git worktree list --porcelain` names them, and a target under one of those should be made relative to that worktree root and then checked exactly as an in-repository path is. **Not reached today**: this repository has never run an agent in a worktree. **It is a hard blocker on any multi-worktree team scheme**, together with item 141  **ASSIGNED as `P1f-worktree-guards` on the user's decision of 2026-10-08, option `a`: build the guard fixes before switching to a multi-worktree team scheme.** It waits for `P1e-test-order`. **The unit cannot be given to a programmer subagent and that is by design**: `.claude/hooks/*.py` is `ALWAYS_DENIED`, measured — a `programmer` writing `guard_paths.py` is refused with "a subagent does not edit the permissions that bind it". The overall lead implements; a code reviewer still reviews; a tester covers it from `tests/`, because `.claude/check_guard.py` is closed to it too  **CLOSED by `P1f-worktree-guards`, 2026-10-08.** `worktree_root_of` finds a worktree by **reading that tree's `.git` file** -- a linked worktree's `.git` is a file holding `gitdir: <project>/.git/worktrees/<name>` -- so the guard runs no subprocess and does not need git on `PATH`. **The first shape did shell out to `git worktree list` and the code reviewer found two faults with it**: once per candidate path rather than once per process (1,059 ms for six targets), and with no git on `PATH` it failed open **silently**, which put this item back under a condition nobody would notice. Reading the file closes both: six outside targets now cost 799 ms, and `PATH=""` still denies. **`.claude/check_guard.py` went from 48 to 60 cases**, the 12 new ones being worktree cases, and its `ask()` no longer runs the guard with `PATH: ""` -- with git unreachable all 12 would have passed as "allow" for the wrong reason. It now **fails rather than skips** when the worktree cannot be built, because a guard check that silently drops its newest cases is backlog item 140's shape. Three mutants priced the cases: revert **52/60**, over-tighten **56/60**, over-deny **57/60** |
| 141 | The seal keeps one baseline file for the whole session, so a second subagent dispatched while a first is still running overwrites the snapshot the first will be judged against | **silent, and it disarms a guard** | `.claude/hooks/seal_baseline.py` (`BASELINE = Path(".agent/.seal-baseline.json")`), `.claude/hooks/seal_check.py:45` | **new, the overall lead, 2026-10-08, found while answering the user's question about running subagents in parallel.** `seal_baseline.py` runs on `PreToolUse` for `Agent`, `Task` and `SendMessage` and writes **one** path, `.agent/.seal-baseline.json`. `seal_check.py` runs on `SubagentStop` and reads that same one path. **With one subagent in flight that is exactly right**, and the hook's own docstring explains why a dispatch-time snapshot is needed rather than a comparison against `HEAD`: the orchestrator writes `.agent/journal/INDEX.md` and `STATUS.md` **after** a subagent returns, so a `HEAD` comparison would accuse every subagent of the orchestrator's own write. **With two in flight it inverts.** Dispatch A writes snapshot S1; dispatch B overwrites it with S2; A then stops and is checked against S2. Anything A wrote to a sealed file between S1 and S2 is **already inside S2**, so the check sees no difference and A is cleared. The failure is a **false negative**: the seal stops catching the one thing it exists to catch, and says nothing. **The three sealed things are `.agent/journal/INDEX.md`, `STATUS.md` and `.claude/hooks/` itself**, the last being "the guard a subagent must not be able to disarm", so the defect is in the guard that guards the guard. **Not reached today**: this repository has run one subagent at a time throughout, and `.agent/QUEUE.md`'s one-unit rule is why. Fix: key the baseline by the subagent, not by the session — one file per in-flight agent, named from whatever identifier the hook payload carries, and have `seal_check.py` read the one belonging to the agent that stopped. **Until it is fixed, dispatching a second subagent while one is in flight weakens the seal on the first**, which is the overall lead's own constraint and not only a build-team one  **ASSIGNED as `P1f-worktree-guards` on the user's decision of 2026-10-08, option `a`: build the guard fixes before switching to a multi-worktree team scheme.** It waits for `P1e-test-order`. **The unit cannot be given to a programmer subagent and that is by design**: `.claude/hooks/*.py` is `ALWAYS_DENIED`, measured — a `programmer` writing `guard_paths.py` is refused with "a subagent does not edit the permissions that bind it". The overall lead implements; a code reviewer still reviews; a tester covers it from `tests/`, because `.claude/check_guard.py` is closed to it too |
| 140 | Mutation M4 is caught only by two tests that need a filing the repository does not hold | **silent, in `tests/`** | `tests/unit/test_p14g_unit_statement_pages.py`, the two tests reading `10K_filings/WMT/` | **new, the `P14g-unit-statement-pages` tester's F2, 2026-10-07.** M4 is `_unit_statement_failures` skipping its "printed on its page" check once the page is allowed, which is the mutation that would make `P14g`'s whole widening worthless: the new page would be allowed without being checked. Two tests kill it and **both need the real Walmart fiscal 2024 PDF**. On a clean checkout, which holds no `10K_filings/`, those two skip and `pytest -q` reports only `2 skipped`, so the guard is absent and nothing says so. **This is item 117's shape in a new place.** Fix: a synthetic fixture, which the tester says is one line away from the known hole's fixture — and that is why it did not build it, because the two shapes differ by exactly the thing item 138 must decide. **The overall lead proved the consequence at acceptance rather than record it on report.** In a scratch copy it applied M4 — `elif unit_statement_on_page(printed, text):` replaced by `elif True:` — and ran the two test files: **2 failed, 155 passed**, the two being `test_walmart_fiscal_2024_the_newly_allowed_page_is_still_checked` and `…_refusals_that_must_survive_the_widening[text-not-printed-there]`. It then renamed `10K_filings/` away, which is what a clean checkout looks like, and re-ran the same mutant: **149 passed, 8 skipped, 0 failed.** The mutation that makes the whole widening worthless survives the suite in silence on any machine without the filing  **CLOSED at `32b3f06`, 2026-10-08**, on the user's instruction: `10K_filings/` is now tracked, so the two tests that kill M4 run on every checkout. The fix is not the synthetic fixture this item asked for — it is that the repository now holds the filing, which removes the cause rather than working around it. A worktree carries it too: measured on 2026-10-08, a fresh worktree ran `tests/unit/test_p14g_unit_statement_pages.py` at **113 passed** against the real Walmart PDF |

---

## 1. 116 silent zero-default sites · **silent**

**Fact.** Reproduce:

```
grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" \
  --include=*.py models analysis api ingestion | wc -l
```
→ **116** at `6cf34d3`, unchanged since `38b903c`. By area: `models/` 60, `ingestion/` 49, `analysis/` 5,
`api/` 2.

| Commit | Count | The delta |
|---|---|---|
| `bc19431` | 119 | — |
| `d1854fb` | 117 | the two dead fields in the deleted `models/company.py` |
| `38b903c` | 116 | one `changes.get(field, 0.0)` rewritten by `P4-normalizer` |

**The grep excludes `tests/`, and `tests/` is not clean.** The nine scripts hold 33
more hits of the same shape. They are dev scripts, not pipeline code, and
[5-testing/strategy.md](../5-testing/strategy.md) already says they are not evidence of
correctness — but the figure must not be read as saying `tests/` has none.

**A comment can inflate this number.** `P4-normalizer`'s first draft carried an
explanatory comment quoting the old code; the grep counted it and held the count at
117. The programmer reworded it, on the grounds that a measurement that counts a
comment is not a measurement. **Check any future delta against the diff, not the
count.**

**What it costs.** A zero meaning "we did not extract this" is the same bytes as a zero
meaning "this is zero". Because every dataclass money field defaults to `0.0`, an
extraction that returned **nothing at all** flows through all eight pipeline steps and
renders a share price. Nothing anywhere reports that no data arrived.

### It is worse than "it produces zeros" · measured 2026-09-21

That description, written at `bc19431`, understated it. Measured independently by the
programmer and the reviewer of `P2b-provider`, on one-line PDFs printing a single
figure:

| The page printed | `other_operating_activities` came back as |
|---|---|
| `4321` | **`-4321.0`** |
| `6174` | **`-6174.0`** |
| `2718` | **`-2718.0`** |

`ingestion/claude_extractor.py:637` computes a residual,
`cfo - net_income - da - sbc - delta_wc`, over inputs that each defaulted to `0.0`.

**So item 1 does not merely produce zeros. It produces a signed, correctly-scaled
figure that tracks the filing and that a reader cannot distinguish from a
measurement.** A zero at least looks like an absence. This does not.

It is also the clearest possible answer to `STATUS.md` trap 3: the run produced a
number that moved with the document, and the number was still an artefact.

**Fix.** Make the money fields required, or introduce a sentinel that arithmetic
refuses. Then convert the `.get(k, 0)` calls in the parser into a validation pass that
names every absent field at once. [Rule 3](../2-rules/rules.md).

**Note the ordering.** Fixing item 1 without item 4 in place means no test detects the
regression it causes. Do 4 first.

## 2. Missing balance sheet gives zero net debt · **CLOSED by `P10a-nci-bridge`**

**Closed 2026-10-02.** `run_dcf` now stops when the latest year has no balance sheet, and
names net debt, cash and the noncontrolling interests it cannot read. The two
`if latest_bs else 0.0` lines are deleted. The red test moves into `test_dcf.py` in
`P10-tests`. The history below is kept as the record.


**Fact.** `analysis/dcf.py:80-81`:

```python
net_debt = latest_bs.net_debt if latest_bs else 0.0
cash = latest_bs.cash_and_equivalents if latest_bs else 0.0
```

`get_balance_sheet(latest_year)` returns `None` whenever the B/S was not extracted for
that year — which is routine, because `extract_multi_year()` takes the balance sheet
**only from the most recent filing**.

**What it costs.** Equity value is `EV − net_debt`. With `net_debt = 0`, equity value is
overstated by the **entire debt balance**. For a company with $100bn of net debt and 12bn
shares, that is $8.33 added to the implied share price, silently, on a clean run.

**This was called the highest-cost silent defect in the repository at `bc19431`. It is
no longer.** Item 19 outranked it — now closed — and **item 20 outranks it today**,
because a NaN reaches the share price through the same function's one working guard.
Item 2 still needs a missing balance sheet; item 20 does not.

**Fix.** Raise, naming the year and the missing statement.
`tests/unit/test_dcf_rule3_red.py` already states the requirement and is red.

## 3. Unknown NRI line item guesses a field · **CLOSED at `38b903c`**

**Was.** `analysis/normalizer.py:46-47` printed a line to stdout and returned
`other_operating_expense` for any label it did not recognise. The list holds 20
spellings and filings use many more, so the adjustment landed on the wrong income
statement line, moving operating margin, every projected year, and the share price. The
only signal was a `print` the web app never displayed.

**Now.** `_resolve_field` raises `ValueError`, naming the unrecognised label and the
year:

```
Unrecognised line_item 'Goodwill impairment charge' on the 2023 non-recurring item…
```

The `print` is deleted. Locked by a test that was written red, went green, and now
lives in `tests/unit/test_normalizer_stops.py` inside the gate — see **item 24** for
why that move was needed.

## 4. No test suite; `pytest` cannot collect · **CLOSED at `d1854fb`**

**Was.** At `bc19431`: 0 `assert` statements and 0 `__main__` guards across 10 files,
so every one ran its whole pipeline at **import**, and `pytest` made paid API calls
during collection and failed before a test ran.

**Now.** Unit `P1-suite` wrapped all nine scripts in `def main()` behind an
`if __name__ == "__main__":` guard, and added `tests/unit/`.

Units `P1b-arith` and `P1c-flow` then took the other five `analysis/` modules.

| | `bc19431` | `38b903c` |
|---|---|---|
| `assert` statements | 0 | **263** |
| guarded scripts | 0 | **9 of 9** |
| tests collected | 0 | **93** |
| `pytest -q` | 3 collection errors | 92 pass, 1 red on purpose, 3.8 s |
| paid calls during collection | attempted | **none** |
| `analysis/` statement coverage | 0 of 194 | **202 of 202 — 100%** |

**What is still open.** `ingestion/` and `api/` have **no tests at all.** That is where
51 of the 116 zero-default sites live, and where the extraction boundary sits. Coverage
of `analysis/` being complete says nothing about either.

**One test is red on purpose.** `tests/unit/test_dcf_rule3_red.py` states item 2's
requirement. It goes green when item 2 is fixed, and it is **kept, not deleted**. Until
then the phase-1 gate is
`pytest -q --ignore=tests/unit/test_dcf_rule3_red.py` → `19 passed`.

## 5. Module-global extraction cache, popped on use · mixed

**Fact.** `api/routes_valuation.py:25`:

```python
_extraction_cache: dict[str, FinancialStatements] = {}
```

Written at line 87, read at line 133 with `.pop()`.

**Three separate problems:**

| | |
|---|---|
| **Shared across users** | process-global. Two people valuing different companies share one dict, keyed by a file-path string |
| **Popped on read** | a page refresh on the results page is a cache miss, and re-runs the whole paid LLM extraction |
| **Unbounded** | anyone who visits `/assumptions` and never submits leaves an entry forever |

**Fix.** A keyed, size-bounded, per-session store that reads without removing.

## 6. Falsy treated as missing, five times · **silent**

**Fact.** `api/routes_valuation.py:150-154`:

```python
operating_margin=operating_margin / 100 if operating_margin else None,
tax_rate=tax_rate / 100 if tax_rate else None,
da_pct_revenue=da_pct / 100 if da_pct else None,
capex_pct_revenue=capex_pct / 100 if capex_pct else None,
nwc_pct_revenue=nwc_pct / 100 if nwc_pct else None,
```

**What it costs.** `None` means "use the historical average". `0` is falsy. So a user who
deliberately enters a 0% ΔNWC — entirely reasonable for a working-capital-neutral
business — gets the historical average instead, and the form silently ignored them.

**Fix.** Test `is not None`, and make the form send an empty string for "not supplied".

## 7. `cli.py` and `api/` duplicate the pipeline · **silent**

**Fact.** `cli.py:667-722` calls `normalize_financials`, `derive_assumptions`,
`fetch_price_data`, `run_capm`, `calculate_wacc`, `project_fcffs`, `run_dcf` — the same
seven calls as `api/routes_valuation.py:139-207`, wired separately.

**What it costs.** A fix applied to one is not applied to the other. A figure verified in
the CLI is not verified in the web app. `cli.py` is 760 lines and already the second
largest file in the repository.

**Fix.** Extract one `run_pipeline(financials, overrides) -> DCFResult` that both call.
The CLI keeps its printing layer; the route keeps its form parsing. **Do this before
fixing items 1, 2 or 3**, or each fix must be made twice.

## 8. Blanket `except Exception` at four sites · **silent**

**Fact.**

```
api/routes_valuation.py:96    BLE001
api/routes_valuation.py:220   BLE001
cli.py:758                    BLE001
ingestion/claude_extractor.py:795  BLE001
```

`routes_valuation.py:220` wraps the **entire** eight-step pipeline and renders
`str(e)` into the results template.

**What it costs.** Every failure mode collapses into one string. A missing API key, a
network timeout, a malformed PDF, and an `AttributeError` from item 11 are
indistinguishable to the user and to the log. It also converts the typed stops this
backlog asks for into the same undifferentiated string, which would undo the value of
fixing items 1 to 3.

**Fix.** Named exception types per failure class, per the four outcomes in
[AGENTS.md](../../AGENTS.md): `input_error`, `spec_incomplete`, `invariant_violation`.

## 9. Unlabelled cost-of-debt assumption · **silent**

**Fact.** `analysis/wacc.py:41-43`: when `total_debt > 0` and `interest_expense == 0`,
returns `config.DEFAULT_COST_OF_DEBT` = 4.0%.

**What it costs.** The substitution reaches WACC, every discounted cash flow, and the
share price. **Nothing in the output records that it happened.** A reader cannot tell a
measured cost of debt from a 4% guess.

This one is defensible as behaviour and indefensible as silence. [Rule 6](../2-rules/rules.md)
asks only that it be labelled.

**Fix.** Return the value with a flag, and show it on the result page as an assumption
with its source.

## 10. D&A subtraction buried in the parser · **silent**

**Fact.** `ingestion/claude_extractor.py:479`:

```python
other_operating_expense=float(yr.get("other_operating_expense", 0))
                       - float(yr.get("depreciation_amortization", 0)),
```

**What it costs.** This is a real accounting decision — whether the filing's "other
operating expense" already includes D&A — taken silently inside a **parser**, on two
values that each default to zero. It changes EBIT. It belongs in `analysis/`, with its
reasoning written down, and it must stop rather than default.
[2-rules/llm-boundary.md](../2-rules/llm-boundary.md) records it too.

## 11. 33 type errors, one a live crash path · stopping

**Fact.** `mypy models analysis ingestion api config.py app.py --ignore-missing-imports`
→ 33 errors in 4 files. By kind: 16 `union-attr`, 11 `arg-type`, 4 `assignment`, 2 other.
By file: `claude_extractor.py` 16, `routes_valuation.py` 12, `routes_upload.py` 4,
`projector.py` 4.

**One is a real defect, not a typing nicety:**

```
api/routes_valuation.py:190: Argument "balance_sheet" to "calculate_wacc"
  has incompatible type "BalanceSheet | None"; expected "BalanceSheet"
```

When the balance sheet is absent, `calculate_wacc` raises `AttributeError` on
`None.total_debt` deep in the valuation, and item 8's blanket catch renders the
traceback message as the user-facing error.

The 16 `union-attr` errors are the same shape as item 2: an `X | None` used without
checking. **Treat the mypy count as a proxy measurement for rule 3 coverage.**

## 12. Dead code and repository hygiene · **mostly closed at `d1854fb`**

| Item | State |
|---|---|
| `models/company.py` is dead | **closed** — deleted |
| `BalanceSheet` imported but unused, `analysis/fcff.py:20` | **closed** |
| `.DS_Store` tracked, twice | **closed** — untracked with `--cached`; both files remain on disk |
| 2 pickles tracked under `cache/` | **closed** — untracked with `--cached`; both remain on disk |
| **3 pickles tracked under `tests/`** | **open, deliberately.** Three scripts read them. Loading a pickle **executes code in it** |
| `.gitignore` lists `CLAUDE.md`, which is tracked | **closed** — the inert line is gone, with a note saying why |
| `.gitignore` misses the cache dirs | **closed** |
| `config.py` creates a directory at **import** | **closed** — the `mkdir` moved into `api/routes_upload.py`, where the file is written. Verified by execution: importing `config` creates nothing |
| `price_fetcher.py` imports pandas twice | **closed** |
| 45 lint errors across the repository | **closed down to 5**, all of them item 8 |
| `datetime.today()` without a timezone | **closed** — and the fix had to stay naive; see below |
| **`yfinance` imported inside a request handler**, `api/routes_valuation.py` | **open.** See below — the import location is the smaller half of the problem |
| **a redundant local `import re`**, `ingestion/claude_extractor.py:389` | **open.** Shadows the module-level import at line 60. Harmless, one line to delete |

### The `DTZ002` fix had to stay naive, and that is not laziness

`ingestion/price_fetcher.py` passes its date to yfinance, and
`yfinance/utils.py:454` branches on whether the datetime carries a timezone:

```python
if dt.tzinfo is None:
    dt = _pd.Timestamp(dt).tz_localize(exchange_tz)   # wall-clock kept, instant moves
else:
    dt = _pd.Timestamp(dt).tz_convert(exchange_tz)    # instant kept, wall-clock moves
```

So the idiomatic aware replacement would have shifted **both** lookback boundaries by
the UTC offset, changing the price window and therefore beta, CAPM and the share
price. The form used is `datetime.now(UTC).astimezone().replace(tzinfo=None)`, which is
wall-clock identical to `datetime.today()` on any machine by construction.

**Anyone tempted to "clean this up" into an aware datetime is about to move a number.**

### `api/routes_valuation.py:184` holds two defects, not one

```python
info.get("sharesOutstanding", 0)
```

- **Rule 5** — a financial figure sourced from yfinance rather than the filing, behind
  an inline import, mid-pipeline.
- **Rule 3** — a `.get` with a zero fallback, on the **denominator** of the headline
  share price.

They sit on one line and should be fixed in one unit.

## 13. Provider changes with the number of PDFs uploaded · **silent**

**Fact.** Three defaults disagree:

| Function | Default provider |
|---|---|
| `extract_financials` — `ingestion/claude_extractor.py:848` | `"gemini"` |
| `extract_multi_year` — `ingestion/claude_extractor.py:901` | `"claude"` |
| `cli.py --provider` — `cli.py:93` | `"gemini"` |

`api/routes_valuation.py:_extract_from_files` (`:40-57`) calls the first for one filing
and the second for several, and passes **no** `provider` argument in either branch.

**What it costs.** Uploading one PDF uses Gemini. Uploading two uses Claude. That is a
different model, requiring a different API key, producing different extracted figures
for the same company — with nothing in the interface indicating which ran.

The most likely symptom is not a wrong number but a confusing failure: a user with only
`GEMINI_API_KEY` set gets a working single-file upload and an
`ANTHROPIC_API_KEY is not set` error on the two-file upload, with no obvious reason why.

**Correction, `d1854fb`.** An earlier revision of this item said
`_DEFAULT_MODELS["claude"] = "claude-sonnet-4-6"` "is not a current model ID". **That
was wrong.** `claude-sonnet-4-6` is a current, served model. It is previous generation
and priced above `claude-sonnet-5`, so there is a better choice, but the provider is
not broken for the reason stated.

**This item is now a blocker on the machine the build runs on.** Measured at
`d1854fb`:

| Fact | Evidence |
|---|---|
| `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` are both unset, and no `.env` exists | the environment; `ls .env` |
| Gemini is unreachable from this network | reported by the user, 2026-09-20 |
| Claude is reachable, **through Microsoft Foundry** | `ANTHROPIC_FOUNDRY_BASE_URL` and `CLAUDE_CODE_USE_FOUNDRY` are set |
| the installed `anthropic` 1.7.0 exports `AnthropicFoundry` | `dir(anthropic)` |
| `ingestion/claude_extractor.py:352` constructs a plain `anthropic.Anthropic(api_key=...)` | it cannot use the Foundry endpoint |
| `_resolve_provider` (`:830`) raises unless `ANTHROPIC_API_KEY` is in the environment | it would refuse a working Foundry credential |

**So extraction cannot run at all on this machine**, by either provider. A one-PDF
upload tries Gemini and fails; a two-PDF upload tries Claude and fails for a different
reason.

### The working path, proven by execution 2026-09-21

Every row was run, not read. This is what the fix must reproduce.

| Step | Result |
|---|---|
| `az login` is active | the user signed in |
| token for `https://cognitiveservices.azure.com/.default` | issued |
| token for `https://ai.azure.com/.default` | issued, then **rejected** by the gateway |
| the gateway's own 401 names the right audience | `"Ensure 'az login' is active and the token audience is https://cognitiveservices.azure.com."` |
| `AnthropicFoundry(azure_ad_token_provider=…)` with **no** `api_key` and **no** `resource` | picks `base_url` up from `ANTHROPIC_FOUNDRY_BASE_URL` |
| `claude-opus-5` and `claude-haiku-4-5` | both served, HTTP 200 |
| a base64 `document` block holding a one-line PDF | the model returned the figure printed on the page |

**That 401 message is the fastest diagnosis available for a wrong scope.** Record it
where someone will find it, rather than leaving it to be rediscovered.

**`azure-identity` is not installed.** It is the only supported way to produce a
refreshing Entra token; `get_bearer_token_provider(DefaultAzureCredential(), SCOPE)` is
the call. **Do not shell out to `az` from library code** — a subprocess is untestable
and breaks wherever the CLI is absent.

**PDF input is a beta feature on Microsoft Foundry**, per Anthropic's platform
availability table. It works today. A future failure there is a platform change, not a
defect in this repository.

**Fix.** One default provider, named once in `config.py`. Make `provider` explicit at
the route and the CLI boundary. Add Foundry as a **transport**, selected by the
presence of a base URL, not as a third provider — the model is still Claude. Then show
the resolved provider, model **and transport** in the output as an assumption,
[rule 6](../2-rules/rules.md). A figure read through a company gateway and one read
through the public API must be distinguishable by the reader.

---

## 14. Empty `projected_fcffs` raises a bare `IndexError` · **CLOSED at `ff632df`**

**Fact.** `analysis/dcf.py:73` — `final_fcff = projected_fcffs[-1].fcff`. Measured by
the tester: `IndexError: list index out of range`.

**What it costs.** It stops, which is half of [rule 3](../2-rules/rules.md). It names
nothing, which is the other half. Item 8's blanket catch then renders
`"list index out of range"` on the results page, where a named input error belongs.

**Fixed at `ff632df`.** `analysis/dcf.py` raises `ValueError` naming
`projected_fcffs`. Measured before and after by the reviewer:
`IndexError: list index out of range` → `ValueError: projected_fcffs is empty…`.

## 15. `latest_year` returns `0` for an empty extraction · **CLOSED at `aa6f80d`**

**Fact.** `models/financial_statements.py:295` — `max(self.years) if self.years else 0`.

**What it costs.** This is the silent upstream of item 2. An extraction that returned
nothing gives `latest_year = 0`; `get_balance_sheet(0)` returns `None`; `dcf.py:80`
supplies zero net debt; a share price comes out of a valuation holding no filing data
at all. Item 1 covers the field defaults, but this `else 0` deserves its own name
because it is what turns "no data" into "year zero" without an error.

## 16. Nine scripts point at a path that does not exist · stopping

**Fact.** Every script under `tests/` opens with

```python
sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")
```

That directory belongs to a different Windows user. Proven pre-existing: the tester ran
the **unmodified** `bc19431` file and got `ModuleNotFoundError: No module named 'ingestion'`.

**What it costs.** None of the nine runs as `python tests/<name>.py`. They work under
`pytest`, and under `python -m tests.<name>`, only because `tests/__init__.py` makes the
repo root resolve.

**Fix.** Delete the nine lines and document `-m tests.<name>` as the invocation, or
resolve the root from `Path(__file__)`. **Any done-criterion that says "run the script"
must use `-m tests.<name>` until this lands.**

## 17. `analysis/` imports from `ingestion/` · —

**Fact.** `analysis/capm.py:14` — `from ingestion.price_fetcher import PriceData`. The
only hit of `grep -rn "^from ingestion" analysis/ models/`.

**What it costs.** No rule forbids it, which is why it is small. It breaks the layering
this repository otherwise keeps: `analysis/` imports `models/`, `config`, the standard
library, numpy and scipy. A dependency pointing upward makes `analysis/` untestable
without the extraction layer present.

**Fix.** Move `PriceData` into `models/`, so both sides import downward.

## 18. The lint gate's rule set is unpinned · —

**Fact.** `ruff.toml` sets `target-version` and one `B008` per-file ignore. It sets no
`select`, so the enabled rules are ruff 0.16.8's built-in default.

**What it costs.** Unit `P2-hygiene` put a number on it: changing **only**
`target-version`, with no source edit, moved the error count from 4 to 5 and woke
`UP017`, which had been dormant repository-wide. A ruff upgrade can do the same, with
no commit to point at and no diff to review.

**Fix is not obvious, which is why this is recorded rather than done.** Writing out
today's rule set freezes out errors the repository has not met yet. Pinning the ruff
version in `requirements-dev.txt` is the cheaper half and has no such cost.

---

# Found by the test units, 2026-09-20

Items 19 to 23 were found by units `P1b-arith` and `P1c-flow`, and confirmed
independently by their reviewers. **None was found by reading.** Each needed a test to
call the function with inputs nobody had tried.

# Found by the first run against a real filing, 2026-09-22

Three L3Harris 10-Ks (FY2023, FY2024, FY2025 — 506 pages) were supplied by the user.
The FY2025 filing was extracted by `claude-opus-5` through the Foundry gateway:
272,204 input tokens, 77 seconds, and the figures trace to the printed page —
`Revenue $ 21,865 $ 21,325` on page 23 is what the extraction returned for 2025 and
2024.

**The pipeline works. The number it produces is not yet trustworthy, and items 33 to 35
are why.**

## 37. The new zero-debt stop states an inference as a fact · —

**Fact.** `analysis/wacc.py` now stops when a filing reports interest expense with a
zero debt balance, and its message says a company that pays interest **has** debt, so
the balance "did not extract".

**That is an inference, not a fact.** Interest expense is a **flow** over the year;
`total_debt` is a **stock** at the closing instant, and is exactly
`short_term_debt + current_portion_lt_debt + long_term_debt`
(`models/financial_statements.py:187-188`). Two ordinary filings produce the pair:

- a company that repaid its borrowings before the balance sheet date reports a full
  year of interest beside a zero closing balance;
- **`BalanceSheet` has no lease-liability field at all** — verified independently by
  two agents, `grep -in "lease" models/financial_statements.py` returns nothing — so
  finance-lease interest can never reach `total_debt` by construction.

**The stop itself is right and must stay.** The pattern is *ambiguous*, not impossible,
and the two readings imply different costs of capital. [Rule 3](../2-rules/rules.md)
says stop rather than guess between them; the old `return 0.0` guessed.

**Fix.** Message only. Name **both** readings instead of asserting one. The reviewer
verified that 23 of 23 `wacc` tests stay green with the rewrite, and no test pins the
wording.

**One thing neither the tester nor the programmer spotted**, found by the reviewer:
`CashFlowStatement.debt_repaid` exists at `:243-244`. **The schema already carries the
evidence that would disambiguate the two readings.** That is a future signature
widening, not a guess available today — but it means this stop could one day become a
decision.

## 38. A 100% equity weighting is fabricated when market cap and debt are both zero · **CLOSED at `47b8b09`**

**Fact.** `analysis/wacc.py:215-223`. When `market_cap + total_debt == 0` the function
returns `equity_weight = 1.0, debt_weight = 0.0` instead of stopping. A company with no
market value and no debt is missing data, not a wholly equity-financed company.

**This is item 22's weights half**, and it has a second face the programmer of
`P6-honest-output` found: a **supplied** `--cost-of-debt` with a missing balance sheet
still gets a zero debt weight, so the rate the user explicitly provided vanishes from
the calculation entirely.

**Measured cost of fixing it**, by the reviewer on a patched scratch tree: exactly one
test fails, `test_cost_of_equity_survives_a_company_with_no_market_cap_and_no_debt`,
which requires the call to return. **No test pins the fabricated weights themselves.**

**It was blocked and is now unblocked.** The fixture that paired interest expense with a
zero debt balance is gone, so a guard added here no longer collides with it. Verified:
`1 failed, 145 passed` with the guard inserted. **Safe to dispatch.**

## 39. `confidence` still defaults to the strongest reading in `models/` · **CLOSED at `aa6f80d`**

**Fact.** `models/financial_statements.py:28` — `confidence: str = "high"`.

`7354698` removed the same optimistic default from the parser, which now stops on a
missing tag. **The reviewer established that no path a user can reach constructs a
`NonRecurringItem` without a confidence**, so the user's decision is fully in force
today. This is the last place where absence becomes the strongest reading, and it is a
type-level gap rather than a live one.

**Fix.** Make the field required, or default it to `low`. Needs a `models/` unit with a
tester, because `models/valuation.py` and `models/financial_statements.py` between them
carry more than 40 assertions.

## 40. Five dev scripts now produce a price neither entry point would · —

**Fact.** Five scripts under `tests/` call `normalize_financials` with the
**unpartitioned** item list. **This misrepresentation is new as of `7354698`**: they
apply `low`-confidence items that both the CLI and the web app now withhold, and they
print no excluded block.

**What it costs.** A script that prints a different share price from the product, with
no indication why. They are dev scripts and not evidence of correctness — but a reader
comparing one against the CLI would find a discrepancy with no explanation.

**Fix.** Call the partition first, as both entry points do. `tests/` is a tester's file.

## 41. `analysis/projector.py:169`'s `0.05` growth rate is unreachable · **dead**

**Fact.** `rev_growth.append(rev_growth[-1] if rev_growth else 0.05)` sits inside
`while len(rev_growth) < ov.projection_years`. `rev_growth` can only be empty when
`projection_years <= 0`, and the `while` never runs in that case. The `P8a` reviewer
proved it two ways at `6e58f13`: by exhausting 48 input combinations — `0.05 pad reached
on 0 of 48` — and by construction.

**What it costs.** Little today, and that is the point. It is one of the three
`analysis/projector.py` hits in item 1's census, and **removing it cannot move a number**,
because no input reaches it. It is the cheapest hit in that census.

**It also carries a claim.** A hardcoded 5% growth rate that never fires still reads, to
anyone auditing the file, as a default this platform is willing to assume.

**Fix.** Delete the `else 0.05`. If `rev_growth` is empty at that point the loop cannot
be running, so no branch is lost. Do it as part of item 1, not on its own.

## 42. A supplied growth list longer than the projection is silently truncated · **CLOSED at `aa6f80d`**

**Fact.** `analysis/projector.py:170` truncates `rev_growth` to `projection_years`.
Measured at `6e58f13`: five supplied rates with `projection_years=2` produce `[0.1, 0.2]`
and the `AssumptionSource` for that ratio carries **no clause saying three rates were
discarded**. The pad case does carry one — it says the last rate was `REPEATED`.

**What it costs.** The reader typed five numbers and the valuation used two. The page
says the rates were `supplied`, which is true of the two that survived and says nothing
about the three that did not. This is not rule 6 broken — nothing is mislabelled — but
it is the same shape one step earlier: an input silently discarded.

**Fix.** Add a truncate clause beside the pad clause, naming how many rates were
discarded. Whoever finishes the provenance work owns it.

## 43. The fiscal year comes from the filename's date, not from the filing · **silent**

**Fact.** `_discover_filings` (`cli.py:140`, moving to `ingestion/filings.py` in
`P9a-session-route`) takes the first year after a `10-K` marker in the filename. The
filenames in `10K_filings/` carry the period-end date. L3Harris ends its fiscal year on
the Friday nearest 31 December:

| File | Year inferred | Fiscal year in the filing |
|---|---|---|
| `L3Harris Technologies Inc._10-K_2023-12-29_English.pdf` | 2023 | 2023 |
| `L3Harris Technologies Inc._10-K_2025-01-03_English.pdf` | **2025** | 2024 |
| `L3Harris Technologies Inc._10-K_2026-01-02_English.pdf` | **2026** | 2025 |

So the multi-filing plan asks the 2025-01-03 filing for "fiscal year 2025 ONLY". That
filing holds 2024, 2023 and 2022. `api/routes_upload.py:_guess_fiscal_year` uses a
different pattern with the same result.

**Cost.** Silent. The model is asked for a year the filing does not contain. It may
return the latest year under the wrong label, or nothing, and the merge then keys
statements on the wrong year. Walmart and Okta are not affected: they name the fiscal
year by the calendar year in which it ends, so the date and the label agree.

**Fix, when assigned.** Read the fiscal year from the filing's cover page, or require it
from the user, and stop when the filename and the filing disagree.

## 44. The `units` field is extracted and then ignored · **CLOSED by `P14a-units`**

**Fact.** `_FINANCIALS_SCHEMA` asks for `"units"` (`claude_extractor.py:158`), and the
prompt says to keep the source's units. `_parse_financials_response` never reads the
field. `docs/4-conventions/units-and-signs.md` says every figure is in millions.

Chipotle reports in thousands. A Chipotle extraction therefore holds thousands, and the
CLI prints them with an `M` suffix. The equity bridge still gives the right price per
share, because the money and the share count are both in thousands. **One path mixes
scales:** when `diluted_shares_outstanding` is missing, `api/routes_valuation.py:482`
substitutes yfinance's `sharesOutstanding / 1e6`, which is millions.

**Fix, when assigned.** Read `units` in the parser and either convert to millions once,
or stop on anything other than millions.

**Measured at `0a5a715` with `pdfplumber`** on the latest filing of each company here:
Walmart page 21 "(Amounts in millions, except per share data)", AbbVie page 21 "(in
millions, except per share data)", Chipotle page 29 "(in thousands, except per share
data)", Okta page 58 "(dollars in millions, shares in thousands, except per share
data)". So Okta's share count is on a different scale from its money figures. No Okta
extraction exists here, so the price error that follows is not measured.

## 45. The constant-market stop in `calculate_beta` is reached only on older SciPy · stopping

**Fact.** `analysis/capm.py:81` calls `stats.linregress`, then checks the result for NaN
at `:86`. SciPy 1.17.1 (macOS, `docs/8-build/environment.md`) raises its own
`ValueError` for a constant regressor first: "Cannot calculate a linear regression if
all x values are identical". So the repository's message, which names `market_returns`
and its variance, never appears.

`tests/unit/test_capm.py::test_beta_stops_when_the_market_series_has_no_variation`
fails on macOS for that reason. It is the one failure in the test gate there.

**Cost.** Low. The run still stops. It names SciPy's reason, not the input.

**Fix, when assigned.** Check `np.var(market_returns) == 0` before calling
`linregress`. **Held by the user on 2026-10-02.**

## 46. `.env` overrides the environment, so unsetting a key does not stop a paid call · **CLOSED by `P13c-env-override`**

**Fact.** `config.py:15` is `load_dotenv(BASE_DIR / ".env", override=True)`. Its comment
says "System env vars still work; .env just provides a convenient local override". The
code does the opposite of the usual order: a value in `.env` replaces a value already
in the environment, and it also restores a variable that the caller removed.

**Measured by accident on 2026-10-02.** `P9a-session-route` ran
`env -u ANTHROPIC_API_KEY … cli.py 10K_filings/Chipotle -t CMG` to show that the API
route stops with no credential. It did not stop. The run printed
`Credential: ANTHROPIC_API_KEY (environment)` and started Pass 1 on the Chipotle 2023
10-K. It is not known whether that call was billed.

**Cost.** Silent, and it costs money. Any instruction of the form "unset the key to make
sure no API call is made" is false while `.env` holds the key. The label then also says
`(environment)` for a key that came from the file.

**Measured 2026-10-02**, with a probe that prints only whether the key is present after
`load_dotenv`:

| `.env` setting | shell unsets the key (`env -u`) | shell sets it empty (`ANTHROPIC_API_KEY=`) |
|---|---|---|
| `override=True` (today) | key present | key present |
| `override=False` | key present | **key absent** |

So with `override=True` **nothing in the shell can turn the key off**. With
`override=False`, an empty value turns it off for one run. Unsetting it never does,
because `load_dotenv` fills an absent variable from the file either way. An earlier
version of this entry said `override=False` makes `env -u` work. That was wrong.

**The keys themselves are not the problem.** `.env` holds three names.
`ANTHROPIC_API_KEY` is the credential route A uses by default. `GEMINI_API_KEY` is read
only when `-p gemini` is chosen. `DEEPSEEK_API_KEY` is read by no code in the repository.

**Fix, when assigned.** `override=False`, and say in `docs/8-build/environment.md` that
`ANTHROPIC_API_KEY=` (empty) is how to run with the key off. Then make
`credential_source` say whether the key came from `.env` or from the shell.

## 47. The income statement shown has no interest income row · display

**Fact.** `IncomeStatement.ebt` is `ebit - interest_expense + interest_income +
other_non_operating` (`models/financial_statements.py:91`). The income statement block
in `cli.py` and in `templates/_statements.html` shows Interest Expense and Other
Non-Operating, and no Interest Income.

**Measured on the first real session extraction, 2026-10-02.** Walmart fiscal 2026:
EBIT 29,825 − interest expense 2,799 + other non-operating 2,075 = 29,101 from the rows
shown. The EBT row shows 29,469. The difference is interest income of 368, which is in
the session file and in EBT, and on no page.

**Cost.** No figure is wrong. A reader who checks the column by hand finds a gap of 368
and cannot close it from the page. That is rule 4.

**Fix, when assigned.** Add an Interest Income row between Interest Expense and Other
Non-Operating, in both places, in the same unit.

## 48. The equity bridge does not subtract noncontrolling interest · **silent**

**Fact.** The Pass 1 schema asks for **consolidated** net income, including the share
that belongs to noncontrolling interests, and for total equity including them. So the
projected cash flows value the whole group. `analysis/dcf.py` then goes from enterprise
value to equity value by subtracting net debt only. The share of that value that belongs
to minority holders is never subtracted, and the schema has no field to hold it.

**Measured on the first real session extraction, 2026-10-02.** Walmart, 2026-01-31
balance sheet (PDF page 22): nonredeemable noncontrolling interest 6,270 plus
redeemable noncontrolling interest 293 = 6,563. Divided by 8,022 diluted shares, that
is about $0.82 of the $28.84 implied price.

**Cost.** Silent. The implied price is overstated for every company with
noncontrolling interests, by their book value at least.

**Fix, when assigned.** This adds a field the model is asked to read, so it changes the
LLM boundary and must go to the user first (`AGENTS.md`, "Escalate"). Then subtract it
in the bridge, beside net debt, with its own label.

## 49. Given several PDFs, the API route drops any PDF with no fiscal year · **silent**

**Fact.** With more than one filing, `cli.py` (`_extract_via_api`, the line
`valid = [(y, p) for y, p in filings if y > 0]`) and `api/routes_valuation.py`
(`_extract_from_files`) keep only the filings with a year greater than zero. A PDF whose
name holds no year is dropped, and nothing is printed. When every filing lacks a year,
both fall back to extracting the first one alone.

Found by `P9a-session-route` and confirmed by its review. Route B's `plan` and loader
stop on the same input and name the file, so the two routes now behave differently on
it.

**Cost.** Silent. A year the user supplied a filing for is missing from the valuation,
and the output does not say a file was ignored.

**Fix, when assigned.** Stop and name the file, as route B does. Make the change in both
entry points, or after item 7 in one place.

## 50. Route A returns `[]` when Pass 2 cannot be parsed twice · **CLOSED at `bce6fae`**

**Fact.** `_run_nri_pass` retries once when the Pass 2 reply does not parse. If the retry
also fails, a blanket `except Exception` prints a warning and returns `[]`
(`ingestion/claude_extractor.py`, the second `try` in `_run_nri_pass`). `_parse_nri_response`
goes out of its way to tell "the model found none" from "nothing was read"; this branch
turns the second into the first.

**Cost.** Silent. Every non-recurring item for that filing is lost, and the CLI and the
result page then say no item was found. Found by `P9c-parse-tests`. Route B is not
affected: its loader stops.

**Fix, when assigned.** Raise, naming the filing. With item 8.

## 51. The arithmetic check's `WARN` branch can never run · dead code

**Fact.** `_validate_extracted_data` marks a field `FAIL` when `diff_pct > fail_pct`, and
`fail_pct` defaults to 0.5. The next branch is `elif diff_pct > 0.5`, which is then
never true. Found by `P9c-parse-tests`.

**Cost.** None to any figure. A reader expects a warning band that does not exist.

## 36. The same filing extracted twice gave share prices 16% apart · **silent**

**This is the most consequential item on this list.** Every other defect here is a wrong
answer that can be traced to a line of code. This one is a **different answer to the
same question**, and the product's whole premise is that a reader can walk a share price
back to a page.

**Fact.** The FY2025 L3Harris 10-K was extracted twice, two days apart, by the same model
through the same gateway:

| Run | Implied share price |
|---|---|
| 2026-09-22, orchestrator | **$343.15** |
| 2026-09-22, `P6-honest-output` | **$296.01** |

The largest single cause, confirmed by the reviewer: one Pass 2 non-recurring item worth
**1,140M** present in one run and absent in the other. Total add-backs differ by exactly
that much — `2,408 − 1,140 = 1,268`.

**The model tagged that item `confidence: low`, and nothing read the tag.**

```
requested from the model          ingestion/claude_extractor.py:255
parsed, defaulting to "high"      ingestion/claude_extractor.py:702
stored on NonRecurringItem        models/financial_statements.py:28
printed by the CLI                cli.py:624
read by anything that computes    -- nothing
```

`grep -c confidence analysis/normalizer.py` → **0**. A `low`-confidence 1,140M add-back
is weighted identically to a figure read cleanly off a page, and the web interface does
not print the tag at all.

**Three separate defects sit inside this one item.**

1. **Nothing consumes `confidence`.** The pipeline already has the information needed to
   detect its own uncertainty and discards it.
2. **`.get("confidence", "high")` defaults an unknown to the *strongest* value.** Rule 3,
   and in the optimistic direction.
3. **The schema has no confidence field outside `NonRecurringItem`.** Total debt also
   moved between the two runs — `10,443` against `11,116` — and there is no field in
   which the model could have expressed doubt about it.

**What it costs.** A user who runs the same filing twice gets two answers and no way to
tell which to believe. Neither run is detectably wrong; both are internally consistent
and both cite their sources.

### Half closed at `7354698`

**The user decided, on 2026-09-22:** *"For low confidence, just leave a note and
document, but don't need to adjust the F/S."*

`analysis/normalizer.py` now partitions before normalising. A `low` item is withheld and
listed separately with its cited source, in both outputs, under wording saying it was
not applied. `confidence` reaches `analysis/`, and an absent tag stops the parse instead
of becoming `"high"`.

**What it cost on the user's own filing: `$0.00`.** The FY2024 extraction tagged 13
items `high` and 2 `medium` and **none `low`**, so nothing was withheld.

### Still open, and it is the harder half

**Nobody has measured the variance.** One pair of runs differing by 16% is an
observation, not a range. Worse, the single occurrence that prompted all this **cannot
be sized**: the two runs used different filings, the graft double-counted a charge
already present, and **all three cache files hold zero `low`-confidence items**
(`{high 40, medium 3}`, `{high 22, medium 1}`, `{high 13, medium 2}`).

So the user's rule is sound in principle and **untested in practice**. Establishing
whether it helps needs the same filing extracted several times and the spread reported —
roughly $6 in tokens, and the only way to turn one observation into a range.

**And the schema half is untouched.** Total debt moved between the two runs, `10,443`
against `11,116`, and **there is no confidence field anywhere outside
`NonRecurringItem`** — the model had no way to express doubt about it. Closing that means
asking the model for something new, which `AGENTS.md` makes an escalation to the user.

**Do not "fix" this by pinning the model's sampling.** A reproducible wrong answer is
not better than a variable one; it is the same defect with the evidence hidden.

**Do not "fix" this by pinning the model's sampling.** A reproducible wrong answer is
not better than a variable one; it is the same defect with the evidence hidden.

## 33. The CLI cache is keyed on the ticker alone · **silent**

**Fact.** `cli.py:248-253`:

```python
return d / f".cache_{args.ticker.lower()}_extraction.pkl"
```

The PDFs passed on the command line are **not part of the key** and are never compared
against the cache's contents.

**Measured.** The first run against the user's new filings —
`cli.py "…LHX/…2025_English.pdf" -t LHX --cache-dir ./cache` — completed in **2 seconds**
and printed a full valuation of **$351.77**. It had loaded
`cache/.cache_lhx_extraction.pkl`, a pickle that predates this entire build, and **never
opened the PDF at all.** The output says `LOADING CACHED EXTRACTION` but does not say
that the file named on the command line was ignored.

**What it costs.** A complete, plausible, correctly-formatted valuation from data of
unknown provenance — unknown extractor version, unknown provider, unknown date — with no
signal. This is `STATUS.md` traps 1 and 3 firing together, and it is the first thing a
new user will hit, because the cache flag appears in four of the six examples in the
CLI's own help text.

**Fix.** Key the cache on the input files as well as the ticker — a hash of the paths
and their modification times. **A cache that can answer a question it was not asked is
worse than no cache.**

## 34. The risk-free rate is a hardcoded constant presented as measured · **silent**

**Fact.** `config.py:42` — `DEFAULT_RISK_FREE_RATE = 0.04  # 4.0% fallback if market
fetch fails`. `analysis/capm.py:123` substitutes it whenever no override is supplied,
and the CLI's `--risk-free-rate` defaults to `None`.

**There is no market fetch.** `grep -rn "treasury\|TNX\|risk_free" ingestion/price_fetcher.py`
returns nothing. The comment describes a fallback for a mechanism that was never built.

**What it costs.** The output prints `Risk-free rate: 4.00%` alongside genuinely measured
figures, with nothing distinguishing it. It enters the cost of equity, so it reaches
every discounted cash flow. [Rule 6](../2-rules/rules.md).

**Fix.** Either fetch it, or label it. Labelling is the cheaper half and closes the rule
break on its own.

## 35. An unusable beta is reported without qualification · **silent**

**Fact.** On the LHX run: `Beta: 0.493 (regression)`, `R-squared: 0.099`,
`Std error: 0.196`. The regression explains **10%** of the variance, and the standard
error is 40% of the estimate.

**What it costs.** Measured on this filing, holding everything else as the run produced
it:

| Beta | Implied price | Against the market's $240.21 |
|---|---|---|
| 0.493, as regressed | $343.57 | **+43.0%** |
| 0.80, a sector figure | $227.33 | **−5.4%** |

**One unmeasurable input moves the answer from a 43% buy to a 5% sell.** The diagnostic
that says so is printed two lines above it and carries no threshold, no warning and no
consequence.

**Fix.** [Rule 6](../2-rules/rules.md). Name a minimum R-squared, and when the
regression falls below it, say so in the output beside the beta — or stop.

## 31. `discount_cash_flows`' `wacc` is unguarded on a direct call · **silent, latent**

**Fact.** `analysis/dcf.py` guards every projected cash flow but not the `wacc`
parameter of `discount_cash_flows` itself. Verified by the reviewer of
`P4d-cashflow-nan`: a direct call with a NaN `wacc` returns `nan`.

**Why it is latent.** Through `run_dcf` the chain stops two lines later, at
`calculate_terminal_value`. No current caller reaches it with a NaN.

**Why it stays recorded.** `discount_cash_flows` is public, and "safe because nothing
calls it that way today" is the argument
[.claude/agents/code-reviewer.md](../../.claude/agents/code-reviewer.md) names as one of
the three that never justify a downgrade. Reachability is not the test.

## 32. Zero diluted shares render a share price of `0.0` · **CLOSED at `aa6f80d`**

**Fact.** `models/valuation.py:138`. Reported by the tester of `P1-suite`, reported
again by `P4d-cashflow-nan`, and never assigned.

**What it costs.** It is item 2's shape on the **denominator** of the headline figure.
Equity value divided by zero shares gives `0.0` rather than a stop, so a valuation with
no share count renders a price of zero — which reads as a company worth nothing rather
than as an absent input.

**Why no test asserts it.** Locking `implied_share_price == 0.0` would make the defect
permanent. The testers reported it instead, twice.

**Fix.** Raise, naming `diluted_shares`. **`models/valuation.py` carries 40 assertions**
— any unit touching it must expect to answer for every one.

## 30. A NaN in one `ProjectedFCFF` reaches the share price · **CLOSED at `2ca620a`**

**Fact.** Confirmed by the reviewer of `P4c-nan-stops`, **before and after** that unit,
in a middle projection year and in the final year: a NaN in a single `ProjectedFCFF`
produces `implied_share_price = nan` even when WACC is finite.

`analysis/dcf.py:46-57` sums and discounts the projected cash flows with no check on
what it is summing.

**What it costs.** The same as item 20 — a NaN share price on a clean run — through a
different door. **All three stops item 20 added sit on the discount-rate side.** The
cash-flow side has none.

**Why it is not charged to `P4c-nan-stops`.** `analysis/dcf.py:46-57` is unchanged by
that diff, and widening its scope to reach this would itself have been a review finding.

**Fixed at `2ca620a`.** `analysis/dcf.py` guards each projected cash flow before it is
discounted, naming the **year** rather than only the field. The terminal value's base
cash flow is guarded inside `calculate_terminal_value`, **not** in `run_dcf` — a guard
there would be dead code, because `discount_cash_flows` runs first over the whole list
including the last element. The reviewer verified that by stack trace rather than by
argument: `run_dcf:133 <- discount_cash_flows:97 <- _require_finite:35`, with the later
lines never reached.

**Two more doors are still open**, both reported by the same unit and neither charged to
it: item **31** (`discount_cash_flows`' `wacc` on a direct call) and item **32**
(`models/valuation.py:138`).

## 23b. The NaN tax clamp twin, `analysis/fcff.py:44` · **CLOSED at `2ca620a`**

**Fact.** `max(0.0, min(nan, 0.50))` is **`0.0`**. Python's `min` and `max` keep their
first argument when a comparison is `False`, and every comparison against NaN is
`False`. Measured:

```
min(nan, 0.50)           ->  nan
max(0.0, min(nan, 0.50)) ->  0.0
```

**What it costs.** The clamp turns an unknown tax rate into **zero percent** — a full
tax shield, which **raises** the valuation. An input nobody could compute becomes the
most favourable possible assumption, silently.

`analysis/wacc.py` held the identical clamp and `P4c-nan-stops` fixed it, checking
**before** the clamp because afterwards the evidence is gone. `analysis/fcff.py:44` was
out of that unit's scope and still has it. Recorded here rather than as a new number
because it is the same defect as item 23's file.

**Fixed at `2ca620a`**, checking before the clamp as `analysis/wacc.py` does. Measured
cost, reproduced independently by the reviewer:

| Tax rate supplied | `tax_rate` | after-tax interest | FCFF |
|---|---|---|---|
| `0.25`, from the filing | 0.25 | 7.5 | **112.5** |
| NaN, before the fix | **0.00** | 10.0 | **115.0** |

An unknown rate raised free cash flow by 2.5 in a single year and was reported as a
measurement.

**The clamp still clamps**, which was the point of keeping two controls on it: `0.80`
still becomes `0.50` and `-0.30` still becomes `0.0`, byte-identical before and after.
A **known** out-of-range rate is corrected; only an **unknown** one stops. Before the
fix the two were indistinguishable in the output, and the unknown one gave the most
favourable result available.

`analysis/fcff.py` is still open on item 23's other half.

## 29. `POST /valuation` with no `files` runs an extraction on an empty path · **CLOSED at `be1c077`**

**Fact.** `api/routes_valuation.py:131` declares `files: str = Form("")`, and `:154`
branches on it without ever checking that it holds anything:

```python
filings = _parse_files_param(files) if ":" in files else [(0, files)]
```

Measured by the tester of `P5b-route-tests`, and again by the orchestrator, with the
extractor faked:

```
POST /valuation data={"ticker": "TESTCO"}   ->  HTTP 200
  extract_financials received pdf_path = ''
  the word 'files' appears on the page: False
```

**What it costs.** A request that names no filing is not an error here. It becomes an
extraction against the empty string, and whatever that produces flows into a rendered
page. [Rule 3](../2-rules/rules.md): a missing input must stop the run and name the
field. This one does neither.

**It is not item 26 and not item 1.** Item 26 is about the branch *test*; this is about
the value being empty in the first place. Item 1's census counts a different pattern and
does not match a `""` default in a `Form()` declaration, so this site has never been
counted.

**Fix.** Stop when `files` is empty, naming `files`. The three inputs declared without a
default — `ticker` and `pdf_files` on `POST /upload`, `ticker` on `POST /valuation` —
already return 422 naming the field, so the correct behaviour is established in the same
file.

**No test asserts it in either direction.** The tester reported it rather than encoding
it, because asserting the current behaviour would lock the defect.

## 27. `GET /` and `GET /assumptions` return 500 · **CLOSED 2026-09-21**

**Fact.** `starlette` 1.6.0 requires `TemplateResponse(request, name, context)`. Two
call sites still use the removed `(name, context)` form:

| Site | State |
|---|---|
| `api/routes_upload.py:42` | **broken.** Unchanged since `bc19431` |
| `api/routes_valuation.py:114` (`assumptions.html`) | **broken** |
| the two `valuation_result.html` calls | fixed by `P2b-provider` |

Measured at `0e4649f`:

```
TestClient(app.app, raise_server_exceptions=False).get('/')  ->  500
```

**What it costs.** `app.py` is one of the two entry points this product ships, and a
user cannot reach its first page. The command in `docs/0-start.md` starts a server that
serves nothing.

**Why nobody noticed.** The failing calls sit inside item 8's blanket catch, which
renders the error onto a page — through the same broken call. So the error page could
not render either, and the failure surfaced as a bare 500 with no message. mypy had been
reporting all four as `arg-type` errors since `bc19431`; they were ranked below a
different error from the same output.

**Fixed at `622262b`.** Unit `P5-web-routes`, two lines. Measured before and after against a
`git archive` export of the baseline, by the programmer and again by the reviewer:

```
BEFORE   GET / -> 500,   21 bytes (literally b'Internal Server Error')
AFTER    GET / -> 200, 1648 bytes,  all six upload-form markers present
         GET /assumptions -> 200, 5673 bytes
```

Types fell 18 → 14; `comm -13` against the baseline is empty and `comm -23` is exactly
the four `arg-type` errors on the two changed lines.

**The reviewer proved the "why nobody noticed" claim rather than repeating it.** It
exercised the error branch of `assumptions_page`, which now returns 200 and renders
`<div class="alert alert-error">[Errno 2] No such file…</div>`. Before the fix that
branch rendered through the same broken call, so the handler meant to report the error
could not report anything.

## 26. A Windows upload path is parsed as a fiscal year · stopping

**Fact.** `api/routes_valuation.py:152`:

```python
filings = _parse_files_param(files) if ":" in files else [(0, files)]
```

The `":"` test is meant to detect the `year:path` encoding used for a multi-file
upload. `_parse_files_param` at `:34-43` then does:

```python
year_str, _, path = entry.partition(":")
result.append((int(year_str), path))
```

**Correction, 2026-09-21.** An earlier revision of this item — written by the
orchestrator from a reading of `:152` alone — said "every saved upload path on this
platform contains a colon", and told a story in which refreshing a working valuation
breaks. **That was wrong**, and the reviewer of `P2b-provider` round 2 disproved it by
execution. The upload flow at `api/routes_upload.py:60-62` always builds the parameter
as `f"{year or 0}:{path}"`, and `str.partition` splits on the **first** colon only:

```
'2024:C:\Users\x\goog.pdf'  ->  [(2024, 'C:\\Users\\x\\goog.pdf')]   OK
'0:C:\Users\x\goog.pdf'     ->  [(0,    'C:\\Users\\x\\goog.pdf')]   OK
'C:\Users\x\goog.pdf'       ->  ValueError: invalid literal for int() with base 10: 'C'
```

So the year prefix absorbs the drive-letter colon, and the upload flow is safe. The
reviewer's own criterion-4 runs went through `_parse_files_param` on a cache miss with a
Windows absolute path and returned 200.

**What it actually costs.** The defect fires only when `files` arrives with **no** year
prefix — the legacy `file_path` branch at `api/routes_valuation.py:91-92`, or any caller
that builds the parameter by hand. It is latent, not live, which is why it is ranked
below the silent defects rather than with them.

**It stays recorded** because the guard is wrong in principle: `":" in files` tests for
a character that a path on this platform always contains, so the branch is right today
only by the accident that something else always adds a colon first. A future change that
drops the prefix turns it live with no other edit.

**Fix.** Decide the branch on something a path cannot contain, or pass the filings as
structured data rather than as one delimited string. **Do not "fix" it by testing for a
drive letter** — that repairs one platform and leaves the design wrong.

## 25. An adjustment whose year matches no statement is silently discarded · **CLOSED at `47b8b09`**

**Fact.** `analysis/normalizer.py:167-170`. `normalize_financials` groups the
non-recurring items by year, then walks the **income statements** and applies whatever
that year's bucket holds. An item whose year is in no statement is never looked at.
Measured by the tester:

```
statement years : [2023, 2024]   item year : 2019
RAISED          : nothing
  2023: sga 200.0 -> 200.0   2024: sga 200.0 -> 200.0
```

The item was well formed — recognised label, legal direction, real amount.

**What it costs.** A valuation labelled *normalised* whose figures are still GAAP, with
no signal anywhere. It is the same class as item 3, one line above it in the same
function, which `P4-normalizer` has just closed.

**It is not hypothetical.** The item's year and the statements' years come from **two
separate model passes** — `ingestion/claude_extractor.py:259` and `:553` — with nothing
reconciling them. `extract_multi_year` merges statements year by year while accumulating
every NRI, so a mismatch is routine rather than exotic.

**Fix.** Raise, naming the item's year and the years that do exist. Needs its own unit
and a red test.

**Why no test exists yet.** A test asserting the drop would be asserting the fallback,
which [5-testing/strategy.md](../5-testing/strategy.md) section 2 forbids. And the red
test would have had to live in the file `P4b-normalizer-verify` was sent to delete. The
tester reported it instead, which is what its contract prescribes.

## 24. A red test that goes green stays outside the gate · **CLOSED at `81816be`**

**Was.** At `38b903c`:

```
pytest -q                                  ->  93 tests, 92 pass, 1 red
pytest -q --ignore-glob="*_rule3_red.py"   ->  90 passed
pytest -q tests/unit/test_normalizer_rule3_red.py  ->  2 passed
```

The gate ran 90 of the 92 passing tests. The missing two were the former red tests for
items 3 and 21, which went green when `P4-normalizer` fixed what they stated and stayed
inside the pattern the gate excludes. **So the two tests proving the fix worked were the
two the gate did not run.** That is the shape of defect this repository exists to avoid:
a clean report about something nobody checked.

**Now.** They live in `tests/unit/test_normalizer_stops.py`, each additionally asserting
the year. `ls tests/unit/*_rule3_red.py` returns one line, `test_dcf_rule3_red.py`,
which states item 2 and is correctly still red. The gate reports **105 passed**.

**The rule is now in the tester's contract** —
[.claude/agents/tester.md](../../.claude/agents/tester.md), "A red test lives in
`*_rule3_red.py`, and it moves out the day it goes green" — so the next unit does it
without being told.

## 19. One sign rule applied to two kinds of line · **CLOSED at `38b903c`**

**Fact.** Two lines of the income statement move earnings in opposite directions:

| Line | How it reaches earnings |
|---|---|
| `other_operating_expense`, `sga`, `cost_of_revenue`, … | **subtracted** — `ebit` |
| `other_non_operating` | **added** — `models/financial_statements.py:91` |

`analysis/normalizer.py:68` applies one rule to both:

```python
delta = -item.amount if item.direction == "add_back" else item.amount
```

`_LABEL_TO_FIELD` routes three labels to `other_non_operating`
(`analysis/normalizer.py:38-40`), so an adjustment on a non-operating line moves
**both** directions the wrong way.

**Measured** by the reviewer, on revenue 1000 / SG&A 200 / `other_non_operating` 80 /
`tax_expense` 100, removing a one-time gain of 50:

| | `other_non_operating` | EBT | Effective tax rate |
|---|---|---|---|
| Correct clean base | 30.0 | 430.0 | 23.26% |
| What the code produces | **130.0** | **530.0** | **18.87%** |

**What it costs.** The error is `+100` on a `50` item — twice the amount, in the wrong
direction. It understates the effective tax rate by 4.4 points, which
`analysis/projector.py:63-64` averages into the projected tax rate, which **overstates
NOPAT by 5.7% in every projected year** (324.53 against 306.98 on an EBIT of 400).

**This fires on ordinary, correct input.** Every other silent defect in this backlog
needs a missing value. This one needs only a filing that reports a gain on an asset
sale — which is the exact case `NonRecurringItem`'s own docstring names as
`gain_loss_asset_sale`.

**The repository already disagrees with itself in writing.**
`models/financial_statements.py:31-37` declares the correct intent:

```python
@property
def adjusted_impact(self) -> float:
    """add_back -> positive (removes expense -> improves EBIT)
       remove   -> negative (removes gain   -> reduces EBIT)"""
    return self.amount if self.direction == "add_back" else -self.amount
```

That is the effect on **earnings**. `normalizer.py:68` computes the delta on the
**field**, and the two are equal only when the field reduces earnings.

**Fixed at `38b903c`, and it was not a judgement.** The delta on a field is now

```python
item.adjusted_impact * _FIELD_EARNINGS_SIGN[field]
```

`_FIELD_EARNINGS_SIGN` holds six `±1.0` entries; only `other_non_operating` is `+1.0`.
[Rule 2](../2-rules/rules.md) permits it explicitly: **a lookup table that maps a key
to a number is allowed.** It is looking up *behaviour* that is forbidden.

**Verified three times, independently, by three agents who did not share context.** The
programmer derived all six signs by bumping each field and reading the change in `ebt`.
The reviewer re-derived them by finite difference at two step sizes, against both `ebt`
and `net_income`, and checked the invariant the fix exists to restore —
`Δebt == adjusted_impact` — over all six fields and both directions, 12 of 12. The
orchestrator ran the worked case and the expense case.

After: `other_non_operating` 30.0, `ebt` 430.0, effective tax rate 23.26%. The expense
path is unchanged: an `add_back` of 50 in `sga` still moves it 200 → 150 and raises
`ebit` 400 → 450.

**One consequence, recorded rather than hidden.** This converts a silent wrong number
into a hard stop, and that stop lands in the blanket catch at
`api/routes_valuation.py:220`, which renders it as a bare string on the results page.
**Item 8 is more urgent than its rank suggests.**

## 20. A NaN beta is returned, not raised · **CLOSED at `ff632df`**

**Fact.** `analysis/capm.py:87` calls `calculate_beta`, which calls
`scipy.stats.linregress`. On an empty series that returns `nan` for the slope and
**raises nothing**. Measured directly:

```
linregress([], []) -> slope=nan  rvalue=nan  stderr=nan
```

The guard at `analysis/capm.py:42-43` does catch an empty series, but only on the path
that derives the equity risk premium from history. **Supplying an ERP skips it**, and
both the web form and the CLI let a user do that.

**What it costs.** `nan` reaches the cost of equity, then WACC, then
`analysis/dcf.py:24`:

```python
if wacc <= terminal_growth_rate:
    raise ValueError(...)
```

**`nan <= 0.025` is `False`.** Every comparison against NaN is false, so the one
correct stop in the whole of `analysis/` does not fire. A complete `DCFResult` renders
with `implied_share_price = nan`.

Chain confirmed end to end by the reviewer: `capm.py:72` → `:87` → `:32` →
`models/valuation.py:16` → `analysis/wacc.py:66` → `models/valuation.py:34-38` →
`analysis/dcf.py:24` → `:74,75` → `models/valuation.py:138`. Reached from both
`api/routes_valuation.py:167-172` and `cli.py:687-692`.

**Fixed at `ff632df`** by unit `P4c-nan-stops`, with three stops in series, every one
`math.isnan` and none a comparison:

| File | Catches |
|---|---|
| `analysis/capm.py` | unequal series lengths; fewer than 3 observations; a regression whose statistics come back NaN |
| `analysis/wacc.py` | a NaN arriving where CAPM cannot see it — an overridden beta, a NaN market cap, a `CAPMResult` built elsewhere |
| `analysis/dcf.py` | the last guard before a price is rendered now rejects NaN itself, rather than trusting upstream |

**The proof is the path that did not move.** Six new stops were added to files already
at 100% coverage, where every assertion was derived by hand, so the risk was never that
a stop fails to fire — it is that a healthy path shifts. The reviewer ran six controls
**with its own inputs**, different from the programmer's, and none moved by a digit:
`implied_share_price = 12.697763190328896`, `beta = 1.596774193548387`,
`std_error = 0.10158303025640267`.

**The threshold of 3 observations is derived, not fitted.**
`SE(beta) = sqrt(SSE / ((n-2) · Sxx))` needs `n - 2 >= 1`. scipy 1.18.1 at `n = 2`
returns a finite slope with `stderr = nan`, so the old code rendered a price while
carrying a NaN diagnostic. Adopting the threshold **removes** a number the old code
produced, which is the opposite of fitting a case.

**Coverage fell and was not worked around.** `capm.py` 92%, `dcf.py` 93%, `wacc.py` 97%;
all six missed lines are the new raises. The reviewer reached every one by execution, so
no unreachable guard was written to hold a percentage.

**Two doors are still open.** See item **30** — the cash-flow side is unguarded — and
item **23b**, the tax clamp twin in `analysis/fcff.py`.

## 21. An unrecognised `direction` silently reverses the adjustment · **CLOSED at `38b903c`**

**Was.** `analysis/normalizer.py:68` tested `item.direction == "add_back"`. Every other
string — `"Add_Back"`, `"addback"`, a typo, an empty string — took the `else` branch and
was treated as `remove`, moving the adjustment the opposite way with no signal. The
value arrives from the model, so the set of possible spellings was never closed.

**Now.** Raises `ValueError` naming the value and the year:

```
Unrecognised direction 'Add_Back' on the 2022 non-recurring item 'Restructuring charge'…
```

Locked by a test in `tests/unit/test_normalizer_stops.py`, written red and now green
inside the gate — see **item 24**.

## 22. Zero debt balance gives a 0% cost of debt · **CLOSED at `6cf34d3`**

**Corrected 2026-10-06.** This section said "silent" and described the defect in the
present tense, while the summary table at the head of this file said "closed at
`6cf34d3`". **One of the two had to be stale and this one was**, measured against the
code: `analysis/wacc.py:253-290` now stops when a zero debt balance sits beside a
reported interest expense, and its own comment at `:262` reads "A zero debt balance
**used to** return 0.0 unconditionally". The `--confirm-zero-debt` flag and the
"Confirm zero debt" checkbox are the deliberate exception, added by `P13h` at `bc30be4`.
The weights half of this item became item 38.

**The original fact, kept because it is what the rule was written from.**
`analysis/wacc.py:37-38` held `if total_debt == 0: return 0.0`. A filing that reports an
interest expense but from which no debt balance was extracted is missing data, not a
debt-free company, and the zero was read as a measurement. The weight was also zero in
that case, so it did not move WACC — but it would have, the moment the weights came
from anywhere else.

## 23. `analysis/fcff.py` holds no `raise` at all · **silent**

**Fact.** Measured by the tester: an entirely empty `IncomeStatement` and
`CashFlowStatement` return a well-formed `HistoricalFCFF` with `fcff = 0.0`.

**What it costs.** Free cash flow of exactly zero is a meaningful figure for a real
company. It is indistinguishable here from "nothing was extracted". This is item 1
wearing a different face, and it is named separately because `fcff.py` is the one
`analysis/` module with no stop of any kind.

---

## 38b. Item 38's second face, restated at `P13a` · **part (b) CLOSED at `5c4fb67`; part (a) assigned to `P13h-zero-debt-confirm`**

**The user's decision of 2026-10-04 for part (a): option 1.** An explicit "confirm zero
debt" choice, a checkbox on the form and `--confirm-zero-debt` on the CLI. When it is
set, the run values the company with no debt and the label says that the user confirmed
the zero. A supplied cost of debt no longer gets past item 22's stop. Options 2 (keep the
cost of debt as the confirmation) and 3 (always stop) were refused.

Item 38's own case (market cap plus debt equal to 0, and since `P13a` round 2 a market cap
of 0 or below) stops. The **second face** described under item 38 does not match what the
code does. Both reviews of `P13a` re-ran it, identically at `0021845` and after `P13a`:

- **An override with zero debt lines.** Market cap 300, every balance-sheet debt line 0,
  interest expense 30, a supplied cost of debt 0.05: `calculate_wacc` returns weights
  1.0 / 0.0, and the supplied rate reaches nothing. The override returns before item 22's
  interest-against-zero-debt stop runs.
- **No balance sheet.** `balance_sheet=None` raises a bare `AttributeError` at
  `analysis/wacc.py:211`. It is reachable from `api/routes_valuation.py:621-634`, and it
  is the live crash path in item 11.

**Fix, when assigned.** Run the zero-debt stop before the override returns, and stop with
a named `ValueError` when the balance sheet is `None`.


## Suggested order

Dependencies, not severity. **The order matters more than the ranking**, because
fixing a silent defect with no test in place produces an unverifiable claim.

**Steps 1 and 2 are done.** Re-measured at `796de9a`, with `analysis/` at 192 of 194
statements covered.

1. ~~**Item 4**~~ — **done.** `pytest` runs 20 tests with no key. `analysis/dcf.py` is
   at 100% of statements; the other five modules are at 0%.
2. ~~**Item 12's hygiene subset**~~ — **done.** Item 13 was deliberately deferred out
   of this step: one default provider makes the provider a named assumption, and
   [rule 6](../2-rules/rules.md) then requires it to be visible in the output. It ships
   with its labelling, not before it.
3. ~~**Items 19, 3 and 21**~~ — **done at `38b903c`**, in one unit, because all three
   sat in the same 34-line function. Item 19 went first in the whole list because it
   was the only silent defect here that fired on ordinary, complete input.
4. ~~**Item 24**~~ — **done at `81816be`.**
5. **Item 13, with Foundry. Next.** **Extraction cannot run on the build machine at
   all** until it lands, so nothing after this can be exercised against a real filing.
   The whole path is now proven by execution — see the item — so its criteria are
   measurable rather than aspirational.
6. **Item 20**, with item 14 alongside — both are `analysis/dcf.py:24` failing to stop,
   for different reasons. **Item 20 needs a check that is not a comparison**, because
   every comparison against NaN is `False`.
7. **Item 2**, with item 15 alongside — the same failure walking through two files.
   Item 2's red test goes green here.
8. **Item 7** — unify the pipeline, so each later fix is made once.
9. **Item 6**, then **item 22**, then **item 23**.
10. **Item 8**, then **item 11**. Typed failures, which item 1 depends on.
11. **Item 1** — the large one. Last, with the suite in place.
12. **Items 9, 10, 5, 16, 17, 18.**

**Two deviations from the stated rule, both named rather than hidden.**

- **Step 4 sits ahead of step 7.** The rule says unify before fixing, so each fix is
  made once. Item 13 is a stopping defect on the only machine available, and the cost
  of waiting is that no unit after it can be checked against a real extraction. A fix
  applied twice is cheaper than a build nobody can run.
- **Step 3 sits ahead of everything, including the test-first rule.** It does not
  breach it: `analysis/normalizer.py` is at 93% of statements with 39 assertions
  against it, and the two lines not covered are the ones the fix will delete. The tests
  are already in place. That is exactly the position the rule was written to produce.

**Step 3 moved ahead of step 5, and that is a deviation worth naming.** The rule is
that unification comes before behaviour fixes, so each fix is made once. Item 13 is a
stopping defect on the only machine available, so the cost of waiting is that no unit
after it can be checked against a real extraction. A fix applied twice is cheaper than
a build nobody can run.

## Constraints on any unit taken from this list

- **Do not fix more than the assignment names.** An out-of-scope fix is a review
  finding even when the change is good.
- **Do not weaken, skip or `xfail` a test to make a suite green.**
- **Do not lock a defect as an expectation.** A test asserting `net_debt == 0.0` when
  the balance sheet is missing makes item 2 permanent and turns its fix red.
- **Re-measure the counts in this file when a unit lands.** They are measurements, and
  they carry a commit.
