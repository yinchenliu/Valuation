---
id: P14e-nri-dedupe
phase: 14 — the Pass 1 and Pass 2 roles
agent: programmer
depends_on: []
---

# Two different items with the same amount: one is dropped in silence (item 112)

## Objective

**The fact.** `ingestion/claude_extractor.py`, in `merge_filing_extractions`, deduplicates
non-recurring items on the key `(item.year, item.amount, item.direction)`:

```python
# Dedupe NRIs by (year, amount, direction)
for item in nri:
    key = (item.year, item.amount, item.direction)
    if key not in nri_keys:
        all_nri.append(item)
        nri_keys.add(key)
```

There is no `else`. An item whose key is already present is discarded and **nothing
anywhere reports it**.

**What follows.** Two genuinely different items that share a year, an amount and a
direction are one item after the merge. The amount is the only thing separating them, and
a 10-K rounds its MD&A figures to one decimal place in billions, so collisions are not
rare.

**Measured on 2026-10-06, by the overall lead, on the real route B Walmart file.**
Walmart's fiscal 2024 10-K prints two incremental divestiture losses for fiscal 2022, each
`$0.2 billion`, in Note 12 (Disposals, Acquisitions and Related Items):

| Item | PDF page | Year | Amount | Direction |
|---|---|---|---|---|
| Incremental pre-tax loss on the divestiture of Asda | 66 | 2022 | 0.2 | `add_back` |
| Incremental pre-tax loss on the divestiture of Seiyu | 67 | 2022 | 0.2 | `add_back` |

```
TOTAL WRITTEN 14   DISTINCT (year, amount, direction) KEYS 13
COLLISION (2022, 0.2, 'add_back')
    (0, 66, 'Incremental pre-tax loss on the divestiture of Asda (U.')
    (0, 67, 'Incremental pre-tax loss on the divestiture of Seiyu (J')
```

`len(load_session_extraction('extractions/WMT.json').non_recurring)` is **13**. So **200
$M of add-back is lost from fiscal 2022.** Nothing on either page and nothing in `check`'s
output says an item was dropped.

**Corrected 2026-10-06, after round 1. The first version of this paragraph named the wrong
mechanism, and both the programmer and the code reviewer proved it wrong by execution.**
It said the fiscal 2022 operating margin is understated. It is not. All four Walmart
fiscal 2022 items carry `line_item: "other_non_operating"`, which the normalizer applies
**below** EBIT, so `operating_margin` is `0.045293441861602016` and `ebit` is `25942.0` in
both trees. **What moves is the fiscal 2022 effective tax rate**: `ebt` goes from
`23706.0` to `23906.0`, exactly 200 apart, against an unchanged `tax_expense` of `4756.0`,
so `effective_tax_rate` goes `0.20062431451953092 → 0.19894587132937339`. That changes the
derived `tax_rate` assumption, 23.147309% to 23.113740%, hence NOPAT in all five projected
years and the terminal value. **The defect and its cost are real. The path this paragraph
described was not.**

**Why the dedupe exists, and it is right about that case.** Filings overlap. Walmart's
fiscal 2024 10-K presents fiscal 2022, 2023 and 2024, and the fiscal 2025 10-K presents
fiscal 2025. Where two filings present the same year, both can flag the same item, and the
merge must not count it twice. **That case is real and the fix must keep it.**

**What follows for the fix.** Two items in **one** filing's answer are two items: the
model wrote two rows, each with its own printed label and its own page. Two items in
**different** filings' answers may be one item re-reported. The current key cannot tell
the two situations apart because it drops the one field that distinguishes them, the
printed description, and the one field that locates them, the page.

**What follows for rule 3 and rule 6.** Rule 3: an input that the code refuses must stop
and name itself. Rule 6: a figure shown must be shown for what it is. An item silently
removed from a valuation is neither. **Whatever key you choose, no drop may be silent.**

## What is already true — verify, do not redo

Measured by the overall lead on 2026-10-06, on the **Windows** machine
(`.venv/Scripts/python.exe`, Python 3.14.4), with `ANTHROPIC_API_KEY= GEMINI_API_KEY=`:

| Fact | Command | Result |
|---|---|---|
| the collision exists in the real file | the counting script above, over `extractions/WMT.json` | 14 written, 13 distinct keys |
| the merged list is short by one | `len(load_session_extraction('extractions/WMT.json').non_recurring)` | **13** |
| `check` says nothing about it | `-m ingestion.session_extraction check extractions/WMT.json` | exit 0, no mention of a dropped item |
| the session file itself is sound | the same command | 129 of 129 printed lines found, 284,668 = 284,668 |

