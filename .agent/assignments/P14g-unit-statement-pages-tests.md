---
id: P14g-unit-statement-pages-tests
phase: 14 — extraction correctness (part 7)
agent: tester
depends_on: [P14g-unit-statement-pages]
---

# Tests for `P14g-unit-statement-pages`: the two unit-scale checks state one rule, and the page before a statement's figures is allowed

## Objective

`P14g-unit-statement-pages` is written and its code reviewer approved it at round 1. It
closes backlog item 114.

**The fact that forced the unit.** Two checks in `ingestion/claude_extractor.py` decided
where a printed unit statement may sit, and they disagreed. Check B1
(`_row_scale_failures`) allowed the row's page **and the page before it**.
`_unit_statement_pages_allowed` allowed only the pages a printed line cites. Walmart's
fiscal 2024 10-K prints its income statement title, `(Amounts in millions, except per share
data)` and the year header as the last four text lines of PDF page 45, and **every data row
on page 46**. So a model citing page 45 had read the filing correctly and the run stopped.

**What the unit did.** One new pure function, `_pages_and_page_before`, holds B1's rule
once. `_unit_statement_pages_allowed` and both of B1's page lines read it. No prompt byte
and no schema byte moved, confirmed by hashing `inspect.getsource` of all sixteen prompt and
schema objects in both trees.

**Two tests are red in the working tree and both assert the old rule.** You repair them.
Neither reports wrong new code. The reviewer diagnosed each by line and the diagnosis is in
"What is already true" below.

## The trap this repository puts in front of you, stated first

**There is no benchmark in this repository.** No trustee file, no signed reference, no
published figure. So the only thing that makes your expected values worth anything is that
you computed them **before** the code ran, from the filing or from the formula.

**Running the code, reading the output and asserting that is the one failure mode that
passes forever.** `.claude/agents/tester.md` spends its first section on it. Read that
section before you write a line.

## The second trap, and it is specific to this unit

**This unit leaves a known hole open, on purpose and on the record. Do not write a test
that asserts the hole.**

The hole: a model may cite the unit statement of **another** table printed on the page
before the figures. Measured by the programmer and rebuilt independently by the reviewer: a
two-page PDF, page 1 a note headed `(in thousands)`, page 2 the income statement headed
`(in millions)` with every figure. That answer is refused at `HEAD` and **accepted** after
this unit, and every money figure would then be divided by 1,000.

**The reviewer found the fact that makes shipping it right, and you need it too**: the same
wrong answer with the note on the **same** page as the figures is accepted at `HEAD` as
well. So this unit widens an existing window from one page to two. It does not open one.

**What that means for you.** A test that asserts `len(failures) == 0` for that wrong answer
would lock the hole as correct behaviour, and the unit that finally closes it would turn
your test red. That is the same mistake the `P3d-invisible-year` tester refused to make with
two margin cells, and it refused for this reason. **If you want the behaviour recorded,
record it in your entry, not in an assertion.**

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-07, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`, on
the working tree that holds this unit:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1257 tests, 2 failed**, and the two are named below |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |
| types | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` | 2 errors in 2 files, 21 checked |
| census | the grep at `docs/2-rules/rules.md:102` | 64 |
| route | `TestClient(app.app, raise_server_exceptions=False).get('/')` | 200 |
| guard | `.claude/check_guard.py` | 48/48 |

**If one of these disagrees when you run it, stop and report the disagreement.** Do not
edit anything to make it agree.

**The two red tests, diagnosed by the code reviewer line by line on 2026-10-07.** Confirm
each diagnosis yourself before you act on it:

| Test | Line | Why it is red | What must not change |
|---|---|---|---|
| `tests/unit/test_p14a_units.py::test_unit_statement_pages_allowed_constrains_pages` | `:289` | `assert allowed["units"] == {29, 30}` fails as `{28, 29, 30} == {29, 30}`. **Page 28 is the page before income page 29, which is the unit's whole purpose** | **`:291`, `allowed["share_units"] == {29, 30}`, is still true.** Leave it. It is what locks the unit's `share_units` decision |
| `tests/unit/test_p14a_units.py::test_unit_statement_failures_stops_when_page_outside_allowed` | `:340` | `assert "the pages allowed are [29]" in msg`; the list is now `[28, 29]` | **`:336`, `:338` and `:339` all still pass.** The refusal of a stock-award page six pages away still stands |

**Repair them. Do not delete either.** A test deleted is a rule nobody checks.

**There is no test-order guard on this machine.** `pytest-randomly` is not installed, so
every run uses one fixed order. That gap is backlog item 127 and it is not yours. **Do not
add `-p no:randomly` to any command**: it was deleted from every live document on the user's
decision of 2026-10-07 because it asserted nothing. **Compare two runs by the set of failing
test names, never by count.**

**Read these two entries before you start.** They hold the probe shapes already built, so
you do not rediscover them:

- `.agent/journal/2026-10-07T1556-programmer-p14g-unit-statement-pages.md`
- `.agent/journal/2026-10-07T1642-code_reviewer-p14g-unit-statement-pages.md`, whose 2x2
  table prices two narrower rules that **do not work**, so nobody re-proposes them.

## What to do

1. **Repair the two red tests** to the new rule, per the table above. Derive each expected
   set and each expected string from the rule, not from what the code now prints.
2. **Test `_pages_and_page_before` directly.** It is pure, with no PDF and no I/O. Cover the
   page-1 edge, the empty set, and that page 0 is never produced.
3. **Test that the two checks really read one rule.** The unit's whole objective is that
   they agree. Write the test that fails if a later edit gives either check its own rule
   again.
