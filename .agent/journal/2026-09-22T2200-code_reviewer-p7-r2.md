---
agent: code_reviewer
assignment: P7-low-confidence
round: 2
verdict: approved
---

# Review of P7-low-confidence, round 2

Programmer entry: `.agent/journal/2026-09-22T2100-programmer-p7-low-confidence-r2.md`
Round-1 review: `.agent/journal/2026-09-22T2000-code_reviewer-p7-low-confidence.md`

HEAD is `54c5af8`, so the baseline and `HEAD` are the same tree and every set-diff below
is against a `git archive HEAD` export at `c:/tmp/p7r2rev/base/`.

Diff: 5 files, **+319 / −27**, exactly the Files in scope. `git status --short` shows the
same five and nothing else. This round moved two of them —
`ingestion/claude_extractor.py` (mtime 12:19) and `analysis/normalizer.py` (13:05);
`cli.py`, `api/routes_valuation.py` and `templates/valuation_result.html` still carry
round 1's 11:39–11:40 mtimes and their round-1 line counts. No scope finding.

## The six checks

### 1 — F1's stop is a real stop · **confirmed by execution**

I did not take the programmer's word or its script. I wrote my own
(`c:/tmp/p7r2rev/prop.py`): `_call_llm` replaced by a counting stub, no network, no key,
no PDF, driving the **wrapper** `_run_nri_pass`, not the parser.

```
[absent key {}]           RAISED ValueError: Pass 2 returned no 'non_recurring_items' field...  llm_calls=1
[other keys only]         RAISED ValueError: ...                                                llm_calls=1
[pass1 shape]             RAISED ValueError: ...                                                llm_calls=1
[explicit empty list]     RETURNED []                                                           llm_calls=1
[item missing confidence] RAISED ValueError: ...no 'confidence' field: year 2024, 'a charge'    llm_calls=1
[item missing source]     RAISED ValueError: ...no 'source' field: year 2024, 'a charge'        llm_calls=1
[good low item]           RETURNED [NonRecurringItem(... confidence='low' ...)]                 llm_calls=1
```

**One LLM call in every case.** The error is not caught on the way out, and the reason is
structural, not lucky: `json.JSONDecodeError` is a *subclass* of `ValueError`, so
`except (json.JSONDecodeError, KeyError)` at `:978` does **not** match a plain
`ValueError` — no retry fires, so the retry's `except Exception: return []` at `:990` is
never reached. I checked the rest of the route out: the only two blanket catches in the
file are `:568` (unrelated) and `:990`; `extract_financials:1230` wraps nothing; the
entry-point catches (`cli.py:1115`, `api/routes_valuation.py:124,317`) render the message
and produce no valuation. The run stops and names the field. **F1 is fixed.**

### 2 — every remaining `.get` in `_parse_nri_response` · **the reasoning holds**

Exactly three survive, and all three are inside the two raise messages:

```
735:  f"field: year {item.get('year')}, "
736:  f"{item.get('description')!r}. The prompt requires one of "
744:  f"year {item.get('year')}, {item.get('description')!r}. The "
```

None takes a fallback argument — they are `.get(k)`, not `.get(k, default)`, so they are
not lookups-with-a-default in rule 3's sense; an absent key renders `None` **into a
message on a path that is already raising**. The stated reason is correct and I verified
the failure mode it avoids: with `item["year"]` there, a reply missing both `source` and
`year` would die with `KeyError: 'year'` raised while formatting — and that `KeyError`
*is* in the `:978` catch tuple, so it would route into the repair retry and could end at
`return []`. Using the subscript there would have rebuilt F1. `item["source"]` on the
value that reaches `NonRecurringItem` is a plain subscript. **F3 is fixed, not argued
away.**

### 3 — the F2 withdrawal · **both claims verified; withdrawal is the right answer**

Loaded `cache/.cache_lhx_extraction_inputs.pkl` read-only (`c:/tmp/p7r2rev/cache3.py`):

```
2023 add_back   30  cost_of_revenue          high   acquisition_costs
2023 add_back  296  other_operating_expense  high   impairment
2023 add_back   78  other_operating_expense  high   impairment
2023 add_back  115  sga                      high   restructuring         LHX NeXt implementation costs included in G&A
2023 add_back  174  sga                      high   acquisition_costs     Merger, acquisition, and divestiture-related expenses
2023 add_back   51  sga                      high   gain_loss_asset_sale  Business divestiture-related losses, net
2023 net adjusted_impact: 744.0
2023 sga items SUM: 340.0   (115 + 174 + 51)
```

