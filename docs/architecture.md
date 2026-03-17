# Architecture & Module Reference

Detailed documentation for every module, class, function, and property in the valuation platform.

---

## Table of Contents

- [Configuration](#configuration)
- [Data Models](#data-models)
  - [financial_statements.py](#financial_statementspy)
  - [company.py](#companypy)
  - [valuation.py](#valuationpy)
- [Ingestion Layer](#ingestion-layer)
  - [capital_iq_parser.py](#capital_iq_parserpy)
  - [price_fetcher.py](#price_fetcherpy)
- [Analysis Engine](#analysis-engine)
  - [capm.py](#capmpy)
  - [wacc.py](#waccpy)
  - [fcff.py](#fcffpy)
  - [projector.py](#projectorpy)
  - [dcf.py](#dcfpy)
  - [normalizer.py](#normalizerpy)
- [API Routes](#api-routes)
  - [routes_upload.py](#routes_uploadpy)
  - [routes_valuation.py](#routes_valuationpy)
- [Web Application](#web-application)
- [Templates & Styling](#templates--styling)

---

## Configuration

**File:** `config.py`

| Constant | Value | Description |
|----------|-------|-------------|
| `BASE_DIR` | Project root | Path to the valuation_platform directory |
| `UPLOAD_DIR` | `BASE_DIR/uploads` | Where uploaded Excel files are saved (auto-created) |
| `DEFAULT_PROJECTION_YEARS` | `5` | Default forecast horizon |
| `DEFAULT_TERMINAL_GROWTH_RATE` | `0.025` | 2.5% perpetuity growth rate |
| `DEFAULT_EQUITY_RISK_PREMIUM` | `0.055` | 5.5% market risk premium |
| `DEFAULT_RISK_FREE_RATE` | `0.04` | 4.0% fallback if market fetch fails |
| `DEFAULT_BETA_LOOKBACK_YEARS` | `5` | Years of price history for beta regression |
| `DEFAULT_RETURN_FREQUENCY` | `"monthly"` | Return calculation frequency for CAPM |
| `SP500_TICKER` | `"^GSPC"` | Market index ticker for CAPM |

---

## Data Models

### financial_statements.py

**File:** `models/financial_statements.py`

#### `IncomeStatement`

Single-period income statement. All monetary fields default to `0.0`.

| Field | Type | Description |
|-------|------|-------------|
| `year` | `int` | Fiscal year |
| `revenue` | `float` | Total revenue / net sales |
| `cost_of_revenue` | `float` | COGS |
| `sga` | `float` | Selling, General & Administrative |
| `rd_expense` | `float` | Research & Development |
| `depreciation_amortization` | `float` | D&A (operating) |
| `other_operating_expense` | `float` | Other operating costs |
| `interest_expense` | `float` | Interest on debt |
| `interest_income` | `float` | Interest earned |
| `other_non_operating` | `float` | Other non-operating items |
| `tax_expense` | `float` | Income tax provision |
| `diluted_shares_outstanding` | `float` | Diluted share count |
| `non_recurring_items` | `dict[str, float]` | Tracked GAAP adjustments (populated by normalizer) |

**Computed Properties:**

| Property | Formula | Description |
|----------|---------|-------------|
| `gross_profit` | `revenue - cost_of_revenue` | |
| `gross_margin` | `gross_profit / revenue` | Returns 0 if revenue is 0 |
| `total_operating_expenses` | Sum of all opex fields | Includes COGS |
| `ebit` | `revenue - total_operating_expenses` | Operating income |
| `operating_margin` | `ebit / revenue` | Returns 0 if revenue is 0 |
| `ebt` | `ebit - interest_expense + interest_income + other_non_operating` | Earnings before tax |
| `net_income` | `ebt - tax_expense` | |
| `effective_tax_rate` | `tax_expense / ebt` | Returns 0 if EBT is 0 |
| `eps` | `net_income / diluted_shares_outstanding` | Returns 0 if shares is 0 |

---

#### `BalanceSheet`

Single-period balance sheet.

| Field | Type | Description |
|-------|------|-------------|
| `year` | `int` | Fiscal year |
| `cash_and_equivalents` | `float` | Cash & cash equivalents |
| `short_term_investments` | `float` | Short-term investments |
| `accounts_receivable` | `float` | A/R |
| `inventory` | `float` | Inventories |
| `other_current_assets` | `float` | Other current assets |
| `ppe_net` | `float` | PP&E, net of depreciation |
| `goodwill` | `float` | Goodwill |
| `intangible_assets` | `float` | Other intangibles |
| `other_non_current_assets` | `float` | Other long-term assets |
| `accounts_payable` | `float` | A/P |
| `short_term_debt` | `float` | Short-term borrowings |
| `current_portion_lt_debt` | `float` | Current portion of LT debt |
| `accrued_liabilities` | `float` | Accrued expenses |
| `other_current_liabilities` | `float` | Other current liabilities |
| `long_term_debt` | `float` | Long-term debt |
| `other_non_current_liabilities` | `float` | Other LT liabilities |
| `total_equity` | `float` | Total stockholders' equity |

**Computed Properties:**

| Property | Formula | Description |
|----------|---------|-------------|
| `total_current_assets` | Sum of all current asset fields | |
| `total_assets` | `total_current_assets + ppe_net + goodwill + intangible_assets + other_non_current_assets` | |
| `total_current_liabilities` | Sum of all current liability fields | |
| `total_liabilities` | `total_current_liabilities + long_term_debt + other_non_current_liabilities` | |
| `total_debt` | `short_term_debt + current_portion_lt_debt + long_term_debt` | All interest-bearing debt |
| `net_debt` | `total_debt - cash_and_equivalents` | |
| `net_working_capital` | `(A/R + inventory + other CA) - (A/P + accrued + other CL)` | Operating NWC, excludes cash and debt |

---

#### `CashFlowStatement`

Single-period cash flow statement.

| Field | Type | Description |
|-------|------|-------------|
| `year` | `int` | Fiscal year |
| `net_income` | `float` | Starting net income |
| `depreciation_amortization` | `float` | D&A add-back |
| `stock_based_compensation` | `float` | SBC add-back |
| `change_in_working_capital` | `float` | Net change in WC |
| `other_operating_activities` | `float` | Other CFO adjustments |
| `capital_expenditures` | `float` | CapEx (typically negative) |
| `acquisitions` | `float` | M&A spending |
| `other_investing_activities` | `float` | Other CFI |
| `debt_issued` | `float` | New debt proceeds |
| `debt_repaid` | `float` | Debt repayments (negative) |
| `shares_issued` | `float` | Stock issuance |
| `shares_repurchased` | `float` | Buybacks (negative) |
| `dividends_paid` | `float` | Dividend payments (negative) |
| `other_financing_activities` | `float` | Other CFF |

**Computed Properties:**

| Property | Formula |
|----------|---------|
| `cash_from_operations` | `net_income + D&A + SBC + change_in_WC + other_operating` |
| `cash_from_investing` | `capex + acquisitions + other_investing` |
| `cash_from_financing` | `debt_issued + debt_repaid + shares_issued + shares_repurchased + dividends + other_financing` |
| `net_change_in_cash` | `CFO + CFI + CFF` |

---

#### `FinancialStatements`

Container for multiple years of all three statements.

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | `str` | Stock ticker |
| `company_name` | `str` | Company name |
| `income_statements` | `list[IncomeStatement]` | Historical I/S |
| `balance_sheets` | `list[BalanceSheet]` | Historical B/S |
| `cash_flow_statements` | `list[CashFlowStatement]` | Historical C/F |

**Properties & Methods:**

| Name | Returns | Description |
|------|---------|-------------|
| `years` | `list[int]` | All unique years from income statements, sorted ascending |
| `latest_year` | `int` | Most recent year, or 0 if empty |
| `get_income_statement(year)` | `IncomeStatement \| None` | Lookup by year |
| `get_balance_sheet(year)` | `BalanceSheet \| None` | Lookup by year |
| `get_cash_flow(year)` | `CashFlowStatement \| None` | Lookup by year |

---

### company.py

**File:** `models/company.py`

#### `Company`

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | `str` | Stock ticker |
| `name` | `str` | Company name |
| `sector` | `str` | Sector classification |
| `industry` | `str` | Industry classification |
| `current_price` | `float` | Current stock price |
| `diluted_shares_outstanding` | `float` | Share count |
| `financials` | `FinancialStatements \| None` | Attached financial data |

| Property | Formula |
|----------|---------|
| `market_cap` | `current_price * diluted_shares_outstanding` |

---

### valuation.py

**File:** `models/valuation.py`

#### `CAPMResult`

| Field | Type | Description |
|-------|------|-------------|
| `beta` | `float` | Regression slope (systematic risk) |
| `risk_free_rate` | `float` | Annual risk-free rate (decimal) |
| `equity_risk_premium` | `float` | Market risk premium (decimal) |
| `r_squared` | `float` | Regression R-squared |
| `std_error` | `float` | Beta standard error |

| Property | Formula |
|----------|---------|
| `cost_of_equity` | `risk_free_rate + beta * equity_risk_premium` |

#### `WACCResult`

| Field | Type | Description |
|-------|------|-------------|
| `cost_of_equity` | `float` | From CAPM (decimal) |
| `cost_of_debt` | `float` | Pre-tax cost of debt (decimal) |
| `tax_rate` | `float` | Effective tax rate (decimal) |
| `equity_weight` | `float` | E / (E + D) |
| `debt_weight` | `float` | D / (E + D) |

| Property | Formula |
|----------|---------|
| `wacc` | `equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)` |

#### `ProjectedFCFF`

| Field | Type | Description |
|-------|------|-------------|
| `year` | `int` | Projection year |
| `revenue` | `float` | Projected revenue |
| `ebit` | `float` | Projected EBIT |
| `nopat` | `float` | Net operating profit after tax |
| `depreciation_amortization` | `float` | Projected D&A |
| `capital_expenditures` | `float` | Projected CapEx |
| `change_in_working_capital` | `float` | Projected delta NWC |

| Property | Formula |
|----------|---------|
| `fcff` | `nopat + D&A - abs(capex) - delta_NWC` |

#### `DCFResult`

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | `str` | Stock ticker |
| `projection_years` | `int` | Number of forecast years |
| `terminal_growth_rate` | `float` | Perpetuity growth rate (decimal) |
| `wacc` | `float` | Discount rate (decimal) |
| `projected_fcffs` | `list[ProjectedFCFF]` | Projected cash flows |
| `pv_fcffs` | `float` | Present value of projected FCFFs |
| `terminal_value` | `float` | Undiscounted terminal value |
| `pv_terminal_value` | `float` | Discounted terminal value |
| `net_debt` | `float` | Total debt minus cash |
| `cash` | `float` | Cash and equivalents |
| `diluted_shares` | `float` | Share count |
| `current_price` | `float` | Current stock price |

| Property | Formula |
|----------|---------|
| `enterprise_value` | `pv_fcffs + pv_terminal_value` |
| `equity_value` | `enterprise_value - net_debt` |
| `implied_share_price` | `equity_value / diluted_shares` |
| `upside_downside` | `(implied_share_price / current_price - 1) * 100` |

#### `ProjectionAssumptions`

User-configurable inputs for financial projections.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `projection_years` | `int` | `5` | Forecast horizon |
| `terminal_growth_rate` | `float` | `0.025` | 2.5% perpetuity growth |
| `revenue_growth_rates` | `list[float]` | `[]` | Per-year growth rates; empty = use CAGR |
| `operating_margin` | `float \| None` | `None` | Override; None = historical average |
| `tax_rate` | `float \| None` | `None` | Override; None = derived |
| `capex_pct_revenue` | `float \| None` | `None` | Override; None = historical average |
| `da_pct_revenue` | `float \| None` | `None` | Override; None = historical average |
| `nwc_pct_revenue` | `float \| None` | `None` | Override; None = historical average |
| `risk_free_rate` | `float \| None` | `None` | Override; None = fetch from market |
| `equity_risk_premium` | `float` | `0.055` | 5.5% default ERP |
| `cost_of_debt_override` | `float \| None` | `None` | Override pre-tax Rd |
| `beta_override` | `float \| None` | `None` | Override; None = regress |
| `beta_lookback_years` | `int` | `5` | Price history for regression |
| `return_frequency` | `str` | `"monthly"` | `"daily"` or `"monthly"` |

---

## Ingestion Layer

### capital_iq_parser.py

**File:** `ingestion/capital_iq_parser.py`

Parses S&P Capital IQ Pro Excel exports into `FinancialStatements` objects. Uses substring matching on row labels to map Capital IQ fields to dataclass attributes.

**Row Label Mappings:**

Three dictionaries (`IS_MAPPING`, `BS_MAPPING`, `CF_MAPPING`) map Capital IQ row label substrings (case-insensitive) to dataclass field names. Examples:

- `"total revenue"` → `revenue`
- `"cost of goods sold"` → `cost_of_revenue`
- `"long-term debt"` → `long_term_debt`
- `"capital expenditure"` → `capital_expenditures`

**Internal Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `_parse_excel_sheet` | `(file_path, sheet_name=0, header_row=0) → DataFrame` | Read Excel file; first column becomes `"label"` |
| `_extract_years` | `(df) → list[int]` | Extract 4-digit years (1990-2100) from column headers |
| `_match_label` | `(label, mapping) → str \| None` | Case-insensitive substring match against mapping keys |
| `_safe_float` | `(value) → float` | Convert to float; handles NaN, commas, parentheses as negatives |

**Public Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `parse_income_statement` | `(file_path, sheet_name=0) → list[IncomeStatement]` | Parse I/S Excel sheet |
| `parse_balance_sheet` | `(file_path, sheet_name=0) → list[BalanceSheet]` | Parse B/S Excel sheet |
| `parse_cash_flow` | `(file_path, sheet_name=0) → list[CashFlowStatement]` | Parse C/F Excel sheet |
| `parse_capital_iq` | `(is_path, bs_path, cf_path, ticker, company_name="") → FinancialStatements` | Parse all three into unified object |

---

### price_fetcher.py

**File:** `ingestion/price_fetcher.py`

Fetches historical stock and S&P 500 prices via `yfinance` for CAPM beta calculation.

#### `PriceData` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | `str` | Stock ticker |
| `stock_returns` | `np.ndarray` | Aligned stock returns |
| `market_returns` | `np.ndarray` | Aligned S&P 500 returns |
| `dates` | `pd.DatetimeIndex` | Common dates |
| `current_price` | `float` | Most recent closing price |

#### `fetch_price_data`

```python
fetch_price_data(ticker: str, lookback_years: int = 5, frequency: str = "monthly") → PriceData
```

**Process:**
1. Calculate date range: today minus `lookback_years * 365` days
2. Download adjusted close for stock and `^GSPC` via `yfinance`
3. Resample to month-end if `frequency == "monthly"`
4. Calculate percentage returns via `pct_change()`
5. Align on common dates, drop NaN
6. Extract current price from latest data point

**Raises:** `ValueError` if data cannot be fetched.

---

## Analysis Engine

### capm.py

**File:** `analysis/capm.py`

**Formula:** `E(Ri) = Rf + β × (E(Rm) - Rf)`

| Function | Signature | Description |
|----------|-----------|-------------|
| `calculate_beta` | `(price_data) → (beta, r_squared, std_error)` | OLS regression via `scipy.stats.linregress` |
| `run_capm` | `(price_data, risk_free_rate=None, equity_risk_premium=None, beta_override=None) → CAPMResult` | Full CAPM calculation; uses config defaults for None values; skips regression if beta_override provided |

---

### wacc.py

**File:** `analysis/wacc.py`

**Formula:** `WACC = (E/V) × Re + (D/V) × Rd × (1 - T)`

| Function | Signature | Description |
|----------|-----------|-------------|
| `calculate_cost_of_debt` | `(income_statement, balance_sheet, override=None) → float` | `Rd = interest_expense / total_debt` or override; returns 0 if no debt |
| `calculate_wacc` | `(capm_result, income_statement, balance_sheet, market_cap, cost_of_debt_override=None, tax_rate_override=None) → WACCResult` | Full WACC; E = market_cap, D = total_debt; tax rate clamped to [0%, 50%]; returns 100% equity weight if V = 0 |

---

### fcff.py

**File:** `analysis/fcff.py`

**Formula:** `FCFF = EBIT × (1 - T) + D&A - CapEx - ΔWC`

| Function | Signature | Description |
|----------|-----------|-------------|
| `calculate_fcff_historical` | `(income_statement, cash_flow, balance_sheet, prior_balance_sheet=None, tax_rate_override=None) → ProjectedFCFF` | From actual financial statements; ΔWC = 0 if no prior balance sheet; tax rate clamped to [0%, 50%] |
| `calculate_fcff_projected` | `(year, revenue, operating_margin, tax_rate, da_pct_revenue, capex_pct_revenue, nwc_pct_revenue, prior_nwc) → ProjectedFCFF` | From assumptions; all margin/pct inputs are decimals |

---

### projector.py

**File:** `analysis/projector.py`

Derives default assumptions from historical data and projects future FCFFs.

**Internal Helpers:**

| Function | Description |
|----------|-------------|
| `_historical_average(values)` | Mean of non-zero values only |
| `_historical_cagr(first, last, periods)` | `(last/first)^(1/periods) - 1`; returns 0 if any input ≤ 0 |

**Public Functions:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `derive_assumptions` | `(financials, overrides=None) → dict` | Derive all projection parameters from historical averages; user overrides take priority; returns dict with keys: `revenue_growth_rates`, `operating_margin`, `tax_rate`, `da_pct_revenue`, `capex_pct_revenue`, `nwc_pct_revenue`, `projection_years`, `terminal_growth_rate` |
| `project_fcffs` | `(financials, assumptions) → list[ProjectedFCFF]` | Generate projected FCFF for each forecast year; compounds revenue growth year-over-year; tracks running NWC for delta calculation |

---

### dcf.py

**File:** `analysis/dcf.py`

DCF valuation engine with Gordon Growth Model terminal value.

| Function | Signature | Description |
|----------|-----------|-------------|
| `calculate_terminal_value` | `(final_fcff, terminal_growth_rate, wacc) → float` | `TV = FCFF_n × (1+g) / (WACC-g)`; raises `ValueError` if WACC ≤ g |
| `discount_cash_flows` | `(projected_fcffs, wacc) → float` | `PV = Σ FCFF_t / (1+WACC)^t` for t = 1..n |
| `run_dcf` | `(projected_fcffs, wacc_result, financials, terminal_growth_rate, current_price, diluted_shares) → DCFResult` | Full DCF: discount FCFFs + terminal value; extract net debt from latest B/S; compute EV → equity value → implied share price |

---

### normalizer.py

**File:** `analysis/normalizer.py`

GAAP → Non-GAAP adjustment engine. Currently supports manual adjustments; Phase 2 will add Claude API automation.

| Function | Signature | Description |
|----------|-----------|-------------|
| `apply_manual_adjustments` | `(income_statement, adjustments: dict[str, float]) → IncomeStatement` | Apply adjustments to a single I/S; positive values reduce expenses (increase earnings); stores adjustments in `non_recurring_items` for audit trail; nets total into `other_operating_expense` |
| `normalize_financials` | `(financials, adjustments_by_year: dict[int, dict] \| None) → FinancialStatements` | Apply adjustments across all years; returns new `FinancialStatements` with adjusted I/S, original B/S and C/F |

---

## API Routes

### routes_upload.py

**File:** `api/routes_upload.py`

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Render file upload form |
| `/upload` | POST | Accept 3 Excel files (I/S, B/S, C/F) + ticker + company name; save to `uploads/{TICKER}/`; redirect to `/assumptions` with file paths as query params |

**Internal:** `_save_upload(file, prefix, ticker) → Path` saves uploaded file as `{prefix}_{filename}` under ticker directory.

---

### routes_valuation.py

**File:** `api/routes_valuation.py`

| Route | Method | Description |
|-------|--------|-------------|
| `/assumptions` | GET | Show assumptions form; auto-derives defaults from uploaded financials; displays pre-populated values |
| `/valuation` | POST | Execute full DCF pipeline: parse → assumptions → yfinance → CAPM → WACC → project FCFFs → DCF → render results |

**`/valuation` Form Parameters (13 total):**

All percentage inputs are entered as whole numbers (e.g., `5.5` for 5.5%) and converted to decimals internally.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ticker` | `str` | required | Stock ticker |
| `company_name` | `str` | `""` | Optional company name |
| `is_path, bs_path, cf_path` | `str` | required | Paths to uploaded Excel files |
| `projection_years` | `int` | `5` | Forecast horizon |
| `terminal_growth_rate` | `float` | `2.5` | Terminal growth rate (%) |
| `revenue_growth` | `str` | `""` | Comma-separated rates (%); blank = use CAGR |
| `operating_margin` | `float` | `0` | Operating margin (%); 0 = historical avg |
| `tax_rate` | `float` | `0` | Tax rate (%); 0 = derived |
| `da_pct` | `float` | `0` | D&A as % of revenue; 0 = historical avg |
| `capex_pct` | `float` | `0` | CapEx as % of revenue; 0 = historical avg |
| `nwc_pct` | `float` | `0` | NWC as % of revenue; 0 = historical avg |
| `risk_free_rate` | `float` | `4.0` | Risk-free rate (%) |
| `equity_risk_premium` | `float` | `5.5` | Market risk premium (%) |
| `beta_override` | `str` | `""` | Optional beta override; blank = regress |
| `cost_of_debt_override` | `str` | `""` | Optional cost of debt (%); blank = derive |
| `beta_lookback_years` | `int` | `5` | Price history for regression |
| `return_frequency` | `str` | `"monthly"` | `"daily"` or `"monthly"` |

---

## Web Application

**File:** `app.py`

- Creates FastAPI app (`title="DCF Valuation Platform"`, `version="1.0.0"`)
- Mounts `/static` directory for CSS/JS
- Registers `upload_router` and `valuation_router`
- Inserts project root into `sys.path` for module imports

**Run command:**
```bash
python -m uvicorn app:app --reload
```

---

## Templates & Styling

### Templates (Jinja2)

| Template | Route | Description |
|----------|-------|-------------|
| `base.html` | — | Base layout: navbar with brand & links, main container, script block |
| `upload.html` | `GET /` | File upload form: ticker, company name, 3 Excel file inputs |
| `assumptions.html` | `GET /assumptions` | Assumptions form with sections: projection settings, revenue & margins, CapEx & WC, WACC/CAPM inputs |
| `valuation_result.html` | `POST /valuation` | Results display: summary cards (implied price, current price, upside/downside), CAPM/WACC table, projected FCFF table, DCF bridge table, assumptions audit |

### Static Assets

**`static/style.css`** — Professional theme using CSS variables:

| Variable | Value | Usage |
|----------|-------|-------|
| `--primary` | `#1a56db` | Buttons, section borders |
| `--positive` | `#047857` | Green for upside indicators |
| `--negative` | `#dc2626` | Red for downside indicators |
| `--bg` | `#f8fafc` | Page background |
| `--card-bg` | `#ffffff` | Card backgrounds |
| `--text` | `#1e293b` | Primary text |
| `--text-secondary` | `#64748b` | Muted text |

**Key CSS components:** navbar, cards, form groups/rows, buttons (primary/secondary), summary grid (3-column), data tables with highlight rows, section headers with blue underline, error alerts.
