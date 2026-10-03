# Build order

**The order is set by dependency, not by severity.** Fixing a silent defect with no test
in place produces an unverifiable claim, and a fix applied to a duplicated pipeline is a
fix applied to half the program.

Every phase names its done-criteria as **measurements**. A criterion that cannot be
measured by a command is not a criterion.

Measured state is in [STATUS.md](../../STATUS.md);
the defects are in
[9-reference/refactor-backlog.md](../9-reference/refactor-backlog.md).

---

## Phase 0 — the contract · **done 2026-09-20**

The agent contract, the docs tree, and the environment.

| # | Criterion | Measured by |
|---|---|---|
| 1 | `.venv` exists and every runtime dependency imports | the import check in [environment.md](environment.md) |
| 2 | the three gates run and report a number | `pytest`, `ruff check .`, `mypy …` |
| 3 | the write guard is correct | `.venv/Scripts/python.exe .claude/check_guard.py` → 48/48 |
| 4 | every defect found in review is recorded with `file:line` evidence | `refactor-backlog.md`, 13 items |

## Phase 1 — make the suite runnable · **done `d1854fb`**

**Prerequisite for every later phase.** Backlog item 4. Unit `P1-suite`.

| # | Criterion | Expected | Result at `d1854fb` |
|---|---|---|---|
| 1 | `pytest` collects without an API key | 0 errors | **pass** — 20 tests collected, 0 errors |
| 2 | the existing scripts still run by hand | unchanged output | **pass, re-measured.** The criterion's literal command was already broken at `bc19431` — backlog item 16. Use `-m tests.<name>` |
| 3 | first real tests exist for `analysis/dcf.py` | ≥ 6 assertions, each with a stated source | **pass** — 35 assertions execute `dcf.py`, each sourced in the journal entry |
| 4 | the `WACC <= g` raise is locked | 1 test, asserting type **and** message | **pass** — 3 tests, including the `wacc == g` boundary |

**Constraint held.** Every expected value came from hand arithmetic or a closed-form
identity, and the reviewer re-derived 11 of 38 rather than accepting the claim. Two
assertions are falsifiable against an off-by-one in the discounting exponent, which is
the property a suite copied from the code's own output cannot have.

**The gate carries an `--ignore` until backlog item 2 lands:**
`pytest -q --ignore=tests/unit/test_dcf_rule3_red.py` → `19 passed`. That one test is
red on purpose. **Remove the `--ignore` the day item 2 is fixed**, not before.

**What phase 1 did not finish.** Five of six `analysis/` modules have **0%** coverage.
Closing that is phase 1b, in the order
[5-testing/strategy.md](../5-testing/strategy.md) section 6 gives.

## Phase 2 — hygiene · **done `d1854fb`**, except criterion 4

Backlog item 12. Unit `P2-hygiene`.

| # | Criterion | Expected | Result at `d1854fb` |
|---|---|---|---|
| 1 | `ruff check .` clean, or every remaining error justified | 0 | **pass with justification** — 45 → 5, every one `BLE001`, deferred to phase 5 and deliberately left visible |
| 2 | `.gitignore` covers the cache dirs; the inert `CLAUDE.md` line resolved | — | **pass** |
| 3 | dead code removed | `models/company.py`, the unused import | **pass** — no importers, verified |
| 4 | one provider default, in one place | identical across both functions and the CLI | **deferred to phase 2b**, see below |

**Criterion 4 was deliberately moved out.** Resolving the provider to one default makes
the provider a named assumption, and [rule 6](../2-rules/rules.md) then requires it to
be visible in the output — which is phase 7 criterion 2. Splitting them would leave a
rule 6 break standing between two units, and a rule break cannot be downgraded to a
note. They ship together.

## Phase 2b — one provider, one transport, both labelled

Backlog item 13, plus phase 7 criterion 2. **Promoted ahead of phase 3**, because
extraction cannot run on the build machine at all until it lands.

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | one default provider, named once | 1 definition | `grep -rn "DEFAULT_EXTRACTION_PROVIDER"` |
| 2 | the route passes `provider` explicitly in every branch | 0 implicit calls | `grep -n "extract_financials\|extract_multi_year" api/ cli.py` |
| 3 | a Foundry endpoint is used when one is configured | a real extraction completes | run one filing end to end |
| 4 | the resolved provider, model **and transport** appear in the output | all three shown | manual run, web and CLI |

