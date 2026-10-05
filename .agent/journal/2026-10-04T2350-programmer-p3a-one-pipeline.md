---
agent: programmer
assignment: P3a-one-pipeline
round: 1
status: complete
files_touched: [pipeline.py, cli.py, api/routes_valuation.py, docs/3-architecture/entry-points.md, docs/INDEX.md]
verdict:
---

# P3a-one-pipeline — one module runs the valuation steps; no figure moved

## What I did

I created `pipeline.py` at the repository root. It holds two functions with fixed, typed
signatures, `adjust_financials(raw_financials, non_recurring) -> AdjustedFinancials` and
`value_company(adjusted, overrides, ticker, lookback_years, frequency) -> ValuationRun`,
plus one frozen dataclass for each result, with no field defaulted. The eight valuation
calls, the share count and its yfinance fallback (moved as it was, now recorded as
`shares_from_market_data`), and the market cap now run only there. `cli.main` calls
`adjust_financials`, prints stages 2 to 5, calls `value_company`, then prints stages 6 to
10, the summary and the "not measured" block from the result. Every print function and
printed line is kept, `total_debt = latest_bs.total_debt if latest_bs else 0` included.
`assumptions_page` and the cache-miss branch of `run_valuation` call `adjust_financials`,
and `run_valuation` calls `value_company`. Form parsing, the cache, `_shown_identity`, the
chain builders and both template contexts are unchanged. I rewrote
`docs/3-architecture/entry-points.md` ("Where they duplicate each other" became "What
`pipeline.py` holds, and how the two still differ") and changed its `docs/INDEX.md` row.

**No number moved.** The comparisons below were run with one recorded `PriceData` given to
both commits, so yfinance noise is held fixed. All three web pages are byte-identical.
The CLI differs by one display line, which moved and did not change.

## Done-criteria

The base is a worktree at `6c528f0`, run with this repository's `.venv/bin/python` and the
absolute path of `extractions/WMT.json`. The worktree is removed (`git worktree list`
shows only main and an unrelated copilot worktree). Every command ran with
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`. No paid API call was made. The scratch scripts are
in the session scratchpad: `web_run.py`, `frozen.py`, `stub_run.py`, `fallback_run.py`,
`record_price.py`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | one home for the sequence | **pass** | The assignment's grep prints 9 lines (the base printed 19). `pipeline.py:104,105,121,123,128,163,173,175` each call one of the eight functions once. The only other hit is `api/routes_valuation.py:420 defaults = derive_assumptions(normalised_financials)`, the assumptions page's defaults. `cli.py` has none |
| 2 | rule 2 | **pass** | `grep -n "def \|kwargs\|getattr" pipeline.py` gives 2 hits: `94:def adjust_financials(` and `109:def value_company(`. Both take named, typed arguments with no defaults. There is no `**kwargs`, no `getattr` and no function chosen at run time. The two dataclasses have typed fields and no defaults |
| 3 | the CLI does not move | **pass, with one moved display line** (see "Decisions", row 1) | `cli.py --session-file <abs WMT.json>`, base then head, live yfinance: both exit 0, Current $104.26, **Implied $28.02**, stderr identical. Diffing stdout with the `elapsed`/`Done in` lines removed leaves exactly `157a158 > ERP from history: S&P 500 annualized return 10.89% - risk-free 4.00% = 6.89%` and `172d172 <` the same line. The same result with frozen market data (`frozen.py ... cli`). With `--equity-risk-premium 0.05`, so that `run_capm` prints nothing, base and head are **byte-identical** apart from elapsed (diff exit 0), $36.29 at both. Filing inputs in the head output: revenue 2026 713,163, Net Debt 40,796, diluted shares 8,022M |
| 4 | the CLI with overrides does not move | **pass, same single moved line** | `build_overrides` takes **decimals**: the argparse group is titled "valuation overrides (decimals)" and passes values unconverted. `--risk-free-rate 4.5 --terminal-growth 2.0` would mean 450% and 200%, so I ran `--beta 1.0 --risk-free-rate 0.045 --terminal-growth 0.02`. Both exit 0, **Implied $15.00** at both, Beta 1.000, risk-free 4.50%, terminal growth 2.00%. Diff: only the ERP line, moved from 172 to 158 |
| 5 | the web pages do not move | **pass** | `frozen.py <root> wmt_price.pkl web`, base then head. Three HTML files compared: `GET /assumptions?session_file=<abs>`, then `POST /valuation` with the form's own fields parsed out of that page (cache hit), then the same POST again (cache miss, which exercises `adjust_financials` in `run_valuation`). **diff exit 0 for all three**, all status 200. The page shows Net Debt (40,796), Diluted Shares 8,022 and Implied $27.01. Each commit made the `fetch_price_data` call with `('WMT', 5, 'monthly')`: positional at the base, keyword at the head, so the same binding. **The live-yfinance run differed by 1 ($M) in EV, equity and PV of TV**, and it differed by the same amount between the hit and the miss **inside one head process**. Three fetches in one process returned `stock_returns.sum()` of 0.9095788982780555, 0.9095788986924012 and 0.9095788716466747 with the same current price, so that difference is yfinance noise and not code. That is why the comparison holds `PriceData` fixed |
| 6 | a market data failure still stops with its message | **pass** | `stub_run.py`. The stub is installed on `ingestion.price_fetcher` before anything imports it, and the script confirms the call site holds the stub: base `api.routes_valuation ... is stub: True`, head `pipeline ... is stub: True`. CLI at both: exit 1, stderr `ERROR: stub: no market data` (identical). Web at both: 200, error block `Error: stub: no market data`. Every CLI stdout line that differs: the base prints `>>> [6/10] Deriving projection assumptions`, the 13-line PROJECTION ASSUMPTIONS block (blank, rule, title, rule, the 8 assumption lines, blank) and `>>> [7/10] Fetching market data & running CAPM` before the error, and the head prints none of them. The rest differs only in elapsed seconds. This is the expected difference: stage 6 now prints after the market call |
| 7 | the gates do not get worse | **pass, with the red set named** | See "Measurements". Gate form: 2 failed, 1013 passed, 77 errors. Full: 3 failed, 1013 passed, 78 errors. **Every one of the 80 new reds has one cause**: a test patches `fetch_price_data` (78 at `api.routes_valuation`, 2 at `cli`) where it is no longer imported, so `monkeypatch.setattr` raises `AttributeError: ... has no attribute 'fetch_price_data'`. **Proof:** in a scratch copy of this tree I retargeted only those patch sites (22 substitutions in 6 test files, `routes_valuation`/`cli` → `pipeline` for `"fetch_price_data"` and `"calculate_wacc"`). The full suite then gave **2 failed, 1092 passed**, exactly the baseline, with the 2 red on purpose. ruff **4** (all BLE001). mypy with `pipeline.py` added: **6 errors in 3 files, 0 in `pipeline.py`** (the expected figure was 8, see "Decisions", row 3). Census over `models analysis api ingestion pipeline.py`: **65**, and 64 without `pipeline.py` (the `sharesOutstanding` site moved). `GET /` **200**. Guard **48/48** |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| I accepted the moved "ERP from history" line in criteria 3 and 4 and changed no code to suppress it | `analysis/capm.py:215`: `run_capm` prints to stdout. The assignment (step 3) requires `value_company` to run before stages 6 to 10 print, and `analysis/` is out of scope | The other way to keep identical output is to capture stdout around `value_company` in the CLI and replay it under stage 7. That hides where a print happens and also captures anything else written there. The line's content is unchanged at both commits. With an ERP supplied the output is byte-identical (criterion 3 row) |
| `value_company` stops with a `ValueError` when `latest_is is None`, and does not keep the CLI's conditional zero | Assignment step 2: the CLI's `if latest_is else 0` "is unreachable ... so it goes". The branch cannot run: with no income statements, `value_company` stops earlier, in `derive_assumptions` (executed: `IndexError`, the red-on-purpose `test_projector_rule3_red`), and `latest_year` raises `ValueError` if it is reached (executed). The stop is needed so mypy reports 0 errors in `pipeline.py` | A bare `latest_is.diluted_shares_outstanding`, as the route had it, carries over the two mypy errors from `routes_valuation.py:649,658`. An `assert` disappears under `-O`. A stop that names the year is rule 3 and moves no number |
| The mypy result is 6 errors in 3 files, not the assignment's "8 in 3" | The 2 removed errors are the old `routes_valuation.py:649` (union-attr on `diluted_shares_outstanding`) and `:658` (`IncomeStatement \| None` passed to `calculate_wacc`). Their code moved into `pipeline.py`, where the stop above narrows the type | The assignment asked for 0 errors in `pipeline.py`. That is only possible if those two go, so 8 cannot also hold |
| `ValuationRun` carries `latest_balance_sheet` | The CLI reads it afterwards for the display-only `total_debt` line, which stays unchanged (step 3). The assignment says `ValuationRun` holds every value either entry point reads afterwards | Looking the balance sheet up again in the CLI would be a second copy of a step the pipeline already took |
| `value_company` passes `fetch_price_data` its options by keyword | The CLI passed keywords, the route passed positionals. The binding is the same, as recorded in the criterion 5 call log | — |
| Comments in `pipeline.py` describe the old conditional zero and the `.get` fallback in words, not as code | Quoting them made the census grep count my comments (67) | A census that counts comments measures prose |
| Criterion 4 run with decimal flags | `build_overrides` passes the values unconverted, and the argparse group is titled "(decimals)". The assignment said to check this first | — |
| I deleted the now-unused imports from `cli.py` and `routes_valuation.py` rather than keeping them so test patches would still find the names | ruff F401. A test that patches a name nothing calls would pass without testing anything, for example `_refuse("fetch_price_data")` in `_session_route_helpers.py:256` | The tests go red loudly, and the tester retargets them (criterion 7 proof) |

No code was changed to reach a target number.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| income statements (none at all) | stops in `derive_assumptions` with a bare `IndexError`, before market data. It does not name the field: that is the pre-existing red test `test_projector_rule3_red.py`, the same at base | executed: `value_company(replace(fs, income_statements=[]), ...)` → `IndexError list index out of range` |
| `adjusted.latest_year` | stops: `ValueError` "holds no income statements, so there is no latest year" | `models/financial_statements.py:452-467`, executed |
| the latest income statement | stops: `ValueError` naming the ticker and year (`pipeline.py:143-148`). Unreachable, see above | code |
| `latest_is.diluted_shares_outstanding` == 0 | **defaults to `info.get("sharesOutstanding", 0) / 1e6` from yfinance** (`pipeline.py:159`). Moved as it was, by assignment step 2. It breaks rules 3 and 5, and `P3b-pipeline-stops` removes it. It is now recorded as `shares_from_market_data` | `fallback_run.py`: shares zeroed and a fake yfinance returning 8e9. CLI prints `Diluted shares from yfinance: 8,000M` under `[8/10]` at both commits, implied $28.10 at both, web shows 8,000 at both |
| `latest_bs` | `None` is passed to `calculate_wacc`, which decides (unchanged behaviour). The CLI's display line `if latest_bs else 0` is **a default to 0 for display**, kept by assignment step 3 (item 72, P3b) | `cli.py`, stage 8 |
| `price_data` | a failure in `fetch_price_data` stops the run with its message, CLI and web | criterion 6 |

## Measurements

- **Suite, full, base (`9e49bef` per STATUS, same code at `14a5608`):** 2 failed (`test_projector_rule3_red`, `test_routes_session_rule3_red`), 1092 passed.
- **Suite, full, head:** 3 failed, 1013 passed, 78 errors. Failure set: `test_projector_rule3_red` (on purpose); `test_cli_overrides.py::test_main_hands_the_flag_to_calculate_wacc[no-flag]` and `[flag]` (`cli` has no attribute `fetch_price_data`, patched at `test_cli_overrides.py:206`). Error set, all 78 with `AttributeError: <module 'api.routes_valuation'> has no attribute 'fetch_price_data'`, from fixtures at `_session_route_helpers.py:256,277`, `test_statements_ui.py:288,491,697,925`, `test_pass1_printed_lines.py:865`, `test_routes.py` (`wacc_calls` fixture :1098 and the other setattr sites), `test_route_context_keys.py:233,389,475`. By file: test_routes.py 30, test_routes_session.py 23 (and `test_routes_session_rule3_red.py` 1, red on purpose, now erroring at setup instead of failing at its assertion), test_statements_ui.py 14, test_route_context_keys.py 6, test_pass1_printed_lines.py 4. Several of these tests (for example the upload tests) do not call the pipeline themselves. They share a fixture that patches it.
- **Suite, gate form, head:** 2 failed, 1013 passed, 77 errors (the same set without the two `_rule3_red` files).
- **Retargeted scratch copy** (only the 22 patch sites changed to `pipeline`): **2 failed, 1092 passed**, the same as the base.
- ruff: 4 errors, all BLE001 (`api/routes_valuation.py:443,699`, `cli.py:1148`, `tests/test_e2e_all_googl.py:106`). The same 4 as before, at new line numbers.
- mypy (`models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports`): 6 errors in 3 files, 21 files checked, `grep -c ^pipeline.py` 0. Remaining: projector.py:172,225,235,345; routes_upload.py:28; routes_valuation.py:128.
- census: 65 with `pipeline.py`, 64 over the four folders alone (baseline 65).
- Figures: WMT CLI $28.02 (net debt 40,796, shares 8,022M); with overrides $15.00; with ERP 0.05 $36.29; fallback path $28.10. The same at base and head. The web page with the form defaults shows $27.01 at both.

## What I did not do

- I did not edit `tests/` (out of scope). The 80 tests that patch `fetch_price_data`/`calculate_wacc` at the old import site need retargeting to `pipeline` in `P3a-one-pipeline-tests`. The exact substitution that restores the baseline is above.
- I did not remove the share-count fallback, item 49 or item 72 (P3b).
- I did not touch `analysis/capm.py`'s stdout print (out of scope, see the finding below).
- The CLI table of line numbers in `entry-points.md` ("Measured at `P9b-session-web`") is left as it was. Its own header says the line numbers drift. I updated the line count (1,150) and the stage sentence.

## Findings for the orchestrator

1. **The assignment's grep for patch sites missed 21 of 22.** `monkeypatch.setattr(routes_valuation, "fetch_price_data", ...)` (the comma form) does not match `routes_valuation\.fetch_price_data`. The real red surface is 80 tests, not 1. The tests assignment should name the 6 files: `_session_route_helpers.py`, `test_statements_ui.py`, `test_pass1_printed_lines.py`, `test_cli_overrides.py`, `test_routes.py`, `test_route_context_keys.py`.
2. **`run_capm` prints to stdout** (`analysis/capm.py:215`, "ERP from history: ..."). A calculation function writing to stdout is why criterion 3 could not be met byte-for-byte, and the web route sends the same line to server stdout. A unit could move the market return into `CAPMResult` (if it is not already there) and let the CLI print it under stage 7.
3. **The web defaults are rounded before they reach the valuation.** `assumptions_page` formats each default as `f"{x*100:.1f}"`, the form posts those back as overrides, and a user who accepts every default gets **$27.01** where the CLI gets **$28.02** for the same filing. Executed with frozen market data: `value_company` with no overrides gives 28.02, and with the six ratios rounded to 0.1 points gives 27.01 (growth 4.897% becomes 4.9%, margin 4.25% becomes 4.3%, and so on). This is pre-existing and the same at base. It is a case of "a figure verified in the CLI is not verified on the web page" that this unit could not fix without moving a number. I could not find it in the backlog under "round".
4. **Historical FCFF differs between the CLI and the web for Walmart** (the assignment's known open item, measured). CLI, from the statements as extracted: 2024 17,109, 2025 12,854, 2026 16,985. Web, from the normalised statements: 2024 17,192, 2025 12,873, 2026 16,952. The cause is that normalisation changes the effective tax rate (2024 25.53% → 22.42%), which changes after-tax interest (1,998 → 2,081). Display only. Neither reaches the DCF.
5. **Live yfinance returns are not reproducible in the 9th digit** from one fetch to the next, even inside one process. That is enough to flip a $1M rounding in EV on the web page. Any future "no number moves" criterion should hold `PriceData` fixed (as `frozen.py` does) or compare to a tolerance.
6. mypy's expected figure in the assignment (8) is inconsistent with "0 in `pipeline.py`". The live figure is now 6 in 3 files. STATUS section 1 will need it.
