---
id: P3f-cli-assumption-labels
phase: 3 — unify the pipeline
agent: programmer
depends_on: []
team: B (worktree `Valuation-wt/team-b`, branch `unit/team-b`)
---

# The CLI shows where each projection ratio came from, as the web page does (item 68)

## Objective

**The fact.** `analysis/projector.derive_assumptions` returns, beside the six projection
ratios, a `sources` dict: one `AssumptionSource` per ratio (`models/valuation.py:130`),
with an `origin` (`supplied`, `derived` or `substituted`) and a `detail` sentence. The
assumptions page prints both for every ratio: `templates/assumptions.html:50-58` shows
`SUBSTITUTED` when `origin == 'substituted'`, then the `detail` sentence. `cli.print_assumptions`
(`cli.py:957-975` at `e7f3023`) prints the rates and an `(override)` tag, and nothing from
`sources`. Measured by the overall lead on the tracked Walmart file:

```
  Revenue growth (per yr): ['5.3%', '5.3%', '5.3%', '5.3%', '5.3%']
  Operating margin:        4.26%
  Tax rate:                23.11%
  D&A / Revenue:           1.88%
  CapEx / Revenue:         3.18%
  NWC chg / Revenue:       0.06%
```

while `sources` holds, for each of the six, `origin=derived` and a sentence that begins
"derived from the filing: 5 filing-year(s) of extracted data fed it" (2 for revenue growth).

**What follows.** On the CLI, a ratio a default replaced looks exactly like one measured
from five filing-years. Rule 6 says an assumption is labelled and visible to the user, and
the third standing trap is two entry points that say different things about one number.
Backlog item 68 holds it.

**When this unit is done**, `print_assumptions` prints, under each of the six ratios, the
same words the page shows for it: `SUBSTITUTED` when the origin is `substituted`, then the
`detail` sentence.

## What is already true — verify, do not redo

- `derive_assumptions(...)["sources"]` has one entry per ratio:
  `revenue_growth_rates`, `operating_margin`, `tax_rate`, `da_pct_revenue`,
  `capex_pct_revenue`, `nwc_pct_revenue`.
- `cli._wrap_label` (`cli.py:982`) already wraps a provenance sentence under its figure,
  for the CAPM block. Reuse it.
- The gate form on `main` at `e7f3023`: **1623 passed, 0 failed, 0 skipped** at seeds 7,
  1234 and 99.
- Reproduce the measurement above:

  ```
  ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python - <<'PY'
  import io, contextlib, cli, pipeline
  from ingestion.session_extraction import load_session_extraction
  from analysis.projector import derive_assumptions
  from models.valuation import ProjectionAssumptions
  with contextlib.redirect_stdout(io.StringIO()):
      s = load_session_extraction("extractions/WMT.json")
      adj = pipeline.adjust_financials(s.financials, s.non_recurring).adjusted
  cli.print_assumptions(derive_assumptions(adj, ProjectionAssumptions()), ProjectionAssumptions())
  PY
  ```

If a measurement disagrees, stop and report the disagreement. Do not edit to make it agree.

## What to do

1. In `print_assumptions`, under each of the six ratio lines, print that ratio's source
   with `_wrap_label`: `SUBSTITUTED` first when its `origin` is `substituted`, then its
   `detail`. Reason: rule 6, and the page's words at `templates/assumptions.html:50-58`.
2. Read each source from `assumptions["sources"]` by its ratio's name. If one is missing,
   stop with an error that names the ratio. Never print a ratio without its source.
   Reason: rule 3.
3. Leave the rate lines and the `(override)` tag as they are, and leave
   `Projection years` and `Terminal growth` alone (see "Out of scope").

## Files in scope

- `cli.py` (programmer)
- `tests/unit/test_p3f_cli_assumption_labels.py` (tester, new file)

**Nothing else.** Work outside this list is a review finding, even if the change is good.

## Out of scope

- `templates/`, `api/`: the page is the reference.
- `analysis/projector.py`, `models/valuation.py`: they produce the sources; do not change
  a `detail` sentence.
- `Terminal growth` and `Projection years` have no `AssumptionSource` today. Backlog item
  90 holds the terminal growth literal. Do not invent a label for either.
