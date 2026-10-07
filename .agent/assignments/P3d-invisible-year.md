---
id: P3d-invisible-year
phase: 3 — unify the pipeline (part 4)
agent: programmer
depends_on: [P3a-one-pipeline, P3b-pipeline-stops, P3c-one-number]
---

# A year with no income statement is in no table, and the branch written to report it cannot run (item 116)

## Objective

**Fact 1.** `models/financial_statements.py:435-440`:

```python
@property
def years(self) -> list[int]:
    """Available years sorted ascending."""
    year_set = set()
    for stmt in self.income_statements:
        year_set.add(stmt.year)
    return sorted(year_set)
```

The set is built from `self.income_statements` **alone**. `self.balance_sheets` and
`self.cash_flow_statements` are not read.

**What follows.** A year that has a cash flow statement and a balance sheet but no income
statement is **not in `years` at all**. It is in no table, it carries no reason, and
nothing anywhere reports it. The figures were extracted and then dropped without a word.

**Fact 2, and it is the proof that fact 1 is a defect rather than a choice.** Both entry
points hold a branch written to report exactly this case, and neither branch can run:

| File | Line | Code |
|---|---|---|
| `cli.py` | 737-738 | `if is_ is None: missing.append("income statement")` |
| `api/routes_valuation.py` | 266-267 | `if income_statement is None: missing.append("income statement")` |

Both sit inside a loop over `financials.years`, and both then call
`get_income_statement(year)` for a year that came **from** the income statements. The call
cannot return `None`. Two authors wrote that branch because the case is real; the set they
iterate hides it.

**Found by the `P3c-one-number-tests` tester (T1) on 2026-10-06 and confirmed by the
overall lead against the code.**

**Fact 3, and it decides the shape of the work.** `.years` has **twelve** readers outside
`tests/`. One of them crashes if the set is widened without being touched:

```python
analysis/projector.py:171
revenues = [financials.get_income_statement(y).revenue for y in years]
```

A year with no income statement makes that `None.revenue` — an `AttributeError` with no
field named, deep inside the projection, which the blanket `except Exception` then renders
as a string on the results page. **Widening `years` and stopping there would turn a silent
omission into an unnamed crash.** That is not an improvement; it is the same defect with a
louder failure.

**Fact 4.** `models/financial_statements.py:455-467`, `latest_year`, reads `max(self.years)`
and raises a `ValueError` whose message says "holds no income statements". If `years` is
widened, that message can become false: the list would be non-empty while the income
statements are not.

**What follows.** When this unit is done, a year that any statement covers is visible with
a reason naming what is missing; no reader of the year list crashes; and every reader has
been visited on purpose, with its choice written down.

## Do not delete the dead branch

