---
agent: programmer
assignment: P6-honest-output
round: 1
status: complete
files_touched: [cli.py, config.py, analysis/capm.py, analysis/wacc.py, models/valuation.py, templates/valuation_result.html]
verdict: —
---

# P6-honest-output — the cache stops answering a question it was not asked, and the three unmeasured inputs say so

> Opened before the first command. Filled as each result landed.

## What I did

Four defects, one family: the output presented something as more solid than it was.

**Item 33, the unit.** The extraction cache was keyed on the ticker alone. It is now
keyed on the input files themselves — resolved path, size, mtime\_ns and a **sha256 of
the content** — together with the ticker, the provider and the model. The key is stored
*inside* the cache entry and compared on read, not encoded into the filename, because a
filename-encoded key can only ever produce a silent miss; comparing on read is what lets
the miss print **which file changed and what it changed from**. Proved by the three runs
step 6 asked for, against the user's real L3Harris filings: the FY2024 PDF under ticker
`LHX` is now a miss that names both files, and the re-extraction it triggers returns
fiscal years **2022–2024** with 2022 revenue **17,062** — a year and a figure that exist
nowhere in the FY2025 filing whose pickle used to be served in its place.

**Items 34, 35 and 9, the labelling.** `CAPMResult` gained `risk_free_rate_source`,
`beta_source` and `beta_reliability`; `WACCResult` gained `cost_of_debt_source`. Each is
a plain string with a default that says *"not recorded"*, assigned by the one function
that knows which branch fired, and printed verbatim by both output layers. `config.py`
gained `MINIMUM_BETA_R_SQUARED = 0.20`, derived in its comment from the standard error of
an OLS slope at n = 60 rather than picked; the comments on `DEFAULT_RISK_FREE_RATE` and
`DEFAULT_COST_OF_DEBT` were rewritten, the first because it claimed to be a fallback for
a market fetch that does not exist.

**I built no treasury fetch** (step 2 and rule 5) and **the weak regression does not stop
the run** (step 3). Beta 0.492 with R² 0.098 on the real LHX run is a real measurement of
a weak relationship; it is now labelled `NOT RELIABLE` on the line under the beta, and it
still produces a number.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | a different PDF, same ticker, is a cache **miss** | **pass** | run 3 below. Miss, then a real extraction returning years **2022–2024**, never in the FY2025 filing |
| 2 | an unchanged PDF is a cache **hit** | **pass** | run 2 below — `Done in 2s` |
| 3 | the miss says what changed | **pass** | run 3 names both files by full path |
| 4 | the risk-free rate is labelled when substituted | **pass** | run 1's CAPM block and summary; the rendered page, `c:/tmp/p6_route.py` |
| 5 | a weak regression is labelled beside the beta | **pass** | run 1, R² 0.098 on the real LHX filing; and the page |
| 6 | a substituted cost of debt is labelled | **pass** | `c:/tmp/p6_labels.py`, all four branches; and the page, interest 0 with debt 500 |
| 7 | no existing assertion changed meaning | **pass** | `pytest -q` → `1 failed, 120 passed`, the failure being `test_dcf_rule3_red.py` |
| 8 | the routes still serve | **pass** | `GET /` **200**, `GET /assumptions` 200, `POST /valuation` 200 |
| 9 | lint 5 / types ≤14 / census ≤116 | **pass** | **5 / 14 / 116**, all unchanged |

### Criteria 1, 2 and 3 — the three runs, in order, against `./cache`

The two stale pre-build pickles sat in `./cache` throughout. They were neither deleted
nor loaded; see "the stale pickles" below.

**Run 1 — FY2025, a real extraction, a cache written.**

```
$ .venv/Scripts/python.exe cli.py "10K_filings/LHX/L3Harris Technologies Inc._10-K_2025_English.pdf" \
    -t LHX -n "L3Harris Technologies Inc." --cache-dir ./cache

>>> [1/10] Extracting financials via CLAUDE — 1 PDF(s)  (0s elapsed)
  PDF: L3Harris Technologies Inc._10-K_2025_English.pdf (1.3 MB)
  [Pass 1] Tokens — input: 272,204  output: 2,745
  [Pass 2] Tokens — input: 271,168  output: 1,965
  Cached to .cache_lhx_extraction_inputs.pkl, keyed on the file(s) just read
  Years extracted: [2023, 2024, 2025]
>>> Done in 1:05
```

