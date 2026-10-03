---
agent: code_reviewer
assignment: P10a-nci-bridge
round: 2
verdict: approved
---

# Review of P10a-nci-bridge, round 2

Programmer entry: `.agent/journal/2026-10-02T2141-programmer-p10a-nci-bridge-r2.md`
Round 1 review: `.agent/journal/2026-10-02T2139-code_reviewer-p10a-nci-bridge.md`

I reviewed `git diff 54c966f` over the nine paths I was given. All measurements were taken in
scratch trees under `/tmp/`, away from the shared tree, because P10c is still uncommitted there:
- `/tmp/p10a_r2base`: `54c966f` plus P10b's `analysis/capm.py`.
- `/tmp/p10a_r2rev`: `base` plus P10a's seven code and template files.
- `/tmp/p10a_r2probe`: `rev` with the absent NCI keys read as 0 and left out of the route B key
  list. This tree is the neutralisation probe.

None of the trees has a `.env`. Price data and `_call_llm` were stubbed in every run that could
reach them.

**User decision.** The assignment cites "item 48: fix" (2026-10-02) for the new Pass 1 fields.
`docs/2-rules/llm-boundary.md` now records that decision. Round 2 claims no exception to any
rule, and it needs none: each key is one printed line, and Python takes the sum.

## The guard checks

I counted each pattern per file, in the files in scope, at `54c966f` and now.

| Check | Result |
|---|---|
| conditional zero: `if … else 0.0` | `analysis/dcf.py` went from 2 to **0**: item 2's two lines are deleted. Every other file is unchanged |
| lookup with a fallback: `.get(k, 0)` | unchanged (`claude_extractor.py` 62/62). The two new reads at `claude_extractor.py:704-705` are `.get(key)` with no fallback |
| bare or-default | unchanged (3/3, all pre-existing) |
| money field defaulted to zero | unchanged (42/42, 10/10). The new `BalanceSheet` parts are `float \| None = None`. The `DCFResult` fields are `field(kw_only=True)` with no default |
| `**kwargs` | clean |
| `getattr(` | unchanged (2 and 1, pre-existing) |
| dict of functions keyed by data | clean |
| model client outside `ingestion/` | clean. The grep over `models/ analysis/ api/` returns nothing |
| census (`rules.md:65`) | **114**, down from 116 |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| either NCI key absent or `null` in a route A response | yes. It becomes `None`, and `total_noncontrolling_interest` stops on it | `/tmp/p10a_r2s/bridge.py`. The parser gives `None None` for absent, for `null` and for the old single key. It gives `0.0 0.0` for explicit zeros |
| either part `None` (one part, both parts, or unset on the dataclass) | yes. The message names the key and FY2025 | `noncontrolling_interest_redeemable was not extracted for the FY2025 balance sheet…` |
| either part NaN | yes | `noncontrolling_interest_nonredeemable on the FY2025 balance sheet is NaN…` |
| no latest balance sheet | yes, and the stop now comes first in `run_dcf` | `The latest year (FY2025) has no balance sheet, so net debt, cash and the noncontrolling interests cannot be read…` |
| either key absent in a route B session file | yes. Exit 2, naming each absent key | criterion 3 |
| `net_debt`, `cash` | no longer default to 0.0. They are read only after the balance sheet stop | `analysis/dcf.py:196-205` |
| `None` on the memo lines | prints `not extracted`. An explicit 0 prints `0` | template: None → `not extracted`, 0 → `0`, 6563 → `6,563`. CLI: `NCI, redeemable:      not extracted` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | yes. On WMT: 6,270 + 293 = 6,563, and 142,828 − 40,796 − 6,563 = 95,469. 95,469 / 8,022 = 11.90 |
| no double count | The 293 is inside `other_non_current_liabilities`: 13,941 + 16,549 + 293 = 30,783 (PDF page 22 against the session file). That line is not in `total_debt`, so `net_debt` does not already hold it. The 6,270 is inside `total_equity` 105,887, which no part of the bridge uses |
| percentages converted at the route boundary | not touched |
| falsy not treated as missing | `is None` in the parser, the CLI and the template. An explicit 0/0 gives equity 800 and price 80 |
| `analysis/` imports | `analysis/dcf.py` imports only `models` |
| scope | every path written is named in the assignment. `api/routes_valuation.py` was not needed and was not touched |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | the bridge | equity 750, price 75 | EV 1000.0, net debt 200, NCI 50 (40 + 10), equity 750.0, price 75.0. The source string names both parts and the function | yes |
| 2 | absence stops | `ValueError` naming the key and the year | 7 cases stop and name the key and FY2025: None in either part, None in both, NaN in either part, no balance sheet, and both parts unset | yes |
| 3 | route B requires the keys | exit 2 without them, exit 0 with them | Today's `extractions/WMT.json` (6270/293) copied to `/tmp/p10a_r2s/with.json` gives exit 0, `Clean`. With both keys removed: exit 2, naming both. With only the redeemable key removed: exit 2, naming it | yes |
| 4 | the output shows it | CLI and page | CLI: `Less: Noncontrolling Int.    $       6,563M` lines up with `Less: Net Debt               $      40,796M`; then the source line; then `Equity Value: $ 95,469M`. `POST /valuation` returns 200, with `Less: Noncontrolling Interest (6,563)`, the source row, `Equity Value 95,469`, and both memo rows, 6,270 and 293 | yes |
| 5 | census | 114 | 114 | yes |
| 6 | the red list | 31 of mine plus 5 of P10c's | `rev` gives 31 failed, 367 passed. The shared tree gives 36. `comm` of the two name sets leaves exactly the 5 P10c names the entry lists: `test_filings` ×1, `test_session_extraction::test_plan_writes…` ×1, `test_routes` upload ×3. The **probe** tree gives **398 passed, 0 failed**, so all 31 fail on the absent NCI keys alone. `*_rule3_red.py`: 2 failed, 1 passed (`test_dcf_rule3_red.py`, which stops for the missing balance sheet) | yes |
| 7 | lint and types | ruff 5, mypy 10 in 4 files | ruff `Found 5 errors.` in base and rev. mypy gate `Found 10 errors in 4 files` in both, and the error sets are identical once line numbers are stripped. `mypy cli.py` gives 48 in both | yes |

