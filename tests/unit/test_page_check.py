"""The page check (`P12a-printed-pages`): each Pass 1 printed line on the page it cites.

One group per item of `.agent/assignments/P12a-tests.md`, "What to do", 2 to 6:

  2. the rule, `printed_line_on_page`, case by case;
  3. the walk, on PDFs written here: every outcome, every field, each page once;
  4. route B: `check`'s exit codes and wording;
  5. route A: the check retry, with `_call_llm` stubbed;
  6. the F7 attack end to end: a balance sheet that balances because one row was
     invented, which the balance check passes and the page check does not.

**Where every expected value comes from.** The rule's cases are derived by hand
from the rule as `docs/3-architecture/extraction.md`, "The page check", states it
(steps 1 to 4), before the code was run; each case carries its derivation. The
walk's expected failures are the rows each test leaves off the page it writes. The
parts a message must name are the ones the P12a assignment requires ("where, the
field, the line index, the label, the value and the page"). **No expected value
here was read off the code's output.**

**What is deliberately not tested.** Backlog item 64 (a label written across two
printed rows) has no decided fix, so no case here asserts either outcome for it;
every wrapped-label case below has figures on one half only, so the candidate fix
recorded on item 64 would leave them as they are. Backlog item 63 (route A
retrying lines on a page with no text layer) is not locked either: the no-text-layer
outcome is tested through the walk and route B only.

**No test reaches the API or the network.** `_call_llm` is replaced by a function
that raises, and the route A tests replace it with a scripted stub. Every PDF is
written under `tmp_path`; nothing reads `10K_filings/` or `extractions/`.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
from pdfplumber.utils.exceptions import PdfminerException

import ingestion.claude_extractor as ce
from ingestion.claude_extractor import (
    Pass1ShapeError,
    ProviderResolution,
    printed_line_on_page,
    printed_line_page_failures,
)
from ingestion.session_extraction import cmd_check, load_session_extraction
from tests.unit._pass1_pdf import write_pass1_pdf
from tests.unit._printed_lines import lines
from tests.unit._session_route_helpers import session_dict, write_session
from tests.unit._text_pdf import write_text_pdf

TICKER = "TST"
COMPANY = "Test Co"


@pytest.fixture(autouse=True)
def _no_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Close the API boundary. A route A test stubs it again."""

    def _refuse(*args: object, **kwargs: object) -> tuple[str, int, int]:
        raise AssertionError("a page-check test reached _call_llm")

    monkeypatch.setattr(ce, "_call_llm", _refuse)


# ===========================================================================
# 2. The rule, by hand
# ===========================================================================
#
# The rule (extraction.md, "The page check"):
#   1. a figure: optional "(", optional "$" and spaces, digits with optional
#      thousands commas, optional decimals, optional ")"; its magnitude drops the
#      rest. A dash standing alone is a printed zero.
#   2. a text line holds the value when one figure's magnitude is abs(value); 0 is
#      held by a figure 0 or a standalone dash.
#   3. normalised: figures removed, casefolded, each run of non-letters-non-digits
#      one space, stripped; label and page alike.
#   4. found: some line L holds the value and the normalised label (not empty) is
#      inside L; or inside (line above + " " + L) when the line above alone does
#      not hold the whole label; or inside (L + " " + line below) likewise.

