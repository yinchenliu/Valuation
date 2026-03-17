"""Trace B/S section detection to debug bucketing."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from ingestion.capital_iq_parser import (
    _parse_sheet, _is_section_header, _has_data, _safe_float,
    _match_label, BS_KNOWN, BS_SECTIONS, _should_skip, BS_SKIP_PATTERNS
)

fp = r'C:\Users\yinchenliu\Downloads\AlphabetInc.NASDAQGSGOOGL_Report_03-02-2026.xlsx'
df, years, ycols = _parse_sheet(fp, 'Balance Sheet (As Reported)')
col = ycols[0]  # 2024

print(f"Years: {years}")
print(f"Using column: {col}")
print(f"Total rows: {len(df)}")
print(f"BS_SECTIONS keys: {list(BS_SECTIONS.keys())}")
print()

bucket = None
for idx, row in df.iterrows():
    label = str(row['label']).strip()
    if not label or label == 'nan':
        continue
    raw_val = row.get(col, None)
    sec = _is_section_header(label, raw_val, BS_SECTIONS)
    has = _has_data(raw_val)
    skip = _should_skip(label, BS_SKIP_PATTERNS)
    field = _match_label(label, BS_KNOWN)
    
    if sec is not False:
        bucket = sec
        print(f"SECTION: [{label}] -> bucket={bucket}")
    elif skip:
        print(f"SKIP:    [{label}] val={_safe_float(raw_val)}")
    elif has:
        val = _safe_float(raw_val)
        if field:
            print(f"NAMED:   [{label}] -> {field} = {val}")
        else:
            print(f"BUCKET:  [{label}] -> {bucket} += {val}")
    else:
        print(f"NODATA:  [{label}]")
