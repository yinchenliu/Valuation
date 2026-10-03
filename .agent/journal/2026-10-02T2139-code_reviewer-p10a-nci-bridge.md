---
agent: code_reviewer
assignment: P10a-nci-bridge
round: 1
verdict: changes_requested
---

# Review of P10a-nci-bridge, round 1

Programmer entry: `.agent/journal/2026-10-02T2127-programmer-p10a-nci-bridge.md`

I reviewed `git diff 54c966f` over the ten files in scope. Every measurement below was taken
in scratch trees under `/tmp/p10a_rev/`, not in the shared tree, because P10c is still
writing to it:
- `base`: `54c966f` plus P10b's uncommitted `analysis/capm.py`.
- `after`: `base` plus P10a's seven code and template files.

Neither tree has a `.env`. `_call_llm` and `fetch_price_data` were stubbed in every run that could reach them.

**User decision.** The assignment cites the user's approval of 2026-10-02 ("item 48: fix")
for adding a Pass 1 field. That covers the new field. It is not an exception to rule 1, and
the assignment does not claim one. See F1.

## The guard checks

All checks ran over the lines this unit added in its in-scope files. The per-file census is
unchanged, so every hit in the whole files predates the unit.

| Check | Result |
|---|---|
| conditional zero: `if … else 0.0` | no new hit. `analysis/dcf.py:199-200` (item 2) is unchanged. See "Pre-existing" |
| lookup with a fallback: `.get(k, 0)` | clean. `claude_extractor.py:701` is `.get("noncontrolling_interest")` with no fallback. Absent or `null` gives `None` |
| bare or-default: `or 0.0` | clean |
| money field defaulted to zero: `: float = 0.0` | clean. `BalanceSheet.noncontrolling_interest: float \| None = None`, and `run_dcf` stops on it. The `DCFResult` fields are `field(kw_only=True)` with no default |
| `**kwargs` | clean |
| `getattr(` | clean |
| dict of functions keyed by data | clean |
| model client outside `ingestion/` | clean: `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` gives no output |
| census (`rules.md:65`) | **116**. Per file before/after: claude_extractor 49/49, financial_statements 47/47, valuation 13/13, dcf 2/2 |

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| NCI key absent or `null` (route A parser) | yes. It becomes `None`, and `run_dcf` stops | `claude_extractor.py:701-702`. My scratch run gives `ValueError: noncontrolling_interest was not extracted for the FY2025 balance sheet…` |
| NCI key absent (route B loader) | yes. Exit 2 with `balance sheet 2026: key 'noncontrolling_interest' is absent` | criterion 3 below |
| NaN NCI | yes | scratch: `noncontrolling_interest on the FY2025 balance sheet is NaN…` |
| latest balance sheet absent | yes | scratch: `noncontrolling_interest cannot be read for FY2025: the latest year (2025) has no balance sheet…` |
| `DCFResult` built without the NCI fields | yes, a `TypeError` | scratch: `missing 2 required keyword-only arguments: 'noncontrolling_interest' and 'noncontrolling_interest_source'` |
| a pickled route A cache made before this unit | yes. The class default `None` applies, then the stop | same path as "absent" |
| `None` on the CLI memo line and in `_statements.html` | prints `not extracted`, and `0` for an explicit 0 | rendered: None → `not extracted`, 0.0 → `0`, 6563.0 → `6,563`. CLI: `Noncontrolling Int.:  not extracted` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | yes. NCI is a balance sheet figure, in millions like its neighbours. On the CLI and the page, 142,828 − 40,796 − 6,563 = 95,469, and 95,469 / 8,022 = 11.90 |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing | correct throughout: `is None` in the parser, `cli.py:509` and the template. An explicit 0 passes: equity 800 and price 80 in my scratch run |
| `analysis/` imports no `ingestion/`, `api/` or model client | `analysis/dcf.py` imports only `models` |
| `DCFResult` built anywhere else | no. `analysis/dcf.py:202` is the only constructor, and `run_dcf` is the only path to a share price (checked `api/`, `cli.py`, `templates/`) |
| `BalanceSheet` built anywhere else | no. `claude_extractor.py:703` is the only constructor, so no merge or copy path drops the field |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | the bridge | equity 750, price 75 | `/tmp/p10a_rev/s/bridge.py`: EV 999.99…, ND 200, NCI 50, equity 749.99…, price 74.99… (float error) | yes |
| 2 | absence stops | `ValueError` naming the field and the year | None, an unset field, NaN and no balance sheet all stop and name `noncontrolling_interest` and FY2025 | yes |
| 3 | route B requires the key | exit 2, naming the key | scratch WMT copy with the key removed: exit 2, `filings[0] (…), balance sheet 2026: key 'noncontrolling_interest' is absent`. With the key: exit 0, `Clean` | yes |
| 4 | the output shows it | the CLI and the page show the term | CLI: `Less: Noncontrolling interest$ 6,563M`, a source line, `Equity Value: $ 95,469M`. `POST /valuation`: 200, `Less: Noncontrolling Interest (6,563)`, the source row, `Equity Value 95,469`, and the memo row `6,563`. Without the key, the CLI stops at the loader naming it | yes |
| 5 | no new zero default | 116 | 116, with every per-file count unchanged | yes |
| 6 | the red list | 398 → 367 passed / 31 failed, all from the missing NCI | `base` 398 passed. `after` 31 failed, 367 passed, the same 31 names the entry lists. **Cause, proven:** in a third tree I made only two changes: absent NCI read as 0.0, and the key left out of `PASS1_BALANCE_SHEET_FIELDS`. That tree gives **398 passed, 0 failed**. All 31 therefore fail on the missing NCI alone. `test_implied_share_price_unchanged_on_baseline_stub` going green there also shows that an NCI of 0 moves no other figure | yes |
| 7 | lint and types | ruff 5, mypy 10 in 4 files | ruff `Found 5 errors.` in both trees. mypy `Found 10 errors in 4 files` in both, and the error sets match after stripping line numbers. `mypy cli.py` gives 48 in both | yes |