RULE_CASES = [
    # --- the label and the figure on one line; "$", commas, parentheses -------
    pytest.param(
        # "$ 284,668" is a figure of magnitude 284668 = abs(284668): L holds it.
        # L normalised: figures removed -> "Total assets" -> "total assets" = label.
        "Total assets", 284668, "Total assets $ 284,668 $ 260,823", True,
        id="dollar sign and commas"),
    pytest.param(
        # "$   9,037": "$" with several spaces is still one figure, 9037.
        "Cash and cash equivalents", 9037,
        "Cash and cash equivalents $   9,037 $ 9,867", True,
        id="dollar sign with several spaces"),
    pytest.param(
        # "(26,642)" has magnitude 26642; the sign of -26642 is not compared.
        "Payments for property and equipment", -26642,
        "Payments for property and equipment (26,642) (20,606)", True,
        id="parentheses, negative value"),
    pytest.param(
        # The same line, the value positive: still magnitude 26642.
        "Payments for property and equipment", 26642,
        "Payments for property and equipment (26,642) (20,606)", True,
        id="parentheses, positive value"),
    pytest.param(
        # Commas are optional (step 1): "26642" has magnitude 26642.
        "Capex", 26642, "Capex 26642", True,
        id="no thousands comma"),
    pytest.param(
        # A decimal part: "$ 2.50" has magnitude 2.5.
        "Diluted earnings per share", 2.5,
        "Diluted earnings per share $ 2.50 $ 2.41", True,
        id="decimal figure"),
    pytest.param(
        # The label is on the page, the figure is not: 260,823 and 284,668 only.
        "Total assets", 284000, "Total assets $ 284,668 $ 260,823", False,
        id="label printed, figure not"),
    pytest.param(
        # The figure is printed, the label is not ("capex" is not in the line).
        "Capex", 26642, "Payments for property and equipment (26,642)", False,
        id="figure printed, label not"),
    # --- a curly apostrophe against a straight one ------------------------------
    pytest.param(
        # "’" and "'" are both neither letter nor digit: each becomes a space, so
        # both sides normalise to "total stockholders equity".
        "Total stockholders' equity", 105887, "Total stockholders’ equity 105,887", True,
        id="straight label, curly page"),
    pytest.param(
        "Total stockholders’ equity", 105887, "Total stockholders' equity 105,887", True,
        id="curly label, straight page"),
    # --- a label that prints a year ---------------------------------------------
    pytest.param(
        # "2030" is a figure (digits), removed from the label and from L:
        # both "senior notes due". L holds 500.
        "Senior notes due 2030", 500, "Senior notes due 2030 500 450", True,
        id="year in the label"),
    pytest.param(
        # Step 3 drops the year on both sides, so the label's 2030 is not compared
        # with the page's 2031: both normalise to "senior notes due". L holds 500.
        "Senior notes due 2030", 500, "Senior notes due 2031 500 450", True,
        id="year compared without the year"),
    pytest.param(
        # The year does not stand in for the value: 501 is not on the line.
        "Senior notes due 2030", 501, "Senior notes due 2030 500 450", False,
        id="year in the label, value absent"),
    # --- a value of 0 ------------------------------------------------------------
    pytest.param("Other", 0, "Other —", True, id="zero, em dash"),
    pytest.param("Other", 0, "Other –", True, id="zero, en dash"),
    pytest.param("Other", 0, "Other -", True, id="zero, hyphen"),
    pytest.param("Other", 0, "Other 0", True, id="zero, printed 0"),
    pytest.param(
        # No figure and no dash: nothing on the line holds 0.
        "Other", 0, "Other", False, id="zero, no dash"),
    pytest.param(
        # "Other—" is one whitespace token: the dash does not stand alone.
        "Other", 0, "Other—", False, id="zero, dash not standing alone"),
    pytest.param(
        # A figure of 5 does not hold 0.
        "Other", 0, "Other 5", False, id="zero against a figure"),
    # --- a figure that only matches in another magnitude: not found ---------------
    pytest.param(
        # "2,664.2" is one figure of magnitude 2664.2, not 26642.
        "Capex", 26642, "Capex 2,664.2", False, id="a tenth of the magnitude"),
    pytest.param(
        # "266,420" has magnitude 266420.
        "Capex", 26642, "Capex 266,420", False, id="ten times the magnitude"),
    pytest.param(
        # "26.642" has magnitude 26.642.
        "Capex", 26642, "Capex 26.642", False, id="decimal point for a comma"),
    pytest.param(
        "Capex", 26642, "Capex 26,643", False, id="one off"),
    # --- a wrapped label: found ----------------------------------------------------
    pytest.param(
        # Figures on the FIRST half. L = line 0 holds 53. L alone normalises to
        # "payments for business acquisitions net of cash": not the label. The
        # line below, "acquired", does not hold the whole label, so L + " " +
        # below counts: "payments for business acquisitions net of cash acquired".
        "Payments for business acquisitions, net of cash acquired", 53,
        "Payments for business acquisitions, net of cash (53) (12)\nacquired", True,
        id="wrapped label, figures on the first half"),
    pytest.param(
        # Figures on the SECOND half. L = line 1 holds 53. The line above does not
        # hold the whole label, so above + " " + L counts, normalised as above.
        "Payments for business acquisitions, net of cash acquired", -53,
        "Payments for business acquisitions,\nnet of cash acquired (53) (12)", True,
        id="wrapped label, figures on the second half"),
    pytest.param(
        # A label two lines away is not joined: only the line above or below is.
        # L = "Other 5" holds 5; L alone "other", above "cost of sales": no
        # "revenue" in either form, and line 0 is two away.
        "Revenue", 5, "Revenue 100\nCost of sales 60\nOther 5", False,
        id="label two lines from the figure"),
    # --- F1: a label printed whole on the neighbouring row: not found ----------------
    pytest.param(
        # L = "Total current assets 84,874 79,458" holds 84874. L alone: "total
        # current assets", no label. The line above holds the whole label on its
        # own, so above + L does not count. No line below. Not found.
        "Prepaid expenses and other", 84874,
        "Inventories 58,851 56,435\nPrepaid expenses and other 4,124 4,011\n"
        "Total current assets 84,874 79,458", False,
        id="F1, the row below's figure"),
    pytest.param(
        # L = "Inventories 58,851 56,435" holds 58851. L alone: "inventories". The
        # line below holds the whole label, so L + below does not count.
        "Prepaid expenses and other", 58851,
        "Inventories 58,851 56,435\nPrepaid expenses and other 4,124 4,011\n"
        "Total current assets 84,874 79,458", False,
        id="F1, the row above's figure"),
    pytest.param(
        # L = the prepaid line, holds 4124. L alone: no "inventories". Above holds
        # "inventories" whole: refused. Below: "total current assets" lacks it,
        # so L + below counts, "prepaid expenses and other total current assets":
        # no "inventories". Not found.
        "Inventories", 4124,
        "Inventories 58,851 56,435\nPrepaid expenses and other 4,124 4,011\n"
        "Total current assets 84,874 79,458", False,
        id="F1, a label above takes the next row's figure"),
    pytest.param(
        # Control on the same page: the row's own figure, L alone.
        "Prepaid expenses and other", 4124,
        "Inventories 58,851 56,435\nPrepaid expenses and other 4,124 4,011\n"
        "Total current assets 84,874 79,458", True,
        id="F1 control, own figure"),
    pytest.param(
        "Inventories", 58851,
        "Inventories 58,851 56,435\nPrepaid expenses and other 4,124 4,011\n"
        "Total current assets 84,874 79,458", True,
        id="F1 control, first row"),
    pytest.param(
        "Total current assets", 84874,
        "Inventories 58,851 56,435\nPrepaid expenses and other 4,124 4,011\n"
        "Total current assets 84,874 79,458", True,
        id="F1 control, last row"),
    # --- an empty normalised label: never found ----------------------------------------
    pytest.param(
        # "2030" is a figure: removed, the label is "". The page holds 2030.
        "2030", 2030, "2030 2030", False, id="label only a year"),
    pytest.param(
        # "(1,234)" is a figure: removed, "".
        "(1,234)", 1234, "Total (1,234)", False, id="label only a figure"),
    pytest.param(
        # "$ 5" is a figure: removed, "".
        "$ 5", 5, "$ 5", False, id="label only a dollar figure"),
    pytest.param(
        # "—" is neither letter nor digit: a space, stripped, "". The page holds 0.
        "—", 0, "Other —", False, id="label only a dash"),
]


