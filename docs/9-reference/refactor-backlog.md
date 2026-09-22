# Refactor backlog

Every known defect, with its evidence and what it costs. **Re-measured at `2ca620a`,
2026-09-21.** Twelve are closed: 3, 4, 13, 14, 19, 20, 21, 23b, 24, 27, 30, and 12 mostly.

**Items 14 to 30 did not exist when this build started, and every one of 19 to 30 was
found by running the code rather than by reading it.** That is the single strongest
argument for the test suite that found them — and for the gates it added, since three of
them were found by a reviewer re-running a measurement it had been handed.

**Read this before reporting a defect as new**, and before writing an assignment that
touches one of these files. An item listed here, in a line a unit did not touch, is
**not** a finding against that unit — see
[.claude/agents/code-reviewer.md](../../.claude/agents/code-reviewer.md).

---

## How to read this

Two axes. **The second one outranks the first.**

| | |
|---|---|
| **Silent** | produces a wrong number on a clean run. Nothing downstream detects it |
| **Stopping** | raises, or refuses to run. Visible the moment it happens |

A silent defect that moves the headline share price outranks everything else, however
small the diff that causes it. A stopping defect is close to harmless: the run refuses
rather than lying.

---

## Ranked by cost

| # | Item | Silent? | Area | State at `2ca620a` |
|---|---|---|---|---|
| 1 | **116** silent zero-default sites | **silent** | `models/` 60, `ingestion/` 49, `analysis/` 5, `api/` 2 | open |
| 2 | Missing balance sheet gives zero net debt | **silent** | `analysis/dcf.py` | open, **proven by measurement** |
| 3 | Unknown NRI line item guesses a field | **silent** | `analysis/normalizer.py` | **closed at `38b903c`** |
| 4 | No test suite; `pytest` cannot collect | stopping | `tests/` | **closed** — 121 tests |
| 5 | Module-global extraction cache, popped on use | mixed | `api/routes_valuation.py` | open |
| 6 | Falsy treated as missing, five times | **silent** | `api/routes_valuation.py` | open |
| 7 | `cli.py` and `api/` duplicate the pipeline | **silent** | both | open |
| 8 | Blanket `except Exception` at five sites | **silent** | `api/`, `cli.py`, `ingestion/`, `tests/` | open, **now the only lint errors** |
| 9 | Unlabelled cost-of-debt assumption | **silent** | `analysis/wacc.py` | open |
| 10 | D&A subtraction buried in the parser | **silent** | `ingestion/claude_extractor.py` | open |
| 11 | **14** type errors, down from 33 | stopping | 4 files | open; every removal so far was a real defect |
| 12 | Dead code and stale repository hygiene | — | several | **mostly closed** |
| 13 | Provider changed with the number of PDFs uploaded | stopping, here | `ingestion/`, `api/` | **closed at `0e4649f`** |
| 14 | Empty `projected_fcffs` raises a bare `IndexError` | stopping | `analysis/dcf.py` | **closed at `ff632df`** |
| 15 | `latest_year` returns `0` for an empty extraction | **silent** | `models/financial_statements.py` | new |
| 16 | Nine scripts point at a path that does not exist | stopping | `tests/` | new |
| 17 | `analysis/` imports from `ingestion/` | — | `analysis/capm.py` | new |
| 18 | The lint gate's rule set is unpinned | — | `ruff.toml` | open |
| 19 | One sign rule applied to two kinds of line | **silent** | `analysis/normalizer.py` | **closed at `38b903c`** |
| 20 | A NaN beta is returned, not raised | **silent** | `analysis/capm.py` | **closed at `ff632df`** |
| 21 | An unrecognised `direction` silently reverses | **silent** | `analysis/normalizer.py` | **closed at `38b903c`** |
| 22 | Zero debt balance gives a 0% cost of debt | **silent** | `analysis/wacc.py` | open |
| 23 | `analysis/fcff.py` holds no `raise` for empty statements, **and `calculate_fcff_projected` has seven unguarded float parameters** | **silent** | `analysis/fcff.py` | open; **the clamp twin (23b) is closed at `2ca620a`** |
| 24 | A red test that goes green stays outside the gate | — | `tests/` | **closed at `81816be`** |
| 25 | An adjustment whose year matches no statement is discarded | **silent** | `analysis/normalizer.py` | **new** |
| 26 | The `files` branch tests for a character every path contains | stopping, **latent** | `api/routes_valuation.py` | **new.** Live only on the legacy no-year branch |
| 27 | `GET /` and `GET /assumptions` return **500** | stopping | `api/` | **closed at `622262b`** |
| 28 | `api/routes_upload.py:27` — `str \| None` used as a path segment | stopping | `api/routes_upload.py` | **new.** The last type error in that file |
| 29 | `POST /valuation` with no `files` runs an extraction on an empty path | **silent** | `api/routes_valuation.py` | **new.** A rule 3 break with no field named |
| 30 | A NaN in one `ProjectedFCFF` reaches the share price | **silent** | `analysis/dcf.py` | **closed at `2ca620a`** |
| 31 | `discount_cash_flows`' `wacc` is unguarded on a direct call | **silent** | `analysis/dcf.py` | **new, latent.** The `run_dcf` chain stops two lines later |
| 32 | `models/valuation.py:138` renders a share price of `0.0` on zero diluted shares | **silent** | `models/valuation.py` | **new.** Same shape as item 2 |
| 33 | The CLI cache is keyed on the **ticker alone**, so the PDFs you pass are silently ignored | **silent** | `cli.py` | **new.** Found on the first real filing run |
| 34 | The risk-free rate is a hardcoded `0.04` presented as measured | **silent** | `config.py`, `analysis/capm.py` | **new.** Rule 6 |
| 35 | A beta from a regression explaining 10% of variance is reported without qualification | **silent** | `analysis/capm.py` | **new.** Rule 6 |

---

## 1. 116 silent zero-default sites · **silent**

**Fact.** Reproduce:

```
grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" \
  --include=*.py models analysis api ingestion | wc -l
```
→ **116** at `ff632df`, unchanged since `38b903c`. By area: `models/` 60, `ingestion/` 49, `analysis/` 5,
`api/` 2.

| Commit | Count | The delta |
|---|---|---|
| `bc19431` | 119 | — |
| `d1854fb` | 117 | the two dead fields in the deleted `models/company.py` |
| `38b903c` | 116 | one `changes.get(field, 0.0)` rewritten by `P4-normalizer` |

**The grep excludes `tests/`, and `tests/` is not clean.** The nine scripts hold 33
more hits of the same shape. They are dev scripts, not pipeline code, and
[5-testing/strategy.md](../5-testing/strategy.md) already says they are not evidence of
correctness — but the figure must not be read as saying `tests/` has none.

