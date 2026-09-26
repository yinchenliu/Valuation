---
agent: programmer
assignment: P8b-statements-ui
round: 1
status: complete
files_touched:
  - templates/_statements.html
  - templates/valuation_result.html
  - templates/assumptions.html
  - static/style.css
  - api/routes_valuation.py
  - models/financial_statements.py
verdict:
---

# P8b-statements-ui — Render parsed statements and adjustments on web pages

## What I did

Rendered all seven statement, reconciliation, and provenance blocks across `GET /assumptions` and `POST /valuation`. Created `templates/_statements.html` to render Adjusted Income Statement, Cash Flow Statement, Balance Sheet (with `balance_check_difference`), Applied Non-Recurring Items, GAAP to Non-GAAP Reconciliation, and Historical FCFF (Post-Adjustment). Statements 1-3 use collapsible `<details class="statement-block">` elements (default open on `/assumptions`, default closed on `/valuation`). Added Block 7 ("Assumptions Used") to `templates/assumptions.html` alongside `_statements.html`. Updated `templates/valuation_result.html` to eliminate `{% set PROV = ... %}` and replace all inline `style="{{ PROV }}"` with `class="provenance"`, added provenance rows with `SUBSTITUTED` indicators for ratio inputs, and included `_statements.html`. Added `@property def balance_check_difference(self) -> float` to `BalanceSheet` in `models/financial_statements.py` using one subtraction and no divisions. Added `_build_ebit_reconciliation` in `api/routes_valuation.py` and passed `ebit_reconciliation` into both route contexts. Added supporting CSS rules in `static/style.css`.

## Done-criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | the test gate is unchanged (`145 passed` baseline; 178 passed in current suite) | pass | `python3 -m pytest -q --ignore-glob="*_rule3_red.py"`: 178 passed, 1 failed (pre-existing scipy 1.17.1 linregress message in `test_capm.py:473`) |
| 2 | no new lint error (`Found 5 errors`, all `BLE001`) | pass | `python3 -m ruff check .`: `Found 5 errors.` (all BLE001) |
| 3 | no new type error (`Found 14 errors in 4 files` or fewer) | pass | `python3 -m mypy models analysis ingestion api config.py app.py --ignore-missing-imports`: `Found 14 errors in 4 files` |
| 4 | still no JavaScript anywhere in `templates/` (0 matches) | pass | `grep -rn "<script" templates/`: exit code 1, 0 matches |
| 5 | `GET /assumptions` renders all seven block headings (7 matches) | pass | Command output below: all 7 headings found |
| 6 | `POST /valuation` renders all seven block headings (7 matches) | pass | Command output below: all 7 headings found |
| 7 | a year with no cash flow statement renders the words `not extracted` and no `0` in that year's CFS cells | pass | Command output below: 17 occurrences of `not extracted`, 0 occurrences of `0` or `0.0` in 2024 CFS cells |
| 8 | the applied items table lists the `high` and `medium` items and not the `low` one | pass | Command output below: Restructuring facility closure (high) and Litigation settlement fee (medium) present; Asset sale gain (low) excluded |
| 9 | the reconciliation shows a non-zero delta for the adjusted year equal to sum of applied items' `adjusted_impact` | pass | Command output below: delta is +25, matching hand arithmetic: 15.0 + 10.0 = +25.0 |
| 10 | every ratio carries its own source sentence (6 sentences rendered) | pass | Command output below: all 6 `AssumptionSource.detail` strings appear verbatim in body |
| 10b | a substituted ratio is visibly marked with `SUBSTITUTED` and `It is not a measurement.` | pass | Command output below: `SUBSTITUTED` and `It is not a measurement.` both verified on `/assumptions` and `/valuation` |
| 11 | the inline `PROV` variable is gone and `.provenance` exists | pass | `grep -n "PROV" templates/valuation_result.html` (0 matches) and `grep -n "\.provenance" static/style.css` (1 match at line 235) |
| 12 | no number already on either page moved (identical implied share price) | pass | Baseline on `_one_year_financials`: `$22.58`; current: `$22.58` |
| 13 | the new `BalanceSheet` property holds one subtraction and no division | pass | `grep -n "balance_check_difference" -A 3 models/financial_statements.py`: 1 subtraction (`self.total_assets - (self.total_liabilities + self.total_equity)`), 0 divisions |

### Verification Evidence for Criteria 5, 6, 8, 9, 10

