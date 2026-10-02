---
agent: programmer
assignment: P9d-pass2-checks
round: 1
status: complete
files_touched: [ingestion/session_extraction.py]
---

# P9d-pass2-checks — check the shape of Pass 2 in the session loader, as Pass 1 is checked

## What I did

The loader now checks each filing's `pass2` before it calls `parse_pass2`. The new
function is `_pass2_shape_problems` in `ingestion/session_extraction.py`, with
`_pass2_item_label` beside it. It checks five things:

- `non_recurring_items` is a list;
- every item is a JSON object;
- every key `_NRI_SCHEMA` names is present on every item (all eight: `year`,
  `description`, `amount`, `line_item`, `direction`, `category`, `confidence`, `source`);
- `amount` is a finite JSON number (`_is_number`, the same check Pass 1 uses);
- `year` is a JSON integer.

Problems are collected per filing, the way Pass 1 problems already are. Each one names
the file, `filings[i]`, the PDF name and the item's index, plus its year and description
when those are present. If any shape problem is found, `parse_pass2` is not called for
that filing. When the shape is clean, `parse_pass2` runs exactly as before.
`parse_pass2` and `_parse_nri_response` are unchanged, and `git diff` touches no file
but `session_extraction.py`. Finding F2 is answered by changing the code, not by
argument: the balance-sheet `year` stop now reads `year` only after a presence test, and
it uses different words for "absent" and "wrong".

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the red tests pass | **pass** | `.venv/bin/python -m pytest -q tests/unit/test_session_extraction_rule3_red.py` → `3 passed in 0.04s` (before: `3 failed`) |
| 2 | nothing else moved | **pass** | `pytest -q --ignore-glob="*_rule3_red.py"` → `1 failed, 353 passed`, the same failure set as before: `{test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}`. Full `pytest -q` → `3 failed, 356 passed`, set `{test_capm…no_variation, test_dcf_rule3_red…balance_sheet_is_absent, test_projector_rule3_red…no_income_statements…}`. The three P9d cases left the failure set and nothing joined it |
| 3 | `check` exit codes keep their meaning | **pass** | `/tmp/p9d/probe.py`. `nri_dict` (`{"a": 1}`) → exit 2, `nri_str` → exit 2, `nri_null` → exit 2, `item_str` → exit 2. HEAD's module on the same files (`/tmp/p9d/old_session_extraction.py`) → exit **1** with `AttributeError: 'str' object has no attribute 'get'` for all three |
| 4 | the real Walmart file still loads | **pass** | `.venv/bin/python -m ingestion.session_extraction check extractions/WMT.json` → exit 0. Its output is byte-identical to the run before the change (`diff /tmp/p9d_wmt_before.txt /tmp/p9d/wmt_after.txt` → no output): years [2024, 2025, 2026], B/S [2026], 4 items, sha256 `23920728ddd7eed2…` |
| 5 | no new lint or type errors | **pass** | ruff → `Found 5 errors.`, the same five BLE001 sites. mypy (exact gate command) → `Found 10 errors in 4 files (checked 20 source files)`, and none is in `session_extraction.py` (`grep -c session_extraction` → 0) |

### Criterion 3, all probes (mutations of a copy of `extractions/WMT.json`, item 0 unless stated)