**Run 2 — the identical command. A hit, in two seconds, that names what it is keyed on.**

```
>>> [1/10] Loading cached extraction  (0s elapsed)
======================================================================
LOADING CACHED EXTRACTION: .cache_lhx_extraction_inputs.pkl
======================================================================
  Reused because every input matches the run that produced it:
    - L3Harris Technologies Inc._10-K_2025_English.pdf  sha256 8f0015ec0c73da4e…  1,342,857 bytes
    - read by claude / (provider default)
  No PDF was opened and no extraction was paid for on this run.
  Years extracted: [2023, 2024, 2025]
>>> Done in 2s
```

**Run 3 — FY2024, same ticker, same cache dir. This is the run that failed before.**

```
>>> [1/10] Cached extraction REJECTED — the inputs changed  (0s elapsed)
======================================================================
CACHE MISS: .cache_lhx_extraction_inputs.pkl answers a different question
======================================================================
  The cached extraction was NOT used. What differs:
    - NEW input, not in the cached extraction: C:\…\10K_filings\LHX\L3Harris Technologies Inc._10-K_2024_English.pdf
    - the cached extraction was built from a file NOT supplied this run: C:\…\10K_filings\LHX\L3Harris Technologies Inc._10-K_2025_English.pdf

  A cached extraction is only reused when the files, the ticker, the provider
  and the model all match. Re-extracting from the files named on the command line.

>>> [1/10] Extracting financials via CLAUDE — 1 PDF(s)  (0s elapsed)
  PDF: L3Harris Technologies Inc._10-K_2024_English.pdf (1.7 MB)
  [Pass 1] Tokens — input: 603,715  output: 2,211
  Years extracted: [2022, 2023, 2024]
>>> Done in 1:21
```

**"It ran" is not the evidence. This is.** Run 3 did not replay run 1:

| | Run 1 (FY2025 PDF) | Run 3 (FY2024 PDF) |
|---|---|---|
| years extracted | 2023, 2024, 2025 | **2022, 2023, 2024** |
| revenue, $M | 19,419 / 21,325 / 21,865 | **17,062** / 19,419 / 21,325 |
| Pass 1 input tokens | 272,204 | **603,715** |
| implied share price | $296.01 | **$406.95** |

Revenue **17,062** for fiscal 2022 appears nowhere in the FY2025 document — it is printed
in the FY2024 one. An input to the displayed figure came from the file named on the
command line. **Before this change the third command returned $296.01 in two seconds,
from a pickle, under a FY2024 command line.**

### Criterion 5 — the beta label, on the real filing

From run 1, verbatim:

```
  Beta:                 0.492
      source: measured — OLS regression of this stock's returns on the S&P 500's, over the
      price history named beside it
      reliability: NOT RELIABLE — R-squared 0.098 is below the 0.200 minimum in
      config.MINIMUM_BETA_R_SQUARED. The market explains only 9.8% of this stock's return
      variation over 60 observations, so beta 0.492 carries a standard error of 0.196.
      Treat the cost of equity, the WACC and the implied share price below as uncertain by
      a wide margin, and consider supplying a beta with --beta.
  R-squared:            0.098
  Std error:            0.196

  Risk-free rate:       4.00%
      source: ASSUMPTION — config.DEFAULT_RISK_FREE_RATE. No rate was supplied and this
      platform fetches no treasury series, so the configured constant was substituted. It
      is not a measurement of any market.
```

The verdict is on the line **under** the beta, not two lines past the diagnostics, which
was the complaint. And a gathered block follows the final summary, for the reader who
scrolls to the answer:

```
======================================================================
WHAT IN THIS VALUATION WAS NOT MEASURED
======================================================================
  Extraction source
    live extraction of L3Harris Technologies Inc._10-K_2025_English.pdf
  Risk-free rate
    4.00% — ASSUMPTION — config.DEFAULT_RISK_FREE_RATE. …
  Beta
    0.492 — measured — OLS regression …
    reliability: NOT RELIABLE — …
  Cost of debt (pre-tax)
    5.37% — measured from the filing: interest expense 597 / total debt 11,116
```

