"""Compare gemini-3.1-pro vs gemini-3.1-flash-lite extraction results for ABBV."""
import sys
import pickle
from pathlib import Path

sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")

PRO_CACHE = Path(__file__).parent / ".cache_abbv_extraction_pro.pkl"
LITE_CACHE = Path(__file__).parent / ".cache_abbv_extraction.pkl"

with open(PRO_CACHE, "rb") as f:
    pro_fin, pro_nri = pickle.load(f)
with open(LITE_CACHE, "rb") as f:
    lite_fin, lite_nri = pickle.load(f)

years = sorted(set(pro_fin.years) | set(lite_fin.years))

# =====================================================================
# INCOME STATEMENT COMPARISON
# =====================================================================
print("=" * 100)
print("INCOME STATEMENT COMPARISON: gemini-3.1-pro vs gemini-3.1-flash-lite")
print("=" * 100)

is_fields = [
    ("revenue", "Revenue"),
    ("cost_of_revenue", "Cost of Revenue"),
    ("sga", "SG&A"),
    ("rd_expense", "R&D"),
    ("depreciation_amortization", "D&A"),
    ("other_operating_expense", "Other Op. Exp."),
    ("interest_expense", "Interest Exp."),
    ("interest_income", "Interest Inc."),
    ("other_non_operating", "Other Non-Op."),
    ("tax_expense", "Tax Expense"),
    ("diluted_shares_outstanding", "Diluted Shares"),
]

for year in years:
    pro_is = pro_fin.get_income_statement(year)
    lite_is = lite_fin.get_income_statement(year)
    if pro_is is None and lite_is is None:
        continue
    print(f"\n  {year}")
    print(f"  {'Field':<20} {'Pro':>12} {'Lite':>12} {'Diff':>12} {'%Diff':>8}  Notes")
    print(f"  {'-'*76}")
    for attr, label in is_fields:
        pro_val = getattr(pro_is, attr, None) if pro_is else None
        lite_val = getattr(lite_is, attr, None) if lite_is else None
        if pro_val is None and lite_val is None:
            continue
        pro_v = pro_val or 0
        lite_v = lite_val or 0
        diff = lite_v - pro_v
        pct = (diff / abs(pro_v) * 100) if pro_v != 0 else 0
        flag = "" if abs(pct) < 1 else ("MINOR" if abs(pct) < 5 else "MAJOR DIFF")
        print(f"  {label:<20} {pro_v:>12,.0f} {lite_v:>12,.0f} {diff:>+12,.0f} {pct:>+7.1f}%  {flag}")

# =====================================================================
# CASH FLOW COMPARISON
# =====================================================================
print("\n" + "=" * 100)
print("CASH FLOW COMPARISON: gemini-3.1-pro vs gemini-3.1-flash-lite")
print("=" * 100)

cf_fields = [
    ("net_income", "Net Income"),
    ("depreciation_amortization", "D&A"),
    ("stock_based_compensation", "SBC"),
    ("change_in_working_capital", "Chg Working Cap"),
    ("other_operating_activities", "Other Op. Act."),
    ("capital_expenditures", "CapEx"),
]

