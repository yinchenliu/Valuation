---
name: extract-filing
description: >-
  Extract a company's financial statements from its 10-K PDFs inside this Claude Code
  session, instead of through a paid API call, and save them as a session file that the
  valuation pipeline reads. Use when the user asks to extract, read or value a filing
  "in the chat", "without the API", "with Claude Code", or "to save tokens", or invokes
  /extract-filing with a filings folder and a ticker.
user-invocable: true
---

# Extract a filing in this session (route B)

The pipeline has two extraction routes. They meet at the same parser
(`docs/3-architecture/extraction.md`, "Two routes, one parser").

| Route | Who reads the PDF | Cost |
|---|---|---|
| A | the Anthropic API, called by `ingestion/claude_extractor.py` | API tokens, two calls per filing |
| B | **you, in this session**, writing a session file | this session only |

In route B you do exactly what the API model does in route A. You answer the **same
prompts** with the **same JSON**. The code then checks, parses and merges your answer
with the same functions it uses for route A. So your job is narrow, and the rules are the
API model's rules.

**Arguments:** a filings folder or `YEAR:PATH` entries, and a ticker. Example:
`/extract-filing 10K_filings/Walmart WMT`.

---

## Rule 1 binds you exactly as it binds the API model

Read [docs/2-rules/llm-boundary.md](../../../docs/2-rules/llm-boundary.md) before you start.

- **Write only figures printed on a page you read.** Never a figure you remember about
  the company, never an estimate, never a figure computed from other figures. Where a
  field is made of several rows, list each row; Python adds them.
- **Never adjust a figure to make `check` pass.** An arithmetic error means you misread
  or mismapped a line. Open the page again and find which one. There is no exception:
  the old rule that let the catch-alls close the balance sheet is gone.
- **Copy every figure in the filing's own units. Never convert one.** Most 10-Ks print
  in millions. Chipotle prints in thousands. Okta prints money in millions and shares in
  thousands. You copy the words that state the unit, with their page, into `units` and
  `share_units` (step 2.4). Python reads the scale word and converts every figure to
  millions (`P14a`). The two scales may differ. That is not a reason to stop.

## Steps

The interpreter is `.venv/bin/python` on macOS and `.venv/Scripts/python.exe` on
Windows. Below, `SE` means `.venv/bin/python -m ingestion.session_extraction`.

### 1. Plan

```
SE plan <folder or YEAR:PATH ...> -t TICKER -n "Company name" -o extractions/TICKER.json
```

This writes a skeleton. It lists each filing with its fiscal year, its sha256, the years
to extract from it and whether to extract its balance sheet. **Do not change the plan.**
It is the same plan route A uses.

`plan` takes each fiscal year from the filename and verifies it against the filing: the
cover page's "For the fiscal year ended" date, and the year printed above the income
statement's columns. A 52- or 53-week company such as L3Harris files its fiscal 2025 10-K
with a 2026 date, so `plan` stops on it and names the year the filing gives. **Do not
work around the stop.** Tell the user, and re-run `plan` with `YEAR:PATH` entries only
when the user agrees, for example `2024:"10K_filings/LHX/…_2025-01-03_….pdf"`.

When a filing labels its columns by date ("January 3, 2025") and not by year, the prompt
still asks for "fiscal year 2024". Read the column whose date ends that fiscal year.

### 2. Pass 1, for each filing N

1. Get the prompt, and follow it exactly:
   ```
   SE prompt extractions/TICKER.json --filing N --pass 1
   ```
2. Find the statement pages:
   ```
   SE locate extractions/TICKER.json --filing N
   ```
3. Read those pages from the PDF's text layer:
   ```
   SE text extractions/TICKER.json --filing N --pages 21-23
   ```
   Read the income statement, the cash flow statement and, if the plan asks for it, the
   balance sheet. Read a note only when the prompt sends you there, for example for
   gross interest expense.

   **Use the text layer first.** It costs fewer tokens than page images, and it works on
   both machines. The Read tool renders a PDF page only where `pdftoppm` is installed,
   and on the macOS machine it is not (`docs/8-build/environment.md`). Fall back to the
   Read tool with its `pages` parameter only when a page's text is garbled, for example
   a scanned page, and only where it works.

   One PDF page can hold several printed pages. Walmart's PDF page 21 holds printed
   pages 49 to 52. Record **PDF** page numbers, the ones `text` and `locate` use.