4. **Test the real Walmart fiscal 2024 case end to end**, against the PDF on this machine.
   A `units` citation of page 45 is accepted, and the figure pages are unchanged. This is
   the case the unit exists for, so it needs a guard that uses the real filing.
5. **Test that the newly-allowed page is still checked, not merely allowed.** The reviewer's
   sharpest measurement: `(Amounts in millions)` cited on page 45 is **still refused**,
   because that text is not printed there. A widening that stopped checking the text would
   pass criterion 2 and be worthless.
6. **Test the refusals that must survive.** At least: a page two before the figures, a page
   after the figures, and text not printed on the cited page at all.
7. **Mutate your own tests and record what each mutation kills.** At least these four, each
   in its own scratch tree, never in the repository:
   - `_pages_and_page_before` returning `pages` unchanged, which is the old defect.
   - It returning `pages | {p - 1 for p in pages}` with no `p > 1` guard, so page 0 appears.
   - It returning `pages | {p + 1 for p in pages}`, the page after instead of before.
   - `_unit_statement_failures` skipping the "printed on its page" check once the page is
     allowed.
   **A mutation your suite survives is a hole, and you report it rather than hide it.**
8. **Count what you covered, do not estimate it.** Intersect a `--cov-branch` report with
   the added line numbers from `git diff -U0`. Report statements covered and statements
   missed as counts, with the command.

## Files in scope

- `tests/` only.

**Nothing else.** The write guard denies the rest, and a tester that may edit the code it
judges is not a tester.

## Out of scope

- **`ingestion/claude_extractor.py`.** If you believe the implementation is wrong, say so in
  your entry and return `fail`. Do not fix it.
- **The known hole.** Second trap section. Record it in your entry. Do not assert it.
- **`extractions/WMT.json`.** It is not in git and it is the only real route B file on this
  machine. **Read it. Do not edit it and do not delete it.** Its `filings[0]` cites the
  Comprehensive Income header rather than the income statement's own, which this unit makes
  citable for the first time. That is recorded and it is not yours to correct.
- **The two tests that are red on purpose**, `test_projector_rule3_red.py` and
  `test_routes_session_rule3_red.py`. Leave both red. They are different from the two you
  repair.
- **Backlog item 127**, the absent test-order guard.
- **Make no LLM API call of any kind.** Read every PDF with `pdfplumber`.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | Every expected value is hand-sourced | a count of assertions, and how many came from the code's output | **the second number must be 0.** State both |
| 2 | The two red tests are repaired, not deleted | both green, and `:291`, `:336`, `:338`, `:339` unchanged | `git diff` on `tests/unit/test_p14a_units.py` |
| 3 | `_pages_and_page_before` is covered | page 1, the empty set, and that page 0 never appears | your tests |
| 4 | The two checks are proved to read one rule | a test that fails if either gets its own rule back | your tests |
| 5 | The real Walmart fiscal 2024 case | page 45 accepted, against the PDF on this machine | your tests |
| 6 | The new page is still checked | a text not printed on page 45 and cited there is refused | your tests |
| 7 | The surviving refusals | three, each with the reason it is refused | your tests |
| 8 | Four mutations, each killed | for each: the mutation, the command, the failing count and the **names** of the tests that went red | your own scratch trees. **Report any mutation your suite survives** |
| 9 | Coverage of what the unit added | statements covered and statements missed, as counts | `--cov-branch` intersected with `git diff -U0`. Not an estimate |
| 10 | The gate | **1257 passed plus your new tests, 2 skipped, 0 failed** | `-m pytest -q --ignore-glob="*_rule3_red.py"` |
| 11 | The failing set | empty, compared **by name** | the gate form |
| 12 | Lint | 4 errors, every one `BLE001`. **Run `ruff check .` after your last edit** | `-m ruff check .` |
| 13 | The write guard | 48/48 | `.claude/check_guard.py` |
| 14 | No LLM call was made | state it, and name how you know | no key is set on any command |

**Criterion 12 has its own history.** `P3c-one-number-tests` reported lint as "4 `BLE001`"
and, beside it, "`All checks passed!` over my five files". Both cannot be true. The
acceptance re-run found a fifth error, `C402`, in a file that tester had written: it ran
ruff over its own files, then added two more tests, and never re-ran lint. The
`P3d-invisible-year` tester nearly repeated it and caught a `B018` in its own file.
**Run lint after your last write, not beside the edit that prompted it.**

## Citations

- `.claude/agents/tester.md` — your role card. Its first section is the first trap above.
- `docs/2-rules/rules.md` — rule 1, and the 2026-10-04 decision on item 44 that lets the
  model return two printed unit statements, each with its page, and the sentence "The page
  check confirms each text on its page." That check is this unit.
- `docs/9-reference/refactor-backlog.md`, item 114.
- `.agent/assignments/P14g-unit-statement-pages.md` — the unit and its fourteen criteria.
- `ingestion/claude_extractor.py` — `_pages_and_page_before`, `_unit_statement_pages_allowed`,
  `_unit_statement_failures`, `_row_scale_failures`.
- `10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf`, PDF pages 45 and 46 — the
  split income statement.

## Known open items

- **Never mutate a file in this repository, not even briefly.** A spot check left a
  `return []` in `ingestion/claude_extractor.py` on 2026-10-05 with a comment saying it had
  been restored. It had not, and a check was dead for about ten hours. **That was the very
  file this unit changed.** Work in a scratch copy under `C:\tmp` and print the repository
  file's sha256 before and after. `git stash` is forbidden.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- `tests/unit/_text_pdf.write_text_pdf` already exists and writes a text PDF. The programmer
  used it to build the two-page probe.
- The suite takes about 135 to 225 seconds.
