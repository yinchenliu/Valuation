---
id: P3a-one-pipeline
phase: 3 — unify the pipeline (backlog item 7; the user's "ok" of 2026-10-04 puts it after Phase 14)
agent: programmer
depends_on: [P14d-finance-leases]
---

# One module runs the valuation steps; `cli.py` and the web routes both call it, and no number moves (backlog item 7)

## Objective

`cli.py:main` and `api/routes_valuation.py:run_valuation` each call the same eight
functions in the same order: `partition_by_confidence`, `normalize_financials`,
`derive_assumptions`, `fetch_price_data`, `run_capm`, `calculate_wacc`, `project_fcffs`,
`run_dcf`. `assumptions_page` calls the first two again. Each copy chooses the share
count and the arguments itself. So a fix applied to one copy does not reach the other,
and a figure verified in the CLI is not verified on the web page (backlog item 7). Items
49 and 72 wait on this unit, so that each fix lands once.

When this unit is done, a new module, `pipeline.py`, holds the sequence once. The CLI
keeps its printing, and the routes keep their form parsing and templates. **No number
moves.** If one moves, the two copies disagreed before, and that disagreement is the
finding: stop and report it. Do not choose a side.

## What is already true — verify, do not redo

Measured by the overall lead at `6c528f0` (`P14d-finance-leases` accepted), macOS, with
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| gate | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` | 1092 passed |
| full suite | `.venv/bin/python -m pytest -q` | 2 failed (the two red on purpose), 1092 passed |
| lint, types | `ruff check .`; `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` | 4 errors, all `BLE001`; 8 errors in 3 files |
| census | the grep in `docs/2-rules/rules.md`, with `'--include=*.py'` quoted under zsh | 65 |
| Walmart, CLI | `cli.py --session-file extractions/WMT.json` | net debt 40,796; implied price $28.02 |
| the latest income statement exists | `models/financial_statements.py:452-467` | `latest_year` is the largest year with an income statement, and it raises when there is none. So `get_income_statement(latest_year)` is never `None` |
| tests that patch a pipeline call at an entry point | `grep -rn "cli\.\(fetch_price_data\|run_capm\|calculate_wacc\|derive_assumptions\|run_dcf\|project_fcffs\)\|routes_valuation\.\(fetch_price_data\|run_capm\|calculate_wacc\|derive_assumptions\|run_dcf\|project_fcffs\)" tests/` | 1, in `tests/unit/test_routes.py` |

`extractions/WMT.json` and `10K_filings/` are not in git (`.gitignore`). They are on this
machine.

## What to do

1. **Create `pipeline.py` at the repository root**, beside `cli.py` and `app.py`. Not in
   `analysis/`: the sequence calls `ingestion.price_fetcher.fetch_price_data`, and
   `analysis/` importing from `ingestion/` is backlog item 17. It holds two functions with
   typed signatures, named arguments and no `**kwargs` (rule 2), and one frozen dataclass
   for the result of each:
   - `adjust_financials(raw_financials: FinancialStatements, non_recurring:
     list[NonRecurringItem]) -> AdjustedFinancials`: `partition_by_confidence`, then
     `normalize_financials` with the applied half. `AdjustedFinancials` holds `applied`,
     `excluded` and `adjusted`.
   - `value_company(adjusted: FinancialStatements, overrides: ProjectionAssumptions,
     ticker: str, lookback_years: int, frequency: str) -> ValuationRun`:
     `derive_assumptions(adjusted, overrides)`, `fetch_price_data`, `run_capm`, the share
     count, the market cap, `calculate_wacc`, `project_fcffs` and `run_dcf`, with the
     arguments both copies pass today. `ValuationRun` holds every value either entry
     point reads afterwards: at least `assumptions`, `price_data`, `capm_result`,
     `shares`, whether the share count came from market data, `market_cap`,
     `wacc_result`, `projected` and `dcf_result`.
   **Reason:** backlog item 7; `docs/3-architecture/entry-points.md`, "The fix, when it
   is assigned". Two functions, not one: the CLI prints stages 3 to 5 before it fetches
   market data, and the web assumptions page uses the first function alone.
2. **The share count.** Read `latest_is.diluted_shares_outstanding` directly, as the web
   route does. The CLI's `if latest_is else 0` is unreachable (see the table above), so
   it goes, and no behaviour changes. Move the yfinance fallback for a share count of 0
   **as it is**, with its `info.get("sharesOutstanding", 0)`, and record in `ValuationRun`
   that it ran. The CLI prints its line "Diluted shares from yfinance: ..." from that
   record, in the same place. **Reason:** this unit moves no behaviour. The fallback
   breaks rules 3 and 5, and `P3b-pipeline-stops` removes it in one place.
3. **`cli.py`.** `main` calls `adjust_financials`, prints stages 2 to 5 as today, calls
   `value_company` with `build_overrides(args)`, `args.ticker`, `args.lookback_years`
   and `args.frequency`, then prints stages 6 to 10, the summary and the "not measured"
   block from the result. Keep every print function and every printed line. The
   display-only line `total_debt = latest_bs.total_debt if latest_bs else 0` stays in
   `cli.py`, unchanged (item 72, for `P3b`).
4. **`api/routes_valuation.py`.** `assumptions_page` and the cache-miss branch of
   `run_valuation` call `adjust_financials`. `run_valuation` calls `value_company` with
   the `ProjectionAssumptions` it builds today and the ticker from `_shown_identity`. The
   form parsing, the cache, `_shown_identity`, the chain builders and both template
   contexts do not change. The assumptions page keeps its own
   `derive_assumptions(normalised_financials)` call with no overrides: it fills the
   form's defaults and is not part of the valuation.
5. **Docs.** `docs/3-architecture/entry-points.md`: replace "Where they duplicate each
   other" with what `pipeline.py` holds and who calls it, and keep the list of the ways
   the two entry points still differ (form parsing, item 6; the provider choice, item 13;
   the CLI audit trail). Say that the share count fallback now has one home. Update the
   map row in `docs/INDEX.md` if its wording no longer fits.

## Files in scope

- `pipeline.py` (new)
- `cli.py`
- `api/routes_valuation.py`
- `docs/3-architecture/entry-points.md`
- `docs/INDEX.md` (the `entry-points.md` row only)
- your journal entry, `.agent/journal/<timestamp>-programmer-p3a-one-pipeline.md`

**Nothing else.**

## Out of scope

- `analysis/`, `models/`, `ingestion/`: no function changes. This unit moves call sites.
- `templates/`: the contexts do not change, so the templates do not.
- `tests/`: the tester, in `P3a-one-pipeline-tests`.
- The extraction step (`_extract_via_api`, `_extract_from_session_file`, `_run_extraction`,
  `_extract_from_files`): it stays in each entry point. Item 49 lives there, for `P3b`.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. **Make no paid API call.**
yfinance is free and the runs below use it. For each comparison, run the base and the
head back to back. If the market price differs between the two runs, run both again.
The base is a worktree at `6c528f0` (`git worktree add --detach <scratch dir> 6c528f0`),
run with this repository's `.venv/bin/python` and the absolute path of
`extractions/WMT.json`. Remove the worktree after use.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | one home for the sequence | no call to `partition_by_confidence`, `normalize_financials`, `fetch_price_data`, `run_capm`, `calculate_wacc`, `project_fcffs` or `run_dcf` in `cli.py` or `api/routes_valuation.py`; one `derive_assumptions(` call there, the assumptions page's defaults; each of the eight called once in `pipeline.py` | the grep below the table |
| 2 | rule 2 | every function in `pipeline.py` has typed, named arguments; no `**kwargs`, no function chosen at run time | `grep -n "def \|kwargs\|getattr" pipeline.py`, each hit explained |
| 3 | the CLI does not move | output identical but for the lines holding `elapsed` or `Done in`; $28.02 | `cli.py --session-file <WMT.json>` at the base and the head, diffed |
| 4 | the CLI with overrides does not move | the same | `cli.py --session-file <WMT.json> --beta 1.0 --risk-free-rate 4.5 --terminal-growth 2.0` at both, diffed (check the flag units in `build_overrides` first) |
| 5 | the web pages do not move | the HTML of `GET /assumptions?session_file=<WMT.json>` and of `POST /valuation` with `ticker=WMT`, `session_file=<WMT.json>` and the form's default fields is identical at both | a scratch script with `starlette.testclient.TestClient`, run at both, diffed |
| 6 | a market data failure still stops with its message | with `fetch_price_data` replaced by a stub that raises `ValueError("stub: no market data")`, the CLI exits 1 and prints `ERROR: stub: no market data`; the web result page shows the same text, at the base and at the head. List every line of the CLI output that differs. Stage 6 now prints after the market data call, so it no longer prints before this error: that is the one expected difference | a scratch script that patches the name at its import site in each commit |
| 7 | the gates do not get worse | gate 0 failed, or each red test named with its cause (expected: only a test that patches a pipeline call at its old import site, and the 2 red on purpose); ruff 4; mypy with `pipeline.py` added: 8 errors in 3 files, 0 in `pipeline.py`; census over `models analysis api ingestion pipeline.py`: 65 (the `sharesOutstanding` site moves from `api/` into `pipeline.py`); `GET /` 200; guard 48/48 | the gate commands in `docs/8-build/environment.md`, with `pipeline.py` added to mypy and to the census |

The command for criterion 1 (basic `grep`: `\|` is alternation, `(` is literal). At
`6c528f0` it prints 19 lines, 11 in `api/routes_valuation.py` and 8 in `cli.py`:

```
grep -n "\b\(partition_by_confidence\|normalize_financials\|derive_assumptions\|fetch_price_data\|run_capm\|calculate_wacc\|project_fcffs\|run_dcf\)(" cli.py api/routes_valuation.py pipeline.py
```


## Citations

- `docs/9-reference/refactor-backlog.md`, item 7, and items 49 and 72 (the next unit).
- `docs/3-architecture/entry-points.md`, "Where they duplicate each other" and "The fix,
  when it is assigned".
- `docs/8-build/phases.md`, Phase 3: "This phase must not change a number."
- `docs/2-rules/rules.md`, rules 2, 3 and 5.

## Known open items

- The CLI prints historical FCFF from the statements as extracted
  (`print_historical_fcff(financials)`). The web pages build it from the normalised
  statements (`_historical_fcff_by_year(normalised_financials)`). This is display, not
  the valuation, and this unit changes neither. Measure for Walmart whether the two tables
  differ, and report it in your entry.
- The share count fallback reads yfinance mid-pipeline (rules 3 and 5). It moves as it
  is. `P3b-pipeline-stops` removes it.

## Backlog items this unit is NOT fixing

Items 5, 6, 8, 13, 17, 26 and 62 in `api/routes_valuation.py`; items 49, 72 (the
`total_debt` display line) and 82 in `cli.py`; item 1 (the census); the share count
fallback. A reviewer must not raise them as findings against this unit.

## Round 2 amendment (overall lead)

The code review of round 1 (`.agent/journal/2026-10-05T0011-code_reviewer-p3a-one-pipeline.md`)
returned `changes_requested` with F1 to F4. The overall lead's answer to each, by number.
The programmer answers each by number in a new entry.

- **F1, blocker: the share count fallback. The overall lead widens the unit.** The
  fallback (`if shares == 0`, `yf.Ticker(ticker).info`, `info.get("sharesOutstanding",
  0) / 1e6`) breaks rules 3 and 5. The rules override this assignment, and no user
  decision exempts the lines. A share count of 0 is reachable: `diluted_shares` may be
  `[]` (only `net_income` is in `PASS1_YEAR_NEVER_EMPTY_FIELDS`). **Replace step 2:**
  delete the fallback and the `yfinance` import with it. When the latest year's
  `diluted_shares_outstanding` is not a finite number above 0, `value_company` stops with
  `ValueError`. The message names `diluted_shares`, the ticker and the fiscal year, and
  says that no share count is taken from market data (rule 5). Delete
  `shares_from_market_data` and the CLI's "Diluted shares from yfinance" line.
  **The one behaviour change of this unit:** a filing with no diluted share count used to
  get a price from a yfinance share count, and now stops, the same way in the CLI and on
  the web page. Every other path moves no number. `P3b-pipeline-stops` keeps items 49 and
  72 (the `total_debt` display line).
- **F2, major: the `assumptions` dict (rule 2). Not a finding against this unit.**
  `derive_assumptions` returns a bare `dict`, and `project_fcffs(financials, assumptions:
  dict)` takes it (`analysis/projector.py:329-332`). Both entry points passed it the same
  way before this unit, and `analysis/` is out of scope. The overall lead records it as
  backlog item 88. Change nothing.
- **F3, minor: criteria 3 and 4. The assignment's error.** `run_capm` prints "ERP from
  history: ..." from inside `analysis/capm.py:215`, and `value_company` now runs before
  stage 6 prints. So the line moves above the stage 6 banner. **Criteria 3 and 4 now
  expect:** identical but for the lines that hold `elapsed` or `Done in`, and the position
  of the "ERP from history" line, whose text is unchanged. Recorded as backlog item 89.
  Change nothing.
- **F4, note: what a stop hides.** In `docs/3-architecture/entry-points.md`, state in
  words which CLI stage output a stop now hides: a stop inside `adjust_financials` comes
  before stages 3 to 5 print; a stop inside `value_company` comes before stages 6 to 10
  print. The error message itself is unchanged. **Criterion 6 now also expects** this
  paragraph.

**Criteria that change with F1.** Criterion 7: the census over `models analysis api
ingestion pipeline.py` is **64**, because the `sharesOutstanding` site is deleted, not
moved. **A new criterion 8:** a copy of the Walmart session file whose 2026
`diluted_shares` is `[]` stops in the CLI (exit 1) and on the web result page, with the
same message, naming `diluted_shares`, `WMT` and 2026; with no network attempt to
yfinance's `Ticker.info` (stub `yfinance.Ticker` to raise, and show that it was not
called).

**The reviewer's two smaller items** are not this unit's. The overall lead records them:
the web price differs from the CLI price because the assumptions form rounds its defaults
(item 87), and `cli.py:205`'s literal `0.025` terminal growth default (item 90).
