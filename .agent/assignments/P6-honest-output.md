---
id: P6-honest-output
phase: 7 — label the assumptions
agent: programmer
depends_on: [P2b-provider, P4d-cashflow-nan]
---

# Stop the cache answering a question it was not asked, and label the three inputs that are not measured

## Objective

The first run against a real filing exposed four defects, all of the same family: **the
output presents something as more solid than it is.**

**Backlog item 33 is the worst, and it is first.** `cli.py:253` keys the extraction
cache on the **ticker alone**. Measured on the user's new L3Harris filings:

```
cli.py "…LHX/…2025_English.pdf" -t LHX --cache-dir ./cache
  ->  done in 2 seconds, a complete valuation, implied share price $351.77
```

Two seconds is impossible for an 89-page extraction. It loaded
`cache/.cache_lhx_extraction.pkl`, a pickle predating this entire build, and **never
opened the PDF.** The output printed `LOADING CACHED EXTRACTION` and never said the file
named on the command line was ignored. That flag appears in **four of the six examples
in the CLI's own help text**.

Then three unlabelled assumptions, all of which reach the share price, and all of which
[rule 6](../../docs/2-rules/rules.md) requires to be visible as assumptions:

| Item | What is presented as measured |
|---|---|
| **34** | `Risk-free rate: 4.00%` is `config.DEFAULT_RISK_FREE_RATE`. Its comment says "fallback if market fetch fails" — **there is no market fetch** |
| **35** | `Beta: 0.493` came from a regression with `R-squared: 0.099`. The diagnostic is printed two lines above and carries no threshold |
| **9** | `analysis/wacc.py` substitutes `config.DEFAULT_COST_OF_DEBT` when interest is not separately reported, with nothing saying so |

**Item 35's cost, measured on the LHX filing**, everything else held as the run produced
it:

| Beta | Implied price | Against the market's $240.21 |
|---|---|---|
| 0.493, as regressed | $343.57 | **+43.0%** |
| 0.80, a sector figure | $227.33 | **−5.4%** |

One unmeasurable input moves the answer from a buy to a sell.

## What is already true — verify, do not redo

| Fact | Evidence |
|---|---|
| `cli.py:248-253` builds `.cache_{ticker}_extraction.pkl`; the PDFs are not in the key | read it |
| `--cache-dir` defaults to `None`, so omitting it disables the cache | `cli.py:103` |
| `ingestion/price_fetcher.py` fetches **no** treasury rate | `grep -rn "treasury\|TNX\|risk_free" ingestion/` → nothing |
| `CAPMResult` already carries `r_squared` and `std_error` | `models/valuation.py` |
| the real LHX run's output is at `c:/tmp/lhx_real.txt` | 272,204 input tokens, 77 s |
| suite `1 failed, 120 passed`; lint 5; types 14; census 116; `GET /` 200 | the gates |

**The three filings are at `10K_filings/LHX/`.** The FY2025 one is 89 pages and the
cheapest to re-extract.

## What to do

1. **Fix the cache key.** Include the input files — their paths **and** their
   modification times or a content hash. A cache that can answer a question it was not
   asked is worse than no cache.

   When the key misses because the inputs changed, **say so on stdout**: name what
   changed, not just that a miss happened.

2. **Record whether the risk-free rate was measured or substituted**, and show it. The
   value already flows through `run_capm`; what is missing is the fact that it was
   defaulted.

   **Do not build a treasury fetch.** That is a new data source and
   [rule 5](../../docs/2-rules/rules.md) territory. Labelling closes the rule break on
   its own, and it is the half that is in scope.

3. **Give the beta a named threshold.** Put a minimum R-squared in `config.py`, with a
   comment saying why that number. When the regression falls below it, the output must
   say the beta is not reliable, beside the beta — not two lines away.

   **Do not stop the run.** A weak regression is a real measurement of a weak
   relationship, not a missing input. This is rule 6, not rule 3.

4. **Label the substituted cost of debt**, item 9, the same way. Leaving it would make
   the output label two of three assumptions and look complete.

5. **Show all four in both outputs.** The CLI already prints an assumptions block, and
   `P2b-provider` added a provider/model/transport block to the result page. Follow that
   pattern rather than inventing a second one.

6. **Prove item 33 by execution.** Three runs, in this order, output pasted:
   - the FY2025 filing with `--cache-dir` → a real extraction, a cache written;
   - the same command again → a cache **hit**, seconds;
   - the **FY2024** filing, same ticker, same cache dir → a cache **miss** and a real
     extraction, not a replay of FY2025.

   The third run is the unit. It is the one that fails today.

## Files in scope

- `cli.py` — the cache key, and the printing of the four labels.
- `config.py` — the R-squared threshold; comments on the two existing defaults.
- `analysis/capm.py` — recording whether the rate was substituted, and the R-squared
  verdict.
- `analysis/wacc.py` — recording the cost-of-debt substitution.
- `models/valuation.py` — **only** if a result object must carry a new flag.
- `templates/` — the result page.

**Nothing else.**

## Out of scope

- **`tests/`** — your write guard denies it. 121 tests exist; a tester follows you.
- **`ingestion/`** — no new data source. See step 2.
- **`api/routes_valuation.py`** — the route already carries a context block; if a label
  needs plumbing there, **stop and say so**.
