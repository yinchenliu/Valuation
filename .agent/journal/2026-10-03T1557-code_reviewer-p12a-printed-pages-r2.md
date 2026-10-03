---
agent: code_reviewer
assignment: P12a-printed-pages
round: 2
verdict: approved
---

# Review of P12a-printed-pages, round 2

Programmer entry: `.agent/journal/2026-10-03T1549-programmer-p12a-printed-pages-r2.md`
Round 1 review: `.agent/journal/2026-10-03T1547-code_reviewer-p12a-printed-pages.md`
Assignment: `.agent/assignments/P12a-printed-pages.md`, section "Round 2" (decisions 1 to 5)

Baseline `0839ad9`; rounds 1 and 2 are uncommitted. `git status --short` shows the four
in-scope files modified and the three journal entries. The assignment and
`.agent/journal/INDEX.md` are the orchestrator's edits and are not reviewed. Nothing under
`tests/`, `cli.py`, `api/`, `models/`, `extractions/` or `.claude/` moved.

## The guard checks

Run over `ingestion/claude_extractor.py` and `ingestion/session_extraction.py`: at
`0839ad9`, in the working tree, and on the 270 added lines of `git diff -U0 0839ad9`.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | 0 before / 0 after / 0 added |
| lookup with a fallback — `.get(k, …)` | 13 / 13 / **0 added** |
| bare or-default | 3 / 3 / 0 added |
| money field defaulted to zero | 0 / 0 / 0 |
| `**kwargs` | 0 / 0 / 0 |
| `getattr(` | 2 / 2 / 0 added |
| dict of functions keyed by data | 0 / 0 / 0 |
| model client imported outside `ingestion/` | clean: no hit in `models/`, `analysis/`, `api/` |

The unit adds no hit. These are the same counts as round 1.

## Rule 3, by reading

These rows cover only what round 2 changed. Round 1's table still holds for the rest.

