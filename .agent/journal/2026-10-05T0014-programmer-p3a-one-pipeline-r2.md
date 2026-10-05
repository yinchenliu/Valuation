---
agent: programmer
assignment: P3a-one-pipeline
round: 2
status: complete
files_touched: [pipeline.py, cli.py, api/routes_valuation.py, docs/3-architecture/entry-points.md]
verdict:
---

# P3a-one-pipeline, round 2 — a filing with no diluted share count now stops (F1); what a stop hides is documented (F4)

## What I did

Round 2 follows the overall lead's "Round 2 amendment" in the assignment. This entry
covers only the round 2 changes. Round 1 is in
`.agent/journal/2026-10-04T2350-programmer-p3a-one-pipeline.md`, and the review is in
`.agent/journal/2026-10-05T0011-code_reviewer-p3a-one-pipeline.md`.

**F1.** I deleted the yfinance share count fallback from `pipeline.value_company`, along
with its inline `import yfinance` and its `info.get("sharesOutstanding", 0) / 1e6`. I also
deleted the `ValuationRun.shares_from_market_data` field and the CLI line "Diluted shares
from yfinance: ...". `value_company` now reads the latest year's
`diluted_shares_outstanding`. When that is not a finite number above 0, it raises
`ValueError`. The message names `diluted_shares`, the ticker and the fiscal year, and says
that no share count is taken from market data. The stop runs after `derive_assumptions`
and before `fetch_price_data`, so it makes no network call. To make that possible I moved
the `latest_year` / `latest_is` / `latest_bs` lookup, and the round 1 stop for
`latest_is is None`, from after `run_capm` to before `fetch_price_data`.

**F4.** `docs/3-architecture/entry-points.md` now has a paragraph, "What a stop hides in
the CLI". I also rewrote the share count paragraph and the `value_company` table row. In
`api/routes_valuation.py` I changed only the comment at the `value_company` call, which
used to say the yfinance fallback lived in the pipeline.

**F2 and F3:** no change, as the amendment directs.

## Answers to the review, by number

| # | Finding | Answer | Where |
|---|---|---|---|
| F1 | blocker: the yfinance share count fallback (rules 3 and 5) | **Fixed as the amendment specifies.** The fallback and the `yfinance` import are gone, and so are `shares_from_market_data` and the CLI's yfinance line. A share count that is not finite or not above 0 stops with `ValueError` naming `diluted_shares`, the ticker and the fiscal year, and says no share count is taken from market data (rule 5). It stops for 0, -5, NaN and inf (executed, below). This is the one behaviour change of the unit. Criterion 8 passes at the head, and at the base the same input reached `yfinance.Ticker('WMT')` | `pipeline.py:128-161`; `cli.py` stage 8; `api/routes_valuation.py:632-637`; `entry-points.md`, "The share count comes from the filing" |
| F2 | major: the `assumptions` dict | **No change**, per the amendment. The overall lead recorded it as backlog item 88. `ValuationRun.assumptions: dict` and the `assumptions["tax_rate"]` / `["terminal_growth_rate"]` reads are as in round 1 | — |
| F3 | minor: the "ERP from history" line moves | **No change**, per the amendment (backlog item 89). Criteria 3 and 4 were re-run against the amended expectation: the only difference is that line's position, and its text is unchanged | criteria 3 and 4 below |
| F4 | note: what a stop hides | **Documented.** `entry-points.md`, "What a stop hides in the CLI": a stop inside `adjust_financials` comes after the stage 3 banner and before stage 3's items and stages 4 and 5. A stop inside `value_company` comes before stages 6 to 10 (assumptions, CAPM result, WACC). Each error message is the one the failing function raised before the move, and the web result page is unchanged | `docs/3-architecture/entry-points.md` |

## Done-criteria

