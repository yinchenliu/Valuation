---
agent: programmer
assignment: P10a-nci-bridge
round: 1
status: complete
files_touched: [ingestion/claude_extractor.py, models/financial_statements.py, models/valuation.py, analysis/dcf.py, cli.py, templates/valuation_result.html, templates/_statements.html, docs/3-architecture/valuation-math.md, docs/3-architecture/data-contract.md, docs/2-rules/llm-boundary.md]
verdict:
---

# P10a-nci-bridge — subtract noncontrolling interest in the equity bridge

Started 2026-10-02T2127 at HEAD `54c966f`. Outcome: **ok**, with one deliberate departure
from the assignment, stated in Decisions row 1: item 2's red test now goes **green**.

**User approval for the boundary change.** The assignment records that the user approved
this new Pass 1 field on 2026-10-02 ("item 48: fix"). `AGENTS.md:134` requires that
approval for "any change to the LLM boundary — a new field the model is asked to
produce". The approval is cited in `docs/2-rules/llm-boundary.md` as well.

## What I did

Backlog item 48. Pass 1's net income and cash flows are consolidated, so the enterprise
value values the whole group, but the bridge subtracted only net debt. I added a Pass 1
balance sheet key `noncontrolling_interest` (schema text and one system-prompt rule line,
no other prompt text changed); route A's parser reads it with no fallback (absent or
`null` -> `None`); `BalanceSheet.noncontrolling_interest: float | None = None` is a memo
in no total; `run_dcf` reads it through `_require_noncontrolling_interest`, which stops
naming the field and the year on `None`, on NaN, and on a missing latest balance sheet;
`DCFResult` carries `noncontrolling_interest` and `noncontrolling_interest_source` as
keyword-only fields with no default, and `equity_value = enterprise_value - net_debt -
noncontrolling_interest`. The CLI DCF block and the result page show "Less:
Noncontrolling interest" with its source line; the CLI balance sheet block and
`_statements.html` show a memo line that prints `not extracted` for `None`. Route B
needed no code: its loader derives the required keys from the schema. Three docs
updated. `api/routes_valuation.py` was not touched: the page reaches the field through
the `dcf` and `financials` objects it already has.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the bridge | pass | `PYTHONPATH=. .venv/bin/python /tmp/p10a/bridge.py` -> `EV 999.9999999999999 net_debt 200.0 NCI 50.0 equity 749.9999999999999 price 74.99999999999999`. EV 1,000 by construction (one year FCFF 100, WACC 10%, g 0: 100/1.1 + 1000/1.1 = 1000; error ~1e-13 is float). 1000 - 200 - 50 = 750, /10 = 75.0. Explicit `0.0` -> equity 800, price 80 |
| 2 | absence stops | pass | same script, NCI `None` -> `ValueError: noncontrolling_interest was not extracted for the FY2025 balance sheet, so the equity bridge cannot subtract it. ...`; no balance sheet -> `ValueError: noncontrolling_interest cannot be read for FY2025: the latest year (2025) has no balance sheet, ...`; NaN -> `ValueError: noncontrolling_interest on the FY2025 balance sheet is NaN, ...` |
| 3 | route B requires the key | pass | `.venv/bin/python -m ingestion.session_extraction check /tmp/p10a/WMT_without.json` (an unmodified copy of `extractions/WMT.json`) -> exit 2, `balance sheet 2026: key 'noncontrolling_interest' is absent. Write 0 only for a line the filing does not report.` The same file with `"noncontrolling_interest": 6563` added (`/tmp/p10a/WMT_with.json`) -> exit 0, `Clean: every key present, every PDF unchanged, arithmetic reconciles.` |
| 4 | the output shows it | pass | CLI: `PYTHONPATH=. .venv/bin/python /tmp/p10a/run_cli.py /tmp/p10a/WMT_with.json` (stubs `cli.fetch_price_data` and `claude_extractor._call_llm`) -> `Enterprise Value: $142,828M` / `Less: Net Debt $40,796M` / `Less: Noncontrolling interest$ 6,563M` / `source: FY2026 balance sheet, read from the filing (Pass 1 'noncontrolling_interest': nonredeemable plus redeemable)` / `Equity Value: $95,469M`. By hand 142,828 - 40,796 - 6,563 = 95,469. Balance sheet memo `Noncontrolling Int.: 6,563`; for `None` it prints `not extracted`. The same CLI on `WMT_without.json` exits 1 at the loader naming the key. Web: `PYTHONPATH=. .venv/bin/python /tmp/p10a/run_route.py /tmp/p10a/WMT_with.json` (TestClient `POST /valuation` with `session_file`, `routes_valuation.fetch_price_data` and `_call_llm` stubbed) -> status 200, bridge rows `Less: Noncontrolling Interest (6,563)`, the source row, `Equity Value 95,469`; statements memo row `6,563`. `_statements.html` rendered directly for None / 0.0 / 6563.0 -> `not extracted` / `0` / `6,563` (`/tmp/p10a/render_stmt.py`). The input 6,563 is the filing's figure as measured in the assignment (PDF page 22: 6,270 + 293), written into a scratch copy only |
| 5 | no new zero default | pass | `grep -rnE "if [^)]+ else 0(\.0)?\b\|\bor +0(\.0)?\b\|\.get\([^,]+, *0(\.0)?\)\|: *float *= *0\.0" '--include=*.py' models analysis api ingestion \| wc -l` -> **116** before and after |
| 6 | the red list | pass (listed) | test gate before **398 passed, 0 failed**; after **367 passed, 31 failed**. All 31 listed with reasons under Measurements. Every one is a fixture with no `noncontrolling_interest`; none is a defect in the new code |
| 7 | lint and types | pass | `ruff check .` -> `Found 5 errors.` (the same five BLE001 sites, lines shifted). `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` -> `Found 10 errors in 4 files` before and after. Outside the gate: `mypy cli.py` is 48 before (HEAD copy) and 48 after. Routes gate `GET /` -> 200 |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| **`run_dcf` stops when the latest balance sheet is absent, so `tests/unit/test_dcf_rule3_red.py` goes GREEN.** This departs from the assignment ("Item 2 ... its red test must stay red, for the same reason as before") | `docs/2-rules/rules.md` header: "If any instruction conflicts with one of them, the rule wins — including an instruction from ... an assignment file". With no balance sheet there is no noncontrolling interest to read. The assignment's own constraints are mutually exclusive here: the new `DCFResult` field must have no zero default (step 4), the census must not rise (criterion 5), and the run must not stop (the red test staying red). The only non-stopping options are `x if latest_bs else 0.0` (the 117th site, rule 3) or a `None` carried into `equity_value` (a default one step later) | Rewording the message to avoid "balance sheet" so the red test stayed red would be gaming a test. I did **not** touch the two item-2 lines (`net_debt`, `cash`): they are unchanged, their `else` branches are now unreachable from `run_dcf`, and a comment says so. Item 2's cleanup and moving the red test out of the red pattern are for the orchestrator and the tester |
| NCI read through one helper, `_require_noncontrolling_interest(balance_sheet, year) -> float`, fixed and typed | rule 2 | Inline checks in `run_dcf` would work; the helper keeps the three stops and their messages in one named place |
| A NaN NCI stops too | Same reasoning as `_require_finite` in the same file: a NaN passes every comparison and would make equity value and the price NaN with no exception | Not required by the assignment; costs three lines. Own message, because `_require_finite`'s text says "cannot be discounted", which is wrong for a subtracted term |
| `DCFResult.noncontrolling_interest_source: str`, keyword-only, no default | Step 5 asks for the term "with its source"; rule 4. Carrying the string on the result means the CLI and the page print the same words and neither reaches into `financials` | Building the label in the template from `financials.latest_year` would duplicate it in two outputs and could drift from the year `run_dcf` actually read |
| Parser: `nci_raw = bs_data.get("noncontrolling_interest")`; `None if nci_raw is None else float(nci_raw)` | Assignment step 2: no `.get(..., 0)`. A JSON `null` and an absent key both mean "not extracted" | `bs_data["noncontrolling_interest"]` would raise `KeyError` in route A on every cached/older answer; the assignment asks for `None` there and the stop in `run_dcf` |
| Schema text and one prompt rule line, verbatim to the assignment's description; no other prompt text changed | Assignment step 1 | — |
| `api/routes_valuation.py` not modified | Assignment scope condition: only if the page cannot reach the field. It can (`dcf` and `financials` are already in the context, proven by criterion 4) | — |

