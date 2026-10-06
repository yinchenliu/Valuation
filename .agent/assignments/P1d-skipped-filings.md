---
id: P1d-skipped-filings
phase: 1 — the gate on the Windows machine (part 4)
agent: tester
depends_on: [P1c-test-network-copies]
---

# A `skipif` guard names a folder no machine uses, so a real-filing test skips on a machine that holds the filing (items 101, 102)

## Objective

**The fact, measured by the overall lead on 2026-10-05.**
`tests/unit/test_p14b_note_figures.py:80` holds

```python
_REAL_WALMART_PDF = Path("10K_filings/Walmart/Walmart Inc._10-K_2026-01-31_English.pdf")
```

`find 10K_filings -name "*.pdf"` gives nine files, under `10K_filings/ABBV/`,
`10K_filings/LHX/` and `10K_filings/WMT/`. One of them is
`10K_filings/WMT/Walmart Inc._10-K_2026-01-31_English.pdf` — **the exact file name the
constant asks for, under the ticker folder instead of the company name.** So
`test_real_walmart_filing_scale_confirmation` skips on a machine that holds the filing.

**What follows.** Check B1 is the rule that stops a run when no printed unit statement
confirms a Pass 1 row's scale. Its only test against a real 10-K has never run here, and
a skipped test reports neither pass nor fail. `pytest -q` prints `5 skipped` and nothing
says that four of them are a path typing error.

**The second constant misses for a different reason.** `_REAL_LHX_PDF`
(`tests/unit/test_p14b_note_figures.py:83`) names
`10K_filings/LHX/L3Harris Technologies Inc._10-K_2026-01-02_English.pdf`. The folder is
right. The file on disk is `L3Harris Technologies Inc._10-K_2025_English.pdf`. **Do not
assume these are the same filing.** L3Harris's fiscal year ends in early January, so a
file named `2025` may or may not be the filing whose fiscal year ends 2026-01-02. Open
the PDF and read its cover page before you decide.

**Two constants are honest misses.** `_REAL_CHIPOTLE_PDF` and `_REAL_OKTA_PDF` name
companies this machine does not hold at all. Those two must keep skipping, and their skip
reason must stay true.

**When this unit is done**, every real-filing test either runs or skips for a reason that
is true on the machine it skips on, and the reason names what it looked for.

## What is already true — verify, do not redo

Measured by the overall lead at `19fe831`, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| gate | `-m pytest -q --ignore-glob="*_rule3_red.py"` | **1137 passed, 5 skipped, 0 failed** |
| full suite | `-m pytest -q` | **2 failed**, 1137 passed, 5 skipped. The 2 are red on purpose |
| the five skips | `-m pytest -q -rs` | `test_p14b_note_figures.py:899` Walmart, `:939` Chipotle, `:963` Okta, `:1007` L3Harris, and `test_p14d_finance_leases.py:519` (`extractions/WMT.json` absent, a true reason) |
| the filings on disk | `find 10K_filings -name "*.pdf"` | **9**, three each under `ABBV/`, `LHX/`, `WMT/` |
| lint | `-m ruff check .` | 4 errors, every one `BLE001` |

**Facts about the code, each read today:**

| Fact | Where |
|---|---|
| Four path constants, one per company | `tests/unit/test_p14b_note_figures.py:80-83` |
| Each guards one test with `@pytest.mark.skipif(not <const>.exists(), reason=...)` | `:898`, `:938`, `:962`, `:1007` |
| The Walmart test's claim: page 21 prints `(Amounts in millions, except per share data)`, so 0 failures; a row citing page 2 gives 1 failure naming page 2 | `:899-905` |
| The L3Harris test's claim: page 62 prints both `(In millions)` and `(In thousands)` | `:1009-1013` |
| A docstring cites `10K_filings/Walmart/` with the same error | `tests/unit/test_p14d_finance_leases.py:22` |
| `tests/unit/test_p15a_two_routes.py:238` passes `10K_filings/Walmart` to the CLI. **This one is harmless**: argparse rejects `-p claude` before any path is read, and the test asserts exit code 2 | read today |

## What to do

1. **Make each guard resolve the filing the way the repository stores it**: under
   `10K_filings/<TICKER>/`. Prefer one small helper that takes a ticker and a file-name
   pattern and returns the path or `None`, over four corrected literals. A literal goes
   stale the next time a filing is added; a helper states the convention once.
2. **Make every skip reason name what it looked for.** "Walmart 10-K PDF not found" does
   not tell a reader which path was tried. After this unit, a reader of
   `pytest -q -rs` can see the pattern that missed.
3. **Read the L3Harris PDF's cover page before you point the constant at it.** State in
   your entry which fiscal year `L3Harris Technologies Inc._10-K_2025_English.pdf`
   covers, and whether page 62 of that file prints both `(In millions)` and
   `(In thousands)`. If it is not the filing the test describes, leave that test skipping
   and say so. **Do not retarget a test at a different document to make it run.**
