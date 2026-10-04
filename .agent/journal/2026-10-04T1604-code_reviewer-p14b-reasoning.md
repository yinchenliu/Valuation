---
agent: code_reviewer
assignment: P14b-reasoning
round: 1
verdict: approved
---

# Review of P14b-reasoning, round 1

Programmer entry: `.agent/journal/2026-10-04T1548-programmer-p14b-reasoning.md`

## The guard checks

Run over the assignment's **Files in scope** (`config.py`, `ingestion/claude_extractor.py`, `ingestion/session_extraction.py`, `templates/assumptions.html`, `templates/valuation_result.html`, `docs/2-rules/llm-boundary.md`, `docs/3-architecture/extraction.md`):

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean in diff (0 hits across files in scope) |
| lookup with a fallback — `.get(k, 0)` | clean in diff. 13 pre-existing hits in `ingestion/claude_extractor.py` (env var reads and doc table), untouched |
| bare or-default — `or 0.0` | clean in diff. 3 pre-existing hits in `ingestion/claude_extractor.py` (1925-1927) in token counter, 5 pre-existing hits in `templates/assumptions.html` (166-192) in input fields, untouched |
| money field defaulted to zero — `: float = 0.0` | clean in diff (0 hits) |
| `**kwargs` on a calculation function | clean in diff (0 hits) |
| `getattr(` on a name from outside the file | clean in diff. 2 pre-existing hits in `ingestion/claude_extractor.py:1926-1927` on usage metadata, untouched |
| dict of functions keyed by data | clean in diff (0 hits) |
| model client imported outside `ingestion/` | clean in diff (0 hits) |

**A hit is a question, not automatically a finding.** All pre-existing hits in files in scope are outside modified lines and untouched.

## Rule 3, by reading

The greps catch the four written forms. This table catches the rest. For every value the unit reads, ask: if it were missing, what happens?

| Value | Stops and names it? | Evidence |
|---|---|---|
| `config.EXTRACTION_EFFORT` in `_call_claude` | Stops: raises `AttributeError` naming `EXTRACTION_EFFORT` | `ingestion/claude_extractor.py:1847` |
| `config.EXTRACTION_EFFORT` in `_resolve_claude` | Stops: raises `AttributeError` naming `EXTRACTION_EFFORT` | `ingestion/claude_extractor.py:2725, 2750, 2764` |
| `ProviderResolution.reasoning_label` field | Stops: dataclass field without default; constructor raises `TypeError` missing required argument `reasoning_label` | `ingestion/claude_extractor.py:151` |
| `resolution.reasoning_label` in `describe_resolution` | Stops: raises `AttributeError` naming `reasoning_label` | `ingestion/claude_extractor.py:2821` |
| Text block in Claude stream response (`response.content`) | Stops: raises `ValueError` naming missing text block and block types received | `ingestion/claude_extractor.py:1858-1863` |
| Claude stream response hitting token limit (`response.stop_reason`) | Stops: raises `ValueError` naming 64,000-token output ceiling | `ingestion/claude_extractor.py:1868-1873` |
| Pass 2 item check failures in `_pass2_item_failures` | Stops: `item_failed` boolean per item accurately tracks failure without string collision; reports exit 2 and names unconfirmed item | `ingestion/claude_extractor.py:1595-1714` |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean: diff modifies extraction parameters, resolution metadata, and item counts; does not handle financial amounts |
| percentages converted at the route boundary, once | clean: not applicable to this diff |
| falsy not treated as missing (`if x` where `if x is not None` is meant) | clean: `item_failed` is boolean; `_CLAUDE_MAX_TOKENS` checked via explicit enum/string equality |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | clean: `analysis/` was not touched |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | the request carries the reasoning setting | pass | Stub client in python probe verified `thinking == {"type": "adaptive"}`, `output_config == {"effort": "high"}`, `max_tokens == 64000`, 0 forbidden parameters (`temperature`, `top_p`, `top_k`, `budget_tokens`). | Agree |
| 2 | a thinking block is not read | pass | Stub client returning `[thinking "SECRET", text "{\"a\": 1}"]`: returns `"{\"a\": 1}"`, `SECRET` never appears in return value or stdout. | Agree |
| 3 | the stops still hold | pass | Stub with thinking block only raises `ValueError` naming missing text block; stub with `stop_reason == "max_tokens"` raises `ValueError` naming 64,000 ceiling. | Agree |
| 4 | the effort is named once | pass | `grep -rn "EXTRACTION_EFFORT" config.py ingestion/`: exactly 1 definition at `config.py:125:EXTRACTION_EFFORT: Final = "high"`, read at `claude_extractor.py:1847` and in label formatters. | Agree |
| 5 | the label is shown | pass | 1) `describe_resolution` for route A Claude prints `Reasoning: adaptive thinking, effort 'high' (config.EXTRACTION_EFFORT)`.<br>2) CLI on Walmart prints `Reasoning: as the Claude Code session ran; not set by this code`.<br>3) `TestClient` on `/assumptions` and `/valuation` returns HTTP 200 with Reasoning row in HTML tables. | Agree |
| 6 | item 81 is fixed | pass | Clean Walmart prints `4 checked, 4 found, 0 not confirmed` (exit 0). Copy with 2025 item amount 795 prints `4 checked, 3 found, 1 not confirmed` and exits 2 with 1 problem listed. | Agree |
| 7 | Walmart does not move | pass | `cli.py --session-file extractions/WMT.json`: Stages 1-10 identical to `21125ed`, PV of TV $214,819M, implied price $28.02, downside -73.1%. | Agree |
| 8 | the gates do not get worse | pass | ruff: 4 (exact baseline).<br>mypy: 9 in 4 files (exact baseline).<br>census: 65 (exact baseline).<br>`GET /`: status 200. | Agree |
| 9 | every red test is named | pass | Suite has 588 passed, 2 failed (known red on purpose). 4 test files errored at collection on `ProviderResolution` missing `reasoning_label` fixture argument (`test_claude_extractor.py`, `test_page_check.py`, `test_pass1_printed_lines.py`, `test_session_extraction.py`). All 413 tests in these 4 files pass when `reasoning_label` supplied (1001 passed + 2 red on purpose = 1003 tests total). Out of scope per assignment; delegated to `P14b-reasoning-tests`. | Agree |
| 10 | not measured here | pass | Real route A call through Foundry gateway is a paid call; intentionally not run. | Agree |

