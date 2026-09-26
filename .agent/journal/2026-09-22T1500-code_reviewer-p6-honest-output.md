---
agent: code_reviewer
assignment: P6-honest-output
round: 1
verdict: changes_requested
---

# Review of P6-honest-output, round 1

Programmer entry: `.agent/journal/2026-09-22T1400-programmer-p6-honest-output.md`

Diff: 6 files, +625/−27, all six inside **Files in scope**. `git status --short` shows
nothing under `tests/`, `ingestion/`, `api/`, `static/`, `STATUS.md` or the journal
index. **No scope breach.**

## The guard checks

Over the six files in scope.

| Check | Result |
|---|---|
| conditional zero — `if … else 0.0` | 7 hits, **none added**: `cli.py:234,593,957,965`, `models/valuation.py:147,151,216` — all context lines, backlog item 1 |
| lookup with a fallback — `.get(k, 0)` | 1 hit, `cli.py:961` (yfinance share count) — context line, items 1/12 |
| bare or-default — `or 0.0` | clean |
| money field defaulted to zero — `: float = 0.0` | 10 hits, **none added**; the four new fields are `str`, not `float` |
| `**kwargs` on a calculation function | clean |
| `getattr(` on a name from outside the file | 1 hit, `cli.py:693` — context line, `getattr(overrides, field_name, None)` on a local dataclass |
| dict of functions keyed by data | clean. The new provenance constants are `Final[str]` printed verbatim; nothing indexes behaviour by them |
| model client outside `ingestion/` | clean — `grep -rnE "anthropic\|google\.genai\|from google" models/ analysis/ api/` → no output |

Census over added lines only reproduces the programmer's own result:

```
$ git diff -U0 -- cli.py config.py analysis/ models/ templates/ | grep "^+" \
    | grep -E "if [^)]+ else 0(\.0)?\b|\bor +(0|0\.0)\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0|\*\*kwargs|getattr\("
exit=1        (no output)
```

Every hit above is answered by number in the programmer's rule-3 table. **No hit is a
finding.**

## Rule 3, by reading

| Value | Stops and names it? | Evidence |
|---|---|---|
| each input PDF, `fingerprint_filings` | **yes**, names the path | `FileNotFoundError: extraction input 'C:\tmp\p6rev\files\nope.pdf' is not a readable file…` — `c:/tmp/p6rev/keycheck.py` |
| cache entry format marker, `_load_cache` | **yes**, names the file and three remedies | `ValueError: …foreign.pkl is not a cache entry written by this CLI (expected format marker 'p6-inputs-keyed-v1')…` — same script |
| `args.model` when `-m` absent | no — records the literal `"(provider default)"` | stable string, key component only, printed on every hit. Cannot cause a false hit. Accepted |
| `risk_free_rate` in `run_capm` | no — substitutes, now labelled | rule 6 by design; step 2 forbids the rule 5 half. Accepted |
| `interest_expense == 0` in `cost_of_debt_with_source` | no — substitutes, now labelled | **rule 6's own *Why* paragraph names this exact site as rule-6 territory.** Item 9 correctly closed as *labelled* |
| `total_debt == 0` → `0.0` | **no, and the unit touched the line** | `analysis/wacc.py`, `- return 0.0` / `+ return 0.0, (…)` — **F2** |

## Units and boundaries

| Check | Result |
|---|---|
| every financial figure in millions | clean — the diff adds no arithmetic. `cost_of_debt_with_source` is branch-for-branch the old `calculate_cost_of_debt`; the label prints `total_debt:,.0f` and `interest:,.0f` in the same units the fields carry |
| percentages converted at the route boundary, once | unchanged — no new conversion. `capm.risk_free_rate * 100` in the template matches the pre-existing rows |
| falsy not treated as missing | clean in the diff. `run_capm` branches on `risk_free_rate is not None`, not on truthiness. The five pre-existing `x / 100 if x else None` sites at `api/routes_valuation.py:150-154` are untouched (item 6) |
| `analysis/` imports no `ingestion/`, no `api/`, no model client | `analysis/capm.py:16` imports `ingestion.price_fetcher` — **pre-existing item 17.** The line was *shifted* by the `models.valuation` import expanding, not modified (context line in the diff). Recorded, not a finding. `analysis/wacc.py` clean |
| `models/` imports only stdlib / other `models/` | clean — `dataclasses`, `typing.Final` |