On run 2 the first entry instead reads `cached extraction reused from
.cache_lhx_extraction_inputs.pkl, keyed on the 1 file(s) above`.

### Criterion 6 — all four cost-of-debt branches, `c:/tmp/p6_labels.py`

```
interest 0, debt 10,443   rate = 4.0000%
  ASSUMPTION — config.DEFAULT_COST_OF_DEBT (4.00%) was SUBSTITUTED, because interest
  expense is not reported separately (0) while the balance sheet carries 10,443 of debt,
  so interest / total debt cannot be computed. This is a guess at a coupon, it is not this
  company's, and it reaches the WACC and the implied share price.

interest 597, debt 10,443 rate = 5.7167%
  measured from the filing: interest expense 597 / total debt 10,443

total debt 0              rate = 0.0000%
  0% because total debt on the balance sheet is 0. If that zero means the debt figures did
  not extract rather than that the company is debt-free, this rate is wrong and so is the
  WACC (backlog item 22).

caller override 0.055     rate = 5.5000%
  supplied by the caller (--cost-of-debt / ProjectionAssumptions.cost_of_debt_override).
  Not derived from the filing.
```

### Criteria 4, 5, 6 and 8 — the rendered page, over a real ASGI request

`c:/tmp/p6_route.py`, `TestClient(app.app)`, extraction and yfinance faked at the
boundary, `beta_override` and `cost_of_debt_override` left **blank** so the regression and
the substitution branches both fire, and interest expense 0 against 500 of debt.

```
GET /            -> 200
GET /assumptions -> 200
POST /valuation  -> 200 (10606 bytes)
error page?      -> False

=== CAPM & WACC ===
  Beta                       0.869
  Beta — source              measured — OLS regression of this stock's returns on the S&P 500's, …
  Beta — reliability         NOT RELIABLE — R-squared 0.110 is below the 0.200 minimum in
                             config.MINIMUM_BETA_R_SQUARED. … so beta 0.869 carries a standard
                             error of 0.324. …
  R-squared                  0.110
  Std error of beta          0.324
  Risk-Free Rate             4.00%
  Risk-Free Rate — source    supplied by the caller (--risk-free-rate / …). Still an
                             assumption, not a measurement: nothing in this platform reads a
                             treasury rate.
  Cost of Debt (pre-tax)     4.00%
  Cost of Debt — source      ASSUMPTION — config.DEFAULT_COST_OF_DEBT (4.00%) was SUBSTITUTED,
                             because interest expense is not reported separately (0) while the
                             balance sheet carries 500 of debt …

=== What in this valuation was not measured ===   (the gathered block, same three)
```

`api/routes_valuation.py` was **not touched**. Nothing needed plumbing there: the route
already puts `capm_result` and `wacc_result` straight into the template context, so
carrying the labels on those two objects put them on the page for free. That was a
deciding reason for putting them there rather than in a parallel structure.

**Note on the web risk-free rate.** `api/routes_valuation.py:140` declares
`risk_free_rate: float = Form(4.0)` and `templates/assumptions.html:85` prefills the field
with `4.0`, so the web path always reaches `run_capm` with a value and always reports
"supplied by the caller". That is honest as far as it goes — the sentence ends "**Still an
assumption, not a measurement: nothing in this platform reads a treasury rate**" — but the
user is being shown a config-shaped default through a form field and told they supplied
it. See finding 1.

### Criteria 7 and 9 — the gates, before and after

| Gate | Before (clean tree) | After | Verdict |
|---|---|---|---|
| Tests | `1 failed, 120 passed` | **`1 failed, 120 passed`** | identical failure set: `test_dcf_rule3_red.py::test_run_dcf_stops_when_the_balance_sheet_is_absent` |
| Lint | 5, all `BLE001` | **5, all `BLE001`** | same five files; `cli.py` moved 758 → 1035 |
| Types | 14 in 4 files | **14 in 4 files** | unchanged |
| Rule-3 census | 116 | **116** | unchanged |
| `GET /` | 200 | **200** | — |