## Findings

None.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 (zero defaults in models) | `models/financial_statements.py` | No |
| 8 (blanket `except Exception`) | `cli.py:1165` | No |
| 10 (D&A in Pass 1 parser) | `ingestion/claude_extractor.py:1260` | No |
| 51 (dead `WARN` branch) | `ingestion/claude_extractor.py:270` | No |
| 53 (private `_NRI_SCHEMA` import) | `ingestion/session_extraction.py:84` | No |
| 61 (AssertionError after retry loop) | `ingestion/claude_extractor.py:2532` | No |
| 63 (filing with no text layer) | `ingestion/claude_extractor.py:1611, 1647` | No |
| 64 (page check joined-line form) | `ingestion/claude_extractor.py:1460` | No |
| 70 (PV of terminal value variance) | stage 10 | No |
| 72 (conditional zeros in cli) | `cli.py:1056, 1064` | No |
| 73 (first Pass 2 reply stops without filing name) | `ingestion/claude_extractor.py:2570` | No |
| 74 (OverflowError/RecursionError in Pass 2) | `ingestion/claude_extractor.py:2600` | No |
| 78 (already converted guard sees BS only) | `ingestion/claude_extractor.py:3145` | No |
| 79 (route A unit stop names field/text/page but not PDF) | `ingestion/claude_extractor.py:2612` | No |
| 80 (arithmetic check in printed units) | `ingestion/claude_extractor.py:1568` | No |
| 81 (Pass 2 summary miscount) | `ingestion/claude_extractor.py:1715` | **Fixed by this unit** |

Note: The one line added by the programmer in `.agent/journal/INDEX.md` is standard logging and ignored during code review (as in `2026-10-04T0948-code_reviewer-p13h-zero-debt-confirm.md`).

## Earlier findings — re-reviews only

| # | Outcome | Note |
|---|---|---|
| — | — | Round 1 |

## Verdict

`approved`

The unit satisfies all requirements of assignment `P14b-reasoning` under Rule 1 option 0 and Rule 6. Route A calls Claude via streamed requests with `thinking={"type": "adaptive"}` and `output_config={"effort": config.EXTRACTION_EFFORT}`, with a 64,000-token ceiling and strict preservation of text-only block parsing (thinking blocks are never read, printed, or logged). `ProviderResolution` exposes `reasoning_label` with no silent default, and the setting is displayed in `describe_resolution` and across both web templates. Backlog item 81 is resolved cleanly by tracking failures directly per item. All 10 done-criteria pass upon re-execution, the gates remain stable, and test suite collection errors in 4 test files are strictly confined to expected fixture updates assigned to tester unit `P14b-reasoning-tests`.
