---
agent: programmer
assignment: P14a-units
round: 1
status: complete
files_touched: [ingestion/claude_extractor.py, ingestion/session_extraction.py, models/financial_statements.py, cli.py, templates/_statements.html, docs/3-architecture/extraction.md, docs/2-rules/llm-boundary.md, docs/4-conventions/units-and-signs.md, docs/3-architecture/data-contract.md]
verdict:
---

# P14a-units — read the printed unit statements, check them on their pages, convert to millions once

Base commit `99f8b1d`. Opened 2026-10-04T0951 before the first command. No commit, no
paid API call, `extractions/WMT.json` and `.claude/` untouched, `tests/` untouched.

## What I did

Pass 1 now returns two printed unit statements, each `{"printed", "page"}`: `units`
(money) and `share_units` (diluted share count). Python reads the scale word in each
(`claude_extractor.printed_scale`), the page check confirms each text on its page
(a statement not confirmed stops the run: route A after its last retry, route B at
once), and `convert_filing_to_millions` converts each filing's statements and Pass 2
items to millions once, after that filing's Pass 2 and before any merge, in both
routes. `BalanceSheet` carries `printed_unit_in_millions` (required, no default; the
parser states `None`, the conversion sets it), so the balance check stays at 1 printed
unit in the parser, the CLI and the page. The session format is `session-extraction-v3`
(v2 refused with the remedy), and the CLI cache marker is `p14a-units-in-millions-v1`.
Four docs updated.

| Step | Where |
|---|---|
| 1 schema | `_FINANCIALS_SCHEMA["units"]`, `["share_units"]` objects; `diluted_shares` description ("as printed. Its unit is the one 'share_units' states"); the prompt line now "Copy every figure as printed ... NEVER convert"; `currency` unchanged |
| 2 scale | `printed_scale(printed, unit_of) -> PrintedScale`; `_SCALE_IN_MILLIONS` (word -> `Fraction`, a table of numbers); problems join `pass1_problems`, so they are `Pass1ShapeError` in both routes |
| 3 page check | `unit_statement_on_page` (pure), `_unit_statement_failures` (route A, in the retry loop; stops after the last retry), `unit_statement_page_failures` (route B wrapper), `session_extraction._unit_statement_problems` (in `_filing_problems`, so the loader stops and `check` exits 2) |
| 4 conversion | `convert_filing_to_millions(financials, non_recurring, units)`; `filing_units(json_str)`; route A `_run_financials_pass` now returns `(financials, FilingUnits)` and `extract_financials` converts after `_run_nri_pass`; route B converts per filing in `load_session_extraction` before the merge / one-filing return |
| 5 balance check | `printed_unit_in_millions: float \| None = field(kw_only=True)`; `printed_total_status` (module function, printed units, used by the parser); `printed_total_check`, `printed_total_tolerance`, `printed_unit`, `printed_unit_decimals` instance methods (stop on `None`); CLI and template header print `FAIL above <t> $M: 1 in the filing's printed unit, and 1 printed unit = <u> $M` |
| 6 session file | `SESSION_FORMAT = "session-extraction-v3"`; `_SESSION_FORMAT_V2` refused by name with the remedy; v1 refusal kept; `SessionFiling.units`; `check` prints both statements and their scales |
| 7 cache | `CACHE_FORMAT = "p14a-units-in-millions-v1"` |
| 8 docs | the four named files |

## Done-criteria

