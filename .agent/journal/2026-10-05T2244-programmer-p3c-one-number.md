---
agent: programmer
assignment: P3c-one-number
round: 1
status: complete
files_touched: [api/routes_valuation.py, templates/assumptions.html, templates/valuation_result.html, cli.py]
---

# P3c-one-number — the web page and the CLI give one number for one filing (items 87, 92, 6, 97)

## What I did

The six ratio inputs on `templates/assumptions.html` no longer carry a `value`
attribute, so an untouched form posts nothing for them; the derived figure stays in
the "Derived Default" column and is repeated in each field's `placeholder`, which a
browser never submits (the user's decision of 2026-10-05, option 1a). The five
`float = Form(0)` ratio fields in `run_valuation` became `str = Form("")` and are
converted with the `.strip()` pattern the four CAPM/WACC fields below them already
use — the shape the comment at `api/routes_valuation.py:537-556` records the reason
for. That closes backlog item 87 (an untouched form now derives at full precision and
is labelled `derived`, not `supplied`) and backlog item 6 for all five fields (a typed
`0` survives as `0.0`). `cli.py` stage 5 now passes `adjusted`, not `financials`, so
the historical FCFF table is built from the statements the valuation used (item 92);
both entry points print the same sentence naming that basis; and a year the CLI cannot
compute is printed with the reason instead of being dropped by a bare `continue`. The
error block on both page templates carries `white-space: pre-line` (item 97).

Every figure below comes either from hand-built `FinancialStatements` with
`pipeline.fetch_price_data` and `api.routes_valuation._run_extraction` stubbed, or
from a route-B session file over a real PDF with only the market stubbed. No network
call and no model call in either. The scratch harness is at `C:/tmp/p3c/` — nothing in
the repository, and nothing under `tests/`, was written:

| Script | What it measures |
|---|---|
| `harness.py` | the hand-built filing, the stubbed market, and a parser for what a browser would submit from a rendered form |
| `c1_price.py` | criteria 1, 2, 5, 6, 7, 8: CLI price against web price, six ways |
| `c10_fcff.py` | criteria 10, 11, 12, 13: the FCFF table, CLI against web |
| `c11_before.py` | criteria 11 and 13, the `19fe831` side |
| `c9_render.py` | criteria 4, 7, 9, 12, 14: what the two pages render |
| `c12_cli_e2e.py` | criteria 1, 12, end to end: `cli.main()` against `POST /valuation` on one session file |
| `c19_errorbox.py` | criteria 14 and 19: the error box, and which regex can read it |

The "before" tree is `git archive 19fe831` exported to `C:/tmp/p3c/before`. **`git
stash` was not used**, as the assignment requires.

**One thing I measured that is worth reading before the table.** The repository's
existing session-file fixture derives ratios of 30.0%, 20.0%, 3.0%, 7.0%, 1.5% and
100.0% — **every one of them exact to one decimal place.** Run end to end through that
fixture, `19fe831` gives the same price on the web as in the CLI
(`1243.176933388447`, `delta = 0.0`), because rounding to one decimal takes nothing
away from a figure that already has one. **The defect is invisible on a filing whose
ratios round cleanly**, which is why criterion 1 asks for one that does not and why the
hand-built filing below exists. A test built on the existing fixture alone would have
reported this unit's defect as absent.

**The hand-built filing.** Three years, revenue 100,000 / 110,000 / 121,000, one
`high`-confidence non-recurring item (`sga`, `add_back`, 100, 2024). Cost of revenue is
chosen so that every **adjusted** year's operating margin is exactly **4.2537%** — a
figure that does not survive a round to one decimal place, which is the defect under
test. Market data: stock returns == market returns, so beta is exactly 1.0.

## Done-criteria

Commands run with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and `.venv/Scripts/python.exe`.
`$AFTER = C:/Users/LiuYinchen/Valuation`, `$BEFORE = C:/tmp/p3c/before` (`19fe831`).

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | An untouched form gives the CLI's price | **pass** | `python C:/tmp/p3c/c1_price.py $AFTER`. CLI (`pipeline.value_company`, no ratio override): `np.float64(101.7718483684063)`. Web (GET `/assumptions`, then POST exactly what a browser submits from that rendered form with nothing changed): `np.float64(101.7718483684063)`. **`price == cli_price` is `True`; `delta` is `np.float64(0.0)`.** Not "equal to the cent" — equal to all 16 significant digits of the IEEE-754 double, bit for bit. Case C, with every ratio field absent instead of empty, gives the same number and the same `delta = 0.0` |
| 1b | The same identity, end to end, through route B | **pass** | `c12_cli_e2e.py $AFTER`: one session file over a real PDF written by the repository's own test helper (read, never written); 54 of 54 printed lines found on their cited pages; the only stub is `pipeline.fetch_price_data`. `GET /assumptions` renders all six ratio fields with `value=''`; submitting that form unchanged gives `WEB implied share price = np.float64(1243.176933388447)`, and `cli.main()` on the same file with no projection override gives `np.float64(1243.176933388447)`. `EQUAL? True   delta = np.float64(0.0)` |
| 2 | The old behaviour is reproduced first | **pass** | the same script against `$BEFORE`: CLI `101.7718483684063`, untouched form **`103.0635942742541`**, `equal to the CLI? False`, `delta = np.float64(1.2917459058478045)` — **$1.29 a share, 1.269%**. The before tree's form posted `operating_margin='4.3' tax_rate='21.1' da_pct='3.0' capex_pct='2.0' nwc_pct='1.0' revenue_growth='10.0, 10.0, 10.0, 10.0, 10.0'` in its `value` attributes; the after tree posts `''` for all six and shows those figures as placeholders |
| 3 | No derived value reaches a form `value` attribute | **pass** | `grep -n 'value="{{ defaults\.' templates/assumptions.html` → **no match** (exit 1). Also `grep -n 'value="{%* *if* *defaults\|value="{{ *defaults'` → no match, so the jinja-`if` form used by `revenue_growth` is gone too |
| 4 | The derived figure is still shown twice | **pass** | `grep -n placeholder templates/assumptions.html` → lines 194, 208, 214, 224, 230, 236: `revenue_growth`, `operating_margin`, `tax_rate`, `da_pct`, `capex_pct`, `nwc_pct` — **6 of 6, by name**. Rendered (`c9_render.py $AFTER`): the "Derived Default" column reads `10.0, 10.0, 10.0, 10.0, 10.0%`, `4.3%`, `21.1%`, `3.0%`, `2.0%`, `1.0%`, and the form's parsed placeholders read `'10.0, 10.0, 10.0, 10.0, 10.0'`, `'4.3'`, `'21.1'`, `'3.0'`, `'2.0'`, `'1.0'` |
| 5 | A typed `0` is kept | **pass** | `c1_price.py $AFTER`, case D (`operating_margin=0`): **`ProjectionAssumptions ... operating_margin=0.0`**, origin `supplied`, price `np.float64(-15.000000000000007)` = −(net debt 15,000)/1,000 shares, the right answer for a 0% margin. Against `$BEFORE`, case D built **`operating_margin=None`** and returned the derived price `101.7718483684063` with origin `derived` — backlog item 6, live |
| 6 | A blank field is `None` | **pass** | same script, cases B and C: `operating_margin=None tax_rate=None da_pct_revenue=None capex_pct_revenue=None nwc_pct_revenue=None revenue_growth_rates=[]` |
| 7 | The result page says `derived` for an untouched form | **pass** | `c1_price.py $AFTER` case B: all six of `revenue_growth_rates`, `operating_margin`, `tax_rate`, `da_pct_revenue`, `capex_pct_revenue`, `nwc_pct_revenue` have `origin = derived`. Rendered (`c9_render.py`): six "derived from the filing: N filing-year(s) ..." sentences on `POST /valuation`. Against `$BEFORE` the same POST gave **six `supplied`** |
| 8 | The result page says `supplied` for a typed value | **pass** | `c1_price.py $AFTER` cases D, E, F: `origin[operating_margin] = supplied`, the other five `derived` |
| 9 | The form states what blank means and what typing means | **pass** | `c9_render.py $AFTER`, section "what the form says about blank and about typing" — three sentences, rendered: *"A blank field means 'derive it'. Left blank, the ratio is derived from this filing's statements at full precision ... The share price then equals the one `cli.py` reports for the same filing and the same market data."* / *"A value you type is used exactly as typed, and the result page labels it supplied: nothing in this platform checks a figure you typed against the filing."* / *"Typing the grey figure shown inside a field is not the same as leaving the field blank. That figure is the derived value rounded to one decimal place ... so typing it back gives a different share price."* Plus a per-field `Blank = derive from the filing. A typed 0 is a 0% margin, not "derive".` The third sentence is **measured, not asserted**: `c1_price.py` case F types the figure the field shows (`'4.3'`) and gets `np.float64(103.0428680875818)` against the blank field's `101.7718483684063` — $1.27, 1.249% |
| 10 | The CLI's historical FCFF equals the web's | **pass** | `c10_fcff.py $AFTER`. CLI on `adjusted`: 2022 `3,260`, 2023 `3,695`, 2024 `4,171`. Web `_historical_fcff_by_year(adjusted)`: `3260.2832835975814`, `3694.939569789697`, **`4171.139261582476`**. Every year equal |
| 11 | The CLI's figures changed, and by how much | **pass** | `c11_before.py $BEFORE` (19fe831's own `cli.py`, its own stage-5 argument): 2022 `3,260`, 2023 `3,695`, **2024 `4,170`**, `Int*(1-t)` `323`. Mine: 2024 **`4,171`**, `Int*(1-t)` `324`. Full precision: 2024 raw `4169.5072815141975` → adjusted `4171.139261582476`, **delta `+1.631980068278608`**; 2022 and 2023 delta `0.0` (the item is a 2024 item). The cause, printed beside it: 2024 effective tax rate `0.1936742962145068` raw against `0.18959434604380856` adjusted. **The CLI now equals what 19fe831's web page already showed for the same filing** (`19fe831` web 2024 = `4171.139261582476`) |
| 12 | Both entry points name the basis | **pass** | one sentence, word for word in three renderings. **CLI, from a real `cli.main()` run** (`c12_cli_e2e.py $AFTER`, route B on a session file over a real PDF), under the `HISTORICAL FCFF (CFO-based, $M)` banner: `Computed from the normalised statements, the same statements the valuation used.` At `$BEFORE` the same run prints the banner and goes straight to the column headings — **no basis at all**. `c9_render.py $AFTER`: `present: True` on `GET /assumptions` and `present: True` on `POST /valuation`, rendered as `Historical Free Cash Flow to Firm: Computed from the normalised statements, the same statements the valuation used.` |
| 13 | A year with no cash flow statement is reported, not dropped | **pass** | statements built with 2023's cash flow statement absent. **After** — CLI: `2023  not extracted: cash flow statement`; web: `2023  is_computable=False  missing=('cash flow statement',)`. **Before** (`c11_before.py $BEFORE`) — the CLI table jumps `2022` to `2024`: the year is **not in the output at all**, while the web page for the same statements printed the row |
| 14 | The multi-line stop is readable | **pass** | `grep -rn "white-space" templates/` → `templates/assumptions.html:14`, `templates/upload.html:11`, `templates/valuation_result.html:16`, each `style="white-space: pre-line"` on the `alert alert-error` div. Rendered, by execution (`c19_errorbox.py $AFTER`): `GET /assumptions?files=0:a.pdf,2025:b.pdf` renders `<div class="alert alert-error" style="white-space: pre-line">1 of 2 filings have no fiscal year:` followed by the file list and the two remedies — `P3b`'s multi-line stop, inside a box that now preserves its newlines. At `$BEFORE` the same page rendered `<div class="alert alert-error">` and the browser collapsed it |
| 15 | Types | **pass** | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` → **`Found 5 errors in 2 files (checked 21 source files)`**: 4 in `analysis/projector.py`, 1 in `api/routes_upload.py`. Unchanged. None removed, none added |
| 16 | Lint | **pass** | `-m ruff check .` → **`Found 4 errors.`**, every one `BLE001` |
| 17 | Census | **pass** | the grep at `docs/2-rules/rules.md:102` → **64**. Unchanged. The five `x / 100 if x else None` conversions I deleted were never counted by that grep (it matches `else 0`, not `else None`) |
| 18 | Route | **pass** | `TestClient(app.app, raise_server_exceptions=False).get('/')` → **200** |
| 19 | The failing test set | **measured; 22 tests changed state, every one named and attributed below** | see "Measurements". 2 are the unit's direct subject; 20 trace to one test-helper regex, and the failure is proved by execution to be the helper, not the message |

Write guard: `.claude/check_guard.py` → **48/48 guard cases correct**.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The five ratio fields become `str = Form("")`, converted with `.strip()` | `api/routes_valuation.py:537-556`: a `float` form field cannot express "the user left this blank" without inventing a sentinel number, and when the route always reached the calculation with a value the output could never say a figure had been substituted. The assignment's step 1 | A `float \| None` field would need a sentinel. Keeping `float` and adding a companion "was this typed?" flag per field is six more form fields the browser would have to be trusted to set |
| `placeholder`, not `value`, for the derived figure | A browser never submits a placeholder, so an untouched form posts nothing and `derive_assumptions` derives at full precision. The user's decision, option 1a | `value` with full precision would fix the price but still label a platform figure "supplied by the caller" (rule 6). Removing the figure from the page entirely would lose the reader's only sight of it |
| The "Derived Default" column is untouched | Assignment step 3; `assumption_sources` already labels each cell `derived` or `substituted` | — |
| The `:.1f` display strings stay `:.1f` | They now feed only the column and the placeholder, neither of which is submitted. Rounding a *displayed* figure is not rounding a *computed* one — and the form says, in words, that the two differ | Showing 4.2537% in the placeholder would tempt a reader to type it, which is a supplied figure wearing a derived figure's clothes |
| `step="any"` on the five ratio inputs | `step="0.1"` makes a browser enforce the same one-decimal grid this unit just removed from the server. Assignment step 5 | Leaving `step="0.1"` would refuse `4.25` in a field whose own derived default is `4.2537` |
| `terminal_growth_rate` keeps `value="2.5" step="0.1" min="0" max="5"` | Assignment: item 90 is not this unit's, and its backlog row was corrected on 2026-10-05 in a way that changes its fix | — |
| `print_historical_fcff` takes a **required** `basis: str` | Rule 6 and rule 2. The function cannot see which statements it was handed, so a sentence hard-coded inside it would read "normalised" for a caller that passed the raw ones — a false label, which is the defect rule 6 exists for. The caller knows what it passed, so the caller states it | A module-level constant printed unconditionally is one `print_historical_fcff(financials)` away from lying. There is exactly one call site and no test calls it, so the signature change costs nothing |
| The basis sentence is a literal in three places | The module both entry points share is `pipeline.py`, which is **out of this unit's file scope**; and neither entry point may import the other (a web route importing `cli`, or `cli` importing FastAPI through `api/`) | Recorded as finding F1 below rather than widened into |
| The sentence sits at the `_statements.html` **include site** on each page | `templates/_statements.html` draws the FCFF table and is **not in this unit's file scope** | — |
| The sentence is ASCII (`,` not an em dash) | It reaches a Windows console, which is not UTF-8 by default | — |
| `valuation_result.html`'s error div is collapsed onto one source line | With `white-space: pre-line` the template's own indentation becomes rendered blank lines. `upload.html:11` is already one line | — |
| The CLI's uncomputable row reads `not extracted: cash flow statement` | The same words `_statements.html` renders for the same row, so the two entry points say the same thing | — |
| Nothing was changed to reach a target number | The only numbers I chose are the hand-built filing's, chosen **before** any run so that the adjusted operating margin is exactly 4.2537% — the assignment's own worked example of a ratio that does not round cleanly | — |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `operating_margin`, `tax_rate`, `da_pct`, `capex_pct`, `nwc_pct` (form) | **Blank is not "missing".** A blank field is the reader declining to override, and `ProjectionAssumptions.<field> is None` is the documented way to say so (`analysis/projector.py:226-228`). It reaches `derive_assumptions`, which derives from the filing and **labels the result `derived` with the number of filing-years behind it** — or `substituted`, when nothing fed it. Nothing defaults to 0 | `c1_price.py $AFTER` cases B/C: `operating_margin=None ...` and six `origin = derived`. The substituted branch is `analysis/projector.py`'s and was not touched |
| the same five, typed | A typed `0` is **kept as `0.0`**, not read as absent | case D: `operating_margin=0.0`, origin `supplied`, price `-15.000000000000007`. At `19fe831` the same input gave `None` |
| the same five, non-numeric | `float("abc")` raises `ValueError`; the run stops and the message renders on the result page. **The message does not name which field** — see finding F2 | the pre-existing shape of `risk_free_rate`, `equity_risk_premium`, `beta_override`, `cost_of_debt_override` |
| income statement / cash flow statement of a year, in `print_historical_fcff` | **Stops computing that year and prints the reason**, naming each missing statement. No figure is invented and the year is not dropped | `c10_fcff.py $AFTER`: `2023  not extracted: cash flow statement` |
| `basis`, in `print_historical_fcff` | Required positional argument — a caller that omits it raises `TypeError` at the call, so the table cannot print without naming its basis | `cli.py`, the signature |
| `defaults.*_display` in a placeholder | `defaults` is `{}` on the no-filing and error paths, so `defaults.operating_margin_display or ''` renders an empty placeholder — a field with no suggestion, not a field with a fabricated one. The "Derived Default" column uses the identical guard and is unchanged | `templates/assumptions.html:208` and `:61` |

**No "defaults to" row.** This unit deleted five sites that had one (`x / 100 if x else None`) and added none.

## Measurements

**The failing test set, by name, not by count.**

| | Command | Result |
|---|---|---|
| before, in my working tree at the start of this run | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly` | `1146 passed, 3 skipped in 129.28s` — **failing set = {} (empty)** |
| after | the same command | `22 failed, 1124 passed, 3 skipped in 108.44s` |

