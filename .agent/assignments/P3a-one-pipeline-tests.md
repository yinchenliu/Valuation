---
id: P3a-one-pipeline-tests
phase: 3 — unify the pipeline (backlog item 7)
agent: tester
depends_on: [P3a-one-pipeline]
---

# Repair the tests that patch a moved call, and lock `pipeline.py`: its wiring, its share count stop, and one price for both entry points

## Objective

`P3a-one-pipeline` moved the eight valuation calls from `cli.py` and
`api/routes_valuation.py` into a new root module, `pipeline.py` (`adjust_financials`,
`value_company`). About 80 tests now go red for one reason: they patch
`fetch_price_data` or `calculate_wacc` on `cli` or `routes_valuation`, where those names
are no longer imported. The unit also deleted the yfinance share count fallback: a latest
year whose `diluted_shares_outstanding` is not a finite number above 0 now stops before
any market call (rules 3 and 5).

Read first:
- `.agent/assignments/P3a-one-pipeline.md`, with its round 2 amendment
- the programmer's entries `.agent/journal/2026-10-04T2350-programmer-p3a-one-pipeline.md`
  and `.agent/journal/2026-10-05T0014-programmer-p3a-one-pipeline-r2.md`
- the reviews `.agent/journal/2026-10-05T0011-code_reviewer-p3a-one-pipeline.md` and the
  round 2 review beside it
- `.claude/agents/tester.md`

## What to do

1. **Repair the patch sites.** Point each patch of a moved name at `pipeline`. The
   programmer counted 22 sites in 6 files; find them yourself, including the
   `monkeypatch.setattr(routes_valuation, "fetch_price_data", ...)` form. **No assertion
   changes.** A test that asserted the yfinance fallback is the one exception: it now
   expects the stop, and your entry names it.
2. **Lock `adjust_financials`.** With items you build by hand: a `high` and a `medium`
   item are applied and a `low` item is excluded; the adjusted figure equals the raw
   figure moved by the applied items only, computed by hand; the raw statements are not
   mutated.
3. **Lock `value_company`'s wiring**, with `fetch_price_data` stubbed (no network) and
   inputs you choose so the arithmetic is by hand:
   - the share count is the filing's: `market_cap` equals the stub's price times the
     filing's diluted shares;
   - the overrides reach CAPM: with a supplied beta, risk-free rate and equity risk
     premium, the cost of equity is `rf + beta × ERP`, computed by hand;
   - the result's `dcf_result` is the one `run_dcf` gives for the same projected FCFFs
     and WACC (a closed-form check, or `run_dcf` called directly on the result's own
     `projected` and `wacc_result`).
4. **Lock the share count stop.** For a latest-year `diluted_shares_outstanding` of 0,
   a negative number, NaN and infinity: `value_company` raises `ValueError` naming
   `diluted_shares`, the ticker and the year; `fetch_price_data` is not called; and
   `yfinance.Ticker` is not called. The same stop reaches the CLI (exit 1, the message
   printed) and the web result page (the message shown).
5. **Lock one price for both entry points.** For one set of statements, items and
   overrides, with the same stubbed market data, `cli.main` and `POST /valuation`
   (the cache-miss branch, or a primed cache) report the same implied share price. This is
   the identity the unit exists for. Pass the same overrides to both; do not rely on the
   web form's rounded defaults (backlog item 87).

Never make a paid API call or a real network call. Do not read `extractions/` or
`10K_filings/` in a test unless it carries `pytest.mark.skipif(not path.exists(), ...)`.

## Files in scope

- `tests/`
- `.agent/journal/<YYYY-MM-DDTHHMM>-tester-p3a-one-pipeline.md`

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | gate form | 0 failed | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` |
| 2 | full suite | exactly 2 failed: `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` | `.venv/bin/python -m pytest -q` |
| 3 | no assertion weakened | each changed old test changes a patch target only, except the fallback test named in your entry | `git diff tests/`, per file |
| 4 | new tests can fail | in a scratch copy, each of these turns a test red: restore the yfinance fallback; drop the share count stop; pass `beta_override=None` to `run_capm`; normalise with all items instead of the applied half | mutants in a scratch copy |
| 5 | clean checkout | the gate passes with no `extractions/` and no `10K_filings/` | a worktree at the commit under test |
| 6 | lint and types | ruff 4, 0 new in `tests/`; mypy 6 errors in 3 files | the gate commands |
| 7 | two counts | accuracy and coverage reported | your entry |
