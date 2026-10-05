---
agent: tester
assignment: P3a-one-pipeline-tests
round: 1
status: complete
files_touched: [tests/unit/_session_route_helpers.py, tests/unit/test_cli_overrides.py, tests/unit/test_pass1_printed_lines.py, tests/unit/test_route_context_keys.py, tests/unit/test_routes.py, tests/unit/test_statements_ui.py, tests/unit/test_pipeline.py]
verdict: pass
---

# P3a-one-pipeline-tests: 22 patch sites now target `pipeline`, and a new `test_pipeline.py` locks the wiring, the share count stop and one price for both entry points

Unit under test: `P3a-one-pipeline` at `dc81088`. Every command ran with
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`. No paid API call and no network call was made. The
new tests replace `socket` connects, `yfinance.Ticker` and `pipeline.fetch_price_data`
with stubs. Nothing is committed.

## What I did

**Step 1: repair.** I searched `tests/` myself and found **22 sites in 6 files**, the same
count as the programmer. 21 are `monkeypatch.setattr(<routes_valuation|cli>,
"<fetch_price_data|calculate_wacc>", ...)`, two of them split over lines in
`test_route_context_keys.py`. The 22nd is the read `real = routes_valuation.calculate_wacc`
at `test_routes.py:1101`. `tests/` has no `mock.patch("cli....")` string form. Each site now
targets `pipeline`, and each file gains `import pipeline`. The per-file counts are:

| File | Sites |
|---|---|
| `_session_route_helpers.py` | 2 |
| `test_statements_ui.py` | 4 |
| `test_pass1_printed_lines.py` | 1 |
| `test_cli_overrides.py` | 2 |
| `test_route_context_keys.py` | 3 |
| `test_routes.py` | 10 |

**No old test asserted the yfinance fallback**, so I changed no assertion and no test
became the exception the assignment allowed for. I also rewrote one stale comment,
`_session_route_helpers.py:189-191`. It pointed at the deleted fallback at
`api/routes_valuation.py:625-628`, and it now points at the share count stop. The change is
to a comment only.

**Steps 2 to 5: the new file `tests/unit/test_pipeline.py`, with 17 tests.** I wrote every
expected value, and the hand arithmetic behind it, into the docstrings before the first
run. The first run gave 17 passed. After that run I edited no expected value. My only
edit was to remove one unused import that ruff flagged.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | gate form, 0 failed | **pass** | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` gave **1109 passed**, 0 failed. Before the repair: 2 failed, 1013 passed, 77 errors |
| 2 | full suite, exactly the 2 red on purpose | **pass** | `.venv/bin/python -m pytest -q` gave **2 failed, 1109 passed**. The two are `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`. Before the repair: 3 failed, 1013 passed, 78 errors |
| 3 | no assertion weakened | **pass** | In `git diff tests/`, every `-` line is a patch target (`routes_valuation`/`cli` → `pipeline`) except the two lines of the stale comment. Every `+` line is the same target, `import pipeline`, or the reworded comment. No assertion line changed, and no test was skipped or marked xfail |
| 4 | new tests can fail | **pass** | Mutants in a scratch copy (`<scratchpad>/mut/mutants.py`), run on `test_pipeline.py`. The unmutated copy passes 17. **Restore the yfinance fallback** (`if shares == 0: yf.Ticker(ticker).info...sharesOutstanding / 1e6`, placed before the stop): **3 red**, stop[zero], the CLI stop and the web stop. **Drop the share count stop**: **6 red**, stop[zero/negative/nan/inf], the CLI stop and the web stop. **`beta_override=None` to `run_capm`**: **2 red**, the overrides-reach-CAPM test and the DCF value test. **Normalise with all items**: **1 red**, the high/medium-applied, low-excluded test |
| 5 | clean checkout | **pass** | `git worktree add --detach <scratchpad>/wt dc81088`, with my 7 test files copied in. Neither `extractions/` nor `10K_filings/` exists there. The gate gave **1104 passed, 5 skipped, 0 failed**: the 5 skips are the existing `skipif(not path.exists())` tests. I removed the worktree, and `git worktree list` shows main and the copilot worktree |
| 6 | lint and types | **pass** | `ruff check .`: **4**, all BLE001 (`api/routes_valuation.py:443,701`, `cli.py:1144`, `tests/test_e2e_all_googl.py:106`, the last pre-existing). 0 new in `tests/`. `mypy models analysis ingestion api config.py app.py --ignore-missing-imports`: **6 errors in 3 files**, and the same with `pipeline.py` added (21 files checked) |
| 7 | two counts | **pass** | below |

## Expected values — testers only

