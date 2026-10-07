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

**`-p no:randomly` is a no-op on this machine** and several commands carry it as though it
were a guard: only `pytest` and `pytest-cov` are installed, and pytest accepts disabling an
absent plugin in silence. Backlog item 126. Do not rely on it, and do not fix it here.

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
- **Backlog item 126**, `-p no:randomly`. Named above so you do not trust the flag.
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