**Claim 1 holds exactly**: three fiscal-2023 `sga` charges, 115 + 174 + 51 = **340**, net
744. The grafted aggregate describes itself as *"LHX NeXt implementation costs **and other
charges in G&A** (components not separately disclosed for 2023)"*, so removing the 115
leaves 174 and 51 as unquantifiable overlap with "other charges in G&A". There is no
arithmetic on disk that resolves it, and the graft would still splice one document's
aggregate into another document's itemisation. **The repair I offered in round 1 would not
have produced a defensible number, and I withdraw the suggestion.**

**Claim 2 holds**, measured by unpickling all three caches rather than by opcode scan:

```
.cache_abbv_extraction.pkl        43 items  {'high': 40, 'medium': 3}   low: 0
.cache_lhx_extraction.pkl         23 items  {'high': 22, 'medium':  1}   low: 0
.cache_lhx_extraction_inputs.pkl  15 items  {'high': 13, 'medium':  2}   low: 0
```

No `low` item exists anywhere on disk, so the FY2025 Pass 2 list cannot be recovered
without a paid extraction. **"The magnitude cannot be sized from the data on disk; only
the direction is certain" is the correct answer**, and it is better than a repaired
number.

**Provenance**, independently checked: `docs/9-reference/refactor-backlog.md:612` —
*"The **FY2025** L3Harris 10-K was extracted twice"* — and the cache entry measured is the
FY2024 PDF, sha `7d7ca648…`. Two documents, as I said in round 1.

**Is the withdrawal plain enough?** Yes. The entry's first section is the correction, in
bold: *"is WITHDRAWN. It is not a measurement, it is not an upper bound, and it should not
be quoted"*, and F2 enumerates every withdrawn figure — `$474.96`, `$63.57`, `13.4%`, run
C's adjusted EBIT `3,310` — and also retires the criterion-4 block's `$411.47` headline as
constructed. It states what replaces it: `$0.00`, 13 `high` + 2 `medium` + 0 `low`.

**Circulation**, checked: `grep -rn "63\.57\|474\.96\|13\.4%"` over `*.md` and `*.py`
outside `.agent/journal/` hits only `.agent/assignments/P7-low-confidence.md` (the
amendment quoting it). **Not in `STATUS.md`, not in the backlog, not in code.**

**The docstring provenance is fixed.** `analysis/normalizer.py` now reads *"the 1,140M
add-back the model itself tagged `low` in the **FY2025** L3Harris 10-K extraction …
(backlog item 36, which records that filing and that run). No cache entry on disk now
holds a `low` item, so this docstring cites the recorded run, not a measurement."* That
matches the backlog, and it labels itself as a record rather than a measurement — rule 5's
habit applied to a docstring.

### 4 — criterion 7's measurement is untouched · **re-measured**

```
raw items: 15  {'high': 13, 'medium': 2}          <- 0 low
partition: applied 15  excluded 0
applied is elementwise-identical to raw: True
```

`partition_by_confidence` returns the same objects in the same order, so the two runs are
one computation performed twice and the difference is **$0.00** by construction, not by
coincidence. Unchanged from round 1.

### 5 — criterion 8 and scope · **re-run, as sets**

| Check | Result |
|---|---|
| suite | `1 failed, 145 passed` |
| failure **set** vs baseline export | both trees fail the single nodeid `tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` — I ran pytest in `c:/tmp/p7r2rev/base/` too, not just here |
| tests edited | none — `git status --short -- tests/` empty |
| `git status --short -- models/ tests/ docs/ STATUS.md .agent/journal/INDEX.md` | **empty** |
| ruff | 5, all `BLE001`; `comm` both directions vs baseline → **empty** |
| mypy (documented gate) | **14 in 4 files**; `comm` both directions vs baseline → **empty** |
| rule-3 census | **116** here, **116** in the baseline export |
| `GET /` | **200**, 1648 bytes |
| cache files | `.cache_abbv…` and `.cache_lhx_extraction.pkl` at 2026-09-20 12:24, `.cache_lhx_extraction_inputs.pkl` at 2026-09-22 14:12, sizes 11412 / 7435 / 6621 — **nothing written today**; every access this round and this review was a read |

### 6 — the types-gate discrepancy · **reproduced; here are the exact figures**

| Command | Result |
|---|---|
| `mypy models analysis ingestion api` — the agent harness note | **18 errors in 6 files (checked 16 source files)** |
| `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` — `docs/8-build/environment.md:148`, and `STATUS.md:22` | **14 errors in 4 files (checked 18 source files)** |