Both runs collected **1149 tests** (`--collect-only` → `1149 tests collected`), so the
collected set did not move between them and the comparison is like for like.
`P1d-skipped-filings`'s newest file, `tests/unit/test_real_filings_helper.py`, was
written at 22:43 and my baseline ran at 22:45.

The baseline is **1146 passed, 3 skipped**, not the `1137 passed, 5 skipped` the
assignment records at `19fe831`. That difference is **not mine**: `P1d-skipped-filings`
is in flight and its changes to `tests/conftest.py`,
`tests/unit/test_p14b_note_figures.py`, `tests/unit/test_p14d_finance_leases.py`,
`tests/unit/test_p15a_two_routes.py`, `tests/unit/_real_filings.py` and
`tests/unit/test_real_filings_helper.py` were already on disk when I started. I
measured the baseline against the tree as I found it.

**22 tests changed state, in one direction only (pass → fail). Every one is mine, and
every one falls into exactly two groups.** `tests/` is denied to me and I changed
nothing in it.

**Group A — 2 tests. The unit's direct subject: the `value` prefill.**

| Test | Assertion that now fails |
|---|---|
| `tests/unit/test_routes.py::test_get_assumptions_puts_the_derived_defaults_into_the_form` | `assert _field_value(body, field) == expected, field` → `AssertionError: revenue_growth` / `assert '' == '20.0, 20.0, 20.0, 20.0, 20.0'` |
| `tests/unit/test_routes.py::test_get_assumptions_reads_two_filings_with_the_multi_year_extractor` | the same `EXPECTED_DEFAULTS` loop over `_field_value` |

