"""Dump full contents of LLY extraction cache."""
import sys, pickle, pprint
sys.path.insert(0, r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform")

with open(r"C:\Users\yinchenliu\Desktop\Python\python\Scripts\valuation_platform\tests\.cache_lly_extraction.pkl", "rb") as f:
    financials, adjustments = pickle.load(f)

print("=" * 70)
print("INCOME STATEMENTS")
print("=" * 70)
for s in financials.income_statements:
    print(f"\n--- {s.year} ---")
    for k, v in vars(s).items():
        print(f"  {k:<30} {v}")

print("\n" + "=" * 70)
print("CASH FLOW STATEMENTS")
print("=" * 70)
for s in financials.cash_flow_statements:
    print(f"\n--- {s.year} ---")
    for k, v in vars(s).items():
        print(f"  {k:<30} {v}")

print("\n" + "=" * 70)
print("BALANCE SHEETS")
print("=" * 70)
for s in financials.balance_sheets:
    print(f"\n--- B/S {s.year} ---")
    for k, v in vars(s).items():
        print(f"  {k:<30} {v}")

print("\n" + "=" * 70)
print("NON-RECURRING ITEMS")
print("=" * 70)
for a in adjustments:
    sign = "+" if a.direction == "add_back" else "-"
    print(f"\n  [{a.year}] {sign}{a.amount:,.1f}M on {a.line_item}")
    print(f"    Description: {a.description}")
    print(f"    Category:    {a.category}")
    print(f"    Confidence:  {a.confidence}")
    print(f"    Source:      {a.source}")
