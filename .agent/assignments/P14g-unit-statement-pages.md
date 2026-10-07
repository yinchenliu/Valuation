---
id: P14g-unit-statement-pages
phase: 14 — extraction correctness (part 7)
agent: programmer
depends_on: [P14d-finance-leases, P14e-nri-dedupe, P3d-invisible-year]
---

# The two unit-scale checks disagree about where a unit statement may be printed, and the stricter one stops a correct reading (item 114)

## Objective

**Fact 1.** Two checks in `ingestion/claude_extractor.py` decide where a printed unit
statement may sit, and they do not agree.

| Check | Where | What it allows |
|---|---|---|
| B1, `_row_scale_failures` | `:1654` | `pages_to_check = (page, page - 1) if page > 1 else (page,)` — the row's page **and the page before it** |
| `_unit_statement_failures`, through `_unit_statement_pages_allowed` | `:1473-1490` | for `units`, **exactly** the set of pages an income statement printed line cites. No "page before" |

**Fact 2, measured by the overall lead on 2026-10-07 against the real PDF**
(`10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf`, 147 pages, read with
`pdfplumber`). Walmart's fiscal 2024 10-K **splits its income statement across a page
break**:

```
PDF page 45, last four lines:
    Walmart Inc.
    Consolidated Statements of Income
    Fiscal Years Ended January 31,
    (Amounts in millions, except per share data) 2024 2023 2022

PDF page 46, first lines:
    Revenues:
    Net sales $ 642,637 $ 605,881 $ 567,762
    Membership and other income 5,488 5,408 4,992
    Total revenues 648,125 611,289 572,754
```

So the statement's title, its unit statement and its year header are on page 45, and
**every data row is on page 46.**

**What follows.** A model that cites page 45 for `units` has read the filing correctly:
page 45 is where the income statement's unit statement is printed. The allowed set for
that filing is `{46, 48}`, the pages its printed lines cite. Page 45 is not in it, so the
run stops. **The check refuses the right answer.**

**Fact 3, and it is the one that makes this more than a theory. The defect has already
bent a real extraction, and the evidence is in the repository.** `extractions/WMT.json`
holds three Walmart filings. The overall lead read their `units` fields on 2026-10-07:

| Filing | `units.page` | `units.printed` | Pages its printed lines cite |
|---|---|---|---|
| `filings[0]`, fiscal 2024 | **46** | `(Amounts in millions)` | `[46, 48]` |
| `filings[1]`, fiscal 2025 | 45 | `(Amounts in millions, except per share data)` | `[45, 48]` |
| `filings[2]`, fiscal 2026 | 21 | `(Amounts in millions, except per share data)` | `[21, 22, 23]` |

**Read the first row against fact 2.** The income statement's own unit statement, on page
45, reads `(Amounts in millions, except per share data)`. `filings[0]` does not cite it.
It cites `(Amounts in millions)` on page 46, which is the header of the **Consolidated
Statements of Comprehensive Income**, a different statement that happens to start on the
page of the income statement's figures.

**So the same company's two filings carry two different unit statements for the same
statement**, and the one that cites the income statement's own line is accepted only
because that filing happens to print a data row on the same page. **No figure moved and no
scale word was invented** — both texts say millions — but the check is steering what the
model cites, and the thing it steers toward is the other statement's header.

**Fact 4.** The model is asked for the right thing already. The Pass 1 schema at
`ingestion/claude_extractor.py:223` and `:227` says `"page": "int — the 1-based PDF page it
is printed on"`. That instruction is correct and **it does not change in this unit**. The
check is what is wrong.

**What follows.** When this unit is done, a unit statement printed on the page before its
figures is accepted, both checks state the same rule about where a unit statement may sit,
and nothing the checks used to catch gets through.

## The trap in this unit, stated first

**You are widening a check. A check that is widened too far catches nothing, and nothing
downstream can tell.** These two checks exist because a wrong scale word multiplies every
figure in the filing by a thousand. Rule 1 lets the model copy a printed unit statement; it
is Python that reads the scale and converts. The page check is the only thing that confirms
the words the model copied are really printed where it says.