## Done-criteria, re-run

| # | Criterion | Programmer claimed | I measured | Agree? |
|---|---|---|---|---|
| 1 | different PDF, same ticker → **miss** | pass | **verified two ways, see below** | yes |
| 2 | unchanged PDF → **hit** | pass | identical key → `describe_key_difference` returns `[]`; order-swap, relative-vs-absolute path and ticker case all also return `[]` | yes |
| 3 | the miss names what changed | pass | `NEW input, not in the cached extraction: …_2024_English.pdf` + `the cached extraction was built from a file NOT supplied this run: …_2025_English.pdf` | yes |
| 4 | risk-free rate labelled when substituted, **in both outputs** | pass | **CLI yes; web page NEVER.** `ASSUMPTION — config.DEFAULT_RISK_FREE_RATE` absent from a real rendered page — **F1** | **no** |
| 5 | weak regression labelled beside the beta | pass | rendered page row `Beta — reliability`: `NOT RELIABLE — R-squared 0.181 is below the 0.200 minimum…`, one row under `Beta`. CLI prints it on the line under the beta | yes |
| 6 | substituted cost of debt labelled | pass | rendered page, interest 0 / debt 500: `ASSUMPTION — config.DEFAULT_COST_OF_DEBT (4.00%) was SUBSTITUTED…` | yes |
| 7 | no existing assertion changed meaning | `1 failed, 120 passed` | `pytest -q` → `1 failed, 120 passed`, failure = `test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent`. `git diff --stat -- tests/` and `git status --short -- tests/` both **empty** | yes |
| 8 | routes still serve | 200 | `GET /` **200**, `GET /assumptions` **200**, `POST /valuation` **200** (11,973 bytes, not an error page) | yes |
| 9 | lint 5 / types ≤14 / census ≤116 | 5 / 14 / 116 | **5 / 14 / 116** — see below | yes |

### Criterion 1 — the falsification, verified not assumed

I did not re-extract. I read both PDFs with `pdfplumber` and read the cache entry on
disk.

- **`17,062` appears 0 times in the FY2025 PDF** (89 pages, all text extracted):
  `grep -c "17,062" fy2025.txt` → `0`; `grep -c "17062"` → `0`. Its income statement
  reads `Total revenue 21,865 21,325 19,419`.
- **`17,062` appears in the FY2024 PDF** at `Total revenue 21,325 19,419 17,062`.
- The 18 occurrences of "2022" in the FY2025 PDF are director biographies, credit-agreement
  dates and one AOCI opening balance (`Balance at December 30, 2022`). **No fiscal 2022
  statement column exists in that document.**
- Independent corroboration: `cache/.cache_lhx_extraction_inputs.pkl` — the entry left on
  disk by run 3 — holds `years [2022, 2023, 2024]`, `revenues [(2022, 17062.0), …]`, keyed
  on the **FY2024** path at 1,795,814 bytes. And the FY2025 PDF's live sha256 is
  `8f0015ec0c73da4e…`, byte-for-byte the digest run 2's hit message printed.

**The proof is a proof.** Run 3 could not have replayed the FY2025 pickle.

### Criterion 2 — the key holds what is claimed

`c:/tmp/p6rev/keycheck.py`, fabricated files, no network, no extraction:

```
KEY: ExtractionKey(ticker='LHX', provider='claude', model='(provider default)',
  inputs=(InputFingerprint(year=2025, path='C:\tmp\p6rev\files\a.pdf', size_bytes=16,
          mtime_ns=1790101286604375700, sha256='425890168ac6702a…'),))
identical differences: []
content-changed-same-mtime differences: ['CONTENT CHANGED: …a.pdf  sha256 425890168ac6702a… -> 145e8cf4ce554376…, 16 -> 16 bytes']
mtime touched, same content -> mtime differs? True    pure-touch differences: []
provider diff: ["provider: cached 'claude', now 'gemini'"]
model diff:    ["model: cached '(provider default)', now 'x'"]
ticker diff:   ["ticker: cached 'LHX', now 'ABBV'"]
```