The 14 are a **strict subset** of the 18. The four extra are nothing but missing third-party
stubs, which is exactly what the missing flag suppresses:

```
analysis\capm.py:  Library stubs not installed for "scipy"  [import-untyped]
api\routes_valuation.py:  Skipping analyzing "yfinance": ... missing library stubs  [import-untyped]
ingestion\price_fetcher.py:  Library stubs not installed for "pandas"  [import-untyped]
ingestion\price_fetcher.py:  Skipping analyzing "yfinance": ...  [import-untyped]
```

The harness command also checks **two fewer files** (it omits `config.py` and `app.py`)
while reporting *more* files with errors — so the two numbers cannot be reconciled by
arithmetic and will always look like a regression to whoever quotes the smaller one
second. **The documented gate is the right one** and `docs/8-build/environment.md:159`
says why: *"`mypy .` is not the gate … The gate names the four source packages plus the
two root modules."*

**One correction to the programmer's report, in your favour.** `environment.md:148` is
**not stale in the way described.** Its table is headed *"Result at `bc19431`"* and the
text beneath it reads *"**No gate passes today.** That is the starting position.
STATUS.md section 1 holds the breakdown and keeps the current figure; this file owns the
commands, not the counts."* So `33 errors in 4 files` is a dated historical baseline, not
an expected value, and `STATUS.md:22` already carries the live figure, **14 errors in 4
files**, under the identical command. Nothing there needs re-measuring. **The one thing
that is wrong is the harness note's command**, and that is a harness-prompt fix, not a
docs unit.

## The guard checks

