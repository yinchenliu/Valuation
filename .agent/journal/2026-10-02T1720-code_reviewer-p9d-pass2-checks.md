---
agent: code_reviewer
assignment: P9d-pass2-checks
round: 1
verdict: approved
---

# Review of P9d-pass2-checks, round 1

Programmer entry: `.agent/journal/2026-10-02T1713-programmer-p9d-pass2-checks.md`
Diff reviewed: `git diff dce8d42 -- ingestion/session_extraction.py` (+84 / -4).

## The guard checks

Run over `ingestion/session_extraction.py`, the only code file in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | clean |
| lookup with a fallback — `.get(k, 0)` | clean. The two hits at base (`:471` `balance.get('year', '(absent)')`, `:473` `balance.get("year")`) are gone; F2 of the P9a review was answered by rewriting them |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` | clean |
| `getattr(` | clean |
| dict of functions keyed by data | clean |
| model client outside `ingestion/` | clean (`grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → nothing) |

The only remaining `.get(` in the file is `:264` `entry.get("pdf_path")`, one argument, a label, unchanged since P9a and answered there.

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| `pass2.non_recurring_items` absent | yes, via the unchanged parser | probe `nri_absent` → exit 2, `Pass 2 returned no 'non_recurring_items' field` |
| `non_recurring_items` not a list (dict, null) | yes, names file, `filings[0]`, PDF | probes `nri_dict`, `nri_null` → exit 2 (base: `nri_dict` exit 1, traceback) |
| item not an object | yes, names `pass2.non_recurring_items[i]` | probe `item_int` → exit 2 |
| each of the 8 schema keys absent | yes, names key and item | probe `desc_absent_year_absent` → 2 problems, label falls back to index only |
| `amount` NaN, -inf, `"12"`, `false` | yes | probes → exit 2 (base: all exit 0) |
| `amount` 0, 700.5, -700 | accepted, as Pass 1 accepts an explicit 0 | probes → exit 0 |
| `year` 2025.0, `true` | yes | probes → exit 2 (base: exit 0, `true` loaded as year 1) |
| `year`, `description` read for the label | read only after `in` tests (`:502-515`) | by reading |
| balance-sheet `year` absent / not positive int | yes, different words for each (`:477-486`) | by reading; the programmer's probes `bs_year_absent` etc. |

Shape problems return before `parse_pass2` runs (`_pass2_problems`, `:562`). The shape check covers every key the parser reads, so nothing the parser would name is hidden by the early return.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | no figure is produced or converted; `amount` is only type-checked |
| percentages converted at the route boundary, once | not touched |
| falsy not treated as missing | holds: `amount` 0 accepted (probe `amount_zero` exit 0); every test is `in` or `_is_int` / `_is_number` |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | unchanged. `session_extraction.py` gains one import from `ingestion.claude_extractor` — see F1 |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | red tests pass | 3 passed | `pytest -q tests/unit/test_session_extraction_rule3_red.py` → `3 passed in 0.04s` | yes |
| 2 | nothing else moved | gate 353 / 1, same set | gate → `1 failed, 353 passed`, `{test_capm…no_variation}`. Full suite in tree → `3 failed, 356 passed`. Full suite on a `git archive dce8d42` copy (`/tmp/p9d_rev_base`) → `6 failed, 353 passed`. **Failure sets compared:** after = before minus exactly the three `test_session_extraction_rule3_red.py` cases; nothing joined | yes |
| 3 | non-list exits 2 | exit 2 | `/tmp/p9d_rev_probe/probe.py`, 19 mutations of WMT.json, base vs tree: `nri_dict` base 1 → tree 2 | yes |
| 4 | WMT loads | exit 0, byte-identical | exit 0 in both trees; `diff /tmp/p9d_rev_wmt_before.txt /tmp/p9d_rev_wmt_after2.txt` → identical | yes |
| 5 | ruff 5, mypy as P9b left it | 5; 10 in 4 | mypy exact gate → `Found 10 errors in 4 files (checked 20 source files)`, 0 in `session_extraction.py`. `ruff check ingestion/session_extraction.py` → `All checks passed!`. **`ruff check .` reads 37 now**, but 32 are in `tests/unit/test_routes_session.py` and `test_routes_session_rule3_red.py`, untracked files the P9b tester is writing in parallel; the remaining 5 are the known BLE001 sites | yes, for this unit |

