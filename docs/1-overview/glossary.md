# Glossary

Each term defined once. **This file is the owner** — no other document redefines one
of these, it links here.

Ordered by where you meet it in [the pipeline](pipeline.md), not alphabetically.

---

## Filings

**10-K** — a company's annual report to the SEC. Holds three financial statements plus
the notes that explain them. The only source of financial data in this repository
([rule 5](../2-rules/rules.md)).

**10-Q** — the quarterly equivalent. Shorter, unaudited.

**MD&A** — Management's Discussion and Analysis. The narrative section where management
explains the year. Pass 2 of extraction reads it for one-time items.

**Fiscal year (FY)** — a company's own twelve-month accounting year. It need not match
the calendar. A 10-K shows the current year plus one or two comparative prior years,
which is why `extract_multi_year()` routes years to filings rather than extracting
every year from every PDF.

## The three statements

**Income statement (I/S)** — revenue minus costs over a period, ending in net income.

**Balance sheet (B/S)** — what the company owns and owes at one instant. Used here only
for the equity bridge and for debt weights.

**Cash flow statement (C/F, CFS)** — how cash actually moved over the period, in three
sections: operating, investing, financing.

**CFO** — Cash From Operations. The operating section's total. Under US GAAP, interest
paid sits in this section, so **CFO is after interest** — the reason
`calculate_fcff_historical` adds after-tax interest back.

**CapEx** — Capital Expenditures. Cash spent on long-lived assets. Reported negative on
the CFS; used as a positive magnitude in every formula here.

**D&A** — Depreciation and Amortisation. The non-cash spreading of an asset's cost over
its life. Subtracted on the I/S, added back on the CFS.

**SBC** — Stock-Based Compensation. Pay issued as shares. Non-cash, so added back in
CFO. This is why CFO-based and EBIT-based FCFF differ materially for technology
companies.

## Earnings measures

**Gross profit** — revenue minus cost of revenue.

**EBIT** — Earnings Before Interest and Taxes. Operating profit. Here:
`revenue - total_operating_expenses`.

**EBT** — Earnings Before Tax. EBIT after interest and other non-operating items.

**Net income** — EBT minus tax. The bottom line.

**Operating margin** — EBIT ÷ revenue.

**Effective tax rate** — tax expense ÷ EBT. What the company actually paid, as opposed
to the statutory rate.

**NOPAT** — Net Operating Profit After Tax. `EBIT × (1 − tax rate)`. Profit as if the
company had no debt, which is what makes it the right starting point for a
firm-level cash flow.

## Non-GAAP

**GAAP** — Generally Accepted Accounting Principles. The required reporting rules.

**Non-GAAP / adjusted** — GAAP figures with one-time items removed, to show what the
business earns in a normal year.

**Non-recurring item (NRI)** — a charge or gain not expected to repeat: restructuring,
impairment, a litigation settlement, a gain on selling a business. Pass 2 identifies
candidates; `analysis/normalizer.py` applies them.

**add_back / remove** — the two directions an NRI can have. `add_back` is a one-time
**expense** to strip out, which raises adjusted earnings. `remove` is a one-time
**gain** to strip out, which lowers them.

## Cash flow to value

**FCFF** — Free Cash Flow to the Firm. Cash available to **all** capital providers,
debt and equity both, before financing. Two formulas are used here and they are not
interchangeable — see
[3-architecture/valuation-math.md](../3-architecture/valuation-math.md).

**NWC** — Net Working Capital. Operating current assets minus operating current
liabilities, excluding cash and debt. Growth consumes cash, so an **increase** in NWC
**reduces** FCFF.

**ΔNWC** — the change in NWC over a period. The sign convention is the single easiest
thing to get backwards here; [4-conventions/units-and-signs.md](../4-conventions/units-and-signs.md)
owns it.

## Discount rates

**Risk-free rate (Rf)** — the return on a government bond, taken as having no default
risk.

**Beta (β)** — how much a stock moves relative to the market. β = 1 moves with it;
β = 1.5 amplifies it by half. Estimated here by OLS regression of the stock's returns
on the S&P 500's.

**ERP** — Equity Risk Premium. The extra return demanded for holding equities over the
risk-free asset. Either supplied by the user or derived as the annualised S&P 500
return minus Rf.

**CAPM** — Capital Asset Pricing Model. `Cost of equity = Rf + β × ERP`.

**Cost of equity (Re)** — the return equity holders require.

**Cost of debt (Rd)** — the interest rate the company pays. Estimated as interest
expense ÷ total debt.

**WACC** — Weighted Average Cost of Capital. The blended required return, weighting
equity at market value and debt at book. The discount rate for FCFF.

**OLS** — Ordinary Least Squares. The regression that fits the line whose slope is β.

**R²** — how much of the stock's movement the market explains. Low R² means β is a weak
estimate, which is a fact about the measurement, not a defect.

## The valuation

**DCF** — Discounted Cash Flow. Value today = the sum of future cash flows, each
divided by `(1 + WACC)^t`.

**Terminal value (TV)** — the value of every cash flow beyond the projection window,
collapsed into one figure at the end of it.

**Gordon Growth Model** — the formula used for TV: `FCFF_n × (1 + g) ÷ (WACC − g)`. It
requires `WACC > g`; `analysis/dcf.py:24` raises when that fails.

**Terminal growth rate (g)** — the rate cash flows grow forever after. Must be below
long-run economic growth, or the company eventually exceeds the economy.

**Enterprise value (EV)** — the value of the whole business, debt and equity together.

**Net debt** — total debt minus liquid assets. Here liquid assets include short-term
investments as well as cash, which is standard equity-bridge practice.

**Equity bridge** — the step from EV to equity value: `EV − net debt`.

**Implied share price** — equity value ÷ diluted shares. The output of the whole
platform.

**Diluted shares** — shares outstanding counting options and convertibles as if
exercised. Always the diluted count, never basic — it is the conservative one.
