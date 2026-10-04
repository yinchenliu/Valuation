---
agent: programmer
assignment: P13g-pass2-unread
round: 1
status: complete
files_touched: [ingestion/claude_extractor.py]
verdict:
---

# P13g-pass2-unread — stop when route A cannot read Pass 2, instead of reporting no items

## What I did

In `_run_nri_pass` (`ingestion/claude_extractor.py`), the retry branch's blanket
`except Exception: print(...); return []` is now
`except (ValueError, KeyError, TypeError, AttributeError) as retry_exc: raise ValueError(...) from retry_exc`.
The message names the filing by what the function holds (ticker, company name, and the
fiscal years Pass 1 read, each printed with `repr` so an empty value shows as `''`),
says Pass 2's reply did not parse and the retry's reply did not parse either, and gives
both parse errors with their types. A reply that parses and lists no items still
returns `[]`. Nothing else in the file changed: `git diff` touches only lines inside
`_run_nri_pass`, between the retry `_call_llm` call and the `if nri:` line. Backlog item 50,
and item 8's site in the extractor. Rule 3.

No API call was made. The isolated tree has no `.env`. Every check ran with
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY` and `GOOGLE_API_KEY` removed from the environment,
`_call_llm` replaced by a stub, and `_call_claude`, `_call_gemini`,
`anthropic.Anthropic.__init__`, `socket.socket.connect` and `socket.create_connection` all
replaced by a function that raises. A control showed that guard firing.

## Done-criteria

Every run used the isolated tree
`scratchpad/p13g_programmer/tree` (`git archive 19298f3` plus this unit's one file). The
check script is `scratchpad/p13g_programmer/checks/check_pass2.py`. Its cases run as
`env -u ANTHROPIC_API_KEY -u GEMINI_API_KEY -u GOOGLE_API_KEY PYTHONPATH=<tree> .venv/bin/python check_pass2.py <case>`.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | an unparseable Pass 2 after the retry stops | **pass** | case `c1`: stub returns `{this is not json}` and then `{still not json`. Output: `RAISED ValueError stub calls=2`, `Pass 2 (non-recurring items) could not be read for the filing with ticker 'TEST', company 'Test Co', fiscal years [2023, 2024] read in Pass 1. The model's reply did not parse (JSONDecodeError: Expecting property name ...), and the reply to one retry did not parse either (ValueError: No JSON object found in LLM response. ...). Nothing was read about non-recurring items, ...`, `__cause__: ValueError`. Same script on the 19298f3 export (`scratchpad/p13g_programmer/base`): `[Pass 2 WARN] NRI parsing failed after retry — returning empty list`, `RETURNED []  stub calls=2`. The cases also stop when the retry reply has no `non_recurring_items` (`c1b`, cause ValueError) or an item that is a JSON list (`c1c`, cause AttributeError) |
| 2 | a parseable reply with no items still returns `[]` | **pass** | case `c2`: stub returns `{"non_recurring_items": []}`: `RETURNED []  stub calls=1`. Case `c2b`, malformed and then `{"non_recurring_items": []}`: `RETURNED []  stub calls=2` |
| 3 | no API call was made | **pass** | read `check_pass2.py`: `_call_llm` is replaced by `stub()` before every `_run_nri_pass` call, and every road to a client raises `NetworkReached`, which exits 2. No case exited 2. Control: calling the real `_call_llm` under the guard printed `guard fired: a network connection was attempted`. No `.env` in the tree (`ls -a \| grep -c "^.env$"` gives `0`). No route A, upload, or `cli.py` was run with a PDF |
| 4 | lint falls by one | **pass** | `.venv/bin/python -m ruff check . --no-cache --output-format=concise` gives `Found 4 errors.`, all `BLE001`, at `api/routes_valuation.py:445`, `:703`, `cli.py:1143` and `tests/test_e2e_all_googl.py:106`. The baseline also had `ingestion/claude_extractor.py:1798` |
| 9 | the suite fails only where expected | **pass** | full suite: `2 failed, 793 passed`. The failure set is the same as the baseline, both `*_rule3_red.py`: `test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input` and `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`. Gate form `--ignore-glob="*_rule3_red.py"`: `793 passed`. **No test turned red.** No test reached the old `return []`: `grep -rn "returning empty\|after retry\|_run_nri_pass" tests` finds nothing |
| 10 | the gates do not get worse | **pass** | ruff 4 (was 5). mypy `Found 10 errors in 4 files` (was 10 in 4). The one mypy error in the extractor is at `:1162`, which is pre-existing and not my code. Census grep `65` (was 65) |

## Baseline (verified, not redone), at the 19298f3 export, 2026-10-04

| Fact | Assignment says | Measured |
|---|---|---|
| gate | 793 passed | 793 passed |
| full | 2 failed (`*_rule3_red.py`), 793 passed | same, the same two tests |
| lint | 5, all BLE001 | 5, all BLE001 |
| types | 10 errors in 4 files | 10 errors in 4 files |
| census | 65 | 65 |
| blanket except | 1 BLE001 at 1798 | `ingestion/claude_extractor.py:1798:16` |

No disagreement.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Raise a plain `ValueError`, not `Pass1ShapeError` | `Pass1ShapeError` is a Pass 1 shape error with a `problems` list (`:406`). It does not fit Pass 2 | A new subclass would be new public surface the assignment did not ask for. `ValueError` is what every caller already stops on |
| Catch `(ValueError, KeyError, TypeError, AttributeError)` | "Catch only the exception types the parse can raise." Each type was measured by running `_parse_nri_response(_extract_json(c))` on stub replies. ValueError: `{not json}` (JSONDecodeError), no braces, no field, `year:"abc"`. KeyError: an absent `year`. TypeError: `non_recurring_items: 5`, `[null]`, `amount: null`. AttributeError: `[[]]`, which reaches `item.get` inside `_parse_nri_response`'s own error message | Leaving out AttributeError would let that reply escape without the filing name. It would still stop, but the message would not say which filing |
| Name the filing by ticker, company name and Pass 1 years | `_run_nri_pass` receives no path, and its caller is outside my scope ("`_run_nri_pass` only"). On a multi-filing run, `extract_multi_year` prints `EXTRACTING: <file name>` just before, so the console names the file | Passing the path in would mean editing `extract_financials`. Reported as a finding |
| No `or`/fallback when an identity value is empty | Rule 3: `repr` shows `''` as `''` | `ticker or 'Unknown'` would put a guess in the message |
| Keep the first-attempt path unchanged | The assignment asks for the retry branch only | See the findings: one first-attempt path stops without naming the filing |
| `from retry_exc` | Keeps the parse error's traceback chained for a reader in debug mode | — |

No code was changed to reach a target number.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| Pass 2 reply, first attempt, malformed JSON, then the retry reply unparseable | **stops** with a ValueError that names the filing and both errors | case `c1`, `c1b`, `c1c` |
| Pass 2 reply, `non_recurring_items: []` | returns `[]`. This is a real answer ("none found"), not a missing value | case `c2`, `c2b` |
| Pass 2 reply, first attempt, no `{` at all | **stops** with `No JSON object found in LLM response` and **does not name the filing**. No retry, because `_extract_json(raw)` is outside the first `try`. Unchanged by this unit | case `c0`: `RAISED ValueError stub calls=1` |
| Pass 2 reply, first attempt parses as JSON but has no `non_recurring_items`, `confidence` or `source`, or `TypeError` | **stops** without a retry, and the message does not name the filing. Unchanged: the first `except` catches only `(json.JSONDecodeError, KeyError)` | `claude_extractor.py`, the first `try` in `_run_nri_pass` |
| `financials.ticker`, `company_name`, `years` (message only) | printed as they are. An empty ticker shows `''` | the message f-string |

No "defaults to" row.

## What the CLI and the web route now show when this stop fires (read, not run)

- **CLI, route A** (`cli.py` with PDFs): the ValueError leaves `extract_financials` or
  `extract_multi_year` (`cli.py:863-891`). Nothing around those calls catches it. The
  `except ValueError` at `cli.py:808` wraps only `parse_pdf_args`. It reaches
  `__main__`'s `except Exception` at `cli.py:1143`, which prints `ERROR: <message>` to
  stderr and exits 1. `_save_cache` runs after the extraction, so no cache file is
  written. Before this unit: `[Pass 2 WARN] ... returning empty list`, then the run went
  on with zero items, stated that none were found, and cached that result.
- **Web, GET /assumptions** (`api/routes_valuation.py:399`, `_run_extraction`): the
  `except Exception` at `:445` sets `error = str(e)`. `assumptions.html:9-10` renders it
  in `alert alert-error`, and the assumption tables are hidden (`{% if not error ... %}`).
  `_extraction_cache` is not written, because the write comes after the extraction in
  the `try`.
- **Web, POST /valuation, cache miss** (`:563`): the `except Exception` at `:703` renders
  `valuation_result.html` with `error=str(e)` and `dcf=None`. The page shows
  `Error: <message>` (`valuation_result.html:9-11`).
- **Route B** (session file) is not affected. It never calls `_run_nri_pass`.

These three handlers are item 8's other sites. They were not edited.

## Measurements

- Failure set before: {`test_projector_rule3_red.py::test_an_extraction_with_no_income_statements_stops_and_names_the_input`, `test_routes_session_rule3_red.py::test_valuation_with_session_file_and_files_on_a_cache_hit_stops`}. After: the same set. 793 passed both times.
- Lint 5 to 4. Types 10 in 4 to 10 in 4. Census 65 to 65.
- No figure moved. This unit changes no number. It only changes whether the run continues.

## What I did not do

- No test was written or edited (`tests/` is not mine). None needs repair. The tester
  could add a test locking criteria 1 and 2 with a stubbed `_call_llm`, as in
  `tests/unit/test_claude_extractor.py:65-71`.
- The first-attempt paths were not changed (see the Rule 3 table, rows 3 and 4).
- `cli.py`, `api/` and the backlog were not edited.
- Nothing was committed.

## Findings for the orchestrator

1. **The first Pass 2 attempt stops without naming the filing, and sometimes without the
   retry.** In `_run_nri_pass`, `json_str = _extract_json(raw)` sits outside the first
   `try`. The first `except` catches only `(json.JSONDecodeError, KeyError)`. So:
   - a first reply with no `{` stops on the first attempt with `No JSON object found in LLM response`, with no retry and no filing named (measured, case `c0`);
   - a first reply that lacks `non_recurring_items`, `confidence` or `source`, or that raises TypeError, also stops without a retry or a filing name.

   This is a stop, not silent, so it is not a rule 3 defect. It is inconsistent with the
   retry that the malformed-JSON case gets. A candidate unit: put the first-attempt
   parse in the same `try`, catch the same four types, and keep one message shape.
2. **`_run_nri_pass` does not know the filing's path.** The stop names the filing by
   ticker, company name and the years Pass 1 read. To name the PDF itself,
   `extract_financials` would pass `Path(pdf_path).name` down to `_run_nri_pass`. That is
   a two-line change in one file, outside this unit's scope.
