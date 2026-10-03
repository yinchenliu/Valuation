---
agent: programmer
assignment: P10a-nci-bridge
round: 2
status: complete
files_touched: [ingestion/claude_extractor.py, models/financial_statements.py, models/valuation.py, analysis/dcf.py, cli.py, templates/_statements.html, docs/3-architecture/valuation-math.md, docs/3-architecture/data-contract.md, docs/2-rules/llm-boundary.md]
verdict:
---

# P10a-nci-bridge round 2 — two printed NCI keys, the sum in Python

Started 2026-10-02T2141. This round answers the review at
`.agent/journal/2026-10-02T2139-code_reviewer-p10a-nci-bridge.md` and the assignment's
"Round 2" section, steps 1-4. Round 1's entry is unchanged.

**Outcome: ok.**

## What I did

- **F1 / Round 2 steps 1-2.** I replaced the single Pass 1 key `noncontrolling_interest`
  ("nonredeemable PLUS redeemable") with two keys. Each one is a printed line, and each is
  `0` when the filing prints none:
  - `noncontrolling_interest_nonredeemable`: the line inside equity;
  - `noncontrolling_interest_redeemable`: the mezzanine line outside equity.
- **The prompt.** The prompt sentence about adding the two is gone. The new prompt rule
  says "each copied from its own printed line ... Do not combine them".
- **`BalanceSheet`.** It holds the two parts as `float | None = None`. They are memos, in no
  total.
- **The parser.** It reads both with `.get(key)` and no fallback, so an absent key or
  `null` becomes `None`.
- **The sum.** The sum is taken in one named, typed function,
  `analysis/dcf.py:total_noncontrolling_interest(balance_sheet: BalanceSheet) -> float`.
  It stops on `None` or NaN in either part and names that key and the year.
- **The bridge.** It subtracts the total. `DCFResult.noncontrolling_interest_source` names
  both parts and their figures, and the function that summed them.
- **Step 3.** The two item-2 lines in `run_dcf` are deleted. `run_dcf` now raises once, up
  front, when the latest balance sheet is absent. The error names net debt, cash, the
  noncontrolling interests and the year. After that, `net_debt` and `cash` are read with
  no conditional. The census went from 116 to 114.
- **Step 4 / F3.** The CLI label is now `Less: Noncontrolling Int.    $`, padded to the
  same 29-character column as `Less: Net Debt               $`.
- **Memo lines.** The CLI and `_statements.html` balance sheet memo lines show the two
  parts, each `not extracted` on `None`.
- **Docs.** The three docs are updated.
- **Files I did not write.** `extractions/WMT.json`, `tests/`, and every P10b and P10c
  file.

## Findings, answered by number

| # | Finding | Answer | Evidence |
|---|---|---|---|
| F1 | The model was asked to add two printed figures, and the sum is printed nowhere | **Fixed** as the amended assignment specifies (two printed keys, sum in Python). I re-read PDF page 22 myself: `Redeemable noncontrolling interest 293 271` and `Nonredeemable noncontrolling interest 6,270 6,408`. No 6,563 appears | `.venv/bin/python -m ingestion.session_extraction text extractions/WMT.json --filing 0 --pages 22-22 \| grep -i noncontrolling`. Code: `ingestion/claude_extractor.py:208-209` (schema), `:262-264` (rule), `:698-711` (parser); `analysis/dcf.py:43` (the sum) |
| F2 | `extractions/WMT.json` was changed with no entry naming who changed it | **Not mine.** The orchestrator confirms it made the edit. I did not write the file in either round. In round 1 I wrote only `/tmp/p10a/WMT_with.json`. This round I read `extractions/WMT.json` and wrote scratch copies under `/tmp/p10a/`. It still holds the old single key (`{'noncontrolling_interest': 6563}`), so until the orchestrator updates it, route B stops on it and names both new keys (criterion 3) | `/tmp/p10a/r2_oldkey.json` (a byte copy) → exit 2 |
| F3 | The CLI label runs into its dollar sign | **Fixed**: `Less: Noncontrolling Int.    $       6,563M`, aligned with `Less: Net Debt               $      40,796M` | criterion 4 output below |

The review's "Pre-existing" row for item 2 is acted on by step 3. Its "seen, not recorded"
items (capex SUM at `:184`, "adjust catch-alls" at `:260`) are not in this round's
scope. They are listed under Findings for the orchestrator.