Both read the form field's **`value` attribute** and assert it holds the derived
default. That prefill is backlog item 87 and is precisely what the user's decision of
2026-10-05 ("1a") removed. The figures themselves are unchanged and still on the page
**twice** — in the "Derived Default" column and in each field's `placeholder`. The
repair is to read the placeholder and the column instead of `value`, and to add the
assertion the old tests could not make: that an untouched form posts `""`.

**Group B — 20 tests. One test-helper regex, not one message.**

`tests/unit/_session_route_helpers.py:368` extracts the error box with
`re.search(r'<div class="alert alert-error">(.*?)</div>', body, re.DOTALL)` — a literal
that requires the `div` to carry **no attribute**. Backlog item 97 adds
`style="white-space: pre-line"` to that div, so the helper returns `None` and every
assertion built on it fails.

**Proved by execution, not by reading** (`python C:/tmp/p3c/c19_errorbox.py $AFTER`):

```
--- POST /valuation, no filing named ---
  the box is on the page: True
  rendered: <div class="alert alert-error" style="white-space: pre-line"><strong>Error:</strong> No filing named: session_file, files and file_path are all empty.</div>
  helper regex as written  -> None
  the same regex, tolerant of attributes -> 'Error: No filing named: session_file, files and file_path are all empty.'
```

