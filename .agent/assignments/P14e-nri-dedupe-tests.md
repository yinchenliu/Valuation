---
id: P14e-nri-dedupe-tests
phase: 14 — the Pass 1 and Pass 2 roles
agent: tester
depends_on: [P14e-nri-dedupe]
---

# Lock the two keys, and repair the two tests that assert the old one (item 112)

## Objective

`P14e-nri-dedupe` is the unit that stops a non-recurring item being dropped in silence.
You are its tester. **Its code is not committed.** One file changed:
`ingestion/claude_extractor.py`.

**Fact 1, the defect it closes.** `merge_filing_extractions` deduplicated items on
`(year, amount, direction)` with no `else` branch, so an item whose key was already
present was discarded and nothing reported it. Walmart's fiscal 2024 10-K prints two
different incremental divestiture losses for fiscal 2022, each `$0.2 billion`: Asda on PDF
page 66 and Seiyu on page 67. Both are `add_back`, both are 2022. **14 items written, 13
merged. 200 $M of add-back lost, in silence.**

**Fact 2, what it costs.** Measured by the programmer and re-run by the round 1 code
reviewer, and **not** what the first version of the programmer assignment said. The fiscal
2022 operating margin does not move: all four Walmart fiscal 2022 items carry
`line_item: "other_non_operating"`, which the normalizer applies **below** EBIT, so
`operating_margin` is `0.045293441861602016` and `ebit` is `25942.0` with the item and
without it. What moves is the fiscal 2022 **effective tax rate**: `ebt` goes `23706.0 →
23906.0`, exactly 200 apart, against an unchanged `tax_expense` of `4756.0`, so the rate
goes `0.20062431451953092 → 0.19894587132937339` and the derived `tax_rate` assumption
`23.147309% → 23.113740%`. That reaches NOPAT in all five projected years and the terminal
value.

**Fact 3, the shape of the fix.** There are now **two** keys.

| Key | Fields | Governs |
|---|---|---|
| `nri_identity` | `(year, amount, direction, description)` | **across** filings |
| `nri_identity_within_filing` | `(year, amount, direction, description, page)` | **one** filing's own answer |

`page` is out of the across-filing key because a full `source` carries one PDF's page
number, and the same disclosure moves: the round 1 reviewer confirmed from the file that
one Walmart note is `page 52` in the FY2024 10-K and `page 51` in the FY2025. A key holding
`page` could never match across filings, so every overlapping item would be double-counted.
**Inside one PDF the opposite holds**: `page` is exactly what separates Asda on page 66 from
Seiyu on page 67.

**Fact 4, and it decides how you build every test in this unit.** The programmer proved by
mutation that **`extractions/WMT.json` catches neither mutant**. Removing `page` from the
within-filing key turns a 2-item case into 1. Adding `page` to the across-filing key turns
a 1-item case into 2. **Both mutants still give `MERGED 14` with Asda and Seiyu present.**
So the real file cannot see the boundary this unit draws. **A test suite built on it alone
would be green against both mutations.**

**What follows.** When this unit is done, each of the two keys is held by a hand-built test
that goes red when that key loses or gains `page`, both drop messages are held by a test,
the two red tests assert the new behaviour instead of the old, and the failing set is empty.

## The trap this unit is most likely to fall into

**Read the first section of `.claude/agents/tester.md` before you write a line.** There is
no benchmark in this repository. The cheapest way to write any test here is to run the
code, read what it printed, and assert that. **A test written that way verifies nothing and
passes forever.**

Three traps have already caught work in this repository, and the third is this unit's:

1. `P3b`'s first CLI stop test ran `cli.py` through `runpy.run_path`, which executes the
   file into a fresh namespace, so a patch on the `cli` module was never the name that
   namespace bound and the assertion **could not fail** (backlog item 98). A patch on a
   module that `cli` imports **from** still holds.
2. `P1d`'s `test_real_lhx_filing_multi_scale_limit` asserted "no failures" twice and
   nothing else, so it passed with the check it tested replaced by `return []`. **Any test
   whose only assertion is "no failures" is green against a deleted check.**