**So every widening in this unit must be paid for with a measurement of what it now lets
through.** For each page you add to an allowed set, say which wrong answer could now use
it. "It is the same rule B1 has" is a reason to make them agree. It is not a measurement of
the cost.

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-07, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`, at
commit `0a9ed51`:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1257 passed, 2 skipped, 0 failed** |
| full suite | `-m pytest -q` | **2 failed**, the two red on purpose, by name |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 2 errors in 2 files, 21 checked |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.claude/check_guard.py` | 48/48 |

**If one of these disagrees when you run it, stop and report the disagreement.** Do not
edit anything to make it agree.

**There is no test-order guard on this machine.** `pytest-randomly` is not installed, so
every run uses one fixed order. That gap is backlog item 127 and it is not yours. **Do not
add `-p no:randomly` to any command**: it was deleted from every live document on the
user's decision of 2026-10-07 because it asserted nothing. **What it means for you**:
compare two runs by the **set of failing test names**, never by count.

**The three Walmart PDFs are on this machine**, at `10K_filings/WMT/`. The fiscal 2024 one
is the filing fact 2 measures. **Read them with `pdfplumber`. Make no API call of any
kind.**

## What to do

1. **Reproduce the refusal first.** Build the Pass 1 answer shape that cites page 45 for
   `units` on the fiscal 2024 filing, run `_unit_statement_failures` against the real PDF,
   and print the failure message. **A fix whose "before" was never seen is a fix for a
   defect nobody has seen.** Quote the message in your entry.
2. **Make the two checks state one rule.** `_unit_statement_pages_allowed` must allow what
   B1 allows: the pages of the figures the statement governs, **and the page before each of
   them**, with the same `page > 1` edge that B1 has at `:1654`. Say in the docstring that
   the rule is B1's, and name B1's line, so a later reader can see the two are meant to
   agree.
3. **Decide `share_units` on purpose and write the reason down.** Its allowed set today is
   `{data["units"]["page"]} | diluted_pages`. Two of those three parts are different kinds
   of thing: `diluted_pages` are **row** pages, where B1's "page before" rule applies, and
   `data["units"]["page"]` is an **already-resolved statement** page, where it may not.
   **State what you chose for each part and why.** A widening you cannot give a reason for
   is one you should not make.
4. **Measure what the widening admits.** For the three filings in `extractions/WMT.json`,
   print the allowed set for `units` and for `share_units`, before and after, as a table.
   Then say, for each page the change adds, **which wrong answer could now use it**. This is
   the payment the trap section asks for.
5. **Prove nothing the checks used to catch now gets through.** Build at least three answers
   that must still be refused and show each one's failure message: a unit statement citing a
   page two before its figures; one citing a page after its figures; and one whose text is
   not printed on the page it cites at all. **If your widening lets any of these through,
   stop and report it rather than narrowing the test.**
6. **No figure may move for the three Walmart filings.** Every one passes today. Prove it:
   the implied share price and the whole stage table identical before and after.
7. **Do not change what the model is asked for.** Fact 4: the Pass 1 schema already asks for
   the page the statement is printed on, and that is right. **A change to the prompt text or
   the schema is an LLM boundary change**, which `AGENTS.md` says to escalate. If you believe
   one is needed, stop, write it under `## Questions for the overall lead`, and do not make
   it.
8. **Record what you find, do not widen your scope.** A defect outside this list goes in your
   entry under "Found". The overall lead puts it in the backlog.

## Files in scope

- `ingestion/claude_extractor.py`

**Nothing else.** A change not traced to the two checks named in fact 1 is a review
finding, even if the change is good.

## Out of scope

- **`tests/`.** The write guard denies it. This unit's tests are a separate assignment
  after the code review.
- **The Pass 1 prompt text and the Pass 1 schema.** Fact 4 and step 7. Escalate, never
  edit.