**A comment can inflate this number.** `P4-normalizer`'s first draft carried an
explanatory comment quoting the old code; the grep counted it and held the count at
117. The programmer reworded it, on the grounds that a measurement that counts a
comment is not a measurement. **Check any future delta against the diff, not the
count.**

**What it costs.** A zero meaning "we did not extract this" is the same bytes as a zero
meaning "this is zero". Because every dataclass money field defaults to `0.0`, an
extraction that returned **nothing at all** flows through all eight pipeline steps and
renders a share price. Nothing anywhere reports that no data arrived.

### It is worse than "it produces zeros" · measured 2026-09-21

That description, written at `bc19431`, understated it. Measured independently by the
programmer and the reviewer of `P2b-provider`, on one-line PDFs printing a single
figure:

| The page printed | `other_operating_activities` came back as |
|---|---|
| `4321` | **`-4321.0`** |
| `6174` | **`-6174.0`** |
| `2718` | **`-2718.0`** |

`ingestion/claude_extractor.py:637` computes a residual,
`cfo - net_income - da - sbc - delta_wc`, over inputs that each defaulted to `0.0`.

**So item 1 does not merely produce zeros. It produces a signed, correctly-scaled
figure that tracks the filing and that a reader cannot distinguish from a
measurement.** A zero at least looks like an absence. This does not.

It is also the clearest possible answer to `STATUS.md` trap 3: the run produced a
number that moved with the document, and the number was still an artefact.

**Fix.** Make the money fields required, or introduce a sentinel that arithmetic
refuses. Then convert the `.get(k, 0)` calls in the parser into a validation pass that
names every absent field at once. [Rule 3](../2-rules/rules.md).

**Note the ordering.** Fixing item 1 without item 4 in place means no test detects the
regression it causes. Do 4 first.

## 2. Missing balance sheet gives zero net debt · **silent**

**Fact.** `analysis/dcf.py:80-81`:

```python
net_debt = latest_bs.net_debt if latest_bs else 0.0
cash = latest_bs.cash_and_equivalents if latest_bs else 0.0
```

`get_balance_sheet(latest_year)` returns `None` whenever the B/S was not extracted for
that year — which is routine, because `extract_multi_year()` takes the balance sheet
**only from the most recent filing**.

**What it costs.** Equity value is `EV − net_debt`. With `net_debt = 0`, equity value is
overstated by the **entire debt balance**. For a company with $100bn of net debt and 12bn
shares, that is $8.33 added to the implied share price, silently, on a clean run.

**This was called the highest-cost silent defect in the repository at `bc19431`. It is
no longer.** Item 19 outranked it — now closed — and **item 20 outranks it today**,
because a NaN reaches the share price through the same function's one working guard.
Item 2 still needs a missing balance sheet; item 20 does not.

**Fix.** Raise, naming the year and the missing statement.
`tests/unit/test_dcf_rule3_red.py` already states the requirement and is red.

## 3. Unknown NRI line item guesses a field · **CLOSED at `38b903c`**

**Was.** `analysis/normalizer.py:46-47` printed a line to stdout and returned
`other_operating_expense` for any label it did not recognise. The list holds 20
spellings and filings use many more, so the adjustment landed on the wrong income
statement line, moving operating margin, every projected year, and the share price. The
only signal was a `print` the web app never displayed.

**Now.** `_resolve_field` raises `ValueError`, naming the unrecognised label and the
year:

```
Unrecognised line_item 'Goodwill impairment charge' on the 2023 non-recurring item…
```

The `print` is deleted. Locked by a test that was written red, went green, and now
lives in `tests/unit/test_normalizer_stops.py` inside the gate — see **item 24** for
why that move was needed.

## 4. No test suite; `pytest` cannot collect · **CLOSED at `d1854fb`**

**Was.** At `bc19431`: 0 `assert` statements and 0 `__main__` guards across 10 files,
so every one ran its whole pipeline at **import**, and `pytest` made paid API calls
during collection and failed before a test ran.

**Now.** Unit `P1-suite` wrapped all nine scripts in `def main()` behind an
`if __name__ == "__main__":` guard, and added `tests/unit/`.

Units `P1b-arith` and `P1c-flow` then took the other five `analysis/` modules.

| | `bc19431` | `38b903c` |
|---|---|---|
| `assert` statements | 0 | **263** |
| guarded scripts | 0 | **9 of 9** |
| tests collected | 0 | **93** |
| `pytest -q` | 3 collection errors | 92 pass, 1 red on purpose, 3.8 s |
| paid calls during collection | attempted | **none** |
| `analysis/` statement coverage | 0 of 194 | **202 of 202 — 100%** |

**What is still open.** `ingestion/` and `api/` have **no tests at all.** That is where
51 of the 116 zero-default sites live, and where the extraction boundary sits. Coverage
of `analysis/` being complete says nothing about either.

**One test is red on purpose.** `tests/unit/test_dcf_rule3_red.py` states item 2's
requirement. It goes green when item 2 is fixed, and it is **kept, not deleted**. Until
then the phase-1 gate is
`pytest -q --ignore=tests/unit/test_dcf_rule3_red.py` → `19 passed`.

## 5. Module-global extraction cache, popped on use · mixed

**Fact.** `api/routes_valuation.py:25`:

```python
_extraction_cache: dict[str, FinancialStatements] = {}
```

Written at line 87, read at line 133 with `.pop()`.

**Three separate problems:**

| | |
|---|---|
| **Shared across users** | process-global. Two people valuing different companies share one dict, keyed by a file-path string |
| **Popped on read** | a page refresh on the results page is a cache miss, and re-runs the whole paid LLM extraction |
| **Unbounded** | anyone who visits `/assumptions` and never submits leaves an entry forever |

**Fix.** A keyed, size-bounded, per-session store that reads without removing.

## 6. Falsy treated as missing, five times · **silent**

**Fact.** `api/routes_valuation.py:150-154`:

```python
operating_margin=operating_margin / 100 if operating_margin else None,
tax_rate=tax_rate / 100 if tax_rate else None,
da_pct_revenue=da_pct / 100 if da_pct else None,
capex_pct_revenue=capex_pct / 100 if capex_pct else None,
nwc_pct_revenue=nwc_pct / 100 if nwc_pct else None,
```

**What it costs.** `None` means "use the historical average". `0` is falsy. So a user who
deliberately enters a 0% ΔNWC — entirely reasonable for a working-capital-neutral
business — gets the historical average instead, and the form silently ignored them.

**Fix.** Test `is not None`, and make the form send an empty string for "not supplied".

## 7. `cli.py` and `api/` duplicate the pipeline · **silent**

**Fact.** `cli.py:667-722` calls `normalize_financials`, `derive_assumptions`,
`fetch_price_data`, `run_capm`, `calculate_wacc`, `project_fcffs`, `run_dcf` — the same
seven calls as `api/routes_valuation.py:139-207`, wired separately.

**What it costs.** A fix applied to one is not applied to the other. A figure verified in
the CLI is not verified in the web app. `cli.py` is 760 lines and already the second
largest file in the repository.