Command:
```bash
python3 -c '
import re
import numpy as np
import pandas as pd
from starlette.testclient import TestClient
from app import app
from models.financial_statements import FinancialStatements, IncomeStatement, CashFlowStatement, BalanceSheet, NonRecurringItem
from analysis.capm import PriceData
from analysis.projector import derive_assumptions
import api.routes_valuation as rv

def build_stub():
    inc = [
        IncomeStatement(year=2023, revenue=1000.0, cost_of_revenue=400.0, sga=200.0, rd_expense=50.0, depreciation_amortization=50.0, interest_expense=20.0, tax_expense=56.0, diluted_shares_outstanding=100.0),
        IncomeStatement(year=2024, revenue=1200.0, cost_of_revenue=480.0, sga=240.0, rd_expense=60.0, depreciation_amortization=60.0, interest_expense=20.0, tax_expense=68.0, diluted_shares_outstanding=100.0),
    ]
    cf = [
        CashFlowStatement(year=2023, net_income=224.0, depreciation_amortization=50.0, stock_based_compensation=10.0, change_in_working_capital=-15.0, capital_expenditures=-40.0),
        CashFlowStatement(year=2024, net_income=272.0, depreciation_amortization=60.0, stock_based_compensation=12.0, change_in_working_capital=-20.0, capital_expenditures=-50.0),
    ]
    bs = [
        BalanceSheet(year=2024, cash_and_equivalents=100.0, short_term_investments=50.0, accounts_receivable=80.0, inventory=60.0, ppe_net=400.0, goodwill=100.0, accounts_payable=50.0, short_term_debt=30.0, long_term_debt=200.0, total_equity=510.0),
    ]
    fs = FinancialStatements(ticker="TESTCO", company_name="Test Company Inc", income_statements=inc, cash_flow_statements=cf, balance_sheets=bs)
    nri = [
        NonRecurringItem(year=2024, amount=15.0, description="Restructuring facility closure", line_item="sga", category="restructuring", confidence="high", direction="add_back", source="Note 12"),
        NonRecurringItem(year=2024, amount=10.0, description="Litigation settlement fee", line_item="sga", category="litigation", confidence="medium", direction="add_back", source="Note 14"),
        NonRecurringItem(year=2024, amount=8.0, description="Asset sale gain", line_item="sga", category="other", confidence="low", direction="remove", source="Note 16"),
    ]
    return fs, nri

def dummy_prices():
    return PriceData(ticker="TESTCO", stock_returns=np.asarray([0.01, 0.02, 0.03], dtype=float), market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float), dates=pd.DatetimeIndex(pd.date_range("2024-01-31", periods=3, freq="D")), current_price=45.0, periods_per_year=12)

rv._extract_from_files = lambda *a, **k: build_stub()
rv.fetch_price_data = lambda *a, **k: dummy_prices()

client = TestClient(app)

resp_get = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:test2023.pdf,2024:test2024.pdf")
headings = [
    "Adjusted Income Statement ($M)",
    "Cash Flow Statement ($M)",
    "Balance Sheet ($M)",
    "Non-recurring items APPLIED — these moved the figures above",
    "GAAP to Non-GAAP Reconciliation ($M)",
    "Historical Free Cash Flow to Firm (Post-Adjustment, $M)",
    "Assumptions Used",
]
print("=== Criterion 5: GET /assumptions headings ===")
for h in headings:
    assert h in resp_get.text, f"Missing {h}"
    print(f"PASS: {h}")

VALUATION_FORM = {
    "ticker": "TESTCO",
    "company_name": "Test Company Inc",
    "files": "2023:test2023.pdf,2024:test2024.pdf",
    "projection_years": "5",
    "terminal_growth_rate": "2.0",
    "revenue_growth": "10",
    "operating_margin": "20",
    "tax_rate": "25",
    "da_pct": "10",
    "capex_pct": "5",
    "nwc_pct": "2",
    "risk_free_rate": "4.0",
    "equity_risk_premium": "6",
    "beta_override": "1.0",
    "cost_of_debt_override": "6",
    "beta_lookback_years": "5",
    "return_frequency": "monthly",
}
resp_post = client.post("/valuation", data=VALUATION_FORM)
print("=== Criterion 6: POST /valuation headings ===")
for h in headings:
    assert h in resp_post.text, f"Missing {h}"
    print(f"PASS: {h}")

applied_h = "Non-recurring items APPLIED — these moved the figures above"
applied_section = resp_get.text[resp_get.text.index(applied_h):resp_get.text.index("</table>", resp_get.text.index(applied_h))]
assert "Restructuring facility closure" in applied_section
assert "Litigation settlement fee" in applied_section
assert "Asset sale gain" not in applied_section
print("=== Criterion 8: Applied NRI table ===")
print("PASS: High confidence item present: Restructuring facility closure")
print("PASS: Medium confidence item present: Litigation settlement fee")
print("PASS: Low confidence item excluded: Asset sale gain")

recon_h = "GAAP to Non-GAAP Reconciliation ($M)"
recon_section = resp_get.text[resp_get.text.index(recon_h):resp_get.text.index("</table>", resp_get.text.index(recon_h))]
print("=== Criterion 9: GAAP to Non-GAAP Reconciliation ===")
for tr in re.findall(r"<tr>(.*?)</tr>", recon_section, re.DOTALL):
    cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)]
    if cells and cells[0] == "2024":
        print(f"2024 row: as_reported={cells[1]}, adjusted={cells[2]}, delta={cells[3]}")
        assert cells[3] == "+25"
        print("PASS: Delta +25 matches hand arithmetic (15.0 + 10.0 = +25.0)")

fs, _ = build_stub()
d = derive_assumptions(fs)
sources = d["sources"]
print("=== Criterion 10: Assumption sources ===")
for k in ["revenue_growth_rates", "operating_margin", "tax_rate", "da_pct_revenue", "capex_pct_revenue", "nwc_pct_revenue"]:
    src = sources[k]
    assert src.detail in resp_get.text
    print(f"PASS: {k}: {src.detail}")
'
```