All assertions in `tests/unit/test_pipeline.py`. The inputs are hand-built: one year,
2024. Revenue 1,000, COGS 600, SG&A 200, R&D 50, no interest, diluted shares 100. The
balance sheet has cash 100, no debt line, and both NCI lines at 0. The overrides supply
every input: 1 year, g 0.02, growth 0.10, margin 0.20, tax 0.25, capex 0.05, D&A 0.05,
NWC 0.01, rf 0.04, ERP 0.05, beta 1.2, lookback 3, frequency `daily`. The stub price is
20.0, and the stub's stock returns equal its market returns.

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| `applied == [high, medium]`, `excluded == [low]` | the list identities | `partition_by_confidence` contract (`analysis/normalizer.py:99-104`), with the items built by hand |
| adjusted SG&A | 190 | hand: 200 − 10 (high add_back on an expense line) |
| adjusted COGS | 605 | hand: 600 + 5 (medium remove: earnings −5, field sign −1) |
| adjusted R&D | 50 | hand: the low item is excluded, so the field is unchanged (applied, it would be 20) |
| adjusted EBIT | 155 | hand: 1000 − 605 − 190 − 50 = 155 = 150 + 10 − 5 |
| raw COGS, SG&A, R&D after the call | 600, 200, 50 | the inputs as written. The raw `IncomeStatement` is the same object |
| raw EBIT | 150 | hand: 1000 − 600 − 200 − 50 |
| market data call | `("TST", 3, "daily")` | the caller's arguments, chosen to differ from the defaults |
| `shares`, `dcf_result.diluted_shares` | 100 | the filing figure as written |
| `market_cap` | 2,000 | hand: 20.0 × 100 |
| `dcf_result.current_price` | 20.0 | the stub |
| beta, rf, ERP | 1.2, 0.04, 0.05 | the overrides. A regression on identical series would give 1.0 (identity, `strategy.md` §1) |
| cost of equity | 0.10 | hand: 0.04 + 1.2 × 0.05 |
| debt weight, equity weight | 0, 1 | identity: total debt 0, so D/(D+E) = 0 |
| WACC | = cost of equity = 0.10 | identity: debt weight 0 |
| projected years | [2025] | hand: latest 2024 + 1 |
| projected revenue | 1,100 | hand: 1000 × 1.10 |
| projected FCFF | 154 | hand: NOPAT 220 × 0.75 = 165; +55 − 55 − 11 |
| PV of FCFF | 140 | hand: 154 / 1.10 |
| TV | 1,963.5 | hand: 154 × 1.02 / 0.08 = 157.08 / 0.08 |
| PV of TV | 1,785 | hand: 1963.5 / 1.10 |
| net debt | −100 | hand: 0 − 100 |
| implied share price | 20.25 | hand: (140 + 1785 + 100) / 100 |
| result price and EV = `run_dcf` on the result's own `projected` and `wacc_result` | equal | closed-form check (assignment step 3) |
| a stubbed `ValueError("stub: no market data")` | re-raised unchanged | the stub's own text |
| no balance sheet | `ValueError` "balance_sheet is None" | `calculate_wacc` contract (`analysis/wacc.py:417-418`) |
| share count 0 / −5 / NaN / inf | `ValueError` containing `diluted_shares`, `TST`, `2024`; 0 price calls; 0 `Ticker` calls | the assignment's requirement, step 4 |
| CLI, session file with 2024 `diluted_shares: []` | `SystemExit` code 1. stderr holds `ERROR: diluted_shares`, `'TST'`, `fiscal year 2024`. 0 price calls, 0 `Ticker` calls | the assignment's requirement. I ran `cli.py` as `__main__` (via `runpy`) so that its own exit handler is what is tested |
| web, the same file | error block holds `diluted_shares`, `'TST'`, `fiscal year 2024`. No "Implied Share Price". 0 price calls, 0 `Ticker` calls | the assignment's requirement |
| form fields ÷ 100 = CLI flags | equal, field by field | hand: each pair is written side by side in the test |
| CLI price = web price (the cache-miss branch), CLI WACC = web WACC, shares equal, both two-decimal displays equal | equal (rel 1e-12) | **identity**: one file, one set of overrides, one stub. I captured each `DCFResult` by wrapping `pipeline.run_dcf`. Both runs priced `("TST", 5, "monthly")` |

**Two counts, with their units.**

- **Accuracy.** The new file holds **77 of 77 `assert` statements** and **7 of 7
  `pytest.raises` blocks**, and all pass. Of the assertions on a number, **30 of 30**
  match a hand-derived or identity-derived expectation. That is 25 from the rows above,
  "adjusted SG&A" through "implied share price"; 2 from the `run_dcf` equality (price and
  EV); and 3 from the CLI = web check (price, WACC, shares). By tests that is **17 of 17**: 14 functions, one of them run 4 times.
  The retargeted old tests are **1092 of 1092** passing, with no assertion changed.