`tests/unit/test_capm.py`, `test_wacc.py` and `test_dcf.py` — the 45 assertions that read
`CAPMResult` and `WACCResult` most closely — pass: `45 passed in 2.92s`.

**On the 40 assertions in `models/valuation.py` I may not edit: I checked, and the file
contains no `assert` at all** (`grep -c '^\s*assert' models/valuation.py` → 0). The
assertions that bind it live in `tests/unit/`, which I did not touch. **Every field I
added carries a default**, so every construction that predates them still builds — which
is what the 120 passing tests demonstrate, since five of those test files construct these
objects positionally and by keyword. One existing route assertion *did* go red on my first
attempt and I moved my code, not the test; see the decisions table.

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| The key is stored **in** the entry and compared on read, not hashed into the filename | A filename-encoded key produces a miss you cannot explain: the old entry is not locatable, so the run can only say "miss". Step 1 requires it to "name what changed" | Comparing on read gives the previous key for free, which is exactly what criterion 3 needs |
| The cache file is renamed to `.cache_{ticker}_extraction_inputs.pkl` | Unpickling **executes code in the pickle**, so the two stale pre-build files must not be opened even to reject them. A new name means the old path is never a candidate | A format check after `pickle.load` would already have run the payload. The rename is the only way to not load them |
| sha256 **and** size **and** mtime, not one of them | The assignment permits "modification times **or** a content hash". sha256 is the authority — a file rewritten with its timestamp preserved still changes it — and size/mtime make the miss message checkable against `ls -l` | mtime alone is defeated by a touch or a restore; a hash alone gives the reader nothing to verify against |
| Provider and model are in the key too | Same defect. `P2b-provider` made the output state which model produced the figures; serving a Gemini extraction under a `CLAUDE` label prints a **false label**, not merely a stale number | Slightly wider than the letter of step 1. I flag it for review rather than hide it |
| A cache file in this format's name that this CLI did not write **raises**, and is not overwritten | Re-extracting cost 272,204 input tokens on run 1. Silently discarding someone's paid extraction is worse than stopping and asking | Treating it as a miss would spend money without consent |
| `fingerprint_filings` **raises** `FileNotFoundError` on a missing input | Rule 3. A cache decision taken from a file the run cannot read is a guess | Skipping the file would let a hit be declared on an incomplete input set |
| `cost_of_debt_with_source` is new; `calculate_cost_of_debt` stays and delegates to it | `tests/unit/test_wacc.py` calls `calculate_cost_of_debt` directly and compares its float return. Changing that signature would change the meaning of existing assertions — criterion 7 | Re-deriving the label in a second function would let label and number drift apart. One function knows, one function says |
| The labels are **strings on the result dataclasses**, not a lookup structure | Rule 2 forbids looking up *behaviour*. Nothing indexes a function by these; the producing function assigns one and two output layers print it | A parallel dict keyed by a label name would be the registry rule 2 bans |
| Every new field defaults to a sentence that says **"not recorded"** | A default reading "measured" would be the exact defect these fields close. A default of `""` renders as a blank cell, which a reader takes for "fine" | Rule 6 wants the assumption visible; an invisible default is not visible |
| `MINIMUM_BETA_R_SQUARED = 0.20`, derived in the comment | SE(β)/β = sqrt((1−R²)/(R²(n−2))). At n = 60, R² = 0.20 gives SE/β = 0.263, a 95% interval of ±52% — about as wide as the estimate. The identity is checkable against any run's own output: LHX printed β 0.492 and SE 0.196, ratio 0.398, against 0.396 predicted from R² 0.098 | Picking a number that happens to fail LHX would be tuning to a target. The derivation stands independently of LHX, and **LHX is quoted as a check of the identity, not as its source** |
| The weak verdict **does not stop the run** | Step 3 in as many words, and rule 6 vs rule 3. The data are present and the arithmetic is sound; the relationship is weak. A defence contractor whose returns track its order book rather than the index is the normal case | A stop here would refuse legitimate runs |
| An overridden beta gets `BETA_RELIABILITY_NOT_ASSESSED`, never "weak" | `analysis/capm.py` sets `r_squared = 0.0` on that path, meaning "no regression ran". Judging that 0.0 against the threshold would accuse an overridden beta of failing a test it never took | The underlying zero-default is backlog item 1 and is **not** fixed here; `beta_source` now tells the two zeros apart |
| The page labels sit in **their own `<tr>`**, not inside the value's `<td>` | My first attempt put them in the same cell and turned `tests/unit/test_routes.py::test_post_valuation_renders_the_completed_valuation` red on `assert capm["Beta"] == "1.000"`. **I moved my code, not the test** | I may not edit `tests/`, and more importantly that assertion was right: the Beta cell should contain the beta |
| The provenance style is an inline `style=` attribute | `static/style.css` is **not** in my Files in scope, so a `.provenance` class could not be defined there. An inline style keeps the change inside `templates/` | Widening my own scope, which the brief forbids. Flagged as finding 3 |