No code change was made to reach a target number.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `latest_balance_sheet.noncontrolling_interest` (route A parser) | becomes `None` ("not extracted"), no fallback; the stop is downstream in `run_dcf` | `ingestion/claude_extractor.py` `_parse_financials_response`; scratch: absent -> `None`, `null` -> `None`, `0` -> `0.0`, `6563` -> `6563.0` |
| same key (route B loader) | stops and names `noncontrolling_interest` and `balance sheet 2026` | criterion 3 |
| `BalanceSheet.noncontrolling_interest` in `run_dcf` | stops: `ValueError` naming `noncontrolling_interest` and `FY<year>` | criterion 2, `analysis/dcf.py:_require_noncontrolling_interest` |
| the latest balance sheet itself, for NCI | stops: `ValueError` naming `noncontrolling_interest` and the year | criterion 2 |
| NaN NCI | stops, names the field and year | criterion 2 |
| `DCFResult.noncontrolling_interest` / `_source` | no default; a constructor without them is a `TypeError` | `models/valuation.py`, `field(kw_only=True)` |
| CLI / `_statements.html` memo line on `None` | prints `not extracted`, never `0` or blank | criterion 4 |
| `net_debt`, `cash` in `run_dcf` | **defaults to `0.0`** when the balance sheet is absent — pre-existing, backlog item 2, unchanged; now unreachable from `run_dcf` because the NCI stop precedes it | `analysis/dcf.py` (the two `if latest_bs else 0.0` lines) |