| Probe | Before (HEAD) | After |
|---|---|---|
| `non_recurring_items` = `{"a":1}` / `"restructuring"` / `null` | exit 1, `AttributeError` | exit 2, `'pass2.non_recurring_items' must be a list …, got dict {'a': 1}` (and `str …`, `NoneType None`) |
| item 0 = `"restructuring"` | exit 1, `AttributeError` | exit 2, `pass2.non_recurring_items[0]: must be a JSON object, got str 'restructuring'` |
| `amount` NaN / inf / `"12"` / `true` / `null` | NaN, inf and `"12"` exit 0 (loaded) | exit 2, `pass2.non_recurring_items[0] (year 2026, "Non-cash charge on PhonePe's …"): 'amount' must be a finite JSON number, got nan` (and `inf`, `'12'`, `True`, `None`) |
| `amount` = 0 | — | exit 0. An explicit 0 is accepted, as in Pass 1 |
| `year` = 2025.7 / `"2025"` | 2025.7 exit 0 (loaded as 2025 by `int()`) | exit 2, `'year' must be an integer, got 2025.7` (and `'2025'`) |
| each of the 8 keys absent | exit 2, `KeyError: 'category'`, naming no item | exit 2, `pass2.non_recurring_items[0] (year 2026, "…"): key '<key>' is absent.` With `year` absent the label is the index and the description. With `description` absent it is the index and `(year 2026)` |
| `non_recurring_items` absent | exit 2 (parser) | exit 2 (parser), unchanged: `Pass 2 returned no 'non_recurring_items' field …` |
| `non_recurring_items` = `[]` | exit 0 | exit 0 |
| item 0 `category` absent and item 1 `amount` NaN | — | exit 2, `2 problem(s)`: both are listed, each naming its own item |
| B/S `year` absent / 0 / `"2026"` (F2) | — | exit 2: `balance sheet: key 'year' is absent.` / `… must be a positive integer, got 0.` / `… got '2026'.` |

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The key list is `tuple(_NRI_SCHEMA["non_recurring_items"][0])`, imported from `claude_extractor` under its private name | The assignment says "every key `_NRI_SCHEMA` names". Pass 1 reads its key list from the schema the prompt is built from (`claude_extractor.py:165-167`, `:222-223`), so the check and the prompt cannot drift | A literal tuple in this file would drift silently if the prompt schema gains a key. The clean fix is a public `PASS2_ITEM_FIELDS` in `claude_extractor.py`, as Pass 1 has, but that file is out of scope. That is finding 1 below |
| Shape problems stop the filing before `parse_pass2` is called | If the parser also ran, one absent key would be reported twice, once by the shape check and once as the parser's `KeyError`. A non-list would still raise `AttributeError` | Running the parser regardless would need `AttributeError` added to the `except`, which hides the cause rather than naming it |
| An absent `non_recurring_items` is left to the parser | Its message (`claude_extractor.py`, `_parse_nri_response`) already explains why "absent" and "empty" are different answers. One source for that message | Duplicating it here would give two wordings of one stop |
| All 8 schema keys are checked, including `confidence` and `source` | The assignment names `_NRI_SCHEMA`'s keys, and `_NRI_SCHEMA` holds 8. The existing tests `test_stop_pass2_item_key_absent[confidence/source]` still pass: the message carries `'confidence'`, `year 2023` and `Settlement C` on one line | — |
| `year` must be a JSON integer, which the assignment does not ask for | Rule 3. `int(item["year"])` in route A's parser turns `2025.7` into 2025 and `"2025"` into 2025 without saying so (probe `year_float`, before: exit 0). That is a guess about which year an adjustment belongs to. Pass 1 already requires an integer `year` (`_pass1_problems`, `_is_int`) | Leaving it would keep the same silent coercion the P9c tester's finding 5 raised for `amount`. It cannot move a valid file: WMT's output is byte-identical |
| The full description goes into the label, not truncated | It is what a reader searches for in the filing, and the P9a parser's `confidence`/`source` stops print it whole. The red test asserts the full string `Plant closure` | Truncating to a fixed width would introduce an arbitrary constant. The cost is one long line, which is acceptable for a stop message |
| F2: rewrite rather than answer | The rewrite is two presence tests, it removes both `.get` reads on the balance sheet (`:471` and `:473` at HEAD), and it separates "absent" from "wrong" in the message. Before, both were printed as `got '(absent)'` | An answer alone would leave a guard-grep hit that every later reviewer must answer again |

No change was made to reach a target number. No figure moved: the WMT output is identical.

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `pass2.non_recurring_items` | stops (via the parser, unchanged) and names the key | probe `nri_absent`, exit 2 |
| `pass2.non_recurring_items`, not a list | stops and names `pass2.non_recurring_items` with the file, filing and PDF | red tests `[not_a_list0]`, `[restructuring]`; probes `nri_dict`, `nri_str`, `nri_null` |
| an item that is not an object | stops and names `pass2.non_recurring_items[i]` | probe `item_str` |
| each of the 8 item keys | stops and names the key and the item by its index, year and description where present | probes `absent_*`; `_pass2_shape_problems` key loop |
| item `amount`: NaN, inf, string, bool, null | stops and names `'amount'` and the item | red test `…amount_nan…`; probes `amount_*` |
| item `year`: not an integer | stops and names `'year'` and the item | probes `year_float`, `year_str` |
| item `year` / `description`, read for the **label** | read only after `"year" in item` / `"description" in item`. When absent, the label carries the index alone, and the absence is itself reported as a problem | `_pass2_item_label`; probes `absent_year`, `absent_description` |
| balance-sheet `year` (F2) | stops: `balance sheet: key 'year' is absent.`. Read only after a presence test | probe `bs_year_absent` |
| balance-sheet label `bs_label` | `"balance sheet"` with no year when the year is absent or not an integer. This is message text, not a figure, and the absence is reported on its own line | `_pass1_problems` |
| `entry.get("pdf_path")` at `:264` | a label only. `pdf_path` is checked for presence a few lines below (`_session_plans`). Answered in the P9a entry and unchanged here | `grep -n "\.get(" ingestion/session_extraction.py` → that one line only |