Red tests, `base` → `after`: `test_dcf_rule3_red.py` goes from failed to **passed**. The projector
and routes_session red tests still fail, unchanged.

## The departure: item 2's red test goes green. Ruling: the departure is correct

The assignment told the programmer to keep `test_dcf_rule3_red.py` red. Steps 2 and 4 make that
impossible without breaking rule 3. Step 4 requires `run_dcf` to read the NCI from the latest
balance sheet, with no zero default on the result field. When there is no balance sheet, there
are only three choices:
- stop;
- `x if latest_bs else 0.0`, which would be the 117th census site and break criterion 5;
- carry `None` into `equity_value`.

The `rules.md` header settles it: the rule wins over an assignment. The test now passes for its
stated reason. The run stops with `ValueError`, and the message names the missing balance sheet
(`test_dcf_rule3_red.py`'s assertion is `"balance sheet" in message`). The message was not
reworded to suit the test. The programmer left item 2's two lines untouched, which matches the
assignment's "not fixing item 2". `.agent/assignments/P10ab-tests.md:19,39` already moves the
test out of the red pattern, as `STATUS.md` §1 requires. No finding.

## Findings

### F1 — The model is asked to add two printed figures, and the sum is printed nowhere in the filing · `major`

**Evidence:** `ingestion/claude_extractor.py:208` and `:261-263` ask for "the nonredeemable
noncontrolling interest shown in equity PLUS any redeemable noncontrolling interest shown
outside equity". The WMT filing text, pages 20-30 (`session_extraction text … --pages 20-30`),
prints `Redeemable noncontrolling interest 293` and `Nonredeemable noncontrolling interest
6,270`. 6,563 appears on no page.

**Rule or document:**
- Rule 1 ("Forbidden: asking the model for … any number that is not printed in the filing").
- `llm-boundary.md` ("Only values that are printed on a page of the filing").
- Rule 4: the reader cannot walk 6,563 back to one line, and if the model misses the mezzanine
  line, the sum comes out low and nothing detects it.

This is **the assignment's defect, not the programmer's**. Step 1 asked for exactly this text.
Per the contract, the assignment conflicts with a rule, so the rule wins and the orchestrator
corrects the assignment. The user's "item 48: fix" approves a field. It is not a recorded
exception to rule 1 for these lines.

**What would fix it:**
- Replace the key with two Pass 1 keys, each a printed line with an explicit 0 when absent:
  `nonredeemable_noncontrolling_interest` and `redeemable_noncontrolling_interest`.
- Add them in one named, typed Python function that stops if either is `None`.
- Show both components in the bridge's source line.

Changing the shape of a boundary field is the orchestrator's call, and probably the user's.

### F2 — `extractions/WMT.json` was changed, but no entry says who changed it · `note`

**Evidence:** `cmp /tmp/p10a/WMT_with.json extractions/WMT.json` shows the two files are
identical. The file's mtime is `21:34:48`, 38 s after the programmer entry (`21:34:10`). The
entry says the file was not touched ("The orchestrator adds the key").

**Rule or document:** this is not a rule break. Under the assignment's "Out of scope", the file is
the orchestrator's to change. It is gitignored, so the change is not in the diff.

**What would fix it:** the orchestrator confirms it made the copy. If the programmer made it,
the write is out of scope. If F1 is accepted, this key changes again anyway.

### F3 — CLI label runs into its dollar sign · `note`

**Evidence:** `cli.py:757` prints `Less: Noncontrolling interest$       6,563M`. The label is
exactly 29 characters, which fills the column, so no space is left before `$`. The page says
"Interest" with a capital I, and the CLI says "interest".

**Rule or document:** none. This is cosmetic.

**What would fix it:** use a shorter label, such as `Less: Noncontrolling int.`, or widen the
column.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 2: zero net debt and cash with no balance sheet | `analysis/dcf.py:199-200` | No. The lines are unchanged, and only the comment above them was rewritten. Their `else` branches can no longer be reached from `run_dcf`, because the NCI stop at `:198` comes first. Deleting them (census 116 → 114) is a follow-up for the orchestrator. `rules.md:43-44` and backlog §2 (line 169) still describe that behaviour as live |
| 1: `.get(field, 0)` in the parser | `claude_extractor.py:704-721` | No. The new line beside them adds no fallback |
| 32: share price `0.0` on zero shares | `models/valuation.py:336` | No |

**Seen, not recorded in the backlog, and not this unit's:**
- `claude_extractor.py:184` asks the model for capex as a "SUM of 'Purchases of PP&E' PLUS
  'Acquisitions…'".
- `:260` has the model "adjust catch-alls to close any gap".

These are the same shape as F1, and they predate this unit. The orchestrator should record
them. They are not a precedent that widens rule 1. I also agree with the programmer's
finding 4: the `total_equity` description is ambiguous, and fixing it is a prompt change that
needs the user.

## Verdict

`changes_requested`

The code is clean:
- every stop names the field and the year;
- no fallback or zero default was added, and the census holds at 116;
- the bridge is correct, and it is shown with its source on both outputs;
- all 31 red tests fail on the missing NCI alone, which the neutralisation probe proved;
- lint and types are unchanged;
- the programmer was right to depart from the assignment on item 2's red test.

**F1 blocks.** The schema text the assignment required asks the model for a number that is not
printed in the filing, against rule 1. It goes back to the orchestrator: the assignment
conflicts with a rule. It needs either two printed fields summed in Python, or a recorded user
decision that names these lines. F2 and F3 are notes.