**`extractions/WMT.json` is your test input and it is not in git** (`.gitignore:33`).
**Do not edit it and do not delete it.** Copy it to a scratch path if you need a variant.

## What to do

1. **Never dedupe two items that came from the same filing's answer.** One filing's Pass 2
   answer holds one list, and two rows in it are two items. The merge runs over filings,
   so the filing each item came from is known at the point the key is built.
2. **Across filings, make the key able to tell one item from another.** The year, the
   amount and the direction are not enough. Add what the model actually wrote: the printed
   description and the page, or the `source`. **State in a comment which fields the key
   holds and why each one is there.**
3. **Report every drop.** When the merge discards an item, it must say so, naming the
   year, the amount, the direction, the description and the filing of **both** the item
   kept and the item dropped. Print it where the other merge and check messages already
   print, so both routes show it. **Do not stop the run.** Two filings re-reporting one
   item is normal and must not be an error.
4. **Decide nothing about what is "the same item".** If you find a case that the printed
   text cannot settle, that is a finding: write it and stop. Do not add a similarity rule,
   a fuzzy match, or a tolerance.
5. **Record what you find, do not widen your scope.** A defect outside this list goes in
   your log entry under "Found". The overall lead puts it in the backlog.

## Files in scope

- `ingestion/claude_extractor.py`

**Nothing else.** `P3c-one-number` landed at `2e2eb2f` and the tree is clean, so no file
is in flight. The scope is still one file: the merge is the only place this defect lives,
and a message printed from `ingestion/` reaches both routes. If you believe the message
also belongs on a web page, that is a finding: write it and stop.

## Out of scope

- **`tests/`.** The write guard denies it. This unit's tests are a separate assignment
  after the code review.
- **`ingestion/session_extraction.py`.** The session loader calls the merge; it does not
  own it.
- **Backlog items 113 and 114**, both found by the same extraction and both recorded. Item
  113 is the Pass 2 prompt's console encoding, item 114 is
  `_unit_statement_pages_allowed`. Neither is yours.
- **Backlog items 84, 73, 79, 80** in the same file. Each is recorded.
- **What counts as a non-recurring item.** The user's decision "1a" of 2026-10-06 settled
  the two open Walmart judgements, and the Pass 2 prompt is unchanged by this unit.

## Done-criteria

