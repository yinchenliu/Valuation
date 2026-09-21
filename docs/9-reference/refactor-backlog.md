# Refactor backlog

Every known defect, with its evidence and what it costs. **Re-measured at `d1854fb`,
2026-09-20.** Item 4 is closed. Items 12 and 13 moved. Items 14 to 18 are new, found
by the two units that have run.

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

| # | Item | Silent? | Area | State at `d1854fb` |
|---|---|---|---|---|
| 1 | **117** silent zero-default sites | **silent** | `models/`, `analysis/`, `api/`, `ingestion/` | open |
| 2 | Missing balance sheet gives zero net debt | **silent** | `analysis/dcf.py` | open, **proven by measurement** |
| 3 | Unknown NRI line item guesses a field | **silent** | `analysis/normalizer.py` | open |
| 4 | No test suite; `pytest` cannot collect | stopping | `tests/` | **closed** — 20 tests |
| 5 | Module-global extraction cache, popped on use | mixed | `api/routes_valuation.py` | open |
| 6 | Falsy treated as missing, five times | **silent** | `api/routes_valuation.py` | open |
| 7 | `cli.py` and `api/` duplicate the pipeline | **silent** | both | open |
| 8 | Blanket `except Exception` at five sites | **silent** | `api/`, `cli.py`, `ingestion/`, `tests/` | open, **now the only lint errors** |
| 9 | Unlabelled cost-of-debt assumption | **silent** | `analysis/wacc.py` | open |
| 10 | D&A subtraction buried in the parser | **silent** | `ingestion/claude_extractor.py` | open |
| 11 | 33 type errors, one a live crash path | stopping | 4 files | open, error set unchanged |
| 12 | Dead code and stale repository hygiene | — | several | **mostly closed** |
| 13 | Provider changes with the number of PDFs uploaded | stopping, here | `ingestion/`, `api/` | open, **and now a blocker** |
| 14 | Empty `projected_fcffs` raises a bare `IndexError` | stopping | `analysis/dcf.py` | new |
| 15 | `latest_year` returns `0` for an empty extraction | **silent** | `models/financial_statements.py` | new |
| 16 | Nine scripts point at a path that does not exist | stopping | `tests/` | new |
| 17 | `analysis/` imports from `ingestion/` | — | `analysis/capm.py` | new |
| 18 | The lint gate's rule set is unpinned | — | `ruff.toml` | new |

---

## 1. 119 silent zero-default sites · **silent**

**Fact.** Reproduce:

```
grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" \
  --include=*.py models analysis api ingestion | wc -l
```
→ **117** at `d1854fb`, was 119 at `bc19431`. The delta is exactly the two dead fields
in the deleted `models/company.py`. By area: `models/` 60, `ingestion/` 49,
`analysis/` 6, `api/` 2.

**The grep excludes `tests/`, and `tests/` is not clean.** The nine scripts hold 33
more hits of the same shape. They are dev scripts, not pipeline code, and
[5-testing/strategy.md](../5-testing/strategy.md) already says they are not evidence of
correctness — but the 117 figure must not be read as saying `tests/` has none.

**What it costs.** A zero meaning "we did not extract this" is the same bytes as a zero
meaning "this is zero". Because every dataclass money field defaults to `0.0`, an
extraction that returned **nothing at all** flows through all eight pipeline steps and
renders a share price. Nothing anywhere reports that no data arrived.

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

**This is the highest-cost silent defect in the repository.**

**Fix.** Raise, naming the year and the missing statement.

## 3. Unknown NRI line item guesses a field · **silent**

**Fact.** `analysis/normalizer.py:46-47`:

```python
print(f"  [normalizer] Unrecognised line_item '{line_item}' — defaulting to other_operating_expense")
return "other_operating_expense"
```

**What it costs.** The model returns a label the `_LABEL_TO_FIELD` list does not hold —
easy, since it holds 20 spellings and filings use many more. The adjustment lands on the
wrong income statement line. Operating margin moves, which moves every projected year,
which moves the share price. The only signal is a line on stdout that nobody reads, and
which the web app does not display at all.

**Fix.** Raise, naming the unrecognised label and the year it came from.

## 4. No test suite; `pytest` cannot collect · **CLOSED at `d1854fb`**

**Was.** At `bc19431`: 0 `assert` statements and 0 `__main__` guards across 10 files,
so every one ran its whole pipeline at **import**, and `pytest` made paid API calls
during collection and failed before a test ran.