Resolved path, size, mtime_ns, sha256, ticker, provider, model — **all present**. A
content edit with the mtime restored **misses** (sha256 catches it, and the message names
the file and both digests). A pure `touch` with identical content is a **hit**, which is
what the entry's decisions table says ("sha256 is the authority … size/mtime make the miss
message checkable"). Order-swap, relative paths and lowercase ticker are all hits; a
fiscal-year re-assignment on the same file is a miss. This is a well-built key.

### Criterion 9 — the gates, measured

- Lint: `.venv/Scripts/python.exe -m ruff check .` → **`Found 5 errors`**, all `BLE001`.
- Types, the documented gate (`docs/8-build/environment.md:148`):
  `mypy models analysis ingestion api config.py app.py --ignore-missing-imports` →
  **14 errors in 4 files**. **Set-diffed, not counted**: `git archive d2ba1e5` exported to
  `c:/tmp/p6rev/base`, mypy re-run there, `comm` on the sorted error lists → **all 14 in
  the third column, first and second columns empty.** Identical sets, not identical counts.
- Census: the rule-3 grep from `rules.md` → **116** on HEAD and **116** on the `d2ba1e5`
  export.
- `GET /` → **200**.

### The R-squared threshold — checked, and it is derived

The identity `SE(β)/β = sqrt((1−R²)/(R²(n−2)))` is correct for a simple OLS slope
(`SE(b)²/b² = [SST(1−R²)/((n−2)Sxx)] · [Sxx/(R²·SST)]`). I confirmed it numerically
against `scipy.stats.linregress` on a synthetic 60-observation regression: observed
`SE/β = 0.3917`, predicted `0.3917`.

The comment's table at n = 60 recomputes as `0.2006 / 0.2626 / 0.3939`, and the 95%
intervals as `±39.3% / ±51.5% / ±77.2%`. The LHX cross-check holds both ways:
R² 0.099 → predicted 0.3961 against observed 0.196/0.493 = 0.3976; R² 0.098 → predicted
0.3984 against 0.196/0.492 = 0.3984.

**The derivation stands without LHX.** 0.20 is defined by a closed-form property of the
estimator — the point at which the 95% interval is about as wide as the estimate — and
LHX is quoted only as a check that the identity holds against the run's own printed
numbers. **This is not a number tuned to fail a case.** Minor arithmetic nit in F6.

### Rule 5 and the no-stop constraint

- **No treasury fetch was built.** `ingestion/` is untouched (`git status --short`), and
  `grep -rn "treasury|TNX|risk_free|\^IRX|DGS10" ingestion/` returns nothing.
- **A weak regression labels, it does not raise.** `describe_beta_reliability` returns a
  `str` on both branches; there is no `raise` in it. Proven by execution: the rendered
  page carries `NOT RELIABLE — R-squared 0.181 …` *and* an implied share price of $102.59.

## Findings

### F1 — criterion 4 is not met in the web output: the substituted-rate label is unreachable there, and the page instead tells the reader they supplied a rate they did not · `major`

**Evidence:** real `POST /valuation` through `TestClient`, `beta_override` and
`cost_of_debt_override` blank, no `risk_free_rate` in the form body:

```
  no   ASSUMPTION — config.DEFAULT_RISK_FREE_RATE
  YES  supplied by the caller (--risk-free-rate / ProjectionAssumptions.risk_free_rate)
```

`api/routes_valuation.py:140` is `risk_free_rate: float = Form(4.0)` and `:186` passes
`risk_free_rate=overrides.risk_free_rate`, which `:165` sets to `risk_free_rate / 100`
unconditionally. `run_capm` therefore **can never take the substituted branch on the web
path**, and the new page row names a CLI flag to a user who has never used one.

