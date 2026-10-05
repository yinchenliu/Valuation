---
agent: code_reviewer
assignment: P3a-one-pipeline
round: 1
verdict: changes_requested
---

# Review of P3a-one-pipeline, round 1

Programmer entry: `.agent/journal/2026-10-04T2350-programmer-p3a-one-pipeline.md`

Reviewed: `git diff 14a5608` (cli.py, api/routes_valuation.py, docs/3-architecture/entry-points.md,
docs/INDEX.md) plus the new `pipeline.py`. `.agent/journal/INDEX.md` also moved. Its row is
the orchestrator's (AGENTS.md:118), so it is not a scope finding. Every command ran with
`ANTHROPIC_API_KEY= GEMINI_API_KEY=`. No paid call was made. The base worktree at `6c528f0` has
been removed (`git worktree list`: main and the unrelated copilot worktree).

## The guard checks

Run over `pipeline.py cli.py api/routes_valuation.py`.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | `cli.py:1065` `total_debt = latest_bs.total_debt if latest_bs else 0`. The line is unchanged in the diff (context only): item 72, excluded by the assignment. `cli.py:205` `... else 0.025`: untouched, see the pre-existing table |
| lookup with a fallback — `.get(k, 0)` | **`pipeline.py:160` `info.get("sharesOutstanding", 0) / 1e6`**, moved here by this unit. **F1.** (`routes_valuation.py:357` is `@router.get`, a false hit) |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | `cli.py:701`, untouched. It reads a field name passed by the file's own literals |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean (models/ analysis/ api/ pipeline.py) |