- Backlog items **1, 2, 5, 6, 7, 8, 25, 26, 29, 31, 32**.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | a different PDF with the same ticker is a cache **miss** | a real extraction runs | step 6's third run; paste it |
| 2 | an unchanged PDF is a cache **hit** | seconds | step 6's second run |
| 3 | the miss says what changed | the file is named | same output |
| 4 | the risk-free rate is labelled when substituted | shown in both outputs | CLI output, and the rendered page |
| 5 | a weak regression is labelled beside the beta | shown | the LHX run — its R-squared is 0.099 |
| 6 | a substituted cost of debt is labelled | shown | a fixture where interest is 0 and debt is not |
| 7 | **no existing assertion changed meaning** | `1 failed, 120 passed`, the failure being `test_dcf_rule3_red.py` | `pytest -q` |
| 8 | the routes still serve | `GET /` 200 | `TestClient` |
| 9 | lint unchanged, types not worse, census not risen | 5 / ≤14 / ≤116 | the three gates |

**Criterion 1 is the unit.** Everything else is labelling.

**Criterion 7 is the constraint.** `models/valuation.py` carries **40 assertions** you
may not edit. If you add a field there, add it with a default so every existing
construction still works — and say in your entry that you checked.

## Citations

- `docs/9-reference/refactor-backlog.md` items **33**, **34**, **35** and **9**.
- `docs/2-rules/rules.md` rule 6 (an assumption is labelled) and rule 5 (the filing is
  the only source of statement data — which is why step 2 forbids a treasury fetch).
- `.agent/journal/2026-09-21T0200-programmer-p2b-provider-r2.md` — the labelling block
  to follow.
- `c:/tmp/lhx_real.txt` — the run that exposed all four.

## Known open items

- **Extraction costs real money.** The FY2025 filing is 89 pages and cost 272,204 input
  tokens. **Do not re-extract more than the three runs step 6 requires.** Use the
  smallest filing for the first two.
- `cache/.cache_lhx_extraction.pkl` and `.cache_abbv_extraction.pkl` are **stale pickles
  from before this build**, untracked but present. They are what caused item 33 to fire.
  Do not delete them — they are the reproduction case. Do not load them either.
- `analysis/capm.py:14` imports from `ingestion/` — item 17, not yours. Say you saw it.

## Backlog items this unit is NOT fixing

- **Item 1** — the 116 zero-default sites.
- **Item 2** — zero net debt. Its red test stays red; criterion 7 depends on it.
- **Item 10** — the D&A subtraction in the parser.
- **Item 31/32** — the remaining unguarded values.

---

# Round 2 — orchestrator amendment, 2026-09-22

Review `.agent/journal/2026-09-22T1500-code_reviewer-p6-honest-output.md` returned
`changes_requested` with two `major` findings. **Neither is a mistake you made.** Both
say my file scope was too narrow, and both are mine to correct.

**Everything else was verified and stands.** The reviewer falsified criterion 1 rather
than accepting it (`17,062` appears **zero** times in the FY2025 PDF; the live sha256
matches run 2's hit message byte for byte), exercised the cache key directly with
fabricated files, checked the R-squared derivation numerically against
`scipy.stats.linregress`, confirmed no test was edited, and set-diffed the type errors.
**Do not redo any of it.**

## F1 · `major` · the web path cannot meet criterion 4

`api/routes_valuation.py:140` is `risk_free_rate: float = Form(4.0)` — a **literal**,
not `config.DEFAULT_RISK_FREE_RATE`. So a real `POST /valuation` always renders
`supplied by the caller` and can **never** render the substitution label. Backlog item
34 is half closed, and changing the constant would move the CLI while leaving the web
app at 4.0%.

**Scope is widened.** `api/routes_valuation.py` and `templates/assumptions.html` are now
in scope, **for this defect only.**

Make the form's default come from `config`, and make the web path able to report a
substitution the same way the CLI does. Nothing else in `api/routes_valuation.py` —
items 5, 6, 8, 26 and 29 all live in that file and none is yours.

## F2 · `major` · you touched a rule 3 line, so it is yours

Changing the arity of `analysis/wacc.py`'s `if total_debt == 0: return 0.0` to carry the
label makes that branch this unit's, whatever its behaviour.
[docs/9-reference/severity.md](../../docs/9-reference/severity.md) is explicit that
moving a line makes it yours, and a rule 3 citation cannot be filed as a note.

**I am not granting an exception, because that is not mine to grant.** I am widening
scope to close **backlog item 22** instead.

The fix is a distinction the code does not currently draw:

| Case | Correct behaviour |
|---|---|
| `total_debt == 0` and `interest_expense == 0` | a genuinely debt-free company. Return `0.0`, **labelled** — "no debt reported" |
| `total_debt == 0` and `interest_expense > 0` | **a contradiction.** A company paying interest has debt, so the balance was not extracted. **Stop**, naming both figures |

The second case is the one item 22 is about: missing data read as a measurement. The
first is a real measurement and must keep working.

## Revised done-criteria

Criteria 1, 2, 3, 5, 6, 7, 8, 9 stand as verified. These replace and extend criterion 4.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 4 | the **web** path reports a substituted risk-free rate | the assumption label renders | a real `POST /valuation` via `TestClient`; paste the block |
| 4b | the form default is no longer a literal | 0 hits | `grep -n "Form(4.0)" api/routes_valuation.py` |
| 10 | a debt-free company still returns a `0.0` cost of debt, labelled | no raise | a fixture with zero debt and zero interest |
| 11 | interest with no debt balance **stops**, naming both | raises | a fixture with zero debt and non-zero interest |

**Criterion 7 still binds**: `1 failed, 120 passed`, and **no test edited.** If a route
assertion goes red, move your code, not the test — as you did last round.

## One more thing, and it is not yours to fix

The reviewer confirmed the 16% swing and its cause: `confidence` is read **nowhere** in
`analysis/`, `.get("confidence", "high")` defaults an unknown to the strongest value,
and the debt figure that also moved has no confidence field in the schema at all. **That
is now backlog item 36 and it gets its own unit.** Do not touch it here. Say in your
entry that you saw it.
