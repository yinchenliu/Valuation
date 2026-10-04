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

## Phase 11 — the model reads printed lines; Python does every sum · **done at `P11a-tests`**

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


## Phase 12 — every printed line is found on the page it cites · **done at `P12a-tests`**

Backlog item 59, from the `P11a` review's F7. Since `P11a` every Pass 1 figure is a list
of printed lines, but nothing checks that a line was printed: a model can add a row of
the size of a gap, and every arithmetic check passes. Both routes now look for each
line's label and figure on its cited page with `pdfplumber`. A line not found is a
failed check, shown with the figures kept, as the user decided on 2026-10-02 for a
failed balance check.

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | Walmart's real session file is clean | 89 of 89 lines found; `check` exits 0 | `session_extraction check extractions/WMT.json` |
| 2 | an invented row that balances is caught | `check` exits 1, naming the field, line, label and page; the balance check stays `OK` | a scratch copy of `WMT.json` |
| 3 | both routes run one check | one definition; route A's runner and route B's loader each call it | a grep |
| 4 | route A's retry names the row and states no amount | no gap or total in the retry text | a stubbed run on the real PDF |

**Result.** Every criterion passes. 1 and 2: `P12a` (`a64818b`), re-run by both reviews;
the invented `Other current assets` = 4,124 on page 22 fails while both balance rows stay
`OK`. 3: one walk, `_printed_line_failures`, called by `_run_financials_pass` and through
`printed_line_page_failures` by `load_session_extraction`. 4: the retry names label,
field and page and no amount. `P12a-tests` locks each outcome with PDFs it writes,
including the attack end to end (`tests/unit/test_page_check.py`).

## Phase 13 — silent defects first

**The user's decision of 2026-10-03:** "I want to start with silent defects first." This
moves the silent items ahead of phase 3. The cost of that order is small, and it is
measured: 13 of the 16 open silent items sit in code that both entry points share
(`models/`, `analysis/`, `ingestion/`, `config.py`), so one fix reaches both. Only items
6, 7 and 49, and the yfinance fallback of item 44, sit in the duplicated orchestration.

Wave 1 holds the items that do not touch the LLM boundary. Items 10, 44 and 50 wait for
the user's decision on the Pass 1 role. Item 23 goes with item 1, because an empty
statement cannot be told from a zero one until the zero defaults are gone. Item 36 is a
measurement and needs paid runs or sessions.

| Unit | Items | Files |
|---|---|---|
| `P13a-analysis-silent` | 25, 38 | `analysis/normalizer.py`, `analysis/wacc.py` |
| `P13b-models-silent` | 15, 32, 39, 42 | `models/financial_statements.py`, `models/valuation.py`, `analysis/dcf.py`, `analysis/projector.py` |
| `P13c-env-override` | 46 | `config.py`, `ingestion/claude_extractor.py`, `docs/8-build/environment.md` |

**Wave 1 is done at `19298f3`.** Wave 2, on the user's "go" of 2026-10-03, holds the
silent items that the wave 1 runs found, plus item 50, which no longer waits: the user
decided the Pass 1 role the same day.

| Unit | Items | Files |
|---|---|---|
| `P13d-upside-price` | 65 | `models/valuation.py`, `analysis/dcf.py` |
| `P13e-growth-input` | 66, 67 | `analysis/projector.py` |
| `P13f-wacc-debt` | 69, 38b | `analysis/wacc.py` |
| `P13g-pass2-unread` | 50, and item 8's site in `_run_nri_pass` | `ingestion/claude_extractor.py` |

| # | Criterion | Expected | Measured by |
|---|---|---|---|
| 1 | each wave 1 item stops and names its input, or labels what it did | a `ValueError` naming the field, or a clause in the label | the command in each assignment |
| 2 | no wave 1 unit moves a figure on a complete input | Walmart's normalised statements and assumptions unchanged | `cli.py --session-file extractions/WMT.json`, stages 1 to 5 |
| 3 | the gates do not get worse | ruff 5 or fewer, mypy 10 or fewer, census 67 or fewer | the gates in [environment.md](environment.md) |

**Wave 2 is done at `0a5a715`.** Wave 3 holds item 38b (a). **The user's decision of
2026-10-04:** option 1, an explicit "confirm zero debt" choice on the form and on the
CLI. A supplied cost of debt no longer counts as that confirmation.

| Unit | Items | Files |
|---|---|---|
| `P13h-zero-debt-confirm` | 38b (a) | `analysis/wacc.py`, `models/valuation.py`, `cli.py`, `api/routes_valuation.py`, `templates/assumptions.html` |

`P13h` and `P14a` both edit `cli.py`, so `P14a` starts after `P13h`'s code review approves.

## Phase 14 — the Pass 1 role · **`P14a` done at `69436d9`; `P14b`, `P14c` not started**

**The user's decision of 2026-10-03:** options 0, A, B and C, recorded under rule 1 in
[rules.md](../2-rules/rules.md); options D and E refused. This is the approval
`AGENTS.md` requires for a change to what the model returns. Items 10 and 44 go with it,
because both sit in the Pass 1 parse.

| Unit | What | Items |
|---|---|---|
| `P14a-units` | read the printed unit statement for money (`units`) and for the share count (`share_units`), each with its page and page-checked; Python reads the scale word and converts to millions once, per filing. The user approved `share_units` on 2026-10-04 | 44 |
| `P14b-pass2-units` | each Pass 2 item copies its figure as printed, its page, and the printed words that state its unit; Python reads the scale and converts each item. Session format v4. **The user's decision of 2026-10-04: "fix 77a"** | 77 |
| `P14b-reasoning` | 0: route A asks the model to reason first. B: the prompt allows a printed figure from a note or MD&A. Prompt only | — |
| `P14b-row-reasons` | A: a reason for each printed row, shown on both pages. A format change; Walmart is extracted again | — |
| `P14c-layout-facts` | C: a cited layout fact, checked on its page; the D&A decision moves out of the parser into `analysis/` and reads that fact | 10 |

All three touch `ingestion/claude_extractor.py` and the session file format, so they run
in sequence, after wave 2's `P13g`.

**`P14b` is split in three, on 2026-10-04,** so each unit fits one build run. Options A
and C both need the model to write new text for each filing. So Walmart is extracted
again once, after both land, and not once for each. The build order and the state of
each unit are in `.agent/QUEUE.md`. Each unit states what happens to a `v2` session file
such as `extractions/WMT.json`.

**After Phase 14: Phase 3**, on the user's "ok" of 2026-10-04. Items 7, 49 and 72 sit in
the code that `cli.py` and `api/` duplicate, so one pipeline lets each later fix reach
both entry points.

---

## Rules for every phase

1. **A criterion is a measurement, never an opinion.** If it cannot be measured by a
   command, rewrite it.
2. **A phase that changes a number says which number and why.** Phase 3 explicitly must
   not.
3. **Re-measure the counts in `STATUS.md` when a phase lands.** Never carry a figure
   forward.
4. **A failing or blocked unit is still committed**, and the message says so.
