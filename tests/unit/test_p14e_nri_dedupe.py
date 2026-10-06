"""The merge's two non-recurring-item keys: `ingestion/claude_extractor.py`.

`merge_filing_extractions` is the one function route A and route B share, and
`P14e-nri-dedupe` gave it **two** keys, each for one comparison:

| Key | Fields | Governs |
|---|---|---|
| `nri_identity` | `(year, amount, direction, description)` | **across** filings |
| `nri_identity_within_filing` | the same four, plus `page` | **one** filing's own answer |

**Why this file is hand-built and not driven by `extractions/WMT.json`.** The
programmer and the round 2 code reviewer each measured, independently, that the
real Walmart file is green against *three* one-line mutations of this merge:
removing `page` from the within-filing key, adding `page` to the across-filing key,
and registering a dropped row as kept. All three still give 14 merged items with
Asda and Seiyu present, because that file has no cross-filing year overlap and no
repeated row. **A suite built on the real file alone would pass three broken
versions of this merge.** Every boundary case below is therefore built by hand, in
round numbers, and the real file appears once at the end as a regression guard and
is labelled as one.

**Where every expected value here comes from.** Nothing below was read off a run.

1. **The key definitions**, quoted above from
   `.agent/assignments/P14e-nri-dedupe-tests.md` "Fact 3" and from the two
   functions' docstrings. Two tuples are equal exactly when every field is equal,
   so the number of items out of a merge is a count anyone can do on paper from
   the inputs: it is stated in a comment beside each case.
2. **The identity "same JSON in, same object out"** for the two key functions:
   each returns the fields it was given, so the expected tuple *is* the input.
3. **Two figures read off a filing page.** `10K_filings/WMT/Walmart
   Inc._10-K_2024-01-31_English.pdf`, PDF page 66: "Upon closing of the
   transaction, the Company recorded an incremental pre-tax loss of $0.2 billion
   in other gains and losses" (Asda, the U.K. retail operations, divested February
   2021). PDF page 67, the same sentence for Seiyu (Japan, divested March 2021).
   Both fall in Walmart's fiscal 2022 ("the first quarter of fiscal 2022", same
   page 67). **Two different losses, each $0.2 billion, one year, one direction,
   two pages.** That pair is what the within-filing key has to keep apart, and
   losing one of them is backlog item 112.
4. **What a drop report must name**, from the assignment's step 5: the year,
   amount, direction, description, filing and page of the item kept **and** the
   item dropped. Each is asserted as a field present in the line, never as a whole
   sentence, so a reword is not a failure.

**No network, no API key, no model call.** Nothing here imports a model client or
calls one; the merge is pure Python over objects built in this file. The one test
that reads the repository's real session file is skipped when this machine does
not hold it or the three PDFs it cites.

**What is deliberately NOT asserted.** Backlog item 119 — two filings reporting one
charge in *different* words are counted twice, and nothing says so. One test below
records that as the measured behaviour and names item 119; it asserts neither that
the behaviour is right nor that it is wrong, because deciding that two texts mean
one charge is the model's judgement and not Python's (rule 1).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion.claude_extractor import (
    REPEAT_ACROSS_FILINGS,
    REPEAT_WITHIN_ONE_FILING,
    FilingPlan,
    merge_filing_extractions,
    nri_identity,
    nri_identity_within_filing,
    parse_pass2,
)
from models.financial_statements import (
    BalanceSheet,
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
    NonRecurringItem,
)
from tests.unit._real_filings import REPO_ROOT

# ===========================================================================
# Builders. Every figure a round number, so every count below is arithmetic
# anyone can do on paper.
# ===========================================================================


def nri(year: int, amount: float, direction: str, description: str,
        page: int) -> NonRecurringItem:
    """One item, with the five fields the two keys read spelled out at the call.

    The fields no key reads (`line_item`, `category`, `confidence`,
    `printed_units`, `units_page`, `source`) are held constant, so a case that
    gives two items can only have done so on a field that IS in a key.
    """
    return NonRecurringItem(
        year=year, description=description, amount=amount, direction=direction,
        page=page, line_item="other_non_operating", category="other",
        confidence="high", printed_units="(Amounts in millions)", units_page=1,
        source="Note 12",
    )


def plan(fiscal_year: int) -> FilingPlan:
    return FilingPlan(fiscal_year=fiscal_year, pdf_path=f"F{fiscal_year}.pdf",
                      target_years=None, include_bs=False)


def fin(year: int, revenue: float) -> FinancialStatements:
    """One income statement, one cash flow, one balance sheet, all for `year`."""
    return FinancialStatements(
        ticker="IGNORED", company_name="Ignored",
        income_statements=[IncomeStatement(year=year, revenue=revenue)],
        cash_flow_statements=[CashFlowStatement(year=year, net_income=revenue)],
        balance_sheets=[BalanceSheet(year=year, cash_and_equivalents=revenue,
                                     printed_unit_in_millions=1.0)],
    )


def run_merge(
    capsys: pytest.CaptureFixture[str],
    *filings: tuple[int, list[NonRecurringItem]],
) -> tuple[FinancialStatements, list[NonRecurringItem], list[dict[str, str]]]:
    """Merge `filings` in the order given and return what was printed, parsed.

    Each filing is `(fiscal_year, items)`; its statements hold that year alone,
    with the year itself as the revenue, so a statement in the merged result can
    be traced back to the filing it came from.

    The third value is one dict per `[MERGE]` block, with the headline and the
    two rows as raw text. Parsing the block into three labelled strings is the
    only thing this helper knows about the message's shape; every assertion
    about its *content* names one field and looks for that field's own text.
    """
    extractions = [
        (plan(fiscal_year), fin(fiscal_year, float(fiscal_year)), items)
        for fiscal_year, items in filings
    ]
    merged, merged_items = merge_filing_extractions(extractions, "TST", "Test Co")
    out = capsys.readouterr().out
    reports: list[dict[str, str]] = []
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("[MERGE] "):
            reports.append({"headline": stripped[len("[MERGE] "):]})
        elif stripped.startswith("kept   :"):
            reports[-1]["kept"] = stripped
        elif stripped.startswith("dropped:"):
            reports[-1]["dropped"] = stripped
    return merged, merged_items, reports


def fields_missing_from(row: str, item: NonRecurringItem, filing: str) -> list[str]:
    """Which of the six fields a drop report must name are absent from `row`.

    The six are the assignment's step 5: year, amount, direction, description,
    filing and page. Each is looked for on its own, never as part of a whole
    sentence, so rewording the message around them is not a failure — and a test
    that fails names the field that went missing rather than printing `False`.
    """
    present = {
        "year": str(item.year) in row,
        "amount": str(item.amount) in row,
        "direction": item.direction in row,
        "description": item.description in row,
        "filing": filing in row,
        "page": f"page {item.page}" in row,
    }
    return [name for name, found in present.items() if not found]


def names_item(row: str, item: NonRecurringItem, filing: str) -> bool:
    """True when `row` names every one of the six fields of `item`."""
    return not fields_missing_from(row, item, filing)


# ===========================================================================
# 1. The two keys, read directly
# ===========================================================================
#
# Expected value: the key's own definition, and the fields the call was given.


def test_nri_identity_is_the_four_fields_it_was_given() -> None:
    item = nri(2022, 200.0, "add_back", "Incremental loss on the Asda divestiture", 66)
    # The across-filing key, from the assignment's Fact 3 table:
    # (year, amount, direction, description). The expected tuple is the input.
    assert nri_identity(item) == (
        2022, 200.0, "add_back", "Incremental loss on the Asda divestiture")


def test_nri_identity_ignores_the_page_because_a_page_moves_between_filings() -> None:
    """`page` is out of the across-filing key.

    The same Walmart note is "... Investments, page 52" in the FY2024 10-K and
    "... page 51" in the FY2025 (measured from the two filings by the round 1 code
    reviewer). A key holding the page could never match the same disclosure across
    two PDFs, so every overlapping item would be counted twice.
    """
    on_page_52 = nri(2024, 3800.0, "add_back", "Net losses on equity investments", 52)
    on_page_51 = nri(2024, 3800.0, "add_back", "Net losses on equity investments", 51)
    assert nri_identity(on_page_52) == nri_identity(on_page_51)


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("year", nri(2023, 200.0, "add_back", "Incremental loss, Asda", 66)),
        ("amount", nri(2022, 300.0, "add_back", "Incremental loss, Asda", 66)),
        ("direction", nri(2022, 200.0, "remove", "Incremental loss, Asda", 66)),
        ("description", nri(2022, 200.0, "add_back", "Incremental loss, Seiyu", 66)),
    ],
)
def test_nri_identity_separates_items_that_differ_in_any_of_its_four_fields(
    field: str, changed: NonRecurringItem,
) -> None:
    base = nri(2022, 200.0, "add_back", "Incremental loss, Asda", 66)
    assert nri_identity(base) != nri_identity(changed), field


def test_nri_identity_within_filing_is_the_four_fields_plus_the_page() -> None:
    item = nri(2022, 200.0, "add_back", "Incremental loss on the Asda divestiture", 66)
    # The within-filing key, from the assignment's Fact 3 table: the across-filing
    # key's four fields, plus `page`. The expected tuple is the input.
    assert nri_identity_within_filing(item) == (
        2022, 200.0, "add_back", "Incremental loss on the Asda divestiture", 66)
    assert nri_identity_within_filing(item) == (*nri_identity(item), item.page)


def test_nri_identity_within_filing_separates_two_rows_by_the_page_alone() -> None:
    """Inside one PDF the page is stable, and it is the field that separates two
    real items of the same size printed on different pages."""
    on_66 = nri(2022, 200.0, "add_back", "Incremental pre-tax loss on a divestiture", 66)
    on_67 = nri(2022, 200.0, "add_back", "Incremental pre-tax loss on a divestiture", 67)
    assert nri_identity(on_66) == nri_identity(on_67)
    assert nri_identity_within_filing(on_66) != nri_identity_within_filing(on_67)


# ===========================================================================
# 2. Across filings: the same item re-reported is one item
# ===========================================================================


def test_one_item_re_reported_by_a_later_filing_is_one_item(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two filings, one charge. A re-report copies the printed line, so the text
    is the same and only the page moves: page 52 in the earlier PDF, page 51 in
    the later one, as the same Walmart note really does.

    By hand, from the across-filing key (year, amount, direction, description)
    with `page` NOT in it: both rows give (2023, 10.0, 'add_back',
    'Restructuring charges, Mexico segment'). One key, first seen kept.
    2 in, 1 out, 1 drop.

    This case is the one that goes red if `page` is ever added to the
    across-filing key: the two keys would then differ and nothing would merge.
    """
    first = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 52)
    repeat = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 51)
    _, items, reports = run_merge(capsys, (2023, [first]), (2024, [repeat]))
    assert items == [first]
    assert items[0].page == 52
    assert len(reports) == 1
    assert reports[0]["headline"] == REPEAT_ACROSS_FILINGS


