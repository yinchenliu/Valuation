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
| 49 | Given several PDFs, the API route drops any PDF with no fiscal year and says nothing | **silent** | `cli.py`, `api/routes_valuation.py` | **new at `P9a`.** Route B stops on the same input, so the two routes now differ on it |
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
| 68 | The CLI prints no assumption label | **silent**, on the CLI | `cli.py` | **new, the `P13b` review's O1.** `print_assumptions` (`cli.py:677-695`) prints the rates and an `(override)` tag, never the label text. So `SUBSTITUTED`, `REPEATED` and `DROPPED` are invisible on the CLI; the web page shows them (rule 6) |
| 69 | A negative debt balance gives WACC weights above 1 and below 0 | **silent** | `analysis/wacc.py` | **closed by `P13f-wacc-debt` (`5c4fb67`)**: each debt line and the total must be finite and not negative |
| 70 | Walmart's stage 10 is not reproducible: PV of terminal value reads 214,819M or 214,820M between runs on one tree | — | stage 6 onward | **new, the `P13e` review's F3.** Cause not measured; live market data is the first suspect |
| 71 | The rule 3 census grep cannot see a conditional zero written on two lines | — | `docs/2-rules/rules.md` | **new, the `P13d` programmer and review.** `if x == 0:` / `return 0.0` is not counted, so the census undercounts |
| 72 | `cli.py:1035` and `:1043` hold conditional zeros (`shares`, `latest_bs.total_debt if latest_bs else 0`) | **silent** | `cli.py` | **new, the `P13f` programmer and review.** The census does not search `cli.py` **Half closed by `P3a-one-pipeline`:** the `shares` site is gone (`pipeline.py` reads the share count directly and stops on one that is not above 0). The `total_debt` display line stays in `cli.py` for `P3b-pipeline-stops` |
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
| 87 | The web page and the CLI give different prices for the same filing: the assumptions form rounds each default to one decimal and posts it back as an override | **silent**, on the web | `api/routes_valuation.py` (`assumptions_page`, the `*_display` defaults), `templates/assumptions.html` | **new, the `P3a-one-pipeline` programmer, confirmed by its reviewer, 2026-10-05.** Walmart: operating margin 4.25% shows as 4.3%, and a user who accepts every default gets $27.01 on the web page; the CLI gets $28.02 from the same filing and the same market data. Older than `P3a`. Not yet checked: whether the page then labels the rounded ratios as supplied by the reader (rule 6) |
| 88 | The valuation assumptions are a bare `dict` passed between functions | — | `analysis/projector.py` (`derive_assumptions` returns it; `project_fcffs(financials, assumptions: dict)` takes it), `pipeline.py` | **new, the `P3a-one-pipeline` review's F2, 2026-10-05.** Rule 2 forbids an untyped dict as an argument bag. Keys are read by name (`assumptions["tax_rate"]`, `["terminal_growth_rate"]`), so a missing key is a `KeyError` at run time, not a type error. Fix: a typed return from `derive_assumptions` **The user's decision of 2026-10-05** ("Accept until item 88") accepts `pipeline.py`'s `assumptions: dict` until this item is fixed |
| 89 | `run_capm` prints from inside a calculation | — | `analysis/capm.py:215` | **new, the `P3a-one-pipeline` programmer and review, 2026-10-05.** It prints "ERP from history: ..." to stdout, so the web server's console gets it and the CLI shows it wherever the call happens to run. The `CAPMResult` should carry the figures, and the CLI print them |
| 90 | The default terminal growth rate is a literal in two places | — | `cli.py:205` (`0.025`), `api/routes_valuation.py` (`terminal_growth_rate: float = Form(2.5)`) | **new, the `P3a-one-pipeline` review, 2026-10-05.** The same shape as item 34's risk-free literal: not a named `config` constant, so editing one moves one entry point only. Rule 6 asks for a named default with its reason |
| 91 | Seven scripts in `tests/` run their own valuation sequence, each with the yfinance share count fallback | — | `tests/test_e2e_abbv.py:175`, `test_e2e_abbv_3years.py:204`, `test_e2e_lly.py:175`, `test_e2e_googl_3years.py:219`, `test_e2e_all_googl.py:74`, `test_e2e_phase2_googl.py:123`, `tests/_run_lly_dcf.py:31` | **new, the `P3a-one-pipeline` programmer and tester, 2026-10-05.** Each holds `info.get("sharesOutstanding", 0) / 1e6`, which `P3a` removed from the pipeline (rules 3 and 5). The census does not scan `tests/`. Point them at `pipeline.value_company`, or delete them (item 40) |
| 92 | The CLI and the web pages show different historical FCFF for the same filing | — | `cli.py` (`print_historical_fcff(financials)`, the statements as extracted), `api/routes_valuation.py` (`_historical_fcff_by_year(normalised_financials)`) | **new, the `P3a-one-pipeline` programmer, 2026-10-05.** Walmart: the CLI shows 17,109 / 12,854 / 16,985 and the web pages 17,192 / 12,873 / 16,952. Normalisation changes the effective tax rate, which changes after-tax interest. Display only: neither table reaches the DCF. One of the two is the wrong basis, and nothing on either page says which statements it used |

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

## 22. Zero debt balance gives a 0% cost of debt · **silent**

**Fact.** `analysis/wacc.py:37-38` — `if total_debt == 0: return 0.0`.

**What it costs.** A filing that reports an interest expense but from which no debt
balance was extracted is missing data, not a debt-free company. The zero is read as a
measurement. The weight is also zero in that case, so today it does not move WACC — but
it will the moment the weights come from anywhere else.

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
