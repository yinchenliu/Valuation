"""Quick diagnostic: show section detection results using current extractor."""
import sys, re
sys.path.insert(0, '.')
import pdfplumber
from pathlib import Path
from ingestion.claude_extractor import _find_10k_section_pages

_LINE_ITEM = re.compile(r'(?:^|\n)\s*item\s+\d+', re.IGNORECASE)
pdf = Path(r'C:\Users\yinchenliu\Downloads\google\Alphabet Inc._10-K_2024-12-31_English.pdf')

with pdfplumber.open(str(pdf)) as f:
    pages = f.pages
    n = len(pages)
    print(f'Total pages: {n}')

    # Show line-anchored item ref counts per page
    for i, page in enumerate(pages):
        snippet = (page.extract_text() or '')[:700]
        line_refs = _LINE_ITEM.findall(snippet)
        if line_refs:
            print(f'  Page {i+1:3d}: {len(line_refs)} line-start refs  {line_refs}')

    print()
    mda_start, mda_end, fs_start, fs_end = _find_10k_section_pages(pages)
    print(f'mda_start={mda_start}  mda_end={mda_end}')
    print(f'fs_start ={fs_start}   fs_end ={fs_end}')
    selected: set[int] = set()
    if mda_start is not None:
        selected.update(range(mda_start, min(mda_end or mda_start+40, n)))
    if fs_start is not None:
        selected.update(range(fs_start, min(fs_end or fs_start+90, n)))
    print(f'Selected pages: {sorted(selected)[:5]}...  total={len(selected)}')