def test_three_filings_re_reporting_one_item_give_one_item_and_two_drops(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """By hand: three rows, one across-filing key, first seen kept.
    3 in, 1 out, 2 drops — one per row dropped. Both drops are reported against
    the first filing's row, which is the one in the merged list."""
    first = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 52)
    second = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 51)
    third = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 49)
    _, items, reports = run_merge(
        capsys, (2023, [first]), (2024, [second]), (2025, [third]))
    assert items == [first]
    assert [r["headline"] for r in reports] == [REPEAT_ACROSS_FILINGS] * 2
    # Every `kept:` line names the row that really is in the merged list: page 52,
    # from F2023.pdf.
    for report in reports:
        assert fields_missing_from(report["kept"], first, "F2023.pdf") == []
    assert fields_missing_from(reports[0]["dropped"], second, "F2024.pdf") == []
    assert fields_missing_from(reports[1]["dropped"], third, "F2025.pdf") == []


@pytest.mark.parametrize(
    ("field", "later"),
    [
        ("year", nri(2024, 10.0, "add_back", "Restructuring charges, Mexico", 51)),
        ("amount", nri(2023, 11.0, "add_back", "Restructuring charges, Mexico", 51)),
        ("direction", nri(2023, 10.0, "remove", "Restructuring charges, Mexico", 51)),
    ],
)
def test_two_filings_whose_rows_differ_in_a_key_field_give_two_items(
    capsys: pytest.CaptureFixture[str], field: str, later: NonRecurringItem,
) -> None:
    """By hand: the two across-filing keys differ in one field, so they are two
    keys, so both rows are kept and nothing is dropped. 2 in, 2 out, 0 drops."""
    earlier = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico", 52)
    _, items, reports = run_merge(capsys, (2023, [earlier]), (2024, [later]))
    assert items == [earlier, later], field
    assert reports == []