| Value | Stops and names it? | Evidence |
|---|---|---|
| a PDF `pdfplumber` cannot open, route B | yes. It now names the filing too | `session_extraction.py:632-637`: `except ValueError as exc: raise ValueError(f"{where}: {exc}") from exc`. It re-raises and never swallows. `Pass1ShapeError` subclasses `ValueError` (measured), so a shape error would get the same correct prefix. `_filing_problems` has already proved the shape, so that path is unreachable |
| the neighbouring text line in a joined form | not a default. It is a test that returns False, so a refused join is a failed check, never a pass | `claude_extractor.py`, `printed_line_on_page`: `wanted not in _normalised_text(text_lines[index ± 1])` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | not crossed. Values are compared with the figures as printed, in the filing's own units, as in round 1 |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing | no new `if x` on a figure |
| `analysis/` imports no `ingestion/`, `api/` or model client | unchanged |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 2 | Walmart clean | exit 0, 89 of 89, 0.63 s | `check extractions/WMT.json`: exit 0, `89 checked, 89 found, 0 not confirmed`, the new Clean sentence. `real 0.63` | yes |
| 3 | invented row caught | exit 1, page 22, balance OK | my round 1 file `rv_c3.json`: exit 1, `'Other current assets' = 4,124 was not found on page 22`. `Total Assets` and `Total L + E` both `284,668 … +0 OK` | yes |
| 4 | wrong page caught | exit 1, page 23 | `rv_c4.json`: exit 1, `… was not found on page 23` | yes |
| 5 | page beyond the PDF | exit 1, 87 and 86 | `rv_c5.json`: exit 1, `cites page 87, but the PDF has 86 pages` | yes |
| 6 | the rule, by hand | 6 of 6 | my own script: True, False, True, True, True, False. All 6 as written | yes |
| 6b | a neighbour's figure is refused, on real page 22 | 3 of 3 False | `('Prepaid expenses and other', 84874)` False, `(…, 58851)` False, `('Inventories', 4124)` False. Controls, each a real row with its own figure, stay True: `('Prepaid expenses and other', 4124)`, `('Inventories', 58851)`, `('Total current assets', 84874)`. Column limit `(…, 4011)` True, short-label limit `('Debt', 34624)` True, as the docs say | yes |
| 7 | retry names the row, no amount | yes | `_call_llm` stubbed with real Walmart bytes. The retry opening reads "…and looked for each line on the page it cites". It names `Other current assets`, `other_current_assets` and `page 22`. None of `4,124`, `4124`, `284,668`, `284668` appears outside the JSON | yes |
| 8 | figures kept after the last retry | yes | 3 calls, both retries carry the PDF. `[Pass 1 FAIL] Checks still fail after 2 retries`, the page failure printed, and `other_current_assets` = 4124.0 returned | yes |
| 9 | unopenable PDF stops | `ValueError`, route B prefixed | `check rv_c9.json`: `STOPPED — …/rv_c9.json: filings[0] (rv_standin.pdf): the PDF sha256 f700f7160a8d5857… (28 bytes) cannot be opened by pdfplumber (PdfminerException…`, exit 2. Through `load_session_extraction`, the cause chain is `ValueError` → `ValueError` → `pdfplumber.utils.exceptions.PdfminerException` | yes |
| 10 | gates do not regress | ruff 5, mypy 10 in 4, census 67 | ruff `Found 5 errors.`, 5 `BLE001`. mypy (the exact harness command) `Found 10 errors in 4 files`. Census (`rules.md:65`, `'--include=*.py'` quoted): 67 | yes |
| 11 | the red list | 24, all stand-in PDF | gate run: **24 failed, 602 passed**. Compared **by name** with my round 1 set (`rv_after_set.txt`), the two sets are equal (`diff` empty). The output holds `cannot be opened by pdfplumber` 31 times. Control with `_printed_line_failures` stubbed to `[]` (my round 1 plugin `rv_nopage.py`): **626 passed**. `test_routes_session_rule3_red.py` still fails at `:63`, and `test_projector_rule3_red.py` still fails at `:98` | yes |

## Findings

### F6 — a label written across two printed rows is found with either row's figure, so one extra word gets past the F1 fix · `minor`