- **`extractions/WMT.json`.** It is not in git, it is the only real route B file on this
  machine, and it is read by `tests/unit/test_p14d_finance_leases.py:519`. **Read it. Do
  not edit it and do not delete it.** If your fix would make its `filings[0]` entry cite a
  different page, that is a finding for your entry, not an edit.
- **Backlog items 119, 120, 121, 122, 133** in `ingestion/claude_extractor.py`. Each is
  recorded. Item 133 is the two surviving `if target_years:` sites at `:2280` and `:2358`.
- **Backlog item 8**, the blanket `except Exception`. Do not rely on it.
- **The two tests that are red on purpose.** Leave both red.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`. Use `PYTHONIOENCODING=utf-8` for any
command that prints a prompt.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | The refusal is reproduced first | at `HEAD`, a `units` citation of page 45 on the fiscal 2024 filing is refused, and you quote the message | `git archive HEAD` into a scratch directory. **`git stash` is forbidden** |
| 2 | That citation is now accepted | no failure for it | `_unit_statement_failures` against the real PDF |
| 3 | The two checks state one rule | B1's `(page, page - 1)` and the allowed set agree, including the `page > 1` edge | read both, and execute a page-1 case |
| 4 | `share_units` is decided on purpose | your choice for each of its two parts, with the reason | your entry |
| 5 | What the widening admits | a table: the three filings, `units` and `share_units`, allowed set before and after, and the wrong answer each added page could carry | your entry |
| 6 | Nothing that used to be caught gets through | three refusals, each with its message: two pages before, a page after, text not on the page | your probe |
| 7 | No figure moves for the three Walmart filings | the implied share price and every stage figure identical before and after | `cli.py --session-file extractions/WMT.json`, both trees, **in one sitting**: the market call drifts by about ±$0.01 between runs taken minutes apart. Pin `pipeline.fetch_price_data` to remove it |
| 8 | `extractions/WMT.json` is unchanged | sha256 identical before and after every run | print it at both ends |
| 9 | Types | 2 errors in 2 files, or fewer. Name any you removed | the mypy command above |
| 10 | Lint | 4 errors, every one `BLE001`. **Run `ruff check .` after your last edit** | `-m ruff check .` |
| 11 | Census | 64, or fewer. Name any site you removed | the grep at `docs/2-rules/rules.md:102` |
| 12 | Route | 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` |
| 13 | The failing test set | name every test that changed state and why | `-m pytest -q --ignore-glob="*_rule3_red.py"`, before and after, compared **by name** |
| 14 | No paid call was made | state it, and name how you know | no key is set on any command |

**Every criterion is a measurement, never an opinion.** Criterion 5 is the one this unit
turns on: it is the price of the widening, and a widening with no price written down is a
check nobody can judge.

## Citations

- `docs/2-rules/rules.md` — rule 1, and in particular the 2026-10-04 decision on backlog
  item 44 that lets the model return two printed unit statements, each with its page, and
  the sentence "The page check confirms each text on its page." That check is this unit.
- `docs/9-reference/refactor-backlog.md`, item 114.
- `ingestion/claude_extractor.py:1473-1490` — `_unit_statement_pages_allowed`.
- `ingestion/claude_extractor.py:1500-1555` — `_unit_statement_failures` and its messages.
- `ingestion/claude_extractor.py:1654` — B1's `(page, page - 1)` rule.
- `ingestion/claude_extractor.py:223`, `:227` — the Pass 1 schema's `page` field.
- `10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf`, PDF pages 45 and 46 — the
  split income statement of fact 2.
- `.claude/agents/programmer.md` — your role card.

## Known open items

- **Never mutate a file in this repository, not even briefly.** A spot check left a
  `return []` in `ingestion/claude_extractor.py` on 2026-10-05 with a comment saying it had
  been restored. It had not, and a check was dead for about ten hours. **That was this very
  file.** Work in a scratch copy under `C:\tmp` and print the repository file's sha256
  before and after.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- **`extractions/WMT.json` is not in git.** Three filings, five fiscal years, 2022 to 2026,
  balance sheet on `filings[2]`.
- The suite takes about 135 to 225 seconds.