## Findings

### F4: CLI memo shows `not extracted` one character past its column · `note`

**Evidence:** `cli.py:515` formats the memo value with `{nci_text:>12}`. `not extracted` is 13
characters, so the line prints as `NCI, redeemable:      not extracted  (memo…`, one column off
from the figure lines.

**Rule or document:** none. This is cosmetic. The text is right and is never a 0.

**What would fix it:** widen the field to 13, or leave it as it is.

### F5: The rules, backlog and STATUS still describe item 2 as live · `note`

**Evidence:**
- `docs/2-rules/rules.md:71` (`analysis/dcf.py:80` gives a company **zero net debt**…);
- `docs/9-reference/refactor-backlog.md:39,157-162`;
- `STATUS.md:395`.

The code no longer does this (`analysis/dcf.py:196-205`, census 114).

**Rule or document:** none of those files is in this unit's scope. The programmer flagged it
under its "Findings for the orchestrator" 1.

**What would fix it:** the orchestrator updates those files and the census figure.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1: `.get(field, 0)` in the parser | `claude_extractor.py:712-728` | No. The new lines beside them have no fallback |
| 2: zero net debt and cash with no balance sheet | was `analysis/dcf.py:199-200` | Yes, and **fixed**: deleted, and replaced by a stop that names the field and the year. Round 2 step 3 |
| 32: share price 0.0 on zero shares | `models/valuation.py` `implied_share_price` | No |

Two prompt lines have the same shape as round 1's F1: `claude_extractor.py:184` asks the model to
sum capex, and `:260` tells it to adjust the catch-alls. Both predate this unit, and I saw that the
programmer has passed them to the orchestrator. They are not this unit's.

One more thing I saw: `analysis/dcf.py:_require_finite` checks for NaN and not for infinity, and
the new NCI check follows the same convention. An infinite NCI gives an equity value of `-inf`.
Route B's loader already rejects non-finite numbers (`session_extraction.py:190`). No rule is
broken, so I record no finding.

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| F1 | fixed | There are two keys, one per printed line, each with an explicit 0 when the filing prints none. The "PLUS" prompt text is gone (`claude_extractor.py:208-209`, `:262-264`). Python takes the sum in one typed function (`analysis/dcf.py:43`), which stops on `None` and NaN. The source line names both parts and their figures. I re-read PDF page 22: 293 and 6,270 are printed, and 6,563 is not |
| F2 | withdrawn | The orchestrator states that it made the `extractions/WMT.json` edit and that it has since updated the file to the two keys. The file now holds 6270 and 293. Not the programmer's write |
| F3 | fixed | The `$` signs line up at column 29 (CLI output, lines 237-238) |

## Verdict

`approved`

All three round 1 findings are answered. F1 is fixed in the shape the amended assignment
requires: each Pass 1 key is one printed line, and the sum is Python's, in one named, typed
function that stops naming the key and the year. Round 2 step 3 removed item 2's two conditional
zeros, and the census fell from 116 to 114, which I measured. Every done-criterion re-runs as
claimed. The 31 red tests fail on the missing NCI keys alone, which the neutralisation probe
proved. The 5 other failures are P10c's, by name. Lint and types are unchanged. F4 and F5 are
notes, and neither blocks. The tester can now repair the 31 fixtures with explicit values for both
keys.