Run every command with `ANTHROPIC_API_KEY= GEMINI_API_KEY=` and
`.venv/Scripts/python.exe`. Never a bare `python`. Use `PYTHONIOENCODING=utf-8` for any
command that prints a prompt (backlog item 113).

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | The two Walmart items both survive | `len(...non_recurring)` is **14**, not 13, and both the Asda and the Seiyu descriptions are in the list | `load_session_extraction('extractions/WMT.json')`, print every item's year, amount, direction and description |
| 2 | The old behaviour is reproduced first | the same command at `HEAD` gives **13**, and the Seiyu item is absent | `git archive HEAD` into a scratch directory. **`git stash` is forbidden** |
| 3 | The same item re-reported by two filings is still merged once | one item, not two | build two filings' answers by hand that flag one item for one year, and merge them |
| 4 | A drop is reported | the message names the year, amount, direction, description and filing of both items | criterion 3's input, output quoted |
| 5 | A drop does not stop the run | the merge returns, and the valuation continues | criterion 3 |
| 6 | Two items in one filing are never merged | both survive, whatever their amounts | one filing's answer holding two items with the same year, amount and direction |
| 7 | The key's fields are stated | the comment names each field and why | read it back |
| 8 | Route A is unchanged in what it asks the model | `git diff` touches no prompt and no schema | `git diff` |
| 9 | Types | 5 errors in 2 files, or fewer. Name any you removed | `-m mypy models analysis ingestion api config.py app.py pipeline.py --ignore-missing-imports` |
| 10 | Lint | 4 errors, every one `BLE001` | `-m ruff check .` |
| 11 | Census | 64, or fewer. Name any site you removed | the grep at `docs/2-rules/rules.md:102` |
| 12 | Route | 200 | `TestClient(app.app, raise_server_exceptions=False).get('/')` |
| 13 | The failing test set | name every test that changed state and why | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly`, before and after, compared **by name** |
| 14 | The share price moves, and you say by how much | the fiscal 2022 figures before and after, and the implied price before and after | `cli.py --session-file extractions/WMT.json`, both trees. **This needs a market call.** If it cannot run, say so and give the fiscal 2022 adjusted operating margin instead |

**Every criterion is a measurement, never an opinion.** Criteria 2 and 14 exist because a
change that moves a number must show the number before and the number after.

## Citations

- `docs/2-rules/rules.md` — rule 3 (a refused input names itself) and rule 6 (a shown
  figure is shown for what it is).
- `docs/9-reference/refactor-backlog.md`, item 112, with the 2026-10-06 measurements.
- `.agent/journal/2026-10-06T1109-session-extraction-wmt.md` — the extraction that found
  it, and the 14 items with their pages and sources.
- `docs/3-architecture/extraction.md` — the two routes and the one parser they share.
- `.claude/agents/programmer.md` — your role card.

## Known open items

- **Backlog item 113**: `session_extraction prompt --pass 2` exits 2 on a Windows console
  without `PYTHONIOENCODING=utf-8`.
- **Backlog item 75**: the write guard reads text inside a Bash command as a file path and
  refuses a `>` or a heredoc. Write files with the Write tool.
- `extractions/WMT.json` holds three filings and five fiscal years, 2022 to 2026. The
  balance sheet is on `filings[2]`, the newest filing, not on `filings[0]`.
- The suite takes about 120 seconds.

---

## Round 2 amendment (overall lead), 2026-10-06

**Round 1 is `approved`.** The code reviewer re-ran all 14 criteria and they agree. This
amendment adds **one** change, and it answers the reviewer's F1, which is a defect in my
assignment and not in your code.

**The fact.** Step 1 of "What to do" told you never to dedupe two items that came from one
filing's answer. You followed it exactly. The reviewer then measured the consequence: a
filing whose Pass 2 answer lists **the identical row twice** — same year, same amount, same
direction, same description **and the same page** — now produces two items, silently. At
`HEAD` the second was dropped, also silently.

**What follows.** This unit set out to make a silent drop impossible, and in this one case
it replaced a silent drop with a silent double-count. A double-count inflates the add-back
instead of losing it. Both are silent and both are wrong.

**Why the fix carries no judgement, which is why I am asking for it rather than deferring
it.** Your reason for keeping `page` out of the key is correct **across** filings: a full
`source` string carries one PDF's page number, and the reviewer confirmed the same
disclosure moves between filings — `Note 1 … Investments, page 52` in the FY2024 10-K and
`page 51` in the FY2025. **That reason does not apply inside one filing.** Within one PDF,
`page` is what separates Asda on page 66 from Seiyu on page 67. Two rows that agree on the
year, the amount, the direction, the description **and** the page are one printed line
written twice, not two charges.

### What to do

1. **Give the within-filing comparison its own key**: `(year, amount, direction,
   description, page)`. The across-filing key is unchanged at `nri_identity`, for the
   reason you gave and the reviewer confirmed.
2. **Report a within-filing drop exactly as you report a cross-filing one.** Use
   `_print_repeated_item` or the same words. **The whole point of this amendment is that
   neither direction is silent**, so a within-filing repeat that is dropped must say so.
3. **Say in the docstring which key applies where, and why `page` is in one and not the
   other.** A reader meeting two keys must not have to infer the reason.
4. Change nothing else. Round 1's behaviour, its message text and its public
   `nri_identity` all stand.

### Added done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 15 | The identical row twice in one filing is one item, and the drop is reported | 1 item, and the message names both copies with their page | one filing's answer holding two rows identical in year, amount, direction, description and page |
| 16 | Asda and Seiyu still survive | 2 items | the two real rows, which differ only in description and page |
| 17 | Two rows alike in every field but the page, in one filing | **2 items**, no drop | the reviewer's case, stated so the boundary is measured from both sides |
| 18 | Walmart does not move | `MERGED 14`, Asda and Seiyu both present | the criterion 1 command |
| 19 | The cross-filing behaviour does not move | the same results as round 1 for criteria 3, 4, 5 and 6 | re-run them |
| 20 | Gates, after the last edit | types 5 in 2, lint 4 all `BLE001`, census 64, route 200 | the commands above |
| 21 | The failing test set | the same two tests as round 1, and no others | `-m pytest -q --ignore-glob="*_rule3_red.py" -p no:randomly`, compared **by name** |

### Not in this round

- **The differently-worded re-report across filings is a silent double-count.** The
  reviewer's F2. It is a backlog item, not this round's work: the reviewer measured that
  `plan_filings` gives every filing after the oldest its own fiscal year alone, so the
  planned path has disjoint years and a cross-filing re-report needs the model to
  volunteer a year it was not asked for. In the real Walmart file it never did.
- **Carrying a drop to the web page.** Backlog item 62. Out of scope, and the reviewer
  agreed stopping was right.
- **`tests/`.** Both red tests build their repeat with a **different** description and
  cannot pass under any correct new key. The tester re-expresses them.
