---
agent: tester
assignment: P9d-tests
round: 2
status: complete
files_touched: [tests/unit/test_session_extraction.py, tests/unit/test_session_extraction_rule3_red.py (deleted)]
verdict: pass
---

# P9d-tests (run 2) — move P9d's green tests out of the red file, lock its other stops

Run 1 (`2026-10-02T1724-tester-p9d-tests.md`) stopped on the usage limit with no
change made. This run started from the committed tree at `255756f`; the loader under
test, `ingestion/session_extraction.py`, is unchanged since `33afced`
(`git diff 33afced HEAD --stat -- ingestion/session_extraction.py` → empty).

## What I did

Moved the three cases of `tests/unit/test_session_extraction_rule3_red.py` into
`tests/unit/test_session_extraction.py`, unchanged in what they assert, and deleted the
red file (`git rm`, so the deletion is **staged**; nothing is committed). Added 18 test
cases locking the Pass 2 shape stops P9d added, which until now only scratch probes had
shown: each of the eight schema keys absent (one parametrised test), `amount` of
`"12"` / `true` / `null` / `inf`, `year` of `2025.5` / `true`, an item that is a string,
`non_recurring_items` absent, `amount` of `0` loading, and one guard test that the
hand-written key list is the schema and the builder writes it. Corrected one comment in
the existing `test_stop_pass2_item_other_key_absent` that P9d made false ("it does not
name the item's year or description"); its assertions are unchanged. No implementation
file was touched.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the red file is gone | **pass** | `ls tests/unit/test_session_extraction_rule3_red.py` → `No such file or directory`. `git status --short` → `D  tests/unit/test_session_extraction_rule3_red.py` |
| 2 | the gate runs the moved tests | **pass** | `.venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` → before **376 passed, 1 failed**; after **397 passed, 1 failed**. +21 = 3 moved + 18 new. Failure set unchanged: `{test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}` |
| 3 | the full suite | **pass** | `.venv/bin/python -m pytest -q` → **397 passed, 4 failed** (before: 379 / 4; total 383 → 401, +18 new). Failure set, identical before and after: `test_capm…no_variation`, `test_dcf_rule3_red…balance_sheet_is_absent`, `test_projector_rule3_red…no_income_statements_stops_and_names_the_input`, `test_routes_session_rule3_red…cache_hit_stops` |
| 4 | at least one new test can fail | **pass** | eight mutants of `session_extraction.py` in copies under `/tmp/p9dt_mut/`, below. Every new test goes red under at least one; the unmutated copy is 145/145 green |
| 5 | lint | **pass** | `.venv/bin/python -m ruff check .` → `Found 5 errors.`, the same five BLE001 sites (`routes_valuation.py:445`, `:703`, `cli.py:1107`, `claude_extractor.py:1051`, `tests/test_e2e_all_googl.py:106`). `ruff check tests/unit/test_session_extraction.py` → `All checks passed!` |

### Criterion 4, pasted

Script `/tmp/p9dt_mut/run.py`: rsync of the working tree (no `.venv`, `.git`,
`10K_filings`, `extractions`) to `/tmp/p9dt_mut/base`, one copy per mutant, the file run
with the repo's `.venv/bin/python` from inside the copy. Counts are of the 145 cases in
`test_session_extraction.py` at the time (before `test_stop_pass2_items_absent` was
added).

```
== M1 amount check removed: 5 failed, 140 passed
   red: test_pass2_item_amount_nan_stops_naming_filing_year_and_description
   red: test_stop_pass2_item_amount_not_a_finite_json_number[string|bool|null|inf]
== M2 year check removed: 2 failed, 143 passed
   red: test_stop_pass2_item_year_not_an_integer[fraction|bool]
== M3 not-an-object check removed: 1 failed, 144 passed
   red: test_stop_pass2_item_not_an_object
== M4 amount 0 refused: 1 failed, 144 passed
   red: test_pass2_item_amount_zero_loads
== M5 description dropped from label: 16 failed, 129 passed
   red: test_stop_pass2_item_key_absent[confidence|source], the moved NaN test,
        missing_a_schema_key[7 of 8, all but description], amount[4], year[2]
== M6 key loop removed: 8 failed, 137 passed
   red: test_stop_pass2_item_missing_a_schema_key[all 8]
== M7 amount check isinstance only (NaN/inf/bool pass): 3 failed, 142 passed
   red: the moved NaN test, amount_not_a_finite_json_number[bool|inf]
== M8 year dropped from label: 13 failed, 132 passed
   red: test_stop_pass2_item_key_absent[confidence|source],
        missing_a_schema_key[7 of 8, all but year], amount[4]
== control (unmutated copy): 145 passed
```

`test_stop_pass2_items_absent`, added after, was not mutated separately; it covers line
531 and the parser catch at 573-574, which were uncovered before it (coverage below).

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The moved tests keep their assertions byte-for-byte; only the two "Today:" comments became "Before P9d:" | Assignment step 1, "unchanged in what they assert". `diff` of the red file's test bodies against the moved ones shows only those two comment lines and blank lines | Strengthening the moved NaN test's vacuous `"2024"` (finding 1) would change what it asserts |
| New tests break item **1** of `one_filing` (`nri(2023, 3.0, "Legal settlement")`), not item 0 | Item 0's year, 2024, is also in the PDF name `TST_10-K_2024.pdf`, so a `"2024"` on the line proves nothing about the item (proved by M8: the moved NaN test stays green when the year is dropped from the label). `"year 2023"` can only come from the item, and index `[1]` is not the `0` of `filings[0]` | Item 0 would have repeated the vacuity |
| Item year spelled `"year 2023"` | The format the existing P9c test `test_stop_pass2_item_key_absent` already asserts (`"year 2023"`), written before P9d from route A's parser message, and the Pass 1 convention in the same file | `"2023"` alone would be weaker; any other spelling would be guessing |
| `test_stop_pass2_item_not_an_object` also asserts `"JSON object"` | Without it, the test passed with the not-an-object check removed (M3 against the weak form → `1 passed`): `"year" in "restructuring"` is a substring test, so the string is reported as eight absent keys under the same index | The same part the `_SHAPE_STOPS` row "filing not an object" asserts |
| Kept `test_stop_pass2_item_key_absent` and `test_stop_pass2_item_other_key_absent`, corrected the stale comment only | They pass, assert true things, and also exercise route A's parser stop if the loader check were removed (M6 leaves them green, which is correct: the parser still stops) | Deleting tests is not in the assignment; the new 8-key test is strictly stronger and the comment now says so |
| Added `test_stop_pass2_items_absent`, not in the assignment's list | Rule 3 and `tester.md`: for every input the unit reads, remove it and assert the raise. P9d's line 531 (`return []` when the key is absent) was the one P9d line no test reached | — |
| Hand-written `PASS2_ITEM_KEYS` checked against `ce._NRI_SCHEMA` and against `nri()` | Mirrors `test_the_required_key_lists_are_the_schema` for Pass 1: a key dropped from the schema or the builder shows as a failure, not as a shorter loop | Reading `_PASS2_ITEM_FIELDS` from the loader would tie the test to the private name F1 of the P9d review plans to replace |

## Rule 3 — what stops, and what does not

Every value P9d's shape check reads, and the test that locks it now.

| Value read | If it were missing or malformed | Evidence |
|---|---|---|
| `pass2.non_recurring_items` absent | stops; names file, `filings[0]`, PDF, `'non_recurring_items'` | `test_stop_pass2_items_absent` |
| `pass2.non_recurring_items` not a list (`{"a":1}`, `"restructuring"`) | stops; names file, `filings[0]`, PDF, `non_recurring_items` | `test_pass2_items_not_a_list_stops_naming_file_and_filing` (moved) |
| an item that is not an object | stops; names file, `filings[0]`, PDF, `non_recurring_items[1]`, `JSON object` | `test_stop_pass2_item_not_an_object` |
| each of the 8 item keys absent | stops; names file, filing, PDF, `non_recurring_items[1]`, `'<key>'`, `absent`, and `year 2023` / `Legal settlement` unless that is the key removed | `test_stop_pass2_item_missing_a_schema_key[8]` |
| `amount` NaN | stops; names file, filing, PDF, `Plant closure` | moved NaN test |
| `amount` `"12"`, `true`, `null`, `inf` | stops; names file, filing, PDF, item index, year, description, `'amount'` | `test_stop_pass2_item_amount_not_a_finite_json_number[4]` |
| `amount` `0` | **loads**, as `0.0`, no validation error. Not a default: the explicit input | `test_pass2_item_amount_zero_loads` |
| `year` `2025.5`, `true` | stops; names file, filing, PDF, item index, description, `'year'` | `test_stop_pass2_item_year_not_an_integer[2]` |
| balance-sheet `year` absent / `0` (P9d's F2 rewrite) | stops, names `balance sheet` and `'year'` | already locked: `test_stop_balance_sheet_planned_without_a_year`, `_SHAPE_STOPS` row "balance sheet year 0" |

No stop path in P9d's lines defaults. **No stop path I could not lock.**

## Measurements

### Before, at `255756f` (macOS, `.venv/bin/python`)

- Gate `pytest -q --ignore-glob="*_rule3_red.py"` → **376 passed, 1 failed**:
  `{test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}`.
- Full `pytest -q` → **379 passed, 4 failed**: `{test_capm…no_variation,
  test_dcf_rule3_red…balance_sheet_is_absent, test_projector_rule3_red…no_income_statements…,
  test_routes_session_rule3_red…cache_hit_stops}`. The 3 cases in
  `test_session_extraction_rule3_red.py` are among the 379 passes, unseen by the gate.
- Ruff `check .` → **5 errors**.

### After (working tree on `255756f`)

- `tests/unit/test_session_extraction.py`: 125 → **146** cases, all pass.
- Gate → **397 passed, 1 failed**, same set. Full → **397 passed, 4 failed**, same set.
- Ruff → **5 errors**, same sites; none in my file.
- Mypy not re-run: no file it checks was touched.

### Coverage — measured, `COVERAGE_FILE=/tmp/p9dt_cov`

`pytest -q tests/unit/test_session_extraction.py --cov=ingestion.session_extraction --cov-branch`,
then `coverage json`, restricted to the lines P9d added or changed
(`git diff -U0 33afced~1 33afced`: 73, 91-96, 475-480, 483, 485-486, 502-561, 563,
568-570):

| Count | Before `test_stop_pass2_items_absent` | After |
|---|---|---|
| functions P9d added or changed (`_pass2_item_label`, `_pass2_shape_problems`, `_pass2_problems`, `_pass1_problems`) | 4 of 4 | **4 of 4** |
| statements in P9d's lines | 37 of 38 (531 missed) | **38 of 38** |
| branch arcs from P9d's lines | 27 of 28 | **28 of 28** |

Whole module from this file alone: 85% (510 statements, 73 missed), the misses all
outside P9d's lines (`text`, `plan` and CLI paths).

## Expected values — testers only

**Accuracy: 43 of 43 checks match**, over 21 test cases (3 moved, 18 new), from 15
assertion statements in source (moved: 2 `pytest.raises` + 2 name checks; new: 3 in
the guard test, 1 each in the five stop tests, 2 in the zero test). Per case: moved
3×2 = 6, guard 3, missing key 8×2 = 16, amount 4×2 = 8, year 2×2 = 4, not-an-object
2, absent list 2, zero 2; total 43. A "check" is one executed assertion: the
`pytest.raises(ValueError)` type check in `stop_message` / the moved tests, each
`assert_one_line_names`, and each plain `assert`.

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| every stop: exception type | `ValueError` | the loader's contract, P9a step 10, restated in P9d's assignment ("collect each problem the way the loader already collects Pass 1 problems") |
| every stop: one line names the file | `str(path.resolve())` | the path the test itself wrote; P9a step 10 |
| every stop: names the filing and PDF | `filings[0]`, `TST_10-K_2024.pdf` | `one_filing` builds one filing at index 0 from `make_pdf(directory, 2024)`; P9d assignment "the filing index, the PDF name" |
| item stops: index | `non_recurring_items[1]` | the test broke item 1; P9d assignment "name the item by its index" |
| item stops: year | `year 2023` | `nri(2023, ...)` in `one_filing`; spelling from the pre-P9d test at `test_stop_pass2_item_key_absent` |
| item stops: description | `Legal settlement` | `nri(..., "Legal settlement")` in `one_filing` |
| key stops: key and word | `'<key>'`, `absent` | the key the test deleted; the Pass 1 key-absent tests' convention in the same file |
| amount / year stops: key | `'amount'`, `'year'` | the key the test set |
| not-an-object | `JSON object` | the `_SHAPE_STOPS` "filing not an object" row's precedent; justified by M3 |
| absent list | `'non_recurring_items'` | the key the test deleted |
| zero loads: items | `[("Plant closure", 12.0), ("Legal settlement", 0.0)]` | hand: `one_filing`'s two items in order, item 0's amount 12.0 as built, item 1's the explicit 0 the test wrote |
| zero loads: no errors | `[]` | hand: `one_filing` reconciles (comment at `_BASE_YEAR`) and the zero touches no Pass 1 figure |
| key list is the schema | the 8 keys in `PASS2_ITEM_KEYS` | written out by reading `_NRI_SCHEMA` at `claude_extractor.py:268-281` (source text, not a run) |
| builder writes all 8; item 1 is (2023, Legal settlement) | `PASS2_ITEM_KEYS`; `(2023, "Legal settlement")` | the `nri()` builder and `one_filing` in the same file |
| moved tests | as in the red file | written by the P9c tester; unchanged |

No expected value was read from the code's output.

## What I did not do

- I did not strengthen the moved NaN test's `"2024"` part (finding 1): the assignment
  says unchanged in what they assert.
- I did not commit. The red file's deletion is staged by `git rm`; the edit to
  `test_session_extraction.py` is unstaged. Nothing outside `tests/` and my entry moved.
- I did not touch `STATUS.md` or `.agent/journal/INDEX.md`.
- No test reaches the API or the network (the file's autouse `_no_api` fixture), and
  nothing read `10K_filings/`.

## Findings for the orchestrator

1. **The moved NaN test's `"2024"` is vacuous.** In
   `test_pass2_item_amount_nan_stops_naming_filing_year_and_description`, the part
   `"2024"` is satisfied by the PDF name `TST_10-K_2024.pdf` on the same line. Proved by
   mutant M8 (year removed from the item label): that test stays green. The year naming
   is now locked by 13 new cases that use item 1 and `"year 2023"`, so nothing is
   unprotected, but a later tester unit could change the part to `"year 2024"`. Severity
   `note`.
2. **`STATUS.md` section 1 moves.** Gate 376/1 → **397 passed, 1 failed**; full suite
   383 → **401 tests, 397 pass, 4 fail** (same set). The trap "3 more pass inside a red
   file and the gate skips them" is closed once this lands. Rule 3 census unchanged (no
   implementation file touched).
3. **`_pass2_problems`'s `except (ValueError, KeyError, TypeError)`
   (`session_extraction.py:571-574`) is now reachable only through an absent
   `non_recurring_items`**: every key the parser reads is checked first. Not a defect;
   it is locked by `test_stop_pass2_items_absent`. If F1's follow-up (a public
   `PASS2_ITEM_FIELDS`) lands, my guard test reads `ce._NRI_SCHEMA`, which stays, so it
   does not break; it could switch to the public name then.