**No code change in this unit was made to reach a target number.** The one figure this
unit could have been accused of steering — the R² threshold — is derived from a
closed-form property of an OLS slope, and the derivation is in `config.py` where a
reviewer meets it.

### Run 1 does not reproduce `c:/tmp/lhx_real.txt`, and that is the extractor, not me

The earlier real run gave $343.15; run 1 gives $296.01 off the same PDF. I chased this
rather than report the number:

| | `lhx_real.txt` | run 1 | what it is |
|---|---|---|---|
| Pass 2 items | 15, add-backs 2,408M | 14, add-backs **1,268M** | the missing item is 2023's `+1,140M on sga`, the one the model itself marked **`confidence: low`** with "components not separately disclosed for 2023". 2,408 − 1,140 = 1,268 exactly |
| total debt | 10,443 | **11,116** | a different Pass 1 read of the balance sheet's debt lines |
| adjusted operating margin | 12.28% | 10.32% | follows from dropping the 1,140M add-back, which inflated 2023 adjusted EBIT |
| beta / R² | 0.493 / 0.099 | 0.492 / 0.098 | one more day of yfinance prices; market price 240.21 → 240.23 |

**Every one of those is upstream of my diff.** My changes touch no arithmetic: the
risk-free selection is the same `if/else` in a different shape, the beta-override branch
is unchanged, and `cost_of_debt_with_source` is branch-for-branch the old
`calculate_cost_of_debt`. The 120 passing hand-derived assertions are the evidence for
that, not my say-so. **The volatility itself is a real finding and it is finding 2 below.**

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| each input PDF, in `fingerprint_filings` | **stops**, naming the path | `FileNotFoundError: extraction input 'C:\tmp\p6_dry\does-not-exist.pdf' is not a readable file, so its content cannot be fingerprinted and no cache decision can be made about it` — `c:/tmp/p6_cache_dryrun.py` |
| the cache entry's format marker | **stops**, naming the file and three remedies | `ValueError: … is not a cache entry written by this CLI (expected format marker 'p6-inputs-keyed-v1'). Delete the file, or run with --no-cache, or point --cache-dir elsewhere.` — same script |
| `args.model` when `-m` is not given | **does not stop.** Recorded in the key as the literal string `"(provider default)"` | `cli.py`, `build_extraction_key`. Not a money field and not an input to a calculation: it is a key component, and it is *stable* — the same absent `-m` gives the same string, so it can never cause a false hit. It is printed on every cache hit |
| `risk_free_rate` in `run_capm` | **does not stop — substitutes `config.DEFAULT_RISK_FREE_RATE`.** Unchanged behaviour, now labelled | This is the rule 6 half by design: a risk-free rate is not extracted from a filing, so no measurement is being papered over. Step 2 forbids the rule 5 half |
| `interest_expense` in `cost_of_debt_with_source` | **does not stop — substitutes `config.DEFAULT_COST_OF_DEBT`.** Unchanged behaviour, now labelled | Backlog item 9, closed as *labelled*. Whether it should stop instead is item 1's question, not this unit's |
| `balance_sheet.total_debt == 0` | **does not stop — returns 0.0.** Unchanged, now labelled, and the label names the ambiguity | **Backlog item 22, still open.** This is a genuine "defaults to" row and I am writing it as the template requires |