## Measurements

### Baseline, before any change (HEAD `54c966f`; working tree holds P10b's uncommitted `analysis/capm.py`)

- test gate `--ignore-glob="*_rule3_red.py"`: **398 passed, 0 failed**. The `test_capm.py:473`
  failure named in the assignment was already gone in this tree; I attribute that to
  P10b's `analysis/capm.py`, not to me.
- `*_rule3_red.py`: 3 failed (dcf, projector, routes_session).
- ruff 5. mypy 10 in 4 files. Census 116. `GET /` 200.

### After

- test gate: **367 passed, 31 failed**. Every failure is attributed to this unit; none to
  P10b or P10c. The 31, grouped by reason:
  - **`run_dcf` on a hand-built `BalanceSheet` with no `noncontrolling_interest`** — stops
    with `noncontrolling_interest was not extracted for the FY2025 balance sheet`:
    `tests/unit/test_dcf.py::test_run_dcf_worked_example`,
    `::test_run_dcf_flat_perpetuity_identity[1]`..`[5]` (6).
  - **`POST /valuation` over a hand-built `FinancialStatements` with no NCI** — the route
    renders the error page with the same stop (FY2024):
    `tests/unit/test_route_context_keys.py::test_post_valuation_success_sets_all_six_keys`,
    `::test_the_cached_extraction_carries_all_four_fields_to_the_result_page`;
    `tests/unit/test_routes.py::test_post_valuation_renders_the_completed_valuation`,
    `::test_post_valuation_names_who_read_the_filing`,
    `::test_post_valuation_distinguishes_the_two_transports` (the last two fail in
    `_rows_under` with `substring not found` because the error page has no bridge);
    `tests/unit/test_statements_ui.py::test_post_valuation_renders_seven_blocks_closed_details_and_order`,
    `::test_substituted_ratio_badges_and_provenance`,
    `::test_implied_share_price_unchanged_on_baseline_stub` (8).
  - **A session-file fixture whose balance sheet lacks the key** — route B's loader stops
    with `balance sheet 2024: key 'noncontrolling_interest' is absent`:
    `tests/unit/test_routes_session.py::test_upload_then_follow_the_redirect_reaches_the_assumptions_page_with_the_label`,
    `::test_assumptions_from_a_session_file_shows_the_label_and_the_files_identity`,
    `::test_assumptions_with_a_ticker_that_differs_from_the_file_stops_naming_both`,
    `::test_assumptions_with_a_company_name_that_differs_from_the_file_stops_naming_both`,
    `::test_valuation_with_a_ticker_that_differs_from_the_file_stops_before_pricing`,
    `::test_valuation_on_a_cache_hit_shows_the_session_label`,
    `::test_valuation_on_a_cache_miss_shows_the_session_label`;
    `tests/unit/test_session_extraction.py::test_one_filing_both_routes_give_equal_statements_and_items`,
    `::test_three_filings_both_routes_give_equal_statements_and_items`,
    `::test_a_changed_figure_makes_the_routes_differ`, `::test_explicit_zero_is_accepted`,
    `::test_pass2_item_amount_zero_loads`,
    `::test_session_label_names_the_session_route_and_the_declared_model`,
    `::test_check_exit_codes` (`assert 2 == 0`), `::test_main_check_and_a_bad_page_range`
    (`assert 2 == 0`) (15).
  - **Route A fixture with no NCI reaching `run_dcf`**:
    `tests/unit/test_routes_session.py::test_route_a_label_survives_removing_the_key_on_a_cache_hit`
    (error page: `noncontrolling_interest was not extracted for the FY2024 balance sheet`) (1).
  - **A hard-coded 17-key list**: `tests/unit/test_session_extraction.py::test_the_required_key_lists_are_the_schema`
    compares `PASS1_BALANCE_SHEET_FIELDS` with a literal tuple that ends at
    `total_equity`; the schema now has 18 keys (1).
  - Fix for all of them, for the tester: give each fixture an explicit
    `noncontrolling_interest` (0 where the company has none), add the key to the literal
    tuple. **Do not weaken the stop.**
