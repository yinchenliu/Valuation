# The data contract

`models/` defines every type that flows through the pipeline. **`FinancialStatements` is
the central one** — extraction produces it, normalisation returns a new one, and every
`analysis/` function reads it.

Units and signs are owned by
[4-conventions/units-and-signs.md](../4-conventions/units-and-signs.md). Terms by
[1-overview/glossary.md](../1-overview/glossary.md).

---

## The types

| Type | File | Role |
|---|---|---|
| `IncomeStatement` | `financial_statements.py` | one period's I/S |
| `BalanceSheet` | `financial_statements.py` | one period's B/S |
| `CashFlowStatement` | `financial_statements.py` | one period's C/F |
| `FinancialStatements` | `financial_statements.py` | **the container**: ticker + lists of the three, by year |
| `NonRecurringItem` | `financial_statements.py` | one candidate adjustment, from Pass 2 |
| `CAPMResult` | `valuation.py` | beta, Rf, ERP, and the diagnostics |
| `WACCResult` | `valuation.py` | the two costs, the two weights, the tax rate |
| `HistoricalFCFF` | `valuation.py` | one year, CFO-based, with the full breakdown |
| `ProjectedFCFF` | `valuation.py` | one year, EBIT-based |
| `DCFResult` | `valuation.py` | the whole valuation, ending in `implied_share_price` |
| `ProjectionAssumptions` | `valuation.py` | the user's overrides. **`None` means "derive it"** |
| `Company` | `company.py` | **dead.** Nothing imports it |

## Stored fields versus derived properties

This is the distinction to hold, because it decides what a test may set and what it must
compute.

**Stored** fields are `@dataclass` fields. They are what extraction fills.

**Derived** values are `@property`. They are never stored, never extracted, and never
settable. They recompute from stored fields every time they are read.

```python
@property
def ebit(self) -> float:
    return self.revenue - self.total_operating_expenses
```

### The derived set, in full

| Type | Derived |
|---|---|
| `IncomeStatement` | `gross_profit`, `gross_margin`, `total_operating_expenses`, `ebit`, `operating_margin`, `ebt`, `net_income`, `effective_tax_rate`, `eps` |
| `BalanceSheet` | `total_current_assets`, `total_assets`, `total_current_liabilities`, `total_liabilities`, `total_debt`, `net_debt`, `net_working_capital` |
| `CashFlowStatement` | `cash_from_operations`, `cash_from_investing`, `cash_from_financing`, `net_change_in_cash` |
| `FinancialStatements` | `years`, `latest_year` |
| `CAPMResult` | `cost_of_equity` |
| `WACCResult` | `wacc` |
| `DCFResult` | `enterprise_value`, `equity_value`, `implied_share_price`, `upside_downside` |

**Three consequences:**

1. **You cannot set `ebit`.** To test a specific EBIT, set `revenue` and the expense
   fields so it falls out. This is deliberate: it makes an inconsistent statement
   unrepresentable.
2. **The extractor must not send a derived field.** `_parse_financials_response` reads
   `operating_income` and `gross_profit` from the model **only to reconcile them**
   against the computed values — never to store them. See
   [extraction.md](extraction.md).
3. **A derived property with a zero-guard is a rule 3 site.** `gross_margin`,
   `operating_margin`, `effective_tax_rate`, `eps`, `fcff_margin`,
   `implied_share_price` and `upside_downside` all return `0.0` on a zero denominator.
   Backlog item 1.

## `FinancialStatements` — the access pattern

```python
financials.years                      # sorted ascending, from income statements only
financials.latest_year                # max(years), or 0 when empty
financials.get_income_statement(year) # -> IncomeStatement | None
financials.get_balance_sheet(year)    # -> BalanceSheet | None
financials.get_cash_flow(year)        # -> CashFlowStatement | None
```

**All three getters return `None` when the year is absent, and that is routine, not
exceptional.** `extract_multi_year()` takes the balance sheet **only from the most
recent filing**, so `get_balance_sheet(y)` is `None` for every earlier year by design.

This is the source of 16 `union-attr` type errors and of backlog item 2. **Every call
site must handle `None` explicitly** — and per [rule 3](../2-rules/rules.md), handling it
means stopping and naming the year, not substituting a zero.

`years` is derived from **income statements only**. A year with a cash flow statement
and no income statement is invisible to `years`.

## `NonRecurringItem`

```python
year: int
description: str
amount: float          # absolute value, millions
line_item: str         # the IncomeStatement field it sits in
direction: str         # "add_back" | "remove"
category: str          # restructuring | impairment | litigation | ...
confidence: str        # "high" | "medium" | "low"
source: str            # e.g. "Note 12 — Restructuring charges"
```

**`amount` is always positive.** `direction` carries the sign, and `adjusted_impact`
applies it.

**`line_item` names an `IncomeStatement` field**, which is what lets `normalizer.py`
apply the adjustment to the line the item actually sits in.

**`source` is the audit trail.** An item with an empty `source` cannot be traced back to
a page, which is [rule 4](../2-rules/rules.md). It is not currently enforced.

## `BalanceSheet` noncontrolling interest — two memo lines, and `None` stops

`noncontrolling_interest_nonredeemable: float | None = None` and
`noncontrolling_interest_redeemable: float | None = None`, added by `P10a` on the user's
approval of 2026-10-02 (backlog item 48). Each is one line as the filing prints it: the
noncontrolling interest inside equity, and the redeemable noncontrolling interest shown
outside equity (mezzanine). Pass 1 reads each from the key of the same name.

- **Memos.** Each is already inside `total_equity` or another line, so neither is part of
  any derived total — not `total_assets`, `total_liabilities`, `total_equity` nor
  `balance_check_difference`.
- **Not summed on the dataclass.** The total is computed in one place,
  `analysis/dcf.py:total_noncontrolling_interest`, because the filing prints the parts and
  not the sum ([rule 1](../2-rules/rules.md)).
- **`None` is not a zero default.** It means "not extracted": route A's parser leaves a part
  `None` when its key is absent (no `.get(..., 0)`), and route B's loader refuses a session
  file without either key. `total_noncontrolling_interest` stops on `None` or NaN, naming the
  key and the year. A filing that prints no such line is extracted as an explicit `0`.
- **Where it goes.** `run_dcf` puts the total in `DCFResult.noncontrolling_interest`, a
  keyword-only field with **no default**, beside `noncontrolling_interest_source` (which
  names both parts and their figures), and `DCFResult.equity_value` is
  `enterprise_value − net_debt − noncontrolling_interest`. The CLI's balance sheet block and
  `templates/_statements.html` print the two parts as memo lines, `not extracted` when
  `None`.

## `ProjectionAssumptions` — `None` is meaningful

Every override field is `T | None`, and **`None` means "derive from history"**. That is
why testing truthiness instead of `is not None` is a defect: a deliberate `0` is not
`None`, and the two must not be conflated. Backlog item 6.

## Immutability by convention

`normalize_financials` does not mutate. It returns a new object:

```python
return dataclasses.replace(financials, income_statements=adjusted_is)
```

**Keep this.** The adjusted and unadjusted statements both need to be displayable side
by side, which is impossible if normalisation edits in place. No `analysis/` function
may mutate its argument.