## Done-criteria (round 1 table, re-run, plus round 2 steps)

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the bridge | pass | `PYTHONPATH=. .venv/bin/python /tmp/p10a/bridge2.py`. EV 1,000 by construction: FCFF 100, WACC 10%, g 0, so 100/1.1 + 1000/1.1 = 1000. Net debt 200; NCI parts 40 and 10. Output: `EV 999.9999999999999 net_debt 200.0 NCI 50.0 equity 749.9999999999999 price 74.99999999999999` (float error). Source string: `FY2025 balance sheet, read from the filing: nonredeemable 40 + redeemable 10, summed by analysis/dcf.py:total_noncontrolling_interest`. Explicit 0 and 0 → equity 800, price 80 |
| 2 | absence stops | pass | Same script. Each of these raises a `ValueError` naming the key and FY2025: nonredeemable `None`, redeemable `None`, nonredeemable NaN, redeemable NaN. No balance sheet → `The latest year (FY2025) has no balance sheet, so net debt, cash and the noncontrolling interests cannot be read ...` |
| 3 | route B requires the keys | pass | `.venv/bin/python -m ingestion.session_extraction check` on three scratch files. `/tmp/p10a/r2_without.json` (no NCI key) → exit 2, names both `noncontrolling_interest_nonredeemable` and `noncontrolling_interest_redeemable` as absent. `/tmp/p10a/r2_oldkey.json` (today's `extractions/WMT.json`, old key) → exit 2, the same two. `/tmp/p10a/r2_with.json` (6270 and 293) → exit 0, `Clean`. No change to `session_extraction.py`: the key list now has 19 entries, derived from the schema |
| 4 | the output shows it | pass | **CLI:** `PYTHONPATH=. .venv/bin/python /tmp/p10a/run_cli.py /tmp/p10a/r2_with.json` stubs `fetch_price_data` and `_call_llm`. Output: `Enterprise Value: $ 142,828M`, `Less: Net Debt $ 40,796M`, `Less: Noncontrolling Int. $ 6,563M`, `source: FY2026 balance sheet, read from the filing: nonredeemable 6,270 + redeemable 293, summed by analysis/dcf.py:total_noncontrolling_interest`, `Equity Value: $ 95,469M`. By hand: 6,270 + 293 = 6,563, and 142,828 − 40,796 − 6,563 = 95,469. The CLI memo shows `NCI, nonredeemable: 6,270` and `NCI, redeemable: 293`; both print `not extracted` on `None`. **Web:** `/tmp/p10a/run_route.py /tmp/p10a/r2_with.json` → status 200. It renders the `Less: Noncontrolling Interest (6,563)` row, the source row with both parts, and `Equity Value 95,469`. **Template:** `_statements.html` rendered for None, 0 and 6563 gives `not extracted`, `0` and `6,563` on both memo rows |
| 5 | census | pass, **114** | `grep -rnE "<rules.md:65 pattern>" '--include=*.py' models analysis api ingestion \| wc -l` → `114`. It was 116 in round 1 and at baseline; the two item-2 lines are gone |
| 6 | the red list | pass (listed) | See Measurements. My 31 failures are the same set as round 1. P10c's work adds 5 more, and I attribute none of those to me |
| 7 | lint and types | pass | ruff: `Found 5 errors.`, the same five BLE001. mypy gate: `Found 10 errors in 4 files`. `GET /` → 200 |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The sum lives in `analysis/dcf.py:total_noncontrolling_interest`, not on `BalanceSheet` as a property | Round 2 step 2 says "one named, typed function ... stops naming the missing key". A property cannot raise cleanly from inside a template. It would also put a second, non-stopping reader of the sum within reach of `_statements.html` | The memo lines show the two printed parts and no total, so the template never sums. The one total appears in the bridge, beside its source string |
| The missing-balance-sheet stop moved from the NCI helper into `run_dcf`, with one message naming net debt, cash and NCI | Step 3 deletes the item-2 lines. A raise in `run_dcf` also narrows `latest_bs` to `BalanceSheet` for mypy, so `latest_bs.net_debt` needs no conditional. The message keeps "balance sheet" and "net debt", so `test_dcf_rule3_red.py` stays green for the right reason | — |
| The source string prints both parts with `:,.0f` | Rule 4: the reader sees the two printed figures that make the total | The f-string runs only after `total_noncontrolling_interest` has proved that neither part is `None` |
| The old single key in a session file is ignored, so the file fails as "absent" | The schema no longer names it, and the loader requires the two new keys | Accepting the old key would mean accepting a figure the model added up, which is F1 |

No code change was made to reach a target number.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `noncontrolling_interest_nonredeemable` / `_redeemable` (route A parser) | `None` ("not extracted"), with no fallback. The stop happens downstream | Scratch: absent → `None None`; `null` → `None None`; 0/0 → `0.0 0.0`; 6270/293 → `6270.0 293.0`; old single key only → `None None` |
| the same keys in route B | stops at the loader and names each key | criterion 3 |
| either part `None` or NaN in `total_noncontrolling_interest` | stops and names the key and the year | criterion 2 |
| the latest balance sheet in `run_dcf` | stops and names net debt, cash, NCI and the year | criterion 2 |
| `net_debt`, `cash` | **no longer default to 0.0**: the item-2 lines are deleted | `analysis/dcf.py:run_dcf`, census 114 |
| `DCFResult.noncontrolling_interest` / `_source` | no default, so leaving them out is a `TypeError` | unchanged from round 1 |
| memo lines on `None` | print `not extracted` | criterion 4 |

## Measurements

- **Test gate** (`--ignore-glob="*_rule3_red.py"`): **362 passed, 36 failed**. Round 1
  measured 367 passed and 31 failed; the baseline was 398 passed and 0 failed.
- **Failure set, compared with round 1** (`diff` of sorted FAILED lists): the same 31, plus 5 new
  ones. The 5 new ones are **not mine**. They are P10c's work in `ingestion/filings.py`
  and `api/routes_upload.py`, which are still uncommitted:
  - `tests/unit/test_filings.py::test_parse_pdf_args_reads_year_colon_path`: `ingestion/filings.py:320: ValueError: The fiscal year given does not match the filing`
  - `tests/unit/test_session_extraction.py::test_plan_writes_route_a_plan_and_refuses_to_overwrite`: the same `filings.py:320` error
  - `tests/unit/test_routes.py::test_post_upload_saves_the_file_and_redirects_naming_it` (`assert 400 == 303`)
  - `tests/unit/test_routes.py::test_the_form_on_the_front_page_is_accepted_by_the_route_it_targets` (`assert 400 == 303`)
  - `tests/unit/test_routes.py::test_post_upload_journey_reaches_a_rendered_assumptions_page` (`assert 400 == 200`)
- **My 31.** They are named in round 1's entry, Measurements. They fail now on the new key
  names: 9 name `noncontrolling_interest_nonredeemable`, and 6 name
  `noncontrolling_interest_redeemable` (a route B loader reports both). The rest fail on
  the same fixtures through the error page, plus the literal key tuple in
  `test_the_required_key_lists_are_the_schema`. **The tester's fix:** in each fixture, give
  both keys an explicit value (`0` where the company has none), and set the literal tuple
  to the 19 keys ending `total_equity`, `noncontrolling_interest_nonredeemable`,
  `noncontrolling_interest_redeemable`. Do not weaken either stop.
- **`*_rule3_red.py`:** 2 failed, 1 passed. `test_dcf_rule3_red.py` passes. Its message
  now comes from the explicit balance sheet stop in `run_dcf`, which names "balance sheet"
  and "net debt", and no longer from the NCI helper. The projector and routes_session red
  tests are unchanged.
- **Gates:** ruff 5, mypy 10 in 4 files, census 114, `GET /` 200.

## What I did not do

- `extractions/WMT.json`: the orchestrator's file (F2). It needs
  `"noncontrolling_interest_nonredeemable": 6270, "noncontrolling_interest_redeemable": 293`
  in place of `"noncontrolling_interest": 6563` (PDF page 22, re-read this round).
- `tests/`, the P10b files and the P10c files.
- `docs/2-rules/rules.md:43-44` and `docs/9-reference/refactor-backlog.md` §2 still describe
  item 2 (`dcf.py:80` zero net debt) as live. Both are outside my scope.

## Findings for the orchestrator

1. **Item 2 is fixed in code.** Update `rules.md:43-44`, backlog §2 and the census figure
   (119/116 → 114) in STATUS. The tester should move `test_dcf_rule3_red.py` out of the red
   pattern; `.agent/assignments/P10ab-tests.md` already plans this.
2. **`P10ab-tests` needs the two-key shape.** If it was written for the single
   `noncontrolling_interest` key, its fixtures and the literal key tuple need both new keys.
3. **The review's "seen, not recorded" items.** `claude_extractor.py:184` asks the model to
   SUM capex lines, and `:260` asks it to "adjust catch-alls to close any gap". Both have
   the same shape as F1 and predate this unit. Fixing either is a prompt change and goes
   to the user.
4. **The `total_equity` schema text is still ambiguous** about NCI (round 1 finding 4).