Rule 3 census grep: **116** in the tree and **116** at `dce8d42`.

## Rulings asked for

**Decision 1 — the unasked `year` integer check. Accepted, no finding.** It sits in the file in scope, its reason is rule 3 and not a target number, and it mirrors Pass 1, which already requires an integer `year` through the same `_is_int`. The objective is "check Pass 2 as Pass 1 is checked", and the assignment applied the same reasoning to `amount` ("as the Pass 1 key check already rejects a non-number"). It closes a silent path I measured: at base, `"year": true` exits 0 and `int(True)` loads the item as year 1, which `analysis/normalizer.py` then discards without a word (backlog item 25). It moves no valid file (WMT byte-identical).

**Decision 2 — `_NRI_SCHEMA` imported by its private name. F1, `minor`.** It breaks no rule in `rules.md`, so the rule floor does not apply. It does break an invariant that P9a's assignment step 5 set and that the P9a review verified as holding (`2026-10-02T1654-code_reviewer-p9a-session-route.md:65`, "no other module imports a `_` name"), and `claude_extractor.py:165` says the Pass 1 exports exist precisely to avoid this. The programmer's choice was the lesser of the two options its scope left it: a literal tuple would drift silently, the import fails loudly at import time if renamed. The tension was created by the assignment, which asked for "every key `_NRI_SCHEMA` names" while putting `claude_extractor.py` out of scope.

## Findings

### F1 — `session_extraction.py` imports the private `_NRI_SCHEMA` · `minor`

**Evidence:** `ingestion/session_extraction.py:73` `_NRI_SCHEMA,` and `:95`; it is the only private-name import across `ingestion/ api/ analysis/ models/ cli.py app.py` (`grep -rnE "^\s+_[A-Za-z_]+,\s*$"` → this line only).
**Rule or document:** no rule. P9a assignment step 5 and `claude_extractor.py:165-166`; the P9a review recorded the invariant as holding, and it no longer does.
**What would fix it:** export `PASS2_ITEM_FIELDS: tuple[str, ...] = tuple(_NRI_SCHEMA["non_recurring_items"][0])` beside `PASS1_YEAR_FIELDS` at `claude_extractor.py:222` and import that. It needs `claude_extractor.py` in scope, so it is the orchestrator's to schedule (the programmer's finding 1). When done, also drop the comment at `session_extraction.py:91-94`, which names "this unit" and "the P9d entry" and goes stale on the fix.

### F2 — two files outside scope changed in the working tree during this review · `note`

**Evidence:** `git status --short` at dispatch showed only `ingestion/session_extraction.py` modified. At 17:18 it also shows `M docs/3-architecture/extraction.md` (+5, a stop-list bullet naming P9d) and `M .claude/skills/extract-filing/SKILL.md` (+3), both mtime 17:17:37, after the programmer's entry (17:17:03), whose `files_touched` and "What I did not do" exclude them.
**Rule or document:** none against this unit; the text matches the programmer's finding 2, so it reads as the orchestrator acting on it. I do not attribute it to the programmer.
**What would fix it:** the orchestrator should commit those two files under its own name, not inside the P9d commit, so the unit's diff stays one file. I reviewed their content only in passing: the extraction.md bullet is accurate against my probes.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 25 — an item whose year matches no statement is silently discarded | `analysis/normalizer.py:236-241` (`by_year.get(stmt.year, [])`) | no. Seen through probe `year_neg`: `"year": -1` is an integer, so it passes the new check and exits 0. Range is not this unit's ask; item 25 is where it bites |
| 1 — route A's parser coerces / defaults | `ingestion/claude_extractor.py`, `_parse_nri_response` | no. Route A still turns `"12"` into 12.0 and `2025.7` into 2025; route B now refuses both. The programmer's finding 3 records the asymmetry |
| 45 — CAPM test held by the user | `tests/unit/test_capm.py:473` | no |

## Verdict

`approved`

No `blocker` or `major` stands. The shape check stops on every malformed Pass 2 I could construct, names the file, filing, PDF and item, leaves route A's parser untouched, and moves no valid file. F1 is a convention breach forced by the assignment's scope and should be scheduled as a one-line follow-up in `claude_extractor.py`; F2 is for the orchestrator's commit hygiene.