The same script against `$BEFORE` prints `helper regex as written -> MATCH` for the
identical message. **The stop, its wording and its HTTP status are unchanged; only the
helper's regex is.** Grouped by assertion, the 20 are 12 × `assert None is not None`
(via `assert message is not None` / `assert shown is not None`), 5 ×
`assert 'confirm_zero_debt' in ''` and 3 × `assert '--confirm-zero-debt' in ''` — all
three forms reading `error_text`'s return value.

| File | Tests |
|---|---|
| `tests/unit/test_routes_session.py` | `test_assumptions_with_a_ticker_that_differs_from_the_file_stops_naming_both`, `test_assumptions_with_a_company_name_that_differs_from_the_file_stops_naming_both`, `test_valuation_with_a_ticker_that_differs_from_the_file_stops_before_pricing`, `test_route_a_on_a_cache_miss_with_no_key_stops_on_the_credential`, `test_valuation_with_no_filing_stops_naming_all_three_fields`, `test_assumptions_with_files_naming_no_entry_stops_naming_files`, `test_assumptions_with_a_session_file_that_is_not_there_stops_naming_it`, `test_a_session_file_missing_one_pass1_key_renders_the_loaders_message`, `test_a_bad_session_file_uploaded_through_the_form_reaches_the_page_named`, `test_valuation_with_session_file_and_files_on_a_cache_miss_stops` |
| `tests/unit/test_routes.py` | `test_post_valuation_with_the_box_unchecked_stops_at_item_22[absent]`, `[empty]`, `[absent-with-override]`, `test_post_valuation_with_a_value_no_checkbox_sends_stops_and_names_it[yes]`, `[ON]`, `[true]`, `[1]`, `[ on]` |
| `tests/unit/test_p3b_pipeline_stops.py` | `test_the_stop_reaches_the_assumptions_page` |
| `tests/unit/test_pipeline.py` | `test_the_share_count_stop_reaches_the_web_result_page` |

