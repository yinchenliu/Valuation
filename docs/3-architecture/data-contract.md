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
| `ProviderResolution` | `claude_extractor.py` | who read the filing, over what, on whose credential |
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
| `BalanceSheet` | `total_current_assets`, `total_assets`, `total_current_liabilities`, `total_liabilities`, `total_liabilities_and_equity`, `total_debt`, `net_debt`, `balance_check_difference`, `printed_total_assets_difference`, `printed_total_liabilities_and_equity_difference`, `net_working_capital` |
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
   the printed `gross_profit`, `operating_income` and `net_income` rows **only to check
   them** against the computed values — never to store them as figures (`net_income`
   also starts the reconstructed cash flow, as before). See
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
amount: float          # absolute value; printed in filing until convert_filing_to_millions, then millions
page: int              # 1-based PDF page where amount is printed
printed_units: str     # exact unit words printed in filing (inline or statement)
units_page: int        # 1-based PDF page where printed_units is printed
line_item: str         # the IncomeStatement field it sits in
direction: str         # "add_back" | "remove"
category: str          # restructuring | impairment | litigation | ...
confidence: str        # "high" | "medium" | "low"
source: str            # e.g. "Note 12 — Restructuring charges"
```

**`page`, `printed_units`, `units_page` are required fields with no defaults** (`P14b`,
backlog item 77, user decision "fix 77a" of 2026-10-04). They record the page where `amount`
is printed, the exact unit words printed in the filing, and the page where those words
appear. `pass2_amount_scale(item.printed_units, item.amount)` reads the scale and converts
`amount` to millions in `convert_filing_to_millions`.

**`amount` is always positive.** It holds the printed amount until `convert_filing_to_millions`,
after which it is in millions. `direction` carries the sign, and `adjusted_impact` applies it.

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
- **`None` is not a zero default.** It means "not extracted". Since `P11a` neither route's
  parser produces `None` here: each key is a list of printed lines, an absent key stops
  the parse (`pass1_problems`), and `[]` (the filing prints no such line) reads as 0. A
  `BalanceSheet` built any other way may still hold `None`. `total_noncontrolling_interest` stops on `None` or NaN, naming the
  key and the year. A filing that prints no such line is extracted as an empty list,
  `[]`, which reads as `0`.
- **Where it goes.** `run_dcf` puts the total in `DCFResult.noncontrolling_interest`, a
  keyword-only field with **no default**, beside `noncontrolling_interest_source` (which
  names both parts and their figures), and `DCFResult.equity_value` is
  `enterprise_value − net_debt − noncontrolling_interest`. The CLI's balance sheet block and
  `templates/_statements.html` print the two parts as memo lines, `not extracted` when
  `None`.

## `BalanceSheet` printed totals — two memo fields, used only to check the reading

`printed_total_assets: float | None = None` and
`printed_total_liabilities_and_equity: float | None = None`, added by `P11a` on the
user's decision of 2026-10-02 (backlog item 56, option A). Each is the total row the
filing prints, read from the Pass 1 keys `total_assets` and
`total_liabilities_and_equity`, and summed from its printed lines like every other field.

- **Memos.** In no total and no figure. They exist so the balance check, and both
  outputs, can put the printed total beside the sum of the mapped lines. They are not
  `total_assets` (a derived property: the sum of the nine mapped asset fields) and not
  `total_liabilities_and_equity` (derived: `total_liabilities + total_equity`; the
  noncontrolling interest memos are in neither).
- **The check.** `printed_total_assets_difference` and
  `printed_total_liabilities_and_equity_difference` are printed minus mapped, in
  millions, `None` when the printed total is `None`. `printed_total_status(difference_in_printed_units)`
  returns `FAIL` when the difference, rounded to `PRINTED_UNIT_DECIMALS` (6) places,
  exceeds `BALANCE_CHECK_TOLERANCE` (1.0, **in printed units**: rounding, nothing more),
  `OK` otherwise, and `FAIL: not extracted` for `None`. The parser's check calls it on
  the figures as printed. `BalanceSheet.printed_total_check(difference)`, an instance
  method since `P14a`, divides a difference in millions by `printed_unit_in_millions`
  and calls it; `cli.py` and `templates/_statements.html` use that. One threshold, 1
  printed unit, in either unit. A failure is shown and the figures are kept.
- **`None` is not a zero default.** It means "not extracted", and the check then says
  `FAIL: not extracted`, never `OK`. The Pass 1 keys are required, so an absent key
  stops the parse. **`[]` for a total is `None`, not `0`** (`P11a` round 2, review F1):
  `claude_extractor.py:check_row_from_printed_lines` maps it, because every balance
  sheet prints both totals and a `0` the filing never printed must not be shown as a
  printed figure. The check fails, the outputs print `not extracted` and no gap, and the
  run continues.
- **The threshold on the page.** `BalanceSheet.printed_total_tolerance()` returns
  `BALANCE_CHECK_TOLERANCE × printed_unit_in_millions`, in millions (0.001 for a filing
  in thousands), so `templates/_statements.html` and `cli.py` print the threshold the
  check applies rather than a copy of it, beside `printed_unit()` (what 1 printed unit
  is in $M).

## `BalanceSheet.printed_unit_in_millions` — what one printed unit is, set by the conversion

`printed_unit_in_millions: float | None`, keyword-only and **required, with no
default**, added by `P14a` (backlog item 44). It is what one unit the filing prints its
money figures in is worth in millions: 0.001 for a filing in thousands, 1.0 for
millions, 1000.0 for billions. `claude_extractor.py:convert_filing_to_millions` sets it
from the money scale Python read in the filing's printed `units` statement, when it
converts the balance sheet's figures to millions.

- **No default.** A default would assume millions, and a filing in thousands would then
  be checked at 1,000 printed units (rule 3). Every construction states it.
- **`None` is stated, never defaulted.** The parser (`_parse_financials_response`)
  builds the balance sheet with `printed_unit_in_millions=None`, because its figures
  are still as printed. `printed_unit()`, `printed_total_check`,
  `printed_total_tolerance` and `printed_unit_decimals` **stop** on `None`, naming the
  field: a balance sheet that was never converted has no threshold in millions.
- **The conversion stops** on a balance sheet whose field is already set: the filing
  was converted before, and a second conversion would move every figure again.

Every money field of `IncomeStatement`, `BalanceSheet` and `CashFlowStatement`, and
`NonRecurringItem.amount`, is in millions after the conversion; `diluted_shares_outstanding`
is in millions of shares. `parse_pass1` alone returns the figures as printed.

## `BalanceSheet` debt fields — finance leases included, operating leases excluded

`short_term_debt` and `long_term_debt` are stored fields that together form `total_debt`:

- **`short_term_debt`** holds the current portion of long-term debt, short-term borrowings,
  notes payable, commercial paper rows, and the **finance lease obligations due within one year**.
  Operating lease obligations are excluded and mapped to `other_current_liabilities`.
- **`long_term_debt`** holds long-term debt beyond one year and **long-term finance lease obligations**.
  Operating lease obligations are excluded and mapped to `other_non_current_liabilities`.

Approved on the user's decision of 2026-10-04 ("83a", backlog item 83): finance lease
obligations are debt; operating lease obligations are not.

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

## `ProviderResolution`, `Transport` and `CredentialKind`

`ProviderResolution` records who read the filing, over what transport, and on what credential.

- **`Provider`**: `"claude"` or `"gemini"`.
- **`Transport`**: `"gemini-direct"` (route A calls Google Gemini API) or `"claude-code-session"` (route B reads from a Claude Code session file).
- **`CredentialKind`**: `"gemini-api-key"` (route A) or `"claude-code-session"` (route B, no API key).