3. **Fact 4 above.** The real Walmart file is green against both of this unit's mutations.
   A test that merges `extractions/WMT.json` and asserts 14 items proves that the defect is
   closed and proves **nothing** about either key.

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-06, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| gate at `HEAD` (`5291710`), before the unit | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly` | **1175 passed, 2 skipped, 0 failed** |
| the unit's diff | `git diff --stat` | one file, **191 insertions, 7 deletions** |
| `ingestion/claude_extractor.py` | sha256 | **171,384 bytes, `b459e4ee…`** |
| `extractions/WMT.json` | sha256 | **36,626 bytes, `c436e427…`**, unchanged through both rounds |

**Take your own baseline before you write anything, and compare failing sets by name,
never by count.**

## The two red tests, by name

Both build their "repeat" with a **different** description, which is not what a re-report
looks like, so **neither can pass under any correct new key.**

| File | Test | What it asserts today |
|---|---|---|
| `tests/unit/test_claude_extractor.py:590-603` | `test_merge_keeps_one_item_per_year_amount_direction` | its own comment names the old key: `# Key (year, amount, direction), first seen kept`. Its "duplicate" carries `"same item, seen again in the 2024 10-K"` |
| `tests/unit/test_session_extraction.py:249` | `test_three_filings_both_routes_give_equal_statements_and_items` | its repeat is `dict(item_a, description="A, read again")`. Its route-equality assertions `route_b.financials == fin_a` and `route_b.non_recurring == items_a` **still pass**; only the hand-written description list at `:361` fails |

**Re-express both fixtures with the same printed description.** A filing that re-reports an
item copies the printed line, so the description is the same text. Do not delete either
test and do not weaken an assertion to make it pass.

## What to do

1. **Repair the two red tests**, as above. Rename either one whose name states the old key.
2. **Lock the across-filing key.** The same item, same text, reported by two filings is one
   item. By three filings, one item with two drops reported. Build these by hand.
3. **Lock the within-filing key.** The identical row twice in one filing, same page, is one
   item and the drop is reported. Two rows alike in every field **but** the page are two
   items with no drop. Asda and Seiyu, which differ in description **and** page, are two
   items.
4. **Make each key's `page` load-bearing, by mutation.** Your tests must go red when `page`
   is removed from the within-filing key, and red when `page` is added to the across-filing
   key. **Mutate a scratch copy only.** Print the repository file's sha256 before and after.
5. **Lock both drop messages.** A cross-filing drop and a within-filing drop each name the
   year, amount, direction, description, filing and page of the item kept **and** the item
   dropped. Assert the fields, not the whole sentence: a test that pins every character
   makes a reword a failure.
6. **Lock that a drop does not stop the run.** The merge returns and the valuation
   continues. Two filings re-reporting one item is normal.
7. **Lock the compound case the round 2 programmer found.** An earlier filing already
   reported the item **and** this filing writes its row twice. Every `kept:` line must name
   an item that is really in the merged list.
8. **Test both routes.** The merge is the one function route A and route B share. Use the
   real route B loader for at least one case, and `extract_multi_year` stubbed for at least
   one. **Make no network call and no model call.**
9. **Record what you find, do not widen your scope.** A defect outside this list goes in
   your entry under "Found".

## Files in scope

- `tests/` — any file under it.

**Nothing else.** The write guard denies everything else to you.

## Out of scope

- **`ingestion/claude_extractor.py`.** It is the unit's code and it is reviewed. If you
  believe it is wrong, **that is a finding: write it and stop.** Do not edit it.
- **Backlog item 119**, the differently-worded cross-filing re-report that is counted
  twice. Left open on purpose: deciding that two texts mean one charge is a judgement rule 1
  gives to the model, not to Python. **Do not write a test that asserts it is wrong**, and
  do not write one that asserts it is right. One test may record it as the measured
  behaviour, named as item 119.