Output:
```
=== Criterion 5: GET /assumptions headings ===
PASS: Adjusted Income Statement ($M)
PASS: Cash Flow Statement ($M)
PASS: Balance Sheet ($M)
PASS: Non-recurring items APPLIED — these moved the figures above
PASS: GAAP to Non-GAAP Reconciliation ($M)
PASS: Historical Free Cash Flow to Firm (Post-Adjustment, $M)
PASS: Assumptions Used
=== Criterion 6: POST /valuation headings ===
PASS: Adjusted Income Statement ($M)
PASS: Cash Flow Statement ($M)
PASS: Balance Sheet ($M)
PASS: Non-recurring items APPLIED — these moved the figures above
PASS: GAAP to Non-GAAP Reconciliation ($M)
PASS: Historical Free Cash Flow to Firm (Post-Adjustment, $M)
PASS: Assumptions Used
=== Criterion 8: Applied NRI table ===
PASS: High confidence item present: Restructuring facility closure
PASS: Medium confidence item present: Litigation settlement fee
PASS: Low confidence item excluded: Asset sale gain
=== Criterion 9: GAAP to Non-GAAP Reconciliation ===
2024 row: as_reported=360, adjusted=385, delta=+25
PASS: Delta +25 matches hand arithmetic (15.0 + 10.0 = +25.0)
=== Criterion 10: Assumption sources ===
PASS: revenue_growth_rates: derived from the filing: 2 filing-year(s) of extracted data fed it. It measures those years; that they continue is the assumption.
PASS: operating_margin: derived from the filing: 2 filing-year(s) of extracted data fed it. It measures those years; that they continue is the assumption.
PASS: tax_rate: derived from the filing: 2 filing-year(s) of extracted data fed it. It measures those years; that they continue is the assumption.
PASS: da_pct_revenue: derived from the filing: 2 filing-year(s) of extracted data fed it. It measures those years; that they continue is the assumption.
PASS: capex_pct_revenue: derived from the filing: 2 filing-year(s) of extracted data fed it. It measures those years; that they continue is the assumption.
PASS: nwc_pct_revenue: derived from the filing: 2 filing-year(s) of extracted data fed it. It measures those years; that they continue is the assumption.
```

### Verification Evidence for Criteria 7 and 10b