4. **Run the tests that now run, and report what they do.** If a newly-running test
   fails, **that is a finding about the code or about the test's stated claim, not a
   licence to weaken the test.** Write it in your entry and stop. Do not change what a
   test asserts to make it green.
5. **Fix the two stale citations** that are text only: `tests/unit/test_p14d_finance_leases.py:22`
   names `10K_filings/Walmart/`. Correct it to the folder that exists. Leave
   `tests/unit/test_p15a_two_routes.py:238` alone, or correct the path and say in your
   entry why the test's three assertions do not move.
6. **Item 102, in the same unit because it is the same file family.** The comment at
   `tests/conftest.py:44-48` says two tests hold the `_no_socket` contract in place. There
   are three: `test_no_socket_refuses_an_address_that_leaves_the_machine`,
   `test_no_socket_refuses_an_address_it_cannot_read` and
   `test_no_socket_allows_the_loopback_address`. Add the second fact the next reader
   needs: **the loopback test cannot detect a fixture turned into a no-op**, because a
   loopback connection succeeds with no patch at all. The two refusal tests are what hold
   the contract. Text only. Change no behaviour in `tests/conftest.py`.
7. **Record what you find, do not widen your scope.**

## Files in scope

- `tests/unit/test_p14b_note_figures.py`
- `tests/unit/test_p14d_finance_leases.py` (step 5 only: the docstring citation)
- `tests/unit/test_p15a_two_routes.py` (step 5 only, and only if you can show the three
  assertions do not move)
- `tests/conftest.py` (step 6 only: the comment)
- A new helper module under `tests/unit/`, if step 1 needs one. Name it for what it does.

**Nothing else.** The write guard denies every path outside `tests/`.

## Out of scope

- **Every implementation file.** If a newly-running test shows a defect in
  `ingestion/claude_extractor.py` or anywhere else, that is a finding. Write it and stop.
- **Adding a filing to `10K_filings/`.** Chipotle and Okta are not on this machine and
  this unit does not put them here. Those two tests keep skipping.
- **Items 91 and 40**, the seven dev scripts that run their own valuation sequence.
- **Items 94 to 100.** Each is recorded in the backlog.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | The Walmart real-filing test runs | it is not in the skip list, and it passes or you report why it does not | `-m pytest -q -rs tests/unit/test_p14b_note_figures.py` |
| 2 | The skip list is honest | every remaining skip names a file this machine does not hold, and the reason names the pattern tried | the same command, and `find 10K_filings -name "*.pdf"` beside it |
| 3 | The L3Harris question is answered by reading the PDF | your entry states the fiscal year on the cover page and what page 62 prints | `pdfplumber`, in a `-c` command; quote the text |
| 4 | No literal company-name folder survives in `tests/` | no match, or each match explained | `grep -rn "10K_filings/Walmart\|10K_filings/Chipotle\|10K_filings/Okta" tests/` |
| 5 | The gate is green | **0 failed**, and no new failing name | `-m pytest -q --ignore-glob="*_rule3_red.py"` |
| 6 | The full suite shows only the two deliberate failures | 2 failed | `-m pytest -q` |
| 7 | A newly-running test is a real measurement | revert check B1's stop in a scratch copy and show the Walmart test goes red | the mutation, in a scratch copy; restore and prove it byte-identical |
| 8 | Item 102's comment is correct | the comment names three tests and states that the loopback test cannot detect a no-op | `git diff tests/conftest.py`, and the three names run green |
| 9 | Lint | 4 errors, every one `BLE001`, and your changed files lint clean | `-m ruff check .` |
| 10 | Nothing outside `tests/` changed | every path starts with `tests/` | `git status --porcelain` |

**Every criterion is a measurement, never an opinion.** Criterion 5 is a set comparison,
not a count: save the failing names before and after.

## Citations

- `.claude/agents/tester.md` — your role card, and the trap it opens with.
- `docs/9-reference/refactor-backlog.md`, items 101 and 102 — the two defects.
- `docs/2-rules/rules.md`, rule 1 option B and check B1 — what the Walmart test proves.
- `.agent/assignments/P1c-test-network-copies.md`, "Overall lead review" — how item 101
  was found.

## Known open items

- Backlog item 75: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- Backlog item 98: `runpy.run_path` executes a module into a fresh namespace, so a patch
  on that module object is not the name the fresh copy binds. Do not introduce one.
- Backlog item 100: a filing citation must give the printed page and the PDF index. The
  tests in this file cite PDF page indexes. Say which you mean wherever you write one.
- The suite takes about 135 seconds. Measure once, not after every edit.