Scripts are in `scratchpad/p14a_programmer/`; every run on the isolated `new/` tree
(`git archive 99f8b1d` + this unit's files via `sync.sh`), `PYTHONDONTWRITEBYTECODE=1`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | each required case gives its scale or its stop | pass (scale function; `parse_pass1` rows below) | `c1.py`: rows 1-5 give millions/millions, millions/millions, thousands/thousands, millions/thousands, millions/millions; row 6 money millions, share count STOP "it excepts the share count from its scale ('except share and per share data')"; row 7 both STOP "holds no scale word". Also checked: `(IN BILLIONS)` -> billions; `(In millions, except shares)` share STOP; `(Shares in thousands)` money STOP; `(in millions of dollars, except per share data)` share STOP; `(Dollars in millions and shares in thousands)` millions / thousands |
| 1b | the stop rows through `parse_pass1` | pass | `c1b.py` on the Walmart v3 Pass 1 with its unit keys replaced: row 6 (`share_units` = `(in millions, except share and per share data)`) -> `Pass1ShapeError: 'pass1.share_units' '(in millions, except share and per share data)' (page 21): the scale of the share count cannot be read: it excepts the share count ...`; row 7 (`(in dollars)` both) -> two problems, `'pass1.units' '(in dollars)' (page 21) ... holds no scale word` and the same for `share_units`; the row 6 text as `units` with Walmart's `share_units` parses (revenue 713163.0); the v2 shape (`"units": "Millions"`, no `share_units`) -> two problems naming both keys |
| 2 | a filing in millions does not move | pass | `dump_session.py` + `cmp.py`: base tree on `extractions/WMT.json` (v2) vs new tree on `WMT_v3.json`: 137 leaf values compared (income, balance, cash flow, NRI, validation errors, ticker), 0 differ in value or type; the only addition `balance[0].printed_unit_in_millions = 1.0` |
| 3 | a filing in thousands is converted once | pass | `c3_c4.py` (`handbuilt.py` drivers), units `(in thousands, except per share data)` p29 of the Chipotle 2025 10-K. Route A (`extract_financials`, `_call_llm` and `resolve_provider` stubbed): revenue `11313.853`, diluted shares `1370.0`, Pass 2 amount `5.0`, `printed_unit_in_millions` `0.001`. Route B (`load_session_extraction` on a v3 session file): identical |
| 4 | money and shares on two scales | pass | `c3_c4.py`, Okta 2026 10-K p58 `(dollars in millions, shares in thousands, except per share data)`: revenue `2610.0`, diluted shares `180.0`, by route A and route B |
| 5 | a unit statement not on its page stops | pass | `c5.py`, Chipotle PDF, `units` citing p31 (the statement is on 28, 29, 44, 45, 48). Route B: `ValueError ... 'units' (the unit of the money figures): the statement '(in thousands, except per share data)' was not found on page 31, the page it cites ...`; `check` exits 2 with the same line; `share_units` on p31 names `share_units`. Route A: 3 Pass 1 calls (first + 2 retries), then `ValueError Pass 1: after 2 retries, 1 printed unit statement(s) are still not confirmed ...` with the same message; a reply fixed at the retry proceeds (revenue 11313.853) |
| 6 | the real statements pass the page check | pass | `c6.py`: Walmart p21, AbbVie p21, Chipotle p29, Okta p58, L3Harris p35 (2026), p41 (2025), p28 (2023) all `found=True`; the statement is not found on the next page (control) |
| 7 | the balance check stays at 1 printed unit | pass | `c7.py` on the converted thousands balance sheet (assets printed 1,000,000.5 vs mapped 1,000,000; L+E printed 1,000,002 vs 1,000,000): parser (as printed) OK / FAIL; model `printed_total_check` on 0.0005 -> OK, on 0.002 -> FAIL, `printed_total_tolerance()` 0.001; CLI `FAIL above 0.001 $M: 1 in the filing's printed unit, and 1 printed unit = 0.001 $M`, rows OK / FAIL; page (TestClient GET /assumptions, 200) header `FAIL above 0.001 $M: 1 in the filing's printed unit, and 1 printed unit = 0.001 $M`, rows OK / FAIL. `boundary.py`: a gap of exactly 1 printed unit, 20,000 random values: OK 20,000 with the rounding guard; **without it OK 5,706 / FAIL 14,294** |
| 8 | a v2 session file stops with the remedy | pass | `load_session_extraction('extractions/WMT.json')` -> `ValueError ... format is 'session-extraction-v2' ... 'units' is now the statement ... with its page ... 'share_units' is new ... Remedy: run the extract-filing skill again, or add the two keys ...` |
| 9 | an old pickle is refused | pass | `c9_write.py` on the BASE tree wrote a cache with marker `p11a-printed-lines-v1` (Walmart, real key); `c9_read.py` ran the NEW `cli.py 2026:<Walmart PDF> -t WMT --cache-dir cache9` (socket guarded): `ERROR: ... is not a cache entry written by this CLI (expected format marker 'p14a-units-in-millions-v1') ...`, exit 1, network attempts `[]` |
| 10 | Walmart end to end does not move | pass | `run_cli_guarded.py` (`_call_llm` replaced by a refusal): base tree `--session-file extractions/WMT.json` vs new tree `--session-file WMT_v3.json`, both exit 0; `diff` shows only (a) the session file's name and path, (b) the new `Unit statements looked up ... 2 checked, 2 found` line, (c) the new `Units: money '(Amounts in millions, except per share data)' (page 21) -> millions ...` line, (d) the balance check header, reworded by step 5 (`FAIL above 1 $M: 1 in the filing's printed unit, and 1 printed unit = 1 $M`). Every figure of stages 1-10 identical: revenue 680,985 present in both, PV of terminal value 214,819 in both (one later run of the new tree printed 214,820: item 70, see below), implied share price $28.02 in both |
| 11 | no paid API call | pass | `handbuilt.py` replaces `socket.socket.connect` with a refusal that records the address; every route A run stubs `_call_llm` and `resolve_provider`. `network attempts: []` after c3/c4, c5 and c7 |
| 12 | the suite fails only where expected | pass (every red test named below, with its reason) | `final.sh` on the isolated tree: full suite **254 failed, 605 passed** (base: 2 failed, 857 passed); gate form **252 failed, 605 passed** (base 857 passed). The 252 + 2 split into five groups, each traced to a cause (see "Red tests"); the base's two known reds are among the 254 |
| 13 | the gates do not get worse | pass | isolated tree: ruff **4** (the same four BLE001 sites as base, `diff` of the line-stripped lists empty); mypy (exact gate command) **9 errors in 4 files**, the same nine as base (`diff` empty); census **65**; `TestClient(...).get('/')` **200** |

All of 1-13 were re-run together by `final.sh` on the final code (after the last edit
to `printed_scale`); every number above is from that run, except criterion 10's PV of
the terminal value: `final.sh`'s run printed **214,820** where the base printed
214,819 — item 70's flip. Three further runs of each tree, back to back, all printed
214,819 (new) and 214,819 (base). The implied price was $28.02 in every run.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| `printed_unit_in_millions` is keyword-only and **required with no default**; the parser passes `None` explicitly | Step 5: "Do not give that field a default that assumes millions (rule 3)" and "set by the conversion". The parser's figures are still as printed, so no value in millions is true for them yet | A `None` default would let a `BalanceSheet` built anywhere skip the field silently; a value set by the parser (the money scale) would be wrong for the unconverted figures it sits beside. Explicit `None` + a stop in every reader (`printed_unit()`) is the `printed_total_*` / NCI convention already in `models/` |
| `printed_total_check` became an instance method; a module function `printed_total_status(difference_in_printed_units)` holds the one rule | The parser checks figures as printed (threshold 1 in its own units), the CLI and page check converted ones (1 printed unit in $M). One rule, two inputs | The template line `bs.printed_total_check(difference)` (outside my template scope, `:353`) keeps working unchanged as an instance call |
| A difference is rounded to `PRINTED_UNIT_DECIMALS = 6` places of a printed unit before the comparison | `boundary.py`: a gap of exactly 1 printed unit in a thousands filing, after the conversion, FAILED 14,294 of 20,000 random cases without it (0.001 has no exact binary form) while the parser, in printed units, says OK. With it, 20,000 OK; gaps of 2: 20,000 FAIL either way | The parser, the CLI and the page must agree (step 5). The constant decides no figure, only whether 1.00000001 printed units reads as 1; documented in `models/`, `data-contract.md`, `units-and-signs.md` and `extraction.md`. **For the reviewer**: it is a numeric guard, not a financial assumption; if it is judged a rule 6 assumption it needs a label on the page |
| Scale table `_SCALE_IN_MILLIONS` maps to `Fraction`; `_in_millions` divides by the denominator or multiplies by the numerator, one operation | Step 4: "divide by 1,000 for thousands, multiply by 1,000 for billions ... a multiplication by 0.001 is not [correctly rounded]" | `11313853 / 1000 == 11313.853` exactly (criterion 3). Millions multiply by 1, exact, so Walmart's 137 values are identical (criterion 2) |
| How `printed_scale` reads a statement: cut at `,;()`; `except` (whole word) starts the exception list, which continues through later pieces with no scale word; each `in <scale>` clause's subject is the words before it (plus an `of <word>` just after it); subject naming dollars/`$` -> money, naming shares -> shares, empty or only `amounts/amount/all/and` -> both; a named subject wins; an exception mentioning shares (after removing "per share") stops the share scale; two different scales for one kind, or a scale word inside the exception, stop | Step 2's table, row by row, and the forms measured in all 16 filings (`scan_units.py`) | The conservative choice everywhere a reading is not certain: `($ in millions)` gives no share scale, `(Shares in thousands)` no money scale, `(options in thousands, aggregate intrinsic value in millions)` neither. A stop is cheap (the session copies other words); a wrong scale is a factor of 1,000 |
| Unit problems are part of `pass1_problems` | Step 2: "A stop is a `Pass1ShapeError` problem (both routes already report those)" | Route A's shape retry therefore asks the model again (its prompt now describes `units`/`share_units`); route B lists them with every other Pass 1 problem |
| The page check matches the statement's normalised words as **whole words** in the normalised text of the **whole page** | Step 3: use `_read_cited_pages` and `_normalised_text`. L3Harris prints the statement on the column-heading line (`(In millions, except per share amounts) 2025 2024 2023`), and a long statement can wrap | Whole page, because a statement is not a figure row; whole words (space-padded), so `(in millions)` is not found inside `within millions`. Controls: none of the five real statements is found on the next page (`c6.py`) |
| Route A: a unit failure joins the other failed checks for the retry; after the last retry it raises `ValueError` naming the field, the text and the page | Step 3 | `ValueError`, not `Pass1ShapeError`: the shape was fine; the check failed. Every caller that stops on a bad answer stops on a `ValueError` |
| Route B: the unit page check runs in `_filing_problems` (only when Pass 1's shape is usable) | Step 3: "the loader stops and `check` lists it" | In the problem phase the stop is listed with every other problem and `check` exits 2; after it, it would be a second, separate stop |
| `_run_financials_pass` returns `(financials, FilingUnits)`; its unreachable fall-through now raises `AssertionError` | `extract_financials` needs the accepted answer's unit statements after Pass 2 | The old fall-through `return financials` was unreachable (every last-attempt branch returns or raises) and could not return the units |
| `SessionFiling` gains a required `units: FilingUnits`; `check` prints both statements and the scale read | Rule 4: the conversion is a step a reader must be able to walk back | No test constructs `SessionFiling` (grep), so no extra red |
| The conversion prints one line (`Units: money '...' (page 21) -> millions; share count ... Converted to millions.`) in both routes | Rule 4/6: the console says which scale moved the figures | It is the second of the two new lines in the Walmart CLI diff (criterion 10) |
| The conversion stops on a statement field it does not list (`_require_every_field_converted`) and on a balance sheet already converted | Rule 3: a new model field would otherwise reach the valuation unconverted, and a second call would divide again | Measured by `rule3.py` |
| `replace(...)` with every field named, not `BalanceSheet(...)` rebuilt | A rebuilt dataclass with a forgotten keyword gets the field's `0.0` default silently; `replace` keeps the printed value, and the field-coverage guard catches it | — |
| `_run_nri_pass`'s console line no longer says `M` (`{amount:,.0f} (as printed)`) | Its amounts are as printed until the conversion | A thousands filing would have printed `5,000M` |
| CLI balance check: the call is `BalanceSheet.printed_total_check(bs, difference)` | My `cli.py` scope is `CACHE_FORMAT` and the balance check print only; `bs.printed_total_check(...)` would leave the `BalanceSheet` import unused (ruff F401), and that import line is outside my scope | Behaviour is the instance method's. The orchestrator may prefer `bs.` plus deleting the import in a later unit |
| CLI prints printed / mapped / diff to `printed_unit_decimals()` places (0 for millions, 3 for thousands) | A gap of 0.002 $M printed as `+0` beside `FAIL` cannot be checked by a reader (step 5, "in words a reader can check") | Millions stay at 0 decimals, so Walmart's CLI rows are byte-identical |
| Template: only the header (`:333-345`) changed; it prints `FAIL above {tolerance:g} $M: {tolerance/unit:g} in the filing's printed unit, and 1 printed unit = {unit:g} $M` | Scope; the "1" is derived from the two methods, not typed | The value cells (`:347-358`, `{:,.0f}`) are out of scope: see Findings |
| `UnitOf = Literal["money figures", "share count"]` | The messages read "the unit of the money figures", "the unit of the share count" | — |
| The L3Harris statement: found, and covered | Objective: "Find it, or report that it is printed in a form step 2 does not cover" | See Measurements: `(In millions, except per share amounts)` on the `CONSOLIDATED STATEMENT OF OPERATIONS` page, same text line as the years |

**No code was changed to reach a target number.** The Walmart figures were compared,
not aimed at.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `pass1.units`, `pass1.share_units` | stop, `Pass1ShapeError`: `key 'pass1.share_units' is absent ...`; a string (v2 shape) -> `must be a JSON object` | `c1b.py`, v2-shape row |
| `units.printed`, `.page` | stop, naming `'pass1.<key>': key 'printed' is absent`, an empty string, a page below 1 or not an integer | `_unit_statement_problems` (claude_extractor.py); same shape rules as a printed line |
| the scale word in `units` | stop: `holds no scale word ... that states the unit of the money figures` | `c1.py` row 7, `c1b.py` row 7 |
| the scale word for the share count | stop: no share/generic clause, or the exception excepts shares | `c1.py` row 6, `(In millions, except shares)`, `($ in millions)`; `c1b.py` row 6 |
| the unit statement on its page | not found / page beyond the PDF / no text layer: route A retried then `ValueError`; route B loader stops, `check` exit 2 | `c5.py`; `rule3.py` (page 999: `cites page 999, but the PDF has 60 pages`) |
| the PDF for the unit check | `pdfplumber` cannot open it: `ValueError` naming the PDF by sha256 (existing `_read_cited_pages`); route B adds the filing | unchanged `P12a` path |
| `BalanceSheet.printed_unit_in_millions` | no default: `BalanceSheet(year=2024)` -> `TypeError ... missing 1 required keyword-only argument`; `None` -> `printed_unit()`, `printed_total_check`, `printed_total_tolerance`, `printed_unit_decimals` all `ValueError ... 'printed_unit_in_millions' is None` | `rule3.py` |
| a statement field the conversion does not list | stop naming class and field | `rule3.py` (`dividends_paid` removed from the list -> `CashFlowStatement has field(s) ['dividends_paid'] ...`) |
| a balance sheet already converted | stop | `rule3.py` (`the balance sheet(s) [2024] of 'HAND' already carry printed_unit_in_millions ...`) |
| `_SCALE_IN_MILLIONS[word]` | `word` is the regex group `thousands\|millions\|billions`, so every key exists | `_SCALE_CLAUSE` |

No "defaults to" row. The one reading that is an interpretation rather than a stop: a
clause with no subject (or only "amounts") states the share count's scale too, as step
2's table requires (`(In millions)` -> millions, millions).

## Measurements

### Base gates, on an isolated `git archive 99f8b1d` tree (`scratchpad/p14a_programmer/base`, `10K_filings` symlinked)

| Gate | Result at `99f8b1d` |
|---|---|
| full suite | 2 failed, 857 passed: the two `*_rule3_red.py` cases |
| ruff | 4 errors (BLE001) |
| mypy (exact gate command) | 9 errors in 4 files |
| census (`'--include=*.py'`) | 65 |

Agrees with the assignment's table (measured at `0a5a715`) and STATUS (`bc30be4`).

### The printed unit statements in all 16 filings (`scratchpad/p14a_programmer/scan_units.py`, pdfplumber, every parenthesised text holding a scale word)

The four in the Objective's table are where the assignment says: Walmart 2026 p21
`(Amounts in millions, except per share data)` (also 19, 27, 28); AbbVie 2025 p21
`(in millions, except per share data)`; Chipotle 2025 p29 `(in thousands, except per
share data)` (also 28); Okta 2026 p58 `(dollars in millions, shares in thousands,
except per share data)` (also 57, 82).

**L3Harris (found).** Its income statement is titled `CONSOLIDATED STATEMENT OF
OPERATIONS`, not "of Income", and the unit statement is printed on the same text line
as the column headings: `(In millions, except per share amounts) 2025 2024 2023`.
10-K 2026-01-02 page 35; 10-K 2025-01-03 page 41; 10-K 2023-12-29 page 28. Its balance
sheet prints `(In millions, except shares)` (2026 p36, 2025 p43, 2023 p29). Step 2's
reading covers the income statement form (money millions, shares millions: "per share
amounts" excepts only per-share figures). The balance sheet form excepts the share
count, so cited as `share_units` it stops — correctly.

Other forms seen, for the reader: `(in millions, except share data)` (AbbVie balance
sheet), `(dollar and share amounts in thousands, unless otherwise specified)` (Chipotle
notes), `(options in thousands, aggregate intrinsic value in millions)` (AbbVie),
`(Shares in thousands)` (Walmart), `($ in millions)` (L3Harris).

### After, on the isolated new tree (`final.sh`, final code)

| Gate | Base `99f8b1d` | This unit |
|---|---|---|
| full suite | 2 failed, 857 passed | **254 failed, 605 passed** (groups below) |
| gate form | 857 passed | **252 failed, 605 passed** |
| ruff | 4 (BLE001) | 4, the same four sites |
| mypy (exact command) | 9 in 4 files | 9 in 4 files, the same nine |
| census | 65 | 65 |
| route `GET /` | — | 200 |

Pass 2's prompt is built from the figures as printed, in both routes
(`pass2prompt.py`, and `session_extraction prompt --pass 2` on the thousands session
file): `FY2024: Revenue=11,313,853 ...`; the result after conversion is 11313.853.
`session_extraction plan` writes `"format": "session-extraction-v3"`, and `prompt
--pass 1` prints the new `units` / `share_units` schema and the "Copy every figure as
printed ... NEVER convert" rule through the shared prompt.

Figures this unit moved: none for a filing in millions (criterion 2, 137 values
identical; criterion 10, Walmart $28.02). A filing in thousands now reaches the
valuation divided by 1,000 (criterion 3), where before it reached it as printed.

### Red tests — 254 on the full suite (base: 2), 252 in the gate form

Measured on the isolated tree (`final.sh`; `f_suite.txt`). Each group's cause was
confirmed by execution, not by reading the message alone: `probe/` (a scratch copy of
the new tree with the new field given a default of 1.0, **not a deliverable**) leaves
exactly the 130 of groups B, E, V and K red, so the other 124 are caused by the
required field alone; each of the 40 tests whose summary line did not name the cause
was re-run with a full traceback and its cause read there.

| Group | Count | Reason | What the tester changes |
|---|---|---|---|
| A | 124 | `BalanceSheet(...)` built without `printed_unit_in_millions` -> `TypeError: BalanceSheet.__init__() missing 1 required keyword-only argument` (117 directly; 7 route tests where a fake extractor builds one and the route renders the error page: 6 in `test_routes.py`, 1 in `test_route_context_keys.py`) | add `printed_unit_in_millions=<the unit>` to each construction (1.0 where the fixture is in millions) |
| B | 121 | a Pass 1 fixture or a session file lacks the two unit statements (`"units": "Millions"`, no `share_units`) or is written as `session-extraction-v2` -> `Pass1ShapeError` naming `pass1.units` / `pass1.share_units`, or the loader stops ("the session file cannot be used"); downstream of that, scripted `_call_llm` stubs run out ("call 3 was not scripted"), `check` exits 2 instead of 0/1, and route-level session tests render the stop | give each fixture `units` and `share_units` `{printed, page}` (a statement actually printed on the cited page of the PDF the test uses, since the page check now runs on it) and `format` `session-extraction-v3`; the shared helpers are `tests/unit/_session_route_helpers.py` and the fixtures in `test_page_check.py`, `test_pass1_printed_lines.py`, `test_claude_extractor.py`, `test_session_extraction.py` |
| E | 6 | the tests call `BalanceSheet.printed_total_tolerance()` on the class; it is an instance method now (the threshold depends on the sheet's printed unit) | call it on a converted `BalanceSheet`; the static rule is `printed_total_status(difference_in_printed_units)` |
| V | 1 | `test_a_v1_session_file_stops_naming_both_formats` asserts the v1 refusal names `'session-extraction-v2'` as the current format; the current format is v3 (step 6) | expect `'session-extraction-v3'` |
| K | 2 | the two known reds. `test_projector_rule3_red.py` unchanged. `test_routes_session_rule3_red.py` is still red, **but now stops earlier**, at the loader (its session fixture lacks the unit statements), not at its own assertion (`:74`) | after the fixture is repaired it should again fail at `:74` (item 52); check that it does |

Tests by name, by group and file:

### Group A: 124 tests
- `tests/unit/test_claude_extractor.py` (1): `test_merge_prefers_the_filing_whose_fiscal_year_is_the_statement_year`
- `tests/unit/test_dcf.py` (37): `test_run_dcf_worked_example`, `test_run_dcf_flat_perpetuity_identity[1]`, `test_run_dcf_flat_perpetuity_identity[2]`, `test_run_dcf_flat_perpetuity_identity[3]`, `test_run_dcf_flat_perpetuity_identity[4]`, `test_run_dcf_flat_perpetuity_identity[5]`, `test_run_dcf_raises_when_terminal_growth_is_not_below_wacc`, `test_run_dcf_stops_when_there_are_no_projected_cash_flows`, `test_run_dcf_bridge_subtracts_net_debt_and_both_noncontrolling_interests`, `test_total_noncontrolling_interest_is_the_sum_of_the_two_printed_parts[40.0-10.0-50.0]`, `test_total_noncontrolling_interest_is_the_sum_of_the_two_printed_parts[6270.0-293.0-6563.0]`, `test_total_noncontrolling_interest_is_the_sum_of_the_two_printed_parts[0.0-0.0-0.0]`, `test_total_noncontrolling_interest_is_the_sum_of_the_two_printed_parts[0.0-25.0-25.0]`, `test_total_noncontrolling_interest_stops_naming_the_key_and_the_year[None-noncontrolling_interest_nonredeemable]`, `test_total_noncontrolling_interest_stops_naming_the_key_and_the_year[None-noncontrolling_interest_redeemable]`, `test_total_noncontrolling_interest_stops_naming_the_key_and_the_year[NaN-noncontrolling_interest_nonredeemable]`, `test_total_noncontrolling_interest_stops_naming_the_key_and_the_year[NaN-noncontrolling_interest_redeemable]`, `test_total_noncontrolling_interest_stops_when_neither_part_was_set`, `test_run_dcf_stops_when_a_noncontrolling_interest_was_not_extracted[noncontrolling_interest_nonredeemable]`, `test_run_dcf_stops_when_a_noncontrolling_interest_was_not_extracted[noncontrolling_interest_redeemable]`, `test_neither_nci_part_enters_any_balance_sheet_total[not-extracted]`, `test_neither_nci_part_enters_any_balance_sheet_total[zeros]`, `test_neither_nci_part_enters_any_balance_sheet_total[seven-and-three]`, `test_run_dcf_stops_on_no_share_count_and_names_it[zero]`, `test_run_dcf_stops_on_no_share_count_and_names_it[integer-zero]`, `test_run_dcf_stops_on_no_share_count_and_names_it[negative]`, `test_run_dcf_stops_on_no_share_count_and_names_it[nan]`, `test_run_dcf_stops_on_no_share_count_and_names_it[inf]`, `test_run_dcf_stops_on_no_share_count_and_names_it[minus-inf]`, `test_run_dcf_positive_share_count_gives_the_bridge_price_by_hand`, `test_run_dcf_stops_on_no_current_price_and_names_it[zero]`, `test_run_dcf_stops_on_no_current_price_and_names_it[integer-zero]`, `test_run_dcf_stops_on_no_current_price_and_names_it[negative]`, `test_run_dcf_stops_on_no_current_price_and_names_it[nan]`, `test_run_dcf_stops_on_no_current_price_and_names_it[inf]`, `test_run_dcf_stops_on_no_current_price_and_names_it[minus-inf]`, `test_run_dcf_positive_current_price_gives_the_upside_by_hand`
- `tests/unit/test_models_stops.py` (1): `test_latest_year_ignores_balance_sheets_when_there_is_no_income_statement`
- `tests/unit/test_normalizer.py` (1): `test_normalize_financials_leaves_the_other_statements_alone`
- `tests/unit/test_normalizer_year_stop.py` (1): `test_a_balance_sheet_year_does_not_count_as_a_statement_year`
- `tests/unit/test_route_context_keys.py` (3): `test_get_assumptions_success_sets_all_six_keys_and_both_sides_of_the_adjustment`, `test_post_valuation_success_sets_all_six_keys`, `test_the_cached_extraction_carries_all_four_fields_to_the_result_page`
- `tests/unit/test_routes.py` (7): `test_get_assumptions_puts_the_derived_defaults_into_the_form`, `test_get_assumptions_reads_two_filings_with_the_multi_year_extractor`, `test_post_valuation_renders_the_completed_valuation`, `test_post_valuation_shows_and_subtracts_the_noncontrolling_interests`, `test_post_valuation_names_who_read_the_filing`, `test_post_valuation_distinguishes_the_two_transports`, `test_post_valuation_reports_a_failure_on_a_rendered_page`
- `tests/unit/test_statements_ui.py` (14): `test_balance_check_difference_property_hand_computed`, `test_get_assumptions_renders_seven_blocks_and_open_details`, `test_post_valuation_renders_seven_blocks_closed_details_and_order`, `test_applied_items_table_filters_confidence_hand_computed`, `test_ebit_reconciliation_delta_matches_hand_arithmetic`, `test_assumption_sources_rendered_verbatim`, `test_missing_cash_flow_statement_renders_not_extracted_and_no_zeros`, `test_missing_balance_sheet_renders_not_extracted`, `test_substituted_ratio_badges_and_provenance`, `test_empty_applied_items_renders_explanatory_sentence`, `test_unadjusted_reconciliation_renders_explanatory_sentence`, `test_balance_sheet_table_renders_difference_and_metrics_hand_computed`, `test_implied_share_price_unchanged_on_baseline_stub`, `test_money_headers_and_sign_conventions`
- `tests/unit/test_wacc.py` (59): `test_cost_of_debt_is_interest_over_total_debt`, `test_cost_of_debt_is_the_same_for_either_interest_sign`, `test_cost_of_debt_override_replaces_the_derived_rate`, `test_wacc_worked_example`, `test_the_weights_sum_to_one`, `test_wacc_with_no_debt_equals_the_cost_of_equity_whatever_the_cost_of_debt`, `test_a_debt_free_company_prices_at_its_cost_of_equity`, `test_wacc_at_a_zero_tax_rate_is_the_plain_weighted_average`, `test_the_tax_shield_only_reduces_the_debt_term`, `test_weights_are_still_the_reported_ones_when_interest_is_not_reported`, `test_cost_of_equity_passes_through_unchanged_where_the_weights_can_be_formed`, `test_weights_that_cannot_be_formed_stop_and_name_market_cap[zero-market-cap-and-zero-debt]`, `test_weights_that_cannot_be_formed_stop_and_name_market_cap[sum-is-zero]`, `test_weights_that_cannot_be_formed_stop_and_name_market_cap[zero-market-cap-beside-debt]`, `test_weights_that_cannot_be_formed_stop_and_name_market_cap[negative-market-cap-beside-debt]`, `test_a_zero_sum_also_names_the_debt_balance_and_its_value[zero-market-cap-and-zero-debt]`, `test_a_zero_sum_also_names_the_debt_balance_and_its_value[sum-is-zero]`, `test_the_weights_stop_does_not_state_a_cause[zero-market-cap-and-zero-debt]`, `test_the_weights_stop_does_not_state_a_cause[sum-is-zero]`, `test_the_weights_stop_does_not_state_a_cause[zero-market-cap-beside-debt]`, `test_the_weights_stop_does_not_state_a_cause[negative-market-cap-beside-debt]`, `test_a_positive_market_cap_and_debt_form_the_weights_by_hand`, `test_the_same_company_with_a_supplied_cost_of_debt_keeps_its_weights`, `test_a_zero_debt_balance_beside_a_reported_interest_expense_stops`, `test_the_contradiction_stop_is_not_bypassed_by_a_negative_interest_sign`, `test_the_contradiction_stops_calculate_wacc_too`, `test_a_genuinely_debt_free_company_measures_zero_and_the_label_says_so`, `test_the_debt_free_label_is_not_the_substituted_one`, `test_a_nan_cost_of_equity_stops_and_names_the_capm_result`, `test_a_nan_cost_of_debt_override_stops_and_names_the_cost_of_debt`, `test_a_nan_tax_rate_stops_before_the_clamp_flattens_it_to_zero`, `test_a_nan_market_cap_stops_and_names_the_market_cap`, `test_a_nan_total_debt_stops_and_names_the_balance_sheet_field`, `test_a_negative_total_debt_stops_and_names_the_total_and_its_value[no-override]`, `test_a_negative_total_debt_stops_and_names_the_total_and_its_value[override-0.05]`, `test_a_negative_total_debt_stops_the_cost_of_debt_on_a_direct_call`, `test_a_negative_debt_line_under_a_positive_total_stops_and_names_the_line[short-term-minus-50-no-override]`, `test_a_negative_debt_line_under_a_positive_total_stops_and_names_the_line[short-term-minus-50-override-0.05]`, `test_a_negative_debt_line_under_a_positive_total_stops_and_names_the_line[current-portion-minus-10-no-override]`, `test_a_negative_debt_line_under_a_positive_total_stops_and_names_the_line[current-portion-minus-10-override-0.05]`, `test_a_negative_debt_line_under_a_positive_total_stops_and_names_the_line[long-term-minus-50-no-override]`, `test_a_negative_debt_line_under_a_positive_total_stops_and_names_the_line[long-term-minus-50-override-0.05]`, `test_an_infinite_debt_line_stops_and_names_the_line[short_term_debt-no-override]`, `test_an_infinite_debt_line_stops_and_names_the_line[short_term_debt-override-0.05]`, `test_an_infinite_debt_line_stops_and_names_the_line[current_portion_lt_debt-no-override]`, `test_an_infinite_debt_line_stops_and_names_the_line[current_portion_lt_debt-override-0.05]`, `test_an_infinite_debt_line_stops_and_names_the_line[long_term_debt-no-override]`, `test_an_infinite_debt_line_stops_and_names_the_line[long_term_debt-override-0.05]`, `test_a_negative_infinite_debt_line_stops_and_names_the_line`, `test_finite_debt_lines_that_sum_to_infinity_stop_and_name_the_total`, `test_an_infinite_market_cap_stops_and_names_it`, `test_an_infinite_cost_of_equity_stops_and_names_it`, `test_an_infinite_cost_of_debt_override_stops_and_names_it`, `test_an_infinite_tax_override_stops_before_the_clamp[plus-inf]`, `test_an_infinite_tax_override_stops_before_the_clamp[minus-inf]`, `test_a_non_finite_interest_beside_zero_debt_stops_and_names_it[nan]`, `test_a_non_finite_interest_beside_zero_debt_stops_and_names_it[plus-inf]`, `test_a_non_finite_interest_stops_cost_of_debt_with_source_and_names_it[nan]`, `test_a_non_finite_interest_stops_cost_of_debt_with_source_and_names_it[plus-inf]`

### Group E: 6 tests
- `tests/unit/test_pass1_printed_lines.py` (6): `test_the_tolerance_is_the_one_the_code_applies`, `test_a_difference_of_the_tolerance_passes_and_one_more_fails[printed above-exactly the tolerance passes]`, `test_a_difference_of_the_tolerance_passes_and_one_more_fails[printed above-one more fails]`, `test_a_difference_of_the_tolerance_passes_and_one_more_fails[printed below-exactly the tolerance passes]`, `test_a_difference_of_the_tolerance_passes_and_one_more_fails[printed below-one more fails]`, `test_the_cli_balance_check_has_no_two_percent_tolerance`

### Group V: 1 tests
- `tests/unit/test_pass1_printed_lines.py` (1): `test_a_v1_session_file_stops_naming_both_formats`

### Group K: 2 tests
- `tests/unit/test_projector_rule3_red.py` (1): `test_an_extraction_with_no_income_statements_stops_and_names_the_input`
- `tests/unit/test_routes_session_rule3_red.py` (1): `test_valuation_with_session_file_and_files_on_a_cache_hit_stops`

### Group B: 121 tests
- `tests/unit/test_claude_extractor.py` (17): `test_pass1_income_statement_fields_land_on_their_fields`, `test_pass1_ticker_and_name_come_from_the_caller`, `test_pass1_ebit_equals_the_stated_operating_income[D&A inside other_operating_expense-overrides0]`, `test_pass1_ebit_equals_the_stated_operating_income[D&A inside cost_of_revenue-overrides1]`, `test_pass1_ebit_equals_the_stated_operating_income[no D&A reported-overrides2]`, `test_pass1_cash_from_operations_equals_the_stated_cfo`, `test_pass1_capex_is_stored_negative`, `test_pass1_balance_sheet_fields_land_on_their_fields`, `test_pass1_an_absent_nci_key_stops_never_zero[noncontrolling_interest_nonredeemable]`, `test_pass1_an_absent_nci_key_stops_never_zero[noncontrolling_interest_redeemable]`, `test_pass1_explicit_zero_nci_is_kept_as_zero`, `test_pass1_without_a_balance_sheet_gives_none`, `test_pass1_years_are_returned_ascending`, `test_pass1_arithmetic_check_is_clean_when_everything_reconciles`, `test_pass1_arithmetic_check_names_year_and_field_on_a_gross_profit_miss`, `test_pass1_gross_profit_tolerance_is_half_a_percent[602-False]`, `test_pass1_gross_profit_tolerance_is_half_a_percent[604-True]`
- `tests/unit/test_page_check.py` (58): `test_every_row_printed_on_its_page_gives_no_failure`, `test_every_line_field_is_walked[revenue-year 2024]`, `test_every_line_field_is_walked[cost_of_revenue-year 2024]`, `test_every_line_field_is_walked[gross_profit-year 2024]`, `test_every_line_field_is_walked[sga-year 2024]`, `test_every_line_field_is_walked[rd_expense-year 2024]`, `test_every_line_field_is_walked[depreciation_amortization-year 2024]`, `test_every_line_field_is_walked[other_operating_expense-year 2024]`, `test_every_line_field_is_walked[operating_income-year 2024]`, `test_every_line_field_is_walked[interest_expense-year 2024]`, `test_every_line_field_is_walked[interest_income-year 2024]`, `test_every_line_field_is_walked[other_non_operating-year 2024]`, `test_every_line_field_is_walked[tax_expense-year 2024]`, `test_every_line_field_is_walked[net_income-year 2024]`, `test_every_line_field_is_walked[diluted_shares-year 2024]`, `test_every_line_field_is_walked[cfo-year 2024]`, `test_every_line_field_is_walked[capex-year 2024]`, `test_every_line_field_is_walked[sbc-year 2024]`, `test_every_line_field_is_walked[change_in_working_capital-year 2024]`, `test_every_line_field_is_walked[cash-balance sheet 2024]`, `test_every_line_field_is_walked[short_term_investments-balance sheet 2024]`, `test_every_line_field_is_walked[accounts_receivable-balance sheet 2024]`, `test_every_line_field_is_walked[inventory-balance sheet 2024]`, `test_every_line_field_is_walked[other_current_assets-balance sheet 2024]`, `test_every_line_field_is_walked[ppe_net-balance sheet 2024]`, `test_every_line_field_is_walked[goodwill-balance sheet 2024]`, `test_every_line_field_is_walked[intangible_assets-balance sheet 2024]`, `test_every_line_field_is_walked[other_non_current_assets-balance sheet 2024]`, `test_every_line_field_is_walked[accounts_payable-balance sheet 2024]`, `test_every_line_field_is_walked[accrued_liabilities-balance sheet 2024]`, `test_every_line_field_is_walked[other_current_liabilities-balance sheet 2024]`, `test_every_line_field_is_walked[short_term_debt-balance sheet 2024]`, `test_every_line_field_is_walked[long_term_debt-balance sheet 2024]`, `test_every_line_field_is_walked[other_non_current_liabilities-balance sheet 2024]`, `test_every_line_field_is_walked[total_equity-balance sheet 2024]`, `test_every_line_field_is_walked[noncontrolling_interest_nonredeemable-balance sheet 2024]`, `test_every_line_field_is_walked[noncontrolling_interest_redeemable-balance sheet 2024]`, `test_every_line_field_is_walked[total_assets-balance sheet 2024]`, `test_every_line_field_is_walked[total_liabilities_and_equity-balance sheet 2024]`, `test_the_line_index_is_the_rows_own`, `test_every_year_is_walked`, `test_not_found_names_where_field_line_label_value_and_page`, `test_a_page_beyond_the_last_names_both_page_numbers`, `test_a_page_with_no_text_layer_is_a_failure_that_cannot_be_confirmed[no text]`, `test_a_page_with_no_text_layer_is_a_failure_that_cannot_be_confirmed[only spaces]`, `test_a_wrapped_row_is_found_through_a_real_pdf`, `test_each_cited_page_is_read_once`, `test_an_empty_balance_sheet_is_not_walked`, `test_route_b_wrapper_stops_naming_the_pdf_by_sha256`, `test_route_a_stops_naming_the_pdf_by_sha256_and_makes_no_retry`, `test_check_exits_0_when_every_row_is_printed_and_says_so`, `test_check_exits_1_when_the_only_problem_is_a_line_not_found`, `test_check_exits_1_on_a_page_with_no_text_layer`, `test_route_a_a_line_not_found_goes_to_the_check_retry`, `test_route_a_retry_names_label_field_and_page_and_no_value`, `test_route_a_after_the_last_retry_prints_the_failure_and_keeps_the_figures`, `test_the_f7_attack_balances_and_the_page_check_names_the_invented_row`, `test_the_f7_control_the_honest_answer_has_no_failure`
- `tests/unit/test_pass1_printed_lines.py` (28): `test_two_capex_rows_are_summed_and_stored_negative`, `test_summed_rows_feed_the_checks`, `test_a_field_of_two_rows_is_their_sum_by_route_b`, `test_an_empty_catch_all_on_the_income_statement_is_zero`, `test_an_empty_catch_all_on_the_balance_sheet_is_zero`, `test_an_empty_printed_total_is_not_extracted_and_fails[total_assets]`, `test_an_empty_printed_total_is_not_extracted_and_fails[total_liabilities_and_equity]`, `test_an_empty_printed_total_reaches_the_cli_as_not_extracted[total_assets]`, `test_an_empty_printed_total_reaches_the_cli_as_not_extracted[total_liabilities_and_equity]`, `test_empty_gross_profit_and_operating_income_skip_their_checks`, `test_printed_totals_that_agree_pass`, `test_a_row_of_4124_kept_balances`, `test_a_dropped_row_of_4124_fails_names_the_difference_and_keeps_the_figures`, `test_the_shape_retry_sends_the_pdf`, `test_the_check_retry_sends_the_pdf`, `test_the_json_repair_retry_does_not_send_the_pdf`, `test_the_balance_check_retry_states_no_gap_and_no_total`, `test_the_income_statement_check_retry_states_no_gap_and_no_total`, `test_after_the_last_retry_a_failed_check_is_kept`, `test_a_cli_cache_under_the_old_marker_is_refused`, `test_a_cli_cache_under_the_current_marker_loads`, `test_the_cli_session_route_shows_a_failed_check_and_keeps_the_figures`, `test_the_cli_balance_check_says_ok_when_the_totals_agree`, `test_the_cli_balance_check_says_fail_on_a_dropped_row`, `test_the_page_shows_ok_when_the_totals_agree`, `test_the_page_shows_fail_visibly_on_a_dropped_row`, `test_the_page_shows_an_empty_total_as_not_extracted_never_zero[total_assets]`, `test_the_page_shows_an_empty_total_as_not_extracted_never_zero[total_liabilities_and_equity]`
- `tests/unit/test_routes_session.py` (9): `test_upload_then_follow_the_redirect_reaches_the_assumptions_page_with_the_label`, `test_assumptions_from_a_session_file_shows_the_label_and_the_files_identity`, `test_assumptions_with_a_ticker_that_differs_from_the_file_stops_naming_both`, `test_assumptions_with_a_company_name_that_differs_from_the_file_stops_naming_both`, `test_valuation_with_a_ticker_that_differs_from_the_file_stops_before_pricing`, `test_valuation_on_a_cache_hit_shows_the_session_label`, `test_valuation_on_a_cache_miss_shows_the_session_label`, `test_route_a_label_survives_removing_the_key_on_a_cache_hit`, `test_route_a_on_a_cache_miss_with_no_key_stops_on_the_credential`
- `tests/unit/test_session_extraction.py` (9): `test_one_filing_both_routes_give_equal_statements_and_items`, `test_three_filings_both_routes_give_equal_statements_and_items`, `test_a_changed_figure_makes_the_routes_differ`, `test_explicit_zero_is_accepted`, `test_pass2_item_amount_zero_loads`, `test_session_label_names_the_session_route_and_the_declared_model`, `test_check_exit_codes`, `test_prompt_prints_route_a_prompts`, `test_main_check_and_a_bad_page_range`

## What I did not do

- **No test edited** (`tests/` is the tester's). 254 red, listed above with their cause.
- **`extractions/WMT.json` not upgraded** (the orchestrator's, after acceptance). The
  exact transformation is `scratchpad/p14a_programmer/make_wmt_v3.py`: `format` ->
  `session-extraction-v3`; `pass1.units` -> `{"printed": "(Amounts in millions, except
  per share data)", "page": 21}`; `pass1.share_units` the same (page 21 prints it under
  `Consolidated Statements of Income`; the diluted row is on page 22, under the same
  statement). Nothing else changes (the script's diff shows three changes).
- **`.claude/skills/extract-filing/`** not taught the v3 shape (out of scope; the
  orchestrator's). Until it is, a session following the skill writes a v2 file, which
  the loader refuses with the remedy.
- Not fixed, by the assignment: items 10, 61, 51, 73, 74, 53, 60, 64, 72, item 1's sites.
- Item 63 (no text layer): recorded. A filing with no text layer now also **stops** on
  the unit check, in both routes, after route A's retries. None of the 16 filings lacks
  a text layer.

## Findings for the orchestrator

1. **The page's balance check value cells print `{:,.0f}`** (`templates/_statements.html`
   `:347-358`, outside my scope). For a filing in thousands, a gap of 2 printed units
   (0.002 $M) shows as `+0` beside `FAIL`, and printed / mapped `1,000.002` / `1,000.000`
   as `1,000` / `1,000` (`c7.py`). The header now states the threshold and the printed
   unit, so the page is not wrong, but a reader cannot check the gap. A one-unit fix:
   format those three cells with `bs.printed_unit_decimals()` places, as the CLI now does.
2. **The arithmetic check table and route B's failed-check messages are in printed
   units, unlabelled** (`_validate_extracted_data` runs before the conversion). For a
   thousands filing, `check` and the CLI print `printed=11,313,853` beside statements
   shown in $M. They match the page the reader opens, which is useful, but the table
   does not say "as printed, in thousands". A small wording unit in
   `claude_extractor.py`.
3. **Route A's unit stop names the field, the text and the page, but not the PDF**:
   `_run_financials_pass` holds only bytes. `extract_multi_year` prints `EXTRACTING:
   <name>` just before, so the console shows it; the exception text alone does not.
   Same shape as the existing page-check stop, which names the PDF by sha256.
4. **The CLI calls `BalanceSheet.printed_total_check(bs, difference)`** only to keep
   the `BalanceSheet` import used without editing the import block outside my scope.
   `bs.printed_total_check(difference)` and deleting the import is the cleaner form.
5. **`PRINTED_UNIT_DECIMALS = 6`** is a numeric guard (see Decisions). If the reviewer
   classes it as a rule 6 assumption, the page needs to show it.
6. **`docs/3-architecture/extraction.md` "Known defects" still lists `except
   Exception` in `_run_nri_pass`**, which `P13g` closed. Stale; not this unit's.
7. **`test_routes_session_rule3_red.py`** must be checked after the fixture repair: it
   must fail at its own assertion again, or it no longer measures item 52.
8. The schema text is `json.dumps` with `ensure_ascii`, so the prompt shows `—` for
   every em dash, in the old fields and the new. Pre-existing; harmless to a model;
   noted only because the `prompt` output a session reads shows it.