**Rule or document:** done-criterion 4, "shown in **both** outputs". Backlog item 34 is
claimed closed but is closed only on the CLI half. Rule 6 wants "a name, a default, **the
reason for that default**" — on the web the 4.00% is presented as caller-supplied, so its
default and the reason for it are never named.

**What would fix it:** make `risk_free_rate: str = Form("")` and drop `value="4.0"` from
`templates/assumptions.html:88`, exactly as `equity_risk_premium` beside it already works,
so an unfilled field reaches `run_capm` as `None`.

**Escalation, not blame.** Both files are explicitly **out of this unit's scope**, the
assignment told the programmer to "stop and say so", and it did — this is its own finding 1.
Per `docs/9-reference/severity.md`, "the fix belongs to a future unit" is not grounds to
downgrade; the orchestrator should widen scope to `api/routes_valuation.py` and
`templates/assumptions.html` rather than the programmer being asked to have done more.

### F2 — `total_debt == 0 → 0.0` is backlog item 22, and this unit touched the line · `major`

**Evidence:** `git diff -- analysis/wacc.py`: `-        return 0.0` →
`+        return 0.0, (` … at the `if total_debt == 0:` branch.

**Rule or document:** rule 3 — a zero that means "the balance sheet did not extract" and a
zero that means "debt-free" are the same bytes. Backlog item 22, open.

**What would fix it:** distinguish the two, which means `total_debt: float | None` in
`models/financial_statements.py` — out of scope here.

**Escalation.** The behaviour is byte-identical; the line was touched only because the
function's return arity changed to carry the label the assignment required, and the
programmer marked it in the code (`# KNOWN DEFECT, backlog item 22, NOT fixed here`) and
declared it by number in its own rule-3 table. But `severity.md` is unambiguous: "a defect
the unit touched is the unit's, backlog or not. Moving a line makes it yours," and I may
not downgrade a rule-3 citation to a `note`. **I am not asking the programmer to fix
item 22 inside this unit.** The orchestrator should either record a user decision covering
`analysis/wacc.py`'s zero-debt branch for this unit, or widen scope to close item 22. I am
not picking that side.

*(Its sibling, the `interest_expense == 0` substitution, is **not** a finding: rule 6's own
"Why" paragraph names `analysis/wacc.py:43` as the rule-6 exemplar and directs it to be
labelled. Item 9 is correctly closed.)*

### F3 — a user with an old-format cache pays for a full re-extraction and is told nothing · `minor`

**Evidence:** `cli.py:408` returns `.cache_{ticker}_extraction_inputs.pkl`; a pre-existing
`.cache_{ticker}_extraction.pkl` beside it is never a candidate path, so `cache.exists()`
is `False` and the run goes straight to `_step(1, "Extracting financials via …")` with no
message.

**Rule or document:** none. It contradicts the unit's own stated principle — the decisions
table rejects silently overwriting a cache because "re-extracting cost 272,204 input
tokens … silently discarding someone's paid extraction is worse than stopping and asking."

**What would fix it:** when the old name exists beside the new one, print one line saying
it is being ignored, why (unpickling executes code), and that this run will re-extract.

### F4 — `cli.py`'s two new stops escape `main()` as raw tracebacks · `minor`

**Evidence:** `cli.py:826` calls `build_extraction_key` outside the `try` at `:814-817`
that turns `parse_pdf_args`' `ValueError` into `SystemExit(f"ERROR: {exc}")`. Same for
`_load_cache`'s `ValueError` at `:828`.

**Rule or document:** none — rule 3 is satisfied, the run stops and names the path. Only
the presentation is inconsistent with the line two above it.

**What would fix it:** widen the existing `try` to cover both, or catch
`(FileNotFoundError, ValueError)` around them.

### F5 — a CLI-written cache entry cannot be read by anything that imports `cli` as a module · `minor`

**Evidence:**

```
$ .venv/Scripts/python.exe -c "import cli; cli._load_cache(Path('cache/.cache_lhx_extraction_inputs.pkl'))"
AttributeError: module '__main__' has no attribute 'ExtractionKey'
```

