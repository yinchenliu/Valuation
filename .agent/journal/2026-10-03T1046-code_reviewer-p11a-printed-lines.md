---
agent: code_reviewer
assignment: P11a-printed-lines
round: 1
verdict: changes_requested
---

# Review of P11a-printed-lines, round 1

Programmer entry: `.agent/journal/2026-10-03T1029-programmer-p11a-printed-lines-run3.md`
(run 3; it owns run 2's diff). Diff reviewed: `git diff 631cf45` over the eight files
in scope. The `.agent/journal/INDEX.md` change is the orchestrator's and was not reviewed.

## The guard checks

Run over the five code files in scope. Then I listed every line the diff added (692
lines, `/tmp/p11a_added.txt`, from `git diff -U0 631cf45` per file) and ran all
the patterns against those lines alone: **0 hits**. Every hit below is on an untouched line.

| Check | Result |
|---|---|
| conditional zero | hits at `models/financial_statements.py:64,88,108,115,366`, `cli.py:200,1035,1043`. All untouched, backlog item 1 |
| lookup with a fallback | `claude_extractor.py:1043-1044` (`ticker or data.get("ticker", "")`), `cli.py:1039`, env-var reads. Untouched. The programmer listed `:1043` |
| bare or-default | `claude_extractor.py:884-886` (Gemini token counts). Untouched |
| money field defaulted to zero | 45 in `models/financial_statements.py`, all untouched. The two new memo fields are `float \| None = None` (`:211-212`) |
| `**kwargs` | clean |
| `getattr(` | `claude_extractor.py:885-886` literal names; `cli.py:682` untouched |
| dict of functions keyed by data | clean |
| model client outside `ingestion/` | clean |

New `.get(` calls without a default at `session_extraction.py:432,449`: each result is
`isinstance`-tested and the absence is reported by `pass1_problems` first. The programmer
answered this in the rule 3 table. Accepted.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| any year / balance sheet line field absent | yes: field and year | `routeA.py`/`crit6.py`: `year 2025: key 'sbc' is absent.`, `balance sheet 2026: key 'total_assets' is absent.` |
| malformed line (no page, `"26642"`, `true`, NaN, page 0, blank label, bare number, null) | yes: field, year, line index | `/tmp/p11a_rev/crit6.py`, 9 cases, each `Pass1ShapeError` |
| line `value` an integer beyond float range | stops, but **unnamed** (`OverflowError` traceback) | F4 |
| `latest_balance_sheet` absent | yes | `key 'pass1.latest_balance_sheet' is absent.` |
| `[]` on a component field | reads 0, by the assignment's definition | `figure_from_printed_lines` `:473` |
| `[]` on `gross_profit` | SKIP, labelled | `check` output: `SKIP: the filing prints no gross profit row` |
| **`[]` on `total_assets` / `total_liabilities_and_equity`** | **no: becomes a printed 0** | F1 |
| **`[]` on `operating_income` / `net_income`** | **no: becomes a printed 0** | F2 |
| `printed_total_*` `None` on a `BalanceSheet` | "not extracted", counted as a failure | `models/financial_statements.py:262-264` |
| session format v1 | yes, names both formats | `check /tmp/p11a_rev/wmt_v1.json` exit 2 |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | unchanged by the unit. The tolerance is 1 "in the filing's units". The new page header says `Printed ($M)` beside "in the filing's units" (`templates/_statements.html:340-341`). Item 44, see below |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing | clean on added lines. `if bs_data:` tests `{}` (the "skip" answer), `len(entry["gross_profit"]) > 0`, `difference is None` |
| `analysis/` imports no `ingestion/`, `api/` or model client | untouched; `models/` gained no import |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | no prompt sentence asks to compute | 0 hits | `grep -n -i "sum of\|combine\|minus\|adjust catch"` gives 0 lines. A scan of the rendered system prompt for add/sum/subtract/reconcile/adjust/plug finds only prohibitions ("NEVER add, subtract or net rows", "never add it to any total") | yes |
| 2 | both routes, same statements | ALL EQUAL | `/tmp/p11a/r3_equal.py` run under my guard (`_build_claude_client`, `_call_claude` raise): `ALL EQUAL`, 4 calls with 2 retries (one filing) and 8 with 2 (three filings) | yes |
| 3 | capex 26,642 + 53 = 26,695 | 26,695 | I re-read PDF pages 22-23 with pdfplumber (`/tmp/p11a_rev/wmt_22_23.txt`) and checked every row of `r3_wmt_v2.json` against them. `figure_from_printed_lines -> 26695.0`, `CashFlowStatement 2026 capital_expenditures -26695.0` | yes |
| 4 | balanced sheet passes | OK at 0 | `check /tmp/p11a_rev/wmt_v2.json`: exit 0, `Total Assets 284,668 284,668 +0 OK`, `Total L + E 284,668 284,668 +0 OK` | yes |
| 5 | dropped row fails, shown, kept | FAIL +4,124 | route B: exit 1, `+4,124 FAIL`. CLI `print_extracted_financials`: `printed 284,668 mapped 280,544 diff +4,124 FAIL`. Page: status 200, red row, `<strong>FAIL</strong>`. Route A (stubbed): 3 calls, figures returned with `other_current_assets=0` | yes |
| 6 | absent key / bad line stops | ValueError naming field, year, line | 11 cases stop with the field, the year and the line named. A 10**400 `value` raises `OverflowError`, not a named error (F4) | yes, with F4 |
| 7 | v1 file stops | message names both | exit 2, `format is 'session-extraction-v1', and this reader understands 'session-extraction-v2' only` | yes |
| 8 | census falls | 114 → 67 | 67 now, 114 on a `git archive 631cf45` export | yes |
| 9 | red list | 40, all fixture shape | Compared by set from JUnit XML (`/tmp/p11a_rev/base_junit.xml`, `final_junit.xml`). Baseline 495 passed. Now 455 passed and 40 failed. No test is missing from either run, and none newly passes. **Each of the 40 fails on the shape alone:** 28 on `must be a list of printed lines`, 9 on the v1 refusal (its unique "cannot be converted" text), 2 on `check` exiting 2 for that same 56-problem shape stop (captured stdout), and 1 on the key tuple (`total_assets` extra). The names match the programmer's list | yes |
| 10 | lint, types | ruff 5, mypy 10 | ruff `Found 5 errors.`, the same five BLE001 with their lines moved. mypy `Found 10 errors in 4 files`, the same set | yes |

## The two questions put to me

**Route A's retries sending the PDF: right.** The retry asks the model to read the rows
again. Without the document, the only way to comply is to write rows from memory, and
rule 1 forbids that. The stub run confirms each shape and check retry carries
`pdf_bytes`, and the JSON-syntax repair does not (`json repair calls: [(..., True),
('The following JSON is malformed. ...', False)]`). **The cost is labelled only in part.**
Each retry prints its token counts. `extraction.md` says the PDF is sent again. But the
route cost row at `extraction.md:184` still reads "plus up to two retries", and does not
say each retry is now a full-document call. That is F3.

**`[]` on a printed total reads 0 and FAILs: overruled.** See F1.

## Findings

### F1 — `[]` on a printed balance sheet total is shown as a printed 0 · `major`

**Evidence:** `check /tmp/p11a_rev/wmt_empty_total.json` gives `Total Assets 0 284,668
-284,668 FAIL`. The page shows `<td class="num">0</td>` under `Printed ($M)`. The error
says `printed total_assets=0`. The value is made at `claude_extractor.py:473` and stored at
`:1035-1036`. The programmer records the choice at `data-contract.md:164`.
**Rule or document:** rule 3. The filing prints Walmart's total assets as 284,668, and
the outputs say it prints 0. That zero means "we do not know". The programmer's own
reason (`data-contract.md:164`: "a balance sheet always prints both totals, so an empty
list is a misreading") argues for treating it as missing, not as 0. The model already
has the right path: `None`, "not extracted", which `_validate_extracted_data`, the CLI
and the page all count as a failure. The fail-and-show decision still holds that way.
The run keeps going, and no printed figure appears that the filing does not print. The
assignment's general sentence ("An empty list ... Python reads it as 0") gives a skip only
to `gross_profit`, and says nothing about check-only rows. Where it reaches these rows,
it conflicts with rule 3. The orchestrator corrects the assignment.
**What would fix it:** in the parser, map `[]` on `total_assets` and
`total_liabilities_and_equity` to `None`, so the status reads "not extracted", or report it
as a shape problem. Then correct `data-contract.md:164`.

### F2 — `[]` on `operating_income` or `net_income` is a printed 0, and `net_income` enters the cash flow as 0 · `major`

**Evidence:** `_YearFigures` sums `[]` to 0 (`claude_extractor.py:473`). The check then
reports `printed=0` and fails by the whole derived figure. For `net_income`, `:977` puts 0
into `CashFlowStatement.net_income`, and `other_ops = cfo - net_income - ...` absorbs the
whole of net income into `other_operating_activities`. `cli.py:436,440` prints both.
**Rule or document:** rule 3, the same defect as F1 on the income statement's check rows.
A filing that genuinely prints no operating income row (some do) gets a 100% FAIL every
time, plus two full-PDF retries.
**What would fix it:** this needs a decision the assignment does not make. Either a
labelled SKIP like `gross_profit`, or a "not printed" failure, and never a 0 into
`CashFlowStatement.net_income`. **Escalated to the orchestrator.** The programmer cannot
settle it from the assignment.

### F3 — The route A cost row does not say retries now re-send the PDF · `minor`

**Evidence:** `docs/3-architecture/extraction.md:184`: "two API calls per filing, plus up to
two retries". Since run 3, each shape or check retry is a full-document call (`_call_claude`
attaches the base64 PDF and sets no prompt cache, `claude_extractor.py:792-800`). So Pass
1 can cost up to three times its input tokens per filing.
**Rule or document:** the orchestrator's question, "whether its cost is labelled". Not a
rules.md rule.
**What would fix it:** state in that cost cell that each Pass 1 retry re-sends the whole
PDF.

### F4 — An out-of-range integer `value` crashes instead of being named · `minor`

**Evidence:** `check /tmp/p11a_rev/wmt_huge.json` (capex value `10**400`) ends in
`OverflowError: int too large to convert to float` at `claude_extractor.py:417`. It is a
traceback, not a problem that names the field, the year and the line.
**Rule or document:** done-criterion 6 ("`ValueError` naming field, year, line"). It still
stops, so this is not a rule 3 break.
**What would fix it:** in `_is_finite_number`, return `False` on `OverflowError`.

### F5 — Dead `WARN` branch rewritten by the unit · `note`

**Evidence:** `claude_extractor.py:641-642`, `elif diff_pct > 0.5: status = "WARN"`, sits
after `if diff_pct > fail_pct` with `fail_pct = 0.5` (`:569`). It cannot fire. The unit
re-indented it into its new `else:`. The programmer flagged it.
**What would fix it:** delete the branch.

### F6 — A stale sentence in a bullet the unit edited · `note`

**Evidence:** `docs/3-architecture/data-contract.md:134`: "A filing that prints no such
line is extracted as an explicit `0`." Since P11a that is `[]`. Two lines above it, the
same bullet says so.

### F7 — The check retry hands the model the exact gap · `note`

**Evidence:** the retry text includes `diff=+4,124` and the mapped sum
(`claude_extractor.py:675-680`, sent by `:1340-1356`). The prompt forbids changing a value
to pass, and it carries the PDF. But a model that invents a 4,124 catch-all row with a
plausible label and page passes every check Python has. No rule is broken: the
assignment sends failures back "as today's validation errors do". This is for the
orchestrator to weigh: name the failing total, but not the amount.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 | `claude_extractor.py:1043-1044` (`ticker or data.get(...)`), `:992-1000` and `:1025` (`0.0` cash flow and `current_portion_lt_debt`), the 45 `float = 0.0` in `models/financial_statements.py`, `cli.py:422,1035,1039,1043` | no, unchanged context lines |
| 8 | `claude_extractor.py:1416` `except Exception` | no |
| 10 | `claude_extractor.py:967` D&A subtraction | rewritten only to drop the two `.get(..., 0)` reads, which closes item 10's "must stop rather than default" half. Its location stays, and the assignment keeps it on purpose. Not a finding |
| 11 | `claude_extractor.py:808` mypy | no |
| 44 | `templates/_statements.html:340-341` `($M)` headers in a table that also says "in the filing's units" | the new table copies the template's existing `$M` convention. The units label is item 44, out of scope by the assignment |

**Not this unit's diff:** `.claude/skills/extract-filing/SKILL.md` is modified in the tree
(mtime 10:39:58). It was absent from the git status taken when I was dispatched, it is not
in the programmer's `files_touched`, and the assignment gives it to the orchestrator. I did
not review it. The orchestrator should confirm that the edit is its own.

## Verdict

`changes_requested`

The code does what the assignment asks. I re-ran all ten done-criteria, and they hold
(criterion 6 with the small gap in F4). Each of the 40 red tests fails on the old fixture
shape and on nothing else. The prompt no longer asks the model to add, net or plug
anything, and running route A's retries with the PDF is the right call. **F1 and F2 block.**
An empty list on a check-only row is turned into a printed `0`, which the outputs show as
a figure the filing never printed. On `net_income`, that 0 also goes into the cash flow
statement. F1 has a fix the programmer can make inside the unit, through the existing
`None` / "not extracted" path. F2 needs the orchestrator to say what `[]` means on
`operating_income` and `net_income`, and to correct the assignment's general "`[]` reads
as 0" sentence for the check rows. F3 and F4 are minor and quick to fix in the same round.
