---
agent: code_reviewer
assignment: P2-hygiene
round: 1
verdict: approved
---

# Review of P2-hygiene, round 1

Programmer entry: `.agent/journal/2026-09-20T2010-programmer-p2-hygiene.md`

Diff reviewed: `git diff HEAD -- analysis/ api/ config.py ingestion/ .gitignore models/company.py`,
plus the new untracked `ruff.toml`. `tests/**` and `tests/unit/` are `P1-suite`'s and were
excluded; `CLAUDE.md`, `README.md`, `docs/`, `STATUS.md`, `AGENTS.md`, `.claude/`,
`requirements-dev.txt` were already modified or created before this unit opened and are the
orchestrator's.

## The guard checks

Run over the eleven **Files in scope** only.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | 1 hit, `ingestion/claude_extractor.py:291` — **untouched line**, backlog item 1 |
| lookup with a fallback — `.get(k, 0)` | 53 hits, all in `claude_extractor.py`, `normalizer.py:69`, `routes_valuation.py:184` — **every one on an untouched line**, backlog items 1/3/10/12 |
| bare or-default — `or 0.0` | 5 hits (`routes_upload.py:56,61`, `claude_extractor.py:417-419`) — **untouched lines** |
| money field defaulted to zero — `: float = 0.0` | clean (the only two in scope died with `models/company.py`) |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | 3 hits (`normalizer.py:76`, `claude_extractor.py:418-419`) — **untouched lines**, pre-existing |
| dict of functions keyed by data | clean |
| model client imported outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → 0 hits |

Every hit is on a line this unit did not change. I verified that by hunk, not by assertion:
the only changed lines in `claude_extractor.py` are the import blocks at 56–66 and 386–391,
the three `f`-prefix removals at 785/796/806, and the blank line at 821; the only changed
lines in `normalizer.py` and `routes_valuation.py` are import blocks. The programmer
disclosed the `routes_valuation.py:184` site itself (its finding 3) and I agree with its
reading: `info.get("sharesOutstanding", 0) / 1e6` is a rule 3 site as well as the known
rule 5 site, and it zeroes the denominator of the headline per-share figure.

Census, executed on both trees rather than trusted:

```
new:  grep -rnE "<rules.md census regex>" --include=*.py models analysis api ingestion | wc -l  → 117
base: same command in a worktree at bc19431                                                     → 119
diff of the two site lists → only:
  models/company.py:    current_price: float = 0.0
  models/company.py:    diluted_shares_outstanding: float = 0.0
```

**Zero new rule 3 sites. The delta is exactly the two dead fields deleted with the dead file.**

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| the system clock, `datetime.now(UTC)` | yes — no fallback branch exists; it cannot be absent | `ingestion/price_fetcher.py:48` |
| `pd.__version__` | yes — `import pandas as pd` at module scope fails loudly first | `ingestion/price_fetcher.py:71` |
| `config.UPLOAD_DIR` | yes — a module constant; absence is `ImportError` | `api/routes_upload.py:24` |
| `UPLOAD_DIR.mkdir(exist_ok=True)` | not a value read. `exist_ok` suppresses `FileExistsError` only; a missing parent still raises `FileNotFoundError` naming the path | `api/routes_upload.py:24` |

`mkdir(exist_ok=True)` is idempotency, not a defaulted number. It supplies no figure and
hides no missing input. Agreed with the programmer.

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | not applicable — the unit reads and writes no financial figure |
| percentages converted at the route boundary, once | untouched; `routes_valuation.py` changed 2 lines, both imports |
| falsy not treated as missing | no new instance. The five recorded ones (`routes_valuation.py:150-154`) are untouched |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | **one pre-existing import survives** — see F1 |

## The three checks the orchestrator asked for by name

**1. `DTZ002` in `price_fetcher.py` — verified against the installed source, not accepted.**

The programmer's reasoning is correct and I reproduced it. `.venv/Lib/site-packages/yfinance/utils.py:454`:

```python
if dt.tzinfo is None:
    dt = _pd.Timestamp(dt).tz_localize(exchange_tz)   # wall-clock kept, instant moved
else:
    dt = _pd.Timestamp(dt).tz_convert(exchange_tz)    # instant kept, wall-clock moved
```

and the path is live for this call: `yf.download` → `scrapers/history.py:211,214` →
`utils._parse_user_dt(start, tz)` / `(end, tz)`. An aware datetime would therefore take the
`tz_convert` branch and move **both** window boundaries by the local UTC offset. Keeping it
naive is the only replacement that changes nothing.

The final expression is wall-clock identical to `datetime.today()` on **any** machine, not
just this one. `datetime.now(UTC)` is the instant; `.astimezone()` with no argument converts
it to the system local zone, whose wall-clock fields are by definition local time;
`.replace(tzinfo=None)` drops the label and leaves those fields. `datetime.today()` is the
same local wall clock. Measured here: `2026-09-20 20:41:02.052676` vs `…052701`, delta
2.5e-05 s, same date. The only attribute that can differ is `fold`, during a DST repeat
hour, and `fold` does not reach the date or the `timedelta` subtraction. **The date cannot
move. Not a blocker.**