**This is the trap in this unit and it is cheap to fall into.** Coverage reports both
branches in fact 2 as unreachable, and the smallest change that makes the report clean is
to delete them. **Deleting them removes the only evidence in the code that the case
exists, and the year stays invisible.** The branch is right. The set it iterates is wrong.

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-07, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1224 passed, 2 skipped, 0 failed** |
| full suite | `-m pytest -q` | **2 failed**, the two red on purpose |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 5 errors in 2 files, 21 checked |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.claude/check_guard.py` | 48/48 |

**There is no test-order guard on this machine, and no command below asks for one.**
`pytest-randomly` is not installed, so every run uses one fixed order. **Do not add
`-p no:randomly` to any command**: it was deleted from every live document on the user's
decision of 2026-10-07 because it asserted nothing (item 126, closed). The gap it leaves
is item 127 and it is not yours to fix. **What it means for you**: comparing two runs by
the **set of failing test names** is sound, and comparing them by count is not.

**The twelve readers of `.years` outside `tests/`, each read on 2026-10-07:**

| File | Line | What it does with the year |
|---|---|---|
| `models/financial_statements.py` | 460 | `latest_year` takes `max(years)` and its stop message names income statements (fact 4) |
| `analysis/projector.py` | 167, 171 | **the crash site.** Builds `revenues` by calling `get_income_statement(y).revenue` for every year |
| `api/routes_valuation.py` | 261 | the historical FCFF table; holds the dead branch of fact 2 |
| `api/routes_valuation.py` | 317 | `sorted(set(raw.years) \| set(adjusted.years))` |
| `ingestion/claude_extractor.py` | 2309 | `target_years or financials.years` |
| `ingestion/claude_extractor.py` | 2628, 2642 | two message strings |
| `ingestion/claude_extractor.py` | 3525 | a `MERGED:` print |
| `ingestion/session_extraction.py` | 1075 | the `Years:` summary line |
| `cli.py` | 424, 669, 721, 1055 | four separate loops; `:721` holds the dead branch of fact 2 |

**Visit every one.** A reader you do not visit is a reader that assumed something you
changed.

## What to do

1. **Make a year that any statement covers reachable**, and say in a docstring which
   statements the set is built from. How you expose it is yours: widen `years`, or add a
   second accessor beside it and leave `years` as the income-statement set. **State the
   choice and its reason in your entry.**
2. **Visit all twelve readers and record each one in a table**: the file, the line, which
   set it now reads, and **why**. A reader that genuinely needs an income statement for
   every year must say so and read a set that guarantees one.
3. **`analysis/projector.py:171` must not crash and must not silently skip.** A projection
   cannot be built from a year with no revenue. If the projection refuses such a year, it
   refuses **by name**, through the rule 3 shape this repository already uses: a stop that
   names the field and the year. `None.revenue` is not a stop.
4. **Make the two dead branches run.** After this unit, a year with no income statement
   appears in the CLI's table and on the web page with its reason, exactly as a year with
   no cash flow statement already does. **Do not delete either branch.**
5. **Correct `latest_year`'s message if its premise moved** (fact 4). A message that names
   income statements must still be true when it prints.
6. **No figure may move for a filing whose years all have an income statement.** That is
   every filing in this repository today. Prove it: Walmart's implied share price and its
   whole stage table must be identical before and after.
7. **Record what you find, do not widen your scope.** A defect outside this list goes in
   your entry under "Found". The overall lead puts it in the backlog.

## Files in scope

- `models/financial_statements.py`
- `analysis/projector.py`
- `api/routes_valuation.py`
- `cli.py`
- `ingestion/claude_extractor.py`
- `ingestion/session_extraction.py`
- `pipeline.py`, **only if** a reader you visit sits there

**Nothing else.** This is a wide scope by necessity: the defect is one property and its
twelve readers. **It is not a licence to change anything else in those files.** A change
not traced to a reader of `.years` is a review finding.

## Out of scope

- **`tests/`.** The write guard denies it. This unit's tests are a separate assignment
  after the code review.
- **Backlog item 127**, the absent test-order guard. Named above so you compare failing
  sets by name and never by count.
- **Backlog items 119, 120, 121, 122, 123, 124, 125** in the files you touch. Each is
  recorded.
- **Backlog item 8**, the blanket `except Exception` that would render your `AttributeError`
  as a string. Four sites, each recorded. Do not touch them, and do not rely on them.
- **The two tests that are red on purpose.** Leave both red.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`. Use `PYTHONIOENCODING=utf-8` for any
command that prints a prompt.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | The old behaviour is reproduced first | at `HEAD`, a year with only a cash flow statement and a balance sheet is **absent from both tables** and no message names it | `git archive HEAD` into a scratch directory. **`git stash` is forbidden.** Build the statements by hand |
| 2 | That year is now visible in the CLI | the year appears with its reason | hand-built statements, `print_historical_fcff` |
| 3 | That year is now visible on the web page | the year appears with its reason | the same statements through `_historical_fcff_by_year`, rendered |
| 4 | Both entry points say the same thing for it | the same words | criteria 2 and 3 side by side |
| 5 | The projection refuses it **by name** | a stop naming the field and the year, never an `AttributeError` | `analysis/projector.derive_assumptions` on the same statements. Print the exception type and its message |
| 6 | Every one of the twelve readers is visited | a table of 12 rows: file, line, set read, reason | your entry |
| 7 | `latest_year`'s message is true when it prints | quote it for a filing with a balance sheet and no income statement | execute it |
| 8 | Walmart does not move | the implied share price and every stage figure identical before and after | `cli.py --session-file extractions/WMT.json`, both trees, **in one sitting**: the market call drifts by about ±$0.01 between runs taken minutes apart |
| 9 | No figure moves for any filing whose years all have an income statement | state it, and name the input you proved it on | criterion 8 plus one hand-built filing |
| 10 | Types | 5 errors in 2 files, or fewer. Name any you removed | the mypy command above |
| 11 | Lint | 4 errors, every one `BLE001`. **Run `ruff check .` after your last edit** | `-m ruff check .` |
| 12 | Census | 64, or fewer. Name any site you removed | the grep at `docs/2-rules/rules.md:102` |
| 13 | Route | 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` |
| 14 | The failing test set | name every test that changed state and why | `-m pytest -q --ignore-glob="*_rule3_red.py"`, before and after, compared **by name** |
| 15 | Neither dead branch was deleted | both still in the diff, and both now reachable | `git diff`, plus criteria 2 and 3 |

**Every criterion is a measurement, never an opinion.** Criterion 1 exists because a fix
whose "before" was never reproduced is a fix for a defect nobody has seen. Criterion 5
exists because the cheapest wrong answer here is an `AttributeError`.

## Citations

- `docs/2-rules/rules.md` — rule 3 (a missing input stops and names itself) and rule 6.
- `docs/9-reference/refactor-backlog.md`, item 116, with the 2026-10-06 measurements.
- `.agent/journal/2026-10-06T1121-tester-p3c-one-number-tests.md` — finding T1, which
  found it.
- `models/financial_statements.py:435-467` — `years` and `latest_year`.
- `analysis/projector.py:167-171` — the crash site.
- `.claude/agents/programmer.md` — your role card.

## Known open items

- **Never mutate a file in this repository, not even briefly.** A spot check left a
  `return []` in `ingestion/claude_extractor.py` on 2026-10-05 with a comment saying it had
  been restored. It had not, and a check was dead for about ten hours. Work in a scratch
  copy and print the repository file's sha256 before and after.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- **`extractions/WMT.json` is not in git.** Three filings, five fiscal years, 2022 to 2026,
  balance sheet on `filings[2]`. Do not edit it and do not delete it.
- The suite takes about 135 seconds.

---

## Overall lead ruling on review round 1 (2026-10-07)

The code reviewer returned `changes_requested` with one `major`, two `minor` and two
`note` findings. Its entry is
`.agent/journal/2026-10-07T1150-code_reviewer-p3d-invisible-year.md`. **Read it and answer
every finding by number.** This section rules on the one question the reviewer put to the
overall lead, and it binds: where it and the reviewer's text differ, this section wins.

### The ruling: F1 is fixed in `cli.py` and nowhere else

**The reviewer's F1 is correct and it blocks.** I read `cli.py:506` myself. The net-margin
row holds `financials.get_income_statement(y).net_income / financials.get_income_statement(y).revenue
if financials.get_income_statement(y).revenue else 0`. The unit deleted that line from
`print_extracted_financials` and added it inside the new `_print_income_statement_table`.
`docs/9-reference/severity.md:83` says a defect the unit touched is the unit's, backlog or
not, and that moving a line makes it yours. The two downgrades the reviewer refused stay
refused.

**The reviewer then asked whether to widen F1 to `models/financial_statements.py:108`
(`gross_margin`) and `:132` (`operating_margin`), which carry the identical
`if self.revenue else 0.0`. The answer is no. Here are the two facts that decide it.**

**Fact A.** `templates/_statements.html:44` and `:86` render those same two properties as
`{{ "{:.1f}%".format(stmt.gross_margin * 100) }}` and the operating-margin equivalent,
guarded only by `{% if stmt is not none %}`. So for a year whose revenue is 0 the **web
page prints `0.0%` today**, exactly as the CLI does. `templates/` is out of this unit's
scope. **What follows:** repairing those two rows inside `cli.py` alone would make the CLI
say one thing and the page say another for the same cell. That is this repository's named
third trap, two entry points drifting apart, and it would be a new defect that this unit
created.

**Fact B.** `analysis/projector.py` reads `income.operating_margin` into `op_margins`, and
that average reaches the DCF and the share price. **What follows:** changing
`operating_margin` at the property is not a display repair. It moves a figure, it needs
its own tests and its own before-and-after measurement, and it belongs with the census
unit for backlog item 1 that takes both entry points together.

**So the within-table inconsistency the reviewer warns of is real and I accept it on
purpose.** Today all three margin rows print a fabricated `0.0%`. After this round the
net-margin row tells the truth and the two above it still do not. A reader who sees one
row say the figure is absent learns something that today's table hides from them. That is
a partial repair, not a contradiction, and the rest is recorded in the backlog by me.

### What to do, by finding number

1. **F1 (`major`, blocking).** In `cli.py`, make the net-margin cell stop printing a
   fabricated `0.0%` when revenue is 0. Use the **same vocabulary this unit already
   established** for a figure that is not there, so the table speaks one language. Do not
   raise out of a table build: a table that raises prints nothing at all, and the reader
   loses the twelve rows that were fine. **Do not touch `models/financial_statements.py:108`
   or `:132`.** State in your entry what the cell now prints and what the other two print
   beside it.
2. **F2 (`minor`).** `ingestion/claude_extractor.py:2319`,
   `target_years or financials.income_statement_years`. **First read every caller and say
   in your entry whether any one of them passes an empty list and relies on it meaning
   "every year".** If none does, fix the shape. If one does, leave the line, name that
   caller, and say so. Do not change what any current caller receives.
3. **F3 (`minor`).** `_print_latest_balance_sheet` prints the latest balance sheet, and
   `pipeline.py` nets debt from `get_balance_sheet(latest_year)`. The two can differ with
   nothing saying so. `pipeline.py` is out of scope and stays out. **In the CLI, when the
   balance sheet year it prints is not `latest_year`, say so on the line.** A reader must
   be able to see the divergence where it happens.
4. **F4 (`note`).** The comment at `cli.py:748` says the CLI names an unreconciled year "in
   the same words" as the web, and the reviewer measured that it does not: CLI
   `raw income statement, adjusted income statement` against web
   `raw and adjusted income statement`. **Make the comment true, or make the words
   identical.** Say which you chose and why.
5. **F5 (`note`).** A filing with no income statement at all reports the fact twice.
   **Leave it.** I record it. Do not widen your diff for it.

### What does not change

- **The design is approved.** Widening `years` to the union, adding `income_statement_years`
  beside it, pointing `latest_year` at the narrow set, and making `derive_assumptions` read
  the wide set and stop by name: all four stand. The reviewer re-ran all fifteen criteria on
  its own scratch trees and all fifteen agree.
- **Neither dead branch may be deleted.** Criterion 15 still binds.
- **Re-run every done-criterion after your last edit**, not beside the edit that prompted
  it. `STATUS.md` records an overturn caused by a gate measured before the last write.
  Criteria 8, 11, 12 and 14 are the ones a late edit moves.
- **`tests/` stays untouched.** The tester is a separate assignment.

---

## Overall lead review: `accepted` (2026-10-07)

**Re-run by me, not read.** Every figure below is from my own command on the Windows
machine (`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`.

| Gate | Command | Result |
|---|---|---|
| gate form | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1257 passed, 2 skipped, 0 failed** in 151.77s. The baseline 1224 plus the tester's 33 |
| full suite | `-m pytest -q` | **2 failed, 1257 passed, 2 skipped**, and the failing set is exactly the two red on purpose, by name: `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops` |
| lint | `-m ruff check .` | **4 errors, every one `BLE001`**: `api/routes_valuation.py:463`, `:745`, `cli.py:1411`, `tests/test_e2e_all_googl.py:106` |
| types | the mypy command above | **2 errors in 2 files**, 21 checked: `analysis/projector.py:395` and `api/routes_upload.py:28`. Three removed against the 5 at `HEAD`, and criterion 10 asked for 5 or fewer |
| census | the grep at `docs/2-rules/rules.md:102` | **64**, unchanged |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | **200** |
| write guard | `.claude/check_guard.py` | **48/48** |
| scope | `git diff --stat -- . ':(exclude).agent' ':(exclude)docs'` | six files, 400 insertions, 45 deletions. No `tests/`, no `templates/`, no `pipeline.py`. The tester added one file, `tests/unit/test_p3d_invisible_year.py` |

### I ran one mutation myself, and I chose the one the unit was written around

**Criterion 15 is this unit's trap**: the cheapest way to make the coverage report clean
was to delete the two branches, and that would have left the year invisible. The tester
reports that mutation as caught by **2** tests, which is thin, so I built it myself rather
than take the count on report.

In a scratch copy at `C:\tmp\p3d_accept` I deleted `if is_ is None: missing.append("income
statement")` from `cli.py` and `if income_statement is None: missing.append("income
statement")` from `api/routes_valuation.py` — the exact edit a programmer who fell into the
trap would make, and one that leaves the surrounding `if is_ is None or cf_ is None:` in
place, so the year still gets a row and the row has no reason.

```
control   33 passed
mutant     2 failed, 31 passed
          FAILED … ::test_the_cli_fcff_table_prints_a_row_for_the_year_with_no_income_statement
          FAILED … ::test_the_web_fcff_rows_hold_a_row_for_the_year_with_no_income_statement
```

**One failure per entry point, which is the right shape**: a fix applied to one entry point
and not the other cannot pass. The repository's `cli.py` carries sha256
`f87e2915…` before and after the run, unchanged.

### What I verified for myself beyond the gates

**`cli.py:845` is unchanged context, so finding 128 is not this unit's.** Both the code
reviewer and the tester found that `cli.py` iterates `raw.years` where
`api/routes_valuation.py:329` iterates the union, and both refused to charge it to this
unit. I checked the claim rather than accept it: `git diff -U0 -- cli.py` matches that line
with neither `+` nor `-`. `docs/9-reference/severity.md:83` makes a defect the unit's only
when the unit touched it, and this unit did not. Recorded as item 128.

### The three rounds, and what each one changed

1. **Programmer round 1.** The design: widen `years`, add `income_statement_years`, point
   `latest_year` at the narrow set, make `derive_assumptions` read the wide set and stop by
   name. All twelve readers visited and tabulated.
2. **Code reviewer round 1, `changes_requested`.** F1 `major`: the unit moved a line holding
   `net_income / revenue if revenue else 0` into a new function, which makes the defect the
   unit's under `severity.md:83`. F2 and F3 `minor`, F4 and F5 `note`.
3. **My ruling**, above. F1 is fixed in `cli.py` and nowhere else, on two facts: the page
   renders the same two properties, so a repair here alone splits the entry points, and the
   projector reads `operating_margin` into the share price, so changing the property moves a
   figure.
4. **Programmer round 2.** F1 to F4 answered, F5 left as ruled.
5. **Code reviewer round 2, `approved`.** All fifteen criteria re-run on its own scratch
   trees after the late edit. Four `note` findings, none citing a rule.
6. **Tester, `pass`.** 101 of 101 assertions hand-sourced, 0 from the code's output. 78 of
   78 added statements covered, 0 missed. Seven mutations, seven killed.

### What this closes and what it opens

**Backlog item 116 is closed.** Items **128 to 137** are opened for what the three agents
found and this unit deliberately did not fix.

**One live behaviour change, recorded in `STATUS.md`:** a year reached only by a balance
sheet or a cash flow statement now **stops** the valuation, where it used to be dropped in
silence. That is the rule 3 answer and it is right, because the silent drop moved the
revenue CAGR. No input in this repository has that shape today: `extractions/WMT.json` has
`years == income_statement_years`.
