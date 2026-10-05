---
agent: code_reviewer
assignment: P3a-one-pipeline
round: 2
verdict: changes_requested
---

# Review of P3a-one-pipeline, round 2

Programmer entry: `.agent/journal/2026-10-05T0014-programmer-p3a-one-pipeline-r2.md`
Round 1 review: `.agent/journal/2026-10-05T0011-code_reviewer-p3a-one-pipeline.md`

What I reviewed: `git diff 14a5608` (cli.py, api/routes_valuation.py,
docs/3-architecture/entry-points.md, docs/INDEX.md) plus the untracked `pipeline.py`. I checked it
against the assignment's `## Round 2 amendment (overall lead)`. Two untracked files belong to the
orchestrator, so neither is a scope finding: `.agent/journal/INDEX.md` and the new
`.agent/assignments/P3a-one-pipeline-tests.md`. Every command ran with
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`, and no paid call was made. I used my own scratch scripts in
`<scratchpad>/rv2/` (`ns.py`, the retargeting snippet). I put the base worktree at `6c528f0` in
`<scratchpad>/rv2/base` and removed it afterwards: `git worktree list` shows main and the
unrelated copilot worktree.

## The guard checks

I ran these over `pipeline.py cli.py api/routes_valuation.py`.

| Check | Result |
|---|---|
| conditional zero: `if … else 0.0` | `cli.py:1061` `total_debt = latest_bs.total_debt if latest_bs else 0`. The line is unchanged (item 72, excluded by the assignment and the amendment). `cli.py:205` `... else 0.025` is untouched (item 90) |
| lookup with a fallback: `.get(k, 0)` | clean. The round 1 hit `info.get("sharesOutstanding", 0)` has been **deleted**. `routes_valuation.py:357` is `@router.get`, a false hit |
| bare or-default: `or 0.0` | clean |
| money field defaulted to zero: `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | `cli.py:701`, untouched. It reads a field name from the file's own literals |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (models/ analysis/ api/ pipeline.py) |
| `yfinance` / `sharesOutstanding` in scope | comments only (`pipeline.py:120,148-149`, `routes_valuation.py:637`). No import, no call |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `adjusted.latest_year` | yes, `ValueError` | `models/financial_statements.py:452-467` |
| latest income statement | yes, but the branch is unreachable | `pipeline.py:137-142` |
| `latest_is.diluted_shares_outstanding` that is not a finite number above 0 | **yes**: `ValueError` naming `diluted_shares`, the ticker and the year, saying that no market share count is used. It runs before `fetch_price_data` | `pipeline.py:153-161`. Executed: criterion 8 below |
| `latest_bs` None | passed to `calculate_wacc`, which decides. Unchanged | `pipeline.py:130,180` |
| `fetch_price_data` failure | stops with its message in the CLI (exit 1) and on the web page. I spot-checked it at the head with a raising stub | `ns.py` on the real WMT.json: `ERROR: stub: fetch_price_data was called`, and the web error block shows the same text |
| assumption keys `tax_rate`, `terminal_growth_rate` | a `KeyError`. The dict is untyped | `pipeline.py:82,183,187,193`. **F2, carried** |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | yes. `shares` now comes only from the filing, which is in millions, so the `/ 1e6` conversion is gone along with the yfinance path. `market_cap` = price × shares (M) is in $M |
| percentages converted at the route boundary, once | the form parsing is untouched |
| falsy not treated as missing | the round 1 `if shares == 0` is gone. The new test is `math.isfinite(shares) and shares > 0`, which refuses 0, negative values, NaN and inf. The programmer's entry explains that 0 here is the extractor's encoding of `[]` |
| `analysis/` imports no `ingestion/`, `api/` or model client | unchanged. `pipeline.py` sits at the root |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 3 | CLI unchanged (amended: only the ERP line moves) | only the ERP line moves, $28.02 | Base and head were run live, back to back, three times. **Run 1** also showed `PV of Terminal Value 214,820M` vs `214,819M`, but base run 1 differs the same way from base run 2, so that is live market noise (the assignment's "run both again"). **Runs 2 and 3**: after the `elapsed`/`Done in` lines are removed, the only diff is `157a158 > ERP from history ...` / `172d172 <` with the same text. Both exit 0, stderr is identical, and both print Net Debt 40,796, Diluted Shares 8,022M, Current $104.26, Implied $28.02 | yes |
| 7 | gates | gate 2F/1013P/77E; full 3F/1013P/78E; retargeted 2F/1092P; ruff 4; mypy 6 in 3; census 64; GET / 200; guard 48/48 | **The same, measured.** Full run: 3 failed, 1013 passed, 78 errors (81 ids). By cause: 78 × `api.routes_valuation has no attribute 'fetch_price_data'`, 2 × the same on `cli`, 1 × `test_projector_rule3_red`. Gate run: 2 failed, 1013 passed, 77 errors. In a scratch copy of the head tree I retargeted 22 patch sites to `pipeline.*` with my own regex: **2 failed, 1092 passed**. The failed ids are `test_projector_rule3_red::…no_income_statements…` and `test_routes_session_rule3_red::…cache_hit_stops`, the same two ids as my fresh base run at `6c528f0` (2 failed, 1087 passed, 5 skipped). **I compared the failure sets, not just the counts.** ruff found 4, all BLE001. mypy with `pipeline.py` found 6 in 3 files, none in `pipeline.py`. Census over `models analysis api ingestion pipeline.py`: **64** (64 without `pipeline.py` too, so pipeline.py contributes 0). `GET /` returned 200. `check_guard.py` passed 48/48 | yes |
| 8 | zero share count stops with no yfinance call | head stops in CLI and web with no Ticker call; base calls `Ticker('WMT')` | My own copy `WMT_rv_noshares.json` sets 2026 `diluted_shares` to `[]` (it was `[{'label':'Diluted','value':8022,'page':22}]`). `ns.py` stubs `yfinance.Ticker` to record and raise, stubs `fetch_price_data` to record and **raise**, and blocks `socket.connect`. **Head CLI:** exit 1, `ERROR: diluted_shares is 0.0 for 'WMT' in fiscal year 2026: … No share count is taken from market data (rule 5); …`. Record: `Ticker: [] fetch_price_data: [] connect: []`. **Head web:** 200, the error block holds the same message, no implied price, and the record is empty in the same way. **Base** (with frozen price data, for contrast): CLI exit 1 `ERROR: stub: yfinance.Ticker was called`, and the web page shows the same, with record `Ticker: [('WMT',)]` | yes |

Criteria 1, 2, 4, 5 and 6 I did not re-run in full this round (I was asked for 3, 7 and 8). The
guard greps re-confirm criterion 2. The criterion 6 spot-check above was run at the head only.

## Findings

### F2 (carried from round 1): `ValuationRun.assumptions` and the moved `project_fcffs` call carry an untyped `dict` argument bag · `major`, standing. The amendment's exemption for it has no user decision behind it

**Evidence:** `pipeline.py:82` `assumptions: dict`, and `pipeline.py:183,187,193`. The amendment says "F2 … Not a finding against this unit … Change nothing", and it cites no user decision or date.
**Rule or document:** rule 2 ("no untyped dict passed as an argument bag"). `code-reviewer.md` says: "A defect the unit **touched** is the unit's, backlog or not. Moving a line makes it yours." It also says "the fix belongs to a future unit" is not grounds to downgrade, and that "An assignment claiming an exception with no user decision behind it is a `blocker`." Recording the defect as backlog item 88 after the fact does not change who touched the lines. I found nothing in `AGENTS.md` or `rules.md` that lets the overall lead exempt rule-break lines without a user decision.
**Correction to my round 1 entry:** its "What would fix it" offered "put it in a unit of its own and record it in the backlog" as a way out. That option was wrong under `code-reviewer.md`, and I withdraw it.
**Whose it is:** the assignment's, not the programmer's. The programmer followed the amendment to the letter. **This goes to the orchestrator:** the amendment conflicts with a rule, and the rule wins.
**What would fix it:** either (a) widen the unit so that `derive_assumptions` returns a frozen typed dataclass, which `project_fcffs`, `pipeline.py` and both printers read by attribute (`analysis/projector.py` in scope), or (b) a recorded user decision that accepts `pipeline.py:82,183,187,193` until item 88 is fixed, cited in the assignment with its date.

### F5: `entry-points.md` gives `cli.py` as 1,150 lines; it has 1,146 · `note`

**Evidence:** `wc -l cli.py` gives `1146`. `docs/3-architecture/entry-points.md` says "1,150 lines (measured at `P3a-one-pipeline`)". The round 2 deletion of the yfinance lines left the figure stale.
**Rule or document:** none.
**What would fix it:** change the figure to 1,146, or drop the line count.

## Pre-existing, already recorded: not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 72 (display conditional zero) | `cli.py:1061` | no. The line is context only. Its input now comes from `run.latest_balance_sheet` |
| 90 (literal `0.025` terminal growth) | `cli.py:205` | no |
| 87 (the web form rounds its defaults, $27.01 vs $28.02) | `api/routes_valuation.py` `assumptions_page` | no |
| 89 (`run_capm` prints) | `analysis/capm.py:215` | no. It explains the F3 line move |
| 5, 6, 8, 13, 26 | `api/routes_valuation.py` | no |
| 49 | the extraction step in both entry points | no |
| **not in the backlog**: six e2e scripts and one helper still run the sequence themselves, each with its own copy of `info.get("sharesOutstanding", 0) / 1e6` (the programmer's finding 2) | `tests/test_e2e_abbv.py:175` and others, `tests/_run_lly_dcf.py:31` | no. These are the tester's files, outside the census. Reported so the orchestrator can record them |

## Earlier findings, re-review

| # | Outcome | Note |
|---|---|---|
| F1 | **fixed** | The fallback, the `yfinance` import, `shares_from_market_data` and the CLI's "Diluted shares from yfinance" line are all gone. The stop is at `pipeline.py:153-161`, and its message names `diluted_shares`, the ticker and the year, and invokes rule 5. Criterion 8 passes as I executed it: no `Ticker`, no `fetch_price_data` and no socket connect at the head. The base reached `Ticker('WMT')`. Census 65 → 64 |
| F2 | **not_fixed** | No change, as the amendment ordered. The finding stands as `major` against lines this unit wrote and moved. The amendment's exemption has no user decision behind it, so this is escalated to the orchestrator (see above) |
| F3 | **fixed** (by amending the criterion) | Criteria 3 and 4 now allow the ERP line's position, recorded as item 89. Re-run: the ERP line is the only difference |
| F4 | **fixed** | `entry-points.md`, "What a stop hides in the CLI", matches the code. `cli.py` prints the stage 3 banner and then calls `adjust_financials`, and `value_company` runs before stage 6. My zero-share run's stdout ends at the stage 5 table |

## Verdict

`changes_requested`

The round 2 code does what the amendment asked, and I confirmed each claim by running it. F1 is
fixed: a filing with no diluted share count now stops in both entry points with a message that
names the field, the ticker and the year, and it never reaches yfinance or the market data call.
The CLI output for Walmart moves only by the ERP line ($28.02). With the 22 patch sites
retargeted, the failure set equals the base's. ruff is 4, mypy 6 in 3, census 64, `GET /` 200,
guard 48/48. F3 and F4 are closed. **F2 (`major`, rule 2) still stands and blocks.** The
amendment set it aside as "not a finding against this unit" without a user decision. Under
`code-reviewer.md` that exemption is itself a `blocker` on the assignment, because the unit wrote
`pipeline.py:82` and moved the call sites. This goes to the orchestrator, not back to the
programmer. Either widen the scope to `analysis/projector.py` and give `derive_assumptions` a
typed return, or obtain and cite a user decision that covers `pipeline.py:82,183,187,193`. With
either one, I see nothing else that would stop approval. F5 is a note.
