# Refactor backlog

Every known defect, with its evidence and what it costs. **Measured at `bc19431`,
2026-09-20.** No item here has been assigned or fixed.

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

| # | Item | Silent? | Area |
|---|---|---|---|
| 1 | 119 silent zero-default sites | **silent** | `models/`, `analysis/`, `api/`, `ingestion/` |
| 2 | Missing balance sheet gives zero net debt | **silent** | `analysis/dcf.py` |
| 3 | Unknown NRI line item guesses a field | **silent** | `analysis/normalizer.py` |
| 4 | No test suite; `pytest` cannot collect | stopping | `tests/` |
| 5 | Module-global extraction cache, popped on use | mixed | `api/routes_valuation.py` |
| 6 | Falsy treated as missing, five times | **silent** | `api/routes_valuation.py` |
| 7 | `cli.py` and `api/` duplicate the pipeline | **silent** | both |
| 8 | Blanket `except Exception` at four sites | **silent** | `api/`, `cli.py`, `ingestion/` |
| 9 | Unlabelled cost-of-debt assumption | **silent** | `analysis/wacc.py` |
| 10 | D&A subtraction buried in the parser | **silent** | `ingestion/claude_extractor.py` |
| 11 | 33 type errors, one a live crash path | stopping | 4 files |
| 12 | Dead code and stale repository hygiene | — | several |
| 13 | Provider changes with the number of PDFs uploaded | **silent** | `ingestion/`, `api/` |

---

## 1. 119 silent zero-default sites · **silent**

**Fact.** Reproduce:

```
grep -rnE "if [^)]+ else 0(\.0)?\b|\bor +0(\.0)?\b|\.get\([^,]+, *0(\.0)?\)|: *float *= *0\.0" \
  --include=*.py models analysis api ingestion | wc -l
```
→ **119**. Of these: 54 money fields defaulted to `0.0` in `models/`, 46 `.get(k, 0)` in
`ingestion/`, 14 conditional zeros and or-defaults elsewhere.

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

## 4. No test suite; `pytest` cannot collect · stopping

**Fact.** At `bc19431`:

- `grep -c "assert " tests/*.py` → **0** in all 10 files.
- `grep -c "__main__" tests/*.py` → **0** in all 10 files.
- `.venv/Scripts/python.exe -m pytest -q` → 3 collection errors, 0 tests.

Because no file guards its body, every one executes its whole pipeline — LLM call,
network fetch, DCF — at **import**. `pytest` therefore triggers paid API calls during
collection and fails before a test runs.

**What it costs.** Nothing detects items 1, 2, 3, 6 or 9. Every fix in this backlog is
unverifiable until this is addressed.

**Fix.** Keep the scripts — they are useful — but move them out of `pytest`'s collection
path, or guard them behind `if __name__ == "__main__":`. Then build a real suite per
[5-testing/strategy.md](../5-testing/strategy.md). **This is the prerequisite for
everything else here.**

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

## 12. Dead code and repository hygiene · —

Each is small. Grouped because none justifies a unit alone.

| Item | Evidence |
|---|---|
| `models/company.py` is dead — nothing imports `Company` | `grep -rn "from models.company"` → no hits |
| `BalanceSheet` imported but unused | `analysis/fcff.py:20` (F401) |
| `.DS_Store` tracked, twice | `git ls-files` → `.DS_Store`, `10K_filings/.DS_Store` |
| 5 pickled extraction files tracked | `cache/*.pkl` (2), `tests/*.pkl` (3). Loading a pickle **executes code in it** |
| `.gitignore` lists `CLAUDE.md`, which is **tracked** | git does not ignore a tracked file; the line is inert and misleading |
| `.gitignore` misses the cache dirs | `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `.agent/.seal-baseline.json` |
| `config.py` creates a directory at **import** | `config.py:8` — `UPLOAD_DIR.mkdir(exist_ok=True)`. Importing a config module should not touch the filesystem |
| `price_fetcher.py` imports pandas twice | module level line 9, then `import pandas as _pd` at line 65 |
| `yfinance` imported inside a request handler | `api/routes_valuation.py:182` — hides a network dependency from the import list |
| 28 unsorted-import and 6 empty-f-string lint errors | `ruff check tests cli.py` → 28; 26 auto-fixable |
| `datetime.today()` without a timezone | `ingestion/price_fetcher.py:42` (DTZ002) |

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

**Also note:** `_DEFAULT_MODELS["claude"]` is `"claude-sonnet-4-6"`, which is not a
current model ID. Verify it against the Claude API model list before relying on that
provider.

**Fix.** One default, in one place. Make `provider` explicit at the route and CLI
boundary, and show the resolved provider and model in the output as an assumption —
[rule 6](../2-rules/rules.md).

---

## Suggested order

Dependencies, not severity. **The order matters more than the ranking**, because
fixing a silent defect with no test in place produces an unverifiable claim.

1. **Item 4** — make `pytest` runnable and build the first real tests. Nothing else can
   be verified until this lands.
2. **Item 12's hygiene subset, and item 13** — `.gitignore`, dead code, lint, and the
   one provider default. Cheap, and they make every later diff readable.
3. **Item 7** — unify the pipeline, so each later fix is made once.
4. **Item 2**, then **item 3**, then **item 6**. The three highest-cost silent defects,
   each small and each now testable.
5. **Item 8**, then **item 11**. Typed failures, which item 1 depends on.
6. **Item 1** — the large one. Do it last, with the suite in place.
7. **Items 9, 10, 5.**

## Constraints on any unit taken from this list

- **Do not fix more than the assignment names.** An out-of-scope fix is a review
  finding even when the change is good.
- **Do not weaken, skip or `xfail` a test to make a suite green.**
- **Do not lock a defect as an expectation.** A test asserting `net_debt == 0.0` when
  the balance sheet is missing makes item 2 permanent and turns its fix red.
- **Re-measure the counts in this file when a unit lands.** They are measurements, and
  they carry a commit.
