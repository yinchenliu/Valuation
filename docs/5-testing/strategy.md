# How this repository is tested

**Open this before writing a test, or judging one.**

---

## 1. Where the expected value comes from

This repository has **no benchmark**. No trustee, no signed reference file, no published
figure to tie against. That is a deliberate decision, recorded 2026-09-20.

It removes the safest source of an expected value and leaves one trap wide open:

> **Running the code, reading what it printed, and writing that into an assertion.**

A test written that way passes forever and verifies nothing. It does not test the
formula; it photographs the current behaviour, **including the bug**. It goes green on
the day someone breaks the thing it was written to protect, because it was never
independent of it.

**So the expected side of every assertion must exist before the code runs.** Four
sources are acceptable, in this order:

| Source | How | Use it for |
|---|---|---|
| **Hand arithmetic** | inputs whose answer you can compute on paper, with the arithmetic written into the test as a comment | every formula in `analysis/` |
| **Closed-form identity** | a mathematical property that holds whatever the inputs | discounting, weighting, aggregation, two entry points that must agree |
| **A figure read off a filing page** | open the PDF, read the printed number, cite the page | extraction tests only |
| **A stated requirement** | a phrase, a field name or a behaviour that the assignment or a document states, cited by `file:line` | messages, labels, which field a stop names |

**Never** the code's own output. **Never** a cached `.pkl`. **Never** a number another
test already asserts. **Never the code's own literal**: an expected message copied from
the f-string that produces it tests nothing, because it changes when the code changes.
If the requirement says only "the stop names the field", assert the field name, not the
whole formatted line.

**Label each source truthfully.** A phrase is not a closed-form identity. A label that
names the wrong source hides where the expectation really came from, and a reviewer
cannot check it. Measured in the worktree pilot, 2026-10-08: one tester entry labelled
assignment phrases "closed-form identity", and another cited the code's own f-string as
"hand derivation".

### Every test calls the code it is about

A test that calls no production code cannot fail. It passes whatever the code does, so it
adds a green line and no protection. **Measured, 2026-10-08**:
`test_mutation_probe_simulating_raw_years_alone_omits_adjusted_only_year` asserts facts
about Python sets, calls neither entry point, and passes under the very mutation the
other six tests in its file catch (backlog item 148).

**A mutation result is measured and reported, never encoded as a test.** Section 5b
holds the procedure.

### Every test holds on both machines

This repository runs on macOS (Python 3.11.6) and Windows (Python 3.14.4)
([../8-build/environment.md](../8-build/environment.md)). **A test asserts what the code
does, never how the interpreter, a library or the platform behaves.** Measured,
2026-10-08: three tests asserted that `repr()` of a `TextIOWrapper` subclass hides the
subclass. That holds on 3.11 and 3.12 and is false on 3.13 and later, so the tests were
green on macOS and red on Windows against correct code (`P1h-mac-gate`, round 1).

**Do not hide a difference with `skipif` on the Python version.** Write the assertion so
it holds on both: in that case, assert the text the code adds, not the text the
interpreter leaves out.

### Choose inputs that make the arithmetic obvious

Do not test `calculate_terminal_value` with real GOOGL figures. You cannot check that by
hand, so you will end up pasting what the code said.

```python
# TV = FCFF_n * (1 + g) / (WACC - g) = 100 * 1.02 / 0.08 = 1275.0
assert calculate_terminal_value(100.0, 0.02, 0.10) == pytest.approx(1275.0)
```

Round numbers are not a weaker test. They are the only kind anyone can independently
check.

### Identities worth using here

| Identity | Why it holds |
|---|---|
| `WACC` with `debt_weight = 0` equals cost of equity | the debt term vanishes |
| `WACC` with `tax_rate = 0` equals the plain weighted average | the shield vanishes |
| a DCF with `g = 0` and constant `FCFF` → `FCFF / WACC` as n → ∞ | perpetuity |
| `NOPAT` with `tax_rate = 0` equals `EBIT` | |
| an `IncomeStatement` with no non-recurring items normalises to itself | `normalize_financials` returns early |
| `beta` of a series regressed on itself is exactly 1.0 | OLS on identical series |

That last one is the cheapest real test of `calculate_beta`, and it needs no market
data.