for year in years:
    pro_cf = pro_fin.get_cash_flow(year)
    lite_cf = lite_fin.get_cash_flow(year)
    if pro_cf is None and lite_cf is None:
        continue
    print(f"\n  {year}")
    print(f"  {'Field':<20} {'Pro':>12} {'Lite':>12} {'Diff':>12} {'%Diff':>8}  Notes")
    print(f"  {'-'*76}")
    for attr, label in cf_fields:
        pro_val = getattr(pro_cf, attr, None) if pro_cf else None
        lite_val = getattr(lite_cf, attr, None) if lite_cf else None
        if pro_val is None and lite_val is None:
            continue
        pro_v = pro_val or 0
        lite_v = lite_val or 0
        diff = lite_v - pro_v
        pct = (diff / abs(pro_v) * 100) if pro_v != 0 else 0
        flag = "" if abs(pct) < 1 else ("MINOR" if abs(pct) < 5 else "MAJOR DIFF")
        print(f"  {label:<20} {pro_v:>12,.0f} {lite_v:>12,.0f} {diff:>+12,.0f} {pct:>+7.1f}%  {flag}")
    # CFO comparison
    pro_cfo = pro_cf.cash_from_operations if pro_cf else 0
    lite_cfo = lite_cf.cash_from_operations if lite_cf else 0
    diff = lite_cfo - pro_cfo
    pct = (diff / abs(pro_cfo) * 100) if pro_cfo != 0 else 0
    flag = "" if abs(pct) < 1 else ("MINOR" if abs(pct) < 5 else "MAJOR DIFF")
    print(f"  {'CFO (computed)':<20} {pro_cfo:>12,.0f} {lite_cfo:>12,.0f} {diff:>+12,.0f} {pct:>+7.1f}%  {flag}")

# =====================================================================
# BALANCE SHEET COMPARISON
# =====================================================================
print("\n" + "=" * 100)
print("BALANCE SHEET COMPARISON: gemini-3.1-pro vs gemini-3.1-flash-lite")
print("=" * 100)

bs_fields = [
    ("cash_and_equivalents", "Cash"),
    ("short_term_investments", "ST Investments"),
    ("accounts_receivable", "A/R"),
    ("inventory", "Inventory"),
    ("other_current_assets", "Other Curr Assets"),
    ("ppe_net", "PP&E Net"),
    ("goodwill", "Goodwill"),
    ("intangible_assets", "Intangibles"),
    ("other_non_current_assets", "Other NC Assets"),
    ("accounts_payable", "A/P"),
    ("short_term_debt", "ST Debt"),
    ("long_term_debt", "LT Debt"),
    ("other_non_current_liabilities", "Other NC Liab"),
    ("total_equity", "Total Equity"),
]

for year in years:
    pro_bs = pro_fin.get_balance_sheet(year)
    lite_bs = lite_fin.get_balance_sheet(year)
    if pro_bs is None and lite_bs is None:
        continue
    print(f"\n  {year}")
    print(f"  {'Field':<20} {'Pro':>12} {'Lite':>12} {'Diff':>12} {'%Diff':>8}  Notes")
    print(f"  {'-'*76}")
    for attr, label in bs_fields:
        pro_val = getattr(pro_bs, attr, None) if pro_bs else None
        lite_val = getattr(lite_bs, attr, None) if lite_bs else None
        if pro_val is None and lite_val is None:
            continue
        pro_v = pro_val or 0
        lite_v = lite_val or 0
        diff = lite_v - pro_v
        pct = (diff / abs(pro_v) * 100) if pro_v != 0 else 0
        flag = "" if abs(pct) < 1 else ("MINOR" if abs(pct) < 5 else "MAJOR DIFF")
        print(f"  {label:<20} {pro_v:>12,.0f} {lite_v:>12,.0f} {diff:>+12,.0f} {pct:>+7.1f}%  {flag}")

# =====================================================================
# NON-RECURRING ITEMS COMPARISON
# =====================================================================
print("\n" + "=" * 100)
print("NON-RECURRING ITEMS COMPARISON")
print("=" * 100)

print(f"\n  Pro model:  {len(pro_nri)} items")
print(f"  Lite model: {len(lite_nri)} items")

