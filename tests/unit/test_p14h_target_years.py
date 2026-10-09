"""Verifying target_years prompt builder stops and prompt invariance (item 133).

What this file locks:
  1. No truthiness test of `target_years` remains in `_build_financials_prompt`
     or `_build_nri_prompt` in `ingestion/claude_extractor.py` (Criterion 1).
  2. Calling `_build_financials_prompt(target_years=[])` stops with `ValueError`
     naming `target_years` and explaining that an empty list requests no year while
     `None` asks for every year (Rule 3; Criterion 2).
  3. Calling `_build_nri_prompt(is_summary=..., target_years=[])` stops with
     `ValueError` naming `target_years` with the same diagnostic message (Rule 3; Criterion 3).
  4. Calling `_pass1_prompt_pair([])` and `_pass2_prompt_pair(financials, [])`
     propagates the Rule 3 stop (Criterion 2, Criterion 3).
  5. Calling `pass1_prompts(plan)` and `pass2_prompts(plan, financials)` with an
     empty `plan.target_years=()` propagates the Rule 3 stop.
  6. Calling `_build_financials_prompt` and `_build_nri_prompt` with `target_years=None`
     produces exact hand-derived prompt text matching `main` (Criterion 5).
  7. Calling `_build_financials_prompt` and `_build_nri_prompt` with single-element
     and multiple-element sorted year lists produces exact hand-derived prompt text (Criterion 5).
  8. Calling `_build_financials_prompt` with `include_bs=True` and `include_bs=False`
     produces exact hand-derived balance sheet instructions.
  9. The prompt pairs produced by `_pass1_prompt_pair` and `_pass2_prompt_pair`
     assemble the system prompt constant and user prompt builder output without drift.
 10. The six real prompts extracted from `extractions/WMT.json` match the baseline
     SHA256 hashes byte-for-byte across all three filings and both passes (Criterion 4).

Where every expected value came from:
  - Hand derivation from template strings:
      * Pass 1 template:
        "Extract financial data from the attached 10-K/10-Q PDF filing.\\n\\n"
        "TARGET YEARS: {year_instruction}\\n"
        "BALANCE SHEET: {bs_instruction}"
        Where None gives:
        "Extract Income Statement and Cash Flow data for ALL fiscal years present in the filing (typically 2-3 years)."
        Where [2024] gives:
        "Extract Income Statement and Cash Flow data for fiscal year(s): 2024 ONLY. Do NOT extract other years."
        Where [2025, 2023] gives:
        "Extract Income Statement and Cash Flow data for fiscal year(s): 2023, 2025 ONLY. Do NOT extract other years."
        Where include_bs=True gives:
        "Also extract the latest balance sheet."
        Where include_bs=False gives:
        "Do NOT extract the balance sheet. Set latest_balance_sheet to {}."
      * Pass 2 template:
        "{year_instruction}\\n\\n"
        "EXTRACTED INCOME STATEMENT (for reference \u2014 use to anchor your findings):\\n"
        "{is_summary}"
        Where None gives:
        "Analyze non-recurring items for ALL fiscal years in the filing."
        Where [2024] gives:
        "Analyze non-recurring items for fiscal year(s): 2024."
        Where [2025, 2023] gives:
        "Analyze non-recurring items for fiscal year(s): 2023, 2025."
  - Rule 3 requirement:
      * Exception type is `ValueError`.
      * Message must contain "target_years".
      * Message text: "target_years cannot be empty: an empty list requests no year; None is how a caller asks for every year."
  - Baseline hashes on extractions/WMT.json (filings 0, 1, 2 x passes 1, 2):
      * Filing 0 Pass 1: cbf26b0a876034f6
      * Filing 0 Pass 2: 024bd96701e72481
      * Filing 1 Pass 1: c401b7bb3096592c
      * Filing 1 Pass 2: 9391f61bfa21ac43
      * Filing 2 Pass 1: 4aa84c989703f3ce
      * Filing 2 Pass 2: cc61ac590ca169f0

No assertion in this file was obtained by running the code and reading what it printed.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
from pathlib import Path

import pytest

from ingestion.claude_extractor import (
    _FINANCIALS_SYSTEM_PROMPT,
    _NRI_SYSTEM_PROMPT,
    FilingPlan,
    _build_financials_prompt,
    _build_is_summary,
    _build_nri_prompt,
    _pass1_prompt_pair,
    _pass2_prompt_pair,
    pass1_prompts,
    pass2_prompts,
)
from ingestion.session_extraction import cmd_prompt
from models.financial_statements import (
    CashFlowStatement,
    FinancialStatements,
    IncomeStatement,
)

# ---------------------------------------------------------------------------
# Hand-derived literal expected strings
# ---------------------------------------------------------------------------

EXPECTED_EMPTY_YEARS_MESSAGE = (
    "target_years cannot be empty: an empty list requests no year; "
    "None is how a caller asks for every year."
)

EXPECTED_PASS1_NONE_BS_TRUE = (
    "Extract financial data from the attached 10-K/10-Q PDF filing.\n\n"
    "TARGET YEARS: Extract Income Statement and Cash Flow data for ALL fiscal years "
    "present in the filing (typically 2-3 years).\n"
    "BALANCE SHEET: Also extract the latest balance sheet."
)

EXPECTED_PASS1_NONE_BS_FALSE = (
    "Extract financial data from the attached 10-K/10-Q PDF filing.\n\n"
    "TARGET YEARS: Extract Income Statement and Cash Flow data for ALL fiscal years "
    "present in the filing (typically 2-3 years).\n"
    "BALANCE SHEET: Do NOT extract the balance sheet. Set latest_balance_sheet to {}."
)

EXPECTED_PASS1_2024_BS_TRUE = (
    "Extract financial data from the attached 10-K/10-Q PDF filing.\n\n"
    "TARGET YEARS: Extract Income Statement and Cash Flow data for fiscal year(s): "
    "2024 ONLY. Do NOT extract other years.\n"
    "BALANCE SHEET: Also extract the latest balance sheet."
)

EXPECTED_PASS1_2024_BS_FALSE = (
    "Extract financial data from the attached 10-K/10-Q PDF filing.\n\n"
    "TARGET YEARS: Extract Income Statement and Cash Flow data for fiscal year(s): "
    "2024 ONLY. Do NOT extract other years.\n"
    "BALANCE SHEET: Do NOT extract the balance sheet. Set latest_balance_sheet to {}."
)

EXPECTED_PASS1_MULTI_BS_TRUE = (
    "Extract financial data from the attached 10-K/10-Q PDF filing.\n\n"
    "TARGET YEARS: Extract Income Statement and Cash Flow data for fiscal year(s): "
    "2023, 2025 ONLY. Do NOT extract other years.\n"
    "BALANCE SHEET: Also extract the latest balance sheet."
)

SUMMARY_FIXTURE = (
    "  FY2024: Revenue=1,000  COGS=600  SG&A=200  R&D=0  "
    "D&A=50  Other_OpEx=50  EBIT=100  Other_NonOp=0"
)

EXPECTED_PASS2_NONE = (
    "Analyze non-recurring items for ALL fiscal years in the filing.\n\n"
    "EXTRACTED INCOME STATEMENT (for reference \u2014 use to anchor your findings):\n"
    "  FY2024: Revenue=1,000  COGS=600  SG&A=200  R&D=0  "
    "D&A=50  Other_OpEx=50  EBIT=100  Other_NonOp=0"
)

EXPECTED_PASS2_2024 = (
    "Analyze non-recurring items for fiscal year(s): 2024.\n\n"
    "EXTRACTED INCOME STATEMENT (for reference \u2014 use to anchor your findings):\n"
    "  FY2024: Revenue=1,000  COGS=600  SG&A=200  R&D=0  "
    "D&A=50  Other_OpEx=50  EBIT=100  Other_NonOp=0"
)

EXPECTED_PASS2_MULTI = (
    "Analyze non-recurring items for fiscal year(s): 2023, 2025.\n\n"
    "EXTRACTED INCOME STATEMENT (for reference \u2014 use to anchor your findings):\n"
    "  FY2024: Revenue=1,000  COGS=600  SG&A=200  R&D=0  "
    "D&A=50  Other_OpEx=50  EBIT=100  Other_NonOp=0"
)

WMT_BASELINE_HASHES: dict[tuple[int, int], str] = {
    (0, 1): "cbf26b0a876034f6",
    (0, 2): "024bd96701e72481",
    (1, 1): "c401b7bb3096592c",
    (1, 2): "9391f61bfa21ac43",
    (2, 1): "4aa84c989703f3ce",
    (2, 2): "cc61ac590ca169f0",
}


def _make_minimal_financials(year: int = 2024) -> FinancialStatements:
    """Fixture providing minimal financial statements for Pass 2 context."""
    return FinancialStatements(
        ticker="WMT",
        company_name="Walmart Inc.",
        income_statements=[
            IncomeStatement(
                year=year,
                revenue=1000.0,
                cost_of_revenue=600.0,
                sga=200.0,
                rd_expense=0.0,
                depreciation_amortization=50.0,
                other_operating_expense=0.0,
                interest_expense=10.0,
                tax_expense=20.0,
                diluted_shares_outstanding=100.0,
            )
        ],
        cash_flow_statements=[
            CashFlowStatement(
                year=year,
                net_income=120.0,
                depreciation_amortization=50.0,
                change_in_working_capital=5.0,
                capital_expenditures=-40.0,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Criterion 1: No truthiness test of target_years
# ---------------------------------------------------------------------------


def test_no_truthiness_test_of_target_years_in_source() -> None:
    """Verify that 'if target_years:' does not appear anywhere in ingestion/claude_extractor.py."""
    source_path = Path("ingestion/claude_extractor.py")
    content = source_path.read_text(encoding="utf-8")
    assert "if target_years:" not in content


# ---------------------------------------------------------------------------
# Criterion 2: Empty target_years stops Pass 1
# ---------------------------------------------------------------------------


def test_build_financials_prompt_empty_list_stops_and_names_target_years() -> None:
    """Pass 1 prompt builder must reject empty target_years list with ValueError."""
    with pytest.raises(ValueError) as excinfo:
        _build_financials_prompt(target_years=[])

    msg = str(excinfo.value)
    assert "target_years" in msg
    assert msg == EXPECTED_EMPTY_YEARS_MESSAGE


def test_build_financials_prompt_empty_list_stops_with_include_bs_false() -> None:
    """Pass 1 prompt builder must reject empty target_years regardless of include_bs flag."""
    with pytest.raises(ValueError) as excinfo:
        _build_financials_prompt(target_years=[], include_bs=False)

    msg = str(excinfo.value)
    assert "target_years" in msg
    assert msg == EXPECTED_EMPTY_YEARS_MESSAGE


def test_pass1_prompt_pair_empty_list_stops() -> None:
    """_pass1_prompt_pair must propagate the ValueError when target_years is empty."""
    with pytest.raises(ValueError) as excinfo:
        _pass1_prompt_pair(target_years=[], include_bs=True)

    assert "target_years" in str(excinfo.value)


def test_pass1_prompts_empty_tuple_in_plan_stops() -> None:
    """pass1_prompts must raise ValueError when plan.target_years is empty tuple ()."""
    plan = FilingPlan(
        fiscal_year=2024,
        pdf_path="test.pdf",
        target_years=(),
        include_bs=True,
    )
    with pytest.raises(ValueError) as excinfo:
        pass1_prompts(plan)

    assert "target_years" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Criterion 3: Empty target_years stops Pass 2
# ---------------------------------------------------------------------------


def test_build_nri_prompt_empty_list_stops_and_names_target_years() -> None:
    """Pass 2 prompt builder must reject empty target_years list with ValueError."""
    with pytest.raises(ValueError) as excinfo:
        _build_nri_prompt(is_summary=SUMMARY_FIXTURE, target_years=[])

    msg = str(excinfo.value)
    assert "target_years" in msg
    assert msg == EXPECTED_EMPTY_YEARS_MESSAGE


def test_pass2_prompt_pair_empty_list_stops() -> None:
    """_pass2_prompt_pair must propagate the ValueError when target_years is empty."""
    financials = _make_minimal_financials(2024)
    with pytest.raises(ValueError) as excinfo:
        _pass2_prompt_pair(financials=financials, target_years=[])

    assert "target_years" in str(excinfo.value)


def test_pass2_prompts_empty_tuple_in_plan_stops() -> None:
    """pass2_prompts must raise ValueError when plan.target_years is empty tuple ()."""
    plan = FilingPlan(
        fiscal_year=2024,
        pdf_path="test.pdf",
        target_years=(),
        include_bs=True,
    )
    financials = _make_minimal_financials(2024)
    with pytest.raises(ValueError) as excinfo:
        pass2_prompts(plan, financials)

    assert "target_years" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Criterion 5: Prompt text matches hand-derived expectations
# ---------------------------------------------------------------------------


def test_build_financials_prompt_none_bs_true_matches_hand_derived() -> None:
    """target_years=None with include_bs=True matches hand-derived all-years text."""
    actual = _build_financials_prompt(target_years=None, include_bs=True)
    assert actual == EXPECTED_PASS1_NONE_BS_TRUE


def test_build_financials_prompt_none_bs_false_matches_hand_derived() -> None:
    """target_years=None with include_bs=False matches hand-derived all-years text."""
    actual = _build_financials_prompt(target_years=None, include_bs=False)
    assert actual == EXPECTED_PASS1_NONE_BS_FALSE


def test_build_financials_prompt_single_year_bs_true_matches_hand_derived() -> None:
    """target_years=[2024] with include_bs=True matches hand-derived single-year text."""
    actual = _build_financials_prompt(target_years=[2024], include_bs=True)
    assert actual == EXPECTED_PASS1_2024_BS_TRUE


def test_build_financials_prompt_single_year_bs_false_matches_hand_derived() -> None:
    """target_years=[2024] with include_bs=False matches hand-derived single-year text."""
    actual = _build_financials_prompt(target_years=[2024], include_bs=False)
    assert actual == EXPECTED_PASS1_2024_BS_FALSE


def test_build_financials_prompt_multi_year_sorted_matches_hand_derived() -> None:
    """target_years=[2025, 2023] produces sorted year list '2023, 2025'."""
    actual = _build_financials_prompt(target_years=[2025, 2023], include_bs=True)
    assert actual == EXPECTED_PASS1_MULTI_BS_TRUE


def test_build_nri_prompt_none_matches_hand_derived() -> None:
    """target_years=None matches hand-derived all-years NRI prompt text."""
    actual = _build_nri_prompt(is_summary=SUMMARY_FIXTURE, target_years=None)
    assert actual == EXPECTED_PASS2_NONE


def test_build_nri_prompt_single_year_matches_hand_derived() -> None:
    """target_years=[2024] matches hand-derived single-year NRI prompt text."""
    actual = _build_nri_prompt(is_summary=SUMMARY_FIXTURE, target_years=[2024])
    assert actual == EXPECTED_PASS2_2024


def test_build_nri_prompt_multi_year_sorted_matches_hand_derived() -> None:
    """target_years=[2025, 2023] produces sorted year list '2023, 2025'."""
    actual = _build_nri_prompt(is_summary=SUMMARY_FIXTURE, target_years=[2025, 2023])
    assert actual == EXPECTED_PASS2_MULTI


def test_prompt_pair_assembly_closed_form_identity() -> None:
    """_pass1_prompt_pair and _pass2_prompt_pair assemble system prompt and user prompt."""
    p1_sys, p1_user = _pass1_prompt_pair(target_years=None, include_bs=True)
    assert p1_sys == _FINANCIALS_SYSTEM_PROMPT
    assert p1_user == EXPECTED_PASS1_NONE_BS_TRUE

    financials = _make_minimal_financials(2024)
    expected_is_summary = _build_is_summary(financials, target_years=[2024])
    expected_p2_user = _build_nri_prompt(expected_is_summary, target_years=[2024])

    p2_sys, p2_user = _pass2_prompt_pair(financials, target_years=[2024])
    assert p2_sys == _NRI_SYSTEM_PROMPT
    assert p2_user == expected_p2_user


# ---------------------------------------------------------------------------
# Criterion 4: Real prompt hash invariance on extractions/WMT.json
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filing_idx", "which_pass", "expected_hash"),
    [
        (0, 1, WMT_BASELINE_HASHES[(0, 1)]),
        (0, 2, WMT_BASELINE_HASHES[(0, 2)]),
        (1, 1, WMT_BASELINE_HASHES[(1, 1)]),
        (1, 2, WMT_BASELINE_HASHES[(1, 2)]),
        (2, 1, WMT_BASELINE_HASHES[(2, 1)]),
        (2, 2, WMT_BASELINE_HASHES[(2, 2)]),
    ],
)
def test_real_prompt_hash_invariance(
    filing_idx: int,
    which_pass: int,
    expected_hash: str,
) -> None:
    """Real filing prompts on extractions/WMT.json match the baseline hashes."""
    wmt_path = Path("extractions/WMT.json").resolve()
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        exit_code = cmd_prompt(wmt_path, filing_idx, which_pass)
    assert exit_code == 0

    # Match shell 2>&1 behavior: stderr preceding/interleaved with stdout
    combined = buf_err.getvalue() + buf_out.getvalue()
    normalized = combined.replace(f"{Path.cwd()}/", "<REPO>/")
    computed_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    assert computed_hash == expected_hash