**Three "defaults to" rows are findings against my own unit and I am not hiding them.**
All three are pre-existing behaviour this assignment told me to *label*, not to stop
(step 2: "Labelling closes the rule break on its own"; step 3: "Do not stop the run"), and
items 1, 9 and 22 own the rest. **I added no new default.** The census grep over my own
diff returns nothing:

```
$ git diff -U0 -- cli.py config.py analysis/ models/ templates/ | grep "^+" \
    | grep -E "if [^)]+ else 0(\.0)?\b|\bor +(0|0\.0)\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0|\*\*kwargs|getattr\("
exit=1        (no output)
```

## Rules 1, 2, 4, 5 and 6

- **Rule 1.** No prompt, no schema field, no extractor code was touched. `ingestion/` is
  untouched — `git diff --stat` lists six files and none is in it. No number in this diff
  came from a model.
- **Rule 2.** Five new functions, every one named with a fixed typed signature:
  `fingerprint_filings`, `build_extraction_key`, `describe_key_difference`,
  `cost_of_debt_with_source`, `describe_beta_reliability`. No `**kwargs`, no `getattr` on
  an outside name, no dict of functions.
- **Rule 4.** Improved, not closed. A reader of the output can now name where the
  risk-free rate, the beta and the cost of debt came from, and which files the extraction
  read. The chain from a share price back to a filing page is still not on the page.
- **Rule 5.** **No new data source.** `grep -rn "treasury\|TNX\|risk_free" ingestion/`
  still returns nothing, because I did not touch `ingestion/`.
- **Rule 6.** This is the unit. Four assumptions that reached the share price invisibly
  are now named, defaulted on the record in `config.py` with the reason, and shown in
  both outputs.

## The stale pickles

Not deleted, not loaded, not written to.

```
$ ls -la cache/
-rw-r--r--  11412  Sep 20 12:24  .cache_abbv_extraction.pkl     <- untouched, pre-build
-rw-r--r--   7435  Sep 20 12:24  .cache_lhx_extraction.pkl      <- untouched, pre-build
-rw-r--r--   6621  Sep 22 14:12  .cache_lhx_extraction_inputs.pkl  <- written by run 1
```

Both keep their 20 September size and mtime after three runs against that directory. They
could not have been loaded: the only occurrence of the string `_extraction.pkl` in
`cli.py` is inside the docstring explaining why that name was abandoned —
`grep -n "_extraction.pkl\|_extraction_inputs.pkl" cli.py` returns `398:` (a docstring
line) and `408:` (the `_inputs` name that is actually built).

## Measurements

Diff: **6 files, +625 / −27.** `cli.py` +289, `models/valuation.py` +78, `config.py` +65,
`analysis/capm.py` +90, `analysis/wacc.py` +82, `templates/valuation_result.html` +48.
Every one is in Files in scope. `api/routes_valuation.py`, `ingestion/`, `static/` and
`tests/` are untouched.

**Extraction spend: exactly the three runs step 6 required.** Run 1 272,204 + 271,168
input tokens; run 2 **zero** (the hit); run 3 603,715 + 602,677. The FY2023 filing (191
pages) **was not opened**. `c:/tmp/p6_labels.py`, `c:/tmp/p6_route.py` and
`c:/tmp/p6_cache_dryrun.py` make no network call at all — the cache dry run is what
confirmed the key logic before any money was spent.

**Figures this unit moved:** none, in any valuation. Run 1's $296.01 and run 3's $406.95
differ from `lhx_real.txt`'s $343.15 for the extraction reasons tabulated above, all
upstream of this diff. **Treat all three as measurements of the pipeline, not as
valuations of L3Harris** — run 1's own output now says, in the block below its own share
price, that the beta it rests on is not reliable.

**Scratch, all outside the repository:** `c:/tmp/p6_labels.py`, `c:/tmp/p6_route.py`,
`c:/tmp/p6_route_body.html`, `c:/tmp/p6_cache_dryrun.py`, `c:/tmp/p6_dry/`,
`c:/tmp/p6_run{1,2,3}.txt`. Nothing was copied into the repository. `TestClient` opens no
socket, so there is no server to stop.