**Foundry is a transport, not a third provider.** The model is still Claude. A figure
read through a company gateway and one read through the public API must be
distinguishable by the reader, which is why criterion 4 names three things and not two.

## Phase 3 — unify the pipeline

Backlog item 7. **Before any behaviour fix**, so each is made once.

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | one function runs steps 2–8; both entry points call it | 1 definition | `grep -n "def run_pipeline"` |
| 2 | the CLI's printed output is unchanged for a cached extraction | byte-identical | diff against a saved run |
| 3 | the web result page is unchanged for the same inputs | same implied price | manual run |

**This phase must not change a number.** If one moves, the two paths disagreed before,
and that disagreement is the finding.

## Phase 4 — the three highest-cost silent defects

Backlog items 2, 3, 6. Each small, each now testable.

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | a missing balance sheet stops and names the year | raises | a test asserting type and message |
| 2 | an unrecognised NRI label stops and names the label | raises | same |
| 3 | a user-entered `0` is honoured, not read as "not supplied" | 0 reaches the assumption | a route test per field |

**Constraint.** Do not lock a fallback as an expectation. A test asserting
`net_debt == 0.0` makes item 2 permanent.

## Phase 5 — typed failures

Backlog items 8 and 11.

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | named exception types for the four outcomes in [AGENTS.md](../../AGENTS.md) | — | `grep` for the class definitions |
| 2 | no blanket `except Exception` in `api/` or `ingestion/` | 0 | `ruff check --select BLE001` |
| 3 | mypy errors reduced, with the remaining count recorded | < 33 | the mypy gate |

## Phase 6 — the zero defaults

Backlog item 1. **The large one. Last, with the suite in place.**

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | an empty extraction stops instead of rendering a price | raises | a test feeding an empty `FinancialStatements` |
| 2 | the zero-default count falls, and the new count is recorded | < 119 | the grep in [rules.md](../2-rules/rules.md) |
| 3 | every stop path has a test naming its field | 1 per input | `pytest -q` |

## Phase 7 — label the assumptions

Backlog items 9, 10, 13. [Rule 6](../2-rules/rules.md).

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | a substituted cost of debt is visible on the result page | shown with its source | manual run |
| 2 | the resolved provider and model appear in the output | shown | manual run |
| 3 | the D&A decision moved out of the parser, with its reasoning recorded | — | `grep` on `claude_extractor.py:479` |

## Phase 8 — show the chain

[Rule 4](../2-rules/rules.md), which states the gap in as many words: "the trace is true
by reading the source, and it is not true from the output — the result page shows a
share price and no chain."

`cli.py` prints seven blocks the web app does not: the income statement, the cash flow
statement, the balance sheet with its balance check, the non-recurring items that were
**applied**, the GAAP to non-GAAP reconciliation, the historical FCFF table, and the
`(override)` tag on each assumption ratio. The web app shows only the items that were
**withheld**, which is the inversion of what a reader needs.

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | both routes carry the raw statements, the normalised statements, the applied items and the excluded items | 4 named fields | `grep -n "class CachedExtraction" api/routes_valuation.py` |
| 2 | `GET /assumptions` renders all seven blocks | 200, every block present | `TestClient` over a stubbed extraction |
| 3 | `POST /valuation` renders all seven blocks | 200, every block present | same |
| 4 | a year with no extracted statement renders the words, never a zero and never a blank | `not extracted` | `grep` on the rendered body |

**Constraint.** This phase must not change a number. It shows figures that already
exist. If a displayed figure disagrees with the CLI's for the same inputs, the two paths
disagreed before, and that disagreement is the finding.

**Do not copy `cli.py`'s print layer.** It holds three rule 3 sites — `:508`, `:522-538`
and `:593` — each a conditional zero or a blank cell standing in for a missing
statement. A blank cell and a zero cell are the same bytes to a reader.