No "defaults to" row.

## Measurements

### Before, at `dce8d42` (macOS, `.venv/bin/python`)

- Red file: `pytest -q tests/unit/test_session_extraction_rule3_red.py` → **3 failed**:
  `test_pass2_items_not_a_list_stops_naming_file_and_filing[not_a_list0]`,
  `[restructuring]`, `test_pass2_item_amount_nan_stops_naming_filing_year_and_description`.
- Gate: `pytest -q --ignore-glob="*_rule3_red.py"` → **353 passed, 1 failed**. Failure set
  `{test_capm.py::test_beta_stops_when_the_market_series_has_no_variation}` (item 45, held).
- Ruff: **5 errors**, all BLE001 (`routes_valuation.py:445`, `:703`, `cli.py:1107`,
  `claude_extractor.py:1051`, `tests/test_e2e_all_googl.py:106`).
- Mypy (exact gate command): **10 errors in 4 files**, 20 files checked.
- `check extractions/WMT.json` → exit 0, years [2024, 2025, 2026], B/S [2026], 4 items.

### After (working tree on `dce8d42`, `session_extraction.py` changed)

- Red file: **3 passed**.
- Gate: **353 passed, 1 failed**, with the same failure set.
- Full suite: **356 passed, 3 failed**: capm and the two other `*_rule3_red.py` cases
  (`test_dcf_rule3_red`, `test_projector_rule3_red`).
- Ruff: **5**, the same sites. Mypy: **10 in 4 files**, none in `session_extraction.py`.
- Rule 3 census grep (`'--include=*.py'` quoted): **116**, unchanged.
- `check extractions/WMT.json`: exit 0, with output byte-identical to the run before.
- `git diff --stat`: `ingestion/session_extraction.py | 84 +++++++++++++++++++++++++++++++++++++++--`.
  No other tracked file changed. `claude_extractor.py` is untouched.

The test counts were measured while the P9b tester was running in parallel. Its entry,
`2026-10-02T1713-tester-p9b-route-tests.md`, was untracked at the time, and no new test
file of theirs had been collected.

## What I did not do

- I did not run route A on any PDF.
- I did not move the three tests out of the red file. That belongs to the tester, by the
  assignment.
- I did not edit `docs/3-architecture/extraction.md`. Its stop list (`:207-227`) still
  describes the Pass 2 stops only as "route A's Pass 2 parser rejects `pass2`". It is out
  of scope (finding 2).
- I did not check that the strings in an item are strings, or that their values are
  members of their enums (`line_item`, `direction`, `category`, `confidence`). The
  assignment does not ask for it. `analysis/normalizer.py` already stops on an unknown
  `line_item` and an unknown `direction` (backlog items 3 and 21, both closed).

## Findings for the orchestrator

1. **`claude_extractor.py` should export `PASS2_ITEM_FIELDS`**, defined as
   `tuple(_NRI_SCHEMA["non_recurring_items"][0])`, beside `PASS1_YEAR_FIELDS` at `:222`.
   `session_extraction.py` would then import that public name instead of `_NRI_SCHEMA`.
   Today it imports the private name, because this unit's scope did not include
   `claude_extractor.py`. Severity: `note`. The behaviour is correct, and no drift is
   possible either way.
2. **`docs/3-architecture/extraction.md:207-227`, the stop list, needs one bullet**:
   "`pass2.non_recurring_items` is not a list; an item is not an object, lacks a key
   `_NRI_SCHEMA` names, has an `amount` that is not a finite JSON number, or a `year`
   that is not an integer. Each stop names the item by its index, year and description."
   The same applies to anything in `.claude/skills/extract-filing/` that tells a session
   what `check` accepts.
3. **The unasked `year` check.** `int(item["year"])` in route A's parser
   (`_parse_nri_response`) still coerces `2025.7` to 2025 and `"2025"` to 2025 on route
   A, as does `float(item["amount"])` for `"12"`. Route B now refuses all three. The two
   routes therefore differ on malformed input, and agree on well-formed input. That is
   the same asymmetry Pass 1 already has (backlog item 1). If route A should refuse them
   too, it is item 1's work, not this unit's.