## What I did not do

- **Did not build a treasury fetch.** Step 2, rule 5. `DEFAULT_RISK_FREE_RATE` is
  labelled, not sourced.
- **Did not stop a weak regression.** Step 3.
- **Did not touch `api/routes_valuation.py`.** It needed no plumbing; the two result
  objects already reach the template.
- **Did not touch `tests/`, `ingestion/`, `static/`, `STATUS.md` or the journal index.**
- **Did not fix backlog item 1's zeros in `analysis/capm.py`** (`r_squared = 0.0` and
  `std_error = 0.0` on the override path). They are labelled, not removed; changing them
  to `float | None` would change what existing assertions mean.
- **Did not fix backlog item 22** (`total_debt == 0` → 0% cost of debt). Labelled only,
  and the label names the ambiguity.
- **Saw and left `analysis/capm.py:14`** — now line 16 — `from ingestion.price_fetcher
  import PriceData`. Backlog item 17, a layering break, not mine. **I note I saw it**, as
  the assignment asked.
- **Saw and left** `cli.py`'s blanket `except Exception` (item 8, now line 1035) and
  `cli.py`'s yfinance share-count fallback in stage 8 (items 1 and 12, rule 5).

## Findings for the orchestrator

1. **The web path can never report a substituted risk-free rate, and the CLI can.**
   `api/routes_valuation.py:140` is `risk_free_rate: float = Form(4.0)` and
   `templates/assumptions.html:85` prefills `value="4.0"`, so the route always passes a
   value and `run_capm` always takes the "supplied by the caller" branch. Two problems in
   one: the user is shown a default and then told they supplied it, and **the `4.0` is a
   literal, not `config.DEFAULT_RISK_FREE_RATE`** — so changing the constant moves the CLI
   and leaves the web app at 4.0%, silently. `STATUS.md` trap 3 exactly. The fix is to
   make the form field empty-by-default and the parameter `str = Form("")`, like
   `equity_risk_premium` beside it already is. Both files are outside my scope.

2. **Two extractions of the same 89-page PDF, two days apart, disagreed by 16% on the
   implied share price** — $343.15 against $296.01 — and the largest single cause was one
   Pass 2 non-recurring item worth **1,140M** that the model itself tagged
   `confidence: low`, present in one run and absent in the other. Total debt also moved
   10,443 → 11,116. Nothing in the pipeline treats `confidence` as anything: the
   normalizer applies a `low`-confidence 1,140M add-back with the same weight as a `high`
   one. That is a real decision nobody has taken, it is not on the backlog, and it is
   worth its own unit. The evidence is `c:/tmp/lhx_real.txt` against `c:/tmp/p6_run1.txt`.

3. **`static/style.css` has no provenance class, so my labels carry an inline `style=`.**
   Four `style="{{ PROV }}"` attributes in `templates/valuation_result.html`, from a
   `{% set %}` at the top of the file. A unit that owns `static/` should lift it into a
   `.provenance` rule and delete the `{% set %}`. Cosmetic, but it is duplication of the
   kind that goes stale.

4. **The page's provenance rows are invisible to `tests/unit/test_routes.py`'s
   `_rows_under` helper**, and a tester needs to know before writing against them. That
   helper matches `<td>(.*?)</td>` with no attributes, and my label rows are
   `<td style="…">`. This is *why* criterion 7 holds — the helper cannot see the new rows,
   so no existing assertion could break — but it also means a test for criterion 4, 5 or 6
   on the page must match differently. I did not adjust the helper because `tests/` is not
   mine.

5. **Nothing tests the cache key.** `cli.py` has no tests at all, and the five functions
   this unit added to it — `fingerprint_filings`, `build_extraction_key`,
   `describe_key_difference`, `_load_cache`, `_save_cache` — are pure and environment-free
   apart from the filesystem, which `tmp_path` covers. `c:/tmp/p6_cache_dryrun.py` shows
   the shape a test file would take: same-file hit, different-file miss, same-path
   content-edited miss, provider miss, foreign-format stop, missing-file stop. That is a
   tester assignment worth writing, and **criterion 1 is the defect most likely to
   regress silently**, because a wrong answer still looks like a right one.