**The helper was already blind to one of the three pages before this unit.**
`templates/upload.html:11` has carried `style="white-space: pre-line"` since before
`19fe831`, so `error_text` could never read the upload page's error box. Widening the
regex by four characters — `<div class="alert alert-error"[^>]*>` — repairs all 20 and
the upload page with them. **That is a `tests/` change and it is not mine to make.**

**Gates.**

| Gate | Before (`STATUS.md` at `f763b7c`) | After |
|---|---|---|
| Lint | 4, every one `BLE001` | **4**, every one `BLE001` |
| Types | 5 errors in 2 files | **5 errors in 2 files**, 21 files checked |
| Census | 64 | **64** |
| Route `GET /` | 200 | **200** |
| Write guard | 48/48 | **48/48** |

**The numbers this unit moved, with the input that produced them.**

| Figure | Before (`19fe831`) | After | Input |
|---|---|---|---|
| web share price, untouched form | `103.0635942742541` | **`101.7718483684063`** | the hand-built filing, 4.2537% adjusted operating margin, stubbed market |
| CLI share price, no override | `101.7718483684063` | `101.7718483684063` | the same |
| the gap between them | **$1.29 / 1.269%** | **$0.00 / 0.000%** | — |
| CLI historical FCFF 2024 | `4,170` (`4169.5072815141975`) | **`4,171`** (`4171.139261582476`) | stage 5 given `adjusted`, not `financials` |
| CLI historical FCFF 2022, 2023 | `3,260`, `3,695` | `3,260`, `3,695` — unchanged | the non-recurring item is a 2024 item |
| CLI `Int*(1-t)` 2024 | `323` | **`324`** | 2024 effective tax rate `0.19367…` → `0.18959…` |
| a 2023 with no cash flow statement, in the CLI | the row is absent | `2023  not extracted: cash flow statement` | — |