@pytest.mark.parametrize(("label", "value", "page_text", "expected"), RULE_CASES)
def test_printed_line_on_page_by_hand(
    label: str, value: float, page_text: str, expected: bool,
) -> None:
    assert printed_line_on_page(label, value, page_text) is expected


# ===========================================================================
# Builders for the walk: a Pass 1 answer whose every field holds one printed row
# ===========================================================================
#
# The field lists are written by hand from the Pass 1 schema
# (docs/3-architecture/extraction.md; the keys test_session_extraction.py also
# writes out), then checked against the exported tuples, so a field the walk
# should visit cannot drop out of the loop below unnoticed.

YEAR_LINE_FIELDS = (
    "revenue", "cost_of_revenue", "gross_profit", "sga", "rd_expense",
    "depreciation_amortization", "other_operating_expense", "operating_income",
    "interest_expense", "interest_income", "other_non_operating", "tax_expense",
    "net_income", "diluted_shares", "cfo", "capex", "sbc", "change_in_working_capital",
)
BALANCE_SHEET_LINE_FIELDS = (
    "cash", "short_term_investments", "accounts_receivable", "inventory",
    "other_current_assets", "ppe_net", "goodwill", "intangible_assets",
    "other_non_current_assets", "accounts_payable", "accrued_liabilities",
    "other_current_liabilities", "short_term_debt", "long_term_debt",
    "other_non_current_liabilities", "total_equity",
    "noncontrolling_interest_nonredeemable", "noncontrolling_interest_redeemable",
    "total_assets", "total_liabilities_and_equity",
)
# Five check rows and two memos, named by the assignment as walked like the rest.
CHECK_ROWS = ("gross_profit", "operating_income", "net_income",
              "total_assets", "total_liabilities_and_equity")
NCI_MEMOS = ("noncontrolling_interest_nonredeemable", "noncontrolling_interest_redeemable")

INCOME_PAGE, BALANCE_PAGE = 1, 2
UNPRINTED = "Unprinted row label"


def test_the_walked_field_lists_are_the_schema() -> None:
    # 18 line fields a year, 20 in the balance sheet (19 and 21 keys, less "year").
    assert len(YEAR_LINE_FIELDS) == 18
    assert len(BALANCE_SHEET_LINE_FIELDS) == 20
    assert ce.PASS1_YEAR_LINE_FIELDS == YEAR_LINE_FIELDS
    assert ce.PASS1_BALANCE_SHEET_LINE_FIELDS == BALANCE_SHEET_LINE_FIELDS
    assert set(CHECK_ROWS) | set(NCI_MEMOS) <= set(YEAR_LINE_FIELDS + BALANCE_SHEET_LINE_FIELDS)