**Now.** Unit `P1-suite` wrapped all nine scripts in `def main()` behind an
`if __name__ == "__main__":` guard, and added `tests/unit/`.

| | `bc19431` | `d1854fb` |
|---|---|---|
| `assert` statements | 0 | **40** |
| guarded scripts | 0 | **9 of 9** |
| tests collected | 0 | **20** |
| `pytest -q` | 3 collection errors | 19 pass, 1 red on purpose, 0.26 s |
| paid calls during collection | attempted | **none** |

**What is still open, and it is the honest headline.** One `analysis/` module of six
has any test. `analysis/dcf.py` is at 100% of statements; `capm.py`, `fcff.py`,
`normalizer.py`, `projector.py` and `wacc.py` are at **0%** — 170 statements that no
test touches. [5-testing/strategy.md](../5-testing/strategy.md) section 6 gives the
order to take them in.

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

**Fix.** One default provider, named once in `config.py`. Make `provider` explicit at
the route and the CLI boundary. Add Foundry as a **transport**, selected by the
presence of a base URL, not as a third provider — the model is still Claude. Then show
the resolved provider, model **and transport** in the output as an assumption,
[rule 6](../2-rules/rules.md). A figure read through a company gateway and one read
through the public API must be distinguishable by the reader.

---

## 14. Empty `projected_fcffs` raises a bare `IndexError` · stopping

**Fact.** `analysis/dcf.py:73` — `final_fcff = projected_fcffs[-1].fcff`. Measured by
the tester: `IndexError: list index out of range`.

**What it costs.** It stops, which is half of [rule 3](../2-rules/rules.md). It names
nothing, which is the other half. Item 8's blanket catch then renders
`"list index out of range"` on the results page, where a named input error belongs.

**Fix.** One line. Raise, naming `projected_fcffs`. A test can then be written green.

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

## 19. One sign rule applied to two kinds of line · **silent** · **highest cost known**

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

**Fix, and it is not a judgement.** The delta on a field is
`adjusted_impact × field_sign`, where `field_sign` is `-1` for a field that reduces
earnings and `+1` for one that raises them. Only `other_non_operating` is `+1` today.
[Rule 2](../2-rules/rules.md) permits this: **a lookup table that maps a key to a
number is allowed.** It is looking up *behaviour* that is forbidden.

## 20. A NaN beta is returned, not raised · **silent**

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

**Fix.** Stop in `calculate_beta` when the series is empty or too short, naming the
input. Then add a NaN check that does not rely on a comparison — `math.isnan` — at the
point WACC is built, because **a guard written as `<=` cannot catch this.**

## 21. An unrecognised `direction` silently reverses the adjustment · **silent**

**Fact.** `analysis/normalizer.py:68` tests `item.direction == "add_back"`. Every other
string — `"Add_Back"`, `"addback"`, a typo, an empty string — takes the `else` branch
and is treated as `remove`.

**What it costs.** The adjustment moves the opposite way from the one intended, with no
signal. The value arrives from the model, so the set of possible spellings is not
closed. [Rule 3](../2-rules/rules.md).

**Fix.** Raise on any value that is neither `"add_back"` nor `"remove"`, naming the
value and the year. A red test already states this:
`tests/unit/test_normalizer_rule3_red.py`.

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
3. **Items 19, 3 and 21 together** — all three are in `analysis/normalizer.py`, all
   three are about the same 34-line function, and two of the three already have a red
   test waiting. **Item 19 is first in the whole list** because it is the only silent
   defect here that fires on ordinary, complete input. Every other one needs something
   to be missing.
4. **Item 13, with Foundry.** **Extraction cannot run on the build machine at all**
   until it lands, so nothing after this can be exercised against a real filing.
5. **Item 20**, with item 14 alongside — both are `analysis/dcf.py:24` failing to stop,
   for different reasons. Item 20 needs a check that is not a comparison.
6. **Item 2**, with item 15 alongside — the same failure walking through two files.
   Item 2's red test goes green here.
7. **Item 7** — unify the pipeline, so each later fix is made once.
8. **Item 6**, then **item 22**, then **item 23**.
9. **Item 8**, then **item 11**. Typed failures, which item 1 depends on.
10. **Item 1** — the large one. Last, with the suite in place.
11. **Items 9, 10, 5, 16, 17, 18.**

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