- **Coverage**, measured with `--cov=pipeline --cov-branch`:
  - Functions in `pipeline.py`: **2 of 2** (`adjust_financials`, `value_company`). The
    new file alone covers both.
  - Statements: **47 of 48**.
  - Branches: **3 of 4**. The one missed statement and branch is `pipeline.py:138`, the
    `latest_is is None` stop, which cannot be reached. `latest_year` is defined as the
    largest year that has an income statement, and `derive_assumptions` reads every
    year's income statement before this line.
  - Lines the unit added to the entry points: the gate's coverage (`--cov=cli
    --cov=api.routes_valuation --cov-branch`) executes all of them. These are `cli.py:64,
    1012-1017, 1029-1047, 1058, 1060, 1067` and `api/routes_valuation.py:13, 29, 402-404,
    409-412, 590-597, 632-643, 645-649, 657`. None is in the missing list
    (`cli.py: 999-1000, 1082->1089, 1128, 1142-1143`, all pre-existing lines).

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| an item's `confidence` (unrecognised) | stops: `ValueError` naming `confidence` and the value | `test_adjust_financials_stops_on_an_unrecognised_confidence` |
| an item's `year` (no statement for it) | stops: `ValueError` naming `year 2019` and "no income statement" | `test_adjust_financials_stops_on_an_item_year_with_no_statement` |
| latest `diluted_shares_outstanding` (0, negative, NaN, inf) | stops: `ValueError` naming `diluted_shares`, the ticker and the year, before any market call | the 4 parametrised tests, plus the CLI and web tests |
| `fetch_price_data` failure | stops with its own message, unchanged | `test_value_company_passes_a_market_data_failure_through_unchanged` |
| latest balance sheet | stops: `ValueError` "balance_sheet is None" | `test_value_company_stops_on_a_missing_latest_balance_sheet` |
| latest income statement | **not lockable**: `pipeline.py:137-142` cannot be reached (see coverage). It is a stop, not a default | — |
| no income statements at all | stops with a bare `IndexError` in `derive_assumptions` before the pipeline names anything. Already the red-on-purpose `test_projector_rule3_red.py`, unchanged | full-suite failure set |
| `assumptions["tax_rate"]`, `["terminal_growth_rate"]` | `KeyError`, untyped (F2, user-accepted until backlog item 88). Not locked: no test asserts this dict's shape | `pipeline.py:183,193` |

No stop path in this unit defaults where it should raise. I asserted no fallback.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The CLI stop runs `cli.py` as `__main__` in the same process (`runpy.run_path`) | "exit 1, the message printed" lives in the `if __name__ == "__main__"` handler (`cli.py:1139-1146`), not in `main()` | A subprocess would lose the stubs, so the restored-fallback mutant could reach the network. Calling `cli.main()` alone would not test the exit code |
| The CLI and web stop tests use a real session file plus a PDF written under `tmp_path` by `_session_route_helpers` | Both entry points go through their real loaders. Nothing reads `extractions/` | — |
| The one-price identity captures `DCFResult` by wrapping `pipeline.run_dcf` | It gives the exact floats from both entry points without parsing HTML. The test also compares the two-decimal displays | Spying on `value_company` would not work: both entry points import it by name |
| The identity test, not hand arithmetic, carries the CLI = web check | This session's numbers give a WACC that is not round (debt 425 against a market cap of 4,320). The hand arithmetic lives in the `value_company` tests with round inputs | Pasting a computed price would be the photograph the rules forbid |
| Beta override 1.2, with the stub's stock returns equal to its market returns | A regression on identical series gives exactly 1.0, so a dropped override shows up as 0.09 against 0.10 | — |

No code change was made to reach a number. I made no implementation change.

## Measurements

- Failure sets. Before: 3 failed + 78 errors (the moved-name patch sites, plus
  `test_projector_rule3_red`). After: `{test_projector_rule3_red::…no_income_statements…,
  test_routes_session_rule3_red::…cache_hit_stops}`.
- Gate 1109 passed (1092 old + 17 new). Clean worktree: 1104 passed, 5 skipped.
- ruff 4 (BLE001, 0 new). mypy 6 errors in 3 files.

## What I did not do

- I did not change the e2e scripts (`tests/test_e2e_*.py`, `tests/_run_lly_dcf.py`). They
  still carry their own `info.get("sharesOutstanding", 0) / 1e6` (programmer finding 2).
  The assignment does not ask for it, and they are scripts with no assertions.
- I did not edit the module docstring of `_session_route_helpers.py` (line 19). It still
  says `open_closed_client` replaces "the route module's `fetch_price_data`". The code now
  patches `pipeline`. I left it because it is wording only.

## Findings for the orchestrator

1. **The rule 5 pattern survives in `tests/`.** Seven e2e scripts and helpers still run
   the sequence themselves, with their own yfinance share count fallback:
   `tests/test_e2e_abbv.py:175`, `test_e2e_abbv_3years.py:204`, `test_e2e_lly.py:175`,
   `test_e2e_googl_3years.py:219`, `test_e2e_all_googl.py:74`,
   `test_e2e_phase2_googl.py:123`, `tests/_run_lly_dcf.py:31`. An assignment could point
   them at `pipeline.value_company`, or delete them. They are outside the census.
2. **`pipeline.py:137-142` cannot be reached**, so no test can lock it. If `latest_year`
   ever changes, a test can be written then.
3. **The stale docstring line** at `tests/unit/_session_route_helpers.py:19` (see above)
   needs a one-line fix in the next tests unit.
4. No `*_rule3_red.py` test has gone green. Both remain red for their stated reasons, so
   none needs to move (backlog item 24 check).