**Fix.** Extract one `run_pipeline(financials, overrides) -> DCFResult` that both call.
The CLI keeps its printing layer; the route keeps its form parsing. **Do this before
fixing items 1, 2 or 3**, or each fix must be made twice.

## 8. Blanket `except Exception` at four sites · **silent**

**Fact.**

```
api/routes_valuation.py:96    BLE001
api/routes_valuation.py:220   BLE001
cli.py:758                    BLE001
ingestion/claude_extractor.py:795  BLE001
```

`routes_valuation.py:220` wraps the **entire** eight-step pipeline and renders
`str(e)` into the results template.

**What it costs.** Every failure mode collapses into one string. A missing API key, a
network timeout, a malformed PDF, and an `AttributeError` from item 11 are
indistinguishable to the user and to the log. It also converts the typed stops this
backlog asks for into the same undifferentiated string, which would undo the value of
fixing items 1 to 3.

**Fix.** Named exception types per failure class, per the four outcomes in
[AGENTS.md](../../AGENTS.md): `input_error`, `spec_incomplete`, `invariant_violation`.

## 9. Unlabelled cost-of-debt assumption · **silent**

**Fact.** `analysis/wacc.py:41-43`: when `total_debt > 0` and `interest_expense == 0`,
returns `config.DEFAULT_COST_OF_DEBT` = 4.0%.

**What it costs.** The substitution reaches WACC, every discounted cash flow, and the
share price. **Nothing in the output records that it happened.** A reader cannot tell a
measured cost of debt from a 4% guess.

This one is defensible as behaviour and indefensible as silence. [Rule 6](../2-rules/rules.md)
asks only that it be labelled.

**Fix.** Return the value with a flag, and show it on the result page as an assumption
with its source.

## 10. D&A subtraction buried in the parser · **silent**

**Fact.** `ingestion/claude_extractor.py:479`:

```python
other_operating_expense=float(yr.get("other_operating_expense", 0))
                       - float(yr.get("depreciation_amortization", 0)),
```

**What it costs.** This is a real accounting decision — whether the filing's "other
operating expense" already includes D&A — taken silently inside a **parser**, on two
values that each default to zero. It changes EBIT. It belongs in `analysis/`, with its
reasoning written down, and it must stop rather than default.
[2-rules/llm-boundary.md](../2-rules/llm-boundary.md) records it too.

## 11. 33 type errors, one a live crash path · stopping

**Fact.** `mypy models analysis ingestion api config.py app.py --ignore-missing-imports`
→ 33 errors in 4 files. By kind: 16 `union-attr`, 11 `arg-type`, 4 `assignment`, 2 other.
By file: `claude_extractor.py` 16, `routes_valuation.py` 12, `routes_upload.py` 4,
`projector.py` 4.

**One is a real defect, not a typing nicety:**

```
api/routes_valuation.py:190: Argument "balance_sheet" to "calculate_wacc"
  has incompatible type "BalanceSheet | None"; expected "BalanceSheet"
```

When the balance sheet is absent, `calculate_wacc` raises `AttributeError` on
`None.total_debt` deep in the valuation, and item 8's blanket catch renders the
traceback message as the user-facing error.

The 16 `union-attr` errors are the same shape as item 2: an `X | None` used without
checking. **Treat the mypy count as a proxy measurement for rule 3 coverage.**

## 12. Dead code and repository hygiene · **mostly closed at `d1854fb`**

| Item | State |
|---|---|
| `models/company.py` is dead | **closed** — deleted |
| `BalanceSheet` imported but unused, `analysis/fcff.py:20` | **closed** |
| `.DS_Store` tracked, twice | **closed** — untracked with `--cached`; both files remain on disk |
| 2 pickles tracked under `cache/` | **closed** — untracked with `--cached`; both remain on disk |
| **3 pickles tracked under `tests/`** | **open, deliberately.** Three scripts read them. Loading a pickle **executes code in it** |
| `.gitignore` lists `CLAUDE.md`, which is tracked | **closed** — the inert line is gone, with a note saying why |
| `.gitignore` misses the cache dirs | **closed** |
| `config.py` creates a directory at **import** | **closed** — the `mkdir` moved into `api/routes_upload.py`, where the file is written. Verified by execution: importing `config` creates nothing |
| `price_fetcher.py` imports pandas twice | **closed** |
| 45 lint errors across the repository | **closed down to 5**, all of them item 8 |
| `datetime.today()` without a timezone | **closed** — and the fix had to stay naive; see below |
| **`yfinance` imported inside a request handler**, `api/routes_valuation.py` | **open.** See below — the import location is the smaller half of the problem |
| **a redundant local `import re`**, `ingestion/claude_extractor.py:389` | **open.** Shadows the module-level import at line 60. Harmless, one line to delete |

### The `DTZ002` fix had to stay naive, and that is not laziness

`ingestion/price_fetcher.py` passes its date to yfinance, and
`yfinance/utils.py:454` branches on whether the datetime carries a timezone:

```python
if dt.tzinfo is None:
    dt = _pd.Timestamp(dt).tz_localize(exchange_tz)   # wall-clock kept, instant moves
else:
    dt = _pd.Timestamp(dt).tz_convert(exchange_tz)    # instant kept, wall-clock moves
```

So the idiomatic aware replacement would have shifted **both** lookback boundaries by
the UTC offset, changing the price window and therefore beta, CAPM and the share
price. The form used is `datetime.now(UTC).astimezone().replace(tzinfo=None)`, which is
wall-clock identical to `datetime.today()` on any machine by construction.

**Anyone tempted to "clean this up" into an aware datetime is about to move a number.**

### `api/routes_valuation.py:184` holds two defects, not one

```python
info.get("sharesOutstanding", 0)
```

- **Rule 5** — a financial figure sourced from yfinance rather than the filing, behind
  an inline import, mid-pipeline.
- **Rule 3** — a `.get` with a zero fallback, on the **denominator** of the headline
  share price.

They sit on one line and should be fixed in one unit.

## 13. Provider changes with the number of PDFs uploaded · **silent**

**Fact.** Three defaults disagree:

| Function | Default provider |
|---|---|
| `extract_financials` — `ingestion/claude_extractor.py:848` | `"gemini"` |
| `extract_multi_year` — `ingestion/claude_extractor.py:901` | `"claude"` |
| `cli.py --provider` — `cli.py:93` | `"gemini"` |

`api/routes_valuation.py:_extract_from_files` (`:40-57`) calls the first for one filing
and the second for several, and passes **no** `provider` argument in either branch.

**What it costs.** Uploading one PDF uses Gemini. Uploading two uses Claude. That is a
different model, requiring a different API key, producing different extracted figures
for the same company — with nothing in the interface indicating which ran.