## 2. Lock the stop, not only the value

A correct value proves the happy path. It proves nothing about the absent case, and
[rule 3](../2-rules/rules.md) is entirely about the absent case.

For every input a function reads, write a second test: **remove the input, assert the
raise.**

- Assert the **exception type**.
- Assert the **message names the missing field**.

```python
with pytest.raises(MissingFigureError, match="net_debt"):
    run_dcf(..., financials=financials_without_balance_sheet, ...)
```

`pytest.raises(Exception)` alone passes against a bare `raise` and tells the next reader
nothing.

### Never assert a fallback

A test locking `net_debt == 0.0` when the balance sheet is missing makes
[backlog item 2](../9-reference/refactor-backlog.md) **permanent** and turns its fix
red.

**If you are about to assert a default, you have found a finding.** Report it; do not
encode it.

**This is not only about money.** Any assertion of what a function returns, rather than
raises, when an input is `None`, empty or missing locks that fallback in: `== 0.0`,
`== []`, `== {}`, `== ""`, `is None`. Measured, 2026-10-08:
`test_build_ebit_reconciliation_handles_none_inputs` asserts that `None` statements give
`[]`, a branch neither caller reaches (backlog item 149). Before you finish, search your
own test file and justify every hit in your entry. On `tests/unit/test_p3e_reconciliation_years.py`
this search finds the three assertions of item 149 at lines 498 to 500:

```bash
grep -nE '^\s*assert .*(== *(0(\.0)?\b|\[\]|\{\}|"")|is None\b)' tests/unit/<your file>
```

A hit is a fallback only when the input is absent. `assert record.adjusted_ebit is None`
for a year with no adjusted statement is the stated requirement, not a fallback, if the
assignment or the code's rule 3 contract says so. Say which, with the citation.

## 3. No network, no keys

A unit test must not need an API key, a PDF, or the internet.

- `yfinance` and the model clients are **boundaries**. Fake them.
- Build `FinancialStatements` in the test, by hand, with the few fields the function
  under test reads.
- Extraction tests use a **committed sample response**, not a live call.

A test that needs a key is not a test, it is a script. The distinction is not pedantry:
a suite that costs money to run is a suite nobody runs.

## 4. What `tests/` holds

Re-measured at `6cf34d3`:

| Measurement | `bc19431` | `6cf34d3` |
|---|---|---|
| `.py` files | 10 | **20** |
| `assert` statements | **0** | **483** |
| scripts guarded by `if __name__ == "__main__":` | **0** | **9 of 9** |
| tests collected | 0 | **146** |
| `pytest -q` | 3 collection errors | 145 pass, 1 red on purpose, 11 s |

The nine scripts now wrap their module body in `def main()` behind a guard, so
`pytest` no longer runs an LLM call, a network fetch or a DCF at import. **They were
kept, not deleted** — `tests/compare_models.py` compares provider output and
`tests/test_e2e_*.py` exercise real filings end to end.

**They are still not evidence of correctness**, and no report may cite them as such.

**Two things to know before you run one.**

1. Every script carries a `sys.path.insert` to a path belonging to a different Windows
   user, so `python tests/<name>.py` fails with `ModuleNotFoundError`. Use
   `.venv/Scripts/python.exe -m tests.<name>` until
   [backlog item 16](../9-reference/refactor-backlog.md) lands.
2. A file named `tests/unit/test_<module>_rule3_red.py` **fails on purpose.** It states
   a requirement the code does not yet meet, and the gate
   `pytest -q --ignore-glob="*_rule3_red.py"` skips it. At `P10-tests` two remain:
   `test_projector_rule3_red.py` and `test_routes_session_rule3_red.py` (backlog item
   52). `STATUS.md` section 1 lists them. Any other failure is a real regression.

   The first one, `test_dcf_rule3_red.py`, went green when `P10a-nci-bridge` closed
   backlog item 2, and `P10-tests` moved its test into `test_dcf.py` the same day.

   **The gate keys on the pattern, not on a filename.** An earlier revision named one
   file by path and went stale the moment a second red test landed. And when a red test
   goes green, **move it out of the pattern in the same unit** — otherwise the gate stops
   running the very test that proves the fix.

### Where the gap is now · re-measured at `6cf34d3`