- **Backlog item 62**, a drop that reaches the server console and not the web page.
- **The two tests that are red on purpose**, `tests/unit/test_projector_rule3_red.py` and
  `tests/unit/test_routes_session_rule3_red.py`. Leave both red. If one goes green, move it
  out of the `*_rule3_red.py` pattern in this unit.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`. Add `-p no:randomly` when you compare
two runs. Use `PYTHONIOENCODING=utf-8` for any command that prints a prompt.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | Your own baseline, before you write anything | the failing set, by name | the gate command, names captured to a file |
| 2 | The failing set is empty when you finish | `{}` | the same command, sets compared by name |
| 3 | The full suite shows only the two deliberate failures | exactly those two names | `-m pytest -q -p no:randomly` |
| 4 | The two red tests are repaired, not deleted | both run, both assert the new key | run both by name |
| 5 | The across-filing key is held | the cases in step 2, by test | run them |
| 6 | The within-filing key is held | the cases in step 3, by test | run them |
| 7 | **`page` is load-bearing in the within-filing key** | removing it turns a 2-item case into 1, and **your tests go red** | mutation, scratch copy, tests named |
| 8 | **`page` is excluded from the across-filing key, and that matters** | adding it turns a 1-item case into 2, and **your tests go red** | mutation, scratch copy, tests named |
| 9 | The real file cannot see either boundary | both mutants still give `MERGED 14` with Asda and Seiyu present | re-run the programmer's measurement yourself, and say so in your entry |
| 10 | Both drop messages are held | the named fields, for both kinds | run the tests |
| 11 | A drop does not stop the run | the merge returns | step 6 |
| 12 | The compound case | every `kept:` names an item in the merged list | step 7 |
| 13 | Both routes | one case through the route B loader, one through `extract_multi_year` stubbed, 0 network attempts | run them |
| 14 | Walmart still merges 14 | `MERGED 14`, Asda and Seiyu both present | the real file. **This is a regression guard, not evidence about a key** |
| 15 | Lint | 4 errors, every one `BLE001`. **Run `ruff check .` after your last edit**, not over your own files | `-m ruff check .` |
| 16 | Nothing outside `tests/` changed | `git diff --stat -- . ':(exclude)tests'` holds only `ingestion/claude_extractor.py`, at the same line counts as when you started | before and after |
| 17 | Accuracy and coverage, with their units | "N of N assertions hand-sourced, 0 from the code's output", and the branch coverage of the behaviours you named | `--cov` on the modules your tests name |

**Every criterion is a measurement, never an opinion.** Criteria 7, 8 and 9 exist because
the real filing is green against both mutations, so without them this unit's two keys are
untested.

## Citations

- `.claude/agents/tester.md` — your role card. Its first section is the trap above.
- `.agent/assignments/P14e-nri-dedupe.md` — the unit, and its `## Round 2 amendment`.
- `.agent/journal/2026-10-06T1229-programmer-p14e-nri-dedupe.md` — round 1.
- `.agent/journal/2026-10-06T1412-code_reviewer-p14e-nri-dedupe.md` — the round 1 review,
  with the measured answers to four questions.
- `.agent/journal/2026-10-06T1432-programmer-p14e-nri-dedupe-round2.md` — round 2 and its
  mutation proof. The hand-built cases are at `C:\tmp\p14e2\hand_merge2.py`.
- `docs/9-reference/refactor-backlog.md`, items 112 and 119.
- `docs/2-rules/rules.md` — rule 1 (the model judges, Python does not) and rule 3.

## Known open items

- **Backlog item 98**: `runpy.run_path` executes a module into a fresh namespace, so a
  patch on that module object is not the name the fresh copy binds.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- **Backlog item 113**: `session_extraction prompt --pass 2` exits 2 on a Windows console
  without `PYTHONIOENCODING=utf-8`. Open, and not this unit's.
- **`extractions/WMT.json` is not in git.** Do not edit it and do not delete it. Copy it to
  a scratch path if you need a variant.
- The suite takes about 130 seconds.