def full_answer(year: int = 2024) -> dict[str, Any]:
    """Every line field one printed row, label = field name. Values 101, 102, ... for
    the year and 201, 202, ... for the balance sheet, so no two rows share a figure.
    Nothing here reconciles: the walk does no arithmetic, it looks rows up. The NCI
    memos carry a row too (209 + 8 = 217 and 218), so they are walked."""
    entry: dict[str, Any] = {"year": year}
    for i, field in enumerate(YEAR_LINE_FIELDS):
        entry[field] = lines(field, [101 + i], page=INCOME_PAGE)
    balance: dict[str, Any] = {"year": year}
    for i, field in enumerate(BALANCE_SHEET_LINE_FIELDS):
        balance[field] = lines(field, [201 + i], page=BALANCE_PAGE)
    return {
        "ticker": TICKER,
        "company_name": COMPANY,
        "currency": "USD",
        "units": {"printed": "(in millions)", "page": INCOME_PAGE},
        "share_units": {"printed": "(in millions)", "page": INCOME_PAGE},
        "historical_years": [entry],
        "latest_balance_sheet": balance,
    }


def failures(answer: dict[str, Any], pdf: Path) -> list[str]:
    return printed_line_page_failures(json.dumps(answer), pdf.read_bytes())


def one_line_names(messages: list[str], *parts: str) -> bool:
    return any(all(part in line for part in parts)
               for message in messages for line in message.splitlines())


# ===========================================================================
# 3. The walk, with real PDFs
# ===========================================================================

def test_every_row_printed_on_its_page_gives_no_failure(tmp_path: Path) -> None:
    answer = full_answer()
    pdf = write_pass1_pdf(tmp_path / "f.pdf", answer)
    assert failures(answer, pdf) == []


@pytest.mark.parametrize(
    ("field", "where"),
    [(f, "year 2024") for f in YEAR_LINE_FIELDS]
    + [(f, "balance sheet 2024") for f in BALANCE_SHEET_LINE_FIELDS],
)
def test_every_line_field_is_walked(tmp_path: Path, field: str, where: str) -> None:
    """One field's row relabelled to a label the PDF does not print: exactly one
    failure, naming that field, where, line 0 and the label. The PDF prints the
    unchanged answer, so every other row is found."""
    printed = full_answer()
    pdf = write_pass1_pdf(tmp_path / "f.pdf", printed)
    answer = full_answer()
    block = (answer["historical_years"][0] if where.startswith("year")
             else answer["latest_balance_sheet"])
    block[field][0]["label"] = UNPRINTED
    found = failures(answer, pdf)
    assert len(found) == 1, found
    assert one_line_names(found, where, f"'{field}'", "line 0", UNPRINTED), found


def test_the_line_index_is_the_rows_own(tmp_path: Path) -> None:
    # capex as two rows; the second (index 1) is not printed.
    printed = full_answer()
    printed["historical_years"][0]["capex"] = lines("capex", [70, 30], page=INCOME_PAGE)
    pdf = write_pass1_pdf(tmp_path / "f.pdf", printed)
    answer = json.loads(json.dumps(printed))
    answer["historical_years"][0]["capex"][1]["label"] = UNPRINTED
    found = failures(answer, pdf)
    assert len(found) == 1, found
    assert one_line_names(found, "year 2024", "'capex'", "line 1", UNPRINTED), found


def test_every_year_is_walked(tmp_path: Path) -> None:
    # Two years; the row unprinted is in the second, so "year 2023" can only
    # come from that entry.
    printed = full_answer(2024)
    older = full_answer(2023)["historical_years"][0]
    printed["historical_years"].append(older)
    pdf = write_pass1_pdf(tmp_path / "f.pdf", printed)
    answer = json.loads(json.dumps(printed))
    answer["historical_years"][1]["sga"][0]["label"] = UNPRINTED
    found = failures(answer, pdf)
    assert len(found) == 1, found
    assert one_line_names(found, "year 2023", "'sga'", "line 0", UNPRINTED), found


def test_not_found_names_where_field_line_label_value_and_page(tmp_path: Path) -> None:
    # Page 2 prints "Prepaid expenses and other 4,124"; the answer cites
    # "Other current assets" = 4,124 on page 2. Not found.
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["net_income 228"], ["Prepaid expenses and other 4,124"],
    ])
    answer = minimal_answer(
        balance_rows={"other_current_assets": [
            {"label": "Other current assets", "value": 4124, "page": 2}]},
    )
    found = failures(answer, pdf)
    assert len(found) == 1, found
    (message,) = found
    for part in ("balance sheet 2024", "'other_current_assets'", "line 0",
                 "Other current assets", "page 2"):
        assert part in message, (part, message)
    # The value, written with or without its thousands comma.
    assert re.search(r"4,?124", message), message


def test_a_page_beyond_the_last_names_both_page_numbers(tmp_path: Path) -> None:
    # A PDF of 4 pages; the row cites page 11. Neither 4 nor 11 is a value, a
    # year or a line index in this answer (values 228 and 77; year 2024; line 0).
    pdf = write_text_pdf(tmp_path / "f.pdf", [
        ["net_income 228"], ["cash 77"], [], [],
    ])
    answer = minimal_answer(balance_rows={"cash": [
        {"label": "cash", "value": 77, "page": 11}]})
    found = failures(answer, pdf)
    assert len(found) == 1, found
    (message,) = found
    assert "'cash'" in message and "line 0" in message
    assert re.search(r"\b11\b", message), message
    assert re.search(r"\b4\b", message), message


