---
agent: tester
assignment: P14d-finance-leases-tests
round: 2
status: complete
files_touched:
  - tests/unit/test_p14d_finance_leases.py
  - .agent/journal/2026-10-04T2330-tester-p14d-finance-leases.md
verdict: pass
---

# P14d-finance-leases-tests, round 2: T1 deleted, T2 rebuilt from Walmart page 22, every test checked (T3)

Claude tester, one-team mode. This entry continues the partial Gemini run,
`.agent/journal/2026-10-05T0246-tester-p14d-finance-leases.md`, and does not edit it.
(My filename stamp is the local clock, 2026-10-04 23:30 EDT. The Gemini entries carry
stamps three to four hours ahead, so this file sorts before the one it supersedes.)
Every command ran with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`. No network call was made:
each test in the file runs under a fixture that refuses socket connections.

## What I did

I rewrote `tests/unit/test_p14d_finance_leases.py`, starting from the file committed at
`78d21c4`. **T1:** I deleted the valuation test that patched CAPM and the price with
values copied from a run. **T2:** The debt arithmetic is now built in the test from
the rows printed on Walmart's PDF page 22. I read those rows off the PDF myself, with
pdfplumber, page index 21. The route B prompt test now builds its session file in
`tmp_path`. One test still needs the real `extractions/WMT.json` and the PDF it names,
and it carries a `skipif`. **T3:** I checked every test in the three files against the
tester card (table below). I tightened the prompt test, which could pass with the rule
deleted. I added the case that kills the `_load_cache` key-type mutant, a test that no
catch-all field names finance leases, and a stop test for each absent debt key. I did
not modify `tests/unit/test_p14a_units.py` or `tests/unit/test_p14b_units.py`; their
`78d21c4` repairs hold (criterion 3). No implementation file was touched.

## Answers to the round 2 findings

### T1. The test that asserts the code's own output: deleted

`test_route_b_walmart_valuation_share_price_ties_to_28_02` is deleted, not replaced.
Its inputs (beta `0.5662169972765607`, ERP `0.06892192021225155`, price
`104.26000213623047`) and its EV `272,116M` came from a run, so the expected $28.02 was
a photograph. A hand-derived replacement would test `analysis/dcf.py`'s equity bridge.
P14d does not change that bridge, and `tests/unit/test_dcf.py` already covers it. The
part of the valuation that P14d does affect is net debt. Two hand-derived tests now
lock it (`test_walmart_finance_leases_in_debt_give_net_debt_40_796` and its contrast,
below). The Walmart end-to-end price is the overall lead's measurement, as the
amendment says.

### T2. The four tests that read a git-ignored file: three rebuilt, one skipped when the files are absent

| Committed test | Now |
|---|---|
| `test_route_b_cmd_prompt_exits_zero_and_emits_lease_rules` | replaced by `test_route_b_cmd_prompt_prints_the_lease_rule`. It writes a one-filing session file into `tmp_path`: `target_years` null and `include_bs` true, which is what `plan_filings` gives for one filing (`ingestion/claude_extractor.py:2772-2779`). Pass 1's prompt opens no PDF |
| `test_route_b_walmart_debt_lines_breakdown_by_hand_arithmetic` | split in two. (a) `test_walmart_finance_leases_in_debt_give_net_debt_40_796` builds the whole page-22 balance sheet as Pass 1 printed lines and parses it with `parse_pass1`. Page and figures are cited in the comment block above section 4 of the file. (b) The check of the real file's rows moved into the skip-guarded test below |
| `test_route_b_walmart_session_check_exits_zero` | merged into `test_real_route_b_walmart_file_maps_page_22_rows_by_the_rule`. It is skipped unless `extractions/WMT.json` exists **and** every PDF it names exists. The file names an absolute path on this Mac, so a check on the JSON alone would not be enough |
| the T1 test | deleted (T1) |

**Measured on a fresh clone.** I exported `git archive HEAD` to a scratch directory,
which leaves out `extractions/` and `10K_filings/`, and ran the tests there:

- committed file: `4 failed, 18 passed`. The 4 failures are exactly the four tests named in T2.
- revised file: `25 passed, 1 skipped`. The skip reason is "extractions/WMT.json or the Walmart 10-K PDF it names is absent (both git-ignored)".
- whole gate on the fresh clone: `1087 passed, 5 skipped, 0 failed`. The other 4 skips are the existing `test_p14b_note_figures.py` real-PDF tests.

### T3. Every test in the three files: kept, changed or deleted

The test names are those in the revised file. "Expected from" names the source of the
expected side.

| Test | Action | Reason / where the expected value comes from |
|---|---|---|
| `test_schema_short_term_debt_includes_finance_leases_excludes_operating` | kept, one phrase added | phrases quoted from assignment `P14d-finance-leases` step 1 ("short-term borrowings", "finance lease obligations due within one year", "Not operating lease obligations."). "short-term borrowings" is new: step 1 asks for it |
| `test_schema_long_term_debt_includes_finance_leases_excludes_operating` | kept | step 1 wording |
| `test_schema_other_current_liabilities_includes_operating_lease_obligations` | kept | step 1 wording |
| `test_schema_other_non_current_liabilities_includes_operating_lease_liabilities` | kept | step 1: "it names operating lease liabilities already; keep it" |
| `test_schema_no_catch_all_field_claims_finance_leases` | **added** | step 1/2: finance leases are debt, so neither `other_` liability field may name them. Kills mutant M6, which the committed file let survive |
| `test_system_prompt_states_the_lease_rule_inside_balance_sheet_rules` | **changed** | The committed version's `A or (B and C)` assertions passed with the rule moved (mutant M8 survives the alternative branch). Its last two asserts searched the whole prompt, where the embedded schema already holds `"other_current_liabilities"`. Now each phrase is asserted inside the one bullet that begins "- finance lease obligations are debt", in the order step 2 states, and the bullet must sit under `BALANCE SHEET RULES`. Expected: step 2 ("current in short_term_debt, long-term in long_term_debt; operating lease obligations are not debt and go to the catch-all fields") |
| `test_route_a_pass1_prompt_carries_the_rule_and_schema` | kept, rule check moved into the bullet | `pass1_prompts` is the one source of both routes' Pass 1 prompt. Same step 1/2 wording. `FilingPlan` now has the one-filing shape that `plan_filings` gives |
| `test_route_b_cmd_prompt_prints_the_lease_rule` | **changed** (T2) | as above; assignment done-criterion 2 of P14d |
| `test_cli_cache_format_marker_is_p14d_finance_leases` | kept | marker named in step 3 |
| `test_cli_cache_refuses_older_markers_and_names_p14d` ×4 | kept, tightened | The match is now on `repr("p14d-finance-leases-v1")`, quotes included, so a marker appearing in the file path cannot satisfy it. Expected: step 3 and done-criterion 4 of P14d |
| `test_cli_cache_accepts_the_p14d_marker` | **changed** | The committed version wrote the pickle with `cli.CACHE_FORMAT`, so it moved with the constant. It now writes the literal marker from step 3 |
| `test_cli_cache_save_writes_p14d_marker_and_roundtrips` | kept (renamed) | the literal marker from step 3; a roundtrip identity for the rest |
| `test_cli_cache_rejects_malformed_payload` ×6 | kept, one case added | added `(marker, "not-a-key", "fin", [])`, the only case reaching the `isinstance(payload[1], ExtractionKey)` condition, `cli.py:359`. It kills mutant M11, which the committed file let survive. Expected: `_load_cache`'s docstring contract (ValueError) and its message text naming the marker |
| `test_walmart_finance_leases_in_debt_give_net_debt_40_796` | **added** (T2) | PDF page 22 plus the hand sums in the file |
| `test_walmart_finance_leases_outside_debt_give_net_debt_34_035` | **added** | the same page with the two finance lease rows in the catch-alls. Hand: 40,796 − 856 − 5,905 = 34,035, which equals the route A figure in STATUS.md section 3. The balance check still passes, which is the reason "no check sees the difference" |
| `test_walmart_absent_debt_field_stops_and_names_it` ×2 | **added** | stop lock for the two fields this rule fills. `Pass1ShapeError` is stated in `parse_pass1`'s and `printed_line_page_failures`' docstrings for an absent key |
| `test_real_route_b_walmart_file_maps_page_22_rows_by_the_rule` | **changed** (T2), skip-guarded | `check` exit 0: P14d done-criterion 3. Rows and values: PDF page 22. Loaded net debt 40,796: the hand sums |
| `test_route_b_walmart_valuation_share_price_ties_to_28_02` | **deleted** (T1) | photographed run output |
| `test_route_b_walmart_session_check_exits_zero`, `test_route_b_walmart_debt_lines_breakdown_by_hand_arithmetic`, `test_route_b_cmd_prompt_exits_zero_and_emits_lease_rules` | **replaced** (T2) | see the T2 table |
| module docstring | **corrected** | It said long-term operating lease obligations were "11,041M". Page 22 prints **13,941**, and the committed test body had 13,941 |
| `test_p14a_units.py::test_old_cli_cache_marker_p11a_refused` | kept as repaired at `78d21c4` | Expected marker from step 3. The assertion `repr("p14b-…") in message` became `repr("p14d-…") in message`, the same form, with a loop adding the `p14b` marker as a refused input. Killed by M10 |
| `test_p14b_units.py::test_cli_cache_refuses_old_marker` | kept as repaired at `78d21c4` | same: `"p14b-…" in msg` became `"p14d-…" in msg`, `"expected format marker" in msg` kept, and the `p14b` marker was added as a refused input. Killed by M10 |
| `test_p14b_units.py::test_cli_cache_accepts_v1_marker` | kept, docstring-only change at `78d21c4` | It writes with `cli.CACHE_FORMAT`, a roundtrip identity. The literal is locked by my `test_cli_cache_accepts_the_p14d_marker` |

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | gate form: 0 failed | **pass** | `ANTHROPIC_API_KEY= GEMINI_API_KEY= .venv/bin/python -m pytest -q --ignore-glob="*_rule3_red.py"` gives `1092 passed`. On a fresh clone (git archive, no ignored dirs): `1087 passed, 5 skipped` |
| 2 | full suite: exactly the 2 red on purpose | **pass** | `… -m pytest -q` gives `2 failed, 1092 passed`. Failure set: `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`. Neither red test has gone green, so no move is due (backlog item 24 check) |
| 3 | no assertion weakened | **pass** | `git diff 78d21c4~1 78d21c4 -- tests/unit/test_p14a_units.py tests/unit/test_p14b_units.py`: each marker assertion was replaced one-for-one by the same form on the new marker, and none was removed. In my rewrite of the p14d file, the only removed assertions are the T1 test's 4 (photographed) and the committed debt test's `cash == 10727` / `short_term_investments == 0.0`. Those two are now implied by `net_debt == 40796` = 51,523 − 10,727 − 0 in both the page-built test and the real-file test. Every other assertion is kept or strengthened (T3 table) |
| 4 | new tests can fail (schema text, prompt rule, cache marker) | **pass, 11 of 11 mutants red** | `scratchpad/mutants.py` on the scratch copy, three test files run per mutant: M1 to M5 (each schema phrase removed), M6 (catch-all names finance leases), M7 (rule deleted), M8 (long-term finance leases sent to a catch-all inside the rule), M9 (operating half of the rule deleted), M10 (`CACHE_FORMAT` back to `p14b-pass2-units-v1`, 15 red including the p14a/p14b repairs), M11 (`_load_cache` key-type check dropped). The committed file, run against the same mutants after subtracting its 4 base failures from missing files, **let M6 and M11 survive** |
| 5 | lint | **pass, with a note on the wording** | `.venv/bin/python -m ruff check .` gives `Found 4 errors.`, all BLE001: `api/routes_valuation.py:445`, `:729`, `cli.py:1168`, `tests/test_e2e_all_googl.py:106`. This is the baseline set, unchanged. The criterion says "0 in `tests/`", but one of the four pre-existing errors has always been in `tests/test_e2e_all_googl.py` (backlog item 8). The three files in scope: `All checks passed!` |
| 6 | mypy | **pass** | `.venv/bin/python -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports` gives `Found 8 errors in 3 files`. My file checked on its own: 0 errors attributed to `tests/` (one `var-annotated` found during the run, fixed) |
| 7 | two counts | **pass** | below |

## The two counts

**Accuracy (unit: assertion sites).** The file holds 65 `assert` statements and 3
`pytest.raises` sites, 68 assertion sites in all. On this machine all 68 hold, across
26 of 26 collected test items. On a fresh clone the 10 asserts of the skip-guarded test
do not run, so 58 of 58 hold across 25 of 26 items, with 1 skipped. Every expected
value existed before the first run: the file passed on its first execution and no
expected value was edited afterwards.

**Coverage (unit: functions, then branches, then changed text).**

- Functions this unit added: **0**. Branches it added: **0**. P14d changed constants
  only.
- Changed text spans: **5 of 5** are read by a test that a mutant proves can fail.
  They are the `short_term_debt`, `long_term_debt` and `other_current_liabilities`
  schema strings, the prompt bullet, and `CACHE_FORMAT`.
- Functions that read those constants, measured with
  `pytest tests/unit/test_p14d_finance_leases.py --cov=cli --cov=ingestion.claude_extractor --cov=ingestion.session_extraction --cov-branch`:
  - `cli._load_cache` and `cli._save_cache`: every line, and 2 of 2 branch arcs.
  - `pass1_prompts`: every line.
  - `cmd_prompt`: the Pass 1 path is covered. The Pass 2 arm (5 arcs, `session_extraction.py:1024-1041`) is not reached by this file, but `test_session_extraction.py::test_prompt_prints_route_a_prompts` covers it. P14d did not change it.
  - the `parse_pass1` balance sheet block (`claude_extractor.py:2064-2106`): every line. The `{}` arc (2066 to 2108) is covered elsewhere.

## Expected values (testers only)

| Assertion | Expected | Where the expected value came from |
|---|---|---|
| schema `short_term_debt` phrases | "short-term borrowings", "finance lease obligations due within one year", "Not operating lease obligations." | assignment `P14d-finance-leases`, step 1 |
| schema `long_term_debt` phrases | "long-term finance lease obligations", "Not operating lease obligations." | step 1 |
| schema `other_current_liabilities` | "operating lease obligations due within one year" | step 1 |
| schema `other_non_current_liabilities` | "operating lease liabilities" | step 1 ("keep it") |
| no catch-all names "finance lease" | absent | steps 1 and 2: finance leases are debt |
| prompt bullet content and order | `"short_term_debt"` before `"long_term_debt"`; "operating lease obligations are not debt" before `"other_current_liabilities"`; `"other_non_current_liabilities"`; under BALANCE SHEET RULES | step 2 |
| `cli.CACHE_FORMAT` and every marker match | `"p14d-finance-leases-v1"` | step 3; P14d done-criterion 4 |
| `cmd_prompt` / check exit code | 0 | P14d done-criteria 2 and 3 |
| `short_term_debt` | 10,994 | page 22: 6,596 + 3,542 + 856 |
| `long_term_debt` | 40,529 | page 22: 34,624 + 5,905 |
| `total_debt` | 51,523 | 10,994 + 40,529 |
| `net_debt` | 40,796 | 51,523 − 10,727 (cash, page 22) − 0 (no short-term investments row printed) |
| `other_current_liabilities` | 2,227 | page 22: 596 + 1,631 |
| `other_non_current_liabilities` | 30,783 | page 22: 13,941 + 16,549 + 293 |
| `total_assets` | 284,668 | 10,727 + 11,172 + 58,851 + 4,124 + 136,083 + 28,735 + (14,750 + 6,123 + 14,103), which equals the printed total |
| `total_liabilities_and_equity` | 284,668 | 107,469 + 40,529 + 30,783 + 105,887, which equals the printed total |
| contrast `short_term_debt` / `long_term_debt` | 10,138 / 34,624 | 6,596 + 3,542 / 34,624 |
| contrast `net_debt` | 34,035 | 10,138 + 34,624 − 10,727. The same figure appears in STATUS.md section 3 for route A |
| contrast catch-alls | 3,083 / 36,688 | 2,227 + 856 / 30,783 + 5,905 |
| real-file rows | 6,596; 3,542; 856 / 34,624; 5,905; operating 1,631 and 13,941 | page 22 |
| absent `short_term_debt` / `long_term_debt` | `Pass1ShapeError` naming the key | `parse_pass1` and `pass1_problems` docstrings (absent key is a shape problem) |
| malformed cache payload | `ValueError` naming `'p14d-finance-leases-v1'` | `_load_cache` docstring, plus step 3 |

## Rule 3: what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| cache payload marker (`payload[0]`) | stops: `ValueError` naming `'p14d-finance-leases-v1'` | `cli.py:355-367`. Locked by `test_cli_cache_refuses_older_markers_and_names_p14d` ×4 and `test_cli_cache_rejects_malformed_payload[bad_payload0,1]` |
| cache payload shape (tuple, length 4) | stops, same message | locked by `test_cli_cache_rejects_malformed_payload[bad_payload0-3,5]` |
| cache key type (`payload[1]`) | stops, same message | `cli.py:359`. Locked by `test_cli_cache_rejects_malformed_payload[bad_payload4]` (new) |
| `latest_balance_sheet.short_term_debt` key | stops: `Pass1ShapeError` naming `short_term_debt` | `claude_extractor.py:968` (`_line_field_problems`). Locked by `test_walmart_absent_debt_field_stops_and_names_it[short_term_debt]` |
| `latest_balance_sheet.long_term_debt` key | stops: `Pass1ShapeError` naming `long_term_debt` | locked by `[long_term_debt]` |
| schema and prompt text | constants; no absent case | n/a |

**Stop paths I could not lock: none in this unit.** Two pre-existing notes, neither a
finding against P14d. An empty list `[]` for a debt field gives 0
(`claude_extractor.py:525`), by design: it is the explicit answer "the filing prints no
such row" (comment at `:252`). `BalanceSheet`'s money fields default to `0.0`
(`models/financial_statements.py:172-234`), but `parse_pass1` passes every field
explicitly. `current_portion_lt_debt=0.0` is hard-coded at `claude_extractor.py:2086`
because `short_term_debt` holds the current portion. That design is pre-existing.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Delete the T1 test and write no hand-derived replacement | amendment T1; the equity bridge is `analysis/dcf.py`, unchanged by P14d and covered by `test_dcf.py` | A replacement would add a duplicate DCF test that is not about leases. The lease effect on valuation is net debt, which two hand-derived tests lock |
| Parse the full page-22 balance sheet through `parse_pass1` instead of summing literals | It runs the real code path (`figure_from_printed_lines`, `BalanceSheet.total_debt`, `net_debt`), and the printed totals give an independent cross-check (284,668 both sides) | Summing literals in the test would test Python's `+` operator and nothing in the repository |
| Add the "outside debt" contrast | the user's decision 83a was taken because of exactly this 40,796 against 34,035 gap (P14d objective) | It shows in one place that the balance check cannot see the misplacement, so the schema text is the only guard. It locks the reason for the rule |
| Skip the real-file test unless the JSON **and** its PDF exist | `WMT.json` stores an absolute PDF path from this machine. `check` re-hashes the PDF | A guard on the JSON alone would fail on a machine that has the JSON but keeps its PDFs elsewhere |
| Leave `test_p14a_units.py` and `test_p14b_units.py` as repaired at `78d21c4` | They hold (criterion 3), and M10 kills both | Re-editing them would churn the files without adding a test |

## Measurements

- Before (fe56ecf): full suite failure set {projector_rule3_red, routes_session_rule3_red}, 1088 passed.
- After: full suite, same failure set of 2, 1092 passed. The gate gives 1092 passed. +4 items: the committed file had 22 items and mine has 26.
- Fresh clone (no `extractions/`, no `10K_filings/`): the committed p14d file fails 4. Mine gives 25 passed, 1 skipped. Whole gate: 1087 passed, 5 skipped.
- ruff 4 (all BLE001, baseline set). mypy 8 errors in 3 files (baseline).
- No figure moved. No implementation file touched.

## What I did not do

- I did not run `cli.py --session-file extractions/WMT.json` end to end ($28.02). The amendment assigns that to the overall lead (P14d done-criterion 3).
- I did not test the docs changes (`data-contract.md`, `valuation-math.md`, `extraction.md`). They are prose, and no test reads them.
- I did not edit the earlier Gemini tester entry.

## Findings for the orchestrator

1. **The comment above `CACHE_FORMAT` is stale** (`cli.py:229-237`). It explains the
   P11a and P14a marker changes but not P14b (Pass 2 units) or P14d (finance leases).
   The P14d assignment told the programmer to change nothing in `cli.py` but the
   `CACHE_FORMAT` line, so this is not a finding against that unit. A one-line comment
   for each marker would let the next reader see why an old cache is refused.
   Owner: programmer, in any later `cli.py` unit.
2. **The committed `78d21c4` tester file had two blind spots, now closed.** It let M6
   (a catch-all naming finance leases) and M11 (the `_load_cache` key-type check
   dropped) survive. Its prompt test could not tell where in the prompt its phrases
   appeared. Recorded so the overall lead can weigh the Gemini run's "verdict: pass" in
   the partial entry, which was never measured.
3. **Done-criterion 5's wording, "0 in `tests/`", has never matched the baseline.** One
   of the four pre-existing BLE001 errors is in `tests/test_e2e_all_googl.py:106`
   (backlog item 8). Later assignments should say "0 in the files in scope".