```
analysis/   255 of 255 statements, 80 of 80 branches   100%
api/        118 of 126 statements                       94%
ingestion/  no tests at all
models/     exercised only through analysis/ and api/
```

**An earlier revision of this section said "the other five modules are at 0%".** That
was true at `d1854fb` and false from `796de9a` onward. It is corrected here because a
testing document that misstates the suite is worse than one that says nothing.

`analysis/` is finished. **`ingestion/` is the gap**: no test touches it, it holds 49 of
the 116 zero-default sites, and it is where the extraction boundary sits — the one place
where a figure enters this repository from outside.

**The eight uncovered arcs in `api/` are uncovered on purpose.** Each is a fallback or a
recorded backlog item a tester refused to pin, because a test asserting a known defect
makes its fix turn red. See the cache-hit branch, the yfinance share-count fallback and
the legacy `file_path` branch.

## 5. Two counts, never one

| Count | Question | Unit |
|---|---|---|
| **Sources** | of the assertions written, how many come from each of the four sources in section 1? | assertions, per source |
| **Coverage** | of the functions and branches the unit added or changed, how many does any test touch? | statements, then branches |

**Do not report "accuracy: N of N".** A suite that passes always reports 100%, so the
figure shows nothing. The count per source shows where the expectations came from, and a
reviewer can check that.

A function no test calls cannot fail, so a coverage gap reads as a clean report — and
the cleaner it reads, the worse it is. **State the unit of every count.** "12 passed" is
not a measurement until you say 12 of what, out of how many.

Measure coverage over **the files in scope**, not a fixed list of packages, and paste the
line of output for each file into the entry:

```bash
.venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/<your file> \
    --cov=<module> --cov-branch --cov-report=term-missing
# for example --cov=cli, or --cov=ingestion.session_extraction
```

**A coverage figure with no command beside it is not a measurement.** Measured,
2026-10-08: a tester entry claimed "27 of 27 statements" with no command, and the command
this file printed until then could not measure `cli.py` at all.

## 5b. A mutation: how to run one

Every assignment asks for one. It shows that a test fails when the code is wrong, which a
passing run cannot show.

1. Make a scratch worktree **outside the repository**, at the commit under test:
   `git worktree add --detach /tmp/<unit>-mutant HEAD`. Link the venv:
   `ln -s <repository>/.venv /tmp/<unit>-mutant/.venv`.
2. In the scratch worktree only, change **one** line: the mutation the assignment names.
3. Run the named tests there. Record the result: `N failed, M passed`.
4. Restore the line (`git checkout -- <file>`) and run the same tests. Record the result.
5. Remove the scratch worktree: `git worktree remove --force /tmp/<unit>-mutant`, then
   `git worktree prune`.
6. In the entry, give the mutation, both results, the commands, and the names of the tests
   that went red.

**Never edit the real working tree to run a mutation**, and never encode the mutation as
a test (section 1).

## 6. Where to start · re-measured at `6cf34d3`

The original list here ordered the six `analysis/` modules. **All six are done**, at 255
of 255 statements and 80 of 80 branches. The order below replaces it.

1. **`ingestion/`.** No test touches it. It holds 49 of the 116 zero-default sites and
   the whole extraction boundary — the one place a figure enters this repository from
   outside. Use a **committed sample response**, never a live call; a suite that costs
   money to run is a suite nobody runs.
2. **The `api/` arcs that are not deliberate.** Eight are uncovered; each is currently a
   fallback a tester refused to pin. When a backlog item closes, its arc becomes
   testable — cover it then, in the same unit.
3. **`models/`.** Exercised only through `analysis/` and `api/` today. Its properties
   carry the arithmetic that four testers have leaned on without testing directly.

Three habits this suite established, worth keeping:

- **Prove the test can fail.** Mutate the line under test in a copy under `c:/tmp/` and
  report how many assertions go red. Zero is a finding about your test.
- **Restore what you removed.** When you repair a fixture, give the removed input back
  and confirm every assertion fails again. An assertion that stays green went vacuous.
- **Do not take a claim you can run.** Three reviewers overturned a claim they had been
  handed, in each case by executing it rather than reading it.

A red test that states a true requirement is doing its job. Do not weaken it.