The programmer answered the `.get` hit in its entry: it moved the line as step 2 told it to. That is
the question F1 raises.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `adjusted.latest_year` | yes, `ValueError` | `models/financial_statements.py:452-467` |
| latest income statement | yes, a new stop naming the ticker and year. It cannot be reached today, and it replaces the CLI's `if latest_is else 0` | `pipeline.py:144-149` |
| `latest_is.diluted_shares_outstanding` == 0 | **no**. It falls back to yfinance, and `.get(..., 0)` then gives a share count of 0 | `pipeline.py:157-161`. **F1** |
| `latest_bs` None | passed to `calculate_wacc`, which decides. The behaviour is unchanged | `pipeline.py:137,167` |
| `fetch_price_data` failure | stops with its message, CLI and web | criterion 6 below |
| assumption keys `tax_rate`, `terminal_growth_rate` | a `KeyError` with no type check, because `assumptions` is a bare `dict` | `pipeline.py:170,180`. **F2** |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | yes. `shares` is in millions (`/ 1e6` on the fallback), so `market_cap` = price × shares (M) is in $M. Unchanged |
| percentages converted at the route boundary, once | unchanged. The form parsing was not touched |
| falsy not treated as missing | `pipeline.py:157` `if shares == 0` treats a printed 0 as "not supplied". This moved code is part of F1 |
| `analysis/` imports no `ingestion/`, `api/`, model client | unchanged. `pipeline.py` sits at the root, and only `cli.py:64` and `api/routes_valuation.py:29` import it |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | one home | 9 lines, 8 in pipeline.py, 1 `derive_assumptions` in routes | the same: `pipeline.py:104,105,121,123,128,164,174,176` and `api/routes_valuation.py:420` | yes |
| 2 | rule 2 grep | 2 `def` hits, no kwargs or getattr | the same (`94`, `109`). But see F2 for the untyped `dict` | grep yes; rule 2 no (F2) |
| 3 | CLI unchanged | identical except that the ERP line moved | base and head both exit 0, $28.02, Net Debt 40,796, stderr identical. diff: `157a158 > ERP from history ...` / `172d172 <` the same | yes, and the criterion **as written fails**. F3 |
| 4 | CLI with overrides | the same, with decimal flags | `build_overrides` takes decimals (`cli.py:138`, "(decimals)"). `--beta 1.0 --risk-free-rate 0.045 --terminal-growth 0.02`: both $15.00, Beta 1.000. diff: only the ERP line moved | yes. F3 |
| 5 | web pages unchanged | 3 pages identical with frozen PriceData | my own script (`rev_run.py`): one live `PriceData` pickled and given to both commits, the form fields parsed from the page, then GET /assumptions, POST /valuation (cache hit) and POST /valuation (cache miss). **`cmp` identical for all 3**, all 200, $27.01. Calls: base `('WMT', 5, 'monthly')` positional, head keyword, same binding | yes |
| 6 | market failure stops | CLI exit 1 `ERROR: stub: no market data`. Web shows it. The only difference is stages 6 and 7 plus the assumptions block | stub on `ingestion.price_fetcher` before import. Both exit 1 with identical stderr. Web: all 3 pages identical between commits, text present. The CLI stdout diff is exactly the 14-line PROJECTION ASSUMPTIONS block plus the `[6/10]` and `[7/10]` banners, missing at head | yes |
| 7a | tests | full: 3 failed, 1013 passed, 78 errors, all from the moved patch site | **the same counts.** Grouped by cause: 78 × `AttributeError: api.routes_valuation has no attribute 'fetch_price_data'`, 2 × the same on `cli`, and `test_projector_rule3_red` (on purpose). **The failure sets were compared, not the counts.** In a scratch copy with 22 patch sites retargeted to `pipeline` (`retarget.py`): `2 failed, 1092 passed`, and the two FAILED ids match the base run at `6c528f0` exactly (base: 2 failed, 1087 passed, 5 skipped, the skips being the worktree's missing `extractions/WMT.json`) | yes. The assignment's patch-site grep found 1 of 22 (the programmer's finding 1, confirmed) |
| 7b | ruff | 4 BLE001 | 4, all BLE001 | yes |
| 7c | mypy | 6 in 3, 0 in pipeline.py | **6 in 3**, 21 files, none in `pipeline.py`. Base: 8 in 3, and the two gone are the old `routes_valuation.py:649` (union-attr) and `:658` (arg-type), now narrowed by `pipeline.py:144` | yes. The assignment's "8" could not hold together with "0 in pipeline.py". STATUS section 1 should read 6 |
| 7d | census | 65 with pipeline.py, 64 without | 65 / 64 | yes |
| 7e | GET / | 200 | 200 | yes |
| 7f | guard | 48/48 | 48/48 | yes |

## Findings

### F1 — The yfinance share count fallback was moved into `pipeline.py` as it was, and the assignment's exemption for it has no user decision behind it · `blocker`

**Evidence:** `pipeline.py:155-161`, `if shares == 0: ... shares = info.get("sharesOutstanding", 0) / 1e6`. `docs/8-build/phases.md:97`: "Split in two on 2026-10-05, **by the overall lead**". The assignment's "Backlog items this unit is NOT fixing" ends "A reviewer must not raise them as findings against this unit", and the fallback is in that list.
**Rule or document:** rules 3 and 5 (rules.md, rule 5 "Why" names this very fallback). `code-reviewer.md`: "Moving a line makes it yours"; "the fix belongs to a future unit" is not grounds to downgrade; "An assignment claiming an exception with no user decision behind it is a `blocker`."
**Whose it is:** the assignment's, not the programmer's. Step 2 ordered the move word for word, and the programmer did it faithfully and labelled it honestly in the docstring, the comment and entry-points.md. **This is an escalation to the orchestrator:** the assignment conflicts with a rule, and the rule wins.
**What would fix it:** one of two. (a) The orchestrator widens P3a so that `value_company` stops and names the field when the filing's diluted share count is 0 or missing. No Walmart figure moves (8,022M is printed), but the zero-share path does change from a number to a stop, against phases.md's "must not change a number", and rules.md outranks that. (b) The user records a decision accepting `pipeline.py:155-161` until `P3b-pipeline-stops`, and the assignment cites it with its date.

### F2 — `ValuationRun.assumptions` and the moved `project_fcffs` call carry an untyped `dict` argument bag · `major`

**Evidence:** `pipeline.py:82` `assumptions: dict`. The dict is read by key at `pipeline.py:170` (`assumptions["tax_rate"]`) and `:180` (`assumptions["terminal_growth_rate"]`) and passed whole at `:174` to `project_fcffs(financials, assumptions: dict)` (`analysis/projector.py:329-331`). `derive_assumptions` returns a 9-key literal dict (`analysis/projector.py:314-326`). `grep -n "TypedDict\|derive_assumptions\|project_fcffs" docs/9-reference/refactor-backlog.md` finds no entry for it.
**Rule or document:** rule 2: "Arguments are named and typed. No ... untyped dict passed as an argument bag." The unit wrote the new `dict` field and moved the three call sites, so the defect is the unit's, backlog or not. A misspelt key fails only at run time, on the path that ran. mypy checks nothing.
**What would fix it:** `derive_assumptions` returns a frozen dataclass with the nine typed fields, and `project_fcffs`, `pipeline.py` and both printers read attributes. That means changing `analysis/projector.py`, so the orchestrator must widen the scope or put it in a unit of its own and record it in the backlog. It must not be passed over as a note.

### F3 — Criteria 3 and 4 fail as written: the "ERP from history" line moves from line 172 to line 158 · `minor`

**Evidence:** `diff` of the base and head CLI stdout, with the elapsed lines removed: `157a158 > ERP from history ...` / `172d172 < ERP from history ...`, for both the plain run and the overrides run. The print is in `analysis/capm.py:215-218`.
**Rule or document:** none broken. The assignment contradicts itself: step 3 has `value_company` run before stages 6 to 10 print, while criterion 3 asks for identical output. The programmer did right to refuse to capture stdout to hide it, and it showed that with `--equity-risk-premium` given the outputs are identical (I did not re-run that variant).
**What would fix it:** the orchestrator amends criteria 3 and 4 to allow this one moved line. Moving the market return into `CAPMResult` and printing it in the CLI's stage 7 is a later unit (the programmer's finding 2).

### F4 — Every stop inside the two pipeline functions now cuts off more of the CLI audit trail than it did, and only the market-data case is recorded · `note`

**Evidence:** `cli.py:1015` (`adjust_financials`, which can raise at `analysis/normalizer.py:137,161,182,255`) runs before `cli.py:1018` prints the item list. So a normalisation stop now prints no stage 3 items, where at the base it printed them and then the stage 4 banner. Likewise a stop in `calculate_wacc` or `run_dcf` (for example item 22, the zero-debt stop) now prints none of stages 6 to 9, where at the base it printed the assumptions and the CAPM result first. `entry-points.md`, "One display difference the move made", mentions only the ERP line.
**Rule or document:** none. This follows from the design in assignment step 3. A reader debugging a stop has less on screen.
**What would fix it:** a sentence in `entry-points.md`, or have the CLI print what it can on the error path. That is for the orchestrator to decide.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 72 (display conditional zero) | `cli.py:1065` | no. The line is context-only in the diff. Only its input now comes from `run.latest_balance_sheet` |
| 5, 6, 8, 13, 26 | `api/routes_valuation.py` (cache pop, `x / 100 if x else None`, BLE001, provider, `":" in files`) | no |
| 49 | the extraction step in both entry points | no |
| 17 | `analysis/` → `ingestion/` | no. `pipeline.py` is at the root to avoid it |
| not found in the backlog: `cli.py:205` `terminal_growth_rate=... else 0.025`, a literal default for an assumption (rule 6) | `cli.py:205` | no. Reported so the orchestrator can record it |

Also confirmed, and not this unit's: the programmer's finding 3 (web $27.01 against CLI $28.02 for the same filing and market data, because the form rounds its defaults) reproduces. My frozen-price web run gives $27.01 and the live CLI gives $28.02 at the same $104.26 price.

## Verdict

`changes_requested`

The code does what the assignment asked, and the claims in the programmer's entry held when re-run. One sequence lives in `pipeline.py`. The web pages are byte-identical with market data held fixed. The CLI differs only by the moved ERP line. A market-data failure stops the same way in both. Once the 22 patch sites are retargeted, the failure set equals the base's. ruff 4, mypy 6 in 3, census 65, GET / 200, guard 48/48. **F1 (`blocker`) and F2 (`major`) block.** Both are rule breaks in lines this unit wrote or moved. F1 is an assignment defect: it exempts a moved rule 3 and rule 5 site with no user decision, so it goes to the orchestrator, not back to the programmer as it stands. F2 needs `analysis/projector.py` in scope. F3 needs the assignment's criteria amended. F4 is a note.