The most likely symptom is not a wrong number but a confusing failure: a user with only
`GEMINI_API_KEY` set gets a working single-file upload and an
`ANTHROPIC_API_KEY is not set` error on the two-file upload, with no obvious reason why.

**Correction, `d1854fb`.** An earlier revision of this item said
`_DEFAULT_MODELS["claude"] = "claude-sonnet-4-6"` "is not a current model ID". **That
was wrong.** `claude-sonnet-4-6` is a current, served model. It is previous generation
and priced above `claude-sonnet-5`, so there is a better choice, but the provider is
not broken for the reason stated.

**This item is now a blocker on the machine the build runs on.** Measured at
`d1854fb`:

| Fact | Evidence |
|---|---|
| `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` are both unset, and no `.env` exists | the environment; `ls .env` |
| Gemini is unreachable from this network | reported by the user, 2026-09-20 |
| Claude is reachable, **through Microsoft Foundry** | `ANTHROPIC_FOUNDRY_BASE_URL` and `CLAUDE_CODE_USE_FOUNDRY` are set |
| the installed `anthropic` 1.7.0 exports `AnthropicFoundry` | `dir(anthropic)` |
| `ingestion/claude_extractor.py:352` constructs a plain `anthropic.Anthropic(api_key=...)` | it cannot use the Foundry endpoint |
| `_resolve_provider` (`:830`) raises unless `ANTHROPIC_API_KEY` is in the environment | it would refuse a working Foundry credential |

**So extraction cannot run at all on this machine**, by either provider. A one-PDF
upload tries Gemini and fails; a two-PDF upload tries Claude and fails for a different
reason.

### The working path, proven by execution 2026-09-21

Every row was run, not read. This is what the fix must reproduce.

| Step | Result |
|---|---|
| `az login` is active | the user signed in |
| token for `https://cognitiveservices.azure.com/.default` | issued |
| token for `https://ai.azure.com/.default` | issued, then **rejected** by the gateway |
| the gateway's own 401 names the right audience | `"Ensure 'az login' is active and the token audience is https://cognitiveservices.azure.com."` |
| `AnthropicFoundry(azure_ad_token_provider=…)` with **no** `api_key` and **no** `resource` | picks `base_url` up from `ANTHROPIC_FOUNDRY_BASE_URL` |
| `claude-opus-5` and `claude-haiku-4-5` | both served, HTTP 200 |
| a base64 `document` block holding a one-line PDF | the model returned the figure printed on the page |

**That 401 message is the fastest diagnosis available for a wrong scope.** Record it
where someone will find it, rather than leaving it to be rediscovered.

**`azure-identity` is not installed.** It is the only supported way to produce a
refreshing Entra token; `get_bearer_token_provider(DefaultAzureCredential(), SCOPE)` is
the call. **Do not shell out to `az` from library code** — a subprocess is untestable
and breaks wherever the CLI is absent.

**PDF input is a beta feature on Microsoft Foundry**, per Anthropic's platform
availability table. It works today. A future failure there is a platform change, not a
defect in this repository.

**Fix.** One default provider, named once in `config.py`. Make `provider` explicit at
the route and the CLI boundary. Add Foundry as a **transport**, selected by the
presence of a base URL, not as a third provider — the model is still Claude. Then show
the resolved provider, model **and transport** in the output as an assumption,
[rule 6](../2-rules/rules.md). A figure read through a company gateway and one read
through the public API must be distinguishable by the reader.

---

## 14. Empty `projected_fcffs` raises a bare `IndexError` · **CLOSED at `ff632df`**

**Fact.** `analysis/dcf.py:73` — `final_fcff = projected_fcffs[-1].fcff`. Measured by
the tester: `IndexError: list index out of range`.

**What it costs.** It stops, which is half of [rule 3](../2-rules/rules.md). It names
nothing, which is the other half. Item 8's blanket catch then renders
`"list index out of range"` on the results page, where a named input error belongs.

**Fixed at `ff632df`.** `analysis/dcf.py` raises `ValueError` naming
`projected_fcffs`. Measured before and after by the reviewer:
`IndexError: list index out of range` → `ValueError: projected_fcffs is empty…`.

## 15. `latest_year` returns `0` for an empty extraction · **silent**

**Fact.** `models/financial_statements.py:295` — `max(self.years) if self.years else 0`.

**What it costs.** This is the silent upstream of item 2. An extraction that returned
nothing gives `latest_year = 0`; `get_balance_sheet(0)` returns `None`; `dcf.py:80`
supplies zero net debt; a share price comes out of a valuation holding no filing data
at all. Item 1 covers the field defaults, but this `else 0` deserves its own name
because it is what turns "no data" into "year zero" without an error.

## 16. Nine scripts point at a path that does not exist · stopping

**Fact.** Every script under `tests/` opens with

```python
sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")
```

That directory belongs to a different Windows user. Proven pre-existing: the tester ran
the **unmodified** `bc19431` file and got `ModuleNotFoundError: No module named 'ingestion'`.

**What it costs.** None of the nine runs as `python tests/<name>.py`. They work under
`pytest`, and under `python -m tests.<name>`, only because `tests/__init__.py` makes the
repo root resolve.

**Fix.** Delete the nine lines and document `-m tests.<name>` as the invocation, or
resolve the root from `Path(__file__)`. **Any done-criterion that says "run the script"
must use `-m tests.<name>` until this lands.**

## 17. `analysis/` imports from `ingestion/` · —

**Fact.** `analysis/capm.py:14` — `from ingestion.price_fetcher import PriceData`. The
only hit of `grep -rn "^from ingestion" analysis/ models/`.

**What it costs.** No rule forbids it, which is why it is small. It breaks the layering
this repository otherwise keeps: `analysis/` imports `models/`, `config`, the standard
library, numpy and scipy. A dependency pointing upward makes `analysis/` untestable
without the extraction layer present.

**Fix.** Move `PriceData` into `models/`, so both sides import downward.

## 18. The lint gate's rule set is unpinned · —

**Fact.** `ruff.toml` sets `target-version` and one `B008` per-file ignore. It sets no
`select`, so the enabled rules are ruff 0.16.8's built-in default.

**What it costs.** Unit `P2-hygiene` put a number on it: changing **only**
`target-version`, with no source edit, moved the error count from 4 to 5 and woke
`UP017`, which had been dormant repository-wide. A ruff upgrade can do the same, with
no commit to point at and no diff to review.

**Fix is not obvious, which is why this is recorded rather than done.** Writing out
today's rule set freezes out errors the repository has not met yet. Pinning the ruff
version in `requirements-dev.txt` is the cheaper half and has no such cost.

---

# Found by the test units, 2026-09-20

Items 19 to 23 were found by units `P1b-arith` and `P1c-flow`, and confirmed
independently by their reviewers. **None was found by reading.** Each needed a test to
call the function with inputs nobody had tried.

# Found by the first run against a real filing, 2026-09-22

