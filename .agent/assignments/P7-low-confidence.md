---
id: P7-low-confidence
phase: 7 — label the assumptions
agent: programmer
depends_on: [P6-honest-output, P6b-wacc-fixture]
---

# Stop applying adjustments the model is not sure of, and show what was left out

## The user's decision — 2026-09-22

> **"For low confidence, just leave a note and document, but don't need to adjust the
> F/S."**

That is the recorded decision this unit implements. It settles the open half of backlog
item 36, and **it is not yours to re-open.** A `low`-confidence non-recurring item is
**not applied** to the financial statements. It is listed separately, with its
description and its cited source, so a reader can see exactly what was excluded and put
it back by hand if they disagree.

## Objective

The same L3Harris filing, extracted twice, produced **$343.15** and **$296.01**. The
largest single cause was one non-recurring item worth **1,140M** present in one run and
absent from the other — and **the model itself tagged it `confidence: low`.**

The tag is requested, parsed, stored and printed. **Nothing that computes ever reads
it:**

```
requested                 ingestion/claude_extractor.py:255
parsed, defaulting "high" ingestion/claude_extractor.py:702
stored                    models/financial_statements.py:28
printed by the CLI        cli.py:624
read by analysis/         grep -c confidence analysis/normalizer.py  ->  0
```

So a billion-dollar adjustment the model was unsure of moved the valuation exactly as
much as a figure read cleanly off a page.

**This also puts the LLM boundary back where `rules.md` rule 1 says it belongs.** The
model identifies a candidate and cites its note; **`analysis/` decides what that does to
a figure.** Today `analysis/` does not decide — it applies whatever it is handed.

## What is already true — verify, do not redo

| Fact | Evidence |
|---|---|
| `confidence` is already on `NonRecurringItem`, so `analysis/` **already receives it** | `models/financial_statements.py:28` |
| `normalize_financials(financials, non_recurring)` is called by both entry points | `cli.py`, `api/routes_valuation.py` |
| the parser defaults an absent confidence to `"high"` | `ingestion/claude_extractor.py:702` |
| the two adjacent defects in `analysis/normalizer.py` — an unknown label and an unknown direction — **both now raise** | closed at `38b903c` |
| suite `1 failed, 145 passed`; `analysis/` at 255/255 statements, 80/80 branches | the gates |
| the content-keyed cache works, and `./cache` may hold valid LHX entries | `P6-honest-output` |

## What to do

1. **Partition before you normalise, and do not change `normalize_financials`'
   signature.** Add a function to `analysis/normalizer.py` that splits the items into
   applied and excluded. Both callers then pass only the applied list.

   That keeps `normalize_financials` exactly as 145 tests expect it, and it puts the
   decision in `analysis/` where rule 1 requires it.

2. **`low` is excluded. `medium` and `high` are applied.** The user's decision names low
   confidence and nothing else. **Do not invent a second threshold**, and do not make it
   configurable — a knob here is a way to reintroduce the defect.

3. **An absent or unrecognised confidence must stop, naming the value and the year.**
   `.get("confidence", "high")` defaults an unknown to the **strongest** reading, which
   is rule 3 in the optimistic direction. The two adjacent defects in the same file both
   raise now; follow them.

   Change that one line in `ingestion/claude_extractor.py` and nothing else in that file.

4. **Show what was excluded, in both outputs.** For each excluded item: the year, the
   amount, the line item, the direction, the description and **the source it cited**.
   A reader must be able to reverse the decision by hand.

   Say plainly that these were **not** applied. A list that does not say so reads as a
   summary of what was done.

5. **State the effect on the headline figure.** The output must make clear that the
   valuation excludes these items. A share price that silently differs from one a reader
   would compute from the printed adjustments is the defect this unit exists to fix,
   wearing a different face.

6. **Measure the effect on the LHX filing.** Use the content-keyed cache if `./cache`
   holds a valid entry for one of the three filings — `P6-honest-output` wrote some.
   **Only extract if it does not.** Report the implied share price with and without the
   exclusion, and name the items that were dropped.

## Files in scope

- `analysis/normalizer.py` — the partition.
- `ingestion/claude_extractor.py` — **the one `.get("confidence", "high")` line.**
- `cli.py` — passing the applied list, and printing the excluded one.
- `api/routes_valuation.py` — the same, plus the template context.
- `templates/valuation_result.html` — the excluded list.

**Nothing else.**

## Out of scope

- **`tests/`** — your write guard denies it. A tester follows you.
- **`models/`** — `NonRecurringItem` already carries the field. If you believe it needs
  a change, **stop and say so.**
- **The other half of item 36.** Total debt also varied between the two runs —
  `10,443` against `11,116` — and **there is no confidence field anywhere outside
  `NonRecurringItem`**, so the model had no way to express doubt about it. That is a
  schema question and an LLM-boundary change, which `AGENTS.md` says is an escalation.
  **Not this unit.**
- Backlog items **1, 2, 5, 6, 7, 8, 10, 25, 26, 29, 31, 32, 37, 38**.

## Done-criteria

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 1 | a `low` item is not applied to the statements | the figure is unchanged | a fixture with one `low` item; assert the income statement |
| 2 | `medium` and `high` are applied | unchanged behaviour | same fixture, two more cases |
| 3 | an absent or unrecognised confidence **stops**, naming the value and the year | raises | a fixture, and a malformed parser payload |
| 4 | the excluded items appear in the CLI output with their source | all fields listed | your LHX run; paste the block |
| 5 | the excluded items appear on the result page | rendered | `TestClient`; paste the block |
| 6 | the output says the valuation **excludes** them | the wording is unambiguous | same |
| 7 | the effect on LHX is measured | price with and without | criterion 4's run |
| 8 | **no existing assertion changed meaning** | `1 failed, 145 passed`, the failure being `test_dcf_rule3_red.py` | `pytest -q` |
| 9 | lint 5, types ≤ 14 set-diffed, census ≤ 116, `GET /` 200 | unchanged | the four gates |