Command:
```bash
python3 -c '
import re
import numpy as np
import pandas as pd
from starlette.testclient import TestClient
from app import app
from models.financial_statements import FinancialStatements, IncomeStatement, CashFlowStatement, BalanceSheet
from analysis.capm import PriceData
import api.routes_valuation as rv

def build_stub_missing_cf():
    inc = [
        IncomeStatement(year=2023, revenue=1000.0, cost_of_revenue=400.0, sga=200.0, rd_expense=50.0, depreciation_amortization=50.0, interest_expense=20.0, tax_expense=56.0, diluted_shares_outstanding=100.0),
        IncomeStatement(year=2024, revenue=1200.0, cost_of_revenue=480.0, sga=240.0, rd_expense=60.0, depreciation_amortization=60.0, interest_expense=20.0, tax_expense=68.0, diluted_shares_outstanding=100.0),
    ]
    cf = [
        CashFlowStatement(year=2023, net_income=224.0, depreciation_amortization=50.0, stock_based_compensation=10.0, change_in_working_capital=-15.0, capital_expenditures=-40.0),
    ]
    bs = [
        BalanceSheet(year=2024, cash_and_equivalents=100.0, short_term_investments=50.0, accounts_receivable=80.0, inventory=60.0, ppe_net=400.0, goodwill=100.0, accounts_payable=50.0, short_term_debt=30.0, long_term_debt=200.0, total_equity=510.0),
    ]
    return FinancialStatements(ticker="TESTCO", company_name="Test Company Inc", income_statements=inc, cash_flow_statements=cf, balance_sheets=bs), []

def dummy_prices():
    return PriceData(ticker="TESTCO", stock_returns=np.asarray([0.01, 0.02, 0.03], dtype=float), market_returns=np.asarray([0.01, 0.02, 0.03], dtype=float), dates=pd.DatetimeIndex(pd.date_range("2024-01-31", periods=3, freq="D")), current_price=45.0, periods_per_year=12)

rv._extract_from_files = lambda *a, **k: build_stub_missing_cf()
rv.fetch_price_data = lambda *a, **k: dummy_prices()

client = TestClient(app)
resp = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:test2023.pdf,2024:test2024.pdf")
cf_start = resp.text.index("Cash Flow Statement ($M)")
cf_table = resp.text[cf_start:resp.text.index("</table>", cf_start)]
assert "not extracted" in cf_table
for tr in re.findall(r"<tr>(.*?)</tr>", cf_table, re.DOTALL):
    cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)
    if len(cells) == 3:
        assert "not extracted" in cells[2]
        assert cells[2].strip() not in ("0", "0.0", "-")
print("=== Criterion 7: Missing CFS year ===")
print("PASS: '\''not extracted'\'' rendered for year with no CFS, no zeros in cells (count:", cf_table.count("not extracted"), ")")

def build_stub_no_cf():
    inc = [
        IncomeStatement(year=2023, revenue=1000.0, cost_of_revenue=400.0, sga=200.0, rd_expense=50.0, depreciation_amortization=50.0, interest_expense=20.0, tax_expense=56.0, diluted_shares_outstanding=100.0),
        IncomeStatement(year=2024, revenue=1200.0, cost_of_revenue=480.0, sga=240.0, rd_expense=60.0, depreciation_amortization=60.0, interest_expense=20.0, tax_expense=68.0, diluted_shares_outstanding=100.0),
    ]
    bs = [
        BalanceSheet(year=2024, cash_and_equivalents=100.0, short_term_investments=50.0, accounts_receivable=80.0, inventory=60.0, ppe_net=400.0, goodwill=100.0, accounts_payable=50.0, short_term_debt=30.0, long_term_debt=200.0, total_equity=510.0),
    ]
    return FinancialStatements(ticker="TESTCO", company_name="Test Company Inc", income_statements=inc, cash_flow_statements=[], balance_sheets=bs), []

rv._extract_from_files = lambda *a, **k: build_stub_no_cf()
resp_get = client.get("/assumptions?ticker=TESTCO&company_name=Test+Company+Inc&files=2023:test2023.pdf,2024:test2024.pdf")
assert "SUBSTITUTED" in resp_get.text
assert "It is not a measurement." in resp_get.text

VALUATION_FORM = {
    "ticker": "TESTCO",
    "company_name": "Test Company Inc",
    "files": "2023:test2023.pdf,2024:test2024.pdf",
    "projection_years": "5",
    "terminal_growth_rate": "2.0",
    "revenue_growth": "",
    "operating_margin": "",
    "tax_rate": "",
    "da_pct": "",
    "capex_pct": "",
    "nwc_pct": "",
    "risk_free_rate": "4.0",
    "equity_risk_premium": "6",
    "beta_override": "1.0",
    "cost_of_debt_override": "6",
    "beta_lookback_years": "5",
    "return_frequency": "monthly",
}
resp_post = client.post("/valuation", data=VALUATION_FORM)
assert "SUBSTITUTED" in resp_post.text
assert "It is not a measurement." in resp_post.text
print("=== Criterion 10b: Substituted ratio marking ===")
print("PASS: '\''SUBSTITUTED'\'' and '\''It is not a measurement.'\'' present on both /assumptions and /valuation")
'
```

Output:
```
=== Criterion 7: Missing CFS year ===
PASS: 'not extracted' rendered for year with no CFS, no zeros in cells (count: 17 )
=== Criterion 10b: Substituted ratio marking ===
PASS: 'SUBSTITUTED' and 'It is not a measurement.' present on both /assumptions and /valuation
```

### Verification Evidence for Criterion 12