## Phase 9 — two extraction routes, one parser · **done `a375dae`**

**Decided by the user on 2026-10-02.** Every extraction today is a paid API call: two
per filing, so six for three 10-Ks, plus up to two retries per filing. The user wants a
second route. A Claude Code session reads the PDF in the chat, writes the same two JSON
answers the API would return, and saves them to a file. The pipeline then reads that
file instead of calling the API.

**Both routes must meet at the parser.** The same schema, the same
`_parse_financials_response` and `_parse_nri_response`, the same arithmetic check, the
same multi-filing plan and the same merge. A route with its own parser is a second
pipeline, which is the shape of backlog item 7.

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | one plan and one merge, used by both routes | 1 definition each | `grep -n "def plan_filings\|def merge_filing_extractions" ingestion/` |
| 2 | the same JSON gives the same statements by either route | equal dataclasses | a test feeding identical JSON through both |
| 3 | the CLI values a company from a session file with no API credential set | a DCF result | `cli.py --session-file …` with every key unset |
| 4 | the web app values a company from an uploaded session file | 200, the result page | `TestClient` and a manual run |
| 5 | the output names the route | transport `Claude Code session` shown | CLI output and the result page |
| 6 | a session file whose PDF changed on disk stops and names the file | raises | a test |
| 7 | a session file missing a schema key stops and names the filing, year and key | raises | a test |

**Constraint.** Route A must not change a number. A test that held before this phase
holds after it.

**Result at `a375dae`.** Every criterion passes. 1: `plan_filings` and
`merge_filing_extractions`, one definition each (`ad52e1a`). 2: route equality tests in
`tests/unit/test_session_extraction.py` (`92549f8`). 3: `cli.py --session-file` with
every credential removed and `_call_llm` disabled (`ad52e1a`, re-run by review). 4:
`tests/unit/test_routes_session.py` (`5294a73`), and the real Walmart file through the
web routes gave the CLI's $28.84. 5: the stage 1 line and both pages name
`Claude Code session`. 6 and 7: loader stop tests (`92549f8`, `a375dae`).

## Phase 10 — the user's fixes of 2026-10-02 · **done at `P10-tests`**

The user asked on 2026-10-02 for three backlog items to be fixed, in their own words:
"item 48: fix, item 45: fix, item 43: can get it from the filename, but need to verify
against content of the file". Item 48 adds a field the model is asked to read, so this
is also the user's approval of that change to the LLM boundary.

| Unit | Item | Criterion | Measured by |
|---|---|---|---|
| `P10a-nci-bridge` | 48 | equity value = EV − net debt − noncontrolling interest; absence stops | a test with round numbers |
| `P10b-capm-variance` | 45 | the constant-market stop names `market_returns` on every SciPy version | `test_capm.py` on macOS |
| `P10c-fiscal-year` | 43 | a filename year the filing contradicts stops, naming both | `discover_filings` on `10K_filings/LHX` |

## Phase 11 — the model reads printed lines; Python does every sum

**Decided by the user on 2026-10-02** ("go with option A … if the balance sheet check
doesn't pass, just fail it and show it"). Backlog item 56. Every Pass 1 money field
becomes a list of the printed rows that make it up, and Python adds them. The prompt no
longer asks the model to plug the balance sheet, so the balance check becomes a real
test of the reading.

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | no prompt sentence asks the model to compute | 0 | a grep, each remaining hit explained |
| 2 | both routes give equal statements from the same JSON | equal | the route equality test |
| 3 | a dropped balance sheet row fails and is shown; the figures are kept | `FAIL` | a test |
| 4 | a balance check difference above 1 unit is `FAIL`, not the old 2% `OK` | `FAIL` | the CLI and the result page |

---

## Rules for every phase

1. **A criterion is a measurement, never an opinion.** If it cannot be measured by a
   command, rewrite it.
2. **A phase that changes a number says which number and why.** Phase 3 explicitly must
   not.
3. **Re-measure the counts in `STATUS.md` when a phase lands.** Never carry a figure
   forward.
4. **A failing or blocked unit is still committed**, and the message says so.