**2. The moved `mkdir` — every writer reaches it.**

`grep -rn "UPLOAD_DIR" --include=*.py .` (excluding `.venv/`, `tests/`) → 3 hits: the
definition at `config.py:10`, and `routes_upload.py:13,24-25`. `_save_upload` is the only
function that opens a file under `UPLOAD_DIR` (`routes_upload.py:28`), and the only caller
is the single `POST /upload` route at `routes_upload.py:55`. `cli.py` mentions `uploads/`
once, in a comment at line 11, and writes nothing there. **No writer bypasses the `mkdir`.**
I also confirmed the programmer's live probe is consistent with the code: importing
`config` now creates nothing, and `mkdir` precedes the `open()` in the same function.

**3. `ruff.toml` adds nothing beyond what step 7 allows.**

The file contains exactly one top-level key, `target-version = "py314"`, and one table,
`[lint.per-file-ignores]` with `"api/*.py" = ["B008"]`. No `select`, no `ignore`, no
`extend-*`, no `exclude`. `py314` is truthful: `.venv/Scripts/python.exe -V` → `Python 3.14.4`.

I measured what the per-file ignore actually hides, rather than reading its comment:

```
.venv/Scripts/python.exe -m ruff check api --isolated --target-version py314
api\routes_upload.py:50:35: B008 …File… in argument defaults
api\routes_valuation.py:96:16: BLE001 …
api\routes_valuation.py:220:12: BLE001 …
```

It hides **one** diagnostic, the FastAPI `File(...)` idiom, and nothing else. `BLE001`
survives the ignore and is still an error. **Nothing recorded is suppressed.**

## The refusal on criterion 1 — right, and I would have made the same call

The unit returned `partial` because `target-version = "py314"` woke `UP017` in
`.claude/hooks/seal_baseline.py`. All three routes to green were correctly rejected:

- fixing the line is outside both the write scope and the Files in scope;
- lowering `target-version` to `py39` is a code change made to reach a target number rather
  than on a reason, and would have made the config state something false about a repository
  running 3.14.4;
- an `exclude` or an `UP017` ignore is forbidden by step 7 and would hide a correct finding —
  the same failure mode step 7 cites for `BLE001`.

Reporting the disagreement instead of working around it is what the assignment asks for. The
orchestrator has since fixed the line; criterion 1 now measures 4 and I have credited the
unit for the eight criteria it owns, not for that fix.

## Done-criteria, re-run

Every row below is a command I executed on the combined tree.

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | only deferred blind-excepts outside `tests/` | fail — 5 (4 `BLE001` + `.claude` `UP017`) | **4, every one `BLE001`**: `routes_valuation.py:96,220`, `cli.py:758`, `claude_extractor.py:795` | yes — the fifth was `.claude/`, now fixed by the orchestrator. **Passes** |
| 2 | type gate not worse | 33 errors, 4 files, 18 checked, "same 33" | 33 errors, 4 files, 18 checked. I did not take "same" on trust: ran mypy in a `bc19431` worktree, normalised line numbers, `diff` → **identical error set** | yes |
| 3 | `Company` gone | 0 hits | 0 hits | yes |
| 4 | no binary tracked | 0 | `git ls-files \| grep -icE "\.DS_Store\|^cache/"` → 0, and all four files still on disk at their original 6148/6148/11412/7435 bytes | yes |
| 5 | config import touches no directory | 0 in `config.py`, 2 in the route | same; plus the call-graph check above | yes |
| 6 | app imports, routes registered | exit 0 | exit 0, no output | yes |
| 7 | analysis modules import | `ok` | `ok`, exit 0 | yes |
| 8 | `BLE001` still an error | pass | pass, and proved by `--isolated` that the one ignore hides only `B008` | yes |
| 9 | no arithmetic changed | pass | **pass** — I read every hunk. No numeric literal, operator or expression changed anywhere in scope. `capm.py` renames two *discarded* unpack slots (`grep -n "intercept\|p_value" analysis/capm.py` → only the docstring and the unpacking); `fcff.py` drops a name with zero occurrences in the file; `price_fetcher.py:71` differs from the original only by the alias `_pd`→`pd`, both bound to the same module object | yes |

Eight of nine were already green. The ninth is green now. **Nine of nine.**

Two further measurements the assignment did not require:

- `pytest -q` → `1 failed, 19 passed`. The failure is
  `tests/unit/test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`,
  `P1-suite`'s deliberate red test against `analysis/dcf.py:80`. Not a regression from this unit.
- `tests/.cache_*.pkl` (3 files) remain tracked and `git check-ignore` returns no match for
  them — the new `cache/` pattern did not reach them, as the assignment required.

## Findings

### F1 — `analysis/capm.py:14` imports from `ingestion/`, and that layering break is not in the backlog · `note`