Three L3Harris 10-Ks (FY2023, FY2024, FY2025 — 506 pages) were supplied by the user.
The FY2025 filing was extracted by `claude-opus-5` through the Foundry gateway:
272,204 input tokens, 77 seconds, and the figures trace to the printed page —
`Revenue $ 21,865 $ 21,325` on page 23 is what the extraction returned for 2025 and
2024.

**The pipeline works. The number it produces is not yet trustworthy, and items 33 to 35
are why.**

## 33. The CLI cache is keyed on the ticker alone · **silent**

**Fact.** `cli.py:248-253`:

```python
return d / f".cache_{args.ticker.lower()}_extraction.pkl"
```

The PDFs passed on the command line are **not part of the key** and are never compared
against the cache's contents.

**Measured.** The first run against the user's new filings —
`cli.py "…LHX/…2025_English.pdf" -t LHX --cache-dir ./cache` — completed in **2 seconds**
and printed a full valuation of **$351.77**. It had loaded
`cache/.cache_lhx_extraction.pkl`, a pickle that predates this entire build, and **never
opened the PDF at all.** The output says `LOADING CACHED EXTRACTION` but does not say
that the file named on the command line was ignored.

**What it costs.** A complete, plausible, correctly-formatted valuation from data of
unknown provenance — unknown extractor version, unknown provider, unknown date — with no
signal. This is `STATUS.md` traps 1 and 3 firing together, and it is the first thing a
new user will hit, because the cache flag appears in four of the six examples in the
CLI's own help text.

**Fix.** Key the cache on the input files as well as the ticker — a hash of the paths
and their modification times. **A cache that can answer a question it was not asked is
worse than no cache.**

## 34. The risk-free rate is a hardcoded constant presented as measured · **silent**

**Fact.** `config.py:42` — `DEFAULT_RISK_FREE_RATE = 0.04  # 4.0% fallback if market
fetch fails`. `analysis/capm.py:123` substitutes it whenever no override is supplied,
and the CLI's `--risk-free-rate` defaults to `None`.

**There is no market fetch.** `grep -rn "treasury\|TNX\|risk_free" ingestion/price_fetcher.py`
returns nothing. The comment describes a fallback for a mechanism that was never built.

**What it costs.** The output prints `Risk-free rate: 4.00%` alongside genuinely measured
figures, with nothing distinguishing it. It enters the cost of equity, so it reaches
every discounted cash flow. [Rule 6](../2-rules/rules.md).

**Fix.** Either fetch it, or label it. Labelling is the cheaper half and closes the rule
break on its own.

## 35. An unusable beta is reported without qualification · **silent**

**Fact.** On the LHX run: `Beta: 0.493 (regression)`, `R-squared: 0.099`,
`Std error: 0.196`. The regression explains **10%** of the variance, and the standard
error is 40% of the estimate.

**What it costs.** Measured on this filing, holding everything else as the run produced
it:

| Beta | Implied price | Against the market's $240.21 |
|---|---|---|
| 0.493, as regressed | $343.57 | **+43.0%** |
| 0.80, a sector figure | $227.33 | **−5.4%** |

**One unmeasurable input moves the answer from a 43% buy to a 5% sell.** The diagnostic
that says so is printed two lines above it and carries no threshold, no warning and no
consequence.

**Fix.** [Rule 6](../2-rules/rules.md). Name a minimum R-squared, and when the
regression falls below it, say so in the output beside the beta — or stop.

## 31. `discount_cash_flows`' `wacc` is unguarded on a direct call · **silent, latent**

**Fact.** `analysis/dcf.py` guards every projected cash flow but not the `wacc`
parameter of `discount_cash_flows` itself. Verified by the reviewer of
`P4d-cashflow-nan`: a direct call with a NaN `wacc` returns `nan`.

**Why it is latent.** Through `run_dcf` the chain stops two lines later, at
`calculate_terminal_value`. No current caller reaches it with a NaN.

**Why it stays recorded.** `discount_cash_flows` is public, and "safe because nothing
calls it that way today" is the argument
[.claude/agents/code-reviewer.md](../../.claude/agents/code-reviewer.md) names as one of
the three that never justify a downgrade. Reachability is not the test.

## 32. Zero diluted shares render a share price of `0.0` · **silent**

**Fact.** `models/valuation.py:138`. Reported by the tester of `P1-suite`, reported
again by `P4d-cashflow-nan`, and never assigned.

**What it costs.** It is item 2's shape on the **denominator** of the headline figure.
Equity value divided by zero shares gives `0.0` rather than a stop, so a valuation with
no share count renders a price of zero — which reads as a company worth nothing rather
than as an absent input.

**Why no test asserts it.** Locking `implied_share_price == 0.0` would make the defect
permanent. The testers reported it instead, twice.

**Fix.** Raise, naming `diluted_shares`. **`models/valuation.py` carries 40 assertions**
— any unit touching it must expect to answer for every one.

## 30. A NaN in one `ProjectedFCFF` reaches the share price · **CLOSED at `2ca620a`**

**Fact.** Confirmed by the reviewer of `P4c-nan-stops`, **before and after** that unit,
in a middle projection year and in the final year: a NaN in a single `ProjectedFCFF`
produces `implied_share_price = nan` even when WACC is finite.

`analysis/dcf.py:46-57` sums and discounts the projected cash flows with no check on
what it is summing.

**What it costs.** The same as item 20 — a NaN share price on a clean run — through a
different door. **All three stops item 20 added sit on the discount-rate side.** The
cash-flow side has none.

**Why it is not charged to `P4c-nan-stops`.** `analysis/dcf.py:46-57` is unchanged by
that diff, and widening its scope to reach this would itself have been a review finding.

**Fixed at `2ca620a`.** `analysis/dcf.py` guards each projected cash flow before it is
discounted, naming the **year** rather than only the field. The terminal value's base
cash flow is guarded inside `calculate_terminal_value`, **not** in `run_dcf` — a guard
there would be dead code, because `discount_cash_flows` runs first over the whole list
including the last element. The reviewer verified that by stack trace rather than by
argument: `run_dcf:133 <- discount_cash_flows:97 <- _require_finite:35`, with the later
lines never reached.