`ExtractionKey` and `InputFingerprint` are defined in `cli.py`, so running `python cli.py`
pickles them as `__main__.ExtractionKey`. The supported path (`python cli.py` again) works.
But the `AttributeError` is raised by `pickle.load` **before** the format-marker check, so
the helpful `ValueError` ("Delete the file, or run with `--no-cache`, or point
`--cache-dir` elsewhere") is unreachable for the most likely real corruption case — and the
tester the programmer asks for in its finding 5 will hit this on the first fixture built
from a real CLI run.

**Rule or document:** none.

**What would fix it:** move the two dataclasses into a module that is never `__main__`, or
serialise the key as a plain dict.

### F6 — one rounding slip in the threshold derivation · `note`

**Evidence:** `config.py` — `R^2 = 0.10  ->  SE/beta = 0.395`. The value is
`sqrt(0.90/(0.10·58)) = 0.3939`, i.e. **0.394**. The other two rows (0.201, 0.263) and all
three interval widths are exact.

**Rule or document:** none. A stale digit in a comment a reviewer is invited to check.

### F7 — `mtime_ns` and `size_bytes` are in `ExtractionKey` but are not compared · `note`

**Evidence:** `describe_key_difference` compares ticker, provider, model, path set, sha256
and year. It never reads `mtime_ns` or `size_bytes`. Verified: pure-touch → `[]` (a hit).

**Rule or document:** none. The behaviour is correct and the decisions table describes it
correctly. But the entry's summary sentence says the cache is "keyed on … mtime_ns", and
`ExtractionKey.__eq__` (frozen dataclass) *would* compare them — so a future caller that
writes `cached_key == current_key` instead of calling `describe_key_difference` gets
different, worse semantics with no warning.

**What would fix it:** one line in the `ExtractionKey` docstring saying `==` is not the
comparison, `describe_key_difference` is.

### F8 — the extraction is non-deterministic by 16% on the headline figure, and `confidence` is read nowhere · `note`, and it needs its own backlog item

Not a defect in this diff. The orchestrator asked for its precise shape; this is it.

**What varied** — same PDF, same prompt, two days apart (`c:/tmp/lhx_real.txt` vs
`c:/tmp/p6_run1.txt`):

| | 20 Sep run | 22 Sep run | cause |
|---|---|---|---|
| Pass 2 items / add-backs | 15 / **2,408M** | 14 / **1,268M** | 2,408 − 1,140 = 1,268 **exactly**. The missing item is 2023 `+1,140M on sga`, `"confidence":"low"`, source note `"components not separately disclosed for 2023"` |
| total debt | **10,443M** | **11,116M** | a different Pass 1 read of the balance sheet's debt lines. **No confidence flag exists on this figure at all** |
| implied share price | **$343.15** | **$296.01** | +15.9% |

**What did not vary:** the deterministic half. Beta 0.493 → 0.492 and R² 0.099 → 0.098 are
one extra trading day of yfinance; market price 240.21 → 240.23. Every moving part is
upstream of `analysis/`.

**A second axis, worth noting:** run 3 reads *fiscal 2023* out of the FY2024 filing and
finds `296+78+115+174+51+30 = 744M` of add-backs for that year, against `374+77 = 451M`
(or 1,591M with the low-confidence item) from the FY2025 filing. The same fiscal year,
read from two documents, normalises differently.

**Does the pipeline have the information to detect it?** Half.

```
$ grep -rn "confidence" models/ analysis/ api/ cli.py
models/financial_statements.py:28:    confidence: str = "high"   # "high" | "medium" | "low"
cli.py:624:  f"({item.confidence} confidence)  line_item={item.line_item}"
$ grep -c "confidence" analysis/normalizer.py
0
```

- For **Pass 2 items** the information exists and is thrown away. `analysis/normalizer.py`
  never reads `confidence`; `apply_adjustments` weights a `low`-confidence 1,140M add-back
  identically to a `high` one. It surfaces in exactly one place — a `print` in `cli.py:624`
  — and **nowhere on the web result page.** Worse, `ingestion/claude_extractor.py:702` is
  `confidence=item.get("confidence", "high")`: an item whose confidence the model did not
  state is recorded as the *strongest* value. That is a rule-3 shape the `rules.md` census
  regex does not match, so it is not among the 116.
- For **Pass 1 statement figures** — the 10,443 → 11,116 debt swing — the schema carries
  no confidence field at all. `confidence` exists only on `NonRecurringItem`. The pipeline
  has **no** information with which to detect that variance.

`grep -n "confidence" docs/9-reference/refactor-backlog.md` returns nothing. **This is
unrecorded and it is larger than anything this unit fixed.** It deserves a backlog item
and its own work unit: a `low`-confidence add-back that moves the share price 16% is a
decision nobody has taken.

## Pre-existing, already recorded — not findings against this unit

| Backlog item | `file:line` | Touched by this unit? |
|---|---|---|
| 1 | 116 zero-default sites across `models/`, `analysis/`, `api/`, `ingestion/` | no — census 116 on HEAD and on `d2ba1e5` |
| 2 | `analysis/dcf.py:80` zero net debt; `test_dcf_rule3_red.py` stays red | no |
| 6 | `api/routes_valuation.py:150-154`, falsy treated as missing, five times | no |
| 8 | `cli.py` blanket `except Exception` (now ~:1035) | no — lint still 5 `BLE001`, same five files |
| 12 | `cli.py:961` yfinance share-count fallback | no |
| 17 | `analysis/capm.py:16` imports `ingestion.price_fetcher` | **shifted, not modified** — context line in the diff; the `models.valuation` import above it expanded. Recorded, and I say so as the assignment asked |

**The two stale pickles are untouched.** Measured after the three runs:

```
.cache_abbv_extraction.pkl        11412  mtime_ns=1789921463314647500  (20 Sep 12:24)
.cache_lhx_extraction.pkl          7435  mtime_ns=1789921463317007100  (20 Sep 12:24)
.cache_lhx_extraction_inputs.pkl   6621  mtime_ns=1790100739411473900  (22 Sep, run 3)
```

Sizes and mtimes match the pre-build state the assignment records. They could not have been
loaded: `grep -n "_extraction.pkl\|_extraction_inputs.pkl" cli.py` → `398` (a docstring
explaining why the name was abandoned) and `408` (the `_inputs` name actually built).

## Verdict

`changes_requested`

The in-scope engineering is strong and I want to say so plainly: the cache key is the best
piece of work in this diff — content-addressed, order-independent, path-resolved,
provider-aware, it refuses to unpickle a file it did not write, and its miss message names
the file rather than announcing a miss. I verified criterion 1 by falsification rather than
by assertion and it holds: `17,062` exists in the FY2024 filing and appears **zero** times
in the FY2025 one, and the cache entry left on disk proves run 3 read the file on its
command line. The R² threshold is genuinely derived from a closed-form property of the OLS
slope, not reverse-engineered from LHX — I recomputed every figure in its comment and
checked the identity against `scipy`. No treasury fetch was built, a weak regression labels
without stopping, `tests/` is unedited, and all four gates are unchanged with mypy
**set**-diffed against a `d2ba1e5` export rather than counted.

Two `major` findings stand, and **neither is a mistake the programmer made** — both are
lines its assignment placed out of reach, and it raised the first one itself. **F1**: done-
criterion 4 says the substituted risk-free rate is shown in *both* outputs, and on the web
it can never be, because `api/routes_valuation.py:140` is `Form(4.0)` — so backlog item 34
is half closed and the page now tells a reader they supplied a rate the form supplied for
them. **F2**: `analysis/wacc.py`'s `total_debt == 0 → 0.0` is rule 3 and backlog item 22,
and this diff touched the line; `severity.md` forbids me filing that as a note. Both need
the orchestrator to widen scope or record a decision, not another round from the programmer
against the same brief.

Separately, **F8 is the most consequential thing in this review and it is not this unit's
defect**: the same PDF extracted twice disagrees by 16% on the share price, the largest
single cause is a 1,140M item the model itself tagged `confidence: low`, and nothing in
`analysis/` reads `confidence` — while the 673M swing in total debt has no confidence
signal in the schema at all. It is unrecorded. It needs a backlog item and its own unit.