def test_a_differently_worded_re_report_is_counted_twice_backlog_item_119(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """**Recorded, not endorsed.** Backlog item 119.

    Two filings describing one charge in different words give two items, and
    nothing reports it. By hand from the key: the descriptions differ, so the
    two across-filing keys differ, so both are kept. 2 in, 2 out, 0 drops.

    This test asserts neither that the behaviour is right nor that it is wrong.
    It states what the key, as defined, must do with two different texts —
    deciding that two texts mean one charge is a reading the model makes and
    Python does not (rule 1). It is here so that a change to item 119 is a
    deliberate change to this test, and never a silent one.
    """
    earlier = nri(2023, 10.0, "add_back", "Restructuring charges", 52)
    later = nri(2023, 10.0, "add_back", "Charges for the restructuring of a segment", 51)
    _, items, reports = run_merge(capsys, (2023, [earlier]), (2024, [later]))
    assert items == [earlier, later]
    assert reports == []


# ===========================================================================
# 3. Within one filing: the identical printed line twice is one item
# ===========================================================================


def test_the_identical_row_written_twice_in_one_filing_is_one_item(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """By hand, from the within-filing key (the four fields plus `page`): both
    rows give (2022, 200.0, 'add_back', '<one text>', 66). One key, first seen
    kept. The filing's other row is a different year. 3 in, 2 out, 1 drop."""
    asda = nri(2022, 200.0, "add_back", "Incremental pre-tax loss, Asda", 66)
    asda_again = nri(2022, 200.0, "add_back", "Incremental pre-tax loss, Asda", 66)
    unrelated = nri(2023, 40.0, "add_back", "Opioid legal charges", 70)
    _, items, reports = run_merge(capsys, (2024, [asda, asda_again, unrelated]))
    assert items == [asda, unrelated]
    assert len(reports) == 1
    assert reports[0]["headline"] == REPEAT_WITHIN_ONE_FILING


def test_asda_and_seiyu_are_two_items_in_one_filing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The pair backlog item 112 is about, as the filing prints it.

    `Walmart Inc._10-K_2024-01-31_English.pdf` PDF page 66 prints an incremental
    pre-tax loss of $0.2 billion on the Asda divestiture; PDF page 67 prints an
    incremental pre-tax loss of $0.2 billion on the Seiyu divestiture. Both fall
    in Walmart's fiscal 2022 and both are add-backs. $0.2 billion is 200 $M, the
    scale the merge sees (`convert_filing_to_millions` runs per filing first).

    By hand: the two rows differ in `description` AND in `page`, so they differ
    under both keys. 2 in, 2 out, 0 drops — and 400 $M of add-back, not 200.
    """
    asda = nri(2022, 200.0, "add_back",
               "Incremental pre-tax loss on the divestiture of Asda", 66)
    seiyu = nri(2022, 200.0, "add_back",
                "Incremental pre-tax loss on the divestiture of Seiyu", 67)
    _, items, reports = run_merge(capsys, (2024, [asda, seiyu]))
    assert items == [asda, seiyu]
    assert reports == []
    # The arithmetic the defect cost: two $0.2bn losses are 400 $M of add-back.
    assert sum(i.amount for i in items) == 400.0


def test_two_rows_alike_in_every_field_but_the_page_are_two_items(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The same boundary from the other side, and the case `page` is load-bearing
    for: the two rows agree on year, amount, direction and description, and
    differ only in the page.

    By hand, from the within-filing key, which holds all five fields: 66 != 67,
    so the two keys differ, so both rows are kept. 2 in, 2 out, 0 drops.

    This case is the one that goes red if `page` is ever removed from the
    within-filing key: the two keys would collapse into one and a real item would
    be dropped — which is exactly backlog item 112.
    """
    on_66 = nri(2022, 200.0, "add_back", "Incremental pre-tax loss on a divestiture", 66)
    on_67 = nri(2022, 200.0, "add_back", "Incremental pre-tax loss on a divestiture", 67)
    _, items, reports = run_merge(capsys, (2024, [on_66, on_67]))
    assert items == [on_66, on_67]
    assert reports == []


def test_three_identical_rows_in_one_filing_give_one_item_and_two_drops(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """By hand: three rows, one within-filing key, first seen kept.
    3 in, 1 out, 2 drops."""
    row = nri(2022, 200.0, "add_back", "Incremental pre-tax loss, Asda", 66)
    again = nri(2022, 200.0, "add_back", "Incremental pre-tax loss, Asda", 66)
    thrice = nri(2022, 200.0, "add_back", "Incremental pre-tax loss, Asda", 66)
    _, items, reports = run_merge(capsys, (2024, [row, again, thrice]))
    assert items == [row]
    assert [r["headline"] for r in reports] == [REPEAT_WITHIN_ONE_FILING] * 2


# ===========================================================================
# 4. Both drop reports name both items, field by field
# ===========================================================================
#
# What a report must name is the assignment's step 5, not an observed sentence:
# the year, amount, direction, description, filing and page of the item kept AND
# of the item dropped. Each is asserted as its own text in its own row.


def test_a_cross_filing_drop_names_the_year_amount_direction_text_filing_and_page(
    capsys: pytest.CaptureFixture[str],
) -> None:
    kept = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 52)
    dropped = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 51)
    _, items, reports = run_merge(capsys, (2023, [kept]), (2024, [dropped]))
    (report,) = reports
    assert report["headline"] == REPEAT_ACROSS_FILINGS
    assert fields_missing_from(report["kept"], kept, "F2023.pdf") == []
    assert fields_missing_from(report["dropped"], dropped, "F2024.pdf") == []
    # The two rows are told apart by the page and the filing, which is the whole
    # point of printing both: 52 in F2023.pdf, 51 in F2024.pdf.
    assert "page 52" in report["kept"] and "page 51" not in report["kept"]
    assert "page 51" in report["dropped"] and "page 52" not in report["dropped"]
    # And the kept row names an item that really is in the merged list.
    assert items == [kept]


def test_a_within_filing_drop_names_both_copies_with_the_same_filing_and_page(
    capsys: pytest.CaptureFixture[str],
) -> None:
    kept = nri(2022, 200.0, "add_back", "Incremental pre-tax loss, Asda", 66)
    dropped = nri(2022, 200.0, "add_back", "Incremental pre-tax loss, Asda", 66)
    _, items, reports = run_merge(capsys, (2024, [kept, dropped]))
    (report,) = reports
    assert report["headline"] == REPEAT_WITHIN_ONE_FILING
    assert fields_missing_from(report["kept"], kept, "F2024.pdf") == []
    assert fields_missing_from(report["dropped"], dropped, "F2024.pdf") == []
    assert items == [kept]


def test_the_two_headlines_differ_so_a_reader_is_told_which_comparison_dropped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One run, both kinds of drop. The two reasons are different facts about the
    filings — "a later filing repeated it" and "one filing printed it twice" — so
    a reader must not have to guess which one happened.

    By hand: filing 2023 writes its row twice (one within-filing key) -> 1 kept,
    1 within-filing drop. Filing 2024 re-reports that same charge with the same
    text on another page -> 1 across-filing drop. 3 in, 1 out, 2 drops.
    """
    row = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 52)
    row_again = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 52)
    re_reported = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 51)
    _, items, reports = run_merge(
        capsys, (2023, [row, row_again]), (2024, [re_reported]))
    assert items == [row]
    assert [r["headline"] for r in reports] == [
        REPEAT_WITHIN_ONE_FILING, REPEAT_ACROSS_FILINGS]
    assert REPEAT_WITHIN_ONE_FILING != REPEAT_ACROSS_FILINGS


# ===========================================================================
# 5. A drop does not stop the run
# ===========================================================================


def test_a_drop_does_not_stop_the_run_and_the_statements_still_merge(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two filings reporting one item is normal, so the merge reports and returns.

    The statements are the control that the run really continued past the drop:
    by the merge's year rule (prefer the filing whose fiscal_year equals the
    statement year, else first seen), filing 2023 holds year 2023 and filing 2024
    holds year 2024, each primary for its own year, so both survive with their
    own markers — 2023.0 and 2024.0, the revenue `fin` was given.
    """
    first = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 52)
    repeat = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 51)
    merged, items, reports = run_merge(capsys, (2023, [first]), (2024, [repeat]))
    assert len(reports) == 1
    # The merge returned, with everything a caller needs.
    assert items == [first]
    assert {s.year: s.revenue for s in merged.income_statements} == {
        2023: 2023.0, 2024: 2024.0}
    assert [b.year for b in merged.balance_sheets] == [2023, 2024]
    assert (merged.ticker, merged.company_name) == ("TST", "Test Co")