**Two more doors are still open**, both reported by the same unit and neither charged to
it: item **31** (`discount_cash_flows`' `wacc` on a direct call) and item **32**
(`models/valuation.py:138`).

## 23b. The NaN tax clamp twin, `analysis/fcff.py:44` · **CLOSED at `2ca620a`**

**Fact.** `max(0.0, min(nan, 0.50))` is **`0.0`**. Python's `min` and `max` keep their
first argument when a comparison is `False`, and every comparison against NaN is
`False`. Measured:

```
min(nan, 0.50)           ->  nan
max(0.0, min(nan, 0.50)) ->  0.0
```

**What it costs.** The clamp turns an unknown tax rate into **zero percent** — a full
tax shield, which **raises** the valuation. An input nobody could compute becomes the
most favourable possible assumption, silently.

`analysis/wacc.py` held the identical clamp and `P4c-nan-stops` fixed it, checking
**before** the clamp because afterwards the evidence is gone. `analysis/fcff.py:44` was
out of that unit's scope and still has it. Recorded here rather than as a new number
because it is the same defect as item 23's file.

**Fixed at `2ca620a`**, checking before the clamp as `analysis/wacc.py` does. Measured
cost, reproduced independently by the reviewer:

| Tax rate supplied | `tax_rate` | after-tax interest | FCFF |
|---|---|---|---|
| `0.25`, from the filing | 0.25 | 7.5 | **112.5** |
| NaN, before the fix | **0.00** | 10.0 | **115.0** |

An unknown rate raised free cash flow by 2.5 in a single year and was reported as a
measurement.

**The clamp still clamps**, which was the point of keeping two controls on it: `0.80`
still becomes `0.50` and `-0.30` still becomes `0.0`, byte-identical before and after.
A **known** out-of-range rate is corrected; only an **unknown** one stops. Before the
fix the two were indistinguishable in the output, and the unknown one gave the most
favourable result available.

`analysis/fcff.py` is still open on item 23's other half.

## 29. `POST /valuation` with no `files` runs an extraction on an empty path · **silent**

**Fact.** `api/routes_valuation.py:131` declares `files: str = Form("")`, and `:154`
branches on it without ever checking that it holds anything:

```python
filings = _parse_files_param(files) if ":" in files else [(0, files)]
```

Measured by the tester of `P5b-route-tests`, and again by the orchestrator, with the
extractor faked:

```
POST /valuation data={"ticker": "TESTCO"}   ->  HTTP 200
  extract_financials received pdf_path = ''
  the word 'files' appears on the page: False
```

**What it costs.** A request that names no filing is not an error here. It becomes an
extraction against the empty string, and whatever that produces flows into a rendered
page. [Rule 3](../2-rules/rules.md): a missing input must stop the run and name the
field. This one does neither.

**It is not item 26 and not item 1.** Item 26 is about the branch *test*; this is about
the value being empty in the first place. Item 1's census counts a different pattern and
does not match a `""` default in a `Form()` declaration, so this site has never been
counted.

**Fix.** Stop when `files` is empty, naming `files`. The three inputs declared without a
default — `ticker` and `pdf_files` on `POST /upload`, `ticker` on `POST /valuation` —
already return 422 naming the field, so the correct behaviour is established in the same
file.

**No test asserts it in either direction.** The tester reported it rather than encoding
it, because asserting the current behaviour would lock the defect.

## 27. `GET /` and `GET /assumptions` return 500 · **CLOSED 2026-09-21**

**Fact.** `starlette` 1.6.0 requires `TemplateResponse(request, name, context)`. Two
call sites still use the removed `(name, context)` form:

| Site | State |
|---|---|
| `api/routes_upload.py:42` | **broken.** Unchanged since `bc19431` |
| `api/routes_valuation.py:114` (`assumptions.html`) | **broken** |
| the two `valuation_result.html` calls | fixed by `P2b-provider` |

Measured at `0e4649f`:

```
TestClient(app.app, raise_server_exceptions=False).get('/')  ->  500
```

**What it costs.** `app.py` is one of the two entry points this product ships, and a
user cannot reach its first page. The command in `docs/0-start.md` starts a server that
serves nothing.

**Why nobody noticed.** The failing calls sit inside item 8's blanket catch, which
renders the error onto a page — through the same broken call. So the error page could
not render either, and the failure surfaced as a bare 500 with no message. mypy had been
reporting all four as `arg-type` errors since `bc19431`; they were ranked below a
different error from the same output.

**Fixed at `622262b`.** Unit `P5-web-routes`, two lines. Measured before and after against a
`git archive` export of the baseline, by the programmer and again by the reviewer:

```
BEFORE   GET / -> 500,   21 bytes (literally b'Internal Server Error')
AFTER    GET / -> 200, 1648 bytes,  all six upload-form markers present
         GET /assumptions -> 200, 5673 bytes
```

Types fell 18 → 14; `comm -13` against the baseline is empty and `comm -23` is exactly
the four `arg-type` errors on the two changed lines.

**The reviewer proved the "why nobody noticed" claim rather than repeating it.** It
exercised the error branch of `assumptions_page`, which now returns 200 and renders
`<div class="alert alert-error">[Errno 2] No such file…</div>`. Before the fix that
branch rendered through the same broken call, so the handler meant to report the error
could not report anything.

## 26. A Windows upload path is parsed as a fiscal year · stopping

**Fact.** `api/routes_valuation.py:152`:

```python
filings = _parse_files_param(files) if ":" in files else [(0, files)]
```

The `":"` test is meant to detect the `year:path` encoding used for a multi-file
upload. `_parse_files_param` at `:34-43` then does:

```python
year_str, _, path = entry.partition(":")
result.append((int(year_str), path))
```

**Correction, 2026-09-21.** An earlier revision of this item — written by the
orchestrator from a reading of `:152` alone — said "every saved upload path on this
platform contains a colon", and told a story in which refreshing a working valuation
breaks. **That was wrong**, and the reviewer of `P2b-provider` round 2 disproved it by
execution. The upload flow at `api/routes_upload.py:60-62` always builds the parameter
as `f"{year or 0}:{path}"`, and `str.partition` splits on the **first** colon only:

```
'2024:C:\Users\x\goog.pdf'  ->  [(2024, 'C:\\Users\\x\\goog.pdf')]   OK
'0:C:\Users\x\goog.pdf'     ->  [(0,    'C:\\Users\\x\\goog.pdf')]   OK
'C:\Users\x\goog.pdf'       ->  ValueError: invalid literal for int() with base 10: 'C'
```

So the year prefix absorbs the drive-letter colon, and the upload flow is safe. The
reviewer's own criterion-4 runs went through `_parse_files_param` on a cache miss with a
Windows absolute path and returned 200.

**What it actually costs.** The defect fires only when `files` arrives with **no** year
prefix — the legacy `file_path` branch at `api/routes_valuation.py:91-92`, or any caller
that builds the parameter by hand. It is latent, not live, which is why it is ranked
below the silent defects rather than with them.

**It stays recorded** because the guard is wrong in principle: `":" in files` tests for
a character that a path on this platform always contains, so the branch is right today
only by the accident that something else always adds a colon first. A future change that
drops the prefix turns it live with no other edit.

**Fix.** Decide the branch on something a path cannot contain, or pass the filings as
structured data rather than as one delimited string. **Do not "fix" it by testing for a
drive letter** — that repairs one platform and leaves the design wrong.

## 25. An adjustment whose year matches no statement is silently discarded · **silent**

**Fact.** `analysis/normalizer.py:167-170`. `normalize_financials` groups the
non-recurring items by year, then walks the **income statements** and applies whatever
that year's bucket holds. An item whose year is in no statement is never looked at.
Measured by the tester:

```
statement years : [2023, 2024]   item year : 2019
RAISED          : nothing
  2023: sga 200.0 -> 200.0   2024: sga 200.0 -> 200.0
```

The item was well formed — recognised label, legal direction, real amount.

**What it costs.** A valuation labelled *normalised* whose figures are still GAAP, with
no signal anywhere. It is the same class as item 3, one line above it in the same
function, which `P4-normalizer` has just closed.

**It is not hypothetical.** The item's year and the statements' years come from **two
separate model passes** — `ingestion/claude_extractor.py:259` and `:553` — with nothing
reconciling them. `extract_multi_year` merges statements year by year while accumulating
every NRI, so a mismatch is routine rather than exotic.

**Fix.** Raise, naming the item's year and the years that do exist. Needs its own unit
and a red test.

**Why no test exists yet.** A test asserting the drop would be asserting the fallback,
which [5-testing/strategy.md](../5-testing/strategy.md) section 2 forbids. And the red
test would have had to live in the file `P4b-normalizer-verify` was sent to delete. The
tester reported it instead, which is what its contract prescribes.

## 24. A red test that goes green stays outside the gate · **CLOSED at `81816be`**

**Was.** At `38b903c`:

```
pytest -q                                  ->  93 tests, 92 pass, 1 red
pytest -q --ignore-glob="*_rule3_red.py"   ->  90 passed
pytest -q tests/unit/test_normalizer_rule3_red.py  ->  2 passed
```

The gate ran 90 of the 92 passing tests. The missing two were the former red tests for
items 3 and 21, which went green when `P4-normalizer` fixed what they stated and stayed
inside the pattern the gate excludes. **So the two tests proving the fix worked were the
two the gate did not run.** That is the shape of defect this repository exists to avoid:
a clean report about something nobody checked.

**Now.** They live in `tests/unit/test_normalizer_stops.py`, each additionally asserting
the year. `ls tests/unit/*_rule3_red.py` returns one line, `test_dcf_rule3_red.py`,
which states item 2 and is correctly still red. The gate reports **105 passed**.

**The rule is now in the tester's contract** —
[.claude/agents/tester.md](../../.claude/agents/tester.md), "A red test lives in
`*_rule3_red.py`, and it moves out the day it goes green" — so the next unit does it
without being told.

## 19. One sign rule applied to two kinds of line · **CLOSED at `38b903c`**

**Fact.** Two lines of the income statement move earnings in opposite directions:

| Line | How it reaches earnings |
|---|---|
| `other_operating_expense`, `sga`, `cost_of_revenue`, … | **subtracted** — `ebit` |
| `other_non_operating` | **added** — `models/financial_statements.py:91` |

`analysis/normalizer.py:68` applies one rule to both:

```python
delta = -item.amount if item.direction == "add_back" else item.amount
```

`_LABEL_TO_FIELD` routes three labels to `other_non_operating`
(`analysis/normalizer.py:38-40`), so an adjustment on a non-operating line moves
**both** directions the wrong way.

**Measured** by the reviewer, on revenue 1000 / SG&A 200 / `other_non_operating` 80 /
`tax_expense` 100, removing a one-time gain of 50:

| | `other_non_operating` | EBT | Effective tax rate |
|---|---|---|---|
| Correct clean base | 30.0 | 430.0 | 23.26% |
| What the code produces | **130.0** | **530.0** | **18.87%** |

**What it costs.** The error is `+100` on a `50` item — twice the amount, in the wrong
direction. It understates the effective tax rate by 4.4 points, which
`analysis/projector.py:63-64` averages into the projected tax rate, which **overstates
NOPAT by 5.7% in every projected year** (324.53 against 306.98 on an EBIT of 400).

**This fires on ordinary, correct input.** Every other silent defect in this backlog
needs a missing value. This one needs only a filing that reports a gain on an asset
sale — which is the exact case `NonRecurringItem`'s own docstring names as
`gain_loss_asset_sale`.

**The repository already disagrees with itself in writing.**
`models/financial_statements.py:31-37` declares the correct intent:

```python
@property
def adjusted_impact(self) -> float:
    """add_back -> positive (removes expense -> improves EBIT)
       remove   -> negative (removes gain   -> reduces EBIT)"""
    return self.amount if self.direction == "add_back" else -self.amount
```

That is the effect on **earnings**. `normalizer.py:68` computes the delta on the
**field**, and the two are equal only when the field reduces earnings.

**Fixed at `38b903c`, and it was not a judgement.** The delta on a field is now

```python
item.adjusted_impact * _FIELD_EARNINGS_SIGN[field]
```

`_FIELD_EARNINGS_SIGN` holds six `±1.0` entries; only `other_non_operating` is `+1.0`.
[Rule 2](../2-rules/rules.md) permits it explicitly: **a lookup table that maps a key
to a number is allowed.** It is looking up *behaviour* that is forbidden.

**Verified three times, independently, by three agents who did not share context.** The
programmer derived all six signs by bumping each field and reading the change in `ebt`.
The reviewer re-derived them by finite difference at two step sizes, against both `ebt`
and `net_income`, and checked the invariant the fix exists to restore —
`Δebt == adjusted_impact` — over all six fields and both directions, 12 of 12. The
orchestrator ran the worked case and the expense case.

After: `other_non_operating` 30.0, `ebt` 430.0, effective tax rate 23.26%. The expense
path is unchanged: an `add_back` of 50 in `sga` still moves it 200 → 150 and raises
`ebit` 400 → 450.

**One consequence, recorded rather than hidden.** This converts a silent wrong number
into a hard stop, and that stop lands in the blanket catch at
`api/routes_valuation.py:220`, which renders it as a bare string on the results page.
**Item 8 is more urgent than its rank suggests.**

## 20. A NaN beta is returned, not raised · **CLOSED at `ff632df`**

**Fact.** `analysis/capm.py:87` calls `calculate_beta`, which calls
`scipy.stats.linregress`. On an empty series that returns `nan` for the slope and
**raises nothing**. Measured directly:

```
linregress([], []) -> slope=nan  rvalue=nan  stderr=nan
```

The guard at `analysis/capm.py:42-43` does catch an empty series, but only on the path
that derives the equity risk premium from history. **Supplying an ERP skips it**, and
both the web form and the CLI let a user do that.

**What it costs.** `nan` reaches the cost of equity, then WACC, then
`analysis/dcf.py:24`:

```python
if wacc <= terminal_growth_rate:
    raise ValueError(...)
```

**`nan <= 0.025` is `False`.** Every comparison against NaN is false, so the one
correct stop in the whole of `analysis/` does not fire. A complete `DCFResult` renders
with `implied_share_price = nan`.

Chain confirmed end to end by the reviewer: `capm.py:72` → `:87` → `:32` →
`models/valuation.py:16` → `analysis/wacc.py:66` → `models/valuation.py:34-38` →
`analysis/dcf.py:24` → `:74,75` → `models/valuation.py:138`. Reached from both
`api/routes_valuation.py:167-172` and `cli.py:687-692`.

**Fixed at `ff632df`** by unit `P4c-nan-stops`, with three stops in series, every one
`math.isnan` and none a comparison:

| File | Catches |
|---|---|
| `analysis/capm.py` | unequal series lengths; fewer than 3 observations; a regression whose statistics come back NaN |
| `analysis/wacc.py` | a NaN arriving where CAPM cannot see it — an overridden beta, a NaN market cap, a `CAPMResult` built elsewhere |
| `analysis/dcf.py` | the last guard before a price is rendered now rejects NaN itself, rather than trusting upstream |

**The proof is the path that did not move.** Six new stops were added to files already
at 100% coverage, where every assertion was derived by hand, so the risk was never that
a stop fails to fire — it is that a healthy path shifts. The reviewer ran six controls
**with its own inputs**, different from the programmer's, and none moved by a digit:
`implied_share_price = 12.697763190328896`, `beta = 1.596774193548387`,
`std_error = 0.10158303025640267`.

**The threshold of 3 observations is derived, not fitted.**
`SE(beta) = sqrt(SSE / ((n-2) · Sxx))` needs `n - 2 >= 1`. scipy 1.18.1 at `n = 2`
returns a finite slope with `stderr = nan`, so the old code rendered a price while
carrying a NaN diagnostic. Adopting the threshold **removes** a number the old code
produced, which is the opposite of fitting a case.

**Coverage fell and was not worked around.** `capm.py` 92%, `dcf.py` 93%, `wacc.py` 97%;
all six missed lines are the new raises. The reviewer reached every one by execution, so
no unreachable guard was written to hold a percentage.

**Two doors are still open.** See item **30** — the cash-flow side is unguarded — and
item **23b**, the tax clamp twin in `analysis/fcff.py`.

## 21. An unrecognised `direction` silently reverses the adjustment · **CLOSED at `38b903c`**

**Was.** `analysis/normalizer.py:68` tested `item.direction == "add_back"`. Every other
string — `"Add_Back"`, `"addback"`, a typo, an empty string — took the `else` branch and
was treated as `remove`, moving the adjustment the opposite way with no signal. The
value arrives from the model, so the set of possible spellings was never closed.

**Now.** Raises `ValueError` naming the value and the year:

```
Unrecognised direction 'Add_Back' on the 2022 non-recurring item 'Restructuring charge'…
```

Locked by a test in `tests/unit/test_normalizer_stops.py`, written red and now green
inside the gate — see **item 24**.

## 22. Zero debt balance gives a 0% cost of debt · **silent**

**Fact.** `analysis/wacc.py:37-38` — `if total_debt == 0: return 0.0`.

**What it costs.** A filing that reports an interest expense but from which no debt
balance was extracted is missing data, not a debt-free company. The zero is read as a
measurement. The weight is also zero in that case, so today it does not move WACC — but
it will the moment the weights come from anywhere else.

## 23. `analysis/fcff.py` holds no `raise` at all · **silent**

**Fact.** Measured by the tester: an entirely empty `IncomeStatement` and
`CashFlowStatement` return a well-formed `HistoricalFCFF` with `fcff = 0.0`.

**What it costs.** Free cash flow of exactly zero is a meaningful figure for a real
company. It is indistinguishable here from "nothing was extracted". This is item 1
wearing a different face, and it is named separately because `fcff.py` is the one
`analysis/` module with no stop of any kind.

---

## Suggested order

Dependencies, not severity. **The order matters more than the ranking**, because
fixing a silent defect with no test in place produces an unverifiable claim.

**Steps 1 and 2 are done.** Re-measured at `796de9a`, with `analysis/` at 192 of 194
statements covered.

1. ~~**Item 4**~~ — **done.** `pytest` runs 20 tests with no key. `analysis/dcf.py` is
   at 100% of statements; the other five modules are at 0%.
2. ~~**Item 12's hygiene subset**~~ — **done.** Item 13 was deliberately deferred out
   of this step: one default provider makes the provider a named assumption, and
   [rule 6](../2-rules/rules.md) then requires it to be visible in the output. It ships
   with its labelling, not before it.
3. ~~**Items 19, 3 and 21**~~ — **done at `38b903c`**, in one unit, because all three
   sat in the same 34-line function. Item 19 went first in the whole list because it
   was the only silent defect here that fired on ordinary, complete input.
4. ~~**Item 24**~~ — **done at `81816be`.**
5. **Item 13, with Foundry. Next.** **Extraction cannot run on the build machine at
   all** until it lands, so nothing after this can be exercised against a real filing.
   The whole path is now proven by execution — see the item — so its criteria are
   measurable rather than aspirational.
6. **Item 20**, with item 14 alongside — both are `analysis/dcf.py:24` failing to stop,
   for different reasons. **Item 20 needs a check that is not a comparison**, because
   every comparison against NaN is `False`.
7. **Item 2**, with item 15 alongside — the same failure walking through two files.
   Item 2's red test goes green here.
8. **Item 7** — unify the pipeline, so each later fix is made once.
9. **Item 6**, then **item 22**, then **item 23**.
10. **Item 8**, then **item 11**. Typed failures, which item 1 depends on.
11. **Item 1** — the large one. Last, with the suite in place.
12. **Items 9, 10, 5, 16, 17, 18.**

**Two deviations from the stated rule, both named rather than hidden.**

- **Step 4 sits ahead of step 7.** The rule says unify before fixing, so each fix is
  made once. Item 13 is a stopping defect on the only machine available, and the cost
  of waiting is that no unit after it can be checked against a real extraction. A fix
  applied twice is cheaper than a build nobody can run.
- **Step 3 sits ahead of everything, including the test-first rule.** It does not
  breach it: `analysis/normalizer.py` is at 93% of statements with 39 assertions
  against it, and the two lines not covered are the ones the fix will delete. The tests
  are already in place. That is exactly the position the rule was written to produce.

**Step 3 moved ahead of step 5, and that is a deviation worth naming.** The rule is
that unification comes before behaviour fixes, so each fix is made once. Item 13 is a
stopping defect on the only machine available, so the cost of waiting is that no unit
after it can be checked against a real extraction. A fix applied twice is cheaper than
a build nobody can run.

## Constraints on any unit taken from this list

- **Do not fix more than the assignment names.** An out-of-scope fix is a review
  finding even when the change is good.
- **Do not weaken, skip or `xfail` a test to make a suite green.**
- **Do not lock a defect as an expectation.** A test asserting `net_debt == 0.0` when
  the balance sheet is missing makes item 2 permanent and turns its fix red.
- **Re-measure the counts in this file when a unit lands.** They are measurements, and
  they carry a commit.