**Criterion 8 is the constraint.** `analysis/normalizer.py` carries assertions derived
from the accounting by two separate testers. If one turns red, you changed a number, and
that is a blocker unless you can show the old number was wrong.

**Criterion 7 is the point.** The user is entitled to know what their own decision costs
on their own filing.

## Citations

- **The user's decision, 2026-09-22**, quoted at the top of this file. It covers the
  treatment of `low`-confidence non-recurring items and nothing else.
- `docs/9-reference/refactor-backlog.md` item **36**.
- `docs/2-rules/rules.md` rule 1 (the model identifies; `analysis/` decides) and rule 3
  (an absent input stops and names the field).
- `docs/2-rules/llm-boundary.md` — **required reading; you touch `ingestion/`.**

## Known open items

- **Excluding low-confidence items should reduce the run-to-run variance**, because the
  items that differ between runs are disproportionately the ones the model was unsure
  of. That is a claim, not a measurement. **Do not assert it** — say in your entry
  whether your LHX run supports it, and leave the measurement to a unit that runs the
  same filing several times.
- `analysis/normalizer.py:167-170` silently discards an adjustment whose **year** matches
  no statement — backlog item 25, in the file you are editing. **Not yours.** Say you
  saw it.

## Backlog items this unit is NOT fixing

- **Item 25** — the year mismatch, in your file.
- **Item 36's schema half** — no confidence field outside `NonRecurringItem`.
- **Item 2** — zero net debt. Its red test stays red; criterion 8 depends on it.

---

# Round 2 — orchestrator amendment, 2026-09-22

Review `.agent/journal/2026-09-22T2000-code_reviewer-p7-low-confidence.md` returned
`changes_requested` with two `major`. **Answer every finding by number in a new entry.**

**The commissioned work is correct and was verified by execution.** The partition, the
stop on seven malformed values, the untouched `normalize_financials`, criterion 7's
`$0.00` difference reproduced from the cache, the route behaviour, and all four gates as
sets. **Do not redo any of it.**

## F1 · `major` · your rewrite introduced a rule 3 default

`ingestion/claude_extractor.py:707` — `data.get("non_recurring_items", [])`. The
listcomp-to-loop rewrite carried a `.get` fallback with it, and it is **yours**, because
you rewrote the line.

**What it costs is specific to this unit.** A Pass 2 reply that never contained the key
becomes an empty list. Both of the outputs you just built then say **"nothing was
withheld"** about a response nobody read. The feature whose whole purpose is to tell the
user what was left out reports silence as confidence.

**An explicit empty list is legitimate** — a filing may genuinely have no non-recurring
items. **An absent key is not.** Distinguish them: accept `[]`, stop on a missing key,
naming it. The reviewer reports a second `.get` in the same hunk; answer that one too,
either by fixing it or by saying why it is sound.

## F2 · `major` · the counterfactual is wrong twice, and I published it

I reported your $63.57 figure to the user before this review ran. **That is on me, and
it is now a correction I owe them**, so the replacement must be right.

Two defects:

1. **Provenance.** The 1,140M item came from the **FY2025** filing's extraction. The
   price you computed is from the **FY2024** cache entry. Your entry describes them as
   the same filing.
2. **An undisclosed double count.** The FY2024 extraction already carries
   `+115M LHX NeXt implementation costs` for fiscal 2023. Run C therefore counts it
   twice: adjusted EBIT `3,310 = GAAP 1,426 + 1,884`, against the filing's own `744`.

**Do one of two things, and say which.** Either redo the counterfactual correctly —
right filing, no double count, provenance stated — or **withdraw the number and say it
cannot be sized from the data on disk.** Withdrawing is a complete answer and is better
than a figure that needs three caveats.

**Whichever you choose, the entry must state plainly that the earlier $63.57 is
withdrawn.** A corrected record that does not say what it corrects leaves the old number
in circulation.

## Not yours, recorded here so you do not widen into them

- `models/financial_statements.py:28` still declares `confidence: str = "high"`. The
  reviewer established that **no path a user can reach constructs a `NonRecurringItem`
  without a confidence**, so the user's decision is fully in force today. It is the last
  place absence becomes the strongest reading, and it needs a `models/` unit with a
  tester.
- **Five dev scripts under `tests/` now misrepresent the pipeline**, and the
  misrepresentation is **new as of this unit**: they apply `low` items that both entry
  points withhold, and print no excluded block, so they produce a share price neither
  the CLI nor the web app would produce. `tests/` is closed to you. A tester unit
  follows.
- The cache tuple unpack is executed by **no test** — the route tests rebind the cache
  and take the extract branch. The reviewer exercised it by hand. Also a tester's.

## Revised done-criteria

All nine stand as verified. These are added.

| # | Criterion | Expected | How it is measured |
|---|---|---|---|
| 10 | a Pass 2 reply with **no** `non_recurring_items` key **stops**, naming it | raises | a malformed payload fixture |
| 11 | a reply with an **explicit empty list** is accepted | no raise, nothing excluded | the same fixture with `[]` |
| 12 | the $63.57 figure is withdrawn in the entry, or replaced by a correct one | stated plainly | your entry |

**Criterion 8 still binds**: `1 failed, 145 passed`, and no test edited.

**Spend no tokens.** The cache holds what you need, and F1 and F2 need a parser fix and a
paragraph.