**Evidence:** on Walmart page 22: `('other Total current assets', 84874)` True (the programmer's case). Also `('Prepaid expenses and other Total', 84874)` True, `('Prepaid expenses and other Total', 4124)` True, `('Inventories Prepaid', 58851)` True and `('Inventories Prepaid', 4124)` True.
**Rule or document:** no rule is broken. The code applies decision 1 exactly: no neighbour holds these labels whole, so the joined form counts. But the second probe is F1's misread with one word added: a real row label takes the figure of the row below. `llm-boundary.md` says "a row the filing never printed, written to close a gap, is now caught, within three limits". None of the three limits covers a label longer than any printed label. So that sentence is false for this case. The programmer left it out because decision 4 allows only the short-label sentence. That was right, so this is not a finding against the programmer.
**What would fix it:** **a sentence in the docs now, not a code change now.** In both docs, the orchestrator should authorise widening the short-label limit to cover this case. A possible wording: *"A label is matched as text, not as a whole printed row: a short label can be found inside a longer printed label, and a label that runs from one printed row into the next is found with the figure of either row."* It should go in before the commit. My reasons against a code change in this unit:
- (a) Every match still needs a figure that is printed on the cited page, under a label that shares text with that figure's row. To use the gap, a model must write a label that no filing prints. A plain misread, where the printed label takes the neighbour's figure, is closed (6b).
- (b) A fix would be a third change to step 4. Text lines alone cannot tell a wrap from two rows. The one marker I found is that only one half of a real wrap prints figures. I measured the variant "a joined form counts only when the neighbouring line prints no figure". It still finds **89 of 89** Walmart lines. It makes all five probes above False and keeps criterion 6's wrap True. But it refuses a wrap whose other half prints a year (`"Senior notes due 2030\nand other 500"` → False). And see F7: Walmart exercises no joined form, so 89 of 89 cannot validate it.

Record the variant on the backlog as a candidate. Measure it on a filing with real wraps before adopting it.

### F7 — the real-file measurement never exercises a joined form · `note`

**Evidence:** for each of the 89 Walmart lines, I tested L alone with no join: **89 of 89** are found that way (scratch `/tmp/rv2/variant.py`). So "Walmart still finds 89 of 89" says nothing about the joined forms or the F1 condition. Their only evidence is the synthetic wrap in criterion 6 and the three refusals in criterion 6b.
**Rule or document:** none.
**What would fix it:** the tester should derive at least one fixture from a real wrapped row, taken from a filing under `10K_filings/` that has one. It should hold the wrap with figures on the first half and the wrap with figures on the second half.

### F8 — the F1 change refuses a layout that round 1 found: a label on one text line, its figures on the next · `note`

**Evidence:** `printed_line_on_page("Total stockholders' equity", 105887, "Total stockholders' equity\n$ 105,887 $ 97,000")` returns False. The label sits whole on the neighbour line, so the join is refused. Under round 1's rule this was True.
**Rule or document:** none. It fails safe: the line becomes a failed check that is shown, and the figures are kept. The assignment's fact table says all 16 filings print each row "on one line, label first, then the figures", so this is not live today.
**What would fix it:** nothing now. If a filing with this layout appears, the F6 variant (a neighbour that prints no figure may join) would accept it. That is one more reason to measure the variant together with this case.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 8 — blanket `except Exception` | `ingestion/claude_extractor.py`, five sites, BLE001 = 5 | no. Round 2 adds only `except ValueError`, which re-raises |
| 1 — census sites | 13 `.get(…, …)` and 3 or-defaults in the two files | no. 0 on added lines; census 67 |
| 62 — failed reading checks never reach the web page | `api/routes_valuation.py` | no, out of scope by assignment |

**Reminder to the orchestrator:** decision 5 says that a filing with no text layer (round 1 F5) goes on the backlog. `grep "text layer" docs/9-reference/refactor-backlog.md` finds no hit yet.

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| F1 | fixed | The rule follows decision 1, and the docstring and both docs state it. Criterion 6b measured 3 of 3 False, criterion 6 6 of 6, Walmart 89 of 89, and criteria 3 to 5 hold. A residual case is F6 |
| F2 | fixed | Route B now prefixes `where`, chained `from` the original. Route A's wording is unchanged, as decision 3 says |
| F3 | withdrawn | Decision 4 did not adopt it. The one-sentence short-label limit is in both docs, with the measured `Debt` = 34,624 example in `extraction.md` |
| F4 | withdrawn | Reassigned to the tester by decision 5. It still fails at `:63`, as reported |
| F5 | withdrawn | Reassigned to the orchestrator's backlog by decision 5. It is not recorded yet (see the reminder above) |

## Verdict

`approved`

Round 2 answers each round 1 finding as the Round 2 section decided. I re-ran every
criterion:
- Criterion 6b refuses all three neighbour figures, and its controls stay found.
- Criterion 6, Walmart's 89 of 89 and criteria 3 to 5, 7, 8 and 9 hold.
- Route B's stop now names the filing.
- The 24 red tests are the same set as in round 1, by name. The control with the walk stubbed passes 626 of 626.
- The gates hold at 5 / 10 / 67.

No rule is broken and no file outside scope was written.

On the programmer's new limit (F6): **a docs sentence now, not a code change.** A label
written across two rows takes either row's figure, so F1's misread comes back with one
added word. But the model must write a label that no filing prints. Closing it needs a
third rule change, and Walmart cannot validate that change (F7). The orchestrator should
authorise the widened limit sentence for both docs before the commit. It should also put
the "neighbour prints no figure" variant on the backlog, to be measured on a filing with
real wraps.