@pytest.mark.parametrize("blank_page", [[], ["   "]], ids=["no text", "only spaces"])
def test_a_page_with_no_text_layer_is_a_failure_that_cannot_be_confirmed(
    tmp_path: Path, blank_page: list[str],
) -> None:
    # Page 2 prints nothing (or only spaces); the cash row cites it. A line that
    # was not looked at is not confirmed (rule 3): a failure, never a pass.
    pdf = write_text_pdf(tmp_path / "f.pdf", [["net_income 228"], blank_page])
    answer = minimal_answer(balance_rows={"cash": [
        {"label": "cash", "value": 77, "page": 2}]})
    found = failures(answer, pdf)
    assert len(found) == 1, found
    (message,) = found
    assert "cannot be confirmed" in message
    assert "'cash'" in message and "page 2" in message


def test_a_wrapped_row_is_found_through_a_real_pdf(tmp_path: Path) -> None:
    # The wrap of the rule cases, as two text lines of a written page: the label's
    # last word on the line below the figures. The PDF's text lines must arrive as
    # the two lines written, so the joined form finds the row.
    pdf = write_text_pdf(tmp_path / "f.pdf", [[
        "net_income 228",
        "Payments for business acquisitions, net of cash (53) (12)",
        "acquired",
    ]])
    answer = minimal_answer(year_rows={"capex": [{
        "label": "Payments for business acquisitions, net of cash acquired",
        "value": 53, "page": 1}]})
    assert failures(answer, pdf) == []


def test_each_cited_page_is_read_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 18 rows cite page 1 and 20 cite page 2; pages 3 and 4 are cited by none.
    # Each cited page's text is read once, and only the cited pages.
    import pdfplumber.page

    answer = full_answer()
    pages = write_text_pdf(tmp_path / "f.pdf", [
        [f"{f} {101 + i}" for i, f in enumerate(YEAR_LINE_FIELDS)],
        [f"{f} {201 + i}" for i, f in enumerate(BALANCE_SHEET_LINE_FIELDS)],
        ["uncited page three"], ["uncited page four"],
    ], leading=12)
    reads: list[int] = []
    real = pdfplumber.page.Page.extract_text

    def counting(self: Any, *args: Any, **kwargs: Any) -> Any:
        reads.append(self.page_number)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(pdfplumber.page.Page, "extract_text", counting)
    assert failures(answer, pages) == []
    assert sorted(reads) == [1, 2]


def test_an_empty_balance_sheet_is_not_walked(tmp_path: Path) -> None:
    # `{}` is the answer for "balance sheet not asked for" (pass1_problems): no
    # balance sheet row exists, so none is looked up and none fails.
    pdf = write_text_pdf(tmp_path / "f.pdf", [["net_income 228"]])
    answer = minimal_answer()
    answer["latest_balance_sheet"] = {}
    assert failures(answer, pdf) == []


# --- a PDF pdfplumber cannot open ----------------------------------------------

STAND_IN = b"%PDF-1.4 not a PDF pdfplumber can open, for the P12a tests\n"


def test_route_b_wrapper_stops_naming_the_pdf_by_sha256() -> None:
    answer = minimal_answer()
    digest = hashlib.sha256(STAND_IN).hexdigest()
    with pytest.raises(ValueError) as excinfo:
        printed_line_page_failures(json.dumps(answer), STAND_IN)
    assert digest[:16] in str(excinfo.value)
    # The type pdfplumber raises is caught by name and chained, never a broad catch.
    assert isinstance(excinfo.value.__cause__, PdfminerException)


def test_route_b_wrapper_stops_on_a_malformed_answer_before_the_pdf() -> None:
    # The wrapper re-runs the shape check: an absent key is a Pass1ShapeError
    # naming it, not a KeyError from the walk (and the PDF is never opened).
    answer = minimal_answer()
    del answer["historical_years"][0]["capex"]
    with pytest.raises(Pass1ShapeError) as excinfo:
        printed_line_page_failures(json.dumps(answer), STAND_IN)
    assert any("'capex'" in p for p in excinfo.value.problems), excinfo.value.problems


def test_route_b_loader_stops_naming_the_filing_and_check_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = tmp_path / "TST_10-K_2024.pdf"
    pdf.write_bytes(STAND_IN)
    data = session_dict(pdf.resolve())  # records the stand-in's own sha256
    path = write_session(tmp_path, data)
    with pytest.raises(ValueError) as excinfo:
        load_session_extraction(path)
    message = str(excinfo.value)
    # One line names the session file, the filing index and the PDF's name.
    assert one_line_names([message], str(path), "filings[0]", pdf.name), message
    assert cmd_check(path) == 2
    assert pdf.name in capsys.readouterr().out