- `ingestion/session_extraction.py`: team A's unit `P15c-portable-session-paths` is in
  flight on it.
- `.venv`, `requirements*.txt`: a unit branch installs nothing.
- The four record files and `docs/`, `.claude/`, `extractions/`: see "Pilot rules".

## Done-criteria

Run every command **from the worktree root**, with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`
in front.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | on Walmart, each ratio line is followed by its source | six source lines, each beginning "derived from the filing" | the command in "What is already true" |
| 2 | a substituted ratio says `SUBSTITUTED`, then its sentence | both, under that ratio's line | the tester's test, with an input that makes one ratio substituted |
| 3 | a supplied ratio prints its sentence, and keeps `(override)` | both | the tester's test, with one override |
| 4 | the CLI's words for each ratio are the page's | for each ratio, the `detail` string appears in the CLI output, and `SUBSTITUTED` appears exactly when `origin == "substituted"` | the tester's test. Both entry points read `assumptions["sources"]`: a closed-form identity |
| 5 | a missing source stops and names the ratio | an error naming the ratio | the tester's test, with one key removed from `sources` |
| 6 | the tests fail without the change | red with `main`'s `print_assumptions`, green with this unit's | a mutation, by `docs/5-testing/strategy.md`, section 5b |
| 7 | the gate form at three orders | `0 failed`, `0 skipped`; passed = 1623 plus the tester's new tests | `.venv/bin/python -m pytest -q -rs -p no:cacheprovider --ignore-glob="*_rule3_red.py" --randomly-seed=<n>` for n = 7, 1234, 99 |
| 8 | lint, types, census unchanged | `4 errors`, all `BLE001`, none in a unit file; `2 errors in 2 files`; `64` | `docs/8-build/environment.md`, section 4, and the grep at `docs/2-rules/rules.md:65` with `pipeline.py` added |
| 9 | the unit stayed in scope | only the two files above, this assignment, `P3f-cli-assumption-labels-tests.md` and new files under `.agent/journal/` | `git diff --name-only main...HEAD` |

**Every criterion is a measurement, never an opinion.**

## Pilot rules (worktree)

This unit runs in a git worktree, beside team A's unit. [docs/8-build/worktree-teams.md](../../docs/8-build/worktree-teams.md)
owns the scheme. These five points bind this unit:

1. **Do not write** `STATUS.md`, `.agent/QUEUE.md`, `.agent/journal/INDEX.md` or
   `docs/9-reference/refactor-backlog.md`. The overall lead writes them on `main` after the
   merge. A subagent's own journal entry, with its own file name, is allowed.
2. **The loop has five steps now** (`AGENTS.md`, "The build lead's procedure", from
   `919afd7`): programmer, code reviewer, tester, then **the code reviewer in test-review
   mode**. Your branch holds the new cards; use the relative paths.
3. **The handoff names every commit hash, and is committed with the unit. Do not amend a
   commit.**
4. **Install nothing.** `.venv` in the worktree is a link to the main checkout's venv.
5. **No hook protects a Gemini subagent.** After each subagent run, run `git status` and
   reject the run if it wrote outside its role or outside Files in scope.

## Citations

- `docs/2-rules/rules.md`, rule 6 — an assumption is labelled and visible to the user;
  rule 3 — a missing source stops.
- `templates/assumptions.html:50-58` — the page's words for one ratio.
- `models/valuation.py:86-88`, `:130-146` — the three origins and `AssumptionSource`.
- `docs/3-architecture/entry-points.md` — the two entry points and how they still differ.

## Known open items

- `templates/valuation_result.html` also shows sources, in its provenance block. Item 111
  (the derived ratio shown at one decimal place) is about the rate, not the label.

## Backlog items this unit is NOT fixing

Each sits in `cli.py`. Leave them alone.

- 8 — the blanket `except Exception` in `cli.py`.
- 86, 90 — the `CACHE_FORMAT` comment and the terminal growth literal.
- 104 — the historical-FCFF basis sentence in three files.
- 129, 130, 132, 134, 135, 136, 137 — the `P3d-invisible-year` findings in `cli.py`.