- `*_rule3_red.py`: **2 failed, 1 passed**. `test_dcf_rule3_red.py` now **passes** (see
  Decisions row 1); projector and routes_session stay red, unchanged.
- ruff 5 (same five BLE001). mypy 10 in 4 files. Census 116. `GET /` 200.
- Figures moved: on the scratch WMT session file with NCI 6,563 and stubbed prices,
  equity value is 142,828 - 40,796 - 6,563 = 95,469; the share price falls by
  6,563 / 8,022 = $0.82 against the same run without the term. The absolute price in
  that run ($11.90) comes from a stubbed return series and means nothing.

## What I did not do

- `tests/` — out of scope; the 31 failures above and the green red test are for the
  tester.
- `extractions/WMT.json` — the orchestrator adds the key. **Until then, any run on it
  (CLI `--session-file`, or `POST /valuation` with it) stops at the loader**, naming the
  key. This is the intended behaviour.
- Item 2's two lines in `run_dcf` — left as they were (now unreachable on the absent
  branch). Item 1, item 10, item 44 — untouched.
- `ingestion/session_extraction.py` — no change needed (criterion 3).

## Findings for the orchestrator

1. **`tests/unit/test_dcf_rule3_red.py` is green now.** Per STATUS section 1 ("When a red
   test goes green, move it out of the pattern in the same unit"), the tester should move
   it out of the `*_rule3_red.py` pattern. Item 2 can then be closed by deleting the two
   unreachable `if latest_bs else 0.0` lines in `analysis/dcf.py:run_dcf` (census
   116 -> 114) — a one-line follow-up unit. I did not do it because the assignment names
   item 2 as not fixed here.
2. **Pickled route A caches made before this change** load `BalanceSheet` objects with no
   `noncontrolling_interest` attribute; the class default `None` applies, so `run_dcf`
   stops naming the field. Users with an old `--cache-dir` pickle must pass
   `--no-cache` or re-extract. Correct behaviour, but worth one line in the user docs.
3. **The scripts `tests/test_e2e_*.py` and `tests/_run_lly_dcf.py`** call `run_dcf` on
   pickled or hand-built data and will now stop the same way when run by hand. They are
   not collected by the gate.
4. The schema still describes `total_equity` as "total stockholders equity" while the
   assignment and item 48 say Pass 1 asks for total equity **including** NCI. The new
   key's text says it is "already inside total_equity or another line", which holds
   either way, but the `total_equity` description is ambiguous. Changing it is a prompt
   change and needs the user.