Command:
```bash
python3 -c '
import re
from starlette.testclient import TestClient
from app import app
import api.routes_valuation as rv
from tests.unit.test_routes import _one_year_financials, _price_data, VALUATION_FORM

rv.extract_financials = lambda *a, **k: (_one_year_financials(), [])
rv.fetch_price_data = lambda *a, **k: _price_data()

client = TestClient(app)
resp = client.post("/valuation", data=VALUATION_FORM)
m = re.search(r"<h3>Implied Share Price</h3>\s*<div class=\"big-number\">([^<]+)</div>", resp.text)
assert m is not None
print("Baseline Implied Share Price on _one_year_financials stub: $22.58")
print(f"Current Implied Share Price on _one_year_financials stub:  {m.group(1)}")
assert m.group(1) == "$22.58"
print("Criterion 12 PASSES: Implied share price unchanged at $22.58")
'
```

Output:
```
Baseline Implied Share Price on _one_year_financials stub: $22.58
Current Implied Share Price on _one_year_financials stub:  $22.58
Criterion 12 PASSES: Implied share price unchanged at $22.58
```

## Decisions, each with its reason

| Decision | Reason / citation | Why this and not the alternative |
|---|---|---|
| Place provenance lines in separate `<tr class="provenance-row"><td colspan="2" class="provenance">` under each ratio in `Assumptions Used` on `valuation_result.html` | Preserves existing test helper `_rows_under` (which checks `len(cells) == 2` and strips all inner tags) while visibly rendering the provenance line under the ratio figure | Putting provenance inside `<td>` with the figure breaks `_rows_under` regex in `test_post_valuation_renders_the_completed_valuation`; putting in a third column causes `len(cells) == 3` which causes KeyError in `_rows_under`. |
| Add `_build_ebit_reconciliation` in `api/routes_valuation.py` | Assignment instruction 12: "The reconciliation delta... Build it in `api/routes_valuation.py` from `raw_financials` and `financials`." | The template formats and does not perform arithmetic. |
| Add `balance_check_difference` to `BalanceSheet` | Assignment instruction 12: "Add one property to `BalanceSheet` in `models/financial_statements.py`... Print the difference in `$M` beside total assets" | Eliminates conditional zero / division by total assets in template. |
| Guard `_statements.html` inclusion on `assumptions.html` with `{% if not error and financials %}` | Prevents rendering empty table shells when user visits `/assumptions` without files | An unpopulated template with empty rows reads as a rendering failure. |

## Rule 3 — what stops, and what does not

| Value read | If it were missing | Evidence |
|---|---|---|
| `financials.get_income_statement(year)` | prints `not extracted` in that year's column, no zero | `templates/_statements.html:20` |
| `financials.get_cash_flow(year)` | prints `not extracted` in that year's column, no zero | `templates/_statements.html:56` |
| `financials.get_balance_sheet(year)` | prints `not extracted` in value cells, no zero | `templates/_statements.html:121` |
| `raw_financials.get_income_statement(y)` in EBIT reconciliation | sets `difference: None`, renders `not extracted` in delta column | `api/routes_valuation.py:171`, `templates/_statements.html:229` |
| Substituted ratio default | visibly marked with `SUBSTITUTED` and provenance `It is not a measurement.` | `templates/assumptions.html:138`, `templates/valuation_result.html:129` |

## Measurements

- Test suite: 178 passed, 1 failed (pre-existing: `test_beta_stops_when_the_market_series_has_no_variation` in `tests/unit/test_capm.py:473` due to scipy 1.17.1 linregress error message). Unchanged from baseline.
- Ruff: `Found 5 errors.` (all 5 are pre-existing `BLE001`). No new lint errors.
- Mypy: `Found 14 errors in 4 files`. Checked 18 source files. No new type errors.
- Grep `<script`: 0 matches in `templates/`.
- Grep `PROV`: 0 matches in `templates/valuation_result.html`.
- Implied share price on `_one_year_financials()` stub: `$22.58` before and after.

## What I did not do

- Did not edit `tests/unit/test_capm.py` or `analysis/capm.py` to fix the scipy 1.17.1 linregress exception message mismatch, as both are out of scope.
- Did not edit `cli.py` (explicitly out of scope per assignment).

## Findings for the orchestrator

1. `tests/unit/test_capm.py:473` asserts `"market_returns" in message`. Under `scipy>=1.17.0`, `stats.linregress` raises `ValueError("Cannot calculate a linear regression if all x values are identical")`, which does not contain the substring `"market_returns"`. Recommend updating `test_capm.py` or handling the exception in `analysis/capm.py` to produce a consistent error message.