4. Write the Pass 1 JSON object into `filings[N].pass1`, and the page numbers into
   `filings[N].pages_read.pass1`. Write a JSON object, not a string. Write every key the
   schema names.

   **The two printed unit statements** (format `session-extraction-v3`, `P14a`):

   ```json
   "units":       {"printed": "(Amounts in millions, except per share data)", "page": 21},
   "share_units": {"printed": "(Amounts in millions, except per share data)", "page": 21}
   ```

   - `units` is the statement of the unit of the money figures, usually just under the
     income statement's title. `share_units` is the statement of the unit of the
     diluted share count. When one statement covers both, `share_units` copies it with
     its page.
   - Copy the **whole** statement exactly as `text` prints it, with its parentheses.
     `check` looks for it as one whole parenthesised group, or one whole text line, on
     the page it cites. A fragment is not found: `(in thousands)` is not found on
     Okta's page 58, which prints `(dollars in millions, shares in thousands, except
     per share data)`.
   - `units` must cite a page that an income statement row cites. `share_units` must
     cite the `units` page or a page that a `diluted_shares` row cites. Words such as
     `(In thousands)` above a stock-award table are not the statement.
   - A unit statement that `check` cannot find **stops** the run (exit 2), because a
     wrong scale moves every figure by a factor of 1,000. So does a statement with no
     `thousands`, `millions` or `billions`, and one that excepts shares. Tell the user.
     Never write a scale word the filing does not print.

   **Every money field is a list of printed rows**:

   ```json
   "capex": [
     {"label": "Payments for property and equipment", "value": 26642, "page": 23},
     {"label": "Payments for business acquisitions, net of cash acquired", "value": 53, "page": 23}
   ]
   ```

   - One row per printed line: its label as printed, the one figure printed for that
     year under the field's sign rule, and its 1-based PDF page.
   - **`check` looks for every row on the page it cites** (`P12a`): the label and the
     figure on one line of that page's text layer. Copy the label from the `text`
     output, not from memory, and record the PDF page that `text` printed it under. A
     shortened label is still found; a reworded one is not.
   - **Never add, subtract or net rows yourself.** Python sums each list.
   - `[]` means the filing prints no such row. Never omit a key.
   - Every row belongs to exactly one field. A row that matches no named field goes
     into its section's `other_*` list.
   - `gross_profit`, `operating_income` and `net_income` are the printed subtotal rows.
     Write `gross_profit: []` when the filing prints none.
   - The balance sheet also takes the printed `total_assets` and
     `total_liabilities_and_equity` rows.
5. Run `SE check extractions/TICKER.json`. Pass 2 is still empty, so expect that stop.
   Fix every Pass 1 problem it reports by reading the page again.

   **A balance sheet `FAIL` means a row was misread, missed, or listed twice.** The
   message lists the rows Python added. Find the missing or extra row on the page.
   **Never change a figure, or add a row the filing does not print, to make the totals
   agree.** If the page really does not tie, leave the `FAIL`. The user decided on
   2026-10-02 that a failed check is shown, with the figures kept.

### 3. Pass 2, for each filing N

1. Get the prompt. It includes the income statement summary built from your Pass 1:
   ```
   SE prompt extractions/TICKER.json --filing N --pass 2
   ```
2. Read the pages `locate` listed for restructuring, impairment, litigation, gains and
   losses on sale, and acquisition costs, with `SE text`. Read the MD&A discussion of
   the same items.
3. Write the Pass 2 object into `filings[N].pass2`, and the pages into
   `filings[N].pages_read.pass2`. Give every item a `source` that names the note and
   the page, and the `confidence` the evidence on the page supports. **Add no rule the
   prompt does not state.** A stricter or looser standard here than in route A makes the
   two routes disagree about the same filing. Items marked `low` are withheld from the
   valuation and listed. Flag only an item whose amount the filing prints.
   `{"non_recurring_items": []}` is a valid answer.

   Write `amount` as a JSON number, never a string, and `year` as an integer. Give every
   item all eight schema keys. `check` stops on anything else and names the item.

### 4. Label and check

1. Set `extracted_by.model` to your model ID, and `extracted_by.date` to today's date.
2. Run `SE check extractions/TICKER.json` until it exits 0. Exit 1 means only failed
   checks remain: arithmetic, or a row "not found on page N". For a row not found, open
   that page with `text` again and correct the label or the page to what is printed.
   Never change a figure to make it match. Report each failure that remains to the user,
   and say whether a second reading of the page confirmed the figure.

### 5. Value it

```
.venv/bin/python cli.py --session-file extractions/TICKER.json
```

Or start the web app and use "Use a Claude Code session file" on the upload page.

## Report to the user

- The plan: which years and which balance sheet came from which filing.
- For each filing, the pages you read for each pass.
- **Three figures you can name with their page**, for example revenue, CFO and total
  equity. "The pipeline ran" proves nothing (`docs/0-start.md`, fact 3). A figure with
  its page does.
- Every `check` warning that remains, and why.
- Every non-recurring item, with its confidence and note.

## Keep the context small

A 10-K has 100 to 200 printed pages. Read only the pages `locate` points to. The
statements are usually three to six pages. `text` refuses more than 20 pages at once. Do
not read the whole PDF.