def test_route_a_stops_naming_the_pdf_by_sha256_and_makes_no_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = json.dumps(attack_answer(honest=True))
    calls = install_script(monkeypatch, [answer])
    digest = hashlib.sha256(STAND_IN).hexdigest()
    with pytest.raises(ValueError) as excinfo:
        run_pass1(STAND_IN)
    assert digest[:16] in str(excinfo.value)
    # The run stops: no retry could make the PDF readable.
    assert len(calls) == 1


# ===========================================================================
# Builders for routes A and B: a small balance sheet that balances, by hand
# ===========================================================================
#
# The filing prints, on page 2 (the balance sheet):
#   Cash and cash equivalents       100
#   Short-term investments           50
#   Receivables, net                 80
#   Inventories                      60
#   Prepaid expenses and other    4,124
#   Property and equipment, net     300
#   Goodwill                        200
#   Intangible assets, net           40
#   Other long-term assets           20
#   Total assets                  4,974   = 100+50+80+60+4,124+300+200+40+20
#   Accounts payable                 70
#   Accrued liabilities              30
#   Other current liabilities        15
#   Short-term borrowings            25
#   Long-term debt                  400
#   Other long-term liabilities      35
#   Total shareholders' equity    4,399   = 4,974 - (70+30+15+25+400+35 = 575)
#   Total liabilities and equity  4,974   = 575 + 4,399
# and, on page 1, an income statement whose checks reconcile:
#   revenue 1,000; cost 400; gross profit 600 = 1,000 - 400; sga 150; R&D 100;
#   other opex 50; operating income 300 = 600 - 150 - 100 - 50; interest income
#   10; interest expense 20; other (5); tax 57; net income 228 = 300+10-20-5-57.
# The cash flow rows are on page 3: D&A 30, CFO 290, capex (70), SBC 25, change in
# working capital (15); diluted shares 48 on page 1.

_INCOME = {
    "revenue": ("Total revenues", 1000), "cost_of_revenue": ("Cost of sales", 400),
    "gross_profit": ("Gross profit", 600), "sga": ("Selling, general and administrative", 150),
    "rd_expense": ("Research and development", 100),
    "other_operating_expense": ("Other operating expense", 50),
    "operating_income": ("Operating income", 300),
    "interest_income": ("Interest income", 10), "interest_expense": ("Interest expense", 20),
    "other_non_operating": ("Other gains and losses", -5),
    "tax_expense": ("Provision for income taxes", 57),
    "net_income": ("Consolidated net income", 228),
    "diluted_shares": ("Weighted-average diluted shares", 48),
}
_CASH_FLOW = {
    "depreciation_amortization": ("Depreciation and amortization", 30),
    "cfo": ("Net cash provided by operating activities", 290),
    "capex": ("Payments for property and equipment", -70),
    "sbc": ("Share-based compensation", 25),
    "change_in_working_capital": ("Changes in operating working capital", -15),
}
_BALANCE = {
    "cash": ("Cash and cash equivalents", 100),
    "short_term_investments": ("Short-term investments", 50),
    "accounts_receivable": ("Receivables, net", 80), "inventory": ("Inventories", 60),
    "other_current_assets": ("Prepaid expenses and other", 4124),
    "ppe_net": ("Property and equipment, net", 300), "goodwill": ("Goodwill", 200),
    "intangible_assets": ("Intangible assets, net", 40),
    "other_non_current_assets": ("Other long-term assets", 20),
    "total_assets": ("Total assets", 4974),
    "accounts_payable": ("Accounts payable", 70),
    "accrued_liabilities": ("Accrued liabilities", 30),
    "other_current_liabilities": ("Other current liabilities", 15),
    "short_term_debt": ("Short-term borrowings", 25), "long_term_debt": ("Long-term debt", 400),
    "other_non_current_liabilities": ("Other long-term liabilities", 35),
    "total_equity": ("Total shareholders' equity", 4399),
    "total_liabilities_and_equity": ("Total liabilities and equity", 4974),
}
INVENTED_LABEL = "Other current assets"


def _row(label: str, value: float, page: int) -> list[dict[str, Any]]:
    return [{"label": label, "value": value, "page": page}]


def attack_answer(*, honest: bool) -> dict[str, Any]:
    """The filing above as Pass 1 reads it. With `honest=False`, the real row
    "Prepaid expenses and other" 4,124 is replaced by an invented one, "Other
    current assets" 4,124: the same value, so every total still balances."""
    entry: dict[str, Any] = {"year": 2024}
    entry |= {k: _row(label, v, 1) for k, (label, v) in _INCOME.items()}
    entry |= {k: _row(label, v, 3) for k, (label, v) in _CASH_FLOW.items()}
    balance: dict[str, Any] = {"year": 2024}
    balance |= {k: _row(label, v, 2) for k, (label, v) in _BALANCE.items()}
    balance |= {memo: [] for memo in NCI_MEMOS}  # this filing prints no NCI
    if not honest:
        balance["other_current_assets"] = _row(INVENTED_LABEL, 4124, 2)
    return {
        "ticker": TICKER,
        "company_name": COMPANY,
        "currency": "USD",
        "units": {"printed": "(in millions)", "page": 1},
        "share_units": {"printed": "(in millions)", "page": 1},
        "historical_years": [entry],
        "latest_balance_sheet": balance,
    }