Run over the five Files in scope, and over the added lines of the diff.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | no hit on any added line |
| lookup with a fallback — `.get(k, 0)` | **no hit on any added line.** The one regex match is line 744's two zero-default `.get(k)` calls read as one by the pattern; both are message diagnostics, answered in the entry and in check 2 above |
| bare or-default — `or 0.0` | clean on added lines |
| money field defaulted to zero — `: float = 0.0` | clean |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | no new one |
| dict of functions keyed by data | clean — `grep -rnE "= *\{[^}]*: *_?[a-z_]+ *[,}]"` over the five files returns nothing |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` returns nothing |

## Rule 3, by reading — what this round changed

| Value | Stops and names it? | Evidence |
|---|---|---|
| `non_recurring_items` key, Pass 2 reply | **yes**, naming the field and listing the keys that arrived — and the stop leaves `_run_nri_pass` | `c:/tmp/p7r2rev/prop.py`, three shapes, 1 LLM call each |
| `"non_recurring_items": []` | **accepted**, correctly — the prompt asks for exactly that at `:297` (verified) | same script |
| `confidence` key, Pass 2 item | **yes**, naming year and description. The prompt requires it at `:255` (verified) | same script |
| `source` key, Pass 2 item | **yes**, naming year and description. The schema requires it at `:256` | same script |
| explicit `source: ""` | **accepted**, renders `(none cited)`, which now has exactly one meaning | same script |
| `year`/`amount`/`line_item`/`direction`/`category`/`description` | plain subscripts → `KeyError`. **Moved by this unit but behaviourally identical** — they were subscripts before the rewrite. The weakness is the `:990` swallow that `KeyError` routes into, which is backlog item 8 and untouched | `KeyError: 'year'` reproduced |
| `NonRecurringItem.confidence` / `.source` constructed in Python | still `"high"` / `""` | `models/financial_statements.py:28-29`, F4, out of scope |

## Earlier findings

| # | Outcome | Note |
|---|---|---|
| F1 | **fixed** | absent key raises and the `ValueError` propagates out of `_run_nri_pass` after one LLM call; `[]` still accepted. Criteria 10 and 11 met |
| F2 | **fixed — by withdrawal, which I accept** | both defects conceded; both of the programmer's verification claims reproduced above. Criterion 12 met. **I withdraw my round-1 "drop the +115M and re-graft" suggestion**: the measurement shows it would still leave an unquantified overlap |
| F3 | **fixed** | `item["source"]` with a guard; the remaining `.get`s are message diagnostics only, and the reasoning survives inspection |
| F4 | **not_fixed — correctly deferred** | `models/financial_statements.py:28-29` untouched; `git status --short -- models/` empty. Needs a `models/` unit plus a tester, as the amendment records |
| F5 | **not_fixed — correctly deferred** | five dev scripts untouched; `git status --short -- tests/` empty. Tester unit, as the amendment records. The programmer adds a second reason: they bypass the new parser stops as well |
| F6 | **not_fixed — acknowledged** | `note`. The page still renders nothing when nothing is excluded; the CLI says so in words. Named in the entry so it is not lost |
| F7 | **not_fixed — acknowledged** | `note`. `api/routes_valuation.py:292-294` still cites `:31`, `:102`, `:148-154`; the entry records the current `:38`, `:115`, `:194-195` |

## Findings, round 2

### F8 — a non-dict entry inside `non_recurring_items` dies while building the raise message · `note`

**Evidence:** `_parse_nri_response('{"non_recurring_items": ["we found none"]}')` →
`AttributeError: 'str' object has no attribute 'get'`.

**Rule or document:** none. The run **stops** and produces no figure, which is what rule 3
requires, so this is not a rule break. It is the same masking the `.get` choice was made
to avoid, one shape further out: the message that should say which field is missing never
prints. `_extract_json` guarantees `data` is an object, so only the *items* can arrive
with the wrong type.

**What would fix it:** nothing now. If a tester adds parser fixtures, one malformed-shape
case is worth pinning.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 8 — blanket `except Exception` | `ingestion/claude_extractor.py:990` (`BLE001`, one of the accepted 5) | **no.** I checked whether this unit's stops can be swallowed there: they cannot, because a `ValueError` does not match `(JSONDecodeError, KeyError)` on the first attempt. A reply whose *first* attempt is malformed JSON and whose *retry* omits the key still ends at `return []`, but that is item 8's swallow on lines this diff never touched, and the programmer raised it to you unprompted |
| 25 — adjustment whose year matches no statement | `analysis/normalizer.py` | no; seen again in the file under edit and left |
| 1 — zero-default census | — | no; **116 in both trees** |
| 36's schema half | — | no; correctly still out of scope |
| 2, 5, 6, 7, 10, 26, 29, 31, 32, 37, 38 | — | not re-reported, per your instruction |

The three items already queued for a tester — `models/financial_statements.py:28`, the
five dev scripts, the untested cache tuple unpack — are recorded and **not raised again**.

## Layering and the LLM boundary

Unchanged and still correct. This round's diff calls no model, adds no prompt field and
touches no client; it **removes** two defaults and adds three stops. `analysis/normalizer.py`
imports `dataclasses` and `models.financial_statements` only. The decision `low → not
applied` remains literal Python in `analysis/`, which is where rule 1 puts it.

One operational consequence, stated so nobody is surprised: a real filing whose Pass 2
reply omits `source` on one item now **aborts the whole extraction** after both passes
have been paid for, with no repair attempt — because routing this stop into the repair
retry would end at `return []` and rebuild F1. That is the rule working as intended, and
it is the right trade, but it is a live behaviour change for a paid run.

## Verdict

`approved`

**Both `major` findings are closed, and closed by the harder route in each case.** F1's
stop is structural, not cosmetic: I drove the wrapper with my own stub and the `ValueError`
leaves `_run_nri_pass` after exactly one LLM call in all three absent-key shapes, while an
explicit `[]` still returns `[]` — the swallow at `:990` is unreachable from it because a
plain `ValueError` is not an instance of `JSONDecodeError`. F3 was fixed rather than
defended, and the three `.get`s that survive are message diagnostics whose replacement by
subscripts would have re-created F1 through the `KeyError` catch — I verified that failure
mode rather than taking the argument on trust. F2 is a withdrawal, and it is the right
one: the three fiscal-2023 `sga` charges are 115 + 174 + 51 = **340** against an aggregate
whose own description says its components are not separately disclosed, and no cache on
disk holds a `low` item, so I also **withdraw my own round-1 repair suggestion** — the
magnitude genuinely cannot be sized from the data on disk, and the direction is all that
is certain. The withdrawal is unmistakable, it names every retired figure, and `$63.57`
appears nowhere in code, `STATUS.md` or the backlog. Criterion 7's real measurement is
intact — 13 `high` + 2 `medium` + **0** `low`, `applied` elementwise-identical to the raw
list, difference `$0.00`. Criterion 8 holds as a **set** against a fresh baseline export,
no test was edited, the guarded paths are clean and the caches were read and never
written. F4 through F7 remain open and are correctly deferred to the units you already
recorded; F8 is a `note` that breaks no rule. On the types gate: **18 in 6 is the harness
note's command, 14 in 4 is the documented gate, the 14 are a strict subset, and the four
extra are missing third-party stubs** — but `environment.md:148` is a dated baseline that
the file explicitly disclaims owning, and `STATUS.md:22` already carries the live 14, so
the thing to correct is the harness prompt, not the doc.
