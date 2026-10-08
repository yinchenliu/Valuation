"""Tests for P14g-unit-statement-pages (backlog item 114): one rule for where a
printed unit statement may sit, and the page before a statement's figures is part of it.

The defect. `_unit_statement_pages_allowed` allowed a unit statement only on a page a
figure it governs is printed on. Check B1 (`_row_scale_failures`) has allowed the row's
page *and the page before it* since P14b-note-figures. The two checks therefore held two
different rules. Walmart's fiscal 2024 10-K prints its income statement's title, its unit
statement and its year header as the last four text lines of PDF page 45 and every data
row on PDF page 46, so the correct reading — `units` cites page 45 — was refused and the
run stopped. P14g puts B1's rule in one pure function, `_pages_and_page_before`, and both
checks read it.

Where every expected value in this file comes from. No expected value was taken from the
code's output.

1. **Hand arithmetic from the rule.** The rule is one line:
   `_pages_and_page_before(pages) = pages | {p - 1 for p in pages if p > 1}`.
   Every allowed set and every printed "the pages allowed are [...]" list below is worked
   out from that line in a comment beside the assertion.
2. **A closed-form identity.** `pages ⊆ f(pages) ⊆ pages ∪ {p - 1 : p ∈ pages}`, and
   `0 ∉ f(pages)` for every input, whatever the input is. Identities hold before the code
   runs and do not need a worked example.
3. **Figures read off a filing page.** `10K_filings/WMT/Walmart Inc._10-K_2024-01-31_
   English.pdf`, read here with `pdfplumber` and cited line by line:
   - PDF page 44: no parenthesised scale statement at all;
   - PDF page 45, last four text lines: `Walmart Inc.` / `Consolidated Statements of
     Income` / `Fiscal Years Ended January 31,` / `(Amounts in millions, except per share
     data) 2024 2023 2022`. Its only scale statement is
     `(Amounts in millions, except per share data)`;
   - PDF page 46, first two text lines: `Revenues:` / `Net sales $ 642,637 $ 605,881
     $ 567,762`. Its only scale statement is `(Amounts in millions)`, which is the
     Consolidated Statements of Comprehensive Income header;
   - the PDF has 147 pages.

What this file deliberately does NOT assert. P14g widens, by one page, the window in
which a model may cite *another* table's unit statement: a `(in thousands)` note header
on the page before a `(in millions)` income statement is accepted after P14g and refused
before it. That hole is on the record (the programmer's and the reviewer's entries for
P14g, and the tester's entry for P14g-unit-statement-pages-tests). **An assertion that
the wrong answer produces zero failures would lock the hole as correct and turn red on
the day it is closed, so there is no such assertion here.** The behaviour is recorded in
the journal, not in a test.

No network call, no API key, no LLM call: every PDF is read with `pdfplumber`, and every
synthetic PDF is written by `tests/unit/_text_pdf.write_text_pdf`.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any

import pytest

from ingestion.claude_extractor import (
    PASS1_YEAR_FIELDS,
    _pages_and_page_before,
    _row_scale_failures,
    _unit_statement_failures,
    _unit_statement_pages_allowed,
)
from tests.unit._real_filings import RealFiling
from tests.unit._text_pdf import write_text_pdf

# ---------------------------------------------------------------------------
# Fixtures built by hand. Nothing here holds an expected value.
# ---------------------------------------------------------------------------

WMT_2024 = RealFiling("WMT", "Walmart Inc._10-K_2024-01-31_English.pdf")

#: Walmart's fiscal 2024 income statement header, word for word as PDF page 45 prints it.
WMT_INCOME_HEADER = "(Amounts in millions, except per share data)"

#: The income statement's figures are on this PDF page; its header is on the page before.
WMT_FIGURE_PAGE = 46
WMT_HEADER_PAGE = 45

_PARENTHESISED = re.compile(r"\([^()]*\)")


def _year_entry(
    income_page: int,
    *,
    diluted_page: int | None = None,
    cash_flow_page: int | None = None,
    year: int = 2024,
) -> dict[str, Any]:
    """One `historical_years` entry: every Pass 1 year key, rows on the pages given.

    Four income statement rows are printed on `income_page` (the diluted share count on
    `diluted_page` when that differs), and the three cash flow rows on `cash_flow_page`
    when one is given. Every other field is `[]`, which is Pass 1's answer for a row the
    filing does not print.
    """
    entry: dict[str, Any] = {"year": year}
    for field in PASS1_YEAR_FIELDS:
        if field != "year":
            entry[field] = []
    entry["revenue"] = [{"label": "Net sales", "value": 1000.0, "page": income_page}]
    entry["operating_income"] = [
        {"label": "Operating income", "value": 200.0, "page": income_page},
    ]
    entry["net_income"] = [
        {"label": "Consolidated net income", "value": 150.0, "page": income_page},
    ]
    entry["diluted_shares"] = [{
        "label": "Diluted",
        "value": 50.0,
        "page": income_page if diluted_page is None else diluted_page,
    }]
    if cash_flow_page is not None:
        entry["depreciation_amortization"] = [
            {"label": "Depreciation", "value": 80.0, "page": cash_flow_page},
        ]
        entry["cfo"] = [{"label": "Operating cash flow", "value": 300.0, "page": cash_flow_page}]
        entry["capex"] = [{"label": "Payments for property", "value": -100.0, "page": cash_flow_page}]
    return entry


def _answer(
    entry: dict[str, Any],
    *,
    units_printed: str,
    units_page: int,
    share_units_printed: str | None = None,
    share_units_page: int | None = None,
) -> dict[str, Any]:
    """A Pass 1 answer carrying `entry` and the two printed unit statements."""
    return {
        "ticker": "TST",
        "company_name": "Test Co",
        "units": {"printed": units_printed, "page": units_page},
        "share_units": {
            "printed": units_printed if share_units_printed is None else share_units_printed,
            "page": units_page if share_units_page is None else share_units_page,
        },
        "historical_years": [entry],
        "latest_balance_sheet": {},
    }


def _two_page_statement_pdf(
    path: Path, *, row_page: int, statement_page: int, statement: str = "(in millions)",
) -> bytes:
    """A PDF printing `statement` on `statement_page` and four rows on `row_page`.

    One page past the higher of the two is left blank, so no case below is refused for
    citing a page beyond the filing.
    """
    pages: list[list[str]] = [[] for _ in range(max(row_page, statement_page) + 1)]
    pages[statement_page - 1].append(statement)
    pages[row_page - 1].extend([
        "Net sales 1,000", "Operating income 200", "Consolidated net income 150", "Diluted 50",
    ])
    return write_text_pdf(path, pages).read_bytes()


def _units_failures(failures: list[Any]) -> list[Any]:
    """Only the failures the `units` statement produced."""
    return [f for f in failures if f.message.startswith("'units'")]


# ---------------------------------------------------------------------------
# 1. `_pages_and_page_before`: the rule itself, pure, no PDF and no I/O
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pages", "expected"),
    [
        # The rule: f(S) = S | {p - 1 for p in S if p > 1}. Each line is that
        # arithmetic done by hand.
        # f({}) = {} | {} = {}  -- nothing in, nothing out
        (set(), set()),
        # f({1}) = {1} | {}        = {1}       -- 1 is not > 1, so no predecessor
        ({1}, {1}),
        # f({2}) = {2} | {2-1}     = {1, 2}
        ({2}, {1, 2}),
        # f({1,2}) = {1,2} | {2-1} = {1, 2}    -- the predecessor is already there
        ({1, 2}, {1, 2}),
        # f({46}) = {46} | {46-1}  = {45, 46}  -- Walmart fiscal 2024
        ({46}, {45, 46}),
        # f({1,46}) = {1,46} | {45} = {1, 45, 46}
        ({1, 46}, {1, 45, 46}),
        # f({5,6,7}) = {5,6,7} | {4,5,6} = {4, 5, 6, 7}  -- three consecutive pages
        ({5, 6, 7}, {4, 5, 6, 7}),
        # f({3,10}) = {3,10} | {2,9}     = {2, 3, 9, 10} -- two separate statements
        ({3, 10}, {2, 3, 9, 10}),
        # f({2,100}) = {2,100} | {1,99}  = {1, 2, 99, 100}
        ({2, 100}, {1, 2, 99, 100}),
    ],
    ids=["empty", "page-1", "page-2", "1-and-2", "walmart-46", "1-and-46",
         "three-consecutive", "two-statements", "page-1-edge-and-far"],
)
def test_pages_and_page_before_is_each_page_and_its_predecessor(
    pages: set[int], expected: set[int],
) -> None:
    """Hand arithmetic: each page, plus the page before it when that page is not page 1."""
    assert _pages_and_page_before(pages) == expected


def test_pages_and_page_before_empty_set_allows_no_page() -> None:
    """Rule 3 in its set form: no page in means no page allowed, never a default.

    Hand arithmetic: f({}) = {} | {} = {}. The function does not fall back to "the page
    the statement cites" or to any other page, so an answer with no printed income row
    allows nothing and every citation of it is refused (locked below in
    `test_an_answer_with_no_income_rows_allows_no_page_and_the_statement_is_refused`).
    """
    assert _pages_and_page_before(set()) == set()
    assert len(_pages_and_page_before(set())) == 0


@pytest.mark.parametrize("page", list(range(1, 61)))
def test_pages_and_page_before_never_produces_page_zero(page: int) -> None:
    """Identity: a PDF's first page is page 1, so 0 is never a page and never allowed.

    For every page p >= 1, f({p}) = {p} | ({p-1} if p > 1 else {}). The guard `p > 1` is
    what keeps 0 out: without it f({1}) would be {0, 1}. Holds whatever p is, so the
    expected value needs no worked example.
    """
    result = _pages_and_page_before({page})
    assert 0 not in result
    assert min(result) >= 1
    # And the whole 1..60 range at once: still no page 0.
    whole = _pages_and_page_before(set(range(1, 61)))
    assert 0 not in whole
    assert min(whole) == 1


@pytest.mark.parametrize(
    "pages",
    [set(), {1}, {2}, {1, 2}, {7}, {3, 4, 5}, {1, 9, 40}, set(range(1, 12))],
    ids=["empty", "p1", "p2", "p1p2", "p7", "run", "scattered", "range"],
)
def test_pages_and_page_before_adds_at_most_the_predecessor_of_each_page(
    pages: set[int],
) -> None:
    """Closed-form identity, true for every input: S ⊆ f(S) ⊆ S ∪ {p-1 : p ∈ S, p > 1}.

    The lower bound says a page the figures are printed on is never taken away; the upper
    bound says nothing but a predecessor is ever added — in particular not p + 1, the page
    *after*, which would let a model cite a table printed below the statement it governs.
    """
    result = _pages_and_page_before(pages)
    predecessors = {p - 1 for p in pages if p > 1}
    assert pages <= result
    assert result <= pages | predecessors
    assert len(result) <= 2 * len(pages)
    # The page after is never admitted.
    assert not any(p + 1 in result for p in pages if p + 1 not in pages)


def test_pages_and_page_before_does_not_mutate_its_argument() -> None:
    """It is pure: the caller's set is the caller's, unchanged.

    `_unit_statement_pages_allowed` passes `income_pages` and then uses `diluted_pages`
    from the same answer; a function that widened its argument in place would make the
    second call depend on the first.
    """
    pages = {5, 6}
    before = set(pages)
    _pages_and_page_before(pages)
    assert pages == before


# ---------------------------------------------------------------------------
# 2. `_unit_statement_pages_allowed`: the rule applied to a whole answer
# ---------------------------------------------------------------------------


def test_units_allowed_is_the_income_pages_and_the_page_before_each() -> None:
    """Hand arithmetic on an answer whose income statement is split across a page break.

    income line pages: Net sales 46, Operating income 46, Consolidated net income 46,
                       Diluted 46                                      ->  {46}
    page before each:  46 - 1 = 45                                     ->  {45}
    union                                                              ->  {45, 46}
    """
    data = _answer(
        _year_entry(46), units_printed=WMT_INCOME_HEADER, units_page=45,
    )
    assert _unit_statement_pages_allowed(data)["units"] == {45, 46}


def test_units_allowed_ignores_the_cash_flow_statement_pages() -> None:
    """`_INCOME_STATEMENT_LINE_FIELDS` excludes the five cash-flow fields on purpose.

    income line pages: all four rows on page 46                        ->  {46}
    page before each:  45                                             ->  {45}
    union                                                              ->  {45, 46}
    The cash flow rows cite page 52, so neither 52 nor 51 may be cited by `units`: a
    statement heading the cash flow statement is not the income statement's unit.
    """
    data = _answer(
        _year_entry(46, cash_flow_page=52),
        units_printed=WMT_INCOME_HEADER, units_page=45,
    )
    allowed = _unit_statement_pages_allowed(data)["units"]
    assert allowed == {45, 46}
    assert 52 not in allowed
    assert 51 not in allowed


def test_share_units_widens_the_share_count_pages_but_not_the_units_page() -> None:
    """The P14g criterion-4 decision, stated as one assertion.

    A `diluted_shares` page is a **row** page — the page a figure is printed on — so the
    page before it is allowed. `data["units"]["page"]` is an already-resolved **statement**
    page, checked in its own right by the `units` row of this same check, so its
    predecessor is NOT added.

    Hand arithmetic, with income rows on 22, the diluted share count on 22, units on 20:
      share count pages              = {22}
      page before each               = {21}
      {units.page} | {21, 22}        = {20} | {21, 22} = {20, 21, 22}
    Page 19 — the page before the `units` page — must not appear. On Walmart's fiscal 2026
    filing that page prints `(Amounts in millions)` heading an Item 7A market-risk table.
    """
    data = _answer(_year_entry(22), units_printed="(Amounts in millions)", units_page=20)
    allowed = _unit_statement_pages_allowed(data)
    assert allowed["share_units"] == {20, 21, 22}
    assert 19 not in allowed["share_units"]
    # units itself: income pages {22}, page before {21} -> {21, 22}. Page 20 is the
    # statement page, not a figure page, so `units` may not cite it either.
    assert allowed["units"] == {21, 22}


def test_share_units_allowed_when_the_share_count_sits_on_its_own_page() -> None:
    """A diluted share count printed a page after the other income rows.

    income line pages: Net sales 30, Operating income 30, net income 30, Diluted 31
                                                                       ->  {30, 31}
    page before each:  29, 30                                          ->  {29, 30}
    units union                                                        ->  {29, 30, 31}
    share count pages                                                  ->  {31}
    page before each                                                   ->  {30}
    {units.page = 30} | {30, 31}                                       ->  {30, 31}
    """
    data = _answer(
        _year_entry(30, diluted_page=31), units_printed="(in millions)", units_page=30,
    )
    allowed = _unit_statement_pages_allowed(data)
    assert allowed["units"] == {29, 30, 31}
    assert allowed["share_units"] == {30, 31}


# ---------------------------------------------------------------------------
# 3. Rule 3 — every value the widened check reads stops when it is missing
# ---------------------------------------------------------------------------


def test_pages_allowed_stops_when_historical_years_is_missing() -> None:
    """Rule 3: no `historical_years` stops and names the field. It is not an empty list."""
    data = _answer(_year_entry(46), units_printed="(in millions)", units_page=45)
    del data["historical_years"]
    with pytest.raises(KeyError) as excinfo:
        _unit_statement_pages_allowed(data)
    assert "historical_years" in str(excinfo.value)


def test_pages_allowed_stops_when_an_income_field_is_missing_from_a_year() -> None:
    """Rule 3: an absent income field stops and names it; it is not read as `[]`.

    `[]` means "the filing prints no such row"; an absent key means the answer is the
    wrong shape, and the two must not look the same to the page check.
    """
    data = _answer(_year_entry(46), units_printed="(in millions)", units_page=45)
    del data["historical_years"][0]["operating_income"]
    with pytest.raises(KeyError) as excinfo:
        _unit_statement_pages_allowed(data)
    assert "operating_income" in str(excinfo.value)


def test_pages_allowed_stops_when_a_printed_line_has_no_page() -> None:
    """Rule 3: a printed row with no `page` stops and names `page`.

    A row with no page cannot widen anything: there is no page to take the predecessor of.
    """
    data = _answer(_year_entry(46), units_printed="(in millions)", units_page=45)
    del data["historical_years"][0]["revenue"][0]["page"]
    with pytest.raises(KeyError) as excinfo:
        _unit_statement_pages_allowed(data)
    assert "page" in str(excinfo.value)


def test_pages_allowed_stops_when_the_units_statement_is_missing() -> None:
    """Rule 3: `share_units`'s allowed set is built from `data["units"]["page"]`.

    With no `units`, the check stops and names it rather than allowing the share
    statement anywhere.
    """
    data = _answer(_year_entry(46), units_printed="(in millions)", units_page=45)
    del data["units"]
    with pytest.raises(KeyError) as excinfo:
        _unit_statement_pages_allowed(data)
    assert "units" in str(excinfo.value)


def test_pages_allowed_stops_when_the_units_statement_has_no_page() -> None:
    """Rule 3: `units` without a `page` stops and names `page`."""
    data = _answer(_year_entry(46), units_printed="(in millions)", units_page=45)
    del data["units"]["page"]
    with pytest.raises(KeyError) as excinfo:
        _unit_statement_pages_allowed(data)
    assert "page" in str(excinfo.value)


def test_an_answer_with_no_income_rows_allows_no_page_and_the_statement_is_refused(
    tmp_path: Path,
) -> None:
    """Rule 3: nothing to govern means no page is allowed, and the run stops.

    Hand arithmetic: with every income field `[]`, the income line pages are `{}` and
    f({}) = {}. There is no fallback to the page the statement cites, so the `units`
    statement is refused and the printed list of allowed pages is the empty list.
    `share_units`'s set is `{units.page} | f({}) = {2}`, so the share statement on page 2
    is still allowed and still found — exactly one failure, and it names `units`.
    """
    entry: dict[str, Any] = {"year": 2024}
    for field in PASS1_YEAR_FIELDS:
        if field != "year":
            entry[field] = []
    data = _answer(entry, units_printed="(in millions)", units_page=2)
    pdf = write_text_pdf(
        tmp_path / "nothing.pdf", [["Cover"], ["(in millions)"], []],
    ).read_bytes()

    failures = _unit_statement_failures(data, pdf)

    assert len(failures) == 1
    message = failures[0].message
    assert message.startswith("'units'")
    assert "the pages allowed are []" in message
    assert "cites page 2" in message


def test_a_newly_allowed_page_with_no_text_layer_is_not_confirmed(tmp_path: Path) -> None:
    """Rule 3: the widening must not let an unreadable page through as "allowed".

    Before P14g every allowed page had a figure printed on it, so it always had a text
    layer. The page before the figures need not: it can be a blank page or a scanned
    image. Hand arithmetic: rows on page 3, so allowed = {3} | {2} = {2, 3}; page 2 IS
    allowed, and page 2 of this PDF carries no text at all. The check must say the
    statement cannot be confirmed and name the page, not take "allowed" for "found".

    `share_units` cites page 3, which prints the statement, so it passes: one failure.
    """
    pdf = write_text_pdf(tmp_path / "blank_before.pdf", [
        ["Cover"],
        [],
        ["(in millions)", "Net sales 1,000", "Operating income 200",
         "Consolidated net income 150", "Diluted 50"],
    ]).read_bytes()
    data = _answer(
        _year_entry(3), units_printed="(in millions)", units_page=2,
        share_units_printed="(in millions)", share_units_page=3,
    )
    assert _unit_statement_pages_allowed(data)["units"] == {2, 3}

    failures = _unit_statement_failures(data, pdf)

    assert len(failures) == 1
    message = failures[0].message
    assert message.startswith("'units'")
    assert "cannot be confirmed, because page 2 has no text layer; it was not looked for" in message


def test_an_allowed_page_beyond_the_filing_is_refused(tmp_path: Path) -> None:
    """Rule 3: being inside the allowed set is not the same as being inside the PDF.

    Hand arithmetic: a model that cites page 50 for every income row makes the allowed
    set {50} | {49} = {49, 50}, so page 50 passes the first test — and the PDF has three
    pages. Both statements cite page 50, so both are refused and both messages give the
    filing's real page count.
    """
    pdf = write_text_pdf(tmp_path / "short.pdf", [
        ["Cover"], ["(in millions)"], ["Net sales 1,000"],
    ]).read_bytes()
    data = _answer(_year_entry(50), units_printed="(in millions)", units_page=50)
    assert _unit_statement_pages_allowed(data)["units"] == {49, 50}

    failures = _unit_statement_failures(data, pdf)

    assert len(failures) == 2
    assert {f.message.split(" ")[0] for f in failures} == {"'units'", "'share_units'"}
    for failure in failures:
        assert "cites page 50, but the PDF has 3 pages" in failure.message


# ---------------------------------------------------------------------------
# 4. The two checks read one rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("row_page", "statement_page", "accepted"),
    [
        # Hand arithmetic, f(S) = S | {p-1 for p in S if p > 1}, applied to the one page
        # the rows cite. A statement page is accepted exactly when it is in f({row_page}).
        # f({1}) = {1}
        (1, 1, True),
        # f({2}) = {1, 2}
        (2, 1, True),
        (2, 2, True),
        (2, 3, False),
        # f({3}) = {2, 3}
        (3, 1, False),
        (3, 2, True),
        (3, 3, True),
        (3, 4, False),
        # f({6}) = {5, 6}
        (6, 4, False),
        (6, 5, True),
        (6, 6, True),
        (6, 7, False),
    ],
    ids=["p1-on-1", "p2-on-1", "p2-on-2", "p2-on-3", "p3-on-1", "p3-on-2", "p3-on-3",
         "p3-on-4", "p6-on-4", "p6-on-5", "p6-on-6", "p6-on-7"],
)
def test_both_unit_scale_checks_accept_the_same_statement_pages(
    tmp_path: Path, row_page: int, statement_page: int, accepted: bool,
) -> None:
    """P14g's whole objective: the unit statement check and check B1 hold ONE rule.

    The same PDF and the same answer are put through both checks. `(in millions)` is
    printed on `statement_page` and the four rows on `row_page`, so the only thing that
    can differ between the two checks is where each believes a unit statement may sit.

    If `_unit_statement_pages_allowed` is given its own, narrower rule again, the
    `p2-on-1`, `p3-on-2` and `p6-on-5` cases go red on the first assertion. If B1's
    `pages_to_check` loses the page before, the same three go red on the second. A later
    edit that moves one check and not the other cannot leave this test green.
    """
    pdf = _two_page_statement_pdf(
        tmp_path / "split.pdf", row_page=row_page, statement_page=statement_page,
    )
    data = _answer(
        _year_entry(row_page), units_printed="(in millions)", units_page=statement_page,
    )

    unit_statement_accepted = _units_failures(_unit_statement_failures(data, pdf)) == []

    b1_failures = _row_scale_failures(data, pdf)
    b1_money = [f for f in b1_failures if f.message.startswith(f"page {row_page} (money figures)")]
    b1_accepted = b1_money == []

    assert unit_statement_accepted is accepted
    assert b1_accepted is accepted
    assert unit_statement_accepted == b1_accepted


def test_check_b1_refusal_names_the_two_pages_it_looked_at(tmp_path: Path) -> None:
    """The rule the two checks share is visible in B1's message too.

    Rows on page 3, the statement two pages before on page 1. f({3}) = {2, 3}, so B1 looks
    at pages 3 and 2 and says so. One failure per (page, kind): money figures and share
    count, both for page 3 — two in all, derived from the documented shape of the message
    ("one failure per page and kind"), not from a run.
    """
    pdf = _two_page_statement_pdf(tmp_path / "far.pdf", row_page=3, statement_page=1)
    data = _answer(_year_entry(3), units_printed="(in millions)", units_page=1)

    failures = _row_scale_failures(data, pdf)

    assert len(failures) == 2
    money = [f for f in failures if "(money figures)" in f.message]
    assert len(money) == 1
    assert "no unit statement on page 3 or 2" in money[0].message


def test_both_checks_read_the_one_function_that_holds_the_rule() -> None:
    """The rule is written once, in source, not twice with the same value.

    The behavioural test above cannot tell one rule from two identical copies of it, and
    two copies are exactly how item 114 happened: B1 gained "the page before" in
    P14b-note-figures and the unit statement check did not. So this asserts the shape as
    well: both of B1's page lines (`pages_to_read` and `pages_to_check`) and
    `_unit_statement_pages_allowed` read `_pages_and_page_before`, and the allowed-pages
    function spells no page arithmetic of its own.
    """
    allowed_source = inspect.getsource(_unit_statement_pages_allowed)
    b1_source = inspect.getsource(_row_scale_failures)

    assert allowed_source.count("_pages_and_page_before(") >= 1
    # `pages_to_read` (every page B1 opens) and `pages_to_check` (the pages of one row).
    assert b1_source.count("_pages_and_page_before(") >= 2

    allowed_body = allowed_source.replace(_unit_statement_pages_allowed.__doc__ or "", "")
    assert "- 1" not in allowed_body, (
        "`_unit_statement_pages_allowed` is spelling the page-before rule itself again; "
        "it must read `_pages_and_page_before`, which is the one place that rule lives."
    )


# ---------------------------------------------------------------------------
# 5. The real Walmart fiscal 2024 filing — the case the unit exists for
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not WMT_2024.found, reason=WMT_2024.skip_reason)
def test_walmart_fiscal_2024_splits_its_income_statement_across_a_page_break() -> None:
    """The fact the whole unit rests on, read off the filing with `pdfplumber`.

    Expected values read from `10K_filings/WMT/Walmart Inc._10-K_2024-01-31_English.pdf`:
      - PDF page 45's last four text lines are the statement's title block, ending
        `(Amounts in millions, except per share data) 2024 2023 2022`;
      - PDF page 45 prints no figure of the statement: `Net sales` is not on it;
      - PDF page 46's second text line is `Net sales $ 642,637 $ 605,881 $ 567,762`;
      - PDF page 45's only scale statement is `(Amounts in millions, except per share
        data)`, and PDF page 46's only one is `(Amounts in millions)` — the Comprehensive
        Income header, a different statement.
    """
    import pdfplumber

    with pdfplumber.open(WMT_2024.path) as pdf:
        assert len(pdf.pages) == 147
        page_45 = pdf.pages[WMT_HEADER_PAGE - 1].extract_text() or ""
        page_46 = pdf.pages[WMT_FIGURE_PAGE - 1].extract_text() or ""

    lines_45 = [line for line in page_45.splitlines() if line.strip()]
    assert lines_45[-4:] == [
        "Walmart Inc.",
        "Consolidated Statements of Income",
        "Fiscal Years Ended January 31,",
        "(Amounts in millions, except per share data) 2024 2023 2022",
    ]
    assert "Net sales" not in page_45
    assert "Net sales $ 642,637 $ 605,881 $ 567,762" in page_46

    def scale_groups(text: str) -> list[str]:
        normalised = " ".join(text.split())
        return [
            group for group in _PARENTHESISED.findall(normalised)
            if any(word in group.casefold() for word in ("thousand", "million", "billion"))
        ]

    assert scale_groups(page_45) == [WMT_INCOME_HEADER]
    assert scale_groups(page_46) == ["(Amounts in millions)"]


@pytest.mark.skipif(not WMT_2024.found, reason=WMT_2024.skip_reason)
def test_walmart_fiscal_2024_header_on_the_page_before_its_figures_is_accepted() -> None:
    """The defect item 114 names: this correct reading stopped the run before P14g.

    Every income statement row cites PDF page 46, so by hand
      income line pages {46}; page before 46 - 1 = 45; allowed = {45, 46},
    and `(Amounts in millions, except per share data)` is printed on page 45 as one whole
    parenthesised group (asserted against the PDF in the test above). `share_units` cites
    the same page: {units.page = 45} | f({46}) = {45} | {45, 46} = {45, 46}. So neither
    statement has anything to fail on and the check returns no failure at all.
    """
    data = _answer(
        _year_entry(WMT_FIGURE_PAGE),
        units_printed=WMT_INCOME_HEADER, units_page=WMT_HEADER_PAGE,
    )
    allowed = _unit_statement_pages_allowed(data)
    assert allowed["units"] == {45, 46}
    assert allowed["share_units"] == {45, 46}

    assert _unit_statement_failures(data, WMT_2024.read_bytes()) == []


@pytest.mark.skipif(not WMT_2024.found, reason=WMT_2024.skip_reason)
def test_walmart_fiscal_2024_the_newly_allowed_page_is_still_checked() -> None:
    """A widening that stopped checking the text would be worthless.

    Page 45 is allowed by hand ({46} | {45}), but the only scale statement printed on it
    is `(Amounts in millions, except per share data)`. `(Amounts in millions)` is the
    Comprehensive Income header on page 46, and `unit_statement_on_page` compares whole
    parenthesised groups, so citing it against page 45 is refused for the second reason —
    the text is not printed there — not the first.
    """
    data = _answer(
        _year_entry(WMT_FIGURE_PAGE),
        units_printed="(Amounts in millions)", units_page=WMT_HEADER_PAGE,
        share_units_printed=WMT_INCOME_HEADER, share_units_page=WMT_HEADER_PAGE,
    )

    failures = _unit_statement_failures(data, WMT_2024.read_bytes())

    assert len(failures) == 1
    message = failures[0].message
    assert message.startswith("'units'")
    assert "was not found on page 45, the page it cites, as a whole printed statement" in message
    # It is NOT refused for citing a page outside the allowed set: page 45 is allowed.
    assert "is not a page of the figures" not in message


@pytest.mark.skipif(not WMT_2024.found, reason=WMT_2024.skip_reason)
@pytest.mark.parametrize(
    ("printed", "page", "expected_reason"),
    [
        # allowed = f({46}) = {45, 46}. 44 is two pages before the figures.
        # Page 44 of this filing prints no scale statement at all, so a model citing it
        # is reaching for a statement that is not there.
        (WMT_INCOME_HEADER, 44,
         ("cites page 44, which is not a page of the figures it states the unit of: "
          "the pages allowed are [45, 46]")),
        # 47 is the page AFTER the figures: the balance sheet's header, a different
        # statement. f never adds p + 1.
        ("(Amounts in millions)", 47,
         ("cites page 47, which is not a page of the figures it states the unit of: "
          "the pages allowed are [45, 46]")),
        # 46 IS allowed, but page 46 prints `(Amounts in millions)` and nothing else;
        # `(in thousands)` is printed nowhere on it.
        ("(in thousands)", 46,
         "was not found on page 46, the page it cites, as a whole printed statement"),
    ],
    ids=["two-pages-before", "the-page-after", "text-not-printed-there"],
)
def test_walmart_fiscal_2024_refusals_that_must_survive_the_widening(
    printed: str, page: int, expected_reason: str,
) -> None:
    """Three refusals, each with the reason it is refused, on the real filing.

    `share_units` is pinned to the correct citation in every case, so the one failure is
    the `units` one under test.
    """
    data = _answer(
        _year_entry(WMT_FIGURE_PAGE),
        units_printed=printed, units_page=page,
        share_units_printed=WMT_INCOME_HEADER, share_units_page=WMT_HEADER_PAGE,
    )

    failures = _unit_statement_failures(data, WMT_2024.read_bytes())

    assert len(failures) == 1
    message = failures[0].message
    assert message.startswith("'units'")
    assert expected_reason in message


@pytest.mark.skipif(not WMT_2024.found, reason=WMT_2024.skip_reason)
def test_walmart_fiscal_2024_share_units_two_pages_before_is_refused() -> None:
    """`share_units` is widened by exactly one page too, and no further.

    Hand arithmetic: diluted share count pages {46}; page before 45; `units` page 45.
      share_units allowed = {45} | {45, 46} = {45, 46}
    Page 44 is outside it, and the message names the rule that produced the set.
    """
    data = _answer(
        _year_entry(WMT_FIGURE_PAGE),
        units_printed=WMT_INCOME_HEADER, units_page=WMT_HEADER_PAGE,
        share_units_printed=WMT_INCOME_HEADER, share_units_page=44,
    )

    failures = _unit_statement_failures(data, WMT_2024.read_bytes())

    assert len(failures) == 1
    message = failures[0].message
    assert message.startswith("'share_units'")
    assert "cites page 44" in message
    assert "the pages allowed are [45, 46]" in message
    assert (
        "the 'units' page, the pages the diluted share count's printed lines cite, and "
        "the page before each of those"
    ) in message


@pytest.mark.skipif(not WMT_2024.found, reason=WMT_2024.skip_reason)
def test_walmart_fiscal_2024_refusal_message_states_the_rule_it_applied() -> None:
    """A refusal has to tell the model what it may cite, or the retry is a guess.

    The words come from the rule, not from a run: `units` may cite the pages the income
    statement's printed lines cite, **and the page before each of them**.
    """
    data = _answer(
        _year_entry(WMT_FIGURE_PAGE),
        units_printed=WMT_INCOME_HEADER, units_page=44,
        share_units_printed=WMT_INCOME_HEADER, share_units_page=WMT_HEADER_PAGE,
    )

    failures = _unit_statement_failures(data, WMT_2024.read_bytes())

    assert len(failures) == 1
    for text in (failures[0].message, failures[0].retry_message):
        assert (
            "the pages the income statement's printed lines cite, and the page before "
            "each of them"
        ) in text