# ===========================================================================
# 6. The compound case: every `kept:` names an item in the merged list
# ===========================================================================


def test_every_kept_line_names_an_item_that_is_really_in_the_merged_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Both at once: an earlier filing already reported the charge AND the later
    filing writes its own row twice, byte for byte.

    By hand. Filing 2023 contributes the charge once, on page 52. Filing 2024
    writes the same printed line twice, both on page 51. The within-filing key
    compares a row against the rows **this filing kept**, and this filing keeps
    neither — both carry the 2023 row's across-filing key, so both are dropped
    there. 3 in, 1 out, 2 drops, **both of the across-filing kind**.

    The requirement this locks is the word `kept`. A report that says "kept" of a
    row which was itself dropped sends a reader looking for an item that is not in
    the merged list. Only one item is in that list — the 2023 row, page 52, from
    F2023.pdf — so every `kept:` row must name that one, and no other.
    """
    kept = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 52)
    later_row = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 51)
    later_row_again = nri(2023, 10.0, "add_back",
                          "Restructuring charges, Mexico segment", 51)
    _, items, reports = run_merge(
        capsys, (2023, [kept]), (2024, [later_row, later_row_again]))
    assert items == [kept]
    assert [r["headline"] for r in reports] == [REPEAT_ACROSS_FILINGS] * 2
    for report in reports:
        # The kept row matches an item that really is in the merged list, by its
        # own fields and by the filing it came from.
        assert any(names_item(report["kept"], i, "F2023.pdf") for i in items)
        # And it is NOT one of the rows this run dropped: those sit on page 51 of
        # F2024.pdf, and neither is in `items`.
        assert "F2024.pdf" not in report["kept"]
        assert "page 51" not in report["kept"]
    assert fields_missing_from(reports[0]["dropped"], later_row, "F2024.pdf") == []
    assert fields_missing_from(reports[1]["dropped"], later_row_again, "F2024.pdf") == []


def test_a_later_filing_writing_two_rows_that_differ_only_in_the_page_drops_both(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The same compound shape with the later filing's two rows on different pages.

    By hand: within one filing, 51 != 49, so the two rows are two rows and the
    within-filing key drops neither. Both carry the 2023 row's across-filing key,
    so the across-filing comparison drops both. 3 in, 1 out, 2 across-filing
    drops, each naming the 2023 row as kept.
    """
    kept = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 52)
    later_first = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 51)
    later_second = nri(2023, 10.0, "add_back", "Restructuring charges, Mexico segment", 49)
    _, items, reports = run_merge(
        capsys, (2023, [kept]), (2024, [later_first, later_second]))
    assert items == [kept]
    assert [r["headline"] for r in reports] == [REPEAT_ACROSS_FILINGS] * 2
    for report in reports:
        assert fields_missing_from(report["kept"], kept, "F2023.pdf") == []
    assert fields_missing_from(reports[0]["dropped"], later_first, "F2024.pdf") == []
    assert fields_missing_from(reports[1]["dropped"], later_second, "F2024.pdf") == []