**Walmart's $27.01 and $28.02 were not reproduced, and no criterion asked for them.**
This machine holds no session file and no cached extraction (`extractions/` is empty),
so there is no end-to-end real-filing run available here. Every figure above comes from
hand-built statements.

## What I did not do

- **No test was written or edited.** `tests/` is denied, and the unit's tests are a
  separate assignment after the code review.
- **`templates/_statements.html` was not touched.** It is outside the Files in scope,
  so the basis sentence sits at each page's include site rather than in the table's own
  heading. A later unit that owns that file should move it into the `<h2>`.
- **`analysis/projector.py`, `models/valuation.py`, `pipeline.py` were not touched.**
  No change was needed in any of them.
- **Items 5, 8, 26, 82, 88, 89, 90, 94, 99 were left exactly as they are**, each named
  in the assignment's "Out of scope".

## Findings for the orchestrator

| # | Finding | Evidence |
|---|---|---|
| F1 | **The historical-FCFF basis sentence is a literal in three files.** `cli.HISTORICAL_FCFF_BASIS`, `templates/assumptions.html` and `templates/valuation_result.html` each hold the same string. Nothing checks that they still match, so a reword in one leaves the other two asserting a basis the figures may not have. It belongs in the one module both entry points already import — `pipeline.py` — with the route passing it into both template contexts. All three candidate homes (`pipeline.py`, `models/valuation.py`, `templates/_statements.html`) are outside this unit's file scope | `cli.py:70-88`, `templates/assumptions.html:306-314`, `templates/valuation_result.html:252-259` |
| F2 | **Nine form fields stop on a non-numeric entry with a message that does not name the field.** `float(operating_margin)` raises `could not convert string to float: 'abc'`, which the blanket `except Exception` renders on the result page. Pre-existing for `risk_free_rate`, `equity_risk_premium`, `beta_override` and `cost_of_debt_override`; this unit gave the same shape to five more. It stops rather than guessing, so it is not rule 3, but a reader cannot tell which of nine fields was rejected. The fix is one typed helper, `_optional_percent(field: str, value: str) -> float \| None`, used by all nine | `api/routes_valuation.py:650-658` and `:655-658` |
| F3 | **`risk_free_rate` and `equity_risk_premium` still carry `step="0.1"`.** They are blank-by-default fields whose substituted constant is `4.0`, so the grid happens not to bite today, but a browser will refuse `4.25` in either. The assignment's step 5 named only the five projection ratios, so I left them. Same one-character fix | `templates/assumptions.html:254`, `:259` |
| F4 | **`templates/_statements.html` renders `not extracted` six times per uncomputable year** — once per column — so a year missing one statement produces six copies of the same sentence across the row. The CLI now prints it once. Display only; no figure moves | `templates/_statements.html:500-505` |
| F5 | **`P1d-skipped-filings`'s uncommitted test changes raise the gate from 1137 passed / 5 skipped to 1146 passed / 3 skipped.** Noted so the next `STATUS.md` re-measurement is not read as this unit's doing. The two un-skipped tests are backlog item 101's | `git status`, and the two gate runs above |
| F6 | **`error_text` (`tests/unit/_session_route_helpers.py:368`) matches an attribute-free `<div class="alert alert-error">`, so it has been blind to `templates/upload.html`'s error box since before `19fe831`** — that template already carried `style="white-space: pre-line"`. Twenty tests in four files depend on it. A helper that silently returns `None` when a page it does not recognise is handed to it turns a missing error box and an unreadable one into the same result. Worth a `tests/` finding of its own: the helper should **assert** that the box is on the page and fail loudly, not return `None` | `c19_errorbox.py` output above; `templates/upload.html:11` at `19fe831` |
| F8 | **The repository's only session-file fixture cannot see backlog item 87.** Its six derived ratios are 30.0%, 20.0%, 3.0%, 7.0%, 1.5% and 100.0% — each already exact to one decimal place — so at `19fe831` the web and the CLI agree on it (`1243.176933388447`, `delta = 0.0`). A regression test for this unit built on that fixture would be green before the fix and after it. **The fixture needs one ratio that does not round**, as the hand-built filing in this entry has | `c12_cli_e2e.py $BEFORE` against `c1_price.py $BEFORE` |
| F9 | **`api/routes_valuation.py:640`: `revenue_growth_rates=rev_growth_list if rev_growth_list else []`.** Both branches are the same empty list, so the conditional does nothing. Pre-existing, not on the backlog, and the census grep does not match it (it matches `else 0`, not `else []`). Cosmetic — no number moves — but it is the shape of the defect rule 3 names, sitting three lines above five sites this unit removed | `api/routes_valuation.py:640` |
| F7 | **A new, unassigned backlog candidate: the "Derived Default" column and the placeholder both show one decimal place, and the result page shows the derived ratio at one decimal place too** (`4.3%` for `0.04253700000000001`). So a reader who wants to reproduce the share price by hand cannot read the ratio that produced it from any page. Rule 4. Out of this unit's remit — step 3 says keep the column as it is — but the chain is not walkable to the figure that was used | `c9_render.py $AFTER`, the "Assumption Provenance" block |