**Evidence:** `grep -rn "^from ingestion" analysis/ models/` → `analysis/capm.py:14:from ingestion.price_fetcher import PriceData` (only hit).
**Rule or document:** no rule in `docs/2-rules/rules.md`. It breaks the layering convention
(`analysis/` imports `models/`, `config`, stdlib, numpy, scipy — never `ingestion/`), which
is why it is a `note` and not a `major`.
**Not this unit's.** The line is unchanged context in the diff; the unit moved `import config`
past it to clear `I001` and left the line's text alone. It is also not listed in
`docs/9-reference/refactor-backlog.md`, so I am raising it for the orchestrator to record
rather than against this diff.
**What would fix it:** move `PriceData` into `models/`, so `analysis/capm.py` and
`ingestion/price_fetcher.py` both import it downward.

### F2 — `ingestion/claude_extractor.py:389` keeps a local `import re` that shadows the module-level one · `note`

**Evidence:** `ingestion/claude_extractor.py:60` `import re` (module scope) and
`ingestion/claude_extractor.py:389` `import re` inside `_call_gemini`.
**Rule or document:** none. Ruff does not flag it and both names bind the same module object,
so behaviour is identical.
**Touched-line test:** the unit *moved* this line (reordering `import re` above `import time`
to clear `I001`), so by the moving-a-line rule it is arguably the unit's. I am keeping it a
`note` because the assignment restricts this file to "imports and f-strings only", the move
was mandated by step 2, and deleting the line is a different edit from reordering it. The
programmer disclosed it unprompted.
**What would fix it:** delete line 389; the module-level `re` already covers the function.

### F3 — `.gitignore` gained `.DS_Store` and `.coverage` beyond the `cache/` the assignment named · `note`

**Evidence:** `git diff HEAD -- .gitignore` shows a `# macOS` block adding `.DS_Store` and a
`.coverage` line alongside the assigned `cache/`.
**Rule or document:** none. `.gitignore` is in scope, and ignoring `.DS_Store` is the natural
completion of step 8 — untracking the two `.DS_Store` files without ignoring them would leave
them as permanent untracked noise.
**Caveat I must state rather than hide:** `.gitignore` was **already modified in the working
tree before this unit opened** (it is in the pre-unit `git status`), and both edits are
uncommitted, so I could not mechanically separate the orchestrator's lines from the unit's.
I verified the only thing that matters: no tracked file became ignored
(`git check-ignore` on the three `tests/*.pkl` → no match; they remain tracked).
**What would fix it:** nothing. Recorded so the next reader does not attribute these lines
to the wrong unit.

No `blocker`, no `major`, no `minor`. Nothing in this unit cites a rule in
`docs/2-rules/rules.md`.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 — zero-default sites | 117 sites across `models/ analysis/ api/ ingestion/` | no — census fell 119→117, delta is the two deleted dead fields |
| 3 — NRI line-item guess | `analysis/normalizer.py:46` | no — import block only |
| 5 — rule 5 yfinance fallback (`rules.md` names it) / item 12 | `api/routes_valuation.py:180-184` | no — file diff is 2 lines, both imports. Seen, and left exactly as the assignment directed |
| 6 — falsy treated as missing | `api/routes_valuation.py:150-154` | no |
| 8 — blind `except Exception` | `routes_valuation.py:96,220`, `cli.py:758`, `claude_extractor.py:795` | no — deliberately left as the 4 visible lint errors |
| 10 — D&A subtraction in the parser | `ingestion/claude_extractor.py:479` | no |
| 11 — 33 type errors | 4 files | no — error set proved identical |

`config.py:14` still calls `load_dotenv(BASE_DIR / ".env", override=True)`, so importing the
config still *reads* the filesystem even though it no longer *writes* to it. The assignment
asked only for the directory creation to move, and the line is untouched. Noting it so it is
not rediscovered as new; it is not a finding.

## Open item the assignment asked me to carry forward

The lint gate's rule set is still unpinned — `ruff.toml` sets `target-version` but no
`select`, so the gate is ruff 0.16.8's built-in default. This unit put a number on the cost:
changing only `target-version`, with no source edit, moved the count from 4 to 5 and woke a
rule (`UP017`) that had been dormant repository-wide. A ruff upgrade can do the same with no
commit to point at. The programmer's finding 1 states this correctly; it belongs in the
backlog.

## Verdict

`approved`

Nine of nine done-criteria measured green, every one re-run rather than read. The unit added
no rule 3 site and removed two, changed no numeric literal, operator or expression, and
touched no line that carries a financial figure. The two changes that could have moved a
number do not: the `DTZ002` replacement is wall-clock identical to `datetime.today()` on any
machine and stays on yfinance's `tz_localize` branch, verified against the installed source
and the live `yf.download` call path; and the moved `mkdir` is reached by the only function
that writes an uploaded file, which is reached by the only route that accepts one. `ruff.toml`
holds exactly the two things step 7 permits, and I proved by `--isolated` run that its single
per-file ignore hides one `B008` and nothing else — `BLE001` is still an error at all four
recorded sites. The three findings are all `note`: none cites a rule, none blocks, and F1 is
a new backlog candidate rather than a defect in this diff. The programmer's refusal to reach
criterion 1 by lowering `target-version` or by adding an ignore was the right call and is the
reason this review is short.