# ===========================================================================
# 7. Rule 3: `page` is the field this unit put into a key, and it cannot default
# ===========================================================================
#
# The merge reads five fields of every item. All five are required fields of
# `NonRecurringItem` with no default (models/financial_statements.py:67-77), and
# the Pass 2 parser stops on an absent one before the merge can run. `page` is
# the one this unit newly made load-bearing, so its stop is locked here; the
# stops for `confidence` and `source` are already locked in
# tests/unit/test_claude_extractor.py.


def _pass2_item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "year": 2022,
        "description": "Incremental pre-tax loss on the divestiture of Asda",
        "amount": 0.2,
        "line_item": "other_non_operating",
        "direction": "add_back",
        "category": "gain_loss_asset_sale",
        "confidence": "high",
        "page": 66,
        "units": {"printed": "(Amounts in billions)", "page": 66},
        "source": "Note 12 - Divestitures",
    }
    item.update(overrides)
    return item


def test_an_item_with_no_page_stops_and_the_message_names_page() -> None:
    """`page` is in the within-filing key, so a merge that never saw one would be
    comparing four fields where it must compare five. It cannot happen: the Pass 2
    parser stops first, and the stop names the field."""
    item = _pass2_item()
    del item["page"]
    with pytest.raises(ValueError, match="'page'") as excinfo:
        parse_pass2(json.dumps({"non_recurring_items": [item]}))
    # The stop names the item too, so a reader can find it in the filing.
    assert "year 2022" in str(excinfo.value)
    assert "Asda" in str(excinfo.value)