Every command ran with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. No paid API call was made.
The base is a worktree at `6c528f0` in the session scratchpad
(`git worktree add --detach <scratch>/base6c 6c528f0`), run with this repository's
`.venv/bin/python` and the absolute path of `extractions/WMT.json`. I removed it after
the runs: `git worktree list` shows only main and the unrelated copilot worktree. The
scratch scripts are in
`/private/tmp/claude-501/-Users-yinchenliu-Documents-Git-DCF-Valuation/8efc320b-f9b1-41b6-a3bf-e1ac55cf5be8/scratchpad/`:
`rev_run.py` (the reviewer's, reused), `noshares_run.py` (new, criterion 8),
`retarget.py`, and `wmt_price.pkl` (one recorded `PriceData`).

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | one home for the sequence | **pass** | The assignment's grep prints 9 lines: `pipeline.py:103,104,126,163,168,177,187,189`, one per function, and `api/routes_valuation.py:420 defaults = derive_assumptions(normalised_financials)` (the form's defaults). `cli.py`: none |
| 2 | rule 2 | **pass** (the grep). F2 is not this unit's, per the amendment | `grep -n "def \|kwargs\|getattr" pipeline.py` → `93:def adjust_financials(`, `108:def value_company(`. Both have named, typed arguments with no defaults. There is no `**kwargs`, no `getattr`, and no function chosen at run time |
| 3 | the CLI does not move (amended by F3) | **pass** | `cli.py --session-file <abs WMT.json>`, live yfinance, base then head back to back. Both exit 0 with identical stderr. Diffing stdout without the `elapsed`/`Done in` lines leaves only `157a158 > ERP from history: S&P 500 annualized return 10.89% - risk-free 4.00% = 6.89%` / `172d172 <` the same line. The head prints Net Debt 40,796, Diluted Shares 8,022M, Current Price $104.26 and **Implied $28.02**, the same as the base |
| 4 | the CLI with overrides (amended by F3) | **pass** | `--beta 1.0 --risk-free-rate 0.045 --terminal-growth 0.02`. `build_overrides` takes decimals (argparse group "(decimals)"), as recorded in round 1. Both exit 0 with identical stderr and **Implied $15.00**. The diff is only the ERP line (`risk-free 4.50% = 6.39%`), moved from 172 to 158 |
| 5 | the web pages do not move | **pass** | `rev_run.py <root> web <WMT.json> wmt_price.pkl <out>` at base and head. GET /assumptions, then POST /valuation twice with the page's own form fields (cache hit, then cache miss). `cmp`: `web_1`, `web_2` and `web_3` are identical. All return 200, and both POSTs show $27.01. Calls: base `('WMT', 5, 'monthly')` positional, head `('WMT',)` plus `lookback_years=5, frequency='monthly'`, which bind the same |
| 6 | a market data failure still stops (and, from F4, the paragraph) | **pass** | `rev_run.py ... cli_stub`: base and head both exit 1 with stderr `ERROR: stub: no market data`. `rev_run.py ... web_stub`: all 3 pages identical between commits (`cmp`), and `stub: no market data` is in the error block. **Every CLI stdout line that differs:** the base prints `>>> [6/10] Deriving projection assumptions`, the 14-line PROJECTION ASSUMPTIONS block (two blank lines, rule, title, rule, 8 assumption lines, blank) and `>>> [7/10] Fetching market data & running CAPM` before the error, and the head prints none of them. The rest differs only in elapsed seconds. The F4 paragraph is in `entry-points.md` |
| 7 | the gates do not get worse | **pass, with the red set named** | **Gate form**: 2 failed, 1013 passed, 77 errors. **Full**: 3 failed, 1013 passed, 78 errors. **The failure set is identical to round 1's** (`diff` of the sorted FAILED/ERROR ids: no difference, 81 ids). Their single cause, as in round 1: tests patch `fetch_price_data`/`calculate_wacc` on `api.routes_valuation`/`cli`, where they are no longer imported. **Proof:** in a scratch copy of the tree with only the 22 patch sites retargeted to `pipeline` (`retarget.py`), the full suite gives **2 failed, 1092 passed**, and the two failures are `test_projector_rule3_red` and `test_routes_session_rule3_red` (red on purpose). So no test depended on the deleted fallback. ruff: **4**, all BLE001. mypy (`models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports`): **6 errors in 3 files, 0 in `pipeline.py`** (`analysis/projector.py:172,225,235,345`, `api/routes_upload.py:28`, `api/routes_valuation.py:128`, the same six as round 1, a figure the reviewer agreed). **Census** over `models analysis api ingestion pipeline.py`: **64**, because the `sharesOutstanding` site is deleted. `GET /` **200**. Guard **48/48** |
| 8 (new) | a filing with no diluted share count stops, with no yfinance call | **pass** | `WMT_noshares.json` is a copy of `extractions/WMT.json` with the 2026 filing's 2026 `diluted_shares` set to `[]` (it was `[{'label': 'Diluted', 'value': 8022, 'page': 22}]`, the only 2026 entry). `noshares_run.py` replaces `yfinance.Ticker` with a stub that records the call and raises, and `fetch_price_data` with one that records the call and returns the frozen data. **Head CLI:** exit 1, stderr `ERROR: diluted_shares is 0.0 for 'WMT' in fiscal year 2026: the implied share price needs the latest year's diluted share count as printed in the filing, a finite number above 0. No share count is taken from market data (rule 5); supply the count printed in the filing.` The record shows `yfinance.Ticker=[] fetch_price_data=[]`. **Head web** (POST /valuation): 200, error block `Error: ` followed by the same message, no implied price, `yfinance.Ticker=[] fetch_price_data=[]`. **Base, for contrast:** the CLI exits 1 with `ERROR: stub: yfinance.Ticker was called`, the web page shows the same, and the record shows `yfinance.Ticker=[('WMT',)]`. The base reached the fallback. The head does not |

**The stop, for every value it refuses.** In-process, `value_company(WMT, ProjectionAssumptions(), ticker="WMT", 5, "monthly")`, with the latest year's `diluted_shares_outstanding` set to 0.0, -5.0, nan and inf in turn. Each raises `ValueError` starting `diluted_shares is <v> for 'WMT' in fiscal year 2026`, and `fetch_price_data` was called 0 times.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The share count stop runs before `fetch_price_data`, after `derive_assumptions` | Criterion 8 requires no attempt to reach yfinance. The share count is a filing figure, so a stop on it should not wait on the network or spend a market data fetch whose result would be thrown away | After `run_capm`, where the fallback was, the stop would still be correct, but each zero-share run would fetch market data first. It goes after `derive_assumptions`, so that function's stops (for example the red-on-purpose `IndexError` for no income statements) still come first, as before |
| The `latest_year`/`latest_is`/`latest_bs` lookup and the round 1 `latest_is is None` stop moved up with it | The share count is read from `latest_is`. When income statements exist, the lookup cannot raise (`models/financial_statements.py:452-467`), so moving it changes no output on any path that values a company. The one ordering change: a filing with no share count **and** a market data failure now reports the share count, where the base reported the market error. Both are stops, and no number is involved | — |
| The test is `math.isfinite(shares) and shares > 0`, not `shares == 0` | The amendment says "not a finite number above 0". This is the same test `run_dcf` applies to `diluted_shares` (`analysis/dcf.py:187`). A comparison alone lets NaN through | `run_dcf` would already stop on 0, but only after the fallback had run, and its message does not name the year or say the count was not taken from market data |
| The message uses the `ticker` argument, not `adjusted.ticker` | The ticker argument is the one being priced, and the CLI and the route both pass it. For WMT the two are the same | — |
| The 0 the stop sees is "not supplied", not a printed zero | `figure_from_printed_lines` turns an empty `diluted_shares` list into 0 (`ingestion/claude_extractor.py:512-525`), and `IncomeStatement.diluted_shares_outstanding` defaults to `0.0` (`models/financial_statements.py:155`, backlog census). A filing cannot print a diluted share count of 0 for a company with a share price, so both readings lead to a stop | Telling "printed 0" apart from "not printed" needs `models/` or `ingestion/`, which are out of scope |

No code was changed to reach a target number.

## Rule 3 — what stops, and what does not

The values `value_company` reads after round 2.

| Value read | If it were missing | Evidence |
|---|---|---|
| income statements (none at all) | stops in `derive_assumptions` with a bare `IndexError`. It does not name the field. This is the pre-existing red test `test_projector_rule3_red`, unchanged | round 1, executed. Still in the red set above |
| `adjusted.latest_year` | stops: `ValueError` "holds no income statements" | `models/financial_statements.py:452-467` |
| the latest income statement | stops: `ValueError` naming the ticker and year. Unreachable | `pipeline.py:137-142` |
| **`latest_is.diluted_shares_outstanding`** 0 / negative / NaN / inf | **stops: `ValueError` naming `diluted_shares`, the ticker and the year; no market data call** | criterion 8, and the in-process run over 0, -5, nan and inf |
| `latest_bs` | `None` is passed to `calculate_wacc`, which decides (unchanged). The CLI's display line `total_debt = latest_bs.total_debt if latest_bs else 0` **defaults to 0 for display**. It is kept by assignment step 3 and the amendment (item 72, `P3b`) | `cli.py`, stage 8 |
| `price_data` | a failure in `fetch_price_data` stops with its message, in the CLI and on the web | criterion 6 |
| `assumptions["tax_rate"]`, `["terminal_growth_rate"]` | a `KeyError`, with no type check (F2, backlog item 88, not this unit's) | `pipeline.py:183,193` |

## Measurements

- Suite, head, full: 3 failed, 1013 passed, 78 errors. Gate form: 2 failed, 1013 passed,
  77 errors. The sorted id set equals round 1's exactly (81 ids). Retargeted scratch copy:
  2 failed (the two `_rule3_red`), 1092 passed, which equals the base.
- ruff 4 (BLE001). mypy 6 errors in 3 files, 21 files checked, 0 in `pipeline.py`.
- Census: 64 over `models analysis api ingestion pipeline.py` (65 at the base; the
  `sharesOutstanding` line is deleted).
- `GET /` 200. Guard 48/48.
- Figures, base = head: WMT CLI $28.02 (Net Debt 40,796, shares 8,022M printed on page 22
  of the 2026 10-K, current price $104.26). With the overrides, $15.00. Web with the form
  defaults, $27.01 (item 87). Zero-share copy: a stop at the head; at the base, a call to
  `yfinance.Ticker('WMT')`.

## What I did not do

- `docs/INDEX.md`: not edited this round. The round 1 row ("the one valuation sequence
  both call (`pipeline.py`), and how the two still differ") still fits.
- `tests/`: not edited. The tester must retarget the 22 patch sites (round 1, finding 1)
  and can test the new stop.
- F2 (`analysis/projector.py`), F3 (`analysis/capm.py`'s print), items 49 and 72: out of
  scope per the amendment.

## Findings for the orchestrator

1. **Tests for `P3a-one-pipeline-tests`.** There is no test yet for the new stop. Testable
   facts: `value_company` raises `ValueError` whose message contains `diluted_shares`,
   the ticker and the year when the latest `diluted_shares_outstanding` is 0, negative,
   NaN or inf. It calls neither `fetch_price_data` nor `yfinance.Ticker`. The CLI exits 1
   with `ERROR: diluted_shares is ...`, and the web result page shows the message. The
   scratch `noshares_run.py` shows the setup.
2. **Six e2e test scripts and a helper still carry their own copy of the fallback**, as
   `info.get("sharesOutstanding", 0) / 1e6`: `tests/test_e2e_abbv.py:175`,
   `test_e2e_abbv_3years.py:204`, `test_e2e_lly.py:175`, `test_e2e_googl_3years.py:219`,
   `test_e2e_all_googl.py:74`, `test_e2e_phase2_googl.py:123`, `tests/_run_lly_dcf.py:31`.
   Each runs the sequence itself rather than through `pipeline.py`. So they do not test
   what the product does, and they keep the rule 5 pattern alive outside the census
   (which does not scan `tests/`). They are the tester's files.
3. **`IncomeStatement.diluted_shares_outstanding: float = 0.0`** (`models/financial_statements.py:155`)
   and `figure_from_printed_lines` returning 0 for `[]` mean that "not printed" and
   "printed 0" are the same bytes when they reach the pipeline. The new stop treats both
   as missing, which is correct for a share count. A field that keeps "not printed"
   apart (for example `None`) would let the stop say which one happened. That is a
   `models/` and `ingestion/` unit.
4. The mypy figure stays at **6 in 3 files** (the reviewer agreed in round 1). STATUS
   section 1 shows 8.