def filing_pdf(directory: Path) -> Path:
    """The filing: the honest answer's rows, printed on their pages."""
    return write_pass1_pdf(directory / "TST_10-K_2024.pdf", attack_answer(honest=True),
                           cover="Test filing for the P12a page check").resolve()


def minimal_answer(
    year_rows: dict[str, list[dict[str, Any]]] | None = None,
    balance_rows: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Every key present, every field `[]` except net_income (never empty: 228 on
    page 1) and the rows given. The shape check passes; the walk sees only these."""
    entry: dict[str, Any] = {"year": 2024} | {f: [] for f in YEAR_LINE_FIELDS}
    entry["net_income"] = _row("net_income", 228, 1)
    entry |= year_rows or {}
    balance: dict[str, Any] = {"year": 2024} | {f: [] for f in BALANCE_SHEET_LINE_FIELDS}
    balance |= balance_rows or {}
    return {
        "ticker": TICKER,
        "company_name": COMPANY,
        "currency": "USD",
        "units": {"printed": "(in millions)", "page": 1},
        "share_units": {"printed": "(in millions)", "page": 1},
        "historical_years": [entry],
        "latest_balance_sheet": balance,
    }


def attack_session(directory: Path, *, honest: bool) -> Path:
    """A one-filing session file over the filing PDF, holding the given answer.
    The PDF is written first: the session records its sha256."""
    data = session_dict(filing_pdf(directory))
    data["filings"][0]["pass1"] = attack_answer(honest=honest)
    data["filings"][0]["pass2"] = {"non_recurring_items": []}
    data["filings"][0]["pages_read"]["pass1"] = [1, 2, 3]
    return write_session(directory, data, name=f"session_{'honest' if honest else 'attack'}.json")


# ===========================================================================
# 4. Route B: check
# ===========================================================================

def test_check_exits_0_when_every_row_is_printed_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert cmd_check(attack_session(tmp_path, honest=True)) == 0
    out = capsys.readouterr().out
    clean = [line for line in out.splitlines() if line.startswith("Clean")]
    assert len(clean) == 1, out
    # The P12a assignment, step 3: the Clean line says every printed line was found
    # on its page.
    assert "every printed line was found on the page it cites" in clean[0]


def test_check_exits_1_when_the_only_problem_is_a_line_not_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert cmd_check(attack_session(tmp_path, honest=False)) == 1
    out = capsys.readouterr().out
    assert "Clean" not in out
    # One line names where, the field, the line index, the label, the value and
    # the page (P12a assignment, step 1, `message`).
    named = [line for line in out.splitlines()
             if all(part in line for part in (
                 "filings[0]", "balance sheet 2024", "'other_current_assets'", "line 0",
                 INVENTED_LABEL, "page 2"))]
    assert len(named) == 1, out
    assert re.search(r"4,?124", named[0]), named[0]


def test_check_exits_1_on_a_page_with_no_text_layer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    # The cash flow rows cite page 3, which prints nothing: five lines that cannot
    # be confirmed, a failed check each, so exit 1 and never "Clean".
    pdf = write_text_pdf(tmp_path / "TST_10-K_2024.pdf", [
        ["(in millions)", *(f"{label} {v}" for label, v in _INCOME.values())],
        [f"{label} {v}" for label, v in _BALANCE.values()],
        [],
    ])
    data = session_dict(pdf.resolve())
    data["filings"][0]["pass1"] = attack_answer(honest=True)
    data["filings"][0]["pass2"] = {"non_recurring_items": []}
    path = write_session(tmp_path, data)
    assert cmd_check(path) == 1
    out = capsys.readouterr().out
    assert "Clean" not in out
    unconfirmed = [line for line in out.splitlines() if "cannot be confirmed" in line]
    assert len(unconfirmed) == 5, out


# ===========================================================================
# 5. Route A: the check retry, with _call_llm stubbed
# ===========================================================================

_RESOLUTION = ProviderResolution(
    provider="claude", model="stub-model",
    reasoning_label="adaptive thinking, effort 'high' (config.EXTRACTION_EFFORT)",
    transport="anthropic-direct",
    transport_label="stub", credential="anthropic-api-key",
    credential_source="stub: no call is made",
)


def install_script(
    monkeypatch: pytest.MonkeyPatch, answers: list[str],
) -> list[tuple[str, bytes | None]]:
    """`_call_llm` answering `answers` in order; a call beyond them raises."""
    calls: list[tuple[str, bytes | None]] = []

    def stub(system_prompt: str, user_prompt: str, resolution: ProviderResolution,
             pdf_bytes: bytes | None = None) -> tuple[str, int, int]:
        if len(calls) >= len(answers):
            raise AssertionError(f"call {len(calls) + 1} was not scripted")
        calls.append((user_prompt, pdf_bytes))
        return answers[len(calls) - 1], 0, 0

    monkeypatch.setattr(ce, "_call_llm", stub)
    return calls


def run_pass1(pdf_bytes: bytes) -> Any:
    outcome = ce._run_financials_pass(
        pdf_bytes, TICKER, COMPANY, _RESOLUTION, target_years=None, include_bs=True,
    )
    if isinstance(outcome, tuple):
        outcome = outcome[0]
    return outcome


def test_route_a_a_line_not_found_goes_to_the_check_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = filing_pdf(tmp_path).read_bytes()
    attack = json.dumps(attack_answer(honest=False))
    honest = json.dumps(attack_answer(honest=True))
    calls = install_script(monkeypatch, [attack, honest])
    fin = run_pass1(pdf_bytes)
    # One retry, carrying the PDF, then the honest answer is used.
    assert len(calls) == 2
    assert calls[1][1] == pdf_bytes
    assert fin.get_balance_sheet(2024).other_current_assets == 4124.0


def test_route_a_retry_names_label_field_and_page_and_no_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = filing_pdf(tmp_path).read_bytes()
    attack = json.dumps(attack_answer(honest=False))
    calls = install_script(monkeypatch, [attack, json.dumps(attack_answer(honest=True))])
    run_pass1(pdf_bytes)
    prompt = calls[1][0]
    assert prompt.endswith(attack), "the retry no longer ends with the answer"
    text = prompt[: -len(attack)]
    # Only the page check fails (the sheet balances, the income statement
    # reconciles): one failure line, naming the row.
    failure_lines = [line for line in text.splitlines() if line.startswith("  - ")]
    assert len(failure_lines) == 1, text
    (line,) = failure_lines
    for part in (INVENTED_LABEL, "other_current_assets", "page 2"):
        assert part in line, (part, line)
    # No value and no amount: the only numbers the line may hold are the year
    # 2024, the line index 0 and the page 2 (hand-listed from the row).
    assert set(re.findall(r"\d+(?:[,.]\d+)*", line)) <= {"2024", "0", "2"}, line
    for amount in ("4,124", "4124", "4,974", "4974", "4,399", "4399"):
        assert amount not in text, (amount, text)


def test_route_a_after_the_last_retry_prints_the_failure_and_keeps_the_figures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf_bytes = filing_pdf(tmp_path).read_bytes()
    attack = json.dumps(attack_answer(honest=False))
    calls = install_script(monkeypatch, [attack] * 3)
    fin = run_pass1(pdf_bytes)
    # The first call and two retries (MAX_RETRIES), each with the PDF.
    assert len(calls) == 3
    assert all(sent == pdf_bytes for _, sent in calls)
    out = capsys.readouterr().out
    assert "[Pass 1 FAIL]" in out
    shown = out.split("[Pass 1 FAIL]", 1)[1].splitlines()
    assert any(INVENTED_LABEL in line and "'other_current_assets'" in line
               and "page 2" in line for line in shown), out
    # Kept, as read: the invented row's 4,124, and the mapped assets 4,974.
    bs = fin.get_balance_sheet(2024)
    assert bs.other_current_assets == 4124.0
    assert bs.total_assets == 4974.0


# ===========================================================================
# 6. The F7 attack, end to end
# ===========================================================================

def test_the_f7_attack_balances_and_the_page_check_names_the_invented_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The case the unit exists for. The answer's balance sheet balances because
    "Prepaid expenses and other" 4,124 was replaced by an invented "Other current
    assets" 4,124: assets 4,974 against the printed 4,974, L + E 4,974 against
    4,974 (by hand above). The balance check passes; the page check does not."""
    loaded = load_session_extraction(attack_session(tmp_path, honest=False))
    bs = loaded.financials.get_balance_sheet(2024)
    # The balance check passes: both sides map to the printed totals.
    assert bs.total_assets == 4974.0
    assert bs.printed_total_assets_difference == 0.0
    assert bs.total_liabilities_and_equity == 4974.0
    out = capsys.readouterr().out
    assert re.search(r"Total Assets\s+4,974\s+4,974\s+\+0\s+OK", out), out
    assert re.search(r"Total L \+ E\s+4,974\s+4,974\s+\+0\s+OK", out), out
    # The page check fails, once, naming that row.
    assert len(loaded.validation_errors) == 1, loaded.validation_errors
    assert one_line_names(loaded.validation_errors, "balance sheet 2024",
                          "'other_current_assets'", "line 0", INVENTED_LABEL,
                          "page 2"), loaded.validation_errors


def test_the_f7_control_the_honest_answer_has_no_failure(tmp_path: Path) -> None:
    # The same filing read honestly: no failure of either kind.
    loaded = load_session_extraction(attack_session(tmp_path, honest=True))
    assert loaded.validation_errors == []
    assert loaded.financials.get_balance_sheet(2024).total_assets == 4974.0