def test_an_item_whose_page_is_not_a_positive_page_number_stops_naming_page() -> None:
    with pytest.raises(ValueError, match="'page'") as excinfo:
        parse_pass2(json.dumps({"non_recurring_items": [_pass2_item(page=0)]}))
    assert "year 2022" in str(excinfo.value)


@pytest.mark.parametrize("field", ["year", "description", "amount", "direction"])
def test_an_item_missing_any_other_key_field_stops_and_names_it(field: str) -> None:
    """The other four fields the two keys read. None may arrive absent: `amount`
    has its own named stop, and the remaining three stop in the dataclass call,
    where the exception names the field. No key field defaults."""
    item = _pass2_item()
    del item[field]
    with pytest.raises((ValueError, KeyError), match=field):
        parse_pass2(json.dumps({"non_recurring_items": [item]}))


# ===========================================================================
# 8. The real Walmart file — A REGRESSION GUARD, NOT EVIDENCE ABOUT EITHER KEY
# ===========================================================================
#
# Measured by the programmer and re-measured independently by the round 2 code
# reviewer: `extractions/WMT.json` gives `MERGED 14` with Asda and Seiyu present
# against the correct code AND against three one-line mutants of it. **It cannot
# see either key's boundary.** Sections 1 to 6 above are what tests the keys;
# this is here to catch a regression of backlog item 112 on the one real
# multi-filing extraction this repository holds, and nothing more.