for year in years:
    pro_items = [x for x in pro_nri if x.year == year]
    lite_items = [x for x in lite_nri if x.year == year]
    if not pro_items and not lite_items:
        continue
    print(f"\n  --- {year} ---")
    print(f"  Pro ({len(pro_items)} items):")
    pro_total = 0
    for item in pro_items:
        sign = "+" if item.direction == "add_back" else "-"
        val = item.amount if item.direction == "add_back" else -item.amount
        pro_total += val
        print(f"    {sign}{item.amount:>10,.0f}M  {item.category:<20} {item.line_item:<25} {item.description[:60]}")
    print(f"    {'Net impact:':<12} {pro_total:>+10,.0f}M")

    print(f"  Lite ({len(lite_items)} items):")
    lite_total = 0
    for item in lite_items:
        sign = "+" if item.direction == "add_back" else "-"
        val = item.amount if item.direction == "add_back" else -item.amount
        lite_total += val
        flag = " *** UNIT ERROR (not in $M) ***" if item.amount > 100_000 else ""
        print(f"    {sign}{item.amount:>10,.0f}M  {item.category:<20} {item.line_item:<25} {item.description[:60]}{flag}")
    print(f"    {'Net impact:':<12} {lite_total:>+10,.0f}M")
    diff = lite_total - pro_total
    print(f"    {'Difference:':<12} {diff:>+10,.0f}M")

# =====================================================================
# SUMMARY
# =====================================================================
print("\n" + "=" * 100)
print("SUMMARY OF KEY DIFFERENCES")
print("=" * 100)

# Count issues
issues = []

for year in years:
    pro_is = pro_fin.get_income_statement(year)
    lite_is = lite_fin.get_income_statement(year)
    if pro_is and lite_is:
        for attr, label in is_fields:
            pro_v = getattr(pro_is, attr, 0) or 0
            lite_v = getattr(lite_is, attr, 0) or 0
            if pro_v != 0:
                pct = abs((lite_v - pro_v) / pro_v * 100)
                if pct >= 5:
                    issues.append((year, "I/S", label, pro_v, lite_v, pct))

    pro_cf = pro_fin.get_cash_flow(year)
    lite_cf = lite_fin.get_cash_flow(year)
    if pro_cf and lite_cf:
        for attr, label in cf_fields:
            pro_v = getattr(pro_cf, attr, 0) or 0
            lite_v = getattr(lite_cf, attr, 0) or 0
            if pro_v != 0:
                pct = abs((lite_v - pro_v) / pro_v * 100)
                if pct >= 5:
                    issues.append((year, "C/F", label, pro_v, lite_v, pct))

# NRI unit errors
nri_unit_errors = [x for x in lite_nri if x.amount > 100_000]

print(f"\n  Financial statement fields with >5% difference: {len(issues)}")
for year, stmt, label, pro_v, lite_v, pct in issues:
    print(f"    {year} {stmt:>3} {label:<20}  Pro={pro_v:>12,.0f}  Lite={lite_v:>12,.0f}  ({pct:>+.1f}%)")

print(f"\n  NRI items with unit errors (not in $M): {len(nri_unit_errors)}")
for item in nri_unit_errors:
    print(f"    [{item.year}] {item.amount:>16,.0f}  {item.description[:60]}")

print(f"\n  NRI count: Pro={len(pro_nri)}, Lite={len(lite_nri)}  (difference: {len(pro_nri) - len(lite_nri)} items)")

# Items only in pro (by description matching)
pro_descs = {(x.year, x.description[:40]) for x in pro_nri}
lite_descs = {(x.year, x.description[:40]) for x in lite_nri}
only_pro = pro_descs - lite_descs
only_lite = lite_descs - pro_descs
if only_pro:
    print(f"\n  NRI items found ONLY by Pro ({len(only_pro)}):")
    for year, desc in sorted(only_pro):
        matching = [x for x in pro_nri if x.year == year and x.description[:40] == desc]
        for m in matching:
            print(f"    [{year}] {m.amount:>8,.0f}M  {m.description[:70]}")
if only_lite:
    print(f"\n  NRI items found ONLY by Lite ({len(only_lite)}):")
    for year, desc in sorted(only_lite):
        matching = [x for x in lite_nri if x.year == year and x.description[:40] == desc]
        for m in matching:
            print(f"    [{year}] {m.amount:>8,.0f}M  {m.description[:70]}")