_WMT_SESSION = REPO_ROOT / "extractions" / "WMT.json"


def _wmt_session() -> dict[str, object] | None:
    """The real session file, if this machine holds it AND the PDFs it cites.

    `extractions/` and `10K_filings/` are both outside git, so the set of files
    differs from machine to machine (backlog item 101: a guard that misses is a
    test that reports neither pass nor fail).
    """
    if not _WMT_SESSION.is_file():
        return None
    data = json.loads(_WMT_SESSION.read_text(encoding="utf-8"))
    filings = data["filings"]
    if not all(Path(f["pdf_path"]).is_file() for f in filings):
        return None
    return data


_WMT = _wmt_session()


@pytest.mark.skipif(
    _WMT is None,
    reason=("this machine does not hold extractions/WMT.json together with every "
            "PDF it cites under 10K_filings/WMT/"),
)
@pytest.mark.usefixtures("_no_socket")
def test_the_real_walmart_file_keeps_every_item_it_lists_including_asda_and_seiyu(
) -> None:
    """Regression guard for backlog item 112, through the real route B loader.

    **Where the expected count comes from, without running the merge.** Two facts
    read off the session file itself, each asserted below before the count is:

    1. The three filings report **disjoint** fiscal years (the 2024 10-K reports
       2022-2024, the 2025 10-K reports 2025, the 2026 10-K reports 2026). No
       across-filing key can therefore collide, whatever the key holds.
    2. Inside each filing, no two rows agree on all five of year, amount,
       direction, description and page. No within-filing key can collide either.

    With no collision possible on either side, **every row written survives**, so
    the merged count equals the number of rows the file lists. That is 14 — and it
    was 13 before this unit, because Seiyu's $0.2 billion collided with Asda's
    under the old three-field key.

    The two survivors are checked by their printed figures: `Walmart
    Inc._10-K_2024-01-31_English.pdf` prints "an incremental pre-tax loss of $0.2
    billion" for Asda on PDF page 66 and the same figure for Seiyu on PDF page 67,
    both for fiscal 2022. $0.2 billion is 200 $M after
    `convert_filing_to_millions`.
    """
    from ingestion.session_extraction import load_session_extraction

    assert _WMT is not None
    filings = _WMT["filings"]  # type: ignore[index]

    # Premise 1: disjoint years across filings.
    year_sets = [{i["year"] for i in f["pass2"]["non_recurring_items"]} for f in filings]
    for a in range(len(year_sets)):
        for b in range(a + 1, len(year_sets)):
            assert not (year_sets[a] & year_sets[b]), (a, b)

    # Premise 2: no two rows inside one filing agree on all five key fields.
    written = 0
    for f in filings:
        rows = f["pass2"]["non_recurring_items"]
        written += len(rows)
        keys = [(r["year"], r["amount"], r["direction"], r["description"], r["page"])
                for r in rows]
        assert len(set(keys)) == len(keys), f["pdf_path"]

    # Counted from the file, not from a run: 9 + 2 + 3.
    assert written == 14

    session = load_session_extraction(_WMT_SESSION)
    assert len(session.non_recurring) == written

    # The pair backlog item 112 lost. Figures read off PDF pages 66 and 67.
    divestiture_losses = sorted(
        (i.page, i.year, i.amount, i.direction)
        for i in session.non_recurring
        if "Asda" in i.description or "Seiyu" in i.description
    )
    assert divestiture_losses == [
        (66, 2022, 200.0, "add_back"),
        (67, 2022, 200.0, "add_back"),
    ]
